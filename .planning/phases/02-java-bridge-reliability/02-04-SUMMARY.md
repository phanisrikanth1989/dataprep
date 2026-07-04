---
phase: 02-java-bridge-reliability
plan: 04
subsystem: java-bridge
tags: [java, py4j, arrow, groovy, integration-tests, maven, decimal, timestamp]

# Dependency graph
requires:
  - phase: 02-01
    provides: type_mapping.py and bridge.py rewrite
  - phase: 02-02
    provides: JavaBridge.java, ArrowSerializer.java, RowWrapper.java rewrite
  - phase: 02-03
    provides: JavaBridgeManager update, unit tests, converter type fixes
provides:
  - Built Java bridge JAR with maven-shade-plugin and Py4J 0.10.9.9
  - 27 integration tests with real JVM covering all 12 Talend data types
  - Fixed executeJavaRow output collection bug (getOutputRow vs get)
  - Fixed ArrowSerializer Java type name handling
  - Fixed ArrowSerializer timestamp/Decimal serialization
affects: [engine-components, tMap, tJavaRow, tJava]

# Tech tracking
tech-stack:
  added: [maven-shade-plugin 3.5.1]
  patterns: [module-scoped JVM fixture for integration tests, row-oriented tMap script output format]

key-files:
  created:
    - tests/v1/engine/test_bridge_integration.py
  modified:
    - src/v1/java_bridge/java/pom.xml
    - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java
    - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java
    - .gitignore

key-decisions:
  - "Added maven-shade-plugin to pom.xml for fat JAR creation (was missing, blocking JAR build)"
  - "Use TimeStampNanoVector instead of DateMilliVector to match Python pa.timestamp('ns')"
  - "Adjust Decimal scale with HALF_UP rounding in ArrowSerializer to avoid ArithmeticException"

patterns-established:
  - "Integration tests use module-scoped bridge fixture for JVM reuse across tests"
  - "tMap scripts must return {outputName: {data: Object[][], count: int}} format"
  - "Lifecycle tests use dynamic port allocation to avoid conflicts with module fixture"

requirements-completed: [BRDG-01, BRDG-04, BRDG-05, BRDG-06]

# Metrics
duration: 31min
completed: 2026-04-14
---

# Phase 02 Plan 04: JAR Build and Integration Tests Summary

**Built fat JAR with maven-shade-plugin, created 27 integration tests covering all 12 Talend data types round-trip through real JVM, fixed 4 Java bridge bugs found during integration testing**

## Performance

- **Duration:** 31 min
- **Started:** 2026-04-14T15:26:13Z
- **Completed:** 2026-04-14T15:58:12Z
- **Tasks:** 2 auto + 1 checkpoint (documented as awaiting human verify)
- **Files modified:** 5

## Accomplishments
- Java bridge JAR built with maven-shade-plugin containing Py4J 0.10.9.9, Arrow 15.0.2, Groovy 3.0.21
- 27 integration tests passing with real JVM: 15 type round-trips, 3 compiled scripts, 3 batch expressions, 2 library validation, 2 Py4J version, 2 lifecycle
- Decimal with custom precision (10, 2) verified end-to-end through Arrow serialization
- Found and fixed 4 bugs in Java bridge code during integration testing

## Task Commits

Each task was committed atomically:

1. **Task 1: Build Java bridge JAR with Maven** - `1375f21` (feat)
2. **Task 2: Create integration tests with real JVM** - `f9e0adc` (test + fix)
3. **Task 3: Human verification of complete Phase 2** - *checkpoint:human-verify (awaiting)*

## Files Created/Modified
- `src/v1/java_bridge/java/pom.xml` - Added maven-shade-plugin for fat JAR with signature exclusion
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` - Fixed output row collection (getOutputRow)
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java` - Fixed type mapping, timestamps, Decimal scale
- `tests/v1/engine/test_bridge_integration.py` - 27 integration tests with real JVM
- `.gitignore` - Added Maven target/ and dependency-reduced-pom.xml

