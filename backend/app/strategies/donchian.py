"""唐奇安通道突破（海龟交易法简化版）。"""

import pandas as pd

from app.strategies.common import latest_from_scan, scan_cross_signals


def _params(params: dict) -> int:
    entry = int(params.get("entry_period", 20))
    if entry < 5:
        raise ValueError("突破周期至少为 5")
    if entry > 252:
        raise ValueError("突破周期不能超过 252")
    return entry


def min_bars_required(params: dict) -> int:
    return _params(params) + 5


def _prepare_df(bars: list[dict], params: dict) -> pd.DataFrame:
    entry = _params(params)
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    df["upper"] = df["high"].rolling(entry).max().shift(1)
    df["lower"] = df["low"].rolling(entry).min().shift(1)
    return df


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list:
    entry = _params(params)
    if len(bars) < entry + 2:
        return []
    df = _prepare_df(bars, params)
    bullish = (df["close"] > df["upper"]) & (df["close"].shift(1) <= df["upper"].shift(1))
    bearish = (df["close"] < df["lower"]) & (df["close"].shift(1) >= df["lower"].shift(1))
    return scan_cross_signals(
        instrument_id,
        symbol,
        df,
        bullish_mask=bullish,
        bearish_mask=bearish,
        long_reason=f"唐奇安 {entry} 日向上突破",
        short_reason=f"唐奇安 {entry} 日向下突破",
    )


def latest_signal(instrument_id: int, symbol: str, bars: list[dict], params: dict) -> list:
    return latest_from_scan(scan_historical_signals(instrument_id, symbol, bars, params))
