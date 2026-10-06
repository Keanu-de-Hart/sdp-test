#!/usr/bin/env python3
"""Verify Repo Analysis Tool metrics for a repository.

Two modes:

  1. Against a running server (no local indexing):
       python scripts/verify_metrics.py --api http://localhost:8000 \
           --clone https://github.com/DaveGamble/cJSON.git --name cJSON
       # or reuse an existing repository:
       python scripts/verify_metrics.py --api http://localhost:8000 --repo cJSON

  2. Purely local (isolated data dir, ingests in-process):
       python scripts/verify_metrics.py --repo https://github.com/DaveGamble/cJSON.git \
           --data-dir /tmp/rat-verify

Optional expected values (subset match, exact integers, floats with tolerance):

  python scripts/verify_metrics.py --api http://localhost:8000 --repo cJSON \
      --expected scripts/expected_example.json

Expected file format::

  {
    "summary": {"added": 18990, "removed": 7123, "commit_count": 730},
    "files":   {"cJSON.c": {"churn": 12345}},
    "dirs":    {"tests": {"modifications": 320}},
    "authors": {"Lewis Baker": {"churn": 4000}}
  }

Exit code 0 when every check passes (or no expectations were supplied).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

METRIC_KEYS = (
    "added", "removed", "growth", "churn", "modifications",
    "modification_frequency", "churn_rate",
)


# --------------------------------------------------------------------------- #
# HTTP helpers (server mode)
# --------------------------------------------------------------------------- #

def http_json(url: str, payload: dict | None = None) -> dict:
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode()
        method = "POST"
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as res:
        return json.loads(res.read().decode())


def api_wait_ready(api: str, repo_id: int) -> dict:
    last = ""
    while True:
        repo = http_json(f"{api}/api/repos/{repo_id}")
        status = repo["status"]
        line = f"  {status:<10} {repo['progress'] * 100:5.1f}%  {repo.get('progress_detail') or ''}"
        if line != last:
            print(line, flush=True)
            last = line
        if status == "ready":
            return repo
        if status == "error":
            raise SystemExit(f"Ingestion failed: {repo.get('error')}")
        time.sleep(2)


def server_mode(args: argparse.Namespace) -> tuple[dict, dict]:
    api = args.api.rstrip("/")
    repo: dict | None = None

    if args.repo:
        repos = http_json(f"{api}/api/repos")
        repo = next((r for r in repos
                     if str(r["id"]) == str(args.repo) or r["name"] == args.repo), None)
        if repo is None:
            raise SystemExit(f"No repository matching '{args.repo}' on {api}.")
    elif args.clone:
        print(f"Creating clone job for {args.clone} …", flush=True)
        repo = http_json(f"{api}/api/repos/clone", {"url": args.clone, "name": args.name})

    assert repo is not None
    print(f"Repository #{repo['id']} '{repo['name']}' — status: {repo['status']}", flush=True)
    if repo["status"] not in ("ready", "error"):
        repo = api_wait_ready(api, repo["id"])

    results: dict = {}
    for view in ("summary", "files", "dirs", "authors"):
        body = {"limit": 5000} if view in ("files", "dirs", "authors") else {}
        results[view] = http_json(f"{api}/api/repos/{repo['id']}/metrics/{view}", body)
    return repo, results


# --------------------------------------------------------------------------- #
# local mode (in-process indexing into an isolated data dir)
# --------------------------------------------------------------------------- #

def local_mode(args: argparse.Namespace) -> tuple[dict, dict]:
    os.environ["RAT_DATA_DIR"] = str(Path(args.data_dir).resolve())
    sys.path.insert(0, str(BACKEND))
    from app import db, ingest, metrics  # noqa: E402  (import after env is set)

    db.init_db()
    source = args.repo or args.clone
    name = (args.name or "").strip()
    if not name:  # same derivation as the clone API
        tail = str(source).rstrip("/").split("/")[-1]
        name = tail[:-4] if tail.endswith(".git") else tail

    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO repos(name, source_type, source, status, created_at)"
            " VALUES (?,?,?,?,?)",
            (name, "clone", str(source), "pending", int(time.time())),
        )
        repo_id = int(cur.lastrowid)
        conn.commit()

    print(f"Repository #{repo_id} '{name}' — indexing {source} locally…", flush=True)
    ingest.run_ingest(repo_id, "clone", str(source))

    conn = db.connect()
    try:
        repo = dict(conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,)).fetchone())
        if repo["status"] != "ready":
            raise SystemExit(f"Ingestion failed: {repo.get('error')}")
        print(f"  ready — {repo['commit_count']:,} commits indexed", flush=True)

        results: dict = {}
        for view in ("summary", "files", "dirs", "authors"):
            results[view] = metrics.run_view(conn, repo_id, view, metrics.Filter(limit=5000))
    finally:
        conn.close()
    return repo, results


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #

def print_report(repo: dict, results: dict, top: int) -> None:
    s = results["summary"]
    print()
    print(f"== {repo['name']} ==")
    print(f"   head {repo.get('head_sha') or '?'} · {repo.get('commit_count', 0):,} non-merge commits"
          f" · .mailmap: {'yes' if repo.get('have_mailmap') else 'no'}")
    print()
    print("summary @ repository root   (H = all indexed non-merge commits)")
    print(f"   added={s['added']:,}  removed={s['removed']:,}  growth={s['growth']:+,}"
          f"  churn={s['churn']:,}  modifications={s['modifications']:,}")
    print(f"   eta (modification frequency) = {s['modification_frequency']:.4f}"
          f"   rho (churn rate) = {s['churn_rate']:.4f}   |H| = {s['commit_count']:,}")

    print()
    print(f"top files by churn (of {len(results['files']['items'])} shown)")
    print(f"   {'churn':>9} {'+added':>9} {'-removed':>9} {'mods':>7}  path")
    for row in results["files"]["items"][:top]:
        print(f"   {row['churn']:>9,} {row['added']:>9,} {row['removed']:>9,}"
              f" {row['modifications']:>7,}  {row['path']}")

    print()
    print(f"directories by churn (of {len(results['dirs']['items'])} shown)")
    dirs = sorted(results["dirs"]["items"], key=lambda r: -r["churn"])
    for row in dirs[:top]:
        name = row["path"] or "/ (root)"
        print(f"   {row['churn']:>9,} churn  {row['modifications']:>7,} mods"
              f"  growth {row['growth']:+,}  /{name if row['path'] else ''}")

    print()
    print("authors (churn → ownership)")
    for row in results["authors"]["items"][:top]:
        print(f"   {row['churn']:>9,} churn  {row['commits']:>5,} commits"
              f"  {row['modifications']:>5,} mods  ω={row['ownership'] * 100:6.2f}%"
              f"  {row['author']}")
    print()


def compare_expected(expected_path: str, results: dict) -> bool:
    expected = json.loads(Path(expected_path).read_text())
    checks = 0
    failures = 0
    print(f"== expected-value checks ({expected_path}) ==")
    for view, spec in expected.items():
        if view.startswith("_") or not isinstance(spec, dict):
            continue  # annotation keys (e.g. "_comment")
        result = results.get(view)
        if result is None:
            print(f"  FAIL {view}: unknown view")
            failures += 1
            continue
        if view == "summary":
            for metric, want in spec.items():
                got = result.get(metric)
                checks += 1
                ok = _close(got, want)
                print(f"  {'PASS' if ok else 'FAIL'} summary.{metric} = {got!r} (expected {want!r})")
                failures += 0 if ok else 1
            continue
        key = "path" if view in ("files", "dirs") else "author"
        for row_key, metrics_want in spec.items():
            match = next((r for r in result["items"] if r.get(key) == row_key), None)
            if match is None:
                checks += 1
                failures += 1
                print(f"  FAIL {view}['{row_key}']: row not found")
                continue
            for metric, want in metrics_want.items():
                got = match.get(metric)
                checks += 1
                ok = _close(got, want)
                label = f"{view}['{row_key}'].{metric}"
                print(f"  {'PASS' if ok else 'FAIL'} {label} = {got!r} (expected {want!r})")
                failures += 0 if ok else 1
    print(f"  {checks - failures}/{checks} checks passed")
    return failures == 0


def _close(got, want) -> bool:
    if got is None:
        return False
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        if isinstance(want, int) and float(want).is_integer():
            return int(got) == int(want)
        return abs(float(got) - float(want)) <= max(1e-9, abs(float(want)) * 1e-9)
    return got == want


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", help="base URL of a running RAT server, e.g. http://localhost:8000")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--repo", help="repository name/id (server mode) or git URL/path (local mode)")
    src.add_argument("--clone", help="git URL to clone and index (server mode)")
    ap.add_argument("--name", help="display name for a newly created repository")
    ap.add_argument("--data-dir", default="/tmp/rat-verify", help="isolated data dir (local mode)")
    ap.add_argument("--top", type=int, default=10, help="rows shown per view")
    ap.add_argument("--expected", help="JSON file with expected metric values (subset match)")
    ap.add_argument("--json", dest="json_out", help="write the raw results to this file")
    args = ap.parse_args()

    if not args.repo and not args.clone:
        ap.error("provide --repo (name/id/url/path) or --clone (url)")
    if args.api and not args.repo and not args.clone:
        ap.error("server mode needs --repo or --clone")

    if args.api:
        if args.clone is None and args.repo and args.repo.startswith(("http", "git@", "ssh://")):
            args.clone, args.repo = args.repo, None
        repo, results = server_mode(args)
    else:
        if args.repo and args.repo.startswith(("http", "git@", "ssh://")):
            args.clone, args.repo = args.repo, None
        repo, results = local_mode(args)

    print_report(repo, results, args.top)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2))
        print(f"raw results written to {args.json_out}")

    if args.expected:
        if not compare_expected(args.expected, results):
            raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
