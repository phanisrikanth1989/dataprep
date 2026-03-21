# Audit Report: tFileInputDelimited / FileInputDelimited

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputDelimited` |
| **V1 Engine Class** | `FileInputDelimited` |
| **Engine File** | `src/v1/engine/components/file/file_input_delimited.py` (575 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 109-126) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Registry Aliases** | `FileInputDelimited`, `tFileInputDelimited` (registered in `src/v1/engine/engine.py` lines 58-59) |
| **Category** | File / Input |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_delimited.py` | Engine implementation (575 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 109-126) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (lines 64-68) | Dispatch -- no dedicated `elif` for `tFileInputDelimited`; uses generic `parse_base_component()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 4 | 4 | 1 | 12 of 30 Talend params extracted (40%); missing CSV_OPTION, SPLITRECORD, UNCOMPRESS, etc.; deprecated generic mapper |
| Engine Feature Parity | **Y** | 1 | 5 | 3 | 1 | No REJECT flow; missing globalMap vars; no compressed/RFC4180; no CHECK_FIELDS_NUM/CHECK_DATE |
| Code Quality | **Y** | 2 | 2 | 5 | 2 | Cross-cutting base class bugs; dead `_validate_config()`; single-string DF creation bug |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | Streaming mode works; minor optimization opportunities in post-processing and engine selection |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputDelimited Does

`tFileInputDelimited` reads a character-delimited flat file (CSV, TSV, pipe-separated, semicolon-separated, etc.) and outputs rows as a data flow. It is the single most commonly used input component in Talend, present in the vast majority of data integration jobs. The component opens a file, reads it row by row, splits each row into fields based on the configured delimiter, and sends the fields as defined in the output schema to downstream components via a Row link.

**Source**: [tFileInputDelimited Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-standard-properties), [Component-specific settings (Job Script Reference Guide)](https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/component-specific-settings-for-tfileinputdelimited), [Talend Component Properties File (GitHub)](https://github.com/EDS-APHP/TalendComponents/blob/master/tFileInputDelimitedAPHP/tFileInputDelimitedAPHP_messages_en.properties)

**Component family**: Delimited (File / Input)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.
**Required JARs**: `talend_file_enhanced-1.1.jar`, `talendcsv-1.0.0.jar`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. |
| 3 | File Name / Stream | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path or data stream variable (e.g., `tFileFetch_1_INPUT_STREAM`). Supports context variables, globalMap references, Java expressions. |
| 4 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | Character(s) identifying the end of a row. Supports `\r\n`, `\n`, `\r`. Can be multi-character. |
| 5 | Field Separator | `FIELDSEPARATOR` | String / Regex | `";"` | Delimiter separating fields. Can be a character, string, or regular expression. When `CSV_OPTION=true`, must be single character. **Note**: Talend default is semicolon, not comma. |
| 6 | CSV Options | `CSV_OPTION` | Boolean (CHECK) | `false` | Enables RFC4180 CSV mode: activates escape char and text enclosure fields. When enabled, field separator must be a single character (regex not allowed). |
| 7 | Escape Char | `ESCAPE_CHAR` | Character | `"\\"` | Escape character for metacharacters inside quoted fields. Only visible when `CSV_OPTION=true`. Standard is backslash. |
| 8 | Text Enclosure | `TEXT_ENCLOSURE` | Character | `"\""` | Single character wrapping field values. Only visible when `CSV_OPTION=true`. Standard is double-quote. |
| 9 | Header | `HEADER` | Integer | `0` | Number of rows to skip at the beginning of the file. These rows are completely discarded -- NOT used for column naming (schema defines column names). |
| 10 | Footer | `FOOTER` | Integer | `0` | Number of rows to skip at the end of the file. Requires reading the entire file to determine the last N rows. |
| 11 | Limit | `LIMIT` | Integer | `0` | Maximum number of rows to read. `0` = unlimited (read all rows). Applies after header skip. |
| 12 | Skip Empty Rows | `REMOVE_EMPTY_ROW` | Boolean (CHECK) | `false` | Skip rows where all fields are empty/blank. |
| 13 | Uncompress | `UNCOMPRESS` | Boolean (CHECK) | `false` | Transparently decompress ZIP or GZIP compressed input files via Java's `GZIPInputStream`/`ZipInputStream`. Decompression happens before parsing. |
| 14 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on read/parse error. When unchecked, malformed rows are routed to the REJECT flow (if connected) or silently dropped. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 15 | Encoding | `ENCODING` | Dropdown / Custom | `"ISO-8859-15"` | Character encoding for file reading. Options include ISO-8859-15, UTF-8, and custom values. **Note**: Talend default is `ISO-8859-15`, NOT `UTF-8`. JVM-dependent support for encoding names. |
| 16 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands and decimal separators. |
| 17 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 18 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 19 | Extract Lines at Random | `RANDOM` | Boolean (CHECK) | `false` | Enable random line extraction mode instead of sequential reading. |
| 20 | Number of Random Lines | `NB_RANDOM` | Integer | -- | Number of lines to extract randomly. Only visible when `RANDOM=true`. |
| 21 | Trim All Columns | `TRIMALL` | Boolean (CHECK) | `false` | Remove leading and trailing whitespace from ALL string fields in every column. |
| 22 | Check Columns to Trim | `TRIMSELECT` | Table (SCHEMA_COLUMN, TRIM) | -- | Per-column trim configuration. Auto-populated from schema. Allows selective trimming when `TRIMALL` is unchecked. Each row maps a schema column to a boolean trim flag. |
| 23 | Check Row Structure | `CHECK_FIELDS_NUM` | Boolean (CHECK) | `false` | Validate that each row has the same number of fields as defined in the schema. Rows that fail are routed to REJECT. If a row has too many or too few fields, it is considered malformed. |
| 24 | Check Date | `CHECK_DATE` | Boolean (CHECK) | `false` | Strictly validate date-typed columns against the date pattern defined in the input schema. Invalid dates cause row rejection (routed to REJECT). |
| 25 | Split Record | `SPLITRECORD` | Boolean (CHECK) | `false` | Allow fields to span multiple physical lines (split rows before splitting fields). This is mandatory for proper RFC4180 CSV compliance when fields contain embedded newlines (e.g., `"line1\nline2"`). Without it, embedded newlines create separate rows. |
| 26 | Permit Hex/Octal | `ENABLE_DECODE` | Boolean (CHECK) | `false` | Parse numeric types (long, integer, short, byte) from hexadecimal (`0xNNN`) or octal (`0NNNN`) string representations. |
| 27 | Decode Columns | `DECODE_COLS` | Table (SCHEMA_COLUMN, DECODE) | -- | Specify which columns to decode from hex/octal format. Only visible when `ENABLE_DECODE=true`. |
| 28 | CSV Row Separator | `CSVROWSEPARATOR` | String | -- | CSV-specific row separator used when `CSV_OPTION=true`. Overrides the standard `ROWSEPARATOR` in CSV mode. |
| 29 | Min Column Number for Optimize Code | `SCHEMA_OPT_NUM` | Integer | `100` | Performance optimization threshold: when schema has more columns than this value, Talend generates optimized code. Not a user-facing setting in most cases. |
| 30 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 31 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully parsed rows matching the output schema. All columns defined in the schema are present. Primary data output. |
| `REJECT` | Output | Row > Reject | Rows that failed parsing, type conversion, or structural validation. Includes ALL original schema columns (with whatever partial data was parsed) PLUS two additional columns: `errorCode` (String) and `errorMessage` (String). These extra columns appear in green in Talend Studio to distinguish them. Only active when `DIE_ON_ERROR=false`. |
| `ITERATE` | Output | Iterate | Enables iterative processing when the component is used with iteration components like `tFlowToIterate`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows read from the file (data rows, after header skip, before REJECT filtering). This is the primary row count variable. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output via the FLOW (Main) connection. Equals `NB_LINE - NB_LINE_REJECT`. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to the REJECT flow (due to parse errors, type mismatches, structural validation failures). Zero when no REJECT link is connected. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

**Note on CURRENT_LINE**: Some community sources reference `{id}_CURRENT_LINE` as a row-level counter available during iteration. Official Talend documentation lists only `NB_LINE` and `ERROR_MESSAGE` as After-scope global variables. The `CURRENT_LINE` variable is not officially documented but may be available through the Talend runtime in certain contexts. For row-level tracking within the flow, `tSetGlobalVar` or `tJavaRow` is the recommended approach.

**Note on FILENAME**: Official documentation does not list `{id}_FILENAME` as a standard global variable for this component. The resolved file path can be accessed through the component's `FILENAME` property expression in Talend Studio, but it is not automatically stored in globalMap. When iterating with `tFileList`, the file path is available via `tFileList_1_CURRENT_FILE` instead.

### 3.5 Behavioral Notes

1. **HEADER behavior**: When `HEADER > 0`, Talend skips that many rows at the TOP of the file, then uses the SCHEMA column names -- NOT the file header row. The header rows are completely discarded and never used for column naming. This is a common source of confusion for users expecting the first row to define column names.

2. **REJECT flow behavior**: When a REJECT link is connected and `DIE_ON_ERROR=false`:
   - Rows that fail type conversion, date validation, or structural checks are sent to REJECT
   - REJECT rows contain ALL original schema columns (with whatever partial data was parsed) PLUS `errorCode` (String) and `errorMessage` (String) columns
   - The `errorCode` and `errorMessage` columns appear in green in Talend Studio
   - When REJECT is NOT connected, errors are silently dropped or cause job failure depending on `DIE_ON_ERROR`
   - If you do not need the error columns, they can be deleted from the reject schema

3. **SPLITRECORD=true**: Allows quoted fields to contain embedded newlines. The field spans multiple physical lines. This is mandatory for proper RFC4180 CSV compliance. Without it, a field like `"line1\nline2"` would be parsed as two separate rows, corrupting data. Common in address fields, descriptions, JSON snippets.

4. **UNCOMPRESS=true**: Transparently reads `.gz` and `.zip` files via Java's `GZIPInputStream` or `ZipInputStream`. The decompression happens before any parsing. File extension is used to auto-detect compression type.

5. **LIMIT=0 or empty**: Means no limit -- read ALL rows. This differs from some implementations where `0` might mean "read zero rows." Talend documentation explicitly states: "maximum number of rows to be processed; 0 means no limit."

6. **CHECK_FIELDS_NUM=true**: If a row has more or fewer fields than schema columns, it goes to REJECT (if connected) or causes an error. This is important for data quality validation of source files.

7. **CHECK_DATE=true**: Date-typed columns are strictly validated against the pattern defined in the schema. Invalid dates cause the entire row to be rejected to the REJECT flow.

8. **CSV_OPTION=true**: Enables proper RFC4180 CSV parsing with text enclosure and escape character. When enabled, the field separator MUST be a single character (not regex). This mode handles embedded delimiters within quoted fields correctly.

9. **Default encoding**: Talend defaults to `ISO-8859-15`, NOT `UTF-8`. This is a critical behavioral difference from most Python library defaults. If a Talend job does not explicitly set encoding, it uses `ISO-8859-15`.

10. **Default field separator**: Talend defaults to `";"` (semicolon), NOT `","` (comma). This is important for European data formats where semicolon is the standard CSV delimiter.

11. **Dynamic schema**: Talend supports a dynamic schema feature where unknown columns are captured automatically. When `Use existing dynamic` is enabled, the component uses a schema from `tSetDynamicSchema`. Dynamic schema always treats the first row as a header regardless of the `HEADER` setting.

12. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow -- only in subsequent subjobs connected via triggers. To get row count within the same subjob, use `tFileRowCount` instead.

13. **Non-nullable primitive fields**: When a non-nullable primitive field (int, long, float, double) encounters a null value, the row is rejected. This is a common source of reject rows in production Talend jobs.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the **deprecated generic parameter mapping approach** (`_map_component_parameters()` in `component_parser.py` lines 109-126) rather than a dedicated `parse_file_input_delimited()` method. There is NO dedicated `elif component_type == 'tFileInputDelimited'` branch in `converter.py:_parse_component()`. The component falls through to the generic `parse_base_component()` path.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tFileInputDelimited', config_raw)` (line 472)
4. Returns mapped config with renamed keys
5. Schema is extracted generically from `<metadata connector="FLOW">` and `<metadata connector="REJECT">` nodes

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | 114 | Expressions and context vars handled by generic loop |
| 2 | `FIELDSEPARATOR` | Yes | `delimiter` | 115 | **Default `','` differs from Talend default `';'`** |
| 3 | `ROWSEPARATOR` | Yes | `row_separator` | 116 | Default `'\n'` matches Talend |
| 4 | `HEADER` | Yes | `header_rows` | 117 | Converted to int via `.isdigit()` -- rejects negative values and expressions |
| 5 | `FOOTER` | Yes | `footer_rows` | 118 | Same `.isdigit()` conversion as HEADER |
| 6 | `LIMIT` | Yes | `limit` | 119 | Passed as raw string, engine handles int conversion |
| 7 | `ENCODING` | Yes | `encoding` | 120 | **Default `'UTF-8'` differs from Talend default `'ISO-8859-15'`** |
| 8 | `TEXT_ENCLOSURE` | Yes | `text_enclosure` | 121 | Strips escaped quotes via `.replace('\\\"', '')` |
| 9 | `ESCAPE_CHAR` | Yes | `escape_char` | 122 | Complex double-replace: `.replace('\\\\', '').replace('\\\\\\', '\\')` |
| 10 | `REMOVE_EMPTY_ROW` | Yes | `remove_empty_rows` | 123 | Boolean from CHECK field type |
| 11 | `TRIMALL` | Yes | `trim_all` | 124 | Boolean from CHECK field type |
| 12 | `DIE_ON_ERROR` | Yes | `die_on_error` | 125 | Boolean from CHECK field type. Default `False` matches Talend |
| 13 | `CSV_OPTION` | **No** | -- | -- | **Not extracted. Engine has no RFC4180 toggle.** |
| 14 | `SPLITRECORD` | **No** | -- | -- | **Not extracted. No multi-line field support toggle.** |
| 15 | `UNCOMPRESS` | **No** | -- | -- | **Not extracted. No compressed file reading.** |
| 16 | `CHECK_FIELDS_NUM` | **No** | -- | -- | **Not extracted. No row structure validation.** |
| 17 | `CHECK_DATE` | **No** | -- | -- | **Not extracted. No strict date validation.** |
| 18 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted. No locale-aware number parsing.** |
| 19 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 20 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 21 | `TRIMSELECT` | **No** | -- | -- | **Not extracted. Table parameter -- generic mapper cannot parse nested `elementValue` groups.** |
| 22 | `RANDOM` | **No** | -- | -- | **Not extracted. Random sampling not available.** |
| 23 | `NB_RANDOM` | **No** | -- | -- | **Not extracted.** |
| 24 | `ENABLE_DECODE` | **No** | -- | -- | **Not extracted.** |
| 25 | `DECODE_COLS` | **No** | -- | -- | **Not extracted. Table parameter.** |
| 26 | `CSVROWSEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 27 | `SCHEMA_OPT_NUM` | **No** | -- | -- | Not needed at runtime (code generation optimization) |
| 28 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 29 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 30 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 12 of 30 parameters extracted (40%). 13 runtime-relevant parameters are missing.

**Cross-reference with tFileInputPositional**: The converter for `tFileInputPositional` (lines 150-171) already extracts `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`, `CHECK_DATE`, and `UNCOMPRESS`. This demonstrates the converter team knows how to extract these parameters -- they simply have not been added to the `tFileInputDelimited` mapping.

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
- The `ExpressionConverter.detect_java_expression()` is aggressive -- it marks values with common operators (`+`, `-`, `/`, etc.) as Java expressions. This can cause false positives for file paths containing `/` (mitigated by path detection logic) or values with hyphens.
- The HEADER and FOOTER values are converted via `.isdigit()` before expression marking, so Java expressions in these fields (e.g., `context.headerCount + 1`) are passed as strings but not marked as `{{java}}`.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FID-001 | **P1** | **No dedicated parser method**: `tFileInputDelimited` uses the deprecated `_map_component_parameters()` approach instead of a dedicated `parse_file_input_delimited()` method. This prevents extraction of table parameters (`TRIMSELECT`, `DECODE_COLS`) and limits extensibility. Per STANDARDS.md, every component MUST have its own `parse_*` method. |
| CONV-FID-002 | **P1** | **`CSV_OPTION` not extracted**: Engine cannot distinguish between RFC4180 CSV mode and raw delimited mode. In Talend, `CSV_OPTION=true` changes parsing behavior significantly -- single-char delimiter, proper quoting, CSVROWSEPARATOR. Without this flag, CSV files with embedded delimiters inside quoted fields may parse incorrectly in edge cases. |
| CONV-FID-003 | **P1** | **`SPLITRECORD` not extracted**: Multi-line quoted fields (embedded newlines inside quoted strings) cannot be explicitly controlled. While pandas handles some multi-line cases by default, the explicit toggle is missing. Critical for RFC4180 compliance. |
| CONV-FID-004 | **P1** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both, this violates the documented standard (STANDARDS.md line 865-878) and creates subtle type mapping differences (e.g., `Decimal` vs `id_BigDecimal` maps differently in `_build_dtype_dict()` vs `validate_schema()`). |
| CONV-FID-005 | **P2** | **`UNCOMPRESS` not extracted**: Jobs reading compressed `.gz` or `.zip` files will fail at runtime with encoding or format errors. |
| CONV-FID-006 | **P2** | **`CHECK_FIELDS_NUM` not extracted**: Row structure validation unavailable. Malformed rows with wrong field count will silently produce misaligned columns rather than being routed to REJECT. |
| CONV-FID-007 | **P2** | **`ADVANCED_SEPARATOR` / `THOUSANDS_SEPARATOR` / `DECIMAL_SEPARATOR` not extracted**: Locale-aware number parsing unavailable. Files using European number format (e.g., `1.234.567,89`) will fail numeric conversion. |
| CONV-FID-008 | **P2** | **Default encoding mismatch**: Converter defaults `ENCODING` to `'UTF-8'` (line 120), but Talend default is `'ISO-8859-15'`. If a Talend job does not explicitly set encoding, the converter writes `'UTF-8'`, which differs from Talend behavior. This can cause mojibake on files containing non-ASCII characters encoded in ISO-8859-15. |
| CONV-FID-009 | **P2** | **Default delimiter mismatch**: Converter defaults `FIELDSEPARATOR` to `','` (line 115), but Talend default is `';'`. If a job relies on the Talend default semicolon delimiter, the converter produces the wrong delimiter value. |
| CONV-FID-010 | **P3** | **`RANDOM` / `NB_RANDOM` not extracted**: Random sampling unavailable. Low priority -- rarely used in production Talend jobs. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read delimited file | **Yes** | High | `_read_batch()` line 351, `_read_streaming()` line 434 | Uses `pd.read_csv()` -- solid core implementation |
| 2 | Header row skip | **Yes** | High | `_read_batch()` line 361 | `skiprows=list(range(header_rows))` when schema present |
| 3 | Footer row skip | **Yes** | High | `_read_batch()` line 389 | `skipfooter=footer_rows`, forces Python engine |
| 4 | Row limit | **Yes** | High | `_read_batch()` line 388 | `nrows=limit` passed to `pd.read_csv()` |
| 5 | Encoding support | **Yes** | Medium | `_read_batch()` line 385 | Passed to pandas. Default mismatch: engine defaults to UTF-8, Talend to ISO-8859-15 |
| 6 | Text enclosure / quoting | **Yes** | Medium | `_configure_csv_params()` line 521 | Single-char only; multi-char disables quoting (falls back to `QUOTE_NONE`) |
| 7 | Escape character | **Yes** | High | `_configure_csv_params()` line 527 | Correctly handles doublequote mode (escape==enclosure) |
| 8 | Tab delimiter (`\t`) | **Yes** | High | `_process()` line 280 | Normalizes `"\\t"` to `"\t"` |
| 9 | Multi-char delimiter (regex) | **Yes** | Medium | `_process()` line 283-285 | Uses pandas regex engine via `sep=rf"{delimiter}"` and `regex=True`. May differ from Talend on special regex chars. |
| 10 | Trim all columns | **Yes** | High | `_post_process_dataframe()` line 546 | Applied to string columns via `str.strip()` |
| 11 | Remove empty rows | **Yes** | High | `_post_process_dataframe()` line 554 | `dropna(how='all')` -- correct behavior |
| 12 | Die on error | **Yes** | High | `_process()` line 243, 257, 300 | Raises `FileOperationError`/`ConfigurationError` or returns empty DF |
| 13 | BigDecimal columns | **Yes** | High | `_post_process_dataframe()` line 569 | Post-processes with `Decimal(str(x))` conversion |
| 14 | Schema column naming | **Yes** | High | `_read_batch()` line 363 | Uses `names=column_names` from output_schema |
| 15 | Schema type enforcement | **Yes** | Medium | `_build_dtype_dict()` + `validate_schema()` | Double type mapping: `_build_dtype_dict` uses nullable `Int64`, `validate_schema` uses non-nullable `int64` with `fillna(0)` |
| 16 | Streaming / hybrid mode | **Yes** | Medium | `_read_streaming()` line 434 | Generator-based chunked reading. Footer skip may not work correctly with chunks. |
| 17 | Single-string read mode | **Yes** | Medium | `_read_as_single_string()` line 305 | Handles empty delimiter+separator for XML/document files. Has DF creation bug (see BUG-FID-005). |
| 18 | File existence check | **Yes** | High | `_process()` line 253 | `os.path.exists()` before reading |
| 19 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 20 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 21 | `keep_default_na=False` | **Yes** | High | `_read_batch()` line 392 | Prevents "NA", "NULL", "None" strings from becoming NaN. Correct for Talend compat. |
| 22 | `usecols` optimization | **Yes** | High | `_read_batch()` line 398-399 | Only reads schema columns, ignoring extra file columns |
| 23 | **REJECT flow** | **No** | N/A | -- | **No reject output. All errors either die or return empty DF. Fundamental gap.** |
| 24 | **CSV_OPTION (RFC4180)** | **No** | N/A | -- | **No toggle. Always uses the same parsing mode regardless of CSV_OPTION flag.** |
| 25 | **Split record (multi-line)** | **No** | N/A | -- | **No explicit SPLITRECORD control. pandas handles some cases by default with quoting, but not explicitly controlled.** |
| 26 | **Compressed file reading** | **No** | N/A | -- | **No gzip/zip support. pandas natively supports `compression='gzip'`/`'zip'`, so this is straightforward.** |
| 27 | **Check row structure** | **No** | N/A | -- | **No field count validation per row.** |
| 28 | **Check date** | **No** | N/A | -- | **No strict date column validation against schema pattern.** |
| 29 | **Advanced separator** | **No** | N/A | -- | **No locale-aware number parsing.** |
| 30 | **Per-column trim** | **No** | N/A | -- | **Only trim-all; no per-column TRIMSELECT.** |
| 31 | **Random sampling** | **No** | N/A | -- | **Not implemented.** |
| 32 | **Hex/Octal decode** | **No** | N/A | -- | **Not implemented.** |
| 33 | **`{id}_FILENAME` globalMap** | **No** | N/A | -- | **Resolved filename not stored in globalMap.** |
| 34 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FID-001 | **P0** | **No REJECT flow**: Talend produces reject rows for unparseable lines with `errorCode` and `errorMessage` columns when `DIE_ON_ERROR=false` and a REJECT link is connected. V1 either raises `FileOperationError` (die_on_error=true) or returns empty DataFrame (die_on_error=false). There is NO mechanism to capture and route bad rows. This is a fundamental gap for data quality pipelines. The component docstring on line 59 acknowledges this: `"NB_LINE_REJECT: Failed rows (0 for this component)"`. |
| ENG-FID-002 | **P1** | **No split record / multi-line field support**: Multi-line quoted fields (RFC4180) will be parsed as separate rows in cases where pandas defaults do not handle them. While pandas `read_csv` does support multi-line quoted fields when `quotechar` is set, there is no explicit SPLITRECORD toggle, and the behavior depends on `_configure_csv_params()` configuration. Fields with embedded newlines in non-CSV-option mode may corrupt data. |
| ENG-FID-003 | **P1** | **No compressed file support**: Jobs reading `.gz` or `.zip` files will fail with encoding or format errors. pandas `read_csv` natively supports `compression='gzip'` and `compression='zip'`, so implementation is straightforward. |
| ENG-FID-004 | **P1** | **`{id}_FILENAME` not set in globalMap**: Downstream components referencing the resolved filename via globalMap will get null/None. This variable is used in logging, audit trails, and conditional logic in Talend jobs. While not officially documented as a standard global variable, it is commonly expected. |
| ENG-FID-005 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. |
| ENG-FID-006 | **P1** | **Default encoding differs from Talend**: Engine defaults to `UTF-8` (line 80: `DEFAULT_ENCODING = 'UTF-8'`), but Talend defaults to `ISO-8859-15`. Files without explicit encoding in the Talend job will be read with the wrong encoding, potentially causing mojibake for non-ASCII characters. |
| ENG-FID-007 | **P2** | **No field count validation (CHECK_FIELDS_NUM)**: Malformed rows with wrong number of fields silently produce wrong column alignment. In Talend with CHECK_FIELDS_NUM=true, these rows go to REJECT. In v1, they either cause a pandas parsing error or produce misaligned data. |
| ENG-FID-008 | **P2** | **Single-char text enclosure only**: `_configure_csv_params()` line 523 checks `len(text_enclosure) != 1` and falls back to `QUOTE_NONE`. While Talend also expects single-char enclosure, the fallback disables all quoting rather than logging a warning and using a reasonable default. |
| ENG-FID-009 | **P2** | **No date validation (CHECK_DATE)**: Date-typed columns are converted via `pd.to_datetime()` with no format specification in `validate_schema()` (base_component.py line 348), which uses pandas' flexible parser. Invalid dates silently become `NaT` rather than being routed to REJECT. |
| ENG-FID-010 | **P3** | **No hex/octal decode (ENABLE_DECODE)**: Low priority. Rarely used in production Talend jobs. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE since no reject exists -- never accurately reflects rejected rows |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no reject flow exists. Even if `validate_schema()` drops rows, the reject count is not updated. |
| `{id}_FILENAME` | Uncertain (not in official docs) | **No** | -- | Not implemented. Common community expectation. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FID-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileInputDelimited, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-FID-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FID-003 | **P1** | `src/v1/engine/components/file/file_input_delimited.py:266` | **Single-string mode trigger condition is too broad**: The check `delimiter in [None, '', '  '] and row_separator in [None, '', '  ', '\r\n']` treats `\r\n` as a trigger for single-string mode when delimiter is empty. While the AND condition means `delimiter=','` with `row_separator='\r\n'` does NOT trigger it, a file with empty delimiter and default `\r\n` row separator would incorrectly read the entire file as a single string. The inclusion of `'  '` (two spaces) as a special value is suspicious and undocumented. |
| BUG-FID-004 | **P1** | `src/v1/engine/components/file/file_input_delimited.py:86-146` | **`_validate_config()` is never called**: The method exists and contains 60 lines of validation logic, but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (missing filepath, non-integer header_rows, etc.) are not caught until they cause runtime errors deep in processing. |
| BUG-FID-005 | **P2** | `src/v1/engine/components/file/file_input_delimited.py:322` | **`_read_as_single_string()` creates DataFrame incorrectly**: `pd.DataFrame({column_name: file_content})` where `file_content` is a scalar string creates a DataFrame where each CHARACTER becomes a separate row (pandas scalar expansion behavior). The intent is to create a single-row DataFrame. Should be `pd.DataFrame({column_name: [file_content]})` (list wrapper). |
| BUG-FID-006 | **P2** | `src/v1/engine/components/file/file_input_delimited.py:419` | **NB_LINE_REJECT always 0 in batch mode**: `_update_stats(rows_read, rows_read, 0)` unconditionally sets `NB_LINE_OK = NB_LINE`. Even if `validate_schema()` drops or modifies rows, the rejected count is never updated because `validate_schema()` does not return reject information. The count after `validate_schema()` should be compared to the count before. |
| BUG-FID-007 | **P2** | `src/v1/engine/components/file/file_input_delimited.py:374` | **Engine selection logic treats empty list as non-None**: `engine = 'python' if (footer_rows > 0 or use_regex or skiprows is not None) else 'c'`. When `header_rows=0` and `output_schema` exists, `skiprows` is set to `list(range(0))` = `[]` (empty list) on line 361. An empty list is not None, so the Python engine is used unnecessarily. The C engine is significantly faster for large files. Should check for truthiness (`skiprows`) instead of None-ness (`skiprows is not None`). |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FID-001 | **P2** | **`remove_empty_rows` (plural)** vs Talend parameter `REMOVE_EMPTY_ROW` (singular). The STANDARDS.md mapping documents this as `remove_empty_rows` (plural), so the converter matches the standard. However, `tFileInputPositional` converter uses `remove_empty_row` (singular, line 158), creating inter-component inconsistency. |
| NAME-FID-002 | **P3** | **`header_rows` adds `_rows` suffix** not present in Talend's `HEADER`. Documented as intentional in STANDARDS.md for clarity. No action needed. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FID-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md line 91) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FID-002 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | Uses deprecated `_map_component_parameters()` instead of a dedicated `parse_file_input_delimited()` method. Cannot handle table parameters. |
| STD-FID-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md line 865) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |
| STD-FID-004 | **P3** | "No `print()` statements" (STANDARDS.md) | No print statements in `file_input_delimited.py` itself. Some exist in `component_parser.py` for other components but not for tFileInputDelimited specifically. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FID-001 | **P3** | **`# ...existing code...` comment artifacts**: Lines 359 and 407 of `file_input_delimited.py` contain `# ...existing code...` comments that appear to be artifacts from code generation or editing tools. Should be removed. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FID-001 | **P3** | **No path traversal protection**: `filepath` from config is used directly with `os.path.exists()` and passed to `pd.read_csv()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.6 Logging Quality

