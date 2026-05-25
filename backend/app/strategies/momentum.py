"""价格动量 + 趋势均线：中长期趋势跟踪（类似双动量简化）。"""

import pandas as pd

from app.strategies.common import latest_from_scan, scan_cross_signals


def _params(params: dict) -> tuple[int, int, float]:
    lookback = int(params.get("lookback", 63))
    trend_ma = int(params.get("trend_ma", 100))
    roc_threshold = float(params.get("roc_threshold", 0.0))
    if lookback < 10:
        raise ValueError("动量回看周期至少 10")
    if trend_ma < lookback:
        raise ValueError("趋势均线周期应不小于动量回看周期")
    return lookback, trend_ma, roc_threshold


def min_bars_required(params: dict) -> int:
    lookback, trend_ma, _ = _params(params)
    return max(lookback, trend_ma) + 5


def _prepare_df(bars: list[dict], params: dict) -> pd.DataFrame:
    lookback, trend_ma, roc_threshold = _params(params)
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    df["roc"] = df["close"] / df["close"].shift(lookback) - 1.0
    df["trend"] = df["close"].rolling(trend_ma).mean()
    df["long_ok"] = (df["roc"] > roc_threshold) & (df["close"] > df["trend"])
    df["short_ok"] = (df["roc"] < -roc_threshold) & (df["close"] < df["trend"])
    return df


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list:
    lookback, trend_ma, roc_threshold = _params(params)
    if len(bars) < min_bars_required(params):
        return []
    df = _prepare_df(bars, params)
    prev_long = df["long_ok"].shift(1).astype("boolean").fillna(False)
    prev_short = df["short_ok"].shift(1).astype("boolean").fillna(False)
    bullish = df["long_ok"] & ~prev_long
    bearish = df["short_ok"] & ~prev_short
    return scan_cross_signals(
        instrument_id,
        symbol,
        df,
        bullish_mask=bullish,
        bearish_mask=bearish,
        long_reason=f"{lookback}日动量>{roc_threshold:.1%}且站上{trend_ma}均线",
        short_reason=f"{lookback}日动量<-{roc_threshold:.1%}且跌破{trend_ma}均线",
    )


def latest_signal(instrument_id: int, symbol: str, bars: list[dict], params: dict) -> list:
    return latest_from_scan(scan_historical_signals(instrument_id, symbol, bars, params))
