"""LLM 策略 DSL 的语法、校验与人类可读化。

DSL 是一个 dict：
{
  "name": str,
  "description": str (optional),
  "side_mode": "long_only" | "short_only" | "both",
  "entries": [ { "side": "long"|"short", "when": <expr>, "comment": str? }, ... ],
  "exits":   [ { "when": <expr>, "comment": str? }, ... ]      # 可空
}

<expr> 节点形式之一：
  数值：
    { "const": float }
    { "indicator": "close"|"open"|"high"|"low"|"volume" }
    { "indicator": "sma"|"ema"|"rsi"|"atr"|"roc"|"highest"|"lowest", "period": int }
    { "indicator": "bb_upper"|"bb_lower", "period": int, "std_dev": float }
    { "indicator": "bb_middle", "period": int }
    { "indicator": "macd_line"|"macd_signal"|"macd_hist",
      "fast": int, "slow": int, "signal": int }
  布尔：
    { "op": "lt"|"lte"|"gt"|"gte"|"eq"|"neq"
            |"crosses_above"|"crosses_below",
      "left": <expr>, "right": <expr> }
    { "all_of": [ <expr>, ... ] }
    { "any_of": [ <expr>, ... ] }
    { "not": <expr> }
"""

from __future__ import annotations

from typing import Any

NUMERIC_INDICATORS_NO_PARAM = {"close", "open", "high", "low", "volume"}
NUMERIC_INDICATORS_PERIOD = {"sma", "ema", "rsi", "atr", "roc", "highest", "lowest", "bb_middle"}
NUMERIC_INDICATORS_BB = {"bb_upper", "bb_lower"}
NUMERIC_INDICATORS_MACD = {"macd_line", "macd_signal", "macd_hist"}

ALL_INDICATORS = (
    NUMERIC_INDICATORS_NO_PARAM
    | NUMERIC_INDICATORS_PERIOD
    | NUMERIC_INDICATORS_BB
    | NUMERIC_INDICATORS_MACD
)

COMPARISON_OPS = {"lt", "lte", "gt", "gte", "eq", "neq"}
CROSS_OPS = {"crosses_above", "crosses_below"}
ALL_BIN_OPS = COMPARISON_OPS | CROSS_OPS

MAX_NODES = 200  # 单个表达式树最大节点数，防爆
MAX_PERIOD = 400


class DSLValidationError(ValueError):
    """DSL 校验失败。"""


# ---------- 校验 ----------

def _is_numeric_expr(node: dict) -> bool:
    if "const" in node:
        return True
    if "indicator" in node:
        return True
    return False


def _is_bool_expr(node: dict) -> bool:
    return "op" in node or "all_of" in node or "any_of" in node or "not" in node


def _validate_numeric(node: Any, path: str, counter: list[int]) -> None:
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise DSLValidationError(f"{path}: 表达式过于复杂（节点数超过 {MAX_NODES}）")
    if not isinstance(node, dict):
        raise DSLValidationError(f"{path}: 应为对象")
    if "const" in node:
        if not isinstance(node["const"], (int, float)):
            raise DSLValidationError(f"{path}.const 必须是数字")
        return
    if "indicator" in node:
        ind = node["indicator"]
        if ind not in ALL_INDICATORS:
            raise DSLValidationError(f"{path}.indicator='{ind}' 未支持，可用：{sorted(ALL_INDICATORS)}")
        if ind in NUMERIC_INDICATORS_PERIOD:
            period = node.get("period")
            if not isinstance(period, int) or period < 1 or period > MAX_PERIOD:
                raise DSLValidationError(f"{path}.period 必须是 1..{MAX_PERIOD} 的整数")
        elif ind in NUMERIC_INDICATORS_BB:
            period = node.get("period")
            std_dev = node.get("std_dev")
            if not isinstance(period, int) or period < 2 or period > MAX_PERIOD:
                raise DSLValidationError(f"{path}.period 必须是 2..{MAX_PERIOD} 的整数")
            if not isinstance(std_dev, (int, float)) or std_dev <= 0 or std_dev > 10:
                raise DSLValidationError(f"{path}.std_dev 必须是 (0, 10] 范围的数字")
        elif ind in NUMERIC_INDICATORS_MACD:
            for k in ("fast", "slow", "signal"):
                v = node.get(k)
                if not isinstance(v, int) or v < 2 or v > 100:
                    raise DSLValidationError(f"{path}.{k} 必须是 2..100 的整数")
            if node["fast"] >= node["slow"]:
                raise DSLValidationError(f"{path}: MACD fast 必须小于 slow")
        return
    raise DSLValidationError(f"{path}: 必须是 const/indicator 之一")


