# 17 - Doors and specialists

Status: resolved
Type: task
Blocked by: 16

## Question

Build the two front doors and the design-side specialists on ticket 16's
chassis -- the vendored BRD chain, the typed intake, the shared interpreter
with gap-driven elicitation, flow-designer, configurator, assembler -- plus
the knowledge-delivery machinery (ticket 11) that feeds every LLM stage,
including 18's and 19's slices.

Implements: ticket 02 (doors, intake envelope, gap objects, elicitation
content), ticket 04 (BRD-door spine, shape-repair participants, sample-value
reads), ticket 11 (knowledge sources, render-at-startup, slice map, prompt
ports tiers 1-2), ticket 06 (stage-tagged calls, prompted opening line, no
code-side fallback prose).

Scope:

- BRD door, vendored from `agents/tools/` into `demo/etl_studio/`:
  `explode_doc` (jailed extraction, rung metadata), `normalize_validate`
  (fail-closed; shape_error enters 16's shape-repair loop; needs_human goes
  to the question channel); `extract_doc` demoted to library code -- no
  purity stage, no template route; `docx_purity` is not vendored (dead per
  04).
- Typed door: thin intake builder -- request text, optional data files,
  job name. One `intake.json` envelope with `door: brd|typed` wraps both.
- Specialist harness riding 16's loop runner: per-stage prompt assembly from
  knowledge slices, per-stage tool registries (registry absence IS the
  enforcement), stage-tagged calls at call-issue time (06), the prompted
  opening line before the JSON (06's live-line source), JSON artifact
  parsing with bounded malformed-output retries (escalation hands to the
  orchestrator once 18 lands), prompt-budget checks via count_tokens where
  the model has it.
- Interpreter (tier-2 port absorbing doc-interpreter): serves both doors
  from intake.json; emits 02's gap objects (target field, question text,
  options + recommended default, blocking|advisory severity, recorded
  resolution); drafts `requirement_spec.json` (draft-N on the bus); re-runs
  as the spec door under 16's directed iteration; reads sample values --
  bounded rows in-prompt, full files via tool (04). The missing-data
  advisory gap is conductor-injected (16); its object shape is this
  ticket's.
- doc-normalizer (tier-2 port: purity/template references die, needs_human
  routes to the channel). flow-designer, configurator (vendored
  `validate_config` as its bounded inner loop), assembler: tier-1
  near-verbatim ports from `.github/agents/*.agent.md` -- knowledge
  sentences become "included below", subagent/terminal mechanics become
  core tools.
- Knowledge delivery per 11: sources vendored (`agents/schemas/*.json` +
  `_index.json`, `agents/knowledge/landmines.py`, the renderer's authored
  prose, `config-surfaces.md`, patterns/envelope resources);
  `render_skills` adapted to render at every core startup into a gitignored
  knowledge dir; the slice map replaces the SKILL index; slice legality
  (whole artifact / field projection / component filter -- never editorial
  picks); fit-pass items: restore code anchors in landmine rendering,
  filter/projection render functions; the enum-ref drift and
  fixture-consistency checks ride along with the sources. The renderer
  also serves the orchestrator's and diagnostician's matrix rows (consumed
  by 18/19).
- Data-write ban is structural: no specialist holds a data-write tool; on
  this ticket only explode_doc's jailed extraction writes data files.

Invariants: vendor, never import `agents/`; everything under
`demo/etl_studio/`; engine untouched.

Done when a BRD-door run (the vendored trade_position_demo.docx) and a
typed-door run both reach a signed-off `requirement_spec.json` through real
elicitation on 16's chassis -- gap rounds raised and resolved, needs_human
and shape-repair each demonstrated once, drafts versioned on the bus -- and
flow-designer -> configurator -> assembler produce their artifacts through
the code gate with 16's stub standing in for the materializer (19's);
proven against the double plus at least one live run of the chain on this
Mac (Mac-provisional per the provenance rule); seam tripwire green.

## Answer

Built 2026-08-10 (commits c2a29915 + d96110df). Both doors and all five
design-side specialists are real on ticket 16's chassis; `npm run smoke`
grew 74 -> 76 checks, all green (both doors end to end through the REAL
stages, with the vendored validator producing the shape-repair and
needs_human beats from genuine content defects); seam tripwire green (27
core modules); tsc + esbuild clean. The webview needed zero changes.

**Done criteria, with provenance:**

- Double-proven (smoke): BRD door explodes the vendored
  `examples/trade_position_demo.docx` for real (7 handles: 2 tables, 2
  prose blocks, 3 rung-1 sibling CSVs), and both doors reach a signed-off
  `requirement_spec.json` through real elicitation -- gap rounds with
  dependency-first re-find (typed: r1 G0+G1+G2 -> re-found G3 in r2 ->
  drains; BRD: r1 -> drains), shape-repair and needs_human each demonstrated
  once from real validator verdicts on scripted content, drafts versioned in
  `history/`; design -> configure -> assemble produce their artifacts
  through the code gate with 16's stub materializer/test-runner.
- Live-proven (Mac-provisional): one full BRD-door run on THIS Mac through
  the live vscode.lm adapter in the CLI-launched Extension Development Host
  -- every specialist stream `provider: vscode_lm` (shim-default Copilot
  model; per-stage selectors available via `studio_config.json`), one real
  needs_human convergence (the live model missed table:0's disposition
  once), live-raised G1/G2 gaps from the real BRD, signed spec at tier
  verified (all sources rung 1, graded output rung 2), a live-designed
  11-component / 10-flow job through the real validate_config loop
  (11/11 clean), the code gate, and an approved run end.
  Provenance caveats: questions were answered by the autorun rig's
  deterministic kind policy (recommended option / approve / one-grant cap),
  not a human -- the HITL live demo remains ticket 20's; earlier probe
  attempts r1/r2 ended in honest exhaustion stops before three prompt-side
  convergence fixes landed (see below).

