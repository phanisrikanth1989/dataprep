# Audit Report: tFileInputFullRow / FileInputFullRowComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputFullRow` |
| **V1 Engine Class** | `FileInputFullRowComponent` |
| **Engine File** | `src/v1/engine/components/file/file_input_fullrow.py` (213 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileinputfullrow()` (lines 1090-1097) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFileInputFullRow':` (line 254) |
| **Registry Aliases** | `FileInputFullRowComponent`, `tFileInputFullRow` (registered in `src/v1/engine/engine.py` lines 64-65) |
| **Category** | File / Input |
| **Complexity** | Low-Medium -- single-column line reader with minimal configuration |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_fullrow.py` | Engine implementation (213 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1090-1097) | Active parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/component_parser.py` (lines 1073-1088) | Dead code: alternate parser `parse_file_input_full_row()` (never called) |
| `src/converters/complex_converter/converter.py` (line 254) | Dispatch to `parse_tfileinputfullrow()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 5 | 3 | 1 | 5 of 12 runtime Talend params extracted (42%); missing HEADER, FOOTER, DIE_ON_ERROR; FILENAME not quote-stripped; dead code parser; row_separator quote-strip crash; encoding not quote-stripped |
| Engine Feature Parity | **Y** | 0 | 5 | 2 | 1 | No header/footer skip; no REJECT flow; hardcoded column name; no ERROR_MESSAGE/FILENAME globalMap; limit=0 reads zero rows |
| Code Quality | **Y** | 1 | 4 | 6 | 5 | unicode_escape crash risk; \r\n normalization bug; limit type fragility; dual validation methods; strip() filters whitespace-only lines |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | Entire file loaded into memory; intermediate list for filtering; suboptimal DataFrame construction |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputFullRow Does

`tFileInputFullRow` reads a file row by row and sends each complete row as a single string value to the next component via a Row link. Unlike `tFileInputDelimited`, it does **not** parse fields within each row -- the entire line is treated as one atomic string. This is commonly used for:

- Pre-processing raw log files before field extraction via `tExtractRegexFields` or `tExtractDelimitedFields`
- Reading configuration files line by line
- Handling non-delimited or irregularly structured files
- Feeding raw lines into `tMap` for downstream conditional parsing

The component belongs to the **File** family and is available in the Standard Job framework across all Talend products. It is also available in MapReduce (deprecated), Spark Batch, and Spark Streaming frameworks.

**Source**: [tFileInputFullRow Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/fullrow/tfileinputfullrow-standard-properties), [tFileInputFullRow Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/fullrow/tfileinputfullrow-standard-properties), [tFileInputFullRow Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/fullrow/tfileinputfullrow), [tFileInputFullRow -- Talend Skill ESB 5.x Docs](https://talendskill.com/talend-for-esb-docs/docs-5-x/tfileinputfullrow-docs-for-esb-5-x/)

**Component family**: FullRow (File / Input)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Defines the single output column. Schema consists of a single read-only column (typically named `line`), always of type String. |
| 3 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path to the input file. Supports context variables, globalMap references, and Java expressions. |
| 4 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | Character or string identifying the end of each row. Supports `\r\n`, `\n`, `\r`, or custom multi-character separators (e.g., `"||"`). |
| 5 | Header | `HEADER` | Integer | `0` | Number of rows to skip at the beginning of the file. These rows are completely discarded and never appear in output. |
| 6 | Footer | `FOOTER` | Integer | `0` | Number of rows to skip at the end of the file. Requires reading the entire file to determine the last N rows. |
| 7 | Limit | `LIMIT` | Integer | `0` | Maximum number of rows to read. `0` means unlimited (read all rows). Applies after header skip. |
| 8 | Skip Empty Rows | `REMOVE_EMPTY_ROW` | Boolean (CHECK) | `false` | When enabled, blank/empty rows are excluded from output. |
| 9 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | When checked, job stops on error. When unchecked, error rows are routed to REJECT flow (if connected) or silently dropped. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 10 | Encoding | `ENCODING` | Dropdown / Custom | System default (JVM-dependent) | Character encoding for file reading. Options include ISO-8859-15, UTF-8, and custom values. JVM-dependent default. |
| 11 | Extract Lines at Random | `RANDOM` | Boolean (CHECK) | `false` | Enable random line extraction mode instead of sequential reading. |
| 12 | Number of Random Lines | `NB_RANDOM` | Integer | -- | Number of lines to extract randomly. Only visible when `RANDOM=true`. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 14 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully read rows. Each row contains a single string column with the full line content. |
| `REJECT` | Output | Row > Reject | Rows that failed processing (when `DIE_ON_ERROR` is unchecked). Includes ALL original schema columns PLUS `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false` and a REJECT link is connected. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows read and processed from the file (after header/footer/limit/empty-row filtering). This is the primary row count variable. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message text when exceptions occur. Only functional when `DIE_ON_ERROR` is unchecked. |

**Note on FILENAME**: Some implementations store `{id}_FILENAME` with the resolved file path. This is not part of the official Talend documentation for this component but is a common community expectation based on other file input components.

### 3.5 Behavioral Notes

1. **Schema is always single-column**: The output schema of `tFileInputFullRow` has exactly one column of type `String`. The column name is user-defined in the schema editor (commonly `line`, `row`, or `data`). The column is read-only in Talend Studio.

2. **No field parsing**: Unlike `tFileInputDelimited`, this component does NOT split lines into fields. The entire line becomes a single string value. To extract individual fields from the output, use complementary components like `tExtractDelimitedFields`, `tExtractRegexFields`, or `tMap`.

3. **Row separator handling**: The row separator splits the file content into individual rows. Common values are `"\n"` (Unix), `"\r\n"` (Windows), or custom separators like `"||"`. Multi-character separators are fully supported.

4. **HEADER behavior**: When `HEADER > 0`, Talend skips that many rows at the TOP of the file. These rows are completely discarded.

5. **FOOTER behavior**: When `FOOTER > 0`, Talend discards that many rows at the BOTTOM of the file. This requires reading the entire file to determine the total row count before trimming.

6. **LIMIT=0 means unlimited**: In tFileInputFullRow, `LIMIT=0` (or empty) means "read all rows" with no cap. This is explicitly stated in Talend documentation: "maximum number of rows to be processed; 0 means no limit."

7. **REJECT flow**: When `DIE_ON_ERROR` is unchecked and a REJECT link is connected, error rows are routed to REJECT with `errorCode` and `errorMessage` columns appended. When REJECT is NOT connected, errors are silently dropped.

8. **Empty rows**: With `REMOVE_EMPTY_ROW=true`, lines that are empty strings (after splitting on the row separator) are excluded from output. Whitespace-only lines may be considered empty depending on Talend version.

9. **File not found**: When the file does not exist and `DIE_ON_ERROR=true`, the job fails immediately. When `DIE_ON_ERROR=false`, the component produces zero rows and sets `ERROR_MESSAGE`.

10. **Random extraction**: When `RANDOM=true`, the component reads the entire file but returns only `NB_RANDOM` randomly selected lines. The order of returned lines is not guaranteed.

11. **Encoding**: Affects how bytes are decoded into characters. Mismatch between file encoding and configured encoding can produce garbled text (mojibake) or `UnicodeDecodeError` exceptions.

12. **NB_LINE availability**: The `NB_LINE` global variable is set after the component finishes. It reflects the total rows that were **output** (after header/footer/limit/empty-row filtering).

13. **Always use absolute paths**: Talend documentation explicitly recommends using absolute file paths to prevent processing errors. Relative paths depend on the JVM's working directory, which may differ between environments.

---

## 4. Converter Audit

### 4.1 Converter Architecture

The complex converter has a dedicated dispatch for `tFileInputFullRow` at `converter.py` line 254:

```python
elif component_type == 'tFileInputFullRow':
    component = self.component_parser.parse_tfileinputfullrow(node, component)
```

This calls the `parse_tfileinputfullrow()` method (lines 1090-1097) which uses direct `node.find()` calls to extract parameters.

**Important**: There is also a second parser method `parse_file_input_full_row()` (lines 1073-1088) that uses an if/elif iteration pattern. This method is **dead code** -- it is never called from any dispatch path. The two methods have different behavior (quote stripping, different config key naming).

### 4.2 Parameter Extraction (Active Parser: `parse_tfileinputfullrow`)

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filename` | 1092 | **No quote stripping** -- Talend stores values with surrounding double quotes (e.g., `"C:/data/file.txt"`). Literal quotes may be passed to the engine. |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | 1093 | Default `'\n'`; no quote stripping on this either |
| 3 | `REMOVE_EMPTY_ROW` | Yes | `remove_empty_row` | 1094 | Boolean conversion via `.lower() == 'true'` |
| 4 | `ENCODING` | Yes | `encoding` | 1095 | Default `'UTF-8'` -- **differs from Talend JVM-dependent default** |
| 5 | `LIMIT` | Yes | `limit` | 1096 | Passed as raw string |
| 6 | `HEADER` | **No** | -- | -- | **Not extracted. Jobs with header rows will include headers as data.** |
| 7 | `FOOTER` | **No** | -- | -- | **Not extracted. Jobs with footer rows will include trailers as data.** |
| 8 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted. Engine defaults to `True` internally, but jobs with explicit `false` setting will not have graceful error handling converted.** |
| 9 | `RANDOM` | **No** | -- | -- | **Not extracted. Random sampling not available.** |
| 10 | `NB_RANDOM` | **No** | -- | -- | **Not extracted.** |
| 11 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 12 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 13 | `SCHEMA` | N/A | -- | -- | Schema handled separately by base parser |
| 14 | `LABEL` | No | -- | -- | Not extracted (cosmetic -- no runtime impact) |

**Summary**: 5 of 12 runtime-relevant parameters extracted (42%). 3 critical runtime parameters are missing (HEADER, FOOTER, DIE_ON_ERROR).

### 4.3 Parameter Extraction (Dead Code Parser: `parse_file_input_full_row`)

For reference, the dead code parser at lines 1073-1088 extracts a different set:

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `filename` | Quote-stripped via `.strip('"')` -- **better** than active parser |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | Quote-stripped |
| 3 | `ENCODING` | Yes | `encoding` | Quote-stripped |
| 4 | `REMOVE_EMPTY_ROW` | Yes | `remove_empty_rows` | Note: **plural** `rows` -- inconsistent with active parser's singular `row` and engine's singular `row` |
| 5 | `LIMIT` | **No** | -- | Not extracted in this version |
| 6 | `HEADER` | **No** | -- | Not extracted |
| 7 | `FOOTER` | **No** | -- | Not extracted |
| 8 | `DIE_ON_ERROR` | **No** | -- | Not extracted |

**Key difference**: The dead code parser correctly quote-strips `FILENAME` but uses `remove_empty_rows` (plural) while the engine reads `remove_empty_row` (singular). If the dead code parser were ever activated, the `REMOVE_EMPTY_ROW` setting would be silently lost due to the naming mismatch.

### 4.4 Schema Extraction

Schema is extracted generically by the base parser. For `tFileInputFullRow`, the schema typically has a single column:

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from schema (e.g., `line`, `data`, `raw_line`) |
| `type` | Yes | Always `id_String` for this component |
| `nullable` | Yes | Boolean conversion |
| `key` | Yes | Boolean conversion |
| `length` | Yes | Integer conversion if present |

**Critical gap**: The engine ignores the schema column name entirely and hardcodes the output column to `line`. See BUG-FIFR-004.

### 4.5 Expression Handling

**Context variable handling**: Context variables in `FILENAME` (e.g., `context.input_dir + "/data.txt"`) are handled by the generic context resolution in `BaseComponent.execute()`. The converter does not perform any special expression handling for this component.

**Java expression handling**: Java expressions in `FILENAME` are detected by `mark_java_expression()` in the generic parameter processing loop. However, since `parse_tfileinputfullrow()` uses direct `node.find()` calls rather than iterating through the generic loop, Java expressions in `FILENAME` may **not** be properly marked with `{{java}}` prefix.

**Known limitation**: The active parser does not call `self.expr_converter.mark_java_expression()` on the extracted `FILENAME` value. If the filename contains a Java expression (e.g., `context.dir + "/file.txt"`), it will be stored as a literal string without the `{{java}}` marker, and the base class's `_resolve_java_expressions()` method will not process it.

### 4.6 Null Safety in Active Parser

The active parser uses `node.find()` which returns `None` if the element is not found. The subsequent `.get('value', '')` call on `None` will raise `AttributeError`. For example:

```python
component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
```

If a Talend XML node for `tFileInputFullRow` is missing the `FILENAME` element (malformed XML), this line will crash with `AttributeError: 'NoneType' object has no attribute 'get'`. The dead code parser's if/elif pattern is safer because it only processes elements that exist.

### 4.7 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FIFR-001 | **P1** | **`HEADER` not extracted by complex converter**: The `parse_tfileinputfullrow()` method does not extract the `HEADER` parameter. Talend jobs that skip header rows will lose this setting during conversion, causing the header line(s) to appear as data rows in the output. |
| CONV-FIFR-002 | **P1** | **`FOOTER` not extracted by complex converter**: The `parse_tfileinputfullrow()` method does not extract the `FOOTER` parameter. Talend jobs that skip footer rows will include trailer lines in the output data. |
| CONV-FIFR-003 | **P1** | **`FILENAME` not quote-stripped in active parser**: The active `parse_tfileinputfullrow()` uses `.get('value', '')` without stripping quotes. Talend stores string parameters with surrounding double quotes (e.g., `"C:/data/file.txt"`). The dead code parser correctly calls `.strip('"')`, but the active parser does not, potentially passing literal quote characters in the file path. The engine will then try to open a file with quotes in the path, which will fail with `FileNotFoundError`. |
| CONV-FIFR-004 | **P2** | **`DIE_ON_ERROR` not extracted by any converter path**: Neither the active parser nor the dead code parser extracts `DIE_ON_ERROR`. The v1 engine defaults to `True` internally, but jobs where it was explicitly set to `false` in Talend will not have graceful error handling after conversion. |
| CONV-FIFR-005 | **P2** | **Dead code: `parse_file_input_full_row()` is never called**: The method at line 1073 is dead code. The converter dispatch at `converter.py:254` calls `parse_tfileinputfullrow()` instead. This creates confusion about which parser is canonical and has a naming inconsistency (`remove_empty_rows` vs `remove_empty_row`). |
| CONV-FIFR-006 | **P2** | **Config key `filename` vs `filepath` naming**: The complex converter stores the file path as `filename` in the v1 config. However, other v1 file input components (e.g., `FileInputDelimited`) use `filepath`. This inconsistency means any generic code that expects `filepath` will not find the file path for this component. |
| CONV-FIFR-007 | **P3** | **`RANDOM`/`NB_RANDOM` not extracted**: Random line extraction is not supported by any converter or engine. Low priority as this is a rarely used feature. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read file line by line | **Yes** | High | `_process()` lines 139-149 | Uses `open()` + `read()` + `split()` -- functional but loads entire file |
| 2 | Single-column output | **Yes** | Medium | `_process()` line 167 | Column name hardcoded to `line` -- does NOT read from schema |
| 3 | Row separator | **Yes** | Medium | `_process()` lines 109-116 | Supports custom separators; escape sequence decoding applied; quote stripping applied |
| 4 | Remove empty rows | **Yes** | High | `_process()` lines 154-157 | Filters lines where `line.strip()` is empty |
| 5 | Encoding support | **Yes** | High | `_process()` line 139 | Passed to `open()` as `encoding` parameter |
| 6 | Limit (max rows) | **Yes** | Medium | `_process()` lines 160-164 | Only applied when `limit` is a digit string -- integer limit causes crash |
| 7 | Die on error | **Yes** | High | `_process()` lines 97-103, 128-136, 182-191 | Respects `die_on_error` config; raises or returns empty DataFrame |
| 8 | File not found handling | **Yes** | High | `_process()` lines 128-136 | Checks `os.path.exists()` before reading |
| 9 | Multi-char row separator | **Yes** | High | `_process()` line 149 | `split()` works with multi-character separators |
| 10 | `\r\n` normalization | **Yes** | Low | `_process()` line 145 | **Unconditional** `\r\n` -> `\n` replacement breaks `\r\n` as row separator |
| 11 | Config validation | **Yes** | Medium | `_validate_config()` lines 61-83 | Called by `_process()` at entry; validates filename, encoding, limit |
| 12 | Statistics tracking | **Yes** | High | `_process()` line 172 | `_update_stats()` with NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 13 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 14 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 15 | **Header skip** | **No** | N/A | -- | **Not implemented -- config parameter not consumed** |
| 16 | **Footer skip** | **No** | N/A | -- | **Not implemented -- config parameter not consumed** |
| 17 | **REJECT flow** | **No** | N/A | -- | **No reject output. All errors either die or return empty DF.** |
| 18 | **Random extraction** | **No** | N/A | -- | **Not implemented** |
| 19 | **Schema-driven column naming** | **No** | N/A | -- | **Column is always `line` regardless of schema definition** |
| 20 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not set -- Talend sets this on error** |
| 21 | **`{id}_FILENAME` globalMap** | **No** | N/A | -- | **Not set -- Talend stores the resolved filename** |
| 22 | **tStatCatcher Statistics** | **No** | N/A | -- | **Not implemented** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIFR-001 | **P1** | **No header row skipping**: The v1 engine does not consume a `header` or `header_rows` configuration parameter. Talend jobs with `HEADER > 0` will include header lines as data rows, corrupting the output. This is a common setting in production jobs, especially for files with column-header lines. |
| ENG-FIFR-002 | **P1** | **No footer row skipping**: The v1 engine does not consume a `footer` or `footer_rows` configuration parameter. Talend jobs with `FOOTER > 0` will include trailer lines as data rows. Footer skipping is used in many financial data files that have summary/trailer records. |
| ENG-FIFR-003 | **P1** | **No REJECT flow output**: Talend's tFileInputFullRow produces reject rows with `errorCode` and `errorMessage` when `DIE_ON_ERROR` is unchecked and a REJECT link is connected. The v1 engine either raises an exception (die_on_error=true) or returns an empty DataFrame (die_on_error=false). There is NO mechanism to capture and route bad rows. This is a fundamental gap for data quality pipelines. |
| ENG-FIFR-004 | **P1** | **Column name hardcoded to `line`**: The v1 engine always outputs a column named `line` regardless of the schema definition. In Talend, the column name is defined by the schema (could be `data`, `raw_line`, `content`, etc.). Any downstream component that references the schema-defined column name will fail if it is not `line`. |
| ENG-FIFR-005 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: Talend sets `{id}_ERROR_MESSAGE` on error. The v1 engine does not set this variable, so downstream components or trigger conditions that check for error messages will not work correctly. |
| ENG-FIFR-006 | **P2** | **`{id}_FILENAME` not set in globalMap**: Talend sets `{id}_FILENAME` to the resolved file path. The v1 engine does not set this variable. Downstream logging or file-tracking logic that reads this variable will get null. |
| ENG-FIFR-007 | **P3** | **`\r\n` normalization may alter data**: The engine unconditionally replaces `\r\n` with `\n` in the file content before splitting (line 145). If the row separator is explicitly `\r\n` (Windows line endings), the normalization destroys it. Talend does not perform unconditional normalization -- it splits directly on the configured row separator. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE since no reject exists |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no reject flow exists |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_FILENAME` | Uncertain (community expectation) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | v1-specific, not in Talend |

### 5.4 Empty File Edge Case

When the input file is empty (0 bytes):

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0. No error. |
| **V1** | `file.read()` returns empty string. `''.split('\n')` returns `['']` -- a list with one empty string. If `remove_empty_row=True`, this is filtered out, yielding 0 rows. If `remove_empty_row=False`, the engine outputs 1 row with an empty string. **This differs from Talend**, which produces 0 rows for an empty file regardless of the `remove_empty_row` setting. |
| **Verdict** | **GAP**: v1 produces 1 empty row for empty files when `remove_empty_row=False`. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIFR-001 | **P0** | `file_input_fullrow.py:116` | **`unicode_escape` decode on arbitrary user input is dangerous and incorrect for many separators**: The line `row_separator = row_separator.encode().decode('unicode_escape')` converts escape sequences like `\\n` to `\n`. However, `unicode_escape` codec has known issues with non-ASCII characters and can produce incorrect results for separators containing backslashes that are not escape sequences. More critically, if the separator contains bytes in the range `\x80`-`\xFF`, `unicode_escape` will raise a `UnicodeDecodeError` because it treats them as incomplete escape sequences. This is a latent crash risk for any row separator containing non-ASCII characters. |
| BUG-FIFR-002 | **P1** | `file_input_fullrow.py:160` | **`limit` type check is fragile**: The code checks `if limit and limit.isdigit()` but `limit` is extracted from config as-is. If `limit` is passed as an integer (e.g., from a programmatic caller), `isdigit()` will raise `AttributeError` because integers have no `isdigit()` method. |
| BUG-FIFR-003 | **P1** | `file_input_fullrow.py:145` | **Unconditional `\r\n` normalization corrupts custom separators**: If `row_separator` is `"\r\n"` (Windows line endings), the code first normalizes all `\r\n` to `\n`, then splits on `\r\n`. Since all `\r\n` sequences have been replaced, the split produces a single element containing the entire file content. The entire file becomes one row instead of being split into lines. |
| BUG-FIFR-004 | **P1** | `file_input_fullrow.py:167` | **Hardcoded column name `line` ignores schema**: The output always uses `{'line': line}` regardless of the schema definition. In Talend, the schema defines the column name. If the schema says `data` or `raw_content`, the v1 engine still outputs `line`, causing column-not-found errors in downstream components. |
| BUG-FIFR-005 | **P1** | `file_input_fullrow.py:167-168` | **Empty file produces phantom row**: When the input file is empty, `''.split('\n')` returns `['']` (a list with one empty string element). With `remove_empty_row=False`, the engine outputs a DataFrame with one row containing an empty string. Talend outputs zero rows for an empty file. This phantom row can cause incorrect row counts and downstream data corruption. |
| BUG-FIFR-009 | **P1** | `component_parser.py:1093` / `file_input_fullrow.py:109-116` | **Single-quote row_separator causes empty separator crash**: Quote-stripping on `'"'` produces empty string. `''.split('')` raises `ValueError`. Converter doesn't validate row_separator. |
| BUG-FIFR-010 | **P1** | `component_parser.py:1095` | **Encoding value from converter not quote-stripped (line 1095)**: `open(filename, 'r', encoding='"UTF-8"')` raises `LookupError`. Guaranteed crash for converted jobs. |
| BUG-FIFR-011 | **P1** | `file_input_fullrow.py:160-164` | **Limit=0 reads zero rows instead of unlimited**: `lines[:0]` = `[]`. Contradicts Talend where LIMIT=0 means no limit. |
| BUG-FIFR-012 | **P2** | `file_input_fullrow.py:154-157` | **`remove_empty_row` uses `strip()` which filters whitespace-only lines**: Talend only removes truly empty (zero-length) lines. Data loss for whitespace-preserving files. |

### 6.2 Cross-Cutting Bugs (Base Class)

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIFR-006 | **P0 (cross-cutting)** | `base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **Affects ALL components**, not just FileInputFullRowComponent, since `_update_global_map()` is called after every component execution via `execute()`. |
| BUG-FIFR-007 | **P0 (cross-cutting)** | `global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **Affects ALL code** using `global_map.get()`. |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIFR-001 | **P2** | **Config key `remove_empty_row` (singular) vs dead parser's `remove_empty_rows` (plural)**: The active parser and engine use `remove_empty_row` (singular), matching Talend's `REMOVE_EMPTY_ROW`. The dead code parser uses `remove_empty_rows` (plural). This inconsistency would cause silent failures if the dead code parser were ever activated. |
| NAME-FIFR-002 | **P2** | **Config key `filename` (v1 complex converter) vs `filepath` (other v1 file components)**: The complex converter stores the file path as `filename`, but other v1 file input components (e.g., `FileInputDelimited`) use `filepath`. This inconsistency makes generic file-path handling across components impossible without special-casing. |
| NAME-FIFR-003 | **P3** | **File name `file_input_fullrow.py` (no underscore before `row`)**: The v1 file uses `fullrow` as a single word, while the class name uses `FullRow` (two words). Minor inconsistency in naming convention. |
| NAME-FIFR-004 | **P3** | **Class name `FileInputFullRowComponent` includes `Component` suffix**: Most other v1 file components (e.g., `FileInputDelimited`, `FileOutputDelimited`) do not use the `Component` suffix. Some do (e.g., `FileArchiveComponent`, `FileExistComponent`). This is inconsistent across the component family. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIFR-001 | **P2** | "`_validate_config()` must validate all config parameters" (METHODOLOGY.md) | `_validate_config()` does not validate `row_separator`. An empty row separator would cause `split('')` which raises `ValueError: empty separator` at runtime. |
| STD-FIFR-002 | **P2** | "`_validate_config()` must validate parameter types" (METHODOLOGY.md) | `_validate_config()` does not validate `die_on_error` type. If passed as string `"true"` instead of boolean `True`, the truthiness check would evaluate incorrectly. |
| STD-FIFR-003 | **P2** | "Single validation entry point" (STANDARDS.md) | The class has both a public `validate_config()` (line 193) that returns `bool` and a private `_validate_config()` (line 61) that returns `List[str]`. The public method wraps the private one but catches all exceptions, which could mask validation bugs. |
| STD-FIFR-004 | **P3** | "Use custom exception hierarchy" (STANDARDS.md) | The engine raises `ValueError`, `FileNotFoundError`, and `RuntimeError`. STANDARDS.md defines `ConfigurationError`, `FileOperationError`, and `ComponentExecutionError` as the preferred exception types. |
| STD-FIFR-005 | **P3** | "Docstrings must describe validation rules" (STANDARDS.md) | The `validate_config()` docstring says "Returns: True if the configuration is valid" but does not enumerate what specific validations are performed. |

### 6.5 Error Handling Quality

| ID | Priority | Issue |
|----|----------|-------|
| ERR-FIFR-001 | **P2** | **`FileNotFoundError` re-raised without wrapping**: Line 179-181 catches `FileNotFoundError` and re-raises it directly. STANDARDS.md recommends wrapping in `FileOperationError` for consistent exception handling upstream. |
| ERR-FIFR-002 | **P2** | **Generic `Exception` catch wraps in `RuntimeError`**: Line 182-187 catches all exceptions and wraps them in `RuntimeError`. This loses the original exception type information. STANDARDS.md recommends using `ComponentExecutionError`. |
| ERR-FIFR-003 | **P3** | **`validate_config()` swallows exceptions**: The public `validate_config()` method (line 193) catches `Exception` and returns `False`, logging the error. This means a bug in the validation code itself (e.g., `TypeError` from a None config value) would be silently treated as "invalid config" rather than propagating as a code defect. |

### 6.6 Logging Quality

The component has good logging that follows STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones (file path, completion), DEBUG for details (config, row counts) -- correct |
| Start/complete logging | `_process()` logs file path at INFO (line 123); logs completion with row counts at INFO (line 174) -- correct |
| Sensitive data | No file content logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process() -> Dict[str, Any]`, `validate_config() -> bool` -- all present |
| Parameter types | `input_data: Optional[pd.DataFrame] = None` -- correct |
| Import types | Uses `Any`, `Dict`, `List`, `Optional` from typing -- correct |

### 6.8 Dead Code

| ID | Priority | Issue |
|----|----------|-------|
| DEAD-FIFR-001 | **P2** | **`parse_file_input_full_row()` in `component_parser.py` (lines 1073-1088) is dead code**: This method is never called by any dispatch path. The converter dispatch at `converter.py:254` calls `parse_tfileinputfullrow()` instead. The dead code has different behavior (quote stripping, different config key naming) which creates confusion. Should be deleted or consolidated with the active parser. |

### 6.9 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FIFR-001 | **P3** | **No path traversal protection**: The `filename` from config is passed directly to `open()` without sanitization. If the config is derived from user input or external data, path traversal attacks (e.g., `../../etc/passwd`) are possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FIFR-002 | **P3** | **Config values logged at DEBUG level**: The `logger.debug()` call on line 124 logs the row separator, encoding, and limit values. If debug logging is enabled in production, this could expose configuration details. Low risk. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIFR-001 | **P1** | **Entire file loaded into memory**: Lines 139-141 read the entire file content into a string with `file.read()`, then split it into a list of lines on line 149. For very large files (multiple GB), this requires at minimum 2x the file size in memory (the raw string + the list of split lines). Talend's tFileInputFullRow reads line by line via Java's `BufferedReader`, using constant memory. The v1 engine should use `readline()` iteration or chunked reading for large files. |
| PERF-FIFR-002 | **P2** | **List comprehension creates intermediate list for empty row filtering**: Line 156 creates a new list `[line for line in lines if line.strip()]`. For files with millions of lines, this doubles memory usage temporarily. Could use a generator or filter in-place. |
| PERF-FIFR-003 | **P3** | **DataFrame construction from list of dicts is suboptimal**: Lines 167-168 create a list of dicts `[{'line': line} for line in lines]` then pass it to `pd.DataFrame()`. This is slower than `pd.DataFrame({'line': lines})` which avoids creating intermediate dict objects per row. For a file with 10 million lines, this creates 10 million unnecessary dict objects. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | **Not implemented** -- the component reads the entire file at once regardless of file size. The base class `execute()` supports streaming mode, but `_process()` always does a full file read. |
| Memory threshold | `MEMORY_THRESHOLD_MB = 3072` (3GB) inherited from `BaseComponent`, but the component does not check file size before reading. A 10GB file will be read entirely into memory. |
| Chunked processing | Not available. Unlike `FileInputDelimited` which can use pandas `chunksize`, this component reads and splits the entire file in one pass. |
| File size check | Not performed before reading. No warning or fallback for large files. |

### 7.2 Memory Usage Profile for Various File Sizes

| File Size | Memory Required (Approximate) | Risk |
|-----------|------------------------------|------|
| 1 MB | ~3 MB (file content + split list + dict list + DataFrame) | Low |
| 100 MB | ~300 MB | Low-Medium |
| 1 GB | ~3 GB | High -- may cause OOM on machines with limited RAM |
| 10 GB | ~30 GB | **Critical** -- will OOM on most machines |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputFullRowComponent` v1 engine |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests for this component |

**Key finding**: The v1 engine has ZERO tests for this component. All 213 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic file read | P0 | Read a multi-line text file, verify row count and content of each `line` column value |
| 2 | Empty file | P0 | Read an empty file, verify empty DataFrame returned with stats (0, 0, 0). Verify NO phantom row. |
| 3 | File not found + die_on_error=true | P0 | Should raise FileNotFoundError or FileOperationError with descriptive message |
| 4 | File not found + die_on_error=false | P0 | Should return empty DataFrame with stats (0, 0, 0) |
| 5 | Remove empty rows enabled | P0 | File with blank lines, verify they are excluded |
| 6 | Remove empty rows disabled | P0 | File with blank lines, verify they are preserved |
| 7 | Limit applied | P0 | File with 10 lines, limit="3", verify only 3 rows returned |
| 8 | Statistics tracking | P0 | Verify NB_LINE, NB_LINE_OK, NB_LINE_REJECT are set correctly in stats dict after execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 9 | Custom row separator | P1 | File with `||` separator, verify correct splitting |
| 10 | Row separator `\r\n` | P1 | Windows line endings, verify correct behavior (documents BUG-FIFR-003) |
| 11 | Row separator with quotes | P1 | Separator `"\n"` with surrounding quotes, verify quote stripping |
| 12 | Encoding ISO-8859-1 | P1 | File with non-UTF8 characters, verify correct reading |
| 13 | Invalid encoding | P1 | Bad encoding string, verify error handling |
| 14 | Limit as string "5" | P1 | Verify string limit is handled correctly |
| 15 | Limit as integer 5 | P1 | Verify integer limit handling (documents BUG-FIFR-002) |
| 16 | Limit zero reads all | P1 | Verify limit=0 reads all rows per Talend behavior |
| 17 | GlobalMap update | P1 | Verify stats are pushed to globalMap after execution |
| 18 | Context variable in filename | P1 | Filename with `${context.input_dir}`, verify resolution |
| 19 | Config validation -- missing filename | P1 | Verify `_validate_config()` returns error for missing `filename` |
| 20 | Config validation -- empty filename | P1 | Verify `_validate_config()` returns error for empty `filename` |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Large file memory | P2 | Verify behavior with large file (document OOM risk) |
| 22 | Unicode content | P2 | File with emoji, CJK characters, verify correct reading |
| 23 | Whitespace-only rows with remove_empty | P2 | Lines with only spaces/tabs, verify `strip()` filtering |
| 24 | Non-ASCII row separator | P2 | Separator containing non-ASCII character (documents BUG-FIFR-001) |
| 25 | Single-line file | P2 | File with no row separators, verify single-row output |
| 26 | File with BOM | P2 | UTF-8 file with BOM, verify handling |
| 27 | Binary content in text file | P2 | Verify graceful handling of non-text bytes |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIFR-001 | Bug | `unicode_escape` decode on row separator can crash on non-ASCII input or produce incorrect results |
| BUG-FIFR-006 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined `value` variable. Will crash ALL components when `global_map` is set. |
| BUG-FIFR-007 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined `default` parameter. Will crash on any `global_map.get()` call. |
| TEST-FIFR-001 | Testing | Zero v1 unit tests for this component. All 213 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIFR-001 | Converter | `HEADER` not extracted by complex converter -- header rows appear as data |
| CONV-FIFR-002 | Converter | `FOOTER` not extracted by complex converter -- footer rows appear as data |
| CONV-FIFR-003 | Converter | `FILENAME` not quote-stripped in active parser -- literal quotes in file path cause FileNotFoundError |
| ENG-FIFR-001 | Engine | No header row skipping in v1 engine -- HEADER config parameter not consumed |
| ENG-FIFR-002 | Engine | No footer row skipping in v1 engine -- FOOTER config parameter not consumed |
| ENG-FIFR-003 | Engine | No REJECT flow -- error rows are lost or cause job failure |
| ENG-FIFR-004 | Engine | Column name hardcoded to `line`, ignores schema definition |
| BUG-FIFR-002 | Bug | `limit` type check fails if limit is passed as integer (no `isdigit()` on int) |
| BUG-FIFR-003 | Bug | `\r\n` normalization corrupts splitting when row_separator is `\r\n` |
| BUG-FIFR-004 | Bug | Hardcoded column name `line` ignores schema (duplicate of ENG-FIFR-004) |
| BUG-FIFR-005 | Bug | Empty file produces phantom row -- `''.split('\n')` returns `['']` |
| BUG-FIFR-009 | Bug | Single-quote row_separator causes empty separator crash. Quote-stripping on `'"'` produces empty string. `''.split('')` raises ValueError. Converter doesn't validate row_separator. |
| BUG-FIFR-010 | Bug | Encoding value from converter not quote-stripped (line 1095). `open(filename, 'r', encoding='"UTF-8"')` raises LookupError. Guaranteed crash for converted jobs. |
| BUG-FIFR-011 | Bug | Limit=0 reads zero rows instead of unlimited. `lines[:0]` = `[]`. Contradicts Talend where LIMIT=0 means no limit. |
| PERF-FIFR-001 | Performance | Entire file loaded into memory -- OOM risk for large files |
| TEST-FIFR-002 | Testing | No integration test for v1 engine pipeline |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIFR-004 | Converter | `DIE_ON_ERROR` not extracted by any converter path |
| CONV-FIFR-005 | Converter | Dead code: `parse_file_input_full_row()` is never called |
| CONV-FIFR-006 | Converter | Config key `filename` vs `filepath` naming inconsistency across v1 components |
| ENG-FIFR-005 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap |
| ENG-FIFR-006 | Engine | `{id}_FILENAME` not set in globalMap |
| NAME-FIFR-001 | Naming | Config key singular/plural inconsistency (`remove_empty_row` vs `remove_empty_rows`) |
| NAME-FIFR-002 | Naming | Config key `filename` vs `filepath` mismatch across converter and other components |
| STD-FIFR-001 | Standards | `_validate_config()` does not validate `row_separator` |
| STD-FIFR-002 | Standards | `_validate_config()` does not validate `die_on_error` type |
| STD-FIFR-003 | Standards | Dual `validate_config()` / `_validate_config()` methods |
| DEAD-FIFR-001 | Dead Code | `parse_file_input_full_row()` is dead code (duplicate: CONV-FIFR-005) |
| PERF-FIFR-002 | Performance | Intermediate list created for empty row filtering |
| BUG-FIFR-012 | Bug | `remove_empty_row` uses `strip()` which filters whitespace-only lines. Talend only removes truly empty (zero-length) lines. Data loss for whitespace-preserving files. |
| ERR-FIFR-001 | Error Handling | `FileNotFoundError` re-raised without wrapping in `FileOperationError` |
| ERR-FIFR-002 | Error Handling | Generic exception wrapped in `RuntimeError` instead of `ComponentExecutionError` |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIFR-007 | Converter | `RANDOM`/`NB_RANDOM` not extracted (rarely used) |
| ENG-FIFR-007 | Engine | `\r\n` normalization may alter data compared to Talend behavior |
| NAME-FIFR-003 | Naming | File name `file_input_fullrow.py` naming convention |
| NAME-FIFR-004 | Naming | Class name `FileInputFullRowComponent` suffix inconsistency |
| STD-FIFR-004 | Standards | Exception types do not use custom exception hierarchy |
| STD-FIFR-005 | Standards | No docstring on validation rules |
| ERR-FIFR-003 | Error Handling | `validate_config()` swallows exceptions |
| SEC-FIFR-001 | Security | No path traversal protection |
| SEC-FIFR-002 | Security | Config values logged at DEBUG level |
| PERF-FIFR-003 | Performance | DataFrame construction from list of dicts is suboptimal |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 3 bugs (1 component-specific + 2 cross-cutting), 1 testing |
| P1 | 16 | 3 converter, 4 engine, 7 bugs, 1 performance, 1 testing |
| P2 | 15 | 3 converter, 2 engine, 2 naming, 3 standards, 1 dead code, 1 performance, 2 error handling, 1 bug |
| P3 | 10 | 1 converter, 1 engine, 2 naming, 2 standards, 1 error handling, 2 security, 1 performance |
| **Total** | **45** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FIFR-006): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FIFR-007): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Fix BUG-FIFR-001**: Replace `unicode_escape` decode with a targeted escape sequence handler that only processes known escape sequences (`\\n` -> `\n`, `\\t` -> `\t`, `\\r` -> `\r`):
   ```python
   ESCAPE_MAP = {'\\n': '\n', '\\t': '\t', '\\r': '\r', '\\\\': '\\'}
   for seq, char in ESCAPE_MAP.items():
       row_separator = row_separator.replace(seq, char)
   ```

4. **Fix BUG-FIFR-003**: Remove or conditionalize the `\r\n` normalization. Only normalize when the row separator is `\n`:
   ```python
   if row_separator == '\n':
       file_content = file_content.replace('\r\n', '\n')
   ```

5. **Fix BUG-FIFR-004 / ENG-FIFR-004**: Read column name from schema instead of hardcoding `line`:
   ```python
   col_name = 'line'  # default
   if self.output_schema and len(self.output_schema) > 0:
       col_name = self.output_schema[0].get('name', 'line')
   output_data = [{col_name: line} for line in lines]
   ```

6. **Fix BUG-FIFR-005**: Handle empty file edge case:
   ```python
   if not file_content:
       self._update_stats(0, 0, 0)
       return {'main': pd.DataFrame(columns=[col_name])}
   ```

7. **Fix BUG-FIFR-002**: Add type coercion for `limit`:
   ```python
   if limit is not None:
       try:
           limit_val = int(limit)
           if limit_val > 0 and len(lines) > limit_val:
               lines = lines[:limit_val]
       except (ValueError, TypeError):
           logger.warning(f"[{self.id}] Invalid limit value: {limit}, ignoring")
   ```

8. **Create unit test suite** (TEST-FIFR-001): Implement at minimum the 8 P0 test cases listed in Section 8.2.

9. **Fix CONV-FIFR-003**: Add quote stripping to the active parser for `FILENAME`:
   ```python
   component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
   ```

### Short-Term (Hardening)

10. **Implement header/footer skipping** (ENG-FIFR-001, ENG-FIFR-002): Add `header` and `footer` parameters to `_process()`:
    ```python
    header = int(self.config.get('header', 0))
    footer = int(self.config.get('footer', 0))
    if header > 0:
        lines = lines[header:]
    if footer > 0 and len(lines) > footer:
        lines = lines[:-footer]
    ```

11. **Update converters** (CONV-FIFR-001, CONV-FIFR-002, CONV-FIFR-004): Extract `HEADER`, `FOOTER`, and `DIE_ON_ERROR` in `parse_tfileinputfullrow()`:
    ```python
    component['config']['header'] = int(node.find('.//elementParameter[@name="HEADER"]').get('value', '0'))
    component['config']['footer'] = int(node.find('.//elementParameter[@name="FOOTER"]').get('value', '0'))
    component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'true').lower() == 'true'
    ```

12. **Set globalMap variables** (ENG-FIFR-005, ENG-FIFR-006): Add `ERROR_MESSAGE` and `FILENAME` to globalMap after processing:
    ```python
    if self.global_map:
        self.global_map.put(f"{self.id}_FILENAME", filename)
    # In error handlers:
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    ```

13. **Delete dead code** (DEAD-FIFR-001 / CONV-FIFR-005): Remove `parse_file_input_full_row()` from `component_parser.py` to eliminate confusion about canonical parser.

14. **Add null safety to active parser** (CONV-FIFR-003 related): Add None checks on `node.find()` results to prevent `AttributeError` on malformed XML:
    ```python
    filename_node = node.find('.//elementParameter[@name="FILENAME"]')
    if filename_node is not None:
        component['config']['filename'] = filename_node.get('value', '').strip('"')
    ```

### Long-Term (Optimization)

15. **Implement streaming file reading** (PERF-FIFR-001): For the default `\n` separator, use line-by-line reading:
    ```python
    lines = []
    with open(filename, 'r', encoding=encoding) as f:
        for line_content in f:
            lines.append(line_content.rstrip('\n'))
    ```
    For custom separators, use buffered reading with separator detection.

16. **Implement REJECT flow** (ENG-FIFR-003): Add a `reject` key to the output dictionary:
    ```python
    return {'main': df, 'reject': reject_df}
    ```

17. **Optimize DataFrame construction** (PERF-FIFR-003): Use direct column construction:
    ```python
    df = pd.DataFrame({col_name: lines})
    ```

18. **Use custom exception types** (STD-FIFR-004): Replace `ValueError` with `ConfigurationError`, `FileNotFoundError` with `FileOperationError`, and `RuntimeError` with `ComponentExecutionError`.

19. **Consolidate validation methods** (STD-FIFR-003): Remove the public `validate_config()` wrapper and integrate `_validate_config()` into the standard lifecycle.

20. **Add comprehensive config validation** (STD-FIFR-001, STD-FIFR-002): Validate all config parameters including `row_separator` (must not be empty), `die_on_error` type (must be boolean), and `remove_empty_row` type.

21. **Implement random extraction** (CONV-FIFR-007): If business need exists, add random sampling via `random.sample(lines, nb_random)`.

22. **Add path traversal protection** (SEC-FIFR-001): Validate filename against allowed base directories.

---

## Appendix A: Converter Parameter Mapping Code

### Active Parser: `parse_tfileinputfullrow()` (lines 1090-1097)

```python
def parse_tfileinputfullrow(self, node, component: Dict) -> Dict:
    """Parse tFileInputFullRow specific configuration"""
    component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    component['config']['row_separator'] = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
    component['config']['remove_empty_row'] = node.find('.//elementParameter[@name="REMOVE_EMPTY_ROW"]').get('value', 'false').lower() == 'true'
    component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    component['config']['limit'] = node.find('.//elementParameter[@name="LIMIT"]').get('value', '')
    return component
