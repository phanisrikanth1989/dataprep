# Audit Report: tFileOutputXML / FileOutputXML

> **Audited**: 2026-05-11
> **Reconciled**: 2026-05-11 (net-new doc -- no prior audit existed per D-A4)
> **Auditor**: Claude Sonnet 4.6 (automated, Phase 15.1-04)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileOutputXML` |
| **V1 Engine Class** | `FileOutputXML` |
| **Engine File** | `src/v1/engine/components/file/file_output_xml.py` (535 lines -- built FEAT-12-06, commit 5b52a22) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_output_xml.py` (469 lines -- shared with tAdvancedFileOutputXML) |
| **Converter Dispatch** | `@REGISTRY.register("tFileOutputXML")` decorator-based dispatch |
| **Registry Aliases** | `FileOutputXML`, `tFileOutputXML` |
| **Category** | File / XML / Output |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_output_xml.py` | Engine implementation (535 lines -- FEAT-12-06 build, lxml streaming, split-file, sink-contract passthrough) |
| `src/v1/engine/components/file/_xml_io.py` | Shared XML I/O helpers (secure_xml_parser, XXE protection) |
| `src/converters/talend_to_v1/components/file/file_output_xml.py` | Converter class (469 lines, shared with AdvancedFileOutputXmlConverter) |
| `tests/v1/engine/components/file/test_file_output_xml.py` | Engine tests (43 tests, 18 classes) |
| `tests/converters/talend_to_v1/components/test_file_output_xml.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 18 unique + 2 framework = 20 params extracted. TABLE helpers for MAPPING, GROUP_BY, ROOT_TAGS. USE_DYNAMIC_GROUPING and GROUP_BY deferred with needs_review entries. |
| Engine Feature Parity | **Y** | 0 | 1 | 2 | 1 | No REJECT flow for write errors; USE_DYNAMIC_GROUPING/GROUP_BY deferred; ADVANCED_SEPARATOR numeric formatting deferred. Core output (element-per-row, attributes, root wrapper, split, encoding, sink contract) GREEN. |
| Code Quality | **G** | 0 | 0 | 1 | 1 | Streaming-hook reset() closes contexts properly; _write_rows_to_xf shared between streaming and split paths; _bool() coercion helper; _safe_int() fallback. Minor: split mode ignores FLUSHONROW_NUM granularity (always flush per chunk). |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | etree.xmlfile incremental API (never buffers full tree per Pitfall P-2). Streaming hook holds context open across chunks (S-6). Split mode writes each chunk to disk immediately. Minor: iterrows() on large DataFrames. |
| Testing | **G** | 0 | 0 | 0 | 0 | 43 engine tests (18 classes): TestRegistry, TestBaseComponent, TestValidateConfig, TestProcessMain, TestMapping, TestEncoding, TestRowTag, TestRootTags, TestCreate, TestSplit, TestFlushOnRow, TestDeleteEmptyFile, TestStreamingHook, TestNoBufferAndWrite, TestSinkContract, TestStats, TestInputIsDocument, TestParamRootTagsMultiple. >= 95% per-module floor (Phase 14). |

Overall: YELLOW -- Core flat-XML output is production-ready. Three deferred features (REJECT flow, dynamic grouping, advanced separators) limit full Talend parity for edge-case jobs.

**Resolved actions** (none -- this is a net-new component built in Phase 12-06):

No prior audit existed. Component shipped as FEAT-12-06 (commit `5b52a22`). WR-02 (`98aac1d`) fixed `_write_rows_to_xf` return count. WR-03 (`4eeaf2b`) added converter annotation coverage. WR-04 (`7c75fbe`) cleaned up test suite.

**Open actions**:

1. Implement REJECT flow for write-time errors (ENG-WR-05, P1)
2. Implement USE_DYNAMIC_GROUPING / GROUP_BY grouping (ENG-WR-06, P2)
3. Implement ADVANCED_SEPARATOR numeric formatting (ENG-WR-07, P2)

---

## 3. Talend Feature Baseline

### What tFileOutputXML Does

