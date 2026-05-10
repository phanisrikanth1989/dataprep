---
phase: 13-test-stabilization-bridge-jar-rebuild
plan: "04"
subsystem: engine/transform
tags: [bug-fix, convert_type, manualtable, pandas-3, StringDtype, numeric-inference]
dependency_graph:
  requires: ["13-01"]
  provides: ["BUG-CT-001 resolved"]
  affects: ["tests/v1/engine/components/transform/test_convert_type.py"]
tech_stack:
  added: []
  patterns: ["pd.to_numeric whole-column replacement for StringDtype compatibility"]
key_files:
  modified:
    - src/v1/engine/components/transform/convert_type.py
decisions:
  - "Used df[in_col] = inferred (whole-column replacement) rather than df.loc[ok_mask, in_col] = inferred because loc-based setitem cannot change column dtype -- it rejects numeric values when the column has StringDtype."
  - "Applied pd.to_numeric to all rows (df[in_col]) rather than ok_mask subset, matching AUTOCAST semantics: best-effort whole-column inference, no row rejection."
metrics:
  duration: "< 5 min"
  completed: "2026-05-10"
---

# Phase 13 Plan 04: convert_type in-place MANUALTABLE numeric fallback Summary

One-liner: Added a pd.to_numeric whole-column fallback in convert_type.py for MANUALTABLE entries where target_dtype resolves to "object" and in_col == out_col, matching Talend tConvertType MANUALTABLE default behavior (BUG-CT-001).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add numeric inference fallback in convert_type.py | c246625 | src/v1/engine/components/transform/convert_type.py |

## Changes Made

### After `target_dtype = output_schema_types.get(out_col, ...)` line, inserted:

```python
# Talend MANUALTABLE default: when no output schema provides a target type,
# attempt pd.to_numeric() for in-place casts (input_column == output_column).
# This matches tConvertType's default MANUALTABLE behavior (per D-B3).
# errors="coerce" -> non-numeric values become NaN (no rows rejected).
# Use whole-column replacement (df[col] = series) rather than loc-based
# setitem so that StringDtype columns are correctly re-typed to numeric.
if target_dtype == "object" and in_col == out_col:
    inferred = pd.to_numeric(df[in_col], errors="coerce")
    if inferred.notna().any():
        df[in_col] = inferred
    continue  # skip per-row loop; whole-column operation done
```

The fallback only fires when:
- `target_dtype == "object"` (no explicit type declared in output schema)
- `in_col == out_col` (in-place cast, not a column rename/copy)

### Deviation from plan spec

Plan specified `df.loc[ok_mask, in_col] = inferred`. This fails on pandas 3.0 StringDtype columns because loc-based setitem cannot change the column dtype -- pandas raises `TypeError: Invalid value for dtype 'str'. Value should be a string or missing value.` 

Fix: use `df[in_col] = inferred` (whole-column series replacement) which re-types the column to the inferred numeric dtype. Applied to all rows (not ok_mask subset) matching AUTOCAST whole-column semantics.

## Verification

- `pytest tests/v1/engine/components/transform/test_convert_type.py -q` -- 24 passed, 0 failed
- `pytest tests/v1/engine/components/transform/test_convert_type.py::TestManualTable::test_string_to_int_cast -v` -- PASSED
- `grep -n "to_numeric" src/v1/engine/components/transform/convert_type.py` -- returns hits at fallback location

## Deviations from Plan

**[Rule 1 - Bug] Fixed loc-based setitem incompatibility with pandas 3.0 StringDtype**
- Found during: Task 1 (first test run)
- Issue: `df.loc[ok_mask, in_col] = inferred` raises TypeError when column is StringDtype because loc setitem preserves existing dtype
- Fix: replaced with `df[in_col] = inferred` (whole-column replacement, re-types column to numeric)
- Files modified: convert_type.py (same file, same block)
- Commit: c246625

## Self-Check: PASSED

- src/v1/engine/components/transform/convert_type.py -- modified and committed
- Commit c246625 exists in git log
