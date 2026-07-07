# General ETL Pipeline Builder - Design

- **Date:** 2026-07-07
- **Version:** v3 (hardened over two adversarial spec-review rounds: 3 Critical + 30 Important resolved)
- **Branch:** `feature/copilot-etl-agents`
- **Status:** DRAFT - pending user sign-off, then writing-plans
- **Owner:** A Arun
- **Supersedes (framing):** the "recon / enrichment" framing in `2026-07-03-copilot-etl-agents-design.md`
  and `2026-07-03-enrichment-scope-correction.md` (both stay as bannered historical records).

---

## 1. Motivation

The DataPrep engine is a general Talend replacement (1200+ production jobs). The recon team is one
*consumer*, not the tool's *purpose*. The "recon"/"enrichment" framing narrows what the agents will
confidently build. This design (1) de-biases the agent system to **general ETL** (sources ->
transformations -> outputs, any of the ~86 components), (2) makes doc extraction **lossless** (no
BA-authored note/section silently dropped, without ever letting an LLM rewrite the exact data), and
(3) closes the **input/output materialization gap** (a deterministic step creates the input + expected
files the harness needs, and the orchestrator runs the whole front door itself).

## 2. Decisions (locked)

- **Framing:** fully general ETL - not "recon", not "enrichment".
- **Skill rename:** `.github/skills/dataprep-recon/` -> `.github/skills/dataprep-etl/` (coordinated).
- **Scope of de-bias:** the agent system only - `.github/agents/`, `.github/skills/`, and everything
  agent-facing under `agents/`. Engine (`src/`) and historical specs (`docs/superpowers/`) OUT.
- **Lossless capture:** deterministic machine-copy for exact data; every note/prose to the LLM;
  unknowns flagged, never dropped/silently-rejected.
- **Determinism boundary (the principle):** deterministic layer = DATA (capture losslessly + materialize
  the exact input/expected files). LLM layer = INTENT. **An LLM never authors/rewrites the oracle or
  input data.**
- **Verification is 3-tier**, canonical tokens `verified | smoke | build` (used verbatim everywhere).

## 3. The 3-tier verification model

Tier is selected by **presence of the H1 heading**, never by parsed row count:

| Doc has (H1 present)               | Tier       | Pipeline                                  | Gate label                 |
|------------------------------------|------------|-------------------------------------------|----------------------------|
| Sample Input **+** Expected Output | `verified` | materialize -> run + diff + repair loop   | "verified"                 |
| Sample Input only                  | `smoke`    | materialize inputs -> run (no diff)       | "smoke: ran, not graded"   |
| neither (or Expected only)         | `build`    | build `job.json` only, no run             | "build-only: not executed" |

- **Expected present, no Sample** -> `build` + explicit warning (an oracle with no input cannot be run).
- **Malformed / unreadable** Sample or Expected block (present H1 but the tables cannot be parsed into a
  header + rows) -> **conformance ERROR (hard-stop)**, never a silent downgrade.
- **Declared-empty** is valid and distinct from malformed: an Expected-Output H2 with a header row but
  zero data rows means that output is `graded: false` (author declared it, chose not to grade it) - NOT
  a hard-stop.
- **Partial expected (multi-output):** each output carries `graded: true|false`. Overall tier is
  `verified` iff >=1 output is graded; the gate label states `verified (N/M outputs graded)`. Ungraded
  outputs are run but not diffed.

All tiers ALWAYS run: `surface_code_cells` + pre-exec human approval of any code cell **before any
in-process run (including a smoke run)**, the audit log, and the human gate. A `smoke`/`build` job is
never presented as correct. Required doc blocks: **`Inputs and Schema` + `Transformation Rules`** only;
`Sample Input`, `Expected Output`, `Notes / Special Handling` are optional.

## 4. Component changes

