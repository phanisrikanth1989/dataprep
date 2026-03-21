# Audit Report: tFileInputRaw / FileInputRaw

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputRaw` |
| **V1 Engine Class** | `FileInputRaw` |
| **Engine File** | `src/v1/engine/components/file/file_input_raw.py` (148 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_t_file_input_raw()` (lines 2104-2118) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif component_type == 'tFileInputRaw'` branch (lines 335-336) |
| **Registry Aliases** | `TFileInputRaw`, `tFileInputRaw` (registered in `src/v1/engine/engine.py` lines 80-81) |
| **Category** | File / Input |
| **Complexity** | Low -- single-file, single-column reader with minimal parameters |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_raw.py` | Engine implementation (148 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2104-2118) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (lines 335-336) | Dispatch -- dedicated `elif` for `tFileInputRaw`; calls `parse_t_file_input_raw()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 9: `from .file_input_raw import FileInputRaw`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 1 | 1 | 4 of 6 Talend params extracted (67%); missing Stream mode, no Java expression marking on FILENAME; crash on missing XML nodes; duplicate config keys from Phase 1 |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 0 | No FILENAME_PATH/ERROR_MESSAGE globalMap; hardcoded column name; no stream mode; die_on_error defaults to False |
| Code Quality | **R** | 2 | 4 | 5 | 5 | debug_content() logs at INFO; _validate_config() dead code; overly broad exception; base class bugs cross-cutting; binary mode zero diagnostics; validate_schema() dead metadata |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | No large-file protection; unconditional debug_content() cost; DataFrame overhead for single value |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero converter tests |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputRaw Does

`tFileInputRaw` reads **all data in a raw file** and sends it to a **single output column** for subsequent processing by another component. It is a simple file reader designed for jobs that require a whole file to be ingested as a single value -- such as reading XML/JSON blobs for downstream parsing by `tExtractXMLField` or `tExtractJSONFields`, binary payloads for REST API calls via `tREST`, or template files for string substitution via `tReplace`.

Unlike `tFileInputDelimited` (which splits rows and columns), `tFileInputRaw` delivers the entire file as one row with one column. This makes it the simplest input component in the File family, but its behavior is tightly specified and downstream components depend on its exact output shape (column name, data type, and single-row guarantee).

**Source**: [tFileInputRaw Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/raw/tfileinputraw-standard-properties), [tFileInputRaw Component Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/raw/tfileinputraw), [tFileInputRaw Component Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/raw/tfileinputraw), [Configuring tFileInputRaw (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/data-mapping/thmap-tfileinputraw-configuring-tfileinputraw)

**Component family**: Raw (File / Input)
**Available in**: All Talend products (Standard). Also referenced in Data Mapping scenarios with tFileOutputRaw.
**Required JARs**: `commons-io-2.8.0.jar` (Talend 8.0) / `commons-io-2.4.jar` (Talend 6.5)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | Single `content` column (id_String) | Column definitions. Typically one column whose name and type define the output shape. The user can rename this column (e.g., `raw_data`, `xml_payload`, `file_blob`). |
| 3 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path to the input file. Supports context variables, globalMap references, Java expressions. Talend documentation: "Use absolute path (instead of relative path) for this field to avoid possible errors." |
| 4 | Mode | `MODE` | Dropdown | Read as string | How to read the file. Three options: **Read as string** (entire file as Java `String`), **Read as bytes array** (file as `byte[]`), or **Stream the file** (real-time character-by-character reading). |
| 5 | Encoding | `ENCODING` | Dropdown / Custom | UTF-8 | Character encoding when Mode = "Read as string". Options include predefined encoding types (UTF-8, ISO-8859-1, etc.) or custom manual definition. Only applicable when Mode is "Read as string"; ignored for bytes/stream modes. |
| 6 | Die on Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop job execution on error. When checked, catches `FileNotFoundException` and stops the job. When unchecked, skips the error and allows error row collection via Row > Reject link. **Note**: Talend documentation specifically states `DIE_ON_ERROR` defaults to `false` (unchecked), unlike some components that default to `true`. |

#### Mode Options Detail

| Mode | Talend XML Value | Talend Behavior | Output Type | Notes |
|------|------------------|-----------------|-------------|-------|
| Read as string | `STRING` | Entire file content is read into memory as a Java `String` using the specified encoding. Output column type: `id_String`. | String | Most common mode. Used for text files, XML, JSON, templates. |
| Read as bytes array | `BYTE_ARRAY` | File content is read as a `byte[]`. No encoding conversion. Output column type: `id_byte[]`. | byte[] | Used for binary files, images, PDFs, REST payloads. |
| Stream file | `STREAM` | File is streamed character-by-character. As soon as the first character is entered in the source file, it is read immediately. Output type: `InputStream`. | InputStream | Used for real-time file monitoring, log tailing, pipe reading. Blocking mode. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 7 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Single row containing the file content in one column. Always exactly one row per execution. |
| `ITERATE` | Output | Iterate | Enables iterative processing when the component is used with iteration components like `tFlowToIterate`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |

**Note**: tFileInputRaw does **not** have a REJECT connector. Unlike `tFileInputDelimited`, errors are either fatal (`die_on_error=true`) or silently produce an empty result. There is no row-level rejection concept since the component outputs exactly one row (the whole file) or zero rows (on error).

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_FILENAME_PATH` | String | After execution | The resolved absolute file path that was read. Available as an After variable for downstream reference. |
| `{id}_ERROR_MESSAGE` | String | On error | Error description when a failure occurs. Only populated when `DIE_ON_ERROR` is unchecked and an error was caught. |

**Note on NB_LINE**: Talend's tFileInputRaw does NOT produce `NB_LINE`, `NB_LINE_OK`, or `NB_LINE_REJECT` as standard GlobalMap variables in the way other components do (e.g., `tFileInputDelimited`). The base statistics are tracked internally for tStatCatcher but are not exposed as standard GlobalMap entries. However, the v1 engine's `BaseComponent._update_global_map()` does push `NB_LINE`, `NB_LINE_OK`, and `NB_LINE_REJECT` for all components uniformly, creating a behavioral difference from Talend.

### 3.5 Behavioral Notes

1. **Single row output**: Regardless of file size or content, tFileInputRaw always produces exactly one row with one column. The schema is typically a single column named `content` (or whatever the user defines in the schema editor).

2. **Schema flexibility**: The user can rename the output column in the schema editor. The component reads the file and assigns it to the first (and typically only) schema column. Common column names include `content`, `raw_data`, `xml_payload`, `file_blob`, `body`.

3. **Encoding only applies in string mode**: When mode is "Read as bytes array" or "Stream file", the encoding parameter is ignored. Attempting to set encoding in bytes mode has no effect.

4. **Die on Error interaction with FileNotFoundException**: The Talend documentation specifically notes that `DIE_ON_ERROR` must be checked to properly catch `FileNotFoundException`. When unchecked, a missing file silently produces an empty result and sets `ERROR_MESSAGE`.

5. **Stream mode is blocking**: In "Stream file" mode, the component acts as a real-time listener on the file, suitable for monitoring log files or named pipes. This is an advanced feature rarely used in batch ETL jobs.

6. **JAR dependency note**: Talend documentation mentions that certain JARs (commons-io) may require manual installation due to license incompatibility. This is a Talend Studio concern, not a v1 engine concern.

7. **Die on Error defaults to False**: Unlike many other components where `DIE_ON_ERROR` defaults to True, tFileInputRaw defaults to False. This means by default, file-not-found errors are silently swallowed and the job continues with an empty result.

8. **Output column type depends on mode**: In string mode, the output column type is `id_String`. In bytes mode, it is `id_byte[]`. The schema should match the selected mode, but Talend does not enforce this at design time.

9. **Empty file behavior**: Reading an empty file (0 bytes) in string mode produces a single row with an empty string `""`. In bytes mode, it produces a single row with an empty byte array `b""`. The component does NOT return zero rows for an empty file.

10. **Line endings preserved**: tFileInputRaw reads the file content exactly as-is. Line endings (`\n`, `\r\n`, `\r`) are preserved in the output. No normalization occurs. This is important for downstream XML/JSON parsing where whitespace matters.

11. **Binary safety**: In bytes mode, null bytes (`\x00`) and all binary data are preserved. The output is a raw byte array suitable for binary protocols and file operations.

12. **Maximum file size**: There is no explicit file size limit in Talend's tFileInputRaw. The effective limit is the JVM heap size. In the v1 Python engine, the limit is available system memory. For very large files (multi-GB), both environments may encounter `OutOfMemoryError` / `MemoryError`.

---

## 4. Converter Audit

### 4.1 Parsing Architecture

tFileInputRaw follows a **two-phase parsing** approach:

1. **Phase 1** (`parse_base_component` in `component_parser.py` line ~388):
   - Extracts all `elementParameter` values into `config_raw`
   - Calls `_map_component_parameters('tFileInputRaw', config_raw)`
   - Since `tFileInputRaw` has NO explicit mapping in `_map_component_parameters`, it falls through to the **default else clause** (line ~384-386) which returns the raw config unmodified
   - This means the initial config contains ALL raw Talend parameters (FILENAME, AS_STRING, ENCODING, DIE_ON_ERROR, LABEL, UNIQUE_NAME, etc.) with no filtering or renaming
   - Phase 1 applies Java expression marking (`mark_java_expression`) to string values containing expressions

2. **Phase 2** (`converter.py` line ~335-336):
   - Calls `parse_t_file_input_raw(node, component)` which **overwrites** `component['config']` keys
   - Extracts only 4 parameters: `filename`, `as_string`, `encoding`, `die_on_error`
   - Parses directly from the XML node, re-extracting parameters that were already extracted in Phase 1

**Critical observation**: Phase 1 populates config with ALL raw parameters under their Talend names (e.g., `FILENAME`, `AS_STRING`). Phase 2 then adds Python-named equivalents (`filename`, `as_string`) but does NOT remove the Talend-named originals. The resulting config dictionary contains **both** Talend-named and Python-named keys for the same parameters -- for example, both `FILENAME` and `filename` will be present. The engine ignores the Talend-named keys, so there is no functional bug, but it is wasteful and could confuse debugging.

### 4.2 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_t_file_input_raw()` in `component_parser.py` lines 2104-2118) with explicit `elif component_type == 'tFileInputRaw'` dispatch in `converter.py` line 335-336. This is the recommended pattern per STANDARDS.md.

