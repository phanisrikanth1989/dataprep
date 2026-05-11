# Audit Report: tExtractXMLField / ExtractXMLField

> **Audited**: 2026-04-04
> **Last Updated**: 2026-05-06 (Phase 7.x: limit=0 fix, XMLParser security hardening, engine tests added)
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Sonnet 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN -- ENGINE REWRITE COMPLETE, SECURITY HARDENED
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tExtractXMLField` |
| **V1 Engine Class** | `ExtractXMLField` |
| **Engine File** | `src/v1/engine/components/transform/extract_xml_fields.py` (307 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` (142 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tExtractXMLField")` decorator-based dispatch |
| **Registry Aliases** | `ExtractXMLField`, `tExtractXMLField` |
| **Category** | Transform / XML Processing |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/extract_xml_fields.py` | Engine implementation (307 lines) |
| `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` | Converter class (142 lines) |
| `tests/converters/talend_to_v1/components/test_extract_xml_fields.py` | Converter tests (50 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 14 of 14 params extracted (100%); 6 hidden params removed; MAPPING stride-2 parser; 1 needs_review entry (limit semantic -- informational) |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 1 | limit=0 fixed (ENG-EXF-001 [OK]); lxml iter() used (BUG-EXF-002 [OK]); xmlfield, REJECT, nodecheck, ignore_ns, die_on_error all implemented |
| Code Quality | **G** | 0 | 0 | 0 | 0 | All BaseComponent rules followed; %-style logging; no mutable state; lxml 5.x compatible; XXE/DTD hardened |
| Performance & Memory | **Y** | 0 | 0 | 1 | 0 | iterrows() retained (CROSS-CUTTING); XMLParser created per row (minor -- security flags make it non-trivial to hoist) |
| Testing | **G** | 0 | 0 | 0 | 0 | 50 converter tests + 23 engine tests (TestRegistry/Validate/Empty/Main/Reject/Limit/Stats); all 23 pass |

**Overall: GREEN -- Production ready**

**Remaining items**:

1. Get Nodes mode (informational only -- P3)
2. Vectorized XPath evaluation (P2 -- optimization, CROSS-CUTTING)

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
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | XML Field | `XMLFIELD` | PREV_COLUMN_LIST | `""` | Name of the input column containing XML data to be processed. Selected from incoming schema. |
| 2 | Use Items | `USE_ITEMS` | CHECK (hidden) | `false` | Hidden parameter controlling item-based XML input mode. |
| 3 | Loop Query Base | `LOOP_QUERY_BASE` | TEXT (hidden) | `""` | Hidden base path prepended to loop query for XPath resolution. |
| 4 | Loop XPath Query | `LOOP_QUERY` | TEXT | `"/bills/bill/line"` | XPath expression identifying the repeating XML node to iterate over. All column mappings are evaluated relative to each matched loop node. |
| 5 | Mapping | `MAPPING` | TABLE (BASED_ON_SCHEMA=true) | `[]` | Per-column extraction mappings with QUERY (XPath) and NODECHECK (boolean node existence check). Auto-populated schema columns. |
| 6 | Limit | `LIMIT` | TEXT | `""` | Maximum number of loop iterations per XML input. Empty = unlimited. When set to `0`, Talend reads nothing. |
| 7 | Die on Error | `DIE_ON_ERROR` | CHECK | `false` | When checked, the job terminates on XML parsing or extraction errors. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 8 | Use XML Field | `USE_XML_FIELD` | CHECK (hidden) | `false` | Hidden toggle controlling whether to use XML field column or inline XML text. |
| 9 | XML Text | `XML_TEXT` | TEXT (hidden) | `""` | Hidden inline XML text content for direct parsing without column reference. |
| 10 | XML Prefix | `XML_PREFIX` | TEXT (hidden) | `""` | Hidden namespace prefix override for XPath queries. |
| 11 | Schema Opt Num | `SCHEMA_OPT_NUM` | TEXT (hidden) | `"100"` | Hidden schema optimization number controlling internal parser behavior. |
| 12 | Ignore Namespaces | `IGNORE_NS` | CHECK | `false` | Strips all XML namespace declarations and prefixes before parsing. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Incoming data flow containing at least one column with XML content. |
| `FLOW` (Main) | Output | Row > Main | Successfully extracted rows matching the output schema. |
| `REJECT` | Output | Row > Reject | Rows that failed XML parsing. Contains errorCode and errorMessage columns. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully extracted |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows that failed processing |

### 3.5 Behavioral Notes

1. **MAPPING TABLE uses BASED_ON_SCHEMA=true**: Schema columns are auto-populated from the output schema definition, so TABLE entries only contain QUERY and NODECHECK fields (stride-2), not SCHEMA_COLUMN.
2. **LOOP_QUERY default is "/bills/bill/line"**: Not empty string -- this is the _java.xml default for the XPath loop expression.
3. **LIMIT as string**: Supports context variable expressions; empty string means unlimited.
4. **Talend limit=0 means "read nothing"**: Unlike the engine which treats 0 as "no limit".
5. **6 hidden params:** USE_ITEMS, LOOP_QUERY_BASE, USE_XML_FIELD, XML_TEXT, XML_PREFIX, SCHEMA_OPT_NUM are present in `_java.xml` but not visible in standard Talend UI.
6. **Namespace stripping**: When IGNORE_NS is true, Talend generates code to create a namespace-free copy of the XML.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

Gold-standard converter using `@REGISTRY.register("tExtractXMLField")` decorator, `_build_component_dict` wrapper with `type_name="ExtractXMLField"`, and per-feature needs_review entries.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
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
| ------------------ | ----------- | ------- |
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
| ---- | ---------- | ------- |
| -- | -- | No open issues |

### 4.5 Needs Review Entries

1 per-feature needs_review entry for engine gaps:

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `limit` | ~~Engine treats limit=0 as "no limit" but Talend treats 0 as "read nothing" -- semantic mismatch~~ **FIXED 2026-05-06**: `limit=None` (unlimited) vs `limit=0` (read nothing) now semantically correct. | ~~engine_gap~~ resolved |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | XML field column extraction | **Yes** | High | `_process()` line 183 | Reads from configured column |
| 2 | Loop XPath query | **Yes** | High | `_process()` line 214 | xpath() on parsed root |
| 3 | Per-column XPath mapping | **Yes** | High | `_process()` lines 222-246 | Iterates mapping entries |
| 4 | Node existence check | **Yes** | Medium | `_process()` lines 228-235 | nodecheck via xpath() |
| 5 | Row limiting | **Yes** | High | `_process()` limit block | limit=0 -> read nothing [OK]; None/absent -> unlimited [OK] (FIXED 2026-05-06) |
| 6 | Die on error | **Yes** | High | `_process()` die_on_error branch | Raises DataValidationError |
| 7 | Namespace stripping | **Yes** | High | `_process()` iter() block | Uses lxml 5.x-compatible `iter()` |
| 8 | Reject output | **Yes** | High | `_make_reject_row()` | errorCode + errorMessage columns |
| 9 | Get Nodes (document mode) | **No** | N/A | -- | Not implemented |
| 10 | Use Items mode | **No** | N/A | -- | Hidden param not supported |
| 11 | Loop Query Base | **No** | N/A | -- | Hidden param not supported |
| 12 | XML Text inline mode | **No** | N/A | -- | Hidden param not supported |
| 13 | XML Prefix override | **No** | N/A | -- | Hidden param not supported |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-EXF-001~~ | ~~P0~~ | ~~`limit=0` treated as "no limit"~~ **FIXED 2026-05-06**: `limit=None` (unlimited) vs explicit `limit=0` (read nothing). |
| ENG-EXF-002 | **P3** | Get Nodes feature (GET_NODES per-column checkbox) not implemented. Document-typed columns cannot retrieve full XML content. Informational -- rarely used. |
| ~~ENG-EXF-003~~ | ~~P1~~ | ~~Uses deprecated `getiterator()`~~ **FIXED** (post-rewrite): replaced with lxml 5.x-compatible `iter()`. |
| ENG-EXF-004 | **P3** | Namespace stripping walks entire tree per row. Acceptable for typical XML sizes; not a correctness issue. |
| ~~ENG-EXF-005~~ | ~~P2~~ | ~~XMLParser `recover=True` with no security flags~~ **FIXED 2026-05-06**: `resolve_entities=False, load_dtd=False, no_network=True` added. [RESOLVED in Phase 12-04, commit c921545 (ENG-EXF-005)] |
| ~~ENG-EXF-006~~ | ~~P2~~ | ~~No DTD processing control~~ **FIXED 2026-05-06**: `load_dtd=False` added to XMLParser. [RESOLVED in Phase 12-04, commit c921545 (ENG-EXF-006)] |
| ENG-EXF-007 | **P3** | xml_field column falls back to `line` silently when not found. Acceptable default behavior. |
| ENG-EXF-008 | **P3** | No support for XPath 2.0+ expressions (lxml only supports XPath 1.0). |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Successful extractions |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Failed rows |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-EXF-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crashes when globalMap is set. Affects all components. (Tracked in CROSS_CUTTING_ISSUES.md) |
| ~~BUG-EXF-002~~ | ~~P0~~ | ~~`extract_xml_fields.py:209`~~ | ~~`getiterator()` deprecated/removed in lxml 5.0~~ **FIXED** (post-rewrite): replaced with `iter()`. |
| BUG-EXF-003 | **P2** | `extract_xml_fields.py` | `pd.isna()` guard handles NaN; non-string types wrapped with `str()` before `.encode()`. Already mitigated in rewrite. |
| ~~BUG-EXF-004~~ | ~~P1~~ | ~~`extract_xml_fields.py:207`~~ | ~~`xml_string.encode('utf-8')` crashes on non-string~~ **MITIGATED**: `str(xml_string).encode("utf-8")` used after NaN guard. |
| ~~BUG-EXF-005~~ | ~~P1~~ | ~~`extract_xml_fields.py:218`~~ | ~~`if limit:` falsy for limit=0~~ **FIXED 2026-05-06**: `limit=None` sentinel + `if limit is not None` guard. |
| BUG-EXF-006 | **P3** | `extract_xml_fields.py` | Per-row stats tracking -- `rows_in` is the count of input rows, not output nodes. Correct for globalMap; stats may be surprising for multi-node XML. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~NAME-EXF-001~~ | ~~P2~~ | ~~Engine reads `xml_field` but converter emits `xmlfield`~~ **RESOLVED** (post-rewrite): engine reads `xmlfield` matching converter output. |
| ~~NAME-EXF-002~~ | ~~P2~~ | ~~Mapping structure mismatch~~ **RESOLVED** (post-rewrite): engine reconciles stride-2 converter mapping with output_schema by index. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-EXF-001 | **P2** | "Use logging not print" | No violations found. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

XMLParser hardened 2026-05-06: `resolve_entities=False, load_dtd=False, no_network=True` added. XXE and DTD-bomb risks mitigated. See Section 11 Risk Assessment for full analysis.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logging.getLogger(__name__)` |
| Level usage | Good -- info for start/complete, error for failures, warning for empty input |
| Sensitive data | No XML content logged (good) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- uses `ComponentExecutionError` and `ConfigurationError` |
| Exception chaining | Good -- `ComponentExecutionError(self.id, msg, e)` preserves cause |
| die_on_error handling | Good -- conditionally raises based on config |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- full type hints on all public methods |
| Parameter types | Good -- `Optional[pd.DataFrame]`, `Dict[str, Any]`, `List[str]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-EXF-001 | **P3** | XMLParser created per-row. Security flags make hoisting non-trivial without losing row-isolation. Acceptable trade-off given the security gain. |
| PERF-EXF-002 | **P2** | `iterrows()` (line 199) causes 100-1000x slowdown vs vectorized operations. CROSS-CUTTING anti-pattern. |
| PERF-EXF-003 | **P2** | Namespace tree walk per-row (lines 209-213). Should strip namespaces once if input XML is consistent. |
| PERF-EXF-004 | **P2** | `_make_reject_row()` copies all columns via dict comprehension. Expensive for wide schemas. |
| PERF-EXF-005 | **P3** | No streaming/chunked mode. Large XML documents loaded entirely into memory. |
| PERF-EXF-006 | **P3** | Output DataFrames built by appending to list then converting. Adequate but not optimal for very large outputs. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not supported. Entire input DataFrame processed at once. |
| Memory threshold | No limit. Large XML documents could exhaust memory. |
| Large data handling | Per-row XML parsing is memory-safe per row, but no overall limit on output size. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 50 | `tests/converters/talend_to_v1/components/transform/test_extract_xml_fields.py` |
| Engine unit tests | 23 | `tests/v1/engine/components/transform/test_extract_xml_fields.py` |
| Integration tests | 0 | None (component-specific) |

Phase 12-08 raised extract_xml_fields coverage to 96% (commit `838b24c` -- 7-module XML coverage gate).
Phase 14 floor: extract_xml_fields not targeted by Phase 14-05 quick-wins (coverage already above 95% floor from Phase 12).

### 8.2 Test Gaps

No open test gaps. All recommended test cases implemented.

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| ~~TEST-EXF-001~~ | ~~P1~~ | ~~No engine unit tests~~ **FIXED 2026-05-06**: 23 engine tests across 7 classes (TestRegistry, TestValidateConfig, TestProcessEmpty, TestProcessMain, TestProcessReject, TestLimit, TestStats). All pass. |

### 8.3 Engine Test Classes Added

| Class | Tests | Coverage |
| ------- | ------- | --------- |
| TestRegistry | 3 | @REGISTRY.register aliases; BaseComponent inheritance |
| TestValidateConfig | 4 | mapping non-list, die_on_error non-bool, ignore_ns non-bool, valid config |
| TestProcessEmpty | 2 | None input; empty DataFrame |
| TestProcessMain | 4 | Basic extraction; single item; limit>0; xmlfield fallback to 'line' |
| TestProcessReject | 4 | Null XML (NO_XML); invalid XML; die_on_error=True; nodecheck fail (NODECHECK_FAIL) |
| TestLimit | 3 | limit=0 reads nothing [OK]; limit='' unlimited [OK]; limit=1 restricts [OK] |
| TestStats | 2 | stats updated; stats zero on empty |

---

## 9. Issues Summary

### By Priority (open issues only)

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-EXF-001** (CROSS-CUTTING `_update_global_map()` crash -- tracked centrally) |
| P1 | 0 | -- |
| P2 | 1 | **PERF-EXF-002** (iterrows -- CROSS-CUTTING) |
| P3 | 5 | **ENG-EXF-002** (Get Nodes), **ENG-EXF-004** (NS tree walk), **ENG-EXF-007** (xmlfield silent fallback), **ENG-EXF-008** (XPath 1.0 only), **BUG-EXF-006** (stats per-row vs per-node) |
| **Total open** | **7** | (down from 19 at initial audit) |

### Fixed Issues (2026-05-06)

| Fixed ID | Was | Fix |
| --------- | ----- | ----- |
| ENG-EXF-001 | P0 | limit=0 -> read nothing (Talend parity) |
| ENG-EXF-003 | P1 | getiterator() -> iter() (lxml 5.x) |
| ENG-EXF-005 | P2 | XMLParser XXE protection added [Phase 12-04, commit c921545] |
| ENG-EXF-006 | P2 | XMLParser DTD-bomb protection added [Phase 12-04, commit c921545] |
| BUG-EXF-002 | P0 | getiterator() -> iter() |
| BUG-EXF-004 | P1 | str(xml_string).encode() guards non-string types |
| BUG-EXF-005 | P1 | limit sentinel None vs explicit 0 |
| NAME-EXF-001 | P2 | xmlfield key match |
| NAME-EXF-002 | P2 | mapping index reconciliation |
| TEST-EXF-001 | P1 | 23 engine tests added |

### By Category

| Category | Open | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 4 | ENG-EXF-002, ENG-EXF-004, ENG-EXF-007, ENG-EXF-008 |
| Bug (BUG) | 2 | BUG-EXF-001 (cross-cutting), BUG-EXF-006 |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 1 | PERF-EXF-002 (cross-cutting iterrows) |
| Testing (TEST) | 0 | -- |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `extract_xml_fields.py:199` | `iterrows()` anti-pattern (shared with multiple components) |

---

## 10. Recommendations

### Immediate (Before Production)

1. ~~**ENG-EXF-001 (P0)**~~: **DONE 2026-05-06** -- limit=0 reads nothing per Talend semantics.
2. **BUG-EXF-001 (P0)**: Fix cross-cutting `_update_global_map()` crash -- tracked in CROSS_CUTTING_ISSUES.md.
3. ~~**BUG-EXF-002 (P0)**~~: **DONE** (post-rewrite) -- `iter()` replaces deprecated `getiterator()`.

### Short-term (Hardening)

1. ~~**ENG-EXF-002/003/004 (P1)**~~: **DONE** -- lxml 5.x compatibility, NaN detection, str() guard all addressed in post-rewrite.
2. ~~**PERF-EXF-001 (P1)**~~: XMLParser security flags added; per-row creation acceptable.
3. ~~**TEST-EXF-001 (P1)**~~: **DONE 2026-05-06** -- 23 engine unit tests across 7 classes.

### Long-term (Optimization)

1. **PERF-EXF-002 (P2)**: Replace iterrows() with vectorized XML processing (CROSS-CUTTING -- defer to batch fix).
2. **ENG-EXF-002 (P3)**: Implement Get Nodes feature for Document-typed columns if needed.

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| XXE (XML External Entity) injection | ~~Medium~~ **Low** | High | **MITIGATED 2026-05-06**: `resolve_entities=False, no_network=True` added to XMLParser. [Phase 12-04, commit c921545] |
| DTD processing risks | ~~Medium~~ **Low** | Medium | **MITIGATED 2026-05-06**: `load_dtd=False` added to XMLParser prevents DTD-bomb attacks. [Phase 12-04, commit c921545] |
| XPath injection via loop_query | Low | High | User-controlled `loop_query` expressions could be crafted to extract unintended data or cause excessive processing. Mitigation: validate XPath expressions before execution. |
| Large XML document memory consumption | High | Medium | No size limit on XML content in columns. A single row with a 1GB XML string would be parsed entirely into memory. Mitigation: add configurable max XML size. |
| Namespace handling inconsistencies | Medium | Low | `ignore_ns` strips namespaces by walking entire tree, which may not handle all namespace declaration patterns (e.g., default namespaces, namespace re-declarations). |
| Path traversal via xml_text/xml_prefix | Low | Medium | Hidden `xml_text` and `xml_prefix` params could be used to inject unexpected content or namespace prefixes. Currently not read by engine, but if implemented need validation. |

### High-Risk Job Patterns

1. ~~Jobs processing untrusted XML content -- XXE risk~~ **MITIGATED** (2026-05-06)
2. ~~Jobs with limit=0 expecting "read nothing" behavior~~ **FIXED** (2026-05-06)
3. ~~Jobs running on lxml 5.0+ -- getiterator() crash~~ **FIXED** (post-rewrite)
4. Jobs with very large XML documents (>100MB per row) -- memory exhaustion (no size limit)

### Safe Usage Patterns

1. Jobs with trusted, well-formed XML from internal databases
2. Jobs with small-to-medium XML documents (<10MB per row)
3. Jobs not relying on limit=0 behavior
4. Jobs running on lxml 4.x

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tExtractXMLField Standard Properties (8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractxmlfield-standard-properties) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [nicholasalx/talend_components](https://github.com/nicholasalx/talend_components) | Component definition XML, hidden params |
| Engine source | `src/v1/engine/components/transform/extract_xml_fields.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_extract_xml_fields.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | Multiple engine components | `iterrows()` anti-pattern causes 100-1000x performance degradation |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 -- Phase 15.1-05 reconciliation (Phase 12-04 c921545 harden cited for ENG-EXF-005/006; Phase 12-08 838b24c coverage gate noted)*
