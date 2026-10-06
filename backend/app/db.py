"""SQLite storage layer: schema and connection helpers.

All metric data for every repository lives in one database; every table is keyed
by ``repo_id`` so that multi-repository support is a plain filter.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL,              -- 'zip' | 'clone'
    source          TEXT,                       -- original URL / zip filename
    path            TEXT NOT NULL DEFAULT '',   -- on-disk git repository root
    ref             TEXT NOT NULL DEFAULT 'HEAD',
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|cloning|extracting|indexing|ready|error
    progress        REAL NOT NULL DEFAULT 0,    -- 0..1 (best effort while cloning/indexing)
    progress_detail TEXT,
    error           TEXT,
    head_sha        TEXT,
    commit_count    INTEGER NOT NULL DEFAULT 0, -- |H̄|: non-merge commits reachable from ref
    have_mailmap    INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS commits (
    repo_id          INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    sha              TEXT NOT NULL,
    parent_sha       TEXT,                      -- first parent (h[p]); NULL for the initial commit
    author_name      TEXT NOT NULL,             -- mailmap-resolved author name   (%aN)
    author_email     TEXT NOT NULL,             -- mailmap-resolved author email  (%aE)
    raw_author_name  TEXT NOT NULL,             -- raw author name                (%an)
    raw_author_email TEXT NOT NULL,             -- raw author email               (%ae)
    committer_ts     INTEGER NOT NULL,          -- h[committer-date] as UNIX timestamp
    subject          TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (repo_id, sha)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_commits_ts    ON commits(repo_id, committer_ts);
CREATE INDEX IF NOT EXISTS idx_commits_email ON commits(repo_id, author_email);

CREATE TABLE IF NOT EXISTS file_changes (
    repo_id  INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    sha      TEXT NOT NULL,
    path     TEXT NOT NULL,                     -- object path; changes are attributed to the new path
    old_path TEXT,                              -- set when the change is a rename
    added    INTEGER NOT NULL,
    removed  INTEGER NOT NULL,
    PRIMARY KEY (repo_id, sha, path)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_fc_path ON file_changes(repo_id, path);

CREATE TABLE IF NOT EXISTS merged_authors (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    name    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS author_merges (
    repo_id          INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    identity         TEXT NOT NULL,             -- lowercased author email
    merged_author_id INTEGER NOT NULL REFERENCES merged_authors(id) ON DELETE CASCADE,
    PRIMARY KEY (repo_id, identity)
);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a tuned connection. One connection per request/thread is fine."""
    conn = sqlite3.connect(str(db_path or DB_PATH), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
