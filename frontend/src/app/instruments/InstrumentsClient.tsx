"use client";

import { useEffect, useState } from "react";
import { CandlestickChart, type PriceLevel } from "@/components/CandlestickChart";
import { AgentWatchPanel } from "@/components/AgentWatchPanel";
import type { Bar, Instrument } from "@/lib/api";
import { api } from "@/lib/api";

const TABS = [
  { key: "all", label: "全部" },
  { key: "crypto", label: "加密" },
  { key: "metal", label: "黄金" },
  { key: "equity", label: "美股" },
];

export function InstrumentsClient({ instruments }: { instruments: Instrument[] }) {
  const [tab, setTab] = useState("all");
  const [selected, setSelected] = useState<Instrument | null>(instruments[0] ?? null);
  const [bars, setBars] = useState<Bar[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  // Agent 看盘的价位线（entry / SL / TP）
  const [agentLevels, setAgentLevels] = useState<PriceLevel[]>([]);

  const filtered =
    tab === "all" ? instruments : instruments.filter((i) => i.asset_class === tab);

  useEffect(() => {
    if (filtered.length === 0) {
      setSelected(null);
      setBars([]);
      return;
    }
    setSelected((prev) => {
      if (prev && filtered.some((i) => i.id === prev.id)) return prev;
      return filtered[0];
    });
  }, [tab, instruments]);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setLoadError(null);
    api
      .getBars(selected.id)
      .then((data) => {
        setBars(data);
        if (data.length === 0) {
          setLoadError("该品种尚无 K 线，请点击下方「同步行情」");
        }
      })
      .catch((e) => {
        setBars([]);
        const msg = e instanceof Error ? e.message : "加载失败";
        setLoadError(
          msg.includes("Failed to fetch") || msg.includes("fetch")
            ? "无法连接后端，请确认 API 已启动（端口 9999）"
            : `加载 K 线失败：${msg}`
        );
      })
      .finally(() => setLoading(false));
  }, [selected]);

  const syncMarket = async () => {
    setSyncing(true);
    setLoadError(null);
    try {
      await api.bootstrapData();
      if (selected) {
        const data = await api.getBars(selected.id);
        setBars(data);
        if (data.length === 0) setLoadError("同步完成，但该品种仍无数据，请换品种或点「演示数据」");
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">行情</h1>
        <p className="text-sm text-zinc-500">
          日 K 线 · BTC（Coinbase）+ XAUUSD + Magnificent 7（AAPL/MSFT/GOOGL/AMZN/NVDA/META/TSLA） · Agent 看盘可一键标注入场/止损/止盈
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn-primary text-sm"
          disabled={syncing}
          onClick={syncMarket}
        >
          {syncing ? "同步中…" : "同步行情"}
        </button>
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              tab === t.key ? "bg-emerald-600/20 text-emerald-300" : "text-zinc-400 hover:bg-zinc-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        <div className="space-y-1 lg:col-span-1">
          {filtered.map((inst) => (
            <button
              key={inst.id}
              type="button"
              onClick={() => setSelected(inst)}
              className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${
                selected?.id === inst.id ? "bg-zinc-800 text-emerald-300" : "hover:bg-zinc-900"
              }`}
            >
              <span className="font-medium">{inst.symbol}</span>
              <span className="ml-2 text-zinc-500">{inst.name}</span>
            </button>
          ))}
        </div>

        <div className="lg:col-span-3">
          {selected && (
            <>
              <h2 className="mb-2 text-lg font-semibold">
                {selected.symbol} — {selected.name}
              </h2>
              {loading ? (
                <p className="text-sm text-zinc-500">加载中...</p>
              ) : loadError ? (
                <div
                  className="flex flex-col items-center justify-center gap-3 rounded-lg border border-zinc-800 text-zinc-500"
                  style={{ height: 420 }}
                >
                  <p className="text-sm text-amber-400/90">{loadError}</p>
                  <button type="button" className="btn-secondary text-sm" onClick={syncMarket} disabled={syncing}>
                    同步行情
                  </button>
                </div>
              ) : (
                <>
                  <CandlestickChart bars={bars} priceLevels={agentLevels} />
                  <div className="mt-4">
                    <AgentWatchPanel
                      instrumentId={selected.id}
                      symbol={selected.symbol}
                      onLevelsChange={setAgentLevels}
                    />
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
