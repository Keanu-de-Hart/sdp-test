/** Author multi-select. Merged identities collapse into a single option. */
import { useMemo, useState } from "react";
import { fmtInt } from "../lib/format";
import { useAuthors, useClickOutside } from "../lib/hooks";
import { useFilters } from "../state/FiltersContext";

interface AuthorOption {
  key: string;
  name: string;
  commits: number;
  emails: string[];
  isGroup: boolean;
}

export function useAuthorOptions(repoId: number) {
  const { data, loading, error } = useAuthors(repoId);
  const options = useMemo<AuthorOption[]>(() => {
    if (!data) return [];
    const map = new Map<string, AuthorOption>();
    for (const a of data.authors) {
      const key = a.group_id != null ? `m:${a.group_id}` : `i:${a.identity}`;
      const name = a.group_name ?? a.name;
      const existing = map.get(key);
      if (existing) {
        existing.commits += a.commits;
        existing.emails.push(a.email);
      } else {
        map.set(key, {
          key,
          name,
          commits: a.commits,
          emails: [a.email],
          isGroup: a.group_id != null,
        });
      }
    }
    return [...map.values()].sort((x, y) => y.commits - x.commits);
  }, [data]);
  return { options, loading, error };
}

export function AuthorSelect() {
  const { repoId, filters, setFilters } = useFilters();
  const { options, loading } = useAuthorOptions(repoId);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const wrapRef = useClickOutside<HTMLDivElement>(() => setOpen(false));

  const selected = new Set(filters.authors);
  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return options;
    return options.filter(
      (o) =>
        o.name.toLowerCase().includes(needle) ||
        o.emails.some((e) => e.toLowerCase().includes(needle)),
    );
  }, [options, q]);

  const toggle = (key: string) => {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    // keep a stable ordering that matches the option list
    const ordered = options.filter((o) => next.has(o.key)).map((o) => o.key);
    setFilters({ authors: ordered });
  };

  const count = filters.authors.length;

  return (
    <div className="field" ref={wrapRef} style={{ position: "relative" }}>
      <label>Authors</label>
      <div className="row">
        <button
          type="button"
          className="btn"
          style={{ minWidth: 170, justifyContent: "space-between" }}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="ellipsis">
            {count === 0 ? "All authors" : `${count} author${count > 1 ? "s" : ""}`}
          </span>
          <span className="faint" style={{ marginLeft: 8 }}>▾</span>
        </button>
        {count > 0 && (
          <button
            type="button"
            className="btn ghost sm"
            title="Clear author filter"
            onClick={() => setFilters({ authors: [] })}
          >
            ×
          </button>
        )}
      </div>

      {open && (
        <div className="popover" style={{ width: 380 }}>
          <div className="popover-head">
            <input
              autoFocus
              placeholder="Search name or email…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <div className="popover-list">
            {loading && <div className="empty small">Loading authors…</div>}
            {!loading && visible.length === 0 && <div className="empty small">No authors.</div>}
            {visible.map((o) => {
              const isSel = selected.has(o.key);
              return (
                <div
                  key={o.key}
                  className={`option${isSel ? " selected" : ""}`}
                  onClick={() => toggle(o.key)}
                >
                  <input type="checkbox" checked={isSel} readOnly />
                  <div className="meta">
                    <div className="row" style={{ gap: 6 }}>
                      <span className="ellipsis" style={{ fontWeight: 550 }}>{o.name}</span>
                      {o.isGroup && <span className="badge accent">merged</span>}
                    </div>
                    <div className="faint small ellipsis">
                      {o.emails.join(", ")}
                    </div>
                  </div>
                  <span className="faint small nowrap">{fmtInt(o.commits)} commits</span>
                </div>
              );
            })}
          </div>
          <div className="popover-foot">
            <span className="faint small">Selected authors narrow the commit set H.</span>
            <div className="row">
              {count > 0 && (
                <button type="button" className="btn ghost sm" onClick={() => setFilters({ authors: [] })}>
                  Clear
                </button>
              )}
              <button type="button" className="btn ghost sm" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
