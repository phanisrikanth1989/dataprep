# Audit Report: tContextLoad / ContextLoad

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tContextLoad` |
| **V1 Engine Class** | `ContextLoad` |
| **Engine File** | `src/v1/engine/components/context/context_load.py` (349 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 241-250) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Registry Aliases** | `ContextLoad`, `tContextLoad` (registered in `src/v1/engine/engine.py` lines 169-170) |
| **Category** | Context / Misc |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/context/context_load.py` | Engine implementation (349 lines) |
| `src/v1/engine/context_manager.py` | ContextManager class: `set()`, `get()`, `get_type()`, `_convert_type()`, `resolve_string()`, `load_from_file()` |
| `src/converters/complex_converter/component_parser.py` (lines 241-250) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` | Dispatch -- no dedicated `elif` for `tContextLoad`; uses generic `parse_base_component()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_CONTEXT_LOADED` |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `FileOperationError`) |
| `src/v1/engine/components/context/__init__.py` | Package exports: `ContextLoad` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 2 | 1 | 6 of 10 relevant Talend params extracted; CONTEXTFILE mapped to filepath; missing DISABLE_WARNINGS, DIE_ON_ERROR; default delimiter mismatch |
| Engine Feature Parity | **Y** | 0 | 5 | 4 | 2 | No warning validation; no type coercion on properties load; incomplete comment handling; no `!` comment prefix support |
| Code Quality | **R** | 3 | 6 | 5 | 2 | Cross-cutting base class bugs; error-path exception swallowing; NaN key/value pollution; value always stringified; properties comment handling incomplete; duplicate code between methods; thread-safety gaps |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Row-by-row iterrows() for DataFrame/CSV; minor optimization opportunities |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready. P0 error-path bug swallows all component failures, NaN pollution silently corrupts context.**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tContextLoad Does

`tContextLoad` modifies dynamically the values of the active context at runtime. It receives an input flow containing key-value pairs (typically from a file reader like `tFileInputDelimited`, a database input like `tMySqlInput`, or any upstream component producing rows with `key` and `value` columns) and overrides the current context variable values with the values from the incoming flow. Once context variables are loaded via `tContextLoad`, the statically defined values in Talend Studio or Talend Management Console are superseded.

The component performs two validation controls:
1. It warns when parameters defined in the incoming flow are NOT defined in the job's context (i.e., unknown keys in the input).
2. It warns when context variables defined in the job are NOT initialized by the incoming flow (i.e., missing keys in the input).

These warnings are informational and do not block processing by default.

**Source**: [tContextLoad Standard Properties (Talend 8.0)](https://help.talend.com/en-US/components/8.0/context/tcontextload-standard-properties), [tContextLoad (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/context/tcontextload), [Using tContextLoad and Implicit Context Loading](https://mindmajix.com/talend/using-tcontextload-and-implicit-context-loading-to-load-contexts), [Best Practices for Context Variables Part 3](https://www.talend.com/resources/best-practices-for-using-context-variables-part-3/)

**Component family**: Misc (Context)
**Available in**: All Talend products (Standard). The Standard tContextLoad component belongs to the Misc family.
**Required JARs**: None (built-in component)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | key (String), value (String) | Input schema defining the incoming flow structure. Must contain at minimum a `key` column and a `value` column. Both are typically String type. |
| 3 | Print Operations | `PRINT_OPERATIONS` | Boolean (CHECK) | `false` | When enabled, the component prints each context variable assignment to the console/log. It outputs messages like `"Context variable 'host' has been reassigned: 'oldvalue' -> 'newvalue'"`. Useful for debugging but should be disabled in production to avoid leaking sensitive values (e.g., passwords) to log files. |
| 4 | Disable Warnings | `DISABLE_WARNINGS` | Boolean (CHECK) | `false` | When enabled, suppresses the two validation warnings (unknown keys and missing context variables). When disabled (default), warnings are printed to stderr. |
| 5 | Die on Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on error during context loading. When unchecked, errors are logged but processing continues. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 6 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 7 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Implicit Context Load Parameters

When used via Talend's Implicit Context Load feature (configured at the job level rather than via the tContextLoad component), additional parameters come into play:

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 8 | Context File | `CONTEXTFILE` / `IMPLICIT_CONTEXT_FILE` | Expression (String) | -- | Path to the context file when loading from file. Supports context variables and Java expressions. |
| 9 | File Format | `FORMAT` | Dropdown | `properties` | Format of the context file. Options: `properties` (key=value), `csv` (comma-separated with header). |
| 10 | Field Separator | `FIELDSEPARATOR` | String | `";"` | Delimiter for key-value pairs in file-based loading. For properties files, this is typically `=`. Talend default is semicolon. |
| 11 | CSV Separator | `CSV_SEPARATOR` | String | `","` | Separator character when FORMAT is `csv`. |
| 12 | Error if Not Exists | `ERROR_IF_NOT_EXISTS` | Boolean | `true` | Whether to raise an error if the context file does not exist. When false, a missing file is silently ignored. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input flow containing key-value pairs. Schema must have at minimum `key` (String) and `value` (String) columns. An optional third column for type information may be present. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Important**: tContextLoad is an **input-only** component. It does NOT produce an output data flow. It consumes the incoming key-value rows and applies them to the job's context. There is no FLOW output or REJECT output.

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed from the input flow. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully applied as context variables. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows that could not be applied (e.g., type conversion failures). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. |

### 3.6 Behavioral Notes

1. **Input flow requirement**: tContextLoad receives its data from an upstream component connected via a Row link. Commonly, the upstream is `tFileInputDelimited` reading a key=value file, or `tMySqlInput`/`tOracleInput` reading from a database table. The upstream MUST produce at minimum `key` and `value` columns.

2. **Override semantics**: tContextLoad OVERRIDES any previously defined context variable values. If a context variable `host` was set to `localhost` in the static context definition and the input flow provides `host=production-server`, the context variable becomes `production-server`. The original value is permanently replaced for the remainder of the job execution.

3. **Warning behavior**: By default (DISABLE_WARNINGS=false), the component produces two types of warnings:
   - **Unknown keys**: If the input flow contains a key `foo` but no context variable `foo` is defined in the job, a warning is logged: `"key 'foo' from the input flow is not defined in the context"`.
   - **Missing keys**: If the job defines a context variable `bar` but the input flow does not contain a row with key `bar`, a warning is logged: `"context variable 'bar' is not set in the input flow"`.
   These warnings go to stderr and do NOT stop processing. They are purely informational.

4. **Print operations**: When PRINT_OPERATIONS=true, each context variable assignment is printed to the console. The output shows the variable name, old value, and new value. This is a debugging aid and should be disabled in production to prevent sensitive values (passwords, connection strings) from appearing in logs.

5. **Type preservation**: In Talend, context variables have defined types (String, Integer, Boolean, etc.). When tContextLoad sets a value from the input flow, it performs type conversion based on the context variable's declared type. For example, if context variable `port` is declared as Integer and the input flow provides the string `"5432"`, Talend converts it to integer `5432`.

6. **Properties file format**: When loading from a properties file (via Implicit Context Load), the format is standard Java properties: `key=value` pairs, one per line. Comment lines start with `#` or `!`. Blank lines are ignored. Values can contain `=` characters (only the first `=` is treated as the delimiter). Backslash escapes are supported for special characters.

7. **CSV format**: When loading from CSV format, the file has a header row with column names. The component looks for columns named `key` and `value`. Additional columns (e.g., `type`) may be present but are not standard.

8. **Die on error**: When DIE_ON_ERROR=true and an error occurs (e.g., type conversion failure, file not found for implicit context), the job terminates immediately. When false, the error is logged and the job continues with whatever context values were successfully loaded.

9. **Typical job pattern**: The most common usage pattern is: `tFileInputDelimited` -> `tContextLoad`, where the file reader reads a properties file with `=` as the field separator, producing `key` and `value` columns that flow into tContextLoad. Another common pattern is: `tMySqlInput` -> `tMap` -> `tContextLoad`, where database rows are mapped to key-value pairs.

10. **Implicit Context Load**: Talend also supports loading context variables implicitly at job startup (before any components execute). This feature uses the same underlying mechanism as tContextLoad but is configured at the Job level rather than as a component. The v1 engine's `ContextLoad` component handles both use cases through its file-based loading mode.

11. **No output data**: Unlike most Talend components, tContextLoad does NOT produce output rows. It is a data sink for context configuration. Downstream components connected via trigger links (SUBJOB_OK, COMPONENT_OK) can access the updated context variables.

12. **Multiple tContextLoad components**: A job can have multiple tContextLoad components, each loading different context variables from different sources. Later loads override earlier ones for overlapping keys.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the **deprecated generic parameter mapping approach** (`_map_component_parameters()` in `component_parser.py` lines 241-250) rather than a dedicated `parse_tcontextload()` method. There is NO dedicated `elif component_type == 'tContextLoad'` branch in `converter.py:_parse_component()`. The component falls through to the generic `parse_base_component()` path.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tContextLoad', config_raw)` (line 472)
4. Returns mapped config with renamed keys
5. Schema is extracted generically from `<metadata connector="FLOW">` nodes

**Converter mapping code** (component_parser.py lines 241-250):
```python
elif component_type == 'tContextLoad':
    return {
        'filepath': config_raw.get('CONTEXTFILE', ''),
        'format': config_raw.get('FORMAT', 'properties'),
        'delimiter': config_raw.get('FIELDSEPARATOR', ';'),
        'csv_separator': config_raw.get('CSV_SEPARATOR', ','),
        'print_operations': config_raw.get('PRINT_OPERATIONS', False),
        'error_if_not_exists': config_raw.get('ERROR_IF_NOT_EXISTS', True)
    }
```

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `CONTEXTFILE` | Yes | `filepath` | 244 | Maps to file path for file-based context loading |
| 2 | `FORMAT` | Yes | `format` | 245 | Default `'properties'` -- matches Talend |
| 3 | `FIELDSEPARATOR` | Yes | `delimiter` | 246 | **Default `';'` -- Talend default is `'='` for properties files** |
| 4 | `CSV_SEPARATOR` | Yes | `csv_separator` | 247 | Default `','` -- matches Talend |
| 5 | `PRINT_OPERATIONS` | Yes | `print_operations` | 248 | Boolean from CHECK field type |
| 6 | `ERROR_IF_NOT_EXISTS` | Yes | `error_if_not_exists` | 249 | Default `True` -- matches Talend |
| 7 | `DISABLE_WARNINGS` | **No** | -- | -- | **Not extracted. Warning validation not available.** |
| 8 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted. Error handling behavior not configurable.** |
| 9 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 10 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 11 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 6 of 8 runtime-relevant parameters extracted (75%). 2 runtime-relevant parameters are missing: `DISABLE_WARNINGS` and `DIE_ON_ERROR`.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 474-507 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime format |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic -- no runtime impact) |

For tContextLoad, the schema typically defines two columns: `key` (String) and `value` (String). Some jobs add a third `type` (String) column. The schema extraction handles this correctly.

### 4.3 Expression Handling

**Context variable handling** (component_parser.py lines 449-456):
- Simple `context.var` references in non-CODE/IMPORT fields are detected by checking `'context.' in value`
- If the expression is NOT a Java expression (per `detect_java_expression()`), it is wrapped as `${context.var}` for ContextManager resolution
- If it IS a Java expression, it is left as-is for the Java expression marking step

**Java expression handling** (component_parser.py lines 460-469):
- After raw parameter extraction, the `mark_java_expression()` method scans all non-CODE/IMPORT/UNIQUE_NAME string values
- Values containing Java operators, method calls, routine references, etc. are prefixed with `{{java}}` marker
- The engine's `BaseComponent._resolve_java_expressions()` resolves these at runtime via the Java bridge

