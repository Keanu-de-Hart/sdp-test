/** Summary cards: the seven commit-set numbers plus |H|. */
import { fmtInt, fmtRate, fmtSigned } from "../lib/format";
import { useMetrics } from "../lib/hooks";
import { useFilters } from "../state/FiltersContext";
import type { SummaryResponse } from "../types";
import { ErrorNote } from "./ui";

function Stat({
  label,
  value,
  foot,
  cls,
  loading,
}: {
  label: string;
  value: string;
  foot?: string;
  cls?: string;
  loading?: boolean;
}) {
  return (
    <div className="card stat-card">
      <span className="stat-label">{label}</span>
      {loading ? (
        <span className="skeleton" style={{ width: "65%", height: 24, display: "inline-block" }} />
      ) : (
        <span className={`stat-value ${cls ?? ""}`}>{value}</span>
      )}
      {foot && <span className="stat-foot">{foot}</span>}
    </div>
  );
}

export function SummaryCards() {
  const { repoId, apiFilters, filters, mode } = useFilters();
  const { data, loading, error } = useMetrics<SummaryResponse>(repoId, "summary", apiFilters);

  const scope = filters.path
    ? `/${filters.path}${filters.type === "dir" ? "/" : ""}`
    : "repository root";
  const skeleton = loading && !data;

  if (error && !data) return <ErrorNote>{error}</ErrorNote>;

  return (
    <div className="grid cols-4">
      <Stat label="Added lines" value={data ? fmtInt(data.added) : "–"} foot="Σ l⁺ over H" loading={skeleton} />
      <Stat label="Removed lines" value={data ? fmtInt(data.removed) : "–"} foot="Σ l⁻ over H" loading={skeleton} />
      <Stat
        label="Growth"
        value={data ? fmtSigned(data.growth) : "–"}
        cls={data && data.growth < 0 ? "neg" : "pos"}
        foot="δ = l⁺ − l⁻"
        loading={skeleton}
      />
      <Stat label="Churn" value={data ? fmtInt(data.churn) : "–"} foot="λ = l⁺ + l⁻" loading={skeleton} />
      <Stat
        label="Modifications"
        value={data ? fmtInt(data.modifications) : "–"}
        foot={`n_H,o @ ${scope}`}
        loading={skeleton}
      />
      <Stat
        label="Modification frequency"
        value={data ? fmtRate(data.modification_frequency) : "–"}
        foot="η = n_H,o ⁄ |H|"
        loading={skeleton}
      />
      <Stat
        label="Churn rate"
        value={data ? fmtRate(data.churn_rate) : "–"}
        foot="ρ = λ_H,o ⁄ |H|"
        loading={skeleton}
      />
      <Stat
        label="Commits |H|"
        value={data ? fmtInt(data.commit_count) : "–"}
        foot={mode === "manual" ? "manual commit selection" : "time range after filters"}
        loading={skeleton}
      />
    </div>
  );
}
