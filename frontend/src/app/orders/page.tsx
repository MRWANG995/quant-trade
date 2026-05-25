import { fetchApiServer } from "@/lib/api-server";
import type { Order, PortfolioSummary } from "@/lib/api";
import { StrategyFilter } from "@/components/StrategyFilter";

export const dynamic = "force-dynamic";

export default async function OrdersPage({
  searchParams,
}: {
  searchParams: { strategy_id?: string };
}) {
  const sid = searchParams.strategy_id;
  const ordersPath = sid ? `/api/orders?strategy_id=${sid}` : "/api/orders";
  try {
    const [orders, portfolio] = await Promise.all([
      fetchApiServer<Order[]>(ordersPath),
      fetchApiServer<PortfolioSummary>("/api/portfolio"),
    ]);
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">交易</h1>
          <p className="text-sm text-zinc-500">
            模拟盘委托与持仓 · 每日额度 {portfolio.trades_today}/{portfolio.max_trades_per_day}
          </p>
        </div>

        <StrategyFilter />

        {portfolio.positions.length > 0 && (
          <div className="card">
            <h2 className="mb-4 font-semibold">持仓</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500">
                  <th className="pb-2">品种</th>
                  <th>数量</th>
                  <th>均价</th>
                  <th>浮动盈亏</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((p) => (
                  <tr key={p.symbol} className="border-t border-zinc-800">
                    <td className="py-2">{p.symbol}</td>
                    <td>{p.quantity}</td>
                    <td>{p.avg_price.toFixed(4)}</td>
                    <td className={p.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                      ${p.unrealized_pnl}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="card">
          <h2 className="mb-4 font-semibold">委托记录</h2>
          {orders.length === 0 ? (
            <p className="text-sm text-zinc-500">暂无订单</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500">
                  <th className="pb-2">ID</th>
                  <th>品种</th>
                  <th>日期</th>
                  <th>方向</th>
                  <th>数量</th>
                  <th>状态</th>
                  <th>成交价</th>
                  <th>券商</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-t border-zinc-800">
                    <td className="py-1">{o.id}</td>
                    <td>{o.symbol}</td>
                    <td>{o.order_date}</td>
                    <td className={o.side === "buy" ? "text-emerald-400" : "text-red-400"}>
                      {o.side === "buy" ? "买入" : "卖出"}
                    </td>
                    <td>{o.quantity}</td>
                    <td>{o.status}</td>
                    <td>{o.fill_price?.toFixed(4) ?? "-"}</td>
                    <td>{o.broker}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    );
  } catch {
    return (
      <div className="card">
        <h1 className="text-xl font-bold">交易</h1>
        <p className="mt-2 text-sm text-zinc-500">请先启动后端 API</p>
      </div>
    );
  }
}