**Known limitations for tContextLoad**:
- The `CONTEXTFILE` path may contain context variables (e.g., `context.config_dir + "/context.properties"`), which requires Java expression resolution. If the Java bridge is not available, the path will not be resolved correctly.
- The `FIELDSEPARATOR` value may be expressed as a Java char literal (e.g., `'='`), which the converter's quote-stripping logic handles via `value[1:-1]` on line 441.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-CL-001 | **P1** | **No dedicated parser method**: `tContextLoad` uses the deprecated `_map_component_parameters()` approach instead of a dedicated `parse_tcontextload()` method. Per STANDARDS.md, every component MUST have its own `parse_*` method. This prevents future extraction of complex parameters and limits extensibility. |
| CONV-CL-002 | **P1** | **`DIE_ON_ERROR` not extracted**: The converter does not map `DIE_ON_ERROR` to the v1 config. The engine has no way to know whether errors should be fatal or recoverable. Currently the engine always raises on error in file mode and always raises ValueError for DataFrame mode, regardless of the original Talend configuration. |
| CONV-CL-003 | **P2** | **`DISABLE_WARNINGS` not extracted**: The warning validation behavior (checking for unknown keys and missing context variables) cannot be configured. The engine does not implement this validation at all. |
| CONV-CL-004 | **P2** | **Default delimiter mismatch**: Converter defaults `FIELDSEPARATOR` to `';'` (line 246), but Talend's standard properties file format uses `'='` as the key-value delimiter. The semicolon default is appropriate for Talend's generic field separator, but when `FORMAT='properties'`, the delimiter should default to `'='`. This mismatch means converted jobs that rely on the default delimiter will use the wrong separator. |
| CONV-CL-005 | **P3** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both, this violates the documented standard. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Load context from DataFrame input | **Yes** | High | `_process_dataframe_input()` line 106 | Processes key-value rows from upstream component |
| 2 | Load context from properties file | **Yes** | Medium | `_load_properties_context()` line 246 | Reads key=value format; handles `#` and `//` comments |
| 3 | Load context from CSV file | **Yes** | Medium | `_load_csv_context()` line 203 | Uses `pd.read_csv()` with configurable separator |
| 4 | Print operations logging | **Yes** | Medium | Lines 141-142, 239-240, 285-286 | Logs `key = value (type)` -- different format from Talend (no old value, no reassignment message) |
| 5 | Context variable type preservation | **Yes** | Medium | `_determine_value_type()` line 294 | Checks explicit type column, then existing context type, then defaults to `id_String` |
| 6 | NB_CONTEXT_LOADED globalMap | **Yes** | Low | `_update_component_stats()` line 348 | Uses non-standard variable name `{id}_NB_CONTEXT_LOADED` instead of `{id}_NB_LINE` |
| 7 | File existence check | **Yes** | High | `_process_file_input()` line 178 | `os.path.exists()` before reading |
| 8 | error_if_not_exists handling | **Yes** | High | `_process_file_input()` lines 179-184 | Raises FileNotFoundError or logs warning and returns empty DF |
| 9 | Properties file comment handling | **Partial** | Medium | `_load_properties_context()` line 265 | Handles `#` and `//` comments but **NOT `!` comments** (Java properties standard supports `!` as comment prefix) |
| 10 | Value quote stripping | **Yes** | High | `_clean_value()` line 319 | Removes surrounding single or double quotes |
| 11 | Empty line skipping | **Yes** | High | `_load_properties_context()` line 265 | `if not line` check after strip |
| 12 | Context variable override | **Yes** | High | Via `context_manager.set()` | Overwrites existing context values correctly |
| 13 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 14 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 15 | Type conversion on set | **Yes** | High | Via `context_manager.set()` -> `_convert_type()` | Supports `id_String`, `id_Integer`, `id_Float`, `id_Boolean`, `id_BigDecimal`, etc. |
| 16 | **Warning validation** | **No** | N/A | -- | **No validation that input keys exist in context or that all context variables are loaded. Fundamental gap in Talend behavior.** |
| 17 | **Disable warnings toggle** | **No** | N/A | -- | **No DISABLE_WARNINGS support. Warnings not implemented at all.** |
| 18 | **Die on error toggle** | **No** | N/A | -- | **No DIE_ON_ERROR support. Error behavior is hardcoded.** |
| 19 | **`!` comment prefix** | **No** | N/A | -- | **Java properties standard supports `!` as comment prefix. Only `#` and `//` handled.** |
| 20 | **Print operations old-value display** | **No** | N/A | -- | **Talend shows old value alongside new value. Engine only shows new value.** |
| 21 | **Backslash escape in properties values** | **No** | N/A | -- | **Java properties files support `\n`, `\t`, `\uXXXX` escapes. Not implemented.** |
| 22 | **Multi-line properties values** | **No** | N/A | -- | **Java properties support line continuation with trailing `\`. Not implemented.** |
| 23 | **`{id}_NB_LINE` standard globalMap** | **No** | N/A | -- | **Uses non-standard `{id}_NB_CONTEXT_LOADED`. Standard `{id}_NB_LINE` not set.** |
| 24 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-CL-001 | **P1** | **No warning validation for unknown/missing keys**: Talend warns when input keys are not defined in the context and when context variables are not initialized by the input flow. The v1 engine silently accepts ALL keys without any validation. This means unknown keys are quietly ignored (set on context manager where they may never be used) and missing context variables retain their old values with no notification. This eliminates a critical debugging aid for context configuration issues. |
| ENG-CL-002 | **P1** | **Non-standard globalMap variable name**: The engine uses `{id}_NB_CONTEXT_LOADED` (line 348) instead of the Talend standard `{id}_NB_LINE`. Downstream components referencing `((Integer)globalMap.get("tContextLoad_1_NB_LINE"))` (the standard Talend pattern) will get null/None. The component should set BOTH `{id}_NB_LINE` and `{id}_NB_CONTEXT_LOADED` for backward compatibility. |
| ENG-CL-003 | **P1** | **Values always stringified via `str()` in DataFrame and CSV modes**: In `_process_dataframe_input()` line 131 and `_load_csv_context()` line 229, values are converted to string via `str(row['value'])` BEFORE being passed to `context_manager.set()`. This means the type conversion in `context_manager._convert_type()` receives a string representation, which may lose precision for floating-point numbers or produce incorrect conversions for boolean values that are already Python `True`/`False` objects (they become the string `"True"` which then gets re-parsed). |
| ENG-CL-004 | **P1** | **`!` comment prefix not supported in properties files**: The Java `.properties` file format supports both `#` and `!` as comment line prefixes. The engine only handles `#` and `//` (line 265). Lines starting with `!` will be treated as key-value pairs, potentially causing a parsing error or loading garbage into context variables. |
| ENG-CL-005 | **P1** | **No `DIE_ON_ERROR` support**: The engine always raises exceptions on error. There is no way to configure graceful degradation where errors are logged but processing continues. The only exception is `error_if_not_exists=False` for missing files. For all other errors (malformed files, CSV parse errors, type conversion failures), the exception propagates unconditionally. |
| ENG-CL-006 | **P2** | **Print operations format differs from Talend**: Talend's print operations show the reassignment with old and new values: `"Context variable 'host' has been reassigned: 'oldvalue' -> 'newvalue'"`. The v1 engine only shows `"Context loaded: key = value (type: type)"` without the old value. This makes it harder to track what changed during context loading. |
| ENG-CL-007 | **P2** | **No backslash escape handling in properties files**: Java properties files support escape sequences like `\n` (newline), `\t` (tab), `\\` (backslash), and `\uXXXX` (Unicode). The engine reads the raw line content without processing escapes. A value like `path=C:\\data\\file.csv` would be stored as `C:\\data\\file.csv` (with double backslashes) instead of `C:\data\file.csv`. |
| ENG-CL-008 | **P2** | **No multi-line value support in properties files**: Java properties files support line continuation with a trailing backslash. A value like `message=Hello \` (followed by `World` on the next line) produces `message=Hello World`. The engine reads line-by-line without joining continuation lines. |
| ENG-CL-009 | **P2** | **CSV format requires hardcoded column names**: Both `_load_csv_context()` (line 221) and `_process_dataframe_input()` (line 123) require columns named exactly `key` and `value`. Talend allows any column names in the upstream component, as long as they are mapped to the tContextLoad schema via tMap. This works correctly for DataFrame input (since the upstream tMap would produce correctly named columns), but for direct CSV file loading, the CSV file MUST have headers named `key` and `value` -- there is no column index-based fallback. |
| ENG-CL-010 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream reference. Only the `NB_CONTEXT_LOADED` counter is stored. |
| ENG-CL-011 | **P3** | **No support for `=` in property keys**: The `_load_properties_context()` method uses `line.split(delimiter, 1)`, which correctly handles `=` in VALUES (only the first delimiter is used for splitting). However, Java properties files also support `key\=with\=equals=value` (escaped equals in keys). The engine does not handle backslash-escaped delimiters in keys. |
| ENG-CL-012 | **P3** | **No support for whitespace-only delimiter in properties**: Java properties files support whitespace (space or tab) as the key-value delimiter in addition to `=` and `:`. The engine only supports the configured delimiter character. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Partial** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set via base class mechanism, but the component ALSO sets the non-standard `{id}_NB_CONTEXT_LOADED` directly |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same base class mechanism | Always equals NB_LINE since no reject counting exists |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same base class mechanism | Always 0 -- no reject counting implemented |
| `{id}_NB_CONTEXT_LOADED` | **No** (Talend does not set this) | **Yes** | `_update_component_stats()` line 348 | Non-standard variable. Custom addition by v1 engine. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

**Key observation**: The component has a peculiar dual-tracking approach. It uses the base class `_update_stats()` (which sets standard `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` via `_update_global_map()`) AND separately stores `NB_CONTEXT_LOADED` via its own `_update_component_stats()` method. However, the base class `_update_global_map()` has a cross-cutting bug (BUG-CL-001) that causes a `NameError`, so in practice, the standard stats are NOT successfully written to globalMap. Only the custom `NB_CONTEXT_LOADED` variable is reliably stored.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-CL-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just ContextLoad, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The consequence for ContextLoad is that the standard `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` statistics are never written to globalMap. Only the custom `NB_CONTEXT_LOADED` variable (stored directly via `self.global_map.put()` in `_update_component_stats()`) is successfully persisted. |
| BUG-CL-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. For ContextLoad specifically, this means any downstream component trying to read `{id}_NB_CONTEXT_LOADED` via `global_map.get()` will crash. However, `global_map.put()` (used by `_update_component_stats()`) works correctly since it does not call `get()`. |
| BUG-CL-003 | **P1** | `src/v1/engine/components/context/context_load.py:131` | **Values always stringified loses type fidelity**: In `_process_dataframe_input()`, `value = str(row['value'])` on line 131 converts the value to string BEFORE passing to `context_manager.set()`. If the DataFrame `value` column contains typed data (e.g., Python `int` 5432, `float` 3.14, `bool` True), these are converted to strings `"5432"`, `"3.14"`, `"True"` BEFORE type conversion. While `context_manager._convert_type()` can parse these strings back, the round-trip through string representation can lose precision for floats (e.g., `3.141592653589793` may become `"3.141592653589793"` which converts back correctly, but `Decimal("3.14")` becomes `"3.14"` which loses the Decimal precision semantics). More critically, if the DataFrame value is already the correct type and the `value_type` is None (no type column and no existing context type), the value is stored as a string when it should be stored as its original type. |
| BUG-CL-004 | **P1** | `src/v1/engine/components/context/context_load.py:265` | **`!` comment prefix not handled**: The properties file reader checks `line.startswith('#') or line.startswith('//')` for comment detection, but Java `.properties` files also use `!` as a comment prefix. Lines starting with `!` (e.g., `! This is a comment`) will be parsed as key-value pairs, potentially causing a "missing delimiter" warning or, worse, loading `! This is a comment` as a context variable key. |
| BUG-CL-005 | **P1** | `src/v1/engine/components/context/context_load.py:218` | **CSV loading does not strip header quotes**: `pd.read_csv()` with default settings will strip enclosing quotes from data values but NOT from header names. If the CSV file has headers like `"key","value"`, pandas may produce column names `"key"` and `"value"` (with quotes), causing the `'key' not in df.columns` check on line 221 to fail with a misleading error. This depends on the CSV format and quoting behavior. |
| BUG-CL-006 | **P2** | `src/v1/engine/components/context/context_load.py:106-150 vs 203-244` | **Duplicate code between DataFrame and CSV processing**: The `_process_dataframe_input()` and `_load_csv_context()` methods contain near-identical logic: iterate rows, extract key/value, determine type, call `context_manager.set()`, log if print_operations, increment counter. The only difference is the data source (passed DataFrame vs `pd.read_csv()` result). This duplication means bugs fixed in one path may not be fixed in the other. |
| BUG-CL-007 | **P2** | `src/v1/engine/components/context/context_load.py:307-308` | **`_determine_value_type()` returns DataFrame cell value, not type string**: When `'type' in columns` is True, the method does `return row.get('type', 'id_String')`. If the `type` column contains `NaN` (e.g., for rows where type was not specified), `row.get('type', 'id_String')` returns `NaN` (a float), not the default `'id_String'`. The `NaN` value is then passed to `context_manager.set()` as the type, which causes `_convert_type()` to look up `NaN` in its type mapping, fail the lookup, fall back to `str` conversion, and silently store the value as a string. The fallback behavior happens to produce correct results for string values, but is incorrect for typed values. |
| BUG-CL-008 | **P0** | `src/v1/engine/base_component.py:231` | **`_update_global_map()` crash in error path swallows original exception**: When `_process()` raises an exception, the error handler in `execute()` calls `_update_global_map()`, which itself raises `NameError` (due to BUG-CL-001). The `NameError` replaces the original meaningful exception. The caller never sees the real error. This makes ALL component failures impossible to diagnose -- every error surfaces as an opaque `NameError` about an undefined variable instead of the actual `ValueError`, `FileNotFoundError`, or other meaningful exception that caused the failure. |
| BUG-CL-009 | **P1** | `src/v1/engine/components/context/context_load.py:130` | **NaN in `key` column produces context variable named `'nan'`**: When an upstream join or merge produces missing keys, the `key` column contains `NaN`. `str(NaN)` evaluates to the string `'nan'`. The component then calls `context_manager.set('nan', ...)`, silently polluting the context with a spurious variable named `'nan'`. No validation detects this. Downstream `resolve_string()` calls referencing `${context.nan}` would resolve to this garbage value. |
| BUG-CL-010 | **P1** | `src/v1/engine/components/context/context_load.py:131, 229` | **NaN in `value` column produces context value `'nan'`**: When the `value` column contains `NaN` (e.g., from a left join with no match, or pandas CSV parsing of `"NA"`/`"NULL"` strings), `str(NaN)` evaluates to `'nan'`. If the context variable is something like `database_password` or `connection_url`, it gets set to the literal string `'nan'`. This causes downstream connection failures with misleading "authentication failed" or "invalid URL" errors that do not point back to the NaN origin. |
| BUG-CL-011 | **P1** | `src/v1/engine/base_component.py:218-220` | **Component status never reaches SUCCESS**: `_update_global_map()` at `base_component.py:218` crashes (due to BUG-CL-001) before line 220 where `self.status = ComponentStatus.SUCCESS` is set. The status remains `RUNNING` permanently. Any monitoring, orchestration, or downstream logic that checks component status will see a perpetually running component even after it completes. Combined with BUG-CL-008, this means the success path is also broken -- not just the error path. |
| BUG-CL-012 | **P2** | `src/v1/engine/components/context/context_load.py:260` | **BOM (Byte Order Mark) handling corrupts first key**: Line 260 uses `encoding='utf-8'` which preserves the BOM character (`\ufeff`) if present in the file. The first key in the properties file gets a `\ufeff` prefix (e.g., `\ufeffhost` instead of `host`). All lookups for that key fail silently -- `context_manager.get('host')` returns `None` while `context_manager.get('\ufeffhost')` holds the value. Fix: use `encoding='utf-8-sig'` which automatically strips BOM. |
| BUG-CL-013 | **P2** | `src/v1/engine/components/context/context_load.py:319-334` | **`_clean_value('"')` turns single-character quoted value into empty string**: The `_clean_value()` method uses `value[1:-1]` to strip surrounding quotes. For a single-character value that is itself a quote character (e.g., `'"'` or `"'"`), `value[1:-1]` on a 1-character string returns `''`. A context variable whose legitimate value is a single quote character silently becomes an empty string. |
| BUG-CL-014 | **P2** | `src/v1/engine/context_manager.py` (ContextManager.context, context_types) | **Thread safety: plain dicts with no locking**: `ContextManager.context` and `ContextManager.context_types` are plain Python dicts accessed without any synchronization. When parallel subjobs execute (e.g., via `tParallelize`), concurrent `set()` and `resolve_string()` calls can interleave, producing torn reads (a key is set in `context` but its type is not yet set in `context_types`) or lost updates. Python's GIL protects against data corruption at the interpreter level, but does NOT prevent logical race conditions across multiple dict operations. |

### 6.2 Code Structure Analysis

| Aspect | Assessment |
|--------|------------|
| **Method decomposition** | Good. The `_process()` method delegates to `_process_dataframe_input()` and `_process_file_input()`, which further delegate to `_load_csv_context()` and `_load_properties_context()`. Helper methods `_determine_value_type()`, `_clean_value()`, and `_update_component_stats()` handle cross-cutting concerns. |
| **Single Responsibility** | Good. Each method has a clear purpose. File input handling is separated from DataFrame input handling. |
| **Code duplication** | Moderate concern. `_process_dataframe_input()` and `_load_csv_context()` share ~80% identical logic (see BUG-CL-006). |
| **Magic strings** | Minor concern. `'id_String'` default appears in multiple places (lines 308, 317). Should be a class constant. |
| **Error propagation** | Mixed. File input errors are caught and re-raised (line 200-201). DataFrame input errors propagate naturally. But there is no `die_on_error` toggle to control behavior. |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-CL-001 | **P2** | **`NB_CONTEXT_LOADED` is non-standard globalMap variable name**: Talend uses `NB_LINE` for all components. The custom name `NB_CONTEXT_LOADED` diverges from the standard naming convention. While descriptive, it breaks the pattern that all components follow and prevents generic downstream logic from accessing the row count. |
| NAME-CL-002 | **P3** | **`filepath` vs Talend `CONTEXTFILE`**: The config key `filepath` is clear but differs from Talend's `CONTEXTFILE`. The STANDARDS.md convention appears to use `filepath` for file paths, so this is consistent with the v1 standard even if it differs from Talend naming. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-CL-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | No `_validate_config()` method exists. No configuration validation is performed at initialization time. Invalid configurations (empty filepath with no DataFrame input, invalid format string, etc.) are not caught until runtime. |
| STD-CL-002 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | Uses deprecated `_map_component_parameters()` instead of a dedicated `parse_tcontextload()` method. |
| STD-CL-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |

### 6.5 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-CL-001 | **P3** | **Verbose debug logging on line 120**: `logger.debug(f"Component {self.id}: Processing DataFrame input: {input_data}")` logs the entire input DataFrame contents at DEBUG level. For large DataFrames, this produces enormous log output and may expose sensitive context values (passwords, API keys) in debug logs. Should be replaced with `logger.debug(f"Component {self.id}: Processing DataFrame input with {len(input_data)} rows")`. |

### 6.6 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-CL-001 | **P2** | **Print operations may log sensitive values**: When `print_operations=True`, the component logs all context variable values at INFO level, including potentially sensitive values like database passwords, API keys, and connection strings. While this matches Talend behavior (which also prints values), the Talend documentation explicitly warns against using print_operations in production for this reason. The v1 engine should at minimum log a warning when print_operations is enabled, and ideally support a configurable list of sensitive key patterns to mask (e.g., `*password*`, `*secret*`, `*key*`). |
| SEC-CL-002 | **P3** | **No path traversal protection on filepath**: `filepath` from config is used directly with `os.path.exists()` and `open()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.7 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | Most log messages use `f"Component {self.id}:"` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process_file_input()` logs completion with count (line 195). `_process_dataframe_input()` logs completion (line 148) -- correct |
| Sensitive data | **Potential issue**: print_operations logs ALL values at INFO level (see SEC-CL-001) |
| No print statements | No `print()` calls -- correct |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Raises `ValueError` (lines 124, 175, 222) and `FileNotFoundError` (line 180). Does NOT use custom exceptions from `exceptions.py` (`ConfigurationError`, `FileOperationError`). Should use `ConfigurationError` for validation failures and `FileOperationError` for file access issues. |
| Exception chaining | `_process_file_input()` uses bare `raise` (line 201) which preserves the original traceback -- correct. However, no `raise ... from e` pattern is used anywhere in the component. |
| No bare `except` | `_process_file_input()` catches `Exception` (line 199) -- correct |
| Error messages | Include component ID and file path -- correct |
| Graceful degradation | `error_if_not_exists=False` returns empty DataFrame -- correct. But no `die_on_error` toggle for other error types. |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_process_dataframe_input()`, `_process_file_input()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]` -- correct |
| Missing hints | `_load_csv_context()` and `_load_properties_context()` correctly hint return as `int` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-CL-001 | **P2** | **Row-by-row iteration via `iterrows()` in DataFrame and CSV modes**: Both `_process_dataframe_input()` (line 129) and `_load_csv_context()` (line 227) use `for _, row in df.iterrows()` to process each context variable. For most real-world use cases, context files have fewer than 100 variables, so this is not a practical concern. However, if a job loads thousands of context variables (unusual but possible), the `iterrows()` approach is significantly slower than vectorized pandas operations or `itertuples()`. |
| PERF-CL-002 | **P3** | **`context_manager.get_type()` called per-row in DataFrame mode**: In `_determine_value_type()` (line 311), `self.context_manager.get_type(key)` is called for every row when no explicit type column exists. For N context variables, this is N dictionary lookups, which is O(1) per lookup and O(N) total -- acceptable. But the method also logs at DEBUG level for each lookup (line 313), which adds I/O overhead when debug logging is enabled. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| DataFrame mode | Input DataFrame is processed row-by-row and not copied. Memory efficient. |
| CSV file loading | Uses `pd.read_csv()` which loads entire file into memory. For context files (typically < 1KB), this is negligible. |
| Properties file loading | Reads file line-by-line with `open()` and `for line in f`. Memory efficient -- only one line in memory at a time. |
| Return value | Returns `{'main': pd.DataFrame()}` -- empty DataFrame. Minimal memory footprint. |
| Context storage | Context variables stored in `ContextManager.context` (dict) and `ContextManager.context_types` (dict). Both are O(N) where N is the number of context variables. Negligible memory for typical use cases (< 100 variables). |

