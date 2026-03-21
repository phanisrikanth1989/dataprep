# Audit Report: tFileOutputDelimited / FileOutputDelimited

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileOutputDelimited` |
| **V1 Engine Class** | `FileOutputDelimited` |
| **Engine File** | `src/v1/engine/components/file/file_output_delimited.py` (472 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 129-147) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Dedicated Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileoutputdelimited()` (lines 2252-2264) -- exists but is NOT wired into `converter.py` |
| **Registry Aliases** | `FileOutputDelimited`, `tFileOutputDelimited` (registered in `src/v1/engine/engine.py` lines 60-61) |
| **Category** | File / Output |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_output_delimited.py` | Engine implementation (472 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 129-147) | Parameter mapping from Talend XML to v1 JSON via `_map_component_parameters()` |
| `src/converters/complex_converter/component_parser.py` (lines 2252-2264) | Dedicated parser `parse_tfileoutputdelimited()` -- **NOT wired into converter.py** |
| `src/converters/complex_converter/converter.py` (lines 216-382) | Dispatch -- no dedicated `elif` for `tFileOutputDelimited`; uses generic `parse_base_component()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 5 | 1 | 11 of 27 Talend params extracted (41%); missing COMPRESS, SPLIT, SPLIT_EVERY, FLUSHONROW, ROW_MODE, FILE_EXIST_EXCEPTION, ESCAPE_CHAR, ADVANCED_SEPARATOR, etc.; dedicated parser exists but not wired; `_map_component_parameters()` usage is non-compliant with STANDARDS.md |
| Engine Feature Parity | **Y** | 0 | 7 | 4 | 1 | No compress/zip; no split files; no flush buffer; no row mode; no file-exist exception; no escape_char handling; missing globalMap vars; streaming mode skips output schema |
| Code Quality | **Y** | 2 | 5 | 2 | 3 | Cross-cutting base class bugs; dead `_validate_config()`; list-to-DF error handling scoping bug; die_on_error default mismatch; empty data path skips directory creation; streaming stats accumulation (informational) |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | Streaming mode works; row_separator not applied in pandas to_csv; minor optimization opportunities |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileOutputDelimited Does

`tFileOutputDelimited` writes rows from a data flow to a character-delimited flat file (CSV, TSV, pipe-separated, semicolon-separated, etc.). It is the single most commonly used output component in Talend, present in the vast majority of data integration jobs. The component receives rows from an upstream connector via a Row (Main) link, formats each row with configured delimiters and enclosures, and writes them to the target file. It supports append mode, header inclusion, output compression as ZIP, splitting large files into multiple smaller files, configurable encoding, and various CSV-specific options including text enclosure and escape characters.

