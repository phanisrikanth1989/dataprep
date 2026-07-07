# General ETL Pipeline Builder - Design

- **Date:** 2026-07-07
- **Branch:** `feature/copilot-etl-agents`
- **Status:** DRAFT - pending user sign-off, then writing-plans
- **Owner:** A Arun
- **Supersedes (framing):** the "recon / enrichment" framing of the agent system introduced in
  `2026-07-03-copilot-etl-agents-design.md` and `2026-07-03-enrichment-scope-correction.md`. Those
  remain as historical records (bannered); this design re-frames the *live* agent system as a
  general ETL pipeline builder.

---

## 1. Motivation

The DataPrep engine is a general Talend replacement (1200+ production jobs). The recon team is one
*consumer* of it, not the tool's *purpose*. The agent system was authored with a "recon", then
"enrichment", framing that artificially narrows what the agents will confidently build - e.g. a
"transform breaks -> aggregate -> email a report" job is not enrichment at all (no lookup join). This
design does three things:

1. **De-biases the agent system to general ETL** - sources -> transformations -> outputs, any of the
   ~86 engine components. No "recon" or "enrichment" framing anywhere in the live agent system.
2. **Makes the doc extraction lossless** - a deterministic parser scoped to four known blocks silently
   dropped any note, caveat, or non-template section a business analyst wrote, so a stated requirement
   could vanish before any LLM saw it (producing an opaque failure or, worse, a silently-wrong green
   job). The front door must capture everything.
3. **Closes the input/output materialization gap** - `extract_doc` produced JSON, the harness wanted
   CSVs + a manifest, and nothing bridged them (the one golden dir was hand-built). A deterministic
   `materialize_golden` step now creates the input + expected files from the doc, and the orchestrator
   runs the whole front door itself (no human pre-step).

## 2. Decisions (locked with the user)

- **Framing:** fully general ETL. Not "recon", not "enrichment". Vocabulary is *sources ->
  transformations -> outputs*; a lookup-join is "a join".
