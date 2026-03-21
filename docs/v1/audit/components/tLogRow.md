# Audit Report: tLogRow / LogRow

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tLogRow` |
| **V1 Engine Class** | `LogRow` |
| **Engine File** | `src/v1/engine/components/transform/log_row.py` (232 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (falls through to `else: return config_raw` at line 386 -- no dedicated mapping for tLogRow) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Registry Aliases** | `LogRow`, `tLogRow` (registered in `src/v1/engine/engine.py` lines 142-143) |
| **Category** | Transform / Logs & Errors |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/log_row.py` | Engine implementation (232 lines) |
| `src/converters/complex_converter/component_parser.py` (line 59) | Name mapping `'tLogRow': 'LogRow'` |
| `src/converters/complex_converter/component_parser.py` (lines 384-386) | Parameter mapping -- falls through to `else: return config_raw` (raw Talend XML params passed as-is) |
| `src/converters/complex_converter/converter.py` | Dispatch -- no dedicated `elif` for `tLogRow`; uses generic `parse_base_component()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ETLError`, `ConfigurationError`) |
| `src/v1/engine/components/transform/__init__.py` (line 13) | Package export: `from .log_row import LogRow` |
| `src/v1/engine/engine.py` (line 29) | Import: `from .components.transform import ... LogRow` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 3 | 1 | No dedicated parser; raw Talend params passed through -- relies on engine dual-naming; BASIC_MODE/TABLE_PRINT/VERTICAL not explicitly mapped; PRINT_CONTENT_WITH_LOG4J ignored |
| Engine Feature Parity | **Y** | 0 | 3 | 4 | 2 | Three display modes implemented; output goes to stdout via `print()` not logger; no Log4J integration; `NB_LINE_OK` counts displayed rows not input rows |
| Code Quality | **Y** | 1 | 3 | 5 | 3 | Cross-cutting `_update_global_map()` bug; `_validate_config()` never called by base class; `print()` used instead of logger; error swallowed in catch block; table width inconsistency across all border elements; `or` operator ignores falsy config values; NaN string comparison hides legitimate data |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | `iterrows()` used for all formats; table width calculation scans entire DataFrame; minor optimization opportunities |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tLogRow Does

`tLogRow` is a Talend Standard component in the **Logs & Errors** family. It displays data or results in the Run console to monitor data being processed. The component can be used as an **intermediate step** in a data flow (pass-through, forwarding all rows unchanged to the next component) or as a **terminal sink** at the end of a flow. It is one of the most commonly used components in Talend jobs for debugging and data verification purposes.

