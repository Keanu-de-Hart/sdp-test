---
kind: dependency_management
name: Dual-Toolchain Dependency Management (pip + npm with Makefile Orchestration)
category: dependency_management
scope:
    - '**'
source_files:
    - backend/requirements.txt
    - frontend/package.json
    - frontend/package-lock.json
    - Makefile
---

## Approach

RAT is a monorepo with two independent language toolchains, each managing its own dependencies:

- **Backend (Python/FastAPI)** — uses `pip` with a flat `requirements.txt` and an isolated virtual environment under `backend/.venv/`.
- **Frontend (TypeScript/Vite/React)** — uses `npm` with `package.json` plus a committed `frontend/package-lock.json` lockfile.

A top-level `Makefile` acts as the single entry point that bootstraps both environments (`make install`, `make dev`, `make build`, `make test`).

## Key Files

- `backend/requirements.txt` — declares runtime and test dependencies for the Python side.
- `frontend/package.json` — declares runtime (`react`, `echarts`, `react-router-dom`) and development (`typescript`, `vite`, `@vitejs/plugin-react`, `@types/*`) dependencies.
- `frontend/package-lock.json` — npm lockfile pinning exact transitive versions.
- `Makefile` — orchestrates venv creation, pip install, npm install, and runs both servers.

## Conventions Observed

### Python side

- Dependencies are declared in a single `backend/requirements.txt` using `>=` lower-bound ranges (e.g. `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `python-multipart>=0.0.9`, `pytest>=8.0`, `httpx>=0.27`). No `pyproject.toml`, no `Pipfile`, no `poetry.lock`.
- The virtual environment lives at `backend/.venv/` and is created by the `backend/.venv/bin/python` Makefile target via `python3 -m venv backend/.venv`, followed by `pip install --upgrade pip wheel` and `pip install -q -r backend/requirements.txt`.
- Tests run inside the venv: `make test` executes `.venv/bin/python -m pytest -q` from the `backend/` directory.
- There is no `requirements.in` / `pip-tools` resolution step; `requirements.txt` is installed directly.

### Frontend side

- Dependencies are split between `dependencies` (runtime: `echarts`, `react`, `react-dom`, `react-router-dom`) and `devDependencies` (build/tooling: `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `typescript`, `vite`).
- Versions use caret (`^`) ranges, allowing compatible minor/patch updates.
- `frontend/package-lock.json` is committed to the repo, so CI and other developers get deterministic installs.
- `npm install` is invoked through `$(NPM) = npm --prefix frontend` with flags `--no-audit --no-fund` to suppress security advisories and funding prompts during automated installs.

### Monorepo orchestration

- All dependency installation flows go through the root `Makefile`; there is no per-subproject `setup.py` or separate CI script for installing deps.
- `make install` creates the Python venv and then runs `npm --prefix frontend install --no-audit --no-fund`.
- `make dev` starts both `uvicorn` (FastAPI on :8000) and `vite` (dev server on :5173) concurrently.
- `make build` runs `tsc --noEmit && vite build`, producing artifacts under `frontend/dist/`.

## Constraints & Rules

- **No vendoring**: Neither the Python nor the Node side vendors third-party source code into the repo. Python packages are installed into `backend/.venv/` (gitignored), and Node packages land in `frontend/node_modules/` (also gitignored).
- **No private registry configuration**: Neither `requirements.txt` nor `package.json` references custom indexes, registries, or authentication tokens; both rely on the default PyPI and npm registries.
- **No lockfile for Python**: Unlike the frontend's committed `package-lock.json`, the Python side has no lockfile; reproducibility relies on the `>=` version bounds in `requirements.txt` combined with the pinned `package-lock.json` for the frontend.
- **Audit/fund suppression**: `make install` explicitly passes `--no-audit --no-fund` to npm, indicating that automated dependency installation should not block on security advisories or funding prompts.