**Source**: [tFileOutputDelimited Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileoutputdelimited-standard-properties), [Component-specific settings (Job Script Reference Guide 8.0)](https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/component-specific-settings-for-tfileoutputdelimited), [tFileOutputDelimited Docs (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-5-x/tfileoutputdelimited-docs-for-esb-5-x/)

**Component family**: Delimited (File / Output)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.
**Required JARs**: `talend_file_enhanced-1.1.jar`, `talendcsv-1.0.0.jar`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. Can be synchronized from upstream component. |
| 3 | Use Output Stream | `USESTREAM` | Boolean (CHECK) | `false` | When enabled, the component writes to a Java OutputStream instead of a file. The stream is specified in `STREAMNAME`. Disables the `FILENAME` field. |
| 4 | Output Stream | `STREAMNAME` | Expression (String) | -- | Java variable referencing the OutputStream. Only visible when `USESTREAM=true`. Supports auto-completion via Ctrl+Space. |
| 5 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory** (when `USESTREAM=false`). Absolute file path for the output file. Supports context variables, globalMap references, Java expressions. Disabled when `USESTREAM=true`. |
| 6 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | Character(s) identifying the end of a row. Supports `\r\n`, `\n`, `\r`. Can be multi-character. **Note**: Talend writes a trailing row separator after the last row by default. |
| 7 | Field Separator | `FIELDSEPARATOR` | String | `";"` | Delimiter separating fields. Can be a character, string, or regular expression. When `CSV_OPTION=true`, must be single character. **Note**: Talend default is semicolon, not comma. |
| 8 | Append | `APPEND` | Boolean (CHECK) | `false` | When selected, new rows are added to the end of an existing file rather than overwriting it. When appending to a file that already has content, the header is typically not re-written (depends on implementation). |
| 9 | Include Header | `INCLUDEHEADER` | Boolean (CHECK) | `false` | Include column headers as the first row. Uses schema column names. **Note**: Talend default is `false` (no header), unlike many tools that default to `true`. |
| 10 | Compress as Zip File | `COMPRESS` | Boolean (CHECK) | `false` | Compress the output file in ZIP format. Mutually exclusive with `SPLIT` -- cannot split and compress simultaneously. When enabled, the output file is wrapped in a ZIP archive. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 11 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number formatting with custom thousands and decimal separators for numeric output. |
| 12 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 13 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 14 | CSV Options | `CSV_OPTION` | Boolean (CHECK) | `false` | Enables RFC4180 CSV mode: activates escape char and text enclosure fields. When enabled, field separator must be a single character (regex not allowed). |
| 15 | Escape Char | `ESCAPE_CHAR` | Character | `"\\"` | Escape character for metacharacters inside quoted fields. Only visible when `CSV_OPTION=true`. Standard is backslash. Talend documentation recommends `"\\"`. |
| 16 | Text Enclosure | `TEXT_ENCLOSURE` | Character | `"\""` | Single character wrapping field values containing special characters (delimiters, newlines, etc.). Only visible when `CSV_OPTION=true`. Standard is double-quote. |
| 17 | CSV Row Separator | `CSVROWSEPARATOR` | String | -- | CSV-specific row separator used when `CSV_OPTION=true`. Overrides the standard `ROWSEPARATOR` in CSV mode. |
| 18 | Create Directory | `CREATE` | Boolean (CHECK) | `true` | Automatically create the parent directory if it does not exist. Selected by default. When disabled, writing to a nonexistent directory causes an error. |
| 19 | Split Output | `SPLIT` | Boolean (CHECK) | `false` | Divide the output file into multiple smaller files. Mutually exclusive with `COMPRESS`. When enabled, filenames are suffixed with a sequential index (e.g., `output_0.csv`, `output_1.csv`). |
| 20 | Rows Per File | `SPLIT_EVERY` | Integer | `1000` | Number of rows in each split output file. Only visible when `SPLIT=true`. |
| 21 | Flush Buffer | `FLUSHONROW` | Boolean (CHECK) | `false` | Enable custom buffer flushing interval. When enabled, the output stream is flushed after every N rows. |
| 22 | Flush Row Count | `FLUSHONROW_NUM` | Integer | `1` | Number of lines to write before emptying the buffer. Only visible when `FLUSHONROW=true`. Useful for reducing memory usage in streaming scenarios. |
| 23 | Row Mode | `ROW_MODE` | Boolean (CHECK) | `false` | Ensure atomicity of the flush operation. When enabled, each row write is flushed individually, ensuring data integrity in multi-threaded or crash-sensitive environments. |
| 24 | Encoding | `ENCODING` | Dropdown / Custom | `"ISO-8859-15"` | Character encoding for file writing. Options include ISO-8859-15, UTF-8, and custom values. **Note**: Talend default is `ISO-8859-15`, NOT `UTF-8`. JVM-dependent support for encoding names. |
| 25 | Don't Generate Empty File | `DELETE_EMPTYFILE` | Boolean (CHECK) | `false` | When selected, prevents creation of empty output files (files with no data rows). If no data flows to the component, no file is created. |
| 26 | File Exist Exception | `FILE_EXIST_EXCEPTION` | Boolean (CHECK) | `false` | Throw an exception if the specified output file already exists. Used to prevent accidental overwrites. |
| 27 | OS Line Separator | `OS_LINE_SEPARATOR_AS_ROW_SEPARATOR` | Boolean (CHECK) | `true` | Uses the operating-system-defined line separator for CR/LF/CRLF settings. When true, overrides the explicit `ROWSEPARATOR` value. |
| 28 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 29 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Incoming data rows to write to the file. The component receives rows from an upstream component connected via a Row link. All columns defined in the schema are expected to be present. |
| `ITERATE` | Input | Iterate | Enables iterative execution when the component is used within an iteration loop (e.g., `tFileList` + `tFlowToIterate`). The component writes files for each iteration. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows written to the output file. This is the primary row count variable. Stored via `globalMap.put("tFileOutputDelimited_1_NB_LINE", nb_line)` in generated Java code. |
| `{id}_FILE_NAME` | String | During flow | The name/path of the file currently being written. Available as a flow-level variable during processing. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. Only populated when error-catching is enabled. |

**Note on NB_LINE**: In Talend-generated Java code, `nb_line_tFileOutputDelimited_1++` is incremented for each row written, and the final value is stored in globalMap as `tFileOutputDelimited_1_NB_LINE` after the component completes. This counter reflects actual rows written, excluding the header row.

**Note on FILE_NAME**: This is a flow-level variable available during execution, unlike `NB_LINE` which is only available after execution. The resolved filename (after context variable and expression evaluation) is stored.

### 3.5 Behavioral Notes

1. **INCLUDEHEADER default is `false`**: Unlike many tools and libraries (including pandas which defaults to `True`), Talend defaults to NOT including the header. This is a common source of mismatch when converting jobs.

2. **Row separator after last row**: Talend's generated Java code writes a row separator after every row, including the last one. This means the output file ends with a trailing newline (or whatever the configured row separator is). Pandas `to_csv()` has the same behavior by default (`line_terminator='\n'`), so this is generally compatible.

3. **APPEND + INCLUDEHEADER interaction**: When `APPEND=true` and the target file already exists, Talend does NOT re-write the header, even if `INCLUDEHEADER=true`. The header is only written on the first write to a new/empty file. This prevents duplicate headers in appended files.

4. **COMPRESS vs SPLIT mutual exclusion**: These two features cannot be used simultaneously. The component either compresses the entire output into a ZIP archive OR splits it into multiple files, but not both. If both are enabled, the behavior is undefined.

5. **SPLIT file naming**: When `SPLIT=true`, Talend generates filenames by appending an index: `filename_0.csv`, `filename_1.csv`, etc. Each file contains up to `SPLIT_EVERY` rows. The header is included in each split file if `INCLUDEHEADER=true`.

6. **Default encoding**: Talend defaults to `ISO-8859-15`, NOT `UTF-8`. This is a critical behavioral difference from most Python library defaults. If a Talend job does not explicitly set encoding, it uses `ISO-8859-15`.

7. **Default field separator**: Talend defaults to `";"` (semicolon), NOT `","` (comma). This is important for European data formats where semicolon is the standard CSV delimiter.

8. **Empty data behavior**: When no data rows flow to the component:
   - With `INCLUDEHEADER=true`: Creates a file with only the header row
   - With `INCLUDEHEADER=false` and `DELETE_EMPTYFILE=false`: Creates an empty file (0 bytes)
   - With `INCLUDEHEADER=false` and `DELETE_EMPTYFILE=true`: No file is created (or existing file is deleted)

9. **FILE_EXIST_EXCEPTION**: When enabled, the component throws a Java exception if the target file already exists before writing begins. This is checked BEFORE any directory creation or write operations.

10. **ROW_MODE**: Ensures each row write is atomic. In standard buffered mode, multiple rows may be buffered before being flushed to disk. In row mode, each row is flushed immediately, which is slower but ensures data integrity in case of crashes or concurrent access.

11. **FLUSHONROW**: Provides a middle ground between full buffering and row mode. The buffer is flushed every N rows, balancing performance with data safety.

12. **CSV_OPTION=true**: Enables proper RFC4180 CSV writing with text enclosure and escape character. When enabled, fields containing the delimiter, newlines, or the enclosure character are wrapped in the text enclosure. The escape character is used to escape enclosure characters within fields.

13. **USESTREAM**: When enabled, the component writes to a Java OutputStream rather than a file. This is used for in-memory processing or piping data to other components. The stream variable is specified in `STREAMNAME`.

14. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow -- only in subsequent subjobs connected via triggers.

15. **Row-by-row writing**: Unlike batch-oriented tools, Talend's generated Java code writes rows one at a time through the main loop. Each row is formatted with delimiters and enclosures, written to the output stream, and the row counter is incremented. This design enables streaming and minimizes memory usage.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the **generic parameter mapping approach non-compliant with STANDARDS.md** (`_map_component_parameters()` in `component_parser.py` lines 129-147) rather than routing through the dedicated `parse_tfileoutputdelimited()` method that exists on lines 2252-2264. There is NO dedicated `elif component_type == 'tFileOutputDelimited'` branch in `converter.py:_parse_component()`. The component falls through to the generic `parse_base_component()` path.

**Important finding**: A dedicated parser method `parse_tfileoutputdelimited()` EXISTS at lines 2252-2264, but it is NEVER called because `converter.py` has no `elif component_type == 'tFileOutputDelimited'` branch to route to it. This means two separate extraction logic paths exist -- the active `_map_component_parameters()` path (lines 129-147) and the dormant dedicated parser (lines 2252-2264). They extract different subsets of parameters and use different extraction approaches.

**Converter flow (active path)**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tFileOutputDelimited', config_raw)` (line 472)
4. Returns mapped config with renamed keys
5. Schema is extracted generically from `<metadata connector="FLOW">` nodes

**Dormant dedicated parser** (`parse_tfileoutputdelimited()`, lines 2252-2264):
1. Directly accesses XML nodes via `node.find('.//elementParameter[@name="FILENAME"]')`
2. Extracts: FILENAME, FIELDSEPARATOR, ROWSEPARATOR, INCLUDEHEADER, APPEND, ENCODING, DIE_ON_ERROR
3. Also extracts FLOW input connections
4. Does NOT extract: CSV_OPTION, TEXT_ENCLOSURE, ESCAPE_CHAR, CREATE, DELETE_EMPTYFILE, COMPRESS, SPLIT, etc.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | 136 | Expressions and context vars handled by generic loop |
| 2 | `FIELDSEPARATOR` | Yes | `delimiter` | 137 | **Default `','` differs from Talend default `';'`** |
| 3 | `ROWSEPARATOR` | Yes | `row_separator` | 138 | Default `'\n'` matches Talend |
| 4 | `ENCODING` | Yes | `encoding` | 139 | **Default `'UTF-8'` differs from Talend default `'ISO-8859-15'`** |
| 5 | `TEXT_ENCLOSURE` | Yes (conditional) | `text_enclosure` | 132-134, 140 | Only extracted when `CSV_OPTION=true`. Set to `None` when false. Strips escaped quotes via `.replace('\\"', '')` |
| 6 | `INCLUDEHEADER` | Yes | `include_header` | 141 | Default `True` **differs from Talend default `false`** |
| 7 | `APPEND` | Yes | `append` | 142 | Default `False` matches Talend |
| 8 | `CREATE` | Yes | `create_directory` | 143 | Default `True` matches Talend |
| 9 | `DELETE_EMPTYFILE` | Yes | `delete_empty_file` | 144 | **Default `True` differs from Talend default `false`** |
| 10 | `DIE_ON_ERROR` | Yes | `die_on_error` | 145 | Default `False` matches Talend |
| 11 | `CSV_OPTION` | Yes | `csv_option` | 130, 146 | Extracted as boolean, used to gate TEXT_ENCLOSURE extraction. Passed through to config but **engine never reads it**. |
| 12 | `COMPRESS` | **No** | -- | -- | **Not extracted. No compressed output support.** |
| 13 | `SPLIT` | **No** | -- | -- | **Not extracted. No file splitting support.** |
| 14 | `SPLIT_EVERY` | **No** | -- | -- | **Not extracted.** |
| 15 | `ESCAPE_CHAR` | **No** | -- | -- | **Not extracted. Engine uses hardcoded DEFAULT_ESCAPE_CHAR = `'\\'` instead.** |
| 16 | `FLUSHONROW` | **No** | -- | -- | **Not extracted. No flush buffer support.** |
| 17 | `FLUSHONROW_NUM` | **No** | -- | -- | **Not extracted.** |
| 18 | `ROW_MODE` | **No** | -- | -- | **Not extracted. No row-mode atomicity.** |
| 19 | `FILE_EXIST_EXCEPTION` | **No** | -- | -- | **Not extracted. No file-exists check.** |
| 20 | `USESTREAM` | **No** | -- | -- | **Not extracted. No output stream support.** |
| 21 | `STREAMNAME` | **No** | -- | -- | **Not extracted.** |
| 22 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted. No locale-aware number formatting.** |
| 23 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 24 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 25 | `CSVROWSEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 26 | `OS_LINE_SEPARATOR_AS_ROW_SEPARATOR` | **No** | -- | -- | **Not extracted. OS line separator behavior not handled.** |
| 27 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 28 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 29 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 11 of 29 parameters extracted (38%). 16 runtime-relevant parameters are missing.

**Cross-reference with dormant `parse_tfileoutputdelimited()`**: The dedicated parser on lines 2252-2264 extracts ONLY 7 parameters (FILENAME, FIELDSEPARATOR, ROWSEPARATOR, INCLUDEHEADER, APPEND, ENCODING, DIE_ON_ERROR) and also extracts FLOW input connections. It does NOT extract CSV_OPTION, TEXT_ENCLOSURE, CREATE, or DELETE_EMPTYFILE, making it LESS comprehensive than the active `_map_component_parameters()` path. Neither extraction path covers the full parameter set.

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

**Note on output component schema**: For an output component like `tFileOutputDelimited`, the schema defines which columns to write and in what order. The schema is typically inherited from the upstream component via the "Sync columns" button in Talend Studio. The converter correctly extracts the FLOW metadata but does not extract REJECT metadata (output components do not have REJECT schemas).

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
- The FILENAME parameter commonly contains path expressions with `/`, string concatenation (`+`), and context references. The expression detection logic must carefully distinguish between a simple file path like `/data/output.csv` and a Java expression like `context.outputDir + "/output_" + TalendDate.getDate("yyyyMMdd") + ".csv"`.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FOD-001 | **P1** | **Dedicated parser exists but not wired**: `parse_tfileoutputdelimited()` exists at lines 2252-2264 but is NEVER called because `converter.py` has no `elif component_type == 'tFileOutputDelimited'` branch. The component falls through to `_map_component_parameters()`, which is non-compliant with STANDARDS.md. Per STANDARDS.md, every component MUST have its own `parse_*` method AND a corresponding dispatch branch. |
| CONV-FOD-002 | **P1** | **`ESCAPE_CHAR` not extracted**: The converter extracts `CSV_OPTION` and `TEXT_ENCLOSURE` but NOT `ESCAPE_CHAR`. The engine uses a hardcoded `DEFAULT_ESCAPE_CHAR = '\\'` instead of the user-configured value. Jobs with non-standard escape characters (e.g., `""` for doubleQuote mode) will produce incorrect output. |
| CONV-FOD-003 | **P1** | **`COMPRESS` not extracted**: Jobs requiring ZIP-compressed output will silently produce uncompressed files. |
| CONV-FOD-004 | **P2** | **Default `include_header=True` differs from Talend default `false`**: Converter line 141 defaults `INCLUDEHEADER` to `True`. Talend defaults to `false`. Jobs that do not explicitly set this parameter will get headers when they should not. |
| CONV-FOD-005 | **P2** | **Default `delete_empty_file=True` differs from Talend default `false`**: Converter line 144 defaults `DELETE_EMPTYFILE` to `True`. Talend defaults to `false`. Jobs that do not explicitly set this will delete empty files when they should create them. |
| CONV-FOD-006 | **P2** | **Default encoding mismatch**: Converter defaults `ENCODING` to `'UTF-8'` (line 139), but Talend default is `'ISO-8859-15'`. Files written without explicit encoding in the Talend job will use the wrong encoding. |
| CONV-FOD-007 | **P2** | **Default delimiter mismatch**: Converter defaults `FIELDSEPARATOR` to `','` (line 137), but Talend default is `';'`. Jobs relying on the Talend default semicolon delimiter will produce comma-separated output. |
| CONV-FOD-008 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both, this violates the documented standard. |
| CONV-FOD-009 | **P2** | **`FILE_EXIST_EXCEPTION` not extracted**: Jobs that require file-existence checks before writing will silently overwrite existing files. |
| CONV-FOD-010 | **P3** | **`SPLIT` / `SPLIT_EVERY` not extracted**: File splitting for large outputs unavailable. Low priority unless specific jobs use this feature. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Write delimited file | **Yes** | High | `_process()` line 230 | Uses `pd.DataFrame.to_csv()` -- solid core implementation |
| 2 | Include header | **Yes** | High | `_process()` line 213-215 | Correctly disabled when appending to existing file |
| 3 | Append mode | **Yes** | High | `_process()` line 212, 214 | `mode='a'` for append, `mode='w'` for overwrite. Header suppressed on append. |
| 4 | Encoding support | **Yes** | Medium | `_process()` line 233 | Passed to `to_csv()`. Default mismatch: engine defaults to UTF-8, Talend to ISO-8859-15 |
| 5 | Text enclosure / quoting | **Yes** | Medium | `_configure_quoting()` line 404-417 | `None` disables quoting (`QUOTE_NONE`); otherwise `QUOTE_MINIMAL` with configured `quotechar` |
| 6 | Create directory | **Yes** | High | `_ensure_directory_exists()` line 385-394 | Uses `os.makedirs(exist_ok=True)`. Correct behavior. |
| 7 | Delete empty file | **Yes** | Medium | `_handle_empty_data()` line 298-304 | Only deletes when both `delete_empty_file=True` AND no header was written. Does not create then delete; simply does not write. |
| 8 | Tab delimiter (`\t`) | **Yes** | High | `_normalize_delimiter()` line 396-402 | Normalizes `"\\t"` to `"\t"` |
| 9 | Empty data handling | **Yes** | High | `_handle_empty_data()` line 259-307 | Creates header-only file when `include_header=True`, handles delimiter normalization |
| 10 | Streaming mode | **Yes** | Medium | `_write_streaming()` line 309-383 | Generator-based chunked writing. First chunk gets header, subsequent chunks append. |
| 11 | Output schema filtering | **Yes** | Medium | `_apply_output_schema()` line 419-438 | Filters and reorders columns based on configured schema. Multiple schema sources checked. |
| 12 | Single-column output | **Yes** | Medium | `_write_single_column()` line 456-471 | Special case for empty delimiter (AT17854 logic). Writes each row as single string. |
| 13 | Die on error | **Yes** | High | `_process()` lines 150-157, 248-257 | Raises `FileOperationError`/`ConfigurationError` or returns empty DF |
| 14 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 15 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 16 | List-to-DataFrame conversion | **Yes** | Low | `_process()` line 172-183 | Converts list input to DataFrame. **Has scoping bug** -- see BUG-FOD-003. |
| 17 | Pass-through of input data | **Yes** | High | `_process()` line 246 | Returns input DataFrame as `{'main': input_data}` for flow continuation |
| 18 | **Compressed ZIP output** | **No** | N/A | -- | **No ZIP compression. `COMPRESS` not extracted or implemented.** |
| 19 | **Split output files** | **No** | N/A | -- | **No file splitting. `SPLIT` / `SPLIT_EVERY` not implemented.** |
| 20 | **Flush buffer** | **No** | N/A | -- | **No custom flush buffer. `FLUSHONROW` / `FLUSHONROW_NUM` not implemented. pandas `to_csv()` handles buffering internally.** |
| 21 | **Row mode** | **No** | N/A | -- | **No row-mode atomicity. `ROW_MODE` not implemented.** |
| 22 | **File exist exception** | **No** | N/A | -- | **No file-existence check. `FILE_EXIST_EXCEPTION` not implemented.** |
| 23 | **Output stream** | **No** | N/A | -- | **No OutputStream support. `USESTREAM` / `STREAMNAME` not implemented.** |
| 24 | **Escape char (configurable)** | **No** | N/A | -- | **Hardcoded `DEFAULT_ESCAPE_CHAR = '\\'`. User-configured `ESCAPE_CHAR` not used.** |
| 25 | **Advanced separator** | **No** | N/A | -- | **No locale-aware number formatting. `ADVANCED_SEPARATOR` not implemented.** |
| 26 | **Row separator in pandas** | **Partial** | Low | `_handle_empty_data()` line 275, `_write_single_column()` line 463 | Row separator only used in manual write paths (`_handle_empty_data`, `_write_single_column`). **NOT passed to `to_csv()` in the main write path** -- pandas uses `'\n'` by default regardless of config. |
| 27 | **`{id}_FILE_NAME` globalMap** | **No** | N/A | -- | **Resolved filename not stored in globalMap.** |
| 28 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |
| 29 | **CSV_OPTION toggle in engine** | **No** | N/A | -- | **`csv_option` config key is extracted by converter but never read by engine code.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FOD-001 | **P1** | **Row separator not applied in main write path**: The `row_separator` config is only used in `_handle_empty_data()` and `_write_single_column()`. In the main `to_csv()` path (line 230), `lineterminator` is NOT passed, so pandas defaults to `'\n'`. Jobs with `ROWSEPARATOR='\r\n'` or other custom separators will produce incorrect output. This is a significant fidelity gap since many Windows-origin Talend jobs use `\r\n`. |
| ENG-FOD-002 | **P1** | **No compressed ZIP output**: Jobs requiring ZIP compression will silently produce uncompressed files. pandas `to_csv()` supports `compression='zip'`, so implementation would be straightforward. |
| ENG-FOD-003 | **P1** | **No file splitting**: Large output jobs that split into multiple files will produce a single large file. Requires custom implementation wrapping `to_csv()` with row counting. |
| ENG-FOD-004 | **P1** | **Escape char hardcoded**: Engine always uses `DEFAULT_ESCAPE_CHAR = '\\'` (line 73) regardless of what the user configured in Talend. The `escapechar=self.DEFAULT_ESCAPE_CHAR` is hardcoded in `to_csv()` call on line 239. When `CSV_OPTION=true` with a non-default escape char, output will be incorrect. |
| ENG-FOD-005 | **P1** | **`{id}_FILE_NAME` not set in globalMap**: Downstream components referencing the resolved filename via globalMap will get null/None. Common in logging and audit flows. |
| ENG-FOD-006 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. |
| ENG-FOD-007 | **P2** | **Default encoding differs from Talend**: Engine defaults to `UTF-8` (line 71: `DEFAULT_ENCODING = 'UTF-8'`), but Talend defaults to `ISO-8859-15`. Files without explicit encoding in the Talend job will be written with the wrong encoding, potentially causing mojibake for non-ASCII characters. |
| ENG-FOD-008 | **P2** | **No file-exist exception**: Jobs with `FILE_EXIST_EXCEPTION=true` will silently overwrite existing files instead of throwing an error. |
| ENG-FOD-009 | **P2** | **`csv_option` extracted but unused**: The converter extracts `csv_option` (line 146), but the engine's `_process()` never reads `self.config.get('csv_option')`. The engine always applies the same quoting behavior regardless of whether CSV mode is enabled or disabled. |
| ENG-FOD-010 | **P2** | **No flush buffer / row mode**: These features affect write performance and data safety but are not implemented. For most batch jobs this is acceptable, but streaming/crash-sensitive scenarios may need them. |
| ENG-FOD-011 | **P3** | **No output stream support (USESTREAM)**: Writing to Java OutputStreams is not supported. Low priority since this requires Java bridge integration for the stream object. |
| ENG-FOD-012 | **P1** | **Streaming mode skips `_apply_output_schema()`**: The main `_process()` path calls `_apply_output_schema()` at line 206, but `_write_streaming()` does not. Streaming writes will include all columns instead of just the configured subset. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE since no reject exists for output components |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 for successful writes. Set to `rows_in` in the error handler (line 256). |
| `{id}_FILE_NAME` | Yes (official) | **No** | -- | Not implemented. Commonly expected. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FOD-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileOutputDelimited, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-FOD-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FOD-003 | **P1** | `src/v1/engine/components/file/file_output_delimited.py:176-183` | **List-to-DataFrame error handler scoping bug**: The `try` block (lines 173-175) converts a list to DataFrame, but the `except` block (lines 176-177) logs the error and then falls through. Lines 179-183 (`if die_on_error: raise ...`) are OUTSIDE the `except` block (they are at the same indent level as `if isinstance(input_data, list)`). This means: (a) if the conversion succeeds, the code falls through to `if die_on_error: raise FileOperationError(...)` which will ALWAYS raise because `die_on_error` defaults to `True` and `error_msg` and `e` are from the previous scope; (b) if the conversion fails, the error is logged but the code continues to execute the raise outside the except block. This is a control flow bug that can cause crashes on valid list input. |
| BUG-FOD-004 | **P1** | `src/v1/engine/components/file/file_output_delimited.py:77-122` | **`_validate_config()` is never called**: The method exists and contains 45 lines of validation logic, but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (missing filepath, non-string delimiter, etc.) are not caught until they cause runtime errors deep in processing. |
| BUG-FOD-005 | **P1** | `src/v1/engine/components/file/file_output_delimited.py:359-370` | **Streaming mode `delete_empty_file` is no-op**: When `total_rows == 0` and `delete_empty_file=True`, the code enters the if-block (line 366) but the file deletion is commented out (line 369: `# os.remove(filepath)`). The log message says "Empty file deletion skipped" (line 370). This means `delete_empty_file` has no effect in streaming mode, contradicting the configuration intent. |
| BUG-FOD-006 | **P3** | `src/v1/engine/components/file/file_output_delimited.py:361` | **Streaming mode stats accumulation** (Note/Informational): `_update_stats(chunk_rows, chunk_rows, 0)` is called per chunk, which ACCUMULATES stats in the base class (line 308: `self.stats['NB_LINE'] += rows_read`). This means if 3 chunks of 100 rows each are written, `NB_LINE` correctly shows 300. However, `_update_global_map()` is also called after each `execute()` (line 218 in base class), but `execute()` is only called once for the streaming write. The streaming `_write_streaming()` correctly accumulates internally, but the final global map update happens once at the end with the accumulated total. This is technically correct behavior and not a bug -- noted for informational purposes only. |
| BUG-FOD-007 | **P2** | `src/v1/engine/components/file/file_output_delimited.py:230-240` | **`escapechar` always set even with QUOTE_NONE**: When `text_enclosure=None`, `_configure_quoting()` returns `(QUOTE_NONE, None)`. The `to_csv()` call on line 239 still passes `escapechar=self.DEFAULT_ESCAPE_CHAR`. While pandas technically ignores `escapechar` when `quoting=QUOTE_NONE`, this is misleading and may cause issues with certain pandas versions. |
| BUG-FOD-008 | **P1** | `src/converters/complex_converter/component_parser.py:145`, `src/v1/engine/components/file/file_output_delimited.py:148` | **`die_on_error` default mismatch between converter and engine**: Converter defaults to `False` (line 145), but engine defaults to `True` (line 148: `self.config.get('die_on_error', True)`). If converter ever fails to set this key, engine behaves differently than expected. |
| BUG-FOD-009 | **P1** | `src/v1/engine/components/file/file_output_delimited.py:195` | **`_handle_empty_data()` skips directory creation**: The method writes a header file via `open(filepath, ...)` but never calls `_ensure_directory_exists()`. If parent directory doesn't exist and input is empty with `include_header=True`, it will fail with `FileNotFoundError` even when `create_directory=True`. The main write path at line 199-200 does call it, but the empty data path at line 195 returns before reaching it. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FOD-001 | **P2** | **`include_header` (engine)** vs Talend parameter `INCLUDEHEADER`. The engine uses `include_header` (snake_case with underscore), which is the correct Python convention. However, the converter line 141 maps it as `include_header` while the dormant dedicated parser (line 2257) also uses `include_header`. Consistent. |
| NAME-FOD-002 | **P2** | **`delete_empty_file` (engine)** vs Talend parameter `DELETE_EMPTYFILE`. The engine uses `delete_empty_file` while Talend uses `DELETE_EMPTYFILE`. The naming is reasonable but the semantic differs: Talend says "Don't generate empty file" (suppress creation), while the engine says "delete empty file" (implies creation then deletion). The engine implementation actually matches the Talend semantic (suppresses creation) but the name suggests deletion. |
| NAME-FOD-003 | **P3** | **`text_enclosure` vs `quotechar`**: The config key is `text_enclosure` (matching Talend terminology), but internally the engine uses `quotechar` (pandas terminology). This is acceptable since it follows the convention of using Talend names in config and library names in implementation. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FOD-001 | **P1** | "Every component MUST have its own `parse_*` method with dispatch" (STANDARDS.md line 1037) | `parse_tfileoutputdelimited()` EXISTS but is not wired into `converter.py`. The component uses `_map_component_parameters()`, which is non-compliant with STANDARDS.md. This is worse than not having a dedicated parser at all -- the code exists but is dead. |
| STD-FOD-002 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md line 91) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FOD-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md line 865) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |
| STD-FOD-004 | **P3** | Consistent indentation | Mixed indentation in class body: class constants (lines 69-75) use 4-space indent with extra leading space before comment. `_validate_config()` (lines 86-122) uses inconsistent 4+4 indentation for body content. Some methods have 8-space indent for body (e.g., lines 86-88), which appears to be 2-level indent rather than 1-level. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FOD-001 | **P3** | **Commented-out deletion in streaming mode**: Line 369 has `# os.remove(filepath)` with a comment "Note: Keeping original logic - commented out deletion". This is a debug/development artifact indicating incomplete implementation of `delete_empty_file` for streaming mode. Should either be uncommented (to match the feature intent) or removed entirely with a clear code comment explaining why deletion is intentionally skipped. |
| DBG-FOD-002 | **P3** | **Verbose debug logging for small inputs**: Lines 189-190 log `input_data.head()` when `len(input_data) <= 5`. This could expose sensitive data in logs. Should be behind a more restrictive debug flag or removed. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FOD-001 | **P3** | **No path traversal protection**: `filepath` from config is used directly with `os.path.exists()`, `os.makedirs()`, and passed to `pd.DataFrame.to_csv()`. If config comes from untrusted sources, path traversal (`../../etc/crontab`) could be used to write to arbitrary locations. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FOD-002 | **P3** | **No file permission control**: Files are created with default OS permissions. Talend does not configure file permissions either, but for sensitive data files, explicit permission setting (e.g., `0o600`) would be a defense-in-depth measure. |

