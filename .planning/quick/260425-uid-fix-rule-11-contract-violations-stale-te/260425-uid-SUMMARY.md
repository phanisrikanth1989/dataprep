---
quick_id: 260425-uid
description: Fix Rule 11 contract violations + stale tests + add manual-component authoring guide
date: 2026-04-25
status: complete
tasks_completed: 9
tasks_total: 9
commits: 8
duration_minutes: 25
key_files_modified:
  - src/v1/engine/components/transform/sort_row.py
  - src/v1/engine/components/transform/row_generator.py
  - src/v1/engine/components/transform/extract_xml_fields.py
  - src/v1/engine/components/transform/swift_block_formatter.py
  - src/v1/engine/components/transform/extract_delimited_fields.py
  - src/v1/engine/components/file/file_input_positional.py
  - tests/v1/engine/components/transform/test_filter_columns.py
  - tests/v1/engine/components/transform/test_sort_row.py
  - tests/v1/engine/components/transform/test_unite.py
key_files_created:
  - docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md
---

# Quick Task 260425-uid: Rule 11 Cleanup + Manual Authoring Guide — Summary

**One-liner:** Removed 6 Rule 11 violations (manual validate_schema in _process), corrected 4 stale test assertions to post-7.1 stats contract, and added a 330-line manual authoring guide covering all 11 rules.

---

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Remove validate_schema in SortRow._process | d4bd11b | sort_row.py |
| 2 | Remove validate_schema in RowGenerator._process | d16275b | row_generator.py |
| 3 | Remove validate_schema in ExtractXmlFields._process | a71d3f1 | extract_xml_fields.py |
| 4 | Remove validate_schema in SwiftBlockFormatter._process | b420723 | swift_block_formatter.py |
| 5 | Remove validate_schema in ExtractDelimitedFields._process | 1924dfa | extract_delimited_fields.py |
| 6 | Remove validate_schema in FileInputPositional._process | 7115726 | file_input_positional.py |
| 7 | Update 4 stale test assertions | 79adf5c | test_filter_columns.py, test_sort_row.py, test_unite.py |
| 8 | Add MANUAL_COMPONENT_AUTHORING.md | 2aec90b | MANUAL_COMPONENT_AUTHORING.md |
| 9 | Final regression sweep + push | N/A (push only) | — |

---

## Must-Haves Verification

- [x] All 6 components no longer call `self.validate_schema()` inside `_process()` (grep returns empty)
- [x] 4 previously-failing tests now pass with corrected assertions
- [x] `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` exists (331 lines, all required sections)
- [x] Full Python test suite: 1093 passed, 1 skipped, 0 failures
- [x] `mvn test`: BUILD SUCCESS
- [x] Branch pushed to origin: `feature/engine-restructure`

---

## Deviations from Plan

### Missing Test Files (no action required)

Tasks 2-6 reference test files that do not exist:
- `tests/v1/engine/components/transform/test_row_generator.py` — does not exist
- `tests/v1/engine/components/transform/test_extract_xml_fields.py` — does not exist
- `tests/v1/engine/components/transform/test_swift_block_formatter.py` — does not exist
- `tests/v1/engine/components/transform/test_extract_delimited_fields.py` — does not exist
- `tests/v1/engine/components/file/test_file_input_positional.py` — does not exist

Per deviation rules, the full suite (`python -m pytest tests/v1/engine/ -q`) was run after each task to confirm no regressions. All 1093 tests passed with 0 new failures.

### ExtractDelimitedFields — Extra Code Removed

The `validate_schema` block in `extract_delimited_fields.py` also contained a column-ordering
and missing-column fill block that duplicated `_enforce_schema_column_order` (base class step 7b).
The entire `if schema:` block (10 lines) was removed — the base class handles both schema
validation and column ordering automatically.

### test_schema_column_not_in_input — Contract Clarification

The test description said "output has [a, b] only" but post-7.1 the actual contract is that
the base class `_enforce_schema_column_order` (step 7b) fills missing schema columns with
null. The test was updated to:
- Assert columns are `["a", "b", "z"]` (base class fills missing "z")
- Assert `result["main"]["z"].isna().all()` (null-filled)
- Assert warning was logged for missing schema column (via `caplog` fixture)
- Convert test method signature to accept `caplog` parameter

---

## Known Stubs

None. All changes are production-quality fixes.

---

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries introduced.

---

## Self-Check: PASSED

- [x] `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` exists
- [x] Commits d4bd11b, d16275b, a71d3f1, b420723, 1924dfa, 7115726, 79adf5c, 2aec90b all present in git log
- [x] `grep -r "self.validate_schema" src/v1/engine/components/` — returns 0 hits in the 6 target files
- [x] 1093 passed, 0 failures in final engine suite run
