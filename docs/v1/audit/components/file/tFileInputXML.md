# Audit Report: tFileInputXML / FileInputXML

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileInputXML` |
| **V1 Engine Class** | `FileInputXML` |
| **Engine File** | `src/v1/engine/components/file/file_input_xml.py` (555 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_xml.py` (169 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputXML")` decorator-based dispatch |
| **Registry Aliases** | `FileInputXML`, `tFileInputXML` |
| **Category** | File / XML / Input |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_input_xml.py` | Engine implementation (555 lines): 6 module-level helpers + 1 class with 4 methods |
| `src/converters/talend_to_v1/components/file/file_input_xml.py` | Converter class (169 lines) |
| `tests/converters/talend_to_v1/components/test_file_input_xml.py` | Converter tests (63 tests, 10 classes) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 19 config keys extracted (17 unique + 2 framework). MAPPING triplet parser. 7 per-feature needs_review. TMP_FILENAME and SCHEMA_OPT_NUM added. |
| Engine Feature Parity | **Y** | 1 | 4 | 3 | 2 | No REJECT flow; no SAX/streaming; no date validation; namespace detection only root NS; bare `@attr` XPath broken |
| Code Quality | **Y** | 1 | 3 | 4 | 2 | Cross-cutting `_update_global_map()` crash; `_validate_config()` dead code; parent traversal O(n^2); `zip()` drops columns silently |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | Full DOM parse via ElementTree; no SAX streaming option; O(n) parent scan per `../` per column per row |
| Testing | **Y** | 0 | 1 | 1 | 0 | 63 converter tests across 10 classes; zero engine unit tests |

Overall: YELLOW -- Converter production-ready; engine has P0 cross-cutting crash and functional gaps

**Top Actions**:

1. Fix cross-cutting `_update_global_map()` crash (P0, affects all components)
2. Implement REJECT flow support for XML parsing errors
3. Add SAX/streaming mode for large XML files
4. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tFileInputXML Does

tFileInputXML reads XML files and extracts data using XPath expressions. It defines a loop query that selects repeating elements (e.g., `/orders/order`), then for each matched element, evaluates per-column XPath expressions to extract values into a tabular row structure.

The component supports Dom4j and SAX parsing modes (via GENERATION_MODE), namespace handling (IGNORE_NS), DTD processing control (IGNORE_DTD), and advanced number formatting (ADVANCED_SEPARATOR with locale-specific thousands/decimal separators). The MAPPING TABLE defines the extraction rules using triplets of SCHEMA_COLUMN (column name), QUERY (XPath expression), and NODECHECK (whether to verify node existence).

**Source**: Talaxie GitHub `tFileInputXML_java.xml`
**Component family**: File / XML
**Available in**: Talend Open Studio, Talend Platform
**Required JARs**: Dom4j (for Dom4j mode), built-in (for SAX mode)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Output schema defining column names and types |
| 2 | File Name | `FILENAME` | FILE | (dir default) | Path to the XML file to read |
| 3 | Loop XPath Query | `LOOP_QUERY` | TEXT | `"/bills/bill/line"` | XPath expression selecting repeating elements for row extraction |
| 4 | Mapping | `MAPPING` | TABLE | -- | Stride-3 table: SCHEMA_COLUMN + QUERY + NODECHECK per column |
| 5 | Row Limit | `LIMIT` | TEXT | (empty) | Maximum rows to extract (empty = unlimited) |
| 6 | Die on Error | `DIE_ON_ERROR` | CHECK | false | Whether to abort job on XML parsing errors |
| 7 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding of the XML file |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 8 | Generation Mode | `GENERATION_MODE` | CLOSED_LIST | `"Dom4j"` | XML parser mode: Dom4j (DOM tree) or SAX (streaming) |
| 9 | Ignore Namespaces | `IGNORE_NS` | CHECK | false | Strip namespace prefixes from XPath evaluation |
| 10 | Ignore DTD | `IGNORE_DTD` | CHECK | false | Skip DTD validation during parsing |
| 11 | Advanced Separator | `ADVANCED_SEPARATOR` | CHECK | false | Enable locale-aware number formatting |
| 12 | Thousands Separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands separator character (when advanced_separator=true) |
| 13 | Decimal Separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal separator character (when advanced_separator=true) |
| 14 | Check Date | `CHECK_DATE` | CHECK | false | Validate date fields against pattern during extraction |
| 15 | Use Separator | `USE_SEPARATOR` | CHECK | false | Enable field separator concatenation mode |
| 16 | Field Separator | `FIELD_SEPARATOR` | TEXT | `","` | Separator for concatenating multi-value fields (when use_separator=true) |
| 17 | Temp File Name | `TMP_FILENAME` | FILE | (empty) | Temporary file path for processing large files |
| 18 | Schema Opt Num | `SCHEMA_OPT_NUM` | TEXT | `100` | Schema optimization row count threshold |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Extracted XML data as tabular rows |
| `REJECT` | Output | Row > Reject | Rows that failed XPath extraction (with errorCode/errorMessage) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on component error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows extracted |

### 3.5 Behavioral Notes

1. **Encoding default is ISO-8859-15**, not UTF-8 -- this is the Talend standard default per _java.xml
2. **MAPPING TABLE uses stride-3 triplets**: SCHEMA_COLUMN (column name), QUERY (XPath expression), NODECHECK (verify node exists before extracting)
3. **LOOP_QUERY default is `/bills/bill/line`** -- from the _java.xml default parameter value
4. **GENERATION_MODE controls parser backend**: Dom4j loads entire document into memory (DOM tree), SAX streams it with event handlers
5. **IGNORE_NS strips namespace prefixes** from both the document and XPath expressions during evaluation
6. **NODECHECK=true** means the parser verifies the XPath target node exists before attempting value extraction; false means extract regardless (may return empty)
7. **TMP_FILENAME** is used when processing very large XML files -- Talend writes intermediate results to this temp file
8. **SCHEMA_OPT_NUM** controls how many rows to sample for automatic schema type detection optimization

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileInputXML")` decorator-based dispatch. The `FileInputXMLConverter.convert()` method extracts all 19 config keys (17 unique + 2 framework) using base class helpers. A module-level `_parse_mapping()` function handles the stride-3 MAPPING TABLE with push-on-next-SCHEMA_COLUMN state machine.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILENAME` | Yes | `filepath` | Engine reads `filepath` or `FILENAME` |
| 2 | `LOOP_QUERY` | Yes | `loop_query` | Default: `"/bills/bill/line"` |
| 3 | `MAPPING` | Yes | `mapping` | Triplet TABLE: column/xpath/nodecheck dicts |
| 4 | `LIMIT` | Yes | `limit` | As string for expression support |
| 5 | `DIE_ON_ERROR` | Yes | `die_on_error` | Default: False |
| 6 | `ENCODING` | Yes | `encoding` | Default: ISO-8859-15 |
| 7 | `IGNORE_NS` | Yes | `ignore_ns` | Default: False |
| 8 | `IGNORE_DTD` | Yes | `ignore_dtd` | Default: False |
| 9 | `GENERATION_MODE` | Yes | `generation_mode` | Default: "Dom4j" (CLOSED_LIST) |
| 10 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | Default: False |
| 11 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | Default: "," |
| 12 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | Default: "." |
| 13 | `CHECK_DATE` | Yes | `check_date` | Default: False |
| 14 | `USE_SEPARATOR` | Yes | `use_separator` | Default: False |
| 15 | `FIELD_SEPARATOR` | Yes | `field_separator` | Default: "," |
| 16 | `TMP_FILENAME` | Yes | `tmp_filename` | Default: "" (newly added) |
| 17 | `SCHEMA_OPT_NUM` | **REMOVED** | ~~schema_opt_num~~ | Hidden/design-time param -- removed from converter |
| 18 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param |
| 19 | `LABEL` | Yes | `label` | Framework param |

**Summary**: 18 of 19 parameters extracted. 1 hidden param removed (SCHEMA_OPT_NUM).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Direct from SchemaColumn |
| `type` | Yes | Converted via `convert_type()` (Talend -> Python) |
| `nullable` | Yes | Boolean flag |
| `key` | Yes | Boolean flag |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not implemented in base class |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are preserved as literal strings in config values. The engine handles resolution at runtime via `replace_in_config()`.

### 4.4 Converter Issues

None. All parameters correctly extracted with proper defaults and types.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `generation_mode` | Engine only supports Dom4j-style DOM processing; SAX mode not implemented | engine_gap |
| 2 | `advanced_separator` | Engine does not support locale-aware number formatting for XML | engine_gap |
| 3 | `check_date` | Engine does not validate date fields during XML extraction | engine_gap |
| 4 | `use_separator` | Engine does not support field separator concatenation for XML | engine_gap |
| 5 | `field_separator` | Engine does not read field_separator config key | engine_gap |
| 6 | `tmp_filename` | Engine does not read tmp_filename config key | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | XML file reading | **Yes** | High | `_process()` line 296 | ElementTree parsing |
| 2 | Loop XPath query | **Yes** | Medium | `_parse_xml()` line 377 | Namespace auto-qualification |
| 3 | MAPPING extraction | **Yes** | High | `_parse_xml()` line 449 | Stride-3 triplet scan |
| 4 | Encoding handling | **Partial** | Medium | `_parse_xml_passthrough()` line 533 | Only in passthrough mode, not tabular |
| 5 | Die on error | **Yes** | High | `_process()` line 366 | RuntimeError on True |
| 6 | Ignore namespaces | **Partial** | Low | `normalize_nsmaps()` line 57 | Only detects root element NS |
| 7 | Ignore DTD | **Partial** | Low | `_parse_xml_passthrough()` line 535 | Only in passthrough mode |
| 8 | GENERATION_MODE | **No** | N/A | -- | Only Dom4j-style DOM; no SAX streaming |
| 9 | ADVANCED_SEPARATOR | **No** | N/A | -- | No locale-aware number formatting |
| 10 | CHECK_DATE | **No** | N/A | -- | No date validation during extraction |
| 11 | USE_SEPARATOR | **No** | N/A | -- | No field separator concatenation |
| 12 | TMP_FILENAME | **No** | N/A | -- | No temp file support |
| 13 | SCHEMA_OPT_NUM | **No** | N/A | -- | No schema optimization |
| 14 | REJECT flow | **No** | N/A | -- | No reject output for failed rows |
| 15 | Limit support | **Partial** | Low | `_process()` line 312 | Config read but not applied in tabular mode |
| 16 | Parent navigation (..) | **Yes** | Medium | `find_element_by_manual_navigation()` line 110 | Custom parent traversal for ElementTree |
| 17 | XML passthrough mode | **Yes** | High | `_parse_xml_passthrough()` line 515 | Single-column raw XML output |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FIX-001 | **P0** | Cross-cutting: `_update_global_map()` crashes when globalMap is set (base_component.py) |
| ENG-FIX-002 | **P1** | No REJECT flow support -- XML parsing errors either crash or return empty, never route to reject |
| ENG-FIX-003 | **P1** | No SAX streaming mode -- all XML files loaded into memory as DOM tree regardless of GENERATION_MODE |
| ENG-FIX-004 | **P1** | Namespace detection only finds root element namespace -- multi-namespace documents partially broken |
| ENG-FIX-005 | **P1** | `zip()` silently drops columns when schema/xpath count mismatch (line 478) |
| ENG-FIX-006 | **P2** | Encoding only applied in passthrough mode, not tabular mode (`_parse_xml()` uses system default) |
| ENG-FIX-007 | **P2** | LIMIT config read but not enforced in tabular mode -- all rows processed regardless |
| ENG-FIX-008 | **P2** | Bare `@attr` XPath expressions fail silently -- no leading `./@attr` normalization |
| ENG-FIX-009 | **P3** | `extract_value()` only returns first node text -- sibling text nodes dropped |
| ENG-FIX-010 | **P3** | No GET_NODES mode for complex XML structures |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Row count |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Success count |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 (no REJECT flow) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FIX-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crash when globalMap is set |
| BUG-FIX-002 | **P1** | `file_input_xml.py:478` | `zip(schema_order, schema_xpaths)` silently drops columns when counts differ |
| BUG-FIX-003 | **P2** | `file_input_xml.py:24-51` | `extract_value()` returns attribute string concat instead of text for multi-attribute nodes |
| BUG-FIX-004 | **P2** | `file_input_xml.py:57-71` | `normalize_nsmaps()` only detects root element namespace; misses child-declared namespaces |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FIX-001 | **P2** | Method `_parse_xml_passthrough` is very long single method (40 lines); should decompose |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FIX-001 | **P2** | "Use custom exceptions" | Uses bare `RuntimeError` and `ValueError` instead of custom exception classes |

### 6.4 Debug Artifacts

None found. All logging uses proper `logger.debug()` / `logger.info()`.

### 6.5 Security

See Section 11 for XML-specific security assessment (XXE, DTD attacks, namespace abuse).

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logging.getLogger(__name__)` |
| Level usage | Good -- debug for XPath details, info for status, error for failures |
| Sensitive data | OK -- file paths logged at info level (may contain sensitive paths) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Missing -- uses RuntimeError/ValueError/FileNotFoundError |
| Exception chaining | Good -- uses `raise ... from e` pattern |
| die_on_error handling | Good -- respects config flag, returns empty DataFrame on False |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods typed |
| Parameter types | Good -- uses Dict, List, Optional, Any |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FIX-001 | **P1** | Full DOM parse loads entire XML into memory -- 100MB+ files will cause OOM |
| PERF-FIX-002 | **P2** | `find_parent_element()` does O(n) tree traversal per call; called per `../` per column per row = O(rows \* cols \* nodes) |
| PERF-FIX-003 | **P3** | No limit enforcement in tabular mode -- processes all matching elements even when LIMIT configured |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not available -- ElementTree DOM parse only; SAX mode not implemented |
| Memory threshold | No threshold -- entire XML file loaded into memory |
| Large data handling | Risk of OOM for files >100MB; no chunked processing |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 63 | `tests/converters/talend_to_v1/components/test_file_input_xml.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (covered by regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FIX-001 | **P1** | Zero engine unit tests -- no test coverage for `_parse_xml()`, `_parse_xml_passthrough()`, namespace handling, parent navigation |
| TEST-FIX-002 | **P2** | No integration test with real XML files testing converter+engine round-trip |

### 8.3 Recommended Test Cases

- Engine: Test `_parse_xml()` with simple XML file and loop query
- Engine: Test namespace handling with multi-namespace XML
- Engine: Test parent navigation (`../`) XPath expressions
- Engine: Test `die_on_error` True vs False behavior
- Engine: Test empty XML file handling
- Engine: Test malformed XML error recovery
- Integration: Converter output -> engine execution round-trip

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-FIX-001** |
| P1 | 5 | **ENG-FIX-002**, **ENG-FIX-003**, **ENG-FIX-004**, **ENG-FIX-005**, **PERF-FIX-001**, **TEST-FIX-001** |
| P2 | 7 | **ENG-FIX-006**, **ENG-FIX-007**, **ENG-FIX-008**, **BUG-FIX-003**, **BUG-FIX-004**, **NAME-FIX-001**, **STD-FIX-001**, **PERF-FIX-002**, **TEST-FIX-002** |
| P3 | 3 | **ENG-FIX-009**, **ENG-FIX-010**, **PERF-FIX-003** |
| **Total** | **16** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 9 | ENG-FIX-001 through ENG-FIX-010 |
| Bug (BUG) | 4 | BUG-FIX-001 through BUG-FIX-004 |
| Naming (NAME) | 1 | NAME-FIX-001 |
| Standards (STD) | 1 | STD-FIX-001 |
| Performance (PERF) | 3 | PERF-FIX-001 through PERF-FIX-003 |
| Testing (TEST) | 2 | TEST-FIX-001, TEST-FIX-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects NB_LINE stat writing |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix cross-cutting `_update_global_map()` crash (BUG-FIX-001) -- affects all 54 components
2. Implement REJECT flow for XML parsing errors (ENG-FIX-002)

### Short-term (Hardening)

1. Add SAX streaming mode for large XML files (ENG-FIX-003)
2. Fix multi-namespace detection (ENG-FIX-004)
3. Guard `zip()` against mismatched schema/xpath counts (ENG-FIX-005)
4. Add engine unit tests (TEST-FIX-001)

### Long-term (Optimization)

1. Implement GET_NODES mode (ENG-FIX-010)
2. Optimize parent navigation with parent-map cache (PERF-FIX-002)
3. Enforce LIMIT in tabular mode (PERF-FIX-003)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| XXE (XML External Entity) injection | Medium | High | ElementTree blocks XXE by default (no external entity resolution); however, if DTD processing enabled (IGNORE_DTD=false), custom entity definitions could expand large payloads causing memory exhaustion (billion laughs attack) |
| DTD processing attacks | Medium | High | When IGNORE_DTD=false, external DTD references could cause network requests or file reads from the server; mitigation: set IGNORE_DTD=true for untrusted XML |
| Namespace abuse / confusion | Low | Medium | Attackers could craft XML with conflicting namespace declarations; engine only detects root namespace, so child namespace declarations would be invisible, potentially extracting wrong data |
| Large file memory exhaustion | High | High | No SAX streaming mode; 100MB+ XML files will cause OOM. Mitigation: pre-filter large files or add streaming support before production use with large XML |
| DOM4J vs SAX security differences | Low | Medium | Dom4j mode (the only mode implemented) loads full document into memory, making it vulnerable to zip-bomb-style XML expansion; SAX mode would limit memory exposure but is not implemented |
| Path traversal via FILENAME | Low | Medium | FILENAME parameter accepts arbitrary file paths; if user-controlled, could read sensitive system files; engine does `os.path.exists()` check but no path sanitization |

### High-Risk Job Patterns

- Jobs processing untrusted/external XML with IGNORE_DTD=false -- vulnerable to DTD attacks
- Jobs with large XML files (>50MB) without LIMIT -- risk of OOM from full DOM parse
- Jobs with multi-namespace XML and IGNORE_NS=false -- namespace detection is incomplete
- Jobs using `../` parent navigation on deeply nested XML -- O(n^2) performance degradation

### Safe Usage Patterns

- Small to medium XML files (<50MB) with IGNORE_DTD=true
- Simple single-namespace or no-namespace XML with well-defined XPath mappings
- LIMIT set to reasonable value for large document iteration
- DIE_ON_ERROR=true for fail-fast behavior on malformed XML

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `tFileInputXML_java.xml` from Talaxie repository | Parameter definitions, defaults, types |
| Engine source | `src/v1/engine/components/file/file_input_xml.py` | Feature parity analysis (555 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_xml.py` | Converter audit (169 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_xml.py` | Test coverage (63 tests) |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |
| Phase 9 research | `.planning/phases/09-file-input-components/09-RESEARCH.md` | _java.xml parameter analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects `_update_stats()` call at end of `_process()` |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature -- may affect stat retrieval |
| XCUT-003 | `base_component.py:174` | `replace_in_config` literal `[i]` bug -- affects config resolution of context vars |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after hidden/design-time param removal*
