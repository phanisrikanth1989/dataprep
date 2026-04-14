# Phase 2: Java Bridge Reliability - Research

**Researched:** 2026-04-14 (re-run with corrected converter fix scope)
**Domain:** Python-Java bridge (Py4J + Apache Arrow IPC), data type serialization, bidirectional state sync
**Confidence:** HIGH

## Summary

Phase 2 rewrites the Python-Java bridge layer: `bridge.py` (591 lines), `JavaBridge.java` (1022 lines), `RowWrapper.java` (160 lines), and updates `java_bridge_manager.py` (129 lines). The current bridge has 6 documented issues: data-inference-based Arrow serialization that fails on all-null columns, missing `_sync_from_java()` on 5 of 6 call paths, 47 print/println statements instead of proper logging, Py4J version mismatch (Python 0.10.9.9 vs Java 0.10.9.7), inconsistent type handling on Java side, and no retry logic.

Additionally, two converters (tMap and tXMLMap) have a bug where they output raw Talend `id_*` type strings instead of running them through `convert_type()`. This must be fixed as part of the schema standardization effort (D-05a). The bridge's type mapping should ONLY handle the 7 Python type strings: `str`, `int`, `float`, `bool`, `datetime`, `Decimal`, `object`. No `id_*` fallback handling in the bridge -- the converter is responsible for producing correct types.

**Primary recommendation:** Full rewrite of both Python and Java sides with schema-driven serialization. Fix the tMap and tXMLMap converter bugs first (or in parallel as a separate wave), then build the bridge to accept ONLY the 7 standardized Python type strings. Re-convert affected sample JSONs after the converter fix.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite of both `bridge.py` (Python client) and `JavaBridge.java` + `RowWrapper.java` (Java server). Not patching existing code. Audit for unused code and remove it.
- **D-02:** The API surface (method signatures visible to engine components) should remain similar, but internals are rebuilt from scratch with schema-driven serialization, consistent sync, proper logging, and retry logic.
- **D-03:** `java_bridge_manager.py` disposition is Claude's discretion -- update or rewrite based on what research reveals about needed changes.
- **D-04:** Every bridge method receives an explicit schema dict mapping column names to types. No data inference. No guessing from first non-null value. Schema is the single source of truth for Arrow type mapping.
- **D-05:** Research phase MUST audit what format the talend_to_v1 converters produce for schema in JSON configs. That format becomes THE standard schema representation across the entire application.
- **D-05a:** Fix the tXMLMap converter bug that outputs raw Talend `id_*` type strings instead of running them through `convert_type()`. Every converter must produce Python type strings (`str`, `int`, `float`, `bool`, `datetime`, `Decimal`, `object`). No exceptions, no fallbacks.
- **D-06:** The bridge handles the mapping from the standardized schema format (7 Python type strings only) to Arrow types. No fallback handling for raw Talend `id_*` types -- the converter is responsible for producing correct types. Components pass schema as-is from their config. Single source of truth for type mapping lives in the bridge.
- **D-07:** Full audit and rewrite of JavaBridge.java (42KB) and RowWrapper.java. Remove unused code, fix type handling on the Java side, match the new Python bridge API.
- **D-08:** Upgrade Py4J from 0.10.9.7 to 0.10.9.9 (retry-on-empty-response fix). Both Python package and Java dependency in pom.xml.
- **D-09:** Arrow stays at 15.0.2 on both sides. No Arrow version upgrade.
- **D-10:** Groovy stays at 3.0.21. No Groovy upgrade.
- **D-11:** Fail fast with clear error. If the bridge fails, raise `JavaBridgeError` immediately. No silent fallback.
- **D-12:** Context/globalMap sync must happen at EVERY bridge call site.
- **D-13:** ASCII-only logging throughout. No emojis, unicode symbols, or non-ASCII characters.
- **D-14:** Replace all `print()` with proper `logging.getLogger(__name__)` on Python side. Java side uses `java.util.logging`.
- **D-15:** Java log messages must be clearly identifiable with `[JavaBridge]` prefix.
- **D-16:** Log level sync between Python and Java at bridge startup.
- **D-17:** JavaBridge.java may be decomposed into smaller focused classes.
- **D-18:** Unit tests for Python-side logic with mocked Py4J gateway.
- **D-19:** Integration tests with real JVM, marked `@pytest.mark.java`.
- **D-20:** Round-trip test for 12 Talend data types.
- **D-21:** Phase 2 tests cover bridge infrastructure, not component-specific usage.
- **D-22:** Java 21 available on dev machine; Java 11 is minimum target.

### Claude's Discretion
- java_bridge_manager.py -- update vs rewrite based on needed changes
- Internal method design and data structures for the rewritten bridge
- Retry logic specifics (count, backoff, which failures trigger retry)
- BRDG-06 (compiled script synchronization) -- implementation approach
- BRDG-04 (JAR/library loading) -- robust classpath management approach