### 6.6 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 159); logs completion with row counts (line 244) -- correct |
| Sensitive data | Lines 189-190 log input data head for small inputs -- potential concern for sensitive data |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `FileOperationError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern consistently -- correct |
| `die_on_error` handling | Three separate paths: missing filepath (line 150-157), main try/except (line 248-257), and empty data handling (not die-on-error aware -- always writes or deletes) |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID, file path, and error details -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct |
| **Gap**: `_handle_empty_data()` not die_on_error aware | `_handle_empty_data()` (line 294-296) raises `FileOperationError` unconditionally on header write failure. Should check `die_on_error` and return gracefully when false. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_write_streaming()`, `_handle_empty_data()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[str]`, `Iterator[pd.DataFrame]` -- correct |
| `_configure_quoting` | Returns `tuple` but should return `Tuple[int, Optional[str]]` for clarity |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FOD-001 | **P2** | **`_normalize_delimiter()` called redundantly**: In `_handle_empty_data()`, delimiter normalization is done manually (line 272-273: `if delimiter == '\\t': delimiter = '\t'`). In `_process()`, `_normalize_delimiter()` is called (line 203). In `_write_streaming()`, `_normalize_delimiter()` is also called (line 321). The manual normalization in `_handle_empty_data()` should use `_normalize_delimiter()` for consistency and to avoid duplicated logic. |
| PERF-FOD-002 | **P2** | **Row separator normalization duplicated**: `_handle_empty_data()` has manual row separator normalization (lines 275-281) that is not factored into a shared method. This same normalization should be applied in the main write path as well (currently row_separator is NOT passed to `to_csv()`), and should be a reusable method. |
| PERF-FOD-003 | **P3** | **`_configure_quoting()` called per chunk in streaming**: In `_write_streaming()` (line 343), `_configure_quoting()` is called inside the chunk loop. Since `text_enclosure` does not change between chunks, this could be called once before the loop. Minor performance impact. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Implemented via `_write_streaming()` with chunked iteration. Correct design for large datasets. |
| Memory threshold | Streaming activated via `BaseComponent._auto_select_mode()` when DataFrame memory > 3GB (`MEMORY_THRESHOLD_MB = 3072`). Reasonable default. |
| Chunked writing | Iterates over `data_iterator` generator -- memory efficient for large files. |
| Pass-through output | Returns input DataFrame as-is for non-streaming mode (line 246: `return {'main': input_data}`). No unnecessary copy. |
| Empty data path | Returns `pd.DataFrame()` (empty) -- minimal memory footprint. |