**Converter flow**:
1. `converter.py:_parse_component()` matches `tFileInputRaw` at line 335
2. Calls `self.component_parser.parse_t_file_input_raw(node, component)` at line 336
3. Parser extracts 4 parameters directly from XML `elementParameter` nodes
4. Schema is extracted generically from `<metadata connector="FLOW">` nodes via `parse_base_component()` (Phase 1)

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filename` | 2107 | Quotes stripped via `.strip('"')`. **Does NOT apply `mark_java_expression()`** -- Java expressions in filenames will not be resolved. |
| 2 | `AS_STRING` | Yes | `as_string` | 2108 | Converted to boolean. Maps Talend's Mode dropdown partially (string=True, bytes=False). **Stream mode not distinguished.** |
| 3 | `ENCODING` | Yes | `encoding` | 2109 | Quotes stripped. Defaults to `'UTF-8'`. Matches Talend default for this component. |
| 4 | `DIE_ON_ERROR` | Yes | `die_on_error` | 2110 | Converted to boolean. Defaults to `false`. Matches Talend default. |
| 5 | `MODE` (Stream) | **Partial** | -- | -- | Only `AS_STRING` is extracted. The "Stream file" third mode option is **not distinguished** from "Read as string". |
| 6 | `TSTATCATCHER_STATS` | No | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 7 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 4 of 6 runtime-relevant parameters extracted (67%). 2 are missing: Stream mode distinction and tStatCatcher.

### 4.3 Schema Extraction

Schema extraction happens generically in `parse_base_component()` (Phase 1):

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` -- e.g., `content`, `raw_data` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |

**Critical**: The engine's `FileInputRaw._process()` **completely ignores the schema**. It always creates a DataFrame with a hardcoded column name `'content'` (line 129), regardless of what the schema defines. The schema is extracted by the converter but never consumed by the engine.

### 4.4 Expression Handling

**Phase 1 Java expression marking**: During `parse_base_component()`, the generic loop applies `mark_java_expression()` to string values. If `FILENAME` contains a Java expression (e.g., `context.input_dir + "/data.raw"`), Phase 1 would mark it with the `{{java}}` prefix.

**Phase 2 overwrite problem**: `parse_t_file_input_raw()` extracts `FILENAME` fresh from the XML node and does a simple `strip('"')`. It does NOT apply `mark_java_expression()`. Phase 2's `filename` value overwrites the properly marked value from Phase 1.

**Result**: If the FILENAME contains a Java expression, Phase 2 will overwrite the properly marked value from Phase 1 with an unmarked version. The engine's `_resolve_java_expressions()` looks for the `{{java}}` marker prefix, so unmarked expressions will NOT be resolved.

**Context variable handling**: Simple `context.var` references (without Java operators like `+`) are resolved by `BaseComponent.execute()` via `context_manager.resolve_dict()`. This path works correctly because it operates on the final config after both phases, and does not depend on the `{{java}}` marker.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FIR-001 | **P1** | **Stream mode not distinguished**: The `AS_STRING` boolean only captures two of the three Talend modes. "Stream file" mode (real-time file monitoring) has no representation in the extracted config. While streaming is an advanced feature, any Talend job using it will silently fall back to string-read behavior. The converter should extract the `MODE` parameter value (`STRING`, `BYTE_ARRAY`, `STREAM`) and map it to a three-valued config key. |
| CONV-FIR-002 | **P2** | **Java expression marking bypassed**: `parse_t_file_input_raw` extracts `FILENAME` directly from the XML node with `strip('"')`, bypassing the `mark_java_expression()` step from Phase 1. If the filename is a Java expression like `context.input_dir + "/data.raw"`, it will not be properly marked for resolution. The engine's `_resolve_java_expressions()` requires the `{{java}}` prefix. Should add: `filename = self.expr_converter.mark_java_expression(filename)`. |
| CONV-FIR-003 | **P1** | **Converter maps to `TFileInputRaw` with leading `T`**: In `component_parser.py` line 27, the mapping is `'tFileInputRaw': 'TFileInputRaw'`. This preserves the Talend `t` prefix as an uppercase `T`. Other components follow the pattern of dropping the `t` prefix entirely (e.g., `'tFileInputDelimited': 'FileInputDelimited'`, `'tFileCopy': 'FileCopy'`). While the engine compensates by registering both `TFileInputRaw` and `tFileInputRaw` as aliases (engine.py lines 80-81), this inconsistency could cause lookup failures if only the standard `FileInputRaw` name is used. |
| CONV-FIR-004 | **P3** | **Duplicate config keys**: Phase 1 populates both Talend-named keys (`FILENAME`, `AS_STRING`, `ENCODING`, `DIE_ON_ERROR`, `LABEL`, etc.) and Phase 2 adds Python-named duplicates (`filename`, `as_string`, `encoding`, `die_on_error`). The config dictionary is polluted with unused keys. No functional impact but complicates debugging and increases serialized JSON size. |
| CONV-FIR-006 | **P1** | **Converter crashes with AttributeError on missing XML parameter nodes**: Lines 2107-2110 chain `.find(...).get(...)` with no null checks. If any of the `elementParameter` nodes (`FILENAME`, `AS_STRING`, `ENCODING`, `DIE_ON_ERROR`) are absent from the Talend XML, `.find()` returns `None` and the subsequent `.get()` call raises `AttributeError: 'NoneType' object has no attribute 'get'`. The converter should guard each `.find()` result before calling `.get()`, or use a safe extraction helper. This is a crash-path bug that will surface on any non-standard or hand-edited Talend XML missing expected parameters. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read file as string | **Yes** | High | `_process()` line 118 | Uses Python `open(path, 'r', encoding=encoding)` -- correct |
| 2 | Read file as bytes array | **Yes** | High | `_process()` line 121 | Uses `open(path, 'rb')` -- correct |
| 3 | Stream file mode | **No** | N/A | -- | No real-time file monitoring/streaming implementation |
| 4 | Encoding support | **Yes** | High | `_process()` line 118 | Passed to `open()` as `encoding=` parameter |
| 5 | Die on error (true) | **Yes** | High | `_process()` line 144 | Re-raises the original exception with `raise` |
| 6 | Die on error (false) | **Yes** | Medium | `_process()` line 148-149 | Returns empty DataFrame. But `ERROR_MESSAGE` not set. |
| 7 | Single-row output | **Yes** | High | `_process()` line 129 | `pd.DataFrame([{'content': content}])` -- always 1 row |
| 8 | Schema column naming | **No** | N/A | -- | Column is hardcoded as `'content'` -- ignores schema-defined names |
| 9 | `FILENAME_PATH` GlobalMap | **No** | N/A | -- | Not set. Talend sets `{id}_FILENAME_PATH` after execution. |
| 10 | `ERROR_MESSAGE` GlobalMap | **No** | N/A | -- | Not set on error. Talend sets `{id}_ERROR_MESSAGE` when die_on_error is unchecked. |
| 11 | tStatCatcher Statistics | **No** | N/A | -- | Not implemented (base engine limitation) |
| 12 | NB_LINE statistics | **Yes** | Medium | `_process()` line 132 | Set via `_update_stats(1, 1, 0)` -- handled by BaseComponent. Note: Talend does NOT expose NB_LINE for this component, but v1 does. |
| 13 | Empty file -> single row | **Yes** | High | `_process()` line 118-119 | `file.read()` on empty file returns `""`, which creates 1 row with empty string. Correct. |
| 14 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 15 | Java expression support | **Partial** | Low | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers, but CONV-FIR-002 means filenames with expressions are not marked. |
| 16 | File existence check | **No** | N/A | -- | No `os.path.exists()` pre-check. Relies on `open()` raising `FileNotFoundError`. This is acceptable but differs from `FileInputDelimited` which checks first. |
| 17 | Binary content integrity | **Yes** | High | `_process()` line 121-122 | `open(path, 'rb')` preserves all bytes including null bytes. |
| 18 | Line ending preservation | **Yes** | High | `_process()` line 118-119 | `open()` without `newline=` parameter uses universal newline mode by default, which may convert `\r\n` to `\n`. **Potential issue**: Python's default text mode converts `\r\n` to `\n` on all platforms. Talend's Java `FileReader` preserves `\r\n` on all platforms. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIR-001 | **P1** | **`{id}_FILENAME_PATH` GlobalMap not set**: Talend produces this After variable containing the resolved file path. Downstream components or triggers referencing `globalMap.get("{id}_FILENAME_PATH")` will get null. This is required for audit trails and conditional logic in production jobs. The fix is straightforward: `self.global_map.put(f"{self.id}_FILENAME_PATH", file_path)` after successful read. |
| ENG-FIR-002 | **P1** | **`{id}_ERROR_MESSAGE` GlobalMap not set**: When `die_on_error=false` and an error occurs, Talend sets `{id}_ERROR_MESSAGE` so downstream error-handling flows can inspect it. The v1 engine logs the error but does not store it in GlobalMap. Conditional triggers checking `globalMap.get("{id}_ERROR_MESSAGE") != null` will not fire. |
| ENG-FIR-003 | **P1** | **`die_on_error` defaults to `False`**: While this matches Talend's default, it means file-not-found errors are silently swallowed by default. This is correct behavior but catches operators off-guard. Unlike most components where errors stop the job, `tFileInputRaw` silently continues. The engine correctly implements this, but it is a behavioral note for production monitoring. |
| ENG-FIR-004 | **P2** | **Hardcoded column name `'content'`**: The output DataFrame always uses column name `'content'` (line 129). In Talend, the column name is defined by the schema editor and can be anything (e.g., `raw_data`, `file_blob`, `xml_payload`). Downstream `tMap` or `tExtractXMLField` components expecting a differently-named column will fail with `KeyError`. |
| ENG-FIR-005 | **P2** | **No "Stream file" mode**: Talend's third mode provides real-time file monitoring where content is read character-by-character as it appears. The v1 engine has no equivalent. Jobs using this mode will silently read the file as a string instead, missing the streaming/monitoring behavior. |
| ENG-FIR-006 | **P2** | **Python text mode may convert line endings**: Python's `open()` in text mode (`'r'`) uses universal newline translation by default. On all platforms, `\r\n` is converted to `\n`, and `\r` is converted to `\n`. Talend's Java `FileReader` preserves the original line endings. For files where exact line ending preservation matters (e.g., CRLF in Windows files), the v1 engine may produce different content. This can be fixed by using `open(path, 'r', newline='', encoding=encoding)` to disable newline translation. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_FILENAME_PATH` | Yes (official) | **No** | -- | Not implemented. Required for audit trails. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. Required for error-handling flows. |
| `{id}_NB_LINE` | No (not standard for tFileInputRaw) | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | V1 sets this uniformly via BaseComponent, but Talend does not expose it for tFileInputRaw. Behavioral difference, but harmless. |
| `{id}_NB_LINE_OK` | No (not standard for tFileInputRaw) | **Yes** | Same mechanism | Same note as NB_LINE. |
| `{id}_NB_LINE_REJECT` | No (not standard for tFileInputRaw) | **Yes** | Same mechanism | Always 0. Same note as NB_LINE. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

### 5.4 Output Shape Analysis

**Talend output**: Single row, single column. Column name and type defined by schema. Column type depends on mode: `id_String` for string mode, `id_byte[]` for bytes mode.

**V1 output**:
```python
result_df = pd.DataFrame([{'content': content}])  # line 129
```
- Always 1 row, 1 column named `'content'`
- Column type: `object` (Python `str` or `bytes` depending on `as_string`)
- No schema enforcement on the output

**Gap**: If the Talend job's schema defines the column as `raw_data` (type `id_String`), a downstream tMap referencing `row.raw_data` will be converted to `row['raw_data']` by the converter, which will raise `KeyError` because the actual column is named `content`.

**Error output shape**:
```python
return {'main': pd.DataFrame()}  # line 149
```
- Empty DataFrame with NO columns
- Differs from a DataFrame with a `'content'` column but zero rows
- Downstream components may fail differently on empty input vs. error input

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIR-001 | **P0** | `file_input_raw.py` lines 76-94, called at line 126 | **`debug_content()` always executes at INFO level**: The `debug_content()` method is called unconditionally on every successful string read (line 126: `if isinstance(content, str): self.debug_content(content)`). This method logs 5-6 INFO-level messages per execution including raw `repr()` of content (line 82), content display (line 83), line ending detection (lines 86-91), and line break counts (line 94). In production, this means every file read produces a burst of debug diagnostic output at INFO level, flooding logs with content previews and line-ending analysis. This is a **debug artifact left in production code**. Per `STANDARDS.md` Section "Logging Standards", detailed variable values and flow tracing should use `DEBUG` level, not `INFO`. Additionally, this may expose sensitive file content (credentials, PII, tokens) in production logs. |
| BUG-FIR-002 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileInputRaw, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-FIR-003 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FIR-004 | **P1** | `file_input_raw.py` line 149 | **Error DataFrame has no columns**: When `die_on_error=false` and an error occurs, the method returns `pd.DataFrame()` which has no columns at all. This differs from the success DataFrame which has a `'content'` column. Downstream components expecting a `'content'` column will get a `KeyError` on the error-path DataFrame instead of an empty-but-correctly-shaped DataFrame. Should be `pd.DataFrame(columns=['content'])` or use schema-derived column name. |
| BUG-FIR-005 | **P3** | `file_input_raw.py` line 142 | **Error stats record 0 rejected but should record 0 OK**: On error, `_update_stats(1, 0, 0)` records 1 row read, 0 OK, 0 rejected. The NB_LINE_REJECT stays 0. In Talend, a file error is not a "rejected row" -- it is a component failure. So 0 reject is technically correct, but it means `NB_LINE != NB_LINE_OK + NB_LINE_REJECT` (1 != 0 + 0), which violates the invariant expected by downstream stat consumers. Should either record (0, 0, 0) since no row was actually produced, or (1, 0, 1) to account for the failed attempt. **Downgraded from P1 to P3**: Talend's tFileInputRaw does not expose NB_LINE statistics as standard GlobalMap variables, so no downstream consumer expects this invariant for this component. |
| BUG-FIR-008 | **P1** | `file_input_raw.py` lines 76-94, `_process()` binary path | **Binary mode has zero diagnostic logging**: When `as_string=False`, the component reads the file in binary mode but produces no diagnostic output whatsoever -- no length, no type, no preview is logged. The `debug_content()` call at line 126 is gated by `if isinstance(content, str)`, so bytes content silently bypasses all diagnostics. Additionally, `debug_content()` is type-unsafe for bytes: if the `isinstance` guard were ever removed or relaxed, calling `content.count('\n')` and `content.count('\r')` on `bytes` would raise `TypeError` because these methods expect `bytes` arguments when called on `bytes` objects (i.e., `content.count(b'\n')` not `content.count('\n')`). There should be at minimum a `logger.debug(f"[{self.id}] Read {len(content)} bytes in binary mode")` for the bytes path. |
| BUG-FIR-009 | **P2** | `src/v1/engine/base_component.py` | **`validate_schema()` defined on BaseComponent but never called by `execute()` or any component**: The `validate_schema()` method is defined in the base class (referenced in Section 1 Key Files) and individual components may override it, but no part of the execution lifecycle -- neither `BaseComponent.execute()` nor any component's `_process()` -- invokes it. Schemas extracted by the converter are stored in config but never validated at runtime. This means schema definitions are dead metadata across the entire engine. **Cross-cutting**: Affects all components that define or inherit `validate_schema()`, not just FileInputRaw. |

### 6.2 Dead Code

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| DEAD-FIR-001 | **P1** | `file_input_raw.py` lines 46-74 | **`_validate_config()` is never called**: The method is defined and performs useful validation (checks `filename` required, validates `encoding` type, validates `as_string` type, validates `die_on_error` type). However, it is never invoked. `BaseComponent.execute()` does not call `_validate_config()`. `FileInputRaw._process()` does not call it. No external caller invokes it. The validation is dead code. A missing `filename` config will only fail later at `open(None, 'r')` with an obscure `TypeError: expected str, bytes or os.PathLike object, not NoneType` instead of the clear `"Missing required config: 'filename'"` message. |
| DEAD-FIR-002 | **P1** | `file_input_raw.py` line 76 | **`debug_content()` should not exist as a production method**: This is a debugging utility that was useful during development but should be either removed or gated behind a `logger.isEnabledFor(logging.DEBUG)` check. Its presence as a named method with `logger.info()` calls suggests it was intended to be temporary. |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIR-001 | **P2** | **Converter maps to `TFileInputRaw` with leading `T`**: In `component_parser.py` line 27, the mapping is `'tFileInputRaw': 'TFileInputRaw'`. Other components follow the pattern of dropping the `t` prefix entirely (e.g., `'tFileInputDelimited': 'FileInputDelimited'`, `'tFileCopy': 'FileCopy'`). The engine compensates by registering both `TFileInputRaw` and `tFileInputRaw` as aliases (engine.py lines 80-81), but the inconsistency could confuse developers. |
| NAME-FIR-002 | **P2** | **Config key `as_string` vs Talend `MODE` / `AS_STRING`**: The Talend parameter is `AS_STRING` which is a derived boolean from the `MODE` dropdown. Using `as_string` as the config key obscures the fact that Talend actually has three modes (string, bytes, stream), not two. A more accurate key might be `mode` with values `'string'`, `'bytes'`, `'stream'`. |
| NAME-FIR-003 | **P3** | **Config key `filename` vs convention `filepath`**: Other file components use `filepath` (e.g., `FileInputDelimited`, `FileOutputDelimited`). `FileInputRaw` uses `filename`. This inconsistency means developers cannot assume a standard key name for file paths across components. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIR-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FIR-002 | **P2** | "Logging Standards: DEBUG for detailed values" (STANDARDS.md) | `debug_content()` logs raw file content preview, type information, line ending analysis, and character counts at INFO level instead of DEBUG level. |
| STD-FIR-003 | **P3** | "Docstrings should document behavioral variations" (STANDARDS.md) | `_process()` docstring (lines 97-106) documents the return dict but does not mention the `die_on_error` behavior, the `as_string` mode, or the encoding parameter. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FIR-001 | **P3** | **No path traversal protection**: `file_path` from config is used directly with `open()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FIR-002 | **P3** | **Content logged at INFO level**: `debug_content()` logs the first 200 characters of file content at INFO level (lines 82-83). If the file contains sensitive data (credentials, PII, tokens, API keys), this content will appear in production logs. This is both a security concern and a logging-standards violation. |

