import pandas as pd

from app.strategies.common import latest_from_scan, scan_cross_signals


def _params(params: dict) -> tuple[int, float]:
    period = int(params.get("period", 20))
    std_dev = float(params.get("std_dev", 2.0))
    if period < 5:
        raise ValueError("布林带周期至少为 5")
    if std_dev <= 0:
        raise ValueError("标准差倍数必须大于 0")
    return period, std_dev


def min_bars_required(params: dict) -> int:
    period, _ = _params(params)
    return period + 5


def _prepare_df(bars: list[dict], params: dict) -> pd.DataFrame:
    period, std_dev = _params(params)
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    mid = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    df["bb_mid"] = mid
    df["bb_upper"] = mid + std_dev * std
    df["bb_lower"] = mid - std_dev * std
    return df


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list:
    period, std_dev = _params(params)
    if len(bars) < period + 2:
        return []
    df = _prepare_df(bars, params)
    # 均值回归：价格从下方穿回下轨做多，从上方跌破上轨做空
    bullish = (df["close"].shift(1) < df["bb_lower"].shift(1)) & (
        df["close"] >= df["bb_lower"]
    )
    bearish = (df["close"].shift(1) > df["bb_upper"].shift(1)) & (
        df["close"] <= df["bb_upper"]
    )
    return scan_cross_signals(
        instrument_id,
        symbol,
        df,
        bullish_mask=bullish,
        bearish_mask=bearish,
        long_reason=f"布林带{period} 下轨反弹",
        short_reason=f"布林带{period} 上轨回落",
    )


def latest_signal(instrument_id: int, symbol: str, bars: list[dict], params: dict) -> list:
    return latest_from_scan(scan_historical_signals(instrument_id, symbol, bars, params))
