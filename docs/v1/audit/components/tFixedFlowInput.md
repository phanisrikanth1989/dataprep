# Audit Report: tFixedFlowInput / FixedFlowInputComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFixedFlowInput` |
| **V1 Engine Class** | `FixedFlowInputComponent` |
| **Engine File** | `src/v1/engine/components/file/fixed_flow_input.py` (330 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfixedflowinput()` (lines 1532-1663) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFixedFlowInput'` (line 278) |
| **Registry Aliases** | `FixedFlowInputComponent`, `tFixedFlowInput` (registered in `src/v1/engine/engine.py` lines 66-67) |
| **Category** | Misc / Input |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/fixed_flow_input.py` | Engine implementation (330 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1532-1663) | Dedicated `parse_tfixedflowinput()` parser method |
| `src/converters/complex_converter/converter.py` (line 278-279) | Dispatch -- dedicated `elif` branch for `tFixedFlowInput` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `ComponentExecutionError`) |
| `src/v1/engine/context_manager.py` | ContextManager for `${context.var}` resolution and expression concatenation |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 17) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 3 | 1 | Dedicated parser exists; 7 of ~10 Talend params extracted (~70%); INTABLE parsing stubbed; context vars in inline content not documented; VALUES pairing fragile |
| Engine Feature Parity | **Y** | 1 | 8 | 2 | 1 | Three modes implemented; nb_rows ignored in inline mode (correct); no validate_schema() call; no REJECT flow; `_resolve_value()` uses `eval()`; globalMap cast/regex handling broken (BUG-FFI-010/011/012); resolve_dict() skips List[Dict] (BUG-FFI-013) |
| Code Quality | **Y** | 2 | 3 | 5 | 2 | Cross-cutting base class bugs; dead `_validate_config()`; `eval()` security risk; bare `except` clauses; `_update_stats()` semantics wrong; negative int coercion (BUG-FFI-014) |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Data generated in-memory (appropriate for fixed row component); minor optimization opportunities |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero unit tests; zero integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFixedFlowInput Does

`tFixedFlowInput` generates a fixed number of rows of predefined data and feeds them into the data flow. It is commonly used for creating test data, providing constant lookup values, building SQL DDL statement lists, setting up context loading flows, and feeding fixed parameters into downstream components. The component does NOT read from a file or database -- it generates data purely from its configuration.

**Source**: [tFixedFlowInput Standard Properties (Talend 7.3)](https://help.talend.com/r/en-US/7.3/tfixedflowinput/tfixedflowinput-standard-properties), [Configuring tFixedFlowInput (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/excel/tfileinputjson-tflowinput-tjavarow-tlogrow-configuring-tfixedflowinput-component-standard-component), [Uma's Blog: tFixedFlowInput in many ways](http://umashanthan.blogspot.com/2015/08/how-to-use-tfixedflowinput-in-many-ways.html), [TutorialGateway: Talend tFixedFlowInput](https://www.tutorialgateway.org/talend-tfixedflowinput/)

**Component family**: Misc (Miscellaneous / Input)
**Available in**: All Talend products (Standard). Also available in Spark Batch and Spark Streaming variants.
**Required JARs**: None (pure in-memory generation)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. |
| 3 | Number of Rows | `NB_ROWS` | Integer | `1` | **Key parameter**. Total number of rows to generate. In Single mode and Inline Table mode, controls repetition. In Inline Content mode, Talend ignores this value and instead processes all rows in the content. |
| 4 | Mode: Use Single Table | `USE_SINGLEMODE` | Radio (Boolean) | `true` | **Default mode**. Enables the VALUES table where each schema column gets a single value expression. The same row of values is repeated `NB_ROWS` times. Values can be Java expressions, context variables, globalMap references, routine calls, or literal constants. Supports Ctrl+Space auto-completion for global variables. |
| 5 | Mode: Use Inline Table | `USE_INTABLE` | Radio (Boolean) | `false` | Enables an inline table editor where each UI row corresponds to one output row. Each cell can contain a Java expression or literal value. `NB_ROWS` controls the total rows generated; if `NB_ROWS` exceeds the table row count, remaining rows are empty/null. |
| 6 | Mode: Use Inline Content (delimited file) | `USE_INLINECONTENT` | Radio (Boolean) | `false` | Enables a free-text area where multi-row data is entered as a delimited string. Rows are separated by the Row Separator and fields by the Field Separator. **Context variables are NOT supported** in inline content (the content is treated as literal text, like reading from a delimited file). |
| 7 | VALUES Table | `VALUES` | Table (SCHEMA_COLUMN, VALUE) | -- | Only visible when `USE_SINGLEMODE=true`. Two-column table mapping each schema column to a value expression. Each row in the table has `elementRef="SCHEMA_COLUMN"` and `elementRef="VALUE"` pairs. Values can be: string literals (quoted), numeric literals, Java expressions, `context.var` references, `globalMap.get("key")` calls, routine invocations (e.g., `TalendDate.getCurrentDate()`). |
| 8 | Inline Table | `INTABLE` | Table (per-column values) | -- | Only visible when `USE_INTABLE=true`. Multi-row table where each row is a distinct output record. Each cell maps to a schema column. Supports Java expressions in each cell. |
| 9 | Inline Content | `INLINECONTENT` | Multiline String | `""` | Only visible when `USE_INLINECONTENT=true`. Free-text block of delimited data. Example: `"John;30\nJane;25"` with `FIELDSEPARATOR=";"` and `ROWSEPARATOR="\n"`. |
| 10 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | Only visible when `USE_INLINECONTENT=true`. Separator between rows in the inline content. Common values: `"\n"`, `"\r\n"`, `"|"`. |
| 11 | Field Separator | `FIELDSEPARATOR` | String | `";"` | Only visible when `USE_INLINECONTENT=true`. Separator between fields within a row. Common values: `";"`, `","`, `"|"`, `"\t"`. **Note**: Talend default is semicolon, not comma. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 12 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Stop the entire job on error. When unchecked, errors are logged but the job continues. Note: default is `true` (unlike `tFileInputDelimited` where default is `false`). |
| 13 | Custom Flush Buffer Size | -- | Boolean (CHECK) | `false` | Advanced setting to customize the output buffer flush size. Rarely used. |
| 14 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher. Rarely used. |
| 15 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |
| 16 | Connection Format | `CONNECTION_FORMAT` | String | `"row"` | Connection format (typically "row" for standard row-based flow). |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Generated rows matching the output schema. All columns defined in the schema are present. Primary data output. |
| `ITERATE` | Output | Iterate | Enables iterative processing when combined with `tFlowToIterate`. Each generated row becomes one iteration. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: Unlike `tFileInputDelimited`, `tFixedFlowInput` does NOT have a REJECT connection. Since the data is user-defined, there is no concept of "malformed input" to reject.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows generated. Equals `NB_ROWS` in Single mode, number of table rows in Inline Table mode, number of content rows in Inline Content mode. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output via the FLOW connection. Should always equal `NB_LINE` since there is no rejection logic. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 -- no rejection mechanism exists for this component. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. |

### 3.5 Behavioral Notes

1. **Single mode (USE_SINGLEMODE=true)**: The VALUES table defines one "template row". This row is repeated `NB_ROWS` times. Each cell in the VALUES table can be a Java expression, which is evaluated ONCE per row (not once for the entire batch). This means expressions like `Numeric.sequence("s1", 1, 1)` increment per row.

2. **Inline Table mode (USE_INTABLE=true)**: Each table row is an independent record. If `NB_ROWS` exceeds the number of table rows, extra rows may be null-filled or the table rows may cycle (behavior depends on Talend version). In most cases, `NB_ROWS` should match or exceed the inline table row count.

3. **Inline Content mode (USE_INLINECONTENT=true)**: The content is parsed like a delimited file. `NB_ROWS` is typically ignored -- all rows in the content are processed. **Context variables are NOT supported** in inline content. The content string is treated as literal text. To use dynamic values, use Single mode or Inline Table mode instead.

4. **Expression evaluation in VALUES**: Values in the VALUES table are Java expressions compiled and executed at runtime. Common patterns include:
   - String literals: `"Hello"` (quotes included in the XML value)
   - Integer literals: `42` (no quotes)
   - Context variables: `context.myVar`
   - GlobalMap references: `(String)globalMap.get("tFileList_1_CURRENT_FILE")`
   - Concatenation: `context.prefix + "_" + context.suffix`
   - Routine calls: `TalendDate.getCurrentDate()`, `TalendString.getAsciiRandomString(10)`
   - Sequence generation: `routines.system.Numeric.sequence("seq1", 1, 1)`

5. **NB_ROWS=0**: Generates zero rows. Returns an empty DataFrame with the correct schema columns. This is valid and commonly used in conditional flows.

6. **No REJECT flow**: Unlike input components that read external data, tFixedFlowInput has no concept of "bad rows" since all data is predefined. There is no REJECT connector.

7. **Common use cases**:
   - Providing fixed parameters to downstream components (e.g., SQL queries, file paths)
   - Creating test data for development and debugging
   - Building DDL statement lists for database operations
   - Feeding context variable values into `tContextLoad`
   - Generating a single row to trigger downstream processing

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** `parse_tfixedflowinput()` in `component_parser.py` (lines 1532-1663). This is dispatched from `converter.py` line 278 via `elif component_type == 'tFixedFlowInput'`. This follows the recommended pattern (unlike `tFileInputDelimited` which uses the deprecated generic mapper).

**Converter flow**:
1. `converter.py:_parse_component()` identifies `tFixedFlowInput` at line 278
2. Calls `self.component_parser.parse_tfixedflowinput(node, component)`
3. Parser extracts: `NB_ROWS`, `CONNECTION_FORMAT`, mode flags, inline content params, schema, VALUES table, INTABLE (stubbed), generates `rows` list
4. Schema extracted from `<metadata connector="FLOW">` nodes
5. VALUES table parsed by iterating `elementValue` pairs
6. Pre-generates `rows` list from configuration for engine consumption

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `NB_ROWS` | Yes | `nb_rows` | 1553 | Converted to `int()` -- will throw `ValueError` on non-numeric strings (e.g., context vars) |
| 2 | `CONNECTION_FORMAT` | Yes | `connection_format` | 1554 | Default `'row'` -- informational, not used by engine |
| 3 | `USE_SINGLEMODE` | Yes | `use_singlemode` | 1557 | Boolean via `str_to_bool()` helper |
| 4 | `USE_INTABLE` | Yes | `use_intable` | 1558 | Boolean via `str_to_bool()` helper |
| 5 | `USE_INLINECONTENT` | Yes | `use_inlinecontent` | 1559 | Boolean via `str_to_bool()` helper |
| 6 | `ROWSEPARATOR` | Yes | `row_separator` | 1566 | Default `'\n'` matches Talend |
| 7 | `FIELDSEPARATOR` | Yes | `field_separator` | 1567 | Default `';'` matches Talend default |
| 8 | `INLINECONTENT` | Yes | `inline_content` | 1568 | Default `''` |
| 9 | `VALUES` | Yes | `values_config` + `rows` | 1586-1609 | Parsed via `elementValue` pair iteration |
| 10 | `INTABLE` | **Stub** | `intable_data` | 1614-1618 | **`pass` statement -- INTABLE parsing not implemented** |
| 11 | `SCHEMA` | Yes | `schema` | 1571-1578 | Extracted from `<metadata connector="FLOW">` with type conversion |
| 12 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted by parser. Engine defaults to `True`.** |
| 13 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 14 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 15 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 9 of 11 runtime-relevant parameters extracted (~82%). 1 critical stub (INTABLE), 1 missing runtime parameter (DIE_ON_ERROR).

### 4.2 Schema Extraction

Schema is extracted via a dedicated loop in `parse_tfixedflowinput()` (lines 1571-1578).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | `column.get('name', '')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | **No** | Not extracted |
| `length` | **No** | Not extracted |
| `precision` | **No** | Not extracted |
| `pattern` (date) | **No** | Not extracted -- important for date-typed columns |
| `default` | **No** | Not extracted |
| `comment` | **No** | Not extracted (cosmetic) |
| `talendType` | **No** | Full Talend type string not preserved |

### 4.3 VALUES Table Parsing

The VALUES table parsing (lines 1586-1609) uses a **paired iteration** approach:

```python
elements = values_table.findall('./elementValue')
for i in range(0, len(elements), 2):
    if i + 1 < len(elements):
        schema_col_elem = elements[i]
        value_elem = elements[i + 1]
        if (schema_col_elem.get('elementRef') == 'SCHEMA_COLUMN' and
                value_elem.get('elementRef') == 'VALUE'):
            column_name = schema_col_elem.get('value', '').strip('"')
            column_value = value_elem.get('value', '').strip('"')
```

**Assumption**: Elements alternate SCHEMA_COLUMN, VALUE, SCHEMA_COLUMN, VALUE. If Talend XML ever stores these in a different order (e.g., grouped by row rather than alternating), parsing breaks silently. The `elementRef` checks provide some validation but the index-based pairing is fragile.

**Expression handling in VALUES**:
- `context.var` references are wrapped as `${context.var}` (line 1603-1604) -- correct
- Other non-quoted values are passed through `mark_java_expression()` (line 1607) -- correct
- **Missing**: `globalMap.get()` references are not explicitly handled in the converter; they pass through as raw strings and must be resolved at runtime by the engine's `_resolve_value()` method

### 4.4 Inline Content Pre-Parsing in Converter

The converter pre-parses inline content rows at conversion time (lines 1632-1649), generating the `rows` list. This means:
- Content is split by `row_separator` and `field_separator` at conversion time
- The engine also splits content again at runtime (in `_generate_inline_content_rows()`)
- **Double parsing**: Both converter and engine parse inline content, which is redundant. The converter generates `rows`, but the engine checks `rows` first (in single mode) and falls back to re-parsing `inline_content` (in inline content mode). For inline content mode, the engine ignores the pre-parsed `rows` and re-parses `inline_content` directly.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FFI-001 | **P1** | **INTABLE parsing is a stub**: `parse_tfixedflowinput()` line 1617-1618 contains only `pass`. Any job using `USE_INTABLE=true` will get an empty `intable_data` list, causing the engine to generate null-filled rows. The Inline Table mode is completely non-functional at the converter level. |
| CONV-FFI-002 | **P1** | **DIE_ON_ERROR not extracted**: The converter does not extract `DIE_ON_ERROR` from the Talend XML. The engine defaults to `True` (line 156 of `fixed_flow_input.py`), which matches Talend's default for this component. However, if a job explicitly sets `DIE_ON_ERROR=false`, the converter will not pass this through, and the engine will still fail on errors instead of returning an empty DataFrame. |
| CONV-FFI-003 | **P2** | **VALUES pairing assumes alternating order**: The paired iteration (`for i in range(0, len(elements), 2)`) assumes `elementValue` elements always alternate SCHEMA_COLUMN then VALUE. If Talend XML ever groups them differently (e.g., all SCHEMA_COLUMNs first, then all VALUEs), parsing will silently produce wrong mappings. Should use `elementRef` attribute to match pairs dynamically. |
| CONV-FFI-004 | **P2** | **NB_ROWS `int()` conversion crashes on expressions**: Line 1553 does `int(get_param('NB_ROWS', '1'))`. If `NB_ROWS` contains a context variable (`context.rowCount`) or Java expression, `int()` throws `ValueError`. Should handle non-numeric values gracefully like `tFileInputDelimited` does with `.isdigit()`. |
| CONV-FFI-005 | **P2** | **Schema type format violates STANDARDS.md**: Types are converted to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine's `validate_schema()` handles both formats, this violates the documented standard. |
| CONV-FFI-006 | **P3** | **Redundant inline content parsing**: Both converter (lines 1632-1649) and engine (`_generate_inline_content_rows()`) parse inline content. The converter-generated `rows` are ignored by the engine in inline content mode because the engine checks `use_inlinecontent` before checking `rows`. The converter's inline parsing is dead code for this mode. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Single mode (VALUES) | **Yes** | High | `_generate_single_mode_rows()` line 165 | Uses pre-parsed `rows` from converter or falls back to `values_config` |
| 2 | Inline Table mode | **Partial** | Low | `_generate_intable_mode_rows()` line 195 | Engine method exists but converter provides empty `intable_data`. Null-fills beyond data. |
| 3 | Inline Content mode | **Yes** | High | `_generate_inline_content_rows()` line 217 | Splits content by separators, maps to schema columns |
| 4 | NB_ROWS generation | **Yes** | Medium | `_process()` line 116 | Used in single and intable modes; correctly ignored in inline content mode (line 244-246) |
| 5 | Schema column naming | **Yes** | High | Throughout `_generate_*` methods | Uses `col['name']` from schema definition |
| 6 | Context variable resolution | **Yes** | Medium | `_resolve_value()` line 268 | Handles `${context.var}`, `context.var`, and `globalMap.get()` patterns. Uses `context_manager.resolve_string()` as primary. |
| 7 | Java expression resolution | **Yes** | Medium | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers before `_process()` |
| 8 | GlobalMap reference resolution | **Yes** | Low | `_resolve_value()` line 308-323 | Regex-based `globalMap.get()` extraction with `eval()` for complex expressions. **Security risk.** |
| 9 | Row separator normalization | **Yes** | Medium | `_generate_inline_content_rows()` line 232 | Handles `\\n` -> `\n` conversion |
| 10 | Field separator normalization | **Yes** | Medium | `_generate_inline_content_rows()` line 234 | Handles `\\|` -> `|` conversion. Only handles pipe; other escapes (e.g., `\\t`) not normalized. |
| 11 | Empty row filtering (inline) | **Yes** | High | `_generate_inline_content_rows()` line 241 | `row.strip()` filter removes empty rows from split |
| 12 | Die on error | **Yes** | High | `_process()` line 156 | Re-raises or returns empty DataFrame |
| 13 | Statistics tracking | **Partial** | Low | `_process()` line 142 | Passes `(0, rows_generated, 0)` -- NB_LINE is 0 instead of rows_generated |
| 14 | Empty schema handling | **Yes** | High | `_process()` line 150-152 | Returns empty DataFrame with correct column names |
| 15 | DataFrame creation | **Yes** | High | `_process()` line 146 | `pd.DataFrame(output_data)` from list of dicts |
| 16 | **validate_schema()** | **No** | N/A | -- | **Never called. Generated DataFrame is not type-validated against schema.** |
| 17 | **REJECT flow** | **No** | N/A | -- | No REJECT connector (correct -- matches Talend behavior for this component) |
| 18 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | Error message not stored in globalMap on failure |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FFI-001 | **P0** | **`_update_stats()` passes wrong NB_LINE value**: Line 142 calls `self._update_stats(0, rows_generated, 0)`. The first argument is `rows_read` which maps to `NB_LINE`. Passing `0` means `{id}_NB_LINE` in globalMap will always be `0`, while `{id}_NB_LINE_OK` will have the correct count. Talend sets `NB_LINE` to the total rows generated. Should be `self._update_stats(rows_generated, rows_generated, 0)`. |
| ENG-FFI-002 | **P1** | **`_resolve_value()` uses `eval()` for globalMap expressions**: Line 321 calls `eval(new_value)` on a user-controlled string derived from globalMap references after partial string replacement. This is a **code injection vulnerability**. If a globalMap value contains malicious content (e.g., `__import__('os').system('rm -rf /')`), it will be executed. While the risk is low in Talend-converted jobs (config is trusted), this violates secure coding practices. |
| ENG-FFI-003 | **P1** | **`validate_schema()` never called**: Unlike other components (e.g., `FileInputDelimited`), `FixedFlowInputComponent._process()` never calls `self.validate_schema(df, schema_columns)`. Generated data is returned as-is with whatever types Python infers from the raw values (all strings from inline content, mixed types from VALUES). Integer columns may be strings, dates will be strings, etc. |
| ENG-FFI-004 | **P1** | **Inline content field separator normalization incomplete**: Line 234 only handles `\\|` -> `|`. Other common escape sequences like `\\t` (tab), `\\;` (semicolon), `\\,` (comma) are not normalized. A Talend job with `FIELDSEPARATOR="\\t"` will fail to split correctly because the engine will look for the literal two-character string `\t` rather than a tab character. |
| ENG-FFI-005 | **P1** | **No `{id}_ERROR_MESSAGE` in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap. Downstream error handling flows referencing `(String)globalMap.get("tFixedFlowInput_1_ERROR_MESSAGE")` will get null. |
| ENG-FFI-006 | **P2** | **Inline content strips field values unconditionally**: Line 256 calls `field_values[col_idx].strip()` on every field value. In Talend, inline content values are NOT trimmed by default. Leading/trailing whitespace in field values is significant. For example, `" John "` should remain `" John "` unless trimming is explicitly enabled. |
| ENG-FFI-007 | **P2** | **Single mode ignores NB_ROWS when `rows` is populated**: In `_generate_single_mode_rows()` line 169, when `rows` is non-empty (populated by converter), the method returns all pre-parsed rows without checking `nb_rows`. If the converter generated 3 rows but `NB_ROWS=5`, only 3 rows are returned. The fallback `values_config` path (line 184) correctly uses `nb_rows`, but the primary `rows` path does not. |
| ENG-FFI-008 | **P2** | **Intable mode generates null rows beyond data**: `_generate_intable_mode_rows()` lines 208-213 create null-filled rows when `nb_rows > len(intable_data)`. Talend behavior varies by version but generally does not pad with null rows. |
| ENG-FFI-009 | **P3** | **Excessive DEBUG logging in inline content mode**: Lines 223-226, 239, 242, 246, 250, 261 log raw content, parsed rows, and field values at INFO and DEBUG levels. For large inline content blocks, this generates excessive log output. Content may contain sensitive data. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Bug** | `_update_stats(0, ...)` -> always 0 | **BUG**: First arg to `_update_stats()` is 0 instead of `rows_generated`. See ENG-FFI-001. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | `_update_stats(_, rows_generated, _)` | Correct via second argument |
| `{id}_NB_LINE_REJECT` | Yes (always 0) | **Yes** | `_update_stats(_, _, 0)` | Always 0 -- correct for this component |
| `{id}_ERROR_MESSAGE` | Yes (on error) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific stat |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FFI-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. Line 304 IS inside the for loop (same indentation as line 302), so `stat_name` IS valid -- only `value` is wrong. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FixedFlowInputComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-FFI-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`, including `_resolve_value()` on line 313 of `fixed_flow_input.py`. |
| BUG-FFI-003 | **P1** | `src/v1/engine/components/file/fixed_flow_input.py:142` | **`_update_stats()` passes 0 for NB_LINE**: `self._update_stats(0, rows_generated, 0)` sets `NB_LINE` to 0 while `NB_LINE_OK` is correctly set to `rows_generated`. This means `{id}_NB_LINE` in globalMap is always 0. Downstream components checking `(Integer)globalMap.get("tFixedFlowInput_1_NB_LINE")` get 0 regardless of how many rows were generated. Should be `self._update_stats(rows_generated, rows_generated, 0)`. |
| BUG-FFI-004 | **P1** | `src/v1/engine/components/file/fixed_flow_input.py:61-101` | **`_validate_config()` is never called**: The method exists and contains validation logic (mode checking, nb_rows validation, schema validation, mode-specific requirements), but it is never invoked by `_process()`, `__init__()`, or `execute()`. Many other components in the codebase DO call `_validate_config()` at the start of `_process()` (e.g., `FileInputFullRowComponent`, `SleepComponent`, `SendMailComponent`). All validation is dead code. Invalid configurations (negative `nb_rows`, empty schema, missing `values_config`) are not caught until they cause runtime errors. |
| BUG-FFI-005 | **P1** | `src/v1/engine/components/file/fixed_flow_input.py:169-178` | **Single mode with `rows` ignores `nb_rows`**: When the converter pre-generates `rows`, `_generate_single_mode_rows()` returns all rows without respecting `nb_rows`. Example: converter generates 1 row for a 3-column schema. Engine returns 1 row even if `nb_rows=10`. The `values_config` fallback path (line 184) correctly iterates `range(nb_rows)`, but this path is never reached when `rows` is populated (which is always the case when the converter runs). |
| BUG-FFI-006 | **P2** | `src/v1/engine/components/file/fixed_flow_input.py:286` | **Bare `except` clause**: Line 286 (`except:`) catches all exceptions including `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`. Should be `except Exception:` at minimum. Similarly, line 322 (`except:`) in the `eval()` fallback also uses bare except. |
| BUG-FFI-007 | **P2** | `src/v1/engine/components/file/fixed_flow_input.py:282-285` | **Numeric type coercion may lose precision**: After resolving a value, `_resolve_value()` checks `resolved_value.isdigit()` (line 282) and converts to `int`, or checks for `.` and converts to `float` (line 284). This silently converts string values that look numeric. A schema column with type `id_String` containing value `"12345"` would be converted to integer `12345`, potentially causing type mismatches downstream. The function does not consult the schema to determine the target type. |
| BUG-FFI-008 | **P2** | `src/v1/engine/components/file/fixed_flow_input.py:308-310` | **`import re` inside function body**: `import re` is called on every invocation of `_resolve_value()` for any value containing `"globalMap.get"`. Should be a module-level import. While Python caches imports, this is a code smell and violates PEP 8 conventions. |
| BUG-FFI-010 | **P1** | `src/v1/engine/components/file/fixed_flow_input.py:318` | **`replace(')', '')` destroys ALL closing parentheses in expression**: The Java cast cleanup code on line 318 strips every `)` from the entire expression, not just the cast parenthesis. Expressions containing function calls (e.g., `Math.abs(x)`) or arithmetic grouping (e.g., `(a + b) * c`) become malformed after this replacement, producing incorrect values or eval() SyntaxErrors. |
| BUG-FFI-011 | **P1** | `src/v1/engine/components/file/fixed_flow_input.py:318` | **Only `((Integer)` cast type handled**: Line 318 removes the `((Integer)` Java cast prefix but does not handle `(String)`, `(Long)`, `(Float)`, `(Double)`, `(BigDecimal)`, or other Talend Java casts. These cast prefixes remain in the expression string, causing `eval()` SyntaxError or producing wrong results. All non-Integer globalMap cast patterns are broken. |
| BUG-FFI-012 | **P1** | `src/v1/engine/components/file/fixed_flow_input.py:310` | **`globalMap.get()` regex uses `re.search()` -- matches only first reference**: Line 310 uses `re.search()` which returns only the first match. Multi-reference expressions like `globalMap.get("a") + "_" + globalMap.get("b")` silently leave the second (and subsequent) `globalMap.get()` calls unresolved. Should use `re.findall()` or an iterative approach to resolve all references. |
| BUG-FFI-013 | **P1** | `src/v1/engine/base_component.py` (execute Step 2) | **`resolve_dict()` doesn't recurse into dicts inside lists**: The `rows` config key (List[Dict]) and `schema` config key (List[Dict]) bypass context resolution in `execute()` Step 2 because `resolve_dict()` does not recurse into dict elements nested within lists. Context variable references inside `rows` entries (e.g., `${context.myVar}`) survive Layer 1 resolution unchanged and must rely entirely on Layer 2/3 in `_resolve_value()`. **CROSS-CUTTING**: This affects any component whose config contains List[Dict] structures with context variable references. |
| BUG-FFI-014 | **P2** | `src/v1/engine/components/file/fixed_flow_input.py:282-285` | **Negative integers treated as floats**: `'-5'.isdigit()` returns `False` in Python, so negative integer strings fall through to the float check. `float('-5')` produces `-5.0`, causing negative integers to be coerced to float type instead of int. Downstream components expecting `int` may encounter type mismatches or precision differences. |

### 6.2 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FFI-001 | **P1** | **`eval()` call on partially user-controlled string**: `_resolve_value()` line 321 calls `eval(new_value)` after performing string replacement on globalMap references. The `new_value` variable is derived from (1) the original config value (from converter) and (2) globalMap values (which could be set by any upstream component). If a globalMap value contains crafted Python code, it will be executed. The `except:` on line 322 suppresses all errors, meaning failed injection attempts are silently ignored. **Recommendation**: Replace `eval()` with safe parsing (e.g., `ast.literal_eval()` for simple values, or a proper expression evaluator for arithmetic). |
| SEC-FFI-002 | **P3** | **Sensitive data in logs**: Lines 223-226 log raw inline content at INFO level. If inline content contains passwords, API keys, or PII, these will appear in logs. Should be DEBUG level at most, or redacted. |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FFI-001 | **P2** | **`field_separator` vs `delimiter`**: The converter stores `field_separator` (line 1567), matching the Talend parameter name `FIELDSEPARATOR`. But many other components use `delimiter` for the same concept (e.g., `tFileInputDelimited` uses `delimiter`). This inter-component inconsistency can confuse developers. |
| NAME-FFI-002 | **P3** | **`values_config` naming**: The config key `values_config` contains the raw VALUES table mapping. The `rows` key contains the pre-generated row list. Both represent the same conceptual data (VALUES). Having two keys for the same purpose is confusing. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FFI-001 | **P1** | "`_validate_config()` MUST be called at start of `_process()`" (pattern from other components) | Method exists but is never called. Dead code. 15 other components in the codebase follow this pattern correctly. |
| STD-FFI-002 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend types. |
| STD-FFI-003 | **P2** | "`validate_schema()` should be called on output DataFrame" (pattern from other components) | Engine never calls `validate_schema()` on the generated DataFrame. Types are whatever Python infers from raw values. |
| STD-FFI-004 | **P3** | "No bare `except` clauses" (Python best practices) | Two bare `except:` clauses at lines 286 and 322 catch all exceptions including system exits. |

### 6.5 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FFI-001 | **P3** | **Excessive INFO-level logging**: `_generate_inline_content_rows()` has 8 log statements at INFO level (lines 223-226, 242, 246) that output raw data content, separator values, and row counts. These should be DEBUG level for production use. The `repr()` calls on content strings (line 223-225) are useful for debugging but inappropriate for INFO level. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | **Partially incorrect**: Many DEBUG-appropriate messages logged at INFO level in `_generate_inline_content_rows()`. Other methods use levels correctly. |
| Start/complete logging | `_process()` logs start (line 124) and completion (line 139) at INFO -- correct |
| Sensitive data | **Risk**: Raw inline content logged at INFO level (line 223). May contain sensitive data. |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions from `exceptions.py`. Uses generic `Exception` re-raise (line 157). Should use `ConfigurationError` for config issues and `ComponentExecutionError` for runtime failures. |
| Exception chaining | Not applicable -- re-raises original exception via bare `raise` |
| `die_on_error` handling | Single try/except block in `_process()` (line 154-163). Correct pattern: re-raises if `die_on_error=True`, returns empty DF if `False`. |
| Bare `except` | **Two bare `except:` clauses** at lines 286 and 322 in `_resolve_value()`. These catch `SystemExit`, `KeyboardInterrupt`, etc. Should use `except Exception:` |
| Error messages | Include component ID -- correct. Could include more context (mode, nb_rows). |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct pattern |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has return type hint `Dict[str, Any]` -- correct |
| `_generate_*` methods | Return type `List[Dict]` -- correct |
| `_resolve_value()` | Return type missing -- should be `-> Any` |
| `_validate_config()` | Return type `List[str]` -- correct |
| Parameter types | `nb_rows: int`, `schema_columns: List` -- partially typed. `List` should be `List[Dict]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FFI-001 | **P2** | **`_resolve_value()` called per cell, not vectorized**: For a 1000-row by 10-column DataFrame, `_resolve_value()` is called 10,000 times. Each call potentially invokes `context_manager.resolve_string()`, regex compilation (`re.search` on line 310), and `eval()`. For large `NB_ROWS` in single mode with expression values, this becomes a significant bottleneck. Consider resolving values once and replicating the row, since single mode repeats the same values. |
| PERF-FFI-002 | **P3** | **`import re` inside `_resolve_value()`**: The `re` module is imported on every call to `_resolve_value()` that encounters a `globalMap.get` reference (line 309). While Python caches imports, the import lookup adds unnecessary overhead per call. Move to module-level import. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Data generation | All rows generated in-memory as `List[Dict]` before DataFrame creation. For very large `NB_ROWS` (millions), this could consume significant memory. |
| DataFrame creation | `pd.DataFrame(output_data)` creates the DataFrame in one shot from the list. No streaming mode for generation. |
| Single mode optimization | When `rows` are pre-parsed by converter, all rows are materialized. For `NB_ROWS=1000000` with the same values, 1M identical dicts are created. Should generate one row and use `pd.DataFrame([row] * nb_rows)` or `pd.concat([pd.DataFrame([row])] * nb_rows)`. |
| Inline content | Content string is split into rows and fields, creating intermediate lists. Memory usage is proportional to content size. Acceptable for typical use cases (inline content is usually small). |

### 7.2 Scalability Notes

| Scenario | Assessment |
|----------|------------|
| NB_ROWS = 1 (common case) | Fast, no concerns |
| NB_ROWS = 100-1000 | Fast, no concerns |
| NB_ROWS = 100,000+ | `_resolve_value()` called per cell. Single mode could be optimized to resolve once and replicate. |
| NB_ROWS = 1,000,000+ | Memory concern: 1M dicts in `output_data` list before DataFrame creation. Should use vectorized generation. |
| Large inline content | Rare edge case. Memory proportional to content size. No streaming support. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FixedFlowInputComponent` |
| V1 engine integration tests | **No** | -- | No integration tests involving `tFixedFlowInput` |
| Converter unit tests | **No** | -- | No tests for `parse_tfixedflowinput()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 330 lines of engine code and 131 lines of converter code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Single mode basic | P0 | Generate 5 rows with 3 columns (string, int, float). Verify row count, column names, and values match configuration. |
| 2 | Single mode with NB_ROWS=1 | P0 | Most common case. Single row, multiple columns. Verify exact output. |
| 3 | Single mode with NB_ROWS=0 | P0 | Should return empty DataFrame with correct column names. No error. |
| 4 | Inline content basic | P0 | Multi-row inline content with semicolon separator. Verify correct row/field splitting. |
| 5 | Empty schema | P0 | Empty schema list. Should return empty DataFrame without error. |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution. Currently `NB_LINE` is always 0 (bug). |
| 7 | Die on error = true | P0 | Inject an error (e.g., invalid config). Verify exception is raised. |
| 8 | Die on error = false | P0 | Inject an error. Verify empty DataFrame returned, no exception. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 9 | Context variable in VALUES | P1 | `${context.myVar}` in a value cell. Verify resolution via context manager. |
| 10 | GlobalMap reference in VALUES | P1 | `(Integer)globalMap.get("comp_1_NB_LINE")` in a value. Verify resolution. |
| 11 | Java expression in VALUES | P1 | `{{java}}context.prefix + "_suffix"` value. Verify Java bridge resolution. |
| 12 | Inline content with pipe separator | P1 | `FIELDSEPARATOR="|"` with `\\|` escaped. Verify correct normalization and splitting. |
| 13 | Inline content with tab separator | P1 | `FIELDSEPARATOR="\\t"`. Verify tab normalization. (Currently a gap -- only `\\|` handled.) |
| 14 | Inline content with custom row separator | P1 | `ROWSEPARATOR="||"`. Verify multi-char row splitting. |
| 15 | Schema type enforcement | P1 | Generate data with typed schema (int, date, Decimal). Verify `validate_schema()` is called and types are correct. (Currently a gap.) |
| 16 | Inline table mode | P1 | `USE_INTABLE=true` with pre-populated `intable_data`. Verify correct row generation. (Currently a gap -- converter stub.) |
| 17 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. |
| 18 | _validate_config wiring | P1 | Verify `_validate_config()` is called and errors are properly handled. (Currently dead code.) |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | Large NB_ROWS (10000+) | P2 | Verify performance and memory usage for large row counts in single mode. |
| 20 | Inline content with empty rows | P2 | Content with blank lines between data rows. Verify empty rows are filtered. |
| 21 | Values with special characters | P2 | Values containing commas, quotes, newlines, semicolons. Verify no parsing corruption. |
| 22 | NB_ROWS as context variable | P2 | `NB_ROWS=context.rowCount`. Verify converter handles non-numeric value. (Currently crashes.) |
| 23 | Concurrent instances | P2 | Multiple `FixedFlowInputComponent` instances running simultaneously. Verify no shared state issues. |
| 24 | Inline content with trailing separator | P2 | Content ending with row separator (e.g., `"row1\nrow2\n"`). Verify no extra empty row. |
| 25 | Mixed mode flags | P2 | Multiple mode flags set to true (e.g., `use_singlemode=true, use_intable=true`). Verify priority order. |
| 26 | Inline content field count mismatch | P2 | Row with fewer fields than schema columns. Verify null-fill for missing columns. |
| 27 | Inline content field count excess | P2 | Row with more fields than schema columns. Verify extra fields are silently ignored. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FFI-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Line 304 is inside the for loop so `stat_name` is valid; only `value` is wrong. Will crash ALL components when `global_map` is set. |
| BUG-FFI-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| ENG-FFI-001 | Engine | `_update_stats(0, rows_generated, 0)` sets `NB_LINE` to 0 instead of `rows_generated`. GlobalMap variable `{id}_NB_LINE` is always wrong. |
| TEST-FFI-001 | Testing | Zero unit tests for this component. All 330 lines of engine code and 131 lines of converter code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FFI-001 | Converter | INTABLE parsing is a stub (`pass` on line 1618). Any job using Inline Table mode gets empty data. |
| CONV-FFI-002 | Converter | `DIE_ON_ERROR` not extracted from Talend XML. Jobs with `DIE_ON_ERROR=false` will still fail on errors. |
| ENG-FFI-002 | Engine | `_resolve_value()` uses `eval()` on partially user-controlled string (line 321). Code injection vulnerability. |
| ENG-FFI-003 | Engine | `validate_schema()` never called on output DataFrame. Generated data has unvalidated types. |
| ENG-FFI-004 | Engine | Inline content field separator normalization only handles `\\|`. Other escapes (`\\t`, `\\;`, `\\,`) not normalized. |
| ENG-FFI-005 | Engine | `{id}_ERROR_MESSAGE` not stored in globalMap on error. Downstream error handlers get null. |
| BUG-FFI-004 | Bug | `_validate_config()` is dead code -- never called by any code path. 40 lines of unreachable validation. |
| BUG-FFI-005 | Bug | Single mode with pre-parsed `rows` ignores `nb_rows`. Converter generates 1 row per schema; engine returns 1 row even if `nb_rows=10`. |
| SEC-FFI-001 | Security | `eval()` call on partially user-controlled string in `_resolve_value()` line 321. Potential code injection. |
| STD-FFI-001 | Standards | `_validate_config()` exists but is never called. Violates pattern followed by 15+ other components. |
| TEST-FFI-002 | Testing | No integration test for this component in a multi-step job (e.g., `tFixedFlowInput -> tMap -> tLogRow`). |
| BUG-FFI-010 | Bug | `replace(')', '')` on line 318 destroys ALL closing parentheses in expression, not just the cast parenthesis. Expressions with function calls or arithmetic grouping become malformed. |
| BUG-FFI-011 | Bug | Only `((Integer)` cast type handled (line 318). `(String)`, `(Long)`, `(Float)`, `(Double)`, `(BigDecimal)` casts remain in expression, causing eval() SyntaxError. |
| BUG-FFI-012 | Bug | `globalMap.get()` regex uses `re.search()` (line 310) -- matches only first reference. Multi-reference expressions silently broken. Should use `re.findall()` or iterative approach. |
| BUG-FFI-013 | Bug (Cross-Cutting) | `resolve_dict()` doesn't recurse into dicts inside lists. `rows` (List[Dict]) and `schema` (List[Dict]) bypass context resolution in execute() Step 2. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FFI-003 | Converter | VALUES pairing assumes alternating SCHEMA_COLUMN/VALUE element order. Fragile if XML structure varies. |
| CONV-FFI-004 | Converter | `NB_ROWS` `int()` conversion crashes on context variable or expression values. No graceful fallback. |
| CONV-FFI-005 | Converter | Schema types converted to Python format (`str`) instead of Talend format (`id_String`), violating STANDARDS.md. |
| ENG-FFI-006 | Engine | Inline content unconditionally strips field values (`strip()` on line 256). Talend preserves whitespace. |
| ENG-FFI-007 | Engine | Single mode with pre-parsed `rows` returns all rows regardless of `nb_rows` parameter. |
| ENG-FFI-008 | Engine | Intable mode null-fills rows beyond data. May not match Talend behavior. |
| BUG-FFI-006 | Bug | Two bare `except:` clauses (lines 286, 322) catch `SystemExit`, `KeyboardInterrupt`, etc. |
| BUG-FFI-007 | Bug | Numeric type coercion in `_resolve_value()` silently converts string values that look numeric (e.g., `"12345"` -> `12345`). |
| BUG-FFI-008 | Bug | `import re` inside function body (`_resolve_value()` line 309). Should be module-level. |
| BUG-FFI-014 | Bug | Negative integers treated as floats. `'-5'.isdigit()` is False, falls to float check, `float('-5')` = `-5.0`. |
| NAME-FFI-001 | Naming | `field_separator` vs `delimiter` inconsistency across components. |
| STD-FFI-002 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| STD-FFI-003 | Standards | `validate_schema()` not called on output DataFrame -- violates expected pattern. |
| PERF-FFI-001 | Performance | `_resolve_value()` called per cell. Single mode with large `NB_ROWS` is O(rows * columns) function calls. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FFI-006 | Converter | Redundant inline content parsing in converter (dead code -- engine re-parses). |
| ENG-FFI-009 | Engine | Excessive INFO-level logging of raw content in `_generate_inline_content_rows()`. |
| SEC-FFI-002 | Security | Sensitive data may appear in INFO-level logs (raw inline content). |
| NAME-FFI-002 | Naming | `values_config` and `rows` config keys represent overlapping data. |
| STD-FFI-004 | Standards | Bare `except:` clauses violate Python best practices. |
| DBG-FFI-001 | Debug | 8 log statements at INFO level in `_generate_inline_content_rows()` should be DEBUG. |
| PERF-FFI-002 | Performance | `import re` inside `_resolve_value()` function body instead of module level. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 2 bugs (cross-cutting), 1 engine, 1 testing |
| P1 | 15 | 2 converter, 4 engine, 6 bugs (incl. 1 cross-cutting), 1 security, 1 standards, 1 testing |
| P2 | 14 | 3 converter, 3 engine, 4 bugs, 1 naming, 2 standards, 1 performance |
| P3 | 7 | 1 converter, 1 engine, 1 security, 1 naming, 1 standards, 1 debug, 1 performance |
| **Total** | **40** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FFI-001): Change `value` to `stat_value` on `base_component.py` line 304, or better yet remove the stale `{stat_name}: {value}` reference entirely. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FFI-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Fix `_update_stats()` NB_LINE bug** (ENG-FFI-001): Change line 142 from `self._update_stats(0, rows_generated, 0)` to `self._update_stats(rows_generated, rows_generated, 0)`. **Impact**: Fixes globalMap `{id}_NB_LINE` for this component. **Risk**: Very low.

4. **Create unit test suite** (TEST-FFI-001): Implement at minimum the 8 P0 test cases listed in Section 8.2. These cover: single mode basic, NB_ROWS=1, NB_ROWS=0, inline content basic, empty schema, statistics tracking, and die_on_error modes. Without these, no behavior is verified.

### Short-Term (Hardening)

5. **Wire up `_validate_config()`** (BUG-FFI-004, STD-FFI-001): Add a call to `_validate_config()` at the beginning of `_process()`, following the pattern used by 15+ other components:
```python
config_errors = self._validate_config()
if config_errors:
    error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
    if self.config.get('die_on_error', True):
        raise ConfigurationError(error_msg)
    logger.warning(f"[{self.id}] {error_msg}")
    return {'main': pd.DataFrame(columns=column_names)}
```

6. **Replace `eval()` with safe evaluation** (SEC-FFI-001, ENG-FFI-002): Replace `eval(new_value)` on line 321 with `ast.literal_eval(new_value)` for simple value parsing, or implement a proper arithmetic expression evaluator. `ast.literal_eval()` safely evaluates Python literals (strings, numbers, tuples, lists, dicts, booleans, None) without executing arbitrary code.

7. **Fix single mode NB_ROWS handling** (BUG-FFI-005): When `rows` is populated by the converter, replicate the row data to match `nb_rows`:
```python
if rows:
    resolved_rows = []
    for row in rows:
        resolved_row = {k: self._resolve_value(v) for k, v in row.items()}
        resolved_rows.append(resolved_row)
    # Replicate resolved rows to match nb_rows
    if len(resolved_rows) == 1 and nb_rows > 1:
        resolved_rows = resolved_rows * nb_rows
    return resolved_rows[:nb_rows]
```

8. **Implement INTABLE parsing** (CONV-FFI-001): Replace the `pass` stub on line 1618 with actual parsing of the INTABLE structure. The Talend XML structure for INTABLE uses `elementValue` groups similar to VALUES but with one group per row.

9. **Extract DIE_ON_ERROR** (CONV-FFI-002): Add to `parse_tfixedflowinput()`:
```python
component['config']['die_on_error'] = str_to_bool(get_param('DIE_ON_ERROR', 'true'))
```

10. **Add `validate_schema()` call** (ENG-FFI-003, STD-FFI-003): After DataFrame creation in `_process()`, call `validate_schema()` to enforce schema types:
```python
if output_data:
    df = pd.DataFrame(output_data)
    df = self.validate_schema(df, schema_columns)
    return {'main': df}
```

11. **Complete separator normalization** (ENG-FFI-004): Replace the ad-hoc normalization with a comprehensive approach:
```python
escape_map = {'\\n': '\n', '\\t': '\t', '\\r': '\r', '\\|': '|', '\\\\': '\\'}
for escaped, actual in escape_map.items():
    if row_separator == escaped:
        row_separator = actual
    if field_separator == escaped:
        field_separator = actual
```

12. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FFI-005): In the error handler (line 154-163):
```python
except Exception as e:
    logger.error(f"[{self.id}] Processing failed: {str(e)}")
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    if self.config.get('die_on_error', True):
        raise
```

