---
kind: build_system
name: Makefile-driven monorepo build for FastAPI + Vite/React
category: build_system
scope:
    - '**'
source_files:
    - Makefile
    - backend/requirements.txt
    - frontend/package.json
---

## Build approach

The repository is a Python/FastAPI backend and a TypeScript/Vite React frontend assembled as a top-level monorepo. There is no Dockerfile, CI pipeline, or release automation in the repo; the build surface is a single `Makefile` at the repository root that orchestrates both subprojects.

## Key files

- `Makefile` — top-level entry point for every developer workflow (install, dev, build, run, test, verify, clean).
- `backend/requirements.txt` — pinned-with-minimum-version constraints for the Python runtime (`fastapi`, `uvicorn[standard]`, `python-multipart`, `pytest`, `httpx`).
- `frontend/package.json` — Vite + TypeScript build scripts; `build` runs `tsc --noEmit` first, then `vite build`.
- `frontend/vite.config.ts` — Vite configuration (referenced by the Makefile's npm invocation).
- `scripts/verify_metrics.py` — ad-hoc verification script invoked via `make verify`.

## Architecture and conventions

### Virtual environment
The Makefile creates an isolated Python venv at `backend/.venv` on demand:

```
backend/.venv/bin/python: python3 -m venv backend/.venv && pip install -r backend/requirements.txt
```

All Python tooling goes through the Makefile variables `PY := backend/.venv/bin/python` and `PIP := backend/.venv/bin/pip`; nothing in the repo invokes system `python` directly for project work.

### Frontend dependency management
Frontend dependencies are installed via `npm --prefix frontend install` (target `install`), which delegates to `frontend/package.json`. The frontend build script `tsc --noEmit && vite build` enforces type-checking before emitting assets into `frontend/dist`.

### Unified dev server
The `dev` target launches both services concurrently in the same shell process using background jobs and a trap:

```bash
trap 'kill 0' EXIT INT TERM;
$(UVICORN) --host 127.0.0.1 --port 8000 --reload &
$(NPM) run dev &
wait
```

This ensures Ctrl-C stops both the API and the Vite dev server together. The API binds to `127.0.0.1` in dev mode (not `0.0.0.0`).

### Production-style run
`make run` first builds the frontend (`build` → `npm run build`) and then serves the FastAPI app with `uvicorn` bound to `0.0.0.0:8000` without auto-reload. This is the only production-oriented target in the repo.

### Testing
Backend tests are executed via `make test`, which `cd`s into `backend` and runs `.venv/bin/python -m pytest -q`. No test discovery flags beyond `-q` are used; pytest defaults apply.

### Metrics verification
`make verify ARGS='--api http://localhost:8000 --repo cJSON'` runs `scripts/verify_metrics.py` against a live API instance. This is an optional smoke-test, not part of the normal test suite.

### Clean target
`make clean` removes generated/runtime artifacts: `backend/data`, `frontend/dist`, `backend/.pytest_cache`, and all `__pycache__` directories under `backend/`.

## Conventions and constraints

- All developer commands go through `make`; there are no top-level shell scripts or CI YAMLs in this repository.
- Backend dependencies are declared exclusively in `backend/requirements.txt` and installed into `backend/.venv`; the Makefile is the sole installer.
- Frontend dependencies are declared exclusively in `frontend/package.json` and installed via `npm --prefix frontend`.
- The frontend build always performs a strict TypeScript check (`tsc --noEmit`) before emitting assets — a type error will fail `make build` / `make run`.
- The default goal is `help`; running `make` without arguments prints available targets rather than building anything.
- There is no containerization, cross-compilation, version bumping, or release automation present in the repository (grep for `docker|Dockerfile|ci\.yml|github.*actions|workflow` returns zero matches).