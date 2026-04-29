# Audit Report: tFileTouch / FileTouch

> **Audited**: 2026-04-04
> **Re-audited**: 2026-04-29 (engine remediation)
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: REMEDIATED -- engine rewritten to ENGINE_COMPONENT_PATTERN.md gold standard
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 0. 2026-04-29 Re-audit Summary (Engine Remediation)

Engine rewrite at `src/v1/engine/components/file/file_touch.py` brings the
component to gold-standard compliance.

| Issue | Status | Resolution |
| ----- | ------ | ---------- |
| ~~BUG-FT-001 (P0)~~ | **FIXED** | Cross-cutting `_update_global_map()` already corrected in `base_component.py:617` (verified) |
| ~~ENG-FT-001 (P1)~~ | **FIXED** | Engine now reads `createdir` (converter key) and falls back to legacy `create_directory` |
| ~~ENG-FT-002 (P2)~~ | **FIXED** | Silent-failure bug eliminated; broad `except Exception` replaced with `except OSError`; `die_on_error` honoured; missing-parent-directory raises `FileOperationError` |
| ~~Code-Quality P1 (no `_validate_config`)~~ | **FIXED** | `_validate_config()` raises `ConfigurationError` for missing `filename` and bad bool types |
| ~~Code-Quality P2 (f-string in logger)~~ | **FIXED** | %-formatting throughout (Rule 8) |
| ~~Code-Quality P2 (bare except)~~ | **FIXED** | Narrowed to `OSError` / `FileOperationError` |
| ~~Code-Quality P3 (unused typing import)~~ | **FIXED** | Imports trimmed |
| ~~ENG-FT-001 (ERROR_MESSAGE globalMap not set)~~ | **FIXED** | `{id}_ERROR_MESSAGE` set on failure |
| ~~Testing P2 gap~~ | **FIXED** | New `tests/v1/engine/components/file/test_file_touch.py` (8 classes, 13 tests, all passing) |

**Other improvements**:
- Added `@REGISTRY.register("FileTouch", "tFileTouch")` (Rule 9)
- Module docstring with Config Mapping table (Rule 1)
- Replaced bare `ValueError` / `FileNotFoundError` with `ConfigurationError` / `FileOperationError` (Rule 7)
- Returns `{"main": ..., "reject": None}` (Rule 3)

