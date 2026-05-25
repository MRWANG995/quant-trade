"""组合策略（Composite）：加权聚合多个子策略的信号。

子策略由引擎在调用前 resolve 进 params['_resolved_children']，
单元为 {strategy_id, strategy_type, name, params, weight}。
"""

from __future__ import annotations

from app.models.entities import SignalSide
from app.strategies.base import StrategySignal


def _validate(params: dict) -> tuple[str, list[dict]]:
    mode = params.get("mode", "weighted")
    if mode != "weighted":
        # 目前只实现 weighted；vote/and/any 留给后续
        raise ValueError(f"暂不支持的组合模式: {mode}（仅 weighted 可用）")
    children = params.get("_resolved_children")
    if not children:
        raise ValueError(
            "composite 策略需通过引擎调用：缺少 _resolved_children；"
            "请检查回测/扫描入口是否做了子策略解析"
        )
    return mode, children


def min_bars_required(params: dict) -> int:
    # 延迟 import 避免循环：组合策略的最小 bar 数 = 子策略中最大的需求
    from app.strategies.registry import min_bars_required as child_min_bars

    _, children = _validate(params)
    if not children:
        return 60
    return max(child_min_bars(c["strategy_type"], c["params"]) for c in children)


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    from app.strategies.registry import scan_historical_signals as child_scan

    _, children = _validate(params)
    # signal_date -> {"long": weighted_score, "short": weighted_score, "reasons": [...]}
    bucket: dict = {}
    for c in children:
        weight = float(c.get("weight", 0.0))
        if weight <= 0:
            continue
        sigs = child_scan(c["strategy_type"], instrument_id, symbol, bars, c["params"])
        for sig in sigs:
            slot = bucket.setdefault(
                sig.signal_date, {"long": 0.0, "short": 0.0, "reasons": []}
            )
            # 强度 0 时退化为权重本身贡献（信号存在即有发言权）
            magnitude = abs(sig.strength) if sig.strength else 1.0
            contrib = weight * magnitude
            key = "long" if sig.side == SignalSide.long else "short"
            slot[key] += contrib
            child_name = c.get("name") or f"#{c['strategy_id']}"
            slot["reasons"].append(
                f"{child_name} {sig.side.value} (w={weight:g})"
            )

    out: list[StrategySignal] = []
    for d, slot in bucket.items():
        net = slot["long"] - slot["short"]
        if abs(net) < 1e-9:
            continue
        side = SignalSide.long if net > 0 else SignalSide.short
        out.append(
            StrategySignal(
                instrument_id=instrument_id,
                symbol=symbol,
                signal_date=d,
                side=side,
                strength=abs(net),
                reason="; ".join(slot["reasons"][:4]),
            )
        )
    out.sort(key=lambda s: s.signal_date)
    return out


def latest_signal(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    sigs = scan_historical_signals(instrument_id, symbol, bars, params)
    if not sigs:
        return []
    last = max(s.signal_date for s in sigs)
    return [s for s in sigs if s.signal_date == last]
