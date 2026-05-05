---
phase: 10-iterate-support
plan: 02
subsystem: engine
tags: [executor, execution-plan, output-router, iterate, bfs, reject-accumulation]

requires:
  - phase: 10-01-iterate-support
    provides: BaseIterateComponent with 9-hook lifecycle, IterateStubComponent in conftest

provides:
  - OutputRouter.drain_reject_flows: drains reject-type flows from body component set per iteration
  - OutputRouter.clear_partial_subjob_flows: body-subset-aware flow clear with cross-subjob preservation
  - ExecutionPlan._build_iterate_body_plan: BFS from iterate targets to compute intra-subjob body set
  - ExecutionPlan._detect_nested_iterate: raises ConfigurationError on depth>1 iterate nesting
  - ExecutionPlan.get_iterate_body_plan: public API returning pre-computed body SubjobPlan
  - Executor._execute_subjob_plan: extracted inner loop of _execute_subjob for iterate reuse
  - Executor._execute_iterate_body: drives body N times per iteration item with full lifecycle
  - 39 unit tests covering EXEC-04, EXEC-05, EXEC-06 and all iterate loop semantics

affects: [10-03, 10-04, 10-07, any future iterate component phases]

tech-stack:
  added: []
  patterns:
    - "BFS from iterate edge target following FLOW + outbound trigger edges, stopping at cross-subjob components"
    - "drain-and-accumulate pattern: per-iteration reject drain into buffer, concat at loop end"
    - "_execute_subjob_plan extracted from _execute_subjob for plan-direct reuse"
    - "_ITERATE_TYPES frozenset as extension point for future iterate component registration"

key-files:
  created:
    - tests/v1/engine/test_output_router_iterate.py
    - tests/v1/engine/test_execution_plan_iterate.py
    - tests/v1/engine/test_executor_iterate.py
  modified:
    - src/v1/engine/output_router.py
    - src/v1/engine/execution_plan.py
    - src/v1/engine/executor.py

key-decisions:
  - "Body components added to body_components_executed_by_iterate set so outer subjob loop skips them"
  - "Empty iterate (0 items): body components marked success in trigger_manager so OnSubjobOk fires"
  - "die_on_error=True on body component: _any_body_die_on_error helper breaks iterate loop early (D-E6)"
  - "_ITERATE_TYPES hardcoded in execution_plan.py as frozenset; future iterate types add here"
  - "drain_reject_flows uses flow.get(type) check not _FLOW_TYPE_TO_RESULT_KEY lookup (pure name check)"

requirements-completed: [EXEC-04, EXEC-05, EXEC-06]

duration: 45min
completed: 2026-05-06
---

# Phase 10 Plan 02: Iterate Engine Execution Loop Summary

**Iterate execution loop in Executor driving body N times per item, with BFS body-subgraph detection, nested-iterate protection, and per-iteration REJECT accumulation**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-06
- **Completed:** 2026-05-06
- **Tasks:** 3
- **Files modified:** 6 (3 source, 3 test)

## Accomplishments

- OutputRouter gains `drain_reject_flows` + `clear_partial_subjob_flows` for iterate body cleanup
- ExecutionPlan gains BFS body-subgraph computation for all iterate components at construction time
- Executor gains `_execute_iterate_body` that runs body N times per iteration item with full lifecycle hooks, stats rollup, and REJECT accumulation
- 39 unit tests covering EXEC-04/05/06, BFS correctness, nested-iterate detection, trigger semantics (D-C1, D-C2), REJECT accumulation, tDie termination, die_on_error semantics, and empty iterate

## Task Commits

1. **Task 1: OutputRouter helpers** - `cd13805` (feat)
2. **Task 2: ExecutionPlan body-subgraph BFS + nested-iterate detection** - `5b4b654` (feat)
3. **Task 3: Executor._execute_iterate_body + _execute_subjob_plan refactor** - `a7b8359` (feat)

## Files Created/Modified

- `src/v1/engine/output_router.py` - Added `drain_reject_flows` and `clear_partial_subjob_flows`
- `src/v1/engine/execution_plan.py` - Added `_ITERATE_TYPES`, `_build_iterate_body_plan`, `_detect_nested_iterate`, `_topo_sort_body`, `get_iterate_body_plan`; steps 8+9 in `__init__`
- `src/v1/engine/executor.py` - Refactored `_execute_subjob` -> `_execute_subjob` + `_execute_subjob_plan`; added `_execute_iterate_body`, `_any_body_die_on_error`, `_snapshot_body_stats`, `_log_iteration_progress`; iterate detection branch in `_execute_subjob_plan`
- `tests/v1/engine/test_output_router_iterate.py` - 9 tests for drain/clear helpers
- `tests/v1/engine/test_execution_plan_iterate.py` - 15 tests for BFS + nested detection
- `tests/v1/engine/test_executor_iterate.py` - 15 tests for iterate loop (EXEC-04/05/06 + failure/trigger/stats)