The component has excellent logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 248); `_read_batch()` logs completion with row counts (line 421) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `FileOperationError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern consistently -- correct |
| `die_on_error` handling | Three separate try/except blocks handle this: main `_process()` (line 296-303), `_read_as_single_string()` (line 330-337), and missing file (line 253-261) -- correct |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID, file path, and error details -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_read_batch()`, `_read_streaming()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[int]`, `Iterator[pd.DataFrame]` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FID-001 | **P2** | **Post-processing iterates string columns twice**: `_post_process_dataframe()` first calls `df.select_dtypes(include=['object'])` for trimming (line 546), then again for NaN filling (line 559). These could be combined into a single pass. For DataFrames with 100+ columns and millions of rows, this doubles the column iteration overhead. |
| PERF-FID-002 | **P2** | **BigDecimal conversion uses `apply()` with lambda**: Lines 569-571 use `df[col_name].apply(lambda x: Decimal(str(x)) ...)` which is a Python-level row-by-row loop. For columns with millions of values, this is slow compared to vectorized approaches. Consider deferred conversion or vectorized string-to-Decimal. |
| PERF-FID-003 | **P3** | **C engine not used when `skiprows=[]`**: When `header_rows=0` with a schema, `skiprows` is set to `[]` (empty list). The engine selection check `skiprows is not None` evaluates True for `[]`, forcing the slower Python engine unnecessarily. Should use `skiprows` (truthy check). See also BUG-FID-007. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Implemented via `_read_streaming()` with configurable `chunk_size`. Activated when file > 3GB and `execution_mode=HYBRID`. Correct design. |
| Memory threshold | `MEMORY_THRESHOLD_MB = 3072` (3GB) inherited from `BaseComponent`. Reasonable default. |
| Chunked processing | Uses pandas `chunksize` parameter with generator -- memory efficient for large files. |
| `keep_default_na=False` | Prevents pandas from treating "NA", "NULL", "None" strings as NaN. Correct for Talend compatibility. |
| `usecols` optimization | Uses `usecols=columns_to_keep` when schema provides `dtype_dict` (lines 398-399). Reduces memory for wide files with many unused columns. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| Footer skip + streaming | `skipfooter` requires the Python engine and may not work correctly with chunked reading. The last chunk may include footer rows. |
| Reject flow + streaming | Not applicable currently (no reject flow), but if implemented, streaming mode would need to yield both main and reject chunks. |
| Stats accumulation | `_update_stats()` is called per chunk (line 504), which correctly accumulates totals across all chunks. |
| Schema validation per chunk | `validate_schema()` is called per chunk (line 500). Correct but means type conversion runs N times. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputDelimited` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 575 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic CSV read | P0 | Read a simple comma-separated file with header row, verify row count and column values match expected output |
| 2 | Schema enforcement | P0 | Read with typed schema (int, float, string, Decimal), verify correct type coercion for each column type |
| 3 | Header/footer skip | P0 | Verify `header_rows=2, footer_rows=1` skips the correct rows from a known file |
| 4 | Missing file + die_on_error=true | P0 | Should raise `FileOperationError` with descriptive message |
| 5 | Missing file + die_on_error=false | P0 | Should return empty DataFrame with stats (0, 0, 0) |
| 6 | Empty file | P0 | Should return empty DataFrame without error, stats (0, 0, 0) |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict after execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Tab delimiter | P1 | Read TSV file with `delimiter="\\t"`, verify tab normalization and correct parsing |
| 9 | Multi-char delimiter | P1 | Read with `"||"` delimiter, verify regex engine path produces correct results |
| 10 | Quoted fields with embedded delimiter | P1 | `"hello, world"` with comma delimiter should be parsed as one field |
| 11 | Encoding ISO-8859-15 | P1 | Read file with non-UTF8 characters using ISO-8859-15 encoding, verify correct decoding |
| 12 | BigDecimal columns | P1 | Verify `Decimal` precision is preserved (e.g., `123.456789012345` not rounded) |
| 13 | Row limit | P1 | Verify `limit=5` reads only 5 rows from a 100-row file |
| 14 | Trim all | P1 | Verify leading/trailing whitespace is stripped from all string columns |
| 15 | Remove empty rows | P1 | Verify blank rows (all fields empty) are filtered out |
| 16 | Context variable in filepath | P1 | `${context.input_dir}/file.csv` should resolve via context manager |
| 17 | Single-string mode | P1 | Empty delimiter + empty separator reads entire file as single string in one row |
| 18 | Schema column mismatch | P1 | File has different column count than schema -- verify warning logged and graceful handling |
| 19 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution |
| 20 | Doublequote escape mode | P1 | `escape_char == text_enclosure` triggers doublequote mode -- verify fields like `""hello""` are parsed correctly |
| 21 | Invalid header_rows value | P1 | Non-integer `header_rows` falls back to default 0 with warning |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 22 | Large file streaming | P2 | Verify hybrid mode activates streaming for file > threshold and produces correct results |
| 23 | Pipe delimiter | P2 | `|` as delimiter (regex special char) should work correctly as single-char delimiter |
| 24 | File with BOM | P2 | UTF-8 file with BOM should be handled (currently a known gap) |
| 25 | Concurrent reads | P2 | Multiple `FileInputDelimited` instances reading different files simultaneously |
| 26 | Unicode in delimiter | P2 | Non-ASCII delimiter character |
| 27 | Empty delimiter with non-empty row separator | P2 | Verify behavior matches expectation (currently a gap -- see Edge Case 13) |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FID-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FID-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FID-001 | Testing | Zero v1 unit tests for the most-used input component. All 575 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FID-001 | Converter | No dedicated parser method -- uses deprecated `_map_component_parameters()`. Cannot handle table parameters (`TRIMSELECT`, `DECODE_COLS`). Violates STANDARDS.md. |
| CONV-FID-002 | Converter | `CSV_OPTION` not extracted -- engine cannot enable RFC4180 CSV mode. |
| CONV-FID-003 | Converter | `SPLITRECORD` not extracted -- multi-line quoted fields cannot be explicitly controlled. |
| CONV-FID-004 | Converter | Schema types converted to Python format (`str`) instead of Talend format (`id_String`), violating STANDARDS.md. |
| ENG-FID-001 | Engine | **No REJECT flow** -- bad rows are lost or cause job failure. Fundamental gap for data quality pipelines. |
| ENG-FID-002 | Engine | No SPLITRECORD support -- multi-line fields not explicitly controlled. |
| ENG-FID-003 | Engine | No compressed file reading -- gzip/zip files will fail. |
| ENG-FID-004 | Engine | `{id}_FILENAME` globalMap variable not set -- downstream references get null. |
| ENG-FID-005 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set -- error details not available downstream. |
| ENG-FID-006 | Engine | Default encoding `UTF-8` differs from Talend default `ISO-8859-15`. Files without explicit encoding will be read wrong. |
| BUG-FID-003 | Bug | Single-string mode condition too broad -- `\r\n` row separator triggers single-string for empty-delimiter files. |
| BUG-FID-004 | Bug | `_validate_config()` is dead code -- never called by any code path. 60 lines of unreachable validation. |
| TEST-FID-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FID-005 | Converter | `UNCOMPRESS` not extracted -- compressed file reading unavailable. |
| CONV-FID-006 | Converter | `CHECK_FIELDS_NUM` not extracted -- row structure validation unavailable. |
| CONV-FID-007 | Converter | `ADVANCED_SEPARATOR` / `THOUSANDS_SEPARATOR` / `DECIMAL_SEPARATOR` not extracted. |
| CONV-FID-008 | Converter | Default encoding mismatch: converter defaults to `UTF-8`, Talend defaults to `ISO-8859-15`. |
| CONV-FID-009 | Converter | Default delimiter mismatch: converter defaults to `,`, Talend defaults to `;`. |
| ENG-FID-007 | Engine | No field count validation (CHECK_FIELDS_NUM) -- malformed rows produce misaligned columns. |
| ENG-FID-008 | Engine | Single-char text enclosure only -- multi-char falls back to `QUOTE_NONE`, disabling all quoting. |
| ENG-FID-009 | Engine | No date validation (CHECK_DATE) -- invalid dates silently become NaT instead of going to REJECT. |
| BUG-FID-005 | Bug | `_read_as_single_string()` creates per-character DataFrame instead of single-row DF. |
| BUG-FID-006 | Bug | `NB_LINE_REJECT` always 0 -- no reject counting even if schema validation drops rows. |
| BUG-FID-007 | Bug | Engine selection treats empty list `skiprows=[]` as non-None, forcing Python engine unnecessarily. |
| NAME-FID-001 | Naming | `remove_empty_rows` (plural) inconsistent with `tFileInputPositional`'s `remove_empty_row` (singular). |
| STD-FID-001 | Standards | `_validate_config()` exists but never called -- dead validation. |
| STD-FID-002 | Standards | Uses deprecated `_map_component_parameters()` instead of dedicated `parse_*` method. |
| STD-FID-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| PERF-FID-001 | Performance | Post-processing iterates string columns twice (trim pass + NaN fill pass). |
| PERF-FID-002 | Performance | BigDecimal conversion uses slow `apply()` with lambda (row-by-row Python loop). |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FID-010 | Converter | `RANDOM` / `NB_RANDOM` not extracted -- random sampling unavailable (rarely used). |
| ENG-FID-010 | Engine | No hex/octal decode (`ENABLE_DECODE`). |
| NAME-FID-002 | Naming | `header_rows` suffix differs from Talend's `HEADER` (intentional per STANDARDS.md). |
| STD-FID-004 | Standards | `print()` statements in `component_parser.py` (other components, not this one specifically). |
| SEC-FID-001 | Security | No path traversal protection on `filepath`. |
| PERF-FID-003 | Performance | C engine not used when `skiprows=[]` (empty list treated as non-None). |
| DBG-FID-001 | Debug | `# ...existing code...` comments are generation artifacts on lines 359, 407. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 13 | 4 converter, 6 engine, 2 bugs, 1 testing |
| P2 | 17 | 5 converter, 3 engine, 3 bugs, 1 naming, 3 standards, 2 performance |
| P3 | 7 | 1 converter, 1 engine, 1 naming, 1 standards, 1 security, 1 performance, 1 debug |
| **Total** | **40** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FID-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FID-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FID-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic CSV read, schema enforcement, header/footer skip, missing file handling (both die_on_error modes), empty file, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Implement REJECT flow** (ENG-FID-001): Use pandas `on_bad_lines` callback (pandas >= 1.3) to capture malformed rows during `_read_batch()`. Build a reject DataFrame with all original schema columns plus `errorCode` (String) and `errorMessage` (String). Return `{'main': good_df, 'reject': reject_df}` from `_process()`. Update `_update_stats()` to reflect actual rejected count. This is the single most impactful feature gap.

