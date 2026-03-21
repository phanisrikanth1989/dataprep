# Audit Report: tFileInputJSON / FileInputJSON

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputJSON` |
| **V1 Engine Class** | `FileInputJSON` |
| **Engine File** | `src/v1/engine/components/file/file_input_json.py` (334 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileinputjson()` (lines 1509-1520) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif component_type == 'tFileInputJSON'` branch (line 274) |
| **Registry Aliases** | `FileInputJSON`, `tFileInputJSON` (registered in `src/v1/engine/engine.py` lines 95-96) |
| **Converter Name Mapping** | `tFileInputJSON` -> `FileInputJSONComponent` (component_parser.py line 101) -- **MISMATCH with engine registry** |
| **Category** | File / Input (also Internet family) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_json.py` | Engine implementation (334 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1509-1520) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 274) | Dispatch -- dedicated `elif` for `tFileInputJSON` calls `parse_tfileinputjson()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 21: `from .file_input_json import FileInputJSON`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 1 | 3 | 3 | 1 | 5 of 18 Talend params extracted (28%); missing USE_URL, URL, READ_BY, API_VERSION, ADVANCED_SEPARATOR, VALIDATE_DATE, USE_LOOP_AS_ROOT, etc.; **P0 naming mismatch** -- converter writes `FileInputJSONComponent`, engine registers `FileInputJSON` |
| Engine Feature Parity | **Y** | 0 | 6 | 3 | 1 | Has JSONPath extraction, URL reading, reject flow, schema type coercion, advanced separators, date checking. Missing XPath mode, globalMap `ERROR_MESSAGE`, Talend-default encoding. **`die_on_error` does not stop per-row errors; date pattern key mismatch makes date validation non-functional for converted jobs.** |
| Code Quality | **Y** | 2 | 5 | 5 | 2 | Cross-cutting base class bugs; dead `validate_config()`; NaN handling gaps; type demotion via DataFrame construction; unused imports; **`die_on_error` per-row bypass; schema date key mismatch; `json.dumps()` crash on non-serializable values** |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | Row-by-row JSONPath parsing is inherently slow for large files; list/dict serialization pass on output; no streaming mode for large JSON files |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes (44 issues: 4 P0, 16 P1, 17 P2, 7 P3)**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputJSON Does

`tFileInputJSON` reads JSON data from a file or URL and extracts structured records using JSONPath or XPath expressions. It iterates over a loop node in the JSON structure, extracting fields from each element according to a mapping table, and outputs the extracted data as a row flow. The component is commonly used for reading REST API responses saved as files, configuration files, and hierarchical data exports.

**Source**: [tFileInputJSON Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/json/tfileinputjson-standard-properties), [tFileInputJSON Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/json/tfileinputjson-standard-properties), [tFileInputJSON Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/json/tfileinputjson)

**Component family**: JSON (File / Internet / Input)
**Available in**: All Talend products (Standard). Also available in Spark Batch and Spark Streaming variants.
**Required JARs**: `json-path-xxx.jar`, `json-smart-xxx.jar`, `asm-xxx.jar`, `accessors-smart-xxx.jar`, `slf4j-api-xxx.jar`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. Each column maps to a JSONPath/XPath query in the Mapping table. |
| 3 | Read By | `READ_BY` | Dropdown | `JsonPath` | Method for extracting JSON data. Three options: `JsonPath` (JSONPath with loop node), `Xpath` (XPath query), `JsonPath without loop` (JSONPath query applied directly, no iteration). When `XPath` is selected, JSON field names must not start with numbers. |
| 4 | API Version | `API_VERSION` | Dropdown | -- | JSONPath API version selection. Controls which JSONPath specification is used for expression parsing. |
| 5 | Use URL | `USE_URL` | Boolean (CHECK) | `false` | When selected, retrieves JSON data directly from a web URL instead of a local file. Reveals the URL field and hides the Filename field. |
| 6 | URL | `URL` | Expression (String) | -- | Web source URL for data retrieval. Only visible when `USE_URL=true`. Supports context variables and expressions. |
| 7 | Filename | `FILENAME` | Expression (String) | -- | **Mandatory** (unless USE_URL=true). Absolute file path to JSON file. Supports context variables, globalMap references, Java expressions. |
| 8 | Loop JSON Query | `JSON_LOOP_QUERY` | Expression (String) | -- | **Mandatory**. JSONPath or XPath expression defining the loop node. Each match of this expression produces one output row. Example: `"$.store.goods.book[*]"` iterates over all books. Must be enclosed in double quotes in Talend. |
| 9 | Mapping | `MAPPING_JSONPATH` | Table | -- | **Mandatory**. Maps schema columns to JSON nodes via JSONPath or XPath expressions relative to the loop node. Each row has: `SCHEMA_COLUMN` (column name from schema) and `QUERY` (JSONPath/XPath expression). Expressions enclosed in double quotes. |
| 10 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on parse/read error. When unchecked, malformed records are routed to the REJECT flow (if connected) or silently skipped. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 11 | JDK Version | `JDK_VERSION` | Dropdown | -- | JDK 8-11 or JDK 11+. When JDK 11+ selected, Nashorn scripting engine may need to be included separately. |
| 12 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands and decimal separators. |
| 13 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 14 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 15 | Use Loop Node as Root | `USE_LOOP_AS_ROOT` | Boolean (CHECK) | `false` | Use the loop node as the root element for querying the file. When enabled, mapping JSONPath queries are relative to the loop result, not the document root. |
| 16 | Validate Date | `VALIDATE_DATE` | Boolean (CHECK) | `false` | Strictly validate date-typed columns against the date pattern defined in the input schema. Only available when Read By is XPath. Invalid dates cause row rejection. |
| 17 | Encoding | `ENCODING` | Dropdown / Custom | -- | Character encoding for JSON file reading. Common values: UTF-8, ISO-8859-1, etc. Compulsory for database handling. |
| 18 | Include Nashorn Library | `INCLUDE_NASHORN` | Boolean (CHECK) | `false` | Required for JDK 15+. Includes the Nashorn JavaScript engine library. |
| 19 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully extracted JSON records matching the output schema. All columns defined in the schema are present. Primary data output. This is a start component -- an output link is **mandatory**. |
| `REJECT` | Output | Row > Reject | Records that failed parsing, type conversion, or JSONPath extraction. Includes ALL original schema columns (with whatever partial data was extracted) PLUS two additional columns: `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of JSON elements processed (loop node matches). This is the primary row count variable. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

**Note on NB_LINE_OK / NB_LINE_REJECT**: Official Talend documentation for tFileInputJSON lists only `NB_LINE` and `ERROR_MESSAGE` as global variables. The `NB_LINE_OK` and `NB_LINE_REJECT` split is available in the v1 engine via the base class statistics mechanism but is not an official Talend variable for this component.

### 3.5 Behavioral Notes

1. **JSONPath expressions must be quoted**: In Talend, JSONPath expressions in the Loop JSON Query and Mapping fields are wrapped in double quotes (e.g., `"$.store.book[*]"`). The engine must strip these quotes before parsing.

2. **Loop node iteration**: The Loop JSON Query defines the iteration level. Each match produces one output row. If the query matches an array, each element becomes a row. If it matches a single object, one row is produced.

3. **Mapping is relative to loop node**: By default, mapping JSONPath queries are relative to each loop element, NOT to the document root. When `USE_LOOP_AS_ROOT=true`, the loop result itself becomes the root for sub-queries.

4. **Read By modes**:
   - `JsonPath`: Uses JSONPath expressions for both loop and mapping. Standard mode.
   - `Xpath`: Uses XPath expressions. JSON field names must not start with numbers.
   - `JsonPath without loop`: Applies JSONPath queries directly without a loop node. Each query produces one value.

5. **REJECT flow behavior**: When a REJECT link is connected and `DIE_ON_ERROR=false`:
   - Records where JSONPath extraction fails (missing node, type mismatch) are sent to REJECT
   - REJECT rows contain ALL original schema columns PLUS `errorCode` and `errorMessage`
   - When REJECT is NOT connected, errors are silently skipped or cause job failure depending on `DIE_ON_ERROR`

6. **URL reading**: When `USE_URL=true`, the component opens an HTTP(S) connection and reads JSON directly from the web. The URL field supports context variables and Java expressions. This is commonly used for REST API integration.

7. **Complex JSON values**: When a JSONPath expression matches a nested object or array (not a scalar), Talend serializes it as a JSON string in the output field. The v1 engine also does this (line 268-269).

8. **Null handling**: When a JSONPath expression matches no node in a particular element, the value is `null`. Talend passes this through as null/empty. The v1 engine represents this as an empty list `[]` (from `jsonpath_ng` returning no matches), which may differ from Talend's `null`.

9. **Encoding**: Talend does not have a strong default for encoding on this component. The engine defaults to `UTF-8`, which is reasonable for JSON files since JSON is defined as UTF-8 by RFC 8259.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_tfileinputjson()` in `component_parser.py` lines 1509-1520) registered via a dedicated `elif component_type == 'tFileInputJSON'` branch in `converter.py` line 274. This is the correct approach per STANDARDS.md.

However, the parser is **extremely minimal** -- only 12 lines extracting 5 parameters out of 19 Talend parameters.

**Converter flow**:
1. `converter.py:_parse_component()` matches `tFileInputJSON` at line 274
2. Calls `component_parser.parse_tfileinputjson(node, component)`
3. Extracts: FILENAME, JSON_LOOP_QUERY, MAPPING_JSONPATH, DIE_ON_ERROR, ENCODING
4. Returns component with mapped config

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filename` | 1511 | Direct `.get('value', '')`. No expression handling or quote stripping. |
| 2 | `JSON_LOOP_QUERY` | Yes | `json_loop_query` | 1512 | Direct `.get('value', '')`. No quote stripping -- engine handles this. |
| 3 | `MAPPING_JSONPATH` | Yes | `mapping` | 1513-1517 | Iterates `elementValue` children. Uses `elementRef` for column and `value` for jsonpath. |
| 4 | `DIE_ON_ERROR` | Yes | `die_on_error` | 1518 | Boolean conversion from `'true'/'false'` string. Default `false` matches Talend. |
| 5 | `ENCODING` | Yes | `encoding` | 1519 | Default `'UTF-8'`. Reasonable for JSON (RFC 8259 specifies UTF-8). |
| 6 | `READ_BY` | **No** | -- | -- | **Not extracted. Engine always uses JSONPath. XPath mode unavailable.** |
| 7 | `API_VERSION` | **No** | -- | -- | **Not extracted. JSONPath API version selection unavailable.** |
| 8 | `USE_URL` | **No** | -- | -- | **Not extracted. Engine has `useurl` in config, but converter never sets it.** |
| 9 | `URL` | **No** | -- | -- | **Not extracted. URL field for web-based reading not mapped.** |
| 10 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted. Engine has `advanced_separator` support but converter never sets it.** |
| 11 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 12 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 13 | `USE_LOOP_AS_ROOT` | **No** | -- | -- | **Not extracted. Engine has `use_loop_as_root` support but converter never sets it.** |
| 14 | `VALIDATE_DATE` | **No** | -- | -- | **Not extracted. Engine has `check_date` support but converter never sets it.** |
| 15 | `JDK_VERSION` | **No** | -- | -- | Not needed at runtime (JDK configuration for code generation). |
| 16 | `INCLUDE_NASHORN` | **No** | -- | -- | Not needed at runtime (Nashorn JS engine for JDK 15+). |
| 17 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used). |
| 18 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |
| 19 | `SCHEMA` | Yes (generic) | `schema` | generic | Extracted via generic schema extraction in `parse_base_component()`. |

**Summary**: 5 of 19 parameters extracted (26%). 8 runtime-relevant parameters are missing (READ_BY, API_VERSION, USE_URL, URL, ADVANCED_SEPARATOR, THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR, USE_LOOP_AS_ROOT, VALIDATE_DATE). However, the engine already has config keys for many of these (`useurl`, `urlpath`, `advanced_separator`, `thousands_separator`, `decimal_separator`, `check_date`, `use_loop_as_root`, `read_by`, `json_path_version`) -- they are simply never populated by the converter.