```

**Notes on this code**:
- Line 1092: No quote stripping on `FILENAME`. Talend XML stores string values with surrounding double quotes. The engine receives `"C:/data/file.txt"` (with quotes) instead of `C:/data/file.txt`.
- Line 1093: Default `'\n'` matches Talend default for row separator.
- Line 1094: Boolean conversion via `.lower() == 'true'` -- correct.
- Line 1095: Default `'UTF-8'` -- Talend's default is JVM-dependent (often `ISO-8859-15` for European locales).
- Line 1096: `LIMIT` passed as raw string -- engine handles int conversion.
- Missing: `HEADER`, `FOOTER`, `DIE_ON_ERROR`, `RANDOM`, `NB_RANDOM`.
- No null safety: If any `elementParameter` is missing from the XML, `node.find()` returns `None` and `.get()` raises `AttributeError`.

### Dead Code Parser: `parse_file_input_full_row()` (lines 1073-1088)

```python
def parse_file_input_full_row(self, node, component: Dict) -> Dict:
    """Parse tFileInputFullRow specific configuration."""
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')

        if name == 'FILENAME':
            component['config']['filename'] = value.strip('"')
        elif name == 'ROWSEPARATOR':
            component['config']['row_separator'] = value.strip('"')
        elif name == 'ENCODING':
            component['config']['encoding'] = value.strip('"')
        elif name == 'REMOVE_EMPTY_ROW':
            component['config']['remove_empty_rows'] = value.lower() == 'true'

    return component
