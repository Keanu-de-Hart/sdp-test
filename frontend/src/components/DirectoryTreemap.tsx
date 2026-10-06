/** Directory treemap: size = churn, colour = growth (red↘ … green↗).
 *  Clicking a cell scopes every metric to that directory. */
import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { divergingColor, tooltipBase } from "../lib/charts";
import { fmtInt, fmtSigned } from "../lib/format";
import { useMetrics } from "../lib/hooks";
import { useECharts } from "../lib/useECharts";
import { useFilters } from "../state/FiltersContext";
import type { DirRow, DirsResponse } from "../types";
import { ChartState } from "./ui";

interface TreeNode {
  name: string;
  path: string;
  value: number;
  growth: number;
  added: number;
  removed: number;
  modifications: number;
  itemStyle: { color: string };
  children?: TreeNode[];
}

function leafName(path: string, scope: string): string {
  if (!path) return "/";
  const base = path.slice(scope ? scope.length + 1 : 0);
  return base || path;
}

function buildTree(items: DirRow[], scope: string, maxAbsGrowth: number): TreeNode | null {
  const nodes = new Map<string, TreeNode>();
  for (const it of items) {
    nodes.set(it.path, {
      name: leafName(it.path, scope),
      path: it.path,
      value: Math.max(it.churn, 1),
      growth: it.growth,
      added: it.added,
      removed: it.removed,
      modifications: it.modifications,
      itemStyle: { color: divergingColor(it.growth, maxAbsGrowth) },
    });
  }
  const scopeNode = nodes.get(scope);
  if (!scopeNode) return null;
  for (const [path, node] of nodes) {
    if (path === scope) continue;
    const parentPath = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
    const parent = nodes.get(parentPath);
    if (parent) (parent.children ??= []).push(node);
  }
  const sortChildren = (n: TreeNode) => {
    if (n.children) {
      n.children.sort((a, b) => b.value - a.value);
      n.children.forEach(sortChildren);
    }
  };
  sortChildren(scopeNode);
  return scopeNode;
}

export function DirectoryTreemap() {
  const { repoId, apiFilters, filters, setFilters } = useFilters();
  const isFileScope = filters.type === "file" && !!filters.path;
  const scope = isFileScope ? "" : filters.path;
  const { data, loading, error } = useMetrics<DirsResponse>(repoId, "dirs", apiFilters, !isFileScope);

  const scopeNode = useMemo(() => {
    if (!data) return null;
    const maxAbs = Math.max(1, ...data.items.map((i) => Math.abs(i.growth)));
    return buildTree(data.items, scope, maxAbs);
  }, [data, scope]);

  const children = scopeNode?.children ?? [];

  const option = useMemo<EChartsOption>(
    () => ({
      animation: false,
      tooltip: {
        ...tooltipBase,
        formatter: (p: unknown) => {
          const d = (p as { data?: TreeNode }).data;
          if (!d) return "";
          const where = d.path ? `/${d.path}/` : "/ (repository root)";
          return (
            `<b>${where}</b><br/>` +
            `Churn: <b>${fmtInt(d.value)}</b><br/>` +
            `Added: ${fmtInt(d.added)} · Removed: ${fmtInt(d.removed)}<br/>` +
            `Growth: <b>${fmtSigned(d.growth)}</b><br/>` +
            `Modifications: ${fmtInt(d.modifications)}`
          );
        },
      },
      series: [
        {
          type: "treemap",
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          width: "100%",
          height: "100%",
          top: 2,
          left: 2,
          right: 2,
          bottom: 2,
          visibleMin: 160,
          data: children,
          label: { color: "#eaf1fb", fontSize: 11, overflow: "truncate" },
          itemStyle: { borderColor: "#0b1220", borderWidth: 2, gapWidth: 2 },
        },
      ],
    }),
    [children],
  );

  const { elRef } = useECharts(option, {
    click: (p) => {
      const d = (p as { data?: TreeNode }).data;
      if (d && typeof d.path === "string" && d.path !== filters.path) {
        setFilters({ path: d.path, type: "dir" });
      }
    },
  });

  const parent = filters.path.includes("/")
    ? filters.path.slice(0, filters.path.lastIndexOf("/"))
    : "";

  return (
    <section className="card">
      <header className="card-header">
        <span className="card-title">Directories</span>
        <span className="card-sub">size = churn · colour = growth</span>
        <div className="card-actions">
          {filters.path !== "" && (
            <button
              type="button"
              className="btn ghost sm"
              onClick={() => setFilters({ path: parent, type: "dir" })}
            >
              ↑ Up
            </button>
          )}
          <span className="faint small">click a cell to scope</span>
        </div>
      </header>
      <div className="card-body">
        {isFileScope ? (
          <div className="empty">
            A file is selected as the object scope — pick a <b>directory</b> (or the root) to see
            the treemap.
          </div>
        ) : (
          <ChartState
            loading={loading}
            error={error}
            empty={!loading && children.length === 0}
          >
            <div ref={elRef} className="chart tall" />
          </ChartState>
        )}
      </div>
    </section>
  );
}
