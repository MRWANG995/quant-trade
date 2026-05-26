"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import type { Bar } from "@/lib/api";

export type ChartMarker = {
  time: string;
  kind: "entry" | "exit";
  side: string;
  price?: number;
  text?: string;
};

export type LineOverlay = {
  time: string;
  value: number;
};

export type PriceLevel = {
  label: string;
  price: number;
  color: string;       // hex
  lineStyle?: "solid" | "dashed" | "dotted";
};

type Props = {
  bars: Bar[];
  markers?: ChartMarker[];
  overlays?: {
    fast_ma?: LineOverlay[];
    slow_ma?: LineOverlay[];
  };
  // 水平价位线（Agent 看盘的 entry / stop_loss / take_profit）
  priceLevels?: PriceLevel[];
  height?: number;
};

export function CandlestickChart({ bars, markers = [], overlays, priceLevels = [], height = 420 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: { background: { type: ColorType.Solid, color: "#09090b" }, textColor: "#a1a1aa" },
      grid: { vertLines: { color: "#27272a" }, horzLines: { color: "#27272a" } },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    series.setData(
      bars.map((b) => ({
        time: b.trade_date as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    );

    if (overlays?.fast_ma?.length) {
      const fast = chart.addSeries(LineSeries, {
        color: "#38bdf8",
        lineWidth: 1,
        title: "快线",
      });
      fast.setData(
        overlays.fast_ma.map((p) => ({ time: p.time as Time, value: p.value }))
      );
    }
    if (overlays?.slow_ma?.length) {
      const slow = chart.addSeries(LineSeries, {
        color: "#f97316",
        lineWidth: 1,
        title: "慢线",
      });
      slow.setData(
        overlays.slow_ma.map((p) => ({ time: p.time as Time, value: p.value }))
      );
    }

    const lwMarkers: SeriesMarker<Time>[] = markers.map((m) => {
      const isLong = m.side === "long";
      const isEntry = m.kind === "entry";
      if (isEntry) {
        return {
          time: m.time as Time,
          position: isLong ? "belowBar" : "aboveBar",
          color: isLong ? "#22c55e" : "#ef4444",
          shape: isLong ? "arrowUp" : "arrowDown",
          text: m.text || "入",
        };
      }
      return {
        time: m.time as Time,
        position: isLong ? "aboveBar" : "belowBar",
        color: "#a1a1aa",
        shape: isLong ? "arrowDown" : "arrowUp",
        text: m.text || "出",
      };
    });

    if (lwMarkers.length > 0) {
      createSeriesMarkers(series, lwMarkers);
    }

    // Agent 看盘价位线：entry/SL/TP 以水平虚线画在主图上
    for (const lvl of priceLevels) {
      const styleMap: Record<string, LineStyle> = {
        solid: LineStyle.Solid,
        dashed: LineStyle.Dashed,
        dotted: LineStyle.Dotted,
      };
      series.createPriceLine({
        price: lvl.price,
        color: lvl.color,
        lineWidth: 2,
        lineStyle: styleMap[lvl.lineStyle || "dashed"],
        axisLabelVisible: true,
        title: lvl.label,
      });
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [bars, markers, overlays, priceLevels, height]);

  if (bars.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-zinc-800 text-zinc-500"
        style={{ height }}
      >
        暂无 K 线。请在左侧选择品种，或在「行情」页点击「同步行情」
      </div>
    );
  }

  return <div ref={containerRef} className="w-full rounded-lg border border-zinc-800" />;
}