### 4.2 Mapping Extraction

The converter's mapping extraction (lines 1513-1517) uses a specific approach:
```python
for mapping_entry in node.findall('.//elementParameter[@name="MAPPING_JSONPATH"]/elementValue'):
    column = mapping_entry.get('elementRef', '')
    jsonpath = mapping_entry.get('value', '')
    component['config']['mapping'].append({'column': column, 'jsonpath': jsonpath})
```

This produces a list of `{'column': ..., 'jsonpath': ...}` dicts. However, the Talend XML for `MAPPING_JSONPATH` typically stores data as alternating `SCHEMA_COLUMN` / `QUERY` pairs:
- `elementRef="SCHEMA_COLUMN"` with `value="column_name"`
- `elementRef="QUERY"` with `value="\"$.path\""`

The engine has a `_normalize_mapping()` method (lines 93-120) that converts this alternating pair format to the standard `{'column': ..., 'jsonpath': ...}` format. This means the converter's extraction of `elementRef` as `column` would produce entries where `column` is `"SCHEMA_COLUMN"` or `"QUERY"` -- NOT the actual column name. The engine's `_normalize_mapping()` specifically checks for `column == 'SCHEMA_COLUMN'` (line 111), confirming that the converter produces this alternating format.

**This is architecturally confusing but functionally correct** -- the converter passes through the raw Talend XML structure, and the engine normalizes it. However, the column name ends up in `mapping_entry.get('value')` when `elementRef == 'SCHEMA_COLUMN'`, and the jsonpath ends up in `mapping_entry.get('value')` when `elementRef == 'QUERY'`. So both `column` and `jsonpath` in the converter output contain the wrong field -- `column` holds `"SCHEMA_COLUMN"` or `"QUERY"` (the elementRef), while `jsonpath` holds the actual value. This is only correct because the engine's `_normalize_mapping()` reads from the `jsonpath` field for both the column name AND the actual JSONPath.

### 4.3 Schema Extraction

Schema is extracted generically in `parse_base_component()`.

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) |
| `nullable` | Yes | Boolean conversion from string |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if present |
| `precision` | Yes | Integer conversion, only if present |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime format |
| `default` | **No** | Column default value not extracted from XML |

### 4.4 Expression Handling

**Context variable handling**: The generic `parse_base_component()` handles `context.var` references by wrapping as `${context.var}`. However, `parse_tfileinputjson()` does NOT call generic context handling -- it directly reads raw XML values. Context variables in FILENAME, JSON_LOOP_QUERY, or MAPPING expressions will be passed through as raw `context.varName` strings without `${...}` wrapping. Resolution depends on the engine's `context_manager.resolve_dict()` call in `BaseComponent.execute()`.

