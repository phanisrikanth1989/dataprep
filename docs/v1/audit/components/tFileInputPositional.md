# Audit Report: tFileInputPositional / FileInputPositional

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputPositional` |
| **V1 Engine Class** | `FileInputPositional` |
| **Engine File** | `src/v1/engine/components/file/file_input_positional.py` (359 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 150-171) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Registry Aliases** | `FileInputPositional`, `tFileInputPositional` (registered in `src/v1/engine/engine.py` lines 62-63) |
| **Category** | File / Input (Positional) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_positional.py` | Engine implementation (359 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 150-171) | Parameter mapping from Talend XML to v1 JSON via `_map_component_parameters()` |
| `src/converters/complex_converter/converter.py` | Dispatch -- no dedicated `elif` for `tFileInputPositional`; uses generic `parse_base_component()` path |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`, `ComponentExecutionError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (`FileInputPositional` on line 8) |
| `src/converters/complex_converter/expression_converter.py` (line 231) | `convert_type()` -- Talend->Python type conversion used during schema extraction |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 3 | 1 | 16 of 23 Talend params extracted (70%); dedicated `_map_component_parameters()` branch exists but missing `CUSTOMIZE`, `USE_BYTE_LENGTH`, per-column padding |
| Engine Feature Parity | **Y** | 0 | 5 | 3 | 2 | No REJECT flow; no compressed file reading; no `{id}_ERROR_MESSAGE` globalMap; no streaming mode for positional files; no per-column customize/padding |
| Code Quality | **R** | 2 | 6 | 6 | 2 | Cross-cutting base class bugs; dead `_validate_config()`; `id_Boolean` mapped to `object`; advanced separator applied to ALL object columns; `check_date` ignores schema date pattern; `remove_empty_row` doesn't catch blank-but-not-NaN rows; `skipfooter`+`nrows` interaction wrong; UTF-8 BOM corrupts first field |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | No streaming mode (batch only); post-processing iterates string columns twice; BigDecimal uses slow `apply()` |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready without P0/P1 fixes (42 total issues, 13 at P1)**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputPositional Does

`tFileInputPositional` reads a fixed-width (positional) file row by row, splits each row into fields based on a given pattern of column widths, and outputs the parsed fields as defined in the output schema to downstream components via a Row link. Unlike delimited files where separators mark field boundaries, positional files define field boundaries by character positions -- each column occupies a fixed number of characters in every row, with optional padding characters (typically spaces).

**Source**: [tFileInputPositional Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/positional/tfileinputpositional-standard-properties), [tFileInputPositional Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/positional/tfileinputpositional-standard-properties), [tFileInputPositional (Talend Skill 5.x)](https://talendskill.com/talend-for-esb-docs/docs-5-x/tfileinputpositional-docs-for-esb-5-x/)

**Component family**: Positional (File / Input)
**Available in**: All Talend products. Standard, MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. |
| 3 | Use existing dynamic | -- | Boolean (CHECK) | `false` | Reuse an existing dynamic schema to handle data from unknown columns. Leverages `tSetDynamicSchema`. |
| 4 | File Name / Stream | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path or data stream variable. Supports context variables, globalMap references, Java expressions. |
| 5 | Row Separator | `ROWSEPARATOR` | String | Carriage return (`"\n"`) | Character(s) identifying the end of a row. Supports `\r\n`, `\n`, `\r`. |
| 6 | Use byte length as cardinality | `USE_BYTE_LENGTH` | Boolean (CHECK) | `false` | Enable support for double-byte characters (e.g., CJK). Requires JDK 1.6+. When enabled, pattern widths are measured in bytes rather than characters. |
| 7 | Customize | `CUSTOMIZE` | Boolean (CHECK) | `false` | Enable per-column customization for padding character and alignment. See Section 3.5. |
| 8 | Pattern | `PATTERN` | String | -- | **Mandatory**. Comma-separated field width values defining the positional layout (e.g., `"5,4,5"`). Length values correspond to the number of characters (or bytes, if `USE_BYTE_LENGTH=true`) for each field. |
| 9 | Pattern Units | `PATTERN_UNITS` | Enum | `Bytes` | Unit of measurement for pattern widths: `Bytes`, `Symbols`, or `Symbols (including rare)`. Controls how multi-byte characters are counted. |
| 10 | Skip Empty Rows | `REMOVE_EMPTY_ROW` | Boolean (CHECK) | `false` | Skip rows where all fields are empty/blank after splitting. |
| 11 | Uncompress as zip file | `UNCOMPRESS` | Boolean (CHECK) | `false` | Transparently decompress ZIP compressed input files before parsing. |
| 12 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Stop the entire job on read/parse error. When unchecked, malformed rows are routed to the REJECT flow (if connected) or silently dropped. **Note**: Talend default is `true` for this component. |
| 13 | Header | `HEADER` | Integer | `0` | Number of rows to skip at the beginning of the file. These rows are completely discarded -- NOT used for column naming (schema defines column names). |
| 14 | Footer | `FOOTER` | Integer | `0` | Number of rows to skip at the end of the file. Requires reading the entire file to determine the last N rows. |
| 15 | Limit | `LIMIT` | Integer | `0` | Maximum number of rows to read. `0` = unlimited (read all rows). Applies after header skip. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 16 | Needed to process rows longer than 100,000 characters | `PROCESS_LONG_ROW` | Boolean (CHECK) | `false` | Enable handling of very long rows exceeding the default 100,000-character buffer. |
| 17 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands and decimal separators. |
| 18 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 19 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 20 | Trim All Columns | `TRIMALL` | Boolean (CHECK) | `false` | Remove leading and trailing whitespace from ALL string fields. Critical for positional files where fields are padded to fixed width. |
| 21 | Validate Date | `CHECK_DATE` | Boolean (CHECK) | `false` | Strictly validate date-typed columns against the date pattern defined in the input schema. Invalid dates cause row rejection (routed to REJECT). |
| 22 | Encoding | `ENCODING` | Dropdown / Custom | (JVM-dependent) | Character encoding for file reading. Options include ISO-8859-15, UTF-8, and custom values. |
| 23 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Customize Sub-Parameters

When `CUSTOMIZE=true`, per-column settings become available:

| # | Sub-Parameter | Type | Default | Description |
|---|---------------|------|---------|-------------|
| C1 | Column | Schema column name | -- | Specific field for customization. |
| C2 | Size | Integer | Pattern-derived | Column width override (can differ from pattern width). |
| C3 | Padding char | Character | Space `' '` | Padding character to strip from field values. For positional files, fields are typically right-padded with spaces. This defines which character to remove. |
| C4 | Alignment | Enum (Left/Right/Center) | Left | Alignment of actual data within the fixed-width field. Determines from which side padding is stripped. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully parsed rows matching the output schema. All columns defined in the schema are present. Primary data output. |
| `REJECT` | Output | Row > Reject | Rows that failed parsing, type conversion, or structural validation. Includes ALL original schema columns PLUS `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false`. "Filter the data which does not correspond to the type defined." |
| `ITERATE` | Output | Iterate | Enables iterative processing when the component is used with iteration components like `tFlowToIterate`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed (data rows, after header skip, before REJECT filtering). Primary row count variable. |
| `{id}_ERROR_MESSAGE` | String | On error | Error description when failure occurs. Only available when `Die on error` is unchecked. |

**Note on NB_LINE**: The `NB_LINE` global variable is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow -- only in subsequent subjobs connected via triggers.

### 3.6 Behavioral Notes

1. **PATTERN behavior**: The pattern defines fixed column widths as a comma-separated string (e.g., `"5,4,5"` means 3 columns of widths 5, 4, and 5 characters respectively). The sum of all widths should equal the total line length minus the row separator. If the sum exceeds the line length, the last column is truncated. If the sum is less, trailing characters are discarded.

2. **PATTERN_UNITS behavior**: When set to `Bytes`, multi-byte characters (CJK, accented chars in UTF-8) are counted by byte length. When set to `Symbols`, each character counts as 1 regardless of byte representation. `Symbols (including rare)` handles Unicode supplementary characters (surrogate pairs) as single symbols.

3. **CUSTOMIZE behavior**: Per-column padding/alignment settings allow stripping field-specific padding. Positional files commonly right-pad text fields with spaces and left-pad numeric fields with zeros. Without CUSTOMIZE, all fields keep their raw positional content (including padding).

4. **REJECT flow behavior**: When a REJECT link is connected and `DIE_ON_ERROR=false`:
   - Rows that fail type conversion or date validation are sent to REJECT
   - REJECT rows contain ALL original schema columns PLUS `errorCode` (String) and `errorMessage` (String)
   - When REJECT is NOT connected, errors are silently dropped or cause job failure depending on `DIE_ON_ERROR`

5. **HEADER behavior**: When `HEADER > 0`, Talend skips that many rows at the TOP of the file, then uses the SCHEMA column names -- NOT the file header row. The header rows are completely discarded.

6. **UNCOMPRESS=true**: Transparently reads `.zip` files via Java's `ZipInputStream`. Decompression happens before parsing.

7. **LIMIT=0 or empty**: Means no limit -- read ALL rows. Talend documentation explicitly states: "maximum number of rows to be processed; 0 means no limit."

8. **Default encoding**: Talend uses a JVM-dependent default encoding. Many environments default to `ISO-8859-15` or system locale. This is NOT necessarily `UTF-8`.

9. **TRIM_ALL importance**: For positional files, trim is especially important because fields are always padded to their fixed width. Without trimming, a 5-character field containing "AB" would appear as "AB   " (with 3 trailing spaces). Most Talend jobs using tFileInputPositional enable `TRIMALL=true`.

10. **Pattern vs Schema column count**: The number of widths in the PATTERN must match the number of columns in the SCHEMA. If they differ, behavior is undefined (typically causes parsing errors or misalignment).

11. **CHECK_DATE=true**: Date-typed columns are strictly validated against the pattern defined in the schema. Invalid dates cause the entire row to be rejected to the REJECT flow.

12. **PROCESS_LONG_ROW**: Needed for mainframe or legacy files where individual rows exceed 100,000 characters. Without this flag, extremely long rows are silently truncated.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the `_map_component_parameters()` method in `component_parser.py` (lines 150-171) with a dedicated `elif component_type == 'tFileInputPositional'` branch within that method. Unlike some components, this one HAS a specific mapping branch in `_map_component_parameters()`. However, there is NO dedicated `elif` branch in `converter.py:_parse_component()` -- it falls through to the generic `parse_base_component()` path.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` (generic path -- no dedicated elif for tFileInputPositional)
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tFileInputPositional', config_raw)` (line 472)
4. `_map_component_parameters()` enters `elif component_type == 'tFileInputPositional'` branch (line 150)
5. Returns mapped config with 16 key-value pairs (lines 153-171)
6. Schema is extracted generically from `<metadata connector="FLOW">` and `<metadata connector="REJECT">` nodes

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | 154 | Expressions and context vars handled by generic loop |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | 155 | Default `'\n'` matches Talend default |
| 3 | `PATTERN` | Yes | `pattern` | 156 | Raw comma-separated widths string |
| 4 | `PATTERN_UNITS` | Yes | `pattern_units` | 157 | Default `'SYMBOLS'` -- **differs from Talend default `'Bytes'`** |
| 5 | `REMOVE_EMPTY_ROW` | Yes | `remove_empty_row` | 158 | Boolean from CHECK field type |
| 6 | `TRIMALL` | Yes | `trim_all` | 159 | Boolean from CHECK field type |
| 7 | `ENCODING` | Yes | `encoding` | 160 | **Default `'UTF-8'` may differ from Talend JVM-dependent default** |
| 8 | `HEADER` | Yes | `header_rows` | 161 | Converted to int via `.isdigit()` -- rejects negative values and expressions |
| 9 | `FOOTER` | Yes | `footer_rows` | 162 | Same `.isdigit()` conversion as HEADER |
| 10 | `LIMIT` | Yes | `limit` | 163 | Passed as raw string, engine handles int conversion |
| 11 | `DIE_ON_ERROR` | Yes | `die_on_error` | 164 | Boolean from CHECK field type. **Default `False` differs from Talend default `True`** |
| 12 | `PROCESS_LONG_ROW` | Yes | `process_long_row` | 165 | **Extracted but NEVER used by engine** |
| 13 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | 166 | Boolean from CHECK field type |
| 14 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | 167 | Default `','` matches Talend |
| 15 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | 168 | Default `'.'` matches Talend |
| 16 | `CHECK_DATE` | Yes | `check_date` | 169 | Boolean from CHECK field type |
| 17 | `UNCOMPRESS` | Yes | `uncompress` | 170 | Boolean from CHECK field type. **Extracted but engine only stores it, does NOT implement decompression** |
| 18 | `CUSTOMIZE` | **No** | -- | -- | **Not extracted. Per-column padding/alignment not available.** |
| 19 | `USE_BYTE_LENGTH` | **No** | -- | -- | **Not extracted. Double-byte character support unavailable.** |
| 20 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 21 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 22 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 23 | Customize sub-params (Column, Size, Padding char, Alignment) | **No** | -- | -- | **Not extracted. Table parameter -- generic mapper cannot parse nested `elementValue` groups.** |

**Summary**: 17 of 23 parameters extracted (74%). However, 2 extracted parameters (`process_long_row`, `uncompress`) are not functionally implemented in the engine. Effective extraction rate for functional parameters: 15 of 23 (65%).

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
| `pattern` (date) | Yes | Java date pattern converted to Python strftime: `yyyy`->`%Y`, `MM`->`%m`, `dd`->`%d`, `HH`->`%H`, `mm`->`%M`, `ss`->`%S` |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic -- no runtime impact) |
| `originalDbColumnName` | **No** | Original database column name not extracted (metadata only) |
| `talendType` | **No** | Full Talend type string (e.g., `id_String`) not preserved -- converted to Python type |