def _validate_bool(node: Any, path: str, counter: list[int]) -> None:
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise DSLValidationError(f"{path}: 表达式过于复杂")
    if not isinstance(node, dict):
        raise DSLValidationError(f"{path}: 应为对象")
    if "op" in node:
        op = node["op"]
        if op not in ALL_BIN_OPS:
            raise DSLValidationError(
                f"{path}.op='{op}' 未支持，可用：{sorted(ALL_BIN_OPS)}"
            )
        if "left" not in node or "right" not in node:
            raise DSLValidationError(f"{path}: 二元操作需要 left 和 right")
        _validate_numeric(node["left"], f"{path}.left", counter)
        _validate_numeric(node["right"], f"{path}.right", counter)
        return
    if "all_of" in node or "any_of" in node:
        key = "all_of" if "all_of" in node else "any_of"
        items = node[key]
        if not isinstance(items, list) or not items:
            raise DSLValidationError(f"{path}.{key} 必须是非空数组")
        for i, child in enumerate(items):
            _validate_bool(child, f"{path}.{key}[{i}]", counter)
        return
    if "not" in node:
        _validate_bool(node["not"], f"{path}.not", counter)
        return
    raise DSLValidationError(f"{path}: 必须是 op/all_of/any_of/not 之一")


def validate_dsl(dsl: Any) -> dict:
    """校验 LLM 产出的 DSL，返回归一化（仅必要时改格式）的 dict。出错抛 DSLValidationError。"""
    if not isinstance(dsl, dict):
        raise DSLValidationError("DSL 顶层必须是 JSON 对象")
    name = dsl.get("name")
    if not isinstance(name, str) or not name.strip():
        raise DSLValidationError("缺少有效的 name")
    side_mode = dsl.get("side_mode", "both")
    if side_mode not in ("long_only", "short_only", "both"):
        raise DSLValidationError("side_mode 必须是 long_only|short_only|both")

    entries = dsl.get("entries")
    if not isinstance(entries, list) or not entries:
        raise DSLValidationError("entries 必须是非空数组")
    for i, ent in enumerate(entries):
        if not isinstance(ent, dict):
            raise DSLValidationError(f"entries[{i}] 必须是对象")
        side = ent.get("side")
        if side not in ("long", "short"):
            raise DSLValidationError(f"entries[{i}].side 必须是 long|short")
        if side_mode == "long_only" and side != "long":
            raise DSLValidationError(f"entries[{i}].side 与 side_mode=long_only 冲突")
        if side_mode == "short_only" and side != "short":
            raise DSLValidationError(f"entries[{i}].side 与 side_mode=short_only 冲突")
        if "when" not in ent:
            raise DSLValidationError(f"entries[{i}].when 缺失")
        _validate_bool(ent["when"], f"entries[{i}].when", [0])

    exits = dsl.get("exits") or []
    if exits and not isinstance(exits, list):
        raise DSLValidationError("exits 必须是数组")
    for i, ex in enumerate(exits):
        if not isinstance(ex, dict) or "when" not in ex:
            raise DSLValidationError(f"exits[{i}].when 缺失")
        _validate_bool(ex["when"], f"exits[{i}].when", [0])

    return {
        "name": name.strip(),
        "description": (dsl.get("description") or "").strip(),
        "side_mode": side_mode,
        "entries": entries,
        "exits": exits,
    }


# ---------- 估算最少需要多少条 bar ----------

