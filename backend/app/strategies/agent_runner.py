"""Agent 策略的 LLM 调用器：拼指标摘要 → 调 Gemini → 缓存到 DB。"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import get_llm_provider, LLMError
from app.models.entities import AgentDecision, Bar, Instrument, StrategyDefinition
from app.strategies.dsl.indicators import _atr, _ema, _rsi, _sma  # 复用 DSL 实现

logger = logging.getLogger(__name__)

SYSTEM_TEMPLATE = """你是一个经验丰富的量化交易员，正在为客户标注实时的入场/出场点。

用户策略指导：{user_prompt}

请基于给定的近期 K 线和指标，给出一个**可执行的交易计划**，JSON 格式：
{{
  "side": "long" | "short" | "hold",
  "confidence": 0.0 到 1.0 之间的浮点数,
  "entry_price": 数字（建议入场价；hold 时填 null）,
  "stop_loss": 数字（止损价；hold 时填 null）,
  "take_profit": 数字（止盈价；hold 时填 null）,
  "reason": "不超过 80 字的中文说明：为什么这样定价"
}}

要求：
- 仅输出 JSON，不要其他文字、不要 markdown 代码块
- side=long 时：entry_price 通常贴近当前价；stop_loss < entry_price；take_profit > entry_price
- side=short 时：entry_price 通常贴近当前价；stop_loss > entry_price；take_profit < entry_price
- 趋势/震荡不明、不确定时返回 hold，三个价位填 null，confidence ≤ 0.3
- 止盈 / 止损至少要考虑 ATR 等波动率，止损不能太近（被噪声打掉）也不能太远（损失过大）
- 风险回报比（reward / risk）原则上 ≥ 1.5，否则不入场"""


def _build_context(symbol: str, bars: list[dict], lookback: int) -> str:
    """生成喂给 LLM 的标的上下文：最近 N 根 K 线 + 关键指标当前值。"""
    if len(bars) < 30:
        return f"{symbol}: 数据不足"
    df = pd.DataFrame(bars).sort_values("trade_date").reset_index(drop=True)
    last = min(lookback, len(df))
    recent = df.tail(last)
    # 指标用全量 df 计算，截取末值
    rsi14 = float(_rsi(df["close"], 14).iloc[-1])
    sma20 = float(_sma(df["close"], 20).iloc[-1])
    sma50 = float(_sma(df["close"], 50).iloc[-1])
    ema12 = float(_ema(df["close"], 12).iloc[-1])
    atr14 = float(_atr(df, 14).iloc[-1])
    close = float(df["close"].iloc[-1])
    high20 = float(df["high"].tail(20).max())
    low20 = float(df["low"].tail(20).min())

    # K 线最近 20 根（精度收敛，避免 prompt 太长）
    bars_csv = "date,open,high,low,close,volume\n" + "\n".join(
        f"{r['trade_date']},{r['open']:.4f},{r['high']:.4f},{r['low']:.4f},{r['close']:.4f},{r.get('volume', 0):.0f}"
        for _, r in recent.tail(20).iterrows()
    )

    return f"""标的：{symbol}
最新收盘：{close:.4f}
近 20 日通道：高 {high20:.4f} / 低 {low20:.4f}
指标：
  RSI(14) = {rsi14:.2f}
  SMA(20) = {sma20:.4f}（close 相对位置：{((close - sma20) / sma20 * 100):+.2f}%）
  SMA(50) = {sma50:.4f}（close 相对位置：{((close - sma50) / sma50 * 100):+.2f}%）
  EMA(12) = {ema12:.4f}
  ATR(14) = {atr14:.4f}（波动率约 {atr14 / close * 100:.2f}%）