**REJECT schema**: The converter DOES extract REJECT metadata (lines 506-507: `component['schema']['reject'] = schema_cols`). However, the engine never uses it -- there is no REJECT flow implementation.

### 4.3 Expression Handling

**Context variable handling** (component_parser.py lines 449-456):
- Simple `context.var` references in non-CODE/IMPORT fields are detected by checking `'context.' in value`
- If the expression is NOT a Java expression (per `detect_java_expression()`), it is wrapped as `${context.var}` for ContextManager resolution
- If it IS a Java expression, it is left as-is for the Java expression marking step

**Java expression handling** (component_parser.py lines 462-469):
- After raw parameter extraction, the `mark_java_expression()` method scans all non-CODE/IMPORT/UNIQUE_NAME string values
- Values containing Java operators, method calls, routine references, etc. are prefixed with `{{java}}` marker
- The engine's `BaseComponent._resolve_java_expressions()` resolves these at runtime via the Java bridge

**Known limitations**:
- The `ExpressionConverter.detect_java_expression()` is aggressive -- it marks values with common operators (`+`, `-`, `/`, etc.) as Java expressions. This can cause false positives for file paths containing `/` (mitigated by path detection logic).
- The HEADER and FOOTER values are converted via `.isdigit()` before expression marking, so Java expressions in these fields (e.g., `context.headerCount + 1`) are passed as strings but not marked as `{{java}}`.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FIP-001 | **P1** | **No dedicated parser method in `converter.py`**: `tFileInputPositional` has no dedicated `elif` branch in `converter.py:_parse_component()`. It falls through to generic `parse_base_component()` which then dispatches via `_map_component_parameters()`. While `_map_component_parameters()` DOES have a dedicated branch (lines 150-171), the lack of a dedicated parser method in `converter.py` prevents extraction of table parameters (`CUSTOMIZE` sub-params) and limits extensibility. Per STANDARDS.md, every component SHOULD have its own `parse_*` method for complex parameters. |
| CONV-FIP-002 | **P1** | **`DIE_ON_ERROR` default mismatch**: Converter defaults `DIE_ON_ERROR` to `False` (line 164: `config_raw.get('DIE_ON_ERROR', False)`), but Talend documentation states default is `true` for this component. If a Talend job does not explicitly set `die_on_error`, the converter produces `False`, which differs from Talend behavior. This silences errors that Talend would have surfaced. |
| CONV-FIP-003 | **P2** | **`CUSTOMIZE` not extracted**: Per-column padding character and alignment settings are unavailable. This is a table parameter that the generic mapper cannot parse. For positional files, this is important because fields are commonly padded with specific characters (spaces, zeros) and the Customize section defines how to strip them. Without this, all padding remains in the data. |
| CONV-FIP-004 | **P2** | **`USE_BYTE_LENGTH` not extracted**: Double-byte character support unavailable. Files containing CJK characters or other multi-byte encodings where byte-based width counting is needed will be parsed incorrectly. |
| CONV-FIP-005 | **P2** | **`PATTERN_UNITS` default mismatch**: Converter defaults to `'SYMBOLS'` (line 157), but Talend documentation lists default as `Bytes`. This can cause incorrect field splitting for multi-byte encoded files where byte and symbol widths differ. |
| CONV-FIP-006 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both, this violates the documented standard and creates subtle type mapping differences (e.g., `bool` in converter output maps differently in `_build_dtype_dict()` vs `validate_schema()`). |
| CONV-FIP-007 | **P3** | **`process_long_row` extracted but unused**: The converter extracts `PROCESS_LONG_ROW` as `process_long_row` (line 165), but the engine never reads this config key. This is dead config -- converter effort wasted, and users may believe they have long-row support when they do not. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read fixed-width file | **Yes** | High | `_process()` line 264 | Uses `pd.read_fwf()` -- solid core implementation |
| 2 | Pattern-based column splitting | **Yes** | High | `_process()` line 245 | Parses pattern string to list of widths, passes to `pd.read_fwf(widths=...)` |
| 3 | Header row skip | **Yes** | High | `_process()` line 270 | `skiprows=header_rows` passed to `pd.read_fwf()` |
| 4 | Footer row skip | **Yes** | High | `_process()` line 272 | `skipfooter=footer_rows`, forces Python engine when `footer_rows > 0` |
| 5 | Row limit | **Yes** | High | `_process()` line 271 | `nrows=nrows` passed to `pd.read_fwf()` |
| 6 | Encoding support | **Yes** | Medium | `_process()` line 267 | Passed to pandas. Default `UTF-8` may differ from Talend JVM default |
| 7 | Schema column naming | **Yes** | High | `_process()` lines 253-255 | Uses `names=names` from output_schema |
| 8 | Schema type enforcement (read) | **Yes** | Medium | `_build_dtype_dict()` line 137 | Builds dtype dict for `pd.read_fwf()`. Supports both Talend and Python type formats. |
| 9 | Schema validation (post-read) | **Yes** | Medium | `_process()` line 300 | Calls `self.validate_schema(df, self.output_schema)` from base class |
| 10 | Trim all columns | **Yes** | Medium | `_process()` lines 281-285 | Applied to string columns via `str.strip()`. **Bug**: depends on NaN fill ordering (see BUG-FIP-003) |
| 11 | Remove empty rows | **Yes** | Medium | `_process()` lines 288-293 | `dropna(how='all')` -- does NOT catch blank-but-not-NaN rows after trim (see BUG-FIP-010) |
| 12 | NaN fill for strings | **Yes** | High | `_process()` lines 295-296 | Fills NaN in string columns with empty string (Talend compatibility) |
| 13 | Die on error | **Yes** | High | `_process()` lines 234-241, 354-359 | Raises or returns empty DF based on flag |
| 14 | BigDecimal columns | **Yes** | High | `_process()` lines 319-326 | Post-processes with `Decimal(str(x))` conversion |
| 15 | Advanced separator (number) | **Yes** | Medium | `_process()` lines 303-307 | Strips thousands separator, replaces decimal separator. **Bug**: applied AFTER schema validation (see BUG-FIP-005) |
| 16 | Check date | **Partial** | Low | `_process()` lines 310-317 | Converts dates via `pd.to_datetime(errors='coerce')` but only checks if type is `'date'` (lowercase), missing `'id_Date'` and `'datetime'`. No format-based validation. Invalid dates become NaT, not REJECT rows. |
| 17 | File existence check | **Yes** | High | `_process()` line 233 | `os.path.exists()` before reading |
| 18 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 19 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 20 | Pattern validation | **Yes** | High | `_validate_config()` lines 97-106 and `_process()` lines 244-250 | Both validate pattern format; only `_process()` validation is live |
| 21 | **REJECT flow** | **No** | N/A | -- | **No reject output. All errors either die or return empty DF. Fundamental gap.** |
| 22 | **Compressed file reading** | **No** | N/A | -- | **`uncompress` config key exists but is NEVER used in `_process()`. Config stored but ignored.** |
| 23 | **Customize (per-column padding)** | **No** | N/A | -- | **No per-column padding removal or alignment. Critical for positional files with non-space padding.** |
| 24 | **Use byte length** | **No** | N/A | -- | **No byte-based width counting. Multi-byte character files may parse incorrectly.** |
| 25 | **Process long row** | **No** | N/A | -- | **`process_long_row` config extracted but never used. Very long rows not explicitly handled.** |
| 26 | **Pattern units (Bytes vs Symbols)** | **No** | N/A | -- | **`pattern_units` config extracted but NEVER used in `_process()`. Always treats widths as character counts.** |
| 27 | **Row separator** | **No** | N/A | -- | **`row_separator` config extracted but NEVER passed to `pd.read_fwf()`. pandas uses its own default line terminator.** |
| 28 | **Streaming / hybrid mode for positional files** | **No** | N/A | -- | **No `_read_streaming()` method. `_process()` always reads entire file. Base class HYBRID mode falls through to batch.** |
| 29 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |
| 30 | **Per-column trim (TRIMSELECT)** | **No** | N/A | -- | **Only trim-all; no per-column selective trimming.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIP-001 | **P1** | **No REJECT flow**: Talend produces reject rows for unparseable lines with `errorCode` and `errorMessage` columns when `DIE_ON_ERROR=false` and a REJECT link is connected. V1 either raises exceptions (die_on_error=true) or returns empty DataFrame (die_on_error=false). There is NO mechanism to capture and route bad rows. The component docstring on line 49 acknowledges this: `"NB_LINE_REJECT: Rows rejected (always 0 for this component)"`. |
| ENG-FIP-002 | **P1** | **No compressed file support**: `uncompress` config key is extracted from Talend XML and stored in config, but line 213 (`uncompress = self.config.get('uncompress', ...)`) reads it only to NEVER use it anywhere in the processing logic. Jobs reading compressed positional files will fail with encoding or format errors. |
| ENG-FIP-003 | **P1** | **Row separator ignored**: `row_separator` is extracted (line 199) and stored in a local variable but is NEVER passed to `pd.read_fwf()`. The `pd.read_fwf()` call on line 264 has no `lineterminator` parameter. Files with non-standard row separators (e.g., `\r\n` on Unix, `\r` for old Mac format) rely on pandas auto-detection, which may fail for unusual separators. |
| ENG-FIP-004 | **P1** | **Pattern units ignored**: `pattern_units` is extracted (line 201) but NEVER used in processing logic. The engine always treats pattern widths as character counts via `pd.read_fwf(widths=...)`. For files with multi-byte encodings (CJK in UTF-8), byte-based counting would produce different field boundaries than symbol-based counting. |
| ENG-FIP-005 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. |
| ENG-FIP-006 | **P2** | **No per-column padding/alignment (CUSTOMIZE)**: Positional files commonly use character padding (spaces, zeros, asterisks) to fill fixed-width fields. Talend's Customize section lets users define per-column padding characters and alignment. Without this, a field like `000042` (zero-padded integer) retains leading zeros unless `TRIMALL` happens to strip them (which it won't -- trim only removes whitespace). |
| ENG-FIP-007 | **P2** | **No byte-length mode (USE_BYTE_LENGTH)**: Files with multi-byte character encodings that need byte-based field boundaries will parse incorrectly. |
| ENG-FIP-008 | **P2** | **Check date only matches lowercase `'date'`**: Line 313 checks `col.get('type', '').lower() == 'date'`, which matches `'date'` and `'Date'` but NOT `'id_Date'` (lowered: `'id_date'`). Since the converter outputs Python types (`'datetime'`), not Talend types (`'id_Date'`), and `'datetime'.lower() == 'datetime'` != `'date'`, the check_date feature is effectively dead for converter-produced schemas. |
| ENG-FIP-009 | **P3** | **No `process_long_row` support**: Config extracted but unused. Very long rows (>100K chars) may be truncated without warning. Rare in practice. |
| ENG-FIP-010 | **P3** | **Default encoding may differ from Talend**: Engine defaults to `UTF-8` (line 67: `DEFAULT_ENCODING = 'UTF-8'`). Talend's default is JVM-dependent, often `ISO-8859-15`. Files without explicit encoding may be read with wrong encoding. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. **BUT**: `_update_global_map()` has a P0 bug (BUG-FIP-001) that crashes before completion. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE since no reject exists. |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no reject flow exists. Even if `validate_schema()` drops rows, the reject count is not updated. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIP-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileInputPositional, since `_update_global_map()` is called after every component execution (via `execute()` line 218). Additionally, `{stat_name}` references the last loop iteration value only, which is misleading. |
| BUG-FIP-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FIP-003 | **P3** | `src/v1/engine/components/file/file_input_positional.py:281-296` | **Trim and NaN fill ordering dependency**: The trim logic on lines 283-285 calls `df[col].str.strip()` on object columns before NaN values are filled on line 296. The pandas `str` accessor tolerates NaN (produces NaN), so the ordering dependency is actually robust either way. The real semantic issue is the `dropna` mismatch in `remove_empty_row` (see BUG-FIP-010). Downgraded from P1 -- the ordering is safe in practice. |
| BUG-FIP-004 | **P1** | `src/v1/engine/components/file/file_input_positional.py:81-135` | **`_validate_config()` is never called**: The method exists and contains 54 lines of validation logic, but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (empty pattern, non-integer header_rows, etc.) are only caught when they cause runtime errors deep in `_process()` or `pd.read_fwf()`. |
| BUG-FIP-005 | **P1** | `src/v1/engine/components/file/file_input_positional.py:298-307` | **Advanced separator applied AFTER schema validation**: Advanced separator processing (lines 303-307: removing thousands separator, replacing decimal separator) runs AFTER `validate_schema()` (line 300). But `validate_schema()` calls `pd.to_numeric(errors='coerce')` which will FAIL to parse "1,234,567.89" (with thousands separators) -- the numeric conversion produces NaN BEFORE the separators are removed. The correct order is: remove separators FIRST, then validate schema. This bug makes `advanced_separator=true` non-functional for numeric columns with schema enforcement. |
| BUG-FIP-006 | **P2** | `src/v1/engine/components/file/file_input_positional.py:148-154` and `base_component.py:353-354` | **`id_Boolean` mapped to `object` in `_build_dtype_dict()` but `bool` in `validate_schema()`**: Line 154 maps `id_Boolean` to `'object'` with comment "Read as object, convert later". But `validate_schema()` in base_component.py line 354 converts to `'bool'` directly via `.astype('bool')`. This means: (1) during read, boolean columns are strings; (2) during validation, they are cast to bool. The issue is that string `"false"` cast to Python bool produces `True` (non-empty string is truthy). Only `""` and `None`/`NaN` produce `False`. This differs from Talend where `"false"` string maps to boolean `false`. |
| BUG-FIP-007 | **P2** | `src/v1/engine/components/file/file_input_positional.py:313` | **`check_date` type comparison dead for converter-produced schemas**: Line 313 checks `col.get('type', '').lower() == 'date'`. The converter's `ExpressionConverter.convert_type()` maps `id_Date` to `'datetime'` (not `'date'`). Since `'datetime'.lower() != 'date'`, the check_date feature never activates for converter-produced schemas. For schemas with raw Talend types, `'id_Date'.lower() == 'id_date'` also does not match `'date'`. The check is effectively dead code for all real-world schemas. |
| BUG-FIP-008 | **P1** | `src/v1/engine/components/file/file_input_positional.py:303-307` | **Advanced separator applied to ALL object columns, not just numeric**: Strips `thousands_separator` from string fields like `'Smith, John'` -> `'Smith John'`. Should restrict to numeric-typed schema columns only. |
| BUG-FIP-009 | **P1** | `src/v1/engine/components/file/file_input_positional.py:315` | **`check_date` ignores schema date pattern**: `pd.to_datetime()` on line 315 never passes `format` parameter from schema column's `pattern`. Dates silently misinterpreted (dd/MM vs MM/dd). |
| BUG-FIP-010 | **P1** | `src/v1/engine/components/file/file_input_positional.py:288-293` | **`remove_empty_row` with `dropna(how='all')` doesn't catch blank-but-not-NaN rows after trim**: Empty strings `''` are not NaN. Talend treats all-blank rows as empty. After trim, rows that are all-whitespace become all-empty-string but `dropna` ignores them because `''` is not NaN. |
| BUG-FIP-011 | **P2** | `src/v1/engine/components/file/file_input_positional.py:270-272` | **`skipfooter` + `nrows` interaction wrong**: pandas applies `nrows` first then `skipfooter` on the limited set. Talend removes footer from full file then limits. 100-row file with footer=5 limit=10: Talend returns 10 rows, pandas returns 5. |
| BUG-FIP-012 | **P2** | `src/v1/engine/components/file/file_input_positional.py:267` | **UTF-8 BOM corrupts first field**: `encoding='UTF-8'` preserves BOM. First field shifted by 3 chars. Fix: use `'utf-8-sig'`. |
| BUG-FIP-013 | **P2** | `src/v1/engine/components/file/file_input_positional.py:240-241` | **Empty DataFrame on missing file loses schema**: When `die_on_error=false` and file is missing, line 241 returns `pd.DataFrame()` -- an empty DataFrame with NO columns. Downstream components expecting specific columns will fail with KeyError. Should return `pd.DataFrame(columns=schema_column_names)` to preserve schema structure. |
| BUG-FIP-014 | **P2** | `src/v1/engine/components/file/file_input_positional.py:358-359` | **Error-path empty DataFrame also loses schema**: Same issue as BUG-FIP-013 but in the general exception handler (line 359). Returns `pd.DataFrame()` with no columns instead of preserving schema. |
| BUG-FIP-015 | **P2** | `src/v1/engine/base_component.py:351` | **`validate_schema()` nullable logic inverted**: Line 351 checks `col_def.get('nullable', True)`. Default is `True` (nullable). When nullable=True, the code does `fillna(0).astype('int64')`, which REMOVES nulls. This means: nullable columns get nulls silently converted to 0. While this happens to match Talend default behavior (null integers -> 0), the code semantics are inverted: "if the column IS nullable, then fill nulls with 0" -- the opposite of what "nullable" means. If a column is explicitly marked `nullable=False`, the `if` branch is SKIPPED, and the column retains NaN values with float64 dtype. This is backwards. **CROSS-CUTTING**: Affects all components using `validate_schema()`. |