### 7.2 Scalability Assessment

| Scenario | Assessment |
|----------|------------|
| 10 context variables | Instant. No concerns. |
| 100 context variables | Instant. No concerns. |
| 1,000 context variables | Sub-second. `iterrows()` overhead negligible. |
| 10,000+ context variables | Unusual use case. `iterrows()` may take seconds. Consider vectorized approach. |
| Large properties file (>1MB) | Unusual. Line-by-line reading handles this efficiently. |
| Large CSV context file (>10MB) | Very unusual. `pd.read_csv()` loads into memory but should handle fine. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `ContextLoad` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 349 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic DataFrame input | P0 | Create a DataFrame with `key` and `value` columns, pass to `ContextLoad._process()`, verify context variables are set correctly via `context_manager.get()` |
| 2 | Properties file loading | P0 | Create a temporary properties file with `key=value` pairs, configure ContextLoad to read it, verify all context variables are loaded correctly |
| 3 | CSV file loading | P0 | Create a temporary CSV file with `key,value` header and data rows, configure ContextLoad with `format='csv'`, verify context variables are loaded |
| 4 | Missing file + error_if_not_exists=True | P0 | Configure ContextLoad with a non-existent filepath and `error_if_not_exists=True`, verify `FileNotFoundError` is raised |
| 5 | Missing file + error_if_not_exists=False | P0 | Configure ContextLoad with a non-existent filepath and `error_if_not_exists=False`, verify empty DataFrame returned and no error raised |
| 6 | Empty filepath | P0 | Configure ContextLoad with empty filepath and no DataFrame input, verify `ValueError` is raised |
| 7 | Statistics tracking | P0 | Load 5 context variables, verify `stats['NB_LINE']` == 5, `stats['NB_LINE_OK']` == 5, `stats['NB_LINE_REJECT']` == 0 |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Type column in DataFrame | P1 | Create DataFrame with `key`, `value`, `type` columns where type is `id_Integer`, verify context value is stored as integer |
| 9 | Type preservation from existing context | P1 | Pre-set a context variable with type `id_Integer`, then load a new value via ContextLoad without type column, verify the type is preserved |
| 10 | Print operations logging | P1 | Enable `print_operations=True`, load context variables, verify INFO-level log messages are produced for each variable |
| 11 | Properties file with comments | P1 | Create a properties file with `#` comment lines, verify comments are skipped and not loaded as context variables |
| 12 | Properties file with `!` comments | P1 | Create a properties file with `!` comment lines, **verify current behavior** (bug: `!` comments are loaded as variables) to document the gap |
| 13 | Value with embedded delimiter | P1 | Properties file line `url=jdbc:oracle:thin:@host:1521:SID` (value contains `=`), verify only the first `=` is used as delimiter |
| 14 | Quoted values in properties | P1 | Properties file with `password="my secret"`, verify quotes are stripped by `_clean_value()` |
| 15 | Custom delimiter | P1 | Configure ContextLoad with `delimiter=':'` and a file using `:` as separator, verify correct parsing |
| 16 | NB_CONTEXT_LOADED globalMap | P1 | Verify `global_map.get(f"{id}_NB_CONTEXT_LOADED")` returns correct count after loading |
| 17 | Context variable in filepath | P1 | `${context.config_dir}/context.properties` should resolve via context manager before file loading |
| 18 | Override existing context variable | P1 | Pre-set context variable `host=localhost`, load `host=production` via ContextLoad, verify `context_manager.get('host')` returns `production` |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | Empty properties file | P2 | Load from an empty file, verify 0 variables loaded and no error |
| 20 | Properties file with only comments | P2 | Load from a file containing only comment lines, verify 0 variables loaded |
| 21 | CSV with extra columns | P2 | Load from CSV with columns `key,value,type,comment`, verify only key/value/type are used |
| 22 | DataFrame with missing columns | P2 | Pass a DataFrame without `key` column, verify `ValueError` is raised with descriptive message |
| 23 | CSV without required columns | P2 | Load CSV file with headers `name,data` (no `key`/`value`), verify `ValueError` is raised |
| 24 | Large context file (1000 variables) | P2 | Load 1000 context variables, verify all loaded correctly and performance is acceptable |
| 25 | Unicode values in properties | P2 | Properties file with `greeting=\u4f60\u597d`, verify Unicode handling (current gap: no \uXXXX support) |
| 26 | Boolean type conversion | P2 | Load value `"true"` with type `id_Boolean`, verify stored as Python `True` |
| 27 | Integer type conversion | P2 | Load value `"5432"` with type `id_Integer`, verify stored as Python `int(5432)` |

