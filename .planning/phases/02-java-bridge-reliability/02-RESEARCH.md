# Phase 2: Java Bridge Reliability - Research

**Researched:** 2026-04-14
**Domain:** Python-Java bridge (Py4J + Apache Arrow IPC), Groovy script execution, data type serialization
**Confidence:** HIGH

## Summary

The Java bridge layer consists of 4 files (1,900 total lines) connecting Python ETL engine components to a JVM process for Java/Groovy expression evaluation. The architecture (Py4J for RPC, Arrow IPC for data transfer) is sound, but the implementation has six documented reliability gaps: data-inference-based serialization instead of schema-driven, missing context/globalMap sync on most call sites, no retry logic for Py4J empty responses, fragile JAR loading, print-everywhere logging, and thread safety issues with compiled script execution.

The highest-value finding from this research is the **schema format standardization problem**. The converter outputs type strings like `"int"`, `"float"`, `"str"`, `"datetime"`, `"Decimal"` -- but these lose Talend type fidelity (id_Integer, id_Long, id_Byte, id_Short all become `"int"`). The rewritten bridge must build a comprehensive type mapping table that handles all observed schema type strings (including raw `id_*` strings from tXMLMap converter bugs) and maps them to correct Arrow types. The schema dict from component config becomes the single source of truth -- no data inference anywhere.

The rewrite is well-scoped: Python side replaces 590 lines of bridge.py, Java side replaces 1,022 lines of JavaBridge.java and 160 lines of RowWrapper.java. The java_bridge_manager.py (128 lines) needs targeted updates rather than a full rewrite -- its lifecycle management and port allocation are sound.

**Primary recommendation:** Rewrite both sides with schema-driven serialization as the central design principle. Every bridge method that transfers data receives explicit schema. Every bridge method that calls Java syncs context/globalMap afterward. Build comprehensive type mapping table on Python side (schema string -> Arrow type) and Java side (schema string -> Java class + Arrow vector type).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite of both `bridge.py` (Python client) and `JavaBridge.java` + `RowWrapper.java` (Java server). Not patching existing code. Audit for unused code and remove it.
- **D-02:** The API surface (method signatures visible to engine components) should remain similar, but internals are rebuilt from scratch with schema-driven serialization, consistent sync, proper logging, and retry logic.
- **D-03:** `java_bridge_manager.py` disposition is Claude's discretion -- update or rewrite based on what research reveals about needed changes.
- **D-04:** Every bridge method receives an explicit schema dict mapping column names to types. No data inference. No guessing from first non-null value. Schema is the single source of truth for Arrow type mapping.
- **D-05:** Research phase MUST audit what format converters produce for schema in JSON configs. That format becomes THE standard schema representation across the entire application. Bridge, engine components, and all downstream code use the same schema format. This has been a pain point -- one format, everywhere.
- **D-06:** The bridge handles the mapping from the standardized schema format to Arrow types. Components pass schema as-is from their config. Single source of truth for type mapping lives in the bridge.
- **D-07:** Full audit and rewrite of JavaBridge.java (42KB) and RowWrapper.java. Remove unused code, fix type handling on the Java side, match the new Python bridge API.
- **D-08:** Upgrade Py4J from 0.10.9.7 to 0.10.9.9 (retry-on-empty-response fix). Both Python package and Java dependency in pom.xml.
- **D-09:** Arrow stays at 15.0.2 on both sides. No Arrow version upgrade -- current version works, lower risk.
- **D-10:** Groovy stays at 3.0.21. No Groovy upgrade.
- **D-11:** Fail fast with clear error. If the bridge fails (JVM crash, serialization error, timeout), raise a `JavaBridgeError` immediately. No silent fallback to Python-side expression handling. Components that need Java MUST have the bridge working.
- **D-12:** Context/globalMap sync must happen at EVERY bridge call site -- not just `execute_java_row()`. This is fixed by design in the rewrite (every method that calls Java syncs afterward).
- **D-13:** ASCII-only logging throughout. No emojis, unicode symbols, or non-ASCII characters in any log messages. Production target is RHEL Linux servers. Use `[OK]`, `[ERROR]`, `[WARN]` text markers.
- **D-14:** Replace all `print()` statements with proper `logging.getLogger(__name__)` calls on Python side. Java side uses `java.util.logging` (no SLF4J/Logback -- keep dependencies minimal).
- **D-15:** Java log messages must be clearly identifiable as coming from the Java side. Use a logger name or prefix (e.g., `[JavaBridge]`) so interleaved Python/Java logs have obvious boundaries.
- **D-16:** Log level sync between Python and Java. Python passes its log level to Java at bridge startup. Mapping: Python `DEBUG` -> JUL `FINE`, `INFO` -> `INFO`, `WARNING` -> `WARNING`, `ERROR` -> `SEVERE`. One knob on Python side controls both. No separate Java log config needed.
- **D-17:** JavaBridge.java (42KB single file) may be decomposed into smaller focused classes for maintainability. Research determines the right boundaries.
- **D-18:** Unit tests for Python-side logic (schema mapping, type conversion, retry logic) with mocked Py4J gateway. No JVM required for these.
- **D-19:** Integration tests that start a real JVM and round-trip data through the bridge end-to-end. Marked with `@pytest.mark.java` so they can be skipped on machines without JVM.
- **D-20:** Round-trip test coverage for 12 Talend data types: String, Integer, Long, Float, Double, BigDecimal, Date, Timestamp, Boolean, Byte, Short, Character.
- **D-21:** Subsequent component phases will add their own bridge integration tests. Phase 2 tests cover the bridge infrastructure itself.
- **D-22:** Java 21 is available on dev machine (OpenJDK 21.0.10 via Homebrew). Java 11 is the minimum target for production.