### Short-Term (Hardening)

5. **Create dedicated converter parser** (CONV-FID-001): Replace the `_map_component_parameters()` call with a dedicated `parse_file_input_delimited(node, component)` method in `component_parser.py`. Extract ALL missing parameters: `CSV_OPTION`, `SPLITRECORD`, `UNCOMPRESS`, `CHECK_FIELDS_NUM`, `CHECK_DATE`, `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`, `RANDOM`, `NB_RANDOM`, `TRIMSELECT`, `ENABLE_DECODE`, `DECODE_COLS`, `CSVROWSEPARATOR`. Register the new parser in `converter.py:_parse_component()` with an `elif component_type == 'tFileInputDelimited'` branch.

6. **Set `{id}_FILENAME` and `{id}_ERROR_MESSAGE` in globalMap** (ENG-FID-004, ENG-FID-005): After resolving filepath in `_process()`, call `self.global_map.put(f"{self.id}_FILENAME", filepath)`. In error handlers, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

7. **Fix default encoding to match Talend** (ENG-FID-006): Change `DEFAULT_ENCODING = 'UTF-8'` to `DEFAULT_ENCODING = 'ISO-8859-15'` in `file_input_delimited.py` line 80, and update the converter default on line 120 of `component_parser.py`.

8. **Fix single-string mode trigger** (BUG-FID-003): Tighten the condition on line 266 to only trigger when both delimiter and row_separator are explicitly empty strings or None. Remove `'  '` (two spaces) and `'\r\n'` from the match lists.