### 6.6 Exception Handling

| ID | Priority | Issue |
|----|----------|-------|
| EXC-FIR-001 | **P2** | **Overly broad exception catch**: Line 138 catches `Exception` which includes programming errors (`TypeError`, `AttributeError`, `IndexError`) that should always propagate regardless of `die_on_error`. The intent of `die_on_error=false` is to survive IO errors (`FileNotFoundError`, `UnicodeDecodeError`, `PermissionError`), not to mask implementation bugs. Should catch `(FileNotFoundError, IOError, UnicodeDecodeError, OSError, PermissionError)` specifically. |

### 6.7 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | **INCORRECT**: `debug_content()` uses INFO for debug diagnostics. Should be DEBUG. `_process()` INFO for milestones is correct. |
| Start/complete logging | `_process()` logs start (line 113) and completion (line 134) at INFO -- correct |
| Sensitive data | **VIOLATION**: `debug_content()` logs first 200 chars of content at INFO level. May contain credentials/PII. |
| No print statements | No `print()` calls -- correct |
| Error logging | Line 139 logs at ERROR with component ID, file path, and error detail -- correct |
| Warning on graceful degradation | Line 148 logs at WARNING when returning empty result -- correct |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use `ConfigurationError` or `FileOperationError` from `exceptions.py`. Uses bare `raise` to re-raise original exception. This preserves the original traceback which is good, but loses the structured exception hierarchy. |
| Exception chaining | Not used. The bare `raise` re-raises the caught exception directly. No `raise ... from e` pattern. |
| `die_on_error` handling | Single try/except block handles all errors. Correct for this simple component. |
| No bare `except` | All except clauses specify `Exception` -- correct, but overly broad (see EXC-FIR-001). |
| Error messages | Include component ID and file path -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct (but wrong shape, see BUG-FIR-004) |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `Optional[pd.DataFrame]` for `input_data` -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional`, `List[str]` -- correct |
| Missing | `debug_content()` parameter `content: str` is typed -- correct |

---

## 7. Performance & Memory

### 7.1 Memory Profile

The component reads the **entire file into memory** in a single `file.read()` call (line 119 for strings, line 122 for bytes). This is correct behavior for tFileInputRaw (Talend does the same), but has implications:

- For a 1 GB text file, Python will allocate ~1 GB for the string content, plus ~1 GB for the DataFrame cell, plus overhead for the pandas Index and metadata. Total: ~2.1 GB.
- For binary mode, `bytes` objects have less overhead but still require the full file size in memory.
- The `debug_content()` call at line 126 creates additional temporary string slices (`content[:200]`) and calls `repr()` which creates yet another string copy. For extremely large files, `content.count('\n')` and `content.count('\r')` each scan the entire string, adding two full-string scans to the read cost.

### 7.2 Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIR-001 | **P1** | **No large-file protection**: There is no file size check before reading. A multi-gigabyte file will be read entirely into memory, potentially causing `MemoryError`. Talend's Java implementation has similar behavior (the whole file is read), but the Python memory overhead is higher due to Unicode string representation. Consider adding a warning when file size exceeds a threshold (e.g., 1 GB) or supporting chunked reading for very large files. The `BaseComponent` has a `MEMORY_THRESHOLD_MB = 3072` constant for streaming mode selection, but `FileInputRaw._process()` does not leverage it. |
| PERF-FIR-002 | **P2** | **Unconditional `debug_content()` call**: Even when logging is set to WARNING or ERROR level, `debug_content()` is called and performs string operations (line counting, repr generation, substring slicing) that are discarded when the logger suppresses the output. For a 1 GB file, `content.count('\n')` and `content.count('\r')` each scan the entire string -- that is 2 GB of scanning just for debug output that may be suppressed. The method should be gated: `if logger.isEnabledFor(logging.DEBUG):`. |
| PERF-FIR-003 | **P3** | **DataFrame overhead for single value**: Creating a `pd.DataFrame([{'content': content}])` for a single value introduces significant overhead: pandas index allocation, column metadata, dtype inference. For a simple key-value result, a lighter structure could suffice. However, this matches the engine's DataFrame-centric architecture, so changing it would require broader refactoring. Not actionable in isolation. |

### 7.3 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | NOT implemented. The entire file is always read into memory. |
| Memory threshold | `BaseComponent.MEMORY_THRESHOLD_MB = 3072` exists but is never checked by `FileInputRaw`. |
| File handle cleanup | Uses `with` statement for proper file handle cleanup -- correct. |
| Temporary allocations | `debug_content()` creates temporary string slices (`content[:200]`) and `repr()` copies -- minor but unnecessary in production. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputRaw` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No test for `parse_t_file_input_raw()` found |

