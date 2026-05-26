import asyncio
from datetime import date

from app.config import get_settings
from app.data.alphavantage_provider import AlphaVantageProvider
from app.data.base import DataProvider, OHLCVBar
from app.data.binance_provider import BinanceProvider
from app.data.coinbase_provider import CoinbaseProvider
from app.data.frankfurter_provider import FrankfurterProvider
from app.data.stooq_provider import StooqProvider
from app.data.symbols import (
    AlphaVantageEquityRef,
    AlphaVantageFxRef,
    BinanceRef,
    CoinbaseRef,
    FrankfurterFxRef,
    InstrumentDataConfig,
    StooqRef,
    YFINANCE_SYMBOLS,
    get_data_config,
)
from app.data.yfinance_provider import YFinanceProvider


class CompositeDataProvider(DataProvider):
    """Binance（加密） → Stooq → Alpha Vantage → Frankfurter（外汇）→ Yahoo Finance。"""

    def __init__(self) -> None:
        self._stooq = StooqProvider()
        self._av = AlphaVantageProvider()
        self._frankfurter = FrankfurterProvider()
        self._yf = YFinanceProvider()
        self._binance = BinanceProvider()
        self._coinbase = CoinbaseProvider()
        self._settings = get_settings()

    async def fetch_daily_bars(
        self, yfinance_symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        config = get_data_config(yfinance_symbol)
        if config is None:
            raise RuntimeError(f"未配置数据源映射: {yfinance_symbol}")
        return await self.fetch_for_symbol(yfinance_symbol, config, start, end)

    async def fetch_for_symbol(
        self,
        instrument_symbol: str,
        config: InstrumentDataConfig,
        start: date,
        end: date,
    ) -> list[OHLCVBar]:
        errors: list[str] = []

        for name, ref in config.providers:
            if name == "stooq" and not self._settings.stooq_api_key:
                continue
            if name == "alphavantage" and not self._settings.alphavantage_api_key:
                continue
            try:
                bars = await self._fetch_one(name, ref, start, end)
                if bars:
                    return bars
                errors.append(f"{name}: 空数据")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
            if name == "alphavantage":
                await asyncio.sleep(12)

        yf_ticker = YFINANCE_SYMBOLS.get(instrument_symbol)
        if yf_ticker:
            try:
                await asyncio.sleep(self._settings.yfinance_request_delay_seconds)
                bars = await self._yf.fetch_daily_bars(yf_ticker, start, end)
                if bars:
                    return bars
                errors.append("yfinance: 空数据")
            except Exception as exc:
                errors.append(f"yfinance: {exc}")

        raise RuntimeError(
            f"{instrument_symbol} 拉取失败: " + "; ".join(errors)
        )

    async def _fetch_one(self, name: str, ref, start: date, end: date) -> list[OHLCVBar]:
        if name == "stooq" and isinstance(ref, StooqRef):
            return await self._stooq.fetch_daily_bars(ref.symbol, start, end)
        if name == "alphavantage" and isinstance(ref, AlphaVantageFxRef):
            return await self._av.fetch_fx(ref, start, end)
        if name == "alphavantage" and isinstance(ref, AlphaVantageEquityRef):
            return await self._av.fetch_equity(ref, start, end)
        if name == "frankfurter" and isinstance(ref, FrankfurterFxRef):
            return await self._frankfurter.fetch_fx(ref.base, ref.quote, start, end)
        if name == "binance" and isinstance(ref, BinanceRef):
            return await self._binance.fetch_daily_bars(ref.symbol, start, end)
        if name == "coinbase" and isinstance(ref, CoinbaseRef):
            return await self._coinbase.fetch_daily_bars(ref.product_id, start, end)
        raise RuntimeError(f"未知数据源配置: {name} {ref}")
