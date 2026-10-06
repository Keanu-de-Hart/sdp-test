# RAT — Repo Analysis Tool. Common dev / build / test entry points.
SHELL := /bin/bash

PY      := backend/.venv/bin/python
PIP     := backend/.venv/bin/pip
NPM     := npm --prefix frontend
UVICORN := $(PY) -m uvicorn app.main:app --app-dir backend

.DEFAULT_GOAL := help
.PHONY: help venv install api web dev build run test verify clean

help:
	@echo "RAT — Repo Analysis Tool"
	@echo ""
	@echo "  make install   Create the Python venv and install backend + frontend deps"
	@echo "  make dev       Run the API (:8000) and the Vite dev server (:5173) together"
	@echo "  make api       Run the API only (:8000, auto-reload)"
	@echo "  make web       Run the Vite dev server only (:5173)"
	@echo "  make build     Type-check and build the frontend into frontend/dist"
	@echo "  make run       Build the frontend, then serve everything on :8000"
	@echo "  make test      Run the backend test suite (pytest)"
	@echo "  make verify    Spot-check metrics: make verify ARGS='--api http://localhost:8000 --repo cJSON'"
	@echo "  make clean     Remove runtime data, caches and the frontend build"

backend/.venv/bin/python:
	python3 -m venv backend/.venv
	$(PIP) install --upgrade pip wheel -q
	$(PIP) install -q -r backend/requirements.txt

venv: backend/.venv/bin/python

install: venv
	$(NPM) install --no-audit --no-fund

api: venv
	$(UVICORN) --host 0.0.0.0 --port 8000 --reload

web:
	$(NPM) run dev

dev: venv
	@echo "API on :8000, Vite dev server on :5173 — Ctrl-C stops both."
	@trap 'kill 0' EXIT INT TERM; \
	$(UVICORN) --host 127.0.0.1 --port 8000 --reload & \
	$(NPM) run dev & \
	wait

build:
	$(NPM) run build

run: build
	$(UVICORN) --host 0.0.0.0 --port 8000

test: venv
	cd backend && .venv/bin/python -m pytest -q

verify: venv
	$(PY) scripts/verify_metrics.py $(ARGS)

clean:
	rm -rf backend/data frontend/dist backend/.pytest_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
