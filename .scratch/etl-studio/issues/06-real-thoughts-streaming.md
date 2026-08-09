# 06 - Real thoughts: what streams to the UI?

Status: resolved
Type: grilling
Blocked by: 01

## Question

What does "real reasoning and state, never canned" concretely mean on the
webview -- raw token streams per agent, curated-but-real agent output, or
layered (curated default, expandable raw)?

To settle, informed by ticket 01's facts on what vscode.lm exposes:

- What is actually streamable per model call (text deltas; whether any
  reasoning/thinking content exists beyond output tokens).
- Per-agent framing: how the UI attributes a stream to a pipeline stage.
- What replaces the old presenter's canned _LABEL / _CALLOUT / THOUGHTS
  layers.
- Data posture: the old presenter was deliberately data-free; the new UI
  shows real content to the human who owns the input. State the new rule.

## Answer

Resolved 2026-08-09 via grilling (two rounds; the user reset the frame
mid-way: think AI product -- Claude Code / Claude Desktop-class thinking UX --
not a compliance display; rigidity kills the aha moment). Ticket 05 landed
mid-session and reshaped the tree: the thoughts stream = specialist streams +
orchestrator narration/answers, no separate narrator model. Terms in root
`CONTEXT.md`.

**The rule: content real, presentation free.** Every string shown as
reasoning or state must be traceable to THIS run -- a stream part, an
artifact field, or an event. That admits verbatim model output,
orchestrator-restyled prose (original survives in artifact + audit, per 05),
and fixed templates framing real values that assert nothing the run didn't
produce. Presentation -- shimmer, motion, collapse grammar, streaming
animation, phrasing templates -- is unrestricted. The old canned layers die
for inventing content (THOUGHTS pool, _CALLOUT rationale, _LABEL); the old
presenter's classify()-style config-derived labels survive as derived state.
The pill's form was right, its feed was fake: the design center is an
AI-product surface fed by real content. Temporal corollary: content moves
only when real content arrives; true silence renders the real in-flight
operation with elapsed time -- animated freely, never a canned rotation.

**What streams (the thoughts stream, composed per 05).**

- Orchestrator narration + Q&A answers: the feed's speaking voice.
- Per-specialist live activity: a thinking block (collapses to "thought for
  Ns", reopenable) + tool chips (expandable to real output) + the live line.
- Conductor: never a speaker -- its work renders as state changes (stage
  lights, gate opens), not speech.
- The live line (the THOUGHTS-pill successor): one present-tense line of NOW,
  fed by priority from (1) real thinking deltas when the proposed-API flag
  works (--enable-proposed-api in our F5 launch config;
  unsupported-but-working per 01; ticket 09 probes it), (2) the specialist's
  prompted opening line -- one line of what it is about to check before its
  JSON; same call, so legal under 05's no-separate-narrator rule, (3) its
  tool-call verbs. Graceful degradation, never silent, never canned.

**Surfaces and voice (one-voice reconciled with 05).** Canvas is the hero
stage -- a live ETL pipeline assembling is the differentiator; the feed docks
beside it, both first-class. 05's single voice governs who ADDRESSES the
human, not whose work is visible (05's own for-06 note mandates specialist
streams; its verbatim class already puts specialist-authored code cells,
options and diffs in front of the human untouched). Per surface:

- Feed (conversation): orchestrator only -- questions, narration, gate
  summaries, answers. Only the orchestrator gets chat bubbles.
- Thinking blocks / live line: observed work -- a window, not a message.
- Canvas (state): artifact fields rendered verbatim + attributed (05's
  verbatim class generalized) -- labels, purpose text, rule text, diffs, code.

Attribution renders as provenance bylines (a small stage chip on the node),
never as bubbles. Hard constraint enforcing "never addresses the human":
specialist content never carries a response affordance -- no button, input or
question attaches to it; anything needing an answer goes through the question
channel in orchestrator voice. Absence stays absence: no code-side fallback
prose anywhere; if every node must carry purpose text, fix the
flow-designer's prompt contract upstream.

**Per-agent framing.** The core tags every model call with its owning stage
at call-issue time (it knows; no inference). Display names are the
title-cased domain names (Interpreter, Flow Designer, Configurator,
Assembler, Diagnostician, Doc Normalizer) -- one vocabulary, docs to screen.
Code stages (Explode, Materializer, Test Runner...) appear in the feed as
step chips with real event lines ("Materializer: wrote golden/,
tier=verified"). The orchestrator is a first-class presence with its own
voice; the conductor is invisible as a speaker.

**Data posture.** Data-free is dead. The UI renders whatever the run's
artifacts and events carry, real values included -- filter predicates, join
keys, expected-vs-actual diff rows, sample rows -- bounded only by what the
artifact already bounds (e.g. the harness's 5-examples-per-bucket cap); no
redaction or aliasing layer anywhere; whole data files open in the editor,
not the feed. Conscious consequence, on record: no masking mode exists for a
viewer who is not the data owner -- out of scope by decision.

**Run health, shown real and premium.** Live credit readout accumulated from
the trailing `usage` DataParts only (narration turns included; absent part ->
no number, never a countTokens estimate). Failures render as themselves,
calm: "Rate-limited -- retrying (2)" chips, shape-repair and repair-loop
iterations as "attempt 2 of 3", propose-confirm escalations visible -- real
state, never a masking spinner. A repair loop recovering live is the backend
showing through the frontend.

**For ticket 07:** the provider port surfaces thinking deltas as optional
stream parts when the adapter has them; core and UI treat them as bonus --
absent parts change nothing.
**For ticket 08:** channels implied by this policy: orchestrator prose,
per-specialist activity (attributed; thinking/tool/output parts), conductor
state events, usage events, failure states. Shapes are 08's.
**For ticket 09:** the flag probe decides live-line source (1) vs (2); no
other design change either way.

Boundaries held: 08 owns message shapes; visual/layout detail (including the
exact thinking-block and chip designs) is implementation-slice fog;
pause/steer stays fog.