**Java expression handling**: Similarly, no `mark_java_expression()` call is made in `parse_tfileinputjson()`. Java expressions in parameter values (e.g., `context.filePath + "/data.json"`) will NOT be marked with `{{java}}` prefix, so they will not be resolved by the Java bridge.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FIJ-001 | **P0** | **Component name mismatch**: `component_mapping` on line 101 maps `tFileInputJSON` to `FileInputJSONComponent`, but the engine registry (`engine.py` lines 95-96) registers `FileInputJSON` and `tFileInputJSON`. The converter outputs `type: 'FileInputJSONComponent'` in the JSON config, which the engine will NOT find in its registry. **Result: Component instantiation will fail at runtime for any converted Talend job using tFileInputJSON.** |
| CONV-FIJ-002 | **P1** | **`USE_URL` and `URL` not extracted**: The engine supports URL-based reading via `useurl` and `urlpath` config keys (lines 156-157, 168-173), but the converter never sets these. Talend jobs that read JSON from URLs will silently fall back to file reading and fail with missing filename error. |
| CONV-FIJ-003 | **P1** | **`READ_BY` not extracted**: The engine has a `read_by` config key (line 162) but it is never set by the converter. XPath mode and "JSONPath without loop" mode are unavailable for converted jobs. |
| CONV-FIJ-004 | **P1** | **No Java expression marking**: Unlike other dedicated parsers, `parse_tfileinputjson()` does not call `mark_java_expression()` on any values. Java expressions in FILENAME, JSON_LOOP_QUERY, or mapping queries will be passed as literal strings, causing runtime failures for jobs that use expressions like `context.basePath + "/file.json"`. |
| CONV-FIJ-005 | **P2** | **`ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR` not extracted**: Engine has full support (lines 158-160, 221-229) but converter never populates these config keys. |
| CONV-FIJ-006 | **P2** | **`USE_LOOP_AS_ROOT` not extracted**: Engine has support (lines 164, 188-190) but converter never sets it. |
| CONV-FIJ-007 | **P2** | **`VALIDATE_DATE` not extracted**: Engine has `check_date` support (lines 161, 233-240) but converter never sets it. |
| CONV-FIJ-008 | **P3** | **`API_VERSION` not extracted**: Engine has `json_path_version` config key (line 163) but it is never used in processing anyway. Low impact. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read JSON file | **Yes** | High | `_process()` lines 174-177 | Uses `json.load()` with `open(filename, 'r', encoding=encoding)`. Correct. |
| 2 | Read JSON from URL | **Yes** | Medium | `_process()` lines 168-173 | Uses `urllib.request.urlopen()`. No timeout, no headers, no auth. Basic implementation. |
| 3 | JSONPath loop extraction | **Yes** | High | `_process()` lines 182-186 | Uses `jsonpath_ng.ext.parse()`. Strips quotes from expression. Correct. |
| 4 | JSONPath field mapping | **Yes** | High | `_process()` lines 201-212 | Per-element JSONPath extraction with `parse(jsonpath).find(element)`. Correct. |
| 5 | Mapping normalization | **Yes** | High | `_normalize_mapping()` lines 93-120 | Converts alternating SCHEMA_COLUMN/QUERY pairs to column/jsonpath format. Handles Talend XML structure. |
| 6 | Schema type coercion | **Yes** | Medium | `_process()` lines 214-240 | Supports `id_Integer`, `id_Float`, `id_Date` types. Uses schema column definitions. |
| 7 | Advanced separator | **Yes** | High | `_process()` lines 221-222, 228-229 | String replacement of thousands/decimal separators before numeric conversion. |
| 8 | Date validation | **Yes** | Medium | `_process()` lines 233-240 | Validates against schema pattern using `datetime.strptime()`. Only active when `check_date=True`. Java pattern format (from schema) may differ from Python strftime. |
| 9 | Die on error | **Yes** | **Low** | `_process()` lines 154, 243-251, 279-284 | Outer file-level exception respects `die_on_error`. **However, inner per-row try/except (lines 200-247) NEVER checks `die_on_error` -- always catches row errors and routes to reject regardless of setting. Behavioral divergence from Talend.** See BUG-FIJ-007. |
| 10 | REJECT flow | **Yes** | Medium | `_process()` lines 243-251, 274-276 | Rows with extraction/conversion errors get `errorCode='PARSE_ERROR'` and `errorMessage`. Returned as `result['reject']`. **This is better than tFileInputDelimited which has NO reject flow.** |
| 11 | Use loop as root | **Yes** | Medium | `_process()` lines 188-190 | Unwraps single-element list when `use_loop_as_root=True`. Does NOT handle the full Talend semantics where sub-queries become relative to the loop result. |
| 12 | Complex value serialization | **Yes** | High | `_process()` lines 266-269 | Lists and dicts in output columns are serialized to JSON strings via `json.dumps()`. Matches Talend behavior. |
| 13 | Encoding support | **Yes** | High | `_process()` lines 155, 172, 176 | Configurable encoding for both file and URL reading. Default `UTF-8`. |
| 14 | Quote stripping from JSONPath | **Yes** | High | `_process()` line 184, 204-205 | Strips surrounding quotes from JSONPath expressions. Handles Talend's quoting convention. |
| 15 | Multi-match handling | **Yes** | Medium | `_process()` lines 208-213 | `[*]` or `.*` in JSONPath keeps results as list. Single match is flattened. **However, the code on lines 208-213 has identical branches** -- both `if` and `else` produce `[v.value for v in value_matches]`. The `[*]`/`.*` check is dead code; behavior is identical regardless. |
| 16 | Statistics tracking | **Yes** | High | `_process()` lines 258-259 | Calls `_update_stats(total, ok, reject)` with correct counts. |
| 17 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()`. |
| 18 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers. But converter never marks expressions (see CONV-FIJ-004). |
| 19 | **XPath read mode** | **No** | N/A | -- | **No XPath parser. Only JSONPath via `jsonpath_ng` library.** |
| 20 | **JSONPath without loop mode** | **No** | N/A | -- | **No direct query mode without a loop expression.** |
| 21 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |
| 22 | **`{id}_FILENAME` globalMap** | **No** | N/A | -- | **Resolved filename not stored in globalMap.** |
| 23 | **URL authentication** | **No** | N/A | -- | **`urlopen()` has no support for HTTP headers, auth tokens, or timeouts.** |
| 24 | **Nashorn / JDK version** | **No** | N/A | -- | Not applicable (Python engine, not JVM). |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIJ-001 | **P1** | **No XPath read mode**: Talend supports `READ_BY=Xpath` for XPath-based JSON extraction. The v1 engine only supports JSONPath via the `jsonpath_ng` library. Jobs using XPath mode will fail at runtime with a `jsonpath_ng` parse error. |
| ENG-FIJ-002 | **P1** | **No "JSONPath without loop" mode**: Talend supports `READ_BY=JsonPath without loop` where queries are applied directly without iteration. The v1 engine always requires `json_loop_query` and iterates. |
| ENG-FIJ-003 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream reference. The base class `error_message` attribute is set (line 229) but never propagated to globalMap. |
| ENG-FIJ-004 | **P1** | **URL reading is bare-bones**: `urlopen(urlpath)` has no timeout, no HTTP headers, no authentication, no proxy support. Talend's URL reading supports more sophisticated HTTP features. Production jobs accessing REST APIs will likely need more robust HTTP handling. |
| ENG-FIJ-005 | **P2** | **Null/missing JSONPath match returns empty list, not None**: When `jsonpath_ng` finds no match for a field, `value_matches` is empty, producing `val = []` (empty list). Talend would produce `null`. This causes downstream type coercion to fail differently -- `int([])` raises TypeError vs `int(None)` raises TypeError, but the error message differs, and empty list `[]` is truthy while `None` is falsy. |
| ENG-FIJ-006 | **P2** | **Dead multi-match branch**: Lines 208-213 have identical code in both `if` and `else` branches. The `[*]`/`.*` check for keeping results as list vs flattening is a no-op. Both branches produce a list, with single-element lists being flattened identically. |
| ENG-FIJ-007 | **P2** | **`use_loop_as_root` only unwraps single-element lists**: Line 188-190 only handles the case where `elements` is a single-element list containing a list. This does not implement the full Talend behavior where `USE_LOOP_AS_ROOT=true` changes how sub-queries are resolved relative to the loop node. |
| ENG-FIJ-008 | **P3** | **No Nashorn / JDK version handling**: Not relevant for Python engine, but noted for completeness. |
| ENG-FIJ-009 | **P1** | **`die_on_error=True` does not stop per-row errors**: In Talend, `DIE_ON_ERROR=true` aborts the job on the first row-level parse/coercion error. In v1, the inner per-row try/except (lines 200-247) never checks `die_on_error` and always routes errors to reject. Only file-level errors (e.g., file not found, invalid JSON) respect the flag. See BUG-FIJ-007. *(Adversarial review finding)* |
| ENG-FIJ-010 | **P1** | **Date validation non-functional for converted jobs**: Schema date pattern stored by converter as `'date_pattern'` key but engine reads `'pattern'` key (line 234). Pattern is always `None`, so `datetime.strptime(val, None)` is never called and date validation silently skips. See BUG-FIJ-008. *(Adversarial review finding)* |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. **However, see BUG-FIJ-001 -- `_update_global_map()` will crash before storing stats.** |
| `{id}_NB_LINE_OK` | No (v1 only) | **Yes** | Same mechanism | Not a standard Talend variable for this component, but tracked by v1 engine. |
| `{id}_NB_LINE_REJECT` | No (v1 only) | **Yes** | Same mechanism | Not a standard Talend variable, but correctly tracks rejected rows. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIJ-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components. When `global_map` is set, `execute()` calls `_update_global_map()` on line 218 (success path) and line 231 (error path). The `NameError` will be raised BEFORE `self.status = ComponentStatus.SUCCESS` on line 220, which means **the component will never reach SUCCESS status** and stats will never be stored in globalMap. The exception from `_update_global_map()` propagates up through `execute()` into the error handler on line 227, which calls `_update_global_map()` AGAIN, causing a second `NameError`. |
| BUG-FIJ-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). `default` is not defined in scope. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. Even if BUG-FIJ-001 were fixed, `put_component_stat()` on line 49 calls `self.put(key, value)` which works, but any subsequent `get()` call will crash. |
| BUG-FIJ-003 | **P1** | `src/v1/engine/components/file/file_input_json.py:262-263` | **Empty `output_data` produces DataFrame with no columns**: When ALL rows are rejected (e.g., all JSONPath extractions fail), `pd.DataFrame([])` creates a DataFrame with 0 rows and 0 columns. Downstream components expecting specific columns will fail. Talend would produce an empty DataFrame with the schema columns still defined. Should pass column names: `pd.DataFrame(output_data, columns=[m['column'] for m in mapping])`. |
| BUG-FIJ-004 | **P1** | `src/v1/engine/components/file/file_input_json.py:208-213` | **Dead code in multi-match branch**: The `if '[*]' in jsonpath or '.*' in jsonpath` condition on line 208 has the **exact same code** in both branches. The `else` branch (lines 210-213) produces `val = [v.value for v in value_matches]` then flattens single-element lists to scalars. The `if` branch (line 209) produces the same list `[v.value for v in value_matches]` but does NOT prevent flattening (since the `if len(val) == 1` check is only in the `else` branch). This means wildcard queries like `$.items[*]` that match exactly one element will be flattened to a scalar, losing the list semantics. The developer likely intended the `if` branch to keep the list as-is without flattening. |
| BUG-FIJ-005 | **P1** | `src/v1/engine/components/file/file_input_json.py:286-334` | **`validate_config()` is never called**: The method contains 48 lines of validation logic (required fields, mapping structure, schema type, encoding type, URL config). It is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (missing filename, empty mapping, etc.) are not caught until they cause `AttributeError` or `TypeError` deep in processing. |
| BUG-FIJ-006 | **P2** | `src/v1/engine/components/file/file_input_json.py:242` | **Debug log references last loop variable only**: `logger.debug(f"[{self.id}] Row {i} column '{column_name}' extracted value: {val}")` is OUTSIDE the inner `for mapping_entry in mapping` loop, so `column_name` and `val` reference only the last column processed. This log message is misleading for debugging multi-column extractions. |
| BUG-FIJ-007 | **P1** | `src/v1/engine/components/file/file_input_json.py:200-247` | **`die_on_error=True` does NOT stop per-row errors**: Inner try/except (lines 200-247) NEVER checks `die_on_error`. Always catches row errors and routes to reject, regardless of setting. Only file-level errors respect `die_on_error`. Behavioral divergence from Talend, where `die_on_error=True` should abort the job on the first row-level parse/coercion error instead of routing it to reject. *(Adversarial review finding)* |
| BUG-FIJ-008 | **P1** | `src/converters/complex_converter/component_parser.py:500`, `src/v1/engine/components/file/file_input_json.py:234` | **Schema date pattern key mismatch**: Converter stores the date pattern as `'date_pattern'` (component_parser.py:500) but the engine reads `'pattern'` (file_input_json.py:234). Pattern is never found, so date validation is completely non-functional for converted jobs. Even when `check_date=True` is set manually, the engine looks up `col_def.get('pattern')` which is always `None` because the converter wrote `col_def['date_pattern']`. *(Adversarial review finding)* |
| BUG-FIJ-009 | **P2** | `src/v1/engine/components/file/file_input_json.py:266-269` | **`json.dumps()` on non-serializable values can crash and lose ALL data**: Lines 266-269 call `json.dumps(v)` on list/dict column values, but this will raise `TypeError` on non-serializable values (e.g., `datetime`, `Decimal`, `bytes`). This error falls OUTSIDE the per-row try/except block, so it is caught by the outer handler (line 279) which returns empty DataFrames -- losing ALL successfully processed rows. A single non-serializable value in any row/column discards the entire result set. *(Adversarial review finding)* |
| BUG-FIJ-010 | **P2** | `src/v1/engine/components/file/file_input_json.py:210-213` | **Empty match produces empty list instead of None**: When `value_matches` is empty (no JSONPath match), `val = []` (empty list). After the `if len(val) == 1` check (which fails for length 0), `val` remains `[]`. This empty list is then stored in the row dict and passes to schema type coercion. `int([])` and `float([])` will raise `TypeError`, not `ValueError`, producing a confusing error message in the reject row. Additionally, `[]` is not caught by the `if val is not None` check on line 218, so type coercion is attempted on an empty list. |
| BUG-FIJ-011 | **P2** | `src/v1/engine/components/file/file_input_json.py:10-14` | **Unused imports**: `os`, `re`, `codecs` are imported but never used in the module. `os` was likely intended for file existence checks (which the component lacks), `re` for regex operations, and `codecs` for encoding handling. These are dead imports. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIJ-001 | **P1** | **Converter name `FileInputJSONComponent` vs engine name `FileInputJSON`**: The converter's `component_mapping` (line 101) outputs `FileInputJSONComponent` as the component type, but the engine registry uses `FileInputJSON`. This is not just a cosmetic issue -- it causes runtime failure. See CONV-FIJ-001. |
| NAME-FIJ-002 | **P2** | **Config key `useurl` (no underscore) vs `urlpath` (no underscore)**: The engine uses `useurl` (line 156) instead of the more consistent `use_url` pattern used by other config keys (`use_loop_as_root`, line 164). Minor inconsistency. |
| NAME-FIJ-003 | **P2** | **Config key `check_date` vs Talend `VALIDATE_DATE`**: The engine uses `check_date` (line 161) while Talend calls it `VALIDATE_DATE`. This differs from the standard Talend-to-v1 naming convention used by other components. |
| NAME-FIJ-004 | **P3** | **Config key `json_path_version` vs Talend `API_VERSION`**: Non-standard mapping, but low impact since the key is never used. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIJ-001 | **P1** | "Component name in converter mapping must match engine registry" | Converter outputs `FileInputJSONComponent`; engine registers `FileInputJSON`. Fatal mismatch. |
| STD-FIJ-002 | **P2** | "`validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract technically met but functionally useless. Dead code. |
| STD-FIJ-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) via `ExpressionConverter.convert_type()`. |
| STD-FIJ-004 | **P3** | "No unused imports" | `os`, `re`, `codecs` imported but never used. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FIJ-001 | **P3** | **Duplicate logging**: Lines 254-255 log the same completion message twice -- once via `logger` (module-level) and once via `self.logger` (instance-level). Both reference `__name__` so they produce identical output on the same logger. Redundant. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FIJ-001 | **P2** | **No URL validation for `urlopen()`**: `urlopen(urlpath)` on line 170 accepts any URL including `file:///` scheme, which could be used for local file access bypass. Also no SSL certificate verification control. |
| SEC-FIJ-002 | **P3** | **No path traversal protection**: `filename` from config is used directly with `open()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` AND instance-level `self.logger = logging.getLogger(__name__)`. Redundant -- both point to same logger. |
| Component ID prefix | Most log messages use `[{self.id}]` prefix -- correct. Some use `Component {self.id}:` format (line 255) -- inconsistent. |
| Level usage | INFO for milestones, DEBUG for details, ERROR for failures -- mostly correct. |
| Start/complete logging | `_process()` logs start (line 136) and completion (lines 254-255) -- correct but duplicate. |
| Sensitive data | URL may be logged on line 169 (could contain auth tokens in query params). |
| No print statements | No `print()` calls -- correct. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions from `exceptions.py`. Uses generic `Exception`. |
| Exception chaining | No `raise ... from e` pattern used. |
| `die_on_error` handling | Two-level error handling: inner per-row try/except (line 200) creates reject rows; outer try/except (line 279) re-raises or returns empty DF. **FLAW**: Inner try/except NEVER checks `die_on_error` -- always routes to reject. Only file-level errors respect the flag. See BUG-FIJ-007. |
| No bare `except` | All except clauses specify `Exception` -- correct. |
| Error messages | Include component ID and error details -- correct. |
| Graceful degradation | Returns `{'main': pd.DataFrame([]), 'reject': pd.DataFrame([])}` when `die_on_error=false` (line 284). However, `pd.DataFrame([])` has no columns -- see BUG-FIJ-003. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has return type `Dict[str, Any]` -- correct. `validate_config()` has return type `List[str]` -- correct. |
| Parameter types | `_normalize_mapping()` has `mapping: List[Dict]` -- correct. `_process()` has `input_data=None` without type hint -- should be `Optional[pd.DataFrame]`. |
| Complex types | Uses `Dict[str, Any]`, `List[Dict]`, `List[str]` -- correct. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIJ-001 | **P2** | **Row-by-row JSONPath parsing**: Lines 201-206 call `parse(jsonpath).find(element)` for EVERY column of EVERY row. The `parse()` call compiles the JSONPath expression each time. For a file with 10,000 elements and 10 columns, this is 100,000 JSONPath compilations. The expressions should be pre-compiled once before the element loop and reused. |
| PERF-FIJ-002 | **P2** | **Post-DataFrame serialization pass**: Lines 266-269 iterate ALL columns of the output DataFrame to check for list/dict values and JSON-serialize them. This is a second full scan of the data. Could be done during row construction (line 241) instead. |
| PERF-FIJ-003 | **P3** | **`jsonpath_ng.ext` import inside `_process()`**: Line 182 imports `from jsonpath_ng.ext import parse` inside the processing method. While Python caches imports after the first load, the import lookup still has overhead per invocation. Should be a module-level import. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | **Not implemented**. The entire JSON file is loaded into memory via `json.load()` (line 177) or `json.loads()` (line 173). For large JSON files (100MB+), this will consume significant memory. No chunked reading or streaming JSON parser (like `ijson`) is used. |
| Memory threshold | Inherited `MEMORY_THRESHOLD_MB = 3072` from `BaseComponent`, but never checked. `_auto_select_mode()` returns BATCH for `input_data=None` (line 238-239 of base class), so this component always runs in batch. |
| Full data duplication | The component creates `elements` (all JSONPath matches), then `output_data` (list of dicts), then `main_df` (DataFrame). At peak, three copies of the data exist in memory simultaneously. |
| URL response buffering | `response.read()` (line 171) reads the entire HTTP response into memory as bytes. For large URL responses, this doubles memory usage (bytes + parsed JSON). |

### 7.2 Streaming Mode via Base Class

When `execution_mode=HYBRID` and input_data=None (file input component):
1. `execute()` calls `_auto_select_mode(None)` which returns `BATCH` (base class line 238-239)
2. Component always runs in batch mode
3. Even if streaming were selected, `_execute_streaming()` with `input_data=None` calls `self._process(None)` (base class line 258) -- same as batch
4. **Conclusion**: Streaming mode has NO effect on this component. Large JSON files will always be loaded entirely into memory.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputJSON` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tfileinputjson()` found |