**Source**: [tLogRow Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tlogrow-standard-properties), [tLogRow Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/tlogrow-standard-properties), [tLogRow Overview (Talend 8.0)](https://help.qlik.com/talend/r/en-US/8.0/logs-and-errors/tlogrow), [Configuring the tLogRow component (Talend Studio User Guide 7.3)](https://help.talend.com/en-US/studio-user-guide/7.3/configuring-tlogrow-component)

**Component family**: Logs & Errors (Integration)
**Available in**: All Talend products (Standard). Also available in Apache Spark Batch and Spark Streaming variants.
**Required JARs**: None (built-in component).

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions. The schema defines which columns are displayed and which are passed through. Can be synchronized with the input flow via "Sync columns". |
| 3 | Mode: Basic | `BASIC_MODE` | Radio button | **Selected** (default) | Displays the output flow in basic delimited mode. Each row is printed as a single line with fields separated by the configured separator character. This is the default display mode. |
| 4 | Mode: Table | `TABLE_PRINT` | Radio button | Unselected | Displays the output flow formatted in table cells with borders and alignment. Values are printed within a visual table structure with headers and proper column sizing. More readable for wide data. |
| 5 | Mode: Vertical | `VERTICAL` | Radio button | Unselected | Displays each row of the output flow as a vertical key-value list. Each column becomes a line showing `column_name: value`. Useful for rows with many columns. |
| 6 | Separator | `FIELDSEPARATOR` | String | `"\|"` (pipe) | Delimiter character for separating fields in the log display. Only visible and applicable when `BASIC_MODE` is selected. In Talend, the default is pipe `\|`. |
| 7 | Print Header | `PRINT_HEADER` | Boolean (CHECK) | `false` | Include the header (column names) of the input flow in the output display. When checked, a header line is printed before the data rows in Basic mode. |
| 8 | Print Component Unique Name | `PRINT_UNIQUE` | Boolean (CHECK) | `false` | Print the component's unique name (e.g., `tLogRow_1`) in front of each output row. Useful for distinguishing output from multiple tLogRow components in the same job. |
| 9 | Print Schema Column Names | `PRINT_COLUMN_NAMES` | Boolean (CHECK) | `false` | Print the schema column label in front of each value. Each field is prefixed with its column name followed by a colon. Provides self-describing output. |
| 10 | Use Fixed Length Values | `USE_FIXED_LENGTH` | Boolean (CHECK) | `false` | Set a uniform width for the value display. When enabled, all values are padded to the same length for aligned columnar output. Only visible in Basic mode. |
| 11 | Log4J Output | `PRINT_CONTENT_WITH_LOG4J` | Boolean (CHECK) | `false` | Output the data flow content via Log4J at INFO level or lower instead of (or in addition to) System.out. When activated, the component routes output through the Talend logging framework rather than directly to the console. This is the recommended approach for production environments. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 12 | Max Rows / Schema Opt Num | `SCHEMA_OPT_NUM` | Integer | Not set (all rows) | Performance optimization: limits the number of rows displayed. In Talend, this parameter controls the threshold for optimized code generation. For tLogRow, it effectively acts as a maximum row display count. When not set or set to a high value, all incoming rows are displayed. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 14 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | **Input** | Row > Main | Receives rows from upstream component. All incoming rows are displayed according to the configured format. The component requires at least one input FLOW connection. |
| `FLOW` (Main) | **Output** | Row > Main | **Pass-through**: All incoming rows are forwarded unchanged to the next component. The output schema is identical to the input schema. This makes tLogRow an inline diagnostic -- it does NOT consume or modify data. When this output is connected, tLogRow acts as a pass-through; when not connected, it acts as a terminal sink. |
| `ITERATE` | Output | Iterate | Enables iterative processing when the component is used with iteration components like `tFlowToIterate`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |

**Critical behavioral note**: tLogRow is a **pass-through component**. Unlike terminal output components (e.g., `tFileOutputDelimited`), tLogRow forwards ALL input rows to its output connection UNCHANGED. The display/logging is a side effect. Downstream components receive the exact same DataFrame that arrived at tLogRow's input. This is fundamental to its design -- it allows insertion into any point in a data flow for debugging without altering the data.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows received by the component. This equals the total number of input rows, regardless of how many were actually displayed (which may be limited by SCHEMA_OPT_NUM). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

**Note on NB_LINE_OK and NB_LINE_REJECT**: Official Talend documentation for tLogRow lists only `NB_LINE` and `ERROR_MESSAGE` as global variables. Unlike input/output components, tLogRow does not produce `NB_LINE_OK` or `NB_LINE_REJECT` because it does not filter, reject, or transform rows. All rows pass through. The v1 engine sets these anyway via the base class mechanism, which is harmless but not strictly Talend-accurate.

### 3.5 Behavioral Notes

1. **Pass-through semantics**: tLogRow NEVER modifies data. The output DataFrame MUST be identical to the input DataFrame. This is a strict invariant. Any implementation that alters, filters, or reorders rows violates tLogRow's contract.

2. **Display mode exclusivity**: The three display modes (BASIC_MODE, TABLE_PRINT, VERTICAL) are mutually exclusive radio buttons in Talend. Only one can be active at a time. BASIC_MODE is the default. The mode selection is stored as three boolean parameters in the Talend XML, where exactly one is `true`.

3. **BASIC_MODE is the default**: When no mode is explicitly set, Talend uses Basic mode. This is important because the v1 engine defaults to Table mode (`table_print=True`), which differs from Talend behavior.

4. **Separator only applies to Basic mode**: The `FIELDSEPARATOR` parameter is only used in Basic mode. In Table mode, the formatting is handled by the table border structure. In Vertical mode, each field is displayed on its own line as `key: value`.

5. **PRINT_HEADER only applies to Basic mode**: The header line (column names joined by separator) is only relevant in Basic mode. Table mode always shows headers as part of the table structure. Vertical mode inherently shows column names with each value.

6. **PRINT_UNIQUE prefix**: When enabled, prepends the component unique name (e.g., `tLogRow_1`) before each output line. This is distinct from the title shown in Table mode.

7. **PRINT_CONTENT_WITH_LOG4J**: In Talend, this toggles between `System.out.println()` (unchecked) and Log4J `logger.info()` (checked). The v1 engine always uses `print()` (Python's stdout), which corresponds to `System.out.println()`. There is no Log4J equivalent implementation.

8. **No REJECT flow**: tLogRow does not have a REJECT output. Since it does not transform or validate data, there is no concept of rejected rows. All rows pass through unconditionally.

9. **Empty input**: When tLogRow receives an empty DataFrame or null input, it should log a warning and pass through the empty input. It should NOT raise an error.

10. **NB_LINE reflects total input rows**: The `NB_LINE` global variable counts ALL input rows, not just displayed rows. If `SCHEMA_OPT_NUM` limits display to 50 rows but 1000 rows arrive, `NB_LINE` is 1000.

11. **Multiple tLogRow in one job**: It is common to have multiple tLogRow components in a single Talend job at different points in the data flow. The `PRINT_UNIQUE` option helps distinguish their output.

12. **Performance consideration in Talend**: tLogRow is intended for debugging. In production, it should either be disabled, removed, or configured with `PRINT_CONTENT_WITH_LOG4J` to route through log levels that can be suppressed. Large data volumes through tLogRow cause significant console output overhead.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the **deprecated generic parameter mapping approach** (`_map_component_parameters()` in `component_parser.py`). There is NO dedicated `elif component_type == 'tLogRow'` branch in `_map_component_parameters()`. The component falls through to the `else: return config_raw` default path (line 386), meaning all raw Talend XML parameters are passed directly to the engine without any name translation.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tLogRow', config_raw)` (line 472)
4. No `elif` matches `'tLogRow'` -> falls through to `else: return config_raw` (line 386)
5. Raw Talend parameter names (BASIC_MODE, TABLE_PRINT, VERTICAL, FIELDSEPARATOR, etc.) are passed directly as the engine config
6. Schema is extracted generically from `<metadata connector="FLOW">` nodes

**Implication**: The engine receives Talend-style parameter names (UPPERCASE), NOT Python-style names (lowercase). This is why the engine's `_process()` method (line 100-106) supports dual naming -- it checks both `basic_mode` AND `BASIC_MODE` for every parameter.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `BASIC_MODE` | **Yes (raw)** | `BASIC_MODE` | Passed as raw Talend name. Engine checks both `basic_mode` and `BASIC_MODE`. |
| 2 | `TABLE_PRINT` | **Yes (raw)** | `TABLE_PRINT` | Passed as raw Talend name. Engine checks both `table_print` and `TABLE_PRINT`. |
| 3 | `VERTICAL` | **Yes (raw)** | `VERTICAL` | Passed as raw Talend name. Engine checks both `vertical` and `VERTICAL`. |
| 4 | `FIELDSEPARATOR` | **Yes (raw)** | `FIELDSEPARATOR` | Passed as raw Talend name. Engine checks both `field_separator` and `FIELDSEPARATOR`. |
| 5 | `PRINT_HEADER` | **Yes (raw)** | `PRINT_HEADER` | Passed as raw Talend name. Engine checks `print_header`, `PRINT_HEADER`, `print_column_names`, and `PRINT_COLUMN_NAMES`. |
| 6 | `PRINT_UNIQUE` | **Yes (raw)** | `PRINT_UNIQUE` | Passed as raw Talend name. **Engine does NOT check for this parameter.** Not implemented. |
| 7 | `PRINT_COLUMN_NAMES` | **Yes (raw)** | `PRINT_COLUMN_NAMES` | Passed as raw Talend name. Engine conflates this with `print_header`. |
| 8 | `USE_FIXED_LENGTH` | **Yes (raw)** | `USE_FIXED_LENGTH` | Passed as raw Talend name. **Engine does NOT check for this parameter.** Not implemented. |
| 9 | `PRINT_CONTENT_WITH_LOG4J` | **Yes (raw)** | `PRINT_CONTENT_WITH_LOG4J` | Passed as raw Talend name. **Engine does NOT check for this parameter.** Not implemented. |
| 10 | `SCHEMA_OPT_NUM` | **Yes (raw)** | `SCHEMA_OPT_NUM` | Passed as raw Talend name. Engine checks both `max_rows` and `SCHEMA_OPT_NUM`. |
| 11 | `TSTATCATCHER_STATS` | **Yes (raw)** | `TSTATCATCHER_STATS` | Not needed at runtime (tStatCatcher rarely used). |
| 12 | `LABEL` | **Yes (raw)** | `LABEL` | Not needed (cosmetic -- no runtime impact). |
| 13 | `PROPERTY_TYPE` | **Yes (raw)** | `PROPERTY_TYPE` | Not needed (always Built-In in converted jobs). |

**Summary**: All 13 Talend parameters are technically extracted (passed through as raw config). However, 3 runtime-relevant parameters (`PRINT_UNIQUE`, `USE_FIXED_LENGTH`, `PRINT_CONTENT_WITH_LOG4J`) are extracted but completely ignored by the engine. The raw pass-through approach means no validation, no type conversion, and no default value normalization happens at the converter level.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 475-508 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic -- no runtime impact) |
| `talendType` | **No** | Full Talend type string not preserved -- converted to Python type |

**Note on schema relevance for tLogRow**: The schema defines which columns to display and how to format them. However, since tLogRow is a pass-through component, schema enforcement is less critical than for input/output components. The engine does NOT call `validate_schema()` on the data -- it simply displays whatever columns are in the input DataFrame.

### 4.3 Expression Handling

**Context variable handling** (component_parser.py lines 449-456):
- Simple `context.var` references in non-CODE/IMPORT fields are detected by checking `'context.' in value`
- For tLogRow, context variables are most likely to appear in `FIELDSEPARATOR` (using a context-defined separator)
- If the expression is NOT a Java expression, it is wrapped as `${context.var}` for ContextManager resolution

**Java expression handling** (component_parser.py lines 462-469):
- Values containing Java operators, method calls, or routine references are prefixed with `{{java}}` marker
- For tLogRow, Java expressions are unlikely in standard configurations but possible in `FIELDSEPARATOR` if dynamically computed

**Known limitations**:
- Boolean handling nuance: CHECK-type parameters (`PRINT_HEADER`, `PRINT_UNIQUE`, `PRINT_COLUMN_NAMES`, `USE_FIXED_LENGTH`, `PRINT_CONTENT_WITH_LOG4J`) ARE converted to Python bools by `parse_base_component()` (lines 444-446), so they arrive at the engine as native `True`/`False`. However, RADIO-type parameters (`BASIC_MODE`, `TABLE_PRINT`, `VERTICAL`) may arrive as strings (`"true"`, `"false"`) because they follow a different XML extraction path. The engine's `_get_boolean_config()` method handles both native bools and string representations correctly, so there is no practical impact.
- `SCHEMA_OPT_NUM` arrives as a string and must be converted to int by the engine. The engine does this on line 107 (`max_rows = int(max_rows_param)`), which will raise `ValueError` if the value is not a valid integer.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-LR-001 | **P1** | **No dedicated parser method**: `tLogRow` uses the deprecated `_map_component_parameters()` fallback (`else: return config_raw`). This passes raw Talend XML parameter names directly to the engine instead of normalizing them to Python-style names. The engine must support dual naming (UPPERCASE + lowercase) for every parameter, creating maintenance burden and potential for naming drift. Per STANDARDS.md, every component SHOULD have its own `parse_*` method. |
| CONV-LR-002 | **P1** | **No parameter validation at converter level**: Since raw config is passed through, invalid values (e.g., non-boolean for BASIC_MODE, non-integer for SCHEMA_OPT_NUM, empty FIELDSEPARATOR) are not caught until runtime. A dedicated parser could validate and normalize these during conversion. |
| CONV-LR-003 | **P2** | **PRINT_UNIQUE not mapped to engine parameter**: The `PRINT_UNIQUE` Talend parameter is passed through but the engine never reads it. A dedicated parser could map it to a `print_component_name` flag that the engine checks. |
| CONV-LR-004 | **P2** | **USE_FIXED_LENGTH not mapped to engine parameter**: The `USE_FIXED_LENGTH` Talend parameter is passed through but the engine never reads it. A dedicated parser could map it to a `fixed_length` flag. |
| CONV-LR-005 | **P2** | **PRINT_CONTENT_WITH_LOG4J not mapped**: The Log4J output toggle is passed through but completely ignored by the engine. A dedicated parser could map it to a `use_logger` flag that switches from `print()` to `logger.info()`. |
| CONV-LR-006 | **P3** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While less impactful for tLogRow (which does not enforce schema types), this creates inconsistency with a future standardized approach. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Basic mode display | **Yes** | Medium | `_print_basic_format()` line 206 | Prints each row as separator-delimited line. Header printing supported. |
| 2 | Table mode display | **Yes** | High | `_print_table_format()` line 145 | Formatted table with borders, headers, column sizing. Closest to Talend's table rendering. |
| 3 | Vertical mode display | **Yes** | Medium | `_print_vertical_format()` line 214 | Prints each row as key-value pairs. Format differs from Talend (uses `Row N:` prefix). |
| 4 | Field separator | **Yes** | High | `_process()` line 105 | Supports both `field_separator` and `FIELDSEPARATOR` config keys. Default `\|` matches Talend. |
| 5 | Print header | **Yes** | Medium | `_process()` line 103 | Checks `print_header`, `PRINT_HEADER`, `print_column_names`, `PRINT_COLUMN_NAMES`. **Default `True` differs from Talend default `False`.** |
| 6 | Max rows limit | **Yes** | High | `_process()` line 106-110 | Uses `head(max_rows)` to limit displayed rows. Checks both `max_rows` and `SCHEMA_OPT_NUM`. Default 100. |
| 7 | Pass-through output | **Yes** | High | `_process()` line 132 | Returns `{'main': input_data}` -- original input DataFrame passed through unchanged. Correct. |
| 8 | Statistics tracking | **Yes** | Medium | `_process()` line 128 | `_update_stats(rows_in, rows_logged, 0)`. **`NB_LINE_OK` counts displayed rows, not input rows.** |
| 9 | Empty input handling | **Yes** | High | `_process()` line 91-94 | Returns `{'main': input_data}` with stats (0, 0, 0) on empty input. Logs warning. |
| 10 | Print component unique name | **No** | N/A | -- | `PRINT_UNIQUE` parameter not read. Table mode hardcodes a title but basic/vertical modes have no component name prefix. |
| 11 | Print column names per value | **Partial** | Low | -- | `PRINT_COLUMN_NAMES` is conflated with `print_header` (line 103). In Talend, this prints column name before each value in basic mode (e.g., `col1:val1\|col2:val2`). In v1, it just prints the header row. Different behavior. |
| 12 | Fixed length values | **No** | N/A | -- | `USE_FIXED_LENGTH` parameter not read. No fixed-width formatting in basic mode. |
| 13 | Log4J output | **No** | N/A | -- | `PRINT_CONTENT_WITH_LOG4J` parameter not read. All output goes to `print()` (stdout). No logger integration for data output. |
| 14 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 15 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 16 | Schema sync (input = output) | **Yes** | High | Implicit | Pass-through means output schema = input schema. No explicit sync needed. |
| 17 | Dual parameter naming | **Yes** | High | `_process()` lines 100-106 | Supports both `basic_mode`/`BASIC_MODE`, `table_print`/`TABLE_PRINT`, etc. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-LR-001 | **P1** | **Default display mode differs from Talend**: The engine defaults to Table mode (`table_print=True`, line 101). Talend defaults to Basic mode (`BASIC_MODE=true`). When a Talend job does not explicitly set the mode (relying on the Talend default), the converted job will display in table format instead of basic delimited format. This changes the output appearance for any tLogRow that uses the default mode. |
| ENG-LR-002 | **P1** | **Default `print_header` differs from Talend**: The engine defaults `print_header` to `True` (line 103). Talend defaults `PRINT_HEADER` to unchecked (`false`). This means the engine prints column headers by default when Talend would not. |
| ENG-LR-003 | **P1** | **`NB_LINE_OK` counts displayed rows, not input rows**: `_update_stats(rows_in, rows_logged, 0)` on line 128 sets `NB_LINE=rows_in` but `NB_LINE_OK=rows_logged` (i.e., `min(rows_in, max_rows)`). In Talend, `NB_LINE` is the total processed count. Since tLogRow does not reject rows, `NB_LINE_OK` should equal `NB_LINE`. When `max_rows < rows_in`, the engine reports fewer OK rows than input rows, which is misleading for downstream logic that checks `NB_LINE_OK`. |
| ENG-LR-004 | **P2** | **All output goes to `print()` (stdout), never to logger**: Talend's `PRINT_CONTENT_WITH_LOG4J` option routes output through Log4J at INFO level, allowing it to be captured by log appenders, filtered by log level, or suppressed in production. The v1 engine always uses `print()`, which goes directly to stdout and cannot be redirected or suppressed through logging configuration. This is a significant gap for production deployments where console output should be controlled. |
| ENG-LR-005 | **P2** | **`PRINT_UNIQUE` (print component name) not implemented**: Talend's option to prefix each output line with the component unique name (e.g., `tLogRow_1`) is not available. Table mode has a title with the component name, but basic and vertical modes have no component name identification. When multiple tLogRow components run in the same job, their output cannot be distinguished. |
| ENG-LR-006 | **P2** | **`PRINT_COLUMN_NAMES` conflated with `PRINT_HEADER`**: In Talend, `PRINT_COLUMN_NAMES` adds column names in front of each value (e.g., `name:John\|age:30`). In the v1 engine, this parameter is aliased to `print_header` (line 103), which simply prints a header ROW (column names joined by separator) above the data. These are different display behaviors. |
| ENG-LR-007 | **P2** | **`USE_FIXED_LENGTH` not implemented**: Talend's fixed-width value display option is ignored. In basic mode, values are printed at their natural length. For aligned columnar output in basic mode, this parameter is needed. |
| ENG-LR-008 | **P3** | **Vertical format differs from Talend**: V1 uses `Row {idx + 1}:` prefix with 0-based index (line 217). Talend uses its own row numbering scheme. Also, v1 prints a dashed separator (`-` * 30) between rows; Talend may use a different separator or no separator. |
| ENG-LR-009 | **P3** | **Table format title convention**: V1 generates title as `tLogRow_{self.id}` unless `self.id` already starts with `tLogRow` (line 161). Talend uses the component's actual unique name. If the component ID is `LogRow_1`, the v1 title becomes `tLogRow_LogRow_1`, which is awkward. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Value = total input rows. |
| `{id}_NB_LINE_OK` | **No** (not standard for tLogRow) | **Yes** | Same mechanism | V1 sets this via base class. Value = displayed rows (not input rows). Not standard for tLogRow in Talend. May confuse downstream logic. |
| `{id}_NB_LINE_REJECT` | **No** (not standard for tLogRow) | **Yes** | Same mechanism | Always 0. Not standard for tLogRow in Talend. Harmless but unnecessary. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented. When errors occur during display, the error message is not stored in globalMap. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-LR-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just LogRow, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-LR-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-LR-003 | **P1** | `src/v1/engine/components/transform/log_row.py:128` | **`NB_LINE_OK` set to displayed rows, not input rows**: `_update_stats(rows_in, rows_logged, 0)` sets `NB_LINE_OK = rows_logged` where `rows_logged = len(df_to_print)` = `min(rows_in, max_rows)`. For a pass-through component, `NB_LINE_OK` should always equal `NB_LINE` (all rows pass through successfully). The "logged" count is a display artifact, not a data flow metric. Downstream components checking `{id}_NB_LINE_OK` will see fewer rows than actually passed through. Should be `_update_stats(rows_in, rows_in, 0)`. |
| BUG-LR-004 | **P1** | `src/v1/engine/components/transform/log_row.py:123-125` | **Error swallowed silently -- exception caught, print to stderr, but execution continues**: When an exception occurs during display formatting, the `except Exception as e` block logs the error and prints it to stdout via `print()`, but does NOT re-raise. The method then proceeds to update stats (line 128) and return the input data (line 132). While this is arguably correct (display errors should not block data flow), the error is logged twice (once via logger, once via print), and the `print()` on line 125 is a debug artifact. More importantly, `{id}_ERROR_MESSAGE` is never set in globalMap for downstream error checking. |
| BUG-LR-005 | **P1** | `src/v1/engine/components/transform/log_row.py:68-87` | **`_validate_config()` is never called by the base class**: The `_validate_config()` method exists and validates `max_rows`, but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (e.g., `max_rows=-5`) are not caught until they cause unexpected behavior in `_process()`. |
| BUG-LR-006 | **P2** | `src/v1/engine/components/transform/log_row.py:107` | **`int(max_rows_param)` can raise ValueError**: Line 107 does `max_rows = int(max_rows_param)` without try/except. If `SCHEMA_OPT_NUM` or `max_rows` contains a non-numeric value (e.g., a context variable that failed to resolve, or a string like `"unlimited"`), this raises an unhandled `ValueError` that propagates up as a component execution error. The `_validate_config()` method (lines 78-85) would catch this, but it is never called. |
| BUG-LR-007 | **P2** | `src/v1/engine/components/transform/log_row.py:154` | **`max_value_len` calculated even when df is empty**: Line 154 has a redundant guard `if not df.empty` inside `_print_table_format()` which already has an early return for empty DataFrames (line 147-148). Not a bug per se, but the check is unreachable and suggests a copy-paste artifact. |
| BUG-LR-008 | **P2** | `src/v1/engine/components/transform/log_row.py:176` | **Table format padding is off by one**: Line 176 prints the title as `f"|{' ' * left_pad}{title}{' ' * right_pad} |"` with an extra space before the closing `|`. This means the title row is `table_width + 1` characters wide while the data rows are `table_width` characters wide, causing visual misalignment. The `top_border` (line 169) uses `table_width + 2` and the header separator (line 182) uses a different width calculation. The table borders may not align properly for all data widths. |
| BUG-LR-009 | **P2** | `src/v1/engine/components/transform/log_row.py` (table format) | **Table width inconsistency broader than title row**: Four different width formulas are used across the table structure: top/bottom border (`table_width + 4`), title row (`table_width + 3`), header separator (`sum(col_widths) + N + 3`), data rows (`sum(col_widths) + N + 1`). All four can produce different widths, causing misaligned table borders across the entire table -- not just the title row. This is a systemic alignment bug affecting all table output. |
| BUG-LR-010 | **P3** | `src/v1/engine/components/transform/log_row.py:198` | **`str(row[col]) != 'nan'` filter hides legitimate string values**: The NaN filter on line 198 uses string comparison `str(row[col]) != 'nan'`, which also suppresses display of legitimate data values that happen to be the string `'nan'` (e.g., a name field containing `'nan'`). Should use `pd.isna(row[col])` to check for actual NaN values instead of string comparison. |
| BUG-LR-011 | **P2** | `src/v1/engine/components/transform/log_row.py:105-106` | **`or` operator in config lookup silently ignores falsy values**: Line 105 uses `self.config.get('field_separator') or self.config.get('FIELDSEPARATOR', ...)` -- if `field_separator` is set to empty string `''` (a falsy value), it falls through to `FIELDSEPARATOR` instead of using the explicitly configured empty string. Line 106: if `max_rows` is set to `0` (falsy), it falls through to `SCHEMA_OPT_NUM` or the default 100, ignoring the explicit zero value. Should use `if ... is not None` checks instead of `or` chaining. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-LR-001 | **P2** | **Dual parameter naming throughout**: Every config parameter is checked under two names (e.g., `basic_mode` AND `BASIC_MODE`). This is caused by the converter's raw pass-through of Talend parameter names. A dedicated converter parser would normalize names, eliminating the need for dual lookups. The dual naming creates 2x the surface area for typos and naming drift. |
| NAME-LR-002 | **P2** | **`PRINT_COLUMN_NAMES` aliased to `print_header`**: Line 103 lists four parameter names for the same flag: `print_header`, `PRINT_HEADER`, `print_column_names`, `PRINT_COLUMN_NAMES`. In Talend, `PRINT_HEADER` and `PRINT_COLUMN_NAMES` are different parameters with different behaviors. Conflating them means one Talend behavior is lost. |
| NAME-LR-003 | **P3** | **`max_rows` vs `SCHEMA_OPT_NUM`**: The engine config key `max_rows` corresponds to Talend's `SCHEMA_OPT_NUM`, which is not an intuitive mapping. `max_rows` is clearer but deviates from Talend naming. A converter parser should provide the translation with a comment explaining the mapping. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-LR-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-LR-002 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | Uses deprecated `_map_component_parameters()` fallback instead of a dedicated `parse_tlogrow()` method. |
| STD-LR-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types. Less impactful for tLogRow but creates inconsistency. |
| STD-LR-004 | **P1** | "No `print()` statements" (STANDARDS.md) | `LogRow` uses `print()` extensively (lines 170, 176, 183, 189, 192, 200, 203, 204, 209, 212, 217, 220, 221, and error handler line 125). This is inherent to tLogRow's purpose (console output), but the error handler on line 125 is clearly a debug artifact that should use `logger.error()` instead. For data output, `print()` is acceptable but should be switchable to `logger.info()` when `PRINT_CONTENT_WITH_LOG4J` is enabled. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-LR-001 | **P2** | **`print()` in error handler (line 125)**: `print(f"[{self.id}] Error logging data: {e}")` is a debug artifact. Error messages should go through the logger, not stdout. This line outputs the error to the same stream as data, making it indistinguishable from data output. |
| DBG-LR-002 | **P3** | **Legacy `validate_config()` method (lines 224-231)**: A public `validate_config()` method wraps `_validate_config()` for backward compatibility. Since neither method is called by any code path, this is dead code that adds confusion about the validation lifecycle. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-LR-001 | **P3** | **No output sanitization**: Data values are printed directly to stdout without any sanitization. If input data contains ANSI escape codes, control characters, or terminal manipulation sequences, they will be rendered in the console. This is a minor concern for tLogRow since it is a debugging component, but noted for awareness. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, WARNING for empty input, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 97) and complete (line 129) -- correct |
| Sensitive data | No sensitive data filtering on displayed data -- acceptable for debugging component |
| Print statements | Extensive `print()` usage -- acceptable for data display purpose but error handler on line 125 should use logger |
| Data vs log separation | **Issue**: Data output (`print()`) and logging output (`logger`) go to different streams. In production, this separation is important. But the error handler `print()` on line 125 mixes error messages into the data stream. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Exception types | No custom exceptions raised. Display errors are caught generically. Acceptable for a display-only component. |
| Exception handling | Broad `except Exception as e` on line 123 catches all display errors. Error is logged and printed, but NOT re-raised. Execution continues, returning the input data unchanged. This is correct behavior (display failure should not block data flow) but error details are lost (no `ERROR_MESSAGE` in globalMap). |
| Empty input | Handled correctly on line 91-94. Returns `{'main': input_data}` with zero stats. |
| None input | `input_data is None` check on line 91 handles null input correctly. |
| ValueError from int() | `int(max_rows_param)` on line 107 is NOT wrapped in try/except. Invalid `max_rows` will crash the component. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `input_data: Optional[pd.DataFrame]` -- correct |
| Complex types | Uses `Dict[str, Any]`, `List[str]`, `Optional` -- correct |
| `_get_boolean_config` | Parameter `param_names: List[str]`, `default: bool` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-LR-001 | **P2** | **`iterrows()` used in all three display modes**: `_print_table_format()` (line 195), `_print_basic_format()` (line 211), and `_print_vertical_format()` (line 216) all use `df.iterrows()`. For DataFrames with many rows, `iterrows()` is slow because it creates a Series per row. For display-limited rows (default 100), this is acceptable. But if `max_rows` is set high (e.g., 100000), performance degrades. Consider `df.to_string()` or `df.itertuples()` for basic format. |
| PERF-LR-002 | **P2** | **Table width calculation scans entire DataFrame**: `_print_table_format()` lines 152-155 compute `max_value_len` for each column by converting ALL values to strings and finding the max length. For a 100-row display limit, this scans 100 rows per column. For wide DataFrames (100+ columns), this creates `100 * N_columns` string conversions. The `fillna('').astype(str).str.len().max()` chain creates intermediate Series objects. |
| PERF-LR-003 | **P3** | **`print()` called per row**: Each row generates a separate `print()` call, which flushes stdout per call by default. For 100 rows, this is 100+ print calls. Building the entire output as a string buffer and printing once would be more efficient and avoid interleaving with other output in multi-threaded environments. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Pass-through design | `{'main': input_data}` returns the original DataFrame reference (NOT a copy). No memory duplication for the data flow. Correct. |
| Display slice | `df_to_print = input_data.head(max_rows)` creates a view/shallow copy of at most `max_rows` rows. Memory efficient. |
| String conversion | `astype(str)` in `_print_table_format()` creates temporary string Series for width calculation. These are garbage collected after the method returns. Acceptable for limited rows. |
| No streaming concern | tLogRow is display-only. Even for large inputs, it only displays `max_rows` rows and passes through the full DataFrame without modification. Memory is not a concern. |

