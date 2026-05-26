"""各品种免费数据源映射（Stooq / Alpha Vantage / Frankfurter / yfinance）。"""

from dataclasses import dataclass
from typing import Literal, Optional, Union

ProviderName = Literal[
    "stooq", "alphavantage", "frankfurter", "yfinance", "binance", "coinbase"
]

# 零配置回退：Yahoo 真实日 K（非模拟，易限流）
YFINANCE_SYMBOLS: dict[str, str] = {
    "XAUUSD": "GC=F",
    # 美股 Magnificent 7
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "NVDA": "NVDA",
    "META": "META",
    "TSLA": "TSLA",
    # BTC 不走 yfinance（Binance 本身就是主路径）
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


@dataclass(frozen=True)
class BinanceRef:
    symbol: str  # 例：BTCUSDT


@dataclass(frozen=True)
class CoinbaseRef:
    product_id: str  # 例：BTC-USD


ProviderRef = Union[
    StooqRef,
    AlphaVantageFxRef,
    AlphaVantageEquityRef,
    FrankfurterFxRef,
    BinanceRef,
    CoinbaseRef,
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
    # 加密货币：Coinbase 全球可用（Binance 在美国地区 451 被封）；Binance 留作 fallback
    "BTC": InstrumentDataConfig(
        providers=(
            ("coinbase", CoinbaseRef("BTC-USD")),
            ("binance", BinanceRef("BTCUSDT")),
        )
    ),
    # 黄金
    "XAUUSD": InstrumentDataConfig(
        providers=(
            ("stooq", StooqRef("xauusd")),
            ("alphavantage", AlphaVantageFxRef("XAU", "USD")),
        )
    ),
    # 美股 Magnificent 7
    "AAPL": _equity_config("AAPL", "aapl.us"),
    "MSFT": _equity_config("MSFT", "msft.us"),
    "GOOGL": _equity_config("GOOGL", "googl.us"),
    "AMZN": _equity_config("AMZN", "amzn.us"),
    "NVDA": _equity_config("NVDA", "nvda.us"),
    "META": _equity_config("META", "meta.us"),
    "TSLA": _equity_config("TSLA", "tsla.us"),
}


def get_data_config(symbol: str) -> Optional[InstrumentDataConfig]:
    return INSTRUMENT_DATA.get(symbol)
