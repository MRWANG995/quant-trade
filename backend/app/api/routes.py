from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from app.auth.deps import require_auth_if_enabled
from app.data.stooq_provider import StooqProvider
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.brokers.ib import IBAdapter
from app.brokers.oanda import OandaAdapter
from app.config import get_settings
from app.data.demo_bars import seed_demo_bars
from app.data.readiness import get_market_data_readiness
from app.data.sync_service import sync_all_instruments, sync_instrument_bars
from app.database import get_db
from app.data.risk_free_rate import (
    get_latest_risk_free_rate,
    get_risk_free_rate_for_period,
    refresh_risk_free_rates,
)
from app.engine.backtest import BacktestParams, run_backtest
from app.engine.live import run_daily_scan
from app.engine.metrics import compute_metrics
from app.engine.portfolio import get_orders, get_portfolio_summary
from app.models.entities import BacktestResult, Bar, Instrument, RunLog, Signal
from app.schemas import BacktestRequest, BarOut, InstrumentOut

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth_if_enabled)])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/portfolio")
async def portfolio(session: AsyncSession = Depends(get_db)):
    return await get_portfolio_summary(session)


@router.get("/instruments", response_model=list[InstrumentOut])
async def list_instruments(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.symbol)
    )
    return result.scalars().all()


@router.get("/instruments/{instrument_id}/bars", response_model=list[BarOut])
async def instrument_bars(
    instrument_id: int,
    limit: int = 300,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Bar)
        .where(Bar.instrument_id == instrument_id)
        .order_by(Bar.trade_date.desc())
        .limit(limit)
    )
    bars = list(reversed(result.scalars().all()))
    return bars


@router.get("/signals")
async def list_signals(
    signal_date: Optional[date] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
):
    q = select(Signal).options(selectinload(Signal.instrument)).order_by(Signal.created_at.desc())
    if signal_date:
        q = q.where(Signal.signal_date == signal_date)
    result = await session.execute(q.limit(limit))
    signals = result.scalars().all()
    return [
        {
            "id": s.id,
            "symbol": s.instrument.symbol,
            "signal_date": s.signal_date.isoformat(),
            "side": s.side.value,
            "strength": s.strength,
            "reason": s.reason,
            "executed": s.executed,
        }
        for s in signals
    ]


@router.get("/orders")
async def orders(
    limit: int = 50,
    strategy_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
):
    return await get_orders(session, limit, strategy_id=strategy_id)


