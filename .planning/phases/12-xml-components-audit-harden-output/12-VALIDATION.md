---
phase: 12
slug: xml-components-audit-harden-output
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
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
| TBD — planner fills during /gsd-plan-phase. Each task in every PLAN.md must map to a row here. | | | | | | | | | |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/components/file/test_file_input_xml.py` — engine-side test file does NOT exist today; create with stubs for XML-01 (tFileInputXML parity)
- [ ] `tests/v1/engine/components/file/test_file_output_xml.py` — engine-side test file does NOT exist today; create with stubs for XML-03 (tFileOutputXML parity)
- [ ] `tests/v1/engine/components/file/test_file_output_advanced_xml.py` — engine-side test file does NOT exist today; create with stubs for XML-04 (tAdvancedFileOutputXML parity)
- [ ] `tests/v1/engine/components/transform/test_xml_map.py` — engine-side test file does NOT exist today; create with stubs for XML-02 (tXMLMap parity)
- [ ] `tests/talend_xml_samples/Job_tFileOutputXML_*.item` — hand-author minimal output `.item` fixture (D-D5)
- [ ] `tests/talend_xml_samples/Job_tAdvancedFileOutputXML_*.item` — hand-author minimal output `.item` fixture (D-D5)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TBD — planner fills if any audit-surfaced behavior cannot be automated. Default expectation: all phase behaviors have automated verification. | | | |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (4 missing engine test files + 2 missing output `.item` fixtures)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] Per-module line coverage >= 95% for all 6 in-scope XML components (D-D2)
- [ ] Per-parameter pos+neg test catalog complete per Talaxie javajet inventory (D-D1)
- [ ] E2E `.item` fixture test exists for each of the 6 components (D-D3)
- [ ] No mocks of `lxml.etree` itself (D-D4)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
