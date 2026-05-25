from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import Order, OrderStatus
from app.strategies.base import StrategySignal


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


async def count_trades_today(session: AsyncSession, trade_date: date) -> int:
    result = await session.execute(
        select(func.count(Order.id)).where(
            Order.order_date == trade_date,
            Order.status == OrderStatus.filled,
        )
    )
    return int(result.scalar() or 0)


async def count_symbol_trades_today(
    session: AsyncSession, instrument_id: int, trade_date: date
) -> int:
    result = await session.execute(
        select(func.count(Order.id)).where(
            Order.instrument_id == instrument_id,
            Order.order_date == trade_date,
            Order.status == OrderStatus.filled,
        )
    )
    return int(result.scalar() or 0)


async def check_signal_risk(
    session: AsyncSession,
    signal: StrategySignal,
    trade_date: date,
) -> RiskDecision:
    settings = get_settings()
    daily_count = await count_trades_today(session, trade_date)
    if daily_count >= settings.max_trades_per_day:
        return RiskDecision(False, f"已达每日最大开仓数 {settings.max_trades_per_day}")

    symbol_count = await count_symbol_trades_today(session, signal.instrument_id, trade_date)
    if symbol_count >= settings.max_trades_per_symbol_per_day:
        return RiskDecision(False, "该标的今日已交易")

    return RiskDecision(True, "通过风控")


def select_top_signals(
    signals: list[StrategySignal],
    max_count: int,
    already_taken: int,
) -> list[StrategySignal]:
    remaining = max(0, max_count - already_taken)
    if remaining == 0:
        return []
    ranked = sorted(signals, key=lambda s: s.strength, reverse=True)
    return ranked[:remaining]
