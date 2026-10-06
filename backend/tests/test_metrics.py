"""Golden metric tests against the deterministic fixture repository.

All expected values are hand-computed in ``conftest.py``; see that docstring for
the full history and the derivation of the numbers.
"""
from __future__ import annotations

import pytest

from conftest import TS

from app import authors as authors_mod
from app import db, metrics


def view(rid: int, name: str, **kw) -> dict:
    if not kw.get("commits"):
        kw.pop("commits", None)
    with db.connect() as conn:
        return metrics.run_view(conn, rid, name, metrics.Filter(**kw))


def by_path(items: list[dict]) -> dict[str, dict]:
    return {i["path"]: i for i in items}


# --------------------------------------------------------------------------- #
# ingest-level checks
# --------------------------------------------------------------------------- #

def test_ingest_rows(indexed) -> None:
    rid = indexed["repo_id"]
    shas = indexed["shas"]
    assert indexed["count"] == 9                       # c1..c7, fm, c9 — merge excluded

    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM commits WHERE repo_id=?", (rid,)).fetchone()[0]
        assert n == 9
        # merge commit is excluded
        assert conn.execute("SELECT 1 FROM commits WHERE repo_id=? AND sha=?",
                            (rid, shas["merge"])).fetchone() is None

        # mailmap applied at ingest: Alicia's commit resolves to Alice
        row = conn.execute("SELECT author_name, author_email, raw_author_name FROM commits"
                           " WHERE repo_id=? AND sha=?", (rid, shas["c3"])).fetchone()
        assert (row["author_name"], row["author_email"]) == ("Alice", "alice@w.com")
        assert row["raw_author_name"] == "Alicia"

        # parent chain: c4's parent is c3
        parent = conn.execute("SELECT parent_sha FROM commits WHERE repo_id=? AND sha=?",
                              (rid, shas["c4"])).fetchone()["parent_sha"]
        assert parent == shas["c3"]

        # pure rename: single 0/0 row on the new path with old_path recorded
        rows = conn.execute("SELECT path, old_path, added, removed FROM file_changes"
                            " WHERE repo_id=? AND sha=?", (rid, shas["c3"])).fetchall()
        assert [(r["path"], r["old_path"], r["added"], r["removed"]) for r in rows] == \
            [("b.txt", "a.txt", 0, 0)]

        # rename+edit attributed to the new path
        rows = conn.execute("SELECT path, old_path, added, removed FROM file_changes"
                            " WHERE repo_id=? AND sha=?", (rid, shas["c4"])).fetchall()
        assert [(r["path"], r["old_path"], r["added"], r["removed"]) for r in rows] == \
            [("docs/b.txt", "b.txt", 2, 0)]

        # binary-only commit has no rows; binary path never appears
        assert conn.execute("SELECT COUNT(*) FROM file_changes WHERE repo_id=? AND sha=?",
                            (rid, shas["c7"])).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM file_changes WHERE repo_id=? AND path=?",
                            (rid, "bin.dat")).fetchone()[0] == 0

        # empty commit exists but has no rows
        assert conn.execute("SELECT COUNT(*) FROM file_changes WHERE repo_id=? AND sha=?",
                            (rid, shas["c9"])).fetchone()[0] == 0


# --------------------------------------------------------------------------- #
# repository / summary metrics
# --------------------------------------------------------------------------- #

def test_summary_root(indexed) -> None:
    rid = indexed["repo_id"]
    s = view(rid, "summary")
    assert s["added"] == 19
    assert s["removed"] == 9
    assert s["growth"] == 10
    assert s["churn"] == 28
    assert s["modifications"] == 6
    assert s["commit_count"] == 9
    assert s["modification_frequency"] == pytest.approx(6 / 9)
    assert s["churn_rate"] == pytest.approx(28 / 9)


def test_summary_file_and_dir(indexed) -> None:
    rid = indexed["repo_id"]
    s = view(rid, "summary", path="src/x.py", object_type="file")
    assert (s["added"], s["removed"], s["growth"], s["churn"], s["modifications"]) == (5, 2, 3, 7, 2)
    assert s["churn_rate"] == pytest.approx(7 / 9)

    s = view(rid, "summary", path="src", object_type="dir")
    assert (s["added"], s["removed"], s["growth"], s["churn"], s["modifications"]) == (11, 2, 9, 13, 4)
    assert s["modification_frequency"] == pytest.approx(4 / 9)


# --------------------------------------------------------------------------- #
# commit-set filtering
# --------------------------------------------------------------------------- #

