---
phase: 12
plan: 01
subsystem: xml-audit
tags: [xml, audit, baseline, planning]
requires: []
provides: [12-01-AUDIT.md, xml-requirements]
affects: [plans/12-03, plans/12-04, plans/12-05, plans/12-06, plans/12-07]
tech-stack:
  added: []
  patterns: [audit-first, verify-audit-claims]
key-files:
  created:
    - .planning/phases/12-xml-components-audit-harden-output/12-01-AUDIT.md
    - .planning/REQUIREMENTS.md
  modified: []
decisions:
  - tFileInputMSXML engine is absent in current HEAD (RESEARCH.md claim of 172 LOC was wrong); Plan 12-04 is build-from-scratch not audit-and-fix
  - GlobalMap.get() bug (ENG-02) and replace_in_config [i] bug (ENG-03) still present despite REQUIREMENTS.md marking them Complete; Plan 12-05 owns the fix
  - D-E1 conditional needs_review list locked at 10 entries (3 tXMLMap + 6 tAdvancedFileOutputXML + 1 tFileInputXML)
  - REQUIREMENTS.md pre-existing em-dash unicode chars remain; XML-01..04 additions are ASCII-clean
metrics:
  duration: 45 minutes
  completed: 2026-05-08
---

# Phase 12 Plan 01: XML Components Audit Re-baseline Summary

Re-baselined 5 prior audit docs (dated 2026-04-03..04) against current HEAD and produced
consolidated 12-01-AUDIT.md classifying all findings as RESOLVED/OPEN/NEW.
Added XML-01..XML-04 to REQUIREMENTS.md.

## Audit Findings by Component

### tFileInputXML (file_input_xml.py, 555 LOC, stdlib)

| Classification | Count | Items |
|---|---|---|
| RESOLVED | 1 | BUG-FIX-001 (_update_global_map crash) -- Phase 7.1 |
| OPEN | 9 | ENG-FIX-002..008, STD-FIX-001, TEST-FIX-001 |
| NEW | 2 | NEW-XML-001 (stdlib->lxml migration gap), NEW-XML-002 (no secure XMLParser flags) |

Plan 12-03 owns all OPEN + NEW items. Full stdlib->lxml migration required.

### tFileInputMSXML (NO ENGINE FILE)

| Classification | Count | Items |
|---|---|---|
| RESOLVED | 0 | -- |
| OPEN | 3 | ENG-MSXML-001, BUG-MSXML-001, TEST-MSXML-001 (all build-from-scratch) |
| NEW | 1 | NEW-MSXML-001: RESEARCH.md claim of "172 LOC, has engine-side test" is WRONG -- engine absent in current HEAD |

Plan 12-04 builds tFileInputMSXML from scratch (not audit-and-light-fix as RESEARCH described).

### tExtractXMLField (extract_xml_fields.py, ~260 LOC, lxml)

| Classification | Count | Items |
|---|---|---|
| RESOLVED | 1 | BUG-EXF-001 (_update_global_map crash) -- Phase 7.1 |
| OPEN | 8 | BUG-EXF-002 (getiterator removed in lxml 5.0), BUG-EXF-003/004, ENG-EXF-001 (limit=0 semantic), ENG-EXF-003/004/005, TEST-EXF-001 |
| NEW | 1 | NEW-EXF-001 (XMLParser missing secure flags) |

Plan 12-04 owns all OPEN + NEW items.

### tXMLMap (xml_map.py, 738 LOC, lxml, NO engine tests)

| Classification | Count | Items |
|---|---|---|
| RESOLVED | 1 | BUG-XMP-012 (_update_global_map crash) -- Phase 7.1 |
| OPEN | 13 | BUG-XMP-013 (GlobalMap.get still broken), BUG-XMP-003 (iloc[0,0] data-loss), BUG-XMP-004/006/014, ENG-XMP-001/003/006, STD-XMP-001 (46 print()), SEC-XMP-001, BUG-XMP-015 (lstrip vs removeprefix) |
| NEW | 0 | -- |

D-E1 items (ENG-XMP-004 expression_filter, ENG-XMP-005 allInOne, ENG-XMP-001 lookup/join)
converted to conditional needs_review -- not fixed in Plan 12-05, emitted by converter.
Plan 12-05 owns all remaining OPEN items.

### tAdvancedFileOutputXML (NO ENGINE FILE)

| Classification | Count | Items |
|---|---|---|
| RESOLVED | 0 | -- |
| OPEN | 3 | ENG-AFOXML-001, BUG-AFOXML-001, TEST-AFOXML-001 (all build-from-scratch) |
| NEW | 0 | -- |

Plan 12-07 builds tAdvancedFileOutputXML from scratch.
6 sub-features locked as D-E1 conditional needs_review (see AUDIT.md table).

### tFileOutputXML (NEW -- no prior audit, no engine, no converter)

Forward-looking only:

| Concern | Severity |
|---|---|
| Engine class missing | P0 |
| Converter class missing | P0 |
| No .item fixture | P2 |
| No engine tests | P1 |

Plan 12-06 builds tFileOutputXML from scratch.

## Cross-cutting Resolved Items

