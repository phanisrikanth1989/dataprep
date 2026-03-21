# Audit Report: tFileOutputExcel / FileOutputExcel

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileOutputExcel` |
| **V1 Engine Class** | `FileOutputExcel` |
| **Engine File** | `src/v1/engine/components/file/file_output_excel.py` (383 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileoutputexcel()` (lines 1522-1530) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFileOutputExcel'` (line 276) |
| **Registry Aliases** | `FileOutputExcel`, `tFileOutputExcel` (registered in `src/v1/engine/engine.py` lines 93-94) |
| **Category** | File / Output |
| **Complexity** | Medium -- output sink with append mode, header detection, empty-row filtering, openpyxl workbook management |
| **Base Class** | `BaseComponent` (`src/v1/engine/base_component.py`) |
| **Dependencies** | `openpyxl`, `pandas`, `os`, `logging` |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_output_excel.py` | Engine implementation (383 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1522-1530) | Parameter extraction from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 276-277) | Dispatch -- dedicated `elif` for `tFileOutputExcel` calls `parse_tfileoutputexcel()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ComponentExecutionError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 19: `from .file_output_excel import FileOutputExcel`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 4 | 2 | 6 of 28+ Talend params extracted (21%); missing VERSION_2007, PROTECT_FILE, PASSWORD, AUTO_SIZE, FONT, FIRST_CELL positioning, FLUSH, SPLIT, etc. Converter crashes on missing XML elements. |
| Engine Feature Parity | **Y** | 0 | 5 | 5 | 2 | No .xls support; no cell positioning; no auto-size; no password protection; no split output; NaN leaks to Excel cells; streaming mode overwrites per chunk |
| Code Quality | **Y** | 3 | 4 | 3 | 1 | Cross-cutting base class bugs; NaN/empty-row filtering has string-cast side effects; `_validate_config()` never called; workbook handle leak; sheet name not validated |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | Row-by-row `sheet.append()` for all rows; entire workbook in memory; no streaming write support |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes (4 P0, 14 P1)**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileOutputExcel Does

`tFileOutputExcel` writes data rows from an incoming flow to a Microsoft Excel file (.xls or .xlsx format). It is the standard output component for generating Excel reports and data exports in Talend. The component receives rows via a Row link, writes them cell by cell into a specified sheet of a workbook, and saves the file. It supports appending to existing files, header inclusion, cell positioning, column auto-sizing, font formatting, password protection, and Excel 2007 (xlsx) format selection.

**Source**: [tFileOutputExcel Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/excel/tfileoutputexcel-standard-properties), [tFileOutputExcel Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/excel/tfileoutputexcel-standard-properties), [tFileOutputExcel Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/excel/tfileoutputexcel), [tFileOutputExcel (Talend Skill v6.5.1)](https://talendskill.com/knowledgebase/tfileoutputexcel-talend-components-v6-5-1-20180116_1512/), [tFileOutputExcel tdi-studio-se (GitHub)](https://github.com/Talend/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputExcel/tFileOutputExcel_begin.javajet)

**Component family**: Excel (File / Output)
**Available in**: All Talend products (Standard). Also available in Spark Batch variants.
**Required JARs**: `jxl.jar` (when VERSION_2007=false), `talendExcel-1.2-*.jar`, `poi-3.16-*.jar`, `poi-ooxml-3.16-*.jar`, `poi-ooxml-schemas-3.16-*.jar`, `poi-scratchpad-3.16-*.jar`, `xmlbeans-2.6.0.jar`, `dom4j-1.6.1.jar`, `geronimo-stax-api_1.0_spec-1.0.1.jar`, `commons-collections4-4.1.jar`, `log4j-1.2.15.jar` (when VERSION_2007=true)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the input structure for writing. |
| 3 | Write Excel 2007 format | `VERSION_2007` | Boolean (CHECK) | `false` | When checked, writes `.xlsx` format using Apache POI (XSSF). When unchecked, writes `.xls` format using JExcelApi (jxl.jar). This is a critical toggle that changes the underlying Java library used. |
| 4 | Use Output Stream | `USE_OUTPUT_STREAM` | Boolean (CHECK) | `false` | Enables streaming output via OutputStream instead of file path. Used when output goes to another component (e.g., `tFileFetch`). |
| 5 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute path to the output Excel file. Supports context variables, globalMap references, Java expressions. |
| 6 | Sheet Name | `SHEETNAME` | Expression (String) | `"Sheet1"` | Name of the Excel sheet to write data to. Supports expressions. If the sheet does not exist, it will be created. |
| 7 | Include Header | `INCLUDEHEADER` | Boolean (CHECK) | `false` | When checked, writes schema column names as the first row in the sheet. |
| 8 | Append Existing File | `APPEND_FILE` | Boolean (CHECK) | `false` | When checked, opens the existing file and adds data instead of overwriting. If file does not exist, creates new. |
| 9 | Append Existing Sheet | `APPEND_SHEET` | Boolean (CHECK) | `false` | When checked with APPEND_FILE, appends rows to the end of the specified sheet. Without this, data overwrites the sheet content. |
| 10 | Is Absolute Y Position | `FIRST_CELL_Y_ABSOLUTE` | Boolean (CHECK) | `false` | Enables absolute cell positioning on the Y axis (row offset). |
| 11 | First Cell X | `FIRST_CELL_X` | Integer | `0` | Starting column offset (0-based). Allows writing data starting from a specific column. |
| 12 | First Cell Y | `FIRST_CELL_Y` | Integer | `0` | Starting row offset (0-based). Allows writing data starting from a specific row. |
| 13 | Keep Existing Cell Format | `KEEP_CELL_FORMATING` | Boolean (CHECK) | `false` | Preserves existing cell formatting (font, color, borders) when appending to existing file. Only effective with APPEND_FILE. |
| 14 | Font | `FONT` | Dropdown | System default | Font family to use for written cells (e.g., Arial, Times New Roman). |
| 15 | Define All Columns Auto Size | `AUTO_SIZE_SETTING` | Boolean (CHECK) | `false` | Automatically adjusts column widths to fit content. Can be configured per-column when unchecked (table parameter). |
| 16 | Protect File | `PROTECT_FILE` | Boolean (CHECK) | `false` | Enables password protection for the workbook. Only available with VERSION_2007=true. |
| 17 | Password | `PASSWORD` | Password String | -- | Password for file protection. Only visible when PROTECT_FILE=true. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 18 | Create Directory If Not Exists | `CREATE` | Boolean (CHECK) | `true` | Creates the output directory structure if it does not already exist. |
| 19 | Custom Flush Buffer Size | `CUSTOM_FLUSH_BUFFER` | Boolean (CHECK) | `false` | Enables manual configuration of the write buffer flush interval. |
| 20 | Row Number (Flush) | `FLUSH_ON_ROW` | Integer | `1000` | Number of rows to buffer before flushing to disk. Only visible when CUSTOM_FLUSH_BUFFER=true. Helps manage memory for large writes. |
| 21 | Advanced Separator (for numbers) | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enables custom number formatting with locale-specific separators. |
| 22 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Character used for thousands grouping in numeric values. Only visible when ADVANCED_SEPARATOR=true. |
| 23 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Character used as decimal point in numeric values. Only visible when ADVANCED_SEPARATOR=true. |
| 24 | Truncate Characters Exceeding Max Cell Length | `TRUNCATE_EXCEEDING_CHARACTERS` | Boolean (CHECK) | `false` | Truncates cell values to 32,767 characters (Excel cell limit). Only available with VERSION_2007=true. |
| 25 | Encoding | `ENCODING` | Dropdown / Custom | System default | Character encoding for file output. Common values: UTF-8, ISO-8859-1, Cp1252. |
| 26 | Don't Generate Empty File | `DELETE_EMPTYFILE` | Boolean (CHECK) | `false` | When checked, does not create the output file if no data rows are written. |
| 27 | Recalculate Formula | `RECALCULATE_FORMULA` | Boolean (CHECK) | `false` | Forces Excel to recalculate all formulas when the file is opened. Relevant when appending to files with formulas. |
| 28 | Streaming Append | `STREAMING_APPEND` | Boolean (CHECK) | `false` | Uses streaming mode (SXSSF) for appending to large Excel 2007 files. Reduces memory usage for high-volume writes. |
| 29 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | When checked, the job fails immediately on write error. When unchecked, errors are logged but job continues. |
| 30 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for the tStatCatcher component. |
| 31 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Primary data input -- rows to be written to the Excel file. All columns defined in the schema are expected. |
| `ITERATE` | Input | Iterate | Enables iterative processing when the component is used with iteration components. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: `tFileOutputExcel` is a **sink** component. It does NOT have a `FLOW` output connection. It does NOT have a `REJECT` output. Data flows INTO this component, not out of it.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows written to the Excel file. This is the primary row count variable. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully written. Typically equals NB_LINE for output components. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows that failed to write. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

**Note on NB_LINE**: The `NB_LINE` global variable can be used in downstream components connected via triggers. A common pattern is `((Integer)globalMap.get("tFileOutputExcel_1_NB_LINE"))`. A [known Talend community issue](https://community.talend.com/t5/Design-and-Development/tFileOutputExcel-1-NB-LINE-leads-to-null-pointer-exception/td-p/104605) documents that accessing `NB_LINE` when no rows are written can produce a null pointer exception if the variable is not initialized.

### 3.5 Behavioral Notes

1. **Sink component -- no pass-through**: `tFileOutputExcel` consumes rows but does NOT forward them downstream via a FLOW connection. It returns `null` (Talend) / `{'main': None}` (v1). If you need data to continue flowing, use `tMap` to replicate the flow before this component, or use `tReplicate`.

2. **VERSION_2007 toggle**: This is a critical parameter that changes the entire underlying implementation:
   - `false` (default): Uses `jxl.jar` (JExcelApi), writes `.xls` format (Excel 97-2003), limited to 65,536 rows and 256 columns.
   - `true`: Uses Apache POI (XSSF/SXSSF), writes `.xlsx` format, supports 1,048,576 rows and 16,384 columns.
   - Several features (PROTECT_FILE, TRUNCATE_EXCEEDING_CHARACTERS, STREAMING_APPEND) are ONLY available with VERSION_2007=true.

3. **Append mode behavior**: When APPEND_FILE=true:
   - If the file exists, it is loaded into memory, data is appended, then saved back.
   - If APPEND_SHEET=true, new rows are added after the last row of the specified sheet.
   - If APPEND_SHEET=false, a new sheet is created (or existing sheet content is replaced).
   - Header inclusion is intelligent: if the sheet already has a matching header, the header is not duplicated.

4. **Cell positioning (FIRST_CELL_X, FIRST_CELL_Y)**: Allows writing data to a specific region of the sheet, not just starting from A1. This is commonly used for template-based report generation where static content exists in the sheet and data fills a designated area.

5. **Multiple components writing same file**: If multiple `tFileOutputExcel` components target the same file within the same subjob, the last one to execute overwrites previous writes. This is a known Talend behavior documented in official help.

6. **Empty file behavior with DELETE_EMPTYFILE**: When enabled, if no data rows are written (NB_LINE=0), the output file is not created (or is deleted if it was created as a placeholder). Useful for conditional file generation.

7. **Excel cell length limit**: Excel cells have a maximum of 32,767 characters. When TRUNCATE_EXCEEDING_CHARACTERS is not enabled, writing longer strings can cause file corruption or write errors.

8. **NB_LINE includes only data rows**: The header row (if included) is NOT counted in NB_LINE. Only actual data rows from the input flow are counted.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated `parse_tfileoutputexcel()` method** (lines 1522-1530 in `component_parser.py`). The dispatch is properly registered in `converter.py` at line 276: `elif component_type == 'tFileOutputExcel': component = self.component_parser.parse_tfileoutputexcel(node, component)`.

**Converter flow**:
1. `converter.py:_parse_component()` matches `'tFileOutputExcel'` and calls `self.component_parser.parse_tfileoutputexcel(node, component)`
2. `parse_tfileoutputexcel()` extracts 6 parameters directly from `elementParameter` nodes using `.find()` with XPath
3. Schema is extracted generically from `<metadata connector="FLOW">` nodes

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | **Yes** | `filename` | 1524 | Direct `.get('value', '')` extraction. No Java expression marking. |
| 2 | `SHEETNAME` | **Yes** | `sheetname` | 1525 | Default `'Sheet1'`. No Java expression marking. |
| 3 | `INCLUDEHEADER` | **Yes** | `includeheader` | 1526 | Boolean conversion via `.lower() == 'true'` |
| 4 | `APPEND_FILE` | **Yes** | `append_file` | 1527 | Boolean conversion |
| 5 | `CREATE` | **Yes** | `create` | 1528 | Boolean conversion. Default `'true'` |
| 6 | `ENCODING` | **Yes** | `encoding` | 1529 | Default `'UTF-8'`. **Not actually used by engine.** |
| 7 | `VERSION_2007` | **No** | -- | -- | **Not extracted. Engine cannot distinguish between .xls and .xlsx mode.** |
| 8 | `USE_OUTPUT_STREAM` | **No** | -- | -- | **Not extracted. Streaming output mode unavailable.** |
| 9 | `APPEND_SHEET` | **No** | -- | -- | **Not extracted. Engine conflates APPEND_FILE and APPEND_SHEET into one `append_file` flag.** |
| 10 | `FIRST_CELL_X` | **No** | -- | -- | **Not extracted. No cell offset positioning.** |
| 11 | `FIRST_CELL_Y` | **No** | -- | -- | **Not extracted.** |
| 12 | `FIRST_CELL_Y_ABSOLUTE` | **No** | -- | -- | **Not extracted.** |
| 13 | `KEEP_CELL_FORMATING` | **No** | -- | -- | **Not extracted. Cell formatting not preserved.** |
| 14 | `FONT` | **No** | -- | -- | **Not extracted. No font control.** |
| 15 | `AUTO_SIZE_SETTING` | **No** | -- | -- | **Not extracted. No column auto-sizing.** |
| 16 | `PROTECT_FILE` | **No** | -- | -- | **Not extracted. No password protection.** |
| 17 | `PASSWORD` | **No** | -- | -- | **Not extracted.** |
| 18 | `CUSTOM_FLUSH_BUFFER` | **No** | -- | -- | **Not extracted. No flush buffer control.** |
| 19 | `FLUSH_ON_ROW` | **No** | -- | -- | **Not extracted.** |
| 20 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted. No locale-aware number formatting.** |
| 21 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 22 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 23 | `TRUNCATE_EXCEEDING_CHARACTERS` | **No** | -- | -- | **Not extracted. Long strings may corrupt output.** |
| 24 | `DELETE_EMPTYFILE` | **No** | -- | -- | **Not extracted. Empty files always created.** |
| 25 | `RECALCULATE_FORMULA` | **No** | -- | -- | **Not extracted.** |
| 26 | `STREAMING_APPEND` | **No** | -- | -- | **Not extracted. No streaming write mode.** |
| 27 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted by converter. Engine uses hardcoded default `True` (line 136).** |
| 28 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority). |
| 29 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic). |
| 30 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In). |

