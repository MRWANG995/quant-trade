from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.data.risk_free_rate import get_risk_free_rate_for_period
from app.engine.metrics import compute_metrics
from app.models.entities import BacktestResult, Bar, Instrument, StrategyDefinition
from app.strategies.bars import bars_to_records
from app.strategies.registry import scan_historical_signals
from app.strategies.service import get_strategy


@dataclass
class BacktestParams:
    start_date: date
    end_date: date
    initial_capital: float
    strategy_id: Optional[int] = None
    risk_per_trade: float = 0.02
    param_overrides: Optional[dict] = None


def _trade_markers(trades: list[dict]) -> list[dict]:
    markers: list[dict] = []
    for t in trades:
        sym = t["symbol"]
        side = t.get("side", "long")
        if t.get("entry_date"):
            markers.append(
                {
                    "symbol": sym,
                    "time": t["entry_date"],
                    "kind": "entry",
                    "side": side,
                    "price": t["entry_price"],
                    "text": "入",
                }
            )
        if t.get("exit_date"):
            markers.append(
                {
                    "symbol": sym,
                    "time": t["exit_date"],
                    "kind": "exit",
                    "side": side,
                    "price": t["exit_price"],
                    "text": "出",
                }
            )
    return markers


async def run_backtest(session: AsyncSession, params: BacktestParams) -> BacktestResult:
    settings = get_settings()
    strategy_def = await get_strategy(session, params.strategy_id)
    if strategy_def.strategy_type == "agent":
        raise ValueError(
            "Agent 策略不支持历史回测：会消耗大量 LLM 调用配额；"
            "请运行「每日扫描」逐日累积决策，未来计划支持稀疏采样回测"
        )
    run_params = {**strategy_def.params, **(params.param_overrides or {})}
    # 组合策略：在调用 scan 前把子策略 resolve 进 run_params._resolved_children
    if strategy_def.strategy_type == "composite":
        from app.strategies.service import resolve_composite_params
        run_params = await resolve_composite_params(session, run_params)

    inst_result = await session.execute(select(Instrument).where(Instrument.is_active.is_(True)))
    instruments = inst_result.scalars().all()

    equity = params.initial_capital
    cash = equity
    positions: dict[str, dict] = {}
    equity_curve: list[dict] = []
    trades: list[dict] = []
    max_equity = equity
    max_drawdown = 0.0
    daily_trade_count: dict[date, int] = {}

    all_dates: set[date] = set()
    price_data: dict[str, pd.DataFrame] = {}
    signals_by_date: dict[date, list[tuple]] = {}

    for inst in instruments:
        bars_result = await session.execute(
            select(Bar)
            .where(
                Bar.instrument_id == inst.id,
                Bar.trade_date >= params.start_date,
                Bar.trade_date <= params.end_date,
            )
            .order_by(Bar.trade_date)
        )
        bars = bars_result.scalars().all()
        if not bars:
            continue
        records = bars_to_records(bars)
        df = pd.DataFrame(records)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        price_data[inst.symbol] = df
        all_dates.update(df["trade_date"].tolist())

        hist_signals = scan_historical_signals(
            strategy_def.strategy_type,
            inst.id,
            inst.symbol,
            records,
            run_params,
        )
        for sig in hist_signals:
            if params.start_date <= sig.signal_date <= params.end_date:
                signals_by_date.setdefault(sig.signal_date, []).append((sig, inst))

    for current_date in sorted(all_dates):
        day_signals = signals_by_date.get(current_date, [])
        day_signals.sort(key=lambda x: x[0].strength, reverse=True)
        trades_today = daily_trade_count.get(current_date, 0)

        for sig, inst in day_signals:
            if trades_today >= settings.max_trades_per_day:
                break
            row = price_data[inst.symbol][price_data[inst.symbol]["trade_date"] == current_date]
            if row.empty:
                continue
            price = float(row.iloc[-1]["close"])
            pos = positions.get(inst.symbol)
            target_side = sig.side.value

            if pos and pos["side"] == target_side:
                continue

            risk_amount = equity * params.risk_per_trade
            qty = max(risk_amount / price, 0.01)

            if pos:
                direction = 1 if pos["side"] == "long" else -1
                pnl = (price - pos["entry"]) * pos["qty"] * direction
                cash += pnl
                trades.append(
                    {
                        "symbol": inst.symbol,
                        "side": pos["side"],
                        "entry_date": pos["entry_date"],
                        "entry_price": pos["entry_price"],
                        "exit_date": current_date.isoformat(),
                        "exit_price": price,
                        "pnl": round(pnl, 2),
                        "reason": pos.get("reason", ""),
                    }
                )
                del positions[inst.symbol]

            if target_side in ("long", "short"):
                positions[inst.symbol] = {
                    "side": target_side,
                    "entry": price,
                    "entry_price": price,
                    "entry_date": current_date.isoformat(),
                    "qty": qty,
                    "reason": sig.reason,
                }
                trades_today += 1

        daily_trade_count[current_date] = trades_today

        mtm = cash
        for symbol, pos in positions.items():
            if symbol not in price_data:
                continue
            row = price_data[symbol][price_data[symbol]["trade_date"] == current_date]
            if row.empty:
                continue
            price = float(row.iloc[-1]["close"])
            direction = 1 if pos["side"] == "long" else -1
            mtm += (price - pos["entry"]) * pos["qty"] * direction

        equity = mtm
        max_equity = max(max_equity, equity)
        dd = (max_equity - equity) / max_equity if max_equity > 0 else 0
        max_drawdown = max(max_drawdown, dd)
        equity_curve.append({"date": current_date.isoformat(), "equity": round(equity, 2)})

    last_date = max(all_dates) if all_dates else params.end_date
    for symbol, pos in list(positions.items()):
        if symbol not in price_data:
            continue
        df = price_data[symbol]
        rows = df[df["trade_date"] <= last_date]
        if rows.empty:
            continue
        price = float(rows.iloc[-1]["close"])
        direction = 1 if pos["side"] == "long" else -1
        pnl = (price - pos["entry"]) * pos["qty"] * direction
        cash += pnl
        trades.append(
            {
                "symbol": symbol,
                "side": pos["side"],
                "entry_date": pos["entry_date"],
                "entry_price": pos["entry_price"],
                "exit_date": last_date.isoformat(),
                "exit_price": price,
                "pnl": round(pnl, 2),
                "reason": pos.get("reason", "") + "（期末平仓）",
            }
        )

    total_return = (equity - params.initial_capital) / params.initial_capital * 100
    markers = _trade_markers(trades)

    rf_rate = await get_risk_free_rate_for_period(
        session, params.start_date, params.end_date
    )
    metrics = compute_metrics(
        equity_curve=equity_curve,
        trades=trades,
        initial_capital=params.initial_capital,
        final_equity=equity,
        risk_free_rate_annual=rf_rate,
    )

    result = BacktestResult(
        strategy_id=strategy_def.id,
        strategy=strategy_def.slug,
        start_date=params.start_date,
        end_date=params.end_date,
        initial_capital=params.initial_capital,
        final_equity=round(equity, 2),
        total_return_pct=round(total_return, 2),
        max_drawdown_pct=round(max_drawdown * 100, 2),
        trade_count=len(trades),
        params={
            "strategy_type": strategy_def.strategy_type,
            "strategy_name": strategy_def.name,
            **run_params,
            "risk_per_trade": params.risk_per_trade,
        },
        equity_curve=equity_curve,
        trades=trades,
        markers=markers,
        metrics=metrics,
    )
    session.add(result)
    await session.commit()
    await session.refresh(result)
    return result
