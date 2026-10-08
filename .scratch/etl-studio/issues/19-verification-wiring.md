# 19 - Verification wiring

Status: resolved
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

## Answer

Built 2026-08-10 (commit e54a717f + the resolution commit). The
verification spine is real on 16's chassis: `npm run smoke` grew 84 -> 93
checks, all green -- twice, the second pass against the final vendored
harness -- with real red -> repair -> green arcs on BOTH doors; seam
tripwire green (29 core modules); tsc + esbuild clean; the webview needed
zero changes; `git status src/v1` clean before and after (including after
the live probe, whose engine runs all executed inside run dirs through the
path jail).

**Done criteria, with provenance:**

- Double-proven (smoke): the typed-door walk materializes inputs + golden
  from four REAL attached example files, run 1 fails RED from the real
  engine (4/4 keyed rows value_mismatch, enriched examples carrying
  expected `30200` vs actual `30200.0`), feedback.json names the
  Configurator with value-visible evidence, the repair re-runs
  owner+forward, and run 2 goes green to a human gate whose verdict fields
  (verified, matched 4/4, runs 2/3, diagnosis naming the real owner + fix)
  all derive from the real report. The BRD walk runs the full arc: an
  owner:human diagnosis questioning the golden itself (answered "run again
  as-is"), a misdiagnosis whose faithfully-applied fix GENUINELY widens the
  diff on disk (run 3 adds closing_price to the mismatch columns),
  exhaustion at k=3 with one granted extension, and the correct fix green
  on run 4. Crash-restore mid-human-gate still replays full-fidelity.
- Live-proven (Mac-provisional, rig-answered): one live diagnostician turn
  on THIS Mac via the autorun rig + CLI dev host -- stream provider
  `vscode_lm`, two real tool rounds, and a feedback.json naming owner
  `configurator` with evidence quoting the real report's values
  ("value_mismatch=4 ... market_value expected '30200' vs actual
  '30200.0'"); the loop repaired and the run ended approved. Honest
  wrinkle, recorded verbatim: the live `fix` field came back off-target
  and object-shaped (`{"key": "die_on_error", "value": true}`, suspect
  derive_mv) -- owner routing and evidence quality proven, fix quality is
  ticket-20 live-tuning territory (ticket 11's "feedback.json carries more
  load" warning made concrete). The live diag stream also carried 2 usage
  parts (token-shaped), confirming 18's usage-parts news for 20.

**The demo defect story changed -- forced by the real oracle.** The stub
era's run-1 failure was a mis-sort (`sort_type` unset), but the vendored
harness diff is ORDER-INSENSITIVE (keyed on trade_id; bag compare sorted)
-- a mis-sort can never produce a red verdict, by the engine world's own
locked design ("a wrong final order ships undetected"). Run 1 now fails on
a textual-parity defect: the configurator types `market_value` float, the
engine writes `30200.0`, the golden says `30200` -- numerically identical,
textually wrong, and the oracle compares text. That IS the DataPrep moral
(Talend parity is byte parity), it exercises the enriched report's
per-column expected-vs-actual examples, and the fix is one config-draft
type -- gate-approved code cells stay untouched by repairs, as 17 locked.
The parallel session independently validated an alternative beat (inner
join dropping T005, contradicting the signed G1 keep-blanks answer);
recorded here as a rehearsal option, not built.

**Module map** (under `demo/etl_studio/`):

- `core/vendored/materialize_golden.py` -- near-verbatim vendor (CLI main
  dropped); path jails, rung-aware graded allow-list (rung 1-2 only),
  sniffed-delimiter round-trip all port whole.
- `core/vendored/run_and_validate.py` -- the harness, vendored with ticket
  04's enrichment: per-bucket `examples` (up to 5 offending keys;
  expected-vs-actual per differing column; bag diffs get sample rows) plus
  keyed-diff row counts. Run as the test-runner's SUBPROCESS; inside it the
  job runs in-process through ETLEngine exactly as the original. Joint
  provenance: this file was written by both this session and the parallel
  one (see Comments); the committed shape is the parallel session's,
  re-verified green. `src.v1` resolves via the repo venv's editable-install
  .pth -- no sys.path shim needed.
- `core/real_stages.py` -- three new stages; `stub_stages.py` deleted.
  RealMaterializer: BRD door reads the validator's extract; the TYPED door
  synthesizes one from attachments (stem `<output>`/`<output>_expected`
  maps an attachment to that output's answer key, other CSVs become
  sources; sniffed delimiter; first-column key iff tuple-unique; all rung 1
  by construction) and lands it under the SAME canonical
  `extract_doc.json`, so the configurator's delimiter reads and the
  diagnostician's provenance reads never fork on the door. Tier =
  verified/smoke/build from what actually materialized; frozen by the
  conductor. RealTestRunner: vendored CLI as an asyncio subprocess (180s
  timeout, kill on hang -- an RCE-capable cell can never take the core
  down), stdout/stderr captured to `runs/run-<k>/harness_output.txt`,
  report facts verbatim into notes/fields. RealDiagnostician: tier-3
  authored-fresh prompt; inline report + spec rules/gap_resolutions +
  config.json + topology + 11's slice (flow-scoped landmines WITH anchors,
  envelope, flow-scoped reference); four tools -- list_work_files /
  read_work_file (run-dir jail), read_engine_source (the pipeline's ONLY
  src/v1 mount, realpath-jailed, 120-line windows), read_config_surfaces
  (rendered file:line reference) -- registry absence enforces the ban
  everywhere else; joined LIVE_SLOTS.
- `core/conductor.py` -- verify rewritten on real facts: verdict
  matched/runs/diagnosis assemble from the last report + feedback (06:
  every shown string traceable); owner enum enforced FAIL-CLOSED (anything
  outside interpreter|flow-designer|configurator|assembler|human routes to
  human -- the old agent's "cannot classify -> human" rule is now code);
  owner+forward runs the owner then EVERY forward design-side stage
  (design -> configure -> assemble); `_verdict_table` reads the golden
  through the manifest; `scripted_slots` rig knob pins named slots to the
  double inside a live run (the live-probe affordance).
- `core/real_stages.py` (assembler) -- structural enforcement extended to
  `schema.output` byte-for-byte from the draft, with each consumer's
  `schema.input` rebuilt from its driver producer's enforced output. The
  prompt always assigned schema.output to the Configurator; without the
  enforcement a schema-typed repair was silently dropped in re-wiring and
  the loop could never converge. Locked delta, same philosophy as 17's
  config-from-draft.
- `core/prompts.py` -- `_DIAGNOSTICIAN_SYSTEM` (tier 3, authored fresh):
  value-visible posture, the auto-repair-only-below-the-oracle boundary
  (no doc-normalizer owner; golden doubts -> human with a question;
  note-tagged rules never silently silenced), and the ported owner-routing
  map from the data-blind original.
- `core/demo_fixtures.py` -- the new defect story: draft mv float / repair
  mv int / misdiagnosis floats closing_price too; four diagnostician reply
  labels (`diag.run`, `.human`, `.miss`, `.after`) whose quoted values
  match what the deterministic reports actually carry;
  `config.repair.miss`; ORCH verdict line updated. Rig knobs are
  fixture-label selectors only: `verify_fails` is dead; `diag_misses`,
  `owner_human`, `scripted_slots` arrived; the configurator's repair label
  follows the diagnosis that produced it (`_last_diag`).
- `examples/trade_positions_expected.csv` -- the typed door's golden
  attachment (the docx answer table as a CSV).
- `core/app.py` -- autorun bot caps unattended owner_human retries at one
  (then stop-to-gate): uncapped human acts are for humans, not probe bots.

**Flagged forward:**

- To 20: live diagnostician FIX quality (owner/evidence proven; the fix
  field needs prompt-side tuning or a shape constraint before a fully-live
  repair loop); usage parts now arrive on live diag streams (token-shaped,
  2 observed) -- reconcile the credit readout; the inner-join/T005
  alternative beat is available for rehearsal staging.
- To 21 (unchanged): owner_human / exhaustion cards and smoke-clean
  Approve remain webview renderer gaps -- both kinds now genuinely fire in
  smoke phase 7 over the wire; the default demo walk still never fires
  them.
- Honest coverage note: the smoke-tier and build-tier verify paths
  (`--smoke` runner branch; build short-circuit) are code-complete but not
  smoke-asserted -- no phase walks a smoke-tier or dataless run through
  verify to its gate.

## Comments

2026-08-10 -- Provenance note: a second Claude session was independently
pointed at this ticket and began work before noticing this session's
claim; it backed off cleanly. Its read-only engine probe independently
confirmed the two load-bearing facts (order-insensitive oracle; float
formatting vs the integer golden). One file collision:
`core/vendored/run_and_validate.py` was authored twice -- this session's
copy overwrote theirs unknowingly, theirs later landed over this
session's edits; the committed version is the parallel session's
(enrichment shape equivalent, no sys.path shim -- the venv .pth carries
`src.v1`), re-verified by a full second smoke pass (93/93).
