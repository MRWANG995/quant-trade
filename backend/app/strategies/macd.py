import pandas as pd

from app.strategies.common import latest_from_scan, scan_cross_signals


def _params(params: dict) -> tuple[int, int, int]:
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal = int(params.get("signal", 9))
    if fast >= slow:
        raise ValueError("MACD 快线必须小于慢线")
    return fast, slow, signal


def min_bars_required(params: dict) -> int:
    _, slow, signal = _params(params)
    return slow + signal + 5


def _prepare_df(bars: list[dict], params: dict) -> pd.DataFrame:
    fast, slow, signal = _params(params)
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    return df


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list:
    fast, slow, signal = _params(params)
    if len(bars) < slow + signal + 2:
        return []
    df = _prepare_df(bars, params)
    bullish = (df["macd"].shift(1) <= df["macd_signal"].shift(1)) & (
        df["macd"] > df["macd_signal"]
    )
    bearish = (df["macd"].shift(1) >= df["macd_signal"].shift(1)) & (
        df["macd"] < df["macd_signal"]
    )
    return scan_cross_signals(
        instrument_id,
        symbol,
        df,
        bullish_mask=bullish,
        bearish_mask=bearish,
        long_reason=f"MACD({fast},{slow},{signal}) 金叉",
        short_reason=f"MACD({fast},{slow},{signal}) 死叉",
    )


def latest_signal(instrument_id: int, symbol: str, bars: list[dict], params: dict) -> list:
    return latest_from_scan(scan_historical_signals(instrument_id, symbol, bars, params))
