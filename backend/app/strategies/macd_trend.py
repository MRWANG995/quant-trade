"""MACD 交叉 + 中长期均线趋势过滤（减少震荡假信号）。"""

import pandas as pd

from app.strategies.common import latest_from_scan, scan_cross_signals


def _params(params: dict) -> tuple[int, int, int, int]:
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal = int(params.get("signal", 9))
    trend_ma = int(params.get("trend_ma", 50))
    if fast >= slow:
        raise ValueError("MACD 快线必须小于慢线")
    if trend_ma < slow:
        raise ValueError("趋势均线周期应不小于 MACD 慢线")
    return fast, slow, signal, trend_ma


def min_bars_required(params: dict) -> int:
    _, slow, signal, trend_ma = _params(params)
    return max(slow + signal, trend_ma) + 5


def _prepare_df(bars: list[dict], params: dict) -> pd.DataFrame:
    fast, slow, signal, trend_ma = _params(params)
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["trend"] = df["close"].rolling(trend_ma).mean()
    return df


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list:
    fast, slow, signal, trend_ma = _params(params)
    if len(bars) < min_bars_required(params):
        return []
    df = _prepare_df(bars, params)
    macd_up = (df["macd"].shift(1) <= df["macd_signal"].shift(1)) & (df["macd"] > df["macd_signal"])
    macd_down = (df["macd"].shift(1) >= df["macd_signal"].shift(1)) & (df["macd"] < df["macd_signal"])
    bullish = macd_up & (df["close"] > df["trend"])
    bearish = macd_down & (df["close"] < df["trend"])
    return scan_cross_signals(
        instrument_id,
        symbol,
        df,
        bullish_mask=bullish,
        bearish_mask=bearish,
        long_reason=f"MACD 金叉且收盘>{trend_ma}均线",
        short_reason=f"MACD 死叉且收盘<{trend_ma}均线",
    )


def latest_signal(instrument_id: int, symbol: str, bars: list[dict], params: dict) -> list:
    return latest_from_scan(scan_historical_signals(instrument_id, symbol, bars, params))
