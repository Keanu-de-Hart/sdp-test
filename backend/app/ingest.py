"""Repository ingestion: zip upload / clone URL acquisition and history indexing.

The whole history is indexed in a *single* streamed ``git log`` pass per
repository:

    git log --no-merges -M50% --numstat -z --format=<header> <ref>

This delegates diffing (including 50% rename detection and binary detection) to
git itself, and keeps memory usage flat: the NUL-delimited stream is parsed
incrementally into batched SQLite inserts.

Empirical output format (git >= 2.43, validated by ``tests/test_parser.py``):

  * commit header (one NUL-terminated token, fields joined by LF):
    sha / parents / aN / aE / an / ae / ct / subject
  * change entry:  ``<added>\\t<removed>\\t<path>\\x00``
  * binary entry:  ``-\\t-\\t<path>\\x00``                      (binary files are not measured -> skipped)
  * rename entry:  ``<added>\\t<removed>\\t\\x00<old>\\x00<new>\\x00``
  * a single LF may separate the header from the first entry.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator

from . import db
from .config import REPOS_DIR

GIT_BIN = shutil.which("git") or "git"

LOG_FORMAT = "%H%n%P%n%aN%n%aE%n%an%n%ae%n%ct%n%s"   # %P: full parent hashes
HEADER_RE = re.compile(rb"^[0-9a-f]{40}\n")
NUMSTAT_RE = re.compile(rb"^(\d+|-)\t(\d+|-)\t(.*)$", re.S)


class IngestError(Exception):
    """Raised for user-actionable ingestion failures."""


# --------------------------------------------------------------------------- #
# git plumbing helpers
# --------------------------------------------------------------------------- #

def _env() -> dict:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"          # never hang waiting for credentials
    env["LC_ALL"] = "C"
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    return env


def git(base: list[str], args: list[str], *, check: bool = True,
        capture: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(base + args, capture_output=capture, env=_env(), text=True)
    if check and proc.returncode != 0:
        raise IngestError((proc.stderr or proc.stdout or "").strip() or f"git {' '.join(args)} failed")
    return proc


def git_base(repo_path: Path) -> list[str]:
    """Return the git invocation prefix for a repository directory.

    Works for worktrees (``.git`` dir or file), bare repositories and plain
    ``.git`` directories extracted from a zip.
    """
    candidates: list[Path] = []
    if (repo_path / ".git").exists() or (repo_path / "HEAD").exists() or (repo_path / "objects").is_dir():
        candidates.append(repo_path)
    try:
        for child in sorted(repo_path.iterdir()):
            if child.is_dir():
                if (child / ".git").exists() or (child / "HEAD").exists() or (child / "objects").is_dir():
                    candidates.append(child)
    except OSError:
        pass
    for cand in candidates:
        base = [GIT_BIN, "-C", str(cand)]
        probe = git(base, ["rev-parse", "--git-dir"], check=False)
        if probe.returncode == 0:
            return base
    raise IngestError("No git repository found in the uploaded archive.")


# --------------------------------------------------------------------------- #
# acquisition: clone / unzip
# --------------------------------------------------------------------------- #

def clone_repo(url: str, dest: Path, progress_cb: Callable[[float, str], None] | None = None) -> None:
    """Full (deep) mirror clone. Progress is parsed from git's stderr."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [GIT_BIN, "clone", "--mirror", "--progress", url, str(dest)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=_env(), text=True,
        errors="replace",
    )
    pct_re = re.compile(r"(\d+)%")
    assert proc.stderr is not None
    for line in proc.stderr:                    # stream progress line by line
        line = line.strip()
        if not line or progress_cb is None:
            continue
        m = pct_re.search(line)
        if m:
            progress_cb(int(m.group(1)) / 100.0, line)
        elif "Cloning into" in line:
            progress_cb(0.0, line)
    proc.wait()
    if proc.returncode != 0:
        raise IngestError(f"Could not clone repository from {url}")


