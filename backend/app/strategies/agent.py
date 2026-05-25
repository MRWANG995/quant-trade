"""Agent 策略：把 LLM 的逐品种逐日决策渲染成 StrategySignal。

实际的 LLM 调用在 app.strategies.agent_runner 里异步发生，
由引擎在调用 scan/latest 前预先 resolve 进 params['_resolved_decisions']。
"""

from __future__ import annotations

from app.models.entities import SignalSide
from app.strategies.base import StrategySignal


def min_bars_required(params: dict) -> int:
    try:
        n = int(params.get("lookback_bars", 60))
    except (TypeError, ValueError):
        n = 60
    return max(n, 30)


def _decisions_for(params: dict, instrument_id: int) -> list[dict]:
    all_decisions = params.get("_resolved_decisions") or []
    return [d for d in all_decisions if d.get("instrument_id") == instrument_id]


def scan_historical_signals(
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    min_conf = float(params.get("min_confidence", 0.6))
    out: list[StrategySignal] = []
    for d in _decisions_for(params, instrument_id):
        side = d.get("side")
        conf = float(d.get("confidence", 0.0))
        if side not in ("long", "short") or conf < min_conf:
            continue
        out.append(
            StrategySignal(
                instrument_id=instrument_id,
                symbol=symbol,
                signal_date=d["decision_date"],
                side=SignalSide.long if side == "long" else SignalSide.short,
                strength=conf,
                reason=f"Agent({d.get('model', 'llm')}): {(d.get('reason') or '')[:200]}",
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