### 7.2 Streaming Mode Behavior

| Issue | Description |
|-------|-------------|
| First chunk header | Header written only for first non-empty chunk (lines 333-336). Correct behavior. |
| Append + first chunk | When `append=True`, first chunk uses `mode='a'` and suppresses header if file exists (line 335). Correct. |
| Empty chunk skipping | Empty chunks are skipped (lines 328-330). Correct. |
| Stats accumulation | `_update_stats()` called per chunk (line 361). Correctly accumulates totals. |
| Return value | Returns empty DataFrame for streaming mode (line 374). Correct since data is written to file, not passed through. |
| `delete_empty_file` | **BROKEN**: Deletion is commented out (line 369). See BUG-FOD-005. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileOutputDelimited` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests. All 472 lines of v1 engine code are completely unverified by automated tests.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic CSV write | P0 | Write a DataFrame with 3 columns and 10 rows to a CSV file, verify file contents match expected output with correct delimiters and no header (Talend default) |
| 2 | Write with header | P0 | Write with `include_header=True`, verify first row contains column names separated by delimiter |
| 3 | Write without header | P0 | Write with `include_header=False` (Talend default), verify no header row in output |
| 4 | Append mode | P0 | Write to existing file with `append=True`, verify new rows are added to end and header is NOT duplicated |
| 5 | Missing filepath + die_on_error=true | P0 | Should raise `ConfigurationError` with descriptive message |
| 6 | Missing filepath + die_on_error=false | P0 | Should return empty DataFrame with stats (0, 0, 0) |
| 7 | Empty input | P0 | Verify behavior with empty DataFrame: header-only file when `include_header=True`, empty/no file when `include_header=False` |
| 8 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict after execution (NB_LINE = NB_LINE_OK = row count, NB_LINE_REJECT = 0) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 9 | Tab delimiter | P1 | Write with `delimiter="\\t"`, verify tab normalization and correct TSV output |
| 10 | Custom delimiter (pipe) | P1 | Write with `delimiter="|"`, verify correct pipe-delimited output |
| 11 | Text enclosure / quoting | P1 | Write with `text_enclosure='"'`, verify fields containing delimiter are properly quoted |
| 12 | No quoting (text_enclosure=None) | P1 | Write with `text_enclosure=None`, verify no quoting in output (`QUOTE_NONE`) |
| 13 | Encoding ISO-8859-15 | P1 | Write non-ASCII characters with ISO-8859-15 encoding, verify correct encoding in output file |
| 14 | Create directory | P1 | Write to filepath in nonexistent directory with `create_directory=True`, verify directory is created |
| 15 | Create directory disabled | P1 | Write to filepath in nonexistent directory with `create_directory=False`, verify error is raised |
| 16 | Context variable in filepath | P1 | `${context.output_dir}/output.csv` should resolve via context manager |
| 17 | Delete empty file | P1 | Write empty DataFrame with `delete_empty_file=True` and `include_header=False`, verify no file is created |
| 18 | Streaming mode | P1 | Write large data via streaming iterator, verify all chunks are written correctly with header only once |
| 19 | List input conversion | P1 | Pass list of dicts as input, verify correct DataFrame conversion and file write |
| 20 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution |
| 21 | Row separator custom | P1 | Write with `row_separator='\r\n'`, verify Windows-style line endings in output |
| 22 | Output schema filtering | P1 | Configure output_schema with subset of columns, verify only those columns appear in output |
| 23 | Overwrite existing file | P1 | Write to existing file with `append=False`, verify file is overwritten (not appended) |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 24 | Large file streaming | P2 | Verify streaming mode produces correct output for large datasets (1M+ rows) |
| 25 | Concurrent writes | P2 | Multiple `FileOutputDelimited` instances writing to different files simultaneously |
| 26 | Unicode in data | P2 | Write DataFrame with Unicode characters (CJK, emoji, accented chars) with UTF-8 encoding |
| 27 | File permissions | P2 | Verify output file has appropriate permissions after creation |
| 28 | Empty delimiter | P2 | Write with empty delimiter, verify single-column output behavior |
| 29 | Schema with types | P2 | Write DataFrame with mixed types (int, float, string, date), verify correct string representation |
| 30 | Semicolon delimiter | P2 | Write with `delimiter=";"` (Talend default), verify correct output |
| 31 | Error during write | P2 | Simulate write error (e.g., read-only directory) with `die_on_error=false`, verify graceful handling |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FOD-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FOD-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FOD-001 | Testing | Zero v1 unit tests for the most-used output component. All 472 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOD-001 | Converter | Dedicated parser `parse_tfileoutputdelimited()` exists but is not wired into `converter.py`. Uses `_map_component_parameters()` instead, which is non-compliant with STANDARDS.md. |
| CONV-FOD-002 | Converter | `ESCAPE_CHAR` not extracted -- engine uses hardcoded `DEFAULT_ESCAPE_CHAR`. |
| CONV-FOD-003 | Converter | `COMPRESS` not extracted -- no compressed output support. |
| ENG-FOD-001 | Engine | **Row separator not applied in main write path** -- `to_csv()` always uses `'\n'` default. Jobs with `\r\n` or custom row separators will produce incorrect output. |
| ENG-FOD-002 | Engine | No compressed ZIP output -- `COMPRESS` not implemented. |
| ENG-FOD-003 | Engine | No file splitting -- `SPLIT` / `SPLIT_EVERY` not implemented. |
| ENG-FOD-004 | Engine | Escape char hardcoded to `\\` -- user-configured `ESCAPE_CHAR` ignored. |
| ENG-FOD-005 | Engine | `{id}_FILE_NAME` globalMap variable not set -- downstream references get null. |
| ENG-FOD-006 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set -- error details not available downstream. |
| BUG-FOD-003 | Bug | List-to-DataFrame error handler scoping bug -- `if die_on_error: raise` is outside `except` block, will always raise on list input. |
| BUG-FOD-004 | Bug | `_validate_config()` is dead code -- never called by any code path. 45 lines of unreachable validation. |
| BUG-FOD-005 | Bug | Streaming mode `delete_empty_file` is no-op -- file deletion is commented out with `# os.remove(filepath)`. |
| BUG-FOD-008 | Bug | `die_on_error` default mismatch between converter (`False`) and engine (`True`). If converter fails to set this key, engine behaves differently than expected. |
| BUG-FOD-009 | Bug | `_handle_empty_data()` skips directory creation -- will fail with `FileNotFoundError` when parent directory doesn't exist and input is empty with `include_header=True` and `create_directory=True`. |
| ENG-FOD-012 | Engine | Streaming mode skips `_apply_output_schema()` -- streaming writes include all columns instead of just the configured subset. |
| STD-FOD-001 | Standards | Dedicated parser exists but not wired into converter dispatch. |
| TEST-FOD-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOD-004 | Converter | Default `include_header=True` differs from Talend default `false`. |
| CONV-FOD-005 | Converter | Default `delete_empty_file=True` differs from Talend default `false`. |
| CONV-FOD-006 | Converter | Default encoding mismatch: converter defaults to `UTF-8`, Talend defaults to `ISO-8859-15`. |
| CONV-FOD-007 | Converter | Default delimiter mismatch: converter defaults to `,`, Talend defaults to `;`. |
| CONV-FOD-008 | Converter | Converter uses Python type format in schema instead of Talend type format. |
| CONV-FOD-009 | Converter | `FILE_EXIST_EXCEPTION` not extracted -- existing files silently overwritten. |
| ENG-FOD-007 | Engine | Default encoding `UTF-8` differs from Talend default `ISO-8859-15`. |
| ENG-FOD-008 | Engine | No file-exist exception (`FILE_EXIST_EXCEPTION` not implemented). |
| ENG-FOD-009 | Engine | `csv_option` extracted but never read by engine code. |
| ENG-FOD-010 | Engine | No flush buffer / row mode (`FLUSHONROW`, `ROW_MODE` not implemented). |
| BUG-FOD-007 | Bug | `escapechar` always set even with `QUOTE_NONE` -- misleading, may cause issues. |
| NAME-FOD-001 | Naming | `include_header` naming consistent but Talend default mismatch (`false` vs `True`). |
| NAME-FOD-002 | Naming | `delete_empty_file` semantic mismatch with Talend's "Don't generate empty file". |
| STD-FOD-002 | Standards | `_validate_config()` exists but never called -- dead validation code. |
| STD-FOD-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| PERF-FOD-001 | Performance | `_normalize_delimiter()` not used in `_handle_empty_data()` -- duplicated logic. |
| PERF-FOD-002 | Performance | Row separator normalization duplicated across methods. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOD-010 | Converter | `SPLIT` / `SPLIT_EVERY` not extracted -- file splitting unavailable (rarely used). |
| ENG-FOD-011 | Engine | No output stream support (`USESTREAM`/`STREAMNAME`). |
| BUG-FOD-006 | Note/Informational | Streaming mode stats accumulation -- technically correct behavior, noted for informational purposes. |
| NAME-FOD-003 | Naming | `text_enclosure` vs `quotechar` internal naming (acceptable convention). |
| STD-FOD-004 | Standards | Mixed indentation in class body. |
| SEC-FOD-001 | Security | No path traversal protection on `filepath`. |
| SEC-FOD-002 | Security | No file permission control on created files. |
| DBG-FOD-001 | Debug | Commented-out `os.remove()` in streaming mode -- development artifact. |
| DBG-FOD-002 | Debug | Input data head logged for small inputs -- potential sensitive data exposure. |
| PERF-FOD-003 | Performance | `_configure_quoting()` called per chunk in streaming (minor). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 17 | 3 converter, 7 engine, 5 bugs, 1 standards, 1 testing |
| P2 | 17 | 6 converter, 4 engine, 1 bug, 2 naming, 2 standards, 2 performance |
| P3 | 10 | 1 converter, 1 engine, 1 naming, 1 standards, 2 security, 2 debug, 1 performance, 1 note/informational |
| **Total** | **47** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FOD-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FOD-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FOD-001): Implement at minimum the 8 P0 test cases listed in Section 8.2. These cover: basic CSV write, header/no-header, append mode, missing filepath handling (both die_on_error modes), empty input, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Fix list-to-DataFrame scoping bug** (BUG-FOD-003): The `if die_on_error: raise` block (lines 179-183) must be inside the `except` block. Move lines 179-183 into the except handler and add `return` after the non-die path:
   ```python
   except Exception as e:
       error_msg = f"Failed to convert list to DataFrame: {str(e)}"
       logger.error(f"[{self.id}] Data conversion error: {error_msg}")
       if die_on_error:
           raise FileOperationError(f"[{self.id}] {error_msg}") from e
       else:
           self._update_stats(0, 0, 0)
           return {'main': pd.DataFrame()}
   ```

