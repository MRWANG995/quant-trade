"""Generate synthetic daily bars when yfinance is unavailable."""

import random
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Bar, Instrument

# 演示扫描时更容易出现金叉的标的
_CROSS_DEMO_SYMBOLS = {"EURUSD", "GBPUSD"}


def _trading_days(end: date, count: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def _closes_with_golden_cross(base: float, n: int) -> list[float]:
    """长周期缓跌 + 最后一根大阳线，保证 MA20/50 金叉落在最新 K 线。"""
    closes: list[float] = []
    price = base
    for i in range(n - 1):
        price *= 0.998
        closes.append(round(price, 4))
    closes.append(round(closes[-1] * 2.5, 4) if closes else round(base * 2.5, 4))
    return closes


def _closes_with_death_cross(base: float, n: int) -> list[float]:
    """长周期缓涨 + 最后一根大阴线，保证死叉落在最新 K 线。"""
    closes: list[float] = []
    price = base
    for i in range(n - 1):
        price *= 1.002
        closes.append(round(price, 4))
    closes.append(round(closes[-1] * 0.03, 4) if closes else round(base * 0.03, 4))
    return closes


def _has_cross(closes: list[float], fast_ma: int, slow_ma: int, golden: bool) -> bool:
    df = pd.DataFrame({"close": closes})
    df["fast"] = df["close"].rolling(fast_ma).mean()
    df["slow"] = df["close"].rolling(slow_ma).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(last["fast"]) or pd.isna(last["slow"]):
        return False
    cross_up = prev["fast"] <= prev["slow"] and last["fast"] > last["slow"]
    cross_down = prev["fast"] >= prev["slow"] and last["fast"] < last["slow"]
    return cross_up if golden else cross_down


async def seed_demo_for_symbols(
    session: AsyncSession,
    symbols: list[str],
    *,
    days: int = 320,
    force: bool = False,
) -> dict[str, int]:
    """仅为指定品种生成演示 K 线（用于无 API Key 时补全黄金/期货）。"""
    sym_set = {s.upper() for s in symbols}
    result = await session.execute(select(Instrument).where(Instrument.is_active.is_(True)))
    instruments = [i for i in result.scalars().all() if i.symbol in sym_set]
    return await _seed_instruments(session, instruments, days=days, force=force)


async def seed_demo_bars(
    session: AsyncSession,
    days: int = 320,
    force: bool = False,
) -> dict[str, int]:
    result = await session.execute(select(Instrument).where(Instrument.is_active.is_(True)))
    instruments = result.scalars().all()
    return await _seed_instruments(session, instruments, days=days, force=force)


async def _seed_instruments(
    session: AsyncSession,
    instruments: list[Instrument],
    *,
    days: int = 320,
    force: bool = False,
) -> dict[str, int]:
    stats: dict[str, int] = {}
    end = date.today()
    trade_dates = _trading_days(end, days)

    for inst in instruments:
        existing = await session.execute(
            select(Bar).where(Bar.instrument_id == inst.id).limit(1)
        )
        if existing.scalar_one_or_none() and not force:
            stats[inst.symbol] = 0
            continue

        if force:
            await session.execute(delete(Bar).where(Bar.instrument_id == inst.id))

        base = 100.0 + inst.id * 10
        n = len(trade_dates)
        if inst.symbol == "EURUSD":
            closes = _closes_with_golden_cross(base, n)
        elif inst.symbol == "GBPUSD":
            closes = _closes_with_death_cross(base, n)
        else:
            import math

            price = base
            closes = []
            for i in range(n):
                change = math.sin(i / 25) * 0.008 + random.uniform(-0.004, 0.004)
                price *= 1 + change
                closes.append(round(price, 4))

        inserted = 0
        for d, close_p in zip(trade_dates, closes):
            open_p = close_p * (1 + random.uniform(-0.002, 0.002))
            high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.003))
            low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.003))
            session.add(
                Bar(
                    instrument_id=inst.id,
                    trade_date=d,
                    open=round(open_p, 4),
                    high=round(high_p, 4),
                    low=round(low_p, 4),
                    close=close_p,
                    volume=random.randint(1000, 50000),
                )
            )
            inserted += 1
        stats[inst.symbol] = inserted

    await session.commit()
    return stats