| Audit ID | Fix Source |
|---|---|
| BUG-FIX-001 (tFileInputXML) | 07.1-01-PLAN.md -- BaseComponent rewrite |
| BUG-XMP-012 (tXMLMap) | 07.1-01-PLAN.md -- BaseComponent rewrite |
| BUG-EXF-001 (tExtractXMLField) | 07.1-01-PLAN.md -- BaseComponent rewrite |

## Cross-cutting Bugs Still OPEN (contradicting REQUIREMENTS.md)

| Bug | REQUIREMENTS.md claim | Current HEAD reality | Plan to fix |
|---|---|---|---|
| ENG-02: GlobalMap.get() undefined `default` | Phase 1 Complete | `global_map.py:28` still has bug | 12-05 |
| ENG-03: replace_in_config literal `[i]` | Phase 1 Complete | `base_component.py:174` still has bug | 12-05 |

## Conditional needs_review Lock-in (D-E1) -- Final List

10 entries locked:

| Component | Sub-feature | Plan |
|---|---|---|
| tXMLMap | expression_filter (Java) | 12-05 |
| tXMLMap | lookup/join (LOOKUP connections) | 12-05 |
| tXMLMap | Document output (allInOne) | 12-05 |
| tAdvancedFileOutputXML | DTD_VALID validation | 12-07 |
| tAdvancedFileOutputXML | XSL_VALID validation | 12-07 |
| tAdvancedFileOutputXML | OUTPUT_AS_XSD | 12-07 |
| tAdvancedFileOutputXML | ADD_DOCUMENT_AS_NODE | 12-07 |
| tAdvancedFileOutputXML | ADD_UNMAPPED_ATTRIBUTE | 12-07 |
| tAdvancedFileOutputXML | MERGE | 12-07 |
| tFileInputXML | XSLT/XInclude/custom DTD | 12-03 |

## OPEN-Item Plan Distribution

| Plan | Component(s) | OPEN item count |
|---|---|---|
| 12-03 | tFileInputXML | 11 (9 prior + 2 new) |
| 12-04 | tFileInputMSXML (build) + tExtractXMLField | 12 (4 MSXML + 8 ExtractXMLField + 1 new) |
| 12-05 | tXMLMap + GlobalMap.get fix | 13 (12 tXMLMap + 1 cross-cutting) |
| 12-06 | tFileOutputXML (build) | 4 (net-new) |
| 12-07 | tAdvancedFileOutputXML (build) | 3 (net-new) |

**Total OPEN items:** 43 across 5 plans. Zero orphaned findings.

## Requirements Added

- XML-01: 4 input XML components match javajet behavior (with D-E1 conditional needs_review)
- XML-02: New tFileOutputXML engine + converter
- XML-03: New tAdvancedFileOutputXML engine
- XML-04: All 6 components on lxml, threshold-switched DOM/streaming, secure XMLParser flags

## Deviations from Plan

### Auto-fixed Issues

None -- this is an audit-only plan with no code changes.

### Scope Corrections vs RESEARCH.md

**1. [Rule 1 - Bug] tFileInputMSXML engine status corrected**
- **Found during:** Task 1 re-audit
- **Issue:** RESEARCH.md line ~447 stated tFileInputMSXML "172 LOC, has engine-side test". Current HEAD has no file_input_msxml.py in engine. The 2026-04-03 audit doc also stated "No engine implementation". RESEARCH.md was incorrect.
- **Fix:** Reclassified Plan 12-04 as build-from-scratch for MSXML (not audit-and-light-fix). AUDIT.md documents this as NEW-MSXML-001.
- **Files modified:** .planning/phases/12-xml-components-audit-harden-output/12-01-AUDIT.md

**2. [Rule 1 - Bug] ENG-02 and ENG-03 marked Complete in REQUIREMENTS.md but bugs persist**
- **Found during:** Task 1 cross-cutting verification
- **Issue:** REQUIREMENTS.md marks ENG-02 (GlobalMap.get()) and ENG-03 (replace_in_config [i]) as Phase 1 Complete. Current HEAD has both bugs still present.
- **Fix:** Documented in AUDIT.md with verification evidence. Plan 12-05 takes ownership of the fixes as part of tXMLMap hardening.
- **Files modified:** .planning/phases/12-xml-components-audit-harden-output/12-01-AUDIT.md

### REQUIREMENTS.md ASCII check

The acceptance criteria states the file should be ASCII-clean. The original REQUIREMENTS.md
(before any edits) already contained em-dashes and arrows from prior requirement definitions.
My XML-01..04 additions are ASCII-clean. The pre-existing non-ASCII characters were not
introduced by this plan and are out of scope per "Do NOT edit any other line in REQUIREMENTS.md".

## Self-Check: PASSED

- [x] 12-01-AUDIT.md exists and covers all 6 in-scope components
- [x] All prior audit IDs have RESOLVED/OPEN/NEW classification
- [x] Conditional needs_review Lock-in table has 10 entries (>= 9 required)
- [x] OPEN items mapped to plans 12-03..12-07 with no orphans
- [x] REQUIREMENTS.md has 4 new XML- requirements
- [x] Traceability table has 4 XML-0X rows mapped to Phase 12, Pending
- [x] No src/ or tests/ files modified
- [x] Commits: e7b3f80 (AUDIT.md), 2359c5f (REQUIREMENTS.md)