### Deferred Ideas (OUT OF SCOPE)
- Arrow version upgrade (15.0.2 -> newer)
- Groovy version upgrade
- byte[], List, Object, Document type support in Arrow serialization
- Database connection bridge support
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BRDG-01 | Fix data type serialization failures in Arrow (date, timestamp, decimal types) | Schema-driven serialization replaces data inference; type mapping module maps 7 Python types to Arrow types |
| BRDG-02 | Implement schema-driven Arrow serialization instead of data inference | New `type_mapping.py` in bridge package; schema dict passed to every bridge method; no `_build_arrow_schema` data scanning |
| BRDG-03 | Fix context/globalMap sync at every bridge call site | `_sync_from_java()` currently called only in `execute_java_row()`; must be added to all 5 other methods |
| BRDG-04 | Strengthen JAR/library loading -- robust classpath management | Current `validateLibraries()` uses string-contains on classpath; needs actual class loading verification |
| BRDG-05 | Upgrade Py4J Python to 0.10.9.9 (retry on empty response) | Python already at 0.10.9.9; pom.xml needs update from 0.10.9.7 to 0.10.9.9; rebuild JAR required |
| BRDG-06 | Fix compiled script synchronization in Java bridge | `compiledScripts` ConcurrentHashMap exists but synchronization on script execution uses `synchronized(script)` which blocks parallel chunk processing |
| D-05a | Fix tMap and tXMLMap converter bugs outputting raw `id_*` types | Both `map.py` and `xml_map.py` read XML attributes directly without `convert_type()`; 2 converted JSONs affected |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| py4j | 0.10.9.9 | Python-Java gateway communication | Already installed on Python side; retry-on-empty-response fix; Java side needs pom.xml update from 0.10.9.7 [VERIFIED: pip3 show py4j] |
| pyarrow | 23.0.1 (Python) / 15.0.2 (Java) | Arrow IPC data serialization | Python side has newer version; Java stays at 15.0.2 per D-09; IPC format is backward compatible [VERIFIED: pip3 show pyarrow, pom.xml] |
| groovy | 3.0.21 | Dynamic script execution on Java side | Stays at current version per D-10 [VERIFIED: pom.xml] |
| pytest | (installed) | Test framework | Phase 1 created test infrastructure in tests/v1/engine/ [VERIFIED: tests/v1/engine/conftest.py exists] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Mock Py4J gateway for unit tests | Python-side unit tests (D-18) |
| java.util.logging | JDK | Java-side logging | Replace System.out.println per D-14/D-15 |

**No new dependencies required.** The rewrite uses existing libraries with version alignment.

## Architecture Patterns

### Recommended Project Structure

```
src/v1/java_bridge/
    __init__.py                     # Re-exports JavaBridge
    bridge.py                       # REWRITE: Python bridge client
    type_mapping.py                 # NEW: Python type -> Arrow type mapping (7 types only)
    java/
        pom.xml                     # UPDATE: Py4J 0.10.9.7 -> 0.10.9.9
        src/main/java/com/citi/gru/etl/
            JavaBridge.java         # REWRITE: Main gateway + Groovy execution
            RowWrapper.java         # REWRITE: Row accessor for Groovy scripts
            ArrowSerializer.java    # NEW (optional): Arrow read/write utilities
            TypeMapper.java         # NEW (optional): Schema type -> Java type mapping

src/v1/engine/
    java_bridge_manager.py          # UPDATE: Lifecycle management, log level sync

src/converters/talend_to_v1/
    components/transform/
        map.py                      # FIX: Add convert_type() calls (3 locations)
        xml_map.py                  # FIX: Add convert_type() calls (4 locations in output)

tests/v1/engine/
    test_bridge_type_mapping.py     # NEW: Unit tests for type mapping
    test_bridge.py                  # NEW: Unit tests for bridge with mocked Py4J
    test_bridge_integration.py      # NEW: Integration tests with real JVM (@pytest.mark.java)
```

### Pattern 1: Schema-Driven Serialization

**What:** Every bridge method receives an explicit schema dict mapping column names to Python type strings. The bridge uses this schema -- not data inference -- to build Arrow schemas.

**When to use:** Every method that converts DataFrames to/from Arrow bytes.

