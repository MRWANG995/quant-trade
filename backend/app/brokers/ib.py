from app.brokers.base import BrokerAdapter, OrderRequest
from app.config import get_settings
from app.models.entities import Order, Position


class IBAdapter:
    name = "ib"

    def __init__(self):
        self.settings = get_settings()

    async def get_positions(self) -> list[Position]:
        return []

    async def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError(
            "IB 实盘适配器尚未完成。请在 .env 配置 IB 凭证后等待后续版本，"
            "当前请使用 BROKER_MODE=paper。"
        )

    async def cancel_order(self, order_id: int) -> None:
        raise NotImplementedError("IB adapter not implemented")

    async def health_check(self) -> dict[str, str]:
        configured = bool(self.settings.ib_host and self.settings.ib_port)
        return {
            "broker": self.name,
            "status": "stub",
            "configured": str(configured),
            "message": "占位适配器：仅健康检查，不支持真实下单",
        }
