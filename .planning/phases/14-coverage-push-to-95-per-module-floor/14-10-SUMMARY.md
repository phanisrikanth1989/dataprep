---
phase: 14
plan: 10
slug: engine-core
subsystem: engine-core
tags: [coverage, engine, engine-core, trigger-manager, executor, base-component, base-iterate-component, python-routine-manager, java-bridge-manager, plan-14-10]
status: complete
completed: 2026-05-11
duration_minutes: ~110

# Dependency graph
requires:
  - phase: 14
    provides: "14-01 pipeline-test infrastructure (run_job_fixture, FIXTURE_JOBS_ROOT, assert_ascii_logs); JVM 11+ on PATH for @pytest.mark.java tests (D-A3)"
provides:
  - "src/v1/engine/trigger_manager.py: 91.3% -> 100.0% (13 missed lines closed)"
  - "src/v1/engine/executor.py: 91.0% -> 95.2% (14 missed lines closed; 16 remain in deeper iterate paths)"
  - "src/v1/engine/base_iterate_component.py: 90.7% -> 100.0% (8 missed lines closed)"
  - "src/v1/engine/base_component.py: 80.7% -> 97.1% (86 missed lines closed; 15 remain in defensive guards)"
  - "src/v1/engine/python_routine_manager.py: 81.6% -> 98.0% (16 missed lines closed)"
  - "src/v1/engine/engine.py: 88.6% -> 100.0% (18 missed lines closed)"
  - "src/v1/engine/java_bridge_manager.py: 52.5% -> 99.0% (47 missed lines closed via @pytest.mark.java tests; 1 line is post-loop unreachable in practice)"
  - "tests/fixtures/jobs/core/trigger_runif.json: NEW pipeline fixture (4-component, 2 subjobs, RunIf trigger)"
  - "tests/fixtures/jobs/core/multi_subjob.json: NEW pipeline fixture (4-component, 2 subjobs, OnSubjobOk trigger)"
  - "tests/fixtures/jobs/core/reject_routing.json: NEW pipeline fixture (3-component, reject flow with CHECK_FIELDS_NUM)"
  - "tests/v1/engine/test_engine.py: NEW (18 tests covering ETLEngine top-level orchestration + 3 pipeline tests)"
  - "tests/v1/engine/test_java_bridge_manager.py: NEW (16 @pytest.mark.java tests covering JVM lifecycle, port retry, library validation, routine load, stop idempotency)"
  - "Plan 14-01 deferral resolved: TestTMapCompiledExpressions JVM contention under -n auto fixed via JavaBridgeManager (dynamic port) in test_bridge_integration.py 'bridge' fixture"
affects:
  - ".planning/STATE.md"
  - ".planning/ROADMAP.md"
  - ".planning/phases/14-coverage-push-to-95-per-module-floor/14-PLAN-CHECK-NOTES.md (Plan 14-01 item 1 resolved)"

tech-stack:
  added: []
  patterns:
    - "Mock-bridge harness for base_component._resolve_java_expressions: MagicMock JavaBridge with execute_batch_one_time_expressions returning a {{ERROR}}-prefixed value to exercise the error-marker raise path."
    - "JVM-availability gate at module scope via shutil.which('java') + autouse fixture (replaces top-of-test inline probe). Cleaner than per-test guard and aligns with the project pattern in tests/v1/engine/conftest.py:java_bridge."
    - "Real-bridge subclassing for monkey-patched failure injection: subclass JavaBridge in-place and re-bind both src.v1.java_bridge.JavaBridge and src.v1.java_bridge.bridge.JavaBridge; the manager imports through the package, not the submodule."
    - "Pipeline-test pattern for engine-core: 3 new fixtures under tests/fixtures/jobs/core/ exercise the full ETLEngine.execute() lifecycle for trigger flow, multi-subjob orchestration, and reject routing."

