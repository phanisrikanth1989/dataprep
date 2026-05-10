---
phase: 13-test-stabilization-bridge-jar-rebuild
plan: "03"
subsystem: engine/aggregate
tags: [bug-fix, pandas-3, StringDtype, case-insensitive, dedup]
dependency_graph:
  requires: ["13-01"]
  provides: ["BUG-UNIQ-001 resolved"]
  affects: ["tests/v1/engine/components/aggregate/test_unique_row.py"]
tech_stack:
  added: []
  patterns: ["pd.api.types.is_object_dtype / is_string_dtype for pandas 3.0 StringDtype compatibility"]
key_files:
  modified:
    - src/v1/engine/components/aggregate/unique_row.py
decisions:
  - "Used pd.api.types dual check (is_object_dtype OR is_string_dtype) to handle both legacy object columns and pandas 3.0 StringDtype columns without branching on version."
  - "Line 143 (dup_ci rebuild) was left unchanged -- it is only reached when temp_map is non-empty, which means line 119 already passed the dtype check, so dup_ci[col] is guaranteed string-compatible."
metrics:
  duration: "< 2 min"
  completed: "2026-05-10"
---

# Phase 13 Plan 03: unique_row pandas 3.0 StringDtype guard Summary

One-liner: Replaced `work[col].dtype == object` with `pd.api.types.is_object_dtype(work[col]) or pd.api.types.is_string_dtype(work[col])` at unique_row.py line 119 so case-insensitive dedup works correctly on pandas 3.0 StringDtype columns (BUG-UNIQ-001).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix pandas 3.0 StringDtype guard in unique_row.py | 9cf0c91 | src/v1/engine/components/aggregate/unique_row.py |

## Changes Made

### Before (line 119):
```python
if not col_case.get(col, True) and work[col].dtype == object:
```

### After (line 119):
```python
if not col_case.get(col, True) and (
    pd.api.types.is_object_dtype(work[col]) or pd.api.types.is_string_dtype(work[col])
):
```

Root cause: pandas 3.0 with Copy-on-Write defaults string columns to `StringDtype` instead of `object`. The old equality check returned False for StringDtype, silently skipping the `.str.lower()` temp column and causing case-sensitive comparison when case-insensitive was requested.

## Verification

- `grep -n "dtype == object" unique_row.py` returns 0 hits
- `grep -n "is_string_dtype\|is_object_dtype" unique_row.py` returns hits at line ~119
- `pytest tests/v1/engine/components/aggregate/test_unique_row.py -q` -- 42 passed, 0 failed

## Deviations from Plan

None -- plan executed exactly as written. Line 143 confirmed to not need a change (only reachable when temp_map is non-empty, which requires line 119 to have passed).

## Self-Check: PASSED

- src/v1/engine/components/aggregate/unique_row.py -- modified and committed
- Commit 9cf0c91 exists in git log