**Example:**
```python
# Source: Analyzed from converter output format [VERIFIED: converted JSON files]
# Schema dict format (standardized across entire application):
schema = {
    "emp_id": "str",
    "salary": "int",
    "hire_date": "datetime",
    "bonus": "Decimal",
    "active": "bool"
}

# Type mapping module (bridge/type_mapping.py):
PYTHON_TYPE_TO_ARROW = {
    "str": pa.string(),
    "int": pa.int64(),
    "float": pa.float64(),
    "bool": pa.bool_(),
    "datetime": pa.timestamp("ns"),
    "Decimal": pa.decimal128(38, 18),  # Default precision; override from schema
    "object": pa.string(),  # Fallback
}

def build_arrow_schema(schema_dict: dict[str, str],
                       precision_map: dict[str, tuple[int, int]] | None = None) -> pa.Schema:
    """Build Arrow schema from standardized Python type dict."""
    fields = []
    for col_name, col_type in schema_dict.items():
        if col_type == "Decimal" and precision_map and col_name in precision_map:
            p, s = precision_map[col_name]
            arrow_type = pa.decimal128(p, s)
        else:
            arrow_type = PYTHON_TYPE_TO_ARROW.get(col_type, pa.string())
        fields.append(pa.field(col_name, arrow_type))
    return pa.schema(fields)
```

### Pattern 2: Automatic Sync After Every Bridge Call

**What:** `_sync_from_java()` is called after every method that communicates with the Java side, not just `execute_java_row()`.

**When to use:** Design the bridge so sync is impossible to forget -- either call it in a `finally` block of every public method, or create a `_call_java()` wrapper.

**Example:**
```python
# Source: Design pattern for rewrite
def _call_java_with_sync(self, java_method, *args):
    """Call a Java method and sync state back afterward."""
    try:
        result = java_method(*args)
        return result
    finally:
        self._sync_from_java()
```

### Pattern 3: Log Level Sync

**What:** Python passes its log level to Java at bridge startup. Java uses `java.util.logging` with a consistent mapping.

**Example:**
```python
# Python side (at bridge start):
import logging
LOG_LEVEL_MAP = {
    logging.DEBUG: "FINE",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "SEVERE",
}
java_level = LOG_LEVEL_MAP.get(logger.getEffectiveLevel(), "INFO")
self.java_bridge.setLogLevel(java_level)
```

### Anti-Patterns to Avoid
- **Data inference for Arrow types:** Never scan DataFrame values to determine types. Always use the schema dict. All-null columns, mixed types, and first-value-wins are all bugs in the current code.
- **Selective sync:** Never sync context/globalMap in only some methods. Sync after EVERY Java call.
- **print() for logging:** 47 print/println statements exist currently (8 in bridge.py, 39 in JavaBridge.java). All must become proper logger calls. [VERIFIED: grep count]
- **Creating new GroovyShell per operation:** The Java side currently creates `new GroovyShell()` in multiple methods. The rewrite should share/reuse shells where safe.
- **Fallback id_* type handling in bridge:** The bridge must NOT handle raw Talend types. If an `id_*` type reaches the bridge, it is a converter bug that must be fixed at the source.

## Converter Bug Analysis (D-05a)

### Bug Description

Two converters parse schema information directly from XML elements without calling `convert_type()`:

**tMap converter (`map.py`)** -- 3 locations: [VERIFIED: grep + source read]
1. Line 99: `"type": col.get("type", "id_String")` in `_parse_lookup()` join keys
2. Line 162: `"type": var_entry.get("type", "id_String")` in `_parse_variables()`
3. Line 189: `col_type = col.get("type", "id_String")` in `_parse_outputs()` columns

**tXMLMap converter (`xml_map.py`)** -- locations in output data: [VERIFIED: grep + source read]
1. Line 49: `"type": child.get("type", "id_String")` in `_parse_nested_children()` (tree metadata)
2. Line 77: `"type": tree_node.get("type", "id_Document")` in `_parse_input_trees()` (tree metadata)
3. Line 103: `"type": tree_node.get("type", "id_String")` in `_parse_output_trees()` (tree metadata)
4. **Line 339:** `"type": column.get("type", "id_String")` in `_parse_output_schema_from_xml()` -- **CRITICAL: this feeds into output_schema and schema.output used by engine**

Neither file imports `convert_type`. The base class `_parse_schema()` in `base.py` line 134 correctly calls `convert_type(col.type)`, but these converters bypass `_parse_schema()` by reading directly from XML elements.

### Fix Approach

1. Import `convert_type` from `..type_mapping` in both files
2. Wrap each `.get("type", ...)` with `convert_type()` for fields that represent data types
3. For tree metadata nodes (xml_map.py lines 49, 77, 103): these store Talend data types too, so convert them for consistency
4. **NOT** to be confused with `node_type` (e.g., "ATTRIBUT", "ELEMENT") which is an XML node classification, not a data type -- those do NOT get converted

### tXMLMap: Which `type` fields need conversion