### Long-Term (Optimization)

13. **Optimize single mode for large NB_ROWS** (PERF-FFI-001): Resolve values once, then replicate the row using pandas vectorized operations instead of calling `_resolve_value()` per cell per row.

14. **Fix bare `except` clauses** (BUG-FFI-006, STD-FFI-004): Replace `except:` with `except Exception:` on lines 286 and 322.

15. **Remove unconditional `strip()` on inline content fields** (ENG-FFI-006): Remove `field_values[col_idx].strip()` on line 256 or make it conditional on a trim setting.

16. **Move `import re` to module level** (BUG-FFI-008, PERF-FFI-002): Add `import re` at the top of `fixed_flow_input.py` alongside the other imports.

17. **Reduce logging verbosity** (ENG-FFI-009, DBG-FFI-001): Change INFO-level log statements in `_generate_inline_content_rows()` to DEBUG level. Remove `repr()` calls on content strings at INFO level.

18. **Handle NB_ROWS expressions** (CONV-FFI-004): Replace `int(get_param('NB_ROWS', '1'))` with safe conversion:
```python
nb_rows_raw = get_param('NB_ROWS', '1')
try:
    component['config']['nb_rows'] = int(nb_rows_raw)
except (ValueError, TypeError):
    component['config']['nb_rows'] = nb_rows_raw  # Pass through for runtime resolution
```