9. **Wire up `_validate_config()`** (BUG-FID-004): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` or returning empty DataFrame based on `die_on_error`. Alternatively, add validation as a standard lifecycle step in `BaseComponent.execute()`.

10. **Fix `_read_as_single_string()` DataFrame creation** (BUG-FID-005): Change `pd.DataFrame({column_name: file_content})` to `pd.DataFrame({column_name: [file_content]})` on line 322.

11. **Add compressed file support** (ENG-FID-003): Read the `uncompress` config flag. When true, pass `compression='infer'` (or explicit `'gzip'`/`'zip'` based on file extension) to `pd.read_csv()`. This is a one-line change since pandas handles compression natively.

12. **Fix converter schema type format** (CONV-FID-004): Either stop converting types in `ExpressionConverter.convert_type()` (preserve `id_String`, `id_Integer`, etc.) or ensure both Python and Talend type formats produce identical results in both `_build_dtype_dict()` and `validate_schema()`.

### Long-Term (Optimization)

13. **Implement CHECK_FIELDS_NUM** (ENG-FID-007): Use pandas `on_bad_lines='warn'` or a custom callback to detect rows with wrong field counts. Route to REJECT when available.

14. **Implement CHECK_DATE** (ENG-FID-009): After reading, validate date columns against the schema pattern using `pd.to_datetime(format=pattern, errors='coerce')`. Rows where date conversion failed (NaT) should be routed to REJECT.

15. **Optimize post-processing** (PERF-FID-001, PERF-FID-002): Combine the two `select_dtypes(include=['object'])` calls into a single pass. Consider vectorized BigDecimal conversion or lazy conversion.

16. **Fix engine selection for empty skiprows** (BUG-FID-007, PERF-FID-003): Change `skiprows is not None` to `skiprows` (truthy check) on line 374.

17. **Add random sampling** (CONV-FID-010, ENG-FID-010): Implement `RANDOM`/`NB_RANDOM` using pandas `skiprows` with a random function. Low priority unless specific jobs require it.

18. **Add path traversal protection** (SEC-FID-001): Validate filepath against allowed base directories before passing to `os.path.exists()` and `pd.read_csv()`.

19. **Clean up dead code and artifacts** (BUG-FID-004, DBG-FID-001): Remove or activate `_validate_config()`. Remove `# ...existing code...` comment artifacts.