### 6.2 Unused Config Keys

The following config keys are extracted by the converter and read by the engine but NEVER functionally used:

| Config Key | Read At | Used In Processing? | Notes |
|------------|---------|---------------------|-------|
| `row_separator` | Line 199 | **No** | Stored in local var but never passed to `pd.read_fwf()` |
| `pattern_units` | Line 201 | **No** | Stored in local var but never used in width calculation |
| `uncompress` | Line 213 | **No** | Stored in local var but never checked before file reading |
| `process_long_row` | Not read | **No** | Not even read from config; only exists in converter output |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIP-001 | **P2** | **`remove_empty_row` (singular)** vs `tFileInputDelimited`'s converter key `remove_empty_rows` (plural). Inter-component inconsistency. The engine config key is `remove_empty_row` (singular, line 158 of converter, line 202 of engine), while `tFileInputDelimited` uses `remove_empty_rows` (plural). |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIP-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FIP-002 | **P2** | "Every component SHOULD have its own `parse_*` method" (STANDARDS.md) | Uses generic `_map_component_parameters()` branch instead of a dedicated `parse_file_input_positional()` method in converter.py. Cannot handle table parameters. |
| STD-FIP-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FIP-001 | **P3** | **No path traversal protection**: `filepath` from config is used directly with `os.path.exists()` and passed to `pd.read_fwf()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.6 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 215) and complete (line 335) with row counts -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError`, `FileOperationError`, `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | `ComponentExecutionError(self.id, error_msg, e)` preserves original exception (line 356) -- correct |
| `die_on_error` handling | Two separate code paths: missing file (line 234-241) and general errors (line 354-359) -- correct |
| No bare `except` | All except clauses specify exception types -- correct |
| Error messages | Include component ID, file path, and error details -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct but loses schema (BUG-FIP-013, BUG-FIP-014) |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `Optional[pd.DataFrame]` parameter type -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[Dict[str, str]]`, `List[str]` -- correct |

### 6.9 Thread Safety

