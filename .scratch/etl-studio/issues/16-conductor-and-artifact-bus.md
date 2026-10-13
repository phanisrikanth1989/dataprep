# 16 - Conductor and artifact bus

Status: resolved
Type: task

## Question

Build the deterministic runtime chassis under `demo/etl_studio/` -- ticket
05's code conductor, ticket 04's artifact bus, and the full question
lifecycle -- on the walking skeleton (ticket 10), so tickets 17-19 have real
sequencing, events and state to land on. Stub specialists are this ticket's
test rig; ticket 17 replaces them stage by stage.

Implements: ticket 05 (conductor layer), ticket 04 (bus, loops/caps/tiers,
question-event families), ticket 08 (event authorship, resolution recording,
run lifecycle), ticket 13 (hold + directed-iteration verbs, per-gate
options, uncapped human acts), ticket 07 (port completion, core-owned
backoff, double fixture format), ticket 10 (provisional-extension
reconciliation), ticket 02 (round bookkeeping + question-channel mechanics).

Scope:

- Conductor (code, never a speaker): fixed itinerary per 04's spine for both
  doors; loop counters (shape-repair <=3, main repair <=3, elicitation 3
  rounds, configurator inner loop separate, grants uncapped); the
  owner+forward re-run rule; tier routing (verified loops, smoke runs
  exactly once, build never runs); gate raising; artifact moves; resolution
  recording untouched (no model in the return path). Defines the
  stage-adapter interface that 17/18/19 implement against; ships with stub
  stages.
- Artifact bus: flat per-run work dir `demo/etl_studio/work/<job>/` (+
  `golden/`), fixed canonical names, produce-don't-mutate; on supersede the
  old version moves to `history/<artifact>.<k>` (k monotonic per artifact)
  and `audit.jsonl` maps each k to its context; nested `.gitignore` keeps
  the containment invariant.
- Question lifecycle: all nine kinds on the one raised->resolved lifecycle
  with conductor-authored structured options and no timeouts anywhere --
  elicitation gap rounds (round_id batching), extraction needs_human, spec
  sign-off + re-sign-off (re-raise only when the spec changed), code gate
  (vendored `surface_code_cells`; batch approval; re-raise new/changed
  cells only), budget-exhaustion grant/stop-to-gate/steer, owner:human,
  human gate (13's options: Approve absent on red verdict, smoke-clean
  approvable), propose-confirm escalation, hold.
- Ticket 13's verbs: directed iteration (owner interpreter = spec door,
  owner configurator = code door; the raising surface fixes the door, the
  conductor never routes by reading text); hold armed at the next stage
  boundary (in-flight artifact lands whole, no mid-stream cancel; armed
  window visible); stop ends the run plainly (journal marks
  stopped-by-you); every human-initiated act is uncapped and burns no loop
  budget.
- Standing injection rule (grilled 2026-08-10): when intake carries no
  sample/expected data, the conductor injects the missing-data advisory gap
  ("attach data to get verification") into the elicitation round -- code,
  not the model, guarantees it fires every run; the gap object shape stays
  ticket 17's.
- Event and journal authorship: run.* / stage.* / question.* / health.*
  per 08; `artifact_written` carries the renderable fields; `fetch_artifact`
  serves full artifacts from the bus; `command.start_run` starts a run with
  a fresh journal and real run ids (retiring the skeleton's fixed
  "skeleton"); per-part stream forwarding at run scale; `audit.jsonl` and
  `ui_journal.jsonl` append-only; crash-restore from bus + audit with seq
  continuity and `run.crash_restored`, plus the orchestrator context-rebuild
  feed (05) that ticket 18 consumes.
- Port completion to ticket 07's full surface (the skeleton deferred it):
  tool declaration/invocation round trip over `lm/*` (the shim already
  relays toolCall parts), the tool-use loop runner (03 recorded no agent
  loop exists to vendor -- new code, shared by 17/18/19), image content
  behind the capability flag, count_tokens, typed options, per-stage model
  selectors from config (09's roster, select by vendor+id; defaults tuned at
  rehearsal), core-owned visible backoff emitting health.* events. The
  double grows 07's full fixture format: scripted tool calls, thinking
  deltas, error injection.