### 7.2 Stdout Buffering Considerations

| Issue | Description |
|-------|-------------|
| Interleaving | Multiple `print()` calls per row mean that in multi-threaded or async environments, output from different components may interleave line-by-line. Talend's generated Java code typically uses `StringBuilder` to build the entire output and flush once. |
| Redirect | `print()` goes to `sys.stdout`. If stdout is redirected (e.g., to a file or pipe), each `print()` call triggers a write. For high-volume output, this is I/O intensive. |
| Suppression | There is no way to suppress tLogRow output without redirecting stdout globally. In Talend, `PRINT_CONTENT_WITH_LOG4J` allows routing through log levels that can be disabled. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `LogRow` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 232 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic mode output | P0 | Feed a 3-row, 3-column DataFrame. Verify output contains rows separated by pipe (`\|`). Capture stdout and compare. |
| 2 | Table mode output | P0 | Feed a 3-row DataFrame with `table_print=True`. Verify table borders, headers, and row data are properly formatted. |
| 3 | Vertical mode output | P0 | Feed a 2-row DataFrame with `vertical=True`. Verify each row appears as key-value pairs. |
| 4 | Pass-through invariant | P0 | Feed a DataFrame. Verify the returned `{'main': df}` contains the EXACT SAME DataFrame object (identity check with `is`). Verify NO columns added, removed, or modified. |
| 5 | Empty input handling | P0 | Pass `None` and an empty DataFrame. Verify no exception raised and stats are (0, 0, 0). |
| 6 | Statistics tracking | P0 | Feed 10 rows with `max_rows=5`. Verify `NB_LINE=10` (all rows counted). Verify pass-through returns all 10 rows. |
| 7 | GlobalMap integration | P0 | Execute with a GlobalMap instance. Verify `{id}_NB_LINE` is set correctly after execution. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Default mode is Basic (Talend compat) | P1 | Execute with no mode flags set. Verify output is in basic format, not table. (Currently fails -- engine defaults to table.) |
| 9 | Default print_header is False (Talend compat) | P1 | Execute with no print_header flag. Verify no header line printed. (Currently fails -- engine defaults to True.) |
| 10 | Max rows limiting | P1 | Feed 200 rows with `max_rows=50`. Verify only 50 rows appear in output. Verify pass-through returns all 200 rows. |
| 11 | Talend parameter names (UPPERCASE) | P1 | Configure with `BASIC_MODE=true`, `FIELDSEPARATOR=','`. Verify these Talend-style names are recognized. |
| 12 | Python parameter names (lowercase) | P1 | Configure with `basic_mode=True`, `field_separator=','`. Verify these Python-style names are recognized. |
| 13 | Boolean string conversion | P1 | Configure with `basic_mode="true"` (string). Verify `_get_boolean_config()` converts correctly. Test `"false"`, `"1"`, `"0"`, `"yes"`, `"no"`. |
| 14 | Custom field separator | P1 | Use `field_separator=','` in basic mode. Verify fields are comma-separated in output. |
| 15 | NB_LINE_OK equals NB_LINE for pass-through | P1 | Feed 100 rows with max_rows=10. Verify `NB_LINE_OK` equals `NB_LINE` (both 100), not 10. (Currently fails -- engine sets NB_LINE_OK to displayed rows.) |
| 16 | Error during display does not block pass-through | P1 | Mock `print()` to raise an exception. Verify the component still returns the input data unchanged. |
| 17 | NaN/None handling in display | P1 | Feed DataFrame with NaN and None values. Verify they display as empty string (not 'nan' or 'None'). |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | Very wide DataFrame (50+ columns) | P2 | Verify table format handles wide data without truncation or misalignment. |
| 19 | Unicode values | P2 | Feed DataFrame with Unicode characters (CJK, emoji, RTL). Verify display width calculation handles multi-byte correctly. |
| 20 | Large max_rows value | P2 | Set `max_rows=1000000`. Feed 100 rows. Verify no performance issues. |
| 21 | Invalid max_rows value | P2 | Set `max_rows="abc"`. Verify graceful error handling (currently raises unhandled ValueError). |
| 22 | Context variable in field_separator | P2 | Use `field_separator="${context.sep}"`. Verify context resolution before display. |
| 23 | Empty field separator | P2 | Set `field_separator=""`. Verify basic mode handles empty separator gracefully. |
| 24 | Single-column DataFrame | P2 | Verify all three display modes handle a single-column DataFrame. |
| 25 | Zero-width column name | P2 | Feed DataFrame with empty string column name. Verify table width calculation handles edge case. |
| 26 | Concurrent execution | P2 | Two LogRow components executing simultaneously. Verify output does not interleave mid-row. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-LR-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-LR-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-LR-001 | Testing | Zero v1 unit tests for this common debugging component. All 232 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-LR-001 | Converter | No dedicated parser method -- uses deprecated `_map_component_parameters()` fallback. Raw Talend params passed through, forcing engine to support dual naming. |
| CONV-LR-002 | Converter | No parameter validation at converter level -- invalid values not caught until runtime. |
| ENG-LR-001 | Engine | Default display mode is Table; Talend default is Basic. Converted jobs using default mode will render differently. |
| ENG-LR-002 | Engine | Default `print_header` is `True`; Talend default is `false`. Converted jobs using default will print unwanted headers. |
| ENG-LR-003 | Engine | `NB_LINE_OK` counts displayed rows, not input rows. Downstream logic checking this variable gets wrong value when `max_rows < input_rows`. |
| BUG-LR-003 | Bug | Same as ENG-LR-003 -- `NB_LINE_OK` set incorrectly in `_update_stats()`. |
| BUG-LR-004 | Bug | Error in display formatting is caught and swallowed. Error message printed to stdout (mixing with data output) instead of going through logger. `ERROR_MESSAGE` not set in globalMap. |
| BUG-LR-005 | Bug | `_validate_config()` is dead code -- never called by any code path. 20 lines of unreachable validation. |
| STD-LR-004 | Standards | `print()` on line 125 in error handler is a debug artifact that should use `logger.error()`. |
| TEST-LR-002 | Testing | No integration test for this component in a multi-step v1 job (e.g., tFileInputDelimited -> tLogRow -> tFileOutputDelimited). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-LR-003 | Converter | `PRINT_UNIQUE` parameter passed through but engine ignores it. Component name prefix not supported. |
| CONV-LR-004 | Converter | `USE_FIXED_LENGTH` parameter passed through but engine ignores it. Fixed-width formatting not supported. |
| CONV-LR-005 | Converter | `PRINT_CONTENT_WITH_LOG4J` parameter passed through but engine ignores it. All output goes to stdout. |
| ENG-LR-004 | Engine | All output via `print()` -- no option to route through Python logger. Cannot suppress output via log level configuration. |
| ENG-LR-005 | Engine | `PRINT_UNIQUE` (component name prefix per row) not implemented. Cannot distinguish output from multiple tLogRow instances. |
| ENG-LR-006 | Engine | `PRINT_COLUMN_NAMES` conflated with `PRINT_HEADER`. Per-value column name prefix not available. |
| ENG-LR-007 | Engine | `USE_FIXED_LENGTH` not implemented. Fixed-width columnar output in basic mode not available. |
| BUG-LR-006 | Bug | `int(max_rows_param)` on line 107 has no try/except. Non-numeric values cause unhandled ValueError. |
| BUG-LR-008 | Bug | Table format title row padding off by one -- extra space before closing `\|` causes misalignment. |
| BUG-LR-009 | Bug | Table width inconsistency broader than title row. Four different width formulas (top/bottom border, title row, header separator, data rows) can all produce different widths, causing misaligned table borders. |
| BUG-LR-011 | Bug | `or` operator in config lookup silently ignores falsy values. Empty string `field_separator` falls through to FIELDSEPARATOR; `max_rows=0` falls through to SCHEMA_OPT_NUM or default 100. |
| NAME-LR-001 | Naming | Dual parameter naming (UPPERCASE + lowercase) throughout `_process()`. Maintenance burden. |
| NAME-LR-002 | Naming | `PRINT_COLUMN_NAMES` and `PRINT_HEADER` treated as aliases when they are different Talend features. |
| STD-LR-001 | Standards | `_validate_config()` exists but never called -- dead validation. |
| STD-LR-002 | Standards | Uses deprecated `_map_component_parameters()` fallback instead of dedicated `parse_*` method. |
| STD-LR-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| DBG-LR-001 | Debug | `print()` in error handler (line 125) mixes error messages with data output stream. |
| PERF-LR-001 | Performance | `iterrows()` used in all three display modes -- slow for large row counts. |
| PERF-LR-002 | Performance | Table width calculation scans entire display DataFrame converting all values to strings. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-LR-006 | Converter | Schema types converted to Python format instead of Talend format (less impactful for display-only component). |
| ENG-LR-008 | Engine | Vertical format differs from Talend (row numbering, separator style). |
| ENG-LR-009 | Engine | Table title `tLogRow_{self.id}` creates awkward name when ID does not start with `tLogRow`. |
| NAME-LR-003 | Naming | `max_rows` vs Talend's `SCHEMA_OPT_NUM` -- non-intuitive mapping. |
| DBG-LR-002 | Debug | Legacy `validate_config()` wrapper is dead code. |
| SEC-LR-001 | Security | No output sanitization for ANSI escape codes or control characters in displayed data. |
| BUG-LR-007 | Bug | Redundant `if not df.empty` guard inside method that already returns early for empty DataFrames. |
| BUG-LR-010 | Bug | `str(row[col]) != 'nan'` filter on line 198 hides legitimate string values of `'nan'`. Should use `pd.isna()` instead of string comparison. |
| PERF-LR-003 | Performance | `print()` called per row instead of buffered output. Minor interleaving risk in concurrent execution. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 10 | 2 converter, 3 engine, 3 bugs, 1 standards, 1 testing |
| P2 | 19 | 3 converter, 4 engine, 4 bugs, 2 naming, 3 standards, 1 debug, 2 performance |
| P3 | 9 | 1 converter, 2 engine, 1 naming, 1 debug, 1 security, 2 bugs, 1 performance |
| **Total** | **41** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-LR-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove both stale references (`{stat_name}: {value}`) and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-LR-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-LR-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: three display modes, pass-through invariant, empty input, statistics, and globalMap integration. Without these, no v1 engine behavior is verified.