def safe_extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract an archive, refusing absolute paths and zip-slip traversal."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                raise IngestError(f"Refusing unsafe archive entry: {name}")
            target = (dest / name).resolve()
            if target != root and root not in target.parents:
                raise IngestError(f"Refusing unsafe archive entry: {name}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)


def extract_mailmap(base: list[str], ref: str) -> Path | None:
    """Materialise ``<ref>:.mailmap`` to a temp file, or return None.

    Passing the mailmap explicitly via ``-c mailmap.file=`` works for both
    bare mirrors and extracted worktrees.
    """
    probe = git(base, ["cat-file", "-e", f"{ref}:.mailmap"], check=False)
    if probe.returncode != 0:
        return None
    proc = subprocess.run(base + ["cat-file", "blob", f"{ref}:.mailmap"],
                          capture_output=True, env=_env())
    if proc.returncode != 0:
        return None
    fd, path = tempfile.mkstemp(prefix="rat-mailmap-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(proc.stdout)
    return Path(path)


# --------------------------------------------------------------------------- #
# streamed parser
# --------------------------------------------------------------------------- #

@dataclass
class FileChange:
    path: str
    added: int
    removed: int
    old_path: str | None = None


@dataclass
class CommitRecord:
    sha: str
    parents: str
    author_name: str
    author_email: str
    raw_author_name: str
    raw_author_email: str
    committer_ts: int
    subject: str
    files: list[FileChange] = field(default_factory=list)

    @property
    def parent_sha(self) -> str | None:
        parts = self.parents.split()
        return parts[0] if parts else None


def _nul_tokens(stream) -> Iterator[bytes]:
    """Yield NUL-delimited tokens from a binary stream without loading it fully."""
    buf = b""
    while True:
        chunk = stream.read(1 << 16)
        if not chunk:
            if buf:
                yield buf
            return
        buf += chunk
        parts = buf.split(b"\x00")
        buf = parts.pop()
        yield from parts


def parse_log_stream(stream) -> Iterator[CommitRecord]:
    """Parse the ``git log --numstat -z`` stream into CommitRecord objects."""
    cur: CommitRecord | None = None
    # rename state: after an ``added\tremoved\t`` (empty path) token we expect
    # the old path then the new path as two further tokens.
    rename_state: str | None = None
    rename_pending: tuple[int, int, bool] | None = None  # (added, removed, binary)
    rename_old: str = ""

    def decode(raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace")

    for raw in _nul_tokens(stream):
        if rename_state is not None:
            if rename_state == "old":
                rename_old = decode(raw)
                rename_state = "new"
            else:
                if rename_pending is not None and not rename_pending[2] and cur is not None:
                    cur.files.append(FileChange(
                        path=decode(raw), added=rename_pending[0],
                        removed=rename_pending[1], old_path=rename_old,
                    ))
                rename_state = None
                rename_pending = None
            continue

        tok = raw.lstrip(b"\n")             # one LF may separate header and first entry
        if not tok:
            continue

        if HEADER_RE.match(tok):
            if cur is not None:
                yield cur
            parts = tok.split(b"\n", 7)
            while len(parts) < 8:
                parts.append(b"")
            cur = CommitRecord(
                sha=decode(parts[0]),
                parents=decode(parts[1]),
                author_name=decode(parts[2]),
                author_email=decode(parts[3]),
                raw_author_name=decode(parts[4]),
                raw_author_email=decode(parts[5]),
                committer_ts=int(parts[6] or b"0"),
                subject=decode(parts[7]),
            )
            continue

        m = NUMSTAT_RE.match(tok)
        if m and cur is not None:
            added_raw, removed_raw, path_raw = m.groups()
            if not path_raw and added_raw != b"-":        # rename entry
                rename_state = "old"
                rename_pending = (int(added_raw), int(removed_raw), False)
            elif not path_raw and added_raw == b"-":      # binary rename entry
                rename_state = "old"
                rename_pending = (0, 0, True)
            elif added_raw == b"-":                       # binary file -> not measured
                continue
            else:
                cur.files.append(FileChange(
                    path=decode(path_raw), added=int(added_raw), removed=int(removed_raw),
                ))
            continue
        # anything else (defensive): ignore

    if cur is not None:
        yield cur


# --------------------------------------------------------------------------- #
# indexing orchestration
# --------------------------------------------------------------------------- #

def index_repo(repo_id: int, base: list[str], ref: str,
               progress_cb: Callable[[float, str], None] | None = None,
               should_abort: Callable[[], bool] | None = None) -> int:
    """Stream the history into SQLite. Returns the number of indexed commits."""
    total_proc = git(base, ["rev-list", "--count", "--no-merges", ref])
    total = int(total_proc.stdout.strip() or "0")

    mailmap = extract_mailmap(base, ref)
    cmd = list(base)
    if mailmap is not None:
        cmd = [GIT_BIN, *base[1:], "-c", f"mailmap.file={mailmap}"]
    cmd += ["log", "--no-merges", "-M50%", "--numstat", "-z",
            f"--format={LOG_FORMAT}", ref]

    conn = db.connect()
    parsed = 0
    if mailmap is not None:
        with conn:
            conn.execute("UPDATE repos SET have_mailmap = 1 WHERE id = ?", (repo_id,))
    commit_batch: list[tuple] = []
    change_batch: list[tuple] = []
    last_report = 0.0
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_env())
        assert proc.stdout is not None

        def flush():
            nonlocal commit_batch, change_batch
            if not commit_batch and not change_batch:
                return
            with conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO commits(repo_id, sha, parent_sha, author_name, author_email,"
                    " raw_author_name, raw_author_email, committer_ts, subject)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    [(repo_id, c.sha, c.parent_sha, c.author_name, c.author_email,
                      c.raw_author_name, c.raw_author_email, c.committer_ts, c.subject[:512])
                     for c in commit_batch],
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO file_changes(repo_id, sha, path, old_path, added, removed)"
                    " VALUES (?,?,?,?,?,?)",
                    [(repo_id, sha, fc.path, fc.old_path, fc.added, fc.removed)
                     for sha, fc in change_batch],
                )
            commit_batch = []
            change_batch = []

        for rec in parse_log_stream(proc.stdout):
            commit_batch.append(rec)
            for fc in rec.files:
                change_batch.append((rec.sha, fc))
            parsed += 1
            if len(change_batch) >= 10_000 or len(commit_batch) >= 5_000:
                flush()
                if should_abort is not None and should_abort():
                    proc.kill()
                    proc.wait()
                    raise IngestError("Ingestion cancelled.")
            now = time.monotonic()
            if progress_cb is not None and now - last_report > 0.3:
                progress_cb(parsed / total if total else 0.0, f"{parsed:,} / {total:,} commits")
                last_report = now
        flush()
        proc.wait()
        if proc.returncode != 0:
            err = (proc.stderr.read() or b"").decode(errors="replace").strip()
            raise IngestError(err or "git log failed while indexing the repository.")
        if progress_cb is not None:
            progress_cb(1.0, f"{parsed:,} / {total:,} commits")
        return parsed
    finally:
        conn.close()
        if mailmap is not None:
            mailmap.unlink(missing_ok=True)


