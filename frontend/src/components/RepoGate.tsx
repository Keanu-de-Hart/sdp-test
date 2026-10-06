/** Shown while a repository is still being ingested (or failed). */
import { isRepoActive } from "../lib/hooks";
import type { RepoInfo } from "../types";
import { ErrorNote, Progress, StatusBadge } from "./ui";

const TEXT: Record<string, string> = {
  pending: "Queued — the ingestion worker is starting…",
  cloning: "Cloning the repository (this can take a while for large repos)…",
  extracting: "Extracting the uploaded archive…",
  indexing: "Indexing the commit history (single streamed git pass)…",
  ready: "Ready.",
  error: "Ingestion failed.",
};

export function RepoGate({ repo }: { repo: RepoInfo }) {
  return (
    <div className="card">
      <div className="card-body col" style={{ gap: 12 }}>
        <div className="row wrap">
          <StatusBadge status={repo.status} />
          <span>{TEXT[repo.status] ?? repo.status}</span>
          {isRepoActive(repo.status) && (
            <span className="faint small">
              <span className="spinner" style={{ marginRight: 6 }} />
              auto-refreshing…
            </span>
          )}
        </div>
        {isRepoActive(repo.status) && <Progress value={repo.progress} />}
        {repo.progress_detail && <div className="faint small mono">{repo.progress_detail}</div>}
        {repo.status === "error" && repo.error && <ErrorNote>{repo.error}</ErrorNote>}
        {isRepoActive(repo.status) && (
          <div className="faint small">
            You can leave this page — indexing continues on the server.
          </div>
        )}
      </div>
    </div>
  );
}
