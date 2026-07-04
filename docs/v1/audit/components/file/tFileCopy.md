# Audit Report: tFileCopy / FileCopy

> **Audited**: 2026-04-04
> **Re-audited**: 2026-04-29 (engine remediation)
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: REMEDIATED -- engine rewritten to ENGINE_COMPONENT_PATTERN.md gold standard
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 0. 2026-04-29 Re-audit Summary (Engine Remediation)

Engine rewrite at `src/v1/engine/components/file/file_copy.py` brings the
component to gold-standard compliance and implements all 5 missing
features.

| Issue | Status | Resolution |
| ----- | ------ | ---------- |
| ~~BUG-FC P0 (`_update_global_map` crash)~~ | **FIXED** | Cross-cutting fix already in `base_component.py:617` (verified) |
| ~~ENG-FC-001 (P1, source key mismatch)~~ | **FIXED** | Engine reads `filename` (converter key) with legacy `source` fallback |
| ~~ENG-FC-002 (P1, rename key mismatch)~~ | **FIXED** | Engine reads `destination_rename` with legacy `new_name` fallback |
| ~~ENG-FC-003 (P1, preserve mtime key mismatch)~~ | **FIXED** | Engine reads `preserve_last_modified_time` with legacy `preserve_last_modified` fallback |
| ~~ENG-FC-004 (P2, REMOVE_FILE missing)~~ | **FIXED** | `remove_file` deletes source after successful copy (move semantics) |
| ~~ENG-FC-005 (P2, FAILON missing)~~ | **FIXED** | `failon` raises `FileOperationError` on failure; `failon=False` returns error dict (when `die_on_error=False`) |
| ~~Needs-review #4 (enable_copy_directory)~~ | **FIXED** | Read and used to switch to directory-copy mode |
| ~~Needs-review #5 (source_derectory typo)~~ | **FIXED** | Read with the Talend typo preserved; `source_directory` accepted as alias |
| ~~Needs-review #8 (force_copy_delete)~~ | **FIXED** | Implemented; tolerates source-removal failure when set |
| ~~Code-Quality P1 (no `_validate_config`)~~ | **FIXED** | Raises `ConfigurationError` for missing source/destination/bad bool types |
| ~~Code-Quality P2 (f-string in logger)~~ | **FIXED** | %-formatting throughout |
| ~~Code-Quality P2 (bare except)~~ | **FIXED** | Narrowed to `OSError` / `FileOperationError` |
| ~~Code-Quality P3 (unused typing import)~~ | **FIXED** | Imports trimmed |
| ~~Testing P2 gap~~ | **FIXED** | New `tests/v1/engine/components/file/test_file_copy.py` (9 classes, 17 tests, all passing) |

**Other improvements**:
- Added `@REGISTRY.register("FileCopy", "tFileCopy")` (Rule 9)
- Module docstring with full 12-key Config Mapping table (Rule 1)
- Replaced bare `ValueError` / `FileNotFoundError` / `FileExistsError` with `ConfigurationError` / `FileOperationError` (Rule 7)
- Returns `{"main": ..., "reject": None}` (Rule 3)

