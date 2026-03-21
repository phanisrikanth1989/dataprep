# Audit Report: tExtractPositionalFields / ExtractPositionalFields

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tExtractPositionalFields` |
| **V1 Engine Class** | `ExtractPositionalFields` |
| **Engine File** | `src/v1/engine/components/transform/extract_positional_fields.py` (240 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_textract_positional_fields()` (lines 2037-2058) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif` branch at line 325-326 |
| **Registry Aliases** | `ExtractPositionalFields`, `tExtractPositionalFields` (registered in `src/v1/engine/engine.py` lines 123-124) |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/extract_positional_fields.py` | Engine implementation (240 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2037-2058) | Dedicated parser: extracts PATTERN, DIE_ON_ERROR, TRIM, ADVANCED_SEPARATOR, THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR |
| `src/converters/complex_converter/converter.py` (line 325-326) | Dispatch: `elif component_type == 'tExtractPositionalFields'` calls dedicated parser |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ComponentExecutionError`, `ConfigurationError`, `DataValidationError`) |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 7: `from .extract_positional_fields import ExtractPositionalFields`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 2 | 1 | 6 of 12 runtime Talend params extracted (50%); missing FIELD, IGNORE_NULL, CUSTOMIZE, CHECK_FIELDS_NUM; schema extraction missing from dedicated parser |
| Engine Feature Parity | **Y** | 0 | 5 | 3 | 1 | No source field selection; no REJECT flow; no null handling; no per-column Customize; no CHECK_FIELDS_NUM |
| Code Quality | **Y** | 2 | 5 | 4 | 1 | Cross-cutting base class bugs; NaN/None handling gaps; no per-row error capture; streaming drops reject data; phantom rows from `continue`; output_schema type mismatch; iterrows() anti-pattern |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | `iterrows()` is O(n) Python loop; no vectorized extraction; no streaming support for positional extraction |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tExtractPositionalFields Does

`tExtractPositionalFields` extracts data from a single formatted string column and generates multiple output columns based on fixed-width positional field definitions. It is the positional counterpart to `tExtractDelimitedFields`. The component takes one incoming column, slices it at fixed character positions defined by a pattern (comma-separated field widths), and produces one output column per field. It is commonly placed downstream of `tFileInputFullRow` or `tFileInputDelimited` (when the file is read as a single-column raw string).

**Source**: [tExtractPositionalFields Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/textractpositionalfields-standard-properties), [tExtractPositionalFields Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/textractpositionalfields)

**Component family**: Processing
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | Schema editor | -- | Column definitions for the output structure. Defines names, types, lengths, patterns for each extracted field. |
| 2 | Field | `FIELD` | Dropdown (incoming columns) | First column | **The source column to extract from**. Selects which incoming field contains the positional data string. Critical for multi-column input DataFrames. |
| 3 | Pattern | `PATTERN` | String (quoted) | -- | **Mandatory**. Comma-separated integers defining field widths in characters (e.g., `"5,4,5"`). Each integer defines the character width of one output field. Total widths should equal or be less than the source string length. |
| 4 | Die on error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | When checked, stops the entire job on extraction error. When unchecked, error rows are skipped and routed to REJECT (if connected). **Note**: Talend default is `true`, unlike most other components where default is `false`. |
| 5 | Ignore NULL as source data | `IGNORE_NULL` | Boolean (CHECK) | `false` | When checked, null values in the source field are silently skipped (no output row generated). When unchecked, null source values generate output rows with null fields. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 6 | Customize | `CUSTOMIZE` | Boolean (CHECK) | `false` | Enables per-column customization of extraction behavior. When enabled, exposes a table with per-column Size, Padding char, and Alignment settings that override the global Pattern. |
| 7 | Trim Column | `TRIM` | Boolean (CHECK) | `false` | Remove leading and trailing whitespace from ALL extracted fields. Global trim applied after extraction. |
| 8 | Advanced separator (for number) | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands and decimal separators. |
| 9 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 10 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 11 | Check each row structure against schema | `CHECK_FIELDS_NUM` | Boolean (CHECK) | `false` | Validate that each row's source string is long enough to satisfy all field widths. Rows that fail are routed to REJECT. |
| 12 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Customize Sub-Properties (when CUSTOMIZE=true)

When `CUSTOMIZE=true`, the Pattern field is overridden by a per-column table:

| Sub-Property | Type | Default | Description |
|--------------|------|---------|-------------|
| Column | Selection (schema columns) | -- | The target output column |
| Size | Integer | -- | Character width for this column (overrides the global Pattern width) |
| Padding char | Character | `" "` (space) | Character to strip from the extracted value. Padding characters are removed based on the Alignment setting. |
| Alignment | Dropdown | Left | `Left`, `Right`, or `Center`. Determines which side padding characters are stripped from. Left alignment strips trailing padding; Right strips leading padding; Center strips both. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `Row > Main` | Input | Row | Incoming data containing the source string column. Required. |
| `Row > Main` | Output | Row | Successfully extracted rows with all output schema columns populated. |
| `Row > Reject` | Output | Row | Rows that failed extraction (short strings, type mismatches). Includes `errorCode` (String) and `errorMessage` (String) columns. Only active when `DIE_ON_ERROR=false`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows processed. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully extracted and output via Main. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to REJECT. Zero when no REJECT link is connected. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred. Available for downstream reference when `DIE_ON_ERROR=false`. |

### 3.6 Behavioral Notes

1. **FIELD parameter**: The component requires selecting which incoming column contains the positional data. In Talend Studio, this is a dropdown populated from the input schema. If the input has multiple columns, only the selected FIELD column is processed; other columns are discarded from the output. The output schema is entirely defined by the component's schema editor, not inherited from the input.

2. **Pattern interpretation**: The pattern `"5,4,5"` means: extract 5 characters for field 1, then 4 characters for field 2, then 5 characters for field 3. Positions are contiguous -- field 2 starts immediately after field 1 ends. Total pattern width does not need to equal source string length; trailing characters beyond the pattern are ignored.

3. **Short lines**: When a source string is shorter than the total pattern width, Talend extracts whatever characters are available. Fields that start beyond the string length receive empty strings. Fields that start within the string but extend beyond it receive a partial (truncated) value. This is NOT an error condition unless `CHECK_FIELDS_NUM=true`.

4. **IGNORE_NULL=true**: When the source field is null (Java null), the entire row is silently skipped -- no output row is generated and no error is raised. When `IGNORE_NULL=false` (default), a null source field generates output with null values for all extracted fields.

5. **REJECT flow behavior**: When a REJECT link is connected and `DIE_ON_ERROR=false`, rows that fail extraction (type conversion errors, structural validation failures) are sent to REJECT with `errorCode` and `errorMessage` columns. When REJECT is NOT connected and `DIE_ON_ERROR=false`, error rows are silently dropped.

6. **Die on error default**: Unlike most Talend components where `DIE_ON_ERROR` defaults to `false`, `tExtractPositionalFields` defaults to `true`. This means by default, any extraction error stops the entire job.

7. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow.

8. **Reserved word "line"**: In Spark jobs, the field name "line" should not be used as it is a reserved word. Not applicable to Standard framework but noted for portability.

9. **Customize vs Pattern**: When `CUSTOMIZE=true`, the per-column Size settings override the global Pattern values. The Padding char and Alignment settings provide more granular control than global Trim. Both cannot be meaningfully used simultaneously -- Customize takes precedence.

10. **BOM characters**: Talend does not explicitly handle BOM (Byte Order Mark) characters in the source string. If the first row contains a BOM (`\uFEFF` for UTF-8, `\xFF\xFE` for UTF-16 LE), it will be included in the first field's character count, potentially shifting all field positions.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_textract_positional_fields()` in `component_parser.py` lines 2037-2058) which is called AFTER `parse_base_component()` processes all raw parameters. The flow is:

1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` (line 226)
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict
3. Since `tExtractPositionalFields` is NOT in `_map_component_parameters()`, it falls through to `return config_raw` (line 386), which populates `component['config']` with ALL raw Talend parameters
4. `converter.py` then calls `parse_textract_positional_fields(node, component)` (line 326)
5. The dedicated parser overlays 6 specific parameters on top of the raw config
6. Schema is extracted generically from `<metadata connector="FLOW">` and `<metadata connector="REJECT">` nodes in `parse_base_component()` (lines 475-508)

**Double-mapping issue**: Because `_map_component_parameters()` returns `config_raw` (all raw parameters) for unmapped component types, `component['config']` contains BOTH the raw Talend parameter names (e.g., `PATTERN`, `DIE_ON_ERROR`, `TRIM`) AND the mapped names (e.g., `pattern`, `die_on_error`, `trim`). This creates config pollution with duplicate keys in different casings.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `PATTERN` | Yes | `pattern` | 2045-2046 | Dedicated parser extracts and maps |
| 2 | `DIE_ON_ERROR` | Yes | `die_on_error` | 2047-2048 | Dedicated parser converts to boolean |
| 3 | `TRIM` | Yes | `trim` | 2049-2050 | Dedicated parser converts to boolean |
| 4 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | 2051-2052 | Dedicated parser converts to boolean |
| 5 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | 2053-2054 | Dedicated parser extracts |
| 6 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | 2055-2056 | Dedicated parser extracts |
| 7 | `FIELD` | **No** | -- | -- | **Not extracted. Engine cannot select source column by name. Defaults to first column or "line" column.** |
| 8 | `IGNORE_NULL` | **No** | -- | -- | **Not extracted. Engine does not handle null source field values distinctly.** |
| 9 | `CUSTOMIZE` | **No** | -- | -- | **Not extracted. No per-column Size/Padding/Alignment support.** |
| 10 | `CHECK_FIELDS_NUM` | **No** | -- | -- | **Not extracted. No row structure validation.** |
| 11 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 12 | `SCHEMA` (output) | **Partial** | `schema.output` | Generic (475-508) | Extracted generically in `parse_base_component()`. Type converted to Python format via `ExpressionConverter.convert_type()`. |

**Summary**: 6 of 10 runtime-relevant parameters extracted (60%). 4 runtime-relevant parameters missing.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 475-508). Note that the dedicated `parse_textract_positional_fields()` does NOT extract schema -- it relies entirely on the generic extraction in `parse_base_component()`.

Compare with the sibling `parse_textract_regex_fields()` (lines 1992-2035), which DOES have its own schema extraction loop. This is an inconsistency.

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
| `talendType` | **No** | Full Talend type string not preserved |

**REJECT schema**: The generic parser extracts REJECT metadata when present (`component['schema']['reject'] = schema_cols`). However, the engine never uses it -- there is no REJECT flow implementation.

### 4.3 Expression Handling

The dedicated `parse_textract_positional_fields()` parser uses `.strip('"')` on raw values (line 2043) and does NOT integrate with the expression converter for Java expression detection or context variable resolution on the PATTERN value.

However, since `parse_base_component()` runs first and populates `config_raw` (which includes Java expression marking via `mark_java_expression()` on line 469), the raw Talend parameter values in `component['config']` DO have `{{java}}` markers applied. The dedicated parser's overlay values do NOT have these markers because it re-reads from the XML node directly (`node.findall('.//elementParameter')`).

**Known limitation**: If the `PATTERN` value contains a Java expression (e.g., `context.pattern`), the dedicated parser extracts the raw value without `{{java}}` marking, while the generic `config_raw` version may have been marked. The dedicated parser's value takes precedence, potentially breaking Java expression resolution.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-EPF-001 | **P1** | **`FIELD` parameter not extracted**: The source column selection (`FIELD`) is not parsed. The engine has no way to know which incoming column contains the positional data, falling back to a hardcoded heuristic (check for `"line"` column, then use first column). This fails when the input has multiple columns and the target is not the first one. |
| CONV-EPF-002 | **P1** | **`IGNORE_NULL` not extracted**: Null handling behavior is not configurable. The engine converts null/NaN to the string `"nan"` via `str(line)` on line 176, then attempts positional extraction on the literal string `"nan"`. This produces garbage output instead of either skipping the row or generating null fields. |
| CONV-EPF-003 | **P2** | **`CUSTOMIZE` not extracted**: Per-column Size, Padding char, and Alignment settings are not available. Only the global Pattern and Trim are supported. Jobs using Customize will silently use the global Pattern, producing wrong field widths. |
| CONV-EPF-004 | **P2** | **`CHECK_FIELDS_NUM` not extracted**: Row structure validation unavailable. Short source strings silently produce truncated/empty fields instead of being routed to REJECT. |
| CONV-EPF-005 | **P2** | **Config pollution from generic fallthrough**: `_map_component_parameters()` returns all raw Talend parameters (uppercase names like `PATTERN`, `DIE_ON_ERROR`) since `tExtractPositionalFields` has no dedicated mapping. The dedicated parser then adds lowercase versions. Config contains both `PATTERN` and `pattern`, `DIE_ON_ERROR` (raw boolean string or actual boolean from CHECK field) and `die_on_error` (boolean). |
| CONV-EPF-006 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). |
| CONV-EPF-007 | **P3** | **Java expression bypass in dedicated parser**: The dedicated parser re-reads XML values directly (line 2041: `node.findall('.//elementParameter')`) and strips quotes. If PATTERN contains a Java expression or context variable, the `{{java}}` marker applied by `parse_base_component()` is overwritten. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Fixed-width positional extraction | **Yes** | High | `_process()` lines 186-208 | Core extraction logic using string slicing. Correct positional extraction. |
| 2 | Pattern parsing (comma-separated widths) | **Yes** | High | `_process()` line 159 | `int(width) for width in pattern.split(',')`. Correct. |
| 3 | Trim all extracted fields | **Yes** | High | `_process()` lines 198-199 | `field_value.strip()` when `trim=True`. Correct. |
| 4 | Die on error | **Yes** | Medium | `_process()` lines 233-239 | Raises `ComponentExecutionError` when `die_on_error=True`. Returns empty DF + input as reject when False. But default differs: engine defaults to `False`, Talend defaults to `True`. |
| 5 | Output schema column naming | **Yes** | Medium | `_process()` lines 211-217 | Uses `output_schema` if available and has enough fields. Falls back to `field_1, field_2, ...`. |
| 6 | Short line handling | **Yes** | Medium | `_process()` line 195 | `line[start_pos:end_pos] if len(line) > start_pos else ''`. Handles lines shorter than pattern. Does NOT produce partial values when field starts within string but extends beyond it -- Python slicing handles this correctly. |
| 7 | BOM stripping | **Yes** | Medium | `_process()` lines 179-182 | Strips UTF-8 BOM (`\uFEFF`) and UTF-16 LE BOM (`\xFF\xFE`). But UTF-16 LE BOM check is flawed -- at this point the data is already a Python string, so `\xFF\xFE` is a 2-char string match on unicode characters, not raw bytes. |
| 8 | Advanced separator config | **Partial** | Low | `_validate_config()` lines 123-128 | Config is validated and accepted, but the actual separator replacement logic is **not implemented** in `_process()`. The `advanced_separator`, `thousands_separator`, and `decimal_separator` config values are parsed but never used during extraction. |
| 9 | Statistics tracking (NB_LINE, NB_LINE_OK) | **Yes** | Medium | `_process()` line 227 | `_update_stats(rows_in, rows_out, rows_rejected)`. Correctly accumulates. But NB_LINE_REJECT always 0 since no per-row error capture. |
| 10 | Input DataFrame handling | **Yes** | Medium | `_process()` lines 135-147 | Handles None, empty, and non-DataFrame input. Converts non-DataFrame to DataFrame. |
| 11 | **Source field selection (FIELD)** | **No** | N/A | -- | **No FIELD parameter support. Uses hardcoded heuristic: check for "line" column, else use first column (iloc[0]). Fails for multi-column input where target is not first or "line".** |
| 12 | **REJECT flow** | **No** | N/A | -- | **No per-row reject output. All rows succeed or entire batch fails. When `die_on_error=False`, errors return empty main + full input as reject -- no individual row routing.** |
| 13 | **Null source field handling (IGNORE_NULL)** | **No** | N/A | -- | **NaN/None source values are converted to string "nan" or "None" via `str(line)` and then extracted positionally, producing garbage data.** |
| 14 | **Customize (per-column Size/Padding/Alignment)** | **No** | N/A | -- | **No per-column customization. Only global Pattern + Trim.** |
| 15 | **Check row structure (CHECK_FIELDS_NUM)** | **No** | N/A | -- | **Short source strings are silently handled (partial/empty fields). No validation or REJECT routing.** |
| 16 | **Advanced separator application** | **No** | N/A | -- | **Config is parsed but never applied. Thousands/decimal separators are never substituted in extracted values.** |
| 17 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-EPF-001 | **P1** | **No source field selection (FIELD)**: Talend lets the user select which incoming column to extract from via a dropdown. The engine uses a hardcoded heuristic: first checks for a column named `"line"` (line 166), then falls back to `row.iloc[0]` (line 169). This fails when: (a) the input has multiple columns and the target is not the first, (b) the target column is not named "line", (c) the input has zero columns (logged but silently continues). |
| ENG-EPF-002 | **P1** | **No REJECT flow**: Talend routes individual failed rows to REJECT with `errorCode` and `errorMessage`. The engine's error handling is all-or-nothing: when `die_on_error=True`, it raises `ComponentExecutionError` for the entire batch. When `die_on_error=False`, it returns empty main DataFrame + entire input as reject (line 239). There is no per-row error detection or routing. |
| ENG-EPF-003 | **P1** | **NaN/None input produces garbage**: When a source value is NaN (pandas NaN), `str(line)` on line 176 converts it to the literal string `"nan"`. Positional extraction then slices `"nan"` -- e.g., pattern `"5,4,5"` produces `["nan  ", "    ", "    "]` (padded garbage). In Talend with `IGNORE_NULL=false`, null source generates null output fields. With `IGNORE_NULL=true`, the row is skipped entirely. Neither behavior is implemented. |
| ENG-EPF-004 | **P1** | **Empty string input not handled distinctly**: When the source field is an empty string `""`, the engine produces a row with all empty-string fields (correct for Talend with `IGNORE_NULL=false`). However, there is no distinction between empty string and null -- both should behave differently based on `IGNORE_NULL`. |
| ENG-EPF-005 | **P1** | **`die_on_error` default differs from Talend**: The engine defaults `die_on_error` to `False` (line 155), but Talend's `tExtractPositionalFields` defaults to `True` (DIE_ON_ERROR is checked by default). This means unconverted jobs behave differently on errors: Talend stops, v1 continues silently. |
| ENG-EPF-006 | **P2** | **No per-column Customize support**: The `CUSTOMIZE` mode with per-column Size, Padding char, and Alignment is not implemented. Jobs using Customize will produce wrong output because only the global Pattern is used. |
| ENG-EPF-007 | **P2** | **Advanced separator config accepted but never applied**: The component validates `advanced_separator`, `thousands_separator`, and `decimal_separator` config in `_validate_config()` (lines 123-128), but `_process()` never uses these values. Numeric fields with locale-specific formatting (e.g., `1.234,56` for German locale) will not be converted. |
| ENG-EPF-008 | **P2** | **No CHECK_FIELDS_NUM validation**: Short source strings produce truncated/empty fields silently. In Talend with `CHECK_FIELDS_NUM=true`, these rows go to REJECT. |
| ENG-EPF-009 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=False`, the error message is not stored in globalMap for downstream reference. |
| ENG-EPF-010 | **P3** | **UTF-16 LE BOM check is logically incorrect**: Line 181 checks `line.startswith('\xff\xfe')`, but at this point `line` is a Python string (unicode), not raw bytes. The characters `\xff` and `\xfe` in a Python string are the unicode characters U+00FF and U+00FE, not the raw BOM bytes. This check will almost never match. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set via base class mechanism. **BUT**: `_update_global_map()` crashes due to BUG-EPF-001. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE since no per-row reject exists. |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no per-row error capture. Only non-zero in catch-all error path (line 237). |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-EPF-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just ExtractPositionalFields, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The component will crash after processing data but before returning results. |
| BUG-EPF-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-EPF-003 | **P1** | `src/v1/engine/components/transform/extract_positional_fields.py:176` | **NaN source values become literal string `"nan"`**: When a DataFrame cell contains `NaN` (pandas missing value), `str(line)` converts it to the string `"nan"`. Positional extraction then slices this 3-character string, producing garbage data. For pattern `"5,4,5"`, NaN input produces `["nan", "", ""]`. This is wrong for both `IGNORE_NULL=true` (should skip row) and `IGNORE_NULL=false` (should produce null fields). |
| BUG-EPF-004 | **P1** | `src/v1/engine/components/transform/extract_positional_fields.py:166-169` | **Source column selection heuristic is fragile**: The engine checks `if 'line' in input_data.columns` (line 166) then falls back to `row.iloc[0]` (line 169). This hardcoded logic: (a) only works if source column is literally named "line" or is the first column, (b) produces wrong results silently when the target is a different column, (c) the column name "line" check is performed inside the row loop (line 166) but the condition is stable across rows -- wasted per-row evaluation. |
| BUG-EPF-005 | **P1** | `src/v1/engine/components/transform/extract_positional_fields.py:237` | **Entire input DataFrame returned as reject on error**: When `die_on_error=False` and any exception occurs, the ENTIRE input DataFrame is returned as reject (line 239: `return {'main': pd.DataFrame(), 'reject': input_data}`). This is all-or-nothing -- there is no per-row error tracking. If row 500 of 1000 causes an error, all 1000 rows are rejected. |
| BUG-EPF-006 | **P1** | `src/v1/engine/components/transform/extract_positional_fields.py:181` | **UTF-16 LE BOM check is incorrect for Python strings**: `line.startswith('\xff\xfe')` checks for unicode characters U+00FF U+00FE in a Python str. By the time data reaches this code, it has already been decoded from bytes to a Python string by pandas. The raw BOM bytes `0xFF 0xFE` would only appear in the byte representation, not in the decoded string. This check is effectively dead code that will never match real UTF-16 BOM sequences. |
| BUG-EPF-007 | **P1** | `src/v1/engine/base_component.py:_execute_streaming()` | **Streaming mode drops reject data**: `_execute_streaming()` only collects `main`, silently discards `reject` DataFrame when HYBRID mode activates. Any per-chunk reject rows produced by `_process()` are lost because the streaming accumulator only appends `chunk_result['main']`. When the input exceeds the 3 GB HYBRID threshold and streaming kicks in, all reject output is silently dropped, making `NB_LINE_REJECT` inaccurate and downstream reject handling impossible. |
| BUG-EPF-008 | **P1** | `src/v1/engine/components/transform/extract_positional_fields.py:172` | **`continue` on line 172 causes phantom rows**: When no data columns are found, the `continue` statement skips the row without adding it to either `extracted_data` or a reject list. Skipped rows are neither in main nor reject output. This causes `NB_LINE != NB_LINE_OK + NB_LINE_REJECT` -- the stats invariant is violated because these phantom rows are counted in `rows_in` but never appear in `rows_out` or `rows_rejected`. |
| BUG-EPF-009 | **P2** | `src/v1/engine/components/transform/extract_positional_fields.py` | **`output_schema` type hint is `Dict` but code uses it as `List`**: The `output_schema` attribute has a `Dict` type hint (inherited or declared), but the code treats it as a `List` -- it subscripts with integer indices (`output_schema[:len(field_widths)]`) and iterates items as dicts (`field['name']`). If `output_schema` is ever set to an actual `Dict` (as the type hint suggests), the code will crash with `TypeError` on the slice operation and iteration. |
| BUG-EPF-010 | **P2** | `src/v1/engine/components/transform/extract_positional_fields.py:164` | **`iterrows()` is used inside the row loop**: The `input_data.iterrows()` call on line 164 iterates using Python-level loops instead of vectorized pandas operations. For large DataFrames (100K+ rows), this is orders of magnitude slower than vectorized string slicing. Also, `'line' in input_data.columns` check on line 166 is evaluated for every row despite being invariant. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-EPF-001 | **P2** | **Column naming fallback uses `field_N` format**: When `output_schema` is not available or has fewer entries than field widths, columns are named `field_1, field_2, ...` (line 217). Talend uses the schema column names always -- there is no fallback naming. If schema is missing, the job should error, not silently use generated names. |
| NAME-EPF-002 | **P3** | **`trim` config key (singular)** vs tExtractDelimitedFields' `trim` (also singular). Consistent between sibling extract components. No issue. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-EPF-001 | **P2** | "`_validate_config()` should be called during init" | Method IS called during `__init__()` (line 71) -- CORRECT. This is better than the FileInputDelimited component where `_validate_config()` is dead code. |
| STD-EPF-002 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |
| STD-EPF-003 | **P2** | "Config should not contain raw Talend parameter names" | Config contains BOTH raw Talend names (e.g., `PATTERN`, `TRIM`) from generic fallthrough AND mapped names (`pattern`, `trim`) from dedicated parser. Config pollution. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-EPF-001 | **P3** | **Excessive DEBUG logging inside row loop**: Lines 184, 195, 202, 208 all log at DEBUG level inside the row iteration loop. For a DataFrame with 1M rows, this generates 4M+ log messages even at DEBUG level. The per-row logging should be conditional or removed. |