### Claude's Discretion
- java_bridge_manager.py -- update vs rewrite based on needed changes
- Internal method design and data structures for the rewritten bridge
- Retry logic specifics (count, backoff, which failures trigger retry)
- BRDG-06 (compiled script synchronization) -- implementation approach determined during research
- BRDG-04 (JAR/library loading) -- robust classpath management approach determined during research

### Deferred Ideas (OUT OF SCOPE)
- Arrow version upgrade (15.0.2 -> newer) -- keep stable for now
- Groovy version upgrade -- no pressing need
- byte[], List, Object, Document type support in Arrow serialization
- Database connection bridge support
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BRDG-01 | Identify and fix data type serialization failures in Arrow (date, timestamp, decimal types) | Schema audit complete. Found 7 distinct type strings in converter output (`str`, `int`, `float`, `bool`, `datetime`, `Decimal`, `object`) plus raw `id_*` types from tXMLMap. Complete type mapping table documented. Current bugs: date objects -> string, all-null columns -> string, Decimal precision inference from first value. |
| BRDG-02 | Implement schema-driven Arrow serialization instead of data inference from first non-null value | Schema format fully audited. Column dict has keys: `name`, `type`, `nullable`, `key`, `length`, `precision`, `date_pattern`. Type string is the driver. Complete Python->Arrow and Java type mapping tables documented. |
| BRDG-03 | Fix context/globalMap sync at every bridge call site | Audit complete. `_sync_from_java()` called in exactly 1 of 7 bridge methods (`execute_java_row`). Missing from: `execute_one_time_expression`, `execute_batch_one_time_expressions`, `execute_tmap_preprocessing`, `execute_tmap_compiled`, `compile_tmap_script`, `execute_compiled_tmap_chunked`. Components manually call `_sync_from_java()` as workaround (tMap, tJava). |
| BRDG-04 | Strengthen JAR/library loading -- robust classpath management | Current validation is string-contains check on `java.class.path`. No dynamic classpath addition. pom.xml lacks assembly/shade plugin for uber-jar. Maven not installed on dev machine. |
| BRDG-05 | Upgrade Py4J Python to 0.10.9.9 (retry on empty response) | Python-side already at 0.10.9.9 (verified). Java pom.xml still at 0.10.9.7. Need to update pom.xml only. Py4J 0.10.9.9 confirmed on Maven Central. |
| BRDG-06 | Fix compiled script synchronization in Java bridge | `synchronized(compiledScript)` in parallel forEach serializes execution, negating parallelism. Compiled scripts share binding state. Fix: per-thread script cloning or sequential execution with explicit design. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Py4J | 0.10.9.9 (Python + Java) | Python-Java gateway RPC | Already in use, retry-on-empty-response fix in 0.10.9.9 [VERIFIED: pip show py4j, Py4J changelog] |
| Apache Arrow (pyarrow) | 23.0.1 (Python), 15.0.2 (Java) | Data serialization via IPC | Arrow IPC format is stable across versions [CITED: arrow.apache.org/docs/format/Versioning.html] |
| Groovy | 3.0.21 | Dynamic script compilation/execution | Already in use, locked decision D-10 |
| java.util.logging (JUL) | JDK built-in | Java-side logging | Locked decision D-14, no extra dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Test framework | Unit and integration tests [VERIFIED: pytest --version] |
| pytest markers | N/A | `@pytest.mark.java`, `@pytest.mark.unit` | Already configured in pyproject.toml [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Py4J | gRPC + protobuf | Much higher complexity, would require full protocol redesign -- not justified |
| Arrow IPC | JSON serialization | Orders of magnitude slower for large DataFrames, loses type fidelity |
| Groovy | Janino | Less expressive, no dynamic property access (propertyMissing) |

**Installation:**
```bash
# Python-side already installed. For Java:
# Update pom.xml py4j.version from 0.10.9.7 to 0.10.9.9
# Then rebuild JAR (requires Maven)
```

**Version verification:**
- Py4J Python: 0.10.9.9 [VERIFIED: `pip show py4j` on 2026-04-14]
- Py4J Java: 0.10.9.9 available on Maven Central [VERIFIED: central.sonatype.com]
- PyArrow: 23.0.1 [VERIFIED: `python3 -c "import pyarrow; print(pyarrow.__version__)"` on 2026-04-14]
- Arrow Java: 15.0.2 (locked, pom.xml) [VERIFIED: pom.xml]
- Groovy: 3.0.21 (locked, pom.xml) [VERIFIED: pom.xml]
- Pytest: 9.0.2 [VERIFIED: runtime]

## Architecture Patterns

### Recommended Project Structure (Post-Rewrite)
```
src/v1/java_bridge/
  __init__.py                    # Re-exports JavaBridge
  bridge.py                      # REWRITE: Python bridge client
  type_mapping.py                # NEW: Schema type -> Arrow type mapping (single source of truth)
  java/
    pom.xml                      # UPDATE: Py4J 0.10.9.7 -> 0.10.9.9, add assembly plugin
    src/main/java/com/citi/gru/etl/
      JavaBridge.java            # REWRITE: Gateway entry point + method dispatch
      ArrowSerializer.java       # NEW: Arrow IPC read/write + type mapping (extracted from JavaBridge)
      ExpressionExecutor.java    # NEW: Groovy compile/execute logic (extracted from JavaBridge)
      RowWrapper.java            # REWRITE: Row accessor for Arrow vectors
src/v1/engine/
  java_bridge_manager.py         # UPDATE: Add log level passing, improve error handling
tests/v1/engine/
  test_bridge_type_mapping.py    # NEW: Unit tests for schema -> Arrow type conversion
  test_bridge_serialization.py   # NEW: Unit tests for Arrow serialization/deserialization
  test_bridge_integration.py     # NEW: @pytest.mark.java end-to-end round-trip tests
```

### Pattern 1: Schema-Driven Type Mapping (Python Side)
**What:** Central mapping table from schema type strings to Arrow types. The bridge never inspects data values to determine types.
**When to use:** Every bridge method that converts DataFrames to/from Arrow.
**Example:**
```python
# Source: Converter output analysis (7 type strings + raw id_* fallbacks)
# Located in src/v1/java_bridge/type_mapping.py

import pyarrow as pa

# Schema type string -> Arrow type
# Handles both converter output types and raw Talend id_* types
SCHEMA_TO_ARROW: dict[str, pa.DataType] = {
    # Converter output types (from type_mapping.py)
    "str": pa.string(),
    "string": pa.string(),
    "int": pa.int64(),
    "long": pa.int64(),
    "float": pa.float64(),
    "double": pa.float64(),
    "bool": pa.bool_(),
    "datetime": pa.timestamp("ms"),
    "date": pa.timestamp("ms"),
    "object": pa.string(),
    # Decimal handled separately -- needs precision/scale from schema column
    # Raw Talend types (from tXMLMap converter bug, must handle gracefully)
    "id_String": pa.string(),
    "id_Integer": pa.int32(),
    "id_Long": pa.int64(),
    "id_Short": pa.int16(),
    "id_Byte": pa.int8(),
    "id_Float": pa.float32(),
    "id_Double": pa.float64(),
    "id_Boolean": pa.bool_(),
    "id_Date": pa.timestamp("ms"),
    "id_Character": pa.string(),
    "id_Object": pa.string(),
}

def schema_to_arrow_type(col: dict) -> pa.DataType:
    """Convert a schema column dict to an Arrow type.

    Args:
        col: Schema column dict with keys: name, type, nullable,
             key, length, precision, date_pattern.
    Returns:
        Arrow data type.
    """
    type_str = col.get("type", "str")

    # Decimal needs precision/scale from schema
    if type_str.lower() in ("decimal", "id_bigdecimal"):
        precision = col.get("precision", 38)
        if precision <= 0:
            precision = 38
        # Scale defaults to half precision or 18, whichever is smaller
        scale = min(precision // 2, 18)
        return pa.decimal128(precision, scale)

    arrow_type = SCHEMA_TO_ARROW.get(type_str)
    if arrow_type is None:
        # Case-insensitive fallback
        arrow_type = SCHEMA_TO_ARROW.get(type_str.lower(), pa.string())
    return arrow_type


def build_arrow_schema(columns: list[dict]) -> pa.Schema:
    """Build Arrow schema from a list of schema column dicts."""
    fields = []
    for col in columns:
        arrow_type = schema_to_arrow_type(col)
        nullable = col.get("nullable", True)
        fields.append(pa.field(col["name"], arrow_type, nullable=nullable))
    return pa.schema(fields)
```

### Pattern 2: Sync-After-Every-Call (Python Side)
**What:** Every bridge method that calls Java MUST sync context/globalMap back afterward.
**When to use:** Built into every public method on the bridge.
**Example:**
```python
# Every public method follows this pattern:
def execute_some_operation(self, ..., schema: list[dict]) -> ...:
    """Execute operation X on the Java bridge."""
    # 1. Sync Python -> Java BEFORE call
    self._sync_to_java()

    # 2. Make the Py4J call
    try:
        result = self._gateway_call(...)
    except Py4JNetworkError as e:
        raise JavaBridgeError(f"Bridge communication failed: {e}") from e

    # 3. Sync Java -> Python AFTER call
    self._sync_from_java()

    # 4. Return result
    return result
```

### Pattern 3: Java Class Decomposition
**What:** Split 1,022-line JavaBridge.java into focused classes.
**When to use:** The rewrite.
**Recommended boundaries:**

| Class | Responsibility | Lines (est.) |
|-------|---------------|-------------|
| `JavaBridge.java` | Gateway entry point, main(), Py4J server, method dispatch | ~100 |
| `ArrowSerializer.java` | Read/write Arrow IPC, type mapping, vector creation | ~300 |
| `ExpressionExecutor.java` | Groovy compile/execute, routine loading, binding setup | ~300 |
| `RowWrapper.java` | Row accessor for Arrow vectors (simplified, no change to API) | ~120 |

### Pattern 4: Java-Side Type Mapping
**What:** Mirror the Python type mapping on the Java side for creating output Arrow vectors.
**Example:**
```java
// In ArrowSerializer.java
private static Class<?> schemaTypeToJavaClass(String schemaType) {
    if (schemaType == null) return String.class;
    switch (schemaType.toLowerCase()) {
        case "str": case "string": case "id_string": case "id_character":
            return String.class;
        case "int": case "integer": case "id_integer":
            return Integer.class;
        case "long": case "id_long":
            return Long.class;
        case "float": case "id_float":
            return Float.class;
        case "double": case "id_double":
            return Double.class;
        case "bool": case "boolean": case "id_boolean":
            return Boolean.class;
        case "datetime": case "date": case "id_date":
            return Date.class;
        case "decimal": case "bigdecimal": case "id_bigdecimal":
            return BigDecimal.class;
        case "id_byte": return Byte.class;
        case "id_short": return Short.class;
        default: return String.class;
    }
}
```

### Anti-Patterns to Avoid
- **Data inference for types:** Never inspect `first_val` of a column to determine Arrow type. Always use schema.
- **Inconsistent sync:** Never call a Java method without syncing context/globalMap before and after.
- **Direct `print()` output:** All output through logging framework on both sides.
- **Shared mutable compiled script:** Do not share a single compiled Groovy Script across threads with synchronized access. Either clone per-thread or execute sequentially.
- **Hardcoded port:** Always use dynamic port allocation via `socket.bind(('', 0))`.

## Schema Format Standardization

### Audit Results

**What converters produce** (from analysis of 30+ converted JSON files):

Each schema column is a dict with these keys:
```json
{
    "name": "column_name",          // ALWAYS present
    "type": "str",                  // ALWAYS present -- Python type string
    "nullable": true,               // ALWAYS present -- boolean
    "key": false,                   // ALWAYS present -- boolean
    "length": 50,                   // OPTIONAL -- only when >= 0
    "precision": 2,                 // OPTIONAL -- only when >= 0
    "date_pattern": "%Y-%m-%d"      // OPTIONAL -- only for datetime columns
}
```

**Observed type values:**
| Type String | Source | Frequency | Meaning |
|-------------|--------|-----------|---------|
| `str` | `convert_type("id_String")` | Very common | String |
| `int` | `convert_type("id_Integer")`, `convert_type("id_Long")`, etc. | Very common | Integer (loses Long/Byte/Short distinction) |
| `float` | `convert_type("id_Double")`, `convert_type("id_Float")` | Common | Float/Double (loses Float vs Double distinction) |
| `bool` | `convert_type("id_Boolean")` | Moderate | Boolean |
| `datetime` | `convert_type("id_Date")` | Common | Date/Timestamp |
| `Decimal` | `convert_type("id_BigDecimal")` | Rare | BigDecimal (case-sensitive!) |
| `object` | `convert_type("id_Object")` | Rare | Generic object |
| `id_String` | tXMLMap converter bug (skips `convert_type()`) | 2 files | Raw Talend type |
| `id_Integer` | tXMLMap converter bug | 2 files | Raw Talend type |

**Decision: Keep the converter output format as-is.** [VERIFIED: codebase analysis]

Rationale:
1. Changing the converter format would require re-converting all existing JSON configs (violates CLAUDE.md constraint: "No breaking changes: Converter JSON format must remain compatible")
2. The bridge must handle what exists -- both Python types and raw Talend types
3. Type fidelity loss (Long vs Integer) is acceptable because Arrow int64 handles both, and Talend itself uses int64 for most integer operations
4. The bridge's type mapping table (Pattern 1 above) handles all observed type strings

**The bridge's `type_mapping.py` becomes THE authoritative mapping from schema type strings to Arrow types, used by both Python serialization and Java deserialization.**

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arrow IPC serialization | Custom binary protocol | `pyarrow.ipc` / Arrow Java IPC | Battle-tested, handles endianness, alignment, compression |
| Java expression evaluation | Custom parser/interpreter | Groovy `GroovyShell.parse()` + `Script.run()` | Full Java/Groovy compatibility, handles closures, imports |
| Python-Java RPC | REST/HTTP bridge, socket protocol | Py4J | Purpose-built for Python-Java interop, handles type conversion |
| Retry logic | Custom retry decorator | Simple retry loop (3 attempts, 100ms backoff) | Py4J 0.10.9.9 already handles empty-response retry; our retry wraps connection-level failures |
| Uber-JAR building | Manual classpath assembly | Maven assembly plugin or shade plugin | Correctly handles dependency merging, manifest, service files |
| Thread-local script state | Manual ThreadLocal management | Sequential execution for row processing | Groovy Script objects share class-level state, thread-local binding is insufficient |

**Key insight:** The bridge is a thin coordination layer. The heavy lifting (Arrow serialization, Groovy execution, Py4J transport) is done by well-tested libraries. The rewrite's value is in correct wiring, not in replacing library functionality.

## Common Pitfalls

### Pitfall 1: Arrow IPC Version Mismatch
**What goes wrong:** PyArrow 23.0.1 (Python) sends IPC data that Arrow Java 15.0.2 cannot read.
**Why it happens:** Newer Arrow versions may use IPC features not available in older versions.
**How to avoid:** Arrow IPC format is backward-compatible since 1.0.0 [CITED: arrow.apache.org/docs/format/Versioning.html]. The stable IPC format (metadata version V5) is readable by all Arrow 1.0+ implementations. Both 15.0.2 and 23.0.1 are well above 1.0. No action needed as long as we don't use IPC features added after 15.0.2 (dictionary replacement, body buffer compression). Stick to basic types and no compression.
**Warning signs:** `ArrowInvalid` or `UnsupportedOperation` exceptions during IPC read.

### Pitfall 2: Decimal Precision/Scale Mismatch Between Python and Java
**What goes wrong:** Python sends Decimal with precision=38, scale=18. Java creates DecimalVector with precision=38, scale=2 (from first value inference). Arrow rejects the mismatch.
**Why it happens:** Current code infers precision/scale from first non-null value independently on each side.
**How to avoid:** Schema drives precision/scale on both sides. Schema column has `precision` field. Python's `build_arrow_schema()` and Java's `createVectorForType()` both read from the same schema.
**Warning signs:** `ArrowBufPointer` errors, `BigDecimal scale mismatch` exceptions.

### Pitfall 3: Groovy Script Thread Safety
**What goes wrong:** Parallel `forEach` with `synchronized(compiledScript)` serializes execution, providing zero parallelism benefit while adding synchronization overhead.
**Why it happens:** Groovy `Script` objects store execution state (binding, variables) at instance level. Sharing one script across threads requires synchronization.
**How to avoid:** Two options: (1) Parse the script once, clone per chunk/batch using `script.getClass().newInstance()`, or (2) Accept sequential execution for row-level processing (the compile-once benefit already provides the major performance win). Recommendation: Sequential execution. The compile-once pattern is the real performance win. Parallel row execution introduces correctness risks (shared globalMap, non-atomic updates) that outweigh throughput gains.
**Warning signs:** `ConcurrentModificationException`, wrong values in output rows.

### Pitfall 4: Context/GlobalMap Sync Direction
**What goes wrong:** Java code modifies `globalMap.put("key", value)` but Python side never sees the change.
**Why it happens:** Python and Java each have independent copies of context/globalMap dicts. Changes on one side don't automatically reflect on the other.
**How to avoid:** Sync pattern: (1) Python -> Java before every call, (2) Java -> Python after every call. The `_sync_from_java()` + `_sync_to_java()` pair MUST bracket every Py4J call.
**Warning signs:** globalMap variables set in tJava invisible to subsequent Python components.

### Pitfall 5: JVM Startup Race Condition
**What goes wrong:** Python tries to connect before JVM has started the Py4J GatewayServer.
**Why it happens:** `subprocess.Popen` returns immediately, JVM class loading takes 1-3 seconds.
**How to avoid:** Current retry loop with 0.5s sleep is functional. Improve by: (1) reading JVM stdout for startup marker, (2) reducing initial sleep from 2s to 0.5s, (3) using exponential backoff (0.1s, 0.2s, 0.4s, ...).
**Warning signs:** `ConnectionRefusedError` on first attempt.

### Pitfall 6: Maven Not Installed on Dev Machine
**What goes wrong:** Cannot rebuild Java JAR after code changes.
**Why it happens:** Maven is not installed (`mvn` not found). No Maven wrapper (`mvnw`) in project.
**How to avoid:** Add Maven wrapper (`mvnw` + `.mvn/` directory) to the project so builds work regardless of system Maven installation. Also need to add maven-assembly-plugin or maven-shade-plugin to pom.xml for creating the uber-JAR (`java-bridge-with-dependencies.jar`).
**Warning signs:** `command not found: mvn`, missing target/ directory.

## Code Examples

### Schema-Driven Arrow Serialization (Python -> Java)
```python
# Source: Designed for rewrite based on converter output analysis
def _dataframe_to_arrow_bytes(
    self, df: pd.DataFrame, schema: list[dict]
) -> bytes:
    """Convert DataFrame to Arrow IPC bytes using explicit schema.

    Args:
        df: Input DataFrame.
        schema: List of column dicts from component config.
                Each dict has: name, type, nullable, key, [length], [precision], [date_pattern].

    Returns:
        Arrow IPC stream bytes.
    """
    arrow_schema = build_arrow_schema(schema)
    table = pa.Table.from_pandas(df, schema=arrow_schema, preserve_index=False)
    sink = pa.BufferOutputStream()
    writer = pa.ipc.new_stream(sink, table.schema)
    writer.write_table(table)
    writer.close()
    return sink.getvalue().to_pybytes()
```

### Sync Pair Pattern
```python
# Source: Designed for rewrite based on BRDG-03 requirement
def _sync_to_java(self) -> None:
    """Push current context and globalMap to Java bridge."""
    if self._context_manager:
        java_ctx = self._java_bridge.getContext()
        java_ctx.clear()
        for k, v in self._context_manager.get_all().items():
            java_ctx.put(k, v)

    if self._global_map:
        java_gm = self._java_bridge.getGlobalMap()
        java_gm.clear()
        for k, v in self._global_map.get_all().items():
            java_gm.put(k, v)

def _sync_from_java(self) -> None:
    """Pull updated context and globalMap from Java bridge."""
    java_context = self._java_bridge.getContext()
    java_globalmap = self._java_bridge.getGlobalMap()

    if self._context_manager:
        for k in java_context:
            self._context_manager.set(str(k), java_context[k])

    if self._global_map:
        for k in java_globalmap:
            self._global_map.put(str(k), java_globalmap[k])
```

### Java-Side Logging Pattern
```java
// Source: Designed for rewrite based on D-14, D-15, D-16
import java.util.logging.Logger;
import java.util.logging.Level;

public class JavaBridge {
    private static final Logger logger = Logger.getLogger("JavaBridge");

    // Called by Python bridge during startup to sync log levels
    public void setLogLevel(String pythonLevel) {
        Level javaLevel;
        switch (pythonLevel.toUpperCase()) {
            case "DEBUG": javaLevel = Level.FINE; break;
            case "INFO": javaLevel = Level.INFO; break;
            case "WARNING": javaLevel = Level.WARNING; break;
            case "ERROR": javaLevel = Level.SEVERE; break;
            default: javaLevel = Level.INFO;
        }
        logger.setLevel(javaLevel);
        logger.info("[JavaBridge] Log level set to " + javaLevel);
    }
}
```

### Maven Assembly Plugin for Uber-JAR
```xml
<!-- Add to pom.xml <plugins> section -->
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-assembly-plugin</artifactId>
    <version>3.6.0</version>
    <configuration>
        <archive>
            <manifest>
                <mainClass>com.citi.gru.etl.JavaBridge</mainClass>
            </manifest>
        </archive>
        <descriptorRefs>
            <descriptorRef>jar-with-dependencies</descriptorRef>
        </descriptorRefs>
        <finalName>java-bridge-with-dependencies</finalName>
        <appendAssemblyId>false</appendAssemblyId>
    </configuration>
    <executions>
        <execution>
            <id>make-assembly</id>
            <phase>package</phase>
            <goals>
                <goal>single</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

### Maven Wrapper Setup
```bash
# Run once in the java/ directory to add Maven wrapper
cd src/v1/java_bridge/java
mvn wrapper:wrapper -Dmaven=3.9.6
# This creates: mvnw, mvnw.cmd, .mvn/wrapper/maven-wrapper.properties
# After this, use ./mvnw instead of mvn
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Py4J 0.10.9.7 | Py4J 0.10.9.9 | Jan 2025 | Retry on empty response -- fixes intermittent bridge failures [CITED: py4j.org/changelog.html] |
| Data inference for Arrow types | Schema-driven type mapping | This phase | Eliminates all-null column failures, mixed-type bugs, first-value-wins |
| `print()` everywhere | `logging` (Python) + JUL (Java) | This phase | Production-grade logging with level control |
| Manual sync in each component | Automatic sync in bridge layer | This phase | Eliminates forgotten sync bugs |

**Deprecated/outdated:**
- `_build_arrow_schema()` with first-non-null inference: Replaced by `build_arrow_schema(schema)` with explicit schema
- `executeBatchOneTimeExpressions()` (Java): Dead code, replaced by `executeBatchOneTimeExpressionsWithGlobalMap()`
- Direct `print()` calls in bridge code: All replaced with logging

## Dead Code Audit (JavaBridge.java)

| Method | Status | Action |
|--------|--------|--------|
| `executeBatchOneTimeExpressions()` | Dead -- not called from Python | Remove [VERIFIED: grep of bridge.py shows only `executeBatchOneTimeExpressionsWithGlobalMap` is called] |
| `executeTMapCompiled()` | Called from `bridge.py:execute_tmap_compiled()` | Keep -- but this duplicates `compileTMapScript` + `executeCompiledTMap` flow. Consider whether both paths are needed. |
| All other public methods | Active | Rewrite |

## java_bridge_manager.py Assessment

**Recommendation: Update, not rewrite.** [VERIFIED: code analysis of 128 lines]

The manager's responsibilities are sound:
- Dynamic port allocation via `socket.bind(('', 0))` -- correct
- Bridge lifecycle (start/stop) -- correct
- Context manager pattern (`__enter__`/`__exit__`) -- correct
- Library validation on startup -- correct
- Routine loading on startup -- correct

**Changes needed:**
1. Add log level passing to bridge on startup (D-16)
2. Add `exc_info=True` to error logging for traceback visibility
3. Remove silent fallback to Python execution on bridge failure (D-11 -- fail fast instead of `self.enable = False`)
4. Type hints cleanup
5. Integration with Phase 1's rewritten exceptions (`JavaBridgeError` instead of generic `RuntimeError`)

Estimated: ~30 lines of changes, not a rewrite.

## Compiled Script Synchronization (BRDG-06)

### Current Problem
The `compileTMapScript()` + `executeCompiledTMap()` pattern caches compiled scripts in a `ConcurrentHashMap<String, CompiledTMapScript>`. The script object itself is a Groovy `Script` instance that holds mutable state (binding, variables). When `executeCompiledTMap()` runs with `synchronized(script)`, it serializes access to the cached script.

**Issues found:**
1. Script binding is overwritten on each execution -- if two threads call `executeCompiledTMap` for the same component_id, the binding from thread B overwrites thread A's binding.
2. The `synchronized` block covers the entire execution, including Arrow I/O -- unnecessarily long critical section.
3. No cache invalidation -- compiled scripts persist for the lifetime of the JVM process.

### Recommended Fix
For the rewrite, handle compiled script caching as follows:

1. **Cache the compiled Script class, not the instance.** Groovy compiles to a `Class<Script>`. Cache `Class<? extends Script>` and create a new instance per execution via `scriptClass.getDeclaredConstructor().newInstance()`. Each instance gets its own binding -- no synchronization needed.
2. **Add cache invalidation.** `clearCompiledScript(componentId)` and `clearAllCompiledScripts()` methods for cleanup between iterate cycles.
3. **Remove parallel execution from `executeJavaRow` and `executeTMapPreprocessing`.** The `synchronized(compiledScript)` pattern provides zero parallelism benefit. Use sequential iteration with compile-once optimization. The compile-once pattern (not parallelism) is the real performance win.

```java
// Cache Script CLASS, not instance
private Map<String, Class<? extends Script>> compiledScriptClasses = new ConcurrentHashMap<>();

public Map<String, byte[]> executeCompiledTMap(String componentId, byte[] arrowData, ...) {
    Class<? extends Script> scriptClass = compiledScriptClasses.get(componentId);
    // New instance per execution -- no thread safety concern
    Script script = scriptClass.getDeclaredConstructor().newInstance();
    script.setBinding(execBinding);
    Object result = script.run();
    // ...
}
```

## JAR/Library Loading (BRDG-04)

### Current Problem
- `validateLibraries()` does a substring match on `System.getProperty("java.class.path")` -- fragile
- No mechanism to dynamically add JARs at runtime
- pom.xml has no assembly/shade plugin, so uber-JAR cannot be built
- Maven is not installed on dev machine

### Recommended Approach
1. **Add Maven wrapper** (`mvnw`) to the Java project directory so builds work without system Maven installation
2. **Add maven-assembly-plugin** to pom.xml to create `java-bridge-with-dependencies.jar`
3. **Improve library validation:** Instead of classpath string matching, attempt `Class.forName()` for a known class from each library
4. **Support dynamic classpath extension:** Accept a `lib_dir` parameter at startup. The JVM command adds all JARs in that directory to the classpath via `-cp` glob
5. **tLibraryLoad equivalent:** When a job config specifies `libraries: [...]`, the bridge startup command includes those JARs in the classpath. No runtime classpath modification needed -- all JARs known at JVM startup time.

```python
# In bridge.py start() method
def start(self, port: int, lib_dir: str = None, log_level: str = "INFO"):
    """Start JVM with dynamic classpath."""
    classpath_parts = [self._jar_path]
    if lib_dir and os.path.isdir(lib_dir):
        jar_files = glob.glob(os.path.join(lib_dir, "*.jar"))
        classpath_parts.extend(jar_files)
    classpath = os.pathsep.join(classpath_parts)
    cmd = ["java", ..., "-cp", classpath, "com.citi.gru.etl.JavaBridge"]
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Arrow IPC format between PyArrow 23.0.1 and Arrow Java 15.0.2 is fully compatible for basic types | Pitfall 1 | HIGH -- data transfer would fail entirely. Mitigated by stable IPC format guarantee since 1.0 and both being well above 1.0 |
| A2 | Sequential row execution (removing parallel forEach) is acceptable performance for production workloads | Pitfall 3 / BRDG-06 | MEDIUM -- if parallelism was providing significant speedup in production, removing it could cause slowdowns. But the current synchronized pattern negates parallelism anyway. |
| A3 | Groovy Script class can be cached and new instances created per execution via `getDeclaredConstructor().newInstance()` | BRDG-06 | LOW -- standard Java reflection pattern, Groovy scripts compile to regular Java classes |
| A4 | Maven wrapper 3.9.6 is compatible with Java 21 and Java 11 targets | Environment | LOW -- Maven wrapper version is independent of JDK target version |

## Open Questions

1. **Arrow IPC timestamp resolution**
   - What we know: Python sends `timestamp("ms")`, Java Arrow 15.0.2 reads it
   - What's unclear: Does Java Arrow 15.0.2 correctly handle millisecond timestamps when PyArrow 23.0.1 may default to microsecond resolution?
   - Recommendation: Add explicit round-trip test for timestamps as first integration test. If resolution mismatch detected, set explicit resolution when creating Arrow schema.

2. **Compile-once vs execute-tmap-compiled duplication**
   - What we know: There are two code paths: (a) `executeTMapCompiled()` compiles + executes in one call, (b) `compileTMapScript()` + `executeCompiledTMap()` separates compile and execute
   - What's unclear: Are both code paths needed or is (a) dead code superseded by (b)?
   - Recommendation: Check tMap component code to see which path is used. If only (b) is used, remove (a) in the rewrite. From code analysis, tMap uses path (b) (`compile_tmap_script` + `execute_compiled_tmap_chunked`). Path (a) (`execute_tmap_compiled`) appears to be the older implementation. Likely safe to remove, but verify no other callers.

3. **tXMLMap raw type strings**
   - What we know: tXMLMap converter outputs raw Talend types (`id_String`, `id_Integer`) instead of Python types
   - What's unclear: Is this a converter bug that will be fixed, or a permanent fixture?
   - Recommendation: Bridge handles both formats defensively. Type mapping table includes all `id_*` entries. If converter is fixed later, the extra mappings are harmless.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Java (JDK) | JVM bridge process | Yes | OpenJDK 21.0.10 | -- |
| Maven | Building Java JAR | **No** | -- | Add Maven wrapper (`mvnw`) to project |
| Py4J (Python) | Python-Java gateway | Yes | 0.10.9.9 | -- |
| PyArrow | Arrow IPC serialization | Yes | 23.0.1 | -- |
| Pytest | Test execution | Yes | 9.0.2 | -- |
| Homebrew | Maven installation | Yes | Available | Maven wrapper eliminates need for system Maven |

**Missing dependencies with no fallback:**
- None (Maven wrapper resolves the Maven gap)

**Missing dependencies with fallback:**
- Maven: Not installed, but Maven wrapper (`mvnw`) will be added to the project as part of this phase. The wrapper downloads and caches Maven automatically.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (already configured by Phase 1) |
| Quick run command | `pytest tests/v1/engine/test_bridge_type_mapping.py -x -m unit` |
| Full suite command | `pytest tests/v1/engine/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRDG-01 | Data type serialization for 12 types | unit + integration | `pytest tests/v1/engine/test_bridge_type_mapping.py -x` | No -- Wave 0 |
| BRDG-02 | Schema-driven Arrow serialization | unit | `pytest tests/v1/engine/test_bridge_serialization.py -x` | No -- Wave 0 |
| BRDG-03 | Context/globalMap sync at every call site | unit | `pytest tests/v1/engine/test_bridge_sync.py -x` | No -- Wave 0 |
| BRDG-04 | JAR/library loading robustness | integration | `pytest tests/v1/engine/test_bridge_integration.py -x -m java` | No -- Wave 0 |
| BRDG-05 | Py4J 0.10.9.9 upgrade | integration | `pytest tests/v1/engine/test_bridge_integration.py -x -m java` | No -- Wave 0 |
| BRDG-06 | Compiled script synchronization | unit + integration | `pytest tests/v1/engine/test_bridge_compilation.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/v1/engine/test_bridge_type_mapping.py tests/v1/engine/test_bridge_serialization.py -x -m unit`
- **Per wave merge:** `pytest tests/v1/engine/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/v1/engine/test_bridge_type_mapping.py` -- covers BRDG-01, BRDG-02
- [ ] `tests/v1/engine/test_bridge_serialization.py` -- covers BRDG-02
- [ ] `tests/v1/engine/test_bridge_sync.py` -- covers BRDG-03
- [ ] `tests/v1/engine/test_bridge_compilation.py` -- covers BRDG-06
- [ ] `tests/v1/engine/test_bridge_integration.py` -- covers BRDG-04, BRDG-05 (requires @pytest.mark.java)
- [ ] Maven wrapper setup -- required before Java-side integration tests can build the JAR

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A -- batch ETL, no user auth |
| V3 Session Management | No | N/A -- no sessions |
| V4 Access Control | No | N/A -- single-user batch system |
| V5 Input Validation | Yes | Schema-driven type validation before Arrow serialization; Groovy expressions come from trusted config files only |
| V6 Cryptography | No | N/A -- no encryption in bridge layer |

### Known Threat Patterns for Bridge Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Groovy code injection | Tampering | Expressions come from converter-generated JSON configs, not user input at runtime. Trust boundary is at the converter. |
| JVM resource exhaustion | Denial of Service | `RootAllocator(Long.MAX_VALUE)` allows unbounded memory. Consider setting a memory limit. |
| Port scanning/hijacking | Spoofing | Py4J listens on localhost only (default). Dynamic port allocation reduces predictability. |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `bridge.py` (590 lines), `JavaBridge.java` (1022 lines), `RowWrapper.java` (160 lines), `java_bridge_manager.py` (128 lines)
- Codebase analysis: 30+ converter JSON outputs in `tests/talend_xml_samples/converted_jsons/`
- Codebase analysis: `type_mapping.py`, `components/base.py` (`_parse_schema()`)
- Codebase analysis: `base_component.py` `_TYPE_MAPPING` and `_resolve_java_expressions()`
- [VERIFIED: pip show py4j] -- Py4J 0.10.9.9 installed
- [VERIFIED: pyarrow version] -- PyArrow 23.0.1 installed
- [VERIFIED: java --version] -- OpenJDK 21.0.10

### Secondary (MEDIUM confidence)
- [CITED: py4j.org/changelog.html] -- Py4J 0.10.9.9 changelog: "Retry Py4J on empty response"
- [CITED: arrow.apache.org/docs/format/Versioning.html] -- Arrow IPC format stability guarantee
- [CITED: central.sonatype.com/artifact/net.sf.py4j/py4j] -- Py4J 0.10.9.9 on Maven Central

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all versions verified against installed packages and registries
- Architecture: HIGH -- based on thorough audit of all 4 source files and 30+ converter outputs
- Pitfalls: HIGH -- identified from actual code bugs, not theoretical concerns
- Schema standardization: HIGH -- based on exhaustive audit of all converter JSON outputs
- BRDG-06 compiled script fix: MEDIUM -- Groovy Script class caching is standard pattern but needs integration testing

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable stack, no fast-moving dependencies)
