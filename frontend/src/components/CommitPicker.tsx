/** Manual commit selection: searchable, paged multi-select over all commits.
 *  When commits are selected they form H directly (overriding the time range). */
import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDate, fmtInt, truncate } from "../lib/format";
import { useClickOutside } from "../lib/hooks";
import { useDebouncedValue } from "../lib/useDebounced";
import { useFilters } from "../state/FiltersContext";
import type { CommitItem } from "../types";

const PAGE = 100;
const MAX_WINDOW = 500;

export function CommitPicker() {
  const { repoId, filters, setFilters } = useFilters();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const qDeb = useDebouncedValue(q, 250);
  const [rows, setRows] = useState<CommitItem[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(PAGE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wrapRef = useClickOutside<HTMLDivElement>(() => setOpen(false));

  useEffect(() => {
    setLimit(PAGE);
  }, [qDeb]);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setLoading(true);
    api
      .getCommits(repoId, { q: qDeb, limit, offset: 0 })
      .then((r) => {
        if (!alive) return;
        setRows(r.items);
        setTotal(r.total);
        setError(null);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [open, repoId, qDeb, limit]);

  const selected = new Set(filters.commits);

  const toggle = (sha: string) => {
    const next = new Set(selected);
    if (next.has(sha)) next.delete(sha);
    else next.add(sha);
    setFilters({ commits: [...next] });
  };

  const count = filters.commits.length;

  return (
    <div className="field" ref={wrapRef} style={{ position: "relative" }}>
      <label>Commits</label>
      <div className="row">
        <button
          type="button"
          className={`btn${count > 0 ? " primary" : ""}`}
          style={{ minWidth: 160, justifyContent: "space-between" }}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="ellipsis">
            {count === 0 ? "Time range" : `${fmtInt(count)} selected`}
          </span>
          <span style={{ marginLeft: 8, opacity: 0.7 }}>▾</span>
        </button>
        {count > 0 && (
          <button
            type="button"
            className="btn ghost sm"
            title="Clear manual selection"
            onClick={() => setFilters({ commits: [] })}
          >
            ×
          </button>
        )}
      </div>

      {open && (
        <div className="popover right" style={{ width: 560 }}>
          <div className="popover-head">
            <input
              autoFocus
              placeholder="Search by SHA prefix, message, or author…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
              }}
              style={{ width: "100%" }}
            />
          </div>
          <div className="popover-list" style={{ maxHeight: 380 }}>
            {error && <div className="error-note">{error}</div>}
            {loading && rows.length === 0 && <div className="empty small">Loading commits…</div>}
            {!loading && rows.length === 0 && <div className="empty small">No commits match.</div>}
            {rows.map((c) => {
              const isSel = selected.has(c.sha);
              return (
                <div
                  key={c.sha}
                  className={`option${isSel ? " selected" : ""}`}
                  onClick={() => toggle(c.sha)}
                >
                  <input type="checkbox" checked={isSel} readOnly />
                  <span className="sha" title={c.sha}>{c.short}</span>
                  <div className="meta">
                    <div className="ellipsis" title={c.subject}>
                      {truncate(c.subject || "(no subject)", 64)}
                    </div>
                    <div className="faint small ellipsis">
                      {c.author} · {fmtDate(c.committer_ts)}
                    </div>
                  </div>
                </div>
              );
            })}
            {loading && rows.length > 0 && <div className="empty small">Loading…</div>}
          </div>
          <div className="popover-foot">
            <span className="faint small">
              {rows.length < total
                ? `Showing ${fmtInt(rows.length)} of ${fmtInt(total)} matches`
                : `${fmtInt(total)} match${total === 1 ? "" : "es"}`}
              {count > 0 ? ` · ${fmtInt(count)} selected` : ""}
            </span>
            <div className="row">
              {rows.length < total && rows.length < MAX_WINDOW && (
                <button
                  type="button"
                  className="btn sm"
                  disabled={loading}
                  onClick={() => setLimit((l) => Math.min(l + PAGE, MAX_WINDOW))}
                >
                  Load more
                </button>
              )}
              {count > 0 && (
                <button type="button" className="btn ghost sm" onClick={() => setFilters({ commits: [] })}>
                  Clear selection
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
