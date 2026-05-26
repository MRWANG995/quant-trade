"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type AgentDecisionResult, type StrategyDefinition } from "@/lib/api";
import type { PriceLevel } from "@/components/CandlestickChart";

type Props = {
  instrumentId: number;
  symbol: string;
  /** 父组件用以接收价位线，渲染在 K 线图上 */
  onLevelsChange?: (levels: PriceLevel[]) => void;
};

const sideLabel: Record<string, string> = {
  long: "做多",
  short: "做空",
  hold: "观望",
};

const sideColor: Record<string, string> = {
  long: "text-emerald-400",
  short: "text-red-400",
  hold: "text-zinc-400",
};

export function AgentWatchPanel({ instrumentId, symbol, onLevelsChange }: Props) {
  const [agents, setAgents] = useState<StrategyDefinition[]>([]);
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentDecisionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 加载所有 agent 策略
  useEffect(() => {
    api
      .getStrategies()
      .then((list) => {
        const agentList = list.filter((s) => s.strategy_type === "agent" && s.is_active);
        setAgents(agentList);
        if (agentList[0] && !selectedId) setSelectedId(agentList[0].id);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 切到新品种时清掉旧结果
  useEffect(() => {
    setResult(null);
    onLevelsChange?.([]);
    setError(null);
  }, [instrumentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const analyze = useCallback(
    async (force: boolean) => {
      if (!selectedId) {
        setError("请先选择一个 Agent 策略");
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const r = await api.agentAnalyze(selectedId as number, instrumentId, force);
        setResult(r);
        const levels: PriceLevel[] = [];
        if (r.entry_price != null)
          levels.push({ label: `入场 ${r.entry_price.toFixed(2)}`, price: r.entry_price, color: "#22c55e" });
        if (r.stop_loss != null)
          levels.push({ label: `止损 ${r.stop_loss.toFixed(2)}`, price: r.stop_loss, color: "#ef4444" });
        if (r.take_profit != null)
          levels.push({ label: `止盈 ${r.take_profit.toFixed(2)}`, price: r.take_profit, color: "#facc15" });
        onLevelsChange?.(levels);
      } catch (e) {
        setError(e instanceof Error ? e.message : "调用失败");
        onLevelsChange?.([]);
      } finally {
        setLoading(false);
      }
    },
    [selectedId, instrumentId, onLevelsChange]
  );

  if (agents.length === 0) {
    return (
      <div className="card border-zinc-800 bg-zinc-900/30">
        <h3 className="text-sm font-semibold">Agent 看盘</h3>
        <p className="mt-2 text-xs text-zinc-500">
          还没创建 Agent 策略。去「策略」页新建一个 Agent 类型策略后回来用。
        </p>
      </div>
    );
  }

  return (
    <div className="card border-zinc-800 bg-zinc-900/30 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          Agent 看盘 <span className="text-xs text-zinc-500">· {symbol}</span>
        </h3>
        {result?.cached && (
          <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500">
            缓存
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          className="input flex-1 min-w-[180px] text-sm"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
        >
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn-primary text-sm"
          disabled={loading || !selectedId}
          onClick={() => analyze(false)}
        >
          {loading ? "分析中…" : "分析"}
        </button>
        <button
          type="button"
          className="btn-secondary text-sm"
          disabled={loading || !selectedId}
          onClick={() => analyze(true)}
          title="忽略当日缓存，重新调 LLM"
        >
          重算
        </button>
      </div>

      {error && (
        <p className="rounded bg-red-950/30 px-3 py-2 text-xs text-red-300">{error}</p>
      )}

      {result && (
        <div className="space-y-2 text-sm">
          <div className="flex items-baseline gap-3">
            <span className={`text-base font-semibold ${sideColor[result.side] || ""}`}>
              {sideLabel[result.side] || result.side}
            </span>
            <span className="text-xs text-zinc-500">
              置信度 {(result.confidence * 100).toFixed(0)}%
            </span>
            <span className="text-xs text-zinc-500">{result.decision_date}</span>
          </div>

          {result.side !== "hold" && (
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="rounded bg-emerald-950/30 px-2 py-1.5">
                <div className="text-emerald-400">入场</div>
                <div className="font-mono">
                  {result.entry_price?.toFixed(2) ?? "—"}
                </div>
              </div>
              <div className="rounded bg-red-950/30 px-2 py-1.5">
                <div className="text-red-400">止损</div>
                <div className="font-mono">
                  {result.stop_loss?.toFixed(2) ?? "—"}
                </div>
              </div>
              <div className="rounded bg-yellow-950/30 px-2 py-1.5">
                <div className="text-yellow-400">止盈</div>
                <div className="font-mono">
                  {result.take_profit?.toFixed(2) ?? "—"}
                </div>
              </div>
            </div>
          )}

          <p className="rounded bg-zinc-900 px-3 py-2 text-xs text-zinc-300 leading-relaxed">
            {result.reason}
          </p>
          {result.model && (
            <p className="text-[10px] text-zinc-600">model: {result.model}</p>
          )}
        </div>
      )}
    </div>
  );
}