| Location | Field | Meaning | Needs convert_type? |
|----------|-------|---------|---------------------|
| Line 49 (`_parse_nested_children`) | `child.get("type", "id_String")` | Talend data type of tree node | YES -- for consistency |
| Line 77 (`_parse_input_trees`) | `tree_node.get("type", "id_Document")` | Talend data type of input node | YES -- for consistency |
| Line 103 (`_parse_output_trees`) | `tree_node.get("type", "id_String")` | Talend data type of output node | YES -- for consistency |
| **Line 339** (`_parse_output_schema_from_xml`) | `column.get("type", "id_String")` | **Schema column type -- engine reads this** | **YES -- CRITICAL** |

### tMap: Which `type` fields need conversion

| Location | Field | Meaning | Needs convert_type? |
|----------|-------|---------|---------------------|
| Line 99 (`_parse_lookup`) | `col.get("type", "id_String")` | Join key type | YES |
| Line 162 (`_parse_variables`) | `var_entry.get("type", "id_String")` | Variable type | YES |
| Line 189 (`_parse_outputs`) | `col.get("type", "id_String")` | Output column type | YES -- CRITICAL |

### Affected Converted JSONs

Only 2 of 31 converted JSON files contain raw `id_*` types: [VERIFIED: grep across all 31 files]
1. `tests/talend_xml_samples/converted_jsons/Job_tXMLMap_0.1.json` -- raw `id_String`, `id_Integer` in output_schema, schema.output, input_trees, output_trees, and downstream tLogRow_1 schema.input
2. `tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json` -- raw `id_String`, `id_Integer` in outputs columns, join_keys, variables

These must be re-converted after the converter fix. The converter source XML files are in `tests/talend_xml_samples/`.

### Schema Format Standard (D-05)

The standardized schema format across the entire application (verified from correctly-converted JSON files):

```json
{
    "schema": {
        "input": [
            {"name": "emp_id", "type": "str", "nullable": false, "key": false},
            {"name": "salary", "type": "int", "nullable": true, "key": false, "length": 10, "precision": 0},
            {"name": "hire_date", "type": "datetime", "nullable": true, "key": false, "date_pattern": "%Y-%m-%d"},
            {"name": "bonus", "type": "Decimal", "nullable": true, "key": false, "precision": 2}
        ],
        "output": [...]
    }
}
```

**The 7 Python type strings (exhaustive):** [VERIFIED: converter type_mapping.py]
| Python Type | Talend Sources | Arrow Type | Java Type |
|-------------|---------------|------------|-----------|
| `str` | id_String, id_Character | `pa.string()` | `String.class` |
| `int` | id_Integer, id_Long, id_Short, id_Byte | `pa.int64()` | `Long.class` |
| `float` | id_Double, id_Float | `pa.float64()` | `Double.class` |
| `bool` | id_Boolean | `pa.bool_()` | `Boolean.class` |
| `datetime` | id_Date | `pa.timestamp("ns")` | `Date.class` |
| `Decimal` | id_BigDecimal | `pa.decimal128(p, s)` | `BigDecimal.class` |
| `object` | id_Object | `pa.string()` | `String.class` |

## Current Bridge API Surface (Must Preserve)

The rewritten bridge must support all these operations: [VERIFIED: bridge.py source]

| Method | Purpose | Callers | Sync Issue |
|--------|---------|---------|------------|
| `execute_java_row(df, code, schema)` | tJavaRow per-row execution | JavaRowComponent | Has sync (ONLY method that does) |
| `execute_one_time_expression(expr)` | Single Java expression | tMap (variable eval) | **Missing sync** |
| `execute_batch_one_time_expressions(exprs)` | Batch expressions | BaseComponent `{{java}}` resolution | **Missing sync** |
| `execute_tmap_preprocessing(df, exprs, ...)` | tMap filter/join key eval | tMap engine component | **Missing sync** |
| `execute_tmap_compiled(script, df, ...)` | tMap compiled execution | tMap engine component | **Missing sync** |
| `compile_tmap_script(id, script, ...)` | Compile and cache tMap script | tMap engine component | N/A (no Java state change) |
| `execute_compiled_tmap_chunked(id, df, ...)` | Execute cached script on chunks | tMap engine component | **Missing sync** |
| `load_routine(class_name)` | Load custom Java routine | JavaBridgeManager | Missing sync |
| `validate_libraries(libs)` | Check JAR availability | JavaBridgeManager | N/A (read-only) |
| `set_context(key, value)` | Set context variable | BaseComponent, tMap | N/A (Python-side only) |
| `set_global_map(key, value)` | Set globalMap variable | BaseComponent, tMap | N/A (Python-side only) |
| `start(port)` | Start JVM and connect | JavaBridgeManager | N/A |
| `stop()` | Stop JVM | JavaBridgeManager | N/A |

### Dead Code on Java Side

