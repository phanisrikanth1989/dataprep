# Audit Report: tFileRowCount / FileRowCount

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileRowCount` |
| **V1 Engine Class** | `FileRowCount` |
| **Engine File** | `src/v1/engine/components/file/file_row_count.py` (229 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfile_row_count()` (lines 1706-1718) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif component_type == 'tFileRowCount'` branch (line 294) |
| **Registry Aliases** | `FileRowCount`, `tFileRowCount` (registered in `src/v1/engine/engine.py` lines 82-83) |
| **Category** | File / Utility |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_row_count.py` | Engine implementation (229 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1706-1718) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 294-295) | Dispatch -- dedicated `elif` branch for `tFileRowCount` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE`, `{id}_COUNT`, etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 13: `from .file_row_count import FileRowCount`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **R** | 1 | 1 | 2 | 1 | 4 of 6 Talend runtime params extracted (67%); dedicated parser method; missing DIE_ON_ERROR; encoding default mismatch; all 4 `.find().get()` calls crash on missing XML elements (P0); encoding value retains surrounding quotes from XML (P2) |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | No row_separator support; no die_on_error handling; return format is dict not DataFrame; no header row skip; no COUNT as Flow variable |
| Code Quality | **Y** | 2 | 4 | 3 | 1 | Cross-cutting base class bugs; _validate_config() returns bool instead of List[str]; _validate_config() never called; GlobalMap.get() crash on verify read; _update_global_map() double-crash on error path masks original exception (P1) |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Line-by-line reading is correct for this component; minor optimization with buffered counting |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; P0 converter crash on missing XML elements, cross-cutting base class bugs, and zero tests must be resolved first**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileRowCount Does

`tFileRowCount` opens a file and reads it row by row in order to determine the number of rows inside. The component is a standalone utility that counts lines in a file and stores the result in a globalMap variable (`{id}_COUNT`), which can be accessed by downstream components via OnSubjobOk triggers. It does NOT output a data flow -- it is purely a metadata/utility component. The primary use case is pre-validation: checking whether a file has expected row counts before processing it with input components.

**Source**: [tFileRowCount Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfilerowcount/tfilerowcount-standard-properties), [tFileRowCount Component Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfilerowcount/tfilerowcount), [tFileRowCount (Talend Skill ESB 7.x)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfilerowcount-talend-open-studio-for-esb-document-7-x/)

**Component family**: File (Utility)
**Available in**: All Talend products (Standard Job framework). Also available in Spark Batch and Spark Streaming variants.
**Required JARs**: None (standard Java I/O only). Some community notes mention potential licensing-restricted JARs for advanced features.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path. Supports context variables, globalMap references, Java expressions. Must be an absolute path to avoid errors. |
| 3 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | Character(s) identifying the end of a row. Default is Unix newline `\n`. Supports `\r\n`, `\r`, or custom separators. Determines how the component distinguishes between rows. |
| 4 | Ignore Empty Rows | `IGNORE_EMPTY_ROW` | Boolean (CHECK) | `false` | When checked, blank/empty rows are excluded from the count. An "empty row" is a line that is completely blank or contains only whitespace. |
| 5 | Encoding | `ENCODING` | Dropdown / Custom | `"ISO-8859-15"` | Character encoding for file reading. Options include ISO-8859-15, UTF-8, and custom values. **Note**: Talend default is `ISO-8859-15`, NOT `UTF-8`. |
| 6 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on error. When unchecked, errors are captured in `{id}_ERROR_MESSAGE` globalMap variable and the component completes without interrupting the job. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 7 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 8 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data rows. The component can receive rows from an upstream flow but does NOT produce a data flow output. It counts the rows in the specified file, not the input rows. |
| `REJECT` | Input | Row > Reject | Can accept reject rows from upstream. Not commonly used. |
| `ITERATE` | Input/Output | Row > Iterate | Enables iterative processing when combined with iteration components (e.g., `tFlowToIterate`, `tFileList`). |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Primary connection type for chaining to downstream components (e.g., `tJava` to read `{id}_COUNT`). |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronize execution with another subjob. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Parallelize execution with another subjob. |

**Important**: `tFileRowCount` does NOT produce a Row output (Main or Reject). It is a standalone component that stores its result in globalMap. Downstream components access the count via `globalMap.get("tFileRowCount_1_COUNT")` after connecting with a trigger (typically `OnSubjobOk`).

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_COUNT` | Integer | During execution (Flow) | **Primary output**. Total number of rows counted in the file. This is a Flow variable, meaning it is available during component execution. This is the key variable that makes this component useful -- downstream components read this value to make decisions. Access pattern: `((Integer)globalMap.get("tFileRowCount_1_COUNT"))`. |
| `{id}_NB_LINE` | Integer | After execution | Total number of rows read from the file (equivalent to `COUNT` but set after execution). This is the standard Talend stat variable. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully counted. Equals `NB_LINE` minus any rejected (empty) rows when `IGNORE_EMPTY_ROW=true`. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows excluded from the count (empty rows when `IGNORE_EMPTY_ROW=true`). Zero when `IGNORE_EMPTY_ROW=false`. |
| `{id}_ERROR_MESSAGE` | String | On error | Error description if any error occurred during execution. Only populated when `DIE_ON_ERROR=false`. Available for reference in downstream error handling flows. |

**Note on COUNT vs NB_LINE**: The `{id}_COUNT` variable is the **primary output** of this component and is a **Flow variable** (available during execution). The `{id}_NB_LINE` variable is a standard **After variable** (available after execution). In most Talend jobs, downstream components reference `{id}_COUNT` via `OnSubjobOk` triggers. Both should contain the same value, but `COUNT` is the canonical one for this component.

**Note on COUNT semantics**: When `IGNORE_EMPTY_ROW=true`, the `COUNT` variable reflects the count EXCLUDING empty rows. When `IGNORE_EMPTY_ROW=false` (default), `COUNT` reflects ALL rows including empty ones.

### 3.5 Behavioral Notes

1. **Standalone component**: `tFileRowCount` is designed as a standalone component. It does NOT produce a data flow output (no Main row output). The row count is communicated exclusively via the globalMap `{id}_COUNT` variable. Downstream components access this value after connecting with an `OnSubjobOk` trigger. This is fundamentally different from input components like `tFileInputDelimited`.

2. **Row separator behavior**: The `ROWSEPARATOR` parameter determines how the component identifies line boundaries. The default `\n` works for Unix/Linux files. Windows files with `\r\n` may need explicit configuration. Custom separators allow counting records in non-standard formats.

3. **Empty row definition**: When `IGNORE_EMPTY_ROW=true`, an "empty row" is a line that is blank or contains only whitespace characters. Lines containing only delimiters (e.g., `,,,,`) are NOT considered empty -- they are counted as data rows.

4. **Encoding sensitivity**: The file is read using the specified encoding. If the encoding does not match the file's actual encoding, a `UnicodeDecodeError` will occur. The component does NOT auto-detect encoding.

5. **Default encoding**: Talend defaults to `ISO-8859-15`, NOT `UTF-8`. This is a critical behavioral difference from most Python library defaults. If a Talend job does not explicitly set encoding, it uses `ISO-8859-15`.

6. **Header rows**: Unlike `tFileInputDelimited`, `tFileRowCount` has NO header skip parameter. ALL rows in the file are counted, including header rows. If you need to exclude headers from the count, subtract them from `{id}_COUNT` in downstream logic.

7. **Binary files**: `tFileRowCount` reads the file as text using the specified encoding. Binary files will cause encoding errors. This component is designed for text files only.

8. **Large files**: The component reads the file line by line, so memory usage is minimal regardless of file size. This is appropriate for counting rows in very large files.

9. **Die on error**: When `DIE_ON_ERROR=false` and an error occurs (file not found, permission denied, encoding error), the error message is stored in `{id}_ERROR_MESSAGE` and the job continues. When `DIE_ON_ERROR=true`, the entire job stops.

10. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. The `COUNT` variable, being a Flow variable, may be available during execution in some contexts. For most use cases via `OnSubjobOk`, both are available.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_tfile_row_count()` in `component_parser.py` lines 1706-1718) with a dedicated `elif` branch in `converter.py` line 294. This is the correct approach per STANDARDS.md.

**Converter flow**:
1. `converter.py:_parse_component()` matches `component_type == 'tFileRowCount'` (line 294)
2. Calls `self.component_parser.parse_tfile_row_count(node, component)` (line 295)
3. `parse_tfile_row_count()` extracts 4 parameters from `elementParameter` XML nodes
4. Returns component dict with mapped config keys

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filename` | 1710 | Extracted via `node.find('.//elementParameter[@name="FILENAME"]').get('value', '')`. No quote stripping. |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | 1712-1715 | Extracted with surrounding quote normalization: strips leading/trailing `"` if present. Default `'\n'`. |
| 3 | `IGNORE_EMPTY_ROW` | Yes | `ignore_empty_row` | 1716 | Boolean conversion via `.lower() == 'true'`. Default `false`. Correct. |
| 4 | `ENCODING` | Yes | `encoding` | 1717 | Extracted via `.get('value', 'UTF-8')`. **Default `'UTF-8'` differs from Talend default `'ISO-8859-15'`**. |
| 5 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted. Engine has no die_on_error handling.** |
| 6 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used). |
| 7 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact). |
| 8 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |

**Summary**: 4 of 6 runtime-relevant parameters extracted (67%). 1 runtime-relevant parameter missing (`DIE_ON_ERROR`).

### 4.2 Schema Extraction

`tFileRowCount` does NOT have an output schema in Talend. It is a standalone utility component that stores its result in globalMap. The converter does NOT extract any schema for this component, which is correct behavior.

### 4.3 Expression Handling

**FILENAME expression handling** (component_parser.py line 1710):
- The `FILENAME` value is extracted as-is from the XML attribute: `node.find('.//elementParameter[@name="FILENAME"]').get('value', '')`
- No context variable detection or Java expression marking is performed within the `parse_tfile_row_count()` method itself
- Context variables and Java expressions in FILENAME are handled by the generic mechanisms in `parse_base_component()` or `mark_java_expression()` that run after the specific parser
- The engine resolves `${context.var}` via `context_manager.resolve_dict()` in `BaseComponent.execute()` line 202 and `{{java}}` markers via `_resolve_java_expressions()` line 198

