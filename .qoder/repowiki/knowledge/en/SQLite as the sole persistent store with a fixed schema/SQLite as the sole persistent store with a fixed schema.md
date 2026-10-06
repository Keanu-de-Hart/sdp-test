---
kind: design
name: SQLite as the sole persistent store with a fixed schema
source: session
category: adr
---

# SQLite as the sole persistent store with a fixed schema

_Source: coding plans from commit period a90c931 → f91fbcd — records intent at planning time; the implementation may lag or differ._

## Context
The project targets a single-port production deployment without extra infrastructure dependencies; the backend already uses Python stdlib sqlite3.

## Decision drivers
- zero external dependencies
- single-port prod mode
- simple backup/restore

## Considered options
- **PostgreSQL / MySQL** _(rejected)_ — pros: mature concurrency, richer types; cons: requires separate service, adds deployment complexity
- **In-memory dict + pickle snapshot** _(rejected)_ — pros: fastest reads; cons: no persistence across restarts, no WAL, hard to share state
- **SQLite with WAL mode and explicit indexes** — pros: embedded, durable, low ops overhead, supports concurrent readers; cons: write contention under heavy re-ingestion

## Decision
Persist everything in one SQLite database (`backend/data/rat.db`) with tables `repos`, `commits`, `file_changes`, `author_merges`; add indexes on `(repo_id, committer_ts)` and `(repo_id, author_email)` and use WAL mode for concurrent reads during indexing.

## Consequences
Deployment is a single process serving both API and static frontend on :8000. Backup is copying the file. Write-heavy operations (re-ingest) briefly block readers; query paths rely on the specified indexes.