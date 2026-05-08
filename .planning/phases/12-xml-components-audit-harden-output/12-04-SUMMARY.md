---
phase: 12
plan: 04
slug: msxml-extractxml-harden-tests
subsystem: engine/components/file, engine/components/transform
tags: [xml, audit-harden, per-param-tests, light-touch, lxml, secure-parser]
requires: [12-01, 12-02]
provides: [file_input_msxml_hardened, extract_xml_fields_hardened, msxml_param_tests, exf_param_tests, msxml_item_fixture]
affects: [12-08]
tech_stack:
  added: []
  patterns: [threshold-switched-dom-stream, secure-xmlparser-factory, per-param-test-discipline]
key_files:
  created:
    - tests/talend_xml_samples/Job_tFileInputMSXML_0.1.item
  modified:
    - src/v1/engine/components/file/file_input_msxml.py
    - src/v1/engine/components/transform/extract_xml_fields.py
    - tests/v1/engine/components/file/test_file_input_msxml.py
    - tests/v1/engine/components/transform/test_extract_xml_fields.py
decisions:
  - "recover=False adopted via _xml_io.secure_xml_parser() for both components -- fix-source policy; malformed XML routes to REJECT instead of silently recovering partial trees"
  - "Multi-schema SCHEMAS TABLE streaming deferred: when SCHEMAS has >1 entry and file exceeds threshold, component logs WARNING and falls back to DOM; single-schema streaming is fully supported"
  - "iterparse_loop_query uses last path segment of root_loop_query as loop_tag for the streaming path -- sufficient for single-schema simple XPath, documented as known limitation for complex predicates"
  - "extract_xml_fields has no file-level threshold (operates on per-row XML strings, not files) -- only secure_xml_parser() centralization applies, no parse_xml_strategy"
metrics:
  duration_minutes: 7
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 4
  completed_date: "2026-05-08"
---

# Phase 12 Plan 04: MSXML + ExtractXMLField Harden + Test Extension Summary

Light-touch audit harden of `tFileInputMSXML` and `tExtractXMLField` (both already on lxml), delegating parser construction to `_xml_io.secure_xml_parser()` and `_xml_io.parse_xml_strategy`, switching `recover=True` to `recover=False`, adding streaming threshold support to `tFileInputMSXML`, and extending both test suites to >= 30 tests per Talaxie javajet parameter discipline. Hand-authored `Job_tFileInputMSXML_0.1.item` E2E fixture for Plan 12-08.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Delegate parser to _xml_io; switch recover flag | c921545 | file_input_msxml.py (+108/-21 net), extract_xml_fields.py (+7/-8 net) |
| Task 2: Extend test_file_input_msxml.py to 35 tests | 41a0591 | test_file_input_msxml.py (+434 lines) |
| Task 3: Extend test_extract_xml_fields.py to 38 tests; add .item fixture | 0a2292e | test_extract_xml_fields.py (+298 lines), Job_tFileInputMSXML_0.1.item (158 lines) |

## Source File Diffs

### file_input_msxml.py (172 LOC before, 280 LOC after, +108 lines net)

Changes:
- Added `from . import _xml_io` import
- Added `xml_streaming_threshold_mb` config key to module docstring and processing
- Replaced `etree.XMLParser(load_dtd=not ignore_dtd, no_network=True, recover=True, encoding=encoding)` with `_xml_io.parse_xml_strategy(filepath, threshold_mb)` + `_xml_io.log_strategy()`
- Added streaming branch: for single-schema jobs, uses `_xml_io.iterparse_loop_query()` when file exceeds threshold
- Added multi-schema fallback: logs WARNING and re-parses with DOM when SCHEMAS has >1 entry
- Added explicit `etree.XMLSyntaxError` catch for malformed XML routing to REJECT
- `recover=True` completely removed (0 occurrences remaining)

### extract_xml_fields.py (261 LOC before, 265 LOC after, +4 lines net)

Changes:
- Added `from ..file import _xml_io` import
- Replaced `etree.XMLParser(recover=True, resolve_entities=False, load_dtd=False, no_network=True)` with `_xml_io.secure_xml_parser()` (4 lines -> 2 lines)
- Updated comment to explain fix-source policy

## Test File Changes

| File | Tests Before | Tests After | New TestParam Classes |
|------|-------------|-------------|----------------------|
| test_file_input_msxml.py | 13 | 35 | 10 (Filename, RootLoopQuery, IgnoreOrder, Schemas, DieOnError, Trimall, CheckDate, IgnoreDtd, GenerationMode, Encoding) + TestRecoverFalseSemantic + TestStreamingPath |
| test_extract_xml_fields.py | 24 | 38 | 6 (XmlField, LoopQuery, Mapping, Limit, DieOnError, IgnoreNs) |

## .item Fixture Validation

`tests/talend_xml_samples/Job_tFileInputMSXML_0.1.item`:
- Hand-authored using `Job_tFileInputXML_0.1.item` as structural template
- Contains `componentName="tFileInputMSXML"` with all 10 Talaxie javajet params
- SCHEMAS TABLE has 1 row (LOOP_PATH, MAPPING, CREATE_EMPTY_ROW)
- FLOW connection to tLogRow_1; 3-column schema (id, subject, sender)
- Converter result: 2 components, 1 flow, 0 validation issues
- `python -m src.converters.talend_to_v1.converter tests/talend_xml_samples/Job_tFileInputMSXML_0.1.item /tmp/Job_tFileInputMSXML.json` exits 0

## Audit Items Closed by This Plan

From 12-01-AUDIT.md (tExtractXMLField open items):

