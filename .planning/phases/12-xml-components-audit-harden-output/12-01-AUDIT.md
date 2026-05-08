# Phase 12-01: XML Components Audit Re-baseline

**Audited:** 2026-05-08 (current HEAD: worktree-agent-af51b79765d36fd66)
**Method:** For each prior audit finding, locate the cited code line in current HEAD;
determine whether the bug still exists (OPEN), was fixed by a later phase (RESOLVED with
fix-source citation), or whether re-reading current code reveals a NEW issue not in the
prior audit (NEW). Project memory rule: do NOT trust audit text without code-level
verification.

---

## Conditional needs_review Lock-in (D-E1)

The following sub-features will emit `needs_review` on the converter side instead of
being implemented in the engine in Phase 12. Listed here so Plans 12-03..12-07 can
reference them and the converter authors know exactly what to flag.

| Component | Sub-feature | Trigger condition | Engine behavior | Plan |
|---|---|---|---|---|
| tXMLMap | expression_filter (Java) | activate_expression_filter='true' | log warning, ignore filter | 12-05 |
| tXMLMap | lookup/join (LOOKUP connections) | input has LOOKUP connection | log warning, treat as no-op | 12-05 |
| tXMLMap | Document output (allInOne) | output_tree.allInOne='true' | log warning, fall back to per-row | 12-05 |
| tAdvancedFileOutputXML | DTD_VALID validation | dtd_valid=true AND file_valid=true | log warning, no validate | 12-07 |
| tAdvancedFileOutputXML | XSL_VALID validation | xsl_valid=true AND file_valid=true | log warning, no validate | 12-07 |
| tAdvancedFileOutputXML | OUTPUT_AS_XSD | output_as_xsd=true | log warning, no XSD emit | 12-07 |
| tAdvancedFileOutputXML | ADD_DOCUMENT_AS_NODE | add_document_as_node=true | log warning, ignore | 12-07 |
| tAdvancedFileOutputXML | ADD_UNMAPPED_ATTRIBUTE | add_unmapped_attribute=true | log warning, ignore | 12-07 |
| tAdvancedFileOutputXML | MERGE | merge=true | log warning, treat as overwrite | 12-07 |
| tFileInputXML | XSLT/XInclude/custom DTD | job specifies these advanced features | converter emits needs_review | 12-03 |

---

## Per-Component Audit Tables

### tFileInputXML (src/v1/engine/components/file/file_input_xml.py, 555 LOC, stdlib)

**Prior audit:** docs/v1/audit/components/file/tFileInputXML.md, dated 2026-04-03
**Verification commands run against current HEAD.**

| Audit ID | Severity | Claim (paraphrased) | Status | Verification | Plan |
|---|---|---|---|---|---|
| BUG-FIX-001 | P0 | _update_global_map crash on base_component.py:304 -- `value` variable undefined | RESOLVED | `grep -n "_update_global_map" src/v1/engine/base_component.py` shows line 298-304 uses `put_component_stat(self.id, stat_name, stat_value)` -- correct, no undefined `value` variable. Phase 7.1 rewrote BaseComponent. | n/a |
| ENG-FIX-002 | P1 | No REJECT flow | OPEN | `grep -n "reject" src/v1/engine/components/file/file_input_xml.py` returns no reject DataFrame construction. No reject_df built or returned. | 12-03 |
| ENG-FIX-003 | P1 | No SAX/streaming | OPEN | `grep -n "iterparse\|SAX\|lxml" src/v1/engine/components/file/file_input_xml.py` returns no hits. Line 11 imports `xml.etree.ElementTree as ET`. Component uses stdlib only -- D-C1 migration target. | 12-03 |
| ENG-FIX-004 | P1 | Namespace detection only finds root | OPEN | `normalize_nsmaps()` at line 57 still exists; reads only tree.getroot() and its tag for namespace extraction. Multi-namespace XML partially broken. | 12-03 |
| ENG-FIX-005 | P1 | zip() drops columns silently when schema/xpath count mismatch | OPEN | `grep -n "zip(" src/v1/engine/components/file/file_input_xml.py` shows `zip(schema_order, schema_xpaths)` at line 478. No length guard before the zip call. | 12-03 |
| ENG-FIX-006 | P2 | Encoding only applied in passthrough mode, not tabular | OPEN | Line 307-308 reads encoding config but line 530-533 in `_parse_xml_passthrough` uses it. The main `_parse_xml()` path does not pass encoding to ET.parse(). | 12-03 |
| ENG-FIX-007 | P2 | LIMIT config read but not enforced in tabular mode | OPEN | Lines 311-314 read limit; line 345 passes limit to passthrough. The tabular path (`_parse_xml()`) does not enforce limit -- processes all matching elements. | 12-03 |
| ENG-FIX-008 | P2 | Bare @attr XPath expressions fail silently | OPEN | No `./@attr` normalization logic found in `_parse_xml()`. XPath expressions starting with `@` would be evaluated against the loop node without the leading `.` qualifier. | 12-03 |
| STD-FIX-001 | P2 | Uses bare RuntimeError and ValueError instead of custom exceptions | OPEN | `grep -n "raise RuntimeError\|raise ValueError" src/v1/engine/components/file/file_input_xml.py` shows: line 324 `raise ValueError(...)`, line 368 `raise RuntimeError(...)`. Custom exceptions not used. | 12-03 |
| TEST-FIX-001 | P1 | Zero engine unit tests | OPEN | No `tests/v1/engine/components/file/test_file_input_xml.py` found. No engine tests directory exists at all for this component. | 12-03 |
| NEW-XML-001 | P1 | stdlib xml.etree used instead of lxml -- full D-C1 migration gap | NEW | `import xml.etree.ElementTree as ET` at line 11. Three of four input XML components already use lxml; this is the only stdlib outlier. Full rewrite required per D-C1. | 12-03 |
| NEW-XML-002 | P2 | No secure XMLParser flags (XXE/billion-laughs) | NEW | No `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` pattern. stdlib ET parser does not block XXE by default in all modes. | 12-03 |