**Key finding**: The v1 engine has ZERO tests for this component. All 148 lines of v1 engine code are completely unverified.

### 8.2 Testing Issues

| ID | Priority | Issue |
|----|----------|-------|
| TEST-FIR-001 | **P0** | **Zero test coverage**: No unit tests exist for `FileInputRaw`. The component has no automated verification of any feature, including the most basic file reading. Any regression will go undetected. |
| TEST-FIR-002 | **P1** | **No converter test**: `parse_t_file_input_raw` is untested. The parameter extraction from XML (FILENAME, AS_STRING, ENCODING, DIE_ON_ERROR) is not verified. The Java expression marking bypass (CONV-FIR-002) would have been caught by a converter test. |

### 8.3 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Read text file as string | P0 | Create a temp file with known content, read with `as_string=True`, verify `result['main']` has 1 row and content matches exactly |
| 2 | Read binary file | P0 | Create a temp file with binary data (including null bytes), read with `as_string=False`, verify content is `bytes` type and matches |
| 3 | Missing file + die_on_error=True | P0 | Point to non-existent file with `die_on_error=True`, verify exception raised |
| 4 | Missing file + die_on_error=False | P0 | Point to non-existent file with `die_on_error=False`, verify empty DataFrame returned and no exception |
| 5 | UTF-8 encoding | P0 | Read file with UTF-8 characters (accented, CJK, emoji), verify content preserved |
| 6 | Empty file | P0 | Read a zero-byte file, verify single row with empty string `""` (NOT zero rows) |
| 7 | Statistics after success | P0 | Verify `stats['NB_LINE'] == 1`, `stats['NB_LINE_OK'] == 1`, `stats['NB_LINE_REJECT'] == 0` |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | ISO-8859-1 encoding | P1 | Read file with ISO-8859-1 encoding containing non-UTF8 characters, verify no `UnicodeDecodeError` |
| 9 | Wrong encoding + die_on_error=True | P1 | Read UTF-8 file with `encoding='ASCII'` and non-ASCII chars, verify `UnicodeDecodeError` raised |
| 10 | Wrong encoding + die_on_error=False | P1 | Same but with `die_on_error=False`, verify empty DataFrame returned |
| 11 | Statistics after failure | P1 | Verify stats reflect error state correctly |
| 12 | Output column name | P1 | Verify output DataFrame column is named `'content'` (current behavior) |
| 13 | Content integrity - Windows line endings | P1 | Read file with `\r\n` endings, verify they are preserved (or document conversion behavior) |
| 14 | Binary content integrity - null bytes | P1 | Read file with null bytes `\x00` in bytes mode, verify all bytes preserved |
| 15 | Context variable in filename | P1 | Set `filename` to `${context.input_dir}/file.txt`, verify context resolution |
| 16 | Large file (>100MB) | P1 | Verify no crash and reasonable memory behavior |
| 17 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | Permission denied | P2 | Point to a file without read permission, verify appropriate error behavior |
| 19 | Symbolic link | P2 | Read a symlinked file, verify content is from the target |
| 20 | File path with spaces | P2 | Read from path containing spaces, verify correct handling |
| 21 | File path with Unicode chars | P2 | Read from path with accented/CJK characters, verify correct handling |
| 22 | Very large file (>1GB) | P2 | Verify behavior and memory usage for large files |
| 23 | Concurrent reads | P2 | Multiple `FileInputRaw` instances reading different files simultaneously |

#### Converter Tests

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 24 | XML extraction | P0 | Create a tFileInputRaw XML node, verify `parse_t_file_input_raw` extracts all 4 parameters correctly |
| 25 | Boolean conversion | P1 | Verify `AS_STRING="true"` becomes `True`, `"false"` becomes `False` |
| 26 | Quote stripping | P1 | Verify `FILENAME='"path/to/file"'` becomes `path/to/file` |
| 27 | Default values | P1 | Verify missing parameters use correct defaults (`as_string=True`, `encoding='UTF-8'`, `die_on_error=False`) |
| 28 | Java expression in filename | P1 | Verify that Java expressions in `FILENAME` are properly handled (currently broken per CONV-FIR-002) |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIR-001 | Bug (Code Quality) | `debug_content()` always logs at INFO level -- debug artifact in production code. Logs raw file content preview and line-ending diagnostics on every successful file read. Violates STANDARDS.md logging standards. Security risk if files contain sensitive data. |
| BUG-FIR-002 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FIR-003 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FIR-001 | Testing | Zero unit tests for `FileInputRaw`. All 148 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIR-001 | Converter | Stream mode not distinguished. Only two of three Talend modes are captured. `AS_STRING` boolean cannot represent the three-mode choice. |
| CONV-FIR-003 | Converter | Converter maps to `TFileInputRaw` with leading `T`, inconsistent with all other components that drop the `t` prefix. |
| CONV-FIR-006 | Converter (Crash) | Converter crashes with `AttributeError` on missing XML parameter nodes. Lines 2107-2110 chain `.find(...).get(...)` with no null checks. |
| DEAD-FIR-001 | Code Quality | `_validate_config()` is never called. Dead code providing false sense of safety. Missing filename will cause obscure `TypeError` instead of clear error. |
| DEAD-FIR-002 | Code Quality | `debug_content()` method is a development artifact that should not exist in production. |
| ENG-FIR-001 | Feature Gap | `{id}_FILENAME_PATH` GlobalMap variable not set. Downstream audit/trigger flows broken. |
| ENG-FIR-002 | Feature Gap | `{id}_ERROR_MESSAGE` GlobalMap variable not set. Error-handling flows broken. |
| BUG-FIR-004 | Bug | Error DataFrame has no columns. Should have `'content'` column for consistent schema. |
| BUG-FIR-008 | Bug | Binary mode has zero diagnostic logging. `debug_content()` is type-unsafe for bytes. |
| PERF-FIR-001 | Performance | No large-file protection. Multi-GB files will be read entirely into memory with no warning. |
| TEST-FIR-002 | Testing | No converter test. `parse_t_file_input_raw` is untested. Java expression marking bypass would have been caught. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIR-002 | Converter | Java expression marking bypassed in `parse_t_file_input_raw`. Filenames with Java expressions won't resolve. |
| ENG-FIR-004 | Feature Gap | Hardcoded column name `'content'` ignores schema-defined output column names. Breaks downstream components expecting differently-named columns. |
| ENG-FIR-005 | Feature Gap | "Stream file" mode not implemented. Jobs using it silently degrade. |
| ENG-FIR-006 | Feature Gap | Python text mode may convert `\r\n` to `\n`. Talend preserves original line endings. |
| EXC-FIR-001 | Code Quality | Overly broad `except Exception` masks programming errors when `die_on_error=False`. |
| BUG-FIR-009 | Bug (Cross-Cutting) | `validate_schema()` defined on BaseComponent but never called by `execute()` or any component. Schemas are dead metadata across entire engine. |
| NAME-FIR-001 | Naming | Converter maps to `TFileInputRaw` (with T prefix), inconsistent with other components. |
| NAME-FIR-002 | Naming | Config key `as_string` does not represent three-mode choice. |
| STD-FIR-001 | Standards | `_validate_config()` not integrated into component lifecycle per standards. |
| STD-FIR-002 | Standards | `debug_content()` violates logging level standards (detailed values at INFO). |
| PERF-FIR-002 | Performance | `debug_content()` performs string operations even when logging is suppressed. For large files, scans entire string twice for line-ending counts. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIR-004 | Converter | Duplicate config keys from Phase 1 residual. No functional impact. |
| BUG-FIR-005 | Bug | Error stats: `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=0` violates `NB_LINE == NB_LINE_OK + NB_LINE_REJECT` invariant. Downgraded from P1: Talend's tFileInputRaw does not expose NB_LINE stats, so no downstream consumer expects this invariant. |
| NAME-FIR-003 | Naming | Config key `filename` inconsistent with `filepath` used by other file components. |
| STD-FIR-003 | Standards | `_process()` docstring lacks behavioral variation documentation. |
| SEC-FIR-001 | Security | No path validation on filename. Defense-in-depth only. |
| SEC-FIR-002 | Security | Content logged at INFO level may expose sensitive data. |
| PERF-FIR-003 | Performance | DataFrame overhead for single value (not actionable in isolation). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 3 bugs (1 component, 2 cross-cutting), 1 testing |
| P1 | 11 | 3 converter (incl. CONV-FIR-006 crash), 2 dead code, 2 engine, 2 bugs (incl. BUG-FIR-008 binary diagnostics), 1 performance, 1 testing |
| P2 | 11 | 1 converter, 3 engine, 1 exception, 1 bug cross-cutting (BUG-FIR-009 validate_schema dead metadata), 2 naming, 2 standards, 1 performance |
| P3 | 7 | 1 converter, 1 bug (BUG-FIR-005 downgraded from P1), 1 naming, 1 standards, 2 security, 1 performance |
| **Total** | **33** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix BUG-FIR-001**: Change all `logger.info()` calls in `debug_content()` to `logger.debug()`, and gate the call: `if logger.isEnabledFor(logging.DEBUG): self.debug_content(content)`. Alternatively, remove `debug_content()` entirely and add a single `logger.debug(f"[{self.id}] Content length: {len(content)}, type: {type(content).__name__}")`. **Impact**: Stops log flooding and sensitive data exposure. **Risk**: Very low (logging only).

2. **Fix BUG-FIR-002** (Cross-cutting): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components. **Risk**: Very low (log message only).

3. **Fix BUG-FIR-003** (Cross-cutting): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