**New Overall: GREEN**. Updated scorecard: P0=0 / P1=0 / P2=0 / P3=0.

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileTouch` |
| **V1 Engine Class** | `FileTouch` |
| **Engine File** | `src/v1/engine/components/file/file_touch.py` (99 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_touch.py` (67 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileTouch")` decorator-based dispatch |
| **Registry Aliases** | `tFileTouch` |
| **Category** | File / Utility |
| **Complexity** | Low -- utility component with 2 unique parameters, no data flow schema |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_touch.py` | Engine implementation (99 lines) |
| `src/converters/talend_to_v1/components/file/file_touch.py` | Converter class (67 lines) |
| `tests/converters/talend_to_v1/components/test_file_touch.py` | Converter tests (22 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 2 unique params + 2 framework params extracted; `_build_component_dict` pattern; 1 per-feature needs_review entry for engine gap |
| Engine Feature Parity | **Y** | 0 | 1 | 1 | 0 | Engine reads `create_directory` but converter outputs `createdir`; engine default `False` matches _java.xml; no die_on_error support |
| Code Quality | **Y** | 1 | 1 | 2 | 1 | Cross-cutting `_update_global_map()` crash (P0); no `_validate_config()` (P1); f-string in logger (P2); bare except (P2); unused import typing (P3) |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Minimal -- single file touch operation; no memory concerns |
| Testing | **Y** | 0 | 0 | 1 | 0 | 22 converter unit tests across 8 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) -- no engine test coverage prevents Green |

**Overall: Yellow -- Converter fully standardized (Green); engine has config key mismatch documented via needs_review; engine/code quality gaps keep overall at Yellow**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Align engine config key `create_directory` with converter `createdir` (P1, engine gap)
3. Add engine unit tests for FileTouch (P2, testing gap)
4. Replace f-string in logger calls with % formatting (P2, code quality)
5. Add `_validate_config()` implementation (P1, code quality)

---

## 3. Talend Feature Baseline

### What tFileTouch Does

`tFileTouch` creates an empty file at a specified path, or if the file already exists, updates its modification time and last access time while keeping the contents unchanged. This mirrors the Unix `touch` command behavior. It is a utility component in the File family, commonly used in ETL workflows to create flag files, marker files, trigger files, or to update timestamps for scheduling and monitoring purposes.

The component has only 2 unique parameters: FILENAME (the file path) and CREATEDIR (whether to create parent directories). It operates as a standalone utility with no data flow -- it does not consume or produce rows of data.

**Source**: [tFileTouch Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfiletouch/tfiletouch-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileTouch/tFileTouch_java.xml)
**Component family**: File / Utility
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | File Name | `FILENAME` | FILE | `""` | **Mandatory**. Absolute path to the file to create or touch. Supports context variables and Java expressions. |
| 2 | Create directory if not exists | `CREATEDIR` | CHECK | `false` | When checked, automatically creates parent directories if they do not exist. Default is `false` per _java.xml. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 3 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enables collection of processing metadata for tStatCatcher. |
| 4 | Label | `LABEL` | TEXT | `""` | Text label for the component on the designer canvas. No runtime impact. |

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
| `{id}_ERROR_MESSAGE` | String | After error | Error message when the touch operation fails. |

### 3.5 Behavioral Notes

1. **Unix `touch` semantics**: If the file exists, updates modification/access time without altering contents. If the file does not exist, creates a new empty (zero-byte) file.
2. **CREATEDIR default is `false` per _java.xml**: The _java.xml definition specifies `CREATEDIR` as CHECK type with `DEFAULT="false"`. When unchecked, the component fails if the parent directory does not exist.
3. **No schema**: tFileTouch is a pure utility component with no data flow. It does not process rows of data. Both input and output schemas are empty.
4. **No DIE_ON_ERROR setting**: Unlike many Talend components, tFileTouch does not have an explicit DIE_ON_ERROR parameter. Error behavior is controlled by default Talend error handling.
5. **Dynamic filenames**: FILENAME supports context variables (`context.outputDir + "/flag.txt"`), globalMap references, and Java expressions. Commonly used with tFileList iteration.
6. **Absolute paths recommended**: Talend documentation warns against relative paths due to different working directories across environments.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated `FileTouchConverter` class registered via `@REGISTRY.register("tFileTouch")`. It extracts all 2 unique parameters plus 2 framework parameters using safe `_get_str()` / `_get_bool()` helpers. The converter follows the gold standard pattern with `_build_component_dict()` wrapper.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILENAME` | Yes | `filename` | `_get_str()`, default `""` |
| 2 | `CREATEDIR` | Yes | `createdir` | `_get_bool()`, default `False` per _java.xml |
| 3 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default `False` |
| 4 | `LABEL` | Yes | `label` | Framework param, default `""` |

**Summary**: 4 of 4 parameters extracted (100%).

### 4.2 Schema Extraction

Not applicable -- tFileTouch is a utility component with no data flow schema. Schema is set to `{"input": [], "output": []}`.

### 4.3 Expression Handling

FILENAME supports context variables and Java expressions. The converter passes the value through `_get_str()` which strips surrounding quotes. Expression resolution (`context.var`, `{{java}}`) happens at engine runtime, not converter time.

### 4.4 Converter Issues

None -- converter fully standardized per gold standard.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `createdir` | Engine reads `create_directory` but converter outputs `createdir` per _java.xml param name CREATEDIR | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File creation (touch) | **Yes** | High | `_process()` line 85 | Uses `open(filename, 'a')` + `os.utime()` |
| 2 | Create directory | **Yes** | High | `_process()` line 77 | `os.makedirs()` when `create_directory=True` |
| 3 | Statistics tracking | **Yes** | High | `_process()` line 89 | `_update_stats()` for NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 4 | Error handling | **Partial** | Medium | `_process()` line 95 | Catches all exceptions but no die_on_error support |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FT-001 | **P1** | Engine reads `create_directory` config key but converter outputs `createdir` per _java.xml param name. Config key mismatch means engine may use default `False` even when user set `CREATEDIR=true` in Talend. |
| ENG-FT-002 | **P2** | No die_on_error support. Engine catches all exceptions in a broad `except Exception` block. Talend's default error behavior may differ. |

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
| BUG-FT-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` references undefined `value` variable. Crashes all components when globalMap is set. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FT-001 | **P2** | Engine uses `create_directory` config key; converter uses `createdir` per _java.xml. Needs alignment. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FT-001 | **P2** | "Use %-formatting in logger calls" | Uses f-strings: `logger.info(f"[{self.id}] Touch operation started: {filename}")` |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. File path comes from configuration, not user input. No eval/exec usage.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logging.getLogger(__name__)` |
| Level usage | Adequate -- info for start/complete, debug for operations, error for failures |
| Sensitive data | OK -- file paths logged but not sensitive in ETL context |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | P1 -- Uses ValueError/FileNotFoundError directly, no custom exception hierarchy |
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
| PERF-FT-001 | **P3** | Return value wraps result in dict -- minor overhead but consistent with base class pattern |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- utility component, no data flow |
| Memory threshold | N/A -- single file operation |
| Large data handling | N/A -- creates/touches one file per execution |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 22 | `tests/converters/talend_to_v1/components/test_file_touch.py` |
| Engine unit tests | 0 | None |
| Integration tests | Shared | `tests/converters/talend_to_v1/test_integration.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FT-001 | **P2** | No engine unit tests for FileTouch. Engine implementation not tested independently. |

### 8.3 Recommended Test Cases

1. Engine: file creation when file does not exist
2. Engine: timestamp update when file already exists
3. Engine: directory creation with create_directory=True
4. Engine: failure when directory missing and create_directory=False
5. Engine: empty filename raises ValueError
6. Engine: file permissions on created files

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-FT-001** (cross-cutting) |
| P1 | 2 | **ENG-FT-001**, **NAME-FT-001** (via engine gap) |
| P2 | 3 | **ENG-FT-002**, **STD-FT-001**, **TEST-FT-001** |
| P3 | 1 | **PERF-FT-001** |
| **Total** | **7** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 2 | ENG-FT-001, ENG-FT-002 |
| Bug (BUG) | 1 | BUG-FT-001 |
| Naming (NAME) | 1 | NAME-FT-001 |
| Standards (STD) | 1 | STD-FT-001 |
| Testing (TEST) | 1 | TEST-FT-001 |
| Performance (PERF) | 1 | PERF-FT-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- statistics lost |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-FT-001** (P0): Fix `_update_global_map()` crash in base class -- affects all components

### Short-term (Hardening)

1. **ENG-FT-001** (P1): Align engine config key `create_directory` with converter `createdir` or vice versa
2. Add `_validate_config()` implementation to check for required `filename`

### Long-term (Optimization)

1. **TEST-FT-001** (P2): Add engine unit tests for FileTouch
2. **ENG-FT-002** (P2): Add die_on_error support
3. **STD-FT-001** (P2): Replace f-strings in logger calls with % formatting
4. **PERF-FT-001** (P3): Minor -- no action needed

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talend 7.3 docs | <https://help.qlik.com/talend/en-US/components/7.3/tfiletouch/tfiletouch-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileTouch/tFileTouch_java.xml> | Component definition XML, CREATEDIR default=false |
| Engine source | `src/v1/engine/components/file/file_touch.py` | Feature parity analysis (99 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_touch.py` | Converter audit (67 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_touch.py` | Test coverage (22 tests) |

## Appendix B: Engine Config Key Mapping

| _java.xml Parameter | Converter Config Key | Engine Config Key | Match? | Notes |
| --------------------- | --------------------- | ------------------- | -------- | ------- |
| `FILENAME` | `filename` | `filename` | Yes | Both use same key |
| `CREATEDIR` | `createdir` | `create_directory` | **No** | Engine gap -- needs alignment |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 10 gold standard rewrite*
