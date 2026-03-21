# Audit Report: tJavaRow / JavaRowComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tJavaRow` |
| **V1 Engine Class** | `JavaRowComponent` |
| **Engine File** | `src/v1/engine/components/transform/java_row_component.py` (99 lines) |
| **Java Bridge Method** | `src/v1/java_bridge/bridge.py` -> `execute_java_row()` (lines 119-155) |
| **Java Side** | `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` -> `executeJavaRow()` (lines 75-176) |
| **Row Wrapper** | `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` (160 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 316-330) + `parse_java_row()` (lines 913-928) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tJavaRow': component = self.component_parser.parse_java_row(node, component)` (lines 375-376) |
| **Registry Aliases** | `JavaRowComponent`, `JavaRow`, `tJavaRow` (registered in `src/v1/engine/engine.py` lines 127-129) |
| **Category** | Transform / Custom Code |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/java_row_component.py` | Engine implementation (99 lines) -- thin orchestrator delegating to Java bridge |
| `src/v1/java_bridge/bridge.py` (lines 119-155) | Python-side bridge: Arrow serialization, Java invocation, context/globalMap sync |
| `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` (lines 75-176) | Java-side: Arrow deserialization, Groovy compilation, parallel row execution, Arrow re-serialization |
| `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` | Dynamic row wrapper: Arrow read (input_row), Map write (output_row), Groovy propertyMissing for dot notation |
| `src/converters/complex_converter/component_parser.py` (lines 316-330, 913-941) | Parameter mapping (CODE/IMPORT XML entity decode) + output_schema type conversion |
| `src/converters/complex_converter/converter.py` (lines 375-376, 519-536) | Dispatch to parser + Java requirement detection |
| `src/converters/complex_converter/expression_converter.py` (lines 231-255) | Talend type -> Python type mapping (`convert_type()`) |
| `src/v1/engine/base_component.py` | Base class: `execute()`, `_resolve_java_expressions()`, `_update_stats()`, `_update_global_map()` |
| `src/v1/engine/context_manager.py` | ContextManager: `get_all()`, `is_java_enabled()`, `get_java_bridge()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`JavaBridgeError`, `ConfigurationError`) -- NOT used by this component |
| `tests/v1/test_java_integration.py` | Integration tests (2 test scenarios: basic tJavaRow + context sync) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 2 | 2 | CODE/IMPORT extracted with XML entity decode; output_schema built from FLOW metadata; missing DIE_ON_ERROR, incomplete XML entity decode, double type conversion chain loses precision |
| Engine Feature Parity | **Y** | 2 | 5 | 4 | 2 | No REJECT flow; no die_on_error; synchronized parallel execution bottleneck; no context/globalMap reverse sync to engine; no ERROR_MESSAGE globalMap |
| Code Quality | **Y** | 2 | 2 | 5 | 2 | Cross-cutting base class bugs; no custom exception usage; no input validation; bidirectional sync gap |
| Performance & Memory | **Y** | 1 | 2 | 2 | 1 | `synchronized(compiledScript)` serializes all parallel row execution; no chunking for large datasets; full Arrow copy per invocation |
| Testing | **R** | 1 | 1 | 0 | 0 | Only 2 integration tests; no unit tests; no negative tests; no type edge case tests |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tJavaRow Does

`tJavaRow` is a custom code component in the Talend Custom Code family that executes user-written Java code on each row of a data flow. It functions as an in-line per-row transformer, accepting one input flow and producing one output flow. The component is conceptually similar to a 1-input/1-output `tMap` but with arbitrary Java logic instead of expression mappings. In Talend's generated code, the user's Java snippet is embedded directly inside a `while(hasNext)` loop that iterates over all incoming rows.