| Audit ID | Status Before | Closed By |
|----------|--------------|-----------|
| ENG-EXF-005 | OPEN: XMLParser recover=True always enabled | CLOSED: _xml_io.secure_xml_parser() uses recover=False |
| NEW-EXF-001 | OPEN: XMLParser lacks secure flags | CLOSED: _xml_io.secure_xml_parser() centralizes resolve_entities=False, no_network=True, load_dtd=False |

From 12-01-AUDIT.md (tFileInputMSXML -- audit said engine absent, but it existed per important_correction):

| Audit ID | Status Before | Closed By |
|----------|--------------|-----------|
| BUG-EXF-002 | OPEN: getiterator() deprecated | NOT APPLICABLE to msxml (msxml did not use getiterator) |
| ENG-EXF-001 | OPEN: limit=0 treated as unlimited | NOT APPLICABLE to msxml (limit not a param for msxml) |
| TEST-EXF-001 | OPEN: No engine unit tests | CLOSED for both components via extended test suites |

Note: The 12-01 AUDIT incorrectly stated `file_input_msxml.py` was absent. After `git reset --hard 87a0ff9`, the file exists at 172 LOC with 13 passing tests (added in an earlier wave). The plan_specifics important_correction note was accurate; the AUDIT section for MSXML was stale relative to HEAD. This plan treated it as light-touch harden, not build-from-scratch.

## OPEN Items Not Closed (deferred per audit table)

- BUG-EXF-002 (`getiterator()` deprecated): Not present in `file_input_msxml.py`. The `extract_xml_fields.py` already uses `root.iter()` (lxml 5.x compatible) -- line 163: `for elem in root.iter():`. BUG-EXF-002 is RESOLVED in the current HEAD.
- ENG-EXF-004 (namespace stripping walks entire tree per row): Still present in `extract_xml_fields.py`. Out of scope for this plan (light-touch only).
- BUG-EXF-003/004 (NaN and non-string handling): Already fixed in current HEAD -- lines 138-148 have explicit `pd.isna()` check and str() coercion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BUG-EXF-002/003/004 already fixed in current HEAD**
- **Found during:** Task 1 code review
- **Issue:** 12-01 AUDIT listed BUG-EXF-002 (getiterator), BUG-EXF-003 (NaN), BUG-EXF-004 (non-string) as OPEN for extract_xml_fields.py. Current HEAD already has `root.iter()` (line 163), `pd.isna()` check (line 139), and `str(xml_string).encode()` (line 159). These are RESOLVED, not OPEN.
- **Fix:** No code change needed; documented as resolved above.
- **Files modified:** None

**2. [Rule 1 - Bug] Audit claimed file_input_msxml.py absent; it exists at 172 LOC**
- **Found during:** worktree_branch_check -- after `git reset --hard 87a0ff9`
- **Issue:** 12-01 AUDIT section "tFileInputMSXML (NO ENGINE FILE)" was written against a different HEAD where the file was absent. After reset to 87a0ff9 (which includes 12-03 work), the file exists.
- **Fix:** Treated as light-touch harden per the important_correction in the plan prompt. No build-from-scratch needed.
- **Files modified:** file_input_msxml.py (harden only)

**3. [Rule 2 - Missing Critical] Multi-schema streaming fallback added**
- **Found during:** Task 1 implementation
- **Issue:** Plan skeleton showed streaming path but did not explicitly specify what happens when SCHEMAS has multiple entries. Multi-schema streaming requires concurrent iterparse tracking which is non-trivial.
- **Fix:** Added multi-schema detection before threshold check; logs WARNING and forces DOM re-parse. Documented as known limitation in module docstring.
- **Files modified:** file_input_msxml.py

## Known Stubs

None. All per-param test bodies are fully implemented. The `check_date` parameter is a Talend informational flag; the engine reads it but does not validate dates (that would require schema-type awareness). This is documented in the module docstring as a stub. The test for `TestParamCheckDate` asserts no crash, which is the correct behavior for a config-only flag.

## Threat Flags

None. Both components now delegate to `_xml_io.secure_xml_parser()` which has `resolve_entities=False`, `no_network=True`, `load_dtd=False`. The threat mitigations T-12-01, T-12-02, and T-12-04 from the plan's STRIDE register are all implemented. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/v1/engine/components/file/file_input_msxml.py | FOUND |
| src/v1/engine/components/transform/extract_xml_fields.py | FOUND |
| tests/v1/engine/components/file/test_file_input_msxml.py | FOUND |
| tests/v1/engine/components/transform/test_extract_xml_fields.py | FOUND |
| tests/talend_xml_samples/Job_tFileInputMSXML_0.1.item | FOUND |
| commit c921545 (feat 12-04 source harden) | FOUND |
| commit 41a0591 (test 12-04 msxml tests) | FOUND |
| commit 0a2292e (test 12-04 exf tests + fixture) | FOUND |
| grep _xml_io.secure_xml_parser file_input_msxml.py >= 1 | PASSED (2 hits) |
| grep _xml_io.secure_xml_parser extract_xml_fields.py >= 1 | PASSED (2 hits) |
| grep _xml_io.log_strategy file_input_msxml.py >= 1 | PASSED (1 hit) |
| recover=True in file_input_msxml.py == 0 | PASSED |
| test_file_input_msxml.py def test_ count >= 30 | PASSED (35) |
| test_extract_xml_fields.py def test_ count >= 30 | PASSED (38) |
| TestParam class count msxml >= 8 | PASSED (10) |
| TestParam class count exf >= 6 | PASSED (6) |
| synthetic_60mb_xml used in msxml tests | PASSED (5 references) |
| No lxml.etree mocks | PASSED |
| All files ASCII-clean | PASSED |
| 73 tests pass | PASSED |
| .item fixture converts cleanly | PASSED (0 validation issues) |
