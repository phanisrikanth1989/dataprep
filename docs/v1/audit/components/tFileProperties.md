# Audit Report: tFileProperties / FileProperties

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW

> **Converter Update (2026-03-25)**: Converter section updated to reflect migration from `complex_converter` to `talend_to_v1`. All runtime params now extracted. See CONV-* issues below for status.

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileProperties` |
| **V1 Engine Class** | `FileProperties` |
| **Engine File** | `src/v1/engine/components/file/file_properties.py` (179 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_properties.py` |
| **Converter Dispatch** | `talend_to_v1` registry-based dispatch via `REGISTRY["tFileProperties"]` |
| **Registry Aliases** | `FileProperties`, `tFileProperties` (registered in `src/v1/engine/engine.py` lines 87-88) |
| **Category** | File / Utility |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_properties.py` | Engine implementation (179 lines) |
| `src/converters/talend_to_v1/components/file/file_properties.py` | Dedicated `talend_to_v1` converter for tFileProperties |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports -- line 15 imports `FileProperties`, line 37 in `__all__` |

### Related: tFileInputProperties

| Field | Value |
|-------|-------|
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFileInputProperties'` (line 296-298) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileinputproperties()` (lines 1720-1723) |
| **Engine Registration** | **Not registered** -- `tFileInputProperties` has no alias in `engine.py` |
| **Status** | **Dead code** -- converter dispatch is `pass` (no-op), parser is empty stub, engine has no mapping |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 1 | `talend_to_v1` dedicated parser extracts 4 params (4 config keys). All runtime params mapped. TSTATCATCHER_STATS and LABEL now extracted. Config key naming still ALL CAPS (cross-cutting). |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | Missing `mtime` milliseconds format, `dirname` edge case, no `{id}_ERROR_MESSAGE` globalMap, no schema output validation |
| Code Quality | **Y** | 2 | 4 | 4 | 1 | Cross-cutting base class bugs; TOCTOU race on file existence check; double `getmtime()` syscall yields inconsistent timestamps; no file-type validation (directories accepted); `_validate_config()` called but return value ignored; `datetime.fromtimestamp()` timezone issue |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | MD5 computation reads entire file into memory via 4KB chunks (OK) but no file size guard for multi-GB files |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileProperties Does

`tFileProperties` creates a single-row output flow that displays the main properties of a specified file. It analyzes file metadata -- path information, size, modification time, permissions mode -- and outputs these as a single row with predefined schema columns. The component is commonly used in combination with `tFileList` (connected via an Iterator link) to inspect multiple files in a directory, and the results are typically routed to `tLogRow` for display or `tFileOutputDelimited` for persistence.

**Source**: [tFileProperties Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfileproperties/tfileproperties-standard-properties), [tFileProperties Component (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfileproperties/tfileproperties-component), [tFileProperties -- Talend Skill (ESB 7.x)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfileproperties-talend-open-studio-for-esb-document-7-x/)

**Component family**: File (Utility)
**Available in**: All Talend products (Standard)
**Required JARs**: None (standard Java file I/O only)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor (Read-Only) | Predefined | Read-only schema with 7 predefined columns. Cannot be modified by the user. |
| 3 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Path to the file whose properties will be analyzed. Supports context variables, globalMap references, Java expressions. Commonly fed by `tFileList` via `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`. |
| 4 | Calculate MD5 Hash | `MD5` | Boolean (CHECK) | `false` | When checked, calculates the MD5 hash checksum of the file and adds it as an additional output field. Useful for file integrity verification. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 5 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 6 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Predefined Read-Only Schema

The schema is **read-only** and cannot be modified. It contains 7 predefined columns (8 when MD5 is enabled):

| # | Column Name | Type | Description |
|---|-------------|------|-------------|
| 1 | `abs_path` | String | The absolute path of the file |
| 2 | `dirname` | String | The directory containing the file |
| 3 | `basename` | String | The base name of the file (filename without directory path) |
| 4 | `mode_string` | String | File access permissions as a string representation (e.g., `r`, `w`, `rw`) |
| 5 | `size` | Long | File size measured in bytes |
| 6 | `mtime` | Long | Timestamp indicating when the file was last modified, in **milliseconds** that have elapsed since the Unix epoch (00:00:00 UTC, Jan 1, 1970) |
| 7 | `mtime_string` | String | The date and time the file was last modified in a human-readable format |
| 8 | `md5` | String | MD5 hash checksum of the file (only present when `Calculate MD5 Hash` is enabled) |

**Critical note on `mtime`**: Talend outputs `mtime` in **milliseconds** since epoch (Java `System.currentTimeMillis()` style). Python's `os.path.getmtime()` returns **seconds** since epoch (with fractional part). This is a key behavioral difference.

**Critical note on `mode_string`**: Talend outputs the file mode as a human-readable access string (e.g., `r`, `w`, `rw`). Python's `oct(os.stat().st_mode)` outputs the raw octal permission value (e.g., `0o100644`). This is a format mismatch.

**Critical note on `size`**: The `size` column name is an Oracle reserved keyword. When persisting tFileProperties output to Oracle databases, the column name must be quoted. This is a well-known Talend community issue.

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Single-row output containing all file property columns. Primary data output. |
| `ITERATE` | Input | Iterate | Receives iteration signals, commonly from `tFileList`. Each iteration processes a different file. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Input (Trigger) | Trigger | Conditional trigger with a boolean expression. The component only executes if the condition evaluates to true. |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows output. Always 1 for a successful execution (one file = one row). |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output. Always 1 when successful. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rejected rows. Always 0 for this component (no reject flow). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available when `Die on error` is unchecked. Functions as an After variable (post-execution). |

**Note on file property access via globalMap**: In Talend, individual file properties can be accessed via globalMap using expressions like `((Long)globalMap.get("tFileProperties_1.size"))` or `((String)globalMap.get("tFileProperties_1.basename"))`. The V1 engine does NOT set these per-property globalMap variables -- it only sets the standard NB_LINE statistics.

### 3.6 Behavioral Notes

1. **Single-row output**: This component always produces exactly one row per execution. When used with `tFileList` in an Iterator loop, each iteration produces one row for one file.

2. **Read-only schema**: Unlike most Talend components, the schema is predefined and read-only. Users cannot add, remove, or modify columns. The MD5 column appears automatically when `Calculate MD5 Hash` is checked.

3. **File must exist**: If the specified file does not exist, the component raises an error. There is no built-in "die on error" toggle -- file existence is a hard prerequisite. In Talend, this is typically handled by connecting `tFileExist` before `tFileProperties` in the flow.

4. **Iterator pattern**: The most common usage pattern is `tFileList -> (Iterate) -> tFileProperties -> (Main) -> tLogRow`. The `FILENAME` parameter references the tFileList globalMap variable to get each file's path.

5. **mtime format**: The `mtime` field uses Java millisecond timestamps (e.g., `1616316000000`), not Unix second timestamps (e.g., `1616316000.0`). The `mtime_string` field provides a locale-dependent human-readable format.

6. **mode_string format**: The `mode_string` field in Talend shows human-readable access permissions (e.g., `r`, `w`, `rw` for read, write, read-write). This is NOT the Unix octal permission format.

7. **No REJECT flow**: This component does not have a REJECT output. Errors either cause the job to fail or are captured in `{id}_ERROR_MESSAGE` globalMap variable.

8. **No Die on Error toggle**: Unlike most Talend input components, `tFileProperties` does not have a `DIE_ON_ERROR` checkbox. File not found always causes an error. Error handling is done via SUBJOB_ERROR or COMPONENT_ERROR triggers.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated parser (`src/converters/talend_to_v1/components/file/file_properties.py`) registered via `REGISTRY["tFileProperties"]`. The parser extracts all parameters using safe `_get_str` / `_get_bool` helpers with null-safety.

**Converter flow**:
1. `talend_to_v1` registry dispatches to `file_properties.py` converter function
2. Extracts all runtime parameters using `_get_str()` and `_get_bool()` helpers (null-safe)
3. Maps to engine config keys

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `FILENAME` | Quote-stripped, null-safe. |
| 2 | `MD5` | Yes | `MD5` | Boolean. |
| 3 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Not needed at runtime. |
| 4 | `LABEL` | Yes | `label` | Not needed at runtime (cosmetic). |

**Summary**: 4 of 4 parameters extracted (100%). All runtime-relevant parameters correctly mapped. TSTATCATCHER_STATS and LABEL now extracted.

### 4.2 Schema Extraction

The tFileProperties schema is **read-only** and predefined in Talend. The converter does NOT need to extract schema from XML because the engine class hardcodes the output columns. No schema extraction issues.

### 4.3 Expression Handling

**FILENAME expression handling** (component_parser.py line 1699):
- The parser extracts the raw `FILENAME` value and strips surrounding quotes via `.strip('"')`
- **No Java expression detection**: Unlike other dedicated parsers, `parse_tfileproperties()` does NOT call `mark_java_expression()` on the FILENAME value
- **No context variable wrapping**: Unlike the generic `parse_base_component()` path, there is no `context.` detection or `${context.var}` wrapping
- This means Java expressions and context variables in `FILENAME` are stored as raw strings and depend on the base class `execute()` method's context resolution to handle them

**Limitation**: If `FILENAME` contains a Java expression like `"/data/" + context.dir + "/file.txt"`, the converter stores the raw string. The base class `execute()` resolves `${context.var}` patterns but NOT arbitrary Java expressions unless they are prefixed with `{{java}}`. Since the dedicated parser does not call `mark_java_expression()`, Java expressions in FILENAME will not be resolved.

### 4.4 Config Key Naming Convention

**Critical naming observation**: The converter stores config keys as ALL CAPS (`FILENAME`, `MD5`), matching Talend XML parameter names directly. This differs from the naming convention used by most other components:

| Component | Config Key Style | Examples |
|-----------|-----------------|----------|
| tFileInputDelimited | `snake_case` | `filepath`, `delimiter`, `header_rows` |
| tFileOutputDelimited | `snake_case` | `filepath`, `delimiter`, `append` |
| tFileRowCount | `snake_case` | `filename`, `row_separator`, `encoding` |
| **tFileProperties** | **ALL CAPS** | **`FILENAME`**, **`MD5`** |
| tFileExist | Mixed | `FILENAME` (ALL CAPS) |

The FileProperties engine class reads config keys as ALL CAPS (`self.config.get('FILENAME', '')`, `self.config.get('MD5', False)`) on lines 101-102, so the converter and engine are internally consistent. However, this naming inconsistency across components violates the principle of least surprise and makes the codebase harder to maintain.

### 4.5 tFileInputProperties -- Dead Converter Code

The converter contains two related code paths for a `tFileInputProperties` component:

**Converter dispatch** (converter.py lines 296-298):
```python
elif component_type == 'tFileInputProperties':
    # Add logic for handling tFileInputProperties
    pass