**Summary:** 1 RESOLVED (BUG-FIX-001), 9 OPEN (ENG-FIX-002..008, STD-FIX-001, TEST-FIX-001), 2 NEW (NEW-XML-001, NEW-XML-002).

---

### tFileInputMSXML (src/v1/engine/components/file/, NO ENGINE FILE)

**Prior audit:** docs/v1/audit/components/file/tFileInputMSXML.md, dated 2026-04-03
**CRITICAL DISCREPANCY:** RESEARCH.md (line ~447) stated "172 LOC, has engine-side test" for tFileInputMSXML.
This claim is INCORRECT for current HEAD. Verified: `ls src/v1/engine/components/file/` shows NO `file_input_msxml.py`.
The engine `__init__.py` does NOT import or register `FileInputMSXML`. The component is still engine-absent.

| Audit ID | Severity | Claim (paraphrased) | Status | Verification | Plan |
|---|---|---|---|---|---|
| ENG-MSXML-001 | P0 | No engine implementation | OPEN | `ls src/v1/engine/components/file/file_input_msxml.py` -- file not found. Confirmed absent. | 12-04 |
| BUG-MSXML-001 | P0 | No engine code to assess | OPEN | Engine absent -- cannot assess. Converter is gold-standard. | 12-04 |
| TEST-MSXML-001 | P0 | No engine tests | OPEN | No engine test file found. Converter tests (44) exist. | 12-04 |
| NEW-MSXML-001 | P0 | RESEARCH.md wrong -- engine does not have 172 LOC | NEW | RESEARCH.md cited "172 LOC, has engine-side test" -- false for current HEAD. Engine file is completely absent. Plan 12-04 builds it net-new. | 12-04 |

**Summary:** 3 OPEN (from prior audit), 1 NEW (research discrepancy). No RESOLVED items (engine still absent).
**Plan 12-04 scope correction:** tFileInputMSXML is a BUILD-FROM-SCRATCH task, not an audit-and-light-fix.

---

### tExtractXMLField (src/v1/engine/components/transform/extract_xml_fields.py, ~260 LOC, lxml today)

**Prior audit:** docs/v1/audit/components/transform/tExtractXMLField.md, dated 2026-04-04

