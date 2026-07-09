"""Thin Citi-internal relay: upload a BRD, fetch it to the laptop, ingest the
daemon's data-free events, and stream them to the browser via SSE. In-memory,
ephemeral, single process. ASCII-only. The server adds nothing to events and
reads no artifact -- it only relays."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, UploadFile, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles


def _safe_slug(name):
    """A filesystem-safe, STABLE job id from the filename stem -- NO random suffix. The same
    document always maps to the same job id + work dir, so the operator wires the daemon and
    Copilot to one fixed, predictable name (nothing to copy around mid-demo); re-uploading the
    same doc reuses its work dir. `trade_position_demo.docx` -> `trade_position_demo`."""
    stem = "".join(ch for ch in (name or "").rsplit(".", 1)[0]
                   if (ch.isascii() and ch.isalnum()) or ch in "-_").strip("-_")
    return (stem or "demo")[:32].lower()


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


@app.post("/job/{job}/event")
async def ingest(job: str, request: Request):
    event = await request.json()
    await store.add_event(job, event)
    return {"ok": True}


@app.get("/stream/{job}")
async def stream(job: str):
    async def gen():
        q = store.subscribe(job)                 # subscribe FIRST so no event is lost in the replay window
        seen = set()
        try:
            for ev in store.log(job):            # replay for late-join catch-up
                seen.add(ev.get("seq"))
                yield "data: " + json.dumps(ev) + "\n\n"
                if ev.get("type") == "end":
                    return
            while True:
                ev = await q.get()
                if ev.get("seq") in seen:        # already replayed in the race window -> skip
                    continue
                yield "data: " + json.dumps(ev) + "\n\n"
                if ev.get("type") == "end":
                    return
        finally:
            store.unsubscribe(job, q)
    return StreamingResponse(gen(), media_type="text/event-stream")


def mount_static():
    """Serve the built React dist/ at / when it exists (a no-op otherwise).

    Registered AFTER every API route, so Starlette matches /upload, /job/*, and
    /stream/* first; this catch-all mount only handles the rest (index.html and
    the Vite asset bundle). Exposed as a function so a test can (re)mount after
    creating a dist/ fixture. No-op when the frontend is unbuilt."""
    dist = Path(__file__).parent / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")


mount_static()
