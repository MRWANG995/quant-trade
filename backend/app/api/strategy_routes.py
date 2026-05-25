from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_auth_if_enabled
from app.database import get_db
from app.llm import LLMError, get_llm_provider
from app.models.entities import StrategyDefinition
from app.schemas import StrategyCreate, StrategyOut, StrategyUpdate
from app.strategies.dsl import DSL_CAPABILITIES, explain_dsl_human, validate_dsl
from app.strategies.dsl.spec import DSLValidationError
from app.strategies.presets import PRESET_STRATEGIES
from app.strategies.registry import list_strategy_types, validate_params
from app.seed import seed_strategies
from app.strategies.service import create_strategy, update_strategy

router = APIRouter(
    prefix="/api/strategies",
    tags=["strategies"],
    dependencies=[Depends(require_auth_if_enabled)],
)


def _to_out(st: StrategyDefinition) -> StrategyOut:
    return StrategyOut.model_validate(st)


@router.get("/types")
async def strategy_types():
    return list_strategy_types()


@router.get("/presets")
async def list_presets():
    """公共策略模板列表（用于参考，非数据库记录）。"""
    return PRESET_STRATEGIES


@router.post("/seed-presets")
async def seed_presets_api(session: AsyncSession = Depends(get_db)):
    """将缺失的公共预置策略写入数据库。"""
    before = await session.execute(select(StrategyDefinition))
    count_before = len(before.scalars().all())
    await seed_strategies(session)
    after = await session.execute(select(StrategyDefinition).order_by(StrategyDefinition.id))
    items = after.scalars().all()
    return {
        "status": "ok",
        "added": len(items) - count_before,
        "total": len(items),
        "strategies": [_to_out(s) for s in items],
    }


@router.get("", response_model=list[StrategyOut])
async def list_strategies(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(StrategyDefinition).order_by(
            StrategyDefinition.is_default.desc(),
            StrategyDefinition.id,
        )
    )
    return [_to_out(s) for s in result.scalars().all()]


@router.get("/{strategy_id}", response_model=StrategyOut)
async def get_strategy_detail(strategy_id: int, session: AsyncSession = Depends(get_db)):
    st = await session.get(StrategyDefinition, strategy_id)
    if not st:
        raise HTTPException(404, "策略不存在")
    return _to_out(st)


@router.post("", response_model=StrategyOut)
async def create_strategy_api(body: StrategyCreate, session: AsyncSession = Depends(get_db)):
    existing = await session.execute(
        select(StrategyDefinition).where(StrategyDefinition.slug == body.slug.strip().lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "slug 已存在")
    try:
        st = await create_strategy(
            session,
            slug=body.slug,
            name=body.name,
            strategy_type=body.strategy_type,
            params=body.params,
            description=body.description,
            is_default=body.is_default,
        )
        await session.commit()
        await session.refresh(st)
        return _to_out(st)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{strategy_id}", response_model=StrategyOut)
async def update_strategy_api(
    strategy_id: int,
    body: StrategyUpdate,
    session: AsyncSession = Depends(get_db),
):
    st = await session.get(StrategyDefinition, strategy_id)
    if not st:
        raise HTTPException(404, "策略不存在")
    try:
        st = await update_strategy(
            session,
            st,
            name=body.name,
            description=body.description,
            strategy_type=body.strategy_type,
            params=body.params,
            is_active=body.is_active,
            is_default=body.is_default,
        )
        await session.commit()
        await session.refresh(st)
        return _to_out(st)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{strategy_id}")
async def delete_strategy_api(strategy_id: int, session: AsyncSession = Depends(get_db)):
    st = await session.get(StrategyDefinition, strategy_id)
    if not st:
        raise HTTPException(404, "策略不存在")
    if st.is_default:
        raise HTTPException(400, "不能删除默认策略，请先指定其他策略为默认")
    await session.delete(st)
    await session.commit()
    return {"status": "ok"}


# ----------------- LLM 对话生成 -----------------

DSL_SYSTEM_PROMPT = """你是量化交易策略助手，根据用户的自然语言描述输出一份可执行的 DSL JSON。

【硬性约束】只能用下列指标与运算符，不能引入未列出的任何东西：

- 行情字段（无参数）：close, open, high, low, volume
- 带周期的指标（period 必为 1..400 的整数）：sma, ema, rsi, atr, roc, highest, lowest, bb_middle
- 布林带上/下轨（必须含 std_dev，2..10 范围的浮点）：bb_upper, bb_lower
- MACD 三条线（必须含 fast/slow/signal，2..100 整数且 fast<slow）：macd_line, macd_signal, macd_hist

数值比较运算符：lt, lte, gt, gte, eq, neq
交叉运算符（基于前后两根 bar）：crosses_above, crosses_below
布尔组合：all_of(数组，逻辑与), any_of(数组，逻辑或), not

【输出 JSON 严格结构】：
{
  "name": "中文策略短名（≤30 字符）",
  "description": "1-2 句话说明思路",
  "side_mode": "long_only" | "short_only" | "both",
  "entries": [
    {"side": "long" | "short", "when": <bool-expr>, "comment": "<这条规则的中文注释>"}
  ],
  "exits": [
    {"when": <bool-expr>, "comment": "<出场原因>"}
  ]
}

bool-expr 节点之一：
  {"op": "lt|lte|gt|gte|eq|neq|crosses_above|crosses_below", "left": <num-expr>, "right": <num-expr>}
  {"all_of": [<bool-expr>, ...]}
  {"any_of": [<bool-expr>, ...]}
  {"not": <bool-expr>}

num-expr 节点之一：
  {"const": <number>}
  {"indicator": "close|open|high|low|volume"}
  {"indicator": "sma|ema|rsi|atr|roc|highest|lowest|bb_middle", "period": <int>}
  {"indicator": "bb_upper|bb_lower", "period": <int>, "std_dev": <float>}
  {"indicator": "macd_line|macd_signal|macd_hist", "fast": <int>, "slow": <int>, "signal": <int>}

【设计原则】：
- 至少给出 1 条 entries 与 1 条 exits（exits 可选但强烈建议提供，否则只能反向信号止损）
- 入场条件要有意义：纯随机或参数极端的条件应拒绝并解释
- 周期推荐：短线 5-20、中线 20-60、长线 60-200
- 仅输出最终 JSON，不要包裹 markdown 代码块、不要解释

【示例】用户说"RSI 超卖反转，但要在中长期均线上方才做多"：
{
  "name": "RSI 超卖反转 + 趋势过滤",
  "description": "RSI(14) 跌破 30 后回升，同时 close 在 SMA(50) 之上才做多；RSI 进入超买区出场。",
  "side_mode": "long_only",
  "entries": [
    {"side": "long", "when": {"all_of": [
      {"op": "crosses_above", "left": {"indicator": "rsi", "period": 14}, "right": {"const": 30}},
      {"op": "gt", "left": {"indicator": "close"}, "right": {"indicator": "sma", "period": 50}}
    ]}, "comment": "RSI 上穿 30 且趋势多头"}
  ],
  "exits": [
    {"when": {"op": "gt", "left": {"indicator": "rsi", "period": 14}, "right": {"const": 70}}, "comment": "RSI 超买"}
  ]
}
"""


class GenerateStrategyRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    temperature: float = 0.4


class GenerateStrategyResponse(BaseModel):
    dsl: dict[str, Any]
    explain: dict[str, Any]
    raw_text: str
    model: str
    provider: str
    usage: Optional[dict[str, Any]] = None


@router.get("/dsl/capabilities")
async def dsl_capabilities():
    """前端 / 调试用：列出 DSL 支持的全部指标与运算符。"""
    return DSL_CAPABILITIES


class ExplainDslRequest(BaseModel):
    dsl: dict[str, Any]


@router.post("/dsl/explain")
async def explain_dsl(body: ExplainDslRequest):
    try:
        validated = validate_dsl(body.dsl)
    except DSLValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"dsl": validated, "explain": explain_dsl_human(validated)}