19. **Remove redundant converter inline parsing** (CONV-FFI-006): Remove lines 1632-1649 in the converter that pre-parse inline content, since the engine re-parses it anyway.

20. **Create integration test** (TEST-FFI-002): Build an end-to-end test exercising `tFixedFlowInput -> tMap -> tLogRow` in the v1 engine, verifying context resolution, Java bridge integration, and globalMap propagation.

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 1532-1663
def parse_tfixedflowinput(self, node, component: Dict) -> Dict:
    """Parse tFixedFlowInput specific configuration to match Talend behavior"""

    # Helper function to get parameter value
    def get_param(name, default=None):
        elem = node.find(f".//elementParameter[@name='{name}']")
        if elem is not None:
            value = elem.get('value', default)
            # Clean quotes if present
            if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            return value
        return default

    # Helper function to convert string boolean
    def str_to_bool(value, default=False):
        if isinstance(value, str):
            return value.lower() == 'true'
        return default if value is None else bool(value)

    # Parse basic configuration
    component['config']['nb_rows'] = int(get_param('NB_ROWS', '1'))  # BUG: crashes on expressions
    component['config']['connection_format'] = get_param('CONNECTION_FORMAT', 'row')

    # Parse mode selection
    use_singlemode = str_to_bool(get_param('USE_SINGLEMODE', 'true'))
    use_intable = str_to_bool(get_param('USE_INTABLE', 'false'))
    use_inlinecontent = str_to_bool(get_param('USE_INLINECONTENT', 'false'))

    component['config']['use_singlemode'] = use_singlemode
    component['config']['use_intable'] = use_intable
    component['config']['use_inlinecontent'] = use_inlinecontent

    # Parse inline content parameters (even if not used, for completeness)
    component['config']['row_separator'] = get_param('ROWSEPARATOR', '\n')
    component['config']['field_separator'] = get_param('FIELDSEPARATOR', ';')
    component['config']['inline_content'] = get_param('INLINECONTENT', '')

    # ... schema extraction, VALUES parsing, INTABLE stub, row generation ...