**Known limitations**:
- FILENAME may contain Java expressions (e.g., `context.inputDir + "/data.csv"`) that are not explicitly detected in the parser. These rely on the generic post-processing Java expression marking logic, which may or may not mark them correctly depending on the expression format.
- No validation that FILENAME resolves to a non-empty string before passing to the engine.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FRC-005 | **P0** | **Converter crashes with `AttributeError` on missing XML elements**: All 4 `.find(...).get(...)` calls at lines 1710-1717 have no null checks. If any `elementParameter` node is absent from the XML (e.g., `FILENAME`, `ROWSEPARATOR`, `IGNORE_EMPTY_ROW`, `ENCODING`), `.find()` returns `None` and the subsequent `.get('value', ...)` raises `AttributeError: 'NoneType' object has no attribute 'get'`. This crashes the entire conversion pipeline for any Talend job where the XML omits a parameter (which is valid -- Talend uses defaults for missing nodes). Every call should use a guard: `elem = node.find(...); value = elem.get('value', default) if elem is not None else default`. |
| CONV-FRC-001 | **P1** | **`DIE_ON_ERROR` not extracted**: The Talend `DIE_ON_ERROR` parameter is not parsed by `parse_tfile_row_count()`. The engine's `_process()` method has no `die_on_error` handling -- all errors are unconditionally raised (line 228-230). In Talend with `DIE_ON_ERROR=false`, errors should be captured in `{id}_ERROR_MESSAGE` and the job should continue. Without this parameter, any file error crashes the entire job regardless of the Talend configuration. |
| CONV-FRC-002 | **P2** | **Default encoding mismatch**: Converter defaults `ENCODING` to `'UTF-8'` (line 1717), but Talend default is `'ISO-8859-15'`. If a Talend job does not explicitly set encoding, the converter writes `'UTF-8'`, which differs from Talend behavior. This can cause `UnicodeDecodeError` on files containing non-ASCII characters encoded in ISO-8859-15. |
| CONV-FRC-006 | **P2** | **Encoding value retains surrounding quotes from XML**: Line 1717 does not strip quotes from the `ENCODING` value. Talend XML frequently stores encoding as `"\"UTF-8\""` (with embedded quotes), resulting in the converter producing `'"UTF-8"'` (a string with literal quote characters). Python's `open()` passes this to `codecs.lookup()`, which rejects `'"UTF-8"'` with `LookupError: unknown encoding: "UTF-8"`. The same quote-stripping logic applied to `ROWSEPARATOR` on lines 1713-1714 should be applied to `ENCODING`. |
| CONV-FRC-003 | **P3** | **FILENAME not stripped of quotes**: Line 1710 extracts FILENAME with `.get('value', '')` but does not strip surrounding quotes. While Talend XML typically stores values without quotes, some jobs may have quoted file paths (e.g., `""/path/to/file""`). Compare with `row_separator` on lines 1713-1714 which does strip quotes. Inconsistent handling. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Count rows in file | **Yes** | High | `_process()` lines 176-188 | Line-by-line reading with `open()`. Correct approach for counting. |
| 2 | Ignore empty rows | **Yes** | High | `_process()` line 185 | `if ignore_empty_row and not line.strip()` -- correct. Matches Talend behavior (blank/whitespace-only = empty). |
| 3 | Encoding support | **Yes** | Medium | `_process()` line 181 | Passed to `open()`. Default mismatch: engine defaults to UTF-8, Talend to ISO-8859-15. |
| 4 | File existence check | **Yes** | High | `_process()` line 169 | `os.path.exists(filename)` before reading. Raises `FileNotFoundError`. |
| 5 | GlobalMap `{id}_COUNT` | **Yes** | High | `_process()` lines 213, 216 | Stores `rows_out` with `count_key = f"{self.id}_COUNT"`. Legacy key format explicitly supported. |
| 6 | GlobalMap `{id}_NB_LINE` | **Yes** | High | `_process()` lines 212, 215 | Stores `rows_out` with `global_map_key = f"{self.id}_NB_LINE"`. |
| 7 | GlobalMap `{id}_NB_LINE_OK` | **Yes** | High | `_process()` line 219 | `self.global_map.put(f"{self.id}_NB_LINE_OK", rows_out)`. |
| 8 | GlobalMap `{id}_NB_LINE_REJECT` | **Yes** | High | `_process()` line 220 | `self.global_map.put(f"{self.id}_NB_LINE_REJECT", rows_rejected)`. Correctly counts empty rows as rejected. |
| 9 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()`. |
| 10 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers in config. |
| 11 | Component statistics | **Yes** | High | `_process()` line 207 | `self._update_stats(rows_in, rows_out, rows_rejected)`. Correct triple. |
| 12 | Permission error handling | **Yes** | High | `_process()` lines 190-192 | Catches `PermissionError` with descriptive message. |
| 13 | Encoding error handling | **Yes** | Medium | `_process()` lines 193-195 | Catches `UnicodeDecodeError`. But constructs a new `UnicodeDecodeError` instead of re-raising with context. |
| 14 | I/O error handling | **Yes** | High | `_process()` lines 196-198 | Catches `IOError` with descriptive message. |
| 15 | **Row separator** | **No** | N/A | -- | **`row_separator` is extracted by converter but NOT used in engine.** The docstring on line 9 explicitly states: "currently not implemented". The engine reads line-by-line using Python's default `\n` behavior via `for line in file:`, ignoring the configured row_separator. Custom separators (e.g., `\r`, multi-char) will produce incorrect counts. |
| 16 | **Die on error** | **No** | N/A | -- | **Not implemented.** The converter does not extract `DIE_ON_ERROR` and the engine has no handling. All errors unconditionally raise exceptions (line 228-230). In Talend with `DIE_ON_ERROR=false`, errors should populate `{id}_ERROR_MESSAGE` and allow the job to continue. |
| 17 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not implemented.** Error messages are logged but not stored in globalMap for downstream reference. This variable is critical for error handling flows in Talend. |
| 18 | **Return format: dict not DataFrame** | **Partial** | N/A | `_process()` line 226 | **Returns `{'main': {'row_count': row_count}}`** -- a nested dict with an integer value, not a DataFrame. While this is reasonable for a utility component that does not produce a data flow, it differs from the `BaseComponent._process()` contract which expects `'main': DataFrame`. Downstream components expecting a DataFrame will fail with `AttributeError`. See BUG-FRC-003. |
| 19 | **Header row awareness** | **No** | N/A | -- | **No header skip.** Talend's `tFileRowCount` counts ALL rows including headers. This matches the engine behavior (counts all lines). However, there is no parameter to subtract a known header row count, which some jobs may expect from a utility perspective. Not a bug per se, as Talend also counts headers. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FRC-001 | **P1** | **`row_separator` not implemented**: The engine extracts `row_separator` from config (line 162) but never uses it. Python's `for line in file:` uses the platform default line-ending behavior (splits on `\n`, `\r\n`, or `\r` due to universal newline mode). Files with custom row separators (e.g., `|`, `\x00`, multi-character) will produce incorrect counts. The module docstring explicitly acknowledges this: "currently not implemented". |
| ENG-FRC-002 | **P1** | **No `die_on_error` handling**: All errors unconditionally raise exceptions (`_process()` lines 228-230: bare `except Exception as e: raise`). In Talend with `DIE_ON_ERROR=false`, the component should capture the error in `{id}_ERROR_MESSAGE` and return gracefully. This means any file error (missing file, permission denied, encoding mismatch) crashes the entire job even if the Talend job was designed to handle errors gracefully. |
| ENG-FRC-003 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is logged (line 229) but NOT stored in globalMap. Downstream error handling components that reference `{id}_ERROR_MESSAGE` will get `None`. This variable is documented in Talend as a standard After variable for error reporting. |
| ENG-FRC-004 | **P2** | **Return format incompatible with BaseComponent contract**: `_process()` returns `{'main': {'row_count': row_count}}` (line 226) where `'main'` maps to a dict, not a DataFrame. The `BaseComponent._execute_streaming()` method (line 270) calls `chunk_result.get('main')` and tries to append it to a list for `pd.concat()`. If `FileRowCount` were ever run in streaming mode, `pd.concat()` would fail on a dict. The base class `execute()` also adds `result['stats']` (line 223) which works, but any downstream component expecting `result['main']` to be a DataFrame will crash. |
| ENG-FRC-005 | **P2** | **Default encoding differs from Talend**: Engine defaults to `UTF-8` (line 166: `self.config.get('ENCODING', 'UTF-8')`), but Talend defaults to `ISO-8859-15`. Files without explicit encoding in the Talend job will be read with the wrong encoding, potentially causing `UnicodeDecodeError` for non-ASCII characters encoded in ISO-8859-15. |
| ENG-FRC-006 | **P3** | **Universal newline mode silently changes count**: Python's `open()` in text mode uses universal newline translation by default. This means `\r\n` is translated to `\n`, and bare `\r` is also treated as a newline. While this provides broad compatibility, it means the `row_separator` config is doubly irrelevant -- not only is it not used, but Python's built-in behavior already handles the most common cases. For truly custom separators (non-newline characters), this behavior produces wrong counts. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_COUNT` | Yes (Flow) | **Yes** | `_process()` line 216: `self.global_map.put(count_key, rows_out)` | **Primary output.** Correctly set with legacy key format. However, `global_map.get()` on line 223 will CRASH due to BUG-FRC-001 (undefined `default` in `GlobalMap.get()`). |
| `{id}_NB_LINE` | Yes (After) | **Yes** | `_process()` line 215: `self.global_map.put(global_map_key, rows_out)` | Set correctly. Also set via `_update_global_map()` in base class (but that call will crash -- see BUG-FRC-001). |
| `{id}_NB_LINE_OK` | Yes (After) | **Yes** | `_process()` line 219 | Set correctly. Excludes empty rows when `ignore_empty_row=true`. |
| `{id}_NB_LINE_REJECT` | Yes (After) | **Yes** | `_process()` line 220 | Set correctly. Counts empty rows as rejected when `ignore_empty_row=true`. |
| `{id}_ERROR_MESSAGE` | Yes (After) | **No** | -- | Not implemented. Error messages logged but not stored in globalMap. |

**Critical note on double-write and crash**: The component manually writes GlobalMap variables in `_process()` (lines 215-220), AND the base class `execute()` calls `_update_global_map()` (line 218 of `base_component.py`) which ALSO writes stats to GlobalMap via `put_component_stat()`. The `_update_global_map()` call will crash due to BUG-FRC-001 (undefined `value` variable on line 304 of `base_component.py`). If the crash is fixed, the manual writes in `_process()` would be partially redundant with the base class writes. However, the `{id}_COUNT` key is component-specific and would NOT be written by the base class, so the manual write is necessary for that key.

