# Audit Report: tExtractJSONFields / ExtractJSONFields

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tExtractJSONFields` |
| **V1 Engine Class** | `ExtractJSONFields` |
| **Engine File** | `src/v1/engine/components/transform/extract_json_fields.py` (364 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_textract_json_fields()` (lines 2448-2478) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tExtractJSONFields':` (line 327) |
| **Registry Aliases** | `ExtractJSONFields`, `tExtractJSONFields` (registered in `src/v1/engine/engine.py` lines 121-122) |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/extract_json_fields.py` | Engine implementation (364 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2448-2478) | Dedicated `parse_textract_json_fields()` parser for Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 327-328) | Dispatch -- dedicated `elif` branch for `tExtractJSONFields` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ComponentExecutionError`, `ConfigurationError`, `DataValidationError`) |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 6: `from .extract_json_fields import ExtractJSONFields`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 2 | 1 | 9 of 14 Talend params extracted; mapping table parsed with fragile stride-2 assumption ignoring `elementRef` attribute; XPath mode unsupported |
| Engine Feature Parity | **Y** | 1 | 4 | 3 | 1 | Hardcoded `_is_relative_query()` heuristic; no XPath; no `use_loop_as_root` implementation; no `json_field` column selection; reject flow present but incomplete |
| Code Quality | **R** | 3 | 4 | 3 | 2 | Cross-cutting `_update_global_map()` crash; `GlobalMap.get()` crash; hardcoded property list; `json.loads` on non-string crashes; per-mapping silent exception swallowing; reject memory bomb on large documents |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | Row-by-row `iterrows()` + per-row JSONPath `parse()` calls; no caching; streaming mode loses reject output |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tExtractJSONFields Does

`tExtractJSONFields` is a standard Processing family component that extracts desired data from JSON fields in an incoming data flow using JSONPath or XPath queries. It is an **intermediate** component -- it requires an upstream connection providing rows with JSON data, and it outputs extracted fields to downstream components. The component iterates over JSON structures using a configurable loop query and maps nested fields to output schema columns.

**Source**: [tExtractJSONFields Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractjsonfields-standard-properties), [tExtractJSONFields Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractjsonfields), [Uma's Blog -- JSON Path Expressions](http://umashanthan.blogspot.com/2015/11/json-path-expression-for.html)

**Component family**: Processing
**Available in**: All Talend products (Standard). Also available in Spark Batch, Spark Streaming variants.
**Required JARs**: JSONPath library JARs (version-dependent), Nashorn JAR (for XPath mode on JDK 11+)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions for output structure. Must match mapping column names. |
| 3 | Read By | `READ_BY` | Enum | JsonPath | Extraction method: `JsonPath` or `Xpath`. Determines which query syntax is used for loop and mapping. |
| 4 | JSONPath API Version | `JSON_PATH_VERSION` / `API_VERSION` | Enum | Latest (2_1_0) | JSONPath library version selection. Affects query syntax support. Only visible when `READ_BY=JsonPath`. |
| 5 | Loop JSONPath Query | `LOOP_QUERY` / `JSON_LOOP_QUERY` | String (Expression) | -- | **Mandatory**. JSONPath expression for the loop node, e.g., `"$.store.goods.book[*]"`. Defines the iteration context for field extraction. Each match produces one output row. |
| 6 | Loop XPath Query | `LOOP_XPATH_QUERY` | String (Expression) | -- | **Mandatory (XPath mode)**. XPath expression for the loop node. Only visible when `READ_BY=Xpath`. |
| 7 | Mapping Table | `MAPPING_4_JSONPATH` | Table | -- | Column-to-JSONPath mappings. Each row maps a schema column to a JSONPath query expression. Auto-populated from schema. |
| 8 | JSON Field | `JSONFIELD` | String | First column | Specifies which input column contains the JSON data to parse. If not set, uses the first column. |
| 9 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on extraction error. When unchecked, failed rows are routed to the REJECT flow (if connected) or silently dropped. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 10 | Use Loop Node as Root | `USE_LOOP_AS_ROOT` | Boolean (CHECK) | `false` | When enabled, restricts mapping queries to children of the loop node. When disabled, mapping queries are executed against the full JSON document. Affects query context resolution. |
| 11 | Split List | `SPLIT_LIST` | Boolean (CHECK) | `false` | When a JSONPath query returns an array, split each element into a separate output row rather than serializing the array. |
| 12 | Encoding | `ENCODING` | Dropdown / Custom | `UTF-8` | Character encoding for JSON data handling. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher. Rarely used. |
| 14 | Label | `LABEL` | String | -- | Text label for the component in Talend Studio. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Incoming rows containing JSON data in one column. Required -- component cannot function without upstream data. |
| `FLOW` (Main) | Output | Row > Main | Successfully extracted rows matching the output schema. One output row per loop query match per input row. |
| `REJECT` | Output | Row > Reject | Rows that failed JSON parsing or field extraction. Includes ALL original schema columns (with partial data) PLUS `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows processed. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output via FLOW. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to REJECT flow. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred. |

### 3.5 Behavioral Notes

1. **Loop query semantics**: The loop query defines the iteration context. For `$.data[*]`, each array element under `data` produces one output row. If the loop query matches zero elements, the input row produces zero output rows (NOT an error).

2. **Mapping query context**: When `USE_LOOP_AS_ROOT=true`, mapping queries like `$.name` are resolved relative to the current loop item. When `false`, `$.name` resolves against the full JSON document. This distinction is critical for correct field extraction.

3. **REJECT flow**: When `DIE_ON_ERROR=false` and a REJECT link is connected, rows that fail JSON parsing (malformed JSON) or field extraction are sent to REJECT with `errorCode` and `errorMessage`. When REJECT is NOT connected, errors are silently dropped.

4. **JSONPath vs XPath**: The `READ_BY` parameter controls which query syntax is used. JSONPath is the modern default; XPath is legacy. The two modes use different loop and mapping parameters.

5. **JSON Field selection**: The `JSONFIELD` parameter specifies which input column contains JSON data. When not set, the component uses the first column. This is important when the input flow has multiple columns.

6. **Array handling**: When a JSONPath query returns multiple values (array), Talend serializes the array as a JSON string in the output column. With `SPLIT_LIST=true`, each element becomes a separate output row instead.

7. **NB_LINE semantics**: `NB_LINE` counts INPUT rows processed, not output rows. Since one input row can produce multiple output rows (via loop query array expansion), `NB_LINE_OK` may exceed `NB_LINE`.

8. **Null/missing fields**: When a mapping query matches no value in the current loop item, Talend sets the output column to null. This differs from setting it to empty string.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_textract_json_fields()` in `component_parser.py` lines 2448-2478). This is dispatched correctly via `converter.py` line 327: `elif component_type == 'tExtractJSONFields': component = self.component_parser.parse_textract_json_fields(node, component)`.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` for generic parameter extraction
2. Then calls `component_parser.parse_textract_json_fields(node, component)` for tExtractJSONFields-specific parameters
3. `parse_textract_json_fields()` uses local `get_param()` helper to extract `elementParameter` values
4. Mapping table is parsed from `MAPPING_4_JSONPATH` `elementValue` children with stride-2 assumption

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `READ_BY` | Yes | `read_by` | 2455 | Default `'JSONPATH'`. Extracted but **never used by engine** -- engine always uses JSONPath. |
| 2 | `JSON_PATH_VERSION` | Yes | `json_path_version` | 2456 | Default `'2_1_0'`. Extracted but **never used by engine**. |
| 3 | `LOOP_QUERY` / `JSON_LOOP_QUERY` | Yes | `loop_query` | 2458-2461 | Tries `LOOP_QUERY` first, falls back to `JSON_LOOP_QUERY`. Strips surrounding quotes. |
| 4 | `DIE_ON_ERROR` | Yes | `die_on_error` | 2462 | Boolean conversion from string `'true'/'false'`. Correct. |
| 5 | `ENCODING` | Yes | `encoding` | 2463 | Default `'UTF-8'`. Matches Talend default for this component. |
| 6 | `USE_LOOP_AS_ROOT` | Yes | `use_loop_as_root` | 2464 | Boolean conversion. Extracted but **not implemented by engine**. |
| 7 | `SPLIT_LIST` | Yes | `split_list` | 2465 | Boolean conversion. Extracted but **not implemented by engine**. |
| 8 | `JSONFIELD` | Yes | `json_field` | 2466 | Extracted but **engine always uses first column** (hardcoded `row[0]`). |
| 9 | `MAPPING_4_JSONPATH` | Yes | `mapping` | 2468-2477 | Parsed as list of `{schema_column, query}` dicts. See issues below. |
| 10 | `LOOP_XPATH_QUERY` | **No** | -- | -- | XPath loop query not extracted. XPath mode completely unsupported. |
| 11 | `MAPPING_XPATH` | **No** | -- | -- | XPath mapping queries not extracted. |
| 12 | `MAPPING_GET_NODES` | **No** | -- | -- | XPath-specific. Not extracted. |
| 13 | `MAPPING_IS_ARRAY` | **No** | -- | -- | XPath-specific array flag not extracted. |
| 14 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority). |

**Summary**: 9 of 14 parameters extracted (64%). 5 missing parameters relate to XPath mode (3), runtime metadata (1), and label (1). The critical JSONPath parameters are all extracted.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` for both FLOW and REJECT connectors.

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name |
| `type` | Yes | Converted to Python types via `ExpressionConverter.convert_type()` |
| `nullable` | Yes | Boolean from string |
| `key` | Yes | Boolean from string |
| `length` | Yes | Integer if present |
| `precision` | Yes | Integer if present |
| `pattern` (date) | Yes | Java-to-Python date pattern conversion |
| `default` | **No** | Column default not extracted |
| `talendType` | **No** | Original Talend type not preserved |