20. **Create integration test** (TEST-FID-002): Build an end-to-end test exercising `tFileInputDelimited -> tMap -> tFileOutputDelimited` in the v1 engine, verifying context resolution, Java bridge integration, and globalMap propagation.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 109-126
if component_type == 'tFileInputDelimited':
    header_value = config_raw.get('HEADER', '0')
    footer_value = config_raw.get('FOOTER', '0')

    return {
        'filepath': config_raw.get('FILENAME', ''),
        'delimiter': config_raw.get('FIELDSEPARATOR', ','),
        'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
        'header_rows': int(header_value) if header_value.isdigit() else header_value,
        'footer_rows': int(footer_value) if footer_value.isdigit() else footer_value,
        'limit': config_raw.get('LIMIT', ''),
        'encoding': config_raw.get('ENCODING', 'UTF-8'),
        'text_enclosure': config_raw.get('TEXT_ENCLOSURE', '').replace('\\"', ''),
        'escape_char': config_raw.get('ESCAPE_CHAR', '\\').replace('\\\\', '').replace('\\\\\\', '\\'),
        'remove_empty_rows': config_raw.get('REMOVE_EMPTY_ROW', False),
        'trim_all': config_raw.get('TRIMALL', False),
        'die_on_error': config_raw.get('DIE_ON_ERROR', False)
    }
