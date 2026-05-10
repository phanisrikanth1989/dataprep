---
phase: 14
plan: 02
slug: engine-aggregate
type: execute
wave: 1
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/aggregate/test_aggregate_row.py
  - src/v1/engine/components/aggregate/aggregate_row.py  # only if BUG surfaces
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "src/v1/engine/components/aggregate/aggregate_row.py reports >= 95% line coverage"
    - "Existing aggregate_row tests still pass"
    - "All raises assertions use ETLError-subclass exceptions, not generic Exception"
  artifacts:
    - path: tests/v1/engine/components/aggregate/test_aggregate_row.py
      provides: extended coverage of list_object/union/population_std_dev, Decimal handling, financial precision toggle, column collision in grouped mode
  key_links:
    - from: tests/v1/engine/components/aggregate/test_aggregate_row.py
      to: src/v1/engine/components/aggregate/aggregate_row.py
      via: direct _process() unit tests with realistic-shape DataFrames
---

<objective>
Lift `src/v1/engine/components/aggregate/aggregate_row.py` from 79% (203 stmts, 43 missed) to >= 95% line coverage. Pure-pandas transform -- D-C1 says direct `_process()` unit tests, not pipeline tests. Realistic dtypes (Int64, Decimal, datetime64, StringDtype) per D-C4. Existing test file is rich (Phase 6 + 7.1 + 13); this plan extends it to cover the remaining branches.
</objective>

<scope>
- MODIFIED: `tests/v1/engine/components/aggregate/test_aggregate_row.py` -- add tests for the missed-line clusters identified in RESEARCH §Module Triage:
    1. `list_object` aggregation function (returns Python list, not stringified -- AGGR-04)
    2. `union` aggregation function (deduplicates, AGGR-04)
    3. `population_std_dev` aggregation function (AGGR-04)
    4. `ignore_null` per-aggregation behavior (AGGR-03) -- positive + negative cases
    5. Decimal handling in grouped mode (AGGR-06) -- precision preservation across group-by
    6. Financial precision toggle for numeric aggregations (AGGR-07)
    7. Column collision in grouped mode (AGGR-08) -- group-by column name collides with output_column
    8. `output_column` config in grouped mode (AGGR-02) -- using configured name vs default
- POSSIBLY MODIFIED: `src/v1/engine/components/aggregate/aggregate_row.py` -- only if a real bug surfaces during test writing. If bug, patch root cause per Phase 13 D-B1..B4 precedent and add a `BUG-AGG-NN` commit. No defensive shims.
</scope>

<out_of_scope>
- Pipeline tests for aggregate_row (D-C1: pure-pandas transform = unit-test only).
- aggregate_sorted_row.py (already at 99%).
- Converter-side aggregate_row.py (Plan 14-11).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage `aggregate_row.py`
- `.planning/REQUIREMENTS.md` AGGR-01..09 (already Complete; this plan tests existing behavior)
- `src/v1/engine/components/aggregate/aggregate_row.py` (the lift target)
- `src/v1/engine/exceptions.py` (ConfigurationError, DataValidationError -- exception types to assert)
- `tests/v1/engine/components/aggregate/test_aggregate_row.py` (existing test file -- extend, don't replace)
- `.planning/phases/06-transform-group-a/06-01-PLAN.md` (Phase 6 aggregate rewrite; reference for behavior)
- `.planning/phases/07.1-manager-audit-basecomponent-fixes/07.1-06-PLAN.md` (list_object/union/median patches)
- Phase 13 D-B2 pattern: `pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)`
</canonical_refs>

<waves>

## Wave 1 -- Test extensions (parallelizable within plan)

### Task 14-02-001 -- Inventory missed lines and write extension tests

- **Type:** test
- **Description:**
    1. First, run `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py --cov=src/v1/engine/components/aggregate/aggregate_row --cov-report=term-missing -q` to print missed line ranges. Capture the missed-line list.
    2. For each cluster (1-8 above), add a test or test class. Use realistic DataFrame shapes with mixed dtypes (Int64, Decimal, datetime64, StringDtype). Assert exception types from `ETLError` hierarchy (D-C4) -- e.g., `pytest.raises(ConfigurationError, match=...)`.
    3. Each test follows the existing `_make_component(config)` pattern (see test file head). Pure-pandas tests -- direct `_process(input_df)` invocation -- per D-C1.
    4. Cover: `list_object` returns list (not str), `union` dedupes, `population_std_dev` matches `pandas.Series.std(ddof=0)`, `ignore_null=True` excludes NaN, `ignore_null=False` includes NaN where applicable (count semantics), Decimal precision preserved in grouped sum/avg, financial precision toggle changes behavior, column collision raises ConfigurationError or namespaces output, `output_column` config respected in grouped mode.
- **Files to create or modify:** `tests/v1/engine/components/aggregate/test_aggregate_row.py`
- **Verification command:** `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py --cov=src/v1/engine/components/aggregate/aggregate_row --cov-report=term-missing -q`
- **Expected outcome:** Coverage `>= 95%`; all tests green; missed lines list shrinks to <= 10 lines.
- **Notes:** If a missed line cannot be covered with realistic input -- apply D-C5 (delete dead branch as preferred option, document reasoning in plan summary). Do NOT add `# pragma: no cover` outside D-C3 allowlist.

### Task 14-02-002 -- Verify per-module floor for this plan

- **Type:** infra (verify)
- **Description:** Run the per-module gate scoped to this module:
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/aggregate/ -n auto \
      --cov=src/v1/engine/components/aggregate \
      --cov-report=json:cov_14_02.json -q
    python scripts/check_per_module_coverage.py cov_14_02.json --floor 95
    ```
- **Files to create or modify:** none persisted; `cov_14_02.json` ephemeral.
- **Verification command:** above.
- **Expected outcome:** Exit 0; PASS line printed.
- **Notes:** Cleanup `cov_14_02.json` after; not committed.

</waves>

<verification_gate>

Plan 14-02 is GREEN when:
1. `aggregate_row.py` reports >= 95% line coverage.
2. All tests in `test_aggregate_row.py` pass under `pytest -m "not oracle" -n auto -q`.
3. No new `# pragma: no cover` outside D-C3 allowlist.
4. All `pytest.raises` assertions use `ETLError` subclasses, never bare `Exception`.
5. Per-module gate script exits 0 for `src/v1/engine/components/aggregate/`.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `test(14-02): COV-AGG-001 extend aggregate_row tests for list_object/union/population_std_dev + Decimal/financial precision + ignore_null + grouped-mode collisions` | `tests/v1/engine/components/aggregate/test_aggregate_row.py` |
| 2 (conditional) | `fix(14-02): BUG-AGG-NN <description>` -- only if a real bug surfaces; else skip | `src/v1/engine/components/aggregate/aggregate_row.py` |

(Total: 1-2 commits.)

</commit_map>