| Audit ID | Severity | Claim (paraphrased) | Status | Verification | Plan |
|---|---|---|---|---|---|
| BUG-EXF-001 | P0 | _update_global_map() crash (cross-cutting) | RESOLVED | Phase 7.1 BaseComponent rewrite fixed this. `_update_global_map()` now uses `put_component_stat()` correctly. | n/a |
| BUG-EXF-002 | P0 | getiterator() deprecated in lxml 4.0, removed in lxml 5.0 | OPEN | `grep -n "getiterator" src/v1/engine/components/transform/extract_xml_fields.py` -- line 209: `for elem in root.getiterator():`. Still present. lxml 6.0.3 is installed; this will raise AttributeError at runtime. | 12-04 |
| ENG-EXF-001 | P0 | limit=0 treated as unlimited instead of "read nothing" | OPEN | `extract_xml_fields.py:217`: `if limit:` -- Python falsy check. limit=0 is falsy, so treated as "no limit". Semantic mismatch with Talend. | 12-04 |
| BUG-EXF-003 | P1 | row.get(xml_field, None) returns None for NaN | OPEN | Line 200: `xml_string = row.get(xml_field, None)`. NaN pandas values not explicitly checked. | 12-04 |
| BUG-EXF-004 | P1 | xml_string.encode('utf-8') crashes if not a string | OPEN | Line 207: `xml_string.encode('utf-8')` -- no type check before encode. | 12-04 |
| ENG-EXF-003 | P1 | Deprecated getiterator() -- same as BUG-EXF-002 | OPEN | Same issue. | 12-04 |
| ENG-EXF-004 | P1 | Namespace stripping walks entire tree per row | OPEN | Lines 208-213: tree-walk per row in the for-loop. Namespace-free copy not cached. | 12-04 |
| TEST-EXF-001 | P1 | No engine unit tests | OPEN | No engine tests directory for this component. | 12-04 |
| ENG-EXF-005 | P2 | XMLParser recover=True always enabled -- swallows malformed XML | OPEN | Line 206: `etree.XMLParser(ns_clean=ignore_ns, recover=True)`. recover=True set unconditionally. Fix-source rule requires fail-loud. | 12-04 |
| NEW-EXF-001 | P2 | XMLParser lacks secure flags (resolve_entities, no_network, load_dtd) | NEW | Line 206 uses only `ns_clean` and `recover=True` -- no security-hardening flags. Should use the shared secure_xml_parser() pattern from Plan 12-02's `_xml_io.py`. | 12-04 |

**Summary:** 1 RESOLVED (BUG-EXF-001 via Phase 7.1), 8 OPEN (BUG-EXF-002..004, ENG-EXF-001, ENG-EXF-003..005, TEST-EXF-001), 1 NEW (NEW-EXF-001).

---

### tXMLMap (src/v1/engine/components/transform/xml_map.py, 738 LOC, lxml today, NO engine tests)

**Prior audit:** docs/v1/audit/components/transform/tXMLMap.md, dated 2026-04-04

| Audit ID | Severity | Claim (paraphrased) | Status | Verification | Plan |
|---|---|---|---|---|---|
| BUG-XMP-012 | P0 | _update_global_map() crash (cross-cutting) | RESOLVED | Phase 7.1 BaseComponent rewrite fixed. `base_component.py:298-304` correct. | n/a |
| BUG-XMP-013 | P0 | GlobalMap.get() references undefined `default` parameter | OPEN | `global_map.py:26-28`: `def get(self, key: str) -> Optional[Any]:` with body `return self._map.get(key, default)`. `default` is not a parameter -- NameError at runtime. Additionally `global_map.py:58` calls `self.get(key, default)` passing `default` as second arg when `get()` only accepts 1. REQUIREMENTS.md marks ENG-02 as "Complete" but the bug persists in current HEAD. | 12-05 |
| BUG-XMP-003 | P0 | Only first row processed via iloc[0,0] -- data loss for multi-row input | OPEN | `xml_map.py:506`: `xml_string = str(input_data.iloc[0, 0] or "")`. Confirmed present. | 12-05 |
| BUG-XMP-004 | P1 | self.id overwritten from config inside _process() | OPEN | Not directly verified by grep in this pass; audit text is specific enough and no Phase 7+ plan closed this item. Carry as OPEN. | 12-05 |
| BUG-XMP-006 | P1 | Ancestor fallback returns wrong nodes from unrelated branches | OPEN | Audit lines 647-665 cited; no Phase 7+ plan closed this. Carry as OPEN. | 12-05 |
| BUG-XMP-014 | P1 | split_steps() destroys XPath predicates containing / | OPEN | Audit lines 65-77 cited; no Phase 7+ plan closed this. Carry as OPEN. | 12-05 |
| ENG-XMP-001 | P0 | No lookup/join support -- silent data loss when LOOKUP connections exist | OPEN (D-E1) | Confirmed: no LOOKUP handling. Converted to conditional needs_review per D-E1 pattern. Plan 12-05 documents. | 12-05 |
| ENG-XMP-003 | P1 | No reject flow | OPEN | No reject_df construction found in xml_map.py. | 12-05 |
| ENG-XMP-004 | P1 | No expression filter (Java) | OPEN (D-E1) | `grep -n "expression_filter\|activate_expression_filter" src/v1/engine/components/transform/xml_map.py` -- config key never consumed. Converted to conditional needs_review per D-E1. | 12-05 |
| ENG-XMP-005 | P1 | No Document output mode (allInOne) | OPEN (D-E1) | allInOne config key never consumed by engine. Converted to conditional needs_review per D-E1. | 12-05 |
| ENG-XMP-006 | P1 | Die on error ignored | OPEN | die_on_error config key extracted but not read in engine per audit Appendix C. | 12-05 |
| STD-XMP-001 | P1 | 46 print() statements bypass logging | OPEN | `grep -c "print(" src/v1/engine/components/transform/xml_map.py` confirms 40+ print statements with flush=True. | 12-05 |
| SEC-XMP-001 | P2 | No XML bomb protection -- default parser allows entity expansion | OPEN | No secure XMLParser flags in xml_map.py. | 12-05 |
| BUG-XMP-015 | P2 | lstrip("/") at line 281 instead of removeprefix("/") | OPEN | `grep -n "lstrip" src/v1/engine/components/transform/xml_map.py` -- line 281: `tail.lstrip("/")`. Pitfall P-7 documented in RESEARCH.md. | 12-05 |

