# Audit Report: tFileCopy / FileCopy

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
| **Talend Name** | `tFileCopy` |
| **V1 Engine Class** | `FileCopy` |
| **Engine File** | `src/v1/engine/components/file/file_copy.py` (132 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_copy.py` |
| **Converter Dispatch** | `talend_to_v1` registry-based dispatch via `REGISTRY["tFileCopy"]` |
| **Registry Aliases** | `FileCopy`, `tFileCopy` (registered in `src/v1/engine/engine.py` lines 76-77) |
| **Category** | File / Utility |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_copy.py` | Engine implementation (132 lines) |
| `src/converters/talend_to_v1/components/file/file_copy.py` | Dedicated `talend_to_v1` converter for tFileCopy |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 3: `from .file_copy import FileCopy`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | `talend_to_v1` dedicated parser extracts 12 params (12 config keys). All runtime params mapped. REPLACE_FILE default corrected to false. CREATE_DIRECTORY default corrected to false. No DIE_ON_ERROR on tFileCopy. |
| Engine Feature Parity | **Y** | 0 | 4 | 3 | 1 | No `remove_source_file` (move semantics); no `copy_directory` toggle; missing globalMap vars; no `die_on_error` support; `shutil.copy2` always preserves metadata (conflicts with `preserve_last_modified` logic) |
| Code Quality | **Y** | 2 | 2 | 3 | 2 | Cross-cutting base class bugs; no `_validate_config()`; exception swallowing in catch-all; no custom exception types used; `replace_file` default differs from Talend |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | Simple file operation; minor concern with `copytree` on large directories without progress feedback |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; converter crash blocks all usage**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileCopy Does

`tFileCopy` copies a single file or an entire directory (with subdirectories) from a source location to a destination location. It can optionally rename the copied file, replace existing files, create the destination directory if it does not exist, remove the source file after copying (move semantics), and preserve the last modified timestamp. The component is typically used with `tFileList` to process multiple files in batch. It is a standalone utility component that does not process data rows -- it performs filesystem operations and reports success/failure.

**Source**: [tFileCopy Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfilecopy/tfilecopy-standard-properties), [tFileCopy Component (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfilecopy/tfilecopy-component), [tFileCopy Moving/Copying/Renaming in Batch](https://help.qlik.com/talend/en-US/components/8.0/tfilecopy/tfilecopy-tfilelist-moving-copying-renaming-files-in-batch-standard-component)

**Component family**: File (Utility)
**Available in**: All Talend products (Standard).
**Required JARs**: None (uses Java standard library `java.io.File`, `java.nio.file.Files`)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | File Name | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute path to the source file to be copied. Supports context variables, globalMap references, Java expressions. Hidden when `Copy a directory` is selected. |
| 2 | Copy a directory | `COPY_DIRECTORY` | Boolean (CHECK) | `false` | When selected, copies the entire source directory including all subdirectories and files. `File Name` field is hidden; `Source directory` field appears instead. |
| 3 | Source directory | `SOURCE_DIRECTORY` | Expression (String) | -- | Path to the source directory to copy. Only visible when `COPY_DIRECTORY=true`. |
| 4 | Destination directory | `DESTINATION` | Expression (String) | -- | **Mandatory**. Path to the destination directory where the file or directory will be copied. |
| 5 | Rename | `RENAME` | Boolean (CHECK) | `false` | When selected, enables renaming of the copied file. The `Destination filename` field appears. |
| 6 | Destination filename | `DESTINATION_RENAME` | Expression (String) | -- | New name for the copied file. Only visible when `RENAME=true`. |
| 7 | Remove source file | `REMOVE_SOURCE_FILE` | Boolean (CHECK) | `false` | When selected, the source file is deleted after a successful copy, effectively implementing **move** semantics. |
| 8 | Replace existing file | `REPLACE_FILE` | Boolean (CHECK) | `false` | When selected, overwrites an existing file at the destination. **Note**: Talend default is `false` (do NOT overwrite). |
| 9 | Create the directory if it doesn't exist | `CREATE_DIRECTORY` | Boolean (CHECK) | `false` | When selected, auto-creates the destination directory (and any parent directories) if it does not already exist. **Note**: Talend default is `false`. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 10 | Preserve last modified time | `PRESERVE_LAST_MODIFIED_TIME` | Boolean (CHECK) | `false` | When selected, uses the last modified time of the source file as that of the destination file. Without this, the destination file gets the current timestamp. |
| 11 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 12 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Data flow passthrough. Passes incoming data to downstream components. |
| `REJECT` | Output | Row > Reject | Reject data output. |
| `ITERATE` | Input | Iterate | Enables iterative processing when used with `tFileList` for batch file operations. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_DESTINATION_FILENAME` | String | After execution | The destination file name (just the filename, not the full path). |
| `{id}_DESTINATION_FILEPATH` | String | After execution | The full destination file path. |
| `{id}_SOURCE_DIRECTORY` | String | After execution | The source directory path. |
| `{id}_DESTINATION_DIRECTORY` | String | After execution | The destination directory path. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message when the component fails. Available when `Die on error` is unchecked. |

### 3.5 Behavioral Notes

1. **Move semantics**: When `REMOVE_SOURCE_FILE=true`, tFileCopy first copies the file to the destination, then deletes the source. This is a copy-then-delete pattern, NOT a rename/move operation. If the deletion fails after a successful copy, the file exists in both locations. This is a critical distinction from `Files.move()`.

2. **Batch operation with tFileList**: The most common usage pattern is `tFileList -> tFileCopy` connected via an Iterate link. `tFileList` iterates files, and `tFileCopy` references `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))` in its `FILENAME` field. This is the standard pattern for processing multiple files.

3. **Copy a directory**: When `COPY_DIRECTORY=true`, the component copies the entire directory tree recursively. The `File Name` and `Remove source file` fields are hidden. The rename feature is also unavailable in directory mode.

4. **Replace existing file = false (default)**: If the destination file already exists and this is unchecked, the component fails with an error. This is important because the Talend default is `false`, meaning the component will NOT overwrite by default. Many Talend jobs explicitly set this to `true`.

5. **Standalone utility**: Unlike data flow components, `tFileCopy` does not produce or transform DataFrames. It performs filesystem operations. The component has no schema -- it operates purely on file paths. Its outputs are triggers and globalMap variables, not data rows.

6. **No NB_LINE variable**: Unlike data-processing components, `tFileCopy` does not produce a standard `{id}_NB_LINE` count. Its success is communicated via the `COMPONENT_OK`/`COMPONENT_ERROR` triggers and the `{id}_ERROR_MESSAGE` globalMap variable.

7. **Preserve last modified time**: When this is unchecked (default), `shutil.copy()` (or Java's `Files.copy()`) does NOT preserve timestamps. When checked, the source file's modification time is explicitly set on the destination. In Java, this uses `File.setLastModified()`. In Python, `shutil.copystat()` preserves permissions AND timestamps.

8. **Die on error**: While not explicitly listed as a separate parameter in Talend's tFileCopy UI, the component follows the standard Talend error handling pattern. When the component encounters an error (file not found, permissions, disk full), it raises an exception which either terminates the subjob (default) or can be caught by a `COMPONENT_ERROR` trigger.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated parser (`src/converters/talend_to_v1/components/file/file_copy.py`) registered via `REGISTRY["tFileCopy"]`. The parser extracts all runtime parameters using safe `_get_str` / `_get_bool` helpers with null-safety and correct defaults.

**Converter flow**:
1. `talend_to_v1` registry dispatches to `file_copy.py` converter function
2. Extracts all runtime parameters using `_get_str()` and `_get_bool()` helpers (null-safe)
3. Maps to engine config keys (`source`, `destination`, `rename`, `new_name`, etc.)
4. Corrected defaults: `replace_file=false`, `create_directory=false`

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `source` | Source file path. |
| 2 | `DESTINATION` | Yes | `destination` | Destination directory path. |
| 3 | `RENAME` | Yes | `rename` | Boolean. |
| 4 | `DESTINATION_RENAME` | Yes | `new_name` | New filename for renamed copy. |
| 5 | `REPLACE_FILE` | Yes | `replace_file` | Default `false` -- matches Talend. |
| 6 | `CREATE_DIRECTORY` | Yes | `create_directory` | Default `false` -- matches Talend. |
| 7 | `PRESERVE_LAST_MODIFIED_TIME` | Yes | `preserve_last_modified` | Default `false` -- matches Talend. |
| 8 | `REMOVE_SOURCE_FILE` | Yes | `remove_source_file` | Move semantics. Engine-gap warning: not yet implemented in engine. |
| 9 | `COPY_DIRECTORY` | Yes | `copy_directory` | Directory copy toggle. Engine-gap warning: engine auto-detects via `os.path.isdir()`. |
| 10 | `SOURCE_DIRECTORY` | Yes | `source_directory` | Source directory for directory copy mode. |
| 11 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Not needed at runtime. |
| 12 | `LABEL` | Yes | `label` | Not needed at runtime (cosmetic). |

**Summary**: 12 of 12 parameters extracted (100%). All runtime-relevant parameters correctly mapped.

> **Factual correction (2026-03-25)**: The original audit referenced a `DIE_ON_ERROR` parameter on tFileCopy. This parameter does not exist on tFileCopy (verified via Talend documentation and XML parsing). It has been removed from the converter.

### 4.3 Default Value Mismatches

| Parameter | Talend Default | Converter Default | Engine Default | Impact |
|-----------|---------------|-------------------|----------------|--------|
| `REPLACE_FILE` | `false` | `True` (line 282) | `True` (line 71) | **High**: Files will be silently overwritten when Talend would refuse. Data loss risk. |
| `CREATE_DIRECTORY` | `false` | `True` (line 283) | `True` (line 72) | **Medium**: Directories will be auto-created when Talend would fail. Masks configuration errors. |

These defaults are inverted from Talend's behavior. In Talend, both `REPLACE_FILE` and `CREATE_DIRECTORY` default to `false`, meaning the component is conservative by default -- it will not overwrite existing files and will not create directories. The v1 implementation defaults both to `True`, making it permissive by default. This behavioral difference can cause silent data corruption (overwriting files that should not be overwritten) or mask errors (creating directories that should already exist).

### 4.4 Schema Extraction

Not applicable. `tFileCopy` is a utility component that does not have input or output schemas. It does not process data rows. The converter's generic schema extraction in `parse_base_component()` would produce empty schema lists, which is correct.

### 4.5 Expression Handling

The generic `parse_base_component()` parameter extraction (lines 433-469) handles:
- **Context variables**: `context.var` references detected and wrapped as `${context.var}` for ContextManager resolution.
- **Java expressions**: Values containing Java operators/methods are marked with `{{java}}` prefix for runtime resolution.

This applies to the `FILENAME` and `DESTINATION` fields, which commonly contain context variables (e.g., `context.sourceDir + "/" + context.fileName`) or globalMap references (e.g., `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`).

**Known limitation**: The `FILENAME` field in tFileCopy used with tFileList almost always contains `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))` -- a Java cast expression. The `detect_java_expression()` heuristic should flag this as a Java expression (due to the cast and method call), but the `globalMap.get()` call requires the Java bridge or globalMap to be available at runtime.

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FCP-001 | ~~P0~~ | **FIXED (2026-03-25)**: `talend_to_v1` dedicated parser replaces missing `parse_tfilecopy()`. All params extracted via registry-based dispatch. |
| CONV-FCP-002 | ~~P1~~ | **FIXED (2026-03-25)**: `REMOVE_SOURCE_FILE` now extracted as `remove_source_file`. Engine-gap: move semantics not yet implemented in engine. |
| CONV-FCP-003 | ~~P1~~ | **FIXED (2026-03-25)**: `COPY_DIRECTORY` now extracted as `copy_directory`. Engine-gap: engine auto-detects via `os.path.isdir()`. |
| CONV-FCP-004 | ~~P2~~ | **FIXED (2026-03-25)**: `REPLACE_FILE` default corrected to `false`, matching Talend. |
| CONV-FCP-005 | ~~P2~~ | **FIXED (2026-03-25)**: `CREATE_DIRECTORY` default corrected to `false`, matching Talend. |
| CONV-FCP-006 | ~~P2~~ | **FIXED (2026-03-25)**: `SOURCE_DIRECTORY` now extracted as `source_directory`. |
| CONV-FCP-007 | ~~P3~~ | **FIXED (2026-03-25)**: Dedicated `talend_to_v1` parser replaces deprecated `_map_component_parameters()` approach. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Copy single file | **Yes** | High | `_process()` line 112-114 | Uses `shutil.copy2()` -- copies file data and metadata |
| 2 | Copy directory (recursive) | **Yes** | Medium | `_process()` line 109-111 | Uses `shutil.copytree()` with `dirs_exist_ok=replace_file`. Auto-detected via `os.path.isdir()`, not via a dedicated toggle. |
| 3 | Create destination directory | **Yes** | Medium | `_process()` line 92-94 | Uses `os.makedirs()`. Default `True` differs from Talend default `false`. |
| 4 | Rename copied file | **Yes** | High | `_process()` line 97-100 | `os.path.join(destination, new_name)` -- correct implementation |
| 5 | Replace existing file | **Yes** | Medium | `_process()` line 103-106 | Raises `FileExistsError` when destination exists and `replace_file=False`. **But**: check is against `final_destination`, which for non-rename copies is the directory, not the file. See BUG-FCP-003. |
| 6 | Preserve last modified time | **Partial** | Low | `_process()` line 117-119 | Uses `shutil.copystat()` AFTER `shutil.copy2()`. But `shutil.copy2()` already preserves metadata (including timestamps). So `copystat()` is redundant for files. For directories, `copytree` does NOT call `copystat` on the top-level directory, so the explicit call is needed. See BUG-FCP-004. |
| 7 | Source file validation | **Yes** | High | `_process()` line 86-89 | `os.path.exists(source)` check with `FileNotFoundError` |
| 8 | Required field validation | **Yes** | High | `_process()` line 81-84 | Checks `source` and `destination` are non-empty |
| 9 | **Remove source file (move)** | **No** | N/A | -- | **Not implemented. No `remove_source_file` config handling. Move semantics completely missing.** |
| 10 | **Copy directory toggle** | **No** | N/A | -- | **No explicit toggle. Auto-detects via `os.path.isdir()`. Behavioral difference when source is a variable that hasn't been resolved yet.** |
| 11 | **Die on error** | **No** | N/A | -- | **No `die_on_error` support. All errors either raise exceptions (caught by catch-all) or are silently stored in result dict. No way to control whether errors are fatal or non-fatal.** |
| 12 | **`{id}_DESTINATION_FILENAME` globalMap** | **No** | N/A | -- | **Not set. Downstream components referencing this variable get null.** |
| 13 | **`{id}_DESTINATION_FILEPATH` globalMap** | **No** | N/A | -- | **Not set. Downstream components referencing this variable get null.** |
| 14 | **`{id}_SOURCE_DIRECTORY` globalMap** | **No** | N/A | -- | **Not set.** |
| 15 | **`{id}_DESTINATION_DIRECTORY` globalMap** | **No** | N/A | -- | **Not set.** |
| 16 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not set on error. Error stored in result dict but not in globalMap.** |
| 17 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 18 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |
| 19 | Statistics tracking | **Yes** | Medium | `_process()` lines 122, 130 | `_update_stats(1, 1, 0)` on success, `_update_stats(1, 0, 1)` on failure. Always treats as 1 operation. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FCP-001 | **P1** | **No `remove_source_file` (move semantics)**: Talend's most common tFileCopy usage is to MOVE files by enabling `REMOVE_SOURCE_FILE`. The v1 engine only copies. Source files are never deleted. Jobs that rely on move semantics will leave duplicate files, potentially causing re-processing in subsequent runs. This is a fundamental gap for ETL patterns like "process and archive" or "move to done folder". |
| ENG-FCP-002 | **P1** | **No `die_on_error` support**: The component has no `die_on_error` config handling. The catch-all `except Exception` on line 128 catches ALL errors, logs them, updates stats to failed, and returns a result dict with `status: 'error'`. Errors never propagate to the caller unless re-raised. In Talend, unchecked errors cause the subjob to fail with `COMPONENT_ERROR` trigger. The current behavior silently swallows errors. |
| ENG-FCP-003 | **P1** | **Missing globalMap variables**: None of the 5 Talend globalMap variables (`DESTINATION_FILENAME`, `DESTINATION_FILEPATH`, `SOURCE_DIRECTORY`, `DESTINATION_DIRECTORY`, `ERROR_MESSAGE`) are set. Downstream components and trigger conditions referencing these variables will get null/None. |
| ENG-FCP-004 | **P1** | **`REPLACE_FILE` default `True` differs from Talend default `false`**: Engine default on line 71 is `True`. Talend default is `false`. This means the v1 engine will silently overwrite existing destination files by default, while Talend would raise an error. This is a data loss risk. |
| ENG-FCP-005 | **P2** | **`shutil.copy2()` always preserves timestamps**: The engine uses `shutil.copy2()` (line 114) which ALWAYS copies file metadata including modification time. The separate `preserve_last_modified` check with `shutil.copystat()` (line 117-119) is redundant for single files. When `preserve_last_modified=False`, the user expects the destination to have the CURRENT timestamp, but `copy2()` preserves the source timestamp regardless. Should use `shutil.copy()` (no metadata) when `preserve_last_modified=False`. |
| ENG-FCP-006 | **P2** | **`CREATE_DIRECTORY` default `True` differs from Talend default `false`**: Engine default on line 72 is `True`. This auto-creates destination directories that Talend would refuse to create, masking configuration errors. |
| ENG-FCP-007 | **P2** | **No `copy_directory` toggle**: The engine auto-detects directory sources via `os.path.isdir()` (line 109). This differs from Talend which uses an explicit `COPY_DIRECTORY` checkbox that changes the UI and parameter semantics. When the source path comes from a context variable or Java expression that hasn't been resolved yet, `os.path.isdir()` will fail or return incorrect results. |
| ENG-FCP-008 | **P3** | **`copytree` `dirs_exist_ok` requires Python 3.8+**: Line 111 uses `shutil.copytree(source, final_destination, dirs_exist_ok=replace_file)`. The `dirs_exist_ok` parameter was added in Python 3.8. While Python 3.8+ is likely the target, this is not documented as a requirement. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | No (utility component) | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Always 1. Semantically incorrect for a utility component that doesn't process data rows. |
| `{id}_NB_LINE_OK` | No (utility component) | **Yes** | Same mechanism | 1 on success, 0 on failure. |
| `{id}_NB_LINE_REJECT` | No (utility component) | **Yes** | Same mechanism | 0 on success, 1 on failure. |
| `{id}_DESTINATION_FILENAME` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_DESTINATION_FILEPATH` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_SOURCE_DIRECTORY` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_DESTINATION_DIRECTORY` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Error stored in result dict but not in globalMap. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FCP-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileCopy, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The catch block in `execute()` (line 227) will catch this NameError, masking the original result and re-raising as a generic error. |
| BUG-FCP-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FCP-003 | **P1** | `src/v1/engine/components/file/file_copy.py:103` | **`replace_file` check targets directory, not file**: When `rename=False`, `final_destination` equals the destination directory path (line 97). The check `os.path.exists(final_destination) and not replace_file` on line 103 checks if the DIRECTORY exists, not if the specific file within it exists. Since the directory is typically created on line 94, this check will always fail (directory exists) even when the specific file does not exist. This means non-rename copies to existing directories will always raise `FileExistsError` when `replace_file=False`, even if the target file doesn't exist. Conversely, when `rename=True`, `final_destination` is the full file path (line 99), and the check works correctly. |
| BUG-FCP-004 | **P1** | `src/v1/engine/components/file/file_copy.py:114,117-119` | **`shutil.copy2` + `shutil.copystat` double-preserves metadata**: `shutil.copy2()` (line 114) already copies data AND metadata (including timestamps). The subsequent `shutil.copystat()` call (line 119) when `preserve_last_modified=True` is redundant for single files. More critically, when `preserve_last_modified=False`, the source timestamp is STILL preserved because `copy2` always does this. The user expects the destination to have the current time when `preserve_last_modified=False`. Should use `shutil.copy()` (data only, no metadata) when `preserve_last_modified=False`, and `shutil.copy2()` only when `preserve_last_modified=True`. |
| BUG-FCP-005 | **P2** | `src/v1/engine/components/file/file_copy.py:128-131` | **Catch-all silently swallows exceptions**: The `except Exception as e` on line 128 catches ALL exceptions (including `ValueError` and `FileNotFoundError` raised on lines 84 and 89), logs the error, updates stats, and stores the error in the result dict. The error is NEVER re-raised. This means `execute()` in the base class (line 220) will see the result as successful (`ComponentStatus.SUCCESS`) because no exception propagated. The caller gets a dict with `status: 'error'` but the component status is `SUCCESS`. This is semantically incorrect and prevents proper error handling via `COMPONENT_ERROR` triggers. |
| BUG-FCP-006 | **P2** | `src/v1/engine/components/file/file_copy.py:92-94` | **`os.makedirs(destination)` creates intermediate directories unconditionally**: When `create_directory=True`, `os.makedirs(destination)` creates ALL intermediate directories in the path. If `destination="/a/b/c/d/"`, it creates `/a/`, `/a/b/`, `/a/b/c/`, and `/a/b/c/d/`. Talend's `CREATE_DIRECTORY` typically creates only the leaf directory, assuming parent directories exist. The engine behavior is more permissive than Talend. Also, there is no `exist_ok=True` parameter, so if the destination already exists as a directory, `makedirs` may or may not raise `FileExistsError` depending on OS and Python version (though on most platforms it does raise). |
| BUG-FCP-007 | **P2** | `src/v1/engine/components/file/file_copy.py:92` | **Directory creation check `not os.path.exists(destination)` is racy**: Between checking existence (line 92) and creating (line 94), another process could create the directory, causing `os.makedirs()` to raise `FileExistsError`. Should use `os.makedirs(destination, exist_ok=True)`. |

