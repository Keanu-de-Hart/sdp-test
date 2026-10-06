/** The dashboard filter bar: repo-scope, time range OR manual commit list,
 *  authors, path scope and timeseries granularity — all URL-synced. */
import { useFilters } from "../state/FiltersContext";
import type { Gran } from "../types";
import { AuthorSelect } from "./AuthorSelect";
import { CommitPicker } from "./CommitPicker";
import { PathPicker } from "./PathPicker";

export function FilterBar() {
  const { filters, setFilters, reset, mode } = useFilters();
  const manual = mode === "manual";

  const isDefault =
    !filters.start &&
    !filters.end &&
    filters.commits.length === 0 &&
    filters.authors.length === 0 &&
    !filters.path &&
    filters.gran === "month";

  return (
    <div className="card">
      <div className="filter-bar">
        <PathPicker />

        <div className="field">
          <label>From (inclusive)</label>
          <input
            type="date"
            value={filters.start}
            disabled={manual}
            title={manual ? "Ignored while a manual commit list is selected" : "H_t lower bound (UTC)"}
            onChange={(e) => setFilters({ start: e.target.value, commits: [] })}
          />
        </div>

        <div className="field">
          <label>To (inclusive)</label>
          <input
            type="date"
            value={filters.end}
            disabled={manual}
            title={manual ? "Ignored while a manual commit list is selected" : "H_i,j upper bound (UTC, inclusive)"}
            onChange={(e) => setFilters({ end: e.target.value, commits: [] })}
          />
        </div>

        <div className="field">
          <label>Bucket</label>
          <select
            value={filters.gran}
            onChange={(e) => setFilters({ gran: e.target.value as Gran })}
          >
            <option value="day">Day</option>
            <option value="week">Week</option>
            <option value="month">Month</option>
          </select>
        </div>

        <AuthorSelect />
        <CommitPicker />

        <button
          type="button"
          className="btn ghost"
          disabled={isDefault}
          onClick={reset}
          title="Clear every filter"
        >
          Clear all
        </button>
      </div>

      {manual && (
        <div className="filter-hint">
          <span className="badge accent">manual selection</span>
          <span>
            {filters.commits.length} commit{filters.commits.length === 1 ? "" : "s"} selected —
            the time range is ignored while a manual list is active.
          </span>
          <button
            type="button"
            className="btn ghost sm"
            onClick={() => setFilters({ commits: [] })}
          >
            Use the time range instead
          </button>
        </div>
      )}
    </div>
  );
}
