---
phase: 10-iterate-support
plan: 11
subsystem: engine/components/file
tags: [gap-closure, toctou, race-condition, file-list, sort, iterate]
dependency_graph:
  requires: []
  provides: [race-safe-file-sort]
  affects: [src/v1/engine/components/file/file_list.py]
tech_stack:
  added: []
  patterns: [try/except OSError wrapping pathlib.Path.stat(), staticmethod helpers]
key_files:
  created: []
  modified:
    - src/v1/engine/components/file/file_list.py
    - tests/v1/engine/components/file/test_file_list.py
decisions:
  - Use staticmethods on FileList class (consistent with existing codebase pattern) rather than module-level helpers
  - Return sort-stable defaults (0 / 0.0) on OSError so deleted files sort to front of ASC list without crashing
  - Log WARNING at OSError site (ASCII-only, no emojis) for RHEL compatibility
metrics:
  duration: "~5 minutes"
  completed: "2026-05-05T20:00:28Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 10 Plan 11: FileList Sort TOCTOU Race Fix Summary

Race-safe `_safe_stat_size` and `_safe_stat_mtime` staticmethods added to `FileList` to eliminate TOCTOU crash in `_sort_paths` when files are deleted between directory walk and sort key evaluation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wrap p.stat() in try/except OSError in _sort_paths | a532abc | src/v1/engine/components/file/file_list.py |
| 2 | Add TestSortPathsRaceCondition for TOCTOU sort race | 22e6afc | tests/v1/engine/components/file/test_file_list.py |

## What Was Built

### Task 1: Race-Safe Sort Key Helpers

Replaced two racy `p.exists() + p.stat()` lambda patterns in `FileList._sort_paths` with two new staticmethods:

- `_safe_stat_size(p)`: Returns `p.stat().st_size`, catches `OSError`, returns `0`, logs WARNING
- `_safe_stat_mtime(p)`: Returns `p.stat().st_mtime`, catches `OSError`, returns `0.0`, logs WARNING

The `ORDER_BY_FILESIZE` and `ORDER_BY_MODIFIEDDATE` branches in `_sort_paths` now use these helpers as sort keys instead of inline lambdas. The `ORDER_BY_FILENAME` and `ORDER_BY_NOTHING` branches are unaffected.

### Task 2: Race Condition Tests

Added `TestSortPathsRaceCondition` class to `tests/v1/engine/components/file/test_file_list.py` with two unit tests:

- `test_filesize_sort_survives_deleted_file`: Creates 3 files, deletes one before sort, asserts no `FileNotFoundError`, confirms real files still in result, asserts WARNING logged
- `test_modifieddate_sort_survives_deleted_file`: Same pattern for mtime sort

Total test count: 65 (63 original + 2 new), all passing.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None - the threat model (T-10-11-01) was fully addressed by the OSError wrapping in Task 1.

## Self-Check: PASSED

- `src/v1/engine/components/file/file_list.py`: modified (confirmed via grep)
- `tests/v1/engine/components/file/test_file_list.py`: modified (confirmed via pytest run)
- Commit a532abc: present in git log
- Commit 22e6afc: present in git log
- 65 tests pass: confirmed
- Old racy pattern `p.stat().*if p.exists()` count: 0 (confirmed)
- `except OSError` appears 2 times: confirmed
