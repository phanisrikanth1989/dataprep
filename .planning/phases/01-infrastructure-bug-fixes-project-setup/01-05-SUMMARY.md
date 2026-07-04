---
phase: 01-infrastructure-bug-fixes-project-setup
plan: 05
subsystem: engine
tags: [base-component, template-method, config-immutability, streaming, schema-validation, iterate]

requires:
  - phase: 01-02
    provides: "Rewritten GlobalMap with put_component_stat, get_component_stat"
  - phase: 01-03
    provides: "Rewritten ContextManager with resolve_dict, SKIP_RESOLUTION_KEYS"
provides:
  - "BaseComponent ABC with template method lifecycle (validate -> snapshot -> resolve -> process -> stats)"
  - "BaseIterateComponent aligned with BaseComponent lifecycle via _process()"
  - "Config immutability pattern (_original_config frozen, config re-derived per execute)"
  - "Streaming mode with reject data collection"
  - "Correct validate_schema nullable logic"
  - "reset() method for iterate re-execution"
affects: [phase-02-java-bridge, phase-03-engine-loop, phase-04-file-io, phase-05-tmap, phase-06-transforms-a, phase-07-transforms-b, phase-10-iterate]

tech-stack:
  added: []
  patterns:
    - "Template Method: execute() provides fixed lifecycle, subclasses implement _validate_config() and _process()"
    - "Config Immutability: _original_config deepcopied at construction, config re-derived per execute()"
    - "Named Flow Routing: _process() returns dict with arbitrary keys (main, reject, etc.)"
    - "Stats Accumulation: _update_stats_from_result uses += for streaming correctness"

key-files:
  created: []
  modified:
    - src/v1/engine/base_component.py
    - src/v1/engine/base_iterate_component.py
    - src/v1/engine/global_map.py

key-decisions:
  - "Config starts empty (self.config = {}) until execute() populates it from _original_config -- prevents pre-execute config access bugs"
  - "BaseIterateComponent hooks into lifecycle via _process() instead of overriding execute() -- ensures all lifecycle steps (validate, resolve, stats) happen for iterate components"
  - "validate_schema uses pd.Int64Dtype() for nullable integer columns instead of fillna(0).astype(int64)"
  - "Added GlobalMap.reset_component() method (was missing from wave 1 implementation but required by BaseComponent.reset())"

patterns-established:
  - "Template Method: All components inherit BaseComponent, implement _validate_config() and _process(), never override execute()"
  - "Config Snapshot/Restore: _original_config is never mutated; working config is fresh deepcopy per execute()"
  - "Stats Contract: _process() returns dict; _update_stats_from_result reads main/reject lengths"
  - "Iterate Pattern: Iterate components implement prepare_iterations() and set_iteration_globalmap(), engine consumes via has_next_iteration()/get_next_iteration_context()"

requirements-completed: [ENG-03, ENG-07, ENG-08, ENG-09, ENG-16, ENG-17, ENG-19, ENG-20, ENG-21, ENG-23]

duration: 3min
completed: 2026-04-14
---

# Phase 01 Plan 05: BaseComponent Rewrite Summary

**Rewritten BaseComponent with template method lifecycle fixing 10 engine bugs (config mutation, streaming reject loss, dead validation, nullable inversion) and BaseIterateComponent aligned to new lifecycle**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-14T10:22:54Z
- **Completed:** 2026-04-14T10:26:34Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Rewrote BaseComponent from scratch with rigid template method lifecycle: validate -> snapshot -> resolve -> process -> stats
- Fixed 10 engine bugs by design: ENG-03 (array resolution), ENG-07/20 (streaming reject), ENG-08 (dead validation), ENG-09/21 (config mutation), ENG-16 (standardized template), ENG-17 (named flow routing), ENG-19 (nullable inversion), ENG-23 (component pattern), NEW-03 (__repr__)
- Rewrote BaseIterateComponent to use BaseComponent lifecycle via _process() instead of overriding execute()
- Added GlobalMap.reset_component() for iterate re-execution support

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite BaseComponent from scratch** - `b856f5f` (feat)
2. **Task 2: Rewrite BaseIterateComponent to align with new BaseComponent** - `8757684` (feat)

## Files Created/Modified
- `src/v1/engine/base_component.py` - Complete rewrite: BaseComponent ABC with template method lifecycle, config immutability, streaming reject collection, correct validate_schema
- `src/v1/engine/base_iterate_component.py` - Complete rewrite: BaseIterateComponent using _process() hook, iteration query methods, reset with iterate state cleanup
- `src/v1/engine/global_map.py` - Added reset_component() method for clearing component stats during iterate re-execution

## Decisions Made
- **Config starts empty until execute():** `self.config = {}` in __init__ prevents any pre-execute config access from seeing unresolved values. Config is populated fresh from _original_config at start of each execute() call.
- **BaseIterateComponent does not override execute():** The old version completely replaced execute() with its own logic, bypassing validation, Java resolution, and stats. The new version hooks into the lifecycle via _process() which calls prepare_iterations().
- **Nullable integer uses pd.Int64Dtype():** Instead of the old broken pattern of `fillna(0).astype(int64)` when nullable=True, we use pandas nullable integer type which properly represents NaN in integer columns.
- **Added GlobalMap.reset_component():** The plan specified this method in the interface spec but it was missing from the wave 1 GlobalMap rewrite. Added as a Rule 3 auto-fix since BaseComponent.reset() depends on it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added GlobalMap.reset_component() method**
- **Found during:** Task 1 (BaseComponent rewrite)
- **Issue:** BaseComponent.reset() calls self.global_map.reset_component(self.id) but GlobalMap (from Plan 01-02) did not implement this method
- **Fix:** Added reset_component() to GlobalMap that clears _component_stats entry and removes corresponding _map keys
- **Files modified:** src/v1/engine/global_map.py
- **Verification:** TestComp reset() test passes, GlobalMap stats cleared correctly
- **Committed in:** b856f5f (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for reset() correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BaseComponent pattern is complete and ready for all 50+ engine components to inherit
- BaseIterateComponent ready for Phase 10 iterate support (tFileList, tFlowToIterate, tForeach)
- All components must implement _validate_config() (abstract) -- this is enforced at instantiation time
- Engine loop (Phase 3) can use the named flow routing contract from _process() return dict

## Self-Check: PASSED

All files verified present. All commit hashes found in git log.

---
*Phase: 01-infrastructure-bug-fixes-project-setup*
*Completed: 2026-04-14*