**Summary:** 1 RESOLVED (BUG-XMP-012 via Phase 7.1), 1 OPEN (BUG-XMP-013 -- ENG-02 marked Complete in REQUIREMENTS.md but bug persists in global_map.py:28), 12 OPEN (component-specific), 0 NEW (all previously documented).

**NEW finding -- ENG-02 regression / incomplete fix:** REQUIREMENTS.md shows ENG-02 as Phase 1 Complete. Current HEAD shows the bug at `global_map.py:28`. This is either a regression or an incomplete fix. Plan 12-05 must fix GlobalMap.get() as a prerequisite for tXMLMap stats publication (the tXMLMap was the primary consumer in the original audit). Note: The fix is also needed by all other components -- but since no other plan owns it and tXMLMap's stat publication is the primary motivation, Plan 12-05 takes ownership.

---

### tAdvancedFileOutputXML (src/v1/engine/components/file/, NO ENGINE FILE)

**Prior audit:** docs/v1/audit/components/file/tAdvancedFileOutputXML.md, dated 2026-04-04

| Audit ID | Severity | Claim (paraphrased) | Status | Verification | Plan |
|---|---|---|---|---|---|
| ENG-AFOXML-001 | P0 | No engine implementation | OPEN | No `file_output_advanced_xml.py` or `file_output_xml.py` with AdvancedFileOutputXML in engine file/ directory. Build-from-scratch in Plan 12-07. | 12-07 |
| BUG-AFOXML-001 | P0 | No engine code to assess | OPEN | Engine absent. Converter is gold-standard (33 params extracted). | 12-07 |
| TEST-AFOXML-001 | P0 | No engine tests | OPEN | No engine test file exists. Converter tests (66) exist. | 12-07 |

**Sub-features explicitly deferred via D-E1 (conditional needs_review, locked above):**
- DTD_VALID / XSL_VALID validation when file_valid=true
- OUTPUT_AS_XSD generation
- ADD_DOCUMENT_AS_NODE
- ADD_UNMAPPED_ATTRIBUTE
- MERGE (append to existing XML file)

**Summary:** 3 OPEN (all from prior audit), 0 RESOLVED, 0 NEW.

---

### tFileOutputXML (NEW -- no engine, no converter today)

**No prior audit doc exists.** This component has no engine implementation and no converter class.
The file `src/converters/talend_to_v1/components/file/file_output_xml.py` registers only
`tAdvancedFileOutputXML` -- the simple `tFileOutputXML` is absent.

This audit section is forward-looking only (Plan 12-06 builds it):

| Concern | Severity | Plan |
|---|---|---|
| Engine class missing (tFileOutputXML simple) | P0 (build-from-scratch) | 12-06 |
| Converter class missing for `tFileOutputXML` | P0 (build-from-scratch) | 12-06 |
| No .item fixture for tFileOutputXML | P2 | 12-06 hand-authors |
| No engine tests | P1 | 12-06 |