| Method | Status | Evidence |
|--------|--------|----------|
| `executeBatchOneTimeExpressions` (without globalMap param) | DEAD CODE | Python side only calls `executeBatchOneTimeExpressionsWithGlobalMap`; this older version lacks globalMap param [VERIFIED: grep shows Python calls WithGlobalMap variant exclusively] |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arrow IPC serialization | Custom byte packing | `pa.ipc.new_stream()` / `pa.ipc.open_stream()` | Arrow IPC is a stable, versioned protocol |
| Type mapping | Inline switch/if chains | Centralized `type_mapping.py` dict | Single source of truth, testable, reusable |
| Groovy compilation | Per-call `new GroovyShell()` | Compile-once cache pattern (already exists, preserve) | Compilation is expensive; cache is correct pattern |
| Port allocation | Hardcoded ports | `socket.bind(('', 0))` | Already correct pattern in java_bridge_manager.py |

## Common Pitfalls

### Pitfall 1: Arrow Version Mismatch
**What goes wrong:** Python PyArrow 23.0.1 writes IPC streams that Java Arrow 15.0.2 cannot read.
**Why it happens:** Newer Arrow versions may use IPC features not available in older versions.
**How to avoid:** Arrow IPC format is backward compatible per the spec. As long as we don't use data types introduced after Arrow 15 (all 7 types we need -- string, int64, float64, bool, timestamp, decimal128 -- are available in Arrow 15), this works. [CITED: https://arrow.apache.org/docs/format/Versioning.html]
**Warning signs:** Java-side `ArrowStreamReader` throws `UnsupportedOperationException` or `InvalidFlatbuffer`.

### Pitfall 2: Decimal Precision/Scale
**What goes wrong:** `pa.decimal128(38, 18)` default precision may not match actual data, causing overflow or truncation.
**Why it happens:** Converter schema includes `precision` field but bridge currently ignores it, using data-inferred precision instead.
**How to avoid:** Extract precision/scale from the schema dict's `precision` and `length` fields when `type` is `Decimal`. Fall back to (38, 18) only when schema doesn't specify.
**Warning signs:** `ArrowInvalid: Decimal value does not fit in precision` errors.

### Pitfall 3: Synchronized Script Execution
**What goes wrong:** `synchronized(compiledScript)` in `executeCompiledTMap` serializes what should be parallel execution.
**Why it happens:** Groovy `Script` objects are not thread-safe; binding is mutable shared state.
**How to avoid:** Either (a) create a new `Script` instance per thread by re-parsing (fast if pre-compiled class is cached), or (b) use ThreadLocal bindings, or (c) accept serialized execution for correctness (current approach works, just slower).
**Warning signs:** Parallel processing shows no speedup; CPU utilization stays at 1 core.

### Pitfall 4: Context/GlobalMap Sync Direction
**What goes wrong:** Python-side state diverges from Java-side state after a bridge call.
**Why it happens:** Java expressions can modify `context` and `globalMap` (e.g., `globalMap.put("key", value)`). If Python doesn't sync back, subsequent Python-side lookups get stale values.
**How to avoid:** Always call `_sync_from_java()` after every Java call. The rewrite's wrapper pattern makes this automatic.
**Warning signs:** `globalMap.get("tMap_1_NB_LINE")` returns None or stale value after tMap execution.

### Pitfall 5: JVM Startup Race Condition
**What goes wrong:** Python tries to connect before Java GatewayServer is ready.
**Why it happens:** `subprocess.Popen` is non-blocking; JVM startup takes 1-3 seconds.
**How to avoid:** Current code uses `time.sleep(2)` then retry loop -- this works but is fragile. Keep the retry approach but make it more robust (exponential backoff, clearer error on timeout).
**Warning signs:** `ConnectionRefusedError` on first attempt; unreliable startup on slower machines.

### Pitfall 6: Maven Not Installed
**What goes wrong:** Cannot rebuild the Java bridge JAR after pom.xml changes.
**Why it happens:** Maven is not installed on the dev machine. [VERIFIED: `command -v mvn` returns nothing]
**How to avoid:** Install Maven via `brew install maven` as a prerequisite step. The Java bridge JAR must be rebuilt after pom.xml changes (Py4J version update).
**Warning signs:** No `target/` directory; `java_bridge_manager.py` fails to find JAR.

## Code Examples

### Bridge Type Mapping Module (New)

