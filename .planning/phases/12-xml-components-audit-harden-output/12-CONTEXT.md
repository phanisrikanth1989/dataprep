# Phase 12: XML Components Audit, Harden & Output - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit the 4 existing XML input components against Talend behavior, fix the gaps the audit surfaces, build 2 missing output XML components, and lock comprehensive tests so production jobs that consume or emit XML can be migrated reliably.

**In scope:**
- Audit + harden 4 input components: `tFileInputXML`, `tFileInputMSXML`, `tExtractXMLField`, `tXMLMap`
- Build 2 output components: `tFileOutputXML` (simple/flat), `tAdvancedFileOutputXML` (hierarchical)
- Standardize all 6 in-scope components on `lxml` 5.x with `defusedxml.lxml` at input boundaries
- Threshold-switched DOM/streaming at 50 MB (DOM below, `lxml.etree.iterparse` + element clearing above)
- Comprehensive tests: positive + negative test per Talaxie javajet parameter, 95% line coverage per module, E2E test on each component's `.item` fixture
- Hand-author minimal `.item` fixtures for the 2 output components (we do not have any output-XML fixtures today)

**Out of scope (deferred to other phases):**
- Java bridge JAR rebuild (Phase 13 — manager has concurrent bridge changes in flight)
- 95%-coverage CI gate enforcement across the whole codebase (Phase 14)
- Real-job E2E + perf benchmarks (Phase 15)
- Documentation sweep (Phase 16)
- `tWriteXMLField` (writes XML into a single column) — not requested
- XSLT-driven transformation, XInclude, XML 1.1, custom DTD

</domain>

<decisions>
## Implementation Decisions

### Component Scope
- **D-A1:** Audit + harden 4 input components: `tFileInputXML` (engine: 555 LOC, no engine-side test today), `tFileInputMSXML` (172 LOC, has engine-side test), `tExtractXMLField` (260 LOC, has engine-side test), `tXMLMap` (738 LOC, no engine-side test today)
- **D-A2:** Build 2 new output components: `tFileOutputXML` (simple/flat) and `tAdvancedFileOutputXML` (hierarchical with nested groups, repeating sub-elements, attributes mapped from columns)
- **D-A3:** Total = 6 in-scope components — comparable scope to Phase 11 Oracle (which delivered 7 plans across 6 waves)

### Audit Methodology
- **D-B1:** Audit-first pattern (Phase 11 Oracle style) — Plan 1 (or first wave) produces an audit-vs-Talend report per component before any code changes; subsequent plans fix what the audit surfaces
- **D-B2:** Reference source = **Talaxie javajet templates** (same as Phase 11). Read `tFileInputXML_java.xml`, `tFileInputMSXML_java.xml`, `tExtractXMLField_java.xml`, `tXMLMap_java.xml`, `tFileOutputXML_java.xml`, `tAdvancedFileOutputXML_java.xml` from Talaxie's `tdi-studio-se` repo. Each parameter's javajet code reveals exact behavior — machine-checkable against current engine.
- **D-B3:** No known-bug list from manager — discovery is part of the phase itself. Manager's signal "existing XML components are not working" is treated as a starting hypothesis the audit must validate or refute per parameter.

### XML Library + Streaming
- **D-C1:** Standardize on **`lxml` 5.x** (latest, C-backed via libxml2/libxslt) across all 6 in-scope components. `file_input_xml.py` currently uses stdlib `xml.etree` and MUST be migrated to lxml.
- **D-C2:** **Threshold-switched I/O strategy:** files < 50 MB load full DOM (`etree.parse`); files >= 50 MB use `lxml.etree.iterparse` with element clearing for constant-memory streaming. Threshold is a config knob (`xml_streaming_threshold_mb`, default 50).
- **D-C3:** Output mirrors the recent base-component streaming pattern (commit `bb5b97f`): incremental write rather than buffer-and-write the full DOM.
- **D-C4:** **Security: `defusedxml.lxml`** wrappers at every input boundary (XXE / billion-laughs protection). Required even for "internal" inputs — financial-data ingest sees external XML routinely.
- **D-C5:** No fallback to stdlib `xml.etree` — fix-source policy. If lxml is missing at runtime, raise a clear `ConfigurationError`.