```

**Parser stub** (component_parser.py lines 1720-1723):
```python
def parse_tfileinputproperties(self, node, component: Dict) -> Dict:
    """Parse tFileInputProperties specific configuration"""
    # Add parsing logic here
    return component
```

**Issues with tFileInputProperties**:
1. The converter dispatch uses `pass` -- a complete no-op. The `component` variable is NOT updated.
2. The parser method `parse_tfileinputproperties()` exists but is never called (the dispatch uses `pass` instead of calling it).
3. `tFileInputProperties` is not registered in `engine.py` -- no alias exists, so it cannot be instantiated at runtime.
4. The component_parser.py type map (line 34) maps `tFileProperties` to `FileProperties`, but there is no mapping for `tFileInputProperties`.
5. It is unclear whether `tFileInputProperties` is a distinct Talend component or an alias for `tFileProperties`. The official Talend documentation does not list a component named `tFileInputProperties`.

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FP-001 | ~~P2~~ | **FIXED (2026-03-25)**: `talend_to_v1` parser uses safe extraction helpers. Expression handling delegated to base infrastructure. |
| CONV-FP-002 | ~~P2~~ | **FIXED (2026-03-25)**: `talend_to_v1` parser uses safe extraction helpers. Context variable handling delegated to base infrastructure. |
| CONV-FP-003 | **P2** | **DEFERRED**: Config key naming inconsistency (ALL CAPS vs snake_case) is a cross-cutting concern. Requires coordinated engine + converter update. Deferred to separate task. |
| CONV-FP-004 | **P3** | **DEFERRED**: tFileInputProperties dead code cleanup is out of scope for this converter fix. |
| CONV-FP-005 | ~~P3~~ | **FIXED (2026-03-25)**: `talend_to_v1` parser uses `_get_str()`/`_get_bool()` helpers with null-safety. No `AttributeError` risk. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Extract file absolute path | **Yes** | High | `_process()` line 116 | `os.path.abspath(file_path)` -- correct |
| 2 | Extract directory name | **Yes** | Medium | `_process()` line 117 | `os.path.dirname(file_path)` -- returns empty string `""` for bare filename with no path prefix |
| 3 | Extract basename | **Yes** | High | `_process()` line 118 | `os.path.basename(file_path)` -- correct |
| 4 | Extract mode string | **Yes** | **Low** | `_process()` line 119 | `oct(os.stat(file_path).st_mode)` outputs `"0o100644"` -- Talend outputs `"rw"` or similar human-readable format. **Format mismatch.** |
| 5 | Extract file size | **Yes** | High | `_process()` line 120 | `os.path.getsize(file_path)` returns integer bytes -- matches Talend |
| 6 | Extract modification time | **Yes** | **Low** | `_process()` line 121 | `os.path.getmtime()` returns **seconds** (float). Talend returns **milliseconds** (long). **Unit mismatch.** |
| 7 | Format modification time string | **Yes** | Medium | `_format_time()` line 180 | `strftime('%Y-%m-%d %H:%M:%S')` -- Talend format may differ by locale |
| 8 | Calculate MD5 checksum | **Yes** | High | `_calculate_md5()` line 148 | Chunked reading with 4KB buffer -- correct implementation |
| 9 | File existence check | **Yes** | High | `_process()` line 108 | `os.path.exists(file_path)` before analysis |
| 10 | Single-row output | **Yes** | High | `_process()` line 133 | `pd.DataFrame([file_properties])` creates single-row DF -- correct |
| 11 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 12 | Java expression support | **Partial** | Low | Via `BaseComponent.execute()` line 198 | Only works if expressions are marked with `{{java}}` prefix -- converter does NOT mark them (see CONV-FP-001) |
| 13 | Statistics tracking | **Yes** | High | `_process()` line 130 | `_update_stats(1, 1, 0)` -- always 1 line read, 1 OK, 0 reject |
| 14 | Return as DataFrame | **Yes** | High | `_process()` line 133-139 | `pd.DataFrame([file_properties])` wrapped in `{'main': result_df}` -- correct for pipeline compatibility |
| 15 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not implemented. Talend sets this on error when `Die on error` is unchecked.** |
| 16 | **Per-property globalMap variables** | **No** | N/A | -- | **Not implemented. Talend allows `globalMap.get("tFileProperties_1.size")` etc.** |
| 17 | **Die on Error toggle** | **No** | N/A | -- | **Not configurable. Component always raises exceptions on error.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FP-001 | **P1** | **`mtime` returns seconds instead of milliseconds**: `os.path.getmtime()` returns a float in seconds (e.g., `1616316000.123`). Talend's `mtime` field is a long in milliseconds (e.g., `1616316000123`). Downstream components or jobs relying on the numeric `mtime` value for comparisons, arithmetic, or database storage will produce incorrect results. Should multiply by 1000 and convert to integer: `int(os.path.getmtime(file_path) * 1000)`. |
| ENG-FP-002 | **P1** | **`mode_string` format mismatch**: Engine outputs Python octal string (e.g., `"0o100644"`) via `oct(os.stat().st_mode)`. Talend outputs human-readable permission string (e.g., `"rw"` for read-write). Any downstream component or job that parses or displays `mode_string` will see the wrong format. Should convert to Talend-compatible format using `stat` module constants. |
| ENG-FP-003 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When the component raises an exception, the error message is not stored in globalMap. Downstream error handling flows referencing `((String)globalMap.get("tFileProperties_1_ERROR_MESSAGE"))` will get null. Talend sets this as an After variable. |
| ENG-FP-004 | **P2** | **`dirname` returns empty string for bare filename**: `os.path.dirname("myfile.txt")` returns `""` (empty string). Talend may return the current working directory or the resolved absolute directory. The V1 engine should use `os.path.dirname(os.path.abspath(file_path))` to ensure a meaningful directory is always returned. |
| ENG-FP-005 | **P2** | **`mtime_string` format may differ from Talend**: Engine uses `strftime('%Y-%m-%d %H:%M:%S')` which produces `"2021-03-21 10:00:00"`. Talend's format depends on the JVM locale and may produce different formats (e.g., `"Mar 21, 2021 10:00:00 AM"`). While the V1 format is more standardized, it may cause comparison mismatches in jobs that depend on exact string format. |
| ENG-FP-006 | **P2** | **`datetime.fromtimestamp()` uses local timezone**: `_format_time()` on line 180 calls `datetime.fromtimestamp(timestamp)` which uses the system's local timezone. Talend Java's `new Date(mtime)` also uses local timezone, so this is consistent. However, if the V1 engine runs in a different timezone than the original Talend job server, `mtime_string` values will differ. Consider making timezone configurable or using UTC. |
| ENG-FP-007 | **P3** | **No per-property globalMap variables**: Talend allows accessing individual file properties via globalMap (e.g., `globalMap.get("tFileProperties_1.size")`). V1 only sets NB_LINE statistics. Low priority because most jobs access properties via the FLOW output row, not globalMap. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats(1, 1, 0)` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Always 1. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always 1 when successful. |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Always 0 (no reject flow). |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. Talend sets this as After variable on error. |
| `{id}.abs_path` | Possibly | **No** | -- | Not implemented. Some Talend patterns access per-property values via globalMap. |
| `{id}.size` | Possibly | **No** | -- | Not implemented. Community references show `globalMap.get("tFileProperties_1.size")` usage. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FP-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileProperties, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The entire `execute()` method's try block will raise, meaning no component can successfully complete when a globalMap is provided. |
| BUG-FP-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FP-003 | **P1** | `src/v1/engine/components/file/file_properties.py:60-81` | **`_validate_config()` return value is never checked**: The method returns a `List[str]` of errors but no code path in the class calls it. The base class `BaseComponent` does not call `_validate_config()` either. While the method correctly validates `FILENAME` (required, non-empty) and `MD5` (boolean type check), the validation results are silently discarded. Invalid configurations are not caught until they cause runtime errors in `_process()`. The `_process()` method has its own inline validation (lines 101-110), making `_validate_config()` dead code. |
| BUG-FP-004 | **P1** | `src/v1/engine/components/file/file_properties.py:121` | **`mtime` returns seconds instead of Talend-expected milliseconds**: `os.path.getmtime(file_path)` returns a `float` in seconds (e.g., `1616316000.123`). Talend outputs `mtime` as a `long` in milliseconds (e.g., `1616316000123`). Any downstream component comparing, sorting, or storing `mtime` values will produce incorrect results. This is a silent data corruption issue -- the component produces output without errors, but the values are 1000x smaller than expected. |
| BUG-FP-005 | **P1** | `src/v1/engine/components/file/file_properties.py:108-116` | **TOCTOU race between `os.path.exists()` and `os.stat()`/`getsize()`/`getmtime()`**: File can be deleted, moved, or replaced between the existence check on line 108 and the subsequent `os.stat()`/`os.path.getsize()`/`os.path.getmtime()` calls on lines 119-121. The `os.path.exists()` guard adds false safety -- the code should instead handle `FileNotFoundError` from the actual file operations. The redundant existence check creates a window where the file state can change, making the check misleading. |
| BUG-FP-006 | **P1** | `src/v1/engine/components/file/file_properties.py:121-122` | **`os.path.getmtime()` called twice -- two separate syscalls yield potentially different timestamps**: Line 121 calls `os.path.getmtime(file_path)` to populate the `mtime` field, and line 122 calls `os.path.getmtime(file_path)` again to pass to `_format_time()` for `mtime_string`. If the file is modified between these two calls, `mtime` and `mtime_string` will report different timestamps, producing silently inconsistent output. The result should be captured once and reused for both fields. |
| BUG-FP-007 | **P2** | `src/v1/engine/components/file/file_properties.py:108` | **`os.path.exists()` returns `True` for directories -- no file-type validation**: `os.path.exists()` does not distinguish between files and directories. Passing a directory path causes the metadata extraction to succeed for `abs_path`, `dirname`, `basename`, `mode_string`, `size`, and `mtime`, but triggers `IsADirectoryError` when `_calculate_md5()` calls `open()` on line 160. Even without MD5 enabled, directory metadata is returned as if it were a file, producing misleading output. Should validate with `os.path.isfile()` instead of `os.path.exists()`. |
| BUG-FP-008 | **P2** | `src/v1/engine/components/file/file_properties.py:119` | **`mode_string` format does not match Talend**: `oct(os.stat(file_path).st_mode)` produces Python octal string `"0o100644"`. Talend produces human-readable permission string like `"rw"` (read-write). While this is documented as a format difference rather than a crash, it is effectively a data quality bug -- downstream components expecting Talend's format will receive incompatible data. |
| BUG-FP-009 | **P2** | `src/v1/engine/components/file/file_properties.py:117` | **`dirname` returns empty string for relative paths**: `os.path.dirname("myfile.txt")` returns `""`. The `abs_path` field (line 116) correctly uses `os.path.abspath()`, but `dirname` does NOT use the absolute path as input. Should be `os.path.dirname(os.path.abspath(file_path))` for consistency and to avoid empty values. |
| BUG-FP-010 | **P2** | `src/v1/engine/components/file/file_properties.py:180` | **`datetime.fromtimestamp()` may raise `OSError` for invalid timestamps**: If `os.path.getmtime()` returns an out-of-range value (corrupted filesystem metadata), `datetime.fromtimestamp()` raises `OSError` or `OverflowError`. This exception is not caught specifically -- it falls through to the generic `except Exception` handler on line 144, which wraps it in `FileOperationError`. While the error is handled, the error message does not clearly indicate the cause (timestamp formatting failure). |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FP-001 | **P2** | **ALL CAPS config keys (`FILENAME`, `MD5`)** while most other components use snake_case (`filepath`, `delimiter`, `encoding`). The FileProperties engine class matches this convention (reads `self.config.get('FILENAME')`), so it is internally consistent, but inconsistent with the broader codebase. Compare with `tFileRowCount` which uses lowercase `filename` in its converter (component_parser.py line 1710). |
| NAME-FP-002 | **P3** | **Column names use `snake_case`** (`abs_path`, `dirname`, `basename`, `mode_string`, `mtime_string`) which matches Talend's schema. No issue here -- this is correct. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FP-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists and returns error list (lines 60-81), but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FP-002 | **P2** | "Consistent config key naming across components" | Uses ALL CAPS (`FILENAME`, `MD5`) while most components use snake_case. No formal standard exists for this, but the inconsistency creates maintenance burden. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FP-001 | **P3** | **Comment on line 10**: `import pandas as pd  # Add pandas import` -- the `# Add pandas import` comment is a development artifact. Should be removed. Import is correct; comment is noise. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FP-001 | **P3** | **No path traversal protection**: `FILENAME` from config is used directly with `os.path.exists()`, `os.path.abspath()`, `os.stat()`, and `open()` (for MD5). If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. This would expose file metadata (size, mode, mtime) and MD5 hash of arbitrary files. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FP-002 | **P3** | **MD5 is cryptographically weak**: The component uses `hashlib.md5()` for checksum calculation. MD5 is cryptographically broken and should not be used for security-sensitive integrity checks. However, this matches Talend's behavior (which also uses MD5), and the primary use case is file identity/change detection, not security. No action needed unless security requirements change. |