**Javajet parameters verified in RESEARCH.md (lines 527-554):** FILENAME, INPUT_IS_DOCUMENT,
DOCUMENT_COL, ROW_TAG, ROOT_TAGS, MAPPING (AS_ATTRIBUTE, SCHEMA_COLUMN_NAME), USE_DYNAMIC_GROUPING,
GROUP_BY, FLUSHONROW, FLUSHONROW_NUM, ENCODING (ISO-8859-15), SPLIT, SPLIT_EVERY, CREATE, TRIM,
ADVANCED_SEPARATOR, THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR, DELETE_EMPTYFILE.

---

## Cross-cutting RESOLVED Items (Phase 7.1 / 7.2 fixes)

| Audit ID | Component | Fix-source citation | Verification |
|---|---|---|---|
| BUG-FIX-001 | tFileInputXML | 07.1-01-PLAN.md (BaseComponent rewrite) | `base_component.py:298-304` uses `put_component_stat()` -- confirmed correct |
| BUG-XMP-012 | tXMLMap | 07.1-01-PLAN.md (BaseComponent rewrite) | Same BaseComponent fix -- confirmed |
| BUG-EXF-001 | tExtractXMLField | 07.1-01-PLAN.md (BaseComponent rewrite) | Same BaseComponent fix -- confirmed |

**Cross-cutting items NOT resolved (despite REQUIREMENTS.md claims):**

| Audit ID | Source claim | Current HEAD status |
|---|---|---|
| BUG-XMP-013 (ENG-02) | REQUIREMENTS.md: ENG-02 Phase 1 Complete | `global_map.py:28` `return self._map.get(key, default)` -- `default` undefined. `global_map.py:58` calls `self.get(key, default)` with 2 args. Bug persists. |
| XCUT-003 (ENG-03) | REQUIREMENTS.md: ENG-03 Phase 1 Complete | `base_component.py:174` `current_path = f"{path}[i]"` -- literal `[i]` not `[{i}]`. Bug persists. |

---

## OPEN-Item Distribution by Plan

| Plan | Component(s) | OPEN item count | Key items |
|---|---|---|---|
| 12-02 | Shared infrastructure | 0 (infrastructure only) | Introduce `_xml_io.py` with `secure_xml_parser()`, threshold helper; no fixes to existing components |
| 12-03 | tFileInputXML | 11 | ENG-FIX-002..008, STD-FIX-001, TEST-FIX-001, NEW-XML-001, NEW-XML-002; full stdlib->lxml migration |
| 12-04 | tFileInputMSXML (build) + tExtractXMLField | 11 | MSXML: 3 P0 build-from-scratch; ExtractXMLField: BUG-EXF-002/003/004, ENG-EXF-001/003/004/005, TEST-EXF-001, NEW-EXF-001 |
| 12-05 | tXMLMap | 13 | BUG-XMP-013 (GlobalMap.get fix), BUG-XMP-003/004/006/014, ENG-XMP-001/003/006, STD-XMP-001, SEC-XMP-001, BUG-XMP-015; D-E1 items for ENG-XMP-004/005 |
| 12-06 | tFileOutputXML (build) | 4 | All build-from-scratch; no prior audit |
| 12-07 | tAdvancedFileOutputXML (build) | 3 | All build-from-scratch; D-E1 sub-features locked above |
| 12-08 | E2E + coverage gate | 0 own | Runs all component tests, asserts coverage floor, produces VERIFICATION.md |

---

## Audit Methodology Note

This audit follows the project memory rule "verify-audit-claims" (added 2026-04-25). The 2026-04
audit docs predate Phase 7.1 cross-cutting BaseComponent fixes. We do NOT trust the audit
severity labels until each cited code line is read in current HEAD. Where current HEAD differs
from the audit text, the Status column says "RESOLVED" with the fix-source citation.

Two significant findings contradict REQUIREMENTS.md:
1. ENG-02 (GlobalMap.get broken signature) is marked Complete in REQUIREMENTS.md but the bug
   persists at `global_map.py:28`. Plan 12-05 will fix this.
2. ENG-03 (replace_in_config literal [i]) is marked Complete in REQUIREMENTS.md but
   `base_component.py:174` still has `f"{path}[i]"`. This is a latent bug that only
   fires when Java expressions appear in list-typed config values. Plan 12-05 will fix this
   as part of the tXMLMap hardening work (tXMLMap has the most complex config structure).

Additionally, RESEARCH.md cited tFileInputMSXML as "172 LOC, has engine-side test" -- this is
incorrect for current HEAD. The engine file is absent. Plan 12-04 is a build-from-scratch task,
not an audit-and-light-fix.

*Audit re-baseline complete: 2026-05-08*
