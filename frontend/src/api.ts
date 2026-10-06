/** Typed API client. All paths are relative so the Vite dev proxy and the
 *  production single-port static serving both work unchanged. */
import type {
  AuthorsMetricsResponse,
  AuthorsResponse,
  CommitSetResponse,
  CommitsResponse,
  DirsResponse,
  FilesResponse,
  MetricsFilters,
  PathsResponse,
  RepoInfo,
  SummaryResponse,
  TimeseriesResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is the server running?");
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const api = {
  // ---- repositories ----
  listRepos: () => request<RepoInfo[]>("/api/repos"),
  getRepo: (repoId: number) => request<RepoInfo>(`/api/repos/${repoId}`),
  deleteRepo: (repoId: number) =>
    request<{ ok: boolean }>(`/api/repos/${repoId}`, { method: "DELETE" }),
  uploadRepo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<RepoInfo>("/api/repos/upload", { method: "POST", body: form });
  },
  cloneRepo: (url: string, name?: string) =>
    request<RepoInfo>("/api/repos/clone", json({ url, name: name || null })),

  // ---- authors ----
  getAuthors: (repoId: number) =>
    request<AuthorsResponse>(`/api/repos/${repoId}/authors`),
  mergeAuthors: (repoId: number, identities: string[], name: string) =>
    request<AuthorsResponse>(
      `/api/repos/${repoId}/author-merges`,
      json({ identities, name }),
    ),
  unmergeIdentity: (repoId: number, identity: string) =>
    request<AuthorsResponse>(
      `/api/repos/${repoId}/author-merges/${encodeURIComponent(identity)}`,
      { method: "DELETE" },
    ),
  unmergeGroup: (repoId: number, groupId: number) =>
    request<AuthorsResponse>(`/api/repos/${repoId}/author-groups/${groupId}`, {
      method: "DELETE",
    }),

  // ---- commits / paths ----
  getCommits: (
    repoId: number,
    opts: { q?: string; start?: number; end?: number; limit?: number; offset?: number } = {},
  ) => {
    const p = new URLSearchParams();
    if (opts.q) p.set("q", opts.q);
    if (opts.start != null) p.set("start", String(opts.start));
    if (opts.end != null) p.set("end", String(opts.end));
    if (opts.limit != null) p.set("limit", String(opts.limit));
    if (opts.offset != null) p.set("offset", String(opts.offset));
    const qs = p.toString();
    return request<CommitsResponse>(`/api/repos/${repoId}/commits${qs ? `?${qs}` : ""}`);
  },
  getPaths: (repoId: number, q = "", limit = 50) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    p.set("limit", String(limit));
    return request<PathsResponse>(`/api/repos/${repoId}/paths?${p.toString()}`);
  },

  // ---- metrics ----
  metrics: <T>(repoId: number, view: string, filters: MetricsFilters) =>
    request<T & { repo_id: number; view: string }>(
      `/api/repos/${repoId}/metrics/${view}`,
      json(filters),
    ),

  summary: (repoId: number, filters: MetricsFilters) =>
    api.metrics<SummaryResponse>(repoId, "summary", filters),
  files: (repoId: number, filters: MetricsFilters) =>
    api.metrics<FilesResponse>(repoId, "files", filters),
  dirs: (repoId: number, filters: MetricsFilters) =>
    api.metrics<DirsResponse>(repoId, "dirs", filters),
  authorsMetrics: (repoId: number, filters: MetricsFilters) =>
    api.metrics<AuthorsMetricsResponse>(repoId, "authors", filters),
  timeseries: (repoId: number, filters: MetricsFilters) =>
    api.metrics<TimeseriesResponse>(repoId, "timeseries", filters),
  commitSet: (repoId: number, filters: MetricsFilters) =>
    api.metrics<CommitSetResponse>(repoId, "commits", filters),
};