**Key finding**: The v1 engine has ZERO tests for this component. All 334 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic JSON read | P0 | Read a simple JSON file with flat objects, verify row count and column values match expected output |
| 2 | JSONPath loop extraction | P0 | Read nested JSON with `$.items[*]` loop, verify each array element becomes one row |
| 3 | Schema type coercion | P0 | Read with typed schema (int, float, string, date), verify correct type for each column |
| 4 | Missing file + die_on_error=true | P0 | Should raise Exception with descriptive message |
| 5 | Missing file + die_on_error=false | P0 | Should return empty DataFrames in both main and reject |
| 6 | Empty JSON array | P0 | `{"items": []}` with loop `$.items[*]` should return empty DataFrame, stats (0, 0, 0) |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | REJECT flow | P1 | Row with invalid integer value should go to reject with errorCode='PARSE_ERROR' |
| 9 | Mixed valid/invalid rows | P1 | File with some valid and some invalid rows should produce both main and reject DataFrames |
| 10 | URL reading | P1 | Read JSON from a URL endpoint (mock HTTP server), verify correct data extraction |
| 11 | Nested JSONPath | P1 | JSONPath like `$.users[*].address.city` extracts deeply nested values correctly |
| 12 | Encoding UTF-8 BOM | P1 | Read JSON file with UTF-8 BOM, verify no BOM character in output |
| 13 | Encoding ISO-8859-1 | P1 | Read JSON file with non-UTF-8 encoding, verify correct character decoding |
| 14 | Mapping normalization | P1 | Raw Talend SCHEMA_COLUMN/QUERY alternating pairs are correctly normalized |
| 15 | Complex value serialization | P1 | Nested objects/arrays in output columns are JSON-serialized as strings |
| 16 | Context variable in filename | P1 | `${context.input_dir}/file.json` should resolve via context manager |
| 17 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution (requires BUG-FIJ-001 fix) |
| 18 | Advanced separator | P1 | Number `1.234.567,89` with European separators parsed correctly as float |
| 19 | Date validation | P1 | Date column with `check_date=True` and invalid date should reject row |
| 20 | Use loop as root | P1 | With `use_loop_as_root=True`, sub-queries resolve relative to loop result |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Large JSON file | P2 | Verify memory behavior with 50MB+ JSON file |
| 22 | Null JSON values | P2 | JSON `null` values handled correctly (not converted to string "null") |
| 23 | Missing JSONPath field | P2 | JSONPath matching no node produces correct null/empty value |
| 24 | Wildcard JSONPath `[*]` | P2 | Array wildcard correctly produces list values |
| 25 | Concurrent reads | P2 | Multiple `FileInputJSON` instances reading different files simultaneously |
| 26 | JSON with comments | P2 | Some JSON files have comments (non-standard) -- verify error handling |
| 27 | Deeply nested JSON (100+ levels) | P2 | Verify no stack overflow or recursion limit |

---

## 9. Mandatory Edge-Case Analysis

### Edge Case 1: NaN values -- `pd.isna()` vs `is None`

| Aspect | Detail |
|--------|--------|
| **Talend** | JSON `null` becomes Java `null`. Type coercion on null depends on column type (e.g., null integer becomes 0 or stays null based on nullable flag). |
| **V1** | When JSONPath matches a JSON `null`, `jsonpath_ng` returns `None` as the value. The code checks `if val is not None` (line 218) before type coercion. This means JSON `null` skips coercion entirely. However, when `pd.DataFrame(output_data)` is created, `None` values in integer columns become `NaN` (float). The `validate_schema()` call in base class then does `fillna(0).astype('int64')` for integer columns. **Net effect**: JSON null integers become 0. This matches Talend for non-nullable columns. However, `pd.isna(None)` is True but `None is None` is True too -- the code uses `is not None` which is correct here. For empty list `[]` (no match), `pd.isna([])` raises ValueError, but `[] is not None` is True, so coercion IS attempted on empty lists. |
| **Verdict** | PARTIAL -- null values handled correctly, but empty list from no-match is not handled (see BUG-FIJ-010). |

### Edge Case 2: Empty strings in config keys

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty string in FILENAME causes immediate error. Empty string in JSON_LOOP_QUERY causes empty result. |
| **V1** | Empty `filename` passes to `open('', 'r')` which raises `FileNotFoundError` with message about empty path. Caught by outer try/except. Empty `json_loop_query` passes to `parse('')` which raises `JsonPathParserError`. Caught by outer try/except. Empty `mapping` list skips the inner loop entirely, producing rows with no columns. |
| **Verdict** | PARTIAL -- errors are caught but error messages are generic. `validate_config()` would catch these early but is dead code. |

### Edge Case 3: Empty DataFrame (0 rows with columns vs None)

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty JSON array produces 0 rows with schema columns defined. |
| **V1** | Empty `elements` list (line 186) produces empty `output_data = []`. `pd.DataFrame([])` creates 0 rows AND 0 columns. **This loses column information.** Should be `pd.DataFrame(output_data, columns=[m['column'] for m in mapping])`. When `die_on_error=False` and outer exception fires, returns `pd.DataFrame([])` (line 284) -- also loses columns. |
| **Verdict** | **GAP** -- empty result loses schema columns. Downstream components expecting specific columns will fail. See BUG-FIJ-003. |

### Edge Case 4: HYBRID streaming mode via base class

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable (Talend generates Java code, no streaming mode concept). |
| **V1** | `execute()` calls `_auto_select_mode(None)` -> returns `BATCH` (input_data is None for file input). Even if STREAMING were forced, `_execute_streaming()` with `input_data=None` calls `self._process(None)` -- identical to batch. The entire JSON file is loaded into memory regardless of execution mode. **HYBRID/STREAMING mode is effectively dead for this component.** |
| **Verdict** | N/A -- streaming has no effect. Large JSON files will consume proportional memory. |

### Edge Case 5: `_update_global_map()` crash (base_component.py:304 undefined `value`) -- Does it affect result return?

| Aspect | Detail |
|--------|--------|
| **Crash Path** | In `execute()`, after `_process()` completes successfully (line 214), `_update_global_map()` is called on line 218. Line 304 references undefined `value`, raising `NameError`. This exception propagates to `execute()` line 227 (`except Exception as e`). The error handler calls `_update_global_map()` AGAIN on line 231, causing a SECOND `NameError`. This second exception propagates out of `execute()` entirely. |
| **Effect on Result** | The `result` dictionary from `_process()` is computed (line 214) but NEVER returned. Line 220 (`self.status = ComponentStatus.SUCCESS`) is never reached. Line 223 (`result['stats'] = self.stats.copy()`) is never executed. Line 225 (`return result`) is never reached. **The component's processing output is completely lost.** |
| **Effect on Status** | `self.status` is set to `RUNNING` on line 192, then to `ERROR` on line 228. It NEVER reaches `SUCCESS`. |
| **Mitigation** | Only triggered when `self.global_map is not None`. If `global_map` is not set (e.g., standalone testing without engine), the crash does not occur. |
| **Verdict** | **P0 BLOCKER** -- when globalMap is active, ALL component results are lost and status never reaches SUCCESS. Cross-cutting. |

### Edge Case 6: Does component status ever reach SUCCESS?

| Aspect | Detail |
|--------|--------|
| **Answer** | **NO** -- not when `global_map` is set. See Edge Case 5 above. The `NameError` in `_update_global_map()` prevents the success path from completing. When `global_map` is None, `_update_global_map()` short-circuits at line 300 (`if self.global_map:`), and SUCCESS is reached on line 220. |
| **Verdict** | **P0 BLOCKER** -- production deployments with globalMap enabled will never see SUCCESS status. |

### Edge Case 7: Thread safety concerns

| Aspect | Detail |
|--------|--------|
| **V1** | `FileInputJSON` modifies `self.config` during `execute()` via `context_manager.resolve_dict()` (base class line 202). If the same component instance were shared across threads, config resolution would race. However, v1 engine creates new component instances per execution, so this is not a practical concern. `json.load()` and `jsonpath_ng.parse()` are both stateless and thread-safe. `pd.DataFrame()` construction is thread-safe. `_update_stats()` modifies `self.stats` dict without locking -- not safe for concurrent calls, but sequential execution means no practical issue. |
| **Verdict** | SAFE for current v1 engine (single-threaded sequential execution). Would need locking if engine adds parallelism. |

### Edge Case 8: Type demotion risks through iterrows/Series reconstruction

| Aspect | Detail |
|--------|--------|
| **V1** | `FileInputJSON` does NOT use `iterrows()` or Series reconstruction. Data flows through: (1) Python dicts in `output_data` list, (2) `pd.DataFrame(output_data)` constructor, (3) optional `validate_schema()` in downstream. The DataFrame constructor correctly infers types from dict values. However, when `output_data` contains mixed types in the same column (e.g., integer 42 and string "hello"), pandas will infer `object` dtype, losing numeric efficiency. The `json.dumps()` serialization on line 268-269 uses `apply(lambda v: ...)` which does row-by-row Python calls -- slow but no type demotion. |
| **Verdict** | LOW RISK -- no iterrows usage. Minor concern with mixed-type columns producing object dtype. |

### Edge Case 9: `validate_schema` nullable logic (inverted condition)

| Aspect | Detail |
|--------|--------|
| **Base Class** | `validate_schema()` in base_component.py line 351: `if pandas_type == 'int64' and col_def.get('nullable', True):` -- this means when `nullable=True` (the default), it does `fillna(0).astype('int64')`. This is **inverted logic**: nullable columns are the ones that should PRESERVE nulls (use `Int64` nullable), while non-nullable columns should fill nulls with 0. The current code fills nulls with 0 when `nullable=True`, which is backwards. |
| **Effect on FileInputJSON** | If a schema column has `nullable=True` (default) and type `id_Integer`, null values from JSON will be converted to 0 by `validate_schema()`. If `nullable=False`, null values will remain as NaN (float), which then causes `int64` dtype issues. This is the opposite of correct behavior. |
| **Verdict** | **BUG (Cross-cutting)** -- nullable logic is inverted. Nullable columns should preserve NaN; non-nullable should fill with 0. Affects FileInputJSON and all components that call `validate_schema()`. |

### Edge Case 10: Is `validate_config()` actually called or dead code?

| Aspect | Detail |
|--------|--------|
| **V1** | `validate_config()` is defined on lines 286-334 of `file_input_json.py`. It is NOT called by: `__init__()` (lines 88-91), `_process()` (lines 122-284), or `BaseComponent.execute()` (lines 188-234). It is NOT called by any other file in the codebase (confirmed via grep). **It is 100% dead code.** |
| **Content** | Validates: required fields (`filename`, `json_loop_query`, `mapping`), mapping structure (list, non-empty), schema type (list), encoding type (string), URL config consistency (`useurl=True` requires `urlpath`). All valuable validations that would catch misconfigurations early. |
| **Verdict** | DEAD CODE. 48 lines of useful validation that never executes. Should be wired into `execute()` or `_process()`. |

### Edge Case 11: File with JSON `null` values in all fields

| Aspect | Detail |
|--------|--------|
| **Talend** | Produces rows with null values. Type coercion applied per column type. |
| **V1** | `jsonpath_ng` returns `None` for JSON `null`. `is not None` check skips coercion. Row dict has `{col: None, ...}`. DataFrame has `NaN` in all columns. `validate_schema()` converts per type. |
| **Verdict** | CORRECT -- JSON nulls handled via None. |

### Edge Case 12: JSONPath matching object (not scalar)

| Aspect | Detail |
|--------|--------|
| **Talend** | Nested objects serialized as JSON strings in output. |
| **V1** | JSONPath returns the dict/list object. Post-processing (lines 266-269) calls `json.dumps(v)` for list/dict values. |
| **Verdict** | CORRECT -- complex values serialized as JSON strings. |

### Edge Case 13: Multiple JSON files concatenated (JSONL/NDJSON format)

| Aspect | Detail |
|--------|--------|
| **Talend** | tFileInputJSON expects valid JSON (single root). JSONL requires tFileInputDelimited + tExtractJSONFields. |
| **V1** | `json.load()` will fail on JSONL (multiple root objects). Error caught by outer try/except. |
| **Verdict** | CORRECT -- matches Talend behavior (single JSON document expected). |

### Edge Case 14: Very deeply nested JSON (recursion depth)

