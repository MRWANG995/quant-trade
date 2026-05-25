"""把 DSL 节点编译成 pandas.Series。结果按 (indicator, params) 缓存。"""

from __future__ import annotations

import pandas as pd

from app.strategies.dsl.spec import (
    NUMERIC_INDICATORS_BB,
    NUMERIC_INDICATORS_MACD,
    NUMERIC_INDICATORS_NO_PARAM,
    NUMERIC_INDICATORS_PERIOD,
)


def _sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def _ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def _macd_lines(close: pd.Series, fast: int, slow: int, signal: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist


def _node_key(node: dict) -> str:
    """规范化节点为缓存键。"""
    if "const" in node:
        return f"const:{node['const']}"
    ind = node["indicator"]
    if ind in NUMERIC_INDICATORS_NO_PARAM:
        return f"ind:{ind}"
    if ind in NUMERIC_INDICATORS_PERIOD:
        return f"ind:{ind}:{node['period']}"
    if ind in NUMERIC_INDICATORS_BB:
        return f"ind:{ind}:{node['period']}:{node['std_dev']}"
    if ind in NUMERIC_INDICATORS_MACD:
        return f"ind:{ind}:{node['fast']}:{node['slow']}:{node['signal']}"
    raise ValueError(f"未知 indicator: {ind}")


def compute_numeric(node: dict, df: pd.DataFrame, cache: dict[str, pd.Series]) -> pd.Series:
    """计算一个数值表达式节点对应的 Series。结果按节点缓存。"""
    key = _node_key(node)
    if key in cache:
        return cache[key]

    if "const" in node:
        val = float(node["const"])
        series = pd.Series([val] * len(df), index=df.index, dtype=float)
        cache[key] = series
        return series

    ind = node["indicator"]
    if ind in NUMERIC_INDICATORS_NO_PARAM:
        series = df[ind].astype(float)
    elif ind == "sma":
        series = _sma(df["close"], int(node["period"]))
    elif ind == "ema":
        series = _ema(df["close"], int(node["period"]))
    elif ind == "rsi":
        series = _rsi(df["close"], int(node["period"]))
    elif ind == "atr":
        series = _atr(df, int(node["period"]))
    elif ind == "roc":
        period = int(node["period"])
        series = df["close"].pct_change(period) * 100
    elif ind == "highest":
        series = df["high"].rolling(int(node["period"])).max()
    elif ind == "lowest":
        series = df["low"].rolling(int(node["period"])).min()
    elif ind == "bb_middle":
        series = _sma(df["close"], int(node["period"]))
    elif ind == "bb_upper":
        period = int(node["period"])
        k = float(node["std_dev"])
        mid = _sma(df["close"], period)
        sd = df["close"].rolling(period).std(ddof=0)
        series = mid + k * sd
    elif ind == "bb_lower":
        period = int(node["period"])
        k = float(node["std_dev"])
        mid = _sma(df["close"], period)
        sd = df["close"].rolling(period).std(ddof=0)
        series = mid - k * sd
    elif ind == "macd_line":
        line, _, _ = _macd_lines(df["close"], int(node["fast"]), int(node["slow"]), int(node["signal"]))
        series = line
    elif ind == "macd_signal":
        _, sig, _ = _macd_lines(df["close"], int(node["fast"]), int(node["slow"]), int(node["signal"]))
        series = sig
    elif ind == "macd_hist":
        _, _, hist = _macd_lines(df["close"], int(node["fast"]), int(node["slow"]), int(node["signal"]))
        series = hist
    else:
        raise ValueError(f"未实现 indicator: {ind}")

    cache[key] = series
    return series


def compute_bool(node: dict, df: pd.DataFrame, cache: dict[str, pd.Series]) -> pd.Series:
    if "op" in node:
        left = compute_numeric(node["left"], df, cache)
        right = compute_numeric(node["right"], df, cache)
        op = node["op"]
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "eq":
            return left == right
        if op == "neq":
            return left != right
        if op == "crosses_above":
            # 前一根 left <= right，本根 left > right
            return (left.shift(1) <= right.shift(1)) & (left > right)
        if op == "crosses_below":
            return (left.shift(1) >= right.shift(1)) & (left < right)
        raise ValueError(f"未知 op: {op}")
    if "all_of" in node:
        result: pd.Series | None = None
        for child in node["all_of"]:
            s = compute_bool(child, df, cache)
            result = s if result is None else (result & s)
        return result if result is not None else pd.Series(False, index=df.index)
    if "any_of" in node:
        result: pd.Series | None = None
        for child in node["any_of"]:
            s = compute_bool(child, df, cache)
            result = s if result is None else (result | s)
        return result if result is not None else pd.Series(False, index=df.index)
    if "not" in node:
        inner = compute_bool(node["not"], df, cache)
        return ~inner
    raise ValueError("Boolean 节点形式无效")
