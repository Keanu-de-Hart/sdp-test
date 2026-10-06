"""Metric computation — the single source of truth for the formulas.

Definitions (mirroring the brief exactly):

  File, per commit h vs its first parent h[p]:
      l+   : added lines          l-   : removed lines
      delta = l+ - l- (growth)    lambda = l+ + l- (churn)

  Directory, per commit: the (recursive) sum of l+/l-/delta/lambda over the
  immediate children of the directory — equivalent to the sum over every file
  in the subtree, which is how it is evaluated here (path-prefix aggregation).

  Commit set H (subset of the non-merge commits reachable from the reference):
      l+_H,o   = sum over h in H of l+_h,o          (same for l-, delta, lambda)
      I_n(h,o) = 1 if lambda_h,o > 0 else 0
      n_H,o    = sum over h in H of I_n(h,o)        (modifications)
      eta_H,o  = n_H,o / |H|      if |H| != 0 else 0   (modification frequency)
      rho_H,o  = lambda_H,o / |H| if |H| != 0 else 0   (churn rate)

  Author a (after merging):
      I(a,h)     = 1 if a == h[a] else 0
      n_H,o,a    = sum over h of I(a,h) * I_n(h,o)     (author modifications)
      lambda_H,o,a = sum over h of lambda_h,o * I(a,h) (author churn)
      omega_H,o,a  = lambda_H,o,a / lambda_H,o if lambda_H,o != 0 else 0 (ownership)

  H_t (from t) and H_i,j (i inclusive, j exclusive) are expressed as an
  inclusive ``start`` / exclusive ``end`` filter on h[committer-date].
"""
from __future__ import annotations

import calendar
import datetime as _dt
import sqlite3
import time as _time
from dataclasses import dataclass, field

from .authors import AUTHOR_JOIN, AUTHOR_KEY_SQL, AUTHOR_NAME_SQL

# --------------------------------------------------------------------------- #
# filters
# --------------------------------------------------------------------------- #

@dataclass
class Filter:
    start: int | None = None                 # inclusive UNIX timestamp
    end: int | None = None                   # exclusive UNIX timestamp
    commits: list[str] = field(default_factory=list)   # manual selection; overrides range
    authors: list[str] = field(default_factory=list)   # author keys ('i:<email>' / 'm:<id>')
    path: str | None = None                  # object path (file or directory)
    object_type: str | None = None           # 'file' | 'dir'
    granularity: str = "month"               # timeseries bucket
    limit: int = 500
    offset: int = 0
    only_changed: bool = False               # commits view: only commits touching the object

    def object_clause(self, col: str = "fc.path") -> tuple[str, list]:
        """Where-clause fragment implementing H[F] / H[D] membership for the object."""
        path = (self.path or "").strip("/")
        if not path:
            return "", []
        if self.object_type == "file":
            return f" AND {col} = ?", [path]
        # directory: every file under the prefix is in the subtree
        return f" AND {col} >= ? AND {col} < ?", [path + "/", path + "0"]


