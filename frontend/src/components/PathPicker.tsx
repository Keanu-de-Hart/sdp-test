/** Object scope picker: search files and directories of the indexed repo. */
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useClickOutside } from "../lib/hooks";
import { useDebouncedValue } from "../lib/useDebounced";
import { useFilters } from "../state/FiltersContext";
import type { PathItem } from "../types";

export function PathPicker() {
  const { repoId, filters, setFilters } = useFilters();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const qDeb = useDebouncedValue(q, 220);
  const [items, setItems] = useState<PathItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const wrapRef = useClickOutside<HTMLDivElement>(() => setOpen(false));

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setLoading(true);
    api
      .getPaths(repoId, qDeb, 60)
      .then((r) => {
        if (!alive) return;
        setItems(r.items);
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
  }, [open, repoId, qDeb]);

  useEffect(() => {
    if (open) window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  const label = filters.path
    ? `/${filters.path}${filters.type === "dir" ? "/" : ""}`
    : "/ (repository root)";

  const pick = (it: PathItem) => {
    setFilters({ path: it.path, type: it.type });
    setOpen(false);
    setQ("");
  };

  return (
    <div className="field" ref={wrapRef} style={{ position: "relative" }}>
      <label>Object scope</label>
      <div className="row">
        <button
          type="button"
          className="btn"
          style={{ minWidth: 230, justifyContent: "space-between", maxWidth: 340 }}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="mono ellipsis" style={{ fontSize: 12 }}>{label}</span>
          <span className="faint" style={{ marginLeft: 8 }}>▾</span>
        </button>
        {filters.path && (
          <button
            type="button"
            className="btn ghost sm"
            title="Scope to the repository root"
            onClick={() => setFilters({ path: "", type: "dir" })}
          >
            ×
          </button>
        )}
      </div>

      {open && (
        <div className="popover" style={{ width: 420 }}>
          <div className="popover-head">
            <input
              ref={inputRef}
              placeholder="Search files and directories…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && items.length > 0) pick(items[0]);
                if (e.key === "Escape") setOpen(false);
              }}
              style={{ width: "100%" }}
            />
          </div>
          <div className="popover-list">
            {error && <div className="error-note">{error}</div>}
            {loading && items.length === 0 && <div className="empty small">Searching…</div>}
            {!loading && items.length === 0 && <div className="empty small">No match.</div>}
            {items.map((it) => {
              const selected = it.path === filters.path && it.type === filters.type;
              return (
                <div
                  key={`${it.type}:${it.path}`}
                  className={`option${selected ? " selected" : ""}`}
                  onClick={() => pick(it)}
                >
                  <span className={`badge${it.type === "dir" ? " accent" : ""}`}>{it.type}</span>
                  <span className="mono ellipsis" style={{ flex: 1, fontSize: 12 }}>
                    {it.label}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="popover-foot">
            <span className="faint small">Pick a directory to scope all metrics to it.</span>
            <button type="button" className="btn ghost sm" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