tFileOutputXML writes a DataFrame to an XML file with one configurable element per row. The component supports a simple flat-XML structure: a ROOT_TAGS outer wrapper, a ROW_TAG element per row, and per-column decisions to emit as sub-elements or as attributes of the row element. An optional INPUT_IS_DOCUMENT mode treats each row as a pre-formed XML document string to pass through verbatim. Split-file output slices large datasets across numbered files.

**Source**: Talaxie GitHub `tFileOutputXML/tFileOutputXML_java.xml`
**Component family**: File / XML
**Available in**: Talend Open Studio, Talend Platform
**Required JARs**: Dom4j (for tAdvancedFileOutputXML structured mode), built-in etree/lxml for tFileOutputXML flat mode

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Output schema defining column names and types |
| 2 | File Name | `FILENAME` | FILE | (dir default) | Path to the XML output file |
| 3 | Input is Document | `INPUT_IS_DOCUMENT` | CHECK | false | Treat each row's DOCUMENT_COL as a full XML document string to pass through |
| 4 | Document Column | `DOCUMENT_COL` | TEXT | `""` | Column name holding XML document string (when INPUT_IS_DOCUMENT=true) |
| 5 | Row Tag | `ROW_TAG` | TEXT | `"row"` | XML element name wrapping each output row |
| 6 | Root Tags | `ROOT_TAGS` | TABLE | (empty) | Stride-1 table: VALUE -> name; outermost wrapper elements |
| 7 | Mapping | `MAPPING` | TABLE | (empty) | Stride-2 table: SCHEMA_COLUMN_NAME + AS_ATTRIBUTE per output column |
| 8 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Output file character encoding |
| 9 | Create | `CREATE` | CHECK | true | Overwrite existing file; if false and file exists, raises error |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 10 | Flush on Row | `FLUSHONROW` | CHECK | false | Flush xmlfile context incrementally after each row |
| 11 | Flush Every N Rows | `FLUSHONROW_NUM` | TEXT | `"1"` | Flush granularity (reserved; current engine flushes per-row when FLUSHONROW=true) |
| 12 | Split | `SPLIT` | CHECK | false | Split output into multiple numbered files |
| 13 | Split Every | `SPLIT_EVERY` | TEXT | `"1000"` | Maximum rows per split file |
| 14 | Trim | `TRIM` | CHECK | false | Strip whitespace from document column in INPUT_IS_DOCUMENT mode |
| 15 | Delete Empty File | `DELETE_EMPTYFILE` | CHECK | false | Delete output file if no rows were written |
| 16 | Use Dynamic Grouping | `USE_DYNAMIC_GROUPING` | CHECK | false | [DEFERRED] Dynamic grouping mode |
| 17 | Group By | `GROUP_BY` | TABLE | (empty) | [DEFERRED] Grouping column definitions |
| 18 | Advanced Separator | `ADVANCED_SEPARATOR` | CHECK | false | [DEFERRED] Locale-aware numeric separator config |
| 19 | Thousands Separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | [DEFERRED] Thousands grouping character |
| 20 | Decimal Separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | [DEFERRED] Decimal point character |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input DataFrame rows to write as XML elements |
| `FLOW` (Passthrough) | Output | Row > Main | Sink passthrough -- returns input_data unchanged (S-5) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on component error |