```

**Notes on this code**:
- Line 1553: `int(get_param('NB_ROWS', '1'))` will throw `ValueError` if `NB_ROWS` is a context variable or expression.
- Lines 1590-1609: VALUES parsing assumes alternating SCHEMA_COLUMN/VALUE pairs. The `elementRef` attribute check provides some validation.
- Lines 1614-1618: INTABLE parsing is a complete stub (`pass`).
- Lines 1603-1604: Context variable wrapping (`context.var` -> `${context.var}`) is correct.
- Lines 1620-1660: Pre-generates `rows` list from mode configuration. This duplicates work that the engine also does.

---

## Appendix B: Engine Class Structure

```
FixedFlowInputComponent (BaseComponent)
    Constants:
        (none -- uses config defaults inline)

    Methods:
        _validate_config() -> List[str]                    # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]             # Main entry point
        _generate_single_mode_rows(nb_rows, schema) -> List[Dict]    # Single mode generation
        _generate_intable_mode_rows(nb_rows, schema) -> List[Dict]   # Inline table mode
        _generate_inline_content_rows(nb_rows, schema) -> List[Dict] # Inline content mode
        _resolve_value(value) -> Any                       # Expression/variable resolution (USES eval())

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]              # Lifecycle: resolve -> process -> stats
        _update_stats(read, ok, reject) -> None            # Accumulate statistics
        _update_global_map() -> None                       # Push stats to globalMap (BUGGY)
        validate_schema(df, schema) -> pd.DataFrame        # Type enforcement (NOT CALLED)
        _resolve_java_expressions() -> None                # {{java}} marker resolution
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `NB_ROWS` | `nb_rows` | Mapped | -- |
| `CONNECTION_FORMAT` | `connection_format` | Mapped | -- |
| `USE_SINGLEMODE` | `use_singlemode` | Mapped | -- |
| `USE_INTABLE` | `use_intable` | Mapped | -- |
| `USE_INLINECONTENT` | `use_inlinecontent` | Mapped | -- |
| `ROWSEPARATOR` | `row_separator` | Mapped | -- |
| `FIELDSEPARATOR` | `field_separator` | Mapped | -- |
| `INLINECONTENT` | `inline_content` | Mapped | -- |
| `VALUES` | `values_config` + `rows` | Mapped | -- |
| `INTABLE` | `intable_data` | **Stub** | P1 |
| `SCHEMA` | `schema` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Type Handling Analysis

