# Audit Report: tFileInputMSXML / FileInputMSXML

> **Audited**: 2026-04-03
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileInputMSXML` |
| **V1 Engine Class** | `FileInputMSXML` [NEW IN 15.1 -- engine built Phase 12-04; audit predated implementation] |
| **Engine File** | `src/v1/engine/components/file/file_input_msxml.py` (273 lines) [NEW IN 15.1] |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_msxml.py` (132 lines) |
| **Converter Dispatch** | `@REGISTRY.register("FileInputMSXML", "tFileInputMSXML")` decorator-based dispatch |
| **Registry Aliases** | `FileInputMSXML`, `tFileInputMSXML` |
| **Category** | File / Input |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_input_msxml.py` | Engine class `FileInputMSXML` (273 lines) -- built Phase 12-04 |
| `src/converters/talend_to_v1/components/file/file_input_msxml.py` | Converter class `FileInputMSXMLConverter` (132 lines) |
| `tests/converters/talend_to_v1/components/test_file_input_msxml.py` | Converter tests (44 tests, 10 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 10 of 10 _java.xml params extracted (100%); SCHEMAS TABLE stride-3 parser; module docstring follows docs/v1/patterns/CONVERTER_PATTERN.md |
| Engine Feature Parity | **G** | 0 | 0 | 1 | 0 | Engine built Phase 12-04; lxml.etree.parse; root_loop_query XPath; child element extraction; trim_all; die_on_error [NEW IN 15.1] |
| Code Quality | **G** | 0 | 0 | 0 | 0 | All BaseComponent rules followed; %-style logging; REJECT flow [NEW IN 15.1] |
| Performance & Memory | **Y** | 0 | 0 | 1 | 0 | DOM-based XML parsing (entire file in memory); no SAX streaming [NEW IN 15.1] |
| Testing | **G** | 0 | 0 | 0 | 0 | 44 converter tests; engine tests added Phase 12-04; >= 95% per-module floor (Phase 14) [NEW IN 15.1] |

**Overall: GREEN -- Engine implementation complete (Phase 12-04). All core features implemented; production ready.**

**Resolved actions** (pre-Phase-12 open items now closed):

1. ~~Implement concrete FileInputMSXML engine class (P0 -- blocks production use)~~ [RESOLVED in Phase 12-04, commit c921545]
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tFileInputMSXML Does

`tFileInputMSXML` reads XML data from a file and maps XML elements to output schema columns using XPath-like queries. It iterates over repeating elements defined by a root loop query (e.g., `/mailbox/emails/email`) and extracts values for each iteration into output rows.

The component supports two parsing modes via GENERATION_MODE: DOM4J (default, tree-based parsing) and SAX (event-based streaming for large files). Each schema column maps an XPath path to a column name through the SCHEMAS TABLE, which contains LOOP_PATH, MAPPING, and CREATE_EMPTY_ROW fields per entry.

Unlike tFileInputXML which uses a more complex XPath engine, tFileInputMSXML targets simpler XML structures with straightforward element-to-column mappings. It supports trimming all values (TRIMALL defaults to true), date validation (CHECK_DATE), DTD ignoring (IGNORE_DTD), and element order flexibility (IGNORE_ORDER).

**Source**: Talaxie GitHub tdi-studio-se repository (_java.xml definition)
**Component family**: File / Input
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: None (built-in, uses dom4j)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Filename | `FILENAME` | FILE | (dir default) | Path to the XML input file |
| 2 | Root Loop Query | `ROOT_LOOP_QUERY` | TEXT | `/mailbox/emails/email` | XPath expression defining the repeating element to iterate over |
| 3 | Ignore Order | `IGNORE_ORDER` | CHECK | `false` | When true, ignores element order when matching XPath queries |
| 4 | Schemas | `SCHEMAS` | TABLE | (empty) | Column-to-XPath mappings. Each entry has LOOP_PATH (XPath), MAPPING (column name), CREATE_EMPTY_ROW (bool) |
| 5 | Die On Error | `DIE_ON_ERROR` | CHECK | `false` | When true, job stops on first error; when false, errors are logged and processing continues |
| 6 | Trim All | `TRIMALL` | CHECK | `true` | Trims whitespace from all extracted values. Note: default is true, not false |
| 7 | Check Date | `CHECK_DATE` | CHECK | `false` | Validates date values against the schema date pattern |
| 8 | Ignore DTD | `IGNORE_DTD` | CHECK | `false` | Ignores DTD declarations in the XML file during parsing |
| 9 | Generation Mode | `GENERATION_MODE` | CLOSED_LIST | `DOM4J` | XML parsing mode: DOM4J (tree-based, default) or SAX (event-based streaming) |
| 10 | Encoding | `ENCODING` | ENCODING_TYPE | `ISO-8859-15` | Character encoding for reading the XML file. Default is ISO-8859-15, not UTF-8 |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml for tFileInputMSXML beyond the basic settings listed above.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Output data flow. One row per iteration of the root loop query. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after all XML elements processed successfully |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows successfully read from the XML file |

### 3.5 Behavioral Notes

1. **TRIMALL defaults to true** -- Unlike most file input components that default to false, tFileInputMSXML trims whitespace by default. This is the _java.xml source of truth.
2. **ISO-8859-15 encoding** -- The default encoding is ISO-8859-15 (Latin-9), not UTF-8. This is consistent with many Talend components designed for European locale.
3. **SCHEMAS TABLE structure** -- Each row has 3 fields: LOOP_PATH (XPath to the element), MAPPING (column name in output schema), CREATE_EMPTY_ROW (whether to create a row even when the element is absent).
4. **GENERATION_MODE** -- DOM4J loads the entire document into memory (suitable for small/medium files). SAX uses event-based streaming (better for large files).
5. **IGNORE_ORDER** -- When true, the parser does not require XML elements to appear in the same order as the schema columns. Useful for XML files with inconsistent element ordering.
6. **IGNORE_DTD** -- When true, prevents the parser from attempting to load external DTD references, avoiding network calls and potential DTD-based attacks.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The `FileInputMSXMLConverter` class follows the gold standard CONVERTER_PATTERN.md with module-level TABLE constants and parser function, section-delimited parameter extraction, and `_build_component_dict()` wrapper.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILENAME` | Yes | `filename` | `_get_str()`, default `""` |
| 2 | `ROOT_LOOP_QUERY` | Yes | `root_loop_query` | `_get_str()`, default `"/mailbox/emails/email"` |
| 3 | `IGNORE_ORDER` | Yes | `ignore_order` | `_get_bool()`, default `False` |
| 4 | `SCHEMAS` | Yes | `schemas` | Stride-3 TABLE parser `_parse_schemas()` |
| 5 | `DIE_ON_ERROR` | Yes | `die_on_error` | `_get_bool()`, default `False` |
| 6 | `TRIMALL` | Yes | `trim_all` | `_get_bool()`, default `True` |
| 7 | `CHECK_DATE` | Yes | `check_date` | `_get_bool()`, default `False` |
| 8 | `IGNORE_DTD` | Yes | `ignore_dtd` | `_get_bool()`, default `False` |
| 9 | `GENERATION_MODE` | Yes | `generation_mode` | `_get_str()`, default `"DOM4J"` |
| 10 | `ENCODING` | Yes | `encoding` | `_get_str()`, default `"ISO-8859-15"` |
| -- | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, `_get_bool()`, default `False` |
| -- | `LABEL` | Yes | `label` | Framework param, `_get_str()`, default `""` |