| Aspect | Assessment |
|--------|------------|
| Shared state | `self.stats` dict is mutated during execution. Not thread-safe if multiple threads call `execute()` on same instance. |
| Global state | `global_map` is shared across components. `put()` and `get()` are not synchronized. Concurrent access from multiple component threads could corrupt globalMap. |
| File handles | `pd.read_fwf()` handles file opening/closing internally. No leaked file handles. |
| **Verdict** | Not thread-safe. Acceptable for single-threaded Talend subjob execution model, but would fail under concurrent execution. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIP-001 | **P2** | **No streaming mode**: Unlike `FileInputDelimited` which has `_read_streaming()` for large files, `FileInputPositional` only has batch mode via `_process()`. For very large positional files (multi-GB), the entire file is loaded into memory. `pd.read_fwf()` does support `chunksize` parameter, but it is not used. The base class HYBRID mode auto-selection falls through to batch since `_process()` does not check execution mode. |
| PERF-FIP-002 | **P2** | **Post-processing iterates string columns twice**: `_process()` calls `df.select_dtypes(include=['object'])` once for trimming (line 283) and again for NaN filling (line 295). These could be combined into a single pass. For DataFrames with many object columns and millions of rows, this doubles the column iteration overhead. |
| PERF-FIP-003 | **P3** | **BigDecimal conversion uses `apply()` with lambda**: Line 326 uses `df[col_name].apply(lambda x: Decimal(str(x)) ...)` which is a Python-level row-by-row loop. For columns with millions of values, this is slow compared to vectorized approaches. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | **NOT implemented** for positional files. Only batch mode available. |
| Memory threshold | `MEMORY_THRESHOLD_MB = 3072` (3GB) inherited from `BaseComponent` exists but is never checked in `_process()`. |
| Footer skip engine | `engine='python'` forced when `footer_rows > 0` (line 273). Python engine is slower but required for footer support. |
| Dtype enforcement | `dtype=dtype_dict` passed to `pd.read_fwf()` (line 274) -- reduces memory by using correct types from the start. |
| `header=None` | Line 268: `header=None` prevents pandas from using any row as column header. Correct for fixed-width files with explicit schema. |

### 7.2 Engine Selection Logic

| Condition | Engine | Notes |
|-----------|--------|-------|
| `footer_rows > 0` | `'python'` | Required for `skipfooter`. |
| `footer_rows == 0` | `None` (pandas default) | pandas auto-selects C engine when available. Faster for large files. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputPositional` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **Partial** | `tests/converters/test_component_mapper.py` | Contains references to FileInputPositional but only for component mapping, not converter correctness |

**Key finding**: The v1 engine has ZERO tests for this component. All 359 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic positional file read | P0 | Read a simple fixed-width file with pattern "5,4,5", verify row count and column values match expected output |
| 2 | Schema enforcement | P0 | Read with typed schema (int, float, string, Decimal), verify correct type coercion for each column type |
| 3 | Header/footer skip | P0 | Verify `header_rows=2, footer_rows=1` skips the correct rows from a known file |
| 4 | Missing file + die_on_error=true | P0 | Should raise `FileOperationError` with descriptive message |
| 5 | Missing file + die_on_error=false | P0 | Should return empty DataFrame with stats (0, 0, 0) |
| 6 | Empty file | P0 | Should return empty DataFrame without error, stats (0, 0, 0) |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict after execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Trim all columns | P1 | Read positional file with padded fields (e.g., "AB   ", "  42"), verify trim removes padding |
| 9 | BigDecimal columns | P1 | Verify `Decimal` precision is preserved (e.g., `123.456789012345` not rounded to float precision) |
| 10 | Row limit | P1 | Verify `limit=5` reads only 5 rows from a 100-row file |
| 11 | Remove empty rows | P1 | Verify blank rows (all fields empty after splitting) are filtered out |
| 12 | Encoding ISO-8859-15 | P1 | Read file with non-UTF8 characters using ISO-8859-15 encoding, verify correct decoding |
| 13 | Context variable in filepath | P1 | `${context.input_dir}/file.txt` should resolve via context manager |
| 14 | Pattern with various widths | P1 | Test pattern like "10,20,5,3" on file with matching layout, verify each field extracted correctly |
| 15 | Advanced separator | P1 | File with "1.234.567,89" format, verify thousands separator removed and decimal corrected |
| 16 | Boolean column handling | P1 | Verify `"true"`, `"false"`, `"TRUE"`, `"FALSE"` strings convert to correct boolean values |
| 17 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution (requires BUG-FIP-001/002 fixes first) |
| 18 | Invalid pattern value | P1 | Non-integer in pattern (e.g., "5,abc,3") should raise `ConfigurationError` |
| 19 | Empty pattern | P1 | Pattern that parses to empty list should raise `ConfigurationError` |
| 20 | Negative width in pattern | P1 | Pattern "5,-3,4" should raise `ConfigurationError` |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Large file memory | P2 | Read a file larger than typical memory threshold, verify no OOM (or implement streaming) |
| 22 | Check date with valid dates | P2 | Verify date columns are correctly parsed when check_date=true (after fixing BUG-FIP-007) |
| 23 | Check date with invalid dates | P2 | Verify invalid dates produce NaT (or REJECT rows when implemented) |
| 24 | File with only header rows | P2 | `header_rows=5` on a 5-row file should return empty DataFrame with correct columns |
| 25 | Pattern sum exceeds line length | P2 | Verify behavior when total pattern width > actual line length |
| 26 | Pattern sum less than line length | P2 | Verify trailing characters are discarded |
| 27 | NaN handling in non-string columns | P2 | Verify NaN values in integer/float columns are handled correctly through the dtype+validation pipeline |
| 28 | File path with spaces | P2 | Verify `/path with spaces/data.txt` works correctly |
| 29 | Concurrent reads | P2 | Multiple `FileInputPositional` instances reading different files simultaneously |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIP-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FIP-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FIP-001 | Testing | Zero v1 unit tests for this component. All 359 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIP-001 | Converter | No dedicated parser method in `converter.py` -- uses generic `parse_base_component()` path. Cannot handle table parameters (CUSTOMIZE sub-params). |
| CONV-FIP-002 | Converter | `DIE_ON_ERROR` default `False` differs from Talend default `true`. Silences errors that Talend would surface. |
| ENG-FIP-001 | Engine | **No REJECT flow** -- bad rows are lost or cause job failure. Fundamental gap for data quality pipelines. |
| ENG-FIP-002 | Engine | `uncompress` config extracted but NEVER used in processing. Compressed file reading silently fails. |
| ENG-FIP-003 | Engine | `row_separator` config extracted but NEVER passed to `pd.read_fwf()`. Custom row separators ignored. |
| ENG-FIP-004 | Engine | `pattern_units` config extracted but NEVER used. Byte vs symbol counting not implemented. |
| ENG-FIP-005 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set -- error details not available downstream. |
| BUG-FIP-004 | Bug | `_validate_config()` is dead code -- never called by any code path. 54 lines of unreachable validation. |
| BUG-FIP-005 | Bug | Advanced separator applied AFTER schema validation. `pd.to_numeric()` fails on "1,234,567.89" before separators are removed. Makes `advanced_separator=true` non-functional for numeric schema columns. |
| BUG-FIP-008 | Bug | Advanced separator applied to ALL object columns, not just numeric. Strips `thousands_separator` from string fields like `'Smith, John'` -> `'Smith John'`. |
| BUG-FIP-009 | Bug | `check_date` ignores schema date pattern. `pd.to_datetime()` never passes `format` parameter from schema column's `pattern`. Dates silently misinterpreted (dd/MM vs MM/dd). |
| BUG-FIP-010 | Bug | `remove_empty_row` with `dropna(how='all')` doesn't catch blank-but-not-NaN rows after trim. Empty strings `''` are not NaN. Talend treats all-blank rows as empty. |
| TEST-FIP-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIP-003 | Converter | `CUSTOMIZE` not extracted -- per-column padding/alignment unavailable. Critical for positional files. |
| CONV-FIP-004 | Converter | `USE_BYTE_LENGTH` not extracted -- double-byte character support unavailable. |
| CONV-FIP-005 | Converter | `PATTERN_UNITS` default `'SYMBOLS'` differs from Talend default `Bytes`. |
| CONV-FIP-006 | Converter | Schema types converted to Python format instead of Talend format, violating STANDARDS.md. |
| ENG-FIP-006 | Engine | No per-column padding/alignment support (CUSTOMIZE). Padding characters retained in data. |
| ENG-FIP-007 | Engine | No byte-length mode (USE_BYTE_LENGTH). Multi-byte character files may parse incorrectly. |
| ENG-FIP-008 | Engine | `check_date` type check matches `'date'` but converter outputs `'datetime'`. Feature is dead code. |
| BUG-FIP-006 | Bug | `id_Boolean` mapped to `object` in `_build_dtype_dict()` then cast to `bool` in `validate_schema()`. String `"false"` becomes `True`. |
| BUG-FIP-007 | Bug | `check_date` type comparison dead for converter-produced schemas (`'datetime'` != `'date'`). |
| BUG-FIP-011 | Bug | `skipfooter` + `nrows` interaction wrong. pandas applies `nrows` first then `skipfooter` on limited set. Talend removes footer from full file then limits. |
| BUG-FIP-012 | Bug | UTF-8 BOM corrupts first field. `encoding='UTF-8'` preserves BOM. First field shifted by 3 chars. Fix: use `'utf-8-sig'`. |
| BUG-FIP-013 | Bug | Empty DataFrame on missing file loses schema -- no columns preserved for downstream components. |
| BUG-FIP-014 | Bug | Error-path empty DataFrame also loses schema structure. |
| BUG-FIP-015 | Bug (Cross-Cutting) | `validate_schema()` nullable logic inverted: nullable=True causes null-fill-to-0; nullable=False preserves NaN. |
| NAME-FIP-001 | Naming | `remove_empty_row` (singular) inconsistent with `tFileInputDelimited`'s `remove_empty_rows` (plural). |
| STD-FIP-001 | Standards | `_validate_config()` exists but never called -- dead validation. |
| STD-FIP-002 | Standards | Uses generic `_map_component_parameters()` instead of dedicated `parse_file_input_positional()` method. |
| STD-FIP-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| PERF-FIP-001 | Performance | No streaming mode -- entire file loaded into memory. No chunked reading. |
| PERF-FIP-002 | Performance | Post-processing iterates string columns twice (trim pass + NaN fill pass). |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIP-003 | Bug | Trim and NaN fill ordering dependency. Ordering is actually robust either way; the real issue is `dropna` semantic mismatch (BUG-FIP-010). Downgraded from P1. |
| CONV-FIP-007 | Converter | `process_long_row` extracted but never used by engine. Dead config. |
| ENG-FIP-009 | Engine | No `process_long_row` support. Very long rows may truncate. |
| ENG-FIP-010 | Engine | Default encoding `UTF-8` may differ from Talend JVM default. |
| SEC-FIP-001 | Security | No path traversal protection on `filepath`. |
| PERF-FIP-003 | Performance | BigDecimal conversion uses slow `apply()` with lambda (row-by-row Python loop). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 13 | 2 converter, 5 engine, 5 bugs, 1 testing |
| P2 | 20 | 4 converter, 3 engine, 7 bugs, 1 naming, 3 standards, 2 performance |
| P3 | 6 | 1 bug, 1 converter, 2 engine, 1 security, 1 performance |
| **Total** | **42** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FIP-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FIP-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FIP-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic positional read, schema enforcement, header/footer skip, missing file handling (both die_on_error modes), empty file, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Implement REJECT flow** (ENG-FIP-001): Add row-level error handling in `_process()`. When a row fails type conversion or date validation, capture it in a reject list instead of silently dropping it. Return `{'main': good_df, 'reject': reject_df}` from `_process()`. Update `_update_stats()` to reflect actual rejected count.

### Short-Term (Hardening)

5. **Fix advanced separator ordering** (BUG-FIP-005): Move the advanced separator processing (lines 303-307) to BEFORE `validate_schema()` (line 300). This ensures numeric strings like "1,234,567.89" have separators removed before `pd.to_numeric()` attempts to parse them. **Impact**: Makes `advanced_separator=true` functional for numeric schema columns. **Risk**: Low.

6. **Fix `die_on_error` default** (CONV-FIP-002): Change converter default from `False` to `True` on line 164 of `component_parser.py`. This matches Talend's documented default and prevents silent error swallowing. **Impact**: Changes behavior for jobs that don't explicitly set this flag. **Risk**: Medium (may cause previously silent jobs to fail, which is actually the correct behavior).

7. **Wire up unused config keys**: Connect `row_separator`, `pattern_units`, and `uncompress` to actual processing logic:
   - Pass `row_separator` to `pd.read_fwf()` via pre-processing (split content on custom separator, feed to StringIO)
   - Use `pattern_units` to conditionally switch between byte-based and character-based width counting
   - Check `uncompress` before file reading and use pandas `compression` parameter or pre-decompress

8. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FIP-005): In error handlers within `_process()`, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` when global_map is available.