def test_time_range_boundaries(indexed) -> None:
    rid = indexed["repo_id"]
    # H_i,j: i inclusive, j exclusive -> {c4} only
    s = view(rid, "summary", start=TS["c4"], end=TS["c5"])
    assert (s["added"], s["removed"], s["churn"], s["modifications"], s["commit_count"]) == (2, 0, 2, 1, 1)

    # {c4, c5}
    s = view(rid, "summary", start=TS["c4"], end=TS["c6"])
    assert (s["added"], s["removed"], s["growth"], s["churn"], s["modifications"],
            s["commit_count"]) == (2, 6, -4, 8, 2, 2)
    assert s["modification_frequency"] == pytest.approx(1.0)
    assert s["churn_rate"] == pytest.approx(4.0)

    # H_t (from t to present): everything from c6 onwards
    s = view(rid, "summary", start=TS["c6"])
    assert s["commit_count"] == 4                      # c6, fm, c7, c9
    assert s["added"] == 5 and s["removed"] == 2 and s["modifications"] == 2


def test_manual_commit_selection(indexed) -> None:
    rid = indexed["repo_id"]
    s = view(rid, "summary", commits=[indexed["shas"]["c2"]])
    assert (s["added"], s["removed"], s["growth"], s["churn"], s["modifications"],
            s["commit_count"]) == (6, 1, 5, 7, 1, 1)
    assert s["modification_frequency"] == pytest.approx(1.0)
    assert s["churn_rate"] == pytest.approx(7.0)


def test_empty_commit_set(indexed) -> None:
    rid = indexed["repo_id"]
    s = view(rid, "summary", start=TS["c9"] + 10)
    assert s["commit_count"] == 0
    assert s["churn"] == 0 and s["modifications"] == 0
    assert s["modification_frequency"] == 0.0 and s["churn_rate"] == 0.0
    a = view(rid, "authors", start=TS["c9"] + 10)
    assert a["items"] == [] and a["churn_total"] == 0


def test_author_filter(indexed) -> None:
    rid = indexed["repo_id"]
    s = view(rid, "summary", authors=["i:bob@w.com"])
    assert (s["added"], s["removed"], s["growth"], s["churn"], s["modifications"],
            s["commit_count"]) == (10, 3, 7, 13, 2, 2)
    assert s["modification_frequency"] == pytest.approx(1.0)
    assert s["churn_rate"] == pytest.approx(6.5)


# --------------------------------------------------------------------------- #
# files / dirs views
# --------------------------------------------------------------------------- #

def test_files_view(indexed) -> None:
    rid = indexed["repo_id"]
    data = view(rid, "files")
    files = by_path(data["items"])
    assert set(files) == {".mailmap", "a.txt", "b.txt", "docs/b.txt", "src/x.py", "src/sub/y.py"}

    def expect(path, added, removed, growth, churn, mods):
        f = files[path]
        assert (f["added"], f["removed"], f["growth"], f["churn"], f["modifications"]) == \
            (added, removed, growth, churn, mods), path

    expect(".mailmap", 1, 0, 1, 1, 1)
    expect("a.txt", 5, 1, 4, 6, 2)
    expect("b.txt", 0, 0, 0, 0, 0)          # pure rename alone: no metric change
    expect("docs/b.txt", 2, 6, -4, 8, 2)    # rename+edit attributed to the new path
    expect("src/x.py", 5, 2, 3, 7, 2)
    expect("src/sub/y.py", 6, 0, 6, 6, 3)
    # per-file frequency uses |H| = 9
    assert files["src/sub/y.py"]["modification_frequency"] == pytest.approx(3 / 9)


def test_dirs_view(indexed) -> None:
    rid = indexed["repo_id"]
    data = view(rid, "dirs")
    dirs = by_path(data["items"])
    assert set(dirs) == {"", "docs", "src", "src/sub"}

    root = dirs[""]
    assert (root["added"], root["removed"], root["churn"], root["modifications"]) == (19, 9, 28, 6)

    src = dirs["src"]
    # 4 distinct commits touch files under src (c1, c2, c6, fm) — c6 touches two
    # files in src but must count as ONE modification for the directory.
    assert (src["added"], src["removed"], src["churn"], src["modifications"]) == (11, 2, 13, 4)

    sub = dirs["src/sub"]
    assert (sub["added"], sub["churn"], sub["modifications"]) == (6, 6, 3)

    docs = dirs["docs"]
    assert (docs["added"], docs["removed"], docs["growth"], docs["churn"], docs["modifications"]) == \
        (2, 6, -4, 8, 2)

    scoped = view(rid, "dirs", path="src", object_type="dir")
    sdirs = by_path(scoped["items"])
    assert set(sdirs) == {"src", "src/sub"}
    assert sdirs["src"]["churn"] == 13


