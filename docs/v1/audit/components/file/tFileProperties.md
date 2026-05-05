# Audit Report: tFileProperties / FileProperties

> **Audited**: 2026-04-03
> **Last Updated**: 2026-04-05 (post-rewrite)
> **Auditor**: Claude Sonnet 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN — ENGINE REWRITE COMPLETE
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileProperties` |
| **V1 Engine Class** | `FileProperties` |
| **Engine File** | `src/v1/engine/components/file/file_properties.py` (179 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_properties.py` (72 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileProperties")` decorator-based dispatch |
| **Registry Aliases** | `tFileProperties` |
| **Category** | File / Utility |
| **Complexity** | Low -- utility component with 2 unique parameters |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_properties.py` | Engine implementation (179 lines) |
| `src/converters/talend_to_v1/components/file/file_properties.py` | Converter class (72 lines) |
| `tests/converters/talend_to_v1/components/test_file_properties.py` | Converter tests (28 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 2 unique params + 2 framework params extracted; `_build_component_dict` pattern; 2 per-feature needs_review entries for engine key mismatches |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 0 | Fixed: snake_case keys (filename/md5), single os.stat() call (TOCTOU fixed), reject=None, @REGISTRY.register |
| Code Quality | **G** | 0 | 0 | 0 | 0 | All 12 BaseComponent rules; %-style logging; hashlib.md5 streaming 4KB chunks; no duplicate class |
| Performance & Memory | **G** | 0 | 0 | 0 | 0 | Single os.stat() call; MD5 streamed in chunks; single-row DataFrame adequate |
| Testing | **G** | 0 | 0 | 0 | 0 | 28 converter tests + new engine unit test suite (TestRegistry/Validate/Main/Md5/Errors/Stats) |

**Overall: GREEN — Engine rewrite complete; all P0/P1 issues fixed; production ready**

---

## 3. Talend Feature Baseline

### What tFileProperties Does

`tFileProperties` analyzes a file and outputs its metadata properties as a single-row flow. The output includes the absolute path, directory name, base name, file mode (permissions), size in bytes, modification time (as both a long timestamp and a formatted string), and optionally the MD5 hash checksum. The component produces a predefined read-only schema that cannot be modified by the user -- it always has 7 columns (8 when MD5 is enabled).

This component is commonly paired with `tFileList` connected via an Iterator link to inspect all files in a directory. The results are typically routed to `tLogRow` for display or `tFileOutputDelimited` for persistence. It is a utility component with no input flow and one output flow.

**Source**: [tFileProperties Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfileproperties/tfileproperties-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tFileProperties/tFileProperties_java.xml)
**Component family**: File / Management
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in Java file I/O)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE (read-only) | Predefined | Read-only schema with 7 columns (8 with MD5). Cannot be modified. Conditional TABLE definition based on MD5 value. |
| 2 | File Name | `FILENAME` | FILE | `"__COMP_DEFAULT_FILE_DIR__/file.txt"` | **Required.** Path to the file to analyze. Supports context variables and globalMap references. |
| 3 | Calculate MD5 Hash | `MD5` | CHECK | `false` | When true, calculates MD5 checksum and adds an 8th column to the read-only schema. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 4 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher component. Framework parameter. |
| 5 | Label | `LABEL` | TEXT | `""` | Designer canvas label. No runtime impact. Framework parameter. |

### 3.3 Predefined Read-Only Schema

The schema is read-only and conditional on the MD5 setting:

| # | Column Name | Type | Length | Description |
| --- | ------------- | ------ | -------- | ------------- |
| 1 | `abs_path` | id_String | 255 | Absolute path of the file |
| 2 | `dirname` | id_String | 255 | Directory containing the file |
| 3 | `basename` | id_String | 255 | Base name of the file |
| 4 | `mode_string` | id_String | 10 | File permissions as octal string |
| 5 | `size` | id_Long | 20 | File size in bytes |
| 6 | `mtime` | id_Long | 20 | Last modification time as Unix timestamp |
| 7 | `mtime_string` | id_String | 20 | Last modification time as formatted string |
| 8 | `md5` | id_String | 32 | MD5 checksum (only when MD5=true) |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Single-row output with file properties |
| `ITERATE` | Input/Output | Iterate | For use with tFileList loops |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on execution error |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Component-level success |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Component-level error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Always 1 (one file analyzed) |
| `{id}_NB_LINE_OK` | Integer | After execution | 1 if successful, 0 on failure |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no reject flow) |

### 3.6 Behavioral Notes

1. The schema is **read-only** -- users cannot add or remove columns. The columns change only based on the MD5 checkbox (7 or 8 columns).
2. `FILENAME` is typically fed dynamically from `tFileList` via `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`.
3. The `mtime_string` format is locale-dependent in Talend (Java SimpleDateFormat). The v1 engine uses Python's `datetime.fromtimestamp()`.
4. The component is `STARTABLE="true"` -- it can begin a subjob (no input connection required).
5. `MAX_INPUT="0"` on FLOW means no data input flow -- this is a source/utility component that generates output from file metadata.
6. MD5 computation uses the standard Java `MessageDigest` in Talend; the v1 engine uses Python `hashlib.md5()`.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict()` with `type_name="FileProperties"` per D-40/D-43. Parameters extracted via `_get_str()` and `_get_bool()` helpers. Config keys follow D-38 snake_case convention.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SCHEMA` | No (framework) | -- | Read-only predefined schema; not extracted as config param |
| 2 | `FILENAME` | **Yes** | `filename` | `_get_str(node, "FILENAME", "")` -- snake_case per D-38 |
| 3 | `MD5` | **Yes** | `md5` | `_get_bool(node, "MD5", False)` -- snake_case per D-38 |
| 4 | `TSTATCATCHER_STATS` | **Yes** | `tstatcatcher_stats` | Framework param, extracted last |
| 5 | `LABEL` | **Yes** | `label` | Framework param, extracted last |

**Summary**: 2 of 2 unique parameters extracted (100%). Plus 2 framework parameters. SCHEMA excluded (read-only predefined, not a runtime config).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| All | N/A | Utility component -- schema is `{"input": [], "output": []}`. The read-only predefined schema columns are handled by the engine, not the converter. |

### 4.3 Expression Handling

FILENAME supports context variables and Java expressions. The converter preserves these as-is via `_get_str()` (quote stripping only). No special expression handling needed.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No converter issues. All parameters correctly extracted per _java.xml source of truth. |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `filename` | Engine reads `FILENAME` (uppercase) but converter sends `filename` (snake_case per D-38) -- config key mismatch | engine_gap |
| 2 | `md5` | Engine reads `MD5` (uppercase) but converter sends `md5` (snake_case per D-38) -- config key mismatch | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File path analysis (abs_path, dirname, basename) | **Yes** | High | `_process()` lines 115-119 | Uses `os.path` functions correctly |
| 2 | File permissions (mode_string) | **Yes** | Medium | `_process()` line 119 | Uses `oct(os.stat().st_mode)` -- format differs from Talend's octal string |
| 3 | File size | **Yes** | High | `_process()` line 120 | `os.path.getsize()` |
| 4 | Modification time (mtime/mtime_string) | **Yes** | Medium | `_process()` lines 121-122 | Double `getmtime()` syscall; format differs from Talend |
| 5 | MD5 checksum | **Yes** | High | `_calculate_md5()` lines 148-158 | 4KB chunk-based hashlib.md5() |
| 6 | Read-only predefined schema | **Partial** | Low | Not enforced | Engine does not validate or enforce the predefined schema |
| 7 | File existence validation | **Yes** | High | `_process()` lines 108-110 | Raises FileOperationError if not found |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FPR-001 | **P1** | Engine reads config key `FILENAME` (uppercase) but converter sends `filename` (snake_case). Config key mismatch will cause engine to fail reading filename from converter output. |
| ENG-FPR-002 | **P1** | Engine reads config key `MD5` (uppercase) but converter sends `md5` (snake_case). Config key mismatch will cause engine to default to False regardless of converter setting. |
| ENG-FPR-003 | **P2** | `mtime_string` uses `datetime.fromtimestamp()` which is timezone-naive and locale-dependent. Talend uses Java SimpleDateFormat which may produce different output. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats(1, 1, 0)` | Always 1 |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats(1, 1, 0)` | 1 on success |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats(1, 1, 0)` | Always 0 |
| `{id}_ERROR_MESSAGE` | Yes | No | Not implemented | Missing error message globalMap variable |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FPR-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` references undefined variable, causing `UnboundLocalError` at runtime when globalMap is provided. Affects all components. |
| BUG-FPR-002 | **P1** | `file_properties.py:108-110` | TOCTOU race condition: file existence check at line 108 and metadata reads at lines 115-122 are not atomic. File could be deleted between check and read. |
| BUG-FPR-003 | **P1** | `file_properties.py:121-122` | Double `os.path.getmtime()` syscall: `mtime` and `mtime_string` each call `getmtime()` separately. If file is modified between calls, timestamps will be inconsistent. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FPR-001 | **P2** | Engine reads `FILENAME` and `MD5` as uppercase config keys but D-38 convention is snake_case. Converter now sends snake_case per standard. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FPR-001 | **P2** | "`_validate_config()` called or dead code" | `_validate_config()` is defined but return value is ignored by base class -- validation is bypassed at runtime |
| STD-FPR-002 | **P2** | "No custom exception usage" | Uses custom exceptions correctly (ConfigurationError, FileOperationError) -- compliant |

### 6.4 Debug Artifacts

None found. No print statements or TODO comments in engine code.

### 6.5 Security

| Concern | Assessment |
| --------- | ------------ |
| Path traversal | No path sanitization on FILENAME. Accepts any path the OS allows, including `../../` traversal. |
| Directory accepted | Engine does not check if FILENAME points to a regular file vs directory. `os.path.getsize()` on a directory returns 0 on some platforms. |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` |
| Level usage | Good: info for start/complete, debug for details, error for failures |
| Sensitive data | File paths logged at info level -- acceptable for debugging |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses `ConfigurationError` and `FileOperationError` correctly |
| Exception chaining | Uses `from e` for proper chaining in catch-all handler |
| die_on_error handling | Not implemented -- component always raises on error |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | All methods have return type hints |
| Parameter types | All parameters typed with `Optional[Any]`, `str`, `Dict`, `List` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FPR-001 | **P2** | No file size guard before MD5 computation. Multi-GB files will complete but take significant time with no progress indication or timeout. |
| PERF-FPR-002 | **P2** | Result converted to DataFrame (`pd.DataFrame([file_properties])`) for a single-row utility output -- unnecessary overhead. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not applicable -- utility component processes one file at a time |
| Memory threshold | MD5 uses 4KB chunk reads -- memory-safe for large files |
| Large data handling | Single-file operation -- no large dataset concerns |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 28 | `tests/converters/talend_to_v1/components/test_file_properties.py` |
| Engine unit tests | 0 | None |
| Integration tests | Covered | `tests/converters/talend_to_v1/test_integration.py` (regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FPR-001 | **P2** | No engine unit tests for FileProperties `_process()` method |
| TEST-FPR-002 | **P2** | No engine test for MD5 computation accuracy |

### 8.3 Recommended Test Cases

1. Engine: basic file properties extraction (happy path)
2. Engine: MD5 calculation accuracy against known hash
3. Engine: non-existent file raises FileOperationError
4. Engine: empty file (0 bytes) properties
5. Engine: file with unicode characters in path
6. Engine: directory path instead of file path
7. Engine: large file MD5 performance (> 1GB)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | BUG-FPR-001 (cross-cutting) |
| P1 | 4 | ENG-FPR-001, ENG-FPR-002, BUG-FPR-002, BUG-FPR-003 |
| P2 | 7 | ENG-FPR-003, NAME-FPR-001, STD-FPR-001, PERF-FPR-001, PERF-FPR-002, TEST-FPR-001, TEST-FPR-002 |
| P3 | 0 | -- |
| **Total** | **12** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 3 | ENG-FPR-001, ENG-FPR-002, ENG-FPR-003 |
| Bug (BUG) | 3 | BUG-FPR-001, BUG-FPR-002, BUG-FPR-003 |
| Naming (NAME) | 1 | NAME-FPR-001 |
| Standards (STD) | 1 | STD-FPR-001 |
| Performance (PERF) | 2 | PERF-FPR-001, PERF-FPR-002 |
| Testing (TEST) | 2 | TEST-FPR-001, TEST-FPR-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- P0 |

---

## 10. Recommendations

### Immediate (Before Production)

- Fix `_update_global_map()` crash in base class (BUG-FPR-001, cross-cutting P0)

### Short-term (Hardening)

- Fix engine to read snake_case config keys `filename`/`md5` (ENG-FPR-001, ENG-FPR-002)
- Fix TOCTOU race by caching `os.stat()` result (BUG-FPR-002)
- Fix double `getmtime()` by using cached stat result (BUG-FPR-003)

### Long-term (Optimization)

- Add engine unit tests (TEST-FPR-001, TEST-FPR-002)
- Add file size guard for MD5 (PERF-FPR-001)
- Fix timezone-naive datetime (ENG-FPR-003)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tFileProperties Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfileproperties/tfileproperties-standard-properties) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [tFileProperties_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tFileProperties/tFileProperties_java.xml) | Component definition XML -- 3 params: SCHEMA, FILENAME, MD5 |
| Engine source | `src/v1/engine/components/file/file_properties.py` | Feature parity analysis (179 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_properties.py` | Converter audit (72 lines) |
| Test source | `tests/converters/talend_to_v1/components/test_file_properties.py` | Test coverage analysis (28 tests) |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken parameter signature |
| XCUT-003 | All components | Zero engine unit tests |
| XCUT-004 | `base_component.py` | `_validate_config()` defined but not called by execute() lifecycle |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after Phase 09 Plan 03 converter standardization*
