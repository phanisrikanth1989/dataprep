---
phase: 04-file-i-o-components
plan: 01
subsystem: engine-file-input
tags: [file-io, rewrite, talend-parity, reject-flow, tdd]
dependency_graph:
  requires: [base_component, component_registry, exceptions]
  provides: [FileInputDelimited-engine-component, file-input-test-suite]
  affects: [engine-component-file-init, test-directory-structure]
tech_stack:
  added: []
  patterns: [chunked-validation, deque-footer-skip, vectorized-fast-path, reject-flow-with-error-codes]
key_files:
  created:
    - tests/v1/engine/components/__init__.py
    - tests/v1/engine/components/file/__init__.py
    - tests/v1/engine/components/file/test_file_input_delimited.py
  modified:
    - src/v1/engine/components/file/file_input_delimited.py
decisions:
  - "Date validation runs before type conversion for datetime columns so DATE_FORMAT errors are not masked by TYPE_CONVERSION"
  - "select_dtypes includes 'str' alongside 'object' for pandas 3.0 compatibility"
  - "Fast vectorized path used when no validation flags set, falling back to per-row only for columns with conversion failures"
metrics:
  duration: 7m
  completed: "2026-04-14T20:35:51Z"
  tasks: 2/2
  tests: 66
  files: 4
---

# Phase 4 Plan 01: FileInputDelimited Rewrite Summary

Full rewrite of tFileInputDelimited with Talend feature parity: ISO-8859-15 default encoding, semicolon default delimiter, REJECT flow with standardized errorCode constants, CSV_OPTION RFC4180 toggle, TRIMSELECT per-column trim, CHECK_FIELDS_NUM/CHECK_DATE validation, chunked validation for memory efficiency, and 66 exhaustive unit tests.

## What Was Done

### Task 1: Rewrite FileInputDelimited component
**Commit:** ee9edd2

Deleted all existing code (574 lines) and wrote a new 781-line implementation from scratch conforming to ENGINE_COMPONENT_PATTERN.md.

Key implementation details:
- **Config keys:** Reads converter output keys directly (`fieldseparator`, not `delimiter`; `remove_empty_row`, not `remove_empty_rows`)
- **Defaults:** ISO-8859-15 encoding, semicolon separator, remove_empty_row=True, die_on_error=False
- **REJECT flow:** Routes rows failing field count, type conversion, or date validation to reject output with `errorCode` and `errorMessage` columns
- **CSV_OPTION:** csv_option=False uses `csv.QUOTE_NONE` (no quoting); csv_option=True uses Python `csv.reader` for RFC4180 compliance
- **Deque footer skip:** CSV mode uses `collections.deque(maxlen=footer_rows)` sliding window for memory-efficient footer skipping
- **TRIMSELECT:** Per-column trim settings override trim_all when non-empty
- **Chunked validation:** `_VALIDATION_CHUNK_SIZE = 50000` rows per chunk limits peak memory during row-level validation
- **Vectorized fast path:** When check_fields_num=False and check_date=False, uses pandas vectorized operations instead of per-row iteration
- **GlobalMap variables:** Sets `{id}_FILENAME` and `{id}_ENCODING` before processing
- **Deferred features:** uncompress, split_record, random, advanced_separator, enable_decode log warning and proceed
- **Error code constants:** `_ERROR_FIELD_COUNT`, `_ERROR_TYPE_CONVERSION`, `_ERROR_DATE_FORMAT` at module level

### Task 2: Create exhaustive tests for FileInputDelimited
**Commit:** ea36e03

Created 66 unit tests across 15 test classes covering all FILD requirements (FILD-01 through FILD-09).

Test classes:
- **TestValidation** (3 tests): missing/empty filepath raises ConfigurationError
- **TestDefaults** (4 tests): semicolon separator, ISO-8859-15 encoding, header rows, remove_empty_row
- **TestBasicReading** (8 tests): semicolon, comma, tab, header skip, footer skip, limit, UTF-8, escaped tab
- **TestCsvOption** (6 tests): disabled quoting, quoted fields, embedded delimiters, embedded newlines, escaped quotes, footer with deque
- **TestTrimSelect** (5 tests): specific column, override trim_all, untouched columns, trim_all fallback, no trim default
- **TestCheckFieldsNum** (4 tests): wrong count rejected, correct passes, disabled by default, reject schema
- **TestCheckDate** (4 tests): valid/invalid dates, no pattern skip, disabled by default
- **TestRejectFlow** (6 tests): type error, all columns in reject, multiple reasons, NB_LINE_REJECT, main+reject=total, constant values
- **TestGlobalMapVariables** (5 tests): FILENAME, ENCODING, stats, no GlobalMap, NB_LINE_REJECT
- **TestDeferredFeatures** (3 tests): uncompress, random, advanced_separator warnings
- **TestRemoveEmptyRow** (3 tests): enabled, disabled, all-empty
- **TestEdgeCases** (5 tests): empty file, file not found, single row, header only, invalid limit
- **TestSchemaHandling** (4 tests): int/float/datetime conversion, no-schema mode
- **TestIterateReexecution** (3 tests): results match, stats reset, config unchanged
- **TestVectorizedFastPath** (3 tests): fast path works, type conversion correct, handles failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Date validation ordering**
- **Found during:** Task 2 (test_invalid_date_rejected failure)
- **Issue:** Date validation ran after type conversion for datetime columns, so `datetime.strptime` failure in `_convert_value` was classified as TYPE_CONVERSION instead of DATE_FORMAT
- **Fix:** Moved date pattern validation check before type conversion in `_chunked_validate` so datetime columns with invalid patterns get DATE_FORMAT error code
- **Files modified:** src/v1/engine/components/file/file_input_delimited.py
- **Commit:** ea36e03

**2. [Rule 1 - Bug] Pandas 3.0 select_dtypes deprecation**
- **Found during:** Task 2 (Pandas4Warning in test output)
- **Issue:** `select_dtypes(include=["object"])` no longer includes str columns in pandas 3.0+
- **Fix:** Changed to `select_dtypes(include=["object", "str"])` for forward compatibility
- **Files modified:** src/v1/engine/components/file/file_input_delimited.py
- **Commit:** ea36e03

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Date validation before type conversion | For datetime columns with check_date=True, pattern validation must run first so DATE_FORMAT errors are not masked by TYPE_CONVERSION from strptime |
| Include 'str' in select_dtypes | Pandas 3.0 separates 'str' and 'object' dtypes; including both ensures trim works on all string-like columns |
| Fast path falls back per-column not per-row | When vectorized conversion fails for a column, only that column does per-row processing; other columns stay vectorized |

## Verification Results

All plan verification steps passed:
1. Python import succeeds
2. 66/66 tests pass (0 failures)
3. Test count: 66 (requirement: 65+)
4. `fieldseparator` config key used (not `delimiter`)
5. No old `delimiter` key reads
6. All three error code constants present
7. Chunked validation constant present

## Self-Check: PASSED