### 6.6 Logging Quality

The component has good logging throughout:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, DEBUG for details, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 97) and completion with file name and size (lines 135-137) -- correct |
| Sensitive data | File path is logged (not sensitive in Talend context) -- acceptable |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `FileOperationError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern (lines 146, 168) -- correct |
| Separate re-raise for custom exceptions | Lines 141-143 re-raise `ConfigurationError` and `FileOperationError` as-is, avoiding double-wrapping -- correct |
| Generic exception wrapper | Line 144-146 catches `Exception` and wraps in `FileOperationError` -- correct |
| Error messages | Include component ID (via f-string), file path, and error details -- correct |
| No bare `except` | All except clauses specify exception types -- correct |
| MD5-specific error handling | `_calculate_md5()` has its own try/except (lines 161-168) with specific error message -- correct |
| **Missing: Die on Error support** | No `die_on_error` configuration option. Component always raises on error. Should support returning empty DataFrame or partial results when die_on_error=false. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| `_validate_config()` | Returns `List[str]` -- correct |
| `_process()` | Returns `Dict[str, Any]`, takes `Optional[Any]` -- correct |
| `_calculate_md5()` | Returns `str`, takes `str` -- correct |
| `_format_time()` | Returns `str`, takes `float` -- correct |
| Class-level imports | `Dict`, `List`, `Optional`, `Any` from `typing` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FP-001 | **P1** | **MD5 computation on very large files has no size guard**: `_calculate_md5()` reads the entire file in 4KB chunks, which is memory-safe (only 4KB in memory at a time). However, for multi-GB files, the MD5 computation is CPU-intensive and may take minutes. There is no timeout, no progress logging, and no file size warning. A 10GB file would require reading all 10GB sequentially. Should log a warning for files over a configurable threshold (e.g., 1GB) and consider making the chunk size configurable. |
| PERF-FP-002 | **P2** | **`os.stat()` called twice**: Line 119 calls `os.stat(file_path).st_mode` for mode_string, and lines 120-121 call `os.path.getsize()` and `os.path.getmtime()` which internally call `os.stat()` again. Should call `os.stat()` once and extract all fields from the result: `stat_result = os.stat(file_path)` then use `stat_result.st_mode`, `stat_result.st_size`, `stat_result.st_mtime`. This reduces 3 system calls to 1. |
| PERF-FP-003 | **P3** | **DataFrame creation for single-row output**: Creating a `pd.DataFrame` for a single row of metadata is heavyweight. A plain dictionary might be more efficient for downstream components that only need key-value access. However, the DataFrame format is required for pipeline compatibility with components like `tLogRow` and `tFilterRow`, so this is an acceptable tradeoff. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| File metadata extraction | Uses `os.stat()`, `os.path.*` -- O(1) memory, no file content loaded |
| MD5 calculation | 4KB chunked reading (`iter(lambda: f.read(4096), b"")`) -- O(1) memory regardless of file size |
| DataFrame creation | Single-row DataFrame with 7-8 columns -- negligible memory |
| Overall memory profile | Excellent -- only concern is CPU time for MD5 on very large files, not memory |

### 7.2 MD5 Chunk Size Analysis

The MD5 calculation uses a 4KB (4096 byte) chunk size on line 164. While this is memory-safe, it is not optimal for I/O throughput:

| Chunk Size | I/O Calls for 1GB File | Approximate Overhead |
|------------|----------------------|---------------------|
| 4 KB | 262,144 | High (many small reads) |
| 64 KB | 16,384 | Medium |
| 1 MB | 1,024 | Low |
| 8 MB | 128 | Minimal |

A larger chunk size (e.g., 64KB or 1MB) would reduce system call overhead significantly for large files while still maintaining bounded memory usage. The `hashlib.md5().update()` method processes data incrementally regardless of chunk size.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileProperties` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 179 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic file properties extraction | P0 | Analyze a known file, verify all 7 output columns (`abs_path`, `dirname`, `basename`, `mode_string`, `size`, `mtime`, `mtime_string`) are present and correct |
| 2 | MD5 calculation enabled | P0 | Set `MD5=true`, analyze a file with known content, verify MD5 hash matches expected value (e.g., md5 of `"hello\n"` is `b1946ac92492d2347c6235b4d2611184`) |
| 3 | MD5 calculation disabled | P0 | Set `MD5=false`, verify output has 7 columns (no `md5` column) |
| 4 | Missing file | P0 | Provide nonexistent path, verify `FileOperationError` is raised with descriptive message |
| 5 | Statistics tracking | P0 | Verify stats are `NB_LINE=1, NB_LINE_OK=1, NB_LINE_REJECT=0` after successful execution |
| 6 | Empty file (0 bytes) | P0 | Analyze a zero-byte file. Should succeed with `size=0`. MD5 of empty file is `d41d8cd98f00b204e9800998ecf8427e`. |
| 7 | GlobalMap integration | P0 | Provide a GlobalMap instance, verify `{id}_NB_LINE=1` etc. are set after execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | File with spaces in path | P1 | Verify `/path/with spaces/file.txt` is handled correctly for all output columns |
| 9 | Context variable in FILENAME | P1 | `${context.input_dir}/file.txt` should resolve via context manager |
| 10 | Symlink file | P1 | Analyze a symbolic link -- verify `abs_path` resolves to the symlink path (not target) or document behavior |
| 11 | Large file MD5 (>1GB) | P1 | Verify MD5 calculation completes without memory issues on large file |
| 12 | Return type verification | P1 | Verify `_process()` returns `{'main': pd.DataFrame}` with exactly one row |
| 13 | Single-row DataFrame structure | P1 | Verify DataFrame column names match expected schema: `abs_path`, `dirname`, `basename`, `mode_string`, `size`, `mtime`, `mtime_string` |
| 14 | Relative path input | P1 | Pass `"./myfile.txt"` as FILENAME, verify `abs_path` returns full absolute path and `dirname` is meaningful (not empty) |
| 15 | FILENAME with trailing/leading whitespace | P1 | Verify whitespace in config value is handled (stripped or used as-is) |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 16 | Concurrent file analysis | P2 | Multiple FileProperties instances analyzing different files simultaneously |
| 17 | File with special characters in name | P2 | Unicode characters, brackets, parentheses in filename |
| 18 | Read-only file permissions | P2 | Verify component can read properties of a file the user cannot write to |
| 19 | `_validate_config()` correctness | P2 | Call `_validate_config()` directly with missing FILENAME, empty FILENAME, non-boolean MD5 -- verify correct error messages returned |
| 20 | Repeated execution | P2 | Call `execute()` on the same instance twice -- verify stats accumulate or reset correctly |
| 21 | `mtime_string` format | P2 | Verify format is `YYYY-MM-DD HH:MM:SS` for a file with known modification time |
| 22 | Config with missing FILENAME key | P2 | Verify `ConfigurationError` is raised (not `KeyError` or `TypeError`) |
| 23 | Config with empty string FILENAME | P2 | Verify `ConfigurationError` is raised with clear message |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FP-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FP-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FP-001 | Testing | Zero v1 unit tests for this component. All 179 lines of v1 engine code are completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| BUG-FP-003 | Bug | `_validate_config()` exists (60-81) but is never called. 22 lines of dead validation code. Inline validation in `_process()` partially duplicates this. |
| BUG-FP-004 | Bug | `mtime` returns seconds (float) instead of Talend-expected milliseconds (long). Silent data corruption -- values are 1000x smaller than expected. |
| BUG-FP-005 | Bug | TOCTOU race between `os.path.exists()` and `os.stat()`/`getsize()`/`getmtime()`. File can change between check and use. Redundant existence check adds false safety. |
| BUG-FP-006 | Bug | `os.path.getmtime()` called twice (lines 121-122). Two separate syscalls -- if file modified between calls, `mtime` and `mtime_string` report different timestamps. |
| ENG-FP-001 | Engine | `mtime` unit mismatch: seconds vs milliseconds. Downstream components using `mtime` for comparisons/arithmetic will produce incorrect results. |
| ENG-FP-002 | Engine | `mode_string` format mismatch: Python octal `"0o100644"` vs Talend human-readable `"rw"`. Downstream components expecting Talend format will receive incompatible data. |
| ENG-FP-003 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. Downstream error handling flows will get null. |
| PERF-FP-001 | Performance | MD5 computation on multi-GB files has no size guard, no timeout, no progress logging. Could block job execution for minutes with no feedback. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FP-001 | Converter | No Java expression marking on FILENAME. Java expressions like `"/data/" + context.dir` will not be resolved. |
| CONV-FP-002 | Converter | No context variable detection in FILENAME. Simple `context.var` references not wrapped as `${context.var}`. |
| CONV-FP-003 | Converter | Config key naming inconsistency: ALL CAPS (`FILENAME`, `MD5`) vs other components' snake_case (`filepath`, `delimiter`). |
| BUG-FP-007 | Bug | `os.path.exists()` returns `True` for directories. No file-type validation. Passing a directory causes `IsADirectoryError` from MD5 `open()`. |
| BUG-FP-008 | Bug | `mode_string` format incompatible with Talend. Python octal output vs human-readable permission string. |
| BUG-FP-009 | Bug | `dirname` returns empty string for relative paths. Should use `os.path.dirname(os.path.abspath())`. |
| BUG-FP-010 | Bug | `datetime.fromtimestamp()` may raise `OSError` for invalid timestamps. Error message does not clearly indicate timestamp formatting failure. |
| ENG-FP-004 | Engine | `dirname` returns empty string for bare filenames without path prefix. |
| ENG-FP-005 | Engine | `mtime_string` format `YYYY-MM-DD HH:MM:SS` may differ from Talend's locale-dependent format. |
| ENG-FP-006 | Engine | `datetime.fromtimestamp()` uses local timezone. If V1 engine runs in different timezone than Talend server, `mtime_string` values will differ. |
| PERF-FP-002 | Performance | `os.stat()` called 3 times (mode, size, mtime). Should call once and extract all fields. |
| STD-FP-001 | Standards | `_validate_config()` exists but never called. Dead validation code. |
| STD-FP-002 | Standards | Config key naming inconsistency across components. |
| NAME-FP-001 | Naming | ALL CAPS config keys inconsistent with snake_case convention used by other components. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FP-004 | Converter | `tFileInputProperties` is dead code: `pass` dispatch, empty parser stub, no engine alias. |
| CONV-FP-005 | Converter | No `.find()` null safety when extracting FILENAME and MD5 from XML. Will crash with `AttributeError` if XML node missing. |
| ENG-FP-007 | Engine | No per-property globalMap variables (e.g., `tFileProperties_1.size`). Low priority -- most jobs use FLOW output. |
| SEC-FP-001 | Security | No path traversal protection on FILENAME. |
| SEC-FP-002 | Security | MD5 is cryptographically weak. Matches Talend behavior; acceptable for file identity use case. |
| DBG-FP-001 | Debug | `# Add pandas import` comment artifact on line 10. |
| PERF-FP-003 | Performance | DataFrame creation for single-row output is heavyweight. Acceptable for pipeline compatibility. |
| NAME-FP-002 | Naming | Column names use `snake_case` -- correct, matches Talend schema. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 8 | 5 bugs, 2 engine, 1 performance |
| P2 | 14 | 3 converter, 4 bugs, 3 engine, 1 performance, 2 standards, 1 naming |
| P3 | 8 | 2 converter, 1 engine, 2 security, 1 debug, 1 performance, 1 naming |
| **Total** | **33** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FP-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FP-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FP-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic extraction, MD5 enabled/disabled, missing file, statistics, empty file, and GlobalMap integration. Without these, no v1 engine behavior is verified.

