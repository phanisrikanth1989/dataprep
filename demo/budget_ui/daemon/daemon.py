# demo/budget_ui/daemon/daemon.py
"""Watch a job work dir by mtime; dispatch new/changed artifacts to presenter;
wrap payloads in an envelope; send them out (injected sender). ASCII-only.
Artifacts are dispatched in chronological (mtime) order so stages emit in
pipeline order. Stage transitions are keyed off WHICH artifact appeared
(deterministic), not off audit.jsonl event strings.
"""
from __future__ import annotations

import json
import os
import time
import logging

logger = logging.getLogger(__name__)

from . import presenter as P

# canonical pipeline order -- the tiebreak when two artifacts share an mtime tick
_ORDER = {"purity.json": 0, "exploder_inventory.json": 1, "extract_doc.json": 2,
          "requirement_spec.json": 3, "flow_plan.json": 4, "job_draft.json": 5,
          "job.json": 6, "test_report.json": 7}


# artifact filename -> the flat list of event payloads to emit on its appearance.
#
# Stage transitions are ANTICIPATORY: an artifact appearing means the stage that PRODUCED it
# is done and the NEXT agent is already working -- so each artifact lights the NEXT stage
# active. This keeps the UI in step with what the orchestrator is doing NOW instead of one
# step behind (the artifact is written at a step's END). And purity.json -- the very first
# artifact, written in seconds -- lights "reading" immediately so the screen is not blank
# for the ~90s the document read takes before extract_doc lands.
def _dispatch(name, doc):
    if name == "purity.json":
        return [P.ev_stage("reading", "active")]
    if name == "extract_doc.json":
        return [P.ev_stage("reading", "done"), P.ev_sources(doc), P.ev_stage("interpreting", "active")]
    if name == "requirement_spec.json":
        return [P.ev_rules(doc), P.ev_stage("interpreting", "done"), P.ev_stage("designing", "active")]
    if name == "flow_plan.json":
        # provisional node skeleton (flow_plan ids). The AUTHORITATIVE graph -- final ids +
        # business labels + edges -- comes from job.json below. The assembler can rename the
        # terminal FileOutput id (id == output name), so reconciling this skeleton to the final
        # id set is a frontend concern. designing DONE + configuring ACTIVE: the configurator
        # is now running (the skeleton just landed), so the UI shows it, not the past step.
        return [P.ev_nodes(doc), P.ev_stage("designing", "done"), P.ev_stage("configuring", "active")]
    if name == "job_draft.json":
        # callouts pop from a SINGLE source -> no duplicates. configuring DONE + wiring ACTIVE:
        # the assembler is now wiring the envelope.
        return [*P.ev_callouts(doc), P.ev_stage("configuring", "done"), P.ev_stage("wiring", "active")]
    if name == "job.json":
        # job.json is the single source of the AUTHORITATIVE graph: node_config (final ids +
        # business labels + lookup-name resolution -- which needs job.json's flows, absent from
        # job_draft) and edges are emitted here so they stay id-consistent with each other.
        # wiring DONE; if a code cell exists, signoff ACTIVE (the human is now approving it).
        evs = [P.ev_node_config(doc), P.ev_edges(doc), P.ev_stage("wiring", "done")]
        g = P.ev_gate(doc)
        if g:
            evs.append(g)                                  # gate awaiting (code sign-off)
            evs.append(P.ev_stage("signoff", "active"))
        return evs
    return []


class Daemon:
    def __init__(self, job_id, work_dir, send, since=None, synthetic=False):
        self.job_id = job_id
        self.work_dir = work_dir
        self.send = send
        self.since = since if since is not None else time.time()
        self._seen = {}      # filename -> mtime
        self._seq = 0
        self.tier = "build"  # captured from extract_doc.json when it appears (NOT from test_report)
        self._gate_node = None  # remembered from job.json so we can emit gate:signed at test_report
        self.synthetic = synthetic  # --synthetic: attach a finale sample (reads the answer key)
        self._sample = None  # captured from extract_doc.json in synthetic mode only

    def _emit(self, payload):
        if not payload:
            return
        self._seq += 1
        env = {"job": self.job_id, "seq": self._seq, "t": time.time()}
        env.update(payload)
        self.send(env)

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

    def poll(self):
        try:
            names = os.listdir(self.work_dir)
        except FileNotFoundError:
            return
        candidates = []
        for name in names:
            path = os.path.join(self.work_dir, name)
            if not (name.endswith(".json") and os.path.isfile(path)):
                continue
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            if mt < self.since or self._seen.get(name) == mt:
                continue
            candidates.append((mt, _ORDER.get(name, 99), name, path))
        # dispatch in chronological (mtime) order, pipeline-index as the tiebreak --
        # NOT filename order (which would put job.json before job_draft.json).
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
                events = self._events_for(name, doc)
            except Exception as exc:   # malformed-but-parseable artifact: log once, mark seen, move on
                logger.warning("[daemon] cannot process %s (skipping): %s", name, exc)
                self._seen[name] = mt  # mark seen so we do NOT retry a permanently-bad artifact
                continue
            try:
                for ev in events:
                    self._emit(ev)
            except Exception as exc:   # a SEND failure must NOT mark seen -> retry next poll
                logger.warning("[daemon] send failed for %s (will retry): %s", name, exc)
                continue
            self._seen[name] = mt      # marked seen only after ALL its events sent

    def run(self, interval=0.5):
        while True:
            try:
                self.poll()
            except Exception as exc:  # never let one bad pass kill the watch loop
                logger.warning("[daemon] poll error: %s", exc)
            time.sleep(interval)