9. **Wire up `_validate_config()`** (BUG-FIP-004): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` if errors found. Alternatively, add validation as a standard lifecycle step in `BaseComponent.execute()`.

10. **Fix `check_date` type comparison** (BUG-FIP-007): Change line 313 from `col.get('type', '').lower() == 'date'` to `col.get('type', '').lower() in ('date', 'datetime', 'id_date')` to match all possible type representations produced by the converter.

11. **Fix empty DataFrame schema preservation** (BUG-FIP-013, BUG-FIP-014): When returning empty DataFrames on error/missing file, preserve schema columns:
    ```python
    if self.output_schema:
        cols = [c['name'] for c in self.output_schema]
        return {'main': pd.DataFrame(columns=cols)}
    return {'main': pd.DataFrame()}
    ```

12. **Create dedicated converter parser** (CONV-FIP-001): Add an `elif component_type == 'tFileInputPositional'` branch in `converter.py:_parse_component()` that calls a new `parse_file_input_positional(node, component)` method. This enables extraction of `CUSTOMIZE` table parameters (Column, Size, Padding char, Alignment).

### Long-Term (Optimization)

13. **Implement streaming mode** (PERF-FIP-001): Add chunked reading using `pd.read_fwf(chunksize=N)` similar to `FileInputDelimited._read_streaming()`. Check `self.execution_mode` in `_process()` and branch accordingly.

14. **Implement per-column padding removal** (ENG-FIP-006): When `CUSTOMIZE` data is available, apply per-column padding character stripping and alignment-aware trimming instead of just whitespace trimming.

15. **Fix boolean handling** (BUG-FIP-006): In `validate_schema()` or in `_build_dtype_dict()`, ensure that string representations of boolean values (`"true"`, `"false"`, `"1"`, `"0"`) are correctly converted to Python booleans. Consider adding explicit boolean mapping logic similar to how BigDecimal is handled.

16. **Optimize post-processing** (PERF-FIP-002): Combine the two `select_dtypes(include=['object'])` calls (trim + NaN fill) into a single pass over object columns.

17. **Add byte-length mode** (ENG-FIP-007): When `use_byte_length=true` or `pattern_units='Bytes'`, convert byte-based widths to character widths for the current encoding before passing to `pd.read_fwf()`.

18. **Add `keep_default_na=False`**: Add this parameter to the `pd.read_fwf()` call on line 264. Without it, literal strings like "NA", "NULL", "None" in positional files are silently converted to pandas NaN, losing data (e.g., "NA" as a state abbreviation for Namibia).

19. **Create integration test** (TEST-FIP-002): Build an end-to-end test exercising `tFileInputPositional -> tMap -> tFileOutputPositional` in the v1 engine, verifying context resolution, Java bridge integration, and globalMap propagation.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 150-171
# FileInputPositional mapping
elif component_type == 'tFileInputPositional':
    header_value = config_raw.get('HEADER', '0')
    footer_value = config_raw.get('FOOTER', '0')
    return {
        'filepath': config_raw.get('FILENAME', ''),
        'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
        'pattern': config_raw.get('PATTERN', ''),
        'pattern_units': config_raw.get('PATTERN_UNITS', 'SYMBOLS'),
        'remove_empty_row': config_raw.get('REMOVE_EMPTY_ROW', False),
        'trim_all': config_raw.get('TRIMALL', False),
        'encoding': config_raw.get('ENCODING', 'UTF-8'),
        'header_rows': int(header_value) if header_value.isdigit() else header_value,
        'footer_rows': int(footer_value) if footer_value.isdigit() else footer_value,
        'limit': config_raw.get('LIMIT', ''),
        'die_on_error': config_raw.get('DIE_ON_ERROR', False),
        'process_long_row': config_raw.get('PROCESS_LONG_ROW', False),
        'advanced_separator': config_raw.get('ADVANCED_SEPARATOR', False),
        'thousands_separator': config_raw.get('THOUSANDS_SEPARATOR', ','),
        'decimal_separator': config_raw.get('DECIMAL_SEPARATOR', '.'),
        'check_date': config_raw.get('CHECK_DATE', False),
        'uncompress': config_raw.get('UNCOMPRESS', False)
    }
```

**Notes on this code**:
- Line 161: `.isdigit()` rejects negative numbers and Java expressions. If `HEADER` contains a context variable or expression, it passes through as a string, which the engine then tries to `int()` cast (with fallback).
- Line 157: Default `'SYMBOLS'` may differ from Talend default `'Bytes'`.
- Line 164: Default `False` for `DIE_ON_ERROR` differs from Talend default `true`.
- Line 160: Default `'UTF-8'` for `ENCODING` may differ from Talend JVM-dependent default.

---

## Appendix B: Engine Class Structure

```
FileInputPositional (BaseComponent)
    Constants:
        DEFAULT_ENCODING = 'UTF-8'
        DEFAULT_ROW_SEPARATOR = '\n'
        DEFAULT_PATTERN_UNITS = 'SYMBOLS'
        DEFAULT_THOUSANDS_SEPARATOR = ','
        DEFAULT_DECIMAL_SEPARATOR = '.'
        DEFAULT_HEADER_ROWS = 0
        DEFAULT_FOOTER_ROWS = 0
        DEFAULT_REMOVE_EMPTY_ROWS = False
        DEFAULT_TRIM_ALL = False
        DEFAULT_DIE_ON_ERROR = True
        DEFAULT_ADVANCED_SEPARATOR = False
        DEFAULT_CHECK_DATE = False
        DEFAULT_UNCOMPRESS = False

    Methods:
        _validate_config() -> List[str]              # DEAD CODE -- never called
        _build_dtype_dict() -> Optional[Dict]         # Type mapping for pd.read_fwf
        _process(input_data) -> Dict[str, Any]        # Main entry point (batch only)
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filepath` | Mapped | -- |
| `ROWSEPARATOR` | `row_separator` | Mapped (unused) | P1 (wire up) |
| `PATTERN` | `pattern` | Mapped | -- |
| `PATTERN_UNITS` | `pattern_units` | Mapped (unused) | P1 (wire up) |
| `REMOVE_EMPTY_ROW` | `remove_empty_row` | Mapped | -- |
| `TRIMALL` | `trim_all` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped | -- |
| `HEADER` | `header_rows` | Mapped | -- |
| `FOOTER` | `footer_rows` | Mapped | -- |
| `LIMIT` | `limit` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped (wrong default) | P1 (fix default) |
| `PROCESS_LONG_ROW` | `process_long_row` | Mapped (unused) | P3 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | Mapped | -- |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | Mapped | -- |
| `DECIMAL_SEPARATOR` | `decimal_separator` | Mapped | -- |
| `CHECK_DATE` | `check_date` | Mapped (broken) | P2 (fix type check) |
| `UNCOMPRESS` | `uncompress` | Mapped (unused) | P1 (wire up) |
| `CUSTOMIZE` | -- | **Not Mapped** | P2 |
| `USE_BYTE_LENGTH` | -- | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Type Mapping Comparison

### Converter Output (ExpressionConverter.convert_type)

| Talend Type | Converter Output |
|-------------|-----------------|
| `id_String` | `str` |
| `id_Integer` | `int` |
| `id_Long` | `int` |
| `id_Float` | `float` |
| `id_Double` | `float` |
| `id_Boolean` | `bool` |
| `id_Date` | `datetime` |
| `id_BigDecimal` | `Decimal` |
| `id_Object` | `object` |
| `id_Character` | `str` |
| `id_Byte` | `int` |
| `id_Short` | `int` |

### Engine _build_dtype_dict() (for pd.read_fwf)