### 6.2 Missing Features

| ID | Priority | Issue |
|----|----------|-------|
| FEAT-FCP-001 | **P1** | **No `remove_source_file` handling**: The engine has no code to delete the source file after copying. The config key is not even read. Move semantics are completely absent. |
| FEAT-FCP-002 | **P1** | **No `die_on_error` handling**: The engine does not read a `die_on_error` config value. All errors are caught by the catch-all on line 128. There is no mechanism to let errors propagate to the caller for `COMPONENT_ERROR` trigger handling. |
| FEAT-FCP-003 | **P1** | **No Talend-specific globalMap variables set**: None of `DESTINATION_FILENAME`, `DESTINATION_FILEPATH`, `SOURCE_DIRECTORY`, `DESTINATION_DIRECTORY`, or `ERROR_MESSAGE` are written to globalMap. Only the generic NB_LINE stats are set via the base class mechanism. |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FCP-001 | **P2** | **`source` vs Talend `FILENAME`**: The engine uses `source` as the config key (line 67), while Talend uses `FILENAME`. This is acceptable as a semantic renaming, but differs from the convention used by other file components (e.g., `FileInputDelimited` uses `filepath`). |
| NAME-FCP-002 | **P2** | **`replace_file` vs Talend `REPLACE_FILE`**: Minor -- matches Talend naming convention with snake_case conversion. But the default value is inverted (see CONV-FCP-004). |
| NAME-FCP-003 | **P3** | **`new_name` vs Talend `DESTINATION_RENAME`**: Acceptable semantic renaming. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FCP-001 | **P2** | "Every component MUST have its own `parse_*` method" | No `parse_tfilecopy()` method exists. Uses `_map_component_parameters()`. The dispatch entry in converter.py references a nonexistent method. |
| STD-FCP-002 | **P2** | "`_validate_config()` returns `List[str]`" | No `_validate_config()` method defined in `FileCopy`. Validation is inline in `_process()` (lines 81-89). Not following the standard lifecycle pattern. |
| STD-FCP-003 | **P2** | "Use custom exceptions from `exceptions.py`" | Uses built-in `ValueError`, `FileNotFoundError`, `FileExistsError` instead of `ConfigurationError`, `FileOperationError` from the custom exception hierarchy. |
| STD-FCP-004 | **P3** | "Component `__repr__` should include key config" | Inherits base class `__repr__` which shows `type`, `id`, `status` but not `source`/`destination` paths. |