### 6.5 Security

No security concerns for this component. It processes in-memory data and does not access the filesystem or network.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for empty input, ERROR for failures -- correct |
| Start/complete logging | `execute()` logs start (line 81); `_process()` logs completion (line 228) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| **Concern** | Per-row DEBUG logging inside `iterrows()` loop (lines 184, 195, 202, 208) generates excessive output for large DataFrames |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError`, `ComponentExecutionError`, `DataValidationError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern in `ComponentExecutionError` (line 235) -- correct |
| `die_on_error` handling | Two code paths: raises `ComponentExecutionError` when True (line 235), returns empty DF + input as reject when False (line 239) -- correct structure but wrong granularity (all-or-nothing) |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and error details -- correct |
| **Concern** | No per-row error handling. A single malformed value in row 500 causes all 1000 rows to fail. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]` -- correct |
| Parameter types | `input_data: Optional[pd.DataFrame]` -- correct |
| `__init__` parameters | `component_id: str, config: Dict[str, Any]` -- correct. But `global_map` and `context_manager` lack type hints (use `Any` implicitly via base class). |
| `execute` override | Parameter types inherited from base class -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-EPF-001 | **P1** | **`iterrows()` is O(n) Python-level loop**: Lines 164-208 use `input_data.iterrows()` which iterates row-by-row in Python. For positional extraction, vectorized pandas `str.slice()` would be dramatically faster. Example: `df['field_1'] = source_col.str.slice(0, 5)` is 10-100x faster than iterating rows. For 1M rows, the difference is seconds vs minutes. |
| PERF-EPF-002 | **P2** | **Column check inside row loop**: `'line' in input_data.columns` on line 166 is evaluated for every row despite being invariant across the DataFrame. Should be hoisted outside the loop. |
| PERF-EPF-003 | **P3** | **Per-row DEBUG logging**: Four `logger.debug()` calls inside the row loop (lines 184, 195, 202, 208) add overhead even when DEBUG logging is disabled (string formatting still occurs unless using lazy `%s` formatting). |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | The `_process()` method processes the entire DataFrame in batch. It does NOT support streaming. The base class `_execute_streaming()` would call `_process()` per chunk, which works but loses the ability to detect cross-chunk patterns. |
| HYBRID mode auto-switch | Inherited from BaseComponent. Switches to streaming when input > 3GB. For positional extraction, this means the `iterrows()` loop runs per chunk -- still slow but memory-bounded. |
| Output DataFrame creation | `pd.DataFrame(extracted_data, columns=column_names)` on line 220 creates the output in one allocation. For very large datasets, this doubles memory (input + output simultaneously). |
| Intermediate list | `extracted_data` (line 163) accumulates all extracted rows as lists-of-lists in memory before creating the output DataFrame. For 10M rows with 10 fields, this is ~800MB of Python list overhead. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| No streaming-specific logic | The component has no `_execute_streaming()` override. It relies on the base class chunking, which calls `_process()` per chunk. |
| Reject flow + streaming | Not applicable (no reject flow), but if implemented, streaming mode would need to yield both main and reject chunks. |
| Stats accumulation | `_update_stats()` is called once per `_process()` call, which correctly accumulates across chunks when streaming. |
| Per-row loop in streaming | Even in streaming mode, each chunk is processed via `iterrows()`, so the per-row overhead remains. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `ExtractPositionalFields` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 240 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic positional extraction | P0 | Pattern `"5,4,5"` on input `"HELLOWORK12345"` produces `["HELLO", "WORK", "12345"]` |
| 2 | Schema column naming | P0 | With output_schema defining columns `[first, middle, last]`, verify extracted fields use schema names not `field_N` |
| 3 | Short input line | P0 | Pattern `"5,4,5"` on input `"HI"` produces `["HI", "", ""]` -- verify no crash and correct partial extraction |
| 4 | Empty input DataFrame | P0 | Verify returns empty main DataFrame with stats (0, 0, 0) |
| 5 | None input | P0 | Verify returns empty main DataFrame with stats (0, 0, 0) |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats after execution |
| 7 | NaN source value | P0 | Input with NaN in source column should NOT produce `"nan"` output. Should skip row or produce null fields. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Trim enabled | P1 | Pattern `"5,5"` on input `"  HI   WO "` with `trim=True` produces `["HI", "WO"]` |
| 9 | Die on error = True | P1 | Malformed pattern (e.g., non-integer) raises `ConfigurationError` |
| 10 | Die on error = False | P1 | Processing error returns empty main + input as reject |
| 11 | Multi-column input | P1 | Input DataFrame with columns `[id, data, extra]` -- verify extraction from correct column (requires FIELD support) |
| 12 | BOM in first field | P1 | Input starting with UTF-8 BOM `\uFEFF` should strip BOM before extraction |
| 13 | Pattern with spaces | P1 | Pattern `" 5 , 4 , 5 "` with spaces around numbers -- verify `int(part.strip())` handles this |
| 14 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution (requires BUG-EPF-001 fix) |
| 15 | Large DataFrame performance | P1 | 100K+ rows should complete in reasonable time (baseline for vectorization work) |
| 16 | Context variable in pattern | P1 | `${context.pattern}` should resolve via context manager |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Zero-width field in pattern | P2 | Pattern `"5,0,5"` -- verify handling of zero-width field (currently rejected by validation) |
| 18 | Single-field pattern | P2 | Pattern `"10"` -- single field extraction |
| 19 | Very long line | P2 | Input with 10,000+ characters, pattern extracting first 3 fields -- verify trailing chars are ignored |
| 20 | Empty string source | P2 | Source field is empty string `""` -- all fields should be empty strings |
| 21 | Unicode characters in source | P2 | Multi-byte UTF-8 characters -- verify extraction counts characters, not bytes |
| 22 | Output schema shorter than pattern | P2 | Schema has 2 columns but pattern defines 3 fields -- verify column naming fallback |
| 23 | Advanced separator application | P2 | `advanced_separator=True`, `thousands_separator=","` -- verify numeric field conversion (requires implementation) |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-EPF-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-EPF-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-EPF-001 | Testing | Zero v1 unit tests for this component. All 240 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-EPF-001 | Converter | `FIELD` parameter not extracted -- engine cannot select which incoming column to extract from. |
| CONV-EPF-002 | Converter | `IGNORE_NULL` not extracted -- null handling behavior not configurable. |
| ENG-EPF-001 | Engine | No source field selection -- hardcoded heuristic checks for "line" column then falls back to first column. |
| ENG-EPF-002 | Engine | No REJECT flow -- all-or-nothing error handling. Individual bad rows cannot be routed to reject. |
| ENG-EPF-003 | Engine | NaN source values become literal string "nan", producing garbage positional extraction output. |
| ENG-EPF-004 | Engine | Empty string vs null not distinguished. Both should behave differently based on IGNORE_NULL. |
| ENG-EPF-005 | Engine | `die_on_error` default is `False` but Talend default is `True`. Unconverted jobs behave differently on errors. |
| BUG-EPF-003 | Bug | NaN source values converted to "nan" string and extracted positionally. |
| BUG-EPF-004 | Bug | Source column selection heuristic is fragile -- hardcoded "line" column name check. |
| BUG-EPF-005 | Bug | Entire input returned as reject on any error -- no per-row granularity. |
| BUG-EPF-006 | Bug | UTF-16 LE BOM check is incorrect for Python strings (checks unicode chars, not bytes). |
| BUG-EPF-007 | Bug | Streaming mode drops reject data -- `_execute_streaming()` only collects `main`, silently discards `reject` DataFrame when HYBRID mode activates. |
| BUG-EPF-008 | Bug | `continue` on line 172 causes phantom rows -- skipped rows are neither in main nor reject, violating `NB_LINE == NB_LINE_OK + NB_LINE_REJECT`. |
| PERF-EPF-001 | Performance | `iterrows()` Python-level loop is 10-100x slower than vectorized pandas `str.slice()`. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-EPF-003 | Converter | `CUSTOMIZE` not extracted -- per-column Size/Padding/Alignment unavailable. |
| CONV-EPF-004 | Converter | `CHECK_FIELDS_NUM` not extracted -- row structure validation unavailable. |
| CONV-EPF-005 | Converter | Config pollution from generic fallthrough -- both raw Talend params and mapped params in config. |
| CONV-EPF-006 | Converter | Schema type format violates STANDARDS.md -- Python types instead of Talend types. |
| ENG-EPF-006 | Engine | No per-column Customize support (Size/Padding char/Alignment). |
| ENG-EPF-007 | Engine | Advanced separator config accepted but never applied in extraction logic. |
| ENG-EPF-008 | Engine | No CHECK_FIELDS_NUM -- short strings silently produce empty/truncated fields. |
| ENG-EPF-009 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. |
| BUG-EPF-009 | Bug | `output_schema` type hint is `Dict` but code uses it as `List` (subscripts, iterates items). Type mismatch crashes if ever set to actual Dict. |
| BUG-EPF-010 | Bug | `iterrows()` used instead of vectorized operations; column check inside loop. |
| NAME-EPF-001 | Naming | Fallback column names `field_N` instead of erroring on missing schema. |
| STD-EPF-002 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| STD-EPF-003 | Standards | Config contains both raw Talend parameter names and mapped names. |
| PERF-EPF-002 | Performance | Column check `'line' in input_data.columns` inside row loop (invariant). |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-EPF-007 | Converter | Java expression bypass in dedicated parser -- re-reads XML directly, overwriting `{{java}}` markers. |
| ENG-EPF-010 | Engine | UTF-16 LE BOM check is logically incorrect for Python strings (dead code). |
| NAME-EPF-002 | Naming | `trim` naming is consistent with sibling extract components. No action needed. |
| DBG-EPF-001 | Debug | Excessive per-row DEBUG logging (4 log calls per row in `iterrows()` loop). |
| PERF-EPF-003 | Performance | Per-row DEBUG logging adds overhead even when logging is disabled. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 14 | 2 converter, 5 engine, 6 bugs, 1 performance |
| P2 | 14 | 4 converter, 4 engine, 2 bugs, 1 naming, 2 standards, 1 performance |
| P3 | 5 | 1 converter, 1 engine, 1 naming, 1 debug, 1 performance |
| **Total** | **36** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-EPF-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-EPF-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Fix NaN source value handling** (BUG-EPF-003, ENG-EPF-003): Before `str(line)` on line 176, add a null/NaN check:
   ```python
   if pd.isna(line):
       # Skip row (IGNORE_NULL=true behavior) or produce null fields
       extracted_data.append([None] * len(field_widths))
       continue
   ```
   Until `IGNORE_NULL` is extracted from the converter, default to skipping NaN rows (safer than producing garbage).

4. **Create unit test suite** (TEST-EPF-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic extraction, schema naming, short lines, empty/None input, statistics, and NaN handling.

5. **Add FIELD parameter support** (CONV-EPF-001, ENG-EPF-001): Extract `FIELD` in the converter parser. In the engine, use `self.config.get('field')` to select the source column by name instead of the hardcoded "line" / iloc[0] heuristic. Fallback order: (a) config `field` name, (b) first column.

### Short-Term (Hardening)

6. **Implement per-row REJECT flow** (ENG-EPF-002): Wrap the per-row extraction in a try/except inside the `iterrows()` loop. Capture failed rows with `errorCode` and `errorMessage`. Return `{'main': good_df, 'reject': reject_df}`. Update `_update_stats()` with actual reject count.

7. **Extract `IGNORE_NULL` from converter** (CONV-EPF-002): Add `elif name == 'IGNORE_NULL'` to the dedicated parser. In the engine, check `self.config.get('ignore_null', False)` before extraction and skip null rows accordingly.

8. **Fix `die_on_error` default** (ENG-EPF-005): Change default from `False` to `True` on line 155 to match Talend behavior: `die_on_error = self.config.get('die_on_error', True)`.

9. **Vectorize extraction** (PERF-EPF-001): Replace `iterrows()` with vectorized pandas operations:
   ```python
   source_col = input_data[field_column].astype(str)
   current_pos = 0
   for idx, width in enumerate(field_widths):
       output_df[col_names[idx]] = source_col.str.slice(current_pos, current_pos + width)
       if trim:
           output_df[col_names[idx]] = output_df[col_names[idx]].str.strip()
       current_pos += width
   ```
   This eliminates the Python-level row loop entirely and is 10-100x faster.

10. **Clean up config pollution** (CONV-EPF-005): Either add `tExtractPositionalFields` to `_map_component_parameters()` with a clean mapping (returning only the mapped keys), or add the component to `components_with_dedicated_parsers` list on line 421 so `parse_base_component()` skips raw parameter population.

11. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-EPF-009): In error handlers, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

12. **Implement advanced separator application** (ENG-EPF-007): After extraction, when `advanced_separator=True`, apply separator replacement to numeric fields before type conversion:
    ```python
    if self.config.get('advanced_separator', False):
        thousands = self.config.get('thousands_separator', ',')
        decimal = self.config.get('decimal_separator', '.')
        # Replace thousands separator and normalize decimal
        field_value = field_value.replace(thousands, '').replace(decimal, '.')
    ```

### Long-Term (Optimization)

13. **Implement CUSTOMIZE mode** (CONV-EPF-003, ENG-EPF-006): Extract the per-column table from the converter (CUSTOMIZE elementParameters contain nested elementValue groups for Column, Size, Padding char, Alignment). In the engine, use per-column settings to override global Pattern values and apply Padding/Alignment stripping.

14. **Implement CHECK_FIELDS_NUM** (CONV-EPF-004, ENG-EPF-008): After computing total pattern width, compare with source string length. If source is shorter and `check_fields_num=True`, route to REJECT.

15. **Remove UTF-16 LE BOM dead code** (BUG-EPF-006, ENG-EPF-010): Remove the `'\xff\xfe'` check on line 181. Keep only the UTF-8 BOM check (`'\ufeff'`), which is correct for Python strings.

16. **Reduce per-row logging** (DBG-EPF-001): Move DEBUG logging outside the row loop. Log a summary after extraction (e.g., "Processed N rows, extracted M fields per row") instead of per-row details. For debugging specific rows, add a configurable `debug_row_limit` parameter.

17. **Fix converter schema type format** (CONV-EPF-006, STD-EPF-002): Preserve Talend type format (`id_String`, `id_Integer`, etc.) in schema extraction, matching STANDARDS.md requirements.

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 2037-2058
def parse_textract_positional_fields(self, node, component):
    """
    Parse tExtractPositionalFields component from Talend XML.
    """
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '').strip('"')

        if name == 'PATTERN':
            component['config']['pattern'] = value
        elif name == 'DIE_ON_ERROR':
            component['config']['die_on_error'] = value.lower() == 'true'
        elif name == 'TRIM':
            component['config']['trim'] = value.lower() == 'true'
        elif name == 'ADVANCED_SEPARATOR':
            component['config']['advanced_separator'] = value.lower() == 'true'
        elif name == 'THOUSANDS_SEPARATOR':
            component['config']['thousands_separator'] = value
        elif name == 'DECIMAL_SEPARATOR':
            component['config']['decimal_separator'] = value

    return component
```

