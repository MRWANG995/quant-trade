"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type StrategyDefinition } from "@/lib/api";

export function StrategyFilter() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = searchParams.get("strategy_id") || "";
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);

  useEffect(() => {
    api.getStrategies().then(setStrategies).catch(() => {});
  }, []);

  const onChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const params = new URLSearchParams(searchParams.toString());
    if (e.target.value) {
      params.set("strategy_id", e.target.value);
    } else {
      params.delete("strategy_id");
    }
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  };

  return (
    <label className="block text-sm">
      <span className="stat-label">按策略过滤</span>
      <select
        className="input mt-1 w-full sm:w-72"
        value={current}
        onChange={onChange}
      >
        <option value="">全部策略</option>
        {strategies.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
            {s.is_default ? "（默认）" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
