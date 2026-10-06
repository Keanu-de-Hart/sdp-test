/** Timeseries: added / removed / growth per bucket. Brush a range on the chart
 *  to set the dashboard time filter (H_i,j). */
import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { C, axisBase, tooltipBase } from "../lib/charts";
import { fmtInt, fmtSigned } from "../lib/format";
import { useMetrics } from "../lib/hooks";
import { DAY_S, bucketEndTs, tsToYmd } from "../lib/time";
import { useECharts } from "../lib/useECharts";
import { useFilters } from "../state/FiltersContext";
import type { TimeseriesResponse } from "../types";
import { ChartState } from "./ui";

export function GrowthTimeline() {
  const { repoId, apiFilters, filters, setFilters, mode } = useFilters();
  const { data, loading, error } = useMetrics<TimeseriesResponse>(
    repoId,
    "timeseries",
    apiFilters,
  );

  const items = useMemo(() => data?.items ?? [], [data]);
  const buckets = useMemo(() => items.map((i) => i.bucket), [items]);

  const option = useMemo<EChartsOption>(() => {
    const gran = filters.gran;
    const shortLabel = (b: string) => (gran === "month" ? b.slice(0, 7) : b.slice(5));
    return {
      animation: false,
      grid: { left: 58, right: 20, top: 36, bottom: 28 },
      legend: {
        top: 2,
        left: 4,
        textStyle: { color: C.text, fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8,
        icon: "roundRect",
      },
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        formatter: (ps: unknown) => {
          const arr = (Array.isArray(ps) ? ps : [ps]) as { dataIndex: number }[];
          const p = items[arr[0]?.dataIndex ?? -1];
          if (!p) return "";
          return (
            `<b>${p.bucket}</b><br/>` +
            `Added: <b>${fmtInt(p.added)}</b><br/>` +
            `Removed: <b>${fmtInt(p.removed)}</b><br/>` +
            `Growth: <b>${fmtSigned(p.growth)}</b><br/>` +
            `Churn: <b>${fmtInt(p.churn)}</b><br/>` +
            `Commits: <b>${fmtInt(p.commits)}</b>`
          );
        },
      },
      toolbox: {
        right: 10,
        top: 0,
        itemSize: 14,
        iconStyle: { borderColor: C.text },
        feature: {
          brush: {
            type: ["lineX"],
            title: { lineX: "Drag horizontally to set the time range" },
          },
        },
      },
      brush: {
        xAxisIndex: [0],
        brushMode: "single",
        transformable: false,
        throttleType: "debounce",
        throttleDelay: 300,
      },
      xAxis: {
        type: "category",
        data: buckets,
        ...axisBase,
        axisLabel: { color: C.text, fontSize: 11, formatter: shortLabel },
      },
      yAxis: {
        type: "value",
        ...axisBase,
        axisLabel: { color: C.text, fontSize: 11, formatter: (v: number) => fmtInt(Math.abs(v)) },
      },
      dataZoom: [{ type: "inside", xAxisIndex: 0 }],
      series: [
        {
          name: "Added",
          type: "line",
          data: items.map((i) => i.added),
          symbol: "none",
          lineStyle: { width: 1.5, color: C.added },
          itemStyle: { color: C.added },
          areaStyle: { color: "rgba(52, 211, 153, 0.18)" },
        },
        {
          name: "Removed",
          type: "line",
          data: items.map((i) => -i.removed),
          symbol: "none",
          lineStyle: { width: 1.5, color: C.removed },
          itemStyle: { color: C.removed },
          areaStyle: { color: "rgba(248, 113, 113, 0.16)" },
        },
        {
          name: "Growth",
          type: "line",
          data: items.map((i) => i.growth),
          symbol: "none",
          lineStyle: { width: 1.5, color: C.growth, type: "dashed" },
          itemStyle: { color: C.growth },
        },
      ],
    };
  }, [items, buckets, filters.gran]);

  const { elRef, chartRef } = useECharts(option, {
    brushEnd: (p) => {
      const params = p as { areas?: { coordRange?: number[] }[] };
      const range = params.areas?.[0]?.coordRange;
      if (!range || range.length < 2 || buckets.length === 0) return;
      const lo = Math.min(range[0], range[1]);
      const hi = Math.max(range[0], range[1]);
      const i0 = Math.max(0, Math.min(buckets.length - 1, Math.floor(lo)));
      const i1 = Math.max(0, Math.min(buckets.length - 1, Math.ceil(hi)));
      const endExclusive = bucketEndTs(buckets[i1], filters.gran);
      setFilters({
        start: buckets[i0],
        end: tsToYmd(endExclusive - DAY_S),
        commits: [],
      });
      chartRef.current?.dispatchAction({ type: "brush", areas: [] });
    },
  });

  const hasRange = !!(filters.start || filters.end) && mode === "range";

  /** Drop the H_i,j range filter and any painted brush area in one go. */
  const clearRange = () => {
    setFilters({ start: "", end: "" });
    chartRef.current?.dispatchAction({ type: "brush", areas: [] });
  };

  return (
    <section className="card">
      <header className="card-header">
        <span className="card-title">Growth timeline</span>
        <span className="card-sub">
          {filters.gran} buckets · {fmtInt(data?.commit_count ?? 0)} commits in H
        </span>
        <div className="card-actions">
          {hasRange && (
            <button
              type="button"
              className="btn ghost sm"
              onClick={clearRange}
              title="Clear the H_i,j time range filter"
            >
              Clear range
            </button>
          )}
          <span className="faint small">toolbox brush → sets time range</span>
        </div>
      </header>
      <div className="card-body">
        <ChartState loading={loading} error={error} empty={!loading && items.length === 0}>
          <div ref={elRef} className="chart" />
        </ChartState>
      </div>
    </section>
  );
}
