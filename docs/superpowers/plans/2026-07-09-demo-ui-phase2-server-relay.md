# Demo UI Phase 2 -- FastAPI Relay + Fetcher + Daemon Sender

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The thin Citi-server relay that carries the Phase-1 daemon's data-free event stream to a browser via SSE, plus the laptop-side HTTP sender + fetcher that connect the daemon to it.

**Architecture:** One FastAPI app (`server/app.py`) holds ephemeral in-memory per-job state (event log + SSE subscriber queues + the uploaded doc). The browser uploads a BRD (`/upload` -> job id), the laptop fetcher pulls the doc (`/job/next` + `/job/<id>/doc`), the daemon POSTs events up (`/job/<id>/event`), and the browser reads them via SSE (`/stream/<id>`, with log-replay for late join and close on the terminal `end` event). The daemon's `send` becomes a stdlib-urllib HTTP POST; two deferred contract items land here (mark-seen-after-send, `--synthetic` finale sample).

**Tech Stack:** Python 3.12+. Server: FastAPI + Starlette `StreamingResponse` (SSE), tested with `fastapi.testclient.TestClient`. Daemon sender + fetcher: stdlib `urllib` (laptop-outbound, zero deps). `pytest`.

**Depends on:** Phase 1 (`demo/budget_ui/daemon/{presenter,daemon}.py`) is built + committed. This phase consumes the event schema in `docs/superpowers/specs/2026-07-09-demo-ui-design.md` section 8 (as hardened by the contract review).

## Global Constraints

- Python 3.12+; ASCII-only (RHEL); no emojis/unicode.
- **Data-free:** the server relays events verbatim; it adds nothing and reads no artifact. The daemon is the only value-stripper. The `--synthetic` sample (finale table) is emitted ONLY in synthetic mode and ONLY for the known fixture (fail-closed).
- **Laptop-outbound only:** the daemon + fetcher call OUT to the server; the server never calls the laptop.
- **Event envelope + types:** `{job, seq, t, type, ...}`; types per section 8, terminal `end` closes the stream.
- **Guardrail (section 16.1):** the job id the server mints IS the work-dir slug the operator pastes into Copilot; it must be a safe single filename component.

---

## File Structure

- Create `demo/budget_ui/server/__init__.py`, `demo/budget_ui/server/app.py` -- the FastAPI relay + in-memory `JobStore`.
- Create `demo/budget_ui/daemon/sender.py` -- `HttpSender` (stdlib urllib POST), the daemon's real `send`.
- Create `demo/budget_ui/daemon/fetcher.py` -- poll `/job/next`, download the doc.
- Modify `demo/budget_ui/daemon/daemon.py` -- mark-seen-after-send; `--synthetic` sample plumbing.
- Modify `demo/budget_ui/daemon/presenter.py` -- a `sample_from_extract(extract_doc)` helper (synthetic-only).
- Tests: `tests/demo_budget_ui/test_server.py`, `test_sender.py`, `test_fetcher.py`, `test_daemon_synthetic.py`.

---

### Task 1: `JobStore` + upload/queue/doc endpoints

**Files:** Create `demo/budget_ui/server/__init__.py` (empty), `demo/budget_ui/server/app.py`. Test: `tests/demo_budget_ui/test_server.py`.

**Interfaces:**
- Produces: `app` (FastAPI); `store` (`JobStore`). `JobStore.create_job(filename, data) -> job_id` (safe slug); `next_job() -> job_id|None`; `doc(job) -> (filename, bytes)|None`; `add_event(job, event)` (async); `log(job) -> list`; `subscribe(job) -> asyncio.Queue`; `unsubscribe(job, q)`.
- Endpoints here: `POST /upload` (multipart `file`) -> `{job}`; `GET /job/next` -> `{job, filename}` or `{job: null}`; `GET /job/{job}/doc` -> the bytes.

- [ ] **Step 1: Failing test**
```python
# tests/demo_budget_ui/test_server.py
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
```