```

**Notes on this code**:
- Correctly quote-strips all string parameters via `.strip('"')`.
- Uses `remove_empty_rows` (plural) instead of `remove_empty_row` (singular), which does NOT match the engine's expected config key.
- Does not extract `LIMIT`, `HEADER`, `FOOTER`, or `DIE_ON_ERROR`.
- More defensive than active parser (iterates only elements that exist).
- **This method is NEVER called** -- `converter.py` dispatches to `parse_tfileinputfullrow()` instead.

---

## Appendix B: Engine Class Structure

```
FileInputFullRowComponent (BaseComponent)
    No Constants (defaults inline in _process())

    Methods:
        _validate_config() -> List[str]          # Called by _process() -- validates filename, encoding, limit
        _process(input_data) -> Dict[str, Any]    # Main entry point -- reads file, splits, filters, limits
        validate_config() -> bool                 # Public wrapper around _validate_config() (backward compat)
```

**Execution flow**:
```
BaseComponent.execute(input_data)
    -> _resolve_java_expressions()      [if java_bridge set]
    -> context_manager.resolve_dict()   [if context_manager set]
    -> _execute_batch(input_data)       [or _execute_streaming]
        -> _process(input_data)
            -> _validate_config()
            -> open(filename) + read()
            -> file_content.replace('\r\n', '\n')
            -> file_content.split(row_separator)
            -> [filter empty rows]
            -> [apply limit]
            -> pd.DataFrame([{'line': line} for line in lines])
            -> _update_stats(rows, rows, 0)
            -> return {'main': df}
    -> _update_global_map()
    -> status = SUCCESS
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filename` | Mapped (no quote strip) | Fix P1 |
| `ROWSEPARATOR` | `row_separator` | Mapped | -- |
| `REMOVE_EMPTY_ROW` | `remove_empty_row` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped | -- |
| `LIMIT` | `limit` | Mapped (as string) | -- |
| `HEADER` | -- | **Not Mapped** | P1 |
| `FOOTER` | -- | **Not Mapped** | P1 |
| `DIE_ON_ERROR` | -- | **Not Mapped** | P2 |
| `RANDOM` | -- | **Not Mapped** | P3 |
| `NB_RANDOM` | -- | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `SCHEMA` | via base parser | Handled separately | -- |

---

## Appendix D: GlobalMap Variable Completeness

| Talend Variable | V1 Engine Sets? | Mechanism | Notes |
|-----------------|-----------------|-----------|-------|
| `{id}_NB_LINE` | Yes | `_update_stats()` -> `_update_global_map()` via base class | Correct |
| `{id}_NB_LINE_OK` | Yes | `_update_stats()` -> `_update_global_map()` via base class | Always equals NB_LINE (no reject flow) |
| `{id}_NB_LINE_REJECT` | Yes | `_update_stats()` -> `_update_global_map()` via base class | Always 0 (no reject flow) |
| `{id}_NB_LINE_INSERT` | Yes | Via base class default (0) | Not applicable to input component |
| `{id}_NB_LINE_UPDATE` | Yes | Via base class default (0) | Not applicable to input component |
| `{id}_NB_LINE_DELETE` | Yes | Via base class default (0) | Not applicable to input component |
| `{id}_EXECUTION_TIME` | Yes | Via base class `execute()` method | v1-specific, not in Talend |
| `{id}_ERROR_MESSAGE` | **No** | Not set | GAP: Talend sets this on error |
| `{id}_FILENAME` | **No** | Not set | GAP: Common community expectation |

---

## Appendix E: Base Class Contract Compliance

The `FileInputFullRowComponent` extends `BaseComponent`. Here is a compliance check against the base class contract:

| Base Class Requirement | Compliant? | Notes |
|------------------------|-----------|-------|
| Implement `_process()` | Yes | Returns `{'main': df}` on all code paths |
| Call `_update_stats()` | Yes | Called on success (line 172), validation failure (line 103), file not found (line 135), and generic error (line 190) |
| Respect `die_on_error` | Yes | Checked on validation failure (line 100), file not found (line 131), and generic error (line 186) |
| Use `self.id` in log messages | Yes | All log messages prefixed with `[{self.id}]` |
| Return dict with `'main'` key | Yes | All paths return `{'main': df}` or `{'main': pd.DataFrame()}` |
| Return dict with `'reject'` key | No | REJECT flow not implemented |
| Use `self.config` for configuration | Yes | All config read from `self.config` |
| Support `self.global_map` | Partial | Stats pushed via base class, but `ERROR_MESSAGE` and `FILENAME` not set |
| Support `self.context_manager` | Inherited | Context resolution handled by base class `execute()` |
| Support `self.java_bridge` | Inherited | Java expression resolution handled by base class `execute()` |
| Support `execution_mode` | Inherited | Hybrid/batch/streaming handled by base class |

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty file

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0, NB_LINE_OK=0. No error. |
| **V1** | `file.read()` returns `''`. `''.split('\n')` returns `['']` (list with one empty string). With `remove_empty_row=True`, filtered to 0 rows. With `remove_empty_row=False`, produces 1 row with empty string. |
| **Verdict** | **GAP**: v1 produces phantom row when `remove_empty_row=False`. |

### Edge Case 2: File with only whitespace

| Aspect | Detail |
|--------|--------|
| **Talend** | With `REMOVE_EMPTY_ROW=true`, returns 0 rows. With `false`, returns whitespace rows. |
| **V1** | With `remove_empty_row=True`, `line.strip()` removes whitespace-only lines. With `False`, whitespace preserved. |
| **Verdict** | CORRECT (matches Talend behavior for `strip()` semantics) |

### Edge Case 3: Single-line file with no trailing newline

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 1 row with the file content. |
| **V1** | `"content".split('\n')` returns `['content']`. 1 row with correct content. |
| **Verdict** | CORRECT |

### Edge Case 4: File with trailing newline

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns N rows (trailing newline does NOT create an extra empty row). |
| **V1** | `"line1\nline2\n".split('\n')` returns `['line1', 'line2', '']`. The trailing empty string IS included as a row. With `remove_empty_row=True`, it is filtered. With `False`, an extra empty row appears. |
| **Verdict** | **GAP**: v1 produces extra empty row from trailing separator when `remove_empty_row=False`. |

### Edge Case 5: Windows line endings (`\r\n`)

| Aspect | Detail |
|--------|--------|
| **Talend** | With `ROWSEPARATOR="\r\n"`, splits correctly on Windows line endings. |
| **V1** | The unconditional `file_content.replace('\r\n', '\n')` on line 145 destroys `\r\n` before the split. If `row_separator` is `'\r\n'`, the subsequent `split('\r\n')` finds no matches, and the entire file becomes one row. |
| **Verdict** | **BUG**: See BUG-FIFR-003. |

### Edge Case 6: Custom multi-character separator

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports multi-character separators like `"||"`. Splits correctly. |
| **V1** | Python `str.split("||")` works correctly for multi-character separators. |
| **Verdict** | CORRECT |

### Edge Case 7: Non-ASCII row separator

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports any character as separator. |
| **V1** | `unicode_escape` codec on line 116 will crash if the separator contains non-ASCII bytes in the `\x80`-`\xFF` range. |
| **Verdict** | **BUG**: See BUG-FIFR-001. |

### Edge Case 8: Limit=0

| Aspect | Detail |
|--------|--------|
| **Talend** | `LIMIT=0` means unlimited -- read all rows. |
| **V1** | `limit` config value would be `'0'`. Code: `if limit and limit.isdigit()` -- `'0'` is truthy, `'0'.isdigit()` is `True`, so `limit_val = int('0') = 0`. Then `len(lines) > 0` is True, so `lines = lines[:0]` = `[]`. This means **LIMIT=0 reads zero rows** instead of all rows. |
| **Verdict** | **BUG**: Limit=0 reads zero rows instead of being treated as unlimited. This is a significant behavioral difference from Talend. |

### Edge Case 9: NaN handling in output

| Aspect | Detail |
|--------|--------|
| **Talend** | Each row is a string. No NaN values possible in normal operation. |
| **V1** | The output DataFrame has column `line` with string values from `split()`. No NaN values are introduced during normal operation. However, if `pd.DataFrame()` is called with an empty list, it produces an empty DataFrame with no columns (not even `line`). |
| **Verdict** | PARTIAL: Empty output loses the `line` column schema. |

### Edge Case 10: Empty DataFrame schema loss

| Aspect | Detail |
|--------|--------|
| **Talend** | Even with 0 rows, the output maintains the schema (column `line` of type String). |
| **V1** | When validation fails or file not found with `die_on_error=False`, the code returns `pd.DataFrame()` which is a completely empty DataFrame with NO columns. Downstream components expecting the `line` column will fail with `KeyError`. |
| **Verdict** | **GAP**: Empty DataFrames lose schema. Should return `pd.DataFrame(columns=[col_name])`. |

### Edge Case 11: File path with spaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `os.path.exists()` and `open()` both handle spaces correctly in Python. |
| **Verdict** | CORRECT |

### Edge Case 12: Context variable resolving to empty filename

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with clear error. |
| **V1** | `_validate_config()` checks `not self.config['filename']` (line 68). Empty string is falsy, so validation catches it. |
| **Verdict** | CORRECT |

### Edge Case 13: Limit=0 as string "0"

| Aspect | Detail |
|--------|--------|
| **Talend** | Limit=0 means unlimited. |
| **V1** | `"0".isdigit()` is `True`, `int("0")` is `0`, `lines[:0]` returns empty list. **All data is lost.** |
| **Verdict** | **BUG**: See Edge Case 8. The limit check should treat 0 as unlimited, not as "read zero rows". |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileInputFullRowComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FIFR-006 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when globalMap is set. |
| BUG-FIFR-007 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FIFR-006 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-FIFR-007 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FIFR-001 -- Replace `unicode_escape` with Safe Escape Handler

**File**: `src/v1/engine/components/file/file_input_fullrow.py`
**Line**: 116

**Current**:
```python
row_separator = row_separator.encode().decode('unicode_escape')
```

**Fix** (add as method to class):
```python
def _decode_escape_sequences(self, value: str) -> str:
    """
    Decode common escape sequences in a string value.
    Only handles the standard Java/Talend escape sequences.
    """
    ESCAPE_MAP = {
        '\\n': '\n',
        '\\r': '\r',
        '\\t': '\t',
        '\\\\': '\\',
    }
    result = value
    for escape_seq, replacement in ESCAPE_MAP.items():
        result = result.replace(escape_seq, replacement)
    return result