```

**Notes on this code**:
- Line 117: `.isdigit()` rejects negative numbers and Java expressions. If `HEADER` contains a context variable or expression, it passes through as a string, which the engine then tries to `int()` cast (with fallback to default 0).
- Line 121: `replace('\\"', '')` strips escaped quotes. Handles Talend XML storing `"\""` for a quote character.
- Line 122: Double replace on `escape_char` is fragile and may not handle all edge cases of escaped backslashes.
- Default values for `FIELDSEPARATOR` (`,`) and `ENCODING` (`UTF-8`) differ from Talend defaults (`;` and `ISO-8859-15`).

---

## Appendix B: Engine Class Structure

```
FileInputDelimited (BaseComponent)
    Constants:
        DEFAULT_DELIMITER = ','
        DEFAULT_ENCODING = 'UTF-8'
        DEFAULT_HEADER_ROWS = 0
        DEFAULT_FOOTER_ROWS = 0
        DEFAULT_TEXT_ENCLOSURE = '"'
        DEFAULT_ESCAPE_CHAR = '\\'

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _build_dtype_dict() -> Optional[Dict]     # Type mapping for pd.read_csv
        _process(input_data) -> Dict[str, Any]    # Main entry point
        _read_as_single_string(filepath, ...)      # Special mode for XML/document files
        _parse_limit(limit) -> Optional[int]       # Limit parameter parsing
        _read_batch(filepath, ...) -> Dict         # Batch reading with pd.read_csv
        _read_streaming(filepath, ...) -> Dict     # Chunked reading with generator
        _configure_csv_params(text_encl, esc)      # Quote/escape configuration
        _post_process_dataframe(df, trim, empty)   # Trim, empty row removal, NaN fill, BigDecimal
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filepath` | Mapped | -- |
| `FIELDSEPARATOR` | `delimiter` | Mapped | -- |
| `ROWSEPARATOR` | `row_separator` | Mapped | -- |
| `HEADER` | `header_rows` | Mapped | -- |
| `FOOTER` | `footer_rows` | Mapped | -- |
| `LIMIT` | `limit` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped | -- |
| `TEXT_ENCLOSURE` | `text_enclosure` | Mapped | -- |
| `ESCAPE_CHAR` | `escape_char` | Mapped | -- |
| `REMOVE_EMPTY_ROW` | `remove_empty_rows` | Mapped | -- |
| `TRIMALL` | `trim_all` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `CSV_OPTION` | `csv_option` | **Not Mapped** | P1 |
| `SPLITRECORD` | `split_record` | **Not Mapped** | P1 |
| `UNCOMPRESS` | `uncompress` | **Not Mapped** | P2 |
| `CHECK_FIELDS_NUM` | `check_fields_num` | **Not Mapped** | P2 |
| `CHECK_DATE` | `check_date` | **Not Mapped** | P2 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** | P2 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** | P2 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** | P2 |
| `TRIMSELECT` | `trim_select` | **Not Mapped** | P2 |
| `CSVROWSEPARATOR` | `csv_row_separator` | **Not Mapped** | P3 |
| `RANDOM` | `random` | **Not Mapped** | P3 |
| `NB_RANDOM` | `nb_random` | **Not Mapped** | P3 |
| `ENABLE_DECODE` | `enable_decode` | **Not Mapped** | P3 |
| `DECODE_COLS` | `decode_cols` | **Not Mapped** | P3 |
| `SCHEMA_OPT_NUM` | -- | Not needed | -- (code gen optimization) |
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

### Engine _build_dtype_dict() (for pd.read_csv)

| Type Input | Pandas Dtype | Notes |
|------------|-------------|-------|
| `id_String` / `str` | `object` | Correct |
| `id_Integer` / `int` | `Int64` (nullable) | Uses nullable integer to handle NaN during read |
| `id_Long` / `long` | `Int64` (nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | Correct |
| `id_Double` / `double` | `float64` | Correct |
| `id_Boolean` / `bool` | `bool` | **Potential issue**: `bool` dtype cannot handle NaN. Should use `object` and convert later. |
| `id_Date` / `date` | `object` | Correct -- read as string, convert in validate_schema() |
| `id_BigDecimal` / `Decimal` | `object` | Correct -- read as string, convert to Decimal in post-processing |

### Engine validate_schema() (post-read conversion in base_component.py)

| Type Input | Pandas Dtype | Conversion Method |
|------------|-------------|-------------------|
| `id_String` / `str` | `object` | No conversion |
| `id_Integer` / `int` | `int64` (non-nullable) | `pd.to_numeric(errors='coerce')` then `fillna(0).astype('int64')` |
| `id_Long` / `long` | `int64` (non-nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | `pd.to_numeric(errors='coerce')` |
| `id_Double` / `double` | `float64` | Same as Float |
| `id_Boolean` / `bool` | `bool` | `.astype('bool')` |
| `id_Date` / `date` | `datetime64[ns]` | `pd.to_datetime()` -- no format specification, uses pandas' flexible parser |
| `id_BigDecimal` / `decimal` | `object` | No conversion in validate_schema (done in _post_process_dataframe) |

**Key discrepancy**: `_build_dtype_dict()` uses nullable `Int64` but `validate_schema()` converts to non-nullable `int64` with `fillna(0)`. This means:
1. During read: null integers are stored as `<NA>` (nullable `Int64`)
2. During validation: nulls are silently converted to `0` (non-nullable `int64`)

This matches Talend default behavior (null integers become 0), but the double conversion is wasteful and the intermediate nullable state is unnecessary if the final target is non-nullable.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 86-146)

This method validates:
- `filepath` is present and non-empty (required)
- `delimiter` is a string (if present)
- `encoding` is a string (if present)
- `header_rows` is a valid non-negative integer (if present)
- `footer_rows` is a valid non-negative integer (if present)
- `limit` is a valid positive integer (if present)
- `remove_empty_rows` is boolean (if present)
- `trim_all` is boolean (if present)
- `die_on_error` is boolean (if present)

**Not validated**: `text_enclosure`, `escape_char`, `row_separator`, `chunk_size`.

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions.

### `_build_dtype_dict()` (Lines 148-190)

Maps Talend types to pandas dtype strings for type enforcement during `pd.read_csv()`. Supports both Talend format (`id_String`) and Python format (`str`). Returns `None` if no schema is provided, allowing pandas to infer types.

### `_process()` (Lines 192-303)

The main processing method:
1. Extract config values with defaults and type conversion
2. Validate filepath (raises/returns empty on missing)
3. Check file existence (raises/returns empty on missing)
4. Special case: empty delimiter + row_separator -> single-string mode
5. Determine file size for execution mode selection
6. Parse limit, handle delimiter normalization (tab, multi-char)
7. Branch to `_read_batch()` or `_read_streaming()` based on mode
8. Catch-all exception handler with `die_on_error` support

### `_read_batch()` (Lines 351-432)

Batch reading:
1. Determine schema-based vs file-header-based reading
2. Build dtype dictionary for type enforcement
3. Select pandas engine (Python for footer/regex/skiprows, C otherwise)
4. Configure CSV quoting parameters
5. Build and execute `pd.read_csv()` parameters
6. Post-process (trim, remove empty, fill NaN, BigDecimal)
7. Validate schema
8. Update stats and return

### `_read_streaming()` (Lines 434-519)

Generator-based chunked reading:
1. Same parameter setup as batch mode
2. Creates `pd.read_csv()` with `chunksize` and `iterator=True`
3. Generator yields processed chunks
4. Each chunk gets post-processing and schema validation
5. Stats accumulated per chunk

### `_configure_csv_params()` (Lines 521-540)

Handles three quoting modes:
1. Invalid/empty `text_enclosure` -> `csv.QUOTE_NONE` (disables quoting entirely)
2. `escape_char == text_enclosure` -> doublequote mode (`doublequote=True`)
3. Otherwise -> standard escape mode (`escapechar=escape_char`)

### `_post_process_dataframe()` (Lines 542-574)

Post-processing steps:
1. Trim string columns (if `trim_all`)
2. Remove empty rows (if `remove_empty_rows`)
3. Fill NaN in string columns with empty string (Talend compatibility)
4. Convert BigDecimal columns to Python `Decimal` type

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty file

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0, NB_LINE_OK=0. No error. |
| **V1** | pandas `read_csv()` on empty file returns empty DataFrame. Stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: File with only header row

| Aspect | Detail |
|--------|--------|
| **Talend** | If HEADER=1, skips the header, reads 0 data rows. NB_LINE=0. |
| **V1** | With HEADER=1 and schema, `skiprows=[0]` skips row 0, `names=column_names` applies schema names. Empty DataFrame with correct columns. |
| **Verdict** | CORRECT |

### Edge Case 3: File with more columns than schema

| Aspect | Detail |
|--------|--------|
| **Talend** | Extra columns ignored. Only schema columns read. |
| **V1** | `usecols=columns_to_keep` reads only schema columns. Extra columns ignored. |
| **Verdict** | CORRECT |

### Edge Case 4: File with fewer columns than schema

| Aspect | Detail |
|--------|--------|
| **Talend** | If CHECK_FIELDS_NUM=false (default), missing columns filled with null. If true, rows go to REJECT. |
| **V1** | pandas may error or fill with NaN. No CHECK_FIELDS_NUM. `usecols` causes error if schema column not found. |
| **Verdict** | PARTIAL -- may error instead of gracefully handling. |

### Edge Case 5: Unicode BOM in file

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles BOM transparently based on encoding. |
| **V1** | `encoding='UTF-8'` does NOT strip BOM. Should use `encoding='utf-8-sig'` for BOM files. |
| **Verdict** | GAP -- BOM handling not implemented. |

### Edge Case 6: Null integers in nullable columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Null integers remain null or default to 0 depending on context. |
| **V1** | `_build_dtype_dict()` -> `Int64` (nullable), then `validate_schema()` -> `fillna(0).astype('int64')`. Nulls become 0. |
| **Verdict** | MATCHES Talend default (null -> 0). But loses nullability for downstream null-aware logic. |

### Edge Case 7: Quoted fields containing delimiter

| Aspect | Detail |
|--------|--------|
| **Talend** | With CSV_OPTION=true, `"hello, world"` is one field. |
| **V1** | `_configure_csv_params()` sets `quotechar` which pandas respects. Works correctly IF text_enclosure is set. |
| **Verdict** | CORRECT (when text_enclosure configured) |

### Edge Case 8: Quoted fields containing newlines (multi-line)

| Aspect | Detail |
|--------|--------|
| **Talend** | With SPLITRECORD=true, `"line1\nline2"` is one field. |
| **V1** | pandas handles multi-line by default when quoting is configured. No explicit SPLITRECORD toggle. |
| **Verdict** | PARTIALLY CORRECT -- works through pandas defaults, not explicitly controlled. |

### Edge Case 9: Very large limit value

| Aspect | Detail |
|--------|--------|
| **Talend** | LIMIT is a Java int. Max is Integer.MAX_VALUE. |
| **V1** | Python int has no overflow. Very large values work correctly. |
| **Verdict** | CORRECT |

### Edge Case 10: Context variable in filepath resolving to empty

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with clear error. |
| **V1** | `_process()` checks `if not filepath:` (line 239). Raises or returns empty DF. |
| **Verdict** | CORRECT |

### Edge Case 11: Delimiter is regex special char (e.g., `|`)

| Aspect | Detail |
|--------|--------|
| **Talend** | `|` as single char treated literally with CSV_OPTION. Without CSV_OPTION, regex mode. |
| **V1** | Single-char `|` works correctly (length check on line 283: `len(delimiter) > 1`). Not treated as regex. |
| **Verdict** | CORRECT for single-char. For multi-char, regex escaping may be needed for special chars. |

### Edge Case 12: Empty delimiter with non-empty row separator

| Aspect | Detail |
|--------|--------|
| **Talend** | Reads each row as a single field (one column per row). |
| **V1** | Single-string mode check (line 266) requires BOTH to be empty. Falls through to `pd.read_csv()` with `sep=''` which raises error. |
| **Verdict** | GAP -- empty delimiter with non-empty row separator not handled. |

### Edge Case 13: `die_on_error=false` with corrupt binary file

| Aspect | Detail |
|--------|--------|
| **Talend** | Produces reject rows for unparseable lines. Continues to end of file. |
| **V1** | Outer try/except (line 296-303) catches exception and returns empty DataFrame. ALL data lost. |
| **Verdict** | GAP -- no partial recovery. Entire file fails instead of row-by-row error handling. |

### Edge Case 14: Schema with date column but no pattern

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses default date format for locale. |
| **V1** | `validate_schema()` calls `pd.to_datetime()` without format -- uses pandas' flexible parser. May differ from Talend locale default. |
| **Verdict** | PARTIAL -- works for common formats but may differ for locale-specific defaults. |

### Edge Case 15: File path with spaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `os.path.exists()` and `pd.read_csv()` both handle spaces correctly. |
| **Verdict** | CORRECT |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileInputDelimited`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FID-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FID-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FID-004 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FID-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FID-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FID-005 -- Single-string DataFrame creation

**File**: `src/v1/engine/components/file/file_input_delimited.py`
**Line**: 322

**Current**:
```python
df = pd.DataFrame({column_name: file_content})
```

**Fix**:
```python
df = pd.DataFrame({column_name: [file_content]})
```

**Explanation**: Scalar string in DataFrame constructor creates one row per character. List wrapper creates single-row DataFrame as intended.

---

### Fix Guide: ENG-FID-001 -- Implementing REJECT flow

**File**: `src/v1/engine/components/file/file_input_delimited.py`

**Step 1**: Add reject collection in `_read_batch()`:
```python
# Before pd.read_csv()
reject_rows = []

def on_bad_line(bad_line):
    reject_rows.append({
        'raw_line': ','.join(str(x) for x in bad_line),
        'errorCode': 'PARSE_ERROR',
        'errorMessage': f'Row has {len(bad_line)} fields, expected {len(column_names)}'
    })
    return None  # Skip this line

read_params['on_bad_lines'] = on_bad_line
```

**Step 2**: Build reject DataFrame and update stats:
```python
if reject_rows:
    reject_df = pd.DataFrame(reject_rows)
else:
    reject_df = pd.DataFrame()

self._update_stats(rows_read + len(reject_rows), len(df), len(reject_rows))

return {
    'main': df,
    'reject': reject_df
}
```

**Impact**: Enables data quality pipelines. **Risk**: Medium (requires downstream components to handle `reject` key in results dict).

---

### Fix Guide: CONV-FID-001 -- Dedicated converter parser

**File**: `src/converters/complex_converter/component_parser.py`

Add a new `parse_file_input_delimited(self, node, component)` method that iterates `elementParameter` nodes and maps all 30+ Talend parameters. Register in `converter.py:_parse_component()` with:
```python
elif component_type == 'tFileInputDelimited':
    component = self.component_parser.parse_file_input_delimited(node, component)
```

This enables extraction of table parameters (`TRIMSELECT`, `DECODE_COLS`) and all missing boolean/string parameters.

---

### Fix Guide: ENG-FID-003 -- Adding compressed file support

**File**: `src/v1/engine/components/file/file_input_delimited.py`

In `_process()`, before the `pd.read_csv()` calls:
```python
uncompress = self.config.get('uncompress', False)
compression = 'infer' if not uncompress else 'gzip'  # Simplest approach
if uncompress and filepath.endswith('.zip'):
    compression = 'zip'
```

