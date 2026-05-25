from typing import Any, Callable, Optional

from app.strategies import agent, bollinger, composite, donchian, ma_cross, macd, macd_trend, momentum, rsi
from app.strategies.base import StrategySignal
from app.strategies.dsl import (
    dsl_latest_signal,
    dsl_min_bars_required,
    dsl_scan_historical_signals,
    validate_dsl,
)

ScanFn = Callable[[int, str, list[dict], dict], list[StrategySignal]]
LatestFn = Callable[[int, str, list[dict], dict], list[StrategySignal]]
MinBarsFn = Callable[[dict], int]

STRATEGY_TYPE_CATALOG: dict[str, dict[str, Any]] = {
    "ma_cross": {
        "label": "双均线交叉",
        "description": "快线上穿慢线做多，下穿做空",
        "param_schema": [
            {"key": "fast_ma", "label": "快线周期", "type": "int", "default": 20, "min": 2, "max": 200},
            {"key": "slow_ma", "label": "慢线周期", "type": "int", "default": 50, "min": 5, "max": 400},
        ],
    },
    "rsi": {
        "label": "RSI 超买超卖",
        "description": "RSI 脱离超卖区做多，脱离超买区做空",
        "param_schema": [
            {"key": "period", "label": "RSI 周期", "type": "int", "default": 14, "min": 2, "max": 100},
            {"key": "oversold", "label": "超卖线", "type": "float", "default": 30, "min": 5, "max": 50},
            {"key": "overbought", "label": "超买线", "type": "float", "default": 70, "min": 50, "max": 95},
        ],
    },
    "macd": {
        "label": "MACD 交叉",
        "description": "MACD 柱状线与信号线金叉/死叉",
        "param_schema": [
            {"key": "fast", "label": "快线 EMA", "type": "int", "default": 12, "min": 2, "max": 50},
            {"key": "slow", "label": "慢线 EMA", "type": "int", "default": 26, "min": 5, "max": 100},
            {"key": "signal", "label": "信号线", "type": "int", "default": 9, "min": 2, "max": 50},
        ],
    },
    "bollinger": {
        "label": "布林带均值回归",
        "description": "价格从下轨反弹做多，从上轨回落做空",
        "param_schema": [
            {"key": "period", "label": "均线周期", "type": "int", "default": 20, "min": 5, "max": 100},
            {"key": "std_dev", "label": "标准差倍数", "type": "float", "default": 2.0, "min": 0.5, "max": 4.0},
        ],
    },
    "donchian": {
        "label": "唐奇安突破（海龟）",
        "description": "收盘价突破 N 日最高做多、跌破 N 日最低做空，经典趋势跟踪",
        "param_schema": [
            {"key": "entry_period", "label": "通道周期", "type": "int", "default": 20, "min": 5, "max": 252},
        ],
    },
    "macd_trend": {
        "label": "MACD + 趋势过滤",
        "description": "MACD 金叉/死叉，且价格在中长期均线同侧，过滤震荡假信号",
        "param_schema": [
            {"key": "fast", "label": "快线 EMA", "type": "int", "default": 12, "min": 2, "max": 50},
            {"key": "slow", "label": "慢线 EMA", "type": "int", "default": 26, "min": 5, "max": 100},
            {"key": "signal", "label": "信号线", "type": "int", "default": 9, "min": 2, "max": 50},
            {"key": "trend_ma", "label": "趋势均线", "type": "int", "default": 50, "min": 20, "max": 400},
        ],
    },
    "momentum": {
        "label": "动量趋势",
        "description": "N 日收益率与趋势均线同向时入场，适合中长线趋势",
        "param_schema": [
            {"key": "lookback", "label": "动量回看(日)", "type": "int", "default": 63, "min": 10, "max": 252},
            {"key": "trend_ma", "label": "趋势均线", "type": "int", "default": 100, "min": 20, "max": 400},
            {"key": "roc_threshold", "label": "动量阈值", "type": "float", "default": 0.0, "min": 0.0, "max": 0.2},
        ],
    },
    "llm_dsl": {
        "label": "LLM 对话生成（DSL）",
        "description": "由大模型在对话中生成的策略，按 DSL JSON 解释执行；params.dsl 存储具体规则",
        "param_schema": [],  # 无可调参数；DSL 即配置
    },
    "composite": {
        "label": "组合策略（加权）",
        "description": "把多个已有策略按权重聚合：加权后净分大于 0 做多，小于 0 做空",
        "param_schema": [],  # children/weights 由专用 UI 编辑，非简单数值字段
    },
    "agent": {
        "label": "Agent 信号（LLM）",
        "description": "每日扫描时调 Gemini 分析 K 线和指标，按其输出的 side+confidence 出信号",
        "param_schema": [
            {"key": "lookback_bars", "label": "Lookback (日 K 数)", "type": "int", "default": 60, "min": 30, "max": 200},
            {"key": "min_confidence", "label": "最低置信度", "type": "float", "default": 0.6, "min": 0.0, "max": 1.0},
        ],
    },
}

