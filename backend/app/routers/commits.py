"""Commit list and path picker endpoints (used by the dashboard filters)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..authors import AUTHOR_JOIN, AUTHOR_KEY_SQL, AUTHOR_NAME_SQL
from .repos import _get_repo

router = APIRouter(prefix="/api/repos", tags=["commits"])


@router.get("/{repo_id}/commits")
def list_commits(repo_id: int,
                 q: str = "",
                 start: int | None = None,
                 end: int | None = None,
                 limit: int = Query(100, ge=1, le=500),
                 offset: int = Query(0, ge=0)) -> dict:
    where = ["c.repo_id = ?"]
    params: list = [repo_id]
    q = (q or "").strip()
    if q:
        where.append("(c.sha LIKE ? OR c.subject LIKE ? OR c.author_name LIKE ?"
                     " OR c.author_email LIKE ?)")
        like = f"%{q}%"
        params += [f"{q}%", like, like, like]
    if start is not None:
        where.append("c.committer_ts >= ?")
        params.append(int(start))
    if end is not None:
        where.append("c.committer_ts < ?")
        params.append(int(end))
    where_sql = " AND ".join(where)

    with db.connect() as conn:
        _get_repo(conn, repo_id)
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM commits c WHERE {where_sql}", params).fetchone()["n"]
        rows = conn.execute(f"""
            SELECT c.sha AS sha, c.committer_ts AS committer_ts, c.subject AS subject,
                   {AUTHOR_KEY_SQL}  AS author_key,
                   {AUTHOR_NAME_SQL} AS author
            FROM commits c
            {AUTHOR_JOIN}
            WHERE {where_sql}
            ORDER BY c.committer_ts DESC, c.sha
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()
    return {
        "total": int(total),
        "items": [{
            "sha": r["sha"],
            "short": r["sha"][:10],
            "committer_ts": int(r["committer_ts"]),
            "author": r["author"],
            "author_key": r["author_key"],
            "subject": r["subject"],
        } for r in rows],
    }


@router.get("/{repo_id}/paths")
def list_paths(repo_id: int,
               q: str = "",
               limit: int = Query(50, ge=1, le=500)) -> dict:
    """Search files and (derived) directories for the path picker."""
    with db.connect() as conn:
        _get_repo(conn, repo_id)
        rows = conn.execute(
            "SELECT DISTINCT path FROM file_changes WHERE repo_id = ?", (repo_id,)).fetchall()

    files = {r["path"] for r in rows}
    dirs: set[str] = set()
    for p in files:
        parts = p.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))

    q = (q or "").strip().lower()
    items: list[dict] = [{"path": "", "type": "dir", "label": "/ (repository root)"}]
    matches: list[tuple[str, str]] = []
    if q:
        for d in sorted(dirs):
            if q in d.lower():
                matches.append((d, "dir"))
        for f in sorted(files):
            if q in f.lower():
                matches.append((f, "file"))
    else:
        for d in sorted(dirs)[:limit]:
            matches.append((d, "dir"))
        for f in sorted(files)[:limit]:
            matches.append((f, "file"))

    dir_matches = [(p, t) for p, t in matches if t == "dir"][:limit]
    file_matches = [(p, t) for p, t in matches if t == "file"][:limit]
    items += [{"path": p, "type": t, "label": p + ("/" if t == "dir" else "")}
              for p, t in dir_matches]
    items += [{"path": p, "type": t, "label": p + ("/" if t == "dir" else "")}
              for p, t in file_matches]
    return {"items": items[:limit]}