4. **Fix `mtime` unit to milliseconds** (BUG-FP-004 / ENG-FP-001): Change line 121 from `os.path.getmtime(file_path)` to `int(os.path.getmtime(file_path) * 1000)`. Also update line 122 to pass the original seconds value to `_format_time()`. **Impact**: Fixes silent data corruption for any job using the `mtime` column numerically. **Risk**: Low (unit conversion only).

5. **Fix `mode_string` format** (ENG-FP-002 / BUG-FP-008): Replace `oct(os.stat(file_path).st_mode)` with a Talend-compatible formatter. Example:
   ```python
   import stat
   mode = os.stat(file_path).st_mode
   perms = ''
   if mode & stat.S_IRUSR: perms += 'r'
   if mode & stat.S_IWUSR: perms += 'w'
   if mode & stat.S_IXUSR: perms += 'x'
   file_properties['mode_string'] = perms
   ```
   **Impact**: Fixes format mismatch for downstream consumers. **Risk**: Low (output format change only).

### Short-Term (Hardening)

6. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FP-003): In the exception handlers of `_process()` (lines 141-146), before re-raising, store the error message:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```
   **Impact**: Enables downstream error handling flows. **Risk**: Very low.

7. **Fix `dirname` for relative paths** (BUG-FP-009 / ENG-FP-004): Change line 117 from `os.path.dirname(file_path)` to `os.path.dirname(os.path.abspath(file_path))`. This ensures `dirname` always returns a meaningful directory path. **Impact**: Fixes empty `dirname` for relative paths. **Risk**: Very low.

8. **Add Java expression marking in converter** (CONV-FP-001): In `parse_tfileproperties()`, after extracting `file_name`, call `mark_java_expression()`:
   ```python
   file_name = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
   file_name = file_name.strip('"')
   # Add Java expression detection
   file_name = self.expr_converter.mark_java_expression(file_name) if hasattr(self, 'expr_converter') else file_name
   ```
   **Impact**: Enables Java expression resolution for FILENAME. **Risk**: Low.

9. **Add context variable detection in converter** (CONV-FP-002): After extracting `file_name`, check for `context.` patterns:
   ```python
   if 'context.' in file_name and not detect_java_expression(file_name):
       file_name = f"${{{file_name}}}"  # Wrap as ${context.var}
   ```
   **Impact**: Enables context variable resolution for simple FILENAME expressions. **Risk**: Low.

10. **Wire up `_validate_config()` or remove it** (BUG-FP-003 / STD-FP-001): Either add a call to `_validate_config()` at the beginning of `_process()` and check the error list, or remove the method entirely to eliminate dead code. The inline validation in `_process()` already covers the critical checks.

11. **Consolidate `os.stat()` calls** (PERF-FP-002): Call `os.stat()` once and extract all fields:
    ```python
    stat_result = os.stat(file_path)
    file_properties = {
        'abs_path': os.path.abspath(file_path),
        'dirname': os.path.dirname(os.path.abspath(file_path)),
        'basename': os.path.basename(file_path),
        'mode_string': self._format_mode(stat_result.st_mode),
        'size': stat_result.st_size,
        'mtime': int(stat_result.st_mtime * 1000),
        'mtime_string': self._format_time(stat_result.st_mtime)
    }
    ```
    **Impact**: Reduces 3 system calls to 1. **Risk**: Very low.

12. **Add MD5 file size warning** (PERF-FP-001): Before MD5 calculation, log a warning for large files:
    ```python
    if calculate_md5:
        file_size = os.path.getsize(file_path)
        if file_size > 1_073_741_824:  # 1GB
            logger.warning(f"[{self.id}] MD5 calculation on large file ({file_size / 1e9:.1f} GB) may take several minutes")
    ```
    **Impact**: Improves observability. **Risk**: Very low.

### Long-Term (Optimization)

13. **Increase MD5 chunk size**: Change `f.read(4096)` to `f.read(65536)` or `f.read(1048576)` to reduce system call overhead. 64KB chunks reduce I/O calls by 16x compared to 4KB chunks.

14. **Normalize config key naming** (CONV-FP-003 / NAME-FP-001): Migrate to snake_case keys (`filename` instead of `FILENAME`, `md5` instead of `MD5`) for consistency with other components. This requires updating both the converter parser and the engine class simultaneously.

15. **Clean up tFileInputProperties dead code** (CONV-FP-004): Either implement the component (if it is a real Talend component) or remove the `pass` dispatch and empty parser stub.

16. **Add null safety to converter** (CONV-FP-005): Add null checks for `.find()` results:
    ```python
    filename_node = node.find('.//elementParameter[@name="FILENAME"]')
    file_name = filename_node.get('value', '') if filename_node is not None else ''
    ```

17. **Add Die on Error support**: Add a `DIE_ON_ERROR` config option that controls whether the component raises exceptions or returns an empty DataFrame on failure. This would match the pattern used by `tFileInputDelimited` and other components.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1697-1704
def parse_tfileproperties(self, node, component: Dict) -> Dict:
    """Parse tFileProperties specific configuration"""
    file_name = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    calculate_md5 = node.find('.//elementParameter[@name="MD5"]').get('value', 'false').lower() == 'true'

    component['config']['FILENAME'] = file_name.strip('"')
    component['config']['MD5'] = calculate_md5
    return component
```