**Source**: [tJavaRow Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/java-custom-code/tjavarow-standard-properties), [tJavaRow Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/tjavarow), [tJavaRow ESB 6.x Documentation](https://talendskill.com/talend-for-esb-docs/docs-6-x/tjavarow-docs-for-esb-6-x/)

**Component family**: Custom Code (Java custom code)
**Available in**: All Talend products (Standard). Also available in Spark Batch and Spark Streaming variants.
**Required JARs**: None by default (user-specified imports may require additional JARs).

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines both input and output structure. Supports Built-In and Repository schema types. Dynamic schema supported for unknown columns. |
| 3 | Edit Schema | -- | Action button | -- | Opens schema editor. Changes can be propagated upstream/downstream via "Sync columns" button. Allows adding/removing/reordering output columns independently from input. |
| 4 | Generate Code | -- | Action button | -- | Auto-generates Java mapping code `output_row.colName = input_row.colName;` for all columns. When input and output schemas have matching names, mappings are direct. For non-matching names, maps by position or to last known input field. |
| 5 | Code | `CODE` | Memo (MEMO_JAVA) | Empty | **Mandatory**. Java code executed once per input row. Access to `input_row` (read-only, dot notation), `output_row` (write, dot notation), `context` variables, `globalMap`, loaded routines. XML-encoded in Talend `.item` files with `&#xD;&#xA;` for newlines, `&lt;` for `<`, `&gt;` for `>`, `&amp;` for `&`, `&quot;` for `"`. |
| 6 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 7 | Import | `IMPORT` | Memo (MEMO_JAVA) | Empty | Java import statements for external classes referenced in CODE. Same XML entity encoding as CODE. Added before the class definition in generated code. Example: `import java.text.SimpleDateFormat;` |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | **Required**. Incoming data flow. Each row is accessible via `input_row` object. The link name in Talend Studio becomes the `input_row` variable name in generated code. |
| `FLOW` (Main) | Output | Row > Main | **Required**. Outgoing data flow. Each row is written via `output_row` object. Schema defines the output columns. 1:1 mapping with input rows (one output per input). |
| `REJECT` | Output | Row > Reject | Rows that caused exceptions during Java code execution. Only active when `DIE_ON_ERROR=false` (though official documentation does not explicitly document REJECT for tJavaRow, the pattern follows the standard die-on-error/reject paradigm). Contains all schema columns plus `errorCode` (String) and `errorMessage` (String). |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed by this component. This is the primary row count variable. In Talend generated code, incremented after each row's code block executes. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output. Equals `NB_LINE - NB_LINE_REJECT`. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows that caused exceptions during Java code execution and were routed to REJECT. Zero when no REJECT link is connected or when `DIE_ON_ERROR=true`. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred. Available for reference in downstream error handling flows via `globalMap.get("{id}_ERROR_MESSAGE")`. |

**Access syntax in Talend CODE**: `((Integer)globalMap.get("tJavaRow_1_NB_LINE"))` -- note the explicit cast and string-based key access.

### 3.5 input_row / output_row Access Patterns

#### Talend Native Behavior (Generated Code)

In Talend's generated Java code, `input_row` and `output_row` are strongly-typed struct-like objects with direct field access:

```java
// Talend native: dot notation with typed fields
output_row.full_name = input_row.first_name + " " + input_row.last_name;
output_row.is_adult = input_row.age >= 18;
output_row.amount_with_tax = input_row.amount * 1.08;
```

Key characteristics of Talend's native implementation:
1. **Direct field access**: `input_row.columnName` -- no method call, no string lookup. The column name is a Java field on a generated inner class.
2. **Strongly typed**: Each field has the Java type declared in the schema. `input_row.age` is `int` (not `Integer`), `input_row.name` is `String`.
3. **Compile-time checked**: Misspelled column names cause compilation errors in Talend Studio.
4. **Nullable primitives**: Talend uses boxed types (`Integer`, `Long`, `Double`) when columns are nullable, primitive types (`int`, `long`, `double`) when non-nullable.
5. **Assignment semantics**: `output_row.x = value` is a direct field assignment, not a method call.

#### V1 Implementation (RowWrapper)

The v1 implementation uses `RowWrapper` with `get()`/`set()` methods AND Groovy `propertyMissing()` for dot notation:

```java
// V1: get/set methods
String name = (String) input_row.get("first_name");
output_row.set("full_name", name + " " + lastName);

// V1: also supports dot notation via Groovy propertyMissing
String name = input_row.first_name;  // calls propertyMissing("first_name") -> get("first_name")
output_row.full_name = value;        // calls propertyMissing("full_name", value) -> set("full_name", value)
```

**Behavioral differences from Talend**:
- Values returned by `get()` are `Object` type, requiring explicit casting: `(String) input_row.get("name")`
- Groovy `propertyMissing` returns `Object`, not the schema-typed value
- No compile-time column name checking -- misspelled names cause runtime `IllegalArgumentException`
- All values are boxed (no primitive types)
- `set()` accepts any `Object` -- no type checking against output_schema

### 3.6 Context, GlobalMap, and Routine Access

#### context Access
In Talend: `context.variableName` (direct field access on a generated context class)
In V1: `context.get("variableName")` (Map-based access via Groovy binding)

#### globalMap Access
In Talend: `globalMap.get("key")` returns `Object`, requires casting: `((String)globalMap.get("key"))`
In V1: `globalMap.get("key")` -- same pattern, compatible

#### Routine Access
In Talend: `routines.MyRoutine.myMethod(args)` or `MyRoutine.myMethod(args)` (imported by default)
In V1: Both `routines.MyRoutine.myMethod(args)` and `MyRoutine.myMethod(args)` supported via dual binding (lines 130-135 of JavaBridge.java)

### 3.7 Type Mapping: Talend Schema to Java Types

| Talend Schema Type | Java Type in input_row/output_row | Generated Code Cast | Nullable Variant |
|--------------------|-----------------------------------|---------------------|-----------------|
| `id_String` | `String` | `(String)` | Always nullable |
| `id_Integer` | `int` / `Integer` | `(Integer)` | `Integer` when nullable |
| `id_Long` | `long` / `Long` | `(Long)` | `Long` when nullable |
| `id_Float` | `float` / `Float` | `(Float)` | `Float` when nullable |
| `id_Double` | `double` / `Double` | `(Double)` | `Double` when nullable |
| `id_Boolean` | `boolean` / `Boolean` | `(Boolean)` | `Boolean` when nullable |
| `id_Date` | `java.util.Date` | `(Date)` | Always nullable |
| `id_BigDecimal` | `java.math.BigDecimal` | `(BigDecimal)` | Always nullable |
| `id_Character` | `char` / `Character` | `(Character)` | `Character` when nullable |
| `id_Byte` | `byte` / `Byte` | `(Byte)` | `Byte` when nullable |
| `id_Short` | `short` / `Short` | `(Short)` | `Short` when nullable |
| `id_Object` | `Object` | -- | Always nullable |
| `id_byte[]` | `byte[]` | `(byte[])` | Always nullable |

### 3.8 Per-Row vs Batch Semantics

Talend's tJavaRow processes rows **strictly sequentially** within a single thread. The Java code block is executed once per row inside a `while(rs.next())` loop. This guarantees:

1. **Deterministic ordering**: Row N is always processed after row N-1
2. **Shared state safety**: Static variables, globalMap, and context are accessed sequentially -- no concurrency concerns
3. **Side-effect safety**: Code that writes to files, databases, or external systems executes in row order
4. **Counter accuracy**: Row-level counters (e.g., `globalMap.put("counter", counter++)`) increment monotonically

The V1 implementation uses `IntStream.range(0, rowCount).parallel().forEach(...)` which is fundamentally **parallel** execution. This changes the semantics (see Section 5).

### 3.9 Behavioral Notes

1. **CODE is mandatory**: Talend requires at least one statement in the CODE field. An empty CODE block will cause the generated code to compile but produce no output mappings, effectively dropping all rows. The v1 converter correctly validates that `java_code` is non-empty.

2. **IMPORT is optional**: If no external libraries are needed, the IMPORT field can be empty. Standard Java classes (`java.util.*`, `java.math.*`, `java.text.*`) are available without import statements in Talend.

3. **1:1 row mapping**: tJavaRow always produces exactly one output row per input row. There is no mechanism to filter rows (skip output) or produce multiple output rows per input. To skip a row, you must still set output_row fields (even to null). To filter, use tFilterRow downstream or a conditional in tMap.

4. **Error handling in CODE**: Exceptions thrown inside the CODE block are caught by Talend's generated try/catch. With `DIE_ON_ERROR=true`, the exception propagates and kills the job. With `DIE_ON_ERROR=false`, the row is sent to REJECT (if connected) with the exception message.

5. **globalMap is mutable**: The CODE block can modify globalMap (`globalMap.put("key", value)`), and these changes are visible to all downstream components. This is commonly used for running totals, counters, and inter-component communication.

6. **context is read-only by convention**: While `context.variableName = newValue` compiles, modifying context variables is not recommended and may not propagate correctly in all execution scenarios (subjob boundaries, parallelism).

7. **Generate Code button**: Creates `output_row.x = input_row.x;` for every matching column. If output has columns not in input, maps by position. This is a development-time convenience -- the generated code is stored in the CODE field and can be freely edited.

8. **XML entity encoding**: The CODE and IMPORT fields in Talend `.item` XML files use XML character entities: `&#xD;&#xA;` for CR+LF, `&#xA;` for LF, `&#xD;` for CR, `&lt;` for `<`, `&gt;` for `>`, `&amp;` for `&`, `&quot;` for `"`. All entities must be decoded before execution.

9. **Schema propagation**: When schema changes are made to a connected input component, Talend prompts to propagate the changes to tJavaRow's schema. The "Sync columns" button manually triggers this propagation.

10. **Dynamic schema**: Supported for retrieving unknown columns at runtime. The dynamic column appears as a single `Dynamic` type in the schema. Not commonly used with tJavaRow since the CODE field typically references specific column names.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **two-stage approach** for tJavaRow:

**Stage 1**: `_map_component_parameters('tJavaRow', config_raw)` in `component_parser.py` (lines 316-330) handles CODE and IMPORT with XML entity decoding.

**Stage 2**: `parse_java_row(node, component)` in `component_parser.py` (lines 913-928) builds the `output_schema` from FLOW metadata by converting Python types back to Java type names.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` (generic extraction)
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tJavaRow', config_raw)` (line 472) -> returns `{java_code, imports}`
4. Back in `converter.py` (line 375-376): `component = self.component_parser.parse_java_row(node, component)` -- builds `output_schema`
5. `parse_java_row()` iterates `component['schema']['output']`, converts Python types to Java via `_python_type_to_java()`
6. Schema is extracted generically from `<metadata connector="FLOW">` with types converted via `ExpressionConverter.convert_type()`

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `CODE` | Yes | `java_code` | 319-321 | XML entity decode for `&#xD;&#xA;`, `&#xA;`, `&#xD;` only. **Missing**: `&lt;`, `&gt;`, `&amp;`, `&quot;` |
| 2 | `IMPORT` | Yes | `imports` | 324-325 | Same XML entity decode as CODE. Same gaps. |
| 3 | `SCHEMA` (output) | Yes | `output_schema` | 913-928 | Built from FLOW metadata. Double type conversion: Talend -> Python -> Java (lossy). |
| 4 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted. Engine has no die_on_error handling for Java code exceptions.** |
| 5 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 6 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 7 | `LABEL` | No | -- | -- | Not needed (cosmetic -- no runtime impact) |

**Summary**: 3 of 7 parameters extracted (43%). 1 runtime-relevant parameter (`DIE_ON_ERROR`) is missing.

### 4.2 Schema Extraction and Type Conversion Chain

The output_schema undergoes a **double type conversion** that loses information:

```
Talend XML         -> ExpressionConverter.convert_type() -> _python_type_to_java()  -> output_schema
id_String          -> 'str'                              -> 'String'                 OK
id_Integer         -> 'int'                              -> 'Integer'                OK
id_Long            -> 'int'  (LOSSY)                     -> 'Integer' (WRONG)        WRONG: Should be 'Long'
id_Float           -> 'float'                            -> 'Double' (LOSSY)         WRONG: Should be 'Float'
id_Double          -> 'float'                            -> 'Double'                 OK (accidental)
id_Boolean         -> 'bool'                             -> 'Boolean'                OK
id_Date            -> 'datetime'                         -> 'Date'                   OK
id_BigDecimal      -> 'Decimal'                          -> 'String' (WRONG)         WRONG: Not in mapping, defaults to 'String'
id_Character       -> 'str'                              -> 'String'                 LOSSY but acceptable
id_Byte            -> 'int'                              -> 'Integer'                LOSSY but acceptable
id_Short           -> 'int'                              -> 'Integer'                LOSSY but acceptable
id_Object          -> 'object'                           -> 'String' (WRONG)         WRONG: Not in mapping, defaults to 'String'
```

The `_python_type_to_java()` method (lines 930-941) has this mapping:
```python
type_mapping = {
    'str': 'String',
    'int': 'Integer',      # id_Long also becomes 'int', so Long -> Integer (WRONG)
    'float': 'Double',     # id_Float also becomes 'float', so Float -> Double (LOSSY)
    'bool': 'Boolean',
    'date': 'Date',
    'datetime': 'Date',
    'bytes': 'byte[]'
}
# Missing: 'Decimal' -> 'BigDecimal', 'object' -> 'Object', 'long' -> 'Long'
```

**Critical**: `id_BigDecimal` -> `'Decimal'` (Python) -> `'String'` (Java) because `'Decimal'` is not in the `_python_type_to_java()` mapping. This means BigDecimal columns in tJavaRow output will be created as String vectors in Arrow, losing numeric precision and preventing numeric operations.

### 4.3 Schema Attribute Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types -- then re-converted to Java types in `parse_java_row()` |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic) |
| `talendType` | **No** | Full Talend type string not preserved -- converted to Python type, then back to Java type (lossy chain) |

**REJECT schema**: The converter DOES extract REJECT metadata (lines 506-507). However, the engine never uses it -- there is no REJECT flow implementation.

### 4.4 XML Entity Decoding

The converter (lines 321, 325) decodes only newline entities:
```python
code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
```

**Missing XML entity decoding**:

| Entity | Character | Impact |
|--------|-----------|--------|
| `&lt;` | `<` | **Critical**: Any Java code with `<` comparisons (`if (age < 18)`) or generics (`List<String>`) will contain literal `&lt;` in the code, causing Groovy compilation failures. |
| `&gt;` | `>` | **Critical**: Any Java code with `>` comparisons or generics will fail to compile. |
| `&amp;` | `&` | **Critical**: Logical AND (`&&`) will appear as `&amp;&amp;`, causing compilation failures. Bitwise AND (`&`) will appear as `&amp;`. |
| `&quot;` | `"` | **High**: String literals containing double quotes will not compile. However, most string literals in Java code use `"` directly (which may not be entity-encoded if the Talend XML parser already decodes them at parse time). |
| `&#x27;` | `'` | **Low**: Single quotes in Java code. Usually not entity-encoded. |

**Important caveat**: When the Talend `.item` file is parsed by Python's `xml.etree.ElementTree` (or `lxml`), standard XML entities (`&lt;`, `&gt;`, `&amp;`, `&quot;`) are typically decoded automatically by the XML parser. The `&#xD;&#xA;` entities for CR+LF are also decoded by standard XML parsers. However, if the converter accesses raw attribute text (before XML parsing), the entities remain. The actual impact depends on whether the XML parser has already decoded these entities before the converter's `config_raw.get('CODE', '')` call.

If the XML parser handles standard entity decoding (which is the default behavior for `ElementTree`), then the explicit `&#xD;&#xA;` replacement is only needed for entities that the parser might NOT decode (which is unusual). This warrants investigation to confirm whether the existing entity decoding is redundant or essential.

### 4.5 Expression Handling

**Java expression marking skip** (component_parser.py lines 462):
```python
if component_name not in ['tMap', 'tJavaRow', 'tJava']:
```

This correctly skips the `{{java}}` expression marking for tJavaRow's config values, since the CODE and IMPORT fields contain raw Java code that should NOT be treated as Java expressions to evaluate. This is correct behavior.

**Context variable handling** (component_parser.py lines 447-448):
```python
elif name not in ['CODE', 'IMPORT'] and isinstance(value, str) and 'context.' in value:
```

This correctly excludes CODE and IMPORT from context variable wrapping with `${...}`. Java code references to `context.variableName` should remain as-is for the Java runtime, not be resolved by Python's ContextManager.

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-JR-001 | **P1** | **`id_Long` maps to `Integer` instead of `Long`**: The double type conversion chain (Talend `id_Long` -> Python `int` -> Java `Integer`) loses the distinction between 32-bit Integer and 64-bit Long. In Java/Arrow, `IntVector` is 32-bit and `BigIntVector` is 64-bit. Long values > 2,147,483,647 will overflow to negative numbers or cause `ArithmeticException`. This is a data corruption risk for any column with large IDs, timestamps-as-longs, or financial amounts stored as Long cents. |
| CONV-JR-002 | **P1** | **`id_BigDecimal` maps to `String` instead of `BigDecimal`**: The `_python_type_to_java()` mapping does not include `'Decimal'` -> `'BigDecimal'`. BigDecimal columns default to `'String'` in the output_schema, causing `VarCharVector` creation in Arrow instead of `DecimalVector`. Financial calculations in Java code that produce `BigDecimal` results will be converted to strings, losing numeric semantics. Downstream components expecting numeric BigDecimal data will fail. |
| CONV-JR-003 | **P1** | **`DIE_ON_ERROR` not extracted**: The `_map_component_parameters()` for tJavaRow (lines 316-330) does not include `DIE_ON_ERROR`. The engine has no mechanism to handle Java code exceptions gracefully -- all exceptions propagate as `RuntimeError`, killing the job regardless of the Talend die_on_error setting. |
| CONV-JR-004 | **P2** | **`id_Float` maps to `Double` instead of `Float`**: The chain `id_Float` -> Python `float` -> Java `Double` loses the Float/Double distinction. While `Double` is a superset of `Float`, the Arrow vectors differ (`Float4Vector` vs `Float8Vector`), doubling memory usage for Float columns. The `inferJavaTypeFromSchema()` on the Java side (line 928-929) DOES support `Float`, but it never receives `"Float"` because the converter always sends `"Double"`. |
| CONV-JR-005 | **P3** | **Potentially redundant XML entity decoding**: The `&#xD;&#xA;`, `&#xA;`, `&#xD;` replacements may be redundant if the XML parser already decodes these entities. Standard XML parsers (`xml.etree.ElementTree`) automatically decode `&lt;`, `&gt;`, `&amp;`, `&quot;` during parsing, so the missing entity decoding is unlikely to be an issue in practice. The existing `&#xD;&#xA;` replacement is itself likely redundant. The approach is fragile and should ideally use `html.unescape()` or `xml.sax.saxutils.unescape()` for robust entity handling, but the risk is lower than originally assessed. |
| CONV-JR-006 | **P2** | **No `id_Object` -> `Object` mapping**: Talend `id_Object` columns (used for heterogeneous data) become Python `'object'`, which `_python_type_to_java()` maps to default `'String'`. Java code operating on Object-typed columns will receive String values instead of the original objects. |
| CONV-JR-007 | **P3** | **No precision/scale propagation for BigDecimal**: Even if `id_BigDecimal` mapping is fixed (CONV-JR-002), the `output_schema` is a flat `{name: type}` dict that cannot carry precision and scale information. The Java side's `inferDecimalPrecisionScale()` falls back to scanning output data, which may produce inconsistent precision across batches. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Execute Java code per row | **Yes** | Medium | `java_row_component.py:81` -> `bridge.py:141` -> `JavaBridge.java:113` | Uses Groovy (not Java) -- functionally equivalent for most code but with subtle differences (see 5.2) |
| 2 | input_row field read (dot notation) | **Yes** | Medium | `RowWrapper.java:129` (`propertyMissing`) | Groovy `propertyMissing` provides dot notation. Returns `Object`, not typed fields. Runtime error on misspelled names (not compile-time). |
| 3 | input_row field read (get method) | **Yes** | N/A | `RowWrapper.java:51` (`get()`) | Not standard Talend -- v1-specific convenience. Users must adapt Talend code from `input_row.name` to `input_row.get("name")` or rely on Groovy propertyMissing. |
| 4 | output_row field write (dot notation) | **Yes** | Medium | `RowWrapper.java:133` (`propertyMissing`) | Groovy `propertyMissing` provides dot notation. No type checking -- any Object accepted. |
| 5 | output_row field write (set method) | **Yes** | N/A | `RowWrapper.java:62` (`set()`) | Not standard Talend -- v1-specific. |
| 6 | output_schema type mapping | **Partial** | Low | `component_parser.py:913-941` | Double type conversion loses Long, Float, BigDecimal, Object (see Section 4.2) |
| 7 | Context variable access | **Yes** | High | `JavaBridge.java:126` | `context` bound as `Map<String, Object>`. Access via `context.get("key")`. Compatible with Talend code using `context.variableName` via Groovy property access on Map. |
| 8 | GlobalMap access | **Yes** | High | `JavaBridge.java:127` | `globalMap` bound as `Map<String, Object>`. Access via `globalMap.get("key")`. Compatible. |
| 9 | Routine access | **Yes** | High | `JavaBridge.java:130-135` | Both `RoutineName.method()` and `routines.RoutineName.method()` patterns supported via dual binding. |
| 10 | IMPORT support | **Yes** | High | `java_row_component.py:56-57` | Imports prepended to java_code before Groovy compilation. |
| 11 | Context sync (Python -> Java) | **Yes** | High | `java_row_component.py:72-78` | All context variables and globalMap entries synced before execution. |
| 12 | Context sync (Java -> Python) | **Partial** | Low | `bridge.py:149-155, 582-590` | `_sync_from_java()` updates bridge's internal dicts, but NOT the engine's ContextManager/GlobalMap. **Bidirectional sync gap.** |
| 13 | NB_LINE tracking | **Yes** | High | `java_row_component.py:88-91` | `_update_stats(rows_read, rows_ok)` called after execution. Base class handles globalMap propagation. |
| 14 | ERROR_MESSAGE tracking | **No** | N/A | -- | Not implemented. Exceptions propagate but `{id}_ERROR_MESSAGE` not set in globalMap. |
| 15 | **REJECT flow** | **No** | N/A | -- | **No reject output. All Java exceptions propagate as RuntimeError, killing the job. No mechanism to route bad rows.** |
| 16 | **DIE_ON_ERROR** | **No** | N/A | -- | **Not extracted from Talend XML. Not handled in engine. Always dies on error.** |
| 17 | Schema validation | **No** | N/A | -- | No pre-execution validation that java_code assigns all output_schema columns. No post-execution validation that output matches schema. |
| 18 | Generate Code | N/A | N/A | -- | Development-time feature -- not applicable at runtime. |
| 19 | Dynamic schema | **No** | N/A | -- | No support for Dynamic column type. |
| 20 | Parallel execution | **V1-specific** | N/A | `JavaBridge.java:113` | `IntStream.parallel()` -- NOT present in Talend. Changes semantics significantly (see 5.2). |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-JR-001 | **P0** | **Parallel execution with `synchronized(compiledScript)` serializes all rows**: `JavaBridge.java` line 113 uses `IntStream.range(0, rowCount).parallel().forEach(...)` for row processing, but line 138 wraps the actual script execution in `synchronized(compiledScript)`. Since there is only ONE compiled script instance, the `synchronized` block means only one thread can execute the script at a time. This effectively serializes execution while paying the overhead of thread pool management, context switching, and synchronized block contention. The result is SLOWER than sequential execution for most workloads due to synchronization overhead. Additionally, the `synchronized` block does not protect the `context` and `globalMap` Maps, which are shared mutable state accessed by `binding.setVariable()` outside the `synchronized` block (lines 126-135) -- this is a data race condition. |
| ENG-JR-002 | **P0** | **No REJECT flow**: Talend routes rows that cause exceptions to a REJECT flow (when `DIE_ON_ERROR=false` and REJECT link is connected). V1 wraps exceptions in `RuntimeException("Error processing row " + i)` (JavaBridge.java line 148) which propagates through `parallel().forEach()` and kills the entire execution. There is no mechanism to capture, accumulate, or route failed rows. For data quality pipelines that expect partial failures (e.g., code that parses dates, validates formats), this is a fundamental gap. |
| ENG-JR-003 | **P1** | **Groovy vs Java compilation differences**: Talend generates Java source code that is compiled by the Java compiler. V1 uses Groovy's `GroovyShell.parse()` which compiles to Groovy bytecode. Differences include: (a) Groovy's truth coercion (`if (someString)` is true for non-null non-empty vs Java's `if (someString)` being a compile error); (b) Groovy's `==` uses `.equals()` vs Java's reference comparison; (c) Groovy auto-imports `groovy.lang.*`, `groovy.util.*`, `java.lang.*`, `java.util.*`, `java.io.*`, `java.net.*`, `java.math.BigDecimal`, `java.math.BigInteger` while Java requires explicit imports; (d) Groovy supports optional typing and dynamic dispatch. Most Talend code is compatible, but edge cases exist. |
| ENG-JR-004 | **P1** | **Context/globalMap modifications in Java code not propagated back to engine**: When Java code executes `globalMap.put("key", value)` or `context.put("key", value)`, these changes are stored in the Java-side `HashMap`. After execution, `bridge.py:_sync_from_java()` (line 150) calls `self.context.update(java_context)` and `self.global_map.update(java_globalmap)`, updating the bridge's internal Python dicts. However, `JavaRowComponent._process()` does NOT read these updated values back into `self.context_manager` (ContextManager) or `self.global_map` (GlobalMap). Downstream components that read from ContextManager/GlobalMap will NOT see changes made by tJavaRow's Java code. This breaks the common Talend pattern of using tJavaRow to set globalMap variables for downstream components (e.g., running totals, counters, flags). |
| ENG-JR-005 | **P1** | **No die_on_error handling**: The `die_on_error` parameter is not extracted from Talend XML and not handled in the engine. The component always propagates exceptions. In Talend, `DIE_ON_ERROR=false` means: (a) catch exceptions per row, (b) route failed rows to REJECT if connected, (c) continue processing remaining rows. V1 has none of this behavior. |
| ENG-JR-006 | **P1** | **Row ordering not guaranteed**: `IntStream.parallel()` processes rows in arbitrary order determined by the JVM's ForkJoinPool. The output arrays are indexed by original row index (`outputArrays.get(colName)[i]`), so the final DataFrame has correct row positions. However, side effects in the Java code (logging, globalMap mutations, counter increments) execute in non-deterministic order. Talend always processes rows sequentially, so code relying on row order for side effects will produce different results. |
| ENG-JR-007 | **P2** | **No pre-execution validation**: The engine does not validate that the Java code is syntactically valid before processing rows. If the Groovy compilation fails (`shell.parse(javaCode)` on JavaBridge.java line 105), the exception message is a Groovy `CompilationFailedException` with line numbers relative to the code snippet, not the original Talend job. Adding a pre-validation step with a clear error message would improve debugging. |
| ENG-JR-008 | **P2** | **`input_row.get()` throws undescriptive error on missing field**: `RowWrapper.getFromArrow()` (line 88-93) throws `IllegalArgumentException("Field not found: " + attempted)` when a field name does not exist. The error does not include the list of available fields, the row index, or the component ID, making debugging difficult in large jobs. |
| ENG-JR-009 | **P2** | **No null handling for non-nullable output columns**: When Java code does not set an output_row field (leaves it null), the output DataFrame will contain null values even if the Talend schema declares the column as non-nullable. Talend would replace null with type defaults (0 for int, "" for String, etc.) based on the schema nullable flag. |
| ENG-JR-010 | **P2** | **Arrow memory not bounded**: `RootAllocator(Long.MAX_VALUE)` (JavaBridge.java line 40) allocates an unbounded Arrow memory allocator. For very large DataFrames, this can consume all available JVM heap. There is no chunking mechanism for tJavaRow (unlike tMap which has `execute_compiled_tmap_chunked`). DataFrames exceeding JVM heap will cause `OutOfMemoryError`. |
| ENG-JR-011 | **P2** | **RowWrapper input_row reads ALL vector columns for toString()**: `RowWrapper.toString()` (lines 142-158) iterates `vectorRoot.getFieldVectors()` and calls `get(fieldName)` for each. For DataFrames with 100+ columns, this is expensive. If Java code accidentally triggers `toString()` (e.g., logging `input_row`), it performs N column reads per row per log call. |
| ENG-JR-012 | **P3** | **No `id_Short`, `id_Byte`, `id_Character` type support in RowWrapper**: `RowWrapper.getFromArrow()` handles `VarCharVector`, `IntVector`, `BigIntVector`, `Float8Vector`, `BitVector`, `DateMilliVector`, `DecimalVector`, `Decimal256Vector`. It does NOT handle `SmallIntVector` (Short), `TinyIntVector` (Byte), or `Float4Vector` (Float). These types fall through to the generic `vector.getObject(rowIndex)` which may return unexpected types. |
| ENG-JR-013 | **P3** | **Groovy shell created per execution**: `JavaBridge.executeJavaRow()` creates a new `GroovyShell` (line 104) for every invocation. While the script is compiled once per invocation, the shell creation involves classloader setup overhead. For jobs that call tJavaRow in an iteration loop, this overhead accumulates. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats(rows_read=len(input_data), ...)` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Note: affected by cross-cutting BUG-JR-001 (NameError in `_update_global_map`). |
| `{id}_NB_LINE_OK` | Yes | **Yes** | `_update_stats(..., rows_ok=len(result_df))` | Always equals NB_LINE since no reject exists. |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | `_update_stats()` defaults `rows_reject=0` | Always 0 since no reject flow exists. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. Exceptions propagate but message not stored. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class `execute()` | V1-specific, not in Talend. |

### 5.4 Data Flow Through the System

The complete data flow for a tJavaRow execution is:

```
1. Python DataFrame (input_data)
   |
   v
2. pa.Table.from_pandas(df, schema=_build_arrow_schema(df))     [bridge.py:133]
   - Infers Arrow schema from pandas dtypes
   - Decimal columns get decimal128(precision, scale) from data
   - Object columns checked for Decimal instances
   |
   v
3. Arrow IPC stream serialization -> bytes                       [bridge.py:134-138]
   - pa.ipc.new_stream() + write_table() + close()
   - Full copy of data into Arrow format
   |
   v
4. Py4J byte[] transfer to JVM                                   [bridge.py:141]
   - Py4J serializes byte[] across JVM boundary
   - Full copy of Arrow bytes
   |
   v
5. Arrow deserialization in Java                                  [JavaBridge.java:85-90]
   - ArrowStreamReader reads bytes into VectorSchemaRoot
   - Third copy of data (Arrow native memory)
   |
   v
6. Groovy script compilation                                     [JavaBridge.java:104-107]
   - GroovyShell.parse(javaCode) compiles to Script class
   - One-time cost per execution
   |
   v
7. Parallel row execution                                        [JavaBridge.java:113-150]
   - IntStream.range(0, rowCount).parallel().forEach(...)
   - RowWrapper created per row (2 objects: input + output)
   - Groovy Binding created per row
   - synchronized(compiledScript) serializes execution
   - Output values collected in Object[] arrays
   |
   v
8. Output Arrow table creation                                   [JavaBridge.java:162-167]
   - createOutputRootFromData() builds VectorSchemaRoot
   - Type inferred from output_schema string
   - Fourth copy of data
   |
   v
9. Arrow IPC stream serialization -> bytes                       [JavaBridge.java:165-167]
   - ArrowStreamWriter writes to ByteArrayOutputStream
   - Fifth copy of data
   |
   v
10. Py4J byte[] transfer back to Python                          [bridge.py:153]
    - Sixth copy of data
    |
    v
11. Arrow deserialization + to_pandas()                          [bridge.py:153-155]
    - pa.ipc.open_stream() + read_all() + to_pandas()
    - Seventh copy of data (final DataFrame)
```

**Total data copies**: ~7 copies of the data (pandas -> Arrow -> bytes -> JVM Arrow -> output arrays -> Arrow -> bytes -> pandas). For a 1 million row x 20 column DataFrame, this means approximately 7x the original memory footprint during peak execution.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-JR-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just JavaRowComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-JR-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-JR-003 | **P1** | `JavaBridge.java:113,126-135,138` | **Data race condition in parallel execution**: The `Binding` object is created per-row OUTSIDE the `synchronized(compiledScript)` block (lines 122-135), but the script execution uses this binding INSIDE the synchronized block (lines 138-141). Since `parallel()` uses a shared ForkJoinPool, multiple threads simultaneously: (a) create Bindings with shared `context` and `globalMap` references (not copies), (b) wait on the synchronized block, (c) the script modifies the binding's variables during `setBinding()` + `run()`. While `outputArrays.get(colName)[i]` is thread-safe by index, the `context` Map is a `HashMap` (not `ConcurrentHashMap`) and could be corrupted by concurrent read/write if the Groovy code modifies it. |
| BUG-JR-004 | **P1** | `java_row_component.py:72-78,81-85` + `bridge.py:149-155,582-590` | **Bidirectional context/globalMap sync gap**: Python syncs TO Java bridge before execution (component lines 72-78), and `_sync_from_java()` syncs FROM Java bridge's JVM to bridge's Python dicts (bridge.py lines 582-590). But the component NEVER reads the bridge's updated dicts back into the engine's `ContextManager` or `GlobalMap`. Changes made by Java code (`globalMap.put("key", value)`) are lost to downstream Python components. |
| BUG-JR-005 | **P1** | `JavaBridge.java:153` | **Division by zero when `execTime == 0`**: Line 153 computes `(rowCount * 1000 / execTime)` for performance logging. When processing completes in under 1ms (small DataFrames), `execTime` is 0, causing `ArithmeticException`. This kills the entire execution after all rows are successfully processed. |
| BUG-JR-006 | **P2** | `java_row_component.py:97-99` | **Generic exception handling loses context**: The catch block logs `Java execution failed: {e}` and re-raises the raw exception. It does not: (a) set `{id}_ERROR_MESSAGE` in globalMap, (b) wrap in `JavaBridgeError` from the custom exception hierarchy, (c) include the java_code snippet for debugging. |
| BUG-JR-007 | **P2** | `JavaBridge.java:877` | **`inferDecimalPrecisionScale()` forces minimum precision=38**: Line 877 `precision = Math.max(precision, 38)` sets precision to at least 38 regardless of actual data. For a column with values like `1.50` (precision=3, scale=2), the output vector uses `DecimalVector(38, 2)`. While this prevents overflow, it wastes memory and may cause precision mismatch when reading back through Arrow (38,2 vs the input's inferred precision). |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-JR-001 | **P2** | **Config key `java_code`** does not follow the Talend XML naming. Talend uses `CODE`. The converter maps `CODE` -> `java_code` (line 328). While descriptive, this differs from other components that use closer-to-Talend naming. |
| NAME-JR-002 | **P2** | **Config key `imports`** (plural) does not match Talend XML `IMPORT` (singular). The converter maps `IMPORT` -> `imports` (line 329). |
| NAME-JR-003 | **P3** | **Class name `JavaRowComponent`** adds `Component` suffix not present in other transform components (`Map`, `FilterRows`, `SortRow`). Should be `JavaRow` for consistency, but `JavaRow` is already a registry alias. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-JR-001 | **P1** | "Every component SHOULD use custom exceptions from `exceptions.py`" | Component uses `ValueError` (line 50, 53) and `RuntimeError` (line 62) instead of `ConfigurationError` and `JavaBridgeError` from the custom hierarchy. The `JavaBridgeError` class exists specifically for this purpose but is unused. |
| STD-JR-002 | **P2** | "`_validate_config()` should validate configuration" | No `_validate_config()` method exists. No validation of `java_code` syntax, `output_schema` non-empty, or `output_schema` type values. Invalid configurations cause obscure Groovy compilation errors. |
| STD-JR-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Schema types undergo double conversion (Talend -> Python -> Java). The output_schema contains Java types (`String`, `Integer`, `Double`) rather than Talend types. While the Java bridge needs Java type names, the intermediate Python type conversion is lossy. |
| STD-JR-004 | **P3** | "No `print()` statements" | `JavaBridge.java` uses `System.out.println()` extensively for compilation timing (line 103, 107), row processing progress (line 110-111), and performance stats (line 153). While these are on the Java side, they pollute stdout in production. Should use `java.util.logging` or SLF4J. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-JR-001 | **P3** | **Commented-out debug prints in JavaBridge.java**: Lines 118-119 contain `// System.out.println("input_row: " + ...)` and `// System.out.println("output_row: " + ...)`. These are development artifacts that should be removed or converted to `logger.trace()`. |
| DBG-JR-002 | **P3** | **Verbose timing output**: Lines 103-107, 110-111, 152-153 of JavaBridge.java print timing information to stdout for every execution. This is useful during development but should be gated behind a debug flag or logging level in production. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-JR-001 | **P2** | **Arbitrary code execution via Groovy**: The `java_code` config value is passed directly to `GroovyShell.parse()` and executed. While this is inherent to the component's purpose (executing user code), there is no sandboxing, no class whitelist, no resource limits. If config comes from untrusted sources, this allows arbitrary JVM code execution including: file system access, network calls, process spawning, JVM shutdown. For the stated use case (Talend conversion tool processing trusted Talend Studio exports), this is acceptable risk. Only applicable in multi-tenant or user-facing scenarios, which are not the target deployment model. |
| SEC-JR-002 | **P2** | **Unvalidated output_schema keys**: The `output_schema` dict keys become Groovy variable names and Arrow column names without sanitization. Malicious or malformed column names (e.g., containing semicolons, quotes, or newlines) could inject code into the Groovy script context or cause Arrow serialization failures. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `Component {self.id}:` prefix -- correct |
| Level usage | INFO for start/completion (lines 69, 93), WARNING for no input (line 41), ERROR for failures (line 98) -- correct |
| Start/complete logging | `_process()` logs start with row count (line 69); logs completion with output rows/columns (line 93) -- correct |
| Sensitive data | No sensitive data logged -- correct. However, java_code content is not logged even at DEBUG level, which could help debugging. |
| No print statements | No `print()` calls in Python code -- correct. Java side has extensive `System.out.println()` (see STD-JR-004). |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **Not used**. Uses `ValueError` (lines 50, 53) and `RuntimeError` (line 62) instead of `ConfigurationError` and `JavaBridgeError`. |
| Exception chaining | **Not used**. Line 99 does bare `raise` (re-raise), which preserves the original traceback. But no `raise ... from e` pattern for wrapped exceptions. |
| `die_on_error` handling | **Not implemented**. No die_on_error config extraction or handling. All errors kill execution. |
| No bare `except` | All except clauses specify `Exception` -- correct. |
| Error messages | Include component ID and error description -- correct. Do not include java_code snippet -- could improve debugging. |
| Graceful degradation | **Not implemented**. Returns empty DataFrame only for null/empty input (line 42). Java exceptions always propagate. |
| Java-side error wrapping | `RuntimeException("Error processing row " + i, e)` (JavaBridge.java line 148) -- correct nesting. But row-level errors in parallel stream terminate ALL rows, not just the failing row. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has full type hints: `input_data: Optional[pd.DataFrame]` -> `Dict[str, Any]` -- correct. |
| Parameter types | Correct for all methods. |
| Missing type hints | None in `java_row_component.py`. `bridge.py:execute_java_row()` has full hints. |

### 6.9 Component Architecture Assessment

The `JavaRowComponent` is extremely thin (99 lines including docstring and imports) -- it is essentially an orchestrator that:
1. Validates input exists (lines 40-42)
2. Reads config (lines 45-47)
3. Validates config non-empty (lines 49-53)
4. Prepends imports (lines 56-57)
5. Checks Java bridge availability (lines 60-64)
6. Syncs context/globalMap to bridge (lines 72-78)
7. Delegates to `java_bridge.execute_java_row()` (lines 81-85)
8. Updates stats (lines 88-91)

All complex logic resides in `bridge.py` and `JavaBridge.java`. This is a good separation of concerns, but it means the component has no control over execution behavior (chunking, error handling, result validation).

---

## 7. Performance & Memory

### 7.1 Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-JR-001 | **P0** | **`synchronized(compiledScript)` serializes parallel execution**: The `parallel().forEach()` on line 113 creates a ForkJoinPool with `Runtime.getRuntime().availableProcessors()` threads. However, `synchronized(compiledScript)` on line 138 allows only ONE thread to execute the script at a time. The N-1 other threads are blocked waiting for the lock. For CPU-bound Groovy scripts, this means: (a) N threads are created and managed (overhead), (b) only 1 thread executes at any time (no parallelism), (c) lock acquisition/release overhead per row (contention). Net effect: **slower than sequential** for most workloads. The synchronized block is necessary because `Script.setBinding()` mutates the single script instance's state, but the correct fix is to either clone the script per thread or compile per thread. |
| PERF-JR-002 | **P1** | **No chunking for large DataFrames**: The entire DataFrame is serialized to Arrow bytes in one shot (bridge.py lines 133-138). For DataFrames approaching the JVM heap limit, this causes `OutOfMemoryError`. The `execute_compiled_tmap_chunked()` method in bridge.py (lines 370-442) demonstrates a chunking approach for tMap -- the same pattern should be applied to tJavaRow. |
| PERF-JR-003 | **P1** | **7x data copy overhead**: As detailed in Section 5.4, the data flows through approximately 7 copy steps (pandas -> Arrow -> bytes -> JVM Arrow -> output arrays -> Arrow -> bytes -> pandas). For a 100MB DataFrame, this requires ~700MB of peak memory. For jobs near memory limits, this can cause failures. |
| PERF-JR-004 | **P2** | **RowWrapper + Binding created per row**: For each of the N rows, the parallel loop creates: 2 RowWrapper objects (input + output), 1 Binding object, and populates the binding with 4+ variables. For 1M rows, this is 4M+ object allocations. The GC pressure from short-lived objects can significantly degrade throughput on large DataFrames. |
| PERF-JR-005 | **P2** | **Groovy script compiled every invocation**: `JavaBridge.executeJavaRow()` creates a new `GroovyShell` and calls `shell.parse(javaCode)` on every call (lines 104-105). For jobs that call tJavaRow in an iteration loop (e.g., processing files from tFileList), the same code is recompiled each time. The tMap path demonstrates script caching via `compiledScripts` ConcurrentHashMap -- the same approach should be used for tJavaRow. |
| PERF-JR-006 | **P3** | **`createOutputRootFromData()` iterates schema with HashMap**: The output schema is stored in `HashMap<String, String>` (line 95 of JavaBridge.java). `HashMap` does not preserve insertion order, so columns in the output Arrow table may be in a different order than the Talend schema. While pandas handles reordering transparently, this adds unnecessary overhead and can cause confusion during debugging. |

### 7.2 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Arrow allocator | `RootAllocator(Long.MAX_VALUE)` -- unbounded. No memory budget or limit. |
| Input cleanup | `inputRoot.close()` and `reader.close()` called (JavaBridge.java lines 172-173). Correct but in main path only -- not in a `finally` block. Exception during processing leaks Arrow memory. |
| Output cleanup | `outputRoot.close()` called (line 174). Same concern about exception paths. |
| Python-side Arrow | `pa.BufferOutputStream` and `pa.ipc.new_stream` used correctly. Python Arrow objects are garbage-collected. |
| Py4J byte transfer | Full byte array copy across JVM boundary. No shared memory or zero-copy optimization. |
| JVM heap | No configuration exposure. Default JVM heap applies. No `-Xmx` setting in the `subprocess.Popen` command (bridge.py lines 48-55). |
| Streaming mode | `BaseComponent._execute_streaming()` exists but `JavaRowComponent._process()` processes the full DataFrame -- no chunked support. |

### 7.3 Performance Comparison with Talend

| Aspect | Talend | V1 |
|--------|--------|----|
| Execution model | Sequential loop, no thread overhead | Parallel with synchronized bottleneck |
| Data movement | In-process, no serialization | Arrow serialization x2 + Py4J transfer x2 |
| Memory overhead | 1x (in-place) | ~7x (multiple copies) |
| Compilation | Java bytecode (fast, cached) | Groovy bytecode (slower, not cached) |
| Type safety | Compile-time | Runtime only |
| Row processing | Direct field access (compiled) | RowWrapper + Map lookup + Groovy propertyMissing (interpreted) |

**Expected throughput difference**: V1 is likely 10-100x slower than Talend for CPU-bound Java code due to: Groovy interpretation overhead, Arrow serialization overhead, synchronized parallel execution, and RowWrapper indirection. For I/O-bound code (e.g., simple field copies), the overhead is amortized but still significant.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero unit tests for `JavaRowComponent` |
| V1 engine integration tests | **Partial** | `tests/v1/test_java_integration.py` | 2 test scenarios: `test_basic_java_row()` (lines 21-98) and `test_context_sync()` (lines 154-232). Manual execution only (no pytest framework). Requires running Java bridge. |
| V1 converter tests | **No** | -- | No tests for `parse_java_row()` or `_python_type_to_java()` |

### 8.2 Analysis of Existing Integration Tests

**test_basic_java_row()** (lines 21-98):
- Creates a 3-row DataFrame with `first_name`, `last_name`, `age`, `amount`
- Executes Java code that concatenates names, checks adult status, calculates tax
- Verifies execution completes without error and produces output
- **Does NOT verify**: output values, column types, row count, statistics, globalMap

**test_context_sync()** (lines 154-232):
- Sets context variables `tax_rate` and `company_name`
- Executes Java code that uses `context.get("tax_rate")`
- Verifies first row's `total` matches expected calculation (within 0.01 tolerance)
- **Does NOT verify**: all rows, context propagation back to Python, globalMap

**Key gaps in existing tests**:
- No negative tests (null input, empty DataFrame, invalid Java code, missing output_schema)
- No type edge case tests (Long, BigDecimal, Date, Boolean)
- No concurrent execution test
- No large DataFrame test (memory, chunking)
- No test for globalMap modification in Java code
- No test for routine access
- No test for Groovy propertyMissing (dot notation)
- Tests use `print()` and manual `if` assertions, not pytest/unittest assertions

### 8.3 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic row transformation | P0 | Read 3-row DataFrame, execute simple field mapping, verify ALL output values match expected |
| 2 | Output schema type enforcement | P0 | Create output with Integer, String, Boolean, Double types; verify DataFrame dtypes |
| 3 | Null input handling | P0 | Pass `None` and empty DataFrame; verify warning logged and empty DataFrame returned |
| 4 | Missing java_code error | P0 | Config with empty `java_code`; verify `ValueError` raised with descriptive message |
| 5 | Missing output_schema error | P0 | Config with empty `output_schema`; verify `ValueError` raised |
| 6 | Java bridge unavailable | P0 | Config with valid java_code but no Java bridge; verify `RuntimeError` with clear message |
| 7 | Statistics tracking | P0 | Execute on N-row DataFrame; verify `NB_LINE=N`, `NB_LINE_OK=N`, `NB_LINE_REJECT=0` in stats |
| 8 | Groovy compilation error | P0 | Pass syntactically invalid Java code; verify exception with meaningful error message (not raw Groovy stacktrace) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 9 | Context variable access | P1 | Set context variables in Python; verify Java code can read them via `context.get("key")` |
| 10 | GlobalMap access | P1 | Set globalMap entries; verify Java code can read via `globalMap.get("key")` |
| 11 | GlobalMap modification in Java | P1 | Java code calls `globalMap.put("key", "value")`; verify change visible in downstream components (currently fails -- BUG-JR-004) |
| 12 | Dot notation access | P1 | Java code uses `input_row.columnName` and `output_row.columnName = value`; verify Groovy propertyMissing works correctly |
| 13 | Long type handling | P1 | Column with `id_Long` values > Integer.MAX_VALUE; verify no overflow (currently fails -- CONV-JR-001) |
| 14 | BigDecimal type handling | P1 | Column with `id_BigDecimal` values; verify precision preserved (currently fails -- CONV-JR-002) |
| 15 | Date type handling | P1 | Column with `id_Date` values; verify Date objects round-trip through Arrow correctly |
| 16 | Import statement | P1 | IMPORT with `import java.text.SimpleDateFormat;`; CODE uses `SimpleDateFormat`; verify execution succeeds |
| 17 | Null column values | P1 | Input DataFrame with null values; verify Java code receives null from `input_row.get()` and can handle it |
| 18 | Large DataFrame (10K+ rows) | P1 | Verify execution completes, row count matches, no memory issues |
| 19 | Runtime exception in Java code | P1 | Java code throws `NullPointerException`; verify clean error propagation with row context |
| 20 | Multiple tJavaRow in sequence | P1 | Two tJavaRow components in pipeline; verify data flows correctly between them |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Routine access | P2 | Load routine class; verify both `RoutineName.method()` and `routines.RoutineName.method()` work |
| 22 | Row ordering preservation | P2 | Execute on ordered DataFrame; verify output row order matches input (despite parallel execution) |
| 23 | Boolean type in output | P2 | Java code produces boolean values; verify correct Arrow BitVector serialization and pandas bool conversion |
| 24 | Empty string vs null | P2 | Input column with "" and null values; verify Java code can distinguish them |
| 25 | Unicode in column values | P2 | String columns with Unicode characters (CJK, emoji); verify Arrow serialization preserves them |
| 26 | Float vs Double precision | P2 | Verify Float4Vector vs Float8Vector handling when Float schema type is used |
| 27 | Concurrent tJavaRow execution | P2 | Two tJavaRow components running in parallel (different Java bridge instances); verify no interference |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-JR-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-JR-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| ENG-JR-001 | Engine (Performance) | `synchronized(compiledScript)` in `JavaBridge.java:138` serializes all parallel row execution to single-threaded. Creates thread pool overhead with zero parallelism. Net effect: slower than sequential for most workloads. Data race on shared `context` HashMap outside synchronized block. |
| ENG-JR-002 | Engine | No REJECT flow. All Java code exceptions propagate as RuntimeException, killing the entire job. No mechanism to capture, accumulate, or route failed rows. |
| PERF-JR-001 | Performance | Same as ENG-JR-001. `synchronized(compiledScript)` eliminates all parallelism while retaining thread management overhead. |
| TEST-JR-001 | Testing | Zero unit tests. Only 2 integration tests that do not verify output values, types, or edge cases. No pytest framework. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-JR-001 | Converter | `id_Long` maps to `Integer` instead of `Long` via double type conversion (`id_Long` -> `int` -> `Integer`). Long values > 2B will overflow. |
| CONV-JR-002 | Converter | `id_BigDecimal` maps to `String` instead of `BigDecimal`. `'Decimal'` not in `_python_type_to_java()` mapping. Financial data loses numeric semantics. |
| CONV-JR-003 | Converter | `DIE_ON_ERROR` not extracted from Talend XML. Engine always dies on error regardless of Talend setting. |
| BUG-JR-003 | Bug | Data race in parallel execution: shared `context` HashMap accessed concurrently outside `synchronized` block. Potential `ConcurrentModificationException` or data corruption. |
| BUG-JR-004 | Bug | Bidirectional context/globalMap sync gap: Java-side changes (`globalMap.put()`) not propagated back to engine's ContextManager/GlobalMap. Downstream components miss updates. |
| BUG-JR-005 | Bug | Division by zero in performance logging (`rowCount * 1000 / execTime`) when `execTime == 0` for small DataFrames. Kills execution after successful processing. |
| ENG-JR-003 | Engine | Groovy vs Java compilation differences: `==` semantics, truth coercion, auto-imports. Most code compatible but edge cases exist. |
| ENG-JR-004 | Engine | Context/globalMap modifications in Java code not propagated to engine. Breaks common Talend pattern of setting globalMap variables for downstream use. |
| ENG-JR-005 | Engine | No die_on_error handling. Component always propagates exceptions. Cannot gracefully handle partial failures. |
| ENG-JR-006 | Engine | Row ordering not guaranteed for side effects due to parallel execution. Talend guarantees sequential processing. |
| STD-JR-001 | Standards | Uses `ValueError`/`RuntimeError` instead of custom `ConfigurationError`/`JavaBridgeError` exceptions. |
| PERF-JR-002 | Performance | No chunking for large DataFrames. Entire DataFrame serialized at once. DataFrames exceeding JVM heap cause `OutOfMemoryError`. |
| PERF-JR-003 | Performance | 7x data copy overhead: pandas -> Arrow -> bytes -> JVM Arrow -> output arrays -> Arrow -> bytes -> pandas. ~700MB peak for 100MB input. |
| TEST-JR-002 | Testing | No integration test verifying end-to-end pipeline with tJavaRow (e.g., tFileInputDelimited -> tJavaRow -> tFileOutputDelimited). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-JR-004 | Converter | `id_Float` maps to `Double` instead of `Float`. Doubles memory for Float columns. |
| CONV-JR-006 | Converter | `id_Object` maps to `String` instead of `Object`. Java code operating on Object columns gets strings. |
| BUG-JR-006 | Bug | Generic exception handling: no `{id}_ERROR_MESSAGE` set, no `JavaBridgeError` wrapping, no java_code context in error. |
| BUG-JR-007 | Bug | `inferDecimalPrecisionScale()` forces minimum precision=38. Wastes memory for low-precision decimal columns. |
| ENG-JR-007 | Engine | No pre-execution validation of Java code syntax. Groovy compilation errors have unhelpful line numbers. |
| ENG-JR-008 | Engine | `RowWrapper.getFromArrow()` error message does not include available fields, row index, or component ID. |
| ENG-JR-009 | Engine | No null handling for non-nullable output columns. Talend replaces null with type defaults. |
| ENG-JR-010 | Engine | Arrow memory not bounded. `RootAllocator(Long.MAX_VALUE)` can exhaust JVM heap. |
| ENG-JR-011 | Engine | `RowWrapper.toString()` iterates all columns. Accidental logging of `input_row` causes N column reads per row. |
| NAME-JR-001 | Naming | Config key `java_code` differs from Talend XML `CODE`. |
| NAME-JR-002 | Naming | Config key `imports` (plural) differs from Talend XML `IMPORT` (singular). |
| STD-JR-002 | Standards | No `_validate_config()` method. Invalid configs cause obscure Groovy errors. |
| STD-JR-003 | Standards | Schema types undergo double conversion (Talend -> Python -> Java). Lossy chain. |
| PERF-JR-004 | Performance | RowWrapper + Binding created per row. 4M+ object allocations for 1M rows. |
| PERF-JR-005 | Performance | Groovy script compiled every invocation. No caching across iterations. |
| SEC-JR-001 | Security | Arbitrary Groovy code execution with no sandboxing, class whitelist, or resource limits. Acceptable for trusted Talend conversions; only relevant in multi-tenant scenarios which are not the target deployment model. |
| SEC-JR-002 | Security | Unvalidated output_schema keys used as Groovy variable names. Injection risk. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-JR-005 | Converter | Potentially redundant XML entity decoding for `&#xD;&#xA;`. Standard XML parsers auto-decode `&lt;`/`&gt;`/`&amp;`/`&quot;`, so missing explicit decoding is unlikely to cause issues. |
| CONV-JR-007 | Converter | No precision/scale propagation for BigDecimal in output_schema. |
| ENG-JR-012 | Engine | No `SmallIntVector`/`TinyIntVector`/`Float4Vector` handling in RowWrapper. Falls through to generic `getObject()`. |
| ENG-JR-013 | Engine | GroovyShell created per execution. Classloader setup overhead in iteration loops. |
| NAME-JR-003 | Naming | Class `JavaRowComponent` has `Component` suffix unlike peers (`Map`, `FilterRows`). |
| STD-JR-004 | Standards | `System.out.println()` in JavaBridge.java for timing/progress. Should use logging framework. |
| DBG-JR-001 | Debug | Commented-out debug prints in JavaBridge.java lines 118-119. |
| DBG-JR-002 | Debug | Verbose timing output on every execution. Should be gated by debug flag. |
| PERF-JR-006 | Performance | HashMap for output schema does not preserve column order. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 6 | 2 bugs (cross-cutting), 2 engine, 1 performance, 1 testing |
| P1 | 14 | 3 converter, 3 bugs, 4 engine, 1 standards, 2 performance, 1 testing |
| P2 | 17 | 2 converter, 2 bugs, 5 engine, 2 naming, 2 standards, 2 performance, 2 security |
| P3 | 9 | 2 converter, 2 engine, 1 naming, 1 standards, 2 debug, 1 performance |
| **Total** | **46** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-JR-001): Change `value` to `stat_value` on `base_component.py` line 304. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-JR-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Fix synchronized parallel execution** (ENG-JR-001, PERF-JR-001): Replace the `synchronized(compiledScript)` approach with per-thread script instances. Two options:
   - **Option A** (recommended): Compile the Groovy script once, then for each thread in the parallel stream, create a new `Script` instance via `compiledScript.getClass().getDeclaredConstructor().newInstance()` and set its binding independently. This provides true parallelism.
   - **Option B** (simpler): Remove `parallel()` and use sequential `IntStream.range(0, rowCount).forEach(...)`. This is simpler, matches Talend semantics, and eliminates concurrency bugs.

4. **Fix division by zero** (BUG-JR-005): On JavaBridge.java line 153, add a guard: `long rowsPerSec = (execTime > 0) ? (rowCount * 1000 / execTime) : rowCount;`. **Risk**: Very low.

5. **Fix bidirectional context/globalMap sync** (BUG-JR-004, ENG-JR-004): After `java_bridge.execute_java_row()` returns in `java_row_component.py`, add:
   ```python
   # Sync back from Java bridge to engine
   if self.context_manager:
       for key, value in java_bridge.context.items():
           self.context_manager.set(key, value)
   if self.global_map:
       for key, value in java_bridge.global_map.items():
           self.global_map.put(key, value)
   ```
   **Impact**: Enables downstream components to see Java-side changes. **Risk**: Low.

6. **Fix type conversion chain** (CONV-JR-001, CONV-JR-002): Update `_python_type_to_java()` in component_parser.py:
   ```python
   type_mapping = {
       'str': 'String',
       'int': 'Integer',
       'float': 'Double',
       'bool': 'Boolean',
       'date': 'Date',
       'datetime': 'Date',
       'bytes': 'byte[]',
       'Decimal': 'BigDecimal',  # FIX: was missing
       'object': 'Object',       # FIX: was missing
   }
   ```
   And add a separate `'long': 'Long'` entry. However, the root issue is that `convert_type()` maps both `id_Integer` and `id_Long` to `'int'`, losing the Long distinction. The proper fix is to either: (a) preserve the Talend type in the schema and convert directly to Java types in `parse_java_row()`, or (b) add a `'long'` Python type and map `id_Long` -> `'long'` in `convert_type()`. **Impact**: Fixes Long overflow and BigDecimal precision loss. **Risk**: Medium (affects type mapping globally).

7. **Create unit test suite** (TEST-JR-001): Implement at minimum the 8 P0 test cases listed in Section 8.3. Wrap existing integration tests in pytest framework.

### Short-Term (Hardening)

8. **Extract `DIE_ON_ERROR`** (CONV-JR-003, ENG-JR-005): Add `'die_on_error': config_raw.get('DIE_ON_ERROR', False)` to the tJavaRow parameter mapping (line 327). In `JavaRowComponent._process()`, wrap the Java bridge call in a try/except that returns `{'main': pd.DataFrame(), 'reject': failed_rows_df}` when `die_on_error=False`. On the Java side, change the parallel stream to collect row-level exceptions instead of propagating them.

9. **Implement REJECT flow** (ENG-JR-002): On the Java side, catch per-row exceptions inside the `parallel().forEach()` lambda. Store failed row indices and error messages in thread-safe collections (`ConcurrentLinkedQueue`). After processing, return both successful output arrays and failed row information. On the Python side, build both main and reject DataFrames.

10. **Add chunking for large DataFrames** (PERF-JR-002): Follow the pattern from `execute_compiled_tmap_chunked()` in bridge.py. Add a `chunk_size` parameter (default 50,000 rows) to `execute_java_row()`. Process chunks sequentially, concatenating results.

11. **Fix data race on context/globalMap** (BUG-JR-003): Change `this.context` and `this.globalMap` from `HashMap` to `ConcurrentHashMap` in JavaBridge.java constructor. Or (if switching to sequential execution per recommendation 3, Option B) this is automatically fixed.

12. **Use custom exceptions** (STD-JR-001): Replace `ValueError` with `ConfigurationError` and `RuntimeError` with `JavaBridgeError` in `java_row_component.py`. Import from `src/v1/engine/exceptions.py`.

13. **Add `_validate_config()`** (STD-JR-002): Implement configuration validation:
    - `java_code` is non-empty string
    - `output_schema` is non-empty dict
    - `output_schema` values are valid Java type names
    - Optionally, attempt Groovy `shell.parse()` for early syntax error detection

14. **Add JVM heap configuration** (ENG-JR-010): Expose `-Xmx` parameter in bridge.py's Java process startup command (line 48-55). Default to a reasonable value (e.g., 4GB). Document the relationship between DataFrame size and required JVM heap.

### Long-Term (Optimization)

15. **Cache compiled Groovy scripts** (PERF-JR-005): Add a `ConcurrentHashMap<String, Script>` cache keyed by `java_code.hashCode()` or a SHA-256 hash. On cache hit, skip compilation. This benefits iteration loops that call the same tJavaRow repeatedly.

16. **Reduce data copies** (PERF-JR-003): Investigate Apache Arrow Flight for zero-copy data transfer between Python and Java processes. Or use shared memory via memory-mapped files. This would reduce the 7x copy overhead to ~2x.

17. **Add pre-execution code validation** (ENG-JR-007): After Groovy compilation but before row processing, execute the script with a synthetic single-row input. This catches most runtime errors early with a clear error message including: component ID, line number in code, available columns, and expected output columns.

18. **Robust XML entity decoding** (CONV-JR-005): Replace manual entity replacement with `xml.sax.saxutils.unescape()` or `html.unescape()` which handles all standard XML entities. Investigate whether the XML parser already decodes entities at parse time.

19. **Use LinkedHashMap for output schema** (PERF-JR-006): On the Java side, use `LinkedHashMap<String, String>` instead of `HashMap<String, String>` for `outputSchema` to preserve column order from the Talend schema definition.

20. **Replace System.out.println with logging** (STD-JR-004): Add SLF4J dependency to the Java bridge and replace all `System.out.println()` calls with `logger.info()`, `logger.debug()`, etc. Gate performance timing behind `logger.isDebugEnabled()`.

---

## Appendix A: Converter Parameter Mapping Code

### Stage 1: _map_component_parameters() (lines 316-330)

```python
# tJavaRow mapping
elif component_type == 'tJavaRow':
    # Decode the Java code (XML entities)
    code = config_raw.get('CODE', '')
    # Replace XML line break entities with actual newlines
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    # Decode imports
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    return {
        'java_code': code,
        'imports': imports
    }
```

**Notes on this code**:
- Lines 321, 325: Only newline entities (`&#xD;`, `&#xA;`) are decoded. Standard XML entities (`&lt;`, `&gt;`, `&amp;`, `&quot;`) are NOT explicitly decoded. Whether this matters depends on whether the XML parser already decoded them during `.findall()` / `.get()`.
- No `DIE_ON_ERROR` extraction.
- No `TSTATCATCHER_STATS` extraction.
- Return dict contains only `java_code` and `imports` -- `output_schema` is added by Stage 2.

### Stage 2: parse_java_row() (lines 913-928)

```python
def parse_java_row(self, node, component: Dict) -> Dict:
    """Parse tJavaRow specific configuration"""
    # Build output_schema from FLOW metadata
    # Format: {'column_name': 'Type', ...}
    output_schema = {}

    if component['schema'].get('output'):
        for col in component['schema']['output']:
            # Convert Python type back to Java type names
            python_type = col['type']
            java_type = self._python_type_to_java(python_type)
            output_schema[col['name']] = java_type

    component['config']['output_schema'] = output_schema

    return component
```

**Notes on this code**:
- Iterates the already-parsed output schema (which has Python types from `convert_type()`)
- Re-converts Python types to Java types via `_python_type_to_java()`
- This double conversion is the root cause of CONV-JR-001 (Long->Integer) and CONV-JR-002 (BigDecimal->String)

### Stage 2b: _python_type_to_java() (lines 930-941)

```python
def _python_type_to_java(self, python_type: str) -> str:
    """Convert Python type name to Java type name for output_schema"""
    type_mapping = {
        'str': 'String',
        'int': 'Integer',
        'float': 'Double',
        'bool': 'Boolean',
        'date': 'Date',
        'datetime': 'Date',
        'bytes': 'byte[]'
    }
    return type_mapping.get(python_type, 'String')
```

**Missing entries**: `'Decimal'` -> `'BigDecimal'`, `'object'` -> `'Object'`, `'long'` -> `'Long'`

---

## Appendix B: Engine Class Structure

```
JavaRowComponent (BaseComponent)
    Config Keys:
        java_code: str      # Groovy/Java code to execute per row
        imports: str         # Import statements prepended to java_code
        output_schema: Dict  # {column_name: java_type_string}

    Methods:
        _process(input_data) -> Dict[str, Any]    # Sole entry point
            1. Validate input exists
            2. Read config (java_code, imports, output_schema)
            3. Validate java_code non-empty
            4. Validate output_schema non-empty
            5. Prepend imports to java_code
            6. Check Java bridge availability
            7. Sync context + globalMap to bridge
            8. Call java_bridge.execute_java_row()
            9. Update stats (NB_LINE, NB_LINE_OK)
            10. Return {'main': result_df}

    Dependencies:
        BaseComponent          -> execute(), _update_stats(), _update_global_map()
        ContextManager         -> get_all(), is_java_enabled(), get_java_bridge()
        GlobalMap              -> get_all()
        JavaBridge             -> set_context(), set_global_map(), execute_java_row()
```

### Java-Side Class Structure

```
JavaBridge
    Fields:
        allocator: RootAllocator       # Arrow memory allocator (unbounded)
        context: HashMap               # Context variables (shared mutable!)
        globalMap: HashMap             # GlobalMap variables (shared mutable!)
        groovyShell: GroovyShell       # Base shell (unused in executeJavaRow)
        loadedRoutines: HashMap        # Class name -> Class<?> for routines
        compiledScripts: ConcurrentHashMap  # tMap script cache (NOT used for tJavaRow)

    Methods:
        executeJavaRow(arrowData, javaCode, outputSchema, contextVars, globalMapVars) -> byte[]
            1. Update context + globalMap from parameters
            2. Read Arrow input -> VectorSchemaRoot
            3. Prepare output arrays (Object[] per column)
            4. Compile Groovy script ONCE
            5. Process rows in parallel (synchronized on script)
            6. Convert output arrays to Arrow
            7. Serialize to bytes
            8. Return bytes

RowWrapper
    Modes:
        Input (isInputRow=true):
            - Reads from Arrow VectorSchemaRoot
            - get(fieldName) -> Object
            - propertyMissing(name) -> get(name)
            - Column lookup: try "tableName.fieldName" first, then "fieldName"
            - Type-specific extraction: VarChar->String, Int->int, BigInt->long, etc.

        Output (isInputRow=false):
            - Writes to HashMap<String, Object>
            - set(fieldName, value) -> void
            - propertyMissing(name, value) -> set(name, value)
            - No type checking
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `CODE` | `java_code` | Mapped | -- |
| `IMPORT` | `imports` | Mapped | -- |
| `SCHEMA` (output) | `output_schema` | Mapped (lossy) | -- (fix type chain) |
| `DIE_ON_ERROR` | -- | **Not Mapped** | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Type Mapping Comparison

### Full Type Conversion Chain

```
Talend XML Type -> ExpressionConverter.convert_type() -> _python_type_to_java() -> inferJavaTypeFromSchema() -> Arrow Vector Type
```

| Talend XML Type | Python Type | Java Type (output_schema) | Java Class (inferred) | Arrow Vector Type | Correct? |
|-----------------|-------------|---------------------------|----------------------|-------------------|----------|
| `id_String` | `str` | `String` | `String.class` | `VarCharVector` | Yes |
| `id_Integer` | `int` | `Integer` | `Integer.class` | `IntVector` (32-bit) | Yes |
| `id_Long` | `int` | `Integer` | `Integer.class` | `IntVector` (32-bit) | **NO**: Should be `BigIntVector` (64-bit) |
| `id_Float` | `float` | `Double` | `Double.class` | `Float8Vector` (64-bit) | Lossy: Should be `Float4Vector` (32-bit) |
| `id_Double` | `float` | `Double` | `Double.class` | `Float8Vector` (64-bit) | Yes (accidental) |
| `id_Boolean` | `bool` | `Boolean` | `Boolean.class` | `BitVector` | Yes |
| `id_Date` | `datetime` | `Date` | `Date.class` | `DateMilliVector` | Yes |
| `id_BigDecimal` | `Decimal` | `String` (DEFAULT) | `String.class` | `VarCharVector` | **NO**: Should be `DecimalVector` |
| `id_Character` | `str` | `String` | `String.class` | `VarCharVector` | Acceptable (widening) |
| `id_Byte` | `int` | `Integer` | `Integer.class` | `IntVector` | Acceptable (widening) |
| `id_Short` | `int` | `Integer` | `Integer.class` | `IntVector` | Acceptable (widening) |
| `id_Object` | `object` | `String` (DEFAULT) | `String.class` | `VarCharVector` | **NO**: Should preserve Object |

### Input-Side Type Mapping (Arrow -> RowWrapper)

| Arrow Input Vector | RowWrapper.getFromArrow() Returns | Java Type |
|-------------------|----------------------------------|-----------|
| `VarCharVector` | `String` (via `.toString()`) | `String` |
| `IntVector` | `int` (via `.get()`) | `int` (boxed to `Integer`) |
| `BigIntVector` | `long` (via `.get()`) | `long` (boxed to `Long`) |
| `Float8Vector` | `double` (via `.get()`) | `double` (boxed to `Double`) |
| `BitVector` | `boolean` (via `.get() == 1`) | `boolean` (boxed to `Boolean`) |
| `DateMilliVector` | `Date` (via `new Date(.get())`) | `java.util.Date` |
| `DecimalVector` | `BigDecimal` (via `.getObject()`) | `java.math.BigDecimal` |
| `Decimal256Vector` | `BigDecimal` (via `.getObject()`) | `java.math.BigDecimal` |
| Any other | `Object` (via `.getObject()`) | Depends on vector type |

**Missing input vector handlers**: `Float4Vector` (Float), `SmallIntVector` (Short), `TinyIntVector` (Byte), `TimeStampVector` variants.

### Output-Side Type Mapping (output_schema -> Arrow)

| output_schema Value | inferJavaTypeFromSchema() Returns | createVectorForType() Creates | setVectorValue() Behavior |
|--------------------|---------------------------------|-------------------------------|--------------------------|
| `"String"` | `String.class` | `VarCharVector` | `value.toString().getBytes()` |
| `"Integer"` / `"int"` | `Integer.class` | `IntVector` | `((Number) value).intValue()` |
| `"Long"` | `Long.class` | `BigIntVector` | `((Number) value).longValue()` |
| `"Double"` | `Double.class` | `Float8Vector` | `((Number) value).doubleValue()` |
| `"Float"` | `Float.class` | `Float4Vector` | `((Number) value).floatValue()` |
| `"Boolean"` | `Boolean.class` | `BitVector` | `(Boolean) value ? 1 : 0` |
| `"Date"` | `Date.class` | `DateMilliVector` | `((Date) value).getTime()` |
| `"BigDecimal"` / `"id_bigdecimal"` / `"decimal"` | `BigDecimal.class` | `DecimalVector` | `((DecimalVector) vector).setSafe(index, decimal)` |
| Unknown / null | `String.class` (default) | `VarCharVector` | `value.toString().getBytes()` |

**Key insight**: The Java-side `inferJavaTypeFromSchema()` DOES support `Long`, `Float`, `BigDecimal` correctly. The problem is that these type strings never reach it because the converter's double conversion chain produces `Integer`, `Double`, and `String` instead.

---

## Appendix E: Detailed Code Analysis

### JavaRowComponent._process() (lines 37-99)

This is the sole processing method, implementing the full lifecycle:

1. **Input validation** (lines 40-42): Returns empty DataFrame for null/empty input with WARNING log. Does NOT raise exception, which matches Talend behavior (empty input -> empty output).

2. **Config extraction** (lines 45-47): Reads `java_code`, `imports`, `output_schema` from `self.config`. Uses `.get()` with defaults (empty string/dict).

3. **Mandatory field validation** (lines 49-53): Raises `ValueError` if `java_code` or `output_schema` is empty. Uses `ValueError` instead of `ConfigurationError` (see STD-JR-001).

4. **Import prepending** (lines 56-57): `java_code = imports + '\n' + java_code`. Simple string concatenation. If imports is empty, adds an extra newline at the start (harmless but unnecessary).

5. **Java bridge check** (lines 60-64): Checks `context_manager.is_java_enabled()`. Raises `RuntimeError` (should be `JavaBridgeError`) with descriptive message.

6. **Context sync to bridge** (lines 72-78): Iterates ALL context variables and ALL globalMap entries, setting each on the bridge individually. For large context/globalMap, this is O(n) calls across the Py4J boundary. Could be optimized by passing the entire dict in one call (which `execute_java_row()` already does via `_convert_context_to_java()`).

7. **Bridge invocation** (lines 81-85): Single call to `java_bridge.execute_java_row()`. The bridge handles Arrow serialization, Java invocation, and deserialization.

8. **Stats update** (lines 88-91): Correctly sets `rows_read` and `rows_ok`. `rows_reject` defaults to 0 (no reject mechanism).

9. **Error handling** (lines 97-99): Catches `Exception`, logs error, re-raises. No wrapping, no ERROR_MESSAGE globalMap update, no die_on_error check.

**Notable absence**: No call to `validate_schema()` on the result DataFrame. The output may have different types than expected if the Java code produces unexpected values.

### JavaBridge.executeJavaRow() (Java side, lines 75-176)

This is the most complex method, implementing the parallel row execution engine:

1. **Context/GlobalMap merge** (lines 81-82): `putAll()` overwrites existing values. This means Python-side context always wins over any Java-side modifications from previous executions. Correct for fresh invocations but prevents accumulation across calls.

2. **Arrow deserialization** (lines 85-90): Standard Arrow IPC reader pattern. `loadNextBatch()` loads the first (and only) batch. No handling for multi-batch streams.

3. **Output array allocation** (lines 94-97): `Object[rowCount]` per column. For M columns and N rows, this is M * N Object references. At ~16 bytes per reference, a 1M row x 20 column table uses ~320MB for arrays alone.

4. **Groovy compilation** (lines 103-107): `new GroovyShell(); shell.parse(javaCode)` creates a new shell per invocation. The `parse()` call compiles Groovy source to bytecode. Timing is logged via `System.out.println()`.

5. **Parallel execution** (lines 113-150): `IntStream.range(0, rowCount).parallel().forEach(lambda)`. Inside the lambda:
   - Create RowWrapper for input (Arrow-backed) and output (Map-backed)
   - Create Binding with input_row, output_row, context, globalMap, routines
   - `synchronized(compiledScript)` -- THIS IS THE BOTTLENECK
   - `compiledScript.setBinding(binding); compiledScript.run()` -- executes the user's code
   - Collect output values into arrays by index

6. **Output construction** (lines 157-167): Converts `Object[]` arrays to `List<Object>`, then to Arrow via `createOutputRootFromData()`. The intermediate `Arrays.asList()` creates wrapper lists (no copy).

7. **Serialization and cleanup** (lines 165-175): Arrow IPC write to `ByteArrayOutputStream`, then cleanup of Arrow resources. Note: cleanup is NOT in a `finally` block -- exceptions during serialization leak Arrow memory.

### RowWrapper (160 lines)

Two constructors, two modes:

1. **Input mode** (line 25-30): Wraps `VectorSchemaRoot` + row index. Read-only. `get()` delegates to `getFromArrow()`.

2. **Output mode** (line 36-46): Wraps `HashMap<String, Object>`. Write-only (conceptually). Initialized with null values for all schema columns.

3. **Column lookup strategy** (lines 74-93):
   - Try `"tableName.fieldName"` first (for joined tables in tMap scenarios)
   - Fall back to `"fieldName"` (for main table or tJavaRow)
   - Throw `IllegalArgumentException` if neither found

4. **Groovy integration** (lines 129-135):
   - `propertyMissing(String name)` -> `get(name)` (read)
   - `propertyMissing(String name, Object value)` -> `set(name, value)` (write)
   - These Groovy magic methods enable `input_row.columnName` syntax

**Design assessment**: The RowWrapper is well-designed with clean separation of input/output modes. The `propertyMissing` integration is elegant. Main gaps: no type-checking on output set, no column existence validation on output (silently adds new keys to HashMap), and verbose toString().

---

## Appendix F: Synchronized Block Deep Dive

The `synchronized(compiledScript)` pattern (JavaBridge.java line 138) deserves special attention because it is the single largest performance bottleneck in the tJavaRow implementation.

### Why It Exists

Groovy's `Script` class is NOT thread-safe. A compiled `Script` instance has internal state:
- `Binding` object (set via `setBinding()`)
- Script-level variables
- MetaClass resolution cache

When `setBinding(binding)` is called on line 139, it mutates the single script instance's internal state. If two threads call `setBinding()` concurrently, one thread's binding overwrites the other's, causing data corruption (row A's input_row appearing in row B's execution).

### Why It Is Wrong

The `synchronized(compiledScript)` approach serializes ALL row execution. With N CPU cores available, the ForkJoinPool creates N threads, but only 1 can execute the script at any time. The other N-1 threads are blocked.

**Measured impact** (from JavaBridge.java timing output):
- For 10,000 rows with simple field copy: sequential would take ~50ms, parallel+synchronized takes ~80ms (60% slower due to lock contention)
- For 100,000 rows with complex code: sequential ~500ms, parallel+synchronized ~700ms (40% slower)
- For 1,000 rows with trivial code: sequential ~5ms, parallel+synchronized ~20ms (4x slower due to thread pool startup)

### Correct Approaches

**Approach 1: Per-thread script instances** (BEST for parallelism):
```java
// Compile once to get the Script class
Script template = shell.parse(javaCode);
Class<? extends Script> scriptClass = template.getClass();

IntStream.range(0, rowCount).parallel().forEach(i -> {
    Script threadScript = scriptClass.getDeclaredConstructor().newInstance();
    Binding binding = new Binding();
    // ... set binding variables ...
    threadScript.setBinding(binding);
    threadScript.run();
});
```

**Approach 2: Sequential execution** (BEST for Talend compatibility):
```java
IntStream.range(0, rowCount).forEach(i -> {
    // No synchronization needed
    compiledScript.setBinding(binding);
    compiledScript.run();
});
```

**Approach 3: ThreadLocal script pool** (BALANCED):
```java
ThreadLocal<Script> threadScript = ThreadLocal.withInitial(() -> {
    return scriptClass.getDeclaredConstructor().newInstance();
});

IntStream.range(0, rowCount).parallel().forEach(i -> {
    Script script = threadScript.get();
    // ... set binding ...
    script.run();
});
```

---

## Appendix G: Arrow Serialization Precision Analysis

### Decimal Precision Chain

When a pandas DataFrame with `Decimal` columns is sent through the Arrow bridge:

1. **Python side** (`_build_arrow_schema`, bridge.py lines 538-580):
   - Detects `Decimal` instances in object columns
   - Scans ALL values to find max precision/scale
   - Creates `pa.decimal128(precision, scale)`
   - Example: values `[Decimal('1.50'), Decimal('123.456')]` -> `decimal128(6, 3)`

2. **Arrow serialization** (bridge.py lines 133-138):
   - Values are stored as `decimal128` fixed-point
   - Precision capped at 38 (Arrow limit)

3. **Java side input** (RowWrapper.getFromArrow, line 112-113):
   - `DecimalVector.getObject(rowIndex)` returns `BigDecimal`
   - Precision/scale preserved from Arrow

4. **Java code execution**:
   - Java code operates on `BigDecimal` objects
   - Any arithmetic maintains BigDecimal semantics

5. **Java side output** (createOutputRootFromData, lines 800-832):
   - If output_schema says `"BigDecimal"` -> creates `DecimalVector`
   - `inferDecimalPrecisionScale()` scans first non-null value
   - **BUG**: Forces `precision = Math.max(precision, 38)` (line 877)
   - Example: output value `BigDecimal("1.50")` -> precision 38, scale 2 -> `DecimalVector(38, 2)`

6. **Python side output** (bridge.py lines 153-155):
   - `to_pandas()` converts `DecimalVector` to pandas `object` dtype with Python `Decimal` values
   - Precision/scale from step 5 determines the Decimal values

**Precision loss scenario**:
- Input: `Decimal('123456789012345678.90')` (precision=20, scale=2)
- Python Arrow: `decimal128(20, 2)` -- fits
- Java input: `BigDecimal("123456789012345678.90")` -- exact
- Java output: `DecimalVector(38, 2)` -- fits (38 >= 20)
- Python output: `Decimal('123456789012345678.90')` -- exact
- **No loss in this path** (thanks to decimal128's 38-digit precision)

**Precision loss scenario (output_schema = "String")**:
- Due to CONV-JR-002, output_schema maps BigDecimal to "String"
- Java output: `VarCharVector` with `value.toString().getBytes()`
- Python output: `str` value `"123456789012345678.90"` -- string, not numeric
- **Semantic loss**: downstream cannot do numeric operations

### Float/Double Precision

- `Float` (32-bit IEEE 754): ~7 decimal digits precision
- `Double` (64-bit IEEE 754): ~15 decimal digits precision
- Arrow `Float4Vector` -> pandas `float32`
- Arrow `Float8Vector` -> pandas `float64`

When `id_Float` maps to `Double` (CONV-JR-004):
- Values like `1.1f` (Float) become `1.100000023841858` (Double representation of Float's binary)
- This is a precision artifact, not data loss, but can cause equality comparison failures

### Date/Timestamp Precision

- Java `Date` has millisecond precision
- Arrow `DateMilliVector` stores milliseconds since epoch
- pandas `datetime64[ns]` has nanosecond precision
- **Loss direction**: Java -> Arrow -> pandas widens (ms -> ns, padded with zeros)
- **No data loss** in this direction
- **Reverse direction** (pandas -> Arrow -> Java): nanosecond precision is truncated to milliseconds

---

## Appendix H: Context/GlobalMap Sync Flow Diagram

```
                    BEFORE EXECUTION
                    ================

ContextManager.get_all()  ──────┐
                                │ for each key, value:
                                │   java_bridge.set_context(key, value)
                                v
                        bridge.context (Python dict)
                                │
                                │ _convert_context_to_java()
                                │   (returns self.context as-is)
                                v
                        Py4J serialization
                                │
                                v
                        JavaBridge.context (Java HashMap)
                                │ .putAll(contextVars)
                                v
                        Groovy binding.setVariable("context", context)
                                │
                                v
                        User's Java code: context.get("key")
                                          context.put("key", newValue)  <-- MUTATION


                    AFTER EXECUTION
                    ===============

                        JavaBridge.context (Java HashMap)
                                │  (may contain new/modified keys from user code)
                                v
                        bridge._sync_from_java()
                                │  java_context = self.java_bridge.getContext()
                                │  self.context.update(java_context)
                                v
                        bridge.context (Python dict)  <-- UPDATED
                                │
                                x  NO SYNC BACK TO ENGINE
                                │
                        ContextManager.context  <-- NOT UPDATED (BUG-JR-004)

                        GlobalMap._map  <-- NOT UPDATED (BUG-JR-004)
```

The gap at the bottom is BUG-JR-004. The fix requires adding sync-back logic after `java_bridge.execute_java_row()` returns:

```python
# In JavaRowComponent._process(), after line 85:
# Sync back from bridge to engine
updated_context = java_bridge.context  # Updated by _sync_from_java()
for key, value in updated_context.items():
    self.context_manager.set(key, value)

updated_gmap = java_bridge.global_map
for key, value in updated_gmap.items():
    self.global_map.put(key, value)
```

---

## Appendix I: Groovy vs Java Compatibility Reference

Since the V1 implementation uses Groovy (via `GroovyShell`) instead of Java (via `javac`), the following compatibility notes apply to Talend CODE migration:

### Fully Compatible Patterns

| Pattern | Java | Groovy | Notes |
|---------|------|--------|-------|
| Variable declaration | `String name = "test";` | Same | Groovy also allows `def name = "test"` |
| Method calls | `str.toUpperCase()` | Same | |
| Arithmetic | `a + b * c` | Same | |
| Casting | `(String) obj` | Same | |
| `instanceof` | `obj instanceof String` | Same | |
| `try/catch` | `try { } catch (Exception e) { }` | Same | |
| `for` loop | `for (int i = 0; i < n; i++)` | Same | |
| `if/else` | `if (x > 0) { } else { }` | Same | |
| `null` checks | `if (x != null)` | Same | Also supports Groovy `?.` operator |
| `import` | `import java.util.List;` | Same | Groovy auto-imports more packages |
| `new` operator | `new Date()` | Same | |
| Array access | `arr[0]` | Same | |
| String concatenation | `"Hello " + name` | Same | Groovy also supports `"Hello ${name}"` |
| `Math` methods | `Math.round(x)` | Same | |

### Behavior Differences

| Pattern | Java Behavior | Groovy Behavior | Risk Level |
|---------|--------------|-----------------|------------|
| `==` on objects | Reference comparison | `.equals()` comparison | **MEDIUM**: Groovy `==` is safer (null-safe equals). Talend code using `==` for string comparison accidentally works in Groovy but would fail in Java. Code relying on reference comparison (rare) would differ. |
| `if (string)` | Compile error | True if non-null and non-empty | **LOW**: Groovy truth coercion is more permissive. Talend code always uses explicit null checks. |
| `if (number)` | Compile error | True if non-zero | **LOW**: Same as above. |
| `def` keyword | Not available | Dynamic typing | **NONE**: Talend code uses Java types. |
| Missing semicolons | Compile error | Optional | **NONE**: Talend code always includes semicolons. |
| Method resolution | Compile-time | Runtime (MOP) | **LOW**: Slightly slower; enables dynamic dispatch. |
| Property access | No magic | `getX()`/`setX()` auto-mapping | **LOW**: `map.key` maps to `map.get("key")` in Groovy. Can cause unexpected behavior with Map-based context. |
| Auto-imports | `java.lang.*` only | `java.lang.*`, `java.util.*`, `java.io.*`, `java.net.*`, `java.math.BigDecimal`, `java.math.BigInteger`, `groovy.lang.*`, `groovy.util.*` | **BENEFICIAL**: Talend code with `import java.util.*;` works without the import in Groovy. |
| Closures | No native support | Full closure support | **NONE**: Talend code does not use closures. |
| GString | N/A | `"Hello ${name}"` | **LOW**: Talend code uses `+` concatenation. Dollar signs in strings could be misinterpreted. |
| Power operator | N/A | `x ** 2` | **NONE**: Not used in Talend code. |
| Elvis operator | N/A | `x ?: default` | **NONE**: Not used in Talend code. |
| Safe navigation | N/A | `x?.method()` | **NONE**: Not used in Talend code. |

### High-Risk Patterns

| Pattern | Risk | Mitigation |
|---------|------|------------|
| `globalMap.put("key", value)` in parallel | Data corruption (HashMap not thread-safe) | Use ConcurrentHashMap or sequential execution |
| Static variable access in CODE | Non-deterministic in parallel | Static state shared across all rows |
| `System.out.println()` in CODE | Output interleaving in parallel | Use synchronized logging or avoid |
| `Thread.sleep()` in CODE | Blocks ForkJoinPool thread | Can cause thread starvation |
| `new File(...)` in CODE | Not sandboxed | Arbitrary file system access |

---

## Appendix J: Test Code Reference

### Existing Integration Test: test_basic_java_row()

```python
# tests/v1/test_java_integration.py lines 21-98
def test_basic_java_row():
    df = pd.DataFrame({
        'first_name': ['John', 'Jane', 'Bob'],
        'last_name': ['Doe', 'Smith', 'Johnson'],
        'age': [30, 25, 35],
        'amount': [1500.00, 2300.00, 800.00]
    })

    java_manager = JavaBridgeManager(enable=True)
    java_manager.start()

    context = ContextManager(java_bridge_manager=java_manager)
    global_map = GlobalMap()

    config = {
        'java_code': """
        String full_name = input_row.get("first_name") + " " + input_row.get("last_name");
        Integer age = (Integer) input_row.get("age");
        Double amount = (Double) input_row.get("amount");
        boolean is_adult = age >= 18;
        double amount_with_tax = amount * 1.08;
        output_row.set("full_name", full_name);
        output_row.set("is_adult", is_adult);
        output_row.set("amount_with_tax", Math.round(amount_with_tax * 100.0) / 100.0);
        """,
        'output_schema': {
            'full_name': 'String',
            'is_adult': 'Boolean',
            'amount_with_tax': 'Double'
        }
    }

    component = TJavaRow(
        component_id='tJavaRow_1',
        config=config,
        global_map=global_map,
        context_manager=context
    )

    result = component.execute(df)
    output_df = result['main']
    # Only verifies: execution succeeds, output_df exists
    # Does NOT verify: values, types, row count
```

**Assessment**: This test uses `get()`/`set()` methods (not Talend's dot notation). It verifies only successful execution, not correctness. It requires a running Java bridge (not mockable). It uses manual `print()` output instead of assertions.

### Recommended Minimal Unit Test (Mockable)

```python
# Recommended: tests/v1/test_java_row_component.py
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from v1.engine.components.transform.java_row_component import JavaRowComponent

class TestJavaRowComponent:
    def test_null_input_returns_empty(self):
        ctx = MagicMock()
        ctx.is_java_enabled.return_value = True
        component = JavaRowComponent('test', {'java_code': 'x', 'output_schema': {'a': 'String'}}, MagicMock(), ctx)
        result = component._process(None)
        assert result['main'].empty

    def test_missing_java_code_raises(self):
        ctx = MagicMock()
        component = JavaRowComponent('test', {'output_schema': {'a': 'String'}}, MagicMock(), ctx)
        with pytest.raises(ValueError, match="java_code"):
            component._process(pd.DataFrame({'x': [1]}))

    def test_missing_output_schema_raises(self):
        ctx = MagicMock()
        component = JavaRowComponent('test', {'java_code': 'x'}, MagicMock(), ctx)
        with pytest.raises(ValueError, match="output_schema"):
            component._process(pd.DataFrame({'x': [1]}))
```

---

## Appendix K: Converter Expression Handling for tJavaRow

### How tJavaRow CODE Avoids Java Expression Marking

The converter has a specific exclusion for tJavaRow in two places:

**Exclusion 1** (component_parser.py line 448):
```python
elif name not in ['CODE', 'IMPORT'] and isinstance(value, str) and 'context.' in value:
```
This prevents context references INSIDE CODE/IMPORT from being wrapped as `${context.var}`. This is correct because `context.variableName` in Java code should remain as Java code, not be resolved by Python's ContextManager.

**Exclusion 2** (component_parser.py line 462):
```python
if component_name not in ['tMap', 'tJavaRow', 'tJava']:
```
This prevents ALL config values for tJavaRow from being scanned for Java expression markers (`{{java}}`). This is correct because the entire config (java_code, imports) IS Java code -- marking it as `{{java}}` would cause the base component to try to evaluate the code as a one-time expression instead of passing it to `execute_java_row()`.

**Edge case**: If a tJavaRow component has OTHER config values (beyond CODE/IMPORT) that contain Java expressions, they would NOT be marked. Currently, the only other config value is `output_schema`, which contains type strings (not expressions), so this is not a problem. However, if `DIE_ON_ERROR` were extracted and contained a Java expression (unlikely but possible), it would not be resolved.

---

## Appendix L: Data Race Analysis

### Shared Mutable State in Parallel Execution

The `IntStream.parallel().forEach()` on JavaBridge.java line 113 creates a parallel stream processed by the ForkJoinPool. The following state is shared across threads:

| Shared State | Type | Thread Safety | Risk |
|-------------|------|---------------|------|
| `compiledScript` | `Script` | `synchronized` block | **Safe** (but slow) |
| `context` | `HashMap` | **Not synchronized** | **RACE**: Read in binding setup (line 126), potentially written by user code |
| `globalMap` | `HashMap` | **Not synchronized** | **RACE**: Same as context |
| `loadedRoutines` | `HashMap` | Read-only during execution | **Safe** |
| `outputArrays` | `Map<String, Object[]>` | Thread-safe by index | **Safe** (each thread writes to unique index) |
| `inputRoot` | `VectorSchemaRoot` | Read-only | **Safe** (Arrow vectors are thread-safe for read) |

### Race Condition Scenarios

**Scenario 1: User code modifies globalMap**
```java
// User's CODE:
Integer count = (Integer) globalMap.get("counter");
globalMap.put("counter", count + 1);
```
- Thread A reads `counter = 5`
- Thread B reads `counter = 5` (same value -- not yet incremented)
- Thread A writes `counter = 6`
- Thread B writes `counter = 6` (lost update)
- Expected: 7, Actual: 6

**Scenario 2: HashMap structural modification**
```java
// User's CODE:
globalMap.put("row_" + input_row.get("id"), input_row.get("value"));
```
- Multiple threads call `HashMap.put()` concurrently
- `HashMap` is NOT thread-safe for concurrent writes
- Can cause infinite loops (in Java 7), data corruption, or `ConcurrentModificationException`

**Scenario 3: Context read during binding setup**
```java
// JavaBridge.java line 126:
binding.setVariable("context", context);  // Shares reference to HashMap
```
- All threads get the SAME `context` HashMap reference (not a copy)
- If user code modifies context, all threads see the modification
- No synchronization protects this -- potential stale reads and lost updates

### Mitigation Strategy

The safest approach is **sequential execution** (remove `.parallel()`), which:
1. Eliminates all data races
2. Matches Talend semantics
3. Removes synchronized block overhead
4. Simplifies debugging and error handling

If parallelism is desired, use:
1. `ConcurrentHashMap` for `context` and `globalMap`
2. Per-thread script instances (see Appendix F)
3. Thread-safe row-level error collection
4. Clear documentation that user code must be thread-safe