Note: No REJECT connector in tFileOutputXML. Write errors in INPUT_IS_DOCUMENT mode produce a WARNING log and skip the row (no separate reject stream). A REJECT connector would require ENG-WR-05.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_FILE_NAME` | String | After each chunk | Resolved output file path |
| `{id}_NB_LINE` | Integer | After each chunk | Cumulative rows written across all chunks |

### 3.5 Behavioral Notes

1. **Encoding default is ISO-8859-15**, not UTF-8 -- Talend standard default per _java.xml
2. **ROOT_TAGS uses stride-1**: each entry is `{name: str}`; first entry becomes the outermost XML root element
3. **MAPPING uses stride-2**: SCHEMA_COLUMN_NAME + AS_ATTRIBUTE per column; columns absent from MAPPING are still emitted as sub-elements when MAPPING is empty
4. **Sink contract S-5**: `_process()` returns `{'main': input_data, 'reject': None}` -- input DataFrame is returned unchanged
5. **Streaming hook S-6**: etree.xmlfile context is opened on the first `_process()` call and held open across subsequent chunks; `reset()` closes it on iterate re-execution or finalization
6. **Split mode** is stateless: each chunk range written to a numbered file (`{stem}{index}{suffix}`); does not interact with the streaming hook state
7. **INPUT_IS_DOCUMENT mode** parses each row's document through `_xml_io.secure_xml_parser(recover=False)` before re-emitting -- provides T-12-01 XXE mitigation; malformed rows are skipped with WARNING
8. **FLUSHONROW_NUM granularity** not implemented -- when FLUSHONROW=true the engine flushes after every row regardless of FLUSHONROW_NUM value

---

## 4. Converter Analysis

### 4.1 Parameter Extraction Summary

| Extracted As | Config Key | Talend XML Name | Notes |
| -------------- | ------------ | ----------------- | ------- |
| `filename` | `str` | `FILENAME` | Required |
| `input_is_document` | `bool` | `INPUT_IS_DOCUMENT` | Default False |
| `document_col` | `str` | `DOCUMENT_COL` | Default `""` |
| `row_tag` | `str` | `ROW_TAG` | Default `"row"` |
| `root_tags` | `list` | `ROOT_TAGS` | Stride-1 TABLE: VALUE->name |
| `mapping` | `list` | `MAPPING` | Stride-2 TABLE: SCHEMA_COLUMN_NAME + AS_ATTRIBUTE |
| `use_dynamic_grouping` | `bool` | `USE_DYNAMIC_GROUPING` | Default False; [DEFERRED] needs_review |
| `group_by` | `list` | `GROUP_BY` | Stride-2 TABLE; [DEFERRED] needs_review |
| `flushonrow` | `bool` | `FLUSHONROW` | Default False |
| `flushonrow_num` | `str` | `FLUSHONROW_NUM` | Default `"1"` |
| `encoding` | `str` | `ENCODING` | Default `"ISO-8859-15"` |
| `split` | `bool` | `SPLIT` | Default False |
| `split_every` | `str` | `SPLIT_EVERY` | Default `"1000"` |
| `create` | `bool` | `CREATE` | Default True |
| `trim` | `bool` | `TRIM` | Default False |
| `advanced_separator` | `bool` | `ADVANCED_SEPARATOR` | Default False; [DEFERRED] needs_review |
| `thousands_separator` | `str` | `THOUSANDS_SEPARATOR` | Default `","` |
| `decimal_separator` | `str` | `DECIMAL_SEPARATOR` | Default `"."` |
| `delete_empty_file` | `bool` | `DELETE_EMPTYFILE` | Default False |
| `tstatcatcher_stats` | `bool` | `TSTATCATCHER_STATS` | Framework param |
| `label` | `str` | `LABEL` | Framework param |

**Total**: 18 unique + 2 framework = 20 params.

### 4.2 Converter Gaps

| ID | Severity | Description | Status |
| ---- | --------- | ------------- | ------- |
| CONV-WR-001 | P2 | ADVANCED_SEPARATOR / THOUSANDS_SEPARATOR / DECIMAL_SEPARATOR extracted but engine silently ignores them | [NEW IN 15.1] Open -- deferred to ENG-WR-07 |
| CONV-WR-002 | P3 | GROUP_BY TABLE stride-2 COLUMN/LABEL columns extracted but engine ignores grouping | [NEW IN 15.1] Open -- deferred to ENG-WR-06 |

### 4.3 TABLE Helper Quality

Three TABLE helpers implemented in the converter: `_parse_mapping_table` (stride-2, SCHEMA_COLUMN_NAME + AS_ATTRIBUTE), `_parse_groupby_table` (stride-2, COLUMN + LABEL, deferred), `_parse_root_tags_table` (stride-1, VALUE->name). All three handle empty input safely and return empty lists as defaults.

---

## 5. Engine Feature Parity Analysis

### 5.1 Feature Coverage Matrix

| Talend Feature | Implemented | Notes |
| --------------- | ----------- | ------- |
| Flat element-per-row output | Yes | Core path via `_process()` streaming loop |
| ROOT_TAGS wrapper | Yes | First root_tags entry becomes outermost element |
| ROW_TAG element naming | Yes | Configurable via `row_tag` (default "row") |
| MAPPING sub-element vs attribute | Yes | `attr_cols` set built from mapping[].as_attribute |
| INPUT_IS_DOCUMENT passthrough | Yes | Parses via `_xml_io.secure_xml_parser`; skips malformed |
| ENCODING | Yes | Passed directly to etree.xmlfile() |
| SPLIT output | Yes | `_write_split()` generates numbered files |
| SPLIT_EVERY | Yes | `split_every` int coerced via `_safe_int()` |
| CREATE guard | Yes | Raises FileOperationError if create=False and file exists |
| FLUSHONROW | Yes | xf.flush() called after each row when enabled |
| TRIM (doc mode) | Yes | doc.strip() when trim=True in INPUT_IS_DOCUMENT |
| DELETE_EMPTY_FILE | Yes | Deletes file if 0 rows written |
| Sink contract S-5 | Yes | Returns `{'main': input_data, 'reject': None}` |
| GlobalMap FILE_NAME / NB_LINE | Yes | Set after each chunk |
| Streaming hook S-6 | Yes | xmlfile context held across chunks; reset() closes |
| USE_DYNAMIC_GROUPING | No | [DEFERRED] ENG-WR-06 |
| GROUP_BY | No | [DEFERRED] ENG-WR-06 |
| ADVANCED_SEPARATOR | No | [DEFERRED] ENG-WR-07 |
| REJECT flow | No | [DEFERRED] ENG-WR-05 |
| FLUSHONROW_NUM granularity | Partial | Always per-row when FLUSHONROW=true; NUM ignored |

### 5.2 Open Engine Issues

| ID | Severity | Description |
| ---- | --------- | ------------- |
| ENG-WR-005 | P1 | No REJECT connector -- write errors in INPUT_IS_DOCUMENT mode are silently skipped (logged as WARNING) rather than routed to a reject flow |
| ENG-WR-006 | P2 | USE_DYNAMIC_GROUPING / GROUP_BY not implemented -- jobs using dynamic grouping fallback to flat output silently |
| ENG-WR-007 | P2 | ADVANCED_SEPARATOR numeric formatting not implemented -- THOUSANDS_SEPARATOR / DECIMAL_SEPARATOR config keys extracted but ignored by engine |
| ENG-WR-008 | P3 | FLUSHONROW_NUM granularity ignored -- engine flushes every row when FLUSHONROW=true rather than every FLUSHONROW_NUM rows |

---

## 6. Code Quality Review

### 6.1 Method Breakdown

| Method | Lines (approx) | Purpose |
| -------- | -------------- | --------- |
| `__init__` | 18 | Initialize streaming-hook state (6 instance attributes) |
| `reset` | 32 | Close held xmlfile / filehandle contexts; clear streaming state |
| `_bool` | 8 | Coerce config value to bool (handles JSON string 'true'/'false') |
| `_validate_config` | 20 | Presence check for 'filename'; type-coerce check for bool keys |
| `_process` | ~80 | Main write loop: config read, CREATE guard, SPLIT dispatch, streaming hook, row loop |
| `_write_split` | ~45 | Stateless split-file writer; returns total rows written |
| `_write_rows_to_xf` | ~50 | Shared row-write helper for streaming and split paths; returns row count |

### 6.2 Quality Notes

1. **WR-02 fix (commit `98aac1d`)**: `_write_rows_to_xf` now returns the actual rows written instead of None -- prevents NB_LINE overcounting in INPUT_IS_DOCUMENT mode where malformed rows are skipped
2. **_xml_io.secure_xml_parser** provides consistent XXE protection (`resolve_entities=False`, `no_network=True`) across INPUT_IS_DOCUMENT passthrough path
3. **reset() context cleanup**: exits root-element context before xmlfile context (correct inner-to-outer order); exceptions swallowed intentionally to allow finalization even after partial writes
4. **_bool() and _safe_int()** helpers prevent silent failures when converter emits config values as JSON strings vs native bool/int
5. **Minor gap**: `_write_split` does not interact with the streaming-hook state; if SPLIT=true and streaming has already started (from a prior chunk), split mode is skipped and the engine falls back to streaming. This is guarded by `if split and not self._streaming_write_started`.

### 6.3 Type Handling

No explicit pandas dtype coercion on write -- all column values converted via `str(val)` with `pd.isna(val)` null guard (emits empty string for NaN/None/NaT). This is consistent with Talend's flat-XML behavior for string output.

---

## 6.5 Security Notes

| Threat | Mitigation |
| ------- | ----------- |
| XXE in INPUT_IS_DOCUMENT passthrough | `_xml_io.secure_xml_parser(recover=False)` used before re-emitting: `resolve_entities=False`, `no_network=True` (T-12-01) |
| Path traversal on FILENAME | Not mitigated -- relies on OS permissions; `Path.parent.mkdir(parents=True, exist_ok=True)` creates intermediate dirs unconditionally |
| XML injection via column values | Not mitigated -- column values inserted via `etree.xmlfile` API which handles escaping at the lxml level; lxml escapes `<>&"` correctly |

