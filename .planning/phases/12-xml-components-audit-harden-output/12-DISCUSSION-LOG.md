# Phase 12: XML Components Audit, Harden & Output - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 12-xml-components-audit-harden-output
**Areas discussed:** Component scope, Bug source, XML library + streaming, Test parity rubric, Bridge coordination, Output fixtures

---

## Component Scope — tFileInputMSXML inclusion

| Option | Description | Selected |
|--------|-------------|----------|
| Out — audit only the 3 main components | Skip MSXML; small, has tests, MS-specific edge case | |
| In — light audit pass | Add MSXML to scope; light touch since it's smaller and has tests | ✓ |
| Defer to a 12.1 follow-up | Note as candidate for follow-up if production surfaces it | |

**User's choice:** "we will pick it as well bro"
**Notes:** Phase 12 scope grows from 3 → 4 input components. Light-touch audit acceptable since file is small (172 LOC) and has engine-side tests already.

---

## Component Scope — Output XML variant

| Option | Description | Selected |
|--------|-------------|----------|
| tFileOutputXML only (Recommended) | Simple/flat output; covers most production XML emission | |
| Both tFileOutputXML and tAdvancedFileOutputXML | Simple + advanced together; ~1.5x output work | ✓ |
| tAdvancedFileOutputXML only | Skip simple if production needs only hierarchical | |
| Decide based on production .item fixtures | Pause and survey first | |

**User's choice:** Both
**Notes:** Total scope = 4 input audit + 2 output build = 6 components. Comparable to Phase 11 Oracle (7 plans, 6 waves). Existing audit doc at `docs/v1/audit/components/file/tAdvancedFileOutputXML.md` provides head-start for the advanced variant.

---

## Bug Source — known list vs discovery audit

| Option | Description | Selected |
|--------|-------------|----------|
| Manager has a list — ask him for it | Tighter scope, faster execution | |
| Run a fresh audit (Phase 11 Oracle pattern) | Plan 1 = audit-vs-Talend report per component; subsequent plans fix gaps | ✓ |
| Both — audit AND incorporate manager's list | Most thorough; most upfront work | |
| Real-job E2E first — let failures surface bugs | Risk: misses unsurfaced bugs | |

**User's choice:** Run a fresh audit (Phase 11 Oracle pattern)
**Notes:** Audit-first phase structure. Plan 1 produces gap reports; subsequent plans fix what audits surface. Reuse Phase 11 Oracle plan structure as template.

---

## XML Library Standardization

| Option | Description | Selected |
|--------|-------------|----------|
| Standardize on lxml across all 4 (Recommended) | Migrate `file_input_xml.py` from stdlib to lxml; consistent XPath semantics | |
| Keep mixed — fix-only-broken | Smaller diff but inconsistencies remain | |
| Decide per-component during audit | Library swap as a finding | |

**User's choice (free-text):** "we need to use the best library bro. memory and performance optimized, latest, etc"
**Notes:** Resolved to lxml 5.x (latest, C-backed via libxml2). Adds threshold-switched DOM vs iterparse and defusedxml.lxml at input boundaries. Rationale: lxml is the production-grade Python XML library — fastest in benchmarks, full XPath 1.0, mature.

---

## Streaming + Security

| Option | Description | Selected |
|--------|-------------|----------|
| Threshold-switched + defusedxml (Recommended) | <50MB DOM, >=50MB iterparse; defusedxml at input boundaries | ✓ |
| Always streaming | Slower on tiny files; bullet-proof on huge | |
| Mirror existing streaming-mode toggle on file outputs | Honor base-component `streaming_mode` flag | |
| Defer security (defusedxml) to a later phase | Phase 12 = correctness + perf only | |

**User's choice:** Threshold-switched + defusedxml
**Notes:** 50 MB threshold default; configurable via `xml_streaming_threshold_mb`. Output mirrors recent commit `bb5b97f` streaming pattern. defusedxml.lxml required even for "internal" inputs — financial-data ingest sees external XML.

---

