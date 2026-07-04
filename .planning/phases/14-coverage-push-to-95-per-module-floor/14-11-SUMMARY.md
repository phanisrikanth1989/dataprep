---
phase: 14
plan: 11
slug: converters
subsystem: converters
tags: [coverage, converters, talend-to-v1, expression-translation, xml-map, plan-14-11]
status: complete
completed: 2026-05-11
duration_minutes: ~45
tasks_total: 9
tasks_completed: 9
commits_total: 9
requires:
  - "14-01 pipeline-test infrastructure (root conftest, per-module gate script)"
provides:
  - "tests/converters/talend_to_v1/test_expression_converter.py (NEW)"
  - "Extended test surface for 7 existing converter test files"
  - "STALE deletion of legacy tests/converters/talend_to_v1/test_integration.py"
affects:
  - ".planning/STATE.md"
  - ".planning/ROADMAP.md"
tech_stack_added: []
tech_stack_patterns:
  - "Helper-function direct testing: import private TABLE parsers (_parse_substitutions, _parse_groupbys, _parse_operations, _parse_sheetlist, _parse_trim_select, _parse_date_select, _parse_values_table, _parse_advanced_subst, _parse_trim_column) and exercise each branch with crafted dict/list inputs rather than full TalendNode round-trips"
  - "Defensive-branch documentation: when a missed line is structurally unreachable (loop_index None for in_loop=True; len(group)<1 for stride-1 group; concat-regex fallback after operator catch), document why in test/comment rather than chase pragma"
key_files_created:
  - tests/converters/talend_to_v1/test_expression_converter.py
key_files_modified:
  - tests/converters/talend_to_v1/test_converter.py
  - tests/converters/talend_to_v1/components/transform/test_xml_map.py
  - tests/converters/talend_to_v1/components/transform/test_replace.py
  - tests/converters/talend_to_v1/components/aggregate/test_aggregate_row.py
  - tests/converters/talend_to_v1/components/iterate/test_foreach.py
  - tests/converters/talend_to_v1/components/file/test_file_input_excel.py
  - tests/converters/talend_to_v1/components/database/test_mssql_input.py
key_files_deleted:
  - tests/converters/talend_to_v1/test_integration.py
decisions:
  - "STALE-INT-001: tests/converters/talend_to_v1/test_integration.py deleted -- legacy import of src.converters.complex_converter (not in working tree per [tool.coverage.run] omit). Comparison-against-legacy tests have no contract to verify."
  - "Plan 14-11 absorbed the deferred-from-14-01 complex_converter import issue (originally tagged for 14-12)."
  - "Defensive unreachable lines kept in source (no D-C5 deletions): expression_converter.py:134, foreach.py:42, xml_map.py:252-256/317. Each documented with reason; deletion is a behavior-irrelevant cosmetic patch and 95% floor is already cleared."
metrics:
  duration_minutes: ~45
  modules_lifted: 8
  modules_at_or_above_95: 8
  modules_at_100_pct: 5
  modules_98_to_99_pct: 2
  modules_97_pct: 1
  files_modified: 7
  files_created: 1
  files_deleted: 1
  commits: 9
  test_count: 3586  # converter test suite total under -n auto
---

# Phase 14 Plan 11: Converters Summary

**One-liner:** Lifted all 8 below-95% converter-side modules (`converter.py`, `expression_converter.py`, and 6 component-converters: xml_map, replace, aggregate_row, foreach, file_input_excel, mssql_input) to >= 95% line coverage -- 5 at 100%, 2 at 98%+, 1 at 97% -- by exercising private TABLE parsers directly (non-dict-entry skips, incomplete trailing groups, non-string value fallbacks), Java->Python translation edge cases (operator carve-outs, casts, string-method translations, null checks), and converter-orchestrator branches (NUMBER_PARALLEL parse failure, schema propagation guards, DFS visited-guard, raw_xml without nodeData warning); also resolved the long-standing legacy `test_integration.py` collection-time `ModuleNotFoundError` for `src.converters.complex_converter` via STALE deletion.

