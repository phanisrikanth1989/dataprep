---
phase: 10-iterate-support
plan: 07
subsystem: testing
tags: [integration, iterate, java-bridge, end-to-end, talend-parity, tFileList, tFlowToIterate]

# Dependency graph
requires:
  - phase: 10-iterate-support/10-03
    provides: FileList engine component
  - phase: 10-iterate-support/10-04
    provides: FlowToIterate engine component
  - phase: 10-iterate-support/10-05
    provides: executor iterate loop
  - phase: 10-iterate-support/10-06
    provides: iterate logging + connection extraction
provides:
  - "E2E integration tests for tFileList iterate pattern using real .item fixtures and real Java bridge"
  - "E2E integration tests for tFlowToIterate pattern with globalMap last-write-wins verification"
  - "Integration conftest.py with java_bridge gate fixture for tests/integration/"
  - "Bug fix: file_list.py accepts lowercase converter-output config keys"
  - "Bug fix: output_router.py skips ITERATE flows in are_inputs_ready() check"
  - "Bug fix: file_input_delimited converter marks Java filepath expressions with {{java}}"
affects: [phase-11, phase-12, future-iterate-debugging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Integration tests use ETLEngine directly (not run_job) to access engine.global_map.get_all() for raw globalMap assertions"
    - "tests/integration/conftest.py provides java_bridge fixture as a JAR-existence gate; ETLEngine starts its own bridge"
    - "file_list.py _cfg() helper reads uppercase keys first then lowercase fallback for converter compatibility"
    - "output_router.py stores _flow_types dict to distinguish iterate vs data flows in are_inputs_ready()"

key-files:
  created:
    - tests/integration/conftest.py
    - tests/integration/test_iterate_e2e.py
  modified:
    - src/v1/engine/components/file/file_list.py
    - src/v1/engine/output_router.py
    - src/converters/talend_to_v1/components/file/file_input_delimited.py
    - pyproject.toml

key-decisions:
  - "Use ETLEngine directly (not run_job) in integration tests so engine.global_map.get_all() is accessible for raw globalMap key assertions (last-write-wins, NB_FILE, CURRENT_ITERATION)"
  - "tests/integration/conftest.py provides java_bridge as a JAR-gate only; ETLEngine starts its own JavaBridgeManager when java_config.enabled=True"
  - "file_list.py accepts both uppercase ('DIRECTORY') and lowercase ('directory') config keys via _cfg() helper; backward-compatible with existing tests"
  - "output_router.py are_inputs_ready() must skip ITERATE flows; they are control-flow edges that set globalMap, not DataFrame-carrying data flows"
  - "file_input_delimited converter must apply ExpressionConverter.mark_java_expression() to FILENAME so globalMap.get() filepath expressions get {{java}} marker"

patterns-established:
  - "Integration tests that need ETLEngine state post-execution use ETLEngine directly, not run_job wrapper"
  - "Converter must apply ExpressionConverter.mark_java_expression() to any field that may contain a Java expression, not just tMap output columns"

requirements-completed: [TEST-04]

# Metrics
duration: 40min
completed: 2026-05-05
---

# Phase 10 Plan 07: Iterate E2E Integration Tests Summary

**E2E tests for tFileList + tFlowToIterate using real .item fixtures and live Java bridge, with three systemic iterate-pipeline bugs fixed as required for the tests to pass.**

## Performance

- **Duration:** 40 min
- **Started:** 2026-05-05T18:30:00Z
- **Completed:** 2026-05-05T19:10:12Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Integration test suite for Job_tFileList_0.1.item: conversion test (no Java) + 3 Java e2e tests (end-to-end, append, ASCII logs)
- Integration test suite for Job_tFlowToIterate_0.1.item: conversion test + 3 Java e2e tests (end-to-end with globalMap last-write-wins, output schema, ASCII logs)
- Coverage gate documented with exact CLI command per TEST-04 requirement
- Three systemic bugs fixed that blocked iterate pipeline execution end-to-end

## Test Setup Details

### Job_tFileList_0.1.item Setup

- Input directory: `tmp_path/input/` with 3 files named `batch_00.csv`, `batch_01.csv`, `batch_02.csv` (matches glob `batch*`)
- Input schema: `id;name;job;salary` (semicolon-delimited, no header, HEADER=0)
- Output: `tmp_path/merge.dat` (APPEND=true, INCLUDEHEADER=true)
- Context overrides: JSON path mutated via `_mutate_json_paths()` (fixture hardcodes Windows paths)
- GlobalMap assertions: `tFileList_1_NB_FILE == 3` after 3 iterations

### Job_tFlowToIterate_0.1.item Setup

- Row-source: `tmp_path/rows.csv` with columns `filepath,filename,dept` (3 rows, comma-delimited, HEADER=1)
- Per-row files: `tmp_path/per_row/r00.csv`, `r01.csv`, `r02.csv` with `id,name,dept,salary` schema
- Output: `tmp_path/output.dat` (APPEND=true, INCLUDEHEADER=true, pipe-delimited)
- GlobalMap last-write-wins (D-F6): `row1.filename` and `row1.dept` hold last row's values after iterate
- ITER-11 verified: `tFlowToIterate_1_CURRENT_ITERATION` key exists; `CURRENT_ITERATE` typo key is None

## Task Commits

1. **Task 1: Build fixture helpers and tFileList e2e test** - `bfa23ff` (feat)
   (Task 2 content was included in Task 1 since the entire test file was created at once)

**Plan metadata:** (committed with SUMMARY)

## Files Created/Modified

- `tests/integration/conftest.py` - java_bridge JAR-gate fixture for integration tests directory
- `tests/integration/test_iterate_e2e.py` - E2E tests for both .item fixtures with @pytest.mark.java
- `src/v1/engine/components/file/file_list.py` - _cfg() helper + lowercase key acceptance + FILEMASK case handling
- `src/v1/engine/output_router.py` - _flow_types dict + are_inputs_ready() skips iterate flows
- `src/converters/talend_to_v1/components/file/file_input_delimited.py` - ExpressionConverter.mark_java_expression() on FILENAME
- `pyproject.toml` - register 'coverage' pytest marker

## Decisions Made

- Use `ETLEngine` directly in integration tests (not `run_job`) to access `engine.global_map.get_all()` for raw globalMap key assertions.
- The `tests/integration/conftest.py` `java_bridge` fixture acts as a JAR-existence gate and symlinks the JAR into the worktree; the ETLEngine starts its own `JavaBridgeManager` internally.
- `file_list.py` uses a `_cfg(key_upper, key_lower, default)` helper that checks uppercase first then falls back to lowercase, maintaining backward compatibility with existing tests that use uppercase keys.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] file_list.py uses uppercase-only config keys incompatible with converter output**
- **Found during:** Task 1 (test_executes_end_to_end execution)
- **Issue:** `file_list.py` reads `self.config["DIRECTORY"]`, `"FILES"`, `"GLOBEXPRESSIONS"` etc. but the talend_to_v1 converter produces lowercase keys (`directory`, `files`, `glob_expressions`). Component raised `ConfigurationError: Missing required config key 'DIRECTORY'`.
- **Fix:** Added `_cfg(key_upper, key_lower, default)` helper that checks uppercase first then lowercase fallback. Updated all config reads in `_validate_config()` and `prepare_iterations()`. Also handle both `FILEMASK` and `filemask` keys in the files list.
- **Files modified:** `src/v1/engine/components/file/file_list.py`
- **Verification:** All 63 existing file_list unit tests pass + new e2e test passes.
- **Committed in:** bfa23ff (Task 1 commit)

