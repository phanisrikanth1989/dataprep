# 15 - Build the webview to the v2 design

Status: resolved
Type: task

## Question

Implement the real React webview on the walking skeleton to ticket 12's
settled design — `demo/etl_studio/prototype-webview-ui-v2.html` is the design
of record — consuming ticket 08's envelope end to end.

Scope:

- Port the v2 token system, component vocabulary, canvas (layout() math,
  camera choreography, assembly/flow animation) and both themes into
  `demo/etl_studio/extension/webview/` (React + TS, per ticket 03 layers).
- Real events replace the beat scrubber: reducer per 08 (attach/replay from
  `ui_journal.jsonl`, per-part stream forwarding with port-to-pixel ids, the
  one question lifecycle, credits accumulated from usage parts). The five
  beats become emergent states of the run, not modes.
- Drive it against the test double first (07): a scripted run that reaches
  every beat — idle, elicitation round, streaming activity, code gate,
  verdict — plus failure states (retry pills, finish_reason "error",
  crash-restart reattach with seq continuity).
- VS Code theme-following: map the token layer onto the webview's
  light/dark theme class; bundle fonts locally — no CDN inside the webview.
- `npm run smoke` stays green; the seam tripwire stays green; the prototype
  files stay untouched as the design record.
- Ticket 13 increment (semantics resolved there, 2026-08-09): the spec-gate
  card — question-card family anchored to the rules scatter, spec summary
  header, per-gap resolution chips, [Approve and sign] + [Request changes]
  with required free text, draft-N re-sign-off variant; ghost
  [Request changes] on the code-gate and verdict cards (red verdict drops
  [Approve job]); the hold flow (propose-confirm card, armed feed chip, hold
  question card with Resume/Stop/steer, HOLDING spine word); reject/hold
  resolution chips and spine un-fill while forward stages re-run. The
  scripted double run also exercises one hold and one gate reject.

Out of scope: live vscode.lm runs (rehearsal concern), `.vsix` packaging
(out of scope for the effort).

Unblocked: 03, 07, 08, 10 and 12 are all resolved.

## Answer

Resolved 2026-08-10. Built and verified editor-free; the F5 dev-host pass
remains with the human (ticket 10 precedent — harness proof is not editor
proof).

**What exists.**

- **Webview** (`extension/webview/`, React+TS): the v2 system ported whole —
  token layer (dark + full light), layout() DAG math and camera model
  (`layout.ts`, verbatim from the record), assembly choreography (scatter →
  glide, edges draw, flows light), camera leans (active node 0.9, code cell
  0.74, verdict wide 0.98), rules-scatter beat, spot/gatehold/wash/jsweep,
  spine (segments + gate diamonds + the one uppercase word), floating glass
  feed with composer, and the full component vocabulary: orchestrator
  bubbles (only speaking voice), observed activity windows with live-line
  shimmer fed by thinking deltas, collapse-to-"thought for Ns" pills
  (reopenable, tools inside), tool chips with expandable real output, step
  lines, resolution chips, calm warn pills, sys lines. Anchored cards in
  viewport space with dashed leaders (`Cards.tsx`): question round (rec
  preselected + why, free text, waive), code gate, verdict (red verdict
  drops [Approve job]), plus the 13 increment — spec-gate card (draft-N
  eyebrow, what-changed, per-gap resolution chips, [Approve and sign] +
  [Request changes] with required free text), Request-changes ghosts on
  code gate and verdict, propose-confirm feed card, armed-hold feed chip,
  hold card (Resume/Stop/steer), HOLDING spine word, spine un-fill on
  directed iteration.
- **Reducer** (`state.ts`): pure over 08 envelopes; seq-idempotent within a
  run, full reset on run_id change (new run = fresh journal); attach
  `{v, since_seq}` with re-attach-at-0 when the journal changed runs;
  per-part stream forwarding coalesced to animation frames (rAF batch in
  `App.tsx`); credits accumulate reducer-side from raw usage parts; the one
  question lifecycle across all nine kinds. The five beats are emergent
  (`deriveScene`): idle = no run.started, questions = pending gaps,
  streaming = open specialist streams, gate/verdict = pending kinds.
- **Scripted run** (`core/scripted_run.py` + grown double fixtures): the
  trade_positions run over the real wire through the provider port —
  gap round (blocking + advisory/waivable), spec gate with reject →
  draft-2 re-sign-off, design/configure with thinking + tool_call/usage
  parts, rate-limit retry (health.retry) after a stream.close
  finish_reason="error", per-node progress, code gate with reject →
  configurator directed iteration re-raising the changed cell only,
  verify with repair loop, verdict, composer asks answered from real run
  state, composer-intent hold via propose-confirm (armed chip → hold at
  the boundary → Resume/Stop/steer, steer routes to the interpreter),
  stop, crash-restore. Emission helpers are journal-idempotent, so a
  restarted core resumes mid-run by replaying the script against the
  journal (run.crash_restored precedes). `command.start_run`/`answer`/
  `command.ask`/`fetch_artifact` land in `core/app.py`; per-run sessions
  own fresh journals under `work/<run_id>/`.
- **Fonts local** (no CDN): @fontsource/archivo (latin 500/600/700) +
  @fontsource/ibm-plex-mono (latin 400/500/600) as npm deps, bundled by
  esbuild into `dist/fonts/`; CSP gains `font-src`; `dist/webview.css` is
  linked by the panel. Theme-following: `body.vscode-light` /
  `vscode-high-contrast-light` map to the light token layer (HC dark =
  dark); no toggle of our own — VS Code's class is the switch.