**Notes on this code**:
- Line 1699: `.get('value', '')` provides a default empty string if the attribute is missing, but `.find()` itself may return None if the element is not found, which would crash.
- Line 1700: Boolean conversion correctly handles case-insensitive comparison via `.lower() == 'true'`.
- Line 1702: `.strip('"')` removes surrounding quotes. This handles Talend XML quoting but would also strip quotes from paths that legitimately contain quotes (edge case).
- Line 1703: `calculate_md5` is stored as a Python `bool`, which the engine reads directly with `self.config.get('MD5', False)`.

---

## Appendix B: Engine Class Structure

```
FileProperties (BaseComponent)
    Constants:
        (none)

    Methods:
        _validate_config() -> List[str]          # Validation -- NEVER CALLED (dead code)
        _process(input_data) -> Dict[str, Any]   # Main entry point -- extracts file properties
        _calculate_md5(file_path) -> str          # MD5 checksum calculation (chunked)
        _format_time(timestamp) -> str            # Timestamp to string formatting

    Config Keys (ALL CAPS):
        FILENAME (str): Path to file. Required.
        MD5 (bool): Calculate MD5 checksum. Default: False.

    Output Schema (hardcoded):
        abs_path (str): Absolute file path
        dirname (str): Directory name
        basename (str): Base filename
        mode_string (str): File permissions (currently octal format)
        size (int): File size in bytes
        mtime (float): Modification time (currently in seconds, should be ms)
        mtime_string (str): Formatted modification time
        md5 (str): MD5 hash (only when MD5=true)

    Statistics:
        NB_LINE: Always 1
        NB_LINE_OK: Always 1
        NB_LINE_REJECT: Always 0
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `FILENAME` | Mapped | -- |
| `MD5` | `MD5` | Mapped | -- |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| `SCHEMA` | -- | Not needed | -- (read-only predefined) |

---

## Appendix D: Output Column Comparison

### Talend vs V1 Engine Output

| Column | Talend Type | Talend Example | V1 Type | V1 Example | Match? |
|--------|------------|----------------|---------|------------|--------|
| `abs_path` | String | `/data/input/file.csv` | str | `/data/input/file.csv` | Yes |
| `dirname` | String | `/data/input` | str | `/data/input` (or `""` for relative) | **Partial** -- empty for relative paths |
| `basename` | String | `file.csv` | str | `file.csv` | Yes |
| `mode_string` | String | `rw` | str | `0o100644` | **No** -- format mismatch |
| `size` | Long | `1024` | int | `1024` | Yes |
| `mtime` | Long | `1616316000123` (ms) | float | `1616316000.123` (sec) | **No** -- unit mismatch |
| `mtime_string` | String | `Mar 21, 2021 10:00:00 AM` | str | `2021-03-21 10:00:00` | **Partial** -- format differs |
| `md5` | String | `abc123def456...` | str | `abc123def456...` | Yes |

**Summary**: 4 of 8 columns match exactly. 2 have format/unit mismatches (P1 severity). 2 have minor format differences (P2 severity).

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 60-81)

This method validates:
- `FILENAME` key exists in config (required)
- `FILENAME` value is not empty (required)
- `MD5` value is a boolean (if present)

**Not validated**: File existence (checked in `_process()` instead), path format, path traversal.

**Critical**: This method is never called. The `_process()` method has its own inline validation (lines 101-110) that covers the critical `FILENAME` check but does NOT validate `MD5` type.

### `_process()` (Lines 83-146)

The main processing method:
1. Logs processing start (line 97)
2. Extracts `FILENAME` from config with empty string default (line 101)
3. Extracts `MD5` from config with `False` default (line 102)
4. Validates FILENAME is not empty -- raises `ConfigurationError` (lines 104-106)
5. Checks file exists -- raises `FileOperationError` (lines 108-110)
6. Extracts file properties into dictionary (lines 115-123)
7. Conditionally calculates MD5 (lines 125-127)
8. Updates stats: always (1, 1, 0) (line 130)
9. Converts to single-row DataFrame (line 133)
10. Logs completion with filename and size (lines 135-137)
11. Returns `{'main': result_df}` (line 139)
12. Exception handling: re-raises custom exceptions, wraps others in `FileOperationError` (lines 141-146)

### `_calculate_md5()` (Lines 148-168)

MD5 checksum calculation:
1. Creates `hashlib.md5()` instance (line 162)
2. Opens file in binary mode (line 163)
3. Reads in 4096-byte chunks via `iter(lambda: f.read(4096), b"")` (line 164)
4. Updates hash with each chunk (line 165)
5. Returns hex digest string (line 166)
6. Wraps exceptions in `FileOperationError` with descriptive message (lines 167-168)

### `_format_time()` (Lines 170-180)

Timestamp formatting:
1. Takes Unix timestamp (float, in seconds)
2. Converts to `datetime` via `datetime.fromtimestamp(timestamp)` (local timezone)
3. Formats with `strftime('%Y-%m-%d %H:%M:%S')`
4. Returns formatted string

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty file (0 bytes)

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns properties with `size=0`. MD5 of empty file is `d41d8cd98f00b204e9800998ecf8427e`. |
| **V1** | `os.path.getsize()` returns `0`. `_calculate_md5()` reads zero chunks, returns MD5 of empty string: `d41d8cd98f00b204e9800998ecf8427e`. |
| **Verdict** | CORRECT |

### Edge Case 2: File does not exist

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error. No output row. Component error trigger fires. |
| **V1** | `os.path.exists()` check on line 108 raises `FileOperationError("File not found: {path}")`. |
| **Verdict** | CORRECT |

### Edge Case 3: FILENAME is empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises configuration error in Talend Studio validation (before runtime). |
| **V1** | `_process()` line 104 checks `if not file_path:` and raises `ConfigurationError("FILENAME is required in the configuration.")`. |
| **Verdict** | CORRECT |

### Edge Case 4: FILENAME is None (missing key)

| Aspect | Detail |
|--------|--------|
| **Talend** | Would not happen -- FILENAME is mandatory in Talend Studio. |
| **V1** | `self.config.get('FILENAME', '')` returns empty string default, which triggers the `if not file_path:` check. |
| **Verdict** | CORRECT -- handles gracefully via default |

### Edge Case 5: File with spaces in path

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File class). |
| **V1** | `os.path.exists()`, `os.path.abspath()`, `os.stat()`, `open()` all handle spaces correctly. |
| **Verdict** | CORRECT |

### Edge Case 6: Symbolic link

| Aspect | Detail |
|--------|--------|
| **Talend** | Reports properties of the file the symlink points to (follows symlinks). |
| **V1** | `os.path.exists()` follows symlinks. `os.stat()` follows symlinks. `os.path.abspath()` resolves `.` and `..` but does NOT resolve symlinks (use `os.path.realpath()` for that). `abs_path` will show the symlink path, not the target. `size` and `mtime` will be from the target. |
| **Verdict** | PARTIAL -- `abs_path` shows symlink path while other fields show target properties. May differ from Talend behavior. |

### Edge Case 7: Relative path input

| Aspect | Detail |
|--------|--------|
| **Talend** | Resolves relative to Talend job working directory. |
| **V1** | `os.path.abspath()` resolves relative to Python process CWD. `abs_path` will be correct. But `dirname` uses `os.path.dirname(file_path)` on the ORIGINAL relative path, which may return empty string for `"myfile.txt"`. |
| **Verdict** | PARTIAL -- `abs_path` correct, `dirname` may be empty. See BUG-FP-009. |

### Edge Case 8: NaN handling in DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- tFileProperties produces scalar values, not data rows. |
| **V1** | `pd.DataFrame([file_properties])` creates a single-row DataFrame from a dictionary. All values are scalars (strings, ints, floats). No NaN values are possible unless `os.*` functions return None, which they do not for valid files. |
| **Verdict** | NOT APPLICABLE -- NaN handling is not a concern for this component |

### Edge Case 9: Empty DataFrame (no input)

| Aspect | Detail |
|--------|--------|
| **Talend** | tFileProperties does not process input data. It always produces output based on the file. |
| **V1** | `_process()` ignores `input_data` parameter (line 83: `input_data: Optional[Any] = None`). The parameter is unused. Component always produces output from file analysis. |
| **Verdict** | CORRECT -- input_data is correctly ignored |

### Edge Case 10: `_update_global_map()` crash

| Aspect | Detail |
|--------|--------|
| **Talend** | globalMap updates are internal to Talend runtime; no crash risk. |
| **V1** | `_update_global_map()` in base_component.py line 304 references undefined `value` variable. This crashes with `NameError` whenever `global_map` is not None. Since `execute()` calls `_update_global_map()` on line 218 (in try block), the exception propagates up and the entire `execute()` call fails. The component's `_process()` method succeeds but the result is lost. |
| **Verdict** | **CRITICAL BUG** -- Component appears to fail even when file analysis succeeds, because the post-processing globalMap update crashes. See BUG-FP-001. |

### Edge Case 11: ComponentStatus tracking

| Aspect | Detail |
|--------|--------|
| **Talend** | Component status is managed by the Talend runtime. |
| **V1** | `execute()` sets `self.status = ComponentStatus.RUNNING` (line 192), then `ComponentStatus.SUCCESS` (line 220) or `ComponentStatus.ERROR` (line 228). Because of BUG-FP-001, when globalMap is present, the exception in `_update_global_map()` causes `execute()` to enter the except block, setting status to `ERROR` even though `_process()` succeeded. |
| **Verdict** | **BUG** -- Status reports ERROR when processing actually succeeded. Masked by BUG-FP-001. |

### Edge Case 12: Config key ALL CAPS vs other components

| Aspect | Detail |
|--------|--------|
| **Talend** | XML parameter names are ALL CAPS (FILENAME, MD5) in all components. |
| **V1** | Most component converters rename to snake_case (`filepath`, `delimiter`). FileProperties converter preserves ALL CAPS (`FILENAME`, `MD5`). This means a hypothetical config validation tool checking for `filepath` would not find it in FileProperties configs. |
| **Verdict** | **INCONSISTENCY** -- Not a bug (converter and engine match), but creates maintenance burden. See CONV-FP-003. |

### Edge Case 13: MD5 hash computation on large file (memory usage)

| Aspect | Detail |
|--------|--------|
| **Talend** | Java MD5 computation reads file sequentially. Memory usage bounded by buffer size. |
| **V1** | `_calculate_md5()` uses `iter(lambda: f.read(4096), b"")` which reads 4KB at a time. Only 4KB of file content is in memory at any moment. `hashlib.md5()` maintains internal state. Total memory usage is O(1) regardless of file size. |
| **Verdict** | CORRECT -- Memory usage is bounded. CPU time is O(n) which is unavoidable for MD5. Only concern is wall-clock time for multi-GB files (see PERF-FP-001). |

### Edge Case 14: Return format -- single-row DataFrame vs dict

| Aspect | Detail |
|--------|--------|
| **Talend** | tFileProperties outputs a single-row data flow via the FLOW connector. Downstream components receive it as a standard Talend row. |
| **V1** | `_process()` returns `{'main': pd.DataFrame([file_properties])}`. The DataFrame has exactly one row with 7-8 columns. Downstream components that expect DataFrames (like tLogRow, tFilterRow, tMap) can process this correctly. The `[file_properties]` list wrapper (line 133) correctly creates a single-row DataFrame, unlike the scalar-expansion bug seen in `tFileInputDelimited`'s `_read_as_single_string()`. |
| **Verdict** | CORRECT -- Single-row DataFrame is the right format for pipeline compatibility. |

### Edge Case 15: Converter `tFileInputProperties` dispatch as `pass`

| Aspect | Detail |
|--------|--------|
| **Talend** | `tFileInputProperties` may or may not be a real Talend component. Not found in official documentation. |
| **V1** | Converter dispatch (converter.py line 296-298) recognizes `tFileInputProperties` but executes `pass`, meaning the component dict is NOT updated with any config. If this component appears in a Talend XML job, it will be created with an empty config, and the engine will fail to find an alias for `tFileInputProperties` in engine.py, raising a `KeyError` or similar error during instantiation. |
| **Verdict** | **DEAD CODE / SILENT FAILURE** -- The converter recognizes the component but does nothing. The engine cannot instantiate it. If a job contains `tFileInputProperties`, it will fail at runtime with no clear error message about unsupported component type. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileProperties`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FP-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when globalMap is provided. |
| BUG-FP-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FP-003 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called by the base class. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FP-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FP-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FP-004 / ENG-FP-001 -- `mtime` seconds to milliseconds