def collect_max_period(node: Any, _max: int = 0) -> int:
    if not isinstance(node, dict):
        return _max
    for k in ("period", "slow", "signal"):
        v = node.get(k)
        if isinstance(v, int) and v > _max:
            _max = v
    for k in ("left", "right", "not"):
        if k in node:
            _max = collect_max_period(node[k], _max)
    for k in ("all_of", "any_of"):
        if k in node:
            for child in node[k]:
                _max = collect_max_period(child, _max)
    return _max


def dsl_max_lookback(dsl: dict) -> int:
    m = 0
    for ent in dsl.get("entries", []):
        m = collect_max_period(ent.get("when"), m)
    for ex in dsl.get("exits") or []:
        m = collect_max_period(ex.get("when"), m)
    return m


# ---------- 人类可读化 ----------

_OP_LABELS = {
    "lt": "<",
    "lte": "≤",
    "gt": ">",
    "gte": "≥",
    "eq": "=",
    "neq": "≠",
    "crosses_above": "上穿",
    "crosses_below": "下穿",
}


def _explain_numeric(node: dict) -> str:
    if "const" in node:
        return str(node["const"])
    if "indicator" in node:
        ind = node["indicator"]
        if ind in NUMERIC_INDICATORS_NO_PARAM:
            return {"close": "Close", "open": "Open", "high": "High", "low": "Low", "volume": "Volume"}[ind]
        if ind in NUMERIC_INDICATORS_PERIOD:
            return f"{ind.upper()}({node['period']})"
        if ind in NUMERIC_INDICATORS_BB:
            label = "上轨" if ind == "bb_upper" else "下轨"
            return f"BB{label}({node['period']},{node['std_dev']}σ)"
        if ind in NUMERIC_INDICATORS_MACD:
            label = {"macd_line": "MACD", "macd_signal": "Signal", "macd_hist": "Hist"}[ind]
            return f"{label}({node['fast']},{node['slow']},{node['signal']})"
    return "?"


def _explain_bool(node: dict) -> str:
    if "op" in node:
        op = node["op"]
        left = _explain_numeric(node["left"])
        right = _explain_numeric(node["right"])
        if op in ("crosses_above", "crosses_below"):
            return f"{left} {_OP_LABELS[op]} {right}"
        return f"{left} {_OP_LABELS[op]} {right}"
    if "all_of" in node:
        return "(" + " 且 ".join(_explain_bool(c) for c in node["all_of"]) + ")"
    if "any_of" in node:
        return "(" + " 或 ".join(_explain_bool(c) for c in node["any_of"]) + ")"
    if "not" in node:
        return f"非({_explain_bool(node['not'])})"
    return "?"


def explain_dsl_human(dsl: dict) -> dict:
    """把 DSL 翻译为中文条件描述，供前端在保存前向用户展示。"""
    entries_text = []
    for ent in dsl.get("entries", []):
        side = "做多" if ent["side"] == "long" else "做空"
        cond = _explain_bool(ent["when"])
        comment = ent.get("comment") or ""
        entries_text.append({"side": side, "condition": cond, "comment": comment})
    exits_text = []
    for ex in dsl.get("exits") or []:
        exits_text.append(
            {"condition": _explain_bool(ex["when"]), "comment": ex.get("comment") or ""}
        )
    return {
        "name": dsl.get("name", ""),
        "description": dsl.get("description", ""),
        "side_mode": dsl.get("side_mode", "both"),
        "entries": entries_text,
        "exits": exits_text,
    }


# ---------- 给前端 / LLM 用的能力清单 ----------

DSL_CAPABILITIES: dict[str, Any] = {
    "indicators": {
        "bar_fields": sorted(NUMERIC_INDICATORS_NO_PARAM),
        "period_indicators": sorted(NUMERIC_INDICATORS_PERIOD),
        "bollinger": sorted(NUMERIC_INDICATORS_BB),
        "macd": sorted(NUMERIC_INDICATORS_MACD),
    },
    "comparison_ops": sorted(COMPARISON_OPS),
    "cross_ops": sorted(CROSS_OPS),
    "bool_ops": ["all_of", "any_of", "not"],
    "max_nodes": MAX_NODES,
    "max_period": MAX_PERIOD,
}
