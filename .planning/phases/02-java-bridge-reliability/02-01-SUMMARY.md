---
phase: 02-java-bridge-reliability
plan: 01
subsystem: java-bridge
tags: [pyarrow, py4j, type-mapping, arrow-serialization, java-bridge]

# Dependency graph
requires:
  - phase: 01-infrastructure-bug-fixes-project-setup
    provides: "BaseComponent rewrite with clean lifecycle, custom exception hierarchy"
provides:
  - "type_mapping.py: 7-type Python-to-Arrow contract for all bridge operations"
  - "bridge.py: schema-driven Arrow serialization with automatic sync"
  - "tMap/tXMLMap converters produce only Python type strings"
  - "BaseComponent._TYPE_MAPPING cleaned to Python-only types"
affects: [02-02, 02-03, 02-04, 04-tmap, 05-code-components]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Schema-driven Arrow serialization (never infer from data)"
    - "_call_java_with_sync wrapper for guaranteed context/globalMap sync"
    - "7-type contract (str, int, float, bool, datetime, Decimal, object)"
    - "Java stderr capture in bridge error messages"

key-files:
  created:
    - "src/v1/java_bridge/type_mapping.py"
  modified:
    - "src/v1/java_bridge/bridge.py"
    - "src/v1/java_bridge/__init__.py"
    - "src/converters/talend_to_v1/components/transform/map.py"
    - "src/converters/talend_to_v1/components/transform/xml_map.py"
    - "src/v1/engine/base_component.py"
    - "tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json"
    - "tests/talend_xml_samples/converted_jsons/Job_tXMLMap_0.1.json"
    - "tests/converters/talend_to_v1/components/transform/test_map.py"

key-decisions:
  - "7 canonical Python types only (str, int, float, bool, datetime, Decimal, object) -- no id_* anywhere in bridge"
  - "Schema-driven Arrow serialization replaces data-inference approach"
  - "_call_java_with_sync wrapper ensures sync even on exception"
  - "Java stderr captured non-blocking for enriched error diagnostics"
  - "_reconcile_schema_to_df adds missing columns as str with warning rather than crashing"

patterns-established:
  - "Bridge type contract: all types must be one of 7 Python type strings before reaching bridge"
  - "Converter convert_type() call at every type extraction point in tMap/tXMLMap"
  - "Automatic Java state sync after every Java call via _call_java_with_sync"

requirements-completed: [BRDG-01, BRDG-02, BRDG-03]

# Metrics
duration: 8min
completed: 2026-04-14
---

# Phase 02 Plan 01: Type Mapping and Bridge Rewrite Summary

**7-type Python-to-Arrow contract in type_mapping.py, full bridge.py rewrite with schema-driven serialization and guaranteed sync, tMap/tXMLMap converter type bugs fixed**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-14T15:05:45Z
- **Completed:** 2026-04-14T15:13:43Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Created type_mapping.py with 7-type contract (PYTHON_TO_ARROW, PYTHON_TO_JAVA, VALID_TYPES, validate_schema_types, build_arrow_schema, extract_precision_map)
- Fully rewrote bridge.py from scratch: schema-driven Arrow serialization, automatic _sync_from_java on every Java call, zero print statements, Java stderr capture in error messages
- Fixed tMap converter (3 locations) and tXMLMap converter (4 locations) to produce Python type strings via convert_type()
- Re-converted both affected JSON files with zero id_* type strings remaining
- Cleaned BaseComponent._TYPE_MAPPING from 20 entries (13 id_* + 7 simple) to 7 canonical Python types only

## Task Commits

Each task was committed atomically:

1. **Task 1: Create type_mapping.py + fix converters + clean BaseComponent** - `22473f8` (feat)
2. **Task 2: Rewrite bridge.py with schema-driven serialization and auto sync** - `eb44a37` (feat)
3. **Test fix: Update tMap tests for Python type strings** - `b9fb638` (fix)

## Files Created/Modified
- `src/v1/java_bridge/type_mapping.py` - NEW: 7-type Python-to-Arrow mapping contract
- `src/v1/java_bridge/bridge.py` - REWRITE: schema-driven serialization, auto-sync, no prints
- `src/v1/java_bridge/__init__.py` - Updated exports to include type_mapping functions
- `src/converters/talend_to_v1/components/transform/map.py` - Fixed 3 convert_type calls
- `src/converters/talend_to_v1/components/transform/xml_map.py` - Fixed 4 convert_type calls
- `src/v1/engine/base_component.py` - Cleaned _TYPE_MAPPING to 7 Python types, fixed default
- `tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json` - Re-converted with Python types
- `tests/talend_xml_samples/converted_jsons/Job_tXMLMap_0.1.json` - Re-converted with Python types
- `tests/converters/talend_to_v1/components/transform/test_map.py` - Updated type assertions

## Decisions Made
- 7 canonical types cover all Talend types needed by the engine (str, int, float, bool, datetime, Decimal, object)
- Schema-driven Arrow serialization replaces data-inference _build_arrow_schema approach for deterministic behavior
- _call_java_with_sync wraps Java calls with try/finally sync to ensure bidirectional state stays consistent
- _reconcile_schema_to_df provides graceful degradation for incomplete schemas rather than crashing
- Java stderr captured via non-blocking read (select + read) for richer error diagnostics

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed import path for convert_type in converters**
- **Found during:** Task 1 (Part D -- re-conversion)
- **Issue:** `from ..type_mapping import convert_type` resolved to wrong package level (components/ instead of talend_to_v1/)
- **Fix:** Changed to `from ...type_mapping import convert_type` (three dots for correct parent package)
- **Files modified:** map.py, xml_map.py
- **Committed in:** 22473f8

**2. [Rule 1 - Bug] Updated tMap tests expecting old id_* type strings**
- **Found during:** Post-task verification
- **Issue:** 3 test assertions expected `id_Integer`, `id_String`, `id_Double` -- old buggy values
- **Fix:** Updated to expect `int`, `str`, `float` -- correct Python type strings
- **Files modified:** tests/converters/talend_to_v1/components/transform/test_map.py
- **Committed in:** b9fb638

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes essential for correctness. No scope creep.

## Issues Encountered
- None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- type_mapping.py provides the type contract for all subsequent bridge plans (02-02, 02-03, 02-04)
- bridge.py API surface is preserved -- JavaBridgeManager and all engine components use the same methods
- All 7 type strings are validated at the bridge boundary -- any future invalid types will fail fast with clear error

---
*Phase: 02-java-bridge-reliability*
*Completed: 2026-04-14*