### 6.5 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No debug artifacts found in `file_copy.py`. Code is clean. |

### 6.6 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FCP-001 | **P3** | **No path traversal protection**: `source` and `destination` from config are used directly with `os.path.exists()`, `shutil.copy2()`, and `shutil.copytree()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FCP-002 | **P3** | **No symlink protection**: `shutil.copytree()` follows symlinks by default. A malicious source directory with symlinks could copy files from outside the intended directory tree. In sensitive environments, `follow_symlinks=False` should be considered. |

### 6.7 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, DEBUG for intermediate steps, ERROR for failures -- correct |
| Start/complete logging | Line 75 logs start with source/destination; line 125-126 logs completion with counts -- correct |
| Sensitive data | File paths are logged (lines 75, 83, 88, 93, 100, 104, 110, 113). Paths may contain sensitive directory structures but this is acceptable for operational logging. |
| No print statements | No `print()` calls -- correct |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **Not used**. Raises built-in `ValueError` (line 84), `FileNotFoundError` (line 89), `FileExistsError` (line 106). Should use `ConfigurationError` and `FileOperationError` from `exceptions.py`. |
| Exception chaining | **Not used**. The catch-all on line 128 does not chain exceptions (`raise ... from e` pattern missing). |
| Catch-all behavior | **Problematic**. Line 128 `except Exception as e` catches ALL exceptions, including the explicitly-raised `ValueError`/`FileNotFoundError`/`FileExistsError`. These exceptions are logged and swallowed -- never re-raised. The component always returns normally, preventing proper error handling. |
| Error messages | Include component ID and descriptive text -- correct format. |
| Graceful degradation | Returns `{'status': 'error', 'message': str(e)}` -- provides error info but prevents caller from detecting failure via exceptions. |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has complete type hints for parameter and return type -- correct |
| Class docstring | Comprehensive docstring documenting config parameters, inputs, outputs, statistics, example -- good |
| Missing hints | No missing type hints in the single method. |

### 6.10 Thread Safety

| Aspect | Assessment |
|--------|------------|
| Shared state | `self.config`, `self.stats`, `self.status` are instance variables -- no shared state between instances. Thread-safe for separate instances. |
| File system operations | `shutil.copy2()`, `shutil.copytree()`, `os.makedirs()` are not atomic. Concurrent copies to the same destination may corrupt files. No file locking. |
| GlobalMap access | `global_map.put()` uses a plain dict (not `threading.Lock`). Concurrent globalMap writes from different components are not thread-safe. This is a cross-cutting issue. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FCP-001 | **P2** | **`shutil.copytree()` on large directories has no progress feedback**: When copying a directory with thousands of files or gigabytes of data, there is no logging of progress. The component will appear to hang. Should log progress periodically (e.g., every 100 files or every 100MB). Consider using `shutil.copytree()` with a custom `copy_function` that logs progress. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Memory usage | Minimal. File copy operations are performed by the OS kernel via `shutil`. Python does not hold file contents in memory. |
| Large file handling | `shutil.copy2()` uses buffered I/O with a default buffer size. Handles files of any size without memory issues. |
| Large directory handling | `shutil.copytree()` recursively walks the directory tree and copies files one by one. Memory usage is proportional to directory depth (recursion stack), not file count or total size. |

### 7.2 Streaming Mode Considerations

`FileCopy` is a utility component that does not process DataFrames. The base class `execute()` method will call `_auto_select_mode(input_data)` where `input_data=None`, which returns `ExecutionMode.BATCH` (base_component.py line 239). Streaming mode is never activated. This is correct behavior -- file copy operations do not benefit from chunked processing.