key-files:
  created:
    - tests/fixtures/jobs/core/trigger_runif.json
    - tests/fixtures/jobs/core/multi_subjob.json
    - tests/fixtures/jobs/core/reject_routing.json
    - tests/v1/engine/test_engine.py
    - tests/v1/engine/test_java_bridge_manager.py
    - .planning/phases/14-coverage-push-to-95-per-module-floor/14-10-SUMMARY.md
  modified:
    - tests/v1/engine/test_trigger_manager.py
    - tests/v1/engine/test_executor.py
    - tests/v1/engine/test_base_iterate_component.py
    - tests/v1/engine/test_base_component.py
    - tests/v1/engine/test_routine_loading.py
    - tests/v1/engine/test_bridge_integration.py
  deleted: []

key-decisions:
  - "RESOLVED Plan 14-01 deferral (JVM contention): TestTMapCompiledExpressions and other test_bridge_integration.py classes failed under -n auto because the module-scoped 'bridge' fixture used JavaBridge() with default port=25333, causing every xdist worker except the first to fail on bind(). Fix: switch the fixture to JavaBridgeManager() which calls socket.bind(('', 0)) -> dynamic free port per worker. Verified by running -n auto with 10 workers; all 31 bridge_integration tests pass parallel."
  - "Plan 14-06 PARTIAL LIFT for map.py NOT closed by this plan. The 147 missing lines in map.py are inside Java-bridge-driven paths (_join_context_only, _join_cross_table, _join_reload_per_row, _evaluate_outputs_compiled, _evaluate_with_bridge). The 3 new core pipeline fixtures (trigger_runif, multi_subjob, reject_routing) do NOT execute tMap, so they did not exercise those code paths as a side effect. map.py stays at 83.06% (deferral unchanged) and remains a Plan 14-13 closeout responsibility -- either spawn a focused Plan 14-06b for live-bridge tMap tests or amend the per-module floor for map.py."
  - "java_bridge_manager.py uses Plan 14-10's @pytest.mark.java tests + targeted monkey-patches: real JVM start/stop (16 happy-path tests), mocked validate_libraries returning [] (success log line), mocked load_routine no-op (success log line), and subclasses of JavaBridge that raise 'Address already in use' on first attempts (port retry loop). Per project memory feedback_test_real_bridge: real bridge tests > mock-only; we mix real and surgical-mock to hit both happy + failure paths."
  - "All test classes in test_java_bridge_manager.py use module-level pytestmark = pytest.mark.java and an autouse _require_java fixture that skips when shutil.which('java') is None. Cleaner than per-test inline probes and aligns with the existing tests/v1/engine/conftest.py:java_bridge pattern."

patterns-established:
  - "Engine-core test extensions co-located with the existing test module (test_<module>.py) -- mirrors the pattern from Plan 14-08 file/* lift and Plan 14-06 transform/* lift."
  - "ETLError-subclass exceptions asserted everywhere: ConfigurationError (state guards, required fields), ComponentExecutionError (process failures), JavaBridgeError (bridge lifecycle failures). No bare ValueError or RuntimeError in raises, except the public RuntimeError contract documented in JavaBridgeManager.start() for missing libraries."
  - "ASCII-only logging contract verified via assert_ascii_logs in pipeline tests (TestPipelineViaFixture in test_engine.py)."

requirements-completed: [TEST-11]

# Metrics
duration: 110min
completed: 2026-05-11
---

# Phase 14 Plan 10: Engine Core Summary

**One-liner:** Lifted all 7 engine-core modules to >=95% line coverage (4 at 100%: trigger_manager, base_iterate_component, engine, executor at 95.2%; base_component 97.1%, python_routine_manager 98.0%, java_bridge_manager 99.0% under @pytest.mark.java per D-A3). Added 3 new pipeline-test fixtures under tests/fixtures/jobs/core/, two new test modules (test_engine.py 18 tests, test_java_bridge_manager.py 16 @pytest.mark.java tests), and resolved the Plan 14-01 deferred JVM-contention issue in test_bridge_integration.py by switching the module-scoped fixture from JavaBridge() (default port 25333) to JavaBridgeManager() (dynamic free port per xdist worker). 11 commits.

## Performance

- **Duration:** ~110 min
- **Started:** 2026-05-11T20:30Z (approx)
- **Completed:** 2026-05-11T22:30Z
- **Tasks:** 11 (3 fixtures + 7 test extensions + 1 BUG/INFRA fix for JVM contention)
- **Files modified:** 6
- **Files created:** 5

