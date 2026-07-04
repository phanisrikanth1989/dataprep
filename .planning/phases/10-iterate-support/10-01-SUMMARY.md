---
phase: 10-iterate-support
plan: "01"
subsystem: engine
tags: [engine, iterate, base-class, lifecycle, ITER-11]
dependency_graph:
  requires: []
  provides:
    - BaseIterateComponent with 9-hook lifecycle (src/v1/engine/base_iterate_component.py)
    - IterateStubComponent fixture (tests/v1/engine/conftest.py)
    - make_iterate_job_config fixture (tests/v1/engine/conftest.py)
  affects:
    - src/v1/engine/base_iterate_component.py
    - tests/v1/engine/conftest.py
    - tests/v1/engine/test_base_component.py
tech_stack:
  added: []
  patterns:
    - Iterator[Any] return type for prepare_iterations (D-A3)
    - 9-hook lifecycle in BaseIterateComponent (D-A5)
    - execute() override skipping data-pipeline steps (D-A2)
    - _iterate_depth scope field for nested-iterate support (D-A6)
key_files:
  created:
    - tests/v1/engine/test_base_iterate_component.py
  modified:
    - src/v1/engine/base_iterate_component.py
    - tests/v1/engine/conftest.py
    - tests/v1/engine/test_base_component.py
decisions:
  - Use iter(()) as the default value for iteration_iter (empty iterator, not None)
  - total_iterations=-1 is the sentinel for unbounded iterators (not 0)
  - finalize_iterations() kept as backward-compat synonym for finalize()
  - _process() raises NotImplementedError to prevent wrong entry point usage
  - ComponentStatus.ERROR (not FAILED) matches BaseComponent enum values
metrics:
  duration: ~25min
  completed: "2026-05-05"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
  files_created: 1
---

# Phase 10 Plan 01: BaseIterateComponent Lifecycle Rebuild Summary

Rebuilt `BaseIterateComponent` with a 9-hook lifecycle, iterator-based item
production (replacing the old list-based approach), an execute() override that
skips data-pipeline steps, and the _iterate_depth scope field. Fixed the critical
ITER-11 typo (_CURRENT_ITERATE -> _CURRENT_ITERATION). Added IterateStubComponent
and make_iterate_job_config fixtures to conftest.py for downstream Phase 10 plans.

## What Was Built

### Task 1: BaseIterateComponent Rewrite (ea850fb)

Replaced the old skeleton (~202 lines) with the new Phase 10 shape (~290 lines):

**New execute() override (D-A2):**
- Skips: `_select_mode`, `_execute_batch`, `_execute_streaming`, `_count_input_rows`,
  `_update_stats_from_result`, output schema validation
- Keeps: status transitions, `copy.deepcopy(_original_config)` (EXEC-06), `_validate_config`,
  `_resolve_expressions`
- Returns `{"main": None, "reject": None, "stats": ...}` -- iterate components produce
  no DataFrame output; the Executor drives body execution

**New 9 lifecycle hooks (D-A5):**
1. `prepare()` -- one-time setup, default no-op
2. `prepare_iterations(input_data)` -- abstract, returns `Iterator[Any]`
3. `should_stop(item, index)` -- default returns `False`
4. `before_iteration(item, index)` -- default no-op
5. `set_iteration_globalmap(item)` -- abstract
6. (body subjob executes via Executor)
7. `after_iteration(item, index, body_stats)` -- default no-op
8. `on_iteration_error(item, index, exc)` -- default returns `False` (re-raise)
9. `finalize()` -- default no-op

**Iterator-based items (D-A3):**
- `iteration_iter: Iterator[Any] = iter(())` replaces `iteration_items: list[Any] = []`
- `total_iterations: int = -1` sentinel (not 0); bounded subclasses set positive
- `get_next_iteration_context()` calls `next(self.iteration_iter)` instead of list indexing

**ITER-11 / D-F7 fix:**
- `get_next_iteration_context()` now writes `f"{self.id}_CURRENT_ITERATION"` to globalMap
- Old typo `_CURRENT_ITERATE` is gone from all code paths (only in docstrings explaining the fix)

**_iterate_depth field (D-A6):**
- `self._iterate_depth: int = 0` added to `__init__`
- Executor will set this at loop start in Phase 10-02
- ExecutionPlan will enforce depth=1 in Phase 10-02 (ConfigurationError on nesting)

**_process() removed:**
- Raises `NotImplementedError` to prevent wrong entry point usage
- Iterate components go through `execute()` override, not `BaseComponent._process`

**finalize_iterations() backward-compat stub:**
- Delegates to `finalize()` so any existing callers don't break

### Task 2: Test Infrastructure (25e6cac)