### How Types Flow Through the System

1. **Talend XML**: Schema columns have types like `id_String`, `id_Integer`, `id_Date`
2. **Converter**: `ExpressionConverter.convert_type()` converts to Python names: `str`, `int`, `datetime`
3. **Engine config**: Schema stored with Python type names
4. **Engine _process()**: Values resolved as strings (from VALUES or inline content)
5. **DataFrame creation**: `pd.DataFrame(output_data)` -- pandas infers types from Python objects
6. **validate_schema()**: **NEVER CALLED** -- types remain as pandas inferred

### Type Fidelity Gaps

| Talend Type | Expected DataFrame Dtype | Actual DataFrame Dtype | Issue |
|-------------|-------------------------|----------------------|-------|
| `id_String` | `object` | `object` | Correct (strings stay strings) |
| `id_Integer` | `int64` | `object` or `int64` | **Depends on input**: String values from inline content stay as `object`; numeric literals from VALUES may be `int64` after `_resolve_value()` coercion |
| `id_Long` | `int64` | Same as Integer | Same issue |
| `id_Float` | `float64` | `object` or `float64` | Same pattern as Integer |
| `id_Double` | `float64` | Same as Float | Same issue |
| `id_Boolean` | `bool` | `object` | String values `"true"`/`"false"` remain strings |
| `id_Date` | `datetime64[ns]` | `object` | Date strings not parsed to datetime |
| `id_BigDecimal` | `object` (Decimal) | `object` (str) | String values not converted to `Decimal` |

**Key insight**: Without `validate_schema()`, the generated DataFrame has unreliable types. Downstream components that expect typed data (e.g., `tMap` with numeric comparisons, `tDBOutput` with type-specific SQL) may fail or produce incorrect results.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 61-101)

This method validates:
- At least one mode flag is enabled (`use_singlemode`, `use_intable`, `use_inlinecontent`)
- `nb_rows` is a non-negative integer
- `schema` is a non-empty list
- Single mode: either `values_config` or `rows` is provided
- Inline content mode: `inline_content` is provided

**Not validated**: `row_separator`, `field_separator`, `intable_data`, individual VALUES entries.

**Critical**: This method is never called. Even if it were, its return value (list of error strings) is not checked by any caller. The recommended pattern (used by other components) is to call `_validate_config()` at the start of `_process()` and raise `ConfigurationError` if the list is non-empty.

### `_process()` (Lines 103-163)

The main processing method:
1. Extract `nb_rows`, `schema_columns`, and mode flags from config
2. Log processing start with mode information
3. Dispatch to mode-specific generation method
4. Update statistics (NB_LINE=0, NB_LINE_OK=rows_generated, NB_LINE_REJECT=0) -- **BUG: NB_LINE should equal rows_generated**
5. Convert output_data list to DataFrame
6. Return `{'main': df}`
7. On error: re-raise (die_on_error=true) or return empty DataFrame (die_on_error=false)

