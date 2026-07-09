import io
from fastapi.testclient import TestClient
from demo.budget_ui.server.app import app, store


def _client():
    store.__init__()  # reset in-memory state per test
    return TestClient(app)


def test_upload_returns_safe_job_id_and_queues_it():
    c = _client()
    r = c.post("/upload", files={"file": ("trade.docx", b"DOCXBYTES", "application/octet-stream")})
    assert r.status_code == 200
    job = r.json()["job"]
    assert job and "/" not in job and job not in (".", "..")   # safe work-dir slug
    # the fetcher can now pull it
    nxt = c.get("/job/next").json()
    assert nxt["job"] == job and nxt["filename"] == "trade.docx"
    # and download the exact bytes
    d = c.get(f"/job/{job}/doc")
    assert d.status_code == 200 and d.content == b"DOCXBYTES"
    # queue drains: a second /job/next has nothing
    assert c.get("/job/next").json()["job"] is None