```python
# Source: Design based on converter type_mapping.py + bridge requirements
# File: src/v1/java_bridge/type_mapping.py

"""Type mapping from Python type strings to Arrow and Java types.

This is the BRIDGE-SIDE type mapping. The CONVERTER-SIDE mapping lives in
src/converters/talend_to_v1/type_mapping.py (Talend id_* -> Python types).

Only 7 Python type strings are accepted. Any other type string is a bug
in the converter and must be fixed there, not worked around here.
"""

import pyarrow as pa

# The 7 standardized Python type strings -> Arrow types
PYTHON_TO_ARROW: dict[str, pa.DataType] = {
    "str": pa.string(),
    "int": pa.int64(),
    "float": pa.float64(),
    "bool": pa.bool_(),
    "datetime": pa.timestamp("ns"),
    "Decimal": pa.decimal128(38, 18),  # Default; override with schema precision
    "object": pa.string(),
}

# The 7 standardized Python type strings -> Java type names
# (passed to Java side for Arrow vector creation)
PYTHON_TO_JAVA: dict[str, str] = {
    "str": "String",
    "int": "Long",
    "float": "Double",
    "bool": "Boolean",
    "datetime": "Date",
    "Decimal": "BigDecimal",
    "object": "String",
}

VALID_TYPES = frozenset(PYTHON_TO_ARROW.keys())


def validate_schema_types(schema: dict[str, str]) -> None:
    """Raise ValueError if any schema type is not in the 7 valid types."""
    invalid = {col: t for col, t in schema.items() if t not in VALID_TYPES}
    if invalid:
        raise ValueError(
            f"Invalid type(s) in schema (raw Talend types not allowed in bridge): "
            f"{invalid}. Valid types: {sorted(VALID_TYPES)}"
        )
```

### Converter Fix (tXMLMap)

```python
# Source: xml_map.py line 339 -- the critical fix
# Before (bug):
"type": column.get("type", "id_String"),

# After (fix):
from ..type_mapping import convert_type
# ...
"type": convert_type(column.get("type", "id_String")),
```

### Converter Fix (tMap)

```python
# Source: map.py lines 99, 162, 189 -- all need the same fix
from ..type_mapping import convert_type
# ...
# Line 99: join key type
"type": convert_type(col.get("type", "id_String")),
# Line 162: variable type
"type": convert_type(var_entry.get("type", "id_String")),
# Line 189: output column type
col_type = convert_type(col.get("type", "id_String"))
```

### Java-Side Type Mapping (Rewrite)

```java
// Source: Design for rewritten JavaBridge.java
// Maps the 7 Python type strings (what Python sends) to Java types
// Replaces current inferJavaTypeFromSchema which has mixed id_*/Java type names
private static Class<?> mapSchemaTypeToJava(String schemaType) {
    if (schemaType == null) return String.class;
    switch (schemaType) {
        case "str":      return String.class;
        case "int":      return Long.class;
        case "float":    return Double.class;
        case "bool":     return Boolean.class;
        case "datetime": return Date.class;
        case "Decimal":  return BigDecimal.class;
        case "object":   return String.class;
        default:
            logger.warning("Unknown schema type: " + schemaType + " -- defaulting to String");
            return String.class;
    }
}
```

## Java Bridge Manager Analysis (D-03)

The current `java_bridge_manager.py` (129 lines) is relatively clean: [VERIFIED: source read]

**What works:**
- Dynamic port allocation via `socket.bind(('', 0))` -- correct pattern
- Context manager support (`__enter__`/`__exit__`) -- good for cleanup
- Library validation and routine loading at startup -- correct lifecycle
- Graceful degradation when bridge fails to start -- appropriate behavior

**What needs updating:**
- Line 76: `logger.warning("Java execution will be disabled. Components will fall back to Python execution.")` -- this contradicts D-11 (fail fast, no silent fallback). Recommendation: Make it configurable -- `die_on_error=True` raises, `die_on_error=False` degrades gracefully. The job config's `java_config.enabled` already signals intent.
- Missing: Log level sync to Java side (D-16) -- needs `self.bridge.set_log_level(...)` call after start
- Missing: Ready signal / improved startup robustness (currently in bridge.py `time.sleep(2)` + retry)

**Recommendation:** UPDATE, not rewrite. The manager is ~60% correct. Add log level sync, update error handling policy, and integrate with the rewritten bridge API.

## JavaBridge.java Decomposition Analysis (D-17)

Current: 1022 lines in a single file. Method audit: [VERIFIED: source read]

| Method Group | Lines (est.) | Purpose | Decompose? |
|-------------|-------------|---------|------------|
| Constructor + main + state | ~50 | Gateway setup, startup, context/globalMap | Keep in JavaBridge.java |
| executeJavaRow | ~100 | tJavaRow processing | Keep (core operation) |
| executeOneTimeExpression | ~20 | Single expression eval | Keep (small) |
| executeBatchOneTimeExpressions | ~45 | Batch expression eval (WITHOUT globalMap) | **DELETE** (dead code) |
| executeBatchOneTimeExpressionsWithGlobalMap | ~50 | Batch expression eval (with globalMap) | Rename to executeBatchOneTimeExpressions |
| executeTMapPreprocessing | ~115 | tMap filter/join eval | Keep |
| executeTMapCompiled | ~130 | tMap compiled execution | Keep |
| compileTMapScript | ~50 | Script compilation + caching | Keep |
| executeCompiledTMap | ~120 | Cached script execution | Keep |
| loadRoutine / validateLibraries | ~35 | Classpath management | Keep |
| Arrow helpers | ~130 | createOutputRootFromData, createVectorForType, setVectorValue, inferJavaTypeFromSchema, inferDecimalPrecisionScale | **EXTRACT to ArrowSerializer.java** |
| getContext / getGlobalMap | ~10 | State accessors | Keep |

