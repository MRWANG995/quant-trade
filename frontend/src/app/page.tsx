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
    error = e instanceof Error ? e.message : "无法连接后端 API";
  }

  return (
    <DashboardClient
      portfolio={portfolio}
      signals={signals.slice(0, 10)}
      error={error}
    />
  );
}
