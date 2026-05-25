"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function EquityChart({
  data,
}: {
  data: Array<{ date: string; equity: number }>;
}) {
  if (!data.length) return null;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} tickMargin={8} />
        <YAxis tick={{ fill: "#71717a", fontSize: 11 }} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{
            background: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: 8,
          }}
        />
        <Line type="monotone" dataKey="equity" stroke="#22c55e" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
