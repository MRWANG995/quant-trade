"""各品种免费数据源映射（Stooq / Alpha Vantage / Frankfurter / yfinance）。"""

from dataclasses import dataclass
from typing import Literal, Optional, Union

ProviderName = Literal["stooq", "alphavantage", "frankfurter", "yfinance"]

# 零配置回退：Yahoo 真实日 K（非模拟，易限流）
YFINANCE_SYMBOLS: dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F",
    "ES": "ES=F",
    "CL": "CL=F",
    # 美股 Magnificent 7
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "NVDA": "NVDA",
    "META": "META",
    "TSLA": "TSLA",
    # 补充美股 ETF
    "SPY": "SPY",
    "QQQ": "QQQ",
}


@dataclass(frozen=True)
class StooqRef:
    symbol: str


@dataclass(frozen=True)
class AlphaVantageFxRef:
    from_symbol: str
    to_symbol: str


@dataclass(frozen=True)
class AlphaVantageEquityRef:
    symbol: str


@dataclass(frozen=True)
class FrankfurterFxRef:
    base: str
    quote: str


ProviderRef = Union[
    StooqRef, AlphaVantageFxRef, AlphaVantageEquityRef, FrankfurterFxRef
]


@dataclass(frozen=True)
class InstrumentDataConfig:
    providers: tuple[tuple[ProviderName, ProviderRef], ...]


def _equity_config(ticker: str, stooq_sym: str) -> InstrumentDataConfig:
    return InstrumentDataConfig(
        providers=(
            ("stooq", StooqRef(stooq_sym)),
            ("alphavantage", AlphaVantageEquityRef(ticker)),
        )
    )


INSTRUMENT_DATA: dict[str, InstrumentDataConfig] = {
    "EURUSD": InstrumentDataConfig(
        providers=(
            ("stooq", StooqRef("eurusd")),
            ("alphavantage", AlphaVantageFxRef("EUR", "USD")),
            ("frankfurter", FrankfurterFxRef("EUR", "USD")),
        )
    ),
    "GBPUSD": InstrumentDataConfig(
        providers=(
            ("stooq", StooqRef("gbpusd")),
            ("alphavantage", AlphaVantageFxRef("GBP", "USD")),
            ("frankfurter", FrankfurterFxRef("GBP", "USD")),
        )
    ),
    "USDJPY": InstrumentDataConfig(
        providers=(
            ("stooq", StooqRef("usdjpy")),
            ("alphavantage", AlphaVantageFxRef("USD", "JPY")),
            ("frankfurter", FrankfurterFxRef("USD", "JPY")),
        )
    ),
    "XAUUSD": InstrumentDataConfig(
        providers=(
            ("stooq", StooqRef("xauusd")),
            ("alphavantage", AlphaVantageFxRef("XAU", "USD")),
        )
    ),
    "ES": InstrumentDataConfig(providers=(("stooq", StooqRef("es.c")),)),
    "CL": InstrumentDataConfig(providers=(("stooq", StooqRef("cl.c")),)),
    # Magnificent 7
    "AAPL": _equity_config("AAPL", "aapl.us"),
    "MSFT": _equity_config("MSFT", "msft.us"),
    "GOOGL": _equity_config("GOOGL", "googl.us"),
    "AMZN": _equity_config("AMZN", "amzn.us"),
    "NVDA": _equity_config("NVDA", "nvda.us"),
    "META": _equity_config("META", "meta.us"),
    "TSLA": _equity_config("TSLA", "tsla.us"),
    "SPY": _equity_config("SPY", "spy.us"),
    "QQQ": _equity_config("QQQ", "qqq.us"),
}


def get_data_config(symbol: str) -> Optional[InstrumentDataConfig]:
    return INSTRUMENT_DATA.get(symbol)