However, if `input_data` is accidentally passed (e.g., from a Row connection instead of an Iterate connection), the base class `_execute_streaming()` would try to iterate over it and call `_process()` for each chunk. `_process()` ignores `input_data` entirely (line 50: parameter exists but is never used), so the copy would execute once per chunk -- potentially copying the same file multiple times. This is an edge case but could cause unexpected behavior.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileCopy` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter tests | **No** | -- | No converter tests for tFileCopy parsing |

**Key finding**: The v1 engine has ZERO tests for this component. All 132 lines of v1 engine code are completely unverified. The converter crash (CONV-FCP-001) demonstrates that even basic smoke testing has never been performed.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic file copy | P0 | Copy a file from source to destination, verify file exists at destination with correct content |
| 2 | Missing source file | P0 | Attempt to copy a non-existent file, verify appropriate error is raised |
| 3 | Missing required config | P0 | Empty `source` or `destination`, verify `ValueError` is raised |
| 4 | Replace existing file = True | P0 | Copy to a destination where file already exists with `replace_file=True`, verify file is overwritten |
| 5 | Replace existing file = False | P0 | Copy to a destination where file already exists with `replace_file=False`, verify `FileExistsError` is raised |
| 6 | Statistics tracking | P0 | Verify `NB_LINE=1`, `NB_LINE_OK=1`, `NB_LINE_REJECT=0` on success; `NB_LINE=1`, `NB_LINE_OK=0`, `NB_LINE_REJECT=1` on failure |
| 7 | Converter parse_tfilecopy exists | P0 | Verify that `component_parser.parse_tfilecopy()` method exists and is callable -- currently fails (the test itself documents the P0 bug) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Rename on copy | P1 | Copy with `rename=True, new_name='newfile.txt'`, verify destination file has new name |
| 9 | Create destination directory | P1 | Copy to non-existent directory with `create_directory=True`, verify directory is created and file is copied |
| 10 | Create destination directory = False | P1 | Copy to non-existent directory with `create_directory=False`, verify error is raised |
| 11 | Directory copy | P1 | Copy a directory tree, verify all files and subdirectories are copied correctly |
| 12 | Preserve last modified time | P1 | Copy with `preserve_last_modified=True`, verify destination file timestamp matches source |
| 13 | Do not preserve last modified time | P1 | Copy with `preserve_last_modified=False`, verify destination file has current timestamp (currently fails due to `copy2` always preserving -- BUG-FCP-004) |
| 14 | Context variable in source path | P1 | `${context.source_dir}/file.txt` should resolve via context manager |
| 15 | GlobalMap variables set | P1 | Verify `DESTINATION_FILENAME`, `DESTINATION_FILEPATH`, `SOURCE_DIRECTORY`, `DESTINATION_DIRECTORY` are set in globalMap (currently fails -- FEAT-FCP-003) |
| 16 | Error message in globalMap | P1 | Verify `ERROR_MESSAGE` is set in globalMap on failure (currently fails -- FEAT-FCP-003) |
| 17 | Remove source file (move) | P1 | Copy with `remove_source_file=True`, verify source is deleted after copy (currently fails -- FEAT-FCP-001) |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | File with spaces in path | P2 | Copy file with spaces in source and destination paths |
| 19 | Empty file | P2 | Copy a 0-byte file, verify it exists at destination |
| 20 | Large file (> 1GB) | P2 | Copy a large file, verify correct behavior and no memory issues |
| 21 | Concurrent copies | P2 | Multiple `FileCopy` instances copying to same destination directory simultaneously |
| 22 | Symlink handling | P2 | Copy a directory containing symlinks, verify correct behavior |
| 23 | Replace_file default behavior | P2 | Verify that when `replace_file` is not explicitly set in config, the default matches expected behavior |
| 24 | Permission denied on destination | P2 | Copy to a read-only directory, verify appropriate error |
| 25 | Disk full during copy | P2 | Verify graceful handling when disk runs out of space mid-copy |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| CONV-FCP-001 | Converter | **`parse_tfilecopy()` method does not exist**: `converter.py:287` dispatches to a method that is not defined in `component_parser.py`. Any Talend job with tFileCopy will crash during conversion with `AttributeError`. Completely blocks all tFileCopy usage. |
| BUG-FCP-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FCP-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FCP-001 | Testing | Zero v1 unit tests for this component. All 132 lines of engine code and the converter mapping are completely unverified. The converter crash (CONV-FCP-001) proves no testing was ever done. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FCP-002 | Converter | `REMOVE_SOURCE_FILE` not extracted -- move semantics unavailable. Jobs using tFileCopy to move files will only copy. |
| CONV-FCP-003 | Converter | `COPY_DIRECTORY` not extracted -- explicit directory copy toggle missing. Engine auto-detects via `os.path.isdir()`. |
| ENG-FCP-001 | Engine | **No `remove_source_file` (move semantics)**: Source file never deleted after copy. Fundamental gap for "process and archive" patterns. |
| ENG-FCP-002 | Engine | **No `die_on_error` support**: All errors caught by catch-all. No way to control error propagation. |
| ENG-FCP-003 | Engine | **Missing all 5 Talend globalMap variables**: `DESTINATION_FILENAME`, `DESTINATION_FILEPATH`, `SOURCE_DIRECTORY`, `DESTINATION_DIRECTORY`, `ERROR_MESSAGE` not set. |
| ENG-FCP-004 | Engine | **`REPLACE_FILE` default `True` differs from Talend default `false`**: Silent data overwrite risk. |
| BUG-FCP-003 | Bug | `replace_file=False` check targets directory path when not renaming, causing false `FileExistsError`. |
| BUG-FCP-004 | Bug | `shutil.copy2()` always preserves timestamps regardless of `preserve_last_modified` flag. When false, destination still gets source timestamp instead of current time. |
| FEAT-FCP-001 | Feature | No `remove_source_file` config handling -- move semantics completely absent. |
| FEAT-FCP-002 | Feature | No `die_on_error` config handling -- errors always swallowed by catch-all. |
| FEAT-FCP-003 | Feature | No Talend-specific globalMap variables set (5 variables missing). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FCP-004 | Converter | `REPLACE_FILE` default `True` differs from Talend default `false`. |
| CONV-FCP-005 | Converter | `CREATE_DIRECTORY` default `True` differs from Talend default `false`. |
| CONV-FCP-006 | Converter | `SOURCE_DIRECTORY` not extracted for directory copy mode. |
| ENG-FCP-005 | Engine | `shutil.copy2()` always preserves timestamps -- `preserve_last_modified=False` has no effect. |
| ENG-FCP-006 | Engine | `CREATE_DIRECTORY` default `True` differs from Talend default `false`. |
| ENG-FCP-007 | Engine | No explicit `copy_directory` toggle -- auto-detects via `os.path.isdir()`. |
| BUG-FCP-005 | Bug | Catch-all silently swallows exceptions -- component status is always `SUCCESS` even when error occurs. |
| BUG-FCP-006 | Bug | `os.makedirs(destination)` creates all intermediate directories, more permissive than Talend. |
| BUG-FCP-007 | Bug | `os.path.exists(destination)` + `os.makedirs(destination)` is a race condition (TOCTOU). |
| NAME-FCP-001 | Naming | `source` config key differs from other file components that use `filepath`. |
| NAME-FCP-002 | Naming | `replace_file` default inverted from Talend. |
| STD-FCP-001 | Standards | No `parse_tfilecopy()` method -- uses deprecated `_map_component_parameters()`. |
| STD-FCP-002 | Standards | No `_validate_config()` method -- validation inline in `_process()`. |
| STD-FCP-003 | Standards | Uses built-in exceptions instead of custom `ConfigurationError`/`FileOperationError`. |
| PERF-FCP-001 | Performance | No progress logging for large directory copies via `copytree`. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FCP-007 | Converter | No dedicated `parse_*` method -- uses deprecated generic mapper. |
| ENG-FCP-008 | Engine | `copytree` `dirs_exist_ok` requires Python 3.8+. |
| NAME-FCP-003 | Naming | `new_name` config key differs from Talend `DESTINATION_RENAME`. |
| STD-FCP-004 | Standards | Base class `__repr__` does not include source/destination paths. |
| SEC-FCP-001 | Security | No path traversal protection on source/destination paths. |
| SEC-FCP-002 | Security | No symlink protection -- `copytree` follows symlinks by default. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 1 converter, 2 bugs (cross-cutting), 1 testing |
| P1 | 11 | 2 converter, 4 engine, 2 bugs, 3 features |
| P2 | 15 | 3 converter, 3 engine, 3 bugs, 2 naming, 3 standards, 1 performance |
| P3 | 6 | 1 converter, 1 engine, 1 naming, 1 standards, 2 security |
| **Total** | **36** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Create `parse_tfilecopy()` method** (CONV-FCP-001): Add the missing method to `component_parser.py`. This is the highest priority fix because without it, NO tFileCopy job can be converted. The method should extract all Talend parameters including `REMOVE_SOURCE_FILE`, `COPY_DIRECTORY`, and `SOURCE_DIRECTORY`. See Appendix H for the recommended implementation.

2. **Fix `_update_global_map()` bug** (BUG-FCP-001): Change `value` to `stat_value` on `base_component.py` line 304. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

3. **Fix `GlobalMap.get()` bug** (BUG-FCP-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

4. **Create unit test suite** (TEST-FCP-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. Without these, no FileCopy behavior is verified.

### Short-Term (Hardening)

5. **Implement `remove_source_file` (move semantics)** (FEAT-FCP-001, CONV-FCP-002, ENG-FCP-001): Add `remove_source_file` config key extraction in the converter. In the engine, after a successful copy, call `os.remove(source)` for files or `shutil.rmtree(source)` for directories when `remove_source_file=True`. This is the most commonly used tFileCopy feature after basic copy.

6. **Fix `shutil.copy2` / `preserve_last_modified` behavior** (BUG-FCP-004, ENG-FCP-005): Use `shutil.copy()` (no metadata) when `preserve_last_modified=False`, and `shutil.copy2()` (with metadata) when `preserve_last_modified=True`. Remove the redundant `shutil.copystat()` call.

7. **Fix default values to match Talend** (CONV-FCP-004, CONV-FCP-005, ENG-FCP-004, ENG-FCP-006): Change `replace_file` default from `True` to `False`. Change `create_directory` default from `True` to `False`. Both in the converter mapping AND the engine `config.get()` calls.

8. **Set Talend-specific globalMap variables** (ENG-FCP-003, FEAT-FCP-003): After a successful copy, set all 5 globalMap variables:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_DESTINATION_FILENAME", os.path.basename(final_destination))
       self.global_map.put(f"{self.id}_DESTINATION_FILEPATH", os.path.abspath(final_destination))
       self.global_map.put(f"{self.id}_SOURCE_DIRECTORY", os.path.dirname(source))
       self.global_map.put(f"{self.id}_DESTINATION_DIRECTORY", os.path.abspath(destination))
   ```
   On error:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```

9. **Implement `die_on_error` support** (FEAT-FCP-002, ENG-FCP-002): Add `die_on_error` config handling. When `True`, let exceptions propagate (remove catch-all or re-raise). When `False`, catch exceptions and return error result dict. The current catch-all behavior is only correct for `die_on_error=False`.

10. **Fix `replace_file` check for non-rename mode** (BUG-FCP-003): When `rename=False`, compute the actual target file path (not the directory) before checking existence:
    ```python
    if not rename:
        actual_target = os.path.join(destination, os.path.basename(source))
    else:
        actual_target = os.path.join(destination, new_name)

    if os.path.exists(actual_target) and not replace_file:
        raise FileExistsError(...)
    ```

11. **Fix catch-all exception handling** (BUG-FCP-005): Remove the catch-all `except Exception` block or restructure to re-raise when `die_on_error=True`. Use custom exceptions (`ConfigurationError`, `FileOperationError`) for structured error handling.

### Long-Term (Optimization)

12. **Add `copy_directory` toggle** (CONV-FCP-003, CONV-FCP-006, ENG-FCP-007): Extract `COPY_DIRECTORY` and `SOURCE_DIRECTORY` parameters. When `copy_directory=True`, use `SOURCE_DIRECTORY` as the source path. When `False`, use `FILENAME`. This matches Talend's explicit mode switching.

13. **Fix TOCTOU race condition** (BUG-FCP-007): Replace `if not os.path.exists(destination): os.makedirs(destination)` with `os.makedirs(destination, exist_ok=True)`.

14. **Add progress logging for directory copies** (PERF-FCP-001): Use `shutil.copytree()` with a custom `copy_function` that logs every N files or N bytes.

15. **Use custom exceptions** (STD-FCP-003): Replace `ValueError` with `ConfigurationError`, `FileNotFoundError` with `FileOperationError`, `FileExistsError` with `FileOperationError`.

16. **Add `_validate_config()` method** (STD-FCP-002): Implement standard lifecycle validation that checks required fields, validates path formats, and returns a list of error strings.

17. **Add symlink protection** (SEC-FCP-002): Pass `follow_symlinks=False` to `shutil.copy2` and `symlinks=True` to `shutil.copytree` to preserve symlinks as symlinks rather than following them.

---

## Appendix A: Converter Parameter Mapping Code (Dead Code)

```python
# component_parser.py lines 275-285
# NOTE: This code is DEAD -- unreachable because converter.py line 287
# dispatches to parse_tfilecopy() which does not exist, crashing before
# this code can execute.

