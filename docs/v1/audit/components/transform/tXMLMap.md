# Audit Report: tXMLMap / XMLMap

> **Audited**: 2026-04-04
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tXMLMap` |
| **V1 Engine Class** | `XMLMap` |
| **Engine File** | `src/v1/engine/components/transform/xml_map.py` (738 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/xml_map.py` (~310 lines post-standardization) |
| **Converter Dispatch** | `@REGISTRY.register("tXMLMap")` decorator-based dispatch |
| **Registry Aliases** | `XMLMap`, `tXMLMap` |
| **Category** | Transform / XML (Multi-Flow) |
| **Complexity** | Very High -- XML tree mapping, recursive parsing, XPath evaluation, namespace handling, looping element detection, expression rewriting |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/xml_map.py` | Engine implementation (738 lines) |
| `src/converters/talend_to_v1/components/transform/xml_map.py` | Converter class (~310 lines) |
| `tests/converters/talend_to_v1/components/test_xml_map.py` | Converter tests (24 tests in 9 classes) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 2 flat + nodeData (inputTrees/outputTrees/connections/varTables) + 2 framework params; _build_component_dict with type_name="XMLMap"; CONNECTION_FORMAT phantom removed; snake_case config keys; removeprefix() per D-76; 10 needs_review (8 engine_gap + 2 output_shape_change); 24 tests in 9 classes with TestMultiFlow |
| Engine Feature Parity | **R** | 2 | 7 | 6 | 1 | Only first row processed; no lookup/join; no reject flow; no expression filter; no Document output; die_on_error ignored; globalMap not published; no context var resolution; child namespaces invisible; descendant:: misrouted to root |
| Code Quality | **Y** | 1 | 4 | 7 | 5 | Converter clean with proper logging. Engine: 46 print() statements, NaN handling absent, expression cleaning corrupts valid XPath, split_steps destroys predicate XPaths. Cross-cutting base class bugs remain. |
| Performance & Memory | **Y** | 0 | 1 | 3 | 1 | 46 flush=True print() calls per loop-node-per-column dominate runtime; no streaming mode; no XML caching |
| Testing | **Y** | 0 | 1 | 0 | 0 | 24 converter tests passing (gold standard rewrite). Zero engine unit tests (out of scope). |

**Overall: RED -- Engine not production-ready. Converter is GREEN. Engine and cross-cutting issues remain out of scope for converter enhancement.**

---

## 3. Talend Feature Baseline

### What tXMLMap Does

`tXMLMap` is a specialized transformation component fine-tuned to leverage the **Document** data type for processing XML data. It handles transformation scenarios that mix hierarchical data (XML) and flat data together. The Document type carries a complete user-specific XML flow. tXMLMap provides a visual Map Editor where users can:

- Define input XML tree structures (from schemas or XSD files)
- Define output XML tree structures
- Map fields between input and output trees using drag-and-drop
- Apply XPath expressions for data extraction
- Configure looping elements for repeated XML structures
- Use expression filters to conditionally route data
- Join multiple input sources (inner join and left outer join)
- Produce XML Document output or flat row output
- Aggregate output into classified XML structures

tXMLMap is one of the most complex Talend components, combining XML parsing, tree manipulation, XPath evaluation, namespace management, and data routing into a single visual interface.

**Source**: [tXMLMap Standard properties (Talend 7.3)](https://help.talend.com/r/en-US/7.3/txmlmap/txmlmap-standard-properties), [tXMLMap operation (Talend Studio 8.0)](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-10/txmlmap-operation)
**Component family**: Processing / XML
**Available in**: All Talend products (Standard)
**Required JARs**: Part of Talend runtime; uses built-in SAX/DOM/StAX parsers from the JDK.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Input Trees | `inputTrees` (nodeData) | XML Tree Structure | -- | One or more XML input trees defining the source data structure. First tree is main; additional trees are lookups. |
| 2 | Output Trees | `outputTrees` (nodeData) | XML Tree Structure | -- | One or more XML output trees defining the target structure. Can produce flat rows or XML Document output. |
| 3 | Looping Element | `loop="true"` (node attribute) | Node flag | -- | **Critical**. The XML element on which the component iterates. Each occurrence produces one output row. |
| 4 | Connections | `connections` (nodeData) | Source-Target Mapping | -- | Maps input tree nodes to output tree nodes. Each connection has source, target, and sourceExpression. |
| 5 | Schema | `metadata[@connector="FLOW"]` | Schema editor | -- | Output schema with column definitions. |
| 6 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Whether to stop job execution on processing error. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 7 | Keep Order for Document | `KEEP_ORDER_FOR_DOCUMENT` | Boolean (CHECK) | `false` | Preserve element order in XML Document output. |
| 8 | Expression Filter | `expressionFilter` (outputTree attr) | Java Expression | -- | Java expression to filter rows before output. Uses `row.fieldName` syntax. |
| 9 | Activate Expression Filter | `activateExpressionFilter` (outputTree attr) | Boolean | `false` | Enable/disable the expression filter on an output tree. |
| 10 | Matching Mode (Lookup) | `matchingMode` (inputTree attr) | Enum | `ALL_ROWS` | Lookup matching strategy: ALL_ROWS, FIRST_MATCH, LAST_MATCH, ALL_MATCHES. |
| 11 | Lookup Mode | `lookupMode` (inputTree attr) | Enum | `LOAD_ONCE` | When to load lookup data: LOAD_ONCE or RELOAD. |
| 12 | All in One | `allInOne` (outputTree property) | Boolean | `false` | Generate single aggregated XML Document output. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata. Framework param. |
| 14 | Label | `LABEL` | String | `""` | Component label. Framework param. |

### 3.3 Phantom Parameters

| Parameter | Source | Status |
| ----------- | -------- | -------- |
| `CONNECTION_FORMAT` | .item file only | **PHANTOM** -- not in _java.xml. Removed from converter output. |
| `MAP` | Talend Studio | **EXTERNAL** -- visual editor reference, not extracted. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Primary XML data flow (Document type or flat schema) |
| `LOOKUP` | Input | Row > Lookup | Additional input flows for join/lookup operations |
| `FLOW` (Output) | Output | Row > Main | Transformed rows matching the output schema |
| `REJECT` | Output | Row > Reject | Rows that failed XML processing |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Subjob completed successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Subjob failed |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of output rows generated |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to REJECT |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message |

---

## 4. Converter Audit

### 4.1 Parameter Extraction

| # | Talend XML Parameter | Extracted? | V1 Config Key | Extraction Method | Default | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------------------- | --------- | ------- |
| 1 | `DIE_ON_ERROR` | **Yes** | `die_on_error` | `_get_bool()` | `True` | Hidden param per _java.xml |
| 2 | `KEEP_ORDER_FOR_DOCUMENT` | **Yes** | `keep_order_for_document` | `_get_bool()` | `False` | snake_case per D-38 |
| 3 | `inputTrees` (nodeData) | **Yes** | `input_trees` | `_parse_input_trees()` | `[]` | Recursive: name, matchingMode, lookupMode, lookup, activateGlobalMap, nodes/children |
| 4 | `outputTrees` (nodeData) | **Yes** | `output_trees` | `_parse_output_trees()` | `[]` | Recursive: name, expressionFilter, activateExpressionFilter, allInOne, nodes/children |
| 5 | `connections` (nodeData) | **Yes** | `connections` | `_parse_connections()` | `[]` | source/target/sourceExpression |
| 6 | `varTables` (nodeData) | **Yes** | `var_tables` | `_parse_var_tables()` | `[]` | Variable tables for fidelity |
| 7 | `metadata[@connector="FLOW"]` | **Yes** | `output_schema` | `_parse_output_schema_from_xml()` | `[]` | Column name, type, nullable, key, length, precision |
| 8 | looping_element (derived) | **Yes** | `looping_element` | `_detect_looping_element()` | `""` | 3-strategy: loop="true" -> elementParameter -> deepest node |
| 9 | expressions (derived) | **Yes** | `expressions` | `_build_expressions()` + rewrite | `{}` | Built from connections + node map; XPath rewrite relative to loop |
| 10 | expression_filter (derived) | **Yes** | `expression_filter` | From first output tree | `None` | Prefixed with `{{java}}` when active |
| 11 | `TSTATCATCHER_STATS` | **Yes** | `tstatcatcher_stats` | `_get_bool()` | `False` | Framework param |
| 12 | `LABEL` | **Yes** | `label` | `_get_str()` | `""` | Framework param |

**Summary**: All runtime-relevant parameters extracted (100%). Phantom CONNECTION_FORMAT removed. Snake_case config keys per D-38. Uses `_build_component_dict` with `type_name="XMLMap"`. Uses `removeprefix()` per D-76 (no lstrip). **Converter score: GREEN.**

### 4.2 Schema Extraction

Schema uses `{"input": schema_cols, "output": output_schema}` where output_schema comes from FLOW metadata parsing. Input schema from base class `_parse_schema()`.

### 4.3 Needs_Review Entries

The converter emits 10 `needs_review` entries (8 engine_gap + 2 output_shape_change per D-74):

| Config Key | Severity | Detail |
| ------------ | ---------- | -------- |
| `die_on_error` | engine_gap | Errors silently swallowed regardless of setting |
| `keep_order_for_document` | engine_gap | Document ordering not enforced by engine |
| `input_trees` | engine_gap | Input tree metadata stored but not used by engine |
| `output_trees` | engine_gap | Output tree metadata stored but not used by engine |
| `connections` | engine_gap | Connection metadata stored but not used by engine |
| `expression_filter` | engine_gap | Expression filter not evaluated by engine |
| `activate_expression_filter` | engine_gap | Expression filter activation flag not checked |
| `var_tables` | engine_gap | Variable tables not supported by engine |
| `allInOne` | output_shape_change | allInOne output mode not supported -- engine outputs flat rows only |
| `lookup` | output_shape_change | Lookup/join input trees not supported by engine |

**Keys NOT in needs_review (engine reads them):** `looping_element`, `output_schema`, `expressions`
**Keys NOT in needs_review (framework, exempt per convention):** `tstatcatcher_stats`, `label`

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-XMP-001 | ~~P0~~ | **SUPERSEDED** -- lstrip crash resolved. Converter uses removeprefix() per D-76. |
| CONV-XMP-002 | ~~P1~~ | **SUPERSEDED** -- Registry alias mismatch resolved. `@REGISTRY.register("tXMLMap")` outputs `XMLMap`. |
| CONV-XMP-003 | ~~P1~~ | **SUPERSEDED** -- Only first output tree expression building. Design decision; engine only processes one output. |
| CONV-XMP-004 | ~~P1~~ | **SUPERSEDED** -- Hardcoded root names removed. Engine handles root prefix at runtime. |
| CONV-XMP-005 | ~~P1~~ | **SUPERSEDED** -- Ancestor XPath rewrite rewritten with proper logic. |
| CONV-XMP-006 | ~~P2~~ | **SUPERSEDED** -- Auto-detect looping element type normalization fixed. |

**All CONV-XMP issues SUPERSEDED.** Converter completely rewritten as gold-standard per v1.1 templates.

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Notes |
| ---- | ---------------- | ------------- | ---------- | ------- |
| 1 | Parse XML from Document field | **Yes** | Medium | Reads `iloc[0,0]` only -- single row, single column |
| 2 | Looping element iteration | **Yes** | Medium | Uses `.//{element}` XPath; cleaned via `_clean_looping_element()` |
| 3 | XPath expression evaluation | **Yes** | Medium | Supports relative, absolute, descendant, ancestor via lxml |
| 4 | Namespace handling (default xmlns) | **Yes** | Medium | Default namespace remapped to `ns0` prefix |
| 5 | Namespace handling (prefixed) | **Yes** | Medium | Uses first prefix found in document |
| 6 | Output schema column ordering | **Yes** | High | Ensures column order matches schema |
| 7 | Statistics tracking (NB_LINE) | **Yes** | Medium | NB_LINE_REJECT always 0 |
| 8 | **Multiple input trees (lookup)** | **No** | N/A | Only processes one input -- no lookup/join support |
| 9 | **Multiple output trees** | **No** | N/A | Only produces one "main" output |
| 10 | **REJECT flow** | **No** | N/A | No reject output |
| 11 | **Expression filter (Java)** | **No** | N/A | Config extracted but never consumed |
| 12 | **Document output (All in One)** | **No** | N/A | Cannot produce XML Document type output |
| 13 | **Die on error** | **No** | N/A | Config key extracted but never read |
| 14 | **Multiple rows per Document** | **No** | N/A | Only reads `iloc[0,0]` -- data loss for multi-row input |
| 15 | **GlobalMap publication** | **No** | N/A | Crashes on `_update_global_map()` (cross-cutting bug) |

