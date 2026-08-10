# 18 - Orchestrator agent

Status: resolved
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

## Answer

Built 2026-08-10 (commit 90d2bd9c). The LLM orchestrator is real on 16's
chassis with 17's knowledge machinery; `npm run smoke` grew 76 -> 84
checks, all green; seam tripwire green (28 core modules); the webview
needed zero changes (the wire vocabulary is untouched -- same `orch.*`
labels, same question kinds).

**Done criteria, with provenance:**

- Double-proven (smoke): narration is non-blocking (intake starts while
  the opening line still streams -- asserted by seq order); a composer
  question's answer grounds through a REAL `read_artifact` tool round on
  one stream (model tool_call + core-authored tool_result + threaded
  reply); "hold this" raises the propose-confirm card FROM the scripted
  model's `propose_control` call, confirm arms 16's hold at the next
  boundary (phases 5/7/8 unchanged in behavior); a post-restore ask is
  answered, not journal-skipped (new phase-6 beat); and phase 9 forces a
  permanently-malformed designer (rig `malformed_design` -> label
  `flow.design.bad`): three bounded attempts stream, the orchestrator
  explains, the card's voice IS its streamed text (asserted verbatim),
  options stay conductor-authored, and a confirmed stop ends the run
  plainly.
- Live-proven (Mac-provisional, rig-answered per the provenance rule):
  one BRD-door run on THIS Mac end-to-end to an approved end, every
  orchestrator stream `provider: vscode_lm`. The live model answered the
  composer question by CALLING `read_artifact("requirement_spec.json")`
  and stating G1's recorded disposition (threaded `in_reply_to`); on
  "hold this build" it CALLED `propose_control(hold)` -- card raised,
  rig confirmed, hold armed, the hold question rose at the verify
  boundary (the assemble boundary had already passed -- 13's arm-for-the-
  next-one rule observed live) and resumed; narration stayed content-real
  (the flow narration read flow.json itself: "9 components and 8 flows...
  keeping unmatched trades"). ~89k tokens for the full run. Caveat: the
  escalation beat was NOT forced live -- a live model cannot be made to
  emit malformed JSON deterministically; the escalation machinery is
  port-agnostic and double-proven, and the live run exercised the same
  propose-confirm surface through the hold path.

**Module map:**

- `core/orchestrator.py` (new): persistent per-run conversation + a
  serialized turn worker (one voice; narration enqueues and returns --
  the walk never waits on prose); tier-3 system prompt authored fresh
  (grounding, reword boundary, zero authority, composer rules) + 11's
  slices (patterns, envelope prose, landmine summaries) via 17's
  renderer; per-moment narration instructions; tools `read_artifact` /
  `list_artifacts` (bounded bus reads) on every turn, `propose_control`
  on composer turns only; live turns carry the real conversation,
  scripted turns play the same labels through the double.
- Conductor deltas: `narrate()` call sites replace the `_orch` fixture
  placeholders; `_escalate_failure` awaits the orchestrator's explanation
  and uses its text as the card voice (deterministic fallback covers a
  journal-skipped re-walk); `handle_propose_tool` raises the card as a
  side task (a model turn never blocks on the human); `intent_hint` is a
  LABEL hint only -- whether a card rises is the model's call in both
  paths; `compose_ask_reply` survives as the scripted-path echo stand-in;
  the verdict is now audited + fed (restore parity), and question
  raise/resolve lines feed the live context through a QuestionChannel
  callback (exact parity with the audit rebuild).
- Chassis: `LlmCall.journal_guarded` -- conversation turns are never
  skipped by the crash-restore stream ledger (a latent bug for asks
  before this ticket), and stream ids carry a per-process epoch so a
  restored core's ask streams cannot collide with journaled ids;
  `LIVE_SLOTS` += orchestrator; autorun rig gains `probe_asks`
  ({question_kind: composer_text}, fired once each) and confirms
  hold-proposals only (escalation stops stay dismissed).

**Decisions locked while building:**

- The propose-confirm card only ever rises from `propose_control` -- the
  keyword hint routes labels, never raises cards; a live model answering
  "hold on, what does R5 mean?" as a question (no tool call) is correct
  behavior, not a miss.
- Card options and resolution recording stay conductor-authored/machine-
  recorded end to end; the orchestrator contributes voice prose only.
- With an instant-answer rig the narration queue can drain past run end
  (the verdict narration landed after the approve); at HITL pace the
  human's gate dwell absorbs this. Cosmetic, on record for 20/21.

**Flagged forward:**

- To 20 (updates 17's flag): usage DataParts NOW ARRIVE on live streams
  on this Mac (20/20 turns) but in OpenAI token shape (prompt_tokens /
  completion_tokens / copilot_usage.token_details) with NO nano-AIU
  field, so `total_nano_aiu` stays unnormalized and the credit readout
  still shows nothing live -- the gap moved from "part absent" to
  "normalization decision", which is 20's to reconcile on the Citi
  gateway (06's rule stands: absent -> no number, never an estimate).
- To 20/21 (rehearsal prompt tuning): the live verdict narration read
  `matched: 4/4` as "graded 4 outputs" -- prose imprecision, not a value
  mutation; tighten the verdict instruction if it grates.
- Live `stream.close` on the vscode_lm adapter reports finish_reason
  "unknown" (within contract; the double says "stop").

## Comments

2026-08-10 -- HITL F5 pass (user-driven live BRD run, post gap-card fix):
all four done-when beats confirmed on pixels at human pace; provenance for
the composer beats upgrades from rig-answered to human-driven on this Mac.
One live-feel finding (stage-boundary pacing beat) recorded on ticket 21.