| Type Input | Pandas Dtype | Notes |
|------------|-------------|-------|
| `id_String` / `str` | `object` | Correct |
| `id_Integer` / `int` | `Int64` (nullable) | Uses nullable integer to handle NaN during read |
| `id_Long` / `long` | `Int64` (nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | Correct |
| `id_Double` / `double` | `float64` | Correct |
| `id_Boolean` | `object` | **Reads as object, defers conversion -- correct design intent** |
| `bool` | **Not in mapping** | Falls through to default `object` -- works, but relies on fallback |
| `id_Date` / `date` | `object` | Correct -- read as string, convert later |
| `id_BigDecimal` / `Decimal` | `object` | Correct -- read as string, convert to Decimal later |

### Engine validate_schema() (post-read conversion in base_component.py)

| Type Input | Pandas Dtype | Conversion Method |
|------------|-------------|-------------------|
| `id_String` / `str` | `object` | No conversion |
| `id_Integer` / `int` | `int64` (non-nullable) | `pd.to_numeric(errors='coerce')` then `fillna(0).astype('int64')` when `nullable=True` (inverted logic) |
| `id_Long` / `long` | `int64` (non-nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | `pd.to_numeric(errors='coerce')` |
| `id_Double` / `double` | `float64` | Same as Float |
| `id_Boolean` / `bool` | `bool` | `.astype('bool')` -- **`"false"` string becomes `True`** |
| `id_Date` / `date` | `datetime64[ns]` | `pd.to_datetime()` -- no format specification, uses pandas' flexible parser |
| `id_BigDecimal` / `Decimal` | `object` | No conversion in validate_schema (done in _process BigDecimal block) |

**Key discrepancies**:

1. **Integer nullable inversion**: `_build_dtype_dict()` uses nullable `Int64` but `validate_schema()` converts to non-nullable `int64` with `fillna(0)`. Nulls become 0 when `nullable=True` -- logically inverted but matches Talend behavior.

2. **Boolean string mapping**: `_build_dtype_dict()` maps `id_Boolean` to `object` (read as string). `validate_schema()` then calls `.astype('bool')` which uses Python truthiness: any non-empty string is `True`. The string `"false"` becomes `True` in Python. This differs from Talend where `"false"` maps to `false`.

3. **Type format gap**: `_build_dtype_dict()` maps BOTH `id_Boolean` and `bool` (via separate entries). However, the `bool` key maps to `'object'` (line 163), while `validate_schema()` maps `bool` to `'bool'` (line 335 of base_component.py). This inconsistency means the read-time and validation-time handling differ for boolean columns.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 81-135)

This method validates:
- `filepath` is present and non-empty (required)
- `pattern` is present, non-empty, contains comma-separated positive integers (required)
- `header_rows` is a valid non-negative integer (if present)
- `footer_rows` is a valid non-negative integer (if present)
- `limit` is a valid positive integer (if present, non-empty)

**Not validated**: `encoding`, `row_separator`, `pattern_units`, `advanced_separator`, `trim_all`, `die_on_error`, `check_date`, `uncompress`.

**Pattern validation detail**: Lines 97-106 parse the pattern by splitting on commas, stripping whitespace, filtering empty strings, converting to integers, and checking all values are positive. This is thorough for the pattern validation specifically.

**Limit validation quirk**: Lines 126-133 check `if limit and str(limit).strip()` before attempting `int()` conversion. This means `limit=0` (falsy) would be skipped, and `limit=""` (falsy) would also be skipped. This is actually correct behavior since both `0` and `""` should use the default (unlimited).

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions.

### `_build_dtype_dict()` (Lines 137-175)

Maps Talend types to pandas dtype strings for type enforcement during `pd.read_fwf()`. Supports both Talend format (`id_String`) and Python format (`str`). Returns `None` if no schema is provided, allowing pandas to infer types.

**Notable**: `id_Boolean` is explicitly mapped to `'object'` (line 154) with comment "Read as object, convert later". This is correct design intent but the "convert later" step (in `validate_schema()`) uses `.astype('bool')` which has the Python truthiness bug for string `"false"`.

**Notable**: The `bool` key (line 163) maps to `'object'`, same as `id_Boolean`. This is actually correct -- both paths read booleans as strings initially. The problem is in `validate_schema()` which converts them to `bool` dtype using Python truthiness.

### `_process()` (Lines 177-360)

The main processing method:
1. Extract config values with defaults and type conversion (lines 198-213)
2. Log processing start (line 215)
3. Parse limit value from string to int (lines 218-224)
4. Validate required parameters -- filepath and pattern (lines 227-230)
5. Check file existence; raise or return empty DF (lines 233-241)
6. Parse pattern string to list of integer widths (lines 244-250)
7. Extract column names from schema (lines 253-255)
8. Build dtype dictionary for read-time type enforcement (line 258)
9. Execute `pd.read_fwf()` with all parameters (lines 264-275)
10. Trim string columns if `trim_all=true` (lines 281-285)
11. Remove empty rows if `remove_empty_row=true` (lines 288-293)
12. Fill NaN in string columns with empty string (lines 295-296)
13. Validate schema types via base class (lines 298-300)
14. Apply advanced separator processing (lines 303-307) -- **BUG: should be before step 13**
15. Check date columns if `check_date=true` (lines 310-317) -- **BUG: type comparison broken**
16. Convert BigDecimal columns to Python Decimal (lines 319-326)
17. Calculate and update statistics (lines 329-333)
18. Log completion and return (lines 335-343)
19. Exception handlers: re-raise FileOperationError/ConfigurationError; catch-all with die_on_error support (lines 345-360)

**Config keys read but never used in processing**: `row_separator` (line 199), `pattern_units` (line 201), `uncompress` (line 213).

### `pd.read_fwf()` call (Lines 264-275)

```python
df = pd.read_fwf(
    filepath,
    widths=widths,
    encoding=encoding,
    header=None,
    names=names,
    skiprows=header_rows,
    nrows=nrows,
    skipfooter=footer_rows,
    engine='python' if footer_rows > 0 else None,
    dtype=dtype_dict
)
```

Key observations:
- `header=None` is correct -- prevents pandas from using any row as header
- `engine='python'` required for `skipfooter` -- C engine does not support it
- Missing `keep_default_na=False` -- will convert "NA", "NULL" strings to NaN
- Missing `lineterminator` / `line_terminator` -- though `pd.read_fwf()` may not support this
- Missing `compression` -- needed for `uncompress=true` support
- Missing `chunksize` -- needed for streaming mode

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty file

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0, NB_LINE_OK=0. No error. |
| **V1** | `pd.read_fwf()` on empty file returns empty DataFrame. Stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: File with only header rows

| Aspect | Detail |
|--------|--------|
| **Talend** | If HEADER=3, skips 3 rows, reads 0 data rows. NB_LINE=0. |
| **V1** | `skiprows=3` passed to `pd.read_fwf()`. Returns empty DataFrame with correct columns from schema names. |
| **Verdict** | CORRECT |

### Edge Case 3: Empty pattern string

| Aspect | Detail |
|--------|--------|
| **Talend** | Error -- pattern is mandatory. |
| **V1** | `_validate_config()` would catch this (line 94-95) BUT is never called. `_process()` checks `if not pattern:` (line 229) and raises `ConfigurationError`. |
| **Verdict** | CORRECT (protected by `_process()` check, not by validation method) |

### Edge Case 4: Pattern with non-numeric widths

| Aspect | Detail |
|--------|--------|
| **Talend** | Error during code generation or at runtime. |
| **V1** | `_process()` line 245: `int(x.strip())` raises `ValueError`, caught at line 249, raises `ConfigurationError`. |
| **Verdict** | CORRECT |

### Edge Case 5: Pattern with negative widths

| Aspect | Detail |
|--------|--------|
| **Talend** | Error -- widths must be positive. |
| **V1** | `_validate_config()` checks `any(w <= 0 for w in widths)` (line 103) BUT is never called. `_process()` does NOT check for negative widths -- `pd.read_fwf()` may produce unexpected results or error. |
| **Verdict** | GAP -- negative widths not validated in the live code path. |

### Edge Case 6: Pattern with zero-width column

| Aspect | Detail |
|--------|--------|
| **Talend** | Error or produces empty column. |
| **V1** | Same as Edge Case 5: `_validate_config()` catches `w <= 0` but is dead code. `pd.read_fwf(widths=[5, 0, 3])` behavior is undefined in pandas. |
| **Verdict** | GAP -- zero-width columns not validated in the live code path. |

### Edge Case 7: Pattern column count differs from schema column count

| Aspect | Detail |
|--------|--------|
| **Talend** | If pattern has more widths than schema columns, extra columns are ignored. If fewer, error or undefined. |
| **V1** | `pd.read_fwf(widths=widths, names=names)` -- if `len(widths) != len(names)`, pandas may error or produce misaligned data. No explicit check. |
| **Verdict** | GAP -- no explicit validation that pattern column count matches schema column count. |

### Edge Case 8: NaN handling in non-string columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Null integers default to 0. Null floats remain null. Null strings become empty. |
| **V1** | String NaN -> empty string (line 296). Integer NaN -> `Int64` NA during read, then `fillna(0).astype('int64')` in `validate_schema()`. Float NaN preserved as NaN. |
| **Verdict** | CORRECT for integers and strings. CORRECT for floats. |

### Edge Case 9: Empty DataFrame loses schema

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty result still carries schema metadata. Downstream components know column names/types. |
| **V1** | Missing file (line 241) returns `pd.DataFrame()` -- NO columns. Error path (line 359) same. Downstream components expecting specific columns will KeyError. |
| **Verdict** | GAP -- schema lost on empty results. See BUG-FIP-013, BUG-FIP-014. |

### Edge Case 10: HYBRID streaming mode

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend processes row by row internally. |
| **V1** | Base class `execute()` checks `ExecutionMode.HYBRID` and calls `_auto_select_mode()`. For `input_data=None` (file input), this returns `ExecutionMode.BATCH`. Even if STREAMING were selected, `_execute_streaming()` with `input_data=None` calls `self._process(None)`, which is the same batch path. No actual streaming for positional files. |
| **Verdict** | FUNCTIONAL (falls through to batch correctly) but SUBOPTIMAL (no memory-efficient streaming for large files). |

### Edge Case 11: `_update_global_map()` crash scenario

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A |
| **V1** | When `global_map` is not None, `_update_global_map()` (base_component.py line 304) references undefined `value` variable, causing `NameError`. This crashes AFTER `_process()` completes but BEFORE `execute()` returns. The processed data is lost. |
| **Verdict** | **CRITICAL BUG** -- data processed successfully is lost due to post-processing crash. |

### Edge Case 12: Component status on error

| Aspect | Detail |
|--------|--------|
| **Talend** | Component status reflects success/failure. |
| **V1** | `execute()` sets `self.status = ComponentStatus.RUNNING` (line 192), then `SUCCESS` (line 220) or `ERROR` (line 228). BUT: if `_update_global_map()` crashes (BUG-FIP-001), the exception propagates to the outer `except` block, setting status to `ERROR` even though `_process()` succeeded. Status is misleading. |
| **Verdict** | GAP -- status can show ERROR when processing actually succeeded. |

### Edge Case 13: Boolean string `"false"` conversion

| Aspect | Detail |
|--------|--------|
| **Talend** | `"false"` string in a Boolean column -> `false` boolean value. |
| **V1** | `_build_dtype_dict()` reads as `object` (string). `validate_schema()` calls `.astype('bool')`. Python: `bool("false")` -> `True` (non-empty string). |
| **Verdict** | **BUG** -- `"false"` becomes `True`. See BUG-FIP-006. |

### Edge Case 14: File path with spaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `os.path.exists()` and `pd.read_fwf()` both handle spaces correctly. |
| **Verdict** | CORRECT |

### Edge Case 15: Context variable in filepath resolving to empty

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with clear error. |
| **V1** | `_process()` checks `if not filepath:` (line 228). Raises `ConfigurationError`. |
| **Verdict** | CORRECT |

### Edge Case 16: Advanced separator with schema validation ordering

| Aspect | Detail |
|--------|--------|
| **Talend** | Separator processing happens during parsing, before type conversion. |
| **V1** | Schema validation (line 300) runs BEFORE advanced separator (line 303). A numeric field "1,234,567.89" hits `pd.to_numeric("1,234,567.89")` which returns NaN. Then separator removal on line 306 processes the NaN (now empty string after NaN fill) -- data is lost. |
| **Verdict** | **BUG** -- advanced separator processing order is wrong. See BUG-FIP-005. |

### Edge Case 17: Pattern "5,  4, 5" (extra spaces)

| Aspect | Detail |
|--------|--------|
| **Talend** | Trims whitespace from pattern elements internally. |
| **V1** | Line 245: `int(x.strip())` -- `.strip()` removes whitespace from each element. Handles correctly. |
| **Verdict** | CORRECT |

### Edge Case 18: Pattern "5,,4,5" (empty element between commas)

| Aspect | Detail |
|--------|--------|
| **Talend** | Error or treats empty as zero. |
| **V1** | Line 245: `if x.strip()` filters out empty strings after splitting. Pattern "5,,4,5" becomes `[5, 4, 5]` -- the empty element is silently dropped. This changes the field count without warning. |
| **Verdict** | PARTIAL -- no error raised, but silent column count change may cause schema mismatch. |

### Edge Case 19: Thread safety with shared global_map

| Aspect | Detail |
|--------|--------|
| **Talend** | Talend uses synchronized globalMap in Java. |
| **V1** | `GlobalMap.put()` and `GlobalMap.get()` are not synchronized. Multiple components writing stats concurrently could corrupt the map. Python GIL provides some protection for CPython, but not guaranteed for all operations. |
| **Verdict** | GAP -- acceptable for single-threaded model, risky for future parallelism. |

### Edge Case 20: Type demotion (Int64 -> int64)

| Aspect | Detail |
|--------|--------|
| **Talend** | Integer columns with null values use Java Integer (nullable). |
| **V1** | `_build_dtype_dict()` reads as `Int64` (nullable). `validate_schema()` converts to `int64` (non-nullable) with `fillna(0)`. Null integers become 0. This is a type demotion -- losing nullability information. |
| **Verdict** | MATCHES Talend default behavior (null -> 0), but loses the ability to distinguish "actual 0" from "was null". Acceptable for Talend compatibility. |

### Edge Case 21: `validate_schema()` nullable inversion

| Aspect | Detail |
|--------|--------|
| **Talend** | Nullable columns accept null. Non-nullable columns reject null rows. |
| **V1** | Line 351 of base_component.py: `if pandas_type == 'int64' and col_def.get('nullable', True)` triggers `fillna(0).astype('int64')`. When nullable=True (default): nulls become 0. When nullable=False: the `if` is False, so nulls are PRESERVED as NaN/float64. This is semantically inverted: nullable columns lose their nulls, non-nullable columns keep them. |
| **Verdict** | **BUG** (semantically) but accidentally matches Talend behavior for the nullable=True default case. Breaks for explicit nullable=False columns. See BUG-FIP-015. |

### Edge Case 22: `keep_default_na` not set

| Aspect | Detail |
|--------|--------|
| **Talend** | Treats "NA", "NULL", "None" as literal strings. |
| **V1** | `pd.read_fwf()` without `keep_default_na=False` converts these strings to NaN. A positional field containing "NA" (e.g., Namibia country code) becomes NaN and then empty string after NaN fill (line 296). Data loss. |
| **Verdict** | GAP -- literal strings silently lost. `FileInputDelimited` correctly sets `keep_default_na=False` but `FileInputPositional` does not. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileInputPositional`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FIP-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when `global_map` is set. |
| BUG-FIP-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-FIP-004 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |
| BUG-FIP-006 | **P2** | `base_component.py:354` | `validate_schema()` boolean conversion uses Python truthiness: `"false".astype('bool')` -> `True`. Affects ALL components with boolean schema columns. |
| BUG-FIP-015 | **P2** | `base_component.py:351` | `validate_schema()` nullable logic inverted: nullable=True triggers fillna(0), nullable=False preserves NaN. Logic semantics are backwards even though Talend behavior is matched for the default case. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FIP-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FIP-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FIP-005 -- Advanced separator ordering

**File**: `src/v1/engine/components/file/file_input_positional.py`
**Lines**: 298-307

**Current code (broken ordering)**:
```python
# Validate schema
if self.output_schema:
    logger.debug(f"[{self.id}] Validating schema")
    df = self.validate_schema(df, self.output_schema)

# Advanced separator: convert thousands/decimal if needed
if advanced_separator:
    logger.debug(f"[{self.id}] Applying advanced separators")
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].str.replace(thousands_separator, '', regex=False)
        df[col] = df[col].str.replace(decimal_separator, '.', regex=False)
