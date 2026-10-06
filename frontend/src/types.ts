/** Shared API types — mirrors backend/app/schemas.py + router responses. */

export type Gran = "day" | "week" | "month";
export type ObjectType = "file" | "dir";
export type RepoStatus =
  | "pending"
  | "cloning"
  | "extracting"
  | "indexing"
  | "ready"
  | "error";

export interface RepoInfo {
  id: number;
  name: string;
  source_type: "zip" | "clone";
  source: string;
  ref: string;
  status: RepoStatus;
  progress: number; // 0..1
  progress_detail: string | null;
  error: string | null;
  head_sha: string | null;
  commit_count: number;
  have_mailmap: number; // 0/1
  created_at: number;
  path: string;
}

export interface AuthorIdentity {
  identity: string; // lowercased email
  email: string;
  name: string;
  commits: number;
  group_id: number | null;
  group_name: string | null;
  raw_names: string | null; // comma-joined raw names
}

export interface MergeGroup {
  id: number;
  name: string;
  identities: string[];
}

export interface AuthorsResponse {
  have_mailmap: boolean;
  authors: AuthorIdentity[];
  groups: MergeGroup[];
}

export interface CommitItem {
  sha: string;
  short: string;
  committer_ts: number;
  author: string;
  author_key: string;
  subject: string;
}

export interface CommitsResponse {
  total: number;
  items: CommitItem[];
}

export interface PathItem {
  path: string;
  type: ObjectType;
  label: string;
}

export interface PathsResponse {
  items: PathItem[];
}

export interface MetricsFilters {
  start?: number | null;
  end?: number | null;
  commits?: string[];
  authors?: string[];
  path?: string | null;
  object_type?: ObjectType | null;
  granularity?: Gran;
  limit?: number;
  offset?: number;
  only_changed?: boolean;
}

export interface DerivedMetrics {
  added: number;
  removed: number;
  growth: number;
  churn: number;
  modifications: number;
  modification_frequency: number;
  churn_rate: number;
}

export interface SummaryResponse extends DerivedMetrics {
  commit_count: number;
  object: { path: string; type: "file" | "dir" | "root" };
}

export interface FileRow extends DerivedMetrics {
  path: string;
}

export interface FilesResponse {
  commit_count: number;
  items: FileRow[];
}

export interface DirRow extends DerivedMetrics {
  path: string;
  depth: number;
}

export interface DirsResponse {
  commit_count: number;
  items: DirRow[];
}

export interface AuthorRow {
  author_key: string;
  author: string;
  commits: number;
  modifications: number;
  churn: number;
  ownership: number; // 0..1
}

export interface AuthorsMetricsResponse {
  commit_count: number;
  churn_total: number;
  items: AuthorRow[];
}

export interface TimeseriesPoint {
  bucket: string; // 'YYYY-MM-DD'
  bucket_ts: number;
  added: number;
  removed: number;
  growth: number;
  churn: number;
  commits: number;
  modifications: number;
}

export interface TimeseriesResponse {
  commit_count: number;
  granularity: Gran;
  items: TimeseriesPoint[];
}

export interface CommitSetRow {
  sha: string;
  short: string;
  committer_ts: number;
  author: string;
  author_key: string;
  subject: string;
  added: number;
  removed: number;
  churn: number;
}

export interface CommitSetResponse {
  commit_count: number;
  total: number;
  items: CommitSetRow[];
}
