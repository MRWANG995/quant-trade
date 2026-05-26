from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AssetClass, BrokerHint, Instrument, StrategyDefinition
from app.strategies.presets import PRESET_STRATEGIES
from app.strategies.registry import validate_params
from app.strategies.service import clear_default_flag

# symbol, 中文名, yfinance_symbol（库内字段）, Stooq/展示用
DEFAULT_INSTRUMENTS = [
    # 加密货币（走 Binance 公共 API）
    {
        "symbol": "BTC",
        "name": "比特币 Bitcoin",
        "yfinance_symbol": "BTCUSDT",  # 这里直接是 Binance 的 trading pair
        "asset_class": AssetClass.crypto,
        "broker_hint": BrokerHint.ib,   # 暂用占位，等真有加密 broker 适配器再换
        "pip_value": 0.01,
        "contract_size": 1,
    },
    # 现货黄金
    {
        "symbol": "XAUUSD",
        "name": "现货黄金",
        "yfinance_symbol": "xauusd",
        "asset_class": AssetClass.metal,
        "broker_hint": BrokerHint.ib,
        "pip_value": 0.1,
        "contract_size": 100,
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