### 5.2 Engine Behavioral Issues

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-XMP-001 | **P0** | **No lookup/join support**: Only single input processed. Jobs with lookup connections silently lose data. |
| ENG-XMP-002 | **P0** | **Only first row processed**: `iloc[0,0]` discards all rows after first. Data loss bug. |
| ENG-XMP-003 | **P1** | **No reject flow**: NB_LINE_REJECT always 0. Error rows produce empty strings. |
| ENG-XMP-004 | **P1** | **No expression filter**: Config extracted but never consumed by engine. |
| ENG-XMP-005 | **P1** | **No Document output mode**: Cannot produce XML Document type. |
| ENG-XMP-006 | **P1** | **Die on error ignored**: Errors always silently swallowed. |
| ENG-XMP-007 | **P1** | **GlobalMap crashes**: Cross-cutting `_update_global_map()` bug. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-XMP-003 | **P0** | `xml_map.py` line 506 | Only first row processed via `iloc[0,0]`. Data loss for multi-row Document input. |
| BUG-XMP-012 | **P0** (cross-cutting) | `base_component.py` line 304 | `_update_global_map()` references undefined variable `value`. Crashes ALL components. |
| BUG-XMP-013 | **P0** (cross-cutting) | `global_map.py` line 28 | `GlobalMap.get()` references undefined `default` parameter. |
| BUG-XMP-004 | **P1** | `xml_map.py` line 498 | `self.id` overwritten from config inside `_process()`. |
| BUG-XMP-006 | **P1** | `xml_map.py` lines 647-665 | Ancestor fallback `//tail` returns wrong nodes from unrelated branches. |
| BUG-XMP-014 | **P1** | `xml_map.py` lines 65-77 | `split_steps()` destroys XPath predicates containing `/`. |

