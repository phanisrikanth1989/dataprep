# Audit Report: tFileInputXML / FileInputXML

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputXML` |
| **V1 Engine Class** | `FileInputXML` |
| **Engine File** | `src/v1/engine/components/file/file_input_xml.py` (556 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileinputxml()` (lines 1456-1483) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFileInputXML'` (lines 268-269) |
| **Registry Aliases** | `FileInputXML`, `tFileInputXML` (registered in `src/v1/engine/engine.py` lines 74-75) |
| **Category** | File / XML / Input |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_xml.py` | Engine implementation (556 lines): 6 module-level helpers + 1 class with 4 methods |
| `src/converters/complex_converter/component_parser.py` (lines 1456-1483) | Dedicated parser: `parse_tfileinputxml()` extracts FILENAME, LOOP_QUERY, MAPPING, LIMIT, DIE_ON_ERROR, ENCODING, IGNORE_NS, output schema |
| `src/converters/complex_converter/converter.py` (lines 268-269) | Dispatch: dedicated `elif` branch routes to `parse_tfileinputxml()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports -- **CONTAINS CASING BUG** (`FileInputXml` vs `FileInputXML`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 4 | 3 | 1 | 7 of 19 Talend params extracted (37%); missing IGNORE_DTD, GENERATION_MODE, GET_NODES, ADVANCED_SEPARATOR, VALIDATE_DATE, etc. Schema hardcodes type to `str`. Null-unsafe `.find(...).get(...)` chains crash on incomplete XML. |
| Engine Feature Parity | **Y** | 1 | 6 | 4 | 2 | No REJECT flow; no SAX/streaming parse; no GET_NODES; no date validation; namespace detection only finds root NS; bare `@attr` XPath silently broken |
| Code Quality | **R** | 3 | 5 | 7 | 2 | Import-breaking casing bug; cross-cutting `_update_global_map()` crash; `_validate_config()` dead code; parent traversal O(n^2); no custom exceptions; `zip()` drops columns silently; `extract_value` drops descendant text; `qualify_xpath` corrupts predicates |
| Performance & Memory | **Y** | 0 | 1 | 3 | 1 | Full DOM parse via ElementTree; no SAX streaming option; O(n) parent scan per `../` per column per row |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; P0 import bug blocks all usage**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileInputXML Does

`tFileInputXML` reads an XML structured file, iterates over repeating elements identified by a Loop XPath query, and extracts field values using per-column XPath expressions defined in a Mapping table. The extracted rows are output as a data flow matching the output schema. It supports multiple XML parsing engines (Dom4j, Xerces, SAX), namespace handling, DTD skipping, parent-axis navigation in XPath, and both main (FLOW) and reject (REJECT) output connections.

**Source**: [tFileInputXML Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/xml-connectors/tfileinputxml-standard-properties), [tFileInputXML Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/xml-connectors/tfileinputxml-standard-properties), [tFileInputXML ESB 5.x Docs](https://talendskill.com/talend-for-esb-docs/docs-5-x/tfileinputxml-docs-for-esb-5-x/)

**Component family**: XML (File / Input)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.
**Parsing engines**: Dom4j (default, slow/memory-heavy), Xerces (memory-heavy), SAX (fast/low memory)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. |
| 3 | File Name / Stream | `FILENAME` | Expression (String) | -- | **Mandatory**. Absolute file path to XML file or data stream variable (e.g., `globalMap.get("tFileFetch_1_INPUT_STREAM")`). Supports context variables, globalMap references, Java expressions. |
| 4 | Loop XPath Query | `LOOP_QUERY` | XPath expression (String) | -- | **Mandatory**. XPath expression identifying the repeating XML element to iterate over. Each match produces one output row. Example: `"/root/items/item"`. The loop element is the context node for all column XPath expressions. |
| 5 | Mapping Table | `MAPPING` | Table (SCHEMA_COLUMN, QUERY, NODECHECK) | Auto-populated from schema | Maps each output schema column to an XPath expression relative to the loop node. Three sub-columns: `SCHEMA_COLUMN` (column name from schema), `QUERY` (XPath expression), `NODECHECK` (boolean: get node XML content instead of text). |
| 6 | Limit | `LIMIT` | Integer | -1 | Maximum number of loop elements to process. `-1` = all elements, `0` = read none. Note: differs from tFileInputDelimited where `0` = unlimited. |
| 7 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Stop the entire job on XML parsing errors. When unchecked, error rows are routed to the REJECT flow (if connected) or skipped. **Note**: Default is `true`, unlike tFileInputDelimited's `false`. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 8 | Ignore DTD File | `IGNORE_DTD` | Boolean (CHECK) | `false` | Skip DTD validation and external entity resolution. Prevents network calls for DTD files and avoids errors when DTDs are unreachable. Critical for security (XXE prevention). |
| 9 | Ignore Namespaces | `IGNORE_NS` | Boolean (CHECK) | `false` | Strip all namespace prefixes and URIs from the XML before processing. Creates a temporary file with namespaces removed. Simplifies XPath expressions at the cost of namespace awareness. |
| 10 | Generate Temporary File | `GENERATE_TEMP_FILE` | String | -- | Path for temporary XML file storage when namespace stripping or other pre-processing is needed. |
| 11 | Encoding | `ENCODING` | Dropdown / Custom | `"UTF-8"` | Character encoding for file reading. Options include UTF-8, ISO-8859-1, and custom values. |
| 12 | Generation Mode | `GENERATION_MODE` | Dropdown | `"Dom4j"` | XML parsing engine. `Dom4j`: full DOM tree in memory (default, slow for large files). `Xerces`: alternative DOM parser. `SAX`: event-based streaming parser, fast and memory-efficient for large XML files. |
| 13 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands and decimal separators. |
| 14 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 15 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 16 | Validate Date | `VALIDATE_DATE` | Boolean (CHECK) | `false` | Strict date format validation against schema-defined patterns. Invalid dates cause row rejection. |
| 17 | Use Separator (Xerces mode) | `USE_SEPARATOR_XERCES` | Boolean (CHECK) | `false` | Separate concatenated child node text values with a delimiter. Only applicable when Generation Mode is Xerces. |
| 18 | Field Separator | `FIELD_SEPARATOR` | String | -- | Delimiter for child node values when Use Separator is enabled. |
| 19 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Mapping Table Structure

The Mapping table is the core configuration element. It contains three columns per row, grouped into triplets:

| Sub-column | elementRef | Description |
|------------|-----------|-------------|
| `SCHEMA_COLUMN` | Column name | Auto-populated from the output schema. Read-only. Each row in the mapping table corresponds to a schema column. |
| `QUERY` | XPath expression | Relative XPath from the loop node to the data element/attribute. Examples: `"name"` (child element text), `"@id"` (attribute), `"../parent/field"` (parent navigation), `"sub/child"` (nested element). |
| `NODECHECK` | Boolean | When `true` (equivalent to "Get nodes" checkbox), retrieves the entire XML subtree as a string instead of the text content. Used when downstream processing needs raw XML fragments. |

**Triplet layout in Talend XML**: Each schema column produces three consecutive `elementValue` entries under the `MAPPING` elementParameter:
1. `elementRef="SCHEMA_COLUMN"` with `value="column_name"`
2. `elementRef="QUERY"` with `value="xpath_expression"`
3. `elementRef="NODECHECK"` with `value="false"` (or `"true"`)

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Successfully parsed rows matching the output schema. All columns defined in the schema are present. Primary data output. |
| `REJECT` | Output | Row > Reject | Rows that failed XPath evaluation, type conversion, or XML parsing. Includes ALL original schema columns (with partial data) PLUS two additional columns: `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false`. |
| `ITERATE` | Output | Iterate | Enables iterative processing when the component is used with iteration components like `tFlowToIterate`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of loop elements processed (after LIMIT, before REJECT filtering). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available when `DIE_ON_ERROR=false`. |

**Note**: Unlike `tFileInputDelimited`, Talend's official documentation for `tFileInputXML` does NOT list `NB_LINE_OK` or `NB_LINE_REJECT` as separate global variables. Only `NB_LINE` and `ERROR_MESSAGE` are documented.

### 3.6 Behavioral Notes

1. **Loop XPath query**: The loop query defines the repeating element. Each match of this XPath produces one output row. Relative column XPaths are resolved from the loop node as context. Absolute XPaths (starting with `/`) are resolved from the document root regardless of loop context.

2. **Parent navigation (`../`)**: XPath expressions in the QUERY column support parent-axis navigation. For example, `"../header/date"` navigates up from the loop node to its parent, then down to `header/date`. This is essential for extracting data from sibling or ancestor elements relative to the loop node. Dom4j and Xerces support this natively; SAX mode has limitations.

3. **NODECHECK / Get Nodes**: When a column's NODECHECK is `true`, the component returns the serialized XML subtree of the matched node as a string, rather than the text content. This is used when downstream components (like `tXMLMap`) need to process XML fragments.

4. **Namespace handling**: When `IGNORE_NS=true`, Talend creates a temporary copy of the XML file with all namespace declarations and prefixes stripped. This allows simple XPath expressions without namespace awareness. When `IGNORE_NS=false`, XPath expressions must use namespace-qualified names or namespace-unaware patterns.

5. **LIMIT semantics**: `LIMIT=-1` means read all loop elements (unlimited). `LIMIT=0` means read none. This differs from `tFileInputDelimited` where `LIMIT=0` means unlimited. Positive values limit the number of loop iterations.

6. **Generation mode performance**:
   - **Dom4j** (default): Loads entire XML into memory as DOM tree. Simple, supports full XPath. Memory-intensive for large files (100MB+ XML can require 1GB+ heap).
   - **Xerces**: Alternative DOM parser. Similar memory characteristics to Dom4j.
   - **SAX**: Event-based streaming. Processes XML sequentially without building full tree. Fast and memory-efficient for large XML files. Some XPath features (parent-axis, preceding-sibling) are limited.

7. **Stream input**: `FILENAME` can reference a data stream variable from globalMap (e.g., `((java.io.InputStream)globalMap.get("iStream"))`). This allows reading XML from HTTP responses, database BLOBs, or other in-memory sources without writing to disk.

8. **REJECT flow behavior**: When a REJECT link is connected and `DIE_ON_ERROR=false`, rows where XPath evaluation fails, type conversion errors occur, or XML structure is malformed are routed to REJECT with `errorCode` and `errorMessage` columns. Without a REJECT link, errors are silently skipped.

9. **DTD security**: When `IGNORE_DTD=false` (default), the XML parser may attempt to download external DTDs referenced in the XML. This can cause network calls, timeouts, and is a vector for XXE (XML External Entity) attacks. Production best practice is to set `IGNORE_DTD=true`.

10. **Empty loop nodes**: If the loop XPath matches zero elements, the component produces zero rows with `NB_LINE=0`. This is not an error condition.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** `parse_tfileinputxml()` in `component_parser.py` (lines 1456-1483), dispatched from `converter.py` line 268-269. This follows the recommended pattern (unlike tFileInputDelimited which uses the deprecated generic mapper).

**Converter flow**:
1. `converter.py:_parse_component()` matches `component_type == 'tFileInputXML'`
2. Calls `self.component_parser.parse_tfileinputxml(node, component)`
3. Parser extracts parameters from `elementParameter` nodes
4. Mapping table parsed from `elementParameter[@name="MAPPING"]/elementValue` nodes
5. Output schema built from `metadata[@connector="FLOW"]/column` nodes

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILENAME` | Yes | `filename` | 1459 | Direct `.get('value')`. **Note**: V1 config key is `filename`, but engine also checks `filepath` and `FILENAME` (line 302 of engine). |
| 2 | `LOOP_QUERY` | Yes | `loop_query` | 1460 | Direct `.get('value')` |
| 3 | `MAPPING` | Yes | `mapping` | 1461-1465 | Iterates `elementValue` nodes. **BUG**: Uses `elementRef` for column and `value` for xpath, which may mismatch Talend's actual triplet layout (SCHEMA_COLUMN, QUERY, NODECHECK). See CONV-FIX-001. |
| 4 | `LIMIT` | Yes | `limit` | 1466 | Raw string value, not converted to int. |
| 5 | `DIE_ON_ERROR` | Yes | `die_on_error` | 1467 | Boolean conversion via `.lower() == 'true'`. Correct. |
| 6 | `ENCODING` | Yes | `encoding` | 1468 | Default `'UTF-8'` matches Talend default. |
| 7 | `IGNORE_NS` | Yes | `ignore_ns` | 1469 | Boolean conversion. Correct. |
| 8 | `IGNORE_DTD` | **No** | -- | -- | **Not extracted. DTD handling unavailable at runtime.** |
| 9 | `GENERATION_MODE` | **No** | -- | -- | **Not extracted. Engine always uses ElementTree (effectively Dom-like). No SAX option.** |
| 10 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted. No locale-aware number parsing.** |
| 11 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 12 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 13 | `VALIDATE_DATE` | **No** | -- | -- | **Not extracted. No strict date validation.** |
| 14 | `USE_SEPARATOR_XERCES` | **No** | -- | -- | **Not extracted.** |
| 15 | `FIELD_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 16 | `GENERATE_TEMP_FILE` | **No** | -- | -- | **Not extracted. Namespace stripping done differently in engine.** |
| 17 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used). |
| 18 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |
| 19 | `LABEL` | No | -- | -- | Not extracted (cosmetic -- no runtime impact). |

**Summary**: 7 of 19 parameters extracted (37%). 8 runtime-relevant parameters are missing.

### 4.2 Schema Extraction

Schema is extracted in the dedicated parser method (lines 1471-1482 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | **Hardcoded** | **Always set to `'str'` (line 1476)**. Talend type information (`id_String`, `id_Integer`, etc.) from the column `type` attribute is completely ignored. |
| `nullable` | **Hardcoded** | **Always set to `True` (line 1477)**. Talend nullable attribute from the column is ignored. |
| `key` | **Hardcoded** | **Always set to `False` (line 1478)**. Talend key attribute from the column is ignored. |
| `length` | **Hardcoded** | **Always set to `-1` (line 1479)**. Talend length attribute from the column is ignored. |
| `precision` | **Hardcoded** | **Always set to `-1` (line 1480)**. Talend precision attribute from the column is ignored. |
| `pattern` (date) | **No** | Not extracted. Date patterns from Talend schema not available for date conversion. |
| `default` | **No** | Column default value not extracted. |
| `talendType` | **No** | Full Talend type string not preserved. |

**Critical issue**: All schema columns are forced to `type: 'str'`. This means `validate_schema()` in `base_component.py` will never perform type conversion (since `'str'` maps to `'object'` which is a no-op). Integer, float, date, and BigDecimal columns will remain as strings in the output DataFrame. Downstream components expecting typed data will encounter type mismatches.

### 4.3 Mapping Table Parsing

The mapping table parsing (lines 1462-1465) uses a simple iteration over `elementValue` nodes:

```python
for mapping_entry in node.findall('.//elementParameter[@name="MAPPING"]/elementValue'):
    column = mapping_entry.get('elementRef', '')
    xpath = mapping_entry.get('value', '')
    component['config']['mapping'].append({'column': column, 'xpath': xpath})
```

**Issue**: Talend's MAPPING parameter stores entries as triplets (SCHEMA_COLUMN, QUERY, NODECHECK). The converter treats each `elementValue` as an independent entry, extracting `elementRef` as the column type indicator and `value` as the actual value. This produces a flat list like:
```json
[
  {"column": "SCHEMA_COLUMN", "xpath": "col_name"},
  {"column": "QUERY", "xpath": "xpath_expr"},
  {"column": "NODECHECK", "xpath": "false"},
  ...
]
```

The engine's `_parse_xml()` method (line 450-461) then manually re-groups these into triplets by scanning for `SCHEMA_COLUMN` + `QUERY` pairs and skipping `NODECHECK`. This works but is fragile and discards the NODECHECK value entirely.

### 4.4 Expression Handling

**Context variable handling**: The dedicated parser does NOT call `self.expr_converter.mark_java_expression()` on any extracted values. This means:
- Java expressions in `FILENAME` (e.g., `context.input_dir + "/data.xml"`) are stored as raw strings, not marked with `{{java}}` prefix.
- Context variables (e.g., `context.filepath`) are stored as raw strings.
- The `BaseComponent.execute()` method's generic `context_manager.resolve_dict()` call (line 202) handles `${context.var}` syntax, but Talend-style `context.var` without `${}` wrapper is NOT resolved.

**Implication**: Jobs using Java expressions or bare context variable references in FILENAME or LOOP_QUERY will fail at runtime because the values are not resolved before processing.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FIX-001 | **P1** | **Schema types hardcoded to `'str'`**: Line 1476 always sets `type: 'str'`, ignoring the actual Talend type from `column.get('type')`. This prevents type coercion for integer, float, date, and BigDecimal columns. Should use `self.expr_converter.convert_type(column.get('type', 'id_String'))`. |
| CONV-FIX-002 | **P1** | **Schema nullable/key/length/precision hardcoded**: Lines 1477-1480 hardcode values instead of reading from the Talend XML `column` attributes. Should extract `nullable`, `key`, `length`, `precision` from the XML just as the generic schema extractor does in `parse_base_component()`. |
| CONV-FIX-003 | **P1** | **NODECHECK not extracted from mapping**: The NODECHECK triplet entry is parsed into the mapping list but never used by the engine. When `NODECHECK=true`, the engine should return XML subtree content instead of text. Currently, `get_nodes` behavior is completely missing. |
| CONV-FIX-004 | **P1** | **No Java expression marking on FILENAME**: `parse_tfileinputxml()` does not call `self.expr_converter.mark_java_expression()` on the `FILENAME` value. Java expressions like `context.input_dir + "/data.xml"` are stored as literal strings and not resolved at runtime. |
| CONV-FIX-005 | **P2** | **`IGNORE_DTD` not extracted**: DTD handling flag missing from converter output. Engine has `ignore_dtd` config support but it is never populated from Talend XML. |
| CONV-FIX-006 | **P2** | **`GENERATION_MODE` not extracted**: SAX mode flag missing. Engine always uses DOM-like ElementTree parsing. For large XML files, SAX would be required for production workloads. |
| CONV-FIX-007 | **P1** | **Converter crashes with AttributeError on incomplete Talend XML**: Six `node.find(...).get(...)` calls at lines 1459-1469 have no null checks. If any of the expected `elementParameter` nodes (`FILENAME`, `LOOP_QUERY`, `LIMIT`, `DIE_ON_ERROR`, `ENCODING`, `IGNORE_NS`) are missing from the Talend XML, `node.find()` returns `None` and the chained `.get('value')` raises `AttributeError: 'NoneType' object has no attribute 'get'`. Missing parameter = crash. |
| CONV-FIX-010 | **P2** | **`VALIDATE_DATE` not extracted**: Date validation flag missing. Even if schema types were correctly extracted, date validation would not be enabled. |
| CONV-FIX-008 | **P3** | **`ADVANCED_SEPARATOR` / `THOUSANDS_SEPARATOR` / `DECIMAL_SEPARATOR` not extracted**: Locale-aware number parsing unavailable. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Read XML file | **Yes** | High | `_parse_xml()` line 397, `_parse_xml_passthrough()` line 515 | Uses `xml.etree.ElementTree`. DOM parsing -- entire file loaded into memory. |
| 2 | Loop XPath query | **Yes** | Medium | `_parse_xml()` lines 407-437 | Complex normalization: strips root tag, adds `.//` prefix, qualifies with namespace. May over-normalize in edge cases (see ENG-FIX-003). |
| 3 | Column XPath extraction | **Yes** | Medium | `_parse_xml()` lines 478-507 | Iterates schema columns with paired XPaths. Uses `extract_value()` helper. Returns empty string for missing nodes (matches Talend null-to-empty behavior). |
| 4 | Namespace handling | **Partial** | Low | `normalize_nsmaps()` line 57, `qualify_xpath()` line 77 | **Only detects namespace from root element tag** (line 67-71). Multiple namespaces, child-element namespaces, and declared-but-unused namespaces are not detected. See ENG-FIX-004. |
| 5 | Parent navigation (`../`) | **Yes** | Medium | `find_element_by_manual_navigation()` line 110 | Manual tree traversal since ElementTree does not support `..` in XPath. Uses `find_parent_element()` which is O(n) per call. See PERF-FIX-001. |
| 6 | Encoding support | **Partial** | Medium | `_parse_xml_passthrough()` line 533 | Only used in passthrough mode for `ET.XMLParser(encoding=...)`. In tabular mode, `ET.parse()` on line 397 uses XML declaration encoding (ignoring config encoding). |
| 7 | Die on error | **Yes** | High | `_process()` lines 365-372 | Raises `RuntimeError` when true; returns empty DataFrame when false. |
| 8 | LIMIT | **No** | N/A | -- | **Config is extracted but never used in `_parse_xml()`**. The `limit` parameter is read from config (line 311) and passed to `_parse_xml_passthrough()` but NOT to `_parse_xml()`. Tabular mode always processes all loop nodes. |
| 9 | Ignore DTD | **Partial** | Low | `_parse_xml_passthrough()` line 535 | Only in passthrough mode: `parser.entity = {}`. Tabular mode (`_parse_xml()`) has NO DTD handling -- uses bare `ET.parse()` which can fail on DTD references. |
| 10 | Ignore namespaces | **No** | N/A | -- | Config is read (line 309) but never used in `_parse_xml()`. Only passed to `_parse_xml_passthrough()`. The engine attempts automatic namespace qualification instead of stripping. |
| 11 | XML passthrough mode | **Yes** | Medium | `_parse_xml_passthrough()` line 515 | Re-reads file as raw string. Creates single-row DataFrame with XML content. Used for XMLMap workflows. |
| 12 | Passthrough/tabular detection | **Yes** | Low | `_process()` lines 332-339 | Heuristic: uses passthrough when `explicit_mode == 'xml_passthrough'` OR output schema has exactly 1 column. Single-column tabular schemas are misdetected as passthrough. See ENG-FIX-005. |
| 13 | Attribute extraction (`@attr`) | **No** | Broken | `qualify_xpath()` line 98, `extract_value()` line 47 | ElementTree's `findall()` does not support bare `@attr` XPath syntax -- raises `SyntaxError` caught by `try/except`, returning empty string. Any Talend job using `@id` or similar bare attribute column XPaths silently gets empty values. See ENG-FIX-012, BUG-FIX-016. |
| 14 | Schema type enforcement | **No** | N/A | -- | Converter hardcodes all types to `str`, so `validate_schema()` is a no-op. Even if types were correct, `validate_schema()` is never called in `_process()`. |
| 15 | **REJECT flow** | **No** | N/A | -- | **No reject output. All errors either die or return empty DF. Fundamental gap.** |
| 16 | **GET_NODES (NODECHECK)** | **No** | N/A | -- | **XML subtree serialization not implemented. Always extracts text content.** |
| 17 | **SAX parsing mode** | **No** | N/A | -- | **Always uses DOM (ElementTree). No SAX streaming option for large XML files.** |
| 18 | **Date validation** | **No** | N/A | -- | **No VALIDATE_DATE support.** |
| 19 | **Advanced separator** | **No** | N/A | -- | **No locale-aware number parsing.** |
| 20 | **Stream input** | **No** | N/A | -- | **Only file path input. No InputStream/globalMap stream support.** |
| 21 | **Xerces separator mode** | **No** | N/A | -- | **Not implemented.** |
| 22 | **`{id}_FILENAME` globalMap** | **No** | N/A | -- | **Resolved filename not stored in globalMap.** |
| 23 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIX-001 | **P0** | **Import casing mismatch blocks engine startup**: `__init__.py` line 10 imports `FileInputXml` (lowercase 'm') but the class is defined as `FileInputXML` (uppercase 'ML') in `file_input_xml.py` line 212. `engine.py` line 21 imports `FileInputXML` from the package. This raises `ImportError: cannot import name 'FileInputXml' from 'src.v1.engine.components.file.file_input_xml'. Did you mean: 'FileInputXML'?` at engine startup. **The entire v1 engine cannot load while this bug exists.** Confirmed via direct Python import test. |
| ENG-FIX-002 | **P1** | **No REJECT flow**: Talend produces reject rows for XPath evaluation failures with `errorCode` and `errorMessage` columns when `DIE_ON_ERROR=false` and a REJECT link is connected. V1 either raises `RuntimeError` (die_on_error=true) or returns empty DataFrame (die_on_error=false). There is NO mechanism to capture and route bad rows. |
| ENG-FIX-003 | **P1** | **LIMIT not applied in tabular mode**: The `limit` config is extracted (line 311) and passed to `_parse_xml_passthrough()` (line 345) but NOT passed to `_parse_xml()` (line 352). Tabular mode always processes ALL loop nodes regardless of LIMIT setting. Jobs relying on LIMIT for performance or sampling will process entire files. |
| ENG-FIX-004 | **P1** | **Namespace detection only finds root element namespace**: `normalize_nsmaps()` (line 57-71) only extracts namespace from the root element's tag (e.g., `{http://example.com}root` -> `ns0: http://example.com`). XML documents with multiple namespaces, namespaces declared on non-root elements, or namespace prefixes other than the default are not detected. XPath qualification will fail for elements in secondary namespaces. |
| ENG-FIX-005 | **P1** | **Single-column tabular schema misdetected as passthrough**: Lines 335-336 check `len(output_schema) == 1` and force passthrough mode. A legitimate tabular extraction with a single output column (e.g., extracting just `id` from each loop node) will incorrectly enter passthrough mode, returning the entire XML as a string instead of extracted values. |
| ENG-FIX-006 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. |
| ENG-FIX-007 | **P2** | **Encoding ignored in tabular mode**: `_parse_xml()` line 397 uses `ET.parse(filepath)` which reads encoding from the XML declaration (e.g., `<?xml encoding="UTF-8"?>`). The config `encoding` parameter is only used in passthrough mode (line 533). If the XML file lacks an encoding declaration and uses non-UTF-8 encoding, tabular mode will fail or produce mojibake. |
| ENG-FIX-008 | **P2** | **`ignore_ns` config read but unused in tabular mode**: Line 309 reads `ignore_ns` from config but only passes it to `_parse_xml_passthrough()`. The tabular `_parse_xml()` method does NOT receive or use this parameter. Instead, it always attempts automatic namespace qualification. |
| ENG-FIX-009 | **P2** | **Loop XPath over-normalization**: Lines 408-428 perform aggressive normalization on the loop query: stripping leading `/`, removing root element prefix, prepending `.//`. This transforms `/root/items/item` into `.//ns0:item` which may match unintended elements at arbitrary depth (`.//` means "anywhere in subtree"). Talend's `/root/items/item` should match only at that specific path. |
| ENG-FIX-010 | **P2** | **`_process()` uses `filepath`/`FILENAME` config keys but converter sets `filename`**: The engine reads `filepath` first, falls back to `FILENAME` (line 302). The converter stores the value under `filename` (line 1459 of component_parser.py). This means `self.config.get("filepath")` returns None, then `self.config.get("FILENAME")` also returns None, and the actual value under `filename` is never read. **This should fail for all converted jobs.** |
| ENG-FIX-011 | **P2** | **No GET_NODES support**: NODECHECK mapping entries are parsed but discarded. When Talend jobs use Get Nodes to extract XML subtrees as strings, the engine returns empty string or text content instead. |
| ENG-FIX-012 | **P1** | **Bare `@attr` XPath expressions silently fail**: ElementTree's `findall()` does not support bare `@attr` syntax -- it raises `SyntaxError` which is caught by the surrounding `try/except`, causing the function to return empty string. Any Talend job using `@id` or similar bare attribute column XPaths silently gets empty values instead of the attribute content. |
| ENG-FIX-015 | **P3** | **No SAX parsing option**: Engine always uses DOM-based ElementTree. For XML files exceeding 100MB, this can require gigabytes of memory. SAX-based parsing would handle arbitrarily large files with constant memory. |
| ENG-FIX-013 | **P3** | **No stream input support**: Only file path input. Cannot read XML from in-memory streams, HTTP responses, or database BLOBs. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism (but see BUG-FIX-002 -- `_update_global_map()` crashes). |
| `{id}_NB_LINE_OK` | Not documented for tFileInputXML | **Yes** | Same mechanism | V1 sets this via base class, but Talend does not officially expose it for this component. Always equals NB_LINE. |
| `{id}_NB_LINE_REJECT` | Not documented for tFileInputXML | **Yes** | Same mechanism | Always 0 since no reject flow exists. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. |
| `{id}_FILENAME` | Not documented | **No** | -- | Not implemented. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIX-001 | **P0** | `src/v1/engine/components/file/__init__.py:10` | **Import casing mismatch**: `from .file_input_xml import FileInputXml` but class is `FileInputXML`. This causes `ImportError` at engine startup, preventing ALL components from loading (since `engine.py` imports from this package). **Confirmed via direct Python import test**: `ImportError: cannot import name 'FileInputXml' from 'src.v1.engine.components.file.file_input_xml'. Did you mean: 'FileInputXML'?` |
| BUG-FIX-002 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the for loop variable (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: Affects ALL components. |
| BUG-FIX-003 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: Method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but body calls `self._map.get(key, default)` (line 28). `default` is undefined. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FIX-004 | **P1** | `src/v1/engine/components/file/file_input_xml.py:302` | **Config key mismatch: engine reads `filepath`/`FILENAME` but converter stores `filename`**: `_process()` line 302 reads `self.config.get("filepath") or self.config.get("FILENAME")`. Converter line 1459 stores value under `config['filename']`. Neither `filepath` nor `FILENAME` will match, so `filepath` is always `None` for converted jobs. The component raises `ValueError("XML file path not provided")` on every converted job. |
| BUG-FIX-005 | **P1** | `src/v1/engine/components/file/file_input_xml.py:262-294` | **`_validate_config()` is never called**: The method exists with 32 lines of validation logic (checks filepath, encoding, limit, mapping) but is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. |
| BUG-FIX-006 | **P1** | `src/v1/engine/components/file/file_input_xml.py:335-336` | **Single-column schema forces passthrough mode**: `elif len(output_schema) == 1: mode = "xml_passthrough"` means any XML extraction with a single output column is treated as passthrough, returning the entire XML file content as a string instead of extracting the single column value from each loop node. |
| BUG-FIX-007 | **P1** | `src/v1/engine/components/file/file_input_xml.py:348` | **`_update_stats` sets NB_LINE_REJECT=0 always**: `self._update_stats(rows_out, rows_out, 0)` unconditionally sets `NB_LINE_OK = NB_LINE` and `NB_LINE_REJECT = 0`. Even if individual row extraction fails, no reject counting occurs. |
| BUG-FIX-008 | **P2** | `src/v1/engine/components/file/file_input_xml.py:372` | **Empty DataFrame returned on error loses schema**: When `die_on_error=False`, line 372 returns `pd.DataFrame()` which is an empty DataFrame with NO columns. Downstream components expecting specific columns will fail. Should return a DataFrame with the expected columns but zero rows. |
| BUG-FIX-009 | **P2** | `src/v1/engine/components/file/file_input_xml.py:397` | **`ET.parse()` does not handle DTD by default**: `ET.parse(filepath)` in tabular mode can fail or hang on XML files with external DTD references (e.g., `<!DOCTYPE root SYSTEM "http://example.com/dtd">`). No DTD ignoring is applied. The `ignore_dtd` config is only used in passthrough mode (line 535). |
| BUG-FIX-010 | **P2** | `src/v1/engine/components/file/file_input_xml.py:530-535` | **`parser.entity = {}` does not ignore DTD**: Setting `parser.entity = {}` on `ET.XMLParser` only disables entity expansion, not DTD downloading/validation. ElementTree does not support DTD skipping natively. A custom `XMLParser` with `resolve_entities=False` or `defusedxml` library is needed for proper DTD handling. |
| BUG-FIX-011 | **P1** | `src/v1/engine/components/file/file_input_xml.py` | **`zip(schema_order, schema_xpaths)` silently drops columns on length mismatch**: When the `schema_order` and `schema_xpaths` lists have different lengths, `zip()` silently truncates to the shorter list. Extra columns are lost with no warning. This can occur when the mapping table has fewer QUERY entries than schema columns (e.g., due to NODECHECK triplet parsing issues), causing output to silently omit trailing columns. |
| BUG-FIX-012 | **P2** | `src/v1/engine/components/file/file_input_xml.py` | **`extract_value` drops descendant text for elements with children**: For mixed-content elements like `<desc>Hello <b>world</b></desc>`, the function returns only `'Hello '` (the element's direct `.text`), not `'Hello world'`. Talend concatenates all descendant text nodes (equivalent to XPath `string()` or `normalize-space()`). Should use `''.join(elem.itertext())` to match Talend behavior. |
| BUG-FIX-013 | **P2** | `src/v1/engine/components/file/file_input_xml.py` | **`qualify_xpath` corrupts XPath predicates containing element names**: Predicates like `item[sub='value']` are namespace-qualified only on the outer element, producing `ns0:item[sub='value']` instead of the correct `ns0:item[ns0:sub='value']`. Element names inside predicate brackets are not qualified, causing predicate evaluation to fail silently on namespaced documents (no match found, empty result returned). |
| BUG-FIX-016 | **P2** | `src/v1/engine/components/file/file_input_xml.py:51` | **`extract_value()` falls through to `str(node_or_nodes)` for non-Element results**: When `findall()` returns attribute strings (from `@attr` XPath), the result is a list of strings, not Elements. The function checks `isinstance(node, ET.Element)` on line 43, which fails for strings, and falls through to `str(node_or_nodes)` on line 51 which stringifies the entire list (e.g., `"['value']"` instead of `"value"`). |
| BUG-FIX-017 | **P2** | `src/v1/engine/components/file/file_input_xml.py:402` | **`list(nsmap.keys())[0]` fragile on empty dict**: While the ternary expression `ns_prefix = list(nsmap.keys())[0] if nsmap else ""` is correct Python and will NOT crash, it is fragile -- a code change removing the `if nsmap` guard would cause `IndexError`. Should use `next(iter(nsmap), "")`. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIX-001 | **P1** | **Casing inconsistency across codebase**: Class is `FileInputXML` (file_input_xml.py:212), `__init__.py` exports as `FileInputXml`, `__all__` list uses `FileInputXml`, engine.py imports `FileInputXML`, converter mapping uses `FileInputXML`. Three different casings for the same class. |
| NAME-FIX-002 | **P2** | **Config key `filename` vs engine expectation `filepath`/`FILENAME`**: Converter stores under `filename` (component_parser.py:1459), engine reads `filepath` then `FILENAME` (file_input_xml.py:302). The key `filename` is never read. |
| NAME-FIX-003 | **P3** | **`loop_query` vs `LOOP_QUERY` dual naming**: Engine reads both `loop_query` and `LOOP_QUERY` (line 303). Converter stores as `loop_query`. The dual-read is defensive but adds unnecessary complexity. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIX-001 | **P1** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Dead code. |
| STD-FIX-002 | **P1** | "Schema types should preserve Talend format" | Converter hardcodes all types to `'str'` instead of using `convert_type()` to map Talend types. |
| STD-FIX-003 | **P2** | "Components should use custom exceptions" | Uses generic `ValueError`, `FileNotFoundError`, `RuntimeError` instead of `ConfigurationError`, `FileOperationError`, `ComponentExecutionError` from `exceptions.py`. |
| STD-FIX-004 | **P2** | "No redundant imports" | `import xml.etree.ElementTree as ET` appears at module level (line 11) AND again inside `_parse_xml_passthrough()` (line 530). The local import is redundant. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FIX-001 | **P3** | **Excessive DEBUG logging in hot loop**: Lines 475-510 contain 12 `logger.debug()` calls inside the per-row, per-column loop in `_parse_xml()`. For an XML with 10,000 loop nodes and 10 columns, this produces 120,000+ log messages. These should be guarded with `if logger.isEnabledFor(logging.DEBUG)` or removed. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FIX-001 | **P2** | **Billion Laughs DoS vulnerability**: `ET.parse(filepath)` on line 397 uses the default ElementTree parser. Python's `xml.etree.ElementTree` does NOT expand external entities (so XXE file exfiltration is not a risk), but it IS vulnerable to Billion Laughs (exponential entity expansion) attacks. A malicious XML with nested entity definitions like `<!ENTITY lol9 "&lol8;&lol8;&lol8;">` can consume gigabytes of memory and crash the process. Should use `defusedxml.ElementTree` which guards against both entity expansion bombs and other XML-based DoS vectors. |
| SEC-FIX-002 | **P3** | **No path traversal protection**: `filepath` from config is used directly with `os.path.exists()` and `ET.parse()`. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 344/351) and completion (line 347/360) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| **Over-logging** | **12 debug statements inside inner loop** -- excessive for production use |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **NOT used** -- raises generic `ValueError`, `FileNotFoundError`, `RuntimeError` instead of `ConfigurationError`, `FileOperationError`, `ComponentExecutionError` |
| Exception chaining | Uses `raise RuntimeError(...) from e` on line 368 -- correct |
| `die_on_error` handling | Single try/except block in `_process()` (lines 365-372) -- correct |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and file path -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- **PARTIALLY correct**: empty DF has no columns, losing schema |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` and `_validate_config()` have return type hints -- correct |
| Parameter types | `_parse_xml()` and `_parse_xml_passthrough()` have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[int]`, `List[Dict[str, str]]` -- correct |
| Module-level functions | All 6 helper functions have type hints and docstrings -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIX-001 | **P1** | **`find_parent_element()` is O(n) per call, causing O(n*m*k) overall complexity**: `find_parent_element()` (line 169-184) iterates the ENTIRE tree from root for every parent navigation call. For each loop node (n) with each `../` column (m), it traverses all tree elements (k). For an XML with 10,000 loop nodes, 3 parent-navigation columns, and 50,000 total elements, this is 10,000 * 3 * 50,000 = 1.5 BILLION element comparisons. Should build a parent map once: `parent_map = {child: parent for parent in root.iter() for child in parent}` (or use `ET.Element` iterparse with parent tracking). |
| PERF-FIX-002 | **P2** | **Full DOM parse for all file sizes**: `ET.parse()` loads the entire XML file into memory as a DOM tree. For a 500MB XML file, this can require 2-5GB of heap. No streaming/SAX option is available. Talend offers SAX mode for exactly this scenario. |
| PERF-FIX-003 | **P2** | **Namespace qualification called per column per row**: `qualify_xpath()` is called for every column of every loop node (line 488). The result is always the same for a given XPath expression. Should be pre-computed once per column before the loop iteration. |
| PERF-FIX-004 | **P2** | **Double file read in passthrough mode**: `_parse_xml_passthrough()` first parses the file with `ET.parse()` (line 537) to get the root tag, then re-reads it with `open()` (line 544) to get the raw XML content. The `ET.parse()` call is unnecessary since the root tag is not used for anything meaningful (only logged). |
| PERF-FIX-005 | **P3** | **Excessive debug logging in hot loop**: 12 `logger.debug()` calls in the per-row/per-column loop. Even when debug is disabled, the f-string formatting and method call overhead occurs for each invocation. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| DOM parsing | Full file loaded into memory via `ET.parse()`. No streaming alternative. |
| DataFrame creation | `pd.DataFrame(rows)` creates the entire result at once from a list of dicts. For very large results, this doubles memory (list + DataFrame). |
| Passthrough mode | Reads entire file into a string (`xml_content = f.read()`). For large XML files, this duplicates the DOM tree's memory usage. |
| No chunk support | Unlike `FileInputDelimited`, there is no `chunk_size` or streaming mode for incremental processing. |
| Hybrid mode | Base class `_auto_select_mode()` can select streaming, but `_process()` always does full DOM parse regardless. Streaming mode in base class only applies to input DataFrame chunking, not XML file reading. |

### 7.2 Streaming Mode Analysis

The base class `BaseComponent` supports `ExecutionMode.HYBRID` with automatic streaming selection based on input data size. However, for `FileInputXML`:

| Issue | Description |
|-------|-------------|
| Input is file, not DataFrame | `FileInputXML` reads from a file, not from an input DataFrame. The base class streaming mode only chunks input DataFrames, which is irrelevant here. |
| `_process()` always full DOM | Regardless of execution mode, `_parse_xml()` calls `ET.parse()` which loads the entire file into memory. |
| No incremental output | The method builds a complete `rows` list, then converts to DataFrame at once. No yielding or chunked output. |
| **Conclusion** | **HYBRID streaming mode from base class provides zero benefit for FileInputXML. The component always operates in batch mode regardless of the execution_mode setting.** |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileInputXML` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tfileinputxml()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 556 lines of v1 engine code and 28 lines of converter code are completely unverified. Additionally, the P0 import bug (BUG-FIX-001) means the component cannot even be imported, so ANY test would have caught this immediately.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Import test | P0 | Verify `from src.v1.engine.components.file import FileInputXML` succeeds. Currently fails due to BUG-FIX-001. |
| 2 | Basic XML read | P0 | Read a simple XML file with loop query and 3 columns, verify row count and column values match expected output. |
| 3 | Config key resolution | P0 | Verify that `filename` config key (from converter) is correctly read by the engine. Currently fails due to BUG-FIX-004. |
| 4 | Missing file + die_on_error=true | P0 | Should raise exception with descriptive message. |
| 5 | Missing file + die_on_error=false | P0 | Should return empty DataFrame with stats (0, 0, 0). |
| 6 | Empty XML (no loop matches) | P0 | Should return empty DataFrame without error, stats (0, 0, 0). |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict after execution. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Namespace handling | P1 | Read XML with default namespace, verify XPath qualification produces correct results. |
| 9 | Multiple namespaces | P1 | Read XML with 2+ namespaces, verify columns in secondary namespaces are extracted (currently fails). |
| 10 | Parent navigation (`../`) | P1 | Read XML with `../sibling/field` XPath, verify parent navigation produces correct results. |
| 11 | Attribute extraction | P1 | XPath like `@id` or `sub/@attr`, verify attribute values are extracted correctly. |
| 12 | LIMIT enforcement | P1 | Verify `limit=5` reads only 5 loop elements from a 100-element XML. Currently fails (limit not applied in tabular mode). |
| 13 | Single-column schema | P1 | Verify single-column tabular extraction does NOT enter passthrough mode. Currently fails (BUG-FIX-006). |
| 14 | Passthrough mode | P1 | Verify explicit `mode='xml_passthrough'` returns full XML content in a single row. |
| 15 | Die on error with parse error | P1 | Malformed XML + die_on_error=true should raise RuntimeError (or preferably FileOperationError). |
| 16 | Die on error false with parse error | P1 | Malformed XML + die_on_error=false should return empty DataFrame. |
| 17 | Context variable in filepath | P1 | `${context.input_dir}/data.xml` should resolve via context manager. |
| 18 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | Large XML (100K elements) | P2 | Verify performance is acceptable and memory does not explode. Benchmark against ElementTree baseline. |
| 20 | DTD reference in XML | P2 | XML with external DTD reference should not hang or crash. |
| 21 | Encoding non-UTF8 | P2 | Read XML with ISO-8859-1 encoding declaration, verify non-ASCII characters are correct. |
| 22 | Empty element text | P2 | Loop node child with `<name></name>` should produce empty string, not None. |
| 23 | Mixed content | P2 | Element with both text and child elements (e.g., `<p>text <b>bold</b> more</p>`) -- verify extraction behavior. |
| 24 | CDATA sections | P2 | Elements with `<![CDATA[content]]>` -- verify text extraction includes CDATA content. |
| 25 | XPath with predicates | P2 | XPath like `item[@type='A']/name` -- verify predicate filtering works. |
| 26 | Concurrent reads | P2 | Multiple `FileInputXML` instances reading different files simultaneously. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIX-001 | Bug | **Import casing mismatch**: `__init__.py` exports `FileInputXml` but class is `FileInputXML`. Prevents entire v1 engine from loading. Confirmed via Python import test. |
| BUG-FIX-002 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FIX-003 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FIX-001 | Testing | Zero v1 unit tests for FileInputXML. All 556 lines of engine code + 28 lines of converter code are unverified. Even a basic import test would have caught BUG-FIX-001. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIX-004 | Bug | Config key mismatch: engine reads `filepath`/`FILENAME` but converter stores `filename`. All converted jobs fail with "XML file path not provided". |
| BUG-FIX-005 | Bug | `_validate_config()` is dead code -- never called by any code path. 32 lines of unreachable validation. |
| BUG-FIX-006 | Bug | Single-column schema forces passthrough mode. Legitimate single-column tabular extractions return entire XML instead of extracted values. |
| BUG-FIX-007 | Bug | `NB_LINE_REJECT` always 0 -- no reject counting even if individual row extraction fails. |
| CONV-FIX-001 | Converter | Schema types hardcoded to `'str'`, ignoring Talend type information. Prevents type coercion for all columns. |
| CONV-FIX-002 | Converter | Schema nullable/key/length/precision hardcoded. All Talend schema attributes ignored. |
| CONV-FIX-003 | Converter | NODECHECK not extracted from mapping. GET_NODES functionality completely missing. |
| CONV-FIX-004 | Converter | No Java expression marking on FILENAME. Java expressions in file path not resolved at runtime. |
| CONV-FIX-007 | Converter | Converter crashes with `AttributeError` on incomplete Talend XML. Six `node.find(...).get(...)` calls at lines 1459-1469 have no null checks. Missing parameter = crash. |
| ENG-FIX-002 | Engine | No REJECT flow -- bad rows are lost or cause job failure. |
| ENG-FIX-003 | Engine | LIMIT not applied in tabular mode -- always processes all loop nodes. |
| ENG-FIX-004 | Engine | Namespace detection only finds root element namespace. Multiple namespaces not supported. |
| ENG-FIX-005 | Engine | Single-column tabular schema misdetected as passthrough mode. |
| ENG-FIX-006 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set. |
| ENG-FIX-012 | Engine | Bare `@attr` XPath expressions silently fail. ElementTree `findall()` raises `SyntaxError` caught by `try/except`, returns empty string. Jobs using `@id` column XPaths get empty values. |
| BUG-FIX-011 | Bug | `zip(schema_order, schema_xpaths)` silently drops columns on length mismatch. Extra columns lost with no warning. |
| NAME-FIX-001 | Naming | Three different casings for class name across codebase (`FileInputXML`, `FileInputXml`, `FileInputXml`). |
| STD-FIX-001 | Standards | `_validate_config()` dead code -- exists but never called. |
| STD-FIX-002 | Standards | Converter schema types hardcoded to `'str'` instead of using `convert_type()`. |
| PERF-FIX-001 | Performance | `find_parent_element()` is O(n) per call, causing O(n*m*k) quadratic scan for parent navigation. |
| TEST-FIX-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| BUG-FIX-008 | Bug | Empty DataFrame on error has no columns -- loses schema for downstream components. |
| BUG-FIX-009 | Bug | `ET.parse()` in tabular mode does not handle DTD references. Can hang on external DTDs. |
| BUG-FIX-010 | Bug | `parser.entity = {}` in passthrough mode does not actually ignore DTD. Only disables entity expansion. |
| BUG-FIX-012 | Bug | `extract_value` drops descendant text for elements with children. `<desc>Hello <b>world</b></desc>` returns `'Hello '` not `'Hello world'`. Talend concatenates all descendant text. |
| BUG-FIX-013 | Bug | `qualify_xpath` corrupts XPath predicates containing element names. `item[sub='value']` becomes `ns0:item[sub='value']` instead of `ns0:item[ns0:sub='value']`. |
| BUG-FIX-016 | Bug | `extract_value()` stringifies list for non-Element XPath results (attribute strings). Produces `"['value']"` instead of `"value"`. |
| BUG-FIX-017 | Bug | `list(nsmap.keys())[0]` fragile on empty dict -- correct via ternary but fragile for maintenance. |
| CONV-FIX-005 | Converter | `IGNORE_DTD` not extracted from Talend XML. DTD handling unavailable. |
| CONV-FIX-006 | Converter | `GENERATION_MODE` not extracted. No SAX option for large files. |
| CONV-FIX-010 | Converter | `VALIDATE_DATE` not extracted. No date validation support. |
| ENG-FIX-007 | Engine | Encoding ignored in tabular mode. Only used in passthrough mode. |
| ENG-FIX-008 | Engine | `ignore_ns` config read but unused in tabular mode. Namespace stripping not available. |
| ENG-FIX-009 | Engine | Loop XPath over-normalization. `.//` prefix matches at arbitrary depth instead of specific path. |
| ENG-FIX-010 | Engine | Config key `filename` from converter not read by engine (reads `filepath`/`FILENAME`). |
| ENG-FIX-011 | Engine | No GET_NODES support. NODECHECK mapping entries discarded. |
| STD-FIX-003 | Standards | Uses generic exceptions instead of custom exceptions from `exceptions.py`. |
| STD-FIX-004 | Standards | Redundant `import xml.etree.ElementTree as ET` inside method (already at module level). |
| SEC-FIX-001 | Security | Billion Laughs DoS vulnerability: `ET.parse()` does not guard against exponential entity expansion. Python's ElementTree does NOT expand external entities (no XXE risk), but IS vulnerable to internal entity expansion bombs. |
| PERF-FIX-002 | Performance | Full DOM parse for all file sizes. No SAX streaming option. |
| PERF-FIX-003 | Performance | Namespace qualification called per column per row. Should be pre-computed. |
| PERF-FIX-004 | Performance | Double file read in passthrough mode. Unnecessary `ET.parse()` before raw `open()`. |
| NAME-FIX-002 | Naming | Config key `filename` vs engine expectation `filepath`/`FILENAME`. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FIX-008 | Converter | `ADVANCED_SEPARATOR` / number formatting not extracted. |
| ENG-FIX-015 | Engine | No SAX parsing option for large XML files. |
| ENG-FIX-013 | Engine | No stream input support. Only file path input. |
| NAME-FIX-003 | Naming | `loop_query` / `LOOP_QUERY` dual naming adds unnecessary complexity. |
| SEC-FIX-002 | Security | No path traversal protection on filepath. |
| PERF-FIX-005 | Performance | 12 debug statements in hot loop. F-string formatting overhead even when disabled. |
| DBG-FIX-001 | Debug | Excessive DEBUG logging in per-row/per-column loop (12 calls per row*column). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 3 bugs (1 component-specific, 2 cross-cutting), 1 testing |
| P1 | 21 | 5 bugs, 5 converter, 6 engine, 1 naming, 2 standards, 1 performance, 1 testing |
| P2 | 22 | 7 bugs, 3 converter, 5 engine, 1 naming, 2 standards, 1 security, 3 performance |
| P3 | 7 | 1 converter, 2 engine, 1 naming, 1 security, 1 performance, 1 debug |
| **Total** | **54** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix import casing bug** (BUG-FIX-001): Change `__init__.py` line 10 from `from .file_input_xml import FileInputXml` to `from .file_input_xml import FileInputXML`. Also update `__all__` list to use `'FileInputXML'`. **Impact**: Unblocks entire v1 engine from loading. **Risk**: Very low.

2. **Fix `_update_global_map()` bug** (BUG-FIX-002): Change `value` to `stat_value` on `base_component.py` line 304, or remove the stale `{stat_name}: {value}` reference. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low.

3. **Fix `GlobalMap.get()` bug** (BUG-FIX-003): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components. **Risk**: Very low.

4. **Fix config key mismatch** (BUG-FIX-004): Either change the converter to store `filepath` instead of `filename` (component_parser.py line 1459), or add `self.config.get("filename")` as a third fallback in the engine (file_input_xml.py line 302). Recommended: change converter to use `filepath` for consistency with other file components. **Impact**: Unblocks all converted tFileInputXML jobs. **Risk**: Low.

5. **Create unit test suite** (TEST-FIX-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: import verification, basic XML read, config key resolution, missing file handling, empty XML, and statistics tracking. **Impact**: Catches regressions for all future changes. **Risk**: None.

### Short-Term (Hardening)

6. **Fix schema type extraction in converter** (CONV-FIX-001, CONV-FIX-002): Replace hardcoded `'str'` with `self.expr_converter.convert_type(column.get('type', 'id_String'))`. Extract `nullable`, `key`, `length`, `precision` from column attributes. **Impact**: Enables type coercion for integer, float, date, BigDecimal columns.

7. **Fix single-column passthrough misdetection** (BUG-FIX-006): Remove the `elif len(output_schema) == 1` condition (line 335-336). Only use passthrough when explicitly configured via `mode='xml_passthrough'`. If XMLMap integration requires passthrough detection, use a more specific heuristic (e.g., check if the single column name matches a known XMLMap pattern). **Impact**: Fixes single-column tabular extractions.

8. **Apply LIMIT in tabular mode** (ENG-FIX-003): Pass `limit` to `_parse_xml()` and add `if limit and idx >= limit: break` after the loop node enumeration (line 474). **Impact**: Enables row limiting for performance and sampling.

9. **Add Java expression marking in converter** (CONV-FIX-004): Add `self.expr_converter.mark_java_expression()` call for FILENAME value in `parse_tfileinputxml()`. **Impact**: Enables Java expression resolution in file paths.

10. **Fix `find_parent_element()` performance** (PERF-FIX-001): Build parent map once before the loop:
    ```python
    parent_map = {child: parent for parent in root.iter() for child in parent}
    ```
    Then replace `find_parent_element(target, root)` with `parent_map.get(target)`. **Impact**: Reduces parent navigation from O(n*k) to O(1) per call.

11. **Wire up `_validate_config()`** (BUG-FIX-005): Add a call at the beginning of `_process()`. Raise `ConfigurationError` or return empty DataFrame based on `die_on_error`. **Impact**: Catches invalid configs early.

12. **Fix namespace detection for multiple namespaces** (ENG-FIX-004): Use `ET.iterparse()` with namespace events, or walk the entire tree to collect all unique namespace URIs. Register all namespaces for XPath evaluation. **Impact**: Enables processing of multi-namespace XML documents.

13. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FIX-006): In the error handler (line 366-372), call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` if `global_map` is available.

14. **Add IGNORE_DTD extraction and handling** (CONV-FIX-005, BUG-FIX-009): Extract `IGNORE_DTD` in converter. In engine, use `defusedxml.ElementTree.parse()` or a custom parser that disables DTD loading. **Impact**: Prevents hangs and XXE on DTD-referencing XML files.

### Long-Term (Optimization)

15. **Add SAX parsing mode** (ENG-FIX-015, CONV-FIX-006): Implement a SAX-based parser for large XML files. Use `xml.sax` or `lxml.etree.iterparse()` with element clearing for constant-memory processing. Gate behind `generation_mode='SAX'` config. **Impact**: Enables processing of 100MB+ XML files without memory exhaustion.

16. **Add GET_NODES support** (CONV-FIX-003, ENG-FIX-011): Extract NODECHECK from mapping triplets. When true, serialize the matched element subtree with `ET.tostring()`. **Impact**: Enables XMLMap workflows that require XML fragments.

17. **Implement REJECT flow** (ENG-FIX-002): Wrap per-row XPath extraction in try/except. Capture failed rows with `errorCode` and `errorMessage`. Return `{'main': good_df, 'reject': reject_df}`. **Impact**: Enables data quality pipelines.

18. **Add stream input support** (ENG-FIX-013): Accept `io.BytesIO` or `io.StringIO` objects as input in addition to file paths. **Impact**: Enables reading XML from HTTP responses and in-memory sources.

19. **Pre-compute qualified XPaths** (PERF-FIX-003): Before the loop iteration, qualify all column XPaths once and store in a list. Reuse per row instead of re-qualifying each time. **Impact**: Minor performance improvement for large document processing.

20. **Create integration test** (TEST-FIX-002): Build an end-to-end test exercising `tFileInputXML -> tXMLMap -> tFileOutputDelimited` in the v1 engine. **Impact**: Validates XMLMap workflow integration.

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 1456-1483
def parse_tfileinputxml(self, node, component: Dict) -> Dict:
    """Parse tFileInputXML specific configuration and build full output schema from metadata"""
    # Parse basic config
    component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    component['config']['loop_query'] = node.find('.//elementParameter[@name="LOOP_QUERY"]').get('value', '')
    component['config']['mapping'] = []
    for mapping_entry in node.findall('.//elementParameter[@name="MAPPING"]/elementValue'):
        column = mapping_entry.get('elementRef', '')
        xpath = mapping_entry.get('value', '')
        component['config']['mapping'].append({'column': column, 'xpath': xpath})
    component['config']['limit'] = node.find('.//elementParameter[@name="LIMIT"]').get('value', '')
    component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
    component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    component['config']['ignore_ns'] = node.find('.//elementParameter[@name="IGNORE_NS"]').get('value', 'false').lower() == 'true'
    # Build output schema from metadata (not just mapping)
    output_schema = []
    for metadata_node in node.findall('./metadata[@connector="FLOW"]'):
        for column in metadata_node.findall('./column'):
            output_schema.append({
                'name': column.get('name', ''),
                'type': 'str',           # <<< BUG: hardcoded, ignores Talend type
                'nullable': True,         # <<< BUG: hardcoded, ignores Talend nullable
                'key': False,             # <<< BUG: hardcoded, ignores Talend key
                'length': -1,             # <<< BUG: hardcoded, ignores Talend length
                'precision': -1           # <<< BUG: hardcoded, ignores Talend precision
            })
    component['schema']['output'] = output_schema
    return component
```

**Notes on this code**:
- Line 1459: Stores under `filename` key, but engine reads `filepath` / `FILENAME` -- key mismatch.
- Line 1460: No quote stripping on LOOP_QUERY value (engine does its own stripping on line 304-305, 407).
- Lines 1462-1465: Treats all `elementValue` nodes uniformly. Does not distinguish SCHEMA_COLUMN / QUERY / NODECHECK triplets. Engine re-parses at runtime.
- Line 1466: `LIMIT` stored as raw string. Engine does not parse this string to int in tabular mode.
- Line 1476: `type: 'str'` hardcoded -- most impactful bug in the converter for this component.

---

## Appendix B: Engine Class Structure

```
Module-level helpers (6 functions):
    extract_value(node_or_nodes) -> str         # Extract text from XML node(s)
    normalize_nsmaps(root) -> Dict[str, str]    # Extract namespace from root tag only
    qualify_xpath(expr, ns_prefix) -> str        # Add namespace prefix to XPath elements
    find_element_by_manual_navigation(...)       # Handle ../ parent navigation
    find_parent_element(target, root) -> Element # O(n) tree scan for parent
    choose_context(expr_q, loop_node, root)      # Choose root vs loop context

FileInputXML(BaseComponent):
    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]   # Main entry point: routes to tabular or passthrough
        _parse_xml(filepath, loop_query, ...)     # Tabular mode: XPath extraction per loop node
        _parse_xml_passthrough(filepath, ...)     # Passthrough mode: returns raw XML as single row
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILENAME` | `filename` (converter) / `filepath` (engine) | **Key mismatch** | P1 fix |
| `LOOP_QUERY` | `loop_query` | Mapped | -- |
| `MAPPING` | `mapping` | Mapped (flat list) | -- |
| `LIMIT` | `limit` | Mapped but unused in tabular | P1 fix |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped | -- |
| `IGNORE_NS` | `ignore_ns` | Mapped but unused in tabular | P2 fix |
| `IGNORE_DTD` | `ignore_dtd` | **Not Mapped** | P2 |
| `GENERATION_MODE` | `generation_mode` | **Not Mapped** | P2 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** | P3 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** | P3 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** | P3 |
| `VALIDATE_DATE` | `validate_date` | **Not Mapped** | P2 |
| `USE_SEPARATOR_XERCES` | `use_separator_xerces` | **Not Mapped** | P3 (rarely used) |
| `FIELD_SEPARATOR` | `field_separator` | **Not Mapped** | P3 (rarely used) |
| `GENERATE_TEMP_FILE` | `temp_file_path` | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- |
| `PROPERTY_TYPE` | -- | Not needed | -- |
| `LABEL` | -- | Not needed | -- |

---

## Appendix D: Type Mapping Analysis

### Converter Output (current -- all hardcoded)

| Talend Type | Converter Output | Correct Output |
|-------------|-----------------|----------------|
| `id_String` | `str` (hardcoded) | `str` |
| `id_Integer` | `str` (hardcoded) | `int` |
| `id_Long` | `str` (hardcoded) | `int` |
| `id_Float` | `str` (hardcoded) | `float` |
| `id_Double` | `str` (hardcoded) | `float` |
| `id_Boolean` | `str` (hardcoded) | `bool` |
| `id_Date` | `str` (hardcoded) | `datetime` |
| `id_BigDecimal` | `str` (hardcoded) | `Decimal` |

### Engine validate_schema() Behavior

Since all types are `'str'` (mapped to `'object'` in `validate_schema()`), the validation method performs NO type conversion. All columns remain as Python strings in the output DataFrame. This means:
- Integer columns contain strings like `"42"` instead of `42`
- Float columns contain strings like `"3.14"` instead of `3.14`
- Date columns contain strings like `"2024-01-15"` instead of `datetime` objects
- Boolean columns contain strings like `"true"` instead of `True`

Downstream components that expect typed data (e.g., `tMap` with numeric comparisons) will encounter type errors or incorrect behavior.

### Recommended Fix

Replace line 1476 in `component_parser.py`:
```python
# Current (broken):
'type': 'str',

# Fixed:
'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
```

---

## Appendix E: Detailed Code Analysis

### `extract_value()` (Module-level, Lines 24-51)

Extracts text value from XML node(s). Handles three cases:
1. Empty/falsy input -> returns `""`
2. List input -> takes first element, recurses
3. Element node -> returns `.text` (stripped), or serialized attributes if no text
4. Non-Element -> `str()` cast

**Bug**: Case 4 is reached when `findall()` returns attribute strings (from `@attr` XPath). The result is a list of strings, so case 2 sets `node = node_or_nodes[0]` (a string). Case 3 fails (`isinstance(string, ET.Element)` is False). Case 4 then calls `str(node_or_nodes)` which stringifies the ORIGINAL list, not `node`. This produces `"['value']"` instead of `"value"`. Should return `str(node)` instead.

### `normalize_nsmaps()` (Module-level, Lines 57-71)

Extracts namespace from root element tag by looking for `{uri}localname` format. Returns at most ONE namespace mapping (`ns0: uri`). Completely ignores:
- Namespace declarations on non-root elements
- Multiple namespace prefixes
- Default namespace vs prefixed namespaces
- `xmlns` attributes

### `qualify_xpath()` (Module-level, Lines 77-104)

Adds namespace prefix to each path segment. Correctly skips:
- `.` and `..` navigation operators
- `@attr` attribute selectors
- Already-qualified `prefix:name` segments

**Edge case**: Does not handle predicates (e.g., `item[@type='A']` would be qualified as `ns0:item[@type='A']` which is correct). Does not handle XPath functions (e.g., `text()`, `position()`, `count()`).

### `find_element_by_manual_navigation()` (Module-level, Lines 110-166)

Handles `../` parent navigation that ElementTree does not support natively. Algorithm:
1. Count `../` segments at the start of the XPath
2. Navigate up that many levels using `find_parent_element()` (O(n) each)
3. Qualify the remaining path with namespace
4. Use `findall()` on the ancestor node

**Performance**: O(levels_up * tree_size) per call. For deeply nested XML with many parent navigations, this becomes quadratic.

### `find_parent_element()` (Module-level, Lines 169-184)

Finds parent by iterating ENTIRE tree from root. Uses identity comparison (`child is target`) which is correct for ElementTree (elements have unique identity).

**Performance**: O(tree_size) per call. Called once per `../` segment per column per loop node.

### `_process()` (Lines 296-372)

Main processing method:
1. Extract config values with defaults
2. Determine output schema from component attribute or config
3. Validate filepath existence
4. Determine mode: explicit passthrough, single-column heuristic, or tabular
5. Branch to `_parse_xml()` or `_parse_xml_passthrough()`
6. Update stats and return
7. Catch-all exception handler with `die_on_error` support

**Key observation**: Does NOT call `validate_schema()`. Even if schema types were correctly extracted, no type coercion would occur.

### `_parse_xml()` (Lines 377-512)

Tabular XML extraction:
1. Parse XML with `ET.parse()` (full DOM load)
2. Detect namespace from root element
3. Normalize and qualify loop XPath
4. Find all loop nodes
5. Collect SCHEMA_COLUMN/QUERY pairs from mapping (skipping NODECHECK)
6. For each loop node, evaluate each column XPath
7. Handle parent navigation via `find_element_by_manual_navigation()`
8. Extract text values via `extract_value()`
9. Build row dicts, return list

**Complexity**: O(loop_nodes * columns * tree_size) for parent navigation columns. O(loop_nodes * columns) for regular columns.

### `_parse_xml_passthrough()` (Lines 515-555)

Passthrough mode:
1. Parse XML with `ET.XMLParser(encoding=...)` (for encoding support)
2. If `ignore_dtd`, set `parser.entity = {}` (ineffective -- see BUG-FIX-010)
3. Re-read file as raw string with `open(filepath, 'r', encoding=encoding)`
4. Create single-row DataFrame with column name from output schema

**Inefficiency**: Parses XML to DOM (step 1), then discards it and re-reads as raw string (step 3).

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty XML file

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0. No error. |
| **V1** | `ET.parse()` on empty file raises `ET.ParseError`. Caught by exception handler. If `die_on_error=false`, returns empty DataFrame. |
| **Verdict** | PARTIAL -- error instead of clean 0-row result. |

### Edge Case 2: XML with no matching loop nodes

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0. No error. |
| **V1** | `root.findall(loop_xpath_q)` returns `[]`. Loop body not entered. Returns empty DataFrame via `pd.DataFrame([])`. |
| **Verdict** | CORRECT (but loses column names -- empty DataFrame has no columns). |

### Edge Case 3: XML with default namespace

| Aspect | Detail |
|--------|--------|
| **Talend** | With `IGNORE_NS=false`, XPath must use namespace prefixes. With `IGNORE_NS=true`, namespaces stripped. |
| **V1** | `normalize_nsmaps()` detects root namespace. `qualify_xpath()` prefixes all elements with `ns0:`. `findall()` uses namespace map. |
| **Verdict** | CORRECT for single default namespace. FAILS for multiple namespaces. |

### Edge Case 4: XML with multiple namespaces

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles via Dom4j/Xerces namespace resolution. XPath expressions use declared prefixes. |
| **V1** | Only detects root element namespace. Secondary namespaces not registered. XPath queries for elements in secondary namespaces produce empty results. |
| **Verdict** | **GAP** -- multi-namespace XML not supported. |

### Edge Case 5: Parent navigation (`../`) with deep nesting

| Aspect | Detail |
|--------|--------|
| **Talend** | Dom4j supports full XPath parent axis natively. |
| **V1** | Manual `find_parent_element()` traversal. Works correctly but O(n) per parent level. |
| **Verdict** | CORRECT but slow for deeply nested XML with many rows. |

### Edge Case 6: Attribute extraction (`@id`)

| Aspect | Detail |
|--------|--------|
| **Talend** | Standard XPath attribute access. Returns attribute value as string. |
| **V1** | `qualify_xpath()` correctly skips `@` prefix, but ElementTree's `findall()` does not support bare `@attr` XPath syntax -- it raises `SyntaxError` which is caught by the surrounding `try/except`, causing the function to return empty string. Even if `findall()` did return results, `extract_value()` would stringify the list (see BUG-FIX-016). |
| **Verdict** | **BROKEN** -- bare `@attr` XPaths silently return empty string. See ENG-FIX-012, BUG-FIX-016. |

### Edge Case 7: NaN/None handling in extracted values

| Aspect | Detail |
|--------|--------|
| **Talend** | Missing nodes produce `null`. Type-specific defaults apply (0 for int, empty for string). |
| **V1** | `extract_value()` returns `""` (empty string) for missing nodes. Never returns `None` or `NaN`. All missing values become empty strings in the DataFrame. |
| **Verdict** | PARTIAL -- empty string instead of None/NaN. Downstream `pd.isna()` checks will NOT detect missing values. `is None` checks will also fail. Only `== ""` detects missing values. |

### Edge Case 8: Empty DataFrame schema loss

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty result retains schema (column names and types). |
| **V1** | `pd.DataFrame(rows)` where `rows=[]` produces DataFrame with NO columns. `pd.DataFrame()` on error path also has no columns. |
| **Verdict** | **GAP** -- schema lost on empty results. Should use `pd.DataFrame(columns=schema_order)`. |

### Edge Case 9: Thread safety

| Aspect | Detail |
|--------|--------|
| **V1** | Module-level helper functions are stateless and thread-safe. `find_parent_element()` uses read-only tree traversal. `FileInputXML` instances maintain state in `self.stats` which is per-instance. `ET.parse()` is thread-safe. |
| **Verdict** | SAFE -- no shared mutable state. Multiple instances can process different files concurrently. |

### Edge Case 10: Type demotion through iterrows/Series

| Aspect | Detail |
|--------|--------|
| **V1** | This component does NOT use `iterrows()`. It builds rows as a list of dicts and creates the DataFrame at once via `pd.DataFrame(rows)`. No Series-based iteration occurs. |
| **Verdict** | NOT APPLICABLE -- no type demotion risk through iterrows. |

### Edge Case 11: validate_schema nullable logic (inverted condition)

| Aspect | Detail |
|--------|--------|
| **V1** | `base_component.py` line 351: `if pandas_type == 'int64' and col_def.get('nullable', True)`. This checks if nullable is True and then fills NaN with 0 and casts to int64. The logic appears inverted -- non-nullable columns should refuse NaN, while nullable columns should keep NaN. However, since the converter hardcodes nullable=True for all columns AND all types are `'str'`, this code path is NEVER reached for FileInputXML. |
| **Verdict** | NOT APPLICABLE due to type hardcoding. But the nullable logic IS inverted as a latent bug in base_component.py. When/if CONV-FIX-001 is fixed and types are correctly extracted, this will surface as a behavioral issue: nullable int columns will have NaN replaced with 0 (losing null information), while non-nullable int columns will NOT have NaN replaced (keeping NaN in violation of non-nullable constraint). |

### Edge Case 12: _validate_config() called or dead code?

| Aspect | Detail |
|--------|--------|
| **V1** | `_validate_config()` at line 262 is NEVER called. Not by `__init__()`, not by `execute()`, not by `_process()`. The base class `BaseComponent` does not call it. Searching the entire codebase for `_validate_config` shows it is defined in multiple components but never invoked anywhere. |
| **Verdict** | **DEAD CODE** across all components. Systemic issue. |

### Edge Case 13: Passthrough vs tabular mode detection correctness

| Aspect | Detail |
|--------|--------|
| **V1** | Detection logic (lines 332-339): (1) explicit `mode='xml_passthrough'` -> passthrough. (2) `len(output_schema) == 1` -> passthrough. (3) else -> tabular. |
| **Problem** | Condition (2) is incorrect. A legitimate tabular extraction with one column (e.g., extracting just `name` from each `<item>`) will be forced into passthrough mode, returning the entire XML file as a single string. |
| **Fix** | Remove condition (2). Only use passthrough when explicitly configured. |

### Edge Case 14: HYBRID streaming mode via base class -- correct behavior?

| Aspect | Detail |
|--------|--------|
| **V1** | Base class `_auto_select_mode()` selects STREAMING when input DataFrame exceeds MEMORY_THRESHOLD_MB (3GB). `_execute_streaming()` chunks the input DataFrame and calls `_process()` per chunk. |
| **Problem** | FileInputXML receives `input_data=None` (it reads from a file, not an input DataFrame). `_auto_select_mode(None)` always returns BATCH. Even if STREAMING were selected, `_execute_streaming(None)` falls back to `self._process(None)` (line 258). The XML file is ALWAYS loaded as full DOM regardless. |
| **Verdict** | HYBRID mode has ZERO effect on FileInputXML. No streaming XML parsing occurs. The base class streaming infrastructure is irrelevant for file-reading components. |

### Edge Case 15: _update_global_map() crash effect on result return + component status

| Aspect | Detail |
|--------|--------|
| **V1** | `execute()` calls `_update_global_map()` on line 218 (success path) and line 231 (error path). Due to BUG-FIX-002 (undefined `value` variable), this will raise `NameError` AFTER `_process()` has completed successfully. The exception propagates up from `execute()`, and the successful result is LOST. The component status is set to ERROR (line 228) even though processing succeeded. On the error path (line 231), the crash also means the error status is set (line 228) but the re-raise on line 234 may throw the NameError instead of the original exception, masking the root cause. |
| **Verdict** | **CRITICAL** -- successful processing results are lost due to logging bug in post-processing step. Cross-cutting: affects ALL components when global_map is set. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileInputXML`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FIX-001 | **P0** | `components/file/__init__.py:10` | Import casing mismatch `FileInputXml` vs `FileInputXML`. Blocks engine loading. |
| BUG-FIX-002 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Crashes ALL components on success/error path. Result is lost. |
| BUG-FIX-003 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Crashes on any `get()` call. |
| BUG-FIX-005 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. Systemic architectural gap. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FIX-001 -- Import Casing Mismatch

**File**: `src/v1/engine/components/file/__init__.py`
**Line**: 10

**Current code (broken)**:
```python
from .file_input_xml import FileInputXml
```

**Fix**:
```python
from .file_input_xml import FileInputXML
```

Also update `__all__` list (line 33):
```python
# Current:
'FileInputXml',
# Fix:
'FileInputXML',
```

**Impact**: Unblocks entire v1 engine from loading. **Risk**: Very low -- simple naming correction.

---

### Fix Guide: BUG-FIX-002 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FIX-003 -- `GlobalMap.get()` undefined default

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

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: BUG-FIX-004 -- Config Key Mismatch

**File**: `src/converters/complex_converter/component_parser.py`
**Line**: 1459

**Current code (mismatched)**:
```python
component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
```

**Fix** (preferred -- align converter to engine expectation):
```python
component['config']['filepath'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
```

**Alternative fix** (in engine -- add fallback):
```python
# file_input_xml.py line 302
filepath = self.config.get("filepath") or self.config.get("FILENAME") or self.config.get("filename")
```

**Impact**: Unblocks all converted tFileInputXML jobs. **Risk**: Low.

---

### Fix Guide: BUG-FIX-006 -- Single-Column Passthrough Misdetection

**File**: `src/v1/engine/components/file/file_input_xml.py`
**Lines**: 332-339

**Current code (incorrect)**:
```python
explicit_mode = self.config.get('mode')
if explicit_mode == 'xml_passthrough':
    mode = "xml_passthrough"
elif len(output_schema) == 1:
    # Single column output suggests XMLMap workflow - use passthrough mode
    mode = "xml_passthrough"
else:
    mode = "tabular"
```

**Fix**:
```python
explicit_mode = self.config.get('mode')
if explicit_mode == 'xml_passthrough':
    mode = "xml_passthrough"
else:
    mode = "tabular"
```

**Impact**: Fixes single-column tabular XML extractions. **Risk**: Low -- may break XMLMap workflows that rely on automatic passthrough detection. Those should be explicitly configured with `mode='xml_passthrough'`.

---

### Fix Guide: PERF-FIX-001 -- Parent Map Optimization

**File**: `src/v1/engine/components/file/file_input_xml.py`

**Add to `_parse_xml()` after line 398 (after `ET.parse()`)**:
```python
# Build parent map once for O(1) parent lookups
parent_map = {child: parent for parent in root.iter() for child in parent}
```

**Replace `find_parent_element()` call in `find_element_by_manual_navigation()`**:
```python
# Current (O(n)):
parent = find_parent_element(current, root)

# Fixed (O(1)):
parent = parent_map.get(current)
```

**Note**: `parent_map` would need to be passed as a parameter to `find_element_by_manual_navigation()`, or the function could be refactored to accept a parent_map parameter.

**Impact**: Reduces parent navigation from O(tree_size) to O(1) per parent level. For large XML with many `../` columns, this is a dramatic improvement. **Risk**: Low -- semantically identical behavior.

---

### Fix Guide: CONV-FIX-001 -- Schema Type Extraction

**File**: `src/converters/complex_converter/component_parser.py`
**Lines**: 1474-1481

**Current code (hardcoded)**:
```python
output_schema.append({
    'name': column.get('name', ''),
    'type': 'str',
    'nullable': True,
    'key': False,
    'length': -1,
    'precision': -1
})
```

**Fix**:
```python
col_type = column.get('type', 'id_String')
output_schema.append({
    'name': column.get('name', ''),
    'type': self.expr_converter.convert_type(col_type),
    'nullable': column.get('nullable', 'true').lower() == 'true',
    'key': column.get('key', 'false').lower() == 'true',
    'length': int(column.get('length', '-1')),
    'precision': int(column.get('precision', '-1'))
})
```

**Impact**: Enables type coercion for all columns. Integer, float, date, and BigDecimal columns will be correctly typed in the output DataFrame. **Risk**: Low -- follows the same pattern as the generic schema extractor in `parse_base_component()`.

---

## Appendix I: Comparison with Other XML Components

| Feature | tFileInputXML (V1) | tFileInputJSON (V1) | tXMLMap (V1) | tExtractXMLField (V1) |
|---------|---------------------|---------------------|--------------|------------------------|
| Basic reading | Yes | Yes | N/A (transform) | N/A (transform) |
| Loop/path query | Yes (XPath) | Yes (JSONPath) | Yes (XPath) | Yes (XPath) |
| Namespace handling | Partial (root only) | N/A | Unknown | Unknown |
| Parent navigation | Yes (manual) | N/A | Unknown | Unknown |
| Multiple output schemas | No | No | Yes | No |
| Schema type enforcement | No (hardcoded str) | Unknown | Unknown | Unknown |
| REJECT flow | No | No | No | No |
| SAX/streaming parse | No | No | N/A | N/A |
| Die on error | Yes | Yes | Unknown | Unknown |
| V1 Unit tests | **No** | **No** | **No** | **No** |

**Observation**: The schema type hardcoding, missing REJECT flow, and lack of tests are issues shared across XML-family components. The namespace limitation is specific to `FileInputXML`.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| ANY tFileInputXML job | **Critical** | ALL | BUG-FIX-001 blocks import; BUG-FIX-004 blocks file path resolution. Both must be fixed. |
| Jobs using REJECT flow | **Critical** | Jobs with REJECT link on tFileInputXML | Must implement REJECT flow before migrating. |
| Jobs with typed schemas (int, date, BigDecimal) | **High** | Most production jobs | Fix CONV-FIX-001 to extract actual types. |
| Jobs using multiple namespaces | **High** | Jobs processing SOAP/XBRL/complex XML | Fix ENG-FIX-004 for multi-namespace support. |
| Jobs using LIMIT for sampling | **High** | Jobs with LIMIT > 0 | Fix ENG-FIX-003 to apply limit in tabular mode. |
| Jobs with single-column output | **High** | Jobs extracting one value per row | Fix BUG-FIX-006 passthrough misdetection. |
| Jobs using GET_NODES | **Medium** | XMLMap preprocessing jobs | Implement ENG-FIX-011. |
| Jobs with DTD references in XML | **Medium** | Jobs processing DTD-validated XML | Fix BUG-FIX-009/010 for DTD handling. |
| Jobs processing large XML (>100MB) | **Medium** | Performance-sensitive jobs | Implement SAX mode (ENG-FIX-015). |
| Jobs using Java expressions in FILENAME | **Medium** | Jobs with dynamic file paths | Fix CONV-FIX-004 for expression marking. |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using ADVANCED_SEPARATOR | Low | Rarely used with XML files. |
| Jobs using VALIDATE_DATE | Low | Most XML dates are validated upstream. |
| Jobs using tStatCatcher | Low | Monitoring feature, not data flow. |

### Recommended Migration Strategy

1. **Phase 0 (Blockers)**: Fix BUG-FIX-001 (import casing), BUG-FIX-002 (global_map crash), BUG-FIX-003 (global_map.get crash), BUG-FIX-004 (config key mismatch). Without these, NO tFileInputXML job can run.
2. **Phase 1 (Core)**: Fix CONV-FIX-001 (schema types), BUG-FIX-006 (passthrough misdetection), ENG-FIX-003 (LIMIT). Create P0 unit tests.
3. **Phase 2 (Parity)**: Fix ENG-FIX-004 (multi-namespace), PERF-FIX-001 (parent map), CONV-FIX-004 (expression marking). Create P1 unit tests.
4. **Phase 3 (Production)**: Implement REJECT flow (ENG-FIX-002). Add SAX mode (ENG-FIX-015). Fix DTD handling (BUG-FIX-009/010). Parallel-run against Talend.
5. **Phase 4 (Validation)**: Row-for-row comparison of migrated jobs against Talend originals. Address any behavioral differences.

---

## Appendix K: Complete Mapping Table Parser Fix

The following is the recommended replacement for the mapping table parsing in `parse_tfileinputxml()`. This properly handles the SCHEMA_COLUMN / QUERY / NODECHECK triplet layout:

```python
def parse_tfileinputxml(self, node, component: Dict) -> Dict:
    """Parse tFileInputXML specific configuration and build full output schema from metadata"""

    # Helper to safely get parameter value
    def get_param(name, default=''):
        elem = node.find(f'.//elementParameter[@name="{name}"]')
        if elem is not None:
            return elem.get('value', default)
        return default

    # Parse basic config
    filename = get_param('FILENAME', '')
    component['config']['filepath'] = self.expr_converter.mark_java_expression(filename)

    loop_query = get_param('LOOP_QUERY', '')
    component['config']['loop_query'] = loop_query

    # Parse MAPPING table as triplets (SCHEMA_COLUMN, QUERY, NODECHECK)
    component['config']['mapping'] = []
    mapping_elements = node.findall('.//elementParameter[@name="MAPPING"]/elementValue')
    i = 0
    while i < len(mapping_elements):
        entry = mapping_elements[i]
        ref = entry.get('elementRef', '')
        value = entry.get('value', '')

        if ref == 'SCHEMA_COLUMN':
            column_name = value
            xpath_expr = ''
            get_nodes = False

            # Next entry should be QUERY
            if i + 1 < len(mapping_elements):
                next_entry = mapping_elements[i + 1]
                if next_entry.get('elementRef', '') == 'QUERY':
                    xpath_expr = next_entry.get('value', '')
                    i += 1

            # Next entry should be NODECHECK
            if i + 1 < len(mapping_elements):
                next_entry = mapping_elements[i + 1]
                if next_entry.get('elementRef', '') == 'NODECHECK':
                    get_nodes = next_entry.get('value', 'false').lower() == 'true'
                    i += 1

            component['config']['mapping'].append({
                'column': 'SCHEMA_COLUMN',
                'xpath': column_name,
                'query_xpath': xpath_expr,
                'get_nodes': get_nodes
            })

        i += 1

    # Parse remaining parameters
    component['config']['limit'] = get_param('LIMIT', '-1')
    component['config']['die_on_error'] = get_param('DIE_ON_ERROR', 'false').lower() == 'true'
    component['config']['encoding'] = get_param('ENCODING', 'UTF-8')
    component['config']['ignore_ns'] = get_param('IGNORE_NS', 'false').lower() == 'true'
    component['config']['ignore_dtd'] = get_param('IGNORE_DTD', 'false').lower() == 'true'
    component['config']['generation_mode'] = get_param('GENERATION_MODE', 'Dom4j')
    component['config']['validate_date'] = get_param('VALIDATE_DATE', 'false').lower() == 'true'

    # Build output schema from metadata with actual types
    output_schema = []
    for metadata_node in node.findall('./metadata[@connector="FLOW"]'):
        for column in metadata_node.findall('./column'):
            col_type = column.get('type', 'id_String')
            output_schema.append({
                'name': column.get('name', ''),
                'type': self.expr_converter.convert_type(col_type),
                'nullable': column.get('nullable', 'true').lower() == 'true',
                'key': column.get('key', 'false').lower() == 'true',
                'length': int(column.get('length', '-1')),
                'precision': int(column.get('precision', '-1'))
            })
    component['schema']['output'] = output_schema

    return component
```

---

## Appendix L: extract_value() Fix for Attribute XPaths

```python
def extract_value(node_or_nodes) -> str:
    """
    Extract text value from XML node(s).

    Handles:
    - Element nodes: returns .text or serialized attributes
    - String values (from @attr XPaths): returns string directly
    - Lists: takes first element and recurses
    - Empty/falsy input: returns ""
    """
    if not node_or_nodes:
        return ""
    if isinstance(node_or_nodes, list):
        if not node_or_nodes:
            return ""
        node = node_or_nodes[0]
    else:
        node = node_or_nodes

    # Handle string results (from attribute XPaths)
    if isinstance(node, str):
        return node.strip()

    if isinstance(node, ET.Element):
        txt = (node.text or "").strip()
        if txt:
            return txt
        if node.attrib:
            return " ".join(f"{k}={v}" for k, v in node.attrib.items())
        return ""
    else:
        return str(node)
```

**Key change**: Added `isinstance(node, str)` check before the Element check. This correctly handles attribute XPath results (which are strings, not Elements) by returning the string value directly instead of falling through to `str(node_or_nodes)` which would stringify the original list.

---

## Appendix M: Loop XPath Normalization Walkthrough

The `_parse_xml()` method performs aggressive normalization on the loop XPath query. This section walks through the transformation step by step for different input patterns, highlighting where the normalization diverges from Talend behavior.

### Example 1: Standard absolute path

| Step | Value | Code Line |
|------|-------|-----------|
| Input | `"/root/items/item"` | config |
| After quote strip | `"/root/items/item"` | 304-305 |
| After clean quote strip | `/root/items/item` | 407 |
| After leading `/` strip | `root/items/item` | 408-409 |
| Root local detection | `root` (from `root.tag`) | 411-415 |
| After root prefix strip | `items/item` | 418-419 |
| After `.//` prepend | `.//items/item` | 420-421 |
| After base extraction | base=`".//"`  remainder=`"items/item"` | 423-426 |
| After namespace qualify | `.//ns0:items/ns0:item` | 428 |
| **Result** | `.//ns0:items/ns0:item` | |
| **Talend equivalent** | `/ns0:root/ns0:items/ns0:item` | |
| **Behavioral diff** | `.//` matches at ANY depth. Talend's `/root/items/item` only matches the specific absolute path. If another `items/item` exists elsewhere in the document, V1 would match it but Talend would not. |

### Example 2: Descendant-or-self axis

| Step | Value | Code Line |
|------|-------|-----------|
| Input | `"//item"` | config |
| After clean quote strip | `//item` | 407 |
| After leading `/` strip | `/item` | 408-409 |
| Does NOT start with root local | (skip) | 418-419 |
| After `.//` prepend | `.///item` | 420-421 |
| After base extraction | base=`".//"` remainder=`"/item"` | 423-426 |
| **Result** | `.///ns0:item` | |
| **Problem** | Triple-slash `///` is invalid XPath. Should be `.//ns0:item`. The leading `/` from the original `//item` is not stripped after the `.//` prepend. |

### Example 3: Relative path (no leading slash)

| Step | Value | Code Line |
|------|-------|-----------|
| Input | `"items/item"` | config |
| After clean quote strip | `items/item` | 407 |
| No leading `/` | (skip) | 408-409 |
| Does NOT start with root local (depends on root tag) | (skip if root is not `items`) | 418-419 |
| After `.//` prepend | `.//items/item` | 420-421 |
| After namespace qualify | `.//ns0:items/ns0:item` | 428 |
| **Result** | `.//ns0:items/ns0:item` | |
| **Talend equivalent** | `items/item` (relative from root) | |
| **Behavioral diff** | `.//` matches at any depth. Talend's relative path means "from document root". If `items` only exists as a direct child of root, this works correctly. If it exists at other depths, V1 would produce extra matches. |

### Summary of Normalization Issues

| Pattern | V1 Transforms To | Correct Transform | Risk |
|---------|-------------------|-------------------|------|
| `/root/items/item` | `.//ns0:items/ns0:item` | `ns0:items/ns0:item` (relative from root) | Medium -- extra matches if nested `items/item` exists |
| `//item` | `.///ns0:item` (invalid) | `.//ns0:item` | High -- invalid XPath may error or produce unexpected results |
| `items/item` | `.//ns0:items/ns0:item` | `ns0:items/ns0:item` | Medium -- same depth matching issue |
| `./items/item` | `.//./ns0:items/ns0:item` | `ns0:items/ns0:item` | High -- `.//./` is valid but changes semantics |

---

## Appendix N: Namespace Handling Deep Dive

### How Talend Handles Namespaces

Talend provides two approaches for namespace handling:

1. **`IGNORE_NS=true`**: Creates a temporary copy of the XML file with all namespace declarations and prefixes stripped. The resulting file has no namespace information. XPath expressions use plain element names (e.g., `item` instead of `ns:item`).

2. **`IGNORE_NS=false`**: XPath expressions must account for namespaces. Talend's Dom4j parser resolves namespace prefixes against the document's `xmlns` declarations. Users write XPath with the document's namespace prefixes (e.g., `soap:Body/ns1:Response/ns1:item`).

### How V1 Handles Namespaces

V1 takes a third approach: **automatic namespace detection and qualification**.

1. `normalize_nsmaps()` reads the root element's tag to extract namespace URI
2. The namespace is registered under a synthetic prefix `ns0`
3. `qualify_xpath()` adds `ns0:` prefix to all element names in XPath expressions
4. `findall()` is called with the `namespaces={'ns0': uri}` parameter

### Limitations of V1 Approach

| Limitation | Description | Impact |
|------------|-------------|--------|
| Single namespace only | Only the root element's namespace is detected. Elements in other namespaces (e.g., SOAP envelope vs body) are missed. | High for multi-namespace docs |
| No prefix mapping | Talend users write XPath with the document's prefixes (`soap:Body`). V1 replaces all prefixes with `ns0:`. If the document uses multiple prefixes, the mapping is wrong. | High for documents with multiple declared prefixes |
| No `IGNORE_NS` in tabular mode | Even when `ignore_ns=true`, tabular mode does not strip namespaces. It always attempts automatic qualification. | Medium -- config is silently ignored |
| Synthetic prefix | The `ns0:` prefix is synthetic and may conflict with actual `ns0:` prefixes in the document (unlikely but possible). | Low |
| No wildcard namespace | ElementTree supports `{*}element` syntax for any namespace, but V1 does not use it. This could be a simpler approach for `IGNORE_NS=true` scenarios. | Missed opportunity |

### Recommended Namespace Fix

For `IGNORE_NS=true` (most common production scenario):
```python
# Use ElementTree's namespace wildcard syntax
def strip_namespace_from_xpath(expr: str) -> str:
    """Replace element names with wildcard namespace match."""
    parts = expr.split('/')
    result = []
    for p in parts:
        if p in ('.', '..') or p.startswith('@') or ':' in p or p == '':
            result.append(p)
        else:
            result.append(f'{{*}}{p}')  # Match any namespace
    return '/'.join(result)
```

For `IGNORE_NS=false` with multiple namespaces:
```python
def collect_all_namespaces(root: ET.Element) -> Dict[str, str]:
    """Collect all namespace declarations from entire document."""
    namespaces = {}
    for elem in root.iter():
        # Extract namespace from tag
        if '}' in elem.tag:
            uri = elem.tag[elem.tag.find('{') + 1:elem.tag.find('}')]
            prefix = f'ns{len(namespaces)}'
            if uri not in namespaces.values():
                namespaces[prefix] = uri
        # Extract namespace from attributes
        for attr_name in elem.attrib:
            if '}' in attr_name:
                uri = attr_name[attr_name.find('{') + 1:attr_name.find('}')]
                if uri not in namespaces.values():
                    prefix = f'ns{len(namespaces)}'
                    namespaces[prefix] = uri
    return namespaces
```

---

## Appendix O: Passthrough Mode vs Tabular Mode Decision Matrix

| Condition | Mode Selected | Correct? | Notes |
|-----------|---------------|----------|-------|
| `config.mode == 'xml_passthrough'` | Passthrough | Yes | Explicit passthrough request honored |
| `config.mode == 'tabular'` | Tabular | Yes | Explicit tabular request honored |
| `config.mode` not set, schema has 0 columns | Tabular (fallback) | Uncertain | No columns to extract -- should probably error or warn |
| `config.mode` not set, schema has 1 column | **Passthrough** | **NO** | Single-column tabular extraction incorrectly returns full XML. See BUG-FIX-006. |
| `config.mode` not set, schema has 2+ columns | Tabular | Yes | Standard tabular extraction |
| `config.mode` not set, no schema at all | Tabular (fallback) | Uncertain | No schema means no XPath mapping -- produces empty rows |

**Root cause**: The single-column heuristic (line 335-336) was added to support XMLMap workflows where `tFileInputXML` feeds raw XML to `tXMLMap`. In this pattern, the component has a single output column (e.g., `xml_content`) and the downstream `tXMLMap` handles the actual extraction. However, this heuristic is too broad -- it catches ALL single-column schemas, not just XMLMap preprocessing schemas.

**Recommended fix**: Remove the heuristic entirely. Require explicit `mode='xml_passthrough'` configuration. The converter should detect XMLMap downstream connections and set this flag explicitly.

---

## Appendix P: Complete Test Sample XML Files

### Test File 1: Basic (test_basic.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <items>
    <item>
      <id>1</id>
      <name>Widget A</name>
      <price>9.99</price>
    </item>
    <item>
      <id>2</id>
      <name>Widget B</name>
      <price>19.99</price>
    </item>
    <item>
      <id>3</id>
      <name>Widget C</name>
      <price>29.99</price>
    </item>
  </items>
</root>
```

**Expected output** with loop `/root/items/item` and columns `id`, `name`, `price`:

| id | name | price |
|----|------|-------|
| 1 | Widget A | 9.99 |
| 2 | Widget B | 19.99 |
| 3 | Widget C | 29.99 |

### Test File 2: Namespaced (test_namespace.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root xmlns="http://example.com/ns1">
  <items>
    <item id="A1">
      <name>Widget A</name>
    </item>
  </items>
</root>
```

**Expected behavior**: With `IGNORE_NS=false`, the engine should auto-detect the namespace and qualify XPaths. With `IGNORE_NS=true`, namespace should be stripped.

### Test File 3: Parent Navigation (test_parent.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <header>
    <batch_date>2024-01-15</batch_date>
  </header>
  <items>
    <item>
      <id>1</id>
      <name>Widget A</name>
    </item>
  </items>
</root>
```

**Expected behavior** with loop `/root/items/item` and column XPath `../../header/batch_date`:

| id | name | batch_date |
|----|------|------------|
| 1 | Widget A | 2024-01-15 |

### Test File 4: Multiple Namespaces (test_multi_ns.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns1="http://example.com/api">
  <soap:Body>
    <ns1:Response>
      <ns1:Item>
        <ns1:Id>1</ns1:Id>
        <ns1:Name>Widget A</ns1:Name>
      </ns1:Item>
    </ns1:Response>
  </soap:Body>
</soap:Envelope>
```

**Expected behavior**: Should be able to extract data from `ns1:Item` elements even though root is in SOAP namespace. Currently FAILS because V1 only detects the SOAP namespace from the root element.

### Test File 5: Attributes (test_attributes.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <item id="1" type="widget">
    <name>Widget A</name>
  </item>
  <item id="2" type="gadget">
    <name>Gadget B</name>
  </item>
</root>
```

**Expected output** with loop `/root/item` and columns `@id`, `@type`, `name`:

| id | type | name |
|----|------|------|
| 1 | widget | Widget A |
| 2 | gadget | Gadget B |

**Current V1 issue**: `extract_value()` bug (BUG-FIX-016) will return `"['1']"` instead of `"1"` for attribute XPaths. Additionally, bare `@attr` XPaths fail entirely due to ElementTree `SyntaxError` (ENG-FIX-012), returning empty string before `extract_value()` is even reached.
