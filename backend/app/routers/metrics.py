"""Metric query endpoints. One POST endpoint per view, all sharing the same filter body."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from .. import db, metrics, schemas

router = APIRouter(prefix="/api/repos", tags=["metrics"])


@router.post("/{repo_id}/metrics/{view}")
def metric_view(repo_id: int, view: str, body: schemas.MetricsFilters) -> dict:
    if view not in metrics.VIEWS:
        raise HTTPException(status_code=404, detail=f"Unknown metric view '{view}'.")

    payload = body.model_dump()
    cache_key = (repo_id, view, json.dumps(payload, sort_keys=True))
    cached = metrics.cache_get(cache_key)
    if cached is not None:
        return cached

    with db.connect() as conn:
        exists = conn.execute("SELECT status FROM repos WHERE id = ?", (repo_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Repository not found.")
        if exists["status"] != "ready":
            raise HTTPException(status_code=409,
                                detail=f"Repository is not ready yet (status: {exists['status']}).")
        f = metrics.Filter(
            start=body.start, end=body.end, commits=body.commits, authors=body.authors,
            path=body.path, object_type=body.object_type, granularity=body.granularity,
            limit=body.limit, offset=body.offset, only_changed=body.only_changed,
        )
        result = metrics.run_view(conn, repo_id, view, f)

    response = {"repo_id": repo_id, "view": view, **result}
    metrics.cache_put(cache_key, response)
    return response
