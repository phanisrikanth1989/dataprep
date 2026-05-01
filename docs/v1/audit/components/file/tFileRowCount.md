# Audit Report: tFileRowCount / FileRowCount

> **Audited**: 2026-04-04
> **Revised**: 2026-05-01 (engine rewrite — all engine violations fixed)
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileRowCount` |
| **V1 Engine Class** | `FileRowCount` |
| **Engine File** | `src/v1/engine/components/file/file_row_count.py` (191 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_row_count.py` (71 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileRowCount")` decorator-based dispatch |
| **Registry Aliases** | `FileRowCount`, `tFileRowCount` |
| **Category** | File / Utility |
| **Complexity** | Low -- utility component with 4 unique parameters, no data flow schema |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_row_count.py` | Engine implementation (191 lines) |
| `src/converters/talend_to_v1/components/file/file_row_count.py` | Converter class (71 lines) |
| `tests/v1/engine/components/file/test_file_row_count.py` | Engine tests (42 tests, 9 classes) |
| `tests/converters/talend_to_v1/components/test_file_row_count.py` | Converter tests (26 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 4 unique params + 2 framework params extracted; `_build_component_dict` pattern; phantom DIE_ON_ERROR removed; 1 per-feature needs_review for encoding default mismatch |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 1 | row_separator fully implemented including custom separators; encoding default corrected to ISO-8859-15; DIE_ON_ERROR confirmed phantom (N/A) |
| Code Quality | **G** | 0 | 0 | 0 | 1 | All bugs fixed: proper exceptions, correct return type (main=None), `_validate_config()` raises, `@REGISTRY.register` added, no dual-key fallback, no debug artifacts |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Custom separator reads full file (O(n) memory) -- acceptable edge case; standard \n path is streaming |
| Testing | **G** | 0 | 0 | 0 | 0 | 42 engine unit tests across 9 test classes; 26 converter tests; all passing |

**Overall: Green -- Engine fully rewritten (2026-05-01); all P0/P1/P2 issues resolved; 2 P3s remain (custom-separator memory + SEC path traversal)**

**Resolved Actions (2026-05-01):**

1. ~~Fix `_update_global_map()` crash in base class (P0, cross-cutting)~~ **RESOLVED** (base class fixed)
2. ~~Implement `row_separator` support in engine (P1, engine gap)~~ **RESOLVED** (2026-05-01)
3. ~~Add `die_on_error` handling in engine (P1, engine gap)~~ **RESOLVED** (phantom param — DIE_ON_ERROR not in _java.xml)
4. ~~Add `{id}_ERROR_MESSAGE` globalMap variable in engine (P1, engine gap)~~ **RESOLVED** (not applicable — die_on_error is phantom)
5. ~~Add engine unit tests for FileRowCount (P2, testing gap)~~ **RESOLVED** (42 tests added 2026-05-01)

---

## 3. Talend Feature Baseline

### What tFileRowCount Does

`tFileRowCount` opens a file and reads it row by row to determine the number of rows. The component is a standalone utility that stores the result in a globalMap variable (`{id}_COUNT`), which can be accessed by downstream components via OnSubjobOk triggers. It does NOT output a data flow -- it is purely a metadata/utility component.

The primary use case is pre-validation: checking whether a file has expected row counts before processing it with input components. It can optionally ignore empty rows and supports configurable encoding and row separator characters.

**Source**: [tFileRowCount Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfilerowcount/tfilerowcount-standard-properties), [Talaxie GitHub _java.xml](https://github.com/Talend/tdi-studio-se)
**Component family**: File / Utility
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (standard Java I/O only)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | File Name | `FILENAME` | TEXT (Expression) | `""` | Absolute file path. Supports context variables and Java expressions. |
| 2 | Row Separator | `ROWSEPARATOR` | TEXT | `"\n"` | Character(s) identifying end of a row. Supports `\r\n`, `\r`, or custom separators. |
| 3 | Ignore Empty Rows | `IGNORE_EMPTY_ROW` | CHECK (Boolean) | `false` | When checked, blank/whitespace-only rows are excluded from the count. |
| 4 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for file reading. **Note**: Talend default is ISO-8859-15, NOT UTF-8. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 5 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK (Boolean) | `false` | Capture processing metadata for tStatCatcher. Framework param. |
| 6 | Label | `LABEL` | TEXT | `""` | Designer canvas label. No runtime impact. Framework param. |

**Note on DIE_ON_ERROR**: The old audit report listed `DIE_ON_ERROR` as a parameter. However, `DIE_ON_ERROR` is NOT present in the `tFileRowCount_java.xml` definition. It is a phantom parameter that does not exist for this component. Removed from converter.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. Primary connection for chaining. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with boolean expression. |

**Important**: `tFileRowCount` does NOT produce a Row output (Main or Reject). It is a standalone component that stores its result in globalMap. Downstream components access the count via `globalMap.get("tFileRowCount_1_COUNT")` after connecting with a trigger.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_COUNT` | Integer | During execution | Primary output. Total rows counted in the file. |
| `{id}_NB_LINE` | Integer | After execution | Total rows read from file. Standard Talend stat variable. |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully counted. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows excluded (empty rows when IGNORE_EMPTY_ROW=true). |

### 3.5 Behavioral Notes

1. **Standalone component**: Does NOT produce a data flow output. Row count communicated via globalMap `{id}_COUNT` variable only.
2. **Row separator behavior**: `ROWSEPARATOR` determines how line boundaries are identified. Default `\n` for Unix; Windows needs `\r\n`.
3. **Empty row definition**: When `IGNORE_EMPTY_ROW=true`, blank or whitespace-only lines are excluded.
4. **Encoding sensitivity**: File is read using specified encoding. Mismatch causes `UnicodeDecodeError`.
5. **Default encoding**: Talend defaults to `ISO-8859-15`, NOT UTF-8.
6. **Header rows**: No header skip parameter. ALL rows are counted including headers.
7. **Large files**: Line-by-line reading -- minimal memory regardless of file size.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileRowCount")` with the `FileRowCountConverter` class. All parameters are extracted using `_get_str()` and `_get_bool()` helpers from the base class. Output is wrapped via `_build_component_dict()` with `type_name="FileRowCount"`.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILENAME` | Yes | `filename` | str, default `""` |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | str, default `"\n"` |
| 3 | `IGNORE_EMPTY_ROW` | Yes | `ignore_empty_row` | bool, default `false` |
| 4 | `ENCODING` | Yes | `encoding` | str, default `"ISO-8859-15"` per _java.xml |
| 5 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default `false` |
| 6 | `LABEL` | Yes | `label` | Framework param, str, default `""` |

**Phantom parameter removed**: `DIE_ON_ERROR` was previously extracted but is NOT in `tFileRowCount_java.xml`. Removed from converter output.

**Summary**: 4 of 4 unique parameters extracted (100%) + 2 framework params. 1 needs_review entry for encoding default mismatch.

### 4.2 Schema Extraction

Utility component -- no data flow schema. Schema is `{"input": [], "output": []}` per D-56.

### 4.3 Expression Handling

`FILENAME` may contain context variables (`context.inputDir + "/data.csv"`) or Java expressions. These are extracted as-is by `_get_str()` and resolved at runtime by the engine's `context_manager.resolve_dict()` and `_resolve_java_expressions()`.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-FRC-005 | ~~P0~~ | **FIXED** -- `talend_to_v1` parser uses safe `_get_str()`/`_get_bool()` helpers |
| CONV-FRC-001 | ~~P1~~ | **SUPERSEDED** -- `DIE_ON_ERROR` is phantom param (not in _java.xml); removed from converter |
| CONV-FRC-002 | ~~P2~~ | **FIXED** -- `ENCODING` default corrected to `ISO-8859-15` per _java.xml |
| CONV-FRC-006 | ~~P2~~ | **FIXED** -- Uses `_get_str()` helper for quote stripping |
| CONV-FRC-003 | ~~P3~~ | **FIXED** -- Uses `_get_str()` helper for FILENAME quote stripping |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `encoding` | Engine default is `UTF-8` but _java.xml default is `ISO-8859-15` | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Count rows in file | **Yes** | High | `_process()` lines 176-188 | Line-by-line reading with `open()` |
| 2 | Ignore empty rows | **Yes** | High | `_process()` line 185 | `if ignore_empty_row and not line.strip()` |
| 3 | Encoding support | **Yes** | Medium | `_process()` line 181 | Default mismatch: engine UTF-8, Talend ISO-8859-15 |
| 4 | File existence check | **Yes** | High | `_process()` line 169 | `os.path.exists(filename)` |
| 5 | GlobalMap variables | **Yes** | High | `_process()` lines 113-117 | COUNT, NB_LINE, NB_LINE_OK, NB_LINE_REJECT all set |
| 6 | Row separator | **Yes** | High | `_count_rows()` helper | Both common (`\n`,`\r`,`\r\n`) and custom separators supported via `_ESCAPE_MAP` normalisation |
| 7 | Die on error | **N/A** | N/A | -- | DIE_ON_ERROR is a phantom parameter not present in `tFileRowCount_java.xml` |
| 8 | ERROR_MESSAGE globalMap | **N/A** | N/A | -- | Not applicable — die_on_error is phantom for this component |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-FRC-001~~ | ~~P1~~ | **RESOLVED (2026-05-01)** -- `row_separator` now used. `_ESCAPE_MAP` normalises `"\\n"` to `"\n"`. Custom separators use full-file read+split. |
| ~~ENG-FRC-002~~ | ~~P1~~ | **N/A** -- DIE_ON_ERROR is not in `tFileRowCount_java.xml`. Phantom parameter; not applicable. |
| ~~ENG-FRC-003~~ | ~~P1~~ | **N/A** -- `{id}_ERROR_MESSAGE` not relevant since die_on_error is phantom. |
| ~~ENG-FRC-005~~ | ~~P2~~ | **RESOLVED (2026-05-01)** -- Engine default now `ISO-8859-15` matching Talend _java.xml. |
| ~~ENG-FRC-006~~ | ~~P3~~ | **RESOLVED (2026-05-01)** -- Custom separators now supported. |
| PERF-FRC-002 | **P3** | Custom separator path reads entire file into memory (O(n)). Standard `\n` path streams. Acceptable for typical use cases.

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_COUNT` | Yes | **Yes** | `_process()` line 113 | Primary output. Equals rows_out (excludes empty rows when ignore_empty_row=True) |
| `{id}_NB_LINE` | Yes | **Yes** | `_process()` line 114 | Total rows read from file (rows_in) |
| `{id}_NB_LINE_OK` | Yes | **Yes** | `_process()` line 115 | Rows included in count (rows_out) |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | `_process()` line 116 | Empty rows excluded (rows_rejected) |
| `{id}_ERROR_MESSAGE` | N/A | N/A | -- | Not applicable — die_on_error is phantom for this component |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| ~~BUG-FRC-001~~ | ~~P0~~ | `base_component.py` | **RESOLVED** -- Cross-cutting `_update_global_map()` bug fixed in base class. |
| ~~BUG-FRC-002~~ | ~~P2~~ | `global_map.py` | **RESOLVED** -- Cross-cutting `GlobalMap.get()` undefined `default` fixed. |
| ~~BUG-FRC-003~~ | ~~P1~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `_process()` now returns `{'main': None}` (utility component, no DataFrame). |
| ~~BUG-FRC-004~~ | ~~P1~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `_validate_config()` rewritten to raise `ConfigurationError`; dead code removed. |
| ~~BUG-FRC-005~~ | ~~P3~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `_validate_config()` now returns `None` (raises on error per pattern). |
| ~~BUG-FRC-006~~ | ~~P1~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `row_separator` now used in `_count_rows()`. |
| ~~BUG-FRC-007~~ | ~~P2~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `UnicodeDecodeError` now wrapped as `FileOperationError` with original exception chained. |
| ~~BUG-FRC-010~~ | ~~P2~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- Empty `filename` raises `ConfigurationError`; missing file raises `FileOperationError`. |
| ~~BUG-FRC-011~~ | ~~P2~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- GlobalMap writes moved outside the file-reading try block. |
| ~~DBG-FRC-001~~ | ~~P3~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- Debug verification read removed. |
| ~~NAME-FRC-001~~ | ~~P2~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- Dual-key `or` fallback removed; single key format only. |
| ~~NAME-FRC-002~~ | ~~P2~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- All config reads use single lowercase key. |
| ~~STD-FRC-001~~ | ~~P1~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `_validate_config()` raises, not returns bool. |
| ~~STD-FRC-002~~ | ~~P1~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `_validate_config()` is now abstract-overriding and called by base class. |
| ~~STD-FRC-003~~ | ~~P2~~ | `file_row_count.py` | **RESOLVED (2026-05-01)** -- `_process()` returns `{'main': None}` per pattern. |
| SEC-FRC-001 | **P3** | `file_row_count.py` | No path traversal protection on `filename`. Acceptable for Talend-converted jobs where paths come from job config.
| BUG-FRC-005 | **P3** | `file_row_count.py:88` | `_validate_config()` returns `bool` instead of `List[str]` per METHODOLOGY.md standard. |
| DBG-FRC-001 | **P3** | `file_row_count.py:222-224` | Debug verification read in production code. Will crash due to BUG-FRC-002. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FRC-001 | **P2** | Dual key format support (`filename` or `FILENAME`) uses `or` pattern with subtle falsy-string bug. |
| NAME-FRC-002 | **P2** | Same dual-key issue for all config parameters. Inconsistent across params. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FRC-001 | **P1** | "`_validate_config()` returns `List[str]`" | Returns `bool` instead. |
| STD-FRC-002 | **P1** | "`_validate_config()` must be called" | Never called by any code path. |
| STD-FRC-003 | **P2** | "`_process()` returns `Dict` with `'main': DataFrame`" | Returns `{'main': dict}`. |

### 6.4 Debug Artifacts

DBG-FRC-001: Verification read on line 222-224 is debug code that crashes in production.

### 6.5 Security

SEC-FRC-001 (P3): No path traversal protection on `filename`. Not a concern for Talend-converted jobs.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level + instance-level logger |
| Level usage | Good -- info for start/complete, error for failures, debug for verification |
| Sensitive data | No concerns -- only file paths logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses standard Python exceptions (FileNotFoundError, PermissionError, IOError) |
| Exception chaining | Partial -- `raise ... from e` used but UnicodeDecodeError reconstructed with dummy args |
| die_on_error handling | Not implemented -- all errors raise unconditionally |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- return types annotated |
| Parameter types | Good -- standard typing used |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FRC-001 | **P3** | Buffered counting (without line storage) could marginally improve performance for very large files. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not applicable -- utility component, no data flow |
| Memory threshold | N/A -- line-by-line reading, constant memory |
| Large data handling | Good -- reads line by line regardless of file size |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 26 | `tests/converters/talend_to_v1/components/test_file_row_count.py` |
| Engine unit tests | 0 | None |
| Integration tests | Covered | `tests/converters/talend_to_v1/test_integration.py` |
| Engine unit tests | **Added 2026-05-01** | `tests/v1/engine/components/file/test_file_row_count.py` (42 tests, 9 classes) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| ~~TEST-FRC-001~~ | ~~P2~~ | **RESOLVED (2026-05-01)** -- 42 engine unit tests added across 9 test classes: TestRegistration, TestValidation, TestRowCounting, TestIgnoreEmptyRows, TestRowSeparator, TestEncoding, TestGlobalMapVariables, TestEdgeCases, TestCountRowsHelper. |

### 8.3 Recommended Test Cases

- ~~Engine: count rows in file with various encodings~~ **COVERED** (TestEncoding)
- ~~Engine: ignore_empty_row=true excludes blank lines~~ **COVERED** (TestIgnoreEmptyRows)
- ~~Engine: file not found error handling~~ **COVERED** (TestRowCounting)
- ~~Engine: encoding mismatch error handling~~ **COVERED** (TestEncoding)
- Engine: large file (>1M rows) memory behavior (PERF-FRC-001, P3)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | ~~BUG-FRC-001~~ (resolved) |
| P1 | 0 | ~~ENG-FRC-001, ENG-FRC-002, ENG-FRC-003, BUG-FRC-003, BUG-FRC-004, BUG-FRC-006~~ (all resolved) |
| P2 | 0 | ~~ENG-FRC-005, BUG-FRC-007, BUG-FRC-010, BUG-FRC-011, BUG-FRC-002, NAME-FRC-001, NAME-FRC-002, TEST-FRC-001~~ (all resolved) |
| P3 | 3 | **PERF-FRC-001** (custom separator memory), **PERF-FRC-002** (see §5.2), **SEC-FRC-001** (path traversal) |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All resolved |
| Engine (ENG) | 0 | All resolved |
| Bug (BUG) | 0 | All resolved |
| Naming (NAME) | 0 | All resolved |
| Standards (STD) | 0 | All resolved |
| Performance (PERF) | 1 | PERF-FRC-001 |
| Testing (TEST) | 0 | All resolved |
| Debug (DBG) | 0 | All resolved |
| Security (SEC) | 1 | SEC-FRC-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| ~~BUG-FRC-001~~ | `base_component.py` | **RESOLVED** -- `_update_global_map()` fixed in base class |
| ~~BUG-FRC-002~~ | `global_map.py` | **RESOLVED** -- `GlobalMap.get()` fixed |

---

## 10. Recommendations

### Immediate (Before Production)

None -- all P0/P1/P2 issues resolved as of 2026-05-01.

### Long-term (Optimization)

- SEC-FRC-001: Add path traversal protection for `filename` parameter (P3)
- PERF-FRC-001: Consider streaming-safe custom separator for very large files (P3)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talend 8.0 docs | <https://help.qlik.com/talend/en-US/components/8.0/tfilerowcount/tfilerowcount-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://github.com/Talend/tdi-studio-se> | Component definition XML (confirmed 4 unique params, no DIE_ON_ERROR) |
| Engine source | `src/v1/engine/components/file/file_row_count.py` | Feature parity analysis (229 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_row_count.py` | Converter audit (71 lines) |
| Test source | `tests/converters/talend_to_v1/components/test_file_row_count.py` | Test coverage (26 tests) |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |

---

*Report generated: 2026-03-21*
*Last updated: 2026-04-04 after gold-standard rewrite (Phase 10, Plan 07)*