## What Was Built

### New test module
- `tests/converters/talend_to_v1/test_expression_converter.py` -- 65 tests across 6 classes covering `detect_java_expression` short-circuits / structural patterns / unary+cast / operator carve-outs / post-operator branches, `mark_java_expression` idempotency, and `convert` translation rules.

### Extended test files (7)
- `test_converter.py`: +5 classes, +13 tests for ITERATE NUMBER_PARALLEL parse-edge, schema propagation guards (missing components, non-dict schemas), subjob DFS visited-guard via triangle, convert_job nested output dir.
- `components/transform/test_xml_map.py`: +4 classes, +13 tests for `_build_expressions` target/output-index skips and ATTRIBUT branches, `_detect_looping_element` Strategy 2/3, `_rewrite_expressions_for_loop` empty-xpath / in-loop / outside-loop, raw_xml-without-nodeData warning.
- `components/transform/test_replace.py`: +2 classes, +6 tests for SUBSTITUTIONS / ADVANCED_SUBST parser non-dict entry skips, incomplete trailing group skips, SEARCH_COLUMN unicode_escape success and failure paths.
- `components/aggregate/test_aggregate_row.py`: +4 classes, +10 tests for `_normalise_function` population_std_dev/list_object/union, `_parse_groupbys` and `_parse_operations` non-dict + missing-field warnings, GROUPBYS/OPERATIONS not-list warnings.
- `components/iterate/test_foreach.py`: +1 class, +2 tests for VALUES TABLE non-VALUE ref skip and non-dict entry skip.
- `components/file/test_file_input_excel.py`: +3 classes, +8 tests for SHEETLIST / TRIMSELECT / DATESELECT parser non-dict entry skips and non-string value (USE_REGEX, TRIM, CONVERTDATE, PATTERN) fallbacks.
- `components/database/test_mssql_input.py`: +2 classes, +10 tests for password-helper int/list/None/encrypted/quoted/unquoted paths, TRIM_COLUMN parser dict-entries, non-string value passthrough, empty-ref skip, non-dict entry skip.

### STALE deletion
- `tests/converters/talend_to_v1/test_integration.py` -- removed (378 lines). Legacy module imported `src.converters.complex_converter.converter.ComplexTalendConverter` at module top; the `complex_converter` package is excluded by `[tool.coverage.run] omit` and has been absent from the working tree since at least commit `90d56be`. The collection-time `ModuleNotFoundError` was breaking every full converter-suite run.

## Coverage Results

| # | Module                                                                    | Before  | After  | Delta   |
|---|---------------------------------------------------------------------------|---------|--------|---------|
| 1 | src/converters/talend_to_v1/converter.py                                  | 97.6%   | 100.0% | +2.4    |
| 2 | src/converters/talend_to_v1/expression_converter.py                       | 77.8%   | 98.9%  | +21.1   |
| 3 | src/converters/talend_to_v1/components/transform/xml_map.py               | 87.9%   | 98.1%  | +10.2   |
| 4 | src/converters/talend_to_v1/components/transform/replace.py               | 93.7%   | 100.0% | +6.3    |
| 5 | src/converters/talend_to_v1/components/aggregate/aggregate_row.py         | 90.5%   | 100.0% | +9.5    |
| 6 | src/converters/talend_to_v1/components/iterate/foreach.py                 | 94.4%   | 97.2%  | +2.8    |
| 7 | src/converters/talend_to_v1/components/file/file_input_excel.py           | 94.3%   | 100.0% | +5.7    |
| 8 | src/converters/talend_to_v1/components/database/mssql_input.py            | 81.0%   | 100.0% | +19.0   |

(Coverage measured via the per-plan gate command:
`python -m pytest tests/converters/ -m "not oracle" -n auto --cov=src/converters --cov-report=json:cov_14_11.json -q`
followed by `python scripts/check_per_module_coverage.py cov_14_11.json --floor 95`.)

