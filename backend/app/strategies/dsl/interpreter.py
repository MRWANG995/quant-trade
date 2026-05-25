"""DSL → StrategySignal 列表。与现有 registry 的策略实现签名一致。"""

from __future__ import annotations

import pandas as pd

from app.models.entities import SignalSide
from app.strategies.bars import parse_trade_date
from app.strategies.base import StrategySignal
from app.strategies.dsl.indicators import compute_bool
from app.strategies.dsl.spec import dsl_max_lookback


def _ensure_df(bars: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            raise ValueError(f"行情数据缺少 {col} 列")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df


def _extract_dsl(params: dict) -> dict:
    dsl = params.get("dsl")
    if not isinstance(dsl, dict):
        raise ValueError("llm_dsl 策略缺少 params.dsl")
    return dsl


def dsl_min_bars_required(params: dict) -> int:
    dsl = _extract_dsl(params)
    # 给指标 warmup 留余量 + 至少 30 根 bar 才生成信号
    return max(dsl_max_lookback(dsl) + 5, 30)


def dsl_scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    dsl = _extract_dsl(params)
    min_bars = dsl_min_bars_required(params)
    if len(bars) < min_bars:
        return []

    df = _ensure_df(bars)
    cache: dict[str, pd.Series] = {}

    # 编译所有条件为 boolean Series
    entry_masks: list[tuple[str, str, pd.Series]] = []  # (side, comment, mask)
    for ent in dsl["entries"]:
        mask = compute_bool(ent["when"], df, cache).fillna(False)
        entry_masks.append((ent["side"], ent.get("comment") or "", mask))

    exit_masks: list[tuple[str, pd.Series]] = []
    for ex in dsl.get("exits") or []:
        mask = compute_bool(ex["when"], df, cache).fillna(False)
        exit_masks.append((ex.get("comment") or "", mask))

    signals: list[StrategySignal] = []
    state_side: str | None = None  # 当前模拟持仓方向（仅用于避免连发同向 entry + 触发 exit）

    for i in range(len(df)):
        trade_date = parse_trade_date(df.iloc[i]["trade_date"])

        # 先 exits：触发出场则把 state_side 清空，并发出 flat 信号
        if state_side is not None:
            for comment, mask in exit_masks:
                if bool(mask.iloc[i]):
                    signals.append(
                        StrategySignal(
                            symbol=symbol,
                            instrument_id=instrument_id,
                            signal_date=trade_date,
                            side=SignalSide.flat,
                            strength=0.4,
                            reason=f"DSL 出场：{comment}" if comment else "DSL 出场条件触发",
                        )
                    )
                    state_side = None
                    break

        # 再 entries：当前无持仓或方向与本条不同才发
        for side, comment, mask in entry_masks:
            if not bool(mask.iloc[i]):
                continue
            if state_side == side:
                continue  # 已经同向，不重复
            signals.append(
                StrategySignal(
                    symbol=symbol,
                    instrument_id=instrument_id,
                    signal_date=trade_date,
                    side=SignalSide.long if side == "long" else SignalSide.short,
                    strength=0.6,
                    reason=f"DSL 入场：{comment}" if comment else f"DSL 入场（{side}）",
                )
            )
            state_side = side
            break  # 一根 bar 内只允许一次 entry

    return signals


def dsl_latest_signal(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    sigs = dsl_scan_historical_signals(instrument_id, symbol, bars, params)
    if not sigs:
        return []
    last = max(s.signal_date for s in sigs)
    return [s for s in sigs if s.signal_date == last]
