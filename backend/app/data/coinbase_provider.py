"""Coinbase Exchange 公共 K 线（免 key，全球可用）。

主要用于 BTC 等加密货币——Binance 在美国地区被封（HTTP 451），
Coinbase 是部署到 Render Oregon 仍能稳定访问的备选源。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timezone, timedelta

import httpx

from app.data.base import DataProvider, OHLCVBar

logger = logging.getLogger(__name__)

# 每个 candle 的秒数；Coinbase 仅支持这些值
COINBASE_GRANULARITY_MAP = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}

MAX_CANDLES_PER_REQ = 300  # Coinbase 单次最多 300 根


class CoinbaseProvider(DataProvider):
    """Coinbase Exchange public candles API。product_id 例：BTC-USD。"""

    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        # yfinance_symbol 借用字段名传 Coinbase product_id（如 BTC-USD）
        return await self.fetch_candles(yfinance_symbol, "1d", start, end)

    async def fetch_candles(
        self,
        product_id: str,
        interval: str,
        start: date,
        end: date,
    ) -> list[OHLCVBar]:
        seconds = COINBASE_GRANULARITY_MAP.get(interval)
        if not seconds:
            raise ValueError(f"Coinbase 不支持的时间框架: {interval}")

        window_seconds = MAX_CANDLES_PER_REQ * seconds
        cursor = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        bars: dict[date, OHLCVBar] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            while cursor < end_dt:
                window_end = min(cursor + timedelta(seconds=window_seconds), end_dt)
                params = {
                    "granularity": seconds,
                    "start": cursor.isoformat(),
                    "end": window_end.isoformat(),
                }
                resp = await client.get(
                    f"https://api.exchange.coinbase.com/products/{product_id}/candles",
                    params=params,
                )
                resp.raise_for_status()
                rows = resp.json()
                # rows 格式：[[time, low, high, open, close, volume], ...]，倒序
                if not isinstance(rows, list) or not rows:
                    cursor = window_end
                    continue
                for row in rows:
                    ts_sec, low, high, open_, close, volume = row
                    bar_date = datetime.fromtimestamp(ts_sec, tz=timezone.utc).date()
                    bars[bar_date] = OHLCVBar(
                        trade_date=bar_date,
                        open=float(open_),
                        high=float(high),
                        low=float(low),
                        close=float(close),
                        volume=float(volume),
                    )
                cursor = window_end
                await asyncio.sleep(0.15)  # 友好限速

        return sorted(bars.values(), key=lambda b: b.trade_date)
