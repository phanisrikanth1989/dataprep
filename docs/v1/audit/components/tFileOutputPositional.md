# Audit Report: tFileOutputPositional / FileOutputPositional

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileOutputPositional` |
| **V1 Engine Class** | `FileOutputPositional` |
| **Engine File** | `src/v1/engine/components/file/file_output_positional.py` (469 lines) |
| **Converter Parser (Generic)** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 172-187) |
| **Converter Parser (Dedicated)** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileoutputpositional()` (lines 2811-2848) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFileOutputPositional'` (line 377-378) |
| **Registry Aliases** | **NONE** -- `FileOutputPositional` is NOT registered in `src/v1/engine/engine.py` COMPONENT_REGISTRY; NOT imported in `engine.py` |
| **Category** | File / Output |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_output_positional.py` | Engine implementation (469 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 172-187) | Generic parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/component_parser.py` (lines 2811-2848) | Dedicated parser for FORMATS table XML extraction |
| `src/converters/complex_converter/converter.py` (line 377-378) | Dispatch -- dedicated `elif` branch for `tFileOutputPositional` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports -- `FileOutputPositional` IS exported |
| `src/v1/engine/engine.py` | Engine registry -- `FileOutputPositional` is NOT registered or imported |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 4 | 1 | 12 of 20 Talend params extracted (60%); FORMATS table has dedicated parser; missing ADVANCED_SEPARATOR, USE_BYTE_LENGTH, OUTPUT_ROW_MODE; flush param name mismatch; CREATE vs CREATE_DIRECTORY |
| Engine Feature Parity | **R** | 1 | 3 | 4 | 2 | NOT REGISTERED in engine; no zip compression (only gzip); no advanced separator; missing globalMap variables |
| Code Quality | **R** | 2 | 6 | 3 | 3 | Cross-cutting base class bugs; precision -1 ValueError; unicode_escape footgun; dead `_validate_config()`; NaN handling issues; gzip append mode bug |
| Performance & Memory | **Y** | 0 | 1 | 2 | 0 | Row-by-row `iterrows()` is inherently slow; no vectorized formatting; schema_map rebuilt per row |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; engine cannot even instantiate this component (not registered)**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileOutputPositional Does

`tFileOutputPositional` writes data to a fixed-width (positional) file, formatting each column at a specific position with a defined width, padding character, and alignment. Unlike delimited files where a separator character marks field boundaries, positional files use fixed column widths -- each field occupies a predetermined number of characters, padded as needed. This format is common in mainframe data exchange, banking (SWIFT, NACHA), regulatory reporting, and legacy system integration.

The component receives input data via a Row Main connection, formats each row according to the Formats table configuration, and writes the result to the specified file path. The input DataFrame is passed through unchanged as output.

**Source**: [tFileOutputPositional Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/positional/tfileoutputpositional-standard-properties), [tFileOutputPositional Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/positional/tfileoutputpositional-standard-properties), [tFileOutputPositional (Talend Skill ESB 7.x)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfileoutputpositional-talend-open-studio-for-esb-document-7-x/)

**Component family**: Positional (File / Output)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Use Existing Dynamic | `USE_DYNAMIC_SCHEMA` | Boolean (CHECK) | `false` | Reuse an existing dynamic schema to handle data from unknown columns. |
| 3 | Use Output Stream | `USE_OUTPUT_STREAM` | Boolean (CHECK) | `false` | Process data flow of interest via stream variable instead of file path. |
| 4 | Output Stream | `OUTPUT_STREAM` | String | -- | Data flow variable to write to. Only visible when `USE_OUTPUT_STREAM=true`. |
| 5 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path for the output file. Supports context variables, globalMap references, Java expressions. |
| 6 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the expected input structure. |
| 7 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | Character(s) identifying the end of a row. Supports `\r\n`, `\n`, `\r`. |
| 8 | Append | `APPEND` | Boolean (CHECK) | `false` | Add new rows at the end of an existing file. When false, file is overwritten. |
| 9 | Include Header | `INCLUDEHEADER` | Boolean (CHECK) | `false` | Include column header row at the top of the file. Header uses column names from the schema. |
| 10 | Compress as Zip File | `COMPRESS` | Boolean (CHECK) | `false` | Compress the output file in ZIP format. |

### 3.2 Formats Table

The Formats table is the core configuration of tFileOutputPositional. It defines how each column is formatted in the fixed-width output.

| # | Column | Talend XML Ref | Type | Default | Description |
|---|--------|----------------|------|---------|-------------|
| F1 | Column | `SCHEMA_COLUMN` | Dropdown | -- | **Required**. Select the schema column to format. |
| F2 | Size | `SIZE` | Integer | -- | **Required**. Fixed width of the column in characters. |
| F3 | Padding Char | `PADDING_CHAR` | Character | `' '` (space) | Character used to pad values shorter than the column size. |
| F4 | Alignment | `ALIGN` | Enum (L/R) | `L` | **L** = Left-align (pad on right), **R** = Right-align (pad on left). Numeric columns typically use R alignment with '0' padding. |
| F5 | Keep | `KEEP` | Enum (A/C) | `A` | Behavior when data exceeds column size. **A** = All (keep full value, exceeding the size), **C** = Cut/Crop (truncate to fit column size). |

**Behavioral notes on Formats table**:
1. **KEEP='A' (All)**: The data value is written in full even if it exceeds the column SIZE. This means the total row length may exceed the expected fixed width, potentially corrupting the positional layout of subsequent columns on the same row. This is Talend's default and is intentional -- it preserves data at the cost of format compliance.
2. **KEEP='C' (Cut/Crop)**: The data value is truncated to exactly SIZE characters. This preserves the fixed-width layout but may lose data.
3. **Padding is applied AFTER truncation** (if KEEP='C') or to values shorter than SIZE. The padding character fills the remaining space.
4. **Header formatting**: Column names in the header row also respect SIZE and ALIGN from the Formats table.

### 3.3 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 11 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number formatting with custom thousands and decimal separators. |
| 12 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric output. Only visible when `ADVANCED_SEPARATOR=true`. |
| 13 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric output. Only visible when `ADVANCED_SEPARATOR=true`. |
| 14 | Use Byte Length | `USE_BYTE_LENGTH` | Boolean (CHECK) | `false` | Use byte length instead of character length for column sizing. Required for double-byte character sets (CJK, etc.). Requires JDK 1.6+. |
| 15 | Create Directory | `CREATE_DIRECTORY` | Boolean (CHECK) | `true` | Create output directory if it does not exist. |
| 16 | Custom Flush Buffer | `CUSTOM_FLUSH_BUFFER` | Boolean (CHECK) | `false` | Enable custom buffer flush frequency. |
| 17 | Row Number (Flush) | `ROW_NUMBER` | Integer | -- | Number of rows to write before flushing the buffer. Only visible when `CUSTOM_FLUSH_BUFFER=true`. |
| 18 | Output in Row Mode | `OUTPUT_ROW_MODE` | Boolean (CHECK) | `false` | Write in row mode (one row at a time). |
| 19 | Don't Generate Empty File | `DONT_GENERATE_EMPTY_FILE` | Boolean (CHECK) | `false` | Prevent creation of an empty output file when there is no input data. |
| 20 | Encoding | `ENCODING` | Dropdown / Custom | JVM-dependent | Character encoding for file writing. Options include ISO-8859-15, UTF-8, and custom values. |
| 21 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher. |
| 22 | Label | `LABEL` | String | -- | Component label for Talend Studio canvas. No runtime impact. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `Row Main` | Input | Row > Main | Primary data input. DataFrame of rows to write to the positional file. |
| `FLOW` (Main) | Output | Row > Main | Pass-through of input data. The component outputs the same data it received, allowing chaining to downstream components. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: Unlike input components, `tFileOutputPositional` does NOT have a REJECT flow. It is a write-only component -- rows either succeed or fail the entire write operation.

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows written to the output file. This is the primary row count variable. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

**Note**: Official Talend documentation lists only `NB_LINE` and `ERROR_MESSAGE` for this component. Unlike database output components, there is no `NB_LINE_INSERTED` or `NB_LINE_UPDATED` -- all writes are inserts.

### 3.6 Behavioral Notes

1. **Pass-through behavior**: The component writes data to the file AND passes the input DataFrame through unchanged to any downstream component connected via the Main output flow. This allows chaining: `tMap -> tFileOutputPositional -> tLogRow` would write to file AND display data.

2. **APPEND=true**: New rows are added to the end of the existing file. If the file does not exist, it is created. When `INCLUDE_HEADER=true` and `APPEND=true`, the header is written with each append, potentially creating multiple header rows. Talend Studio warns about this but does not prevent it.

3. **COMPRESS=true**: Talend compresses in **ZIP** format (not gzip). The output is a standard ZIP archive containing the positional file. This uses Java's `ZipOutputStream`.

4. **Default encoding**: Talend defaults to the JVM's default encoding (typically ISO-8859-15 on European systems, UTF-8 on modern systems). The v1 engine defaults to `utf-8`.

5. **INCLUDE_HEADER default**: In Talend, the default for `INCLUDEHEADER` is **false** (unchecked). The v1 engine defaults to **true**, which differs from Talend behavior.

6. **Empty input behavior**: When the component receives no input rows (empty DataFrame or null), it either creates an empty file or skips file creation depending on `DONT_GENERATE_EMPTY_FILE`. If `DONT_GENERATE_EMPTY_FILE=true` and no data exists, no file is written (or an existing file is preserved).

7. **Numeric precision in positional files**: Float and decimal values are formatted with a specified precision. The precision comes from the schema column's `precision` attribute. If no precision is defined, Talend uses the Java default formatting.

8. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow.

9. **Row separator default**: Talend defaults to `"\n"`. The component writes the row separator AFTER each data row, including the last row (trailing newline).

10. **KEEP='A' is dangerous**: When KEEP='A' (the default), values exceeding the column SIZE are NOT truncated. This means a single oversized value shifts ALL subsequent columns on that row, breaking the fixed-width format. Production jobs should typically use KEEP='C' for data integrity.

---

## 4. Converter Audit

### 4.1 Converter Architecture

The converter uses a **two-stage approach** for `tFileOutputPositional`:

1. **Stage 1: Generic parameter mapping** (`_map_component_parameters()` in `component_parser.py` lines 172-187). This extracts scalar parameters (filepath, row_separator, append, etc.) from the raw `config_raw` dictionary built by `parse_base_component()`.

2. **Stage 2: Dedicated table parser** (`parse_tfileoutputpositional()` in `component_parser.py` lines 2811-2848). Called from `converter.py` line 378, this parses the FORMATS table from Talend XML `<elementParameter name="FORMATS">` elements and overwrites the `formats` key in `component['config']`.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tFileOutputPositional', config_raw)` (line 472), producing scalar config
4. Returns component with scalar config (formats = [] at this point since FORMATS is a table)
5. `converter.py` line 378 calls `parse_tfileoutputpositional(node, component)`
6. Dedicated parser extracts FORMATS table XML, overwrites `component['config']['formats']`
7. Also merges format info (size, padding_char, align) into output schema columns

