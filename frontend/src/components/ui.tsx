/** Small presentational primitives shared by pages. */
import type { ReactNode } from "react";
import type { RepoStatus } from "../types";

export function StatusBadge({ status }: { status: RepoStatus }) {
  const cls =
    status === "ready" ? "pos" : status === "error" ? "neg" : "warn";
  return <span className={`badge ${cls}`}>{status}</span>;
}

export function Progress({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  return (
    <div className="progress" title={`${(pct * 100).toFixed(0)}%`}>
      <span style={{ width: `${pct * 100}%` }} />
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div className="error-note">{children}</div>;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="empty">
      <span className="spinner" /> <span style={{ marginLeft: 8 }}>{label}</span>
    </div>
  );
}

export function ChartState({
  loading,
  error,
  empty,
  emptyMessage,
  children,
}: {
  loading: boolean;
  error: string | null;
  empty: boolean;
  emptyMessage?: string;
  children: ReactNode;
}) {
  // Children stay mounted underneath the overlay so an ECharts canvas is
  // never detached (detached charts cannot be re-attached; re-init is costly).
  const overlay = error ? (
    <ErrorNote>{error}</ErrorNote>
  ) : loading && empty ? (
    <Loading />
  ) : empty ? (
    <Empty>{emptyMessage ?? "No data for the current selection."}</Empty>
  ) : null;
  return (
    <div className="chart-state">
      {children}
      {overlay !== null && <div className="chart-overlay">{overlay}</div>}
    </div>
  );
}