### 4.1 `extract_doc` v2 (lossless)
- Deterministic table-copy for `Inputs and Schema`, `Sample Input`, `Expected Output` (exact).
- **Capture prose** under any heading (today only tables are read).
- **New `ExtractResult` fields, all defaulted** (so existing constructors + test fakes keep working):
  `notes: str = ""`, `extra_sections: dict = {}`, `tier: str = "build"` (canonical token, computed from
  which optional H1s are present + parseable).
- **`extra_sections` is data-blind:** per unrecognized H1 it holds **prose text verbatim** (intent) and,
  for any TABLE, **only structural facts** (column names, row count, per-column null-rate/uniqueness) +
  a flag `"unrecognized table under '<h>' - review"`. Raw table cell values are NOT stored there and
  NOT forwarded to the LLM (same data-wall as sample/expected).
- **Conformance:** `REQUIRED_BLOCKS = ("Inputs and Schema", "Transformation Rules")`. The Sample/Expected
  empty-rows checks (extract_doc.py:218-221) are **REPLACED (not deleted)** by presence-gated checks: if
  a Sample/Expected H1 is **present but unparseable** -> conformance error; if **absent** -> it simply
  sets the tier (no error). This keeps a malformed-table detector alive (deleting 218-221 outright would
  re-open the silent-drop hole).
- `to_dict()` + the CLI emit `notes`, `extra_sections`, and `tier`.

