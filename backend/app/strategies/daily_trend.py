"""兼容旧导入。"""
from app.strategies.bars import bars_to_records
from app.strategies.ma_cross import latest_signal


def compute_daily_trend_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    fast_ma: int = 20,
    slow_ma: int = 50,
):
    return latest_signal(
        instrument_id, symbol, bars, {"fast_ma": fast_ma, "slow_ma": slow_ma}
    )


__all__ = ["bars_to_records", "compute_daily_trend_signals"]
