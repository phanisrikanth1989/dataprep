---
phase: 14
slug: coverage-push-to-95-per-module-floor
plan: phase-summary
type: execute
status: ready
created: 2026-05-10
requirements: [TEST-11, TEST-12]
---

# Phase 14 -- Coverage Push to 95% per-module floor (Phase Plan)

> Roll-up across all 12 plans. Each individual plan lives in `14-NN-*.md` files. Read `14-CONTEXT.md`, `14-RESEARCH.md`, `14-VALIDATION.md`, and `13-COVERAGE-BASELINE.md` before executing any plan.

## Phase Objective

Lift every module under `src/v1/engine/` and `src/converters/` (excluding legacy `complex_converter`) from the Phase 13 baseline (53 modules below 95%) to a uniform >=95% line-coverage floor. Build the shared pipeline-test infrastructure (root `tests/conftest.py`, `tests/fixtures/jobs/`, per-module floor enforcement script). Produce final `14-COVERAGE.md` and a paste-runnable gate command. No new product features -- pure stabilization of test surface. No CI workflow file (D-E1).

## Goal-Backward Truths

1. Running `rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html --cov-report=json && python scripts/check_per_module_coverage.py coverage.json --floor 95` from project root exits zero.
2. Every in-scope module (198 total minus `complex_converter`) reports >=95% line coverage in the resulting `coverage.json`.
3. No module currently >=95% has regressed below 95%.
4. `14-COVERAGE.md` exists with the final per-module table; `13-COVERAGE-BASELINE.md` stays archived.
5. CLAUDE.md "Coverage" section documents the gate command.
6. REQUIREMENTS.md lists TEST-11 and TEST-12 with status `Complete`; ROADMAP.md Phase 14 SC#2 reflects the paste-runnable gate (D-E1 amendment).
7. No new `# pragma: no cover` annotations exist outside the D-C3 allowlist (`__main__`, `@abstractmethod`, `ImportError` shims). The single existing pragma at `src/v1/engine/components/file/file_output_delimited.py:364` is resolved via D-C5 (delete or cover).

## Plan Inventory (12 plans, ordered by execution wave)

| Plan | Title | Wave | Depends on | Modules / files | Est. commits |
|------|-------|-----:|-------------|-----------------|-------------:|
| 14-01 | Pipeline-test infrastructure | 0 | -- | root conftest, fixture-jobs scaffolding, pyproject coverage config, xdist pin, floor script | 6 |
| 14-02 | engine.components.aggregate | 1 | 14-01 | `aggregate_row.py` (79->95) | 2 |
| 14-03 | engine.components.control | 1 | 14-01 | `send_mail.py` (60->95) | 2 |
| 14-04 | engine.components.database | 1 | 14-01 | `oracle_output.py` (94->95), `oracle_row.py` (90->95) | 3 |
| 14-05 | engine.components.transform -- quick wins + medium | 1 | 14-01 | 12 modules, replace through filter_rows | 13 |
| 14-06 | engine.components.transform -- deep gaps non-SWIFT | 2 | 14-01 | `map.py`, `join.py`, `python_dataframe_component.py` | 4 |
| 14-07 | engine.components.transform -- SWIFT | 2 | 14-01 | `swift_transformer.py` (7->95), `swift_block_formatter.py` (7->95), synthetic generator | 8 |
| 14-08 | engine.components.file -- quick wins + medium | 1 | 14-01 | 12 modules; resolves dead-code pragma at `file_output_delimited.py:364` | 13 |
| 14-09 | engine.components.file -- deep gaps | 2 | 14-01 | `file_output_excel.py`, `file_input_excel.py`, `file_input_json.py`, `file_input_raw.py`; real .xlsx/.csv/.json fixtures | 8 |
| 14-10 | engine core | 2 | 14-01 | `trigger_manager.py`, `executor.py`, `base_iterate_component.py`, `base_component.py`, `python_routine_manager.py`, `engine.py`, `java_bridge_manager.py` (`-m java`) | 9 |
| 14-11 | converters | 1 | 14-01 | `converter.py`, `expression_converter.py`, `xml_map.py`, `replace.py`, `aggregate_row.py`, `foreach.py`, `file_input_excel.py`, `mssql_input.py` | 9 |
| 14-12 | closeout | 3 | all of 14-02..14-11 | `14-COVERAGE.md`, CLAUDE.md update, REQUIREMENTS.md, ROADMAP.md, STATE.md, `14-VERIFICATION.md`, `14-PHASE-SUMMARY.md`, `coverage.json` commit, no-regression check (incl. iterate/context) | 7 |

