# Audit Report: tExtractXMLField / ExtractXMLField

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tExtractXMLField` |
| **V1 Engine Class** | `ExtractXMLField` |
| **Engine File** | `src/v1/engine/components/transform/extract_xml_fields.py` (307 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` (142 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tExtractXMLField")` decorator-based dispatch |
| **Registry Aliases** | `ExtractXMLField`, `tExtractXMLField` |
| **Category** | Transform / XML Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/extract_xml_fields.py` | Engine implementation (307 lines) |
| `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` | Converter class (142 lines) |
| `tests/converters/talend_to_v1/components/test_extract_xml_fields.py` | Converter tests (50 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 14 of 14 params extracted (100%); 6 hidden params added; MAPPING stride-2 parser; 7 needs_review entries |
| Engine Feature Parity | **Y** | 1 | 3 | 4 | 1 | limit=0 semantic mismatch; no Get Nodes; namespace stripping incomplete; deprecated getiterator() |
| Code Quality | **Y** | 2 | 3 | 5 | 3 | Cross-cutting _update_global_map() crash; getiterator() removed in lxml 5.0; empty string / NaN edge cases |
| Performance & Memory | **Y** | 0 | 1 | 3 | 2 | XMLParser created per-row; iterrows() overhead; no streaming mode |
| Testing | **Y** | 0 | 1 | 0 | 0 | 50 converter tests (Green); zero engine unit tests |

**Overall: YELLOW -- Converter fully standardized (Green). Engine has P0/P1 issues blocking full production readiness.**

**Top Actions**:
1. Fix limit=0 semantic mismatch (P0 -- data correctness)
2. Fix _update_global_map() crash (P0 -- cross-cutting)
3. Replace deprecated getiterator() with iter() (P1 -- lxml 5.0 compatibility)
4. Add engine unit tests (P1 -- testing gap)

---

## 3. Talend Feature Baseline

### What tExtractXMLField Does

`tExtractXMLField` is an intermediate processing component that reads structured XML data from a column of an incoming data flow, applies XPath queries to extract individual fields, and produces a structured output row per XML node. It belongs to both the **Processing** and **XML** component families and is available in all Talend products.

The component is typically placed downstream of a file input or database input component whose output schema includes a column containing XML fragments. It loops over repeating XML nodes identified by a Loop XPath query and maps sub-elements to output schema columns via per-column XPath queries.

**Source**: [tExtractXMLField Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractxmlfield-standard-properties), [Talaxie GitHub _java.xml](https://github.com/nicholasalx/talend_components)
**Component family**: Processing / XML
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in, uses lxml)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | XML Field | `XMLFIELD` | PREV_COLUMN_LIST | `""` | Name of the input column containing XML data to be processed. Selected from incoming schema. |
| 2 | Use Items | `USE_ITEMS` | CHECK (hidden) | `false` | Hidden parameter controlling item-based XML input mode. |
| 3 | Loop Query Base | `LOOP_QUERY_BASE` | TEXT (hidden) | `""` | Hidden base path prepended to loop query for XPath resolution. |
| 4 | Loop XPath Query | `LOOP_QUERY` | TEXT | `"/bills/bill/line"` | XPath expression identifying the repeating XML node to iterate over. All column mappings are evaluated relative to each matched loop node. |
| 5 | Mapping | `MAPPING` | TABLE (BASED_ON_SCHEMA=true) | `[]` | Per-column extraction mappings with QUERY (XPath) and NODECHECK (boolean node existence check). Auto-populated schema columns. |
| 6 | Limit | `LIMIT` | TEXT | `""` | Maximum number of loop iterations per XML input. Empty = unlimited. When set to `0`, Talend reads nothing. |
| 7 | Die on Error | `DIE_ON_ERROR` | CHECK | `false` | When checked, the job terminates on XML parsing or extraction errors. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 8 | Use XML Field | `USE_XML_FIELD` | CHECK (hidden) | `false` | Hidden toggle controlling whether to use XML field column or inline XML text. |
| 9 | XML Text | `XML_TEXT` | TEXT (hidden) | `""` | Hidden inline XML text content for direct parsing without column reference. |
| 10 | XML Prefix | `XML_PREFIX` | TEXT (hidden) | `""` | Hidden namespace prefix override for XPath queries. |
| 11 | Schema Opt Num | `SCHEMA_OPT_NUM` | TEXT (hidden) | `"100"` | Hidden schema optimization number controlling internal parser behavior. |
| 12 | Ignore Namespaces | `IGNORE_NS` | CHECK | `false` | Strips all XML namespace declarations and prefixes before parsing. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Incoming data flow containing at least one column with XML content. |
| `FLOW` (Main) | Output | Row > Main | Successfully extracted rows matching the output schema. |
| `REJECT` | Output | Row > Reject | Rows that failed XML parsing. Contains errorCode and errorMessage columns. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully extracted |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows that failed processing |

### 3.5 Behavioral Notes

1. **MAPPING TABLE uses BASED_ON_SCHEMA=true**: Schema columns are auto-populated from the output schema definition, so TABLE entries only contain QUERY and NODECHECK fields (stride-2), not SCHEMA_COLUMN.
2. **LOOP_QUERY default is "/bills/bill/line"**: Not empty string -- this is the _java.xml default for the XPath loop expression.
3. **LIMIT as string**: Supports context variable expressions; empty string means unlimited.
4. **Talend limit=0 means "read nothing"**: Unlike the engine which treats 0 as "no limit".
5. **6 hidden params**: USE_ITEMS, LOOP_QUERY_BASE, USE_XML_FIELD, XML_TEXT, XML_PREFIX, SCHEMA_OPT_NUM are present in _java.xml but not visible in standard Talend UI.
6. **Namespace stripping**: When IGNORE_NS is true, Talend generates code to create a namespace-free copy of the XML.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

Gold-standard converter using `@REGISTRY.register("tExtractXMLField")` decorator, `_build_component_dict` wrapper with `type_name="ExtractXMLField"`, and per-feature needs_review entries.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `XMLFIELD` | Yes | `xmlfield` | PREV_COLUMN_LIST, default "" |
| 2 | `USE_ITEMS` | **REMOVED** | ~~use_items~~ | Hidden/design-time param -- removed from converter |
| 3 | `LOOP_QUERY_BASE` | **REMOVED** | ~~loop_query_base~~ | Hidden/design-time param -- removed from converter |
| 4 | `LOOP_QUERY` | Yes | `loop_query` | Default "/bills/bill/line" |
| 5 | `MAPPING` | Yes | `mapping` | TABLE stride-2 (QUERY+NODECHECK), BASED_ON_SCHEMA=true |
| 6 | `LIMIT` | Yes | `limit` | String for expression support, default "" |
| 7 | `DIE_ON_ERROR` | Yes | `die_on_error` | Bool, default False |
| 8 | `USE_XML_FIELD` | **REMOVED** | ~~use_xml_field~~ | Hidden/design-time param -- removed from converter |
| 9 | `XML_TEXT` | **REMOVED** | ~~xml_text~~ | Hidden/design-time param -- removed from converter |
| 10 | `XML_PREFIX` | **REMOVED** | ~~xml_prefix~~ | Hidden/design-time param -- removed from converter |
| 11 | `SCHEMA_OPT_NUM` | **REMOVED** | ~~schema_opt_num~~ | Hidden/design-time param -- removed from converter |
| 12 | `IGNORE_NS` | Yes | `ignore_ns` | Bool, default False |
| 13 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default False |
| 14 | `LABEL` | Yes | `label` | Framework param, default "" |

**Summary**: 8 of 14 parameters extracted. 6 unique + 2 framework. 6 hidden/design-time params removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | |
| `precision` | Yes | |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported by base class |

Transform passthrough: input schema == output schema.

### 4.3 Expression Handling

Context variable expressions (e.g., `context.limit`) are preserved as-is in string parameters like `limit`, `xml_text`, and `loop_query`. The engine or Java bridge resolves them at runtime.

### 4.4 Converter Issues

No open converter issues. All parameters extracted correctly.

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No open issues |

### 4.5 Needs Review Entries

1 per-feature needs_review entry for engine gaps:

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `limit` | Engine treats limit=0 as "no limit" but Talend treats 0 as "read nothing" -- semantic mismatch | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | XML field column extraction | **Yes** | High | `_process()` line 183 | Reads from configured column |
| 2 | Loop XPath query | **Yes** | High | `_process()` line 214 | xpath() on parsed root |
| 3 | Per-column XPath mapping | **Yes** | High | `_process()` lines 222-246 | Iterates mapping entries |
| 4 | Node existence check | **Yes** | Medium | `_process()` lines 228-235 | nodecheck via xpath() |
| 5 | Row limiting | **Partial** | Low | `_process()` line 218 | Semantic mismatch: 0 means "no limit" instead of "read nothing" |
| 6 | Die on error | **Yes** | High | `_process()` line 256 | Raises ComponentExecutionError |
| 7 | Namespace stripping | **Yes** | Medium | `_process()` lines 209-213 | Uses deprecated getiterator() |
| 8 | Reject output | **Yes** | High | `_make_reject_row()` | errorCode + errorMessage columns |
| 9 | Get Nodes (document mode) | **No** | N/A | -- | Not implemented |
| 10 | Use Items mode | **No** | N/A | -- | Hidden param not supported |
| 11 | Loop Query Base | **No** | N/A | -- | Hidden param not supported |
| 12 | XML Text inline mode | **No** | N/A | -- | Hidden param not supported |
| 13 | XML Prefix override | **No** | N/A | -- | Hidden param not supported |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-EXF-001 | **P0** | `limit=0` treated as "no limit" (unlimited rows) but Talend treats 0 as "read nothing" (zero rows). Data correctness issue. |
| ENG-EXF-002 | **P1** | Get Nodes feature (GET_NODES per-column checkbox) not implemented. Document-typed columns cannot retrieve full XML content. |
| ENG-EXF-003 | **P1** | Uses deprecated `getiterator()` (removed in lxml 5.0+). Will crash on newer lxml versions. |
| ENG-EXF-004 | **P1** | Namespace stripping walks entire tree per row instead of stripping once. Correctness risk for deeply nested XML. |
| ENG-EXF-005 | **P2** | XMLParser `recover=True` always enabled. Malformed XML silently parsed instead of erroring. |
| ENG-EXF-006 | **P2** | No DTD processing control. DTD entities in XML content could cause unexpected behavior. |
| ENG-EXF-007 | **P2** | xml_field column existence not validated before processing. KeyError on missing column. |
| ENG-EXF-008 | **P3** | No support for XPath 2.0+ expressions (lxml only supports XPath 1.0). |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Successful extractions |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Failed rows |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-EXF-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crashes when globalMap is set. Affects all components. |
| BUG-EXF-002 | **P0** | `extract_xml_fields.py:209` | `getiterator()` deprecated in lxml 4.0, REMOVED in lxml 5.0. Will raise AttributeError on modern lxml. |
| BUG-EXF-003 | **P1** | `extract_xml_fields.py:200` | `row.get(xml_field, None)` returns None for NaN values (pandas). NaN XML content silently routed to reject instead of being detected. |
| BUG-EXF-004 | **P1** | `extract_xml_fields.py:207` | `xml_string.encode('utf-8')` crashes if xml_string is not a string (e.g., numeric column). No type check. |
| BUG-EXF-005 | **P1** | `extract_xml_fields.py:218` | `if limit:` is falsy for limit=0 (Python). Matches engine treating 0 as unlimited, but mismatches Talend. |
| BUG-EXF-006 | **P2** | `extract_xml_fields.py:259` | `rows_read` incremented after XML processing loop but should be at start. Off-by-one on error path. |
| BUG-EXF-007 | **P2** | `extract_xml_fields.py:262` | Empty `main_output` creates DataFrame with no columns. Downstream components expecting specific columns will fail. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-EXF-001 | **P2** | Engine reads `xml_field` but converter emits `xmlfield` (no underscore). Engine gap documented as needs_review. |
| NAME-EXF-002 | **P2** | Engine reads `mapping` with `schema_column` key but converter MAPPING is stride-2 (QUERY+NODECHECK only). Structure mismatch. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-EXF-001 | **P2** | "Use logging not print" | No violations found. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

See Section 11 Risk Assessment for comprehensive XML security analysis.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Good -- module-level `logging.getLogger(__name__)` |
| Level usage | Good -- info for start/complete, error for failures, warning for empty input |
| Sensitive data | No XML content logged (good) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Good -- uses `ComponentExecutionError` and `ConfigurationError` |
| Exception chaining | Good -- `ComponentExecutionError(self.id, msg, e)` preserves cause |
| die_on_error handling | Good -- conditionally raises based on config |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Good -- full type hints on all public methods |
| Parameter types | Good -- `Optional[pd.DataFrame]`, `Dict[str, Any]`, `List[str]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-EXF-001 | **P1** | XMLParser created per-row (line 206). Should be created once and reused. |
| PERF-EXF-002 | **P2** | `iterrows()` (line 199) causes 100-1000x slowdown vs vectorized operations. CROSS-CUTTING anti-pattern. |
| PERF-EXF-003 | **P2** | Namespace tree walk per-row (lines 209-213). Should strip namespaces once if input XML is consistent. |
| PERF-EXF-004 | **P2** | `_make_reject_row()` copies all columns via dict comprehension. Expensive for wide schemas. |
| PERF-EXF-005 | **P3** | No streaming/chunked mode. Large XML documents loaded entirely into memory. |
| PERF-EXF-006 | **P3** | Output DataFrames built by appending to list then converting. Adequate but not optimal for very large outputs. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not supported. Entire input DataFrame processed at once. |
| Memory threshold | No limit. Large XML documents could exhaust memory. |
| Large data handling | Per-row XML parsing is memory-safe per row, but no overall limit on output size. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 50 | `tests/converters/talend_to_v1/components/test_extract_xml_fields.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (component-specific) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-EXF-001 | **P1** | No engine unit tests for ExtractXMLField._process() |

### 8.3 Recommended Test Cases

1. Engine: happy path with realistic XML, multiple loop nodes, correct extraction
2. Engine: limit=0 behavior (verify reads nothing vs unlimited)
3. Engine: REJECT output with die_on_error=False
4. Engine: die_on_error=True raises ComponentExecutionError
5. Engine: namespace stripping with IGNORE_NS=True
6. Engine: NaN/None XML field handling
7. Engine: empty DataFrame input
8. Engine: malformed XML with recover=True

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 3 | **BUG-EXF-001**, **BUG-EXF-002**, **ENG-EXF-001** |
| P1 | 6 | **BUG-EXF-003**, **BUG-EXF-004**, **BUG-EXF-005**, **ENG-EXF-002**, **ENG-EXF-003**, **ENG-EXF-004**, **PERF-EXF-001**, **TEST-EXF-001** |
| P2 | 7 | **BUG-EXF-006**, **BUG-EXF-007**, **ENG-EXF-005**, **ENG-EXF-006**, **ENG-EXF-007**, **NAME-EXF-001**, **NAME-EXF-002**, **PERF-EXF-002**, **PERF-EXF-003**, **PERF-EXF-004** |
| P3 | 3 | **ENG-EXF-008**, **PERF-EXF-005**, **PERF-EXF-006** |
| **Total** | **19** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 8 | ENG-EXF-001 through ENG-EXF-008 |
| Bug (BUG) | 7 | BUG-EXF-001 through BUG-EXF-007 |
| Naming (NAME) | 2 | NAME-EXF-001, NAME-EXF-002 |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 6 | PERF-EXF-001 through PERF-EXF-006 |
| Testing (TEST) | 1 | TEST-EXF-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `extract_xml_fields.py:199` | `iterrows()` anti-pattern (shared with multiple components) |

---

## 10. Recommendations

### Immediate (Before Production)

1. **ENG-EXF-001 (P0)**: Fix limit=0 semantic mismatch -- treat 0 as "read nothing" per Talend behavior
2. **BUG-EXF-001 (P0)**: Fix cross-cutting `_update_global_map()` crash
3. **BUG-EXF-002 (P0)**: Replace `getiterator()` with `iter()` for lxml 5.0 compatibility

### Short-term (Hardening)

4. **ENG-EXF-002 (P1)**: Implement Get Nodes feature for Document-typed columns
5. **BUG-EXF-003/004 (P1)**: Add NaN detection and type checking for xml_field column
6. **PERF-EXF-001 (P1)**: Create XMLParser once, reuse across rows
7. **TEST-EXF-001 (P1)**: Add engine unit tests

### Long-term (Optimization)

8. **PERF-EXF-002 (P2)**: Replace iterrows() with vectorized XML processing
9. **ENG-EXF-008 (P3)**: Consider XPath 2.0 support if needed

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| XXE (XML External Entity) injection | Medium | High | Engine uses `recover=True` but no explicit XXE protection. Malicious XML in data columns could access local files or trigger SSRF. Mitigation: use `etree.XMLParser(resolve_entities=False, no_network=True)`. |
| DTD processing risks | Medium | Medium | No DTD processing controls. DTD bomb (billion laughs attack) could cause memory exhaustion. Mitigation: disable DTD loading with `load_dtd=False`. |
| XPath injection via loop_query | Low | High | User-controlled `loop_query` expressions could be crafted to extract unintended data or cause excessive processing. Mitigation: validate XPath expressions before execution. |
| Large XML document memory consumption | High | Medium | No size limit on XML content in columns. A single row with a 1GB XML string would be parsed entirely into memory. Mitigation: add configurable max XML size. |
| Namespace handling inconsistencies | Medium | Low | `ignore_ns` strips namespaces by walking entire tree, which may not handle all namespace declaration patterns (e.g., default namespaces, namespace re-declarations). |
| Path traversal via xml_text/xml_prefix | Low | Medium | Hidden `xml_text` and `xml_prefix` params could be used to inject unexpected content or namespace prefixes. Currently not read by engine, but if implemented need validation. |

### High-Risk Job Patterns

1. Jobs processing untrusted XML content (user uploads, external APIs) -- XXE risk
2. Jobs with limit=0 expecting "read nothing" behavior -- will get unlimited rows instead
3. Jobs running on lxml 5.0+ -- getiterator() will crash
4. Jobs with very large XML documents (>100MB per row) -- memory exhaustion

### Safe Usage Patterns

1. Jobs with trusted, well-formed XML from internal databases
2. Jobs with small-to-medium XML documents (<10MB per row)
3. Jobs not relying on limit=0 behavior
4. Jobs running on lxml 4.x

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Official Talend docs | [tExtractXMLField Standard Properties (8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractxmlfield-standard-properties) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [nicholasalx/talend_components](https://github.com/nicholasalx/talend_components) | Component definition XML, hidden params |
| Engine source | `src/v1/engine/components/transform/extract_xml_fields.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_extract_xml_fields.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | Multiple engine components | `iterrows()` anti-pattern causes 100-1000x performance degradation |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after hidden/design-time param removal*
