# Audit Report: tFileInputRaw / FileInputRaw

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputRaw` |
| **V1 Engine Class** | `FileInputRaw` |
| **Engine File** | `src/v1/engine/components/file/file_input_raw.py` (149 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_raw.py` |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputRaw")` decorator-based dispatch |
| **Registry Aliases** | `tFileInputRaw` |
| **Category** | File / Input |
| **Complexity** | Low -- single-file reader with 6 unique parameters |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_raw.py` | Engine implementation (149 lines) |
| `src/converters/talend_to_v1/components/file/file_input_raw.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_file_input_raw.py` | Converter tests (35 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 6 unique params + 2 framework params extracted; `_build_component_dict` pattern; 2 per-feature needs_review entries for engine gaps |
| Engine Feature Parity | **Y** | 0 | 2 | 1 | 0 | Engine reads 4 of 6 unique params; ignores as_bytearray and as_inputstream; encoding default mismatch (UTF-8 vs ISO-8859-15) |
| Code Quality | **Y** | 1 | 2 | 2 | 1 | debug_content() at INFO level; _validate_config() dead code; overly broad exception; base class cross-cutting bugs |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | No large-file protection; unconditional debug_content() overhead; DataFrame for single value |
| Testing | **Y** | 0 | 0 | 2 | 0 | 35 converter unit tests across 8 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) — no engine test coverage prevents Green |

**Overall: Yellow -- Converter fully standardized (Green); engine has known gaps documented via needs_review; engine/code quality/performance gaps keep overall at Yellow**

**Top Actions:**
1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Add as_bytearray support to engine (P1, engine gap)
3. Add as_inputstream streaming mode to engine (P1, engine gap)
4. Fix engine encoding default from UTF-8 to ISO-8859-15 (P2, engine mismatch)
5. Remove debug_content() or move to DEBUG level (P2, code quality)

---

## 3. Talend Feature Baseline

### What tFileInputRaw Does

`tFileInputRaw` reads raw data from a file and outputs it as a single field. Unlike `tFileInputDelimited` which parses structured data into columns, `tFileInputRaw` reads the entire file content as one value -- either as a string, a byte array, or an input stream. This makes it suitable for reading unstructured files like binary blobs, configuration files, templates, or any content that needs to be processed as a whole rather than line-by-line.

The component outputs a single row with one column containing the entire file content. The read mode is controlled by three mutually exclusive radio buttons: AS_STRING (default, reads as text with encoding), AS_BYTEARRAY (reads as raw bytes), and AS_INPUTSTREAM (provides a streaming cursor for large files).

**Source**: [tFileInputRaw Standard Properties](https://help.qlik.com/talend/en-US/components/7.3/file/tfileinputraw-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputRaw/tFileInputRaw_java.xml)
**Component family**: File / Input
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Output schema definition. Typically a single column. |
| 2 | File Name | `FILENAME` | FILE | `""` | Path to the file to read. Required. Supports context variables. |
| 3 | Read as String | `AS_STRING` | RADIO | `true` | Read file content as a text string using the specified encoding. Mutually exclusive with AS_BYTEARRAY and AS_INPUTSTREAM. |
| 4 | Read as ByteArray | `AS_BYTEARRAY` | RADIO | `false` | Read file content as a raw byte array. Mutually exclusive with AS_STRING and AS_INPUTSTREAM. |
| 5 | Read as InputStream | `AS_INPUTSTREAM` | RADIO | `false` | Read file content as a streaming cursor (java.io.InputStream). Mutually exclusive with AS_STRING and AS_BYTEARRAY. |
| 6 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for string read mode. Only applies when AS_STRING is true. |
| 7 | Die on Error | `DIE_ON_ERROR` | CHECK | `false` | Stop execution on error. |
| 8 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Framework param: enable statistics collection. |
| 9 | Label | `LABEL` | TEXT | `""` | Framework param: component label for display. |

### 3.2 Advanced Settings

None -- tFileInputRaw has no advanced settings tab in Talend Studio.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Single row with file content in the schema-defined column |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires after failed execution |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Number of rows output (always 1 for success, 0 for failure) |

### 3.5 Behavioral Notes

1. **ISO-8859-15 is the default encoding**, not UTF-8. This is a common Talend default for European locale support. The encoding only applies when AS_STRING is true.
2. **Mutually exclusive radio buttons**: AS_STRING, AS_BYTEARRAY, and AS_INPUTSTREAM are RADIO type -- only one can be true at a time. In Talend Studio, selecting one automatically deselects the others.
3. **Single-row output**: The component always produces exactly one output row (or zero on error). The entire file content goes into a single column.
4. **InputStream mode**: When AS_INPUTSTREAM is true, Talend provides a java.io.InputStream object that allows streaming reads of large files without loading the entire content into memory.
5. **FILENAME is required**: An empty filename will cause a runtime error in Talend.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict` per D-40 with `type_name="FileInputRaw"` per D-43. All parameters are extracted using `_get_str` and `_get_bool` helper methods from the base class.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `filename` | `_get_str`, default `""` |
| 2 | `AS_STRING` | Yes | `as_string` | `_get_bool`, default `True` |
| 3 | `AS_BYTEARRAY` | Yes | `as_bytearray` | `_get_bool`, default `False` |
| 4 | `AS_INPUTSTREAM` | Yes | `as_inputstream` | `_get_bool`, default `False` |
| 5 | `ENCODING` | Yes | `encoding` | `_get_str`, default `"ISO-8859-15"` |
| 6 | `DIE_ON_ERROR` | Yes | `die_on_error` | `_get_bool`, default `False` |
| 7 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | `_get_bool`, default `False` (framework) |
| 8 | `LABEL` | Yes | `label` | `_get_str`, default `""` (framework) |