- **Skill rename:** `.github/skills/dataprep-recon/` -> `.github/skills/dataprep-etl/` (coordinated:
  folder + every agent's by-name reference + `render_skills.py` + tests).
- **Scope of de-bias:** the agent system only - `.github/agents/` (7 files), `.github/skills/`, and
  everything agent-facing under `agents/` (tools help text, `knowledge/landmines.py`, `templates/`,
  `schemas/config-surfaces.md` + `_validation_note` fields, `PLATFORM.md`, `examples/`). The engine
  (`src/`) and the historical specs/plans (`docs/superpowers/`, already bannered) are OUT of scope.
- **Lossless capture:** deterministic machine-copy for the exact data (schema/sample/expected);
  every note/prose/unrecognized section forwarded verbatim to the LLM; unknowns flagged, never
  dropped, never rejected.
- **Verification is 3-tier (dual-mode superset):** the harness grades where it can, smoke-tests where
  it can, and is honest where it can't (below).
- **Determinism boundary (the single principle):** the deterministic layer handles DATA (capture every
  section losslessly AND materialize the exact input/expected files); the LLM layer handles INTENT
  (interpret every section into the job). An LLM must never author or rewrite the test oracle.

## 3. The 3-tier verification model

| Doc contains        | Front door                          | Pipeline                                   | Human gate label            |
|---------------------|-------------------------------------|--------------------------------------------|-----------------------------|
| Sample + Expected   | extract -> materialize (in+exp+man) | build -> **run + diff** + self-correct loop | "verified"                  |
| Sample only         | extract -> materialize (inputs)     | build -> **run** (smoke: executes, output) | "smoke-tested, not graded"  |
| Neither             | extract                             | build `job.json` only, **no run**          | "unverified - not executed" |

All three tiers ALWAYS run: `surface_code_cells` (the security/code-review gate), the audit log, and
the human gate. Only the *grading* net varies, and the gate states the tier plainly - the system is
never allowed to imply a job was verified when it was not.

Required doc blocks drop from four to **two**: `Inputs and Schema` + `Transformation Rules`. `Sample
Input` and `Expected Output` are optional and select the tier. `Notes / Special Handling` is optional.

## 4. Component changes

### 4.1 `extract_doc` v2 (lossless)
- Keep the deterministic table-copy for `Inputs and Schema`, `Sample Input`, `Expected Output` (exact,
  reproducible - these become the oracle + input data).
- **Capture prose, not just tables:** paragraph text under any heading is captured (today only tables
  under a heading are read).
- **New fields on `ExtractResult`:** `notes` (str, from an optional `Notes / Special Handling` block)
  and `extra_sections` (dict: unrecognized H1 heading -> its text/tables). Nothing is discarded.
- **Conformance relaxes:** `REQUIRED_BLOCKS` = (`Inputs and Schema`, `Transformation Rules`). Missing
  `Sample Input`/`Expected Output` is NOT a failure - it sets the verification tier. An unrecognized
  section is a `ConformanceReport` warning (surfaced), never a rejection.
- `to_dict()` / the CLI emit the new fields.

### 4.2 `materialize_golden` (new, deterministic)
- New tool `agents/tools/materialize_golden.py` + CLI `python -m agents.tools.materialize_golden`.
- Input: `extract_doc.json` (+ target dir). Output, when present in the doc:
  - one input CSV per source (from `sample_input`) - the files the job reads;
  - one `<output>_expected.csv` per output (from `expected_output`) - the oracle;
  - `manifest.json` = `{"outputs": {<name>: {"keys": [...], "sep": ";"}}}`.
- **Deterministic only** (never the LLM): it writes the answer key and the input data.
- **Fixed CSV contract:** `;` separator, one header row - honored by BOTH the materializer and the
  configurator (documented in the skill).
- **Output -> component mapping** is NOT in the manifest (the component id only exists after assembly).
  The orchestrator/test-runner derives `output_map = {name: component_id}` from the assembled
  `job.json` at run time and passes it to the harness `check(...)`.
- Emits which tier it produced (inputs+expected / inputs-only / nothing) for the orchestrator to branch on.

### 4.3 `run_and_validate` - smoke tier
- Add a smoke mode (run the job, capture status + produced outputs, **no golden/diff required**) so the
  "Sample only" tier can execute a job and report that it ran cleanly and what it produced, without a
  pass/fail grade. The existing `--golden-dir` grade path is unchanged.

### 4.4 Orchestrator step-0 + tier branching
- Invoked with a **`.docx` path + a `<job>` name** (no `<GOLDEN_DIR>` from a human).
- First terminal commands: `extract_doc <docx> --out agents/work/<job>/extract_doc.json`, then
  `materialize_golden` into `agents/work/<job>/golden` (if `sample_input` present).
- Branch on the tier for the run step (grade / smoke / skip), and label the human gate accordingly.
- Everything else (the forward chain, the 3 safety nets, the 3-iteration repair budget) is unchanged
  in shape.

### 4.5 doc-interpreter consumes all intent
- Reads schema + rules + **`notes` + `extra_sections`**. Folds notes into rules/config; for anything
  it cannot confidently turn into a rule, it raises an entry on the existing `ambiguities` channel
  (-> human gate). Nothing is silently applied and nothing is silently dropped.

### 4.6 De-bias reframe (mechanical, system-wide)
- Skill folder rename + `render_skills.py` output paths/names + every agent's "consult the
  `dataprep-etl` skill" reference + `validate_agents`/tests that assert the skill name.
- 7 agent files: role framing "enrichment specialist / recon" -> neutral ETL stages.
- `knowledge/landmines.py`, `PLATFORM.md`, tool `--help`/docstrings, `examples/README.md`,
  `schemas/config-surfaces.md` + `_validation_note` fields: scrub "recon"/"enrichment" framing (keep
  the engine facts).
- `templates/recon_requirements_template.md` -> `templates/etl_requirements_template.md`; content
  de-biased and updated for the relaxed (2 required blocks) + optional `Notes` structure.

## 5. Updated pipeline data flow

```
  <job>.docx  +  <job> name
      │
  orchestrator (step 0, deterministic terminal commands)
      ├─ extract_doc      -> agents/work/<job>/extract_doc.json   (schema, rules, sample?, expected?, notes, extra_sections)
      └─ materialize_golden-> agents/work/<job>/golden/           (input CSVs, <out>_expected.csv?, manifest.json)   [if sample present]
      │
  forward chain (LLM specialists, unchanged shape)
      doc-interpreter -> flow-designer -> configurator -> assembler -> job.json
      │
  surface_code_cells gate (all tiers)  ──► human approves any code before it runs
      │
  run step (tier-dependent)
      tier=verified : run_and_validate --golden-dir ... --out test_report.json  (run + diff + loop)
      tier=smoke    : run_and_validate --smoke ...                              (run, no grade)
      tier=build    : (skip)
      │
  human gate: job.json + verification tier + surfaced code cells + open ambiguities + captured notes/extra_sections
```

## 6. Non-goals / out of scope

- No engine (`src/`) changes; the code-exec hardening backlog (A6/A8/A10) is unchanged and still
  engine-team-owned.
- No rewrite of historical specs/plans (`docs/superpowers/` pre-2026-07-07) - they stay bannered.
- No change to the converter (`src/converters/`).
- The `tests/fixtures/recon/` golden fixture (a test asset, outside the agent system) stays as-is; it
  is not agent-facing. (Rename optional, deferred.)

## 7. Risks / notes

- **Manifest/component mapping:** deriving `output_map` from `job.json` at run time assumes the
  assembler emits a discoverable output-component-per-flow; the plan must specify exactly how the
  orchestrator/test-runner reads it (e.g. by walking the flow whose `to` is a FileOutput* sink).
- **Smoke tier "success" is weak:** a job can run cleanly and still be wrong. The gate label must make
  this explicit; a smoke-tested job is never presented as correct.
- **Lossless notes vs. the oracle:** when a note implies a transform the Expected Output does not
  reflect, the verified tier will (correctly) fail and route it; when there is no expected data to
  catch it, it surfaces as an ambiguity at the gate - never silently applied.
- **Skill rename is coordinated:** a stale by-name reference to `dataprep-recon` in any agent breaks
  the skill lookup in Citi; `validate_agents`/a test must assert no `dataprep-recon` string remains.

## 8. Build process

design doc (this) -> `writing-plans` -> `subagent-driven-development` (opus everywhere) ->
end-of-plan adversarial review loop, per the established workflow.