@router.post("/backtest")
async def backtest(body: BacktestRequest, session: AsyncSession = Depends(get_db)):
    if body.end_date <= body.start_date:
        raise HTTPException(400, "end_date must be after start_date")
    try:
        result = await run_backtest(
            session,
            BacktestParams(
                start_date=body.start_date,
                end_date=body.end_date,
                initial_capital=body.initial_capital,
                strategy_id=body.strategy_id,
                risk_per_trade=body.risk_per_trade,
                param_overrides=body.param_overrides,
            ),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _backtest_response(result)


def _backtest_response(result: BacktestResult) -> dict:
    metrics = result.metrics or None
    if not metrics:
        # 旧记录懒计算：用 equity_curve + trades 现场算（rf=0，老回测无利率上下文）
        metrics = compute_metrics(
            equity_curve=result.equity_curve or [],
            trades=result.trades or [],
            initial_capital=result.initial_capital,
            final_equity=result.final_equity,
            risk_free_rate_annual=0.0,
        )
    return {
        "id": result.id,
        "strategy_id": result.strategy_id,
        "strategy": result.strategy,
        "strategy_name": (result.params or {}).get("strategy_name", result.strategy),
        "params": result.params,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "initial_capital": result.initial_capital,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "trade_count": result.trade_count,
        "final_equity": result.final_equity,
        "equity_curve": result.equity_curve,
        "trades": result.trades,
        "markers": result.markers or [],
        "metrics": metrics,
    }


@router.get("/backtest/{result_id}")
async def get_backtest(result_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.get(BacktestResult, result_id)
    if not result:
        raise HTTPException(404, "Backtest not found")
    return _backtest_response(result)


@router.get("/backtest/{result_id}/chart-data")
async def backtest_chart_data(
    result_id: int,
    instrument_id: int,
    session: AsyncSession = Depends(get_db),
):
    result = await session.get(BacktestResult, result_id)
    if not result:
        raise HTTPException(404, "Backtest not found")
    inst = await session.get(Instrument, instrument_id)
    if not inst:
        raise HTTPException(404, "Instrument not found")

    bars_result = await session.execute(
        select(Bar)
        .where(
            Bar.instrument_id == instrument_id,
            Bar.trade_date >= result.start_date,
            Bar.trade_date <= result.end_date,
        )
        .order_by(Bar.trade_date)
    )
    bars = bars_result.scalars().all()
    if not bars:
        fallback = await session.execute(
            select(Bar)
            .where(Bar.instrument_id == instrument_id)
            .order_by(Bar.trade_date.desc())
            .limit(300)
        )
        bars = list(reversed(fallback.scalars().all()))
    markers = [
        m
        for m in (result.markers or [])
        if m.get("symbol") == inst.symbol
    ]

    overlays: dict = {}
    p = result.params or {}
    if p.get("strategy_type") == "ma_cross" or "fast_ma" in p:
        import pandas as pd

        records = [
            {"trade_date": b.trade_date, "close": b.close}
            for b in bars
        ]
        if records:
            fast = int(p.get("fast_ma", 20))
            slow = int(p.get("slow_ma", 50))
            df = pd.DataFrame(records)
            df["fast"] = df["close"].rolling(fast).mean()
            df["slow"] = df["close"].rolling(slow).mean()
            overlays = {
                "fast_ma": [
                    {"time": row["trade_date"].isoformat(), "value": row["fast"]}
                    for _, row in df.iterrows()
                    if pd.notna(row["fast"])
                ],
                "slow_ma": [
                    {"time": row["trade_date"].isoformat(), "value": row["slow"]}
                    for _, row in df.iterrows()
                    if pd.notna(row["slow"])
                ],
            }

    return {
        "instrument": {
            "id": inst.id,
            "symbol": inst.symbol,
            "name": inst.name,
        },
        "bars": [
            {
                "trade_date": b.trade_date.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ],
        "markers": markers,
        "overlays": overlays,
        "trades": [t for t in (result.trades or []) if t.get("symbol") == inst.symbol],
    }


@router.get("/backtests")
async def list_backtests(
    limit: int = 20,
    strategy_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
):
    query = select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit)
    if strategy_id is not None:
        query = query.where(BacktestResult.strategy_id == strategy_id)
    result = await session.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": r.id,
            "strategy_id": r.strategy_id,
            "strategy": r.strategy,
            "strategy_name": (r.params or {}).get("strategy_name", r.strategy),
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "total_return_pct": r.total_return_pct,
            "max_drawdown_pct": r.max_drawdown_pct,
            "trade_count": r.trade_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in items
    ]


@router.get("/risk-free-rate/latest")
async def risk_free_rate_latest(session: AsyncSession = Depends(get_db)):
    latest = await get_latest_risk_free_rate(session)
    if not latest:
        return {"available": False, "message": "尚未拉取无风险利率，调用 POST /api/risk-free-rate/refresh"}
    return {"available": True, **latest}


@router.post("/risk-free-rate/refresh")
async def risk_free_rate_refresh(session: AsyncSession = Depends(get_db)):
    return await refresh_risk_free_rates(session)


@router.get("/risk-free-rate/for-period")
async def risk_free_rate_for_period(
    start: date,
    end: date,
    session: AsyncSession = Depends(get_db),
):
    rate = await get_risk_free_rate_for_period(session, start, end)
    return {"start": start.isoformat(), "end": end.isoformat(), "rate_annual_pct": round(rate * 100, 3)}


@router.post("/run/daily")
async def trigger_daily_run(session: AsyncSession = Depends(get_db)):
    details = await run_daily_scan(session)
    return {"status": "ok", "details": details}


@router.post("/data/sync")
async def trigger_data_sync(
    force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """手动同步 yfinance；force=true 时忽略「数据仍新鲜」跳过逻辑。"""
    stats = await sync_all_instruments(session, force=force, only_stale=not force)
    return {"status": "ok", "synced": stats}


@router.post("/data/seed-demo")
async def trigger_demo_seed(
    force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """仅用于离线演示的合成 K 线，非真实行情。"""
    stats = await seed_demo_bars(session, force=force)
    return {"status": "ok", "inserted": stats, "force": force, "warning": "模拟数据，请勿用于实盘决策"}


@router.get("/data/status")
async def data_source_status(session: AsyncSession = Depends(get_db)):
    return await get_market_data_readiness(session)


@router.get("/data/stooq-test")
async def stooq_api_test():
    """验证 Stooq API Key（读取 backend/.env 中的 STOOQ_API_KEY）。"""
    return await StooqProvider().validate_api_key()


@router.post("/data/bootstrap")
async def bootstrap_market_data(
    force: bool = True,
    session: AsyncSession = Depends(get_db),
):
    """清空旧 K 线并从免费源全量同步真实行情。"""
    from sqlalchemy import delete

    from app.models.entities import Bar

    if force:
        await session.execute(delete(Bar))
        await session.commit()
    stats = await sync_all_instruments(session, force=True, only_stale=False)
    return {"status": "ok", "cleared": force, "synced": stats}


@router.post("/instruments/{instrument_id}/sync")
async def sync_one(instrument_id: int, session: AsyncSession = Depends(get_db)):
    inst = await session.get(Instrument, instrument_id)
    if not inst:
        raise HTTPException(404, "Instrument not found")
    count = await sync_instrument_bars(session, inst)
    return {"symbol": inst.symbol, "inserted": count}


@router.post("/agent/analyze")
async def agent_analyze_instrument(
    strategy_id: int,
    instrument_id: int,
    force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """Agent 看盘：对指定品种实时调 LLM 给出入场/止损/止盈。

    - 默认按 (strategy, instrument, 最新行情日期) 维度缓存，重复请求不烧 token
    - force=true 强制重新分析
    - 仅适用于 strategy_type='agent' 的策略
    """
    from datetime import date
    from sqlalchemy import select, func
    from app.models.entities import Bar, Instrument, StrategyDefinition
    from app.strategies.agent_runner import analyze_single_instrument
    from app.llm.base import LLMError

    strategy = await session.get(StrategyDefinition, strategy_id)
    if not strategy or not strategy.is_active:
        raise HTTPException(404, "策略不存在或已停用")
    if strategy.strategy_type != "agent":
        raise HTTPException(400, "该接口仅支持 agent 类型的策略")
    inst = await session.get(Instrument, instrument_id)
    if not inst:
        raise HTTPException(404, "Instrument not found")

    # 用该标的最新一根 K 线的日期作为决策日期（保证缓存按行情而非"今天"分桶）
    latest = await session.scalar(
        select(func.max(Bar.trade_date)).where(Bar.instrument_id == inst.id)
    )
    if not latest:
        raise HTTPException(400, f"{inst.symbol} 暂无 K 线，请先同步行情")

    try:
        return await analyze_single_instrument(session, strategy, inst, latest, force_refresh=force)
    except LLMError as exc:
        raise HTTPException(400, f"LLM 调用失败：{exc}") from exc


@router.get("/run-logs")
async def run_logs(
    limit: int = 30,
    strategy_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(RunLog).order_by(RunLog.created_at.desc()).limit(max(limit * 5, 100))
    )
    logs = result.scalars().all()
    out: list[dict] = []
    for log in logs:
        if strategy_id is not None:
            # 兼容历史日志：strategy_id 可能在 details.strategy.id 或 details.strategy_id
            details = log.details or {}
            sid = (details.get("strategy") or {}).get("id") or details.get("strategy_id")
            if sid != strategy_id:
                continue
        out.append({
            "id": log.id,
            "run_date": log.run_date.isoformat(),
            "run_type": log.run_type,
            "message": log.message,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
        if len(out) >= limit:
            break
    return out


@router.get("/brokers/health")
async def brokers_health():
    ib = IBAdapter()
    oanda = OandaAdapter()
    settings = get_settings()
    return {
        "active_mode": settings.broker_mode,
        "brokers": {
            "paper": {"status": "ok", "message": "模拟盘可用"},
            "ib": await ib.health_check(),
            "oanda": await oanda.health_check(),
        },
    }


@router.get("/settings")
async def get_app_settings():
    s = get_settings()
    return {
        "broker_mode": s.broker_mode,
        "max_trades_per_day": s.max_trades_per_day,
        "max_trades_per_symbol_per_day": s.max_trades_per_symbol_per_day,
        "initial_capital": s.initial_capital,
        "fast_ma": s.fast_ma,
        "slow_ma": s.slow_ma,
        "daily_run_cron": s.daily_run_cron,
    }