**Summary**: 6 of 28+ parameters extracted (21%). 22 runtime-relevant parameters are missing. The parser method is only 9 lines long (1522-1530) and captures only the absolute minimum configuration.

### 4.2 Schema Extraction

Schema is extracted generically by the converter framework for FLOW metadata.

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types |
| `nullable` | Yes | Boolean conversion |
| `key` | Yes | Boolean conversion |
| `length` | Yes | Integer conversion |
| `precision` | Yes | Integer conversion |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted |
| `talendType` | **No** | Full Talend type string not preserved |

### 4.3 Expression Handling

**Critical gap**: The `parse_tfileoutputexcel()` method does NOT call `mark_java_expression()` on the `FILENAME` or `SHEETNAME` values. If a Talend job uses Java expressions in the filename (e.g., `"/data/" + context.output_dir + "/report.xlsx"`), the expression will NOT be marked with `{{java}}` prefix and will NOT be resolved by the Java bridge at runtime.

Compare with other component parsers (e.g., `parse_file_input_delimited`) where `mark_java_expression()` is called, or the generic `parse_base_component()` which scans all values for Java expression markers. The `parse_tfileoutputexcel()` uses raw `.get('value', '')` without any expression processing.

**Context variable handling**: Simple `context.var` references are NOT wrapped with `${context.var}` either. The `BaseComponent.execute()` method calls `self.context_manager.resolve_dict(self.config)` which may catch simple cases, but complex Java expressions with string concatenation will fail.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FOE-001 | **P1** | **`DIE_ON_ERROR` not extracted**: The converter does not extract the `DIE_ON_ERROR` parameter. The engine defaults to `True` (line 136: `die_on_error = self.config.get('die_on_error', True)`). In Talend, the default is `false`. This means jobs that expect to continue after write errors will instead crash. Behavioral inversion. |
| CONV-FOE-002 | **P1** | **`VERSION_2007` not extracted**: The engine uses `openpyxl` which only writes `.xlsx` format. Jobs expecting `.xls` output (VERSION_2007=false, the Talend default) will get `.xlsx` instead, potentially breaking downstream consumers expecting the older format. |
| CONV-FOE-003 | **P2** | **`APPEND_SHEET` not extracted**: The engine conflates file-level append (`APPEND_FILE`) and sheet-level append (`APPEND_SHEET`) into a single `append_file` flag. When APPEND_FILE=true but APPEND_SHEET=false, Talend replaces the sheet content; v1 always appends to the existing sheet. |
| CONV-FOE-004 | **P2** | **`FIRST_CELL_X` / `FIRST_CELL_Y` not extracted**: Cell positioning unavailable. Data always starts at row 1, column A. Template-based reports that need data written to specific cell regions will fail. |
| CONV-FOE-005 | **P1** | **Converter crashes with `AttributeError` on missing XML elements**: Six `.find(...).get(...)` calls at lines 1524-1529 have no null checks. If any `elementParameter` node is missing from the Talend XML (e.g., a job exported from an older Talend version that omits optional parameters), `.find()` returns `None` and the subsequent `.get('value', ...)` raises `AttributeError: 'NoneType' object has no attribute 'get'`. Crashes the entire conversion. |
| CONV-FOE-010 | **P2** | **`AUTO_SIZE_SETTING` not extracted**: Column auto-sizing unavailable. Output columns will use default width, potentially truncating visible data in Excel. |
| CONV-FOE-006 | **P2** | **`PROTECT_FILE` / `PASSWORD` not extracted**: Password protection unavailable. Jobs producing protected workbooks will generate unprotected files. |
| CONV-FOE-007 | **P2** | **No Java expression marking on `FILENAME` / `SHEETNAME`**: Expressions like `"/data/" + context.dir + "/file.xlsx"` will NOT be resolved. Only simple context variable references may work via `ContextManager.resolve_dict()`. |
| CONV-FOE-008 | **P3** | **`FONT` not extracted**: Font formatting unavailable. Output uses default openpyxl font. |
| CONV-FOE-009 | **P3** | **`DELETE_EMPTYFILE` not extracted**: Empty files always generated even when no data rows exist. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Write Excel file | **Yes** | Medium | `_process()` lines 96-360 | Uses `openpyxl` -- only `.xlsx` output. No `.xls` support. |
| 2 | Sheet name configuration | **Yes** | High | Line 125 | Supports custom sheet name with quote stripping (lines 128-131) |
| 3 | Include header row | **Yes** | High | Lines 281-325, 323-325 | Writes column names from schema or DataFrame columns |
| 4 | Append to existing file | **Yes** | Medium | Lines 157-158 | Opens existing workbook with `openpyxl.load_workbook()`. Appends to sheet. |
| 5 | Append header detection | **Yes** | Medium | Lines 287-321 | Smart detection: checks if existing first row matches expected headers before writing duplicate header |
| 6 | Create output directory | **Yes** | High | Lines 141-153 | Uses `os.makedirs()` when `create=True` |
| 7 | Die on error handling | **Yes** | High | Lines 149-150, 170-171, 349-351 | Multiple try/except blocks honor `die_on_error` flag throughout processing |
| 8 | Empty input handling | **Yes** | High | Lines 111-114 | Returns `{'main': None}` with stats (0,0,0) when input is None |
| 9 | DataFrame input | **Yes** | High | Lines 197-199 | Direct DataFrame input supported |
| 10 | Dict input auto-detection | **Yes** | High | Lines 200-214 | Searches for 'main' key, then first DataFrame in dict (skipping 'stats') |
| 11 | List-of-dict input | **Yes** | High | Lines 246-255 | Legacy format supported alongside DataFrame |
| 12 | Output schema column ordering | **Yes** | High | Lines 225-227 | Uses `output_schema` column order when available |
| 13 | Empty row filtering | **Yes** | Low | Lines 263-272 | Filters rows where ALL values are None/empty/NaN. **See BUG-FOE-003.** |
| 14 | Statistics tracking | **Yes** | Medium | Lines 357-358 | `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` via `_update_stats()` |
| 15 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 16 | Java expression support | **Partial** | Low | Via `BaseComponent.execute()` line 198 | Bridge exists but converter does NOT mark expressions. See CONV-FOE-007. |
| 17 | **Excel 2007 (.xlsx) format** | **Yes** | High | Implicit | `openpyxl` always writes `.xlsx`. No format toggle. |
| 18 | **Excel 97-2003 (.xls) format** | **No** | N/A | -- | **openpyxl does not support .xls. Would need `xlwt` library.** |
| 19 | **Cell positioning (FIRST_CELL_X/Y)** | **No** | N/A | -- | **Data always starts at row 1, column A (or after last row in append mode).** |
| 20 | **Column auto-sizing** | **No** | N/A | -- | **Not implemented. Default column widths used.** |
| 21 | **Font selection** | **No** | N/A | -- | **Not implemented. Default openpyxl font.** |
| 22 | **Password protection** | **No** | N/A | -- | **Not implemented.** |
| 23 | **Flush buffer control** | **No** | N/A | -- | **Not implemented. All rows written then saved once.** |
| 24 | **Split output** | **No** | N/A | -- | **Not implemented.** |
| 25 | **Don't generate empty file** | **No** | N/A | -- | **Not implemented. Empty workbook always saved.** |
| 26 | **Truncate cell length** | **No** | N/A | -- | **Not implemented. Long strings written as-is.** |
| 27 | **Keep existing cell format** | **No** | N/A | -- | **Not implemented.** |
| 28 | **Recalculate formula** | **No** | N/A | -- | **Not implemented.** |
| 29 | **Streaming append (SXSSF)** | **No** | N/A | -- | **Not implemented. Entire workbook loaded into memory.** |
| 30 | **Advanced separator (number formatting)** | **No** | N/A | -- | **Not implemented.** |
| 31 | **Output stream mode** | **No** | N/A | -- | **Not implemented.** |
| 32 | **Append sheet control** | **No** | N/A | -- | **APPEND_SHEET not extracted. Engine always appends to existing sheet.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FOE-001 | **P1** | **No `.xls` (Excel 97-2003) format support**: `openpyxl` only supports `.xlsx` (Excel 2007+). Talend defaults to VERSION_2007=false which generates `.xls`. Jobs not explicitly setting VERSION_2007=true will produce a format mismatch. Downstream consumers expecting `.xls` (e.g., legacy systems, macros) will fail. Would need `xlwt` or `xlsxwriter` for `.xls` support. |
| ENG-FOE-002 | **P1** | **Default `die_on_error=True` differs from Talend default `false`**: Engine line 136 defaults to `True`. Talend defaults to `false`. Combined with CONV-FOE-001 (converter not extracting the parameter), this means jobs that expect to continue after write errors will crash. Behavioral inversion. |
| ENG-FOE-003 | **P1** | **NaN values leak into Excel cells**: The `is_non_empty_row()` filter (lines 263-269) uses `str(value).strip().lower() != 'nan'` to detect NaN, but this only applies at the ROW level for filtering empty rows. Individual cell values that are `NaN` (from pandas) are written directly to Excel via `sheet.append(row_values)` (line 338). In Talend, null values in output produce empty cells. In v1, pandas NaN values may appear as literal "nan" strings in Excel cells. |
| ENG-FOE-004 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. The `error_message` is stored on the component object (base_component.py line 229) but NOT propagated to globalMap. |
| ENG-FOE-005 | **P1** | **`{id}_FILENAME` not set in globalMap**: Resolved filename not stored in globalMap. Downstream components referencing the output path via globalMap will get null. |
| ENG-FOE-006 | **P2** | **No cell positioning**: Data always writes starting from cell A1 (or the next row in append mode). Template-based report generation requiring data at specific cell coordinates (FIRST_CELL_X/Y) is not supported. |
| ENG-FOE-007 | **P2** | **No column auto-sizing**: All columns use default widths. Reports may display truncated data in Excel unless users manually resize columns. |
| ENG-FOE-008 | **P2** | **Empty file always created**: When no data rows are present, the engine still creates and saves an empty workbook (with an empty sheet). Talend with DELETE_EMPTYFILE=true would not create the file at all. |
| ENG-FOE-009 | **P2** | **No APPEND_SHEET distinction**: The engine conflates APPEND_FILE and APPEND_SHEET into one `append_file` flag. When APPEND_FILE=true, the engine always appends to the existing sheet. There is no mode to replace sheet content while preserving the file. |
| ENG-FOE-010 | **P2** | **Append mode `sheet.max_row` may be unreliable**: In openpyxl, `sheet.max_row` for a brand-new sheet returns 1 (not 0), because openpyxl considers every worksheet to have at least one row. The code checks `sheet.max_row == 0` (line 289) which will never be true for a freshly created sheet, potentially skipping header writes on empty sheets in append mode. |
| ENG-FOE-011 | **P3** | **No password protection**: Output files are always unprotected regardless of Talend configuration. |
| ENG-FOE-012 | **P3** | **No font control**: Default openpyxl font used for all cells. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism (when base class bug is fixed) |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Equals `rows_written` -- may differ from `NB_LINE` due to empty row filtering |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Set to count of filtered empty rows. Talend counts write failures, not empty rows. Semantic mismatch. |
| `{id}_FILENAME` | Likely (common pattern) | **No** | -- | Not implemented |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FOE-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileOutputExcel, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-FOE-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FOE-003 | **P1** | `src/v1/engine/components/file/file_output_excel.py:263-269` | **Empty row filter casts all values to `str()` and uses `str(value).strip().lower() != 'nan'` comparison**: This has multiple problems: (a) `str(0)` is `'0'` which is non-empty, so rows with all-zero numeric values are kept (correct). But `str(0.0)` is `'0.0'` which is also non-empty (correct). However, `str(None)` is `'None'` which is NOT empty string, meaning `None` values pass the `str(value).strip() != ''` check, marking the row as non-empty. The `value is not None` check saves this case. But `float('nan')` is not None, so NaN values reach the `str(value).strip().lower() != 'nan'` check. This means a row with a single NaN and all other values empty/None IS considered empty (correct), but a row with NaN AND one non-empty value is kept with the NaN intact -- and the NaN leaks into the Excel cell. (b) The `str()` cast is performed on every value of every row, which is wasteful for type-checking purposes. |
| BUG-FOE-004 | **P1** | `src/v1/engine/components/file/file_output_excel.py:289` | **`sheet.max_row == 0` is never true for openpyxl worksheets**: In openpyxl, a newly created empty worksheet has `max_row = 1` (and `max_column = 1`), not 0. The condition on line 289 (`if sheet.max_row == 0`) will never be true, even for a genuinely empty sheet. This means in append mode with an empty sheet, the code falls through to the `elif sheet.max_row >= 1` branch (line 293), which reads `sheet[1]` -- a row that exists but has all `None` values. The `first_row_cleaned` will be `['', '', ...]` (all empty), triggering `if all(val == '' for val in first_row_cleaned)` on line 308, which correctly writes the header. So the end result is **accidentally correct** for empty sheets, but the logic path is wrong and fragile. If openpyxl behavior changes, this breaks. |
| BUG-FOE-005 | **P1** | `src/v1/engine/components/file/file_output_excel.py:63-94` | **`_validate_config()` is never called**: The method exists and contains validation logic for `filename`, `sheetname`, `includeheader`, and `append_file`, but it is never invoked by `__init__()`, `execute()`, or `_process()`. All validation is dead code. Invalid configurations (missing filename, wrong types) are not caught until they cause runtime errors deep in processing. |
| BUG-FOE-006 | **P1** | `src/v1/engine/components/file/file_output_excel.py:338` | **NaN values written directly to Excel cells**: When a DataFrame contains `NaN` values (from pandas operations, joins, etc.), those values are passed to `sheet.append(row_values)` without conversion. openpyxl will write them as the string `"nan"` or as Python `float('nan')` depending on the value type. Talend writes empty cells for null values. This produces incorrect Excel output where cells show "nan" instead of being empty. |
| BUG-FOE-007 | **P2** | `src/v1/engine/components/file/file_output_excel.py:161-166` | **Default sheet removal logic may leave orphan sheets**: When creating a new workbook (not append mode), the code removes the default 'Sheet' worksheet if the target sheet_name is different (lines 163-166). However, if `sheet_name == 'Sheet'`, the default sheet is kept and used. This is correct. But if the user creates a sheet named something other than 'Sheet', then later in lines 177-183, a new sheet is created with the target name. The check `if 'Sheet' in workbook.sheetnames` (line 163) uses exact string match, which means 'Sheet1' (the default in some openpyxl versions) would NOT be removed. This could leave an unwanted empty 'Sheet1' tab in the output file. |
| BUG-FOE-008 | **P2** | `src/v1/engine/components/file/file_output_excel.py:114` | **`_update_stats(0, 0, 0)` called without `_update_global_map()`**: When input is None (line 111-114), the method calls `_update_stats(0, 0, 0)` and returns immediately. The `_update_global_map()` call is NOT made for this path because it happens in `BaseComponent.execute()` AFTER `_process()` returns. This is actually correct -- the base class handles it. However, the `return {'main': None, 'stats': self.stats}` includes stats in the result dict. The base class `execute()` (line 223) then overwrites `result['stats']` with `self.stats.copy()`. So the stats in the return value are set twice -- once by `_process()` and once by `execute()`. Not a bug per se, but confusing code. |
| BUG-FOE-009 | **P0** | `src/v1/engine/components/file/file_output_excel.py:158,161,345` | **Workbook never closed -- file handle leak on error paths**: `workbook.close()` is never called anywhere in the component. The workbook object is created at line 158 (`openpyxl.load_workbook()`) or line 161 (`Workbook()`), and saved at line 345 (`workbook.save()`). If any exception occurs between creation and save -- during data preparation (lines 197-272), header writing (lines 281-325), or row writing (lines 329-338) -- the file handle remains open. On Windows this causes file locking (preventing subsequent retries or cleanup). On all platforms, repeated failures lead to file descriptor exhaustion. The workbook should be managed with a try/finally or context manager to guarantee closure. |
| BUG-FOE-010 | **P1** | `src/v1/engine/components/file/file_output_excel.py:125-131` | **Sheet name >31 characters silently truncated by openpyxl**: Excel sheet names have a maximum length of 31 characters and cannot contain `/ \ * ? [ ]` characters. The engine performs no validation on the `sheetname` config value (only stripping enclosing quotes at lines 128-131). openpyxl silently truncates names exceeding 31 characters. This causes sheet lookup failures in append mode: the workbook is loaded, the code searches for the full (untruncated) sheet name, does not find it (because it was truncated on the previous write), and creates a new sheet instead of appending. This produces duplicate sheets with truncated names and data loss. |
| BUG-FOE-011 | **P2** | `src/v1/engine/components/file/file_output_excel.py:96-360` | **Streaming mode overwrites workbook per chunk**: When the engine processes data in chunks (streaming/iterative mode), each call to `_process()` creates or loads the workbook (line 158/161), writes the current chunk, and saves (line 345) -- effectively overwriting the previous chunk's data without appending. The component holds no state between `_process()` calls to track that previous chunks were already written. Additionally, `_process()` returns `{'main': None}` for each chunk, and concatenating these results produces a list of `None` values that breaks downstream processing expecting a single DataFrame. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FOE-001 | **P2** | **`append_file` config key** combines two distinct Talend concepts (`APPEND_FILE` and `APPEND_SHEET`) into one flag. Talend distinguishes between appending to the file vs appending to the sheet. The v1 config should have separate keys. |
| NAME-FOE-002 | **P3** | **`create` config key** is ambiguous -- could mean "create file" or "create directory." Talend calls it `CREATE` meaning "create directory if not exists." A clearer name would be `create_directory`. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FOE-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FOE-002 | **P2** | "Converter must mark Java expressions" (STANDARDS.md) | `parse_tfileoutputexcel()` does not call `mark_java_expression()` on FILENAME or SHEETNAME values. |
| STD-FOE-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types via `ExpressionConverter.convert_type()`. |