### 4.2 `materialize_golden` (new, deterministic)
- New tool `agents/tools/materialize_golden.py` + CLI. Input: `extract_doc.json` + `<job>` work dir.
- **File placement (matches the harness's path anchoring):**
  - **input CSVs -> `agents/work/<job>/` (work-dir root = `job.json`'s parent)** - the harness anchors a
    relative `filepath: "x.csv"` to that root (run_and_validate.py:769, 320). Under `golden/` they'd be
    unreadable.
  - **`<output-name>_expected.csv` + `manifest.json` -> `agents/work/<job>/golden/`**.
- **Input file naming contract:** each input CSV is `<source-name>.csv` where `source-name` is the
  Sample-Input H2 (== the `Source` value in Inputs-and-Schema). The configurator authors each
  FileInputDelimited `filepath` as exactly `"<source-name>.csv"` (bare relative -> work-dir root). This
  is the input-side twin of the output contract in 4.4.
- **Manifest (NO `component`):** `{"outputs": {<name>: {"keys": [...], "sep": ";", "graded": bool}}}`.
- **CSV quoting (load-bearing - the engine defaults to QUOTE_NONE):** materialize writes RFC-4180
  double-quoted CSV, and the configurator **MUST set `csv_option: true` and `text_enclosure: "\""`** on
  every FileInputDelimited that reads a materialized source AND every terminal FileOutputDelimited the
  oracle reads back. Without this, `FileInputDelimited` reads with `csv.QUOTE_NONE`
  (file_input_delimited.py:380,413) and `FileOutputDelimited` writes unquoted (file_output_delimited.py:
  722), so any value containing `;`/quote/newline shifts columns and a correct job false-fails. The
  render_skills example + skill must show `csv_option: true`. (Documented in the skill CSV contract.)
- **Deterministic only** - it writes the answer key + input data; the LLM never touches it. Emits the tier.

### 4.3 `run_and_validate` - grade-path change + smoke mode
- **The `--golden-dir` grade path CHANGES** (v3 retracts any "unchanged" claim). Today `main()` does
  `output_map[name] = spec["component"]` (run_and_validate.py:765). It is rewritten to, per manifest
  output:
  - read `graded`; for `graded: true`, load `<name>_expected.csv`, set `keys` from the manifest, and set
    `output_map[name]` by finding the FileOutput component in the loaded `job.json` whose **id == name**
    (the Sec 4.4 contract); **diff only graded outputs**.
  - for `graded: false`, run but do not read an expected CSV or diff (no crash on a missing expected file).
  - if a `graded: true` output has no FileOutput component with a matching id, fail with a clear reason
    (not a KeyError).
  The manifest no longer carries `component`; `main()` derives the mapping deterministically from the
  manifest's `graded` flag + the job's component ids.
- **Smoke mode** (`--smoke`, no `--golden-dir`): calls `run_job_capture(job, work_dir)` **unchanged**
  (egress / nested-`tRunJob` / Swift-`config_file` / path-jail gates all still fire), then emits a
  distinct verdict `{"tier": "smoke", "ran_clean": bool, "status": ..., "produced_outputs": {...},
  "dropped_or_errored_components": [...]}` with **NO `passed` field**. `ran_clean` is true only if engine
  status is success AND no declared component was dropped or errored.
- De-bias runtime error/log strings ("the enrichment harness" -> "the ETL harness") - **strings only;
  the jail/egress/surfacing LOGIC + its tests are FROZEN** (Sec 4.6 carve-out).

### 4.4 Output-name plumbing + assembler/input contracts
- **Output-name plumbing:** the Expected-Output names (+ each output's `keys` and `graded` flag) flow
  through the artifact chain: `extract_doc.json` -> doc-interpreter carries them in
  `requirement_spec.json` -> flow-designer -> configurator -> `assembler`. Without this the assembler
  cannot know the output names to bind ids to.
- **Assembler name->sink contract:** the assembler sets each terminal FileOutput component's `id` equal
  to its Expected-Output name (output `enriched` -> component id `enriched`). This is the deterministic
  key `run_and_validate.main()` maps on. A validator/test asserts the assembler honors it.
- **Input contract (twin):** the configurator authors each FileInputDelimited `filepath` as
  `"<source-name>.csv"` matching the materialized input file names (4.2).
- **Orchestrator step-0:** invoked with `<docx path>` + `<job>`. First terminal commands:
  `extract_doc ... --out .../extract_doc.json`, then `materialize_golden` (inputs -> work-dir root,
  expected+manifest -> `golden/`) when Sample present. Branch on the emitted tier: `verified` ->
  `run_and_validate --golden-dir golden/ --out test_report.json` (run+diff+3-iter repair loop keyed on
  `passed`); `smoke` -> `run_and_validate --smoke` (distinct verdict, NO repair loop); `build` -> skip.
- **Human gate** presents: `job.json`, the tier (token + label), the graded/smoke verdict or "not
  executed", surfaced code cells, open `ambiguities`, and captured `notes` + `extra_sections`.

### 4.5 doc-interpreter consumes all intent
- Reads schema + rules + **`notes`** (verbatim) + `extra_sections` **flags/structural facts** (not raw
  values). Folds notes into rules/config; for anything it cannot confidently apply, raises an
  `ambiguities` entry (-> gate).
- **Note-derived rules are TAGGED** (`source: "note"` / `derived_from_note: true`) in
  `requirement_spec.json`. This makes the note-vs-oracle guard enforceable: in the `verified` tier the
  diagnostician must not "repair" a failure by dropping a note-tagged rule to force green; such a
  conflict routes to the human. In `smoke`/`build` the note surfaces at the gate.

### 4.6 De-bias reframe (system-wide; LOGIC-frozen on security files)
- **Skill rename + generated CONTENT:** rename the folder; `render_skills.py` de-biases the generated
  output too - `_SKILL_FRONTMATTER` description, the job-envelope prose, any recon/enrichment body text.
  Also update **`_JOB_ENVELOPE_EXAMPLE_JSON`**: neutral naming AND the terminal FileOutput `id` == the
  output name (teaching the 4.4 contract) AND `csv_option: true` on the delimited I/O (teaching 4.2).
  Update every agent's by-name `dataprep-etl` reference, the generator, and the tests.
- **7 agent files:** neutral ETL role framing; the assembler file states the id==name + csv_option
  contracts.
- **PLATFORM.md - rewrite operational sections:** "How to run" (docx + job name, no human GOLDEN_DIR),
  the pipeline diagram, and the tool table (add `materialize_golden`, the 3 tiers).
- **`knowledge/landmines.py`, tool `--help`/docstrings, `schemas/config-surfaces.md` + `_validation_note`
  fields:** scrub framing (keep engine facts).
- **`examples/`:** rename `sample_enrichment_requirements.docx` -> `sample_etl_requirements.docx`,
  neutralize its title/framing, update the README + generator script.
- **Security-file carve-out (hard rule, reconciles Decision 1):** on `surface_code_cells.py` and
  `run_and_validate.py`, de-bias is **comment/user-facing-string ONLY**; it touches **NO logic and NO
  test**. Decision 1's "no framing anywhere" is satisfied by the string scrub; the code-surfacing /
  path-jail / egress / nested-job logic and their tests stay byte-frozen.
- **`templates/recon_requirements_template.md` -> `templates/etl_requirements_template.md`:** de-biased
  content, updated for 2-required-blocks + optional `Notes` + the canonical tiers.

## 5. Updated pipeline data flow

```
  <job>.docx + <job> name
      │
  orchestrator step 0 (deterministic terminal commands)
      ├─ extract_doc        -> agents/work/<job>/extract_doc.json  (schema, rules, sample?, expected?, notes, extra_sections, tier)
      └─ materialize_golden -> agents/work/<job>/<source>.csv (ROOT)  +  golden/{<out>_expected.csv?, manifest.json}   [if Sample present]
      │
  forward chain  doc-interpreter -> flow-designer -> configurator -> assembler -> job.json
      │   (output names+keys+graded plumbed through; assembler: FileOutput id == output name; csv_option:true on delimited I/O)
      │
  surface_code_cells + pre-exec human approval of any code cell  (ALL tiers, before any run)
      │
  run step (by tier)
      verified : run_and_validate --golden-dir golden/ --out test_report.json   (diff only graded outputs; 3-iter repair loop on `passed`)
      smoke    : run_and_validate --smoke                                       (distinct verdict, NO `passed`, NO loop)
      build    : (skip)
      │
  human gate: job.json + tier(+label) + verdict/"not executed" + code cells + ambiguities + notes + extra_sections
```

## 6. Scope: touched vs frozen

- **Touched (agent system):** `.github/agents/` (7), `.github/skills/` (renamed), `agents/tools/*`
  (extract_doc, run_and_validate, new materialize_golden, render_skills, validate_agents),
  `agents/knowledge/landmines.py`, `agents/templates/*`, `agents/schemas/config-surfaces.md`,
  `agents/PLATFORM.md`, `agents/examples/*`, and their tests.
- **Golden fixture MIGRATES (content, not just the dir name):** because the grade path changes,
  `tests/fixtures/recon/golden_enrichment/job.json`'s terminal FileOutput id is renamed
  `out_enriched` -> `enriched`, its `manifest.json` drops `component`, and the oracle CLI/e2e tests
  (`test_oracle.py::_write_cli_case`, `test_golden_enrichment_e2e.py::_output_map_and_keys`) are updated
  to the new contract. "`tests/fixtures/recon/` stays; rename deferred" means the **directory name**
  only, NOT frozen content.
- **Frozen / out of scope:** engine (`src/`), converter (`src/converters/`), historical specs/plans
  (`docs/superpowers/` pre-2026-07-07), and the security LOGIC + tests per the 4.6 carve-out.

## 7. Risks / notes

- **Two load-bearing contracts** (FileOutput id == output name; `filepath` == `<source-name>.csv`): both
  need a validator/test, and `run_and_validate.main()` must fail with a clear reason (not a KeyError) on
  a mismatch.
- **CSV quoting is the subtle one:** the guarantee only holds if `csv_option: true` is set on both
  sides; the plan must add a configurator rule + a test proving a value with an embedded `;` round-trips.
- **Smoke `ran_clean` is weak** (a job can run and still be wrong) - the gate label makes this explicit.
- **Note-vs-oracle:** guarded by the note tag (4.5); never silently repaired.
- **Skill rename is coordinated:** a test must assert no `dataprep-recon` string remains in the agent system.

## 8. Build process

design doc (this) -> `writing-plans` -> `subagent-driven-development` (opus everywhere) ->
end-of-plan adversarial review loop.