### 6.2 Standards

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| STD-XMP-001 | **P1** | Engine: 46 `print()` statements bypass logging framework. |
| NAME-XMP-003 | **P3** | `DEFAULT_LOOPING_ELEMENT = ""` constant defined but never used. Dead code. |

### 6.3 Security

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| SEC-XMP-001 | **P2** | No XML bomb protection -- lxml default parser allows entity expansion. |
| SEC-XMP-002 | **P3** | XPath injection risk from untrusted config (low risk -- config from Talend export). |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-XMP-001 | **P1** | O(N*M*K) flush=True `print()` calls dominate processing time. |
| PERF-XMP-002 | **P2** | Full ancestor chain iteration per loop node for debug output. |
| PERF-XMP-003 | **P2** | No streaming mode support. All loop nodes processed in single pass. |
| PERF-XMP-004 | **P3** | No XML caching between rows (latent, not active until BUG-XMP-003 fixed). |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
| ----------- | --------- | ------ | ------- |
| Converter unit tests | **Yes** | `tests/converters/talend_to_v1/components/test_xml_map.py` | 24 tests in 9 classes (gold standard rewrite) |
| V1 engine unit tests | **No** | -- | Zero test files for XMLMap engine |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests |

### 8.2 Converter Test Coverage

| Test Class | Tests | Description |
| ----------- | ------- | ------------- |
| TestRegistration | 1 | Registry dispatch verification |
| TestDefaults | 4 | die_on_error, keep_order_for_document, tstatcatcher_stats, label defaults |
| TestParameterExtraction | 2 | Explicit param values extracted correctly |
| TestMultiFlow | 6 | Main input tree, main+lookup, output tree, connections, looping element, all combined (D-75) |
| TestSchema | 1 | Input/output schema structure |
| TestNeedsReview | 2 | Engine gap entries with correct severity |
| TestNoLstripBug | 2 | D-76 compliance -- no lstrip() in source (uses removeprefix) |
| TestCompleteness | 1 | All config keys present |
| TestComponentStructure | 5 | Type, original_type, standard keys, result type, raw_xml None warning |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
| ---- | ---------- | --------- |
| BUG-XMP-003 | Engine Bug | Only first row processed via `iloc[0,0]` -- data loss for multi-row input |
| BUG-XMP-012 | Bug (Cross-Cutting) | `_update_global_map()` references undefined variable |
| BUG-XMP-013 | Bug (Cross-Cutting) | `GlobalMap.get()` references undefined `default` parameter |