### Test Parity Rubric
- **D-D1:** **Per-parameter positive + negative tests** — for each Talaxie javajet parameter on each component, at least one happy-path test and one edge-case/negative test
- **D-D2:** **95% line coverage** floor per module for the 6 XML components (anticipates Phase 14's per-module floor — Phase 12 must not lower the bar)
- **D-D3:** **E2E test per component on its `.item` fixture** — load the XML, run the real converter, run the real ETLEngine, assert on output (DataFrame state for input components; output XML correctness for output components)
- **D-D4:** Tests use real I/O wherever feasible (lessons from Phase 5.1 / 11 — mocks lie). Synthetic XML inputs are fine for unit tests; mocks of `lxml.etree` itself are forbidden.
- **D-D5:** Output `.item` fixtures are **hand-authored minimal `.item` files** — write small Talend `.item` XML by hand for `tFileOutputXML` (simple) and `tAdvancedFileOutputXML` (hierarchical), saved under `tests/talend_xml_samples/`. No external dependency on running Talend Studio.

### Bridge Coordination
- **D-E1:** **Manager has concurrent Java bridge changes in flight.** Phase 12 audits `tXMLMap`'s Java-expression code paths against the **current JAR**. JAR rebuild + signature reconciliation stays in Phase 13. If the audit surfaces a JAR signature gap on `tXMLMap`, document the finding as Phase 13 input — do NOT rebuild the JAR in Phase 12.
- **D-E2:** Phase 12 does NOT block on Phase 13 — XML components can be audited and hardened against today's bridge surface. If a tXMLMap test depends on a bridge signature that's actively being changed, mark that single test `xfail` with the Phase 13 ticket reference and move on.

### Claude's Discretion
- Plan/wave structure for the audit-then-fix flow — the planner agent decides how to slice (one plan per component vs grouped, how to parallelize the 6 components in waves)
- Coverage tooling configuration for Phase-12-scoped reports (`pytest --cov=src/v1/engine/components/file --cov=src/v1/engine/components/transform`) — executor wires this
- `engine_gap` / `needs_review` policy for unsupported XML sub-features (e.g., XSLT, XInclude, custom DTD) — follow Phase 11 D-E1 conditional pattern; planner records exact list during planning

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & Architecture
- `.planning/PROJECT.md` — Core value, scope discipline, evolution rules
- `.planning/REQUIREMENTS.md` — Active requirement IDs (XML-01..XML-04 to be added during planning)
- `.planning/ROADMAP.md` §"Phase 12" — Goal, dependencies, success criteria
- `.planning/codebase/ARCHITECTURE.md` — Component pattern (ABC + registry + per-component organization)
- `.planning/codebase/CONVENTIONS.md` — snake_case, ASCII-only logs, custom exceptions from `src/v1/engine/exceptions.py`
- `CLAUDE.md` — Project instructions, lxml is the documented XML standard

### Talend Behavior Reference (audit baseline)
- `https://github.com/Talaxie/tdi-studio-se` — javajet templates per component:
  - `tFileInputXML_java.xml` (path TBD by audit Plan 1)
  - `tFileInputMSXML_java.xml`
  - `tExtractXMLField_java.xml`
  - `tXMLMap_java.xml`
  - `tFileOutputXML_java.xml`
  - `tAdvancedFileOutputXML_java.xml`
- Existing audit: `docs/v1/audit/components/file/tAdvancedFileOutputXML.md` — prior audit notes for the advanced variant; reuse where current

### Prior Phase Decisions (carry-forward)
- `.planning/phases/11-oracle-components/11-CONTEXT.md` D-E1 — conditional `needs_review` pattern for unsupported sub-features (XML phase should follow the same pattern for XSLT, XInclude, etc.)
- `.planning/phases/05.1-java-bridge-tmap-fix/` — Arrow type bugs + closure-dispatch fix (relevant for tXMLMap's Java-expression path)
- `.planning/phases/05.2-tmap-reload-at-each-row-fix/` — RELOAD_AT_EACH_ROW per-row lookup semantics (NOT applicable to XML components; documented to avoid confusion)
- `.planning/phases/10-iterate-support/` — base component lifecycle (XML components inherit from `BaseComponent`)

### Existing Engine Code (reusable / starting state)
- `src/v1/engine/components/file/file_input_xml.py` (555 LOC, stdlib `xml.etree` — MUST migrate to lxml per D-C1)
- `src/v1/engine/components/file/file_input_msxml.py` (172 LOC, current state TBD by audit)
- `src/v1/engine/components/transform/extract_xml_fields.py` (260 LOC, lxml today)
- `src/v1/engine/components/transform/xml_map.py` (738 LOC, lxml today, NO engine-side test)
- `src/converters/talend_to_v1/components/file/file_input_xml.py` — converter reference
- `src/converters/talend_to_v1/components/file/file_output_xml.py` — converter for the new engine component
- `src/v1/engine/base_component.py` — lifecycle the new components hook into
- `src/v1/engine/exceptions.py` — `ConfigurationError`, `FileOperationError`, `DataValidationError`

### Existing Tests (starting state for harden plans)
- `tests/v1/engine/components/file/test_file_input_msxml.py` — has engine tests
- `tests/v1/engine/components/transform/test_extract_xml_fields.py` — has engine tests
- `tests/converters/talend_to_v1/components/file/test_file_input_xml.py`
- `tests/converters/talend_to_v1/components/file/test_file_input_msxml.py`
- `tests/converters/talend_to_v1/components/file/test_file_output_xml.py`
- `tests/converters/talend_to_v1/components/transform/test_extract_xml_fields.py`
- `tests/converters/talend_to_v1/components/transform/test_xml_map.py`
- `tests/talend_xml_samples/Job_tFileInputXML_*.item`, `Job_tExtractXMLField_*.item`, `Job_tXMLMap_*.item` — engine-E2E fixtures
- **GAPS:** no `test_file_input_xml.py` and no `test_xml_map.py` on the engine side (Plan output)

### Library / Tooling References
- `lxml` 5.x docs — https://lxml.de/api/index.html (etree, iterparse, XPath)
- `defusedxml` — https://github.com/tiran/defusedxml (XXE / billion-laughs protections)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`BaseComponent`** (`src/v1/engine/base_component.py`) — execute() / _process() lifecycle the new output components plug into. Streaming-mode hook landed in commit `bb5b97f`.
- **`FileOutputDelimited` streaming pattern** (`src/v1/engine/components/file/file_output_delimited.py`) — incremental write via base component streaming hook; reference pattern for tFileOutputXML / tAdvancedFileOutputXML.
- **Java bridge interaction in `xml_map.py`** — already uses `JavaBridgeManager` for expression evaluation; pattern carries to fixes during audit.
- **`ConfigurationError` / `FileOperationError`** (`src/v1/engine/exceptions.py`) — typed exception hierarchy for validation failures.
- **Existing XML converters** (`src/converters/talend_to_v1/components/file/file_*_xml.py`, `src/converters/talend_to_v1/components/transform/{extract_xml_fields,xml_map}.py`) — the converter side of all 6 components is already in place; engine work is the gap. (Note: `tAdvancedFileOutputXML` converter status TBD by Plan 1 audit.)

### Established Patterns
- **Audit-first phase** (Phase 11 Oracle) — Plan 1 produces gap reports; subsequent plans fix one component at a time; final plan does cross-component E2E.
- **Conditional `needs_review`** (Phase 11 D-E1) — converter emits `needs_review` only for the specific unsupported sub-feature (XSLT, XInclude, custom DTD), not for the whole component.
- **Per-parameter pos+neg tests** (Phase 11 Oracle 213-test pattern) — exhaustive Talaxie-javajet-driven test breadth, not just coverage %.
- **Real-bridge tests for Java-touching components** (Phase 5.1 lesson) — `tXMLMap` audit's Java-expression tests must use the real bridge, not mocks.
- **Streaming threshold via config** (recent base components, commit `bb5b97f`) — config flag controls streaming-mode; XML components honor the same flag style with their own threshold.

### Integration Points
- `ETLEngine.run_job()` — the new tFileOutput[XML|AdvancedXML] components register via `COMPONENT_REGISTRY` (engine.py)
- `JavaBridgeManager` — `tXMLMap` audit must verify Java-expression dispatch against the current JAR (NOT the JAR Phase 13 will rebuild)
- `ContextManager` — XML config strings (filename, encoding, root tag) resolve `${context.var}` and `context.var` references via the standard 3-phase resolution
- Recent commits to watch:
  - `9bee178` (bridge + Arrow serializer for decimal nulls) — may affect tXMLMap's column-type handling
  - `bb5b97f` (base components streaming mode) — required for tFileOutput[XML|AdvancedXML] streaming output

</code_context>

<specifics>
## Specific Ideas

- **"Best library — memory and performance optimized, latest"** — user direction. Translates to: lxml 5.x, threshold-switched DOM vs `iterparse`, defusedxml input wrappers.
- **Manager's bridge changes are concurrent** — coordinate signal: tXMLMap audit reads against current JAR; JAR rebuild stays in Phase 13. If a single tXMLMap test trips on a signature manager is actively changing, mark `xfail` and document Phase 13 ticket.
- **Hand-authored output `.item` fixtures** — minimal but real Talend XML structure for `tFileOutputXML` (simple) and `tAdvancedFileOutputXML` (hierarchical with attributes, repeating groups, namespace).
- **Phase scope is contractual** — 4 input + 2 output. Resist creep into `tWriteXMLField`, integration testing, perf benchmarking — those go to other phases.

</specifics>

<deferred>
## Deferred Ideas

- **`tWriteXMLField`** (write XML into a single column) — not in current scope; if production jobs use it, candidate for Phase 12.1 or a separate XML-output addendum
- **Bridge JAR rebuild + signature reconciliation** — Phase 13 (Test Stabilization). Manager's in-flight changes land first; Phase 13 folds them in.
- **XSLT-driven transformation / XInclude / XML 1.1 / custom DTD** — emit `needs_review` on the converter (D-E1 pattern) when these appear in a job's `.item`; do not implement runtime support
- **Real Citi production .item files** — use what we have today; if production surfaces bugs after Phase 12 closes, those go to Phase 12.1 gap-closure
- **Large-XML perf fixtures (>50 MB)** — generate programmatically during planning if the planner decides perf coverage matters; otherwise smoke-test the streaming path with a synthetic 60 MB fixture and defer detailed perf to Phase 15

</deferred>

---

*Phase: 12-xml-components-audit-harden-output*
*Context gathered: 2026-05-07*