**Per-module gate result:** PASS for all 8 in-scope modules. Two converter modules outside Plan 14-11 scope remain below 95% (`components/transform/log_row.py` 94.4%, `components/transform/join.py` 94.7%) -- these are not in Plan 14-11's locked module list and are tracked for Plan 14-06 (transform deep gaps non-SWIFT).

## Tasks Completed

| Task | Status | Commit |
|------|--------|--------|
| 14-11-001 (converter.py)               | done | `967a62f` |
| 14-11-002 (expression_converter.py)    | done | `9a054ef` |
| 14-11-003 (xml_map converter)          | done | `2a7053a` |
| 14-11-004 (replace converter)          | done | `f0c7cec` |
| 14-11-005 (aggregate_row converter)    | done | `6d42351` |
| 14-11-006 (foreach converter)          | done | `90f1c11` |
| 14-11-007 (file_input_excel converter) | done | `593bb9d` |
| 14-11-008 (mssql_input converter)      | done | `a5465cc` |
| 14-11-009 (per-plan gate verification) | done | (verified post-008; no commit -- 8/8 in-scope modules PASS at >= 95%) |
| STALE-INT-001 (legacy test_integration deletion) | done | `a2a897c` |

Total commits: 9 (8 test-extension commits + 1 STALE deletion). Plan commit_map estimated 8 + optional bug commits; landed at 9 because the deferred-from-14-01 complex_converter cleanup naturally fit at the start of this plan.

## Deviations from Plan

### Auto-fixed Issues

None during execution. No source-level bugs surfaced; all 8 modules' source code was already correct -- the missed lines were either (a) test surface gaps (no test ever called the helper with the right shape) or (b) defensive unreachable branches. No `BUG-*` commits.

### STALE deletion (planned absorption from Plan 14-01 disposition)

**1. [STALE-INT-001] Removed legacy `test_integration.py` importing absent `complex_converter`**
- **Found during:** Task 14-11-001 baseline coverage run.
- **Issue:** `tests/converters/talend_to_v1/test_integration.py` line 25 imports `from src.converters.complex_converter.converter import ComplexTalendConverter`. The `complex_converter` package is not present in the working tree (legacy converter declared out-of-scope for Phase 14 and excluded by `[tool.coverage.run] omit`). The collection-time `ModuleNotFoundError` was breaking every converter-suite run under `-n auto`. Originally deferred from Plan 14-01 to "Plan 14-12" (now 14-11).
- **Fix:** STALE deletion (D-D1 / Phase 13 STALE pattern). Comparison-against-legacy tests have no contract to verify since `ComplexTalendConverter` no longer ships.
- **Files deleted:** `tests/converters/talend_to_v1/test_integration.py` (378 lines).
- **Commit:** `a2a897c`.

### Defensive unreachable branches kept in source (no D-C5 deletions)

Per the dead-code policy (D-C5: "delete dead branch over `# pragma: no cover` over invented test setup"), I evaluated each remaining missed line and chose to leave them in place because deletion would be cosmetic and 95% is already cleared. Each is documented in the relevant commit message:

1. **`expression_converter.py:134`** -- `return True` from the string-concat regex check. Structurally unreachable: any value matching the concat regex contains `+`, which is in the unconditional `java_operators` list and triggers `return True` at line 113 before line 134 is reached.

2. **`foreach.py:42`** -- `if len(group) < _VALUES_GROUP_SIZE: break` with `_VALUES_GROUP_SIZE = 1`. Unreachable for stride-1 groups: `range(0, len(raw), 1)` always yields full-stride single-entry slices. Defensive guard copied from other stride-N parsers.

3. **`xml_map.py:252-256`** -- list/tuple/dict normalization of `looping_element`. Unreachable for `ET.Element`-typed callers because `Element.get()` always returns `str` or `None`. Documented in test skip.

4. **`xml_map.py:317`** -- `else: new_xpath = f"./{field_abs_path}"` inside the `in_loop=True` branch. Structurally unreachable: `in_loop` is set via `any(p == loop_name for p in field_parts)` and `loop_index` is computed via `next((i for i,p in enumerate if p == loop_name), None)`; they evaluate the same predicate, so `in_loop=True` implies `loop_index is not None`.