**Module map** (new code under `demo/etl_studio/`):

- `core/vendored/`: `explode_doc.py` (purity dropped, jail helpers inlined),
  `extract_doc.py` (library remnant: block iteration + derived facts),
  `normalize_validate.py` (dict API `validate_proposal`; studio addition:
  `extraction.unresolved_why` carries the actionable per-name reason),
  `component_schema.py` (+ repo-root sys.path for read-only engine
  enum_refs), `validate_config.py`, `landmines.py`.
- `knowledge/` (schemas + `_index.json` + config-surfaces.md vendored) +
  `core/knowledge.py`: render at every core startup into gitignored
  `work/_knowledge/` (enum-ref drift check rides the render, fail-loud);
  slice map per 11's matrix with component-filter (alias-expanded through
  the index) and field-projection renderers; landmine code anchors
  restored; orchestrator + diagnostician rows rendered for 18/19.
- `core/prompts.py`: tier-1 near-verbatim ports (flow-designer,
  configurator, assembler) and tier-2 rewrites (doc-normalizer,
  interpreter-absorbing-doc-interpreter); knowledge sentences became
  "included below", terminal mechanics became core tools; every prompt
  carries 06's opening-line contract.
- `core/specialist.py`: the harness on 16's loop runner -- stage-tagged
  calls, capture-based JSON parsing (opening line + fenced artifact),
  bounded malformed-output retries (2, then LlmCallError -> propose-confirm
  escalation), count_tokens prompt budget at 0.9x the model window,
  bus read-back on journal-skipped streams (crash-restore).
- `core/real_stages.py`: the eight real slots + `build_stages()` keeping
  16's stub materializer/test-runner/diagnostician; `LIVE_SLOTS` routing.
- `core/demo_fixtures.py`: the double's scripts as real specialist replies
  (blob-chunked fenced JSON); the vendored validators judge the content.
- Chassis deltas: `_s_gaps` re-find loop (interpreter re-runs between
  rounds; post-batch fold-in closes the loop -- leftover gaps land on the
  spec, never round 5); `RunInfo.nh_resolutions` + `interpret_mode`
  (conductor-set, restore-derived); shape feedback rides `ctx.repair`;
  real notes thread from StageResult data; live/scripted port routing in
  StreamRunner (`LlmCall.live`, per-run announced fallback); boot-order
  fix (rpc read loop serves before restore; `_ready` gate on wire
  handlers -- a racing start_run can no longer close restore's journal);
  double grew the `blob` part kind.

**Decisions locked while building** (deltas 18/19/20/21 stand on):

- Structural invariants beyond the ticket text: the assembler stage
  ENFORCES config-from-draft (parsed job components get the draft's config
  byte-for-byte; terminal rename maps by elimination), and a repair pass
  preserves gate-approved code cells (a cell changes only through the
  gate's hash-based re-raise). Both hold against live models, not just
  fixtures.
- needs_human is failure-typed: unresolved sources/outputs get
  guide(free,recommended)/drop_source with the validator's exact reason in
  the prompt; unaccounted handles get irrelevant(recommended)/guide.
- The interpreter's refind label is door-split (`interp.refind` /
  `brd.refind`) because the two doors' scripted fold-in stories diverge.
- Rig knobs survive as fixture-label selectors only (shape_errors,
  needs_human pick `brd.normalize.shape/.gap`); the default demo walk and
  live runs always play the plain labels -- 16's "none fire in the default
  walk" holds.
- A directed revision must genuinely change the spec or 16's signature rule
  skips the re-sign-off (the revised fixture folds the note into `notes`).
- Autorun live-probe rig: `work/_skeleton/autorun.json` self-starts a run
  at boot; a kind-policy bot answers through the normal `handle_answer`
  path (journaled as ordinary resolutions); the shim auto-opens the panel
  on a pending marker (onStartupFinished; lifecycle-only). Never the demo
  path.
- Prompt-port lesson, on record: dropping the doc-normalizer's worked
  example broke live convergence for six straight passes (path-style
  coverage refs); restoring it plus the bare-token ref grammar and inline
  sibling-CSV header lines fixed convergence immediately. Battle-tested
  prompt furniture ports whole.

**Flagged forward:**

- To 20: the live adapter surfaced NO usage DataParts on this Mac -- the
  credit readout degraded honestly (no number from live turns); reconcile
  when the live wiring is exercised in the dev host. The dev-host window
  from the probe was left open on the user's machine. 20's "vendor the demo
  BRD" item is already done here (`demo/etl_studio/examples/`).
- To 21 (unchanged from 16): needs_human / exhaustion / owner_human cards
  and smoke-clean Approve remain webview renderer gaps; the live probe
  exercised needs_human over the wire only.
- Known rough edge: a steer arriving AFTER a code-gate revision reuses the
  cell-revise framing on the configurator's next pass (rig `_cell_revised`
  persists); content stays correct (cells preserved), framing only.

## Comments

2026-08-10 (first live session, user decision) -- Sibling discovery is
gone: the vendored exploder no longer scans the BRD's directory for CSVs.
That behavior was a vestige of the path-based Copilot world; the studio's
contract is ATTACHMENT, and scanning whatever shares a folder with a picked
file is a correctness and privacy hazard (a BRD in ~/Downloads would have
inventoried every unrelated CSV as candidate business data). The inventory
now carries exactly the attached data files (handle ids keep the
``sibling:<name>`` grammar, meaning "attached data file"); a BRD attached
without data runs honestly dataless. Smoke's BRD phase attaches the three
example CSVs like a real user.