```

**Fix (swap order)**:
```python
# Advanced separator: convert thousands/decimal if needed (MUST be before schema validation)
if advanced_separator:
    logger.debug(f"[{self.id}] Applying advanced separators")
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].str.replace(thousands_separator, '', regex=False)
        df[col] = df[col].str.replace(decimal_separator, '.', regex=False)

# Validate schema (now numeric strings are clean for pd.to_numeric)
if self.output_schema:
    logger.debug(f"[{self.id}] Validating schema")
    df = self.validate_schema(df, self.output_schema)
```

**Impact**: Makes `advanced_separator=true` functional for numeric columns. **Risk**: Low.

---

### Fix Guide: BUG-FIP-006 -- Boolean string conversion

**File**: `src/v1/engine/base_component.py`
**Line**: 354

**Current code (broken)**:
```python
elif pandas_type == 'bool':
    df[col_name] = df[col_name].astype('bool')
```

**Fix**:
```python
elif pandas_type == 'bool':
    # Handle string representations of booleans correctly
    bool_map = {'true': True, 'false': False, '1': True, '0': False,
                'yes': True, 'no': False, 'y': True, 'n': False}
    df[col_name] = df[col_name].apply(
        lambda x: bool_map.get(str(x).lower().strip(), bool(x)) if pd.notna(x) else False
    )
```

**Impact**: Fixes boolean conversion for ALL components (cross-cutting). **Risk**: Medium (changes behavior for existing boolean columns).

---

### Fix Guide: BUG-FIP-013/014 -- Empty DataFrame schema preservation

**File**: `src/v1/engine/components/file/file_input_positional.py`
**Lines**: 241, 359

**Current code (broken)**:
```python
return {'main': pd.DataFrame()}
```

**Fix**:
```python
if self.output_schema:
    empty_cols = [c['name'] for c in self.output_schema]
    return {'main': pd.DataFrame(columns=empty_cols)}
return {'main': pd.DataFrame()}
```

**Impact**: Preserves schema structure for downstream components. Apply at BOTH line 241 and line 359. **Risk**: Very low.

---

### Fix Guide: BUG-FIP-007 -- check_date type comparison

**File**: `src/v1/engine/components/file/file_input_positional.py`
**Line**: 313

**Current code (broken)**:
```python
if col.get('type', '').lower() == 'date':
```

**Fix**:
```python
if col.get('type', '').lower() in ('date', 'datetime', 'id_date'):
```

**Impact**: Enables check_date for converter-produced schemas. **Risk**: Very low.

---

### Fix Guide: ENG-FIP-003 -- Wire up row_separator

**File**: `src/v1/engine/components/file/file_input_positional.py`

`pd.read_fwf()` does not directly support a `lineterminator` parameter like `pd.read_csv()` does. The fix requires pre-processing the file:

```python
# After file existence check, before pd.read_fwf()
if row_separator != '\n' and row_separator != self.DEFAULT_ROW_SEPARATOR:
    logger.debug(f"[{self.id}] Custom row separator detected: {repr(row_separator)}")
    with open(filepath, 'r', encoding=encoding) as f:
        content = f.read()
    # Normalize row separator to \n
    content = content.replace(row_separator, '\n')
    # Use StringIO to feed normalized content to read_fwf
    import io
    filepath_or_buffer = io.StringIO(content)
else:
    filepath_or_buffer = filepath

# Then use filepath_or_buffer instead of filepath in pd.read_fwf()
```

**Impact**: Enables custom row separators. **Risk**: Medium (loads entire file into memory for non-standard separators).

---

### Fix Guide: ENG-FIP-001 -- Implementing REJECT flow

**File**: `src/v1/engine/components/file/file_input_positional.py`

**Step 1**: After `pd.read_fwf()` and before post-processing, add row-level validation:
```python
reject_rows = []
if self.output_schema:
    for idx, row in df.iterrows():
        try:
            for col_def in self.output_schema:
                col_name = col_def['name']
                col_type = col_def.get('type', 'id_String')
                # Validate type conversion would succeed
                # ... type-specific validation
        except Exception as e:
            reject_rows.append({
                **row.to_dict(),
                'errorCode': 'TYPE_CONVERSION',
                'errorMessage': str(e)
            })
            df = df.drop(idx)
```

**Step 2**: Build reject DataFrame and update stats:
```python
reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()
self._update_stats(rows_in, len(df), len(reject_rows))
return {'main': df, 'reject': reject_df}
```

**Impact**: Enables data quality pipelines. **Risk**: Medium (requires downstream components to handle `reject` key; row-by-row iteration is slow for large files).

---

### Fix Guide: CONV-FIP-001 -- Dedicated converter parser

**File 1**: `src/converters/complex_converter/converter.py`

Add between the existing `elif` branches (after `tFileOutputPositional` on line 378, before `tOracleConnection` on line 379):
```python
elif component_type == 'tFileInputPositional':
    component = self.component_parser.parse_file_input_positional(node, component)
