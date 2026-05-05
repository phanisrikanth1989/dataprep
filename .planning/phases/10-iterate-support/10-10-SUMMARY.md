---
phase: 10-iterate-support
plan: 10
subsystem: engine
tags: [iterate, executor, base_iterate_component, lifecycle_hooks, cr-02, cr-03, cr-04]

requires:
  - phase: 10-iterate-support/10-02
    provides: "_execute_iterate_body implementation + BaseIterateComponent skeleton"

provides:
  - "Iterate loop driven via has_next_iteration()/get_next_iteration_context() public API (CR-02)"
  - "current_iteration_index advances correctly per iteration"
  - "Hook 8 (on_iteration_error) removed; errors-as-statuses contract documented (CR-03)"
  - "iter_local_failed_bodies scopes _any_body_die_on_error to current iteration only (CR-04)"
  - "TestIterateAPIContract proves all three CR fixes with 3 passing tests"

affects: [10-iterate-support, executor, base_iterate_component, test_executor_iterate]

tech-stack:
  added: []
  patterns:
    - "errors-as-statuses: _execute_component swallows all exceptions and returns string 'error'; iterate loop reads result strings, not exceptions"
    - "iter_local_failed_bodies: snapshot pre-iteration stats and diff post-stats to scope die_on_error check to current iteration only"
    - "while has_next_iteration() + get_next_iteration_context(): canonical API for driving bounded iterate loops"

key-files:
  created: []
  modified:
    - src/v1/engine/executor.py
    - src/v1/engine/base_iterate_component.py
    - tests/v1/engine/test_executor_iterate.py
    - tests/v1/engine/test_base_iterate_component.py

key-decisions:
  - "CR-02 fix: use while has_next_iteration() + get_next_iteration_context() instead of enumerate(iteration_iter); this is the documented public API and advances current_iteration_index"
  - "CR-03 resolution: remove Hook 8 entirely (on_iteration_error method deleted); the except ComponentExecutionError arm was unreachable because _execute_component returns error string, never re-raises"
  - "CR-04 fix: snapshot pre_iter_stats dict before body runs; compute iter_local_failed_bodies as diff of error-status changes; pass to _any_body_die_on_error to avoid stale execution_stats from prior iterations"
  - "TDD test fix: patch _process not execute for stale-stats test -- patching execute bypasses die_on_error assignment from config, causing false die_on_error=True"

requirements-completed: [EXEC-04, EXEC-05, EXEC-06, ITER-11]

duration: 25min
completed: 2026-05-05
---

# Phase 10 Plan 10: Iterate Loop Trifecta (CR-02 + CR-03 + CR-04) Summary

**Executor iterate loop fixed: CR-02 uses public API advancing current_iteration_index, CR-03 removes unreachable Hook 8, CR-04 scopes die_on_error check to per-iteration failure set**

## Performance

- **Duration:** 25 min
- **Started:** 2026-05-05T00:00:00Z
- **Completed:** 2026-05-05T00:00:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- CR-02: Replaced `enumerate(iter_component.iteration_iter)` with `while iter_component.has_next_iteration()` + `iter_component.get_next_iteration_context()` -- `current_iteration_index` now advances correctly per iteration; duplicate `set_iteration_globalmap` and `_CURRENT_ITERATION` writes removed
- CR-03: Removed `on_iteration_error` (Hook 8) from `BaseIterateComponent` and the unreachable `except ComponentExecutionError` arm from `_execute_iterate_body`; module docstring updated to document the errors-as-statuses architecture
- CR-04: `_any_body_die_on_error` now accepts `iter_failed_bodies` set built from pre/post-iteration stat diff; stale error status from iteration N cannot cause spurious early termination in iteration N+1

## Task Commits

1. **Task 1: Refactor _execute_iterate_body (CR-02 + CR-03 + CR-04)** - `bfe82f0` (fix)
2. **Task 2: Remove on_iteration_error from BaseIterateComponent** - `33bee47` (fix) -- includes updating test_base_iterate_component.py tests that referenced the removed method
3. **Task 3 RED: Add failing TestIterateAPIContract tests** - `f162ab8` (test)
4. **Task 3 GREEN: TestIterateAPIContract tests pass** - `4a86137` (feat)

## Files Created/Modified