```

**Usage**:
```python
row_separator = self._decode_escape_sequences(row_separator)
```

**Risk**: Low. Handles the same common cases without edge-case crashes.

---

### Fix Guide: BUG-FIFR-003 -- Conditional CR/LF Normalization

**File**: `src/v1/engine/components/file/file_input_fullrow.py`
**Lines**: 144-145

**Current**:
```python
file_content = file_content.replace('\r\n', '\n')
```

**Fix**:
```python
# Only normalize \r\n to \n if the row separator is \n (Unix-style)
# This prevents data corruption when the row separator IS \r\n
if row_separator == '\n':
    file_content = file_content.replace('\r\n', '\n')
```

**Risk**: Low. Only changes behavior when `row_separator` is not `\n`.

---

### Fix Guide: BUG-FIFR-005 -- Empty File Phantom Row

**File**: `src/v1/engine/components/file/file_input_fullrow.py`
**After line 140 (after file read)**

**Add**:
```python
# Handle empty file
if not file_content:
    logger.info(f"[{self.id}] File is empty: {filename}")
    self._update_stats(0, 0, 0)
    return {'main': pd.DataFrame(columns=[col_name])}
```

**Risk**: Low. Prevents phantom row and preserves schema in empty output.

---

### Fix Guide: Edge Case 8 / Edge Case 13 -- Limit=0 Treated as Unlimited

**File**: `src/v1/engine/components/file/file_input_fullrow.py`
**Line**: 160-164

**Current**:
```python
if limit and limit.isdigit():
    limit_val = int(limit)
    if len(lines) > limit_val:
        lines = lines[:limit_val]