**Missing steps**: No `_validate_config()` call. No `validate_schema()` call on output.

### `_generate_single_mode_rows()` (Lines 165-193)

Two paths:
1. **Primary** (lines 169-178): Use pre-parsed `rows` from converter. Iterate each row, resolve each value. Return all rows. **Does not check `nb_rows`.**
2. **Fallback** (lines 181-193): Use `values_config` dict. Generate `nb_rows` rows by iterating schema columns and looking up values. **Correctly respects `nb_rows`.** But this path is never reached when converter populates `rows`.

### `_generate_intable_mode_rows()` (Lines 195-215)

Uses `intable_data` from config (always empty due to converter stub). Iterates `range(nb_rows)`. For indices beyond `intable_data` length, creates null-filled rows. With empty `intable_data`, ALL rows are null-filled.

### `_generate_inline_content_rows()` (Lines 217-266)

1. Extract `inline_content`, `row_separator`, `field_separator` from config
2. Normalize escape sequences (`\\n` -> `\n`, `\\|` -> `|`)
3. Split content by row separator
4. Filter empty rows via `row.strip()`
5. **Ignore `nb_rows`** -- process all content rows (line 244-246, with explanatory comment)
6. Split each row by field separator
7. Map fields to schema columns (null-fill if fewer fields than columns)
8. Resolve each value via `_resolve_value()`

**Note**: Line 226 explicitly logs that `nb_rows` is ignored in inline content mode. This matches Talend behavior.

### `_resolve_value()` (Lines 268-330)

Complex multi-strategy value resolution:
1. Non-string values returned as-is (line 270-271)
2. Try `context_manager.resolve_string()` (line 276)
3. If resolved value differs: attempt numeric type coercion (lines 281-287) -- **BUG: bare except, silent type coercion**
4. Fallback: `${context.var}` pattern (lines 292-298)
5. Fallback: `context.var` pattern (lines 301-305)
6. Fallback: `globalMap.get()` regex extraction (lines 308-323) -- **SECURITY RISK: uses eval()**
7. Return original value if nothing matched (line 326)
8. On any exception: log warning, return original value (lines 328-330)

**Key concerns**:
- `eval()` on line 321 is a code injection vector
- Bare `except:` on lines 286 and 322 suppresses critical exceptions
- Numeric coercion on lines 282-285 is schema-unaware
- `import re` on line 309 is inside the function body

---

## Appendix F: Edge Case Analysis

### Edge Case 1: NB_ROWS = 0

| Aspect | Detail |
|--------|--------|
| **Talend** | Generates 0 rows. Empty flow. NB_LINE=0. |
| **V1 (single mode)** | `range(0)` in fallback path produces empty list. Primary `rows` path returns converter-generated rows (typically 0 if nb_rows was 0 at conversion). `output_data` is empty. Returns empty DataFrame with schema columns. |
| **Verdict** | CORRECT (assuming converter correctly generates 0 rows for NB_ROWS=0) |

### Edge Case 2: NB_ROWS = 1 (most common case)

| Aspect | Detail |
|--------|--------|
| **Talend** | Generates 1 row with VALUES. |
| **V1** | Converter generates 1 row in `rows`. Engine returns it via `_generate_single_mode_rows()`. |
| **Verdict** | CORRECT |

### Edge Case 3: Empty inline content

| Aspect | Detail |
|--------|--------|
| **Talend** | No rows generated. NB_LINE=0. |
| **V1** | `inline_content` is empty string. `if inline_content:` (line 230) is False. Returns empty list. Empty DataFrame with schema columns. |
| **Verdict** | CORRECT |

### Edge Case 4: Inline content with trailing newline

| Aspect | Detail |
|--------|--------|
| **Talend** | Trailing separator produces empty last row, which is skipped. |
| **V1** | `inline_content.split('\n')` produces empty string as last element. `row.strip()` filter (line 241) removes it. |
| **Verdict** | CORRECT |

### Edge Case 5: Values containing NaN-like strings

| Aspect | Detail |
|--------|--------|
| **Talend** | String value "NA" or "NULL" remains a string literal. |
| **V1** | `pd.DataFrame(output_data)` may convert "NA", "NULL", "None" strings to NaN unless `keep_default_na=False` is set. The engine does NOT set `keep_default_na=False` when creating the DataFrame. |
| **Verdict** | **GAP** -- NaN-like string values may be silently converted to NaN by pandas. |

### Edge Case 6: Empty string values in VALUES

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty string `""` generates an empty string in the output. |
| **V1** | Converter `strip('"')` on line 1598-1599 removes quotes. Empty string `""` becomes empty string `""`. Correct. But `_resolve_value()` returns the empty string as-is (no special handling). |
| **Verdict** | CORRECT |

### Edge Case 7: Context variable in inline content

| Aspect | Detail |
|--------|--------|
| **Talend** | **Context variables are NOT supported** in inline content mode. Content is treated as literal text. |
| **V1** | `_resolve_value()` IS called on each inline content field (line 257). If content contains `${context.myVar}`, it WILL be resolved. This differs from Talend behavior. |
| **Verdict** | **BEHAVIORAL DIFFERENCE** -- V1 resolves context variables in inline content; Talend does not. This could be a feature or a bug depending on perspective. |

### Edge Case 8: Schema with date column in single mode

| Aspect | Detail |
|--------|--------|
| **Talend** | Date values in VALUES are Java date expressions (e.g., `TalendDate.parseDate("yyyy-MM-dd", "2024-01-15")`). Compiled and evaluated as Java code. |
| **V1** | Value stored as string (e.g., `"2024-01-15"`). `_resolve_value()` returns it as string. Without `validate_schema()`, it remains a string in the DataFrame. Downstream components expecting `datetime64[ns]` will fail. |
| **Verdict** | **GAP** -- Date values not converted to datetime. Would be fixed by calling `validate_schema()`. |

### Edge Case 9: Multiple rows in VALUES with different values per row

| Aspect | Detail |
|--------|--------|
| **Talend** | Single mode VALUES defines ONE row template, repeated NB_ROWS times with the same values (unless expressions produce different results per evaluation). For multiple distinct rows, use Inline Table mode. |
| **V1** | Converter generates NB_ROWS rows in the `rows` list, all with the same VALUES (line 1622-1630). Correct for literal values. For Talend expressions that produce different results per row (e.g., `Numeric.sequence()`), all rows get the same converter-time evaluation result, losing per-row variation. |
| **Verdict** | **PARTIAL** -- Correct for literal values. Loses per-row expression variation (e.g., sequences, random values). |

### Edge Case 10: Inline content with more fields than schema columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Extra fields silently ignored. |
| **V1** | `col_idx < len(field_values)` check (line 255) only iterates schema columns. Extra fields are silently ignored. |
| **Verdict** | CORRECT |

### Edge Case 11: Inline content with fewer fields than schema columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Missing fields default to null. |
| **V1** | `else: row[col_name] = None` (lines 258-259) fills missing fields with None. |
| **Verdict** | CORRECT |

### Edge Case 12: Component status after execution

| Aspect | Detail |
|--------|--------|
| **Talend** | Component status reflects success/failure. |
| **V1** | `BaseComponent.execute()` sets `self.status = ComponentStatus.SUCCESS` (line 220) or `ComponentStatus.ERROR` (line 228). Correct lifecycle management. |
| **Verdict** | CORRECT |

### Edge Case 13: GlobalMap.get() call in _resolve_value() with bug

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.get("key")` returns the stored value. |
| **V1** | `_resolve_value()` line 313 calls `self.global_map.get(global_key, None)`. But `GlobalMap.get()` does NOT accept a `default` parameter (BUG-FFI-002). This will raise `TypeError: get() takes 2 positional arguments but 3 were given`. |
| **Verdict** | **BUG** -- Will crash at runtime when resolving globalMap references. Two bugs compound: the `get()` method references undefined `default`, AND the caller passes two arguments. |

### Edge Case 14: Empty DataFrame creation with mixed schema types

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty result still has typed columns. |
| **V1** | `pd.DataFrame(columns=column_names)` (line 151) creates DataFrame with `object` dtype for all columns. No type enforcement on empty DataFrame. |
| **Verdict** | **PARTIAL** -- Column names correct but types are all `object`. |

### Edge Case 15: Inline content mode and NB_ROWS interaction

| Aspect | Detail |
|--------|--------|
| **Talend** | NB_ROWS is ignored in inline content mode. All content rows are processed. |
| **V1** | Line 244-246: `nb_rows` is explicitly logged as ignored. All content rows are processed via `for i, current_row in enumerate(content_rows)`. |
| **Verdict** | CORRECT |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FixedFlowInputComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FFI-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable (should be `stat_value`). Line 304 is inside the for loop so `stat_name` is valid; only `value` is wrong. Will crash ALL components when `global_map` is set. |
| BUG-FFI-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. `get_component_stat()` also passes wrong number of args. |
| BUG-FFI-004 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called by `FixedFlowInputComponent`. Some other components DO call it (pattern inconsistency across codebase). |
| BUG-FFI-013 | **P1** | `base_component.py` (execute Step 2) | `resolve_dict()` doesn't recurse into dicts inside lists. `rows` (List[Dict]) and `schema` (List[Dict]) bypass context resolution. Affects any component with List[Dict] config structures containing context variable references. |
| STD-FFI-002 | **P2** | `expression_converter.py` | `convert_type()` converts Talend types to Python names instead of preserving original format. Affects all components using the converter. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FFI-001 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). Line 304 is inside the for loop (same indentation as line 302), so `stat_name` is valid. Only the `{value}` reference is wrong. Best fix is to replace `{value}` with `{stat_value}`, or simplify the log message by removing the per-iteration detail.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-FFI-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: ENG-FFI-001 -- `_update_stats()` NB_LINE always 0

**File**: `src/v1/engine/components/file/fixed_flow_input.py`
**Line**: 142

**Current**:
```python
self._update_stats(0, rows_generated, 0)
```

**Fix**:
```python
self._update_stats(rows_generated, rows_generated, 0)
```

**Explanation**: The first argument maps to `NB_LINE` (total rows processed). Passing 0 means the globalMap variable `{id}_NB_LINE` is always 0, even when rows are generated. `NB_LINE_OK` (second argument) is correctly set to `rows_generated`.

**Impact**: Fixes globalMap `{id}_NB_LINE` for this component. **Risk**: Very low.

---

### Fix Guide: BUG-FFI-005 -- Single mode ignores NB_ROWS

**File**: `src/v1/engine/components/file/fixed_flow_input.py`
**Lines**: 165-178

**Current**:
```python
def _generate_single_mode_rows(self, nb_rows: int, schema_columns: List) -> List[Dict]:
    rows = self.config.get('rows', [])
    if rows:
        resolved_rows = []
        for row in rows:
            resolved_row = {}
            for key, value in row.items():
                resolved_row[key] = self._resolve_value(value)
            resolved_rows.append(resolved_row)
        return resolved_rows
