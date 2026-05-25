from datetime import date

import pandas as pd

from app.strategies.base import StrategySignal
from app.strategies.common import latest_from_scan, scan_cross_signals


def _params(params: dict) -> tuple[int, float, float]:
    period = int(params.get("period", 14))
    oversold = float(params.get("oversold", 30))
    overbought = float(params.get("overbought", 70))
    if period < 2:
        raise ValueError("RSI 周期至少为 2")
    if oversold >= overbought:
        raise ValueError("超卖线必须小于超买线")
    return period, oversold, overbought


def min_bars_required(params: dict) -> int:
    period, _, _ = _params(params)
    return period + 5


def _prepare_df(bars: list[dict], params: dict) -> pd.DataFrame:
    period, oversold, overbought = _params(params)
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-10)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["oversold"] = oversold
    df["overbought"] = overbought
    return df


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    period, oversold, overbought = _params(params)
    if len(bars) < period + 2:
        return []
    df = _prepare_df(bars, params)
    bullish = (df["rsi"].shift(1) < oversold) & (df["rsi"] >= oversold)
    bearish = (df["rsi"].shift(1) > overbought) & (df["rsi"] <= overbought)
    return scan_cross_signals(
        instrument_id,
        symbol,
        df,
        bullish_mask=bullish,
        bearish_mask=bearish,
        long_reason=f"RSI{period} 脱离超卖({oversold})",
        short_reason=f"RSI{period} 脱离超买({overbought})",
    )


def latest_signal(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    return latest_from_scan(scan_historical_signals(instrument_id, symbol, bars, params))