4. **Create unit test suite** (TEST-FIR-001): Implement at minimum the 7 P0 test cases listed in Section 8.3. These cover: basic text read, binary read, missing file handling (both die_on_error modes), UTF-8 encoding, empty file, and statistics tracking. Without these, no v1 engine behavior is verified.

### Short-Term (Hardening)

5. **Wire up `_validate_config()`** (DEAD-FIR-001): Add a call to `_validate_config()` at the beginning of `_process()`:
   ```python
   errors = self._validate_config()
   if errors:
       error_msg = f"Invalid configuration: {'; '.join(errors)}"
       logger.error(f"[{self.id}] {error_msg}")
       if die_on_error:
           raise ConfigurationError(error_msg)
       return {'main': pd.DataFrame(columns=[column_name])}
   ```

6. **Fix ENG-FIR-004**: Use schema-defined column name instead of hardcoded `'content'`:
   ```python
   output_schema = self.config.get('schema', {}).get('output', [])
   column_name = output_schema[0]['name'] if output_schema else 'content'
   result_df = pd.DataFrame([{column_name: content}])
   ```

7. **Fix ENG-FIR-001 / ENG-FIR-002**: Set GlobalMap variables after execution:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_FILENAME_PATH", file_path)
   ```
   And in the error handler:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```

8. **Fix CONV-FIR-002**: In `parse_t_file_input_raw`, apply `mark_java_expression()` to the extracted filename:
   ```python
   filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
   filename = self.expr_converter.mark_java_expression(filename)
   ```

9. **Fix EXC-FIR-001**: Narrow the exception catch:
   ```python
   except (FileNotFoundError, IOError, UnicodeDecodeError, OSError, PermissionError) as e:
   ```

10. **Fix NAME-FIR-001 / CONV-FIR-003**: Change converter mapping from `'tFileInputRaw': 'TFileInputRaw'` to `'tFileInputRaw': 'FileInputRaw'`. Optionally remove the `TFileInputRaw` alias from engine.py line 80 (keep only `tFileInputRaw` and `FileInputRaw`).

11. **Fix BUG-FIR-004**: Return correctly-shaped empty DataFrame on error:
    ```python
    return {'main': pd.DataFrame(columns=[column_name])}
    ```

### Long-Term (Feature Parity)

12. **Implement CONV-FIR-001**: Add a `mode` config key with three values: `'string'`, `'bytes'`, `'stream'`. The converter should extract the actual `MODE` parameter from Talend XML:
    ```python
    mode_param = node.find('.//elementParameter[@name="MODE"]')
    if mode_param is not None:
        mode_value = mode_param.get('value', 'STRING')
        component['config']['mode'] = mode_value.lower()
    ```

13. **Fix ENG-FIR-006**: Preserve original line endings by opening with `newline=''`:
    ```python
    with open(file_path, 'r', encoding=encoding, newline='') as file:
        content = file.read()
    ```

14. **Add large-file warning** (PERF-FIR-001): Check file size with `os.path.getsize()` before reading:
    ```python
    import os
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > self.MEMORY_THRESHOLD_MB:
        logger.warning(f"[{self.id}] File is {file_size_mb:.0f} MB, may cause MemoryError")
    ```

15. **Implement stream mode** (ENG-FIR-005): Add file-watching/streaming mode using Python's file monitoring capabilities for jobs that depend on real-time file reading. This is low priority since stream mode is rarely used in batch ETL.

16. **Create converter test** (TEST-FIR-002): Build tests for `parse_t_file_input_raw` verifying XML extraction, boolean conversion, quote stripping, and default values.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 2104-2118
def parse_t_file_input_raw(self, node, component: Dict) -> Dict:
    """Parse tFileInputRaw specific configuration"""
    # Parse file path
    filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
    as_string = node.find('.//elementParameter[@name="AS_STRING"]').get('value', 'true').lower() == 'true'
    encoding = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8').strip('"')
    die_on_error = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

    # Update component configuration
    component['config']['filename'] = filename
    component['config']['as_string'] = as_string
    component['config']['encoding'] = encoding
    component['config']['die_on_error'] = die_on_error

    return component
```

**Notes on this code**:
- Line 2107: `.strip('"')` removes surrounding quotes from the filename. Does NOT handle escaped quotes within the filename.
- Line 2107: **Does NOT apply `mark_java_expression()`**. Java expressions in filenames will not be properly marked for resolution.
- Line 2108: `AS_STRING` is a boolean derived from the `MODE` dropdown. `MODE=STRING` -> `AS_STRING=true`, `MODE=BYTE_ARRAY` -> `AS_STRING=false`. The `STREAM` mode is not captured.
- Line 2109: Default `'UTF-8'` matches Talend's default for tFileInputRaw (unlike tFileInputDelimited which defaults to ISO-8859-15).
- Line 2110: Default `'false'` matches Talend's default for tFileInputRaw. This component defaults to NOT dying on error, which is unusual.

---

## Appendix B: Engine Class Structure

```
FileInputRaw (BaseComponent)
    Constants:
        (none -- all defaults are inline in _process())

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        debug_content(content: str) -> None      # DEBUG ARTIFACT -- logs at INFO level
        _process(input_data) -> Dict[str, Any]   # Main entry point

    Config Keys Consumed:
        'filename'     (str)   -- file path, required
        'as_string'    (bool)  -- True=text, False=binary, default True
        'encoding'     (str)   -- character encoding, default 'UTF-8'
        'die_on_error' (bool)  -- stop on error, default False

    Outputs:
        {'main': pd.DataFrame}  -- single row, single column named 'content'
        (on error with die_on_error=False: {'main': pd.DataFrame()})

    Statistics Updated:
        NB_LINE: 1 (always, even on error)
        NB_LINE_OK: 1 on success, 0 on error
        NB_LINE_REJECT: 0 (always)
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filename` | Mapped | -- |
| `AS_STRING` / `MODE` | `as_string` | Mapped (partial) | P1 (add three-mode support) |
| `ENCODING` | `encoding` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `MODE` (Stream) | -- | **Not Mapped** | P1 (stream mode not distinguished) |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| `LABEL` | -- | Not needed | -- (cosmetic) |

---

## Appendix D: Detailed Code Analysis

### `_validate_config()` (Lines 46-74)

This method validates:
- `filename` is present in config (required)
- `encoding` is a non-empty string (if present)
- `as_string` is a boolean (if present)
- `die_on_error` is a boolean (if present)

**Not validated**: encoding name validity (e.g., `codecs.lookup(encoding)` would verify), file path format, file existence.

**Critical**: This method is never called. Even if it were, the caller would need to check the returned error list and raise exceptions or handle errors appropriately. No caller does this.

### `debug_content()` (Lines 76-94)

This method performs 6 operations on every string file read:
1. Logs content length at INFO level
2. Logs content type at INFO level (always `<class 'str'>` -- redundant)
3. Logs first 200 chars via `repr()` at INFO level (may contain sensitive data)
4. Logs first 200 chars as display at INFO level (may contain sensitive data)
5. Detects line ending type (`\r\n`, `\n`, `\r`) and logs at INFO level
6. Counts all `\n` and `\r` occurrences and logs at INFO level

For a 1 GB file, steps 5 and 6 scan the entire string three times (`'\r\n' in content`, `content.count('\n')`, `content.count('\r')`), adding approximately 3 GB of string scanning just for diagnostic output.

The `elif` chain in line ending detection (lines 86-91) means files with mixed line endings only report the first match. A file with both `\r\n` and standalone `\n` will report "Windows" only.

### `_process()` (Lines 96-149)

The main processing method:
1. Extract config values with defaults and type conversion (lines 108-111)
2. Log file reading start (line 113)
3. Read file in text or binary mode (lines 115-122)
4. Call `debug_content()` for string content (lines 125-126) -- **unconditional**
5. Create single-row DataFrame with hardcoded `'content'` column (line 129)
6. Update stats: 1 read, 1 OK, 0 reject (line 132)
7. Log completion (line 134)
8. Return result dict (line 136)
9. On error: log error, update stats (1, 0, 0), raise if die_on_error, else return empty DF (lines 138-149)

**Notable omissions**:
- No `_validate_config()` call
- No file existence pre-check
- No schema column name usage
- No GlobalMap variable setting for FILENAME_PATH/ERROR_MESSAGE
- No file size check before reading

---

## Appendix E: Edge Case Analysis

### Edge Case 1: Empty file (0 bytes)

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 1 row with empty string `""` (string mode) or empty byte array `b""` (bytes mode). NB_LINE=1. |
| **V1** | `file.read()` on empty file returns `""` for text or `b""` for binary. Creates `pd.DataFrame([{'content': ''}])`. 1 row. Stats (1, 1, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: Missing file + die_on_error=True

| Aspect | Detail |
|--------|--------|
| **Talend** | Job stops with `FileNotFoundException`. |
| **V1** | `open(None, 'r')` raises `TypeError` (if filename is None) or `FileNotFoundError` (if filename is a path). `die_on_error=True` re-raises. |
| **Verdict** | CORRECT (but error type differs: `TypeError` for None filename vs Talend's always `FileNotFoundException`) |

### Edge Case 3: Missing file + die_on_error=False

| Aspect | Detail |
|--------|--------|
| **Talend** | Component outputs empty result. Sets `{id}_ERROR_MESSAGE`. |
| **V1** | Catches exception, logs error and warning, returns `pd.DataFrame()` (empty, no columns). Does NOT set ERROR_MESSAGE. |
| **Verdict** | PARTIAL -- empty result is correct, but ERROR_MESSAGE not set and DataFrame has wrong shape (no columns) |

### Edge Case 4: Encoding mismatch (UTF-8 file read as ASCII)

| Aspect | Detail |
|--------|--------|
| **Talend** | With die_on_error=true: `UnsupportedEncodingException`. With false: empty result + ERROR_MESSAGE. |
| **V1** | With die_on_error=true: `UnicodeDecodeError`. With false: empty DataFrame + warning logged. |
| **Verdict** | CORRECT (error type name differs but behavior matches) |

### Edge Case 5: Binary file read as string (wrong mode)

| Aspect | Detail |
|--------|--------|
| **Talend** | May produce garbled text or encoding error depending on file content. |
| **V1** | `open(path, 'r', encoding='UTF-8')` will raise `UnicodeDecodeError` for non-UTF-8 binary content, or produce garbled text for coincidentally valid UTF-8 bytes. |
| **Verdict** | MATCHES Talend behavior |

### Edge Case 6: Very large file (multi-GB)

| Aspect | Detail |
|--------|--------|
| **Talend** | Limited by JVM heap size. `OutOfMemoryError` if file exceeds heap. |
| **V1** | Limited by system memory. `MemoryError` if file exceeds available RAM. No warning before attempting. |
| **Verdict** | MATCHES Talend behavior, but no preemptive warning |

### Edge Case 7: File with Windows line endings (\r\n)

| Aspect | Detail |
|--------|--------|
| **Talend** | Preserves `\r\n` as-is in the output string. |
| **V1** | Python's default text mode uses universal newline translation: `\r\n` is converted to `\n`. Content will differ from Talend. |
| **Verdict** | GAP -- line endings may be modified. Fix: use `newline=''` parameter. |

### Edge Case 8: File path with spaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `open()` handles spaces correctly on all platforms. |
| **Verdict** | CORRECT |

### Edge Case 9: File path is None (missing filename config)

| Aspect | Detail |
|--------|--------|
| **Talend** | Design-time validation prevents this. At runtime: `FileNotFoundException`. |
| **V1** | `self.config.get('filename')` returns `None`. `open(None, 'r')` raises `TypeError: expected str, bytes or os.PathLike object, not NoneType`. Not a clear error message. |
| **Verdict** | GAP -- `_validate_config()` would catch this, but it is never called. |

### Edge Case 10: File path is empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | `FileNotFoundException` with clear message. |
| **V1** | `open('', 'r')` raises `FileNotFoundError: [Errno 2] No such file or directory: ''`. Reasonable but could be clearer. |
| **Verdict** | CORRECT (error message could be better) |

### Edge Case 11: NaN / empty string in content

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- file content is read as-is. A file containing the text "NaN" or "NULL" produces exactly that string. |
| **V1** | `file.read()` returns the exact content. No pandas `keep_default_na` issue because content is not parsed by pandas (it is directly assigned as a cell value). |
| **Verdict** | CORRECT |

### Edge Case 12: File content containing pandas-special strings ("NA", "NULL", "None")

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns exact file content as-is. "NA" stays "NA". |
| **V1** | Content is assigned directly to DataFrame cell via `pd.DataFrame([{'content': content}])`. pandas does NOT apply `keep_default_na` or NaN conversion on explicit cell assignment. The string "NA" stays as "NA". |
| **Verdict** | CORRECT |

### Edge Case 13: Context variable resolving to empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | `FileNotFoundException` with the empty path. |
| **V1** | `context_manager.resolve_dict()` resolves `${context.var}` to `""` if context value is empty. `open('', 'r')` raises `FileNotFoundError`. |
| **Verdict** | CORRECT |

### Edge Case 14: Binary content in DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Byte array stored in output column of type `id_byte[]`. |
| **V1** | `bytes` object stored in DataFrame cell. pandas stores it as `object` dtype. Downstream components expecting string operations on this column will fail with `AttributeError`. |
| **Verdict** | CORRECT for storage, but downstream type expectations may differ |

### Edge Case 15: Permission denied

| Aspect | Detail |
|--------|--------|
| **Talend** | `SecurityException` or `IOException`. |
| **V1** | `PermissionError: [Errno 13] Permission denied`. Caught by broad `except Exception`. |
| **Verdict** | CORRECT (exception type differs but behavior matches) |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileInputRaw`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FIR-002 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FIR-003 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| DEAD-FIR-001 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called by base class. ALL components with validation logic have dead validation. |
| BUG-FIR-009 | **P2** | `base_component.py` | `validate_schema()` defined on BaseComponent but never called by `execute()` or any component. Schemas are dead metadata across entire engine. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-FIR-001 -- `debug_content()` at INFO level