### P1 -- Major

| ID | Category | Summary |
| ---- | ---------- | --------- |
| ENG-XMP-001 | Feature Gap | No lookup/join support |
| ENG-XMP-002 | Feature Gap | Only first row processed (same as BUG-XMP-003) |
| ENG-XMP-003 | Feature Gap | No reject flow |
| ENG-XMP-004 | Feature Gap | No expression filter support |
| ENG-XMP-005 | Feature Gap | No Document output mode |
| ENG-XMP-006 | Feature Gap | Die on error ignored |
| ENG-XMP-007 | Feature Gap | GlobalMap variables not published (cross-cutting crash) |
| BUG-XMP-004 | Engine Bug | `self.id` overwritten mid-execution |
| BUG-XMP-006 | Engine Bug | Ancestor fallback returns wrong nodes |
| BUG-XMP-014 | Engine Bug | `split_steps()` destroys XPath predicates |
| STD-XMP-001 | Standards | 46 print() statements in engine |
| PERF-XMP-001 | Performance | O(N*M*K) print() calls dominate runtime |

### P2 -- Moderate

| ID | Category | Summary |
| ---- | ---------- | --------- |
| SEC-XMP-001 | Security | No XML bomb protection |
| PERF-XMP-002 | Performance | Ancestor chain iteration per loop node |
| PERF-XMP-003 | Performance | No streaming mode |

