---
phase: 13-test-stabilization-bridge-jar-rebuild
plan: "01"
subsystem: testing
tags: [java-bridge, groovy, py4j, executor, base-component, globalmap]

requires:
  - phase: 12-xml-components-audit-harden-output
    provides: executor.py CR-01 finalization loop (55d8354) that introduced the reset/stats regression

provides:
  - Rebuilt Java bridge JAR (May 10 build from May 5/8 manager source changes)
  - Fix for Groovy compiled tMap script generator (indentation, def void, var keyword bugs)
  - Fix for BaseComponent.reset() incorrectly clearing GlobalMap stats
  - Fix for executor finalization loop calling reset() on all components (not just streaming sinks)
  - Updated test_base_component.py to assert new correct behavior

affects: [13-02, 13-03, 13-04, 13-05, phase-14-coverage]

tech-stack:
  added: []
  patterns:
    - "Streaming sink finalization: guard executor reset() loop on _streaming_write_started attribute"
    - "GlobalMap stats persistence: put_component_stat overwrites -- no need to reset_component on iterate reset"

key-files:
  created: []
  modified:
    - src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar
    - src/v1/java_bridge/java/target/java-bridge.jar
    - src/v1/engine/components/transform/map.py
    - src/v1/engine/base_component.py
    - src/v1/engine/executor.py
    - tests/v1/engine/test_base_component.py

key-decisions:
  - "JAR not committed to git (target/ is gitignored) -- build artifact stays on disk, source in git"
  - "BaseComponent.reset() no longer calls global_map.reset_component: put_component_stat overwrites, no double-count risk, finalization loop was silently wiping stats"
  - "Executor finalization loop scoped to streaming sinks only: guard on _streaming_write_started attribute presence"
  - "Three Groovy syntax bugs fixed inline in map.py (indentation, def void, var keyword) -- CODE-CHANGE not TEST-CHANGE"

requirements-completed: [TEST-07, TEST-08]

duration: 35min
completed: 2026-05-10
---

# Phase 13 Plan 01: JAR Rebuild and Bridge Test Triage Summary

**Java bridge JAR rebuilt from May 5/8 manager source; 3 Groovy/executor CODE bugs fixed; all 57 bridge-coupled tests pass (0 failures)**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-10T13:45:00Z
- **Completed:** 2026-05-10T14:20:00Z
- **Tasks:** 2 (+ 3 inline code fixes)
- **Files modified:** 5 source + 1 test

## JAR Rebuild

| Artifact | Before | After |
|----------|--------|-------|
| java-bridge-with-dependencies.jar | 25M (Apr 25 21:18) | 25M (May 10 19:16) |
| java-bridge.jar | 61K (Apr 25 21:18) | 61K (May 10 19:16) |

Build: `mvn package -f src/v1/java_bridge/java/pom.xml` -- succeeded cleanly in ~45s.

Note: `target/` is gitignored; the JAR is a build artifact. The manager's source changes (JavaBridge.java May 5, ArrowSerializer.java May 8) are committed as source. The plan's instruction to commit the JAR binary was superseded by the `.gitignore` rule -- deviated per Rule 3 (blocked).

## 9-Test Resolution Table

| test_file | was-failing | now | fix-type |
|-----------|------------|-----|----------|
| test_bridge_integration.py (31 tests) | JAR-blocked | PASS | PASS-after-rebuild |
| test_java_component.py (14 tests) | JAR-blocked | PASS | PASS-after-rebuild |
| test_code_components_engine_smoke.py::TestPythonRowComponentEngineEnd2End | FAIL (NB_LINE_OK=0) | PASS | CODE-CHANGE (BUG-BRDG-002/003) |
| test_code_components_engine_smoke.py other 7 tests | JAR-blocked | PASS | PASS-after-rebuild |
| test_map_method_size.py (3 tests) | FAIL (Groovy compile error) | PASS | CODE-CHANGE (BUG-BRDG-001) |
| test_full_pipeline.py::TestTMapJavaExpressionPipeline | JAR-blocked | PASS | PASS-after-rebuild |