**File**: `src/v1/engine/components/file/file_properties.py`
**Lines**: 121-122

**Current code**:
```python
'mtime': os.path.getmtime(file_path),
'mtime_string': self._format_time(os.path.getmtime(file_path))
```

**Fix**:
```python
'mtime': int(os.path.getmtime(file_path) * 1000),
'mtime_string': self._format_time(os.path.getmtime(file_path))
```

**Explanation**: Talend outputs `mtime` in milliseconds since epoch (Java convention). Python's `os.path.getmtime()` returns seconds. Multiply by 1000 and convert to int. Note that `_format_time()` still receives seconds (correct for `datetime.fromtimestamp()`).

**Impact**: Fixes silent data corruption for `mtime` column. **Risk**: Low.

---

### Fix Guide: ENG-FP-002 / BUG-FP-008 -- `mode_string` format

**File**: `src/v1/engine/components/file/file_properties.py`
**Line**: 119

**Current code**:
```python
'mode_string': oct(os.stat(file_path).st_mode),
```

**Fix** (add helper method):
```python
# In _process(), replace line 119 with:
'mode_string': self._format_mode(os.stat(file_path).st_mode),

# Add new method to the class:
def _format_mode(self, mode: int) -> str:
    """
    Format file mode as Talend-compatible permission string.

    Args:
        mode: Raw file mode from os.stat().st_mode

    Returns:
        Permission string (e.g., 'r', 'w', 'rw', 'rwx')
    """
    import stat
    perms = ''
    if mode & stat.S_IRUSR:
        perms += 'r'
    if mode & stat.S_IWUSR:
        perms += 'w'
    if mode & stat.S_IXUSR:
        perms += 'x'
    return perms if perms else '-'
```

**Impact**: Fixes format mismatch for `mode_string` column. **Risk**: Low (output format change).

---

### Fix Guide: BUG-FP-009 -- `dirname` empty for relative paths

**File**: `src/v1/engine/components/file/file_properties.py`
**Line**: 117

**Current code**:
```python
'dirname': os.path.dirname(file_path),
```

**Fix**:
```python
'dirname': os.path.dirname(os.path.abspath(file_path)),
```

**Impact**: Ensures `dirname` always returns a meaningful directory path. **Risk**: Very low.

---

### Fix Guide: PERF-FP-002 -- Consolidate `os.stat()` calls

**File**: `src/v1/engine/components/file/file_properties.py`
**Lines**: 115-123

**Current code**:
```python
file_properties = {
    'abs_path': os.path.abspath(file_path),
    'dirname': os.path.dirname(file_path),
    'basename': os.path.basename(file_path),
    'mode_string': oct(os.stat(file_path).st_mode),
    'size': os.path.getsize(file_path),
    'mtime': os.path.getmtime(file_path),
    'mtime_string': self._format_time(os.path.getmtime(file_path))
}
```

**Fix**:
```python
abs_path = os.path.abspath(file_path)
stat_result = os.stat(file_path)

file_properties = {
    'abs_path': abs_path,
    'dirname': os.path.dirname(abs_path),
    'basename': os.path.basename(file_path),
    'mode_string': self._format_mode(stat_result.st_mode),
    'size': stat_result.st_size,
    'mtime': int(stat_result.st_mtime * 1000),
    'mtime_string': self._format_time(stat_result.st_mtime)
}
```

**Impact**: Reduces 3+ system calls to 1. Also fixes dirname and mtime issues simultaneously. **Risk**: Very low.

---

## Appendix I: Comparison with Other Utility Components

| Feature | tFileProperties (V1) | tFileExist (V1) | tFileRowCount (V1) | tFileTouch (V1) |
|---------|---------------------|------------------|---------------------|-----------------|
| File path input | Yes (FILENAME) | Yes (FILENAME) | Yes (filename) | Yes (FILENAME) |
| Config key naming | ALL CAPS | ALL CAPS | snake_case | ALL CAPS |
| Produces output row | Yes (single row) | No (boolean result) | No (count in globalMap) | No (side effect only) |
| MD5 support | Yes | N/A | N/A | N/A |
| Die on Error | **No** | Yes | Yes | Yes |
| Error globalMap | **No** | Unknown | Unknown | Unknown |
| V1 Unit tests | **No** | **No** | **No** | **No** |
| Dedicated converter parser | Yes | Yes | Yes | Yes |
| Java expression marking | **No** | Unknown | Unknown | Unknown |