### 4.2 Parameter Extraction

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | 175 | Expressions and context vars handled by generic loop |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | 176 | Default `'\n'` matches Talend |
| 3 | `APPEND` | Yes | `append` | 177 | Boolean from CHECK field type |
| 4 | `INCLUDEHEADER` | Yes | `include_header` | 178 | **Default `True` differs from Talend default `false`** |
| 5 | `COMPRESS` | Yes | `compress` | 179 | Boolean from CHECK field type |
| 6 | `ENCODING` | Yes | `encoding` | 180 | **Default `'UTF-8'` may differ from Talend JVM-dependent default** |
| 7 | `CREATE_DIRECTORY` | **Partial** | `create` | 181 | **Converter reads `CREATE` not `CREATE_DIRECTORY`**. If Talend XML uses `CREATE_DIRECTORY`, lookup misses it (silently defaults to `True`, which is correct default). See CONV-FOP-006. |
| 8 | `CUSTOM_FLUSH_BUFFER` | **No (wrong key)** | `flush_on_row` | 182 | **Converter reads `FLUSHONROW` but Talend XML name is `CUSTOM_FLUSH_BUFFER`**. Lookup will miss the actual Talend parameter. See CONV-FOP-005. |
| 9 | `ROW_NUMBER` (Flush) | **No (wrong key)** | `flush_on_row_num` | 183 | **Converter reads `FLUSHONROW_NUM` but Talend XML name is `ROW_NUMBER`**. Lookup will miss the actual Talend parameter. See CONV-FOP-005. |
| 10 | `DONT_GENERATE_EMPTY_FILE` | Yes | `delete_empty_file` | 184 | Renamed from `DELETE_EMPTYFILE` |
| 11 | `FORMATS` (table) | Yes | `formats` | 2814-2833 | Parsed by dedicated `parse_tfileoutputpositional()` method |
| 12 | `DIE_ON_ERROR` | Yes | `die_on_error` | 186 | Default `True` -- matches Talend |
| 13 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted. Locale-aware number formatting unavailable.** |
| 14 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 15 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 16 | `USE_BYTE_LENGTH` | **No** | -- | -- | **Not extracted. Double-byte character support unavailable.** |
| 17 | `OUTPUT_ROW_MODE` | **No** | -- | -- | **Not extracted. Engine always writes in row mode anyway.** |
| 18 | `USE_OUTPUT_STREAM` | **No** | -- | -- | **Not extracted. Stream output not supported.** |
| 19 | `OUTPUT_STREAM` | **No** | -- | -- | **Not extracted.** |
| 20 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 21 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 22 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 12 of 22 parameters nominally extracted (~55%), but 2 use wrong XML key names (`FLUSHONROW`/`FLUSHONROW_NUM` instead of `CUSTOM_FLUSH_BUFFER`/`ROW_NUMBER`) and 1 uses a potentially wrong key (`CREATE` instead of `CREATE_DIRECTORY`), reducing effective extraction to 9 of 22 (~41%). 7 runtime-relevant parameters are missing, though 3 of those (`OUTPUT_ROW_MODE`, `USE_OUTPUT_STREAM`, `OUTPUT_STREAM`) are rarely used.

### 4.3 Formats Table Parsing (Dedicated Parser)

The dedicated parser `parse_tfileoutputpositional()` (lines 2811-2848) handles the FORMATS table:

**Parsing logic**:
```
for param in node.findall('.//elementParameter[@name="FORMATS"]'):
    for item in param.findall('./elementValue'):
        ref = item.get('elementRef')
        if ref == 'SCHEMA_COLUMN':
            # Start new format entry
            fmt['SCHEMA_COLUMN'] = value.strip('"')  # UPPERCASE key
        elif ref and value:
            fmt[ref.lower()] = value.strip('"')  # lowercase keys for SIZE, PADDING_CHAR, etc.
```

**Key observation -- case inconsistency**: The parser stores `SCHEMA_COLUMN` as an **uppercase** key in the format dict, but all other keys (`size`, `padding_char`, `align`, `keep`) are stored as **lowercase** (via `ref.lower()`). The engine code in `_prepare_column_formats()` handles this by checking both cases: `fmt.get('schema_column') or fmt.get('SCHEMA_COLUMN')`. This works but is fragile.

**Schema merging**: After parsing formats, the dedicated parser merges format info into the output schema columns (lines 2836-2848), adding `size`, `padding_char`, and `align` attributes to matching schema columns. This is good for schema-aware processing but does NOT merge the `keep` attribute.

### 4.4 Schema Extraction

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
| `comment` | **No** | Column comment not extracted (cosmetic) |
| `talendType` | **No** | Full Talend type string not preserved |

### 4.5 Expression Handling

**Context variable handling** (component_parser.py lines 449-456):
- Simple `context.var` references in non-CODE/IMPORT fields are detected by checking `'context.' in value`
- If the expression is NOT a Java expression (per `detect_java_expression()`), it is wrapped as `${context.var}` for ContextManager resolution
- If it IS a Java expression, it is left as-is for Java expression marking

**Java expression handling** (component_parser.py lines 462-469):
- After raw parameter extraction, `mark_java_expression()` scans all non-CODE/IMPORT/UNIQUE_NAME string values
- Values containing Java operators, method calls, etc. are prefixed with `{{java}}` marker
- The engine's `BaseComponent._resolve_java_expressions()` resolves these at runtime

