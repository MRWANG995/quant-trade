"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BacktestDrawdownPoint } from "@/lib/api";

export function DrawdownChart({ data }: { data: BacktestDrawdownPoint[] }) {
  if (!data.length) return null;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.05} />
            <stop offset="100%" stopColor="#ef4444" stopOpacity={0.55} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} tickMargin={8} />
        <YAxis
          tick={{ fill: "#71717a", fontSize: 11 }}
          domain={[(dataMin: number) => Math.min(dataMin, 0), 0]}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip
          contentStyle={{
            background: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: 8,
          }}
          formatter={(value) => [`${value}%`, "回撤"]}
        />
        <Area
          type="monotone"
          dataKey="drawdown_pct"
          stroke="#ef4444"
          strokeWidth={1.5}
          fill="url(#ddFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
