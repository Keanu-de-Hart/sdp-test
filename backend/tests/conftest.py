"""Shared test fixtures: a deterministic fixture repository with hand-computed metrics.

Fixture history (all timestamps are UNIX seconds, committer = author):

  T0      c1  Alice   add .mailmap (1 line, maps Alicia -> Alice), a.txt (3), src/x.py (2), bin.dat (binary)
  T0+1000 c2  Bob     edit a.txt (+2 -1), add src/sub/y.py (4)
  T0+2000 c3  Alicia  pure rename a.txt -> b.txt                      (0/0, no metric change)
  T0+3000 c4  Carol   rename+edit b.txt -> docs/b.txt (+2)            (changes attributed to new path)
  T0+4000 c5  Alice   delete docs/b.txt (-6)
  T0+5000 c6  Bob     edit src/x.py (+3 -2) and src/sub/y.py (+1)
  T0+5500 fm  Alice   (branch `feature`) edit src/sub/y.py (+1)
  T0+6000 c7  Carol   edit bin.dat (binary -> not measured)
  T0+7000 M   Alice   merge `feature` into main                      (merge commit -> excluded)
  T0+8000 c9  Dave    empty commit                                   (no changes)

  Indexed commit set H̄ = {c1..c7, fm, c9}: |H̄| = 9.

Expected aggregate values (whole repository, H̄):
  added=19 removed=9 growth=10 churn=28 modifications=6
  eta = 6/9   rho = 28/9
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

# The backend must use an isolated data directory: set before importing `app`.
_TMP_DATA = tempfile.mkdtemp(prefix="rat-test-data-")
os.environ["RAT_DATA_DIR"] = _TMP_DATA

import pytest  # noqa: E402

GIT = shutil.which("git")
T0 = 1_700_000_000
TS = {
    "c1": T0, "c2": T0 + 1000, "c3": T0 + 2000, "c4": T0 + 3000, "c5": T0 + 4000,
    "c6": T0 + 5000, "fm": T0 + 5500, "c7": T0 + 6000, "merge": T0 + 7000, "c9": T0 + 8000,
}
IDENT = {
    "alice": ("Alice", "alice@w.com"),
    "bob": ("Bob", "bob@w.com"),
    "alicia": ("Alicia", "alice2@w.com"),
    "carol": ("Carol", "carol@w.com"),
    "dave": ("Dave", "dave@w.com"),
}


def _env(who: str, ts: int) -> dict:
    name, email = IDENT[who]
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
        "GIT_AUTHOR_DATE": f"{ts} +0000", "GIT_COMMITTER_DATE": f"{ts} +0000",
    })
    return env


def git(repo: Path, args: list[str], who: str = "alice", ts: int = T0) -> str:
    proc = subprocess.run([GIT, "-C", str(repo), *args], env=_env(who, ts),
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout


def write(repo: Path, rel: str, data: str | bytes) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data)


def build_fixture_repo(root: Path) -> dict:
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, ["init", "-q", "-b", "main"])
    git(repo, ["config", "commit.gpgsign", "false"])
    git(repo, ["config", "core.autocrlf", "false"])
    shas: dict[str, str] = {}

    def commit(msg: str, who: str, key: str) -> None:
        git(repo, ["add", "-A"])
        git(repo, ["commit", "-qm", msg], who, TS[key])
        shas[key] = git(repo, ["rev-parse", "HEAD"]).strip()

    # c1
    write(repo, ".mailmap", "Alice <alice@w.com> Alicia <alice2@w.com>\n")
    write(repo, "a.txt", "L1\nL2\nL3\n")
    write(repo, "src/x.py", "x1\nx2\n")
    write(repo, "bin.dat", b"\x00\x01binary\x00")
    commit("c1 add core files", "alice", "c1")

    # c2
    write(repo, "a.txt", "L2\nL3\nN1\nN2\n")
    write(repo, "src/sub/y.py", "y1\ny2\ny3\ny4\n")
    commit("c2 edit a, add y", "bob", "c2")

    # c3: pure rename
    git(repo, ["mv", "a.txt", "b.txt"], "alicia", TS["c3"])
    commit("c3 rename only", "alicia", "c3")

    # c4: rename + edit in one commit
    (repo / "docs").mkdir(exist_ok=True)
    git(repo, ["mv", "b.txt", "docs/b.txt"], "carol", TS["c4"])
    write(repo, "docs/b.txt", "L2\nL3\nN1\nN2\nN3\nN4\n")
    commit("c4 rename and edit", "carol", "c4")

    # c5: delete
    git(repo, ["rm", "-q", "docs/b.txt"], "alice", TS["c5"])
    commit("c5 delete b", "alice", "c5")

    # c6: two files in src touched by a single commit (directory dedupe check)
    write(repo, "src/x.py", "x1b\nx2b\nx3b\n")
    write(repo, "src/sub/y.py", "y1\ny2\ny3\ny4\ny5\n")
    commit("c6 edits under src", "bob", "c6")

    # feature branch commit fm, then main-only c7, then a merge commit
    git(repo, ["checkout", "-q", "-b", "feature"], "alice", TS["fm"])
    write(repo, "src/sub/y.py", "y1\ny2\ny3\ny4\ny5\ny6\n")
    commit("fm feature edit", "alice", "fm")
    git(repo, ["checkout", "-q", "main"], "alice", TS["c7"])
    write(repo, "bin.dat", b"\x00\x02changed-bin\x00")
    commit("c7 binary edit", "carol", "c7")
    git(repo, ["merge", "--no-ff", "-q", "feature", "-m", "merge feature"], "alice", TS["merge"])
    shas["merge"] = git(repo, ["rev-parse", "HEAD"]).strip()

    # c9: empty commit
    git(repo, ["commit", "--allow-empty", "-qm", "c9 empty"], "dave", TS["c9"])
    shas["c9"] = git(repo, ["rev-parse", "HEAD"]).strip()

    return {"path": repo, "root": root, "shas": shas}


@pytest.fixture(scope="session")
def fixture_repo(tmp_path_factory) -> dict:
    return build_fixture_repo(tmp_path_factory.mktemp("fixture-root"))


@pytest.fixture(scope="session")
def fixture_zip(fixture_repo, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("fixture-zip")
    base = out / "repo"
    shutil.make_archive(str(base), "zip", root_dir=fixture_repo["root"])
    return Path(f"{base}.zip")


@pytest.fixture(scope="session")
def indexed(fixture_repo) -> dict:
    """Ingest the fixture repository into the isolated test database."""
    from app import db, ingest

    db.init_db()
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO repos(name, source_type, source, status, created_at)"
        " VALUES ('fixture', 'zip', 'fixture.zip', 'indexing', 0)")
    repo_id = int(cur.lastrowid)
    conn.commit()
    conn.close()

    base = ingest.git_base(Path(fixture_repo["path"]))
    count = ingest.index_repo(repo_id, base, "HEAD")

    conn = db.connect()
    conn.execute("UPDATE repos SET status='ready', commit_count=? WHERE id=?", (count, repo_id))
    conn.commit()
    conn.close()
    return {"repo_id": repo_id, "count": count, **fixture_repo}
