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
