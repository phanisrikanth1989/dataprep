---
phase: 12-xml-components-audit-harden-output
fixed_at: 2026-05-08T00:00:00Z
review_path: .planning/phases/12-xml-components-audit-harden-output/12-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-05-08
**Source review:** `.planning/phases/12-xml-components-audit-harden-output/12-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (3 Critical + 4 Warning + 2 Info; `--fix --all`)
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: Stall Detection Raises Before reset() -- XML Files Left Truncated

**Files modified:** `src/v1/engine/executor.py`
**Commit:** `55d8354`
**Applied fix:** Moved the `reset()` finalization loop (which closes `etree.xmlfile` context managers in FileOutputXML and AdvancedFileOutputXML) to execute BEFORE the stall-detection `ConfigurationError` raise. Previously, the raise at line 158 made the finalization loop at lines 165-177 unreachable on any stall condition, leaving output XML files truncated. The fix also adds a comment explaining the ordering requirement.

---

### CR-02: `_clean_expression` Destroys Valid XPath Predicates via `rstrip("]")`

**Files modified:** `src/v1/engine/components/transform/xml_map.py`, `tests/v1/engine/components/transform/test_xml_map.py`
**Commit:** `0391559`
**Applied fix:** Removed all four `rstrip("]")` calls from `_clean_expression` branches. The `[row1.employee:...]` pattern is fully handled by the `startswith("[") and endswith("]")` branch via `cleaned[1:-1]`. A path ending in `]` is a valid XPath predicate closer (e.g. `./item[1]`) and must not be stripped. Added `TestCleanExpression` regression class (5 tests) covering positional predicates, attribute predicates, text-match predicates, malformed pattern cleaning, and a source-level `rstrip` guard that checks non-docstring executable code.

---

### CR-03: `normalize_nsmap` Only Reads Root Element -- P-5 Regression in XMLMap

**Files modified:** `src/v1/engine/components/transform/xml_map.py`, `tests/v1/engine/components/transform/test_xml_map.py`
**Commit:** `d151932` (combined with WR-01)
**Applied fix:** Replaced the `dict(root.nsmap or {})` single-element read with a full `root.iter()` descendant walk, consistent with the ENG-FIX-004 fix in `file_input_xml._build_nsmap`. Namespace declarations made exclusively on descendant elements are now visible to the XPath engine. The `None` key (lxml default namespace) continues to be mapped to `DEFAULT_NAMESPACE_PREFIX` ("ns0"). Added `TestNormalizeNsmap` regression class (5 tests) covering root namespace, descendant-only namespace, default-namespace sentinel mapping, no-None-key contract, and empty document.

---

### WR-01: Dead Code -- `if None in nsmap` After `normalize_nsmap` Always Evaluates False

**Files modified:** `src/v1/engine/components/transform/xml_map.py`, `tests/v1/engine/components/transform/test_xml_map.py`
**Commit:** `d151932` (combined with CR-03)
**Applied fix:** Replaced `if None in nsmap:` with `if DEFAULT_NAMESPACE_PREFIX in nsmap:` in `_process()`. Since `normalize_nsmap` now (and previously) never returns `None` as a key -- the default namespace is always mapped to the `"ns0"` sentinel -- the old check was permanently false. The new check correctly queries the sentinel key that `normalize_nsmap` uses for default namespaces.

---

### WR-02: `FileOutputXML._write_split` Overcounts Written Rows in `input_is_document` Mode

**Files modified:** `src/v1/engine/components/file/file_output_xml.py`
**Commit:** `98aac1d`
**Applied fix:** Changed `_write_rows_to_xf` return type from `None` to `int`; the method now tracks and returns the actual number of rows successfully written (rows skipped due to `XMLSyntaxError` are not counted). Updated `_write_split` to accumulate `chunk_written` (the returned count) instead of `len(chunk)`, preventing `NB_LINE` overcounting when malformed XML rows are silently skipped in document passthrough mode.

---

### WR-03: `from __future__ import annotations` Missing in `file_output_xml.py` Converter

**Files modified:** `src/converters/talend_to_v1/components/file/file_output_xml.py`
**Commit:** `4eeaf2b`
**Applied fix:** Added `from __future__ import annotations` as the first non-docstring import, per CLAUDE.md convention that all converter module files must begin with this import. The module is now consistent with all sibling converter files in the same package.

---

### WR-04: Unused Import `patch` in `test_file_output_xml.py`

**Files modified:** `tests/v1/engine/components/file/test_file_output_xml.py`
**Commit:** `7c75fbe`
**Applied fix:** Removed `from unittest.mock import patch` (line 33). The symbol was never referenced in the file. The module docstring explicitly declares D-D4 no-mocks discipline; the stray import contradicted that contract.

---

### IN-01: `del ctx` in `iterparse_loop_query` Is Unreachable When Caller Uses `break` (LIMIT Path)

**Files modified:** `src/v1/engine/components/file/_xml_io.py`
**Commit:** `d9b7914`
**Applied fix:** Wrapped the `for _event, element in ctx:` loop in a `try/finally` block so that `del ctx` executes on all exit paths -- including when the caller breaks out of the generator via `GeneratorExit` (LIMIT cap path). In CPython, reference counting releases the `iterparse` context when the generator frame is torn down regardless, so this is correctness-by-intent rather than a resource leak fix. The fix makes the documented cleanup explicit and reliable across all exit paths.

---

### IN-02: Converter `file_output_xml.py` Module Docstring Describes `tAdvancedFileOutputXML` Only

**Files modified:** `src/converters/talend_to_v1/components/file/file_output_xml.py`
**Commit:** `6aee477`
**Applied fix:** Extended the module docstring to document both converters present in the file: `FileOutputXMLConverter` (tFileOutputXML simple variant, 18 unique + 2 framework params, Phase 12-06 addition) and `AdvancedFileOutputXmlConverter` (tAdvancedFileOutputXML, 33 unique + 2 framework params). The docstring now includes the full config mapping for the simple variant plus mentions of its TABLE helpers (`_parse_mapping_table`, `_parse_groupby_table`, `_parse_root_tags_table`).

---

## Skipped Issues

None -- all 9 findings were fixed.

---

## Test Results

**Phase 12 test suite:** 595 passed, 0 failed, 0 skipped

```
tests/v1/engine/components/file/test__xml_io.py               26 passed
tests/v1/engine/components/file/test_file_input_xml.py        30 passed
tests/v1/engine/components/file/test_file_input_msxml.py      35 passed
tests/v1/engine/components/file/test_file_output_xml.py       43 passed
tests/v1/engine/components/file/test_file_output_advanced_xml.py 51 passed
tests/v1/engine/components/file/test_xml_e2e.py                8 passed
tests/v1/engine/components/file/test_xml_coverage_gaps.py     88 passed
tests/v1/engine/components/transform/test_extract_xml_fields.py 38 passed
tests/v1/engine/components/transform/test_xml_map.py         108 passed (inc. 10 new regression tests)
tests/converters/talend_to_v1/components/file/test_file_output_xml.py 103 passed
tests/converters/talend_to_v1/components/transform/test_xml_map.py 65 passed
```

**Coverage gate (>=95% for 7 in-scope modules):**
```
src/v1/engine/components/file/_xml_io.py             100%
src/v1/engine/components/file/file_input_msxml.py    100%
src/v1/engine/components/file/file_input_xml.py       98%
src/v1/engine/components/file/file_output_advanced_xml.py 98%
src/v1/engine/components/file/file_output_xml.py      95%
src/v1/engine/components/transform/extract_xml_fields.py 96%
src/v1/engine/components/transform/xml_map.py         96%
```

All modules at or above 95% gate. Coverage gate: PASS.

---

_Fixed: 2026-05-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
