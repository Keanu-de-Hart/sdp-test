"""API tests: upload a zip of the fixture repo and drive the endpoints end to end."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _wait_ready(client: TestClient, repo_id: int, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        repo = client.get(f"/api/repos/{repo_id}").json()
        if repo["status"] == "ready":
            return repo
        if repo["status"] == "error":
            pytest.fail(f"ingestion failed: {repo['error']}")
        time.sleep(0.25)
    pytest.fail("timed out waiting for ingestion")


def test_upload_zip_and_metrics(client: TestClient, fixture_zip, indexed) -> None:
    with open(fixture_zip, "rb") as fh:
        resp = client.post("/api/repos/upload",
                           files={"file": (fixture_zip.name, fh, "application/zip")})
    assert resp.status_code == 200, resp.text
    repo = resp.json()
    assert repo["source_type"] == "zip"

    repo = _wait_ready(client, repo["id"])
    assert repo["commit_count"] == 9
    assert repo["have_mailmap"] == 1
    assert repo["head_sha"]

    rid = repo["id"]
    summary = client.post(f"/api/repos/{rid}/metrics/summary", json={}).json()
    assert (summary["added"], summary["removed"], summary["growth"], summary["churn"],
            summary["modifications"], summary["commit_count"]) == (19, 9, 10, 28, 6, 9)

    files = client.post(f"/api/repos/{rid}/metrics/files", json={"path": "src", "object_type": "dir"}).json()
    paths = {i["path"] for i in files["items"]}
    assert paths == {"src/x.py", "src/sub/y.py"}

    dirs = client.post(f"/api/repos/{rid}/metrics/dirs", json={}).json()
    dir_map = {i["path"]: i for i in dirs["items"]}
    assert dir_map["src"]["modifications"] == 4

    authors = client.get(f"/api/repos/{rid}/authors").json()
    assert authors["have_mailmap"] is True
    assert all(a["identity"] != "alice2@w.com" for a in authors["authors"])

    # manual author merge through the API
    merged = client.post(f"/api/repos/{rid}/author-merges",
                         json={"identities": ["bob@w.com", "carol@w.com"], "name": "Dev Team"})
    assert merged.status_code == 200, merged.text
    assert merged.json()["groups"][0]["name"] == "Dev Team"
    av = client.post(f"/api/repos/{rid}/metrics/authors", json={}).json()
    team = [i for i in av["items"] if i["author"] == "Dev Team"][0]
    assert team["churn"] == 15

    groups = merged.json()["groups"]
    client.delete(f"/api/repos/{rid}/author-groups/{groups[0]['id']}")
    av = client.post(f"/api/repos/{rid}/metrics/authors", json={}).json()
    assert all(i["author"] != "Dev Team" for i in av["items"])

    # commit picker and path picker
    commits = client.get(f"/api/repos/{rid}/commits", params={"q": "c2"}).json()
    assert commits["total"] >= 1
    assert any("c2" in c["subject"] for c in commits["items"])

    paths_resp = client.get(f"/api/repos/{rid}/paths", params={"q": "x.py"}).json()
    assert {"path": "src/x.py", "type": "file", "label": "src/x.py"} in paths_resp["items"]

    # timeseries + commits views
    ts = client.post(f"/api/repos/{rid}/metrics/timeseries", json={"granularity": "day"}).json()
    assert sum(p["churn"] for p in ts["items"]) == 28

    cview = client.post(f"/api/repos/{rid}/metrics/commits",
                        json={"limit": 5, "path": "src", "object_type": "dir"}).json()
    assert cview["total"] == 9
    assert len(cview["items"]) == 5

    # validation errors
    assert client.post(f"/api/repos/{rid}/metrics/nope", json={}).status_code == 404
    assert client.post("/api/repos/clone", json={"url": "not-a-url"}).status_code == 400

    # cleanup
    assert client.delete(f"/api/repos/{rid}").json() == {"ok": True}
    assert client.get(f"/api/repos/{rid}").status_code == 404


def test_repo_listing(client: TestClient, indexed) -> None:
    repos = client.get("/api/repos").json()
    assert any(r["id"] == indexed["repo_id"] and r["status"] == "ready" for r in repos)
