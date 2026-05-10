---
phase: 14
plan: 10
slug: engine-core
type: execute
wave: 2
depends_on: [14-01]
files_modified:
  - tests/v1/engine/test_trigger_manager.py
  - tests/v1/engine/test_executor.py
  - tests/v1/engine/test_base_iterate_component.py
  - tests/v1/engine/test_base_component.py
  - tests/v1/engine/test_python_routine_manager.py
  - tests/v1/engine/test_engine.py
  - tests/v1/engine/test_java_bridge_manager.py
  - tests/fixtures/jobs/core/trigger_runif.json
  - tests/fixtures/jobs/core/multi_subjob.json
  - tests/fixtures/jobs/core/reject_routing.json
  - src/v1/engine/*.py  # only if BUGs surface
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "All 7 engine-core modules reach >= 95% line coverage"
    - "java_bridge_manager.py is measured WITH @pytest.mark.java tests (D-A3); JVM 11+ available in execution env"
    - "Pipeline tests via run_job_fixture exercise multi-subjob orchestration, trigger firing, reject routing"
    - "ETLError subclasses asserted in raises (ConfigurationError, JavaBridgeError, ComponentExecutionError, etc.)"
  artifacts:
    - path: tests/v1/engine/test_<core_module>.py
      provides: extension of engine-core tests for missed-line clusters
    - path: tests/fixtures/jobs/core/trigger_runif.json
      provides: pipeline fixture for trigger_manager (RunIf, OnComponentOk/Error, OnSubjobOk timing)
    - path: tests/fixtures/jobs/core/multi_subjob.json
      provides: pipeline fixture for executor.py multi-subjob orchestration + finalization order
    - path: tests/fixtures/jobs/core/reject_routing.json
      provides: pipeline fixture for base_component reject flow + die_on_error contract
  key_links:
    - from: tests/v1/engine/test_*.py (core)
      to: src/v1/engine/*.py
      via: direct unit tests + run_job_fixture pipeline tests + @pytest.mark.java for java_bridge_manager
---

<objective>
Lift the 7 engine-core modules: `trigger_manager.py` (91%, 13 missed), `executor.py` (91%, 30), `base_iterate_component.py` (88%, 11), `base_component.py` (87%, 69 missed -- largest core), `python_routine_manager.py` (82%, 18), `engine.py` (81%, 33), `java_bridge_manager.py` (59%, 41 -- needs `-m java` tests per D-A3). Mix of unit + pipeline tests. `java_bridge_manager.py` measured WITH `-m java` markers per D-A3 -- the gate command requires JVM 11+ in execution env.
</objective>

<scope>
- NEW pipeline-job fixtures:
    - `tests/fixtures/jobs/core/trigger_runif.json` -- 3-component pipeline with RunIf trigger; exercises `trigger_manager.py` RunIf + condition-evaluation branches
    - `tests/fixtures/jobs/core/multi_subjob.json` -- 4-component pipeline across 2 subjobs with OnSubjobOk trigger; exercises `executor.py` finalization order + subjob boundary
    - `tests/fixtures/jobs/core/reject_routing.json` -- 3-component pipeline with reject flow; exercises `base_component.py` reject schema + die_on_error
- MODIFIED tests:
    - `tests/v1/engine/test_trigger_manager.py` -- RunIf branches, OnComponentOk/Error, OnSubjobOk timing (Phase 1 ENG-10 / Phase 3), `!=` operator preservation (Phase 1 ENG-06 regression guard).
    - `tests/v1/engine/test_executor.py` -- Phase 12 commit 55d8354 finalization order; iterate stall paths; reject-flow routing; topological sort edge cases; multi-subjob orchestration via pipeline test.
    - `tests/v1/engine/test_base_iterate_component.py` -- iteration finalization, should_stop variants, `_CURRENT_ITERATE` globalMap variable (Phase 10 ITER-11).
    - `tests/v1/engine/test_base_component.py` -- 69 missed lines (largest core gap, 526 stmts). Cover: schema validation + dtype coercion + reject-flow + die_on_error + per-chunk streaming + treat_empty_as_null + datetime/Decimal/float precision (Phase 7.1 patches). Use realistic-shape DataFrames per D-C4.
    - `tests/v1/engine/test_python_routine_manager.py` -- routine discovery, load failures, namespace assembly, malformed routine file -> `ConfigurationError`.
    - `tests/v1/engine/test_engine.py` -- top-level orchestration, error-handling, _cleanup() idempotency, OracleConnectionManager / JavaBridgeManager / PythonRoutineManager wiring per Phase 11 D-A1.
    - `tests/v1/engine/test_java_bridge_manager.py` -- `-m java` real-bridge tests for: port retry loop (RESEARCH §A6: monkey-patch `JavaBridge.start` to seed "Address already in use"), library validation (`libraries=["nonexistent.jar"]` -> `RuntimeError("Missing required libraries...")`), routine loading mix valid/invalid -> `JavaBridgeError("Failed to load routines: ...")`, stop() idempotency (call twice), is_available()/get_bridge() before start / after start / after stop, `__enter__`/`__exit__` context manager, `__repr__`.
- POSSIBLY MODIFIED: source files only if real bugs surface.
</scope>

<out_of_scope>
- Already-at-95% engine-core modules: `__init__.py`, `components/__init__.py`, `component_registry.py`, `exceptions.py`, `context_manager.py`, `global_map.py`, `output_router.py`, `oracle_connection_manager.py`, `execution_plan.py`, `iterate_logging.py`.
- Java bridge implementation in `src/v1/java_bridge/bridge.py` (out of `src/v1/engine/`; not in coverage scope).
- Real Java/Maven build steps (Phase 13 already rebuilt JAR; the JAR is current per RESEARCH §Existing JAR sufficiency).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage core; §Java Bridge Gate Strategy (java_bridge_manager 59% gap analysis); §Pitfall 5 (JVM env requirement)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-A3, D-C1
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-CONTEXT.md` (JAR rebuild context)
- `src/v1/engine/trigger_manager.py`, `executor.py`, `base_iterate_component.py`, `base_component.py`, `python_routine_manager.py`, `engine.py`, `java_bridge_manager.py` (lift targets)
- `tests/v1/engine/conftest.py` (existing `java_bridge` fixture, `_find_java_bridge_jar` worktree handling)
- `tests/integration/test_iterate_e2e.py` (pipeline-test pattern reference)
- `tests/conftest.py` (run_job_fixture from Plan 14-01)
- `src/v1/engine/exceptions.py`
</canonical_refs>

<waves>

## Wave 0 -- Pipeline-test fixtures

### Task 14-10-001 -- Generate trigger_runif pipeline fixture
- **Type:** fixture
- **Description:** 3-component pipeline: tFixedFlowInput -> tRunIf -> tFileOutputDelimited (output only when condition true). Exercises `trigger_manager.py` RunIf condition evaluation.
- **Files:** `tests/fixtures/jobs/core/trigger_runif.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/core/trigger_runif.json')); assert any(t.get('type')=='RunIf' or 'RunIf' in str(t) for t in c.get('triggers',[])); print('ok')"`
- **Expected:** `ok`.

### Task 14-10-002 -- Generate multi_subjob pipeline fixture
- **Type:** fixture
- **Description:** 4-component pipeline across 2 subjobs with OnSubjobOk trigger between them. Exercises `executor.py` _execute_subjob finalization order.
- **Files:** `tests/fixtures/jobs/core/multi_subjob.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/core/multi_subjob.json')); assert len(c.get('subjobs',[])) >= 2; print('ok')"`
- **Expected:** `ok`.

### Task 14-10-003 -- Generate reject_routing pipeline fixture
- **Type:** fixture
- **Description:** 3-component pipeline: tFileInputDelimited (CHECK_FIELDS_NUM=true) with reject flow routed to tFileOutputDelimited. Exercises `base_component.py` reject schema + die_on_error contract.
- **Files:** `tests/fixtures/jobs/core/reject_routing.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/core/reject_routing.json')); print('ok')"`
- **Expected:** `ok`.

## Wave 1 -- Test extensions

### Task 14-10-004 -- Lift trigger_manager.py to 95%
- **Files:** `tests/v1/engine/test_trigger_manager.py`
- **Description:** Cover RunIf condition evaluation + OnComponentOk/Error + OnSubjobOk timing branches (Phase 1 ENG-10) + `!=` operator preservation (Phase 1 ENG-06 regression guard). Optional pipeline test via `run_job_fixture("core/trigger_runif", ...)`.
- **Verification:** `python -m pytest tests/v1/engine/test_trigger_manager.py --cov=src/v1/engine/trigger_manager --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-10-005 -- Lift executor.py to 95%
- **Files:** `tests/v1/engine/test_executor.py`
- **Description:** Cover Phase 12 commit `55d8354` finalization order; iterate stall paths; reject-flow routing in `_route_component_outputs`; topological sort edge cases (cycles -> ConfigurationError). Pipeline test via `run_job_fixture("core/multi_subjob", ...)`.
- **Verification:** `python -m pytest tests/v1/engine/test_executor.py --cov=src/v1/engine/executor --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-10-006 -- Lift base_iterate_component.py to 95%
- **Files:** `tests/v1/engine/test_base_iterate_component.py`
- **Description:** Cover iteration finalization + should_stop variants + _CURRENT_ITERATE globalMap (ITER-11). Use IterateStubComponent fixture from existing `tests/v1/engine/conftest.py`.
- **Verification:** `python -m pytest tests/v1/engine/test_base_iterate_component.py --cov=src/v1/engine/base_iterate_component --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-10-007 -- Lift base_component.py to 95% (largest core gap, 526 stmts, 69 missed)
- **Files:** `tests/v1/engine/test_base_component.py`
- **Description:** Cover schema validation + dtype coercion (datetime / Decimal / float / string with precision -- Phase 7.1 patches) + reject-flow + die_on_error contract + per-chunk streaming + treat_empty_as_null. Use realistic-shape DataFrames per D-C4 (mixed dtypes; pandas 3.0 + CoW). Pipeline test via `run_job_fixture("core/reject_routing", ...)`.
- **Verification:** `python -m pytest tests/v1/engine/test_base_component.py --cov=src/v1/engine/base_component --cov-report=term-missing -q`
- **Expected:** >= 95%.
- **Notes:** This is the largest single test extension in the core plan. Likely 20+ new tests. Use `@pytest.mark.slow` for pipeline tests if any exceed 5s.

### Task 14-10-008 -- Lift python_routine_manager.py to 95%
- **Files:** `tests/v1/engine/test_python_routine_manager.py`
- **Description:** Cover routine discovery + load failures (malformed file -> ConfigurationError; missing entry-point function) + namespace assembly + reload behavior. Use `tmp_path` to write synthetic routine files for isolation.
- **Verification:** `python -m pytest tests/v1/engine/test_python_routine_manager.py --cov=src/v1/engine/python_routine_manager --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-10-009 -- Lift engine.py to 95%
- **Files:** `tests/v1/engine/test_engine.py`
- **Description:** Cover top-level orchestration paths -- error-handling in `run()` / `execute()`, `_cleanup()` idempotency, manager wiring (JavaBridge / PythonRoutine / OracleConnection), context-param overrides via CLI, malformed JSON config -> ConfigurationError.
- **Verification:** `python -m pytest tests/v1/engine/test_engine.py --cov=src/v1/engine/engine --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-10-010 -- Lift java_bridge_manager.py to 95% (-m java)
- **Files:** `tests/v1/engine/test_java_bridge_manager.py`
- **Description:** All tests in this task are `@pytest.mark.java`. Use existing `java_bridge` fixture from `tests/v1/engine/conftest.py`. Cover (per RESEARCH §java_bridge_manager.py 59% gap analysis):
    - Port retry loop (RESEARCH §A6: monkey-patch `JavaBridge.start` to seed "Address already in use" string -- the retry path catches that exact substring)
    - Library validation: `self.libraries = ["nonexistent.jar"]` config -> `RuntimeError("Missing required libraries...")`. Assert exception type + message.
    - Routine loading: mix of valid + invalid routine class names -> `JavaBridgeError("Failed to load routines: [...]")`.
    - stop() idempotency (call twice; no error).
    - stop() during exception (e.g. start fails -> __exit__ stops).
    - is_available() and get_bridge() before start / after start / after stop.
    - `__enter__` / `__exit__` context manager.
    - `__repr__`.
    Top-of-test JVM probe: `import shutil; assert shutil.which("java"), "JVM 11+ required for -m java tests"` (per RESEARCH §Pitfall 5).
- **Verification:** `python -m pytest tests/v1/engine/test_java_bridge_manager.py -m java --cov=src/v1/engine/java_bridge_manager --cov-report=term-missing -q`
- **Expected:** >= 95% (when JVM available); tests skipped (with clear message) when JVM absent.
- **Notes:** Per-module gate command (Plan 14-12 closeout) MUST run with JVM available. Local dev without Java will see this module fall below floor; documented in CLAUDE.md.

### Task 14-10-011 -- Per-plan gate verification
- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/ -m "not oracle" -n auto \
      --cov=src/v1/engine --cov-report=json:cov_14_10.json -q
    python scripts/check_per_module_coverage.py cov_14_10.json --floor 95
    ```
- **Expected:** PASS for all 7 modules in scope (assumes JVM 11+ available).

</waves>

<verification_gate>

Plan 14-10 is GREEN when:
1. All 7 engine-core modules >= 95% line coverage.
2. `java_bridge_manager.py` real-bridge tests under `-m java` pass with JVM 11+.
3. Pipeline tests via `run_job_fixture` succeed for trigger / executor / base_component.
4. ETLError subclasses (ConfigurationError, JavaBridgeError, ComponentExecutionError, ETLError) in all `raises`.
5. `assert_ascii_logs` clean.
6. Per-module gate exits 0 for engine-core modules in scope.
7. No new pragmas outside D-C3 allowlist.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-10): INFRA-CORE-001 add core/trigger_runif pipeline fixture` | `tests/fixtures/jobs/core/trigger_runif.json` |
| 2 | `chore(14-10): INFRA-CORE-002 add core/multi_subjob pipeline fixture` | `tests/fixtures/jobs/core/multi_subjob.json` |
| 3 | `chore(14-10): INFRA-CORE-003 add core/reject_routing pipeline fixture` | `tests/fixtures/jobs/core/reject_routing.json` |
| 4 | `test(14-10): COV-TM-001 lift trigger_manager.py to 95% (RunIf + OnComponentOk/Error + OnSubjobOk timing)` | `tests/v1/engine/test_trigger_manager.py` |
| 5 | `test(14-10): COV-EX-001 lift executor.py to 95% (finalization order + iterate stalls + reject routing + topo edges + pipeline)` | `tests/v1/engine/test_executor.py` |
| 6 | `test(14-10): COV-BIC-001 lift base_iterate_component.py to 95% (finalization + should_stop + _CURRENT_ITERATE)` | `tests/v1/engine/test_base_iterate_component.py` |
| 7 | `test(14-10): COV-BC-001 lift base_component.py to 95% (schema + dtype + reject + die_on_error + streaming + treat_empty_as_null + pipeline)` | `tests/v1/engine/test_base_component.py` |
| 8 | `test(14-10): COV-PRM-001 lift python_routine_manager.py to 95% (discovery + load failures + namespace)` | `tests/v1/engine/test_python_routine_manager.py` |
| 9 | `test(14-10): COV-EN-001 lift engine.py to 95% (orchestration + cleanup idempotency + manager wiring)` | `tests/v1/engine/test_engine.py` |
| 10 | `test(14-10): COV-JBM-001 lift java_bridge_manager.py to 95% (-m java) (port retry + library validation + routine load + stop idempotency)` | `tests/v1/engine/test_java_bridge_manager.py` |
| 11+ (conditional) | `fix(14-10): BUG-CORE-NN <description>` -- only if bug surfaces | source files |

(Total: 10 + optional bug commits.)

</commit_map>