**Notes on this code**:
- The parser does NOT extract `FIELD`, `IGNORE_NULL`, `CUSTOMIZE`, or `CHECK_FIELDS_NUM`.
- Compare with `parse_textract_regex_fields()` (lines 1992-2035) which has its own metadata schema extraction loop. This parser relies entirely on `parse_base_component()` for schema extraction.
- The parser re-reads all `elementParameter` nodes from XML (line 2041), not from the pre-processed `config_raw`. This bypasses the Java expression marking done in `parse_base_component()`.

---

## Appendix B: Engine Class Structure

```
ExtractPositionalFields (BaseComponent)
    Methods:
        __init__(component_id, config, global_map, context_manager)
            - Calls super().__init__()
            - Calls _validate_config() -- ACTIVE (not dead code)
            - Raises ConfigurationError on invalid config
        execute(input_data) -> Dict[str, Any]
            - Override: adds logging around super().execute()
        _validate_config() -> List[str]
            - Validates: pattern (required, non-empty, comma-separated positive ints)
            - Validates: boolean fields (die_on_error, trim, advanced_separator)
            - Validates: separator fields (thousands_separator, decimal_separator)
        _process(input_data) -> Dict[str, Any]
            - Handles None/empty input
            - Converts non-DataFrame input
            - Parses pattern into field_widths
            - Iterates rows via iterrows()
            - Selects source column (heuristic: "line" or first)
            - BOM stripping (UTF-8 correct, UTF-16 LE incorrect)
            - Positional extraction via string slicing
            - Optional trimming
            - Schema-based or fallback column naming
            - Statistics update
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `PATTERN` | `pattern` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `TRIM` | `trim` | Mapped | -- |
| `ADVANCED_SEPARATOR` | `advanced_separator` | Mapped | -- |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | Mapped | -- |
| `DECIMAL_SEPARATOR` | `decimal_separator` | Mapped | -- |
| `FIELD` | `field` | **Not Mapped** | P1 |
| `IGNORE_NULL` | `ignore_null` | **Not Mapped** | P1 |
| `CUSTOMIZE` | `customize` | **Not Mapped** | P2 |
| `CHECK_FIELDS_NUM` | `check_fields_num` | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `SCHEMA` | `schema.output` | Mapped (generic) | -- |

---

## Appendix D: Comparison with Sibling Extract Components

| Feature | tExtractPositionalFields | tExtractDelimitedFields | Gap |
|---------|------------------------|------------------------|-----|
| FIELD parameter | **Missing** | Extracted (`field`) | EPF needs FIELD extraction |
| IGNORE_NULL | **Missing** | Extracted (`ignore_source_null`) | EPF needs IGNORE_NULL |
| CHECK_FIELDS_NUM | **Missing** | Extracted (`check_fields_num`) | EPF needs CHECK_FIELDS_NUM |
| CHECK_DATE | N/A | Extracted (`check_date`) | N/A for positional |
| REJECT flow | **Missing** | **Missing** | Both need REJECT |
| Schema extraction | Generic only | Generic only | Both rely on parse_base_component() |
| Vectorized processing | **No** (iterrows) | Unknown | EPF needs vectorization |
| NaN handling | **Broken** (produces "nan") | Unknown | EPF needs fix |
| _validate_config() called | **Yes** (in __init__) | Unknown | EPF is better than FID here |
| Dedicated converter parser | **Yes** | Via `_map_component_parameters()` | EPF has dedicated parser |

The `tExtractDelimitedFields` converter (in `_map_component_parameters()` lines 295-313) extracts significantly more parameters including `FIELD`, `IGNORE_SOURCE_NULL`, `CHECK_FIELDS_NUM`, and `CHECK_DATE`. The `tExtractPositionalFields` dedicated parser should be brought to feature parity with its delimited sibling.

---

## Appendix E: Detailed Code Analysis

### `__init__()` (Lines 64-77)

```python
def __init__(self, component_id: str, config: Dict[str, Any], global_map, context_manager):
    super().__init__(component_id, config, global_map, context_manager)
    logger.info(f"[{self.id}] ExtractPositionalFields component initialized")
    logger.info(f"[{self.id}] Configuration: {self.config}")
    config_errors = self._validate_config()
    if config_errors:
        error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
        logger.error(f"[{self.id}] {error_msg}")
        raise ConfigurationError(error_msg)
    else:
        logger.info(f"[{self.id}] Configuration validation passed")
```

**Analysis**:
- Calls `super().__init__()` which sets up `self.id`, `self.config`, `self.global_map`, `self.context_manager`, `self.execution_mode`, `self.stats`, `self.output_schema`, etc.
- Logs the ENTIRE config dict at INFO level (line 68). This is acceptable for debugging but may log sensitive data in production if config contains credentials (unlikely for this component but a general concern).
- Calls `_validate_config()` and raises `ConfigurationError` on failure. This is CORRECT and better than `FileInputDelimited` where `_validate_config()` is dead code.
- **Positive**: Init-time validation catches bad patterns (non-integer widths, negative widths, empty pattern) before any data processing occurs. This prevents confusing runtime errors.
- **Concern**: The `super().__init__()` call sets `self.execution_mode` via `_determine_execution_mode()` which reads `config.get('execution_mode', 'hybrid')`. Since `config` at this point contains both raw Talend params and mapped params (due to config pollution), the `execution_mode` key is unlikely to be set, defaulting to HYBRID.

### `execute()` (Lines 79-96)

```python
def execute(self, input_data=None):
    logger.info(f"[{self.id}] ===== EXECUTE CALLED =====")
    logger.info(f"[{self.id}] Input data type: {type(input_data)}")
    if hasattr(input_data, 'shape'):
        logger.info(f"[{self.id}] Input data shape: {input_data.shape}")
    if hasattr(input_data, 'columns'):
        logger.info(f"[{self.id}] Input data columns: {list(input_data.columns)}")
    try:
        result = super().execute(input_data)
        logger.info(f"[{self.id}] ===== EXECUTE COMPLETED =====")
        logger.info(f"[{self.id}] Result keys: {list(result.keys()) if result else 'None'}")
        return result
    except Exception as e:
        logger.error(f"[{self.id}] ===== EXECUTE FAILED =====")
        logger.error(f"[{self.id}] Error: {e}")
        raise
```

**Analysis**:
- This is a logging wrapper around `BaseComponent.execute()`. The actual execution flow is:
  1. `super().execute()` is called
  2. Inside `BaseComponent.execute()`: Java expressions resolved, context variables resolved, mode determined (BATCH/STREAMING/HYBRID), then `_process()` or `_execute_streaming()` called
  3. After `_process()` returns, `BaseComponent.execute()` calls `_update_global_map()` which **CRASHES** due to BUG-EPF-001
- The `except Exception as e: ... raise` block re-raises the exception after logging. This means the `_update_global_map()` crash will propagate up as a `NameError` even if `_process()` succeeded.
- Logs input shape and columns at INFO level. For production workloads, this is appropriate diagnostic information.
- **Concern**: The `super().execute()` call on line 89 will trigger the entire BaseComponent lifecycle including Java expression resolution and context variable resolution. If the config contains `{{java}}` markers on the raw Talend params (from config pollution), the Java bridge may attempt to resolve them, potentially causing errors.

### `_validate_config()` (Lines 98-130)

```python
def _validate_config(self) -> List[str]:
    errors = []
    if 'pattern' not in self.config:
        errors.append("Missing required config: 'pattern'")
    elif not isinstance(self.config['pattern'], str) or not self.config['pattern'].strip():
        errors.append("Config 'pattern' must be a non-empty string")
    else:
        try:
            pattern_parts = self.config['pattern'].split(',')
            for part in pattern_parts:
                width = int(part.strip())
                if width <= 0:
                    errors.append(f"Invalid field width in pattern: {part}. Must be positive integer")
        except ValueError as e:
            errors.append(f"Invalid pattern format: {self.config['pattern']}. Must be comma-separated integers")
    for bool_field in ['die_on_error', 'trim', 'advanced_separator']:
        if bool_field in self.config and not isinstance(self.config[bool_field], bool):
            errors.append(f"Config '{bool_field}' must be boolean")
    for sep_field in ['thousands_separator', 'decimal_separator']:
        if sep_field in self.config:
            value = self.config[sep_field]
            if not isinstance(value, str):
                errors.append(f"Config '{sep_field}' must be string")
    return errors