| Aspect | Detail |
|--------|--------|
| **Talend** | Java has no recursion limit for JSON parsing. |
| **V1** | Python's default recursion limit is 1000. `json.load()` uses C extension which has its own nesting limit. `jsonpath_ng.parse()` uses recursive descent parser. Extremely deep nesting (1000+ levels) may hit Python's recursion limit. |
| **Verdict** | EDGE CASE -- extremely deep nesting may crash. Very rare in practice. |

### Edge Case 15: JSON file with Unicode BOM

| Aspect | Detail |
|--------|--------|
| **Talend** | Java handles BOM transparently. |
| **V1** | `open(filename, 'r', encoding='UTF-8')` does NOT strip BOM. The BOM character (`\ufeff`) becomes part of the JSON string, causing `json.load()` to fail with `JSONDecodeError`. Should use `encoding='utf-8-sig'` for BOM handling. |
| **Verdict** | **GAP** -- UTF-8 BOM files will fail. |

---

## 10. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIJ-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Causes `NameError` at runtime when `global_map` is set. Component results are lost and status never reaches SUCCESS. Affects ALL components. |
| BUG-FIJ-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. Affects ALL components. |
| CONV-FIJ-001 | Converter | **Component name mismatch**: Converter writes `type: 'FileInputJSONComponent'` to JSON config, but engine registers `FileInputJSON` and `tFileInputJSON`. Component instantiation will fail at runtime for ALL converted Talend jobs using tFileInputJSON. |
| TEST-FIJ-001 | Testing | Zero v1 unit tests for FileInputJSON. All 334 lines of engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIJ-002 | Converter | `USE_URL` and `URL` not extracted. Engine supports URL reading but converter never populates config keys. URL-based Talend jobs will fail. |
| CONV-FIJ-003 | Converter | `READ_BY` not extracted. XPath mode and "JSONPath without loop" mode unavailable. |
| CONV-FIJ-004 | Converter | No Java expression marking in `parse_tfileinputjson()`. Expressions in FILENAME, JSON_LOOP_QUERY, mapping queries passed as literal strings. |
| ENG-FIJ-001 | Engine | No XPath read mode. Only JSONPath supported. Jobs using XPath will fail. |
| ENG-FIJ-002 | Engine | No "JSONPath without loop" mode. Jobs using direct query mode will fail. |
| ENG-FIJ-003 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. Error details not available downstream. |
| ENG-FIJ-004 | Engine | URL reading is bare-bones: no timeout, headers, auth, proxy. Not production-grade for REST API integration. |
| ENG-FIJ-009 | Engine | `die_on_error=True` does not stop per-row errors. Only file-level errors respect the flag. Behavioral divergence from Talend. *(Adversarial review)* |
| ENG-FIJ-010 | Engine | Date validation non-functional for converted jobs due to schema key mismatch (`date_pattern` vs `pattern`). *(Adversarial review)* |
| BUG-FIJ-003 | Bug | Empty `output_data` produces DataFrame with no columns. Loses schema column information. |
| BUG-FIJ-004 | Bug | Dead code in multi-match branch. Both `if` and `else` produce identical code. Wildcard query with single match incorrectly flattens to scalar. |
| BUG-FIJ-005 | Bug | `validate_config()` is dead code. 48 lines of validation never executed. |
| BUG-FIJ-007 | Bug | `die_on_error=True` does NOT stop per-row errors. Inner try/except (lines 200-247) never checks `die_on_error`. Always routes to reject regardless of setting. Behavioral divergence from Talend. *(Adversarial review)* |
| BUG-FIJ-008 | Bug | Schema date pattern key mismatch: converter stores as `'date_pattern'` but engine reads `'pattern'`. Date validation completely non-functional for converted jobs. *(Adversarial review)* |
| NAME-FIJ-001 | Naming | Converter name `FileInputJSONComponent` vs engine name `FileInputJSON`. Same root cause as CONV-FIJ-001. |
| TEST-FIJ-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIJ-005 | Converter | `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR` not extracted. Engine has support but config never populated. |
| CONV-FIJ-006 | Converter | `USE_LOOP_AS_ROOT` not extracted. Engine has support but config never populated. |
| CONV-FIJ-007 | Converter | `VALIDATE_DATE` not extracted. Engine has `check_date` support but config never populated. |
| ENG-FIJ-005 | Engine | Null/missing JSONPath match returns empty list `[]` instead of `None`. Causes confusing type coercion errors. |
| ENG-FIJ-006 | Engine | Dead multi-match branch. `[*]`/`.*` check has identical code in both branches. |
| ENG-FIJ-007 | Engine | `use_loop_as_root` only unwraps single-element lists. Does not fully implement Talend semantics. |
| BUG-FIJ-006 | Bug | Debug log on line 242 references last loop variable only. Misleading for multi-column debugging. |
| BUG-FIJ-009 | Bug | `json.dumps()` on non-serializable values (datetime, Decimal) crashes outside per-row try/except, losing ALL processed data. Returns empty DataFrames. *(Adversarial review)* |
| BUG-FIJ-010 | Bug | Empty match produces empty list `[]` instead of `None`. Passes `is not None` check, causing type coercion on empty list. |
| BUG-FIJ-011 | Bug | Unused imports: `os`, `re`, `codecs` never used. |
| NAME-FIJ-002 | Naming | `useurl` (no underscore) inconsistent with `use_loop_as_root` naming convention. |
| NAME-FIJ-003 | Naming | `check_date` vs Talend `VALIDATE_DATE`. Non-standard key mapping. |
| STD-FIJ-002 | Standards | `validate_config()` exists but never called. Dead validation code. |
| STD-FIJ-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| SEC-FIJ-001 | Security | No URL validation for `urlopen()`. Accepts `file:///` scheme. |
| PERF-FIJ-001 | Performance | Row-by-row JSONPath `parse()` compilation. 100,000 compilations for 10K rows x 10 columns. Should pre-compile. |
| PERF-FIJ-002 | Performance | Post-DataFrame serialization pass iterates all columns. Could be done during row construction. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIJ-008 | Converter | `API_VERSION` not extracted. Low impact (config key exists but is unused). |
| ENG-FIJ-008 | Engine | No Nashorn / JDK version handling. Not relevant for Python engine. |
| NAME-FIJ-004 | Naming | `json_path_version` vs Talend `API_VERSION`. Non-standard but unused. |
| STD-FIJ-004 | Standards | Unused imports `os`, `re`, `codecs`. |
| SEC-FIJ-002 | Security | No path traversal protection on `filename`. |
| DBG-FIJ-001 | Debug | Duplicate logging on lines 254-255 via both `logger` and `self.logger`. |
| PERF-FIJ-003 | Performance | `jsonpath_ng.ext` imported inside `_process()`. Should be module-level. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 2 bugs (cross-cutting), 1 converter, 1 testing |
| P1 | 16 | 3 converter, 6 engine, 5 bugs, 1 naming, 1 testing |
| P2 | 17 | 3 converter, 3 engine, 4 bugs, 2 naming, 2 standards, 1 security, 2 performance |
| P3 | 7 | 1 converter, 1 engine, 1 naming, 1 standards, 1 security, 1 debug, 1 performance |
| **Total** | **44** | |

> **Note**: BUG-FIJ-007, BUG-FIJ-008, and BUG-FIJ-009 were added from adversarial review (2026-03-21). Former BUG-FIJ-007 (empty match) renumbered to BUG-FIJ-010; former BUG-FIJ-008 (unused imports) renumbered to BUG-FIJ-011.

---

## 11. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FIJ-001): Change `value` to `stat_value` on `base_component.py` line 304, or better yet, remove the stale `{stat_name}: {value}` reference. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only). **Without this fix, no component can return results when globalMap is active.**