## Reference Source for Talend Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Talaxie javajet templates (Recommended) | Same as Phase 11 Oracle; machine-checkable per parameter | ✓ |
| Talend Open Studio user docs + javajet | Combine docs for semantics, javajet for exact behavior | |
| Existing audit doc + javajet | Reuse `docs/v1/audit/components/file/tAdvancedFileOutputXML.md` where present | |
| Real .item fixtures + observed Talend output | Empirical; requires running Talend | |

**User's choice:** Talaxie javajet templates
**Notes:** Reuse Phase 11 pattern. Read `tFileInputXML_java.xml`, etc., from Talaxie's `tdi-studio-se` repo. Each parameter's javajet code reveals exact behavior.

---

## Test Depth Rubric

| Option | Description | Selected |
|--------|-------------|----------|
| Every Talaxie javajet parameter has positive + negative test (Recommended) | Pos+neg per parameter + 95% coverage + E2E | ✓ |
| Parameters used in current .item fixtures, fully covered | Tighter; misses parameters not in fixtures | |
| Behavior-driven scenarios | ~10-15 scenarios per component instead of one-per-parameter | |
| Coverage 95% + E2E only | Lightest; risk of missing edge cases | |

**User's choice:** Every Talaxie javajet parameter has positive + negative test
**Notes:** Most thorough. Catches semantic bugs that pure coverage % misses. Comparable to Phase 11 Oracle's per-parameter PARAMETER_TYPE matrix discipline.

---

## tXMLMap + Java Bridge Coordination

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 12 audits Java-expression paths but doesn't rebuild JAR (Recommended) | tXMLMap audit covers Java-expression mappings; JAR rebuild stays in Phase 13 | ✓ |
| Defer all Java-expression test scenarios on tXMLMap to Phase 13 | Phase 12 covers only XML/XPath; expression eval in Phase 13 | |
| Wait for manager's JAR changes before starting Phase 12 | Slowest; no rework risk | |
| Coordinate with manager: get a snapshot of his in-flight signatures | Requires sync | |

**User's choice:** Phase 12 audits Java-expression paths but doesn't rebuild JAR
**Notes:** Cleanest separation. Phase 12 uses current JAR. If audit surfaces a JAR signature gap on tXMLMap, mark single test `xfail` and document as Phase 13 input.

---

## Output Fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-author minimal .item files (Recommended) | Write minimal Talend .item by hand for each output variant | ✓ |
| Ask manager / business team for real production samples | Most realistic; takes time + anonymization | |
| Generate via Talend Open Studio if available locally | Fastest if Talend installed; matches exact .item format | |
| Programmatic .item synthesizer | Fastest; loses converter-coverage on path | |

**User's choice:** Hand-author minimal .item files
**Notes:** Living fixtures under `tests/talend_xml_samples/`. Cover simple-output, with-attributes, with-namespace, hierarchical (advanced).

---

## Claude's Discretion

- Plan/wave structure for the audit-then-fix flow — planner agent slices the 6-component scope into plans
- `engine_gap` / `needs_review` policy for unsupported XML sub-features (XSLT, XInclude, custom DTD) — follow Phase 11 D-E1 conditional pattern; planner records exact list during planning
- Coverage tooling configuration for Phase-12-scoped reports — executor wires `pytest --cov=src/v1/engine/components/file --cov=src/v1/engine/components/transform`

## Deferred Ideas

- **`tWriteXMLField`** (write XML into a column) — not requested; candidate for Phase 12.1 or follow-up
- **Bridge JAR rebuild + signature reconciliation** — Phase 13 (Test Stabilization). Manager's in-flight changes land first.
- **XSLT-driven transformation / XInclude / XML 1.1 / custom DTD** — `needs_review` on the converter when present; no runtime support
- **Real Citi production .item files** — if production surfaces bugs after Phase 12, those go to Phase 12.1 gap-closure
- **Large-XML perf fixtures (>50 MB)** — generate programmatically during planning; detailed perf testing deferred to Phase 15