**Critical note on GlobalMap.get() crash**: Line 223 of `file_row_count.py` calls `self.global_map.get(count_key)` for verification. This call will crash because `GlobalMap.get()` (line 28 of `global_map.py`) references an undefined `default` parameter. See BUG-FRC-002.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FRC-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileRowCount, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The component's manual GlobalMap writes in `_process()` lines 210-223 happen BEFORE this crash, so the values ARE written. But the crash in `_update_global_map()` will propagate up through `execute()` and abort the component with an error, overwriting the SUCCESS status. |
| BUG-FRC-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. **SPECIFIC IMPACT on FileRowCount**: Line 223 of `file_row_count.py` calls `self.global_map.get(count_key)` to verify the stored value. This call WILL crash with `NameError: name 'default' is not defined`. |
| BUG-FRC-003 | **P1** | `src/v1/engine/components/file/file_row_count.py:226` | **Return format is dict, not DataFrame**: `_process()` returns `{'main': {'row_count': row_count}}` where `'main'` maps to a plain Python dict containing the integer row count. The `BaseComponent._process()` abstract method contract (line 286-296 of `base_component.py`) documents that `'main'` should be a DataFrame. If `FileRowCount` is ever used in streaming mode, `_execute_streaming()` (line 270-271 of `base_component.py`) calls `results.append(chunk_result['main'])` and later `pd.concat(results)`, which will fail with `TypeError: cannot concatenate object of type '<class 'dict'>'`. While FileRowCount is typically a standalone component and batch mode works, the contract violation creates fragility. |
| BUG-FRC-004 | **P1** | `src/v1/engine/components/file/file_row_count.py:88-136` | **`_validate_config()` is never called**: The method exists and contains 49 lines of validation logic (filename required, encoding valid, boolean type checks), but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (missing filename, invalid encoding, wrong types) are not caught until they cause runtime errors deep in processing. |
| BUG-FRC-005 | **P1** | `src/v1/engine/components/file/file_row_count.py:88` | **`_validate_config()` returns `bool` instead of `List[str]`**: The method signature is `def _validate_config(self) -> bool` (line 88), returning `True`/`False`. The METHODOLOGY.md standard specifies that `_validate_config()` should return `List[str]` (a list of error message strings). This is a contract violation that makes it impossible to aggregate validation errors. Other components (e.g., `FileInputDelimited`) also have this issue. Even if a caller were added, the caller would need to know to check a boolean rather than iterate error strings. |
| BUG-FRC-006 | **P1** | `src/v1/engine/components/file/file_row_count.py:162` | **`row_separator` extracted but never used**: The `_process()` method extracts `row_separator` from config on line 162 but never passes it to the file reading logic. The `open()` call on line 181 uses Python's default text mode (universal newline). The extracted variable is dead code, creating a false impression that custom row separators work. The module docstring explicitly acknowledges this on line 9: "currently not implemented". |
| BUG-FRC-008 | **P1** | `src/v1/engine/base_component.py:218,231` | **`_update_global_map()` double-crash on error path**: Line 218 calls `_update_global_map()` which crashes due to BUG-FRC-001 (undefined `value` variable). The `except` handler on line 231 attempts to call `_update_global_map()` again to record the error state, which crashes a second time with the same `NameError`. The original exception (the real processing failure) is masked by the `NameError` from the second `_update_global_map()` call. This means: (a) error diagnostics are lost, (b) the component's error status is never properly recorded in GlobalMap, and (c) the traceback shown to the user points to the GlobalMap logging code rather than the actual failure site. |
| BUG-FRC-007 | **P2** | `src/v1/engine/components/file/file_row_count.py:193-195` | **`UnicodeDecodeError` re-raised with synthetic arguments**: When a `UnicodeDecodeError` occurs, the handler constructs a new `UnicodeDecodeError(encoding, b'', 0, 1, f"Cannot decode file {filename} with encoding {encoding}")` instead of re-raising the original exception. The original exception contains the exact byte offset, the problematic byte sequence, and the actual error reason. The synthetic exception loses all this diagnostic information, replacing it with dummy values (`b''`, `0`, `1`). This makes debugging encoding issues significantly harder. Should use `raise` to re-raise original, or `raise ... from e` with a wrapper exception. |
| BUG-FRC-010 | **P2** | `src/v1/engine/components/file/file_row_count.py:169` | **Empty filename and missing file share the same error path**: `if not filename or not os.path.exists(filename):` on line 169 raises `FileNotFoundError` for both cases. An empty/None filename should raise `ConfigurationError` (missing required parameter), while a non-existent file should raise `FileNotFoundError` or `FileOperationError`. Conflating these two distinct error conditions makes it harder to diagnose issues. An empty filename says "configuration is wrong"; a missing file says "the file path is valid but the file isn't there". |
| BUG-FRC-011 | **P2** | `src/v1/engine/components/file/file_row_count.py:210-224` | **GlobalMap operations inside try block with catch-all**: The GlobalMap writes (lines 210-224) are inside the main `try` block (line 159). If `global_map.get()` crashes (due to BUG-FRC-002), the exception is caught by the `except Exception as e:` on line 228, logged, and re-raised. This means the GlobalMap verification crash looks like a component processing error, masking the actual successful count operation. The GlobalMap writes should be outside the main try/except or in a separate try/except. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FRC-001 | **P2** | **Dual key format support in config**: `_process()` supports both `filename` (snake_case) and `FILENAME` (UPPER_CASE) via `self.config.get('filename') or self.config.get('FILENAME', '')` (line 161). This OR pattern has a subtle bug: if `filename` is set to an empty string `''`, it is falsy, so the code falls through to `FILENAME`. This means an intentionally empty `filename` key would silently be overridden by `FILENAME`. The `or` operator should be replaced with explicit `None` checking: `filename = self.config.get('filename') if 'filename' in self.config else self.config.get('FILENAME', '')`. |
| NAME-FRC-002 | **P2** | **Same dual-key issue for all config parameters**: Lines 162-166 use the same `or` pattern for `row_separator`, `encoding`. The `ignore_empty_row` parameter (lines 163-165) uses a different pattern with explicit `None` check, which is correct. Inconsistent handling across parameters in the same method. |
| NAME-FRC-003 | **P3** | **Config key `filename` vs `filepath`**: Other file components (e.g., `FileInputDelimited`) use `filepath` as the config key. `FileRowCount` uses `filename`. This inconsistency means job JSON configs need different key names for different file components. Talend XML uses `FILENAME` for both. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FRC-001 | **P1** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method returns `bool` instead of `List[str]`. Contract violation even if the method were called. Callers expecting a list of error strings will get `True`/`False`. |
| STD-FRC-002 | **P1** | "`_validate_config()` must be called before `_process()`" (METHODOLOGY.md) | Method is never called by any code path. Dead code. 49 lines of validation logic that never executes. |
| STD-FRC-003 | **P2** | "`_process()` returns `Dict[str, Any]` with `'main': DataFrame`" (base_component.py) | Returns `{'main': {'row_count': int}}` -- dict instead of DataFrame. While reasonable for utility components, violates the documented contract and breaks streaming mode. |
| STD-FRC-004 | **P3** | "Consistent config key naming across components" | Uses `filename` while other file components use `filepath`. No documented standard for which to prefer. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FRC-001 | **P3** | **Verification read in production code**: Lines 222-224 perform a `global_map.get(count_key)` solely for debug logging: `self.logger.debug(f"[{self.id}] Stored row count {stored_value} in GlobalMap with key: {count_key}")`. This is a debug artifact that (a) will crash due to BUG-FRC-002, (b) adds unnecessary overhead in production, and (c) the `stored_value` is guaranteed to be `rows_out` since the `put()` was just called on line 216. Should be removed or guarded behind a debug flag. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FRC-001 | **P3** | **No path traversal protection**: `filename` from config is used directly with `os.path.exists()` and `open()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.6 Logging Quality

The component has good logging coverage, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` AND instance-level `self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")` -- slightly redundant but functional |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones (start/complete), DEBUG for details (config validation, stored values), ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 173); logs completion with row counts (line 204) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| Error logging | Errors logged before re-raising (lines 191, 194, 197, 229) -- correct |

