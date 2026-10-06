/** ECharts React binding: lazy init (works when the container mounts late),
 *  resize observation, and option diffing. */
import { useCallback, useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

export type ChartEvents = Record<string, (params: unknown) => void>;

export function useECharts(option: EChartsOption, events?: ChartEvents) {
  const elRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const roRef = useRef<ResizeObserver | null>(null);
  const eventsRef = useRef<ChartEvents | undefined>(events);
  eventsRef.current = events;

  const ensure = useCallback(() => {
    const el = elRef.current;
    if (!el || chartRef.current) return chartRef.current;
    const chart = echarts.init(el);
    for (const name of Object.keys(eventsRef.current ?? {})) {
      chart.on(name, (p: unknown) => eventsRef.current?.[name]?.(p));
    }
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);
    roRef.current = ro;
    chartRef.current = chart;
    return chart;
  }, []);

  useEffect(() => {
    ensure()?.setOption(option, true);
  }, [option, ensure]);

  useEffect(
    () => () => {
      roRef.current?.disconnect();
      roRef.current = null;
      chartRef.current?.dispose();
      chartRef.current = null;
    },
    [],
  );

  return { elRef, chartRef };
}