```

**Fix**:
```python
def _generate_single_mode_rows(self, nb_rows: int, schema_columns: List) -> List[Dict]:
    rows = self.config.get('rows', [])
    if rows:
        # Resolve expressions in template rows
        resolved_rows = []
        for row in rows:
            resolved_row = {}
            for key, value in row.items():
                resolved_row[key] = self._resolve_value(value)
            resolved_rows.append(resolved_row)
        # Replicate to match nb_rows (single mode repeats the same values)
        if len(resolved_rows) == 1 and nb_rows > 1:
            resolved_rows = resolved_rows * nb_rows
        elif nb_rows < len(resolved_rows):
            resolved_rows = resolved_rows[:nb_rows]
        return resolved_rows
```

**Explanation**: The converter generates one row per schema column mapping from VALUES. In Talend, single mode repeats this template `NB_ROWS` times. The fix replicates the resolved row to match the requested count.

**Impact**: Fixes row count for single mode. **Risk**: Low.

---

### Fix Guide: SEC-FFI-001 -- Replace eval() with safe evaluation

**File**: `src/v1/engine/components/file/fixed_flow_input.py`
**Line**: 321

**Current (dangerous)**:
```python
try:
    return eval(new_value)
except:
    return new_value
```

**Fix**:
```python
import ast
try:
    return ast.literal_eval(new_value)
except (ValueError, SyntaxError):
    # If it's a simple numeric expression, try safe evaluation
    try:
        # Only allow basic arithmetic on numbers
        if all(c in '0123456789.+-*/ ()' for c in new_value):
            return ast.literal_eval(str(eval(compile(new_value, '<string>', 'eval'))))
        return new_value
    except Exception:
        return new_value
```

**Or simpler (recommended)**:
```python
try:
    return ast.literal_eval(new_value)
except (ValueError, SyntaxError):
    return new_value
```

**Explanation**: `eval()` can execute arbitrary Python code. `ast.literal_eval()` only evaluates Python literals (strings, numbers, tuples, lists, dicts, booleans, None) -- no function calls, imports, or code execution.

**Impact**: Eliminates code injection vector. **Risk**: Low. May fail to evaluate some complex arithmetic expressions that `eval()` handled, but those should go through the Java bridge instead.

---

### Fix Guide: STD-FFI-001 -- Wire up _validate_config()

**File**: `src/v1/engine/components/file/fixed_flow_input.py`
**Location**: Start of `_process()` method (after line 114)

**Add**:
```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    try:
        # Validate configuration first
        config_errors = self._validate_config()
        if config_errors:
            error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
            logger.error(f"[{self.id}] {error_msg}")
            if self.config.get('die_on_error', True):
                from ...exceptions import ConfigurationError
                raise ConfigurationError(error_msg)
            logger.warning(f"[{self.id}] Returning empty DataFrame due to config errors")
            column_names = [col['name'] if isinstance(col, dict) else col
                          for col in self.config.get('schema', [])]
            return {'main': pd.DataFrame(columns=column_names)}

        # Extract configuration (existing code continues...)
        nb_rows = int(self.config.get('nb_rows', 1))
```

**Impact**: Activates 40 lines of existing validation code. **Risk**: Low (validation is conservative and returns error messages rather than modifying data).

---

## Appendix I: _resolve_value() Flow Diagram

```
_resolve_value(value)
    |
    +--> Not a string? --> Return as-is
    |
    +--> Try context_manager.resolve_string(value)
    |       |
    |       +--> Resolved differs from input?
    |               |
    |               +--> Yes: Try numeric coercion (isdigit/float check)
    |               |         Return resolved value (possibly coerced)
    |               |
    |               +--> No: Fall through to legacy resolution
    |
    +--> Starts with '${' and ends with '}'?
    |       |
    |       +--> Contains 'context.'? --> context_manager.get(key) --> Return
    |
    +--> Starts with 'context.'?
    |       |
    |       +--> context_manager.get(key) --> Return
    |
    +--> Contains 'globalMap.get'?
    |       |
    |       +--> Regex extract key --> global_map.get(key) [BUGGY]
    |       |       |
    |       |       +--> Replace globalMap ref with value
    |       |       +--> Clean up Java casting
    |       |       +--> eval(new_value) [SECURITY RISK]
    |       |       +--> Return result
    |
    +--> Return original value (no match)
    |
    +--> On ANY exception: log warning, return original value
```

---

## Appendix J: Comparison with Other Input Components

| Feature | tFixedFlowInput | tFileInputDelimited | tRowGenerator |
|---------|----------------|--------------------|--------------|
| Data Source | Configuration (VALUES/inline) | External file | Expression-generated |
| REJECT Flow | No | Yes (not implemented in v1) | No |
| NB_ROWS | Controls row count (single/intable) | Controls row limit from file | Controls row count |
| Schema Validation | **Not called** | Called via `validate_schema()` | Not audited |
| `_validate_config()` | **Dead code** | **Dead code** | Not audited |
| Dedicated Converter | Yes (`parse_tfixedflowinput`) | No (uses deprecated `_map_component_parameters`) | Yes (`parse_row_generator`) |
| Expression Resolution | `_resolve_value()` with eval() | N/A (values from file) | Expression-based |
| GlobalMap NB_LINE | **Bug: always 0** | Set correctly | Not audited |
| Testing | **Zero tests** | **Zero tests** | Not audited |

---

## Appendix K: Detailed _resolve_value() Security Analysis

### eval() Attack Surface

The `eval()` call on line 321 of `fixed_flow_input.py` is reached through the following path:

1. A config value contains `globalMap.get("some_key")` (from VALUES table or inline content)
2. The regex on line 310 extracts the key: `some_key`
3. `self.global_map.get(global_key, None)` retrieves the stored value (if BUG-FFI-002 is fixed)
4. The globalMap reference is replaced with the resolved value: `value.replace(f'globalMap.get("{global_key}")', str(resolved_value))`
5. Java-style casting is cleaned up: `.replace("((Integer)", "").replace(")", "")`
6. The resulting string is passed to `eval()`

### Attack Scenarios

| Scenario | Risk Level | Exploitation Path |
|----------|-----------|-------------------|
| Trusted converter output | Very Low | Config values come from Talend XML via the converter. Attacker would need to modify the Talend job XML or the converted JSON. |
| GlobalMap value injection | Medium | An upstream component sets a globalMap value to a malicious Python expression. When this component resolves `globalMap.get("key")`, the malicious value is injected into the `eval()` string. Example: upstream sets `globalMap.put("key", "__import__('os').system('id')")`. |
| Multi-tenant environments | High | If the v1 engine processes jobs from multiple untrusted tenants sharing a globalMap, cross-tenant code injection is possible. |

### Recommended Mitigations

1. **Immediate**: Replace `eval()` with `ast.literal_eval()` (handles numbers, strings, basic literals)
2. **Short-term**: Implement a simple arithmetic expression parser (handles `+`, `-`, `*`, `/` on numbers)
3. **Long-term**: Route all expression evaluation through the Java bridge (consistent with Talend behavior)

### Bare except Clause Analysis

The two bare `except:` clauses compound the security issue:

**Line 286** (numeric coercion):
```python
try:
    if resolved_value.isdigit():
        return int(resolved_value)
    elif '.' in resolved_value and resolved_value.replace('.', '').replace('-', '').isdigit():
        return float(resolved_value)
except:
    pass
```
This catches ALL exceptions including `OverflowError`, `MemoryError`, `SystemExit`. Should be `except (ValueError, OverflowError):`.

**Line 322** (eval fallback):
```python
try:
    return eval(new_value)
except:
    return new_value
```
This catches ALL exceptions from `eval()`, including `SyntaxError`, `NameError`, `TypeError`, and importantly `SystemExit` and `KeyboardInterrupt`. A crafted expression like `exit()` or `raise SystemExit` would be caught and silently suppressed instead of terminating the process.

---

## Appendix L: Converter-Engine Data Flow

### Single Mode Data Flow

```
Talend XML
    |
    v
parse_tfixedflowinput()
    |
    +-- get_param('NB_ROWS') --> int() --> config['nb_rows'] = N
    +-- get_param('USE_SINGLEMODE') --> str_to_bool() --> config['use_singlemode'] = True
    +-- Parse VALUES table:
    |       elementValue[0]: elementRef=SCHEMA_COLUMN, value="col1"
    |       elementValue[1]: elementRef=VALUE, value="context.myVar"
    |       --> values_config = {"col1": "${context.myVar}"}
    +-- Generate rows:
    |       for row_idx in range(N):
    |           row = {"col1": "${context.myVar}"}
    |           rows.append(row)
    +-- config['rows'] = [{"col1": "${context.myVar}"}, ...]  (N copies)
    +-- config['values_config'] = {"col1": "${context.myVar}"}
    |
    v
Engine: FixedFlowInputComponent.execute()
    |
    +-- BaseComponent.execute():
    |       Step 1: _resolve_java_expressions() [if java_bridge]
    |       Step 2: context_manager.resolve_dict(config) [if context_manager]
    |       Step 3: _execute_batch() --> _process()
    |
    +-- _process():
    |       nb_rows = config['nb_rows']  (already resolved by context_manager)
    |       use_singlemode = True
    |       --> _generate_single_mode_rows(nb_rows, schema)
    |
    +-- _generate_single_mode_rows():
    |       rows = config['rows']  (N pre-parsed rows, context vars may be resolved)
    |       for each row:
    |           for each key, value:
    |               resolved = _resolve_value(value)
    |       return resolved_rows  (IGNORES nb_rows -- uses len(rows) instead)
    |
    +-- _process() continued:
    |       rows_generated = len(output_data)
    |       _update_stats(0, rows_generated, 0)  <-- BUG: NB_LINE = 0
    |       df = pd.DataFrame(output_data)
    |       return {'main': df}  <-- NO validate_schema() call
    |
    v
BaseComponent.execute() continued:
    stats['EXECUTION_TIME'] = ...
    _update_global_map()  <-- CRASHES due to BUG-FFI-001 (undefined 'value')
    status = SUCCESS
    return result with stats
```

### Inline Content Data Flow

```
Talend XML
    |
    v
parse_tfixedflowinput()
    |
    +-- get_param('NB_ROWS') --> config['nb_rows'] = N
    +-- get_param('USE_INLINECONTENT') --> config['use_inlinecontent'] = True
    +-- get_param('INLINECONTENT') --> config['inline_content'] = "John;30\nJane;25"
    +-- get_param('ROWSEPARATOR') --> config['row_separator'] = "\n"
    +-- get_param('FIELDSEPARATOR') --> config['field_separator'] = ";"
    +-- Converter also pre-parses rows (lines 1632-1649) --> config['rows'] = [...]
    |   (but engine ignores these for inline content mode)
    |
    v
Engine: _generate_inline_content_rows()
    |
    +-- inline_content = "John;30\nJane;25"
    +-- Normalize separators: \\n -> \n, \\| -> |
    +-- Split by row_separator: ["John;30", "Jane;25"]
    +-- Filter empty: ["John;30", "Jane;25"] (no change)
    +-- IGNORE nb_rows (process ALL content rows)
    +-- For each row:
    |       Split by field_separator: ["John", "30"] / ["Jane", "25"]
    |       Map to schema columns: {"name": "John", "age": "30"}
    |       strip() each value  <-- BEHAVIORAL DIFFERENCE from Talend
    |       _resolve_value() each value  <-- Resolves vars; Talend does NOT
    +-- Return list of dicts
    |
    v