Final count: 57 passed, 0 failed.

## Accomplishments
- Maven rebuild picked up `executeOneTimeExpression` 3-arg signature + decimal nulls from ArrowSerializer
- Fixed 3 Groovy script generation bugs in `map.py::_build_compiled_script` that prevented tMap with 250-column outputs from compiling
- Fixed root cause of GlobalMap stats being silently wiped after job completion (executor CR-01 finalization loop calling `reset()` on non-streaming components)
- All 18 executor iterate tests now pass (the executor finalization loop no longer adds a spurious extra `reset()` call on iterate body components)

## Task Commits

1. **Task 1: JAR rebuild** -- Maven built successfully; JAR gitignored, not committed (deviation documented)
2. **Task 2 - BUG-BRDG-001** - `e7282a3` (fix) -- Groovy script indentation + def void + var keyword
3. **Task 2 - BUG-BRDG-002** - `7df08aa` (fix) -- BaseComponent.reset() no longer clears GlobalMap stats
4. **Task 2 - BUG-BRDG-003** - `9ca05e2` (fix+test) -- Executor finalization loop scoped to streaming sinks

## Files Created/Modified
- `src/v1/engine/components/transform/map.py` -- 3 Groovy script generation bugs fixed
- `src/v1/engine/base_component.py` -- reset() no longer calls global_map.reset_component
- `src/v1/engine/executor.py` -- finalization loop guarded on _streaming_write_started
- `tests/v1/engine/test_base_component.py` -- TestBaseComponentReset updated for new correct behavior

## Decisions Made
- JAR binary not committed to git (gitignored); build from source is the reproducible path
- `BaseComponent.reset()` GlobalMap clear removed: `put_component_stat` overwrites (not accumulates), so clearing is redundant AND harmful (causes finalization-time wipe)
- Executor finalization loop scoped by `_streaming_write_started` attribute rather than by class check, keeping it extensible

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] JAR in .gitignore -- cannot commit binary artifact**
- **Found during:** Task 1 (JAR rebuild + commit)
- **Issue:** `src/v1/java_bridge/java/target/` is in `.gitignore`; `git add` rejected with exit 1
- **Fix:** Skipped JAR commit. The JAR is a build artifact; the manager's source (JavaBridge.java, ArrowSerializer.java) is already in git. Anyone can reproduce with `mvn package`.
- **Verification:** Both JARs present on disk with May 10 timestamp; JAR contains JavaBridge.class (14233 entries verified via zipfile)
- **Committed in:** N/A (no commit possible for gitignored files)

**2. [Rule 1 - Bug] BUG-BRDG-001: 3 Groovy syntax bugs in map.py _build_compiled_script**
- **Found during:** Task 2 (re-triaging test_map_method_size.py)
- **Issue 1:** `for col_offset, col in enumerate(chunk_cols)` loop was at wrong indent level (OUTSIDE the chunk loop), producing N empty function headers + 1 body for last chunk only
- **Issue 2:** `def void fillOutput_...` -- `def void` is invalid Groovy (Java syntax leaked in); correct Groovy is `void`
- **Issue 3:** Parameter `var` shadows Groovy's built-in `var` type-inference keyword; renamed to `Var`
- **Fix:** Fixed indentation (body inside chunk loop), `def void` -> `void`, `var` -> `Var` in chunk_fill_params and chunk_fill_args
- **Files modified:** `src/v1/engine/components/transform/map.py`
- **Verification:** All 3 test_map_method_size.py tests pass (250-column tMap compiles and produces correct rows)
- **Committed in:** `e7282a3`

