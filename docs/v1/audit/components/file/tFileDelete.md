# Audit Report: tFileDelete / FileDelete

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
| **Talend Name** | `tFileDelete` |
| **V1 Engine Class** | `FileDelete` |
| **Engine File** | `src/v1/engine/components/file/file_delete.py` (175 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_delete.py` (82 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileDelete")` decorator-based dispatch |
| **Registry Aliases** | `FileDelete`, `tFileDelete` |
| **Category** | File / Utility |
| **Complexity** | Low-Medium -- utility component with 6 unique parameters, 3 deletion modes, no data flow schema |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_delete.py` | Engine implementation (175 lines) |
| `src/converters/talend_to_v1/components/file/file_delete.py` | Converter class (82 lines) |
| `tests/converters/talend_to_v1/components/test_file_delete.py` | Converter tests (31 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 6 unique params + 2 framework params extracted; `_build_component_dict` pattern; 5 per-feature needs_review entries for engine gaps |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | Engine uses different config key names (path vs filename, fail_on_error vs failon, is_directory vs folder, is_folder_file vs folder_file); engine has `recursive` param not in _java.xml; no DELETE_PATH globalMap variable |
| Code Quality | **Y** | 1 | 2 | 2 | 1 | Cross-cutting `_update_global_map()` crash (P0); dead `_validate_config()` (P1); no path sanitization (P1); f-string in logger (P2); empty string path accepted (P2); redundant os.path checks (P3) |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Minimal -- single file/directory deletion; no memory concerns; minor redundant path existence checks (P3) |
| Testing | **Y** | 0 | 0 | 1 | 0 | 31 converter unit tests across 10 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) |

**Overall: Yellow -- Converter fully standardized (Green); engine has config key mismatches documented via 5 needs_review entries; engine/code quality gaps keep overall at Yellow**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Align engine config keys with converter output (P1, engine gaps: failon/fail_on_error, folder/is_directory, folder_file/is_folder_file)
3. Implement `_validate_config()` or remove dead code (P1, code quality)
4. Add path sanitization to prevent path traversal (P1, code quality)
5. Add engine unit tests for FileDelete (P2, testing gap)

---

## 3. Talend Feature Baseline

### What tFileDelete Does

`tFileDelete` deletes files or directories from the filesystem. It is a utility component in the File family, commonly used in pre-job cleanup (deleting output files before a fresh write), post-job cleanup (removing temporary files), and iterative file processing (combined with `tFileList` to delete files matching a pattern).

The component supports three deletion modes controlled by two checkboxes: file-only deletion (default), directory-only deletion (FOLDER=true), and auto-detect file-or-directory deletion (FOLDER_FILE=true). Each mode shows a different path input field. The component does not produce data flow output -- it is a standalone utility.

**Source**: [tFileDelete Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfiledelete/tfiledelete-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileDelete/tFileDelete_java.xml)
**Component family**: File / Utility
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in, uses `java.io.File`)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | File Name | `FILENAME` | FILE | `""` | **Mandatory** (in default mode). Absolute path of the file to delete. Hidden when FOLDER or FOLDER_FILE is selected. Supports context variables and Java expressions. |
| 2 | Directory | `DIRECTORY` | DIRECTORY | `""` | **Mandatory** (when FOLDER=true). Absolute path of the directory to delete. Only visible when "Delete folder" checkbox is selected. |
| 3 | File or directory to delete | `PATH` | TEXT | `""` | **Mandatory** (when FOLDER_FILE=true). Path to the file or directory, whichever exists. Only visible when "Delete file or folder" checkbox is selected. |
| 4 | Fail on error | `FAILON` | CHECK | `true` | When checked, prevents subsequent job execution if deletion fails. When unchecked, errors are suppressed and the job continues. **CRITICAL: Default is `true` per _java.xml.** |
| 5 | Delete folder | `FOLDER` | CHECK | `false` | When checked, displays the "Directory" field instead of "File Name". Switches to directory deletion mode. |
| 6 | Delete file or folder | `FOLDER_FILE` | CHECK | `false` | When checked, displays "File or directory to delete" field. Attempts to delete whatever exists at the path. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 7 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enables collection of processing metadata for tStatCatcher. |
| 8 | Label | `LABEL` | TEXT | `""` | Text label for the component on the designer canvas. No runtime impact. |

**Note:** The _java.xml also contains a `NOTE` parameter of LABEL type (display-only informational text). This is not a configurable parameter and is correctly excluded from the converter.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `ITERATE` | Input | Iterate | Enables iterative deletion when connected from tFileList or tFlowToIterate. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_DELETE_PATH` | String | After execution | Path of the deleted file/directory. Not implemented in v1 engine. |
| `{id}_CURRENT_STATUS` | String | After execution | "deleted" or "not exist". Not implemented in v1 engine. |
| `{id}_ERROR_MESSAGE` | String | After error | Error message when deletion fails. |

### 3.5 Behavioral Notes

1. **Three deletion modes**: The component operates in one of three mutually exclusive modes controlled by the FOLDER and FOLDER_FILE checkboxes. Default mode deletes a file (FILENAME). FOLDER mode deletes a directory (DIRECTORY). FOLDER_FILE mode auto-detects whether the path is a file or directory (PATH).
2. **FAILON default is `true` per _java.xml**: The _java.xml definition specifies FAILON as CHECK with DEFAULT="true". This means by default, deletion failure halts the job. The old converter incorrectly used `false`.
3. **PATH is the _java.xml name**: The FOLDER_FILE mode path parameter is named `PATH` in _java.xml, not `FOLDER_FILE_PATH` as the old converter assumed.
4. **No schema**: tFileDelete is a pure utility component with no data flow. Both input and output schemas are empty.
5. **No RECURSIVE parameter in _java.xml**: The engine has a `recursive` config key, but _java.xml does not expose a RECURSIVE parameter. In Talend, directory deletion implicitly includes contents.
6. **Dynamic paths**: All path parameters support context variables, globalMap references, and Java expressions. Commonly used with tFileList iteration.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated `FileDeleteConverter` class registered via `@REGISTRY.register("tFileDelete")`. It extracts all 6 unique parameters plus 2 framework parameters using safe `_get_str()` / `_get_bool()` helpers. The converter follows the gold standard pattern with `_build_component_dict()` wrapper.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILENAME` | Yes | `filename` | String, default `""`. Quotes stripped by `_get_str()`. |
| 2 | `DIRECTORY` | Yes | `directory` | String, default `""`. Quotes stripped by `_get_str()`. |
| 3 | `PATH` | Yes | `path` | String, default `""`. FOLDER_FILE mode path param. Quotes stripped. |
| 4 | `FAILON` | Yes | `failon` | Boolean, default `True`. **CRITICAL fix**: was `False` via phantom `FAIL_ON_ERROR`. |
| 5 | `FOLDER` | Yes | `folder` | Boolean, default `False`. Directory deletion mode switch. |
| 6 | `FOLDER_FILE` | Yes | `folder_file` | Boolean, default `False`. Auto-detect mode switch. |
| 7 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, boolean, default `False`. |
| 8 | `LABEL` | Yes | `label` | Framework param, string, default `""`. |

**Summary**: 8 of 8 parameters extracted (100%). Correct _java.xml param names used. Phantom params FAIL_ON_ERROR and FOLDER_FILE_PATH removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| N/A | N/A | Utility component per D-56 -- no data flow schema. Both `input` and `output` are empty arrays. |

### 4.3 Expression Handling

All string parameters (`filename`, `directory`, `path`) are extracted as-is after quote stripping. Context variables (`context.var`) and Java expressions (`{{java}}`) are preserved in the string value for the engine to resolve at runtime.

### 4.4 Converter Issues

All previous converter issues have been resolved in the gold-standard rewrite:

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-DEL-001 | ~~P1~~ | **FIXED** -- Was extracting `FAIL_ON_ERROR` (phantom param); now uses `FAILON` per _java.xml |
| CONV-DEL-002 | ~~P1~~ | **FIXED** -- Was extracting `FOLDER_FILE_PATH` (phantom param); now uses `PATH` per _java.xml |
| CONV-DEL-003 | ~~P1~~ | **FIXED** -- FAILON default was `False`; now `True` per _java.xml |
| CONV-DEL-004 | ~~P2~~ | **FIXED** -- Now uses `_build_component_dict()` per D-40 (was flat dict) |

### 4.5 Needs Review Entries

The converter emits 5 per-feature engine gap needs_review entries:

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `failon` | Engine reads `fail_on_error` (default True) but converter outputs `failon` per _java.xml param FAILON | engine_gap |
| 2 | `folder` | Engine reads `is_directory` but converter outputs `folder` per _java.xml param FOLDER | engine_gap |
| 3 | `folder_file` | Engine reads `is_folder_file` but converter outputs `folder_file` per _java.xml param FOLDER_FILE | engine_gap |
| 4 | `filename` | Engine reads `path` for all modes but converter outputs `filename`/`directory`/`path` per _java.xml | engine_gap |
| 5 | `recursive` | Engine reads `recursive` config key but no RECURSIVE param exists in _java.xml | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File deletion | **Yes** | High | `_process()` line 117-125 | Standard `os.remove()` for files |
| 2 | Directory deletion | **Yes** | High | `_process()` line 104-115 | Uses `os.rmdir()` (empty) or `shutil.rmtree()` (recursive) |
| 3 | Auto-detect mode (FOLDER_FILE) | **Yes** | Medium | `_process()` line 86-102 | Checks `os.path.isfile()` then `os.path.isdir()` |
| 4 | Fail on error | **Yes** | High | `_process()` line 135-140 | Catches exception, re-raises if `fail_on_error=True` |
| 5 | Statistics tracking | **Yes** | High | `_process()` line 128-131 | `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` via `_update_stats()` |
| 6 | Recursive deletion | **Yes** | N/A | `_process()` lines 96, 109 | Uses `shutil.rmtree()` -- but no _java.xml RECURSIVE param |
| 7 | DELETE_PATH globalMap | **No** | N/A | -- | Not set after deletion; Talend sets `{id}_DELETE_PATH` |
| 8 | CURRENT_STATUS globalMap | **No** | N/A | -- | Not set; Talend sets "deleted" or "not exist" |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-DEL-001 | **P1** | Engine reads `path` as single config key for all modes; Talend has 3 separate path params (FILENAME, DIRECTORY, PATH) for different modes. Converter now outputs all 3 per _java.xml. |
| ENG-DEL-002 | **P1** | Engine reads `fail_on_error` but converter outputs `failon` per _java.xml param name FAILON. Config key mismatch prevents proper error handling. |
| ENG-DEL-003 | **P1** | Engine reads `is_directory` / `is_folder_file` but converter outputs `folder` / `folder_file` per _java.xml. Mode detection broken. |
| ENG-DEL-004 | **P2** | Engine has `recursive` config key (default False) but _java.xml has no RECURSIVE param. In Talend, directory deletion is implicitly recursive. |
| ENG-DEL-005 | **P2** | Engine does not set `{id}_DELETE_PATH` or `{id}_CURRENT_STATUS` globalMap variables after deletion. |
| ENG-DEL-006 | **P3** | Engine does not handle symbolic links specially -- os.path.isfile/isdir follow symlinks. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Counts 1 for each operation |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | 1 if deleted, 0 otherwise |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | 0 if deleted, 1 otherwise |
| `{id}_DELETE_PATH` | Yes | **No** | -- | Not implemented |
| `{id}_CURRENT_STATUS` | Yes | **No** | -- | Not implemented |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-DEL-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` crash when globalMap is set -- affects all components |
| BUG-DEL-002 | **P1** | `file_delete.py:65` | Empty string `path` accepted via `.get('path', '')` -- raises no error, proceeds silently until `ValueError` at line 80 |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-DEL-001 | **P1** | Engine uses `fail_on_error`, `is_directory`, `is_folder_file` but _java.xml uses `FAILON`, `FOLDER`, `FOLDER_FILE`. Converter now outputs _java.xml names; engine needs alignment. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-DEL-001 | **P2** | "No f-strings in logger calls" | Engine uses f-strings in logger.info/error/warning calls (lines 71, 79, 89, etc.) |
| STD-DEL-002 | **P2** | "_validate_config() should be called" | `_validate_config()` method defined (line 144) but never called by execution path |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No path sanitization in engine -- user-provided paths are used directly with `os.remove()`, `os.rmdir()`, and `shutil.rmtree()`. Path traversal via `../` sequences or symbolic link manipulation could delete unintended files.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` |
| Level usage | Appropriate: info for operations, error for failures, warning for missing files |
| Sensitive data | File paths logged -- acceptable for debugging but may expose directory structure |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses base class `FileOperationError` (declared in docstring but uses generic Exception re-raise) |
| Exception chaining | No -- bare `raise` in except block |
| fail_on_error handling | Correct pattern: catches exception, re-raises only if `fail_on_error=True` |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Present: `_process(self, input_data: Optional[Any] = None) -> Dict[str, Any]` |
| Parameter types | Present: `_validate_config(self) -> List[str]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-DEL-001 | **P3** | Minor: redundant `os.path.isfile()` / `os.path.isdir()` checks in auto-detect mode. Could use single `os.path.exists()` then `os.path.isfile()`. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- utility component, no data processing |
| Memory threshold | N/A -- single file operation |
| Large data handling | N/A -- deletes files/directories, no data flow |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 31 | `tests/converters/talend_to_v1/components/test_file_delete.py` |
| Engine unit tests | 0 | None |
| Integration tests | Included | `tests/converters/talend_to_v1/test_integration.py` (regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-DEL-001 | **P2** | No engine unit tests for FileDelete `_process()` -- prevents Testing from reaching Green |

### 8.3 Recommended Test Cases

**Engine tests (if implemented):**

- Happy path: delete existing file, verify removed
- Happy path: delete existing directory (empty), verify removed
- Auto-detect mode: file exists, directory exists, neither exists
- Fail on error: True (raises), False (suppresses)
- Statistics tracking: NB_LINE, NB_LINE_OK, NB_LINE_REJECT
- Edge case: path is empty string
- Edge case: path does not exist with fail_on_error=False
- Edge case: permission denied on file

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-DEL-001** |
| P1 | 3 | **BUG-DEL-002**, **NAME-DEL-001**, **ENG-DEL-001/002/003** (counted as 1 engine alignment task) |
| P2 | 4 | ENG-DEL-004, ENG-DEL-005, STD-DEL-001, STD-DEL-002, TEST-DEL-001 |
| P3 | 2 | ENG-DEL-006, PERF-DEL-001 |
| **Total** | **10** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All 4 previous CONV issues FIXED |
| Engine (ENG) | 6 | ENG-DEL-001, 002, 003, 004, 005, 006 |
| Bug (BUG) | 2 | BUG-DEL-001, 002 |
| Naming (NAME) | 1 | NAME-DEL-001 |
| Standards (STD) | 2 | STD-DEL-001, 002 |
| Performance (PERF) | 1 | PERF-DEL-001 |
| Testing (TEST) | 1 | TEST-DEL-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set |

---

## 10. Recommendations

### Immediate (Before Production)

- Fix `_update_global_map()` crash in base class (P0, cross-cutting -- fixes all 54 components)
- Align engine config keys with converter output: `failon`/`fail_on_error`, `folder`/`is_directory`, `folder_file`/`is_folder_file` (P1)

### Short-term (Hardening)

- Fix empty string path handling in engine (P1)
- Add path sanitization against traversal attacks (P1)
- Implement `{id}_DELETE_PATH` and `{id}_CURRENT_STATUS` globalMap variables (P2)
- Add engine unit tests for FileDelete (P2)
- Replace f-strings in logger with % formatting (P2)
- Implement or remove dead `_validate_config()` (P2)

### Long-term (Optimization)

- Handle symbolic links explicitly in deletion logic (P3)
- Optimize redundant os.path checks in auto-detect mode (P3)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | <https://help.qlik.com/talend/en-US/components/7.3/tfiledelete/tfiledelete-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileDelete/tFileDelete_java.xml> | _java.xml source of truth for param names and defaults |
| Engine source | `src/v1/engine/components/file/file_delete.py` | Feature parity analysis (175 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_delete.py` | Converter audit (82 lines) |
| Test source | `tests/converters/talend_to_v1/components/test_file_delete.py` | Test coverage (31 tests) |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set -- affects statistics reporting |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature -- may affect DELETE_PATH/CURRENT_STATUS retrieval |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold-standard converter rewrite*
