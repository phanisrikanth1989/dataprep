# General ETL Pipeline Builder - Design

- **Date:** 2026-07-07
- **Version:** v2 (hardened after an adversarial spec review - 3 Critical + 14 Important resolved)
- **Branch:** `feature/copilot-etl-agents`
- **Status:** DRAFT - pending user sign-off, then writing-plans
- **Owner:** A Arun
- **Supersedes (framing):** the "recon / enrichment" framing of the agent system introduced in
  `2026-07-03-copilot-etl-agents-design.md` and `2026-07-03-enrichment-scope-correction.md` (both stay
  as bannered historical records). This design re-frames the *live* agent system as a general ETL
  pipeline builder.

---

## 1. Motivation

The DataPrep engine is a general Talend replacement (1200+ production jobs). The recon team is one
*consumer*, not the tool's *purpose*. The agent system was authored with a "recon", then "enrichment",
framing that narrows what the agents will confidently build (a "transform breaks -> aggregate -> email
a report" job is not enrichment - no lookup join). This design:

1. **De-biases the agent system to general ETL** - *sources -> transformations -> outputs*, any of the
   ~86 engine components. No "recon"/"enrichment" framing anywhere in the live agent system.
2. **Makes doc extraction lossless** - the deterministic parser dropped any note/caveat/non-template
   section a business analyst wrote, so a stated requirement could vanish before any LLM saw it. The
   front door must capture everything, without ever letting an LLM rewrite the exact data.
3. **Closes the input/output materialization gap** - `extract_doc` produced JSON, the harness wanted
   CSVs + a manifest, and nothing bridged them. A deterministic `materialize_golden` step creates them,
   and the orchestrator runs the whole front door itself.

## 2. Decisions (locked with the user)

- **Framing:** fully general ETL - not "recon", not "enrichment".
- **Skill rename:** `.github/skills/dataprep-recon/` -> `.github/skills/dataprep-etl/` (coordinated).
- **Scope of de-bias:** the agent system only - `.github/agents/` (7 files), `.github/skills/`, and
  everything agent-facing under `agents/`. The engine (`src/`) and historical specs/plans
  (`docs/superpowers/`) are OUT of scope.
- **Lossless capture:** deterministic machine-copy for the exact data; every note/prose forwarded to
  the LLM; unknowns flagged, never dropped, never silently rejected.
- **Verification is 3-tier** (canonical tokens below).
- **Determinism boundary (the single principle):** the deterministic layer handles DATA (capture every
  section losslessly AND materialize the exact input/expected files). The LLM layer handles INTENT
  (interpret every section into the job). **An LLM never authors or rewrites the test oracle or the
  input data.**

## 3. The 3-tier verification model

**Canonical tier tokens (used verbatim everywhere - tool output, orchestrator, gate): `verified`,
`smoke`, `build`.**

Tier is selected by the **presence of the H1 heading**, never by parsed row count:

| Doc has (H1 present)      | Tier       | Pipeline                                            | Gate label                    |
|---------------------------|------------|-----------------------------------------------------|-------------------------------|
| Sample Input **+** Expected Output | `verified` | materialize -> **run + diff** + self-correct loop   | "verified"                    |
| Sample Input only         | `smoke`    | materialize inputs -> **run** (no diff)             | "smoke: ran, not graded"      |
| neither (or Expected only)| `build`    | build `job.json` only, **no run**                   | "build-only: not executed"    |

- **`Expected Output` present but no `Sample Input`** -> `build` tier + an explicit warning (an oracle
  with no input to run against cannot be graded).
- **Present-but-unparseable** (a Sample/Expected H1 is present but its tables yield zero rows / are
  malformed) is a **conformance ERROR (hard-stop)**, NOT a silent downgrade - the author clearly
  intended to test, so a parse failure must surface, not quietly drop a tier.
- **Partial expected (multi-output):** the manifest marks each output `graded: true|false`; the tier is
  `verified` only if at least one output is graded, and the gate label states `verified (N/M outputs
  graded)`. Ungraded outputs are run but not diffed.

All three tiers ALWAYS run: `surface_code_cells` + the pre-exec human approval of any code cell (before
ANY in-process run, including a smoke run), the audit log, and the human gate. Only the *grading* net
varies, and the gate states the tier plainly. **A `smoke` or `build` job is never presented as
correct.**

Required doc blocks drop from four to **two**: `Inputs and Schema` + `Transformation Rules`. `Sample
Input`, `Expected Output`, and `Notes / Special Handling` are optional.

## 4. Component changes

### 4.1 `extract_doc` v2 (lossless)
- Keep deterministic table-copy for `Inputs and Schema`, `Sample Input`, `Expected Output` (exact,
  reproducible - the oracle + input data).
- **Capture prose:** paragraph text under any heading is captured (today only tables are read).
- **New `ExtractResult` fields with safe defaults** (so every existing constructor + test fake keeps
  working): `notes: str = ""` (from an optional `Notes / Special Handling` block) and
  `extra_sections: dict = {}` (unrecognized H1 -> its content).
- **Data-wall preserved for unknown TABLES:** prose/notes are forwarded to the LLM verbatim (intent);
  but a TABLE under an unrecognized heading is treated as possible mislabeled data - it is captured
  **locally** as structural facts + flagged `"unrecognized table under '<heading>' - review"`, and its
  raw cell values are NOT forwarded to the doc-interpreter. (Same data-blindness rule that walls
  sample/expected values.)
- **Conformance relaxes:** `REQUIRED_BLOCKS = ("Inputs and Schema", "Transformation Rules")`. The
  `sample_input`/`expected_output` **empty-rows checks in `_check_conformance` (extract_doc.py:218-221)
  are removed** - absence sets the tier; a present-but-unparseable block is the only Sample/Expected
  failure (see Sec 3). Unrecognized sections are a surfaced warning, never a rejection.
- `to_dict()` + the CLI emit the new fields and the selected `tier`.

### 4.2 `materialize_golden` (new, deterministic)
- New tool `agents/tools/materialize_golden.py` + CLI. Input: `extract_doc.json` + `<job>` work dir.
- **File placement (critical - matches how the harness anchors paths):**
  - **input CSVs -> `agents/work/<job>/` (the work-dir root = `job.json`'s parent)**, because
    `run_job_capture(job, Path(args.job).parent)` anchors a relative `filepath: "source.csv"` to that
    root (run_and_validate.py:769, 320, 409-416). Placing them under `golden/` would make
    `FileInputDelimited` read a missing file.
  - **`<output>_expected.csv` + `manifest.json` -> `agents/work/<job>/golden/`** (the read-only oracle).
- **Manifest shape (NO `component`):** `{"outputs": {<name>: {"keys": [...], "sep": ";", "graded":
  bool}}}`. The name is the doc's Expected-Output H2. `graded` is false for an output with no expected
  table.
- **CSV contract (deterministic oracle):** `;` separator, one header row, and **RFC-4180 quoting** (a
  field containing the separator, a quote, or a newline is double-quoted / escaped) so a value can never
  corrupt the layout. Honored by BOTH the materializer and the configurator (documented in the skill).
- **Deterministic only** - it writes the answer key and the input data; the LLM never touches it.
- Emits the selected tier for the orchestrator to branch on.

### 4.3 `run_and_validate` - grade-path change + smoke mode
- **The `--golden-dir` grade path CHANGES (Sec 4.3 explicitly retracts any "unchanged" claim).**
  `main()` currently does `output_map[name] = spec["component"]` (run_and_validate.py:765). It is
  modified to **derive `output_map = {name: component_id}` from the `job.json` it already loads**
  (run_and_validate.py:749) using the assembler name->sink contract (Sec 4.4), and to stop reading
  `spec["component"]`. The manifest no longer carries `component`.
- **Smoke mode** (`--smoke`, no `--golden-dir`): calls `run_job_capture(job, work_dir)` **unchanged** -
  so the egress / nested-`tRunJob` / Swift-`config_file` / path-jail fail-closed gates all still fire -
  then reports a **distinct** verdict object: `{"tier": "smoke", "ran_clean": bool, "status": ...,
  "produced_outputs": {...}, "dropped_or_errored_components": [...]}`. It **does NOT emit a `passed`
  field** (so the orchestrator's `passed`-driven repair loop can never mistake a smoke run for a graded
  pass). `ran_clean` is true only if the engine status is success AND no declared component was dropped
  or errored.
- De-bias the runtime error/log strings (e.g. "the enrichment harness" -> "the ETL harness") - they are
  surfaced to users. **Do not touch the jail/egress/surfacing LOGIC** (strings only - see 4.6).

### 4.4 Orchestrator step-0, assembler contract, tier branching
- **Assembler name->sink contract (makes the mapping deterministic for multi-output):** the assembler
  MUST set each terminal FileOutput component's `id` equal to the corresponding Expected-Output name
  from the doc (e.g. output `enriched` -> component id `enriched`). `run_and_validate.main()` then maps
  `output_map[name] = name` by confirming a FileOutput component with that id feeds the output. This is
  a stated contract, not a heuristic sink-walk.
- **Orchestrator invoked with `<docx path>` + `<job>`** (no human-provided GOLDEN_DIR). First terminal
  commands: `extract_doc <docx> --out agents/work/<job>/extract_doc.json`, then `materialize_golden`
  (inputs -> work-dir root, expected+manifest -> `golden/`) when `Sample Input` is present.
- **Branch on the emitted tier:** `verified` -> `run_and_validate --golden-dir golden/ --out
  test_report.json` (run+diff+repair loop, keyed on `passed`); `smoke` -> `run_and_validate --smoke`
  (distinct verdict, NO repair loop - one run then gate); `build` -> skip the run. The `passed`-driven
  3-iteration repair loop exists ONLY in the `verified` tier; `smoke`/`build` go straight to the gate
  after one run / after build.
- **Human gate** presents: `job.json`, the **tier** (verbatim token + label), the graded verdict or the
  smoke verdict or "not executed", the surfaced code cells, the open `ambiguities`, AND the captured
  `notes` + `extra_sections` (so a dropped-into-notes requirement is visible before sign-off).

### 4.5 doc-interpreter consumes all intent
- Reads schema + rules + **`notes`** (verbatim) + the `extra_sections` **flags/structural facts** (not
  raw table values). Folds notes into rules/config; for anything it cannot confidently turn into a rule
  it raises an `ambiguities` entry (-> human gate). Nothing is silently applied or dropped.
- **Note-vs-oracle guard:** in the `verified` tier the diagnostician must never "repair" a failure by
  dropping a note-derived requirement to make the harness green; a conflict between a note-derived
  transform and the Expected Output is routed to the human, not silently reconciled.

### 4.6 De-bias reframe (system-wide, LOGIC-frozen on security files)
- **Skill rename + generated content:** rename the folder; `render_skills.py` must de-bias the
  **generated CONTENT too** - `_SKILL_FRONTMATTER` description, the job-envelope prose, any
  "enrichment"/"recon" body text - not just output paths/names. Update every agent's by-name
  `dataprep-etl` reference, the generator, and the tests.
- **7 agent files:** role framing "enrichment specialist / recon" -> neutral ETL stages.
- **PLATFORM.md - rewrite the operational sections, not just scrub words:** the "How to run" invocation
  (docx + job name, no human GOLDEN_DIR), the pipeline diagram, and the tool table (add
  `materialize_golden`, the 3 tiers, the orchestrator-runs-extract flow).
- **`knowledge/landmines.py`, tool `--help`/docstrings, `schemas/config-surfaces.md` + `_validation_note`
  fields:** scrub framing (keep engine facts).
- **`examples/`:** rename `sample_enrichment_requirements.docx` -> `sample_etl_requirements.docx` and
  neutralize its title/framing (the settlements scenario stays as one concrete example); update the
  README and the generator script.
- **Security-file carve-out (hard rule):** when de-biasing `surface_code_cells.py` and
  `run_and_validate.py`, change **only user-facing strings**; the code-surfacing, path-jail, egress,
  and nested-job LOGIC and their tests are FROZEN (they survived 6 hardening passes).
- **`templates/recon_requirements_template.md` -> `templates/etl_requirements_template.md`:** de-biased
  content, updated for the 2-required-blocks + optional `Notes` structure + the canonical tier note.

## 5. Updated pipeline data flow

```
  <job>.docx  +  <job> name
      │
  orchestrator (step 0, deterministic terminal commands)
      ├─ extract_doc       -> agents/work/<job>/extract_doc.json   (schema, rules, sample?, expected?, notes, extra_sections, tier)
      └─ materialize_golden -> agents/work/<job>/{source csvs at ROOT}  +  golden/{<out>_expected.csv?, manifest.json}   [if Sample present]
      │
  forward chain (LLM specialists)  doc-interpreter -> flow-designer -> configurator -> assembler -> job.json
      │      (assembler: FileOutput component id == Expected-Output name)
      │
  surface_code_cells + pre-exec human approval of any code cell  (ALL tiers, before any run)
      │
  run step (by tier)
      verified : run_and_validate --golden-dir golden/ --out test_report.json   (run + diff + 3-iter repair loop on `passed`)
      smoke    : run_and_validate --smoke                                       (run, distinct verdict, NO `passed`, NO loop)
      build    : (skip)
      │
  human gate: job.json + tier(+label) + verdict-or-"not executed" + code cells + ambiguities + notes + extra_sections
```

## 6. Non-goals / out of scope

- No engine (`src/`) changes; the code-exec hardening backlog (A6/A8/A10) is unchanged, engine-team-owned.
- No rewrite of historical specs/plans (`docs/superpowers/` pre-2026-07-07) - they stay bannered.
- No converter (`src/converters/`) change.
- `tests/fixtures/recon/` (a test asset, not agent-facing) stays; rename deferred.

## 7. Risks / notes

- **Assembler contract is load-bearing:** the whole grade mapping rests on "FileOutput component id ==
  Expected-Output name". The plan must add a validator/test that the assembler honors it, and
  `run_and_validate.main()` must fail with a clear reason (not a KeyError) if an expected output has no
  matching FileOutput component.
- **Smoke `ran_clean` is a weak signal:** a job can run cleanly and still be wrong. The gate label makes
  this explicit; a smoke job is never presented as correct.
- **Note-vs-oracle in the verified tier:** guarded by 4.5 (no silent repair-away); in `smoke`/`build`
  it surfaces as an ambiguity/note at the gate.
- **Skill rename is coordinated:** a stale `dataprep-recon` reference breaks the skill lookup in Citi;
  a test must assert no `dataprep-recon` string remains in the agent system.
- **Tier vocabulary:** exactly one enum (`verified|smoke|build`) - no synonyms in any artifact.

## 8. Build process

design doc (this) -> `writing-plans` -> `subagent-driven-development` (opus everywhere) ->
end-of-plan adversarial review loop, per the established workflow.