最近 20 根日 K：
{bars_csv}"""


async def _cached_decision(
    session: AsyncSession,
    strategy_id: int,
    instrument_id: int,
    decision_date: date,
) -> Optional[AgentDecision]:
    result = await session.execute(
        select(AgentDecision).where(
            AgentDecision.strategy_id == strategy_id,
            AgentDecision.instrument_id == instrument_id,
            AgentDecision.decision_date == decision_date,
        )
    )
    return result.scalar_one_or_none()


async def _ask_llm(
    user_prompt: str,
    symbol: str,
    bars: list[dict],
    lookback: int,
) -> dict[str, Any]:
    provider = get_llm_provider()
    context = _build_context(symbol, bars, lookback)
    system = SYSTEM_TEMPLATE.format(user_prompt=user_prompt or "无特别偏好，按通用风险/收益判断")
    result = await provider.generate_json(system=system, user=context, temperature=0.3)
    parsed = result.parsed if isinstance(result.parsed, dict) else {}

    def _opt_float(key: str) -> Optional[float]:
        v = parsed.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {
        "side": str(parsed.get("side", "hold")).lower(),
        "confidence": float(parsed.get("confidence", 0.0)),
        "entry_price": _opt_float("entry_price"),
        "stop_loss": _opt_float("stop_loss"),
        "take_profit": _opt_float("take_profit"),
        "reason": str(parsed.get("reason", ""))[:300],
        "model": result.model,
        "raw": parsed,
    }


async def run_agent_decisions(
    session: AsyncSession,
    strategy_def: StrategyDefinition,
    instruments: list[Instrument],
    decision_date: date,
) -> list[dict]:
    """对每个 instrument 取得（或新计算）当日 LLM 决策，返回 dict 列表。"""
    params = strategy_def.params or {}
    user_prompt = str(params.get("system_prompt", "")).strip()
    lookback = int(params.get("lookback_bars", 60))
    out: list[dict] = []

    for inst in instruments:
        # 缓存命中
        cached = await _cached_decision(session, strategy_def.id, inst.id, decision_date)
        if cached:
            out.append({
                "instrument_id": inst.id,
                "decision_date": decision_date,
                "side": cached.side,
                "confidence": cached.confidence,
                "entry_price": cached.entry_price,
                "stop_loss": cached.stop_loss,
                "take_profit": cached.take_profit,
                "reason": cached.reason,
                "model": cached.model,
            })
            continue

        # 取最近 lookback + 60 根 K 线（为指标 warmup 留余量）
        bars_result = await session.execute(
            select(Bar)
            .where(Bar.instrument_id == inst.id, Bar.trade_date <= decision_date)
            .order_by(Bar.trade_date.desc())
            .limit(lookback + 60)
        )
        bars = list(reversed(bars_result.scalars().all()))
        if len(bars) < 30:
            continue
        bar_dicts = [{
            "trade_date": b.trade_date,
            "open": b.open, "high": b.high, "low": b.low,
            "close": b.close, "volume": b.volume,
        } for b in bars]

        try:
            decision = await _ask_llm(user_prompt, inst.symbol, bar_dicts, lookback)
        except LLMError as exc:
            logger.warning("Agent LLM 调用失败 %s: %s", inst.symbol, exc)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent 决策异常 %s: %s", inst.symbol, exc)
            continue

        # 写缓存（重复时不要因 UNIQUE 报错）
        try:
            session.add(AgentDecision(
                strategy_id=strategy_def.id,
                instrument_id=inst.id,
                decision_date=decision_date,
                side=decision["side"],
                confidence=decision["confidence"],
                entry_price=decision.get("entry_price"),
                stop_loss=decision.get("stop_loss"),
                take_profit=decision.get("take_profit"),
                reason=decision["reason"],
                raw_output=decision["raw"],
                model=decision["model"],
            ))
            await session.flush()
        except Exception:
            await session.rollback()

        out.append({
            "instrument_id": inst.id,
            "decision_date": decision_date,
            "side": decision["side"],
            "confidence": decision["confidence"],
            "entry_price": decision.get("entry_price"),
            "stop_loss": decision.get("stop_loss"),
            "take_profit": decision.get("take_profit"),
            "reason": decision["reason"],
            "model": decision["model"],
        })
        # 轻微节流，避免 Gemini 免费档 RPM 限流
        await asyncio.sleep(0.5)

    await session.commit()
    return out


async def analyze_single_instrument(
    session: AsyncSession,
    strategy_def: StrategyDefinition,
    instrument: Instrument,
    decision_date: date,
    force_refresh: bool = False,
) -> dict:
    """单标的即时分析：命中缓存直接返回，force_refresh=True 时重新调 LLM。"""
    params = strategy_def.params or {}
    user_prompt = str(params.get("system_prompt", "")).strip()
    lookback = int(params.get("lookback_bars", 60))

    if not force_refresh:
        cached = await _cached_decision(session, strategy_def.id, instrument.id, decision_date)
        if cached:
            return {
                "instrument_id": instrument.id,
                "symbol": instrument.symbol,
                "decision_date": decision_date.isoformat(),
                "side": cached.side,
                "confidence": cached.confidence,
                "entry_price": cached.entry_price,
                "stop_loss": cached.stop_loss,
                "take_profit": cached.take_profit,
                "reason": cached.reason,
                "model": cached.model,
                "cached": True,
            }

    # 拿最近 lookback + 60 根 K 线
    bars_result = await session.execute(
        select(Bar)
        .where(Bar.instrument_id == instrument.id, Bar.trade_date <= decision_date)
        .order_by(Bar.trade_date.desc())
        .limit(lookback + 60)
    )
    bars = list(reversed(bars_result.scalars().all()))
    if len(bars) < 30:
        raise LLMError(f"{instrument.symbol} K 线不足（需至少 30 根），请先同步行情")

    bar_dicts = [{
        "trade_date": b.trade_date,
        "open": b.open, "high": b.high, "low": b.low,
        "close": b.close, "volume": b.volume,
    } for b in bars]

    decision = await _ask_llm(user_prompt, instrument.symbol, bar_dicts, lookback)

    # 删旧记录后再写新缓存（force_refresh 时）
    if force_refresh:
        existing = await _cached_decision(session, strategy_def.id, instrument.id, decision_date)
        if existing:
            await session.delete(existing)
            await session.flush()

    try:
        session.add(AgentDecision(
            strategy_id=strategy_def.id,
            instrument_id=instrument.id,
            decision_date=decision_date,
            side=decision["side"],
            confidence=decision["confidence"],
            entry_price=decision.get("entry_price"),
            stop_loss=decision.get("stop_loss"),
            take_profit=decision.get("take_profit"),
            reason=decision["reason"],
            raw_output=decision["raw"],
            model=decision["model"],
        ))
        await session.commit()
    except Exception:
        await session.rollback()

    return {
        "instrument_id": instrument.id,
        "symbol": instrument.symbol,
        "decision_date": decision_date.isoformat(),
        "side": decision["side"],
        "confidence": decision["confidence"],
        "entry_price": decision.get("entry_price"),
        "stop_loss": decision.get("stop_loss"),
        "take_profit": decision.get("take_profit"),
        "reason": decision["reason"],
        "model": decision["model"],
        "cached": False,
    }