4. **Fix default display mode to match Talend** (ENG-LR-001): Change the default for `table_print` from `True` to `False` and the default for `basic_mode` from `False` to `True` on lines 100-101 of `log_row.py`. This ensures converted Talend jobs that rely on the default mode render correctly. **Risk**: May change output for existing v1 jobs that rely on the current default.

5. **Fix default `print_header` to match Talend** (ENG-LR-002): Change the default for `print_header` from `True` to `False` on line 103 of `log_row.py`. Talend defaults to no header in Basic mode. **Risk**: May change output for existing v1 jobs.

6. **Fix `NB_LINE_OK` to equal `NB_LINE`** (BUG-LR-003/ENG-LR-003): Change line 128 from `_update_stats(rows_in, rows_logged, 0)` to `_update_stats(rows_in, rows_in, 0)`. For a pass-through component, all rows are "OK" regardless of how many were displayed. **Risk**: Very low.

### Short-Term (Hardening)

7. **Create dedicated converter parser** (CONV-LR-001): Add a `parse_tlogrow(self, node, component)` method in `component_parser.py` that extracts and normalizes all tLogRow parameters. Register in `converter.py:_parse_component()`. This eliminates dual naming in the engine and enables parameter validation at conversion time.

8. **Implement `PRINT_CONTENT_WITH_LOG4J` equivalent** (CONV-LR-005/ENG-LR-004): Add a `use_logger` config flag. When enabled, route data output through `logger.info()` instead of `print()`. This allows output suppression via log level configuration in production. The converter parser should map `PRINT_CONTENT_WITH_LOG4J` to `use_logger`.

9. **Fix error handler** (BUG-LR-004/DBG-LR-001): Replace `print(f"[{self.id}] Error logging data: {e}")` on line 125 with `logger.error(f"[{self.id}] Error logging data: {e}")`. Also set `ERROR_MESSAGE` in globalMap when an error occurs.

10. **Wire up `_validate_config()`** (BUG-LR-005): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and logging warnings. For a display component, invalid config should produce a warning, not block execution.

11. **Wrap `int(max_rows_param)` in try/except** (BUG-LR-006): Handle `ValueError` gracefully by falling back to `DEFAULT_MAX_ROWS`.

12. **Separate `PRINT_COLUMN_NAMES` from `PRINT_HEADER`** (ENG-LR-006/NAME-LR-002): In basic mode, `PRINT_HEADER` should print a header ROW. `PRINT_COLUMN_NAMES` should prefix each VALUE with its column name (e.g., `name:John|age:30`). These are distinct Talend behaviors.

13. **Implement `PRINT_UNIQUE`** (ENG-LR-005): When enabled, prefix each output line with the component unique name. Simple change: prepend `f"{self.id}: "` to each output line.

### Long-Term (Optimization)

14. **Implement `USE_FIXED_LENGTH`** (ENG-LR-007): In basic mode, pad all values to a fixed width. Use `max(len(str(v)) for v in column)` to determine width, then `str.ljust(width)`.

15. **Fix table format alignment** (BUG-LR-008): Audit the table border width calculations. Ensure top border, header separator, data rows, and bottom border all have consistent widths.

16. **Buffer output** (PERF-LR-003): Build the entire display output as a string list, then join and `print()` once. Reduces I/O calls and prevents interleaving.

17. **Replace `iterrows()` with `itertuples()`** (PERF-LR-001): For basic mode, `itertuples()` is ~100x faster than `iterrows()`. For table mode, the width calculation already processes the full DataFrame, so the row iteration cost is secondary.

