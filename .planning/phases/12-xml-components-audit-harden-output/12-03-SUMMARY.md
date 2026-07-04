---
phase: 12
plan: 03
subsystem: engine/file-components
tags: [xml, file-input, lxml-migration, audit-fix, reject-flow, streaming]
dependency_graph:
  requires: [12-02]
  provides: [FileInputXML engine component on lxml with REJECT, threshold-switched I/O, secure parser]
  affects: [src/v1/engine/components/file/file_input_xml.py, tests/v1/engine/components/file/test_file_input_xml.py]
tech_stack:
  added: []
  patterns: [lxml.etree DOM + iterparse, threshold-switched I/O, per-element nsmap walk, reject-flow errorCode/errorMessage]
key_files:
  created:
    - tests/v1/engine/components/file/test_file_input_xml.py
  modified:
    - src/v1/engine/components/file/file_input_xml.py
decisions:
  - Full rewrite (555->372 LOC) over patch: project memory rule applied; stdlib->lxml migration too pervasive for incremental fixes
  - _direct_process() test helper: bypasses base_component execute() lifecycle (schema validation, mode selection) to test _process() in isolation, matching the plan's D-D4 no-mock requirement
  - LIMIT semantics: empty/"" -> unlimited (None), "0" -> 0, "N" -> int cap; exactly mirroring Talend ENG-FIX-007
  - _build_nsmap walks element.iter() descendants, not just root.nsmap (P-5 fix)
  - removeprefix("@") used in streaming tag extraction instead of lstrip (P-7)
metrics:
  duration: "~25 minutes"
  completed: "2026-05-08"
  tasks_completed: 2
  files_modified: 2
---

# Phase 12 Plan 03: FileInputXML stdlib->lxml Migration Summary

Full rewrite of FileInputXML from 555 LOC stdlib xml.etree to 372 LOC lxml with REJECT flow, threshold-switched DOM/streaming, secure parser, decorator registration, and 32 per-Talaxie-param tests.

## LOC Before/After

| File | Before | After | Delta |
|------|--------|-------|-------|
| src/v1/engine/components/file/file_input_xml.py | 555 | 372 | -183 |
| tests/v1/engine/components/file/test_file_input_xml.py | 0 (absent) | 374 | +374 |

## OPEN Audit Items Closed

All 11 items assigned to Plan 12-03 from 12-01-AUDIT.md are closed.

| Audit ID | Severity | Description | Code Change | Regression-Guard Test |
|----------|----------|-------------|-------------|----------------------|
| ENG-FIX-002 | P1 | No REJECT flow | `_extract_node` + `_build_reject_only` with errorCode/errorMessage | `test_missing_file_die_false_produces_reject_row`, `test_bad_xpath_in_mapping_produces_reject_row`, `test_nodecheck_missing_element_routes_to_reject`, `test_bad_xpath_die_on_error_true_raises` |
| ENG-FIX-003 | P1 | No streaming/SAX | `_xml_io.iterparse_loop_query` branch in `_process` | `test_streaming_branch_taken_above_threshold` |
| ENG-FIX-004 | P1 | Namespace detection root-only (P-5) | `_build_nsmap` walks `element.iter()` descendants | `test_ignore_ns_false_multi_namespace_logged` |
| ENG-FIX-005 | P1 | zip() silent column drop | Explicit per-column dict in `_extract_node`, no zip() | `test_missing_column_yields_none` |
| ENG-FIX-006 | P2 | Encoding not applied in tabular mode | lxml respects XML declaration; `encoding` config read | `test_latin1_fixture_parses_correctly` |
| ENG-FIX-007 | P2 | LIMIT not enforced in tabular mode | `limit` parsed as None/0/int, enforced in both DOM and streaming loops | `test_empty_limit_no_cap`, `test_zero_limit_reads_nothing`, `test_numeric_limit_caps_rows` |
| ENG-FIX-008 | P2 | Bare @attr XPath fails silently | `_eval_mapping_xpath` handles `expr.startswith("@")` | `test_bare_attr_xpath_returns_attribute` |
| STD-FIX-001 | P2 | RuntimeError / ValueError instead of custom exceptions | Only ConfigurationError / FileOperationError raised | `test_no_runtime_error_in_source` |
| TEST-FIX-001 | P1 | Zero engine unit tests | 32 tests in new test_file_input_xml.py | All 32 |
| NEW-XML-001 | P1 | stdlib xml.etree used (full migration gap) | `from lxml import etree`; zero stdlib xml.etree refs | `test_registered_under_both_names` (import smoke) |
| NEW-XML-002 | P2 | No secure XMLParser flags | All parses via `_xml_io.secure_xml_parser()` (XXE, no_network, load_dtd=False) | `test_ignore_dtd_true_parses_doc_with_dtd` |