**Total estimated commits:** ~84.

## Wave Structure (cross-plan)

- **Wave 0:** Plan 14-01 ships the pipeline-test infrastructure. All other plans block on 14-01.
- **Wave 1:** Quick wins + medium gaps (14-02, 14-03, 14-04, 14-05, 14-08, 14-11). Run in parallel when executor capacity allows.
- **Wave 2:** Deep gaps (14-06, 14-07, 14-09, 14-10). Higher per-task context cost; do not parallelize 14-07 with 14-09 if the same fixture-jobs subdirectory is touched (verify via `files_modified`).
- **Wave 3:** Closeout (14-12). Depends on every prior plan.

## Cross-Cutting Constraints (apply to every plan)

1. **No new product features.** Test-only phase. If a test surfaces a real bug, patch source root-cause (Phase 13 D-B1..B4 precedent), document under `BUG-...` commit, do NOT add defensive shims.
2. **No xfail markers added.** Unstable test = fix or delete.
3. **pandas 3.0.1 with CoW** -- tests must use realistic dtypes (StringDtype, Int64, datetime64, Decimal). Use `pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)` for string detection (Phase 13 D-B2 canonical pattern). Never `inplace=True` -- always rebind.
4. **ASCII-only logs** -- enforced via `assert_ascii_logs` fixture from Plan 14-01. No emoji or unicode in source, tests, or log output.
5. **Custom exception hierarchy** -- always `pytest.raises(ConfigurationError)` etc., never `pytest.raises(Exception)`.
6. **Pragma allowlist** (D-C3): only `__main__`, `@abstractmethod`, `ImportError` shims. Anything else = reject in review or apply D-C5.
7. **Atomic commits** -- one test file or fixture file per commit. Mirror Phase 13 D-F2.
8. **Plan filenames** follow `{NN}-PLAN.md` shape -- here `14-NN-{slug}.md` (e.g. `14-01-pipeline-test-infrastructure.md`). Padded NN.
9. **Pipeline tests load JSON from `tests/fixtures/jobs/{subsystem}/{behavior}.json`** -- use the `run_job_fixture` from Plan 14-01. Format mirrors converter output (D-C2).
10. **Per-task verification command** -- every task gates on `pytest <touched test file> -q` AND, at end of plan, the per-module floor script for that plan's modules.

## Final Verification Gate (closeout, Plan 14-12)

```bash
# From project root. Requires JVM 11+ on PATH for -m java tests (D-A3).
rm -f .coverage* && python -m pytest tests/ \
  -m "not oracle" \
  -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected outcome:
- Exit code 0
- Stdout: `PASS: all <N> in-scope modules at >= 95.0% line coverage`
- `htmlcov/index.html` regenerated (gitignored)
- `coverage.json` regenerated and committed at `.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json` (locked Q4)

## Open Issues for Plan-Checker

1. **Module count drift (RESEARCH §A1):** baseline FAIL row strict-grep says 52, CONTEXT.md says 53. Final closeout enumerates from `coverage.json`; the off-by-one does not constrain execution.
2. **SWIFT YAML shape iteration (RESEARCH §A3):** Plan 14-07 may discover additional YAML keys during synthesis. Plan-checker should accept iteration on fixture shape during execution.
3. **xdist + cov smoke (RESEARCH §A4):** Plan 14-01 includes a smoke-validation task to confirm parallel coverage matches serial coverage on one test file. If discrepancy, Plan 14-01 falls back to serial gate (subject to user override).
4. **java_bridge_manager retry branch test approach (RESEARCH §A6):** Plan 14-10 may need to monkey-patch `JavaBridge.start` to seed "Address already in use"; that's still a real-bridge-style test (the module under test is `java_bridge_manager.py`, not `bridge.py`). Acceptable.
5. **Dead-code pragma at `file_output_delimited.py:364` (RESEARCH §A7):** Plan 14-08 reviewer decides delete vs cover vs allowlisted (likely delete per "rewrite over patch"). Document outcome in plan summary.
6. **TEST-11 / TEST-12 final wording:** the wording proposed in this set follows RESEARCH.md §phase_requirements; user signed off via the `additional_context` for this planner run. Closeout flips both to Complete in REQUIREMENTS.md.

---
*Phase 14 plan summary -- gathered 2026-05-10 -- ready for execution post-approval*
