---
kind: design
name: Metrics computed from indexed rows via SQL aggregations plus a single Python formula layer
source: session
category: adr
---

# Metrics computed from indexed rows via SQL aggregations plus a single Python formula layer

_Source: coding plans from commit period a90c931 → f91fbcd — records intent at planning time; the implementation may lag or differ._

## Context
Dashboard views (summary, files, dirs, authors, timeseries) must respond in <500 ms over repositories up to ~75k commits, so expensive computation cannot live in the UI or per-request Python loops.

## Decision drivers
- interactive response time
- single source of truth for formulas
- avoid client-side aggregation

## Considered options
- **Client-side aggregation over raw commit list** _(rejected)_ — pros: flexible UI; cons: transfers all commits to browser; unusable on large repos
- **Precompute every view eagerly** _(rejected)_ — pros: instant reads; cons: expensive writes, storage blowup, stale data on filter changes
- **SQL-backed aggregation with `metrics.py` as the canonical formula implementation** — pros: server-side only, deterministic, reusable by tests; cons: Python post-processing for dir folding and ownership ratios

## Decision
All metric formulas live in `backend/app/metrics.py`; queries build SQL filters (time range, manual commits, author, path prefix via `path >= 'd/' AND path < 'd0'`) and aggregate over `commits`/`file_changes`. Directory aggregates fold per-file results into ancestor dirs in Python; ownership and rates are derived after aggregation.

## Consequences
Formula correctness is testable independently via golden fixtures. Response cache keyed by filter hash avoids recomputation. Dir-level aggregation adds a small Python pass after SQL, keeping the hot path in the DB.