- [ ] **Step 2: Run -> FAIL** (`python -m pytest tests/demo_budget_ui/test_server.py -v`; ModuleNotFound).

- [ ] **Step 3: Implement**
```python
# demo/budget_ui/server/app.py
"""Thin Citi-internal relay: upload a BRD, fetch it to the laptop, ingest the
daemon's data-free events, and stream them to the browser via SSE. In-memory,
ephemeral, single process. ASCII-only. The server adds nothing to events and
reads no artifact -- it only relays."""
from __future__ import annotations

import asyncio
import json
import secrets

from fastapi import FastAPI, UploadFile, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse


def _safe_slug(name):
    """A filesystem-safe job id == the work-dir slug the operator pastes into Copilot."""
    stem = "".join(ch for ch in (name or "").rsplit(".", 1)[0]
                   if (ch.isascii() and ch.isalnum()) or ch in "-_").strip("-_")
    stem = (stem or "demo")[:24].lower()
    return "%s-%s" % (stem, secrets.token_hex(3))


class JobStore:
    def __init__(self):
        self._events = {}   # job -> list[event]
        self._subs = {}     # job -> set[asyncio.Queue]
        self._docs = {}     # job -> (filename, bytes)
        self._queue = []    # unfetched job ids

    def create_job(self, filename, data):
        job = _safe_slug(filename)
        self._docs[job] = (filename, data)
        self._events[job] = []
        self._subs[job] = set()
        self._queue.append(job)
        return job

    def next_job(self):
        return self._queue.pop(0) if self._queue else None

    def doc(self, job):
        return self._docs.get(job)

    async def add_event(self, job, event):
        self._events.setdefault(job, []).append(event)
        for q in list(self._subs.get(job, ())):
            await q.put(event)

    def log(self, job):
        return list(self._events.get(job, []))

    def subscribe(self, job):
        q = asyncio.Queue()
        self._subs.setdefault(job, set()).add(q)
        return q

    def unsubscribe(self, job, q):
        self._subs.get(job, set()).discard(q)


store = JobStore()
app = FastAPI()


@app.post("/upload")
async def upload(file: UploadFile):
    data = await file.read()
    return {"job": store.create_job(file.filename, data)}


@app.get("/job/next")
def job_next():
    job = store.next_job()
    if not job:
        return JSONResponse({"job": None})
    filename, _ = store.doc(job)
    return {"job": job, "filename": filename}


@app.get("/job/{job}/doc")
def job_doc(job: str):
    d = store.doc(job)
    if not d:
        raise HTTPException(status_code=404)
    filename, data = d
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename})
```

- [ ] **Step 4: Run -> PASS.**
- [ ] **Step 5: Commit** `git add demo/budget_ui/server/ tests/demo_budget_ui/test_server.py && git commit -m "feat(demo-ui): relay server upload/queue/doc endpoints + JobStore"`

---

### Task 2: `/job/{job}/event` ingest + `/stream/{job}` SSE (replay + end-close)

**Files:** Modify `demo/budget_ui/server/app.py`. Test: `tests/demo_budget_ui/test_server.py`.

**Interfaces:**
- Consumes: `store` from Task 1.
- Produces endpoints: `POST /job/{job}/event` (JSON body = one event) -> `{ok: true}`; `GET /stream/{job}` -> `text/event-stream`, replays `store.log(job)` then streams live, and the generator RETURNS after yielding a `type=="end"` event.

- [ ] **Step 1: Failing test** (post events incl. a terminal `end`, then read the SSE replay to completion)
```python
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
```
(Add `import json` at the top of the test file if not already present.)

- [ ] **Step 2: Run -> FAIL.**