### 4.3 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-EJF-001 | **P1** | **Mapping table stride-2 parsing is fragile**: Lines 2472-2476 assume `elementValue` children alternate between schema column and query in strict pairs. If the Talend XML structure has additional attributes (e.g., `GET_NODES`, `IS_ARRAY` from XPath mode) interleaved, or if the entry count is odd, the parser will either crash (`IndexError` at `entries[i+1]`) or silently misalign columns with queries. No bounds checking on `i+1`. |
| CONV-EJF-002 | **P2** | **XPath mode completely unsupported**: `LOOP_XPATH_QUERY`, `MAPPING_XPATH`, `MAPPING_GET_NODES`, `MAPPING_IS_ARRAY` are all unextracted. Jobs using `READ_BY=Xpath` will produce incomplete config with no loop query. The engine will crash at runtime with "Missing required config: 'loop_query'" since XPath queries are not mapped. |
| CONV-EJF-003 | **P2** | **`json_field` extracted but engine ignores it**: Converter extracts `JSONFIELD` (line 2466) but engine hardcodes `row[0]` (line 170). If input has multiple columns and `JSONFIELD` specifies column 2, the wrong column is parsed. Silent data corruption. |
| CONV-EJF-004 | **P2** | **Schema type format violates STANDARDS.md**: Types converted to Python format (`str`, `int`) instead of Talend format (`id_String`, `id_Integer`). Same issue as other components -- cross-cutting. |
| CONV-EJF-005 | **P3** | **Misplaced comment in `_map_component_parameters()`**: Line 294 of `component_parser.py` reads `# tExtractJSONFields mapping` but the code block below (lines 295-309) handles `tExtractDelimitedFields`. This is a copy-paste error in the comment that causes developer confusion. |
| CONV-EJF-008 | **P1** | **Converter mapping parser ignores `elementRef` attribute**: Lines 2472-2476 rely on fragile positional stride-2 ordering of `elementValue` children instead of using the semantic `elementRef` attribute to distinguish schema-column entries from query entries. This means the parser assumes strict column/query alternation by position rather than by declared role. If the Talend XML emits entries in a different order, or if additional entry types are interleaved, the parser silently misaligns columns with queries. This is the root cause of CONV-EJF-001. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Parse JSON from input column | **Yes** | Medium | `_process()` line 170 | Uses `json.loads(row[0])` -- **hardcoded to first column**. Ignores `json_field` config. |
| 2 | Loop JSONPath query | **Yes** | High | `_extract_fields()` line 258 | Parses loop query, iterates matches. Each match produces one output row. |
| 3 | Field mapping extraction | **Yes** | Medium | `_extract_fields()` lines 273-329 | Supports `schema_column`/`column` and `query`/`jsonpath` key variants. |
| 4 | Die on error | **Yes** | High | `_process()` lines 182-188 | Raises `ComponentExecutionError` on row error when `die_on_error=true`. |
| 5 | REJECT flow | **Partial** | Low | `_process()` lines 191-195 | Produces reject rows with `errorJSONField`, `errorCode`, `errorMessage`. **Missing**: Does not include all original schema columns. Only captures `row[0]` as `errorJSONField`. |
| 6 | Wildcard query handling | **Yes** | Medium | `_extract_fields()` lines 305-313 | Detects `[*]` or `.*` in query string to preserve arrays. Heuristic-based, not semantic. |
| 7 | Complex object serialization | **Yes** | High | `_process()` lines 208-209 | Serializes list/dict values to JSON strings via `json.dumps()`. |
| 8 | Empty input handling | **Yes** | High | `_process()` lines 141-144 | Returns empty DataFrames for None/empty input. |
| 9 | Statistics tracking | **Yes** | Medium | `_process()` line 220 | `_update_stats(rows_in, rows_out, rows_rejected)`. NB_LINE counts input rows, NB_LINE_OK counts output rows. |
| 10 | **JSON Field column selection** | **No** | N/A | -- | `json_field` config is ignored. Always reads `row[0]`. |
| 11 | **Use Loop As Root** | **No** | N/A | -- | `use_loop_as_root` config is extracted but never read by engine. The `_is_relative_query()` heuristic partially mimics this behavior but is hardcoded to specific property names. |
| 12 | **Split List** | **No** | N/A | -- | `split_list` config is extracted but never read by engine. Array results are serialized as JSON strings, never split into separate rows. |
| 13 | **XPath mode** | **No** | N/A | -- | No XPath support at all. Only JSONPath via `jsonpath_ng` library. |
| 14 | **Query context (relative vs absolute)** | **Broken** | N/A | `_is_relative_query()` lines 341-364 | Hardcoded property-name heuristic. See BUG-EJF-003. |
| 15 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | Error message not stored in globalMap. |
| 16 | **Encoding support** | **No** | N/A | -- | `encoding` config is extracted but never used. `json.loads()` operates on Python strings (already decoded). Would be relevant if input were bytes. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-EJF-001 | **P0** | **`_is_relative_query()` is a hardcoded heuristic that silently produces wrong results**: Lines 341-364 determine whether a JSONPath query runs against the current loop item or the full document. The method uses a hardcoded list of "relative patterns" (`$.skill`, `$.level`, `$.name`, `$.value`) that is never actually referenced (dead code on lines 352-357), and a heuristic `query.count('.') <= 1 and not query.startswith('$.employee')` (line 361) that is specific to one test case. This means: (a) `$.employee.name` is treated as absolute (runs on full doc) even when the loop iterates employees; (b) `$.address` is treated as relative even when it should access the root `address` field; (c) the hardcoded `$.employee` check is specific to one test case, not a general solution. In Talend, `USE_LOOP_AS_ROOT` controls this behavior deterministically. This bug causes **silent data corruption** -- wrong values extracted without any error. |
| ENG-EJF-002 | **P1** | **No `json_field` column selection**: Engine hardcodes `row[0]` (line 170) regardless of `json_field` config. If the input DataFrame has the JSON column at index 1 or later, the wrong column is parsed. This causes either `json.loads` failure (if column 0 is not JSON) or silent extraction of wrong data (if column 0 happens to be valid but different JSON). |
| ENG-EJF-003 | **P1** | **No `use_loop_as_root` implementation**: Config value is extracted by converter but never read. The broken `_is_relative_query()` heuristic is the only mechanism, and it does not consult this config flag. |
| ENG-EJF-004 | **P1** | **No `split_list` implementation**: When a JSONPath query returns an array, Talend with `SPLIT_LIST=true` creates separate output rows per element. V1 always serializes arrays as JSON strings. Jobs relying on `SPLIT_LIST` will get a single column containing `[1, 2, 3]` instead of three separate rows. |
| ENG-EJF-005 | **P1** | **REJECT flow missing original schema columns**: Talend REJECT includes ALL schema columns (with partial data) plus `errorCode` and `errorMessage`. V1 reject only includes `errorJSONField` (raw JSON string), `errorCode`, and `errorMessage`. Downstream components expecting schema-conformant reject rows will fail. |
| ENG-EJF-006 | **P2** | **No-match loop query falls back to entire document**: When the loop query matches zero elements (line 264-266), the engine falls back to `matches = [json_data]`, processing the entire JSON document as a single item. In Talend, zero loop matches produce zero output rows. This fallback produces one spurious output row with potentially incorrect values. |
| ENG-EJF-007 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream reference. |
| ENG-EJF-008 | **P2** | **NB_LINE semantics mismatch**: `_update_stats(rows_in, rows_out, rows_rejected)` passes `rows_in` (input row count) as NB_LINE and `rows_out` (output row count including expanded rows from loop) as NB_LINE_OK. Since one input row can produce N output rows via array expansion, NB_LINE_OK can exceed NB_LINE, which is correct per Talend semantics. However, `rows_rejected` only counts input rows that failed entirely -- partial extraction failures within a single row (individual mapping queries failing) are not counted as rejects. |
| ENG-EJF-009 | **P3** | **No XPath mode**: Jobs using `READ_BY=Xpath` will fail. XPath is legacy and rarely used, but it is a documented Talend feature. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism (if `_update_global_map()` bug is fixed). |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Counts output rows (post-expansion). |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Counts input rows that failed entirely. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-EJF-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just ExtractJSONFields, since `_update_global_map()` is called by `execute()` on line 218 after every component execution. Every component will crash when globalMap is provided. |
| BUG-EJF-002 | **P0** | `src/v1/engine/global_map.py:26-28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the method signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-EJF-003 | **P0** | `src/v1/engine/components/transform/extract_json_fields.py:341-364` | **`_is_relative_query()` is a hardcoded heuristic causing silent data corruption**: The method contains a hardcoded list of "relative patterns" (`$.skill`, `$.level`, `$.name`, `$.value`) that are never actually used (dead code on lines 352-357), and a heuristic `query.count('.') <= 1 and not query.startswith('$.employee')` (line 361) that is specific to one test case. For ANY query with 2+ dots (e.g., `$.address.city`), the method returns `False`, causing the query to run against the full document instead of the current loop item. For example, with loop query `$.employees[*]` and mapping query `$.department.name`, the query runs on the full document root rather than the current employee object, producing incorrect results with no error or warning. This is not a theoretical bug -- it will silently produce wrong data for any non-trivial nested JSON structure. |
| BUG-EJF-004 | **P1** | `src/v1/engine/components/transform/extract_json_fields.py:170` | **`json.loads(row[0])` crashes on non-string values**: `row[0]` may be `NaN` (float), `None`, a numeric value, or already a parsed dict/list (if upstream component produced Python objects rather than JSON strings). `json.loads()` requires a string argument. Passing `NaN` raises `TypeError: the JSON object must be str, bytes or bytearray, not float`. Passing `None` raises `TypeError`. This is caught by the outer try/except (line 179), but with `die_on_error=true`, the entire job crashes on a single NaN cell. With `die_on_error=false`, the row is rejected, but the error message is unhelpful (`TypeError` instead of "Column value is not a valid JSON string"). |
| BUG-EJF-005 | **P1** | `src/v1/engine/components/transform/extract_json_fields.py:264-266` | **Zero loop matches fallback to entire document**: When the loop query matches zero elements, the engine falls back to `matches = [json_data]`. This produces a spurious output row. In Talend, zero matches produce zero rows. Example: `loop_query="$.nonexistent[*]"` on `{"data": [1,2,3]}` -- Talend produces 0 rows; V1 produces 1 row with the entire JSON as context, likely extracting `""` for all mapped fields. |
| BUG-EJF-006 | **P1** | `src/v1/engine/components/transform/extract_json_fields.py:71-109` | **`_validate_config()` does not validate JSONPath syntax**: Unlike other components where `_validate_config()` is dead code, this component DOES call it (line 130-134). However, it does not validate JSONPath syntax (invalid queries like `$.[[[` pass validation and crash at runtime in `_extract_fields()`), does not check `json_field` existence, and does not validate that mapping queries are parseable. |
| BUG-EJF-007 | **P2** | `src/v1/engine/components/transform/extract_json_fields.py:301-303` | **No-match fields set to empty string instead of None**: When a JSONPath query returns no matches (line 301-303), the value is set to `row[col] = ''` (empty string). In Talend, missing fields produce `null`. This difference means: (a) downstream null checks (`pd.isna()`) will not detect missing values; (b) numeric columns will contain empty strings instead of NaN, causing type conversion failures; (c) `validate_schema()` integer conversion with `pd.to_numeric(errors='coerce')` will convert `''` to NaN then `fillna(0)` to 0, masking missing data. |
| BUG-EJF-008 | **P2 -- DOWNGRADED (Not a bug)** | `src/v1/engine/components/transform/extract_json_fields.py:208-209` | **Serialization lambda NaN/None bypass is correct behavior**: The lambda `lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v` lets `NaN` and `None` pass through unchanged. This is actually correct -- `json.dumps(None)` would produce the string `'null'` which is wrong (it would inject a literal string into the output instead of preserving the Python null/NaN sentinel). The pass-through allows downstream pandas operations and `validate_schema()` to handle nulls properly. **Previously reported as a bug; downgraded after adversarial review.** |
| BUG-EJF-009 | **P2** | `src/v1/engine/components/transform/extract_json_fields.py:192` | **Reject flow accesses `row[0]` which may fail on non-integer index**: In the reject handler (line 192), `'errorJSONField': row[0]` assumes the DataFrame has integer-indexed columns. If the input DataFrame has named columns, `row[0]` accesses the first column by position (which works for positional indexing via `.iterrows()`), but if the first column contains a non-serializable value (e.g., a large binary blob), this could cause issues in downstream processing of the reject DataFrame. |
| BUG-EJF-010 | **P1** | `src/v1/engine/components/transform/extract_json_fields.py:322-325` | **Per-mapping `except Exception` silently swallows configuration errors**: The per-field extraction try/except (lines 322-325) catches all exceptions and sets the field to `''`. This means a bad JSONPath syntax error in a mapping query (e.g., `$.[[[`) fails silently on every single row, producing `''` for that column with zero visibility. There is no per-field error accumulation, no counter for how many times a mapping query failed, and the warning log (line 324) is easily lost in verbose output. A systemic configuration error (wrong JSONPath in mapping) is indistinguishable from "field not present in data". This should at minimum accumulate per-field failure counts and surface them at the end of processing. |
| BUG-EJF-011 | **P2** | `src/v1/engine/components/transform/extract_json_fields.py:192` | **Reject output stores entire raw JSON per failed row**: The reject handler stores `'errorJSONField': row[0]` which is the full raw JSON string from the input column. For large JSON documents (multi-MB per row), this creates a memory bomb in the reject DataFrame -- every failed row duplicates the entire JSON payload. The reject output also lacks a row index for correlation back to the input DataFrame, making debugging difficult. Should store a truncated preview and the original row index instead. |
| BUG-EJF-012 | **P3** | `src/v1/engine/components/transform/extract_json_fields.py:305` | **Wildcard detection via string matching is fragile**: The check `'[*]' in query or '.*' in query` (line 305) uses string containment to detect wildcard queries. This can false-positive on queries like `$.field_with_star_name` (contains `.*` as part of field name) or false-negative on recursive descent (`$..field`). A semantic check on the parsed JSONPath expression would be more reliable. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-EJF-001 | **P2** | **Dual key support (`schema_column`/`column`, `query`/`jsonpath`)**: Lines 275-277 support two different key names for each mapping field. This is defensive coding but undocumented -- the converter always produces `schema_column` and `query`. The `column`/`jsonpath` variants appear to be legacy or from a different converter version. Should be documented or deprecated. |
| NAME-EJF-002 | **P3** | **`errorJSONField` in reject output** vs Talend's pattern of including all schema columns. The key name is non-standard and not aligned with Talend reject schema conventions. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-EJF-001 | **P1** | "`_validate_config()` should catch all configuration errors" | Validation does not check JSONPath syntax validity. Invalid queries pass validation and crash in `_extract_fields()`. |
| STD-EJF-002 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types. Cross-cutting issue. |
| STD-EJF-003 | **P2** | "Use `None` for null values" (Talend compatibility) | No-match fields set to `''` (empty string) instead of `None`. Breaks null semantics. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-EJF-001 | **P3** | **Excessive debug logging in hot path**: Lines 167, 171, 175, 261, 271, 282, 290, 294, 298, 304, 313, 320, 325, 329, 332 all contain `logger.debug()` calls inside the row-processing and field-extraction loops. For a DataFrame with 100K rows and 10 fields, this generates 1M+ debug log messages even when debug logging is disabled (the f-string formatting still executes). Should use `logger.isEnabledFor(logging.DEBUG)` guard or lazy formatting (`logger.debug("msg %s", var)`). |
| DBG-EJF-002 | **P3** | **Dead code in `_is_relative_query()`**: Lines 352-357 define `relative_patterns` list but never use it. The list is assigned to a local variable that is never referenced. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-EJF-001 | **P3** | **No JSONPath injection protection**: JSONPath queries from config are passed directly to `jsonpath_ng.parse()`. If config is attacker-controlled (unlikely in Talend-converted jobs), malicious queries could cause DoS via pathological expressions (deep recursion, excessive wildcards). Not a concern for trusted Talend-converted configs. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 147) and completion (line 221-222) -- correct |
| Sensitive data | No sensitive data logged (JSON content in debug only) -- acceptable |
| No print statements | No `print()` calls -- correct |
| Performance concern | See DBG-EJF-001 -- excessive debug logging in hot path |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `ComponentExecutionError` -- correct |
| Exception chaining | Uses `raise ... from e` pattern on line 188 -- correct |
| `die_on_error` handling | Three-tier: config validation raises always (line 134), row-level respects flag (line 183-188), outer catch-all wraps in `ComponentExecutionError` (line 237) -- correct structure |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID, row index, and error details -- correct |
| Graceful degradation | Returns empty DataFrame for empty input (line 144) -- correct |
| **Gap** | Individual mapping query failures (line 322-325) are silently caught and set to `''`. No mechanism to report partial extraction failures. Talend would include these in reject output. See BUG-EJF-010. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_extract_fields()`, `_is_relative_query()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `List[Dict]`, `Optional[pd.DataFrame]` -- correct |
| `DataValidationError` imported but unused | Line 14 imports `DataValidationError` but it is never raised -- minor dead import |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-EJF-001 | **P1** | **Row-by-row processing via `iterrows()`**: Line 165 uses `input_data.iterrows()` to process each row individually. For DataFrames with 100K+ rows, this is extremely slow compared to vectorized approaches. Each row triggers `json.loads()`, `jsonpath_ng.parse()` (compiles JSONPath expression from scratch), and individual field extractions. The JSONPath compilation happens INSIDE the row loop for BOTH the loop query (line 258) and each mapping query (lines 289, 293), meaning for N rows and M mappings, there are `N * (1 + M)` JSONPath compilations of the SAME expressions. |
| PERF-EJF-002 | **P2** | **No JSONPath expression caching**: `jsonpath_ng.parse()` compiles a JSONPath expression string into an expression tree. The same expressions (loop_query, mapping queries) are parsed on every row and every field. Caching the compiled expressions outside the row loop would eliminate redundant compilation. For 100K rows with 5 mappings, this eliminates 600K unnecessary parse calls. |
| PERF-EJF-003 | **P3** | **Debug logging f-string evaluation in hot path**: See DBG-EJF-001. Even when debug level is disabled, Python still evaluates all f-string expressions, including `{row.values}`, `{json_data}`, `{extracted_rows}` which may involve serializing large objects. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Output accumulation | `main_output` list (line 161) accumulates all extracted rows in memory before converting to DataFrame (line 198). For large JSON arrays producing many rows, this can use significant memory. |
| Reject accumulation | `reject_output` list (line 162) accumulates all reject rows. Typically small. |
| JSON parsing | `json.loads()` creates in-memory representation of full JSON per row. Large JSON documents consume proportional memory. |
| No streaming support | Unlike file input components, there is no streaming/chunked mode for JSON extraction itself. The base class `_execute_streaming()` chunks the INPUT DataFrame, but each chunk is still processed row-by-row. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| Reject output lost in streaming | Base class `_execute_streaming()` (line 270-271) only collects `chunk_result['main']`. The `reject` key from `_process()` return value is silently dropped. Streaming mode loses ALL reject data. |
| Stats accumulation | `_update_stats()` is called per chunk via `_process()`. Base class correctly accumulates via `+=` (lines 308-310). |
| No output streaming | Even in streaming mode, each chunk's output is accumulated in `results` list and then `pd.concat()`ed (line 275). For very large output (e.g., many loop matches per input row), this can exhaust memory. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `ExtractJSONFields` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 364 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic JSON extraction | P0 | Input DataFrame with JSON strings, simple loop query `$.items[*]`, extract `$.name` and `$.value`. Verify correct column values. |
| 2 | Empty input DataFrame | P0 | Pass empty DataFrame. Verify empty result, stats (0, 0, 0), no error. |
| 3 | None input | P0 | Pass `None`. Verify empty result, stats (0, 0, 0). |
| 4 | Invalid JSON + die_on_error=true | P0 | Input with malformed JSON string. Verify `ComponentExecutionError` raised. |
| 5 | Invalid JSON + die_on_error=false | P0 | Input with malformed JSON string. Verify reject DataFrame has the error, main has remaining rows. |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` correct after extraction. |
| 7 | `_is_relative_query()` correctness | P0 | Verify that mapping queries for nested properties (e.g., `$.address.city`) resolve correctly against loop items, NOT the full document. **This test will FAIL with current code**, demonstrating BUG-EJF-003. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | NaN in JSON column | P1 | Input DataFrame with NaN in column 0. Verify graceful handling (reject row, not crash). |
| 9 | Non-string in JSON column | P1 | Input DataFrame with integer/dict/None in column 0. Verify correct behavior. |
| 10 | Nested JSON extraction | P1 | Loop on `$.data.records[*]`, extract `$.details.name`. Verify nested path resolution. |
| 11 | Array result serialization | P1 | Mapping query returns array. Verify serialized as JSON string in output. |
| 12 | Multiple input rows | P1 | Input with 5 rows, each containing different JSON. Verify all rows processed. |
| 13 | Loop query with zero matches | P1 | Loop query matches nothing. Verify zero output rows (currently buggy -- produces 1 row). |
| 14 | `json_field` column selection | P1 | Input with multiple columns, JSON in column 2. Set `json_field`. Verify correct column used (currently ignores config). |
| 15 | Reject flow schema | P1 | Verify reject DataFrame includes all original schema columns per Talend conventions. |
| 16 | Config validation -- missing loop_query | P1 | Verify `ConfigurationError` raised. |
| 17 | Config validation -- empty mapping | P1 | Verify `ConfigurationError` raised. |
| 18 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. set in globalMap after execution (currently crashes due to BUG-EJF-001). |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | Large DataFrame performance | P2 | Benchmark 10K rows with 5 mappings. Measure time and memory. |
| 20 | Deeply nested JSON | P2 | JSON with 10+ nesting levels. Verify extraction works. |
| 21 | Unicode in JSON values | P2 | JSON with CJK, emoji, RTL characters. Verify correct extraction and serialization. |
| 22 | Empty JSON object `{}` | P2 | Input row with `"{}"`. Loop query matches nothing. Verify behavior. |
| 23 | Empty JSON array `[]` | P2 | Input row with `"[]"`. Loop query on root array. Verify behavior. |
| 24 | Mixed valid/invalid rows | P2 | 3 valid JSON rows, 2 invalid. Verify 3 main + 2 reject. |
| 25 | Wildcard query false positive | P2 | Query `$.field_with_star` (contains `.*` substring). Verify not treated as wildcard. |
| 26 | Thread safety | P2 | Two ExtractJSONFields instances processing concurrently. Verify no shared state corruption. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-EJF-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-EJF-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-EJF-003 | Bug | `_is_relative_query()` is a hardcoded heuristic with dead code and a test-case-specific condition (`$.employee`). Causes silent data corruption for any non-trivial nested JSON. Queries with 2+ dots always run against full document instead of loop item. |
| TEST-EJF-001 | Testing | Zero v1 unit tests for this component. All 364 lines of engine code are unverified. |
| ENG-EJF-001 | Engine | `_is_relative_query()` heuristic silently produces wrong extraction results. Not just a code smell -- actively corrupts output data. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-EJF-001 | Converter | Mapping table stride-2 parsing is fragile. Odd entry count causes `IndexError`. No bounds checking. |
| CONV-EJF-008 | Converter | Converter mapping parser ignores `elementRef` attribute (lines 2472-2476), relying on fragile positional stride-2 ordering instead of semantic attribute. Root cause of CONV-EJF-001. |
| ENG-EJF-002 | Engine | No `json_field` column selection -- engine hardcodes `row[0]` regardless of config. |
| ENG-EJF-003 | Engine | No `use_loop_as_root` implementation -- config extracted but ignored. |
| ENG-EJF-004 | Engine | No `split_list` implementation -- arrays always serialized, never split into rows. |
| ENG-EJF-005 | Engine | REJECT flow missing original schema columns. Only includes `errorJSONField`, not full schema. |
| BUG-EJF-004 | Bug | `json.loads(row[0])` crashes on NaN/None/non-string values. Unhelpful `TypeError` message. |
| BUG-EJF-005 | Bug | Zero loop matches fallback to entire document. Produces spurious output row. |
| BUG-EJF-006 | Bug | `_validate_config()` does not validate JSONPath syntax. Invalid queries pass and crash at runtime. |
| BUG-EJF-010 | Bug | Per-mapping `except Exception` (lines 322-325) silently swallows configuration errors. Bad JSONPath syntax in mapping query fails silently on every row, producing `''` with zero visibility. No per-field error accumulation. |
| STD-EJF-001 | Standards | Config validation incomplete -- no JSONPath syntax checking. |
| PERF-EJF-001 | Performance | Row-by-row `iterrows()` with per-row JSONPath `parse()` compilation. N*M redundant compilations. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-EJF-002 | Converter | XPath mode completely unsupported -- 4 parameters not extracted. |
| CONV-EJF-003 | Converter | `json_field` extracted by converter but ignored by engine. Silent data corruption when JSON is not in first column. |
| CONV-EJF-004 | Converter | Schema type format uses Python types instead of Talend types (cross-cutting). |
| ENG-EJF-006 | Engine | Zero loop matches fallback to processing entire document instead of producing zero rows. |
| ENG-EJF-007 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. |
| ENG-EJF-008 | Engine | NB_LINE semantics -- partial extraction failures within a row not counted as rejects. |
| BUG-EJF-007 | Bug | No-match fields set to `''` instead of `None`. Breaks null semantics for downstream type conversion. |
| BUG-EJF-008 | Bug (Downgraded) | ~~Serialization lambda does not handle NaN/None explicitly.~~ NaN bypass of serialization lambda is actually correct behavior -- `json.dumps(None)` would produce `'null'` string which is wrong. **No longer considered a bug.** |
| BUG-EJF-009 | Bug | Reject handler accesses `row[0]` -- fragile assumption about column indexing. |
| BUG-EJF-011 | Bug | Reject output stores entire raw JSON per failed row (line 192). Memory bomb for large documents. Also lacks row index for correlation. |
| NAME-EJF-001 | Naming | Dual key support (`schema_column`/`column`, `query`/`jsonpath`) undocumented. |
| STD-EJF-002 | Standards | Schema types in Python format, not Talend format (cross-cutting). |
| STD-EJF-003 | Standards | No-match fields use `''` instead of `None` (breaks Talend null convention). |
| PERF-EJF-002 | Performance | No JSONPath expression caching. Same expressions compiled N*M times. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-EJF-005 | Converter | Misplaced comment at line 294: says "tExtractJSONFields mapping" but code handles `tExtractDelimitedFields`. |
| ENG-EJF-009 | Engine | No XPath mode support. |
| BUG-EJF-012 | Bug | Wildcard detection via `'[*]' in query` is fragile string matching. (Renumbered from BUG-EJF-010.) |
| NAME-EJF-002 | Naming | `errorJSONField` in reject output is non-standard key name. |
| SEC-EJF-001 | Security | No JSONPath injection protection (low risk for trusted configs). |
| DBG-EJF-001 | Debug | Excessive debug logging in hot path (15+ log calls per row per field). |
| DBG-EJF-002 | Debug | Dead `relative_patterns` list in `_is_relative_query()` never referenced. |
| PERF-EJF-003 | Performance | Debug f-string evaluation overhead in hot path. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 3 bugs (2 cross-cutting, 1 component-specific), 1 testing, 1 engine |
| P1 | 12 | 2 converter, 4 engine, 4 bugs, 1 standards, 1 performance |
| P2 | 14 (13 active) | 3 converter, 3 engine, 4 bugs (1 downgraded: BUG-EJF-008), 1 naming, 2 standards, 1 performance |
| P3 | 8 | 1 converter, 1 engine, 1 bug, 1 naming, 1 security, 2 debug, 1 performance |
| **Total** | **39 entries (38 active)** | Adversarial additions: BUG-EJF-010 (P1), CONV-EJF-008 (P1), BUG-EJF-011 (P2). BUG-EJF-008 (P2) downgraded to not-a-bug but retained for traceability. BUG-EJF-010 (P3, wildcard) renumbered to BUG-EJF-012. |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-EJF-001): Change `{stat_name}: {value}` to remove the stale `{value}` reference on `base_component.py` line 304. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low.

2. **Fix `GlobalMap.get()` bug** (BUG-EJF-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Replace `_is_relative_query()` with `use_loop_as_root` flag** (BUG-EJF-003, ENG-EJF-001, ENG-EJF-003): Delete the entire `_is_relative_query()` method. Instead, read `self.config.get('use_loop_as_root', True)` (default True, matching Talend default behavior where mapping queries run against the loop item). When `use_loop_as_root=True`, ALL mapping queries execute on the current loop item. When `False`, queries starting with `$` execute on the full document. This is the single most impactful fix -- it eliminates silent data corruption.

4. **Create unit test suite** (TEST-EJF-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover basic extraction, empty input, die_on_error modes, statistics, and the `_is_relative_query` regression.

5. **Fix zero-match loop fallback** (BUG-EJF-005): Remove lines 264-266 (`if not matches: matches = [json_data]`). When the loop query matches zero elements, return an empty list from `_extract_fields()`. This matches Talend behavior.

### Short-Term (Hardening)

6. **Implement `json_field` column selection** (ENG-EJF-002): Replace `row[0]` on line 170 with `row[self.config.get('json_field', row.index[0])]`. If `json_field` is specified, use it as the column name/index. Otherwise, default to the first column.

7. **Add NaN/None guard for `json.loads()`** (BUG-EJF-004): Before `json.loads(row[0])`, check `if pd.isna(row[col]) or row[col] is None:` and route to reject with a clear message. Also handle the case where `row[col]` is already a dict (skip `json.loads`).

8. **Cache compiled JSONPath expressions** (PERF-EJF-001, PERF-EJF-002): Parse the loop query and all mapping queries ONCE before the row loop:
   ```python
   compiled_loop = parse(loop_query)
   compiled_mappings = [(m, parse(m.get('query') or m.get('jsonpath'))) for m in mapping]
   ```
   Then use the compiled expressions inside the loop. This eliminates N*(1+M) redundant compilations.

9. **Implement `split_list`** (ENG-EJF-004): When `self.config.get('split_list', False)` is True and a query returns a list, create one output row per element instead of serializing the list.

10. **Use `None` for no-match fields** (BUG-EJF-007, STD-EJF-003): Change `row[col] = ''` (lines 303, 324, 328) to `row[col] = None`. This preserves null semantics for downstream type conversion and null-aware logic.

11. **Fix REJECT flow schema** (ENG-EJF-005): Include all output schema columns (with whatever partial data was extracted) in the reject row, plus `errorCode` and `errorMessage`. Currently only includes `errorJSONField`.

12. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-EJF-007): In error handlers, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` when `global_map` is available.

### Long-Term (Optimization)

13. **Add JSONPath syntax validation to `_validate_config()`** (BUG-EJF-006, STD-EJF-001): Try `parse(loop_query)` and `parse(query)` for each mapping during validation. Catch `JsonPathParserError` and add to error list.

14. **Fix converter mapping table parsing** (CONV-EJF-001): Add bounds checking on `entries[i+1]` access. Handle odd entry counts gracefully. Consider parsing by `elementRef` attribute rather than stride-2 positional assumption.

15. **Add debug logging guard** (DBG-EJF-001, PERF-EJF-003): Wrap hot-path debug logging with `if logger.isEnabledFor(logging.DEBUG):` or use lazy formatting `logger.debug("msg %s", var)`.

16. **Consider vectorized JSON extraction** (PERF-EJF-001): For simple extraction patterns, consider using `pd.json_normalize()` or `df[col].apply(json.loads)` followed by vectorized column selection instead of row-by-row iteration.

17. **Fix misplaced comment** (CONV-EJF-005): Change line 294 of `component_parser.py` from `# tExtractJSONFields mapping` to `# tExtractDelimitedFields mapping`.

18. **Remove dead code** (DBG-EJF-002): Remove the unused `relative_patterns` list in `_is_relative_query()` (or delete the entire method per recommendation 3).

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 2448-2478
def parse_textract_json_fields(self, node, component: dict) -> dict:
    """Parse tExtractJSONFields specific configuration from Talend XML node."""
    def get_param(name, default=None):
        param = node.find(f'.//elementParameter[@name="{name}"]')
        return param.get('value', default) if param is not None else default

    # Map Talend XML parameters to config
    component['config']['read_by'] = get_param('READ_BY', 'JSONPATH')
    component['config']['json_path_version'] = get_param('JSON_PATH_VERSION', '2_1_0')
    # Remove extra quotes from loop_query
    loop_query = get_param('LOOP_QUERY', '') or get_param('JSON_LOOP_QUERY', '')
    if loop_query and loop_query.startswith('"') and loop_query.endswith('"'):
        loop_query = loop_query[1:-1]
    component['config']['loop_query'] = loop_query
    component['config']['die_on_error'] = get_param('DIE_ON_ERROR', 'false').lower() == 'true'
    component['config']['encoding'] = get_param('ENCODING', 'UTF-8')
    component['config']['use_loop_as_root'] = get_param('USE_LOOP_AS_ROOT', 'false').lower() == 'true'
    component['config']['split_list'] = get_param('SPLIT_LIST', 'false').lower() == 'true'
    component['config']['json_field'] = get_param('JSONFIELD', '')

    # Parse mapping table (MAPPING_4_JSONPATH)
    mapping = []
    mapping_table = node.find('.//elementParameter[@name="MAPPING_4_JSONPATH"]')
    if mapping_table is not None:
        entries = list(mapping_table.findall('elementValue'))
        for i in range(0, len(entries), 2):
            schema_col = entries[i].get('value', '').strip('"')
            query = entries[i+1].get('value', '').strip('"')  # IndexError if odd count
            mapping.append({'schema_column': schema_col, 'query': query})
    component['config']['mapping'] = mapping
    return component
```

**Notes on this code**:
- Line 2458: Tries both `LOOP_QUERY` and `JSON_LOOP_QUERY` XML names. Good defensive coding.
- Lines 2459-2460: Strips surrounding quotes. Talend XML stores JSONPath queries with double quotes.
- Lines 2472-2476: Stride-2 parsing assumes strict column/query alternation. No bounds check on `entries[i+1]`.
- Line 2466: `JSONFIELD` extracted but engine ignores it.
- Lines 2464-2465: `USE_LOOP_AS_ROOT` and `SPLIT_LIST` extracted but engine ignores both.

---

## Appendix B: Engine Class Structure

```
ExtractJSONFields (BaseComponent)
    Methods:
        _validate_config() -> List[str]          # Called from _process(). Validates structure only.
        _process(input_data) -> Dict[str, Any]   # Main entry point. Row-by-row processing.
        _extract_fields(json_data, loop_query, mapping) -> List[Dict]
                                                  # JSONPath extraction with loop iteration.
        _is_relative_query(query) -> bool         # BROKEN. Hardcoded heuristic for query context.

    Config Keys (from converter):
        loop_query (str)          # Required. JSONPath loop expression.
        mapping (list)            # Required. List of {schema_column, query} dicts.
        die_on_error (bool)       # Default False.
        read_by (str)             # Extracted but UNUSED.
        json_path_version (str)   # Extracted but UNUSED.
        encoding (str)            # Extracted but UNUSED.
        use_loop_as_root (bool)   # Extracted but UNUSED.
        split_list (bool)         # Extracted but UNUSED.
        json_field (str)          # Extracted but UNUSED.

    Returns:
        {'main': pd.DataFrame, 'reject': pd.DataFrame}
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `READ_BY` | `read_by` | Mapped (unused) | P3 (XPath) |
| `JSON_PATH_VERSION` | `json_path_version` | Mapped (unused) | P3 |
| `LOOP_QUERY` / `JSON_LOOP_QUERY` | `loop_query` | **Mapped (used)** | -- |
| `DIE_ON_ERROR` | `die_on_error` | **Mapped (used)** | -- |
| `ENCODING` | `encoding` | Mapped (unused) | P3 |
| `USE_LOOP_AS_ROOT` | `use_loop_as_root` | Mapped (unused) | **P1** |
| `SPLIT_LIST` | `split_list` | Mapped (unused) | **P1** |
| `JSONFIELD` | `json_field` | Mapped (unused) | **P1** |
| `MAPPING_4_JSONPATH` | `mapping` | **Mapped (used)** | -- |
| `LOOP_XPATH_QUERY` | -- | **Not Mapped** | P3 |
| `MAPPING_XPATH` | -- | **Not Mapped** | P3 |
| `MAPPING_GET_NODES` | -- | **Not Mapped** | P3 |
| `MAPPING_IS_ARRAY` | -- | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- |
| `LABEL` | -- | Not needed | -- |
| `PROPERTY_TYPE` | -- | Not needed | -- |

---

## Appendix D: `_is_relative_query()` Analysis

This method (lines 341-364) is the most critical bug in the component. Here is the full code:

```python
def _is_relative_query(self, query: str) -> bool:
    # Queries that should be executed on the current iteration item (relative)
    relative_patterns = [          # DEAD CODE: never referenced
        '$.skill',
        '$.level',
        '$.name',
        '$.value',
    ]

    # Simple heuristic: if query is just accessing direct properties without complex paths,
    # it's likely meant for the current iteration item
    if query.count('.') <= 1 and not query.startswith('$.employee'):
        return True

    return False
```

**Problems**:
1. `relative_patterns` list is defined but never used (dead code).
2. `query.count('.') <= 1` means only `$.field` (one dot) is considered relative. `$.address.city` (two dots) is treated as absolute.
3. `not query.startswith('$.employee')` is a hardcoded test-case-specific exclusion that has no general meaning.
4. The method completely ignores the `use_loop_as_root` config parameter.
5. The method is called ONLY for queries starting with `$.` (line 287), but in Talend with `USE_LOOP_AS_ROOT=true`, ALL queries should be relative regardless of prefix.

**Impact**: For a JSON like `{"employees": [{"name": "Alice", "dept": {"id": 1, "name": "Eng"}}]}` with loop `$.employees[*]` and mapping `$.dept.name`:
- **Talend** (USE_LOOP_AS_ROOT=true): Extracts `"Eng"` from the current employee.
- **V1**: `_is_relative_query("$.dept.name")` returns `False` (2 dots). Query runs on full document. `$.dept.name` finds nothing at root level. Returns `''`.

---

## Appendix E: Edge Case Analysis

### Edge Case 1: NaN in JSON column

| Aspect | Detail |
|--------|--------|
| **Talend** | Input column with null value -- row goes to REJECT if REJECT connected, otherwise skipped. |
| **V1** | `json.loads(NaN)` raises `TypeError: the JSON object must be str, bytes or bytearray, not float`. Caught by row-level except. With `die_on_error=true`, crashes. With `false`, reject row created. |
| **Verdict** | PARTIALLY CORRECT -- rejects the row but with unhelpful TypeError message. Should detect NaN before attempting parse. |

### Edge Case 2: Empty string in JSON column

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty string is not valid JSON. Row goes to REJECT. |
| **V1** | `json.loads('')` raises `json.JSONDecodeError: Expecting value`. Caught by row-level except. Correctly rejected. |
| **Verdict** | CORRECT |

### Edge Case 3: Empty DataFrame input

| Aspect | Detail |
|--------|--------|
| **Talend** | No rows to process. NB_LINE=0. |
| **V1** | Line 141: `input_data.empty` returns True. Returns empty DataFrames. Stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 4: HYBRID streaming mode

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A (Talend Standard uses Java streaming). |
| **V1** | Base class `_execute_streaming()` chunks input DataFrame and calls `_process()` per chunk. Reject output from each chunk is LOST (line 270-271 only keeps `main`). Stats accumulate correctly. |
| **Verdict** | BUG -- reject data lost in streaming mode. |

### Edge Case 5: `_update_global_map()` crash

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A (Talend globalMap always works). |
| **V1** | `base_component.py` line 304 references undefined `value` variable. When `global_map` is not None, `_update_global_map()` crashes with `NameError`. This is called from `execute()` line 218 (success path) and line 231 (error path). Every component with a globalMap will crash. |
| **Verdict** | CRITICAL BUG -- all components broken when globalMap is provided. |

### Edge Case 6: Component status tracking

| Aspect | Detail |
|--------|--------|
| **Talend** | Component status is tracked by the Talend runtime. |
| **V1** | `execute()` sets `self.status = ComponentStatus.RUNNING` (line 192), then `SUCCESS` (line 220) or `ERROR` (line 228). However, if `_update_global_map()` crashes (BUG-EJF-001), the status is set to `ERROR` in the except block (line 228), then `_update_global_map()` is called AGAIN (line 231), causing a SECOND crash. The status correctly reflects `ERROR` but the double-crash on globalMap is problematic. |
| **Verdict** | BUG -- cascading failure from `_update_global_map()`. |

### Edge Case 7: Thread safety

| Aspect | Detail |
|--------|--------|
| **Talend** | Components run in dedicated threads with shared globalMap (synchronized). |
| **V1** | `ExtractJSONFields` has no shared mutable state beyond what it inherits from `BaseComponent`. The `stats` dict and `status` field are instance-level. `global_map` is shared but `GlobalMap` has no locking. Concurrent `put()` calls on `GlobalMap._map` (a plain dict) are not thread-safe in CPython when keys collide. |
| **Verdict** | POTENTIAL ISSUE -- GlobalMap not thread-safe for concurrent component execution. |

### Edge Case 8: Type demotion from validate_schema

| Aspect | Detail |
|--------|--------|
| **Talend** | Types are enforced per the schema definition. Null integers remain null or become 0 depending on context. |
| **V1** | `validate_schema()` in base_component.py converts `int64` columns with `nullable=True` using `fillna(0).astype('int64')` (line 352). This means: (a) extracted JSON integer fields that are null (`None`) become 0; (b) empty strings from no-match mappings (BUG-EJF-007) are first coerced to NaN by `pd.to_numeric(errors='coerce')`, then to 0 by `fillna(0)`. Missing data is silently converted to 0. |
| **Verdict** | GAP -- null masking. Exacerbated by BUG-EJF-007 (empty strings instead of None). |

### Edge Case 9: validate_schema nullable inverted

| Aspect | Detail |
|--------|--------|
| **Talend** | Non-nullable columns reject null values. Nullable columns allow null. |
| **V1** | `base_component.py` line 351: `if pandas_type == 'int64' and col_def.get('nullable', True):` -- the `fillna(0)` only runs when `nullable=True`. When `nullable=False`, the NaN is NOT filled, which causes `astype('int64')` to fail (NaN cannot be cast to int64). The logic is INVERTED: nullable columns get `fillna(0)` (correct -- allows null, fills with default), but non-nullable columns should ALSO `fillna(0)` or reject the row (they do neither -- they crash). |
| **Verdict** | BUG -- inverted nullable logic. Non-nullable integer columns with any null/NaN will crash `validate_schema()`. |

### Edge Case 10: _validate_config dead code paths

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A. |
| **V1** | Unlike other components where `_validate_config()` is completely dead code (never called), `ExtractJSONFields._validate_config()` IS called from `_process()` line 130. However, it only validates structural correctness (key presence, types). It does not validate JSONPath syntax, so invalid queries like `$.[[[` pass validation and crash at runtime. The validation IS useful but incomplete. |
| **Verdict** | PARTIAL -- called and useful, but incomplete. Not truly "dead code" for this component. |

### Edge Case 11: JSONPath library edge cases

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses Jayway JsonPath (Java library) with its own semantics. |
| **V1** | Uses `jsonpath_ng` (Python library). Known differences from Jayway: (a) `$..field` recursive descent may produce different ordering; (b) filter expressions (`$[?(@.price < 10)]`) may have syntax differences; (c) `jsonpath_ng` does not support all Jayway extensions. These differences can cause silent result divergence between Talend and V1 for complex queries. |
| **Verdict** | POTENTIAL GAP -- library differences may cause different extraction results for complex queries. |

### Edge Case 12: json.loads on non-string input

| Aspect | Detail |
|--------|--------|
| **Talend** | Input is always a Java String. Type mismatch causes compilation error. |
| **V1** | `row[0]` may be any Python type. `json.loads()` only accepts `str`, `bytes`, `bytearray`. Passing `int`, `float`, `dict`, `list`, `bool`, `None`, or `NaN` raises `TypeError`. If the upstream component already parsed JSON (producing a dict), `json.loads` fails. Should check `isinstance(row[col], str)` first and handle dict/list passthrough. |
| **Verdict** | BUG -- no type check before `json.loads()`. See BUG-EJF-004. |

### Edge Case 13: Reject flow format

| Aspect | Detail |
|--------|--------|
| **Talend** | Reject rows contain ALL output schema columns (with partial data) plus `errorCode` and `errorMessage` in green columns. |
| **V1** | Reject rows contain only `errorJSONField` (raw JSON string), `errorCode` (`'PARSE_ERROR'`), and `errorMessage` (error string). Missing all schema columns. Downstream components expecting schema-conformant reject rows will fail with KeyError on expected columns. |
| **Verdict** | GAP -- reject schema does not match Talend conventions. See ENG-EJF-005. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `ExtractJSONFields`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-EJF-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-EJF-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| CONV-EJF-004 | **P2** | `component_parser.py` | Schema types converted to Python format instead of Talend format. Affects all components. |
| -- | **P2** | `base_component.py:351` | `validate_schema()` nullable logic inverted for integer columns. Non-nullable integers with NaN crash. |
| -- | **P2** | `base_component.py:255-278` | `_execute_streaming()` drops reject output from chunks. Affects all components with reject flows in streaming mode. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-EJF-003 -- Replace `_is_relative_query()` with `use_loop_as_root`

**File**: `src/v1/engine/components/transform/extract_json_fields.py`

**Step 1**: Delete `_is_relative_query()` method entirely (lines 341-364).

**Step 2**: Modify `_extract_fields()` to use `use_loop_as_root` config:

```python
def _extract_fields(self, json_data, loop_query, mapping):
    use_loop_as_root = self.config.get('use_loop_as_root', True)
    # ... existing loop code ...
    for item_idx, item in enumerate(matches):
        for m_idx, m in enumerate(mapping):
            col = m.get('schema_column') or m.get('column')
            query = m.get('query') or m.get('jsonpath')
            if query:
                # Determine context based on use_loop_as_root
                if use_loop_as_root:
                    context = item
                else:
                    context = json_data
                jsonpath_matches = compiled_query.find(context)
                # ... rest of extraction ...
```

**Impact**: Eliminates silent data corruption. **Risk**: Medium -- changes extraction behavior. Requires testing with existing jobs.

---

### Fix Guide: BUG-EJF-005 -- Remove zero-match fallback

**File**: `src/v1/engine/components/transform/extract_json_fields.py`
**Lines**: 264-266

**Current code (wrong)**:
```python
if not matches:
    logger.debug(f"[{self.id}] No matches for loop query, processing entire JSON data")
    matches = [json_data]
```

**Fix**: Remove these 3 lines entirely. When `matches` is empty, the `for item_idx, item in enumerate(matches)` loop simply does not execute, producing zero output rows.

**Impact**: Aligns with Talend behavior. **Risk**: Low -- any job relying on the fallback was already producing incorrect results.

---

### Fix Guide: PERF-EJF-001 -- Cache JSONPath expressions

**File**: `src/v1/engine/components/transform/extract_json_fields.py`

**In `_process()`, before the row loop (after line 153)**:
```python
# Pre-compile JSONPath expressions (cache outside row loop)
compiled_loop_query = parse(loop_query)
compiled_mapping_queries = []
for m in mapping:
    query = m.get('query') or m.get('jsonpath')
    compiled_mapping_queries.append(parse(query) if query else None)
```

**In `_extract_fields()`, accept compiled expressions**:
```python
def _extract_fields(self, json_data, compiled_loop, compiled_mappings, mapping):
    matches = [match.value for match in compiled_loop.find(json_data)]
    # ... use compiled_mappings[m_idx].find(item) instead of parse(query).find(item) ...
```

**Impact**: Eliminates N*(1+M) redundant JSONPath compilations. **Risk**: Very low.

---

## Appendix H: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs with nested JSON extraction (`$.address.city`) | **Critical** | Any job with multi-dot mapping queries | Fix `_is_relative_query()` / implement `use_loop_as_root` |
| Jobs with globalMap | **Critical** | Any job using globalMap | Fix `_update_global_map()` and `GlobalMap.get()` bugs |
| Jobs using `json_field` column selection | **High** | Jobs where JSON is not in first column | Implement `json_field` support |
| Jobs using `split_list` | **High** | Jobs expecting array expansion into rows | Implement `split_list` |
| Jobs depending on REJECT flow schema | **Medium** | Jobs with downstream processing of reject rows | Fix reject schema to include all output columns |
| Jobs with NaN/null in JSON column | **Medium** | Jobs with sparse input data | Add NaN/None guard before `json.loads()` |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using XPath mode | Low | Rare in modern Talend jobs |
| Jobs using tStatCatcher | Low | Monitoring only |
| Jobs with simple `$.field` queries | Low | Current heuristic happens to work for single-dot queries |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting `_update_global_map()`, `GlobalMap.get()`, and `_is_relative_query()`).
2. **Phase 2**: Implement `json_field`, `use_loop_as_root`, `split_list` from already-extracted config.
3. **Phase 3**: Create unit test suite covering all P0 and P1 test cases.
4. **Phase 4**: Audit each target job's Talend configuration. Identify which features are used.
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row, paying special attention to nested JSON extraction results.

---

## Appendix I: Detailed Engine Code Analysis

### `_validate_config()` (Lines 71-109)

This method validates structural correctness of the configuration dictionary:

**Validates**:
- `loop_query` is present, is a string, and is non-empty after stripping whitespace
- `mapping` is present, is a list, and is non-empty
- Each mapping entry is a dict with either `schema_column` or `column` key
- Each mapping entry has either `query` or `jsonpath` key
- `die_on_error` is a boolean if present

**Does NOT validate**:
- JSONPath syntax (invalid queries like `$.[[[` pass)
- `json_field` references a valid column name
- `use_loop_as_root` is boolean
- `split_list` is boolean
- `encoding` is a valid encoding name
- `read_by` is a valid enum value (`JSONPATH` or `XPATH`)
- Mapping queries are valid JSONPath expressions

**Call site**: Called from `_process()` line 130. Unlike many other components where `_validate_config()` is dead code, this component does invoke it. Validation errors raise `ConfigurationError` immediately (line 134), regardless of `die_on_error` setting -- this is correct behavior (config errors are unrecoverable).

**Quality**: Good structure but incomplete coverage. The dual-key support (`schema_column`/`column`, `query`/`jsonpath`) is validated with `or` logic (line 97-98, 101-102), which is correct but means neither key is individually required.

### `_process()` (Lines 111-237)

The main processing method follows this flow:

1. **Validate config** (line 130-134): Call `_validate_config()`, raise on errors.
2. **Handle list input** (line 137-138): Convert list to DataFrame if needed. This is a defensive measure for non-standard callers.
3. **Handle empty input** (line 141-144): Return empty DataFrames with stats (0, 0, 0).
4. **Extract config** (line 151-153): Read `loop_query`, `mapping`, `die_on_error` from config with defaults.
5. **Row-by-row processing** (line 165-195):
   - For each row via `iterrows()`:
     - Parse JSON from first column via `json.loads(row[0])`
     - Call `_extract_fields()` to get list of extracted row dicts
     - Extend `main_output` list
   - On exception:
     - If `die_on_error`: raise `ComponentExecutionError`
     - Else: append reject dict to `reject_output`
6. **Build DataFrames** (line 198-199): Convert lists to DataFrames.
7. **Serialize complex objects** (line 205-211): For each column in main_df, apply lambda to serialize list/dict values as JSON strings.
8. **Update stats** (line 220): Call `_update_stats(rows_in, rows_out, rows_rejected)`.
9. **Return** (line 224): Return `{'main': main_df, 'reject': reject_df}`.

**Exception handling**:
- Line 226-228: Re-raise `ComponentExecutionError` (from die_on_error path)
- Line 230-232: Re-raise `ConfigurationError` (from validation)
- Line 234-237: Catch-all wraps any other exception in `ComponentExecutionError`

**Key observations**:
- Config is extracted TWICE: once by `_validate_config()` (lines 76, 83) and once by `_process()` (lines 151-153). The second extraction uses `.get()` with defaults, which means even if validation passed, the defaults could mask missing values (though this is unlikely given validation checks for key presence).
- The `json.loads()` call (line 170) has no type guard. If `row[0]` is not a string, it raises `TypeError`.
- The serialization loop (lines 206-211) iterates ALL columns, not just those that might contain complex objects. For DataFrames with many string columns, this is wasteful (the `isinstance` check is cheap but the iteration overhead adds up).

### `_extract_fields()` (Lines 239-339)

This method performs the actual JSONPath extraction:

1. **Parse loop query** (line 258): `jsonpath_expr = parse(loop_query)` -- compiles the JSONPath expression from scratch on EVERY call (once per input row).
2. **Find loop matches** (line 259): `matches = [match.value for match in jsonpath_expr.find(json_data)]`
3. **Zero-match fallback** (line 264-266): If no matches, use `[json_data]` as the match list. **BUG**: Should produce zero rows.
4. **For each match** (line 269-332):
   - For each mapping (line 273-329):
     - Get column name and query from mapping dict
     - Determine query context via `_is_relative_query()` (line 287-294). **BUG**: Hardcoded heuristic.
     - Execute JSONPath query on chosen context (line 289 or 293)
     - Handle results:
       - No matches: set `''` (line 302-303). **BUG**: Should be `None`.
       - Wildcard query with single scalar: flatten (line 307-309)
       - Wildcard query with multiple/complex: keep as array (line 311-312)
       - Regular query with single value: use scalar (line 316-317)
       - Regular query with multiple values: keep as array (line 319)
     - On exception: set `''` and log warning (line 322-325)
   - Append row dict to `extracted_rows`

**Key observations**:
- The `parse()` function is called N*(1+M) times where N is input rows and M is mapping count. For 10K rows with 5 mappings, that is 60K parse calls.
- The `_is_relative_query()` dispatch (line 287) only activates for queries starting with `$.`. Queries starting with `@.` or without prefix are always executed on the current item, which is correct for Talend's relative query syntax.
- The wildcard detection (line 305) uses string matching (`'[*]' in query or '.*' in query`), which is a heuristic that can produce false positives and false negatives.

### `_is_relative_query()` (Lines 341-364)

Fully analyzed in Appendix D. Summary: **This method is fundamentally broken.** It uses a hardcoded, test-case-specific heuristic that produces wrong results for any non-trivial nested JSON extraction.

---

## Appendix J: Type Mapping Comparison

### Converter Output (ExpressionConverter.convert_type)

| Talend Type | Converter Output |
|-------------|-----------------|
| `id_String` | `str` |
| `id_Integer` | `int` |
| `id_Long` | `int` |
| `id_Float` | `float` |
| `id_Double` | `float` |
| `id_Boolean` | `bool` |
| `id_Date` | `datetime` |
| `id_BigDecimal` | `Decimal` |

### Engine validate_schema() (post-extraction conversion in base_component.py)

| Type Input | Pandas Dtype | Conversion Method |
|------------|-------------|-------------------|
| `id_String` / `str` | `object` | No conversion |
| `id_Integer` / `int` | `int64` (non-nullable) | `pd.to_numeric(errors='coerce')` then `fillna(0).astype('int64')` when nullable=True |
| `id_Long` / `long` | `int64` (non-nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | `pd.to_numeric(errors='coerce')` |
| `id_Double` / `double` | `float64` | Same as Float |
| `id_Boolean` / `bool` | `bool` | `.astype('bool')` |
| `id_Date` / `date` | `datetime64[ns]` | `pd.to_datetime()` -- no format specification |
| `id_BigDecimal` / `decimal` | `object` | No conversion in validate_schema |

### Impact on ExtractJSONFields

For `ExtractJSONFields`, the type mapping is particularly important because:

1. **Empty string values** (`''`) from no-match mappings (BUG-EJF-007) are passed to `validate_schema()`. For integer columns:
   - `pd.to_numeric('', errors='coerce')` -> `NaN`
   - `fillna(0)` -> `0`
   - `astype('int64')` -> `0`
   - Result: Missing JSON fields silently become `0` instead of remaining null/None.

2. **Boolean columns** with empty string values:
   - `.astype('bool')` on `''` -> `False`
   - Result: Missing JSON boolean fields become `False` instead of null.

3. **Date columns** with empty string values:
   - `pd.to_datetime('')` -> may raise or return `NaT`
   - Result: Depends on pandas version and error handling.

4. **Nested objects serialized as JSON strings** pass through `validate_schema()` as `object` type columns. No conversion needed, but if the schema specifies `int` or `float` for a column that actually contains a serialized JSON array (e.g., `"[1, 2, 3]"`), `pd.to_numeric` will fail and coerce to NaN.

---

## Appendix K: JSONPath Library Comparison (jsonpath_ng vs Jayway JsonPath)

### Feature Parity

| Feature | Jayway JsonPath (Talend) | jsonpath_ng (V1) | Compatible? |
|---------|--------------------------|-----------------|-------------|
| Basic property access (`$.store.name`) | Yes | Yes | Yes |
| Array index (`$.store.books[0]`) | Yes | Yes | Yes |
| Array wildcard (`$.store.books[*]`) | Yes | Yes | Yes |
| Recursive descent (`$..name`) | Yes | Yes | **Partial** -- ordering may differ |
| Filter expressions (`$[?(@.price < 10)]`) | Yes | Via `jsonpath_ng.ext` | **No** -- requires `jsonpath_ng.ext.parse` instead of `jsonpath_ng.parse` |
| Array slice (`$.store.books[0:2]`) | Yes | Yes | Yes |
| Multiple properties (`$['name','age']`) | Yes | Limited | **Partial** |
| Current node (`@`) | Yes | Yes | Yes |
| Script expressions | Yes (Groovy/JS) | No | **No** |
| Length function (`$.store.books.length()`) | Yes | No | **No** |
| Min/Max/Avg functions | Yes | No | **No** |

### Known Divergences

1. **Filter expressions**: Talend's Jayway JsonPath supports `$[?(@.price < 10)]` natively. The standard `jsonpath_ng.parse()` used in V1 does NOT support filter expressions. The extended parser `jsonpath_ng.ext.parse()` does, but V1 imports `from jsonpath_ng import parse` (line 11), using the basic parser. Any Talend job using JSONPath filter expressions will fail at runtime with a parse error.

2. **Recursive descent ordering**: Both libraries support `$..field`, but the order of results may differ. Jayway returns results in document order; `jsonpath_ng` also returns in document order but may differ for complex structures with multiple matching paths.

3. **Functions**: Jayway supports `.length()`, `.min()`, `.max()`, `.avg()`, `.stddev()`, `.concat()`, `.keys()`, `.append()`. None are available in `jsonpath_ng`. Talend jobs using these in mapping queries will fail.

4. **Null handling**: Jayway returns Java `null` for missing values. `jsonpath_ng` simply returns no match (empty list). This difference is partially mitigated by V1's no-match handling (setting `''`), but the semantics differ.

### Recommendation

Consider switching to `jsonpath_ng.ext.parse` to gain filter expression support:
```python
# Change line 11 from:
from jsonpath_ng import parse
# To:
from jsonpath_ng.ext import parse
```
This is a backward-compatible change -- `jsonpath_ng.ext.parse` supports all standard JSONPath features plus extensions.

---

## Appendix L: Comparison with Similar Extract Components

| Feature | tExtractJSONFields (V1) | tExtractDelimitedFields (V1) | tExtractXMLField (V1) |
|---------|------------------------|------------------------------|----------------------|
| Engine file | `extract_json_fields.py` (364 lines) | `extract_delimited_fields.py` | `extract_xml_fields.py` |
| Input format | JSON string in DataFrame column | Delimited string in DataFrame column | XML string in DataFrame column |
| Extraction method | JSONPath via `jsonpath_ng` | String split by delimiter | XPath (if implemented) |
| Loop/iteration support | Yes (loop_query) | N/A (single-level split) | Yes (loop_xpath) |
| Nested extraction | Yes (multi-level JSONPath) | No (flat split only) | Yes (multi-level XPath) |
| _validate_config() called? | **Yes** | TBD | TBD |
| REJECT flow | Partial (missing schema columns) | TBD | TBD |
| die_on_error | Yes | Yes | Yes |
| Column selection (json_field/field) | Config extracted, **engine ignores** | TBD | TBD |
| V1 Unit tests | **No** | **No** | **No** |
| Cross-cutting bugs apply? | Yes (globalMap, validate_schema) | Yes | Yes |

**Observation**: The lack of v1 unit tests is systemic across ALL extract components. The cross-cutting `_update_global_map()` and `GlobalMap.get()` bugs affect all of them equally.

---

## Appendix M: Detailed Fix Guide for All P0/P1 Issues

### Fix Guide: BUG-EJF-001 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-EJF-002 -- `GlobalMap.get()` undefined default

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

**Impact**: Fixes ALL components and any code calling `global_map.get()`. Also fixes `get_component_stat()` on line 58 which passes two arguments. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: BUG-EJF-004 -- json.loads on non-string

**File**: `src/v1/engine/components/transform/extract_json_fields.py`
**Line**: 170

**Current code**:
```python
json_data = json.loads(row[0])
```

**Fix**:
```python
# Determine which column to read JSON from
json_col = self.config.get('json_field', '') or row.index[0]
raw_value = row[json_col] if json_col in row.index else row.iloc[0]

# Handle non-string inputs
if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
    raise ValueError(f"JSON column '{json_col}' contains null/NaN value")
elif isinstance(raw_value, (dict, list)):
    # Already parsed (upstream component returned Python objects)
    json_data = raw_value
elif isinstance(raw_value, str):
    json_data = json.loads(raw_value)
else:
    raise ValueError(
        f"JSON column '{json_col}' contains non-string value of type "
        f"{type(raw_value).__name__}: {repr(raw_value)[:100]}"
    )
```

**Impact**: Fixes json_field column selection (ENG-EJF-002), NaN handling (BUG-EJF-004), and dict passthrough. **Risk**: Medium -- changes column selection behavior. Requires testing.

---

### Fix Guide: BUG-EJF-005 -- Zero-match loop fallback

**File**: `src/v1/engine/components/transform/extract_json_fields.py`
**Lines**: 264-266

**Delete these lines**:
```python
# If no matches found for loop query, try to process the entire JSON data
if not matches:
    logger.debug(f"[{self.id}] No matches for loop query, processing entire JSON data")
    matches = [json_data]
```

**Replace with** (optional, for logging):
```python
if not matches:
    logger.debug(f"[{self.id}] No matches for loop query '{loop_query}', producing 0 output rows")
```

**Impact**: Aligns with Talend behavior. Zero loop matches produce zero output rows. **Risk**: Low.

---

### Fix Guide: BUG-EJF-006 -- Add JSONPath syntax validation

**File**: `src/v1/engine/components/transform/extract_json_fields.py`

**Add to `_validate_config()`, after the existing mapping validation (after line 102)**:
```python
# Validate JSONPath syntax
try:
    parse(self.config['loop_query'])
except Exception as e:
    errors.append(f"Config 'loop_query' has invalid JSONPath syntax: {e}")

for i, mapping_entry in enumerate(self.config.get('mapping', [])):
    query = mapping_entry.get('query') or mapping_entry.get('jsonpath')
    if query:
        try:
            parse(query)
        except Exception as e:
            errors.append(f"Config 'mapping[{i}]' query has invalid JSONPath syntax: {e}")
```

**Impact**: Catches invalid queries at configuration time with clear error messages. **Risk**: Very low.

---

### Fix Guide: CONV-EJF-001 -- Mapping table bounds checking

**File**: `src/converters/complex_converter/component_parser.py`
**Lines**: 2472-2476

**Current code**:
```python
for i in range(0, len(entries), 2):
    schema_col = entries[i].get('value', '').strip('"')
    query = entries[i+1].get('value', '').strip('"')
    mapping.append({'schema_column': schema_col, 'query': query})
```

**Fix**:
```python
for i in range(0, len(entries) - 1, 2):  # -1 ensures i+1 is always valid
    schema_col = entries[i].get('value', '').strip('"')
    query = entries[i+1].get('value', '').strip('"')
    if schema_col and query:  # Only add valid pairs
        mapping.append({'schema_column': schema_col, 'query': query})
    else:
        logger.warning(f"Skipping incomplete mapping entry at index {i}: col='{schema_col}', query='{query}'")

if len(entries) % 2 != 0:
    logger.warning(f"Odd number of mapping entries ({len(entries)}). Last entry ignored.")
```

**Impact**: Prevents `IndexError` on odd entry counts. Warns on incomplete mappings. **Risk**: Very low.

---

### Fix Guide: ENG-EJF-004 -- Implement split_list

**File**: `src/v1/engine/components/transform/extract_json_fields.py`

**In `_extract_fields()`, after the value handling section (around line 300-320), add split_list support**:

Replace the current result handling with:
```python
split_list = self.config.get('split_list', False)

# Handle the extracted values
if not values:
    row[col] = None  # Fix BUG-EJF-007 at the same time
elif split_list and isinstance(values, list) and len(values) > 1:
    # Split mode: will create multiple rows later
    row[col] = values  # Keep as list, expand after all columns processed
    row['_needs_split'] = True
elif '[*]' in query or '.*' in query:
    if len(values) == 1 and not isinstance(values[0], (list, dict)):
        row[col] = values[0]
    else:
        row[col] = values
else:
    row[col] = values[0] if len(values) == 1 else values
```

Then after building `extracted_rows`, expand split rows:
```python
if split_list:
    expanded_rows = []
    for row in extracted_rows:
        if row.pop('_needs_split', False):
            # Find list columns and expand
            list_cols = {k: v for k, v in row.items() if isinstance(v, list)}
            if list_cols:
                max_len = max(len(v) for v in list_cols.values())
                for idx in range(max_len):
                    new_row = dict(row)
                    for col, vals in list_cols.items():
                        new_row[col] = vals[idx] if idx < len(vals) else None
                    expanded_rows.append(new_row)
            else:
                expanded_rows.append(row)
        else:
            expanded_rows.append(row)
    extracted_rows = expanded_rows
```

**Impact**: Enables array expansion into rows per Talend `SPLIT_LIST` behavior. **Risk**: Medium -- new feature, requires testing.

---

### Fix Guide: ENG-EJF-005 -- REJECT flow with schema columns

**File**: `src/v1/engine/components/transform/extract_json_fields.py`

**Replace the reject append block (lines 191-195)**:

**Current**:
```python
reject_output.append({
    'errorJSONField': row[0],
    'errorCode': 'PARSE_ERROR',
    'errorMessage': str(e)
})
```

**Fix**:
```python
# Build reject row with all schema columns set to None
reject_row = {}
for m in mapping:
    col = m.get('schema_column') or m.get('column')
    reject_row[col] = None
# Add Talend-standard error columns
reject_row['errorCode'] = 'PARSE_ERROR'
reject_row['errorMessage'] = str(e)
reject_output.append(reject_row)
```

**Impact**: Reject rows now include all output schema columns per Talend conventions. **Risk**: Medium -- changes reject DataFrame structure. Downstream components may need adjustment.

---

## Appendix N: Base Class Analysis (ExtractJSONFields-Specific Impact)

### `execute()` Lifecycle (base_component.py lines 188-234)

When `ExtractJSONFields.execute(input_data)` is called by the engine:

1. **Set status RUNNING** (line 192): `self.status = ComponentStatus.RUNNING`
2. **Resolve Java expressions** (lines 197-198): If `java_bridge` is set, call `_resolve_java_expressions()`. For ExtractJSONFields, this would resolve `{{java}}` markers in `loop_query`, `mapping[*].query`, etc. Typically not relevant since JSONPath queries rarely contain Java expressions, but possible if a context variable is embedded.
3. **Resolve context variables** (lines 201-202): If `context_manager` is set, call `context_manager.resolve_dict(self.config)`. This resolves `${context.var}` in all config values. Important for dynamic JSONPath queries.
4. **Auto-select mode** (lines 205-208): HYBRID mode checks input DataFrame memory usage against `MEMORY_THRESHOLD_MB` (3GB). For typical JSON extraction inputs, this will almost always select BATCH mode.
5. **Execute** (lines 211-214): Call `_execute_batch(input_data)` or `_execute_streaming(input_data)`.
6. **Update stats** (line 217): Set `EXECUTION_TIME`.
7. **Update globalMap** (line 218): **CRASHES** due to BUG-EJF-001.
8. **Set status SUCCESS** (line 220): Reached only if `_update_global_map()` succeeds (it does not).

### `_execute_streaming()` Impact (base_component.py lines 255-278)

When streaming mode is selected (input > 3GB):

```python
def _execute_streaming(self, input_data):
    # ...
    results = []
    for chunk in chunks:
        chunk_result = self._process(chunk)
        if chunk_result.get('main') is not None:
            results.append(chunk_result['main'])  # <-- ONLY keeps 'main'
    # ...
```

**Problem for ExtractJSONFields**: `_process()` returns `{'main': main_df, 'reject': reject_df}`. The streaming wrapper only collects `chunk_result['main']`. The `reject` key is silently dropped for every chunk. All reject data is lost.

**Impact**: In streaming mode, `die_on_error=false` with invalid JSON rows will silently lose the reject information. The stats will still count rejects (via `_update_stats()`), but the actual reject DataFrame is gone.

### `validate_schema()` Impact (base_component.py lines 314-359)

`ExtractJSONFields._process()` does NOT call `validate_schema()`. The base class `execute()` does not call it either. This means the output DataFrame from ExtractJSONFields is never schema-validated. Any downstream component receiving this DataFrame gets raw extracted values without type coercion.

**Implications**:
- Integer columns remain as Python `int` or `str` (from JSON values)
- Boolean columns remain as Python `bool` or `str`
- Date columns remain as `str` (JSON has no date type)
- If the downstream component expects typed data per the schema, it must call `validate_schema()` itself

**Recommendation**: Add `validate_schema()` call before returning from `_process()`:
```python
if not main_df.empty and self.output_schema:
    main_df = self.validate_schema(main_df, self.output_schema)
```

---

## Appendix O: Detailed Walkthrough of `_is_relative_query()` Failures

### Test Case 1: Simple Nested Property

**Input JSON**:
```json
{
  "employees": [
    {"name": "Alice", "department": {"id": 1, "name": "Engineering"}},
    {"name": "Bob", "department": {"id": 2, "name": "Marketing"}}
  ]
}
```

**Config**:
- `loop_query`: `$.employees[*]`
- `mapping`: `[{"schema_column": "emp_name", "query": "$.name"}, {"schema_column": "dept_name", "query": "$.department.name"}]`

**Expected output** (Talend with USE_LOOP_AS_ROOT=true):
| emp_name | dept_name |
|----------|-----------|
| Alice | Engineering |
| Bob | Marketing |

**V1 actual output**:
- `$.name`: `_is_relative_query("$.name")` -> `query.count('.') = 1`, `<= 1` -> returns `True`. Query runs on loop item. **CORRECT**: Returns "Alice"/"Bob".
- `$.department.name`: `_is_relative_query("$.department.name")` -> `query.count('.') = 2`, `> 1` -> returns `False`. Query runs on FULL document. `$.department.name` on root: no match. Returns `''`.

| emp_name | dept_name |
|----------|-----------|
| Alice | |
| Bob | |

**Result**: **WRONG**. Department names are silently lost.

### Test Case 2: Accessing Root-Level Property

**Input JSON**:
```json
{
  "company": "Acme Corp",
  "employees": [
    {"name": "Alice"},
    {"name": "Bob"}
  ]
}
```

**Config**:
- `loop_query`: `$.employees[*]`
- `mapping`: `[{"schema_column": "emp_name", "query": "$.name"}, {"schema_column": "company", "query": "$.company"}]`
- `use_loop_as_root`: `false` (need to access root-level property)

**Expected output** (Talend with USE_LOOP_AS_ROOT=false):
| emp_name | company |
|----------|---------|
| Alice | Acme Corp |
| Bob | Acme Corp |

**V1 actual output**:
- `$.name`: `_is_relative_query("$.name")` -> returns `True`. Query runs on loop item. Returns "Alice"/"Bob". **CORRECT** (coincidentally).
- `$.company`: `_is_relative_query("$.company")` -> `query.count('.') = 1`, `<= 1` -> returns `True`. Query runs on loop item. `$.company` on employee object: no match. Returns `''`.

| emp_name | company |
|----------|---------|
| Alice | |
| Bob | |

**Result**: **WRONG**. Company name is lost because the heuristic treats ALL single-dot queries as relative, even when `USE_LOOP_AS_ROOT=false`.

### Test Case 3: The Hardcoded `$.employee` Exclusion

**Input JSON**:
```json
{
  "employee": {"name": "Alice", "skills": [{"skill": "Python"}, {"skill": "Java"}]}
}
```

**Config**:
- `loop_query`: `$.employee.skills[*]`
- `mapping`: `[{"schema_column": "skill_name", "query": "$.skill"}, {"schema_column": "emp_name", "query": "$.employee.name"}]`

**V1 actual output**:
- `$.skill`: `_is_relative_query("$.skill")` -> `query.count('.') = 1`, `<= 1`, `not query.startswith('$.employee')` -> returns `True`. Query runs on loop item. **CORRECT**: Returns "Python"/"Java".
- `$.employee.name`: `_is_relative_query("$.employee.name")` -> `query.count('.') = 2`, `> 1` -> returns `False`. Query runs on FULL document. `$.employee.name` finds "Alice". Returns "Alice".

| skill_name | emp_name |
|------------|----------|
| Python | Alice |
| Java | Alice |

**Result**: **CORRECT** -- but ONLY because of the hardcoded `$.employee` exclusion. If the root key were named anything else (e.g., `$.staff.name`), it would still return `True` at line 361 (1 dot, and does not start with `$.employee`), running on the loop item where `$.staff.name` has no match.

This demonstrates that the heuristic was tuned for exactly one test case and fails for general use.

---

## Appendix P: jsonpath_ng Import Analysis

**Current import** (line 11):
```python
from jsonpath_ng import parse
```

This imports the **basic** `jsonpath_ng` parser, which supports standard JSONPath syntax but NOT:
- Filter expressions: `$[?(@.price < 10)]`
- Arithmetic in filters: `$[?(@.price * 2 < 100)]`
- String functions: `$[?(@.name =~ /^A/)]`
- `len()`, `sum()`, etc.

**Alternative** -- `jsonpath_ng.ext`:
```python
from jsonpath_ng.ext import parse
```

This imports the **extended** parser, which adds:
- Filter expressions: `$[?(@.price < 10)]` (operator: `<`, `>`, `<=`, `>=`, `==`, `!=`)
- Arithmetic: `$[?(@.price + @.tax > 100)]`
- Named operators: `sorted()`, `len()`, `sum()`, `avg()`
- String matching: `$[?(@.name =~ "Alice")]`

**Recommendation**: Switch to `jsonpath_ng.ext.parse` to maximize compatibility with Talend's Jayway JsonPath library, which supports filter expressions natively. The extended parser is fully backward-compatible with the basic parser.

**Risk**: Very low. The `ext` module is part of the same `jsonpath_ng` package (no new dependency). All existing JSONPath expressions will continue to work.

---

## Appendix Q: Complete Engine Method Signatures

```python
class ExtractJSONFields(BaseComponent):
    """
    Extract fields from JSON data based on JSONPath queries.
    Talend equivalent: tExtractJSONFields
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.
        Returns list of error strings (empty if valid).
        Called from: _process() line 130.
        """

    def _process(
        self,
        input_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Process input data and extract JSON fields using JSONPath queries.
        Returns: {'main': pd.DataFrame, 'reject': pd.DataFrame}
        Raises: ComponentExecutionError, ConfigurationError
        Called from: BaseComponent._execute_batch() or _execute_streaming()
        """

    def _extract_fields(
        self,
        json_data: Any,          # Parsed JSON (dict/list/scalar)
        loop_query: str,          # JSONPath loop expression
        mapping: List[Dict]       # List of {schema_column, query} dicts
    ) -> List[Dict]:
        """
        Extract fields from JSON data using JSONPath queries.
        Returns list of row dicts.
        Called from: _process() line 174.
        """

    def _is_relative_query(
        self,
        query: str               # JSONPath query string
    ) -> bool:
        """
        BROKEN. Determine if query is relative to loop context.
        Always returns True for single-dot queries, False for multi-dot.
        Called from: _extract_fields() line 287.
        Should be: replaced with use_loop_as_root config flag.
        """
```

---

## Appendix R: Complete Execution Flow Diagram

```
Engine calls component.execute(input_data: pd.DataFrame)
    |
    v
BaseComponent.execute()
    |-- Set status = RUNNING
    |-- Resolve Java expressions (if java_bridge)
    |-- Resolve context variables (if context_manager)
    |-- Auto-select mode (BATCH if input < 3GB)
    |-- _execute_batch(input_data)
    |       |
    |       v
    |   ExtractJSONFields._process(input_data)
    |       |-- _validate_config() -> raise ConfigurationError on errors
    |       |-- Handle list input -> convert to DataFrame
    |       |-- Handle None/empty input -> return empty DFs, stats (0,0,0)
    |       |-- For each row in input_data.iterrows():
    |       |       |-- json.loads(row[0])  <-- BUG: hardcoded column, no type check
    |       |       |-- _extract_fields(json_data, loop_query, mapping)
    |       |       |       |-- parse(loop_query)  <-- RE-COMPILED EVERY ROW
    |       |       |       |-- Find loop matches
    |       |       |       |-- If no matches: [json_data]  <-- BUG: should be []
    |       |       |       |-- For each match:
    |       |       |       |       |-- For each mapping:
    |       |       |       |       |       |-- _is_relative_query()  <-- BROKEN
    |       |       |       |       |       |-- parse(query)  <-- RE-COMPILED EVERY ROW*MAPPING
    |       |       |       |       |       |-- Execute query on context
    |       |       |       |       |       |-- Handle result (scalar/array/empty)
    |       |       |       |       |-- Append row dict
    |       |       |       |-- Return extracted_rows
    |       |       |-- Extend main_output with extracted_rows
    |       |       |-- On error: reject or raise
    |       |-- Build main_df, reject_df
    |       |-- Serialize complex objects (json.dumps for list/dict)
    |       |-- _update_stats(rows_in, rows_out, rows_rejected)
    |       |-- Return {'main': main_df, 'reject': reject_df}
    |
    |-- stats['EXECUTION_TIME'] = elapsed
    |-- _update_global_map()  <-- CRASHES (BUG-EJF-001)
    |-- Set status = SUCCESS  <-- NEVER REACHED
    |-- Return result with stats
```

---

## Appendix S: Converter Dispatch Chain

```
converter.py:convert_job()
    |
    v
converter.py:_parse_component(node)
    |-- Extract component_type from node attributes
    |-- Call component_parser.parse_base_component(node)
    |       |-- Extract all elementParameter values into config_raw
    |       |-- Call _map_component_parameters(component_type, config_raw)
    |       |       |-- For 'tExtractJSONFields': falls through to line 294
    |       |       |       (COMMENT BUG: says "tExtractJSONFields" but code is tExtractDelimitedFields)
    |       |       |-- Returns generic config (may be incomplete)
    |       |-- Parse metadata schemas (FLOW, REJECT)
    |       |-- Mark Java expressions
    |       |-- Return component dict
    |
    |-- elif component_type == 'tExtractJSONFields':  (line 327)
    |       component = self.component_parser.parse_textract_json_fields(node, component)
    |       |-- Extract READ_BY, JSON_PATH_VERSION
    |       |-- Extract LOOP_QUERY / JSON_LOOP_QUERY (with quote stripping)
    |       |-- Extract DIE_ON_ERROR, ENCODING, USE_LOOP_AS_ROOT, SPLIT_LIST, JSONFIELD
    |       |-- Parse MAPPING_4_JSONPATH table (stride-2)
    |       |-- Return updated component
    |
    v
Result: component dict with config, schema, connections
```

**Note**: The `parse_base_component()` call happens FIRST (generic extraction), then the dedicated `parse_textract_json_fields()` call OVERRIDES/SUPPLEMENTS the generic config. The generic `_map_component_parameters()` for tExtractJSONFields falls through to the default case (no dedicated branch in the generic mapper), so the dedicated parser is the primary source of config.

However, there is a subtle issue: `parse_base_component()` calls `_map_component_parameters('tExtractJSONFields', config_raw)`. Looking at the generic mapper code, there is no `elif component_type == 'tExtractJSONFields'` branch. This means `_map_component_parameters()` returns the raw `config_raw` dict. Then `parse_textract_json_fields()` overwrites specific keys. The result is that the component config contains BOTH the raw Talend XML parameters (from generic extraction) AND the mapped config keys (from dedicated parser). This dual presence is generally harmless since the engine reads the mapped keys, but it means the config dict is larger than necessary and contains unmapped raw values.

---

## Appendix T: Additional Edge Cases from Checklist

### Edge Case 14: List input instead of DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend always passes row flows. |
| **V1** | Line 137-138: `if isinstance(input_data, list): input_data = pd.DataFrame(input_data)`. This converts a list of dicts to a DataFrame. If the list contains strings (JSON strings), `pd.DataFrame(['{"a":1}', '{"a":2}'])` creates a single-column DataFrame with column `0` containing the JSON strings. This works correctly with the `row[0]` access pattern. |
| **Verdict** | CORRECT -- defensive coding that handles non-standard callers. |

### Edge Case 15: Very large JSON document per row

| Aspect | Detail |
|--------|--------|
| **Talend** | Limited by Java heap. Typically handles up to ~2GB JSON strings. |
| **V1** | `json.loads()` creates a Python object graph. A 100MB JSON string may consume 500MB+ as Python objects. No memory check before parsing. For very large documents, this can cause OOM. |
| **Verdict** | POTENTIAL ISSUE -- no memory protection for large per-row JSON documents. |

### Edge Case 16: Concurrent access to shared globalMap

| Aspect | Detail |
|--------|--------|
| **Talend** | GlobalMap access is synchronized via Java's `ConcurrentHashMap`. |
| **V1** | `GlobalMap._map` is a plain Python `dict`. In CPython, the GIL provides some protection for simple dict operations (`get`, `put`), but dict resizing during concurrent inserts is not atomic. For production use with concurrent component execution, `GlobalMap` should use `threading.Lock` or `concurrent.futures`-compatible patterns. |
| **Verdict** | POTENTIAL ISSUE -- not thread-safe for concurrent execution. |

### Edge Case 17: JSON with duplicate keys

| Aspect | Detail |
|--------|--------|
| **Talend** | Jayway JsonPath follows RFC 7159 (keys should be unique but duplicates are not forbidden). Last value wins. |
| **V1** | `json.loads()` follows Python's JSON parser: last value wins for duplicate keys. This matches Jayway behavior. `jsonpath_ng` operates on the parsed Python dict (already deduplicated). |
| **Verdict** | CORRECT -- both libraries handle duplicates the same way (last value wins). |

### Edge Case 18: JSON with numeric keys

| Aspect | Detail |
|--------|--------|
| **Talend** | JSON keys are always strings per RFC 7159. `{"1": "value"}` is valid. |
| **V1** | `json.loads()` correctly parses `{"1": "value"}` with string key `"1"`. JSONPath `$.1` or `$['1']` can access it. `jsonpath_ng` handles both syntaxes. |
| **Verdict** | CORRECT |

### Edge Case 19: Extremely deep nesting

| Aspect | Detail |
|--------|--------|
| **Talend** | Limited by Java stack depth. Typically handles ~100 levels. |
| **V1** | `json.loads()` has a default recursion limit. Python's default `sys.getrecursionlimit()` is 1000. Very deep JSON (>500 levels) may hit recursion limits. `jsonpath_ng.parse()` also uses recursion for parsing. |
| **Verdict** | EDGE CASE -- extremely deep nesting (>500 levels) may cause RecursionError. Rare in practice. |

### Edge Case 20: Unicode escape sequences in JSON

| Aspect | Detail |
|--------|--------|
| **Talend** | Java's JSON parser handles `\uXXXX` escapes. |
| **V1** | Python's `json.loads()` handles `\uXXXX` escapes correctly, including surrogate pairs for characters outside BMP (U+10000 to U+10FFFF). |
| **Verdict** | CORRECT |
