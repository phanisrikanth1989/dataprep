# Audit Report: tFileInputExcel / FileInputExcel

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputExcel` |
| **V1 Engine Class** | `FileInputExcel` |
| **Engine File** | `src/v1/engine/components/file/file_input_excel.py` (1023 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_file_input_excel()` (lines 2850-2986) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> line 250 (`elif component_type == 'tFileInputExcel'`) |
| **Registry Aliases** | `FileInputExcel`, `tFileInputExcel` (registered in `src/v1/engine/engine.py` lines 91-92) |
| **Category** | File / Input |
| **Complexity** | High -- dual engine (.xls via xlrd / .xlsx via openpyxl), password support, multi-sheet with regex matching, advanced separators, date conversion, column-level trimming, streaming mode |
| **Lines of Code** | 1023 (engine), 136 (converter parser) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_excel.py` | Engine implementation (1023 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2850-2986) | Dedicated `parse_file_input_excel()` method: parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 250-251) | Dispatch: `elif component_type == 'tFileInputExcel'` calls `parse_file_input_excel()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`, `ComponentExecutionError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (`FileInputExcel` on line 22, `__all__` on line 42) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 1 | 2 | 2 | 28 of 33 Talend params extracted (85%); dedicated `parse_file_input_excel()` with table params; `AFFECT_EACH_SHEET` parsed but not implemented; `filename` key collision bug |
| Engine Feature Parity | **Y** | 2 | 5 | 4 | 2 | Three dead-code methods never called; password decryption not implemented; no REJECT flow; no CURRENT_SHEET globalMap; die_on_error defaults False unlike Talend |
| Code Quality | **Y** | 2 | 4 | 7 | 4 | Cross-cutting base class bugs; 3 dead methods (~95 lines); partial match logic in sheet selection; duplicated code in _read_sheet/_read_xls_sheet; non-standard streaming return signature; unused file_size_mb computation |
| Performance & Memory | **G** | 0 | 1 | 2 | 1 | Streaming mode works; batch/streaming auto-detection; usecols optimization; minor duplication overhead |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputExcel Does

`tFileInputExcel` reads Microsoft Excel files (.xls and .xlsx) row by row, splitting them into fields based on cell positions, and outputs the data as a structured flow. It supports both legacy Excel 97-2003 (.xls) format and modern Office Open XML (.xlsx/.xlsm) format. The component handles password-protected workbooks, multi-sheet reading with regex-based sheet selection, advanced number formatting with locale-aware separators, column-level trimming, date-to-string conversion, and two generation modes (User mode for smaller files, Event mode for large files with lower memory consumption). It is a commonly used Talend component for ingesting spreadsheet data into ETL pipelines.

The component requires external JAR files (Apache POI) due to license incompatibility, which must be installed via Talend Studio's module interface. In the v1 Python engine, openpyxl replaces Apache POI for .xlsx files and xlrd replaces it for .xls files.

