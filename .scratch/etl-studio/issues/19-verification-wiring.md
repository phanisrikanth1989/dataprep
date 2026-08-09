# 19 - Verification wiring

Status: open
Type: task
Blocked by: 16, 17

## Question

Wire the verification spine on 16's chassis and 17's stages: the
materializer, the harness as a core subprocess, the value-visible
diagnostician, and the live repair loop with its exhaustion and owner:human
events.

Implements: ticket 04 (materializer + tiers, harness enrichment,
diagnostician rebuild, repair-loop semantics, execution isolation), ticket
11 (diagnostician knowledge slice + the only engine-source mount), ticket
13 (human-gate options live), ticket 05 (owner+forward made real -- the
verb is 16's, this ticket exercises it with real stages).

Scope:

- Materializer (code; vendored `materialize_golden` plus the tier logic
  relocated out of `extract_doc`): runs post-sign-off; writes input files
  and `golden/` from either door's data; computes the rung-aware tier
  (transcribed image/prose data never earns verified); the tier freezes at
  materialization.
- Test-runner (code -- the agent ceremony is dropped): vendored
  `run_and_validate` CLI run as a subprocess of the core against the
  read-only engine (`src/v1`), output captured; job code cells are
  RCE-capable and must never be able to take the core down. Enrichment
  added: `test_report.json` embeds up to 5 offending keys per diff bucket
  with expected-vs-actual per differing column.
- Diagnostician (tier-3 authored fresh, value-visible): reads the enriched
  report plus the work dir; tools per 11's matrix -- work-dir reads, the
  `src/v1` read-only mount (tool-registry absence enforces the ban for
  every other stage), `config-surfaces` with live file:line anchors;
  knowledge slice (flow-scoped landmines WITH code anchors + envelope +
  flow-scoped reference) via 17's renderer. Writes `feedback.json`:
  {owner, evidence (structural signal + bounded real values), why, fix,
  suspect?, question?}; owner enum interpreter | flow-designer |
  configurator | assembler | human; auto-repair only below the oracle (no
  doc-normalizer owner -- oracle breaches route to human); a failure
  fixable only by silencing a note-sourced rule routes to human, never
  silently repaired.
- The repair loop live through 16's verbs: fail -> diagnostician -> owner
  re-runs reading feedback.json first -> every forward stage -> harness
  again; <=3, verified tier only (smoke is exactly one run, build never
  runs); exhaustion raises 16's grant/stop-to-gate/steer question;
  owner:human raises its structured question; a mid-loop spec revision
  re-presents the spec for re-sign-off.
- Human gate live with 13's options: Approve absent on a red verdict,
  smoke-clean approvable, Request changes = spec door returning to the
  gate, Stop.

Invariants: engine invoked strictly read-only; vendored copies only; all
new code under `demo/etl_studio/`.

Done when a trade_positions run (double-scripted specialists where needed,
real harness) reaches a real red verdict, the diagnostician names an owner
from real evidence, the loop repairs, and the harness goes green to the
human gate -- with one scripted exhaustion grant and one owner:human
question surfacing on the channel; at least one live diagnostician turn on
this Mac (Mac-provisional); `git status src/v1` clean before and after as
the read-only proof.