**Summary**: 8 of 8 parameters extracted (100%). All 6 unique + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | Only when >= 0 |
| `precision` | Yes | Only when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported by `_parse_schema()` |

Schema is structured as `{"input": [], "output": [...]}` per D-41 (source component -- no input schema).

### 4.3 Expression Handling

String parameters (FILENAME, ENCODING) preserve context variable expressions as-is. The `_get_str` method strips surrounding quotes but does not evaluate expressions. Context variables like `context.filepath` are passed through to the engine for runtime resolution.

### 4.4 Converter Issues

None -- converter is fully standardized per gold standard patterns.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `as_bytearray` | Engine does not read 'as_bytearray' config key -- always reads as string or binary based on as_string only | engine_gap |
| 2 | `as_inputstream` | Engine does not read 'as_inputstream' config key -- no streaming cursor support; loads full file | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read as string | **Yes** | High | `_process()` line 117-119 | Opens file with encoding, reads content |
| 2 | Read as binary | **Partial** | Medium | `_process()` line 120-121 | Uses `as_string=False` to trigger binary mode; no separate as_bytearray config check |
| 3 | Read as InputStream | **No** | N/A | -- | No streaming cursor support; always loads full file |
| 4 | Encoding support | **Yes** | Medium | `_process()` line 118 | Engine default is UTF-8, not ISO-8859-15 |
| 5 | Die on error | **Yes** | High | `_process()` line 144-145 | Re-raises exception when die_on_error is True |
| 6 | Single-row output | **Yes** | High | `_process()` line 129 | Wraps content in single-row DataFrame |
| 7 | Statistics | **Partial** | Medium | `_process()` line 131 | Sets NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 8 | Error handling | **Yes** | High | `_process()` line 137-149 | Returns empty DataFrame on error when die_on_error=False |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIR-001 | **P1** | Engine ignores `as_bytearray` config key -- binary mode triggered only by `as_string=False`. Talend distinguishes byte[] from InputStream. |
| ENG-FIR-002 | **P1** | Engine ignores `as_inputstream` config key -- no streaming cursor support. Full file is always loaded into memory. |
| ENG-FIR-003 | **P2** | Engine encoding default is UTF-8 (line 110), Talend default is ISO-8859-15. Jobs relying on default encoding will read differently. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats(1, 1, 0)` | 1 on success, 1 on failure (Talend would set 0 on failure) |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | 1 on success, 0 on failure |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 (no reject flow) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIR-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING** -- `_update_global_map()` references undefined variable. Crashes when globalMap is set. |
| BUG-FIR-002 | **P1** | `file_input_raw.py:76-94` | `debug_content()` logs content at INFO level unconditionally. Exposes file content in production logs. |
| BUG-FIR-003 | **P1** | `file_input_raw.py:137` | Overly broad `except Exception` catches all errors including KeyboardInterrupt propagation. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIR-001 | **P2** | Output column hardcoded as `'content'` (line 129) -- should use schema-defined column name |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIR-001 | **P2** | `_validate_config()` lifecycle | Method defined (lines 46-74) but never called by base class `execute()` -- dead code |
| STD-FIR-002 | **P3** | Custom exceptions | Uses generic `Exception` instead of `FileOperationError` from engine exceptions module |

### 6.4 Debug Artifacts

`debug_content()` method (lines 76-94) is a debug helper that logs content at INFO level. Should be removed or moved to DEBUG level for production.

### 6.5 Security

| Concern | Assessment |
|---------|------------|
| Path traversal | No path validation on filename -- user-supplied paths could access arbitrary files |
| Content exposure | `debug_content()` logs raw file content at INFO level |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Correct -- `logging.getLogger(__name__)` |
| Level usage | Poor -- debug_content() uses INFO for verbose diagnostics |
| Sensitive data | Risk -- file content logged unconditionally |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Not used -- generic Exception |
| Exception chaining | Not implemented |
| die_on_error handling | Correct -- re-raises when True, returns empty DataFrame when False |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Present -- `_process()`, `_validate_config()`, `debug_content()` |
| Parameter types | Present -- `Optional[pd.DataFrame]`, `Dict[str, Any]`, `List[str]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIR-001 | **P1** | No large-file protection -- entire file loaded into memory regardless of size. No streaming support. |
| PERF-FIR-002 | **P2** | `debug_content()` called unconditionally on every string read, counting line endings even for large files. |
| PERF-FIR-003 | **P3** | DataFrame wrapping for single value is overhead -- could use simpler data structure. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not supported -- always loads full file |
| Memory threshold | None -- no file size check before loading |
| Large data handling | Risk -- multi-GB files will cause OOM |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 35 | `tests/converters/talend_to_v1/components/test_file_input_raw.py` |
| Engine unit tests | 0 | None |
| Integration tests | Included in regression guard | `tests/converters/talend_to_v1/test_converter_output_structure.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FIR-001 | **P2** | No engine unit tests for FileInputRaw |
| TEST-FIR-002 | **P2** | No error path tests for engine (die_on_error=True/False) |

### 8.3 Recommended Test Cases

1. Engine: Read text file with default encoding (ISO-8859-15)
2. Engine: Read binary file (as_string=False)
3. Engine: die_on_error=True with missing file
4. Engine: die_on_error=False with missing file (returns empty DataFrame)
5. Engine: Large file handling (memory check)
6. Engine: Non-ASCII content with various encodings

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **BUG-FIR-001** (cross-cutting) |
| P1 | 5 | **ENG-FIR-001**, **ENG-FIR-002**, **BUG-FIR-002**, **BUG-FIR-003**, **PERF-FIR-001** |
| P2 | 6 | **ENG-FIR-003**, **NAME-FIR-001**, **STD-FIR-001**, **PERF-FIR-002**, **TEST-FIR-001**, **TEST-FIR-002** |
| P3 | 2 | **STD-FIR-002**, **PERF-FIR-003** |
| **Total** | **14** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 3 | ENG-FIR-001, ENG-FIR-002, ENG-FIR-003 |
| Bug (BUG) | 3 | BUG-FIR-001, BUG-FIR-002, BUG-FIR-003 |
| Naming (NAME) | 1 | NAME-FIR-001 |
| Standards (STD) | 2 | STD-FIR-001, STD-FIR-002 |
| Performance (PERF) | 3 | PERF-FIR-001, PERF-FIR-002, PERF-FIR-003 |
| Testing (TEST) | 2 | TEST-FIR-001, TEST-FIR-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- BUG-FIR-001 |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash in base class (BUG-FIR-001, P0, cross-cutting)

### Short-term (Hardening)

1. Add `as_bytearray` support to engine -- separate byte[] output mode (ENG-FIR-001, P1)
2. Add `as_inputstream` streaming mode to engine (ENG-FIR-002, P1)
3. Remove or downgrade `debug_content()` to DEBUG level (BUG-FIR-002, P1)
4. Narrow exception handling from bare `Exception` (BUG-FIR-003, P1)
5. Add large-file protection or streaming support (PERF-FIR-001, P1)

### Long-term (Optimization)

1. Fix engine encoding default from UTF-8 to ISO-8859-15 (ENG-FIR-003, P2)
2. Use schema-defined column name instead of hardcoded 'content' (NAME-FIR-001, P2)
3. Wire `_validate_config()` into lifecycle (STD-FIR-001, P2)
4. Add engine unit tests (TEST-FIR-001, TEST-FIR-002, P2)
5. Use custom `FileOperationError` exceptions (STD-FIR-002, P3)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputRaw/tFileInputRaw_java.xml` | Parameter definitions, defaults, types |
| Talend official docs | `https://help.qlik.com/talend/en-US/components/7.3/file/tfileinputraw-standard-properties` | Feature description, behavioral notes |
| Engine source | `src/v1/engine/components/file/file_input_raw.py` | Feature parity analysis (149 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_raw.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_file_input_raw.py` | Test coverage analysis (35 tests) |

## Appendix B: Test Coverage Matrix

| Test Class | Count | Coverage Area |
|-----------|-------|---------------|
| TestRegistration | 1 | Registry lookup verification |
| TestDefaults | 6 | All 6 unique parameter defaults |
| TestParameterExtraction | 6 | All 6 unique parameter extraction |
| TestFrameworkParams | 4 | tstatcatcher_stats and label |
| TestSchema | 3 | Schema dict structure, input/output |
| TestNeedsReview | 6 | Engine gap entries count, content, severity |
| TestCompleteness | 1 | All config keys present |
| TestComponentStructure | 8 | _build_component_dict output verification |
| **Total** | **35** | |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after Phase 09 Plan 01 converter standardization*
