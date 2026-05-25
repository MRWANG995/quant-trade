"use client";

import { useState } from "react";

import {
  api,
  type DslExplain,
  type DslGenerateResponse,
} from "@/lib/api";

type ChatMessage =
  | { role: "user"; text: string; ts: number }
  | {
      role: "assistant";
      ts: number;
      explain: DslExplain;
      dsl: Record<string, unknown>;
      raw: string;
      model: string;
      saved?: { id: number; slug: string };
      prompt: string;
    }
  | { role: "error"; text: string; ts: number };

export function StrategyChatPanel({
  onSaved,
}: {
  onSaved?: (strategyId: number) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<number | null>(null); // assistant msg index being saved
  const [showRaw, setShowRaw] = useState<number | null>(null);

  const send = async () => {
    const prompt = input.trim();
    if (!prompt || loading) return;
    setInput("");
    setLoading(true);
    const ts = Date.now();
    setMessages((m) => [...m, { role: "user", text: prompt, ts }]);
    try {
      const resp: DslGenerateResponse = await api.generateStrategyFromPrompt(prompt);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          ts: Date.now(),
          explain: resp.explain,
          dsl: resp.dsl,
          raw: resp.raw_text,
          model: resp.model,
          prompt,
        },
      ]);
    } catch (e) {
      const text = e instanceof Error ? e.message : "生成失败";
      setMessages((m) => [...m, { role: "error", text, ts: Date.now() }]);
    } finally {
      setLoading(false);
    }
  };

  const saveStrategy = async (idx: number) => {
    const msg = messages[idx];
    if (msg.role !== "assistant") return;
    setSaving(idx);
    try {
      const st = await api.saveDslAsStrategy({
        dsl: msg.dsl,
        llm_prompt: msg.prompt,
        llm_model: msg.model,
      });
      setMessages((m) =>
        m.map((x, i) =>
          i === idx && x.role === "assistant"
            ? { ...x, saved: { id: st.id, slug: st.slug } }
            : x
        )
      );
      onSaved?.(st.id);
    } catch (e) {
      const text = e instanceof Error ? e.message : "保存失败";
      setMessages((m) => [...m, { role: "error", text, ts: Date.now() }]);
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="card flex h-[640px] flex-col">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="font-semibold">对话生成策略</h2>
        <span className="text-xs text-zinc-500">Gemini 2.0 Flash · DSL</span>
      </div>
      <div className="mb-3 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <EmptyState onPick={(s) => setInput(s)} />
        )}
        {messages.map((m, idx) => (
          <MessageBubble
            key={`${m.role}-${m.ts}`}
            msg={m}
            onSave={() => saveStrategy(idx)}
            saving={saving === idx}
            onToggleRaw={() => setShowRaw(showRaw === idx ? null : idx)}
            showRaw={showRaw === idx}
          />
        ))}
        {loading && (
          <div className="rounded-lg bg-zinc-900/60 px-3 py-2 text-sm text-zinc-400">
            正在让 Gemini 生成策略…
          </div>
        )}
      </div>
      <div className="border-t border-zinc-800 pt-3">
        <textarea
          className="input min-h-[80px] w-full resize-none"
          placeholder="用一句话描述你想要的策略，例如：RSI 跌破 30 后回升，且 close 在 50 日均线上方时做多；进入 70 超买出场。"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <div className="mt-2 flex items-center justify-between">
          <p className="text-[11px] text-zinc-500">⌘/Ctrl + Enter 发送</p>
          <button
            type="button"
            className="btn-primary"
            disabled={loading || !input.trim()}
            onClick={send}
          >
            {loading ? "生成中…" : "生成策略"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (s: string) => void }) {
  const suggestions = [
    "RSI 跌破 30 后回升，且 close 在 50 日均线上方时做多；进入 70 超买出场。",
    "双均线交叉系统：EMA(12) 上穿 EMA(26) 做多，下穿做空。",
    "唐奇安 20 日通道：突破做多，跌破做空；ATR(14) 大于 1% 时再过滤。",
    "MACD 金叉做多、死叉做空，要求 close 在 SMA(100) 同侧。",
    "布林带 20/2σ：触下轨且 RSI<30 做多，触上轨且 RSI>70 做空。",
  ];
  return (
    <div className="space-y-2 text-sm">
      <p className="text-zinc-400">用自然语言描述策略，Gemini 会输出可回测的 DSL。试试：</p>
      <ul className="space-y-1">
        {suggestions.map((s) => (
          <li key={s}>
            <button
              type="button"
              className="w-full rounded bg-zinc-900/60 px-3 py-2 text-left text-xs text-zinc-300 hover:bg-zinc-800"
              onClick={() => onPick(s)}
            >
              {s}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MessageBubble({
  msg,
  onSave,
  saving,
  onToggleRaw,
  showRaw,
}: {
  msg: ChatMessage;
  onSave: () => void;
  saving: boolean;
  onToggleRaw: () => void;
  showRaw: boolean;
}) {
  if (msg.role === "user") {
    return (
      <div className="ml-6 rounded-lg bg-emerald-600/15 px-3 py-2 text-sm">
        {msg.text}
      </div>
    );
  }
  if (msg.role === "error") {
    return (
      <div className="rounded-lg bg-red-900/30 px-3 py-2 text-sm text-red-300">
        ⚠ {msg.text}
      </div>
    );
  }
  // assistant
  const e = msg.explain;
  return (
    <div className="rounded-lg bg-zinc-900/60 px-3 py-2 text-sm">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="font-semibold text-zinc-200">{e.name}</p>
        <span className="text-[11px] text-zinc-500">{msg.model}</span>
      </div>
      {e.description && (
        <p className="mb-2 text-xs text-zinc-400">{e.description}</p>
      )}
      <div className="mb-2 space-y-1">
        <p className="text-[11px] text-zinc-500">入场条件</p>
        {e.entries.map((ent, i) => (
          <p key={i} className="text-xs text-emerald-200">
            <span className="mr-1 inline-block rounded bg-emerald-700/40 px-1.5 py-0.5">
              {ent.side}
            </span>
            {ent.condition}
            {ent.comment && <span className="ml-1 text-zinc-500">— {ent.comment}</span>}
          </p>
        ))}
      </div>
      {e.exits.length > 0 && (
        <div className="mb-2 space-y-1">
          <p className="text-[11px] text-zinc-500">出场条件</p>
          {e.exits.map((ex, i) => (
            <p key={i} className="text-xs text-amber-200">
              {ex.condition}
              {ex.comment && <span className="ml-1 text-zinc-500">— {ex.comment}</span>}
            </p>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {msg.saved ? (
          <span className="rounded bg-emerald-700/30 px-2 py-1 text-xs text-emerald-300">
            ✓ 已保存（id={msg.saved.id}，slug={msg.saved.slug}）— 去「回测」选择该策略
          </span>
        ) : (
          <button
            type="button"
            className="btn-primary text-xs"
            disabled={saving}
            onClick={onSave}
          >
            {saving ? "保存中…" : "保存为策略"}
          </button>
        )}
        <button
          type="button"
          className="text-xs text-zinc-400 hover:text-zinc-200"
          onClick={onToggleRaw}
        >
          {showRaw ? "隐藏 DSL" : "查看 DSL"}
        </button>
      </div>
      {showRaw && (
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-zinc-950 p-2 text-[11px] text-zinc-400">
          {JSON.stringify(msg.dsl, null, 2)}
        </pre>
      )}
    </div>
  );
}
