"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "总览" },
  { href: "/instruments", label: "行情" },
  { href: "/strategies", label: "策略" },
  { href: "/backtest", label: "回测" },
  { href: "/orders", label: "交易" },
  { href: "/logs", label: "策略日志" },
  { href: "/settings", label: "设置" },
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout, loading } = useAuth();

  if (pathname === "/login") return null;

  return (
    <nav className="flex flex-wrap items-center gap-1 border-b border-zinc-800 bg-zinc-950 px-4 py-3">
      <span className="mr-4 font-semibold text-emerald-400">Quant Trade</span>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`rounded px-3 py-1.5 text-sm ${
            pathname === l.href
              ? "bg-emerald-600/20 text-emerald-300"
              : "text-zinc-400 hover:text-zinc-100"
          }`}
        >
          {l.label}
        </Link>
      ))}
      <div className="ml-auto flex items-center gap-2 text-sm">
        {!loading && user ? (
          <>
            <span className="text-zinc-500">{user.display_name || user.email}</span>
            <button type="button" className="btn-secondary px-2 py-1 text-xs" onClick={logout}>
              退出
            </button>
          </>
        ) : (
          !loading && (
            <Link href="/login" className="text-emerald-400 hover:underline">
              登录
            </Link>
          )
        )}
      </div>
    </nav>
  );
}
