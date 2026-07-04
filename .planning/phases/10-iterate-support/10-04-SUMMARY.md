---
phase: 10-iterate-support
plan: "04"
subsystem: engine
tags: [iterate, flow-to-iterate, globalmap, talend-parity, tdd]

# Dependency graph
requires:
  - phase: 10-01
    provides: BaseIterateComponent ABC with 9-hook lifecycle, execute() override, get_next_iteration_context()
  - phase: 10-02
    provides: Executor iterate loop that calls set_iteration_globalmap and writes CURRENT_ITERATION key

provides:
  - FlowToIterate engine component registered under FlowToIterate and tFlowToIterate (ITER-10)
  - DEFAULT_MAP=true: writes <inputFlow>.<col> keys per row to globalMap (ITER-02)
  - DEFAULT_MAP=false: writes verbatim user-defined keys from map_entries (ITER-03)
  - prepare_iterations() materialises DataFrame rows into bounded FlowToIterateItem iterator (ITER-01)
  - pd.NA coercion to None before globalMap.put (RESEARCH Risk 10.2)
  - finalize() sets NB_LINE = total input rows (D-F6)
  - 27 unit tests covering all ITER-01..03, ITER-10, ITER-11 requirements

affects: [10-07, 10-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FlowToIterateItem typed dataclass (D-A4) for per-row iteration items"
    - "TDD RED/GREEN cycle: test commit 1be099e -> impl commit 405be33"
    - "pd.NA -> None coercion pattern for globalMap safety"
    - "inputs[] empty check in both _validate_config (structural) and set_iteration_globalmap (runtime)"

key-files:
  created:
    - src/v1/engine/components/iterate/__init__.py
    - src/v1/engine/components/iterate/flow_to_iterate.py
    - tests/v1/engine/components/iterate/__init__.py
    - tests/v1/engine/components/iterate/test_flow_to_iterate.py
  modified:
    - src/v1/engine/components/__init__.py

key-decisions:
  - "DEFAULT_MAP=true uses self.inputs[0] as flow prefix -- confirmed via Job_tFlowToIterate_0.1.item sample which uses globalMap.get('row1.filepath')"
  - "pd.NA coerced to None in set_iteration_globalmap (both branches) per RESEARCH Risk 10.2"
  - "Non-string column names str()-coerced in DEFAULT_MAP=true key construction"
  - "_validate_config checks self.inputs non-empty as structural check (Rule 12 compliant: inputs set by engine at startup, not a row-content check)"
  - "finalize() sets NB_LINE independently; executor's _update_global_map publishes {cid}_NB_LINE from stats"
  - "Test helper _make() uses 'None if inputs is None else inputs' to preserve empty list inputs=[] (or-operator bug fix)"

patterns-established:
  - "Iterate package wired into src/v1/engine/components/__init__.py via 'from . import iterate'"
  - "FlowToIterateItem dataclass carries row dict + 1-based index; consumed by set_iteration_globalmap"
  - "Empty DataFrame -> total_iterations=0, iter([]), no error (D-F1 contract)"

requirements-completed: [ITER-01, ITER-02, ITER-03, ITER-10, ITER-11]

# Metrics
duration: 3min
completed: 2026-05-05
---

# Phase 10 Plan 04: FlowToIterate Component Summary

**FlowToIterate engine component: per-row globalMap iteration with DEFAULT_MAP=true (<inputFlow>.<col>) and DEFAULT_MAP=false (verbatim user keys), registered under both FlowToIterate and tFlowToIterate aliases**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-05T18:21:30Z
- **Completed:** 2026-05-05T18:24:30Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments

- Implemented FlowToIterate engine component extending BaseIterateComponent with full Talend parity
- DEFAULT_MAP=true branch writes `<inputFlow>.<col>` keys (confirmed via Job_tFlowToIterate_0.1.item sample)
- DEFAULT_MAP=false branch writes verbatim user-defined keys from map_entries (no prefix)
- pd.NA coercion to None in both branches guards against Java bridge type errors (Risk 10.2)
- 27 unit tests pass covering all ITER-01, ITER-02, ITER-03, ITER-10, ITER-11 requirements

## Task Commits

Each task was committed atomically (TDD cycle):

1. **RED - Failing tests for FlowToIterate** - `1be099e` (test)
2. **GREEN - FlowToIterate implementation + iterate package** - `405be33` (feat)

**Plan metadata:** (docs commit below)

_Note: TDD tasks have two commits -- test (RED) then implementation (GREEN)._

## Files Created/Modified

- `src/v1/engine/components/iterate/__init__.py` - Iterate engine package; imports FlowToIterate to fire registration
- `src/v1/engine/components/iterate/flow_to_iterate.py` - FlowToIterate component with FlowToIterateItem dataclass
- `src/v1/engine/components/__init__.py` - Added `from . import iterate` to wire package at startup
- `tests/v1/engine/components/iterate/__init__.py` - Test package init (empty; required for discovery)
- `tests/v1/engine/components/iterate/test_flow_to_iterate.py` - 27 unit tests across 7 test classes

## FlowToIterate API

**Config keys (from converter JSON):**
- `default_map` (bool, default True): selects globalMap key format
- `map_entries` (list[dict], default []): used when default_map=False; each entry has `key` and `value` fields

**GlobalMap key formats:**
- DEFAULT_MAP=true: `{self.inputs[0]}.{column_name}` (e.g., `row1.filepath`, `row1.filename`)
- DEFAULT_MAP=false: `{entry["key"]}` verbatim (e.g., `my_path`, `my_filename`)

**pd.NA handling:** Any `pd.NA` value is coerced to `None` before `globalMap.put()`. Non-string column names are `str()`-coerced.

**Iterator contract:** `prepare_iterations()` returns a bounded `iter(list)` with `FlowToIterateItem` objects (index is 1-based).

**Statistics:** `finalize()` sets `NB_LINE = total_iterations`, `NB_LINE_OK = total_iterations`, `NB_LINE_REJECT = 0`.

## Coverage Status (TEST-04 gate)

Coverage gate (>=90%) is enforced in 10-07. Current test run covers all public methods:
- `_validate_config` -- 5 tests
- `prepare_iterations` -- 6 tests (including empty + None)
- `set_iteration_globalmap` -- 9 tests (DEFAULT_MAP=true: 5, DEFAULT_MAP=false: 4)
- `finalize` -- 3 tests
- `CURRENT_ITERATION` key naming -- 2 tests
- Registration -- 2 tests

All paths exercised; coverage expected to be well above 90%.

## Decisions Made

- DEFAULT_MAP=true uses `self.inputs[0]` as flow prefix per Talaxie javajet reference and Job_tFlowToIterate_0.1.item sample (reads `globalMap.get("row1.filepath")`)
- `_validate_config` checks `self.inputs` non-empty as a structural check per Phase 7.1 Rule 12 (inputs set by engine at startup from comp_config["inputs"], not resolved from row content)
- finalize() sets NB_LINE independently from update_iteration_stats() accumulation -- the iterate source's NB_LINE is the input row count, not the body's processed row count

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed empty-list inputs falsy coercion in test helper**

- **Found during:** Task 2 (GREEN phase)
- **Issue:** `_make()` in TestDefaultMapTrue used `inputs or ["row1"]` which evaluates `[] or ["row1"]` = `["row1"]`, making `test_no_inputs_raises_on_set_globalmap` unable to pass `inputs=[]` to the component
- **Fix:** Changed to `["row1"] if inputs is None else inputs` to preserve empty list correctly
- **Files modified:** `tests/v1/engine/components/iterate/test_flow_to_iterate.py`
- **Verification:** `test_no_inputs_raises_on_set_globalmap` now passes; 27/27 total pass
- **Committed in:** `405be33` (GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test helper)
**Impact on plan:** Minor test helper bug fix. No scope creep. All plan behavior correct.

## Issues Encountered

None beyond the test helper bug documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FlowToIterate registered and fully tested; ready for use in 10-07 integration tests
- 10-07 (Job_tFlowToIterate_0.1.item integration test) depends on this component being registered
- Coverage gate (TEST-04 >= 90%) enforced in 10-07 end-to-end test run

## Threat Flags

No new threat surface introduced. FlowToIterate consumes trusted internal DataFrames only; no network, no file I/O, no external boundaries.

## Self-Check: PASSED

Files exist:
- src/v1/engine/components/iterate/__init__.py: FOUND
- src/v1/engine/components/iterate/flow_to_iterate.py: FOUND
- tests/v1/engine/components/iterate/__init__.py: FOUND
- tests/v1/engine/components/iterate/test_flow_to_iterate.py: FOUND

Commits exist:
- 1be099e: FOUND (test RED)
- 405be33: FOUND (feat GREEN)

All 27 tests pass. Registration verified. ASCII-only verified.

---
*Phase: 10-iterate-support*
*Completed: 2026-05-05*
