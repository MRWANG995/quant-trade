from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol

from app.models.entities import Order, OrderSide, Position


@dataclass
class OrderRequest:
    instrument_id: int
    symbol: str
    side: OrderSide
    quantity: float
    order_date: date
    strategy_id: Optional[int] = None


class BrokerAdapter(Protocol):
    name: str

    async def get_positions(self) -> list[Position]: ...

    async def place_order(self, request: OrderRequest) -> Order: ...

    async def cancel_order(self, order_id: int) -> None: ...

    async def health_check(self) -> dict[str, str]: ...