```

**File 2**: `src/converters/complex_converter/component_parser.py`

Add a new method `parse_file_input_positional(self, node, component)` that:
1. Extracts all existing parameters (lines 150-171 of `_map_component_parameters`)
2. Additionally parses CUSTOMIZE table parameter for per-column settings
3. Extracts `USE_BYTE_LENGTH`
4. Returns enhanced component dict

**Impact**: Enables full parameter extraction including CUSTOMIZE table parameter. **Risk**: Low.

---

### Fix Guide: Missing `keep_default_na=False`

**File**: `src/v1/engine/components/file/file_input_positional.py`
**Line**: 264

**Current code**:
```python
df = pd.read_fwf(
    filepath,
    widths=widths,
    encoding=encoding,
    header=None,
    names=names,
    skiprows=header_rows,
    nrows=nrows,
    skipfooter=footer_rows,
    engine='python' if footer_rows > 0 else None,
    dtype=dtype_dict
)
```

**Fix (add `keep_default_na=False`)**:
```python
df = pd.read_fwf(
    filepath,
    widths=widths,
    encoding=encoding,
    header=None,
    names=names,
    skiprows=header_rows,
    nrows=nrows,
    skipfooter=footer_rows,
    engine='python' if footer_rows > 0 else None,
    dtype=dtype_dict,
    keep_default_na=False
)
```

**Impact**: Prevents literal strings like "NA", "NULL", "None" from being silently converted to NaN. Matches `FileInputDelimited` behavior and Talend behavior. **Risk**: Very low (only affects files containing these specific strings).

---

## Appendix I: Comparison with tFileInputDelimited

Key differences between `FileInputPositional` and `FileInputDelimited` implementations:

| Aspect | FileInputDelimited | FileInputPositional |
|--------|-------------------|---------------------|
| Core pandas function | `pd.read_csv()` | `pd.read_fwf()` |
| Lines of code | 575 | 359 |
| Streaming mode | Yes (`_read_streaming()`) | **No** |
| Single-string mode | Yes (`_read_as_single_string()`) | No (not applicable) |
| CSV options | Yes (quoting, escape) | No (not applicable) |
| Delimiter handling | Complex (tab, regex, multi-char) | N/A (pattern-based) |
| Pattern handling | N/A | Yes (comma-separated widths) |
| Advanced separator | Not extracted by converter | Extracted AND implemented (with ordering bug) |
| Check date | Not extracted by converter | Extracted AND partially implemented (with type comparison bug) |
| `_validate_config()` | Dead code | Dead code |
| Config keys extracted | 12 of 30 (40%) | 17 of 23 (74%) |
| Config keys functional | 12 of 12 (100%) | 13 of 17 (76%) -- 4 extracted but unused |
| Remove empty rows key | `remove_empty_rows` (plural) | `remove_empty_row` (singular) |
| `keep_default_na=False` | Set (correct) | **NOT set (gap)** |
| BigDecimal support | Yes | Yes |
| Footer skip | Yes (forces Python engine) | Yes (forces Python engine) |
| Default die_on_error | `True` (engine), `False` (converter) | `True` (engine), `False` (converter) |

**Notable gap**: `FileInputPositional` does NOT set `keep_default_na=False` in its `pd.read_fwf()` call, unlike `FileInputDelimited` which correctly sets it. This means strings like "NA", "NULL", "None" in positional files will be converted to pandas NaN, which differs from Talend behavior (Talend treats these as literal strings).

---

## Appendix J: `pd.read_fwf()` Parameter Utilization

| pd.read_fwf Parameter | Used? | Engine Line | Notes |
|------------------------|-------|-------------|-------|
| `filepath_or_buffer` | Yes | 265 | File path from config |
| `widths` | Yes | 266 | Parsed from pattern string |
| `encoding` | Yes | 267 | From config with UTF-8 default |
| `header` | Yes | 268 | Always `None` (schema-defined columns) |
| `names` | Yes | 269 | Column names from output_schema |
| `skiprows` | Yes | 270 | From `header_rows` config |
| `nrows` | Yes | 271 | From `limit` config |
| `skipfooter` | Yes | 272 | From `footer_rows` config |
| `engine` | Yes | 273 | `'python'` when footer_rows > 0, else None |
| `dtype` | Yes | 274 | From `_build_dtype_dict()` |
| `keep_default_na` | **No** | -- | **Should be `False` for Talend compatibility** |
| `na_values` | **No** | -- | Uses pandas default NA detection (includes "NA", "NULL") |
| `lineterminator` | **No** | -- | Not supported by `pd.read_fwf()` directly |
| `chunksize` | **No** | -- | Would enable streaming mode |
| `compression` | **No** | -- | Would enable compressed file support |
| `comment` | **No** | -- | Not applicable for positional files |
| `colspecs` | **No** | -- | Alternative to `widths` (start, end pairs) |
| `converters` | **No** | -- | Could replace post-processing type conversion |
| `infer_nrows` | **No** | -- | Not relevant when explicit `widths` provided |

---

## Appendix K: Missing `keep_default_na=False` Impact

`pd.read_fwf()` default `keep_default_na=True` causes the following strings to be treated as NaN:

| String | Becomes NaN? | Talend Treatment |
|--------|-------------|------------------|
| `"NA"` | Yes | Literal string "NA" |
| `"NULL"` | Yes | Literal string "NULL" |
| `"None"` | Yes | Literal string "None" |
| `"NaN"` | Yes | Literal string "NaN" |
| `"null"` | Yes | Literal string "null" |
| `"N/A"` | Yes | Literal string "N/A" |
| `""` | Yes | Empty string |
| `"#N/A"` | Yes | Literal string "#N/A" |
| `"#NA"` | Yes | Literal string "#NA" |
| `"-NaN"` | Yes | Literal string "-NaN" |
| `"-nan"` | Yes | Literal string "-nan" |
| `"1.#IND"` | Yes | Literal string "1.#IND" |
| `"1.#QNAN"` | Yes | Literal string "1.#QNAN" |
| `"<NA>"` | Yes | Literal string "<NA>" |
| `"n/a"` | Yes | Literal string "n/a" |
| `"nan"` | Yes | Literal string "nan" |

**Fix**: Add `keep_default_na=False` to the `pd.read_fwf()` call on line 264. This prevents pandas from converting these literal strings to NaN, matching Talend behavior where these are preserved as-is.

This is a significant data quality issue: a positional file containing "NA" in a string field (e.g., state abbreviation for Namibia, or "Not Applicable") would silently lose data.

---

## Appendix L: Positional File Format Specifics

### What Makes Positional Files Different from Delimited

Positional (fixed-width) files are fundamentally different from delimited files and present unique challenges for the engine:

| Characteristic | Delimited Files | Positional Files |
|---------------|-----------------|------------------|
| **Field boundaries** | Marked by delimiter characters | Defined by character position (column widths) |
| **Field padding** | No padding (fields are variable length) | Fields are padded to fixed width (spaces, zeros, etc.) |
| **Quoting** | Fields may be quoted to embed delimiters | No quoting needed (fields cannot contain "delimiters") |
| **Multi-line fields** | Possible with quoting (RFC4180) | Never -- each line is exactly one record |
| **Typical sources** | Modern systems, databases, APIs | Legacy/mainframe systems, COBOL, banking, government |
| **File size** | Variable (depends on data) | Predictable (each row is same byte length) |
| **Encoding sensitivity** | Moderate | High (byte width vs character width matters for multi-byte) |
| **Trim importance** | Optional (data usually not padded) | **Critical** (fields are always padded) |

### Common Positional File Patterns in Talend Jobs

Based on typical Talend enterprise usage:

1. **Mainframe data extracts**: COBOL copybook-defined layouts with packed decimal, COMP fields, and EBCDIC encoding. These files often have very long rows (100+ fields, 1000+ characters per row), requiring `PROCESS_LONG_ROW=true`.

2. **Banking/financial files**: Fixed-format transaction records (SWIFT, NACHA, BAI2). Fields are strictly typed with specific padding: numeric fields are left-padded with zeros, text fields are right-padded with spaces. The `CUSTOMIZE` feature is essential for stripping this padding correctly.

3. **Government data feeds**: Census, regulatory, and reporting files often use positional format. These may contain multi-byte characters (accented names, international addresses), requiring correct `PATTERN_UNITS` and `USE_BYTE_LENGTH` settings.

4. **Legacy system integration**: Files from AS/400, iSeries, or other legacy systems. Often use specific encodings (EBCDIC, CP1252, ISO-8859-1) and custom row separators.

5. **Log file parsing**: Fixed-width log formats where each field occupies a predetermined number of characters. These are typically ASCII/UTF-8 with standard `\n` row separators.

### Impact of Missing Features on Common Use Cases

| Use Case | Missing Feature | Impact |
|----------|----------------|--------|
| Mainframe extracts | `PROCESS_LONG_ROW` | Very long rows may truncate silently |
| Mainframe extracts | `PATTERN_UNITS=Bytes` | Multi-byte character fields misaligned |
| Banking files | `CUSTOMIZE` (padding) | Zero-padded numbers retain leading zeros (e.g., "000042" instead of 42) |
| Banking files | `CUSTOMIZE` (alignment) | Right-aligned numeric fields not properly parsed |
| Government feeds | `USE_BYTE_LENGTH` | Multi-byte character widths incorrect |
| Legacy systems | Custom `row_separator` | Files with `\r` only separators fail to parse |
| All use cases | `REJECT` flow | Malformed records lost instead of captured |

---

## Appendix M: Base Class Lifecycle and FileInputPositional

### Execution Flow Through BaseComponent.execute()

```
execute(input_data=None)
    |
    +--> self.status = ComponentStatus.RUNNING
    |
    +--> Step 1: Resolve Java expressions (if java_bridge)
    |    +--> _resolve_java_expressions()
    |         Scans config for {{java}} markers, executes via Java bridge
    |
    +--> Step 2: Resolve context variables (if context_manager)
    |    +--> self.config = self.context_manager.resolve_dict(self.config)
    |         Replaces ${context.var} with resolved values
    |
    +--> Step 3: Determine execution mode
    |    +--> _auto_select_mode(input_data=None)
    |         Returns BATCH (input_data is None for file input)
    |
    +--> Step 4: Execute
    |    +--> _execute_batch(input_data=None)
    |         +--> _process(input_data=None)   <-- FileInputPositional._process()
    |              +--> Read config values
    |              +--> Validate filepath, pattern
    |              +--> Check file existence
    |              +--> Parse pattern to widths
    |              +--> pd.read_fwf(...)
    |              +--> Post-process (trim, empty rows, NaN fill)
    |              +--> validate_schema()
    |              +--> Advanced separator (WRONG ORDER)
    |              +--> Check date (BROKEN type check)
    |              +--> BigDecimal conversion
    |              +--> _update_stats()
    |              +--> Return {'main': df}
    |
    +--> Step 5: Update stats timing
    |    +--> self.stats['EXECUTION_TIME'] = elapsed
    |
    +--> Step 6: Update global map
    |    +--> _update_global_map()   <-- CRASHES (BUG-FIP-001)
    |         +--> for stat_name, stat_value in self.stats.items():
    |         |    global_map.put_component_stat(id, stat_name, stat_value)
    |         +--> logger.info(...{value}...)  <-- NameError: 'value' undefined
    |
    +--> Step 7: Set status
    |    +--> self.status = ComponentStatus.SUCCESS   <-- NEVER REACHED if step 6 crashes
    |
    +--> Step 8: Return result
         +--> result['stats'] = self.stats.copy()
         +--> return result
```

### Key Observations from Lifecycle Analysis

1. **Steps 1 and 2 run BEFORE `_process()`**: Java expressions and context variables are resolved in config BEFORE the component's `_process()` reads config values. This means `_process()` sees resolved values, not markers.

2. **Step 3 always returns BATCH for file input**: Since `input_data=None` for file input components, `_auto_select_mode()` always returns `BATCH`. The HYBRID/STREAMING modes are irrelevant for this component.

3. **Step 6 crashes with P0 bug**: The `_update_global_map()` method crashes due to undefined `value` variable. This means:
   - GlobalMap stats are partially written (the loop writes them before the log statement)
   - The exception propagates to the outer try/except
   - Status is set to `ERROR` even though `_process()` succeeded
   - The successfully processed DataFrame is LOST (never returned)

4. **No `_validate_config()` call anywhere in the lifecycle**: Neither `__init__()`, `execute()`, nor `_process()` calls `_validate_config()`. The only validation happens inline in `_process()` (checking filepath and pattern non-empty).

5. **`_update_stats()` called inside `_process()`**: Statistics are accumulated BEFORE `execute()` adds timing. This is correct -- `_process()` knows the row counts, `execute()` knows the timing.

---

## Appendix N: Detailed `_build_dtype_dict()` Analysis

### Type Mapping Table (Lines 148-166)

```python
type_mapping = {
    'id_String': 'object',
    'id_Integer': 'Int64',      # Nullable integer
    'id_Long': 'Int64',
    'id_Float': 'float64',
    'id_Double': 'float64',
    'id_Boolean': 'object',     # Read as object, convert later
    'id_Date': 'object',        # Read as object, convert later
    'id_BigDecimal': 'object',  # Read as string, convert to Decimal later
    # Simple type names
    'str': 'object',
    'int': 'Int64',
    'long': 'Int64',
    'float': 'float64',
    'double': 'float64',
    'bool': 'object',
    'date': 'object',
    'Decimal': 'object'
}
```

### Key Design Decisions

1. **Nullable `Int64` for integers**: Using pandas nullable `Int64` (capital I) instead of numpy `int64` allows NaN values during reading. Without this, a column with any missing integer values would fail to read with `int64` dtype. This is the correct approach.

2. **`object` for booleans**: Reading booleans as strings (object) and converting later is the correct design pattern -- it avoids pandas' automatic boolean parsing which has different semantics than Talend. However, the "convert later" step in `validate_schema()` uses `.astype('bool')` which relies on Python truthiness, creating the `"false"` -> `True` bug.

3. **`object` for dates**: Reading dates as strings and converting later via `pd.to_datetime()` is correct. This allows the date pattern from the schema to be applied during conversion.

4. **`object` for BigDecimal**: Reading as strings and converting to `Decimal` later preserves full precision. Direct float64 reading would lose precision for high-precision decimal values.

5. **Dual type format support**: The mapping handles both Talend format (`id_String`) and Python format (`str`). This accommodates both raw Talend schemas and converter-produced schemas. However, the `bool` entry (line 163) maps to `'object'`, while in `validate_schema()` the `bool` key maps to `'bool'` dtype -- this inconsistency creates a double-conversion: read as object, then convert to bool.

### Missing Types

| Type | In Talend? | In `_build_dtype_dict()`? | Notes |
|------|-----------|--------------------------|-------|
| `id_Character` | Yes | **No** | Falls through to default `object` -- correct behavior |
| `id_Byte` | Yes | **No** | Falls through to default `object` -- should map to `Int64` |
| `id_Short` | Yes | **No** | Falls through to default `object` -- should map to `Int64` |
| `id_Object` | Yes | **No** | Falls through to default `object` -- correct behavior |
| `datetime` | Converter output | **No** | Falls through to default `object` -- should map to `object` (same as `date`) |

The fallthrough to default `object` is safe but less efficient than explicit `Int64` for `id_Byte` and `id_Short`, as they would be read as strings and then converted in `validate_schema()` rather than being read as integers directly.

---