**Recommendation:** Extract Arrow serialization helpers into `ArrowSerializer.java` (~130 lines). This is the clearest boundary -- Arrow read/write concerns are distinct from Groovy execution concerns. The tMap methods share the same Groovy execution pattern as the core methods; extracting them would just move code without reducing complexity. Delete the dead `executeBatchOneTimeExpressions` (without globalMap).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Data-inferred Arrow schema (`_build_arrow_schema`) | Schema-driven Arrow schema (type_mapping.py) | This phase | Fixes all-null columns, mixed types, first-value-wins bugs |
| Selective `_sync_from_java` (1 of 6 methods) | Automatic sync after every call | This phase | Fixes stale context/globalMap after tMap, batch expressions |
| print() debugging (47 statements) | Structured logging (Python logging + JUL) | This phase | Production-ready log output |
| Py4J 0.10.9.7 (Java side) | Py4J 0.10.9.9 (both sides) | This phase | Retry on empty response fix |
| Raw Talend id_* types in tMap/tXMLMap converters | All converters produce Python type strings | This phase (D-05a) | One type format everywhere |
| Mixed type handling on Java side (inferJavaTypeFromSchema) | Clean 7-type mapping (mapSchemaTypeToJava) | This phase | Consistent, predictable type handling |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Arrow IPC format from PyArrow 23.0.1 is readable by Java Arrow 15.0.2 | Common Pitfalls | HIGH -- bridge would fail to exchange data; mitigated by Arrow's backward compat guarantee [CITED: Arrow versioning docs] |
| A2 | tXMLMap tree metadata `type` fields (lines 49, 77, 103) should also be converted for consistency | Converter Bug Analysis | LOW -- these are stored but not directly consumed by engine; converting them improves consistency but doesn't fix a runtime bug |

## Open Questions

1. **Maven installation for JAR rebuild**
   - What we know: Maven is not installed (`command -v mvn` returns nothing). No Maven Wrapper in the project. No `target/` directory exists.
   - What's unclear: Whether to install Maven globally or add Maven Wrapper to the project.
   - Recommendation: Install Maven via `brew install maven` as a prerequisite step in Wave 0. The Java bridge must be buildable.

2. **BaseComponent._TYPE_MAPPING cleanup**
   - What we know: Phase 1's BaseComponent rewrite kept both `id_*` and Python type strings in `_TYPE_MAPPING` (lines 78-101). Once all converters are fixed, the `id_*` entries become dead code.
   - What's unclear: Should Phase 2 remove the `id_*` entries from `_TYPE_MAPPING`, or leave that for later?
   - Recommendation: Remove them in Phase 2 alongside the converter fix. Keeping dead `id_*` entries creates confusion about which format is canonical. The converter fix (D-05a) ensures no JSON config will contain `id_*` types after re-conversion.

3. **JVM startup robustness**
   - What we know: Current code uses `time.sleep(2)` + retry loop in bridge.py.
   - What's unclear: Whether to implement a ready signal (Java writes to stdout, Python reads it) or keep the retry approach.
   - Recommendation: Keep the retry approach but improve it (exponential backoff, clear error on timeout, configurable max wait). A ready signal is cleaner but adds subprocess I/O complexity.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Java (JDK) | Bridge JVM runtime | Yes | OpenJDK 21.0.10 | -- |
| Maven | JAR rebuild (pom.xml changes) | **NO** | -- | `brew install maven` required |
| Python | Bridge client | Yes | 3.10+ | -- |
| py4j (Python) | Bridge communication | Yes | 0.10.9.9 | -- |
| pyarrow (Python) | Arrow IPC | Yes | 23.0.1 | -- |
| pytest | Tests | Yes | (installed) | -- |