**File**: `src/v1/engine/components/file/file_input_raw.py`
**Lines**: 76-94 (method definition), 126 (call site)

**Option A -- Minimal fix (change log level and gate call)**:
```python
# Line 126: Gate the call
if logger.isEnabledFor(logging.DEBUG):
    self.debug_content(content)

# Lines 80-94: Change all logger.info to logger.debug
def debug_content(self, content: str) -> None:
    logger.debug(f"[{self.id}] Content length: {len(content)}")
    logger.debug(f"[{self.id}] Content type: {type(content)}")
    logger.debug(f"[{self.id}] First 200 chars (raw): {repr(content[:200])}")
    logger.debug(f"[{self.id}] First 200 chars (display): {content[:200]}")
    # ... rest of method with logger.debug
```

**Option B -- Recommended fix (remove method, add single debug line)**:
```python
# Replace lines 125-126 with:
logger.debug(f"[{self.id}] Read {len(content)} chars from {file_path}")
```

**Impact**: Stops log flooding, removes sensitive data exposure, removes unnecessary string scanning overhead. **Risk**: Very low.

---

### Fix Guide: BUG-FIR-002 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FIR-003 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Lines**: 26-28

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

### Fix Guide: ENG-FIR-004 -- Hardcoded column name

**File**: `src/v1/engine/components/file/file_input_raw.py`
**Line**: 129

**Current**:
```python
result_df = pd.DataFrame([{'content': content}])
```

**Fix**:
```python
# Get column name from schema, default to 'content'
output_schema = self.config.get('schema', {}).get('output', [])
column_name = output_schema[0]['name'] if output_schema else 'content'
result_df = pd.DataFrame([{column_name: content}])
```

**Impact**: Allows downstream components to reference schema-defined column names. **Risk**: Low. Requires verifying schema is present in config (may not be for manually created configs).

---

### Fix Guide: CONV-FIR-002 -- Java expression marking

**File**: `src/converters/complex_converter/component_parser.py`
**Line**: 2107

**Current**:
```python
filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
```

**Fix**:
```python
filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
filename = self.expr_converter.mark_java_expression(filename)
```

**Impact**: Enables Java expression resolution in filenames. **Risk**: Low (mark_java_expression is idempotent for non-expression values).

---

## Appendix H: Converter-to-Engine Contract Analysis

### Config Key Contract

The converter's `parse_t_file_input_raw` produces:

```python
{
    'filename': '<string>',        # File path (quotes stripped)
    'as_string': True/False,       # Boolean
    'encoding': '<string>',        # Encoding name (quotes stripped)
    'die_on_error': True/False     # Boolean
}
```

The engine's `FileInputRaw._process` consumes:

```python
file_path = self.config.get('filename')              # Required
as_string = self.config.get('as_string', True)        # Optional, default True
encoding = self.config.get('encoding', 'UTF-8')       # Optional, default UTF-8
die_on_error = self.config.get('die_on_error', False)  # Optional, default False
```

**Contract analysis**: The converter always produces all 4 keys, and the engine has defaults for all of them. The contract is **satisfied** for normal operation.

**Edge case**: If the converter fails to extract `filename` (e.g., XML parsing error), it defaults to `''` (empty string), not `None`. The engine would then try `open('', 'r')` which raises `FileNotFoundError: [Errno 2] No such file or directory: ''`. This is a reasonable error, but `_validate_config()` (if called) would give a clearer message.

### Phase 1 Residual Keys

After both parsing phases, the config dictionary also contains these Phase 1 residual keys:

| Key | Source | Used by Engine? |
|-----|--------|-----------------|
| `FILENAME` | Raw Talend parameter | No |
| `AS_STRING` | Raw Talend parameter | No |
| `ENCODING` | Raw Talend parameter | No |
| `DIE_ON_ERROR` | Raw Talend parameter | No |
| `LABEL` | Component label | No |
| `UNIQUE_NAME` | Component ID | No |
| Various others | All elementParameters | No |

These residual keys are harmless but increase config size and could confuse debugging.

---

## Appendix I: Comparison with Other File Input Components

| Feature | tFileInputRaw (V1) | tFileInputDelimited (V1) | tFileInputFullRow (V1) | tFileInputXML (V1) |
|---------|---------------------|--------------------------|------------------------|---------------------|
| Basic reading | Yes | Yes | Yes | Yes |
| Schema column naming | **No** (hardcoded 'content') | Yes | Yes | Yes |
| Encoding support | Yes | Yes | Yes | Yes |
| Die on error | Yes (default False) | Yes (default False) | Yes | Yes |
| GlobalMap FILENAME | **No** | **No** | **No** | **No** |
| GlobalMap ERROR_MESSAGE | **No** | **No** | **No** | **No** |
| `_validate_config()` called | **No** (dead code) | **No** (dead code) | Yes | N/A |
| Debug artifacts | **Yes** (INFO-level) | No | No | No |
| V1 Unit tests | **No** | **No** | **No** | **No** |
| Config key for filepath | `filename` | `filepath` | `filepath` | `filepath` |
| Error specificity | Broad `except Exception` | Multiple specific catches | Specific IO catches | Specific catches |
| Converter naming | `TFileInputRaw` (with T) | `FileInputDelimited` | `FileInputFullRowComponent` | `FileInputXML` |

**Observations**:
1. The GlobalMap FILENAME/ERROR_MESSAGE gap and lack of unit tests are systemic issues across ALL file input components. This suggests architectural omissions rather than component-specific oversights.
2. The `debug_content()` debug artifact at INFO level is unique to `FileInputRaw` and is not present in any other file input component. This component appears to have been written earlier in the development cycle with temporary debugging code that was never removed.
3. The `filename` config key (instead of `filepath`) and the `TFileInputRaw` converter name (with leading `T`) are unique inconsistencies not seen in other components.
4. The `_validate_config()` dead-code pattern is shared with `FileInputDelimited` but not with `FileInputFullRow` (which calls it).

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs with schema column name != 'content' | **Critical** | Any job where tFileInputRaw schema defines column as `raw_data`, `xml_payload`, etc. | Must fix hardcoded column name (ENG-FIR-004) before migrating |
| Jobs referencing `{id}_FILENAME_PATH` downstream | **High** | Jobs with audit/logging using FILENAME_PATH | Must set FILENAME_PATH in globalMap |
| Jobs with Java expressions in FILENAME | **High** | Jobs using `context.dir + "/file.raw"` style expressions | Must fix CONV-FIR-002 (Java expression marking) |
| Jobs using `debug_content()` log level in monitoring | **Medium** | All jobs -- INFO logs will be noisy | Must fix BUG-FIR-001 before production |
| Jobs with globalMap initialized | **Critical** | ALL jobs with GlobalMap | Must fix BUG-FIR-002 and BUG-FIR-003 (cross-cutting crashes) |
| Jobs reading Windows files (CRLF) | **Medium** | Jobs where exact line endings matter | Must fix ENG-FIR-006 (newline translation) |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using Stream mode | Low | Rare in batch ETL; silently falls back to string mode |
| Jobs using tStatCatcher | Low | Monitoring feature, not data flow |
| Jobs with simple context variable filenames | Low | Context resolution works correctly for simple `${context.var}` references |
| Jobs reading small text files | Low | Core functionality works correctly |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting `_update_global_map()` and `GlobalMap.get()` crashes, plus `debug_content()` log level). These affect ALL components and must be fixed first.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which schema column names are used and whether FILENAME_PATH is referenced downstream.
3. **Phase 3**: Implement schema column name support (ENG-FIR-004) and GlobalMap variable setting (ENG-FIR-001, ENG-FIR-002).
4. **Phase 4**: Fix Java expression marking (CONV-FIR-002) and narrow exception handling (EXC-FIR-001).
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Compare output content byte-for-byte. Verify downstream component compatibility.

