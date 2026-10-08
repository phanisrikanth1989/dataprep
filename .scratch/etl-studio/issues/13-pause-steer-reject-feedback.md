# 13 - Pause/steer and reject-with-feedback semantics

Status: resolved
Type: grilling
Blocked by: 02, 04, 05, 08

## Question

What do pause/steer and reject-with-feedback actually DO -- the interaction
semantics ticket 08 deliberately left open after fixing their message shape
(`{question_id, choice, free_text?}`)?

To settle:

- Can the human pause or redirect a run outside the enumerated pause points at
  all in v1? (04 shipped autonomous-only; 05's propose-confirm and
  exhaustion-steer are the only steering that exists today.)
- Reject-with-feedback per gate kind: spec sign-off reject re-enters
  elicitation (02, provisional) -- flesh out that loop; what does reject mean
  at the code gate and at the human gate (a directed spec revision, a
  repair-loop entry, or a stop)?
- Does `steer` generalize beyond budget exhaustion, or stay scoped as 05
  deliberately left it?
- Prior art: the retired single-step/testing mode (one stage per turn, no
  auto-repair) -- does anything of it return?

## Answer

Resolved 2026-08-09 via grilling (two rounds; all recommendations accepted).
Terms in root `CONTEXT.md` (Hold, Steer, Request changes, Directed
iteration). UI lands on ticket 12's v2 system via ticket 15 (scope amended
there).

**The primitive: directed iteration.** One mechanism under every human-driven
revision: one owner stage re-runs reading the human's feedback first, then
every forward stage — the repair-iteration shape with the human standing in
for the diagnostician. Two doors, fixed by the surface that raised it (the
conductor never routes by reading text): owner interpreter = the spec door
(draft N+1, re-sign-off if the spec changed, per 04's mid-loop rule); owner
configurator = the code door (code-gate rejects only).

**Interrupting a running stretch: composer-only.** No pause button, no
`command.hold`. The human types intent into the composer; the orchestrator
(05 already licenses it to stop and raise) proposes the hold as a
propose-confirm card; on confirm the conductor arms a hold at the next stage
boundary. Boundary semantics always: the in-flight stage finishes and its
artifact lands whole — no mid-stream cancel exists in v1. If the boundary
passes before confirm, the hold arms for the next one; the armed window is a
feed chip. A deterministic Hold pill stays a purely additive later option if
rehearsal shows propose-confirm latency hurts — the conductor verb is the
same either way.

**Hold = a question.** At the boundary the conductor raises a ninth question
kind (`kind: hold`): "Holding after <stage>", options Resume / Stop, free
text = steer. A held run IS a pending question — replay, attach,
nothing-times-out, and the spine's hold grammar all come free from 08. No
`run.held` event, no new lifecycle.

**Steer has one meaning.** Steer text — hold card, exhaustion card, and the
Request-changes text at the spec and human gates — always becomes an
interpreter-owned directed iteration (05's exhaustion-steer, generalized).
The one exception is the code gate, whose Request changes routes to the
configurator, the cell's author: implementation feedback, not spec feedback.
Room sentence: steer is the spec door; rejecting a cell is the config door.

**Reject-with-feedback per gate.**

- Spec sign-off: Request changes = interpreter directed iteration; new gaps
  (if the revision surfaces any) arrive as one normal round — 02's
  "re-enters elicitation" honored minimally. Draft numbering is the visible
  grammar. Rejects burn no elicitation budget.
- Code gate: per-cell reject = configurator directed iteration; forward
  stages re-run; the gate re-raises new/changed cells only (04's re-pause
  rule verbatim). "This shouldn't be code at all" is spec-shaped and goes
  through the steer door instead.
- Human gate: on a green verdict output ≡ golden, so rejecting the output is
  rejecting the oracle — spec-level by construction. Options: Approve /
  Request changes (spec door; forward re-run; return to the gate) / Stop.
  On a red verdict Approve disappears — Revise/Stop only ("a green harness
  is necessary, not sufficient" is load-bearing). A smoke-clean run is
  approvable; the tier chip prices what that's worth.

**Stop ends the run, plainly.** Journal marks stopped-by-you, feed says it
calmly, canvas freezes as-is; the next run starts fresh. Exhaustion's "stop
to the gate" keeps its specific meaning — there a red verdict exists to
dispose of. Composer stop-intent works anywhere via the same propose-confirm
path. The "every run ends through the human gate" invariant was considered
and rejected (empty-gate state; a conditional invariant is not an invariant).

**Caps are for the machine, not the human.** Every human-initiated act —
gate rejects, holds, steers, grants — is uncapped and burns no loop budget;
the 3-caps bound autonomous iteration only (04's grant logic generalized).
No new counters.

**Single-step mode: fully retired.** Nothing returns. The hold verb is its
only descendant; a step toggle would be a later policy over the same verb.

**Contract impact: zero new families.** Rejects, steers, stops and grants
are resolutions on existing question kinds — 08's shapes unchanged; hold is
one new `kind` on the shared lifecycle (growth 08 explicitly allows). No new
events, no new commands.

**UI landing (ticket 15, amended).**

- New surface — the spec-gate card, the one gate 12 never designed: staged
  like the questions beat (camera to the rules scatter, anchored card in the
  question-card family), spec summary header, per-gap resolution chips,
  [Approve and sign] primary + [Request changes] ghost revealing a required
  free-text row. Re-sign-off = same card, draft-N eyebrow, what-changed line.
- Code gate and verdict cards each gain a ghost [Request changes] with the
  same required free-text reveal; [Ask about this cell] stays distinct (ask
  = conversation, reject = resolution); ≤3 affordances per card; a red
  verdict drops [Approve job].
- Grammar: rejects/holds land as feed resolution chips; spine segments
  un-fill while forward stages re-run (regression legible, never hidden);
  the spine word reads HOLDING during a hold.