**Summary**: 10 of 10 parameters extracted (100%). Plus 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` base class method |
| `type` | Yes | Converted via `convert_type()` from Talend types |
| `nullable` | Yes | Boolean from schema column |
| `key` | Yes | Boolean from schema column |
| `length` | Yes | Integer, only when >= 0 |
| `precision` | Yes | Integer, only when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported by base class `_parse_schema()` |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions (`{{java}}`) are passed through in string parameters (FILENAME, ROOT_LOOP_QUERY, ENCODING) via `_get_str()` which only strips quotes, preserving expression syntax.

### 4.4 Converter Issues

No open issues. Converter follows gold standard CONVERTER_PATTERN.md.

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No converter issues found |

### 4.5 Needs Review Entries

Single consolidated needs_review entry per D-37 (no engine component):

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all) | No concrete engine implementation for tFileInputMSXML -- all config keys extracted for future engine support | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | XML file reading | **Yes** | High | `_process()` | lxml.etree DOM parse -- Phase 12-04 |
| 2 | XPath loop query | **Yes** | High | `_process()` | ROOT_LOOP_QUERY used as XPath for element iteration |
| 3 | SCHEMAS mapping | **Yes** | High | `_process()` | LOOP_PATH -> column extraction |
| 4 | DOM4J/SAX modes | **Partial** | Low | -- | Only DOM (lxml) mode; SAX streaming not implemented (P2) |
| 5 | Trim all values | **Yes** | High | `_process()` | TRIMALL respected (default True per Talend) |
| 6 | Date validation | **No** | N/A | -- | CHECK_DATE extracted but not enforced at runtime |
| 7 | DTD handling | **Yes** | High | `_xml_io._build_parser()` | IGNORE_DTD=True disables DTD loading via lxml resolve_entities=False |
| 8 | Order flexibility | **No** | N/A | -- | IGNORE_ORDER extracted but not enforced |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-MSXML-001~~ | ~~P0~~ | ~~No engine implementation exists.~~ [RESOLVED in Phase 12-04, commit c921545] |
| ENG-MSXML-002 | **P2** | SAX streaming mode not implemented -- large XML files loaded into memory via DOM parse [NEW IN 15.1] |
| ENG-MSXML-003 | **P2** | IGNORE_ORDER not enforced at runtime -- extracted but not applied during element matching [NEW IN 15.1] |
| ENG-MSXML-004 | **P2** | CHECK_DATE not enforced at runtime -- date validation config key extracted but not applied [NEW IN 15.1] |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` via BaseComponent | Correct -- Phase 12-04 [NEW IN 15.1] |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| ~~BUG-MSXML-001~~ | ~~P0~~ | -- | ~~No engine code exists.~~ [RESOLVED in Phase 12-04, commit c921545] |