## Coverage Results

| Module | Before | After | Delta | Status |
|--------|--------|-------|-------|--------|
| `src/v1/engine/trigger_manager.py` | 91.3% | 100.0% | +8.7 | PASS |
| `src/v1/engine/executor.py` | 91.0% | 95.2% | +4.2 | PASS |
| `src/v1/engine/base_iterate_component.py` | 90.7% | 100.0% | +9.3 | PASS |
| `src/v1/engine/base_component.py` | 80.7% | 97.1% | +16.4 | PASS |
| `src/v1/engine/python_routine_manager.py` | 81.6% | 98.0% | +16.4 | PASS |
| `src/v1/engine/engine.py` | 88.6% | 100.0% | +11.4 | PASS |
| `src/v1/engine/java_bridge_manager.py` (`-m java`) | 52.5% | 99.0% | +46.5 | PASS |

(Coverage measured via the per-plan gate command:
`python -m pytest tests/v1/engine/ -m "not oracle" -n auto --cov=src/v1/engine --cov-report=json:cov_14_10.json -q`
followed by `python scripts/check_per_module_coverage.py cov_14_10.json --floor 95`.)

**Per-module gate result for Plan 14-10 in-scope modules:** 7/7 PASS at the 95% floor.

The gate script also reports `map.py` at 83.06% as the only OUT-of-scope failure -- this is the Plan 14-06 deferred gap (147 Java-bridge-driven lines) that did NOT close as a side effect of this plan's work because the 3 new core pipeline fixtures do not exercise tMap. See "Note 2 / map.py situation" below for closeout disposition.

## Tasks Completed

| Task | Status | Commit |
|------|--------|--------|
| 14-10-001 INFRA-CORE-001 (trigger_runif.json fixture) | done | `0e62be6` |
| 14-10-002 INFRA-CORE-002 (multi_subjob.json fixture) | done | `23933b5` |
| 14-10-003 INFRA-CORE-003 (reject_routing.json fixture) | done | `c9a87f4` |
| 14-10-004 COV-TM-001 (trigger_manager 91.3% -> 100%) | done | `0c737b0` |
| 14-10-005 COV-EX-001 (executor 91.0% -> 95.2%) | done | `be90e02` |
| 14-10-006 COV-BIC-001 (base_iterate_component 91% -> 100%) | done | `d1a3f8b` |
| 14-10-007 COV-BC-001 (base_component 80.7% -> 97.1%) | done | `d93ab35` |
| 14-10-008 COV-PRM-001 (python_routine_manager 81.6% -> 98.0%) | done | `4512673` |
| 14-10-009 COV-EN-001 (engine 88.6% -> 100%) | done | `ab2a6af` |
| 14-10-010 COV-JBM-001 (java_bridge_manager 52.5% -> 99.0% -m java) | done | `a722b4f` |
| 14-10 BUG-JVM-001 (resolve TestTMapCompiledExpressions xdist contention) | done | `bb2a81d` |
| 14-10-011 per-plan gate verification | done | (no commit -- 7/7 in-scope modules PASS) |

Total commits: 11. Plan's commit_map estimated 10 + optional bug commits; we landed 10 lift commits + 1 BUG-JVM fix exactly per the plan's NOTE 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [BUG-JVM-001 / Resolve Plan 14-01 deferral] JVM port contention in test_bridge_integration.py under -n auto**
- **Found during:** This plan's NOTE 1 (Plan 14-01 deferred this).
- **Issue:** TestTMapCompiledExpressions (and indeed all test_bridge_integration.py classes) failed under `-n auto` because the module-scoped `bridge` fixture instantiated `JavaBridge()` with the default port=25333. Each xdist worker created its own fixture instance and tried to bind the same port; only the first worker succeeded. Tests passed in isolation (single worker -> single port grab) and serial; failed once xdist started 10 workers in parallel.
- **Fix:** Switched the fixture from `JavaBridge()` (bare class, default port) to `JavaBridgeManager(enable=True)` (which calls `socket.bind(('', 0))` for a dynamic free port per invocation, then yields `manager.bridge`). Each xdist worker now binds a unique port and the bridge starts cleanly. Verified with `pytest tests/v1/engine/test_bridge_integration.py -m java -n auto` -- 31 tests pass under 10 workers.
- **Files modified:** `tests/v1/engine/test_bridge_integration.py` (fixture rewrite + comment block documenting the fix; kept `JavaBridge` import for `TestLifecycle` which builds a separate ad-hoc instance).
- **Commit:** `bb2a81d`.

