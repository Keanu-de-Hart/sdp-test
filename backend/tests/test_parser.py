"""Parser tests: lock the exact `git log --numstat -z` token format.

The byte stream below mirrors real git >= 2.43 output for a repository
containing: a normal add, a binary add, a pure rename, a rename+edit, a binary
rename, a filename with a space and unicode, a deletion, an empty commit, and
an initial (parentless) commit.
"""
from __future__ import annotations

from app.ingest import parse_log_stream

S0 = "e" * 40
S1 = "a" * 40
S2 = "b" * 40
S3 = "c" * 40
S4 = "d" * 40


def header(sha: str, parents: str, name: str, email: str, raw_name: str,
           raw_email: str, ct: int, subject: str) -> bytes:
    return f"{sha}\n{parents}\n{name}\n{email}\n{raw_name}\n{raw_email}\n{ct}\n{subject}".encode() + b"\x00"


STREAM = b"".join([
    header(S1, S0, "Alice", "alice@w.com", "Ali", "ali@x.com", 1_700_000_000, "first"),
    b"\n3\t0\ta.txt\x00",                                  # LF separator + normal entry
    b"-\t-\tbin.dat\x00",                                  # binary -> skipped
    b"0\t0\t\x00old.txt\x00new.txt\x00",                   # pure rename
    b"2\t1\t\x00weird\x00dir/new file.txt\x00",            # rename + edit, path with space
    b"-\t-\t\x00old-bin\0new-bin\x00",                     # binary rename -> skipped
    b"1\t0\tunicode/\xc3\xa9.txt\x00",                     # unicode path
    header(S2, S1, "Bob", "bob@w.com", "Bob", "bob@w.com", 1_700_001_000, "second"),
    b"\n0\t2\tgone.txt\x00",                               # deletion
    header(S3, S2, "Carol", "carol@w.com", "Carol", "carol@w.com", 1_700_002_000, "empty"),
    header(S4, "", "Dan", "dan@w.com", "Dan", "dan@w.com", 1_700_003_000, "seed"),
    b"\n5\t0\tseed.txt\x00",                               # initial commit (no parents)
])


def test_parse_stream() -> None:
    import io
    commits = list(parse_log_stream(io.BytesIO(STREAM)))
    assert len(commits) == 4

    c1, c2, c3, c4 = commits

    # commit header fields
    assert c1.sha == S1 and c1.parent_sha == S0
    assert (c1.author_name, c1.author_email) == ("Alice", "alice@w.com")
    assert (c1.raw_author_name, c1.raw_author_email) == ("Ali", "ali@x.com")
    assert c1.committer_ts == 1_700_000_000
    assert c1.subject == "first"

    # files: binary skipped, pure rename kept as 0/0 with old path,
    # rename+edit attributed to the new path, unicode decoded
    assert [(f.path, f.added, f.removed, f.old_path) for f in c1.files] == [
        ("a.txt", 3, 0, None),
        ("new.txt", 0, 0, "old.txt"),
        ("dir/new file.txt", 2, 1, "weird"),
        ("unicode/\u00e9.txt", 1, 0, None),
    ]

    # deletion
    assert [(f.path, f.added, f.removed) for f in c2.files] == [("gone.txt", 0, 2)]

    # empty commit: no file changes, still a record
    assert c3.sha == S3 and c3.files == []

    # initial commit: no parents
    assert c4.parent_sha is None
    assert [(f.path, f.added, f.removed) for f in c4.files] == [("seed.txt", 5, 0)]