## Decisions Made

- **body_components_executed_by_iterate set:** The outer `_execute_subjob_plan` loop needs to skip body components after the iterate body runs. Used a local set tracked per subjob plan execution to mark body components as "already handled by iterate."
- **Empty iterate trigger fix:** When 0 items, body components never execute but are marked in `executed_components`. The trigger_manager also needs them marked as "success" so `_check_subjob_ok` can fire OnSubjobOk. Added `trigger_manager.set_component_status(body_id, "success")` for body components with no prior status.
- **die_on_error=True stops loop:** Added `_any_body_die_on_error(body_plan)` helper that checks `execution_stats` for failed body components with `die_on_error=True`. Breaks iterate loop when found, matching Talend behavior (D-E6).
- **reject accumulation test design:** Cross-subjob reject sink (in separate subjob) needed to correctly test REJECT accumulation; intra-body reject consumers would consume the data before drain.
- **_ITERATE_TYPES frozenset in execution_plan.py:** Provides a single extension point for future iterate components (tForeach, tLoop). Phase 10-03 and 10-04 components must be added here.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Empty iterate with 0 items: OnSubjobOk trigger not firing**
- **Found during:** Task 3 (test_empty_iterate_fires_subjob_ok)
- **Issue:** Body components added to `executed_components` via the iterate body exit code, but `trigger_manager.set_component_status` was not called. `_check_subjob_ok` checks ALL subjob components for "success" status; body components with unknown status caused OnSubjobOk to not fire.
- **Fix:** After body components are added to `executed_components`, set their status in trigger_manager to "success" only if not already set.
- **Files modified:** `src/v1/engine/executor.py`
- **Committed in:** a7b8359 (Task 3 commit)

**2. [Rule 1 - Bug] die_on_error=True on body component not stopping iterate loop**
- **Found during:** Task 3 (test_die_on_error_true_stops_loop)
- **Issue:** `_execute_subjob_plan` returns "error" when die_on_error=True body component fails, but `_execute_iterate_body` only checked for tDie (exit_code) to break. The loop continued to the next iteration.
- **Fix:** Added `_any_body_die_on_error(body_plan)` that checks `execution_stats` for failed body components with die_on_error=True; breaks the iterate loop if found.
- **Files modified:** `src/v1/engine/executor.py`
- **Committed in:** a7b8359 (Task 3 commit)

**3. [Rule 1 - Bug] Body component executes twice per iteration (once in outer loop, once in body)**
- **Found during:** Task 3 (test_body_runs_per_item: got 4 instead of 3 calls)
- **Issue:** Body components are in the same subjob as the iterate source. The outer `_execute_subjob_plan` loop reached them after the iterate body returned and executed them again.
- **Fix:** Added `body_components_executed_by_iterate` set to track body components handled by the iterate loop; outer subjob loop skips them.
- **Files modified:** `src/v1/engine/executor.py`
- **Committed in:** a7b8359 (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All 3 were correctness bugs discovered during test implementation. No scope creep.

## Issues Encountered

- Pre-existing test failure in `test_unique_row.py::TestCaseSensitivity::test_case_insensitive_dict_deduplicates` -- unrelated to Phase 10-02, logged as out-of-scope, not fixed.
- Reject accumulation test required cross-subjob design: intra-body reject consumers consume data before drain. Updated test to use separate subjob for reject sink.

## Known Stubs

None - all iterate loop orchestration is fully wired.

## Next Phase Readiness

- `_execute_iterate_body` is fully operational and tested. Phase 10-03 (tFileList) and 10-04 (tFlowToIterate) can implement `prepare_iterations` + `set_iteration_globalmap` and the loop runs automatically.
- `get_iterate_body_plan` public API is in place; iterate components registered in `_ITERATE_TYPES` get their body plans pre-computed at ExecutionPlan construction.
- EXEC-04, EXEC-05, EXEC-06 requirements fully covered.

---
*Phase: 10-iterate-support*
*Completed: 2026-05-06*