```

**Analysis**:
- Validates `pattern` presence, type, non-emptiness, and format (comma-separated positive integers).
- `int(part.strip())` correctly handles whitespace in pattern (e.g., `"5, 4, 5"`).
- Rejects zero-width fields (`width <= 0`). This is correct -- a zero-width field makes no sense for positional extraction.
- Validates boolean config types. **BUT**: Due to config pollution, `self.config` may contain BOTH `die_on_error` (boolean from dedicated parser) AND `DIE_ON_ERROR` (raw string `"true"` from parse_base_component). The validation checks lowercase keys only, so uppercase raw params are not validated. This is not a bug per se (the engine uses lowercase keys), but the extra uppercase keys are dead weight.
- Validates separator config types (must be string).
- **NOT validated**: The `field` parameter (not extracted). The `ignore_null` parameter (not extracted). The `customize` parameter (not extracted).
- **Positive edge case**: Pattern `"5"` (single field) is valid. Pattern `"5,4,5,3,2,1,10"` (many fields) is valid. Pattern `" 5 , 4 , 5 "` (spaces around commas/numbers) is valid due to `strip()`.
- **Edge case**: Pattern `"5,,5"` would cause `int('')` which raises `ValueError`, caught and reported. CORRECT.
- **Edge case**: Pattern `"5,-1,5"` would produce `width = -1`, caught by `width <= 0` check. CORRECT.
- **Edge case**: Pattern `"5,abc,5"` would cause `ValueError`. CORRECT.
- **Edge case**: Pattern `"5,4.5,5"` would cause `ValueError` (float not accepted). CORRECT -- field widths must be integers.

### `_process()` (Lines 132-239)

This is the core processing method. Detailed line-by-line analysis:

**Lines 132-147: Input validation**
```python
if input_data is None or input_data.empty:
    logger.warning(f"[{self.id}] Empty input received")
    self._update_stats(0, 0, 0)
    return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}
if not isinstance(input_data, pd.DataFrame):
    try:
        input_data = pd.DataFrame(input_data)
    except Exception as e:
        raise DataValidationError(f"Cannot convert input to DataFrame: {e}") from e
```

- **Positive**: Handles None and empty DataFrame gracefully with stats (0, 0, 0).
- **Concern**: `input_data.empty` is True for a DataFrame with columns but no rows. This is correct.
- **Concern**: The `pd.DataFrame(input_data)` conversion on non-DataFrame input may produce unexpected results for lists, dicts, or scalar values. For example, `pd.DataFrame("hello")` raises `ValueError`. A list of strings like `["hello", "world"]` creates a single-column DataFrame with column name 0. This may or may not work with the downstream column selection logic.

**Lines 149-160: Config extraction and pattern parsing**
```python
rows_in = len(input_data)
pattern = self.config.get('pattern', '')
die_on_error = self.config.get('die_on_error', False)
trim = self.config.get('trim', False)
try:
    field_widths = [int(width) for width in pattern.split(',')]
```

- **Concern**: `die_on_error` defaults to `False` but Talend default is `True` (ENG-EPF-005).
- Pattern parsing repeats the same logic as `_validate_config()`. Since `_validate_config()` runs at init time, this should always succeed. However, if config is mutated between init and execute (possible via context resolution), it could fail here.
- **Concern**: After context resolution, `self.config['pattern']` might be a resolved value that differs from what was validated at init time. For example, if pattern was `${context.pattern}` and context resolves to `"abc"`, the init validation may have passed (assuming the unresolved string looks like a valid pattern or was marked as `{{java}}`) but runtime parsing would fail.

**Lines 163-208: Row-by-row extraction loop**

```python
extracted_data = []
for _, row in input_data.iterrows():
    if 'line' in input_data.columns:
        line = row['line']
    elif len(input_data.columns) > 0:
        line = row.iloc[0]
    else:
        logger.error(f"[{self.id}] No data columns found in input DataFrame")
        continue
    if not isinstance(line, str):
        line = str(line)
    if line.startswith('\ufeff'):
        line = line[1:]
    if line.startswith('\xff\xfe'):
        line = line[2:]
    extracted_row = []
    current_pos = 0
    for idx, width in enumerate(field_widths):
        start_pos = current_pos
        end_pos = current_pos + width
        field_value = line[start_pos:end_pos] if len(line) > start_pos else ''
        if trim:
            field_value = field_value.strip()
        extracted_row.append(field_value)
        current_pos = end_pos
    extracted_data.append(extracted_row)
```

**Critical analysis of the extraction loop**:

1. **Source column selection (lines 166-172)**: The `'line' in input_data.columns` check is inside the for loop but is invariant -- it evaluates the same for every row. Should be hoisted outside (PERF-EPF-002). If neither `'line'` exists nor there are columns, the row is skipped with `continue` but no reject tracking occurs.

2. **NaN handling (line 176)**: `str(line)` converts:
   - `NaN` -> `"nan"` (3 chars)
   - `None` -> `"None"` (4 chars)
   - `float('inf')` -> `"inf"` (3 chars)
   - `123` (int) -> `"123"` (3 chars)
   - `True` (bool) -> `"True"` (4 chars)
   All of these produce valid strings that get sliced positionally, producing garbage output for all except the intended string type.

3. **BOM stripping (lines 179-182)**:
   - UTF-8 BOM (`\ufeff`) check: CORRECT for Python strings. UTF-8 BOM decodes to U+FEFF.
   - UTF-16 LE BOM (`\xff\xfe`) check: INCORRECT. By the time data is a Python string, the UTF-16 BOM bytes have been decoded. If the file was read as UTF-16, the BOM is either stripped by the decoder or appears as U+FEFF. The sequence U+00FF U+00FE would only appear if the raw bytes were incorrectly decoded as Latin-1.
   - **Also**: BOM stripping only applies to the first row's first field. If BOM is present, it shifts ALL fields in the first row. The current code strips BOM per-row, which handles the case where every row has BOM (unlikely). For the typical case (BOM only on first row), stripping should happen only once.

4. **Positional extraction (lines 190-204)**:
   - `field_value = line[start_pos:end_pos] if len(line) > start_pos else ''`: This correctly handles short lines. Python string slicing `line[5:10]` on a 7-char string returns `line[5:7]` (partial field). `line[10:15]` on a 7-char string returns `''` (empty).
   - **However**: The condition `len(line) > start_pos` is slightly wrong. If `len(line) == start_pos`, then `line[start_pos:end_pos]` returns `''` (empty string), which is the same as the else branch. So the condition should be `len(line) >= start_pos` for clarity, though the current code produces the correct result due to Python's slice behavior. Actually, `len(line) > start_pos` with `==` case going to else also returns `''`, so the behavior is correct either way. Not a bug, but slightly confusing.

5. **Trim (lines 198-199)**: `field_value.strip()` removes leading AND trailing whitespace. Talend's TRIM also strips whitespace. The Customize mode's Alignment feature (strip leading only, trailing only, or both) is not available here. `strip()` is equivalent to Center alignment in Customize mode.

6. **No error handling per row**: The entire extraction loop has no try/except. If any row causes an error (which is unlikely given the defensive coding, but possible with unusual data types), the exception propagates out of the loop and is caught by the outer try/except (line 232), which then fails ALL rows.

**Lines 210-230: Output DataFrame creation and stats**

```python
output_schema = getattr(self, 'output_schema', None) or []
if output_schema and len(output_schema) >= len(field_widths):
    column_names = [field['name'] for field in output_schema[:len(field_widths)]]
else:
    column_names = [f"field_{i+1}" for i in range(len(field_widths))]
output_df = pd.DataFrame(extracted_data, columns=column_names)
rows_out = len(output_df)
rows_rejected = 0
self._update_stats(rows_in, rows_out, rows_rejected)
return {'main': output_df, 'reject': pd.DataFrame()}
```

- `output_schema` is set by the engine from `comp_config.get('schema', {}).get('output', [])` (engine.py line 297). It is a list of dicts with `name`, `type`, `nullable`, etc.
- The `len(output_schema) >= len(field_widths)` check is defensive -- if schema has fewer columns than pattern fields, it falls back to `field_N` naming. In Talend, the schema MUST define all output columns, so this mismatch indicates a converter bug.
- **Concern**: `output_schema[:len(field_widths)]` truncates schema to match pattern length. If schema has MORE columns than pattern fields (e.g., schema defines 5 columns but pattern has 3 fields), only the first 3 schema names are used. The extra schema columns are ignored. In Talend, the number of output columns equals the number of pattern fields -- they must match.
- `rows_rejected = 0` is hardcoded. There is no mechanism to track per-row rejections.
- The `reject` output is always an empty DataFrame. No reject routing.

**Lines 232-239: Error handling**

```python
except Exception as e:
    logger.error(f"[{self.id}] Processing failed: {e}")
    if die_on_error:
        raise ComponentExecutionError(self.id, f"Error processing data: {e}", e) from e
    else:
        self._update_stats(rows_in, 0, rows_in)
        logger.warning(f"[{self.id}] Returning empty result due to error (die_on_error=False)")
        return {'main': pd.DataFrame(), 'reject': input_data}
