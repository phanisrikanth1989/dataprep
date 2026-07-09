# demo/budget_ui/daemon/daemon.py
"""Watch a job work dir by mtime; dispatch new/changed artifacts to presenter;
wrap payloads in an envelope; send them out (injected sender). ASCII-only.
Stage transitions are keyed off WHICH artifact appeared (deterministic), not
off audit.jsonl event strings. gate:signed is keyed off test_report appearing.
"""
from __future__ import annotations

import json
import os
import time

from . import presenter as P

# artifact filename -> (stage-on-appearance, [extractor callables])
def _dispatch(name, doc):
    if name == "extract_doc.json":
        return [P.ev_stage("reading", "done"), P.ev_sources(doc), P.ev_stage("interpreting", "active")]
    if name == "requirement_spec.json":
        return [P.ev_rules(doc), P.ev_stage("designing", "active")]
    if name == "flow_plan.json":
        return [P.ev_nodes(doc), P.ev_stage("designing", "done")]
    if name == "job_draft.json":
        # callouts pop here (the configuring stage) from a SINGLE source -> no duplicates
        return [P.ev_node_config(doc), *P.ev_callouts(doc), P.ev_stage("configuring", "active")]
    if name == "job.json":
        evs = [P.ev_edges(doc), P.ev_stage("wiring", "active")]
        g = P.ev_gate(doc)
        if g:
            evs.append(g)
        return evs
    return []


class Daemon:
    def __init__(self, job_id, work_dir, send, since=None):
        self.job_id = job_id
        self.work_dir = work_dir
        self.send = send
        self.since = since if since is not None else time.time()
        self._seen = {}      # filename -> mtime
        self._seq = 0
        self.tier = "build"  # captured from extract_doc.json when it appears (NOT from test_report)

    def _emit(self, payload):
        if not payload:
            return
        self._seq += 1
        env = {"job": self.job_id, "seq": self._seq, "t": time.time()}
        env.update(payload)
        self.send(env)

    def poll(self):
        try:
            names = os.listdir(self.work_dir)
        except FileNotFoundError:
            return
        for name in sorted(names):
            path = os.path.join(self.work_dir, name)
            if not (name.endswith(".json") and os.path.isfile(path)):
                continue
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            if mt < self.since or self._seen.get(name) == mt:
                continue
            self._seen[name] = mt
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (ValueError, OSError):
                continue   # torn/half-written read: skip this pass, retry next
            if name == "extract_doc.json":
                self.tier = doc.get("tier", self.tier)   # tier lives here, NOT in test_report.json
            if name == "test_report.json":
                self._emit(P.ev_result(doc, tier=self.tier))
                self._emit(P.ev_stage("done" if doc.get("passed") else "testing", "done"))
                continue
            for ev in _dispatch(name, doc):
                self._emit(ev)

    def run(self, interval=0.5):
        while True:
            self.poll()
            time.sleep(interval)
