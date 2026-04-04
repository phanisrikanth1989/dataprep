# Audit Report: tFileInputJSON / FileInputJSON

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
| **Talend Name** | `tFileInputJSON` |
| **V1 Engine Class** | `FileInputJSON` |
| **Engine File** | `src/v1/engine/components/file/file_input_json.py` (334 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_json.py` |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputJSON")` decorator-based dispatch |
| **Registry Aliases** | `tFileInputJSON` |
| **Category** | File / Input (JSON) |
| **Complexity** | Medium -- 17 params, 3 MAPPING TABLE variants, 3 read modes, URL input |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_json.py` | Engine implementation (334 lines) |
| `src/converters/talend_to_v1/components/file/file_input_json.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_file_input_json.py` | Converter tests (61 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 17 of 17 config keys extracted (15 unique + 2 framework); 3 MAPPING TABLE variants (JSONPATH, XPATH, JSONPATH_WITHOUTPUT_LOOP); state-machine parser; `_build_component_dict` with type_name="FileInputJSON"; 3 per-feature needs_review entries; 61 converter tests across 10 test classes |
| Engine Feature Parity | **Y** | 0 | 4 | 3 | 1 | Has JSONPath extraction, URL reading, reject flow, schema type coercion, advanced separators, date checking. Missing: XPath mode, JSONPATH_WITHOUTPUT_LOOP mode; json_path_version read but unused; use_loop_as_root default mismatch; die_on_error default mismatch |
| Code Quality | **Y** | 2 | 3 | 4 | 2 | Cross-cutting base class bugs; dead validate_config(); NaN handling gaps; unused json_path_version variable; die_on_error per-row bypass; schema date key mismatch (pattern vs date_pattern) |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | Row-by-row JSONPath parsing slow for large files; list/dict serialization pass on output; no streaming mode for large JSON files |
| Testing | **Y** | 0 | 0 | 2 | 0 | 61 converter unit tests across 10 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) |

**Overall: Yellow -- Converter fully standardized (Green); engine has comprehensive JSONPath support but known gaps in XPath/no-loop modes; engine/code quality gaps keep overall at Yellow**

**Top Actions:**
1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Add XPath read mode support to engine (P1, engine gap)
3. Add JSONPATH_WITHOUTPUT_LOOP mode to engine (P1, engine gap)
4. Fix use_loop_as_root default from False to True (P1, behavioral mismatch)
5. Fix die_on_error default from True to False (P1, behavioral mismatch)

---

## 3. Talend Feature Baseline

### What tFileInputJSON Does

`tFileInputJSON` reads JSON data from a file or URL and extracts structured records using JSONPath or XPath expressions. It iterates over a loop node in the JSON structure, extracting fields from each element according to a mapping table, and outputs the extracted data as a row flow. The component is commonly used for reading REST API responses saved as files, configuration files, and hierarchical data exports.

The component supports three read modes controlled by the READ_BY parameter: JSONPATH (default, uses JSONPath expressions with a loop query), XPATH (uses XPath expressions for XML-style queries on JSON data), and JSONPATH_WITHOUTPUT_LOOP (JSONPath expressions applied directly without loop iteration). Each mode uses a different MAPPING TABLE variant for field extraction. The component also supports reading from URLs instead of local files.

**Source**: [tFileInputJSON Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/json/tfileinputjson-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputJSON/tFileInputJSON_java.xml)
**Component family**: JSON (File / Internet / Input)
**Available in**: All Talend products (Standard)
**Required JARs**: `json-path-xxx.jar`, `json-smart-xxx.jar`, `asm-xxx.jar`, `accessors-smart-xxx.jar`, `slf4j-api-xxx.jar`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Output schema definition. Each column maps to a JSONPath/XPath query in the Mapping table. |
| 2 | Read By | `READ_BY` | CLOSED_LIST | `JSONPATH` | Read mode: JSONPATH (JSONPath with loop), XPATH (XPath queries), JSONPATH_WITHOUTPUT_LOOP (direct JSONPath). |
| 3 | JSON Path Version | `JSON_PATH_VERSION` | CLOSED_LIST | `2_1_0` | JSONPath API version selection. Options: 2_1_0, 1_1_0. |
| 4 | Use URL | `USEURL` | CHECK | `false` | Read JSON from URL instead of file. Shows URLPATH, hides FILENAME. |
| 5 | URL | `URLPATH` | TEXT | `""` | URL for JSON data when USEURL=true. |
| 6 | File Name | `FILENAME` | FILE | `""` | Path to JSON file. Required unless USEURL=true. |
| 7 | Loop XPath Query | `LOOP_QUERY` | TEXT | `"/bills/bill/line"` | XPath loop expression (for XPATH mode). |
| 8 | Loop JSONPath Query | `JSON_LOOP_QUERY` | TEXT | `"$.bills.bill.line[*]"` | JSONPath loop expression (for JSONPATH mode). |
| 9 | Mapping (JSONPATH) | `MAPPING_JSONPATH` | TABLE (stride-2) | -- | SCHEMA_COLUMN + QUERY pairs for JSONPATH mode. |
| 10 | Mapping (XPATH) | `MAPPINGXPATH` | TABLE (stride-3) | -- | SCHEMA_COLUMN + QUERY + NODECHECK triplets for XPATH mode. |
| 11 | Mapping (No Loop) | `MAPPING` | TABLE (stride-2) | -- | SCHEMA_COLUMN + QUERY pairs for JSONPATH_WITHOUTPUT_LOOP mode. |
| 12 | Die On Error | `DIE_ON_ERROR` | CHECK | `false` | Stop job on parse/read error. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 13 | Advanced Separator | `ADVANCED_SEPARATOR` | CHECK | `false` | Enable custom number formatting separators. |
| 14 | Thousands Separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands grouping separator. SHOW_IF ADVANCED_SEPARATOR. |
| 15 | Decimal Separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal point separator. SHOW_IF ADVANCED_SEPARATOR. |
| 16 | Validate Date | `CHECK_DATE` | CHECK | `false` | Validate date-typed columns against schema patterns. |
| 17 | Use Loop as Root | `USE_LOOP_AS_ROOT` | CHECK | `true` | Use loop result as root for mapping queries. |
| 18 | Encoding | `ENCODING` | ENCODING_TYPE | `"UTF-8"` | Character encoding for JSON file reading. Note: UTF-8 is correct for this component (unlike most file components which default to ISO-8859-15). |
| -- | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata. Framework param. |
| -- | Label | `LABEL` | TEXT | `""` | Component label. Framework param. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully extracted JSON records |
| `REJECT` | Output | Row > Reject | Rejected records with errorCode/errorMessage columns |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |
| `ON_COMPONENT_OK` | Output (Trigger) | Trigger | Component-level success |
| `ON_COMPONENT_ERROR` | Output (Trigger) | Trigger | Component-level error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of JSON elements processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of successfully processed elements |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rejected elements |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message (not set by engine) |

### 3.5 Behavioral Notes

1. **UTF-8 encoding is correct** for this component. Unlike most Talend file components that default to ISO-8859-15, tFileInputJSON's _java.xml explicitly sets ENCODING default to UTF-8.
2. **MAPPING TABLE varies by mode**: JSONPATH uses MAPPING_JSONPATH (stride-2), XPATH uses MAPPINGXPATH (stride-3 with NODECHECK), JSONPATH_WITHOUTPUT_LOOP uses MAPPING (stride-2).
3. **USE_LOOP_AS_ROOT default is True** per _java.xml. When enabled, mapping queries are relative to the loop result, not the document root.
4. **JSONPath version** defaults to 2_1_0. This controls which JSONPath specification the Java runtime uses for expression parsing.
5. **XPATH mode** allows querying JSON using XPath syntax. JSON field names must not start with numbers when using XPath mode.
6. **REJECT flow** routes malformed records with errorCode and errorMessage columns when DIE_ON_ERROR is false.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileInputJSON")` decorator-based dispatch. All parameters are extracted using typed helpers (`_get_str`, `_get_bool`) from the `ComponentConverter` base class. The MAPPING TABLE is parsed by a module-level `_parse_mapping()` function using a state-machine approach that supports all three TABLE variants. The converter uses `_build_component_dict()` per D-40 with `type_name="FileInputJSON"` per D-43.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `READ_BY` | Yes | `read_by` | CLOSED_LIST, default "JSONPATH" |
| 2 | `JSON_PATH_VERSION` | Yes | `json_path_version` | CLOSED_LIST, default "2_1_0" |
| 3 | `USEURL` | Yes | `useurl` | CHECK, default False |
| 4 | `URLPATH` | Yes | `urlpath` | TEXT, default "" |
| 5 | `FILENAME` | Yes | `filename` | FILE, default "" |
| 6 | `LOOP_QUERY` | Yes | `loop_query` | TEXT, default "/bills/bill/line" |
| 7 | `JSON_LOOP_QUERY` | Yes | `json_loop_query` | TEXT, default "$.bills.bill.line[*]" |
| 8 | `MAPPING_JSONPATH` | Yes | `mapping` | TABLE (JSONPATH mode) |
| 9 | `MAPPINGXPATH` | Yes | `mapping` | TABLE (XPATH mode, with NODECHECK) |
| 10 | `MAPPING` | Yes | `mapping` | TABLE (JSONPATH_WITHOUTPUT_LOOP mode) |
| 11 | `DIE_ON_ERROR` | Yes | `die_on_error` | CHECK, default False |
| 12 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | CHECK, default False |
| 13 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | TEXT, default "," |
| 14 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | TEXT, default "." |
| 15 | `CHECK_DATE` | Yes | `check_date` | CHECK, default False |
| 16 | `USE_LOOP_AS_ROOT` | Yes | `use_loop_as_root` | CHECK, default True |
| 17 | `ENCODING` | Yes | `encoding` | ENCODING_TYPE, default "UTF-8" |
| -- | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework, default False |
| -- | `LABEL` | Yes | `label` | Framework, default "" |

**Summary**: 17 of 17 parameters extracted (100%). All 3 MAPPING TABLE variants handled.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Direct from SchemaColumn.name |
| `type` | Yes | Converted via `convert_type()` (Talend id_* to Python types) |
| `nullable` | Yes | Direct boolean |
| `key` | Yes | Direct boolean |
| `length` | Yes | Included when >= 0 |
| `precision` | Yes | Included when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not supported by base class `_parse_schema()` |

### 4.3 Expression Handling

Context variable references (`context.var`) and Java expressions (`{{java}}`) are passed through as-is in string parameters. The converter does not resolve expressions -- that is handled at engine runtime. All string values have surrounding quotes stripped via `_get_str()`.

### 4.4 Converter Issues

No converter issues. All parameters extracted correctly with proper defaults.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `loop_query` | Engine only supports JSONPATH mode via json_loop_query; XPath loop_query is ignored | engine_gap |
| 2 | `json_path_version` | Engine reads this key but never uses it in processing logic | engine_gap |
| 3 | `use_loop_as_root` | Engine default is False but Talend default is True -- behavioral mismatch | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | JSONPath extraction | **Yes** | High | `_process()` line 184 | Uses jsonpath_ng.ext library |
| 2 | URL reading | **Yes** | Medium | `_process()` line 169 | Basic urlopen -- no timeout, headers, auth |
| 3 | File reading | **Yes** | High | `_process()` line 176 | Standard file open with encoding |
| 4 | Reject flow | **Yes** | High | `_process()` line 244-251 | Per-row error capture to reject DataFrame |
| 5 | Schema type coercion | **Yes** | Medium | `_process()` line 215 | Integer, float, date conversion with error handling |
| 6 | Advanced separators | **Yes** | High | `_process()` line 222 | Thousands/decimal separator replacement |
| 7 | Date validation | **Partial** | Low | `_process()` line 233 | Uses 'pattern' key but converter sends 'date_pattern' -- mismatch |
| 8 | XPath mode | **No** | N/A | -- | Only JSONPATH mode supported |
| 9 | No-loop mode | **No** | N/A | -- | JSONPATH_WITHOUTPUT_LOOP not implemented |
| 10 | json_path_version | **No** | N/A | line 163 | Read from config but never used |
| 11 | use_loop_as_root | **Partial** | Low | line 188 | Default False vs Talend True |
| 12 | die_on_error | **Yes** | Medium | line 154, 282 | Default True vs Talend False |
| 13 | List/dict serialization | **Yes** | High | line 268 | json.dumps for complex values |
| 14 | Mapping normalization | **Yes** | Medium | line 93 | _normalize_mapping for Talend-style input |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIJ-001 | **P1** | Engine does not support XPATH read mode -- only JSONPATH mode via jsonpath_ng |
| ENG-FIJ-002 | **P1** | Engine does not support JSONPATH_WITHOUTPUT_LOOP mode -- always requires loop query |
| ENG-FIJ-003 | **P1** | `use_loop_as_root` defaults to False in engine but True in Talend -- mapping queries may resolve differently |
| ENG-FIJ-004 | **P1** | `die_on_error` defaults to True in engine but False in Talend -- converted jobs will fail on errors that Talend would skip |
| ENG-FIJ-005 | **P2** | `json_path_version` is read from config but never used in processing logic -- dead variable |
| ENG-FIJ-006 | **P2** | Date validation uses `pattern` key but converter sends `date_pattern` -- date validation non-functional for converted jobs |
| ENG-FIJ-007 | **P2** | `ERROR_MESSAGE` globalMap variable not set on error |
| ENG-FIJ-008 | **P3** | URL reading is bare-bones -- no timeout, custom headers, or authentication support |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` line 259 | Via base class |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` line 259 | Via base class |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` line 259 | Via base class |
| `{id}_ERROR_MESSAGE` | Yes | No | -- | Not implemented |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIJ-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crash when globalMap is set -- `UnboundLocalError` on undefined variable |
| BUG-FIJ-002 | **P0** | `global_map.py:28` | CROSS-CUTTING: `GlobalMap.get()` broken signature causes crash when called with expected arguments |
| BUG-FIJ-003 | **P1** | `file_input_json.py:233` | Date validation uses `pattern` key but converter/schema sends `date_pattern` -- date checking always skipped |
| BUG-FIJ-004 | **P1** | `file_input_json.py:148` | Mapping normalization check `mapping[0]['column'] == 'SCHEMA_COLUMN'` only works for raw Talend format, fails silently on already-normalized input |
| BUG-FIJ-005 | **P1** | `file_input_json.py:208-211` | `[*]` detection for list vs single value returns list unconditionally when no matches -- empty list instead of None |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIJ-001 | **P2** | Duplicate logger: `self.logger` and module-level `logger` both used throughout |
| NAME-FIJ-002 | **P2** | `_normalize_mapping` uses `'column'` and `'jsonpath'` as keys to detect Talend format, confusing with actual output keys |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIJ-001 | **P2** | "No dead code" | `validate_config()` defined but never called by base class `execute()` |
| STD-FIJ-002 | **P3** | "Unused imports" | `os`, `re`, `codecs` imported but never used |

### 6.4 Debug Artifacts

None found -- no print statements or TODO comments.

### 6.5 Security

JSON injection via crafted JSONPath expressions is theoretically possible but mitigated by jsonpath_ng library's parsing. URL reading via `urlopen()` has no SSRF protection (see Section 11).

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Two loggers (module-level `logger` and `self.logger`) -- should use one |
| Level usage | Appropriate: INFO for operations, DEBUG for details, ERROR for failures |
| Sensitive data | URL paths logged at INFO level -- may expose internal API endpoints |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | No custom exceptions; uses base class ComponentExecutionError |
| Exception chaining | Outer try/except catches all; inner per-row catches route to reject |
| die_on_error handling | Re-raises exception when True; returns empty DataFrames when False |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Present on all methods -- `_process`, `validate_config`, `_normalize_mapping` |
| Parameter types | `Dict`, `Any`, `List` properly typed; return types specified |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIJ-001 | **P2** | Row-by-row JSONPath parsing -- each mapping entry calls `parse(jsonpath).find(element)` per row, recompiling the expression each time |
| PERF-FIJ-002 | **P2** | `json.dumps()` serialization pass on all output columns -- iterates every cell to check for list/dict types |
| PERF-FIJ-003 | **P3** | Entire JSON file loaded into memory -- no streaming/chunked processing for large files (100MB+) |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not supported -- entire JSON loaded into memory via `json.load()` |
| Memory threshold | No limit -- large files can cause OOM |
| Large data handling | Output DataFrame holds all rows + reject DataFrame if errors; two full copies of extracted data |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 61 | `tests/converters/talend_to_v1/components/test_file_input_json.py` |
| Engine unit tests | 0 | None |
| Integration tests | Passing | `tests/converters/talend_to_v1/test_integration.py` (regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FIJ-001 | **P2** | Zero engine unit tests -- no coverage for JSONPath extraction, URL reading, reject flow, type coercion |
| TEST-FIJ-002 | **P2** | No engine integration tests with real JSON files |

### 8.3 Recommended Test Cases

1. **Happy path**: Read JSON file with JSONPath loop, verify extracted columns
2. **URL reading**: Mock URL response, verify data extraction
3. **Reject flow**: Malformed data routed to reject with correct error codes
4. **Type coercion**: Integer, float, date conversion with advanced separators
5. **Large file**: Performance test with 10K+ rows
6. **Encoding**: Non-ASCII characters with UTF-8 and other encodings
7. **Empty input**: Empty JSON file, missing file, empty mapping
8. **die_on_error**: Verify exception raised when True, empty result when False

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 2 | **BUG-FIJ-001**, **BUG-FIJ-002** |
| P1 | 7 | **ENG-FIJ-001**, **ENG-FIJ-002**, **ENG-FIJ-003**, **ENG-FIJ-004**, **BUG-FIJ-003**, **BUG-FIJ-004**, **BUG-FIJ-005** |
| P2 | 9 | **ENG-FIJ-005**, **ENG-FIJ-006**, **ENG-FIJ-007**, **NAME-FIJ-001**, **NAME-FIJ-002**, **STD-FIJ-001**, **PERF-FIJ-001**, **PERF-FIJ-002**, **TEST-FIJ-001**, **TEST-FIJ-002** |
| P3 | 3 | **ENG-FIJ-008**, **STD-FIJ-002**, **PERF-FIJ-003** |
| **Total** | **21** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 8 | ENG-FIJ-001 through ENG-FIJ-008 |
| Bug (BUG) | 5 | BUG-FIJ-001 through BUG-FIJ-005 |
| Naming (NAME) | 2 | NAME-FIJ-001, NAME-FIJ-002 |
| Standards (STD) | 2 | STD-FIJ-001, STD-FIJ-002 |
| Performance (PERF) | 3 | PERF-FIJ-001 through PERF-FIJ-003 |
| Testing (TEST) | 2 | TEST-FIJ-001, TEST-FIJ-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set -- NB_LINE stats lost |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature -- any globalMap interaction crashes |
| XCUT-004 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- if tFileInputJSON runs inside iterate loop, config modified on first pass |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash (P0, cross-cutting, BUG-FIJ-001)
2. Fix `GlobalMap.get()` broken signature (P0, cross-cutting, BUG-FIJ-002)

### Short-term (Hardening)

3. Add XPath read mode support (P1, ENG-FIJ-001)
4. Add JSONPATH_WITHOUTPUT_LOOP mode (P1, ENG-FIJ-002)
5. Fix `use_loop_as_root` default to True (P1, ENG-FIJ-003)
6. Fix `die_on_error` default to False (P1, ENG-FIJ-004)
7. Fix date pattern key mismatch: `pattern` vs `date_pattern` (P1, BUG-FIJ-003)
8. Fix mapping normalization detection (P1, BUG-FIJ-004)
9. Fix list/single value detection (P1, BUG-FIJ-005)
10. Add engine unit tests (P2, TEST-FIJ-001, TEST-FIJ-002)
11. Pre-compile JSONPath expressions (P2, PERF-FIJ-001)

### Long-term (Optimization)

12. Add URL reading improvements (P3, ENG-FIJ-008)
13. Remove unused imports (P3, STD-FIJ-002)
14. Add streaming mode for large files (P3, PERF-FIJ-003)

---

## 11. Risk Assessment

This section is included because tFileInputJSON handles URL-based data fetching, file system access, and complex JSONPath expression evaluation -- areas with security and reliability implications for production deployment.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SSRF via USEURL | Medium | High -- attacker-controlled URL can probe internal services | Validate URL against allowlist; reject private/internal IP ranges; add timeout |
| JSONPath injection | Low | Medium -- crafted JSONPath could cause excessive computation or unexpected data access | jsonpath_ng library handles parsing safely; complex expressions may cause performance issues |
| Large file OOM | Medium | High -- entire JSON loaded into memory; 500MB file uses 1GB+ RAM | Implement streaming JSON parser; add configurable file size limit |
| Date validation bypass | High | Low -- date checking is non-functional due to pattern key mismatch; invalid dates pass through as strings | Fix date_pattern key in engine to match converter output |
| die_on_error default mismatch | High | Medium -- converted jobs fail on first error instead of skipping to reject flow | Fix engine default to False; document in migration guide |
| use_loop_as_root default mismatch | High | Medium -- mapping queries resolve from wrong root, returning incorrect data silently | Fix engine default to True; document in migration guide |
| Encoding mismatch for non-UTF-8 | Low | Medium -- explicit encoding settings work correctly; only default behavior differs from some components | No action needed -- UTF-8 default is correct for this component |

### High-Risk Job Patterns

1. **XPATH mode jobs** -- Engine does not support XPath mode. Jobs configured with READ_BY=XPATH will silently use JSONPATH, producing incorrect or empty results.
2. **JSONPATH_WITHOUTPUT_LOOP jobs** -- No-loop mode not implemented. These jobs will fail or produce unexpected results when json_loop_query is applied instead.
3. **URL reading with internal APIs** -- No SSRF protection. Jobs reading from user-controlled URLs can probe internal network services.
4. **Large JSON files (100MB+)** -- Entire file loaded into memory. Combined with row-by-row JSONPath parsing, large files will be extremely slow and may cause OOM.
5. **Date-typed columns with CHECK_DATE=true** -- Date validation is non-functional due to pattern key mismatch. Invalid dates will pass through as strings.

### Safe Usage Patterns

1. **JSONPATH mode with file input** -- The core use case works reliably. JSONPath loop queries with MAPPING_JSONPATH table produce correct results.
2. **Small to medium JSON files (< 50MB)** -- Performance and memory are acceptable for typical API response files.
3. **UTF-8 encoded files** -- Encoding default matches the engine, no mismatch.
4. **Simple type coercion (integer, float)** -- Schema-based type conversion works correctly with advanced separator support.
5. **die_on_error=True with reject flow** -- Error handling works when explicitly configured; the issue is only with the False default.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputJSON/tFileInputJSON_java.xml` | Complete parameter definitions, CLOSED_LIST values, defaults, TABLE structures |
| Official Talend docs | `https://help.qlik.com/talend/en-US/components/8.0/json/tfileinputjson-standard-properties` | Component description, behavioral notes |
| Engine source | `src/v1/engine/components/file/file_input_json.py` (334 lines) | Feature parity analysis, bug identification |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_json.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_json.py` (61 tests) | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting issue identification |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- NB_LINE/NB_LINE_OK/NB_LINE_REJECT stats lost |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature -- any globalMap interaction crashes |
| XCUT-004 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- if tFileInputJSON runs in iterate loop, config modified on first pass |

## Appendix C: MAPPING TABLE Formats

### JSONPATH Mode (MAPPING_JSONPATH)

Stride-2 TABLE with `SCHEMA_COLUMN` + `QUERY` pairs:

```
[{"elementRef": "SCHEMA_COLUMN", "value": "user_id"},
 {"elementRef": "QUERY", "value": "\"$.id\""},
 {"elementRef": "SCHEMA_COLUMN", "value": "username"},
 {"elementRef": "QUERY", "value": "\"$.name\""}]
```

Output: `[{"column": "user_id", "jsonpath": "$.id"}, {"column": "username", "jsonpath": "$.name"}]`

### XPATH Mode (MAPPINGXPATH)

Stride-3 TABLE with `SCHEMA_COLUMN` + `QUERY` + `NODECHECK` triplets:

```
[{"elementRef": "SCHEMA_COLUMN", "value": "id"},
 {"elementRef": "QUERY", "value": "\"@id\""},
 {"elementRef": "NODECHECK", "value": "false"},
 {"elementRef": "SCHEMA_COLUMN", "value": "content"},
 {"elementRef": "QUERY", "value": "\".\""},
 {"elementRef": "NODECHECK", "value": "true"}]
```

Output: `[{"column": "id", "jsonpath": "@id", "nodecheck": false}, {"column": "content", "jsonpath": ".", "nodecheck": true}]`

### JSONPATH_WITHOUTPUT_LOOP Mode (MAPPING)

Same stride-2 format as JSONPATH mode but applied without loop iteration.

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after Phase 9 converter standardization*
