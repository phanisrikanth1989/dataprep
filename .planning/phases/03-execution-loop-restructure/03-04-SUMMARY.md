---
phase: 03-execution-loop-restructure
plan: 04
subsystem: engine
tags: [executor, subjob, trigger, deque, stall-detection, engine-rewrite]

requires:
  - phase: 03-01
    provides: ComponentRegistry with REGISTRY singleton and @REGISTRY.register()
  - phase: 03-02
    provides: ExecutionPlan with DAG, topo sort, validation, cross-subjob flow metadata
  - phase: 03-03
    provides: OutputRouter with route_outputs, get_input_data, clear_subjob_flows
provides:
  - Executor class with _execute_subjob() as Phase 10 iterate building block
  - Thin ETLEngine delegating to Executor/ExecutionPlan/OutputRouter/REGISTRY
  - REGISTRY exported from src/v1/engine/__init__.py for component decorators
affects: [phase-04-file-components, phase-05-control-components, phase-10-iterate, all-component-phases]

tech-stack:
  added: []
  patterns:
    - "Iterative deque-based subjob queue instead of recursive trigger firing"
    - "Cross-subjob OnComponentOk trigger propagation via _component_triggered_subjobs"
    - "Stall detection only flags components in attempted subjobs"
    - "exit_code checked on exception cause chain for BaseComponent wrapping"

key-files:
  created:
    - src/v1/engine/executor.py
    - tests/v1/engine/test_executor.py
  modified:
    - src/v1/engine/engine.py
    - src/v1/engine/__init__.py

key-decisions:
  - "Stall detection excludes components in untriggered subjobs (RunIf=false, no trigger path)"
  - "exit_code detection walks cause chain since BaseComponent wraps exceptions"
  - "OnComponentOk cross-subjob triggers queued via _component_triggered_subjobs list"

patterns-established:
  - "Executor._execute_subjob() is the callable building block for Phase 10 iterate"
  - "Engine is thin orchestrator: init wires deps, execute delegates, cleanup handles lifecycle"
  - "REGISTRY exported from __init__.py -- all component phases use @REGISTRY.register()"

requirements-completed: [EXEC-01, EXEC-02, EXEC-03, EXEC-07, PERF-01]

duration: 15min
completed: 2026-04-15
---

# Phase 3 Plan 4: Executor and Engine Rewrite Summary

**Executor with iterative deque-based subjob queue, cross-subjob OnComponentOk triggers, and engine.py reduced from 868 to 259 lines**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-14T18:18:53Z
- **Completed:** 2026-04-14T18:33:37Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Created Executor module with `_execute_subjob()` as the Phase 10 iterate building block
- Rewrote engine.py from 868 to 259 lines by delegating to Executor, ExecutionPlan, OutputRouter, REGISTRY
- Removed all dead code: 125-line static COMPONENT_REGISTRY dict (D-02), 141-line _execute_iterate_component (D-14), _identify_subjobs, _find_connected_components, _are_inputs_ready, _get_input_data
- 27 orchestration integration tests covering trigger timing, stall detection, error propagation, cross-subjob flow safety, and iterative trigger chains
- Exported REGISTRY from `__init__.py` for component phase decorators

## Task Commits

Each task was committed atomically:

1. **Task 1: Create executor.py** - `0ad7a51` (feat)
2. **Task 2: Rewrite engine.py as thin orchestrator** - `66c816a` (feat)
3. **Task 1 fix: Stall detection, cross-subjob triggers, tDie cause chain** - `302ea60` (fix)
4. **Task 3: Write test_executor.py** - `020aa4a` (test)

## Files Created/Modified

- `src/v1/engine/executor.py` - Executor class: subjob/component execution, iterative trigger queue, stall detection
- `src/v1/engine/engine.py` - Thin ETLEngine orchestrator (259 lines, down from 868)
- `src/v1/engine/__init__.py` - Exports ETLEngine and REGISTRY
- `tests/v1/engine/test_executor.py` - 27 integration tests for Executor

## Decisions Made

- **Stall detection scoping:** Only flags components in subjobs that were actually attempted (queued for execution). Components in untriggered subjobs (RunIf=false, no trigger path) are not considered stuck.
- **exit_code cause chain:** BaseComponent.execute() wraps _process() exceptions in a new ComponentExecutionError, losing the exit_code attribute. Fixed by walking e.cause and e.__cause__ chain to find exit_code.
- **OnComponentOk cross-subjob:** When an OnComponentOk trigger fires and the target is in a different subjob, that subjob is queued via `_component_triggered_subjobs` list, picked up by the main execute_job loop.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed tDie exit_code detection through exception cause chain**
- **Found during:** Task 3 (test_tdie_stops_entire_job)
- **Issue:** BaseComponent.execute() wraps _process() exceptions in a new ComponentExecutionError. The exit_code attribute on the original exception was lost, so _job_terminated was never set.
- **Fix:** Check exit_code on both the exception itself, e.cause, and e.__cause__ (Python's chained exception).
- **Files modified:** src/v1/engine/executor.py
- **Verification:** test_tdie_stops_entire_job passes
- **Committed in:** 302ea60

**2. [Rule 1 - Bug] Fixed stall detection false positives for untriggered subjobs**
- **Found during:** Task 3 (test_runif_false_skips_target, test_tdie_stops_entire_job)
- **Issue:** Stall detection flagged components in subjobs that were never triggered (RunIf=false) or never reached (tDie terminated job early).
- **Fix:** Track attempted subjobs in `_attempted_subjobs` set, only flag stalls for components in attempted subjobs.
- **Files modified:** src/v1/engine/executor.py
- **Verification:** test_runif_false_skips_target and test_tdie_stops_entire_job pass
- **Committed in:** 302ea60

**3. [Rule 2 - Missing Critical] Added OnComponentOk cross-subjob trigger propagation**
- **Found during:** Task 3 (test_on_component_ok_fires_after_specific_component)
- **Issue:** OnComponentOk triggers targeting a component in a different subjob were not queuing that subjob for execution.
- **Fix:** Added `_component_triggered_subjobs` list populated by `_fire_component_triggers()`, consumed by `execute_job()` loop.
- **Files modified:** src/v1/engine/executor.py
- **Verification:** test_on_component_ok_fires_after_specific_component passes
- **Committed in:** 302ea60

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All fixes essential for correct trigger timing and error handling. No scope creep.

## Issues Encountered

- Pre-existing pandas 3.0 test failure in test_base_component.py (test_integer_type_coercion, test_nullable_true_integer) -- not caused by this plan, documented for Phase 4.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 complete: all 5 modules (component_registry, execution_plan, output_router, executor, engine) are wired and tested
- REGISTRY is exported from `__init__.py` -- component phases (4-11) can use `@REGISTRY.register()` decorators
- `_execute_subjob()` is ready as the building block for Phase 10 iterate support
- engine.py is a thin orchestrator with backward-compatible API

## Self-Check: PASSED

- All 5 files verified present
- All 4 commits verified in git log

---
*Phase: 03-execution-loop-restructure*
*Completed: 2026-04-15*