**2. [Rule 1 - Bug] output_router.py are_inputs_ready() treats ITERATE flows as data flow dependencies**
- **Found during:** Task 1 (body components skipped with "inputs not ready" warning)
- **Issue:** `are_inputs_ready()` checks if all input flow names have data in `_data_flows`. The converted JSON sets `tFileInputDelimited_1.inputs = ['iterate1']` (the ITERATE flow name). ITERATE flows don't carry DataFrame data -- they are control-flow edges. The body component was skipped 3 times (once per iteration) because `iterate1` was never in `_data_flows`.
- **Fix:** Added `_flow_types: dict[str, str]` lookup in `__init__`. Updated `are_inputs_ready()` to skip flows where `_flow_types[flow_name] == 'iterate'`.
- **Files modified:** `src/v1/engine/output_router.py`
- **Verification:** All 24 existing output_router + executor_iterate tests pass + new e2e test advances past the "inputs not ready" barrier.
- **Committed in:** bfa23ff (Task 1 commit)

**3. [Rule 1 - Bug] file_input_delimited converter does not mark Java expressions in FILENAME field**
- **Found during:** Task 1 (tFileInputDelimited_1 gets literal Java string as filepath)
- **Issue:** The `FILENAME` field value `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))` was stored as a raw string. The engine's `_resolve_java_expressions()` only processes strings starting with `{{java}}`. Without the marker, the filepath was passed literally to `open()`, causing `File not found: '((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))'`.
- **Fix:** Applied `ExpressionConverter.mark_java_expression()` to the FILENAME field value so it gets the `{{java}}` prefix when it contains Java/globalMap expressions.
- **Files modified:** `src/converters/talend_to_v1/components/file/file_input_delimited.py`
- **Verification:** Re-converted fixture now has `"filepath": "{{java}}((String)globalMap.get(\"tFileList_1_CURRENT_FILEPATH\"))"`. Engine resolves it via Java bridge, body component opens the correct file.
- **Committed in:** bfa23ff (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All three bugs were blockers that prevented the iterate pipeline from executing end-to-end. Fixing them was required to achieve the plan's purpose. No scope creep.

## Coverage Gate Command (TEST-04)

Manual verification before merge:

```
pytest \
  tests/v1/engine/test_base_iterate_component.py \
  tests/v1/engine/test_executor_iterate.py \
  tests/v1/engine/test_execution_plan_iterate.py \
  tests/v1/engine/test_output_router_iterate.py \
  tests/v1/engine/components/file/test_file_list.py \
  tests/v1/engine/components/iterate/test_flow_to_iterate.py \
  tests/v1/engine/test_iterate_logging.py \
  tests/converters/talend_to_v1/test_iterate_connection_extraction.py \
  --cov=src/v1/engine/base_iterate_component \
  --cov=src/v1/engine/iterate_logging \
  --cov=src/v1/engine/components/iterate \
  --cov=src/v1/engine/components/file/file_list \
  --cov-fail-under=90
```

## Java @pytest.mark.java Skip Behavior

When the JAR is not built, the `java_bridge` fixture in `tests/integration/conftest.py` calls `pytest.skip()`. All 6 Java tests in the `TestJobTFileListExecution` and `TestJobTFlowToIterateExecution` classes will be skipped. This is expected behavior per the existing project pattern.

Build the JAR with: `cd src/v1/java_bridge/java && mvn package -q`

## Manual Verification Checklist (for JAR-built path)

- [x] `pytest tests/integration/test_iterate_e2e.py -x` passes (10 passed, 1 skipped)
- [x] `pytest tests/integration/test_iterate_e2e.py -x -m java` passes (6 passed)
- [x] ASCII-only: `python -c "open('tests/integration/test_iterate_e2e.py').read().encode('ascii')"` exits 0
- [x] `grep -c "@pytest.mark.java" tests/integration/test_iterate_e2e.py` = 5
- [x] `grep -c "_CURRENT_ITERATION" tests/integration/test_iterate_e2e.py` = 2
- [x] `gm_all.get("tFlowToIterate_1_CURRENT_ITERATE") is None` assertion present (ITER-11)
- [x] Coverage gate command documented in TestPhase10Coverage class docstring

## Issues Encountered

Three pre-existing bugs in the engine/converter that were not discovered until E2E testing revealed them:
1. Config key case mismatch (converter lowercase vs engine uppercase)
2. ITERATE flows treated as data flow dependencies in readiness check
3. Java filepath expressions not marked with `{{java}}` by the converter

All fixed inline per deviation rules.

## Next Phase Readiness

- Phase 10 iterate support now has real E2E integration tests with live Java bridge
- The three fixed bugs (file_list config key normalization, output_router iterate flow handling, file_input_delimited expression marking) are correctness fixes that also benefit any other iterate pipeline using these components
- Phase 11 (Oracle) and Phase 12 (Integration) can proceed

---
*Phase: 10-iterate-support*
*Completed: 2026-05-05*