```

- When `die_on_error=True`: Raises `ComponentExecutionError` with the original exception chained (`from e`). CORRECT.
- When `die_on_error=False`: Stats set to (rows_in, 0, rows_in) -- ALL rows counted as rejected. Returns entire input as reject. This is the all-or-nothing behavior noted in BUG-EPF-005.
- **Note**: This catch-all only fires for exceptions that escape the extraction loop. Since the loop has no per-row try/except, an exception at row 500 means rows 1-499 are lost (they were added to `extracted_data` but the DataFrame creation on line 220 never executed).

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows via Main, NB_LINE=0, NB_LINE_OK=0. No error. |
| **V1** | Line 135: `input_data.empty` is True. Returns `{'main': pd.DataFrame(), 'reject': pd.DataFrame()}` with stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: None input

| Aspect | Detail |
|--------|--------|
| **Talend** | Component requires input connection; None input not possible in standard Talend jobs. |
| **V1** | Line 135: `input_data is None` is True. Returns `{'main': pd.DataFrame(), 'reject': pd.DataFrame()}` with stats (0, 0, 0). |
| **Verdict** | CORRECT -- defensive handling for a case that should not occur in normal operation. |

### Edge Case 3: NaN source value

| Aspect | Detail |
|--------|--------|
| **Talend** | With `IGNORE_NULL=false` (default): null source generates output row with null values for all extracted fields. With `IGNORE_NULL=true`: row is silently skipped (no output row). |
| **V1** | `str(NaN)` -> `"nan"`. Pattern `"5,4,5"` slices `"nan"` into `["nan", "", ""]`. Then if `trim=True`, `"nan".strip()` -> `"nan"`. Output contains literal string `"nan"` in first field. |
| **Verdict** | **INCORRECT** -- produces garbage. Should produce null fields or skip row. |
| **Impact** | Data corruption in downstream components. A column that should be null or empty instead contains `"nan"`, which may fail numeric parsing, date parsing, or comparison operations downstream. |
| **Reproduction** | `pd.DataFrame({'line': ['HELLOWORLD', float('nan'), 'ABCDEFGHIJ']})` with pattern `"5,5"`. Second row produces `["nan", ""]` instead of `[None, None]` or being skipped. |

### Edge Case 4: Empty string source value

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty string `""` is NOT null. With pattern `"5,4,5"`, produces `["", "", ""]` (all empty fields). No error. |
| **V1** | `str("")` -> `""`. `len("")` is 0. For all fields, `len(line) > start_pos` is False (0 > 0 is False), so all fields are `""`. |
| **Verdict** | CORRECT -- but this means empty string and NaN produce different (both wrong for NaN) outputs. |

### Edge Case 5: Short input line (partial field)

| Aspect | Detail |
|--------|--------|
| **Talend** | Pattern `"5,4,5"` on input `"HELLO W"` (7 chars). Field 1: `"HELLO"` (chars 0-4). Field 2: `" W"` (chars 5-6, partial -- 2 of 4 chars). Field 3: `""` (chars 7-11, all beyond string end). No error unless `CHECK_FIELDS_NUM=true`. |
| **V1** | `line[0:5]` -> `"HELLO"`. `line[5:9]` -> `" W"` (Python slice returns available chars). `line[9:14]` -> `""` (beyond string, returns empty). |
| **Verdict** | CORRECT -- Python string slicing naturally handles partial fields. |

### Edge Case 6: Line exactly matches pattern width

| Aspect | Detail |
|--------|--------|
| **Talend** | Pattern `"5,4,5"` (total 14) on input `"HELLOWORK12345"` (14 chars). All fields fully populated. |
| **V1** | `line[0:5]` -> `"HELLO"`. `line[5:9]` -> `"WORK"`. `line[9:14]` -> `"12345"`. |
| **Verdict** | CORRECT |

### Edge Case 7: Line longer than pattern width

| Aspect | Detail |
|--------|--------|
| **Talend** | Pattern `"5,4,5"` (total 14) on input `"HELLOWORK12345EXTRA"` (19 chars). Trailing `"EXTRA"` is ignored. |
| **V1** | `line[0:5]` -> `"HELLO"`. `line[5:9]` -> `"WORK"`. `line[9:14]` -> `"12345"`. `current_pos` ends at 14 but no more fields are extracted. `"EXTRA"` is ignored. |
| **Verdict** | CORRECT |

### Edge Case 8: BOM in first row

| Aspect | Detail |
|--------|--------|
| **Talend** | If upstream component passes BOM character at start of first row, it shifts all field positions by 1 byte (UTF-8 BOM) or 2 bytes (UTF-16 BOM). Talend does not strip BOM in tExtractPositionalFields. |
| **V1** | UTF-8 BOM (`\uFEFF`) is stripped on line 179. UTF-16 LE BOM check on line 181 is incorrect (see BUG-EPF-006) but would be dead code anyway since UTF-16 BOM in a Python string would be `\uFEFF`. |
| **Verdict** | PARTIALLY CORRECT -- V1 strips UTF-8 BOM which Talend does NOT. This is actually BETTER than Talend behavior (BOM shifting positions is a common data issue). However, it means V1 and Talend produce different output for BOM-prefixed data. |

### Edge Case 9: Pattern with single field

| Aspect | Detail |
|--------|--------|
| **Talend** | Pattern `"10"` extracts one field of 10 characters. |
| **V1** | `pattern.split(',')` -> `['10']`. Single field extracted. Column named from schema or `field_1`. |
| **Verdict** | CORRECT |

### Edge Case 10: Pattern with many fields

| Aspect | Detail |
|--------|--------|
| **Talend** | Pattern `"1,1,1,1,1,1,1,1,1,1"` extracts 10 single-character fields. |
| **V1** | `pattern.split(',')` -> 10 entries. 10 fields extracted. |
| **Verdict** | CORRECT |

### Edge Case 11: Multi-byte Unicode characters

| Aspect | Detail |
|--------|--------|
| **Talend** | Java `String.substring()` operates on UTF-16 code units. For BMP characters (most Unicode), this is equivalent to character count. For supplementary characters (emoji, CJK extension B), one character = 2 UTF-16 code units, so position counting differs from character counting. |
| **V1** | Python string slicing operates on Unicode code points. `"cafE".slice(0, 4)` returns 4 characters regardless of their byte representation. For supplementary characters, Python treats them as single characters, while Java treats them as 2 code units. |
| **Verdict** | **MOSTLY CORRECT** but differs from Talend for supplementary characters (emoji, some CJK). For BMP characters (covers 99%+ of production data including Latin, Greek, Cyrillic, CJK ideographs), behavior is identical. |
| **Example** | Input: `"cafe\u0301"` (5 chars: c, a, f, e, combining accent). Pattern `"2,3"`. V1: field 1 = `"ca"`, field 2 = `"f\u0301"`. Talend: same result. Both treat combining characters as separate code units. |

### Edge Case 12: HYBRID streaming mode with positional extraction

| Aspect | Detail |
|--------|--------|
| **Behavior** | When input DataFrame > 3GB (MEMORY_THRESHOLD_MB = 3072), BaseComponent auto-selects STREAMING mode. |
| **V1 Flow** | `BaseComponent._execute_streaming()` calls `_create_chunks()` which yields DataFrame chunks of `chunk_size` rows (default 100,000). For each chunk, `_process()` is called. Each chunk is independently processed: source column selected, pattern parsed, rows extracted. |
| **Stats** | `_update_stats()` is called per chunk via `_process()`. Stats accumulate correctly: `self.stats['NB_LINE'] += rows_read` (line 308 of base_component.py). Total NB_LINE across all chunks = total input rows. |
| **Concern 1** | The extraction loop (`iterrows()`) runs per chunk, so the total Python-level iterations is still N (total rows). Chunking does not improve CPU performance, only memory usage. |
| **Concern 2** | BOM stripping runs per row per chunk. If BOM is only on the first row of the first chunk, it is correctly stripped. If BOM is NOT present on rows in subsequent chunks, no harm done (the `startswith` check returns False). |
| **Concern 3** | Column selection heuristic (`'line' in input_data.columns`) is evaluated per chunk, but since all chunks share the same column structure, this is redundant but harmless. |
| **Concern 4** | `BaseComponent._execute_streaming()` combines chunk results via `pd.concat(results, ignore_index=True)` (line 275). This creates the full output DataFrame in memory. For 3GB+ input with N output columns, the output may also be 3GB+, defeating the purpose of streaming. True streaming would require yielding output chunks to downstream components. |
| **Concern 5** | The `reject` output from `_process()` (always empty DataFrame) is NOT accumulated across chunks in `_execute_streaming()`. Only `main` is concatenated (line 271: `results.append(chunk_result['main'])`). If reject flow is later implemented per-row, the streaming mode would need to accumulate reject chunks too. |
| **Verdict** | FUNCTIONALLY CORRECT but memory benefits are limited since output is still materialized in full. Performance is identical to batch mode (same `iterrows()` loop). |

### Edge Case 13: `_update_global_map()` crash impact

| Aspect | Detail |
|--------|--------|
| **Bug** | `base_component.py` line 304: `logger.info(f"... {stat_name}: {value}")` references undefined `value` instead of `stat_value`. |
| **When it triggers** | After `_process()` completes successfully, `BaseComponent.execute()` calls `_update_global_map()` on line 218. If `self.global_map` is not None (which it is in normal engine operation), the for loop on line 301 iterates stats and hits the bad log line. |
| **Effect on ExtractPositionalFields** | The extraction succeeds, data is correctly extracted, but the `NameError` is raised from `_update_global_map()`. This exception propagates through `BaseComponent.execute()` (caught on line 227), sets `self.status = ComponentStatus.ERROR`, calls `_update_global_map()` AGAIN (line 231 in the except block), which crashes AGAIN with the same `NameError`. The second crash propagates up to the caller. |
| **Net result** | Even though `_process()` succeeded and produced correct output, the component reports failure. Stats are NOT written to globalMap. The extracted data is LOST because the exception prevents `execute()` from returning the result dict. |
| **Workaround** | Run without globalMap (`global_map=None`). The if-check on line 300 (`if self.global_map:`) skips the buggy code. But this means no stats are shared between components. |
| **Reproduction** | Any call to `ExtractPositionalFields.execute()` with a non-None `global_map` will crash after successful extraction. |

### Edge Case 14: Pattern parsing edge cases

| Input Pattern | Parsed Widths | Validation | Runtime | Notes |
|---------------|---------------|------------|---------|-------|
| `"5,4,5"` | `[5, 4, 5]` | Pass | OK | Normal case |
| `"5"` | `[5]` | Pass | OK | Single field |
| `" 5 , 4 , 5 "` | `[5, 4, 5]` | Pass | OK | Spaces stripped by `int(part.strip())` |
| `"5,,5"` | Error | Fail | N/A | `int('')` raises ValueError -> ConfigurationError at init |
| `"5,0,5"` | Error | Fail | N/A | `width <= 0` check -> ConfigurationError at init |
| `"5,-1,5"` | Error | Fail | N/A | `width <= 0` check -> ConfigurationError at init |
| `"5,4.5,5"` | Error | Fail | N/A | `int('4.5')` raises ValueError -> ConfigurationError at init |
| `"5,abc,5"` | Error | Fail | N/A | `int('abc')` raises ValueError -> ConfigurationError at init |
| `""` | Error | Fail | N/A | `self.config['pattern'].strip()` returns `""`, which is falsy -> ConfigurationError |
| `"999999"` | `[999999]` | Pass | OK | Extremely wide field. Source string is likely shorter; extraction returns partial/empty. No error. |
| `"1,1,1,...(1000 times)"` | `[1]*1000` | Pass | OK | Many fields. Extraction loop iterates 1000 times per row. Slow for large row counts. |
| `"5,4,5\n"` | `[5, 4, 5]` | Pass | OK | `strip()` removes trailing newline from last part: `int("5\n".strip())` -> 5 |
| `"5, 4, 5"` | `[5, 4, 5]` | Pass | OK | `int(" 4".strip())` -> 4 |

### Edge Case 15: Column naming when output_schema has different lengths

| Schema Length | Pattern Fields | Column Names | Notes |
|---------------|---------------|--------------|-------|
| 3 columns | 3 fields | Schema names | Normal case. `output_schema[:3]` gives 3 names. |
| 5 columns | 3 fields | Schema names (first 3) | `output_schema[:3]` truncates schema. Extra 2 schema columns unused. |
| 2 columns | 3 fields | `field_1, field_2, field_3` | `len(output_schema) < len(field_widths)` is True. Falls back to generic names. |
| 0 columns | 3 fields | `field_1, field_2, field_3` | Empty schema. Falls back to generic names. |
| None | 3 fields | `field_1, field_2, field_3` | `getattr(self, 'output_schema', None) or []` -> `[]`. Falls back. |

**Concern**: In Talend, schema column count MUST match pattern field count. A mismatch means the converter produced inconsistent output. The engine silently handles this with fallback naming, which hides the bug.

---

## Appendix G: Base Class Interaction Analysis

### BaseComponent.execute() Flow for ExtractPositionalFields

```
1. ExtractPositionalFields.execute(input_data) called
2.   Logs input shape/columns at INFO level
3.   Calls super().execute(input_data) -> BaseComponent.execute()
4.     Sets status = RUNNING, records start_time
5.     Step 1: Resolve Java expressions ({{java}} markers)
6.       - Scans self.config recursively for {{java}} prefix strings
7.       - Due to config pollution, may find {{java}} markers on BOTH
8.         uppercase raw params AND lowercase mapped params
9.       - If java_bridge is None (common), logs warning and continues
10.      - If java_bridge exists, syncs context + globalMap to Java, executes batch
11.    Step 2: Resolve context variables (${context.var})
12.      - context_manager.resolve_dict(self.config) resolves all ${...} markers
13.      - This mutates self.config IN PLACE
14.      - After resolution, config contains resolved values for both raw + mapped params
15.    Step 3: Determine execution mode
16.      - HYBRID mode: auto-selects based on input size
17.      - If input_data is DataFrame and memory > 3GB: STREAMING
18.      - Otherwise: BATCH
19.    Step 4: Execute based on mode
20.      - BATCH: calls self._process(input_data) -> ExtractPositionalFields._process()
21.      - STREAMING: calls self._execute_streaming(input_data)
22.        - Creates chunks of chunk_size rows
23.        - For each chunk, calls self._process(chunk)
24.        - Concatenates results
25.    Step 5: Update stats and globalMap
26.      - self.stats['EXECUTION_TIME'] = elapsed
27.      - self._update_global_map() -- **CRASHES** with NameError (BUG-EPF-001)
28.    Step 6: Set status = SUCCESS
29.    Step 7: Add stats to result dict
30.    Step 8: Return result
31.  On exception:
32.    Sets status = ERROR
33.    Calls _update_global_map() -- **CRASHES AGAIN** (BUG-EPF-001)
34.    Logs error and re-raises
```

### Impact of Config Pollution on Java Expression Resolution

Because `parse_base_component()` populates `component['config']` with ALL raw Talend parameters (uppercase), and the dedicated parser adds lowercase mapped versions, the config at runtime may look like:

```python
{
    # Raw Talend params from parse_base_component() -> _map_component_parameters() fallthrough
    'PATTERN': '5,4,5',           # Raw string (may have {{java}} marker)
    'DIE_ON_ERROR': True,          # Converted to bool by CHECK field handler
    'TRIM': False,                 # Converted to bool by CHECK field handler
    'ADVANCED_SEPARATOR': False,   # Converted to bool by CHECK field handler
    'THOUSANDS_SEPARATOR': ',',    # Raw string
    'DECIMAL_SEPARATOR': '.',      # Raw string
    'UNIQUE_NAME': 'tExtractPositionalFields_1',  # Raw param, filtered out
    'PROPERTY_TYPE': 'BUILT_IN',   # Raw param, not needed
    'LABEL': '',                   # Raw param, not needed
    # ... potentially many more raw Talend params ...

    # Mapped params from parse_textract_positional_fields()
    'pattern': '5,4,5',           # Clean string (no {{java}} marker)
    'die_on_error': True,          # Boolean
    'trim': False,                 # Boolean
    'advanced_separator': False,   # Boolean
    'thousands_separator': ',',    # String
    'decimal_separator': '.',      # String
}
```

When `_resolve_java_expressions()` scans this config, it may find `{{java}}` markers on the UPPERCASE raw params that were NOT overwritten by the dedicated parser. This could cause:
- Duplicate Java expression resolution (same expression resolved twice under different keys)
- Errors if the Java bridge cannot resolve an expression that was intended to be overridden

When `context_manager.resolve_dict()` scans this config, it resolves `${context.var}` in ALL values, including raw uppercase params. This is wasteful but not harmful since the engine only reads lowercase keys.

### validate_schema() Integration

`BaseComponent.validate_schema()` is NOT called by the extraction component. The `_process()` method returns `output_df` directly without schema validation. This means:
- Output column types are always `object` (string) -- no type conversion to int, float, date, etc.
- Even if output_schema defines columns as `id_Integer`, the output DataFrame contains strings.
- Downstream components must handle type conversion themselves, or the engine must call `validate_schema()` externally.

Compare with `FileInputDelimited._read_batch()` (line 411) which calls `self.validate_schema(output_df, self.output_schema)` before returning. ExtractPositionalFields lacks this call.

---

## Appendix H: Converter Flow Deep Dive

### Full Converter Pipeline for tExtractPositionalFields

```
1. converter.py:_parse_component(node)
2.   Gets component_type = 'tExtractPositionalFields'
3.   Calls component_parser.parse_base_component(node) [line 226]
4.     a. Extracts UNIQUE_NAME -> component['id']
5.     b. Maps component type via component_mapping dict
6.     c. Initializes component dict with empty config, schema, inputs, outputs
7.     d. Since 'tExtractPositionalFields' NOT in components_with_dedicated_parsers:
8.        - Iterates ALL elementParameter nodes from XML
9.        - For each param: extracts name, value, field type
10.       - Strips quotes from value
11.       - Converts CHECK fields to boolean (DIE_ON_ERROR, TRIM, ADVANCED_SEPARATOR become True/False)
12.       - Checks for context variable references in string values
13.       - Stores in config_raw dict
14.       - Marks Java expressions via mark_java_expression() on all non-CODE/IMPORT/UNIQUE_NAME values
15.     e. Calls _map_component_parameters('tExtractPositionalFields', config_raw)
16.       - No match for 'tExtractPositionalFields' in if/elif chain
17.       - Falls through to `else: return config_raw` [line 386]
18.       - component['config'] = config_raw (ALL raw Talend params, with {{java}} markers)
19.     f. Extracts metadata schemas generically (FLOW, REJECT)
20.       - Column name, type (converted to Python), nullable, key, length, precision, pattern
21.       - Stored in component['schema']['output'] and component['schema']['reject']
22.     g. Returns component
23.
24.   Now converter.py has component with populated config (raw Talend params) and schema
25.
26.   elif component_type == 'tExtractPositionalFields': [line 325]
27.     Calls component_parser.parse_textract_positional_fields(node, component) [line 326]
28.       a. Re-reads ALL elementParameter nodes from XML (separate traversal)
29.       b. For name == 'PATTERN': sets component['config']['pattern'] = value.strip('"')
30.       c. For name == 'DIE_ON_ERROR': sets component['config']['die_on_error'] = bool
31.       d. For name == 'TRIM': sets component['config']['trim'] = bool
32.       e. For name == 'ADVANCED_SEPARATOR': sets component['config']['advanced_separator'] = bool
33.       f. For name == 'THOUSANDS_SEPARATOR': sets component['config']['thousands_separator'] = value
34.       g. For name == 'DECIMAL_SEPARATOR': sets component['config']['decimal_separator'] = value
35.       h. Returns component with both raw + mapped params in config
36.
37.   Returns component to engine
```

**Key observation**: The dedicated parser on step 28 uses `.//elementParameter` (descendant-or-self axis) while `parse_base_component()` step 8 uses `.//elementParameter` (same axis). Both traverse the same nodes but the dedicated parser does a SECOND traversal of the XML tree, which is wasteful. The dedicated parser could instead read from `component['config']` (the already-extracted raw values) to avoid re-parsing XML.