**Minor issue**: The component creates BOTH a module-level `logger` (line 35) and an instance-level `self.logger` (line 86). The module-level `logger` is never used within the class -- all class methods use `self.logger`. The module-level logger is dead code within this module. This is not a bug but clutters the namespace.

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions from `exceptions.py`. Uses built-in `FileNotFoundError`, `PermissionError`, `UnicodeDecodeError`, `IOError`. Should use `FileOperationError` and `ConfigurationError` for consistency with the exception hierarchy. |
| Exception chaining | Uses `raise ... from e` pattern for specific exceptions (lines 192, 195, 198) -- correct pattern but synthetic `UnicodeDecodeError` loses information. |
| `die_on_error` handling | **Not implemented**. All errors unconditionally raised. |
| No bare `except` | All except clauses specify exception types... except the catch-all on line 228 which catches `Exception`. This is acceptable for a top-level handler. |
| Error messages | Include component ID and file path -- correct |
| Graceful degradation | **Not implemented**. No code path returns a graceful result on error. All errors propagate up. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> bool` (should be `List[str]`), `_process(...) -> Dict[str, Any]` -- present |
| Parameter types | `_process(self, input_data: Optional[Dict[str, Any]] = None)` -- correct, uses `Dict` since this component doesn't receive DataFrame input |
| Complex types | Uses `Dict[str, Any]`, `Optional` from typing -- correct |
| Missing hints | `__init__` parameters pass through `*args, **kwargs` without type hints -- acceptable for passthrough |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FRC-001 | **P2** | **Line-by-line reading is correct but not optimal for pure counting**: The component reads each line as a Python string object (`for line in file:`), creates a string object for each line, and then checks `line.strip()` if `ignore_empty_row=true`. For pure line counting without empty row filtering, a more efficient approach would be to count newline bytes directly: `sum(1 for _ in file)` or even `buf = file.read(BUFSIZE); count += buf.count('\n')`. For files with millions of lines, the string creation and strip() overhead is measurable. However, the current approach is correct and memory-efficient (O(1) memory regardless of file size), so this is a minor optimization. |
| PERF-FRC-002 | **P3** | **Debug GlobalMap verification read**: Line 223 performs an unnecessary `global_map.get()` call after every `put()`. While the overhead is minimal (dict lookup), it serves no purpose beyond debug logging and will crash due to BUG-FRC-002. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Line-by-line reading | Uses `for line in file:` which reads one line at a time. Memory usage is O(1) regardless of file size. Correct for a counting component. |
| No DataFrame creation | Component does not create a DataFrame from file contents. Returns a simple dict. Memory-efficient. |
| No buffering issues | Python's built-in `open()` uses buffered I/O by default. No additional buffering needed. |
| Large file support | Can handle files of any size since it reads line-by-line. No memory threshold or streaming mode needed. |

### 7.2 Streaming Mode Considerations

`FileRowCount` returns a dict, not a DataFrame. If `execute()` routes to `_execute_streaming()` (base class), the streaming logic (lines 267-278 of `base_component.py`) expects `_process()` to return a DataFrame in `result['main']`. The dict return will cause `pd.concat()` to fail.

In practice, `FileRowCount` processes files directly (input_data is None), so `_auto_select_mode()` returns BATCH (line 238-239 of `base_component.py`: `if input_data is None: return ExecutionMode.BATCH`). Streaming mode is never triggered for this component. But the contract violation remains a latent issue.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileRowCount` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tfile_row_count()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 229 lines of v1 engine code and 13 lines of converter code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic row count | P0 | Count rows in a simple multi-line text file. Verify `row_count` matches expected value and `{id}_COUNT` is set in globalMap. |
| 2 | Empty file | P0 | Count rows in an empty file. Should return `row_count=0` without error, stats (0, 0, 0). |
| 3 | Ignore empty rows | P0 | File with 10 rows including 3 blank lines. With `ignore_empty_row=true`, verify `row_count=7`, `NB_LINE_REJECT=3`. |
| 4 | Missing file | P0 | Should raise `FileNotFoundError` with descriptive message including the file path. |
| 5 | GlobalMap integration | P0 | Verify `{id}_COUNT`, `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` are all set correctly in globalMap after execution. |
| 6 | Statistics tracking | P0 | Verify `stats['NB_LINE']`, `stats['NB_LINE_OK']`, `stats['NB_LINE_REJECT']` are set correctly after execution. |
| 7 | Single-line file (no trailing newline) | P0 | File with `"hello"` (no newline). Should count 1 row. Python `for line in file:` handles this correctly. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Windows line endings | P1 | File with `\r\n` line endings. Verify correct count. Python's universal newline mode should handle this. |
| 9 | Encoding ISO-8859-15 | P1 | File with non-UTF8 characters encoded in ISO-8859-15. Verify correct count without encoding errors when `encoding='ISO-8859-15'`. |
| 10 | Encoding mismatch | P1 | Read a UTF-8 file with `encoding='ascii'` for a file with non-ASCII chars. Should raise `UnicodeDecodeError`. |
| 11 | Permission denied | P1 | Read a file with no read permissions. Should raise `PermissionError`. |
| 12 | Context variable in filename | P1 | `${context.input_dir}/file.txt` should resolve via context manager to correct path. |
| 13 | Ignore empty rows with whitespace-only lines | P1 | Lines containing only spaces/tabs should be treated as empty when `ignore_empty_row=true`. Verify `line.strip()` check. |
| 14 | Large file (1M+ lines) | P1 | Verify correct count for a file with 1 million lines. Verify O(1) memory usage (no OOM). |
| 15 | Return format verification | P1 | Verify `_process()` returns `{'main': {'row_count': int}}` and that the integer is correct. |
| 16 | Die on error = false (when implemented) | P1 | With `die_on_error=false`, missing file should set `{id}_ERROR_MESSAGE` in globalMap and return gracefully instead of raising. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Binary file | P2 | Attempt to count rows in a binary file (e.g., .zip). Should raise appropriate error. |
| 18 | File with BOM | P2 | UTF-8 file with BOM. Verify count is correct and BOM does not create an extra empty line. |
| 19 | Empty filename in config | P2 | `filename=''` should raise `FileNotFoundError` (or ideally `ConfigurationError`). Verify error message. |
| 20 | None filename in config | P2 | `filename=None` or missing key. Should raise appropriate error. |
| 21 | File path with spaces | P2 | Verify files with spaces in path are counted correctly. |
| 22 | Concurrent counting | P2 | Multiple `FileRowCount` instances counting different files simultaneously. Verify no interference. |
| 23 | File with only empty lines | P2 | File with 5 blank lines. With `ignore_empty_row=true`: `row_count=0`, `NB_LINE_REJECT=5`. With `ignore_empty_row=false`: `row_count=5`. |
| 24 | Mixed line endings | P2 | File with mix of `\n`, `\r\n`, and `\r` endings. Verify Python's universal newline handles all correctly. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| CONV-FRC-005 | Converter | Converter crashes with `AttributeError` on missing XML elements. All 4 `.find(...).get(...)` calls at lines 1710-1717 have no null checks. If any `elementParameter` is absent from the Talend XML, `.find()` returns `None` and `.get()` raises `AttributeError`. Crashes the entire conversion pipeline. |
| BUG-FRC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. For FileRowCount, the manual GlobalMap writes happen before this crash, so values ARE written, but the exception propagates and aborts the component. |
| BUG-FRC-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. **Direct FileRowCount impact**: Line 223 of `file_row_count.py` calls `self.global_map.get(count_key)` which will crash. |
| TEST-FRC-001 | Testing | Zero v1 unit tests for this component. All 229 lines of v1 engine code and 13 lines of converter code are completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FRC-001 | Converter | `DIE_ON_ERROR` not extracted -- engine cannot differentiate between die-on-error and graceful-error modes. All errors unconditionally crash the job. |
| ENG-FRC-001 | Engine | `row_separator` not implemented -- config parameter extracted but never used. Files with custom row separators produce incorrect counts. Module docstring explicitly acknowledges this gap. |
| ENG-FRC-002 | Engine | No `die_on_error` handling -- all errors unconditionally raised. Jobs designed to handle row count errors gracefully will crash. |
| ENG-FRC-003 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap -- error details not available for downstream error handling flows. |
| BUG-FRC-003 | Bug | Return format is dict not DataFrame -- violates `BaseComponent._process()` contract. Will crash in streaming mode. |
| BUG-FRC-004 | Bug | `_validate_config()` is dead code -- never called by any code path. 49 lines of unreachable validation. |
| BUG-FRC-005 | Bug | `_validate_config()` returns `bool` instead of `List[str]` -- violates METHODOLOGY.md contract. |
| BUG-FRC-006 | Bug | `row_separator` extracted but never used -- dead variable creates false impression of support. |
| BUG-FRC-008 | Bug (Cross-Cutting) | `_update_global_map()` double-crash on error path. Line 218 crashes, except handler on line 231 crashes again. Original exception masked by `NameError`. Error diagnostics lost and component error status never recorded in GlobalMap. |
| STD-FRC-001 | Standards | `_validate_config()` return type violates METHODOLOGY.md (bool instead of List[str]). |
| STD-FRC-002 | Standards | `_validate_config()` never called -- dead validation code. |
| TEST-FRC-002 | Testing | No integration test for this component in a multi-step v1 job (e.g., `tFileRowCount -> tJava` via OnSubjobOk). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FRC-002 | Converter | Default encoding mismatch: converter defaults to `UTF-8`, Talend defaults to `ISO-8859-15`. |
| CONV-FRC-006 | Converter | Encoding value retains surrounding quotes from XML. Line 1717 doesn't strip quotes. `open()` rejects `'"UTF-8"'` with `LookupError`. |
| ENG-FRC-004 | Engine | Return format `{'main': dict}` incompatible with `BaseComponent` contract expecting `{'main': DataFrame}`. Breaks streaming mode. |
| ENG-FRC-005 | Engine | Default encoding differs from Talend (`UTF-8` vs `ISO-8859-15`). Files without explicit encoding will use wrong encoding. |
| BUG-FRC-007 | Bug | `UnicodeDecodeError` re-raised with synthetic arguments -- loses original byte offset and error details. |
| BUG-FRC-010 | Bug | Empty filename and missing file share same `FileNotFoundError` -- should be `ConfigurationError` for empty filename. |
| BUG-FRC-011 | Bug | GlobalMap operations inside try block -- GlobalMap crash (BUG-FRC-002) looks like processing error, masking successful count. |
| NAME-FRC-001 | Naming | Dual `or` pattern for config keys has subtle bug when value is empty string (falsy). |
| NAME-FRC-002 | Naming | Inconsistent dual-key handling across config parameters within same method. |
| STD-FRC-003 | Standards | `_process()` returns dict instead of DataFrame in `'main'` key -- contract violation. |
| PERF-FRC-001 | Performance | Line-by-line reading creates string objects; pure byte counting would be faster for non-empty-row-filtering cases. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FRC-003 | Converter | FILENAME not stripped of quotes (inconsistent with ROWSEPARATOR handling). |
| ENG-FRC-006 | Engine | Universal newline mode silently handles most separators but custom non-newline separators still fail. |
| NAME-FRC-003 | Naming | Config key `filename` inconsistent with other file components that use `filepath`. |
| STD-FRC-004 | Standards | Inconsistent config key naming across components (`filename` vs `filepath`). |
| SEC-FRC-001 | Security | No path traversal protection on filename. Low risk for Talend-converted jobs. |
| DBG-FRC-001 | Debug | Verification `global_map.get()` on line 223 is debug artifact that will crash in production. |
| PERF-FRC-002 | Performance | Debug GlobalMap verification read adds unnecessary overhead and will crash. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 1 converter, 2 bugs (cross-cutting), 1 testing |
| P1 | 12 | 1 converter, 3 engine, 5 bugs, 2 standards, 1 testing |
| P2 | 11 | 2 converter, 2 engine, 3 bugs, 2 naming, 1 standards, 1 performance |
| P3 | 7 | 1 converter, 1 engine, 1 naming, 1 standards, 1 security, 1 debug, 1 performance |
| **Total** | **34** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FRC-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FRC-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FRC-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic row count, empty file, ignore empty rows, missing file, GlobalMap integration, statistics tracking, and single-line file. Without these, no v1 engine behavior is verified.

4. **Remove debug GlobalMap.get() call** (DBG-FRC-001): Remove lines 222-224 of `file_row_count.py`. The `global_map.get(count_key)` call will crash due to BUG-FRC-002 and serves no purpose beyond debug logging. The `put()` on line 216 is guaranteed to succeed. If verification logging is needed, log the value before putting it rather than reading it back.

### Short-Term (Hardening)

5. **Extract and implement `DIE_ON_ERROR`** (CONV-FRC-001, ENG-FRC-002): Add `die_on_error` extraction to `parse_tfile_row_count()`:
   ```python
   component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
   ```
   In the engine `_process()`, wrap the main logic in a try/except that:
   - When `die_on_error=True`: re-raises the exception (current behavior)
   - When `die_on_error=False`: stores error in `{id}_ERROR_MESSAGE` globalMap variable, returns `{'main': {'row_count': 0}}`, and continues without crashing

6. **Implement `row_separator`** (ENG-FRC-001, BUG-FRC-006): Replace line-by-line reading with custom separator-aware counting:
   ```python
   if row_separator == '\n':
       # Use default Python line iteration (handles \n, \r\n, \r)
       for line in file:
           ...
   else:
       # Custom separator: read in chunks and count separator occurrences
       content = file.read()
       lines = content.split(row_separator)
       ...
   ```
   This preserves the current efficient behavior for the default case while adding support for custom separators.

7. **Implement `{id}_ERROR_MESSAGE` globalMap** (ENG-FRC-003): In error handlers within `_process()`, add:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```

8. **Wire up `_validate_config()` and fix return type** (BUG-FRC-004, BUG-FRC-005, STD-FRC-001, STD-FRC-002): Change `_validate_config()` to return `List[str]` (list of error messages). Add a call at the beginning of `_process()`:
   ```python
   errors = self._validate_config()
   if errors:
       error_msg = '; '.join(errors)
       if die_on_error:
           raise ConfigurationError(error_msg)
       else:
           self.logger.error(f"[{self.id}] Configuration errors: {error_msg}")
           if self.global_map:
               self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)
           return {'main': {'row_count': 0}}
   ```

9. **Fix default encoding to match Talend** (CONV-FRC-002, ENG-FRC-005): Change the default encoding in the converter (line 1717 of `component_parser.py`) from `'UTF-8'` to `'ISO-8859-15'`, and in the engine (line 166 of `file_row_count.py`) from `'UTF-8'` to `'ISO-8859-15'`.

10. **Separate empty filename from missing file** (BUG-FRC-010): Split the validation on line 169:
    ```python
    if not filename:
        raise ConfigurationError(f"[{self.id}] filename is required but not provided")
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")
    ```

### Long-Term (Optimization)

11. **Fix UnicodeDecodeError handling** (BUG-FRC-007): Replace the synthetic `UnicodeDecodeError` construction with either a re-raise or a proper wrapper:
    ```python
    except UnicodeDecodeError as e:
        self.logger.error(f"[{self.id}] Encoding error reading file {filename} with encoding {encoding}: {e}")
        raise FileOperationError(f"Cannot decode file {filename} with encoding {encoding}: {e}") from e
    ```

12. **Fix dual-key config pattern** (NAME-FRC-001, NAME-FRC-002): Replace `or` pattern with explicit key checking:
    ```python
    filename = self.config.get('filename') if 'filename' in self.config else self.config.get('FILENAME', '')
    ```
    Or better, standardize on one key format in the converter and remove legacy support.

13. **Use custom exceptions** (Error Handling): Replace built-in `FileNotFoundError`, `PermissionError`, `IOError` with `FileOperationError` and `ConfigurationError` from `exceptions.py` for consistency with the exception hierarchy.

14. **Optimize pure counting** (PERF-FRC-001): When `ignore_empty_row=false`, use a more efficient counting method:
    ```python
    if not ignore_empty_row:
        rows_out = sum(1 for _ in file)
    ```
    This avoids creating string objects for each line.

15. **Standardize config key naming** (NAME-FRC-003, STD-FRC-004): Align `filename` with other file components' `filepath` key, or document the intentional difference. Update converter accordingly.

16. **Create integration test** (TEST-FRC-002): Build an end-to-end test exercising `tFileRowCount -> tJava` (via OnSubjobOk trigger) in the v1 engine, verifying GlobalMap propagation of `{id}_COUNT` to the downstream component.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1706-1718
def parse_tfile_row_count(self, node, component: Dict) -> Dict:
    """
    Parse tFileRowCount specific configuration.
    """
    component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    # Normalize ROWSEPARATOR to remove surrounding quotes if present
    row_separator = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
    if row_separator.startswith('"') and row_separator.endswith('"'):
        row_separator = row_separator[1:-1]
    component['config']['row_separator'] = row_separator
    component['config']['ignore_empty_row'] = node.find('.//elementParameter[@name="IGNORE_EMPTY_ROW"]').get('value', 'false').lower() == 'true'
    component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    return component
```