2. **Fix `GlobalMap.get()` bug** (BUG-FIJ-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

3. **Fix component name mismatch** (CONV-FIJ-001): Change `component_parser.py` line 101 from `'tFileInputJSON': 'FileInputJSONComponent'` to `'tFileInputJSON': 'FileInputJSON'` to match the engine registry. **Impact**: Enables tFileInputJSON to work in converted Talend jobs. **Risk**: Very low (single string change).

4. **Create unit test suite** (TEST-FIJ-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. Cover basic JSON read, JSONPath extraction, schema coercion, error handling, and statistics.

### Short-Term (Hardening)

5. **Extract `USE_URL` and `URL` from converter** (CONV-FIJ-002): Add to `parse_tfileinputjson()`:
   ```python
   use_url_elem = node.find('.//elementParameter[@name="USE_URL"]')
   if use_url_elem is not None:
       component['config']['useurl'] = use_url_elem.get('value', 'false').lower() == 'true'
   url_elem = node.find('.//elementParameter[@name="URL"]')
   if url_elem is not None:
       component['config']['urlpath'] = url_elem.get('value', '')
   ```

6. **Add Java expression marking** (CONV-FIJ-004): Call `self.expr_converter.mark_java_expression()` on FILENAME, JSON_LOOP_QUERY, and mapping values in `parse_tfileinputjson()`.

7. **Fix empty list from no-match** (BUG-FIJ-010): After line 213, add:
   ```python
   if isinstance(val, list) and len(val) == 0:
       val = None
   ```

8. **Fix multi-match branch** (BUG-FIJ-004): The `if` branch for `[*]`/`.*` should NOT flatten single-element lists:
   ```python
   if '[*]' in jsonpath or '.*' in jsonpath:
       val = [v.value for v in value_matches]
       # Keep as list -- do NOT flatten for wildcard queries
   else:
       val = [v.value for v in value_matches]
       if len(val) == 1:
           val = val[0]
   ```

9. **Fix empty DataFrame column loss** (BUG-FIJ-003): Replace `pd.DataFrame(output_data)` with `pd.DataFrame(output_data, columns=[m['column'] for m in mapping])` on line 262. Same for the error fallback on line 284.

10. **Wire up `validate_config()`** (BUG-FIJ-005): Add a call at the beginning of `_process()`:
    ```python
    errors = self.validate_config()
    if errors:
        error_msg = '; '.join(errors)
        if self.config.get('die_on_error', True):
            raise ValueError(f"Configuration validation failed: {error_msg}")
        return {'main': pd.DataFrame(columns=[m['column'] for m in self.config.get('mapping', [])]),
                'reject': pd.DataFrame()}
    ```

11. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FIJ-003): In the error handler (line 279), add:
    ```python
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    ```

12. **Extract remaining converter parameters** (CONV-FIJ-005/006/007): Add extraction for `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`, `USE_LOOP_AS_ROOT`, `VALIDATE_DATE` to `parse_tfileinputjson()`. These all map to existing engine config keys.

13. **Fix `die_on_error` per-row bypass** (BUG-FIJ-007, adversarial review): The inner try/except block (lines 200-247) must check `die_on_error` before routing to reject. When `die_on_error=True`, re-raise the exception immediately instead of appending to the reject list:
    ```python
    except Exception as e:
        if die_on_error:
            raise
        # ... existing reject-row logic ...
    ```
    **Impact**: Restores Talend-equivalent behavior where `die_on_error=True` aborts on the first row-level error.

14. **Fix schema date pattern key mismatch** (BUG-FIJ-008, adversarial review): Align the converter and engine on a single key. Either change `component_parser.py:500` from `'date_pattern'` to `'pattern'`, or change `file_input_json.py:234` from `col_def.get('pattern')` to `col_def.get('date_pattern')`. The former is recommended to match the engine's expected key. **Impact**: Enables date validation for all converted jobs.

15. **Guard `json.dumps()` against non-serializable values** (BUG-FIJ-009, adversarial review): Wrap the serialization pass (lines 266-269) in a try/except or use a custom default handler:
    ```python
    json.dumps(v, default=str)
    ```
    Alternatively, move serialization inside the per-row try/except so failures route to reject instead of discarding all data. **Impact**: Prevents total data loss from a single non-serializable value.

### Long-Term (Optimization)

16. **Pre-compile JSONPath expressions** (PERF-FIJ-001): Before the element loop, compile all mapping JSONPath expressions once:
    ```python
    compiled_mappings = []
    for m in mapping:
        jp = m['jsonpath']
        if isinstance(jp, str) and jp.startswith('"') and jp.endswith('"'):
            jp = jp[1:-1]
        compiled_mappings.append({'column': m['column'], 'expr': parse(jp)})
    ```
    Then in the inner loop, use `compiled_mappings[j]['expr'].find(element)` instead of `parse(jsonpath).find(element)`.

17. **Add XPath read mode** (ENG-FIJ-001): Implement XPath-based extraction using a library like `lxml` for JSON-to-XML conversion then XPath query, or use a JSONPath-to-XPath adapter.

18. **Improve URL reading** (ENG-FIJ-004): Replace bare `urlopen()` with `requests` library or `urllib.request.Request` with configurable timeout, headers, and auth.

19. **Add streaming JSON parsing** (PERF-FIJ-001): For large JSON files, use `ijson` library for incremental parsing instead of loading entire file into memory.

20. **Move import to module level** (PERF-FIJ-003): Move `from jsonpath_ng.ext import parse` from line 182 to the module-level imports.

21. **Remove unused imports** (BUG-FIJ-011): Remove `os`, `re`, `codecs` from imports.

22. **Fix nullable logic in base class** (Edge Case 9): In `validate_schema()`, change the condition to `if pandas_type == 'int64' and not col_def.get('nullable', True):` -- fill with 0 only when NOT nullable.

23. **Add BOM handling** (Edge Case 15): When `encoding='UTF-8'`, use `'utf-8-sig'` to transparently handle BOM.

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 1509-1520
def parse_tfileinputjson(self, node, component: Dict) -> Dict:
    """Parse tFileInputJSON specific configuration"""
    component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    component['config']['json_loop_query'] = node.find('.//elementParameter[@name="JSON_LOOP_QUERY"]').get('value', '')
    component['config']['mapping'] = []
    for mapping_entry in node.findall('.//elementParameter[@name="MAPPING_JSONPATH"]/elementValue'):
        column = mapping_entry.get('elementRef', '')
        jsonpath = mapping_entry.get('value', '')
        component['config']['mapping'].append({'column': column, 'jsonpath': jsonpath})
    component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
    component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    return component
```

**Notes on this code**:
- Line 1511: Direct value extraction with no null check on `node.find()`. If `FILENAME` element is missing from XML, `node.find()` returns `None`, and `.get('value', '')` raises `AttributeError: 'NoneType' object has no attribute 'get'`. Same risk on lines 1512, 1518, 1519.
- Lines 1514-1517: Mapping extraction uses `elementRef` for column name and `value` for JSONPath. This produces the Talend alternating-pair format that the engine's `_normalize_mapping()` handles.
- Line 1518: Boolean conversion from string. Default `false` matches Talend.
- Line 1519: Default `'UTF-8'` is appropriate for JSON (RFC 8259).
- **No expression handling**: No `mark_java_expression()`, no context variable wrapping. Raw XML values passed through.
- **No error handling**: No try/except around XML parsing. Missing elements cause `AttributeError`.

---

## Appendix B: Engine Class Structure

```
FileInputJSON (BaseComponent)
    Imports: json, logging, os*, re*, codecs*, typing, urllib, datetime, pandas, jsonpath_ng.ext*
    (* = unused)

    Methods:
        __init__(*args, **kwargs)                   # Initializes logger
        _normalize_mapping(mapping) -> List[Dict]   # Converts SCHEMA_COLUMN/QUERY pairs
        _process(input_data) -> Dict[str, Any]      # Main entry point (212 lines)
        validate_config() -> List[str]              # DEAD CODE -- never called (48 lines)
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filename` | Mapped | -- |
| `JSON_LOOP_QUERY` | `json_loop_query` | Mapped | -- |
| `MAPPING_JSONPATH` | `mapping` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped | -- |
| `READ_BY` | `read_by` | **Not Mapped** (engine key exists) | P1 |
| `API_VERSION` | `json_path_version` | **Not Mapped** (engine key exists but unused) | P3 |
| `USE_URL` | `useurl` | **Not Mapped** (engine key exists) | P1 |
| `URL` | `urlpath` | **Not Mapped** (engine key exists) | P1 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** (engine key exists) | P2 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** (engine key exists) | P2 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** (engine key exists) | P2 |
| `USE_LOOP_AS_ROOT` | `use_loop_as_root` | **Not Mapped** (engine key exists) | P2 |
| `VALIDATE_DATE` | `check_date` | **Not Mapped** (engine key exists) | P2 |
| `JDK_VERSION` | -- | Not needed | -- (JDK config) |
| `INCLUDE_NASHORN` | -- | Not needed | -- (JDK config) |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| `SCHEMA` | `schema` | Mapped (generic) | -- |

---

## Appendix D: Type Coercion Flow

### Engine Type Coercion (in `_process()` lines 214-240)

| Schema Type | Coercion Method | Error Handling |
|-------------|----------------|----------------|
| `id_Integer` / `int` / `integer` | `int(float(val))` with optional separator stripping | Raises `ValueError` -> reject row |
| `id_Float` / `float` / `double` | `float(val)` with optional separator stripping | Raises `ValueError` -> reject row |
| `id_Date` / `date` / `datetime` | `datetime.strptime(val, pattern)` when `check_date=True` | Raises `ValueError` -> reject row |
| `id_String` / `str` | No coercion | No error possible |

### Base Class `validate_schema()` (post-processing)

| Type Input | Pandas Dtype | Conversion Method |
|------------|-------------|-------------------|
| `id_String` / `str` | `object` | No conversion |
| `id_Integer` / `int` | `int64` | `pd.to_numeric(errors='coerce')` then `fillna(0).astype('int64')` when `nullable=True` (INVERTED) |
| `id_Float` / `float` | `float64` | `pd.to_numeric(errors='coerce')` |
| `id_Boolean` / `bool` | `bool` | `.astype('bool')` |
| `id_Date` / `date` | `datetime64[ns]` | `pd.to_datetime()` -- no format specification |

**Key observation**: Type coercion happens TWICE -- once in `_process()` (per-row, with reject handling) and once in `validate_schema()` (per-DataFrame, via base class). The `_process()` coercion is more specific (uses schema patterns, separator handling) while `validate_schema()` is generic. This double coercion is wasteful but not harmful -- the second pass on already-coerced data is a no-op in most cases.

**Inverted nullable logic**: `validate_schema()` fills nulls with 0 when `nullable=True`. This is backwards. See Edge Case 9 in Section 9.

---

## Appendix E: Detailed Code Analysis

### `_normalize_mapping()` (Lines 93-120)

This method converts Talend's alternating SCHEMA_COLUMN/QUERY pair format to standard column/jsonpath pairs:
1. Iterates mapping entries
2. When `entry['column'] == 'SCHEMA_COLUMN'`, stores `entry['jsonpath']` as the column name
3. When `entry['column'] == 'QUERY'`, takes `entry['jsonpath']` as the JSONPath expression
4. Strips surrounding quotes from JSONPath expressions
5. Creates `{'column': col_name, 'jsonpath': jsonpath}` pairs

**Edge case**: If the mapping has an odd number of entries (e.g., SCHEMA_COLUMN without matching QUERY), the last column name is silently dropped via `col = None` reset.

### `_process()` (Lines 122-284)

The main processing method:
1. Extract config values with defaults
2. Normalize mapping if Talend format detected
3. Read JSON from file or URL based on `useurl` flag
4. Parse JSONPath loop expression and find all matching elements
5. Optionally unwrap single-element list for `use_loop_as_root`
6. Iterate elements, extract fields via per-column JSONPath
7. Apply schema type coercion (integer, float, date) with error handling
8. Build reject rows for failed extractions/conversions
9. Update statistics
10. Create output DataFrames, serialize complex values
11. Return `{'main': main_df, 'reject': reject_df}` or `{'main': main_df}`

### `validate_config()` (Lines 286-334)

Validates:
- Required fields: `filename`, `json_loop_query`, `mapping`
- Mapping structure: must be non-empty list
- Schema type: must be list if present
- Encoding type: must be string if present
- URL config consistency: `useurl=True` requires `urlpath`

**DEAD CODE** -- never called by any code path.

---

## Appendix F: Edge Case Analysis Summary

| # | Edge Case | Talend Behavior | V1 Behavior | Verdict |
|---|-----------|----------------|-------------|---------|
| 1 | NaN values | null -> type default | None skips coercion, DataFrame has NaN, validate_schema fills | PARTIAL |
| 2 | Empty config keys | Immediate error | Late error via exception | PARTIAL |
| 3 | Empty DataFrame | 0 rows with columns | 0 rows, 0 columns | **GAP** |
| 4 | HYBRID streaming | N/A | Always BATCH for file input | N/A |
| 5 | _update_global_map crash | N/A | Results lost, never SUCCESS | **P0 BLOCKER** |
| 6 | SUCCESS status | Completes | Never with globalMap | **P0 BLOCKER** |
| 7 | Thread safety | N/A | Safe for sequential | SAFE |
| 8 | Type demotion | N/A | No iterrows, low risk | LOW RISK |
| 9 | validate_schema nullable | nullable=true preserves null | nullable=true fills with 0 (INVERTED) | **BUG** |
| 10 | validate_config() | N/A | Dead code | DEAD CODE |
| 11 | All-null JSON values | Rows with nulls | Rows with None -> NaN | CORRECT |
| 12 | Nested object match | JSON-serialized string | JSON-serialized string | CORRECT |
| 13 | JSONL/NDJSON format | Fails (single root) | Fails (json.load) | CORRECT |
| 14 | Deep nesting (1000+) | Java handles | May hit recursion limit | EDGE CASE |
| 15 | UTF-8 BOM | Transparent | Fails (BOM in JSON) | **GAP** |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileInputJSON`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FIJ-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when globalMap is set. Results are lost and status never reaches SUCCESS. |
| BUG-FIJ-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FIJ-005 | **P1** | `base_component.py` | `validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |
| Edge Case 9 | **P2** | `base_component.py:351` | `validate_schema()` nullable logic is inverted. Fills nulls with 0 when `nullable=True` (should be when `nullable=False`). Affects all components using `validate_schema()`. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: CONV-FIJ-001 -- Component name mismatch

**File**: `src/converters/complex_converter/component_parser.py`
**Line**: 101

**Current code (broken)**:
```python
'tFileInputJSON': 'FileInputJSONComponent',
```

**Fix**:
```python
'tFileInputJSON': 'FileInputJSON',
```

**Explanation**: The engine registry (`engine.py` lines 95-96) maps `'FileInputJSON'` and `'tFileInputJSON'` to the `FileInputJSON` class. The converter must output one of these registered names. `FileInputJSONComponent` is not registered and will cause `KeyError` during component instantiation.

**Impact**: Enables all converted tFileInputJSON jobs to run. **Risk**: Very low (single string change).

---

### Fix Guide: BUG-FIJ-001 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration. Removing both stale references fixes the `NameError` and produces a clean summary log.

**Impact**: Fixes ALL components (cross-cutting). Restores SUCCESS status and result returns. **Risk**: Very low.

---

### Fix Guide: BUG-FIJ-002 -- `GlobalMap.get()` undefined default

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

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low.

---

### Fix Guide: BUG-FIJ-010 -- Empty list from no-match

**File**: `src/v1/engine/components/file/file_input_json.py`
**After line**: 213

**Add**:
```python
if isinstance(val, list) and len(val) == 0:
    val = None
```

**Explanation**: When JSONPath finds no match, `value_matches` is empty, producing `val = []`. This empty list passes the `if val is not None` check and enters type coercion, where `int([])` raises confusing `TypeError`. Converting empty list to `None` makes no-match behavior consistent with JSON `null`.

---

### Fix Guide: PERF-FIJ-001 -- Pre-compile JSONPath expressions

**File**: `src/v1/engine/components/file/file_input_json.py`
**Before the element loop** (before line 197)

**Add**:
```python
# Pre-compile JSONPath expressions for all mapping entries
compiled_mappings = []
for mapping_entry in mapping:
    column_name = mapping_entry.get('column')
    jsonpath = mapping_entry.get('jsonpath')
    if isinstance(jsonpath, str) and jsonpath.startswith('"') and jsonpath.endswith('"'):
        jsonpath = jsonpath[1:-1]
    compiled_expr = parse(jsonpath)
    compiled_mappings.append({
        'column': column_name,
        'jsonpath': jsonpath,
        'expr': compiled_expr
    })
```

**Then replace** the inner loop to use `compiled_mappings` with pre-compiled `expr.find(element)` instead of `parse(jsonpath).find(element)`.

**Impact**: Eliminates N*M JSONPath compilations (N elements x M columns). For 10K elements x 10 columns, saves ~100K parse operations. **Risk**: Low.

---

## Appendix I: Comparison with Other File Input Components

| Feature | tFileInputJSON (V1) | tFileInputDelimited (V1) | tFileInputXML (V1) | tFileInputExcel (V1) |
|---------|----------------------|--------------------------|---------------------|----------------------|
| Basic reading | Yes | Yes | Yes | Yes |
| Schema enforcement | Yes (in _process) | Yes (in validate_schema) | Yes | Yes |
| Encoding | Yes | Yes | Yes | N/A |
| Die on error | Yes | Yes | Yes | Yes |
| REJECT flow | **Yes** | **No** | **No** | **No** |
| Advanced separator | Yes (engine) / No (converter) | **No** | **No** | **No** |
| Date validation | Yes (engine) / No (converter) | **No** | **No** | **No** |
| URL reading | Yes (engine) / No (converter) | **No** | **No** | **No** |
| Streaming mode | **No** | Yes | **No** | **No** |
| GlobalMap ERROR_MESSAGE | **No** | **No** | **No** | **No** |
| V1 Unit tests | **No** | **No** | **No** | **No** |

**Observation**: FileInputJSON is notable for having a REJECT flow implementation -- the only file input component in v1 that does. It also has engine-side support for advanced separators, date validation, and URL reading that other components lack. However, the converter does not populate these config keys, making the engine capabilities inaccessible through the standard conversion pipeline.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| **ANY converted tFileInputJSON job** | **Critical** | ALL jobs with tFileInputJSON | Fix CONV-FIJ-001 (name mismatch) -- without this fix, NO converted job will work |
| **ANY job with globalMap active** | **Critical** | ALL jobs (cross-cutting) | Fix BUG-FIJ-001 (_update_global_map crash) -- without this fix, ALL component results are lost |
| Jobs using URL reading | **High** | REST API integration jobs | Fix CONV-FIJ-002 (extract USE_URL/URL from converter) |
| Jobs using Java expressions in params | **High** | Jobs with dynamic paths | Fix CONV-FIJ-004 (add expression marking) |
| Jobs using XPath read mode | **High** | XPath-based JSON extraction | Implement XPath support or document limitation |
| Jobs referencing ERROR_MESSAGE | **Medium** | Error handling pipelines | Implement ENG-FIJ-003 |
| Jobs using advanced separators | **Medium** | European number format | Fix CONV-FIJ-005 (extract separator params) |
| Jobs using USE_LOOP_AS_ROOT | **Medium** | Complex JSON structures | Fix CONV-FIJ-006 |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using tStatCatcher | Low | Monitoring feature, not data flow |
| Jobs using JDK version / Nashorn | Low | Not applicable to Python engine |
| Jobs with API_VERSION set | Low | Config key exists but is unused anyway |

### Recommended Migration Strategy

1. **Phase 0**: Fix ALL P0 bugs -- name mismatch (CONV-FIJ-001), globalMap crash (BUG-FIJ-001, BUG-FIJ-002). Without these fixes, ZERO converted tFileInputJSON jobs will work.
2. **Phase 1**: Extract missing converter parameters (USE_URL, URL, ADVANCED_SEPARATOR, USE_LOOP_AS_ROOT, VALIDATE_DATE). Add expression marking.
3. **Phase 2**: Audit each target job's Talend configuration. Identify which features are used (URL reading, XPath, advanced separators).
4. **Phase 3**: Implement missing engine features as needed (XPath mode, URL auth/headers).
5. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row.
6. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix K: Complete Enhanced Parser Implementation

The following is the recommended replacement for the current minimal `parse_tfileinputjson()`. This method should replace the existing method in `component_parser.py`.

```python
def parse_tfileinputjson(self, node, component: Dict) -> Dict:
    """
    Parse tFileInputJSON specific configuration from Talend XML node.

    Extracts ALL Talend parameters for comprehensive JSON file reading support.

    Talend Parameters:
        FILENAME (str): File path. Mandatory unless USE_URL=true.
        JSON_LOOP_QUERY (str): JSONPath/XPath loop expression. Mandatory.
        MAPPING_JSONPATH (table): Column-to-query mapping. Mandatory.
        READ_BY (str): Read method -- JsonPath, Xpath, or JsonPath without loop.
        API_VERSION (str): JSONPath API version.
        USE_URL (bool): Read from URL instead of file.
        URL (str): URL for web-based reading.
        DIE_ON_ERROR (bool): Stop job on error.
        ENCODING (str): File encoding. Default UTF-8.
        ADVANCED_SEPARATOR (bool): Enable locale-aware number parsing.
        THOUSANDS_SEPARATOR (str): Thousands separator.
        DECIMAL_SEPARATOR (str): Decimal separator.
        USE_LOOP_AS_ROOT (bool): Use loop node as root for sub-queries.
        VALIDATE_DATE (bool): Strict date validation.
    """
    def get_param(name, default=None):
        elem = node.find(f'.//elementParameter[@name="{name}"]')
        if elem is not None:
            return elem.get('value', default)
        return default

    def get_bool_param(name, default=False):
        value = get_param(name)
        if value is not None:
            return value.lower() == 'true'
        return default

    # Basic settings
    component['config']['filename'] = get_param('FILENAME', '')
    component['config']['json_loop_query'] = get_param('JSON_LOOP_QUERY', '')
    component['config']['read_by'] = get_param('READ_BY', 'JSONPATH')
    component['config']['json_path_version'] = get_param('API_VERSION', None)
    component['config']['die_on_error'] = get_bool_param('DIE_ON_ERROR', False)
    component['config']['encoding'] = get_param('ENCODING', 'UTF-8')

    # URL settings
    component['config']['useurl'] = get_bool_param('USE_URL', False)
    component['config']['urlpath'] = get_param('URL', '')

    # Advanced settings
    component['config']['advanced_separator'] = get_bool_param('ADVANCED_SEPARATOR', False)
    component['config']['thousands_separator'] = get_param('THOUSANDS_SEPARATOR', ',')
    component['config']['decimal_separator'] = get_param('DECIMAL_SEPARATOR', '.')
    component['config']['use_loop_as_root'] = get_bool_param('USE_LOOP_AS_ROOT', False)
    component['config']['check_date'] = get_bool_param('VALIDATE_DATE', False)

    # Mapping table
    component['config']['mapping'] = []
    for mapping_entry in node.findall('.//elementParameter[@name="MAPPING_JSONPATH"]/elementValue'):
        column = mapping_entry.get('elementRef', '')
        jsonpath = mapping_entry.get('value', '')
        # Mark Java expressions in mapping values
        if jsonpath and not jsonpath.startswith('"'):
            jsonpath = self.expr_converter.mark_java_expression(jsonpath)
        component['config']['mapping'].append({'column': column, 'jsonpath': jsonpath})

    # Mark Java expressions in filename and loop query
    filename = component['config'].get('filename', '')
    if filename:
        component['config']['filename'] = self.expr_converter.mark_java_expression(filename)

    loop_query = component['config'].get('json_loop_query', '')
    if loop_query:
        component['config']['json_loop_query'] = self.expr_converter.mark_java_expression(loop_query)

    return component
```

---

## Appendix L: FileInputJSON vs tFileInputDelimited Audit Comparison

This section highlights how FileInputJSON differs architecturally from FileInputDelimited:

| Aspect | FileInputJSON | FileInputDelimited |
|--------|---------------|---------------------|
| Converter approach | Dedicated parser (correct) | Deprecated `_map_component_parameters()` (wrong) |
| REJECT flow | **Implemented** | Not implemented |
| validate_config() | Exists (dead code) | Exists (dead code) |
| Schema coercion | In `_process()` per-row | In `validate_schema()` per-DataFrame |
| Streaming mode | Not available | Available via `_read_streaming()` |
| Advanced separator | Engine supports | Engine does NOT support |
| Date validation | Engine supports | Engine does NOT support |
| URL reading | Engine supports | Engine does NOT support |
| Lines of code | 334 | 575 |
| Test coverage | 0% | 0% |

**Key insight**: FileInputJSON has a more Talend-faithful architecture (REJECT flow, per-row type coercion, advanced separators) but is crippled by the converter name mismatch (CONV-FIJ-001) that prevents any converted job from running. FileInputDelimited lacks these features but does not have a blocking converter bug.

---

## Appendix M: Detailed Execution Flow Trace

### Normal Execution (No GlobalMap)

```
1. engine.py creates FileInputJSON(component_id, config, global_map=None, context_manager)
2. BaseComponent.__init__() initializes stats, status=PENDING
3. FileInputJSON.__init__() sets self.logger
4. engine calls component.execute(input_data=None)

5. execute() [base_component.py]:
   a. self.status = RUNNING
   b. start_time = time.time()
   c. _resolve_java_expressions()  -- if java_bridge set
   d. context_manager.resolve_dict(self.config)  -- resolve ${context.var}
   e. _auto_select_mode(None) -> BATCH  (input_data is None)
   f. _execute_batch(None) -> self._process(None)

6. _process(None) [file_input_json.py]:
   a. Extract config: filename, json_loop_query, mapping, die_on_error, ...
   b. Check if mapping needs normalization (SCHEMA_COLUMN/QUERY pairs)
   c. If useurl: urlopen(urlpath) -> json.loads(response.read().decode(encoding))
      Else: open(filename, 'r', encoding=encoding) -> json.load(file)
   d. from jsonpath_ng.ext import parse
   e. parse(json_loop_query.strip('"')) -> jsonpath_expr
   f. jsonpath_expr.find(json_data) -> elements list
   g. If use_loop_as_root and len(elements)==1 and isinstance(elements[0], list):
         elements = elements[0]
   h. For each element:
      - For each mapping_entry:
        * parse(jsonpath).find(element) -> value_matches
        * If [*] or .* in jsonpath: val = [v.value for v in value_matches]
        * Else: val = list, flatten if single
        * If schema: type coerce (int, float, date) with error handling
        * row[column_name] = val
      - If exception: create reject_row with errorCode, errorMessage
      - Append to output_data or reject_data
   i. _update_stats(total, ok, rejected)
   j. main_df = pd.DataFrame(output_data)
   k. Serialize lists/dicts to JSON strings in main_df
   l. reject_df = pd.DataFrame(reject_data) if any
   m. Return {'main': main_df, 'reject': reject_df} or {'main': main_df}

7. Back in execute() [base_component.py]:
   a. stats['EXECUTION_TIME'] = elapsed
   b. _update_global_map()  -- SKIPPED (global_map is None)
   c. self.status = SUCCESS
   d. result['stats'] = self.stats.copy()
   e. return result
```

### Crash Execution (With GlobalMap)

```
Steps 1-6: Same as above

7. Back in execute() [base_component.py]:
   a. stats['EXECUTION_TIME'] = elapsed
   b. _update_global_map():
      - self.global_map is not None -> enters loop
      - for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
            # put_component_stat works fine (calls self.put(key, value))
      - Line 304: logger.info(f"...{stat_name}: {value}")
        ^^^^^^^^ NameError: name 'value' is not defined
      - Exception propagates out of _update_global_map()

   c. Exception caught by execute() line 227:
      - self.status = ERROR
      - self.error_message = "name 'value' is not defined"
      - _update_global_map()  <-- CALLED AGAIN (line 231)
        * Same crash: NameError on line 304
        * Exception propagates out AGAIN

   d. logger.error(f"Component {self.id} execution failed: ...")
      ^^^^^^^^ THIS LINE IS NEVER REACHED because _update_global_map()
               crashed AGAIN before line 233

   e. raise  <-- re-raises the NameError from step 7c's _update_global_map()

8. Result: NameError propagates to engine. Component result is LOST.
   Status: ERROR (but for wrong reason -- NameError, not a processing failure).
   Stats: Partially stored in globalMap (put_component_stat works before the crash),
          but the log statement crashes afterward.
```

### Error Recovery Analysis

The double-crash in the error handler is particularly insidious:
1. First `_update_global_map()` crash prevents SUCCESS status and result return
2. Error handler catches the NameError and tries to update globalMap again
3. Second `_update_global_map()` crash prevents the error handler from completing
4. The `logger.error()` call on line 233 is unreachable
5. The `raise` on line 234 re-raises the NameError, not the original processing result

**Note**: The stats ARE partially stored in globalMap. `put_component_stat()` (line 302) calls `self.put(key, value)` which works. The crash happens on the LOG statement AFTER the loop. So `{id}_NB_LINE`, `{id}_NB_LINE_OK`, etc. are stored but the component still fails.

---

## Appendix N: Mapping Normalization Deep Dive

### Talend XML Mapping Format

In the Talend `.item` XML file, `MAPPING_JSONPATH` is stored as alternating `elementValue` pairs:

```xml
<elementParameter field="TABLE" name="MAPPING_JSONPATH">
  <elementValue elementRef="SCHEMA_COLUMN" value="user_id"/>
  <elementValue elementRef="QUERY" value="&quot;$.id&quot;"/>
  <elementValue elementRef="SCHEMA_COLUMN" value="username"/>
  <elementValue elementRef="QUERY" value="&quot;$.name&quot;"/>
  <elementValue elementRef="SCHEMA_COLUMN" value="email"/>
  <elementValue elementRef="QUERY" value="&quot;$.contact.email&quot;"/>
</elementParameter>
```

### Converter Output

The converter's `parse_tfileinputjson()` extracts `elementRef` as `column` and `value` as `jsonpath`:

```json
{
  "mapping": [
    {"column": "SCHEMA_COLUMN", "jsonpath": "user_id"},
    {"column": "QUERY", "jsonpath": "\"$.id\""},
    {"column": "SCHEMA_COLUMN", "jsonpath": "username"},
    {"column": "QUERY", "jsonpath": "\"$.name\""},
    {"column": "SCHEMA_COLUMN", "jsonpath": "email"},
    {"column": "QUERY", "jsonpath": "\"$.contact.email\""}
  ]
}
```

### Engine Normalization

`_normalize_mapping()` processes this alternating format:
1. Entry `{"column": "SCHEMA_COLUMN", "jsonpath": "user_id"}` -> stores `col = "user_id"`
2. Entry `{"column": "QUERY", "jsonpath": "\"$.id\""}` -> creates `{"column": "user_id", "jsonpath": "$.id"}` (quotes stripped)
3. Repeat for remaining pairs

**Result**:
```json
[
  {"column": "user_id", "jsonpath": "$.id"},
  {"column": "username", "jsonpath": "$.name"},
  {"column": "email", "jsonpath": "$.contact.email"}
]
```

### Potential Issues

1. **Missing QUERY for last SCHEMA_COLUMN**: If XML has odd number of elementValue entries (e.g., SCHEMA_COLUMN without matching QUERY), `col` is stored but never paired. The last column is silently dropped.

2. **Extra QUERY without SCHEMA_COLUMN**: If XML starts with a QUERY entry (no preceding SCHEMA_COLUMN), the condition `col is not None` on line 113 is False, so the entry is skipped.

3. **Non-alternating order**: If XML has two consecutive SCHEMA_COLUMN entries (no QUERY between), the first column name is overwritten by the second. The first column is silently lost.

4. **Empty column name**: If `elementRef="SCHEMA_COLUMN"` has empty `value=""`, `col` is set to empty string `""`. The subsequent QUERY creates a mapping with `column: ""`. This empty-named column will cause issues in DataFrame construction.

5. **Empty JSONPath**: If `elementRef="QUERY"` has empty `value=""`, `jp` is `""`. After quote stripping, it remains `""`. `parse("")` may raise `JsonPathParserError`.

---

## Appendix O: JSONPath Library Analysis

### jsonpath_ng.ext vs Standard jsonpath_ng

The engine imports `from jsonpath_ng.ext import parse` (line 182). The `ext` module extends standard JSONPath with:
- Filter expressions: `$.items[?(@.price > 10)]`
- Arithmetic operations in filters
- Named operators: `len()`, `sorted()`, etc.

This is more capable than standard `jsonpath_ng` and better matches Talend's JSONPath implementation which supports most JSONPath filter expressions.

### jsonpath_ng Behavior for Edge Cases

| Input | jsonpath_ng Result | Talend Result | Match? |
|-------|-------------------|---------------|--------|
| `$.missing` on `{"found": 1}` | `[]` (empty list) | `null` | Partial -- empty list vs null |
| `$.items[*]` on `{"items": []}` | `[]` (empty list) | 0 rows | Yes |
| `$.items[*]` on `{"items": [1,2,3]}` | `[1, 2, 3]` | 3 elements | Yes |
| `$.nested.deep.value` on `{"nested": {"deep": {"value": "hello"}}}` | `["hello"]` | `"hello"` | Yes (after flatten) |
| `$..name` (recursive descent) | All `name` values at any depth | All `name` values at any depth | Yes |
| `$.items[0]` (index access) | First item | First item | Yes |
| `$.items[?(@.active==true)]` (filter) | Filtered items | Filtered items | Yes (ext module) |
| `$.items[*].tags[*]` (nested arrays) | Flattened tags from all items | Flattened tags | Yes |

### Performance Characteristics

- `parse()` compiles a JSONPath expression into an AST. This is the expensive step.
- `.find()` executes the compiled expression against a JSON object. This is fast for simple paths, slower for recursive descent (`..`) and filters.
- For the current implementation, `parse()` is called M times per element (M = number of mapping columns), and there are N elements total. Total: N * M parse operations. With pre-compilation: M parse operations + N * M find operations.

---

## Appendix P: Reject Flow Comparison with Talend

### Talend Reject Behavior

In Talend, when `DIE_ON_ERROR=false` and a REJECT link is connected:
1. Each JSON element is processed independently
2. If JSONPath extraction fails for a field, the ENTIRE row goes to REJECT
3. Reject row contains: ALL schema columns (with partial data) + `errorCode` + `errorMessage`
4. `errorCode` is typically the Java exception class name (e.g., `java.lang.NumberFormatException`)
5. `errorMessage` is the Java exception message
6. Processing continues with the next element

### V1 Engine Reject Behavior

In the v1 engine (lines 197-251):
1. Each JSON element is processed in a try/except block (line 200)
2. If ANY error occurs during column extraction or type coercion, the row goes to reject (line 243-249)
3. Reject row contains: whatever partial data was in `row` dict + `errorCode='PARSE_ERROR'` + `errorMessage=str(err)`
4. `errorCode` is always `'PARSE_ERROR'` (hardcoded on line 245)
5. `errorMessage` is the Python exception string
6. Processing continues with next element (line 197 loop)

### Differences

| Aspect | Talend | V1 Engine |
|--------|--------|-----------|
| Error granularity | Per-field (each column tried independently) | Per-row (first error rejects entire row) |
| Partial data | All columns attempted, partial results kept | Columns up to error point only |
| Error code | Java exception class name | Always `'PARSE_ERROR'` |
| Error message | Java exception message | Python exception string |
| Reject schema | Schema columns + errorCode + errorMessage | Dict keys from partial row + errorCode + errorMessage |
| Type coercion errors | Row to REJECT, processing continues | Row to REJECT, processing continues |
| JSONPath not found | Null value, no error | Empty list `[]`, no error (BUG-FIJ-010) |

### V1 Improvement Opportunity

The current implementation stops processing a row at the first column error. To match Talend:
```python
for mapping_entry in mapping:
    try:
        # ... extraction and coercion for this column ...
        row[column_name] = val
    except Exception as err:
        row[column_name] = None  # Partial data
        if reject_row is None:
            reject_row = {}
            reject_row['errorCode'] = 'PARSE_ERROR'
            reject_row['errorMessage'] = str(err)
# After all columns, decide if row goes to main or reject
```

This would process ALL columns before deciding to reject, preserving partial data.

---

## Appendix Q: Configuration Validation Catalog

### validate_config() Analysis (Lines 286-334)

| Validation | Lines | What It Checks | Correct? |
|------------|-------|----------------|----------|
| Required `filename` | 299-302 | `not self.config.get('filename')` -- checks for None, empty string, False | Mostly correct. `0` would also trigger (edge case). Does NOT check `useurl` flag -- filename should not be required when URL mode is active. |
| Required `json_loop_query` | 299-302 | Same check | Correct. Always required regardless of read mode. |
| Required `mapping` | 299-302 | Same check | Correct. Always required. |
| Mapping is list | 307 | `not isinstance(mapping, list)` | Correct. |
| Mapping non-empty | 309 | `len(mapping) == 0` | Correct. Empty mapping produces no output columns. |
| Schema is list | 314 | `schema is not None and not isinstance(schema, list)` | Correct. |
| Encoding is string | 319 | `encoding is not None and not isinstance(encoding, str)` | Correct. |
| URL consistency | 323-325 | `useurl and not self.config.get('urlpath')` | Correct. URL required when URL mode active. |
| Missing: `json_loop_query` format | -- | Does NOT validate JSONPath syntax | **Gap**: Invalid JSONPath will crash at runtime |
| Missing: `mapping` entry format | -- | Does NOT validate each entry has `column` and `jsonpath` keys | **Gap**: Missing keys cause `None` values in extraction |
| Missing: `encoding` validity | -- | Does NOT validate encoding is supported by Python | **Gap**: Invalid encoding crashes `open()` call |
| Missing: `filename` existence | -- | Does NOT check if file exists on disk | **Gap**: Missing file crashes at runtime |
| Missing: schema column types | -- | Does NOT validate schema types are recognized | **Gap**: Unknown types silently skip coercion |

### If validate_config() Were Wired Up

Estimated impact on error detection:
- **5 misconfigurations** caught early (required fields, type checks)
- **5 misconfigurations** still not caught (format validation, file existence)
- **Net benefit**: Errors fail with clear "Missing required parameter 'filename'" instead of cryptic `AttributeError: 'NoneType' object has no attribute 'read'`

---

## Appendix R: Complete Import Analysis

```python
# Line 10 - USED: json.load() on line 177, json.loads() on line 173, json.dumps() on line 269
import json

# Line 11 - USED: logging.getLogger() on line 23 and line 91
import logging

# Line 12 - UNUSED: 'os' is never called anywhere in the file
import os

# Line 13 - UNUSED: 're' is never called anywhere in the file
import re

# Line 14 - UNUSED: 'codecs' is never called anywhere in the file
import codecs

# Line 15 - USED: Dict on line 93, Any on line 122, List on line 93
from typing import Dict, Any, List

# Line 16 - USED: urlopen on line 170
from urllib.request import urlopen

# Line 17 - USED: datetime.strptime on line 238
from datetime import datetime

# Line 19 - USED: pd.DataFrame on lines 262-263
import pandas as pd

# Line 21 - USED: BaseComponent on line 26
from ...base_component import BaseComponent

# Line 182 (inline) - USED: parse() on lines 184, 206
from jsonpath_ng.ext import parse
```

**Unused imports**: `os`, `re`, `codecs` (3 of 11 imports = 27% dead)

**Likely intent**:
- `os`: Was probably intended for `os.path.exists(filename)` check -- which the component lacks
- `re`: Was probably intended for regex-based JSONPath pattern validation
- `codecs`: Was probably intended as an alternative to `encoding` parameter in `open()`, or for BOM handling via `codecs.BOM_UTF8`
