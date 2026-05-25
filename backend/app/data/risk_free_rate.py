"""无风险利率（美国 3 月期国债年化收益率，FRED DGS3MO）。

策略：优先从 FRED 公开 CSV 拉取（不需要 API Key），按日缓存到本地
risk_free_rates 表；找不到任何数据时回退到 settings.default_risk_free_rate。
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import RiskFreeRate

logger = logging.getLogger(__name__)

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO"
FALLBACK_RATE = 0.0  # 拉取失败且 DB 也无记录时的兜底（年化）


async def _fetch_fred_dgs3mo() -> list[tuple[date, float]]:
    """从 FRED 公开 CSV 抓取 DGS3MO 日序列。返回 (date, rate) 列表，rate 为小数（如 0.045）。"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(FRED_CSV_URL)
            resp.raise_for_status()
            text = resp.text
    except Exception as exc:
        logger.warning("FRED DGS3MO fetch failed: %s", exc)
        return []

    rows: list[tuple[date, float]] = []
    reader = csv.DictReader(io.StringIO(text))
    # FRED 列名形如 "DATE","DGS3MO"。早年还可能是 "observation_date" / "DGS3MO"。
    date_key = next(
        (k for k in (reader.fieldnames or []) if k.lower() in ("date", "observation_date")),
        None,
    )
    value_key = next(
        (k for k in (reader.fieldnames or []) if k.upper() == "DGS3MO"),
        None,
    )
    if not date_key or not value_key:
        logger.warning("FRED CSV format unexpected: %s", reader.fieldnames)
        return []

    for row in reader:
        raw_d = (row.get(date_key) or "").strip()
        raw_v = (row.get(value_key) or "").strip()
        if not raw_d or not raw_v or raw_v == ".":
            continue
        try:
            d = datetime.strptime(raw_d, "%Y-%m-%d").date()
            v = float(raw_v) / 100.0  # FRED 给的是百分比
        except ValueError:
            continue
        rows.append((d, v))
    return rows


async def refresh_risk_free_rates(session: AsyncSession) -> dict:
    """拉取 FRED 最新数据并 upsert 到 risk_free_rates 表。"""
    rows = await _fetch_fred_dgs3mo()
    if not rows:
        return {"status": "skipped", "reason": "fetch_failed", "inserted": 0}

    existing_dates = {
        d
        for d, in (
            await session.execute(select(RiskFreeRate.as_of_date))
        ).all()
    }
    inserted = 0
    now = datetime.now(timezone.utc)
    for d, rate in rows:
        if d in existing_dates:
            continue
        session.add(RiskFreeRate(as_of_date=d, rate=rate, fetched_at=now))
        inserted += 1
    if inserted:
        await session.commit()
    return {
        "status": "ok",
        "inserted": inserted,
        "total": len(existing_dates) + inserted,
        "latest_date": rows[-1][0].isoformat(),
        "latest_rate_pct": round(rows[-1][1] * 100, 3),
    }


async def get_risk_free_rate_for_period(
    session: AsyncSession, start: date, end: date
) -> float:
    """回测期内的代表无风险利率：取期内所有可用日均值；若无数据则取最近一条；再无则回退。

    返回年化小数（如 0.045 表示 4.5%）。
    """
    # 期内均值
    result = await session.execute(
        select(RiskFreeRate).where(
            RiskFreeRate.as_of_date >= start,
            RiskFreeRate.as_of_date <= end,
        )
    )
    rows = result.scalars().all()
    if rows:
        return sum(r.rate for r in rows) / len(rows)

    # 最近一条
    latest = (
        await session.execute(
            select(RiskFreeRate).order_by(desc(RiskFreeRate.as_of_date)).limit(1)
        )
    ).scalar_one_or_none()
    if latest:
        return latest.rate

    # 兜底：第一次跑时若网络也不通，尝试拉一次后再查
    refresh = await refresh_risk_free_rates(session)
    if refresh.get("inserted", 0) > 0:
        result = await session.execute(
            select(RiskFreeRate).order_by(desc(RiskFreeRate.as_of_date)).limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest:
            return latest.rate

    settings = get_settings()
    return getattr(settings, "default_risk_free_rate", FALLBACK_RATE)


async def get_latest_risk_free_rate(session: AsyncSession) -> Optional[dict]:
    latest = (
        await session.execute(
            select(RiskFreeRate).order_by(desc(RiskFreeRate.as_of_date)).limit(1)
        )
    ).scalar_one_or_none()
    if not latest:
        return None
    return {
        "date": latest.as_of_date.isoformat(),
        "rate_annual_pct": round(latest.rate * 100, 3),
        "fetched_at": latest.fetched_at.isoformat() if latest.fetched_at else None,
        "stale": (date.today() - latest.as_of_date) > timedelta(days=14),
    }
