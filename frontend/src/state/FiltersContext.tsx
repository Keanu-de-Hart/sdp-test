/** Dashboard filter state, synced to the URL query string so any view is a
 *  shareable / bookmarkable link.
 *
 *  URL params: start, end (YYYY-MM-DD, `end` inclusive on that UTC day),
 *  commits (comma-separated SHAs, manual selection overriding the range),
 *  authors (comma-separated author keys), path + type (object scope),
 *  gran (timeseries bucket granularity). */
import { createContext, useCallback, useContext, useMemo } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { endOfDayTs, isGran, ymdToTs } from "../lib/time";
import type { Gran, MetricsFilters, ObjectType } from "../types";

export interface FilterState {
  start: string;
  end: string;
  commits: string[];
  authors: string[];
  path: string;
  type: ObjectType;
  gran: Gran;
}

function parse(sp: URLSearchParams): FilterState {
  const gran = sp.get("gran");
  return {
    start: sp.get("start") ?? "",
    end: sp.get("end") ?? "",
    commits: (sp.get("commits") ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    authors: (sp.get("authors") ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    path: sp.get("path") ?? "",
    type: sp.get("type") === "file" ? "file" : "dir",
    gran: isGran(gran) ? gran : "month",
  };
}

function serialize(f: FilterState): URLSearchParams {
  const sp = new URLSearchParams();
  if (f.start) sp.set("start", f.start);
  if (f.end) sp.set("end", f.end);
  if (f.commits.length) sp.set("commits", f.commits.join(","));
  if (f.authors.length) sp.set("authors", f.authors.join(","));
  if (f.path) {
    sp.set("path", f.path);
    sp.set("type", f.type);
  }
  if (f.gran !== "month") sp.set("gran", f.gran);
  return sp;
}

interface FiltersApi {
  repoId: number;
  filters: FilterState;
  /** 'manual' when a commit list is selected (overrides the time range). */
  mode: "range" | "manual";
  setFilters: (patch: Partial<FilterState>) => void;
  reset: () => void;
  /** Filters translated to the backend contract (UNIX seconds, exclusive end). */
  apiFilters: MetricsFilters;
}

const Ctx = createContext<FiltersApi | null>(null);

export function FiltersProvider({
  repoId,
  children,
}: {
  repoId: number;
  children: ReactNode;
}) {
  const [sp, setSp] = useSearchParams();
  const filters = useMemo(() => parse(sp), [sp]);

  const setFilters = useCallback(
    (patch: Partial<FilterState>) => {
      setSp(serialize({ ...parse(sp), ...patch }), { replace: true });
    },
    [sp, setSp],
  );

  const reset = useCallback(() => {
    setSp(new URLSearchParams(), { replace: true });
  }, [setSp]);

  const mode: "range" | "manual" = filters.commits.length ? "manual" : "range";

  const apiFilters = useMemo<MetricsFilters>(
    () => ({
      start: mode === "manual" ? null : ymdToTs(filters.start),
      end: mode === "manual" ? null : endOfDayTs(filters.end),
      commits: filters.commits,
      authors: filters.authors,
      path: filters.path || null,
      object_type: filters.path ? filters.type : null,
      granularity: filters.gran,
    }),
    [filters, mode],
  );

  const value = useMemo(
    () => ({ repoId, filters, mode, setFilters, reset, apiFilters }),
    [repoId, filters, mode, setFilters, reset, apiFilters],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFilters(): FiltersApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFilters must be used inside a FiltersProvider");
  return ctx;
}
