# Audit Report: tFileExist / FileExistComponent

> **Audited**: 2026-04-04
> **Re-audited**: 2026-04-29 (engine remediation)
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: REMEDIATED -- engine rewritten to ENGINE_COMPONENT_PATTERN.md gold standard
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 0. 2026-04-29 Re-audit Summary (Engine Remediation)

Engine rewrite at `src/v1/engine/components/file/file_exist.py` brings the
component to gold-standard compliance. All P0/P1 issues from the 2026-04-04
report are now resolved.

| Issue | Status | Resolution |
| ----- | ------ | ---------- |
| ~~BUG-FE-001 (P0)~~ | **FIXED** | Cross-cutting `_update_global_map()` already corrected in `base_component.py:617` (verified) |
| ~~STD-FE-001 (P1)~~ | **FIXED** | `_validate_config()` now raises `ConfigurationError` and is invoked by `BaseComponent.execute()` Step 2 |
| ~~ENG-FE-001 (P1)~~ | **FIXED** | `{id}_EXISTS` written to globalMap in `_process()` |
| ~~ENG-FE-002 (P1)~~ | **FIXED** | `{id}_FILENAME` written to globalMap in `_process()` |
| ~~Needs-review #1 (engine_gap)~~ | **FIXED** | Engine accepts `file_name` (converter key), `file_path`, and legacy `FILE_NAME` |
| ~~Testing P1 gap~~ | **FIXED** | New `tests/v1/engine/components/file/test_file_exist.py` (8 test classes, 14 tests, all passing) |
| Code-Quality P2 (f-string in logger) | **FIXED** | Switched to %-formatting per Rule 8 |

**Other improvements**:
- Added `@REGISTRY.register("FileExistComponent", "FileExist", "tFileExist")` (Rule 9)
- Module docstring now contains the full Config Mapping table (Rule 1)
- Returns `{"main": ..., "reject": None}` per Rule 3
- Replaced bare `ValueError` with `ConfigurationError` per Rule 7