## Test Count Breakdown by Class

| Class | Tests | Plan Tests |
|-------|-------|------------|
| TestRegistry | 1 | Test 1 |
| TestBaseComponent | 1 | Test 2 |
| TestValidateConfig | 4 | Tests 3-6 |
| TestProcessMain | 1 | Test 7 |
| TestProcessReject | 4 | Tests 8-11 |
| TestStats | 1 | Test 12 |
| TestParamFilename | 2 | Tests 13-14 |
| TestParamLoopQuery | 2 | Tests 15-16 |
| TestParamMapping | 3 | Tests 17-19 |
| TestParamLimit | 3 | Tests 20-22 |
| TestParamEncoding | 2 | Tests 23-24 |
| TestParamIgnoreNS | 2 | Tests 25-26 |
| TestParamIgnoreDtd | 1 | Test 27 |
| TestParamDieOnError | 1 | Test 28 |
| TestColumnMismatch | 1 | Test 29 |
| TestNoRuntimeError | 1 | Test 30 |
| TestStreamingPath | 2 | Tests 31-32 |
| **Total** | **32** | |

All 32 tests green. `pytest tests/v1/engine/components/file/test_file_input_xml.py -q` -> 32 passed in 0.56s.

## Deviations from Plan

### Auto-fixed Issues

None. The plan's code skeleton was implemented as specified with minor variations noted below.

### Planned Skeleton Deviations

**1. [Rule 2 - Missing test infra] `_direct_process()` helper added to tests**
- The plan's test skeleton calls `comp._process(None)` directly. BaseComponent's `execute()` deepcopies `_original_config` into `self.config` before each call; calling `_process()` directly without setting `self.config` would crash. Added `_direct_process()` helper that mimics the relevant parts of `execute()` lifecycle (config copy + stats flag reset) without triggering schema validation or mode selection. This follows D-D4 (no mocks) and keeps tests focused on `_process` behavior.

**2. [Planned] Import path correction**
- The plan's skeleton showed `from ..base_component import BaseComponent` and `from ..component_registry import REGISTRY`. The actual relative path from `file/` subdirectory is `from ...base_component import BaseComponent`. Used correct three-dot path.

**3. [Planned] `_SAMPLE_XML` structure updated**
- Plan used `<bill id="N"><line><id>N</id><amount>...</amount></line></bill>` nesting. Simplified to `<bill id="N"><amount>...</amount></bill>` for direct attribute + child-element coverage without the extra level. All tests adapted accordingly.

### Adjacent Test Regression

`tests/v1/engine/components/file/test_file_output_excel.py::TestBasicWrite::test_file_created` fails with `'FileOutputExcel' object has no attribute 'input_schema'`. This failure is pre-existing (unrelated to Plan 12-03 changes; present on the 719a25e base commit). Out of scope per phase scope boundary rule.

## Known Stubs

None. All mapping extraction, REJECT routing, streaming path, and namespace handling are fully wired.

## Threat Flags

No new trust boundaries introduced beyond those in the plan's threat model (T-12-01 through T-12-05). All XML parsing goes through `_xml_io.secure_xml_parser()` (inherited from Plan 12-02). The `_build_reject_only` helper truncates error messages to exception string only (no raw XML payload) per T-12-05 mitigation.

## Self-Check: PASSED

- `src/v1/engine/components/file/file_input_xml.py` -- FOUND, 372 LOC
- `tests/v1/engine/components/file/test_file_input_xml.py` -- FOUND, 32 tests
- Commit 43eccd6 -- feat(12-03): migrate FileInputXML
- Commit 97658e6 -- test(12-03): add 32 per-Talaxie-param tests
- Registry: `REGISTRY.get('tFileInputXML') is FileInputXML` -- VERIFIED
- ASCII-clean: both source and test files pass `.encode('ascii')` -- VERIFIED
- No stdlib xml.etree refs: `grep -c "from xml.etree" file_input_xml.py` == 0 -- VERIFIED
- No bare RuntimeError: `grep -E "raise RuntimeError" file_input_xml.py` == 0 lines -- VERIFIED