### 6.4 Debug Artifacts

No debug artifacts (print statements, commented-out code, placeholder comments) found in the engine file.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FOE-001 | **P3** | **No path traversal protection**: `filename` from config is used directly with `os.path.exists()`, `os.makedirs()`, and `openpyxl` file operations. If config comes from untrusted sources, path traversal is possible. Not a concern for Talend-converted jobs where config is trusted. |

### 6.6 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 120); completion with stats (line 358) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `FileOperationError` and `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern consistently -- correct |
| `die_on_error` handling | Multiple try/except blocks handle this: directory creation (line 149), workbook load (line 170), sheet access (line 188), workbook save (line 351) -- correct coverage |
| No bare `except` | All except clauses specify exception type -- correct |
| Error messages | Include component ID and descriptive details -- correct |
| Graceful degradation | Returns `{'main': None, 'stats': self.stats}` when `die_on_error=false` -- correct |
| Catch-all handler | Lines 362-367 catch generic `Exception` and raise `ComponentExecutionError` -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]`, `validate_config() -> bool` -- correct |
| Parameter types | `input_data: Union[Dict[str, Any], pd.DataFrame, None]` -- correct |
| Legacy method | `validate_config() -> bool` (line 370) exists for backward compatibility -- acceptable |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FOE-001 | **P1** | **Entire workbook loaded into memory for append mode**: Line 158 calls `openpyxl.load_workbook(filename)` which loads the ENTIRE existing workbook into memory. For large Excel files (100K+ rows with formatting), this can consume hundreds of MB or even GB of RAM. Talend's STREAMING_APPEND mode (using SXSSF) streams data without loading the full workbook. V1 has no streaming write mode. |
| PERF-FOE-002 | **P2** | **Row-by-row `sheet.append()` loop**: Lines 329-338 iterate every row and call `sheet.append(row_values)` individually. While openpyxl's `append()` is optimized for sequential writes, the per-row Python loop with dictionary access (`row.get(col, '')` for each column) adds overhead. For large DataFrames, converting to a list of lists first and using bulk operations would be faster. |
| PERF-FOE-003 | **P2** | **Empty row filter performs `str()` cast on every cell value**: Lines 263-269 call `str(value).strip()` and `str(value).strip().lower()` for every value in every row during the `is_non_empty_row()` check. For a 100K-row DataFrame with 50 columns, this is 5 million string conversions just for filtering. A pandas-native approach using `df.dropna(how='all')` or similar would be orders of magnitude faster. |
| PERF-FOE-004 | **P3** | **DataFrame-to-dict conversion via `iterrows()`**: Lines 234-244 use `main_data.iterrows()` which is notoriously slow in pandas (creates a Series per row). For large DataFrames, `to_dict('records')` or `values.tolist()` would be significantly faster. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming write mode | **Not implemented**. Entire workbook and all data rows held in memory simultaneously. |
| Large file handling | No special handling for large outputs. No chunked write support. Memory usage scales linearly with row count. |
| Workbook lifecycle | Workbook is created/loaded, data written, then saved. No explicit `.close()` call on workbook, but Python garbage collection handles this. |
| Data conversion | DataFrame -> list of dicts -> per-row list of values. Three representations of the data exist simultaneously in memory during processing. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileOutputExcel` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 383 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic write | P0 | Write a DataFrame with 3 columns and 10 rows to a new .xlsx file. Verify file exists, correct sheet name, correct row count. |
| 2 | Include header | P0 | Write with `includeheader=true`. Verify first row contains column names, data starts at row 2. |
| 3 | No header | P0 | Write with `includeheader=false`. Verify first row contains data, not column names. |
| 4 | Append to existing file | P0 | Write file, then write again with `append_file=true`. Verify combined row count. |
| 5 | Append header detection | P0 | Append to file that already has headers. Verify headers are NOT duplicated. |
| 6 | Empty input | P0 | Pass `None` as input. Verify stats (0,0,0), no crash, returns `{'main': None}`. |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | NaN handling | P1 | Write DataFrame with NaN values. Verify Excel cells are empty, NOT "nan" string. |
| 9 | Empty strings | P1 | Write DataFrame with empty strings. Verify cells are empty in Excel. |
| 10 | Empty DataFrame | P1 | Write empty DataFrame (0 rows, columns defined). Verify file created with header only (if includeheader=true). |
| 11 | Create directory | P1 | Write to path with non-existent parent directory, `create=true`. Verify directory created. |
| 12 | Missing directory + create=false | P1 | Write to non-existent directory with `create=false`. Verify appropriate error. |
| 13 | Die on error = false | P1 | Trigger a write error with `die_on_error=false`. Verify job continues, returns stats. |
| 14 | Die on error = true | P1 | Trigger a write error with `die_on_error=true`. Verify `FileOperationError` raised. |
| 15 | Schema column ordering | P1 | Write with `output_schema` specifying column order different from DataFrame column order. Verify Excel columns match schema order. |
| 16 | Dict input with 'main' key | P1 | Pass `{'main': df, 'stats': {...}}` as input. Verify DataFrame is correctly extracted and written. |
| 17 | Dict input without 'main' key | P1 | Pass `{'output_1': df}` as input. Verify first DataFrame is detected and written. |
| 18 | Context variable in filename | P1 | Use `${context.output_dir}/file.xlsx` as filename. Verify context resolution. |
| 19 | Sheet name with quotes | P1 | Pass `sheetname="'MySheet'"` (with enclosing quotes). Verify quotes stripped, sheet named `MySheet`. |
| 20 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. |
| 21 | Mixed types in DataFrame | P1 | Write DataFrame with int, float, string, date, boolean columns. Verify each type renders correctly in Excel. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 22 | Large file (100K rows) | P2 | Write 100,000 rows. Verify memory usage is reasonable and file is correct. |
| 23 | Append to corrupt file | P2 | Attempt append to invalid/corrupt Excel file. Verify error handling. |
| 24 | Special characters in sheet name | P2 | Sheet names with `/`, `\`, `*`, `?`, `[`, `]` (Excel-invalid chars). Verify error handling. |
| 25 | Column name with special chars | P2 | Column names containing spaces, periods, brackets. Verify correct writing. |
| 26 | Very long cell values | P2 | Write cell value > 32,767 chars. Verify behavior (truncation or error). |
| 27 | Concurrent writes | P2 | Two components writing to different sheets in same file simultaneously. Verify no corruption. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FOE-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FOE-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-FOE-009 | Bug | Workbook never closed -- file handle leak on error paths. `workbook.close()` never called. On error between creation (line 158/161) and save (line 345), file handle remains open. Windows file locking, FD exhaustion. |
| TEST-FOE-001 | Testing | Zero v1 unit tests for this output component. All 383 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOE-001 | Converter | `DIE_ON_ERROR` not extracted. Engine defaults to `True` (line 136), Talend defaults to `false`. Behavioral inversion -- jobs expecting to continue after errors will crash. |
| CONV-FOE-002 | Converter | `VERSION_2007` not extracted. Engine always outputs `.xlsx` via openpyxl. Jobs expecting `.xls` (Talend default) get wrong format. |
| CONV-FOE-005 | Converter | Converter crashes with `AttributeError` on missing XML elements. Six `.find(...).get(...)` calls at lines 1524-1529 have no null checks. |
| ENG-FOE-001 | Engine | No `.xls` (Excel 97-2003) format support. openpyxl only supports `.xlsx`. Format mismatch with Talend default. |
| ENG-FOE-002 | Engine | Default `die_on_error=True` differs from Talend default `false`. Combined with CONV-FOE-001, creates behavioral inversion. |
| ENG-FOE-003 | Engine | NaN values leak into Excel cells as literal "nan" strings instead of empty cells. |
| ENG-FOE-004 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set on error. |
| ENG-FOE-005 | Engine | `{id}_FILENAME` globalMap variable not set. |
| BUG-FOE-003 | Bug | Empty row filter casts all values to `str()` for NaN detection. NaN values in non-empty rows leak through to Excel cells. Semantic mismatch with Talend null handling. |
| BUG-FOE-004 | Bug | `sheet.max_row == 0` condition (line 289) is never true for openpyxl worksheets. Works accidentally but fragile. |
| BUG-FOE-005 | Bug | `_validate_config()` is dead code -- never called. 32 lines of unreachable validation logic. |
| BUG-FOE-006 | Bug | NaN values from DataFrame passed directly to `sheet.append()` without None/empty conversion. |
| BUG-FOE-010 | Bug | Sheet name >31 chars silently truncated by openpyxl. No validation on length or invalid characters. Causes sheet lookup failures in append mode. |
| PERF-FOE-001 | Performance | Entire workbook loaded into memory for append mode. No streaming write support. Memory-intensive for large files. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOE-003 | Converter | `APPEND_SHEET` not extracted. Engine conflates file and sheet append into one flag. |
| CONV-FOE-004 | Converter | `FIRST_CELL_X` / `FIRST_CELL_Y` not extracted. No cell positioning. |
| CONV-FOE-010 | Converter | `AUTO_SIZE_SETTING` not extracted. No column auto-sizing. |
| CONV-FOE-006 | Converter | `PROTECT_FILE` / `PASSWORD` not extracted. No password protection. |
| CONV-FOE-007 | Converter | No Java expression marking on `FILENAME` / `SHEETNAME`. Expressions with string concatenation will NOT be resolved. |
| ENG-FOE-006 | Engine | No cell positioning (FIRST_CELL_X/Y). Data always starts at A1. |
| ENG-FOE-007 | Engine | No column auto-sizing. Default widths used. |
| ENG-FOE-008 | Engine | Empty file always created even when no data rows. DELETE_EMPTYFILE not supported. |
| ENG-FOE-009 | Engine | No APPEND_SHEET distinction. Engine always appends to existing sheet. |
| ENG-FOE-010 | Engine | `sheet.max_row == 0` check in append header logic is dead code (openpyxl min is 1). |
| BUG-FOE-007 | Bug | Default sheet removal logic may leave orphan sheet tabs depending on openpyxl version. |
| BUG-FOE-008 | Bug | `_update_stats()` in None-input path writes stats to result dict that base class then overwrites. Confusing but not broken. |
| BUG-FOE-011 | Bug | Streaming mode overwrites workbook per chunk. Each `_process()` call creates/loads workbook, writes chunk, saves -- overwriting previous chunk without append. Returns `{'main': None}` breaking concat. |
| NAME-FOE-001 | Naming | `append_file` config key conflates APPEND_FILE and APPEND_SHEET Talend concepts. |
| STD-FOE-001 | Standards | `_validate_config()` exists but never called. Dead validation. |
| STD-FOE-002 | Standards | Converter does not mark Java expressions on FILENAME/SHEETNAME. |
| STD-FOE-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| PERF-FOE-002 | Performance | Row-by-row `sheet.append()` loop. Could use bulk operations. |
| PERF-FOE-003 | Performance | Empty row filter performs `str()` cast on every cell value. Pandas-native approach would be faster. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FOE-008 | Converter | `FONT` not extracted. No font control in output. |
| CONV-FOE-009 | Converter | `DELETE_EMPTYFILE` not extracted. Empty files always created. |
| ENG-FOE-011 | Engine | No password protection support. |
| ENG-FOE-012 | Engine | No font control. Default openpyxl font. |
| NAME-FOE-002 | Naming | `create` config key is ambiguous -- should be `create_directory`. |
| SEC-FOE-001 | Security | No path traversal protection on `filename`. |
| PERF-FOE-004 | Performance | `iterrows()` used for DataFrame-to-dict conversion. Slow for large DataFrames. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 3 bugs (2 cross-cutting, 1 file handle leak), 1 testing |
| P1 | 14 | 3 converter, 5 engine, 5 bugs, 1 performance |
| P2 | 19 | 4 converter, 5 engine, 3 bugs, 1 naming, 3 standards, 2 performance, 1 naming |
| P3 | 7 | 2 converter, 2 engine, 1 naming, 1 security, 1 performance |
| **Total** | **44** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FOE-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FOE-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FOE-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic write, include header, no header, append, append header detection, empty input, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Fix NaN cell leakage** (BUG-FOE-003, BUG-FOE-006, ENG-FOE-003): Before calling `sheet.append(row_values)`, convert NaN values to `None` (which openpyxl writes as empty cells). Add a sanitization step:
   ```python
   import math
   sanitized_values = [
       None if (v is None or (isinstance(v, float) and math.isnan(v))) else v
       for v in row_values
   ]
   sheet.append(sanitized_values)
   ```
   **Impact**: Fixes incorrect "nan" strings in Excel cells. **Risk**: Low.

5. **Extract `DIE_ON_ERROR` in converter** (CONV-FOE-001): Add to `parse_tfileoutputexcel()`:
   ```python
   component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
   ```
   AND change engine default from `True` to `False` (line 136). **Impact**: Fixes behavioral inversion. **Risk**: Low.

### Short-Term (Hardening)

6. **Add Java expression marking to converter** (CONV-FOE-007, STD-FOE-002): In `parse_tfileoutputexcel()`, wrap `FILENAME` and `SHEETNAME` extraction with `self.expr_converter.mark_java_expression(value)` to enable Java bridge resolution for expressions containing string concatenation or context variables.

7. **Set `{id}_FILENAME` and `{id}_ERROR_MESSAGE` in globalMap** (ENG-FOE-004, ENG-FOE-005): After resolving filename in `_process()`, call `self.global_map.put(f"{self.id}_FILENAME", filename)` if `self.global_map` is not None. In error handlers, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

8. **Fix `sheet.max_row` check** (BUG-FOE-004, ENG-FOE-010): Replace `sheet.max_row == 0` with `sheet.max_row <= 1 and sheet.cell(1, 1).value is None` to properly detect genuinely empty sheets in openpyxl. This makes the header detection logic explicitly correct rather than accidentally correct.

9. **Wire up `_validate_config()`** (BUG-FOE-005): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` or returning empty result based on `die_on_error`. Alternatively, add validation as a standard lifecycle step in `BaseComponent.execute()`.

