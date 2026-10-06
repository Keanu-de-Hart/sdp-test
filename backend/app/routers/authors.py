"""Author listing and manual merge endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import authors, db, metrics, schemas
from .repos import _get_repo

router = APIRouter(prefix="/api/repos", tags=["authors"])


@router.get("/{repo_id}/authors")
def list_authors(repo_id: int) -> dict:
    with db.connect() as conn:
        _get_repo(conn, repo_id)
        return authors.list_authors(conn, repo_id)


@router.post("/{repo_id}/author-merges")
def merge_authors(repo_id: int, body: schemas.MergeRequest) -> dict:
    with db.connect() as conn:
        _get_repo(conn, repo_id)
        try:
            authors.merge_authors(conn, repo_id, body.identities, body.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        result = authors.list_authors(conn, repo_id)
    metrics.cache_invalidate(repo_id)
    return result


@router.delete("/{repo_id}/author-merges/{identity}")
def unmerge_identity(repo_id: int, identity: str) -> dict:
    with db.connect() as conn:
        _get_repo(conn, repo_id)
        authors.unmerge_identity(conn, repo_id, identity)
        result = authors.list_authors(conn, repo_id)
    metrics.cache_invalidate(repo_id)
    return result


@router.delete("/{repo_id}/author-groups/{group_id}")
def unmerge_group(repo_id: int, group_id: int) -> dict:
    with db.connect() as conn:
        _get_repo(conn, repo_id)
        authors.unmerge_group(conn, repo_id, group_id)
        result = authors.list_authors(conn, repo_id)
    metrics.cache_invalidate(repo_id)
    return result