- Ticket 10's provisional extensions reconciled into the contract:
  `stream.close` finish_reason "error", `shim.restart`, real run ids.

Invariants: all code under `demo/etl_studio/`; `surface_code_cells` and
`audit_log` vendored from `agents/tools/`, never imported; engine untouched.

Done when a scripted double-provider run with stub stages walks the full
itinerary end to end for both doors -- an elicitation round including the
injected advisory gap, spec sign-off, code gate, a repair-loop pass with one
exhaustion grant, a hold + steer, a stop, and the human gate -- producing
bus artifacts with history/, audit.jsonl and ui_journal.jsonl, and surviving
a mid-run crash-restore with seq continuity; `npm run smoke` and the seam
tripwire stay green.

## Comments

2026-08-10 -- ticket 15 landed pieces this ticket planned to build; start
from its delta, replace its placeholder:

- Already exists (keep, or absorb as-is): the double's full fixture format
  (keyed scripts: thinking, tool calls, usage, pauses, error injection --
  `adapters/double/adapter.py`); `command.start_run`/`answer`/`command.ask`/
  `fetch_artifact` handlers with per-run sessions and fresh journals + real
  run ids (`core/app.py`); per-part stream forwarding at run scale; the nine
  question kinds' payload/option shapes the webview now renders
  (`core/scripted_run.py` is the reference); boot-time crash-restore with
  `run.crash_restored` and seq continuity; smoke phases 5-6 as the standing
  run-level wire proof.
- To replace: `core/scripted_run.py` is a journal-idempotent scripted
  placeholder, not a conductor -- no bus, no audit.jsonl, no caps/tiers, no
  stage adapters, journal-only restore. The conductor takes over behind the
  SAME wire (payload shapes above are now load-bearing for the webview);
  the webview should need zero changes.
- New extensions 15 recorded beyond ticket 10's list, to reconcile here:
  `stage.progress {stage, node_id, state}`, stream part kind `tool_result`
  (core-authored tool outcome), fixture `label` on stream.open/close,
  runless `attach` -> `{v}` with no run, `editor.pick_file` in the shim.
- Still missing from the port surface (unchanged scope): tool round trip
  over `lm/*`, the tool-use loop runner, count_tokens, typed options,
  per-stage model selectors, core-owned backoff beyond the scripted
  rate-limit retry.

## Answer

Built 2026-08-10. `npm run smoke` grew 51 -> 74 checks, all green (both
doors end to end, crash-restore mid-gate, bus assertions on disk); seam
tripwire green (16 core modules); `tsc --noEmit` and esbuild clean; the
webview needed zero changes, as required.

**Module map** (all new code under `demo/etl_studio/core/`):

- `conductor.py` -- the code conductor: both doors' fixed itinerary, loop
  counters (shape-repair <=3, repair attempts <=3 + uncapped grants,
  elicitation 3 rounds + batch fallback), owner+forward rule via one
  `_DirectedIteration(owner)` primitive (spec door = interpret, code door =
  configure), tier routing (verified loops; smoke runs once; build never
  runs), gate raising, boundary/hold/stop/steer verbs, propose-confirm
  escalation on unplanned stage failure, orchestrator context feed
  (`orchestrator_context()`, rebuilt from audit+bus -- ticket 18 consumes).
- `bus.py` + `vendored/audit_log.py` -- ArtifactBus: canonical names,
  produce-don't-mutate, supersede to `history/<artifact>.<k>` (k monotonic
  per artifact), `audit.jsonl` maps each k to its context; artifact index
  feeds `fetch_artifact` (full artifacts served from the bus).
- `questions.py` -- all nine kinds on one raised->resolved lifecycle;
  resolutions recorded untouched; answers validated against the
  conductor-authored option ids (an out-of-contract choice -- e.g. approve
  on a red verdict -- is ignored and the question stays pending).
- `llm.py` -- StreamRunner: per-part forwarding, the tool-use loop runner
  (shared by 17/18/19; handlers dispatched core-side, `tool_result` parts
  core-authored, results fed back as message items), core-owned visible
  backoff (`health.retry`, bounded attempts, errored stream closes then a
  fresh stream opens).
