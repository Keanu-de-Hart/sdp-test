---
kind: design
name: Single-pass git log --numstat ingestion into SQLite with WAL mode
source: session
category: adr
---

# Single-pass git log --numstat ingestion into SQLite with WAL mode

_Source: coding plans from commit period a90c931 → f91fbcd — records intent at planning time; the implementation may lag or differ._

## Context
The tool must index a repository once and serve interactive dashboard queries against it. A per-commit diff would be too slow for large repos, while loading the entire `git log` output into memory is unsafe.

## Decision drivers
- memory safety on large repos
- one-time indexing cost
- fast read-only queries

## Considered options
- **Per-commit subprocess diffs** _(rejected)_ — pros: simple logic, no streaming parser; cons: O(commits) external processes; rename detection repeated; unacceptable latency at scale
- **Load full `git log` output in memory** _(rejected)_ — pros: simpler parsing loop; cons: unbounded memory use on big repos; risk of OOM
- **Streamed `git log --numstat -z` with NUL-split chunks and batched WAL transactions** — pros: constant memory, one subprocess per repo, fast bulk inserts; cons: parser must handle `-z` rename tokens and binary rows explicitly

## Decision
Use a single subprocess per repo running `git log --no-merges -M50% --numstat -z` (with optional `.mailmap`), parse NUL-delimited chunks, skip binary rows, and insert via batched 10k-row SQLite transactions in WAL mode.

## Consequences
Rename detection cost is paid once at ingest; pure renames produce λ=0 rows that are harmless but kept for completeness. Binary files are invisible to metrics. Re-indexing replaces the whole repo rather than incrementally updating it.