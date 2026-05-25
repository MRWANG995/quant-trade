from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AssetClass, BrokerHint, Instrument, StrategyDefinition
from app.strategies.presets import PRESET_STRATEGIES
from app.strategies.registry import validate_params
from app.strategies.service import clear_default_flag

# symbol, 中文名, yfinance_symbol（库内字段）, Stooq/展示用
DEFAULT_INSTRUMENTS = [
    # 外汇
    {
        "symbol": "EURUSD",
        "name": "欧元/美元",
        "yfinance_symbol": "eurusd",
        "asset_class": AssetClass.forex,
        "broker_hint": BrokerHint.oanda,
        "pip_value": 0.0001,
        "contract_size": 100_000,
    },
    {
        "symbol": "GBPUSD",
        "name": "英镑/美元",
        "yfinance_symbol": "gbpusd",
        "asset_class": AssetClass.forex,
        "broker_hint": BrokerHint.oanda,
        "pip_value": 0.0001,
        "contract_size": 100_000,
    },
    {
        "symbol": "USDJPY",
        "name": "美元/日元",
        "yfinance_symbol": "usdjpy",
        "asset_class": AssetClass.forex,
        "broker_hint": BrokerHint.oanda,
        "pip_value": 0.01,
        "contract_size": 100_000,
    },
    # 商品 / 期货
    {
        "symbol": "XAUUSD",
        "name": "现货黄金",
        "yfinance_symbol": "xauusd",
        "asset_class": AssetClass.metal,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.1,
        "contract_size": 100,
    },
    {
        "symbol": "ES",
        "name": "标普500期货",
        "yfinance_symbol": "es.f",
        "asset_class": AssetClass.futures,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.25,
        "contract_size": 50,
    },
    {
        "symbol": "CL",
        "name": "WTI原油期货",
        "yfinance_symbol": "cl.f",
        "asset_class": AssetClass.futures,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1000,
    },
    # 美股 Magnificent 7
    {
        "symbol": "AAPL",
        "name": "苹果 Apple",
        "yfinance_symbol": "AAPL",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "MSFT",
        "name": "微软 Microsoft",
        "yfinance_symbol": "MSFT",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "GOOGL",
        "name": "谷歌 Alphabet",
        "yfinance_symbol": "GOOGL",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "AMZN",
        "name": "亚马逊 Amazon",
        "yfinance_symbol": "AMZN",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "NVDA",
        "name": "英伟达 NVIDIA",
        "yfinance_symbol": "NVDA",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "META",
        "name": "Meta Platforms",
        "yfinance_symbol": "META",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "TSLA",
        "name": "特斯拉 Tesla",
        "yfinance_symbol": "TSLA",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    # 美股宽基 ETF
    {
        "symbol": "SPY",
        "name": "标普500 ETF",
        "yfinance_symbol": "SPY",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
    {
        "symbol": "QQQ",
        "name": "纳斯达克100 ETF",
        "yfinance_symbol": "QQQ",
        "asset_class": AssetClass.equity,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.01,
        "contract_size": 1,
    },
]


async def seed_instruments(session: AsyncSession) -> int:
    """按 symbol 幂等补全品种（已有库也会插入缺失项）。"""
    result = await session.execute(select(Instrument.symbol))
    existing_slugs = {row[0] for row in result.all()}
    added = 0
    for item in DEFAULT_INSTRUMENTS:
        if item["symbol"] in existing_slugs:
            continue
        session.add(Instrument(**item))
        added += 1
    if added:
        await session.commit()
    return added


async def seed_strategies(session: AsyncSession) -> None:
    """按 slug 幂等写入公共预置策略，缺的补上。"""
    existing = await session.execute(select(StrategyDefinition.slug))
    existing_slugs = {row[0] for row in existing.all()}
    has_default = await session.execute(
        select(StrategyDefinition).where(StrategyDefinition.is_default.is_(True)).limit(1)
    )
    need_default = has_default.scalar_one_or_none() is None

    added = 0
    for preset in PRESET_STRATEGIES:
        slug = preset["slug"]
        if slug in existing_slugs:
            continue
        is_default = preset.get("is_default", False) and need_default
        if is_default:
            await clear_default_flag(session)
            need_default = False
        params = validate_params(preset["strategy_type"], preset["params"])
        session.add(
            StrategyDefinition(
                slug=slug,
                name=preset["name"],
                description=preset.get("description", ""),
                strategy_type=preset["strategy_type"],
                params=params,
                is_active=True,
                is_default=is_default,
            )
        )
        added += 1

    if added:
        await session.commit()
