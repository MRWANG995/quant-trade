from app.brokers.base import OrderRequest
from app.config import get_settings
from app.models.entities import Order, Position


class OandaAdapter:
    name = "oanda"

    def __init__(self):
        self.settings = get_settings()

    async def get_positions(self) -> list[Position]:
        return []

    async def place_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError(
            "OANDA 实盘适配器尚未完成。请在 .env 配置 OANDA_API_KEY 与 OANDA_ACCOUNT_ID，"
            "当前请使用 BROKER_MODE=paper。"
        )

    async def cancel_order(self, order_id: int) -> None:
        raise NotImplementedError("OANDA adapter not implemented")

    async def health_check(self) -> dict[str, str]:
        configured = bool(self.settings.oanda_api_key and self.settings.oanda_account_id)
        return {
            "broker": self.name,
            "status": "stub",
            "configured": str(configured),
            "env": self.settings.oanda_env,
            "message": "占位适配器：仅健康检查，不支持真实下单",
        }
