# Audit Report: tFileOutputExcel / FileOutputExcel

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileOutputExcel` |
| **V1 Engine Class** | `FileOutputExcel` |
| **Engine File** | `src/v1/engine/components/file/file_output_excel.py` (382 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_output_excel.py` (249 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileOutputExcel")` decorator-based dispatch |
| **Registry Aliases** | `FileOutputExcel`, `tFileOutputExcel` (registered in `src/v1/engine/engine.py`) |
| **Category** | File / Output |
| **Complexity** | Medium-high -- sink component with 29 unique parameters, AUTO_SZIE_SETTING TABLE parsing, openpyxl workbook management, append mode, header detection, empty-row filtering |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_output_excel.py` | Engine implementation (382 lines) |
| `src/converters/talend_to_v1/components/file/file_output_excel.py` | Converter class (249 lines) |
| `tests/converters/talend_to_v1/components/test_file_output_excel.py` | Converter tests (66 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 29 unique params + 2 framework extracted; AUTO_SZIE_SETTING TABLE parser; `_build_component_dict` pattern; sink schema (input populated, output empty); 16 per-feature needs_review entries; 66 converter tests |
| Engine Feature Parity | **Y** | 0 | 5 | 5 | 2 | No .xls support (always xlsx); no cell positioning; no auto-size; no password protection; no font selection; NaN leaks to cells; no streaming write mode |
| Code Quality | **Y** | 3 | 4 | 6 | 0 | Cross-cutting `_update_global_map()` crash (P0); NaN/empty-row filtering with string-cast; `_validate_config()` never called; workbook handle leak; f-string logging |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | Row-by-row `sheet.append()` for all rows; entire workbook in memory; no streaming write support (SXSSF equivalent) |
| Testing | **Y** | 0 | 0 | 1 | 0 | 66 converter unit tests across 11 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2 per D-52) |

**Overall: Yellow -- Converter fully standardized (Green); engine functional for basic xlsx write but missing many Talend features; code quality has cross-cutting P0 bugs; testing Yellow per D-52 (no engine unit tests)**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Add cell positioning support (FIRST_CELL_X/Y) in engine (P1)
3. Add workbook password protection in engine (P1)
4. Add column auto-sizing in engine (P1)
5. Add engine unit tests for FileOutputExcel (P2)

---

## 3. Talend Feature Baseline

### What tFileOutputExcel Does

`tFileOutputExcel` writes data from a Talend data flow to an Excel file (.xls or .xlsx). It is a sink component in the File family that receives input rows and writes them to a specified worksheet. The component supports both legacy Excel 97-2003 (.xls) format and the modern Excel 2007+ (.xlsx) format via the VERSION_2007 parameter.

The component offers extensive formatting controls including font selection, cell positioning (starting row/column offset), column auto-sizing, header inclusion, and locale-aware number formatting (custom thousands/decimal separators). It also supports append modes for both files and sheets, workbook password protection, streaming write mode (SXSSF) for large datasets, formula recalculation, and encoding selection.

**Notable Talend quirks:**

- `IS_ALL_AUTO_SZIE` and `AUTO_SZIE_SETTING` have a typo: "SZIE" instead of "SIZE". This is the canonical _java.xml spelling and is preserved in config keys.
- `KEEP_CELL_FORMATING` has a single "T" (not "FORMATTING"). This is the canonical spelling.
- Default encoding is `ISO-8859-15` (not UTF-8), consistent with other Talend file components.
- Default font is `NONE` (not Arial as commonly assumed).
- Default flush row count is `100` (not 1000).

**Source**: [Talend 7.3 tFileOutputExcel docs](https://help.qlik.com/talend/en-US/components/7.3/tfileoutputexcel/tfileoutputexcel-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputExcel/tFileOutputExcel_java.xml)
**Component family**: File / Output
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in, uses Apache POI internally in Talend)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Version 2007 | `VERSION_2007` | CHECK | `false` | Use .xlsx format (Excel 2007+) instead of .xls. |
| 2 | Use stream | `USESTREAM` | CHECK | `false` | Write to an OutputStream instead of a file path. When true, STREAMNAME is used instead of FILENAME. |
| 3 | Stream name | `STREAMNAME` | TEXT | `"outputStream"` | Name of the OutputStream variable to write to. Only active when USESTREAM=true. |
| 4 | File name | `FILENAME` | FILE | `""` | Path to the output Excel file. |
| 5 | Sheet name | `SHEETNAME` | TEXT | `"Sheet1"` | Name of the worksheet to write data to. |
| 6 | Include header | `INCLUDEHEADER` | CHECK | `false` | Write column names as the first row. |
| 7 | Append to file | `APPEND_FILE` | CHECK | `false` | Open existing file and append data instead of overwriting. |
| 8 | Append to sheet | `APPEND_SHEET` | CHECK | `false` | Append rows to existing sheet data instead of overwriting the sheet. |
| 9 | Absolute Y position | `FIRST_CELL_Y_ABSOLUTE` | CHECK | `false` | Use absolute row position for first cell instead of relative. |
| 10 | First cell X | `FIRST_CELL_X` | TEXT | `"0"` | Column offset (0-based) for the starting write position. |
| 11 | First cell Y | `FIRST_CELL_Y` | TEXT | `"0"` | Row offset (0-based) for the starting write position. |
| 12 | Keep cell formatting | `KEEP_CELL_FORMATING` | CHECK | `false` | Preserve existing cell formatting when writing data. Note: Talend spelling has single "T". |
| 13 | Font | `FONT` | CLOSED_LIST | `"NONE"` | Font face for written cells. Options include NONE, Arial, Courier, Times, etc. Default is NONE (no font override). |
| 14 | Auto-size all columns | `IS_ALL_AUTO_SZIE` | CHECK | `false` | Automatically resize all columns to fit content. Note: Talend typo "SZIE" instead of "SIZE". |
| 15 | Auto-size settings | `AUTO_SZIE_SETTING` | TABLE | `[]` | Per-column auto-size configuration. TABLE with SCHEMA_COLUMN entries. Only active when IS_ALL_AUTO_SZIE=false. Note: Talend typo preserved. |
| 16 | Protect file | `PROTECT_FILE` | CHECK | `false` | Apply password protection to the workbook. |
| 17 | Password | `PASSWORD` | PASSWORD | `""` | Password for workbook protection. Only active when PROTECT_FILE=true. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 18 | Create directory | `CREATE` | CHECK | `true` | Create output directory if it does not exist. |
| 19 | Flush on row | `FLUSHONROW` | CHECK | `false` | Enable periodic flushing of rows to disk during write. |
| 20 | Flush row count | `FLUSHONROW_NUM` | TEXT | `"100"` | Number of rows to accumulate before flushing. Only active when FLUSHONROW=true. |
| 21 | Advanced separator | `ADVANCED_SEPARATOR` | CHECK | `false` | Enable locale-aware number formatting for output. |
| 22 | Thousands separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Character for thousands grouping. Only active when ADVANCED_SEPARATOR=true. |
| 23 | Decimal separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Character for decimal point. Only active when ADVANCED_SEPARATOR=true. |
| 24 | Truncate exceeding characters | `TRUNCATE_EXCEEDING_CHARACTERS` | CHECK | `false` | Truncate cell content exceeding the 32,767 character Excel cell limit. |
| 25 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for the output file. Default is ISO-8859-15 (not UTF-8). |
| 26 | Delete empty file | `DELETE_EMPTYFILE` | CHECK | `false` | Delete the output file if no data rows were written. |
| 27 | Recalculate formula | `RECALCULATE_FORMULA` | CHECK | `false` | Force formula recalculation when saving the workbook. |
| 28 | Streaming append | `STREAMING_APPEND` | CHECK | `false` | Use SXSSF streaming write mode for large datasets. Reduces memory usage. |
| 29 | Use shared strings table | `USE_SHARED_STRINGS_TABLE` | CHECK | `false` | Enable shared strings table optimization for xlsx files. Reduces file size for repeated strings. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Primary data input to write to Excel |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully written |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected/skipped |

### 3.5 Behavioral Notes

1. **Encoding default is ISO-8859-15**, not UTF-8. This is consistent across all Talend file components but is a common source of confusion.
2. **Font default is NONE**, not Arial. NONE means no font override is applied to written cells.
3. **Flush row count default is 100**, not 1000. This controls how frequently rows are flushed to disk when FLUSHONROW is enabled.
4. **IS_ALL_AUTO_SZIE** and **AUTO_SZIE_SETTING** contain Talend typos ("SZIE" instead of "SIZE"). These are the canonical _java.xml parameter names.
5. **KEEP_CELL_FORMATING** has a single "T" -- this is the canonical Talend spelling, not a converter bug.
6. **USESTREAM/STREAMNAME** enable OutputStream-based writing instead of file-based. This is used in advanced scenarios where the output target is a Java stream rather than a filesystem path.
7. **VERSION_2007=false** selects the legacy .xls format. The engine only supports .xlsx (openpyxl), so jobs with VERSION_2007=false will produce .xlsx regardless.
8. **CREATE=true** (default) means the output directory is automatically created if missing. This is an advanced setting.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter (`FileOutputExcelConverter`) uses `@REGISTRY.register("tFileOutputExcel")` for dispatch. It extracts all 29 unique parameters plus 2 framework parameters using `_get_str()`, `_get_bool()`, and direct `params.get()` for the TABLE parameter. It uses `_build_component_dict()` for the wrapper structure with sink schema pattern (input populated from `_parse_schema(node)`, output empty).

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `VERSION_2007` | Yes | `version_2007` | bool, default False |
| 2 | `USESTREAM` | Yes | `usestream` | bool, default False |
| 3 | `STREAMNAME` | Yes | `streamname` | str, default "outputStream" |
| 4 | `FILENAME` | Yes | `filename` | str, default "" |
| 5 | `SHEETNAME` | Yes | `sheetname` | str, default "Sheet1" |
| 6 | `INCLUDEHEADER` | Yes | `includeheader` | bool, default False |
| 7 | `APPEND_FILE` | Yes | `append_file` | bool, default False |
| 8 | `APPEND_SHEET` | Yes | `append_sheet` | bool, default False |
| 9 | `FIRST_CELL_Y_ABSOLUTE` | Yes | `first_cell_y_absolute` | bool, default False |
| 10 | `FIRST_CELL_X` | Yes | `first_cell_x` | str, default "0" |
| 11 | `FIRST_CELL_Y` | Yes | `first_cell_y` | str, default "0" |
| 12 | `KEEP_CELL_FORMATING` | Yes | `keep_cell_formating` | bool, default False; Talend spelling preserved |
| 13 | `FONT` | Yes | `font` | str, default "NONE" (was incorrectly Arial) |
| 14 | `IS_ALL_AUTO_SZIE` | Yes | `is_all_auto_szie` | bool, default False; Talend typo preserved |
| 15 | `AUTO_SZIE_SETTING` | Yes | `auto_szie_setting` | TABLE -> list of str; Talend typo preserved |
| 16 | `PROTECT_FILE` | Yes | `protect_file` | bool, default False |
| 17 | `PASSWORD` | Yes | `password` | str, default "" |
| 18 | `CREATE` | Yes | `create` | bool, default True (advanced) |
| 19 | `FLUSHONROW` | Yes | `flushonrow` | bool, default False (advanced) |
| 20 | `FLUSHONROW_NUM` | Yes | `flushonrow_num` | str, default "100" (was incorrectly 1000) |
| 21 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | bool, default False (advanced) |
| 22 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | str, default "," (advanced) |
| 23 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | str, default "." (advanced) |
| 24 | `TRUNCATE_EXCEEDING_CHARACTERS` | Yes | `truncate_exceeding_characters` | bool, default False (advanced) |
| 25 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" (was incorrectly UTF-8) |
| 26 | `DELETE_EMPTYFILE` | Yes | `delete_empty_file` | bool, default False (advanced) |
| 27 | `RECALCULATE_FORMULA` | Yes | `recalculate_formula` | bool, default False (advanced) |
| 28 | `STREAMING_APPEND` | Yes | `streaming_append` | bool, default False (advanced) |
| 29 | `USE_SHARED_STRINGS_TABLE` | Yes | `use_shared_strings_table` | bool, default False (advanced) |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default False |
| F2 | `LABEL` | Yes | `label` | Framework param, str, default "" |

**Summary**: 29 of 29 unique parameters extracted (100%), plus 2 framework parameters. All defaults verified against _java.xml source of truth.

### 4.2 Schema Extraction

Sink component schema pattern (D-55): input populated from FLOW connector, output empty.

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | From SchemaColumn.name |
| `type` | Yes | Converted via `convert_type()` from Talend type |
| `nullable` | Yes | From SchemaColumn.nullable |
| `key` | Yes | From SchemaColumn.key |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are passed through as-is in string parameters (FILENAME, SHEETNAME, STREAMNAME, FIRST_CELL_X, FIRST_CELL_Y, FLUSHONROW_NUM, PASSWORD, THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR). The engine resolves these at runtime via `replace_in_config()`.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-FOE-001 | ~~P1~~ | **FIXED** -- FONT default was "Arial", corrected to "NONE" per _java.xml |
| CONV-FOE-002 | ~~P1~~ | **FIXED** -- FLUSHONROW_NUM default was 1000, corrected to "100" per _java.xml |
| CONV-FOE-003 | ~~P1~~ | **FIXED** -- ENCODING default was "UTF-8", corrected to "ISO-8859-15" per _java.xml |
| CONV-FOE-004 | ~~P1~~ | **FIXED** -- Phantom AUTO_SIZE_SETTING removed, replaced with IS_ALL_AUTO_SZIE (bool) + AUTO_SZIE_SETTING (TABLE) per _java.xml |
| CONV-FOE-005 | ~~P1~~ | **FIXED** -- USESTREAM/STREAMNAME were missing, now extracted |
| CONV-FOE-006 | ~~P2~~ | **FIXED** -- Phantom CUSTOM_FLUSH_BUFFER removed (not in _java.xml), replaced with FLUSHONROW |
| CONV-FOE-007 | ~~P2~~ | **FIXED** -- Phantom DIE_ON_ERROR removed (not in _java.xml) |
| CONV-FOE-008 | ~~P2~~ | **FIXED** -- Config key "create_directory" renamed to "create" per _java.xml param name CREATE |
| CONV-FOE-009 | ~~P2~~ | **FIXED** -- Config key "keep_cell_formatting" renamed to "keep_cell_formating" per Talend spelling |
| CONV-FOE-010 | ~~P2~~ | **FIXED** -- FIRST_CELL_X/Y changed from int to str (TEXT type supports expressions) |
| CONV-FOE-011 | ~~P2~~ | **FIXED** -- Used warnings instead of needs_review for engine gaps; now uses per-feature needs_review per D-24 |
| CONV-FOE-012 | ~~P2~~ | **FIXED** -- Now uses `_build_component_dict` wrapper pattern per D-40 |

### 4.5 Needs Review Entries

The converter emits 16 per-feature needs_review entries for engine gaps:

| # | Config Key(s) | Reason | Severity |
| --- | -------------- | -------- | ---------- |
| 1 | `encoding` | Engine default is 'UTF-8' but _java.xml default is 'ISO-8859-15' | engine_gap |
| 2 | `usestream`, `streamname` | Engine does not read these keys -- OutputStream mode not supported | engine_gap |
| 3 | `font` | Engine does not read this key -- font selection not supported | engine_gap |
| 4 | `is_all_auto_szie`, `auto_szie_setting` | Engine does not read these keys -- column auto-sizing not supported | engine_gap |
| 5 | `protect_file`, `password` | Engine does not read these keys -- workbook protection not supported | engine_gap |
| 6 | `first_cell_y_absolute`, `first_cell_x`, `first_cell_y` | Engine does not read these keys -- cell offset positioning not supported | engine_gap |
| 7 | `keep_cell_formating` | Engine does not read this key -- existing cell formatting not preserved | engine_gap |
| 8 | `advanced_separator`, `thousands_separator`, `decimal_separator` | Engine does not read these keys -- locale number formatting not supported | engine_gap |
| 9 | `truncate_exceeding_characters` | Engine does not read this key -- cell content truncation not supported | engine_gap |
| 10 | `delete_empty_file` | Engine does not read this key -- empty file cleanup not supported | engine_gap |
| 11 | `recalculate_formula` | Engine does not read this key -- formula recalculation not supported | engine_gap |
| 12 | `flushonrow`, `flushonrow_num` | Engine does not read these keys -- row flush buffer control not supported | engine_gap |
| 13 | `streaming_append` | Engine does not read this key -- SXSSF streaming write mode not supported | engine_gap |
| 14 | `use_shared_strings_table` | Engine does not read this key -- shared strings optimization not supported | engine_gap |
| 15 | `version_2007` | Engine does not read this key -- always writes .xlsx via openpyxl | engine_gap |
| 16 | `die_on_error` | Engine reads this key (default True) but param not in _java.xml -- engine-only config key | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Write to xlsx file | **Yes** | High | `_process()` line 96-367 | Uses openpyxl; always writes .xlsx format |
| 2 | Sheet name | **Yes** | High | `_process()` line 126 | Config key `sheetname`, default "Sheet1" |
| 3 | Include header | **Yes** | High | `_process()` lines 277-325 | Includes append-mode header detection |
| 4 | Append to file | **Yes** | Medium | `_process()` lines 157-174 | Loads existing workbook; no .xls append |
| 5 | Create directory | **Yes** | High | `_process()` lines 141-153 | Config key `create`, default True |
| 6 | Die on error | **Yes** | High | `_process()` throughout | Engine-only param, not in _java.xml |
| 7 | Write to xls format | **No** | N/A | -- | Always uses openpyxl (.xlsx only) |
| 8 | Cell positioning | **No** | N/A | -- | FIRST_CELL_X/Y/ABSOLUTE not read |
| 9 | Font selection | **No** | N/A | -- | FONT config not read |
| 10 | Auto-size columns | **No** | N/A | -- | IS_ALL_AUTO_SZIE/AUTO_SZIE_SETTING not read |
| 11 | Password protection | **No** | N/A | -- | PROTECT_FILE/PASSWORD not read |
| 12 | Flush buffer control | **No** | N/A | -- | FLUSHONROW/FLUSHONROW_NUM not read |
| 13 | Streaming write (SXSSF) | **No** | N/A | -- | STREAMING_APPEND not read |
| 14 | OutputStream mode | **No** | N/A | -- | USESTREAM/STREAMNAME not read |
| 15 | Locale number formatting | **No** | N/A | -- | ADVANCED_SEPARATOR and separators not read |
| 16 | Cell content truncation | **No** | N/A | -- | TRUNCATE_EXCEEDING_CHARACTERS not read |
| 17 | Delete empty file | **No** | N/A | -- | DELETE_EMPTYFILE not read |
| 18 | Formula recalculation | **No** | N/A | -- | RECALCULATE_FORMULA not read |
| 19 | Shared strings table | **No** | N/A | -- | USE_SHARED_STRINGS_TABLE not read |
| 20 | Keep cell formatting | **No** | N/A | -- | KEEP_CELL_FORMATING not read |
| 21 | Append to sheet | **Partial** | Low | `_process()` line 178 | Creates/selects sheet but no append-to-existing-data logic |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FOE-001 | **P1** | Cell positioning (FIRST_CELL_X/Y) not supported -- data always starts at A1 |
| ENG-FOE-002 | **P1** | Password protection not available -- PROTECT_FILE/PASSWORD ignored |
| ENG-FOE-003 | **P1** | Column auto-sizing not supported -- IS_ALL_AUTO_SZIE/AUTO_SZIE_SETTING ignored |
| ENG-FOE-004 | **P1** | Font selection not supported -- FONT config key ignored |
| ENG-FOE-005 | **P1** | No .xls format support -- VERSION_2007=false still produces .xlsx |
| ENG-FOE-006 | **P2** | Locale number formatting not supported -- ADVANCED_SEPARATOR and separators ignored |
| ENG-FOE-007 | **P2** | Cell content truncation not supported -- TRUNCATE_EXCEEDING_CHARACTERS ignored, may produce invalid cells |
| ENG-FOE-008 | **P2** | Delete empty file not supported -- empty files persist even with DELETE_EMPTYFILE=true |
| ENG-FOE-009 | **P2** | Formula recalculation not triggered -- RECALCULATE_FORMULA ignored |
| ENG-FOE-010 | **P2** | Streaming write mode not supported -- large files may cause memory exhaustion |
| ENG-FOE-011 | **P3** | Shared strings table optimization not supported |
| ENG-FOE-012 | **P3** | Keep cell formatting not supported -- existing formatting overwritten |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats(rows_in, ...)` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats(..., rows_out, ...)` | Rows written |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats(..., ..., rows_rejected)` | Rows filtered (empty rows) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FOE-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` crashes with `TypeError` when `global_map` is set -- `GlobalMap.set()` signature mismatch |
| BUG-FOE-002 | **P0** | `base_component.py:174` | **CROSS-CUTTING**: `replace_in_config` uses literal `[i]` string instead of f-string -- Java expression resolution fails for list elements |
| BUG-FOE-003 | **P0** | `base_component.py:132` | **CROSS-CUTTING**: `validate_schema` inverted nullable logic -- `nullable=True` triggers `fillna(0)` which destroys intentional nulls |
| BUG-FOE-004 | **P1** | `file_output_excel.py:262-269` | NaN detection via `str(value).strip().lower() != 'nan'` casts all values to string -- potential data loss for numeric 0 values that become "0" and survive, while legitimate "nan" strings are filtered |
| BUG-FOE-005 | **P1** | `file_output_excel.py:157-174` | Workbook handle leak -- if exception thrown between `openpyxl.load_workbook()` and `workbook.save()`, file handle is never closed (no context manager) |
| BUG-FOE-006 | **P1** | `file_output_excel.py:232-243` | Empty value substitution uses empty string `''` for missing schema columns -- should be `None` to preserve type integrity |
| BUG-FOE-007 | **P1** | `file_output_excel.py:276-321` | Header detection in append mode uses complex heuristic that can fail for non-string header columns or Unicode sheet names |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FOE-001 | **P2** | Engine reads `encoding` (default `UTF-8`) but _java.xml default is `ISO-8859-15` -- default mismatch between converter output and engine expectation |
| NAME-FOE-002 | **P2** | Engine reads `die_on_error` but this param does not exist in _java.xml -- engine-only config key |
| NAME-FOE-003 | **P2** | `create_file` local variable (line 135) doesn't match config key `create` -- naming inconsistency |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FOE-001 | **P2** | "No f-string logging" | Uses f-string interpolation in all log calls instead of `logger.info("msg %s", var)` |
| STD-FOE-002 | **P2** | "_validate_config() must be called" | `_validate_config()` is defined (lines 63-93) but never called from `_process()` |
| STD-FOE-003 | **P2** | "Use context manager for file handles" | Workbook opened without `with` statement or try/finally close |

### 6.4 Debug Artifacts

None found. No print statements, no commented-out code, no TODO/FIXME comments.

### 6.5 Security

- **Password in config**: The `password` config key stores the workbook protection password in plaintext. If job configs are logged or stored, the password is exposed.
- **Path traversal**: The `filename` parameter accepts arbitrary paths. No validation that the path is within an allowed directory.
- **Formula injection**: Cell content from input data could contain Excel formula injections (e.g., `=CMD(...)`) -- no sanitization.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logging.getLogger(__name__)` at module level |
| Level usage | Good -- info for operations, warning for missing data, error for failures, debug for details |
| Sensitive data | Concern -- filename paths logged at INFO level; passwords not logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- uses `FileOperationError`, `ComponentExecutionError` |
| Exception chaining | Good -- `raise ... from e` pattern used throughout |
| die_on_error handling | Good -- respects config flag, graceful degradation when False |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `_process()` has proper type hints |
| Parameter types | Mixed -- `Union[Dict[str, Any], pd.DataFrame, None]` is broad but correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FOE-001 | **P1** | Row-by-row `sheet.append()` (line 338) for all rows -- no batch write optimization. For large datasets, this is significantly slower than `pd.DataFrame.to_excel()` |
| PERF-FOE-002 | **P2** | Entire workbook loaded into memory for append mode (line 158). Large .xlsx files (100K+ rows) can cause `MemoryError` |
| PERF-FOE-003 | **P3** | `iterrows()` (line 234) creates a Series per row -- known pandas anti-pattern for large DataFrames |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not supported -- no SXSSF equivalent in engine. All data buffered in memory. |
| Memory threshold | No limit -- entire workbook + all input data in memory simultaneously |
| Large data handling | Poor -- 100K+ rows will be slow (iterrows) and memory-intensive (full workbook in memory) |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 66 | `tests/converters/talend_to_v1/components/test_file_output_excel.py` |
| Engine unit tests | 0 | None |
| Integration tests | 399 | `tests/converters/talend_to_v1/test_integration.py` + `test_converter_output_structure.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FOE-001 | **P2** | No engine unit tests for FileOutputExcel -- basic xlsx write, append mode, header handling untested at engine level |

### 8.3 Recommended Test Cases

1. **Engine: Basic xlsx write** -- verify file created with correct data
2. **Engine: Append mode** -- verify rows appended to existing file
3. **Engine: Header inclusion** -- verify header row written when includeheader=true
4. **Engine: Empty input** -- verify empty file handling
5. **Engine: Create directory** -- verify directory auto-creation
6. **Engine: die_on_error=false** -- verify graceful error handling
7. **Engine: Large dataset** -- verify memory behavior with 100K+ rows

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **BUG-FOE-001**, **BUG-FOE-002**, **BUG-FOE-003** |
| P1 | 10 | **ENG-FOE-001**, **ENG-FOE-002**, **ENG-FOE-003**, **ENG-FOE-004**, **ENG-FOE-005**, **BUG-FOE-004**, **BUG-FOE-005**, **BUG-FOE-006**, **BUG-FOE-007**, **PERF-FOE-001** |
| P2 | 13 | **ENG-FOE-006**, **ENG-FOE-007**, **ENG-FOE-008**, **ENG-FOE-009**, **ENG-FOE-010**, **NAME-FOE-001**, **NAME-FOE-002**, **NAME-FOE-003**, **STD-FOE-001**, **STD-FOE-002**, **STD-FOE-003**, **PERF-FOE-002**, **TEST-FOE-001** |
| P3 | 3 | **ENG-FOE-011**, **ENG-FOE-012**, **PERF-FOE-003** |
| **Total** | **29** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All 12 issues resolved (FIXED) |
| Engine (ENG) | 12 | ENG-FOE-001 through ENG-FOE-012 |
| Bug (BUG) | 7 | BUG-FOE-001 through BUG-FOE-007 |
| Naming (NAME) | 3 | NAME-FOE-001 through NAME-FOE-003 |
| Standards (STD) | 3 | STD-FOE-001 through STD-FOE-003 |
| Performance (PERF) | 3 | PERF-FOE-001 through PERF-FOE-003 |
| Testing (TEST) | 1 | TEST-FOE-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set (BUG-FOE-001) |
| XCUT-002 | `base_component.py:174` | `replace_in_config` literal `[i]` (BUG-FOE-002) |
| XCUT-003 | `base_component.py:132` | `validate_schema` inverted nullable (BUG-FOE-003) |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash in base class (P0, XCUT-001)
2. Fix `replace_in_config` literal `[i]` in base class (P0, XCUT-002)
3. Fix `validate_schema` inverted nullable in base class (P0, XCUT-003)

### Short-term (Hardening)

1. Add cell positioning support (ENG-FOE-001, P1)
2. Add password protection (ENG-FOE-002, P1)
3. Fix NaN detection string-cast (BUG-FOE-004, P1)
4. Add workbook context manager (BUG-FOE-005, P1)
5. Add engine unit tests (TEST-FOE-001, P2)

### Long-term (Optimization)

1. Add streaming write mode (ENG-FOE-010, P2)
2. Add batch write optimization (PERF-FOE-001, P1)
3. Add shared strings table (ENG-FOE-011, P3)
4. Replace `iterrows()` with vectorized approach (PERF-FOE-003, P3)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| **File path traversal** | Medium | High | FILENAME accepts arbitrary paths with no validation. A malicious context variable could write to sensitive locations (e.g., `/etc/`, `~/.ssh/`). Mitigation: Add path allowlist or sandbox validation. |
| **Password in plaintext config** | High | Medium | The PASSWORD param is stored in plaintext in job config JSON. If configs are logged, stored in version control, or transmitted over the network, the password is exposed. Mitigation: Use credential store or environment variable reference. |
| **Formula injection** | Medium | High | Excel formula injection via cell content. Input data containing `=CMD(...)`, `=HYPERLINK(...)`, or similar can execute arbitrary commands when the output file is opened in Excel. Mitigation: Prefix cell values starting with `=`, `+`, `-`, `@` with a single quote. |
| **Memory exhaustion** | High | High | No streaming write support (SXSSF equivalent). Large datasets (500K+ rows) loaded entirely into memory via openpyxl workbook object. Combined with `iterrows()` creating per-row Series objects, this can trigger OOM on production servers. Mitigation: Implement chunked write or use openpyxl write-only mode. |
| **Encoding mismatch** | Medium | Medium | Engine default is UTF-8 but _java.xml default is ISO-8859-15. Jobs migrated from Talend without explicit ENCODING may produce files with incorrect character encoding. Mitigation: Engine should read encoding config or converter should emit a warning. |
| **Append mode data corruption** | Low | High | Append mode loads the full workbook, modifies it, and saves. If the process crashes between load and save, the original file may be corrupted or lost. No atomic write (temp file + rename) pattern used. Mitigation: Write to temp file first, then atomic rename. |
| **NaN leaking to Excel cells** | High | Medium | `is_non_empty_row()` uses string comparison `str(value).strip().lower() != 'nan'` which is fragile. Actual NaN values from pandas may not match this pattern in all locales. Result: NaN values written to cells as literal "nan" strings. Mitigation: Use `pd.isna()` for NaN detection. |

### High-Risk Job Patterns

1. **Large dataset writes (500K+ rows)** -- memory exhaustion likely without streaming mode
2. **Append mode with concurrent access** -- workbook corruption risk
3. **Jobs with context variable paths** -- path traversal if variables are user-supplied
4. **Legacy .xls format jobs** -- silently produce .xlsx regardless of VERSION_2007 setting
5. **Jobs relying on cell positioning** -- data always written starting at A1

### Safe Usage Patterns

1. **Basic xlsx write** -- simple file output with header, no append, small datasets (< 100K rows)
2. **Single-sheet output** -- no append mode, create=true, default settings
3. **UTF-8 with explicit encoding** -- set ENCODING explicitly to avoid default mismatch
4. **No formula content** -- input data without leading `=` characters

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | <https://help.qlik.com/talend/en-US/components/7.3/tfileoutputexcel/tfileoutputexcel-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputExcel/tFileOutputExcel_java.xml> | Component definition XML -- 29 params verified |
| Engine source | `src/v1/engine/components/file/file_output_excel.py` | Feature parity analysis (382 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_output_excel.py` | Converter audit (249 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_output_excel.py` | Test coverage (66 tests) |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py:174` | `replace_in_config` literal `[i]` breaks list element expression resolution |
| XCUT-003 | `base_component.py:132` | `validate_schema` inverted nullable logic destroys intentional nulls |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 10 converter standardization (gold-standard rewrite)*
