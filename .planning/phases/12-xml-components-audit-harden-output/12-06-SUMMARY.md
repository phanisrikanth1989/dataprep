---
phase: 12
plan: 06
subsystem: file-output-xml
tags: [xml, file-output, new-component, streaming, sink, converter, lxml, etree]
requirements: [XML-02]

dependency_graph:
  requires: [12-02, 12-04]
  provides: [FileOutputXML-engine, FileOutputXMLConverter, tFileOutputXML-fixture]
  affects: [12-08]

tech_stack:
  added:
    - lxml.etree.xmlfile (incremental XML write, no full-tree buffering)
  patterns:
    - streaming-hook (S-6): _streaming_xmlfile_ctx/_streaming_xmlfile_root_ctx held across chunks
    - sink contract (S-5): _process returns passthrough + globalMap puts
    - dual-name registry: @REGISTRY.register("FileOutputXML", "tFileOutputXML")
    - stride-2 TABLE parsing for MAPPING (SCHEMA_COLUMN_NAME/AS_ATTRIBUTE) and GROUP_BY (COLUMN/LABEL)
    - stride-1 TABLE parsing for ROOT_TAGS (VALUE)

key_files:
  created:
    - src/v1/engine/components/file/file_output_xml.py (520 lines, FileOutputXML engine component)
    - tests/v1/engine/components/file/test_file_output_xml.py (686 lines, 43 engine tests)
    - tests/talend_xml_samples/Job_tFileOutputXML_0.1.item (hand-authored fixture)
  modified:
    - src/converters/talend_to_v1/components/file/file_output_xml.py (376 lines, added FileOutputXMLConverter + 3 TABLE helpers)
    - src/v1/engine/components/file/__init__.py (added FileOutputXML import + __all__ entry)
    - tests/converters/talend_to_v1/components/file/test_file_output_xml.py (added 26 TestFileOutputXMLSimple tests)
    - src/v1/engine/engine.py (added FileOutputXML import + dual-name registry entries)
    - src/v1/engine/base_component.py (updated to version with reset() method)
    - src/v1/engine/global_map.py (updated to version with reset_component() method)

decisions:
  - Always wrap rows in a root element (default "root") even when ROOT_TAGS is empty — XML requires exactly one root; Talend tFileOutputXML behaves the same way
  - engine.py COMPONENT_REGISTRY uses manual static dict pattern (not the ComponentRegistry class), so FileOutputXML must be manually added there in addition to @REGISTRY.register
  - base_component.py and global_map.py updated to newer versions that support reset()/reset_component() needed by streaming state cleanup

metrics:
  duration: "~4 hours (multi-session, 2 context windows)"
  completed: "2026-05-08"
  tasks: 3
  files: 9
---

# Phase 12 Plan 06: FileOutputXML Engine + Converter Summary

New `FileOutputXML` engine component with `etree.xmlfile` incremental streaming write, new `FileOutputXMLConverter` (alongside existing `AdvancedFileOutputXmlConverter`), 43 engine tests + 26 converter tests, and hand-authored `.item` fixture — all per Pitfall P-2 (never buffer full tree).

## What Was Built

### Task 1 — FileOutputXML Engine Component (8c687fa)

New class at `src/v1/engine/components/file/file_output_xml.py` (520 lines):

- Decorated `@REGISTRY.register("FileOutputXML", "tFileOutputXML")` (S-7 dual-name registration)
- `etree.xmlfile()` context manager held on `self._streaming_xmlfile_ctx` / `self._streaming_xmlfile_root_ctx` across chunks (S-6 streaming-hook pattern)
- First chunk opens file + root element context; subsequent chunks reuse the open context
- `reset()` safely closes both context managers via `__exit__(None, None, None)`
- `_process()` returns `{'main': input_data, 'reject': None}` (S-5 sink passthrough)
- GlobalMap puts: `{id}_FILE_NAME` and `{id}_NB_LINE` after each chunk
- Config params: `filename`, `row_tag`, `root_tags`, `mapping` (with `as_attribute`), `encoding`, `split`, `split_every`, `create`, `trim`, `flushonrow`, `flushonrow_num`, `delete_empty_file`, `input_is_document`, `document_col`, `use_dynamic_grouping`, `group_by`, `advanced_separator`, `thousands_separator`, `decimal_separator`
- `_validate_config()`: checks filename presence and bool key types (Rule 12)
- `_write_split()`: stateless split-mode writer (new file per N rows)
- `_write_rows_to_xf()`: shared helper for both streaming and split modes
- Zero uses of `etree.tostring()` or `etree.SubElement()` (P-2 invariant)

### Task 2 — FileOutputXMLConverter + Converter Tests (95c20c0)

Added to `src/converters/talend_to_v1/components/file/file_output_xml.py`:

- `_parse_mapping_table(raw)`: stride-2 SCHEMA_COLUMN_NAME/AS_ATTRIBUTE parser
- `_parse_groupby_table(raw)`: stride-2 COLUMN/LABEL parser
- `_parse_root_tags_table(raw)`: stride-1 VALUE parser
- `@REGISTRY.register("tFileOutputXML")` class `FileOutputXMLConverter(ComponentConverter)`: all 18 javajet params + 2 framework params, `type_name="FileOutputXML"`, sink schema `{"input": ..., "output": []}`

Added 26 tests to `tests/converters/talend_to_v1/components/file/test_file_output_xml.py` as `TestFileOutputXMLSimple`, covering all 18 params + framework params + schema + component structure. All 92 total tests pass (66 pre-existing + 26 new).

### Task 3 — Engine Tests + .item Fixture (4d74084)