**Observation**: The lack of v1 unit tests is systemic across ALL utility components. The config key naming inconsistency (ALL CAPS vs snake_case) affects multiple components. The missing Java expression marking in dedicated parsers is likely a pattern issue affecting all file utility components.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using `mtime` for numeric comparisons | **Critical** | Any job comparing file modification times | Fix mtime to milliseconds (BUG-FP-004) |
| Jobs parsing `mode_string` | **High** | Any job checking file permissions | Fix mode_string format (ENG-FP-002) |
| Jobs referencing `{id}_ERROR_MESSAGE` | **High** | Jobs with error handling on tFileProperties | Implement ERROR_MESSAGE globalMap (ENG-FP-003) |
| Jobs using `dirname` with relative paths | **Medium** | Jobs where FILENAME comes from relative paths | Fix dirname to use abspath (BUG-FP-009) |
| Jobs comparing `mtime_string` exactly | **Medium** | Jobs doing string-match on formatted dates | Verify format matches Talend output |
| Jobs with globalMap provided to engine | **Critical** | ALL jobs using globalMap | Fix BUG-FP-001 and BUG-FP-002 first |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs only using `abs_path`, `basename`, `size` | Low | These columns are correctly implemented |
| Jobs using MD5 for file integrity | Low | MD5 implementation is correct and memory-safe |
| Jobs using tFileProperties with tLogRow for display | Low | Output format differences are cosmetic in log output |
| Jobs not providing globalMap | Low | Avoids BUG-FP-001 crash (but loses stats) |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting globalMap issues). These block ALL components.
2. **Phase 2**: Fix `mtime` and `mode_string` format issues. These are silent data corruption risks.
3. **Phase 3**: Audit each target job's usage of tFileProperties columns. Identify which jobs depend on `mtime`, `mode_string`, `dirname`, or `ERROR_MESSAGE`.
4. **Phase 4**: Create unit test suite for FileProperties. Verify all column values match Talend output for test files.
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row.

---

## Appendix K: tFileInputProperties Analysis

### Component Status: Dead Code

The converter recognizes `tFileInputProperties` as a component type but the implementation is completely hollow:

**Converter dispatch** (converter.py lines 296-298):
```python
elif component_type == 'tFileInputProperties':
    # Add logic for handling tFileInputProperties
    pass
```

**Parser stub** (component_parser.py lines 1720-1723):
```python
def parse_tfileinputproperties(self, node, component: Dict) -> Dict:
    """Parse tFileInputProperties specific configuration"""
    # Add parsing logic here
    return component
```

**Engine registration**: `tFileInputProperties` does NOT appear in `engine.py`'s component registry. There is no alias for it.

**Type map**: `component_parser.py` line 34 maps `tFileProperties` to `FileProperties`, but there is NO mapping for `tFileInputProperties`.

### Impact Analysis

1. If a Talend XML job contains a `tFileInputProperties` node, the converter will:
   - Match on line 296: `elif component_type == 'tFileInputProperties'`
   - Execute `pass` -- the component dict has NO config populated
   - The component will have `component_type` set via the type map lookup, but `tFileInputProperties` is NOT in the type map (line 34), so it will fall through to the raw component type name
   - The engine will try to instantiate `tFileInputProperties` as a class name, fail to find it in the registry, and raise an error

2. This is a **silent converter failure** -- the converter does not warn or error when it encounters `tFileInputProperties`. It silently produces an incomplete component definition.

### Recommendation

Either:
- **Implement**: If `tFileInputProperties` is a real Talend component (possibly an older or alternative name), map it to `FileProperties` in the type map and call `parse_tfileproperties()` from the dispatch.
- **Remove**: If `tFileInputProperties` is not a real component, remove the dead dispatch and parser stub to avoid confusion.
- **Error**: At minimum, replace `pass` with a warning: `logger.warning(f"tFileInputProperties is not supported. Skipping.")`.

---

## Appendix L: Complete Optimized Engine Implementation

The following is the recommended replacement for the current `_process()` method, incorporating all fixes from this audit:

```python
def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    Extract file properties based on the configuration.

    Args:
        input_data: Not used for this component

    Returns:
        Dictionary with file properties in 'main' key

    Raises:
        ConfigurationError: If FILENAME is missing or empty
        FileOperationError: If file does not exist or cannot be accessed
    """
    import stat

    logger.info(f"[{self.id}] Processing started: analyzing file properties")

    try:
        # Get configuration with validation
        file_path = self.config.get('FILENAME', '')
        calculate_md5 = self.config.get('MD5', False)

        if not file_path:
            logger.error(f"[{self.id}] FILENAME is required in configuration")
            raise ConfigurationError("FILENAME is required in the configuration.")

        if not os.path.exists(file_path):
            logger.error(f"[{self.id}] File not found: {file_path}")
            raise FileOperationError(f"File not found: {file_path}")

        logger.debug(f"[{self.id}] Analyzing file: {file_path}")

        # Single os.stat() call for all metadata
        abs_path = os.path.abspath(file_path)
        stat_result = os.stat(file_path)

        # Format mode as Talend-compatible permission string
        mode = stat_result.st_mode
        perms = ''
        if mode & stat.S_IRUSR: perms += 'r'
        if mode & stat.S_IWUSR: perms += 'w'
        if mode & stat.S_IXUSR: perms += 'x'

        # Extract file properties
        file_properties = {
            'abs_path': abs_path,
            'dirname': os.path.dirname(abs_path),  # Use abs_path for meaningful dirname
            'basename': os.path.basename(file_path),
            'mode_string': perms if perms else '-',
            'size': stat_result.st_size,
            'mtime': int(stat_result.st_mtime * 1000),  # Milliseconds (Talend convention)
            'mtime_string': self._format_time(stat_result.st_mtime)
        }

        if calculate_md5:
            file_size = stat_result.st_size
            if file_size > 1_073_741_824:  # 1GB
                logger.warning(f"[{self.id}] MD5 calculation on large file "
                             f"({file_size / 1e9:.1f} GB) may take several minutes")
            logger.debug(f"[{self.id}] Calculating MD5 checksum")
            file_properties['md5'] = self._calculate_md5(file_path)

        # Update stats (maintain exact same behavior: 1, 1, 0)
        self._update_stats(1, 1, 0)

        # Convert dictionary to DataFrame for compatibility with other components
        result_df = pd.DataFrame([file_properties])

        logger.info(f"[{self.id}] Processing complete: "
                    f"analyzed file {os.path.basename(file_path)}, "
                    f"size {file_properties['size']} bytes")

        return {'main': result_df}

    except (ConfigurationError, FileOperationError):
        # Store error in globalMap before re-raising
        if self.global_map:
            import sys
            exc = sys.exc_info()[1]
            self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(exc))
        raise
    except Exception as e:
        logger.error(f"[{self.id}] Processing failed: {e}")
        if self.global_map:
            self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
        raise FileOperationError(f"Failed to analyze file properties: {e}") from e
```

**Key changes from current implementation**:
1. Single `os.stat()` call (was 3+)
2. `dirname` uses `abs_path` (fixes empty string for relative paths)
3. `mode_string` uses human-readable format (fixes Talend format mismatch)
4. `mtime` in milliseconds (fixes unit mismatch)
5. MD5 file size warning for files over 1GB
6. `ERROR_MESSAGE` set in globalMap on error
7. Import `stat` module for permission constants

---

## Appendix M: Converter Expression Handling Deep Dive

### How FILENAME Flows Through the Converter

When a Talend job contains a globalMap reference in the `FILENAME` parameter of tFileProperties (the most common pattern when used with tFileList), the following transformation chain occurs:

1. **Talend XML**: `<elementParameter name="FILENAME" value="((String)globalMap.get(&quot;tFileList_1_CURRENT_FILEPATH&quot;))" />`

2. **After XML parse and entity decode**: `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`

3. **In `parse_tfileproperties()`** (line 1699):
   - `.get('value', '')` extracts the raw string
   - `.strip('"')` strips surrounding quotes -- but this value does NOT have surrounding quotes, so no change
   - No `mark_java_expression()` call -- the Java expression is stored as-is

4. **Stored in config**: `component['config']['FILENAME'] = '((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))'`

5. **At engine runtime** (`BaseComponent.execute()`):
   - Step 1: `_resolve_java_expressions()` -- only processes values prefixed with `{{java}}`. This value has no prefix, so it is **NOT resolved**.
   - Step 2: `context_manager.resolve_dict()` -- only processes `${context.var}` patterns. This value has no such pattern, so it is **NOT resolved**.
   - Result: `self.config.get('FILENAME')` returns the raw Java expression string `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`
   - `os.path.exists()` receives this string as a literal path -- file does not exist -- `FileOperationError` raised

**Conclusion**: Java expressions in FILENAME are NOT resolved because the converter does not add the `{{java}}` marker prefix. This is a functional gap for the most common tFileProperties usage pattern (tFileList + tFileProperties).

### Comparison with Other Converter Parsers

| Parser Method | Calls `mark_java_expression()`? | Handles `context.`? |
|--------------|--------------------------------|---------------------|
| `_map_component_parameters()` (generic) | No (done in `mark_java_expression()` post-pass) | Yes (lines 449-456) |
| `parse_base_component()` (generic) | Yes (via post-processing loop, lines 462-469) | Yes (lines 449-456) |
| `parse_tfileproperties()` | **No** | **No** |
| `parse_tfilecopy()` | **No** | **No** |
| `parse_tfiletouch()` | **No** | **No** |
| `parse_tfileexist()` | **No** | **No** |
| `parse_tfile_row_count()` | **No** | **No** |