Then add `'compression': compression` to `read_params` dict. pandas handles compression transparently.

---

## Appendix I: Comparison with Other File Input Components

| Feature | tFileInputDelimited (V1) | tFileInputPositional (V1) | tFileInputExcel (V1) | tFileInputXML (V1) |
|---------|--------------------------|---------------------------|----------------------|---------------------|
| Basic reading | Yes | Yes | Yes | Yes |
| Schema enforcement | Yes | Yes | Yes | Yes |
| Header skip | Yes | Yes | Yes | N/A |
| Footer skip | Yes | Yes | No | N/A |
| Row limit | Yes | Yes | Yes | N/A |
| Encoding | Yes | Yes | N/A | Yes |
| Die on error | Yes | Yes | Yes | Yes |
| Trim all | Yes | Yes | N/A | N/A |
| Remove empty rows | Yes | Yes | N/A | N/A |
| Streaming mode | Yes | No | No | No |
| REJECT flow | **No** | **No** | **No** | **No** |
| GlobalMap FILENAME | **No** | **No** | **No** | **No** |
| Compressed reading | **No** | **No** | N/A | N/A |
| V1 Unit tests | **No** | **No** | **No** | **No** |

**Observation**: The REJECT flow gap, missing globalMap variables, and lack of v1 unit tests are systemic issues across ALL file input components. This suggests architectural omissions rather than component-specific oversights.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using REJECT flow for data quality | **Critical** | Any job with REJECT link on tFileInputDelimited | Must implement REJECT flow before migrating |
| Jobs reading compressed files | **High** | Jobs with UNCOMPRESS=true | Must add compression support |
| Jobs using `{id}_FILENAME` in downstream | **High** | Jobs with audit/logging using FILENAME | Must set FILENAME in globalMap |
| Jobs with multi-line CSV fields | **High** | Jobs with addresses, descriptions, JSON in CSV | Verify quoting behavior matches Talend |
| Jobs relying on Talend default encoding | **Medium** | European data files not specifying encoding | Fix converter and engine defaults |
| Jobs relying on Talend default delimiter | **Medium** | European jobs not specifying delimiter | Fix converter default |
| Jobs using CHECK_FIELDS_NUM | **Medium** | Data quality validation jobs | Implement field count check |
| Jobs using ADVANCED_SEPARATOR | **Medium** | European number format files | Implement locale-aware numbers |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using RANDOM sampling | Low | Rarely used in production |
| Jobs using ENABLE_DECODE | Low | Rarely used |
| Jobs using TRIMSELECT (per-column trim) | Low | Most jobs use TRIMALL or no trim |
| Jobs using tStatCatcher | Low | Monitoring feature, not data flow |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting). Run existing converted jobs to verify basic functionality.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which P1 features are used.
3. **Phase 3**: Implement P1 features required by target jobs (REJECT, compression, globalMap vars).
4. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix K: Complete Dedicated Parser Implementation

The following is the recommended replacement for the deprecated `_map_component_parameters()` approach. This method should be added to `component_parser.py` and registered in `converter.py`.

```python
def parse_file_input_delimited(self, node, component: Dict) -> Dict:
    """
    Parse tFileInputDelimited specific configuration from Talend XML node.

    Extracts ALL Talend parameters including table parameters (TRIMSELECT,
    DECODE_COLS) that the generic _map_component_parameters() cannot handle.

    Talend Parameters:
        FILENAME (str): File path or stream. Mandatory.
        FIELDSEPARATOR (str): Field delimiter. Default ";"
        ROWSEPARATOR (str): Row separator. Default "\\n"
        HEADER (int): Header rows to skip. Default 0
        FOOTER (int): Footer rows to skip. Default 0
        LIMIT (int): Max rows. Default 0 (unlimited)
        ENCODING (str): File encoding. Default "ISO-8859-15"
        TEXT_ENCLOSURE (char): Quote character. Default '"'
        ESCAPE_CHAR (char): Escape character. Default '\\\\'
        CSV_OPTION (bool): Enable RFC4180 mode. Default false
        CSVROWSEPARATOR (str): CSV-specific row separator.
        SPLITRECORD (bool): Multi-line fields. Default false
        UNCOMPRESS (bool): Read compressed files. Default false
        REMOVE_EMPTY_ROW (bool): Skip empty rows. Default false
        TRIMALL (bool): Trim all columns. Default false
        DIE_ON_ERROR (bool): Fail on error. Default false
        CHECK_FIELDS_NUM (bool): Validate row structure. Default false
        CHECK_DATE (bool): Validate date format. Default false
        ADVANCED_SEPARATOR (bool): Locale-aware numbers. Default false
        THOUSANDS_SEPARATOR (char): Thousands separator. Default ","
        DECIMAL_SEPARATOR (char): Decimal separator. Default "."
        RANDOM (bool): Random sampling. Default false
        NB_RANDOM (int): Number of random rows.
        TRIMSELECT (table): Per-column trim settings.
        ENABLE_DECODE (bool): Hex/octal parsing. Default false
        DECODE_COLS (table): Per-column decode settings.
    """
    config = component['config']

    # Phase 1: Extract scalar parameters from elementParameter nodes
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')
        field = param.get('field', '')

        # Strip surrounding quotes (Talend XML often wraps values in quotes)
        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        if name == 'FILENAME':
            config['filepath'] = self.expr_converter.mark_java_expression(value)
        elif name == 'FIELDSEPARATOR':
            config['delimiter'] = value if value else ';'  # Talend default is semicolon
        elif name == 'ROWSEPARATOR':
            config['row_separator'] = value if value else '\\n'
        elif name == 'HEADER':
            config['header_rows'] = int(value) if value.isdigit() else value
        elif name == 'FOOTER':
            config['footer_rows'] = int(value) if value.isdigit() else value
        elif name == 'LIMIT':
            config['limit'] = value
        elif name == 'ENCODING':
            config['encoding'] = value if value else 'ISO-8859-15'  # Talend default
        elif name == 'TEXT_ENCLOSURE':
            config['text_enclosure'] = value.replace('\\"', '')
        elif name == 'ESCAPE_CHAR':
            config['escape_char'] = value.replace('\\\\', '\\')
        elif name == 'CSV_OPTION':
            config['csv_option'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'CSVROWSEPARATOR':
            config['csv_row_separator'] = value
        elif name == 'SPLITRECORD':
            config['split_record'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'UNCOMPRESS':
            config['uncompress'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'REMOVE_EMPTY_ROW':
            config['remove_empty_rows'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'TRIMALL':
            config['trim_all'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'DIE_ON_ERROR':
            config['die_on_error'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'CHECK_FIELDS_NUM':
            config['check_fields_num'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'CHECK_DATE':
            config['check_date'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'ADVANCED_SEPARATOR':
            config['advanced_separator'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'THOUSANDS_SEPARATOR':
            config['thousands_separator'] = value if value else ','
        elif name == 'DECIMAL_SEPARATOR':
            config['decimal_separator'] = value if value else '.'
        elif name == 'RANDOM':
            config['random'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'NB_RANDOM':
            config['nb_random'] = int(value) if value.isdigit() else 0
        elif name == 'ENABLE_DECODE':
            config['enable_decode'] = (value.lower() == 'true') if field == 'CHECK' else False

    # Phase 2: Parse TRIMSELECT table parameter
    # TRIMSELECT contains elementValue pairs: SCHEMA_COLUMN + TRIM
    trim_select = []
    for param in node.findall('.//elementParameter[@name="TRIMSELECT"]'):
        current_entry = {}
        for item in param.findall('.//elementValue'):
            ref = item.get('elementRef')
            val = item.get('value', '')
            if ref == 'SCHEMA_COLUMN':
                # New entry -- push previous if exists
                if 'column' in current_entry:
                    trim_select.append(current_entry)
                    current_entry = {}
                current_entry['column'] = val
            elif ref == 'TRIM':
                current_entry['trim'] = val.lower() == 'true'
        # Push last entry
        if 'column' in current_entry:
            trim_select.append(current_entry)
    if trim_select:
        config['trim_select'] = trim_select

    # Phase 3: Parse DECODE_COLS table parameter
    # DECODE_COLS contains elementValue pairs: SCHEMA_COLUMN + DECODE
    decode_cols = []
    for param in node.findall('.//elementParameter[@name="DECODE_COLS"]'):
        current_entry = {}
        for item in param.findall('.//elementValue'):
            ref = item.get('elementRef')
            val = item.get('value', '')
            if ref == 'SCHEMA_COLUMN':
                if 'column' in current_entry:
                    decode_cols.append(current_entry)
                    current_entry = {}
                current_entry['column'] = val
            elif ref == 'DECODE':
                current_entry['decode'] = val.lower() == 'true'
        if 'column' in current_entry:
            decode_cols.append(current_entry)
    if decode_cols:
        config['decode_cols'] = decode_cols

    return component
```

**Registration in converter.py** (add before the existing `elif component_type == 'tFileInputExcel'` block):
```python
elif component_type == 'tFileInputDelimited':
    component = self.component_parser.parse_file_input_delimited(node, component)
```

**Key improvements over current `_map_component_parameters()` approach**:
1. Extracts ALL 30+ parameters instead of just 12
2. Handles table parameters (`TRIMSELECT`, `DECODE_COLS`) via `elementValue` iteration
3. Uses correct Talend defaults (`;` for delimiter, `ISO-8859-15` for encoding)
4. Marks `FILENAME` Java expressions via `mark_java_expression()`
5. Properly handles `CHECK` field type for boolean parameters
6. Follows the STANDARDS.md requirement for dedicated `parse_*` methods

---

## Appendix L: Converter Expression Handling Deep Dive

### How Context Variables Flow Through the Converter

When a Talend job contains `context.input_dir` in the `FILENAME` parameter, the following transformation chain occurs:

1. **Talend XML**: `<elementParameter name="FILENAME" value="&quot;/data/&quot;+context.input_dir+&quot;/input.csv&quot;" />`

2. **After XML parse and quote stripping**: `/data/"+context.input_dir+"/input.csv`
   Note: XML entity `&quot;` is already decoded by Python's XML parser.

