from datetime import date
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import Bar, Instrument


async def get_market_data_readiness(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    result = await session.execute(
        select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.symbol)
    )
    instruments = result.scalars().all()
    per_symbol: dict[str, dict[str, Any]] = {}
    total_bars = 0
    min_bars_for_ready = 60

    for inst in instruments:
        count_result = await session.execute(
            select(func.count(Bar.id)).where(Bar.instrument_id == inst.id)
        )
        count = int(count_result.scalar_one() or 0)
        last_result = await session.execute(
            select(func.max(Bar.trade_date)).where(Bar.instrument_id == inst.id)
        )
        last_date: Optional[date] = last_result.scalar_one_or_none()
        total_bars += count
        per_symbol[inst.symbol] = {
            "bar_count": count,
            "last_trade_date": last_date.isoformat() if last_date else None,
            "ready": count >= min_bars_for_ready,
        }

    symbols_ready = sum(1 for v in per_symbol.values() if v["ready"])
    symbol_count = len(per_symbol)
    zero_key_mode = not settings.stooq_api_key and not settings.alphavantage_api_key

    return {
        "stooq_configured": bool(settings.stooq_api_key),
        "alphavantage_configured": bool(settings.alphavantage_api_key),
        "zero_key_mode": zero_key_mode,
        "auto_demo_fallback": settings.auto_demo_fallback,
        "frankfurter_fallback": True,
        "yfinance_fallback": True,
        "ready": symbol_count > 0 and symbols_ready == symbol_count,
        "partial": symbols_ready > 0 and symbols_ready < symbol_count,
        "total_bars": total_bars,
        "symbols_ready": symbols_ready,
        "symbol_count": symbol_count,
        "instruments": per_symbol,
        "sources": ["frankfurter", "yfinance", "demo_fallback", "stooq", "alphavantage"],
        "message": _status_message(settings, symbols_ready, symbol_count, total_bars, zero_key_mode),
        "docs": {
            "stooq": "https://stooq.com/q/d/?s=eurusd&get_apikey",
            "alphavantage": "https://www.alphavantage.co/support/#api-key",
        },
    }


def _status_message(
    settings,
    symbols_ready: int,
    symbol_count: int,
    total_bars: int,
    zero_key_mode: bool,
) -> str:
    if symbol_count and symbols_ready == symbol_count:
        if zero_key_mode:
            return (
                f"K 线已就绪（共 {total_bars} 根）。"
                "零 Key 模式：外汇为 Frankfurter 真实价，黄金/期货可能含演示补全"
            )
        return f"K 线已就绪（共 {total_bars} 根）"
    if symbols_ready > 0:
        return (
            f"部分品种已有 K 线（{symbols_ready}/{symbol_count}）。"
            "请点「全量灌库」；无需 Stooq Key，失败品种会自动演示补全"
        )
    if zero_key_mode:
        return (
            "无需 API Key：外汇走 Frankfurter，黄金/期货走批量 Yahoo，"
            "仍失败则自动演示数据。请执行全量灌库。"
        )
    return "请执行全量灌库：POST /api/data/bootstrap?force=true"