**Notes on this code**:
- Line 1710: FILENAME extracted as-is. No quote stripping (unlike ROWSEPARATOR on lines 1713-1714). Inconsistent.
- Line 1712-1715: ROWSEPARATOR has explicit quote stripping logic. Handles Talend XML storing `"\"\n\""` for a newline separator.
- Line 1716: `IGNORE_EMPTY_ROW` boolean conversion is correct. Default `'false'` matches Talend.
- Line 1717: Default encoding `'UTF-8'` differs from Talend default `'ISO-8859-15'`.
- **Missing**: `DIE_ON_ERROR` not extracted. `TSTATCATCHER_STATS` not extracted (low priority).

---

## Appendix B: Engine Class Structure

```
FileRowCount (BaseComponent)
    Constants:
        (none)

    Instance Variables:
        self.logger  -- instance-level logger (redundant with module-level)

    Methods:
        __init__(*args, **kwargs)                    # Passthrough to BaseComponent, adds instance logger
        _validate_config() -> bool                   # DEAD CODE -- never called. Returns bool (contract violation)
        _process(input_data) -> Dict[str, Any]       # Main entry point. Returns {'main': {'row_count': int}}

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]        # Main execution with mode handling and stats
        _update_global_map() -> None                 # BUGGY -- crashes due to undefined 'value'
        _update_stats(rows_read, rows_ok, rows_reject)  # Helper to update statistics
        validate_schema(df, schema) -> DataFrame     # Not used by FileRowCount (no DataFrame output)
        _resolve_java_expressions() -> None          # Resolves {{java}} markers in config
        _auto_select_mode(input_data) -> ExecutionMode   # Returns BATCH when input_data is None
        _execute_batch(input_data) -> Dict           # Calls _process()
        _execute_streaming(input_data) -> Dict       # Would fail on dict return from _process()
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filename` | Mapped | -- |
| `ROWSEPARATOR` | `row_separator` | Mapped (but unused in engine) | Engine implementation needed (P1) |
| `IGNORE_EMPTY_ROW` | `ignore_empty_row` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped (wrong default) | Fix default (P2) |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: GlobalMap Key Format Comparison

### Talend GlobalMap Variables

| Variable | Access Pattern | Type | Scope |
|----------|---------------|------|-------|
| `{id}_COUNT` | `((Integer)globalMap.get("tFileRowCount_1_COUNT"))` | Integer | Flow (during execution) |
| `{id}_ERROR_MESSAGE` | `((String)globalMap.get("tFileRowCount_1_ERROR_MESSAGE"))` | String | After (post-execution) |

### V1 Engine GlobalMap Variables