**Known limitation for filepath**: The `FILENAME` value often contains Java string concatenation (e.g., `context.output_dir + "/file.txt"`). The expression converter should correctly mark this with `{{java}}` for bridge resolution.

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FOP-001 | **P1** | **`INCLUDEHEADER` default mismatch**: Converter defaults `include_header` to `True` (line 178), but Talend's default is `false` (unchecked). Jobs that rely on the Talend default of no header will incorrectly produce a header row in v1. This can corrupt positional file consumers that expect data starting at byte 0. |
| CONV-FOP-002 | **P1** | **Formats table key case inconsistency**: The dedicated parser stores `SCHEMA_COLUMN` in uppercase but `size`, `padding_char`, `align`, `keep` in lowercase. While the engine handles both cases, a future refactor or third-party consumer of the JSON config may not. Should normalize all keys to lowercase. |
| CONV-FOP-003 | **P2** | **`ADVANCED_SEPARATOR` / `THOUSANDS_SEPARATOR` / `DECIMAL_SEPARATOR` not extracted**: Locale-aware number formatting unavailable. Files requiring European number format (e.g., `1.234,56`) will produce incorrect output. |
| CONV-FOP-004 | **P2** | **`USE_BYTE_LENGTH` not extracted**: Double-byte character sizing unavailable. CJK characters (which are 2-3 bytes in UTF-8) will be counted as 1 character, producing misaligned columns. |
| CONV-FOP-005 | **P1** | **Converter XML parameter name mismatch for flush**: The converter reads `FLUSHONROW` (line 182) but Talend's actual XML parameter name is `CUSTOM_FLUSH_BUFFER`. The converter reads `FLUSHONROW_NUM` (line 183) but Talend uses `ROW_NUMBER`. Since `config_raw` is built from actual Talend XML element names, these lookups will never match the Talend XML, causing flush configuration to silently fall back to defaults (`False` and `1`). Jobs with custom flush settings will ignore them. |
| CONV-FOP-006 | **P2** | **Converter `CREATE` may not match Talend's `CREATE_DIRECTORY`**: The converter reads `config_raw.get('CREATE', True)` (line 181), but the Talend XML parameter documented in Section 3.3 is `CREATE_DIRECTORY`. Other converters in the codebase use `CREATE_DIRECTORY`. If Talend emits `CREATE_DIRECTORY` in the XML, the `CREATE` lookup will miss it and silently default to `True` (which happens to be the correct default, masking the bug). |
| CONV-FOP-007 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). The engine handles both but this violates documented standards. |
| CONV-FOP-008 | **P3** | **`keep` attribute not merged into schema**: The dedicated parser merges `size`, `padding_char`, and `align` into output schema columns (lines 2842-2847) but omits `keep`. This is inconsistent. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Write fixed-width file | **Yes** | High | `_write_positional_file()` line 261 | Core implementation using row-by-row formatting |
| 2 | Column alignment (L/R) | **Yes** | High | `_format_data_row()` line 461-464 | `ljust()`/`rjust()` with padding char |
| 3 | Padding character | **Yes** | High | `_prepare_column_formats()` line 365 | Handles single-quoted padding chars (e.g., `"' '"`) |
| 4 | Column size enforcement | **Yes** | Medium | `_format_data_row()` line 456 | Truncation only when KEEP='C'; KEEP='A' allows overflow |
| 5 | KEEP option (A/C) | **Yes** | High | `_format_data_row()` line 457-458 | 'C' truncates, 'A' preserves full value |
| 6 | Header row writing | **Yes** | High | `_format_header_row()` line 384 | Headers respect size/align/pad from formats |
| 7 | Append mode | **Yes** | Medium | `_write_positional_file()` line 285 | See BUG-FOP-003 for gzip+append issue |
| 8 | Row separator | **Yes** | High | `_process()` line 225-227 | Decodes escape sequences via `unicode_escape` |
| 9 | Encoding support | **Yes** | Medium | `_write_positional_file()` line 301 | Passed to `open()`. Not applied to gzip mode correctly |
| 10 | gzip compression | **Yes** | Low | `_write_positional_file()` line 298 | **Talend uses ZIP, not gzip**. Fundamental format mismatch. |
| 11 | Create directory | **Yes** | High | `_write_positional_file()` line 291-293 | `os.makedirs(exist_ok=True)` |
| 12 | Flush buffer control | **Yes** | High | `_write_positional_file()` line 325-327 | Flushes every `flush_on_row_num` rows |
| 13 | Delete empty file | **Yes** | High | `_process()` line 210-215, 236-239 | Handles both empty input and post-write empty file |
| 14 | Numeric type formatting | **Yes** | Medium | `_format_data_row()` line 441-451 | Float precision formatting and integer truncation |
| 15 | Empty input handling | **Yes** | High | `_process()` line 208 | Returns empty DataFrame with stats (0,0,0) |
| 16 | Pass-through output | **Yes** | High | `_process()` line 245 | Returns `{'main': input_data}` (original DataFrame) |
| 17 | Die on error | **Yes** | High | `_process()` lines 190-195, 247-259 | Raises or returns gracefully based on flag |
| 18 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 19 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 20 | **ZIP compression** | **No** | N/A | -- | **Talend uses ZIP; engine uses gzip. Fundamental mismatch. See ENG-FOP-002.** |
| 21 | **Advanced separator** | **No** | N/A | -- | **No locale-aware number formatting.** |
| 22 | **Byte-length sizing** | **No** | N/A | -- | **No double-byte character support for column sizing.** |
| 23 | **Output stream mode** | **No** | N/A | -- | **No stream output support.** |
| 24 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |
| 25 | **`{id}_FILENAME` globalMap** | **No** | N/A | -- | **Resolved filename not stored in globalMap.** |
| 26 | **Engine registry** | **No** | N/A | `engine.py` | **Component NOT registered. Cannot be instantiated by engine.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FOP-001 | **P0** | **Component not registered in engine**: `FileOutputPositional` is NOT imported or registered in `src/v1/engine/engine.py` COMPONENT_REGISTRY. The engine cannot instantiate this component at all. Jobs containing `tFileOutputPositional` will fail with "Unknown component type" error. The class exists in `file_output_positional.py` and is exported from `__init__.py`, but the engine cannot find it. This is a complete blocker. |
| ENG-FOP-002 | **P1** | **Compression format mismatch: gzip vs ZIP**: Talend's `COMPRESS` option creates a **ZIP archive** (using Java's `ZipOutputStream`). The v1 engine uses Python's `gzip` module (line 298), producing a **gzip** file (.gz). These are incompatible formats. A downstream system expecting a ZIP file will fail to read a gzip file. The import at line 7 (`import gzip`) confirms this is gzip, not zipfile. |
| ENG-FOP-003 | **P1** | **`INCLUDEHEADER` default differs from Talend**: Engine default is `DEFAULT_INCLUDE_HEADER = True` (line 76), Talend default is `false`. Every job without an explicit `INCLUDEHEADER` setting will produce an unexpected header row. |
| ENG-FOP-004 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. The catch block (line 247-259) logs the error but does not call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`. |
| ENG-FOP-005 | **P2** | **No advanced separator support**: Numeric values are formatted using Python's default locale (decimal point = `.`, no thousands separator). Files requiring European number format (e.g., `1.234,56`) will have incorrect formatting. |
| ENG-FOP-006 | **P2** | **No byte-length sizing**: Column SIZE is measured in characters (`len(val)` on line 456), not bytes. For double-byte character sets (CJK), a 2-byte character counts as 1, producing columns narrower than expected. |
| ENG-FOP-007 | **P2** | **KEEP='A' does not warn about overflow**: When `KEEP='A'` and a value exceeds the column SIZE, the value is written in full (line 456-458 only truncates for KEEP='C'). However, no warning is logged about the overflow, making it difficult to detect format corruption. |
| ENG-FOP-008 | **P2** | **No output stream support**: The `USE_OUTPUT_STREAM` mode is not supported. Jobs writing to a stream variable instead of a file path will fail. |
| ENG-FOP-009 | **P3** | **Encoding default differs**: Engine defaults to `utf-8` (line 74), Talend defaults to JVM-dependent encoding (often `ISO-8859-15`). May cause encoding issues for non-ASCII characters. |
| ENG-FOP-010 | **P3** | **Header always truncated, never overflows**: In `_format_header_row()` line 402-403, headers are always truncated to SIZE (`val[:fmt['size']]`), regardless of the KEEP setting. In Talend, the KEEP setting also applies to headers. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. **However, `_update_global_map()` has a NameError bug (see BUG-FOP-001).** |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set to rows_written count |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Set to 0 on success, rows_in on total failure. No per-row reject tracking. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. Error messages logged but not stored in globalMap. |
| `{id}_FILENAME` | Uncertain | **No** | -- | Not implemented. Resolved filepath not stored. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FOP-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileOutputPositional, since `_update_global_map()` is called after every component execution (via `execute()` line 218). Note: line 304 IS inside the for loop (indented under `for stat_name, stat_value in self.stats.items():` on line 301), so `stat_name` is valid -- only the `value` reference (should be `stat_value`) is the actual bug. |
| BUG-FOP-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FOP-003 | **P1** | `src/v1/engine/components/file/file_output_positional.py:285` | **gzip append mode uses binary-only mode `'ab'`**: The mode selection `mode = 'ab' if compress else ('a' if append else 'w')` always uses `'ab'` for compressed files regardless of the `append` flag. This means: (1) compressed files ALWAYS append (never overwrite), and (2) the gzip open uses binary mode `'ab'` while the regular open uses text mode `'a'`/`'w'`. The `gzip.open(filepath, mode)` call on line 298 would need mode `'wb'` for non-append gzip writes. |
| BUG-FOP-004 | **P1** | `src/v1/engine/components/file/file_output_positional.py:93` | **`_validate_config()` is never called**: The method contains 60 lines of validation logic (lines 93-153) including format validation, size checks, alignment checks, and keep option checks. But it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (empty formats, negative sizes, invalid alignments) are not caught until they cause runtime errors during file writing. |
| BUG-FOP-005 | **P1** | `src/v1/engine/components/file/file_output_positional.py:220` | **`fillna('')` converts ALL NaN to empty string before formatting**: Line 220 `data = input_data.fillna('')` converts NaN/None values to empty strings. While this prevents formatting errors, it loses the distinction between "column has no value" and "column has an empty string value". In Talend, null values in positional files produce a fully-padded field (all padding chars), which the v1 engine also produces since `''` gets padded to full size. However, the early blanket `fillna('')` happens BEFORE any type-specific formatting, which means `float('nan')` is converted to `''` and then the numeric formatter (line 444) sees `val != ''` as False, so it outputs `''` instead of a formatted zero. This is actually correct for Talend null behavior, but the logic is fragile and depends on the empty-string check. |
| BUG-FOP-006 | **P2** | `src/v1/engine/components/file/file_output_positional.py:432-433` | **`schema_map` rebuilt on EVERY row**: Inside `_format_data_row()`, the code builds `schema_map = {col['name']: col for col in schema} if schema else {}` on lines 432-433. This dict comprehension runs for every row in the DataFrame. For a 1 million row file with 20 schema columns, this creates and discards 1 million dictionaries. The schema_map should be built once in `_prepare_column_formats()` or cached. |
| BUG-FOP-007 | **P3** | `src/v1/engine/components/file/file_output_positional.py:456-464` | **KEEP='A' overflow silently produces misaligned rows (informational)**: When `KEEP='A'` and `len(val) > fmt['size']`, the value is NOT truncated (line 456-458 only handles 'C'). The subsequent `ljust`/`rjust` on lines 461-464 does NOT add padding to oversized strings -- Python's `ljust`/`rjust` return the string unchanged when it is already longer than the specified width. So the column is not made wider by padding, but the oversized value itself still silently corrupts the positional layout for all subsequent columns on the row. No warning is logged. This matches Talend's KEEP='A' behavior (preserve full value at cost of format compliance). Downgraded from P2 to P3 informational since the behavior is correct per Talend spec. |
| BUG-FOP-008 | **P2** | `src/v1/engine/components/file/file_output_positional.py:364` | **`int(fmt.get('size') or fmt.get('SIZE'))` crashes on missing SIZE**: If neither `size` nor `SIZE` key exists in the format dict, both `fmt.get('size')` and `fmt.get('SIZE')` return `None`. The expression `None or None` evaluates to `None`, and `int(None)` raises `TypeError`. While `_validate_config()` would catch this, it is never called (BUG-FOP-004). |
| BUG-FOP-009 | **P1** | `src/v1/engine/components/file/file_output_positional.py:443-444` + `src/converters/complex_converter/component_parser.py:733` | **Precision `-1` from converter causes `ValueError`**: The converter sets `precision = int(column.get('precision', -1))` (component_parser.py line 733 and multiple other locations). Since the `precision` key exists in the schema dict with value `-1`, the engine's `schema_map.get(col, {}).get('precision', self.DEFAULT_PRECISION)` on line 443 finds the key and returns `-1` -- the `DEFAULT_PRECISION` (8) fallback never triggers. Line 444 then executes `f'{float(val):.{-1}f}'` which raises `ValueError` for any float/double/decimal column without an explicit precision attribute in the Talend XML. This is a **cross-cutting** issue: every converter code path that uses `int(column.get('precision', -1))` produces schemas that trigger this crash. |
| BUG-FOP-010 | **P1** | `src/v1/engine/components/file/file_output_positional.py:226` | **`unicode_escape` row separator decoding is a Python footgun**: Line 226 does `row_separator.encode('utf-8').decode('unicode_escape')`. The `unicode_escape` codec treats input as Latin-1, not UTF-8. This means: (1) non-ASCII content in the row separator is corrupted because multi-byte UTF-8 sequences are decoded as individual Latin-1 characters, (2) literal backslashes followed by certain characters (e.g., `\x`, `\u`) produce unintended escape sequences, and (3) Python 3.12+ raises `DeprecationWarning` (upgrading to error in future versions) for invalid escape sequences. The correct approach for decoding user escape sequences is `codecs.decode(row_separator, 'unicode_escape')` on a pure ASCII string, or using `ast.literal_eval(f'"{row_separator}"')`. |
| BUG-FOP-011 | **P3** | `src/v1/engine/components/file/file_output_positional.py:259` | **`input_data or pd.DataFrame()` truthy check on DataFrame**: Line 259 `return {'main': input_data or pd.DataFrame()}` uses the `or` operator on a DataFrame. For a non-empty DataFrame, this works. But for an empty DataFrame, `bool(pd.DataFrame())` raises `ValueError: The truth value of a DataFrame is ambiguous`. Should use `input_data if input_data is not None else pd.DataFrame()`. Same issue on lines 195 and 205. |

### 6.2 NaN and Empty Value Handling Analysis

| Scenario | Talend Behavior | V1 Behavior | Correct? |
|----------|----------------|-------------|----------|
| NaN in string column | Padded field (all pad chars) | `fillna('')` -> `str('')` -> padded field | **Yes** |
| NaN in numeric column | Padded field (all pad chars) | `fillna('')` -> `val=''` -> `val != ''` is False -> `''` -> padded field | **Yes** (by accident) |
| NaN in integer column | Padded field (all pad chars) | `fillna('')` -> `val=''` -> `val != ''` is False -> `''` -> padded field | **Yes** (by accident) |
| Empty string in string col | Padded field (all pad chars) | `str('')` -> padded field | **Yes** |
| Zero in numeric column | Formatted zero (e.g., `0.00000000`) | `float(0)` -> `0.00000000` -> padded | **Yes** |
| Empty DataFrame | No file or empty file | Returns empty DataFrame, no rows written | **Yes** |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FOP-001 | **P2** | **`delete_empty_file` vs Talend's `DONT_GENERATE_EMPTY_FILE`**: The converter maps `DELETE_EMPTYFILE` to `delete_empty_file`, but the Talend parameter is actually `DONT_GENERATE_EMPTY_FILE`. The semantic is subtly different: "delete empty file" implies deleting AFTER write, "don't generate" implies not creating at all. The engine implementation (line 210-215) handles both semantics (delete if exists + skip write), but the naming is misleading. |
| NAME-FOP-002 | **P3** | **`flush_on_row` / `flush_on_row_num` naming**: Talend parameters are `CUSTOM_FLUSH_BUFFER` and `ROW_NUMBER`. The v1 names `flush_on_row` and `flush_on_row_num` are clearer but non-standard relative to Talend names. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FOP-001 | **P1** | "Component MUST be registered in engine.py COMPONENT_REGISTRY" | `FileOutputPositional` is NOT registered. Cannot be instantiated. |
| STD-FOP-002 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists and is well-implemented but never called. Dead code. |
| STD-FOP-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types. |
| STD-FOP-004 | **P2** | "Component should use custom exceptions from exceptions.py" | Component raises generic `ValueError` and `IOError` instead of `ConfigurationError` / `FileOperationError`. |

### 6.5 Debug Artifacts

No debug artifacts (print statements, `# ...existing code...` comments) found in the engine file.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 169); logs completion with row count (line 243) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| **Gap**: No overflow warning | When KEEP='A' and value exceeds SIZE, no warning logged. Should warn about positional format corruption. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **Uses generic `ValueError` and `IOError`** instead of `ConfigurationError` / `FileOperationError`. Violates exception hierarchy. |
| Exception chaining | Outer catch (line 247) does `raise` (bare re-raise) which preserves the original traceback -- correct. Inner `_write_positional_file` (line 342) also does bare `raise` -- correct. |
| `die_on_error` handling | Two paths: `_process()` early validation (lines 190, 200) and outer catch-all (line 255) -- correct. |
| No bare `except` | Line 247 uses `except Exception as e` -- correct. Line 336 uses `except Exception as e` -- correct. Line 340 uses bare `except Exception:` for cleanup -- acceptable for cleanup. |
| Error messages | Include component ID and error details -- correct |
| File handle cleanup | `_write_positional_file()` uses try/finally pattern with explicit `file_handle.close()` in both success and error paths (lines 330-342) -- correct. |
| **Gap**: Error stats | On error, stats set to `(rows_in, 0, rows_in)` (line 251-252), meaning ALL rows are counted as rejected. This is correct for a total failure but loses partial write information. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_write_positional_file()`, `_format_data_row()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict]` -- correct |
| **Gap**: `_prepare_column_formats` return type | Returns `tuple` but should be `Tuple[List[Dict], List[str], List[str]]` for clarity |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FOP-001 | **P1** | **Row-by-row `iterrows()` is fundamentally slow**: `_write_positional_file()` uses `data.iterrows()` (line 317) which is the slowest way to iterate a pandas DataFrame. For a 1 million row file, this can be 10-100x slower than vectorized approaches. Each iteration creates a new pandas Series object. Should use `itertuples()` (3-5x faster) or vectorized string formatting with `apply()` on columns. |
| PERF-FOP-002 | **P2** | **`schema_map` dictionary rebuilt per row**: `_format_data_row()` rebuilds `schema_map = {col['name']: col for col in schema}` on EVERY row (line 432-433). This creates and discards one dictionary per row. Should be built once and passed as a parameter. |
| PERF-FOP-003 | **P2** | **String concatenation in tight loop**: `_format_data_row()` builds the output line using `line += val` (line 466) in a loop over columns. For files with many columns, this creates intermediate string objects. Should use `''.join()` on a list. Similarly, `_format_header_row()` uses `header += val` (line 411). |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Input handling | `input_data.fillna('')` on line 220 creates a full copy of the DataFrame. For large DataFrames, this doubles memory usage temporarily. |
| File handle | Single file handle opened and closed properly. No memory leak risk. |
| Streaming mode | **Not implemented for output**. The base class `_execute_streaming()` would call `_process()` per chunk, but the component writes a single file. Append mode would be needed for chunked output. |
| String building | Row strings are built column-by-column and written immediately (not accumulated in memory). This is memory-efficient. |
| Compression buffer | gzip compresses on-the-fly via the file handle. No full-file buffering. |

### 7.2 Scalability Estimates

| Rows | Columns | Estimated Time | Bottleneck |
|------|---------|---------------|------------|
| 10,000 | 10 | < 1 second | N/A |
| 100,000 | 10 | ~2-5 seconds | `iterrows()` overhead |
| 1,000,000 | 10 | ~20-60 seconds | `iterrows()` + string concat |
| 10,000,000 | 10 | ~3-10 minutes | `iterrows()` + `fillna` copy |
| 1,000,000 | 100 | ~2-10 minutes | String concat per column per row |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileOutputPositional` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 469 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic positional write | P0 | Write a simple DataFrame with 3 columns (string, int, float) to a positional file, verify column positions and widths match formats config |
| 2 | Left and right alignment | P0 | Write columns with L and R alignment, verify padding is on the correct side |
| 3 | Padding character | P0 | Write with custom padding chars ('0' for numeric, ' ' for string), verify correct padding |
| 4 | KEEP='C' truncation | P0 | Write a value exceeding column SIZE with KEEP='C', verify truncation to exact SIZE |
| 5 | KEEP='A' overflow | P0 | Write a value exceeding column SIZE with KEEP='A', verify full value preserved (even though it breaks format) |
| 6 | Empty DataFrame input | P0 | Write empty DataFrame, verify empty file or no file created based on `delete_empty_file` |
| 7 | Pass-through output | P0 | Verify `_process()` returns `{'main': input_data}` with the original DataFrame unchanged |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Header row | P1 | Write with `include_header=True`, verify header row uses column names with correct alignment/padding |
| 9 | No header row | P1 | Write with `include_header=False`, verify no header row present |
| 10 | Append mode | P1 | Write to existing file with `append=True`, verify old content preserved and new rows appended |
| 11 | Overwrite mode | P1 | Write to existing file with `append=False`, verify old content replaced |
| 12 | Missing filepath | P1 | Verify `ValueError` raised when `die_on_error=True`, graceful return when `False` |
| 13 | Missing formats | P1 | Verify `ValueError` raised when formats list is empty or not a list |
| 14 | Numeric precision | P1 | Write float column with schema precision=2, verify output has 2 decimal places |
| 15 | Integer formatting | P1 | Write integer column, verify no decimal point in output |
| 16 | NaN handling | P1 | Write DataFrame with NaN values, verify padded empty fields (not "nan" string) |
| 17 | Row separator | P1 | Write with custom row separator (`\r\n`), verify correct line endings |
| 18 | Directory creation | P1 | Write to non-existent directory with `create=True`, verify directory created |
| 19 | Context variable in filepath | P1 | `${context.output_dir}/file.txt` should resolve via context manager |
| 20 | Statistics tracking | P1 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Gzip compression | P2 | Write with `compress=True`, verify output is valid gzip file |
| 22 | Large file (100K rows) | P2 | Verify performance and correctness with large DataFrame |
| 23 | Flush buffer | P2 | Write with `flush_on_row=True, flush_on_row_num=100`, verify file is flushed correctly |
| 24 | Unicode characters | P2 | Write non-ASCII characters, verify encoding is correct |
| 25 | Column not in DataFrame | P2 | Format references a column not present in input DataFrame, verify graceful handling |
| 26 | Delete empty file | P2 | Write empty data with `delete_empty_file=True`, verify file is removed |
| 27 | Schema type matching | P2 | Verify BigDecimal/Decimal columns are formatted with correct precision |
| 28 | Die on error = false | P2 | Trigger write error (e.g., permission denied), verify graceful return with input data |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FOP-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FOP-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| ENG-FOP-001 | Engine | **Component NOT REGISTERED in engine**: `FileOutputPositional` is not imported or registered in `engine.py` COMPONENT_REGISTRY. The engine cannot instantiate this component. Jobs containing `tFileOutputPositional` will fail with "Unknown component type". Complete blocker. |
| TEST-FOP-001 | Testing | Zero v1 unit tests for the component. All 469 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOP-001 | Converter | `INCLUDEHEADER` default mismatch: converter defaults to `True`, Talend defaults to `false`. Jobs without explicit header setting will produce unexpected header rows. |
| CONV-FOP-002 | Converter | Formats table key case inconsistency: `SCHEMA_COLUMN` stored uppercase, other keys stored lowercase. Fragile for future refactoring. |
| CONV-FOP-005 | Converter | Converter XML parameter name mismatch for flush: reads `FLUSHONROW`/`FLUSHONROW_NUM` but Talend uses `CUSTOM_FLUSH_BUFFER`/`ROW_NUMBER`. Flush config silently defaults. |
| ENG-FOP-002 | Engine | Compression format mismatch: Talend uses ZIP, engine uses gzip. Incompatible archive formats. |
| ENG-FOP-003 | Engine | `INCLUDEHEADER` engine default is `True` (line 76), differing from Talend's `false`. |
| ENG-FOP-004 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. Error details not available downstream. |
| BUG-FOP-003 | Bug | gzip append mode always uses `'ab'` regardless of append flag. Non-append gzip writes should use `'wb'`. |
| BUG-FOP-004 | Bug | `_validate_config()` is dead code -- never called. 60 lines of unreachable validation. |
| BUG-FOP-005 | Bug | `fillna('')` applied before type formatting. NaN distinction lost early. Logic works by accident for current type handling but is fragile. |
| BUG-FOP-009 | Bug (Cross-Cutting) | Precision `-1` from converter causes `ValueError`. Converter sets `precision=int(column.get('precision', -1))`. Engine reads via `.get('precision', DEFAULT_PRECISION)` but since key exists with `-1`, fallback never triggers. `f'{float(val):.{-1}f}'` raises `ValueError` for any float/double/decimal column without explicit precision. |
| BUG-FOP-010 | Bug | `unicode_escape` row separator decoding is a Python footgun (line 226). Treats input as Latin-1 not UTF-8, corrupts non-ASCII content, crashes on literal backslashes with invalid escape sequences in Python 3.12+. |
| PERF-FOP-001 | Performance | Row-by-row `iterrows()` is the slowest DataFrame iteration method. 10-100x slower than vectorized approaches. |
| STD-FOP-001 | Standards | Component not registered in engine COMPONENT_REGISTRY. Cannot be instantiated. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOP-003 | Converter | `ADVANCED_SEPARATOR` / `THOUSANDS_SEPARATOR` / `DECIMAL_SEPARATOR` not extracted. Locale-aware number formatting unavailable. |
| CONV-FOP-004 | Converter | `USE_BYTE_LENGTH` not extracted. Double-byte character sizing unavailable. |
| CONV-FOP-006 | Converter | Converter `CREATE` may not match Talend's `CREATE_DIRECTORY`. Other converters use `CREATE_DIRECTORY`. |
| CONV-FOP-007 | Converter | Schema types converted to Python format instead of Talend format, violating STANDARDS.md. |
| ENG-FOP-005 | Engine | No advanced separator support. European number formats produce incorrect output. |
| ENG-FOP-006 | Engine | No byte-length sizing. CJK characters produce misaligned columns. |
| ENG-FOP-007 | Engine | KEEP='A' overflow produces no warning. Silent positional format corruption. |
| ENG-FOP-008 | Engine | No output stream support (`USE_OUTPUT_STREAM`). |
| BUG-FOP-006 | Bug | `schema_map` dict rebuilt on every row in `_format_data_row()`. Wasteful for large files. |
| BUG-FOP-008 | Bug | `int(None)` crash when SIZE key missing from format dict. No graceful fallback. |
| NAME-FOP-001 | Naming | `delete_empty_file` naming differs from Talend's `DONT_GENERATE_EMPTY_FILE`. Subtle semantic mismatch. |
| STD-FOP-002 | Standards | `_validate_config()` exists but never called -- dead code. |
| STD-FOP-003 | Standards | Schema types in Python format instead of Talend format. |
| STD-FOP-004 | Standards | Generic `ValueError`/`IOError` used instead of custom `ConfigurationError`/`FileOperationError`. |
| PERF-FOP-002 | Performance | `schema_map` rebuilt per row in `_format_data_row()`. |
| PERF-FOP-003 | Performance | String concatenation in tight loop (`line += val`). Should use `''.join()`. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOP-008 | Converter | `keep` attribute not merged into schema columns by dedicated parser. |
| ENG-FOP-009 | Engine | Default encoding `utf-8` differs from Talend JVM-dependent default. |
| ENG-FOP-010 | Engine | Header always truncated to SIZE regardless of KEEP setting. |
| BUG-FOP-007 | Bug (informational) | KEEP='A' overflow: value exceeds SIZE but `ljust`/`rjust` return unchanged (do NOT add padding to oversized strings). Behavior matches Talend spec. Downgraded from P2. |
| BUG-FOP-011 | Bug (minor) | `input_data or pd.DataFrame()` truthy check on DataFrame raises `ValueError` for empty DataFrames. Should use `is not None` check. |
| NAME-FOP-002 | Naming | `flush_on_row` / `flush_on_row_num` naming differs from Talend's `CUSTOM_FLUSH_BUFFER` / `ROW_NUMBER`. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 2 bugs (cross-cutting), 1 engine, 1 testing |
| P1 | 13 | 3 converter, 3 engine, 5 bugs (incl. 1 cross-cutting), 1 performance, 1 standards |
| P2 | 16 | 4 converter, 4 engine, 2 bugs, 1 naming, 3 standards, 2 performance |
| P3 | 6 | 1 converter, 2 engine, 2 bugs, 1 naming |
| **Total** | **39** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Register component in engine** (ENG-FOP-001, STD-FOP-001): Add `from .components.file import FileOutputPositional` to `engine.py` imports (after line 25) and add `'FileOutputPositional': FileOutputPositional, 'tFileOutputPositional': FileOutputPositional,` to `COMPONENT_REGISTRY`. Without this, the component cannot be used at all. **Impact**: Enables the component. **Risk**: Very low.

