"use client";

import type { DataStatus, PortfolioSummary, Signal } from "@/lib/api";
import { api } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

const ASSET_LABELS: Record<string, string> = {
  forex: "外汇",
  metal: "黄金",
  futures: "期货",
  equity: "美股",
};

export function DashboardClient({
  portfolio,
  signals,
  error,
}: {
  portfolio: PortfolioSummary | null;
  signals: Signal[];
  error: string | null;
}) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);

  const refreshDataStatus = useCallback(() => {
    api.getDataStatus().then(setDataStatus).catch(() => setDataStatus(null));
  }, []);

  useEffect(() => {
    refreshDataStatus();
  }, [refreshDataStatus]);

  const runAction = async (action: "sync" | "daily" | "demo" | "bootstrap") => {
    setLoading(true);
    setMsg(null);
    try {
      if (action === "bootstrap") {
        setMsg("正在清空并同步真实行情（外汇走 Frankfurter，约 1–3 分钟）…");
        const r = await api.bootstrapData();
        setMsg(`灌库结果: ${JSON.stringify(r.synced)}`);
        refreshDataStatus();
      } else if (action === "sync") {
        const r = await api.syncData();
        setMsg(`行情同步完成: ${JSON.stringify(r.synced)}`);
        refreshDataStatus();
      } else if (action === "demo") {
        const r = await api.seedDemoData(true);
        setMsg(`演示数据（非真实行情）: ${JSON.stringify(r.inserted)}`);
        refreshDataStatus();
      } else {
        const r = await api.runDaily();
        setMsg(`每日扫描完成: ${JSON.stringify(r.details)}`);
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  };

  if (error) {
    return (
      <div className="card border-amber-900/50 bg-amber-950/20">
        <h1 className="text-lg font-semibold text-amber-300">后端未就绪</h1>
        <p className="mt-2 text-sm text-zinc-400">{error}</p>
        <p className="mt-4 text-sm text-zinc-500">
          请启动 FastAPI：
          <code className="text-emerald-400">cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 9999</code>
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {dataStatus && !dataStatus.ready && (
        <div
          className={`card border ${
            dataStatus.partial
              ? "border-amber-900/40 bg-amber-950/15"
              : "border-red-900/40 bg-red-950/15"
          }`}
        >
          <h2 className="text-sm font-semibold text-amber-200">行情数据</h2>
          <p className="mt-1 text-sm text-zinc-400">{dataStatus.message}</p>
          <p className="mt-2 text-xs text-zinc-500">
            已就绪 {dataStatus.symbols_ready}/{dataStatus.symbol_count} 个品种 · 共 {dataStatus.total_bars} 根 K 线
          </p>
          <ul className="mt-2 grid gap-1 text-xs text-zinc-500 sm:grid-cols-3">
            {Object.entries(dataStatus.instruments).map(([sym, info]) => (
              <li key={sym}>
                {sym}: {info.bar_count} 根
                {info.last_trade_date ? ` · 至 ${info.last_trade_date}` : ""}
                {info.ready ? " ✓" : ""}
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary"
              disabled={loading}
              onClick={() => runAction("bootstrap")}
            >
              全量灌库
            </button>
            {dataStatus.zero_key_mode && (
              <span className="self-center text-xs text-zinc-500">
                无需 API Key：灌库后外汇为真实价，黄金/期货失败会自动演示补全
              </span>
            )}
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">组合总览</h1>
          <p className="text-sm text-zinc-500">日频策略 · 每日最多 2 笔开仓</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-primary"
            disabled={loading}
            onClick={() => runAction("bootstrap")}
          >
            全量灌库
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={loading}
            onClick={() => runAction("sync")}
          >
            增量同步
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={loading}
            onClick={() => runAction("demo")}
            title="仅离线演示"
          >
            演示数据
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={loading}
            onClick={() => runAction("daily")}
          >
            运行每日扫描
          </button>
        </div>
      </div>

      {msg && <p className="rounded-lg bg-zinc-900 px-4 py-2 text-xs text-zinc-400">{msg}</p>}

      {portfolio && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="组合净值" value={`$${portfolio.equity.toLocaleString()}`} />
          <StatCard
            label="浮动盈亏"
            value={`$${portfolio.unrealized_pnl.toLocaleString()}`}
            positive={portfolio.unrealized_pnl >= 0}
          />
          <StatCard
            label="今日已交易"
            value={`${portfolio.trades_today} / ${portfolio.max_trades_per_day}`}
          />
          <StatCard label="剩余额度" value={`${portfolio.trades_remaining} 笔`} />
        </div>
      )}

      {portfolio && Object.keys(portfolio.exposure_by_class).length > 0 && (
        <div className="card">
          <h2 className="mb-4 font-semibold">品类敞口</h2>
          <div className="flex flex-wrap gap-4">
            {Object.entries(portfolio.exposure_by_class).map(([k, v]) => (
              <div key={k} className="rounded-lg bg-zinc-800/50 px-4 py-3">
                <p className="stat-label">{ASSET_LABELS[k] || k}</p>
                <p className="stat-value text-lg">${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {portfolio && portfolio.positions.length > 0 && (
        <div className="card">
          <h2 className="mb-4 font-semibold">当前持仓</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-zinc-500">
                <th className="pb-2">品种</th>
                <th>数量</th>
                <th>均价</th>
                <th>市价</th>
                <th>浮动盈亏</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map((p) => (
                <tr key={p.symbol} className="border-t border-zinc-800">
                  <td className="py-2 font-medium">{p.symbol}</td>
                  <td>{p.quantity}</td>
                  <td>{p.avg_price.toFixed(4)}</td>
                  <td>{p.mark_price.toFixed(4)}</td>
                  <td className={p.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                    ${p.unrealized_pnl}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h2 className="mb-4 font-semibold">最近信号</h2>
        {signals.length === 0 ? (
          <p className="text-sm text-zinc-500">暂无信号，请先全量灌库后运行每日扫描</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-zinc-500">
                <th className="pb-2">品种</th>
                <th>日期</th>
                <th>方向</th>
                <th>强度</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.id} className="border-t border-zinc-800">
                  <td className="py-2">{s.symbol}</td>
                  <td>{s.signal_date}</td>
                  <td className={s.side === "long" ? "text-emerald-400" : "text-red-400"}>
                    {s.side === "long" ? "做多" : s.side === "short" ? "做空" : "平仓"}
                  </td>
                  <td>{s.strength.toFixed(4)}</td>
                  <td className="text-zinc-400">{s.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="card">
      <p className="stat-label">{label}</p>
      <p
        className={`stat-value ${
          positive === true ? "text-emerald-400" : positive === false ? "text-red-400" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}
