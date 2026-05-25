import asyncio
from datetime import date

import httpx

from app.data.base import DataProvider, OHLCVBar

FRANKFURTER_URL = "https://api.frankfurter.app"


class FrankfurterProvider(DataProvider):
    """ECB 参考汇率日频（免费、无需 Key）。仅收盘价，OHLC 均取同一汇率。"""

    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        raise RuntimeError("请通过 CompositeDataProvider 使用 FrankfurterFxRef")

    async def fetch_fx(
        self, base: str, quote: str, start: date, end: date
    ) -> list[OHLCVBar]:
        return await asyncio.to_thread(self._fetch_sync, base, quote, start, end)

    def _fetch_sync(
        self, base: str, quote: str, start: date, end: date
    ) -> list[OHLCVBar]:
        url = f"{FRANKFURTER_URL}/{start.isoformat()}..{end.isoformat()}"
        params = {"from": base.upper(), "to": quote.upper()}
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        rates = payload.get("rates") or {}
        bars: list[OHLCVBar] = []
        for day_str, quotes in sorted(rates.items()):
            if quote.upper() not in quotes:
                continue
            px = float(quotes[quote.upper()])
            trade_date = date.fromisoformat(day_str)
            bars.append(
                OHLCVBar(
                    trade_date=trade_date,
                    open=px,
                    high=px,
                    low=px,
                    close=px,
                    volume=0.0,
                )
            )
        deduped: dict[date, OHLCVBar] = {}
        for bar in bars:
            deduped[bar.trade_date] = bar
        return [deduped[d] for d in sorted(deduped)]