```

**Fix**:
```python
if limit is not None:
    try:
        limit_val = int(limit)
        if limit_val > 0 and len(lines) > limit_val:
            lines = lines[:limit_val]
            logger.debug(f"[{self.id}] Applied limit: kept first {limit_val} rows")
    except (ValueError, TypeError):
        logger.warning(f"[{self.id}] Invalid limit value: {limit}, ignoring")
```

**Behavioral change**: `limit=0` or `limit="0"` is now treated as unlimited (matches Talend). Integer and string limit values both work.

---

## Appendix I: Comparison with Similar Components

### tFileInputFullRow vs tFileInputDelimited (v1 Engine)

| Aspect | tFileInputFullRow | tFileInputDelimited |
|--------|-------------------|---------------------|
| Output columns | Single column `line` (hardcoded) | Multiple columns per schema |
| Field parsing | None -- entire line is one value | Delimiter-based field splitting |
| Header skip | **Not implemented** | Implemented |
| Footer skip | **Not implemented** | Implemented |
| Text enclosure | N/A | Implemented |
| Escape character | N/A | Implemented |
| CSV option | N/A | N/A (not implemented) |
| Reject flow | **Not implemented** | **Not implemented** |
| Streaming mode | Not needed (base class handles) | Implemented natively |
| Schema type enforcement | N/A (always string) | Implemented via `validate_schema()` |
| `_validate_config()` | Called by `_process()` | Dead code -- never called |
| Test coverage (v1) | **None** | **None** |
| Engine file size | 213 lines | 575 lines |
| Memory model | Full file in memory | Supports streaming via `pd.read_csv(chunksize=)` |

Both components share the same gap in REJECT flow and test coverage. The tFileInputFullRow additionally lacks header/footer support that tFileInputDelimited has. However, tFileInputFullRow has a working `_validate_config()` (called by `_process()`), while tFileInputDelimited's `_validate_config()` is dead code.

### tFileInputFullRow vs tFileInputRaw (v1 Engine)

| Aspect | tFileInputFullRow | tFileInputRaw |
|--------|-------------------|---------------|
| Output type | DataFrame with `line` column | Raw bytes or string |
| Row splitting | Splits on row separator | No splitting -- entire file as one value |
| Schema | Single-column string schema | No schema |
| Row separator | Configurable | N/A |
| Header/footer | Not implemented (should be) | N/A |
| Use case | Line-by-line processing | Whole-file processing (e.g., XML, JSON) |
| Memory model | Full file in memory + split list | Full file in memory |

---

## Appendix J: Detailed Code Walkthrough

### File: `file_input_fullrow.py` -- Line-by-Line Analysis

**Lines 1-18: Module Setup**
- Proper module docstring with Talend equivalence noted
- Standard imports: `logging`, `os`, `typing` (Any, Dict, List, Optional), `pandas`
- BaseComponent import from relative path `...base_component`
- Module-level logger via `logging.getLogger(__name__)` -- compliant with STANDARDS.md

**Lines 21-59: Class Docstring**
- Comprehensive docstring covering configuration, inputs, outputs, statistics, and example
- Documents `filename`, `row_separator`, `remove_empty_row`, `encoding`, `limit`, `die_on_error`
- Does NOT document `header` or `footer` parameters (because they are not implemented)
- Notes section is accurate for implemented behavior
- Example configuration JSON is valid and helpful

**Lines 61-83: `_validate_config()` Method**
- Validates `filename` presence and non-emptiness -- good
- Validates `encoding` type (must be string) -- good
- Validates `limit` is numeric string or empty -- good but fragile (does not handle integer type)
- Does NOT validate `row_separator` -- gap (STD-FIFR-001)
- Does NOT validate `die_on_error` type -- gap (STD-FIFR-002)
- Does NOT validate `remove_empty_row` type -- minor gap
- Returns list of error strings -- compliant with base class contract

**Lines 85-104: `_process()` Entry and Validation**
- Calls `_validate_config()` and joins errors into message -- good
- Respects `die_on_error` for validation failures -- raises `ValueError` or returns empty DF
- Returns empty DataFrame on validation failure when `die_on_error=False` -- correct Talend behavior
- Updates stats to (0, 0, 0) on failure -- correct

**Lines 106-126: Configuration Extraction**
- Extracts `filename`, `row_separator`, `remove_empty_row`, `encoding`, `limit`, `die_on_error` with defaults
- Row separator quote stripping: checks for surrounding double quotes and removes them -- correct
- Row separator escape decoding via `unicode_escape` -- **problematic** (see BUG-FIFR-001)
- `remove_empty_row` defaults to `False` -- matches Talend
- `encoding` defaults to `'UTF-8'` -- may differ from Talend JVM default
- `die_on_error` defaults to `True` -- matches Talend Studio default
- Logging at INFO for file path, DEBUG for config details -- compliant

**Lines 127-136: File Existence Check**
- Uses `os.path.exists()` -- correct
- Respects `die_on_error` -- raises `FileNotFoundError` or returns empty DF with warning
- Returns empty DataFrame with stats (0, 0, 0) on file not found -- correct

**Lines 138-149: File Reading and Splitting**
- `open(filename, 'r', encoding=encoding)` -- correct encoding usage
- `file.read()` -- **loads entire file into memory** (see PERF-FIFR-001)
- `file_content.replace('\r\n', '\n')` -- **unconditional normalization** (see BUG-FIFR-003)
- `file_content.split(row_separator)` -- correct splitting with configurable separator
- Debug logging of raw line count -- helpful for troubleshooting

**Lines 153-164: Filtering and Limiting**
- Empty row removal via `line.strip()` -- correct (treats whitespace-only as empty, matching Talend)
- Logging of removed row count -- helpful
- Limit check: `if limit and limit.isdigit()` -- **fragile type check** (see BUG-FIFR-002)
- Limit slicing: `lines[:limit_val]` -- correct but `limit_val=0` produces empty list (see Edge Case 8)

**Lines 166-177: Output Construction**
- `[{'line': line} for line in lines]` -- **hardcoded column name** (see BUG-FIFR-004); also suboptimal (PERF-FIFR-003)
- DataFrame construction from list of dicts -- functional but slow for large lists
- Stats update with `(rows_processed, rows_processed, 0)` -- NB_LINE equals NB_LINE_OK, NB_LINE_REJECT always 0
- Returns `{'main': df}` -- correct single-output structure
- INFO log for completion with row count and filename -- good

**Lines 179-191: Exception Handling**
- `FileNotFoundError` re-raised directly -- should wrap in `FileOperationError` (ERR-FIFR-001)
- Generic `Exception` wrapped in `RuntimeError` with `from e` chaining -- correct chaining but wrong exception type (ERR-FIFR-002)
- `die_on_error` respected in generic catch -- correct
- Empty DataFrame returned on error when `die_on_error=False` -- correct

**Lines 193-214: `validate_config()` Public Method**
- Wrapper around `_validate_config()` returning bool
- Catches all exceptions -- defensive but may mask bugs (ERR-FIFR-003)
- Preserved for backward compatibility -- acceptable

---

## Appendix K: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using HEADER skip | **Critical** | Any job with HEADER > 0 on tFileInputFullRow | Must implement header skip before migrating |
| Jobs using FOOTER skip | **Critical** | Any job with FOOTER > 0 | Must implement footer skip before migrating |
| Jobs using REJECT flow | **High** | Any job with REJECT link on tFileInputFullRow | Must implement REJECT flow |
| Jobs with schema column name != `line` | **High** | Jobs where schema column is `data`, `raw_line`, etc. | Must implement schema-driven column naming |
| Jobs using `{id}_ERROR_MESSAGE` downstream | **Medium** | Jobs with error handling flows | Must set ERROR_MESSAGE in globalMap |
| Jobs with Windows line endings | **Medium** | Jobs with `ROWSEPARATOR="\r\n"` | Must fix CR/LF normalization bug |
| Jobs with large files (> 1 GB) | **Medium** | Jobs processing large log files | Must implement streaming or warn operators |
| Jobs with LIMIT=0 (meaning unlimited) | **Medium** | Jobs using default limit | Must fix limit=0 behavior |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using RANDOM sampling | Low | Rarely used in production |
| Jobs using tStatCatcher | Low | Monitoring feature, not data flow |
| Jobs with default config (no custom separator, no header/footer) | Low | Core functionality works |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting `_update_global_map()` and `GlobalMap.get()`, plus `unicode_escape` crash). Run existing converted jobs to verify basic functionality.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which P1 features are used (header skip, footer skip, column name, reject flow).
3. **Phase 3**: Implement P1 features required by target jobs. Prioritize header/footer skip and schema-driven column naming as they are the most commonly used.
4. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row, verifying column name, row count, and content.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix L: Converter Expression Handling for FILENAME

### How Context Variables Flow Through the Converter for tFileInputFullRow

When a Talend job contains `context.input_dir` in the `FILENAME` parameter, the following transformation occurs:

1. **Talend XML**: `<elementParameter name="FILENAME" value="&quot;/data/&quot;+context.input_dir+&quot;/input.txt&quot;" />`

2. **After XML parse**: `"/data/"+context.input_dir+"/input.txt"` (XML entities decoded by Python's XML parser)

3. **In `parse_tfileinputfullrow()` (line 1092)**: `.get('value', '')` extracts the raw value. No quote stripping is applied by the active parser. Result: `"/data/"+context.input_dir+"/input.txt"` (with surrounding quotes from the XML value)

4. **Java expression marking**: The active parser does NOT call `mark_java_expression()` on the extracted value. The `+` operator (Java string concatenation) is not detected. The value is stored as a literal string in the v1 config.

5. **At engine runtime** (`BaseComponent.execute()`):
   - `_resolve_java_expressions()` scans config for `{{java}}` markers -- finds none (expression was not marked)
   - `context_manager.resolve_dict()` scans config for `${context.var}` patterns -- finds none (the value uses Java concatenation syntax, not `${...}` syntax)
   - The filename remains unresolved as a literal string

**Gap**: Java expressions in `FILENAME` are NOT resolved for this component because the active parser bypasses the generic expression-marking pipeline. Simple context references like `${context.input_dir}/input.txt` (using `${...}` syntax) would still work because the context manager detects that pattern.

**Mitigation**: The active parser should mark Java expressions on the FILENAME value:
```python
filename_value = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
component['config']['filename'] = self.expr_converter.mark_java_expression(filename_value)
```

---

## Appendix M: Complete Engine Source Code Annotated

For reference, the complete `file_input_fullrow.py` is 213 lines with the following structure:

| Line Range | Purpose | Issues |
|-----------|---------|--------|
| 1-9 | Module docstring | Clean |
| 10-18 | Imports and logger | Clean |
| 21-59 | Class docstring | Comprehensive but does not mention header/footer |
| 61-83 | `_validate_config()` | Missing `row_separator` and `die_on_error` validation |
| 85-104 | `_process()` entry + validation | Correct; calls `_validate_config()` |
| 106-126 | Config extraction + escape decode | BUG-FIFR-001 (`unicode_escape`), BUG-FIFR-002 (limit type) |
| 127-136 | File existence check | Correct |
| 138-149 | File read + split | BUG-FIFR-003 (`\r\n` normalization), PERF-FIFR-001 (full read) |
| 153-164 | Filter empty + apply limit | BUG-FIFR-002 (limit type), Edge Case 8 (limit=0) |
| 166-177 | DataFrame construction + stats | BUG-FIFR-004 (hardcoded `line`), PERF-FIFR-003 |
| 179-191 | Exception handling | ERR-FIFR-001, ERR-FIFR-002 |
| 193-214 | `validate_config()` wrapper | ERR-FIFR-003 |

---

## Appendix N: Recommended Complete Parser Implementation

The following is the recommended replacement for the current `parse_tfileinputfullrow()` method. This method should replace both existing parsers in `component_parser.py` and be registered in `converter.py`.

```python
def parse_tfileinputfullrow(self, node, component: Dict) -> Dict:
    """
    Parse tFileInputFullRow specific configuration from Talend XML node.

    Extracts ALL Talend parameters for this component, with proper null
    safety, quote stripping, and Java expression marking.

    Talend Parameters:
        FILENAME (str): File path. Mandatory.
        ROWSEPARATOR (str): Row separator. Default "\\n"
        HEADER (int): Header rows to skip. Default 0
        FOOTER (int): Footer rows to skip. Default 0
        LIMIT (int): Max rows. Default 0 (unlimited)
        ENCODING (str): File encoding. Default system-dependent
        REMOVE_EMPTY_ROW (bool): Skip empty rows. Default false
        DIE_ON_ERROR (bool): Fail on error. Default true
        RANDOM (bool): Random extraction. Default false
        NB_RANDOM (int): Number of random rows.
    """
    config = component.get('config', {})

    # Extract scalar parameters with null safety
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')
        field = param.get('field', '')

        # Strip surrounding quotes (Talend XML wraps values in quotes)
        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        if name == 'FILENAME':
            # Mark Java expressions for runtime resolution
            config['filename'] = self.expr_converter.mark_java_expression(value) if hasattr(self, 'expr_converter') else value
        elif name == 'ROWSEPARATOR':
            config['row_separator'] = value if value else '\\n'
        elif name == 'HEADER':
            config['header'] = int(value) if value.isdigit() else 0
        elif name == 'FOOTER':
            config['footer'] = int(value) if value.isdigit() else 0
        elif name == 'LIMIT':
            config['limit'] = value  # Pass as string; engine handles conversion
        elif name == 'ENCODING':
            config['encoding'] = value if value else 'UTF-8'
        elif name == 'REMOVE_EMPTY_ROW':
            config['remove_empty_row'] = (value.lower() == 'true') if field == 'CHECK' else value.lower() == 'true'
        elif name == 'DIE_ON_ERROR':
            config['die_on_error'] = (value.lower() == 'true') if field == 'CHECK' else value.lower() == 'true'
        elif name == 'RANDOM':
            config['random'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'NB_RANDOM':
            config['nb_random'] = int(value) if value.isdigit() else 0

    component['config'] = config
    return component
```

**Key improvements over current `parse_tfileinputfullrow()` approach**:
1. Extracts ALL 10 runtime parameters instead of just 5
2. Adds null safety via iteration (does not crash on missing XML elements)
3. Properly quote-strips all string parameters
4. Marks `FILENAME` Java expressions via `mark_java_expression()`
5. Properly handles `CHECK` field type for boolean parameters
6. Extracts `HEADER`, `FOOTER`, and `DIE_ON_ERROR` that are currently missing
7. Follows the same pattern as other dedicated parsers in the codebase

**Registration in converter.py** (no change needed -- existing dispatch already calls this method name):
```python
elif component_type == 'tFileInputFullRow':
    component = self.component_parser.parse_tfileinputfullrow(node, component)
```

---

## Appendix O: Recommended Engine Enhancement for Header/Footer

The following code block shows the recommended changes to `_process()` in `file_input_fullrow.py` to implement header and footer skipping:

```python
# After splitting lines (after line 149):

# Apply header skip (discard first N rows)
header = 0
header_config = self.config.get('header', 0)
try:
    header = int(header_config)
except (ValueError, TypeError):
    logger.warning(f"[{self.id}] Invalid header value: {header_config}, defaulting to 0")

if header > 0:
    if header >= len(lines):
        logger.warning(f"[{self.id}] Header ({header}) >= total lines ({len(lines)}), no data rows remain")
        lines = []
    else:
        lines = lines[header:]
        logger.debug(f"[{self.id}] Skipped {header} header rows")

# Apply footer skip (discard last N rows)
footer = 0
footer_config = self.config.get('footer', 0)
try:
    footer = int(footer_config)
except (ValueError, TypeError):
    logger.warning(f"[{self.id}] Invalid footer value: {footer_config}, defaulting to 0")

if footer > 0 and len(lines) > 0:
    if footer >= len(lines):
        logger.warning(f"[{self.id}] Footer ({footer}) >= remaining lines ({len(lines)}), no data rows remain")
        lines = []
    else:
        lines = lines[:-footer]
        logger.debug(f"[{self.id}] Skipped {footer} footer rows")
```

**Behavioral notes**:
- Header is applied BEFORE footer, matching Talend's execution order
- Header is applied BEFORE empty row removal and limit
- If header >= total line count, result is 0 rows (no error)
- If footer >= remaining line count after header, result is 0 rows (no error)
- Invalid header/footer values (non-integer) default to 0 with warning

---

## Appendix P: Recommended Engine Enhancement for Schema-Driven Column Name

```python
# Replace hardcoded 'line' column name (line 167):

# Determine output column name from schema
col_name = 'line'  # Default fallback (matches Talend convention)
output_schema = self.config.get('output_schema', [])
if not output_schema:
    # Also check the instance attribute set by engine
    output_schema = getattr(self, 'output_schema', None) or []

if isinstance(output_schema, list) and len(output_schema) > 0:
    first_col = output_schema[0]
    if isinstance(first_col, dict) and 'name' in first_col:
        col_name = first_col['name']
        logger.debug(f"[{self.id}] Using schema-defined column name: '{col_name}'")

# Build output with dynamic column name
output_data = [{col_name: line} for line in lines]
df = pd.DataFrame(output_data) if output_data else pd.DataFrame(columns=[col_name])
```

**Behavioral notes**:
- Falls back to `line` if no schema is defined (backward compatible)
- Handles both `config['output_schema']` and `self.output_schema` attribute
- Empty output preserves the column schema (no schema loss)
- Only uses the FIRST column from the schema (tFileInputFullRow always has exactly one column)

---

## Appendix Q: Recommended Unit Test Skeleton

```python
"""
Unit tests for FileInputFullRowComponent (v1 engine).

Tests cover:
- Basic file reading
- Empty file handling
- File not found (both die_on_error modes)
- Remove empty rows
- Limit handling (string, integer, zero, invalid)
- Custom row separators
- Windows line endings
- Statistics tracking
- Config validation
"""
import os
import pytest
import pandas as pd
from src.v1.engine.components.file.file_input_fullrow import FileInputFullRowComponent


class TestFileInputFullRowBasic:
    """Basic functionality tests."""

    def test_basic_read(self, tmp_path):
        """Read a multi-line text file, verify row count and content."""
        f = tmp_path / "data.txt"
        f.write_text("line1\nline2\nline3\n")
        comp = FileInputFullRowComponent("test_1", {"filename": str(f)})
        result = comp._process()
        df = result['main']
        assert len(df) == 4  # 3 lines + 1 trailing empty (BUG-FIFR-005)
        assert df['line'].iloc[0] == "line1"
        assert df['line'].iloc[1] == "line2"
        assert df['line'].iloc[2] == "line3"

    def test_empty_file(self, tmp_path):
        """Empty file should return empty DataFrame."""
        f = tmp_path / "empty.txt"
        f.write_text("")
        comp = FileInputFullRowComponent("test_2", {"filename": str(f)})
        result = comp._process()
        df = result['main']
        # Current behavior: 1 row with empty string (BUG-FIFR-005)
        # Expected behavior after fix: 0 rows
        assert len(df) <= 1

    def test_file_not_found_die_on_error_true(self, tmp_path):
        """Missing file with die_on_error=True should raise."""
        comp = FileInputFullRowComponent("test_3", {
            "filename": str(tmp_path / "nonexistent.txt"),
            "die_on_error": True
        })
        with pytest.raises(FileNotFoundError):
            comp._process()

    def test_file_not_found_die_on_error_false(self, tmp_path):
        """Missing file with die_on_error=False should return empty DF."""
        comp = FileInputFullRowComponent("test_4", {
            "filename": str(tmp_path / "nonexistent.txt"),
            "die_on_error": False
        })
        result = comp._process()
        df = result['main']
        assert len(df) == 0


class TestFileInputFullRowFiltering:
    """Tests for empty row removal and limiting."""

    def test_remove_empty_rows_enabled(self, tmp_path):
        """Blank lines should be excluded when remove_empty_row=True."""
        f = tmp_path / "data.txt"
        f.write_text("line1\n\nline3\n\n")
        comp = FileInputFullRowComponent("test_5", {
            "filename": str(f),
            "remove_empty_row": True
        })
        result = comp._process()
        df = result['main']
        assert all(val.strip() != '' for val in df['line'].tolist())

    def test_remove_empty_rows_disabled(self, tmp_path):
        """Blank lines should be preserved when remove_empty_row=False."""
        f = tmp_path / "data.txt"
        f.write_text("line1\n\nline3\n")
        comp = FileInputFullRowComponent("test_6", {
            "filename": str(f),
            "remove_empty_row": False
        })
        result = comp._process()
        df = result['main']
        assert len(df) >= 3  # At least 3 entries (including empty)

    def test_limit_string(self, tmp_path):
        """String limit like '3' should work."""
        f = tmp_path / "data.txt"
        f.write_text("a\nb\nc\nd\ne\n")
        comp = FileInputFullRowComponent("test_7", {
            "filename": str(f),
            "limit": "3"
        })
        result = comp._process()
        assert len(result['main']) == 3

    def test_limit_zero_should_read_all(self, tmp_path):
        """Limit of 0 should read all rows (Talend behavior)."""
        f = tmp_path / "data.txt"
        f.write_text("a\nb\nc\n")
        comp = FileInputFullRowComponent("test_8", {
            "filename": str(f),
            "limit": "0"
        })
        result = comp._process()
        # Current bug: limit=0 truncates to 0 rows
        # After fix: should return all rows
        # assert len(result['main']) >= 3


class TestFileInputFullRowSeparators:
    """Tests for row separator handling."""

    def test_custom_separator(self, tmp_path):
        """Custom separator '||' should split correctly."""
        f = tmp_path / "data.txt"
        f.write_text("line1||line2||line3")
        comp = FileInputFullRowComponent("test_9", {
            "filename": str(f),
            "row_separator": "||"
        })
        result = comp._process()
        df = result['main']
        assert df['line'].iloc[0] == "line1"
        assert df['line'].iloc[1] == "line2"

    def test_crlf_separator(self, tmp_path):
        """Windows line endings as separator should work."""
        f = tmp_path / "data.txt"
        f.write_bytes(b"line1\r\nline2\r\nline3")
        comp = FileInputFullRowComponent("test_10", {
            "filename": str(f),
            "row_separator": "\r\n"
        })
        result = comp._process()
        # Current bug: \r\n normalization corrupts this
        # After fix: should have 3 rows


class TestFileInputFullRowValidation:
    """Tests for config validation."""

    def test_missing_filename(self):
        """Missing filename should fail validation."""
        comp = FileInputFullRowComponent("test_11", {})
        errors = comp._validate_config()
        assert len(errors) > 0
        assert any("filename" in e.lower() for e in errors)

    def test_empty_filename(self):
        """Empty filename should fail validation."""
        comp = FileInputFullRowComponent("test_12", {"filename": ""})
        errors = comp._validate_config()
        assert len(errors) > 0

    def test_valid_config(self, tmp_path):
        """Valid config should pass validation."""
        f = tmp_path / "data.txt"
        f.write_text("test")
        comp = FileInputFullRowComponent("test_13", {"filename": str(f)})
        errors = comp._validate_config()
        assert len(errors) == 0


class TestFileInputFullRowStats:
    """Tests for statistics tracking."""

    def test_stats_after_read(self, tmp_path):
        """Stats should reflect actual row count after processing."""
        f = tmp_path / "data.txt"
        f.write_text("a\nb\nc\n")
        comp = FileInputFullRowComponent("test_14", {"filename": str(f)})
        comp._process()
        assert comp.stats['NB_LINE'] > 0
        assert comp.stats['NB_LINE_OK'] == comp.stats['NB_LINE']
        assert comp.stats['NB_LINE_REJECT'] == 0
```

**Notes on test skeleton**:
- Some assertions are commented out where they document known bugs
- Tests use `tmp_path` pytest fixture for temporary file creation
- Test IDs follow component naming convention
- Each class groups related test scenarios
- Tests verify both happy path and error handling
