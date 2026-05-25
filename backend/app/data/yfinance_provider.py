import asyncio
import logging
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from app.config import get_settings
from app.data.base import DataProvider, OHLCVBar

logger = logging.getLogger(__name__)


def _build_yfinance_session():
    try:
        from curl_cffi import requests as curl_requests

        return curl_requests.Session(impersonate="chrome")
    except ImportError:
        return None


def _df_to_bars(df: pd.DataFrame) -> list[OHLCVBar]:
    if df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        if df.columns.nlevels > 1:
            df.columns = df.columns.droplevel(1)
    bars: list[OHLCVBar] = []
    for idx, row in df.iterrows():
        trade_date = idx.date() if hasattr(idx, "date") else idx
        bars.append(
            OHLCVBar(
                trade_date=trade_date,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0) or 0),
            )
        )
    return bars


def _multi_ticker_df_to_bars(df: pd.DataFrame, ticker: str) -> list[OHLCVBar]:
    if df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        try:
            sub = df.xs(ticker, axis=1, level=1)
        except (KeyError, ValueError):
            try:
                sub = df.xs(ticker, axis=1, level=0)
            except (KeyError, ValueError):
                return []
        return _df_to_bars(sub)
    return _df_to_bars(df)


class YFinanceProvider(DataProvider):
    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        settings = get_settings()
        last_error: Optional[Exception] = None
        for attempt in range(settings.yfinance_max_retries):
            try:
                return await asyncio.to_thread(
                    self._fetch_sync, yfinance_symbol, start, end
                )
            except YFRateLimitError as exc:
                last_error = exc
                wait = settings.yfinance_retry_base_seconds * (2**attempt)
                logger.warning(
                    "yfinance 限流 %s，%ss 后重试 (%s/%s)",
                    yfinance_symbol,
                    wait,
                    attempt + 1,
                    settings.yfinance_max_retries,
                )
                await asyncio.sleep(wait)
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= settings.yfinance_max_retries:
                    raise
                wait = settings.yfinance_retry_base_seconds * (2**attempt)
                await asyncio.sleep(wait)
        raise last_error or RuntimeError(f"yfinance 拉取失败: {yfinance_symbol}")

    async def fetch_batch(
        self,
        symbol_to_ticker: Dict[str, str],
        start: date,
        end: date,
    ) -> Dict[str, list[OHLCVBar]]:
        """一次请求拉取多个标的，降低限流概率。"""
        if not symbol_to_ticker:
            return {}
        settings = get_settings()
        tickers = list(symbol_to_ticker.values())
        ticker_to_symbol = {v: k for k, v in symbol_to_ticker.items()}
        last_error: Optional[Exception] = None
        for attempt in range(settings.yfinance_max_retries):
            try:
                raw = await asyncio.to_thread(
                    self._fetch_batch_sync, tickers, start, end
                )
                out: Dict[str, list[OHLCVBar]] = {}
                for ticker, bars in raw.items():
                    sym = ticker_to_symbol.get(ticker)
                    if sym:
                        out[sym] = bars
                return out
            except YFRateLimitError as exc:
                last_error = exc
                wait = settings.yfinance_retry_base_seconds * (2 ** (attempt + 1))
                logger.warning("yfinance 批量限流，%ss 后重试", wait)
                await asyncio.sleep(wait)
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(settings.yfinance_retry_base_seconds)
        raise last_error or RuntimeError("yfinance 批量拉取失败")

    def _fetch_sync(self, yfinance_symbol: str, start: date, end: date) -> list[OHLCVBar]:
        session = _build_yfinance_session()
        df = yf.download(
            yfinance_symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            progress=False,
            threads=False,
            auto_adjust=True,
            session=session,
        )
        if df.empty:
            ticker = yf.Ticker(yfinance_symbol, session=session)
            df = ticker.history(start=start.isoformat(), end=end.isoformat(), interval="1d")
        return _df_to_bars(df)

    def _fetch_batch_sync(
        self, tickers: List[str], start: date, end: date
    ) -> Dict[str, list[OHLCVBar]]:
        session = _build_yfinance_session()
        df = yf.download(
            tickers,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=False,
            auto_adjust=True,
            session=session,
        )
        result: Dict[str, list[OHLCVBar]] = {}
        if len(tickers) == 1:
            result[tickers[0]] = _df_to_bars(df)
            return result
        for ticker in tickers:
            result[ticker] = _multi_ticker_df_to_bars(df, ticker)
        return result
