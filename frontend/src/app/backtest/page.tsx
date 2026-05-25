import { BacktestClient } from "./BacktestClient";
import { fetchApiServer } from "@/lib/api-server";
import type { BacktestSummary, Instrument } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BacktestPage({
  searchParams,
}: {
  searchParams: { strategy_id?: string };
}) {
  const sid = searchParams.strategy_id;
  const historyPath = sid ? `/api/backtests?strategy_id=${sid}` : "/api/backtests";
  try {
    const [history, instruments] = await Promise.all([
      fetchApiServer<BacktestSummary[]>(historyPath),
      fetchApiServer<Instrument[]>("/api/instruments"),
    ]);
    return <BacktestClient history={history} instruments={instruments} />;
  } catch {
    return (
      <div className="card">
        <h1 className="text-xl font-bold">回测</h1>
        <p className="mt-2 text-sm text-zinc-500">请先启动后端 API</p>
      </div>
    );
  }
}