---

## 8. Testing

### 8.1 Engine Test Suite

**File**: `tests/v1/engine/components/file/test_file_output_xml.py`
**Tests**: 43 tests across 18 classes

| Class | Focus |
| ------- | ------- |
| `TestRegistry` | REGISTRY.register aliases (`FileOutputXML`, `tFileOutputXML`) |
| `TestBaseComponent` | Inherits BaseComponent correctly |
| `TestValidateConfig` | Missing filename, invalid bool config keys |
| `TestProcessMain` | Basic element-per-row XML write |
| `TestMapping` | AS_ATTRIBUTE vs sub-element MAPPING |
| `TestEncoding` | Non-default encoding (UTF-8, etc.) |
| `TestRowTag` | Custom ROW_TAG element name |
| `TestRootTags` | ROOT_TAGS wrapper element |
| `TestCreate` | CREATE=False raises FileOperationError on existing file |
| `TestSplit` | SPLIT output generates numbered files |
| `TestFlushOnRow` | FLUSHONROW calls xf.flush() per row |
| `TestDeleteEmptyFile` | DELETE_EMPTY_FILE removes file on 0 rows |
| `TestStreamingHook` | S-6 streaming context held across multiple _process() calls |
| `TestNoBufferAndWrite` | Pitfall P-2: never uses tostring() or SubElement() |
| `TestSinkContract` | S-5: returns input_data unchanged as 'main' |
| `TestStats` | NB_LINE and FILE_NAME in GlobalMap |
| `TestInputIsDocument` | INPUT_IS_DOCUMENT passthrough with malformed-row skip |
| `TestParamRootTagsMultiple` | Multiple ROOT_TAGS entries (only first used) |

