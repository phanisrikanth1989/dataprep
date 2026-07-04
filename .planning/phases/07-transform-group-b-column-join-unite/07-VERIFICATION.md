---
phase: 07-transform-group-b-column-join-unite
verified: 2026-04-15T12:15:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 7: Transform Group B -- Column, Join, Unite Verification Report

**Phase Goal:** tFilterColumns, tJoin, and tUnite produce correct results -- tFilterColumns and tUnite (already functionally Green) get test coverage, and tJoin gets targeted bug fixes for case-insensitive joins, reject output, and null semantics
**Verified:** 2026-04-15T12:15:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | tJoin performs case-sensitive joins by default without corrupting original data | VERIFIED | join.py line 161: `case_sensitive = self.config.get("case_sensitive", True)`. Copies used for merge (lines 177-178). Inversion test: "Alice" and "BOB" preserved after join. test_join.py::TestCaseSensitiveJoin (3 tests) all pass. |
| 2 | Null keys never match in joins (Talend/SQL semantics) | VERIFIED | join.py line 31: `_NULL_SENTINEL`. Lines 189-194: fillna before merge. Lines 212-217: sentinel filtering post-merge. test_join.py::TestNullJoinKeys (4 tests) all pass. Inversion test confirms no sentinel leaks to output. |
| 3 | Reject output contains main rows with no lookup match, computed from a single merge | VERIFIED | join.py lines 197-204: single `pd.merge()` with `indicator=True`. Lines 208-209: matched/unmatched from indicator. Lines 226: `reject_rows = merged[unmatched].copy()`. test_join.py::TestRejectOutput (4 tests) all pass. |
| 4 | INCLUDE_LOOKUP toggle controls whether lookup columns appear in output | VERIFIED | join.py lines 232-264: `use_lookup_cols` and `lookup_cols` config implementation. test_join.py::TestIncludeLookup (3 tests) all pass. |
| 5 | ERROR_MESSAGE globalMap variable is set on join errors | VERIFIED | join.py lines 299-303: sets `{id}_ERROR_MESSAGE` when rejects exist. Lines 327-329: sets on exception. test_join.py::TestErrorMessage passes. |
| 6 | Reject schema includes errorCode and errorMessage columns | VERIFIED | join.py lines 288-297: checks `reject_schema`, adds `errorCode='JOIN_REJECT'` and `errorMessage`. test_join.py::TestRejectOutput::test_reject_schema_with_error_columns and test_reject_error_code_value pass. |
| 7 | tFilterColumns selects columns using output_schema only -- no mode/columns config keys | VERIFIED | filter_columns.py 67: `schema_cols = [col["name"] for col in self.output_schema]`. 77 lines total, no reference to `mode`, `columns`, or `keep_row_order`. test_filter_columns.py::TestSchemaFiltering (9 tests) pass including explicit config-key-absence tests. |
| 8 | tUnite concatenates all input DataFrames via pd.concat (UNION ALL) -- no MERGE mode | VERIFIED | unite.py line 68: `pd.concat(dfs, ignore_index=True, sort=False)`. 72 lines total, no reference to MERGE. test_unite.py::TestUnionConcat (5 tests) all pass. |
| 9 | All three components (Join, FilterColumns, Unite) have exhaustive unit tests | VERIFIED | test_join.py: 35 tests. test_filter_columns.py: 15 tests. test_unite.py: 18 tests. Total: 68 tests, all pass (0.11s). |
| 10 | Mismatched schemas in Unite produce NaN fills (correct UNION ALL behavior) | VERIFIED | test_unite.py::TestMismatchedSchemas (3 tests) all pass. Verifies [a,b] + [a,c] -> [a,b,c] with NaN fills for missing columns. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/v1/engine/components/transform/join.py` | tJoin engine component rewrite | VERIFIED | 340 lines, @REGISTRY.register("Join", "tJoin"), sentinel null handling, single-pass merge, INCLUDE_LOOKUP, ERROR_MESSAGE, reject schema |
| `src/v1/engine/components/transform/filter_columns.py` | Schema-based column filtering | VERIFIED | 77 lines (down from 205), @REGISTRY.register("FilterColumns", "tFilterColumns"), no mode/columns/keep_row_order |
| `src/v1/engine/components/transform/unite.py` | UNION-only concat | VERIFIED | 72 lines (down from 393), @REGISTRY.register("Unite", "tUnite"), no MERGE/streaming/dedup |
| `src/v1/engine/engine.py` | reject_schema initialization | VERIFIED | Line 117: `component.reject_schema = comp_config.get('schema', {}).get('reject', [])` |
| `tests/v1/engine/components/transform/test_join.py` | Exhaustive tJoin tests | VERIFIED | 35 tests covering JOIN-01 through JOIN-08, all pass |
| `tests/v1/engine/components/transform/test_filter_columns.py` | tFilterColumns tests | VERIFIED | 15 tests covering FCOL-01/FCOL-02, all pass |
| `tests/v1/engine/components/transform/test_unite.py` | tUnite tests | VERIFIED | 18 tests covering UNIT-01/UNIT-02, all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| join.py | component_registry.py | @REGISTRY.register("Join", "tJoin") | WIRED | Line 34 |
| join.py | base_component.py | class Join(BaseComponent) | WIRED | Line 35 |
| filter_columns.py | component_registry.py | @REGISTRY.register("FilterColumns", "tFilterColumns") | WIRED | Line 24 |
| unite.py | component_registry.py | @REGISTRY.register("Unite", "tUnite") | WIRED | Line 23 |
| test_join.py | join.py | from src...join import Join | WIRED | Line 16 |
| test_filter_columns.py | filter_columns.py | from src...filter_columns import FilterColumns | WIRED | Line 8 |
| test_unite.py | unite.py | from src...unite import Unite | WIRED | Line 9 |
| __init__.py | all three components | import Join, FilterColumns, Unite | WIRED | Lines 12, 26, 29 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 68 tests pass | `python -m pytest tests/.../test_join.py test_filter_columns.py test_unite.py -v` | 68 passed in 0.11s | PASS |
| Null sentinel does not leak to output | Custom inversion test with NaN keys | No sentinel strings in main or reject | PASS |
| Case-sensitive join preserves original data | Custom inversion test with "Alice"/"BOB" | Values preserved exactly after join | PASS |
| Reject has only main columns when use_lookup_cols=True | Custom inversion test | city not in reject columns | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FCOL-01 | 07-02 | Add engine unit tests for tFilterColumns | SATISFIED | 15 tests in test_filter_columns.py, all pass |
| FCOL-02 | 07-02 | Verify mode and keep_row_order engine-only keys work correctly | SATISFIED | Non-Talend keys removed per D-09; tests verify they are ignored (schema-driven) |
| JOIN-01 | 07-01 | Fix case-insensitive join lowercase corruption | SATISFIED | Merge on copies only; case_sensitive defaults True; 3 case tests pass |
| JOIN-02 | 07-01 | Fix left outer join incorrect reject output | SATISFIED | Single-pass merge with indicator; TestLeftOuterJoin (3 tests) and TestRejectOutput (4 tests) pass |
| JOIN-03 | 07-01 | Fix reject schema never populated | SATISFIED | reject_schema set by engine.py line 117; join.py lines 288-297 populate errorCode/errorMessage |
| JOIN-04 | 07-01 | Implement INCLUDE_LOOKUP toggle | SATISFIED | use_lookup_cols/lookup_cols config; TestIncludeLookup (3 tests) pass |
| JOIN-05 | 07-01 | Implement ERROR_MESSAGE globalMap variable | SATISFIED | join.py lines 299-303, 327-329; TestErrorMessage passes |
| JOIN-06 | 07-01 | Fix schema attribute mismatch dead code | SATISFIED | Full rewrite eliminates dead `self.schema` references; grep confirms zero matches |
| JOIN-07 | 07-01 | Fix double merge for reject computation | SATISFIED | Single pd.merge() with indicator=True at line 197-204; TestSinglePassMerge passes |
| JOIN-08 | 07-01 | Fix null join semantics | SATISFIED | _NULL_SENTINEL pattern; TestNullJoinKeys (4 tests) pass; inversion test confirms no sentinel leak |
| UNIT-01 | 07-02 | Add engine unit tests for tUnite | SATISFIED | 18 tests in test_unite.py, all pass |
| UNIT-02 | 07-02 | Verify union behavior with mismatched schemas | SATISFIED | TestMismatchedSchemas (3 tests) verify NaN fill behavior |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No TODO/FIXME/HACK, no print(), no execute() override, no UPPERCASE config keys, no non-Talend config keys |

### Human Verification Required

None. All behaviors verified programmatically through unit tests and inversion checks.

### Gaps Summary

No gaps found. All 10 must-have truths verified. All 12 requirement IDs satisfied. All 7 artifacts exist, are substantive, and are properly wired. All 68 tests pass. No anti-patterns detected.

---

_Verified: 2026-04-15T12:15:00Z_
_Verifier: Claude (gsd-verifier)_
