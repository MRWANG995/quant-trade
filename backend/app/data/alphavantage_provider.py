import asyncio
from datetime import date
from typing import Union

import httpx

from app.config import get_settings
from app.data.base import DataProvider, OHLCVBar
from app.data.symbols import AlphaVantageEquityRef, AlphaVantageFxRef

AV_BASE = "https://www.alphavantage.co/query"


class AlphaVantageProvider(DataProvider):
    """Alpha Vantage 免费档（https://www.alphavantage.co/support/#api-key）。"""

    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        raise NotImplementedError("请通过 CompositeDataProvider 调用 fetch_for_config")

    async def fetch_fx(
        self, ref: AlphaVantageFxRef, start: date, end: date
    ) -> list[OHLCVBar]:
        settings = self._require_key()
        params = {
            "function": "FX_DAILY",
            "from_symbol": ref.from_symbol,
            "to_symbol": ref.to_symbol,
            "apikey": settings.alphavantage_api_key,
            "outputsize": "full",
        }
        data = await asyncio.to_thread(self._get_json, params)
        series = data.get("Time Series FX (Daily)", {})
        return self._parse_series(series, start, end)

    async def fetch_equity(
        self, ref: AlphaVantageEquityRef, start: date, end: date
    ) -> list[OHLCVBar]:
        settings = self._require_key()
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ref.symbol,
            "apikey": settings.alphavantage_api_key,
            "outputsize": "full",
        }
        data = await asyncio.to_thread(self._get_json, params)
        series = data.get("Time Series (Daily)", {})
        return self._parse_series(series, start, end)

    def _require_key(self):
        settings = get_settings()
        if not settings.alphavantage_api_key:
            raise RuntimeError(
                "未配置 ALPHAVANTAGE_API_KEY。请在 https://www.alphavantage.co/support/#api-key "
                "免费申请（约 20 秒），写入 .env"
            )
        return settings

    def _get_json(self, params: dict) -> dict:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(AV_BASE, params=params)
            response.raise_for_status()
            data = response.json()
        if "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information")
            raise RuntimeError(f"Alpha Vantage 限流或 Key 无效: {msg}")
        if "Error Message" in data:
            raise RuntimeError(data["Error Message"])
        return data

    def _parse_series(self, series: dict, start: date, end: date) -> list[OHLCVBar]:
        bars: list[OHLCVBar] = []
        for day_str, ohlc in series.items():
            trade_date = date.fromisoformat(day_str)
            if trade_date < start or trade_date > end:
                continue
            bars.append(
                OHLCVBar(
                    trade_date=trade_date,
                    open=float(ohlc["1. open"]),
                    high=float(ohlc["2. high"]),
                    low=float(ohlc["3. low"]),
                    close=float(ohlc["4. close"]),
                    volume=float(ohlc.get("6. volume", 0) or 0),
                )
            )
        return sorted(bars, key=lambda b: b.trade_date)
