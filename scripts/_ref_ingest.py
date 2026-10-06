"""Throwaway: ingest redis + git pinned at the official reference SHAs.

Creates the repos rows with ref=<pinned SHA> and runs the product ingestion
pipeline (mirror clone + streamed index) exactly as the API would.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import db  # noqa: E402
from app.ingest import run_ingest  # noqa: E402

PINS = [
    ("redis", "https://github.com/redis/redis.git",
     "b540ca49cba815f3fbe634363c3df68d4f4f127a"),
    ("git", "https://github.com/git/git.git",
     "5a7d1e8045ce66c908f62598e26cbb8df7b39a90"),
]

for name, url, sha in PINS:
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO repos(name, source_type, source, ref, status, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (name, "clone", url, sha, "pending", int(time.time())),
    )
    rid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    t0 = time.time()
    print(f"[{name}] id={rid} ingesting at {sha[:12]} ...", flush=True)
    run_ingest(rid, "clone", url)
    row = db.connect().execute(
        "SELECT status, commit_count, head_sha, error FROM repos WHERE id = ?",
        (rid,)).fetchone()
    print(f"[{name}] id={rid} finished in {time.time() - t0:.1f}s"
          f" status={row['status']} commits={row['commit_count']}"
          f" head={str(row['head_sha'])[:12]} error={row['error']}", flush=True)

print("ALL DONE", flush=True)
