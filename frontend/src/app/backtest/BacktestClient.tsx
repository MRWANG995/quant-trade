"use client";

import { useCallback, useEffect, useState } from "react";
import { CandlestickChart } from "@/components/CandlestickChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { EquityChart } from "@/components/EquityChart";
import { MonthlyReturnHeatmap } from "@/components/MonthlyReturnHeatmap";
import { StrategyFilter } from "@/components/StrategyFilter";
import {
  api,
  type BacktestChartData,
  type BacktestDetail,
  type BacktestMetrics,
  type BacktestSummary,
  type Instrument,
  type StrategyDefinition,
  type StrategyTypeMeta,
} from "@/lib/api";

// 只挑出可数值化的扁平参数作为回测覆盖项；过滤掉 llm_dsl 的 dsl 对象、
// llm_prompt 字符串等非数值字段（否则 Number() 后会变成 null 把 dsl 干掉）。
function pickNumericParams(params: Record<string, unknown>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(params || {})) {
    const n = Number(v);
    if (typeof v !== "object" && Number.isFinite(n)) {
      out[k] = n;
    }
  }
  return out;
}

export function BacktestClient({
  history,
  instruments,
}: {
  history: BacktestSummary[];
  instruments: Instrument[];
}) {
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [types, setTypes] = useState<StrategyTypeMeta[]>([]);
  const [strategyId, setStrategyId] = useState<number | "">("");
  const [paramOverrides, setParamOverrides] = useState<Record<string, number>>({});
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [chartInstrumentId, setChartInstrumentId] = useState<number | "">("");
  const [loading, setLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [result, setResult] = useState<BacktestDetail | null>(null);
  const [chartData, setChartData] = useState<BacktestChartData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedStrategy = strategies.find((s) => s.id === strategyId);
  const typeMeta = types.find((t) => t.type === selectedStrategy?.strategy_type);

  useEffect(() => {
    Promise.all([api.getStrategies(), api.getStrategyTypes()])
      .then(([s, t]) => {
        setStrategies(s);
        setTypes(t);
        const def = s.find((x) => x.is_default) || s[0];
        if (def) {
          setStrategyId(def.id);
          setParamOverrides(pickNumericParams(def.params));
        }
        if (instruments[0]) setChartInstrumentId(instruments[0].id);
      })
      .catch(() => {});
  }, [instruments]);

  const loadChart = useCallback(
    async (resultId: number, instrumentId: number) => {
      setChartLoading(true);
      try {
        const data = await api.getBacktestChartData(resultId, instrumentId);
        setChartData(data);
      } catch {
        setChartData(null);
      } finally {
        setChartLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (result?.id && chartInstrumentId) {
      loadChart(result.id, chartInstrumentId as number);
    }
  }, [result?.id, chartInstrumentId, loadChart]);

  const run = async () => {
    if (!strategyId) {
      setError("请选择策略");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await api.runBacktest({
        start_date: startDate,
        end_date: endDate,
        strategy_id: strategyId as number,
        param_overrides: paramOverrides,
        initial_capital: 100000,
      });
      setResult(r);
      if (chartInstrumentId) {
        await loadChart(r.id, chartInstrumentId as number);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "回测失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">策略回测</h1>
        <p className="text-sm text-zinc-500">
          选择已保存策略运行回测；K 线图标注入场/出场点
        </p>
      </div>

      <div className="card grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block text-sm sm:col-span-2">
          <span className="stat-label">策略</span>
          <select
            className="input mt-1 w-full"
            value={strategyId}
            onChange={(e) => {
              const id = Number(e.target.value);
              setStrategyId(id);
              const s = strategies.find((x) => x.id === id);
              if (s) {
                setParamOverrides(pickNumericParams(s.params));
              }
            }}
          >
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.is_default ? "（默认）" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="stat-label">开始日期</span>
          <input
            type="date"
            className="input mt-1 w-full"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="stat-label">结束日期</span>
          <input
            type="date"
            className="input mt-1 w-full"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </label>
        {typeMeta?.param_schema?.map((field) => (
          <label key={field.key} className="block text-sm">
            <span className="stat-label">{field.label}（本次覆盖）</span>
            <input
              type="number"
              className="input mt-1 w-full"
              value={paramOverrides[field.key] ?? Number(field.default)}
              onChange={(e) =>
                setParamOverrides({
                  ...paramOverrides,
                  [field.key]: Number(e.target.value),
                })
              }
            />
          </label>
        ))}
      </div>

      <button type="button" className="btn-primary" disabled={loading} onClick={run}>
        {loading ? "回测中..." : "运行回测"}
      </button>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && (
        <div className="space-y-4">
          <MetricsGrid result={result} />
          <TradeStatsCard metrics={result.metrics} />

          <div className="card">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">K 线与交易点</h2>
              <select
                className="input"
                value={chartInstrumentId}
                onChange={(e) => setChartInstrumentId(Number(e.target.value))}
              >
                {instruments.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.symbol} — {i.name}
                  </option>
                ))}
              </select>
            </div>
            {chartLoading ? (
              <p className="text-sm text-zinc-500">加载图表…</p>
            ) : chartData ? (
              <>
                <CandlestickChart
                  bars={chartData.bars}
                  markers={chartData.markers}
                  overlays={chartData.overlays}
                />
                <p className="mt-2 text-xs text-zinc-500">
                  绿色上箭头=做多入场，红色下箭头=做空入场，灰色箭头=出场；蓝线=快线，橙线=慢线
                </p>
              </>
            ) : (
              <p className="text-sm text-zinc-500">选择品种查看 K 线</p>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card">
              <h2 className="mb-4 font-semibold">净值曲线</h2>
              <EquityChart data={result.equity_curve} />
            </div>
            <div className="card">
              <div className="mb-4 flex items-baseline justify-between">
                <h2 className="font-semibold">回撤曲线（水下）</h2>
                {result.metrics?.longest_underwater_days ? (
                  <span className="text-xs text-zinc-500">
                    最长水下 {result.metrics.longest_underwater_days} 天
                  </span>
                ) : null}
              </div>
              {result.metrics?.drawdown_series?.length ? (
                <DrawdownChart data={result.metrics.drawdown_series} />
              ) : (
                <p className="text-sm text-zinc-500">无回撤数据</p>
              )}
            </div>
          </div>

          {result.metrics && (
            <div className="card">
              <h2 className="mb-4 font-semibold">月度收益热图</h2>
              <MonthlyReturnHeatmap data={result.metrics.monthly_returns} />
            </div>
          )}

          {result.metrics?.symbol_breakdown?.length ? (
            <div className="card overflow-x-auto">
              <h2 className="mb-4 font-semibold">分品种贡献</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-zinc-500">
                    <th className="pb-2">品种</th>
                    <th>交易数</th>
                    <th>胜率</th>
                    <th>累计盈亏</th>
                  </tr>
                </thead>
                <tbody>
                  {result.metrics.symbol_breakdown.map((row) => (
                    <tr key={row.symbol} className="border-t border-zinc-800">
                      <td className="py-1">{row.symbol}</td>
                      <td>{row.trade_count}</td>
                      <td>{row.win_rate_pct.toFixed(1)}%</td>
                      <td className={row.pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                        ${row.pnl.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="card overflow-x-auto">
            <h2 className="mb-4 font-semibold">交易记录</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500">
                  <th className="pb-2">品种</th>
                  <th>方向</th>
                  <th>入场</th>
                  <th>出场</th>
                  <th>盈亏</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((t, i) => (
                  <tr key={i} className="border-t border-zinc-800">
                    <td className="py-1">{t.symbol}</td>
                    <td>{t.side === "long" ? "多" : "空"}</td>
                    <td>
                      {t.entry_date} @ {t.entry_price}
                    </td>
                    <td>
                      {t.exit_date ? `${t.exit_date} @ ${t.exit_price}` : "—"}
                    </td>
                    <td
                      className={
                        (t.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                      }
                    >
                      {t.pnl != null ? `$${t.pnl}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h2 className="font-semibold">历史回测</h2>
          <StrategyFilter />
        </div>
        {history.length === 0 ? (
          <p className="text-sm text-zinc-500">当前过滤条件下无历史回测</p>
        ) : null}
      </div>

      {history.length > 0 && (
        <div className="card">
          <h2 className="mb-4 font-semibold">历史回测明细</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-zinc-500">
                <th className="pb-2">ID</th>
                <th>策略</th>
                <th>区间</th>
                <th>收益</th>
                <th>交易数</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-t border-zinc-800">
                  <td className="py-1">{h.id}</td>
                  <td>{h.strategy_name || h.strategy}</td>
                  <td>
                    {h.start_date} ~ {h.end_date}
                  </td>
                  <td
                    className={
                      h.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400"
                    }
                  >
                    {h.total_return_pct}%
                  </td>
                  <td>{h.trade_count}</td>
                  <td>
                    <button
                      type="button"
                      className="text-xs text-emerald-400 hover:underline"
                      onClick={async () => {
                        const detail = await api.getBacktest(h.id);
                        setResult(detail);
                      }}
                    >
                      查看
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neutral";
  hint?: string;
}) {
  const toneClass =
    tone === "pos"
      ? "text-emerald-400"
      : tone === "neg"
        ? "text-red-400"
        : "";
  return (
    <div className="card">
      <p className="stat-label">{label}</p>
      <p className={`stat-value text-lg tabular-nums ${toneClass}`}>{value}</p>
      {hint && <p className="mt-1 text-[10px] text-zinc-500">{hint}</p>}
    </div>
  );
}

function fmtNum(v: number | null | undefined, digits = 2, suffix = ""): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}${suffix}`;
}

function MetricsGrid({ result }: { result: BacktestDetail }) {
  const m = result.metrics;
  const toneByPct = (v: number) =>
    v > 0 ? "pos" : v < 0 ? "neg" : "neutral";

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="策略" value={result.strategy_name || result.strategy} />
        <Metric
          label="总收益"
          value={fmtNum(result.total_return_pct, 2, "%")}
          tone={toneByPct(result.total_return_pct)}
        />
        <Metric
          label="年化收益"
          value={fmtNum(m?.annualized_return_pct, 2, "%")}
          tone={m ? toneByPct(m.annualized_return_pct) : undefined}
        />
        <Metric
          label="年化波动率"
          value={fmtNum(m?.annualized_volatility_pct, 2, "%")}
        />
        <Metric
          label="Sharpe"
          value={fmtNum(m?.sharpe, 2)}
          hint={m ? `rf=${m.risk_free_rate_annual_pct}%` : undefined}
        />
        <Metric label="Sortino" value={fmtNum(m?.sortino, 2)} />
        <Metric label="Calmar" value={fmtNum(m?.calmar, 2)} />
        <Metric
          label="最大回撤"
          value={fmtNum(result.max_drawdown_pct, 2, "%")}
          tone={result.max_drawdown_pct > 0 ? "neg" : "neutral"}
        />
        <Metric
          label="最长水下天数"
          value={m ? String(m.longest_underwater_days) : "—"}
          hint={
            m?.underwater_start
              ? `${m.underwater_start} ~ ${m.underwater_end ?? ""}`
              : undefined
          }
        />
        <Metric
          label="胜率"
          value={m ? fmtNum(m.trade_stats.win_rate_pct, 1, "%") : "—"}
        />
        <Metric
          label="盈亏比"
          value={m ? fmtNum(m.trade_stats.profit_factor, 2) : "—"}
        />
        <Metric
          label="交易次数"
          value={String(result.trade_count)}
          hint={
            m
              ? `平均持仓 ${fmtNum(m.trade_stats.avg_holding_days, 1)} 天`
              : undefined
          }
        />
      </div>
    </>
  );
}

function TradeStatsCard({ metrics }: { metrics?: BacktestMetrics }) {
  if (!metrics) return null;
  const s = metrics.trade_stats;
  return (
    <div className="card grid gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
      <StatRow label="赢家" value={`${s.winning_trades} 笔`} />
      <StatRow label="输家" value={`${s.losing_trades} 笔`} />
      <StatRow label="平均盈利" value={`$${fmtNum(s.avg_win, 2)}`} tone="pos" />
      <StatRow label="平均亏损" value={`$${fmtNum(s.avg_loss, 2)}`} tone="neg" />
      <StatRow label="最大单笔盈" value={`$${fmtNum(s.max_win, 2)}`} tone="pos" />
      <StatRow label="最大单笔亏" value={`$${fmtNum(s.max_loss, 2)}`} tone="neg" />
      <StatRow label="期望值/笔" value={`$${fmtNum(s.expectancy, 2)}`} />
      <StatRow label="最长持仓" value={`${fmtNum(s.max_holding_days, 0)} 天`} />
    </div>
  );
}

function StatRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg";
}) {
  const toneClass = tone === "pos" ? "text-emerald-400" : tone === "neg" ? "text-red-400" : "";
  return (
    <div>
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`tabular-nums ${toneClass}`}>{value}</p>
    </div>
  );
}