**Source**: [tFileInputExcel Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/excel/tfileinputexcel-standard-properties), [tFileInputExcel Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/excel/tfileinputexcel-standard-properties), [tFileInputExcel ESB 6.x (TalendSkill)](https://talendskill.com/talend-for-esb-docs/docs-6-x/tfileinputexcel-docs-for-esb-6-x/)

**Component family**: Excel (File / Input)
**Available in**: All Talend products (Standard). Also available in Spark Batch variant.
**Required JARs**: Apache POI (`poi-*.jar`, `poi-ooxml-*.jar`, `xmlbeans-*.jar`, etc.)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. |
| 3 | File Name / Stream | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path or data stream variable. Supports context variables, globalMap references, Java expressions. |
| 4 | Read Excel 2007 | `VERSION_2007` | Boolean (CHECK) | `true` | When checked, reads .xlsx/.xlsm format using SAX/DOM parser; when unchecked, reads legacy .xls format using HSSF. Determines which Apache POI API to use internally. |
| 5 | Password | `PASSWORD` | String (password field) | `""` | Password for opening protected workbooks. Supports "standard encryption and agile encryption" for .xlsx files. Entered in double quotation marks. |
| 6 | All Sheets | `ALL_SHEETS` | Boolean (CHECK) | `false` | When true, reads all sheets in the workbook. When false, reads only sheets specified in the Sheet List. |
| 7 | Sheet List | `SHEETLIST` | Table (SHEETNAME, USE_REGEX) | -- | Table with two columns: `SHEETNAME` (string -- sheet name or regex pattern) and `USE_REGEX` (boolean -- whether to interpret SHEETNAME as a regular expression). When `ALL_SHEETS=false`, only the first matching sheet is read. When `ALL_SHEETS=true`, all matching sheets are read. |
| 8 | Header | `HEADER` | Integer | `0` | Number of rows to skip at the beginning of each sheet. These rows are completely discarded -- NOT used for column naming (schema defines column names). In Talend, setting Header=1 means "skip 1 row" (typically the header row). |
| 9 | Footer | `FOOTER` | Integer | `0` | Number of rows to skip at the end of each sheet. |
| 10 | Limit | `LIMIT` | Integer | `0` (unlimited) | Maximum number of data rows to read per sheet. `0` or empty = unlimited. |
| 11 | Affect Each Sheet | `AFFECT_EACH_SHEET` | Boolean (CHECK) | `false` | When true, applies Header and Footer settings to each sheet individually. When false, Header/Footer only apply to the first sheet. |
| 12 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Stop the entire job on error. When unchecked, errors are logged and processing continues (bad rows can be routed to REJECT). **Note**: Talend default is `true` (checked). |
| 13 | First Column | `FIRST_COLUMN` | Integer | `1` | First column to read (1-based). Allows skipping leading columns. |
| 14 | Last Column | `LAST_COLUMN` | Integer / String | `""` (all) | Last column to read. Can be a column number (1-based) or column letter (A, B, ..., AA, etc.). Empty = read to the last column with data. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 15 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable custom locale-aware number separators for parsing numeric data from cells. |
| 16 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator character. Only visible when `ADVANCED_SEPARATOR=true`. Used for parsing numbers like `1,234,567`. |
| 17 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator character. Only visible when `ADVANCED_SEPARATOR=true`. Used for parsing numbers like `1234,56` (European format). |
| 18 | Trim All Columns | `TRIMALL` | Boolean (CHECK) | `false` | Remove leading and trailing whitespace from ALL string fields in every column. |
| 19 | Check Columns to Trim | `TRIMSELECT` | Table (SCHEMA_COLUMN, TRIM) | -- | Per-column trim configuration. Auto-populated from schema. Each row maps a schema column name to a boolean trim flag. Allows selective trimming when `TRIMALL` is unchecked. |
| 20 | Convert Date Column to String | `CONVERTDATETOSTRING` | Boolean (CHECK) | `false` | Enable date-to-string conversion for specific columns. When checked, the `DATESELECT` table becomes active. |
| 21 | Date Select | `DATESELECT` | Table (SCHEMA_COLUMN, CONVERTDATE, PATTERN) | -- | Per-column date conversion settings. Each row maps a column name to a boolean conversion flag and a date pattern (e.g., `"MM-dd-yyyy"`). Only active when `CONVERTDATETOSTRING=true`. Default pattern is `dd-MM-yyyy`. |
| 22 | Encoding | `ENCODING` | Dropdown / Custom | `"UTF-8"` | Character encoding for reading the file. Note: this is primarily relevant for .xls files (HSSF). For .xlsx files, encoding is embedded in the XML structure. |
| 23 | Read Real Values | `READ_REAL_VALUE` | Boolean (CHECK) | `false` | When true, extracts the underlying numeric value from cells instead of the formatted display value. |
| 24 | Stop Read on Empty Row | `STOPREAD_ON_EMPTYROW` | Boolean (CHECK) | `false` | When true, stops reading a sheet when an empty row is encountered. All subsequent rows (even non-empty ones) are ignored. |
| 25 | Generation Mode | `GENERATION_MODE` | Dropdown | `EVENT_MODE` | Controls the Excel parser mode. `EVENT_MODE` (Event mode): SAX-based streaming parser, lower memory consumption, recommended for large files. `USER_MODE` (User mode): DOM-based parser, loads entire sheet into memory, required for some formula evaluation scenarios. Only visible when `VERSION_2007=true`. |
| 26 | Don't Validate Cells | `NOVALIDATE_ON_CELL` | Boolean (CHECK) | `false` | Skip data validation checks on Excel cells. |
| 27 | Suppress Warning | `SUPPRESS_WARN` | Boolean (CHECK) | `false` | Suppress Excel file parsing warnings (e.g., formula evaluation warnings). |
| 28 | Configure Inflation Ratio | `CONFIGURE_INFLATION_RATIO` | Boolean (CHECK) | `false` | Enable configuration of the inflation ratio for Event mode memory allocation. |
| 29 | Inflation Ratio | `INFLATION_RATIO` | Float | -- | Memory inflation ratio multiplier. Only visible when `CONFIGURE_INFLATION_RATIO=true`. |
| 30 | Include Phonetic Runs | `INCLUDE_PHONETICRUNS` | Boolean (CHECK) | `true` | Include phonetic annotation data from cells (used in East Asian locales). |
| 31 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher component. |
| 32 | Label | `LABEL` | String | -- | Text label for component display in Talend Studio. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully parsed rows matching the output schema. All columns defined in the schema are present. Primary data output. |
| `REJECT` | Output | Row > Reject | Rows that failed parsing, type conversion, or structural validation. Includes ALL original schema columns PLUS `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false`. |
| `ITERATE` | Output | Iterate | Enables iterative processing when used with iteration components like `tFlowToIterate`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows read from all sheets (data rows, after header skip). Primary row count variable. |
| `{id}_CURRENT_SHEET` | String | During flow | Name of the sheet currently being read. Available during row-level processing via globalMap. Unique to tFileInputExcel -- not present in tFileInputDelimited. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message when an error occurs during execution. Available for downstream error handling. |

**Note on NB_LINE**: Unlike some components, `NB_LINE` for tFileInputExcel represents the TOTAL across ALL sheets read in a single execution. If reading 3 sheets with 100 rows each, `NB_LINE = 300`.

**Note on CURRENT_SHEET**: This variable is set before processing each sheet and can be referenced in downstream components to know which sheet a given row came from. This is critical for multi-sheet processing pipelines.

### 3.5 Behavioral Notes

1. **HEADER behavior**: When `HEADER > 0`, Talend skips that many rows at the TOP of each sheet, then uses the SCHEMA column names -- NOT the file header row. The header rows are completely discarded and never used for column naming.

2. **AFFECT_EACH_SHEET behavior**: When `AFFECT_EACH_SHEET=true`, the HEADER and FOOTER settings are applied independently to each sheet. When false, they are only applied to the first sheet. This matters when reading multiple sheets with different header/footer structures.

3. **REJECT flow behavior**: When a REJECT link is connected and `DIE_ON_ERROR=false`:
   - Rows that fail type conversion or validation are sent to REJECT
   - REJECT rows contain ALL original schema columns PLUS `errorCode` (String) and `errorMessage` (String) columns
   - When REJECT is NOT connected, errors are silently dropped or cause job failure depending on `DIE_ON_ERROR`

4. **ALL_SHEETS vs SHEETLIST interaction**:
   - `ALL_SHEETS=true` + empty SHEETLIST: Read every sheet in the workbook
   - `ALL_SHEETS=true` + non-empty SHEETLIST: Read sheets matching the SHEETLIST filter (name or regex)
   - `ALL_SHEETS=false` + SHEETLIST: Read only the FIRST matching sheet from SHEETLIST
   - `ALL_SHEETS=false` + empty SHEETLIST: Read the first sheet in the workbook

5. **USE_REGEX in SHEETLIST**: When `USE_REGEX=true` for a SHEETLIST entry, the SHEETNAME is interpreted as a Java regular expression and matched against all available sheet names. This enables patterns like `"Data_\d{4}"` to match `Data_2023`, `Data_2024`, etc.

6. **PASSWORD handling**: Talend uses Apache POI's encryption support. Standard encryption (RC4) is used for .xls files. Agile encryption (AES) is used for .xlsx files. The password field supports context variables for externalized credential management. Talend also supports encrypted passwords via its `enc:system.encryption.key.v1:` prefix.

7. **FIRST_COLUMN / LAST_COLUMN**: These define the horizontal read range. Columns outside this range are completely ignored. `FIRST_COLUMN=1` means start from column A. `LAST_COLUMN` can be a number (e.g., `5`) or a letter (e.g., `E`). When empty, reads to the last column with data.

8. **GENERATION_MODE**: Event mode (SAX-based) is the default for .xlsx files and consumes significantly less memory for large files. User mode (DOM-based) loads the entire sheet into memory and is needed for formula evaluation and certain cell formatting operations. This setting is only relevant for .xlsx files.

9. **STOPREAD_ON_EMPTYROW**: When enabled, the component stops reading a sheet as soon as it encounters a completely empty row. This is useful for sheets where data is followed by formatting or notes, but dangerous if data has intentional blank rows in the middle.

10. **Default DIE_ON_ERROR**: Talend defaults `DIE_ON_ERROR` to `true` (checked) for tFileInputExcel. This is important: unlike tFileInputDelimited where the default is `false`, tFileInputExcel defaults to failing the job on errors.

11. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow.

12. **.xls vs .xlsx differences**: Talend uses HSSF (from Apache POI) for .xls files and XSSF/SAX (from Apache POI) for .xlsx files. The `VERSION_2007` flag controls which API is used. Password handling differs between the two formats. Generation mode (Event/User) only applies to .xlsx.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated `parse_file_input_excel()` method** (lines 2850-2986 of `component_parser.py`), dispatched from `converter.py` line 250-251 via `elif component_type == 'tFileInputExcel'`. This is the correct approach per STANDARDS.md -- unlike `tFileInputDelimited` which uses the deprecated generic mapper.

The parser is comprehensive, handling simple parameters, boolean conversions, integer conversions, and complex table parameters (SHEETLIST, TRIMSELECT, DATESELECT) with nested `elementValue` groups.

**Converter flow**:
1. `converter.py:_parse_component()` matches `tFileInputExcel` on line 250
2. Calls `self.component_parser.parse_file_input_excel(node, component)` on line 251
3. `parse_file_input_excel()` extracts all parameters using helper functions (`get_param`, `str_to_bool`, `str_to_int`)
4. Table parameters (SHEETLIST, TRIMSELECT, DATESELECT) are parsed via nested `elementValue` iteration
5. Schema is extracted generically from `<metadata connector="FLOW">` nodes

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | 2875 | Direct string extraction via `get_param()` |
| 2 | `PASSWORD` | Yes | `password` | 2876 | Direct string extraction. **No decryption of `enc:` prefix passwords.** |
| 3 | `VERSION_2007` | Yes | `version_2007` | 2879 | Boolean conversion. Default `true`. Engine ignores this -- detects format from file extension instead. |
| 4 | `ALL_SHEETS` | Yes | `all_sheets` | 2880 | Boolean conversion. Default `false` -- matches Talend. |
| 5 | `SHEETLIST` | Yes | `sheetlist` | 2883-2897 | **Table parameter correctly parsed**: iterates `elementValue` children, extracts `SHEETNAME` and `USE_REGEX`. |
| 6 | `HEADER` | Yes | `header` | 2900 | Integer conversion via `str_to_int()`. Default `1`. **Differs from Talend default `0`.** |
| 7 | `FOOTER` | Yes | `footer` | 2901 | Integer conversion. Default `0` -- matches Talend. |
| 8 | `LIMIT` | Yes | `limit` | 2902 | Raw string extraction. Empty string = no limit. Engine handles int conversion. |
| 9 | `AFFECT_EACH_SHEET` | Yes | `affect_each_sheet` | 2903 | Boolean conversion. **Extracted but engine never uses it.** |
| 10 | `FIRST_COLUMN` | Yes | `first_column` | 2904 | Integer conversion. Default `1` -- matches Talend. |
| 11 | `LAST_COLUMN` | Yes | `last_column` | 2905 | Raw string extraction. Supports both numeric and alphabetic values. |
| 12 | `DIE_ON_ERROR` | Yes | `die_on_error` | 2908 | Boolean conversion. **Default `false` -- differs from Talend default `true`.** |
| 13 | `SUPPRESS_WARN` | Yes | `suppress_warn` | 2909 | Boolean conversion. Default `false` -- matches Talend. |
| 14 | `NOVALIDATE_ON_CELL` | Yes | `novalidate_on_cell` | 2910 | Boolean conversion. **Extracted but engine never uses it.** |
| 15 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | 2913 | Boolean conversion. Default `false` -- matches Talend. |
| 16 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | 2914-2917 | String extraction with quote stripping. Default `","`. |
| 17 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | 2915-2918 | String extraction with quote stripping. Default `"."`. |
| 18 | `TRIMALL` | Yes | `trimall` | 2921 | Boolean conversion. Default `false` -- matches Talend. |
| 19 | `TRIMSELECT` | Yes | `trim_select` | 2924-2938 | **Table parameter correctly parsed**: `SCHEMA_COLUMN` -> `column`, `TRIM` -> `trim`. |
| 20 | `CONVERTDATETOSTRING` | Yes | `convertdatetostring` | 2941 | Boolean conversion. Default `false` -- matches Talend. |
| 21 | `DATESELECT` | Yes | `date_select` | 2944-2960 | **Table parameter correctly parsed**: `SCHEMA_COLUMN` -> `column`, `CONVERTDATE` -> `convert_date`, `PATTERN` -> `pattern`. Pattern has quote stripping. |
| 22 | `READ_REAL_VALUE` | Yes | `read_real_value` | 2963 | Boolean conversion. **Extracted but engine never uses it.** |
| 23 | `STOPREAD_ON_EMPTYROW` | Yes | `stopread_on_emptyrow` | 2964 | Boolean conversion. Default `false`. |
| 24 | `INCLUDE_PHONETICRUNS` | Yes | `include_phoneticruns` | 2965 | Boolean conversion. Default `true`. **Extracted but engine never uses it.** |
| 25 | `GENERATION_MODE` | Yes | `generation_mode` | 2968 | String extraction. Default `EVENT_MODE`. **Extracted but engine never uses it -- uses its own streaming heuristic.** |
| 26 | `CONFIGURE_INFLATION_RATIO` | Yes | `configure_inflation_ratio` | 2969 | Boolean conversion. **Extracted but engine never uses it.** |
| 27 | `INFLATION_RATIO` | Yes | `inflation_ratio` | 2970 | Raw string extraction. **Extracted but engine never uses it.** |
| 28 | `ENCODING` | Yes | `encoding` | 2973-2974 | String extraction with quote stripping. Default `UTF-8`. |
| 29 | `SHEET_NAME` | Yes | `sheet_name` | 2977 | For single-sheet mode compatibility. **Extracted but engine never uses it -- uses sheetlist instead.** |
| 30 | `EXECUTION_MODE` | Yes | `execution_mode` | 2978 | String extraction. **Extracted but engine uses its own mode heuristic.** |
| 31 | `CHUNK_SIZE` | Yes | `chunk_size` | 2979 | String extraction. Used by base class for streaming chunk size. |
| 32 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 33 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |

**Summary**: 28 of 33 parameters extracted (85%). However, 8 of the 28 extracted parameters are never used by the engine (see Section 5.1 for details). The effective extraction rate (parameters both extracted AND implemented) is 20 of 33 (61%).

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (base class schema extraction).

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
| `talendType` | **No** | Full Talend type string (e.g., `id_String`) not preserved -- converted to Python type |

**REJECT schema**: The converter may extract REJECT metadata if present. However, the engine never uses it -- there is no REJECT flow implementation.

### 4.3 Expression Handling

**Context variable handling**: The `parse_file_input_excel()` method does not perform context variable detection internally. Context variables in parameter values (e.g., `context.filepath`) are resolved at engine runtime by `BaseComponent.execute()` -> `self.context_manager.resolve_dict(self.config)` (line 202 of `base_component.py`). Sheet names with context variables are resolved in `_get_sheets_to_read()` via `self.context_manager.resolve_string()` calls.

**Java expression handling**: Java expressions are handled by the post-parsing `mark_java_expression()` step in the converter pipeline. Values containing Java operators, method calls, or routine references are prefixed with `{{java}}` marker. The engine's `BaseComponent._resolve_java_expressions()` resolves these at runtime via the Java bridge.

**Known limitations**:
- The `FILENAME` value is extracted as-is. If it contains a Java expression like `context.filepath + "/data.xlsx"`, it will be marked as `{{java}}` and resolved at runtime via the Java bridge. Simple `context.var` references are resolved by the context manager.
- Sheet names containing context variables (e.g., `context.sheetName`) are resolved at engine runtime in `_get_sheets_to_read()` / `_get_sheets_to_read_xlrd()`, which explicitly calls `self.context_manager.resolve_string()`.
- The `PASSWORD` field is extracted as raw text. If it contains `enc:system.encryption.key.v1:` prefix (Talend encrypted password), the engine's `_decode_password()` method logs a warning and returns the encrypted string as-is -- no actual decryption is implemented.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FIE-001 | **P1** | **DIE_ON_ERROR default mismatch**: Converter defaults `DIE_ON_ERROR` to `false` (line 2908: `str_to_bool(get_param('DIE_ON_ERROR', 'false'), False)`), but Talend default is `true`. If a Talend job does not explicitly set DIE_ON_ERROR, the converter produces `false`, changing the error behavior from fail-fast to continue-on-error. This can silently suppress errors that Talend would have caught. |
| CONV-FIE-002 | **P2** | **HEADER default mismatch**: Converter defaults `HEADER` to `1` (line 2900: `str_to_int(get_param('HEADER', '1'), 1)`), but Talend default is `0`. If a Talend job does not explicitly set HEADER, the converter produces `1` (skip first row) instead of `0` (skip no rows). This will cause the first data row to be silently dropped. |
| CONV-FIE-003 | **P2** | **`filename` key collision on line 2983-2984**: Lines 2983-2984 attempt to normalize parameter names: `if 'filepath' not in component['config'] and component['config']['filename']: component['config']['filepath'] = component['config']['filename']`. However, `component['config']['filename']` is never set by the parser (the parser sets `filepath` on line 2875). This code will raise `KeyError` if `filepath` is somehow missing from config. The intent is to catch edge cases where generic parsing populates `filename` instead of `filepath`, but the condition `component['config']['filename']` will throw if the key does not exist -- should use `.get('filename')`. |
| CONV-FIE-004 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both formats in `_build_converters_dict()` and `_build_dtype_dict()`, this creates inconsistency and may cause subtle type mapping differences. |
| CONV-FIE-005 | **P3** | **Eight extracted parameters are never used by engine**: `version_2007`, `affect_each_sheet`, `novalidate_on_cell`, `read_real_value`, `include_phoneticruns`, `generation_mode`, `configure_inflation_ratio`, `inflation_ratio` are extracted but completely ignored by the engine. These add config bloat without functional value. |
| CONV-FIE-006 | **P3** | **`sheet_name` vs `sheetlist` redundancy**: The converter extracts both `SHEET_NAME` (line 2977) and `SHEETLIST` (lines 2883-2897). The engine only uses `sheetlist`. The `sheet_name` key is dead config. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read .xlsx files | **Yes** | High | `_process_xlsx_file()` line 827 | Uses openpyxl with `read_only=True, data_only=True`. Core reading via `pd.read_excel()` in `_read_sheet()`. |
| 2 | Read .xls files | **Yes** | High | `_process_xls_file()` line 765 | Uses xlrd via `pd.read_excel(engine='xlrd')` in `_read_xls_sheet()`. |
| 3 | Auto-detect .xls vs .xlsx | **Yes** | High | `_detect_excel_format()` line 405 | Extension-based detection: `.xls` -> xlrd, `.xlsx/.xlsm/.xlsb` -> openpyxl. Unknown defaults to openpyxl with warning. |
| 4 | Header row skip | **Yes** | High | `_read_sheet()` line 744, `_read_xls_sheet()` line 947 | `header=header-1 if header > 0 else None` converts 1-based Talend to 0-based pandas. |
| 5 | Footer row skip | **Yes** | High | `_read_sheet()` line 748, `_read_xls_sheet()` line 951 | `skipfooter=footer` passed to `pd.read_excel()`. |
| 6 | Row limit | **Yes** | High | `_read_sheet()` line 686-689, `_read_xls_sheet()` line 893-899 | `nrows=limit` passed to `pd.read_excel()`. Empty/invalid limit -> None (unlimited). |
| 7 | Column range (FIRST/LAST) | **Yes** | Medium | `_read_sheet()` lines 704-727, `_read_xls_sheet()` lines 912-939 | Converts column range to `usecols` list. Supports both numeric and alphabetic LAST_COLUMN via `_column_letter_to_index()`. |
| 8 | All sheets reading | **Yes** | High | `_get_sheets_to_read()` line 509, `_get_sheets_to_read_xlrd()` line 420 | Returns all sheet names when `all_sheets=True` and `sheetlist` is empty. |
| 9 | Sheet filtering by name | **Yes** | High | `_get_sheets_to_read()` lines 525-566, `_get_sheets_to_read_xlrd()` lines 437-477 | Matches sheet names against sheetlist entries. |
| 10 | Sheet filtering by regex | **Yes** | Medium | `_get_sheets_to_read()` lines 537-545 | Uses `re.compile()` + `pattern.search()` for regex matching. **Uses `search()` not `fullmatch()` -- partial regex matches succeed.** |
| 11 | Schema column naming | **Yes** | High | `_read_sheet()` line 745, `_read_xls_sheet()` line 948 | `names=expected_col_names` from output schema. |
| 12 | Schema type enforcement via converters | **Yes** | High | `_build_converters_dict()` lines 232-343 | Comprehensive converter functions for str, int, float, bool, date, Decimal. Uses closure pattern (`make_*_converter()`) to avoid late-binding issues. |
| 13 | Trimming (all columns) | **Partial** | Low | `_apply_trimming()` lines 627-647 | Method exists and is correct, **but is never called from any code path**. Dead code. |
| 14 | Trimming (per-column) | **Partial** | Low | `_apply_trimming()` lines 639-645 | Method handles per-column trim from `trim_select` config, **but is never called**. Dead code. |
| 15 | Advanced separator handling | **Partial** | Low | `_apply_advanced_separators()` lines 608-625 | Method exists and is correct, **but is never called from any code path**. Dead code. |
| 16 | Date-to-string conversion | **Partial** | Low | `_apply_date_conversion()` lines 649-670 | Method exists with Java-to-Python pattern conversion, **but is never called from any code path**. Dead code. |
| 17 | Password-protected files | **No** | N/A | `_decode_password()` line 380, `_process_xlsx_file()` line 833 | `_decode_password()` returns encrypted passwords as-is (line 389). `_process_xlsx_file()` logs warning "Password protection not fully implemented" (line 838) and opens file without password. **openpyxl does not support password-protected files natively** -- requires `msoffcrypto-tool` library which is not imported. |
| 18 | Stop read on empty row | **No** | N/A | Config read at lines 682, 891 | `stopread_on_emptyrow` is read from config but never used in any processing logic. The value is stored in a local variable and then ignored. |
| 19 | Die on error | **Yes** | Medium | Throughout `_process()`, `_process_xlsx_file()`, `_process_xls_file()` | Controls whether to raise exceptions or return empty DataFrame. **Default `false` in engine differs from Talend default `true`.** |
| 20 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 + sheet-level in `_get_sheets_to_read()` lines 531-533 | `context_manager.resolve_dict()` resolves config. `context_manager.resolve_string()` resolves sheet names. |
| 21 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers. |
| 22 | `keep_default_na=False` | **Yes** | High | `_read_sheet()` line 749, `_read_xls_sheet()` line 952 | Prevents "NA", "NULL", "None" strings from becoming NaN. Correct for Talend compatibility. |
| 23 | `na_filter=False` | **Yes** | High | `_read_sheet()` line 749, `_read_xls_sheet()` line 952 | Additional NaN prevention. |
| 24 | Multi-sheet concatenation | **Yes** | High | `_read_batch()` line 984, `_process_xls_file()` line 800 | Uses `pd.concat(all_data, ignore_index=True)` to merge sheets. |
| 25 | Streaming mode for large files | **Yes** | Medium | `_read_streaming()` lines 998-1022 | Generator-based chunked reading. Activated when `execution_mode=HYBRID` and file size > 3GB (`MEMORY_THRESHOLD_MB`). |
| 26 | `usecols` optimization | **Yes** | High | `_read_sheet()` lines 726-730, `_read_xls_sheet()` lines 935-939 | Only reads schema-defined columns. Reduces memory for wide spreadsheets. |
| 27 | Column letter-to-index conversion | **Yes** | High | `_column_letter_to_index()` lines 392-403 | Supports single-letter (A-Z) and multi-letter (AA, AB, etc.) Excel column references. |
| 28 | File existence check | **Yes** | High | `_process()` line 204 | `os.path.exists()` before reading. Returns empty DF or raises based on `die_on_error`. |
| 29 | Quote stripping on filepath | **Yes** | High | `_process()` lines 185-188 | Strips surrounding single or double quotes. Talend often wraps paths in quotes. |
| 30 | **REJECT flow** | **No** | N/A | -- | **No reject output. All errors either raise exceptions or return empty DataFrame. Fundamental gap.** |
| 31 | **AFFECT_EACH_SHEET** | **No** | N/A | -- | **Extracted by converter but never implemented in engine. Header/Footer always apply to every sheet (pandas `pd.read_excel` applies them per-sheet by default, so the Talend `false` case is not handled).** |
| 32 | **CURRENT_SHEET globalMap** | **No** | N/A | -- | **Not implemented. Downstream components cannot determine which sheet a row came from.** |
| 33 | **ERROR_MESSAGE globalMap** | **No** | N/A | -- | **Error message not stored in globalMap for downstream reference.** |
| 34 | **GENERATION_MODE** | **No** | N/A | -- | **Extracted but not implemented. Engine uses its own file-size-based heuristic instead of honoring Talend's Event/User mode setting.** |
| 35 | **READ_REAL_VALUE** | **No** | N/A | -- | **Not implemented. Cell values are read using openpyxl's `data_only=True` which reads cached values, not the same as READ_REAL_VALUE behavior.** |
| 36 | **NOVALIDATE_ON_CELL** | **No** | N/A | -- | **Extracted but not implemented.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIE-001 | **P0** | **No REJECT flow**: Talend produces reject rows for unparseable cells/rows with `errorCode` and `errorMessage` columns when `DIE_ON_ERROR=false` and a REJECT link is connected. V1 either raises `FileOperationError`/`ComponentExecutionError` (die_on_error=true) or returns empty DataFrame (die_on_error=false). There is NO mechanism to capture and route bad rows. The component docstring on line 60 acknowledges this: `"NB_LINE_REJECT: Always 0"`. |
| ENG-FIE-002 | **P0** | **Three dead-code post-processing methods**: `_apply_advanced_separators()` (lines 608-625), `_apply_trimming()` (lines 627-647), and `_apply_date_conversion()` (lines 649-670) are defined but NEVER called from any code path. These methods contain 61 lines of correct, tested-looking logic for critical Talend features -- but none of it executes. Any Talend job relying on TRIMALL, TRIMSELECT, ADVANCED_SEPARATOR, or CONVERTDATETOSTRING will silently produce untrimmed/unconverted data. |
| ENG-FIE-003 | **P1** | **Password protection not implemented**: `_process_xlsx_file()` line 838 logs "Password protection not fully implemented" and opens the file WITHOUT the password. `_decode_password()` returns encrypted passwords as-is. The `msoffcrypto-tool` library (needed for decryption) is not imported. Password-protected Excel files will fail with openpyxl or produce incorrect results. For .xls files via `_process_xls_file()`, the password parameter is passed to `_process_xls_file()` but never forwarded to `xlrd.open_workbook()`. |
| ENG-FIE-004 | **P1** | **DIE_ON_ERROR defaults to False**: Engine defaults `die_on_error` to `False` (line 191: `self.config.get('die_on_error', False)`). Talend defaults to `True`. Combined with converter default `False` (CONV-FIE-001), jobs that do not explicitly set this flag will continue on error instead of failing -- potentially producing incomplete/corrupt output without any error indication. |
| ENG-FIE-005 | **P1** | **STOPREAD_ON_EMPTYROW read but never used**: The config value is read into a local variable `stopread_on_emptyrow` at line 682 and 891, but this variable is never referenced in any subsequent logic. Empty rows in the middle of a sheet will be included in output, and rows after empty rows will not be skipped. |
| ENG-FIE-006 | **P1** | **CURRENT_SHEET globalMap variable not set**: Talend sets `{id}_CURRENT_SHEET` in globalMap before processing each sheet, allowing downstream components to know the source sheet. V1 does not set this variable -- multi-sheet processing loses sheet provenance. |
| ENG-FIE-007 | **P1** | **ERROR_MESSAGE globalMap variable not set**: When errors occur with `die_on_error=false`, the error message is logged but not stored in globalMap via `{id}_ERROR_MESSAGE` for downstream reference. |
| ENG-FIE-008 | **P2** | **AFFECT_EACH_SHEET not implemented**: Converter extracts `affect_each_sheet` but engine never reads it. When `affect_each_sheet=false`, Talend only applies Header/Footer to the first sheet. Pandas `pd.read_excel()` applies `skiprows`/`skipfooter` to every sheet call, so the engine always behaves as if `affect_each_sheet=true`. This means jobs with `affect_each_sheet=false` will incorrectly skip header/footer rows in all sheets. |
| ENG-FIE-009 | **P2** | **Partial match fallback in sheet selection**: `_get_sheets_to_read()` lines 548-553 and `_get_sheets_to_read_xlrd()` lines 461-465 implement a case-insensitive partial match fallback when exact sheet name match fails. This is NOT Talend behavior -- Talend uses exact match only (or regex if USE_REGEX=true). A sheet list entry of `"Data"` will match sheets named `"Data_2023"`, `"Old_Data"`, `"DataBackup"`, etc. This can cause unexpected sheets to be read. |
| ENG-FIE-010 | **P2** | **Regex uses `search()` not `fullmatch()`**: Sheet regex matching (line 541) uses `pattern.search(s)` which matches anywhere in the sheet name. A regex `"Sheet"` will match `"Sheet1"`, `"OldSheet"`, `"SheetBackup"`, etc. Talend's Java `Pattern.matches()` performs full-string matching. Should use `pattern.fullmatch(s)` or `pattern.match(s)` with anchors. |
| ENG-FIE-011 | **P2** | **`set()` deduplication loses sheet order**: `_get_sheets_to_read()` line 567 and `_get_sheets_to_read_xlrd()` line 478 return `list(set(selected_sheets))` which removes duplicates but loses the original sheet order. Talend processes sheets in the order they appear in the workbook. If SHEETLIST contains `["Sheet2", "Sheet1"]`, the v1 engine may process them in arbitrary order. |
| ENG-FIE-012 | **P2** | **xlrd password not forwarded**: `_process_xls_file()` receives `password` as a parameter (line 765) but never passes it to `xlrd.open_workbook()` (line 425). xlrd supports a `formatting_info` parameter but not passwords for encrypted .xls files. |
| ENG-FIE-013 | **P3** | **VERSION_2007 flag ignored**: Engine detects format from file extension (`_detect_excel_format()`) rather than using the `version_2007` flag from Talend config. This works correctly for files with standard extensions, but could fail for files with non-standard extensions (e.g., `.dat` files that are actually Excel format). |
| ENG-FIE-014 | **P3** | **GENERATION_MODE ignored**: Talend's Event/User mode setting is not used. The engine uses its own file-size-based heuristic (streaming for files > 3GB). This means small files that Talend would read in User mode (DOM) are always read in batch mode, and large files that Talend would read in Event mode (SAX) are only streamed if > 3GB. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Accumulated across all sheets. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE since no reject exists -- never accurately reflects rejected rows. |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no reject flow exists. |
| `{id}_CURRENT_SHEET` | Yes (Flow) | **No** | -- | **Not implemented. Critical for multi-sheet jobs.** |
| `{id}_ERROR_MESSAGE` | Yes (After) | **No** | -- | **Not implemented.** |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIE-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileInputExcel, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-FIE-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FIE-004 | **P1** | `file_input_excel.py:380-390` | **`_decode_password()` is a no-op for encrypted passwords**: Method detects `enc:system.encryption.key.v1:` prefix but only logs a warning and returns the encrypted string as-is (line 389). Comment says "In real implementation, this would decrypt the password." The decrypted password is never usable. |
| BUG-FIE-005 | **P1** | `file_input_excel.py:833-839` | **Password-protected .xlsx files opened without password**: When `password` is truthy, `_process_xlsx_file()` calls `_decode_password()` (which returns encrypted text), logs "Password protection not fully implemented", then opens the file identically to the no-password path: `wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)`. No password is ever passed to openpyxl. Password-protected files will fail with openpyxl's generic error rather than a helpful message. |
| BUG-FIE-006 | **P1** | `file_input_excel.py:682, 891` | **`stopread_on_emptyrow` is read but never used**: The config value is assigned to a local variable in both `_read_sheet()` (line 682) and `_read_xls_sheet()` (line 891), but neither method references the variable in any subsequent logic. Functionally, this setting is ignored. |
| BUG-FIE-007 | **P2** | `file_input_excel.py:548-553, 461-465` | **Partial match fallback is not Talend behavior**: When an exact sheet name match fails, both `_get_sheets_to_read()` and `_get_sheets_to_read_xlrd()` fall back to case-insensitive partial matching (`resolved_sheet_name.lower() in s.lower()`). This is an invention of the v1 engine, not Talend behavior. Talend uses exact match or regex -- never partial substring match. This can match unintended sheets silently. |
| BUG-FIE-008 | **P2** | `file_input_excel.py:567, 478` | **`list(set())` loses sheet ordering**: Both `_get_sheets_to_read()` (line 567) and `_get_sheets_to_read_xlrd()` (line 478) return `list(set(selected_sheets))` to remove duplicates. Python's `set()` does not preserve insertion order. This can change the order in which sheets are processed compared to Talend, which processes sheets in workbook order. Should use `dict.fromkeys(selected_sheets)` or a manual dedup loop. |
| BUG-FIE-009 | **P2** | `file_input_excel.py:734-738` | **Filepath re-stripped inside `_read_sheet()`**: Lines 734-738 strip quotes from `self.config.get('filepath')` again, even though `_process()` already does this on lines 185-188 and passes the cleaned `filepath` to `_process_xlsx_file()`. However, `_read_sheet()` does NOT receive the cleaned filepath -- it reads it from `self.config` directly, which still contains the unstripped value. The double-stripping works, but indicates a design flaw: `_read_sheet()` should receive the already-cleaned filepath as a parameter instead of re-reading from config. |
| BUG-FIE-010 | **P2** | `file_input_excel.py:722-723` | **Magic number 100 for default column limit**: When no schema and no `last_column` are provided, `usecols = list(range(start_col, start_col + 100))`. The magic number 100 is undocumented and arbitrary. If a sheet has more than 100 columns, data will be silently truncated. Should either read all columns (no usecols) or log a warning about the limit. |
| BUG-FIE-011 | **P3** | `file_input_excel.py:2983-2984` (converter) | **`component['config']['filename']` KeyError risk**: Line 2983 accesses `component['config']['filename']` without `.get()`. If the generic parser did not set `filename`, this raises `KeyError`. Should be `component['config'].get('filename')`. |
| BUG-FIE-012 | **P2** | `file_input_excel.py:1019-1022` | **`_read_streaming()` returns non-standard dict with `is_streaming` key**: Returns `{'main': generator, 'is_streaming': True}` which is not part of the standard component return signature. Could cause issues in downstream processing where only `{'main': DataFrame}` is expected. |
| BUG-FIE-013 | **P3** | `file_input_excel.py:784` | **`file_size_mb` computed but unused in `_process_xls_file()`**: Line 784 computes file size but never uses it -- streaming decision only occurs in `_process_xlsx_file()`. Dead computation. |

### 6.2 Dead Code Analysis

The following methods are defined but never called, representing ~95 lines of dead code:

| Method | Lines | Purpose | Why Dead | Impact |
|--------|-------|---------|----------|--------|
| `_apply_advanced_separators()` | 608-625 (18 lines) | Converts thousands/decimal separators in string columns | Never called from `_read_batch()`, `_read_sheet()`, or any other method | Jobs using European number formats (e.g., `1.234,56`) will have incorrect numeric parsing |
| `_apply_trimming()` | 627-647 (21 lines) | Trims whitespace from all or selected columns based on `trimall`/`trim_select` config | Never called from any code path | Jobs relying on `TRIMALL=true` or per-column `TRIMSELECT` will have untrimmed string data |
| `_apply_date_conversion()` | 649-670 (22 lines) | Converts date columns to strings using Java-to-Python pattern conversion | Never called from any code path | Jobs using `CONVERTDATETOSTRING=true` with `DATESELECT` will have date objects instead of formatted strings |
| `_build_dtype_dict()` | 345-378 (34 lines) | Builds dtype dictionary for `pd.read_excel()` | Engine uses `_build_converters_dict()` instead (which is correct -- converters are more reliable). `_build_dtype_dict()` is never referenced. | No functional impact (converters approach is better), but 34 lines of dead code add confusion |

**Total dead code**: ~95 lines across 4 methods (9% of the 1023-line file).

### 6.3 Code Duplication

| ID | Priority | Issue |
|----|----------|-------|
| DUP-FIE-001 | **P2** | **`_read_sheet()` and `_read_xls_sheet()` are 90% identical**: `_read_sheet()` (lines 672-763, 92 lines) and `_read_xls_sheet()` (lines 881-966, 86 lines) contain nearly identical logic for configuration extraction, column range computation, usecols construction, schema enforcement, and `pd.read_excel()` invocation. The ONLY difference is `_read_xls_sheet()` passes `engine='xlrd'` to `pd.read_excel()`. These should be consolidated into a single method with an `engine` parameter. |
| DUP-FIE-002 | **P2** | **`_get_sheets_to_read()` and `_get_sheets_to_read_xlrd()` are 85% identical**: `_get_sheets_to_read()` (lines 509-606, 98 lines) and `_get_sheets_to_read_xlrd()` (lines 420-507, 88 lines) duplicate the sheet selection logic. The only difference is how available sheets are retrieved: `wb.sheetnames` vs `xlrd.open_workbook().sheet_names()`. The entire sheetlist matching logic is duplicated. Should extract a `_filter_sheets(available_sheets)` method. |

### 6.4 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIE-001 | **P2** | **`trim_select` (underscore)** vs Talend parameter `TRIMSELECT` (no separator). The converter maps `TRIMSELECT` -> `trim_select` (line 2938). This is consistent with the snake_case convention used for other parameters (`die_on_error`, `all_sheets`), but differs from tFileInputDelimited which uses `trim_all` (vs `TRIMALL`). The inconsistency is between Talend's concatenated naming and Python's snake_case -- acceptable. |
| NAME-FIE-002 | **P3** | **`convertdatetostring` (no separators)** retains Talend's concatenated naming. Unlike other parameters which use snake_case (`die_on_error`, `all_sheets`, `first_column`), `convertdatetostring` preserves the original Talend naming verbatim. Should be `convert_date_to_string` for consistency. |
| NAME-FIE-003 | **P3** | **`date_select` vs `trim_select`**: Both are table parameters from Talend (`DATESELECT`, `TRIMSELECT`). The converter maps them consistently to snake_case (`date_select`, `trim_select`). However, `convertdatetostring` (the parent toggle for `date_select`) is NOT snake_case. |

### 6.5 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIE-001 | **P1** | "Extracted parameters MUST be implemented in the engine" (METHODOLOGY.md) | 8 extracted parameters (`version_2007`, `affect_each_sheet`, `novalidate_on_cell`, `read_real_value`, `include_phoneticruns`, `generation_mode`, `configure_inflation_ratio`, `inflation_ratio`) are never used by the engine. |
| STD-FIE-002 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |
| STD-FIE-003 | **P2** | "`_validate_config()` validates all config keys" (METHODOLOGY.md) | `_validate_config()` is called (unlike tFileInputDelimited), but does not validate `affect_each_sheet`, `generation_mode`, or other extracted params. |
| STD-FIE-004 | **P3** | "No dead code" (STANDARDS.md) | Four dead methods: `_apply_advanced_separators()`, `_apply_trimming()`, `_apply_date_conversion()`, `_build_dtype_dict()`. Total ~95 lines. |

### 6.6 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FIE-001 | **P2** | **Password logged in debug output**: If debug logging is enabled, the password string may appear in log messages since it is part of `self.config` which is logged at various points. Sensitive credentials should be masked in log output. |
| SEC-FIE-002 | **P3** | **No path traversal protection**: `filepath` from config is used directly with `os.path.exists()` and passed to `pd.read_excel()` / `openpyxl.load_workbook()`. If config comes from untrusted sources, path traversal is possible. Not a concern for Talend-converted jobs where config is trusted. |

### 6.7 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 171); batch/xls methods log completion with row counts -- correct |
| Sensitive data | Password may appear in debug logs (see SEC-FIE-001) -- needs fix |
| No print statements | No `print()` calls -- correct |
| Sheet-level logging | Each sheet read is logged at INFO level with sheet name -- correct |
| Regex matching logging | Matched sheets from regex are logged at INFO level -- helpful for debugging |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError`, `FileOperationError`, and `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern in `_process_xlsx_file()` (line 820) and `_process_xls_file()` (line 875) -- correct |
| `die_on_error` handling | Consistent pattern: raise on error when True, return empty DataFrame when False. Applied in `_process()` (lines 197-201, 207-212), `_process_xlsx_file()` (lines 848-854, 870-879), `_process_xls_file()` (lines 776-781, 817-825) -- correct |
| No bare `except` | All except clauses specify `Exception` or specific exception types -- correct |
| Error messages | Include component ID, file path, and error details -- correct |
| Re-raise custom exceptions | `FileOperationError` and `ConfigurationError` are re-raised as-is (lines 225-227, 813-815, 867-869) while generic `Exception` is wrapped in `ComponentExecutionError` -- correct |
| Sheet-level errors | Individual sheet read failures in `_read_sheet()` and `_read_xls_sheet()` return empty DataFrame (lines 762-763, 965-966) rather than propagating -- allows other sheets to be read. This is a design choice that may differ from Talend behavior where one bad sheet could fail the whole component. |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | All methods have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[Dict[str, callable]]`, `List[str]`, `Iterator[pd.DataFrame]` -- correct |
| Generic callable | `_build_converters_dict()` return type `Optional[Dict[str, callable]]` uses lowercase `callable` instead of `typing.Callable` -- minor style issue |

### 6.10 Converter Function Quality (Engine)

The `_build_converters_dict()` method (lines 232-343) is one of the most sophisticated parts of this component and deserves detailed analysis:

| Aspect | Assessment |
|--------|------------|
| Closure pattern | Uses `make_*_converter()` factory functions to create closures for each type. This correctly avoids the late-binding closure pitfall in Python (where all converters would reference the last `col_type`). -- correct |
| NaN handling | All converters check `pd.isna(x) or x is None` as first condition -- correct |
| String converter | Handles datetime objects (formats as `dd-mm-yyyy`), whole numbers (strips `.0`), booleans, and pass-through for existing strings. The date format `dd-mm-yyyy` is hardcoded -- should use schema pattern. |
| Integer converter | Uses `int(float(str(x)))` chain to handle "123.0" -> 123 conversion common in Excel. Returns None for unparseable values. -- correct |
| Float converter | Uses `float(str(x))` with None fallback -- correct |
| Boolean converter | Recognizes `"true"`, `"1"`, `"yes"`, `"on"` (case-insensitive) as True. Returns None for empty. -- correct |
| Date converter | Returns datetime objects as-is, attempts `pd.to_datetime()` for strings, falls back to raw string -- correct |
| Decimal converter | Uses `Decimal(str(x))` with `InvalidOperation` catch. Imports `Decimal` inside the function (redundant -- already imported at module level line 10). |
| Type coverage | Supports: `str`, `int`, `id_Integer`, `id_Long`, `float`, `id_Float`, `id_Double`, `bool`, `id_Boolean`, `date`, `id_Date`, `Decimal`, `id_BigDecimal`. -- comprehensive |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIE-001 | **P1** | **Entire workbook loaded for sheet name discovery (.xlsx)**: `_process_xlsx_file()` line 839 calls `openpyxl.load_workbook(filepath, read_only=True, data_only=True)` to discover sheet names, then `_read_sheet()` calls `pd.read_excel()` which opens the file again. The workbook is effectively opened twice. For large files, this doubles I/O overhead. Should pass the opened workbook to `pd.read_excel()` or use `openpyxl` to read directly. |
| PERF-FIE-002 | **P2** | **Duplicated code in `_read_sheet()` / `_read_xls_sheet()`**: ~180 lines of nearly identical code. This is a maintenance cost rather than runtime performance issue, but each bug fix or feature addition must be applied in two places. |
| PERF-FIE-003 | **P2** | **`_build_converters_dict()` builds converters for ALL schema columns**: Even when `usecols` limits which columns are read, converters are built for every column in the schema. This is a minor overhead since converter construction is O(N) and N is typically small, but wasteful for wide schemas. |
| PERF-FIE-004 | **P3** | **Decimal import inside converter closure**: `_build_converters_dict()` line 336 imports `Decimal` and `InvalidOperation` inside the closure, even though `Decimal` is already imported at module level (line 10). The redundant import adds negligible overhead per-row but is unnecessary. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Implemented via `_read_streaming()` with configurable `chunk_size` (default 100,000 rows). Activated when file > 3GB and `execution_mode=HYBRID`. Correct design. |
| Memory threshold | `MEMORY_THRESHOLD_MB = 3072` (3GB) inherited from `BaseComponent`. Reasonable default for Excel files which are typically smaller than CSVs. |
| `read_only=True` | openpyxl `read_only=True` mode uses lazy loading -- correct for memory efficiency. |
| `data_only=True` | openpyxl `data_only=True` reads cached formula values instead of formula strings -- reduces memory and is correct for ETL use. |
| `keep_default_na=False` | Prevents pandas from treating "NA", "NULL" strings as NaN -- correct for Talend compatibility. |
| `usecols` optimization | Limits columns read to schema-defined columns -- reduces memory for wide spreadsheets. |
| Multi-sheet concatenation | `pd.concat(all_data, ignore_index=True)` creates a new DataFrame with all sheets combined. For very large workbooks with many sheets, this could exceed memory. The streaming mode helps but only chunks within a sheet, not across sheets. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| Footer skip + streaming | `skipfooter` requires reading the entire sheet to know where the footer starts. With streaming chunks, the last chunk may include footer rows. pandas `skipfooter` may not work correctly with chunked reading. |
| Stats per sheet | `_update_stats()` is called per sheet in batch mode (line 980, 795), which correctly accumulates totals. In streaming mode, stats are updated per chunk (line 1014). |
| Sheet-level errors | In `_read_batch()`, if one sheet fails, its DataFrame is empty and `_read_sheet()` returns `pd.DataFrame()` (line 763). The loop continues to process other sheets. This is reasonable degradation but may lose data from the failed sheet without proper error reporting. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputExcel` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests found for `parse_file_input_excel()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 1023 lines of v1 engine code are completely unverified. The converter parser (136 lines) is also unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic .xlsx read | P0 | Read a simple .xlsx file with header row, verify row count and column values match expected output |
| 2 | Basic .xls read | P0 | Read a simple .xls file, verify xlrd engine path works correctly |
| 3 | Schema enforcement | P0 | Read with typed schema (int, float, string, Decimal, date), verify correct type coercion via converters |
| 4 | Header skip | P0 | Verify `header=2` skips the correct rows from a known Excel file |
| 5 | Missing file + die_on_error=true | P0 | Should raise `FileOperationError` with descriptive message |
| 6 | Missing file + die_on_error=false | P0 | Should return empty DataFrame with stats (0, 0, 0) |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Multi-sheet reading (all_sheets=true) | P1 | Read workbook with 3 sheets, verify all rows from all sheets are concatenated |
| 9 | Sheet filtering by name | P1 | Read specific sheet by name from a multi-sheet workbook |
| 10 | Sheet filtering by regex | P1 | Read sheets matching `"Data_\d+"` pattern, verify correct sheets selected |
| 11 | Column range (first_column, last_column) | P1 | Verify `first_column=2, last_column=5` reads only columns B-E |
| 12 | Column letter-to-index | P1 | Verify `last_column="E"` correctly converts to index 5 |
| 13 | Footer skip | P1 | Verify `footer=2` skips the last 2 rows of a sheet |
| 14 | Row limit | P1 | Verify `limit=5` reads only 5 rows from a 100-row sheet |
| 15 | Context variable in filepath | P1 | `${context.input_dir}/data.xlsx` should resolve via context manager |
| 16 | Context variable in sheet name | P1 | Sheet name `${context.target_sheet}` should resolve before matching |
| 17 | Empty Excel file | P1 | Should return empty DataFrame without error |
| 18 | Converter parameter extraction | P1 | Verify `parse_file_input_excel()` correctly extracts all 28 parameters from sample Talend XML |
| 19 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` is set in globalMap after execution |
| 20 | Die on error default | P1 | Verify die_on_error defaults match expected behavior (currently False; should be True per Talend) |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Multi-letter column (AA, AB) | P2 | Verify `_column_letter_to_index("AA")` returns 27, `"AZ"` returns 52 |
| 22 | Large file streaming | P2 | Verify hybrid mode activates streaming for file > threshold and produces correct results |
| 23 | Regex edge cases | P2 | Regex with special characters, invalid regex patterns (should warn not crash) |
| 24 | Duplicate sheet names in sheetlist | P2 | Verify deduplication does not cause issues |
| 25 | Password-protected file | P2 | Verify appropriate error message (not generic openpyxl error) when password not supported |
| 26 | Concurrent reads | P2 | Multiple `FileInputExcel` instances reading different files simultaneously |
| 27 | .xlsb and .xlsm formats | P2 | Verify `.xlsm` (macro-enabled) and `.xlsb` (binary) formats are handled correctly |
| 28 | Trimming (when wired up) | P2 | Test `_apply_trimming()` once it is called from the main code path |
| 29 | Advanced separators (when wired up) | P2 | Test `_apply_advanced_separators()` once it is called from the main code path |
| 30 | Date conversion (when wired up) | P2 | Test `_apply_date_conversion()` with various date patterns |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIE-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FIE-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| ENG-FIE-001 | Engine | No REJECT flow -- bad rows are lost or cause job failure. Fundamental gap for data quality pipelines. |
| ENG-FIE-002 | Engine | Three dead-code post-processing methods (`_apply_advanced_separators`, `_apply_trimming`, `_apply_date_conversion`) containing 61 lines of correct logic that is never executed. TRIMALL, TRIMSELECT, ADVANCED_SEPARATOR, CONVERTDATETOSTRING features silently do nothing. |
| TEST-FIE-001 | Testing | Zero v1 unit tests for this 1023-line component. All engine code is completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIE-001 | Converter | DIE_ON_ERROR default `false` differs from Talend default `true`. Jobs without explicit setting will silently suppress errors. |
| ENG-FIE-003 | Engine | Password protection not implemented. `_decode_password()` is a no-op for encrypted passwords. `msoffcrypto-tool` not imported. |
| ENG-FIE-004 | Engine | DIE_ON_ERROR defaults to False in engine. Combined with converter default False, error behavior inverted from Talend. |
| ENG-FIE-005 | Engine | STOPREAD_ON_EMPTYROW config read but never used. Empty-row stop behavior does not work. |
| ENG-FIE-006 | Engine | `{id}_CURRENT_SHEET` globalMap variable not set. Multi-sheet jobs lose sheet provenance. |
| ENG-FIE-007 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set. Error details not available downstream. |
| BUG-FIE-004 | Bug | `_decode_password()` returns encrypted passwords unchanged. No actual decryption. |
| BUG-FIE-005 | Bug | Password-protected .xlsx files opened without password. openpyxl call identical to no-password path. |
| BUG-FIE-006 | Bug | `stopread_on_emptyrow` assigned to local variable but never referenced. |
| STD-FIE-001 | Standards | 8 extracted parameters never used by engine. Converter work wasted. |
| PERF-FIE-001 | Performance | Workbook opened twice for .xlsx files (openpyxl + pd.read_excel). Doubles I/O for large files. |
| TEST-FIE-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIE-002 | Converter | HEADER default `1` differs from Talend default `0`. First data row silently dropped for jobs without explicit HEADER. |
| CONV-FIE-003 | Converter | `filename` key collision on line 2983 -- `component['config']['filename']` without `.get()` risks KeyError. |
| CONV-FIE-004 | Converter | Schema type format violates STANDARDS.md (Python types vs Talend types). |
| ENG-FIE-008 | Engine | AFFECT_EACH_SHEET not implemented. Engine always applies header/footer to every sheet. |
| ENG-FIE-009 | Engine | Partial match fallback in sheet selection is not Talend behavior. Can match unintended sheets. |
| ENG-FIE-010 | Engine | Regex uses `search()` not `fullmatch()`. Partial regex matches succeed unexpectedly. |
| ENG-FIE-011 | Engine | `set()` deduplication loses sheet order. Processing order may differ from Talend. |
| ENG-FIE-012 | Engine | xlrd password parameter not forwarded. .xls password-protected files will fail. |
| BUG-FIE-007 | Bug | Partial match fallback matches unintended sheets silently. |
| BUG-FIE-008 | Bug | `list(set())` loses sheet ordering. |
| BUG-FIE-009 | Bug | Filepath re-stripped in `_read_sheet()` -- design flaw, reads from config instead of parameter. |
| BUG-FIE-010 | Bug | Magic number 100 for default column limit. Wide sheets silently truncated. |
| DUP-FIE-001 | Duplication | `_read_sheet()` and `_read_xls_sheet()` are 90% identical (~180 lines duplicated). |
| DUP-FIE-002 | Duplication | `_get_sheets_to_read()` and `_get_sheets_to_read_xlrd()` are 85% identical (~186 lines duplicated). |
| NAME-FIE-001 | Naming | `trim_select` naming is consistent within the component but differs from Talend's `TRIMSELECT`. |
| STD-FIE-002 | Standards | Schema types use Python format instead of Talend format. |
| STD-FIE-003 | Standards | `_validate_config()` does not validate all extracted config keys. |
| SEC-FIE-001 | Security | Password may appear in debug log output. |
| PERF-FIE-002 | Performance | 180 lines of duplicated code in read methods. |
| PERF-FIE-003 | Performance | Converters built for all schema columns even when usecols limits reading. |
| BUG-FIE-012 | Bug | `_read_streaming()` returns non-standard dict with `is_streaming` key (lines 1019-1022). Returns `{'main': generator, 'is_streaming': True}` which is not part of the standard component return signature. Could cause issues in downstream processing. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIE-005 | Converter | 8 extracted parameters never used by engine. Dead config data. |
| CONV-FIE-006 | Converter | `sheet_name` vs `sheetlist` redundancy. |
| ENG-FIE-013 | Engine | VERSION_2007 flag ignored. Format detected from extension only. |
| ENG-FIE-014 | Engine | GENERATION_MODE ignored. Engine uses own file-size heuristic. |
| BUG-FIE-011 | Bug | `component['config']['filename']` KeyError risk in converter line 2983. |
| NAME-FIE-002 | Naming | `convertdatetostring` retains Talend naming instead of snake_case. |
| NAME-FIE-003 | Naming | Inconsistent naming style between `convertdatetostring` and `date_select`. |
| STD-FIE-004 | Standards | 4 dead methods (~95 lines total) violate no-dead-code standard. |
| SEC-FIE-002 | Security | No path traversal protection on `filepath`. |
| PERF-FIE-004 | Performance | Redundant `Decimal` import inside converter closure. |
| BUG-FIE-013 | Bug | `file_size_mb` computed but unused in `_process_xls_file()`. Line 784 computes file size but never uses it -- streaming decision only in `_process_xlsx_file()`. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 2 bugs (cross-cutting), 1 engine (REJECT), 1 engine (dead code), 1 testing |
| P1 | 12 | 1 converter, 5 engine, 3 bugs, 1 standards, 1 performance, 1 testing |
| P2 | 21 | 3 converter, 5 engine, 5 bugs, 2 duplication, 1 naming, 2 standards, 1 security, 2 performance |
| P3 | 11 | 2 converter, 2 engine, 2 bugs, 2 naming, 1 standards, 1 security, 1 performance |
| **Total** | **49** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FIE-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FIE-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Wire up dead post-processing methods** (ENG-FIE-002): Add calls to `_apply_advanced_separators()`, `_apply_trimming()`, and `_apply_date_conversion()` after `pd.read_excel()` returns in both `_read_sheet()` and `_read_xls_sheet()`. The methods already exist with correct logic -- they just need to be called. Example insertion point after line 758 in `_read_sheet()`:
   ```python
   # Apply post-processing
   df = self._apply_advanced_separators(df)
   df = self._apply_trimming(df)
   df = self._apply_date_conversion(df)
   ```
   **Impact**: Enables TRIMALL, TRIMSELECT, ADVANCED_SEPARATOR, CONVERTDATETOSTRING features. **Risk**: Low -- methods already exist and are self-contained.

4. **Fix DIE_ON_ERROR defaults** (CONV-FIE-001, ENG-FIE-004): Change converter default on line 2908 from `'false'` to `'true'`. Change engine default on line 191 from `False` to `True`. This aligns with Talend behavior where tFileInputExcel defaults to fail-fast. **Impact**: Jobs without explicit DIE_ON_ERROR setting will now fail on error instead of silently continuing. **Risk**: Medium -- may cause previously-silent errors to surface. This is the correct behavior.

5. **Create unit test suite** (TEST-FIE-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic .xlsx read, basic .xls read, schema enforcement, header skip, missing file handling (both die_on_error modes), and statistics tracking. Without these, no v1 engine behavior is verified.

### Short-Term (Hardening)

6. **Fix HEADER default** (CONV-FIE-002): Change converter default on line 2900 from `'1'` to `'0'` to match Talend. This is critical: the current default silently drops the first data row of every Excel file that does not explicitly set HEADER.

7. **Implement STOPREAD_ON_EMPTYROW** (ENG-FIE-005, BUG-FIE-006): After reading with `pd.read_excel()`, iterate the DataFrame to find the first fully-empty row (all values are empty string or NaN), then truncate the DataFrame at that point. Apply in both `_read_sheet()` and `_read_xls_sheet()`. Example:
   ```python
   if stopread_on_emptyrow:
       empty_mask = df.eq('').all(axis=1) | df.isna().all(axis=1)
       first_empty = empty_mask.idxmax() if empty_mask.any() else None
       if first_empty is not None:
           df = df.iloc[:first_empty]
   ```

8. **Set CURRENT_SHEET globalMap variable** (ENG-FIE-006): Before processing each sheet in `_read_batch()` and `_read_streaming()`, call `self.global_map.put(f"{self.id}_CURRENT_SHEET", sheet_name)` if `self.global_map` is set. This enables downstream components to know the source sheet.

9. **Set ERROR_MESSAGE globalMap variable** (ENG-FIE-007): In error handlers throughout the component, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` when `self.global_map` is set.

10. **Fix partial match fallback** (BUG-FIE-007, ENG-FIE-009): Remove the partial match fallback logic in both `_get_sheets_to_read()` (lines 548-553) and `_get_sheets_to_read_xlrd()` (lines 461-465). Replace with a log warning that the exact sheet name was not found. Talend does not do partial matching.

11. **Fix regex matching to use fullmatch** (ENG-FIE-010): Change `pattern.search(s)` to `pattern.fullmatch(s)` on line 541 (and equivalent lines in `_get_sheets_to_read_xlrd()`). This matches Talend's Java `Pattern.matches()` behavior which requires the entire string to match.

12. **Fix set-based deduplication** (BUG-FIE-008, ENG-FIE-011): Replace `list(set(selected_sheets))` with `list(dict.fromkeys(selected_sheets))` to preserve insertion order while removing duplicates.

13. **Implement password support** (ENG-FIE-003, BUG-FIE-004, BUG-FIE-005): Add `msoffcrypto-tool` as a dependency. In `_process_xlsx_file()`, when password is provided, use `msoffcrypto` to decrypt the file into a BytesIO buffer before passing to openpyxl:
    ```python
    import msoffcrypto
    import io
    with open(filepath, 'rb') as f:
        ms_file = msoffcrypto.OfficeFile(f)
        ms_file.load_key(password=decoded_password)
        decrypted = io.BytesIO()
        ms_file.decrypt(decrypted)
        wb = openpyxl.load_workbook(decrypted, read_only=True, data_only=True)
    ```

14. **Fix converter KeyError risk** (BUG-FIE-011, CONV-FIE-003): Change line 2983 from `component['config']['filename']` to `component['config'].get('filename')`.

### Long-Term (Optimization)

15. **Consolidate duplicated methods** (DUP-FIE-001, DUP-FIE-002): Merge `_read_sheet()` and `_read_xls_sheet()` into a single `_read_sheet(filepath, sheet_name, engine=None)` method. Merge `_get_sheets_to_read()` and `_get_sheets_to_read_xlrd()` into `_get_sheets_to_read(available_sheets)` with a separate method to get available sheet names per engine.

16. **Implement REJECT flow** (ENG-FIE-001): Wrap `pd.read_excel()` calls with error handling that captures per-row failures. Build a reject DataFrame with schema columns plus `errorCode` and `errorMessage`. Return `{'main': good_df, 'reject': reject_df}` from `_process()`. Update `_update_stats()` with actual reject count.

17. **Implement AFFECT_EACH_SHEET** (ENG-FIE-008): When `affect_each_sheet=false`, only pass `skiprows` and `skipfooter` for the first sheet in the iteration. For subsequent sheets, pass `skiprows=0` and `skipfooter=0`.

18. **Remove dead `_build_dtype_dict()` method** (STD-FIE-004): Since the engine correctly uses `_build_converters_dict()` (which is superior to dtype for controlling type conversion), the unused `_build_dtype_dict()` method (lines 345-378) should be removed.

19. **Fix magic number for column limit** (BUG-FIE-010): Replace the hardcoded `100` with either no limit (pass `usecols=None` to read all columns) or a configurable constant. Add a log warning when applying the default column limit.

20. **Implement GENERATION_MODE** (ENG-FIE-014): Honor the Talend `generation_mode` setting. When `EVENT_MODE`, use openpyxl's `read_only=True` (already done by default). When `USER_MODE`, use `read_only=False` for full formula evaluation. Currently, the engine always uses `read_only=True`.

21. **Create integration test** (TEST-FIE-002): Build an end-to-end test exercising `tFileInputExcel -> tMap -> tFileOutputDelimited` in the v1 engine, verifying context resolution, multi-sheet processing, and globalMap propagation (including CURRENT_SHEET).

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 2850-2986
def parse_file_input_excel(self, node, component: dict) -> dict:
    """
    Parse tFileInputExcel specific configuration from Talend XML node.
    Comprehensive parsing of all tFileInputExcel parameters including complex tables.
    """
    # Helper functions
    def get_param(name, default=None):
        elem = node.find(f".//elementParameter[@name='{name}']")
        return elem.get('value', default) if elem is not None else default

    def str_to_bool(value, default=False):
        if isinstance(value, str):
            return value.lower() == 'true'
        return default if value is None else bool(value)

    def str_to_int(value, default=0):
        if isinstance(value, str) and value.isdigit():
            return int(value)
        elif isinstance(value, int):
            return value
        return default

    # Basic File Parameters
    component['config']['filepath'] = get_param('FILENAME', '')
    component['config']['password'] = get_param('PASSWORD', '')

    # Excel Version and Sheet Selection
    component['config']['version_2007'] = str_to_bool(get_param('VERSION_2007', 'true'), True)
    component['config']['all_sheets'] = str_to_bool(get_param('ALL_SHEETS', 'false'), False)

    # SHEETLIST table parsing
    sheetlist = []
    for table in node.findall(".//elementParameter[@name='SHEETLIST']"):
        sheet_entry = {}
        for elem in table.findall('./elementValue'):
            ref = elem.get('elementRef', '')
            val = elem.get('value', '')
            if ref == 'SHEETNAME':
                sheet_entry['sheetname'] = val
            elif ref == 'USE_REGEX':
                sheet_entry['use_regex'] = str_to_bool(val, False)
        if sheet_entry:
            sheetlist.append(sheet_entry)
    component['config']['sheetlist'] = sheetlist

    # Row and Column Parameters
    component['config']['header'] = str_to_int(get_param('HEADER', '1'), 1)   # BUG: default should be '0'
    component['config']['footer'] = str_to_int(get_param('FOOTER', '0'), 0)
    component['config']['limit'] = get_param('LIMIT', '')
    component['config']['affect_each_sheet'] = str_to_bool(get_param('AFFECT_EACH_SHEET', 'false'), False)
    component['config']['first_column'] = str_to_int(get_param('FIRST_COLUMN', '1'), 1)
    component['config']['last_column'] = get_param('LAST_COLUMN', '')

    # Error Handling
    component['config']['die_on_error'] = str_to_bool(get_param('DIE_ON_ERROR', 'false'), False)  # BUG: default should be 'true'
    component['config']['suppress_warn'] = str_to_bool(get_param('SUPPRESS_WARN', 'false'), False)
    component['config']['novalidate_on_cell'] = str_to_bool(get_param('NOVALIDATE_ON_CELL', 'false'), False)

    # Advanced Separators
    component['config']['advanced_separator'] = str_to_bool(get_param('ADVANCED_SEPARATOR', 'false'), False)
    thousands_sep = get_param('THOUSANDS_SEPARATOR', ',')
    decimal_sep = get_param('DECIMAL_SEPARATOR', '.')
    component['config']['thousands_separator'] = thousands_sep.strip('"') if isinstance(thousands_sep, str) else ','
    component['config']['decimal_separator'] = decimal_sep.strip('"') if isinstance(decimal_sep, str) else '.'

    # Trimming Configuration
    component['config']['trimall'] = str_to_bool(get_param('TRIMALL', 'false'), False)

    # TRIMSELECT table parsing
    trim_select = []
    for table in node.findall(".//elementParameter[@name='TRIMSELECT']"):
        trim_entry = {}
        for elem in table.findall('./elementValue'):
            ref = elem.get('elementRef', '')
            val = elem.get('value', '')
            if ref == 'SCHEMA_COLUMN':
                trim_entry['column'] = val
            elif ref == 'TRIM':
                trim_entry['trim'] = str_to_bool(val, False)
        if trim_entry and 'column' in trim_entry:
            trim_select.append(trim_entry)
    component['config']['trim_select'] = trim_select

    # Date Conversion
    component['config']['convertdatetostring'] = str_to_bool(get_param('CONVERTDATETOSTRING', 'false'), False)

    # DATESELECT table parsing
    date_select = []
    for table in node.findall(".//elementParameter[@name='DATESELECT']"):
        date_entry = {}
        for elem in table.findall('./elementValue'):
            ref = elem.get('elementRef', '')
            val = elem.get('value', '')
            if ref == 'SCHEMA_COLUMN':
                date_entry['column'] = val
            elif ref == 'CONVERTDATE':
                date_entry['convert_date'] = str_to_bool(val, False)
            elif ref == 'PATTERN':
                date_entry['pattern'] = val.strip('"') if val else "MM-dd-yyyy"
        if date_entry and 'column' in date_entry:
            date_select.append(date_entry)
    component['config']['date_select'] = date_select

    # Reading Behavior
    component['config']['read_real_value'] = str_to_bool(get_param('READ_REAL_VALUE', 'false'), False)
    component['config']['stopread_on_emptyrow'] = str_to_bool(get_param('STOPREAD_ON_EMPTYROW', 'false'), False)
    component['config']['include_phoneticruns'] = str_to_bool(get_param('INCLUDE_PHONETICRUNS', 'true'), True)

    # Generation and Performance
    component['config']['generation_mode'] = get_param('GENERATION_MODE', 'EVENT_MODE')
    component['config']['configure_inflation_ratio'] = str_to_bool(get_param('CONFIGURE_INFLATION_RATIO', 'false'), False)
    component['config']['inflation_ratio'] = get_param('INFLATION_RATIO', '')

    # Encoding
    encoding = get_param('ENCODING', 'UTF-8')
    component['config']['encoding'] = encoding.strip('"') if isinstance(encoding, str) else 'UTF-8'

    # Additional Parameters
    component['config']['sheet_name'] = get_param('SHEET_NAME', '')
    component['config']['execution_mode'] = get_param('EXECUTION_MODE', '')
    component['config']['chunk_size'] = get_param('CHUNK_SIZE', '')

    # Normalize parameter names -- BUG: should use .get('filename') not ['filename']
    if 'filepath' not in component['config'] and component['config']['filename']:
        component['config']['filepath'] = component['config']['filename']

    return component
```

**Notes on this code**:
- Line 2900: `HEADER` default `'1'` differs from Talend default `0`. This is a silent data-loss bug.
- Line 2908: `DIE_ON_ERROR` default `'false'` differs from Talend default `true`. This changes error behavior.
- Lines 2883-2897: SHEETLIST table parsing is correct -- properly extracts nested `elementValue` groups.
- Lines 2924-2938: TRIMSELECT table parsing is correct.
- Lines 2944-2960: DATESELECT table parsing is correct, with quote stripping on patterns.
- Line 2983: `component['config']['filename']` should use `.get()` to avoid KeyError.

---

## Appendix B: Engine Class Structure

```
FileInputExcel (BaseComponent)
    Imports:
        openpyxl          # .xlsx reading
        xlrd              # .xls reading
        pandas            # DataFrame creation via pd.read_excel()
        re                # Regex sheet matching
        Decimal           # BigDecimal support
        datetime          # Date handling

    Methods:
        _validate_config() -> List[str]                    # Called from _process() -- validates config fields
        _process(input_data) -> Dict[str, Any]             # Main entry point: detect format, dispatch to xls/xlsx handler
        _build_converters_dict() -> Optional[Dict]         # Type-safe converter functions for pd.read_excel() converters param
        _build_dtype_dict() -> Optional[Dict]              # DEAD CODE: dtype dict for pd.read_excel() (never called)
        _decode_password(encrypted_password) -> str         # NO-OP: returns encrypted passwords as-is
        _column_letter_to_index(column_letter) -> int      # Converts "A" -> 1, "AA" -> 27, etc.
        _detect_excel_format(filepath) -> str               # Extension-based format detection: .xls -> 'xlrd', .xlsx -> 'openpyxl'
        _get_sheets_to_read_xlrd(filepath) -> List[str]    # Sheet selection for .xls files (opens workbook via xlrd)
        _get_sheets_to_read(wb) -> List[str]               # Sheet selection for .xlsx files (uses openpyxl workbook)
        _apply_advanced_separators(df) -> DataFrame        # DEAD CODE: applies thousands/decimal separator conversion
        _apply_trimming(df) -> DataFrame                   # DEAD CODE: applies trimall/trim_select
        _apply_date_conversion(df) -> DataFrame            # DEAD CODE: applies date-to-string conversion
        _read_sheet(wb, sheet_name) -> DataFrame           # Reads single .xlsx sheet via pd.read_excel()
        _process_xls_file(filepath, ...) -> Dict           # Orchestrates .xls file reading
        _process_xlsx_file(filepath, ...) -> Dict          # Orchestrates .xlsx file reading (with streaming decision)
        _read_xls_sheet(filepath, sheet_name) -> DataFrame # Reads single .xls sheet via pd.read_excel(engine='xlrd')
        _read_batch(wb, sheets_to_read) -> Dict            # Batch mode: read all sheets, concat, return
        _read_streaming(wb, sheets_to_read) -> Dict        # Streaming mode: yield sheet chunks via generator
```

**Method call graph** (main execution path for .xlsx):
```
execute()                          [BaseComponent]
  -> _resolve_java_expressions()   [BaseComponent]
  -> context_manager.resolve_dict() [ContextManager]
  -> _process()                    [FileInputExcel:156]
       -> _validate_config()       [FileInputExcel:81]
       -> _detect_excel_format()   [FileInputExcel:405]
       -> _process_xlsx_file()     [FileInputExcel:827]
            -> _decode_password()  [FileInputExcel:380]  (if password)
            -> openpyxl.load_workbook()
            -> _get_sheets_to_read() [FileInputExcel:509]
            -> _read_batch()       [FileInputExcel:968]
                 -> _read_sheet()  [FileInputExcel:672]
                      -> _build_converters_dict() [FileInputExcel:232]
                      -> pd.read_excel()
                 -> pd.concat()
                 -> _update_stats() [BaseComponent:306]
  -> _update_global_map()          [BaseComponent:298]
```

**Method call graph** (main execution path for .xls):
```
execute()                          [BaseComponent]
  -> _process()                    [FileInputExcel:156]
       -> _validate_config()       [FileInputExcel:81]
       -> _detect_excel_format()   [FileInputExcel:405]
       -> _process_xls_file()      [FileInputExcel:765]
            -> _get_sheets_to_read_xlrd() [FileInputExcel:420]
                 -> xlrd.open_workbook()
            -> _read_xls_sheet()   [FileInputExcel:881]
                 -> _build_converters_dict() [FileInputExcel:232]
                 -> pd.read_excel(engine='xlrd')
            -> pd.concat()
            -> _update_stats()     [BaseComponent:306]
  -> _update_global_map()          [BaseComponent:298]
```

**NEVER called** (dead code):
```
_build_dtype_dict()               # Replaced by _build_converters_dict()
_apply_advanced_separators()      # Should be called after pd.read_excel()
_apply_trimming()                 # Should be called after pd.read_excel()
_apply_date_conversion()          # Should be called after pd.read_excel()
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filepath` | Mapped + Implemented | -- |
| `PASSWORD` | `password` | Mapped + **Not decrypted** | P1 (implement decryption) |
| `VERSION_2007` | `version_2007` | Mapped + **Not used** | P3 (format detected from extension) |
| `ALL_SHEETS` | `all_sheets` | Mapped + Implemented | -- |
| `SHEETLIST` | `sheetlist` | Mapped + Implemented | -- |
| `HEADER` | `header` | Mapped + Implemented | -- (**fix default from 1 to 0**) |
| `FOOTER` | `footer` | Mapped + Implemented | -- |
| `LIMIT` | `limit` | Mapped + Implemented | -- |
| `AFFECT_EACH_SHEET` | `affect_each_sheet` | Mapped + **Not used** | P2 |
| `FIRST_COLUMN` | `first_column` | Mapped + Implemented | -- |
| `LAST_COLUMN` | `last_column` | Mapped + Implemented | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped + Implemented | -- (**fix default from false to true**) |
| `SUPPRESS_WARN` | `suppress_warn` | Mapped + Implemented | -- |
| `NOVALIDATE_ON_CELL` | `novalidate_on_cell` | Mapped + **Not used** | P3 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | Mapped + **Dead code** | P0 (wire up) |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | Mapped + **Dead code** | P0 (wire up) |
| `DECIMAL_SEPARATOR` | `decimal_separator` | Mapped + **Dead code** | P0 (wire up) |
| `TRIMALL` | `trimall` | Mapped + **Dead code** | P0 (wire up) |
| `TRIMSELECT` | `trim_select` | Mapped + **Dead code** | P0 (wire up) |
| `CONVERTDATETOSTRING` | `convertdatetostring` | Mapped + **Dead code** | P0 (wire up) |
| `DATESELECT` | `date_select` | Mapped + **Dead code** | P0 (wire up) |
| `READ_REAL_VALUE` | `read_real_value` | Mapped + **Not used** | P3 |
| `STOPREAD_ON_EMPTYROW` | `stopread_on_emptyrow` | Mapped + **Not used** | P1 |
| `INCLUDE_PHONETICRUNS` | `include_phoneticruns` | Mapped + **Not used** | P3 |
| `GENERATION_MODE` | `generation_mode` | Mapped + **Not used** | P3 |
| `CONFIGURE_INFLATION_RATIO` | `configure_inflation_ratio` | Mapped + **Not used** | P3 |
| `INFLATION_RATIO` | `inflation_ratio` | Mapped + **Not used** | P3 |
| `ENCODING` | `encoding` | Mapped + **Not used by engine** | P3 (xls only, xlsx has embedded encoding) |
| `SHEET_NAME` | `sheet_name` | Mapped + **Not used** | P3 |
| `EXECUTION_MODE` | `execution_mode` | Mapped + **Not used** | P3 |
| `CHUNK_SIZE` | `chunk_size` | Mapped + Used by BaseComponent | -- |
| `TSTATCATCHER_STATS` | -- | **Not Mapped** | -- (rarely used) |
| `LABEL` | -- | **Not Mapped** | -- (cosmetic) |

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

### Engine _build_converters_dict() (for pd.read_excel converters param)

| Type Input | Converter Function | Return Type | NaN Handling |
|------------|-------------------|-------------|-------------|
| `str` / `id_String` | `str_converter()` | `str` | Returns `""` for NaN/None |
| `int` / `id_Integer` / `id_Long` | `int_converter()` | `int` or `None` | Returns `None` for NaN/empty |
| `float` / `id_Float` / `id_Double` | `float_converter()` | `float` or `None` | Returns `None` for NaN/empty |
| `bool` / `id_Boolean` | `bool_converter()` | `bool` or `None` | Returns `None` for NaN/empty. Recognizes `"true"`, `"1"`, `"yes"`, `"on"`. |
| `date` / `id_Date` | `date_converter()` | `datetime` or `str` or `None` | Returns `None` for NaN/empty. Attempts `pd.to_datetime()`, falls back to string. |
| `Decimal` / `id_BigDecimal` | `decimal_converter()` | `Decimal` or `None` | Returns `None` for NaN/empty. Uses `Decimal(str(x))`. |

### Engine _build_dtype_dict() (DEAD CODE -- never called)

| Type Input | Pandas Dtype | Notes |
|------------|-------------|-------|
| `id_String` / `str` | `object` | Correct |
| `id_Integer` / `int` | `Int64` (nullable) | Uses nullable integer |
| `id_Long` / `long` | `Int64` (nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | Correct |
| `id_Double` / `double` | `float64` | Correct |
| `id_Boolean` / `bool` | `object` | Correct -- avoids NaN issues with bool dtype |
| `id_Date` / `date` | `object` | Correct -- read as string for later conversion |
| `id_BigDecimal` / `Decimal` | `object` | Correct |

**Why converters are used over dtype**: The docstring on line 236-238 explains: "Converters give us precise control over column types during reading, unlike dtype which can be ignored by read_excel() for auto-detected types." This is correct -- pandas `read_excel()` sometimes overrides dtype hints when auto-detecting types from cell data. Converters are applied cell-by-cell and cannot be overridden.

### Engine validate_schema() (post-read conversion in base_component.py)

| Type Input | Pandas Dtype | Conversion Method |
|------------|-------------|-------------------|
| `id_String` / `str` | `object` | No conversion |
| `id_Integer` / `int` | `int64` (non-nullable) | `pd.to_numeric(errors='coerce')` then `fillna(0).astype('int64')` |
| `id_Long` / `long` | `int64` (non-nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | `pd.to_numeric(errors='coerce')` |
| `id_Double` / `double` | `float64` | Same as Float |
| `id_Boolean` / `bool` | `bool` | `.astype('bool')` |
| `id_Date` / `date` | `datetime64[ns]` | `pd.to_datetime()` -- no format specification |
| `id_BigDecimal` / `decimal` | `object` | No conversion in validate_schema |

**Key observation**: When converters are used (as in FileInputExcel), `validate_schema()` becomes partially redundant for type conversion. The converters handle type casting during read, and `validate_schema()` may re-cast already-converted values. This double-conversion is wasteful but not harmful for most types. For `date` types, converters return `datetime` objects that `validate_schema()` then re-parses via `pd.to_datetime()` -- this is redundant but safe.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 81-154)

This method validates:
- `filepath` is present, is a string, and is non-empty (required)
- `password` is a string (if present)
- Boolean fields: `all_sheets`, `die_on_error`, `suppress_warn`, `advanced_separator`, `trimall`, `convertdatetostring`, `stopread_on_emptyrow` (if present)
- Numeric fields: `header`, `first_column` must be positive integers (if present)
- `footer` must be a non-negative integer (if present)
- `limit` must be a positive integer, empty string, or None (if present)
- List fields: `sheetlist`, `trim_select`, `date_select` must be lists (if present)
- String fields: `thousands_separator`, `decimal_separator` must be strings or None (if present)

**Unlike tFileInputDelimited, this method IS called** from `_process()` on line 175. Configuration errors are caught and either raised as `ConfigurationError` or logged based on `die_on_error`.

**Not validated**: `affect_each_sheet`, `novalidate_on_cell`, `read_real_value`, `include_phoneticruns`, `generation_mode`, `configure_inflation_ratio`, `inflation_ratio`, `encoding`, `version_2007`.

### `_build_converters_dict()` (Lines 232-343)

This is the primary type enforcement mechanism. Unlike `_build_dtype_dict()` (which sets expectations for pandas but can be overridden by auto-detection), converters are applied cell-by-cell and provide guaranteed type conversion.

Key design choices:
1. **Closure factories**: Each type uses a `make_*_converter()` factory function that returns a closure. This avoids Python's late-binding closure pitfall where all converters would reference the last loop iteration's variables.
2. **NaN handling**: Every converter starts with `if pd.isna(x) or x is None:` check.
3. **String converter for dates**: When a `str`-typed column contains datetime values (which Excel auto-detects), the converter formats them as `dd-mm-yyyy`. This hardcoded format may not match Talend's expected format.
4. **Integer via float**: `int(float(str(x)))` handles Excel's tendency to store integers as floats (e.g., `30.0` -> `30`).

### `_get_sheets_to_read()` (Lines 509-606)

This method implements the sheet selection logic for .xlsx files. It handles four scenarios:

1. **`all_sheets=true` + empty sheetlist**: Return all sheet names from workbook
2. **`all_sheets=true` + non-empty sheetlist**: Filter sheets by name/regex, with partial match fallback
3. **`all_sheets=false` + non-empty sheetlist**: Return first matching sheet only
4. **`all_sheets=false` + empty sheetlist**: Return first sheet in workbook

**Known issues**:
- Partial match fallback (lines 548-553) is not Talend behavior
- `re.search()` instead of `re.fullmatch()` for regex matching
- `list(set())` deduplication loses order
- Context variable resolution via `self.context_manager.resolve_string()` is correctly applied to sheet names

### `_process()` (Lines 156-230)

Main entry point. Flow:
1. Log processing start
2. Validate config via `_validate_config()`
3. Extract and clean filepath (strip quotes)
4. Check file existence
5. Detect Excel format via `_detect_excel_format()`
6. Dispatch to `_process_xls_file()` or `_process_xlsx_file()`
7. Catch and wrap exceptions

**Design note**: The `die_on_error` flag is checked at multiple levels:
- `_process()` line 197: for empty filepath
- `_process()` line 207: for missing file
- `_process_xlsx_file()` line 849: for no sheets found
- `_process_xlsx_file()` line 873: for generic errors
- `_process_xls_file()` line 776: for no sheets found
- `_process_xls_file()` line 819: for generic errors

### `_read_sheet()` (Lines 672-763)

Reads a single .xlsx sheet using `pd.read_excel()`. This is the core reading method. Key parameters passed to `pd.read_excel()`:
- `sheet_name`: specific sheet to read
- `header`: 0-based row for column names (converted from 1-based Talend)
- `names`: column names from output schema
- `nrows`: row limit
- `usecols`: column range restriction
- `skipfooter`: footer rows to skip
- `na_filter=False`: prevent NaN auto-detection
- `keep_default_na=False`: prevent special value NaN treatment
- `date_format=None`: prevent date auto-parsing
- `converters`: type conversion functions from `_build_converters_dict()`

**No post-processing calls**: After `pd.read_excel()` returns, the DataFrame is returned directly. `_apply_advanced_separators()`, `_apply_trimming()`, and `_apply_date_conversion()` are NEVER called here.

---

## Appendix F: .xls vs .xlsx Handling Comparison

| Aspect | .xls Path | .xlsx Path |
|--------|-----------|------------|
| **Detection** | `_detect_excel_format()` returns `'xlrd'` for `.xls` extension | `_detect_excel_format()` returns `'openpyxl'` for `.xlsx/.xlsm/.xlsb` |
| **Orchestrator** | `_process_xls_file()` | `_process_xlsx_file()` |
| **Sheet discovery** | `_get_sheets_to_read_xlrd()`: opens via `xlrd.open_workbook(on_demand=True)`, reads names, releases | `_get_sheets_to_read()`: uses `wb.sheetnames` from already-opened openpyxl workbook |
| **Sheet reading** | `_read_xls_sheet()`: `pd.read_excel(engine='xlrd')` | `_read_sheet()`: `pd.read_excel()` (default engine) |
| **Password** | Received as parameter but never forwarded to xlrd | `_decode_password()` called but result not passed to openpyxl |
| **Streaming** | Not supported -- always batch mode | Supported: `_read_streaming()` activated for files > 3GB |
| **File opened** | Once by xlrd for sheet names + once per sheet by pandas | Once by openpyxl for sheet names + once per sheet by pandas |
| **Error handling** | Identical pattern: try/except with die_on_error check | Identical pattern: try/except with die_on_error check |
| **Post-processing** | None (dead methods not called) | None (dead methods not called) |
| **Statistics** | `_update_stats()` per sheet | `_update_stats()` per sheet (batch) or per chunk (streaming) |

---

## Appendix G: Dead Code Impact Analysis

The three dead post-processing methods represent features that Talend users may configure but that will silently not work:

### `_apply_advanced_separators()` -- Impact: Medium
**Scenario**: European company uses `.` as thousands separator and `,` as decimal separator. Excel file contains `"1.234,56"` in numeric columns.
**Expected (Talend)**: ADVANCED_SEPARATOR=true converts `"1.234,56"` to `1234.56` for numeric processing.
**Actual (v1)**: The raw string `"1.234,56"` is passed to converters. If the column type is `float`, `float("1.234,56")` will raise `ValueError`, and the converter returns `None`. The numeric value is silently lost.

### `_apply_trimming()` -- Impact: Low-Medium
**Scenario**: Excel file has cells with leading/trailing spaces (e.g., `"  John  "`).
**Expected (Talend)**: TRIMALL=true strips whitespace from all string columns, producing `"John"`.
**Actual (v1)**: The untrimmed string `"  John  "` is passed through. Downstream joins, lookups, or comparisons may fail due to whitespace mismatch.

### `_apply_date_conversion()` -- Impact: Medium
**Scenario**: Excel file has a date column that should be output as a formatted string (e.g., `"03-21-2026"` instead of a datetime object).
**Expected (Talend)**: CONVERTDATETOSTRING=true with pattern `"MM-dd-yyyy"` converts dates to strings.
**Actual (v1)**: If the schema type is `date`, the converter returns a `datetime` object. If the schema type is `str`, the converter uses a hardcoded `dd-mm-yyyy` format (line 269), which may differ from the configured DATESELECT pattern.

---

## Appendix H: Column Letter Conversion

The `_column_letter_to_index()` method (lines 392-403) converts Excel column letters to 1-based numeric indices:

| Input | Output | Calculation |
|-------|--------|-------------|
| `""` | `1` | Empty string returns default 1 |
| `"A"` | `1` | 0*26 + (65-65+1) = 1 |
| `"B"` | `2` | 0*26 + (66-65+1) = 2 |
| `"Z"` | `26` | 0*26 + (90-65+1) = 26 |
| `"AA"` | `27` | (0*26 + 1)*26 + 1 = 27 |
| `"AZ"` | `52` | (0*26 + 1)*26 + 26 = 52 |
| `"BA"` | `53` | (0*26 + 2)*26 + 1 = 53 |
| `"ZZ"` | `702` | (0*26 + 26)*26 + 26 = 702 |
| `"AAA"` | `703` | ((0*26 + 1)*26 + 1)*26 + 1 = 703 |

The algorithm is correct for all standard Excel column ranges (A-XFD for .xlsx, A-IV for .xls). The method handles case conversion via `.upper()` on line 399.

**Edge case**: Non-alphabetic characters (e.g., `"A1"`) are not validated. `ord('1') - ord('A') + 1` = -16, which produces incorrect negative indices. The caller should validate that `last_column` is purely alphabetic before calling this method (partially done via `last_column.isalpha()` check on line 707/916).

---

## Appendix I: Sheet Selection Logic Detailed Walkthrough

### Scenario Matrix

The sheet selection logic is the most complex part of this component, with 8 distinct code paths across two methods. Here is every scenario and its behavior:

#### `_get_sheets_to_read()` (.xlsx path)

| # | `all_sheets` | `sheetlist` | `use_regex` | Available Sheets | Expected Result | Actual Result | Correct? |
|---|-------------|-------------|------------|------------------|-----------------|---------------|----------|
| 1 | `true` | `[]` | N/A | `["Sheet1", "Sheet2", "Sheet3"]` | All 3 sheets | All 3 sheets | Yes |
| 2 | `true` | `[{"sheetname": "Sheet1"}]` | `false` | `["Sheet1", "Sheet2"]` | `["Sheet1"]` | `["Sheet1"]` | Yes |
| 3 | `true` | `[{"sheetname": "Sheet1"}, {"sheetname": "Sheet2"}]` | `false` | `["Sheet1", "Sheet2", "Sheet3"]` | `["Sheet1", "Sheet2"]` | `["Sheet1", "Sheet2"]` (may be reordered by `set()`) | **Partial** -- order may differ |
| 4 | `true` | `[{"sheetname": "Sheet.*", "use_regex": true}]` | `true` | `["Sheet1", "Data"]` | `["Sheet1"]` | `["Sheet1"]` | Yes |
| 5 | `true` | `[{"sheetname": "Data", "use_regex": false}]` | `false` | `["DataSheet", "OldData"]` | `[]` (no exact match) | `["DataSheet", "OldData"]` (partial match) | **No** -- partial match is not Talend behavior |
| 6 | `false` | `[{"sheetname": "Sheet2"}]` | `false` | `["Sheet1", "Sheet2", "Sheet3"]` | `["Sheet2"]` | `["Sheet2"]` | Yes |
| 7 | `false` | `[]` | N/A | `["Sheet1", "Sheet2"]` | `["Sheet1"]` (first sheet) | `["Sheet1"]` | Yes |
| 8 | `false` | `[{"sheetname": "Missing"}]` | `false` | `["Sheet1", "Sheet2"]` | `["Sheet1"]` (fallback) | `["Sheet1"]` (partial match might return something else) | **Depends** -- if partial match finds something |
| 9 | `true` | `[{"sheetname": "[invalid", "use_regex": true}]` | `true` | `["Sheet1"]` | Warning logged, skip entry | Warning logged, no crash | Yes |
| 10 | `false` | `[{"sheetname": "Data_\\d+", "use_regex": true}]` | `true` | `["Data_2023", "Data_2024", "Info"]` | `["Data_2023"]` (first match only) | `["Data_2023"]` (line 587: `matching_sheets[:1]`) | Yes |

#### Key behavioral differences from Talend:

1. **Scenario 5**: Partial match fallback is the biggest behavioral divergence. Talend would return an empty result and log a warning. V1 returns all sheets containing "Data" as a substring.

2. **Scenario 3**: `list(set())` may reorder sheets. Talend preserves workbook order.

3. **Scenario 10**: The `[:1]` slice on line 587 correctly limits to the first match when `all_sheets=false`, but the order of `matching_sheets` depends on workbook sheet order (which is preserved by `wb.sheetnames`), so this is correct.

### Context Variable Resolution in Sheet Names

Sheet names containing context variables are resolved before matching. The resolution flow:

```
Config: {"sheetlist": [{"sheetname": "${context.target_sheet}", "use_regex": false}]}
                                    |
                                    v
_get_sheets_to_read() line 531-533:
  if hasattr(self, 'context_manager') and self.context_manager:
      resolved_sheet_name = self.context_manager.resolve_string(sheet_name)
                                    |
                                    v
resolved_sheet_name = "Sales_Q1"    (from context variable)
                                    |
                                    v
Match against available_sheets: ["Sales_Q1", "Sales_Q2"] -> found "Sales_Q1"
```

This works correctly. The `hasattr(self, 'context_manager')` check is defensive -- `context_manager` is always set in `BaseComponent.__init__()`, but may be None if no context manager is provided.

---

## Appendix J: Error Handling Flow Diagram

### Normal Execution Path (.xlsx)

```
_process()
  |
  +-> _validate_config() returns errors?
  |     |
  |     +-> Yes: die_on_error?
  |     |     +-> True:  raise ConfigurationError
  |     |     +-> False: return {'main': empty_df}, stats=(0,0,0)
  |     |
  |     +-> No: continue
  |
  +-> filepath empty?
  |     +-> Same die_on_error branch as above
  |
  +-> file exists?
  |     |
  |     +-> No: die_on_error?
  |     |     +-> True:  raise FileOperationError
  |     |     +-> False: return {'main': empty_df}, stats=(0,0,0), log warning
  |     |
  |     +-> Yes: continue
  |
  +-> _detect_excel_format() -> 'openpyxl'
  |
  +-> _process_xlsx_file()
        |
        +-> openpyxl.load_workbook() fails?
        |     +-> Caught by outer except -> die_on_error branch
        |
        +-> _get_sheets_to_read() returns []?
        |     +-> die_on_error?
        |           +-> True:  raise FileOperationError("No sheets found")
        |           +-> False: return {'main': empty_df}, stats=(0,0,0)
        |
        +-> file_size > 3GB and HYBRID mode?
        |     +-> Yes: _read_streaming()
        |     +-> No:  _read_batch()
        |
        +-> _read_batch()
              |
              +-> for each sheet:
              |     +-> _read_sheet()
              |     |     +-> pd.read_excel() fails?
              |     |           +-> log error, return empty_df (sheet skipped)
              |     |
              |     +-> df not empty? -> append to all_data, update stats
              |
              +-> pd.concat(all_data) or empty_df
              +-> return {'main': result_df}
```

### Error Propagation

| Error Source | Exception Type | die_on_error=true | die_on_error=false |
|-------------|---------------|-------------------|-------------------|
| Config validation | `ConfigurationError` | Raised to caller | Empty DF returned |
| Missing file | `FileOperationError` | Raised to caller | Empty DF returned, warning logged |
| No sheets found | `FileOperationError` | Raised to caller | Empty DF returned |
| openpyxl open fails | `FileOperationError` (wrapped) | Raised to caller | Empty DF returned |
| pd.read_excel fails (single sheet) | Caught in `_read_sheet()` | **Not propagated** -- empty DF for sheet | Empty DF for sheet |
| pd.read_excel fails (all sheets) | Returns empty concat | Result is empty DF | Result is empty DF |
| Generic exception in `_process()` | `ComponentExecutionError` (wrapped) | Always raised | Always raised |

**Key observation**: Sheet-level errors in `_read_sheet()` are ALWAYS caught and return empty DataFrame, regardless of `die_on_error`. This means a single corrupt sheet will not fail the entire job even when `die_on_error=true`. This differs from Talend where `DIE_ON_ERROR=true` would stop the job on any sheet error.

---

## Appendix K: Converter vs Engine Default Comparison

This table compares the defaults set by the converter (when a Talend job does not explicitly set a parameter) against the engine defaults (when a config key is missing). Both should match Talend defaults.

| Parameter | Talend Default | Converter Default | Engine Default | Match? | Risk |
|-----------|---------------|------------------|----------------|--------|------|
| `all_sheets` | `false` | `false` (line 2880) | `True` (line 429, 513) | **No** | Engine reads all sheets by default; converter sets false. When converter is used, this is fine. But if engine is used directly with missing config, it reads all sheets. |
| `header` | `0` | `1` (line 2900) | `1` (line 677, 886) | **Converter wrong** | Both converter and engine default to 1, but Talend defaults to 0. First data row silently dropped. |
| `footer` | `0` | `0` (line 2901) | `0` (line 678, 887) | Yes | |
| `limit` | `0` (unlimited) | `""` (line 2902) | `""` (line 679, 888) | Yes | Empty string = unlimited in both. |
| `first_column` | `1` | `1` (line 2904) | `1` (line 680, 889) | Yes | |
| `last_column` | `""` (all) | `""` (line 2905) | `""` (line 681, 890) | Yes | |
| `die_on_error` | `true` | `false` (line 2908) | `False` (line 191) | **Both wrong** | Errors silently suppressed instead of failing the job. |
| `suppress_warn` | `false` | `false` (line 2909) | `False` (line 192) | Yes | |
| `advanced_separator` | `false` | `false` (line 2913) | `False` (line 612) | Yes | (but dead code) |
| `thousands_separator` | `","` | `","` (line 2917) | `","` (line 615) | Yes | (but dead code) |
| `decimal_separator` | `"."` | `"."` (line 2918) | `"."` (line 616) | Yes | (but dead code) |
| `trimall` | `false` | `false` (line 2921) | `False` (line 631) | Yes | (but dead code) |
| `convertdatetostring` | `false` | `false` (line 2941) | `False` (line 653) | Yes | (but dead code) |
| `stopread_on_emptyrow` | `false` | `false` (line 2964) | `False` (line 682) | Yes | (but never used) |
| `encoding` | `"UTF-8"` | `"UTF-8"` (line 2974) | Not used | Yes | Encoding embedded in xlsx format |

**Summary**: Two critical default mismatches: `header` (should be 0, defaults to 1) and `die_on_error` (should be true, defaults to false). Both mismatches cause silent data quality issues.

---

## Appendix L: Dependency Analysis

### Runtime Dependencies

| Library | Version Required | Purpose | Import Location |
|---------|-----------------|---------|-----------------|
| `openpyxl` | >= 3.0 | Read .xlsx files | Line 13: `import openpyxl` |
| `pandas` | >= 1.3 | DataFrame operations, `pd.read_excel()` | Line 14: `import pandas as pd` |
| `xlrd` | >= 2.0 | Read .xls files | Line 15: `import xlrd` |
| `re` (stdlib) | -- | Regex sheet matching | Line 8: `import re` |
| `os` (stdlib) | -- | File existence check, path operations | Line 7: `import os` |
| `datetime` (stdlib) | -- | Date handling in converters | Line 9: `from datetime import datetime` |
| `decimal` (stdlib) | -- | BigDecimal support | Line 10: `from decimal import Decimal` |
| `logging` (stdlib) | -- | Structured logging | Line 6: `import logging` |

### Missing Dependencies

| Library | Purpose | Why Needed |
|---------|---------|-----------|
| `msoffcrypto-tool` | Decrypt password-protected Excel files | openpyxl cannot open encrypted files. `msoffcrypto` decrypts to a BytesIO buffer. Currently not imported or listed in requirements. |

### Internal Dependencies

| Module | Class/Function | Purpose |
|--------|---------------|---------|
| `...base_component` | `BaseComponent` | Parent class: `execute()`, `_update_stats()`, `_update_global_map()`, `validate_schema()` |
| `...base_component` | `ExecutionMode` | Enum: `BATCH`, `STREAMING`, `HYBRID` |
| `...exceptions` | `ConfigurationError` | Raised for invalid config |
| `...exceptions` | `FileOperationError` | Raised for file read failures |
| `...exceptions` | `ComponentExecutionError` | Raised for generic processing failures |

---

## Appendix M: Comparison with tFileInputDelimited Audit

This section compares the audit findings for `tFileInputExcel` against the gold-standard `tFileInputDelimited` audit to identify patterns and unique issues.

### Shared Issues (Cross-Cutting)

| Issue | tFileInputDelimited | tFileInputExcel |
|-------|-------------------|-----------------|
| `_update_global_map()` undefined `value` | BUG-FID-001 (P0) | BUG-FIE-001 (P0) -- same bug |
| `GlobalMap.get()` undefined `default` | BUG-FID-002 (P0) | BUG-FIE-002 (P0) -- same bug |
| No REJECT flow | ENG-FID-001 (P0) | ENG-FIE-001 (P0) -- same gap |
| Schema type format (Python vs Talend) | CONV-FID-004 (P1) | CONV-FIE-004 (P2) -- same gap |
| No ERROR_MESSAGE globalMap | ENG-FID-005 (P1) | ENG-FIE-007 (P1) -- same gap |
| Zero v1 unit tests | TEST-FID-001 (P0) | TEST-FIE-001 (P0) -- same gap |

### Unique to tFileInputExcel

| Issue | Why Unique |
|-------|-----------|
| Dead post-processing methods (ENG-FIE-002) | tFileInputDelimited has dead `_validate_config()` but not dead feature methods |
| Password not implemented (ENG-FIE-003) | tFileInputDelimited has no password feature |
| Partial match fallback (ENG-FIE-009) | Sheet matching is unique to Excel |
| Code duplication (DUP-FIE-001/002) | Dual engine (.xls/.xlsx) creates duplication |
| CURRENT_SHEET not set (ENG-FIE-006) | Multi-sheet is unique to Excel |
| AFFECT_EACH_SHEET not implemented (ENG-FIE-008) | Per-sheet header/footer is unique to Excel |

### Structural Comparison

| Dimension | tFileInputDelimited | tFileInputExcel |
|-----------|-------------------|-----------------|
| Engine lines | 575 | 1023 (78% larger) |
| Converter approach | Generic mapper (deprecated) | Dedicated parser (correct) |
| Converter extraction rate | 40% (12/30) | 85% (28/33) |
| Dead code | `_validate_config()` (60 lines) | 4 methods (95 lines) |
| Total issues | 40 | 48 |
| P0 issues | 3 | 5 |
| P1 issues | 13 | 13 |

**Conclusion**: tFileInputExcel has a significantly better converter (dedicated parser, 85% extraction rate) but a worse engine (more dead code, unimplemented features despite being extracted, dual-engine duplication). The converter represents best-practice that tFileInputDelimited should adopt. The engine has more surface area and correspondingly more issues.

---

## Appendix N: Risk Assessment for Production Deployment

### High Risk Scenarios

| Scenario | Likelihood | Impact | Mitigation |
|----------|-----------|--------|-----------|
| Job uses TRIMALL=true | High (common setting) | Untrimmed data causes downstream failures | Wire up `_apply_trimming()` (5-minute fix) |
| Job uses DIE_ON_ERROR default | High (most jobs don't set it explicitly) | Errors silently suppressed, incomplete output | Fix default to `true` |
| Job uses password-protected file | Medium | Job fails with unhelpful error | Implement msoffcrypto integration |
| Job uses HEADER=0 (Talend default) | Medium (converter overrides to 1) | First data row silently dropped | Fix converter default to 0 |
| Job uses ADVANCED_SEPARATOR | Low-Medium (European data) | Numeric values lost (converted to None) | Wire up `_apply_advanced_separators()` |
| Job uses CONVERTDATETOSTRING | Low-Medium | Dates remain as objects instead of formatted strings | Wire up `_apply_date_conversion()` |
| Job uses regex sheet matching | Low | Regex matches more than intended (search vs fullmatch) | Change to fullmatch() |
| Job relies on CURRENT_SHEET | Low-Medium (multi-sheet jobs) | Downstream components get null for sheet name | Set globalMap variable per sheet |
| GlobalMap.get() called | High (standard operation) | NameError crash | Fix get() method signature |

### Safe Scenarios (Working Correctly)

| Scenario | Confidence |
|----------|-----------|
| Basic .xlsx read with schema | High -- core path well-implemented |
| Basic .xls read with schema | High -- xlrd path mirrors xlsx path |
| Multi-sheet reading (all_sheets=true, no regex) | High |
| Header/footer skip | High -- correctly converts 1-based to 0-based |
| Row limit | High -- nrows passed directly to pandas |
| Column range with numeric FIRST/LAST | High |
| Context variables in filepath | High -- resolved by BaseComponent.execute() |
| Type conversion via converters | High -- comprehensive converter functions |
| File not found handling | High -- proper die_on_error branching |
| Streaming mode for large files | Medium -- works but footer may have issues |

### Production Deployment Recommendation

**Do NOT deploy to production without**:
1. Fixing BUG-FIE-001 and BUG-FIE-002 (cross-cutting GlobalMap crashes)
2. Wiring up dead post-processing methods (ENG-FIE-002)
3. Fixing DIE_ON_ERROR default (CONV-FIE-001 + ENG-FIE-004)
4. Fixing HEADER default (CONV-FIE-002)
5. Creating at minimum P0 test suite

**Can deploy with known limitations for**:
- Jobs without password-protected files
- Jobs without STOPREAD_ON_EMPTYROW
- Jobs without AFFECT_EACH_SHEET=false
- Jobs without regex sheet matching (or with full-string regex patterns)
- Jobs that explicitly set HEADER and DIE_ON_ERROR

---

## Appendix O: String Converter Edge Cases

The string converter in `_build_converters_dict()` (lines 253-278) is the most complex converter and has several edge cases worth documenting:

### Date-to-String Formatting (Lines 263-269)

When a column has schema type `str` but the Excel cell contains a date value (Excel auto-detects dates), the converter formats it as `dd-mm-yyyy`:

```python
day = x.day
month = x.month
year = x.year
return f"{day:02d}-{month:02d}-{year}"
```

**Issues**:
1. The format `dd-mm-yyyy` is hardcoded. Talend's `DATESELECT` pattern (e.g., `"MM-dd-yyyy"`) is never consulted because the dead `_apply_date_conversion()` method would handle that. The format is also European (day-month-year) which may not match American expectations (month-day-year).
2. The year is formatted without zero-padding and without a width specifier. Years before 1000 AD would produce 1-3 digit years (e.g., `01-01-99` for year 99). This is an edge case but technically incorrect.
3. Time components are completely discarded. A datetime like `2026-03-21 14:30:00` becomes `"21-03-2026"` with no time information. Talend's behavior depends on the date pattern, and time components are preserved if the pattern includes them.

### Whole Number Formatting (Lines 273-275)

When a `str`-typed column contains a number (common in Excel -- numeric cells read as float by openpyxl):

```python
if isinstance(x, (int, float)) and float(x).is_integer():
    return str(int(x))  # Convert 30.0 to "30", 50000.0 to "50000"
else:
    return str(x)
```

**Issues**:
1. This correctly handles the common case of Excel storing integers as floats (e.g., `30.0` -> `"30"`). This matches Talend behavior.
2. For non-integer floats (e.g., `3.14`), `str(x)` produces Python's default float representation which may differ from Talend's. For example, `str(3.1000000000000001)` produces `"3.1"` in Python (due to repr rounding), while Talend might produce `"3.1000000000000001"`.
3. Very large numbers may use scientific notation: `str(1e20)` produces `"1e+20"`, which Talend would render as `"100000000000000000000"`.
4. NaN check uses `pd.isna(x)` which covers `float('nan')`, `np.nan`, and `pd.NA`. However, the string `"nan"` (which Excel could produce as a text cell) would pass through the NaN check and be returned as `"nan"` -- this matches Talend behavior.

### Boolean-to-String

No special handling for booleans in the string converter. A boolean `True` from an Excel cell would go through `str(True)` producing `"True"`. Talend produces `"true"` (lowercase). This is a minor behavioral difference.

### None vs Empty String

The converter returns `""` (empty string) for NaN/None values:
```python
if pd.isna(x) or x is None:
    return ""
```

This matches Talend behavior where empty cells produce empty strings. However, if `keep_default_na=False` is set (which it is, line 749), pandas will not convert empty cells to NaN -- they will already be empty strings. The NaN check is defensive and handles edge cases where openpyxl returns None for empty cells.

---

## Appendix P: Streaming Mode Analysis

### When Streaming Activates

Streaming mode is controlled by two conditions (file_input_excel.py lines 860-865):

```python
if (self.execution_mode == ExecutionMode.HYBRID and file_size_mb > self.MEMORY_THRESHOLD_MB):
    return self._read_streaming(wb, sheets_to_read)
else:
    return self._read_batch(wb, sheets_to_read)
```

- `MEMORY_THRESHOLD_MB = 3072` (3GB) -- inherited from `BaseComponent`
- `execution_mode` defaults to `HYBRID` if not specified

**Typical Excel file sizes**:
- Most business Excel files: 1-50 MB
- Large data exports: 50-500 MB
- Very large files: 500 MB - 2 GB
- Extreme files: 2+ GB (rare, usually converted to CSV)

The 3GB threshold means streaming mode will almost never activate for Excel files. This is arguably correct since Excel files are inherently smaller than CSVs (binary format, compression in .xlsx), but it means the streaming code path is rarely exercised.

### Streaming Behavior

The `_read_streaming()` method (lines 998-1022) implements a generator-based approach:

```python
def sheet_generator() -> Iterator[pd.DataFrame]:
    for sheet_name in sheets_to_read:
        df = self._read_sheet(wb, sheet_name)
        if not df.empty:
            chunk_size = self.chunk_size
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size].copy()
                self._update_stats(len(chunk), len(chunk), 0)
                yield chunk
```

**Key observations**:
1. **Entire sheet is read into memory first**: `self._read_sheet(wb, sheet_name)` reads the entire sheet into a DataFrame, then chunks it. This means streaming only helps with downstream processing memory, NOT with reading memory. True streaming would use openpyxl's `ws.iter_rows()` or pandas `chunksize` parameter.
2. **Chunking is intra-sheet**: Each sheet is chunked independently. This is correct for maintaining data boundaries.
3. **Stats updated per chunk**: `_update_stats()` is called for each chunk, which correctly accumulates totals.
4. **`.copy()` on each chunk**: `df.iloc[i:i+chunk_size].copy()` creates an independent copy of each chunk. This prevents downstream mutations from affecting the original DataFrame but doubles memory usage temporarily.
5. **Return format differs**: Batch mode returns `{'main': DataFrame}`. Streaming mode returns `{'main': generator, 'is_streaming': True}`. Downstream components must handle both formats.

### Streaming Mode Limitations

| Limitation | Impact | Severity |
|-----------|--------|----------|
| Full sheet read before chunking | No memory savings during read phase | Medium |
| Footer skip may fail with chunks | Last chunk may include footer rows | Low (pandas handles skipfooter before chunking) |
| No per-sheet streaming | Cannot stream a single very-wide sheet | Low (Excel has column limits) |
| `is_streaming` flag must be handled | Downstream components must check for generator | Medium |
| `_apply_trimming()` etc. never called | Post-processing dead code affects streaming equally | High (same as batch) |

### .xls Files Never Stream

The `_process_xls_file()` method (lines 765-825) has no streaming path. It always uses batch mode regardless of file size. The streaming decision in `_process_xlsx_file()` (line 860) only applies to .xlsx files. Large .xls files will always be loaded entirely into memory.

---

## Appendix Q: pd.read_excel() Parameter Reference

Both `_read_sheet()` and `_read_xls_sheet()` pass a specific set of parameters to `pd.read_excel()`. Here is the complete mapping with rationale:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `filepath` | Cleaned file path (quotes stripped) | First positional argument |
| `sheet_name` | Resolved sheet name | Specific sheet to read |
| `engine` | `'xlrd'` (.xls) or omitted (.xlsx) | Format-specific engine selection |
| `header` | `header-1` if `header > 0` else `None` | Converts 1-based Talend to 0-based pandas. `None` means "no header row" -- pandas assigns integer column indices. |
| `names` | `expected_col_names` (from schema) or `None` | Overrides column names from header with schema-defined names. When set with `header=N`, pandas reads row N as header but replaces names with these. |
| `nrows` | `int(limit)` or `None` | Row limit. `None` = read all rows. |
| `usecols` | Column index list or `None` | Restricts which columns are read. Reduces memory for wide sheets. |
| `skipfooter` | `footer` (int) | Number of rows to skip at the end. Requires Python engine. |
| `na_filter` | `False` | **Critical**: Prevents pandas from interpreting "NA", "N/A", "#N/A", "null", "None", etc. as NaN. Without this, data containing these strings would lose information. |
| `keep_default_na` | `False` | **Critical**: Complementary to `na_filter`. Prevents default NaN interpretation. Together with `na_filter=False`, ensures raw cell values are preserved. |
| `date_format` | `None` | Prevents pandas from auto-parsing date strings. Date handling is done by converters instead. |
| `converters` | Converter dict from `_build_converters_dict()` | Per-column type conversion functions. Takes precedence over `dtype`. |

**Parameters NOT passed** (and their implications):

| Parameter | Default | Implication |
|-----------|---------|-------------|
| `dtype` | Auto-detect | Not used because converters are used instead (more reliable). The dead `_build_dtype_dict()` was meant for this. |
| `converters` + `dtype` | N/A | Cannot use both -- converters take precedence when both are set. |
| `thousands` | None | pandas `thousands` parameter could handle ADVANCED_SEPARATOR natively. Currently not used because `_apply_advanced_separators()` is dead code. |
| `decimal` | `"."` | pandas `decimal` parameter could handle DECIMAL_SEPARATOR natively. Currently not used. |
| `encoding` | System default | Not passed for .xlsx (XML-based, encoding embedded). Should be passed for .xls files. |
| `skiprows` | None | Not used -- `header` parameter handles row skipping. Could be used for more complex skip patterns. |
