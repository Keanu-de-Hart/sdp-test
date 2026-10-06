/** Repository management: upload a zip, clone a URL, watch progress, delete. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { Empty, ErrorNote, Loading, Progress, StatusBadge } from "../components/ui";
import { fmtDate, fmtInt } from "../lib/format";
import { isRepoActive } from "../lib/hooks";
import { useToast } from "../state/ToastContext";
import type { RepoInfo } from "../types";

export function ReposPage() {
  const [repos, setRepos] = useState<RepoInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const toast = useToast();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      const list = await api.listRepos();
      setRepos(list);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const anyActive = (repos ?? []).some((r) => isRepoActive(r.status));
  useEffect(() => {
    if (!anyActive) return;
    const t = window.setInterval(() => void load(), 1500);
    return () => window.clearInterval(t);
  }, [anyActive, load]);

  const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

  const upload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      toast.push("Please provide a .zip archive containing the repository (with its .git directory).", "error");
      return;
    }
    setBusy(true);
    try {
      const r = await api.uploadRepo(file);
      toast.push(`Uploaded “${r.name}” — ingestion started.`, "success");
      setRepos((prev) => (prev ? [r, ...prev] : [r]));
    } catch (e) {
      toast.push(errMsg(e), "error");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const clone = async () => {
    const u = url.trim();
    if (!u) return;
    setBusy(true);
    try {
      const r = await api.cloneRepo(u, name.trim());
      toast.push(`Cloning “${r.name}” — this may take a while for large repositories.`, "success");
      setRepos((prev) => (prev ? [r, ...prev] : [r]));
      setUrl("");
      setName("");
    } catch (e) {
      toast.push(errMsg(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (r: RepoInfo) => {
    if (!window.confirm(`Delete “${r.name}” and all of its indexed data?`)) return;
    try {
      await api.deleteRepo(r.id);
      toast.push(`Deleted “${r.name}”.`, "success");
      setRepos((prev) => prev?.filter((x) => x.id !== r.id) ?? null);
    } catch (e) {
      toast.push(errMsg(e), "error");
    }
  };

  return (
    <div className="container">
      <h1 className="page-title">Repositories</h1>
      <p className="page-sub">
        Ingest a repository by uploading a <b>.zip</b> of it, or by cloning a remote URL. Metrics
        are computed from the full commit history.
      </p>

      <div className="grid cols-2 section-gap">
        <div className="card">
          <header className="card-header">
            <span className="card-title">Upload a zip</span>
            <span className="card-sub">contains the repository with its .git directory</span>
          </header>
          <div className="card-body">
            <div
              className={`dropzone${drag ? " over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                const f = e.dataTransfer.files?.[0];
                if (f && !busy) void upload(f);
              }}
              onClick={() => fileRef.current?.click()}
            >
              {busy ? (
                <>
                  <span className="spinner" /> Uploading…
                </>
              ) : (
                <>
                  <div style={{ fontSize: 15, marginBottom: 4 }}>Drop a .zip here</div>
                  <div className="small">or click to choose a file</div>
                </>
              )}
              <input
                ref={fileRef}
                type="file"
                accept=".zip,application/zip"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void upload(f);
                }}
              />
            </div>
          </div>
        </div>

        <div className="card">
          <header className="card-header">
            <span className="card-title">Clone from URL</span>
            <span className="card-sub">https://, ssh:// or git@…</span>
          </header>
          <div className="card-body col">
            <div className="field">
              <label>Repository URL</label>
              <input
                placeholder="https://github.com/redis/redis.git"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void clone();
                }}
              />
            </div>
            <div className="field">
              <label>Display name (optional)</label>
              <input
                placeholder="derived from the URL when empty"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="row">
              <button
                type="button"
                className="btn primary"
                disabled={busy || !url.trim()}
                onClick={() => void clone()}
              >
                {busy ? <span className="spinner" /> : null} Clone &amp; index
              </button>
              <span className="faint small">A full mirror clone; no worktree is created.</span>
            </div>
          </div>
        </div>
      </div>

      <h2 className="page-title section-gap" style={{ fontSize: 17, marginTop: 26 }}>
        Indexed repositories
      </h2>

      {error ? (
        <div className="section-gap">
          <ErrorNote>{error}</ErrorNote>
        </div>
      ) : repos === null ? (
        <Loading label="Loading repositories…" />
      ) : repos.length === 0 ? (
        <Empty>No repositories yet — upload a zip or clone a URL to get started.</Empty>
      ) : (
        <div className="grid cols-2 section-gap">
          {repos.map((r) => (
            <div key={r.id} className="card repo-card">
              <div className="row">
                <span className="repo-name ellipsis" title={r.name}>{r.name}</span>
                <StatusBadge status={r.status} />
                <div className="nav-spacer" />
                {r.have_mailmap ? (
                  <span className="badge accent" title=".mailmap found — identities are resolved automatically">
                    mailmap
                  </span>
                ) : null}
              </div>

              <dl className="meta-grid" style={{ margin: 0 }}>
                <dt>Source</dt>
                <dd className="ellipsis" title={r.source}>
                  {r.source_type === "zip" ? "zip" : "clone"} · {r.source}
                </dd>
                <dt>Commits</dt>
                <dd>
                  {fmtInt(r.commit_count)}
                  {r.head_sha ? (
                    <>
                      {" · "}
                      <span className="mono" style={{ fontSize: 11 }} title={r.head_sha}>
                        {r.head_sha.slice(0, 10)}
                      </span>
                    </>
                  ) : null}
                </dd>
                <dt>Added</dt>
                <dd>{fmtDate(r.created_at)}</dd>
              </dl>

              {isRepoActive(r.status) && (
                <>
                  <Progress value={r.progress} />
                  {r.progress_detail && (
                    <span className="faint small mono ellipsis">{r.progress_detail}</span>
                  )}
                </>
              )}
              {r.status === "error" && r.error && (
                <div className="error-note small ellipsis" title={r.error}>
                  {r.error}
                </div>
              )}

              <div className="row" style={{ marginTop: "auto" }}>
                {r.status === "ready" ? (
                  <>
                    <Link className="btn primary" to={`/repos/${r.id}/dashboard`}>
                      Open dashboard
                    </Link>
                    <Link className="btn" to={`/repos/${r.id}/authors`}>
                      Authors
                    </Link>
                  </>
                ) : (
                  <>
                    <button className="btn primary" disabled>
                      Open dashboard
                    </button>
                    <button
                      className="btn"
                      disabled={!isRepoActive(r.status)}
                      onClick={() => navigate(`/repos/${r.id}/authors`)}
                    >
                      Authors
                    </button>
                  </>
                )}
                <div className="nav-spacer" />
                <button
                  type="button"
                  className="btn danger sm"
                  onClick={() => void remove(r)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