10. **Extract `APPEND_SHEET`** (CONV-FOE-003): Add separate `append_sheet` config key to distinguish file-level vs sheet-level append behavior. Update engine logic to handle the distinction: APPEND_FILE=true + APPEND_SHEET=false should clear existing sheet content before writing.

11. **Extract `VERSION_2007`** (CONV-FOE-002): Add to converter. In the engine, when VERSION_2007=false, either log a warning that `.xls` is not supported (and continue writing `.xlsx`), or add `xlwt` dependency for `.xls` output. The warning approach is pragmatic since most modern consumers accept `.xlsx`.

### Long-Term (Optimization)

12. **Add column auto-sizing** (CONV-FOE-010, ENG-FOE-007): Extract `AUTO_SIZE_SETTING` and implement using openpyxl's column dimension adjustment: `sheet.column_dimensions[col_letter].width = max_width`. Iterate columns and calculate max string length.

13. **Add cell positioning** (CONV-FOE-004, ENG-FOE-006): Extract `FIRST_CELL_X` and `FIRST_CELL_Y`. Modify the write loop to offset row and column indices. Use `sheet.cell(row=y_offset + row_num, column=x_offset + col_num).value = val` instead of `sheet.append()`.

14. **Replace `iterrows()` with vectorized conversion** (PERF-FOE-004): Use `main_data.to_dict('records')` instead of the manual `iterrows()` loop. This is 10-100x faster for large DataFrames.