# tFileCopy mapping
elif component_type == 'tFileCopy':
    return {
        'source': config_raw.get('FILENAME', ''),
        'destination': config_raw.get('DESTINATION', ''),
        'rename': config_raw.get('RENAME', False),
        'new_name': config_raw.get('DESTINATION_RENAME', ''),
        'replace_file': config_raw.get('REPLACE_FILE', True),
        'create_directory': config_raw.get('CREATE_DIRECTORY', True),
        'preserve_last_modified': config_raw.get('PRESERVE_LAST_MODIFIED_TIME', False)
    }
```

**Why this code is dead**: The converter flow is:
1. `converter.py:226` calls `parse_base_component(node)` which calls `_map_component_parameters('tFileCopy', config_raw)` -- this hits the branch above and populates `component['config']`.
2. `converter.py:287` then calls `parse_tfilecopy(node, component)` -- this method does NOT exist in `component_parser.py`, raising `AttributeError`.
3. The exception propagates up, and the valid config from step 1 is never returned to the caller.

**Critically**: The `_map_component_parameters` code IS executed (step 1), but its result is never used because the subsequent call to `parse_tfilecopy` crashes. The crash occurs AFTER the valid config is already in `component['config']`. If the `parse_tfilecopy` call on line 287 were simply removed (or changed to not crash), the existing mapping would work.

**Notes on the code**:
- Line 282: `REPLACE_FILE` default is `True`, but Talend default is `false`. Inverted.
- Line 283: `CREATE_DIRECTORY` default is `True`, but Talend default is `false`. Inverted.
- `REMOVE_SOURCE_FILE` is NOT extracted. Move semantics are missing.
- `COPY_DIRECTORY` and `SOURCE_DIRECTORY` are NOT extracted. Directory copy toggle is missing.

---

## Appendix B: Engine Class Structure

```
FileCopy (BaseComponent)
    Configuration Keys:
        source (str): Source file/directory path. Required.
        destination (str): Destination directory path. Required.
        rename (bool): Rename copied file. Default: False
        new_name (str): New filename. Default: ''
        replace_file (bool): Overwrite existing. Default: True (DIFFERS from Talend)
        create_directory (bool): Auto-create dest dir. Default: True (DIFFERS from Talend)
        preserve_last_modified (bool): Keep source timestamps. Default: False

    Methods:
        _process(input_data) -> Dict[str, Any]  # Main entry point (only method)

    Missing Methods:
        _validate_config()  # Not implemented
        _set_global_map_variables()  # Not implemented

    Missing Config Keys:
        remove_source_file  # Not read
        die_on_error  # Not read
        copy_directory  # Not read
        source_directory  # Not read
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `source` | Mapped (dead code) | -- |
| `DESTINATION` | `destination` | Mapped (dead code) | -- |
| `RENAME` | `rename` | Mapped (dead code) | -- |
| `DESTINATION_RENAME` | `new_name` | Mapped (dead code) | -- |
| `REPLACE_FILE` | `replace_file` | Mapped (dead code) | -- (fix default) |
| `CREATE_DIRECTORY` | `create_directory` | Mapped (dead code) | -- (fix default) |
| `PRESERVE_LAST_MODIFIED_TIME` | `preserve_last_modified` | Mapped (dead code) | -- |
| `REMOVE_SOURCE_FILE` | `remove_source_file` | **Not Mapped** | P1 |
| `COPY_DIRECTORY` | `copy_directory` | **Not Mapped** | P1 |
| `SOURCE_DIRECTORY` | `source_directory` | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |

---

## Appendix D: Converter Dispatch Flow Diagram

```
converter.py: _parse_component(node)
    |
    |--> component_type = 'tFileCopy'
    |
    |--> Step 1: component = self.component_parser.parse_base_component(node)
    |       |
    |       |--> Extracts UNIQUE_NAME, componentName, position
    |       |--> Builds config_raw from elementParameter nodes
    |       |--> Calls _map_component_parameters('tFileCopy', config_raw)
    |       |       |--> Hits elif branch on line 276
    |       |       |--> Returns {'source': ..., 'destination': ..., ...}
    |       |       |--> 7 parameters mapped correctly
    |       |
    |       |--> component['config'] = mapped_config  <-- VALID CONFIG
    |       |--> Extracts schema metadata (empty for tFileCopy)
    |       |--> Returns component dict with valid config
    |
    |--> Step 2: component = self.component_parser.parse_tfilecopy(node, component)
    |       |
    |       |--> AttributeError: 'ComponentParser' object has no attribute 'parse_tfilecopy'
    |       |--> *** CRASH ***
    |       |--> Valid config from Step 1 is LOST
    |
    |--> NEVER REACHED: return component
```

---

## Appendix E: Detailed Code Analysis

### `_process()` (Lines 50-133)

The complete and only method in `FileCopy`. Analysis by section:

**Lines 67-73: Config extraction**
```python
source = self.config.get('source')
destination = self.config.get('destination')
rename = self.config.get('rename', False)
new_name = self.config.get('new_name', '')
replace_file = self.config.get('replace_file', True)
create_directory = self.config.get('create_directory', True)
preserve_last_modified = self.config.get('preserve_last_modified', False)
```
- Missing: `remove_source_file`, `die_on_error`, `copy_directory`, `source_directory`.
- `replace_file` default `True` differs from Talend default `false`.
- `create_directory` default `True` differs from Talend default `false`.

**Lines 81-89: Validation**
```python
if not source or not destination:
    raise ValueError(...)
if not os.path.exists(source):
    raise FileNotFoundError(...)
```
- Uses built-in exceptions instead of custom `ConfigurationError`/`FileOperationError`.
- These exceptions are CAUGHT by the catch-all on line 128 and swallowed.

**Lines 92-94: Directory creation**
```python
if not os.path.exists(destination) and create_directory:
    os.makedirs(destination)
```
- TOCTOU race condition: between `exists()` check and `makedirs()` call.
- Missing `exist_ok=True` parameter.
- Creates ALL intermediate directories, more permissive than Talend.

**Lines 97-100: Rename handling**
```python
final_destination = destination
if rename and new_name:
    final_destination = os.path.join(destination, new_name)
```
- Correct: builds full path when renaming.
- Issue: when NOT renaming, `final_destination` is the DIRECTORY, not the file. This affects the `replace_file` check on line 103.

**Lines 103-106: Replace file check**
```python
if os.path.exists(final_destination) and not replace_file:
    raise FileExistsError(...)
```
- When not renaming, checks if DIRECTORY exists, not the specific file.
- When renaming, checks the correct full file path.

**Lines 109-114: Copy operation**
```python
if os.path.isdir(source):
    shutil.copytree(source, final_destination, dirs_exist_ok=replace_file)
else:
    shutil.copy2(source, final_destination)
```
- `os.path.isdir()` auto-detects directory vs file (no explicit toggle).
- `shutil.copy2()` always copies metadata (including timestamps) regardless of `preserve_last_modified`.
- `shutil.copytree()` with `dirs_exist_ok` requires Python 3.8+.

**Lines 117-119: Timestamp preservation**
```python
if preserve_last_modified:
    shutil.copystat(source, final_destination)
```
- Redundant for files: `copy2()` already did this.
- For directories: `copytree()` copies individual file metadata but NOT the top-level directory metadata. This `copystat` call handles the top-level directory. Correct for directory mode, redundant for file mode.

**Lines 122-126: Success path**
```python
self._update_stats(rows_processed, 1, 0)
result = {'status': 'success', 'message': f"Copied {source} to {final_destination}"}
```
- No globalMap variables set.
- No `DESTINATION_FILENAME`, `DESTINATION_FILEPATH`, etc.

**Lines 128-131: Error path**
```python
except Exception as e:
    logger.error(...)
    self._update_stats(rows_processed, 0, 1)
    result = {'status': 'error', 'message': str(e)}
```
- Catches ALL exceptions including the explicitly-raised ones on lines 84, 89, 106.
- Never re-raises. Component always returns normally.
- No `ERROR_MESSAGE` set in globalMap.

**Line 133: Return**
```python
return {'main': result}
```
- Returns `{'main': dict}` not `{'main': DataFrame}`. This differs from data flow components that return `{'main': pd.DataFrame}`. The base class `_execute_streaming()` tries to `pd.concat()` results, which would fail on dicts. However, since `input_data=None`, streaming mode is never activated for this component.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Source file does not exist

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error. COMPONENT_ERROR trigger fires. ERROR_MESSAGE set in globalMap. |
| **V1** | `FileNotFoundError` raised on line 89, caught by catch-all on line 128. Returns `{'status': 'error', 'message': '...'}`. ERROR_MESSAGE NOT set in globalMap. Component status is SUCCESS (bug). |
| **Verdict** | GAP -- error handling differs. No ERROR_MESSAGE in globalMap. Status incorrectly shows SUCCESS. |

### Edge Case 2: Destination directory does not exist, create_directory=False

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error. Copy fails. |
| **V1** | Skips `os.makedirs()` on line 94. `shutil.copy2()` on line 114 raises `FileNotFoundError` because destination directory doesn't exist. Caught by catch-all. Returns error result. |
| **Verdict** | CORRECT behavior, but error message differs (OS-level error vs Talend-specific message). |