- [ ] **Step 3: Implement (append to app.py)**
```python
@app.post("/job/{job}/event")
async def ingest(job: str, request: Request):
    event = await request.json()
    await store.add_event(job, event)
    return {"ok": True}


@app.get("/stream/{job}")
async def stream(job: str):
    async def gen():
        for ev in store.log(job):                       # replay for late-join catch-up
            yield "data: " + json.dumps(ev) + "\n\n"
            if ev.get("type") == "end":
                return
        q = store.subscribe(job)
        try:
            while True:
                ev = await q.get()
                yield "data: " + json.dumps(ev) + "\n\n"
                if ev.get("type") == "end":
                    return
        finally:
            store.unsubscribe(job, q)
    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: Run -> PASS.**
- [ ] **Step 5: Add a sync unit test for live fan-out** (env-independent -- wraps `asyncio.run`, no plugin, no config):
```python
import asyncio
def test_add_event_fans_out_to_subscribers():
    from demo.budget_ui.server.app import JobStore
    async def _check():
        s = JobStore(); q = s.subscribe("j")
        await s.add_event("j", {"type": "rules", "seq": 1})
        return (await asyncio.wait_for(q.get(), 1))["type"]
    assert asyncio.run(_check()) == "rules"
```
Run: `python -m pytest tests/demo_budget_ui/test_server.py -v`.
- [ ] **Step 6: Commit** `git add -u && git commit -m "feat(demo-ui): relay event ingest + SSE stream (replay + end-close)"`

---

### Task 3: Daemon `HttpSender` + `fetcher.py`

**Files:** Create `demo/budget_ui/daemon/sender.py`, `demo/budget_ui/daemon/fetcher.py`. Test: `tests/demo_budget_ui/test_sender.py`, `test_fetcher.py`.

**Interfaces:**
- Produces: `HttpSender(base_url, job_id)` callable `__call__(event: dict) -> None` (POST `base_url/job/<job_id>/event`, json body, stdlib urllib; raises on non-2xx). `fetch_once(base_url, out_dir) -> job_id|None` (GET `/job/next`; if a job, GET `/job/<id>/doc`, write to `out_dir/<filename>`, return job id).

- [ ] **Step 1: Failing tests** (run a real server in a uvicorn thread so urllib hits it end-to-end)
```python
# tests/demo_budget_ui/test_sender.py
import threading, time, urllib.request, json, socket, contextlib
import uvicorn
from demo.budget_ui.server.app import app, store
from demo.budget_ui.daemon.sender import HttpSender

def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

@contextlib.contextmanager
def _server():
    store.__init__()
    port = _free_port()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(cfg)
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/job/next", timeout=0.2); break
        except Exception:
            time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.should_exit = True; t.join(timeout=2)

def test_http_sender_posts_events():
    with _server() as base:
        send = HttpSender(base, "job-x")
        send({"type": "sources", "seq": 1, "nodes": []})
        send({"type": "end", "passed": True, "seq": 2})
        # verify via the stream replay
        req = urllib.request.urlopen(f"{base}/stream/job-x", timeout=2)
        data = req.read().decode()
    assert '"type": "sources"' in data and '"type": "end"' in data
```
```python
# tests/demo_budget_ui/test_fetcher.py
import urllib.request, pathlib
from demo.budget_ui.server.app import app  # noqa
from demo.budget_ui.daemon.fetcher import fetch_once
# reuse the _server helper pattern from test_sender (import it)
from tests.demo_budget_ui.test_sender import _server, store

def test_fetch_once_downloads_the_uploaded_doc(tmp_path):
    with _server() as base:
        import io
        urllib.request.urlopen  # ensure import
        # upload via urllib multipart is awkward; use the store directly to enqueue
        job = store.create_job("brd.docx", b"HELLO")
        got = fetch_once(base, str(tmp_path))
    assert got == job
    assert (tmp_path / "brd.docx").read_bytes() == b"HELLO"
```

- [ ] **Step 2: Run -> FAIL.**

- [ ] **Step 3: Implement**
```python
# demo/budget_ui/daemon/sender.py
"""Laptop-outbound HTTP sender: POST one data-free event to the relay. stdlib only."""
from __future__ import annotations

import json
import urllib.request


