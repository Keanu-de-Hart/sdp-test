"""Repository management endpoints: upload (zip), clone (URL), list, delete."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import db, metrics
from ..config import REPOS_DIR
from ..ingest import start_ingest_thread
from ..schemas import CloneRequest

router = APIRouter(prefix="/api/repos", tags=["repos"])

_REPO_FIELDS = ("id", "name", "source_type", "source", "ref", "status", "progress",
                "progress_detail", "error", "head_sha", "commit_count", "have_mailmap",
                "created_at", "path")


def repo_out(row) -> dict:
    return {k: row[k] for k in _REPO_FIELDS}


def _get_repo(conn, repo_id: int):
    row = conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return row


def _create_repo(conn, *, name: str, source_type: str, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO repos(name, source_type, source, status, created_at) VALUES (?,?,?,?,?)",
        (name, source_type, source, "pending", int(time.time())),
    )
    conn.commit()
    return int(cur.lastrowid)


@router.get("")
def list_repos() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM repos ORDER BY created_at DESC, id DESC").fetchall()
    return [repo_out(r) for r in rows]


@router.post("/upload")
async def upload_repo(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".zip", ".git"):
        raise HTTPException(status_code=400, detail="Please upload a .zip archive of the repository.")

    tmp = tempfile.NamedTemporaryFile(prefix="rat-upload-", suffix=".zip", delete=False)
    try:
        while chunk := await file.read(1 << 20):
            tmp.write(chunk)
        tmp.close()
        import zipfile
        if not zipfile.is_zipfile(tmp.name):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid zip archive.")
    except HTTPException:
        Path(tmp.name).unlink(missing_ok=True)
        raise
    except OSError as exc:
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not store upload: {exc}")

    name = Path(file.filename).stem or "repository"
    with db.connect() as conn:
        repo_id = _create_repo(conn, name=name, source_type="zip", source=file.filename)
        repo = repo_out(_get_repo(conn, repo_id))
    start_ingest_thread(repo_id, "zip", tmp.name)
    return repo


@router.post("/clone")
def clone_repo(req: CloneRequest) -> dict:
    url = req.url.strip()
    if not (url.startswith(("http://", "https://", "git://", "ssh://")) or url.startswith("git@")):
        raise HTTPException(status_code=400, detail="Provide a valid git URL (https://, ssh:// or git@…).")
    name = (req.name or "").strip()
    if not name:
        tail = url.rstrip("/").split("/")[-1]
        name = tail[:-4] if tail.endswith(".git") else tail
    with db.connect() as conn:
        repo_id = _create_repo(conn, name=name or "repository", source_type="clone", source=url)
        repo = repo_out(_get_repo(conn, repo_id))
    start_ingest_thread(repo_id, "clone", url)
    return repo


@router.get("/{repo_id}")
def get_repo(repo_id: int) -> dict:
    with db.connect() as conn:
        return repo_out(_get_repo(conn, repo_id))


@router.delete("/{repo_id}")
def delete_repo(repo_id: int) -> dict:
    with db.connect() as conn:
        _get_repo(conn, repo_id)
        with conn:
            conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
    dest = REPOS_DIR / str(repo_id)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    metrics.cache_invalidate(repo_id)
    return {"ok": True}