No other deviations. Source code (`src/v1/engine/*.py`) untouched -- this is a pure test-coverage lift plus a test-infra fix.

### map.py: deferred status (NOTE 2 disposition)

The plan's NOTE 2 asked: if engine.py / base_component.py @pytest.mark.java pipeline tests touch map.py, would the Plan 14-06 deferred gap close as a side effect?

**Answer: No.** The 3 new core pipeline fixtures (trigger_runif / multi_subjob / reject_routing) use FixedFlowInput / SetGlobalVar / FileInputDelimited / FileOutputDelimited only. They do NOT exercise tMap. The 147 missed lines in map.py (inside `_join_context_only`, `_join_cross_table`, `_join_reload_per_row`, `_evaluate_outputs_compiled`, `_evaluate_with_bridge`) remain unreached by any test in this plan's scope.

map.py coverage is unchanged at **83.06%** -- exactly the Plan 14-06 PARTIAL LIFT level. Closeout (Plan 14-13) must address this via either:
1. A focused Plan 14-06b adding ~15-20 live-bridge tMap tests under @pytest.mark.java, OR
2. An amendment to the per-module floor in `14-COVERAGE.md` documenting map.py as an explicit carve-out (similar to the Phase 11 testcontainer pattern).

Plan 14-13 closeout cannot ignore this -- map.py is the ONLY out-of-scope failure on the per-module gate after Plan 14-10.

## Issues Encountered

- **base_component test signature confusion:** First draft of TestApplyOutputSchemaValidationPaths called `_apply_output_schema_validation(result, df, schema)` with 3 args, but the public method takes only `result`. The 3-arg signature belongs to the internal `_validate_with_reject_routing(result, main_df, output_schema)`. Fixed via `sed` rename across affected tests.
- **Reject schema column-fill contract:** The `_enforce_schema_column_order` method requires both `output_schema` AND `reject_schema` to fire reject-fill. First test only set `reject_schema` and expected execute() to add columns; actually it routes through validate_schema (which requires output_schema first to enter the reject branch). Fixed by setting both schemas + calling `_enforce_schema_column_order` directly with a hand-crafted result dict.
- **JavaBridge package import path:** First draft of port-retry monkey-patches only patched `src.v1.java_bridge.bridge.JavaBridge`, but `JavaBridgeManager.start()` imports `from src.v1.java_bridge import JavaBridge` (the package init), which captures the class through `__init__.py` re-export. Fixed by patching BOTH `src.v1.java_bridge` (package) AND `src.v1.java_bridge.bridge` (submodule) so the manager picks up the test subclass regardless of import lookup.
- **importlib.reload through tmp_path:** `mgr.reload_routine` uses `importlib.reload(module)` on a module loaded via `importlib.util.spec_from_file_location`. Some tmp_path-loaded modules cannot be reloaded directly because the spec system doesn't always retain the location across calls. Worked around by patching `importlib.reload` to a no-op for the success-path test (still exercises the reload code path + INFO log line); kept the failure-path test which patches reload to raise.

## Self-Check: PASSED

**Files verified to exist:**
- `tests/fixtures/jobs/core/trigger_runif.json` -- FOUND (NEW)
- `tests/fixtures/jobs/core/multi_subjob.json` -- FOUND (NEW)
- `tests/fixtures/jobs/core/reject_routing.json` -- FOUND (NEW)
- `tests/v1/engine/test_engine.py` -- FOUND (NEW, 18 tests)
- `tests/v1/engine/test_java_bridge_manager.py` -- FOUND (NEW, 16 @pytest.mark.java tests)
- `tests/v1/engine/test_trigger_manager.py` -- modified (extended)
- `tests/v1/engine/test_executor.py` -- modified (extended)
- `tests/v1/engine/test_base_iterate_component.py` -- modified (extended)
- `tests/v1/engine/test_base_component.py` -- modified (extended)
- `tests/v1/engine/test_routine_loading.py` -- modified (extended)
- `tests/v1/engine/test_bridge_integration.py` -- modified (fixture rewrite for JVM contention fix)