_HANDLERS: dict[str, tuple[ScanFn, LatestFn, MinBarsFn]] = {
    "ma_cross": (ma_cross.scan_historical_signals, ma_cross.latest_signal, ma_cross.min_bars_required),
    "rsi": (rsi.scan_historical_signals, rsi.latest_signal, rsi.min_bars_required),
    "macd": (macd.scan_historical_signals, macd.latest_signal, macd.min_bars_required),
    "bollinger": (bollinger.scan_historical_signals, bollinger.latest_signal, bollinger.min_bars_required),
    "donchian": (donchian.scan_historical_signals, donchian.latest_signal, donchian.min_bars_required),
    "macd_trend": (macd_trend.scan_historical_signals, macd_trend.latest_signal, macd_trend.min_bars_required),
    "momentum": (momentum.scan_historical_signals, momentum.latest_signal, momentum.min_bars_required),
    "llm_dsl": (dsl_scan_historical_signals, dsl_latest_signal, dsl_min_bars_required),
    "composite": (
        composite.scan_historical_signals,
        composite.latest_signal,
        composite.min_bars_required,
    ),
    "agent": (
        agent.scan_historical_signals,
        agent.latest_signal,
        agent.min_bars_required,
    ),
}


def list_strategy_types() -> list[dict[str, Any]]:
    return [
        {"type": key, **{k: v for k, v in meta.items() if k != "param_schema"}, "param_schema": meta["param_schema"]}
        for key, meta in STRATEGY_TYPE_CATALOG.items()
    ]


def validate_params(strategy_type: str, params: dict) -> dict:
    if strategy_type not in STRATEGY_TYPE_CATALOG:
        raise ValueError(f"未知策略类型: {strategy_type}")
    if strategy_type == "llm_dsl":
        dsl = params.get("dsl") if isinstance(params, dict) else None
        if not dsl:
            raise ValueError("llm_dsl 策略需要 params.dsl")
        validated = validate_dsl(dsl)
        # 保留 LLM 元数据（model/prompt/...）方便审计
        meta = {k: v for k, v in (params or {}).items() if k not in ("dsl",)}
        return {"dsl": validated, **meta}
    if strategy_type == "agent":
        # agent 有可调数值（lookback、min_confidence），加上自由文本 system_prompt
        prompt = str((params or {}).get("system_prompt", "")).strip()
        if not prompt:
            raise ValueError("agent 策略需要 params.system_prompt（系统提示词）")
        schema = STRATEGY_TYPE_CATALOG[strategy_type]["param_schema"]
        merged: dict = {"system_prompt": prompt}
        for field in schema:
            key = field["key"]
            val = (params or {}).get(key, field["default"])
            if field["type"] == "int":
                val = int(val)
            elif field["type"] == "float":
                val = float(val)
            if "min" in field and val < field["min"]:
                raise ValueError(f"{field['label']} 不能小于 {field['min']}")
            if "max" in field and val > field["max"]:
                raise ValueError(f"{field['label']} 不能大于 {field['max']}")
            merged[key] = val
        return merged
    if strategy_type == "composite":
        mode = (params or {}).get("mode", "weighted")
        if mode != "weighted":
            raise ValueError(f"暂不支持的组合模式: {mode}（仅 weighted 可用）")
        raw_children = (params or {}).get("children") or []
        if not isinstance(raw_children, list) or not raw_children:
            raise ValueError("composite 策略需要至少一个子策略：params.children")
        cleaned: list[dict] = []
        for c in raw_children:
            sid = c.get("strategy_id") if isinstance(c, dict) else None
            if not isinstance(sid, int):
                raise ValueError("每个子策略需 strategy_id（整数）")
            try:
                weight = float(c.get("weight", 0.0))
            except (TypeError, ValueError) as exc:
                raise ValueError("子策略 weight 必须是数字") from exc
            if weight <= 0:
                raise ValueError(f"子策略 #{sid} 权重必须 > 0")
            cleaned.append({"strategy_id": sid, "weight": weight})
        total = sum(c["weight"] for c in cleaned)
        if total <= 0:
            raise ValueError("子策略权重总和必须 > 0")
        return {"mode": "weighted", "children": cleaned}
    schema = STRATEGY_TYPE_CATALOG[strategy_type]["param_schema"]
    merged = {}
    for field in schema:
        key = field["key"]
        val = params.get(key, field["default"])
        if field["type"] == "int":
            val = int(val)
            if "min" in field and val < field["min"]:
                raise ValueError(f"{field['label']} 不能小于 {field['min']}")
            if "max" in field and val > field["max"]:
                raise ValueError(f"{field['label']} 不能大于 {field['max']}")
        elif field["type"] == "float":
            val = float(val)
            if "min" in field and val < field["min"]:
                raise ValueError(f"{field['label']} 不能小于 {field['min']}")
            if "max" in field and val > field["max"]:
                raise ValueError(f"{field['label']} 不能大于 {field['max']}")
        merged[key] = val
    if strategy_type == "ma_cross":
        ma_cross._params(merged)
    elif strategy_type == "rsi":
        rsi._params(merged)
    elif strategy_type == "macd":
        macd._params(merged)
    elif strategy_type == "bollinger":
        bollinger._params(merged)
    elif strategy_type == "donchian":
        donchian._params(merged)
    elif strategy_type == "macd_trend":
        macd_trend._params(merged)
    elif strategy_type == "momentum":
        momentum._params(merged)
    return merged


def scan_historical_signals(
    strategy_type: str,
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    handler = _HANDLERS.get(strategy_type)
    if not handler:
        raise ValueError(f"未注册的策略类型: {strategy_type}")
    return handler[0](instrument_id, symbol, bars, params)


def latest_signals(
    strategy_type: str,
    instrument_id: int,
    symbol: str,
    bars: list[dict],
    params: dict,
) -> list[StrategySignal]:
    handler = _HANDLERS.get(strategy_type)
    if not handler:
        raise ValueError(f"未注册的策略类型: {strategy_type}")
    return handler[1](instrument_id, symbol, bars, params)


def min_bars_required(strategy_type: str, params: dict) -> int:
    handler = _HANDLERS.get(strategy_type)
    if not handler:
        return 60
    return handler[2](params)
