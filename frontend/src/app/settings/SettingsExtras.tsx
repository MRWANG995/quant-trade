"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function SettingsExtras({
  stooqConfigured,
  dataStatusMessage,
}: {
  stooqConfigured: boolean;
  dataStatusMessage?: string;
}) {
  const [stooqMsg, setStooqMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const testStooq = async () => {
    setLoading(true);
    setStooqMsg(null);
    try {
      const r = await api.testStooq();
      setStooqMsg(
        r.ok
          ? `✓ ${r.message}（${r.bar_count} 根，最新 ${r.last_date}）`
          : `✗ ${r.message}`
      );
    } catch (e) {
      setStooqMsg(e instanceof Error ? e.message : "测试失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="card">
        <h2 className="mb-4 font-semibold">行情数据源</h2>
        <p className="mb-2 text-sm text-zinc-500">
          Stooq：{stooqConfigured ? "已配置（可选）" : "未配置 — 不影响使用"} ·
          零 Key 时外汇走 Frankfurter，黄金/期货灌库后自动演示补全
        </p>
        {dataStatusMessage && <p className="mb-3 text-xs text-zinc-500">{dataStatusMessage}</p>}
        <button type="button" className="btn-secondary" disabled={loading} onClick={testStooq}>
          测试 Stooq Key
        </button>
        {stooqMsg && <p className="mt-2 text-xs text-zinc-400">{stooqMsg}</p>}
        <p className="mt-3 text-xs text-zinc-600">
          申请 Key：
          <a
            href="https://stooq.com/q/d/?s=eurusd&get_apikey"
            className="text-emerald-500 hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            stooq.com
          </a>
          ，写入 backend/.env 的 STOOQ_API_KEY
        </p>
      </div>

      <div className="card border-zinc-700">
        <h2 className="mb-2 font-semibold">PostgreSQL 生产部署</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-zinc-400">
          <li>
            <code className="text-emerald-400">docker compose up -d</code> 启动 Postgres + API + 前端
          </li>
          <li>修改 compose 中 SECRET_KEY、ADMIN_PASSWORD，并配置 STOOQ_API_KEY</li>
          <li>访问 http://localhost:9998 ，默认账号见 compose 环境变量</li>
          <li>登录后执行「全量灌库」同步 K 线</li>
        </ol>
      </div>
    </>
  );
}