### P3 -- Low

| ID | Category | Summary |
| ---- | ---------- | --------- |
| NAME-XMP-003 | Naming | Dead constant `DEFAULT_LOOPING_ELEMENT` |
| SEC-XMP-002 | Security | XPath injection (low risk) |
| PERF-XMP-004 | Performance | No XML caching (latent) |

---

## 10. Recommendations

### Immediate (Converter -- DONE)

1. ~~Rewrite converter to gold standard~~ -- COMPLETED in Phase 12 Plan 10
2. ~~Replace lstrip with removeprefix per D-76~~ -- COMPLETED
3. ~~Remove phantom CONNECTION_FORMAT~~ -- COMPLETED
4. ~~Add multi-flow test scenarios per D-75~~ -- COMPLETED (TestMultiFlow, 6 tests)
5. ~~Add D-76 compliance test~~ -- COMPLETED (TestNoLstripBug)

### Short-term (Engine)

1. Fix BUG-XMP-003: Process all rows, not just `iloc[0,0]`
2. Fix cross-cutting base class bugs (BUG-XMP-012, BUG-XMP-013)
3. Add engine unit tests
4. Remove 46 print() statements, use logging framework

### Medium-term (Engine)

1. Implement lookup/join support
2. Implement expression filter evaluation
3. Implement reject flow
4. Implement Document output mode
5. Add XML bomb protection (SEC-XMP-001)

---

## 11. Risk Assessment

### R1: lstrip Crash Bug (D-76) -- CRITICAL