| Variable | Set By | Line | Notes |
|----------|--------|------|-------|
| `{id}_NB_LINE` | `_process()` | 215 | Manual put. Also written by `_update_global_map()` (if it doesn't crash). |
| `{id}_COUNT` | `_process()` | 216 | Manual put. **Legacy key format.** This is the primary output for Talend compatibility. |
| `{id}_NB_LINE_OK` | `_process()` | 219 | Manual put. |
| `{id}_NB_LINE_REJECT` | `_process()` | 220 | Manual put. |
| `{id}_NB_LINE` | `_update_global_map()` | base_component.py:302 | Via `put_component_stat()`. Duplicates the manual write. Will crash (BUG-FRC-001). |
| `{id}_NB_LINE_OK` | `_update_global_map()` | base_component.py:302 | Via `put_component_stat()`. Duplicates the manual write. Will crash. |
| `{id}_NB_LINE_REJECT` | `_update_global_map()` | base_component.py:302 | Via `put_component_stat()`. Duplicates the manual write. Will crash. |
| `{id}_EXECUTION_TIME` | `_update_global_map()` | base_component.py:302 | V1-specific. Will crash. |
| `{id}_NB_LINE_INSERT` | `_update_global_map()` | base_component.py:302 | Always 0 for this component. Will crash. |
| `{id}_NB_LINE_UPDATE` | `_update_global_map()` | base_component.py:302 | Always 0 for this component. Will crash. |
| `{id}_NB_LINE_DELETE` | `_update_global_map()` | base_component.py:302 | Always 0 for this component. Will crash. |
| `{id}_ERROR_MESSAGE` | -- | -- | **NOT SET.** Missing. |

**Key observation**: The component manually writes 4 GlobalMap variables in `_process()` (lines 215-220), THEN the base class `execute()` attempts to write 7 more via `_update_global_map()` (which crashes). The manual writes succeed before the crash, so `{id}_COUNT`, `{id}_NB_LINE`, `{id}_NB_LINE_OK`, and `{id}_NB_LINE_REJECT` ARE available in GlobalMap after the crash is caught. However, the crash propagates through `execute()` and the component status is set to ERROR (line 228 of `base_component.py`), which means the job may not continue to downstream components that need these values.

---

## Appendix E: Detailed Code Analysis

### `__init__()` (Lines 76-86)

Simple passthrough to `BaseComponent.__init__()` via `*args, **kwargs`. Creates an instance-level logger using `logging.getLogger(f"{__name__}.{self.__class__.__name__}")`. This logger uses a more specific name than the module-level logger (includes class name), which is useful for log filtering. The module-level `logger` on line 35 is never used within the class.

### `_validate_config()` (Lines 88-136)

This method validates three aspects:
1. **filename**: Required, must be a string. Supports both `filename` (snake_case) and `FILENAME` (UPPER_CASE) keys.
2. **encoding**: Optional, if provided must be a valid Python encoding (tested via `''.encode(encoding)`).
3. **ignore_empty_row**: Optional, must be boolean. Supports both `ignore_empty_row` and `IGNORE_EMPTY_ROW` keys.

**Not validated**: `row_separator` (not checked at all), `die_on_error` (not extracted).

**Critical issues**:
- Returns `bool` instead of `List[str]` (contract violation).
- Never called by any code path (dead code).
- The `or` pattern for dual-key support has the same falsy-value bug described in NAME-FRC-001.
- Logs errors at `self.logger.error()` level but also logs validation result at `self.logger.debug()` level (lines 132-134). If the method were called, error-level logs would appear even for non-critical issues.

### `_process()` (Lines 138-230)

The main processing method:
1. Extract config values with defaults (lines 161-166). Dual key support for snake_case and UPPER_CASE.
2. Validate file existence (line 169). Combined empty-filename and missing-file check.
3. Log start (line 173).
4. Count rows line-by-line (lines 180-188):
   - Open file with specified encoding
   - Iterate lines, incrementing `rows_in` for each
   - If `ignore_empty_row` and line is blank after strip, increment `rows_rejected` and skip
   - Otherwise increment `rows_out`
5. Handle specific exceptions: `PermissionError`, `UnicodeDecodeError`, `IOError` (lines 190-198).
6. Log completion with row counts (line 204).
7. Update component statistics (line 207).
8. Store values in GlobalMap with both `{id}_NB_LINE` and `{id}_COUNT` keys (lines 210-224).
9. Return result dict (line 226).
10. Catch-all exception handler (lines 228-230): log and re-raise.

**Flow of execution**:
```
execute() [base_component.py]
  -> _resolve_java_expressions()     [if java_bridge set]
  -> context_manager.resolve_dict()  [if context_manager set]
  -> _auto_select_mode() -> BATCH    [input_data is None]
  -> _execute_batch(None)
     -> _process(None)
        -> extract config
        -> validate file exists
        -> count lines
        -> update stats
        -> write GlobalMap
        -> return {'main': {'row_count': N}}
  -> _update_global_map()            [CRASHES - BUG-FRC-001]
```

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty file

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns COUNT=0, NB_LINE=0. No error. |
| **V1** | `for line in file:` loop executes zero times. `rows_in=0`, `rows_out=0`. Returns `{'main': {'row_count': 0}}`. |
| **Verdict** | CORRECT |

### Edge Case 2: File with single line, no trailing newline

| Aspect | Detail |
|--------|--------|
| **Talend** | COUNT=1. The line is counted even without a trailing newline. |
| **V1** | Python's `for line in file:` yields the last line even without `\n`. `rows_in=1`, `rows_out=1`. |
| **Verdict** | CORRECT |

### Edge Case 3: File with only empty lines

| Aspect | Detail |
|--------|--------|
| **Talend** | With `IGNORE_EMPTY_ROW=true`: COUNT=0. With `IGNORE_EMPTY_ROW=false`: COUNT=N (where N is number of blank lines). |
| **V1** | With `ignore_empty_row=true`: `line.strip()` returns `''` (falsy) for blank lines. `rows_out=0`, `rows_rejected=N`. With `ignore_empty_row=false`: all lines counted. `rows_out=N`. |
| **Verdict** | CORRECT |

### Edge Case 4: Windows line endings (`\r\n`)

| Aspect | Detail |
|--------|--------|
| **Talend** | With `ROWSEPARATOR="\r\n"`: counts correctly. |
| **V1** | Python's universal newline mode in `open()` text mode translates `\r\n` to `\n`. Each line is yielded correctly. Count is correct. |
| **Verdict** | CORRECT (via Python's universal newline, not via row_separator implementation) |

### Edge Case 5: Mac classic line endings (`\r` only)

| Aspect | Detail |
|--------|--------|
| **Talend** | With `ROWSEPARATOR="\r"`: counts correctly. |
| **V1** | Python's universal newline mode treats `\r` as a line ending. Each line yielded correctly. |
| **Verdict** | CORRECT (via Python's universal newline, not via row_separator implementation) |

### Edge Case 6: Custom non-newline row separator (e.g., `|`)

| Aspect | Detail |
|--------|--------|
| **Talend** | With `ROWSEPARATOR="|"`: splits file on `|` characters and counts resulting segments. |
| **V1** | `row_separator` is extracted but NOT used. Python's `for line in file:` splits on newlines only. A file with `"a|b|c\n"` would count as 1 line, not 3 segments. |
| **Verdict** | **GAP** -- custom non-newline separators produce incorrect counts. |

### Edge Case 7: File with NaN-like strings ("NA", "NULL", "None")

| Aspect | Detail |
|--------|--------|
| **Talend** | These are counted as normal non-empty rows. |
| **V1** | Read as text via `open()`, not `pd.read_csv()`. No NaN interpretation. `line.strip()` returns non-empty string. Counted correctly. |
| **Verdict** | CORRECT |

### Edge Case 8: Very large file (multi-GB)

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles efficiently via Java BufferedReader line-by-line. |
| **V1** | Python's `for line in file:` reads one line at a time with buffered I/O. O(1) memory. Handles multi-GB files correctly. |
| **Verdict** | CORRECT |

### Edge Case 9: File path with context variable resolving to empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with clear error message. |
| **V1** | After context resolution, `filename` becomes `''`. Line 169: `if not filename or not os.path.exists(filename):` catches this. Raises `FileNotFoundError(f"File not found: ")`. Error message is not informative -- says "File not found" instead of "filename is required". |
| **Verdict** | PARTIAL -- error is raised but message is misleading. See BUG-FRC-010. |

### Edge Case 10: GlobalMap is None

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- globalMap always exists in Talend runtime. |
| **V1** | Line 210: `if self.global_map:` guards all GlobalMap operations. When `global_map` is None, GlobalMap writes are silently skipped. Row count is still returned in the result dict. However, downstream components relying on `{id}_COUNT` from globalMap will get None. |
| **Verdict** | CORRECT (defensive) but may cause silent downstream failures. |

### Edge Case 11: Binary file

| Aspect | Detail |
|--------|--------|
| **Talend** | May count bytes as rows or fail with encoding error depending on Java's behavior with the specified encoding. |
| **V1** | `open(filename, 'r', encoding=encoding)` in text mode. Binary content will likely cause `UnicodeDecodeError` with UTF-8 encoding (invalid byte sequences). With `ISO-8859-15` (single-byte encoding), all byte values are valid, so the file would be "read" and lines counted based on newline bytes. |
| **Verdict** | VARIES -- behavior depends on encoding. UTF-8 will fail (which is correct for a text-only component). ISO-8859-15 may produce unexpected counts (not an error per se). |

### Edge Case 12: Whitespace-only lines with `ignore_empty_row=true`

| Aspect | Detail |
|--------|--------|
| **Talend** | Whitespace-only lines are treated as empty when `IGNORE_EMPTY_ROW=true`. |
| **V1** | `line.strip()` returns `''` for whitespace-only lines, which is falsy. These lines are correctly excluded from the count. |
| **Verdict** | CORRECT |

### Edge Case 13: Lines containing only delimiter characters (e.g., `,,,,`)

| Aspect | Detail |
|--------|--------|
| **Talend** | NOT treated as empty. A row of delimiters contains empty fields but is a valid data row. Counted. |
| **V1** | `line.strip()` on `",,,,"` returns `",,,,"` (non-empty, not whitespace). Counted as a data row. |
| **Verdict** | CORRECT |

### Edge Case 14: File with trailing newline

| Aspect | Detail |
|--------|--------|
| **Talend** | Trailing newline does NOT create an extra empty row in most Talend implementations. Java's `BufferedReader.readLine()` returns null at EOF, not an empty string for a trailing newline. |
| **V1** | Python's `for line in file:` DOES yield a final empty string `''` if the file ends with a newline... actually no. Python's file iteration yields lines INCLUDING their newline character. So `"a\nb\n"` yields `"a\n"` and `"b\n"` (2 lines). `"a\nb\n\n"` yields `"a\n"`, `"b\n"`, and `"\n"` (3 lines). The trailing `\n` creates a line containing only `\n`. With `ignore_empty_row=true`, `"\n".strip()` is `""` (empty), so it is excluded. With `ignore_empty_row=false`, it counts as a row. |
| **Verdict** | **POTENTIAL DIFFERENCE** -- Talend may not count trailing newline as an extra row, but Python does (unless `ignore_empty_row=true`). This is a subtle behavioral difference for files ending with `\n`. |

### Edge Case 15: File with BOM (Byte Order Mark)

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles BOM based on encoding (Java handles UTF-8 BOM transparently). |
| **V1** | `open(filename, 'r', encoding='utf-8')` does NOT strip BOM. BOM becomes part of the first line. With `encoding='utf-8-sig'`, BOM is stripped. This does not affect row COUNT (BOM does not create extra rows), but if the first line is empty except for BOM, `ignore_empty_row=true` would NOT filter it (BOM characters are not whitespace). |
| **Verdict** | CORRECT for counting purposes (BOM does not affect line count). Minor issue for empty-row detection on first line. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileRowCount`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FRC-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FRC-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FRC-004 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |
| BUG-FRC-005 | **P1** | `base_component.py` / all components | `_validate_config()` return type not standardized. Some components return `bool`, standard says `List[str]`. |
| STD-FRC-003 | **P2** | `base_component.py:286-296` | `_process()` contract says `'main'` should be DataFrame, but utility components like FileRowCount return dicts. No utility component contract variant. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FRC-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FRC-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: DBG-FRC-001 -- Remove debug GlobalMap verification

**File**: `src/v1/engine/components/file/file_row_count.py`
**Lines**: 222-224

**Current code (will crash)**:
```python
# Verify storage in GlobalMap (for debugging purposes)
stored_value = self.global_map.get(count_key)
self.logger.debug(f"[{self.id}] Stored row count {stored_value} in GlobalMap with key: {count_key}")
```

**Fix**: Remove these three lines entirely. The `global_map.put()` on line 216 is guaranteed to succeed, and reading back the value serves no purpose. If verification logging is desired, log before the put:
```python
self.logger.debug(f"[{self.id}] Storing row count {rows_out} in GlobalMap with key: {count_key}")
self.global_map.put(count_key, rows_out)
```

**Impact**: Prevents crash from BUG-FRC-002. **Risk**: None (removes debug-only code).

---

### Fix Guide: ENG-FRC-002 -- Implementing die_on_error

**File**: `src/v1/engine/components/file/file_row_count.py`

**Step 1**: Extract die_on_error from config in `_process()`:
```python
die_on_error = self.config.get('die_on_error', True)  # Default True for backward compat
```

**Step 2**: Replace the catch-all handler (lines 228-230):
```python
except Exception as e:
    self.logger.error(f"[{self.id}] Processing failed: {str(e)}")
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    if die_on_error:
        raise
    else:
        self.logger.warning(f"[{self.id}] Error suppressed (die_on_error=false): {str(e)}")
        self._update_stats(0, 0, 0)
        return {'main': {'row_count': 0}}
```

**Impact**: Enables graceful error handling matching Talend behavior. **Risk**: Medium -- changes default behavior for existing jobs that expect exceptions. Consider making default `True` to maintain backward compatibility.

---

### Fix Guide: ENG-FRC-001 -- Implementing row_separator

**File**: `src/v1/engine/components/file/file_row_count.py`

**Replace** the counting loop (lines 180-188):
```python
with open(filename, 'r', encoding=encoding) as file:
    # Use custom row separator if not a standard newline
    if row_separator in ('\n', '\r\n', '\r', '\\n', '\\r\\n', '\\r'):
        # Standard newline -- use Python's default line iteration (efficient)
        for line in file:
            rows_in += 1
            if ignore_empty_row and not line.strip():
                rows_rejected += 1
                continue
            rows_out += 1
    else:
        # Custom row separator -- read entire file and split
        content = file.read()
        lines = content.split(row_separator)
        # Remove trailing empty segment from split (if file ends with separator)
        if lines and lines[-1] == '':
            lines = lines[:-1]
        for line in lines:
            rows_in += 1
            if ignore_empty_row and not line.strip():
                rows_rejected += 1
                continue
            rows_out += 1
```

**Caveat**: The custom separator path reads the entire file into memory. For very large files with custom separators, a chunked reading approach would be needed. However, custom (non-newline) row separators are rare in practice.

**Impact**: Enables custom row separator support. **Risk**: Low for standard cases (no behavior change). Medium for custom separators (new code path).

---

### Fix Guide: BUG-FRC-005 -- Fix _validate_config() return type

**File**: `src/v1/engine/components/file/file_row_count.py`

**Replace** the entire `_validate_config()` method:
```python
def _validate_config(self) -> List[str]:
    """
    Validate the component configuration parameters.

    Returns:
        List[str]: List of validation error messages. Empty list if valid.
    """
    errors = []

    # Check required filename parameter
    filename = self.config.get('filename') if 'filename' in self.config else self.config.get('FILENAME', '')
    if not filename:
        errors.append(f"[{self.id}] filename is required but not provided")
    elif not isinstance(filename, str):
        errors.append(f"[{self.id}] filename must be a string, got {type(filename)}")

    # Validate encoding parameter if provided
    encoding = self.config.get('encoding') if 'encoding' in self.config else self.config.get('ENCODING', 'UTF-8')
    if encoding:
        try:
            ''.encode(encoding)
        except LookupError:
            errors.append(f"[{self.id}] Invalid encoding specified: {encoding}")

    # Validate boolean parameters
    ignore_empty_row = self.config.get('ignore_empty_row')
    if ignore_empty_row is None:
        ignore_empty_row = self.config.get('IGNORE_EMPTY_ROW', False)
    if not isinstance(ignore_empty_row, bool):
        errors.append(f"[{self.id}] ignore_empty_row must be a boolean, got {type(ignore_empty_row)}")

    if errors:
        for err in errors:
            self.logger.error(err)
    else:
        self.logger.debug(f"[{self.id}] Configuration validation passed")

    return errors
```

**Impact**: Aligns with METHODOLOGY.md contract. **Risk**: Low -- method is currently dead code, so changing its signature has no runtime impact until it is wired up.

---

## Appendix I: Execution Flow Diagram

```
Talend Job XML
    |
    v
[converter.py:_parse_component()]
    |
    | elif component_type == 'tFileRowCount':  (line 294)
    |     component_parser.parse_tfile_row_count(node, component)  (line 295)
    |
    v
[component_parser.py:parse_tfile_row_count()]  (lines 1706-1718)
    |
    | Extracts: filename, row_separator, ignore_empty_row, encoding
    | Missing:  die_on_error
    |
    v
V1 Job JSON
    |
    v
[engine.py: component_registry]
    |
    | 'FileRowCount': FileRowCount  (line 82)
    | 'tFileRowCount': FileRowCount (line 83)
    |
    v
[FileRowCount.__init__()]
    |
    | super().__init__() -> BaseComponent
    | self.logger setup
    |
    v
[BaseComponent.execute()]  (base_component.py:188)
    |
    | 1. _resolve_java_expressions()  [if java_bridge]
    | 2. context_manager.resolve_dict()  [if context_manager]
    | 3. _auto_select_mode(None) -> BATCH
    | 4. _execute_batch(None) -> _process(None)
    |
    v
[FileRowCount._process(None)]  (file_row_count.py:138)
    |
    | 1. Extract config (filename, row_separator, ignore_empty_row, encoding)
    | 2. Validate file exists
    | 3. Open file, count lines
    | 4. _update_stats(rows_in, rows_out, rows_rejected)
    | 5. GlobalMap: put {id}_NB_LINE, {id}_COUNT, {id}_NB_LINE_OK, {id}_NB_LINE_REJECT
    | 6. GlobalMap: get {id}_COUNT  [CRASHES - BUG-FRC-002]
    | 7. Return {'main': {'row_count': N}}
    |
    v
[BaseComponent.execute() continued]
    |
    | 5. stats['EXECUTION_TIME'] = elapsed
    | 6. _update_global_map()  [CRASHES - BUG-FRC-001]
    | 7. status = SUCCESS  [never reached due to crash]
    | 8. result['stats'] = stats  [never reached]
    | 9. return result  [never reached]
    |
    v
[Exception propagation]
    |
    | status = ERROR (line 228)
    | error_message = str(e)
    | _update_global_map()  [called again in except block, CRASHES AGAIN]
    | raise  [original NameError from _update_global_map propagates]
```

**Key insight**: Due to BUG-FRC-001 and BUG-FRC-002, the component will ALWAYS fail with a `NameError` even when the file is counted successfully. The manual GlobalMap writes in `_process()` DO succeed before the crash, but the component status is set to ERROR and the exception propagates to the caller.

**Workaround**: If `global_map` is None (not provided), both crash points are bypassed (guarded by `if self.global_map:`), and the component completes successfully. But then the `{id}_COUNT` variable is not available to downstream components, which defeats the purpose of this component.

---

## Appendix J: Comparison with Similar Components

### FileRowCount vs FileExist

Both are utility components that store results in GlobalMap rather than producing DataFrame output.

| Aspect | FileRowCount | FileExist |
|--------|-------------|-----------|
| Return format | `{'main': {'row_count': int}}` | Likely similar dict format |
| GlobalMap key | `{id}_COUNT` (legacy), `{id}_NB_LINE` | `{id}_EXISTS` (boolean) |
| Config key for path | `filename` | Likely `filename` or `filepath` |
| die_on_error | Not implemented | Unknown |
| _validate_config() | Returns bool (contract violation) | Unknown |

### FileRowCount vs FileInputDelimited

Both read files but for fundamentally different purposes.

| Aspect | FileRowCount | FileInputDelimited |
|--------|-------------|-------------------|
| Purpose | Count rows | Read and parse rows |
| Output | Dict with count | DataFrame with parsed data |
| Memory | O(1) | O(N) for file size |
| Schema | None (no output schema) | Full column schema |
| row_separator | Extracted but not used | Extracted and partially used |
| die_on_error | Not implemented | Implemented |
| Config key for path | `filename` | `filepath` (inconsistent) |

---

## Appendix K: NaN and Empty String Handling

### How FileRowCount Handles Special Values

Since `FileRowCount` reads files as raw text (not via pandas), NaN handling is simpler than for data input components:

| Value in File | `ignore_empty_row=false` | `ignore_empty_row=true` |
|---------------|-------------------------|------------------------|
| `""` (empty line after strip) | Counted (rows_out++) | Skipped (rows_rejected++) |
| `"   "` (whitespace only) | Counted (rows_out++) | Skipped (strip() returns `""`) |
| `"NA"` | Counted (rows_out++) | Counted (strip() returns `"NA"`, truthy) |
| `"NULL"` | Counted (rows_out++) | Counted (strip() returns `"NULL"`, truthy) |
| `"None"` | Counted (rows_out++) | Counted (strip() returns `"None"`, truthy) |
| `"NaN"` | Counted (rows_out++) | Counted (strip() returns `"NaN"`, truthy) |
| `"\n"` (bare newline) | Counted (rows_out++) | Skipped (strip() returns `""`) |
| `"\t"` (tab only) | Counted (rows_out++) | Skipped (strip() returns `""`) |
| `",,,,"` (delimiters only) | Counted (rows_out++) | Counted (strip() returns `",,,,"`, truthy) |

This behavior matches Talend's `IGNORE_EMPTY_ROW` semantics: only truly blank/whitespace-only lines are treated as "empty". NaN-like string values are counted as normal rows.

---

## Appendix L: Component Status Lifecycle

```
ComponentStatus.PENDING
    |
    | execute() called
    v
ComponentStatus.RUNNING  (line 192 of base_component.py)
    |
    | _process() completes successfully
    | _update_global_map() called  [CRASHES]
    |
    v
ComponentStatus.ERROR  (line 228 of base_component.py)
    |
    | _update_global_map() called again in except block [CRASHES AGAIN]
    | exception re-raised
    v
[Exception propagates to caller]
```

**Expected lifecycle (after BUG-FRC-001 fix)**:
```
ComponentStatus.PENDING
    |
    v
ComponentStatus.RUNNING
    |
    v
ComponentStatus.SUCCESS  (line 220 of base_component.py)
    |
    | result['stats'] = stats
    | return result
    v
[Caller receives result dict]
```

**Note**: The `ComponentStatus` is only used internally. No external monitoring system reads this status in the current implementation. However, if monitoring is added in the future, the crash-induced ERROR status would cause false alerts for components that actually completed their work successfully.

---

## Appendix M: Converter Expression Handling Deep Dive

### FILENAME Expression Scenarios

The `FILENAME` parameter in Talend XML can contain various expression types. Here is how each type flows through the converter and engine:

| Expression Type | Talend XML Example | Converter Output | Engine Resolution | Works? |
|----------------|-------------------|-----------------|-------------------|--------|
| Literal path | `"/data/file.csv"` | `"/data/file.csv"` | Used as-is | Yes |
| Context variable | `context.inputFile` | `${context.inputFile}` (if generic marker applied) | `context_manager.resolve_dict()` resolves `${context.inputFile}` | Yes (if generic context detection runs) |
| Java concatenation | `context.dir + "/file.csv"` | May be marked `{{java}}context.dir + "/file.csv"` | `_resolve_java_expressions()` via Java bridge | Yes (if Java bridge available) |
| GlobalMap reference | `(String)globalMap.get("tFileList_1_CURRENT_FILE")` | May be marked `{{java}}...` | Java bridge resolves | Yes (if Java bridge available) |
| Quoted literal | `"\"C:\\data\\file.csv\""` | `"C:\data\file.csv"` (after XML parsing, quotes stripped by Talend) | Used as-is | Yes (but depends on XML attribute handling) |
| Empty string | `""` | `""` | Empty string; line 169 catches `not filename` | Error raised |
| Null / missing | (attribute absent) | `""` (default from `.get('value', '')`) | Empty string; line 169 catches | Error raised |

**Critical observation**: The `parse_tfile_row_count()` method (line 1710) does NOT apply context variable detection or Java expression marking. These are handled by generic post-processing in the converter pipeline. If the generic post-processing does not run for parameters extracted by specific parsers, context variables and Java expressions in FILENAME may not be resolved. This needs verification against the actual converter pipeline flow.

### ROWSEPARATOR Expression Handling

| Talend XML Value | After Quote Stripping (lines 1713-1714) | Engine Usage |
|-----------------|----------------------------------------|--------------|
| `"\"\n\""` | `\n` | Extracted as `\n` string literal. NOT used by engine. |
| `"\"\\r\\n\""` | `\r\n` | Extracted. NOT used by engine. |
| `"\"\|\""` | `\|` | Extracted. NOT used by engine. Would be incorrect if used (no regex handling). |
| `"\n"` (no surrounding quotes) | `\n` (no stripping needed -- quotes check fails) | Correct. |
| `"\\n"` (escaped backslash-n) | `\\n` (not a newline -- literal backslash + n) | Would be incorrect if used. Engine would need to unescape. |

**Issue**: The quote stripping logic (lines 1713-1714) only strips surrounding `"` characters. It does NOT unescape Java-style escape sequences like `\\n` -> `\n` or `\\t` -> `\t`. If the Talend XML stores the row separator as an escaped string (e.g., `"\\n"` meaning a literal backslash followed by `n`), the converter passes this through without converting it to an actual newline character. This is moot currently since the engine ignores `row_separator`, but would be a bug if `row_separator` support is implemented.

---

## Appendix N: Base Class Integration Analysis

### How FileRowCount Interacts with BaseComponent

The `FileRowCount` class extends `BaseComponent` but uses only a subset of the base class functionality. Here is a complete analysis of which base class features are used, unused, or problematic:

| Base Class Feature | Used by FileRowCount? | Notes |
|-------------------|----------------------|-------|
| `self.id` | Yes | Component identifier used in logging and GlobalMap keys |
| `self.config` | Yes | Configuration dictionary with file parameters |
| `self.global_map` | Yes | GlobalMap for storing COUNT and NB_LINE variables |
| `self.context_manager` | Yes (indirectly) | Used by `execute()` to resolve `${context.var}` in config |
| `self.component_type` | No | Set to `'FileRowCount'` but never read within the component |
| `self.subjob_id` | No | Not used -- FileRowCount does not track subjob membership |
| `self.is_subjob_start` | No | Not used |
| `self.execution_mode` | Yes (indirectly) | Set by `_determine_execution_mode()`. Always results in BATCH for this component (input_data is None). |
| `self.chunk_size` | No | Not relevant -- no DataFrame output to chunk |
| `self.java_bridge` | Yes (indirectly) | Used by `execute()` to resolve `{{java}}` expressions in config |
| `self.python_routine_manager` | No | Not used |
| `self.inputs` | No | Empty list -- FileRowCount has no programmatic inputs |
| `self.outputs` | No | Empty list -- FileRowCount has no programmatic outputs |
| `self.triggers` | No | Empty list -- triggers are handled at engine level |
| `self.input_schema` | No | None -- no input schema |
| `self.output_schema` | No | None -- no output schema (utility component) |
| `self.stats` | Yes | Updated via `_update_stats()` |
| `self.status` | Yes (indirectly) | Set by `execute()` to RUNNING/SUCCESS/ERROR |
| `self.error_message` | Yes (indirectly) | Set by `execute()` on error |
| `execute()` | Yes | Main entry point called by engine |
| `_resolve_java_expressions()` | Yes (indirectly) | Called by `execute()` if java_bridge set |
| `_auto_select_mode()` | Yes (indirectly) | Returns BATCH (input_data is None) |
| `_execute_batch()` | Yes (indirectly) | Calls `_process()` |
| `_execute_streaming()` | No (would break) | Never triggered but would fail on dict return |
| `_create_chunks()` | No | Not relevant |
| `_update_global_map()` | Yes (CRASHES) | Called by `execute()` after `_process()` returns |
| `_update_stats()` | Yes | Called in `_process()` line 207 |
| `validate_schema()` | No | No schema to validate (utility component) |
| `get_status()` | No (externally available) | Available but not called internally |
| `get_stats()` | No (externally available) | Available but not called internally |
| `get_python_routines()` | No | Not used |

**Observations**:
1. FileRowCount uses approximately 40% of the base class surface area.
2. The base class is designed primarily for data-flow components (DataFrame in/out). Utility components like FileRowCount fit awkwardly -- they don't produce DataFrames, don't use schemas, and don't need streaming mode.
3. A `BaseUtilityComponent` subclass could be introduced to formalize the utility component pattern (dict return, no schema, no streaming).

### _update_stats() vs Manual GlobalMap Writes

The component has a **double-write pattern** that is both redundant and bug-prone:

1. **Manual writes** in `_process()` (lines 210-220):
   ```python
   self.global_map.put(f"{self.id}_NB_LINE", rows_out)
   self.global_map.put(f"{self.id}_COUNT", rows_out)
   self.global_map.put(f"{self.id}_NB_LINE_OK", rows_out)
   self.global_map.put(f"{self.id}_NB_LINE_REJECT", rows_rejected)
   ```
   These write directly to GlobalMap using `put()`.

2. **Base class writes** in `_update_global_map()` (base_component.py line 298-304):
   ```python
   for stat_name, stat_value in self.stats.items():
       self.global_map.put_component_stat(self.id, stat_name, stat_value)
   ```
   This writes via `put_component_stat()` which ALSO calls `put()` internally (global_map.py line 49).

**Result**: `{id}_NB_LINE`, `{id}_NB_LINE_OK`, and `{id}_NB_LINE_REJECT` are each written TWICE to GlobalMap (once manually, once by base class). The `{id}_COUNT` key is only written once (manually, since the base class stats dict does not have a `COUNT` key). The `{id}_EXECUTION_TIME`, `{id}_NB_LINE_INSERT`, `{id}_NB_LINE_UPDATE`, `{id}_NB_LINE_DELETE` keys are only written by the base class.

**However**, the base class `_update_global_map()` crashes (BUG-FRC-001), so in practice only the manual writes succeed. If BUG-FRC-001 is fixed, the double-write becomes redundant overhead.

**Recommendation**: After fixing BUG-FRC-001, keep only the manual `{id}_COUNT` write (since the base class does not write this key). Remove the other manual writes (`{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT`) and let the base class handle them via `_update_global_map()`.

---

## Appendix O: Testing Strategy Guide

### Unit Test Structure

```python
# test_file_row_count.py

import pytest
import tempfile
import os
from unittest.mock import MagicMock

from src.v1.engine.components.file.file_row_count import FileRowCount
from src.v1.engine.global_map import GlobalMap


class TestFileRowCountBasic:
    """P0: Basic functionality tests"""

    def test_count_simple_file(self):
        """Count rows in a simple multi-line file"""
        # Setup: create temp file with 5 lines
        # Execute: FileRowCount with default config
        # Assert: row_count == 5, stats correct, GlobalMap has {id}_COUNT == 5

    def test_empty_file(self):
        """Empty file returns count of 0"""
        # Assert: row_count == 0, no error raised

    def test_ignore_empty_rows(self):
        """Empty rows are excluded when ignore_empty_row=True"""
        # Setup: file with 10 lines, 3 blank
        # Assert: row_count == 7, NB_LINE_REJECT == 3

    def test_missing_file_raises(self):
        """Missing file raises FileNotFoundError"""
        # Assert: FileNotFoundError with descriptive message

    def test_global_map_count_key(self):
        """COUNT key is set in GlobalMap"""
        # Assert: global_map contains {id}_COUNT with correct value

    def test_statistics_tracking(self):
        """Stats dict contains correct NB_LINE, NB_LINE_OK, NB_LINE_REJECT"""
        # Assert: stats match expected values

    def test_single_line_no_newline(self):
        """File with one line and no trailing newline counts 1"""
        # Assert: row_count == 1


class TestFileRowCountEncoding:
    """P1: Encoding tests"""

    def test_iso_8859_15_encoding(self):
        """Read file with ISO-8859-15 encoding"""
        # Setup: file with non-ASCII chars in ISO-8859-15
        # Assert: correct count, no encoding error

    def test_encoding_mismatch_raises(self):
        """Wrong encoding raises UnicodeDecodeError"""
        # Setup: UTF-8 file, read with ascii encoding
        # Assert: UnicodeDecodeError

    def test_utf8_with_bom(self):
        """UTF-8 file with BOM counted correctly"""
        # Assert: BOM does not affect count


class TestFileRowCountEdgeCases:
    """P1-P2: Edge case tests"""

    def test_windows_line_endings(self):
        """\\r\\n line endings counted correctly"""
        # Assert: each \\r\\n-separated line counts as 1

    def test_whitespace_only_lines_as_empty(self):
        """Lines with only spaces/tabs are empty when ignore_empty_row=True"""
        # Assert: whitespace-only lines excluded

    def test_permission_denied(self):
        """Unreadable file raises PermissionError"""
        # Assert: PermissionError with filename in message

    def test_context_variable_resolution(self):
        """Context variables in filename are resolved"""
        # Setup: config with ${context.path}, mock context_manager
        # Assert: resolved path used

    def test_large_file_performance(self):
        """1M line file counted in reasonable time with O(1) memory"""
        # Assert: count == 1000000, execution < 10 seconds

    def test_global_map_none(self):
        """Component works without GlobalMap (global_map=None)"""
        # Assert: row_count returned, no error (but no GlobalMap writes)

    def test_trailing_newline(self):
        """File ending with newline does not count extra empty row"""
        # Setup: "line1\\nline2\\n"
        # Assert: row_count == 2 (not 3)

    def test_mixed_line_endings(self):
        """File with mixed \\n, \\r\\n, \\r endings"""
        # Assert: all endings treated as line separators

    def test_only_empty_lines_with_ignore(self):
        """File with only empty lines, ignore_empty_row=True"""
        # Assert: row_count == 0, NB_LINE_REJECT == N

    def test_delimiter_only_lines_not_empty(self):
        """Lines containing only commas are not treated as empty"""
        # Assert: ',,,,' is counted as a row even with ignore_empty_row=True
```

### Integration Test Structure

```python
# test_file_row_count_integration.py

class TestFileRowCountIntegration:
    """Integration tests with engine and other components"""

    def test_count_then_read_conditional(self):
        """
        tFileRowCount -> OnSubjobOk -> tJava (check COUNT > 0) -> tFileInputDelimited
        Simulates the common pattern of pre-validating file row count
        before processing.
        """
        # Setup: Create file with known row count
        # Execute: Run FileRowCount, then access {id}_COUNT from GlobalMap
        # Assert: COUNT matches, conditional logic works

    def test_count_in_file_list_iteration(self):
        """
        tFileList (iterate) -> tFileRowCount -> OnSubjobOk -> tLogRow
        Simulates counting rows in multiple files during iteration.
        """
        # Setup: Create 3 files with different row counts
        # Execute: Iterate with FileList, count each
        # Assert: Each file's COUNT stored with correct component ID

    def test_count_with_context_variables(self):
        """
        Context-parameterized filename resolution
        """
        # Setup: Context with input_dir variable
        # Execute: FileRowCount with ${context.input_dir}/file.csv
        # Assert: Correct file counted

    def test_error_handling_chain(self):
        """
        tFileRowCount (missing file) -> OnSubjobError -> tLogRow
        Simulates error handling when file does not exist.
        """
        # Setup: Non-existent file path
        # Execute: FileRowCount, catch error
        # Assert: Error propagated, ERROR_MESSAGE would be set (if implemented)
```

---

## Appendix P: Talend Code Generation Reference

When Talend Studio compiles a job containing `tFileRowCount`, it generates Java code similar to the following. This reference is useful for understanding the exact runtime behavior that the v1 engine should replicate.

### Typical Generated Java Code (Simplified)

```java
// tFileRowCount_1 - Begin
int nb_line_tFileRowCount_1 = 0;

java.io.BufferedReader br_tFileRowCount_1 = null;
try {
    br_tFileRowCount_1 = new java.io.BufferedReader(
        new java.io.InputStreamReader(
            new java.io.FileInputStream(
                /* FILENAME expression */
                context.inputDir + "/data.csv"
            ),
            /* ENCODING */
            "UTF-8"
        )
    );

    String line_tFileRowCount_1 = null;
    String row_separator_tFileRowCount_1 = "\n";

    while ((line_tFileRowCount_1 = br_tFileRowCount_1.readLine()) != null) {
        // IGNORE_EMPTY_ROW check
        if (/* IGNORE_EMPTY_ROW */ true) {
            if (line_tFileRowCount_1.trim().length() == 0) {
                continue;
            }
        }
        nb_line_tFileRowCount_1++;
    }
} catch (Exception e_tFileRowCount_1) {
    // DIE_ON_ERROR handling
    if (/* DIE_ON_ERROR */ false) {
        throw e_tFileRowCount_1;
    } else {
        globalMap.put("tFileRowCount_1_ERROR_MESSAGE", e_tFileRowCount_1.getMessage());
    }
} finally {
    if (br_tFileRowCount_1 != null) {
        br_tFileRowCount_1.close();
    }
}

// Store count in globalMap
globalMap.put("tFileRowCount_1_COUNT", nb_line_tFileRowCount_1);
globalMap.put("tFileRowCount_1_NB_LINE", nb_line_tFileRowCount_1);
// tFileRowCount_1 - End
```

### Key Behavioral Observations from Generated Code

1. **`readLine()` semantics**: Java's `BufferedReader.readLine()` returns `null` at EOF and does NOT include the line terminator in the returned string. This means trailing newlines do NOT create an extra empty line. **This differs from Python's `for line in file:`** which includes the newline character in each line string (and yields a final empty line for trailing newlines in some edge cases).

2. **`IGNORE_EMPTY_ROW` implementation**: Java checks `line.trim().length() == 0`. Python checks `not line.strip()`. These are semantically equivalent -- both treat whitespace-only lines as empty.

3. **`COUNT` timing**: The `globalMap.put("tFileRowCount_1_COUNT", ...)` happens AFTER the loop, in the same thread. This is a synchronous write. The v1 engine's manual GlobalMap writes in `_process()` (lines 215-220) are also synchronous, which is correct.

4. **Error handling**: The generated code has explicit `DIE_ON_ERROR` branching in the catch block. When `false`, the error message is stored in `{id}_ERROR_MESSAGE` and execution continues (count may be 0 or partial). The v1 engine does NOT have this branching -- all errors propagate.

5. **`readLine()` vs `row_separator`**: The generated code uses `BufferedReader.readLine()` which handles `\n`, `\r\n`, and `\r` as line terminators regardless of the `ROWSEPARATOR` parameter. The `row_separator` variable is declared but not actually used in the standard generated code for `tFileRowCount`. This means **Talend itself may not fully implement custom row separators** for this component. The v1 engine's lack of `row_separator` implementation may actually be CORRECT behavior for matching Talend.

6. **Resource management**: Java uses try-finally to close the `BufferedReader`. Python's `with open()` context manager provides equivalent resource management.

### Implication for V1 Engine

The most important insight from the generated code is point 5: **Talend's own generated code for `tFileRowCount` may not use the `ROWSEPARATOR` parameter**. The Java `BufferedReader.readLine()` method hardcodes newline detection. This means the v1 engine's failure to use `row_separator` may actually be **correct Talend behavior**, not a bug. However, this should be verified against actual Talend-generated code for a job with a custom `ROWSEPARATOR` value.

If confirmed, the priority of ENG-FRC-001 should be downgraded from P1 to P3 (the parameter exists in the UI but has no runtime effect in Talend's own generated code).

---

## Appendix Q: Risk Assessment for Production Deployment

### Deployment Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|------|-----------|--------|------------|---------------|
| BUG-FRC-001 crashes all components | **Certain** | **Critical** -- no component completes successfully when global_map is set | Fix `_update_global_map()` before deployment | None after fix |
| BUG-FRC-002 crashes GlobalMap.get() | **Certain** | **High** -- debug verification on line 223 crashes, masking successful count | Fix `GlobalMap.get()` or remove line 223 | None after fix |
| Missing die_on_error causes job crashes | **Medium** | **High** -- jobs designed for graceful error handling will crash | Extract and implement die_on_error | Low (most jobs set die_on_error=true) |
| Encoding mismatch (UTF-8 vs ISO-8859-15) | **Medium** | **Medium** -- wrong encoding causes UnicodeDecodeError on non-ASCII files | Fix default to ISO-8859-15 or verify job configs | Low (most modern files are UTF-8) |
| row_separator not implemented | **Low** | **Low** -- custom separators are rare; standard newlines work correctly | Verify Talend behavior; implement if needed | Very low |
| Return format breaks streaming mode | **Very Low** | **Medium** -- streaming mode never triggered for this component | Add guard in base class for non-DataFrame returns | Very low |
| No tests catch regressions | **High** | **High** -- any code change could introduce bugs undetected | Create P0 test suite before deployment | None after tests |

### Minimum Viable Fixes for Production

To deploy `FileRowCount` in production with acceptable risk, the following fixes are **mandatory**:

1. Fix BUG-FRC-001 (`_update_global_map()` undefined `value`) -- **blocks ALL components**
2. Fix BUG-FRC-002 (`GlobalMap.get()` undefined `default`) OR remove debug line 222-224 -- **blocks this component**
3. Create at least 3 unit tests (basic count, empty file, ignore empty rows) -- **validates core behavior**

With these three fixes, the component can be deployed for the common use case: counting rows in a UTF-8 text file with standard newline line endings. The remaining issues (die_on_error, custom row separator, encoding default) represent edge cases that can be addressed in subsequent releases.

### Jobs That Should NOT Use This Component (Until Fixes)

| Job Pattern | Reason |
|-------------|--------|
| Jobs with `DIE_ON_ERROR=false` for tFileRowCount | No graceful error handling; job will crash on any error |
| Jobs counting files with ISO-8859-15 encoding (without explicit encoding set) | Wrong default encoding; UnicodeDecodeError on non-ASCII chars |
| Jobs using custom row separators (non-newline) | row_separator not implemented; incorrect counts |
| Jobs reading `{id}_ERROR_MESSAGE` from downstream components | ERROR_MESSAGE not set in GlobalMap |
