/** The commit set H itself: every commit after the filters, with its stats for
 *  the selected object (paged). */
import { useEffect, useState } from "react";
import { fmtDate, fmtInt } from "../lib/format";
import { useMetrics } from "../lib/hooks";
import { useFilters } from "../state/FiltersContext";
import type { CommitSetResponse } from "../types";
import { Empty, ErrorNote, Loading } from "./ui";

const PAGE_SIZE = 50;

export function CommitSetTable() {
  const { repoId, apiFilters, filters } = useFilters();
  const [onlyChanged, setOnlyChanged] = useState(false);
  const [page, setPage] = useState(0);
  const key = JSON.stringify(apiFilters);
  useEffect(() => {
    setPage(0);
  }, [key, onlyChanged]);

  const { data, loading, error } = useMetrics<CommitSetResponse>(repoId, "commits", {
    ...apiFilters,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    only_changed: onlyChanged,
  });

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const to = Math.min(total, (page + 1) * PAGE_SIZE);
  const hasScope = !!filters.path;

  return (
    <section className="card">
      <header className="card-header">
        <span className="card-title">Commit set H</span>
        <span className="card-sub">
          {fmtInt(total)} commit{total === 1 ? "" : "s"}
          {hasScope ? ` · stats for ${filters.type === "dir" ? `/${filters.path}/` : `/${filters.path}`}` : ""}
        </span>
        <div className="card-actions">
          <label className="row small muted" style={{ cursor: "pointer", gap: 6 }}>
            <input
              type="checkbox"
              checked={onlyChanged}
              onChange={(e) => setOnlyChanged(e.target.checked)}
            />
            only commits touching the scope
          </label>
        </div>
      </header>
      <div className="card-body flush">
        {error && !data ? (
          <ErrorNote>{error}</ErrorNote>
        ) : loading && !data ? (
          <Loading />
        ) : total === 0 ? (
          <Empty>
            No commits in H for the current filters.
            {onlyChanged ? " Try disabling “only commits touching the scope”." : ""}
          </Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Commit</th>
                    <th>Date</th>
                    <th>Author</th>
                    <th>Subject</th>
                    <th className="num">Added</th>
                    <th className="num">Removed</th>
                    <th className="num">Churn</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.items ?? []).map((r) => (
                    <tr key={r.sha}>
                      <td className="sha nowrap" title={r.sha}>{r.short}</td>
                      <td className="nowrap muted">{fmtDate(r.committer_ts)}</td>
                      <td className="ellipsis" style={{ maxWidth: 160 }} title={r.author}>
                        {r.author}
                      </td>
                      <td className="ellipsis" style={{ maxWidth: 280 }} title={r.subject}>
                        {r.subject || "(no subject)"}
                      </td>
                      <td className="num pos">{fmtInt(r.added)}</td>
                      <td className="num neg">{fmtInt(r.removed)}</td>
                      <td className="num">{fmtInt(r.churn)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="popover-foot">
              <span className="faint small">
                Showing {fmtInt(from)}–{fmtInt(to)} of {fmtInt(total)}
                {loading ? " · updating…" : ""}
              </span>
              <div className="row">
                <button
                  type="button"
                  className="btn sm"
                  disabled={page === 0 || loading}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  ← Newer
                </button>
                <span className="faint small">
                  page {page + 1} / {pages}
                </span>
                <button
                  type="button"
                  className="btn sm"
                  disabled={page + 1 >= pages || loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Older →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