**Evidence.** `npm run smoke` grew 20 → 51 checks, all green: the original
skeleton proofs (attach idle per 08, echo fallback, cancel, crash seq
continuity, SIGTERM) plus phases 5–6 driving the whole scripted run over
the wire — every beat, one spec reject, one code reject, one hold, the
errored stream, crash mid-human-gate with `run.crash_restored` at
last_seq+1 and the pending gate surviving into an approve, full-fidelity
run-journal replay, fetch_artifact. Seam tripwire green (7 core modules).
`tsc --noEmit` and the esbuild bundle clean. Visual verification: a
scratchpad harness stubbed `acquireVsCodeApi` and replayed the real smoke
journal into the built bundle at cut seqs; screenshots confirmed idle,
questions (spot + leaders + INTERPRET spine), spec gate draft 2,
streaming (camera lean + armed chip + retry pill), hold card, code gate
(0.74 + wash + violet cell), verdict (jade wide-shot + zebra table), the
approved end state with the calm crash-restore line — dark and light.
Prototype files untouched.

**Provisional contract extensions recorded** (08 skip-unknown absorbs all):

- `stage.progress {stage, node_id, state}` — per-component configure
  progress; conductor machine truth feeding the canvas choreography.
- stream part kind `tool_result` — core-authored outcome of a `tool_call`
  for the observed window (parts vocabulary stays 07's otherwise).
- `stream.open/close` carry a fixture `label` — used by the driver's
  journal-idempotent restore; display never depends on it.
- `attach` on a runless core returns `{v}` with no `run` (08's idle
  contract, replacing the skeleton's always-run answer).
- `editor.pick_file` implemented in the shim (first concrete `editor.*`
  member; BRD door + attachments). `editor.reveal` not implemented — the
  verdict card's Open-work-dir ghost was dropped to hold 13's ≤3
  affordances rule.

**Deliberate scope facts.** The scripted demo run always plays through the
double (real specialists + live providers arrive with 17/18); the driver
is the placeholder ticket 16's conductor replaces behind the same wire —
the webview should need zero changes then, which is the point of the
contract. Scripted revisions surface no new gaps (13's minimal re-entry
honored). Testing posture per the map: smoke + tripwire only.

## Comments

2026-08-10 — F5 pass feedback (user): the scatter leaders sliced through
their own rule card and overshot its bottom (bottom-center anchor + a
hardcoded 118px height that exceeded the rendered card). Fixed: rule
anchors moved to the top-center (exact edge, no height guess) and
leadPaths() now leaves the subject on the side facing the card.
Re-verified in the journal harness at 1680x1050 on both the gap-round and
spec-gate cards.

2026-08-10 — Design amendment (user direction, superseding the ticket 12
idle beat): the two-portal opening retires for a hero composer in the
AI-product pattern — one large glass box, typed text = typed door,
attached/dropped .docx = BRD door (ember-ringed BRD chip), other files =
data-attachment chips, [+] native pick via editor.pick_file, drag state
with ember ring, Cmd/Ctrl+Enter starts. Wire unchanged (same
command.start_run payloads; BRD wins when both present, text rides as
note). Idle spine word "Two ways in" → "Ready". The v2 prototype file
remains the design record for the other four beats. Also: tool name
corrected DataPrep → RecTran across effort-owned surfaces (brand chip,
lede, extension description, LM consent line, CONTEXT.md).

2026-08-10 — F5 pass feedback (user): (1) HUD actions collapse behind a
"⋯" overflow menu at the extreme right — accidental clicks avoided, HUD
stays status-only; [+ New build] shows in the menu once the build ends,
[Exit] always. (2) The doors screen after + New build is a clean slate:
the finished build's spine ribbon and job/credit chips no longer bleed
through (chrome renders idle-look, "no build" chip + TWO WAYS IN), with
the back link as the only trace. Found en route: the menu button's class
collided with the canvas dot-grid's `.dots` (position:absolute inset
-60px sent the button off-viewport) — renamed `.dotsbtn`.

2026-08-10 — Language decision (user, after pondering the collision): the
session noun is **Build**; "run" is reserved for its ETL meaning — the
harness/Test Runner executing the assembled job at Verify. Display sweep
only: UI labels + core-authored voice strings; the wire keeps run_id /
run.* / command.start_run (contract, not display). "Approve and run" and
"run k of n" stay — genuinely executions. Term recorded in root
CONTEXT.md (Build added; Run spine renamed Spine; session-"run" swept
from definitions). Also from this pass: HUD actions restyled as their own
ember cluster with a plus glyph, and Exit added (shim.close_panel — panel
disposes, journal survives for restore).

2026-08-10 — F5 pass gap (user asked how to start over): no affordance
existed to start the next run — the doors only rendered with no run at
all, and panel reopen restores the finished run from its journal. Added a
New-run HUD chip on run end that returns to the doors (with a back link);
start_run then begins a fresh journal as designed. Harness-verified.

2026-08-10 — F5 pass feedback (user): code-gate footer buttons misaligned —
three buttons overflow the 440px card, wrapping [Ask about this cell]
alone onto a ragged second row. Fixed by taking 13's "ask = conversation,
reject = resolution ... stays distinct" literally: the ask affordance
left the resolution row and became a dotted-underline link (waive voice)
beside the gate note; the footer keeps exactly two buttons like every
other card. Harness-verified.