5. **Apply row separator in main write path** (ENG-FOD-001): Pass `lineterminator` (or `line_terminator` for older pandas) to `to_csv()`:
   ```python
   row_separator = self.config.get('row_separator', self.DEFAULT_ROW_SEPARATOR)
   row_separator = self._normalize_row_separator(row_separator)
   input_data.to_csv(..., lineterminator=row_separator)
   ```
   This is critical for Windows-origin Talend jobs that use `\r\n`.

### Short-Term (Hardening)

6. **Wire dedicated parser into converter** (CONV-FOD-001, STD-FOD-001): Add `elif component_type == 'tFileOutputDelimited': component = self.component_parser.parse_tfileoutputdelimited(node, component)` to `converter.py:_parse_component()`. Then expand `parse_tfileoutputdelimited()` to extract ALL missing parameters: `COMPRESS`, `SPLIT`, `SPLIT_EVERY`, `ESCAPE_CHAR`, `FLUSHONROW`, `FLUSHONROW_NUM`, `ROW_MODE`, `FILE_EXIST_EXCEPTION`, `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`, `CSVROWSEPARATOR`, `USESTREAM`, `STREAMNAME`.

7. **Fix default value mismatches** (CONV-FOD-004, CONV-FOD-005, CONV-FOD-006, CONV-FOD-007):
   - Change `include_header` default from `True` to `False` (Talend default)
   - Change `delete_empty_file` default from `True` to `False` (Talend default)
   - Change `encoding` default from `'UTF-8'` to `'ISO-8859-15'` (Talend default)
   - Change `delimiter` default from `','` to `';'` (Talend default)

8. **Extract and use ESCAPE_CHAR** (CONV-FOD-002, ENG-FOD-004): Add `ESCAPE_CHAR` extraction in the converter. In the engine, read `self.config.get('escape_char', self.DEFAULT_ESCAPE_CHAR)` instead of hardcoding `self.DEFAULT_ESCAPE_CHAR` in the `to_csv()` call.

9. **Set `{id}_FILE_NAME` and `{id}_ERROR_MESSAGE` in globalMap** (ENG-FOD-005, ENG-FOD-006): After resolving filepath in `_process()`, call `self.global_map.put(f"{self.id}_FILE_NAME", filepath)`. In error handlers, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

10. **Fix streaming `delete_empty_file`** (BUG-FOD-005): Uncomment `os.remove(filepath)` on line 369, or implement proper empty-file deletion logic.

11. **Wire up `_validate_config()`** (BUG-FOD-004): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` or returning empty DataFrame based on `die_on_error`.

12. **Add compressed output support** (ENG-FOD-002): Read the `compress` config flag. When true, pass `compression='zip'` to `pd.DataFrame.to_csv()`. This is a one-parameter change since pandas handles compression natively.

### Long-Term (Optimization)

13. **Implement file splitting** (ENG-FOD-003): When `split=True`, implement a loop that writes `split_every` rows at a time to sequentially-numbered files. Each file gets the header if `include_header=True`. Requires custom logic wrapping `to_csv()`.

14. **Implement FILE_EXIST_EXCEPTION** (ENG-FOD-008): Before any write operations, check `os.path.exists(filepath)` when `file_exist_exception=True`. Raise `FileOperationError` if the file exists.

15. **Factor out row separator normalization** (PERF-FOD-001, PERF-FOD-002): Create a `_normalize_row_separator()` method and use it consistently across `_handle_empty_data()`, `_write_single_column()`, and the main write path.

16. **Implement flush buffer / row mode** (ENG-FOD-010): For `flushonrow=True`, wrap the write operation with explicit buffer flushing every N rows. For `row_mode=True`, flush after each row. This may require switching from `to_csv()` to manual row-by-row writing.

17. **Add path traversal protection** (SEC-FOD-001): Validate filepath against allowed base directories before passing to `os.makedirs()` and `to_csv()`.

18. **Create integration test** (TEST-FOD-002): Build an end-to-end test exercising `tFileInputDelimited -> tMap -> tFileOutputDelimited` in the v1 engine, verifying context resolution, Java bridge integration, and globalMap propagation.

19. **Implement output stream support** (ENG-FOD-011): Low priority. Would require Java bridge integration to access the Java OutputStream object.

20. **Clean up debug artifacts** (DBG-FOD-001, DBG-FOD-002): Uncomment or remove the `# os.remove(filepath)` line. Guard input data logging behind a stricter debug check.

---

## Appendix A: Converter Parameter Mapping Code (Active Path)

```python
# component_parser.py lines 129-147 (_map_component_parameters)
# FileOutputDelimited mapping
elif component_type == 'tFileOutputDelimited':
    csv_option = config_raw.get('CSV_OPTION', False)
    if str(csv_option).lower() == 'true':
        text_enclosure = config_raw.get('TEXT_ENCLOSURE', '').replace('\\"', '')
    else:
        text_enclosure = None
    return {
        'filepath': config_raw.get('FILENAME', ''),
        'delimiter': config_raw.get('FIELDSEPARATOR', ','),
        'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
        'encoding': config_raw.get('ENCODING', 'UTF-8'),
        'text_enclosure': text_enclosure,
        'include_header': config_raw.get('INCLUDEHEADER', True),
        'append': config_raw.get('APPEND', False),
        'create_directory': config_raw.get('CREATE', True),
        'delete_empty_file': config_raw.get('DELETE_EMPTYFILE', True),
        'die_on_error': config_raw.get('DIE_ON_ERROR', False),
        'csv_option': csv_option
    }
```

**Notes on this code**:
- Line 130-131: `CSV_OPTION` is extracted as a raw value and compared as string `'true'`. When the generic parameter loop processes CHECK fields, boolean `True` is stored. The `str(csv_option).lower() == 'true'` handles both `True` (boolean) and `'true'` (string). Correct but fragile.
- Line 132: `replace('\\"', '')` strips escaped quotes. Handles Talend XML storing `"\""` for a quote character.
- Line 137: Default `FIELDSEPARATOR` is `','` but Talend default is `';'`.
- Line 139: Default `ENCODING` is `'UTF-8'` but Talend default is `'ISO-8859-15'`.
- Line 141: Default `INCLUDEHEADER` is `True` but Talend default is `false`.
- Line 144: Default `DELETE_EMPTYFILE` is `True` but Talend default is `false`.

---

## Appendix B: Converter Dedicated Parser Code (Dormant)

```python
# component_parser.py lines 2252-2264 (parse_tfileoutputdelimited)
def parse_tfileoutputdelimited(self, node, component: Dict) -> Dict:
    """Parse tFileOutputDelimited specific configuration"""
    component['config']['filepath'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    component['config']['delimiter'] = node.find('.//elementParameter[@name="FIELDSEPARATOR"]').get('value', ';')
    component['config']['row_separator'] = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
    component['config']['include_header'] = node.find('.//elementParameter[@name="INCLUDEHEADER"]').get('value', 'true').lower() == 'true'
    component['config']['append'] = node.find('.//elementParameter[@name="APPEND"]').get('value', 'false').lower() == 'true'
    component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

    # Ensure the component is ready to accept input data
    component['inputs'] = [input_flow.get('name') for input_flow in node.findall('.//connection[@connectorName="FLOW"]')]
    return component
```

**Notes on this code**:
- Line 2255: Default `FIELDSEPARATOR` is `';'` -- **correctly matches Talend default** (unlike the active path which defaults to `,`).
- Line 2257: Default `INCLUDEHEADER` is `'true'` -- still differs from Talend default `false`.
- Line 2259: Default `ENCODING` is `'UTF-8'` -- still differs from Talend default `ISO-8859-15`.
- **Missing parameters**: Does NOT extract `CSV_OPTION`, `TEXT_ENCLOSURE`, `ESCAPE_CHAR`, `CREATE`, `DELETE_EMPTYFILE`, `COMPRESS`, `SPLIT`, `SPLIT_EVERY`, `FLUSHONROW`, `ROW_MODE`, `FILE_EXIST_EXCEPTION`, `ADVANCED_SEPARATOR`, etc.
- **Input connections**: Extracts FLOW input connections (line 2263), which the active path does NOT do.
- **No context/expression handling**: Direct XML access does not go through the generic expression detection pipeline.

**Comparison of active vs dormant parser**:

| Parameter | Active (`_map_component_parameters`) | Dormant (`parse_tfileoutputdelimited`) |
|-----------|--------------------------------------|---------------------------------------|
| FILENAME | Yes | Yes |
| FIELDSEPARATOR | Yes (default: `,`) | Yes (default: `;`) |
| ROWSEPARATOR | Yes | Yes |
| ENCODING | Yes | Yes |
| INCLUDEHEADER | Yes (default: `True`) | Yes (default: `true`) |
| APPEND | Yes | Yes |
| DIE_ON_ERROR | Yes | Yes |
| CSV_OPTION | Yes | **No** |
| TEXT_ENCLOSURE | Yes (conditional on CSV_OPTION) | **No** |
| CREATE | Yes | **No** |
| DELETE_EMPTYFILE | Yes | **No** |
| FLOW inputs | **No** | Yes |
| Expression detection | Yes (via generic pipeline) | **No** |

---

## Appendix C: Engine Class Structure

```
FileOutputDelimited (BaseComponent)
    Constants:
        DEFAULT_DELIMITER = ','
        DEFAULT_ENCODING = 'UTF-8'
        DEFAULT_ROW_SEPARATOR = '\n'
        DEFAULT_ESCAPE_CHAR = '\\'
        QUOTE_NONE = 3       # csv.QUOTE_NONE
        QUOTE_MINIMAL = 1    # csv.QUOTE_MINIMAL

    Methods:
        _validate_config() -> List[str]              # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]       # Main entry point (lines 124-257)
        _handle_empty_data(...) -> Dict[str, Any]    # Empty input handling (lines 259-307)
        _write_streaming(...) -> Dict[str, Any]      # Streaming write (lines 309-383)
        _ensure_directory_exists(filepath)            # Directory creation (lines 385-394)
        _normalize_delimiter(delimiter) -> str        # Tab and multi-char delimiter handling (lines 396-402)
        _configure_quoting(text_enclosure) -> tuple   # Quoting mode selection (lines 404-417)
        _apply_output_schema(df) -> DataFrame         # Schema-based column filtering (lines 419-438)
        _get_output_schema_columns() -> List[str]     # Get column names from schema (lines 440-454)
        _write_single_column(df, filepath, mode, encoding)  # Empty-delimiter special case (lines 456-471)
```