def _repo_alive(conn, repo_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM repos WHERE id = ?", (repo_id,)).fetchone()
    return row is not None


def run_ingest(repo_id: int, kind: str, payload: str) -> None:
    """Background entry point: acquire the repository, then index it."""
    conn = db.connect()
    dest = REPOS_DIR / str(repo_id)
    tmp_zip: Path | None = None

    def set_status(status: str, progress: float | None = None,
                   detail: str | None = None, error: str | None = None) -> None:
        conn.execute(
            "UPDATE repos SET status = ?, progress = COALESCE(?, progress),"
            " progress_detail = ?, error = ? WHERE id = ?",
            (status, progress, detail, error, repo_id),
        )
        conn.commit()

    try:
        if kind == "zip":
            tmp_zip = Path(payload)
            set_status("extracting", 0.0, "Extracting archive…")
            src = dest / "src"
            if src.exists():
                shutil.rmtree(src)
            safe_extract_zip(tmp_zip, src)
            set_status("extracting", 1.0, "Locating git repository…")
            base = git_base(src)
        else:
            set_status("cloning", 0.0, "Cloning repository…")
            if dest.exists():
                shutil.rmtree(dest)
            clone_repo(payload, dest, progress_cb=lambda p, d: set_status("cloning", p, d))
            base = git_base(dest)

        repo = conn.execute("SELECT ref FROM repos WHERE id = ?", (repo_id,)).fetchone()
        if repo is None:
            return
        ref = repo["ref"] or "HEAD"

        head = git(base, ["rev-parse", ref], check=False)
        if head.returncode != 0:
            raise IngestError("Repository has no commits at the requested reference.")
        head_sha = head.stdout.strip()

        have_mailmap = git(base, ["cat-file", "-e", f"{ref}:.mailmap"], check=False).returncode == 0
        conn.execute("UPDATE repos SET path = ?, head_sha = ?, have_mailmap = ? WHERE id = ?",
                     (str(base[-1]), head_sha, 1 if have_mailmap else 0, repo_id))
        conn.commit()

        set_status("indexing", 0.0, "Indexing history…")
        count = index_repo(
            repo_id, base, ref,
            progress_cb=lambda p, d: _alive_and(set_status, conn, repo_id, "indexing", p, d),
            should_abort=lambda: not _repo_alive(conn, repo_id),
        )
        conn.execute("UPDATE repos SET status='ready', progress=1, progress_detail=?,"
                     " commit_count=?, error=NULL WHERE id = ?",
                     (f"{count:,} commits indexed", count, repo_id))
        conn.commit()
        conn.execute("ANALYZE")
        conn.commit()
        from .metrics import cache_invalidate      # late import avoids a cycle
        cache_invalidate(repo_id)
    except Exception as exc:                              # noqa: BLE001 - surfaced to the UI
        if _repo_alive(conn, repo_id):
            set_status("error", None, None, str(exc))
    finally:
        if tmp_zip is not None:
            tmp_zip.unlink(missing_ok=True)
        conn.close()


def _alive_and(set_status, conn, repo_id: int, status: str, progress: float, detail: str) -> None:
    if _repo_alive(conn, repo_id):
        set_status(status, progress, detail)


def start_ingest_thread(repo_id: int, kind: str, payload: str) -> None:
    threading.Thread(target=run_ingest, args=(repo_id, kind, payload), daemon=True).start()
