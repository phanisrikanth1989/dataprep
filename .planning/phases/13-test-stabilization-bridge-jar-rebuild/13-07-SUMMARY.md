---
phase: 13-test-stabilization-bridge-jar-rebuild
plan: "07"
subsystem: testing
tags: [stale-deletion, needs_review, converter, test-cleanup]

requires:
  - phase: 13
    plan: "06"
    provides: TEST-CHANGE fixes for aggregate_row and regex_custom completed before stale deletions

provides:
  - 10 STALE NeedsReview test methods deleted across 3 converter test files
  - Test suite at 0 failures (6832 passed, 26 skipped, 1 xfailed)

affects: [13-coverage-baseline]

tech-stack:
  added: []
  patterns:
    - "D-D1 deletion policy: needs_review tests for engine-implemented features are DELETED not updated"

key-files:
  created: []
  modified:
    - tests/converters/talend_to_v1/components/file/test_file_input_delimited.py
    - tests/converters/talend_to_v1/components/file/test_file_input_fullrow.py
    - tests/converters/talend_to_v1/components/file/test_file_output_delimited.py

key-decisions:
  - "Re-triage found 10 STALE tests, not 11 as planned: test_aggregate_row.py had 0 STALE tests (only 1 TEST-CHANGE resolved in Plan 13-06)"
  - "5 file_input_fullrow deletions: converter now returns needs_review=[] (engine implements all 4 features: header_rows, footer_rows, random, nb_random); the 5th deletion is test_needs_review_count which asserted == 4 entries"
  - "2 file_input_delimited deletions: fieldseparator mismatch and csv_option are engine-implemented"
  - "3 file_output_delimited deletions: delimiter, encoding, include_header mismatches are engine-implemented"
  - "Remaining 3 tests in each TestNeedsReview class (all_engine_gap, has_component_id, no_framework_param) pass vacuously with empty needs_review=[] -- kept as valid structure guards"

requirements-completed: [TEST-07, TEST-08]

duration: 10min
completed: 2026-05-10
---

# Phase 13 Plan 07: STALE NeedsReview Deletions Summary

**10 STALE NeedsReview test methods deleted across 3 converter test files; test suite at 0 failures**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-05-10
- **Tasks:** 1 (10 deletions)
- **Files modified:** 3 test files

## Re-Triage Results

On entry (after Plan 13-06), 10 failing tests remained. All confirmed STALE via D-D1 check (converter no longer emits the asserted needs_review entry):

| File | Tests Deleted | Reason |
|------|---------------|--------|
| test_file_input_delimited.py | 2 | fieldseparator mismatch, csv_option -- engine implemented |
| test_file_input_fullrow.py | 5 | header_rows, footer_rows, random, nb_random count + header_rows header; converter returns needs_review=[] |
| test_file_output_delimited.py | 3 | delimiter mismatch, encoding mismatch, include_header mismatch -- engine implemented |
| **Total** | **10** | |

Note: Plan spec anticipated 11 STALE deletions across 4 files. Actual count was 10 across 3 files -- test_aggregate_row.py had no STALE tests, only 1 TEST-CHANGE (resolved in Plan 13-06).

## Deletions Applied

### test_file_input_delimited.py (2 deletions)

- `test_fieldseparator_engine_mismatch` -- commit `e1ac00f` (STALE-001)
- `test_needs_review_csv_option` -- commit `8c45dff` (STALE-002)

### test_file_input_fullrow.py (5 deletions)

- `test_needs_review_count` -- commit `4671566` (STALE-003) -- asserted == 4 entries; converter now returns 0
- `test_needs_review_header_rows` -- commit `ab05f46` (STALE-004)
- `test_needs_review_footer_rows` -- commit `e5661c6` (STALE-005)
- `test_needs_review_random` -- commit `367344c` (STALE-006)
- `test_needs_review_nb_random` -- commit `ddb93e4` (STALE-007)

### test_file_output_delimited.py (3 deletions)

- `test_needs_review_delimiter_mismatch` -- commit `5272b28` (STALE-008)
- `test_needs_review_encoding_mismatch` -- commit `de1b5af` (STALE-009)
- `test_needs_review_include_header_mismatch` -- commit `401b4df` (STALE-010)

## Final Test Count

```
python -m pytest tests/ -q --no-header 2>&1 | tail -3
6832 passed, 26 skipped, 1 xfailed, 36 warnings in 44.41s
```

Target: 0 failures. Achieved.

## Task Commits (10 STALE deletions)

| Commit | Tag | Description |
|--------|-----|-------------|
| `e1ac00f` | STALE-001 | delete test_fieldseparator_engine_mismatch from test_file_input_delimited.py |
| `8c45dff` | STALE-002 | delete test_needs_review_csv_option from test_file_input_delimited.py |
| `4671566` | STALE-003 | delete test_needs_review_count from test_file_input_fullrow.py |
| `ab05f46` | STALE-004 | delete test_needs_review_header_rows from test_file_input_fullrow.py |
| `e5661c6` | STALE-005 | delete test_needs_review_footer_rows from test_file_input_fullrow.py |
| `367344c` | STALE-006 | delete test_needs_review_random from test_file_input_fullrow.py |
| `ddb93e4` | STALE-007 | delete test_needs_review_nb_random from test_file_input_fullrow.py |
| `5272b28` | STALE-008 | delete test_needs_review_delimiter_mismatch from test_file_output_delimited.py |
| `de1b5af` | STALE-009 | delete test_needs_review_encoding_mismatch from test_file_output_delimited.py |
| `401b4df` | STALE-010 | delete test_needs_review_include_header_mismatch from test_file_output_delimited.py |

## Deviations from Plan

**1. [Scope change] 10 STALE deletions, not 11**
- Plan spec: 11 STALE across 4 files
- Actual: 10 STALE across 3 files
- Reason: test_aggregate_row.py had no STALE tests -- its only failure was the `>= 3` count assertion (TEST-CHANGE) which Plan 13-06 resolved
- Impact: Positive deviation (less work needed)

## Known Stubs
None.

## Threat Flags
None -- test files only, no production source changes.

## Self-Check

- `tests/converters/talend_to_v1/components/file/test_file_input_delimited.py` -- FOUND
- `tests/converters/talend_to_v1/components/file/test_file_input_fullrow.py` -- FOUND
- `tests/converters/talend_to_v1/components/file/test_file_output_delimited.py` -- FOUND
- All 10 STALE commits present in git log -- VERIFIED
- `pytest tests/ -q` -- 6832 passed, 0 failures -- VERIFIED
- `git diff src/` -- empty (no production source changes) -- VERIFIED

## Self-Check: PASSED