---

## Appendix D: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filepath` | Mapped | -- |
| `FIELDSEPARATOR` | `delimiter` | Mapped (wrong default) | Fix default |
| `ROWSEPARATOR` | `row_separator` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped (wrong default) | Fix default |
| `TEXT_ENCLOSURE` | `text_enclosure` | Mapped (conditional) | -- |
| `INCLUDEHEADER` | `include_header` | Mapped (wrong default) | Fix default |
| `APPEND` | `append` | Mapped | -- |
| `CREATE` | `create_directory` | Mapped | -- |
| `DELETE_EMPTYFILE` | `delete_empty_file` | Mapped (wrong default) | Fix default |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `CSV_OPTION` | `csv_option` | Mapped (unused by engine) | P2 -- engine must read it |
| `COMPRESS` | `compress` | **Not Mapped** | P1 |
| `ESCAPE_CHAR` | `escape_char` | **Not Mapped** | P1 |
| `SPLIT` | `split` | **Not Mapped** | P3 |
| `SPLIT_EVERY` | `split_every` | **Not Mapped** | P3 |
| `FLUSHONROW` | `flush_on_row` | **Not Mapped** | P3 |
| `FLUSHONROW_NUM` | `flush_row_count` | **Not Mapped** | P3 |
| `ROW_MODE` | `row_mode` | **Not Mapped** | P3 |
| `FILE_EXIST_EXCEPTION` | `file_exist_exception` | **Not Mapped** | P2 |
| `USESTREAM` | `use_stream` | **Not Mapped** | P3 (requires Java bridge) |
| `STREAMNAME` | `stream_name` | **Not Mapped** | P3 (requires Java bridge) |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** | P2 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** | P2 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** | P2 |
| `CSVROWSEPARATOR` | `csv_row_separator` | **Not Mapped** | P3 |
| `OS_LINE_SEPARATOR_AS_ROW_SEPARATOR` | -- | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix E: Edge Case Analysis

### Edge Case 1: Empty DataFrame input

| Aspect | Detail |
|--------|--------|
| **Talend** | With INCLUDEHEADER=true: writes header-only file. With INCLUDEHEADER=false and DELETE_EMPTYFILE=false: writes empty file. With DELETE_EMPTYFILE=true: no file created. |
| **V1** | `_handle_empty_data()` creates header-only file when `include_header=True` and schema available. Deletes file when `delete_empty_file=True` and no header was written. |
| **Verdict** | CORRECT for header-only case. For DELETE_EMPTYFILE, default mismatch (`True` vs Talend `false`) may cause unexpected behavior. |

### Edge Case 2: None input

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend always sends rows through the component. Zero rows is handled as empty. |
| **V1** | `_process()` checks `input_data is None` (line 193), routes to `_handle_empty_data()`. Correct. |
| **Verdict** | CORRECT |

### Edge Case 3: Append to non-existent file

| Aspect | Detail |
|--------|--------|
| **Talend** | Creates the file (if CREATE=true) and writes with header (if INCLUDEHEADER=true). |
| **V1** | `mode='a'` with `os.path.exists(filepath)` check (line 214). File is created by `open()` in append mode. Header is included because file does not exist yet (line 215: `write_header = False` only if file exists). |
| **Verdict** | CORRECT |

### Edge Case 4: Append to existing file

| Aspect | Detail |
|--------|--------|
| **Talend** | Appends rows without re-writing header. |
| **V1** | Line 214-215: `if append and os.path.exists(filepath): write_header = False`. Correct behavior. |
| **Verdict** | CORRECT |

### Edge Case 5: File path with spaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `os.path.exists()`, `os.makedirs()`, and `pd.DataFrame.to_csv()` all handle spaces correctly. |
| **Verdict** | CORRECT |

### Edge Case 6: Unicode BOM in output

| Aspect | Detail |
|--------|--------|
| **Talend** | Does not add BOM. Output is raw encoded bytes. |
| **V1** | pandas `to_csv()` does not add BOM with standard encoding. Using `encoding='utf-8-sig'` would add BOM, but the default `'UTF-8'` does not. |
| **Verdict** | CORRECT |

### Edge Case 7: Very large file (>3GB)

| Aspect | Detail |
|--------|--------|
| **Talend** | Writes row-by-row, minimal memory usage. |
| **V1** | If input is a DataFrame, `to_csv()` writes it all at once. Memory usage depends on the input DF size, not the output file size. Streaming mode handles chunked input. |
| **Verdict** | PARTIAL -- streaming mode works, but batch mode may OOM for very large inputs. |

### Edge Case 8: Delimiter is regex special char (e.g., `|`)

| Aspect | Detail |
|--------|--------|
| **Talend** | Treats `|` as literal character. |
| **V1** | `_normalize_delimiter()` returns `rf"{delimiter}"` for multi-char delimiters (line 401). For single char `|`, returns as-is (line 402). pandas `to_csv(sep='|')` treats it literally. |
| **Verdict** | CORRECT |

### Edge Case 9: Text enclosure with fields containing delimiter

| Aspect | Detail |
|--------|--------|
| **Talend** | With CSV_OPTION=true, fields containing the delimiter are wrapped in text enclosure. |
| **V1** | `_configure_quoting()` returns `QUOTE_MINIMAL` when text_enclosure is set. pandas wraps fields containing the delimiter in quotes. |
| **Verdict** | CORRECT (when text_enclosure is configured) |

### Edge Case 10: Text enclosure with fields containing newlines

| Aspect | Detail |
|--------|--------|
| **Talend** | With CSV_OPTION=true, fields containing newlines are wrapped in text enclosure. |
| **V1** | pandas `to_csv()` with `QUOTE_MINIMAL` wraps fields containing newlines in quotes. |
| **Verdict** | CORRECT (when text_enclosure is configured) |

### Edge Case 11: Empty delimiter (single-column output)

| Aspect | Detail |
|--------|--------|
| **Talend** | Writes each row as a single field, one per line. |
| **V1** | `_write_single_column()` is triggered when `delimiter == ""` (line 225). Writes first column only, one per line. |
| **Verdict** | PARTIAL -- only writes first column, which is correct for single-column schemas but silently drops additional columns. No warning logged for multi-column schemas with empty delimiter. |

### Edge Case 12: Row separator `\r\n` (Windows)

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses `\r\n` as configured. |
| **V1** | Row separator is normalized in `_handle_empty_data()` (lines 278-279) but NOT applied in the main `to_csv()` path. pandas defaults to `'\n'`. |
| **Verdict** | **GAP** -- Windows-style line endings not applied in main write path. See ENG-FOD-001. |

### Edge Case 13: Context variable in filepath resolving to empty

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with clear error. |
| **V1** | `_process()` checks `if not filepath:` (line 150). Raises `ConfigurationError` or returns empty DF based on `die_on_error`. |
| **Verdict** | CORRECT |

### Edge Case 14: Multiple columns with same name in schema

| Aspect | Detail |
|--------|--------|
| **Talend** | Writes both columns (Talend supports duplicate column names). |
| **V1** | pandas DataFrames can have duplicate column names but `to_csv()` writes all columns. `_apply_output_schema()` uses list-based column selection which handles duplicates. |
| **Verdict** | LIKELY CORRECT (edge case, not explicitly tested) |

### Edge Case 15: Writing NaN/null values

| Aspect | Detail |
|--------|--------|
| **Talend** | Writes null/empty string depending on type and configuration. |
| **V1** | pandas `to_csv()` writes NaN as empty string by default (when `na_rep=''`). The `na_rep` parameter is not explicitly set, so pandas uses its default (empty string). |
| **Verdict** | PARTIALLY CORRECT -- pandas default NaN representation is empty string, which matches Talend's common behavior. However, Talend may write `"null"` for some types. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileOutputDelimited`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FOD-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FOD-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FOD-004 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-FOD-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FOD-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FOD-003 -- List-to-DataFrame error handler scoping

**File**: `src/v1/engine/components/file/file_output_delimited.py`
**Lines**: 172-183

**Current code (broken)**:
```python
# Convert list input to DataFrame if needed
if isinstance(input_data, list):
    try:
        input_data = pd.DataFrame(input_data)
        logger.debug(f"[{self.id}] Converted list input to DataFrame: {len(input_data)} rows")
    except Exception as e:
        error_msg = f"Failed to convert list to DataFrame: {str(e)}"
        logger.error(f"[{self.id}] Data conversion error: {error_msg}")
    if die_on_error:
        raise FileOperationError(f"[{self.id}] {error_msg}") from e
    else:
        self._update_stats(0, 0, len(input_data) if input_data else 0)
        return {'main': pd.DataFrame()}
```

**Fix**:
```python
# Convert list input to DataFrame if needed
if isinstance(input_data, list):
    try:
        input_data = pd.DataFrame(input_data)
        logger.debug(f"[{self.id}] Converted list input to DataFrame: {len(input_data)} rows")
    except Exception as e:
        error_msg = f"Failed to convert list to DataFrame: {str(e)}"
        logger.error(f"[{self.id}] Data conversion error: {error_msg}")
        if die_on_error:
            raise FileOperationError(f"[{self.id}] {error_msg}") from e
        else:
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}
```

**Explanation**: The `if die_on_error: raise` block was at the same indentation level as the `if isinstance(input_data, list)` check, meaning it would ALWAYS execute (whether the conversion succeeded or not). When the conversion succeeds, `error_msg` and `e` are undefined (from a previous or non-existent scope), causing a `NameError`. When the conversion fails, the except block logs the error but does not prevent execution from continuing to the raise statement. Both paths are broken.

**Impact**: Fixes list-to-DataFrame conversion path. **Risk**: Low.

---

### Fix Guide: ENG-FOD-001 -- Row separator in main write path

**File**: `src/v1/engine/components/file/file_output_delimited.py`
**Lines**: 230-240

**Current code (missing row separator)**:
```python
input_data.to_csv(
    filepath,
    sep=delimiter,
    encoding=encoding,
    header=write_header,
    index=False,
    mode=mode,
    quotechar=quotechar,
    quoting=quoting,
    escapechar=self.DEFAULT_ESCAPE_CHAR
)
```

**Fix**:
```python
# Normalize row separator
row_separator = self.config.get('row_separator', self.DEFAULT_ROW_SEPARATOR)
if row_separator == '\\n':
    row_separator = '\n'
elif row_separator == '\\r\\n':
    row_separator = '\r\n'
elif row_separator == '\\t':
    row_separator = '\t'

input_data.to_csv(
    filepath,
    sep=delimiter,
    encoding=encoding,
    header=write_header,
    index=False,
    mode=mode,
    quotechar=quotechar,
    quoting=quoting,
    escapechar=self.DEFAULT_ESCAPE_CHAR,
    lineterminator=row_separator
)
```

**Better fix** -- factor out row separator normalization into a method:
```python
def _normalize_row_separator(self, row_separator: str) -> str:
    """Convert row separator shortcuts to actual characters."""
    if row_separator == '\\n':
        return '\n'
    elif row_separator == '\\r\\n':
        return '\r\n'
    elif row_separator == '\\t':
        return '\t'
    return row_separator
```

Then use it in `_process()`, `_handle_empty_data()`, `_write_single_column()`, and `_write_streaming()`.

