# 16 - Conductor and artifact bus

Status: open
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
