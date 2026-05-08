# Phase 12 Plan Check

**Checked:** 2026-05-08
**Plans verified:** 12-01..12-08 (8 plans across 6 waves)
**Method:** Goal-backward verification — derived ROADMAP success criteria + CONTEXT decisions + RESEARCH pitfalls, then traced each into the plan task list. Adversarial stance: assume plans fail until evidence proves otherwise.

---

## 1. Verdict

**PASS-WITH-CONCERNS**

The plans collectively will deliver the phase goal: every ROADMAP success criterion has at least one plan owning it, every locked CONTEXT decision (D-A1..D-E2) is honored, and every RESEARCH pitfall (P-1..P-8) has at least one regression-guard test. Decomposition is sound: 8 plans, 6 waves, parallel work in Waves 3 and 5, with the heavy `tXMLMap` fix isolated in Wave 4. Coverage of audit OPEN items maps cleanly into Plans 12-03 .. 12-07.

Concerns that downgrade from PASS to PASS-WITH-CONCERNS:

- **C-1 (HIGH):** Wave 5 parallelism (12-06 ‖ 12-07) writes to **3 shared files**, including the converter module `src/converters/talend_to_v1/components/file/file_output_xml.py`, the engine package `__init__.py`, and the converter test file. Plan 12-07 even omits the converter test file from its `files_modified` frontmatter while Task 2 modifies it. Merge conflicts during execution are virtually guaranteed unless these plans are serialized.
- **C-2 (MEDIUM):** RESEARCH.md `## Open Questions` heading lacks `(RESOLVED)` suffix. All 5 questions have inline "Recommendation:" lines that effectively resolve them, but per the plan-checker rubric (Dimension 11) this is normally a blocker. Treating as a MEDIUM concern because the recommendations are concrete and the plans implement them.
- **C-3 (MEDIUM):** Every plan file ends with stray `</content></invoke>` — tool-call artifacts that leaked into the markdown. Harmless to readers but signals serialization hygiene to fix before adopting these plans as canonical artifacts.
- **C-4 (MEDIUM):** Plan 12-05 has a typo `</antomated>` on line 405 followed by a duplicate `<automated>` block on line 406. Parsers that strip unknown tags will accept this; strict XML parsers will not. Cosmetic but should be fixed.
- **C-5 (LOW):** Plan 12-08 `depends_on: [03, 04, 05, 06, 07]` skips direct deps `01, 02`. Transitively satisfied via 03/04/05; no cycle, but explicit listing would aid the wave scheduler.
- **C-6 (LOW):** Plan 12-04's MSXML streaming branch falls back to DOM when `SCHEMAS` table has multiple entries (line 199–206 of 12-04-PLAN.md). The plan documents this as a known limitation but does not add a regression-guard test for the multi-schema-streaming-fallback warning. Acceptable for v1, surface in Phase 12.1 if production needs multi-schema streaming.