**Impact**: Fixes Windows-style line endings and custom row separators. **Risk**: Low.

---

### Fix Guide: CONV-FOD-001 -- Wire dedicated parser

**File**: `src/converters/complex_converter/converter.py`
**Location**: `_parse_component()` method, after the last `elif` branch

**Add this branch**:
```python
elif component_type == 'tFileOutputDelimited':
    component = self.component_parser.parse_tfileoutputdelimited(node, component)
```

**Then expand** `parse_tfileoutputdelimited()` in `component_parser.py` to extract all missing parameters:
```python
def parse_tfileoutputdelimited(self, node, component: Dict) -> Dict:
    """Parse tFileOutputDelimited specific configuration"""
    config = component['config']

    # Basic settings
    config['filepath'] = self._get_param_value(node, 'FILENAME', '')
    config['delimiter'] = self._get_param_value(node, 'FIELDSEPARATOR', ';')
    config['row_separator'] = self._get_param_value(node, 'ROWSEPARATOR', '\\n')
    config['include_header'] = self._get_bool_param(node, 'INCLUDEHEADER', False)
    config['append'] = self._get_bool_param(node, 'APPEND', False)
    config['compress'] = self._get_bool_param(node, 'COMPRESS', False)
    config['encoding'] = self._get_param_value(node, 'ENCODING', 'ISO-8859-15')
    config['die_on_error'] = self._get_bool_param(node, 'DIE_ON_ERROR', False)

    # CSV options
    config['csv_option'] = self._get_bool_param(node, 'CSV_OPTION', False)
    if config['csv_option']:
        config['escape_char'] = self._get_param_value(node, 'ESCAPE_CHAR', '\\\\')
        config['text_enclosure'] = self._get_param_value(node, 'TEXT_ENCLOSURE', '"')
        config['csv_row_separator'] = self._get_param_value(node, 'CSVROWSEPARATOR', '')
    else:
        config['text_enclosure'] = None

    # Advanced settings
    config['create_directory'] = self._get_bool_param(node, 'CREATE', True)
    config['split'] = self._get_bool_param(node, 'SPLIT', False)
    config['split_every'] = self._safe_int(self._get_param_value(node, 'SPLIT_EVERY', '1000'))
    config['flush_on_row'] = self._get_bool_param(node, 'FLUSHONROW', False)
    config['flush_row_count'] = self._safe_int(self._get_param_value(node, 'FLUSHONROW_NUM', '1'))
    config['row_mode'] = self._get_bool_param(node, 'ROW_MODE', False)
    config['delete_empty_file'] = self._get_bool_param(node, 'DELETE_EMPTYFILE', False)
    config['file_exist_exception'] = self._get_bool_param(node, 'FILE_EXIST_EXCEPTION', False)

    # Advanced separator
    config['advanced_separator'] = self._get_bool_param(node, 'ADVANCED_SEPARATOR', False)
    if config['advanced_separator']:
        config['thousands_separator'] = self._get_param_value(node, 'THOUSANDS_SEPARATOR', ',')
        config['decimal_separator'] = self._get_param_value(node, 'DECIMAL_SEPARATOR', '.')

    # Input connections
    component['inputs'] = [
        input_flow.get('name')
        for input_flow in node.findall('.//connection[@connectorName="FLOW"]')
    ]

    return component
```

**Impact**: Full parameter extraction, replaces `_map_component_parameters()` path (non-compliant with STANDARDS.md). **Risk**: Medium (must verify no regressions in existing converted jobs).

---

## Appendix H: Detailed Code Analysis

### `_validate_config()` (Lines 77-122)

This method validates:
- `filepath` is present and non-empty (required)
- `delimiter` is a string (if present)
- `encoding` is a string (if present)
- `include_header` is boolean (if present)
- `append` is boolean (if present)
- `create_directory` is boolean (if present)
- `die_on_error` is boolean (if present)
- `output_schema` is a list (if present)

**Not validated**: `text_enclosure`, `escape_char`, `row_separator`, `delete_empty_file`, `compress`, `split`, `flush_on_row`, `row_mode`, `file_exist_exception`.

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions.

### `_process()` (Lines 124-257)

The main processing method:
1. Extract config values with defaults and type conversion
2. Validate filepath (raises/returns empty on missing)
3. Log start of writing operation
4. Check for streaming input (Iterator) -- delegate to `_write_streaming()`
5. Check for list input -- convert to DataFrame (has scoping bug)
6. Log input data details
7. Handle empty data -- delegate to `_handle_empty_data()`
8. Create directory if needed
9. Normalize delimiter
10. Apply output schema filtering
11. Determine write mode (append vs overwrite) and header behavior
12. Configure quoting
13. Special case: empty delimiter -> `_write_single_column()`
14. Standard case: `pd.DataFrame.to_csv()`
15. Update stats and return
16. Catch-all exception handler with `die_on_error` support

### `_handle_empty_data()` (Lines 259-307)

Empty data handling:
1. Normalize delimiter and row separator (manual, not using `_normalize_delimiter()`)
2. Determine write mode (append vs overwrite)
3. Get output schema columns from various sources
4. If `include_header=True` and schema available: write header-only file
5. If `delete_empty_file=True` and no header written and file exists: delete file
6. Update stats to (0, 0, 0) and return

### `_write_streaming()` (Lines 309-383)

Streaming write mode:
1. Create directory if needed
2. Normalize delimiter
3. Iterate over data chunks
4. First chunk: determine write mode and header
5. Subsequent chunks: append mode, no header
6. Configure quoting per chunk (should be once)
7. Write each chunk with `to_csv()`
8. Accumulate stats per chunk
9. Handle empty result (delete_empty_file is no-op -- commented out)
10. Catch-all exception handler with `die_on_error` support

### `_ensure_directory_exists()` (Lines 385-394)

Creates parent directories with `os.makedirs(exist_ok=True)`. Raises `FileOperationError` on failure.

### `_normalize_delimiter()` (Lines 396-402)

Handles three cases:
1. `"\\t"` or `"\t"` -> actual tab character
2. Multi-char (length > 1) -> raw f-string format `rf"{delimiter}"`
3. Single char -> return as-is

**Note**: The multi-char case wraps the delimiter in a raw f-string, which for `to_csv()` is passed as the `sep` parameter. pandas `to_csv()` accepts multi-character separators directly, so this raw-string wrapping is unnecessary and could introduce subtle issues if the delimiter contains special regex characters.

### `_configure_quoting()` (Lines 404-417)

Handles two quoting modes:
1. `text_enclosure=None` -> `csv.QUOTE_NONE` (disables quoting entirely)
2. `text_enclosure` is set -> `csv.QUOTE_MINIMAL` (quote when needed)

**Missing**: Does not handle doublequote mode (when escape_char == text_enclosure, which triggers `doublequote=True` in pandas). The `doublequote` parameter is never set.

### `_apply_output_schema()` (Lines 419-438)

Filters DataFrame columns based on output schema:
1. Checks `config['output_schema']` first
2. Falls back to `self.output_schema` attribute
3. Falls back to `self.schema['output']` attribute
4. Filters to available columns only (silently drops missing columns)
5. Only applies if available columns differ from current columns

### `_get_output_schema_columns()` (Lines 440-454)

Returns column names from the same three sources as `_apply_output_schema()`, but only returns the name list (not filtered by DataFrame columns). Used by `_handle_empty_data()` for header generation.

### `_write_single_column()` (Lines 456-471)

Special-case writer for empty delimiter:
1. Gets row_separator from config
2. Opens file and writes each value from the first column
3. Each value followed by row_separator
4. Uses `df.iloc[:, 0]` -- first column only, ignoring others

**Note**: No warning is logged if the DataFrame has multiple columns, which would silently drop data.

---

## Appendix I: Talend Generated Java Code Pattern

For reference, the Talend-generated Java code for `tFileOutputDelimited` follows this pattern:

```java
// Open file (simplified)
java.io.Writer outtFileOutputDelimited_1 = null;
outtFileOutputDelimited_1 = new java.io.BufferedWriter(
    new java.io.OutputStreamWriter(
        new java.io.FileOutputStream(fileName, appendMode),
        encoding
    )
);

// Write header (if configured)
if (includeHeader) {
    StringBuilder sb = new StringBuilder();
    sb.append("col1").append(fieldSeparator);
    sb.append("col2").append(fieldSeparator);
    sb.append("col3");
    sb.append(rowSeparator);
    outtFileOutputDelimited_1.write(sb.toString());
}

// Main loop - write each row
// (inside the main data flow loop)
StringBuilder sb_tFileOutputDelimited_1 = new StringBuilder();
if (row1.col1 != null) {
    sb_tFileOutputDelimited_1.append(row1.col1);
}
sb_tFileOutputDelimited_1.append(fieldSeparator);
if (row1.col2 != null) {
    sb_tFileOutputDelimited_1.append(row1.col2);
}
sb_tFileOutputDelimited_1.append(fieldSeparator);
if (row1.col3 != null) {
    sb_tFileOutputDelimited_1.append(row1.col3);
}
sb_tFileOutputDelimited_1.append(rowSeparator);
outtFileOutputDelimited_1.write(sb_tFileOutputDelimited_1.toString());
nb_line_tFileOutputDelimited_1++;

// After loop - store stats
globalMap.put("tFileOutputDelimited_1_NB_LINE", nb_line_tFileOutputDelimited_1);
```

Key observations from the generated code:
1. **Row-by-row writing**: Each row is formatted and written individually through the main loop
2. **StringBuilder usage**: Efficient string concatenation for row formatting
3. **Null handling**: Null values result in empty strings (no "null" text written)
4. **Row separator after every row**: Including the last row (trailing newline)
5. **BufferedWriter**: Standard Java buffered I/O for performance
6. **NB_LINE increment**: Counter incremented per row, stored in globalMap after loop

This differs from the V1 pandas approach where `to_csv()` writes the entire DataFrame at once. The behavioral differences include:
- Talend can flush buffer mid-write; pandas writes all at once (in batch mode)
- Talend explicitly controls row separator per row; pandas uses `lineterminator`
- Talend null handling produces empty strings; pandas NaN representation depends on `na_rep` parameter

---

## Appendix J: Default Value Comparison

| Parameter | Talend Default | V1 Converter Default | V1 Engine Default | Match? |
|-----------|---------------|---------------------|-------------------|--------|
| FIELDSEPARATOR | `";"` | `","` | `","` | **MISMATCH** |
| ROWSEPARATOR | `"\n"` | `"\n"` | `"\n"` | Match |
| ENCODING | `"ISO-8859-15"` | `"UTF-8"` | `"UTF-8"` | **MISMATCH** |
| INCLUDEHEADER | `false` | `True` | `True` | **MISMATCH** |
| APPEND | `false` | `False` | `False` | Match |
| COMPRESS | `false` | Not extracted | Not implemented | N/A |
| CSV_OPTION | `false` | `False` | Not read | Match (converter) |
| ESCAPE_CHAR | `"\\"` | Not extracted | `"\\"` (hardcoded) | Match (coincidental) |
| TEXT_ENCLOSURE | `"\""` | `None` (when CSV off) | `None` (default) | Match (when CSV off) |
| CREATE | `true` | `True` | N/A (uses config) | Match |
| DELETE_EMPTYFILE | `false` | `True` | N/A (uses config) | **MISMATCH** |
| SPLIT | `false` | Not extracted | Not implemented | N/A |
| FLUSHONROW | `false` | Not extracted | Not implemented | N/A |
| ROW_MODE | `false` | Not extracted | Not implemented | N/A |
| FILE_EXIST_EXCEPTION | `false` | Not extracted | Not implemented | N/A |
| DIE_ON_ERROR | `false` | `False` | `True` | **MISMATCH** (engine default differs) |

