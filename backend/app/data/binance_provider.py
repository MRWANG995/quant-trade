"""Binance 公共 K 线 provider（无需 API Key）。

主要用于 BTC 等加密货币。Binance API 限制 1000 根 K 线/次，需要分页。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timezone

import httpx

from app.data.base import DataProvider, OHLCVBar

logger = logging.getLogger(__name__)

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


class BinanceProvider(DataProvider):
    """Binance 公共 K 线。symbol 例：BTCUSDT、ETHUSDT。"""

    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        # 这里复用 DataProvider 接口；yfinance_symbol 实际是 Binance pair（BTCUSDT 等）
        return await self.fetch_klines(yfinance_symbol, "1d", start, end)

    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start: date,
        end: date,
    ) -> list[OHLCVBar]:
        binance_interval = BINANCE_INTERVAL_MAP.get(interval)
        if not binance_interval:
            raise ValueError(f"不支持的 Binance 时间框架: {interval}")
        start_ms = int(
            datetime.combine(start, time.min, tzinfo=timezone.utc).timestamp() * 1000
        )
        end_ms = int(
            datetime.combine(end, time.max, tzinfo=timezone.utc).timestamp() * 1000
        )
        bars: list[OHLCVBar] = []
        cursor = start_ms
        async with httpx.AsyncClient(timeout=30.0) as client:
            while cursor < end_ms:
                params = {
                    "symbol": symbol,
                    "interval": binance_interval,
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": 1000,
                }
                resp = await client.get(BINANCE_KLINES, params=params)
                resp.raise_for_status()
                rows = resp.json()
                if not rows:
                    break
                for row in rows:
                    open_time_ms = row[0]
                    trade_date = datetime.fromtimestamp(
                        open_time_ms / 1000, tz=timezone.utc
                    ).date()
                    bars.append(
                        OHLCVBar(
                            trade_date=trade_date,
                            open=float(row[1]),
                            high=float(row[2]),
                            low=float(row[3]),
                            close=float(row[4]),
                            volume=float(row[5]),
                        )
                    )
                last_open = rows[-1][0]
                if last_open <= cursor:
                    break
                cursor = last_open + 1
                # 友好限速；Binance 公共端点限流 1200 weight/min，每次 klines 是 1-2 weight
                await asyncio.sleep(0.1)
        return bars
