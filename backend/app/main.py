"""RAT — Repo Analysis Tool. FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST
from .db import init_db
from .routers import authors, commits, metrics, repos

app = FastAPI(title="RAT — Repo Analysis Tool", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(repos.router)
app.include_router(metrics.router)
app.include_router(authors.router)
app.include_router(commits.router)

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    """Serve the built frontend (SPA fallback); /api/* is never captured."""
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found.")
    if FRONTEND_DIST.is_dir():
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
    return JSONResponse(
        {"detail": "Frontend is not built yet. Run `make build` (or use the Vite dev server) first."},
        status_code=404,
    )