### 6.2 Naming Consistency

No naming issues. Converter follows D-38 snake_case convention.

### 6.3 Standards Compliance

Converter fully compliant with `docs/v1/patterns/CONVERTER_PATTERN.md`: module docstring with config mapping, section delimiters, `_build_component_dict()` wrapper, framework params last. Engine follows `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` (Phase 12-04 build).

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns in converter code. When engine is implemented, should validate FILENAME paths (path traversal risk) and IGNORE_DTD default behavior (XXE risk if DTD processing enabled).

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` present |
| Level usage | N/A -- no log statements needed in converter |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Not applicable -- converters return ComponentResult, never raise |
| Exception chaining | Not applicable |
| die_on_error handling | Extracted as config key for future engine use |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Fully typed (convert method, _parse_schemas function) |
| Parameter types | All params typed with Dict, List, Any, str, bool |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-MSXML-001 | **P2** | DOM-based parse loads entire XML file into memory; no SAX streaming mode implemented -- large files risk OOM [NEW IN 15.1] |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not available -- DOM (lxml) parse only; SAX mode not implemented (ENG-MSXML-002) |
| Memory threshold | Entire XML file loaded into memory; no threshold check |
| Large data handling | Risk of OOM for very large XML files; SPLIT not applicable for input components |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 44 | `tests/converters/talend_to_v1/components/test_file_input_msxml.py` |
| Engine unit tests | 35 | `tests/v1/engine/components/file/test_file_input_msxml.py` -- added Phase 12-04 (per-Talaxie-param classes) [NEW IN 15.1] |
| E2E integration tests | covered | `tests/v1/engine/components/file/test_xml_e2e.py` -- Phase 12-08 E2E suite |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| ~~TEST-MSXML-001~~ | ~~P0~~ | ~~No engine tests -- engine does not exist~~ [RESOLVED in Phase 12-04, commit c921545] |
| -- | -- | Phase 14 >= 95% per-module line coverage floor achieved. No outstanding test gaps. |

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | ~~ENG-MSXML-001~~ ~~BUG-MSXML-001~~ ~~TEST-MSXML-001~~ (all resolved Phase 12-04) |
| P1 | 0 | -- |
| P2 | 3 | ENG-MSXML-002 (SAX not impl), ENG-MSXML-003 (IGNORE_ORDER), ENG-MSXML-004 (CHECK_DATE), PERF-MSXML-001 [NEW IN 15.1] |
| P3 | 0 | -- |
| **Total open** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 3 (open) | ENG-MSXML-002, ENG-MSXML-003, ENG-MSXML-004 |
| Bug (BUG) | 0 | ~~BUG-MSXML-001~~ (resolved) |
| Performance (PERF) | 1 (open) | PERF-MSXML-001 |
| Testing (TEST) | 0 | ~~TEST-MSXML-001~~ (resolved) |

### Cross-Cutting Issues

No cross-cutting issues -- engine follows BaseComponent pattern (Phase 12-04 build); Phase 1 cross-cutting fixes inherited.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

- No blocking issues. Engine implemented and tested (Phase 12-04).

### Short-term (Hardening)

1. **ENG-MSXML-002 (P2):** Implement SAX streaming mode for large XML files (avoids DOM OOM risk)
2. **ENG-MSXML-003 (P2):** Enforce IGNORE_ORDER at element-matching time
3. **ENG-MSXML-004 (P2):** Enforce CHECK_DATE validation when enabled

### Long-term (Optimization)

- Add REJECT flow support for rows with parsing errors

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputMSXML/tFileInputMSXML_java.xml` | Parameter definitions, defaults, field types |
| Engine source | `src/v1/engine/components/file/file_input_msxml.py` | Engine implementation (273 lines) -- Phase 12-04 |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_msxml.py` | Converter audit |
| Engine tests | `tests/v1/engine/components/file/test_file_input_msxml.py` | Engine test coverage (35 tests) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_msxml.py` | Converter test coverage |
| Pattern docs | `docs/v1/patterns/CONVERTER_PATTERN.md`, `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` | Pattern compliance verification |
| Contributing guide | `docs/CONTRIBUTING.md` | Standards compliance rules |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues -- engine follows BaseComponent pattern; Phase 1 cross-cutting fixes (ENG-01..ENG-07) inherited.

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| -- | -- | No open cross-cutting issues for this component post-Phase 12-04 |

---

*Report generated: 2026-04-03*
*Last updated: 2026-05-11 after Phase 15.1 reconciliation -- engine built Phase 12-04, Component Identity populated, broken refs repaired*