**Expression handling gap**: In step 14, `mark_java_expression()` may mark the `PATTERN` value with `{{java}}` if it contains operators or method calls. For example, `"5,4,5"` contains commas, but commas are not typically flagged as Java expressions. However, a pattern like `context.widths` or `routines.MyRoutine.getPattern()` would be marked as `{{java}}context.widths` or `{{java}}routines.MyRoutine.getPattern()`. In step 29, the dedicated parser overwrites this with the un-marked raw value `context.widths`, breaking Java expression resolution.

---

## Appendix I: Comparison with tFileInputPositional

`tFileInputPositional` is the FILE-LEVEL equivalent of `tExtractPositionalFields`. It reads a positional file directly from disk, while `tExtractPositionalFields` operates on in-memory data from an upstream component.

| Aspect | tFileInputPositional | tExtractPositionalFields | Notes |
|--------|---------------------|-------------------------|-------|
| **Source** | File on disk (FILENAME) | Column in upstream DataFrame (FIELD) | Different input sources |
| **Converter mapping** | Dedicated in `_map_component_parameters()` (lines 150-171) | Falls through + dedicated parser | FIP has more params extracted |
| **PATTERN extracted?** | Yes (`pattern`) | Yes (`pattern`) | Same |
| **FIELD extracted?** | N/A (reads from file) | **No** | EPF needs FIELD |
| **ADVANCED_SEPARATOR** | Yes | Yes | Same |
| **THOUSANDS_SEPARATOR** | Yes | Yes | Same |
| **DECIMAL_SEPARATOR** | Yes | Yes | Same |
| **CHECK_DATE** | Yes (`check_date`) | **No** | EPF could benefit |
| **UNCOMPRESS** | Yes (`uncompress`) | N/A (in-memory) | N/A |
| **REMOVE_EMPTY_ROW** | Yes (`remove_empty_row`) | **No** | EPF could benefit |
| **HEADER/FOOTER** | Yes | N/A (no file) | N/A |
| **LIMIT** | Yes | **No** | EPF could benefit for large datasets |
| **PROCESS_LONG_ROW** | Yes (`process_long_row`) | **No** | Talend-specific behavior |
| **Config pollution** | No (has dedicated mapping) | **Yes** (falls through) | EPF worse |
| **Engine implementation** | Separate file reading component | In-memory extraction only | Different components |

The converter for `tFileInputPositional` extracts 17 parameters (lines 150-171). The converter for `tExtractPositionalFields` extracts 6 parameters (lines 2037-2058). This disparity suggests the positional fields parser was written quickly without referencing the more mature positional input parser.

---

## Appendix J: Recommended Converter Parser Rewrite

The current `parse_textract_positional_fields()` should be rewritten to:
1. Extract ALL missing parameters (FIELD, IGNORE_NULL, CUSTOMIZE, CHECK_FIELDS_NUM)
2. Handle the CUSTOMIZE table parameter (nested elementValue groups)
3. Include its own schema extraction loop (like `parse_textract_regex_fields()`)
4. Avoid config pollution by either adding to `_map_component_parameters()` or to `components_with_dedicated_parsers`

```python
# Recommended rewrite for parse_textract_positional_fields()
def parse_textract_positional_fields(self, node, component):
    """
    Parse tExtractPositionalFields component from Talend XML.

    Extracts: FIELD, PATTERN, DIE_ON_ERROR, IGNORE_NULL, TRIM,
    ADVANCED_SEPARATOR, THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR,
    CUSTOMIZE (table), CHECK_FIELDS_NUM
    """
    config = component['config']

    # Clear raw params from generic fallthrough to avoid pollution
    raw_keys = list(config.keys())
    for key in raw_keys:
        if key.isupper():
            del config[key]

    # Extract parameters
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '').strip('"')

        if name == 'FIELD':
            config['field'] = value
        elif name == 'PATTERN':
            config['pattern'] = value
        elif name == 'DIE_ON_ERROR':
            config['die_on_error'] = value.lower() == 'true'
        elif name == 'IGNORE_NULL':
            config['ignore_null'] = value.lower() == 'true'
        elif name == 'TRIM':
            config['trim'] = value.lower() == 'true'
        elif name == 'ADVANCED_SEPARATOR':
            config['advanced_separator'] = value.lower() == 'true'
        elif name == 'THOUSANDS_SEPARATOR':
            config['thousands_separator'] = value
        elif name == 'DECIMAL_SEPARATOR':
            config['decimal_separator'] = value
        elif name == 'CUSTOMIZE':
            config['customize'] = value.lower() == 'true'
        elif name == 'CHECK_FIELDS_NUM':
            config['check_fields_num'] = value.lower() == 'true'

    # Extract CUSTOMIZE table if enabled
    if config.get('customize', False):
        customize_entries = []
        for table_param in node.findall('.//elementParameter[@name="CUSTOMIZE_TABLE"]'):
            elements = list(table_param.findall('.//elementValue'))
            # Each entry has: COLUMN, SIZE, PADDING_CHAR, ALIGNMENT
            for i in range(0, len(elements), 4):
                entry = {}
                for j in range(4):
                    if i + j < len(elements):
                        elem = elements[i + j]
                        ref = elem.get('elementRef', '')
                        val = elem.get('value', '').strip('"')
                        if ref == 'COLUMN':
                            entry['column'] = val
                        elif ref == 'SIZE':
                            entry['size'] = int(val) if val.isdigit() else 0
                        elif ref == 'PADDING_CHAR':
                            entry['padding_char'] = val if val else ' '
                        elif ref == 'ALIGNMENT':
                            entry['alignment'] = val if val else 'Left'
                if entry:
                    customize_entries.append(entry)
        config['customize_table'] = customize_entries

    # Extract metadata schemas
    for metadata in node.findall('.//metadata'):
        connector = metadata.get('connector', 'FLOW')
        schema_cols = []
        for column in metadata.findall('.//column'):
            col_info = {
                'name': column.get('name', ''),
                'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
                'nullable': column.get('nullable', 'true').lower() == 'true',
                'key': column.get('key', 'false').lower() == 'true'
            }
            if column.get('length'):
                col_info['length'] = int(column.get('length'))
            if column.get('precision'):
                col_info['precision'] = int(column.get('precision'))
            if column.get('pattern'):
                pattern = column.get('pattern').strip('"')
                if pattern:
                    pattern = pattern.replace('yyyy', '%Y').replace('MM', '%m').replace('dd', '%d')
                    pattern = pattern.replace('HH', '%H').replace('mm', '%M').replace('ss', '%S')
                    col_info['date_pattern'] = pattern
            schema_cols.append(col_info)
        if connector == 'FLOW':
            component['schema']['output'] = schema_cols
        elif connector == 'REJECT':
            component['schema']['reject'] = schema_cols

    return component
```

---

## Appendix K: Recommended Engine _process() Rewrite (Vectorized)