### 8.2 Coverage

- Engine module coverage: >= 95% per-module line-coverage floor (Phase 14)
- Converter module coverage: >= 95% per-module line-coverage floor (Phase 14)

### 8.3 Testing Gaps

| ID | Severity | Description |
| ---- | --------- | ------------- |
| TEST-WR-001 | P3 | No test for FLUSHONROW_NUM granularity (deferred feature) |
| TEST-WR-002 | P3 | No test for USE_DYNAMIC_GROUPING / GROUP_BY (deferred feature) |

---

## 7. Build and Conversion History

| Event | Phase | Commit | Description |
| ------- | ------- | ------- | ------------- |
| FEAT-12-06: Engine built | Phase 12-06 | `5b52a22` | FileOutputXML engine implemented from scratch (streaming lxml, sink contract, split mode, INPUT_IS_DOCUMENT) |
| WR-02: _write_rows_to_xf fix | Post Phase 12-06 | `98aac1d` | Fixed _write_rows_to_xf to return written count (was None); prevents NB_LINE overcounting in doc mode |
| WR-03: Converter annotations | Post Phase 12-06 | `4eeaf2b` | Extended converter module docstring to cover FileOutputXMLConverter; IN-02 fix |
| WR-04: Test suite cleanup | Post Phase 12-06 | `7c75fbe` | Test class restructure and naming cleanup |
| Phase 14 coverage floor | Phase 14 | (floor pass) | >= 95% per-module line coverage enforced for file_output_xml.py |
| Phase 15.1-04: Net-new audit | Phase 15.1-04 | (this doc) | First audit doc authored; D-A4 requirement fulfilled |