---

## 9. Context Manager Integration Analysis

### 9.1 ContextManager.set() Behavior

The `ContextLoad` component relies on `ContextManager.set()` (context_manager.py line 58) to store context variables. Understanding this method is critical for evaluating type handling fidelity.

**`set()` method behavior**:
```python
def set(self, key: str, value: Any, value_type: Optional[str] = None) -> None:
    if value_type:
        value = self._convert_type(value, value_type)
        self.context_types[key] = value_type
    self.context[key] = value
```

**Key observations**:
1. When `value_type` is provided and non-None, `_convert_type()` is called to convert the value.
2. When `value_type` is None or empty string, the value is stored AS-IS with no type conversion.
3. The type is only recorded in `context_types` when `value_type` is provided. If a variable is set without a type, its type record is not updated.

### 9.2 ContextManager._convert_type() Coverage

The `_convert_type()` method (context_manager.py lines 162-194) supports the following types:

| Type String | Conversion | Notes |
|-------------|-----------|-------|
| `id_String` | `str` | Identity for string values |
| `id_Integer` | `int` | Parses string to integer. Raises `ValueError` for non-numeric strings. |
| `id_Long` | `int` | Same as `id_Integer` in Python (no distinction between int and long) |
| `id_Float` | `float` | Parses string to float |
| `id_Double` | `float` | Same as `id_Float` in Python |
| `id_Boolean` | `lambda v: str(v).lower() in ('true', '1', 'yes')` | Returns True for `"true"`, `"1"`, `"yes"` (case-insensitive). Returns False for everything else including `"false"`, `"0"`, `"no"`. |
| `id_Date` | `str` | **Stored as string** -- no date parsing. Comment says "Keep as strings for now". |
| `id_BigDecimal` | `Decimal` | **Bug**: The mapping says `'Decimal'` (string) but the converter tries to call `converter(value)` where `converter` is the string `'Decimal'`, not the `Decimal` class. This results in `'Decimal'` being used as a callable, which will throw a `TypeError` because strings are not callable. The issue is that the type_mapping uses string values `'str'`, `'int'`, `'float'`, `'Decimal'` but the `try: return converter(value)` code on line 191 expects callable types. However, Python's `int`, `float`, `str` ARE callable (built-in type constructors), so the string `'int'` is NOT callable -- it would fail. **Wait -- re-reading the code**: the mapping stores the STRING `'int'`, not the TYPE `int`. The `converter = type_mapping.get(value_type, str)` line gets the STRING `'int'`, and then `converter(value)` tries to call the STRING `'int'` as a function, which fails with `TypeError: 'str' object is not callable`. |

**Critical finding on _convert_type()**: On closer inspection of context_manager.py lines 168-191:

```python
type_mapping = {
    'id_String': 'str',
    'id_Integer': 'int',
    ...
}
converter = type_mapping.get(value_type, str)  # Gets STRING 'int', not TYPE int
try:
    return converter(value)  # Calls 'int'('5432') -- TypeError!
```

**Wait -- this actually works in Python**. When `type_mapping.get(value_type, str)` returns the string `'str'`, `'int'`, `'float'`, calling `'str'(value)` would indeed fail. BUT looking again at the default: `str` (without quotes) is the actual `str` type. So the default works. But for mapped types like `'id_Integer'`, `converter` becomes the STRING `'int'`, and `'int'('5432')` would fail because you cannot call a string.

**Correction**: Let me re-read more carefully. The values in the mapping are `'str'`, `'int'`, `'float'` -- these are plain strings, NOT type objects. The code does `converter = type_mapping.get(value_type, str)` where `str` (without quotes) is the actual builtin `str` type as the default. For matched types, `converter` is a string like `'int'`. Then `converter(value)` tries `'int'('5432')` which is `TypeError`.

However, the `lambda` entries for `id_Boolean` and `bool` ARE callable. And the default `str` IS callable (it is the actual `str` type, not the string `'str'`).

**Impact for ContextLoad**: When the ContextLoad component passes `value_type='id_Integer'` to `context_manager.set()`, the `_convert_type()` method will fail with `TypeError` for ANY value. The `except (ValueError, TypeError)` on line 192 catches this and returns the original (string) value with a warning. This means **type conversion silently fails for ALL Talend types except Boolean and the default (no type) case**. All values are effectively stored as strings.

### 9.3 Impact Analysis

| Scenario | Expected Behavior | Actual Behavior | Impact |
|----------|-------------------|-----------------|--------|
| `set('port', '5432', 'id_Integer')` | Store integer `5432` | _convert_type raises TypeError, caught, stores string `'5432'` | Context variable is string instead of int. Downstream comparisons like `context.port > 1000` may fail. |
| `set('debug', 'true', 'id_Boolean')` | Store boolean `True` | Lambda works correctly, stores `True` | CORRECT |
| `set('host', 'localhost', 'id_String')` | Store string `'localhost'` | _convert_type raises TypeError for `'str'('localhost')`, caught, stores `'localhost'` | Correct result by accident -- the fallback stores the original value. |
| `set('rate', '3.14', 'id_Float')` | Store float `3.14` | _convert_type raises TypeError, caught, stores string `'3.14'` | Context variable is string instead of float. |
| `set('amount', '100.50', 'id_BigDecimal')` | Store `Decimal('100.50')` | _convert_type raises TypeError, caught, stores string `'100.50'` | Context variable is string instead of Decimal. |
| `set('name', 'Alice', None)` | Store string `'Alice'` | No conversion called, stores `'Alice'` | CORRECT |

**Severity**: This is a significant type fidelity issue that affects ALL typed context variables. However, in practice, most Talend jobs use context variables as strings and rely on implicit conversion at the point of use (e.g., `Integer.parseInt(context.port)` in Java code). Since the v1 engine's `ContextManager.resolve_string()` always returns strings anyway, the practical impact is limited to cases where downstream Python code expects typed context values.

---

## 10. Detailed Code Analysis

### 10.1 `_process()` (Lines 67-104)

The main entry point for processing:
1. Extract 6 configuration parameters with defaults
2. Check if DataFrame input is provided
3. If yes, delegate to `_process_dataframe_input()`
4. If no, delegate to `_process_file_input()`

**Decision logic**: The routing is based purely on whether `input_data is not None`. This means:
- When connected to an upstream component (tFileInputDelimited -> tContextLoad), `input_data` will be a DataFrame, and the file-based parameters (`filepath`, `format`, `delimiter`) are ignored.
- When used standalone (e.g., for Implicit Context Load), `input_data` is None, and file-based parameters are used.

**Edge case**: If `input_data` is an empty DataFrame (`pd.DataFrame()`), `input_data is not None` is True, so the DataFrame path is taken. The DataFrame has no rows, so 0 variables are loaded. This is correct behavior.

### 10.2 `_process_dataframe_input()` (Lines 106-150)

Processes context variables from a DataFrame:
1. Validate that `key` and `value` columns exist
2. Iterate rows with `iterrows()`
3. For each row: extract key (stripped), value (stringified), determine type
4. Call `context_manager.set(key, value, value_type)`
5. Log if print_operations enabled
6. Increment counter
7. Call `_update_component_stats(loaded_count)`
8. Return empty DataFrame

**Key concerns**:
- Line 131: `value = str(row['value'])` -- always stringifies (BUG-CL-003)
- Line 137: `if self.context_manager:` guard -- if context_manager is None, the component silently does nothing. No error, no warning. Variables are "loaded" but not stored.

### 10.3 `_process_file_input()` (Lines 152-201)

Processes context variables from a file:
1. Validate filepath is not empty
2. Check file existence with `os.path.exists()`
3. Route to `_load_csv_context()` or `_load_properties_context()` based on format
4. Update stats and return empty DataFrame
5. Catch-all exception handler logs error and re-raises

**Key concerns**:
- Line 174: `if not filepath:` -- checks for empty string but not None. Since `config.get('filepath', '')` returns empty string by default, this works. But `filepath=None` would pass this check and fail later at `os.path.exists(None)` with a `TypeError`.
- Lines 199-201: `except Exception as e:` catches ALL exceptions, logs, and re-raises. This is correct but means the component always fails hard on any error during file loading (no die_on_error toggle).

### 10.4 `_load_csv_context()` (Lines 203-244)

Loads context from CSV file:
1. Read CSV with `pd.read_csv(filepath, sep=csv_separator)`
2. Validate `key` and `value` columns exist
3. Process rows identically to `_process_dataframe_input()`

**Key concerns**:
- Line 218: `pd.read_csv(filepath, sep=csv_separator)` -- no error handling for malformed CSV. pandas may raise `ParserError` which propagates to `_process_file_input()`'s catch-all handler.
- Line 218: No encoding parameter passed to `pd.read_csv()`. Defaults to system encoding (usually UTF-8 on modern systems). Talend defaults to ISO-8859-15. This could cause mojibake for non-ASCII context values in CSV files encoded with ISO-8859-15.
- Line 218: No `keep_default_na=False` parameter. Values like `"NA"`, `"NULL"`, `"None"` in the CSV will be interpreted as `NaN` by pandas, then stringified to `"nan"` on line 229, corrupting the context value.