15. **Replace str-cast empty row filter with pandas-native approach** (PERF-FOE-003): Use `df.dropna(how='all').replace('', np.nan).dropna(how='all')` for filtering, which is vectorized and much faster than per-cell `str()` casts.

16. **Add streaming write mode** (PERF-FOE-001): For large outputs (> threshold), use openpyxl's `write_only` mode which streams rows to disk without holding the entire workbook in memory. Activated via `Workbook(write_only=True)`.

17. **Add password protection** (CONV-FOE-006, ENG-FOE-011): Extract `PROTECT_FILE` and `PASSWORD`. Implement using openpyxl's `workbook.security.workbookPassword = password` and `worksheet.protection.sheet = True`.

18. **Add DELETE_EMPTYFILE support** (CONV-FOE-009, ENG-FOE-008): After writing, if `delete_emptyfile=True` and `rows_written == 0`, delete the output file using `os.remove(filename)`.

19. **Clean up dead validation code** (BUG-FOE-005, STD-FOE-001): Either activate `_validate_config()` by calling it from `_process()`, or remove the dead method entirely to reduce code maintenance burden.

20. **Create integration test** (TEST-FOE-001): Build an end-to-end test exercising `tFileInputDelimited -> tMap -> tFileOutputExcel` in the v1 engine, verifying context resolution, Java bridge integration, globalMap propagation, and correct Excel output.

---

## Appendix A: Converter Parameter Extraction Code

```python
# component_parser.py lines 1522-1530
def parse_tfileoutputexcel(self, node, component: Dict) -> Dict:
    """Parse tFileOutputExcel specific configuration"""
    component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    component['config']['sheetname'] = node.find('.//elementParameter[@name="SHEETNAME"]').get('value', 'Sheet1')
    component['config']['includeheader'] = node.find('.//elementParameter[@name="INCLUDEHEADER"]').get('value', 'false').lower() == 'true'
    component['config']['append_file'] = node.find('.//elementParameter[@name="APPEND_FILE"]').get('value', 'false').lower() == 'true'
    component['config']['create'] = node.find('.//elementParameter[@name="CREATE"]').get('value', 'true').lower() == 'true'
    component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    return component
```

**Notes on this code**:
- Only 9 lines, extracting 6 parameters. This is the most minimal parser of any component with a dedicated method.
- No `mark_java_expression()` call on `FILENAME` or `SHEETNAME`. Java expressions with string concatenation will not be resolved.
- No `DIE_ON_ERROR` extraction. Engine defaults to `True` instead of Talend's `false`.
- No `VERSION_2007` extraction. Engine always outputs `.xlsx`.
- `ENCODING` is extracted but never used by the engine (openpyxl handles encoding internally).
- No context variable detection or wrapping.

---

## Appendix B: Engine Class Structure

```
FileOutputExcel (BaseComponent)
    Constants:
        DEFAULT_SHEET_NAME = 'Sheet1'
        DEFAULT_ENCODING = 'UTF-8'

    Methods:
        _validate_config() -> List[str]              # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]       # Main entry point (265 lines)
        validate_config() -> bool                     # Legacy compatibility wrapper

    Internal Logic Flow (within _process):
        1. Handle None input -> return early
        2. Extract config (filename, sheetname, includeheader, append_file, create, die_on_error)
        3. Clean sheet name (strip quotes)
        4. Create output directory if needed
        5. Load or create workbook
        6. Get or create sheet
        7. Extract DataFrame from input (handles DataFrame, dict-with-main, dict-with-any-DF, list-of-dicts)
        8. Determine column order (output_schema priority > DataFrame columns)
        9. Convert DataFrame to list of row dicts via iterrows()
        10. Filter empty rows (is_non_empty_row)
        11. Determine header write (new file vs append with existing matching header)
        12. Write header row if needed
        13. Write data rows via sheet.append()
        14. Save workbook
        15. Update stats and return {'main': None}
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filename` | Mapped | -- |
| `SHEETNAME` | `sheetname` | Mapped | -- |
| `INCLUDEHEADER` | `includeheader` | Mapped | -- |
| `APPEND_FILE` | `append_file` | Mapped | -- |
| `CREATE` | `create` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped (unused) | -- |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P1 |
| `VERSION_2007` | `version_2007` | **Not Mapped** | P1 |
| `APPEND_SHEET` | `append_sheet` | **Not Mapped** | P2 |
| `FIRST_CELL_X` | `first_cell_x` | **Not Mapped** | P2 |
| `FIRST_CELL_Y` | `first_cell_y` | **Not Mapped** | P2 |
| `FIRST_CELL_Y_ABSOLUTE` | `first_cell_y_absolute` | **Not Mapped** | P2 |
| `AUTO_SIZE_SETTING` | `auto_size` | **Not Mapped** | P2 |
| `PROTECT_FILE` | `protect_file` | **Not Mapped** | P2 |
| `PASSWORD` | `password` | **Not Mapped** | P2 |
| `KEEP_CELL_FORMATING` | `keep_cell_format` | **Not Mapped** | P2 |
| `DELETE_EMPTYFILE` | `delete_emptyfile` | **Not Mapped** | P3 |
| `FONT` | `font` | **Not Mapped** | P3 |
| `CUSTOM_FLUSH_BUFFER` | `custom_flush` | **Not Mapped** | P3 |
| `FLUSH_ON_ROW` | `flush_on_row` | **Not Mapped** | P3 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** | P3 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** | P3 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** | P3 |
| `TRUNCATE_EXCEEDING_CHARACTERS` | `truncate_characters` | **Not Mapped** | P3 |
| `RECALCULATE_FORMULA` | `recalculate_formula` | **Not Mapped** | P3 |
| `STREAMING_APPEND` | `streaming_append` | **Not Mapped** | P3 |
| `USE_OUTPUT_STREAM` | `use_output_stream` | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- |
| `LABEL` | -- | Not needed | -- |
| `PROPERTY_TYPE` | -- | Not needed | -- |

---

## Appendix D: Empty Row Filtering Deep Dive

The `is_non_empty_row()` function (lines 263-269) is a critical piece of logic that determines which rows are written to Excel and which are silently discarded. Here is the complete decision matrix:

```python
def is_non_empty_row(row):
    return any(
        value is not None and
        str(value).strip() != '' and
        str(value).strip().lower() != 'nan'
        for value in row.values()
    )
```

### Decision Matrix

| Cell Value | `value is not None` | `str(value).strip() != ''` | `str().lower() != 'nan'` | Cell Passes? | Notes |
|------------|---------------------|---------------------------|--------------------------|-------------|-------|
| `None` | False | -- | -- | **No** | Correctly filtered |
| `''` (empty string) | True | False | -- | **No** | Correctly filtered |
| `'  '` (whitespace) | True | False (after strip) | -- | **No** | Correctly filtered |
| `'nan'` (string) | True | True | False | **No** | Filtered -- but this may be actual data |
| `float('nan')` | True | True (`'nan'`) | False | **No** | Correctly filtered |
| `0` | True | True (`'0'`) | True | **Yes** | Correct |
| `0.0` | True | True (`'0.0'`) | True | **Yes** | Correct |
| `False` | True | True (`'False'`) | True | **Yes** | Correct |
| `'hello'` | True | True | True | **Yes** | Correct |
| `pd.NaT` | True | True (`'NaT'`) | True | **Yes** | **BUG**: NaT passes filter, written to cell |

### Critical Observations

1. **`pd.NaT` (Not a Time) leaks through**: `str(pd.NaT)` is `'NaT'`, which is not `'nan'`, so NaT values are treated as non-empty. They will be written to Excel cells as the string `"NaT"`.

2. **String `'nan'` is filtered even as data**: If a column legitimately contains the string `"nan"` (e.g., a name, abbreviation), rows where that is the ONLY non-empty value will be incorrectly filtered as empty.

3. **The filter is ALL-or-nothing**: A row is filtered only if ALL values fail the checks. If even one value passes, the entire row is written -- including its NaN/None values in other columns.

4. **NaN values in non-empty rows leak to Excel**: The filter determines whether to WRITE the row, not whether to CLEAN individual cell values. NaN values in cells of otherwise-non-empty rows are written as-is.

### Talend Comparison

In Talend, the concept of "empty row filtering" does not exist in `tFileOutputExcel`. All input rows are written. Null values produce empty Excel cells. The v1 engine's empty row filtering is an **added behavior** not present in Talend, which may cause data loss if rows with all-null values are meaningful (e.g., separator rows in reports).

---

## Appendix E: Append Mode Header Detection Logic

The header detection in append mode (lines 281-321) is the most complex logic in the component. Here is the complete decision tree:

