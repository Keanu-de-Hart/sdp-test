"""Throwaway: verify our metrics against the official reference CSVs.

Compares, per repo pinned at the reference SHA:
  * repository/ALL          -> summary view
  * repository/author rows  -> authors view (root)
  * file/ALL rows           -> files view (limit 20k)
  * directory/ALL rows      -> dirs view
  * file/author rows        -> authors view per file
  * directory/author rows   -> authors view per directory
Integers must match exactly; floats within 1e-9 relative tolerance.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import db, metrics  # noqa: E402
from app.metrics import Filter  # noqa: E402

BASE = Path("/home/vmuser/Downloads/repo-references")
CASES = [
    ("cJSON", BASE / "cJSON_6d9f2443ab07.csv",
     "6d9f2443ab071f86e5d9b43025a40929ec41c46c"),
    ("redis", BASE / "redis_b540ca49cba8.csv",
     "b540ca49cba815f3fbe634363c3df68d4f4f127a"),
    ("git", BASE / "git_5a7d1e8045ce.csv",
     "5a7d1e8045ce66c908f62598e26cbb8df7b39a90"),
]

EMAIL_RE = re.compile(r"<([^<>]+)>")
RTOL = 1e-9
MAX_PRINT = 25


def email_of(field: str) -> str | None:
    m = EMAIL_RE.search(field)
    return m.group(1).strip().lower() if m else None


class Section:
    def __init__(self, name: str) -> None:
        self.name = name
        self.checked = 0
        self.mism: list[tuple] = []
        self.missing: list[str] = []
        self.extra = 0
        self.maxdev = 0.0

    def row(self, ref: dict, ours: dict, key: str) -> None:
        for f in ("added", "removed", "growth", "churn", "modifications"):
            rv = ref.get(f, "")
            if rv == "":
                continue
            self.checked += 1
            if ours.get(f) != int(rv):
                self.mism.append((key, f, rv, ours.get(f)))
        for f in ("modification_frequency", "churn_rate", "ownership"):
            rv = ref.get(f, "")
            if rv == "":
                continue
            self.checked += 1
            want = float(rv)
            got = float(ours.get(f) or 0.0)
            rel = abs(want - got) / max(1.0, abs(want))
            self.maxdev = max(self.maxdev, rel)
            if rel > RTOL:
                self.mism.append((key, f, rv, ours.get(f)))

    def summary(self) -> str:
        status = "PASS" if not self.mism and not self.missing else "FAIL"
        return (f"  {self.name:22s} {status}  checks={self.checked}"
                f" mismatches={len(self.mism)} missing={len(self.missing)}"
                f" extra={self.extra} max_float_dev={self.maxdev:.2e}")


def load_csv(path: Path):
    repo_all = None
    repo_auth: dict[str, dict] = {}
    file_all: dict[str, dict] = {}
    file_auth: dict[str, dict[str, dict]] = {}
    dir_all: dict[str, dict] = {}
    dir_auth: dict[str, dict[str, dict]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ot, author, p = row["object_type"], row["author"], row["path"]
            if author == "ALL":
                if ot == "repository":
                    repo_all = row
                elif ot == "file":
                    file_all[p] = row
                elif ot == "directory":
                    dir_all[p] = row
                continue
            em = email_of(author)
            if em is None:
                continue
            if ot == "repository":
                repo_auth[em] = row
            elif ot == "file":
                file_auth.setdefault(p, {})[em] = row
            elif ot == "directory":
                dir_auth.setdefault(p, {})[em] = row
    return repo_all, repo_auth, file_all, file_auth, dir_all, dir_auth


def main() -> int:
    failures = 0
    for name, csv_path, sha in CASES:
        conn = db.connect()
        hit = conn.execute(
            "SELECT id, commit_count FROM repos WHERE head_sha = ?", (sha,)).fetchone()
        if hit is None:
            print(f"== {name}: NOT INGESTED at {sha[:12]} — skipping")
            failures += 1
            continue
        rid = int(hit["id"])
        repo_all, repo_auth, file_all, file_auth, dir_all, dir_auth = load_csv(csv_path)
        sections = {
            "repository ALL": Section("repository ALL"),
            "repository authors": Section("repository authors"),
            "files ALL": Section("files ALL"),
            "files authors": Section("files authors"),
            "dirs ALL": Section("dirs ALL"),
            "dirs authors": Section("dirs authors"),
        }

        s = sections["repository ALL"]
        summ = metrics.run_view(conn, rid, "summary", Filter())
        s.row(repo_all, summ, "repository /ALL")
        if summ["commit_count"] != int(repo_all["commit_count"]):
            s.mism.append(("repository /ALL", "commit_count",
                           repo_all["commit_count"], summ["commit_count"]))

        s = sections["repository authors"]
        items = metrics.run_view(conn, rid, "authors", Filter())["items"]
        ours = {it["author_key"][2:]: it for it in items}
        for em, ref_row in repo_auth.items():
            o = ours.get(em)
            if o is None:
                s.missing.append(f"repo author {em}")
            else:
                s.row(ref_row, o, f"author {em}")
        s.extra = len(set(ours) - set(repo_auth))

        s = sections["files ALL"]
        items = metrics.run_view(conn, rid, "files", Filter(limit=20000))["items"]
        ours_f = {it["path"]: it for it in items}
        for p, ref_row in file_all.items():
            o = ours_f.get(p)
            if o is None:
                s.missing.append(f"file {p}")
            else:
                s.row(ref_row, o, f"file {p}")
        s.extra = len(set(ours_f) - set(file_all))

        s = sections["dirs ALL"]
        items = metrics.run_view(conn, rid, "dirs", Filter())["items"]
        ours_d = {it["path"]: it for it in items if it["path"]}
        for p, ref_row in dir_all.items():
            o = ours_d.get(p)
            if o is None:
                s.missing.append(f"dir {p}")
            else:
                s.row(ref_row, o, f"dir {p}")
        s.extra = len(set(ours_d) - set(dir_all))

        for section_name, table, otype in (
            ("files authors", file_auth, "file"),
            ("dirs authors", dir_auth, "dir"),
        ):
            s = sections[section_name]
            for i, (p, authors) in enumerate(table.items(), 1):
                got = metrics.run_view(
                    conn, rid, "authors", Filter(path=p, object_type=otype))["items"]
                m = {it["author_key"][2:]: it for it in got}
                for em, ref_row in authors.items():
                    o = m.get(em)
                    if o is None:
                        s.missing.append(f"{otype} {p} :: {em}")
                    else:
                        s.row(ref_row, o, f"{p} :: {em}")
                s.extra += len(set(m) - set(authors))
                if i % 2000 == 0:
                    print(f"  …{name} {section_name} {i}/{len(table)}", flush=True)

        print(f"== {name} (repo id {rid}, indexed commits {hit['commit_count']},"
              f" reference commits {repo_all['commit_count']})")
        for sec in sections.values():
            print(sec.summary())
            for mm in sec.mism[:MAX_PRINT]:
                print("     MISMATCH", mm)
            for ms in sec.missing[:MAX_PRINT]:
                print("     MISSING ", ms)
        failures += sum(1 for sec in sections.values() if sec.mism or sec.missing)
        conn.close()

    print("RESULT:", "ALL MATCH" if failures == 0 else f"{failures} section(s) with issues")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
