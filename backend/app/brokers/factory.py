from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.ib import IBAdapter
from app.brokers.oanda import OandaAdapter
from app.brokers.paper import PaperBroker
from app.config import get_settings


def get_broker(session: AsyncSession):
    mode = get_settings().broker_mode.lower()
    if mode == "live_ib":
        return IBAdapter()
    if mode == "live_oanda":
        return OandaAdapter()
    return PaperBroker(session)