class HttpSender:
    def __init__(self, base_url, job_id):
        self._url = base_url.rstrip("/") + "/job/" + job_id + "/event"

    def __call__(self, event):
        body = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(self._url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:  # raises on non-2xx
            resp.read()
```
```python
# demo/budget_ui/daemon/fetcher.py
"""Laptop-outbound fetcher: pull the next queued BRD from the relay to the input dir. stdlib only."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


def fetch_once(base_url, out_dir):
    base = base_url.rstrip("/")
    with urllib.request.urlopen(base + "/job/next", timeout=5) as resp:
        info = json.loads(resp.read())
    job = info.get("job")
    if not job:
        return None
    with urllib.request.urlopen(base + "/job/" + job + "/doc", timeout=30) as resp:
        data = resp.read()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / Path(info["filename"]).name).write_bytes(data)   # basename only -- no path traversal
    return job
```

- [ ] **Step 4: Run -> PASS** (`python -m pytest tests/demo_budget_ui/test_sender.py tests/demo_budget_ui/test_fetcher.py -v`).
- [ ] **Step 5: Commit** `git add demo/budget_ui/daemon/sender.py demo/budget_ui/daemon/fetcher.py tests/demo_budget_ui/test_sender.py tests/demo_budget_ui/test_fetcher.py && git commit -m "feat(demo-ui): daemon HttpSender + fetcher (stdlib, laptop-outbound)"`

---

### Task 4: Daemon relay-robustness -- mark-seen-after-send + `--synthetic` finale sample

**Files:** Modify `demo/budget_ui/daemon/daemon.py`, `demo/budget_ui/daemon/presenter.py`. Test: `tests/demo_budget_ui/test_daemon_synthetic.py`.

**Interfaces:**
- Produces: `presenter.sample_from_extract(extract_doc, limit=5) -> list[dict]|None` (the expected_output rows as a small table; SYNTHETIC-ONLY caller). `Daemon(..., synthetic=False)` -- when `synthetic=True` AND `extract_doc.json` has been seen, the `result` event carries a `sample`. Mark-seen-after-send: an artifact is added to `_seen` only after ALL its events send without raising (so a send failure retries next poll).

- [ ] **Step 1: Failing test**
```python
# tests/demo_budget_ui/test_daemon_synthetic.py
import shutil, time, pathlib
from demo.budget_ui.daemon.daemon import Daemon
FIX = pathlib.Path(__file__).parent / "fixtures" / "trade_position_demo"

def test_synthetic_mode_emits_finale_sample(tmp_path):
    work = tmp_path / "j"; work.mkdir()
    cap = []
    d = Daemon("j", str(work), send=cap.append, since=time.time() - 1, synthetic=True)
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json"); d.poll()
    shutil.copy(FIX / "test_report.json", work / "test_report.json"); d.poll()
    res = next(e for e in cap if e["type"] == "result")
    assert "sample" in res and len(res["sample"]) >= 1     # finale table has rows in synthetic mode

def test_default_mode_has_no_sample(tmp_path):
    work = tmp_path / "j2"; work.mkdir()
    cap = []
    d = Daemon("j2", str(work), send=cap.append, since=time.time() - 1)   # synthetic defaults False
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json"); d.poll()
    shutil.copy(FIX / "test_report.json", work / "test_report.json"); d.poll()
    res = next(e for e in cap if e["type"] == "result")
    assert "sample" not in res                              # fail-closed

def test_mark_seen_after_send_retries_on_failure(tmp_path):
    work = tmp_path / "j3"; work.mkdir()
    calls = {"n": 0}
    def flaky(ev):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("server down")
    d = Daemon("j3", str(work), send=flaky, since=time.time() - 1)
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    d.poll()                     # first send raises -> artifact NOT marked seen
    ok = []
    d.send = ok.append
    d.poll()                     # retried on the next poll
    assert any(e["type"] == "sources" for e in ok)

def test_test_report_marked_seen_no_double_emit(tmp_path):
    # regression: test_report.json must be marked seen too, or run() re-emits result/end every poll
    work = tmp_path / "j4"; work.mkdir()
    cap = []
    d = Daemon("j4", str(work), send=cap.append, since=time.time() - 1)
    shutil.copy(FIX / "test_report.json", work / "test_report.json")
    d.poll()
    d.poll()                     # unchanged file -> must NOT re-emit
    assert sum(1 for e in cap if e["type"] == "result") == 1
```

- [ ] **Step 2: Run -> FAIL.**

- [ ] **Step 3: Implement.** In `presenter.py` add:
```python
def sample_from_extract(extract_doc, limit=5):
    """SYNTHETIC-ONLY: the expected_output rows as a small finale table. The caller
    (daemon) invokes this ONLY in --synthetic mode; it deliberately reads answer-key
    values, which is acceptable only because the demo doc is synthetic."""
    exp = extract_doc.get("expected_output") or {}
    for _name, rows in exp.items():
        return [dict(r) for r in rows[:limit]]
    return None
```
In `daemon.py`, `Daemon.__init__` gains `synthetic=False`: add `self.synthetic = synthetic` and `self._sample = None`. Extract the artifact->events logic into a `_events_for` method (so BOTH the test_report path and the _dispatch path return a flat list and mark-seen covers both -- no double-emit). Replace the per-artifact loop body (from `try: with open...` to the end of the loop) with:

```python
        for mt, _idx, name, path in sorted(candidates):
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (ValueError, OSError):
                continue   # torn read: skip, do NOT mark seen -> retry next pass
            if name == "extract_doc.json":
                self.tier = doc.get("tier", self.tier)
                if self.synthetic:
                    self._sample = P.sample_from_extract(doc)  # SYNTHETIC-ONLY: reads the answer key
            try:
                for ev in self._events_for(name, doc):
                    self._emit(ev)
            except Exception as exc:   # a send failure must NOT mark the artifact seen -> retry next poll
                logger.warning("[daemon] send failed for %s (will retry): %s", name, exc)
                continue
            self._seen[name] = mt      # marked seen only after ALL its events sent (covers BOTH paths)
```

Add the `_events_for` method:
```python
    def _events_for(self, name, doc):
        if name == "job.json":
            _g = P.ev_gate(doc)
            self._gate_node = _g["node"] if _g else None
        if name == "test_report.json":
            evs = []
            if self._gate_node:                      # the test ran -> the human signed off
                evs.append({"type": "gate", "kind": "code_signoff",
                            "node": self._gate_node, "status": "signed"})
            evs.append(P.ev_stage("testing", "active"))
            evs.append(P.ev_result(doc, tier=self.tier, sample=self._sample))
            evs.append(P.ev_stage("done" if doc.get("passed") else "testing", "done"))
            if doc.get("passed"):
                evs.append({"type": "end", "passed": True})
            return evs
        return _dispatch(name, doc)
```

Delete the now-obsolete inline `if name == "extract_doc.json"`/`if name == "test_report.json"` handling that used to live in `poll()` (the tier/sample capture stays in `poll()` as shown; the rest moved into `_events_for`). Keep the torn-read skip and the mtime ordering.

- [ ] **Step 4: Run -> PASS** (`python -m pytest tests/demo_budget_ui/ -v` -- the whole demo suite green).
- [ ] **Step 5: Commit** `git add -u && git commit -m "feat(demo-ui): daemon --synthetic finale sample + mark-seen-after-send"`

---

## Self-Review
- **Spec coverage:** section 9 endpoints -> Tasks 1-2; laptop-outbound sender/fetcher (section 4/5) -> Task 3; the Phase-2 deferrals from the contract review (finale sample, mark-seen-after-send) -> Task 4. `seq`-on-restart is a documented deferral to the live-hardening pass (not built here; note in the final review).
- **Placeholder scan:** none -- every step has runnable code.
- **Type consistency:** `HttpSender.__call__(event)` matches `Daemon.send`; `fetch_once` return type matches Task-3 tests; `sample_from_extract` return matches `ev_result(sample=...)`.

## Execution Handoff
Subagent-Driven. Two review units: **Unit A = server (Tasks 1-2)**; **Unit B = sender + fetcher + daemon robustness (Tasks 3-4)**. Then a final whole-branch review of the Phase-2 diff.
