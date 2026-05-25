"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, displayName);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <div className="card">
        <h1 className="text-2xl font-bold">{mode === "login" ? "登录" : "注册"}</h1>
        <p className="mt-1 text-sm text-zinc-500">Quant Trade 量化交易系统</p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm">
            <span className="stat-label">邮箱</span>
            <input
              type="email"
              required
              className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          {mode === "register" && (
            <label className="block text-sm">
              <span className="stat-label">昵称（可选）</span>
              <input
                type="text"
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </label>
          )}
          <label className="block text-sm">
            <span className="stat-label">密码</span>
            <input
              type="password"
              required
              minLength={8}
              className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "处理中…" : mode === "login" ? "登录" : "注册"}
          </button>
        </form>

        <button
          type="button"
          className="mt-4 text-sm text-emerald-400 hover:underline"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "没有账号？注册" : "已有账号？登录"}
        </button>
      </div>
    </div>
  );
}