```
includeheader=true AND column_names exist?
  |
  No --> should_write_header = false (lines 282)
  |
  Yes --> append_file?
           |
           No --> should_write_header = true (new file, line 285)
           |
           Yes --> sheet.max_row == 0?   [DEAD CODE -- never true in openpyxl]
                    |
                    Yes --> should_write_header = true (line 291)
                    |
                    No --> sheet.max_row >= 1?
                            |
                            Yes --> Read first row values (line 296)
                                    |
                                    first_row matches expected headers?
                                    |
                                    Yes --> should_write_header = false (line 303)
                                    |
                                    No --> first row all empty?
                                           |
                                           Yes --> should_write_header = true (line 310)
                                           |
                                           No --> should_write_header = false (line 315)
                                                  (first row is data, don't add header)
```

### Edge Cases

| Scenario | Result | Correct? |
|----------|--------|----------|
| New file, includeheader=true | Header written | Yes |
| New file, includeheader=false | No header | Yes |
| Append, empty sheet, includeheader=true | Header written (via all-empty first row path) | Yes (accidentally) |
| Append, sheet has matching header | No duplicate header | Yes |
| Append, sheet has different header | No header added (data appended after existing) | **Debatable** -- data may be misaligned |
| Append, sheet has data (no header) | No header added | Yes (consistent with first-row-is-data check) |
| Append, includeheader=false | No header regardless | Yes |

### Risk: First-row comparison fragility

The comparison on line 300-301 does `first_row_cleaned == column_names_cleaned` which is an exact string match. If the existing header has slight differences (extra spaces, case differences, truncation), it will NOT match, and the code falls through to the "first row has data" path, skipping header insertion. This could lead to headerless data being appended after a near-matching header row.

---

## Appendix F: openpyxl Dependency Analysis

The engine uses `openpyxl` for all Excel operations. Here is the dependency analysis:

| Aspect | Detail |
|--------|--------|
| **Library** | `openpyxl` |
| **Import** | `import openpyxl` (line 8) -- top-level import, not conditional |
| **Usage** | `openpyxl.load_workbook()` (line 158), `openpyxl.Workbook()` (line 161) |
| **Output format** | `.xlsx` only (Excel 2007+ / Open XML) |
| **`.xls` support** | **None**. openpyxl does not support the legacy `.xls` format. Would need `xlwt` for writing or `xlrd` for reading `.xls` files. |
| **Streaming mode** | openpyxl supports `write_only=True` mode (SXSSF equivalent) for streaming large files. Not used by the engine. |
| **Memory model** | Default mode loads entire workbook into memory. |
| **Formula support** | openpyxl can read/preserve formulas. The engine does not interact with formulas. |
| **Formatting support** | openpyxl supports extensive cell formatting (fonts, colors, borders, number formats). Not used by the engine. |

### Talend Library Comparison

| Feature | Talend (VERSION_2007=false) | Talend (VERSION_2007=true) | V1 Engine |
|---------|---------------------------|---------------------------|-----------|
| Library | JExcelApi (jxl.jar) | Apache POI (XSSF/SXSSF) | openpyxl |
| Format | `.xls` | `.xlsx` | `.xlsx` only |
| Max rows | 65,536 | 1,048,576 | 1,048,576 |
| Max columns | 256 | 16,384 | 16,384 |
| Streaming write | No | Yes (SXSSF) | No (available but not used) |
| Protection | No | Yes | No (available but not used) |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileOutputExcel`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FOE-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FOE-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FOE-005 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FOE-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FOE-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FOE-003/BUG-FOE-006 -- NaN cell leakage

**File**: `src/v1/engine/components/file/file_output_excel.py`
**Lines**: 329-338

**Current code**:
```python
for row in non_empty_rows:
    if column_names:
        row_values = [row.get(col, '') for col in column_names]
    else:
        row_values = list(row.values())
    sheet.append(row_values)
    rows_written += 1
```

**Fix**:
```python
import math

