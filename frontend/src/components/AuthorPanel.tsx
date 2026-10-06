/** Author metrics for the current object + filters: ownership donut and
 *  modification bars. Clicking an author toggles them into the filter. */
import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { C, tooltipBase } from "../lib/charts";
import { fmtInt, fmtPct } from "../lib/format";
import { useMetrics } from "../lib/hooks";
import { useECharts } from "../lib/useECharts";
import { useFilters } from "../state/FiltersContext";
import type { AuthorRow, AuthorsMetricsResponse } from "../types";
import { ChartState } from "./ui";

export function AuthorPanel() {
  const { repoId, apiFilters, filters, setFilters } = useFilters();
  const { data, loading, error } = useMetrics<AuthorsMetricsResponse>(
    repoId,
    "authors",
    apiFilters,
  );

  const items = useMemo(() => data?.items ?? [], [data]);
  const topDonut = useMemo(() => {
    const sorted = [...items].sort((a, b) => b.ownership - a.ownership);
    if (sorted.length <= 8) return sorted;
    const head = sorted.slice(0, 7);
    const rest = sorted.slice(7);
    return [
      ...head,
      {
        author_key: "__other__",
        author: `Other (${rest.length} authors)`,
        commits: rest.reduce((n, r) => n + r.commits, 0),
        modifications: rest.reduce((n, r) => n + r.modifications, 0),
        churn: rest.reduce((n, r) => n + r.churn, 0),
        ownership: rest.reduce((n, r) => n + r.ownership, 0),
      } satisfies AuthorRow,
    ];
  }, [items]);

  const selected = new Set(filters.authors);

  const donutOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [...C.series],
      tooltip: {
        ...tooltipBase,
        formatter: (p: unknown) => {
          const d = (p as { data: { name: string; value: number; churn: number; commits: number; key: string } }).data;
          return (
            `<b>${d.name}</b><br/>Ownership: <b>${fmtPct(d.value)}</b><br/>` +
            `Churn: ${fmtInt(d.churn)} · Commits: ${fmtInt(d.commits)}`
          );
        },
      },
      legend: {
        type: "scroll",
        orient: "vertical",
        right: 0,
        top: "middle",
        textStyle: { color: C.text, fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
        formatter: (name: string) => (name.length > 22 ? name.slice(0, 21) + "…" : name),
      },
      series: [
        {
          type: "pie",
          radius: ["48%", "74%"],
          center: ["34%", "52%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "#0b1220", borderWidth: 1.5 },
          label: { show: false },
          labelLine: { show: false },
          emphasis: { scale: true, scaleSize: 4 },
          data: topDonut.map((r) => ({
            name: r.author,
            value: Number(r.ownership.toFixed(5)),
            churn: r.churn,
            commits: r.commits,
            key: r.author_key,
          })),
        },
      ],
    }),
    [topDonut],
  );

  const barItems = useMemo(
    () => [...items].sort((a, b) => b.modifications - a.modifications).slice(0, 10),
    [items],
  );

  const barOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      grid: { left: 8, right: 46, top: 8, bottom: 8, containLabel: true },
      tooltip: {
        ...tooltipBase,
        formatter: (p: unknown) => {
          const d = (p as { data: { authorName: string; value: number; churn: number; commits: number; ownership: number } }).data;
          return (
            `<b>${d.authorName}</b><br/>Modifications: <b>${fmtInt(d.value)}</b><br/>` +
            `Churn: ${fmtInt(d.churn)} · Commits: ${fmtInt(d.commits)}<br/>` +
            `Ownership: ${fmtPct(d.ownership)}`
          );
        },
      },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: C.grid } },
        axisLabel: { color: C.text, fontSize: 11 },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: barItems.map((r) => r.author),
        axisLabel: { color: C.text, fontSize: 11, width: 130, overflow: "truncate" },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 16,
          itemStyle: { color: C.churn, borderRadius: [0, 4, 4, 0] },
          label: {
            show: true,
            position: "right",
            color: C.text,
            fontSize: 11,
            formatter: (p: unknown) => fmtInt((p as { value: number }).value),
          },
          data: barItems.map((r) => ({
            value: r.modifications,
            authorName: r.author,
            churn: r.churn,
            commits: r.commits,
            ownership: r.ownership,
            key: r.author_key,
          })),
        },
      ],
    }),
    [barItems],
  );

  const toggleAuthor = (key: string) => {
    if (key === "__other__") return;
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setFilters({ authors: [...next] });
  };

  const donutRef = useECharts(donutOption, {
    click: (p) => {
      const d = (p as { data?: { key?: string } }).data;
      if (d?.key) toggleAuthor(d.key);
    },
  });

  const barRef = useECharts(barOption, {
    click: (p) => {
      const d = (p as { data?: { key?: string } }).data;
      if (d?.key) toggleAuthor(d.key);
    },
  });

  return (
    <section className="card">
      <header className="card-header">
        <span className="card-title">Authors</span>
        <span className="card-sub">
          ownership ω = λ_H,o,a ⁄ λ_H,o · {fmtInt(data?.churn_total ?? 0)} churn total
        </span>
        <div className="card-actions">
          {selected.size > 0 && (
            <button
              type="button"
              className="btn ghost sm"
              onClick={() => setFilters({ authors: [] })}
            >
              Clear author filter
            </button>
          )}
          <span className="faint small">click to filter</span>
        </div>
      </header>
      <div className="card-body">
        <ChartState loading={loading} error={error} empty={!loading && items.length === 0}>
          <div ref={donutRef.elRef} className="chart" />
          <div ref={barRef.elRef} className="chart" style={{ height: 260, marginTop: 6 }} />
        </ChartState>
      </div>
    </section>
  );
}
