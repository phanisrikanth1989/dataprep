# Audit Report: tExtractJSONFields / ExtractJSONFields

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL
> **Last updated**: 2026-04-04 after Phase 12 gold-standard rewrite

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tExtractJSONFields` |
| **V1 Engine Class** | `ExtractJSONFields` |
| **Engine File** | `src/v1/engine/components/transform/extract_json_fields.py` (364 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/extract_json_fields.py` (198 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tExtractJSONFields")` decorator-based dispatch |
| **Registry Aliases** | `ExtractJSONFields`, `tExtractJSONFields` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/extract_json_fields.py` | Engine implementation (364 lines) |
| `src/converters/talend_to_v1/components/transform/extract_json_fields.py` | Converter class (198 lines) |
| `tests/converters/talend_to_v1/components/test_extract_json_fields.py` | Converter tests (45 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 15 config keys (13 unique + 2 framework) extracted; dual-TABLE parsing (XPath MAPPING stride-3 + JSONPath MAPPING_4_JSONPATH stride-2); SCHEMA_OPT_NUM, JDK_VERSION added; 9 per-feature needs_review entries |
| Engine Feature Parity | **Y** | 1 | 4 | 3 | 1 | Hardcoded `_is_relative_query()` heuristic; no XPath mode support; no `json_field` column selection; no `use_loop_as_root`; REJECT flow incomplete |
| Code Quality | **R** | 3 | 3 | 3 | 1 | Cross-cutting `_update_global_map()` crash; `json.loads` on non-string crashes; per-mapping silent exception swallowing; hardcoded property list in `_is_relative_query()` |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | Row-by-row `iterrows()` + per-row JSONPath `parse()` calls; no caching; streaming mode loses reject output |
| Testing | **Y** | 0 | 0 | 1 | 0 | 45 converter tests (Green); zero engine unit tests |

Overall: YELLOW -- Converter fully standardized with 45 tests and dual-TABLE parsing; engine has P0 bugs and missing features preventing Green

**Top Actions**:

1. Fix NaN bypass in json.loads crash path (P0 BUG-EJF-001)
2. Fix `_update_global_map()` crash (P0 cross-cutting BUG-EJF-002)
3. Implement XPath mode extraction (P1 ENG-EJF-001)
4. Implement `json_field` column selection (P1 ENG-EJF-003)
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tExtractJSONFields Does

`tExtractJSONFields` is a Processing-family component that extracts values from a JSON string column in the input data flow using JSONPath or XPath queries, mapping them to output schema columns. It is used when an upstream component produces rows containing a JSON-formatted string field, and the job needs to extract specific nested values into separate typed output columns.

The component supports two extraction modes: **JSONPath** (default, using `$.path.notation`) and **XPath** (using `/path/notation`), selectable via the READ_BY parameter. Each mode has its own mapping table -- MAPPING_4_JSONPATH for JSONPath queries and MAPPING for XPath queries with additional NODECHECK and ISARRAY flags. The loop query defines the repetition point for extracting multiple records from a single JSON document.

**Source**: [tExtractJSONFields Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractjsonfields-standard-properties), [Talaxie GitHub _java.xml](https://github.com/nicoan/talend_components)
**Component family**: Processing
**Available in**: All Talend products (Standard)
**Required JARs**: json-path (for JSONPath mode), jackson-databind

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | Schema editor | -- | Output column definitions with extracted field types. |
| 2 | Read By | `READ_BY` | CLOSED_LIST | `"JSONPATH"` | Extraction mode: JSONPATH or XPATH. Controls which MAPPING TABLE and loop query are active. |
| 3 | JSONPath Library Version | `JSON_PATH_VERSION` | CLOSED_LIST | `"2_1_0"` | JSONPath library version. Values: 2_1_0, 0_8_0. Only visible when READ_BY=JSONPATH. |
| 4 | Source | `JSONFIELD` | PREV_COLUMN_LIST | -- | Selects which incoming column contains the JSON string to extract from. |
| 5 | Loop XPath Query | `LOOP_QUERY` | TEXT | `"/bills/bill/line"` | XPath loop expression. Active when READ_BY=XPATH. Defines the repeating node. |
| 6 | Loop JSONPath Query | `JSON_LOOP_QUERY` | TEXT | `"$.bills.bill.line[*]"` | JSONPath loop expression. Active when READ_BY=JSONPATH. Defines the repeating array. |
| 7 | Mapping (XPath) | `MAPPING` | TABLE (stride-3) | -- | XPath mode: QUERY (xpath expression), NODECHECK (bool), ISARRAY (bool). Active when READ_BY=XPATH. |
| 8 | Mapping (JSONPath) | `MAPPING_4_JSONPATH` | TABLE (stride-2) | -- | JSONPath mode: SCHEMA_COLUMN, QUERY. BASED_ON_SCHEMA=true. Active when READ_BY=JSONPATH. |
| 9 | Die On Error | `DIE_ON_ERROR` | CHECK | `false` | When checked, extraction errors stop the job. |
| 10 | Reject Schema | `SCHEMA_REJECT` | SCHEMA_TYPE | -- | Schema for reject output (errorCode, errorMessage columns). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 11 | Schema Optimization Number | `SCHEMA_OPT_NUM` | TEXT (HIDDEN) | `"100"` | Hidden parameter for Talend internal schema optimization. |
| 12 | Encoding | `ENCODING` | ENCODING_TYPE | `"UTF-8"` | Character encoding for JSON parsing. |
| 13 | Use Loop as Root | `USE_LOOP_AS_ROOT` | CHECK | `true` | When true, JSONPath queries within mapping are relative to the loop node. |
| 14 | Split List | `SPLIT_LIST` | CHECK (HIDDEN) | `true` | Hidden. When true, arrays in extracted values are split into separate rows. |
| 15 | JDK Version | `JDK_VERSION` | CLOSED_LIST | `"JDK_8"` | JDK version for XPath processing. Values: JDK_8, JDK_11. Only visible when READ_BY=XPATH. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Incoming data with JSON string column |
| `FLOW` (Main) | Output | Row > Main | Extracted fields as separate columns |
| `REJECT` | Output | Row > Reject | Rows that failed JSON extraction (with errorCode/errorMessage) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful component execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires if component execution fails |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully extracted |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows that failed extraction |

### 3.5 Behavioral Notes

1. **Dual extraction mode**: READ_BY controls whether XPATH or JSONPATH queries are used. Each mode has its own loop query and mapping table.
2. **MAPPING_4_JSONPATH uses BASED_ON_SCHEMA=true**: Schema column names are auto-populated from the schema definition; the TABLE stores only the QUERY expression. XmlParser may still produce SCHEMA_COLUMN entries for compatibility.
3. **XPath MAPPING has stride-3**: Each mapping row includes QUERY (XPath expression), NODECHECK (boolean for node existence check), and ISARRAY (boolean for array handling).
4. **Loop query defines repetition**: For JSONPath mode, `$.bills.bill.line[*]` iterates over each element in the array. For XPath mode, `/bills/bill/line` iterates over each matching node.
5. **USE_LOOP_AS_ROOT**: When true (default), mapping queries are relative to the current loop node. When false, they are relative to the document root.
6. **SPLIT_LIST (hidden)**: When true (default), array-valued extractions produce multiple output rows. When false, arrays are kept as a single value.
7. **JDK_VERSION**: Only relevant for XPath mode. Controls which JDK XPath implementation is used (JDK 8 vs JDK 11 have different XPath 2.0 support).
8. **Default encoding is UTF-8**: Unlike many Talend components that default to ISO-8859-15.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict()` with `type_name="ExtractJSONFields"`. Two module-level TABLE parsers handle the dual mapping modes: `_parse_mapping_xpath()` for stride-3 XPath MAPPING and `_parse_mapping_jsonpath()` for stride-2 JSONPath MAPPING_4_JSONPATH. Both use elementRef-based parsing (not positional stride).

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SCHEMA` | Yes | (schema) | Via `_parse_schema()` -- passthrough (input=output) |
| 2 | `READ_BY` | Yes | `read_by` | CLOSED_LIST, default "JSONPATH" |
| 3 | `JSON_PATH_VERSION` | Yes | `json_path_version` | CLOSED_LIST, default "2_1_0" |
| 4 | `JSONFIELD` | Yes | `jsonfield` | PREV_COLUMN_LIST, default "" |
| 5 | `LOOP_QUERY` | Yes | `loop_query` | Default "/bills/bill/line" |
| 6 | `JSON_LOOP_QUERY` | Yes | `json_loop_query` | Default "$.bills.bill.line[*]" |
| 7 | `MAPPING` | Yes | `mapping` | TABLE stride-3: QUERY, NODECHECK, ISARRAY |
| 8 | `MAPPING_4_JSONPATH` | Yes | `mapping_4_jsonpath` | TABLE stride-2: SCHEMA_COLUMN, QUERY |
| 9 | `DIE_ON_ERROR` | Yes | `die_on_error` | CHECK, default False |
| 10 | `SCHEMA_OPT_NUM` | **REMOVED** | ~~schema_opt_num~~ | Hidden/design-time param -- removed from converter |
| 11 | `ENCODING` | Yes | `encoding` | ENCODING_TYPE, default "UTF-8" |
| 12 | `USE_LOOP_AS_ROOT` | Yes | `use_loop_as_root` | CHECK, default True |
| 13 | `SPLIT_LIST` | **REMOVED** | ~~split_list~~ | Hidden/design-time param -- removed from converter |
| 14 | `JDK_VERSION` | **REMOVED** | ~~jdk_version~~ | Hidden/design-time param -- removed from converter |
| 15 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework, default False |
| 16 | `LABEL` | Yes | `label` | Framework, default "" |

**Summary**: 13 of 16 extractable parameters extracted. 3 hidden/design-time params removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Direct from SchemaColumn |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Direct from SchemaColumn |
| `key` | Yes | Direct from SchemaColumn |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not in SchemaColumn dataclass |

### 4.3 Expression Handling

Context variables (`context.var_name`) and Java expressions within parameter values are passed through as-is in string form. The converter does not evaluate expressions -- they are preserved for the engine's expression resolver.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-EJF-001 | ~~P1~~ | **SUPERSEDED** -- Old dual-parser conflict eliminated by dedicated talend_to_v1 converter |
| CONV-EJF-002 | ~~P1~~ | **SUPERSEDED** -- ElementRef-based MAPPING_4_JSONPATH parsing replaces fragile stride-2 |
| CONV-EJF-003 | ~~P1~~ | **SUPERSEDED** -- Both LOOP_QUERY and JSON_LOOP_QUERY extracted as independent keys |
| CONV-EJF-004 | ~~P2~~ | **SUPERSEDED** -- Quote stripping handled by `_get_str()` and TABLE parser `strip('"')` |
| CONV-EJF-005 | ~~P1~~ | **SUPERSEDED** -- Boolean params use `_get_bool()` returning Python bools |
| CONV-EJF-006 | ~~P2~~ | **SUPERSEDED** -- Schema passthrough via `_parse_schema()` |
| CONV-EJF-007 | ~~P2~~ | **SUPERSEDED** -- All defaults match _java.xml |
| CONV-EJF-008 | ~~P1~~ | **SUPERSEDED** -- json_field renamed to jsonfield per D-38 |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `read_by` | Engine does not read 'read_by' -- always uses JSONPath internally | engine_gap |
| 2 | `json_path_version` | Engine does not read 'json_path_version' config key | engine_gap |
| 3 | `jsonfield` | Engine does not read 'jsonfield' -- uses first column by default | engine_gap |
| 4 | `json_loop_query` | Engine does not read 'json_loop_query' -- only uses loop_query | engine_gap |
| 5 | `encoding` | Engine does not read 'encoding' config key | engine_gap |
| 6 | `use_loop_as_root` | Engine does not read 'use_loop_as_root' config key | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | JSONPath extraction | **Yes** | Medium | `_extract_fields()` line 239 | Uses `jsonpath_ng.parse()` -- different library than Talend's json-path |
| 2 | XPath extraction | **No** | N/A | -- | Engine only supports JSONPath mode |
| 3 | Loop query iteration | **Yes** | Medium | `_extract_fields()` line 258 | Falls back to whole document if no matches |
| 4 | Field mapping | **Yes** | Medium | `_extract_fields()` line 273 | Supports both `schema_column` and `column` keys |
| 5 | Die on error | **Yes** | High | `_process()` line 183 | Raises ComponentExecutionError when true |
| 6 | Reject flow | **Partial** | Low | `_process()` line 191 | Basic reject with errorJSONField/errorCode/errorMessage but non-standard column names |
| 7 | Use loop as root | **No** | N/A | -- | Not read from config; hardcoded `_is_relative_query()` heuristic |
| 8 | Split list | **No** | N/A | -- | Wildcard queries preserve arrays but no configurable split |
| 9 | JSON field selection | **No** | N/A | -- | Always uses first column (`row[0]`) |
| 10 | Encoding | **No** | N/A | -- | Not configurable; uses Python default |
| 11 | Schema opt num | **No** | N/A | -- | Internal Talend param, not relevant for engine |
| 12 | JDK version | **No** | N/A | -- | Only relevant for XPath mode which is not implemented |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-EJF-001 | **P1** | No XPath mode support -- READ_BY=XPATH jobs cannot execute |
| ENG-EJF-002 | **P0** | `_is_relative_query()` uses hardcoded property list instead of USE_LOOP_AS_ROOT config -- breaks for any non-hardcoded property names |
| ENG-EJF-003 | **P1** | Always reads JSON from `row[0]` instead of the column specified by JSONFIELD |
| ENG-EJF-004 | **P1** | Different JSONPath library (`jsonpath_ng` vs Talend's `json-path` Java) -- subtle syntax differences possible |
| ENG-EJF-005 | **P1** | REJECT flow uses non-standard column names (`errorJSONField` instead of Talend's error columns) |
| ENG-EJF-006 | **P2** | No SPLIT_LIST support -- array-valued extractions may behave differently |
| ENG-EJF-007 | **P2** | No encoding configuration -- assumes Python default string handling |
| ENG-EJF-008 | **P2** | Fallback to entire JSON document when loop query matches nothing -- Talend would produce 0 rows |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` line 220 | Via base class |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` line 220 | rows_out count |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` line 220 | reject count |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-EJF-001 | **P0** | `_process():170` | `json.loads(row[0])` crashes on NaN/None values -- pandas `iterrows()` converts None to NaN which is not a valid JSON string. CROSS-CUTTING with NaN handling issue. |
| BUG-EJF-002 | **P0** | base_component.py | `_update_global_map()` crash when globalMap is set -- affects all components. CROSS-CUTTING. |
| BUG-EJF-003 | **P0** | `_extract_fields():289` | `_is_relative_query()` uses hardcoded list of 5 property names (`$.skill`, `$.level`, `$.name`, `$.value`) and a string check for `$.employee` -- completely unreliable for real-world jobs |
| BUG-EJF-004 | **P1** | `_process():165` | `input_data.iterrows()` causes type demotion -- Decimal becomes float64, datetime64 becomes object |
| BUG-EJF-005 | **P1** | `_extract_fields():322` | Silent exception swallowing in per-mapping try/except -- sets empty string on failure without proper logging of the actual extraction error context |
| BUG-EJF-006 | **P2** | `_process():208` | `json.dumps(v)` serialization of complex objects creates double-serialized strings if downstream re-parses -- fragile data pipeline |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-EJF-001 | **P2** | REJECT output uses `errorJSONField` (camelCase) instead of standard `error_json_field` (snake_case) |
| NAME-EJF-002 | **P3** | Method `_is_relative_query` is misleadingly named -- it is actually a hardcoded property filter |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-EJF-001 | **P2** | "No hardcoded business logic" | `_is_relative_query()` has hardcoded property names that only work for specific demo data |

### 6.4 Debug Artifacts

Multiple `logger.debug()` statements with detailed intermediate state are present. While not problematic, the volume is excessive (12+ debug calls in `_extract_fields` alone). Some include full data dumps (`{item}`, `{row.values}`) which could log sensitive data.

### 6.5 Security

| Concern | Assessment |
| --------- | ------------ |
| JSONPath injection | Low risk -- `jsonpath_ng.parse()` compiles to AST, limited injection surface |
| Path traversal | N/A -- no file system access |
| Data logging | `logger.debug()` logs full JSON data and extracted values -- sensitive data exposure risk in debug mode |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | **Good** -- module-level `logging.getLogger(__name__)` |
| Level usage | **Excessive** -- 20+ debug statements in a 364-line file |
| Sensitive data | **Concern** -- full JSON payloads logged at debug level |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | **Good** -- uses ComponentExecutionError, ConfigurationError |
| Exception chaining | **Good** -- `from e` used correctly |
| die_on_error handling | **Good** -- raises ComponentExecutionError when true, adds to reject when false |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | **Good** -- all methods have return type hints |
| Parameter types | **Good** -- explicit types on all parameters |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-EJF-001 | **P1** | `iterrows()` row-by-row processing defeats pandas vectorization -- 100-1000x slower on large datasets |
| PERF-EJF-002 | **P2** | `jsonpath_ng.parse()` called per-mapping per-row -- should be compiled once and reused |
| PERF-EJF-003 | **P3** | `json.dumps()` serialization pass on every column of every row -- unnecessary for non-complex types |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | **Not supported** -- base class HYBRID mode would chunk input but `_process()` accumulates all results in `main_output` list |
| Memory threshold | **No limit** -- large JSON documents produce unbounded `extracted_rows` lists |
| Large data handling | **Poor** -- row-by-row + per-row JSONPath parsing is both CPU-bound and memory-accumulating |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 45 | `tests/converters/talend_to_v1/components/test_extract_json_fields.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (covered by regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-EJF-001 | **P1** | No engine unit tests -- zero coverage of `ExtractJSONFields._process()`, `_extract_fields()`, `_is_relative_query()` |

### 8.3 Recommended Test Cases

1. **Engine happy path**: JSON with loop query producing multiple rows
2. **NaN/None input**: Verify behavior when input column is NaN
3. **Empty JSON document**: `{}` and `[]` as input
4. **Nested JSON extraction**: Deep path queries like `$.a.b.c.d`
5. **Array extraction with split_list**: Verify array values produce multiple rows
6. **Large JSON (>10MB)**: Memory and performance baseline
7. **Malformed JSON**: Invalid JSON strings with die_on_error True/False
8. **Encoding edge cases**: Non-UTF-8 encoded JSON strings

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **BUG-EJF-001**, **BUG-EJF-002**, **BUG-EJF-003** |
| P1 | 6 | **ENG-EJF-001**, **ENG-EJF-003**, **ENG-EJF-004**, **ENG-EJF-005**, **BUG-EJF-004**, **BUG-EJF-005**, **PERF-EJF-001**, **TEST-EJF-001** |
| P2 | 6 | **ENG-EJF-006**, **ENG-EJF-007**, **ENG-EJF-008**, **BUG-EJF-006**, **NAME-EJF-001**, **STD-EJF-001**, **PERF-EJF-002** |
| P3 | 2 | **NAME-EJF-002**, **PERF-EJF-003** |
| **Total** | **17** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All ~~superseded~~ |
| Engine (ENG) | 8 | ENG-EJF-001 through ENG-EJF-008 |
| Bug (BUG) | 6 | BUG-EJF-001 through BUG-EJF-006 |
| Naming (NAME) | 2 | NAME-EJF-001, NAME-EJF-002 |
| Standards (STD) | 1 | STD-EJF-001 |
| Performance (PERF) | 3 | PERF-EJF-001 through PERF-EJF-003 |
| Testing (TEST) | 1 | TEST-EJF-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set (BUG-EJF-002) |
| XCUT-002 | `base_component.py:iterrows` | Type demotion through iterrows/Series reconstruction (BUG-EJF-004) |
| XCUT-003 | Multiple components | `iterrows()` anti-pattern 100-1000x performance degradation (PERF-EJF-001) |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-EJF-001 (P0)**: Add NaN/None guard before `json.loads()` -- check `pd.isna(row[0])` and skip or reject
2. **BUG-EJF-002 (P0)**: Fix `_update_global_map()` crash in base class (cross-cutting)
3. **BUG-EJF-003 (P0)**: Replace `_is_relative_query()` hardcoded heuristic with `use_loop_as_root` config key

### Short-term (Hardening)

1. **ENG-EJF-001 (P1)**: Implement XPath extraction mode for READ_BY=XPATH jobs
2. **ENG-EJF-003 (P1)**: Read column from `jsonfield` config instead of hardcoded `row[0]`
3. **ENG-EJF-005 (P1)**: Standardize REJECT column names to match Talend conventions
4. **PERF-EJF-001 (P1)**: Replace `iterrows()` with vectorized JSON extraction (apply or list comprehension)
5. **TEST-EJF-001 (P1)**: Add engine unit test suite

### Long-term (Optimization)

1. **PERF-EJF-002 (P2)**: Cache compiled JSONPath expressions -- compile once per mapping, reuse across rows
2. **ENG-EJF-006 (P2)**: Implement SPLIT_LIST support for array-valued extractions
3. **NAME-EJF-002 (P3)**: Rename `_is_relative_query()` to reflect actual behavior or remove entirely

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| JSON injection via crafted JSONPath expressions | Low | Medium | `jsonpath_ng` compiles to AST -- limited injection surface, but untrusted user input in queries should be validated |
| Large JSON document memory consumption | High | High | No streaming support; row-by-row + per-row JSONPath creates O(rows * doc_size) memory pressure; add size limits |
| Encoding mismatches (UTF-8 default vs non-UTF-8 input) | Medium | Medium | Engine ignores encoding config; non-UTF-8 JSON will cause `json.loads()` UnicodeDecodeError or silent corruption |
| JSONPath vs XPath mode switching edge cases | Medium | High | Converter correctly separates both modes, but engine only supports JSONPath -- XPath jobs will fail silently with empty results |
| split_list behavior with nested arrays | Medium | Medium | Talend splits arrays into rows by default; engine preserves arrays as values -- output row count will differ |
| Hardcoded `_is_relative_query()` breaks for production data | High | High | Only works with demo data property names; any real-world JSON structure with different property names will use wrong query context |

### High-Risk Job Patterns

1. **XPath mode jobs**: Any job with READ_BY=XPATH will fail -- engine only supports JSONPath
2. **Large JSON documents (>100MB)**: No streaming, no size limits -- OOM risk
3. **Non-UTF-8 encoded JSON**: Encoding config is ignored -- will crash or corrupt
4. **Deep nested queries with USE_LOOP_AS_ROOT=false**: Engine uses hardcoded heuristic instead of config
5. **Array-valued extractions**: SPLIT_LIST behavior differs from Talend -- output shape mismatch

### Safe Usage Patterns

1. **Small-to-medium JSON (< 10MB per document)**: Memory manageable
2. **JSONPath mode with simple dot-notation queries**: Best supported path
3. **Single-level array iteration with [*]**: Loop query works correctly
4. **die_on_error=true with validation**: Catches extraction failures early

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | <https://help.qlik.com/talend/en-US/components/8.0/processing/textractjsonfields-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://github.com/nicoan/talend_components> | Full parameter list with types and defaults |
| Engine source | `src/v1/engine/components/transform/extract_json_fields.py` | Feature parity analysis (364 lines) |
| Converter source | `src/converters/talend_to_v1/components/transform/extract_json_fields.py` | Converter audit (198 lines) |
| Test suite | `tests/converters/talend_to_v1/components/test_extract_json_fields.py` | 45 tests, 8 test classes |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects NB_LINE stats |
| XCUT-002 | `base_component.py:iterrows` | Type demotion Decimal->float64, datetime64->object during extraction |
| XCUT-003 | Multiple components | `iterrows()` anti-pattern -- 100-1000x performance degradation |
| XCUT-004 | `base_component.py:validate_schema` | Inverted nullable logic -- `nullable=True` triggers `fillna(0)` |

---

*Report generated: 2026-03-21*
*Last updated: 2026-04-04 after hidden/design-time param removal*
