# RAT — Repo Analysis Tool

A multi-repository web dashboard that turns a git repository's history into
filterable file / directory / repository / commit-set / author metrics.

Ingest a repo once (upload a **zip** or **clone a URL**); every metric is then a
fast SQL aggregation over an indexed SQLite database. The whole history is
indexed in a **single streamed `git log` pass**, so repos with ~100k commits
stay interactive.

```
backend/   Python 3.12 · FastAPI · SQLite (stdlib, WAL) · git CLI streaming
frontend/  React 18 · TypeScript · Vite · ECharts
scripts/   verify_metrics.py — metric spot-checker / expected-values validator
```

## Feature checklist

- **Ingestion** — (1) zip upload containing the repository (`.git` anywhere at
  the root or one level down) and (2) remote URL clone (`--mirror`, works for
  https / ssh / `git@…`). Progress is reported live (clone %, commits parsed).
- **Multiple repositories** — independent rows in one database; delete cleans
  up rows and files on disk.
- **Author merging** — `.mailmap` is applied automatically at ingest (via
  `git -c mailmap.file=`); when there is none, identities are merged manually
  in the UI. Manual merges are applied *at query time*, so merging never
  re-indexes a repository.
- **Filters** — repository, author(s), file or directory scope, and the commit
  set **H**: either a time period `H_t` / `H_i,j` (start inclusive, end
  exclusive on committer date) or a **manually selected commit list**.
  Filters live in the URL, so every view is shareable/bookmarkable.
- **Metrics** — file, directory (recursive sums incl. root), repository
  (= directory metrics on the root), commit-set, and author metrics, all with
  the exact formulas below.
- **Rename / binary semantics (delegated to git)** — `-M50%` rename detection;
  pure renames produce no metric change; rename+edit is attributed to the new
  path; binary changes are not measured.

## Metric definitions

Per commit `h` vs its first parent `h[p]`:

| quantity | definition |
|---|---|
| added / removed | `l⁺`, `l⁻` (lines, from `--numstat`) |
| growth | `δ = l⁺ − l⁻` |
| churn | `λ = l⁺ + l⁻` |
| modification indicator | `I_n(h,o) = 1 ⇔ λ_h,o > 0` |

Directory: per commit, the recursive sum over immediate children of the
directory — evaluated as the sum over every file in the subtree
(path-prefix aggregation).

Commit set **H**: `l⁺_H,o = Σ_{h∈H} l⁺_h,o` (same for `l⁻`, `δ`, `λ`),
`n_H,o = Σ_{h∈H} I_n(h,o)`.

- modification frequency `η = n_H,o / |H|` (0 when `|H| = 0`)
- churn rate `ρ = λ_H,o / |H|` (0 when `|H| = 0`)

Authorship (`a` after merging): `I(a,h) = 1 ⇔ a = h[a]`,
`n_H,o,a = Σ_h I(a,h)·I_n(h,o)`, `λ_H,o,a = Σ_h λ_h,o·I(a,h)`, and ownership
`ω = λ_H,o,a / λ_H,o` (0 when `λ_H,o = 0`).

`backend/app/metrics.py` is the single source of truth for these formulas;
`backend/tests/test_metrics.py` locks them against hand-computed golden values.

## Quick start

Prerequisites: Python 3.10+, Node 18+, git ≥ 2.30.

```bash
make install          # python venv + backend deps, npm install for the frontend
make dev              # API on :8000 + Vite dev server on :5173 (open :5173)
# or single-port production mode:
make run              # builds the frontend and serves everything on :8000
```

Then open the app, and either:

- drag a `.zip` of a repository onto the upload box, or
- paste a clone URL (e.g. `https://github.com/DaveGamble/cJSON.git`).

When the status badge turns `ready`, open the dashboard.

## Dashboard

- **Filter bar** — object scope (file/dir picker), time range *From/To*
  (inclusive, UTC) **or** a manual commit selection (searchable multi-select
  over the full history; overrides the range), author multi-select, and the
  timeseries bucket granularity.
- **Summary cards** — added, removed, growth, churn, modifications, η, ρ, |H|.
- **Growth timeline** — added / removed / growth per day/week/month; use the
  toolbox brush (drag horizontally) to set the time range, and **Clear range**
  in the card header to drop it again.
- **Directories** — treemap (size = churn, colour = growth red↘ … green↗) or
  an indented tree view via the toggle; click a cell or row to scope every
  metric to that directory, `↑ Up` to go back.
- **Authors** — ownership donut + modification bars; click an author to filter
  the whole dashboard to them.
- **Files table** — sortable per-file metrics, CSV export.
- **Commit set table** — the commits of H themselves (paged), optionally only
  those touching the current scope.

### Author merging page

Lists every identity (name, email, commits, raw names). Select identities that
belong to one person, type a canonical name and merge — instantly reflected in
every metric. Groups can be unmerged per identity or as a whole. If the repo
has a `.mailmap`, identities are already resolved and badges show that.