@router.post("/generate", response_model=GenerateStrategyResponse)
async def generate_strategy(body: GenerateStrategyRequest):
    """让 LLM 根据自然语言描述生成 DSL 策略。"""
    try:
        provider = get_llm_provider()
    except LLMError as exc:
        raise HTTPException(503, f"LLM 未配置：{exc}") from exc

    try:
        result = await provider.generate_json(
            system=DSL_SYSTEM_PROMPT,
            user=body.prompt,
            temperature=body.temperature,
        )
    except LLMError as exc:
        raise HTTPException(502, f"LLM 调用失败：{exc}") from exc

    try:
        validated = validate_dsl(result.parsed)
    except DSLValidationError as exc:
        raise HTTPException(
            422,
            {
                "message": f"LLM 产出的 DSL 不合法：{exc}",
                "raw_text": result.text,
            },
        ) from exc

    return GenerateStrategyResponse(
        dsl=validated,
        explain=explain_dsl_human(validated),
        raw_text=result.text,
        model=result.model,
        provider=result.provider,
        usage=result.usage,
    )


class SaveDslRequest(BaseModel):
    dsl: dict[str, Any]
    slug: Optional[str] = None
    description: Optional[str] = None
    llm_prompt: Optional[str] = None
    llm_model: Optional[str] = None
    is_default: bool = False


def _slugify(name: str) -> str:
    import re

    base = re.sub(r"[^a-z0-9_]+", "_", name.lower())
    base = base.strip("_") or "llm_strategy"
    return f"llm_{base}"[:64]


@router.post("/from-dsl", response_model=StrategyOut)
async def save_dsl_as_strategy(
    body: SaveDslRequest, session: AsyncSession = Depends(get_db)
):
    try:
        validated = validate_dsl(body.dsl)
    except DSLValidationError as exc:
        raise HTTPException(400, str(exc)) from exc

    slug = (body.slug or _slugify(validated["name"])).strip().lower()
    # 自动加后缀避免冲突
    suffix = 0
    final_slug = slug
    while True:
        existing = await session.execute(
            select(StrategyDefinition).where(StrategyDefinition.slug == final_slug)
        )
        if not existing.scalar_one_or_none():
            break
        suffix += 1
        final_slug = f"{slug}_{suffix}"

    params: dict[str, Any] = {"dsl": validated}
    if body.llm_prompt:
        params["llm_prompt"] = body.llm_prompt
    if body.llm_model:
        params["llm_model"] = body.llm_model

    try:
        st = await create_strategy(
            session,
            slug=final_slug,
            name=validated["name"],
            strategy_type="llm_dsl",
            params=params,
            description=body.description or validated.get("description") or "",
            is_default=body.is_default,
        )
        await session.commit()
        await session.refresh(st)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return _to_out(st)