def _prepare(conn: sqlite3.Connection, repo_id: int, f: Filter) -> None:
    """Materialise the manual commit selection into a TEMP table."""
    if f.commits:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS _sel_shas(sha TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM _sel_shas")
        conn.executemany("INSERT OR IGNORE INTO _sel_shas(sha) VALUES (?)",
                         [(s,) for s in f.commits])


def _h_cte(f: Filter, repo_id: int) -> tuple[str, list]:
    """The commit set H (with merged-author resolution) as a CTE."""
    where = ["c.repo_id = ?"]
    params: list = [repo_id]
    if f.commits:
        where.append("c.sha IN (SELECT sha FROM _sel_shas)")
    else:
        if f.start is not None:
            where.append("c.committer_ts >= ?")
            params.append(int(f.start))
        if f.end is not None:
            where.append("c.committer_ts < ?")
            params.append(int(f.end))
    where_sql = " AND ".join(where)

    cte = f"""
    WITH h0 AS (
        SELECT c.sha AS sha, c.committer_ts AS committer_ts, c.subject AS subject,
               c.author_email AS author_email,
               {AUTHOR_KEY_SQL}  AS author_key,
               {AUTHOR_NAME_SQL} AS author_name
        FROM commits c
        {AUTHOR_JOIN}
        WHERE {where_sql}
    ),
    h AS (SELECT * FROM h0 {{authors_filter}})
    """
    if f.authors:
        marks = ",".join("?" for _ in f.authors)
        cte = cte.format(authors_filter=f"WHERE author_key IN ({marks})")
        params.extend(f.authors)
    else:
        cte = cte.format(authors_filter="")
    return cte, params


def _commit_count(conn: sqlite3.Connection, cte: str, params: list) -> int:
    row = conn.execute(f"{cte} SELECT COUNT(*) AS n FROM h", params).fetchone()
    return int(row["n"] or 0)


def _derive(added: int, removed: int, modifications: int, commit_count: int) -> dict:
    growth = added - removed
    churn = added + removed
    return {
        "added": added,
        "removed": removed,
        "growth": growth,
        "churn": churn,
        "modifications": modifications,
        "modification_frequency": (modifications / commit_count) if commit_count else 0.0,
        "churn_rate": (churn / commit_count) if commit_count else 0.0,
    }


# --------------------------------------------------------------------------- #
# views
# --------------------------------------------------------------------------- #

def summary(conn: sqlite3.Connection, repo_id: int, f: Filter) -> dict:
    """Added/removed/growth/churn/modifications/frequency/churn-rate for one
    object (file, directory, or the whole repository when no path is set)."""
    _prepare(conn, repo_id, f)
    cte, params = _h_cte(f, repo_id)
    obj_sql, obj_params = f.object_clause()
    row = conn.execute(f"""
        {cte}
        SELECT COALESCE(SUM(fc.added), 0)   AS added,
               COALESCE(SUM(fc.removed), 0) AS removed,
               COUNT(DISTINCT CASE WHEN fc.added + fc.removed > 0 THEN fc.sha END) AS modifications
        FROM h
        JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
        WHERE 1 = 1 {obj_sql}
    """, params + [repo_id] + obj_params).fetchone()
    n = _commit_count(conn, cte, params)
    out = _derive(int(row["added"]), int(row["removed"]), int(row["modifications"]), n)
    out["commit_count"] = n
    out["object"] = {"path": (f.path or "").strip("/"),
                     "type": f.object_type or ("file" if f.path else "root")}
    return out


def files(conn: sqlite3.Connection, repo_id: int, f: Filter) -> dict:
    """Per-file commit-set metrics for every file below the selected object."""
    _prepare(conn, repo_id, f)
    cte, params = _h_cte(f, repo_id)
    obj_sql, obj_params = f.object_clause()
    limit = max(1, min(int(f.limit or 500), 20_000))
    rows = conn.execute(f"""
        {cte}
        SELECT fc.path AS path,
               SUM(fc.added)   AS added,
               SUM(fc.removed) AS removed,
               SUM(CASE WHEN fc.added + fc.removed > 0 THEN 1 ELSE 0 END) AS modifications
        FROM h
        JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
        WHERE 1 = 1 {obj_sql}
        GROUP BY fc.path
        ORDER BY SUM(fc.added + fc.removed) DESC, fc.path
        LIMIT ?
    """, params + [repo_id] + obj_params + [limit]).fetchall()
    n = _commit_count(conn, cte, params)
    items = []
    for r in rows:
        item = {"path": r["path"]}
        item.update(_derive(int(r["added"]), int(r["removed"]), int(r["modifications"]), n))
        items.append(item)
    return {"commit_count": n, "items": items}


def dirs(conn: sqlite3.Connection, repo_id: int, f: Filter) -> dict:
    """Per-directory commit-set metrics (subtree sums).

    Correctly *de-duplicates* modifications per commit: a commit that touches
    several files in the same directory counts once for that directory.
    """
    _prepare(conn, repo_id, f)
    cte, params = _h_cte(f, repo_id)
    obj_sql, obj_params = f.object_clause()
    rows = conn.execute(f"""
        {cte}
        SELECT fc.sha AS sha, fc.path AS path, fc.added AS added, fc.removed AS removed
        FROM h
        JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
        WHERE fc.added + fc.removed > 0 {obj_sql}
        ORDER BY fc.sha
    """, params + [repo_id] + obj_params).fetchall()
    n = _commit_count(conn, cte, params)

    scope = (f.path or "").strip("/") if f.object_type == "dir" else ""
    scope_prefix = scope + "/" if scope else ""

    agg: dict[str, dict] = {}

    def acc(path: str) -> dict:
        return agg.setdefault(path, {"added": 0, "removed": 0, "modifications": 0})

    last_sha = None
    touched: set[str] = set()

    def close_commit() -> None:
        for d in touched:
            agg[d]["modifications"] += 1

    for r in rows:
        sha = r["sha"]
        if sha != last_sha:
            if last_sha is not None:
                close_commit()
            touched = set()
            last_sha = sha
        parts = r["path"].split("/")
        # ancestor directories incl. the root (''); the file itself is not a dir
        for i in range(0, len(parts)):
            d = "/".join(parts[:i])
            if scope and not (d == scope or d.startswith(scope_prefix)):
                continue
            node = acc(d)
            node["added"] += int(r["added"])
            node["removed"] += int(r["removed"])
            touched.add(d)
    if last_sha is not None:
        close_commit()

    if scope:                                    # always report the scope node itself
        acc(scope)

    items = []
    for path, node in sorted(agg.items(), key=lambda kv: (kv[0].count("/"), kv[0])):
        item = {"path": path, "depth": path.count("/") + (1 if path else 0)}
        item.update(_derive(node["added"], node["removed"], node["modifications"], n))
        items.append(item)
    return {"commit_count": n, "items": items}


def authors(conn: sqlite3.Connection, repo_id: int, f: Filter) -> dict:
    """Per-author modifications / churn / ownership for the object."""
    _prepare(conn, repo_id, f)
    cte, params = _h_cte(f, repo_id)
    obj_sql, obj_params = f.object_clause()
    rows = conn.execute(f"""
        {cte}
        SELECT h.author_key  AS author_key,
               h.author_name AS author,
               COUNT(DISTINCT h.sha) AS commits,
               COUNT(DISTINCT CASE WHEN fc.added + fc.removed > 0 THEN fc.sha END) AS modifications,
               COALESCE(SUM(fc.added + fc.removed), 0) AS churn
        FROM h
        JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
        WHERE 1 = 1 {obj_sql}
        GROUP BY h.author_key, h.author_name
        ORDER BY churn DESC, author COLLATE NOCASE
    """, params + [repo_id] + obj_params).fetchall()
    n = _commit_count(conn, cte, params)
    churn_total = sum(int(r["churn"]) for r in rows)
    items = [{
        "author_key": r["author_key"],
        "author": r["author"],
        "commits": int(r["commits"]),
        "modifications": int(r["modifications"]),
        "churn": int(r["churn"]),
        "ownership": (int(r["churn"]) / churn_total) if churn_total else 0.0,
    } for r in rows]
    return {"commit_count": n, "churn_total": churn_total, "items": items}


_BUCKET_SQL = {
    "day":   "strftime('%Y-%m-%d', h.committer_ts, 'unixepoch')",
    "month": "strftime('%Y-%m-01', h.committer_ts, 'unixepoch')",
    "week":  ("date(h.committer_ts, 'unixepoch',"
              " '-' || ((CAST(strftime('%w', h.committer_ts, 'unixepoch') AS INTEGER) + 6) % 7)"
              " || ' days')"),
}


def timeseries(conn: sqlite3.Connection, repo_id: int, f: Filter) -> dict:
    """Added / removed / growth / churn / commits over time buckets."""
    _prepare(conn, repo_id, f)
    if f.granularity not in _BUCKET_SQL:
        f.granularity = "month"
    cte, params = _h_cte(f, repo_id)
    obj_sql, obj_params = f.object_clause()
    bucket = _BUCKET_SQL[f.granularity]
    rows = conn.execute(f"""
        {cte}
        SELECT {bucket} AS bucket,
               COALESCE(SUM(fc.added), 0)   AS added,
               COALESCE(SUM(fc.removed), 0) AS removed,
               COUNT(DISTINCT fc.sha) AS commits,
               COUNT(DISTINCT CASE WHEN fc.added + fc.removed > 0 THEN fc.sha END) AS modifications
        FROM h
        JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
        WHERE 1 = 1 {obj_sql}
        GROUP BY bucket
        ORDER BY bucket
    """, params + [repo_id] + obj_params).fetchall()
    n = _commit_count(conn, cte, params)
    items = []
    for r in rows:
        try:
            ts = calendar.timegm(_dt.datetime.strptime(r["bucket"], "%Y-%m-%d").timetuple())
        except (TypeError, ValueError):
            ts = 0
        items.append({
            "bucket": r["bucket"],
            "bucket_ts": ts,
            "added": int(r["added"]),
            "removed": int(r["removed"]),
            "growth": int(r["added"]) - int(r["removed"]),
            "churn": int(r["added"]) + int(r["removed"]),
            "commits": int(r["commits"]),
            "modifications": int(r["modifications"]),
        })
    return {"commit_count": n, "granularity": f.granularity, "items": items}


def commit_set_rows(conn: sqlite3.Connection, repo_id: int, f: Filter) -> dict:
    """The commits of H themselves (paged), with their object-level stats."""
    _prepare(conn, repo_id, f)
    cte, params = _h_cte(f, repo_id)
    has_object = bool((f.path or "").strip("/"))
    obj_sql, obj_params = f.object_clause()

    having = ""
    if f.only_changed:
        having = (" HAVING COALESCE(SUM(CASE WHEN fc.added + fc.removed > 0 THEN 1 ELSE 0 END), 0) > 0")

    limit = max(1, min(int(f.limit or 50), 1000))
    offset = max(0, int(f.offset or 0))
    rows = conn.execute(f"""
        {cte}
        SELECT h.sha AS sha, h.committer_ts AS committer_ts, h.author_name AS author,
               h.author_key AS author_key, h.subject AS subject,
               COALESCE(SUM(fc.added), 0)   AS added,
               COALESCE(SUM(fc.removed), 0) AS removed,
               COALESCE(SUM(CASE WHEN fc.added + fc.removed > 0 THEN 1 ELSE 0 END), 0) AS touched
        FROM h
        LEFT JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
             {'AND fc.path = ?' if has_object and f.object_type == 'file' else ''}
             {'AND fc.path >= ? AND fc.path < ?' if has_object and f.object_type != 'file' else ''}
        GROUP BY h.sha
        {having}
        ORDER BY h.committer_ts DESC, h.sha
        LIMIT ? OFFSET ?
    """, params + [repo_id] + obj_params + [limit, offset]).fetchall()

    total = _commit_count(conn, cte, params)
    if f.only_changed:
        total = conn.execute(f"""
            {cte}
            SELECT COUNT(*) AS n FROM (
                SELECT h.sha FROM h
                LEFT JOIN file_changes fc ON fc.repo_id = ? AND fc.sha = h.sha
                     {'AND fc.path = ?' if has_object and f.object_type == 'file' else ''}
                     {'AND fc.path >= ? AND fc.path < ?' if has_object and f.object_type != 'file' else ''}
                GROUP BY h.sha
                {having}
            )
        """, params + [repo_id] + obj_params).fetchone()["n"]
    items = [{
        "sha": r["sha"],
        "short": r["sha"][:10],
        "committer_ts": int(r["committer_ts"]),
        "author": r["author"],
        "author_key": r["author_key"],
        "subject": r["subject"],
        "added": int(r["added"]),
        "removed": int(r["removed"]),
        "churn": int(r["added"]) + int(r["removed"]),
    } for r in rows]
    return {"commit_count": total, "total": total, "items": items}


VIEWS = {
    "summary": summary,
    "files": files,
    "dirs": dirs,
    "authors": authors,
    "timeseries": timeseries,
    "commits": commit_set_rows,
}


def run_view(conn: sqlite3.Connection, repo_id: int, view: str, f: Filter) -> dict:
    return VIEWS[view](conn, repo_id, f)


# --------------------------------------------------------------------------- #
# tiny TTL cache for expensive aggregate views
# --------------------------------------------------------------------------- #

_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL = 30.0
_CACHE_MAX = 256


def cache_get(key: tuple) -> dict | None:
    hit = _CACHE.get(key)
    if hit is None:
        return None
    expires, value = hit
    if expires < _time.monotonic():
        _CACHE.pop(key, None)
        return None
    return value


def cache_put(key: tuple, value: dict) -> None:
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = (_time.monotonic() + _CACHE_TTL, value)


def cache_invalidate(repo_id: int | None = None) -> None:
    if repo_id is None:
        _CACHE.clear()
        return
    for key in [k for k in _CACHE if k[0] == repo_id]:
        _CACHE.pop(key, None)
