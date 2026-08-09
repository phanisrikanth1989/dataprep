# 18 - Orchestrator agent

Status: open
Type: task
Blocked by: 16, 17

## Question

Build the LLM orchestrator that fronts the run (ticket 05's second layer) on
16's chassis and 17's knowledge machinery: narration, composer answers,
propose-confirm, hold and stop proposals -- one voice, zero authority to act
silently.

Implements: ticket 05 (orchestrator layer, reword boundary, propose-confirm,
per-run memory and context rebuild), ticket 13 (composer-only interruption:
hold/stop/steer proposals), ticket 08 (command.ask with in_reply_to threaded
answers), ticket 06 (feed voice: only the orchestrator addresses the human),
ticket 11 (orchestrator knowledge slice; tier-3 authored-fresh prompt).

Scope:

- Persistent per-run conversation fed by 16's event feed (stage start,
  artifact written, verdict, question raised); tool reads on the bus so
  answers are grounded in this run's real artifacts; knowledge slice per
  11's matrix (patterns + envelope prose + landmine field-projection
  summaries) via 17's renderer.
- Non-blocking narration: the next stage starts immediately; orchestrator
  prose streams alongside as its own stream events, naturally sequential at
  pause points (~12 turns per run).
- Reword boundary enforced in prompt and composition: restyles prose only;
  options, ids, field names, code cells, data values and diff values render
  verbatim from the artifacts; the specialist's original wording survives in
  artifact + audit; the return path (answers, waives, approvals) never
  passes through the model.
- Propose-confirm: on 16's escalation events (specialist still malformed
  after bounded retries, unclassifiable failure) it explains what it sees
  and proposes the move as a question-channel event; it may always stop,
  never silently act; the conductor executes the confirmed move. It never
  sequences -- the conductor never asks it what runs next.
- Composer intent (13): free text mid-run becomes a hold or stop proposal
  through the same propose-confirm path; on confirm the conductor arms the
  hold at the next boundary. Steer text routes deterministically (16), not
  here.
- command.ask: answers stream with `in_reply_to` threading -- conversation,
  never a gate; nothing blocks, nothing times out.
- Crash-restart: behaves correctly on 16's rebuilt context from audit + bus.

Invariants: under `demo/etl_studio/`; no imports from `agents/`; prompt
authored fresh (11 tier 3), not ported.

Done when, on a scripted double run and once live on this Mac
(Mac-provisional), the feed shows orchestrator narration alongside real
stage progress; a composer question gets an artifact-grounded threaded
answer; a composer "hold this" produces a propose-confirm card whose
confirm arms 16's hold at the boundary; and a forced malformed-specialist
escalation surfaces as a propose-confirm question -- with specialist
content nowhere carrying a response affordance and all options/ids/values
verbatim.
