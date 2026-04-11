# Audit Report: tFileInputExcel / FileInputExcel

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE (REWRITE)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileInputExcel` |
| **V1 Engine Class** | `FileInputExcel` |
| **Engine File** | `src/v1/engine/components/file/file_input_excel.py` (1022 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_excel.py` (263 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputExcel")` decorator-based dispatch |
| **Registry Aliases** | `FileInputExcel`, `tFileInputExcel` |
| **Category** | File / Input |
| **Complexity** | High -- dual engine (.xls via xlrd / .xlsx via openpyxl), password support, multi-sheet with regex matching, advanced separators, date conversion, column-level trimming, 3 generation modes |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_input_excel.py` | Engine implementation (1022 lines) |
| `src/converters/talend_to_v1/components/file/file_input_excel.py` | Converter class (263 lines) |
| `tests/converters/talend_to_v1/components/test_file_input_excel.py` | Converter tests (83 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 30/30 params extracted (100%); 3 TABLE parsers; 9 needs_review; 3 critical defaults fixed; 83 tests |
| Engine Feature Parity | **Y** | 2 | 4 | 3 | 2 | 9 config keys not read by engine; no REJECT flow; password decryption incomplete; dead code |
| Code Quality | **Y** | 2 | 3 | 5 | 3 | Cross-cutting base class bugs; dead methods; duplicated read logic; _validate_config never called |
| Performance & Memory | **G** | 0 | 1 | 1 | 1 | Streaming mode works; batch/streaming auto-detection; large spreadsheet memory pressure |
| Testing | **Y** | 0 | 1 | 0 | 0 | 83 converter tests (Green); zero engine unit tests (Yellow per scoring rules) |

Overall: GREEN -- Converter production-ready; engine has known gaps documented via needs_review

**Top Actions**: Engine tests needed for Yellow->Green testing; password decryption; REJECT flow; remove dead code

---

## 3. Talend Feature Baseline

### What tFileInputExcel Does

tFileInputExcel reads data from Microsoft Excel files, supporting both legacy .xls (BIFF8/xlrd) and modern .xlsx (Office Open XML/openpyxl) formats. It is one of Talend's most feature-rich file input components, with 28 unique parameters plus 2 framework parameters.

The component supports password-protected workbooks, multi-sheet reading with regex-based sheet name matching, configurable header/footer row skipping, column range selection, per-column trimming, date-to-string conversion with custom patterns, advanced number separators for international formats, and three generation modes (USER_MODE, EVENT_MODE, STREAM_MODE) controlling memory usage and processing strategy.

**Source**: Talaxie GitHub `tFileInputExcel_java.xml`
**Component family**: File / Input
**Available in**: Talend Open Studio, Talend Data Integration, Talend Big Data
**Required JARs**: None (built-in; uses Apache POI internally)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Excel 2007 format | `VERSION_2007` | BOOLEAN | `false` | When true, forces .xlsx (OOXML) processing; when false, auto-detects from file extension |
| 2 | File path | `FILENAME` | FILE | `""` | Path to the Excel file to read (required) |
| 3 | Password | `PASSWORD` | PASSWORD | `""` | Password for encrypted workbooks |
| 4 | All sheets | `ALL_SHEETS` | BOOLEAN | `false` | When true, reads all sheets; when false, uses SHEETLIST |
| 5 | Sheet list | `SHEETLIST` | TABLE | `[]` | List of sheets to read with optional regex matching (stride-2: SHEETNAME, USE_REGEX) |
| 6 | Header rows | `HEADER` | INT | `0` | Number of header rows to skip |
| 7 | Footer rows | `FOOTER` | INT | `0` | Number of footer rows to skip from bottom |
| 8 | Row limit | `LIMIT` | TEXT | `""` | Maximum number of rows to read (empty = unlimited) |
| 9 | Affect each sheet | `AFFECT_EACH_SHEET` | TEXT | `""` | Apply header/footer/limit independently per sheet |
| 10 | First column | `FIRST_COLUMN` | INT | `1` | First column to read (1-based) |
| 11 | Last column | `LAST_COLUMN` | TEXT | `""` | Last column to read (empty = all remaining) |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 12 | Die on error | `DIE_ON_ERROR` | BOOLEAN | `false` | When true, job fails on read error; when false, returns empty result |
| 13 | Advanced separator | `ADVANCED_SEPARATOR` | BOOLEAN | `false` | Enable custom number separators |
| 14 | Thousands separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands grouping character |
| 15 | Decimal separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal point character |
| 16 | Trim all | `TRIMALL` | BOOLEAN | `false` | Trim whitespace from all string columns |
| 17 | Trim select | `TRIMSELECT` | TABLE | `[]` | Per-column trim settings (stride-2: SCHEMA_COLUMN, TRIM) |
| 18 | Convert date to string | `CONVERTDATETOSTRING` | BOOLEAN | `false` | Convert date cells to string using patterns |
| 19 | Date select | `DATESELECT` | TABLE | `[]` | Per-column date conversion patterns (stride-3: SCHEMA_COLUMN, CONVERTDATE, PATTERN) |
| 20 | Encoding | `ENCODING` | ENCODING | `"ISO-8859-15"` | Character encoding for string data |
| 21 | Read real value | `READ_REAL_VALUE` | BOOLEAN | `false` | Read underlying cell value instead of formatted display |
| 22 | Stop on empty row | `STOPREAD_ON_EMPTYROW` | BOOLEAN | `false` | Stop reading when an empty row is encountered |
| 23 | No validate on cell | `NOVALIDATE_ON_CELL` | BOOLEAN | `false` | Skip cell type validation |
| 24 | Suppress warnings | `SUPPRESS_WARN` | BOOLEAN | `false` | Suppress non-fatal warnings |
| 25 | Generation mode | `GENERATION_MODE` | CLOSED_LIST | `"USER_MODE"` | Processing mode: USER_MODE (default), EVENT_MODE (SAX), STREAM_MODE (streaming) |
| 26 | Include phonetic runs | `INCLUDE_PHONETICRUNS` | BOOLEAN | `true` | Include East Asian phonetic annotations in Event mode |
| 27 | Configure inflation ratio | `CONFIGURE_INFLATION_RATIO` | BOOLEAN | `false` | Enable custom ZIP inflation ratio (zip bomb protection) |
| 28 | Inflation ratio | `INFLATION_RATIO` | TEXT | `""` | Custom inflation ratio value |

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 29 | Stat catcher | `TSTATCATCHER_STATS` | BOOLEAN | `false` | Enable statistics collection |
| 30 | Label | `LABEL` | TEXT | `""` | Component label for display |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Data rows read from Excel file |
| `REJECT` | Output | Row > Reject | Rows that fail validation (with errorCode/errorMessage columns) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob encounters an error |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of data rows read |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully processed |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rejected rows |
| `{id}_CURRENT_SHEET` | String | During execution | Name of the sheet currently being read |

### 3.6 Behavioral Notes

1. **Encoding default is ISO-8859-15** (Latin-9), NOT UTF-8. This is the standard Talend default for European locale components.
2. **DIE_ON_ERROR defaults to false** per _java.xml. The component returns empty result on error rather than failing the job.
3. **GENERATION_MODE defaults to USER_MODE** (DOM-based), not EVENT_MODE (SAX). USER_MODE loads the entire workbook into memory, while EVENT_MODE uses SAX streaming for lower memory usage.
4. **SHEETLIST uses stride-2 TABLE** with SHEETNAME and USE_REGEX fields. Each sheet entry can optionally use regex matching for sheet names.
5. **DATESELECT uses stride-3 TABLE** with SCHEMA_COLUMN, CONVERTDATE, and PATTERN fields. Patterns are Java SimpleDateFormat strings.
6. **FIRST_COLUMN is 1-based** (not 0-based). Value 1 means start from column A.
7. **INCLUDE_PHONETICRUNS defaults to true** -- relevant only in Event mode for East Asian languages.
8. **INFLATION_RATIO** is a zip bomb protection feature added in Talend 8.0+ to prevent DoS via crafted .xlsx files.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `FileInputExcelConverter` in `src/converters/talend_to_v1/components/file/file_input_excel.py` uses the gold-standard pattern: `_build_component_dict` with `type_name="FileInputExcel"`, module-level TABLE parsers (`_parse_sheetlist`, `_parse_trim_select`, `_parse_date_select`), and per-feature `needs_review` entries for all 9 engine gaps.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `VERSION_2007` | Yes | `version_2007` | bool, default False |
| 2 | `FILENAME` | Yes | `filepath` | str, default "" |
| 3 | `PASSWORD` | Yes | `password` | str, always empty -- cleared for security |
| 4 | `ALL_SHEETS` | Yes | `all_sheets` | bool, default False |
| 5 | `SHEETLIST` | Yes | `sheetlist` | TABLE, module-level `_parse_sheetlist()` |
| 6 | `HEADER` | Yes | `header` | int, default 0 |
| 7 | `FOOTER` | Yes | `footer` | int, default 0 |
| 8 | `LIMIT` | Yes | `limit` | str, default "" |
| 9 | `AFFECT_EACH_SHEET` | Yes | `affect_each_sheet` | str, default "" |
| 10 | `FIRST_COLUMN` | Yes | `first_column` | int, default 1 |
| 11 | `LAST_COLUMN` | Yes | `last_column` | str, default "" |
| 12 | `DIE_ON_ERROR` | Yes | `die_on_error` | bool, default False (FIXED: was True) |
| 13 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | bool, default False |
| 14 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | str, default "," |
| 15 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | str, default "." |
| 16 | `TRIMALL` | Yes | `trimall` | bool, default False |
| 17 | `TRIMSELECT` | Yes | `trim_select` | TABLE, module-level `_parse_trim_select()` |
| 18 | `CONVERTDATETOSTRING` | Yes | `convertdatetostring` | bool, default False |
| 19 | `DATESELECT` | Yes | `date_select` | TABLE, module-level `_parse_date_select()` |
| 20 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" (FIXED: was UTF-8) |
| 21 | `READ_REAL_VALUE` | Yes | `read_real_value` | bool, default False |
| 22 | `STOPREAD_ON_EMPTYROW` | Yes | `stopread_on_emptyrow` | bool, default False |
| 23 | `NOVALIDATE_ON_CELL` | Yes | `novalidate_on_cell` | bool, default False |
| 24 | `SUPPRESS_WARN` | Yes | `suppress_warn` | bool, default False |
| 25 | `GENERATION_MODE` | Yes | `generation_mode` | str, default "USER_MODE" (FIXED: was EVENT_MODE) |
| 26 | `INCLUDE_PHONETICRUNS` | Yes | `include_phoneticruns` | bool, default True |
| 27 | `CONFIGURE_INFLATION_RATIO` | Yes | `configure_inflation_ratio` | bool, default False |
| 28 | `INFLATION_RATIO` | Yes | `inflation_ratio` | str, default "" |
| 29 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default False |
| 30 | `LABEL` | Yes | `label` | Framework param, str, default "" |

**Summary**: 30 of 30 parameters extracted (100%).

**Critical Fixes Applied:**

- `DIE_ON_ERROR`: Default changed from `True` to `False` per _java.xml
- `ENCODING`: Default changed from `"UTF-8"` to `"ISO-8859-15"` per _java.xml
- `GENERATION_MODE`: Default changed from `"EVENT_MODE"` to `"USER_MODE"` per _java.xml
- `AFFECT_EACH_SHEET`: Type changed from `bool` to `str` (TEXT type in _java.xml)

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Direct from column definition |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Boolean from column definition |
| `key` | Yes | Boolean from column definition |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not extracted by base class `_parse_schema()` |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are preserved as-is in string parameters (filepath, limit, affect_each_sheet). The v1 engine resolves these at runtime via `resolve_dict()`.

### 4.4 Converter Issues

None. All parameters correctly extracted with proper defaults.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `version_2007` | Engine auto-detects .xls vs .xlsx from file extension | engine_gap |
| 2 | `affect_each_sheet` | Engine does not apply header/footer per-sheet independently | engine_gap |
| 3 | `novalidate_on_cell` | Engine does not skip cell type validation | engine_gap |
| 4 | `generation_mode` | Engine does not switch between USER_MODE/EVENT_MODE/STREAM_MODE | engine_gap |
| 5 | `encoding` | Engine relies on openpyxl/xlrd internal encoding handling | engine_gap |
| 6 | `read_real_value` | Engine does not support reading underlying cell values | engine_gap |
| 7 | `include_phoneticruns` | Engine does not handle East Asian phonetic annotations | engine_gap |
| 8 | `configure_inflation_ratio` | Engine does not configure zip inflation ratio | engine_gap |
| 9 | `inflation_ratio` | Engine does not configure zip inflation ratio | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | .xls file reading | **Yes** | High | `_process_xls_file()` | Uses xlrd library |
| 2 | .xlsx file reading | **Yes** | High | `_process_xlsx_file()` | Uses openpyxl library |
| 3 | Auto format detection | **Yes** | High | `_detect_excel_format()` | Extension-based detection |
| 4 | Password protection | **Partial** | Low | `_process_xlsx_file()` | Only basic openpyxl password, no xlrd password |
| 5 | All sheets mode | **Yes** | High | `_get_sheet_names_*()` | Returns all sheet names |
| 6 | Sheet list with regex | **Yes** | High | `_get_sheet_names_*()` | `re.match()` for regex sheets |
| 7 | Header row skip | **Yes** | Medium | `_apply_row_limits()` | Engine defaults header=1 (Talend=0) |
| 8 | Footer row skip | **Yes** | High | `_apply_row_limits()` | Correct implementation |
| 9 | Row limit | **Yes** | High | `_apply_row_limits()` | Applies after header/footer |
| 10 | Column range | **Yes** | High | `_apply_row_limits()` | first_column/last_column support |
| 11 | Die on error | **Yes** | Medium | `_process()` | Engine defaults False (matches _java.xml) |
| 12 | Advanced separators | **Yes** | High | `_apply_advanced_separators()` | Thousands/decimal separator handling |
| 13 | Trim all | **Yes** | High | `_apply_trimming()` | Trims all string columns |
| 14 | Trim select | **Yes** | High | `_apply_trimming()` | Per-column trim from trim_select list |
| 15 | Date conversion | **Yes** | High | `_apply_date_conversion()` | Per-column date-to-string with patterns |
| 16 | Stop on empty row | **Yes** | High | `_apply_row_limits()` | Stops reading at first empty row |
| 17 | Schema type conversion | **Yes** | High | `_build_converters_dict()` | Schema-based column type enforcement |
| 18 | Streaming mode | **Yes** | Medium | Auto-detected | Based on file size, not GENERATION_MODE config |
| 19 | VERSION_2007 | **No** | N/A | -- | Engine auto-detects from extension |
| 20 | AFFECT_EACH_SHEET | **No** | N/A | -- | Engine applies limits globally, not per-sheet |
| 21 | NOVALIDATE_ON_CELL | **No** | N/A | -- | Not implemented |
| 22 | GENERATION_MODE | **No** | N/A | -- | Engine auto-selects batch/streaming |
| 23 | ENCODING | **No** | N/A | -- | Relies on library defaults |
| 24 | READ_REAL_VALUE | **No** | N/A | -- | Not implemented |
| 25 | INCLUDE_PHONETICRUNS | **No** | N/A | -- | Not implemented |
| 26 | INFLATE_RATIO | **No** | N/A | -- | Not implemented |
| 27 | REJECT flow | **No** | N/A | -- | No reject output |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FIE-001 | **P0** | No REJECT flow -- errored rows are silently dropped instead of routed to error handling path |
| ENG-FIE-002 | **P0** | Password decryption incomplete -- xlrd engine has no password support; openpyxl support is basic |
| ENG-FIE-003 | **P1** | `all_sheets` defaults to True in engine (line 429/513) but False in _java.xml -- behavioral mismatch |
| ENG-FIE-004 | **P1** | `header` defaults to 1 in engine (line 677/886) but 0 in _java.xml -- off-by-one in row skipping |
| ENG-FIE-005 | **P1** | No CURRENT_SHEET globalMap variable set during multi-sheet processing |
| ENG-FIE-006 | **P1** | GENERATION_MODE ignored -- engine auto-selects batch/streaming based on file size instead of user configuration |
| ENG-FIE-007 | **P2** | 9 config keys extracted by converter but never read by engine (see needs_review) |
| ENG-FIE-008 | **P2** | Suppress_warn config read but only used for file-not-found scenario, not for general warnings |
| ENG-FIE-009 | **P2** | Encoding not applied -- engine relies on library defaults rather than user-specified encoding |
| ENG-FIE-010 | **P3** | Streaming threshold is hardcoded, not configurable |
| ENG-FIE-011 | **P3** | No East Asian phonetic run support |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Set after execution |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Equal to NB_LINE |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 (no REJECT flow) |
| `{id}_CURRENT_SHEET` | Yes | No | -- | Not implemented |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FIE-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crash when globalMap is set |
| BUG-FIE-002 | **P0** | `base_component.py:174` | CROSS-CUTTING: `replace_in_config` literal `[i]` replacement breaks list indexing |
| BUG-FIE-003 | **P1** | `file_input_excel.py:429,513` | `all_sheets` default True contradicts _java.xml default False |
| BUG-FIE-004 | **P1** | `file_input_excel.py:677,886` | `header` default 1 contradicts _java.xml default 0 |
| BUG-FIE-005 | **P1** | `file_input_excel.py:232-298` | `_build_converters_dict()` duplicated converter factory logic (~65 lines) |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FIE-001 | **P2** | Method `_detect_excel_format()` returns engine name string, not format enum |
| NAME-FIE-002 | **P2** | `_process_xls_file` and `_process_xlsx_file` share near-identical signatures but different internal logic |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FIE-001 | **P2** | "No dead code" | Three methods that duplicate logic across xls/xlsx paths |
| STD-FIE-002 | **P3** | "DRY principle" | `_apply_row_limits()` logic duplicated in xls and xlsx processing paths |
| STD-FIE-003 | **P3** | "Config validation" | `_validate_config()` defined but never called by `_process()` |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Password values may be logged at DEBUG level. See Section 11 for comprehensive security assessment.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | Good -- info for status, error for failures, debug for details |
| Sensitive data | Risk -- password may appear in debug logs |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- uses FileOperationError, ConfigurationError, ComponentExecutionError |
| Exception chaining | Good -- `raise ... from e` pattern used |
| die_on_error handling | Good -- respects config, returns empty DataFrame when False |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods have return type hints |
| Parameter types | Good -- uses Optional, Dict, List appropriately |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FIE-001 | **P1** | USER_MODE (DOM) loads entire workbook into memory -- no upper bound on file size |
| PERF-FIE-002 | **P2** | `_build_converters_dict()` creates closure per column per call -- minor overhead |
| PERF-FIE-003 | **P3** | Sheet name iteration creates intermediate list even when single sheet requested |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Implemented -- auto-detects based on file size threshold |
| Memory threshold | Hardcoded -- not configurable by user (ignores GENERATION_MODE) |
| Large data handling | Risk -- no upper bound in batch mode; 100MB+ Excel files can exhaust memory |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 83 | `tests/converters/talend_to_v1/components/test_file_input_excel.py` |
| Engine unit tests | 0 | None |
| Integration tests | 399 (shared) | `tests/converters/talend_to_v1/test_integration.py` |
| Output structure tests | Covered | `tests/converters/talend_to_v1/test_converter_output_structure.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FIE-001 | **P1** | Zero engine unit tests -- FileInputExcel is the largest engine component (1022 lines) with no tests |

### 8.3 Recommended Test Cases

1. **Happy path**: Read .xlsx file with schema, verify DataFrame output
2. **Multi-sheet**: ALL_SHEETS=true, sheetlist with regex, verify all sheets read
3. **Password protected**: Read password-protected .xlsx, verify data or error
4. **Header/footer**: Various header/footer combinations, verify row counts
5. **Column range**: first_column/last_column limits, verify column subset
6. **Advanced separators**: European number formats (1.000,50)
7. **Date conversion**: CONVERTDATETOSTRING with custom patterns
8. **Trim select**: Per-column trimming, verify whitespace removed
9. **Stop on empty row**: Verify reading stops at first empty row
10. **Error handling**: die_on_error true/false with missing file
11. **Large file**: Streaming mode activation and memory behavior

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | BUG-FIE-001, BUG-FIE-002 |
| P1 | 5 | BUG-FIE-003, BUG-FIE-004, BUG-FIE-005, ENG-FIE-003, ENG-FIE-004, ENG-FIE-005, ENG-FIE-006, PERF-FIE-001, TEST-FIE-001 |
| P2 | 5 | NAME-FIE-001, NAME-FIE-002, STD-FIE-001, ENG-FIE-007, ENG-FIE-008, ENG-FIE-009, PERF-FIE-002 |
| P3 | 3 | STD-FIE-002, STD-FIE-003, ENG-FIE-010, ENG-FIE-011, PERF-FIE-003 |
| **Total** | **15** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 9 | ENG-FIE-001 through ENG-FIE-011 |
| Bug (BUG) | 5 | BUG-FIE-001 through BUG-FIE-005 |
| Naming (NAME) | 2 | NAME-FIE-001, NAME-FIE-002 |
| Standards (STD) | 3 | STD-FIE-001 through STD-FIE-003 |
| Performance (PERF) | 3 | PERF-FIE-001 through PERF-FIE-003 |
| Testing (TEST) | 1 | TEST-FIE-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set -- stats lost |
| XCUT-002 | `base_component.py:174` | `replace_in_config` literal `[i]` -- breaks list iteration configs |

---

## 10. Recommendations

### Immediate (Before Production)

- Fix cross-cutting `_update_global_map()` crash (XCUT-001) -- affects all 54 components
- Fix cross-cutting `replace_in_config` literal `[i]` (XCUT-002) -- affects config resolution

### Short-term (Hardening)

- Fix `all_sheets` default from True to False in engine (BUG-FIE-003)
- Fix `header` default from 1 to 0 in engine (BUG-FIE-004)
- Implement CURRENT_SHEET globalMap variable (ENG-FIE-005)
- Add engine unit tests for FileInputExcel (TEST-FIE-001)
- Implement REJECT flow for error handling (ENG-FIE-001)

### Long-term (Optimization)

- Implement full password support for .xls files
- Honor GENERATION_MODE config instead of auto-detecting
- Remove duplicated code between xls/xlsx processing paths
- Make streaming threshold configurable

---

## 11. Risk Assessment

This section is included because tFileInputExcel handles Excel files which are ZIP-based XML archives, supports password-protected workbooks, processes potentially untrusted file content, and is the largest engine component at 1022 lines.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| ZIP bomb via crafted .xlsx | Medium | High -- memory exhaustion / DoS; .xlsx files are ZIP archives containing XML | Engine does not implement CONFIGURE_INFLATION_RATIO; use system-level file size limits; monitor memory |
| XML External Entity (XXE) in .xlsx | Low | High -- .xlsx contains XML files that could reference external entities | openpyxl has built-in XXE protection; verify library version is current |
| Formula injection via cell values | Medium | Medium -- Excel cells may contain formulas that execute when opened downstream | Engine reads cell values not formulas by default; READ_REAL_VALUE=false is safe default |
| Password exposure in logs/config | High | Medium -- passwords stored plain text in job config and may appear in DEBUG logs | Use secret manager; disable DEBUG logging in production; never log password values |
| VBA macro execution | Low | High -- .xlsm files may contain VBA macros; Talend reads data only but misidentified files could trigger execution in downstream tools | Engine uses openpyxl/xlrd which do not execute macros; warn if .xlsm detected |
| Memory exhaustion with large files | Medium | High -- USER_MODE loads entire workbook into memory; no configurable upper bound | Implement file size check; honor GENERATION_MODE for streaming; set memory limits |
| Path traversal in FILENAME | Low | High -- attacker-controlled filepath could read arbitrary files | Validate filepath against allowed directories; reject paths with `..` components |
| Encoding mismatch data corruption | Medium | Low -- engine ignores ENCODING config; library defaults may not match source data | Document encoding behavior; honor ENCODING config in engine |

### High-Risk Job Patterns

1. **Large .xlsx files (100MB+) in USER_MODE** -- Engine loads entire workbook into memory regardless of GENERATION_MODE setting. Can exhaust available memory with no warning.
2. **Password-protected .xls files** -- xlrd engine has no password decryption support. Job will fail silently or produce empty results.
3. **Multi-sheet with AFFECT_EACH_SHEET** -- Engine applies header/footer/limit globally, not per-sheet. Results will have incorrect row counts when sheets have different layouts.
4. **Jobs relying on GENERATION_MODE=EVENT_MODE** -- Engine ignores this setting and auto-selects batch/streaming based on file size. Event-mode-specific features (phonetic runs, streaming SAX parsing) are not available.
5. **Untrusted .xlsx files without inflation ratio** -- ZIP bomb protection (CONFIGURE_INFLATION_RATIO) is not implemented in engine. Crafted .xlsx files could cause memory exhaustion.

### Safe Usage Patterns

1. **Standard .xlsx files under 50MB** -- Core read functionality works reliably with openpyxl.
2. **Single sheet or ALL_SHEETS=true without per-sheet limits** -- Sheet selection and all-sheets mode work correctly.
3. **Schema-typed columns** -- Type conversion via `_build_converters_dict()` works well with schema-defined columns.
4. **DIE_ON_ERROR=true for production jobs** -- Error handling correctly raises exceptions when enabled.
5. **Simple trim (TRIMALL=true)** -- Full-column trimming works correctly.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputExcel/tFileInputExcel_java.xml`> | Parameter definitions, defaults, CLOSED_LIST values |
| Engine source | `src/v1/engine/components/file/file_input_excel.py` (1022 lines) | Feature parity analysis, bug identification, security assessment |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_excel.py` (263 lines) | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_excel.py` (83 tests) | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting issue identification |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set -- stats lost |
| XCUT-002 | `base_component.py:174` | `replace_in_config` literal `[i]` -- breaks list-indexed config resolution |
| XCUT-003 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- non-reentrant in iterate loops |

### Edge-Case Checklist Results

| Check | Result | Notes |
| ------- | -------- | ------- |
| NaN handling | Risk | `_build_converters_dict()` handles NaN per type but edge cases possible |
| Empty strings in config | OK | Empty filepath produces warning, returns empty DataFrame |
| Empty DataFrame input | N/A | Source component -- no input data |
| HYBRID streaming mode | Risk | Auto-detected streaming may chunk data; stateful post-processing safe |
| `_update_global_map()` crash | Impact | Stats lost if globalMap is set |
| Type demotion | Risk | iterrows/Series reconstruction may demote Decimal to float64 |
| `validate_schema` nullable | N/A | Source component generates data, does not validate input |
| `_validate_config()` called | Dead code | Defined but not called by `_process()` |

## Appendix C: Generation Mode Comparison

### USER_MODE (Default)

- **Strategy**: DOM-based. Loads entire workbook into memory via openpyxl/xlrd.
- **Memory**: High -- O(file_size) memory usage.
- **Features**: Full feature support (formulas, formatting, merged cells).
- **Performance**: Fast for small files; problematic for 100MB+.
- **Engine behavior**: Engine always uses this approach regardless of config.

### EVENT_MODE

- **Strategy**: SAX-based streaming. Processes XML events one-at-a-time.
- **Memory**: Low -- O(row_size) memory usage.
- **Features**: Reduced -- no formula evaluation, no merged cell support, phonetic runs optional.
- **Performance**: Suitable for very large files.
- **Engine behavior**: Not implemented. Config value captured but ignored.

### STREAM_MODE

- **Strategy**: Apache POI streaming (SXSSF) for .xlsx files.
- **Memory**: Configurable window size.
- **Features**: Similar to USER_MODE but with windowed access.
- **Performance**: Good balance of features and memory.
- **Engine behavior**: Not implemented. Engine auto-detects batch/streaming based on file size threshold.

## Appendix D: Sheet Processing Behavior

### Sheet Selection Logic

1. If `ALL_SHEETS=true`: Read all sheets in workbook order.
2. If `ALL_SHEETS=false` and `SHEETLIST` non-empty: Read sheets matching SHEETLIST entries.
3. If `ALL_SHEETS=false` and `SHEETLIST` empty: Read only the first sheet.

### SHEETLIST Matching

Each SHEETLIST entry has:

- `sheetname`: The sheet name or regex pattern
- `use_regex`: When true, `sheetname` is treated as a regex pattern matched against all sheet names

**Engine implementation**: Uses `re.match()` for regex sheets (matches from start of string). Non-regex entries use exact string match. Sheets are processed in the order they appear in the workbook, not in SHEETLIST order.

### Multi-Sheet Output

All matching sheets are concatenated into a single DataFrame output. There is no per-sheet output separation in the v1 engine. The `CURRENT_SHEET` globalMap variable (which Talend sets during iteration) is not implemented.

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after Phase 9 gold-standard rewrite*
