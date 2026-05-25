"""回测指标计算：Sharpe/Sortino/Calmar/月度收益/水下曲线/交易统计/分品种贡献。

输入仅依赖 equity_curve(list[{date, equity}]) 与 trades(list[dict])，所以
历史回测记录在没有 metrics 字段时也可以即时重算。
"""

from __future__ import annotations

import math
from datetime import date as date_cls
from datetime import datetime
from typing import Any, Iterable

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25


def _to_date(value: Any) -> date_cls | None:
    if isinstance(value, date_cls):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None


def _daily_returns(
    equity_curve: list[dict[str, Any]], initial_capital: float
) -> list[float]:
    rets: list[float] = []
    prev = initial_capital
    for point in equity_curve:
        equity = float(point.get("equity", prev))
        if prev > 0:
            rets.append(equity / prev - 1.0)
        else:
            rets.append(0.0)
        prev = equity
    return rets


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _drawdown_series(
    equity_curve: list[dict[str, Any]], initial_capital: float
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    peak = initial_capital
    for point in equity_curve:
        equity = float(point.get("equity", peak))
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak if peak > 0 else 0.0
        series.append(
            {
                "date": point.get("date"),
                "drawdown_pct": round(dd * 100, 4),
                "equity": round(equity, 2),
                "peak": round(peak, 2),
            }
        )
    return series


def _longest_underwater_days(
    drawdown_series: list[dict[str, Any]],
) -> tuple[int, str | None, str | None]:
    longest = 0
    cur_start: str | None = None
    cur_len = 0
    best_start: str | None = None
    best_end: str | None = None
    for point in drawdown_series:
        if point["drawdown_pct"] < 0:
            if cur_start is None:
                cur_start = point["date"]
                cur_len = 1
            else:
                cur_len += 1
            if cur_len > longest:
                longest = cur_len
                best_start = cur_start
                best_end = point["date"]
        else:
            cur_start = None
            cur_len = 0
    return longest, best_start, best_end


def _monthly_returns(
    equity_curve: list[dict[str, Any]], initial_capital: float
) -> list[dict[str, Any]]:
    if not equity_curve:
        return []
    months: dict[tuple[int, int], dict[str, Any]] = {}
    for point in equity_curve:
        d = _to_date(point.get("date"))
        if d is None:
            continue
        key = (d.year, d.month)
        bucket = months.setdefault(
            key, {"year": d.year, "month": d.month, "first": None, "last": None}
        )
        equity = float(point.get("equity", initial_capital))
        if bucket["first"] is None:
            bucket["first"] = equity
        bucket["last"] = equity
        bucket["last_date"] = d.isoformat()

    sorted_keys = sorted(months.keys())
    result: list[dict[str, Any]] = []
    prev_close = initial_capital
    for key in sorted_keys:
        bucket = months[key]
        last = float(bucket["last"])
        ret = (last / prev_close - 1.0) if prev_close > 0 else 0.0
        result.append(
            {
                "year": bucket["year"],
                "month": bucket["month"],
                "return_pct": round(ret * 100, 3),
                "equity": round(last, 2),
            }
        )
        prev_close = last
    return result


def _trade_stats(trades: Iterable[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t.get("pnl") is not None and t.get("exit_date")]
    wins = [t for t in closed if (t.get("pnl") or 0) > 0]
    losses = [t for t in closed if (t.get("pnl") or 0) < 0]
    total_win = sum(float(t["pnl"]) for t in wins)
    total_loss = sum(float(t["pnl"]) for t in losses)
    n = len(closed)

    holding_days: list[float] = []
    for t in closed:
        ed = _to_date(t.get("entry_date"))
        xd = _to_date(t.get("exit_date"))
        if ed and xd:
            holding_days.append(max((xd - ed).days, 0))

    return {
        "closed_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(len(wins) / n * 100, 2) if n else 0.0,
        "profit_factor": round(total_win / abs(total_loss), 3)
        if total_loss < 0
        else (None if total_win > 0 else 0.0),
        "avg_win": round(total_win / len(wins), 2) if wins else 0.0,
        "avg_loss": round(total_loss / len(losses), 2) if losses else 0.0,
        "max_win": round(max((float(t["pnl"]) for t in wins), default=0.0), 2),
        "max_loss": round(min((float(t["pnl"]) for t in losses), default=0.0), 2),
        "expectancy": round((total_win + total_loss) / n, 2) if n else 0.0,
        "avg_holding_days": round(_mean(holding_days), 2),
        "max_holding_days": round(max(holding_days, default=0.0), 2),
    }


def _symbol_breakdown(trades: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for t in trades:
        if t.get("pnl") is None:
            continue
        sym = t.get("symbol") or "?"
        bucket = by_symbol.setdefault(
            sym,
            {"symbol": sym, "trade_count": 0, "wins": 0, "pnl": 0.0},
        )
        bucket["trade_count"] += 1
        pnl = float(t["pnl"])
        bucket["pnl"] += pnl
        if pnl > 0:
            bucket["wins"] += 1

    rows: list[dict[str, Any]] = []
    for sym, b in by_symbol.items():
        n = b["trade_count"]
        rows.append(
            {
                "symbol": sym,
                "trade_count": n,
                "pnl": round(b["pnl"], 2),
                "win_rate_pct": round(b["wins"] / n * 100, 2) if n else 0.0,
            }
        )
    rows.sort(key=lambda r: r["pnl"], reverse=True)
    return rows


def compute_metrics(
    equity_curve: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    initial_capital: float,
    final_equity: float,
    risk_free_rate_annual: float = 0.0,
) -> dict[str, Any]:
    """根据回测的 equity_curve 与 trades 计算完整指标集合。"""
    n = len(equity_curve)
    daily_rets = _daily_returns(equity_curve, initial_capital)

    daily_rf = (1 + risk_free_rate_annual) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess = [r - daily_rf for r in daily_rets]
    mean_excess = _mean(excess)
    std_all = _stdev(daily_rets)
    sharpe = (
        (mean_excess / _stdev(excess)) * math.sqrt(TRADING_DAYS_PER_YEAR)
        if _stdev(excess) > 0
        else 0.0
    )

    downside = [e for e in excess if e < 0]
    downside_std = (
        math.sqrt(sum(e * e for e in downside) / len(downside)) if downside else 0.0
    )
    sortino = (
        (mean_excess / downside_std) * math.sqrt(TRADING_DAYS_PER_YEAR)
        if downside_std > 0
        else 0.0
    )

    first_date = _to_date(equity_curve[0]["date"]) if n else None
    last_date = _to_date(equity_curve[-1]["date"]) if n else None
    if first_date and last_date and last_date > first_date:
        years = max((last_date - first_date).days / CALENDAR_DAYS_PER_YEAR, 1 / 365.25)
    else:
        years = max(n / TRADING_DAYS_PER_YEAR, 1 / 252)

    if initial_capital > 0 and final_equity > 0:
        annualized_return_pct = ((final_equity / initial_capital) ** (1 / years) - 1) * 100
    else:
        annualized_return_pct = 0.0

    annualized_vol_pct = std_all * math.sqrt(TRADING_DAYS_PER_YEAR) * 100

    dd_series = _drawdown_series(equity_curve, initial_capital)
    max_drawdown_pct = min((p["drawdown_pct"] for p in dd_series), default=0.0)
    longest_uw, uw_start, uw_end = _longest_underwater_days(dd_series)

    calmar = (
        annualized_return_pct / abs(max_drawdown_pct)
        if max_drawdown_pct < 0
        else 0.0
    )

    total_return_pct = (
        (final_equity / initial_capital - 1.0) * 100 if initial_capital > 0 else 0.0
    )

    return {
        # 核心收益/风险
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(annualized_return_pct, 2),
        "annualized_volatility_pct": round(annualized_vol_pct, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "longest_underwater_days": longest_uw,
        "underwater_start": uw_start,
        "underwater_end": uw_end,
        "risk_free_rate_annual_pct": round(risk_free_rate_annual * 100, 3),
        # 交易统计
        "trade_stats": _trade_stats(trades),
        # 月度收益矩阵 + 水下曲线 + 分品种
        "monthly_returns": _monthly_returns(equity_curve, initial_capital),
        "drawdown_series": dd_series,
        "symbol_breakdown": _symbol_breakdown(trades),
    }