18. **Create integration test** (TEST-LR-002): Build an end-to-end test exercising `tFileInputDelimited -> tLogRow -> tFileOutputDelimited` in the v1 engine, verifying pass-through data integrity.

---

## Appendix A: Converter Parameter Mapping Code

### Current Behavior (Generic Fallback)

```python
# component_parser.py line 59 - Name mapping
'tLogRow': 'LogRow',

# component_parser.py lines 384-386 - Parameter mapping (fallback)
# tLogRow has NO dedicated elif branch. Falls through to:
else:
    return config_raw
```

**Effect**: All raw Talend XML parameters are passed as-is to the engine config dict. Parameter names like `BASIC_MODE`, `TABLE_PRINT`, `VERTICAL`, `FIELDSEPARATOR`, `PRINT_HEADER`, `PRINT_UNIQUE`, `PRINT_COLUMN_NAMES`, `USE_FIXED_LENGTH`, `PRINT_CONTENT_WITH_LOG4J`, and `SCHEMA_OPT_NUM` arrive at the engine unchanged.

**Notes on this behavior**:
- Partial type conversion: CHECK-type boolean parameters (e.g., `PRINT_HEADER`) are converted to Python bools by `parse_base_component()` (lines 444-446). RADIO-type parameters (`BASIC_MODE`, `TABLE_PRINT`, `VERTICAL`) may still arrive as strings `"true"` / `"false"`. The engine's `_get_boolean_config()` handles both correctly.
- No default value normalization: if a Talend XML omits a parameter (using Talend default), the config dict simply does not contain that key. The engine must provide its own defaults.
- No validation: invalid values pass through silently.

### Recommended Dedicated Parser

```python
def parse_tlogrow(self, node, component: Dict) -> Dict:
    """
    Parse tLogRow specific configuration from Talend XML node.

    Talend Parameters:
        BASIC_MODE (bool): Use basic delimited display. Default true.
        TABLE_PRINT (bool): Use table display. Default false.
        VERTICAL (bool): Use vertical display. Default false.
        FIELDSEPARATOR (str): Field separator for basic mode. Default "|"
        PRINT_HEADER (bool): Print header row. Default false.
        PRINT_UNIQUE (bool): Print component name prefix. Default false.
        PRINT_COLUMN_NAMES (bool): Print column name per value. Default false.
        USE_FIXED_LENGTH (bool): Fixed-width values. Default false.
        PRINT_CONTENT_WITH_LOG4J (bool): Route to logger. Default false.
        SCHEMA_OPT_NUM (int): Max rows to display. Default 100.
    """
    config = component['config']

    def get_param(name, default=''):
        elem = node.find(f'.//elementParameter[@name="{name}"]')
        return elem.get('value', default) if elem is not None else default

    def get_bool(name, default=False):
        val = get_param(name, str(default).lower())
        return val.lower() in ('true', '1', 'yes')

    def get_int(name, default=0):
        val = get_param(name, str(default))
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    # Display mode (mutually exclusive)
    config['basic_mode'] = get_bool('BASIC_MODE', True)
    config['table_print'] = get_bool('TABLE_PRINT', False)
    config['vertical'] = get_bool('VERTICAL', False)

    # Basic mode options
    config['field_separator'] = get_param('FIELDSEPARATOR', '|')
    config['print_header'] = get_bool('PRINT_HEADER', False)
    config['print_component_name'] = get_bool('PRINT_UNIQUE', False)
    config['print_column_names'] = get_bool('PRINT_COLUMN_NAMES', False)
    config['fixed_length'] = get_bool('USE_FIXED_LENGTH', False)

    # Output routing
    config['use_logger'] = get_bool('PRINT_CONTENT_WITH_LOG4J', False)

    # Display limit
    config['max_rows'] = get_int('SCHEMA_OPT_NUM', 100)

    return component
```

---

## Appendix B: Engine Class Structure

```
LogRow (BaseComponent)
    Constants:
        DEFAULT_FIELD_SEPARATOR = '|'
        DEFAULT_MAX_ROWS = 100

    Methods:
        _validate_config() -> List[str]            # Validates max_rows. DEAD CODE -- never called.
        _process(input_data) -> Dict[str, Any]      # Main entry point. Display + pass-through.
        _get_boolean_config(param_names, default)    # Dual-name boolean resolution.
        _print_table_format(df, separator, header)   # Table display with borders and alignment.
        _print_basic_format(df, separator, header)   # Basic delimited display.
        _print_vertical_format(df)                   # Vertical key-value display.
        validate_config() -> bool                    # Legacy wrapper. Dead code.

    Data Flow:
        Input: Optional[pd.DataFrame]
        Output: {'main': input_data}  # Pass-through unchanged
        Stats: {NB_LINE: rows_in, NB_LINE_OK: rows_logged, NB_LINE_REJECT: 0}
```

### Method Call Graph

```
execute() [BaseComponent]
  |-> _resolve_java_expressions()    # Resolve {{java}} markers in config
  |-> context_manager.resolve_dict() # Resolve ${context.var} in config
  |-> _auto_select_mode()            # Determine batch/streaming
  |-> _execute_batch()               # Always batch for LogRow (no streaming)
  |     |-> _process()               # Main logic
  |           |-> _get_boolean_config()        # x4 (basic_mode, table_print, vertical, print_header)
  |           |-> input_data.head(max_rows)    # Limit display rows
  |           |-> _print_vertical_format()     # If vertical=True
  |           |   OR _print_basic_format()     # If basic_mode=True
  |           |   OR _print_table_format()     # Default (table_print=True)
  |           |-> _update_stats()              # Set NB_LINE, NB_LINE_OK, NB_LINE_REJECT
  |           |-> return {'main': input_data}  # Pass-through
  |-> _update_global_map()           # Push stats to GlobalMap (BUG: crashes)
  |-> return result + stats
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Engine Reads? | Priority to Fix |
|------------------|---------------|--------|---------------|-----------------|
| `BASIC_MODE` | `BASIC_MODE` (raw) / `basic_mode` (dual) | Passed through | **Yes** (dual) | Default mismatch (P1) |
| `TABLE_PRINT` | `TABLE_PRINT` (raw) / `table_print` (dual) | Passed through | **Yes** (dual) | Default mismatch (P1) |
| `VERTICAL` | `VERTICAL` (raw) / `vertical` (dual) | Passed through | **Yes** (dual) | -- |
| `FIELDSEPARATOR` | `FIELDSEPARATOR` (raw) / `field_separator` (dual) | Passed through | **Yes** (dual) | -- |
| `PRINT_HEADER` | `PRINT_HEADER` (raw) / `print_header` (dual) | Passed through | **Yes** (dual) | Default mismatch (P1) |
| `PRINT_UNIQUE` | `PRINT_UNIQUE` (raw) | Passed through | **No** | Not implemented (P2) |
| `PRINT_COLUMN_NAMES` | `PRINT_COLUMN_NAMES` (raw) / `print_column_names` (dual) | Passed through | **Yes** (conflated with print_header) | Behavior wrong (P2) |
| `USE_FIXED_LENGTH` | `USE_FIXED_LENGTH` (raw) | Passed through | **No** | Not implemented (P2) |
| `PRINT_CONTENT_WITH_LOG4J` | `PRINT_CONTENT_WITH_LOG4J` (raw) | Passed through | **No** | Not implemented (P2) |
| `SCHEMA_OPT_NUM` | `SCHEMA_OPT_NUM` (raw) / `max_rows` (dual) | Passed through | **Yes** (dual) | -- |
| `TSTATCATCHER_STATS` | `TSTATCATCHER_STATS` (raw) | Passed through | No | Not needed (tStatCatcher rarely used) |
| `LABEL` | `LABEL` (raw) | Passed through | No | Not needed (cosmetic) |
| `PROPERTY_TYPE` | `PROPERTY_TYPE` (raw) | Passed through | No | Not needed (always Built-In) |

---

## Appendix D: Display Mode Comparison

### Basic Mode

**Talend (BASIC_MODE=true, FIELDSEPARATOR="|", PRINT_HEADER=false)**:
```
John|30|Engineer
Jane|25|Designer
```

**Talend (BASIC_MODE=true, FIELDSEPARATOR="|", PRINT_HEADER=true)**:
```
name|age|role
John|30|Engineer
Jane|25|Designer
```

**Talend (BASIC_MODE=true, PRINT_COLUMN_NAMES=true)**:
```
name:John|age:30|role:Engineer
name:Jane|age:25|role:Designer
```

**V1 Engine (basic_mode=True, field_separator="|", print_header=True)**:
```
name|age|role
John|30|Engineer
Jane|25|Designer
```

**V1 Engine Gap**: `PRINT_COLUMN_NAMES=true` produces the same output as `PRINT_HEADER=true` (header row) instead of per-value column name prefixing.

### Table Mode

**Talend (TABLE_PRINT=true)**:
```
.-----+----+---------.
|name |age |role     |
|=====+====+=========|
|John |30  |Engineer |
|Jane |25  |Designer |
'-----+----+---------'
```

**V1 Engine (table_print=True)**:
```
.----------------------------.
|     tLogRow_tLogRow_1      |
|====|===|=========|
|name|age|role     |
|====|===|=========|
|John|30 |Engineer |
|Jane|25 |Designer |
'----------------------------'
```

**V1 Engine Differences**:
1. V1 adds a component title row at the top (Talend does not in the standard table format)
2. V1 uses `=` for header separators, `|` for column separators
3. V1 has alignment differences in border widths (BUG-LR-008)
4. V1 uses `=` separators wrapped with `|=` and `=|` prefix/suffix

### Vertical Mode

**Talend (VERTICAL=true)**:
```
----
name : John
age : 30
role : Engineer
----
name : Jane
age : 25
role : Designer
----
```

**V1 Engine (vertical=True)**:
```

Row 1:
  name: John
  age: 30
  role: Engineer
------------------------------

Row 2:
  name: Jane
  age: 25
  role: Designer
