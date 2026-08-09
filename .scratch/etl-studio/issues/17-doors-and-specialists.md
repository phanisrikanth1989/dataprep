# 17 - Doors and specialists

Status: open
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