## Decisions Made
- Added maven-shade-plugin to pom.xml because no fat JAR builder existed (pom.xml only had compiler plugin)
- Excluded META-INF signature files (*.SF, *.DSA, *.RSA) to avoid SecurityException with signed dependency JARs
- Changed ArrowSerializer to use TimeStampNanoVector instead of DateMilliVector to match Python's pa.timestamp("ns")
- Added Decimal scale adjustment with HALF_UP rounding to prevent ArithmeticException on precision mismatch

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added maven-shade-plugin to pom.xml**
- **Found during:** Task 1 (JAR build)
- **Issue:** pom.xml had no shade/assembly plugin -- `mvn package` created a thin JAR without dependencies, but bridge expects java-bridge-with-dependencies.jar (fat JAR)
- **Fix:** Added maven-shade-plugin 3.5.1 with outputFile, mainClass manifest, and META-INF signature exclusion
- **Files modified:** src/v1/java_bridge/java/pom.xml
- **Verification:** JAR built, bridge smoke test passes (1+1=2)
- **Committed in:** 1375f21 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed executeJavaRow output row collection**
- **Found during:** Task 2 (integration tests)
- **Issue:** JavaBridge.java line 230 used `output_row.get(colName)` which reads from RowWrapper.inputRow (always empty for output). Should use `output_row.getOutputRow().get(colName)` to read from outputRow map
- **Fix:** Changed to read from `output_row.getOutputRow()` map
- **Files modified:** src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java
- **Verification:** String round-trip test passes (was returning NaN for all values)
- **Committed in:** f9e0adc (Task 2 commit)

**3. [Rule 1 - Bug] Fixed ArrowSerializer Java type name handling**
- **Found during:** Task 2 (integration tests)
- **Issue:** ArrowSerializer.mapSchemaTypeToJava only accepted Python type strings ("str", "int"). bridge.py sends Java type names ("String", "Long") via _convert_schema_to_java. Unknown types defaulted to String, causing int/float/bool columns to serialize as VarChar
- **Fix:** Added Java type name cases (String, Long, Integer, Short, Byte, Double, Float, Boolean, Date, BigDecimal) to mapSchemaTypeToJava switch
- **Files modified:** src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java
- **Verification:** Integer round-trip returns int values instead of strings
- **Committed in:** f9e0adc (Task 2 commit)

**4. [Rule 1 - Bug] Fixed ArrowSerializer datetime/Decimal output vectors**
- **Found during:** Task 2 (integration tests)
- **Issue:** (a) Output used DateMilliVector but Python sends/expects timestamp("ns") causing epoch 0 returns. (b) Output DecimalVector(38, 10) mismatched input scale 18 causing hang. (c) Arrow getObject() returns LocalDateTime not java.util.Date
- **Fix:** (a) Changed to TimeStampNanoVector for datetime. (b) Changed default Decimal precision to (38, 18) and added scale adjustment with HALF_UP rounding. (c) Added LocalDateTime handling in setVectorValue
- **Files modified:** src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java
- **Verification:** Date, timestamp, and BigDecimal round-trip tests all pass
- **Committed in:** f9e0adc (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (1 blocking, 3 bugs)
**Impact on plan:** All fixes were essential for the integration tests to pass. The bugs existed in code from Plans 01-02 but were only discoverable with real JVM execution (unit tests used mocks). No scope creep -- this is exactly why integration tests exist.

## Issues Encountered
- First test run hung because Groovy scripts used `input.get()`/`output.set()` instead of `input_row.get()`/`output_row.set()` (binding variable names in JavaBridge.java are `input_row`/`output_row`)
- BigDecimal round-trip hung because Arrow DecimalVector.setSafe throws ArithmeticException when scale mismatch causes an infinite retry in Py4J
- Compiled tMap scripts must return `{outputName: {data: Object[][], count: int}}` format, not column-oriented maps

## Checkpoint Status

**Task 3 (Human Verification):** Awaiting human verify

The following verification steps should be run to confirm Phase 2 completeness:
1. `python -m pytest tests/v1/engine/ tests/converters/ -x -q` -- full test suite green
2. `python -m pytest tests/v1/engine/test_bridge_integration.py -x -v -m java` -- 27 integration tests pass
3. `grep -rn '"type": "id_' tests/talend_xml_samples/converted_jsons/` -- zero matches (no raw Talend types)
4. `grep -rn "print(" src/v1/java_bridge/ src/v1/engine/java_bridge_manager.py` -- zero matches
5. `grep -rn "System.out" src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/` -- zero matches
6. `grep -n "_reconcile_schema_to_df\|_capture_java_stderr" src/v1/java_bridge/bridge.py` -- both present

## User Setup Required
- Maven must be installed: `brew install maven`
- Java 11+ must be installed (OpenJDK 21 confirmed working)
- JAR must be built before running integration tests: `cd src/v1/java_bridge/java && mvn clean package -q`

## Next Phase Readiness
- Java bridge fully operational with all 12 Talend data types verified
- Phase 2 complete pending human verification checkpoint
- Ready for Phase 3 (engine execution loop) which depends on reliable bridge

## Self-Check: PASSED

All files exist, all commits verified:
- tests/v1/engine/test_bridge_integration.py: FOUND
- .planning/phases/02-java-bridge-reliability/02-04-SUMMARY.md: FOUND
- src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar: FOUND
- Commit 1375f21 (Task 1): FOUND
- Commit f9e0adc (Task 2): FOUND

---
*Phase: 02-java-bridge-reliability*
*Completed: 2026-04-14*