**Missing dependencies with no fallback:**
- **Maven**: Required to rebuild the Java bridge JAR after pom.xml changes (Py4J version upgrade). Must be installed before Java-side work begins.

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed, Phase 1 infrastructure in place) |
| Config file | None -- Phase 1 uses minimal conftest.py at `tests/v1/engine/conftest.py` |
| Quick run command | `python -m pytest tests/v1/engine/test_bridge_type_mapping.py -x -q` |
| Full suite command | `python -m pytest tests/v1/engine/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRDG-01 | All 7 Python types serialize to Arrow and back | unit | `pytest tests/v1/engine/test_bridge_type_mapping.py -x` | Wave 0 |
| BRDG-02 | Schema dict drives Arrow schema (no data inference) | unit | `pytest tests/v1/engine/test_bridge.py::TestSchemaMapping -x` | Wave 0 |
| BRDG-03 | Context/globalMap sync after every bridge call | unit (mock) + integration | `pytest tests/v1/engine/test_bridge.py::TestSync -x` | Wave 0 |
| BRDG-04 | JAR/library loading validates classpath | integration (@java) | `pytest tests/v1/engine/test_bridge_integration.py::TestLibraryLoading -x` | Wave 0 |
| BRDG-05 | Py4J 0.10.9.9 on both sides | integration (@java) | `pytest tests/v1/engine/test_bridge_integration.py::TestPy4JVersion -x` | Wave 0 |
| BRDG-06 | Compiled script cache works across chunks | integration (@java) | `pytest tests/v1/engine/test_bridge_integration.py::TestCompiledScripts -x` | Wave 0 |
| D-05a | Converter fix: no id_* types in output | unit | `pytest tests/converters/test_map_types.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/v1/engine/test_bridge_type_mapping.py tests/v1/engine/test_bridge.py -x -q`
- **Per wave merge:** `python -m pytest tests/v1/engine/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/v1/engine/test_bridge_type_mapping.py` -- covers BRDG-01 (type mapping unit tests)
- [ ] `tests/v1/engine/test_bridge.py` -- covers BRDG-02, BRDG-03 (bridge unit tests with mocked Py4J)
- [ ] `tests/v1/engine/test_bridge_integration.py` -- covers BRDG-04, BRDG-05, BRDG-06 (JVM integration, `@pytest.mark.java`)
- [ ] `tests/converters/test_map_types.py` -- covers D-05a (converter type fix verification)
- [ ] Maven install: `brew install maven` -- required before Java-side changes can be tested

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A (local subprocess bridge) |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | Schema type validation (reject unknown types); expression input from trusted job configs only |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for Python-Java Bridge

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Groovy code injection via job config | Tampering | Job configs are trusted input (generated by converter, not user-editable in production) |
| JVM resource exhaustion | Denial of Service | RootAllocator with memory limit; process isolation per job |
| Classpath manipulation | Elevation of Privilege | Validate JARs exist before adding to classpath; no dynamic classpath modification |

## Sources

### Primary (HIGH confidence)
- `src/v1/java_bridge/bridge.py` -- full source read, 591 lines [VERIFIED]
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` -- full source read, 1022 lines [VERIFIED]
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` -- full source read, 160 lines [VERIFIED]
- `src/v1/engine/java_bridge_manager.py` -- full source read, 129 lines [VERIFIED]
- `src/converters/talend_to_v1/type_mapping.py` -- full source read, type mapping reference [VERIFIED]
- `src/converters/talend_to_v1/components/base.py` -- _parse_schema() with convert_type() call confirmed [VERIFIED]
- `src/converters/talend_to_v1/components/transform/map.py` -- 3 bug locations verified via grep [VERIFIED]
- `src/converters/talend_to_v1/components/transform/xml_map.py` -- 4 bug locations verified via grep [VERIFIED]
- `tests/talend_xml_samples/converted_jsons/` -- 31 files scanned; 2 contain raw id_* types [VERIFIED]
- `src/v1/java_bridge/java/pom.xml` -- Py4J 0.10.9.7, Arrow 15.0.2, Groovy 3.0.21 [VERIFIED]
- `src/v1/engine/base_component.py` -- _TYPE_MAPPING with both id_* and Python type formats [VERIFIED]
- Runtime checks: py4j==0.10.9.9, pyarrow==23.0.1, Java 21.0.10, Maven NOT installed [VERIFIED]

### Secondary (MEDIUM confidence)
- [Py4J 0.10.9.9 changelog](https://www.py4j.org/changelog.html) -- "Retry Py4J on empty response" fix confirmed [CITED]
- [Py4J 0.10.9.9 on Maven Central](https://central.sonatype.com/artifact/net.sf.py4j/py4j) -- Java JAR availability confirmed [CITED]
- [Arrow Format Versioning](https://arrow.apache.org/docs/format/Versioning.html) -- IPC backward compatibility confirmed [CITED]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all versions verified via pip/pom.xml/runtime checks
- Architecture: HIGH -- full source read of all target files; clear bug analysis
- Pitfalls: HIGH -- based on verified code analysis, not speculation
- Converter bug: HIGH -- exact line numbers verified with grep; affected JSONs confirmed

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable domain -- Py4J, Arrow, Groovy are mature libraries)
