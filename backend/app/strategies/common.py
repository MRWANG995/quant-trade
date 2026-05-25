"""策略信号扫描共用工具。"""
from datetime import date

import pandas as pd

from app.models.entities import SignalSide
from app.strategies.base import StrategySignal
from app.strategies.bars import parse_trade_date


def scan_cross_signals(
    instrument_id: int,
    symbol: str,
    df: pd.DataFrame,
    *,
    bullish_mask: pd.Series,
    bearish_mask: pd.Series,
    long_reason: str,
    short_reason: str,
) -> list[StrategySignal]:
    signals: list[StrategySignal] = []
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        trade_date = parse_trade_date(row["trade_date"])
        bull = bool(bullish_mask.iloc[i]) if pd.notna(bullish_mask.iloc[i]) else False
        bear = bool(bearish_mask.iloc[i]) if pd.notna(bearish_mask.iloc[i]) else False
        prev_bull = bool(bullish_mask.iloc[i - 1]) if pd.notna(bullish_mask.iloc[i - 1]) else False
        prev_bear = bool(bearish_mask.iloc[i - 1]) if pd.notna(bearish_mask.iloc[i - 1]) else False
        if bull and not prev_bull:
            signals.append(
                StrategySignal(
                    symbol=symbol,
                    instrument_id=instrument_id,
                    signal_date=trade_date,
                    side=SignalSide.long,
                    strength=0.5,
                    reason=long_reason,
                )
            )
        elif bear and not prev_bear:
            signals.append(
                StrategySignal(
                    symbol=symbol,
                    instrument_id=instrument_id,
                    signal_date=trade_date,
                    side=SignalSide.short,
                    strength=0.5,
                    reason=short_reason,
                )
            )
    return signals


def latest_from_scan(signals: list[StrategySignal]) -> list[StrategySignal]:
    if not signals:
        return []
    last_date = max(s.signal_date for s in signals)
    return [s for s in signals if s.signal_date == last_date]