Same _process() flow as above (DataFrame creation, stats, return)
```

### Inline Table Data Flow (Currently Broken)

```
Talend XML
    |
    v
parse_tfixedflowinput()
    |
    +-- get_param('USE_INTABLE') --> config['use_intable'] = True
    +-- INTABLE parsing: pass  <-- STUB (CONV-FFI-001)
    +-- intable_data = []  (always empty)
    +-- rows generated from intable_data: all null-filled
    |
    v
Engine: _generate_intable_mode_rows()
    |
    +-- intable_data = [] (empty from converter)
    +-- for i in range(nb_rows):
    |       i >= 0 >= len([]) --> create null row
    +-- Return nb_rows null-filled rows
    |
    v
DataFrame with all-null values (INCORRECT)
```

---

## Appendix M: Context Variable Resolution Layers

The `FixedFlowInputComponent` has **three layers** of context variable resolution, which creates complexity and potential double-resolution issues:

### Layer 1: BaseComponent.execute() (line 202)

```python
if self.context_manager:
    self.config = self.context_manager.resolve_dict(self.config)
```

This resolves `${context.var}` patterns in ALL config values (strings, nested dicts, lists) BEFORE `_process()` is called. This means that by the time `_process()` runs, most context variables in config should already be resolved.

### Layer 2: _resolve_value() via context_manager.resolve_string() (line 276)

```python
resolved_value = self.context_manager.resolve_string(value)
```

This is called per-value during row generation. It handles:
- `${context.var}` patterns
- Expression concatenation: `${context.dir} + "/file.csv"`
- `{{java}}` marker detection (returns as-is for Java bridge)

### Layer 3: _resolve_value() legacy fallback (lines 292-323)

If `resolve_string()` returns the original value unchanged, fallback patterns are tried:
- `${context.var}` (lines 292-298)
- `context.var` without `${}` wrapper (lines 301-305)
- `globalMap.get("key")` (lines 308-323)

### Double Resolution Risk

Consider a value like `${context.output_dir}`:

1. **Layer 1** (`resolve_dict`): Resolves to `/data/output` in the config
2. `_process()` reads config: value is already `/data/output`
3. **Layer 2** (`resolve_string`): Called on `/data/output` -- no change (not a context variable)
4. No double resolution issue in this case

But consider a config value that is a nested reference: `${context.path_template}` where `context.path_template = "${context.base}/subfolder"`:

1. **Layer 1**: Resolves outer reference to `${context.base}/subfolder` (if resolve_dict handles one level)
2. **Layer 2**: May resolve inner `${context.base}` to produce `/root/subfolder`
3. Or Layer 1 may recursively resolve both levels at once

The behavior depends on whether `context_manager.resolve_dict()` does recursive resolution. If it does, Layer 2 and 3 are redundant for context variables. If it does not, the multiple layers provide defense-in-depth.

### GlobalMap Resolution

GlobalMap references (`globalMap.get("key")`) are NOT handled by Layer 1 (`resolve_dict`) or Layer 2 (`resolve_string`). They are ONLY handled by Layer 3 (legacy fallback in `_resolve_value()`), which uses regex and `eval()`. This is the only path for globalMap resolution, making the `eval()` security risk unavoidable without refactoring.

---

## Appendix N: Mode Priority and Fallback Behavior

### Mode Selection Priority in _process()

```python
if use_singlemode:
    output_data = self._generate_single_mode_rows(nb_rows, schema_columns)
elif use_intable:
    output_data = self._generate_intable_mode_rows(nb_rows, schema_columns)
elif use_inlinecontent:
    output_data = self._generate_inline_content_rows(nb_rows, schema_columns)
else:
    output_data = self._generate_single_mode_rows(nb_rows, schema_columns)
```

**Priority order**: Single > Intable > Inline Content > Single (fallback)

### Edge Cases in Mode Selection

| Scenario | use_singlemode | use_intable | use_inlinecontent | Result |
|----------|---------------|------------|-------------------|--------|
| Default (no flags set) | True (default) | False (default) | False (default) | Single mode |
| Explicit single | True | False | False | Single mode |
| Explicit intable | False | True | False | Intable mode |
| Explicit inline content | False | False | True | Inline content mode |
| All false | False | False | False | **Fallback to single** (with warning log) |
| Multiple true (single+intable) | True | True | False | **Single mode** (priority wins) |
| Multiple true (intable+inline) | False | True | True | **Intable mode** (priority wins) |
| All true | True | True | True | **Single mode** (priority wins) |

**Note**: In Talend, these are radio buttons -- only one can be true at a time. The converter correctly extracts them as mutually exclusive booleans. However, if config is manually crafted with multiple modes true, the priority order above applies. The `_validate_config()` method (dead code) does NOT validate mutual exclusivity.

### Talend Mode Terminology Mapping

| Talend UI Label | Talend XML Parameter | V1 Config Key | V1 Engine Method |
|-----------------|---------------------|---------------|------------------|
| "Use Single Table" | `USE_SINGLEMODE` | `use_singlemode` | `_generate_single_mode_rows()` |
| "Use Inline Table" | `USE_INTABLE` | `use_intable` | `_generate_intable_mode_rows()` |
| "Use Inline Content (delimited file)" | `USE_INLINECONTENT` | `use_inlinecontent` | `_generate_inline_content_rows()` |

---

## Appendix O: Runtime Error Scenarios

### Scenario 1: globalMap.get() reference (Compound Bug)

**Config**: `VALUES = {col1: '((Integer)globalMap.get("tFileList_1_CURRENT_INDEX"))'}`
**Runtime path**:
1. `_resolve_value()` called with `'((Integer)globalMap.get("tFileList_1_CURRENT_INDEX"))'`
2. `context_manager.resolve_string()` returns unchanged (not a context variable)
3. `"globalMap.get" in value` is True (line 308)
4. Regex extracts key: `tFileList_1_CURRENT_INDEX`
5. Calls `self.global_map.get("tFileList_1_CURRENT_INDEX", None)` -- **CRASHES** with `TypeError` due to BUG-FFI-002 (extra argument)
6. Exception caught by outer `except Exception as e` (line 328)
7. Returns original unresolved string
8. **Result**: Column contains literal Java-style expression string instead of numeric value

**Impact**: Silently produces wrong data. No error raised. Downstream processing operates on string "((Integer)globalMap.get(...))" instead of the expected integer.

### Scenario 2: NB_ROWS as context variable

**Talend XML**: `<elementParameter name="NB_ROWS" value="context.rowCount"/>`
**Converter path**:
1. `get_param('NB_ROWS', '1')` returns `'context.rowCount'`
2. `int('context.rowCount')` -- **CRASHES** with `ValueError`
3. Exception propagates up, aborting conversion

**Impact**: Job conversion fails entirely. No v1 JSON produced.

### Scenario 3: Large inline content with sensitive data

**Config**: 1000-line inline content containing customer names and addresses
**Runtime path**:
1. `_generate_inline_content_rows()` logs at INFO level:
   - Line 223: `Raw inline_content: 'John Smith;123 Main St;...(1000 lines)...'`
   - Line 242: `Parsed 1000 non-empty rows from inline content: [...]`
   - Lines 250: Per-row field logging at DEBUG level
2. All customer data appears in application logs

**Impact**: PII exposure in logs. Compliance violation (GDPR, CCPA, etc.).

### Scenario 4: die_on_error=false with missing context

**Config**: `{die_on_error: false, use_singlemode: true, values_config: {col1: '${context.missing_var}'}}`
**Runtime path**:
1. `context_manager.resolve_dict()` (Layer 1) may or may not resolve `${context.missing_var}` -- depends on context_manager behavior for missing keys
2. If unresolved, `_resolve_value()` tries legacy fallback
3. `context_manager.get('missing_var')` returns None (line 296-297)
4. `resolved_value is not None` check fails
5. Returns original string `'${context.missing_var}'`
6. Column contains literal `'${context.missing_var}'` string
7. No error raised (die_on_error=false is set but no error occurred)

**Impact**: Silently produces wrong data. Column contains unresolved placeholder string.

### Scenario 5: _update_global_map() crash (BUG-FFI-001)

**Any execution path**:
1. `_process()` completes successfully
2. `_update_stats()` correctly updates `self.stats`
3. `execute()` calls `_update_global_map()` (line 218)
4. `_update_global_map()` iterates stats, calls `global_map.put_component_stat()` -- OK
5. Log statement on line 304 references `{value}` -- **NameError**
6. Exception propagates to `execute()` except block (line 227)
7. `self.status = ComponentStatus.ERROR` set
8. `_update_global_map()` called AGAIN in error handler (line 231) -- **CRASHES AGAIN**
9. Exception propagates up to caller
10. **Result**: Component reports ERROR even though data generation succeeded. Stats not saved to globalMap. Potential infinite recursion if error handler calls _update_global_map() recursively.

**Impact**: Every component execution fails after producing correct data. The error is in the stats reporting, not the data processing. This is the most critical cross-cutting bug.

---

## Appendix P: Talend tFixedFlowInput Common Patterns

### Pattern 1: Context Loading

```
tFixedFlowInput --> tContextLoad
```

tFixedFlowInput generates key-value pairs that tContextLoad uses to set context variables. Single mode with two columns: `key` and `value`. This is a common initialization pattern in Talend jobs.

**V1 compatibility**: Should work if VALUES are literal strings. May fail if VALUES contain Java expressions (e.g., `TalendDate.getCurrentDate()`).

### Pattern 2: DDL Statement Execution

```
tFixedFlowInput --> tMSSqlRow (or tOracleRow, tMysqlRow)
```

Each row contains a SQL DDL statement (CREATE TABLE, ALTER TABLE, DROP INDEX). Inline content mode with newline row separator.

**V1 compatibility**: Should work for inline content with literal SQL. May fail if SQL contains semicolons that conflict with field separator.

### Pattern 3: Iteration Driver

```
tFixedFlowInput --> tFlowToIterate --> [downstream processing]
```

tFixedFlowInput generates a list of values (e.g., file names, date ranges). tFlowToIterate converts each row to an iteration variable accessible via globalMap.

**V1 compatibility**: Depends on tFlowToIterate implementation in v1. The tFixedFlowInput part should work.

### Pattern 4: Test Data Generation

```
tFixedFlowInput --> tMap --> tFileOutputDelimited
```

Generates fixed test data rows, maps/transforms them, and writes to a file.

**V1 compatibility**: Should work for literal values. Type issues may appear in tMap if validate_schema() is not called (ENG-FFI-003).

### Pattern 5: Single Row Trigger

```
tFixedFlowInput (NB_ROWS=1) --> tJavaRow (sets globalMap) --> [downstream]
```

Generates a single row to trigger downstream processing. The row content is often irrelevant; the purpose is to start the flow.

**V1 compatibility**: Should work. NB_ROWS=1 is the simplest and most reliable case.