**New Overall: GREEN**. Updated scorecard: P0=0 / P1=0 / P2=0 / P3=0.

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileCopy` |
| **V1 Engine Class** | `FileCopy` |
| **Engine File** | `src/v1/engine/components/file/file_copy.py` (133 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_copy.py` (116 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileCopy")` decorator-based dispatch |
| **Registry Aliases** | `FileCopy`, `tFileCopy` |
| **Category** | File / Utility |
| **Complexity** | Medium -- utility component with 12 unique parameters, no data flow schema, directory copy mode |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_copy.py` | Engine implementation (133 lines) |
| `src/converters/talend_to_v1/components/file/file_copy.py` | Converter class (116 lines) |
| `tests/converters/talend_to_v1/components/test_file_copy.py` | Converter tests (44 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 12 unique params + 2 framework params extracted; `_build_component_dict` pattern; 8 per-feature needs_review entries for engine gaps |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 0 | 3 config key mismatches (filename/source, destination_rename/new_name, preserve_last_modified_time/preserve_last_modified); 5 params not implemented in engine (enable_copy_directory, source_derectory, remove_file, failon, force_copy_delete) |
| Code Quality | **Y** | 1 | 1 | 2 | 1 | Cross-cutting `_update_global_map()` crash (P0); no `_validate_config()` (P1); f-string in logger (P2); bare except (P2); unused import typing (P3) |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Minimal -- single file/directory copy operation; shutil.copytree for directory copy |
| Testing | **Y** | 0 | 0 | 1 | 0 | 44 converter unit tests across 10 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) |

**Overall: Yellow -- Converter fully standardized (Green); engine has config key mismatches and 5 unimplemented params documented via 8 needs_review entries; engine/code quality gaps keep overall at Yellow**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Align engine config keys with converter output (P1, 3 key mismatches)
3. Implement missing engine features: enable_copy_directory, source_derectory, remove_file, failon, force_copy_delete (P1)
4. Add engine unit tests for FileCopy (P2, testing gap)
5. Replace f-string in logger calls with % formatting (P2, code quality)

---

## 3. Talend Feature Baseline

### What tFileCopy Does

`tFileCopy` copies files or directories from a source path to a destination path. It supports renaming during copy, replacing existing files, creating destination directories, moving files (copy + delete source), and preserving file timestamps. It can operate in file mode (single file) or directory mode (entire directory tree).

The component has 12 unique parameters controlling file/directory paths, rename behavior, replace/overwrite policy, directory creation, error handling, and move semantics (copy + delete source via REMOVE_FILE and FORCE_COPY_DELETE). Note: the _java.xml contains a typo `SOURCE_DERECTORY` (missing "I" in DIRECTORY) which is preserved in the converter.

**Source**: [tFileCopy Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfilecopy/tfilecopy-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileCopy/tFileCopy_java.xml)
**Component family**: File / Utility
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | File Name | `FILENAME` | FILE | `""` | Source file path. Supports context variables and Java expressions. |
| 2 | Enable Copy Directory | `ENABLE_COPY_DIRECTORY` | CHECK | `false` | When checked, switches to directory copy mode using SOURCE_DERECTORY instead of FILENAME. |
| 3 | Source Directory | `SOURCE_DERECTORY` | DIRECTORY | `""` | Source directory path when ENABLE_COPY_DIRECTORY is enabled. Note: Talend typo "DERECTORY" preserved. |
| 4 | Destination | `DESTINATION` | DIRECTORY | `""` | Destination directory path. |
| 5 | Rename | `RENAME` | CHECK | `false` | When checked, renames the copied file to DESTINATION_RENAME. |
| 6 | Destination Rename | `DESTINATION_RENAME` | TEXT | `"NewName.temp"` | New filename when RENAME is enabled. |
| 7 | Remove Source File | `REMOVE_FILE` | CHECK | `false` | When checked, deletes the source file after successful copy (move semantics). Note: _java.xml name is REMOVE_FILE, not REMOVE_SOURCE_FILE. |
| 8 | Replace Existing File | `REPLACE_FILE` | CHECK | `true` | When checked, overwrites existing file at destination. Default is `true` per _java.xml. |
| 9 | Create Directory | `CREATE_DIRECTORY` | CHECK | `true` | When checked, creates destination directory if it does not exist. Default is `true` per _java.xml. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 10 | Fail On Error | `FAILON` | CHECK | `false` | When checked, throws exception on copy failure instead of continuing. |
| 11 | Force Copy Delete | `FORCE_COPY_DELETE` | CHECK | `false` | When checked, forces delete of source after copy even if copy was partial. Used with REMOVE_FILE for robust move semantics. |
| 12 | Preserve Last Modified Time | `PRESERVE_LAST_MODIFIED_TIME` | CHECK | `false` | When checked, preserves the source file's last modified timestamp on the destination copy. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enables collection of processing metadata for tStatCatcher. |
| 14 | Label | `LABEL` | TEXT | `""` | Text label for the component on the designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `ITERATE` | Input | Iterate | Enables iterative execution when connected from tFileList or tFlowToIterate. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of copy operations attempted (always 1). |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of successful copy operations. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of failed copy operations. |
| `{id}_ERROR_MESSAGE` | String | After error | Error message when the copy operation fails. |

### 3.5 Behavioral Notes

1. **REPLACE_FILE default is `true` per _java.xml**: The old converter incorrectly used `False`. The _java.xml definition specifies `REPLACE_FILE` as CHECK type with `DEFAULT="true"`.
2. **CREATE_DIRECTORY default is `true` per _java.xml**: The old converter incorrectly used `False`. The _java.xml definition specifies `CREATE_DIRECTORY` as CHECK type with `DEFAULT="true"`.
3. **REMOVE_FILE, not REMOVE_SOURCE_FILE**: The _java.xml parameter name is `REMOVE_FILE`, not `REMOVE_SOURCE_FILE`. The old converter used the wrong name.
4. **ENABLE_COPY_DIRECTORY, not COPY_DIRECTORY**: The _java.xml parameter name is `ENABLE_COPY_DIRECTORY`, not `COPY_DIRECTORY`. The old converter used the wrong name.
5. **SOURCE_DERECTORY Talend typo**: The _java.xml contains `SOURCE_DERECTORY` (missing "I" in DIRECTORY). This typo is preserved in the converter as the source of truth.
6. **Move semantics**: Setting REMOVE_FILE=true with FORCE_COPY_DELETE=true provides robust move semantics (copy then delete source).
7. **No schema**: tFileCopy is a pure utility component with no data flow. It does not process rows of data. Both input and output schemas are empty.
8. **Dynamic paths**: FILENAME, SOURCE_DERECTORY, and DESTINATION support context variables and Java expressions.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated `FileCopyConverter` class registered via `@REGISTRY.register("tFileCopy")`. It extracts all 12 unique parameters plus 2 framework parameters using safe `_get_str()` / `_get_bool()` helpers. The converter follows the gold standard pattern with `_build_component_dict()` wrapper.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILENAME` | Yes | `filename` | `_get_str()`, default `""` |
| 2 | `ENABLE_COPY_DIRECTORY` | Yes | `enable_copy_directory` | `_get_bool()`, default `False` |
| 3 | `SOURCE_DERECTORY` | Yes | `source_derectory` | `_get_str()`, default `""` -- Talend typo preserved |
| 4 | `DESTINATION` | Yes | `destination` | `_get_str()`, default `""` |
| 5 | `RENAME` | Yes | `rename` | `_get_bool()`, default `False` |
| 6 | `DESTINATION_RENAME` | Yes | `destination_rename` | `_get_str()`, default `"NewName.temp"` |
| 7 | `REMOVE_FILE` | Yes | `remove_file` | `_get_bool()`, default `False` |
| 8 | `REPLACE_FILE` | Yes | `replace_file` | `_get_bool()`, default `True` per _java.xml |
| 9 | `CREATE_DIRECTORY` | Yes | `create_directory` | `_get_bool()`, default `True` per _java.xml |
| 10 | `FAILON` | Yes | `failon` | `_get_bool()`, default `False` |
| 11 | `FORCE_COPY_DELETE` | Yes | `force_copy_delete` | `_get_bool()`, default `False` |
| 12 | `PRESERVE_LAST_MODIFIED_TIME` | Yes | `preserve_last_modified_time` | `_get_bool()`, default `False` |
| 13 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default `False` |
| 14 | `LABEL` | Yes | `label` | Framework param, default `""` |

**Summary**: 14 of 14 parameters extracted (100%).

### 4.2 Schema Extraction

Not applicable -- tFileCopy is a utility component with no data flow schema. Schema is set to `{"input": [], "output": []}`.

### 4.3 Expression Handling

FILENAME, SOURCE_DERECTORY, DESTINATION, and DESTINATION_RENAME support context variables and Java expressions. The converter passes values through `_get_str()` which strips surrounding quotes. Expression resolution (`context.var`, `{{java}}`) happens at engine runtime, not converter time.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-FC-001 | ~~P1~~ | **FIXED** -- Old converter used wrong param name `REMOVE_SOURCE_FILE` instead of `REMOVE_FILE` per _java.xml |
| CONV-FC-002 | ~~P1~~ | **FIXED** -- Old converter used wrong param name `COPY_DIRECTORY` instead of `ENABLE_COPY_DIRECTORY` per _java.xml |
| CONV-FC-003 | ~~P1~~ | **FIXED** -- Old converter used wrong param name `SOURCE_DIRECTORY` instead of `SOURCE_DERECTORY` (Talend typo) |
| CONV-FC-004 | ~~P1~~ | **FIXED** -- Old converter defaulted `REPLACE_FILE` to `False` but _java.xml says `True` |
| CONV-FC-005 | ~~P1~~ | **FIXED** -- Old converter defaulted `CREATE_DIRECTORY` to `False` but _java.xml says `True` |
| CONV-FC-006 | ~~P1~~ | **FIXED** -- Old converter was missing `FAILON` parameter entirely |
| CONV-FC-007 | ~~P1~~ | **FIXED** -- Old converter was missing `FORCE_COPY_DELETE` parameter entirely |
| CONV-FC-008 | ~~P1~~ | **FIXED** -- Old converter was missing `ENABLE_COPY_DIRECTORY` parameter entirely |
| CONV-FC-009 | ~~P1~~ | **FIXED** -- Old converter was missing `SOURCE_DERECTORY` parameter entirely |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `filename` | Engine reads `source` but converter outputs `filename` per _java.xml param name FILENAME | engine_gap |
| 2 | `destination_rename` | Engine reads `new_name` but converter outputs `destination_rename` per _java.xml param name DESTINATION_RENAME | engine_gap |
| 3 | `preserve_last_modified_time` | Engine reads `preserve_last_modified` but converter outputs `preserve_last_modified_time` per _java.xml param name PRESERVE_LAST_MODIFIED_TIME | engine_gap |
| 4 | `enable_copy_directory` | Engine does not read this key -- not implemented in engine | engine_gap |
| 5 | `source_derectory` | Engine does not read this key -- not implemented in engine | engine_gap |
| 6 | `remove_file` | Engine does not read this key -- not implemented in engine | engine_gap |
| 7 | `failon` | Engine does not read this key -- not implemented in engine | engine_gap |
| 8 | `force_copy_delete` | Engine does not read this key -- not implemented in engine | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File copy | **Yes** | High | `_process()` line 114 | Uses `shutil.copy2()` for single file copy |
| 2 | Directory copy | **Partial** | Medium | `_process()` line 111 | Uses `shutil.copytree()` with `dirs_exist_ok` but no ENABLE_COPY_DIRECTORY toggle |
| 3 | Rename during copy | **Yes** | High | `_process()` line 99 | Joins destination + new_name |
| 4 | Replace existing | **Yes** | High | `_process()` line 103 | Checks `os.path.exists()` + `replace_file` flag |
| 5 | Create directory | **Yes** | High | `_process()` line 93 | `os.makedirs()` when `create_directory=True` |
| 6 | Preserve last modified | **Yes** | High | `_process()` line 118 | `shutil.copystat()` |
| 7 | Remove source file | **No** | N/A | Not implemented | Engine has no move/delete-source support |
| 8 | Fail on error | **No** | N/A | Not implemented | Engine catches all exceptions in broad except block |
| 9 | Force copy delete | **No** | N/A | Not implemented | Engine has no robust move support |
| 10 | Enable copy directory | **No** | N/A | Not implemented | Engine auto-detects via `os.path.isdir()` but no explicit toggle |
| 11 | Source directory | **No** | N/A | Not implemented | Engine only reads `source` config key |
| 12 | Statistics tracking | **Yes** | High | `_process()` line 122 | `_update_stats()` for NB_LINE, NB_LINE_OK, NB_LINE_REJECT |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FC-001 | **P1** | Engine reads `source` config key but converter outputs `filename` per _java.xml. Config key mismatch means engine receives empty string when user sets FILENAME in Talend. |
| ENG-FC-002 | **P1** | Engine reads `new_name` config key but converter outputs `destination_rename` per _java.xml. Rename feature broken due to key mismatch. |
| ENG-FC-003 | **P1** | Engine reads `preserve_last_modified` config key but converter outputs `preserve_last_modified_time` per _java.xml. Timestamp preservation broken due to key mismatch. |
| ENG-FC-004 | **P2** | Engine does not implement REMOVE_FILE (move/delete-source semantics). No equivalent of Talend's "move file" functionality. |
| ENG-FC-005 | **P2** | Engine does not implement FAILON. All errors caught in broad except block regardless of setting. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` via base class | Always 1 |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | 1 on success, 0 on failure |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | 0 on success, 1 on failure |
| `{id}_ERROR_MESSAGE` | Yes | No | Not implemented | P2 gap -- error message not written to globalMap |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FC-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` references undefined `value` variable. Crashes all components when globalMap is set. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FC-001 | **P1** | Engine uses `source` config key; converter uses `filename` per _java.xml. Needs alignment. |
| NAME-FC-002 | **P1** | Engine uses `new_name` config key; converter uses `destination_rename` per _java.xml. Needs alignment. |
| NAME-FC-003 | **P2** | Engine uses `preserve_last_modified` config key; converter uses `preserve_last_modified_time` per _java.xml. Needs alignment. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FC-001 | **P2** | "Use %-formatting in logger calls" | Uses f-strings: `logger.info(f"[{self.id}] Copy operation started: {source} -> {destination}")` |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified for standard file copy use. File paths come from configuration, not user input. Engine uses `shutil.copy2` and `shutil.copytree` which are standard library functions.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logging.getLogger(__name__)` |
| Level usage | Adequate -- info for start/complete, debug for operations, error for failures |
| Sensitive data | OK -- file paths logged but not sensitive in ETL context |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses ValueError/FileNotFoundError/FileExistsError directly, no custom exception hierarchy |
| Exception chaining | Not used |
| die_on_error handling | Not implemented -- broad except catches all errors |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `_process()` has return type `Dict[str, Any]` |
| Parameter types | Good -- `input_data: Optional[Dict[str, Any]]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FC-001 | **P3** | Return value wraps result in dict -- minor overhead but consistent with base class pattern |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- utility component, no data flow |
| Memory threshold | N/A -- single file/directory operation |
| Large data handling | shutil.copytree for directory copy handles large directory trees efficiently using OS-level copy |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 44 | `tests/converters/talend_to_v1/components/test_file_copy.py` |
| Engine unit tests | 17 | `tests/v1/engine/components/file/test_file_copy.py` (9 classes, added 2026-04-29) |
| Integration tests | Shared | `tests/converters/talend_to_v1/test_integration.py` |

**Phase 14-08 note**: Per-module coverage floor lifted to >=95% (Phase 14 gate). Engine unit tests were added in the 2026-04-29 re-audit. [RESOLVED in Phase 14-08]

### 8.2 Test Gaps

~~TEST-FC-001 (P2) -- No engine unit tests for FileCopy.~~ [RESOLVED in Phase 14-08]

### 8.3 Recommended Test Cases

1. Engine: file copy to existing destination with replace_file=True/False
2. Engine: directory copy with shutil.copytree
3. Engine: rename during copy with new_name
4. Engine: create directory when destination missing and create_directory=True
5. Engine: failure when destination exists and replace_file=False
6. Engine: empty source/destination raises ValueError
7. Engine: preserve_last_modified timestamp verification
8. Engine: source file does not exist raises FileNotFoundError

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-FC-001** (cross-cutting) |
| P1 | 5 | **ENG-FC-001**, **ENG-FC-002**, **ENG-FC-003**, **NAME-FC-001**, **NAME-FC-002** |
| P2 | 5 | **ENG-FC-004**, **ENG-FC-005**, **NAME-FC-003**, **STD-FC-001**, **TEST-FC-001** |
| P3 | 1 | **PERF-FC-001** |
| **Total** | **12** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 5 | ENG-FC-001, ENG-FC-002, ENG-FC-003, ENG-FC-004, ENG-FC-005 |
| Bug (BUG) | 1 | BUG-FC-001 |
| Naming (NAME) | 3 | NAME-FC-001, NAME-FC-002, NAME-FC-003 |
| Standards (STD) | 1 | STD-FC-001 |
| Testing (TEST) | 1 | TEST-FC-001 |
| Performance (PERF) | 1 | PERF-FC-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- statistics lost |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-FC-001** (P0): Fix `_update_global_map()` crash in base class -- affects all components

### Short-term (Hardening)

1. **ENG-FC-001/002/003** (P1): Align engine config keys with converter output (source->filename, new_name->destination_rename, preserve_last_modified->preserve_last_modified_time)
2. **NAME-FC-001/002** (P1): Part of engine key alignment
3. Implement REMOVE_FILE support for move semantics (P2)
4. Implement FAILON error behavior (P2)

### Long-term (Optimization)

1. **TEST-FC-001** (P2): Add engine unit tests for FileCopy
2. **STD-FC-001** (P2): Replace f-strings in logger calls with % formatting
3. Implement ENABLE_COPY_DIRECTORY, SOURCE_DERECTORY, FORCE_COPY_DELETE engine features
4. **PERF-FC-001** (P3): Minor -- no action needed

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talend 7.3 docs | <https://help.qlik.com/talend/en-US/components/7.3/tfilecopy/tfilecopy-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileCopy/tFileCopy_java.xml> | Component definition XML, correct param names and defaults |
| Engine source | `src/v1/engine/components/file/file_copy.py` | Feature parity analysis (133 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_copy.py` | Converter audit (116 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_copy.py` | Test coverage (44 tests) |

## Appendix B: Engine Config Key Mapping

| _java.xml Parameter | Converter Config Key | Engine Config Key | Match? | Notes |
| --------------------- | --------------------- | ------------------- | -------- | ------- |
| `FILENAME` | `filename` | `source` | **No** | Engine gap -- engine reads `source`, converter outputs `filename` |
| `ENABLE_COPY_DIRECTORY` | `enable_copy_directory` | N/A | **No** | Engine does not implement -- auto-detects via `os.path.isdir()` |
| `SOURCE_DERECTORY` | `source_derectory` | N/A | **No** | Engine does not implement |
| `DESTINATION` | `destination` | `destination` | Yes | Both use same key |
| `RENAME` | `rename` | `rename` | Yes | Both use same key |
| `DESTINATION_RENAME` | `destination_rename` | `new_name` | **No** | Engine gap -- engine reads `new_name`, converter outputs `destination_rename` |
| `REMOVE_FILE` | `remove_file` | N/A | **No** | Engine does not implement |
| `REPLACE_FILE` | `replace_file` | `replace_file` | Yes | Both use same key |
| `CREATE_DIRECTORY` | `create_directory` | `create_directory` | Yes | Both use same key |
| `FAILON` | `failon` | N/A | **No** | Engine does not implement |
| `FORCE_COPY_DELETE` | `force_copy_delete` | N/A | **No** | Engine does not implement |
| `PRESERVE_LAST_MODIFIED_TIME` | `preserve_last_modified_time` | `preserve_last_modified` | **No** | Engine gap -- engine reads `preserve_last_modified`, converter outputs `preserve_last_modified_time` |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 after Phase 15.1 reconciliation*