### 10.5 `_load_properties_context()` (Lines 246-292)

Loads context from properties file:
1. Open file with UTF-8 encoding
2. Read line by line
3. Skip empty lines and lines starting with `#` or `//`
4. Split on delimiter (first occurrence only)
5. Strip whitespace from key, clean value via `_clean_value()`
6. Look up existing type from context manager
7. Call `context_manager.set(key, value, value_type)`
8. Log if print_operations enabled

**Key concerns**:
- Line 260: `open(filepath, 'r', encoding='utf-8')` -- hardcoded UTF-8 encoding. No way to configure encoding for the properties file. Java properties files are typically ISO-8859-1 (Latin-1), not UTF-8. This is a behavioral difference from Talend.
- Line 265: Missing `!` comment prefix handling (BUG-CL-004).
- Line 270: `key, value = line.split(delimiter, 1)` -- if the line has no delimiter, this raises `ValueError` which is NOT caught. However, line 269 checks `if delimiter in line:` before splitting, so this is safe. Lines without the delimiter are logged as warnings (line 290).
- Line 276: `self.context_manager.get_type(key)` returns `None` if the key has no stored type. The `if` guard on line 276 correctly handles this. But if `get_type()` returns an empty string `""`, it passes the truthiness check and is used as the type, which will fail in `_convert_type()`.

### 10.6 `_determine_value_type()` (Lines 294-317)

Determines the type for a context variable with three fallback levels:
1. Check if `type` column exists in DataFrame and use its value
2. Check existing context type via `context_manager.get_type(key)`
3. Default to `'id_String'`

**Key concerns**:
- Line 307-308: `row.get('type', 'id_String')` -- if the `type` column exists but the cell value is `NaN`, this returns `NaN` (see BUG-CL-007). Should use `row.get('type') or 'id_String'` to handle NaN/None/empty.

### 10.7 `_clean_value()` (Lines 319-334)

Removes surrounding quotes from property values:
1. Check for double-quote wrapper and strip
2. Check for single-quote wrapper and strip
3. Return as-is if no quotes

**Assessment**: Simple and correct. Handles the most common quoting scenarios. Does NOT handle escaped quotes within quoted values (e.g., `"value with \"nested\" quotes"`), but this is an edge case for context variable values.

### 10.8 `_update_component_stats()` (Lines 336-349)

Updates statistics and globalMap:
1. Call `_update_stats(loaded_count, loaded_count, 0)` -- sets NB_LINE and NB_LINE_OK to loaded_count, NB_LINE_REJECT to 0
2. If globalMap available, store `{id}_NB_CONTEXT_LOADED` via `global_map.put()`

**Key observation**: This method calls `_update_stats()` which increments counters (not sets them). If `_process()` is called multiple times on the same component instance (unusual but possible in streaming mode), the stats will accumulate rather than reset. This is correct behavior for streaming but could be surprising for batch mode.

---

## 11. ContextManager Duplicate Loading Path

### 11.1 context_manager.load_from_file()

The `ContextManager` class has its own `load_from_file()` method (context_manager.py lines 39-56) that duplicates some of the functionality of `ContextLoad._load_properties_context()`.

```python
def load_from_file(self, file_path: str, delimiter: str = '=') -> None:
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if delimiter in line:
                    key, value = line.split(delimiter, 1)
                    self.set(key.strip(), value.strip())
```

**Comparison with ContextLoad._load_properties_context()**:

| Feature | context_manager.load_from_file() | ContextLoad._load_properties_context() |
|---------|----------------------------------|---------------------------------------|
| `#` comment support | Yes | Yes |
| `//` comment support | **No** | Yes |
| `!` comment support | **No** | **No** |
| Value quote stripping | **No** | Yes (via `_clean_value()`) |
| Type preservation | **No** (always None type) | Yes (looks up existing type) |
| Line number tracking | **No** | Yes (for warning messages) |
| Print operations | **No** | Yes |
| Statistics tracking | **No** | Yes |
| GlobalMap update | **No** | Yes |
| Error message on missing delimiter | **No** | Yes (warning logged) |

**Risk**: If the engine uses `context_manager.load_from_file()` directly (bypassing `ContextLoad`), the behavior will differ from `ContextLoad._load_properties_context()`. The `load_from_file()` method is simpler but lacks features needed for Talend compatibility.

Note the typo in the docstring: `"Used by tCOntextLoad component"` (capital O in "COntextLoad") on line 43 of context_manager.py.

---

