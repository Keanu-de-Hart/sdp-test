/** Dashboard: filters + summary cards + charts + tables for one repository.
 *  `FiltersProvider` (with the URL-synced filter state) wraps this page. */
import { AuthorPanel } from "../components/AuthorPanel";
import { CommitSetTable } from "../components/CommitSetTable";
import { DirectoryTreemap } from "../components/DirectoryTreemap";
import { FileMetricsTable } from "../components/FileMetricsTable";
import { FilterBar } from "../components/FilterBar";
import { GrowthTimeline } from "../components/GrowthTimeline";
import { RepoNav } from "../components/NavBar";
import { RepoGate } from "../components/RepoGate";
import { SummaryCards } from "../components/SummaryCards";
import { ErrorNote, Loading } from "../components/ui";
import { fmtInt } from "../lib/format";
import { useRepo } from "../lib/hooks";
import { useFilters } from "../state/FiltersContext";

export function DashboardPage() {
  const { repoId, filters } = useFilters();
  const { repo, loading, error } = useRepo(repoId);

  if (error) {
    return (
      <div className="container">
        <ErrorNote>{error}</ErrorNote>
      </div>
    );
  }
  if (!repo) {
    return (
      <div className="container">
        <Loading label={loading ? "Loading repository…" : "Repository not found."} />
      </div>
    );
  }

  const scope = filters.path
    ? `/${filters.path}${filters.type === "dir" ? "/" : ""}`
    : "repository root";

  return (
    <div className="container">
      <RepoNav repo={repo} active="dashboard" />

      {repo.status !== "ready" ? (
        <RepoGate repo={repo} />
      ) : (
        <>
          <div className="row wrap small muted" style={{ marginBottom: 14 }}>
            <span>{fmtInt(repo.commit_count)} non-merge commits indexed</span>
            {repo.head_sha && (
              <>
                <span className="nav-sep">·</span>
                <span className="mono" title={repo.head_sha}>
                  {repo.head_sha.slice(0, 12)}
                </span>
              </>
            )}
            <span className="nav-sep">·</span>
            <span>
              {repo.source_type === "clone" ? "cloned from" : "uploaded"}{" "}
              <span className="mono">{repo.source}</span>
            </span>
            <span className="nav-sep">·</span>
            <span className={repo.have_mailmap ? "" : "warn"}>
              {repo.have_mailmap ? ".mailmap applied" : "no .mailmap"}
            </span>
            <span className="nav-sep">·</span>
            <span>scope: {scope}</span>
          </div>

          <FilterBar />

          <div className="section-gap">
            <SummaryCards />
          </div>

          <div className="section-gap">
            <GrowthTimeline />
          </div>

          <div className="grid cols-2 section-gap">
            <DirectoryTreemap />
            <AuthorPanel />
          </div>

          <div className="grid cols-2 section-gap">
            <FileMetricsTable repoName={repo.name} />
            <CommitSetTable />
          </div>
        </>
      )}
    </div>
  );
}