### Edge Case 3: Destination file exists, replace_file=False, rename=False

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error because destination file already exists. |
| **V1** | `final_destination = destination` (the directory). `os.path.exists(destination)` returns True (directory exists). `FileExistsError` raised. |
| **Verdict** | INCORRECT -- raises error because the DIRECTORY exists, not because the FILE exists. If the destination directory has other files but NOT the specific file being copied, this still raises an error. See BUG-FCP-003. |

### Edge Case 4: Destination file exists, replace_file=False, rename=True

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error because renamed destination file already exists. |
| **V1** | `final_destination = os.path.join(destination, new_name)`. `os.path.exists(final_destination)` correctly checks the file path. `FileExistsError` raised if file exists. |
| **Verdict** | CORRECT. |

### Edge Case 5: Source is a directory with many nested subdirectories

| Aspect | Detail |
|--------|--------|
| **Talend** | Copies entire tree recursively. |
| **V1** | `shutil.copytree()` copies entire tree. `dirs_exist_ok=replace_file` controls overwrite behavior. |
| **Verdict** | CORRECT. But no progress logging for large trees. |

### Edge Case 6: Source is a directory, destination exists, replace_file=True

| Aspect | Detail |
|--------|--------|
| **Talend** | Overwrites/merges with existing directory contents. |
| **V1** | `shutil.copytree(source, destination, dirs_exist_ok=True)` merges trees. Existing files in destination are overwritten if source has same-named files. New files from source are added. Existing files in destination NOT in source are preserved. |
| **Verdict** | CORRECT -- merge behavior matches Talend. |

### Edge Case 7: Source is a directory, destination exists, replace_file=False

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error because destination directory exists. |
| **V1** | `shutil.copytree(source, destination, dirs_exist_ok=False)` raises `FileExistsError`. |
| **Verdict** | CORRECT. |

### Edge Case 8: Copy file from NFS/network path

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles NFS/UNC paths via Java NIO. May have performance or timeout issues. |
| **V1** | `shutil.copy2()` uses OS-level file operations. NFS/network paths are handled by the OS. Python has no special NFS handling. |
| **Verdict** | CORRECT for basic cases. Network-specific errors may differ. |

### Edge Case 9: Source file is read-only

