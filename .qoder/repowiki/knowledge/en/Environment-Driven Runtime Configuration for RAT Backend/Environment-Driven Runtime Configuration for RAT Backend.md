---
kind: configuration_system
name: Environment-Driven Runtime Configuration for RAT Backend
category: configuration_system
scope:
    - '**'
source_files:
    - backend/app/config.py
    - backend/app/main.py
    - backend/app/db.py
    - Makefile
    - frontend/vite.config.ts
    - scripts/verify_metrics.py
    - backend/tests/conftest.py
---

# Configuration System

## Approach

RAT uses a minimal, environment-variable-driven configuration approach. There is no `.env` file loader, no YAML/TOML/JSON config files, and no feature-flag framework. Runtime paths are resolved at import time from `os.environ`, with sensible defaults derived from the package layout.

## Key Files

- `backend/app/config.py` — single source of truth for runtime paths (`DATA_DIR`, `REPOS_DIR`, `DB_PATH`, `FRONTEND_DIST`).
- `backend/app/main.py` — FastAPI entry point that consumes `FRONTEND_DIST` to mount the SPA static assets.
- `backend/app/db.py` — SQLite layer that imports `DB_PATH` from `config.py` and applies PRAGMAs (WAL journal, synchronous=NORMAL, foreign_keys=ON).
- `Makefile` — hard-codes dev/runtime ports (`8000` for uvicorn, `5173` for Vite) and the default data directory via `backend/data`.
- `frontend/vite.config.ts` — hard-codes the Vite dev server port (`5173`) and proxies `/api` to `http://localhost:8000`.
- `scripts/verify_metrics.py` — overrides `RAT_DATA_DIR` before running verification against a test database.
- `backend/tests/conftest.py` — sets `RAT_DATA_DIR` to an in-process temp directory so tests never touch the real data dir.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `RAT_DATA_DIR` | `backend/data` (relative to `backend/app`) | Root for SQLite DB and cloned repos. Created with `mkdir(parents=True, exist_ok=True)` on import. |
| `RAT_FRONTEND_DIST` | `frontend/dist` (relative to repo root) | Directory containing the built SPA; if absent, the API serves a 404 JSON fallback. |

No other environment variables are read by application code. The only other `os.environ` usage is in `ingest.py`, which passes a copy of the process environment to child git processes (not configuration).

## Conventions Observed

1. **Path-only configuration.** All configurable values are filesystem paths; there are no typed settings classes, validation, or schema enforcement.
2. **Defaults baked into code.** Every env var has a path-based default computed from `BASE_DIR = Path(__file__).resolve().parent.parent`. This keeps the app runnable without any env setup.
3. **Eager initialization side effects.** Importing `config.py` creates `DATA_DIR` and `REPOS_DIR` on disk. Consumers (e.g. `db.init_db()`) rely on these directories existing.
4. **Single responsibility split.** `config.py` exposes module-level constants; consumers import them directly rather than going through a getter function.
5. **Test isolation via env override.** Tests set `RAT_DATA_DIR` to a temporary directory before importing the app, ensuring no cross-test state leakage.
6. **Hard-coded operational defaults elsewhere.** Ports (`8000`, `5173`), CORS origins (`http://localhost:5173`, `http://127.0.0.1:5173`), and the proxy target in `vite.config.ts` are all literal strings — not pulled from env.
7. **No secrets management.** Database credentials, API keys, or other secrets do not appear anywhere in the codebase (SQLite is file-backed).

## Constraints Enforced by Code

- `DATA_DIR` and `REPOS_DIR` are guaranteed to exist after `config.py` is imported because they are created eagerly with `mkdir(parents=True, exist_ok=True)`.
- `DB_PATH` always resolves under `DATA_DIR` as `rat.db`; it cannot be configured independently.
- The SPA fallback route in `main.py` only serves files whose resolved path stays within `FRONTEND_DIST` (checked via `FRONTEND_DIST.resolve() in candidate.parents`), preventing path traversal outside the configured dist directory.
- The SPA route explicitly rejects any path starting with `api` (raising 404), keeping API routes separate from static-file serving.
- SQLite connections use WAL mode (`PRAGMA journal_mode=WAL`) and `synchronous=NORMAL`, enforced in `db.connect()`.

## Build-Time vs Runtime Distinction

The frontend build is configured statically in `vite.config.ts` (chunk splitting, chunk size warning limit, manual chunks for `echarts` and `react`). There is no runtime configuration for the frontend beyond what Vite injects at build time. The backend's `FRONTEND_DIST` is the only bridge between build output location and runtime behavior.