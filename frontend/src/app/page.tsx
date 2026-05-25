import { redirect } from "next/navigation";
import { fetchApiServer } from "@/lib/api-server";
import type { PortfolioSummary, Signal } from "@/lib/api";
import { DashboardClient } from "./DashboardClient";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let portfolio: PortfolioSummary | null = null;
  let signals: Signal[] = [];
  let error: string | null = null;

  try {
    [portfolio, signals] = await Promise.all([
      fetchApiServer<PortfolioSummary>("/api/portfolio"),
      fetchApiServer<Signal[]>("/api/signals"),
    ]);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "无法连接后端 API";
    // 后端启用了认证：把未登录用户直接送去登录页，比展示"后端未就绪"友好得多
    if (msg.includes("需要登录") || msg.includes("Unauthorized") || msg.includes("401")) {
      redirect("/login");
    }
    error = msg;
  }

  return (
    <DashboardClient
      portfolio={portfolio}
      signals={signals.slice(0, 10)}
      error={error}
    />
  );
}
