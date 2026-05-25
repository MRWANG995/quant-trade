from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class OHLCVBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataProvider(ABC):
    @abstractmethod
    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        pass