- `models.py` -- per-stage selectors from optional `studio_config.json`
  (select by vendor+id via enumeration; absent = adapter defaults;
  `--config` on main.py).
- `stages.py` -- the StageAdapter/StageContext/StageResult interface
  17/18/19 implement against; slots: explode, doc_normalize,
  normalize_validate, intake_build, interpret, materialize, design,
  configure, assemble, test_run, diagnose (+ `ctx.repair` for quiet
  repair-loop re-runs).
- `stub_stages.py` -- the trade_positions rig (content constants moved from
  the deleted `scripted_run.py`); rig knobs ride `start_run.rig`
  (verify_fails / shape_errors / needs_human / owner_human).
- Port completed (`port.py`, both adapters, `lmBridge.ts`): content items
  (text/image/tool_call/tool_result), tool declarations, typed ChatOptions,
  `count_tokens` capability (`lm/countTokens` in the shim), system-role
  emulation and tool-convention mapping in the Python adapter (shim stays
  mechanical), `request.label` = UI stream label = the double's fixture
  key. The double's fixtures now script real loops: `config.main` round 2
  is the tool-results follow-up; `config.write` call 1 rate-limits so the
  backoff genuinely re-issues.

**Decisions locked while building** (the deltas 17/18/19 stand on):

- Run dir is per-run: `work/<job>-r<k>/` (the run id, ticket 15's naming);
  04's `work/<job>/` reads as "per job-run", since one job runs many times.
- Restore model: bus + audit own the state (door/request/rig ride the
  audited `run_started` entry; tier/cells/grants re-derive from audit +
  resolutions), the UI journal owns seq and emission idempotence. The
  conductor re-walks its deterministic itinerary with count-based ledgers
  (artifacts by name, streams by label, loop chips by stage) -- the Nth
  call this walk matches the Nth journaled emission, so nothing replays.
- Tool-loop stream semantics reconciled into the contract (envelope.py):
  one stream per attempt; follow-up rounds reuse the attempt's stream_id;
  port-to-pixel holds because every round's `lm/chat` carries that id.
- `run.started.tier` is now null -- the tier is honestly frozen at
  materialization (audit `tier_frozen`; golden artifact fields + human-gate
  payload carry it). The webview stores but never rendered run.tier, so
  nothing changed on screen.
- The code gate re-pause rule is hash-based: cells surface via the vendored
  walker over job.json, display metadata merges from config.json's
  `cell_meta` sidecar, and approval records sha1(component|field|code) in
  the audit -- only unapproved hashes re-raise (new vs changed flags from
  the raised-cells set).
- The injected G0 gap: advisory, `rule_id: "verification"`, options
  attach (free text carries comma-separated paths -- the mid-run file-picker
  affordance is ticket 17+ UI) / waive; an attach answer flips the tier
  computation input and lands `data_attached` on the audit.
- Verdict vocabulary: verified | failed | smoke_clean | smoke_failed |
  unverified(build); Approve is omitted from the OPTIONS on red verdicts
  (13), enforced wire-side by the option-id validation.
- Stub interpreter always raises G1/G2 on both doors -- the demo BRD is
  deliberately incomplete (that IS the demo story); 02's zero-question path
  survives as mechanism (the round loop drains when no gaps exist, proven
  by G0-only suppression on the BRD door).
- Unplanned failures (LlmCallError after backoff) raise a propose-confirm
  (stop / dismiss-and-retry-once) -- 05's "free to pull the cord" without
  the ticket-18 orchestrator yet.

**Provisional extensions recorded here** (documented in envelope.py):
question kinds needs_human / exhaustion / owner_human payload shapes
(source+prompt / loop+k+n+grant_size / prompt+evidence, all with structured
options); `health.retry.stream_label`; `stream.open.model {vendor, id}`.

**Webview renderer gaps flagged to ticket 21** (wire and journal carry
everything; the UI lacks cards): needs_human / exhaustion / owner_human
raise real pending questions the webview cannot yet display or answer, and
VerdictCard keys Approve on `verdict === "verified"`, so an approvable
smoke_clean/build verdict hides its Approve button (13's "smoke-clean
approvable" is wire-true, pixel-false). None of these fire in the default
demo walk.
