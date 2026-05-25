"use client";

import { useCallback, useEffect, useState } from "react";
import { StrategyChatPanel } from "@/components/StrategyChatPanel";
import { api, type StrategyDefinition, type StrategyTypeMeta } from "@/lib/api";

export function StrategiesClient() {
  const [types, setTypes] = useState<StrategyTypeMeta[]>([]);
  const [list, setList] = useState<StrategyDefinition[]>([]);
  const [editing, setEditing] = useState<StrategyDefinition | null>(null);
  const [form, setForm] = useState({
    slug: "",
    name: "",
    strategy_type: "ma_cross",
    description: "",
    is_default: false,
    // composite 时 params = {mode, children: [{strategy_id, weight}]}；
    // llm_dsl 时含嵌套 dsl 对象；其它策略是 {key: number}。
    params: {} as Record<string, unknown>,
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    const [t, s] = await Promise.all([api.getStrategyTypes(), api.getStrategies()]);
    setTypes(t);
    setList(s);
    if (!editing && s.length && !form.name) {
      const def = s.find((x) => x.is_default) || s[0];
      openEdit(def, t);
    }
  }, [editing, form.name]);

  useEffect(() => {
    load().catch((e) => setMsg(e instanceof Error ? e.message : "加载失败"));
  }, []);

  const typeMeta = types.find((t) => t.type === form.strategy_type) || types[0];

  const resetNew = () => {
    setEditing(null);
    const meta = types[0];
    const params: Record<string, number> = {};
    meta?.param_schema?.forEach((f) => {
      params[f.key] = Number(f.default);
    });
    setForm({
      slug: "",
      name: "",
      strategy_type: meta?.type || "ma_cross",
      description: "",
      is_default: false,
      params,
    });
  };

  const openEdit = (s: StrategyDefinition, typeList = types) => {
    setEditing(s);
    setForm({
      slug: s.slug,
      name: s.name,
      strategy_type: s.strategy_type,
      description: s.description,
      is_default: s.is_default,
      params: { ...s.params },
    });
    if (!typeList.length) return;
    const meta = typeList.find((t) => t.type === s.strategy_type);
    if (meta) {
      const merged = { ...s.params };
      meta.param_schema.forEach((f) => {
        if (merged[f.key] === undefined) merged[f.key] = f.default;
      });
      setForm((f) => ({ ...f, params: merged }));
    }
  };

  const onTypeChange = (strategy_type: string) => {
    const meta = types.find((t) => t.type === strategy_type);
    let params: Record<string, unknown> = {};
    if (strategy_type === "composite") {
      params = { mode: "weighted", children: [] };
    } else if (strategy_type === "agent") {
      params = { system_prompt: "" };
      meta?.param_schema?.forEach((f) => {
        params[f.key] = Number(f.default);
      });
    } else {
      meta?.param_schema?.forEach((f) => {
        params[f.key] = Number(f.default);
      });
    }
    setForm((f) => ({ ...f, strategy_type, params }));
  };

  const save = async () => {
    setLoading(true);
    setMsg(null);
    try {
      if (editing) {
        await api.updateStrategy(editing.id, {
          name: form.name,
          strategy_type: form.strategy_type,
          params: form.params,
          description: form.description,
          is_default: form.is_default,
        });
        setMsg("策略已更新");
      } else {
        await api.createStrategy({
          slug: form.slug || form.name.toLowerCase().replace(/\s+/g, "_"),
          name: form.name,
          strategy_type: form.strategy_type,
          params: form.params,
          description: form.description,
          is_default: form.is_default,
        });
        setMsg("策略已创建");
        resetNew();
      }
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("确定删除该策略？")) return;
    setLoading(true);
    try {
      await api.deleteStrategy(id);
      setMsg("已删除");
      resetNew();
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">策略管理</h1>
          <p className="text-sm text-zinc-500">新增、修改策略参数；回测与每日扫描将使用所选策略</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={loading}
            onClick={async () => {
              setLoading(true);
              try {
                const r = await api.seedStrategyPresets();
                setMsg(`已导入 ${r.added} 条公共策略，共 ${r.total} 条`);
                await load();
              } catch (e) {
                setMsg(e instanceof Error ? e.message : "导入失败");
              } finally {
                setLoading(false);
              }
            }}
          >
            导入公共策略
          </button>
          <button type="button" className="btn-secondary" onClick={resetNew}>
            新建策略
          </button>
        </div>
      </div>

      {msg && <p className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-zinc-400">{msg}</p>}

      <StrategyChatPanel
        onSaved={() => {
          load().catch(() => {});
        }}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card lg:col-span-1">
          <h2 className="mb-3 font-semibold">已保存策略</h2>
          <ul className="space-y-2">
            {list.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => openEdit(s)}
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                    editing?.id === s.id ? "bg-emerald-600/20 text-emerald-300" : "hover:bg-zinc-800"
                  }`}
                >
                  <span className="font-medium">{s.name}</span>
                  {s.is_default && (
                    <span className="ml-2 text-xs text-amber-400">默认</span>
                  )}
                  <span className="mt-0.5 block text-xs text-zinc-500">{s.slug}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="card lg:col-span-2">
          <h2 className="mb-4 font-semibold">{editing ? "编辑策略" : "新建策略"}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {!editing && (
              <label className="block text-sm sm:col-span-2">
                <span className="stat-label">标识 slug</span>
                <input
                  className="input mt-1 w-full"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  placeholder="例如 ma_cross_fast"
                />
              </label>
            )}
            <label className="block text-sm">
              <span className="stat-label">名称</span>
              <input
                className="input mt-1 w-full"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              <span className="stat-label">策略类型</span>
              <select
                className="input mt-1 w-full"
                value={form.strategy_type}
                onChange={(e) => onTypeChange(e.target.value)}
                disabled={!!editing}
              >
                {types.map((t) => (
                  <option key={t.type} value={t.type}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            {typeMeta?.param_schema?.map((field) => (
              <label key={field.key} className="block text-sm">
                <span className="stat-label">{field.label}</span>
                <input
                  type="number"
                  step={field.type === "float" ? "0.1" : "1"}
                  className="input mt-1 w-full"
                  min={field.min}
                  max={field.max}
                  value={Number(form.params[field.key] ?? field.default)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      params: {
                        ...form.params,
                        [field.key]:
                          field.type === "float"
                            ? parseFloat(e.target.value)
                            : parseInt(e.target.value, 10),
                      },
                    })
                  }
                />
              </label>
            ))}
            {form.strategy_type === "agent" && (
              <label className="block text-sm sm:col-span-2">
                <span className="stat-label">系统提示词（指导 LLM 怎么交易）</span>
                <textarea
                  className="input mt-1 w-full font-mono text-xs"
                  rows={4}
                  placeholder="例如：你是趋势型交易员，只在 close 站上 SMA50 且 RSI 在 50-70 区间做多；明显回落时做空"
                  value={String(form.params.system_prompt ?? "")}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      params: { ...form.params, system_prompt: e.target.value },
                    })
                  }
                />
                <span className="mt-1 block text-xs text-zinc-500">
                  每日扫描会用此提示词 + 最近 K 线/指标调 Gemini。决策按 (策略, 标的, 日期) 缓存，同日只调一次。
                </span>
              </label>
            )}
            {form.strategy_type === "composite" && (
              <div className="sm:col-span-2">
                <CompositeChildrenEditor
                  value={
                    (form.params.children as
                      | { strategy_id: number; weight: number }[]
                      | undefined) || []
                  }
                  candidates={list.filter(
                    (s) =>
                      s.strategy_type !== "composite" &&
                      s.is_active &&
                      (!editing || s.id !== editing.id)
                  )}
                  onChange={(children) =>
                    setForm((f) => ({
                      ...f,
                      params: { ...f.params, mode: "weighted", children },
                    }))
                  }
                />
              </div>
            )}
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              />
              设为默认策略（每日扫描与未指定时的回测）
            </label>
          </div>
          <label className="mt-4 block text-sm">
            <span className="stat-label">说明</span>
            <textarea
              className="input mt-1 w-full"
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          {typeMeta?.description && (
            <p className="mt-2 text-xs text-zinc-500">{typeMeta.description}</p>
          )}
          <div className="mt-4 flex gap-2">
            <button type="button" className="btn-primary" disabled={loading} onClick={save}>
              {loading ? "保存中…" : "保存"}
            </button>
            {editing && (
              <button
                type="button"
                className="btn-secondary text-red-400"
                disabled={loading || editing.is_default}
                onClick={() => remove(editing.id)}
              >
                删除
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function CompositeChildrenEditor({
  value,
  candidates,
  onChange,
}: {
  value: { strategy_id: number; weight: number }[];
  candidates: StrategyDefinition[];
  onChange: (next: { strategy_id: number; weight: number }[]) => void;
}) {
  const [selectId, setSelectId] = useState<number | "">("");
  const remaining = candidates.filter(
    (c) => !value.some((v) => v.strategy_id === c.id)
  );

  const add = () => {
    if (!selectId) return;
    onChange([...value, { strategy_id: Number(selectId), weight: 1 }]);
    setSelectId("");
  };

  const remove = (sid: number) =>
    onChange(value.filter((v) => v.strategy_id !== sid));

  const setWeight = (sid: number, w: number) =>
    onChange(
      value.map((v) => (v.strategy_id === sid ? { ...v, weight: w } : v))
    );

  const total = value.reduce((s, v) => s + (v.weight || 0), 0);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium">子策略与权重</span>
        <span className="text-xs text-zinc-500">
          权重总和 {total.toFixed(2)}（加权聚合，自动归一化）
        </span>
      </div>
      {value.length === 0 && (
        <p className="text-xs text-zinc-500">尚未选择子策略</p>
      )}
      <ul className="space-y-2">
        {value.map((v) => {
          const child = candidates.find((c) => c.id === v.strategy_id);
          return (
            <li
              key={v.strategy_id}
              className="flex items-center gap-3 rounded bg-zinc-900/60 px-3 py-2 text-sm"
            >
              <span className="flex-1">
                {child?.name || `#${v.strategy_id}`}
                <span className="ml-2 text-xs text-zinc-500">
                  ({child?.strategy_type || "?"})
                </span>
              </span>
              <input
                type="number"
                step="0.1"
                min="0"
                className="input w-24"
                value={v.weight}
                onChange={(e) =>
                  setWeight(v.strategy_id, parseFloat(e.target.value) || 0)
                }
              />
              <button
                type="button"
                className="text-xs text-red-400 hover:text-red-300"
                onClick={() => remove(v.strategy_id)}
              >
                移除
              </button>
            </li>
          );
        })}
      </ul>
      {remaining.length > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <select
            className="input flex-1"
            value={selectId}
            onChange={(e) => setSelectId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">选择子策略加入…</option>
            {remaining.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}（{c.strategy_type}）
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-secondary"
            disabled={!selectId}
            onClick={add}
          >
            添加
          </button>
        </div>
      )}
    </div>
  );
}
