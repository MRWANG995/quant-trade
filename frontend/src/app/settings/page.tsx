import { fetchApiServer } from "@/lib/api-server";
import type { AppSettings, BrokersHealth, DataStatus } from "@/lib/api";
import { SettingsExtras } from "./SettingsExtras";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  try {
    const [settings, brokers, dataStatus] = await Promise.all([
      fetchApiServer<AppSettings>("/api/settings"),
      fetchApiServer<BrokersHealth>("/api/brokers/health"),
      fetchApiServer<DataStatus>("/api/data/status").catch(() => null),
    ]);
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">设置</h1>
          <p className="text-sm text-zinc-500">系统参数与券商接入（实盘占位）</p>
        </div>

        <div className="card">
          <h2 className="mb-4 font-semibold">交易参数</h2>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <Item label="券商模式" value={settings.broker_mode} />
            <Item label="初始资金" value={`$${settings.initial_capital.toLocaleString()}`} />
            <Item label="每日最大开仓" value={String(settings.max_trades_per_day)} />
            <Item label="单标的每日上限" value={String(settings.max_trades_per_symbol_per_day)} />
            <Item label="快线 MA" value={String(settings.fast_ma)} />
            <Item label="慢线 MA" value={String(settings.slow_ma)} />
            <Item label="定时任务 Cron" value={settings.daily_run_cron} />
          </dl>
        </div>

        <div className="card">
          <h2 className="mb-4 font-semibold">券商适配器状态</h2>
          <p className="mb-4 text-sm text-zinc-500">
            当前模式：<span className="text-emerald-400">{brokers.active_mode}</span>。
            实盘下单默认关闭，需完善适配器后切换 BROKER_MODE。
          </p>
          <div className="space-y-4">
            {Object.entries(brokers.brokers).map(([name, info]) => (
              <div key={name} className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                <h3 className="font-medium uppercase">{name}</h3>
                <dl className="mt-2 grid gap-1 text-sm text-zinc-400">
                  {Object.entries(info).map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <dt className="text-zinc-500">{k}:</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        </div>

        <SettingsExtras
          stooqConfigured={dataStatus?.stooq_configured ?? false}
          dataStatusMessage={dataStatus?.message}
        />

        <div className="card border-amber-900/30 bg-amber-950/10">
          <h2 className="mb-2 font-semibold text-amber-300">实盘接入步骤</h2>
          <ol className="list-decimal space-y-2 pl-5 text-sm text-zinc-400">
            <li>
              <strong className="text-zinc-300">OANDA（外汇）</strong>：在 .env 填写 OANDA_API_KEY、OANDA_ACCOUNT_ID，实现
              backend/app/brokers/oanda.py 后设置 BROKER_MODE=live_oanda
            </li>
            <li>
              <strong className="text-zinc-300">Interactive Brokers（期货/黄金）</strong>：启动 TWS Gateway，配置 IB_HOST/PORT，实现
              backend/app/brokers/ib.py 后设置 BROKER_MODE=live_ib
            </li>
            <li>上线前请更换 yfinance 为正式行情源，并自行完成合规审查</li>
          </ol>
        </div>
      </div>
    );
  } catch {
    return (
      <div className="card">
        <h1 className="text-xl font-bold">设置</h1>
        <p className="mt-2 text-sm text-zinc-500">请先启动后端 API</p>
      </div>
    );
  }
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="stat-label">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  );
}
