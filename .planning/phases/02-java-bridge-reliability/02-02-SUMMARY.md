---
phase: 02-java-bridge-reliability
plan: 02
subsystem: java-bridge
tags: [py4j, arrow, groovy, java, jvm, serialization]

# Dependency graph
requires:
  - phase: 02-java-bridge-reliability plan 01
    provides: Python-side bridge.py rewrite with schema-driven serialization
provides:
  - Rewritten JavaBridge.java with JUL logging and clean type mapping
  - New ArrowSerializer.java with 7-type mapSchemaTypeToJava
  - Rewritten RowWrapper.java with map-based row accessor interface
  - Py4J 0.10.9.9 in pom.xml (version alignment with Python side)
  - Compiled script class caching (BRDG-06 fix)
  - File-existence library validation (BRDG-04 fix)
affects: [02-java-bridge-reliability plan 03, 02-java-bridge-reliability plan 04, phase 04 tMap, phase 05 tJava/tJavaRow]

# Tech tracking
tech-stack:
  added: []
  patterns: [ArrowSerializer utility class for all Arrow operations, Script class caching for thread-safe Groovy execution, JUL logging with JavaBridge prefix]

key-files:
  created:
    - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java
  modified:
    - src/v1/java_bridge/java/pom.xml
    - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java
    - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java

key-decisions:
  - "Keep executeBatchOneTimeExpressionsWithGlobalMap as backward-compatible alias delegating to renamed executeBatchOneTimeExpressions"
  - "RowWrapper simplified to pure Map-based interface -- Arrow vector reading moved to JavaBridge.buildArrowRowWrapper helper"
  - "executeJavaRow uses sequential row processing with fresh Script instances instead of synchronized parallel -- correctness over parallelism"

patterns-established:
  - "ArrowSerializer: static utility class for all Arrow vector creation/population -- single place for type mapping"
  - "Script class caching: compileTMapScript caches Class<Script> not Script instance, each execution creates fresh instance with own Binding"
  - "JUL logging with [JavaBridge] prefix on every log message for Python/Java log interleaving"

requirements-completed: [BRDG-04, BRDG-05, BRDG-06]

# Metrics
duration: 5min
completed: 2026-04-14
---

# Phase 02 Plan 02: Java Bridge Server Rewrite Summary

**Rewritten JavaBridge.java with ArrowSerializer extraction, Script class caching (BRDG-06), file-based library validation (BRDG-04), and Py4J 0.10.9.9 alignment (BRDG-05)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-14T15:05:54Z
- **Completed:** 2026-04-14T15:11:11Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Rewrote JavaBridge.java from scratch: zero println, all JUL logging with [JavaBridge] prefix, dead code removed
- Created ArrowSerializer.java with clean 7-type mapSchemaTypeToJava replacing old inferJavaTypeFromSchema (no id_* types)
- Fixed BRDG-06: compiledScriptClasses caches Script classes not instances, each execution gets fresh Binding -- no synchronized(script) bottleneck
- Fixed BRDG-04: validateLibraries uses file existence check + Class.forName instead of string-contains on classpath
- Fixed BRDG-05: Py4J updated from 0.10.9.7 to 0.10.9.9 in pom.xml (Arrow 15.0.2 and Groovy 3.0.21 unchanged)
- Rewrote RowWrapper.java with clean Map-based inputRow/outputRow interface and proper JUL logging

## Task Commits

Each task was committed atomically:

1. **Task 1: Update pom.xml and rewrite RowWrapper.java** - `1ffe40b` (feat)
2. **Task 2: Rewrite JavaBridge.java + create ArrowSerializer.java** - `bfd2495` (feat)

## Files Created/Modified
- `src/v1/java_bridge/java/pom.xml` - Updated Py4J from 0.10.9.7 to 0.10.9.9
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` - Full rewrite: JUL logging, Script class caching, dead code removal
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java` - New file: Arrow serialization utilities with mapSchemaTypeToJava
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` - Rewritten: clean Map-based interface, JUL logging

## Decisions Made
- **Backward-compatible alias:** Kept `executeBatchOneTimeExpressionsWithGlobalMap` as a delegate to the renamed `executeBatchOneTimeExpressions` since the Python client currently calls the WithGlobalMap variant. This avoids needing a coordinated rename across plans.
- **RowWrapper simplification:** Removed Arrow vector reading from RowWrapper entirely. The new RowWrapper is a pure Map wrapper. Arrow-to-Map extraction is done in `JavaBridge.buildArrowRowWrapper()` before passing to RowWrapper. This makes RowWrapper simpler and testable without Arrow dependencies.
- **Sequential row execution:** Changed `executeJavaRow` from parallel `IntStream.range().parallel()` with `synchronized(compiledScript)` to sequential loop with fresh Script instances per row. This is correct by construction (no shared mutable state) and avoids the synchronized bottleneck. Performance is acceptable for ETL batch sizes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added executeCompiledTMapChunked backward-compatible alias**
- **Found during:** Task 2 (JavaBridge rewrite)
- **Issue:** Python client bridge.py calls `executeCompiledTMap` for chunked execution. The old Java code had this as a separate method. Plan only mentioned keeping executeCompiledTMap.
- **Fix:** Added `executeCompiledTMapChunked` that delegates to `executeCompiledTMap` for backward compatibility.
- **Files modified:** JavaBridge.java
- **Committed in:** bfd2495

**2. [Rule 2 - Missing Critical] Added backward-compatible executeBatchOneTimeExpressionsWithGlobalMap alias**
- **Found during:** Task 2 (JavaBridge rewrite)
- **Issue:** Python client calls `executeBatchOneTimeExpressionsWithGlobalMap` by name via Py4J. Simply renaming would break the Python client until Plan 01 changes are merged.
- **Fix:** Kept `executeBatchOneTimeExpressionsWithGlobalMap` as an alias delegating to `executeBatchOneTimeExpressions`.
- **Files modified:** JavaBridge.java
- **Committed in:** bfd2495

---

**Total deviations:** 2 auto-fixed (2 missing critical -- backward compatibility)
**Impact on plan:** Both auto-fixes ensure the rewritten Java server works with the existing Python client. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Java server side is fully rewritten and ready for integration testing (Plan 03)
- Plans 01 (Python side) and 02 (Java side) must both be merged before Plan 03 integration tests can run
- The ArrowSerializer.mapSchemaTypeToJava type mapping is the Java-side complement to the Python type_mapping.py -- they must stay in sync

## Self-Check: PASSED

All 4 source files exist. Both task commits (1ffe40b, bfd2495) verified in git log. No stubs found. No new threat surface.

---
*Phase: 02-java-bridge-reliability*
*Completed: 2026-04-14*