The current `iterrows()` implementation should be replaced with vectorized pandas operations for performance:

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Process input data by extracting positional fields (vectorized)."""
    # Handle empty input
    if input_data is None or input_data.empty:
        logger.warning(f"[{self.id}] Empty input received")
        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

    # Ensure DataFrame
    if not isinstance(input_data, pd.DataFrame):
        try:
            input_data = pd.DataFrame(input_data)
        except Exception as e:
            raise DataValidationError(f"Cannot convert input to DataFrame: {e}") from e

    rows_in = len(input_data)
    pattern = self.config.get('pattern', '')
    die_on_error = self.config.get('die_on_error', True)  # Match Talend default
    trim = self.config.get('trim', False)
    field_name = self.config.get('field')  # From FIELD parameter
    ignore_null = self.config.get('ignore_null', False)

    try:
        field_widths = [int(w) for w in pattern.split(',')]

        # Select source column
        if field_name and field_name in input_data.columns:
            source_col = input_data[field_name]
        elif 'line' in input_data.columns:
            source_col = input_data['line']
        elif len(input_data.columns) > 0:
            source_col = input_data.iloc[:, 0]
        else:
            raise DataValidationError("No data columns in input DataFrame")

        # Handle nulls
        null_mask = source_col.isna()
        if ignore_null:
            # Skip null rows entirely
            source_col = source_col[~null_mask]
        else:
            # Replace nulls with empty string (produces null-like output)
            source_col = source_col.fillna('')

        # Convert to string
        source_str = source_col.astype(str)

        # Strip BOM from first row if present
        if len(source_str) > 0:
            first_val = source_str.iloc[0]
            if first_val.startswith('\ufeff'):
                source_str.iloc[0] = first_val[1:]

        # Get column names
        output_schema = getattr(self, 'output_schema', None) or []
        if output_schema and len(output_schema) >= len(field_widths):
            col_names = [f['name'] for f in output_schema[:len(field_widths)]]
        else:
            col_names = [f"field_{i+1}" for i in range(len(field_widths))]

        # Vectorized extraction
        output_df = pd.DataFrame(index=source_str.index)
        current_pos = 0
        for idx, width in enumerate(field_widths):
            output_df[col_names[idx]] = source_str.str.slice(current_pos, current_pos + width)
            if trim:
                output_df[col_names[idx]] = output_df[col_names[idx]].str.strip()
            current_pos += width

        output_df = output_df.reset_index(drop=True)
        rows_out = len(output_df)
        rows_rejected = rows_in - rows_out if ignore_null else 0

        self._update_stats(rows_in, rows_out, rows_rejected)
        return {'main': output_df, 'reject': pd.DataFrame()}

    except Exception as e:
        logger.error(f"[{self.id}] Processing failed: {e}")
        if die_on_error:
            raise ComponentExecutionError(self.id, f"Error: {e}", e) from e
        else:
            self._update_stats(rows_in, 0, rows_in)
            return {'main': pd.DataFrame(), 'reject': input_data}
```

**Key improvements**:
1. Uses `str.slice()` instead of `iterrows()` -- 10-100x faster
2. Supports `field` config for source column selection
3. Handles NaN with `ignore_null` flag
4. BOM stripping only on first row
5. `die_on_error` default changed to `True` to match Talend
6. Proper null masking and reject counting

---

## Appendix L: Runtime Execution Trace (Successful Case)

For a complete understanding of the execution flow, here is a trace of a successful extraction with the current code:

```
Input:
  DataFrame with 3 rows, 1 column named "line":
    row 0: "JOHNDoe 12345"
    row 1: "JANE   67890"
    row 2: "BOB    00001"
  Config: {"pattern": "4,4,5", "trim": true}
  Output schema: [{"name": "first"}, {"name": "last"}, {"name": "code"}]

Execution:

1. ExtractPositionalFields.execute(input_data)
   INFO: [comp_1] ===== EXECUTE CALLED =====
   INFO: [comp_1] Input data type: <class 'pandas.core.frame.DataFrame'>
   INFO: [comp_1] Input data shape: (3, 1)
   INFO: [comp_1] Input data columns: ['line']

2. BaseComponent.execute(input_data)
   Status -> RUNNING
   Java expressions: none found (no {{java}} markers in lowercase config keys)
   Context variables: none found (no ${...} markers)
   Mode determination: BATCH (3 rows << 3GB threshold)
   Calls _process(input_data)

3. ExtractPositionalFields._process(input_data)
   rows_in = 3
   pattern = "4,4,5"
   die_on_error = False (engine default, differs from Talend True)
   trim = True
   field_widths = [4, 4, 5]

4. Row 0: "JOHNDoe 12345"
   'line' in columns -> True
   line = "JOHNDoe 12345"
   isinstance(str) -> True, no str() conversion
   BOM check: no BOM
   Field 0: line[0:4] = "JOHN", strip -> "JOHN"
   Field 1: line[4:8] = "Doe ", strip -> "Doe"
   Field 2: line[8:13] = "12345", strip -> "12345"
   extracted_row = ["JOHN", "Doe", "12345"]

5. Row 1: "JANE   67890"
   line = "JANE   67890" (12 chars, pattern needs 13)
   Field 0: line[0:4] = "JANE", strip -> "JANE"
   Field 1: line[4:8] = "   6", strip -> "6"
   Field 2: line[8:13] = "7890" (partial: only 4 chars, not 5), strip -> "7890"
   extracted_row = ["JANE", "6", "7890"]

6. Row 2: "BOB    00001"
   line = "BOB    00001" (12 chars)
   Field 0: line[0:4] = "BOB ", strip -> "BOB"
   Field 1: line[4:8] = "   0", strip -> "0"
   Field 2: line[8:13] = "0001" (partial), strip -> "0001"
   extracted_row = ["BOB", "0", "0001"]

7. Output DataFrame creation:
   output_schema has 3 columns >= 3 field_widths
   column_names = ["first", "last", "code"]
   output_df:
     first | last | code
     JOHN  | Doe  | 12345
     JANE  | 6    | 7890
     BOB   | 0    | 0001

8. Stats: _update_stats(3, 3, 0)
   NB_LINE = 3, NB_LINE_OK = 3, NB_LINE_REJECT = 0

9. Return {'main': output_df, 'reject': pd.DataFrame()}

10. Back in BaseComponent.execute():
    EXECUTION_TIME = elapsed
    _update_global_map() -> **CRASHES** with NameError (BUG-EPF-001)

    Exception handler:
      Status -> ERROR
      _update_global_map() -> **CRASHES AGAIN**
      Logs error, re-raises NameError

    Result: Component fails even though extraction was correct.
    Output data is LOST.
```

---

## Appendix M: Runtime Execution Trace (NaN Input Case)

```
Input:
  DataFrame with 3 rows, 1 column named "line":
    row 0: "HELLO12345"
    row 1: NaN (pandas float NaN)
    row 2: "WORLD67890"
  Config: {"pattern": "5,5"}

Execution (in _process):

1. rows_in = 3

2. Row 0: "HELLO12345"
   line = "HELLO12345"
   isinstance(str) -> True
   Field 0: line[0:5] = "HELLO"
   Field 1: line[5:10] = "12345"
   extracted_row = ["HELLO", "12345"]

3. Row 1: NaN
   line = NaN (float)
   isinstance(str) -> False
   line = str(NaN) -> "nan"  <-- BUG: should be None or skip
   BOM check: "nan" does not start with BOM
   Field 0: "nan"[0:5] = "nan" (3 chars, padded to nothing extra)
   Field 1: "nan"[5:10] = "" (beyond string length)
   extracted_row = ["nan", ""]  <-- GARBAGE DATA

4. Row 2: "WORLD67890"
   line = "WORLD67890"
   Field 0: line[0:5] = "WORLD"
   Field 1: line[5:10] = "67890"
   extracted_row = ["WORLD", "67890"]

5. Output:
   field_1 | field_2
   HELLO   | 12345
   nan     | ""       <-- CORRUPTED ROW
   WORLD   | 67890

6. Stats: _update_stats(3, 3, 0)
   NB_LINE_REJECT = 0 even though row 1 is corrupted
```

**Impact**: Downstream components receiving `"nan"` as a string value may:
- Fail numeric conversion (e.g., `int("nan")` raises ValueError)
- Pass it through as a valid string (corrupting data)
- Match it against null checks that look for the literal string "nan" (pandas `pd.isna("nan")` returns False)
- Cause confusion in aggregations, joins, or filters

---

## Appendix N: Comparison with Gold Standard (tFileInputDelimited Audit)

| Audit Section | tFileInputDelimited (Gold Standard) | tExtractPositionalFields (This Audit) | Notes |
|---------------|--------------------------------------|---------------------------------------|-------|
| Component Identity | Complete with all key files | Complete with all key files | Parity |
| Scorecard | 5 dimensions, R/Y/G scoring | 5 dimensions, R/Y/G scoring | Parity |
| Talend Feature Baseline | 31 parameters, 5 connection types, 4+ globalMap vars, 13 behavioral notes | 12 parameters, 8 connection types, 4 globalMap vars, 10 behavioral notes | EPF has fewer params (simpler component) |
| Converter Audit | 30-param extraction table, schema extraction, expression handling, 10 issues | 12-param extraction table, schema extraction, expression handling, 7 issues | Proportional to complexity |
| Engine Feature Parity | 34-feature table, 10 behavioral diffs, globalMap coverage | 17-feature table, 10 behavioral diffs, globalMap coverage | Parity in structure |
| Code Quality | 7 bugs, naming, standards, debug, security, logging, error handling, type hints | 7 bugs, naming, standards, debug, security, logging, error handling, type hints | Parity in structure |
| Performance & Memory | 3 issues, memory assessment, streaming limitations | 3 issues, memory assessment, streaming limitations | Parity |
| Testing | 0 tests, 27 recommended test cases | 0 tests, 23 recommended test cases | Parity |
| Issues Summary | 40 total (3 P0, 13 P1, 17 P2, 7 P3) | 33 total (3 P0, 12 P1, 13 P2, 5 P3) | EPF has fewer issues (simpler component) |
| Recommendations | 20 items in 3 tiers | 17 items in 3 tiers | Parity |
| Appendices | 6 appendices (A-F) | 14 appendices (A-N) | EPF has more detailed analysis |

**Key shared P0 issues**: Both audits identify the SAME two cross-cutting P0 bugs (BUG-*-001 and BUG-*-002 in `base_component.py` and `global_map.py`). These affect ALL v1 engine components and should be fixed once. Both also identify zero tests as P0.

**Key difference**: `tFileInputDelimited` has a P0 bug for missing REJECT flow (fundamental gap for a file input component). `tExtractPositionalFields` has the missing REJECT flow as P1 (less critical for a transform component that can be preceded by null-checking logic).

---

## Appendix O: Glossary

| Term | Definition |
|------|------------|
| **BOM** | Byte Order Mark. A Unicode character (U+FEFF) placed at the beginning of a file to indicate byte order and encoding. UTF-8 BOM is `EF BB BF` (3 bytes). UTF-16 LE BOM is `FF FE` (2 bytes). |
| **config pollution** | The presence of both raw Talend parameter names (uppercase, e.g., `PATTERN`) and mapped v1 parameter names (lowercase, e.g., `pattern`) in the same config dictionary, creating redundant and potentially conflicting entries. |
| **cross-cutting bug** | A bug in shared infrastructure (e.g., `BaseComponent`, `GlobalMap`) that affects ALL components using that infrastructure, not just the component being audited. |
| **dead code** | Code that exists in the source but can never be executed because it is unreachable through any code path. Example: a validation method that is never called. |
| **globalMap** | Talend's shared key-value store for passing variables between components and tracking execution statistics. In v1, implemented by `GlobalMap` class. |
| **HYBRID mode** | The default execution mode in BaseComponent. Automatically selects BATCH or STREAMING based on input data size. Threshold: 3072 MB. |
| **iterrows()** | A pandas DataFrame method that iterates over rows as (index, Series) pairs. Known to be slow (Python-level loop) compared to vectorized operations. |
| **positional extraction** | Extracting fields from a fixed-width string by character positions rather than delimiters. Each field occupies a fixed number of characters. |
| **REJECT flow** | Talend's mechanism for routing rows that fail processing to a separate output. REJECT rows include `errorCode` and `errorMessage` columns. |
| **vectorized operation** | A pandas operation that processes all rows simultaneously using optimized C code, rather than iterating row-by-row in Python. Typically 10-100x faster than `iterrows()`. |
| **{{java}} marker** | A prefix added by the converter to config values that contain Java expressions. The engine's `_resolve_java_expressions()` detects this prefix and resolves the expression via the Java bridge. |
| **${context.var}** | A context variable reference that is resolved by the ContextManager before component execution. The ContextManager replaces `${context.var}` with the actual variable value from the context. |