| Aspect | Detail |
|--------|--------|
| **Talend** | Copies successfully (reading doesn't require write permission). |
| **V1** | `shutil.copy2()` reads source and writes to destination. Source permissions are irrelevant for reading. |
| **Verdict** | CORRECT. |

### Edge Case 10: Destination file is read-only, replace_file=True

| Aspect | Detail |
|--------|--------|
| **Talend** | May raise error depending on OS. |
| **V1** | `shutil.copy2()` will raise `PermissionError`. Caught by catch-all. |
| **Verdict** | CORRECT behavior (error), but error is swallowed by catch-all. |

### Edge Case 11: Source path contains context variable

| Aspect | Detail |
|--------|--------|
| **Talend** | Resolves `context.var` before file operation. |
| **V1** | `context_manager.resolve_dict()` called in `execute()` (line 202) before `_process()`. Context variables in `source` and `destination` are resolved. |
| **Verdict** | CORRECT. |

### Edge Case 12: Source path contains globalMap reference (`tFileList` pattern)

| Aspect | Detail |
|--------|--------|
| **Talend** | `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))` is a Java expression resolved at runtime. |
| **V1** | Marked as `{{java}}` expression by converter. Resolved by Java bridge in `_resolve_java_expressions()` (line 198). Requires Java bridge to be available. |
| **Verdict** | CORRECT if Java bridge is configured. If Java bridge is not available, warning is logged (line 129-130 of base_component.py) and the raw expression string is used as the file path, causing FileNotFoundError. |

### Edge Case 13: Empty string for source or destination

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error at design time (required field). |
| **V1** | `if not source or not destination:` check on line 81 catches empty strings. Raises `ValueError`. |
| **Verdict** | CORRECT. |

### Edge Case 14: Source and destination are the same path

| Aspect | Detail |
|--------|--------|
| **Talend** | Raises error (source and destination cannot be the same). |
| **V1** | `shutil.copy2()` may or may not handle this depending on OS. On some systems it silently succeeds (no-op). On others it raises `SameFileError`. |
| **Verdict** | GAP -- no explicit check for source==destination. Behavior is OS-dependent. |

### Edge Case 15: NaN, empty strings, empty DataFrame considerations

| Aspect | Detail |
|--------|--------|
| **Relevance** | `FileCopy` is a utility component that does not process DataFrames. These data-related edge cases are not applicable. |
| **Input data handling** | `_process()` accepts `input_data` parameter but never uses it (line 50). If a DataFrame is passed, it is silently ignored. |
| **Verdict** | N/A for this component type. |

### Edge Case 16: HYBRID streaming mode interaction

| Aspect | Detail |
|--------|--------|
| **Scenario** | If `execution_mode=HYBRID` and `input_data` is a large DataFrame. |
| **V1** | `_auto_select_mode(input_data)` returns `BATCH` when `input_data=None` (line 239). Since `FileCopy._process()` is always called with `input_data=None` in normal usage, streaming is never activated. |
| **Risk** | If erroneously called with a DataFrame (e.g., from a Row connection), `_execute_streaming()` would chunk the DataFrame and call `_process()` once per chunk. Each call performs the same file copy (ignoring input). The file would be copied N times (once per chunk). |
| **Verdict** | Low risk but worth documenting. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileCopy`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FCP-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FCP-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: CONV-FCP-001 -- Create `parse_tfilecopy()` method

**File**: `src/converters/complex_converter/component_parser.py`

**Option A (Quick fix)**: Remove the dispatch in `converter.py` line 287, letting `parse_base_component()` handle tFileCopy via `_map_component_parameters`:

```python
# converter.py line 286-287
# CHANGE FROM:
elif component_type == 'tFileCopy':
    component = self.component_parser.parse_tfilecopy(node, component)

# CHANGE TO:
elif component_type == 'tFileCopy':
    pass  # Config already populated by parse_base_component() -> _map_component_parameters()
```

**Option B (Proper fix)**: Create a dedicated `parse_tfilecopy()` method that extracts ALL parameters including the missing ones:

```python
def parse_tfilecopy(self, node, component: Dict) -> Dict:
    """
    Parse tFileCopy specific configuration from Talend XML node.

    Talend Parameters:
        FILENAME (str): Source file path. Mandatory.
        DESTINATION (str): Destination directory. Mandatory.
        RENAME (bool): Rename copied file. Default false.
        DESTINATION_RENAME (str): New filename for rename.
        REMOVE_SOURCE_FILE (bool): Delete source after copy. Default false.
        REPLACE_FILE (bool): Overwrite existing. Default false.
        CREATE_DIRECTORY (bool): Create dest dir. Default false.
        COPY_DIRECTORY (bool): Copy entire directory. Default false.
        SOURCE_DIRECTORY (str): Source directory (when COPY_DIRECTORY=true).
        PRESERVE_LAST_MODIFIED_TIME (bool): Keep timestamps. Default false.
    """
    config = component.get('config', {})

    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')
        field = param.get('field', '')

        # Strip surrounding quotes
        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        if name == 'FILENAME':
            config['source'] = self.expr_converter.mark_java_expression(value)
        elif name == 'DESTINATION':
            config['destination'] = self.expr_converter.mark_java_expression(value)
        elif name == 'RENAME':
            config['rename'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'DESTINATION_RENAME':
            config['new_name'] = self.expr_converter.mark_java_expression(value)
        elif name == 'REMOVE_SOURCE_FILE':
            config['remove_source_file'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'REPLACE_FILE':
            config['replace_file'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'CREATE_DIRECTORY':
            config['create_directory'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'COPY_DIRECTORY':
            config['copy_directory'] = (value.lower() == 'true') if field == 'CHECK' else False
        elif name == 'SOURCE_DIRECTORY':
            config['source_directory'] = self.expr_converter.mark_java_expression(value)
        elif name == 'PRESERVE_LAST_MODIFIED_TIME':
            config['preserve_last_modified'] = (value.lower() == 'true') if field == 'CHECK' else False

    component['config'] = config
    return component
```

**Impact**: Unblocks all tFileCopy conversion. Extracts 3 additional parameters not in the current dead code. Fixes defaults to match Talend.

---

### Fix Guide: BUG-FCP-001 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). Best fix is to remove the stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-FCP-002 -- `GlobalMap.get()` undefined default

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

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low.

---

### Fix Guide: BUG-FCP-004 -- `copy2` always preserves timestamps

**File**: `src/v1/engine/components/file/file_copy.py`
**Lines**: 112-119

**Current code**:
```python
else:
    logger.debug(f"[{self.id}] Copying file: {source} -> {final_destination}")
    shutil.copy2(source, final_destination)

# Preserve last modified time if requested
if preserve_last_modified:
    logger.debug(f"[{self.id}] Preserving last modified time")
    shutil.copystat(source, final_destination)
```

**Fix**:
```python
else:
    logger.debug(f"[{self.id}] Copying file: {source} -> {final_destination}")
    if preserve_last_modified:
        shutil.copy2(source, final_destination)  # copy data + metadata
    else:
        shutil.copy(source, final_destination)  # copy data only (current timestamp)
```

**Explanation**: `shutil.copy()` copies file data without metadata. `shutil.copy2()` copies data AND metadata (including timestamps). Using `copy()` when `preserve_last_modified=False` ensures the destination gets the current timestamp.

---

### Fix Guide: BUG-FCP-005 -- Catch-all silently swallows exceptions

**File**: `src/v1/engine/components/file/file_copy.py`
**Lines**: 128-131

**Current code**:
```python
except Exception as e:
    logger.error(f"[{self.id}] Copy operation failed: {e}")
    self._update_stats(rows_processed, 0, 1)
    result = {'status': 'error', 'message': str(e)}
```

**Fix**:
```python
except Exception as e:
    logger.error(f"[{self.id}] Copy operation failed: {e}")
    self._update_stats(rows_processed, 0, 1)
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    die_on_error = self.config.get('die_on_error', True)
    if die_on_error:
        raise FileOperationError(f"[{self.id}] Copy failed: {e}") from e
    result = {'status': 'error', 'message': str(e)}
```

**Explanation**: When `die_on_error=True` (default for utility components), re-raise as `FileOperationError`. When `False`, swallow and return error dict. Always set ERROR_MESSAGE in globalMap.

---

### Fix Guide: FEAT-FCP-001 -- Implement remove_source_file (move semantics)

**File**: `src/v1/engine/components/file/file_copy.py`
**After line 119** (after the copy operation and timestamp handling):

```python
# Remove source file if requested (move semantics)
remove_source = self.config.get('remove_source_file', False)
if remove_source:
    logger.debug(f"[{self.id}] Removing source file (move mode): {source}")
    if os.path.isdir(source):
        shutil.rmtree(source)
    else:
        os.remove(source)
    logger.info(f"[{self.id}] Source removed: {source}")
```

**Impact**: Enables move semantics. **Risk**: Medium -- source deletion is irreversible. Should be thoroughly tested.

---

### Fix Guide: FEAT-FCP-003 -- Set Talend-specific globalMap variables

**File**: `src/v1/engine/components/file/file_copy.py`
**After line 123** (after `_update_stats` in the success path):

```python
# Set Talend-compatible globalMap variables
if self.global_map:
    self.global_map.put(f"{self.id}_DESTINATION_FILENAME",
                        os.path.basename(final_destination))
    self.global_map.put(f"{self.id}_DESTINATION_FILEPATH",
                        os.path.abspath(final_destination))
    self.global_map.put(f"{self.id}_SOURCE_DIRECTORY",
                        os.path.dirname(os.path.abspath(source)))
    self.global_map.put(f"{self.id}_DESTINATION_DIRECTORY",
                        os.path.abspath(destination))
```

---

## Appendix I: Comparison with Other File Utility Components

| Feature | tFileCopy (V1) | tFileDelete (V1) | tFileTouch (V1) | tFileExist (V1) |
|---------|----------------|-------------------|------------------|------------------|
| Basic operation | Copy file/dir | Delete file/dir | Create empty file | Check file exists |
| Parameter extraction | Dead code (crash) | Via parse_base_component | Via parse_tfiletouch | Via parse_tfileexist |
| Dedicated parser | **No** (method missing) | **No** (uses base) | Yes | Yes |
| Die on error | **No** | Unknown | Unknown | N/A |
| GlobalMap variables | **No** | Unknown | Unknown | Unknown |
| Remove source | **No** | N/A | N/A | N/A |
| V1 Unit tests | **No** | **No** | **No** | **No** |

**Observation**: The missing `parse_tfilecopy()` method is unique to tFileCopy -- other file utility components either have dedicated parsers or explicitly use `parse_base_component`. The lack of v1 unit tests is systemic across all file utility components.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Any job containing tFileCopy | **Blocker** | ALL tFileCopy jobs | Fix CONV-FCP-001 (missing parse method) before any conversion |
| Jobs using tFileCopy to MOVE files | **Critical** | Jobs with REMOVE_SOURCE_FILE=true | Implement remove_source_file feature |
| Jobs referencing DESTINATION_FILEPATH in downstream | **High** | Jobs with audit/logging using globalMap vars | Implement globalMap variable setting |
| Jobs relying on replace_file=false default | **High** | Jobs that don't explicitly set REPLACE_FILE | Fix default to match Talend (false) |
| Jobs with preserve_last_modified=false | **Medium** | Jobs where destination should have current timestamp | Fix copy2 vs copy behavior |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Basic file copy with explicit config | Low | Once converter crash is fixed, basic copy works |
| Directory copy with replace_file=true | Low | copytree with dirs_exist_ok works correctly |
| Rename on copy | Low | Implementation is correct |

### Recommended Migration Strategy

1. **Phase 0 (Blocker)**: Fix CONV-FCP-001 -- create `parse_tfilecopy()` method or remove the broken dispatch. Without this, NO tFileCopy job can be converted.
2. **Phase 1**: Fix cross-cutting P0 bugs (BUG-FCP-001, BUG-FCP-002). Fix default values (REPLACE_FILE, CREATE_DIRECTORY).
3. **Phase 2**: Implement `remove_source_file` (move semantics) and `die_on_error` support.
4. **Phase 3**: Set Talend-compatible globalMap variables. Fix `copy2`/`copy` timestamp behavior.
5. **Phase 4**: Create unit tests covering all P0 and P1 test cases.
6. **Phase 5**: Parallel-run migrated jobs against Talend originals. Verify file operations produce identical results.

---

## Appendix K: Return Format Analysis

### Current Return Format

```python
# Success:
{'main': {'status': 'success', 'message': 'Copied /src/file.txt to /dst/file.txt'}}

# Failure:
{'main': {'status': 'error', 'message': '[tFileCopy_1] Source path does not exist: /src/missing.txt'}}
```

### Expected Return Format (per base class contract)

The base class `_process()` docstring (base_component.py lines 287-295) states:
```
Returns:
    Dict with keys:
    -'main': main output DataFrame
    -'reject': Rejected rows DataFrame (optional)
    - Any other outputs specific to the component
```

The `FileCopy` component returns `{'main': dict}` instead of `{'main': pd.DataFrame}`. This is acceptable for utility components that do not produce data rows, BUT it creates an inconsistency:

1. The base class `_execute_streaming()` (line 270-271) does `results.append(chunk_result['main'])` and then `pd.concat(results)`. If streaming mode were activated (normally impossible for this component but theoretically possible), `pd.concat()` on a list of dicts would raise `TypeError`.

2. Downstream components expecting a DataFrame from the `main` output would fail.

3. The `stats` key added by `execute()` (line 223) works correctly because it's added to the result dict, not to the `main` value.

**Recommendation**: This is correct behavior for a utility component. Document that utility components return `{'main': dict}` instead of `{'main': DataFrame}`. The engine's connection handling should check result types before passing between components.

---

## Appendix L: Complete Engine Implementation with All Fixes

The following shows the recommended implementation of `file_copy.py` with all P0 and P1 fixes applied:

```python
"""
tFileCopy component - Copies/moves files from source to destination

Talend equivalent: tFileCopy
"""
import os
import shutil
from typing import Dict, Any, List, Optional
import logging

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


class FileCopy(BaseComponent):
    """
    Copies or moves files or directories from source to destination.

    Configuration:
        source (str): Source file path. Required.
        destination (str): Destination directory path. Required.
        rename (bool): Whether to rename the copied file. Default: False
        new_name (str): New name for the copied file. Default: ''
        remove_source_file (bool): Delete source after copy (move). Default: False
        replace_file (bool): Whether to replace existing files. Default: False
        create_directory (bool): Create destination directory. Default: False
        copy_directory (bool): Copy entire directory. Default: False
        source_directory (str): Source directory (when copy_directory=True). Default: ''
        preserve_last_modified (bool): Preserve source timestamps. Default: False
        die_on_error (bool): Raise on error vs return error dict. Default: True
    """

    def _validate_config(self) -> List[str]:
        """Validate component configuration"""
        errors = []
        if not self.config.get('source') and not self.config.get('source_directory'):
            errors.append("Source path must be provided")
        if not self.config.get('destination'):
            errors.append("Destination path must be provided")
        return errors

    def _process(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        source = self.config.get('source', '')
        destination = self.config.get('destination', '')
        rename = self.config.get('rename', False)
        new_name = self.config.get('new_name', '')
        remove_source_file = self.config.get('remove_source_file', False)
        replace_file = self.config.get('replace_file', False)  # Talend default
        create_directory = self.config.get('create_directory', False)  # Talend default
        copy_directory = self.config.get('copy_directory', False)
        source_directory = self.config.get('source_directory', '')
        preserve_last_modified = self.config.get('preserve_last_modified', False)
        die_on_error = self.config.get('die_on_error', True)

        # Use source_directory when copy_directory mode
        if copy_directory and source_directory:
            source = source_directory

        logger.info(f"[{self.id}] Copy operation started: {source} -> {destination}")

        rows_processed = 1
        result = {'status': 'error', 'message': ''}

        try:
            # Validation
            if not source or not destination:
                raise ConfigurationError("Source and destination paths must be provided")

            if not os.path.exists(source):
                raise FileOperationError(f"Source path does not exist: {source}")

            # Create destination directory if needed
            if create_directory:
                os.makedirs(destination, exist_ok=True)

            # Determine final destination path
            if rename and new_name:
                final_destination = os.path.join(destination, new_name)
            else:
                if os.path.isdir(source):
                    final_destination = destination
                else:
                    final_destination = os.path.join(destination, os.path.basename(source))

            # Check if destination exists
            if os.path.exists(final_destination) and not replace_file:
                raise FileOperationError(
                    f"Destination already exists and replace_file is False: {final_destination}")

            # Perform copy
            if os.path.isdir(source):
                shutil.copytree(source, final_destination, dirs_exist_ok=replace_file)
            else:
                if preserve_last_modified:
                    shutil.copy2(source, final_destination)
                else:
                    shutil.copy(source, final_destination)

            # Remove source if requested (move semantics)
            if remove_source_file:
                if os.path.isdir(source):
                    shutil.rmtree(source)
                else:
                    os.remove(source)

            # Set globalMap variables
            if self.global_map:
                self.global_map.put(f"{self.id}_DESTINATION_FILENAME",
                                    os.path.basename(final_destination))
                self.global_map.put(f"{self.id}_DESTINATION_FILEPATH",
                                    os.path.abspath(final_destination))
                self.global_map.put(f"{self.id}_SOURCE_DIRECTORY",
                                    os.path.dirname(os.path.abspath(source)))
                self.global_map.put(f"{self.id}_DESTINATION_DIRECTORY",
                                    os.path.abspath(destination))

            self._update_stats(rows_processed, 1, 0)
            result = {'status': 'success', 'message': f"Copied {source} to {final_destination}"}

        except Exception as e:
            logger.error(f"[{self.id}] Copy operation failed: {e}")
            self._update_stats(rows_processed, 0, 1)
            if self.global_map:
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
            if die_on_error:
                raise FileOperationError(f"[{self.id}] Copy failed: {e}") from e
            result = {'status': 'error', 'message': str(e)}

        return {'main': result}
```

---

## Appendix M: Base Class Interaction Analysis

### `execute()` Lifecycle for FileCopy

When `FileCopy.execute()` is called (inherited from `BaseComponent`), the following lifecycle steps occur:

```
BaseComponent.execute(input_data=None)
    |
    |--> self.status = ComponentStatus.RUNNING
    |--> start_time = time.time()
    |
    |--> Step 1: Resolve Java expressions (if java_bridge available)
    |       |--> _resolve_java_expressions()
    |       |--> Scans self.config for {{java}} markers
    |       |--> For tFileCopy: source/destination may contain Java expressions
    |       |    e.g., ((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))
    |       |--> Requires java_bridge to be set by engine
    |
    |--> Step 2: Resolve context variables (if context_manager available)
    |       |--> self.config = self.context_manager.resolve_dict(self.config)
    |       |--> For tFileCopy: source/destination may contain ${context.var}
    |       |    e.g., ${context.sourceDir}/input.txt
    |
    |--> Step 3: Determine execution mode (HYBRID -> BATCH for input_data=None)
    |       |--> _auto_select_mode(None) returns ExecutionMode.BATCH
    |
    |--> Step 4: Execute in batch mode
    |       |--> _execute_batch(None)
    |       |--> Calls self._process(None)  # FileCopy._process()
    |       |    |--> Performs file copy operation
    |       |    |--> Returns {'main': {'status': '...', 'message': '...'}}
    |
    |--> Step 5: Update statistics
    |       |--> self.stats['EXECUTION_TIME'] = time.time() - start_time
    |       |--> self._update_global_map()  # CRASHES due to BUG-FCP-001
    |       |    |--> NameError: name 'value' is not defined
    |       |    |--> Exception propagates to execute() catch block (line 227)
    |
    |--> Step 6: Exception handler (line 227-234)
    |       |--> self.status = ComponentStatus.ERROR
    |       |--> self.error_message = "name 'value' is not defined"
    |       |--> self._update_global_map()  # CRASHES AGAIN (same bug)
    |       |--> Infinite recursion? No -- the second crash is also caught.
    |       |--> Actually: line 231 calls _update_global_map() which crashes,
    |       |    and this NameError propagates up uncaught from the except block.
    |       |    The component execution appears to fail with a NameError.
    |       |
    |       |--> RESULT: Even a successful file copy will appear to fail
    |            because _update_global_map() crashes in the success path.
```

**Critical insight**: Due to BUG-FCP-001 (`_update_global_map()` referencing undefined `value`), EVERY execution of FileCopy (and every other component) with a non-None `global_map` will crash. The crash occurs on the SUCCESS path (line 218), causing the exception handler to fire (line 227), which calls `_update_global_map()` AGAIN (line 231), causing another crash. The second crash propagates out of the `except` block, resulting in an unhandled `NameError` that terminates the job.

**Implication**: If `global_map` is None (not configured), the component works correctly. If `global_map` is configured (the normal case), the component always fails regardless of whether the file copy succeeded.

### `_update_stats()` Behavior

`FileCopy._process()` calls `_update_stats()` with:
- Success: `_update_stats(1, 1, 0)` -- NB_LINE=1, NB_LINE_OK=1, NB_LINE_REJECT=0
- Failure: `_update_stats(1, 0, 1)` -- NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=1

The base class `_update_stats()` (lines 306-312) uses `+=` to accumulate, so multiple calls would sum. For FileCopy, `_process()` is called exactly once per execution, so accumulation is correct (no double-counting).

However, if streaming mode were activated (e.g., by passing a large DataFrame accidentally), `_process()` would be called once per chunk, and stats would accumulate: NB_LINE=N, NB_LINE_OK=N for N chunks. This is incorrect for a utility component.

### `validate_schema()` Relevance

`FileCopy` never calls `validate_schema()` because it does not produce a DataFrame. The method is available (inherited from `BaseComponent`) but unused. This is correct behavior for a utility component.

---

## Appendix N: Comparison with Talend Java Code Generation

### Talend Generated Java Code for tFileCopy (simplified)

When Talend generates Java code for a tFileCopy component, it produces approximately the following pattern:

```java
// tFileCopy_1 main code
String src_tFileCopy_1 = context.sourceDir + "/" + context.fileName;
String dest_dir_tFileCopy_1 = context.destDir;
boolean rename_tFileCopy_1 = false;
String newName_tFileCopy_1 = "";
boolean removeSource_tFileCopy_1 = true;  // move mode
boolean replace_tFileCopy_1 = true;
boolean createDir_tFileCopy_1 = true;

java.io.File src_file_tFileCopy_1 = new java.io.File(src_tFileCopy_1);
java.io.File dest_file_tFileCopy_1;

if (createDir_tFileCopy_1) {
    new java.io.File(dest_dir_tFileCopy_1).mkdirs();
}

if (rename_tFileCopy_1 && newName_tFileCopy_1.length() > 0) {
    dest_file_tFileCopy_1 = new java.io.File(dest_dir_tFileCopy_1, newName_tFileCopy_1);
} else {
    dest_file_tFileCopy_1 = new java.io.File(dest_dir_tFileCopy_1, src_file_tFileCopy_1.getName());
}

if (dest_file_tFileCopy_1.exists() && !replace_tFileCopy_1) {
    throw new RuntimeException("Destination file exists: " + dest_file_tFileCopy_1.getPath());
}

// Copy the file
java.nio.file.Files.copy(
    src_file_tFileCopy_1.toPath(),
    dest_file_tFileCopy_1.toPath(),
    java.nio.file.StandardCopyOption.REPLACE_EXISTING
);

// Preserve last modified time
if (preserveLastModified_tFileCopy_1) {
    dest_file_tFileCopy_1.setLastModified(src_file_tFileCopy_1.lastModified());
}

// Remove source (move mode)
if (removeSource_tFileCopy_1) {
    src_file_tFileCopy_1.delete();
}

// Set global variables
globalMap.put("tFileCopy_1_DESTINATION_FILENAME", dest_file_tFileCopy_1.getName());
globalMap.put("tFileCopy_1_DESTINATION_FILEPATH", dest_file_tFileCopy_1.getPath());
globalMap.put("tFileCopy_1_SOURCE_DIRECTORY", src_file_tFileCopy_1.getParent());
globalMap.put("tFileCopy_1_DESTINATION_DIRECTORY", dest_dir_tFileCopy_1);
```

### Key Differences from V1 Engine

| Aspect | Talend Java | V1 Python Engine | Impact |
|--------|-------------|------------------|--------|
| File copy method | `Files.copy()` | `shutil.copy2()` / `shutil.copy()` | `copy2` always preserves metadata; Java's `Files.copy()` only with explicit options |
| Destination path computation | Always includes source filename (`new File(dir, name)`) | When not renaming, destination = directory (not file) | BUG-FCP-003: replace_file check is wrong |
| Remove source | `file.delete()` after copy | Not implemented | Move semantics missing |
| GlobalMap variables | Set after each operation | Not set | Downstream references fail |
| Error handling | Throws RuntimeException | Catch-all swallows | Different error propagation |
| Default replace_file | `false` (depends on job) | `True` | Inverted -- data loss risk |
| Default create_directory | `false` (depends on job) | `True` | Inverted -- masks errors |
| Preserve timestamps | Explicit `setLastModified()` | `copy2()` implicit | `copy2` always preserves even when not requested |

---

## Appendix O: Interaction with tFileList Iterator Pattern

### Common Talend Pattern

The most common production usage of tFileCopy is in combination with tFileList:

```
[tFileList_1] --(iterate)--> [tFileCopy_1] --(OnComponentOk)--> [tLogRow_1]
```

Where:
- `tFileList_1` iterates over files in a source directory
- `tFileCopy_1.FILENAME` = `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`
- `tFileCopy_1.DESTINATION` = `context.archiveDir`
- `tFileCopy_1.REMOVE_SOURCE_FILE` = `true` (move to archive)
- `tLogRow_1` logs the globalMap variable `tFileCopy_1_DESTINATION_FILEPATH`

### V1 Engine Challenges for This Pattern

1. **Java expression in FILENAME**: The globalMap.get expression is a Java cast expression that requires the Java bridge for resolution. If the Java bridge is not configured, the expression remains as a literal string, causing `FileNotFoundError`.

2. **Iterate connection**: The v1 engine must support the Iterate connection type from tFileList to tFileCopy. The iterate connection means tFileCopy's `_process()` is called once per iteration of tFileList. The engine must set the `tFileList_1_CURRENT_FILEPATH` globalMap variable before each tFileCopy execution.

3. **Missing REMOVE_SOURCE_FILE**: Even if the pattern above is converted and executed, the source files are never moved -- only copied. The "process and archive" pattern breaks.

4. **Missing DESTINATION_FILEPATH**: The tLogRow after tFileCopy cannot log the destination path because `tFileCopy_1_DESTINATION_FILEPATH` is never set in globalMap.

5. **Error propagation**: If one file copy fails (e.g., permissions error), the catch-all swallows the error. The iterate loop continues, potentially processing more files. In Talend, the error would trigger `COMPONENT_ERROR`, which could be configured to stop the iteration.

### Recommended V1 Engine Flow for Iterator Pattern

```
Engine loop:
    for each file from tFileList:
        global_map.put("tFileList_1_CURRENT_FILEPATH", current_file)
        global_map.put("tFileList_1_CURRENT_FILEDIRECTORY", os.path.dirname(current_file))
        global_map.put("tFileList_1_CURRENT_FILE", os.path.basename(current_file))

        resolve Java expressions in tFileCopy config
        execute tFileCopy._process()

        if success:
            execute OnComponentOk triggers
        else:
            execute OnComponentError triggers
            if die_on_error: break
```

---

## Appendix P: Summary of All Default Value Mismatches

| Config Key | Converter Default | Engine Default | Talend Default | Severity | Fix |
|------------|------------------|----------------|----------------|----------|-----|
| `replace_file` | `True` (line 282) | `True` (line 71) | `false` | **High** -- silent data overwrite | Change both to `False` |
| `create_directory` | `True` (line 283) | `True` (line 72) | `false` | **Medium** -- masks config errors | Change both to `False` |
| `rename` | `False` (line 280) | `False` (line 69) | `false` | None -- matches | No change |
| `preserve_last_modified` | `False` (line 284) | `False` (line 73) | `false` | None -- matches | No change |
| `remove_source_file` | Not extracted | Not read | `false` | **High** -- feature missing | Add extraction and handling |

---
