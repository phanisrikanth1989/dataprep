---
phase: 13-test-stabilization-bridge-jar-rebuild
plan: "05"
subsystem: engine/file
tags: [bug-fix, file_list, NB_FILE, globalMap, finalize]
dependency_graph:
  requires: ["13-01"]
  provides: ["BUG-FL-001 resolved"]
  affects: ["tests/integration/test_iterate_e2e.py"]
tech_stack:
  added: []
  patterns: ["globalMap.put in finalize() for definitive post-loop count"]
key_files:
  modified:
    - src/v1/engine/components/file/file_list.py
decisions:
  - "Applied global_map.put in finalize() with a None guard to protect unit-test isolation contexts where global_map is not injected."
  - "Used df[in_col] = inferred rather than loc-based assignment in the convert_type fallback (different plan, but same root-cause family)."
metrics:
  duration: "< 3 min"
  completed: "2026-05-10"
---

# Phase 13 Plan 05: file_list NB_FILE globalMap finalize put Summary

One-liner: Added `self.global_map.put(f"{self.id}_NB_FILE", total)` in FileList.finalize() so the definitive post-iteration NB_FILE count is written to globalMap after all iterations complete, matching Talend tFileList convention (BUG-FL-001).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add NB_FILE final-count put in file_list.py finalize() | bfffc32 | src/v1/engine/components/file/file_list.py |

## Changes Made

### Added after `self.stats["NB_FILE"] = total`:
```python
        if self.global_map is not None:
            self.global_map.put(f"{self.id}_NB_FILE", total)
```

The `set_iteration_globalmap()` method already puts `{id}_NB_FILE` per iteration (ending at `total` on the last iteration). The finalize() put makes the value definitive regardless of whether the last iteration's globalMap put was flushed correctly.

## Observation

The E2E tests (`TestJobTFileListExecution::test_executes_end_to_end`) already passed before this fix because `set_iteration_globalmap()` happens to leave the correct value after the last iteration. The finalize() put adds correctness insurance (especially for edge cases like 0 files where the loop never runs and NB_FILE would otherwise be absent from globalMap).

## Verification

- `pytest tests/integration/test_iterate_e2e.py -q` -- 11 passed, 1 skipped (no regression)
- `pytest tests/v1/engine/components/iterate/ -q` -- 27 passed
- `grep -n "global_map.put.*NB_FILE" src/v1/engine/components/file/file_list.py` returns 2 hits (per-iteration and finalize)

## Deviations from Plan

None -- plan executed exactly as written. Note that the E2E tests were already passing before the fix (the per-iteration put was sufficient for non-zero file counts). The finalize() put adds correctness for the zero-files edge case.

## Self-Check: PASSED

- src/v1/engine/components/file/file_list.py -- modified and committed
- Commit bfffc32 exists in git log