`tests/v1/engine/components/file/test_file_output_xml.py` — 43 tests across 18 classes:

- `TestRegistry`, `TestBaseComponent`, `TestValidateConfig`, `TestProcessMain`
- `TestMapping` (attribute vs element output), `TestEncoding`, `TestRowTag`, `TestRootTags`
- `TestCreate`, `TestSplit`, `TestFlushOnRow`, `TestDeleteEmptyFile`
- `TestStreamingHook` (context reuse across chunks), `TestNoBufferAndWrite` (P-2 regression guard)
- `TestSinkContract`, `TestStats` (globalMap NB_LINE), `TestInputIsDocument`, `TestParamRootTagsMultiple`

`tests/talend_xml_samples/Job_tFileOutputXML_0.1.item` — hand-authored fixture:
- `componentName="tFileOutputXML"`, `ROW_TAG="order"`, `ROOT_TAGS` table entry `orders`
- `MAPPING` with 3 columns: `orderId` (AS_ATTRIBUTE=true), `customerName`, `status` (both false)
- `ENCODING=ISO-8859-15`, `LABEL="Write_Orders_XML"`
- Converts cleanly via `python -m src.converters.talend_to_v1.converter` (exit 0)

### Deviation — ETLEngine Registry Wiring (b96fadf, Rule 2)

`src/v1/engine/engine.py` uses a manual static `COMPONENT_REGISTRY` dict separate from the decorator-based `ComponentRegistry`. Without adding entries here, the converter output would fail at execution despite `@REGISTRY.register` being correct. Added:
- `from .components.file import FileOutputXML`
- `'FileOutputXML': FileOutputXML` and `'tFileOutputXML': FileOutputXML` entries

This is a correctness requirement (Rule 2 — missing critical functionality), not a new feature.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Root element required for valid XML**
- **Found during:** Task 3 engine tests
- **Issue:** `LxmlSyntaxError: cannot append trailing element to complete XML document` — writing multiple `<row>` elements at document level is invalid XML (only one root allowed)
- **Fix:** Always open a root element context: use `ROOT_TAGS[0].name` if specified, otherwise default to `"root"` as the wrapper element
- **Files modified:** `src/v1/engine/components/file/file_output_xml.py`
- **Commit:** 8c687fa (part of initial implementation)

**2. [Rule 1 - Bug] P-2 grep false positive in docstring**
- **Found during:** Task 1 acceptance check
- **Issue:** `etree.tostring()` appeared as text in a docstring, triggering the P-2 grep check (`grep -E "^[^#]*..."` catches docstring lines)
- **Fix:** Rewrote docstring to avoid those exact strings while preserving intent
- **Files modified:** `src/v1/engine/components/file/file_output_xml.py`
- **Commit:** 8c687fa (part of initial implementation)

**3. [Rule 3 - Blocking] Missing dependency files in worktree**
- **Found during:** Task 1 setup
- **Issue:** Worktree was branched from `464d2f9` (pre-Phase-12). Files `_xml_io.py`, `component_registry.py`, newer `base_component.py` (with `reset()`), newer `global_map.py` (with `reset_component()`), and all `tests/v1/` were absent
- **Fix:** Copied files from main repo `/Users/aarun/Workspace/Projects/dataprep/`
- **Files modified:** Multiple (see key_files.modified above)
- **Commit:** 4d74084

**4. [Rule 2 - Missing critical functionality] ETLEngine COMPONENT_REGISTRY not wired**
- **Found during:** Task 3 post-execution acceptance check
- **Issue:** `ETLEngine.COMPONENT_REGISTRY` is a manual static dict — `@REGISTRY.register` alone is insufficient; without explicit dict entries the engine cannot dispatch `tFileOutputXML` jobs
- **Fix:** Added import + dual-name entries to `engine.py`
- **Files modified:** `src/v1/engine/engine.py`
- **Commit:** b96fadf

## Test Results

| Suite | Count | Status |
|-------|-------|--------|
| Engine tests (test_file_output_xml.py) | 43 | All pass |
| Converter tests (TestFileOutputXMLSimple) | 26 | All pass |
| Converter tests (pre-existing) | 66 | All pass |
| Combined | 135 | All pass |

## Known Stubs

None — all config params are wired to runtime behavior.

## Threat Flags

None — `FileOutputXML` writes to local filesystem only; no new network endpoints, auth paths, or trust-boundary crossings introduced. `_xml_io.secure_xml_parser()` used for XXE mitigation in `INPUT_IS_DOCUMENT` mode (T-12-01 addressed).

## Self-Check: PASSED

- [x] `src/v1/engine/components/file/file_output_xml.py` exists (520 lines)
- [x] `src/converters/talend_to_v1/components/file/file_output_xml.py` contains `FileOutputXMLConverter`
- [x] `tests/v1/engine/components/file/test_file_output_xml.py` exists (43 tests)
- [x] `tests/converters/talend_to_v1/components/file/test_file_output_xml.py` contains `TestFileOutputXMLSimple` (26 tests)
- [x] `tests/talend_xml_samples/Job_tFileOutputXML_0.1.item` exists with `componentName="tFileOutputXML"`
- [x] Converter exit 0: `python -m src.converters.talend_to_v1.converter tests/talend_xml_samples/Job_tFileOutputXML_0.1.item /tmp/Job_tFileOutputXML.json`
- [x] Commits exist: 8c687fa, 95c20c0, 4d74084, b96fadf
- [x] P-2 clean: no `etree.tostring()` or `etree.SubElement()` in non-comment lines of engine file
- [x] `FileOutputXML` and `tFileOutputXML` in `ETLEngine.COMPONENT_REGISTRY`