---

## Appendix K: Talend XML Example

A typical tFileInputRaw node in Talend's `.item` XML file:

```xml
<node componentName="tFileInputRaw" componentVersion="0.101"
      offsetLabelX="0" offsetLabelY="0" posX="128" posY="96">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputRaw_1"/>
  <elementParameter field="FILE" name="FILENAME" value="&quot;/data/input/payload.xml&quot;"/>
  <elementParameter field="CLOSED_LIST" name="MODE" value="STRING"/>
  <elementParameter field="CHECK" name="AS_STRING" value="true"/>
  <elementParameter field="ENCODING_TYPE" name="ENCODING" value="&quot;UTF-8&quot;"/>
  <elementParameter field="CHECK" name="DIE_ON_ERROR" value="false"/>
  <metadata connector="FLOW" name="tFileInputRaw_1">
    <column name="content" type="id_String" nullable="true"/>
  </metadata>
</node>
```

The converter's `parse_t_file_input_raw` would extract:
- `filename` = `/data/input/payload.xml`
- `as_string` = `True`
- `encoding` = `UTF-8`
- `die_on_error` = `False`

The schema extraction would capture:
- Column `content`, type `str` (converted from `id_String`), nullable `True`

### Example with Java expression filename:

```xml
<elementParameter field="FILE" name="FILENAME"
    value="context.input_dir+&quot;/payload.xml&quot;"/>
```

Phase 1 (`parse_base_component`): Detects Java expression (`+` operator), marks with `{{java}}`.
Phase 2 (`parse_t_file_input_raw`): Re-extracts from XML, strips quotes, produces `context.input_dir+"/payload.xml"` **without** `{{java}}` marker. **Bug**: The Java expression will not be resolved at runtime.

### Example with bytes mode:

```xml
<elementParameter field="CLOSED_LIST" name="MODE" value="BYTE_ARRAY"/>
<elementParameter field="CHECK" name="AS_STRING" value="false"/>
```

Converter extracts: `as_string = False`. Engine reads in binary mode. Correct.

### Example with stream mode (not supported):

```xml
<elementParameter field="CLOSED_LIST" name="MODE" value="STREAM"/>
<elementParameter field="CHECK" name="AS_STRING" value="true"/>
```

Converter extracts: `as_string = True` (same as string mode). Engine reads as string. **Gap**: Stream mode behavior (real-time monitoring) is lost.

---

## Appendix L: Cross-Component Integration Analysis

### Typical Usage Patterns

tFileInputRaw is typically used in these job patterns:

1. **XML/JSON ingestion**: `tFileInputRaw` -> `tExtractXMLField` / `tExtractJSONFields`
2. **REST API payload**: `tFileInputRaw` (bytes mode) -> `tREST` (file content as request body)
3. **Template processing**: `tFileInputRaw` -> `tReplace` / `tMap` (string substitution)
4. **Binary file handling**: `tFileInputRaw` (bytes mode) -> `tFileOutputRaw` (copy/transform)
5. **File content logging**: `tFileInputRaw` -> `tLogRow`
6. **Cloud upload**: `tFileInputRaw` (bytes mode) -> `tGoogleDrivePut` / `tS3Put`

### Integration Risks

| Pattern | Risk | Severity | Description |
|---------|------|----------|-------------|
| `tFileInputRaw` -> `tExtractXMLField` | **High** | P1 | If schema defines column as `xml_content` but engine outputs `content`, tExtractXMLField will fail with KeyError on the expected column name |
| `tFileInputRaw` -> `tMap` | **High** | P1 | tMap expressions referencing `row.raw_data` (schema-defined name) will fail because column is actually `content` |
| `tFileInputRaw` -> Any downstream | **Medium** | P1 | If downstream references `globalMap.get("{id}_FILENAME_PATH")`, it gets null |
| Conditional triggers | **Medium** | P1 | If trigger condition checks `globalMap.get("{id}_ERROR_MESSAGE") != null`, it never fires because ERROR_MESSAGE is never set |
| `tFileInputRaw` -> `tLogRow` | **Low** | P3 | Works correctly (single row, single column) but `debug_content()` floods logs before tLogRow even gets the data |

### Dependency on BaseComponent

`FileInputRaw` relies on these `BaseComponent` features:

| Feature | Used? | Notes |
|---------|-------|-------|
| `execute()` orchestration | Yes | Entry point; handles mode detection, context resolution, java expression resolution |
| `_update_stats()` | Yes | Called at lines 132 and 142 |
| `_update_global_map()` | Yes | Called automatically by `execute()` after `_process()` returns. **Has latent bug (BUG-FIR-002)**. |
| `_resolve_java_expressions()` | Yes (implicitly) | Called by `execute()` if `java_bridge` is set. Works if expressions are properly marked. |
| `context_manager.resolve_dict()` | Yes (implicitly) | Called by `execute()` to resolve `${context.*}` in config |
| `_validate_config()` | **No** | Defined but never called by base or self |
| `validate_schema()` | **No** | Not called; output schema not enforced |
| `_auto_select_mode()` | Yes (implicitly) | Called by `execute()` but always returns BATCH for None input_data |

---

## Appendix M: Complete Recommended Parser Implementation

The following is the recommended replacement for the current `parse_t_file_input_raw()` method. It addresses CONV-FIR-001 (stream mode), CONV-FIR-002 (Java expression marking), and adds proper MODE extraction.

```python
def parse_t_file_input_raw(self, node, component: Dict) -> Dict:
    """
    Parse tFileInputRaw specific configuration from Talend XML node.

    Extracts ALL Talend parameters:
        FILENAME (str): File path. Mandatory.
        MODE (str): Read mode: STRING, BYTE_ARRAY, STREAM. Default STRING.
        AS_STRING (bool): Derived from MODE. True for STRING/STREAM.
        ENCODING (str): File encoding (string mode only). Default "UTF-8".
        DIE_ON_ERROR (bool): Stop on error. Default false.
    """
    config = component['config']

    # Extract filename with Java expression marking
    filename_param = node.find('.//elementParameter[@name="FILENAME"]')
    if filename_param is not None:
        filename = filename_param.get('value', '').strip('"')
        filename = self.expr_converter.mark_java_expression(filename)
        config['filename'] = filename

    # Extract MODE (three-valued: STRING, BYTE_ARRAY, STREAM)
    mode_param = node.find('.//elementParameter[@name="MODE"]')
    if mode_param is not None:
        mode_value = mode_param.get('value', 'STRING').upper()
        config['mode'] = mode_value.lower()  # 'string', 'byte_array', 'stream'

    # Extract AS_STRING (backward compat, derived from MODE)
    as_string_param = node.find('.//elementParameter[@name="AS_STRING"]')
    if as_string_param is not None:
        config['as_string'] = as_string_param.get('value', 'true').lower() == 'true'

    # Extract encoding
    encoding_param = node.find('.//elementParameter[@name="ENCODING"]')
    if encoding_param is not None:
        config['encoding'] = encoding_param.get('value', 'UTF-8').strip('"')

    # Extract die_on_error
    die_param = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
    if die_param is not None:
        config['die_on_error'] = die_param.get('value', 'false').lower() == 'true'

    return component
```

**Key improvements over current implementation**:
1. Applies `mark_java_expression()` to FILENAME (fixes CONV-FIR-002)
2. Extracts `MODE` parameter for three-mode support (fixes CONV-FIR-001)
3. Uses safe `if param is not None` checks to avoid `AttributeError` on missing parameters
4. Preserves `as_string` for backward compatibility while adding `mode` key

---

## Appendix N: Detailed Code Walkthrough

### Line-by-Line Analysis of `_process()` (lines 96-149)

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
```
**Line 96**: Correct signature matching `BaseComponent._process()` abstract method. `input_data` is Optional since this is a source component (no upstream input).

```python
    file_path = self.config.get('filename')
```
**Line 108**: Gets `filename` from config. Returns `None` if missing. No validation. If `_validate_config()` were called, this would be caught. Without it, `None` will cause `TypeError` at `open()`.

```python
    as_string = self.config.get('as_string', True)
    encoding = self.config.get('encoding', 'UTF-8')
    die_on_error = self.config.get('die_on_error', False)
```
**Lines 109-111**: Good use of defaults. `as_string=True` matches Talend's default string mode. `encoding='UTF-8'` matches Talend's default for this component (note: differs from tFileInputDelimited which defaults to ISO-8859-15). `die_on_error=False` matches Talend's default for this component (file errors are silently swallowed by default).

```python
    logger.info(f"[{self.id}] Reading raw file: {file_path}")
```
**Line 113**: Appropriate INFO-level log for file operation start. Follows `[{self.id}]` prefix convention. Includes file path for debugging.

```python
    try:
        if as_string:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
        else:
            with open(file_path, 'rb') as file:
                content = file.read()
```
**Lines 115-122**: Core file reading logic. Clean and correct. `with` statement ensures proper file handle cleanup even if `read()` raises an exception. Binary mode correctly omits the encoding parameter. **Potential issue**: Text mode does not pass `newline=''`, so Python's universal newline translation will convert `\r\n` to `\n` and `\r` to `\n`. Talend's Java `FileReader` preserves original line endings.

```python
        if isinstance(content, str):
            self.debug_content(content)
```
**Lines 125-126**: **Problem area**. Called unconditionally for all string reads. Not gated by log level. Produces 5-6 INFO-level log messages per invocation. For a 1 GB file, performs 3 full-string scans (checking for `\r\n` substring, counting `\n`, counting `\r`). Should be `if logger.isEnabledFor(logging.DEBUG): self.debug_content(content)` at minimum, or removed entirely.

```python
        result_df = pd.DataFrame([{'content': content}])
```
**Line 129**: Creates single-row DataFrame with hardcoded column name `'content'`. The list wrapper `[{...}]` is correct -- it creates exactly one row. Scalar string in dict creates one row per dict entry. **Should use schema-defined column name** instead of hardcoded `'content'`.

```python
        self._update_stats(1, 1, 0)
```
**Line 132**: Correct for success: 1 row read, 1 OK, 0 rejected. The NB_LINE always counts 1 since the component reads one file as one "row".

```python
        logger.info(f"[{self.id}] File read complete: 1 file processed successfully")
```
**Line 134**: Appropriate completion log at INFO level. Follows standards.

```python
        return {'main': result_df}
```
**Line 136**: Correct return structure matching BaseComponent contract. The `'main'` key is the standard output key.

```python
    except Exception as e:
        logger.error(f"[{self.id}] Failed to read file {file_path}: {e}")