3. **In `parse_base_component()` generic loop** (line 449):
   - Detects `'context.' in value` -> True
   - Calls `detect_java_expression(value)` to check if it's a Java expression
   - Since the value contains `+` (string concatenation operator), `detect_java_expression()` returns True
   - Value is NOT wrapped with `${...}` (left for Java execution)

4. **In Java expression marking** (line 469):
   - `mark_java_expression(value)` detects the `+` operator
   - Prefixes with `{{java}}`: `{{java}}/data/"+context.input_dir+"/input.csv`

5. **At engine runtime** (`BaseComponent._resolve_java_expressions()`):
   - Detects `{{java}}` prefix
   - Sends to Java bridge for evaluation
   - Java bridge resolves `context.input_dir` and concatenates strings
   - Result: `/data/inputs/input.csv` (example)

**Limitation**: Simple context references like `context.filepath` (without operators) get wrapped as `${context.filepath}` and resolved by the ContextManager. But expressions like `context.dir + "/file.csv"` require the Java bridge. If the Java bridge is not available, these expressions remain unresolved, causing runtime failures.

### How Boolean CHECK Fields Are Handled

For `elementParameter` nodes with `field="CHECK"`, the generic loop in `parse_base_component()` (line 445-446) converts:
- `value="true"` -> Python `True`
- `value="false"` -> Python `False`

This conversion happens BEFORE `_map_component_parameters()` is called. So when `_map_component_parameters()` reads `config_raw.get('REMOVE_EMPTY_ROW', False)`, the value is already a Python boolean.

**Implication for dedicated parser**: The dedicated parser must handle this differently since it reads directly from XML `elementParameter` nodes where the value is still a string. The parser must explicitly check `field == 'CHECK'` and convert accordingly (as shown in the Appendix K implementation).

---

## Appendix M: Comparison with tFileInputPositional Converter

The `tFileInputPositional` converter (lines 150-171 of `component_parser.py`) extracts several parameters that `tFileInputDelimited` does NOT. This comparison highlights the gap:

| Parameter | tFileInputPositional extracts? | tFileInputDelimited extracts? | Gap? |
|-----------|-------------------------------|-------------------------------|------|
| `FILENAME` | Yes | Yes | No |
| `ROWSEPARATOR` | Yes | Yes | No |
| `ENCODING` | Yes | Yes | No |
| `HEADER` | Yes | Yes | No |
| `FOOTER` | Yes | Yes | No |
| `LIMIT` | Yes | Yes | No |
| `TRIMALL` | Yes | Yes | No |
| `REMOVE_EMPTY_ROW` | Yes (as `remove_empty_row` singular) | Yes (as `remove_empty_rows` plural) | Naming inconsistency |
| `DIE_ON_ERROR` | Yes | Yes | No |
| `ADVANCED_SEPARATOR` | Yes (line 166) | **No** | Yes |
| `THOUSANDS_SEPARATOR` | Yes (line 167) | **No** | Yes |
| `DECIMAL_SEPARATOR` | Yes (line 168) | **No** | Yes |
| `CHECK_DATE` | Yes (line 169) | **No** | Yes |
| `UNCOMPRESS` | Yes (line 170) | **No** | Yes |
| `PROCESS_LONG_ROW` | Yes (line 165) | N/A (not applicable) | -- |

This demonstrates that the converter already has the pattern for extracting these parameters. The `tFileInputDelimited` mapping simply needs to be updated to include them, following the same approach used by `tFileInputPositional`.

**Naming inconsistency note**: `tFileInputPositional` uses `remove_empty_row` (singular), while `tFileInputDelimited` uses `remove_empty_rows` (plural). The STANDARDS.md documents the plural form, so `tFileInputPositional` is the one that deviates. This should be fixed for consistency.

---

## Appendix N: Detailed `_configure_csv_params()` Behavior Matrix

The `_configure_csv_params()` method (lines 521-540) determines how pandas handles quoting and escaping. Here is the complete decision matrix:

| text_enclosure | escape_char | Result | pandas params | Description |
|----------------|-------------|--------|---------------|-------------|
| `""` (empty) | any | Mode 1 | `quoting=csv.QUOTE_NONE` | No quoting. All characters treated literally. |
| `None` | any | Mode 1 | `quoting=csv.QUOTE_NONE` | No quoting. |
| `"ab"` (multi-char) | any | Mode 1 | `quoting=csv.QUOTE_NONE` | Length != 1 triggers QUOTE_NONE. Quoting disabled. **Potential data corruption for CSV files.** |
| `'"'` | `'"'` | Mode 2 | `quotechar='"', doublequote=True` | RFC4180 standard: doubled quotes for escaping. `""` inside field = literal `"`. |
| `'"'` | `'\\'` | Mode 3 | `quotechar='"', escapechar='\\'` | Backslash escaping: `\"` inside field = literal `"`. |
| `'"'` | `""` (empty) | Mode 3 | `quotechar='"', escapechar=None` | No escape char. Only unmatched quotes terminate fields. |
| `'"'` | `None` | Mode 3 | `quotechar='"', escapechar=None` | Same as empty escape_char. |
| `"'"` | `"'"` | Mode 2 | `quotechar="'", doublequote=True` | Single-quote enclosure with doubled escaping. |

**Talend comparison**:
- Talend's CSV_OPTION=true mode defaults to doublequote escaping (RFC4180 standard)
- Talend's escape_char default is `\\` (backslash), which differs from the doublequote convention
- The V1 engine auto-detects doublequote mode when `escape_char == text_enclosure`, which is a reasonable heuristic

**Gap**: There is no `csv_option` flag in the engine. The engine always uses the same parsing mode regardless of whether Talend's CSV_OPTION was enabled. In practice, this means:
- If text_enclosure and escape_char are properly set by the converter, CSV files parse correctly
- If CSV_OPTION was false in Talend (no quoting), the converter still extracts TEXT_ENCLOSURE and ESCAPE_CHAR, which may cause the engine to apply quoting when it should not

---

## Appendix O: Base Component `_update_global_map()` Detailed Analysis

The `_update_global_map()` method in `base_component.py` (lines 298-304) is critical because it propagates component statistics to the global map after every execution:

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} "
                     f"NB_LINE_OK:{self.stats['NB_LINE_OK']} "
                     f"NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} "
                     f"{stat_name}: {value}")  # BUG: 'value' is undefined
```

**Bug analysis** (BUG-FID-001):
- The for loop variable is `stat_value` (line 301), but the log statement references `value` (line 304)
- `stat_name` on line 304 references the loop variable from line 301, which will have the value from the LAST iteration of the for loop (i.e., `EXECUTION_TIME` since that is the last key in the `stats` dict)
- `value` is completely undefined in this scope, causing `NameError`
- This method is called from `execute()` (line 218) after EVERY component execution
- Since `self.global_map` is set by the engine during component instantiation, this bug will crash ANY component that runs in a job with a global map configured

**Call chain**:
1. `ETLEngine._execute_component()` calls `component.execute(input_data)`
2. `BaseComponent.execute()` calls `self._update_global_map()` on line 218 (success path) or line 231 (error path)
3. `_update_global_map()` crashes with `NameError: name 'value' is not defined`

**Severity**: This is the highest-severity bug in the v1 engine. It prevents ANY component from completing execution when a global map is present. The fix is trivial (see Appendix H) but the impact is cross-cutting.

---

## Appendix P: `GlobalMap.get()` Detailed Analysis

The `GlobalMap.get()` method in `global_map.py` (lines 26-28) has a complementary bug:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # BUG: 'default' not in signature
```

**Bug analysis** (BUG-FID-002):
- `default` is referenced in the body (line 28) but is not a parameter in the method signature (line 26)
- The method signature only accepts `key: str`
- Any call to `global_map.get("some_key")` will crash with `NameError: name 'default' is not defined`

**Cascading impact**:
- `get_component_stat()` (line 51-58) calls `self.get(key, default)` with TWO arguments, but `get()` only accepts ONE positional argument. This would cause `TypeError: get() takes 2 positional arguments but 3 were given`
- `get_nb_line()`, `get_nb_line_ok()`, `get_nb_line_reject()` all call `get_component_stat()` which calls `get()` with two args

**Fix**: Add `default: Any = None` to the `get()` method signature. This fixes both the `NameError` (direct calls) and the `TypeError` (two-argument calls from `get_component_stat()`).

---

## Appendix Q: Source References

- [tFileInputDelimited Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-standard-properties) -- Official Talend documentation for Basic and Advanced Settings, connection types, and global variables.
- [tFileInputDelimited Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/delimited/tfileinputdelimited-standard-properties) -- Talend 7.3 documentation with detailed property descriptions.
- [Component-specific settings for tFileInputDelimited (Job Script Reference Guide)](https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/component-specific-settings-for-tfileinputdelimited) -- XML parameter names and descriptions for job scripting.
- [tFileInputDelimited Properties File (GitHub)](https://github.com/EDS-APHP/TalendComponents/blob/master/tFileInputDelimitedAPHP/tFileInputDelimitedAPHP_messages_en.properties) -- Component properties file listing all parameter names and UI labels.
- [tFileInputDelimited Overview (Talend 7.3)](https://help.talend.com/r/en-US/7.3/delimited/tfileinputdelimited) -- Component overview, family, purpose, and framework support.
- [tFileInputDelimited v8.0.1 (Talend Skill)](https://talendskill.com/knowledgebase/tfileinputdelimited-talend-components-v8-0-1-20211103_1602/) -- Component connector types, returns, and required modules.
- [tFileInputDelimited Blog Reference (talendweb)](https://talendweb.wordpress.com/2016/07/27/tfileinputdelimited/) -- Community documentation on properties and global variables.
- [Retrieving data in error with a Reject link (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/mysql/tmysqloutput-tmap-tfileoutputdelimited-tfileinputdelimited-retrieving-data-in-error-with-reject-link-standard-component-this) -- REJECT flow behavior and errorCode/errorMessage column details.
- [NB_LINE Discussion (Talend Community)](https://community.talend.com/t5/Design-and-Development/Why-we-can-t-get-NB-LINE-of-tFileInputDelimited-on-flow/td-p/80749) -- NB_LINE availability and timing constraints.
- [Reject Row Count Discussion (Talend Community)](https://community.talend.com/t5/Design-and-Development/Count-of-rejected-rows-in-tFileinputdelimited-component/m-p/78335) -- NB_LINE_REJECT behavior and reject counting.