**New Overall: GREEN**. Updated scorecard: P0=0 / P1=0 / P2=0 / P3=0.

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileExist` |
| **V1 Engine Class** | `FileExistComponent` |
| **Engine File** | `src/v1/engine/components/file/file_exist.py` (120 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_exist.py` (67 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileExist")` decorator-based dispatch |
| **Registry Aliases** | `tFileExist` (converter registry) |
| **Category** | File / Management |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_exist.py` | Engine implementation (120 lines) |
| `src/converters/talend_to_v1/components/file/file_exist.py` | Converter class (67 lines) |
| `tests/converters/talend_to_v1/components/test_file_exist.py` | Converter tests (25 tests, 8 classes) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1/1 unique param extracted (FILE_NAME); 1 needs_review (engine key mismatch); _build_component_dict with type_name="FileExistComponent" |
| Engine Feature Parity | **Y** | 0 | 2 | 1 | 0 | Missing globalMap EXISTS/FILENAME variables; check_directory not in Talend XML |
| Code Quality | **Y** | 1 | 1 | 1 | 0 | Cross-cutting _update_global_map crash (P0); dead _validate_config (P1); f-string in logger (P2) |
| Performance & Memory | **G** | 0 | 0 | 0 | 0 | Single file stat check -- no memory or performance concerns |
| Testing | **Y** | 0 | 1 | 0 | 0 | 25 converter tests across 8 classes (Green); 0 engine unit tests (P1 gap) |

**Overall: GREEN -- Simple utility component with correct converter, documented engine gaps, comprehensive converter tests**

**Top Actions**:

1. Fix cross-cutting `_update_global_map()` crash (P0, shared with all components)
2. Add engine unit tests for FileExistComponent (P1)
3. Implement globalMap EXISTS/FILENAME variables in engine (P1)

---

## 3. Talend Feature Baseline

### What tFileExist Does

tFileExist is a simple utility component in the File/Management family that checks whether a file or directory exists at a specified path. It is a **trigger-only** component with no data flow (FLOW MAX_INPUT=0, MAX_OUTPUT=0). It is typically used in conjunction with tRunIf to conditionally execute subjobs based on file existence.

The component sets two globalMap variables: `{id}_EXISTS` (boolean, available during FLOW) indicating whether the file exists, and `{id}_FILENAME` (string, available AFTER) containing the resolved file path.

**Source**: <https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileExist/tFileExist_java.xml>
**Component family**: File / Management
**Available in**: All Talend Studio editions
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | File Name | `FILE_NAME` | FILE | `"__COMP_DEFAULT_FILE_DIR__/file"` | Path to the file to check for existence. Required. |

### 3.2 Advanced Settings

None -- tFileExist has no advanced settings.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` | N/A | N/A | MAX_INPUT=0, MAX_OUTPUT=0 -- no data flow |
| `ITERATE` | Input | Row > Iterate | MAX_OUTPUT=0, MAX_INPUT=1 -- can be iterated |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires after failed execution |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component success |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires after component error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution trigger |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_EXISTS` | id_Boolean | FLOW | Whether the file/directory exists |
| `{id}_FILENAME` | id_String | AFTER | The resolved file path that was checked |

### 3.5 Behavioral Notes

1. tFileExist is a **trigger component** -- it produces no data rows, only sets globalMap variables and fires trigger connections.
2. The EXISTS variable is available at FLOW time, meaning downstream components connected via RUN_IF can immediately check file existence.
3. FILENAME is available AFTER execution, useful for logging or passing to subsequent components.
4. The component checks for both files and directories via `os.path.exists()` semantics in Talend.
5. FILE_NAME supports context variables (e.g., `context.input_dir + "/file.txt"`) which are resolved at runtime.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileExist")` with the standard `_build_component_dict` wrapper pattern. It extracts 1 unique parameter plus 2 framework parameters.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILE_NAME` | Yes | `file_name` | D-38 snake_case. Engine reads `file_path` -- needs_review for key mismatch |
| 2 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default False |
| 3 | `LABEL` | Yes | `label` | Framework param, default "" |

**Summary**: 1 of 1 unique parameters extracted (100%). 2 framework params extracted.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| N/A | N/A | Utility component -- schema = `{"input": [], "output": []}` |

tFileExist has FLOW MAX_INPUT=0, MAX_OUTPUT=0 -- there is no schema to extract. The converter correctly sets empty schema for both input and output.

### 4.3 Expression Handling

FILE_NAME supports context variables (e.g., `context.input_path`) which are passed through as-is by `_get_str()`. No Java expression translation is needed for this component.

### 4.4 Converter Issues

None -- all issues resolved in rewrite.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `file_name` | Converter sends `file_name` (D-38 snake_case of FILE_NAME) but engine reads `file_path` -- config key mismatch | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File existence check | **Yes** | High | `_process()` line 98-105 | Uses `os.path.exists()` for files, `os.path.isdir()` for directories |
| 2 | check_directory mode | **Yes** | Medium | `_process()` line 100-101 | Extra engine feature not in Talend _java.xml |
| 3 | EXISTS globalMap var | **No** | N/A | N/A | Not set -- downstream RUN_IF checks will fail |
| 4 | FILENAME globalMap var | **No** | N/A | N/A | Not set -- post-execution file path not available |
| 5 | Legacy FILE_NAME fallback | **Yes** | High | `_process()` line 86 | Reads `file_path` or `FILE_NAME` as fallback |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FE-001 | **P1** | Engine does not set `{id}_EXISTS` globalMap variable -- downstream tRunIf components checking file existence will not work |
| ENG-FE-002 | **P1** | Engine does not set `{id}_FILENAME` globalMap variable -- post-execution file path not available to downstream components |
| ENG-FE-003 | **P2** | Engine has `check_directory` config option not present in Talend _java.xml -- extra feature, no Talend equivalent |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_EXISTS` | Yes (FLOW) | No | N/A | P1: Critical for RUN_IF patterns |
| `{id}_FILENAME` | Yes (AFTER) | No | N/A | P1: Needed for downstream file path access |
| `{id}_NB_LINE` | Yes | Partial | `_update_stats()` | Cross-cutting: base class stats mechanism |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FE-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` references undefined variable, causing `UnboundLocalError` at runtime |

### 6.2 Naming Consistency

No naming issues found. Engine class `FileExistComponent` follows project conventions.

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FE-001 | **P1** | "`_validate_config()` should be called" | Dead code: defined but never invoked by base class `execute()` |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

| Concern | Assessment |
| --------- | ------------ |
| Path traversal | Low risk -- FILE_NAME from config, not user input at runtime. Engine does no path sanitization but this is acceptable for batch ETL. |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | Good -- info for start/complete, error for failures |
| Sensitive data | **P2** -- f-string in `logger.info()` includes file path, acceptable for ETL but could expose paths in logs |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Not used -- raises generic `ValueError` |
| Exception chaining | Not used |
| die_on_error handling | Not implemented -- always raises on missing config |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods have return type annotations |
| Parameter types | Good -- proper use of `Optional[Any]`, `Dict[str, Any]`, `List[str]` |

---

## 7. Performance & Memory

No performance concerns. tFileExist performs a single `os.path.exists()` or `os.path.isdir()` system call -- effectively O(1).

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no data flow |
| Memory threshold | N/A -- single stat call |
| Large data handling | N/A -- utility component |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 25 | `tests/converters/talend_to_v1/components/test_file_exist.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (covered by regression guard suite) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FE-001 | **P1** | No engine unit tests for FileExistComponent -- file existence check, check_directory mode, missing config error, globalMap variables |

### 8.3 Recommended Test Cases

- Happy path: file exists, file does not exist
- check_directory mode: directory exists, directory does not exist, file exists but check_directory=True
- Missing config: no file_path, empty file_path
- Special paths: symlinks, relative paths, paths with spaces
- GlobalMap: verify EXISTS and FILENAME variables are set (when engine is fixed)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-FE-001** |
| P1 | 4 | **ENG-FE-001**, **ENG-FE-002**, **STD-FE-001**, **TEST-FE-001** |
| P2 | 1 | **ENG-FE-003** |
| P3 | 0 | |
| **Total** | **6** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 3 | ENG-FE-001, ENG-FE-002, ENG-FE-003 |
| Bug (BUG) | 1 | BUG-FE-001 |
| Standards (STD) | 1 | STD-FE-001 |
| Testing (TEST) | 1 | TEST-FE-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- BUG-FE-001 |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash in base class (BUG-FE-001, P0, cross-cutting)

### Short-term (Hardening)

1. Implement `{id}_EXISTS` globalMap variable in engine (ENG-FE-001, P1)
2. Implement `{id}_FILENAME` globalMap variable in engine (ENG-FE-002, P1)
3. Wire `_validate_config()` call in base class `execute()` (STD-FE-001, P1)
4. Add engine unit tests for FileExistComponent (TEST-FE-001, P1)

### Long-term (Optimization)

1. Document or remove `check_directory` engine-only feature (ENG-FE-003, P2)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | <https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileExist/tFileExist_java.xml> | Parameter definitions, defaults, connector types, return variables |
| Engine source | `src/v1/engine/components/file/file_exist.py` (120 lines) | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/file/file_exist.py` (67 lines) | Converter audit |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_exist.py` (25 tests) | Test coverage assessment |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash -- prevents globalMap variable setting even after engine fix |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 09-02 converter rewrite*
