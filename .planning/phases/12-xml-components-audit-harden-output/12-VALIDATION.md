---
phase: 12
slug: xml-components-audit-harden-output
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-08
completed: 2026-05-08
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Skeleton produced by /gsd-plan-phase. Planner fills the per-task verification map.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (assumed; project uses `test_*.py` naming) |
| **Config file** | none — implicit pytest discovery |
| **Quick run command** | `pytest tests/v1/engine/components/file/test_file_input_xml.py tests/v1/engine/components/file/test_file_input_msxml.py tests/v1/engine/components/file/test_file_output_xml.py tests/v1/engine/components/file/test_file_output_advanced_xml.py tests/v1/engine/components/transform/test_extract_xml_fields.py tests/v1/engine/components/transform/test_xml_map.py -x -q` |
| **Full suite command** | `pytest tests/v1/engine/components/file tests/v1/engine/components/transform tests/converters/talend_to_v1/components/file tests/converters/talend_to_v1/components/transform --cov=src/v1/engine/components/file --cov=src/v1/engine/components/transform --cov=src/converters/talend_to_v1/components/file --cov=src/converters/talend_to_v1/components/transform --cov-report=term-missing` |
| **Estimated runtime** | ~30-90 seconds (Java bridge tests excluded by default; opt-in via `-m java`) |

---

## Sampling Rate

- **After every task commit:** Run quick command (subset of files touched)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite green; per-module coverage >= 95% for all 6 in-scope XML components
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-T1 | 01 | 0 | XML-01..04 | T-12-01..08 | Audit produced comprehensive OPEN item list | Manual | N/A (audit doc) | 12-01-AUDIT.md | ✅ |
| 12-03-T1 | 03 | 1 | XML-01 | T-12-01,02 | XXE: resolve_entities=False; billion-laughs: load_dtd=False | Unit | `pytest test_xml_io.py -q` | _xml_io.py | ✅ |
| 12-03-T2 | 03 | 1 | XML-01 | T-12-01..04 | FileInputXML replaces RuntimeError with FileOperationError; no lxml mock | Unit | `pytest test_file_input_xml.py -q` | file_input_xml.py | ✅ |
| 12-03-T3 | 03 | 1 | XML-01 | T-12-02 | ignore_ns uses iter() not getiterator() (lxml 5.x compat) | Unit | `pytest test_file_input_xml.py::TestParamIgnoreNS -q` | file_input_xml.py | ✅ |
| 12-04-T1 | 04 | 2 | XML-01,02 | T-12-05,06 | FileInputMSXML streaming path; multi-schema DOM fallback | Unit | `pytest test_file_input_msxml.py -q` | file_input_msxml.py | ✅ |
| 12-04-T2 | 04 | 2 | XML-02 | T-12-01,02 | ExtractXMLField ignore_ns uses iter() not getiterator() | Unit | `pytest test_extract_xml_fields.py -q` | extract_xml_fields.py | ✅ |
| 12-05-T1 | 05 | 3 | XML-02 | T-12-03,04 | BUG-XMP-003: per-row loop replaces iloc[0,0]; 5-row regression | Unit | `pytest test_xml_map.py::TestMultiRowInput -q` | xml_map.py | ✅ |
| 12-05-T2 | 05 | 3 | XML-02 | T-12-03,04 | BUG-XMP-006..015: removeprefix, ancestor fallback, namespace | Unit | `pytest test_xml_map.py -q` | xml_map.py | ✅ |
| 12-05-T3 | 05 | 3 | XML-02 | T-12-03 | No etree.tostring, no print calls, no JavaBridgeManager import | Static | `pytest test_xml_map.py::TestNoIlocZeroZero -q` | xml_map.py | ✅ |
| 12-06-T1 | 06 | 4 | XML-03 | T-12-04 | FileOutputXML etree.xmlfile streaming; no etree.tostring buffering | Unit | `pytest test_file_output_xml.py -q` | file_output_xml.py | ✅ |
| 12-06-T2 | 06 | 4 | XML-03 | T-12-01 | T-12-01 mitigation: secure_xml_parser(recover=False) in doc passthrough | Unit | `pytest test_file_output_xml.py::TestInputIsDocument -q` | file_output_xml.py | ✅ |
| 12-06-T3 | 06 | 4 | XML-03 | T-12-04 | Converter: needs_review entries for 3 deferred sub-features | Unit | `pytest test_file_output_xml.py -q` | file_output_xml.py converter | ✅ |
| 12-07-T1 | 07 | 5 | XML-04 | T-12-04,06 | AdvancedFileOutputXML hierarchical ROOT/GROUP/LOOP streaming; no tostring | Unit | `pytest test_file_output_advanced_xml.py -q` | file_output_advanced_xml.py | ✅ |
| 12-07-T2 | 07 | 5 | XML-04 | T-12-06 | D-E1: 6 conditional needs_review entries in converter | Unit | `pytest test_file_output_xml.py::TestAdvancedFileOutputXmlConverterConditionalNeedsReview -q` | file_output_xml.py converter | ✅ |
| 12-07-T3 | 07 | 5 | XML-04 | T-12-06 | 51 engine tests + .item fixture validate converter+engine pipeline | Unit+Fixture | `pytest test_file_output_advanced_xml.py -q` | test + fixture | ✅ |
| 12-08-T1 | 08 | 6 | XML-01..04 | T-12-01..08 | 6 E2E tests: convert_job + ETLEngine.run_job per component | E2E | `pytest test_xml_e2e.py -q` | test_xml_e2e.py | ✅ |
| 12-08-T2 | 08 | 6 | XML-01..04 | T-12-01..08 | 95% per-module coverage gate for all 7 modules | Coverage | `python -m coverage report --include=[modules] --show-missing` | test_xml_coverage_gaps.py | ✅ |
| 12-08-T3 | 08 | 6 | XML-01..04 | All | Manual checkpoint: verify VERIFICATION.md + coverage table | Manual | N/A | 12-VERIFICATION.md | ✅ |
| 12-08-T4 | 08 | 6 | XML-01..04 | All | ROADMAP+REQUIREMENTS+STATE updated for Phase 12 close-out | State | `gsd-sdk query state.advance-plan` | STATE.md | ✅ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/v1/engine/components/file/test_file_input_xml.py` — COMPLETE (Plan 12-03)
- [x] `tests/v1/engine/components/file/test_file_output_xml.py` — COMPLETE (Plan 12-06)
- [x] `tests/v1/engine/components/file/test_file_output_advanced_xml.py` — COMPLETE (Plan 12-07)
- [x] `tests/v1/engine/components/transform/test_xml_map.py` — COMPLETE (Plan 12-05)
- [x] `tests/talend_xml_samples/Job_tFileOutputXML_0.1.item` — COMPLETE (Plan 12-06)
- [x] `tests/talend_xml_samples/Job_tAdvancedFileOutputXML_0.1.item` — COMPLETE (Plan 12-07)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TBD — planner fills if any audit-surfaced behavior cannot be automated. Default expectation: all phase behaviors have automated verification. | | | |

---

## Validation Sign-Off

- [x] All tasks have automated verify (unit + E2E + coverage)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (4 missing engine test files + 2 missing output `.item` fixtures)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] Per-module line coverage >= 95% for all 7 in-scope modules (D-D2): see 12-VERIFICATION.md
- [x] Per-parameter pos+neg test catalog complete per Talaxie javajet inventory (D-D1)
- [x] E2E `.item` fixture test exists for each of the 6 components (D-D3)
- [x] No mocks of `lxml.etree` itself (D-D4)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** COMPLETE (2026-05-08)