**Pattern observation**: ALL dedicated file utility component parsers share the same gap -- they extract raw values without Java expression marking or context variable wrapping. This is likely because these parsers were written quickly using a simpler extraction pattern, while the generic `parse_base_component()` path includes the expression handling as a post-processing step. The fix should be applied systematically to all file utility parsers.

### Recommended Fix Pattern for All File Utility Parsers

```python
def parse_tfileproperties(self, node, component: Dict) -> Dict:
    """Parse tFileProperties specific configuration"""
    file_name_node = node.find('.//elementParameter[@name="FILENAME"]')
    file_name = file_name_node.get('value', '') if file_name_node is not None else ''

    md5_node = node.find('.//elementParameter[@name="MD5"]')
    calculate_md5 = md5_node.get('value', 'false').lower() == 'true' if md5_node is not None else False

    # Strip surrounding quotes
    file_name = file_name.strip('"')

    # Handle context variable references
    if 'context.' in file_name:
        if not self.expr_converter.detect_java_expression(file_name):
            # Simple context reference -- wrap for ContextManager
            file_name = f"${{{file_name}}}"
        # If it IS a Java expression, fall through to marking below

    # Mark Java expressions for engine resolution
    file_name = self.expr_converter.mark_java_expression(file_name)

    component['config']['FILENAME'] = file_name
    component['config']['MD5'] = calculate_md5
    return component
```

**Key improvements**:
1. Null safety on `.find()` results
2. Context variable detection and wrapping
3. Java expression marking via `mark_java_expression()`
4. Same pattern can be applied to all file utility parsers

---

## Appendix N: Base Class Lifecycle Analysis for FileProperties

### How `execute()` Processes FileProperties

The `BaseComponent.execute()` method (lines 188-234) orchestrates the complete lifecycle:

```
execute(input_data=None)
  |
  +-- 1. Set status = RUNNING
  +-- 2. Record start_time
  +-- 3. Resolve Java expressions (if java_bridge present)
  |     |
  |     +-- _resolve_java_expressions()
  |           - Scans config for {{java}} prefixed values
  |           - For FileProperties: likely finds NONE (converter doesn't mark)
  |
  +-- 4. Resolve context variables (if context_manager present)
  |     |
  |     +-- context_manager.resolve_dict(self.config)
  |           - Scans config for ${context.var} patterns
  |           - For FileProperties: resolves any ${...} in FILENAME
  |
  +-- 5. Determine execution mode (HYBRID -> auto-select)
  |     |
  |     +-- _auto_select_mode(None) -> BATCH (no input data)
  |
  +-- 6. Execute in batch mode
  |     |
  |     +-- _execute_batch(None)
  |           |
  |           +-- _process(None)
  |                 - FileProperties._process() runs
  |                 - Returns {'main': single_row_dataframe}
  |
  +-- 7. Update execution time stat
  +-- 8. _update_global_map()  <-- CRASHES HERE (BUG-FP-001)
  |     |
  |     +-- For each stat in self.stats:
  |           global_map.put_component_stat(id, stat_name, stat_value)
  |     +-- logger.info(... {value} ...)  <-- NameError: 'value' not defined
  |
  +-- 9. Set status = SUCCESS  <-- NEVER REACHED when globalMap present
  +-- 10. Add stats to result
  +-- 11. Return result
  |
  +-- EXCEPTION PATH (triggered by BUG-FP-001):
        +-- Set status = ERROR
        +-- Set error_message = str(e)
        +-- _update_global_map()  <-- CRASHES AGAIN (infinite loop avoided by raise)
        +-- logger.error(...)
        +-- Raise exception
```

**Critical finding**: When `global_map` is not None, the `execute()` method ALWAYS fails due to BUG-FP-001, even though `_process()` completes successfully. The component status is incorrectly set to ERROR. The result dictionary is never returned. This means FileProperties is **completely non-functional** when globalMap is used.

**Workaround**: Pass `global_map=None` when constructing the component. This skips `_update_global_map()` entirely, allowing the component to function. However, this means no NB_LINE statistics are written to globalMap, and downstream components cannot read `{id}_NB_LINE`.

### Statistics Flow

```
FileProperties._process()
  |
  +-- _update_stats(1, 1, 0)
  |     - self.stats['NB_LINE'] += 1  -> 1
  |     - self.stats['NB_LINE_OK'] += 1  -> 1
  |     - self.stats['NB_LINE_REJECT'] += 0  -> 0
  |
  +-- Returns {'main': DataFrame}

BaseComponent.execute()
  |
  +-- _update_global_map()
        - global_map.put_component_stat(id, 'NB_LINE', 1)
        - global_map.put_component_stat(id, 'NB_LINE_OK', 1)
        - global_map.put_component_stat(id, 'NB_LINE_REJECT', 0)
        - global_map.put_component_stat(id, 'NB_LINE_INSERT', 0)
        - global_map.put_component_stat(id, 'NB_LINE_UPDATE', 0)
        - global_map.put_component_stat(id, 'NB_LINE_DELETE', 0)
        - global_map.put_component_stat(id, 'EXECUTION_TIME', 0.xxx)
        - CRASH on log line (BUG-FP-001)
```

**Note**: FileProperties always reports exactly 1 line read, 1 line OK, 0 rejected. This is correct for a component that produces a single output row per file. If the file does not exist, the exception is raised before `_update_stats()` is called, so stats remain at (0, 0, 0).

---

## Appendix O: MD5 Implementation Correctness Verification

### Algorithm Correctness

The `_calculate_md5()` method (lines 148-168) implements the standard chunked MD5 computation pattern:

```python
hash_md5 = hashlib.md5()
with open(file_path, 'rb') as f:
    for chunk in iter(lambda: f.read(4096), b""):
        hash_md5.update(chunk)
return hash_md5.hexdigest()
```

**Verification points**:

1. **Binary mode**: File opened with `'rb'` -- correct. Text mode would alter line endings and produce wrong hash.

2. **Sentinel value**: `iter(lambda: ..., b"")` uses empty bytes as sentinel -- correct. When `f.read()` reaches EOF, it returns `b""`, terminating the loop.

3. **Incremental update**: `hash_md5.update(chunk)` processes each chunk incrementally -- correct. This is equivalent to hashing the entire file content at once.

4. **Hex digest**: `hash_md5.hexdigest()` returns lowercase hex string -- matches Talend's output format.

5. **Known test values**:
   - Empty file: `d41d8cd98f00b204e9800998ecf8427e` (MD5 of empty string)
   - `"hello\n"`: `b1946ac92492d2347c6235b4d2611184`
   - `"Hello World"`: `b10a8db164e0754105b7a99be72e3fe5`

### Security Considerations

MD5 is cryptographically broken (collision attacks exist). However, for the tFileProperties use case (file identity and change detection), MD5 is acceptable because:
- The threat model is accidental changes, not adversarial manipulation
- Talend itself uses MD5 for this feature
- Switching to SHA-256 would break compatibility with Talend output

### Performance Characteristics

| File Size | Estimated MD5 Time | Memory Usage |
|-----------|--------------------|--------------|
| 1 MB | < 1 ms | 4 KB constant |
| 100 MB | ~50 ms | 4 KB constant |
| 1 GB | ~500 ms | 4 KB constant |
| 10 GB | ~5 seconds | 4 KB constant |
| 100 GB | ~50 seconds | 4 KB constant |

**Note**: Times are approximate for modern hardware with SSD storage. HDD storage would be significantly slower due to sequential read throughput.

---

## Appendix P: Talend tFileProperties Usage Patterns

### Pattern 1: Single File Analysis

```
tFileProperties_1 --> (Main) --> tLogRow_1
```

The simplest pattern. A single file is analyzed and its properties are displayed. The `FILENAME` parameter contains a literal path or context variable.

**V1 Support**: Fully supported (with mtime/mode_string format caveats).

### Pattern 2: Directory Scan with tFileList

```
tFileList_1 --> (Iterate) --> tFileProperties_1 --> (Main) --> tLogRow_1
```

The most common pattern. `tFileList` iterates over files in a directory, and for each file, `tFileProperties` extracts metadata. The `FILENAME` parameter references `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`.

**V1 Support**: NOT supported due to Java expression in FILENAME not being resolved (CONV-FP-001). The converter does not mark the globalMap.get() expression with `{{java}}`, so the engine receives a raw Java expression string instead of a resolved file path.

### Pattern 3: File Properties to Database

```
tFileList_1 --> (Iterate) --> tFileProperties_1 --> (Main) --> tMap_1 --> (Main) --> tOutputDB_1
```

Extended pattern where file properties are persisted to a database for auditing. The `size` column name conflicts with Oracle reserved keywords.

**V1 Support**: Partially supported. The `size` column works in the DataFrame, but database persistence depends on the output component handling reserved keywords. The `mtime` millisecond mismatch would store incorrect values.

### Pattern 4: Conditional Processing Based on File Size

```
tFileList_1 --> (Iterate) --> tFileProperties_1 --> (Main) --> tFilterRow_1 --> (Main) --> tFileInputDelimited_1
```

File properties are used to filter files by size before processing. Only files under a certain size are passed through.

**V1 Support**: Partially supported. The filtering works correctly since `size` is correct. However, if the filter references `mtime`, the millisecond mismatch would produce incorrect filtering.

### Pattern 5: MD5 Checksum Verification

```
tFileProperties_1 --> (Main) --> tMap_1 --> (Main) --> tLogRow_1
                                    |
                                    +--> (Lookup) --> tFileInputDelimited_1 (expected MD5 values)
```

File MD5 is compared against expected values for integrity verification.

**V1 Support**: Fully supported. The MD5 implementation is correct.

---