------------------------------
```

**V1 Engine Differences**:
1. V1 uses `Row N:` prefix with 1-based numbering (Talend uses separator lines)
2. V1 indents values with 2 spaces (Talend does not indent)
3. V1 uses 30 dashes as separator (Talend uses 4 dashes)
4. V1 has blank line before each row

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 68-87)

This method validates:
- `max_rows` / `SCHEMA_OPT_NUM` is a valid non-negative integer (if present)

**Not validated**: `basic_mode`, `table_print`, `vertical` (booleans), `field_separator` (string), `print_header` (boolean).

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions. The `validate_config()` wrapper on line 224 calls `_validate_config()` but is itself never called.

### `_process()` (Lines 89-132)

The main processing method:
1. Check for empty/None input -- return early with zero stats (lines 91-94)
2. Count input rows (line 96)
3. Resolve display mode from config with dual naming (lines 100-103)
4. Resolve separator and max_rows from config with dual naming (lines 105-107)
5. Slice DataFrame to max_rows for display (line 110)
6. Try/except block for display formatting (lines 113-125):
   - If vertical: `_print_vertical_format()`
   - Elif basic_mode: `_print_basic_format()`
   - Else (default): `_print_table_format()`
7. Update statistics (line 128)
8. Return `{'main': input_data}` -- pass-through (line 132)

**Key observation**: The display formatting is wrapped in try/except (line 113-125), but the stats update and pass-through return are OUTSIDE the try block (lines 128-132). This means display errors do not prevent data pass-through. Good design.

**Key issue**: `NB_LINE_OK` is set to `rows_logged` (displayed rows) instead of `rows_in` (input rows). This is incorrect for a pass-through component.

### `_get_boolean_config()` (Lines 134-143)

Helper method for resolving boolean config values with support for multiple parameter names:
1. Iterates through a list of parameter name aliases
2. For each name, checks if the config has a value
3. If value is Python `bool`, returns it directly
4. If value is `str`, converts via case-insensitive check against `('true', '1', 'yes', 'on')`
5. If no matching parameter found, returns the default

**Observation**: This method correctly handles both Python booleans (from manual config) and string booleans (from Talend XML pass-through). However, it does not handle `int` values (e.g., `1` or `0`), which would fall through to the default. Not a practical concern since Talend XML always uses string values.

### `_print_table_format()` (Lines 145-204)

Table display with borders:
1. Early return for empty DataFrame (line 147-148)
2. Calculate column widths: max of (column name length, max value length, 1) per column (lines 151-155)
3. Calculate total table width (line 158)
4. Generate component title (line 161) -- prepends `tLogRow_` if ID doesn't start with it
5. Ensure table width accommodates title (lines 165-166)
6. Print top border: `.` + `-` * width + `.` (lines 169-170)
7. Print centered title (lines 173-176)
8. Print header separator with `=` characters (lines 179-183)
9. **Always** print column headers -- ignores `print_header` flag (lines 186-189)
10. Print header bottom separator (line 192)
11. Print data rows with left-justified values (lines 195-200)
12. Print bottom border: `'` + `-` * width + `'` (lines 203-204)

**Issue**: Table mode always prints headers (line 186-189 is unconditional). The `print_header` parameter is ignored for table format. This matches Talend behavior (table mode inherently shows headers), but the method signature accepts `print_header` without using it.

**Issue**: NaN values are handled on line 198: `str(row[col]) if pd.notna(row[col]) and str(row[col]) != 'nan' else ''`. The double check (`pd.notna()` AND `str() != 'nan'`) is redundant -- `pd.notna()` should suffice. The `str(row[col]) != 'nan'` check catches edge cases where a string column contains the literal string `"nan"`, which is overly aggressive (it would hide legitimate "nan" string values).

### `_print_basic_format()` (Lines 206-212)

Basic delimited display:
1. If `print_header` is True and DataFrame has columns, print header row (lines 208-209)
2. For each row, print separator-joined values (lines 211-212)
3. NaN values replaced with empty string (line 212)

**Observation**: Clean and correct implementation. The only issue is that `PRINT_COLUMN_NAMES` behavior (per-value prefix) is not implemented -- it is conflated with `PRINT_HEADER` (header row).

### `_print_vertical_format()` (Lines 214-221)

Vertical key-value display:
1. For each row, print `Row {idx + 1}:` header (line 217)
2. For each column, print `  {col}: {value}` (lines 218-220)
3. Print dashed separator (line 221)

**Observation**: Simple and correct. The `idx + 1` uses 1-based numbering for readability. NaN values are handled on line 219.

**Issue**: The format differs from Talend's vertical display (see Appendix D). Talend does not use "Row N:" prefix or indentation.

### `validate_config()` (Lines 224-231)

Legacy public wrapper that calls `_validate_config()` and logs errors. Returns `True` if no errors, `False` otherwise. Never called by any code path. Dead code.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Displays nothing. NB_LINE=0. Pass-through outputs empty flow. |
| **V1** | Returns `{'main': input_data}` with stats (0, 0, 0). Logs warning. |
| **Verdict** | CORRECT |

### Edge Case 2: None input

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable (FLOW always provides a schema-typed empty set). |
| **V1** | `input_data is None` check on line 91. Returns `{'main': None}` with stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 3: Single-row DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Displays one row in configured format. Pass-through forwards one row. |
| **V1** | All three modes handle single-row correctly. Table mode has proper borders. |
| **Verdict** | CORRECT |

### Edge Case 4: DataFrame with NaN/None values

| Aspect | Detail |
|--------|--------|
| **Talend** | Displays empty string for null values. |
| **V1** | Basic mode (line 212): `str(row[col]) if pd.notna(row[col]) else ''`. Table mode (line 198): `str(row[col]) if pd.notna(row[col]) and str(row[col]) != 'nan' else ''`. Vertical mode (line 219): `row[col] if pd.notna(row[col]) else ''`. |
| **Verdict** | MOSTLY CORRECT -- Table mode has an overly aggressive check that hides legitimate string "nan" values. |

### Edge Case 5: Very wide DataFrame (50+ columns)

| Aspect | Detail |
|--------|--------|
| **Talend** | Table mode wraps or scrolls. Basic mode produces long lines. |
| **V1** | Table mode calculates widths for all columns. Output may be very wide but renders correctly. No wrapping or truncation. |
| **Verdict** | CORRECT (though visual readability may suffer) |

### Edge Case 6: max_rows = 0

| Aspect | Detail |
|--------|--------|
| **Talend** | SCHEMA_OPT_NUM=0 may mean "display all" or "display none" depending on context. |
| **V1** | `input_data.head(0)` returns empty DataFrame. Zero rows displayed. Pass-through still returns all rows. Stats: NB_LINE=N, NB_LINE_OK=0. |
| **Verdict** | AMBIGUOUS -- if Talend treats 0 as "all", v1 behavior differs. |

### Edge Case 7: max_rows larger than input

| Aspect | Detail |
|--------|--------|
| **Talend** | Displays all rows. |
| **V1** | `head(max_rows)` returns entire DataFrame when max_rows > len(df). All rows displayed. |
| **Verdict** | CORRECT |

### Edge Case 8: Unicode column names and values

| Aspect | Detail |
|--------|--------|
| **Talend** | Java handles Unicode natively. Display depends on console encoding. |
| **V1** | Python 3 handles Unicode natively. `len(str(col))` counts characters, not display width. For CJK characters (display width 2), table columns may be misaligned. |
| **Verdict** | PARTIAL -- ASCII works correctly; CJK/wide characters may cause table misalignment. |

### Edge Case 9: Field separator is multi-character

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports multi-character separators in basic mode (e.g., `" \| "`). |
| **V1** | `separator.join(...)` works correctly with multi-character separators. |
| **Verdict** | CORRECT |

### Edge Case 10: Display mode flags all false

| Aspect | Detail |
|--------|--------|
| **Talend** | One mode is always selected (radio buttons). |
| **V1** | If `vertical=False`, `basic_mode=False`, `table_print=False` (all explicitly false), falls through to else branch (table format, line 119-121). |
| **Verdict** | CORRECT (defaults to table) -- but Talend always has exactly one true. |

### Edge Case 11: Display mode flags multiple true

| Aspect | Detail |
|--------|--------|
| **Talend** | Radio buttons enforce mutual exclusivity. Only one can be true. |
| **V1** | Priority order: vertical > basic_mode > table (if/elif/else on lines 115-121). If both `vertical=True` and `basic_mode=True`, vertical wins. |
| **Verdict** | ACCEPTABLE -- handles ambiguity with defined priority, though it should not occur from Talend conversion. |

### Edge Case 12: Context variable in field_separator

| Aspect | Detail |
|--------|--------|
| **Talend** | Context variables resolved before display. |
| **V1** | `context_manager.resolve_dict()` called in `execute()` (line 202) before `_process()`. Correctly resolves `${context.sep}` in field_separator. |
| **Verdict** | CORRECT |

### Edge Case 13: DataFrame with object dtype containing mixed types

| Aspect | Detail |
|--------|--------|
| **Talend** | Java toString() on each value. |
| **V1** | `str(row[col])` in all display modes. Works correctly for mixed types in object columns. |
| **Verdict** | CORRECT |

### Edge Case 14: DataFrame column order preservation

| Aspect | Detail |
|--------|--------|
| **Talend** | Columns displayed in schema order. |
| **V1** | `df.columns` iterates in DataFrame column order. Column order is preserved from input. |
| **Verdict** | CORRECT |

### Edge Case 15: Pass-through with downstream component

| Aspect | Detail |
|--------|--------|
| **Talend** | Downstream receives exact same rows as tLogRow input. |
| **V1** | `return {'main': input_data}` on line 132. Returns the original DataFrame reference (not a copy). Downstream gets the same object. |
| **Verdict** | CORRECT -- pass-through preserves identity. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `LogRow`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-LR-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-LR-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-LR-005 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-LR-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-LR-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-LR-003 / ENG-LR-003 -- NB_LINE_OK counts displayed rows

**File**: `src/v1/engine/components/transform/log_row.py`
**Line**: 128

**Current code (incorrect)**:
```python
self._update_stats(rows_in, rows_logged, 0)
```

**Fix**:
```python
self._update_stats(rows_in, rows_in, 0)
```

**Explanation**: For a pass-through component, all input rows are "OK" (successfully processed). The display row limit is a visual constraint, not a data flow filter. `NB_LINE_OK` should always equal `NB_LINE`.

**Impact**: Fixes downstream logic that checks `{id}_NB_LINE_OK` to know how many rows were passed through. **Risk**: Very low.

---

### Fix Guide: ENG-LR-001 / ENG-LR-002 -- Default mode and header mismatch

**File**: `src/v1/engine/components/transform/log_row.py`
**Lines**: 100-103

**Current code (Talend-incompatible defaults)**:
```python
basic_mode = self._get_boolean_config(['basic_mode', 'BASIC_MODE'], False)
table_print = self._get_boolean_config(['table_print', 'TABLE_PRINT'], True)
vertical = self._get_boolean_config(['vertical', 'VERTICAL'], False)
print_header = self._get_boolean_config(['print_header', 'PRINT_HEADER', 'print_column_names', 'PRINT_COLUMN_NAMES'], True)
```

**Fix**:
```python
basic_mode = self._get_boolean_config(['basic_mode', 'BASIC_MODE'], True)
table_print = self._get_boolean_config(['table_print', 'TABLE_PRINT'], False)
vertical = self._get_boolean_config(['vertical', 'VERTICAL'], False)
print_header = self._get_boolean_config(['print_header', 'PRINT_HEADER'], False)
```

**Changes**:
1. `basic_mode` default changed from `False` to `True` (matches Talend default)
2. `table_print` default changed from `True` to `False` (matches Talend default)
3. `print_header` default changed from `True` to `False` (matches Talend default)
4. Removed `print_column_names` / `PRINT_COLUMN_NAMES` aliases from `print_header` (separate Talend feature)

**Impact**: Changes default display format for all tLogRow components that do not explicitly set the mode. **Risk**: Medium -- existing v1 jobs relying on table-mode default will change appearance.

---

### Fix Guide: BUG-LR-004 -- Error handler print() in data stream

**File**: `src/v1/engine/components/transform/log_row.py`
**Lines**: 123-125

**Current code**:
```python
except Exception as e:
    logger.error(f"[{self.id}] Error during logging: {e}")
    print(f"[{self.id}] Error logging data: {e}")
```

**Fix**:
```python
except Exception as e:
    logger.error(f"[{self.id}] Error during logging: {e}")
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
```

**Changes**:
1. Removed `print()` debug artifact that mixed errors with data output
2. Added `ERROR_MESSAGE` globalMap variable for downstream error checking

**Impact**: Error messages no longer appear in data output stream. Downstream components can check `{id}_ERROR_MESSAGE`. **Risk**: Very low.

---

### Fix Guide: BUG-LR-006 -- Unhandled ValueError from int()

**File**: `src/v1/engine/components/transform/log_row.py`
**Line**: 107

**Current code**:
```python
max_rows = int(max_rows_param)
```

**Fix**:
```python
try:
    max_rows = int(max_rows_param)
    if max_rows < 0:
        logger.warning(f"[{self.id}] Negative max_rows ({max_rows}), using default {self.DEFAULT_MAX_ROWS}")
        max_rows = self.DEFAULT_MAX_ROWS
except (ValueError, TypeError):
    logger.warning(f"[{self.id}] Invalid max_rows value '{max_rows_param}', using default {self.DEFAULT_MAX_ROWS}")
    max_rows = self.DEFAULT_MAX_ROWS
