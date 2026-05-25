from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import OrderRequest
from app.brokers.factory import get_broker
from app.config import get_settings
from app.data.sync_service import sync_for_daily_run
from app.engine.risk import check_signal_risk, count_trades_today, select_top_signals
from app.models.entities import Bar, Instrument, OrderSide, RunLog, Signal, SignalSide
from app.strategies.bars import bars_to_records
from app.strategies.registry import latest_signals, min_bars_required
from app.strategies.service import get_strategy


async def _latest_market_date(session: AsyncSession) -> Optional[date]:
    result = await session.execute(select(func.max(Bar.trade_date)))
    return result.scalar_one_or_none()


async def _signal_exists(
    session: AsyncSession,
    instrument_id: int,
    signal_date: date,
    side: SignalSide,
) -> bool:
    result = await session.execute(
        select(Signal.id).where(
            Signal.instrument_id == instrument_id,
            Signal.signal_date == signal_date,
            Signal.side == side,
        )
    )
    return result.scalar_one_or_none() is not None


async def run_daily_scan(
    session: AsyncSession,
    run_date: Optional[date] = None,
    strategy_id: Optional[int] = None,
) -> dict:
    run_date = run_date or date.today()
    settings = get_settings()
    details: dict = {"signals": [], "orders": [], "rejected": [], "skipped": []}

    try:
        strategy_def = await get_strategy(session, strategy_id)
    except ValueError as exc:
        details["message"] = str(exc)
        return details

    details["strategy"] = {
        "id": strategy_def.id,
        "slug": strategy_def.slug,
        "name": strategy_def.name,
        "type": strategy_def.strategy_type,
        "params": strategy_def.params,
    }

    details["sync"] = await sync_for_daily_run(session)

    # 组合策略：把子策略 resolve 进 params._resolved_children
    if strategy_def.strategy_type == "composite":
        from app.strategies.service import resolve_composite_params
        run_params = await resolve_composite_params(session, dict(strategy_def.params))
    else:
        run_params = dict(strategy_def.params)

    market_date = await _latest_market_date(session)
    if market_date is None:
        details["message"] = "无 K 线数据，请先同步行情"
        return details

    details["market_date"] = market_date.isoformat()
    scan_date = min(run_date, market_date)
    min_bars = min_bars_required(strategy_def.strategy_type, run_params)

    inst_result = await session.execute(select(Instrument).where(Instrument.is_active.is_(True)))
    instruments = inst_result.scalars().all()

    # Agent 策略：先批量取 LLM 决策（带缓存），再走通用 scan
    if strategy_def.strategy_type == "agent":
        from app.strategies.agent_runner import run_agent_decisions
        decisions = await run_agent_decisions(session, strategy_def, instruments, scan_date)
        run_params["_resolved_decisions"] = decisions
        details["agent_decisions_count"] = len(decisions)

    all_signals = []
    for inst in instruments:
        bars_result = await session.execute(
            select(Bar)
            .where(Bar.instrument_id == inst.id)
            .order_by(Bar.trade_date.desc())
            .limit(min_bars + 60)
        )
        bars = list(reversed(bars_result.scalars().all()))
        if len(bars) < min_bars:
            details["skipped"].append(
                {"symbol": inst.symbol, "reason": f"K 线不足（需至少 {min_bars} 根）"}
            )
            continue

        signals = latest_signals(
            strategy_def.strategy_type,
            inst.id,
            inst.symbol,
            bars_to_records(bars),
            run_params,
        )
        for sig in signals:
            if sig.signal_date != scan_date:
                continue
            if await _signal_exists(session, sig.instrument_id, sig.signal_date, sig.side):
                details["skipped"].append(
                    {"symbol": sig.symbol, "reason": "今日同向信号已存在"}
                )
                continue
            all_signals.append(sig)
            db_sig = Signal(
                instrument_id=sig.instrument_id,
                strategy_id=strategy_def.id,
                signal_date=sig.signal_date,
                side=sig.side,
                strength=sig.strength,
                reason=sig.reason,
            )
            session.add(db_sig)
            details["signals"].append(
                {
                    "symbol": sig.symbol,
                    "side": sig.side.value,
                    "strength": round(sig.strength, 6),
                    "reason": sig.reason,
                    "date": sig.signal_date.isoformat(),
                }
            )

    await session.commit()

    if not all_signals:
        details["hint"] = (
            f"最新交易日 {scan_date} 在策略「{strategy_def.name}」下无信号。"
            "可调整策略参数或更换策略。"
        )

    existing_trades = await count_trades_today(session, run_date)
    selected = select_top_signals(
        all_signals,
        settings.max_trades_per_day,
        existing_trades,
    )

    broker = get_broker(session)
    for sig in selected:
        risk = await check_signal_risk(session, sig, run_date)
        if not risk.allowed:
            details["rejected"].append({"symbol": sig.symbol, "reason": risk.reason})
            continue

        side = OrderSide.buy if sig.side.value == "long" else OrderSide.sell
        risk_amount = settings.initial_capital * 0.02
        last_bar = await session.execute(
            select(Bar)
            .where(Bar.instrument_id == sig.instrument_id)
            .order_by(Bar.trade_date.desc())
            .limit(1)
        )
        bar = last_bar.scalar_one_or_none()
        if not bar:
            continue
        qty = max(risk_amount / bar.close, 0.01)

        try:
            order = await broker.place_order(
                OrderRequest(
                    instrument_id=sig.instrument_id,
                    symbol=sig.symbol,
                    side=side,
                    quantity=round(qty, 4),
                    order_date=scan_date,
                    strategy_id=strategy_def.id,
                )
            )
            details["orders"].append(
                {
                    "symbol": sig.symbol,
                    "side": side.value,
                    "status": order.status.value,
                    "fill_price": order.fill_price,
                }
            )
        except NotImplementedError as e:
            details["rejected"].append({"symbol": sig.symbol, "reason": str(e)})

    log = RunLog(
        run_date=run_date,
        run_type="daily_scan",
        message=f"策略 {strategy_def.name}：{len(details['signals'])} 信号，{len(details['orders'])} 笔订单",
        details=details,
    )
    session.add(log)
    await session.commit()

    return details
