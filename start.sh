#!/usr/bin/env bash
# RAT — Repo Analysis Tool: one-shot start.
#
# Installs Python + Node dependencies (idempotent, first run takes a while),
# builds the frontend, then serves the full dashboard on http://localhost:8000.
set -euo pipefail
cd "$(dirname "$0")"

make install   # python venv + backend deps, npm install for the frontend
make run       # type-check + build the frontend, then serve everything on :8000