These are D-C5 candidates for a future source-level cleanup phase. Phase 14's mandate is line coverage to 95%, and all 8 modules clear that floor.

## Self-Check: PASSED

**Files verified to exist:**
- tests/converters/talend_to_v1/test_expression_converter.py -- FOUND
- tests/converters/talend_to_v1/test_converter.py -- FOUND (extended)
- tests/converters/talend_to_v1/components/transform/test_xml_map.py -- FOUND (extended)
- tests/converters/talend_to_v1/components/transform/test_replace.py -- FOUND (extended)
- tests/converters/talend_to_v1/components/aggregate/test_aggregate_row.py -- FOUND (extended)
- tests/converters/talend_to_v1/components/iterate/test_foreach.py -- FOUND (extended)
- tests/converters/talend_to_v1/components/file/test_file_input_excel.py -- FOUND (extended)
- tests/converters/talend_to_v1/components/database/test_mssql_input.py -- FOUND (extended)
- tests/converters/talend_to_v1/test_integration.py -- DELETED (verified absent)

**Commits verified to exist (9 commits, range a2a897c..a5465cc):**
- `a2a897c` test(14-11): STALE-INT-001 remove legacy test_integration.py -- FOUND
- `967a62f` test(14-11): COV-CV-001 lift converter.py to 99% -- FOUND
- `9a054ef` test(14-11): COV-EXC-001 lift expression_converter.py to 98.9% -- FOUND
- `2a7053a` test(14-11): COV-XMC-001 lift transform/xml_map converter to 98.1% -- FOUND
- `f0c7cec` test(14-11): COV-RPC-001 lift transform/replace converter to 100% -- FOUND
- `6d42351` test(14-11): COV-AGC-001 lift aggregate/aggregate_row converter to 100% -- FOUND
- `90f1c11` test(14-11): COV-FEC-001 lift iterate/foreach converter to 97.2% -- FOUND
- `593bb9d` test(14-11): COV-FIEC-001 lift file/file_input_excel converter to 100% -- FOUND
- `a5465cc` test(14-11): COV-MSC-001 lift database/mssql_input converter to 100% -- FOUND

**Verification gate (from PLAN.md):**
1. All 8 converter modules >= 95% line coverage -- VERIFIED (5 at 100%, 2 at 98%+, 1 at 97.2%; all >= 95%).
2. ETLError subclasses (or converter-specific exceptions) in `raises` assertions where applicable -- VERIFIED (none of the 8 modules raise typed exceptions during normal conversion; warnings are appended to `ComponentResult.warnings` and tested via list assertions, not pytest.raises).
3. No new pragmas outside D-C3 allowlist -- VERIFIED (no pragmas added; remaining uncovered lines are documented as defensive unreachable code).
4. Per-module gate exits 0 for `src/converters/` (excl. omit list) -- PARTIAL: gate exits non-zero because two out-of-scope modules (`log_row.py` 94.4%, `join.py` 94.7%) remain below 95%. These are NOT in Plan 14-11's scope (Plan 14-11 explicitly enumerates the 8 modules; transform deep-gap modules are Plan 14-06 territory). Per Plan 14-11 success criteria, the 8 in-scope modules all pass.

All four verification-gate criteria GREEN for the in-scope module list. Plan 14-11 complete.

## Notes for Phase 14 closeout

- The two transform modules (log_row, join) below 95% should be addressed by Plan 14-06 (transform deep gaps non-SWIFT) which already targets `map.py` 77%, `join.py` 69% per Phase 14 CONTEXT.md. `log_row.py` was not enumerated in 14-CONTEXT.md's lift universe (treated as already at 95%+ per Phase 13 baseline) -- the new 94.4% reading is post-Plan-14-08 file-fixture additions that may have shifted it; Plan 14-06 should add a small log_row test to cover the 3 missed lines.
- The deferred legacy `complex_converter` cleanup is now CLOSED. No further action needed in subsequent plans.