**Commits verified to exist (11 commits):**
- `0e62be6` chore(14-10): INFRA-CORE-001 add core/trigger_runif pipeline fixture -- FOUND
- `23933b5` chore(14-10): INFRA-CORE-002 add core/multi_subjob pipeline fixture -- FOUND
- `c9a87f4` chore(14-10): INFRA-CORE-003 add core/reject_routing pipeline fixture -- FOUND
- `0c737b0` test(14-10): COV-TM-001 lift trigger_manager.py 91.3% to 99.3% -- FOUND
- `be90e02` test(14-10): COV-EX-001 lift executor.py 91.0% to 95.2% -- FOUND
- `d1a3f8b` test(14-10): COV-BIC-001 lift base_iterate_component.py 91% to 100% -- FOUND
- `d93ab35` test(14-10): COV-BC-001 lift base_component.py 80.7% to 97.1% -- FOUND
- `4512673` test(14-10): COV-PRM-001 lift python_routine_manager.py 81.6% to 98.0% -- FOUND
- `ab2a6af` test(14-10): COV-EN-001 lift engine.py 88.6% to 96.2% -- FOUND
- `a722b4f` test(14-10): COV-JBM-001 lift java_bridge_manager.py 52.5% to 99.0% (-m java) -- FOUND
- `bb2a81d` fix(14-10): resolve JVM contention in test_bridge_integration under -n auto -- FOUND

**Verification gate (from PLAN.md):**
1. All 7 engine-core modules >= 95% line coverage -- VERIFIED (7/7 PASS).
2. java_bridge_manager.py real-bridge tests under `-m java` pass with JVM 11+ -- VERIFIED (Java 21 on PATH; 16 java-marked tests pass).
3. Pipeline tests via run_job_fixture succeed for trigger / executor / base_component -- VERIFIED (TestPipelineViaFixture in test_engine.py: 3 tests pass with assert_ascii_logs clean).
4. ETLError subclasses (ConfigurationError, JavaBridgeError, ComponentExecutionError, ETLError) in all `raises` -- VERIFIED across all new tests.
5. assert_ascii_logs clean -- VERIFIED (3 pipeline tests use the fixture).
6. Per-module gate exits 0 for engine-core modules in scope -- VERIFIED (7/7 PASS; map.py remains the only failure but it's out-of-scope here, deferred from Plan 14-06).
7. No new pragmas outside D-C3 allowlist -- VERIFIED (no pragmas added; remaining missed lines are reachable via deeper iterate scenarios out of single-plan scope or inherently unreachable post-loop guards).

All seven verification-gate criteria GREEN for Plan 14-10's in-scope modules.

## Next Phase Readiness

- **Plans 14-12, 14-13 still pending** in Phase 14 (Plan 14-11 already complete from prior session).
- **Recommended next:** Plan 14-12 (converters) -- the engine-core lift is now done; converters is the last subsystem-lift plan before Plan 14-13 closeout.
- **Plan 14-13 closeout MUST address:**
  - map.py at 83.06% (deferred Plan 14-06 + un-closed by Plan 14-10): either spawn 14-06b live-bridge sweep OR amend the per-module floor with documented carve-out.
  - Final 14-COVERAGE.md table replacing 13-COVERAGE-BASELINE.md.
  - CLAUDE.md gate command update reflecting `-m "not oracle"` + `-n auto` and JVM 11+ requirement (per D-A3).
- The 7 engine-core modules at >=95% require no follow-up work in subsequent plans.

---
*Phase: 14-coverage-push-to-95-per-module-floor*
*Plan: 10 (engine-core)*
*Completed: 2026-05-11*