## 12. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-CL-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. Means standard NB_LINE/NB_LINE_OK/NB_LINE_REJECT stats never reach globalMap. |
| BUG-CL-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-CL-008 | Bug (Cross-Cutting) | `_update_global_map()` crash in error path (`base_component.py:231`) swallows original exception. When `_process()` raises, the error handler calls `_update_global_map()` which itself raises `NameError`, replacing the original meaningful exception. Caller never sees the real error. Makes ALL component failures impossible to diagnose. |
| TEST-CL-001 | Testing | Zero v1 unit tests for the ContextLoad component. All 349 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-CL-001 | Converter | No dedicated parser method -- uses deprecated `_map_component_parameters()`. Violates STANDARDS.md. |
| CONV-CL-002 | Converter | `DIE_ON_ERROR` not extracted -- engine cannot control error handling behavior. |
| ENG-CL-001 | Engine | **No warning validation for unknown/missing keys** -- eliminates critical debugging aid for context configuration issues. Talend warns for both unknown keys in input and missing context variables. |
| ENG-CL-002 | Engine | Non-standard globalMap variable `NB_CONTEXT_LOADED` instead of `NB_LINE`. Downstream components referencing standard variable get null. |
| ENG-CL-003 | Engine | Values always stringified via `str()` in DataFrame and CSV modes. Loses type fidelity for non-string values. |
| ENG-CL-004 | Engine | `!` comment prefix not supported in properties files. Lines starting with `!` are parsed as key-value pairs. |
| ENG-CL-005 | Engine | No `DIE_ON_ERROR` support. Error behavior is hardcoded to always raise on error (except missing file). |
| BUG-CL-003 | Bug | Values always stringified loses type fidelity. Python `True` becomes string `"True"`, `Decimal("3.14")` becomes `"3.14"`. |
| BUG-CL-004 | Bug | `!` comment prefix not handled in properties file reader. |
| BUG-CL-005 | Bug | CSV loading may fail with quoted headers due to pandas column name handling. |
| BUG-CL-009 | Bug | NaN in `key` column produces context variable named `'nan'`. `str(NaN)` = `'nan'`. Upstream joins/merges producing missing keys silently pollute context with a spurious `'nan'` variable. |
| BUG-CL-010 | Bug | NaN in `value` column produces context value `'nan'`. If a context variable like `database_password` has NaN value, it gets set to literal string `'nan'`, causing downstream connection failures with misleading errors. |
| BUG-CL-011 | Bug (Cross-Cutting) | Component status never reaches `SUCCESS`. `_update_global_map()` at `base_component.py:218` crashes before line 220 `self.status = ComponentStatus.SUCCESS`. Status stays `RUNNING` permanently for all components. |
| TEST-CL-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-CL-003 | Converter | `DISABLE_WARNINGS` not extracted -- warning validation not configurable (not implemented at all). |
| CONV-CL-004 | Converter | Default delimiter mismatch: converter defaults to `';'`, Talend properties format uses `'='`. |
| CONV-CL-005 | Converter | Schema type format violates STANDARDS.md (Python types instead of Talend types). |
| ENG-CL-006 | Engine | Print operations format differs from Talend (no old value display). |
| ENG-CL-007 | Engine | No backslash escape handling in properties files (`\n`, `\t`, `\\`, `\uXXXX`). |
| ENG-CL-008 | Engine | No multi-line value support in properties files (trailing `\` continuation). |
| ENG-CL-009 | Engine | CSV format requires hardcoded `key`/`value` column names. No column index fallback. |
| ENG-CL-010 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. |
| BUG-CL-006 | Bug | Duplicate code between `_process_dataframe_input()` and `_load_csv_context()`. |
| BUG-CL-007 | Bug | `_determine_value_type()` returns NaN for rows with missing type column values. |
| NAME-CL-001 | Naming | `NB_CONTEXT_LOADED` is non-standard globalMap variable name. Should use `NB_LINE`. |
| STD-CL-001 | Standards | No `_validate_config()` method. No configuration validation at initialization. |
| STD-CL-002 | Standards | Uses deprecated `_map_component_parameters()` instead of dedicated `parse_*` method. |
| STD-CL-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| SEC-CL-001 | Security | Print operations may log sensitive values (passwords, API keys) at INFO level. |
| PERF-CL-001 | Performance | Row-by-row `iterrows()` in DataFrame and CSV modes. |
| BUG-CL-012 | Bug | BOM (Byte Order Mark) handling: line 260 uses `encoding='utf-8'` which preserves BOM. First key gets `\ufeff` prefix, fails all lookups. Fix: use `'utf-8-sig'`. |
| BUG-CL-013 | Bug | `_clean_value('"')` turns single-character quoted value into empty string. `value[1:-1]` on a 1-char quoted value returns `''`. |
| BUG-CL-014 | Bug | Thread safety: `ContextManager.context` and `context_types` are plain dicts with no locking. Parallel subjobs can interleave `set()`/`resolve_string()` calls, causing logical race conditions. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-CL-011 | Engine | No support for escaped delimiter in property keys (e.g., `key\=with\=equals`). |
| ENG-CL-012 | Engine | No support for whitespace-only delimiter in properties files. |
| NAME-CL-002 | Naming | `filepath` config key differs from Talend's `CONTEXTFILE` (consistent with v1 standards). |
| SEC-CL-002 | Security | No path traversal protection on `filepath`. |
| DBG-CL-001 | Debug | Debug logging on line 120 logs entire DataFrame contents -- may expose sensitive data. |
| PERF-CL-002 | Performance | `context_manager.get_type()` called per-row with DEBUG logging overhead. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 3 bugs (cross-cutting), 1 testing |
| P1 | 14 | 2 converter, 5 engine, 6 bugs, 1 testing |
| P2 | 19 | 3 converter, 5 engine, 5 bugs, 1 naming, 3 standards, 1 security, 1 performance |
| P3 | 6 | 2 engine, 1 naming, 1 security, 1 debug, 1 performance |
| **Total** | **43** | |

---

## 13. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-CL-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-CL-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-CL-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic DataFrame input, properties file loading, CSV file loading, missing file handling (both error modes), empty filepath, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Add `!` comment prefix support** (BUG-CL-004, ENG-CL-004): In `_load_properties_context()` line 265, change:
   ```python
   if not line or line.startswith('#') or line.startswith('//'):
   ```
   to:
   ```python
   if not line or line.startswith('#') or line.startswith('!') or line.startswith('//'):
   ```
   **Impact**: Fixes properties file loading for files using `!` comments. **Risk**: Very low.

5. **Set standard `NB_LINE` globalMap variable** (ENG-CL-002): In `_update_component_stats()`, add:
   ```python
   self.global_map.put(f"{self.id}_NB_LINE", loaded_count)
   ```
   alongside the existing `NB_CONTEXT_LOADED` for backward compatibility. **Impact**: Downstream Talend patterns work correctly. **Risk**: Very low.

6. **Wrap `_update_global_map()` call in error path with try/except** (BUG-CL-008): In `base_component.py` `execute()`, the error handler must not let `_update_global_map()` crash mask the original exception. Wrap the call:
   ```python
   except Exception as original_error:
       try:
           self._update_global_map()
       except Exception:
           pass  # Do not mask the original error
       raise original_error
   ```
   Alternatively, fix BUG-CL-001 first (which eliminates the crash), but the defensive wrapper should remain regardless. **Impact**: All component error messages become diagnosable again. **Risk**: Very low.

7. **Guard against NaN in key and value columns** (BUG-CL-009, BUG-CL-010): In `_process_dataframe_input()` and `_load_csv_context()`, before processing each row, check for NaN:
   ```python
   key = row['key']
   if pd.isna(key):
       logger.warning(f"Component {self.id}: Skipping row with NaN key")
       continue
   value = row['value']
   if pd.isna(value):
       value = ''  # or skip row, depending on desired behavior
   ```
   Also add `keep_default_na=False` to `pd.read_csv()` calls. **Impact**: Prevents silent context pollution from upstream NaN values. **Risk**: Low (adds validation that was missing).

8. **Ensure status reaches SUCCESS even when `_update_global_map()` fails** (BUG-CL-011): Move `self.status = ComponentStatus.SUCCESS` BEFORE the `_update_global_map()` call in the success path of `execute()`, or wrap `_update_global_map()` in a try/except that does not prevent the status update. **Impact**: Component lifecycle tracking works correctly. **Risk**: Very low.

### Short-Term (Hardening)

9. **Implement warning validation** (ENG-CL-001): After loading all context variables, compare the set of loaded keys against the set of existing context keys:
   ```python
   loaded_keys = set(...)
   existing_keys = set(self.context_manager.get_all().keys())
   unknown_keys = loaded_keys - existing_keys
   missing_keys = existing_keys - loaded_keys
   if unknown_keys:
       logger.warning(f"Keys from input not defined in context: {unknown_keys}")
   if missing_keys:
       logger.warning(f"Context variables not set by input: {missing_keys}")
   ```
   Guard with a `disable_warnings` config flag. **Impact**: Restores Talend debugging aid. **Risk**: Low.

10. **Extract `DIE_ON_ERROR` in converter** (CONV-CL-002): Add `'die_on_error': config_raw.get('DIE_ON_ERROR', False)` to the `tContextLoad` mapping in `_map_component_parameters()`. Then in the engine, wrap error-raising code with `if die_on_error: raise` / `else: logger.error(...)`. **Impact**: Matches Talend error handling behavior. **Risk**: Low.

11. **Stop stringifying values unnecessarily** (BUG-CL-003, ENG-CL-003): In `_process_dataframe_input()` and `_load_csv_context()`, change:
   ```python
   value = str(row['value'])
   ```
   to:
   ```python
   value = row['value']
   if pd.isna(value):
       value = ''
   ```
   This preserves the original type when no type conversion is needed and allows `context_manager.set()` to handle the value directly. **Impact**: Improves type fidelity. **Risk**: Medium (behavior change for downstream code expecting string values).

12. **Fix `_convert_type()` in ContextManager** (Section 9.2): The type mapping uses string values (`'str'`, `'int'`) instead of callable types (`str`, `int`). Change:
   ```python
   'id_Integer': 'int',
   ```
   to:
   ```python
   'id_Integer': int,
   ```
   for ALL entries in the mapping. This enables actual type conversion instead of silent fallback to string. **Impact**: Fixes type conversion for ALL context variables. **Risk**: Medium (may expose type conversion errors that were previously silently swallowed).

13. **Create dedicated converter parser** (CONV-CL-001): Replace the `_map_component_parameters()` call with a dedicated `parse_tcontextload(node, component)` method in `component_parser.py`. Extract `DISABLE_WARNINGS`, `DIE_ON_ERROR`, and any other missing parameters. Register in `converter.py` with an `elif component_type == 'tContextLoad'` branch.

14. **Fix default delimiter** (CONV-CL-004): Change the default for `FIELDSEPARATOR` from `';'` to `'='` in the `tContextLoad` mapping, since the properties file format uses `=` as the standard key-value delimiter.

15. **Add `keep_default_na=False` to CSV loading** (Section 10.4): In `_load_csv_context()`, change:
    ```python
    df = pd.read_csv(filepath, sep=csv_separator)
    ```
    to:
    ```python
    df = pd.read_csv(filepath, sep=csv_separator, keep_default_na=False)
    ```
    This prevents "NA", "NULL", "None" values from being interpreted as NaN.

16. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-CL-010): In the catch-all handler in `_process_file_input()`, add:
    ```python
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    ```

17. **Use `utf-8-sig` encoding for properties files** (BUG-CL-012): In `_load_properties_context()` line 260, change `encoding='utf-8'` to `encoding='utf-8-sig'` to automatically strip BOM if present. **Impact**: Fixes first-key corruption for BOM-prefixed files. **Risk**: Very low (`utf-8-sig` is fully backward-compatible with plain UTF-8 files).

18. **Fix `_clean_value()` edge case for single-char quoted values** (BUG-CL-013): Add a length check before stripping quotes:
    ```python
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    ```
    **Impact**: Prevents single-character quote values from becoming empty strings. **Risk**: Very low.

19. **Add threading lock to ContextManager** (BUG-CL-014): Add a `threading.Lock` to `ContextManager` and acquire it around `set()` and `resolve_string()` operations that touch both `context` and `context_types` dicts. **Impact**: Prevents logical race conditions in parallel subjob execution. **Risk**: Low (small performance overhead from lock acquisition).

### Long-Term (Optimization)

20. **Implement backslash escape handling** (ENG-CL-007): Support `\n`, `\t`, `\\`, `\uXXXX` escape sequences in properties file values. Use Python's `codecs.decode(value, 'unicode_escape')` or a custom parser for Java-compatible escaping.

21. **Implement multi-line value support** (ENG-CL-008): Detect trailing backslash in properties file lines and concatenate with the next line. This requires a look-ahead in the line iterator.

22. **Refactor duplicate code** (BUG-CL-006): Extract the common row-processing logic from `_process_dataframe_input()` and `_load_csv_context()` into a shared `_load_from_dataframe(df, print_operations)` method. Both methods can then delegate to this shared implementation.

23. **Implement print operations old-value display** (ENG-CL-006): Before calling `context_manager.set()`, read the current value:
    ```python
    old_value = self.context_manager.get(key)
    self.context_manager.set(key, value, value_type)
    if print_operations:
        logger.info(f"Context variable '{key}' reassigned: '{old_value}' -> '{value}'")
    ```

24. **Add sensitive value masking** (SEC-CL-001): When `print_operations=True`, mask values for keys matching patterns like `*password*`, `*secret*`, `*key*`, `*token*`. Display masked values as `"****"` instead of the actual value.

25. **Add NaN handling in `_determine_value_type()`** (BUG-CL-007): Change:
    ```python
    return row.get('type', 'id_String')
    ```
    to:
    ```python
    type_val = row.get('type')
    return type_val if pd.notna(type_val) and type_val else 'id_String'
    ```

26. **Add encoding parameter for CSV loading**: Pass an `encoding` config parameter to `pd.read_csv()` in `_load_csv_context()` to support non-UTF-8 CSV context files.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 241-250
elif component_type == 'tContextLoad':
    return {
        'filepath': config_raw.get('CONTEXTFILE', ''),
        'format': config_raw.get('FORMAT', 'properties'),
        'delimiter': config_raw.get('FIELDSEPARATOR', ';'),
        'csv_separator': config_raw.get('CSV_SEPARATOR', ','),
        'print_operations': config_raw.get('PRINT_OPERATIONS', False),
        'error_if_not_exists': config_raw.get('ERROR_IF_NOT_EXISTS', True)
    }
```

**Notes on this code**:
- Line 244: `CONTEXTFILE` is the Talend XML parameter name for the context file path. If the Talend job uses `FILENAME` instead (older versions), this mapping will miss it.
- Line 246: Default `';'` for `FIELDSEPARATOR` is the Talend general default, but properties files typically use `'='`. The converter should differentiate based on `FORMAT`.
- Line 248: `PRINT_OPERATIONS` is a CHECK field type, so it is pre-converted to boolean by the generic parameter loop (line 445-446 of `parse_base_component()`).
- Line 249: `ERROR_IF_NOT_EXISTS` may not be a standard CHECK field -- it could be a string `"true"/"false"`. The converter may store it as a string instead of boolean, depending on the XML field attribute.

---

## Appendix B: Engine Class Structure

```
ContextLoad (BaseComponent)
    Inherits:
        id, config, global_map, context_manager
        execute(), _update_global_map(), _update_stats(), validate_schema()
        _resolve_java_expressions(), _auto_select_mode()

    Methods:
        _process(input_data) -> Dict[str, Any]          # Main entry: routes to DF or file
        _process_dataframe_input(input_data, print_ops)  # Load from DataFrame
        _process_file_input(filepath, format, ...)       # Load from file
        _load_csv_context(filepath, sep, print_ops)      # CSV file reader
        _load_properties_context(filepath, delim, print) # Properties file reader
        _determine_value_type(row, key, columns)         # Type determination
        _clean_value(value) -> str                       # Quote stripping
        _update_component_stats(loaded_count)             # Stats + globalMap update
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `CONTEXTFILE` | `filepath` | Mapped | -- |
| `FORMAT` | `format` | Mapped | -- |
| `FIELDSEPARATOR` | `delimiter` | Mapped | -- (fix default to `=`) |
| `CSV_SEPARATOR` | `csv_separator` | Mapped | -- |
| `PRINT_OPERATIONS` | `print_operations` | Mapped | -- |
| `ERROR_IF_NOT_EXISTS` | `error_if_not_exists` | Mapped | -- |
| `DISABLE_WARNINGS` | `disable_warnings` | **Not Mapped** | P2 |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Type Conversion Analysis

### ContextManager._convert_type() Type Mapping

| Type String | Mapping Value | Callable? | Works? | Notes |
|-------------|--------------|-----------|--------|-------|
| `id_String` | `'str'` (string) | No | **No** | Falls to `except`, returns original value |
| `id_Integer` | `'int'` (string) | No | **No** | Falls to `except`, returns original value |
| `id_Long` | `'int'` (string) | No | **No** | Same as id_Integer |
| `id_Float` | `'float'` (string) | No | **No** | Falls to `except`, returns original value |
| `id_Double` | `'float'` (string) | No | **No** | Same as id_Float |
| `id_Boolean` | `lambda` | Yes | **Yes** | Works correctly |
| `id_Date` | `'str'` (string) | No | **No** | Falls to `except`, returns original value |
| `id_BigDecimal` | `'Decimal'` (string) | No | **No** | Falls to `except`, returns original value |
| `str` | `'str'` (string) | No | **No** | Falls to `except`, returns original value |
| `int` | `'int'` (string) | No | **No** | Falls to `except`, returns original value |
| `float` | `'float'` (string) | No | **No** | Falls to `except`, returns original value |
| `bool` | `lambda` | Yes | **Yes** | Works correctly |
| `Decimal` | `'Decimal'` (string) | No | **No** | Falls to `except`, returns original value |
| `datetime` | `str` (type) | Yes | **Yes** | Works correctly (converts to string) |
| `object` | `str` (type) | Yes | **Yes** | Default fallback works (converts to string) |
| (unknown) | `str` (type) | Yes | **Yes** | Default fallback works |

**Summary**: Of 16 type mappings, only 4 work correctly (`id_Boolean`, `bool`, `datetime`, `object`). The remaining 12 silently fall through to the `except` handler, returning the original value unchanged. This means typed context variables (Integer, Float, String, Date, BigDecimal) are NEVER actually converted -- they remain as their input type (usually string from file loading).

**Root cause**: The type mapping stores string representations of type names (`'int'`, `'str'`, `'float'`) instead of the actual type objects (`int`, `str`, `float`). The code then tries to call these strings as functions, which fails with `TypeError`.

**Fix**: Replace string values with actual type constructors:
```python
type_mapping = {
    'id_String': str,
    'id_Integer': int,
    'id_Long': int,
    'id_Float': float,
    'id_Double': float,
    'id_Boolean': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'id_Date': str,
    'id_BigDecimal': Decimal,
    'str': str,
    'int': int,
    'float': float,
    'bool': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'Decimal': Decimal,
    'datetime': str,
    'object': str
}
```

---

## Appendix E: Edge Case Analysis

### Edge Case 1: Empty DataFrame input

| Aspect | Detail |
|--------|--------|
| **Talend** | 0 context variables loaded. NB_LINE=0. No error. |
| **V1** | Empty DataFrame has columns, `iterrows()` yields 0 rows. `loaded_count=0`. Returns empty DataFrame. |
| **Verdict** | CORRECT |

### Edge Case 2: DataFrame with NaN values

| Aspect | Detail |
|--------|--------|
| **Talend** | NaN/null values in `value` column are typically handled as empty strings. |
| **V1** | `str(row['value'])` converts NaN to `"nan"` (string). Stored as context variable with value `"nan"`. |
| **Verdict** | GAP -- NaN should be converted to empty string or null, not the string `"nan"`. |

### Edge Case 3: Properties file with `=` in value

| Aspect | Detail |
|--------|--------|
| **Talend** | `url=jdbc:oracle:thin:@host:1521:SID` -> key=`url`, value=`jdbc:oracle:thin:@host:1521:SID`. |
| **V1** | `line.split(delimiter, 1)` splits on first `=` only. Correct. |
| **Verdict** | CORRECT |

### Edge Case 4: Properties file with empty value

| Aspect | Detail |
|--------|--------|
| **Talend** | `password=` -> key=`password`, value=`` (empty string). |
| **V1** | `line.split('=', 1)` returns `['password', '']`. `_clean_value('')` returns `''`. Correct. |
| **Verdict** | CORRECT |

### Edge Case 5: Properties file with whitespace around delimiter

| Aspect | Detail |
|--------|--------|
| **Talend** | `host = localhost` -> key=`host`, value=`localhost` (whitespace trimmed). |
| **V1** | `key = key.strip()` (line 271) trims key whitespace. `value = self._clean_value(value.strip())` (line 272) trims value whitespace. |
| **Verdict** | CORRECT |

### Edge Case 6: Properties file with `!` comment

| Aspect | Detail |
|--------|--------|
| **Talend** | `! This is a comment` -> skipped. |
| **V1** | Not handled. `!` lines are treated as data. If `=` is not in the line, a warning is logged. If `=` is in the line (e.g., `! key=value`), it's loaded as a context variable with key `! key` and value `value`. |
| **Verdict** | GAP -- `!` comment prefix not supported. |

### Edge Case 7: DataFrame with type column containing NaN

| Aspect | Detail |
|--------|--------|
| **Talend** | Missing type defaults to String. |
| **V1** | `_determine_value_type()` returns NaN from `row.get('type', 'id_String')`. NaN is passed as type to `context_manager.set()`, which calls `_convert_type(value, NaN)`. Type mapping lookup fails, defaults to `str`. |
| **Verdict** | PARTIAL -- works by accident (NaN default -> str fallback), but the NaN type is stored in `context_types` dict, which could cause issues downstream. |

### Edge Case 8: CSV file with "NA" as a value

| Aspect | Detail |
|--------|--------|
| **Talend** | Stores literal string "NA". |
| **V1** | `pd.read_csv()` without `keep_default_na=False` converts "NA" to NaN. `str(NaN)` becomes `"nan"`. |
| **Verdict** | GAP -- "NA" values corrupted to "nan". |

### Edge Case 9: Properties file with Unicode characters

| Aspect | Detail |
|--------|--------|
| **Talend** | Java properties files use ISO-8859-1 encoding with `\uXXXX` escapes for non-Latin characters. |
| **V1** | File opened with UTF-8 encoding. Direct Unicode characters in UTF-8 files work correctly. `\uXXXX` escapes are NOT processed. |
| **Verdict** | PARTIAL -- works for UTF-8 files with direct Unicode. Fails for ISO-8859-1 files or files using `\uXXXX` escapes. |

### Edge Case 10: Properties file with trailing backslash (line continuation)

| Aspect | Detail |
|--------|--------|
| **Talend** | `message=Hello \` + `World` -> key=`message`, value=`Hello World`. |
| **V1** | `message=Hello \` -> key=`message`, value=`Hello \` (includes trailing backslash). Next line `World` has no delimiter, logs warning. |
| **Verdict** | GAP -- multi-line values not supported. |

### Edge Case 11: Multiple tContextLoad components in same job

| Aspect | Detail |
|--------|--------|
| **Talend** | Later loads override earlier ones for overlapping keys. All context variables from all loads are available. |
| **V1** | Each ContextLoad instance calls `context_manager.set()`, which overwrites existing values. Correct override semantics. |
| **Verdict** | CORRECT |

### Edge Case 12: context_manager is None

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A (context always exists in Talend runtime). |
| **V1** | `if self.context_manager:` guards on lines 137, 235, 281 silently skip context setting. Variables are "loaded" (counter incremented) but not stored. `_determine_value_type()` returns `'id_String'` when context_manager is None (line 310 guard). |
| **Verdict** | DEGRADED -- silent no-op. Should log a warning that context_manager is not available. |

### Edge Case 13: Properties file with blank lines interspersed

| Aspect | Detail |
|--------|--------|
| **Talend** | Blank lines are ignored. |
| **V1** | `if not line` (after strip) catches blank lines. Correct. |
| **Verdict** | CORRECT |

### Edge Case 14: CSV with different column order

| Aspect | Detail |
|--------|--------|
| **Talend** | Column names matter, not order. |
| **V1** | `'key' in df.columns` and `'value' in df.columns` checks are name-based, not position-based. Order does not matter. |
| **Verdict** | CORRECT |

### Edge Case 15: Properties file with colon delimiter

| Aspect | Detail |
|--------|--------|
| **Talend** | Java properties files support both `=` and `:` as key-value delimiters. |
| **V1** | Only the configured `delimiter` is supported. If delimiter is `=`, colon-separated lines are treated as single values. |
| **Verdict** | PARTIAL -- works if explicitly configured with `:` delimiter. Does not auto-detect like Java properties. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `ContextLoad`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-CL-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-CL-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| STD-CL-001 | **P2** | `base_component.py` | No standard lifecycle call to `_validate_config()`. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-CL-001 -- `_update_global_map()` undefined variable

**File**: `src/v1/engine/base_component.py`
**Line**: 304

**Current code (broken)**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

**Fix**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-CL-002 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Line**: 26-28

**Current code (broken)**:
```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Fix**:
```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: BUG-CL-004 -- Add `!` comment prefix support

**File**: `src/v1/engine/components/context/context_load.py`
**Line**: 265

**Current**:
```python
if not line or line.startswith('#') or line.startswith('//'):
    continue
```

**Fix**:
```python
if not line or line.startswith('#') or line.startswith('!') or line.startswith('//'):
    continue
```

**Impact**: Properties files using `!` as comment prefix are handled correctly. **Risk**: Very low.

---

### Fix Guide: ENG-CL-002 -- Set standard NB_LINE globalMap variable

**File**: `src/v1/engine/components/context/context_load.py`
**Lines**: 336-349

**Current**:
```python
def _update_component_stats(self, loaded_count: int) -> None:
    self._update_stats(loaded_count, loaded_count, 0)
    if self.global_map:
        self.global_map.put(f"{self.id}_NB_CONTEXT_LOADED", loaded_count)
```

**Fix**:
```python
def _update_component_stats(self, loaded_count: int) -> None:
    self._update_stats(loaded_count, loaded_count, 0)
    if self.global_map:
        self.global_map.put(f"{self.id}_NB_CONTEXT_LOADED", loaded_count)
        self.global_map.put(f"{self.id}_NB_LINE", loaded_count)
        self.global_map.put(f"{self.id}_NB_LINE_OK", loaded_count)
        self.global_map.put(f"{self.id}_NB_LINE_REJECT", 0)
```

**Impact**: Downstream components using standard `{id}_NB_LINE` pattern can access the count. **Risk**: Very low.

---

### Fix Guide: ENG-CL-001 -- Implementing warning validation

**File**: `src/v1/engine/components/context/context_load.py`

Add a new method and call it after context loading:

```python
def _validate_context_coverage(self, loaded_keys: set, disable_warnings: bool) -> None:
    """Validate loaded keys against existing context variables (Talend behavior)"""
    if disable_warnings or not self.context_manager:
        return

    existing_keys = set(self.context_manager.get_all().keys())

    # Keys in input but not in context
    unknown_keys = loaded_keys - existing_keys
    for key in unknown_keys:
        logger.warning(
            f"Component {self.id}: Key '{key}' from input flow "
            f"is not defined in the context"
        )

    # Context variables not in input
    missing_keys = existing_keys - loaded_keys
    for key in missing_keys:
        logger.warning(
            f"Component {self.id}: Context variable '{key}' "
            f"is not set in the input flow"
        )
```

Then call at the end of `_process_dataframe_input()` and `_load_properties_context()` / `_load_csv_context()`.

**Impact**: Restores Talend validation behavior. **Risk**: Low (warnings only, no behavior change).

---

### Fix Guide: Context Manager _convert_type() fix

**File**: `src/v1/engine/context_manager.py`
**Lines**: 168-186

**Current (broken)**:
```python
type_mapping = {
    'id_String': 'str',
    'id_Integer': 'int',
    'id_Long': 'int',
    'id_Float': 'float',
    'id_Double': 'float',
    'id_Boolean': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'id_Date': 'str',
    'id_BigDecimal': 'Decimal',
    'str': 'str',
    'int': 'int',
    'float': 'float',
    'bool': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'Decimal': 'Decimal',
    'datetime': str,
    'object': str
}
```

**Fix**:
```python
from decimal import Decimal

type_mapping = {
    'id_String': str,
    'id_Integer': int,
    'id_Long': int,
    'id_Float': float,
    'id_Double': float,
    'id_Boolean': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'id_Date': str,
    'id_BigDecimal': Decimal,
    'str': str,
    'int': int,
    'float': float,
    'bool': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'Decimal': Decimal,
    'datetime': str,
    'object': str
}
```

**Note**: `Decimal` is already imported at the top of `context_manager.py` (line 5: `from decimal import Decimal`).

**Impact**: Fixes type conversion for ALL context variables across ALL components that use ContextManager. **Risk**: Medium -- may expose previously hidden type conversion errors. Existing code that relies on values being strings may break if values are now integers or floats. Recommend thorough testing after this change.

---

## Appendix H: Comparison with ContextManager.load_from_file()

| Feature | ContextLoad._load_properties_context() | ContextManager.load_from_file() |
|---------|---------------------------------------|--------------------------------|
| **File** | context_load.py:246-292 | context_manager.py:39-56 |
| **# comment** | Yes (line 265) | Yes (line 48) |
| **// comment** | Yes (line 265) | No |
| **! comment** | No | No |
| **Value cleaning** | Yes (quotes stripped) | No |
| **Type preservation** | Yes (looks up existing type) | No |
| **Statistics** | Yes (loaded_count) | No |
| **GlobalMap** | Yes (NB_CONTEXT_LOADED) | No |
| **Print operations** | Yes (configurable logging) | No |
| **Error handling** | Robust (try/except/re-raise) | Basic (try/except/raise) |
| **Line number tracking** | Yes (warning messages) | No |
| **Encoding** | UTF-8 hardcoded | UTF-8 hardcoded |

**Recommendation**: Consolidate to a single implementation. `ContextLoad._load_properties_context()` is the more complete implementation. `ContextManager.load_from_file()` should either be removed or updated to delegate to `ContextLoad`.

---

## Appendix I: Typical Talend Job Patterns Using tContextLoad

### Pattern 1: File-Based Context Loading

```
tFileInputDelimited (reads context.properties with '=' separator)
    |
    v [FLOW: key, value columns]
tContextLoad (loads key-value pairs into context)
    |
    v [SUBJOB_OK trigger]
tFileInputDelimited (reads data file using context.filepath)
    |
    v [FLOW: data columns]
tFileOutputDelimited (writes output using context.output_dir)
```

**V1 Support**: Fully supported. The first `tFileInputDelimited` reads the properties file, produces a DataFrame with `key` and `value` columns, which flows into `ContextLoad` via the DataFrame input path. The SUBJOB_OK trigger ensures context is loaded before data processing begins.

### Pattern 2: Database-Based Context Loading

```
tMySqlInput (SELECT param_name as key, param_value as value FROM config)
    |
    v [FLOW: key, value columns]
tContextLoad (loads database rows into context)
    |
    v [SUBJOB_OK trigger]
[rest of job using context variables]
```

**V1 Support**: Supported if the upstream database component produces a DataFrame with `key` and `value` columns. The `tMap` intermediate step (common in Talend) would need to rename columns appropriately.

### Pattern 3: Implicit Context Loading (File-Based)

```
[Job startup]
    |
    v [Implicit context load from /config/context.properties]
tContextLoad (standalone, reads file directly)
    |
    v [SUBJOB_OK trigger]
[rest of job]
```

**V1 Support**: Supported via the file input path (`_process_file_input()`). The `filepath`, `format`, and `delimiter` config parameters control file-based loading.

### Pattern 4: Multi-Environment Context

```
tFileInputDelimited (reads ${context.env}_context.properties)
    |
    v
tContextLoad
```

**V1 Support**: Depends on context variable resolution in the filepath. If `${context.env}` is resolved before ContextLoad executes (via `BaseComponent.execute()` -> `context_manager.resolve_dict()`), this works correctly. The `env` variable must be set BEFORE this ContextLoad component runs.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs with typed context variables (Integer, Float) | **High** | Jobs expecting numeric context values | Fix `_convert_type()` in ContextManager to use actual type constructors |
| Jobs relying on `NB_LINE` globalMap variable | **High** | Jobs with audit logic checking `tContextLoad_1_NB_LINE` | Set standard `NB_LINE` in addition to `NB_CONTEXT_LOADED` |
| Jobs with `!` comments in properties files | **High** | Jobs using Java-style properties files | Add `!` comment prefix support |
| Jobs relying on warning messages for debugging | **Medium** | Jobs where context configuration validation is important | Implement warning validation |
| Jobs with `DIE_ON_ERROR=false` expecting graceful degradation | **Medium** | Jobs with error recovery logic | Extract and implement `DIE_ON_ERROR` parameter |
| Jobs with "NA"/"NULL" string values in CSV context | **Medium** | Jobs loading from CSV with special string values | Add `keep_default_na=False` to CSV loading |
| Jobs with ISO-8859-1 properties files | **Medium** | European/legacy jobs | Add encoding parameter support |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs with simple string context variables | Low | String storage works correctly (no type conversion needed) |
| Jobs with `#` comments in properties files | Low | `#` comment handling is implemented correctly |
| Jobs loading from upstream DataFrame | Low | DataFrame input path works correctly for basic use cases |
| Jobs with error_if_not_exists=False | Low | Graceful missing file handling works correctly |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting). Fix `_convert_type()` in ContextManager. Run existing converted jobs to verify basic context loading.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which context variables are typed, which use `!` comments, and which rely on `NB_LINE`.
3. **Phase 3**: Implement P1 features required by target jobs (warning validation, `!` comments, standard globalMap variables).
4. **Phase 4**: Parallel-run migrated jobs. Compare loaded context values between Talend and v1 engine.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix K: Properties File Format Specification

