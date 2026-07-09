import asyncio
import io
import json
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


def test_stream_replays_log_and_closes_on_end():
    c = _client()
    job = c.post("/upload", files={"file": ("t.docx", b"x", "application/octet-stream")}).json()["job"]
    for ev in ({"type": "stage", "stage": "reading", "status": "done", "seq": 1},
               {"type": "sources", "nodes": [], "seq": 2},
               {"type": "end", "passed": True, "seq": 3}):
        assert c.post(f"/job/{job}/event", json=ev).json()["ok"] is True
    # a late-joining stream replays the whole log and stops at 'end'
    with c.stream("GET", f"/stream/{job}") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        payloads = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [p["type"] for p in payloads]
    assert types == ["stage", "sources", "end"]        # full replay, terminated by end


def test_add_event_fans_out_to_subscribers():
    from demo.budget_ui.server.app import JobStore
    async def _check():
        s = JobStore(); q = s.subscribe("j")
        await s.add_event("j", {"type": "rules", "seq": 1})
        return (await asyncio.wait_for(q.get(), 1))["type"]
    assert asyncio.run(_check()) == "rules"