**3. [Rule 1 - Bug] BUG-BRDG-002: BaseComponent.reset() cleared GlobalMap stats**
- **Found during:** Task 2 (test_code_components_engine_smoke.py::TestPythonRowComponentEngineEnd2End)
- **Issue:** `BaseComponent.reset()` called `global_map.reset_component(self.id)`, zeroing GlobalMap stats. The CR-01 finalization loop (commit 55d8354) called `reset()` on ALL components after `execute_job()` -- silently wiping all component stats before the test could read them.
- **Fix:** Removed `global_map.reset_component(self.id)` from `reset()`. `put_component_stat` overwrites on each `_update_global_map()` call, so clearing is redundant and harmful.
- **Files modified:** `src/v1/engine/base_component.py`
- **Verification:** `test_per_row_doubles_value_with_nb_line_ok` passes; `test_base_component.py::TestBaseComponentReset` updated and passes
- **Committed in:** `7df08aa`

**4. [Rule 1 - Bug] BUG-BRDG-003: Executor finalization loop called reset() on ALL components**
- **Found during:** Task 2 (investigation of executor_iterate test failures surfaced by BUG-BRDG-002 fix)
- **Issue:** Executor CR-01 finalization loop used `hasattr(component, "reset")` as guard -- matches ALL components (BaseComponent has `reset()`). For iterate body components, this added an extra reset() call beyond the N calls from the iterate loop, breaking EXEC-05 reset-between-iters contract.
- **Fix:** Added guard `if not hasattr(component, "_streaming_write_started"): continue` -- only FileOutputXML, AdvancedFileOutputXML, FileOutputDelimited have this attribute.
- **Files modified:** `src/v1/engine/executor.py`; `tests/v1/engine/test_base_component.py` (test updated for new behavior)
- **Verification:** All 18 executor iterate tests pass; streaming XML tests unaffected (FileOutputXML still has `_streaming_write_started`)
- **Committed in:** `9ca05e2`

---

**Total deviations:** 4 (1 blocking/gitignore, 3 auto-fixed bugs)
**Impact on plan:** All fixes were necessary for correctness. The 3 code bugs were directly blocking the 9 bridge-coupled tests. No scope creep -- all fixes are within the bridge/executor system this plan touches.

## Issues Encountered
- `test_java_component.py` location: plan referenced `tests/v1/engine/test_java_component.py` (does not exist); actual file is `tests/v1/engine/components/transform/test_java_component.py` -- resolved by `find` search
- The CONTEXT.md D-C1 ambiguity about executor_iterate tests was resolved: the 9 executor_iterate tests were NOT pre-existing failures of the bridge -- they were NEW failures caused by the BUG-BRDG-002/003 fix exposing the CR-01 finalization loop bug. Fixed inline as CODE-CHANGE per D-C1 guidance.

## Known Stubs
None.

## Threat Flags
None -- no new network endpoints, auth paths, or schema changes introduced.

## Self-Check
- `src/v1/engine/components/transform/map.py` -- FOUND
- `src/v1/engine/base_component.py` -- FOUND
- `src/v1/engine/executor.py` -- FOUND
- `tests/v1/engine/test_base_component.py` -- FOUND
- Commit `e7282a3` -- FOUND (git log confirms)
- Commit `7df08aa` -- FOUND
- Commit `9ca05e2` -- FOUND
- 57 bridge tests pass: VERIFIED (pytest final run: 57 passed, 0 failed)

## Self-Check: PASSED

## Next Phase Readiness
- Plans 13-02 through 13-05 can proceed: JAR rebuilt, bridge tests green
- 22 remaining pre-existing failures (Excel D-B1, unique_row D-B2, convert_type D-B3, file_list D-B4, executor_iterate D-C1, NeedsReview D-C2/D-D1) are unchanged from before this plan
- BaseComponent.reset() and executor finalization loop are now correct: future phases building on iterate/streaming components will not regress

---
*Phase: 13-test-stabilization-bridge-jar-rebuild*
*Completed: 2026-05-10*
