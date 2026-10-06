/** Author merging: automatic .mailmap resolution plus manual identity merging. */
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { RepoNav } from "../components/NavBar";
import { RepoGate } from "../components/RepoGate";
import { Empty, ErrorNote, Loading } from "../components/ui";
import { fmtInt, truncate } from "../lib/format";
import { useAuthors, useRepo } from "../lib/hooks";
import { useToast } from "../state/ToastContext";
import type { AuthorIdentity } from "../types";

export function AuthorsPage() {
  const params = useParams();
  const repoId = Number(params.repoId);
  const { repo, loading: repoLoading, error: repoError } = useRepo(repoId);
  const { data, setData, loading, error } = useAuthors(repoId);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

  const toggle = (identity: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(identity)) next.delete(identity);
      else next.add(identity);
      return next;
    });
  };

  const allSelected = !!data && data.authors.length > 0 && selected.size === data.authors.length;

  const toggleAll = () => {
    if (!data) return;
    setSelected(allSelected ? new Set() : new Set(data.authors.map((a) => a.identity)));
  };

  const doMerge = async () => {
    const identities = [...selected];
    if (!identities.length) return;
    const canonical = name.trim() || identities[0];
    setBusy(true);
    try {
      const res = await api.mergeAuthors(repoId, identities, canonical);
      setData(res);
      setSelected(new Set());
      setName("");
      toast.push(
        `Merged ${identities.length} identit${identities.length === 1 ? "y" : "ies"} into “${canonical}”.`,
        "success",
      );
    } catch (e) {
      toast.push(errMsg(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const doUnmergeIdentity = async (identity: string) => {
    setBusy(true);
    try {
      const res = await api.unmergeIdentity(repoId, identity);
      setData(res);
      toast.push(`Removed “${identity}” from its merge group.`, "success");
    } catch (e) {
      toast.push(errMsg(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const doUnmergeGroup = async (groupId: number, groupName: string) => {
    if (!window.confirm(`Unmerge the group “${groupName}”?`)) return;
    setBusy(true);
    try {
      const res = await api.unmergeGroup(repoId, groupId);
      setData(res);
      toast.push(`Unmerged the group “${groupName}”.`, "success");
    } catch (e) {
      toast.push(errMsg(e), "error");
    } finally {
      setBusy(false);
    }
  };

  if (repoError) {
    return (
      <div className="container">
        <ErrorNote>{repoError}</ErrorNote>
      </div>
    );
  }
  if (!repo) {
    return (
      <div className="container">
        <Loading label={repoLoading ? "Loading repository…" : "Repository not found."} />
      </div>
    );
  }

  const resolvedName = (a: AuthorIdentity) => a.group_name ?? a.name;
  const rawNames = (a: AuthorIdentity) => (a.raw_names ?? "").split(",").filter(Boolean);

  return (
    <div className="container">
      <RepoNav repo={repo} active="authors" />

      {repo.status !== "ready" ? (
        <RepoGate repo={repo} />
      ) : (
        <section className="card">
          <header className="card-header">
            <span className="card-title">Author identities</span>
            <span className="card-sub">
              {data ? `${fmtInt(data.authors.length)} identities · ${fmtInt(data.groups.length)} merge groups` : ""}
            </span>
            <div className="nav-spacer" />
            {data?.have_mailmap ? (
              <span className="badge accent" title="Identities were resolved through .mailmap at ingest time">
                .mailmap applied
              </span>
            ) : (
              <span className="badge warn" title="No .mailmap found — merge identities manually below">
                no .mailmap
              </span>
            )}
          </header>

          <div className="card-body flush">
            {error ? (
              <ErrorNote>{error}</ErrorNote>
            ) : loading && !data ? (
              <Loading label="Loading authors…" />
            ) : !data || data.authors.length === 0 ? (
              <Empty>No authors indexed yet.</Empty>
            ) : (
              <>
                <div className="filter-bar" style={{ borderBottom: "1px solid var(--border-soft)" }}>
                  <div className="grow">
                    <p className="muted small" style={{ margin: 0 }}>
                      {data.have_mailmap
                        ? "A .mailmap file was found at the reference commit — the identities below are already mailmap-resolved. Manual merges layer on top of it."
                        : "No .mailmap in this repository. Select the identities that belong to one person and merge them into a single author."}
                    </p>
                  </div>
                  <div className="field">
                    <label>Canonical name</label>
                    <input
                      placeholder="e.g. Jane Doe"
                      value={name}
                      disabled={busy}
                      onChange={(e) => setName(e.target.value)}
                      style={{ width: 220 }}
                    />
                  </div>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy || selected.size === 0}
                    onClick={() => void doMerge()}
                    title={
                      selected.size === 0
                        ? "Select identities to merge first"
                        : "Merge the selected identities into one author"
                    }
                  >
                    {busy ? <span className="spinner" /> : null} Merge {selected.size > 0 ? selected.size : ""}
                  </button>
                  <button
                    type="button"
                    className="btn ghost"
                    disabled={busy || selected.size === 0}
                    onClick={() => setSelected(new Set())}
                  >
                    Clear selection
                  </button>
                </div>

                <div className="table-wrap" style={{ maxHeight: 520 }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th style={{ width: 34 }}>
                          <input
                            type="checkbox"
                            checked={allSelected}
                            onChange={toggleAll}
                            title="Select all"
                          />
                        </th>
                        <th>Resolved author</th>
                        <th>Email</th>
                        <th className="num">Commits</th>
                        <th>Raw names</th>
                        <th>Group</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {data.authors.map((a) => {
                        const inGroup = a.group_id != null;
                        const isSel = selected.has(a.identity);
                        const raws = rawNames(a);
                        const shownName = resolvedName(a);
                        const mailmapChanged = raws.length > 0 && raws.some((n) => n !== shownName);
                        return (
                          <tr key={a.identity} className={isSel ? "selected-row" : undefined}>
                            <td>
                              <input
                                type="checkbox"
                                checked={isSel}
                                disabled={busy}
                                onChange={() => toggle(a.identity)}
                              />
                            </td>
                            <td>
                              <div className="row" style={{ gap: 8 }}>
                                <span style={{ fontWeight: 550 }}>{shownName}</span>
                                {mailmapChanged && !inGroup && (
                                  <span className="badge" title={`Raw identities: ${a.raw_names}`}>
                                    mailmap
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="mono" style={{ fontSize: 12 }}>{a.email}</td>
                            <td className="num">{fmtInt(a.commits)}</td>
                            <td className="muted small ellipsis" style={{ maxWidth: 320 }} title={a.raw_names ?? ""}>
                              {a.raw_names ? truncate(a.raw_names, 60) : "–"}
                            </td>
                            <td>
                              {inGroup ? (
                                <span className="badge accent">{a.group_name}</span>
                              ) : (
                                <span className="faint">–</span>
                              )}
                            </td>
                            <td className="num">
                              {inGroup && (
                                <button
                                  type="button"
                                  className="btn ghost sm"
                                  disabled={busy}
                                  onClick={() => void doUnmergeIdentity(a.identity)}
                                  title="Remove this identity from its merge group"
                                >
                                  unmerge
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {repo.status === "ready" && data && data.groups.length > 0 && (
        <section className="card section-gap">
          <header className="card-header">
            <span className="card-title">Merge groups</span>
            <span className="card-sub">
              manual merges — applied at query time, no re-indexing needed
            </span>
          </header>
          <div className="card-body col" style={{ gap: 12 }}>
            {data.groups.map((g) => (
              <div key={g.id} className="row wrap" style={{ gap: 8 }}>
                <span className="badge accent">{g.name}</span>
                <span className="faint small">
                  {g.identities.length} identit{g.identities.length === 1 ? "y" : "ies"}
                </span>
                {g.identities.map((ident) => (
                  <span key={ident} className="pill">
                    <span className="mono" style={{ fontSize: 11.5 }}>{ident}</span>
                    <button
                      type="button"
                      className="x"
                      disabled={busy}
                      title="Remove from group"
                      onClick={() => void doUnmergeIdentity(ident)}
                    >
                      ×
                    </button>
                  </span>
                ))}
                <div className="nav-spacer" />
                <button
                  type="button"
                  className="btn danger sm"
                  disabled={busy}
                  onClick={() => void doUnmergeGroup(g.id, g.name)}
                >
                  Unmerge all
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