The Java `.properties` file format is defined in the `java.util.Properties` class documentation. Key rules that apply to tContextLoad:

### Comment Lines
- Lines starting with `#` are comments (supported by v1)
- Lines starting with `!` are comments (**NOT supported by v1**)
- Comment characters must be the first non-whitespace character on the line

### Key-Value Separators
- `=` (equals sign) is a separator (supported by v1 when configured)
- `:` (colon) is a separator (**NOT auto-detected by v1**, must be configured)
- Whitespace (space or tab) is a separator (**NOT supported by v1**)
- Only the first occurrence of the separator is significant
- Whitespace around the separator is ignored

### Multi-Line Values
- A line ending with `\` (backslash) continues on the next line (**NOT supported by v1**)
- Leading whitespace on continuation lines is ignored
- Example:
  ```
  message=Hello \
          World
  ```
  Produces: `message=Hello World`

### Escape Sequences
- `\n` -> newline (**NOT supported by v1**)
- `\t` -> tab (**NOT supported by v1**)
- `\\` -> backslash (**NOT supported by v1**)
- `\uXXXX` -> Unicode character (**NOT supported by v1**)
- `\=` -> literal equals in key (**NOT supported by v1**)
- `\:` -> literal colon in key (**NOT supported by v1**)
- `\ ` -> literal space in key (**NOT supported by v1**)

### Encoding
- Java properties files use **ISO-8859-1** (Latin-1) encoding by default
- Non-Latin-1 characters must be expressed as `\uXXXX` escapes
- The v1 engine uses **UTF-8** encoding, which is a behavioral difference

### Blank Lines
- Blank lines (empty or whitespace-only after trimming) are ignored (supported by v1)

---

## Appendix L: CSV Context File Format

When `format='csv'`, the context file is expected to be a standard CSV file with a header row:

### Required Columns
- `key` (String): Context variable name
- `value` (String): Context variable value

### Optional Columns
- `type` (String): Talend type identifier (e.g., `id_String`, `id_Integer`)
- Any other columns are ignored

### Example
```csv
key,value,type
host,localhost,id_String
port,5432,id_Integer
debug,true,id_Boolean
password,secret123,id_String
```

### V1 Behavior
- Reads with `pd.read_csv(filepath, sep=csv_separator)` -- default separator is `,`
- Column names must match exactly (`key`, `value`, case-sensitive)
- No `keep_default_na=False` -- "NA", "NULL", "None" values are interpreted as NaN
- No encoding parameter -- uses system default (usually UTF-8)
- Values are stringified before storage (BUG-CL-003)

---

## Appendix M: ContextLoad vs ContextManager.load_from_file() Decision Matrix

| Use Case | Which to Use | Notes |
|----------|-------------|-------|
| Talend job with tContextLoad component | `ContextLoad._process()` | Full feature set, statistics, globalMap |
| Job startup context initialization | `ContextManager.load_context()` | For JSON-based initial context |
| Implicit context loading from file | `ContextLoad._process_file_input()` | Preferred over `ContextManager.load_from_file()` |
| Simple scripting/testing | `ContextManager.load_from_file()` | Simpler API, fewer dependencies |

**Recommendation**: For production use, always prefer the `ContextLoad` component over `ContextManager.load_from_file()`. The component provides statistics tracking, globalMap integration, print operations, and better error handling.

---

## Appendix N: Complete Engine Method Call Graph

```
BaseComponent.execute(input_data)
    |
    +-> _resolve_java_expressions()          # Resolve {{java}} markers in config
    +-> context_manager.resolve_dict(config)  # Resolve ${context.var} in config
    +-> _auto_select_mode(input_data)         # Determine batch vs streaming
    +-> _execute_batch(input_data)
    |       |
    |       +-> ContextLoad._process(input_data)
    |               |
    |               +-- [if input_data is not None] --> _process_dataframe_input()
    |               |       |
    |               |       +-> Validate 'key' and 'value' columns
    |               |       +-> for _, row in input_data.iterrows():
    |               |       |       +-> _determine_value_type(row, key, columns)
    |               |       |       +-> context_manager.set(key, value, value_type)
    |               |       |       +->     _convert_type(value, value_type) [if type provided]
    |               |       |       +-> Log if print_operations
    |               |       +-> _update_component_stats(loaded_count)
    |               |       |       +-> _update_stats(loaded_count, loaded_count, 0)
    |               |       |       +-> global_map.put(NB_CONTEXT_LOADED)
    |               |       +-> return {'main': pd.DataFrame()}
    |               |
    |               +-- [if input_data is None] --> _process_file_input()
    |                       |
    |                       +-> Validate filepath
    |                       +-> os.path.exists(filepath)
    |                       +-- [if format == 'csv'] --> _load_csv_context()
    |                       |       +-> pd.read_csv(filepath, sep=csv_separator)
    |                       |       +-> Validate 'key' and 'value' columns
    |                       |       +-> [same row processing as DataFrame]
    |                       |
    |                       +-- [else] --> _load_properties_context()
    |                       |       +-> open(filepath, 'r', encoding='utf-8')
    |                       |       +-> for line_num, line in enumerate(f, 1):
    |                       |       |       +-> Skip empty, #, // comments
    |                       |       |       +-> split(delimiter, 1)
    |                       |       |       +-> _clean_value(value)
    |                       |       |       +-> context_manager.get_type(key)
    |                       |       |       +-> context_manager.set(key, value, type)
    |                       |       +-> return loaded_count
    |                       |
    |                       +-> _update_component_stats(loaded_count)
    |                       +-> return {'main': pd.DataFrame()}
    |
    +-> _update_global_map()                  # BUG: crashes due to undefined variable
    +-> result['stats'] = self.stats.copy()
    +-> return result