## API reference

| method & path | purpose |
|---|---|
| `GET /api/repos` | list repositories (status, progress, commit count) |
| `POST /api/repos/upload` | multipart zip upload → background ingestion |
| `POST /api/repos/clone` | `{url, name?}` → background clone + ingestion |
| `GET /api/repos/{id}` | status / progress / error |
| `DELETE /api/repos/{id}` | delete rows + on-disk data |
| `GET /api/repos/{id}/authors` | identities + merge groups |
| `POST /api/repos/{id}/author-merges` | `{identities[], name}` merge |
| `DELETE /api/repos/{id}/author-merges/{identity}` | unmerge one identity |
| `DELETE /api/repos/{id}/author-groups/{id}` | unmerge a whole group |
| `GET /api/repos/{id}/commits` | commit search (`q`, paging) for the picker |
| `GET /api/repos/{id}/paths` | file/dir search for the scope picker |
| `POST /api/repos/{id}/metrics/{view}` | metric query (body below) |

Metric filter body (all optional):

```json
{
  "start": 1690000000, "end": 1700000000,
  "commits": ["<sha>", "…"],
  "authors": ["i:email@x", "m:3"],
  "path": "src", "object_type": "dir",
  "granularity": "month", "limit": 500, "offset": 0, "only_changed": false
}
```

Views: `summary`, `files`, `dirs`, `authors`, `timeseries`, `commits`
(commit-set rows). `end` is exclusive; a manual `commits` list overrides the
time range. Interactive docs at `/docs` when the server runs.

## Verification & tests

```bash
make test             # 17 backend tests: parser format, golden metrics, API
make verify ARGS='--api http://localhost:8000 --repo cJSON'
```

`scripts/verify_metrics.py` runs the standard views against a server (or, fully
locally with `--data-dir`, ingests in-process) and prints a report. With
`--expected values.json` it performs a subset match against expected values
(exact integers, toleranced floats):

```bash
make verify ARGS='--api http://localhost:8000 --repo cJSON --expected scripts/expected_example.json'
```

`scripts/expected_example.json` holds the real values measured on
`DaveGamble/cJSON` (955 non-merge commits) — a fresh ingest passes 19/19 checks.

The test fixture (`backend/tests/conftest.py`) builds a deterministic history —
two authors, mailmap alias, rename-only, rename+edit, delete, binary, merge
commit, empty commit, boundary dates — and asserts hand-computed golden values
for every formula, including `H_i,j` boundaries and per-commit directory
modification de-duplication. The parser test locks the binary
`git log --numstat -z` token format.

## Performance notes

- One subprocess per repository for indexing — never per commit. The NUL stream
  is parsed incrementally (bounded memory) and inserted in 10k-row batches in
  WAL mode.
- Rename detection cost is paid once at ingest; queries hit indexes only
  (`(repo_id, committer_ts)`, `(repo_id, path)`, PK `(repo_id, sha, path)`).
- Directory metrics are computed by a single ordered scan with per-commit
  de-duplication of modifications; path scoping uses the index-friendly range
  `path >= 'dir/' AND path < 'dir0'`.
- A short-TTL (30 s) response cache absorbs repeated dashboard queries.

### Measured on this machine (cold cache)

| repository | non-merge commits | clone | index | DB |
|---|---|---|---|---|
| DaveGamble/cJSON | 955 | — | — | 0.7 MB |
| redis/redis | 11,875 | — | — | 10 MB |
| git/git | 61,101 | 79 s | 31 s (≈2,000 commits/s) | 48 MB |

End-to-end `scripts/verify_metrics.py` runs (clone + index + report): cJSON
**3.3 s**, Redis **49 s**. git.git query latencies without any cache:
summary 144 ms, files top-500 by churn 368 ms, dirs 274 ms, authors 257 ms,
monthly timeseries 270 ms; filtered queries are faster still — time range
30 ms, single author 25 ms, manual 20-commit selection 0.4 ms, dir-scoped
files 52 ms, paged commit list 62 ms. Every measured view stays well under
500 ms on a fresh index.

## Project layout

```
backend/app/        config, db schema, ingest (streamed indexing), authors,
                    metrics (single source of truth), schemas, routers/, main
backend/tests/      fixture builder + parser, metrics (golden), API tests
frontend/src/       api client, state/ (URL-synced filters, toasts),
                    lib/ (time, format, charts, hooks), components/, pages/
scripts/            verify_metrics.py
Makefile            install / dev / build / run / test / verify / clean
```

## Assumptions & limitations

- The reference commit is `HEAD` of the default branch (ref column is stored
  per repo; a selector UI is out of scope).
- Author filtering narrows H to the selected authors' commits; ownership is
  `λ` over the same filtered H.
- Re-ingesting a repository replaces it (no incremental indexing); deleting a
  repository removes its rows and files.
- Committer dates are used for H membership (per the brief), in UTC day
  boundaries in the UI.
