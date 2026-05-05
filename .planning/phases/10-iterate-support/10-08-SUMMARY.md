---
phase: 10-iterate-support
plan: 08
subsystem: testing
tags: [integration, tFileExist, run-if, globalmap, pytest]

# Dependency graph
requires:
  - phase: 10-02
    provides: executor iterate loop and trigger infrastructure used for RUN_IF branching verification

provides:
  - Integration test suite verifying tFileExist ITER-08 (file_name vs file_path config keys) and ITER-09 ({id}_EXISTS and {id}_FILENAME globalMap vars) via 10 tests in 4 classes including a D-K3 RUN_IF branching scenario

affects: [future phases touching trigger_manager, file_exist, or RunIf condition evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RUN_IF condition as Python literal: use globalMap.get('KEY') == Value; TriggerManager._resolve_global_map_refs() replaces the call with Python repr before eval()"
    - "ETLEngine global_map access pattern: engine = ETLEngine(config); engine.execute(); engine.global_map.get(key) -- execute() return value only contains get_all_stats() (component NB_LINE stats), NOT the full _map"
    - "tPython marker-file pattern: pd.DataFrame([{'fired': True}]).to_csv(path, index=False) -- pandas file I/O bypasses __builtins__ whitelist restriction"
    - "M-6 fallback class: direct FileExistComponent instantiation for unit-level ITER verification without engine overhead"

key-files:
  created:
    - tests/integration/__init__.py
    - tests/integration/test_file_exist_e2e.py
  modified: []

key-decisions:
  - "trigger dict key is 'type' (not 'trigger_type') -- matches _initialize_triggers() reading trigger['type']"
  - "Use engine.global_map.get() directly after execute() for _EXISTS/_FILENAME; execute() return value contains get_all_stats() (component NB_LINE only) not the full map"
  - "tPython pd.DataFrame.to_csv() marker pattern works without Java bridge -- pandas uses CPython open() internally, unaffected by exec __builtins__ whitelist"
  - "No source code changes to tFileExist -- component is GREEN per Phase 9 audit, verify-only plan"

patterns-established:
  - "Integration test package created at tests/integration/ for Phase 10+ engine-level tests"

requirements-completed: [ITER-08, ITER-09]

# Metrics
duration: 15min
completed: 2026-05-05
---

# Phase 10 Plan 08: tFileExist Integration Tests (ITER-08, ITER-09, D-K3) Summary

**10 integration/unit tests confirming tFileExist's file_name/file_path key aliases and {id}_EXISTS/{id}_FILENAME globalMap vars via a real RUN_IF branching scenario, with no production code changes**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-05T18:28:00Z
- **Completed:** 2026-05-05T18:43:35Z
- **Tasks:** 1 of 1
- **Files modified:** 2 (both new)

## Accomplishments

- Created `tests/integration/` package (new: `__init__.py` + test module)
- 10 test methods in 4 classes; all pass in 0.46s without Java bridge
- ITER-08 closed: both `file_name` (preferred) and `file_path` (legacy alias) exercised at engine and component level
- ITER-09 closed: `tFileExist_1_EXISTS` (bool) and `tFileExist_1_FILENAME` (str) verified at engine and component level
- D-K3 closed: RUN_IF fires marker-file write when file exists, skips when missing
- No changes to `src/v1/engine/components/file/file_exist.py` (verify-only plan)

## Task Commits

1. **Task 1: Integration test for tFileExist + RUN_IF branching** - `02b41be` (feat)

**Plan metadata:** (see SUMMARY commit below)

## Files Created/Modified

- `tests/integration/__init__.py` - New integration test package init
- `tests/integration/test_file_exist_e2e.py` - 10 tests across 4 classes (TestFileExistConfigKeyAliases, TestGlobalMapVariables, TestRunIfBranching, TestFileExistGlobalMapDirect)

## Decisions Made

- **Trigger dict key format:** The engine's `_initialize_triggers()` reads `trigger['type']`, not `trigger['trigger_type']`. The PLAN.md sample code had the wrong key; used `type` in the actual implementation.
- **ETLEngine globalMap access:** `execute()` return value contains `get_all_stats()` (NB_LINE component stats), not the full `_map`. Accessed `engine.global_map.get(key)` directly after calling `execute()` to check `_EXISTS` and `_FILENAME`.
- **Marker file pattern:** `pd.DataFrame([{'fired': True}]).to_csv(path, index=False)` -- pandas file I/O calls the CPython built-in `open()` internally; the tPython `__builtins__` whitelist only restricts the exec namespace, not pandas itself. Verified by running tests.
- **M-6 fallback class:** Added `TestFileExistGlobalMapDirect` with direct `FileExistComponent` instantiation to provide a lower-level backstop that survives engine or TriggerManager regressions.

## Deviations from Plan

None - plan executed exactly as written. The PLAN.md sample code used `trigger_type` as the config dict key, but this was noted as a guidance template; the correct key `type` was used in the implementation per inspection of `engine.py:_initialize_triggers()`.

## Issues Encountered

None. All 10 tests passed on first run.

## RUN_IF Condition Design

The condition string `globalMap.get('tFileExist_1_EXISTS') == True` is Python-evaluated:

1. `TriggerManager._resolve_global_map_refs()` replaces `globalMap.get('tFileExist_1_EXISTS')` with `repr(True)` or `repr(False)` (reading from the live GlobalMap instance)
2. The resulting expression `True == True` or `False == True` is evaluated via `eval()` with sandboxed globals
3. No Java bridge is invoked -- no `@pytest.mark.java` marker required

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Tests use `tmp_path` (pytest per-test isolation) for all file I/O. No threat flags.

## Known Stubs

None. Tests exercise real production code paths.

## Next Phase Readiness

- ITER-08 and ITER-09 requirements closed
- tFileExist is confirmed GREEN at integration level
- `tests/integration/` package established for future Phase 10 integration tests
- No blockers

---

*Phase: 10-iterate-support*
*Completed: 2026-05-05*

## Self-Check: PASSED

- `tests/integration/__init__.py`: FOUND
- `tests/integration/test_file_exist_e2e.py`: FOUND
- Commit `02b41be`: FOUND
- `git status --porcelain src/v1/engine/components/file/file_exist.py`: empty (no source changes)
- `pytest tests/integration/test_file_exist_e2e.py -x`: 10 passed
