---
kind: error_handling
name: Error Handling in RAT — IngestError, HTTPException, and Status-Driven Background Errors
category: error_handling
scope:
    - '**'
source_files:
    - backend/app/ingest.py
    - backend/app/main.py
    - backend/app/db.py
    - backend/app/authors.py
---

## Overview

RAT's error handling is split between two layers:

1. **FastAPI request layer** — uses FastAPI's built-in `HTTPException` for invalid requests and returns JSON responses directly.
2. **Background ingestion pipeline** — defines a single application-level exception `IngestError`, raises it from all git/archive operations, and converts it into a persisted `repos.status = 'error'` + `repos.error` row via a broad `except Exception` catch.

There is no centralized error middleware, no custom exception-to-HTTP mapping, and no global try/except around route handlers.

## Key Files

- `backend/app/main.py` — FastAPI app entry point; the only place `HTTPException` is raised (SPA fallback path).
- `backend/app/ingest.py` — defines `IngestError(Exception)` and the background ingestion pipeline that catches all exceptions to persist them.
- `backend/app/db.py` — schema includes an `error TEXT` column on `repos` used to store the last ingestion failure message.
- `backend/app/authors.py` — raises bare `ValueError` for invalid input (`No author identities supplied`).

## Architecture & Conventions

### Application-level exception: `IngestError`

`IngestError` is defined at module scope in `ingest.py` as a thin subclass of `Exception` with the docstring "Raised for user-actionable ingestion failures." It is raised uniformly across the ingestion pipeline:

- `git()` helper wraps `subprocess.run` and raises `IngestError` when `returncode != 0`.
- `clone_repo()` raises `IngestError` on non-zero clone return code.
- `safe_extract_zip()` raises `IngestError` for zip-slip / absolute-path entries.
- `index_repo()` raises `IngestError` when `git log` fails or when the requested ref has no commits.
- `run_ingest()` raises `IngestError("Ingestion cancelled.")` when the user aborts.

The design treats `IngestError` as the canonical signal that a user-triggered operation failed; it is not caught inside the pipeline but bubbles up to `run_ingest`.

### Background error persistence

`run_ingest()` wraps its entire body in `try / except Exception as exc` (with a `# noqa: BLE001 - surfaced to the UI` comment) and, if the repo still exists, calls `set_status('error', None, None, str(exc))`. This turns any exception — including `IngestError` — into a persisted error message visible through the REST API. The `finally` block ensures cleanup of temp files and DB connections regardless of outcome.

This is the only place in the backend where errors are converted into a structured status field rather than propagated as Python exceptions.

### Request-layer errors

The FastAPI app has no custom exception handler registered. Errors surface as:

- `HTTPException(status_code=404, detail="Not found.")` in the SPA fallback route (`main.py`).
- A direct `JSONResponse({"detail": "Frontend is not built yet..."}, status_code=404)` when the frontend assets are missing.
- Bare `ValueError` raised from `authors.py` — FastAPI will convert this to a 500 Internal Server Error by default since there is no handler for it.

There is no repository-wide exception-to-HTTP mapping; each route would need its own try/except if it wants to return a specific HTTP status.

### No panic/recover pattern

Python has no `panic`/`recover`; the closest equivalent is the broad `except Exception` in `run_ingest()`, which intentionally swallows all errors to keep the background thread alive and record the failure state.

### Frontend-side errors

The frontend does not define a dedicated error model. Network/API errors are handled inline in components (e.g., `RepoGate.tsx`, `CommitPicker.tsx`) using standard `fetch`/`axios` error branches and React state. There is no global error boundary or toast-based error system beyond the existing `ToastContext` in `state/ToastContext.tsx`.

## Conventions Observed

- All ingestion-related failures raise `IngestError` with a human-readable message string; callers do not inspect exception types further.
- Git command failures are funneled through the `git()` helper so they consistently become `IngestError`.
- Archive extraction rejects unsafe paths (`/`, `\`, `..` traversal) before touching the filesystem, raising `IngestError`.
- Background task errors are persisted to `repos.error` and transition the repo to `status='error'` — clients poll this status to report failures to users.
- The `repos` table schema explicitly documents the `status` enum values: `pending|cloning|extracting|indexing|ready|error`.
- Input validation in routes raises plain `ValueError` rather than a custom domain error type.
- No global FastAPI exception handler is configured; error presentation is ad-hoc per route.
- The `except Exception` in `run_ingest` is deliberately broad and documented with a `noqa` lint suppression, indicating the intentional trade-off of swallowing all errors to preserve thread liveness.