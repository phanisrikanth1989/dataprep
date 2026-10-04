# 05 - Orchestrator: LLM-driven or deterministic?

Status: resolved
Type: grilling
Blocked by: 04

## Question

Is the pipeline driver an LLM agent or a deterministic state machine with LLM
calls only inside the specialists?

Recorded leaning from charting: LLM-driven (user). Stress-test it:

- What decisions does the driver actually make that need a model, given the
  topology from ticket 04?
- Cost and latency per run (credits are ample -- ~20k available, 100-500 per
  run acceptable -- so this is about reliability more than money).
- Failure modes: a wandering driver vs a rigid one when the human steers
  mid-run.
- What each choice does to replay/rehearsal determinism for the demo.

## Answer

Resolved 2026-08-09 via grilling (three rounds). The charted LLM-driven leaning
survived in revised form: the multi-agent orchestrator pattern stays, control
becomes deterministic. Terms in root `CONTEXT.md`; trade-off recorded as ADR
0001.

**The split.** The "driver" dissolves into two layers:

- **Conductor (code).** The deterministic control layer -- the hub. Computes
  every transition (04's fixed itinerary, loop counters, the diagnostician's
  owner-plus-forward rule, tier routing), enforces the 3-caps and gates,
  invokes specialists and the harness, moves artifacts on the bus, writes
  `audit.jsonl`, raises the seven question-channel event families, and records
  the human's resolutions untouched. It cannot improvise; after a crash it
  restores from bus + audit (03/04 made both file-based and append-only).
- **Orchestrator (LLM agent).** Fronts the run, persistent per run. Narrates
  transitions in its own words, answers the human's free-form questions
  grounded in the real artifacts (tool reads on the bus), gives outgoing prose
  a single voice, and catches runs that leave the map. It never sequences --
  the conductor never asks it what runs next.

**What settled it.** Decision inventory: given 02/04, every between-stage
decision is already deterministic (sequence = topology; loop exits = counters;
pauses = enumerated events; repair target = `feedback.json`'s owner; tier =
materializer; pass/fail = harness) -- no driver decision needs a model. And the
human CAN ask the studio questions mid-run (decided here) -- that hub job does
need a model. Both facts honored at once produce the split. Also settled: no
standing between-stage judge -- cross-stage smell detection is the harness +
diagnostician's job; the orchestrator reads artifacts to talk about them,
never to gate them.

**Authority: propose-confirm.** On anything unplanned (specialist output still
malformed after its bounded retries, an unclassifiable harness failure), the
conductor hands the orchestrator the context. The orchestrator may always STOP
and raise a question-channel event -- explain what it sees, propose the move --
and never acts silently; the human confirms, the conductor executes. Free to
pull the cord, never to grab the wheel. Bounded autonomy (choosing among legal
moves unasked, within caps) is a later policy loosening on this same
structure, not a rebuild.

**Narration: non-blocking.** The next stage starts immediately; orchestrator
prose streams alongside, naturally sequential at pause points. ~12 narration
turns + Q&A per run sits well inside the 100-500 credit window; wall-clock
pays no model-turn tax between stages.

**Orchestrator memory.** Persistent per-run conversation: the conductor feeds
it every event (stage start, artifact written, verdict, question raised); it
reads artifacts on demand via tools; on crash-restart the conductor rebuilds
its context from `audit.jsonl` + the bus. Its narration and answers are the
"orchestrator thoughts" stream that 06/08 build on.

**Reword boundary.** One voice out, zero mutation through: the orchestrator
may restyle prose (question wording, gate summaries, narration); it never
touches options, field names, identifiers, code cells, data values or diff
values -- those render verbatim from the artifacts (today's code-cell rule,
generalized); the specialist's original wording survives in artifact + audit;
the return path (answers, waives, approvals) is recorded by the conductor with
no model in between.

**Exhaustion-steer defined.** The `steer` option on a budget-exhaustion event
= the human's free text routed as a directed spec revision: an
`owner: interpreter` iteration with the text as its feedback, re-sign-off if
the spec changed, forward stages re-run. Scoped to this event; general
pause/steer stays in the fog.

**Rationale recorded.** The leaning protected pattern recognition -- the
team/audience knows the multi-agent orchestrator pattern. The resolution keeps
it visibly intact (six specialists, hub-and-spoke, one orchestrator, sole
human channel) as the workflow-hub variant of the same pattern. Also on
record: in the owned runtime an LLM hub is not the cheap option (Copilot's
agent runtime does not come along; both hubs are builds), and today's
orchestrator prompt is mostly itinerary + anti-deviation armor whose jobs
02/04 already moved into code stages and specialists -- its own "Note on
tightening" concedes the deterministic swap is one edit.

**Demo determinism.** A run's path cannot differ between rehearsal and live --
only prose is sampled, and prose never changes the path; provider-port
record/replay covers the rest.

**Hub-and-spoke confirmed.** Specialists never invoke each other: the
diagnostician writes `feedback.json` and stops; the conductor re-invokes the
owner, then every forward stage.

**For ticket 06:** the thoughts stream = specialist streams + orchestrator
narration/answers; no separate narrator model exists.
**For ticket 08:** conductor emits the machine-truth events (04's seven
families plus the propose-confirm escalation); orchestrator prose rides its
own channel alongside.

Boundaries held: 06 owns what streams and how it's framed; 08 owns message
shapes; pause/steer beyond exhaustion-steer stays fog.