None of these are blockers. Execution can proceed if the user accepts C-1 as a known wave-coordination risk (recommended fix: serialize 12-06 → 12-07 as Wave 5a → Wave 5b, or split the converter file into two modules so the parallel work doesn't collide).

---

## 2. Goal-Backward Coverage — ROADMAP Success Criteria

ROADMAP Phase 12 lists 5 success criteria. Coverage matrix:

| # | ROADMAP Success Criterion | Owning Plan(s) | Coverage Verdict |
|---|---|---|---|
| 1 | tFileInputXML, tExtractXMLField, tXMLMap each pass an audit-vs-Talend report with all gaps fixed; comprehensive unit + integration tests | 12-01 (audit) → 12-03 (FileInputXML), 12-04 (ExtractXMLField), 12-05 (XMLMap) → 12-08 (E2E + coverage gate) | COVERED. Per-component test budgets in 12-03 (≥30), 12-04 (≥30 ExtractXMLField), 12-05 (≥35) match RESEARCH.md "per-component test budgets" table. |
| 2 | tFileOutputXML engine component exists with full Talend feature parity; converter integration verified | 12-06 (engine + converter class + ≥25 engine tests + ≥15 converter tests + .item fixture) | COVERED. Note: ROADMAP did not explicitly list tAdvancedFileOutputXML, but CONTEXT D-A2 added it; Plan 12-07 delivers it. |
| 3 | Real .item fixtures exercise each XML component end-to-end through ETLEngine | 12-04 (Job_tFileInputMSXML) + 12-06 (Job_tFileOutputXML) + 12-07 (Job_tAdvancedFileOutputXML) + 12-08 (E2E test runner across 6 components) | COVERED. 3 of 6 fixtures already exist; 3 are hand-authored across 12-04 / 12-06 / 12-07 per D-D5. |
| 4 | No engine_gap entries remaining for the 4 in-scope XML components | 12-01 (lock-in conditional needs_review list) → 12-05 / 12-07 (engine warns + converter emits needs_review for 9 deferred sub-features per D-E1) | COVERED conditionally. The 9 D-E1 sub-features remain explicit needs_review entries (XSLT, XInclude, expression_filter, lookup, allInOne, dtd_validate, xsl_validate, output_as_xsd, add_document_as_node, add_unmapped_attribute, merge — collapsed per the audit lock-in table). User accepted these as out-of-scope per D-E1; success criterion 4 is satisfied because the only remaining gaps are explicit needs_review, not silent engine_gap. |
| 5 | Per-module coverage of each XML component hits the Phase 14 floor (95%) | 12-08 Task 2 runs `--cov-fail-under=95` on all 7 in-scope modules (6 components + `_xml_io.py`); Task 3 (manual checkpoint) blocks if any module falls short | COVERED. The gate command in 12-08 line 363 includes every in-scope module. |

All 5 success criteria are owned by at least one plan and supported by at least one verifiable artifact.

---

## 3. Decision-Backward Coverage — CONTEXT.md Locked Decisions

CONTEXT.md locks 14 decisions across 5 categories (D-A1..D-E2). Coverage matrix:

| Decision | Locked Behavior | Plan(s) Implementing | Verdict |
|---|---|---|---|
| D-A1 | Audit + harden 4 input components | 12-01 (audit) + 12-03 / 12-04 / 12-05 (harden) | COVERED |
| D-A2 | Build tFileOutputXML simple + tAdvancedFileOutputXML hierarchical | 12-06 + 12-07 | COVERED |
| D-A3 | Total = 6 in-scope components | All component plans together | COVERED |
| D-B1 | Audit-first pattern, Plan 1 produces audit-vs-Talend report | 12-01 produces 12-01-AUDIT.md before any code change | COVERED |
| D-B2 | Reference source = Talaxie javajet templates | RESEARCH.md verifies all 6 javajet param tables; PLAN frontmatters reference them; 12-04 / 12-05 / 12-06 / 12-07 each enumerate their javajet params in `<interfaces>` | COVERED |
| D-B3 | Discovery is part of the phase; manager's "not working" is a hypothesis | 12-01 task 1 says "do NOT trust audit text without code-level verification"; cross-cutting BUG-FIX-001 / BUG-XMP-012/013 expected to be RESOLVED by Phase 7.1 | COVERED |
| D-C1 | Standardize on lxml 5.x across all 6 components | 12-03 fully migrates file_input_xml.py from stdlib to lxml; 12-04 / 12-05 already lxml; 12-06 / 12-07 lxml from inception | COVERED. Note: installed lxml is 6.0.3, RESEARCH.md flags this as superset of "lxml 5.x" — acceptable since pin is `>=4.9,<7`. |
| D-C2 | Threshold-switched DOM/streaming at 50 MB; config knob `xml_streaming_threshold_mb` | 12-02 implements `parse_xml_strategy` + `iterparse_loop_query`; 12-03 / 12-04 wire the threshold via `_xml_io.parse_xml_strategy` + `log_strategy`; 12-05 N/A (per-row strings); 12-06 / 12-07 streaming output via `etree.xmlfile` | COVERED. P-4 mitigation log line is testable. |
| D-C3 | Output mirrors recent base-component streaming pattern (commit bb5b97f) | 12-06 / 12-07 use `_streaming_xmlfile_ctx` + `_streaming_write_started` + `reset()` per S-6 | COVERED |
| D-C4 | `defusedxml.lxml` wrappers at every input boundary | NOT IMPLEMENTED LITERALLY. RESEARCH.md P-1 + Assumption A3 identify defusedxml.lxml as upstream-deprecated; plans substitute `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` via `_xml_io.secure_xml_parser()`. Recorded in CONTEXT.md and confirmed via plan-check; substitution is functionally equivalent for XXE / billion-laughs / network mitigations. | INTENTIONALLY DEVIATED — D-C4 obsolete, substitution documented and tested |
| D-C5 | No fallback to stdlib; raise ConfigurationError if lxml missing | All plans use `from lxml import etree` directly; absence raises `ImportError` at import time, which engine handles. No conditional stdlib fallback exists. | COVERED |
| D-D1 | Per-parameter positive + negative tests | Every component test plan organizes around `class TestParam<X>` per Talaxie javajet param: 12-03 (≥12 classes), 12-04 (≥8 + ≥6), 12-05 (multiple), 12-06 (multiple), 12-07 (multiple) | COVERED |
| D-D2 | 95% per-module line coverage floor | 12-08 Task 2 runs `--cov-fail-under=95` on all 7 in-scope modules | COVERED. Risk: per Assumption A4, `xml_map.py` (738 LOC) may struggle to hit 95%; mitigation = either drop to 90% locally or add tests. Plans accept this risk explicitly. |
| D-D3 | E2E `.item` fixture per component | 12-04 / 12-06 / 12-07 hand-author missing fixtures; 12-08 runs the cross-component E2E suite | COVERED |
| D-D4 | No mocks of `lxml.etree`; real I/O wherever feasible | Every test plan asserts `grep ... patch.*lxml\.etree | wc -l == 0` in acceptance criteria | COVERED |
| D-D5 | Hand-author minimal `.item` fixtures for output components | 12-06 (Job_tFileOutputXML) + 12-07 (Job_tAdvancedFileOutputXML) | COVERED |
| D-E1 | Conditional `needs_review` for unsupported sub-features | 12-01 locks the 9-entry list; 12-05 wires 3 (xml_map: expression_filter / lookup / allInOne); 12-07 wires 6 (advanced_xml: dtd / xsl / output_as_xsd / add_document_as_node / add_unmapped_attribute / merge); each plan has dedicated `TestConditionalWarn*` classes | COVERED |
| D-E2 | Phase 12 does NOT block on Phase 13; no Java-bridge JAR rebuild | 12-05 acceptance criteria explicitly grep for zero `JavaBridgeManager` / `java_bridge` / `execute_one_time_expression` imports in xml_map.py; threat T-12-06 documents the contract | COVERED. The plan grants `xfail` permission for any single tXMLMap test that trips on a signature manager is changing — this is documented but no specific xfail marker appears in test plans, which is fine (they assume current bridge surface works). |

**Net coverage:** 14 / 14 decisions either implemented or formally deviated with audit trail (D-C4 substitution).

### Out-of-Scope items NOT in plans (Deferred Ideas — verified absent)

| Deferred Idea | Verified Absent? |
|---|---|
| `tWriteXMLField` | Yes — no plan touches it |
| Bridge JAR rebuild | Yes — D-E2 enforced via grep test |
| XSLT / XInclude / XML 1.1 / custom DTD runtime | Yes — converter emits needs_review (D-E1); engine never invokes XSLT |
| Real Citi production .item files | Yes — only hand-authored fixtures planned |
| Large-XML perf fixtures (>50 MB committed) | Yes — `synthetic_60mb_xml` is generated programmatically in conftest, not committed |

---

## 4. Pitfall Coverage — RESEARCH.md P-1 .. P-8

| Pitfall | Description | Plan(s) Guarding Against | Regression Test |
|---|---|---|---|
| P-1 | `defusedxml.lxml` deprecated | 12-02 substitutes via `_xml_io.secure_xml_parser`; 12-04 / 12-05 / 12-03 delegate; grep test in every plan asserts `from defusedxml` count == 0 | YES — multiple grep tests |
| P-2 | "Streaming" output that buffers full tree | 12-06 / 12-07 use `etree.xmlfile`; both plans have `TestNoBufferAndWrite` class asserting zero `etree.tostring(` and zero `etree.SubElement(` in source | YES — explicit regression-guard class |
| P-3 | iterparse element-clearing bugs | 12-02's `iterparse_loop_query` does `element.clear(keep_tail=True)` + sibling cleanup; 12-02 Task 2 Test 11 uses `tracemalloc` to assert peak < 100 MB on a 60 MB file | YES — tracemalloc-bounded streaming test |
| P-4 | Threshold "advisory not enforced" | 12-02 implements `log_strategy` ASCII INFO line; 12-03 / 12-04 emit it at decision site; tests assert `caplog` contains `strategy=stream` / `strategy=dom` | YES — caplog-spy tests |
| P-5 | Namespace handling — root-only nsmap | 12-03 implements `_build_nsmap` walking all descendants; Test 25 / 26 cover ignore_ns=true and multi-namespace | YES |
| P-6 | tXMLMap iloc[0,0] data loss (BUG-XMP-003) | 12-05 Task 1 replaces with per-row loop; Task 3 has `TestMultiRowInput::test_5_row_document_input_yields_per_row_output` and `TestNoIlocZeroZero` grep guard; 12-08 Task 1 runs the regression at E2E level | YES — three layers of regression coverage |
| P-7 | `lstrip("/")` vs `removeprefix("/")` | 12-05 Task 1 fixes line ~281; Task 3's `TestNoLstripStringArg` greps for multi-char lstrip | YES |
| P-8 | stdlib→lxml semantic drift in tFileInputXML | 12-03 plan calls for batch-convert / diff regression catalog; threat T-12-A2 documents the verify-source rule | PARTIAL. The plan describes the catalog-and-diff approach in prose but does not list it as a discrete acceptance-criterion bullet. **Recommendation:** elevate to an explicit task or acceptance criterion in 12-03 or 12-08 — current state relies on per-test pos+neg coverage to surface drift. |

**Net pitfall coverage:** 7/8 with explicit regression guards; P-8 covered indirectly via per-param tests but not via a dedicated stdlib-vs-lxml diff harness. LOW concern given test breadth.

---

## 5. Per-Plan Review

### Plan 12-01: Re-audit & baseline (Wave 1)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | Single artifact (12-01-AUDIT.md) + REQUIREMENTS.md edits; correctly scoped to "audit, no code change" |
| File / dependency correctness | PASS | depends_on: [] correct for Wave 1 |
| Task verifiability | PASS | Both tasks have `<automated>` grep-based verification; no Wave 0 dependency needed (this IS Wave 0/1) |
| Threat model | PASS | T-12-A1 / T-12-A2 acknowledge audit-doc trust boundaries |
| Risks called out | PASS | "Project memory rule verify-audit-claims" cited; OPEN-Item Distribution table forces every audit row to map to a downstream plan |

Concern (LOW): The OPEN-Item Distribution table maps to plans 12-03..12-07; should also implicitly cover 12-08's role as the verification gate. Cosmetic.

### Plan 12-02: `_xml_io.py` shared helper (Wave 2)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | 4 helpers (secure_xml_parser, parse_xml_strategy, iterparse_loop_query, log_strategy) directly support D-C2 / D-C4 / P-1..P-4 |
| File / dependency correctness | PASS | depends_on: [01] is correct; 01's audit informs which OPEN items 02 must support |
| Task verifiability | PASS | 18+ unit tests including XXE / billion-laughs real payloads, tracemalloc-bounded streaming test |
| Threat model | PASS | T-12-01 / 02 / 04 / 05 mapped; T-12-03 explicitly accepted as out-of-scope (path traversal) |
| Risks called out | PASS | Synthetic 60 MB fixture is session-scoped + size-asserted to prevent flakiness |

### Plan 12-03: tFileInputXML lxml migration (Wave 3)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | Full rewrite-over-patch matches user's `feedback_rewrite_over_patch` memory rule; closes 9 OPEN audit items |
| File / dependency correctness | PASS | depends_on: [01, 02] correct; runs in parallel with 12-04 (different files) |
| Task verifiability | PASS | 32-behavior contract; per-Talaxie-param `TestParam*` classes; streaming test uses synthetic_60mb_xml from 12-02 conftest |
| Threat model | PASS | T-12-01 / 02 / 03 / 04 / 05 mapped; redact-XML-content guideline noted |
| Risks called out | YES — flagged as HIGH risk (full rewrite, 555 LOC); allocated its own Wave 3 slot for context budget |

Concern (LOW): The "stdlib→lxml semantic drift" catalog (P-8) is discussed in prose at line 700+ but not encoded as a discrete task or acceptance bullet. Per-param pos+neg tests partially cover it. Recommend elevating drift-catalog to an explicit acceptance criterion if production-job parity is critical.

### Plan 12-04: tFileInputMSXML + tExtractXMLField light-touch (Wave 3)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | Light-touch parser-helper delegation + per-param test extension + new Job_tFileInputMSXML fixture |
| File / dependency correctness | PASS | depends_on: [01, 02] correct; parallel to 12-03 (different files) |
| Task verifiability | PASS | All 3 tasks have `<automated>` blocks; existing test counts (13 + 24) and target counts (≥30 each) explicit |
| Threat model | PASS | T-12-01 / 02 / 04 / 05 mapped |
| Risks called out | YES — multi-schema-streaming-fallback noted as known limitation; recover=True → recover=False explicitly switched per fix-source policy |

Concern (LOW, C-6 above): Multi-schema MSXML streaming fallback path lacks a dedicated regression-guard test for the warning log line.

### Plan 12-05: tXMLMap heavy fix (Wave 4)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | Closes 7 OPEN audit items + 2 pitfalls (P-6, P-7); D-E1 conditional warn-and-ignore wired |
| File / dependency correctness | PASS | depends_on: [01, 02] correct; isolated in Wave 4 per `feedback_extensive_questions_complex_phases` |
| Task verifiability | MOSTLY PASS — typo `</antomated>` on line 405 + duplicate `<automated>` block on line 406. Strict XML parsers will reject; lenient parsers will pick the second valid block (identical content). | C-4 above |
| Threat model | PASS | T-12-06 (RCE via expression_filter) explicitly mitigated by D-E1 deferral |
| Risks called out | YES — flagged as HIGH risk (738 LOC, no test net); 35-test target with regression-guard classes for each audit ID |

Acceptance criterion grep count `>= 3` for `logger.warning` lines is a soft check — could allow only 1 of the 3 D-E1 warns to be present and still pass. Recommend tightening to `>= 3 distinct warn keywords` (expression_filter, lookup, allInOne).

### Plan 12-06: tFileOutputXML simple (Wave 5)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | New engine + new converter class + .item fixture + 25+15 tests |
| File / dependency correctness | PARTIAL — see C-1. Modifies 3 files shared with 12-07. depends_on: [02, 04] correct. | C-1 above |
| Task verifiability | PASS | TestNoBufferAndWrite (P-2 regression-guard), TestSinkContract (S-5), TestStreamingHook (S-6) all explicit |
| Threat model | PASS — except T-12-01 row notes the bare `etree.fromstring` in INPUT_IS_DOCUMENT mode and asks executor to add `parser=_xml_io.secure_xml_parser()`. The Task 1 action draft does NOT pass `parser=` to `etree.fromstring` (line ~370 of plan). | LOW — noted as "executor cross-reference" but not enforced via acceptance criterion |
| Risks called out | YES — Pitfall P-2 regression class explicit |

Concern (MEDIUM, C-1): Wave 5 conflict with 12-07. 12-06 adds `FileOutputXMLConverter` to the converter module + `__init__.py` export + new converter test class — 12-07 separately augments the same converter module + same `__init__.py` + same converter test file.

Concern (LOW): T-12-01 mitigation note about `etree.fromstring(parser=_xml_io.secure_xml_parser())` is advisory, not enforced. Should be an acceptance-criterion grep.

### Plan 12-07: tAdvancedFileOutputXML hierarchical (Wave 5)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | Hierarchical engine + 6 D-E1 needs_review additive; 35+9 tests |
| File / dependency correctness | PARTIAL — `files_modified` frontmatter omits `tests/converters/talend_to_v1/components/file/test_file_output_xml.py` even though Task 2 modifies it. Also conflicts with 12-06 on 3 shared files. depends_on: [02, 04] correct. | C-1 above + frontmatter omission |
| Task verifiability | PASS | TestNoBufferAndWrite, TestConditionalWarn* (6 classes) explicit |
| Threat model | PASS | T-12-06 (D-E1 deferral) explicitly mitigated |
| Risks called out | PASS |

Recommendation: Add `tests/converters/talend_to_v1/components/file/test_file_output_xml.py` to 12-07's `files_modified` frontmatter. Either serialize 12-06 → 12-07 sequentially or split the converter module so they don't collide.

### Plan 12-08: E2E + coverage gate (Wave 6)

| Dimension | Verdict | Notes |
|---|---|---|
| Goal alignment | PASS | 6 E2E tests, 95% coverage gate, manual checkpoint, ROADMAP / REQUIREMENTS / STATE updates |
| File / dependency correctness | PARTIAL — depends_on: [03, 04, 05, 06, 07] omits direct deps on 01 / 02. Transitively satisfied. | C-5 above |
| Task verifiability | PASS | Coverage gate is `--cov-fail-under=95` (deterministic); E2E tests use real `convert_job + run_job` per D-D4 |
| Threat model | PASS | T-12-A3 (false-green coverage), T-12-A4 (mock contamination) mapped |
| Risks called out | YES — manual checkpoint blocks if any module < 95%; explicit `/gsd-plan-phase 12 --gaps` fallback path |

---

## 6. Wave Dependency Graph

```
                Wave 1: 12-01 (audit, no code)
                  |
                  v
                Wave 2: 12-02 (_xml_io shared helper + tests)
                  |
                  +-----------+
                  |           |
                  v           v
        Wave 3: 12-03      12-04
                (tFileInputXML)   (tFileInputMSXML + tExtractXMLField)
                  |           |
                  +-----+-----+
                        |
                        v
                Wave 4: 12-05 (tXMLMap heavy fix)
                        |
                  +-----+-----+
                  |           |
                  v           v
        Wave 5: 12-06      12-07
                (tFileOutputXML)   (tAdvancedFileOutputXML)
                  |           |
                  +-----+-----+
                        |
                        v
                Wave 6: 12-08 (E2E + coverage gate + manual checkpoint)
```

**DAG check:** No cycles. depends_on declarations are valid (every reference resolves to an earlier plan).

**Parallelism check:**
- Wave 3 (12-03 ‖ 12-04): SAFE — different source files (`file_input_xml.py` vs `file_input_msxml.py` + `extract_xml_fields.py`).
- Wave 5 (12-06 ‖ 12-07): UNSAFE — 3 shared files. C-1 documents the conflict.

**Wave 4 isolation:** 12-05 in its own wave is justified per `feedback_extensive_questions_complex_phases` and per RESEARCH.md decomposition recommendation.

**Soft-dependency note:** 12-06 / 12-07 declare `depends_on: [02, 04]` but the dependency on 04 is "per-param test discipline established", not a hard artifact dependency. Could in principle move to Wave 4 to parallelize with 12-05, but the conservative dependency is fine.

---

## 7. Concerns Summary

### HIGH

**C-1 (Wave 5 parallel-write conflict).** Plans 12-06 and 12-07 both modify:
- `src/converters/talend_to_v1/components/file/file_output_xml.py` (06 adds new class; 07 augments existing class)
- `src/v1/engine/components/file/__init__.py` (both add new exports)
- `tests/converters/talend_to_v1/components/file/test_file_output_xml.py` (06 adds TestFileOutputXMLSimple; 07 adds TestAdvancedFileOutputXmlConverterConditionalNeedsReview — but 07's frontmatter omits this file)

**Recommended fix (pick one):**
1. Serialize: re-declare 12-07 in Wave 6, OR set 12-07 `depends_on: [02, 04, 06]` so it waits for 12-06 to land before starting.
2. Split files: move `AdvancedFileOutputXmlConverter` into its own converter module (`file_output_advanced_xml.py` on the converter side) and migrate the converter test class similarly. Then the parallel work doesn't collide.
3. Accept conflict: warn the executor that Wave 5 needs sequential merge into the converter module + `__init__.py`.

Option 1 is the cheapest and matches Phase 11 precedent.

### MEDIUM

**C-2.** `## Open Questions` heading lacks `(RESOLVED)` suffix — cosmetic but flagged as a Dimension 11 blocker per the rubric. Each question has a "Recommendation:" line that the plans implement. Mitigation: add `(RESOLVED)` to the heading or rename the section.

**C-3.** All 8 plan files end with stray `</content></invoke>` artifacts. Mitigation: clean up before committing as canonical.

**C-4.** Plan 12-05 line 405 typo `</antomated>`; line 406 duplicate `<automated>` block (identical content to line 405). Mitigation: delete line 405's malformed block, keep line 406's correct block.

### LOW

**C-5.** Plan 12-08 `depends_on: [03, 04, 05, 06, 07]` skips direct refs to 01, 02 (transitively satisfied).

**C-6.** Plan 12-04 multi-schema-streaming fallback lacks a dedicated regression-guard test for the warning log line.

**C-7.** Plan 12-06 T-12-01 mitigation note (use `_xml_io.secure_xml_parser()` for INPUT_IS_DOCUMENT mode `etree.fromstring`) is advisory — not enforced via grep acceptance criterion. Recommend adding `grep -c "_xml_io.secure_xml_parser" src/.../file_output_xml.py >= 1` to acceptance criteria.

**C-8.** Plan 12-03 P-8 stdlib→lxml drift catalog is described in prose but not a discrete task. Per-param tests partially cover.

**C-9.** Plan 12-05 acceptance criterion `grep -c "logger.warning" >= 3` is too lenient — could pass with 3 unrelated warns. Tighten to require 3 distinct keywords (`expression_filter`, `lookup`, `allInOne`).

**C-10.** REQUIREMENTS.md still has stale Phase 12 mappings (TEST-05, TEST-06, PERF-03, PERF-04 from old roadmap before Phase 12 was renamed XML). Plan 12-01 only adds XML-01..04 — does not clean up stale rows. Acceptable per `feedback_scope_boundaries` (don't do global sweeps in feature phases); user should be aware.

---

## 8. Final Recommendation

**Ready to execute, with two pre-execution touch-ups recommended:**

1. **MUST do (C-1):** Resolve Wave 5 parallel-write conflict. Easiest path: change `12-07-PLAN.md` frontmatter `depends_on:` from `[02, 04]` to `[02, 04, 06]` — this serializes 12-07 after 12-06. Alternatively split the converter module into separate files (`file_output_xml.py` simple converter / `file_output_advanced_xml.py` advanced converter).

2. **SHOULD do (C-4):** Fix the malformed `</antomated>` typo on line 405 of 12-05-PLAN.md (delete the malformed `<automated>...</antomated>` block; keep the well-formed line 406 block).

3. **NICE to have (C-2, C-3, C-5..C-10):** Add `(RESOLVED)` to RESEARCH.md `## Open Questions` heading; strip the `</content></invoke>` artifacts from all 8 plan files; tighten Plan 12-05 acceptance criterion for warn keywords; add Plan 12-07 `tests/converters/.../test_file_output_xml.py` to its `files_modified`; elevate drift-catalog to an explicit task.

If C-1 is fixed (or accepted as a known wave-coordination risk and surfaced to the executor), the plans will deliver Phase 12's goal as stated in ROADMAP.md and CONTEXT.md.

Plans cleared for execution after C-1 mitigation. None of the remaining concerns block delivery.

---

## PLAN CHECK COMPLETE

## VERDICT: PASS-WITH-CONCERNS
