/** Data-fetching hooks (polling repo status, SWR-style metrics, author list). */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AuthorsResponse, MetricsFilters, RepoInfo } from "../types";
import { useDebouncedValue } from "./useDebounced";

const ACTIVE_STATUSES = new Set(["pending", "cloning", "extracting", "indexing"]);

export function isRepoActive(status: string | undefined): boolean {
  return status != null && ACTIVE_STATUSES.has(status);
}

/** Fetch one repository and keep polling while ingestion is in progress. */
export function useRepo(repoId: number, pollMs = 1500) {
  const [repo, setRepo] = useState<RepoInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;

    const load = async () => {
      try {
        const r = await api.getRepo(repoId);
        if (!alive) return;
        setRepo(r);
        setError(null);
        setLoading(false);
        if (isRepoActive(r.status)) {
          timer = window.setTimeout(() => void load(), pollMs);
        }
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      }
    };

    setLoading(true);
    void load();
    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [repoId, pollMs]);

  return { repo, loading, error };
}

/** Run a metric view; filters are debounced and stale data is kept while a new
 *  query is in flight (charts do not flash empty). */
export function useMetrics<T>(
  repoId: number,
  view: string,
  filters: MetricsFilters,
  enabled = true,
) {
  const key = JSON.stringify(filters);
  const debouncedKey = useDebouncedValue(key, 220);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // drop stale data of a previously viewed repository
  useEffect(() => {
    setData(null);
  }, [repoId]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    api
      .metrics<T>(repoId, view, JSON.parse(debouncedKey) as MetricsFilters)
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [repoId, view, debouncedKey, enabled, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, error, reload };
}

export function useAuthors(repoId: number) {
  const [data, setData] = useState<AuthorsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getAuthors(repoId);
      setData(res);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, setData, loading, error, reload };
}

/** Close-on-outside-click helper for dropdown panels. */
export function useClickOutside<T extends HTMLElement>(onOutside: () => void) {
  const ref = useRef<T | null>(null);
  const cbRef = useRef(onOutside);
  cbRef.current = onOutside;
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && e.target instanceof Node && !ref.current.contains(e.target)) {
        cbRef.current();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);
  return ref;
}
