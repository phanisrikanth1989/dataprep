---
phase: 04-file-i-o-components
reviewed: 2026-04-15T02:30:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/v1/engine/components/file/file_input_delimited.py
  - src/v1/engine/components/file/file_output_delimited.py
  - tests/v1/engine/components/file/test_file_input_delimited.py
  - tests/v1/engine/components/file/test_file_output_delimited.py
  - tests/v1/engine/components/file/test_file_io_integration.py
findings:
  critical: 1
  warning: 2
  info: 3
  total: 6
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-15T02:30:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 4 file I/O component rewrites: `FileInputDelimited`, `FileOutputDelimited`, and their associated unit and integration test suites. The code is well-structured overall with clear separation of concerns, proper docstrings, consistent error handling, and good test coverage. Three issues were found: one critical bug in field count validation that will cause incorrect reject behavior in production, one warning-level inconsistency in the bool type conversion fast path, and one warning about missing error wrapping in the output component's write path. Three info-level items noted for code quality.

## Critical Issues

### CR-01: CHECK_FIELDS_NUM Counts Non-Empty Fields Instead of Actual Fields

**File:** `src/v1/engine/components/file/file_input_delimited.py:595-598`
**Issue:** The field count validation counts non-empty fields rather than total fields per row. Talend's `CHECK_FIELDS_NUM` validates that the row was parsed into the correct number of columns (i.e., the correct number of delimiters were found). The current implementation counts only non-empty values, so a row like `1;;30.0` (3 fields, one empty) would report `non_empty=2` and be incorrectly rejected when `expected_col_count=3`. This breaks feature parity with Talend and will cause valid rows with nullable/empty columns to be routed to the reject flow.
**Fix:**
```python
# Replace lines 595-598:
# Current (wrong):
non_empty = sum(
    1 for v in row_values
    if str(v).strip() != ""
)
if non_empty != expected_col_count:

# Fixed:
actual_field_count = len(row_values)
if actual_field_count != expected_col_count:
```

## Warnings

### WR-01: Vectorized Bool Conversion Silently Produces NaN for Unmapped Values

**File:** `src/v1/engine/components/file/file_input_delimited.py:545-549`
**Issue:** `_vectorized_convert` for bool type uses `series.map(dict)` with a limited set of keys (`true`, `false`, `True`, `False`, `1`, `0`). When `map()` encounters a value not in the dict (e.g., `"yes"`, `"no"`, `"YES"`, `"TRUE"`, or any invalid value), it returns `NaN` silently -- no `ValueError` is raised. This means the fast path never falls back to per-row conversion for bool columns, and values like `"yes"` silently become `NaN` instead of `True`. By contrast, `_convert_value` (the per-row fallback) correctly handles `"yes"`/`"no"` and raises `ValueError` for truly invalid values. The two paths produce different results for the same input.
**Fix:**
```python
elif col_type in ("bool",):
    mapping = {
        "true": True, "false": False, "True": True, "False": False,
        "1": True, "0": False, "yes": True, "no": False,
        "Yes": True, "No": False, "YES": True, "NO": False,
    }
    mapped = series.map(mapping)
    if mapped.isna().any():
        # Some values not in mapping -- force fallback to per-row
        raise ValueError("Unmapped bool values found")
    return mapped
```

### WR-02: Output Write Operations Not Wrapped in FileOperationError

**File:** `src/v1/engine/components/file/file_output_delimited.py:273-318`
**Issue:** `_write_file` calls `df.to_csv()` and `_write_csv_mode()` without try/except. If a write fails (permissions denied, disk full, encoding error), the raw OS/pandas exception propagates unwrapped. The input component wraps all I/O in `FileOperationError` (lines 287-293, 359-366), but the output component does not. While `BaseComponent.execute()` catches everything as `ComponentExecutionError`, the inconsistency means downstream error handlers checking for `FileOperationError` specifically (e.g., `die_on_error` logic) will not match.
**Fix:**
```python
def _write_file(self, df, filepath, field_sep, line_sep, encoding,
                include_header, csv_option, text_enclosure, escape_char, append):
    mode = "a" if append else "w"
    try:
        if csv_option:
            self._write_csv_mode(
                df, filepath, field_sep, line_sep, encoding,
                include_header, text_enclosure, escape_char, mode,
            )
        else:
            df.to_csv(
                filepath, sep=field_sep, header=include_header,
                index=False, encoding=encoding, quoting=csv.QUOTE_NONE,
                lineterminator=line_sep, mode=mode, escapechar="\\",
            )
    except Exception as e:
        raise FileOperationError(
            f"[{self.id}] Failed to write file '{filepath}': {e}"
        ) from e
```

## Info

### IN-01: Duplicated _unescape_separator Logic Across Both Components

**File:** `src/v1/engine/components/file/file_input_delimited.py:698-714` and `src/v1/engine/components/file/file_output_delimited.py:475-493`
**Issue:** `_unescape_separator` is implemented twice -- once as a `@staticmethod` on `FileInputDelimited` and once as a module-level function in `file_output_delimited.py`. The two implementations are functionally equivalent but have different key ordering in their dicts. Consider extracting to a shared utility in a `_file_utils.py` module within the file package.
**Fix:** Extract to a shared module to eliminate duplication: `src/v1/engine/components/file/_file_utils.py`.

### IN-02: Misleading Comment "Try longest match first" in Output Unescape

**File:** `src/v1/engine/components/file/file_output_delimited.py:491`
**Issue:** The comment `# Try longest match first` is misleading. The function performs an exact dict key lookup (`if sep in replacements`), not a longest-match substring search. Dict key lookup does not have an ordering concept. The code is correct, but the comment implies a different algorithm than what executes.
**Fix:** Change the comment to `# Exact match against known escape sequences`.

### IN-03: _vectorized_convert Does Not Handle "Decimal" Type

**File:** `src/v1/engine/components/file/file_input_delimited.py:525-552`
**Issue:** `_vectorized_convert` handles `int`, `long`, `float`, `double`, `bool`, and `datetime` but omits `Decimal` (which `_convert_value` at line 758-760 handles). If a schema column has `type: "Decimal"`, the vectorized path will return the series unchanged as strings, while per-row conversion would produce `Decimal` objects. This is a minor inconsistency -- the vectorized path falls through to `return series` which keeps the value as a string, and `validate_schema` downstream may or may not handle it. This does not cause a crash but may produce type inconsistencies.
**Fix:** Add a Decimal branch to `_vectorized_convert`, or document that Decimal columns always use the per-row fallback.

---

_Reviewed: 2026-04-15T02:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