---

## 9. Issues Summary

See Appendix B (below) for cross-cutting issues tracked across all file/ components.

### 9.1 Cross-Cutting Issues Affecting This Component

| Issue | Status | Notes |
| ------- | ------- | ------- |
| XCUT-001: `_update_global_map()` crash (Phase 1 ENG-01) | Resolved | BaseComponent fix applies; GlobalMap puts confirmed working in TestStats |
| XCUT-002: Encoding default mismatch (ISO-8859-15) | Resolved in converter | Converter emits Talend default; engine reads config |
| XCUT-003: Context variable resolution ordering | N/A | tFileOutputXML filename does use context vars; resolved via BaseComponent context resolution |

---

## 10. Recommendations

### 10.1 Summary

tFileOutputXML / FileOutputXML is production-ready for jobs that use flat XML output (element-per-row), optional root wrappers, attribute/sub-element column mapping, encoding control, split-file output, and INPUT_IS_DOCUMENT passthrough. The sink contract (S-5) and streaming hook (S-6) are correctly implemented and tested.

Three features are deferred and should not appear in production job configs until implemented: USE_DYNAMIC_GROUPING, GROUP_BY, and ADVANCED_SEPARATOR. Jobs requiring those features should remain on Talend until ENG-WR-06 and ENG-WR-07 are resolved.

### 10.2 Blocking Issues

None for core use cases.

### 10.3 Risk Items

| Risk | Severity | Mitigation |
| ------ | --------- | ----------- |
| REJECT flow absent | P1 | Malformed XML rows in INPUT_IS_DOCUMENT mode are silently skipped (WARNING log). Monitor logs in production. |
| Dynamic grouping deferred | P2 | Jobs using USE_DYNAMIC_GROUPING will produce ungrouped flat output without error. Screen job configs before migration. |
| FLUSHONROW_NUM ignored | P3 | All-rows flush when FLUSHONROW=true. Acceptable for most use cases. |

---

## Appendix A: Reference Links

| Resource | Path |
| --------- | ------ |
| Engine implementation | `src/v1/engine/components/file/file_output_xml.py` |
| Converter implementation | `src/converters/talend_to_v1/components/file/file_output_xml.py` |
| XML I/O helpers | `src/v1/engine/components/file/_xml_io.py` |
| Engine tests | `tests/v1/engine/components/file/test_file_output_xml.py` |
| BaseComponent | `src/v1/engine/base_component.py` |
| Exceptions | `src/v1/engine/exceptions.py` |
| Component registry | `src/v1/engine/component_registry.py` |
| Contributing guide | `docs/CONTRIBUTING.md` |
| Manual component authoring | `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` |
| Talaxie source reference | `tFileOutputXML/tFileOutputXML_java.xml` (Talaxie GitHub) |

---

## Appendix B: Cross-Cutting Issue Tracker

This section tracks issues that appear across multiple file/ components. Component-specific items are in Section 5 and Section 6.

| ID | Description | Affects | Status |
| ---- | ------------- | --------- | ------- |
| XCUT-001 | `_update_global_map()` crash (Phase 1 ENG-01) | All engine components | ~~Resolved~~ [RESOLVED Phase 1, ENG-01] |
| XCUT-002 | Encoding default ISO-8859-15 not UTF-8 | All XML file components | ~~Resolved~~ [RESOLVED: Talend standard; converter emits Talend default] |
| XCUT-003 | Context variable resolution ordering | All engine components | ~~Resolved~~ [RESOLVED: BaseComponent three-phase resolution] |
