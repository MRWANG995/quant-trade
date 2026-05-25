from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.engine.risk import count_trades_today
from app.models.entities import Bar, Instrument, Order, Position


async def get_portfolio_summary(session: AsyncSession) -> dict:
    settings = get_settings()
    positions_result = await session.execute(
        select(Position)
        .options(selectinload(Position.instrument))
        .where(Position.quantity != 0)
    )
    positions = positions_result.scalars().all()

    exposure_by_class: dict[str, float] = {}
    position_values = []
    unrealized_pnl = 0.0

    for pos in positions:
        inst = pos.instrument
        bar_result = await session.execute(
            select(Bar)
            .where(Bar.instrument_id == inst.id)
            .order_by(Bar.trade_date.desc())
            .limit(1)
        )
        bar = bar_result.scalar_one_or_none()
        mark = bar.close if bar else pos.avg_price
        notional = abs(pos.quantity) * mark
        direction = 1 if pos.quantity > 0 else -1
        pnl = (mark - pos.avg_price) * abs(pos.quantity) * direction
        unrealized_pnl += pnl
        ac = inst.asset_class.value
        exposure_by_class[ac] = exposure_by_class.get(ac, 0) + notional
        position_values.append(
            {
                "symbol": inst.symbol,
                "name": inst.name,
                "asset_class": ac,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "mark_price": mark,
                "unrealized_pnl": round(pnl, 2),
            }
        )

    equity = settings.initial_capital + unrealized_pnl
    today = date.today()
    trades_today = await count_trades_today(session, today)

    return {
        "equity": round(equity, 2),
        "initial_capital": settings.initial_capital,
        "unrealized_pnl": round(unrealized_pnl, 2),
        "trades_today": trades_today,
        "max_trades_per_day": settings.max_trades_per_day,
        "trades_remaining": max(0, settings.max_trades_per_day - trades_today),
        "exposure_by_class": exposure_by_class,
        "positions": position_values,
    }


async def get_orders(
    session: AsyncSession,
    limit: int = 50,
    strategy_id: Optional[int] = None,
) -> list[dict]:
    query = (
        select(Order)
        .options(selectinload(Order.instrument))
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    if strategy_id is not None:
        query = query.where(Order.strategy_id == strategy_id)
    result = await session.execute(query)
    orders = result.scalars().all()
    return [
        {
            "id": o.id,
            "symbol": o.instrument.symbol,
            "strategy_id": o.strategy_id,
            "order_date": o.order_date.isoformat(),
            "side": o.side.value,
            "quantity": o.quantity,
            "status": o.status.value,
            "fill_price": o.fill_price,
            "fill_date": o.fill_date.isoformat() if o.fill_date else None,
            "broker": o.broker,
        }
        for o in orders
    ]