```

**Impact**: Prevents ValueError crash on invalid config values. **Risk**: Very low.

---

### Fix Guide: CONV-LR-001 -- Dedicated converter parser

**File**: `src/converters/complex_converter/component_parser.py`

Add the `parse_tlogrow()` method from Appendix A to `ComponentParser` class. Register in `converter.py:_parse_component()`:

```python
elif component_type == 'tLogRow':
    component = self.component_parser.parse_tlogrow(node, component)
```

Also add an `elif` in `_map_component_parameters()`:

```python
elif component_type == 'tLogRow':
    return {
        'basic_mode': config_raw.get('BASIC_MODE', 'true').lower() == 'true',
        'table_print': config_raw.get('TABLE_PRINT', 'false').lower() == 'true',
        'vertical': config_raw.get('VERTICAL', 'false').lower() == 'true',
        'field_separator': config_raw.get('FIELDSEPARATOR', '|'),
        'print_header': config_raw.get('PRINT_HEADER', 'false').lower() == 'true',
        'print_component_name': config_raw.get('PRINT_UNIQUE', 'false').lower() == 'true',
        'print_column_names': config_raw.get('PRINT_COLUMN_NAMES', 'false').lower() == 'true',
        'fixed_length': config_raw.get('USE_FIXED_LENGTH', 'false').lower() == 'true',
        'use_logger': config_raw.get('PRINT_CONTENT_WITH_LOG4J', 'false').lower() == 'true',
        'max_rows': int(config_raw.get('SCHEMA_OPT_NUM', '100')) if config_raw.get('SCHEMA_OPT_NUM', '100').isdigit() else 100,
    }
```

**Impact**: Eliminates dual naming in engine. Normalizes parameter names and types. Enables validation at conversion time. **Risk**: Low -- must update engine to use new parameter names exclusively.

---

### Fix Guide: ENG-LR-004 -- Implement use_logger for PRINT_CONTENT_WITH_LOG4J

**File**: `src/v1/engine/components/transform/log_row.py`

Add a helper method that wraps `print()` or `logger.info()` based on config:

```python
def _output(self, text: str) -> None:
    """Output text to appropriate destination (stdout or logger)."""
    use_logger = self._get_boolean_config(['use_logger', 'PRINT_CONTENT_WITH_LOG4J'], False)
    if use_logger:
        logger.info(f"[{self.id}] {text}")
    else:
        print(text)
```

Then replace all `print(...)` calls in the three format methods with `self._output(...)`.

**Impact**: Enables log-level-based suppression of tLogRow output in production. **Risk**: Low.

---

## Appendix I: Comparison with Other Transform Components

| Feature | tLogRow (V1) | tFilterRow (V1) | tSortRow (V1) | tMap (V1) |
|---------|-------------|-----------------|----------------|-----------|
| Pass-through | **Yes** (primary purpose) | No (filters rows) | No (reorders rows) | No (transforms) |
| Modifies data | **No** | Yes (filters) | Yes (reorders) | Yes (maps) |
| Display output | **Yes** (primary purpose) | No | No | No |
| REJECT flow | No (not applicable) | Yes | No | Yes |
| Schema enforcement | No (display only) | Yes | Yes | Yes |
| V1 Unit tests | **No** | **No** | **No** | **No** |
| GlobalMap NB_LINE | Yes | Yes | Yes | Yes |
| GlobalMap ERROR_MESSAGE | **No** | **No** | **No** | **No** |
| Dedicated converter parser | **No** | Yes | No | Yes |

**Observation**: The lack of v1 unit tests is systemic across ALL transform components. The missing `ERROR_MESSAGE` globalMap variable is also a systemic gap.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs relying on tLogRow default display mode | **High** | Any job with tLogRow using Talend default (Basic mode) | Fix engine defaults (ENG-LR-001). Basic mode default must match Talend. |
| Jobs with downstream logic checking `NB_LINE_OK` | **High** | Any job reading `{id}_NB_LINE_OK` from globalMap after tLogRow | Fix stats to set NB_LINE_OK = NB_LINE (BUG-LR-003). |
| Jobs using `PRINT_CONTENT_WITH_LOG4J` | **Medium** | Jobs configured for Log4J output in production | Implement `use_logger` flag (ENG-LR-004). Without it, output always goes to stdout. |
| Jobs using `PRINT_UNIQUE` for multi-component identification | **Medium** | Jobs with multiple tLogRow components | Implement component name prefix (ENG-LR-005). |
| Jobs using `PRINT_COLUMN_NAMES` for self-describing output | **Medium** | Jobs using per-value column name prefixing | Separate from PRINT_HEADER (ENG-LR-006). Currently wrong behavior. |
| Cross-cutting GlobalMap crash | **Critical** | ALL jobs using globalMap | Fix BUG-LR-001 and BUG-LR-002 before any production use. |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using tLogRow as terminal sink | Low | Pass-through not exercised; display is the only purpose. |
| Jobs using fixed-length display | Low | Cosmetic feature rarely used in production. |
| Jobs using tStatCatcher with tLogRow | Low | tStatCatcher rarely used. |
| Vertical format cosmetic differences | Low | Output is for human consumption; format differences are visual only. |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting GlobalMap/base_component issues). These block ALL components.
2. **Phase 2**: Fix default mode and default print_header to match Talend. Run existing converted jobs to verify display output matches expectations.
3. **Phase 3**: Fix NB_LINE_OK stats. Verify downstream components that check globalMap variables work correctly.
4. **Phase 4**: Implement `PRINT_CONTENT_WITH_LOG4J` equivalent for production log management.
5. **Phase 5**: Add unit tests for the P0 test cases to prevent regression.

---

## Appendix K: Complete Engine Method-Level Code Review

### Line-by-Line Analysis: `_process()` (Lines 89-132)

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Process input data and log to console."""
    # Line 91-94: Empty input guard
    if input_data is None or input_data.empty:
        logger.warning(f"[{self.id}] Empty input received")
        self._update_stats(0, 0, 0)
        return {'main': input_data}
    # ANALYSIS: Correct. Returns the original input (None or empty DF) unchanged.
    # Stats (0,0,0) correctly reflect no rows processed.

    # Line 96-97: Count and log
    rows_in = len(input_data)
    logger.info(f"[{self.id}] Logging started: {rows_in} rows")
    # ANALYSIS: Correct. Good logging practice.

    # Line 99-103: Config resolution with dual naming
    basic_mode = self._get_boolean_config(['basic_mode', 'BASIC_MODE'], False)
    table_print = self._get_boolean_config(['table_print', 'TABLE_PRINT'], True)
    vertical = self._get_boolean_config(['vertical', 'VERTICAL'], False)
    print_header = self._get_boolean_config(
        ['print_header', 'PRINT_HEADER', 'print_column_names', 'PRINT_COLUMN_NAMES'], True)
    # ANALYSIS: ISSUE ENG-LR-001: Default basic_mode=False, table_print=True
    #   differs from Talend default basic_mode=true, table_print=false.
    # ANALYSIS: ISSUE ENG-LR-002: Default print_header=True differs from Talend false.
    # ANALYSIS: ISSUE NAME-LR-002: PRINT_COLUMN_NAMES aliased to print_header.

    # Line 105-107: Separator and max_rows
    field_separator = self.config.get('field_separator') or \
        self.config.get('FIELDSEPARATOR', self.DEFAULT_FIELD_SEPARATOR)
    max_rows_param = self.config.get('max_rows') or \
        self.config.get('SCHEMA_OPT_NUM', self.DEFAULT_MAX_ROWS)
    max_rows = int(max_rows_param)
    # ANALYSIS: field_separator uses `or` which treats empty string as falsy.
    #   If field_separator="" is intentional, it falls through to FIELDSEPARATOR.
    #   This may be a bug for empty separator config.
    # ANALYSIS: ISSUE BUG-LR-006: int() not wrapped in try/except.

    # Line 110-111: Limit display rows
    df_to_print = input_data.head(max_rows)
    rows_logged = len(df_to_print)
    # ANALYSIS: Correct. head() creates a view, not a copy. Memory efficient.

    # Lines 113-125: Display formatting with error catch
    try:
        if vertical:
            self._print_vertical_format(df_to_print)
        elif basic_mode:
            self._print_basic_format(df_to_print, field_separator, print_header)
        else:
            self._print_table_format(df_to_print, field_separator, print_header)
    except Exception as e:
        logger.error(f"[{self.id}] Error during logging: {e}")
        print(f"[{self.id}] Error logging data: {e}")
    # ANALYSIS: Priority order vertical > basic > table is correct.
    # ANALYSIS: ISSUE BUG-LR-004: Error swallowed. print() mixes with data stream.
    #   ERROR_MESSAGE not set in globalMap.

    # Line 128: Update statistics
    self._update_stats(rows_in, rows_logged, 0)
    # ANALYSIS: ISSUE BUG-LR-003: rows_logged != rows_in when max_rows < rows_in.
    #   Should be _update_stats(rows_in, rows_in, 0) for pass-through component.

    # Line 129: Log completion
    logger.info(f"[{self.id}] Logging complete: {rows_logged} rows displayed")
    # ANALYSIS: Correct log message. Shows displayed count, not total.

    # Line 132: Pass-through return
    return {'main': input_data}
    # ANALYSIS: Correct. Returns original input DataFrame reference unchanged.
    #   Pass-through invariant maintained.
```

### Line-by-Line Analysis: `_print_table_format()` (Lines 145-204)

```python
def _print_table_format(self, df: pd.DataFrame, separator: str, print_header: bool) -> None:
    # Line 147-148: Empty guard
    if df.empty:
        return
    # ANALYSIS: Correct but unreachable -- _process() already checks empty.

    # Lines 151-155: Column width calculation
    col_widths = {}
    for col in df.columns:
        max_value_len = df[col].fillna('').astype(str).str.len().max() \
            if not df.empty else 0
        col_widths[col] = max(len(str(col)), max_value_len, 1)
    # ANALYSIS: fillna('').astype(str) converts all values to strings.
    #   Creates intermediate Series per column. Acceptable for display-limited rows.
    # ANALYSIS: ISSUE BUG-LR-007: `if not df.empty` guard is redundant (line 147).

    # Lines 158: Total content width
    total_content_width = sum(col_widths.values()) + len(df.columns) - 1
    # ANALYSIS: Width = sum of column widths + (N-1) separators between columns.
    #   Does NOT account for the leading/trailing `|` characters.
    #   This creates inconsistency with the border widths.

    # Lines 161-166: Title and table width
    title = f"tLogRow_{self.id}" if not self.id.startswith('tLogRow') else self.id
    title_width = len(title)
    min_table_width = title_width + 4
    table_width = max(total_content_width, min_table_width)
    # ANALYSIS: ISSUE ENG-LR-009: If self.id='LogRow_1', title='tLogRow_LogRow_1'.
    #   Awkward naming when engine uses LogRow prefix instead of tLogRow.

    # Lines 169-170: Top border
    top_border = '.' + '-' * (table_width + 2) + '.'
    print(top_border)
    # ANALYSIS: Width = table_width + 4 total (`.` + `-` * (width+2) + `.`).

    # Lines 173-176: Title row
    title_padding = table_width - title_width
    left_pad = title_padding // 2
    right_pad = title_padding - left_pad
    print(f"|{' ' * left_pad}{title}{' ' * right_pad} |")
    # ANALYSIS: ISSUE BUG-LR-008: Extra space before `|` on closing side.
    #   Title row width = 1 + left_pad + title_width + right_pad + 1 + 1 = table_width + 3
    #   But top border inner width = table_width + 2. Off by one.

    # Lines 179-183: Header separator
    header_sep_parts = []
    for col in df.columns:
        header_sep_parts.append('=' * col_widths[col])
    header_separator = '|=' + '|'.join(header_sep_parts) + '=|'
    print(header_separator)
    # ANALYSIS: Width = 2 + sum(col_widths) + (N-1) + 2 = total_content_width + 4
    #   The `|=` prefix and `=|` suffix add 2 extra `=` characters.
    #   This may not match the top border width exactly.

    # Lines 186-189: Column headers (ALWAYS printed)
    header_parts = []
    for col in df.columns:
        header_parts.append(str(col).ljust(col_widths[col]))
    print(f"|{'|'.join(header_parts)}|")
    # ANALYSIS: print_header parameter is IGNORED for table mode.
    #   Table mode always shows headers. This matches Talend behavior.
    #   Width = 1 + sum(col_widths) + (N-1) + 1 = total_content_width + 2

    # Line 192: Second header separator
    print(header_separator)

    # Lines 195-200: Data rows
    for idx, row in df.iterrows():
        row_parts = []
        for col in df.columns:
            value = str(row[col]) \
                if pd.notna(row[col]) and str(row[col]) != 'nan' else ''
            row_parts.append(value.ljust(col_widths[col]))
        print(f"|{'|'.join(row_parts)}|")
    # ANALYSIS: ISSUE PERF-LR-001: iterrows() is slow for large DataFrames.
    # ANALYSIS: `str(row[col]) != 'nan'` check is overly aggressive.
    #   Hides legitimate string "nan" values.

    # Lines 203-204: Bottom border
    bottom_border = "'" + '-' * (table_width + 2) + "'"
    print(bottom_border)
    # ANALYSIS: Same width as top border. Uses `'` instead of `.`.
    #   Consistent.