def _sanitize_value(value):
    """Convert NaN/NaT to None for clean Excel output"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, 'isnull') and value != value:  # NaT check
        return None
    if str(value) == 'NaT':
        return None
    return value

for row in non_empty_rows:
    if column_names:
        row_values = [_sanitize_value(row.get(col, '')) for col in column_names]
    else:
        row_values = [_sanitize_value(v) for v in row.values()]
    sheet.append(row_values)
    rows_written += 1
```

**Impact**: Fixes "nan" and "NaT" strings appearing in Excel cells. **Risk**: Low -- converts NaN to empty cells, matching Talend behavior.

---

### Fix Guide: CONV-FOE-001 -- Extract DIE_ON_ERROR

**File**: `src/converters/complex_converter/component_parser.py`
**Location**: Inside `parse_tfileoutputexcel()` method (after line 1529)

**Add**:
```python
die_on_error_elem = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
if die_on_error_elem is not None:
    component['config']['die_on_error'] = die_on_error_elem.get('value', 'false').lower() == 'true'
else:
    component['config']['die_on_error'] = False  # Match Talend default
```

**Also fix engine default** in `file_output_excel.py` line 136:
Change: `die_on_error = self.config.get('die_on_error', True)`
To: `die_on_error = self.config.get('die_on_error', False)`

**Impact**: Fixes behavioral inversion where jobs crash instead of continuing on error. **Risk**: Low.

---

### Fix Guide: BUG-FOE-004 -- Fix sheet.max_row check

**File**: `src/v1/engine/components/file/file_output_excel.py`
**Line**: 289

**Current code**:
```python
if sheet.max_row == 0:
    # Sheet is completely empty
    should_write_header = True
```

**Fix**:
```python
# openpyxl reports max_row=1 for empty sheets, so check cell content
sheet_is_empty = (sheet.max_row <= 1 and
                  all(sheet.cell(1, c).value is None
                      for c in range(1, max(sheet.max_column, 1) + 1)))
if sheet_is_empty:
    # Sheet is genuinely empty (no data in any cell)
    should_write_header = True
```

**Impact**: Makes empty-sheet detection explicit and correct. **Risk**: Low.

---

## Appendix I: Comparison with Other File Output Components

| Feature | tFileOutputExcel (V1) | tFileOutputDelimited (V1) | tFileOutputPositional (V1) |
|---------|-----------------------|---------------------------|---------------------------|
| Basic writing | Yes | Yes | Yes |
| Schema enforcement | Yes (column ordering) | Yes | Yes |
| Include header | Yes | Yes | N/A |
| Append mode | Yes | Yes | N/A |
| Create directory | Yes | Yes | N/A |
| Die on error | Yes (default mismatch) | Yes | Yes |
| Encoding | Extracted but unused | Yes | Yes |
| NaN handling | **Bug** (leaks to cells) | N/A (text output) | N/A |
| Empty row filtering | Yes (non-standard) | No | No |
| Column auto-sizing | **No** | N/A | N/A |
| Cell positioning | **No** | N/A | N/A |
| Password protection | **No** | N/A | N/A |
| GlobalMap FILENAME | **No** | **No** | **No** |
| V1 Unit tests | **No** | **No** | **No** |
| Returns main output | No (sink) | No (sink) | No (sink) |

**Observation**: The missing globalMap variables and lack of v1 unit tests are systemic issues across ALL file output components. This suggests architectural omissions rather than component-specific oversights.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs expecting `.xls` output (VERSION_2007=false) | **Critical** | Any job not explicitly setting VERSION_2007=true (Talend default is false) | Must extract VERSION_2007; either add xlwt or document xlsx-only limitation |
| Jobs relying on `die_on_error=false` behavior | **High** | Jobs with error handling flows after Excel write | Must extract DIE_ON_ERROR and fix engine default |
| Jobs with NaN/null values in data | **High** | Most ETL jobs -- nulls are common | Must fix NaN sanitization before writing |
| Jobs using cell positioning (FIRST_CELL_X/Y) | **High** | Template-based report generation jobs | Must implement cell positioning |
| Jobs using `{id}_NB_LINE` in downstream | **Medium** | Jobs with audit/logging checking row counts | Cross-cutting bug blocks ALL globalMap access |
| Jobs using column auto-sizing | **Medium** | Report generation jobs | Implement auto-sizing for production reports |
| Jobs using password protection | **Medium** | Compliance-required protected outputs | Implement protection for regulated environments |
| Jobs appending to large Excel files | **Medium** | Incremental data export jobs | Memory risk for large files |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using FONT setting | Low | Visual formatting -- data integrity unaffected |
| Jobs using ADVANCED_SEPARATOR | Low | Number formatting in cells |
| Jobs using TRUNCATE_EXCEEDING_CHARACTERS | Low | Rare -- most cell values under 32K chars |
| Jobs using RECALCULATE_FORMULA | Low | Relevant only for formula-heavy templates |
| Jobs using STREAMING_APPEND | Low | Performance optimization, not correctness |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting). Fix NaN leakage. Fix DIE_ON_ERROR default. Run basic Excel output test.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which P1 features are used (VERSION_2007, cell positioning, auto-size).
3. **Phase 3**: Implement P1 features required by target jobs.
4. **Phase 4**: Parallel-run migrated jobs against Talend originals. Open output Excel files side-by-side and compare cell-by-cell for first 100 rows.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix K: Complete Dedicated Parser Implementation

The following is the recommended enhanced version of `parse_tfileoutputexcel()` that extracts all critical parameters:

```python
def parse_tfileoutputexcel(self, node, component: Dict) -> Dict:
    """
    Parse tFileOutputExcel specific configuration from Talend XML node.

    Extracts all Talend parameters for Excel file output including
    format selection, positioning, formatting, and protection settings.

    Talend Parameters:
        FILENAME (str): Output file path. Mandatory.
        SHEETNAME (str): Sheet name. Default "Sheet1"
        INCLUDEHEADER (bool): Include header row. Default false
        APPEND_FILE (bool): Append to existing file. Default false
        APPEND_SHEET (bool): Append to existing sheet. Default false
        CREATE (bool): Create directory if not exists. Default true
        DIE_ON_ERROR (bool): Fail on error. Default false
        VERSION_2007 (bool): Write .xlsx format. Default false
        ENCODING (str): File encoding. Default system
        FIRST_CELL_X (int): Starting column offset. Default 0
        FIRST_CELL_Y (int): Starting row offset. Default 0
        AUTO_SIZE_SETTING (bool): Auto-size columns. Default false
        PROTECT_FILE (bool): Password protect. Default false
        PASSWORD (str): Protection password.
        FONT (str): Font family.
        DELETE_EMPTYFILE (bool): Don't create empty file. Default false
        FLUSH_ON_ROW (int): Flush buffer interval. Default 1000
    """
    config = component['config']

    # Helper to safely get element parameter value
    def get_param(name, default=''):
        elem = node.find(f'.//elementParameter[@name="{name}"]')
        if elem is not None:
            return elem.get('value', default)
        return default

    def get_bool(name, default=False):
        val = get_param(name, str(default).lower())
        return val.lower() == 'true'

    def get_int(name, default=0):
        val = get_param(name, str(default))
        return int(val) if val.isdigit() else default

    # Core settings
    filename_raw = get_param('FILENAME', '')
    config['filename'] = self.expr_converter.mark_java_expression(filename_raw) if hasattr(self, 'expr_converter') else filename_raw

    sheetname_raw = get_param('SHEETNAME', 'Sheet1')
    config['sheetname'] = self.expr_converter.mark_java_expression(sheetname_raw) if hasattr(self, 'expr_converter') else sheetname_raw

    config['includeheader'] = get_bool('INCLUDEHEADER', False)
    config['append_file'] = get_bool('APPEND_FILE', False)
    config['append_sheet'] = get_bool('APPEND_SHEET', False)
    config['create'] = get_bool('CREATE', True)
    config['die_on_error'] = get_bool('DIE_ON_ERROR', False)
    config['version_2007'] = get_bool('VERSION_2007', False)

    # Encoding
    config['encoding'] = get_param('ENCODING', 'UTF-8')

    # Cell positioning
    config['first_cell_x'] = get_int('FIRST_CELL_X', 0)
    config['first_cell_y'] = get_int('FIRST_CELL_Y', 0)
    config['first_cell_y_absolute'] = get_bool('FIRST_CELL_Y_ABSOLUTE', False)

    # Formatting
    config['auto_size'] = get_bool('AUTO_SIZE_SETTING', False)
    config['font'] = get_param('FONT', '')
    config['keep_cell_format'] = get_bool('KEEP_CELL_FORMATING', False)

    # Protection
    config['protect_file'] = get_bool('PROTECT_FILE', False)
    config['password'] = get_param('PASSWORD', '')

    # Advanced
    config['delete_emptyfile'] = get_bool('DELETE_EMPTYFILE', False)
    config['flush_on_row'] = get_int('FLUSH_ON_ROW', 1000)
    config['truncate_characters'] = get_bool('TRUNCATE_EXCEEDING_CHARACTERS', False)
    config['recalculate_formula'] = get_bool('RECALCULATE_FORMULA', False)
    config['streaming_append'] = get_bool('STREAMING_APPEND', False)

    # Number formatting
    config['advanced_separator'] = get_bool('ADVANCED_SEPARATOR', False)
    config['thousands_separator'] = get_param('THOUSANDS_SEPARATOR', ',')
    config['decimal_separator'] = get_param('DECIMAL_SEPARATOR', '.')

    return component
```

**Key improvements over current implementation**:
1. Extracts ALL 25+ parameters instead of just 6
2. Marks `FILENAME` and `SHEETNAME` with Java expression markers
3. Uses correct Talend default for `DIE_ON_ERROR` (false)
4. Extracts `VERSION_2007` for format selection
5. Separates `APPEND_FILE` and `APPEND_SHEET`
6. Includes cell positioning, formatting, and protection parameters
7. Uses safe helper functions for type conversion

---

## Appendix L: Base Component `_update_global_map()` Detailed Analysis

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

**Bug analysis** (BUG-FOE-001):
- The for loop variable is `stat_value` (line 301), but the log statement references `value` (line 304)
- `stat_name` on line 304 references the loop variable from line 301, which will have the value from the LAST iteration of the for loop (i.e., `EXECUTION_TIME` since that is the last key in the `stats` dict)
- `value` is completely undefined in this scope, causing `NameError`
- This method is called from `execute()` (line 218) after EVERY component execution
- Since `self.global_map` is set by the engine during component instantiation, this bug will crash ANY component that runs in a job with a global map configured

**Call chain**:
1. `ETLEngine._execute_component()` calls `component.execute(input_data)`
2. `BaseComponent.execute()` calls `self._update_global_map()` on line 218 (success path) or line 231 (error path)
3. `_update_global_map()` crashes with `NameError: name 'value' is not defined`

**Severity**: This is the highest-severity bug in the v1 engine. It prevents ANY component from completing execution when a global map is present. The fix is trivial (see Fix Guide in Appendix H) but the impact is cross-cutting.

---

## Appendix M: `GlobalMap.get()` Detailed Analysis

The `GlobalMap.get()` method in `global_map.py` (lines 26-28) has a complementary bug:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # BUG: 'default' not in signature
```

**Bug analysis** (BUG-FOE-002):
- `default` is referenced in the body (line 28) but is not a parameter in the method signature (line 26)
- The method signature only accepts `key: str`
- Any call to `global_map.get("some_key")` will crash with `NameError: name 'default' is not defined`

**Cascading impact**:
- `get_component_stat()` (line 51-58) calls `self.get(key, default)` with TWO arguments, but `get()` only accepts ONE positional argument. This would cause `TypeError: get() takes 2 positional arguments but 3 were given`
- `get_nb_line()`, `get_nb_line_ok()`, `get_nb_line_reject()` all call `get_component_stat()` which calls `get()` with two args

**Fix**: Add `default: Any = None` to the `get()` method signature. This fixes both the `NameError` (direct calls) and the `TypeError` (two-argument calls from `get_component_stat()`).

---

## Appendix N: Data Flow Through FileOutputExcel

### Input Data Detection Logic

The component supports multiple input formats, detected in priority order:

```
Input Data
    |
    Is DataFrame directly?  (line 197)
    |
    Yes --> main_data = input_data
    |
    No --> Is dict?  (line 200)
            |
            Yes --> Has 'main' key?  (line 202)
            |        |
            |        Yes --> main_data = input_data['main']
            |        |
            |        No --> Scan all keys for first DataFrame (lines 210-214)
            |                (skip 'stats', check hasattr 'iterrows')
            |                |
            |                Found --> main_data = value
            |                Not found --> main_data = None
            |
            No --> main_data = None

main_data type?
    |
    DataFrame --> Convert via iterrows() to list of dicts (lines 234-244)
    |
    list (of dicts) --> Use directly (lines 246-255)
    |
    Other/None --> Empty rows, 0 stats (lines 257-260)
```

### Output Behavior

The component is a **sink** -- it always returns `{'main': None}`. No data passes through. The `stats` key is added by `BaseComponent.execute()` (line 223) after `_process()` returns. The only meaningful output is the written Excel file on disk and the statistics in globalMap.

---

## Appendix O: Comparison with tFileInputExcel Converter

For reference, the `tFileInputExcel` converter parser is separate but complementary. Comparing the two Excel component parsers:

| Aspect | tFileInputExcel Parser | tFileOutputExcel Parser |
|--------|----------------------|------------------------|
| Method | Not found in search (likely generic) | `parse_tfileoutputexcel()` |
| Parameters extracted | Unknown | 6 |
| Java expression marking | Unknown | **No** |
| DIE_ON_ERROR | Unknown | **Not extracted** |
| Dedicated method | Unknown | Yes (minimal) |

Both Excel components share the same underlying library issue: the v1 engine uses `openpyxl` which only supports `.xlsx` format, while Talend defaults to `.xls` for both input and output when VERSION_2007 is not explicitly set to true.

---

## Appendix P: Source References

- [tFileOutputExcel Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/excel/tfileoutputexcel-standard-properties) -- Official Talend documentation for Basic and Advanced Settings.
- [tFileOutputExcel Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/excel/tfileoutputexcel-standard-properties) -- Talend 7.3 documentation.
- [tFileOutputExcel Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/excel/tfileoutputexcel) -- Component overview, family, purpose.
- [tFileOutputExcel (Talend Skill v6.5.1)](https://talendskill.com/knowledgebase/tfileoutputexcel-talend-components-v6-5-1-20180116_1512/) -- Connector types, returns, and required modules.
- [tFileOutputExcel Docs for ESB 5.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-5-x/tfileoutputexcel-docs-for-esb-5-x/) -- ESB-specific documentation.
- [tFileOutputExcel NB_LINE Discussion (Talend Community)](https://community.talend.com/t5/Design-and-Development/tFileOutputExcel-1-NB-LINE-leads-to-null-pointer-exception/td-p/104605) -- NB_LINE null pointer exception discussion.
- [tFileOutputExcel tdi-studio-se (GitHub)](https://github.com/Talend/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputExcel/tFileOutputExcel_begin.javajet) -- Talend source code with ElementParameterParser parameter names.
- [tFileExcel Components (GitHub)](https://github.com/jlolling/talendcomp_tFileExcel) -- Community Excel component suite for Talend.

---

## Appendix Q: Edge Case Analysis

### Edge Case 1: Empty input (None)

| Aspect | Detail |
|--------|--------|
| **Talend** | NB_LINE=0, NB_LINE_OK=0. No file created (if DELETE_EMPTYFILE=true) or empty file created. |
| **V1** | Returns `{'main': None, 'stats': {'NB_LINE': 0, 'NB_LINE_OK': 0, 'NB_LINE_REJECT': 0}}`. Does NOT create/modify any file. |
| **Verdict** | CORRECT for None input. But if Talend would create an empty file (DELETE_EMPTYFILE=false, the default), v1 does not. Minor gap -- input typically comes from upstream components, not as explicit None. |

### Edge Case 2: Empty DataFrame (0 rows, columns defined)

| Aspect | Detail |
|--------|--------|
| **Talend** | Creates file with header row (if INCLUDEHEADER=true) and 0 data rows. NB_LINE=0. |
| **V1** | DataFrame has 0 rows. `rows_in = len(main_data) = 0`. Empty `rows` list. `non_empty_rows` is empty. If `includeheader=true`, header IS written (because `column_names` populated from schema/DataFrame columns). Workbook saved with just the header row. NB_LINE=0, NB_LINE_OK=0. |
| **Verdict** | CORRECT -- empty DataFrame with header produces correct output. |

### Edge Case 3: DataFrame with ALL rows being NaN/empty

| Aspect | Detail |
|--------|--------|
| **Talend** | All rows written (even if all null). NB_LINE = total rows. Cells are empty. |
| **V1** | All rows filtered by `is_non_empty_row()`. `rows_rejected = len(rows) - 0 = total rows`. `rows_out = 0`. Only header written (if enabled). |
| **Verdict** | **BEHAVIORAL DIFFERENCE** -- v1 silently drops rows that Talend would write. This empty-row filtering is a v1-specific behavior NOT present in Talend. Could cause data loss for jobs that use empty rows as separators or placeholders. |

### Edge Case 4: DataFrame with NaN in specific cells (non-empty rows)

| Aspect | Detail |
|--------|--------|
| **Talend** | NaN/null values become empty cells in Excel. Row is written intact. |
| **V1** | Row passes `is_non_empty_row()` (because at least one value is non-empty). NaN values in other cells are passed to `sheet.append()` as `float('nan')`. openpyxl writes this as a numeric cell containing NaN, which may display as `#NUM!` error or the string "nan" in Excel depending on version. |
| **Verdict** | **BUG** -- NaN values should be converted to `None` before writing. See BUG-FOE-006. |

### Edge Case 5: DataFrame with pd.NaT (Not a Time) values

| Aspect | Detail |
|--------|--------|
| **Talend** | Null dates become empty cells. |
| **V1** | `pd.NaT` passes the `is_non_empty_row()` filter (because `str(pd.NaT) = 'NaT'` which is not `'nan'`). When written via `sheet.append()`, openpyxl may render it as the string `"NaT"` in the cell. |
| **Verdict** | **BUG** -- NaT should be converted to None. |

### Edge Case 6: Very large DataFrame (100K+ rows)

| Aspect | Detail |
|--------|--------|
| **Talend** | With STREAMING_APPEND or VERSION_2007=true with SXSSF, handles efficiently with bounded memory. |
| **V1** | All rows converted to list of dicts via `iterrows()` (slow). All rows held in memory. Then written one-by-one via `sheet.append()`. Entire workbook held in memory until `workbook.save()`. For 100K rows x 50 columns, memory usage could be several hundred MB. |
| **Verdict** | **PERFORMANCE GAP** -- works but slow and memory-intensive. |

### Edge Case 7: Appending to non-existent file

| Aspect | Detail |
|--------|--------|
| **Talend** | If APPEND_FILE=true but file does not exist, creates new file. |
| **V1** | Line 157: `if append_file and os.path.exists(filename):` -- if file does not exist, falls through to `else` branch (line 161) which creates a new workbook. |
| **Verdict** | CORRECT -- creates new file when appending to non-existent path. |

### Edge Case 8: Appending to file with different sheet name

| Aspect | Detail |
|--------|--------|
| **Talend** | Opens existing file, creates new sheet with specified name, writes data to new sheet. |
| **V1** | Opens existing workbook (line 158). Checks if `sheet_name in workbook.sheetnames` (line 178). If not found, creates new sheet (line 182). Writes data to new sheet. |
| **Verdict** | CORRECT -- new sheets are created in existing workbooks. |

### Edge Case 9: Sheet name with invalid Excel characters

| Aspect | Detail |
|--------|--------|
| **Talend** | Java Excel libraries handle validation. Invalid characters cause error. |
| **V1** | openpyxl does NOT validate sheet names by default. Characters like `/ \ * ? [ ]` are passed through. Excel may reject the file when opening. |
| **Verdict** | **GAP** -- no sheet name validation. Could produce corrupt files. |

### Edge Case 10: Filename with context variable

| Aspect | Detail |
|--------|--------|
| **Talend** | `context.output_dir + "/report.xlsx"` resolved by Java runtime. |
| **V1** | Simple `${context.var}` references resolved by `ContextManager.resolve_dict()`. Complex expressions (with `+` concatenation) are NOT resolved because converter does not call `mark_java_expression()`. |
| **Verdict** | **PARTIAL** -- simple context vars work, expressions do not. See CONV-FOE-007. |

### Edge Case 11: File path with spaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `os.path.exists()`, `os.makedirs()`, and `openpyxl` all handle spaces correctly. |
| **Verdict** | CORRECT |

### Edge Case 12: Writing boolean values

| Aspect | Detail |
|--------|--------|
| **Talend** | Boolean values written as `TRUE`/`FALSE` in Excel cells. |
| **V1** | Python `True`/`False` written via `sheet.append()`. openpyxl writes these as Excel boolean cells (`TRUE`/`FALSE`). |
| **Verdict** | CORRECT |

### Edge Case 13: Writing date/datetime values

| Aspect | Detail |
|--------|--------|
| **Talend** | Dates formatted according to schema pattern. Written as Excel date serial numbers with formatting. |
| **V1** | Python `datetime` objects written via `sheet.append()`. openpyxl writes these as Excel date serial numbers (correct). However, no number format is applied, so cells may display as numbers (e.g., `45000`) rather than formatted dates. |
| **Verdict** | **PARTIAL** -- dates are written correctly as serial numbers but may display incorrectly without cell formatting. |

### Edge Case 14: Writing Decimal (BigDecimal) values

| Aspect | Detail |
|--------|--------|
| **Talend** | BigDecimal values written with full precision. |
| **V1** | Python `Decimal` objects may not be handled by openpyxl natively. openpyxl converts to float for numeric cells, potentially losing precision. |
| **Verdict** | **POTENTIAL GAP** -- Decimal precision may be lost during write. |

### Edge Case 15: Output schema column order differs from DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Schema defines column order in output. |
| **V1** | Lines 225-227: when `output_schema` is set, column order from schema is used. Lines 236-243: each row dict is built using schema column order. If a schema column is missing from DataFrame, empty string is used (line 242). |
| **Verdict** | CORRECT -- schema column ordering is properly implemented. |

### Edge Case 16: Schema column not in DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Missing columns produce null/empty values. |
| **V1** | Line 241-243: `if col in main_data.columns: row_dict[col] = pandas_row[col] else: row_dict[col] = ''`. Defaults to empty string for missing columns. Logs a warning. |
| **Verdict** | CORRECT -- graceful handling with logging. |

### Edge Case 17: Concurrent writes to same file

| Aspect | Detail |
|--------|--------|
| **Talend** | Multiple tFileOutputExcel in same subjob: last write wins (documented behavior). |
| **V1** | No file locking. Concurrent writes from different threads/processes could corrupt the file. Within a single-threaded v1 engine execution, sequential writes behave like Talend (last write wins). |
| **Verdict** | CORRECT for single-threaded. **GAP** for concurrent execution. |

### Edge Case 18: Component receives dict without 'main' key or any DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Would not normally receive non-DataFrame input. |
| **V1** | Lines 205-214 search for first non-stats DataFrame in dict. If none found, `main_data` remains None. Lines 257-260 handle this: logs warning, sets `rows = []`, `column_names = []`, `rows_in = 0`. Result: empty or header-only file. |
| **Verdict** | CORRECT -- graceful degradation for unexpected input shapes. |

### Edge Case 19: Workbook save fails (disk full, permissions)

| Aspect | Detail |
|--------|--------|
| **Talend** | Error handling based on DIE_ON_ERROR setting. |
| **V1** | Lines 344-354: try/except around `workbook.save(filename)`. If `die_on_error=True`, raises `FileOperationError`. If `False`, logs error, calls `_update_stats(rows_in, 0, rows_rejected)` and returns `{'main': None}`. |
| **Verdict** | CORRECT -- save errors are properly handled in both die_on_error modes. |

### Edge Case 20: Input data as list of dicts with inconsistent keys

| Aspect | Detail |
|--------|--------|
| **Talend** | Schema defines structure. Missing fields get null. |
| **V1** | Lines 246-255: list-of-dicts handled. Column names from `output_schema` or `rows[0].keys()`. Line 333: `row.get(col, '')` handles missing keys with empty string default. |
| **Verdict** | CORRECT -- missing keys produce empty cells. |

---

## Appendix R: `_process()` Method Detailed Walkthrough

### Lines 96-114: Method Signature and Empty Input Handling

```python
def _process(self, input_data: Union[Dict[str, Any], pd.DataFrame, None] = None) -> Dict[str, Any]:
```

The method accepts three input types: a raw `DataFrame`, a `dict` containing DataFrames (common output format from upstream components like `tMap`), or `None`. The `Union` type hint correctly documents this flexibility.

**Empty input guard** (lines 111-114): When `input_data is None`, the component immediately returns without creating any file. This differs subtly from Talend where even with no input rows, the file might be created (empty or with header only). The early return bypasses all workbook creation logic.

### Lines 122-136: Configuration Extraction

Configuration values are extracted with defaults:
- `filename`: Required, no default (will fail if missing)
- `sheet_name`: Default `'Sheet1'` (class constant)
- `include_header`: Default `False` (matches Talend)
- `append_file`: Default `False` (matches Talend)
- `create_file`: Default `True` (matches Talend)
- `die_on_error`: Default `True` (**DOES NOT match Talend default of `false`**)

### Lines 127-131: Sheet Name Quote Stripping

The code strips enclosing single or double quotes from sheet names:
```python
if sheet_name.startswith("'") and sheet_name.endswith("'"):
    sheet_name = sheet_name[1:-1]
elif sheet_name.startswith('"') and sheet_name.endswith('"'):
    sheet_name = sheet_name[1:-1]
```

This handles cases where the Talend XML stores sheet names as `"'Sheet1'"` (with embedded quotes). The stripping is necessary because Talend's Java code generation wraps string literals in quotes.

### Lines 141-153: Directory Creation

Uses `os.makedirs()` with `create_file` flag. Error handling with `die_on_error` -- on failure, either raises `FileOperationError` or returns early with zero stats. The `output_dir = os.path.dirname(filename)` correctly handles relative paths (returns empty string for filename-only paths) with the guard `if create_file and output_dir and not os.path.exists(output_dir)`.

### Lines 156-174: Workbook Load/Create

Two paths:
1. **Append mode + file exists**: `openpyxl.load_workbook(filename)` loads entire workbook into memory
2. **Otherwise**: `openpyxl.Workbook()` creates new blank workbook

The default sheet cleanup (lines 163-166) removes the auto-created 'Sheet' if the target sheet name is different. This prevents orphan tabs in the output.

### Lines 177-191: Sheet Get/Create

If `sheet_name` already exists in the workbook, uses the existing sheet. Otherwise creates a new one with `workbook.create_sheet(sheet_name)`. In append mode with an existing file, this correctly supports writing to pre-existing sheets or adding new sheets to the workbook.

### Lines 193-260: Input Data Extraction

This is the most complex data extraction logic in the component, handling four input shapes:

1. **Direct DataFrame** (line 197-199): Simplest case
2. **Dict with 'main' key** (line 202): Standard upstream output format
3. **Dict with any DataFrame** (lines 205-214): Auto-detection for non-standard output formats. Skips 'stats' key. Uses `hasattr(value, 'iterrows')` as DataFrame duck-type check.
4. **List of dicts** (lines 246-255): Legacy format support

### Lines 262-272: Empty Row Filtering

The `is_non_empty_row()` inner function defines what constitutes an "empty" row. See Appendix D for the complete decision matrix. Key observation: this filtering is a v1-specific behavior NOT present in Talend, which writes all rows regardless of content.

### Lines 276-325: Header Write Logic

The header write decision tree is documented in Appendix E. This is the most intricate logic in the component, with 5 different code paths and a known bug (BUG-FOE-004) where `sheet.max_row == 0` is dead code.

### Lines 328-339: Data Row Writing

Simple loop calling `sheet.append()` for each non-empty row. Column ordering is handled by the `column_names` list populated earlier. Default empty string for missing columns via `row.get(col, '')`.

### Lines 342-360: Save and Statistics

Workbook saved with `workbook.save(filename)`. Save errors handled with `die_on_error` flag. Statistics updated and logged. Returns `{'main': None, 'stats': self.stats}`.

### Lines 362-367: Catch-All Exception Handler

Re-raises custom exceptions (`FileOperationError`, `ComponentExecutionError`). All other exceptions wrapped in `ComponentExecutionError` with `from e` chaining.

### Lines 370-382: Legacy Compatibility Method

`validate_config() -> bool` wraps `_validate_config()` for backward compatibility. Since neither is ever called, both are dead code.

---

## Appendix S: ComponentStatus Lifecycle for FileOutputExcel

The component status transitions through these states during execution, managed by `BaseComponent.execute()`:

```
PENDING (initial)
    |
    v
RUNNING (set at execute() start, line 192)
    |
    +---> _resolve_java_expressions() (if Java bridge available)
    |
    +---> context_manager.resolve_dict() (if context manager available)
    |
    +---> _process() called
    |        |
    |        +---> None input --> return early (stats 0,0,0)
    |        |
    |        +---> Normal processing --> write Excel --> return {'main': None}
    |        |
    |        +---> Error + die_on_error=false --> return {'main': None}
    |        |
    |        +---> Error + die_on_error=true --> raise exception
    |
    +---> _update_global_map() [BUG: crashes with NameError]
    |
    +---> SUCCESS (line 220)
    |
    |---> Or on exception:
    |        |
    |        +---> ERROR (line 228)
    |        +---> error_message stored (line 229)
    |        +---> _update_global_map() [BUG: crashes with NameError]
    |        +---> Re-raise exception
```

**Key observation**: The `_update_global_map()` bug (BUG-FOE-001) means the component NEVER reaches `SUCCESS` status when a global map is configured. It always crashes with `NameError` on line 304 of `base_component.py`, producing an `ERROR` status even for successful writes. The Excel file IS written successfully (workbook.save() happens before _update_global_map()), but the component reports failure.

This means the SUBJOB_ERROR trigger would fire instead of SUBJOB_OK, and downstream components connected via COMPONENT_OK would not execute. The file exists on disk but the job reports failure.
