from datetime import date

import pandas as pd

from app.models.entities import SignalSide
from app.strategies.base import StrategySignal
from app.strategies.bars import parse_trade_date


def _params(params: dict) -> tuple[int, int]:
    fast_ma = int(params.get("fast_ma", 20))
    slow_ma = int(params.get("slow_ma", 50))
    if fast_ma >= slow_ma:
        raise ValueError("快线周期必须小于慢线周期")
    return fast_ma, slow_ma


def min_bars_required(params: dict) -> int:
    _, slow_ma = _params(params)
    return slow_ma + 2


def latest_signal(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    """仅最新一根 K 线上的交叉（用于每日扫描）。"""
    all_sigs = scan_historical_signals(instrument_id, symbol, bars, params)
    if not all_sigs:
        return []
    last_date = max(s.signal_date for s in all_sigs)
    return [s for s in all_sigs if s.signal_date == last_date]


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    """扫描整段历史，返回每个交易日的金叉/死叉信号（用于回测）。"""
    fast_ma, slow_ma = _params(params)
    if len(bars) < slow_ma + 2:
        return []

    df = pd.DataFrame(bars).sort_values("trade_date")
    df["fast"] = df["close"].rolling(fast_ma).mean()
    df["slow"] = df["close"].rolling(slow_ma).mean()
    df["prev_fast"] = df["fast"].shift(1)
    df["prev_slow"] = df["slow"].shift(1)

    signals: list[StrategySignal] = []
    for _, row in df.iterrows():
        if pd.isna(row["fast"]) or pd.isna(row["slow"]):
            continue
        signal_date = parse_trade_date(row["trade_date"])
        cross_up = row["prev_fast"] <= row["prev_slow"] and row["fast"] > row["slow"]
        cross_down = row["prev_fast"] >= row["prev_slow"] and row["fast"] < row["slow"]
        if cross_up:
            strength = abs(float((row["fast"] - row["slow"]) / row["close"]))
            signals.append(
                StrategySignal(
                    symbol=symbol,
                    instrument_id=instrument_id,
                    signal_date=signal_date,
                    side=SignalSide.long,
                    strength=strength,
                    reason=f"MA{fast_ma}/{slow_ma} 金叉",
                )
            )
        elif cross_down:
            strength = abs(float((row["slow"] - row["fast"]) / row["close"]))
            signals.append(
                StrategySignal(
                    symbol=symbol,
                    instrument_id=instrument_id,
                    signal_date=signal_date,
                    side=SignalSide.short,
                    strength=strength,
                    reason=f"MA{fast_ma}/{slow_ma} 死叉",
                )
            )
    return signals
