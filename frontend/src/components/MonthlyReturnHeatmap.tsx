"use client";

import type { BacktestMonthlyReturn } from "@/lib/api";

const MONTH_LABELS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

function cellColor(ret: number | null): string {
  if (ret === null) return "bg-zinc-900/40 text-zinc-600";
  return ret >= 0 ? "text-emerald-100" : "text-red-100";
}

function cellStyle(ret: number | null): React.CSSProperties {
  if (ret === null) return {};
  const max = 5;
  const ratio = Math.min(Math.abs(ret) / max, 1);
  const alpha = 0.18 + ratio * 0.62;
  const color = ret >= 0 ? `rgba(34,197,94,${alpha})` : `rgba(239,68,68,${alpha})`;
  return { backgroundColor: color };
}

export function MonthlyReturnHeatmap({ data }: { data: BacktestMonthlyReturn[] }) {
  if (!data.length) {
    return <p className="text-sm text-zinc-500">暂无月度数据</p>;
  }

  // 组装年 -> {month -> return} 与年度收益
  const byYear = new Map<number, Map<number, number>>();
  for (const row of data) {
    const months = byYear.get(row.year) ?? new Map<number, number>();
    months.set(row.month, row.return_pct);
    byYear.set(row.year, months);
  }
  const years = Array.from(byYear.keys()).sort((a, b) => a - b);

  // 年度收益：(1+r1)*(1+r2)*...-1，单位 %
  const yearTotals = new Map<number, number>();
  for (const y of years) {
    const months = byYear.get(y)!;
    let acc = 1;
    months.forEach((m) => {
      acc *= 1 + m / 100;
    });
    yearTotals.set(y, (acc - 1) * 100);
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs">
        <thead>
          <tr className="text-zinc-500">
            <th className="px-2 py-1 text-left">年</th>
            {MONTH_LABELS.map((m) => (
              <th key={m} className="px-2 py-1 text-center font-normal">
                {m}
              </th>
            ))}
            <th className="px-2 py-1 text-center font-semibold text-zinc-400">全年</th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => {
            const months = byYear.get(year)!;
            const total = yearTotals.get(year)!;
            return (
              <tr key={year}>
                <td className="px-2 py-1 text-zinc-300">{year}</td>
                {MONTH_LABELS.map((_, idx) => {
                  const m = idx + 1;
                  const ret = months.get(m) ?? null;
                  return (
                    <td
                      key={m}
                      className={`px-2 py-1 text-center tabular-nums ${cellColor(ret)}`}
                      style={cellStyle(ret)}
                      title={ret !== null ? `${year}-${String(m).padStart(2, "0")}: ${ret.toFixed(2)}%` : "无数据"}
                    >
                      {ret !== null ? ret.toFixed(1) : "—"}
                    </td>
                  );
                })}
                <td
                  className={`px-2 py-1 text-center font-semibold tabular-nums ${
                    total >= 0 ? "text-emerald-300" : "text-red-300"
                  }`}
                >
                  {total.toFixed(1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-zinc-500">单位 %；绿=正、红=负，色深与绝对值成正比（满色对应 ±5%）。</p>
    </div>
  );
}