**Impact**: The engine file `xml_map.py` line 281 contains `tail.lstrip("/")` which is dangerous. Python's `str.lstrip()` strips ALL characters in its argument, not just the prefix. For example:

- `"/employees".lstrip("/")` = `"employees"` (correct by luck)
- `"/employees".lstrip("/e")` = `"mployees"` (WRONG -- strips both `/` and `e`)

The converter's previous version had `xpath.strip().lstrip("./")` which would corrupt any XPath starting with characters in `.` or `/` -- e.g., `"./field"` would become `"ield"` if the XPath contained `f` after stripping.

**Status**: Converter FIXED -- uses `removeprefix("./")` per D-76. Engine bug at line 281 (`lstrip("/")`) still exists but is lower risk since it only strips `/` from a path that should always start with `/`.

**Mitigation**: The converter no longer introduces this bug. The engine's usage is limited to a single character and happens to work correctly for most paths, but should still be refactored.

### R2: XXE Injection via XML Tree Content

**Impact**: The engine uses `ET.fromstring(xml_string.encode("utf-8"))` with lxml's default parser, which allows XML entity expansion. Malicious XML input could trigger billion-laughs attack or external entity retrieval.

**Mitigation**: Input comes from Talend job export (trusted source). For untrusted input, would need `defusedxml` or parser with `resolve_entities=False`.

### R3: Recursive Tree Parsing Stack Overflow

**Impact**: The converter's `_parse_nested_children()` recurses to parse deeply nested XML tree structures. Python's default recursion limit is 1000. Extremely deep XML trees (>500 nesting levels) could cause `RecursionError`.

**Mitigation**: Real-world Talend XML trees rarely exceed 20-30 levels. Risk is theoretical.

### R4: Connection Expression Injection

**Impact**: The `connections` element's source/target paths are used to index into the input tree node map via string matching. Malformed paths could produce incorrect expression mappings.

**Mitigation**: Paths come from Talend Studio's visual editor output, which generates well-formed paths. Not exploitable from UI.

### R5: First-Row-Only Processing (BUG-XMP-003)

**Impact**: The engine reads only `input_data.iloc[0, 0]`, silently discarding all other rows. This is a **data loss** bug. If a DataFrame has 100 rows each with an XML Document, 99 are ignored.

**Mitigation**: None. This is the single most critical engine bug. Must be fixed before production use with multi-row input.

### R6: Output Shape Fragility (D-74)

**Impact**: The engine reads only 3 keys from the converter's rich config: `output_schema`, `expressions`, `looping_element`. The remaining tree structures (`input_trees`, `output_trees`, `connections`, `var_tables`) are stored for fidelity but ignored. Features like `allInOne` and `lookup` affect the expected output shape but are not implemented -- producing flat rows instead of Document output, or missing join data.

**Mitigation**: Documented as `output_shape_change` severity in needs_review entries per D-74.

### R7: Memory Consumption for Large XML

**Impact**: The engine loads the entire XML document into memory via lxml. Large XML files (>100MB) could cause OOM. All extracted rows accumulated in a `List[Dict]` before DataFrame creation.

**Mitigation**: No streaming mode exists. Monitor memory usage for large XML workloads.

### R8: Namespace Handling in XPath Expressions

**Impact**: Only one namespace prefix is used for qualifying all XPath steps. XML documents with elements in multiple namespaces (e.g., SOAP envelopes) cannot be correctly queried.

**Mitigation**: Works correctly for single-namespace documents (majority of use cases). Multi-namespace requires engine enhancement.

---

## Appendix A: Source Reference

**_java.xml**: tXMLMap definition from Talaxie GitHub:

- `<https://github.com/Talaxie/tcommon-studio-se/`> (navigate to tXMLMap component)
- nodeData structure defined in .item XML exports (not _java.xml -- nodeData is Talend Studio internal format)
- Flat params (DIE_ON_ERROR, KEEP_ORDER_FOR_DOCUMENT) from _java.xml
- CONNECTION_FORMAT: .item only -- not in _java.xml, classified as phantom

---

## Appendix B: Engine Config Key Mapping