- `src/v1/engine/executor.py` - Three targeted changes: while-loop API, removed dead except arm, iter_local_failed_bodies + updated _any_body_die_on_error signature
- `src/v1/engine/base_iterate_component.py` - Removed on_iteration_error method; updated module docstring to 8-hook lifecycle with CR-03 explanation; updated class docstring reference
- `tests/v1/engine/test_executor_iterate.py` - Added TestIterateAPIContract class with 3 tests proving CR-02/03/04
- `tests/v1/engine/test_base_iterate_component.py` - Updated TestLifecycleHooks: renamed to 8-hooks, replaced test_on_iteration_error_default_false with test_on_iteration_error_removed

## Decisions Made

- CR-02: Use public API (`has_next_iteration`/`get_next_iteration_context`) instead of direct iterator access -- this is the documented contract and the only place `current_iteration_index` is advanced
- CR-03: Remove Hook 8 entirely rather than wiring it through `_execute_component`; the errors-as-statuses architecture is cleaner and matches existing pattern
- CR-04: Snapshot-and-diff approach for `iter_local_failed_bodies` is the minimal surgical change; the `_any_body_die_on_error` method now checks `die_on_error` directly on the component (not via `execution_stats`) which is cleaner and avoids any stale-state race
- Test design: Patch `_process` (not `execute`) for the stale-stats test -- patching `execute` would bypass `die_on_error` assignment from config, causing the test to falsely stop on iteration 1 even with CR-04 fix in place

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_base_iterate_component.py tests that used on_iteration_error**
- **Found during:** Task 2 (Remove on_iteration_error from BaseIterateComponent)
- **Issue:** Two tests in test_base_iterate_component.py called `on_iteration_error` directly (`test_all_nine_hooks_callable` listed it in the hooks list; `test_on_iteration_error_default_false` tested its return value). Removing the method caused these 2 tests to fail.
- **Fix:** Renamed `test_all_nine_hooks_callable` to `test_all_eight_hooks_callable` and removed `on_iteration_error` from the hook list; replaced `test_on_iteration_error_default_false` with `test_on_iteration_error_removed` which asserts the method is absent (documents the CR-03 removal).
- **Files modified:** `tests/v1/engine/test_base_iterate_component.py`
- **Verification:** `pytest tests/v1/engine/test_base_iterate_component.py` -- 29 passed
- **Committed in:** `33bee47` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed stale-stats test to patch _process not execute**
- **Found during:** Task 3 GREEN phase (first run of test_stale_stats_do_not_trigger_die_on_error)
- **Issue:** The test patched `body_a.execute` to raise on iteration 1. However, `BaseComponent.__init__` sets `die_on_error = True` by default; `execute()` sets it to `False` from config. Patching `execute` before it runs meant `die_on_error` stayed `True`, causing the iterate loop to stop after iteration 1 -- but for the wrong reason (not a stale stats issue, a test design issue).
- **Fix:** Changed to a `FailFirstThenOkStub` class that overrides `_process` instead of patching `execute`. This allows the full `execute()` lifecycle to run (including `die_on_error = False` from config) before `_process` raises.
- **Files modified:** `tests/v1/engine/test_executor_iterate.py`
- **Verification:** `pytest tests/v1/engine/test_executor_iterate.py::TestIterateAPIContract` -- 3 passed
- **Committed in:** `4a86137` (Task 3 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs)
**Impact on plan:** Both auto-fixes necessary for test correctness. No scope creep; both directly caused by the plan's intended changes.

## Issues Encountered

- Die-on-error test design issue: discovered that `die_on_error` is initialized to `True` in `BaseComponent.__init__` and only overwritten to `False` during `execute()`. Patching `execute` directly bypasses this, giving a false positive that looked like a CR-04 regression. Fixed by patching `_process` instead (the correct pattern, consistent with all other failure tests in the test file).

## Next Phase Readiness

- Iterate loop is now correctly driven via the documented public API
- `current_iteration_index` tracks correctly -- downstream components reading `{id}_CURRENT_ITERATION` via globalMap will see correct values
- Hook 8 removal is clean -- no remaining references in executor or base class
- `_any_body_die_on_error` is safe across iterations -- no spurious early termination

---
*Phase: 10-iterate-support*
*Completed: 2026-05-05*
