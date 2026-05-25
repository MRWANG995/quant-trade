import { fetchApiServer } from "@/lib/api-server";
import type { RunLog } from "@/lib/api";
import { StrategyFilter } from "@/components/StrategyFilter";

export const dynamic = "force-dynamic";

export default async function LogsPage({
  searchParams,
}: {
  searchParams: { strategy_id?: string };
}) {
  const sid = searchParams.strategy_id;
  const path = sid ? `/api/run-logs?strategy_id=${sid}` : "/api/run-logs";
  try {
    const logs = await fetchApiServer<RunLog[]>(path);
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">策略日志</h1>
          <p className="text-sm text-zinc-500">每日扫描与风控决策记录</p>
        </div>

        <StrategyFilter />

        <div className="space-y-3">
          {logs.length === 0 ? (
            <p className="text-sm text-zinc-500">暂无日志，请运行每日扫描</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="card">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-emerald-400">{log.run_type}</span>
                  <span className="text-xs text-zinc-500">{log.run_date}</span>
                </div>
                <p className="mt-2 text-sm">{log.message}</p>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="mt-3 overflow-x-auto rounded bg-zinc-950 p-3 text-xs text-zinc-400">
                    {JSON.stringify(log.details, null, 2)}
                  </pre>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    );
  } catch {
    return (
      <div className="card">
        <h1 className="text-xl font-bold">策略日志</h1>
        <p className="mt-2 text-sm text-zinc-500">请先启动后端 API</p>
      </div>
    );
  }
}