```

---

## Appendix O: Recommended Dedicated Parser Implementation

```python
def parse_tcontextload(self, node, component: Dict) -> Dict:
    """
    Parse tContextLoad specific configuration from Talend XML node.

    Extracts ALL Talend parameters for context loading.

    Talend Parameters:
        CONTEXTFILE (str): Context file path. Optional when input flow used.
        FORMAT (str): File format ('properties' or 'csv'). Default 'properties'.
        FIELDSEPARATOR (str): Key-value delimiter. Default '=' for properties.
        CSV_SEPARATOR (str): CSV separator. Default ','.
        PRINT_OPERATIONS (bool): Log context assignments. Default false.
        ERROR_IF_NOT_EXISTS (bool): Error on missing file. Default true.
        DISABLE_WARNINGS (bool): Suppress validation warnings. Default false.
        DIE_ON_ERROR (bool): Fatal error handling. Default false.
    """
    config = {}

    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')
        field = param.get('field')

        if field == 'CHECK':
            value = value.lower() == 'true'

        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        if name == 'CONTEXTFILE':
            config['filepath'] = value
        elif name == 'FORMAT':
            config['format'] = value if value else 'properties'
        elif name == 'FIELDSEPARATOR':
            config['delimiter'] = value if value else '='
        elif name == 'CSV_SEPARATOR':
            config['csv_separator'] = value if value else ','
        elif name == 'PRINT_OPERATIONS':
            config['print_operations'] = value
        elif name == 'ERROR_IF_NOT_EXISTS':
            config['error_if_not_exists'] = value
        elif name == 'DISABLE_WARNINGS':
            config['disable_warnings'] = value
        elif name == 'DIE_ON_ERROR':
            config['die_on_error'] = value

    # Apply defaults
    config.setdefault('filepath', '')
    config.setdefault('format', 'properties')
    config.setdefault('delimiter', '=')
    config.setdefault('csv_separator', ',')
    config.setdefault('print_operations', False)
    config.setdefault('error_if_not_exists', True)
    config.setdefault('disable_warnings', False)
    config.setdefault('die_on_error', False)

    component['config'] = config
    return component
```

Register in `converter.py:_parse_component()`:
```python
elif component_type == 'tContextLoad':
    component = self.component_parser.parse_tcontextload(node, component)
```

---

## Appendix P: Relationship to Implicit Context Load Feature

Talend's Implicit Context Load is a job-level feature that automatically loads context variables at job startup. It is configured in the Job Settings (not via a component) and uses parameters similar to tContextLoad:

| Implicit Context Setting | tContextLoad Equivalent | V1 Handling |
|--------------------------|------------------------|-------------|
| `IMPLICIT_CONTEXT_LOAD_ENABLED` | N/A (always enabled when component exists) | N/A |
| `IMPLICIT_CONTEXT_LOAD_FILE` | `CONTEXTFILE` | Handled via `filepath` config |
| `IMPLICIT_CONTEXT_LOAD_FORMAT` | `FORMAT` | Handled via `format` config |
| `IMPLICIT_CONTEXT_LOAD_SEPARATOR` | `FIELDSEPARATOR` | Handled via `delimiter` config |
| `IMPLICIT_CONTEXT_LOAD_ERROR` | `ERROR_IF_NOT_EXISTS` | Handled via `error_if_not_exists` config |
| `IMPLICIT_CONTEXT_LOAD_PRINT` | `PRINT_OPERATIONS` | Handled via `print_operations` config |

**V1 approach**: The v1 engine does not distinguish between explicit tContextLoad components and implicit context loading. Both are handled by the same `ContextLoad` class. For implicit loading, the engine should create a `ContextLoad` component instance at job startup and execute it before any other components. This is handled by the engine's job orchestration logic (outside the scope of this component audit).
