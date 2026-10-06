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
  children,
}: {
  loading: boolean;
  error: string | null;
  empty: boolean;
  children: ReactNode;
}) {
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (loading && empty) return <Loading />;
  if (empty) return <Empty>No data for the current selection.</Empty>;
  return <>{children}</>;
}