2. **Fix `_update_global_map()` bug** (BUG-FOP-001): Change `value` to `stat_value` on `base_component.py` line 304, and move the log statement inside the for loop or use the stats dict directly. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

3. **Fix `GlobalMap.get()` bug** (BUG-FOP-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

4. **Create unit test suite** (TEST-FOP-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic write, alignment, padding, KEEP='C', KEEP='A', empty input, and pass-through. Without these, no v1 engine behavior is verified.

5. **Fix `INCLUDEHEADER` default** (CONV-FOP-001, ENG-FOP-003): Change `DEFAULT_INCLUDE_HEADER = True` to `DEFAULT_INCLUDE_HEADER = False` in `file_output_positional.py` line 76. Also change the converter default on line 178 from `True` to `False`. **Impact**: Matches Talend default behavior. **Risk**: Low -- may break jobs that relied on the incorrect default; those jobs should explicitly set `include_header: true`.

### Short-Term (Hardening)

6. **Fix compression to use ZIP** (ENG-FOP-002): Replace `import gzip` with `import zipfile`. When `compress=True`, create a `zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED)` and write the formatted content as a single entry. This matches Talend's ZIP compression behavior. **Impact**: Fixes compatibility with downstream ZIP consumers. **Risk**: Medium -- changes output format for any existing gzip consumers.

7. **Wire up `_validate_config()`** (BUG-FOP-004): Call `self._validate_config()` at the start of `_process()`. Check the returned error list and raise `ConfigurationError` (not `ValueError`) or return gracefully based on `die_on_error`. **Impact**: Catches invalid configs early with clear error messages. **Risk**: Low.

8. **Fix `input_data or pd.DataFrame()` pattern** (BUG-FOP-011): Replace all occurrences (lines 195, 205, 259) with `input_data if input_data is not None else pd.DataFrame()`. **Impact**: Prevents `ValueError` on empty DataFrames. **Risk**: Very low.

9. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FOP-004): In the error handler (line 248), add `if self.global_map: self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`. **Impact**: Enables downstream error handling. **Risk**: Very low.

10. **Fix gzip append mode** (BUG-FOP-003): Change line 285 to `mode = 'ab' if (compress and append) else ('wb' if compress else ('a' if append else 'w'))`. This ensures non-append gzip writes use `'wb'` instead of always using `'ab'`. **Impact**: Correct file overwrite behavior for compressed files. **Risk**: Low.

11. **Normalize formats table keys** (CONV-FOP-002): In `parse_tfileoutputpositional()` line 2828, change `fmt['SCHEMA_COLUMN'] = current_col` to `fmt['schema_column'] = current_col`. This makes all keys consistently lowercase. Update the engine's `_prepare_column_formats()` to remove the `fmt.get('SCHEMA_COLUMN')` fallback. **Impact**: Consistent key casing. **Risk**: Low -- must update engine in tandem.

12. **Use custom exceptions** (STD-FOP-004): Replace `raise ValueError(...)` with `raise ConfigurationError(...)` and `raise IOError(...)` with `raise FileOperationError(...)`. Add imports from `...exceptions`. **Impact**: Consistent error hierarchy. **Risk**: Very low.

### Long-Term (Optimization)

13. **Replace `iterrows()` with vectorized approach** (PERF-FOP-001): Refactor `_write_positional_file()` to use vectorized string formatting. For each column, apply formatting to the entire Series at once: `df[col].astype(str).str.pad(width, side, fillchar)`. Then join columns with `''.join()` per row or use `df.apply(lambda row: ..., axis=1)`. **Impact**: 10-100x performance improvement for large files. **Risk**: Medium -- requires careful testing of all formatting edge cases.

14. **Cache `schema_map` per write** (BUG-FOP-006, PERF-FOP-002): Build `schema_map` once in `_prepare_column_formats()` and pass it to `_format_data_row()`. **Impact**: Eliminates per-row dict creation. **Risk**: Very low.

15. **Use `''.join()` for string building** (PERF-FOP-003): Replace `line += val` with list append + `''.join()`. Replace `header += val` similarly. **Impact**: Minor performance improvement for many-column files. **Risk**: Very low.

16. **Add overflow warning for KEEP='A'** (ENG-FOP-007): Log a warning (once per column, not per row) when a value exceeds the column SIZE with KEEP='A'. **Impact**: Helps detect format corruption in production. **Risk**: Very low.

17. **Add advanced separator support** (CONV-FOP-003, ENG-FOP-005): Extract `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR` from config. Apply custom separators in numeric formatting (replace `f"{float(val):.{precision}f}"` with locale-aware formatting). **Impact**: Enables European number format output. **Risk**: Low.

18. **Add byte-length support** (CONV-FOP-004, ENG-FOP-006): When `use_byte_length=True`, replace `len(val)` with `len(val.encode(encoding))` for size calculations. **Impact**: Enables CJK character support. **Risk**: Low.

19. **Create integration test** (TEST-FOP-001 extended): Build an end-to-end test: `tFileInputDelimited -> tMap -> tFileOutputPositional -> (read back and verify)`. **Impact**: Verifies full pipeline behavior. **Risk**: Very low.

---

## Appendix A: Converter Parameter Mapping Code

### Generic Mapper (component_parser.py lines 172-187)

```python
# FileOutputPositional mapping
elif component_type == 'tFileOutputPositional':
    return {
        'filepath': config_raw.get('FILENAME', ''),
        'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
        'append': config_raw.get('APPEND', False),
        'include_header': config_raw.get('INCLUDEHEADER', True),  # BUG: Talend default is False
        'compress': config_raw.get('COMPRESS', False),
        'encoding': config_raw.get('ENCODING', 'UTF-8'),
        'create': config_raw.get('CREATE', True),  # BUG: Talend uses CREATE_DIRECTORY. See CONV-FOP-006.
        'flush_on_row': config_raw.get('FLUSHONROW', False),  # BUG: Talend uses CUSTOM_FLUSH_BUFFER. See CONV-FOP-005.
        'flush_on_row_num': config_raw.get('FLUSHONROW_NUM', 1),  # BUG: Talend uses ROW_NUMBER. See CONV-FOP-005.
        'delete_empty_file': config_raw.get('DELETE_EMPTYFILE', False),
        'formats': config_raw.get('FORMATS', []),  # Always [] here; overwritten by dedicated parser
        'die_on_error': config_raw.get('DIE_ON_ERROR', True)
    }
```

### Dedicated Formats Parser (component_parser.py lines 2811-2848)

```python
def parse_tfileoutputpositional(self, node, component: Dict) -> Dict:
    """Parse tFileOutputPositional specific configuration"""
    formats = []
    format_map = {}
    for param in node.findall('.//elementParameter[@name="FORMATS"]'):
        fmt = {}
        current_col = None
        for item in param.findall('./elementValue'):
            ref = item.get('elementRef')
            value = item.get('value', '')
            if ref == 'SCHEMA_COLUMN':
                if fmt and current_col:
                    formats.append(fmt)
                    format_map[current_col] = fmt
                    fmt = {}
                current_col = value.strip('"')
                fmt['SCHEMA_COLUMN'] = current_col  # NOTE: Uppercase key
            elif ref and value:
                fmt[ref.lower()] = value.strip('"')  # NOTE: Lowercase keys
        if fmt and current_col:
            formats.append(fmt)
            format_map[current_col] = fmt
    component['config']['formats'] = formats

    # Merge formatting info into schema columns
    if 'output' in component['schema']:
        for col in component['schema']['output']:
            col_fmt = format_map.get(col['name'])
            if col_fmt:
                if 'size' in col_fmt:
                    col['size'] = col_fmt['size']
                if 'padding_char' in col_fmt:
                    col['padding_char'] = col_fmt['padding_char']
                if 'align' in col_fmt:
                    col['align'] = col_fmt['align']
                # NOTE: 'keep' is NOT merged into schema
    return component
```

**Notes on the dedicated parser**:
- Line 2822: `ref == 'SCHEMA_COLUMN'` is a case-sensitive exact match. If Talend XML uses a different case (unlikely but possible), the column detection would fail.
- Line 2828: `SCHEMA_COLUMN` stored as uppercase key, inconsistent with other keys stored lowercase.
- Line 2829-2830: `elif ref and value:` -- if `value` is empty string (`''`), the key-value pair is skipped. This means a PADDING_CHAR of empty string would not be extracted. However, Talend typically uses `' '` (space), so this is unlikely to be an issue in practice.
- Lines 2836-2848: Schema merging does NOT include `keep`. This means schema-level format info is incomplete.

---

## Appendix B: Engine Class Structure

```
FileOutputPositional (BaseComponent)
    Constants:
        DEFAULT_ROW_SEPARATOR = '\n'
        DEFAULT_ENCODING = 'utf-8'
        DEFAULT_APPEND = False
        DEFAULT_INCLUDE_HEADER = True      # BUG: Talend default is False
        DEFAULT_COMPRESS = False
        DEFAULT_CREATE = True
        DEFAULT_FLUSH_ON_ROW = False
        DEFAULT_FLUSH_ON_ROW_NUM = 1
        DEFAULT_DELETE_EMPTY_FILE = False
        DEFAULT_DIE_ON_ERROR = True
        DEFAULT_PADDING_CHAR = ' '
        DEFAULT_ALIGN = 'L'
        DEFAULT_KEEP = 'A'
        DEFAULT_PRECISION = 8

        VALID_ALIGNMENTS = ['L', 'R']
        VALID_KEEP_OPTIONS = ['A', 'C']
        NUMERIC_TYPES = ['float', 'double', 'decimal', 'id_Float', 'id_Double', 'id_BigDecimal']
        INTEGER_TYPES = ['int', 'long', 'integer', 'id_Integer', 'id_Long']

    Methods:
        _validate_config() -> List[str]                # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]         # Main entry point
        _write_positional_file(data, filepath, ...) -> int   # File writing core
        _prepare_column_formats(formats) -> tuple      # Parse format specs
        _format_header_row(col_names, ...) -> str      # Format header
        _format_data_row(row, col_names, ...) -> str   # Format one data row
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filepath` | Mapped | -- |
| `ROWSEPARATOR` | `row_separator` | Mapped | -- |
| `APPEND` | `append` | Mapped | -- |
| `INCLUDEHEADER` | `include_header` | Mapped | -- (fix default) |
| `COMPRESS` | `compress` | Mapped | -- (fix format: ZIP not gzip) |
| `ENCODING` | `encoding` | Mapped | -- |
| `CREATE_DIRECTORY` | `create` | **Partial** (converter reads `CREATE`) | P2 -- fix key name |
| `CUSTOM_FLUSH_BUFFER` | `flush_on_row` | **Wrong Key** (converter reads `FLUSHONROW`) | P1 -- fix key name |
| `ROW_NUMBER` (flush) | `flush_on_row_num` | **Wrong Key** (converter reads `FLUSHONROW_NUM`) | P1 -- fix key name |
| `DONT_GENERATE_EMPTY_FILE` | `delete_empty_file` | Mapped | -- |
| `FORMATS` (table) | `formats` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** | P2 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** | P2 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** | P2 |
| `USE_BYTE_LENGTH` | `use_byte_length` | **Not Mapped** | P2 |
| `OUTPUT_ROW_MODE` | `output_row_mode` | **Not Mapped** | P3 (engine always row mode) |
| `USE_OUTPUT_STREAM` | `use_output_stream` | **Not Mapped** | P3 |
| `OUTPUT_STREAM` | `output_stream` | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Type Formatting Reference

### Engine Numeric Type Handling (file_output_positional.py)

| Type Category | Types Matched | Format Logic | Example (precision=2) |
|---------------|---------------|-------------|----------------------|
| NUMERIC_TYPES | `float`, `double`, `decimal`, `id_Float`, `id_Double`, `id_BigDecimal` | `f"{float(val):.{precision}f}"` | `123.46` |
| INTEGER_TYPES | `int`, `long`, `integer`, `id_Integer`, `id_Long` | `f"{int(float(val))}"` | `123` |
| Other (string) | All other types | `str(val)` | `hello` |

**Precision source**: `schema_map.get(col, {}).get('precision', DEFAULT_PRECISION)` where `DEFAULT_PRECISION = 8`.

**Known issue**: If `val` is an empty string (from `fillna('')`), the numeric formatter checks `val != ''` and skips formatting, outputting `''`. This produces a fully-padded field, which matches Talend's null behavior but is implemented via a string comparison rather than explicit null checking.

**Known issue**: `int(float(val))` on line 449 truncates decimals silently. A value like `123.7` becomes `123`, not `124`. Talend's Java `(int)` cast also truncates (no rounding), so this matches Talend behavior.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 93-153)

This method validates:
- `filepath` is present and non-empty (required)
- `formats` is a non-empty list of dictionaries (required)
- Each format has `schema_column` or `SCHEMA_COLUMN` (case-insensitive lookup)
- Each format has `size` or `SIZE` that is a positive integer
- Each format's `align` is in `VALID_ALIGNMENTS` ('L', 'R')
- Each format's `keep` is in `VALID_KEEP_OPTIONS` ('A', 'C')
- `flush_on_row_num` is a positive integer

**Strengths**: Thorough validation of format definitions. Handles both uppercase and lowercase keys. Validates size is positive. Clear error messages with format index.

**Critical**: This method is never called. Even if it were, callers would need to check the returned error list and raise/handle appropriately. No existing code path does this.

### `_process()` (Lines 155-259)

The main processing method:
1. Extract config values with defaults and type conversion (lines 173-184)
2. Validate required parameters: filepath and formats (lines 187-205)
3. Handle empty input: return empty DataFrame, optionally delete existing file (lines 208-217)
4. Prepare data: `fillna('')` to convert NaN to empty strings (line 220)
5. Decode escape sequences in row_separator (lines 225-227)
6. Write file via `_write_positional_file()` (lines 230-233)
7. Handle empty file deletion post-write (lines 236-239)
8. Update stats and return pass-through output (lines 242-245)
9. Catch-all exception handler: log error, update stats, re-raise or return based on `die_on_error` (lines 247-259)

**Key observation**: The method uses `die_on_error` in two places: (1) early validation (lines 190, 200) where specific `ValueError` is raised, and (2) outer catch-all (line 255) where any exception is conditionally re-raised. This means even errors from `_write_positional_file()` (like I/O errors) respect the `die_on_error` flag.

### `_write_positional_file()` (Lines 261-342)

File writing core:
1. Determine file mode: `'ab'` for compressed (always), `'a'` for append, `'w'` for overwrite (line 285)
2. Create directory if needed (lines 290-293)
3. Open file handle: `gzip.open()` for compressed, `open()` for regular (lines 296-301)
4. Prepare column formats via `_prepare_column_formats()` (line 304)
5. Write header row if `include_header` (lines 307-313)
6. Write data rows via `iterrows()` loop (lines 317-327)
7. Flush and close (lines 330-332)
8. Return row count
9. Exception handler ensures file handle cleanup (lines 336-342)

**Key observation**: For compressed files, the write calls `file_handle.write(line.encode(encoding))` (lines 311, 320) because gzip opens in binary mode. For regular files, plain `file_handle.write(line)` (lines 313, 322) is used because the file is opened in text mode with encoding specified. This dual-path is correct but adds complexity.

### `_prepare_column_formats()` (Lines 344-382)

Parses format specifications from config:
1. Iterates format dicts
2. Extracts column name (case-insensitive: `schema_column` or `SCHEMA_COLUMN`)
3. Extracts size (case-insensitive), converts to int
4. Extracts padding char (case-insensitive), strips single quotes (e.g., `"' '"` -> `' '`)
5. Extracts alignment (case-insensitive), converts to uppercase
6. Extracts keep (case-insensitive), converts to uppercase
7. Looks up column type from schema
8. Returns three parallel lists: col_formats, col_names, col_types

**Key observation**: The single-quote stripping on line 368 (`pad.startswith("'") and pad.endswith("'") and len(pad) == 3`) only handles the specific case of a single character wrapped in single quotes. Multi-character padding or different quoting styles would not be handled. This is typically sufficient since Talend padding chars are single characters.

### `_format_data_row()` (Lines 416-468)

Formats one data row:
1. Rebuild `schema_map` from scratch (line 432-433) -- per-row overhead
2. For each column:
   a. Get value from row: `row.get(col, '')` (line 438)
   b. Format based on type: numeric (precision), integer (truncate), or string (line 441-453)
   c. Truncate if KEEP='C' and value exceeds SIZE (line 456-458)
   d. Apply alignment and padding: `ljust()` for L, `rjust()` for R (line 461-464)
   e. Concatenate to line (line 466)
3. Append row separator (line 468)

**Key observation on KEEP='A' overflow**: When `keep == 'A'` and `len(val) > fmt['size']`, the code does NOT truncate (the `if fmt['keep'] == 'C'` check on line 457 does not match). Then `ljust`/`rjust` on lines 461-464 is called with `fmt['size']`, but since `len(val)` already exceeds `fmt['size']`, the `ljust`/`rjust` call is a no-op (Python's `ljust`/`rjust` does nothing when the string is already wider than the requested width). So the full value is preserved without additional padding, which is correct for KEEP='A'.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty DataFrame input

| Aspect | Detail |
|--------|--------|
| **Talend** | Depending on `DONT_GENERATE_EMPTY_FILE`: creates empty file (header only if enabled) or no file. |
| **V1** | Line 208: `if input_data is None or (hasattr(input_data, 'empty') and input_data.empty)` -> returns `{'main': pd.DataFrame()}` with stats (0,0,0). If `delete_empty_file=True` and file exists, deletes it. |
| **Verdict** | MOSTLY CORRECT. Does not create header-only file when `INCLUDEHEADER=true` and data is empty. Talend would write just the header. |

### Edge Case 2: NaN values in DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Null values produce fully-padded fields (all padding characters). |
| **V1** | `fillna('')` on line 220 converts NaN to `''`. Empty string gets padded to full SIZE. |
| **Verdict** | CORRECT -- produces same output as Talend. |

### Edge Case 3: Value exactly equal to SIZE

| Aspect | Detail |
|--------|--------|
| **Talend** | Value written as-is, no padding needed. |
| **V1** | `ljust(size, pad)` or `rjust(size, pad)` on a string of exactly `size` length is a no-op. |
| **Verdict** | CORRECT |

### Edge Case 4: Value exceeds SIZE with KEEP='A'

| Aspect | Detail |
|--------|--------|
| **Talend** | Full value preserved, breaking fixed-width layout. Subsequent columns shifted right. |
| **V1** | Line 456-458 only truncates for KEEP='C'. For KEEP='A', full value preserved. `ljust`/`rjust` is no-op since value already exceeds size. |
| **Verdict** | CORRECT -- matches Talend behavior. But no warning logged (see ENG-FOP-007). |

### Edge Case 5: Value exceeds SIZE with KEEP='C'

| Aspect | Detail |
|--------|--------|
| **Talend** | Value truncated to SIZE characters from the beginning. |
| **V1** | Line 458: `val = val[:fmt['size']]` truncates from the beginning. Then padding applied if truncated value is shorter than SIZE (possible if multi-byte encoding, but not with `len()` check). |
| **Verdict** | CORRECT for single-byte encodings. May differ for multi-byte if `USE_BYTE_LENGTH` is needed. |

### Edge Case 6: Empty string value (not NaN)

| Aspect | Detail |
|--------|--------|
| **Talend** | Produces fully-padded field. |
| **V1** | Empty string `''` is padded by `ljust(size, pad)` to full SIZE. |
| **Verdict** | CORRECT |

### Edge Case 7: Numeric precision with schema vs default

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses schema-defined precision, falls back to Java defaults. |
| **V1** | Line 443: `precision = schema_map.get(col, {}).get('precision', self.DEFAULT_PRECISION)`. DEFAULT_PRECISION is 8. |
| **Verdict** | MOSTLY CORRECT. Default precision of 8 may differ from Java's default formatting. |

### Edge Case 8: Float NaN (not from fillna)

| Aspect | Detail |
|--------|--------|
| **Talend** | Null float produces padded field. |
| **V1** | After `fillna('')`, float NaN becomes `''`. Numeric formatter check `val != ''` is False, so `val` stays `''`. Padded to full SIZE. |
| **Verdict** | CORRECT |

### Edge Case 9: Integer value with decimal (e.g., 123.7 in integer column)

| Aspect | Detail |
|--------|--------|
| **Talend** | Java `(int)` cast truncates: 123.7 -> 123. |
| **V1** | Line 449: `int(float(val))` truncates: 123.7 -> 123. |
| **Verdict** | CORRECT -- matches Talend truncation behavior. |

### Edge Case 10: gzip compression + append

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses ZIP format (not gzip). ZIP append semantics differ from gzip. |
| **V1** | Line 285: `mode = 'ab' if compress` always uses binary append. Appending to a gzip file creates a concatenated gzip stream, which is technically valid but may confuse some readers. |
| **Verdict** | WRONG FORMAT (gzip vs ZIP) and WRONG MODE (always append for compressed). See BUG-FOP-003. |

### Edge Case 11: `input_data or pd.DataFrame()` on empty DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A |
| **V1** | Lines 195, 205, 259 use `input_data or pd.DataFrame()`. If `input_data` is an empty DataFrame, `bool(pd.DataFrame())` raises `ValueError: The truth value of a DataFrame is ambiguous`. |
| **Verdict** | BUG -- crashes on empty DataFrame input. See BUG-FOP-011. |

### Edge Case 12: Padding char as empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | Would use default space. |
| **V1** | Line 370: `pad = pad or self.DEFAULT_PADDING_CHAR` falls back to space if `pad` is empty/falsy. Then `ljust(size, '')` would raise `TypeError: The fill character must be exactly one character long`. |
| **Verdict** | The fallback on line 370 prevents this, but if the converter passes an explicitly empty string and the fallback `or` evaluates it as falsy, the DEFAULT_PADDING_CHAR (space) is used. CORRECT behavior. |

### Edge Case 13: Column in formats but not in DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Would use null value for missing column. |
| **V1** | Line 438: `val = row.get(col, '')` returns `''` if column not in row. This is equivalent to null -> padded field. |
| **Verdict** | CORRECT -- graceful handling of missing columns. |

### Edge Case 14: Unicode characters in values (CJK, emoji)

| Aspect | Detail |
|--------|--------|
| **Talend** | With `USE_BYTE_LENGTH=true`, uses byte length for sizing. Without it, uses character count. |
| **V1** | Uses `len(val)` which counts characters, not bytes. A CJK character counts as 1 character but 3 bytes in UTF-8. |
| **Verdict** | MATCHES Talend default (`USE_BYTE_LENGTH=false`). But if byte-length mode is needed, it's not supported (see ENG-FOP-006). |

### Edge Case 15: Row separator with escape sequences

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports `\n`, `\r\n`, `\r`, and custom characters. |
| **V1** | Line 226: `row_separator.encode('utf-8').decode('unicode_escape')`. This converts `\\n` -> `\n`, `\\r\\n` -> `\r\n`. |
| **Verdict** | CORRECT -- handles common escape sequences. May produce unexpected results for non-ASCII escape sequences. |

---

## Appendix G: File Handle Management Analysis

The file handle lifecycle in `_write_positional_file()`:

```
try:
    file_handle = gzip.open(...) or open(...)    # Open
    # ... write operations ...
    file_handle.flush()                           # Explicit flush
    file_handle.close()                           # Explicit close
    file_handle = None                            # Clear reference
    return row_count
except Exception:
    if file_handle:                               # Cleanup on error
        try:
            file_handle.close()
        except Exception:
            pass                                  # Swallow close errors
    raise
```

**Assessment**: The try/except pattern correctly closes the file handle on both success and error paths. Setting `file_handle = None` after close prevents the except block from trying to close again. The bare `except Exception: pass` in the cleanup is acceptable -- a failed close during error handling should not mask the original error.

**Gap**: Does NOT use Python's `with` statement (context manager), which would be more Pythonic and guarantee cleanup. The current pattern is functionally equivalent but harder to maintain.

**Gap**: For gzip mode, `gzip.open(filepath, 'ab')` does not accept an `encoding` parameter directly. The encoding is applied manually via `.encode(encoding)` on lines 311 and 320. This is correct but means encoding errors would surface as `UnicodeEncodeError` during write, not during open.

---

## Appendix H: Converter vs Engine Parameter Default Comparison

| Parameter | Converter Default (line) | Engine Default (line) | Talend Default | Match? |
|-----------|--------------------------|----------------------|----------------|--------|
| `row_separator` | `'\n'` (176) | `'\n'` (73) | `"\n"` | Yes |
| `append` | `False` (177) | `False` (75) | `false` | Yes |
| `include_header` | `True` (178) | `True` (76) | **`false`** | **NO -- both wrong** |
| `compress` | `False` (179) | `False` (77) | `false` | Yes (but format mismatch) |
| `encoding` | `'UTF-8'` (180) | `'utf-8'` (74) | JVM-dependent | **Uncertain** |
| `create` | `True` (181) | `True` (78) | `true` | Yes |
| `flush_on_row` | `False` (182) | `False` (79) | `false` | Yes |
| `flush_on_row_num` | `1` (183) | `1` (80) | -- | Yes |
| `delete_empty_file` | `False` (184) | `False` (81) | `false` | Yes |
| `die_on_error` | `True` (186) | `True` (82) | `true` (implied) | Yes |
| `padding_char` | N/A (in formats) | `' '` (83) | `' '` (space) | Yes |
| `align` | N/A (in formats) | `'L'` (84) | Dependent on column | **Uncertain** |
| `keep` | N/A (in formats) | `'A'` (85) | `A` | Yes |
| `precision` | N/A (in schema) | `8` (86) | Java default | **Uncertain** |

---

## Appendix I: Execution Flow Trace

### Complete Execution Path for FileOutputPositional

The following traces the exact execution path when the v1 engine processes a `FileOutputPositional` component, from engine dispatch to file write completion.

#### Step 1: Engine Dispatch (engine.py)

```
Engine._execute_component(component_config)
  -> component_type = config['type']  # 'FileOutputPositional'
  -> comp_class = COMPONENT_REGISTRY.get('FileOutputPositional')
  -> comp_class is None  # BUG: NOT REGISTERED
  -> ERROR: "Unknown component type: FileOutputPositional"
```

**BLOCKER**: Execution stops here. The component cannot be instantiated because it is not in the registry. All subsequent steps describe what WOULD happen if the registration bug (ENG-FOP-001) were fixed.

#### Step 2: Component Instantiation (base_component.py)

```
FileOutputPositional.__init__(component_id, config, global_map, context_manager)
  -> BaseComponent.__init__()
    -> self.id = component_id
    -> self.config = config
    -> self.global_map = global_map
    -> self.context_manager = context_manager
    -> self.execution_mode = _determine_execution_mode()  # Default: HYBRID
    -> self.stats = {'NB_LINE': 0, 'NB_LINE_OK': 0, 'NB_LINE_REJECT': 0, ...}
    -> self.status = ComponentStatus.PENDING
```

Note: `_validate_config()` is NOT called during initialization. Invalid configurations are not detected until `_process()`.

#### Step 3: Component Execution (base_component.py)

```
FileOutputPositional.execute(input_data)
  -> self.status = ComponentStatus.RUNNING
  -> start_time = time.time()
  -> Step 3a: Resolve Java expressions
    -> if self.java_bridge: self._resolve_java_expressions()
       -> Scans config for {{java}} markers
       -> Sends to Java bridge for evaluation
       -> Replaces markers with evaluated values
  -> Step 3b: Resolve context variables
    -> if self.context_manager: self.config = self.context_manager.resolve_dict(self.config)
       -> Replaces ${context.var} patterns with actual values
       -> filepath "${context.output_dir}/output.txt" becomes "/data/output/output.txt"
  -> Step 3c: Determine execution mode
    -> if HYBRID: _auto_select_mode(input_data)
       -> Estimates memory usage of input DataFrame
       -> If > 3072 MB: STREAMING, else BATCH
  -> Step 3d: Execute
    -> _execute_batch(input_data)
       -> return self._process(input_data)
  -> Step 3e: Post-execution
    -> self.stats['EXECUTION_TIME'] = elapsed
    -> self._update_global_map()  # BUG: NameError on 'value' variable
    -> self.status = ComponentStatus.SUCCESS
    -> result['stats'] = self.stats.copy()
    -> return result
```

#### Step 4: Process Method (file_output_positional.py)

```
FileOutputPositional._process(input_data)
  -> Extract config with defaults:
     filepath = config.get('filepath', '')
     row_separator = config.get('row_separator', '\n')
     append = config.get('append', False)
     include_header = config.get('include_header', True)  # BUG: Wrong default
     compress = config.get('compress', False)
     encoding = config.get('encoding', 'utf-8')
     create = config.get('create', True)
     flush_on_row = config.get('flush_on_row', False)
     flush_on_row_num = int(config.get('flush_on_row_num', 1))
     delete_empty_file = config.get('delete_empty_file', False)
     formats = config.get('formats', [])
     die_on_error = config.get('die_on_error', True)

  -> Validate filepath:
     if not filepath: raise ValueError or return {'main': input_data or pd.DataFrame()}

  -> Validate formats:
     if not formats or not isinstance(formats, list): raise ValueError or return

  -> Handle empty input:
     if input_data is None or input_data.empty:
       -> optionally delete existing file
       -> return {'main': pd.DataFrame()} with stats (0,0,0)

  -> Prepare data:
     data = input_data.fillna('')  # Replace NaN with empty string
     rows_in = len(data)

  -> Decode row separator escape sequences:
     row_separator = row_separator.encode('utf-8').decode('unicode_escape')

  -> Write file:
     rows_written = _write_positional_file(data, filepath, formats, ...)

  -> Post-write cleanup:
     if delete_empty_file and file is empty: delete file

  -> Update stats: _update_stats(rows_in, rows_written, 0)
  -> return {'main': input_data}  # Pass-through original data
```

#### Step 5: File Writing (file_output_positional.py)

```
FileOutputPositional._write_positional_file(data, filepath, formats, ...)
  -> Determine file mode:
     compress -> 'ab'  # BUG: Always append for compressed
     append -> 'a'
     else -> 'w'

  -> Create directory if needed:
     os.makedirs(dirname, exist_ok=True)

  -> Open file handle:
     compress -> gzip.open(filepath, mode)
     else -> open(filepath, mode, encoding=encoding)

  -> Prepare column formats:
     col_formats, col_names, col_types = _prepare_column_formats(formats)

  -> Write header (if include_header):
     header = _format_header_row(col_names, col_formats, row_separator)
     compress -> file_handle.write(header.encode(encoding))
     else -> file_handle.write(header)

  -> Write data rows:
     for idx, row in data.iterrows():  # SLOW: iterrows()
       line = _format_data_row(row, col_names, col_formats, col_types, row_separator)
       compress -> file_handle.write(line.encode(encoding))
       else -> file_handle.write(line)
       row_count += 1
       if flush_on_row and (row_count % flush_on_row_num == 0):
         file_handle.flush()

  -> Final flush and close:
     file_handle.flush()
     file_handle.close()
     file_handle = None

  -> return row_count
```

#### Step 6: Row Formatting (file_output_positional.py)

```
FileOutputPositional._format_data_row(row, col_names, col_formats, col_types, row_separator)
  -> schema_map = {col['name']: col for col in schema}  # PERF BUG: Rebuilt per row
  -> line = ''
  -> for each column:
     val = row.get(col, '')  # Get value or empty string

     -> Type-based formatting:
        NUMERIC_TYPES -> f"{float(val):.{precision}f}" if val != '' else ''
        INTEGER_TYPES -> f"{int(float(val))}" if val != '' else ''
        else -> str(val)

     -> Truncation:
        if len(val) > size and keep == 'C':
          val = val[:size]
        # If keep == 'A': no truncation (value may exceed size)

     -> Alignment and padding:
        align == 'L' -> val.ljust(size, pad)
        align == 'R' -> val.rjust(size, pad)

     -> line += val  # PERF: String concatenation

  -> line += row_separator
  -> return line
```

---

## Appendix J: Cross-Cutting Issues Impact Matrix

These issues exist in shared base classes and affect FileOutputPositional along with all other components.

### BUG-FOP-001: `_update_global_map()` NameError (base_component.py:304)

| Aspect | Detail |
|--------|--------|
| **Location** | `base_component.py` line 304 |
| **Root cause** | Log statement uses `{value}` but loop variable is `stat_value` |
| **Trigger** | Called after every `execute()` when `self.global_map` is not None |
| **Impact** | `NameError: name 'value' is not defined` crashes the component |
| **Components affected** | ALL components in the v1 engine |
| **Workaround** | Do not pass `global_map` to component constructor |
| **Fix** | Change `value` to `stat_value` on line 304; also fix `stat_name` which is used outside loop scope |
| **Risk** | Very low -- log message change only |
| **Estimated effort** | 5 minutes |

### BUG-FOP-002: `GlobalMap.get()` NameError (global_map.py:28)

| Aspect | Detail |
|--------|--------|
| **Location** | `global_map.py` line 28 |
| **Root cause** | Method body uses `default` parameter not in signature |
| **Trigger** | Any call to `global_map.get(key)` |
| **Impact** | `NameError: name 'default' is not defined` |
| **Secondary impact** | `get_component_stat()` line 58 calls `self.get(key, default)` with 2 args but signature only accepts 1 |
| **Components affected** | ALL code using `GlobalMap.get()` |
| **Workaround** | Use `global_map._map.get(key)` directly (breaks encapsulation) |
| **Fix** | Add `default: Any = None` to `get()` signature |
| **Risk** | Very low |
| **Estimated effort** | 5 minutes |

### Combined Impact on FileOutputPositional

When `global_map` is provided (typical production scenario):

1. Component executes `_process()` successfully
2. `execute()` calls `_update_global_map()`
3. `_update_global_map()` iterates stats and calls `global_map.put_component_stat()` -- this WORKS because `put_component_stat()` calls `self.put()` which uses `self._map[key] = value` (dict assignment, not `.get()`)
4. Then the log statement on line 304 crashes with `NameError: name 'value' is not defined`
5. The exception propagates up through `execute()` to the outer `except` block (line 227)
6. `execute()` sets `self.status = ComponentStatus.ERROR` and calls `_update_global_map()` AGAIN (line 231)
7. This SECOND call ALSO crashes with the same NameError
8. The exception propagates out of `execute()` entirely
9. **Net result**: The file IS written successfully, but the component reports as FAILED due to the logging bug

This means FileOutputPositional would appear to fail even when the file write succeeds, causing downstream SUBJOB_ERROR triggers instead of SUBJOB_OK.

---

## Appendix K: Comparison with tFileOutputDelimited

Since `tFileOutputDelimited` is a closely related output component, comparing implementation approaches reveals consistency issues and shared patterns.

| Aspect | FileOutputDelimited | FileOutputPositional | Notes |
|--------|---------------------|---------------------|-------|
| Registered in engine? | **Yes** (lines 60-61) | **No** | Critical gap for positional |
| Compression format | N/A (no compress option shown) | gzip (should be ZIP) | Format mismatch |
| `_validate_config()` called? | Unknown | No (dead code) | Common pattern of dead validation |
| `iterrows()` usage | Likely uses pandas `to_csv()` | Yes (manual row iteration) | Positional cannot use pandas built-in |
| Pass-through output | Yes | Yes | Both return input_data unchanged |
| Error exception type | `FileOperationError` (expected) | `ValueError`, `IOError` | Inconsistent exception usage |
| Default include_header | Expected: False | True (BUG) | Positional has wrong default |
| GlobalMap ERROR_MESSAGE | Expected: Not set | Not set | Same gap in both |

---

## Appendix L: Security Analysis

| ID | Priority | Issue | Risk Level |
|----|----------|-------|------------|
| SEC-FOP-001 | **P3** | **No path traversal protection**: `filepath` from config is used directly with `os.path.exists()`, `os.makedirs()`, and `open()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) could overwrite arbitrary files. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FOP-002 | **P3** | **No file permission validation**: The component does not check write permissions before attempting to create/overwrite a file. Permission errors are caught by the generic exception handler but produce unclear error messages. |
| SEC-FOP-003 | **P3** | **Directory creation with `exist_ok=True`**: `os.makedirs(directory, exist_ok=True)` on line 293 creates directories recursively. If the filepath is malformed (e.g., very deep nesting), this could create many directories. Not a practical concern for Talend jobs. |

---

## Appendix M: Formats Table Parsing Deep Dive

### Talend XML Structure for FORMATS

The Talend XML for the FORMATS table typically looks like:

```xml
<elementParameter field="TABLE" name="FORMATS" ...>
  <elementValue elementRef="SCHEMA_COLUMN" value="id"/>
  <elementValue elementRef="SIZE" value="10"/>
  <elementValue elementRef="PADDING_CHAR" value="'0'"/>
  <elementValue elementRef="ALIGN" value="R"/>
  <elementValue elementRef="KEEP" value="C"/>
  <elementValue elementRef="SCHEMA_COLUMN" value="name"/>
  <elementValue elementRef="SIZE" value="30"/>
  <elementValue elementRef="PADDING_CHAR" value="' '"/>
  <elementValue elementRef="ALIGN" value="L"/>
  <elementValue elementRef="KEEP" value="A"/>
</elementParameter>
```

### Parser Behavior Analysis

The dedicated parser (`parse_tfileoutputpositional`) processes this as a flat list of `elementValue` nodes. It uses `SCHEMA_COLUMN` as a delimiter -- when a new `SCHEMA_COLUMN` is encountered, the previous format entry is finalized and a new one started.

**Potential issues with this approach**:

1. **Single elementParameter assumption**: The parser iterates `node.findall('.//elementParameter[@name="FORMATS"]')`. If there are multiple `elementParameter` nodes named `FORMATS` (unusual but possible in some Talend XML structures), all would be processed. The current code handles this correctly since it appends to the same `formats` list.

2. **Order dependency**: The parser assumes `SCHEMA_COLUMN` appears BEFORE `SIZE`, `PADDING_CHAR`, `ALIGN`, `KEEP` for each column. If the XML has a different order (e.g., `SIZE` before `SCHEMA_COLUMN`), the first column's `SIZE` would be lost because `current_col` is None and the `elif ref and value:` condition is True but `fmt` would be assigned to a dict that gets discarded.

3. **Empty value handling**: The `elif ref and value:` condition (line 2829) skips entries where `value` is an empty string. This means:
   - `PADDING_CHAR` with empty value: skipped, no entry in format dict. Engine falls back to `DEFAULT_PADDING_CHAR`.
   - `ALIGN` with empty value: skipped, engine falls back to `DEFAULT_ALIGN`.
   - `KEEP` with empty value: skipped, engine falls back to `DEFAULT_KEEP`.
   This is acceptable since Talend always provides values for these fields.

4. **Case sensitivity of `elementRef`**: The check `if ref == 'SCHEMA_COLUMN'` is case-sensitive. If Talend XML uses `schema_column` (lowercase), it would NOT be recognized as a column delimiter, and would instead be stored as a lowercase key via `fmt[ref.lower()]`. This would cause the parser to treat all format entries as a single column. However, Talend consistently uses uppercase `elementRef` names, so this is unlikely in practice.

5. **Last column handling**: The `if fmt and current_col:` block after the loop (lines 2831-2833) correctly handles the last format entry, which has no subsequent `SCHEMA_COLUMN` to trigger its finalization.

### Resulting Format Dict Structure

After parsing, each format dict looks like:

```python
{
    'SCHEMA_COLUMN': 'id',   # UPPERCASE key (inconsistent)
    'size': '10',             # lowercase key, STRING value (not int)
    'padding_char': "'0'",    # lowercase key, may include single quotes
    'align': 'R',             # lowercase key
    'keep': 'C'               # lowercase key
}
```

**Note**: `size` is a **string**, not an integer. The engine's `_prepare_column_formats()` converts it via `int(fmt.get('size') or fmt.get('SIZE'))` on line 364. If the converter stores it as a string and the engine expects to convert it, this is correct. But if `size` is `'10'`, then `fmt.get('size')` returns `'10'` (truthy), and `int('10')` works. However, if `size` is `'0'` (zero), `fmt.get('size')` returns `'0'` (truthy), and `int('0')` works. If `size` is `''` (empty), `fmt.get('size')` returns `''` (falsy), falls through to `fmt.get('SIZE')` which is `None` (not present with this key), and `int(None)` crashes.

**Note**: `padding_char` may include surrounding single quotes (e.g., `"'0'"`). The engine's `_prepare_column_formats()` strips these on line 368: `if isinstance(pad, str) and pad.startswith("'") and pad.endswith("'") and len(pad) == 3: pad = pad[1:-1]`. This specifically handles single-character padding chars wrapped in quotes but would NOT handle multi-character padding or different quoting.

---

## Appendix N: Streaming Mode Considerations

### Current State

`FileOutputPositional` inherits streaming support from `BaseComponent`, but the implementation does not explicitly handle streaming mode differently. The base class `_execute_streaming()` method would:

1. Convert input DataFrame to chunks if it is a full DataFrame
2. Call `_process()` for each chunk

However, `_process()` opens the file, writes all rows, and closes the file. If called multiple times with different chunks:
- **First chunk**: Opens file in write mode (`'w'`), writes rows, closes file
- **Second chunk**: Opens file in write mode (`'w'`), OVERWRITES first chunk's data, writes rows, closes file
- **Net result**: Only the last chunk's data is in the file

### Required Fix for Streaming

For streaming mode to work correctly, the component would need to:
1. Open the file ONCE before the first chunk
2. Write each chunk's rows sequentially
3. Close the file after the last chunk

This could be implemented by:
- Setting `append=True` after the first chunk
- Or restructuring to use a persistent file handle across chunks
- Or implementing a custom `_execute_streaming()` override

### Impact Assessment

Currently, this is not a practical concern because:
1. The component is not registered in the engine (ENG-FOP-001)
2. Output components rarely receive streaming input (they typically receive batch data)
3. The `HYBRID` mode auto-selection is based on input DataFrame size, which for output components is typically the full result from upstream

However, for very large data pipelines (100M+ rows), streaming output support would be needed to avoid memory issues from holding the entire DataFrame in memory.

---

## Appendix O: Component Status Lifecycle

### Expected Status Transitions

```
PENDING -> RUNNING -> SUCCESS  (normal execution)
PENDING -> RUNNING -> ERROR    (execution failure)
PENDING -> SKIPPED             (component skipped by trigger logic)
```

### Actual Status for FileOutputPositional

Due to BUG-FOP-001 (`_update_global_map()` NameError):

```
PENDING -> RUNNING -> ERROR    (even when file write succeeds!)
```

The status is set to ERROR because `_update_global_map()` crashes after `_process()` returns successfully. This means:
- `COMPONENT_OK` trigger will NOT fire
- `COMPONENT_ERROR` trigger WILL fire
- Downstream components connected via `SUBJOB_OK` will NOT execute
- Error handling flows connected via `SUBJOB_ERROR` WILL execute

**Net effect**: The file is written correctly, but the job flow behaves as if the component failed. This could cause:
1. Job reported as failed when it actually succeeded
2. Error notification emails sent unnecessarily
3. Retry logic triggered when no retry is needed
4. Subsequent subjobs not executed

### Workaround

Do not pass `global_map` to the component constructor. This causes `_update_global_map()` to skip (the `if self.global_map:` check on line 300 returns False). Stats tracking via globalMap is lost, but the component reports correct status.

---

## Appendix P: Regression Risk Assessment

### Changes Required for Production Readiness (Ordered by Risk)

| # | Change | Risk | Files Modified | Regression Concern |
|---|--------|------|---------------|-------------------|
| 1 | Register in engine | Very Low | `engine.py` | New import + 2 registry entries. No existing behavior changed. |
| 2 | Fix `_update_global_map()` | Very Low | `base_component.py` | Log message change. Affects ALL components but only logging. |
| 3 | Fix `GlobalMap.get()` | Very Low | `global_map.py` | Add optional parameter. Backward compatible. |
| 4 | Fix `INCLUDEHEADER` default | Low | `file_output_positional.py`, `component_parser.py` | Breaks jobs relying on wrong default. Those jobs need explicit `include_header: true`. |
| 5 | Fix `input_data or pd.DataFrame()` | Low | `file_output_positional.py` | Three lines changed. Only affects empty DataFrame edge case. |
| 6 | Wire `_validate_config()` | Low | `file_output_positional.py` | May reject configs that previously worked (if they had invalid values that happened to work at runtime). |
| 7 | Fix gzip mode | Low | `file_output_positional.py` | Changes compressed file behavior. No existing gzip consumers should be affected since component was never usable. |
| 8 | Fix compression to ZIP | Medium | `file_output_positional.py` | Changes compression format. Requires `import zipfile` instead of `import gzip`. |
| 9 | Normalize format keys | Medium | `component_parser.py`, `file_output_positional.py` | Must update converter and engine in tandem. Existing converted JSON configs would need re-conversion or migration. |
| 10 | Replace `iterrows()` | Medium | `file_output_positional.py` | Performance refactor. All formatting edge cases must be re-tested. |
| 11 | Use custom exceptions | Low | `file_output_positional.py` | Changes exception types. Callers catching `ValueError` specifically would miss. |

---

## Appendix Q: Interoperability Notes

### Consuming Positional Files Written by V1

When another system reads a positional file written by the v1 `FileOutputPositional`, the following differences from Talend-written files may cause issues:

1. **Header presence**: If v1 writes a header (due to wrong default) but the consumer expects no header, the first data row will be misinterpreted.

2. **Encoding**: If v1 writes UTF-8 but the consumer expects ISO-8859-15, non-ASCII characters will be garbled.

3. **Compression format**: If v1 writes gzip but the consumer expects ZIP, decompression will fail entirely.

4. **KEEP='A' overflow**: If v1 preserves full values that exceed SIZE (default behavior), subsequent column positions are shifted, corrupting the entire row for the consumer.

5. **Numeric precision**: If v1 uses DEFAULT_PRECISION=8 but the consumer expects Java's default formatting, decimal values may have different digit counts.

6. **Row separator**: If v1 uses `\n` but the consumer expects `\r\n` (Windows), line parsing may fail.

### Writing Positional Files for Mainframe Consumption

Mainframe systems (COBOL, AS/400) are the primary consumers of positional files and have strict requirements:

- **Exact column widths**: KEEP must be 'C' (truncate) to maintain fixed-width layout
- **EBCDIC encoding**: Not supported by v1 (see `tFileOutputEBCDIC` for EBCDIC support)
- **No header row**: Headers corrupt mainframe record parsing
- **Specific padding**: Numeric fields typically require '0' padding with right alignment
- **Fixed record length**: Every row must be exactly the same total width

The v1 engine can produce mainframe-compatible output IF:
- `include_header` is set to `False` (not the current default!)
- All KEEP values are set to 'C'
- Appropriate padding chars and alignments are configured
- Encoding is set to the expected character set

---

## Appendix R: Test Data Generator

### Minimal Reproduction Config for Manual Testing

The following configuration can be used to manually test the component once the registration bug (ENG-FOP-001) is fixed.

#### Test Config JSON

```json
{
    "id": "tFileOutputPositional_1",
    "type": "FileOutputPositional",
    "config": {
        "filepath": "/tmp/test_positional_output.txt",
        "row_separator": "\\n",
        "append": false,
        "include_header": false,
        "compress": false,
        "encoding": "utf-8",
        "create": true,
        "flush_on_row": false,
        "flush_on_row_num": 1,
        "delete_empty_file": false,
        "die_on_error": true,
        "formats": [
            {"schema_column": "id", "size": "5", "padding_char": "0", "align": "R", "keep": "C"},
            {"schema_column": "name", "size": "20", "padding_char": " ", "align": "L", "keep": "C"},
            {"schema_column": "amount", "size": "12", "padding_char": " ", "align": "R", "keep": "C"}
        ]
    },
    "schema": {
        "output": [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str"},
            {"name": "amount", "type": "float", "precision": 2}
        ]
    }
}
```

#### Expected Output File Content

For input DataFrame:
```
   id      name   amount
0   1     Alice   100.50
1   2       Bob  2500.75
2   3   Charlie     0.00
```

Expected `/tmp/test_positional_output.txt`:
```
00001Alice                      100.50
00002Bob                       2500.75
00003Charlie                      0.00
```

Column layout:
- `id`: 5 chars, right-aligned, zero-padded
- `name`: 20 chars, left-aligned, space-padded
- `amount`: 12 chars, right-aligned, space-padded, 2 decimal precision

#### Edge Case Test Data

```python
import pandas as pd
import numpy as np

# Test DataFrame with edge cases
test_data = pd.DataFrame({
    'id': [1, 2, 3, 4, 5, 6, 7],
    'name': ['Alice', 'Bob', '', np.nan, 'ThisNameIsTooLongForTheField', 'X', '  spaces  '],
    'amount': [100.50, 2500.75, 0.0, np.nan, -42.123, 999999999.99, 0.001]
})
```

Expected behaviors per row:
1. Normal case -- standard formatting
2. Normal case -- standard formatting
3. Empty string in name -- fully padded name field
4. NaN in name -- `fillna('')` converts to empty string, fully padded
5. Name exceeds 20 chars with KEEP='C' -- truncated to "ThisNameIsTooLongFor"
6. Single char name -- "X" left-padded with spaces to 20 chars
7. Spaces in name -- preserved as-is (no trimming in output component)

---

## Appendix S: References

- [tFileOutputPositional Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/positional/tfileoutputpositional-standard-properties)
- [tFileOutputPositional Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/positional/tfileoutputpositional-standard-properties)
- [tFileOutputPositional Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/positional/tfileoutputpositional)
- [tFileOutputPositional (Talend Skill ESB 7.x)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfileoutputpositional-talend-open-studio-for-esb-document-7-x/)
- [Talend Components Reference Guide (3.X)](https://docs.huihoo.com/talend/TalendOpenStudio_Components_RG_32a_EN.pdf)
- [Talend Community - tFileOutputPositional Discussion](https://community.talend.com/t5/Design-and-Development/problem-with-tFileOutputPositional/m-p/61481)
