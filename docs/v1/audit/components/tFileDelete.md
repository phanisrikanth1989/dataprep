# Audit Report: tFileDelete / FileDelete

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
| **Talend Name** | `tFileDelete` |
| **V1 Engine Class** | `FileDelete` |
| **Engine File** | `src/v1/engine/components/file/file_delete.py` (175 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_delete.py` |
| **Converter Dispatch** | `talend_to_v1` registry-based dispatch via `REGISTRY["tFileDelete"]` |
| **Registry Aliases** | `FileDelete`, `tFileDelete` (registered in `src/v1/engine/engine.py` lines 72-73) |
| **Category** | File / Utility |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_delete.py` | Engine implementation (175 lines) |
| `src/converters/talend_to_v1/components/file/file_delete.py` | Dedicated `talend_to_v1` converter for tFileDelete |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` (381 lines) |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. (86 lines) |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (`FileDelete` on line 4, `__all__` on line 27) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | `talend_to_v1` dedicated parser extracts 9 params (8 config keys). All runtime params mapped. FAIL_ON_ERROR renamed from FAILON. Path field mapping via FOLDER/FOLDER_FILE selection logic. |
| Engine Feature Parity | **Y** | 0 | 4 | 3 | 1 | No DELETE_PATH globalMap var; no CURRENT_STATUS; no ERROR_MESSAGE; fail_on_error default inverted; no symlink handling |
| Code Quality | **Y** | 2 | 3 | 2 | 2 | Cross-cutting base class bugs; dead `_validate_config()`; no path sanitization; empty string path accepted with .get default |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Simple file I/O; no memory concerns; minor optimization in redundant os.path checks |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileDelete Does

`tFileDelete` deletes files or directories from the filesystem. It is a utility component in the File family, commonly used in pre-job cleanup (e.g., deleting output files before a fresh write), post-job cleanup (removing temporary files), and iterative file processing (combined with `tFileList` to delete files matching a pattern). The component supports three modes: file-only deletion, directory-only deletion, and combined file-or-directory deletion. It does not produce data flow output -- it is a standalone action component.

**Source**: [tFileDelete Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfiledelete/tfiledelete-standard-properties), [tFileDelete Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfiledelete/tfiledelete-standard-properties), [tFileDelete - Talend Skill](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfiledelete-talend-open-studio-for-esb-document-7-x/)

**Component family**: File (Utility)
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (uses Java standard library `java.io.File`)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory** (in default mode). Absolute path of the file to delete. Hidden when `FOLDER` or `FOLDER_FILE` checkbox is selected. Supports context variables, globalMap references, and Java expressions. |
| 3 | Directory | `DIRECTORY` | Expression (String) | -- | **Mandatory** (when `FOLDER=true`). Absolute path of the directory to delete. Only visible when "Delete folder" checkbox is selected. |
| 4 | File or directory to delete | `FOLDER_FILE_PATH` | Expression (String) | -- | **Mandatory** (when `FOLDER_FILE=true`). Path to the file or directory, whichever exists. Only visible when "Delete file or folder" checkbox is selected. |
| 5 | Fail on error | `FAIL_ON_ERROR` | Boolean (CHECK) | `false` | When checked, prevents subsequent job execution if deletion fails (e.g., file does not exist, permission denied). When unchecked, errors are suppressed and the job continues. **Note**: Default is `false` (unchecked) in Talend. |
| 6 | Delete Folder | `FOLDER` | Boolean (CHECK) | `false` | When checked, displays the "Directory" field instead of "File Name". Switches the component to directory deletion mode. |
| 7 | Delete file or folder | `FOLDER_FILE` | Boolean (CHECK) | `false` | When checked, displays "File or directory to delete" field. The component attempts to delete whatever exists at the path, whether file or directory. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 8 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 9 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `Main` (Row) | Output | Row > Main | Data row output. tFileDelete can accept and pass through row data, though it does not produce data flow itself. |
| `ITERATE` | Input | Row > Iterate | Enables iterative deletion when combined with iteration components like `tFileList`. The component deletes the file specified by the current iteration variable. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output/Input (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronize execution with parallel threads. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Enable parallel execution of the component. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_DELETE_PATH` | String | After | The path to the deleted file or folder. Set after the component completes execution. Contains the resolved absolute path that was targeted for deletion. |
| `{id}_CURRENT_STATUS` | String | Flow | The execution result status of the component. Available during flow processing. Values are typically "success" or "failure". |
| `{id}_ERROR_MESSAGE` | String | After | Error message generated by the component when errors occur. Only populated when an error happens and `FAIL_ON_ERROR` is not set (so the job continues). |

**Note on NB_LINE**: Unlike data flow components, `tFileDelete` does not set `{id}_NB_LINE` since it does not process rows. However, the v1 engine base class sets `NB_LINE` statistics via `_update_stats()` for all components, so v1 produces a `NB_LINE` count (1 if attempted, 0 otherwise) that has no Talend equivalent.

### 3.5 Behavioral Notes

1. **Absolute paths required**: Talend documentation explicitly warns: "Use absolute path (instead of relative path) for this field to avoid possible errors." The component does not resolve relative paths against a working directory.

2. **FAIL_ON_ERROR default is `false`**: Unlike many other Talend components where `DIE_ON_ERROR` defaults to `false`, the `FAIL_ON_ERROR` default of `false` means the component silently continues if the target file does not exist. This is intentional -- `tFileDelete` is commonly used in pre-job cleanup where the file may not exist yet.

3. **Directory deletion behavior**: When `FOLDER=true`, the component deletes the directory. In Talend, this uses `java.io.File.delete()` which only deletes EMPTY directories. Non-empty directories cause a failure (if `FAIL_ON_ERROR=true`) or silent no-op (if `FAIL_ON_ERROR=false`). There is NO recursive deletion in standard Talend `tFileDelete`. Recursive deletion requires using `tFileList` + `tFileDelete` in combination, iterating files first.

4. **FOLDER_FILE mode**: When `FOLDER_FILE=true`, the component checks whether the path points to a file or directory and deletes accordingly. This is a convenience mode that avoids needing separate components for file vs directory cleanup.

5. **Symlink handling**: In Talend (Java), `File.delete()` deletes the symlink itself, not the target. This is standard Java behavior via the underlying OS call.

6. **File lock behavior**: On Windows, attempting to delete a file that is open by another process fails. On Unix, the file can be unlinked even while open (content remains accessible via the open file descriptor until it is closed). Talend does not provide special handling for this -- it relies on the OS.

7. **Non-existent file with FAIL_ON_ERROR=false**: The component completes successfully with no error. The `DELETE_PATH` variable is still set to the attempted path. `CURRENT_STATUS` reflects the outcome.

8. **Usage in PreJob**: `tFileDelete` is frequently placed in the PreJob (tPreJob component) to clean up output files before the main job runs. In this context, `FAIL_ON_ERROR` should be unchecked since the files may not exist on the first run.

9. **Iterative deletion with tFileList**: The most common pattern is `tFileList -> tFileDelete` where tFileList iterates files in a directory and tFileDelete deletes each one. The file path is passed via `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`.

10. **No wildcard/glob support**: `tFileDelete` deletes a SINGLE file or directory per execution. It does not support wildcards or glob patterns. For pattern-based deletion, `tFileList` (with filtering) + `tFileDelete` is required.

11. **Standard Talend `File.delete()` does NOT recursively delete directories**: This is a critical behavioral difference from the v1 engine which supports `shutil.rmtree()` via the `recursive` config flag. Talend's `java.io.File.delete()` only deletes empty directories. Non-empty directories fail.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated parser (`src/converters/talend_to_v1/components/file/file_delete.py`) registered via `REGISTRY["tFileDelete"]`. The parser extracts all runtime parameters using safe `_get_str` / `_get_bool` helpers with null-safety and correct defaults.

**Converter flow**:
1. `talend_to_v1` registry dispatches to `file_delete.py` converter function
2. Extracts all runtime parameters using `_get_str()` and `_get_bool()` helpers (null-safe)
3. Implements path field selection logic: if `FOLDER_FILE=true`, use `FOLDER_FILE_PATH`; if `FOLDER=true`, use `DIRECTORY`; otherwise use `FILENAME`
4. Maps to engine config keys (`path`, `fail_on_error`, `is_directory`, `is_folder_file`)
5. Extracts `FAIL_ON_ERROR` (renamed from Talend XML `FAILON` in some exports) with correct default `false`

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `path` | Path field selection: used when FOLDER=false and FOLDER_FILE=false |
| 2 | `DIRECTORY` | Yes | `path` | Path field selection: used when FOLDER=true |
| 3 | `FOLDER_FILE_PATH` | Yes | `path` | Path field selection: used when FOLDER_FILE=true |
| 4 | `FAIL_ON_ERROR` | Yes | `fail_on_error` | Default `false` matches Talend. Note: Talend XML name is `FAIL_ON_ERROR` (not `FAILON`). |
| 5 | `FOLDER` | Yes | `is_directory` | Boolean. Controls path field selection. |
| 6 | `FOLDER_FILE` | Yes | `is_folder_file` | Boolean. Controls path field selection. |
| 7 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Not needed at runtime (tStatCatcher rarely used). |
| 8 | `LABEL` | Yes | `label` | Not needed at runtime (cosmetic). |

**Summary**: All 6 runtime-relevant parameters are correctly extracted and mapped to engine config keys. Path field selection logic implemented. Null-safe extraction via `_get_str`/`_get_bool` helpers.

> **Factual correction (2026-03-25)**: The original audit stated a `RECURSIVE` parameter existed. Standard Talend `tFileDelete` does NOT have a `RECURSIVE` parameter. The engine's `recursive` config key is a v1 extension, not a Talend feature. No `DIE_ON_ERROR` parameter exists on `tFileDelete` either -- the correct name is `FAIL_ON_ERROR`.

### 4.2 Schema Extraction

Schema extraction is irrelevant for `tFileDelete` since it does not produce data flow output. The converter's generic schema extraction logic (lines 475-508 of `component_parser.py`) will attempt to parse `<metadata>` nodes if present, but tFileDelete typically has no metadata/schema definition in Talend XML.

### 4.3 Expression Handling

**Context variable handling** (component_parser.py lines 449-456):
- Simple `context.var` references in path fields (e.g., `context.temp_dir + "/output.csv"`) are detected by checking `'context.' in value`
- If the expression is NOT a Java expression (per `detect_java_expression()`), it is wrapped as `${context.var}` for ContextManager resolution
- If it IS a Java expression (contains `+` operator for concatenation), it is left as-is for the Java expression marking step

**Java expression handling** (component_parser.py lines 462-469):
- After raw parameter extraction, the `mark_java_expression()` method scans all non-CODE/IMPORT/UNIQUE_NAME string values
- Values containing Java operators, method calls, routine references are prefixed with `{{java}}` marker
- However, since the parameter keys are Talend XML names (e.g., `FILENAME`) rather than engine keys (e.g., `path`), the marked expressions are stored under the wrong keys

**Known limitations**:
- Even if Java expressions in path fields are correctly resolved at runtime, the resolved value is stored under `FILENAME` (Talend key), not `path` (engine key). The engine will not find it.
- GlobalMap references in path fields (e.g., `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`) are marked as Java expressions, which requires the Java bridge to be available.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FDL-001 | ~~P1~~ | **FIXED (2026-03-25)**: `talend_to_v1` dedicated parser extracts all params with correct key mapping. Path field selection logic implemented. |
| CONV-FDL-002 | ~~P1~~ | **FIXED (2026-03-25)**: Path field selection logic implemented in `talend_to_v1` converter. Checks FOLDER_FILE, then FOLDER, then defaults to FILENAME. All map to engine `path` key. |
| CONV-FDL-003 | ~~P2~~ | **FIXED (2026-03-25)**: `talend_to_v1` converter sets `fail_on_error` default to `false`, matching Talend. Note: Talend XML name is `FAIL_ON_ERROR` (not `FAILON`). |
| CONV-FDL-004 | ~~P2~~ | **FIXED (2026-03-25)**: `talend_to_v1` converter does not set `recursive=True`. No Talend equivalent exists. Engine extension only. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Delete single file | **Yes** | High | `_process()` lines 116-125 | Uses `os.remove(path)` -- correct |
| 2 | Delete empty directory | **Yes** | High | `_process()` lines 103-115 | Uses `os.rmdir(path)` when `is_directory=True` and `recursive=False` -- correct |
| 3 | Delete file or directory | **Yes** | High | `_process()` lines 86-102 | Uses `is_folder_file` to detect whether path is file or directory, then deletes accordingly -- correct logic |
| 4 | Fail on error | **Yes** | Medium | `_process()` lines 139-140 | Checks `fail_on_error` flag and re-raises. **But default is `True`, Talend default is `false`** |
| 5 | Non-existent file handling | **Yes** | High | `_process()` lines 100-102, 113-115, 123-125 | Logs warning and sets status message. Does not raise when file missing. Correct Talend behavior when `FAIL_ON_ERROR=false`. |
| 6 | Recursive directory deletion | **Partial** | N/A | `_process()` lines 93-94, 107-108 | Uses `shutil.rmtree(path)` when `recursive=True`. **NOT a Talend feature** -- standard Talend `tFileDelete` only deletes empty directories. This is an engine extension that introduces risk (see Security). |
| 7 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 8 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 9 | Path validation | **Yes** | Medium | `_process()` lines 77-80 | Checks `if not path:` and raises `ValueError`. Does not check for path traversal. |
| 10 | Statistics tracking | **Yes** | Medium | `_process()` lines 128-133 | `_update_stats(rows_processed, rows_ok, rows_reject)`. Uses 1/0 for processed/ok/reject. **Not a Talend feature** -- Talend does not set NB_LINE for tFileDelete. |
| 11 | Status message output | **Yes** | Medium | `_process()` return value | Returns `{'main': None, 'status': status_message}`. Not standard Talend output format. |
| 12 | **`{id}_DELETE_PATH` globalMap** | **No** | N/A | -- | **Not implemented. Talend sets this after deletion with the resolved file path.** |
| 13 | **`{id}_CURRENT_STATUS` globalMap** | **No** | N/A | -- | **Not implemented. Talend sets this during execution.** |
| 14 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not implemented. Talend sets this when errors occur with FAIL_ON_ERROR=false.** |
| 15 | **Symlink handling** | **No** | N/A | -- | No explicit symlink handling. Python's `os.remove()` deletes the symlink (not target) on Unix, matching Java behavior. But `shutil.rmtree()` follows symlinks by default in older Python versions, which could cause data loss. |
| 16 | **File lock detection** | **No** | N/A | -- | No explicit file lock detection. OS-level behavior applies. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FDL-001 | **P1** | **`{id}_DELETE_PATH` not set in globalMap**: Talend sets this After variable with the resolved path of the deleted file/directory. Downstream components or logging flows referencing `((String)globalMap.get("tFileDelete_1_DELETE_PATH"))` will get null/None. This variable is commonly used in audit logs and conditional logic. |
| ENG-FDL-002 | **P1** | **`{id}_CURRENT_STATUS` not set in globalMap**: Talend sets this Flow variable with the execution result string. Downstream conditional logic using `((String)globalMap.get("tFileDelete_1_CURRENT_STATUS"))` will fail. |
| ENG-FDL-003 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `FAIL_ON_ERROR=false`, the error message is not stored in globalMap for downstream reference. The base class sets `self.error_message` (line 229 of base_component.py) but does not propagate it to globalMap. |
| ENG-FDL-004 | **P1** | **`fail_on_error` default is `True`, Talend default is `false`**: The engine defaults `fail_on_error` to `True` (line 66: `self.config.get('fail_on_error', True)`), but Talend's `FAIL_ON_ERROR` defaults to `false`. This means: (a) jobs converted without explicit `FAIL_ON_ERROR` will FAIL on missing files when Talend would silently continue; (b) jobs used in PreJob cleanup patterns will break because they rely on the `false` default to tolerate missing files. **This is the most impactful behavioral difference for real-world usage.** |
| ENG-FDL-005 | **P2** | **Recursive directory deletion is NOT a Talend feature**: The engine supports `recursive=True` with `shutil.rmtree()`, but standard Talend `tFileDelete` uses `java.io.File.delete()` which only deletes EMPTY directories. The engine extension allows deleting non-empty directories, which is more powerful but introduces risk: (a) accidental recursive deletion of important directories; (b) no Talend equivalent means converted jobs should never have `recursive=True` set. |
| ENG-FDL-006 | **P2** | **Return format inconsistency**: The engine returns `{'main': None, 'status': status_message}`. The `main` key is `None` (not a DataFrame), which is correct for a non-data-flow component. However, the `status` key is non-standard -- other utility components may use different keys. The base class `execute()` method adds `result['stats']` to the return dict, so the full return is `{'main': None, 'status': '...', 'stats': {...}}`. |
| ENG-FDL-007 | **P2** | **`os.rmdir()` vs `os.remove()` error messages differ**: When `is_directory=True` and the path points to a file (not a directory), `os.path.isdir(path)` returns `False`, so the component reports "Directory does not exist" instead of "Path is a file, not a directory". Similarly, when `is_directory=False` and the path is a directory, `os.path.isfile(path)` returns `False` and the component reports "File does not exist" instead of "Path is a directory, not a file". Misleading error messages. |
| ENG-FDL-008 | **P3** | **`shutil.rmtree()` symlink behavior**: In Python versions before 3.12, `shutil.rmtree()` follows symbolic links by default, which could delete the target directory contents instead of just the symlink. In Python 3.12+, `shutil.rmtree()` no longer follows symlinks. This is platform- and version-dependent behavior that could cause data loss. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_DELETE_PATH` | Yes (After) | **No** | -- | Not implemented. Should be set to the resolved path after deletion. |
| `{id}_CURRENT_STATUS` | Yes (Flow) | **No** | -- | Not implemented. Should be set to "success" or "failure". |
| `{id}_ERROR_MESSAGE` | Yes (After) | **No** | -- | Not implemented. Base class stores in `self.error_message` but does not propagate to globalMap. |
| `{id}_NB_LINE` | No (not standard for tFileDelete) | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | V1-specific; Talend does not set NB_LINE for this component. Not harmful but non-standard. |
| `{id}_NB_LINE_OK` | No | **Yes** | Same mechanism | V1-specific. |
| `{id}_NB_LINE_REJECT` | No | **Yes** | Same mechanism | V1-specific. |
| `{id}_EXECUTION_TIME` | No | **Yes** | Base class | V1-specific. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FDL-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileDelete, since `_update_global_map()` is called after every component execution (via `execute()` line 218 on success, line 231 on error). The component will crash before returning its result. |
| BUG-FDL-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one positional argument (`key`), causing `TypeError`. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FDL-003 | **P1** | `src/v1/engine/components/file/file_delete.py:65` | **Empty string path accepted by `.get()` default**: `path = self.config.get('path', '')` defaults to empty string. The check `if not path:` on line 77 catches this and raises `ValueError`. However, the REAL bug is upstream: the converter stores the path under `FILENAME`/`DIRECTORY`/`FOLDER_FILE_PATH` (Talend key names), not `path` (engine key name). So `self.config.get('path', '')` will ALWAYS return empty string for converted jobs, causing `ValueError("Missing required config: 'path'")` on every execution. |
| BUG-FDL-004 | **P1** | `src/v1/engine/components/file/file_delete.py:66` | **`fail_on_error` default `True` inverts Talend behavior**: `fail_on_error = self.config.get('fail_on_error', True)` defaults to `True`, but Talend defaults `FAIL_ON_ERROR` to `false`. Combined with the converter key mismatch (BUG-FDL-003), even if the converter DID set `FAIL_ON_ERROR=false`, the engine reads `fail_on_error` (different key). The engine default `True` will always be used for converted jobs, causing unexpected failures on missing files. |
| BUG-FDL-005 | **P1** | `src/v1/engine/components/file/file_delete.py:144-176` | **`_validate_config()` is never called**: The method exists and contains 25 lines of validation logic (checking `path` is present and string, `fail_on_error` is boolean, `is_directory` is boolean, `is_folder_file` is boolean, `recursive` is boolean), but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations are not caught until they cause runtime errors in `_process()`. |
| BUG-FDL-006 | **P2** | `src/v1/engine/components/file/file_delete.py:135-140` | **Exception handler catches too broadly then conditionally re-raises**: The `except Exception as e:` block (line 135) catches ALL exceptions, updates stats with `_update_stats(rows_processed, 0, 1)`, and only re-raises if `fail_on_error` is True. For unexpected exceptions like `TypeError`, `MemoryError`, or `KeyboardInterrupt` (Python 2 style), the exception is silently swallowed when `fail_on_error=False`. Should catch `OSError` (file operation errors) specifically, and let other exceptions propagate regardless of `fail_on_error`. |
| BUG-FDL-007 | **P2** | `src/v1/engine/components/file/file_delete.py:83` | **`rows_processed = 1` set before existence check**: Line 83 sets `rows_processed = 1` unconditionally before checking if the file/directory exists. If the file does not exist, `_update_stats(1, 0, 1)` reports 1 row processed and 1 rejected. While not technically wrong, it would be more accurate to set `rows_processed = 0` when the target does not exist, since no deletion was attempted. Talend does not report NB_LINE for this component, so this is a consistency issue with v1 conventions. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FDL-001 | **P2** | **Engine config key `path` vs Talend's three separate path fields**: Talend has `FILENAME`, `DIRECTORY`, and `FOLDER_FILE_PATH` as separate fields with visibility controlled by checkboxes. The engine collapses these into a single `path` key. This is a reasonable simplification, but the converter must implement the selection logic. |
| NAME-FDL-002 | **P2** | **Engine config key `is_directory` vs Talend's `FOLDER`**: The Talend parameter is named `FOLDER` (a checkbox), while the engine uses `is_directory` (a boolean). The naming difference is reasonable (more descriptive), but the converter must perform the mapping. |
| NAME-FDL-003 | **P3** | **Engine config key `is_folder_file` vs Talend's `FOLDER_FILE`**: Similar naming difference. The engine uses a more descriptive name with `is_` prefix following Python boolean naming conventions. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FDL-001 | **P1** | "Every component MUST have its own `parse_*` method" | Uses `parse_base_component()` with no dedicated `parse_tfiledelete()` method. Falls through to `return config_raw` default. No parameter key mapping occurs. |
| STD-FDL-002 | **P2** | "`_validate_config()` returns `List[str]`" | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FDL-003 | **P3** | "No `print()` statements" | No print statements in `file_delete.py`. Compliant. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FDL-001 | **P3** | **Docstring references `FileOperationError`**: The docstring on line 62 says `Raises: FileOperationError: If deletion fails and fail_on_error is True`, but the code actually raises the original OS exception (e.g., `PermissionError`, `OSError`) via bare `raise` on line 140. It does not wrap in `FileOperationError`. The docstring is misleading. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FDL-001 | **P1** | **No path traversal protection**: `path` from config is used directly with `os.path.isfile()`, `os.remove()`, `os.rmdir()`, and `shutil.rmtree()`. If config comes from untrusted sources (e.g., globalMap variables set by upstream components processing external data), path traversal (`../../etc/important_dir`) could delete arbitrary files or directories. For converted Talend jobs where config is trusted, this is lower risk. But the `recursive=True` + `shutil.rmtree()` combination is particularly dangerous -- a single path traversal could recursively delete an entire directory tree. |
| SEC-FDL-002 | **P2** | **`shutil.rmtree()` recursive deletion is an engine extension with no Talend equivalent**: Standard Talend `tFileDelete` only deletes empty directories. The v1 engine's `recursive=True` support with `shutil.rmtree()` is an extension that has no safety equivalent in Talend. A misconfigured or maliciously crafted job could use `recursive=True` to delete critical directory trees. Consider: (a) adding a configurable allowlist of directories that can be recursively deleted; (b) adding a maximum depth limit; (c) requiring explicit confirmation for paths outside a sandbox. |
| SEC-FDL-003 | **P3** | **No audit logging of deleted paths**: While the component logs the path at INFO level, there is no separate audit trail for destructive operations. For compliance in regulated environments, file deletions should be logged to a dedicated audit log with timestamp, user, and path. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete milestones, WARNING for non-existent files, ERROR for failures -- correct |
| Start logging | `_process()` logs start on line 71: `"Delete operation started: {path}"` -- correct |
| Complete logging | `_process()` logs completion on lines 132-133 with stats -- correct |
| Sensitive data | No sensitive data logged (paths are not typically sensitive) -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use `FileOperationError` despite docstring claiming it does. Raises `ValueError` for missing path (line 80) and re-raises original OS exceptions (line 140). |
| Exception specificity | `except Exception as e:` on line 135 is too broad. Should catch `OSError` specifically for file operation errors. |
| `fail_on_error` handling | Single try/except block handles the flag correctly -- re-raises when True, suppresses when False. |
| No bare `except` | Uses `except Exception as e:` -- correct (not bare `except:`). |
| Error messages | Include component ID and path -- correct. |
| Graceful degradation | Returns status message when `fail_on_error=False` -- correct. |
| Exception chaining | Does NOT use `raise ... from e` pattern. Uses bare `raise` (line 140) which preserves the original traceback. Acceptable but less informative than explicit chaining. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has full type hints: `(self, input_data: Optional[Any] = None) -> Dict[str, Any]` -- correct |
| `_validate_config()` | Has return type hint: `-> List[str]` -- correct |
| Class-level type hints | No class-level type annotations for instance variables. Minor gap. |
| Import completeness | Imports `Dict`, `Any`, `List`, `Optional` from `typing` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FDL-001 | **P3** | **Redundant `os.path` checks in `is_folder_file` mode**: When `is_folder_file=True`, the code checks `os.path.isfile(path)` (line 87), then `os.path.isdir(path)` (line 92) if the first fails. These are two separate system calls. Could use `os.path.exists(path)` first to check existence, then `os.path.isfile()` to determine type. Negligible impact since file deletion is I/O-bound, not CPU-bound. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Memory footprint | Negligible. The component does not load file contents into memory. It only performs filesystem metadata operations (`os.path.isfile()`, `os.remove()`, etc.). |
| No DataFrame processing | Component returns `{'main': None}`, so no DataFrame memory overhead. |
| `shutil.rmtree()` | Walks the directory tree sequentially. Memory usage is proportional to directory depth, not file count. Acceptable. |
| No streaming concerns | Not applicable -- no data flow processing. |

### 7.2 HYBRID / Streaming Mode Behavior

| Issue | Description |
|-------|-------------|
| Mode selection | `BaseComponent._auto_select_mode()` receives `input_data=None` (since tFileDelete does not process input data). Returns `ExecutionMode.BATCH`. Correct. |
| Streaming mode irrelevant | Since `_process()` ignores `input_data` and performs a standalone file operation, execution mode has no impact. The component behaves identically in BATCH, STREAMING, and HYBRID modes. |
| `_execute_streaming()` path | If somehow called with non-None input_data in STREAMING mode, `_execute_streaming()` would call `_process(chunk)` which ignores the chunk. The return `{'main': None}` would cause `results.append(None)` -> `pd.concat([None, None, ...])` which raises `TypeError`. Not a practical concern since tFileDelete should never receive input data. |

### 7.3 Thread Safety

| Aspect | Assessment |
|--------|------------|
| Concurrent deletion | If multiple `FileDelete` instances target the same path concurrently, race conditions can occur: both check `os.path.isfile()` -> True, first deletes, second gets `FileNotFoundError`. The `fail_on_error=False` path handles this gracefully (warns and continues). The `fail_on_error=True` path would raise an unexpected error. |
| `shutil.rmtree()` concurrency | If two instances call `shutil.rmtree()` on overlapping directory trees, the behavior is undefined and could result in partial deletion errors. |
| Stats update | `_update_stats()` uses `+=` on `self.stats` dict values. Not thread-safe. If called from multiple threads, stats could be corrupted. Base class issue, not specific to FileDelete. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileDelete` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for tFileDelete parameter mapping |

**Key finding**: The v1 engine has ZERO tests for this component. All 175 lines of v1 engine code are completely unverified. The converter's handling of tFileDelete (falling through to `return config_raw`) is also untested.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Delete existing file | P0 | Create a temporary file, run FileDelete with `path` pointing to it, verify file no longer exists. Verify return dict has `{'main': None, 'status': 'File (or path) deleted.'}`. |
| 2 | Delete non-existent file + fail_on_error=True | P0 | Run FileDelete with path to non-existent file and `fail_on_error=True`. Should raise `FileNotFoundError` or `OSError`. Verify error message includes the path. |
| 3 | Delete non-existent file + fail_on_error=False | P0 | Run FileDelete with path to non-existent file and `fail_on_error=False`. Should return without error. Verify status message indicates file does not exist. Verify stats: `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=1`. |
| 4 | Missing path config | P0 | Run FileDelete with empty config (no `path` key). Should raise `ValueError("Missing required config: 'path'")`. |
| 5 | Delete empty directory | P0 | Create a temporary empty directory, run FileDelete with `is_directory=True`. Verify directory no longer exists. |
| 6 | Statistics tracking | P0 | After successful deletion, verify stats dict has `NB_LINE=1, NB_LINE_OK=1, NB_LINE_REJECT=0`. After failed deletion (file missing, fail_on_error=False), verify `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=1`. |
| 7 | Converter key mapping failure | P0 | Create a FileDelete instance with config `{'FILENAME': '/tmp/test.txt', 'FAIL_ON_ERROR': False}` (Talend key names). Verify that `self.config.get('path', '')` returns empty string, demonstrating the converter key mismatch bug. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Delete non-empty directory + recursive=True | P1 | Create directory with files, run FileDelete with `is_directory=True, recursive=True`. Verify entire tree deleted. |
| 9 | Delete non-empty directory + recursive=False | P1 | Create directory with files, run FileDelete with `is_directory=True, recursive=False`. Should fail (OSError from `os.rmdir()` on non-empty dir). Verify behavior with both `fail_on_error` settings. |
| 10 | is_folder_file=True with file path | P1 | Create a file, run with `is_folder_file=True`. Verify file deleted correctly. |
| 11 | is_folder_file=True with directory path | P1 | Create empty directory, run with `is_folder_file=True`. Verify directory deleted correctly. |
| 12 | is_folder_file=True with non-existent path | P1 | Run with `is_folder_file=True` and non-existent path. Verify warning logged and graceful handling. |
| 13 | Context variable in path | P1 | Set `path="${context.temp_dir}/file.txt"`, verify context resolution via context_manager before `_process()`. |
| 14 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. (Requires fixing BUG-FDL-001 and BUG-FDL-002 first.) |
| 15 | Exception type with fail_on_error=True | P1 | Trigger a `PermissionError` (e.g., read-only file on Linux), verify the original exception type is preserved (not wrapped in `FileOperationError`). |
| 16 | fail_on_error default value | P1 | Run FileDelete with no `fail_on_error` in config. Verify default is `True` (engine behavior). Document this differs from Talend default `false`. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Path with spaces | P2 | Delete file at `/tmp/path with spaces/file.txt`. Verify correct handling. |
| 18 | Path with unicode characters | P2 | Delete file with unicode path. Verify correct handling. |
| 19 | Symlink deletion | P2 | Create a symlink, delete it. Verify symlink removed but target untouched. |
| 20 | Concurrent deletion of same file | P2 | Two FileDelete instances targeting same file. Verify at least one succeeds and no unhandled exception. |
| 21 | Empty string path | P2 | Set `path=""`. Verify `ValueError` raised with descriptive message. |
| 22 | Path is None | P2 | Set `path=None`. Verify `ValueError` raised (since `not None` is True, the `if not path:` check catches this). |
| 23 | Very long path | P2 | Test with path exceeding OS maximum (typically 260 chars on Windows, 4096 on Linux). Verify appropriate error. |
| 24 | Read-only file system | P2 | Attempt deletion on read-only filesystem. Verify `PermissionError` is raised and handled correctly based on `fail_on_error`. |
| 25 | Recursive deletion of directory with symlinks | P2 | Create directory tree containing symlinks. Run `shutil.rmtree()` path. Verify symlinks are removed but targets are not followed (Python 3.12+ behavior). |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FDL-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. Prevents any component from completing execution. |
| BUG-FDL-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FDL-001 | Testing | Zero v1 unit tests for this component. All 175 lines of v1 engine code are unverified. Zero converter tests for tFileDelete parameter mapping. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FDL-001 | Converter | No dedicated parser method -- uses `parse_base_component()` which falls through to `return config_raw` default. ALL Talend XML parameter names passed through verbatim. Engine cannot find `path` key, causing total runtime failure for all converted tFileDelete jobs. |
| CONV-FDL-002 | Converter | Path field selection logic missing. Talend has THREE mutually exclusive path fields (`FILENAME`, `DIRECTORY`, `FOLDER_FILE_PATH`) controlled by checkboxes. Converter does not implement selection logic. |
| ENG-FDL-001 | Engine | `{id}_DELETE_PATH` globalMap variable not set. Downstream components referencing the deleted path get null. |
| ENG-FDL-002 | Engine | `{id}_CURRENT_STATUS` globalMap variable not set. Downstream conditional logic using status gets null. |
| ENG-FDL-003 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set. Error details not available downstream. |
| ENG-FDL-004 | Engine | `fail_on_error` default `True` inverts Talend's `false` default. PreJob cleanup patterns and tolerant deletion flows will break. |
| BUG-FDL-003 | Bug | Converter key mismatch: engine reads `path` but converter stores under `FILENAME`/`DIRECTORY`/`FOLDER_FILE_PATH`. Every converted job fails with `ValueError("Missing required config: 'path'")`. |
| BUG-FDL-004 | Bug | `fail_on_error` default `True` combined with converter key mismatch. Even if converter set `FAIL_ON_ERROR=false`, engine reads `fail_on_error` (different key), always getting `True`. |
| BUG-FDL-005 | Bug | `_validate_config()` is dead code -- never called by any code path. 25 lines of unreachable validation. |
| SEC-FDL-001 | Security | No path traversal protection. `shutil.rmtree()` with `recursive=True` and untrusted path input could recursively delete arbitrary directory trees. |
| STD-FDL-001 | Standards | Uses `parse_base_component()` with no dedicated `parse_tfiledelete()` method. Violates standard requiring dedicated parsers. |
| TEST-FDL-002 | Testing | No integration test for tFileDelete in a multi-step v1 job (e.g., tFileList -> tFileDelete). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FDL-003 | Converter | `FAIL_ON_ERROR` default mismatch: engine defaults to `True`, Talend defaults to `false`. |
| CONV-FDL-004 | Converter | `recursive` config key not populated from converter. No Talend equivalent exists. Engine supports it as an extension, but converted jobs should never use it. |
| ENG-FDL-005 | Engine | Recursive directory deletion is NOT a Talend feature. Engine extension introduces risk with `shutil.rmtree()`. |
| ENG-FDL-006 | Engine | Return format `{'main': None, 'status': '...'}` may not be consistent with other utility components. |
| ENG-FDL-007 | Engine | Misleading error messages when path type mismatches mode (file path with `is_directory=True` reports "Directory does not exist" instead of "Path is a file"). |
| BUG-FDL-006 | Bug | Exception handler `except Exception` is too broad. Should catch `OSError` specifically. `MemoryError`, `KeyboardInterrupt` (Python 2), `SystemExit` could be silently swallowed when `fail_on_error=False`. |
| BUG-FDL-007 | Bug | `rows_processed = 1` set unconditionally before existence check. Reports 1 processed even when target does not exist. |
| NAME-FDL-001 | Naming | Engine key `path` vs Talend's three separate path fields (`FILENAME`, `DIRECTORY`, `FOLDER_FILE_PATH`). |
| NAME-FDL-002 | Naming | Engine key `is_directory` vs Talend's `FOLDER`. |
| SEC-FDL-002 | Security | `shutil.rmtree()` recursive deletion has no Talend equivalent and no safety guards (allowlist, depth limit, sandbox). |
| STD-FDL-002 | Standards | `_validate_config()` exists but never called -- dead validation code. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-FDL-008 | Engine | `shutil.rmtree()` symlink behavior is Python-version-dependent (follows symlinks before 3.12). |
| NAME-FDL-003 | Naming | Engine key `is_folder_file` vs Talend's `FOLDER_FILE`. Minor naming difference. |
| SEC-FDL-003 | Security | No dedicated audit logging for destructive file operations. |
| STD-FDL-003 | Standards | No `print()` statements -- compliant. |
| DBG-FDL-001 | Debug | Docstring claims `FileOperationError` is raised but code re-raises original OS exceptions. |
| PERF-FDL-001 | Performance | Redundant `os.path` checks in `is_folder_file` mode. Negligible impact. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 12 | 2 converter, 3 engine, 3 bugs, 1 security, 1 standards, 2 testing |
| P2 | 11 | 2 converter, 3 engine, 2 bugs, 2 naming, 1 security, 1 standards |
| P3 | 6 | 1 engine, 1 naming, 1 security, 1 standards, 1 debug, 1 performance |
| **Total** | **32** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FDL-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FDL-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both the `NameError` (direct calls) and the `TypeError` (two-argument call from `get_component_stat()` on line 58). **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create dedicated converter parser** (CONV-FDL-001, CONV-FDL-002, BUG-FDL-003, BUG-FDL-004): Add a `parse_tfiledelete(self, node, component)` method in `component_parser.py` that maps Talend XML parameters to engine config keys. Register in `converter.py` line 285. This is the single most critical fix -- without it, ALL converted tFileDelete jobs fail at runtime. See Appendix K for implementation.

4. **Create unit test suite** (TEST-FDL-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic file deletion, missing file handling (both fail_on_error modes), missing path config, empty directory deletion, statistics tracking, and converter key mapping verification.

5. **Fix `fail_on_error` default** (ENG-FDL-004, CONV-FDL-003): Change engine default from `True` to `False` on line 66 of `file_delete.py`: `fail_on_error = self.config.get('fail_on_error', False)`. This matches Talend's `FAIL_ON_ERROR` default. **Impact**: PreJob cleanup patterns and tolerant deletion flows will work correctly. **Risk**: Low -- changes error handling from strict to permissive by default, which matches Talend behavior.

### Short-Term (Hardening)

6. **Set `{id}_DELETE_PATH`, `{id}_CURRENT_STATUS`, and `{id}_ERROR_MESSAGE` in globalMap** (ENG-FDL-001, ENG-FDL-002, ENG-FDL-003): After deletion, call:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_DELETE_PATH", path)
       self.global_map.put(f"{self.id}_CURRENT_STATUS", "success" if deleted else "failure")
   ```
   In the error handler:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
       self.global_map.put(f"{self.id}_CURRENT_STATUS", "failure")
   ```

7. **Wire up `_validate_config()`** (BUG-FDL-005): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` if non-empty. Alternatively, add validation as a standard lifecycle step in `BaseComponent.execute()`.

8. **Narrow exception handler** (BUG-FDL-006): Change `except Exception as e:` on line 135 to `except OSError as e:`. This catches all filesystem errors (`FileNotFoundError`, `PermissionError`, `IsADirectoryError`, `NotADirectoryError`) while letting programming errors (`TypeError`, `AttributeError`) propagate regardless of `fail_on_error`.

9. **Add path traversal protection** (SEC-FDL-001): Validate the resolved path against allowed base directories before performing deletion. For converted Talend jobs, the base directories should be the job's configured output directories. For `shutil.rmtree()` specifically, add a safety check that prevents deletion of system directories or paths above a configurable root.

10. **Fix misleading error messages** (ENG-FDL-007): When `is_directory=True` but path points to a file, log "Path exists but is a file, not a directory: {path}" instead of "Directory does not exist: {path}". Similarly for the reverse case.

### Long-Term (Optimization)

11. **Add `recursive` safety guards** (SEC-FDL-002, ENG-FDL-005): Since recursive deletion is an engine extension with no Talend equivalent, add: (a) a configurable allowlist of directories permitted for recursive deletion; (b) a maximum depth limit (default 5); (c) refuse to recursively delete paths containing `..` or absolute paths above a configured root.

12. **Improve statistics for non-data-flow components** (BUG-FDL-007): Define a clear convention for `NB_LINE` in utility components. Options: (a) always 0 (not applicable); (b) 1 if operation attempted, 0 if not; (c) remove `_update_stats()` call for utility components. Document the chosen convention.

13. **Create integration test** (TEST-FDL-002): Build an end-to-end test exercising `tFileList -> tFileDelete` in the v1 engine, verifying context resolution, Java bridge integration, and globalMap propagation. Verify that `DELETE_PATH` and `CURRENT_STATUS` are set correctly for each iteration.

14. **Add audit logging** (SEC-FDL-003): For compliance in regulated environments, log all file deletion operations to a dedicated audit log with timestamp, component ID, resolved path, and outcome (success/failure/skipped).

---

## Appendix A: Converter Parameter Mapping Code

### Current State (BROKEN)

```python
# converter.py lines 284-285
elif component_type == 'tFileDelete':
    component = self.component_parser.parse_base_component(node)
```

This calls `parse_base_component()` which:
1. Extracts all `elementParameter` nodes into `config_raw` dict with Talend XML names
2. Calls `_map_component_parameters('tFileDelete', config_raw)` (line 472)
3. Falls through to `else: return config_raw` (line 385-386) since there is no `tFileDelete` branch
4. Returns raw config with Talend parameter names (`FILENAME`, `FAIL_ON_ERROR`, `FOLDER`, etc.)

The engine then reads:
- `self.config.get('path', '')` -> empty string (path is under `FILENAME`)
- `self.config.get('fail_on_error', True)` -> `True` (value is under `FAIL_ON_ERROR`)
- `self.config.get('is_directory', False)` -> `False` (value is under `FOLDER`)
- `self.config.get('is_folder_file', False)` -> `False` (value is under `FOLDER_FILE`)

**Result**: Every converted tFileDelete job fails with `ValueError("Missing required config: 'path'")`.

### Component Type Mapping (Working)

```python
# component_parser.py line 31
'tFileDelete': 'FileDelete',
```

This mapping correctly translates `tFileDelete` to `FileDelete` for engine dispatch. The component type mapping works; only the parameter key mapping is broken.

---

## Appendix B: Engine Class Structure

```
FileDelete (BaseComponent)
    Config Keys:
        path (str)             # File or directory path to delete. Required.
        fail_on_error (bool)   # Whether to fail on error. Default: True (BUG: should be False)
        is_directory (bool)    # Treat path as directory. Default: False
        is_folder_file (bool)  # Delete file or directory, whichever exists. Default: False
        recursive (bool)       # Delete directories recursively. Default: False (NO Talend equivalent)

    Methods:
        _process(input_data) -> Dict[str, Any]    # Main entry point (lines 48-142)
        _validate_config() -> List[str]            # DEAD CODE -- never called (lines 144-176)

    Return Format:
        {'main': None, 'status': status_message}
        After base class execute(): {'main': None, 'status': '...', 'stats': {...}}

    Statistics:
        NB_LINE: 1 if deletion attempted, 0 if not
        NB_LINE_OK: 1 if deleted, 0 if not
        NB_LINE_REJECT: 0 if deleted, 1 if not (or if error)
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `path` | **Not Mapped** | P1 (critical) |
| `DIRECTORY` | `path` | **Not Mapped** | P1 (critical) |
| `FOLDER_FILE_PATH` | `path` | **Not Mapped** | P1 (critical) |
| `FAIL_ON_ERROR` | `fail_on_error` | **Not Mapped** | P1 (critical) |
| `FOLDER` | `is_directory` | **Not Mapped** | P1 (critical) |
| `FOLDER_FILE` | `is_folder_file` | **Not Mapped** | P1 (critical) |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| -- (no Talend equiv) | `recursive` | Engine extension | Should default to False; consider removing or guarding |

---

## Appendix D: Decision Logic for Path Field Selection

Talend's three path fields are mutually exclusive, controlled by two checkboxes:

```
IF FOLDER_FILE == true:
    path = FOLDER_FILE_PATH
    is_folder_file = True
    is_directory = False
ELIF FOLDER == true:
    path = DIRECTORY
    is_directory = True
    is_folder_file = False
ELSE:
    path = FILENAME
    is_directory = False
    is_folder_file = False
```

The dedicated parser must implement this logic to produce the correct engine config. See Appendix K for the full implementation.

---

## Appendix E: Detailed `_validate_config()` Analysis (Lines 144-176)

This method validates:
- `path` is present in config (line 154)
- `path` is a string (line 156-157)
- `fail_on_error` is boolean if present (line 160-161)
- `is_directory` is boolean if present (line 163-164)
- `is_folder_file` is boolean if present (line 167-168)
- `recursive` is boolean if present (line 172-173)

**Not validated**:
- Path is not empty string (only checks presence and type)
- Path is absolute (Talend requires absolute paths)
- `is_directory` and `is_folder_file` are not both True simultaneously
- `recursive` is not True when `is_directory` is False (recursive only makes sense for directories)

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions. The method signature `_validate_config() -> List[str]` follows the base class contract, but the contract is not enforced.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Non-existent file with fail_on_error=False

| Aspect | Detail |
|--------|--------|
| **Talend** | Completes successfully. `DELETE_PATH` set to attempted path. `CURRENT_STATUS` set to completion status. No error. |
| **V1** | Logs warning "File does not exist: {path}". Sets `status_message = "File (or path) does not exist or is invalid."`. Updates stats `(1, 0, 1)`. Returns `{'main': None, 'status': '...'}`. Does NOT set `DELETE_PATH` or `CURRENT_STATUS` in globalMap. |
| **Verdict** | PARTIAL -- core behavior correct but globalMap variables missing. |

### Edge Case 2: Non-existent file with fail_on_error=True

| Aspect | Detail |
|--------|--------|
| **Talend** | Job execution prevented. Error reported. |
| **V1** | Logs warning "File does not exist: {path}". Sets status message. Updates stats `(1, 0, 1)`. Returns normally (does NOT raise). The `raise` on line 140 is only reached in the `except Exception` handler, and file non-existence does not raise an exception -- it's handled by the `if os.path.isfile(path)` branch. |
| **Verdict** | **GAP**: File non-existence is NOT treated as an error even when `fail_on_error=True`. The code only re-raises exceptions from `os.remove()` / `os.rmdir()` / `shutil.rmtree()`. Non-existence is handled by the `else` branches which log a warning but do not raise. |

### Edge Case 3: Permission denied on file deletion

| Aspect | Detail |
|--------|--------|
| **Talend** | `java.io.File.delete()` returns false. If `FAIL_ON_ERROR=true`, job fails. |
| **V1** | `os.remove(path)` raises `PermissionError` (subclass of `OSError`). Caught by `except Exception as e:`. If `fail_on_error=True`, re-raised. If `fail_on_error=False`, suppressed with status message. |
| **Verdict** | CORRECT |

### Edge Case 4: Non-empty directory with is_directory=True, recursive=False

| Aspect | Detail |
|--------|--------|
| **Talend** | `java.io.File.delete()` returns false (cannot delete non-empty dir). If `FAIL_ON_ERROR=true`, job fails. |
| **V1** | `os.rmdir(path)` raises `OSError: Directory not empty`. Caught by `except Exception`. Behavior depends on `fail_on_error`. |
| **Verdict** | CORRECT -- matches Talend behavior for non-empty directories. |

### Edge Case 5: Non-empty directory with is_directory=True, recursive=True

| Aspect | Detail |
|--------|--------|
| **Talend** | NOT POSSIBLE -- standard Talend tFileDelete does not support recursive deletion. |
| **V1** | `shutil.rmtree(path)` deletes entire directory tree. Succeeds silently. |
| **Verdict** | **ENGINE EXTENSION** -- no Talend equivalent. Risk of accidental data loss. |

### Edge Case 6: Path is a symlink to a file

| Aspect | Detail |
|--------|--------|
| **Talend** | `java.io.File.delete()` deletes the symlink, not the target. Standard Java behavior. |
| **V1** | `os.path.isfile(path)` returns True for symlinks to files. `os.remove(path)` deletes the symlink, not the target. |
| **Verdict** | CORRECT |

### Edge Case 7: Path is a symlink to a directory

| Aspect | Detail |
|--------|--------|
| **Talend** | `java.io.File.delete()` deletes the symlink. |
| **V1** | `os.path.isdir(path)` returns True for symlinks to directories. If `recursive=False`, `os.rmdir(path)` fails (it's a symlink, not a dir). If `recursive=True`, `shutil.rmtree(path)` may follow the symlink and delete the target directory contents (Python < 3.12). |
| **Verdict** | **GAP (recursive=True)** -- may follow symlinks and delete target directory contents in Python < 3.12. |

### Edge Case 8: Path with trailing slash

| Aspect | Detail |
|--------|--------|
| **Talend** | Java `File` class normalizes trailing slashes. |
| **V1** | Python `os.path.isfile("/path/to/file/")` returns False even if the file exists (trailing slash implies directory). `os.path.isdir("/path/to/dir/")` returns True. This could cause file deletion to fail silently if path has trailing slash. |
| **Verdict** | **MINOR GAP** -- trailing slash on file path causes silent failure. |

### Edge Case 9: Empty DataFrame input (input_data is empty DataFrame)

| Aspect | Detail |
|--------|--------|
| **Talend** | tFileDelete ignores input data flow. Standalone action. |
| **V1** | `_process()` signature accepts `input_data: Optional[Any] = None` but never uses it. Empty DataFrame passed as input is ignored. |
| **Verdict** | CORRECT |

### Edge Case 10: NaN value in path (path is float NaN)

| Aspect | Detail |
|--------|--------|
| **Talend** | Not possible -- path is always a string expression. |
| **V1** | If `path` is `float('nan')`, the `if not path:` check on line 77 fails (NaN is truthy). `os.path.isfile(NaN)` raises `TypeError`. Caught by `except Exception`. Handled based on `fail_on_error`. |
| **Verdict** | ACCEPTABLE -- NaN path is a programming error caught by exception handler. |

### Edge Case 11: Path is empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | Would fail at job startup validation. |
| **V1** | `path = self.config.get('path', '')` returns empty string. `if not path:` check on line 77 catches it. Raises `ValueError("Missing required config: 'path'")`. |
| **Verdict** | CORRECT |

### Edge Case 12: is_directory=True AND is_folder_file=True simultaneously

| Aspect | Detail |
|--------|--------|
| **Talend** | Not possible in UI -- the checkboxes are mutually exclusive (selecting one hides the other's field). |
| **V1** | `is_folder_file` is checked first (line 86). If True, the `is_directory` branch (line 103) is never reached. The `is_folder_file` logic handles both files and directories. |
| **Verdict** | ACCEPTABLE -- `is_folder_file` takes precedence. But `_validate_config()` should warn about this invalid combination (currently dead code). |

### Edge Case 13: Concurrent deletion race condition

| Aspect | Detail |
|--------|--------|
| **Talend** | Not explicitly handled. `java.io.File.delete()` is atomic at the OS level. |
| **V1** | TOCTOU race: `os.path.isfile(path)` returns True, another thread deletes file, `os.remove(path)` raises `FileNotFoundError`. Caught by `except Exception`. Handled based on `fail_on_error`. |
| **Verdict** | ACCEPTABLE -- race condition handled by exception handler. |

### Edge Case 14: HYBRID streaming mode with non-None input

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- tFileDelete does not accept input data flow. |
| **V1** | If `execute()` is called with a non-None DataFrame in STREAMING mode, `_execute_streaming()` iterates chunks, calls `_process(chunk)` for each. `_process()` ignores `chunk`. Returns `{'main': None}`. `results.append(None)`. `pd.concat([None, None, ...])` raises `TypeError`. |
| **Verdict** | **BUG (edge case)** -- `_execute_streaming()` cannot handle components that return `{'main': None}`. This is a base class design issue: utility components that return `None` for main output are incompatible with streaming concatenation logic. Low practical impact since tFileDelete should never receive input data. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileDelete`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FDL-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FDL-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FDL-005 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FDL-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FDL-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: ENG-FDL-004 -- `fail_on_error` default mismatch

**File**: `src/v1/engine/components/file/file_delete.py`
**Line**: 66

**Current code**:
```python
fail_on_error = self.config.get('fail_on_error', True)
```

**Fix**:
```python
fail_on_error = self.config.get('fail_on_error', False)
```

**Explanation**: Talend's `FAIL_ON_ERROR` defaults to `false`. The engine should match. PreJob cleanup patterns rely on the `false` default to tolerate missing files on first runs.

**Impact**: Changes default error handling from strict to permissive. **Risk**: Low -- matches Talend behavior. Jobs that explicitly set `fail_on_error=True` are unaffected.

---

### Fix Guide: Edge Case 2 -- Non-existent file not treated as error with fail_on_error=True

**File**: `src/v1/engine/components/file/file_delete.py`
**Lines**: 100-102, 113-115, 123-125

**Current code** (example for file mode, line 123-125):
```python
else:
    logger.warning(f"[{self.id}] File does not exist: {path}")
    status_message = "File (or path) does not exist or is invalid."
```

**Fix**:
```python
else:
    if fail_on_error:
        error_msg = f"File does not exist: {path}"
        logger.error(f"[{self.id}] {error_msg}")
        raise FileNotFoundError(f"[{self.id}] {error_msg}")
    else:
        logger.warning(f"[{self.id}] File does not exist: {path}")
        status_message = "File (or path) does not exist or is invalid."
```

Apply the same pattern to all three "does not exist" branches (lines 100-102, 113-115, 123-125).

**Impact**: Non-existent files/directories now raise errors when `fail_on_error=True`, matching Talend behavior. **Risk**: Medium -- may cause failures in jobs that previously succeeded silently. Should be paired with fixing the default to `False`.

---

### Fix Guide: ENG-FDL-001/002/003 -- Set globalMap variables

**File**: `src/v1/engine/components/file/file_delete.py`

Add after the `_update_stats()` call (after line 133):
```python
# Set Talend-compatible globalMap variables
if self.global_map:
    self.global_map.put(f"{self.id}_DELETE_PATH", path)
    self.global_map.put(f"{self.id}_CURRENT_STATUS", "success" if deleted else "failure")
```

Add in the `except Exception` handler (after line 138):
```python
if self.global_map:
    self.global_map.put(f"{self.id}_DELETE_PATH", path)
    self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    self.global_map.put(f"{self.id}_CURRENT_STATUS", "failure")
```

**Impact**: Enables downstream components to reference deletion path, status, and error message via globalMap. **Risk**: Low.

---

## Appendix I: Comparison with Other File Utility Components

| Feature | tFileDelete (V1) | tFileCopy (V1) | tFileExist (V1) | tFileTouch (V1) |
|---------|-------------------|----------------|-----------------|-----------------|
| Basic operation | Yes | Yes | Yes | Yes |
| Dedicated converter parser | **No** | Yes | Yes | Yes |
| GlobalMap DELETE_PATH/etc. | **No** | N/A | N/A | N/A |
| GlobalMap ERROR_MESSAGE | **No** | Unknown | Unknown | Unknown |
| fail_on_error default matches Talend | **No (True vs false)** | Unknown | Unknown | Unknown |
| `_validate_config()` called | **No** | **No** | **No** | **No** |
| V1 Unit tests | **No** | **No** | **No** | **No** |

**Observation**: The lack of a dedicated converter parser is unique to `tFileDelete` among the file utility components. Other utility components (`tFileCopy`, `tFileExist`, `tFileTouch`) all have dedicated `parse_*` methods. The dead `_validate_config()` and lack of unit tests are systemic issues across ALL components.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| ALL converted tFileDelete jobs | **Critical** | Every job containing tFileDelete | Converter parameter key mapping is broken. No converted job can execute. Must implement dedicated parser (CONV-FDL-001). |
| Jobs relying on fail_on_error=false default | **High** | PreJob cleanup, first-run scenarios | Fix engine default to match Talend (ENG-FDL-004). |
| Jobs using DELETE_PATH downstream | **High** | Audit/logging flows referencing deletion path | Implement globalMap variable setting (ENG-FDL-001). |
| Jobs using CURRENT_STATUS in conditional logic | **High** | Run-If triggers based on deletion status | Implement CURRENT_STATUS globalMap (ENG-FDL-002). |
| Jobs using ERROR_MESSAGE in error handling | **Medium** | Error handling flows | Implement ERROR_MESSAGE globalMap (ENG-FDL-003). |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using tStatCatcher with tFileDelete | Low | tStatCatcher rarely used |
| Jobs requiring recursive deletion | Low | Not a Talend feature; manual config only |
| Jobs using symlinks in deletion paths | Low | Python behavior matches Java for file symlinks |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting). Implement dedicated converter parser. Fix `fail_on_error` default.
2. **Phase 2**: Add globalMap variable support. Create unit test suite.
3. **Phase 3**: Run converted tFileDelete jobs against known test cases. Verify path resolution, error handling, and globalMap propagation.
4. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare behavior for all deletion scenarios.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix K: Complete Dedicated Parser Implementation

The following is the recommended replacement for the generic `parse_base_component()` approach. This method should be added to `component_parser.py` and registered in `converter.py`.

```python
def parse_tfiledelete(self, node, component: Dict) -> Dict:
    """
    Parse tFileDelete specific configuration from Talend XML node.

    Maps Talend XML parameters to engine-expected config keys:
        FILENAME / DIRECTORY / FOLDER_FILE_PATH -> path
        FAIL_ON_ERROR -> fail_on_error
        FOLDER -> is_directory
        FOLDER_FILE -> is_folder_file

    Talend Parameters:
        FILENAME (str): File path for deletion. Mandatory in default mode.
        DIRECTORY (str): Directory path for deletion. Mandatory when FOLDER=true.
        FOLDER_FILE_PATH (str): File or directory path. Mandatory when FOLDER_FILE=true.
        FAIL_ON_ERROR (bool): Fail on deletion error. Default false.
        FOLDER (bool): Enable directory deletion mode. Default false.
        FOLDER_FILE (bool): Enable file-or-directory deletion mode. Default false.
    """
    config = component.get('config', {})

    # Collect raw parameters
    raw = {}
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')
        field = param.get('field', '')

        if not name or name == 'UNIQUE_NAME':
            continue

        # Strip surrounding quotes
        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        # Convert boolean CHECK fields
        if field == 'CHECK':
            value = value.lower() == 'true'
        elif isinstance(value, str) and 'context.' in value:
            if not self.expr_converter.detect_java_expression(value):
                value = '${' + value + '}'

        raw[name] = value

    # Mark Java expressions
    skip_fields = ['CODE', 'IMPORT', 'UNIQUE_NAME']
    for key, value in raw.items():
        if key not in skip_fields and isinstance(value, str):
            raw[key] = self.expr_converter.mark_java_expression(value)

    # Determine deletion mode and map path field
    is_folder_file = raw.get('FOLDER_FILE', False)
    is_directory = raw.get('FOLDER', False)

    if is_folder_file:
        path = raw.get('FOLDER_FILE_PATH', raw.get('FILENAME', ''))
        config['is_folder_file'] = True
        config['is_directory'] = False
    elif is_directory:
        path = raw.get('DIRECTORY', raw.get('FILENAME', ''))
        config['is_directory'] = True
        config['is_folder_file'] = False
    else:
        path = raw.get('FILENAME', '')
        config['is_directory'] = False
        config['is_folder_file'] = False

    config['path'] = path
    config['fail_on_error'] = raw.get('FAIL_ON_ERROR', False)  # Talend default is false
    # Note: recursive is NOT a Talend feature. Default to False.
    config['recursive'] = False

    component['config'] = config
    return component
```

**Registration in converter.py** (replace line 285):
```python
elif component_type == 'tFileDelete':
    component = self.component_parser.parse_tfiledelete(node, component)
```

**Key improvements over current `parse_base_component()` approach**:
1. Maps ALL Talend parameters to engine-expected config keys
2. Implements path field selection logic (FILENAME vs DIRECTORY vs FOLDER_FILE_PATH)
3. Uses correct Talend default for `FAIL_ON_ERROR` (false, not True)
4. Explicitly sets `recursive=False` (not a Talend feature)
5. Handles context variables and Java expressions in path fields
6. Follows the standard requiring dedicated `parse_*` methods

---

## Appendix L: Detailed `_process()` Control Flow

```
_process(input_data)
    |
    +-- Extract config: path, fail_on_error, is_directory, is_folder_file, recursive
    |
    +-- if not path: raise ValueError
    |
    +-- try:
    |   |
    |   +-- rows_processed = 1
    |   |
    |   +-- if is_folder_file:
    |   |   +-- if os.path.isfile(path): os.remove(path) -> deleted=True
    |   |   +-- elif os.path.isdir(path):
    |   |   |   +-- if recursive: shutil.rmtree(path)
    |   |   |   +-- else: os.rmdir(path)
    |   |   |   +-- deleted=True
    |   |   +-- else: warn "does not exist" -> deleted=False
    |   |
    |   +-- elif is_directory:
    |   |   +-- if os.path.isdir(path):
    |   |   |   +-- if recursive: shutil.rmtree(path)
    |   |   |   +-- else: os.rmdir(path)
    |   |   |   +-- deleted=True
    |   |   +-- else: warn "does not exist" -> deleted=False
    |   |
    |   +-- else (file mode):
    |   |   +-- if os.path.isfile(path): os.remove(path) -> deleted=True
    |   |   +-- else: warn "does not exist" -> deleted=False
    |   |
    |   +-- _update_stats(rows_processed, 1 if deleted else 0, 0 if deleted else 1)
    |   +-- Log completion with stats
    |
    +-- except Exception as e:
    |   +-- Log error
    |   +-- status_message = f"Error: {e}"
    |   +-- _update_stats(rows_processed, 0, 1)
    |   +-- if fail_on_error: raise
    |
    +-- return {'main': None, 'status': status_message}
```

**Key observations**:
1. The `try` block covers ALL three deletion modes. Any OS error (permission, non-empty dir, etc.) is caught.
2. File non-existence is NOT treated as an error -- it's handled by the `else` branches before the `except`.
3. `_update_stats()` is called in both success and error paths, ensuring stats are always set.
4. The `except Exception` on line 135 catches everything including non-OS errors.
5. `rows_processed` is always 1, even when the file does not exist.

---

## Appendix M: Base Component `_update_global_map()` Detailed Analysis

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

**Bug analysis** (BUG-FDL-001):
- The for loop variable is `stat_value` (line 301), but the log statement references `value` (line 304)
- `stat_name` on line 304 references the loop variable from line 301, which will have the value from the LAST iteration of the for loop (i.e., `EXECUTION_TIME` since that is the last key in the `stats` dict)
- `value` is completely undefined in this scope, causing `NameError`
- This method is called from `execute()` (line 218) after EVERY component execution
- Since `self.global_map` is set by the engine during component instantiation, this bug will crash ANY component that runs in a job with a global map configured

**Call chain**:
1. `ETLEngine._execute_component()` calls `component.execute(input_data)`
2. `BaseComponent.execute()` calls `self._update_global_map()` on line 218 (success path) or line 231 (error path)
3. `_update_global_map()` crashes with `NameError: name 'value' is not defined`

**Severity**: This is the highest-severity bug in the v1 engine. It prevents ANY component from completing execution when a global map is present. The fix is trivial (see Appendix H) but the impact is cross-cutting.

---

## Appendix N: `GlobalMap.get()` Detailed Analysis

The `GlobalMap.get()` method in `global_map.py` (lines 26-28) has a complementary bug:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # BUG: 'default' not in signature
```

**Bug analysis** (BUG-FDL-002):
- `default` is referenced in the body (line 28) but is not a parameter in the method signature (line 26)
- The method signature only accepts `key: str`
- Any call to `global_map.get("some_key")` will crash with `NameError: name 'default' is not defined`

**Cascading impact**:
- `get_component_stat()` (line 51-58) calls `self.get(key, default)` with TWO arguments, but `get()` only accepts ONE positional argument. This would cause `TypeError: GlobalMap.get() takes 2 positional arguments but 3 were given`
- `get_nb_line()`, `get_nb_line_ok()`, `get_nb_line_reject()` all call `get_component_stat()` which calls `get()` with two args

**Fix**: Add `default: Any = None` to the `get()` method signature. This fixes both the `NameError` (direct calls) and the `TypeError` (two-argument calls from `get_component_stat()`).

---

## Appendix O: Detailed `_process()` Code Review Line-by-Line

### Lines 48-63: Method Signature and Docstring

```python
def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
```

The method signature accepts `input_data` but never uses it. This is correct for a standalone utility component -- the parameter is required by the abstract base class contract but is ignored. The docstring accurately describes the config keys, return format, and exceptions, except:
- Claims `FileOperationError` is raised, but the code actually re-raises original OS exceptions (see DBG-FDL-001)
- Does not mention that `_validate_config()` is never called

### Lines 64-69: Config Extraction

```python
path = self.config.get('path', '')
fail_on_error = self.config.get('fail_on_error', True)
is_directory = self.config.get('is_directory', False)
is_folder_file = self.config.get('is_folder_file', False)
recursive = self.config.get('recursive', False)
```

**Issues identified**:
1. `path` defaults to `''` (empty string). If the converter stores the path under `FILENAME` (Talend key name), `path` will be empty string, caught by the `if not path:` check on line 77.
2. `fail_on_error` defaults to `True`. Talend defaults to `false`. See ENG-FDL-004.
3. `recursive` defaults to `False`. Correct, since recursive deletion is not a Talend feature.
4. All five config reads use `.get()` with defaults, so missing keys never raise `KeyError`. Defensive but masks converter bugs.

### Lines 71-80: Logging and Path Validation

```python
logger.info(f"[{self.id}] Delete operation started: {path}")

status_message = ""
deleted = False
rows_processed = 0

if not path:
    error_msg = "Missing required config: 'path'"
    logger.error(f"[{self.id}] {error_msg}")
    raise ValueError(f"[{self.id}] {error_msg}")
```

**Issues identified**:
1. The path is logged at INFO level BEFORE validation. If path is empty string (converter bug), the log shows `"Delete operation started: "` with empty path -- not very informative.
2. `ValueError` is raised for missing path. Should arguably be `ConfigurationError` from the custom exception hierarchy.
3. `status_message` initialized to empty string. If an exception occurs before any branch sets it, the return `{'status': ''}` gives no information.
4. `rows_processed = 0` is correct initial value. Reset to 1 on line 83.

### Lines 82-133: Main Deletion Logic

The main try block sets `rows_processed = 1` unconditionally (line 83), then branches into three modes:

**is_folder_file mode (lines 86-102)**: Checks `os.path.isfile()` first, then `os.path.isdir()`. If neither matches, warns and sets failure status. This correctly handles:
- Regular files
- Directories (empty or non-empty depending on `recursive`)
- Non-existent paths (warning only, no exception)

**is_directory mode (lines 103-115)**: Checks only `os.path.isdir()`. If path is a file, incorrectly reports "Directory does not exist" (ENG-FDL-007).

**File mode (lines 116-125)**: Checks only `os.path.isfile()`. If path is a directory, incorrectly reports "File does not exist" (ENG-FDL-007).

**Statistics update (lines 128-133)**: `_update_stats(1, 1 if deleted else 0, 0 if deleted else 1)`. After stats update, logs completion with all three stat values.

### Lines 135-140: Exception Handler

```python
except Exception as e:
    logger.error(f"[{self.id}] Error deleting {path}: {e}")
    status_message = f"Error: {e}"
    self._update_stats(rows_processed, 0, 1)
    if fail_on_error:
        raise
```

**Issues identified**:
1. `except Exception` is too broad -- catches `TypeError`, `AttributeError`, `MemoryError`, etc. Should catch `OSError` specifically. See BUG-FDL-006.
2. Uses bare `raise` (line 140) which preserves the original traceback. This is correct for debugging but the docstring says `FileOperationError` is raised.
3. When `fail_on_error=False`, the error is completely suppressed. The error message is stored in `status_message` but not in globalMap `{id}_ERROR_MESSAGE`.
4. `_update_stats(rows_processed, 0, 1)` may double-count if `_update_stats()` was already called in the success path. However, since the exception interrupts the success path before `_update_stats()` on line 130, this is not actually a problem -- only one call reaches.

### Line 142: Return Statement

```python
return {'main': None, 'status': status_message}
```

Returns a dict with `main=None` (no data flow output) and `status` containing the status message string. The base class `execute()` method adds `result['stats']` on line 223, so the full return is `{'main': None, 'status': '...', 'stats': {...}}`.

### Lines 144-176: `_validate_config()` (Dead Code)

The validation method checks:
- `path` presence (line 154) and type (line 156)
- `fail_on_error` type (lines 160-161)
- `is_directory` type (lines 163-164)
- `is_folder_file` type (lines 167-168)
- `recursive` type (lines 172-173)

**Not validated (should be)**:
- `path` is non-empty string (line 156 only checks `isinstance(str)`, not emptiness)
- `path` is absolute path (Talend requires absolute paths)
- `is_directory` and `is_folder_file` not both True
- `recursive=True` only with `is_directory=True`

**Status**: DEAD CODE. Never called by any code path. See BUG-FDL-005.

---

## Appendix P: Comparison of Talend `java.io.File.delete()` vs Python File Operations

Understanding the behavioral differences between Java and Python file operations is critical for ensuring fidelity:

### File Deletion

| Behavior | Java `File.delete()` | Python `os.remove()` |
|----------|----------------------|---------------------|
| Delete regular file | Returns `true` | Returns `None` (success) |
| Delete non-existent file | Returns `false` | Raises `FileNotFoundError` |
| Delete directory (empty) | Returns `true` | Raises `IsADirectoryError` |
| Delete directory (non-empty) | Returns `false` | Raises `IsADirectoryError` |
| Delete symlink to file | Deletes symlink | Deletes symlink |
| Delete symlink to directory | Deletes symlink | Raises `IsADirectoryError` |
| Permission denied | Returns `false` | Raises `PermissionError` |
| Path is null/None | Throws `NullPointerException` | Raises `TypeError` |

**Key difference**: Java's `File.delete()` returns a boolean (success/failure). Python's `os.remove()` either succeeds or raises an exception. The v1 engine handles this by checking `os.path.isfile()`/`os.path.isdir()` BEFORE attempting deletion, which avoids exceptions for non-existent files but introduces TOCTOU race conditions.

### Directory Deletion

| Behavior | Java `File.delete()` | Python `os.rmdir()` | Python `shutil.rmtree()` |
|----------|----------------------|---------------------|--------------------------|
| Delete empty dir | Returns `true` | Returns `None` | Returns `None` |
| Delete non-empty dir | Returns `false` | Raises `OSError` | Recursively deletes all contents |
| Delete symlink to dir | Deletes symlink | Raises `NotADirectoryError` | **Follows symlink** (Python < 3.12) or deletes symlink (Python >= 3.12) |

**Critical**: `shutil.rmtree()` has fundamentally different behavior from Java's `File.delete()`. In Talend, `tFileDelete` with `FOLDER=true` on a non-empty directory simply fails silently (returns false). In v1 with `recursive=True`, it aggressively deletes the entire tree. This behavioral difference is a security concern.

### TOCTOU Race Condition in v1 Engine

The v1 engine's approach of check-then-act introduces a Time-of-Check-to-Time-of-Use (TOCTOU) race condition:

```python
# Time of Check (line 118)
if os.path.isfile(path):     # File exists at this moment
    # Time of Use (line 119)
    os.remove(path)           # File may have been deleted by another process
```

In contrast, Java's `File.delete()` is atomic at the OS level -- it either deletes or returns false, without a separate check step. The v1 engine's approach is standard in Python but less robust under concurrent access.

**Mitigation**: The `except Exception` handler catches `FileNotFoundError` from the race condition. When `fail_on_error=False`, the error is silently suppressed. When `fail_on_error=True`, the `FileNotFoundError` propagates, which is appropriate.

---

## Appendix Q: Engine `execute()` Lifecycle for FileDelete

The full execution lifecycle for a `FileDelete` component call is:

```
1. ETLEngine._execute_component(component, input_data=None)
   |
2. component.execute(input_data=None)
   |
   +-- 2a. self.status = ComponentStatus.RUNNING
   +-- 2b. start_time = time.time()
   |
   +-- 2c. if self.java_bridge:
   |       self._resolve_java_expressions()
   |       [Scans config for {{java}} markers, resolves via Java bridge]
   |
   +-- 2d. if self.context_manager:
   |       self.config = self.context_manager.resolve_dict(self.config)
   |       [Resolves ${context.var} placeholders in all config string values]
   |
   +-- 2e. Determine execution mode:
   |       HYBRID -> _auto_select_mode(None) -> BATCH (since input_data is None)
   |
   +-- 2f. _execute_batch(None) -> _process(None)
   |       |
   |       +-- Extract config keys (path, fail_on_error, etc.)
   |       +-- Validate path non-empty
   |       +-- Perform deletion based on mode
   |       +-- Update stats
   |       +-- Return {'main': None, 'status': '...'}
   |
   +-- 2g. self.stats['EXECUTION_TIME'] = time.time() - start_time
   +-- 2h. self._update_global_map()   <-- CRASHES here (BUG-FDL-001)
   |       [Would propagate NB_LINE, NB_LINE_OK, NB_LINE_REJECT to globalMap]
   |
   +-- 2i. self.status = ComponentStatus.SUCCESS
   +-- 2j. result['stats'] = self.stats.copy()
   +-- 2k. return result
```

**Critical path**:
- Step 2c: Java expressions are resolved BEFORE context variables (step 2d). This is correct -- Java expressions may contain context references that the Java bridge resolves.
- Step 2d: Context variables are resolved in-place, modifying `self.config`. This means the original config is lost after execution.
- Step 2h: `_update_global_map()` crashes with `NameError` due to BUG-FDL-001. The component appears to fail even though the deletion succeeded.

**Error path** (if exception in `_process()`):
```
2f. _process(None) raises Exception
    |
2g'. self.status = ComponentStatus.ERROR
2h'. self.error_message = str(e)
2i'. self.stats['EXECUTION_TIME'] = time.time() - start_time
2j'. self._update_global_map()   <-- Also crashes here (BUG-FDL-001)
2k'. logger.error(f"Component {self.id} execution failed: {e}")
2l'. raise  (re-raise original exception)
```

Both success and error paths crash at `_update_global_map()`. The deletion itself may succeed, but the engine reports failure due to the base class bug.

---

## Appendix R: Detailed Test Case Specifications

### Test Case 1: Delete Existing File (P0)

```python
def test_delete_existing_file():
    """Verify basic file deletion works correctly."""
    import tempfile
    import os

    # Setup
    fd, path = tempfile.mkstemp()
    os.close(fd)
    assert os.path.exists(path)

    # Execute
    component = FileDelete(
        component_id="tFileDelete_1",
        config={'path': path, 'fail_on_error': True}
    )
    result = component._process(None)

    # Verify
    assert not os.path.exists(path), "File should be deleted"
    assert result['main'] is None
    assert result['status'] == "File (or path) deleted."
    assert component.stats['NB_LINE'] == 1
    assert component.stats['NB_LINE_OK'] == 1
    assert component.stats['NB_LINE_REJECT'] == 0
```

### Test Case 3: Delete Non-existent File + fail_on_error=False (P0)

```python
def test_delete_nonexistent_file_no_fail():
    """Verify graceful handling of missing file with fail_on_error=False."""
    component = FileDelete(
        component_id="tFileDelete_1",
        config={'path': '/tmp/nonexistent_file_12345.txt', 'fail_on_error': False}
    )
    result = component._process(None)

    # Verify
    assert result['main'] is None
    assert "does not exist" in result['status']
    assert component.stats['NB_LINE'] == 1
    assert component.stats['NB_LINE_OK'] == 0
    assert component.stats['NB_LINE_REJECT'] == 1
```

### Test Case 7: Converter Key Mapping Failure (P0)

```python
def test_converter_key_mismatch():
    """Demonstrate the converter key mismatch bug."""
    # Simulate converter output (Talend key names)
    talend_config = {
        'FILENAME': '/tmp/test_file.txt',
        'FAIL_ON_ERROR': False,
        'FOLDER': False,
        'FOLDER_FILE': False
    }

    component = FileDelete(
        component_id="tFileDelete_1",
        config=talend_config
    )

    # Verify the bug: engine reads 'path' but config has 'FILENAME'
    path = component.config.get('path', '')
    assert path == '', "Engine cannot find 'path' key -- converter bug confirmed"

    # Verify the component raises ValueError for empty path
    with pytest.raises(ValueError, match="Missing required config: 'path'"):
        component._process(None)
```

### Test Case 8: Delete Non-empty Directory + recursive=True (P1)

```python
def test_delete_nonempty_dir_recursive():
    """Verify recursive directory deletion."""
    import tempfile
    import os

    # Setup: create directory with files
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
        f.write("content1")
    subdir = os.path.join(tmpdir, "subdir")
    os.makedirs(subdir)
    with open(os.path.join(subdir, "file2.txt"), "w") as f:
        f.write("content2")

    # Execute
    component = FileDelete(
        component_id="tFileDelete_1",
        config={
            'path': tmpdir,
            'is_directory': True,
            'recursive': True,
            'fail_on_error': True
        }
    )
    result = component._process(None)

    # Verify
    assert not os.path.exists(tmpdir), "Directory tree should be deleted"
    assert result['status'] == "File (or path) deleted."
    assert component.stats['NB_LINE_OK'] == 1
```

### Test Case 9: Delete Non-empty Directory + recursive=False (P1)

```python
def test_delete_nonempty_dir_no_recursive_fail():
    """Verify non-empty dir fails with recursive=False and fail_on_error=True."""
    import tempfile
    import os

    # Setup: create non-empty directory
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
        f.write("content")

    # Execute
    component = FileDelete(
        component_id="tFileDelete_1",
        config={
            'path': tmpdir,
            'is_directory': True,
            'recursive': False,
            'fail_on_error': True
        }
    )

    with pytest.raises(OSError):
        component._process(None)

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir)
```

---

## Appendix S: Source References

- [tFileDelete Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfiledelete/tfiledelete-standard-properties) -- Official Talend documentation for Basic and Advanced Settings, connection types, and global variables.
- [tFileDelete Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfiledelete/tfiledelete-standard-properties) -- Talend 8.0 documentation with detailed property descriptions.
- [tFileDelete - Talend Skill (ESB 7.x)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfiledelete-talend-open-studio-for-esb-document-7-x/) -- Community documentation with connection types, global variables, and usage patterns.
- [tFileDelete Component (Talend 7.2)](https://help.qlik.com/talend/en-US/components/7.2/tfiledelete/tfiledelete-component) -- Component overview, family, and purpose.
- [Deleting files (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfiledelete/tfiledelete-tfilelist-tjava-tjava-deleting-files-standard-component) -- Usage scenario: tFileList + tFileDelete + tJava for iterative file deletion.
- [tFileDelete Scenario - Deleting files (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfiledelete/tfiledelete-tfilelist-tjava-tjava-deleting-files-standard-component) -- Usage scenario with tFileList iteration pattern.
- [Error handling with connections (Talend 8.0)](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-09/error-handling-with-connections) -- Trigger connection types: SUBJOB_OK, SUBJOB_ERROR, COMPONENT_OK, COMPONENT_ERROR, RUN_IF.
- [Trigger connections for a Job (Talend 8.0)](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-06/trigger-connections-for-job) -- Detailed trigger connection behavior and usage patterns.
- [Component tFileDelete cannot delete file created by... (Qlik Community)](https://community.qlik.com/t5/Design-and-Development/Component-tFileDelete-cannot-delete-file-created-by/td-p/2257779) -- Community discussion on file lock issues with tFileDelete.
- [How to Append File Using tFileList, tFileDelete and tJava (Desired Data Blog)](https://desireddata.blogspot.com/2015/05/how-to-append-file-using.html) -- Practical tFileDelete usage pattern with tFileList iteration and FAIL_ON_ERROR=false for cleanup.

---

## Appendix T: Talend Generated Java Code for tFileDelete

For reference, Talend generates the following Java code pattern for `tFileDelete` (Standard mode, file deletion):

```java
// tFileDelete_1 - generated code pattern
class_tFileDelete_1 = new class_tFileDelete_1();
java.io.File file_tFileDelete_1 = new java.io.File(
    // FILENAME expression resolved here
    context.output_dir + "/temp_output.csv"
);

if (file_tFileDelete_1.exists()) {
    if (file_tFileDelete_1.isFile()) {
        if (!file_tFileDelete_1.delete()) {
            // FAIL_ON_ERROR handling
            throw new RuntimeException("Could not delete file: "
                + file_tFileDelete_1.getAbsolutePath());
        }
    }
}

// Set global variables
globalMap.put("tFileDelete_1_DELETE_PATH",
    file_tFileDelete_1.getAbsolutePath());
globalMap.put("tFileDelete_1_CURRENT_STATUS", "success");
```

For directory deletion mode (FOLDER=true):

```java
java.io.File dir_tFileDelete_1 = new java.io.File(
    context.temp_dir
);

if (dir_tFileDelete_1.exists()) {
    if (dir_tFileDelete_1.isDirectory()) {
        // NOTE: File.delete() only deletes EMPTY directories
        if (!dir_tFileDelete_1.delete()) {
            // Directory not empty or permission denied
            if (failOnError) {
                throw new RuntimeException("Could not delete directory: "
                    + dir_tFileDelete_1.getAbsolutePath());
            }
        }
    }
}

globalMap.put("tFileDelete_1_DELETE_PATH",
    dir_tFileDelete_1.getAbsolutePath());
```

**Key observations from generated code**:
1. `java.io.File.delete()` returns a boolean -- no exception on failure
2. `exists()` is checked BEFORE `delete()` -- same TOCTOU pattern as v1 engine
3. GlobalMap variables (`DELETE_PATH`, `CURRENT_STATUS`) are ALWAYS set, even if deletion fails
4. For directories, `File.delete()` only works on EMPTY directories -- no recursive option
5. The `FAIL_ON_ERROR` flag controls whether `RuntimeException` is thrown on failure

---

## Appendix U: Component Status Lifecycle

The `ComponentStatus` enum in `base_component.py` defines five states:

```
PENDING -> RUNNING -> SUCCESS
                   -> ERROR
         -> SKIPPED (not used by FileDelete)
```

For `FileDelete`, the status transitions are:

| Scenario | Status Flow | Final Status |
|----------|------------|--------------|
| Successful deletion | PENDING -> RUNNING -> SUCCESS | SUCCESS |
| Missing file, fail_on_error=False | PENDING -> RUNNING -> SUCCESS | SUCCESS (!) |
| Missing file, fail_on_error=True | PENDING -> RUNNING -> SUCCESS | SUCCESS (!) |
| OS error, fail_on_error=False | PENDING -> RUNNING -> SUCCESS | SUCCESS (!) |
| OS error, fail_on_error=True | PENDING -> RUNNING -> ERROR | ERROR |
| Missing path config | PENDING -> RUNNING -> ERROR | ERROR |
| _update_global_map() crash | PENDING -> RUNNING -> ERROR | ERROR |

**Critical finding**: When a file does not exist and `fail_on_error=True`, the status is still `SUCCESS` because the non-existence case is handled by the `else` branches (lines 100-102, 113-115, 123-125) which do NOT raise exceptions. The `ComponentStatus` only becomes `ERROR` when an actual exception propagates to the `execute()` method's outer try/except.

This means:
- `component.get_status() == ComponentStatus.SUCCESS` even when the intended deletion target does not exist
- Only actual OS errors (permission denied, I/O error) with `fail_on_error=True` produce `ERROR` status
- This is arguably a bug: if `fail_on_error=True` and the file does not exist, the user expects an error

---

## Appendix V: Comparison with tFileCopy Converter Parser

The `tFileCopy` component has a dedicated parser (`parse_tfilecopy()`) in `component_parser.py`. This demonstrates the pattern that `tFileDelete` should follow:

```python
# converter.py line 286-287
elif component_type == 'tFileCopy':
    component = self.component_parser.parse_tfilecopy(node, component)
```

In contrast, `tFileDelete` falls through to the generic path:

```python
# converter.py line 284-285
elif component_type == 'tFileDelete':
    component = self.component_parser.parse_base_component(node)
```

The fact that `tFileCopy` has a dedicated parser but `tFileDelete` does not suggests that `tFileDelete` was added later or was considered lower priority during converter development. All other file utility components in the same code block (`tFileArchive`, `tFileUnarchive`, `tFileCopy`, `tFileTouch`, `tFileExist`, `tFileProperties`, `tFileRowCount`) have dedicated parsers. `tFileDelete` is the ONLY file utility component using the generic `parse_base_component()` fallback.
