import asyncio
from datetime import date, timedelta
from io import StringIO
from typing import Optional

import httpx
import pandas as pd

from app.config import get_settings
from app.data.base import DataProvider, OHLCVBar

STOOQ_CSV_URL = "https://stooq.com/q/d/l/"


class StooqProvider(DataProvider):
    """Stooq 日 K（需在 https://stooq.com 免费获取 apikey）。"""

    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        settings = get_settings()
        if not settings.stooq_api_key:
            raise RuntimeError(
                "未配置 STOOQ_API_KEY。请打开 https://stooq.com/q/d/?s=eurusd&get_apikey "
                "完成验证码后，将链接中的 apikey 写入 .env"
            )
        stooq_symbol = yfinance_symbol.lower()
        return await asyncio.to_thread(
            self._fetch_sync, stooq_symbol, start, end, settings.stooq_api_key
        )

    def _fetch_sync(
        self, stooq_symbol: str, start: date, end: date, api_key: str
    ) -> list[OHLCVBar]:
        params = {
            "s": stooq_symbol,
            "d1": start.strftime("%Y%m%d"),
            "d2": end.strftime("%Y%m%d"),
            "i": "d",
            "apikey": api_key,
        }
        headers = {"User-Agent": "Mozilla/5.0 (compatible; QuantTrade/1.0)"}
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(STOOQ_CSV_URL, params=params, headers=headers)
            response.raise_for_status()
            text = response.text.strip()
            if "apikey" in text.lower() and "captcha" in text.lower():
                raise RuntimeError("Stooq API Key 无效或已过期，请重新获取")
            if not text or text.startswith("<"):
                raise RuntimeError(f"Stooq 未返回数据: {stooq_symbol}")

        df = pd.read_csv(StringIO(text))
        return _dataframe_to_bars(df)

    async def validate_api_key(self, api_key: Optional[str] = None) -> dict:
        """拉取少量样本数据以验证 Stooq Key 是否有效。"""
        settings = get_settings()
        key = (api_key or settings.stooq_api_key or "").strip()
        if not key:
            return {"ok": False, "message": "未配置 STOOQ_API_KEY"}
        end = date.today()
        start = end - timedelta(days=30)
        try:
            bars = await asyncio.to_thread(self._fetch_sync, "eurusd", start, end, key)
            if not bars:
                return {"ok": False, "message": "Key 可用但返回空数据"}
            return {
                "ok": True,
                "message": "Stooq API Key 有效",
                "sample_symbol": "eurusd",
                "bar_count": len(bars),
                "last_date": bars[-1].trade_date.isoformat(),
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc)}


def _dataframe_to_bars(df: pd.DataFrame) -> list[OHLCVBar]:
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("data")
    if not date_col:
        raise RuntimeError(f"无法识别 Stooq CSV 列: {list(df.columns)}")

    def col(*names: str) -> str:
        for n in names:
            key = n.lower()
            if key in cols:
                return cols[key]
        raise KeyError(f"缺少列 {names}，实际: {list(df.columns)}")

    bars: list[OHLCVBar] = []
    vol_col = cols.get("volume")
    for _, row in df.iterrows():
        trade_date = pd.to_datetime(row[date_col]).date()
        vol = 0.0
        if vol_col is not None and pd.notna(row.get(vol_col)):
            vol = float(row[vol_col])
        bars.append(
            OHLCVBar(
                trade_date=trade_date,
                open=float(row[col("open")]),
                high=float(row[col("high")]),
                low=float(row[col("low")]),
                close=float(row[col("close")]),
                volume=vol,
            )
        )
    return sorted(bars, key=lambda b: b.trade_date)
