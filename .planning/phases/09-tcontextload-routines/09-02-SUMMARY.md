---
phase: 09-tcontextload-routines
plan: 02
subsystem: engine
tags: [routines, java-bridge, classpath, python-routines, namespace, fail-fast]

# Dependency graph
requires:
  - phase: 02-java-bridge
    provides: JavaBridge with Py4J lifecycle and bridge.py start() method
provides:
  - Extended Java bridge classpath for routine JARs
  - PythonRoutineManager subdirectory scanning and RoutineNamespace
  - Fail-fast validation for required routines at job startup
  - Engine wiring for routine_jars and required_routines from job config
affects: [10-iterate-support, engine-components]

# Tech tracking
tech-stack:
  added: []
  patterns: [routine-namespace-access, fail-fast-validation, classpath-extension]

key-files:
  created:
    - tests/v1/engine/test_routine_loading.py
  modified:
    - src/v1/java_bridge/bridge.py
    - src/v1/engine/java_bridge_manager.py
    - src/v1/engine/python_routine_manager.py
    - src/v1/engine/engine.py

key-decisions:
  - "RoutineNamespace uses __getattr__ for routines.Name.method() access, raising AttributeError with available list on miss"
  - "Subdirectory routines registered under both qualified (system.TalendString) and short (TalendString) names, top-level wins collision"
  - "Path.resolve() canonicalizes JAR paths to prevent symlink tricks (T-09-06 mitigation)"

patterns-established:
  - "Routine namespace access: manager.get_namespace().RoutineName.method()"
  - "Fail-fast required routines: PythonRoutineManager(dir, required_routines=[...]) raises RuntimeError on missing"
  - "Classpath extension: bridge.start(routine_jars=[...]) supports files and directories"

requirements-completed: [ROUT-01, ROUT-02, ROUT-03]

# Metrics
duration: 6min
completed: 2026-04-15
---

# Phase 09 Plan 02: Python Routine Loading Summary

**Extended Java bridge classpath for routine JARs, added PythonRoutineManager subdirectory scanning with RoutineNamespace access pattern, and fail-fast validation for required routines at job startup**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-15T11:45:27Z
- **Completed:** 2026-04-15T11:51:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Java bridge start() extended with routine_jars parameter for JVM classpath extension (supports individual JARs and directory scanning)
- PythonRoutineManager enhanced with subdirectory scanning, RoutineNamespace for attribute-based access, and required_routines fail-fast validation
- JavaBridgeManager passes routine_jars through to bridge.start() transparently
- Engine wired to read routine_jars from java_config and routines from python_config at startup
- 28 unit tests covering all new functionality with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Java bridge classpath and PythonRoutineManager** - `01caf60` (feat)
2. **Task 2: Unit tests for routine loading enhancements** - `1255eba` (test)

## Files Created/Modified
- `src/v1/java_bridge/bridge.py` - Extended start() with routine_jars, classpath construction from multiple entries
- `src/v1/engine/java_bridge_manager.py` - Added routine_jars parameter, passes through to bridge.start()
- `src/v1/engine/python_routine_manager.py` - Added RoutineNamespace class, subdirectory scanning, required_routines fail-fast, get_namespace() method
- `src/v1/engine/engine.py` - Reads routine_jars from java_config, required routines from python_config
- `tests/v1/engine/test_routine_loading.py` - 28 unit tests across 7 test classes (437 lines)

## Decisions Made
- RoutineNamespace uses `__getattr__` for attribute-based access with descriptive AttributeError listing available routines on miss
- Subdirectory routines registered under both qualified name (e.g., `system.TalendString`) and short name (`TalendString`), with top-level routines winning name collisions
- Path.resolve() used to canonicalize JAR paths before adding to classpath (T-09-06 symlink mitigation)
- Directory mode for routine_jars scans for *.jar files within the directory (supports lib/ style deployments)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Routine loading infrastructure complete for both Java and Python paths
- Engine components can now access Python routines via namespace pattern
- Java bridge classpath can include custom routine JARs from job config
- Ready for iterate support work in Phase 10

## Self-Check: PASSED

- All 5 source/test files verified present on disk
- Commit 01caf60 (Task 1) verified in git log
- Commit 1255eba (Task 2) verified in git log
- 28/28 tests pass, 537 existing engine tests pass (1 pre-existing JAR-missing error)

---
*Phase: 09-tcontextload-routines*
*Completed: 2026-04-15*
