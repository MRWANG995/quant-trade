from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import BrokerAdapter, OrderRequest
from app.config import get_settings
from app.models.entities import Bar, Order, OrderSide, OrderStatus, Position


class PaperBroker:
    name = "paper"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def get_positions(self) -> list[Position]:
        result = await self.session.execute(select(Position).where(Position.quantity != 0))
        return list(result.scalars().all())

    async def place_order(self, request: OrderRequest) -> Order:
        order = Order(
            instrument_id=request.instrument_id,
            strategy_id=request.strategy_id,
            order_date=request.order_date,
            side=request.side,
            quantity=request.quantity,
            status=OrderStatus.pending,
            broker=self.name,
        )
        self.session.add(order)
        await self.session.flush()

        fill_price = await self._next_open_price(request.instrument_id, request.order_date)
        if fill_price is None:
            order.status = OrderStatus.rejected
            await self.session.commit()
            return order

        slippage = self.settings.paper_slippage_bps / 10_000
        if request.side == OrderSide.buy:
            fill_price *= 1 + slippage
        else:
            fill_price *= 1 - slippage

        order.status = OrderStatus.filled
        order.fill_price = fill_price
        order.fill_date = request.order_date + timedelta(days=1)

        await self._update_position(request, fill_price)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def cancel_order(self, order_id: int) -> None:
        result = await self.session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order and order.status == OrderStatus.pending:
            order.status = OrderStatus.cancelled
            await self.session.commit()

    async def health_check(self) -> dict[str, str]:
        return {"broker": self.name, "status": "ok", "mode": "paper"}

    async def _next_open_price(self, instrument_id: int, order_date: date) -> Optional[float]:
        target = order_date + timedelta(days=1)
        for offset in range(0, 7):
            check_date = target + timedelta(days=offset)
            result = await self.session.execute(
                select(Bar).where(Bar.instrument_id == instrument_id, Bar.trade_date == check_date)
            )
            bar = result.scalar_one_or_none()
            if bar:
                return bar.open
        # 演示/日频：若无下一交易日 K 线，按信号当日收盘价模拟成交
        same_day = await self.session.execute(
            select(Bar).where(Bar.instrument_id == instrument_id, Bar.trade_date == order_date)
        )
        bar = same_day.scalar_one_or_none()
        return bar.close if bar else None

    async def _update_position(self, request: OrderRequest, fill_price: float) -> None:
        result = await self.session.execute(
            select(Position).where(Position.instrument_id == request.instrument_id)
        )
        pos = result.scalar_one_or_none()
        if pos is None:
            pos = Position(instrument_id=request.instrument_id, quantity=0.0, avg_price=0.0)
            self.session.add(pos)

        signed_qty = request.quantity if request.side == OrderSide.buy else -request.quantity
        new_qty = pos.quantity + signed_qty

        if pos.quantity == 0 or (pos.quantity > 0 and signed_qty > 0) or (pos.quantity < 0 and signed_qty < 0):
            total_cost = abs(pos.quantity) * pos.avg_price + abs(signed_qty) * fill_price
            pos.avg_price = total_cost / abs(new_qty) if new_qty != 0 else 0.0
        elif new_qty == 0:
            pos.avg_price = 0.0
        pos.quantity = new_qty