**New test file: tests/v1/engine/test_base_iterate_component.py (29 tests):**
- `TestCurrentIterationKeyRename` -- verifies _CURRENT_ITERATION key, asserts typo absent
- `TestPrepareIterationsIteratorContract` -- Iterator protocol, bounded/unbounded cases
- `TestExecuteOverride` -- skips data-pipeline steps, hook ordering, error propagation
- `TestLifecycleHooks` -- all 9 hooks callable with correct defaults
- `TestIterateDepthField` -- _iterate_depth defaults and mutability
- `TestIterateStubComponentFixture` -- validates conftest fixtures

**conftest.py additions:**
- `StubIterateItem` dataclass -- typed item for IterateStubComponent
- `IterateStubComponent` -- configurable test stub with config keys: items, globalmap_key_prefix,
  stop_after, fail_at. Consumed by Phase 10-02 (executor iterate loop tests) and 10-06
  (logging tests)
- `make_iterate_job_config` -- builds a complete job config dict with iterate source
  and body components connected via ITERATE flows

**test_base_component.py updates (Rule 1 auto-fix):**
- `ConcreteIterateComponent.prepare_iterations()` updated to return `iter(items)` and set
  `total_iterations` per D-A3 (was returning raw list)
- `TestBaseIterateComponentLifecycle.test_finalize_iterations_updates_stats` updated to
  reflect new behavior (finalize_iterations is a no-op; Executor accumulates stats)
- `TestBaseIterateComponentReset` tests updated: iteration_items -> iteration_iter,
  total_iterations resets to -1 (not 0), finalize_iterations updated

## ITER-11 Fix Verification

```
$ grep "_CURRENT_ITERATE[^I]" src/v1/engine/base_iterate_component.py
(31): (NOT _CURRENT_ITERATE). -- docstring explanation
(314): # canonical key is _CURRENT_ITERATION (NOT _CURRENT_ITERATE) -- inline comment
```

Both occurrences are in comments/docstrings explaining the fix. No code path writes the
typo key. The test `test_current_iteration_key_name` verifies the correct key is written
and the typo key is absent from globalMap.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ComponentStatus.FAILED reference in execute() override**
- **Found during:** GREEN phase of Task 1
- **Issue:** Initial execute() used `ComponentStatus.FAILED` which doesn't exist in the enum
  (actual values: PENDING, RUNNING, SUCCESS, ERROR, SKIPPED)
- **Fix:** Changed to `ComponentStatus.ERROR` to match BaseComponent behavior
- **Files modified:** src/v1/engine/base_iterate_component.py
- **Commit:** ea850fb

**2. [Rule 1 - Bug] Updated old interface tests in test_base_component.py**
- **Found during:** Task 2 regression testing
- **Issue:** `TestBaseIterateComponentLifecycle` and `TestBaseIterateComponentReset` in
  `test_base_component.py` tested the OLD interface (list-based iteration, old finalize_iterations
  behavior, iteration_items attribute). These tests failed after the Phase 10-01 rewrite.
- **Fix:** Updated `ConcreteIterateComponent.prepare_iterations()` to return `iter()`,
  updated tests to match new: total_iterations=-1 sentinel, finalize_iterations delegates
  to finalize(), iteration_iter replaces iteration_items
- **Files modified:** tests/v1/engine/test_base_component.py
- **Commit:** 25e6cac

## Known Stubs

None. This plan is a base-class and test-infrastructure plan. No UI components or data
stubs were introduced.

## Threat Surface

No new external-facing surface. BaseIterateComponent is an internal engine base class.
The only security-relevant surface change is the removal of `_process()` as a reachable
entry point (now raises NotImplementedError), which is a hardening improvement.

## Downstream Fixture Availability

Plans that can now use these fixtures:

| Plan | Fixture | Purpose |
|------|---------|---------|
| 10-02 | IterateStubComponent | Executor iterate loop tests without real components |
| 10-02 | make_iterate_job_config | Build iterate job configs for Executor tests |
| 10-03 | IterateStubComponent | Verify tFileList integrates with base lifecycle |
| 10-04 | IterateStubComponent | Verify tFlowToIterate integrates with base lifecycle |
| 10-06 | IterateStubComponent | Logging tests with configurable item counts |

## Self-Check: PASSED

Files confirmed created/modified:
- FOUND: src/v1/engine/base_iterate_component.py
- FOUND: tests/v1/engine/test_base_iterate_component.py
- FOUND: tests/v1/engine/conftest.py (modified)
- FOUND: tests/v1/engine/test_base_component.py (modified)

Commits confirmed:
- ea850fb: feat(10-01): rebuild BaseIterateComponent with 9-hook lifecycle and ITER-11 fix
- 25e6cac: feat(10-01): add BaseIterateComponent tests, IterateStubComponent, and conftest fixtures
- All 29 tests in test_base_iterate_component.py pass
- All 12 BaseIterateComponent tests in test_base_component.py pass
- Pre-existing failures confirmed unchanged (test_file_output_excel.py, test_unique_row.py,
  test_convert_type.py, test_full_pipeline.py)