| Converter Config Key | Engine Reads? | Engine Access Pattern | Notes |
| --------------------- | -------------- | ---------------------- | ------- |
| `output_schema` | **Yes** | `config.get("output_schema", [])` or `config.get("schema", {}).get("output", [])` | Column definitions for output |
| `expressions` | **Yes** | `config.get("expressions", {})` | XPath expression mapping per column |
| `looping_element` | **Yes** | `config.get("looping_element", "")` or `config.get("config", {}).get("looping_element", "")` | Element that drives row iteration |
| `die_on_error` | **No** | -- | Extracted but never read |
| `keep_order_for_document` | **No** | -- | Extracted but never read |
| `input_trees` | **No** | -- | Stored for fidelity |
| `output_trees` | **No** | -- | Stored for fidelity |
| `connections` | **No** | -- | Stored for fidelity |
| `var_tables` | **No** | -- | Stored for fidelity |
| `expression_filter` | **No** | -- | Extracted but never read |
| `activate_expression_filter` | **No** | -- | Extracted but never read |
| `tstatcatcher_stats` | **No** | -- | Framework param |
| `label` | **No** | -- | Framework param |

---

## Appendix C: nodeData XML Tree Structure Reference

The tXMLMap nodeData is an embedded XML structure within the Talend .item file that defines the visual mapping configuration. It is NOT accessible through the flat params dict -- the converter parses it directly from `node.raw_xml`.

### Structure

```xml
<nodeData>
  <!-- Input tree definitions (one or more) -->
  <inputTrees name="row1" matchingMode="ALL_ROWS" lookupMode="LOAD_ONCE"
              lookup="false" activateGlobalMap="false">
    <nodes name="doc" expression="row1.payload" type="id_Document" xpath="/">
      <children name="root" type="id_String" xpath="root"
                nodeType="ELEMENT" loop="false" main="false">
        <children name="item" type="id_String" xpath="item"
                  nodeType="ELEMENT" loop="true" main="false">
          <children name="id" type="id_String" xpath="id" nodeType="ELEMENT"/>
          <children name="name" type="id_String" xpath="name" nodeType="ELEMENT"/>
        </children>
      </children>
    </nodes>
  </inputTrees>

  <!-- Output tree definitions -->
  <outputTrees name="out1" expressionFilter="" activateExpressionFilter="false"
               allInOne="false">
    <nodes name="id" expression="" type="id_String" xpath="id"/>
    <nodes name="name" expression="" type="id_String" xpath="name"/>
  </outputTrees>

  <!-- Connection mappings (source -> target) -->
  <connections source="inputTrees.0/@nodes.0/@children.0/@children.0/@children.0"
               target="outputTrees.0/@nodes.0" sourceExpression=""/>
  <connections source="inputTrees.0/@nodes.0/@children.0/@children.0/@children.1"
               target="outputTrees.0/@nodes.1" sourceExpression=""/>

  <!-- Variable tables (optional) -->
  <varTables name="Var" minimized="false"/>
</nodeData>
```

### Key Attributes

| Element | Attribute | Description |
| --------- | ----------- | ------------- |
| `inputTrees` | `name` | Tree identifier (connection name) |
| `inputTrees` | `lookup` | Whether this is a lookup input (boolean) |
| `inputTrees` | `matchingMode` | Lookup matching: ALL_ROWS, FIRST_MATCH, LAST_MATCH, ALL_MATCHES |
| `inputTrees` | `lookupMode` | Loading strategy: LOAD_ONCE, RELOAD |
| `nodes` | `name` | Element/field name |
| `nodes` | `expression` | Source expression for the node |
| `nodes` | `type` | Talend type ID (e.g., id_Document, id_String) |
| `children` | `nodeType` | ELEMENT, ATTRIBUT, NAMESPACE |
| `children` | `loop` | Whether this node is the looping element |
| `connections` | `source` | Path to source node in input tree |
| `connections` | `target` | Path to target node in output tree |
| `outputTrees` | `allInOne` | Aggregate all rows into single Document |
| `outputTrees` | `expressionFilter` | Java expression for row filtering |
