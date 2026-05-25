import asyncio
import logging
from datetime import date, timedelta
from typing import Optional, Union

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.data.composite_provider import CompositeDataProvider
from app.data.demo_bars import seed_demo_for_symbols
from app.data.symbols import YFINANCE_SYMBOLS, get_data_config
from app.data.yfinance_provider import YFinanceProvider
from app.models.entities import Bar, Instrument

logger = logging.getLogger(__name__)

FOREX_SYMBOLS = frozenset({"EURUSD", "GBPUSD", "USDJPY"})
MIN_BARS_READY = 60


async def _bar_count(session: AsyncSession, instrument_id: int) -> int:
    result = await session.scalar(
        select(func.count(Bar.id)).where(Bar.instrument_id == instrument_id)
    )
    return int(result or 0)


async def insert_bars(
    session: AsyncSession,
    instrument: Instrument,
    fetched: list,
    *,
    start: Optional[date] = None,
) -> int:
    if not fetched:
        return 0
    if start is None:
        start = min(b.trade_date for b in fetched)
    existing_dates_result = await session.execute(
        select(Bar.trade_date).where(
            Bar.instrument_id == instrument.id,
            Bar.trade_date >= start,
        )
    )
    existing_dates = set(existing_dates_result.scalars().all())
    inserted = 0
    seen: set[date] = set()
    for bar in fetched:
        if bar.trade_date in existing_dates or bar.trade_date in seen:
            continue
        seen.add(bar.trade_date)
        session.add(
            Bar(
                instrument_id=instrument.id,
                trade_date=bar.trade_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
        )
        inserted += 1
    if inserted:
        await session.commit()
    return inserted


async def sync_instrument_bars(
    session: AsyncSession,
    instrument: Instrument,
    provider: Optional[CompositeDataProvider] = None,
    lookback_days: int = 365 * 3,
) -> int:
    provider = provider or CompositeDataProvider()
    config = get_data_config(instrument.symbol)
    if config is None:
        raise RuntimeError(f"品种 {instrument.symbol} 无数据源配置")

    end = date.today()
    start = end - timedelta(days=lookback_days)

    last_bar = await session.execute(
        select(Bar)
        .where(Bar.instrument_id == instrument.id)
        .order_by(Bar.trade_date.desc())
        .limit(1)
    )
    existing = last_bar.scalar_one_or_none()
    if existing:
        start = existing.trade_date + timedelta(days=1)
        if start > end:
            return 0

    fetched = await provider.fetch_for_symbol(instrument.symbol, config, start, end)
    return await insert_bars(session, instrument, fetched, start=start)


async def _last_bar_date(session: AsyncSession, instrument_id: int) -> Optional[date]:
    result = await session.execute(
        select(func.max(Bar.trade_date)).where(Bar.instrument_id == instrument_id)
    )
    return result.scalar_one_or_none()


async def apply_zero_key_fallbacks(
    session: AsyncSession,
    stats: dict[str, Union[int, str]],
    *,
    lookback_days: int = 365 * 3,
) -> dict[str, Union[int, str]]:
    """无 Stooq/AV Key：批量 Yahoo → 仍失败则演示数据（仅补空缺品种）。"""
    settings = get_settings()
    result = await session.execute(
        select(Instrument).where(Instrument.is_active.is_(True))
    )
    instruments = result.scalars().all()
    end = date.today()
    start = end - timedelta(days=lookback_days)

    need_fill: list[Instrument] = []
    for inst in instruments:
        count = await _bar_count(session, inst.id)
        if count < MIN_BARS_READY:
            need_fill.append(inst)

    if not need_fill:
        return stats

    yf_targets = {
        inst.symbol: YFINANCE_SYMBOLS[inst.symbol]
        for inst in need_fill
        if inst.symbol in YFINANCE_SYMBOLS and inst.symbol not in FOREX_SYMBOLS
    }
    if yf_targets:
        try:
            batch = await YFinanceProvider().fetch_batch(yf_targets, start, end)
            for inst in need_fill:
                if inst.symbol not in batch:
                    continue
                bars = batch.get(inst.symbol) or []
                if not bars:
                    continue
                n = await insert_bars(session, inst, bars, start=start)
                if n:
                    stats[inst.symbol] = f"yfinance_batch:{n}"
                    logger.info("%s 批量 Yahoo 入库 %s 根", inst.symbol, n)
        except Exception as exc:
            logger.warning("批量 Yahoo 失败: %s", exc)
            for sym in yf_targets:
                if sym not in stats or str(stats[sym]).startswith("error"):
                    stats[sym] = f"yfinance_batch: {exc}"

    if settings.auto_demo_fallback:
        still_need: list[str] = []
        for inst in need_fill:
            if await _bar_count(session, inst.id) < MIN_BARS_READY:
                still_need.append(inst.symbol)
        if still_need:
            demo_stats = await seed_demo_for_symbols(session, still_need, force=True)
            for sym, n in demo_stats.items():
                stats[sym] = f"demo_fallback:{n}（合成数据，非实盘行情）"
    return stats


async def sync_all_instruments(
    session: AsyncSession,
    *,
    force: bool = False,
    only_stale: bool = True,
) -> dict[str, Union[int, str]]:
    settings = get_settings()
    result = await session.execute(select(Instrument).where(Instrument.is_active.is_(True)))
    instruments = result.scalars().all()
    provider = CompositeDataProvider()
    stats: dict[str, Union[int, str]] = {}
    stale_before = date.today() - timedelta(days=settings.yfinance_stale_days)

    worklist = [(inst.id, inst.symbol) for inst in instruments]
    for inst_id, symbol in worklist:
        if only_stale and not force:
            last = await _last_bar_date(session, inst_id)
            if last and last >= stale_before:
                stats[symbol] = "skipped_fresh"
                continue
        inst = await session.get(Instrument, inst_id)
        if not inst:
            stats[symbol] = "error: instrument missing"
            continue
        try:
            count = await sync_instrument_bars(session, inst, provider)
            stats[symbol] = count
        except Exception as exc:
            await session.rollback()
            stats[symbol] = f"error: {exc}"
        if symbol not in FOREX_SYMBOLS:
            await asyncio.sleep(settings.yfinance_request_delay_seconds)

    stats = await apply_zero_key_fallbacks(session, stats)
    return stats


async def sync_for_daily_run(session: AsyncSession) -> dict[str, Union[int, str]]:
    settings = get_settings()
    if settings.yfinance_sync_on_daily:
        return {
            "mode": "sync",
            "results": await sync_all_instruments(session, only_stale=True),
        }
    return {
        "mode": "skipped",
        "message": "每日扫描使用本地 K 线；手动「同步行情」更新数据",
    }
