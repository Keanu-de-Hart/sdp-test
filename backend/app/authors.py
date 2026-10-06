"""Author identity handling: mailmap-resolved identities plus manual merging.

Raw identities are stored per commit at ingest time (both the mailmap-resolved
``%aN/%aE`` pair and the raw ``%an/%ae`` pair). Manual merges live in
``author_merges`` and are applied at query time, so merging never requires
re-indexing a repository.
"""
from __future__ import annotations

import sqlite3

# Effective author expression shared by every metrics query.
#   key:  'm:<group id>' for manually merged authors, 'i:<lowercased email>' otherwise
#   name: merged group name, falling back to the mailmap-resolved name
AUTHOR_JOIN = """
LEFT JOIN author_merges am
       ON am.repo_id = c.repo_id AND am.identity = lower(c.author_email)
LEFT JOIN merged_authors ma ON ma.id = am.merged_author_id
"""

AUTHOR_KEY_SQL = (
    "CASE WHEN ma.id IS NOT NULL THEN 'm:' || ma.id"
    " ELSE 'i:' || lower(c.author_email) END"
)
AUTHOR_NAME_SQL = "COALESCE(ma.name, c.author_name)"


def list_authors(conn: sqlite3.Connection, repo_id: int) -> dict:
    """Identities with commit counts plus the manual merge groups."""
    rows = conn.execute(f"""
        SELECT lower(c.author_email)  AS identity,
               c.author_email         AS email,
               MAX(c.author_name)     AS name,
               COUNT(*)               AS commits,
               am.merged_author_id    AS group_id,
               ma.name                AS group_name,
               GROUP_CONCAT(DISTINCT c.raw_author_name) AS raw_names
        FROM commits c
        {AUTHOR_JOIN}
        WHERE c.repo_id = ?
        GROUP BY lower(c.author_email)
        ORDER BY commits DESC, name COLLATE NOCASE
    """, (repo_id,)).fetchall()

    groups_rows = conn.execute(
        "SELECT id, name FROM merged_authors WHERE repo_id = ? ORDER BY name COLLATE NOCASE",
        (repo_id,),
    ).fetchall()
    members: dict[int, list[str]] = {g["id"]: [] for g in groups_rows}
    for r in rows:
        if r["group_id"] is not None and r["group_id"] in members:
            members[r["group_id"]].append(r["identity"])

    mailmap = conn.execute("SELECT have_mailmap FROM repos WHERE id = ?", (repo_id,)).fetchone()
    return {
        "have_mailmap": bool(mailmap["have_mailmap"]) if mailmap else False,
        "authors": [dict(r) for r in rows],
        "groups": [{"id": g["id"], "name": g["name"], "identities": members[g["id"]]}
                   for g in groups_rows],
    }


def merge_authors(conn: sqlite3.Connection, repo_id: int,
                  identities: list[str], name: str) -> None:
    """Merge raw identities (lowercased email addresses) into one author.

    If any selected identity already belongs to a merge group, all affected
    groups are unified into a single group carrying ``name``.
    """
    identities = sorted({i.strip().lower() for i in identities if i.strip()})
    if not identities:
        raise ValueError("No author identities supplied.")
    name = name.strip() or identities[0]
    marks = ",".join("?" for _ in identities)

    with conn:
        existing = conn.execute(
            f"SELECT DISTINCT merged_author_id FROM author_merges"
            f" WHERE repo_id = ? AND identity IN ({marks})",
            (repo_id, *identities),
        ).fetchall()
        group_ids = [r["merged_author_id"] for r in existing]

        if group_ids:
            target = group_ids[0]
            conn.execute("UPDATE merged_authors SET name = ? WHERE id = ?", (name, target))
            others = group_ids[1:]
            if others:
                omarks = ",".join("?" for _ in others)
                conn.execute(
                    f"UPDATE author_merges SET merged_author_id = ?"
                    f" WHERE repo_id = ? AND merged_author_id IN ({omarks})",
                    (target, repo_id, *others),
                )
        else:
            cur = conn.execute(
                "INSERT INTO merged_authors(repo_id, name) VALUES (?, ?)", (repo_id, name))
            target = cur.lastrowid

        conn.executemany(
            "INSERT OR REPLACE INTO author_merges(repo_id, identity, merged_author_id)"
            " VALUES (?, ?, ?)",
            [(repo_id, ident, target) for ident in identities],
        )
        # drop groups that lost all members during the unification
        conn.execute(
            "DELETE FROM merged_authors WHERE id NOT IN"
            " (SELECT merged_author_id FROM author_merges)",
        )


def unmerge_identity(conn: sqlite3.Connection, repo_id: int, identity: str) -> None:
    with conn:
        conn.execute(
            "DELETE FROM author_merges WHERE repo_id = ? AND identity = ?",
            (repo_id, identity.strip().lower()),
        )
        conn.execute(
            "DELETE FROM merged_authors WHERE id NOT IN"
            " (SELECT merged_author_id FROM author_merges)",
        )


def unmerge_group(conn: sqlite3.Connection, repo_id: int, group_id: int) -> None:
    with conn:
        conn.execute(
            "DELETE FROM author_merges WHERE repo_id = ? AND merged_author_id = ?",
            (repo_id, group_id),
        )
        conn.execute("DELETE FROM merged_authors WHERE id = ?", (group_id,))
