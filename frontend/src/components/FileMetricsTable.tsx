/** Per-file commit-set metrics table with client-side sorting and CSV export. */
import { useMemo, useState } from "react";
import { downloadCsv } from "../lib/csv";
import { fmtInt, fmtRate, fmtSigned } from "../lib/format";
import { useMetrics } from "../lib/hooks";
import { useFilters } from "../state/FiltersContext";
import type { FileRow, FilesResponse } from "../types";
import { Empty, ErrorNote, Loading } from "./ui";

type SortKey =
  | "path"
  | "added"
  | "removed"
  | "growth"
  | "churn"
  | "modifications"
  | "modification_frequency"
  | "churn_rate";

export function FileMetricsTable({ repoName }: { repoName: string }) {
  const { repoId, apiFilters } = useFilters();
  const { data, loading, error } = useMetrics<FilesResponse>(repoId, "files", {
    ...apiFilters,
    limit: 5000,
  });
  const [sortKey, setSortKey] = useState<SortKey>("churn");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);

  const rows = useMemo(() => {
    const items = [...(data?.items ?? [])];
    items.sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (typeof va === "string" || typeof vb === "string") {
        return String(va).localeCompare(String(vb)) * sortDir;
      }
      return (va - vb) * sortDir;
    });
    return items;
  }, [data, sortKey, sortDir]);

  const onSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(key === "path" ? 1 : -1);
    }
  };

  const th = (key: SortKey, label: string, num = true) => (
    <th
      className={`sortable${num ? " num" : ""}`}
      onClick={() => onSort(key)}
      title="Click to sort"
    >
      {label}
      {sortKey === key ? (sortDir === 1 ? " ↑" : " ↓") : ""}
    </th>
  );

  const exportCsv = () => {
    const safe = repoName.replace(/[^a-z0-9_-]+/gi, "_") || "repo";
    downloadCsv(
      `${safe}_file_metrics.csv`,
      [
        "path",
        "added",
        "removed",
        "growth",
        "churn",
        "modifications",
        "modification_frequency",
        "churn_rate",
      ],
      rows.map((r) => [
        r.path,
        r.added,
        r.removed,
        r.growth,
        r.churn,
        r.modifications,
        r.modification_frequency.toFixed(5),
        r.churn_rate.toFixed(5),
      ]),
    );
  };

  return (
    <section className="card">
      <header className="card-header">
        <span className="card-title">Files</span>
        <span className="card-sub">
          {fmtInt(rows.length)} files · |H| = {fmtInt(data?.commit_count ?? 0)} commits
        </span>
        <div className="card-actions">
          <button
            type="button"
            className="btn ghost sm"
            onClick={exportCsv}
            disabled={rows.length === 0}
          >
            Export CSV
          </button>
        </div>
      </header>
      <div className="card-body flush">
        {error && !data ? (
          <ErrorNote>{error}</ErrorNote>
        ) : loading && !data ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty>No files for the current selection.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  {th("path", "Path", false)}
                  {th("added", "Added")}
                  {th("removed", "Removed")}
                  {th("growth", "Growth")}
                  {th("churn", "Churn")}
                  {th("modifications", "Mods")}
                  {th("modification_frequency", "η")}
                  {th("churn_rate", "ρ")}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.path}>
                    <td className="mono ellipsis" style={{ maxWidth: 320 }} title={r.path}>
                      {r.path}
                    </td>
                    <td className="num pos">{fmtInt(r.added)}</td>
                    <td className="num neg">{fmtInt(r.removed)}</td>
                    <td className={`num ${r.growth < 0 ? "neg" : ""}`}>{fmtSigned(r.growth)}</td>
                    <td className="num">{fmtInt(r.churn)}</td>
                    <td className="num">{fmtInt(r.modifications)}</td>
                    <td className="num muted">{fmtRate(r.modification_frequency)}</td>
                    <td className="num muted">{fmtRate(r.churn_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
