from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import StrategyDefinition
from app.strategies.registry import validate_params


async def resolve_composite_params(
    session: AsyncSession, params: dict
) -> dict:
    """组合策略：把 children 里的 strategy_id 替换为完整的子策略定义快照。

    返回的 dict 多出 _resolved_children 字段供 composite.scan 使用；
    原始 children 保持不变，方便编辑/序列化。
    """
    children = (params or {}).get("children") or []
    resolved: list[dict] = []
    for c in children:
        sid = c.get("strategy_id")
        weight = float(c.get("weight", 0.0))
        child = await session.get(StrategyDefinition, sid)
        if not child or not child.is_active:
            raise ValueError(f"子策略 #{sid} 不存在或已停用")
        if child.strategy_type == "composite":
            raise ValueError("组合策略不能嵌套引用另一个组合策略")
        resolved.append(
            {
                "strategy_id": sid,
                "strategy_type": child.strategy_type,
                "name": child.name,
                "params": child.params,
                "weight": weight,
            }
        )
    return {**params, "_resolved_children": resolved}


async def get_strategy(
    session: AsyncSession, strategy_id: Optional[int] = None
) -> StrategyDefinition:
    if strategy_id:
        st = await session.get(StrategyDefinition, strategy_id)
        if not st or not st.is_active:
            raise ValueError("策略不存在或已停用")
        return st
    result = await session.execute(
        select(StrategyDefinition)
        .where(StrategyDefinition.is_active.is_(True), StrategyDefinition.is_default.is_(True))
        .limit(1)
    )
    st = result.scalar_one_or_none()
    if st:
        return st
    result = await session.execute(
        select(StrategyDefinition)
        .where(StrategyDefinition.is_active.is_(True))
        .order_by(StrategyDefinition.id)
        .limit(1)
    )
    st = result.scalar_one_or_none()
    if not st:
        raise ValueError("请先在「策略管理」中创建策略")
    return st


async def clear_default_flag(session: AsyncSession) -> None:
    await session.execute(
        update(StrategyDefinition).values(is_default=False)
    )


async def create_strategy(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    strategy_type: str,
    params: dict,
    description: str = "",
    is_default: bool = False,
) -> StrategyDefinition:
    params = validate_params(strategy_type, params)
    if is_default:
        await clear_default_flag(session)
    st = StrategyDefinition(
        slug=slug.strip().lower().replace(" ", "_"),
        name=name,
        description=description,
        strategy_type=strategy_type,
        params=params,
        is_default=is_default,
    )
    session.add(st)
    await session.flush()
    return st


async def update_strategy(
    session: AsyncSession,
    strategy: StrategyDefinition,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    strategy_type: Optional[str] = None,
    params: Optional[dict] = None,
    is_active: Optional[bool] = None,
    is_default: Optional[bool] = None,
) -> StrategyDefinition:
    st_type = strategy_type or strategy.strategy_type
    if params is not None or strategy_type is not None:
        merged = {**strategy.params, **(params or {})}
        strategy.params = validate_params(st_type, merged)
    if strategy_type is not None:
        strategy.strategy_type = strategy_type
    if name is not None:
        strategy.name = name
    if description is not None:
        strategy.description = description
    if is_active is not None:
        strategy.is_active = is_active
    if is_default is not None:
        if is_default:
            await clear_default_flag(session)
        strategy.is_default = is_default
    await session.flush()
    return strategy