```
**Line 138-139**: Catches ALL exceptions -- overly broad. Should catch specific IO exceptions. The error log is appropriate: includes component ID, file path, and error message.

```python
        self._update_stats(1, 0, 0)
```
**Line 142**: Stats on error: 1 row attempted, 0 OK, 0 rejected. This means `NB_LINE (1) != NB_LINE_OK (0) + NB_LINE_REJECT (0)`, violating the expected invariant. Should either be `(0, 0, 0)` (no row was produced) or `(1, 0, 1)` (one row attempted, one failed).

```python
        if die_on_error:
            raise
```
**Lines 144-145**: Re-raises the original exception. `raise` without arguments preserves the original traceback, which is the correct pattern. The exception will propagate up through `BaseComponent.execute()` which catches it, sets `ComponentStatus.ERROR`, and re-raises.

```python
        logger.warning(f"[{self.id}] Returning empty result due to error")
        return {'main': pd.DataFrame()}
```
**Lines 148-149**: Returns empty DataFrame on non-fatal error. The warning log is appropriate. **Issue**: `pd.DataFrame()` has NO columns at all, which differs from a DataFrame with a `'content'` column but zero rows. Downstream components expecting a `'content'` column will get different behavior depending on whether the error occurred or the file was empty (which returns 1 row with empty string).

### Line-by-Line Analysis of `debug_content()` (lines 76-94)

```python
def debug_content(self, content: str) -> None:
    logger.info(f"[{self.id}] Content length: {len(content)}")
    logger.info(f"[{self.id}] Content type: {type(content)}")
```
**Lines 76-81**: Content length is useful for debugging. Content type is always `<class 'str'>` since the method is only called after an `isinstance(content, str)` check -- this is redundant information logged at INFO level.

```python
    logger.info(f"[{self.id}] First 200 chars (raw): {repr(content[:200])}")
    logger.info(f"[{self.id}] First 200 chars (display): {content[:200]}")
```
**Lines 82-83**: Logs the first 200 characters of file content. `repr()` shows escape sequences; plain display shows rendered text. **Security risk**: If file contains credentials, API keys, PII, or tokens, the first 200 characters will appear in production logs. This is the most dangerous line in the component.

```python
    if '\r\n' in content:
        logger.info(f"[{self.id}] Contains Windows line endings (\\r\\n)")
    elif '\n' in content:
        logger.info(f"[{self.id}] Contains Unix line endings (\\n)")
    elif '\r' in content:
        logger.info(f"[{self.id}] Contains Mac line endings (\\r)")
```
**Lines 86-91**: Line ending detection. The `elif` chain means mixed line endings (common in real-world files) will only report the first match. A file with both `\r\n` and standalone `\n` will report "Windows" only. The `'\r\n' in content` check scans the entire string for the substring. For a 1 GB file, this is a 1 GB scan just for diagnostic output.

```python
    logger.info(f"[{self.id}] Line break counts: \\n={content.count('\\n')}, \\r={content.count('\\r')}")
```
**Line 94**: Counts ALL occurrences of each line ending character. For a file with 1 million lines, this requires scanning the entire string twice. For a 1 GB file, this is two full-string scans (2 GB of scanning) just for debug logging that will appear at INFO level whether anyone needs it or not.

### Line-by-Line Analysis of `_validate_config()` (lines 46-74)

```python
def _validate_config(self) -> List[str]:
    errors = []
    if 'filename' not in self.config:
        errors.append("Missing required config: 'filename'")
```
**Lines 46-56**: Checks for required `filename`. Correct and useful. Would prevent `TypeError` on `open(None, 'r')`.

```python
    if 'encoding' in self.config:
        encoding = self.config['encoding']
        if not isinstance(encoding, str) or not encoding.strip():
            errors.append("Config 'encoding' must be a non-empty string")
```
**Lines 59-62**: Validates encoding is a non-empty string. Good. But does not validate that the encoding name is actually supported by Python (e.g., `codecs.lookup(encoding)` would verify). An invalid encoding like `'EBCDIC-CP-FI'` would pass validation but fail at `open()`.

```python
    if 'as_string' in self.config:
        as_string = self.config['as_string']
        if not isinstance(as_string, bool):
            errors.append("Config 'as_string' must be a boolean")
```
**Lines 64-67**: Validates `as_string` type. Good.

```python
    if 'die_on_error' in self.config:
        die_on_error = self.config['die_on_error']
        if not isinstance(die_on_error, bool):
            errors.append("Config 'die_on_error' must be a boolean")
```
**Lines 69-72**: Validates `die_on_error` type. Good.

**Overall**: The validation logic is well-written but never executed. It covers type checking for all 4 config keys but does not validate encoding name validity or file path format. Even if it were called, the method only returns a list of error strings -- the caller must check and raise exceptions, but no caller exists.

---

## Appendix O: NaN, Empty String, and Empty DataFrame Behavior

### NaN Handling

| Scenario | Behavior | Correct? |
|----------|----------|----------|
| File content is the literal string "NaN" | Stored as string `"NaN"` in DataFrame cell. Not converted to `float('nan')`. | Correct. `pd.DataFrame([{'content': 'NaN'}])` stores it as a string, not as pandas NA. |
| File content is the literal string "NA" | Stored as string `"NA"`. No NaN conversion. | Correct. No `keep_default_na` issue because content is directly assigned, not parsed by CSV reader. |
| File content is the literal string "NULL" | Stored as string `"NULL"`. | Correct. |
| File content is the literal string "" (empty) | Stored as string `""`. Not converted to NaN. | Correct. Empty file produces 1 row with empty string. |

### Empty String Behavior

| Scenario | Result | Notes |
|----------|--------|-------|
| Empty file (0 bytes) | 1 row with `""` in content column | Correct. `file.read()` on empty file returns `""`. |
| File with only whitespace | 1 row with whitespace string in content column | Correct. No trimming applied. |
| File with only newlines | 1 row with newline string in content column | Correct. Content preserved as-is. |

### Empty DataFrame Behavior

| Scenario | DataFrame Shape | Column Present? | Notes |
|----------|----------------|-----------------|-------|
| Successful read | 1 row x 1 col | Yes (`content`) | Normal case |
| Error + die_on_error=False | 0 rows x 0 cols | **No** | `pd.DataFrame()` has no columns. **BUG** (BUG-FIR-004). Should be `pd.DataFrame(columns=['content'])`. |
| Error + die_on_error=True | N/A (exception raised) | N/A | Exception propagates |

**Impact of missing column on error DataFrame**: Downstream components that check `if 'content' in df.columns` before processing will behave differently for error-path empty DataFrames vs. normal empty results. Components that directly access `df['content']` will get `KeyError` on the error path but `Series` on the normal path.

---

## Appendix P: Component Status and Statistics Lifecycle

### Success Path

```
execute() called
  -> _resolve_java_expressions()     # Resolve {{java}} markers if java_bridge set
  -> context_manager.resolve_dict()   # Resolve ${context.*} variables
  -> _auto_select_mode(None)          # Returns BATCH (input_data is None)
  -> _execute_batch(None)
     -> _process(None)
        -> config extraction (lines 108-111)
        -> logger.info: start (line 113)
        -> open() + read() (lines 115-122)
        -> debug_content() [BUG: always runs at INFO] (line 126)
        -> pd.DataFrame creation (line 129)
        -> _update_stats(1, 1, 0) (line 132)
        -> logger.info: complete (line 134)
        -> return {'main': result_df}
  -> stats['EXECUTION_TIME'] = elapsed
  -> _update_global_map()             # [BUG: will crash if global_map set]
  -> status = ComponentStatus.SUCCESS
  -> result['stats'] = self.stats.copy()
  -> return result
```

### Error Path (die_on_error=False)

```
execute() called
  -> _resolve_java_expressions()
  -> context_manager.resolve_dict()
  -> _auto_select_mode(None) -> BATCH
  -> _execute_batch(None)
     -> _process(None)
        -> config extraction
        -> logger.info: start
        -> open() raises FileNotFoundError/UnicodeDecodeError/etc.
        -> except Exception:
           -> logger.error: failure (line 139)
           -> _update_stats(1, 0, 0) (line 142)
           -> die_on_error is False -> do not raise
           -> logger.warning: returning empty (line 148)
           -> return {'main': pd.DataFrame()}  # [BUG: no columns]
  -> stats['EXECUTION_TIME'] = elapsed
  -> _update_global_map()             # [BUG: will crash]
  -> status = ComponentStatus.SUCCESS   # NOTE: status is SUCCESS even on error!
  -> result['stats'] = self.stats.copy()
  -> return result
```

**Critical observation**: When `die_on_error=False` and an error occurs in `_process()`, the `execute()` method in `BaseComponent` sees a successful return (no exception) and sets `status = ComponentStatus.SUCCESS`. The component appears to have succeeded even though it encountered an error and returned empty results. There is no mechanism to signal "completed with warnings" vs. "completed successfully". This means:
- `COMPONENT_OK` trigger would fire (correct for die_on_error=False, the component did complete)
- `COMPONENT_ERROR` trigger would NOT fire (questionable -- an error did occur)
- `ComponentStatus` is `SUCCESS` (misleading for monitoring)

### Error Path (die_on_error=True)

```
execute() called
  -> _process(None)
     -> open() raises FileNotFoundError
     -> except Exception:
        -> logger.error
        -> _update_stats(1, 0, 0)
        -> die_on_error is True -> raise (re-raises original exception)
  -> execute() catches exception:
     -> status = ComponentStatus.ERROR
     -> error_message = str(e)
     -> _update_global_map()          # [BUG: will crash]
     -> logger.error
     -> raise (propagates to engine)
```

---

## Appendix Q: Comparison with Talend tFileOutputRaw

tFileInputRaw and tFileOutputRaw are complementary components. Understanding tFileOutputRaw helps validate tFileInputRaw behavior:

| Aspect | tFileInputRaw | tFileOutputRaw |
|--------|---------------|----------------|
| Direction | Input (reads file) | Output (writes file) |
| Schema | Single column (user-defined name) | Single column (user-defined name) |
| Modes | String, Bytes, Stream | Append, Create new, Stream |
| Encoding | Configurable (UTF-8 default) | Configurable (UTF-8 default) |
| Die on Error | Default: false | Default: false |
| FILENAME_PATH global | Yes | Yes |
| ERROR_MESSAGE global | Yes | Yes |

**Round-trip expectation**: `tFileInputRaw` (string mode) -> `tMap` (identity) -> `tFileOutputRaw` should produce an identical file. In the v1 engine, line ending conversion (ENG-FIR-006) may break this round-trip for files with `\r\n` endings.

---

*Report generated: 2026-03-21*
*Auditor: Claude Opus 4.6 (automated)*
*Component version: As of commit `dfbc5c5`*
*Engine file: 148 lines | Converter parser: 15 lines | Total audit scope: ~600 lines across 7 files*
