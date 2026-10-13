# 11 - Engine knowledge in the owned runtime

Status: resolved
Type: grilling

## Question

How do the rebuilt/vendored specialists receive the engine knowledge that the
Copilot world served as the `dataprep-etl` Agent Skill -- `config-reference.md`
(resolved enums), `landmines.md`, `job-envelope.md`, and the SKILL index --
now that there is no skill auto-load?

To settle:

- Injection mechanism: per-stage system prompts assembled by the core,
  on-demand file reads via a tool, or both.
- Which stage gets which slice (flow-designer vs configurator vs assembler vs
  diagnostician need different cuts; oversized prompts burn credits).
- Freshness: `render_skills` code-generates the knowledge from live schemas --
  when does the owned runtime regenerate, and what guards drift?
- Where the rendered knowledge lives under `demo/etl_studio/` (vendored copy
  vs generated at build/startup).

(Graduated from the "how rebuilt agents receive the engine knowledge" fog by
ticket 04's stage roster.)

## Answer

Resolved 2026-08-09 via grilling (parallel session while ticket 10 ran).
Terms recorded in root `CONTEXT.md`.

**Content posture.** Fit-adaptation + reactive fixes only, and only in the
knowledge sources -- the curated schemas (12 components today), the landmine
registry, and the renderer's authored prose, all vendored under
`demo/etl_studio/`. Rendered output is never hand-edited: a wrong rendered
artifact indicts its source. Substantive enrichment (more components, deeper
coverage) is deliberately deferred to ticket 14. Corpus = all four resource
files (patterns.md included) plus `config-surfaces.md` served to the
diagnostician; PLATFORM.md, templates and examples are not engine knowledge.

**Injection mechanism.** Inline-primary hybrid, assembled by the core's
prompt builder:

- Each stage's knowledge slice is always in-prompt -- deterministic: every
  call provably carries its knowledge, identically in rehearsal and live.
- A knowledge read tool covers the long tail only (config-surfaces for the
  diagnostician; catalog detail lookups when the catalog grows).
- Slice legality rule: a slice is the whole artifact, a field projection
  (e.g. id+summary), or a component-filtered subset keyed on source metadata
  (the landmine `component` field) -- NEVER an editorial hand-pick. Nobody
  selects entries; filters do.
- Engine source (`src/v1`, read-only) is mounted for exactly one stage: the
  diagnostician. Enforcement is tool-registry absence for everyone else, not
  prompt admonition. config-surfaces' file:line anchors become live pointers
  for it -- targeted hops, not spelunking. Source-level truth reaches the
  human through one door: feedback.json evidence.
- SKILL.md retires; its routing job becomes the core's slice map.

**Slice matrix** (today at 12 components; "flow-scoped" = mechanical
component filter once flow_design.json exists):

| Stage | Inline | Tool surface |
|---|---|---|
| doc-normalizer | full landmines | -- |
| interpreter | full landmines | data files (04) |
| flow-designer | patterns + full reference + full landmines + envelope wiring prose | knowledge detail (at scale) |
| configurator | flow-scoped reference + flow-scoped landmines + envelope schema section | -- |
| assembler | envelope (worked example) + landmines (flow-scoped) | -- |
| diagnostician | flow-scoped landmines WITH code anchors + envelope + flow-scoped reference | work dir (04), src/v1 (read-only), config-surfaces |
| orchestrator | patterns + envelope prose + landmine summaries (field projection) | run artifacts (05) |

Scale invariant: **inline what is O(job), tool-read what is O(catalog)** --
post-flow stages' inline cost is bounded by the job's component count at any
catalog size. The flow-designer is the one O(catalog) stage; its growth path
(catalog one-liner summary inline + key-level detail via tool) is a designed
seam, built when the catalog actually grows (ticket 14 territory). Pre-flow
stages (normalizer, interpreter) can't flow-scope; their scaling seam is left
open deliberately -- full file today at ~1.4k tokens.

**Freshness.** Dissolved by construction: rendering happens at every core
startup from the vendored sources; nothing rendered is tracked, so there is
no stale artifact and nothing to regenerate on a schedule. The existing
enum-ref drift check and fixture-consistency tests ride along with the
vendored sources.

**Location.** Sources vendored under `demo/etl_studio/`; rendered at startup
into a gitignored knowledge dir (inspectable per run -- artifact-bus spirit);
the prompt builder and the diagnostician's read tool consume the same render.

**Prompt-port policy (three tiers).** (1) Near-verbatim: flow-designer,
configurator, assembler -- forced changes are mechanical only (knowledge
sentences become "included below", subagent/terminal mechanics become core
tools). (2) Ported through the 02/04 structural rewrites: doc-normalizer
(purity/template references die, needs_human routes to the question channel)
and doc-interpreter-as-interpreter (serves both doors from intake.json,
ambiguities become gap objects, carries the elicitation loop and sign-off).
Battle-tested engine wisdom ports word-for-word in both. (3) Authored fresh:
diagnostician (04's value-visible rebuild) and orchestrator (05's narrator
under the code conductor); test-runner has no prompt -- it is code.

**Fit-pass work items produced:** restore code anchors in the diagnostician's
landmine rendering (render_landmines drops them today); component-filtered /
field-projection render functions; retire the index into the slice map; port
the knowledge-reference sentences per the tier policy.

**Accepted cost, eyes open:** with specialists banned from source, a failure
rooted in an engine subtlety the knowledge lacks reaches the repair owner
only through feedback.json -- its quality carries more load under this
policy. The reactive-fix path (enrich the source, regenerate) is the relief
valve.