**Critical mismatches**: 5 parameters have mismatched defaults between Talend and the V1 converter/engine. These can cause silent behavioral differences when converting Talend jobs that rely on default values.

The `die_on_error` default is particularly notable: the converter defaults to `False` (matching Talend), but the engine's `_process()` method has `die_on_error = self.config.get('die_on_error', True)` (line 148), defaulting to `True`. If the converter does not explicitly set `die_on_error=False` in the config, the engine will default to `True`, which is stricter than Talend's default behavior. However, since the converter DOES set this explicitly (line 145), this only matters if the config key is missing for some other reason.

---

## Appendix K: Detailed Method-by-Method Code Review

### `_process()` -- Control Flow Analysis

The `_process()` method has 8 distinct exit paths:

| # | Condition | Exit Type | Return Value | Stats Updated? |
|---|-----------|-----------|-------------|----------------|
| 1 | `not filepath` + `die_on_error=True` | Raise `ConfigurationError` | N/A | Yes (0,0,0) -- **but raise happens before return** |
| 2 | `not filepath` + `die_on_error=False` | Return | `{'main': pd.DataFrame()}` | Yes (0,0,0) |
| 3 | `isinstance(input_data, Iterator)` | Delegate | `_write_streaming()` result | Delegated |
| 4 | `isinstance(input_data, list)` + conversion fails + `die_on_error=True` | Raise `FileOperationError` | N/A | **No** -- see BUG-FOD-003 |
| 5 | `isinstance(input_data, list)` + conversion fails + `die_on_error=False` | Return | `{'main': pd.DataFrame()}` | **Incorrect** -- uses `len(input_data)` which may be the failed list |
| 6 | `input_data is None or empty` | Delegate | `_handle_empty_data()` result | Delegated |
| 7 | Normal write succeeds | Return | `{'main': input_data}` | Yes (rows_in, rows_in, 0) |
| 8 | Normal write fails + `die_on_error=True` | Raise `FileOperationError` | N/A | No |
| 9 | Normal write fails + `die_on_error=False` | Return | `{'main': pd.DataFrame()}` | Yes (rows_in, 0, rows_in) |

**Exit path 1 analysis**: When `die_on_error=True` and filepath is empty, `_update_stats(0,0,0)` is called (line 156) and then `ConfigurationError` is raised (line 154). The stats update is correct because the base class `execute()` (line 218) calls `_update_global_map()` even on exception (via the except block on line 227-234). However, the `_update_stats()` call is technically redundant since no rows were processed.

**Exit path 4/5 analysis (BUG-FOD-003)**: The control flow is broken. After the `except` block ends, execution continues to the `if die_on_error:` check which is OUTSIDE the except block. Variables `error_msg` and `e` from the except scope may not be accessible depending on Python version and error occurrence.

**Exit path 7 analysis**: The return value `{'main': input_data}` passes through the ORIGINAL input DataFrame (potentially modified by `_apply_output_schema()`). This is correct for flow continuation -- downstream components receive the same data that was written to the file. However, if `_apply_output_schema()` dropped columns, the downstream component receives the reduced DataFrame, which may or may not be the intended behavior.

### `_handle_empty_data()` -- Detailed Analysis

This method handles the case where no data rows flow to the component. The logic is:

```
IF include_header AND output_schema:
    Write header-only file
ELIF delete_empty_file AND (NOT include_header OR NOT output_schema) AND file exists:
    Delete existing file
ELSE:
    Do nothing (no file created, no file deleted)
```

**Potential issue**: The condition `os.path.exists(filepath)` on line 299 means the file is only deleted if it already exists from a previous run. If the file does not exist and `delete_empty_file=True`, no action is taken. This matches Talend behavior (don't generate = don't create), but the name `delete_empty_file` implies deletion rather than non-creation.

**Potential issue**: When `include_header=True` but `output_schema` is empty, no header is written. This can happen if the schema is not properly propagated from the upstream component. In Talend, the schema is always available from the component definition. In V1, the schema may be missing if the converter did not extract it properly.

**Potential issue**: The `_handle_empty_data()` method does NOT respect `die_on_error` for the header write failure case. Line 296 raises `FileOperationError` unconditionally on failure. If `die_on_error=False`, the method should catch the error and return gracefully.

### `_write_streaming()` -- Detailed Analysis

Streaming mode is activated when the input is an Iterator (line 165). The method:

1. Creates directory if needed
2. Normalizes delimiter (once, before loop)
3. Iterates over chunks from the data iterator
4. First non-empty chunk: determines write mode and header
5. Subsequent chunks: append mode, no header
6. Each chunk written with `to_csv()`
7. Stats accumulated per chunk

**Potential issue -- header race condition**: If the first chunk is empty (skipped by line 329), `first_chunk` remains `True`. The next non-empty chunk becomes the "first" chunk and gets the header. This is correct behavior, but if ALL chunks are empty, `first_chunk` remains `True` and the `total_rows == 0` path is taken (line 366). In this case, `delete_empty_file` would theoretically apply, but the deletion is commented out.

**Potential issue -- row_separator not applied**: Like the batch path, `to_csv()` in streaming mode (line 346) does not pass `lineterminator`, so `'\n'` is always used. Custom row separators are ignored.

**Potential issue -- stats accumulation**: `_update_stats(chunk_rows, chunk_rows, 0)` on line 361 accumulates stats per chunk. Since `_update_stats()` uses `+=` (line 308 of base_component.py), the final `NB_LINE` correctly reflects the total. However, `_update_global_map()` is called once after `execute()` completes (line 218), so intermediate stats are not visible to globalMap during writing. This matches Talend behavior (NB_LINE only available after completion).

### `_normalize_delimiter()` -- Edge Cases

| Input | Output | Correct? |
|-------|--------|----------|
| `"\\t"` | `"\t"` | Yes |
| `"\t"` | `"\t"` | Yes |
| `";"` | `";"` | Yes |
| `","` | `","` | Yes |
| `"|"` | `"|"` | Yes |
| `"||"` | `rf"||"` (raw string) | Questionable -- raw f-string on `||` produces `||` which is correct for `to_csv()`. But `rf"{delimiter}"` is a no-op for non-escape strings. |
| `""` | `""` | Yes (triggers `_write_single_column`) |
| `"\\n"` | `rf"\\n"` | **Incorrect** -- `\\n` as delimiter would produce `rf"\\n"` which is literal `\n` characters, not a newline. Unusual edge case. |

### `_configure_quoting()` -- Missing doublequote Mode

Talend supports three quoting behaviors:
1. No quoting (CSV_OPTION off, or no text enclosure)
2. Standard quoting with escape char (e.g., `\"` inside quoted fields)
3. Doublequote mode (escape char == text enclosure, e.g., `""` inside quoted fields)

The engine only handles cases 1 and 2 (partially, since escape char is hardcoded). Case 3 (doublequote mode) is not implemented. In pandas, this would be `doublequote=True` parameter.

For comparison, the `FileInputDelimited` engine's `_configure_csv_params()` DOES handle doublequote mode (when `escape_char == text_enclosure`, it sets `doublequote=True`). The output component should have matching logic.

### `_apply_output_schema()` -- Schema Source Priority

The method checks three schema sources in order:
1. `self.config.get('output_schema')` -- direct config list of column names
2. `self.output_schema` -- component attribute (list of dicts with `name` key)
3. `self.schema['output']` -- schema dict attribute (list of dicts with `name` key)

**Potential issue**: If none of these sources are available, the DataFrame is returned unmodified with ALL columns. This is correct for the "no schema" case, but may write unexpected columns if the schema was supposed to filter them.

**Potential issue**: The `available_cols` check (line 432) only includes columns that exist in BOTH the schema AND the DataFrame. If a schema column is missing from the DataFrame, it is silently dropped. No warning is logged for missing schema columns. This can hide data pipeline issues where an upstream transformation dropped a column.

### `_write_single_column()` -- Data Loss Risk

This method writes only `df.iloc[:, 0]` (first column) to the file. If the DataFrame has multiple columns and the delimiter is empty (triggering this path), all columns except the first are silently lost.

**Recommendation**: Log a warning when `len(df.columns) > 1` and the single-column path is triggered. This alerts operators to potential data loss.

---

## Appendix L: Comparison with FileInputDelimited Engine

| Feature | FileInputDelimited (472-line audit) | FileOutputDelimited (this audit) |
|---------|--------------------------------------|----------------------------------|
| Core operation | Read CSV -> DataFrame | DataFrame -> Write CSV |
| Pandas function | `pd.read_csv()` | `pd.DataFrame.to_csv()` |
| Dead `_validate_config()` | Yes (BUG-FID-004) | Yes (BUG-FOD-004) |
| `_update_global_map()` bug | Yes (BUG-FID-001) | Yes (BUG-FOD-001) -- same cross-cutting bug |
| `GlobalMap.get()` bug | Yes (BUG-FID-002) | Yes (BUG-FOD-002) -- same cross-cutting bug |
| REJECT flow | Not implemented | N/A (output components don't have REJECT) |
| Streaming mode | Yes (generator-based chunked reading) | Yes (chunked writing from Iterator) |
| Row separator handling | Passed to `pd.read_csv()` via `sep` parameter | **NOT passed to `to_csv()`** -- major gap |
| Encoding default | `UTF-8` (mismatch) | `UTF-8` (mismatch) |
| Delimiter default | `,` (mismatch) | `,` (mismatch) |
| Test coverage (V1) | Zero tests | Zero tests |
| Converter parser | `_map_component_parameters()` (non-compliant with STANDARDS.md) | `_map_component_parameters()` (non-compliant with STANDARDS.md) + dormant dedicated parser |
| Parameters extracted | 12 of 30 (40%) | 11 of 29 (38%) |

Both components share the same cross-cutting bugs and structural issues (dead validation, non-compliant converter approach, encoding/delimiter default mismatches, zero V1 tests). Fixes to the cross-cutting issues should be applied once and will benefit both components.

---

## Appendix M: Risk Assessment for Production Deployment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cross-cutting `_update_global_map()` crash | **High** (triggers on every execution with globalMap) | **Critical** (all components fail) | Fix BUG-FOD-001 immediately |
| Cross-cutting `GlobalMap.get()` crash | **High** (triggers on any get call) | **Critical** (globalMap unusable) | Fix BUG-FOD-002 immediately |
| List input causes crash | **Medium** (depends on upstream component output type) | **High** (component crash) | Fix BUG-FOD-003 |
| Wrong row separator in output | **Medium** (Windows-origin jobs) | **Medium** (corrupted output format) | Fix ENG-FOD-001 |
| Wrong delimiter default | **High** (any job relying on Talend defaults) | **Medium** (wrong file format) | Fix CONV-FOD-007 |
| Wrong encoding default | **High** (any job relying on Talend defaults) | **Medium** (mojibake) | Fix CONV-FOD-006 |
| Wrong include_header default | **High** (any job relying on Talend defaults) | **Low** (extra or missing header) | Fix CONV-FOD-004 |
| Missing COMPRESS support | **Low** (few jobs use ZIP output) | **Medium** (uncompressed output) | Implement when needed |
| Missing SPLIT support | **Low** (few jobs split output) | **Low** (single large file) | Implement when needed |
| No V1 tests | **N/A** (certainty) | **High** (no regression detection) | Create test suite (TEST-FOD-001) |

**Overall deployment risk**: **HIGH** due to the cross-cutting P0 bugs that will crash any component execution when globalMap is configured. These must be fixed before any V1 engine deployment, regardless of which components are used.