```

---

## Appendix L: Talend tLogRow Generated Java Code Reference

In Talend, the generated Java code for tLogRow follows this pattern (simplified):

```java
// Basic mode (BASIC_MODE=true)
StringBuilder sb_tLogRow_1 = new StringBuilder();
if (PRINT_HEADER) {
    sb_tLogRow_1.append("col1").append("|").append("col2").append("\n");
}
sb_tLogRow_1.append(row.col1).append("|").append(row.col2);
if (PRINT_UNIQUE) {
    System.out.println("tLogRow_1|" + sb_tLogRow_1.toString());
} else {
    System.out.println(sb_tLogRow_1.toString());
}
// OR with Log4J:
if (PRINT_CONTENT_WITH_LOG4J) {
    log.info("tLogRow_1|" + sb_tLogRow_1.toString());
}

// Pass-through: output = input (direct assignment)
row_output = row_input;
nb_line_tLogRow_1++;
```

Key observations from the generated code:
1. **StringBuilder** is used for efficient string concatenation (v1 uses multiple `print()` calls)
2. **PRINT_UNIQUE** prepends component name with `|` separator (not implemented in v1)
3. **PRINT_CONTENT_WITH_LOG4J** uses `log.info()` instead of `System.out.println()` (not implemented in v1)
4. **Pass-through** is a direct assignment (`row_output = row_input`), not a copy
5. **NB_LINE** is incremented per row (v1 sets it once after processing)
6. **PRINT_COLUMN_NAMES** (not shown) adds `col1:` prefix before each value in basic mode

---

## Appendix M: Dual Parameter Naming Inventory

The following table documents every config parameter accessed in `log_row.py` with both its Python-style and Talend-style names, showing which code paths check which names:

| Line | Python Name | Talend Name | Method | Default | Notes |
|------|-------------|-------------|--------|---------|-------|
| 100 | `basic_mode` | `BASIC_MODE` | `_get_boolean_config` | `False` | **Talend default is `True`** |
| 101 | `table_print` | `TABLE_PRINT` | `_get_boolean_config` | `True` | **Talend default is `False`** |
| 102 | `vertical` | `VERTICAL` | `_get_boolean_config` | `False` | Matches Talend |
| 103 | `print_header` | `PRINT_HEADER` | `_get_boolean_config` | `True` | **Talend default is `False`** |
| 103 | `print_column_names` | `PRINT_COLUMN_NAMES` | `_get_boolean_config` | (same as print_header) | **Wrong: different Talend feature** |
| 105 | `field_separator` | `FIELDSEPARATOR` | `config.get()` or fallback | `'\|'` | Matches Talend |
| 106 | `max_rows` | `SCHEMA_OPT_NUM` | `config.get()` or fallback | `100` | Talend default varies |
| 78 | `max_rows` | `SCHEMA_OPT_NUM` | `_validate_config` (dead) | N/A | Validation never called |

**Total dual-naming lookups**: 7 parameters x 2 names = 14 config lookups. A dedicated converter parser would reduce this to 7.

---

## Appendix N: Output Stream Architecture

```
                    +------------------+
                    | Talend tLogRow   |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    PRINT_CONTENT_WITH_LOG4J     PRINT_CONTENT_WITH_LOG4J
         = false                      = true
              |                             |
    System.out.println()          log.info() [Log4J]
              |                             |
         Console                    Log Appender
                                   (file, DB, etc.)

                    +------------------+
                    |  V1 Engine LogRow|
                    +--------+---------+
                             |
                        print()
                             |
                     sys.stdout ONLY
                             |
                        Console
```

**Gap**: The v1 engine has no equivalent to Log4J routing. All output goes to `sys.stdout` via `print()`. There is no mechanism to:
- Route output to a log file via logging configuration
- Suppress output by changing log level
- Capture output programmatically without redirecting stdout
- Distinguish tLogRow data output from error/diagnostic output

This is the most significant architectural gap for production use of tLogRow.

---

## Appendix O: Pass-Through Invariant Verification

The pass-through invariant is the most critical behavioral requirement for tLogRow. The following analysis verifies it is maintained:

### Code Path Analysis

1. **Normal execution** (lines 89-132):
   - Input: `input_data` parameter
   - Processing: Display formatting (side effect only)
   - Output: `return {'main': input_data}` -- same object reference
   - **INVARIANT MAINTAINED**

2. **Empty input** (lines 91-94):
   - Input: `None` or empty DataFrame
   - Output: `return {'main': input_data}` -- same object reference
   - **INVARIANT MAINTAINED**

3. **Display error** (lines 113-125):
   - Input: any DataFrame
   - Processing: Display raises exception, caught silently
   - Output: Falls through to `return {'main': input_data}` -- same object reference
   - **INVARIANT MAINTAINED**

4. **max_rows limiting** (line 110):
   - `df_to_print = input_data.head(max_rows)` creates a SEPARATE view for display
   - The original `input_data` is NOT modified
   - Output: `return {'main': input_data}` -- original, unlimited data
   - **INVARIANT MAINTAINED**

### Potential Violations (Not Present)

- No `df.drop()`, `df.drop_duplicates()`, `df.sort_values()` called on `input_data`
- No `validate_schema()` called (which could modify column types)
- No column renaming, addition, or removal
- Return statement uses `input_data`, not `df_to_print`

### Conclusion

The pass-through invariant is correctly maintained in all code paths. The `input_data` reference is never modified and is always returned as the `main` output. The `df_to_print` slice is used only for display purposes and is not returned.

---

## Appendix P: Comparison with Talend's Actual Table Format

Talend's actual table format output (from Talend Studio console) follows this pattern:

```
.----+-----+---------.
|name|age  |role     |
|=====+=====+=========|
|John|30   |Engineer |
|Jane|25   |Designer |
'-----+-----+---------'
```

Versus v1 engine output:

```
.----------------------------.
|     tLogRow_tLogRow_1      |
|====|===|=========|
|name|age|role     |
|====|===|=========|
|John|30 |Engineer |
|Jane|25 |Designer |
'----------------------------'
```

### Differences

| Aspect | Talend | V1 Engine |
|--------|--------|-----------|
| Title row | None | Component name centered |
| Top border corners | `.` | `.` (matches) |
| Bottom border corners | `'` | `'` (matches) |
| Column separators in border | `+` | `\|` (different) |
| Header separator | `=` with `+` at column boundaries | `=` with `\|` at column boundaries |
| Data alignment | Left-justified | Left-justified (matches) |
| Border width consistency | Consistent | Off-by-one (BUG-LR-008) |
| Column padding | 1 space after value | None |

The v1 engine's table format is a reasonable approximation of Talend's table mode but differs in several cosmetic details. For debugging purposes, these differences are unlikely to cause issues. However, for automated output comparison (regression testing), the differences would cause false failures.

---

## Appendix Q: Recommended Unit Test Implementation

```python
"""
Unit tests for LogRow component (v1 engine).

Test file: tests/v1/unit/test_log_row.py
"""
import pytest
import pandas as pd
from io import StringIO
from unittest.mock import patch

from src.v1.engine.components.transform.log_row import LogRow
from src.v1.engine.global_map import GlobalMap


class TestLogRowPassThrough:
    """Tests for pass-through invariant."""

    def test_passthrough_returns_same_object(self):
        """Pass-through should return the exact same DataFrame object."""
        config = {'basic_mode': True, 'max_rows': 10}
        component = LogRow('test_1', config)
        df = pd.DataFrame({'a': [1, 2], 'b': ['x', 'y']})

        with patch('builtins.print'):
            result = component._process(df)

        assert result['main'] is df  # Identity check

    def test_passthrough_with_max_rows_returns_all_data(self):
        """Even when max_rows limits display, all rows pass through."""
        config = {'basic_mode': True, 'max_rows': 1}
        component = LogRow('test_2', config)
        df = pd.DataFrame({'a': range(100)})

        with patch('builtins.print'):
            result = component._process(df)

        assert len(result['main']) == 100

    def test_empty_input(self):
        """Empty DataFrame returns unchanged."""
        config = {'basic_mode': True}
        component = LogRow('test_3', config)
        df = pd.DataFrame()

        result = component._process(df)

        assert result['main'] is df
        assert component.stats['NB_LINE'] == 0

    def test_none_input(self):
        """None input returns None."""
        config = {'basic_mode': True}
        component = LogRow('test_4', config)

        result = component._process(None)

        assert result['main'] is None
        assert component.stats['NB_LINE'] == 0


class TestLogRowDisplayModes:
    """Tests for display format output."""

    def test_basic_mode_output(self):
        """Basic mode outputs separator-delimited rows."""
        config = {'basic_mode': True, 'field_separator': '|',
                  'print_header': False, 'max_rows': 100}
        component = LogRow('test_5', config)
        df = pd.DataFrame({'name': ['John'], 'age': [30]})

        with patch('builtins.print') as mock_print:
            component._process(df)

        calls = [str(c) for c in mock_print.call_args_list]
        assert any('John' in c and '30' in c for c in calls)

    def test_table_mode_output(self):
        """Table mode outputs bordered table."""
        config = {'table_print': True, 'max_rows': 100}
        component = LogRow('test_6', config)
        df = pd.DataFrame({'name': ['John']})

        with patch('builtins.print') as mock_print:
            component._process(df)

        calls = [str(c[0][0]) if c[0] else '' for c in mock_print.call_args_list]
        assert any('.' in c and '-' in c for c in calls)  # Top border

    def test_vertical_mode_output(self):
        """Vertical mode outputs key-value pairs."""
        config = {'vertical': True, 'max_rows': 100}
        component = LogRow('test_7', config)
        df = pd.DataFrame({'name': ['John'], 'age': [30]})

        with patch('builtins.print') as mock_print:
            component._process(df)

        calls = [str(c) for c in mock_print.call_args_list]
        assert any('name: John' in c for c in calls)
        assert any('age: 30' in c for c in calls)


class TestLogRowStatistics:
    """Tests for statistics tracking."""

    def test_stats_with_max_rows_limit(self):
        """NB_LINE should count all rows, NB_LINE_OK should equal NB_LINE."""
        config = {'basic_mode': True, 'max_rows': 5}
        component = LogRow('test_8', config)
        df = pd.DataFrame({'a': range(20)})

        with patch('builtins.print'):
            component._process(df)

        assert component.stats['NB_LINE'] == 20
        # NOTE: Currently fails -- BUG-LR-003
        # assert component.stats['NB_LINE_OK'] == 20
```

**Note**: These tests are provided as a recommendation. They should be placed in `tests/v1/unit/test_log_row.py` and executed with pytest.