# --------------------------------------------------------------------------- #
# author metrics
# --------------------------------------------------------------------------- #

def test_authors_view_and_ownership(indexed) -> None:
    rid = indexed["repo_id"]
    data = view(rid, "authors")
    by_key = {i["author_key"]: i for i in data["items"]}

    # Alicia was merged into Alice by the repository's .mailmap at ingest time
    assert "i:alice2@w.com" not in by_key
    alice = by_key["i:alice@w.com"]
    assert (alice["churn"], alice["modifications"], alice["commits"]) == (13, 3, 4)

    bob = by_key["i:bob@w.com"]
    assert (bob["churn"], bob["modifications"], bob["commits"]) == (13, 2, 2)

    carol = by_key["i:carol@w.com"]
    assert (carol["churn"], carol["modifications"], carol["commits"]) == (2, 1, 1)

    # ownership = author churn / total churn
    assert alice["ownership"] == pytest.approx(13 / 28)
    assert sum(i["ownership"] for i in data["items"]) == pytest.approx(1.0)
    assert data["churn_total"] == 28
    # Dave's only commit is empty -> not shown in the author breakdown
    assert "i:dave@w.com" not in by_key


def test_manual_author_merging(indexed) -> None:
    rid = indexed["repo_id"]
    with db.connect() as conn:
        authors_mod.merge_authors(conn, rid, ["bob@w.com", "carol@w.com"], "Dev Team")
    metrics.cache_invalidate(rid)

    data = view(rid, "authors")
    by_key = {i["author_key"]: i for i in data["items"]}
    team = [i for k, i in by_key.items() if k.startswith("m:")]
    assert len(team) == 1
    assert team[0]["author"] == "Dev Team"
    assert team[0]["churn"] == 15
    assert team[0]["modifications"] == 3
    assert team[0]["ownership"] == pytest.approx(15 / 28)

    # the author filter accepts merged-author keys (bob: c2,c6 + carol: c4,c7)
    s = view(rid, "summary", authors=[team[0]["author_key"]])
    assert s["churn"] == 15 and s["commit_count"] == 4

    # unmerge one identity, then the whole group
    with db.connect() as conn:
        authors_mod.unmerge_identity(conn, rid, "bob@w.com")
    metrics.cache_invalidate(rid)
    data = view(rid, "authors")
    by_key = {i["author_key"]: i for i in data["items"]}
    assert by_key["i:bob@w.com"]["churn"] == 13
    team = [i for k, i in by_key.items() if k.startswith("m:")]
    assert len(team) == 1 and team[0]["churn"] == 2

    with db.connect() as conn:
        authors_mod.unmerge_group(conn, rid, int(team[0]["author_key"][2:]))
    metrics.cache_invalidate(rid)
    data = view(rid, "authors")
    assert all(not i["author_key"].startswith("m:") for i in data["items"])
    assert view(rid, "summary", commits=[indexed["shas"]["c9"]])["commit_count"] == 1


def test_authors_list_endpoint_helper(indexed) -> None:
    rid = indexed["repo_id"]
    with db.connect() as conn:
        data = authors_mod.list_authors(conn, rid)
    assert data["have_mailmap"] is True
    identities = {a["identity"]: a for a in data["authors"]}
    assert "alice2@w.com" not in identities
    assert identities["alice@w.com"]["commits"] == 4
    assert identities["dave@w.com"]["commits"] == 1
    assert data["groups"] == []


# --------------------------------------------------------------------------- #
# timeseries / commits views
# --------------------------------------------------------------------------- #

def test_timeseries(indexed) -> None:
    rid = indexed["repo_id"]
    data = view(rid, "timeseries", granularity="day")
    assert len(data["items"]) == 1                       # all commits on the same day
    pt = data["items"][0]
    assert (pt["added"], pt["removed"], pt["churn"], pt["modifications"]) == (19, 9, 28, 6)
    assert pt["bucket"] == "2023-11-14"                  # 1700000000 == 2023-11-14 UTC


def test_commits_view(indexed) -> None:
    rid = indexed["repo_id"]
    data = view(rid, "commits", limit=50)
    assert data["total"] == 9
    assert data["items"][0]["sha"] == indexed["shas"]["c9"]     # newest first
    assert data["items"][0]["subject"] == "c9 empty"
    assert data["items"][0]["churn"] == 0

    scoped = view(rid, "commits", path="src/x.py", object_type="file", only_changed=True)
    shas = {i["sha"] for i in scoped["items"]}
    assert shas == {indexed["shas"]["c1"], indexed["shas"]["c6"]}
    assert scoped["total"] == 2
