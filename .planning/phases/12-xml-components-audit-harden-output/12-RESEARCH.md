# Phase 12: XML Components Audit, Harden & Output - Research

**Researched:** 2026-05-08
**Domain:** XML parsing & emission for ETL (lxml 5+/6.x, defusedxml deprecation, threshold-switched DOM/iterparse, incremental xmlfile output, Talend feature parity for 6 components)
**Confidence:** HIGH on the lxml stack, current engine state, and prior audits; MEDIUM on tFileOutputXML simple-mode behavior (not previously audited in repo); LOW on the precise Talend behavior of tXMLMap's "All-in-One" Document output and lookup loops -- both are deferred via D-E1 conditional `needs_review`.

## Summary

Phase 12 takes 4 existing XML input components (tFileInputXML stdlib, tFileInputMSXML lxml, tExtractXMLField lxml, tXMLMap lxml) and 2 missing output components (tFileOutputXML simple/flat, tAdvancedFileOutputXML hierarchical) to feature parity with Talend, on a unified lxml stack. The audit work has a substantial head start: per-component audit docs already exist under `docs/v1/audit/components/{file,transform}/` for all 6 components, dated 2026-04-03..04. These predate the Phase 7.1 cross-cutting fixes, so the cross-cutting P0s (`_update_global_map`, `GlobalMap.get`, `replace_in_config[i]`) flagged in those audits are RESOLVED — Plan 1 must re-baseline against current `HEAD` not the audit text. The audit text remains the right starting hypothesis for component-specific gaps (REJECT flow, encoding, namespace handling, streaming, `iloc[0,0]` data-loss bug in xml_map, etc.).

**Architecturally** the engine surface is well-shaped: `BaseComponent.execute()` already provides streaming-mode hooks (commit `bb5b97f`) with per-chunk `_process()` and `_streaming_write_started` flag (proven by `FileOutputDelimited`). The 2 new output components plug into that lifecycle. `lxml.etree.xmlfile()` is the right primitive for incremental XML output; `lxml.etree.iterparse(..., events=('end',))` with `element.clear(keep_tail=True)` is the right primitive for streaming input. Neither is "novel" — both are documented and verified via Context7 against lxml 6.0/6.1 docs.

**Critical correction to CONTEXT.md D-C4:** `defusedxml.lxml` is DEPRECATED upstream and slated for removal. The accepted-secure-pattern is the existing `extract_xml_fields.py` / `file_input_msxml.py` recipe: `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)`. We document this as a recommendation to revisit D-C4 in discuss-phase (or accept the planner's discretion to substitute "etree.XMLParser with secure flags" wherever D-C4 says "defusedxml.lxml wrappers").

**Primary recommendation:** Execute as 7 plans across 6 waves (Phase 11 mirror), with Plan 1 = re-audit-and-baseline, Plan 2 = lxml infrastructure + shared helpers, Plans 3-5 = per-component fix-and-test for the 4 inputs (file_input_xml is the heaviest because it's a stdlib→lxml migration; tXMLMap is the riskiest because of `iloc[0,0]` data-loss + zero engine tests today), Plan 6 = the 2 output components, Plan 7 = E2E + coverage gate.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Component Scope**
- D-A1: Audit + harden 4 input components: `tFileInputXML` (engine: 555 LOC, no engine-side test today), `tFileInputMSXML` (172 LOC, has engine-side test), `tExtractXMLField` (260 LOC, has engine-side test), `tXMLMap` (738 LOC, no engine-side test today)
- D-A2: Build 2 new output components: `tFileOutputXML` (simple/flat) and `tAdvancedFileOutputXML` (hierarchical with nested groups, repeating sub-elements, attributes mapped from columns)
- D-A3: Total = 6 in-scope components — comparable scope to Phase 11 Oracle (which delivered 7 plans across 6 waves)

**Audit Methodology**
- D-B1: Audit-first pattern (Phase 11 Oracle style) — Plan 1 (or first wave) produces an audit-vs-Talend report per component before any code changes; subsequent plans fix what the audit surfaces
- D-B2: Reference source = **Talaxie javajet templates** (same as Phase 11). Read `tFileInputXML_java.xml`, `tFileInputMSXML_java.xml`, `tExtractXMLField_java.xml`, `tXMLMap_java.xml`, `tFileOutputXML_java.xml`, `tAdvancedFileOutputXML_java.xml` from Talaxie's `tdi-studio-se` repo. Each parameter's javajet code reveals exact behavior — machine-checkable against current engine.
- D-B3: No known-bug list from manager — discovery is part of the phase itself. Manager's signal "existing XML components are not working" is treated as a starting hypothesis the audit must validate or refute per parameter.

**XML Library + Streaming**
- D-C1: Standardize on **`lxml` 5.x** (latest, C-backed via libxml2/libxslt) across all 6 in-scope components. `file_input_xml.py` currently uses stdlib `xml.etree` and MUST be migrated to lxml.
- D-C2: **Threshold-switched I/O strategy:** files < 50 MB load full DOM (`etree.parse`); files >= 50 MB use `lxml.etree.iterparse` with element clearing for constant-memory streaming. Threshold is a config knob (`xml_streaming_threshold_mb`, default 50).
- D-C3: Output mirrors the recent base-component streaming pattern (commit `bb5b97f`): incremental write rather than buffer-and-write the full DOM.
- D-C4: **Security: `defusedxml.lxml`** wrappers at every input boundary (XXE / billion-laughs protection). Required even for "internal" inputs — financial-data ingest sees external XML routinely.
- D-C5: No fallback to stdlib `xml.etree` — fix-source policy. If lxml is missing at runtime, raise a clear `ConfigurationError`.

**Test Parity Rubric**
- D-D1: **Per-parameter positive + negative tests** — for each Talaxie javajet parameter on each component, at least one happy-path test and one edge-case/negative test
- D-D2: **95% line coverage** floor per module for the 6 XML components
- D-D3: **E2E test per component on its `.item` fixture** — load the XML, run the real converter, run the real ETLEngine, assert on output (DataFrame state for input components; output XML correctness for output components)
- D-D4: Tests use real I/O wherever feasible. Mocks of `lxml.etree` itself are forbidden.
- D-D5: Output `.item` fixtures are **hand-authored minimal `.item` files** for `tFileOutputXML` (simple) and `tAdvancedFileOutputXML` (hierarchical), saved under `tests/talend_xml_samples/`.

**Bridge Coordination**
- D-E1: Phase 12 audits `tXMLMap`'s Java-expression code paths against the **current JAR**. JAR rebuild stays in Phase 13. If a JAR signature gap surfaces on tXMLMap, document as Phase 13 input — do NOT rebuild the JAR in Phase 12.
- D-E2: Phase 12 does NOT block on Phase 13. If a tXMLMap test depends on a bridge signature manager is actively changing, mark that single test `xfail` with the Phase 13 ticket reference and move on.

### Claude's Discretion
- Plan/wave structure for the audit-then-fix flow — the planner agent decides how to slice (one plan per component vs grouped, how to parallelize the 6 components in waves)
- Coverage tooling configuration for Phase-12-scoped reports (`pytest --cov=src/v1/engine/components/file --cov=src/v1/engine/components/transform`) — executor wires this
- `engine_gap` / `needs_review` policy for unsupported XML sub-features (e.g., XSLT, XInclude, custom DTD) — follow Phase 11 D-E1 conditional pattern; planner records exact list during planning

### Deferred Ideas (OUT OF SCOPE)
- `tWriteXMLField` (write XML into a single column) — candidate for Phase 12.1 follow-up
- Bridge JAR rebuild + signature reconciliation — Phase 13
- XSLT-driven transformation / XInclude / XML 1.1 / custom DTD — emit `needs_review` on the converter (D-E1 pattern); no runtime support
- Real Citi production .item files — if production surfaces bugs after Phase 12 closes, Phase 12.1 gap-closure
- Large-XML perf fixtures (>50 MB) — generate programmatically during planning if perf coverage matters; detailed perf to Phase 15

### Important Caveat (research finding)
- **D-C4 — `defusedxml.lxml` is DEPRECATED upstream** [VERIFIED: defusedxml README via Context7 — see Pitfall P-1]. The library author recommends configuring `lxml.etree.XMLParser` with `resolve_entities=False, no_network=True, load_dtd=False` instead. The repo's existing `extract_xml_fields.py` (Phase 7.x security hardening) and `file_input_msxml.py` already follow this pattern. Recommendation: substitute "etree.XMLParser with secure flags" wherever D-C4 references defusedxml.lxml. Surface to the user during plan check or in a discuss-phase amendment if the planner thinks this materially changes the contract.
</user_constraints>

<phase_requirements>
## Phase Requirements

The CONTEXT.md and ROADMAP say XML-01..XML-04 are "to be added during planning". Below is the recommended requirement text to add to `.planning/REQUIREMENTS.md` so the plan/verifier chain has IDs to anchor on. Planner can refine wording.

| ID | Description | Research Support |
|----|-------------|------------------|
| **XML-01** | The 4 input XML components (`tFileInputXML`, `tFileInputMSXML`, `tExtractXMLField`, `tXMLMap`) match Talaxie javajet behavior parameter-by-parameter; gaps surfaced by the Phase 12 audit are either fixed in code OR converted to a conditional `needs_review` (D-E1 pattern) for explicitly out-of-scope sub-features (XSLT, XInclude, custom DTD, Document output for tXMLMap). | Standard Stack §; Audit-first decomposition (Plan 1 baseline) §Plan/Wave Decomposition; per-component sections for each input; Talaxie javajet param tables in Component-by-Component Audit §. |
| **XML-02** | A new `tFileOutputXML` engine component is built with full simple/flat XML emission (one row per ROW_TAG, columns→sub-elements or attributes via MAPPING) and registered alongside a new `tFileOutputXML` converter (one does not exist today; only `tAdvancedFileOutputXML` is registered). | tFileOutputXML javajet parameter inventory §; Output Components §; converter registration gap noted under "Code Insights / Important Findings". |
| **XML-03** | A new `tAdvancedFileOutputXML` engine component is built with hierarchical emission (ROOT/GROUP/LOOP TABLE-driven nesting, attributes via ATTRIBUTE flag, namespace support, optional file-merge in DOM4J mode); converter `AdvancedFileOutputXmlConverter` already extracts all 33 params, so no converter rewrite needed. | Existing converter audit `tAdvancedFileOutputXML.md` §; tAdvancedFileOutputXML 33-param inventory §; xmlfile incremental emission patterns §. |
| **XML-04** | All 6 in-scope components are unified on lxml ≥4.9 (already pinned via the `xml` extra in pyproject.toml; pyproject already correct). `file_input_xml.py` is migrated from stdlib `xml.etree.ElementTree` to lxml. Threshold-switched DOM (`etree.parse`)/streaming (`etree.iterparse + element.clear(keep_tail=True)`) at the configured threshold. Per-input-boundary secure-XMLParser flags (resolve_entities=False, no_network=True, load_dtd=False) — substituting for the deprecated defusedxml.lxml per D-C4 caveat. Per-component test budgets meet the 95% per-module line coverage floor and the per-parameter positive+negative test rule. | Standard Stack §; Architecture Patterns / Threshold-Switched Parsing §; Pitfalls (P-1, P-2, P-3) §; Validation Architecture §. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Python 3.10+** required (uses `set[str]` syntax). Engine modules must remain compatible.
- **Compatibility**: produced output must match Talend for the same input + config. Feature parity is non-negotiable.
- **Java bridge architecture**: must remain Py4J + Arrow. Phase 12 does NOT touch the bridge — D-E2 is explicit.
- **No breaking changes to converter JSON**: existing JSONs must still execute. Engine-side changes are free; converter changes that REMOVE keys are forbidden, but ADDING keys (`xml_streaming_threshold_mb` config) is fine.
- **Existing patterns**: ABC + decorator-based registry + per-component file organization. Apply to new output components: register on import via `__init__.py`.
- **GSD workflow enforcement**: every change goes through GSD. Phase 12 plans must be `/gsd-plan-phase` outputs.
- **Naming**: `snake_case` modules / functions / variables; `PascalCase` classes; `UPPER_SNAKE_CASE` constants; private members single-underscore.
- **ASCII-only logging** (carry-over rule from Phase 10 D-H1..H7) — XML components log file paths and counts; emojis/unicode forbidden.
- **Custom exceptions only**: `ConfigurationError`, `DataValidationError`, `FileOperationError`, `ETLError` — no bare `RuntimeError`/`ValueError` per current convention. The 2026-04-03 audit flagged the existing file_input_xml.py as using bare `RuntimeError`; that's a STD- bug to fix during the migration.
- **Fix source, no fallbacks** (memory rule): bad XML = REJECT or `DataValidationError`, NOT silent string passthrough or stdlib fallback.
- **No mocks of the thing under test** (memory rule + D-D4): `lxml.etree` is the thing under test; tests use real XML strings/files.
- **Verify audit claims** (memory rule): the 2026-04-03 audit docs predate Phase 7.1 cross-cutting fixes. Plan 1 verifies each P0/P1 claim against current `HEAD` before locking it as a fix item.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| XML file I/O (read + write) | Engine Component Layer (`src/v1/engine/components/file/`) | — | File-level XML ops sit alongside delimited / Excel / positional file components; consistent with `FileInput*` family. |
| XPath extraction over a DataFrame column | Engine Component Layer (`src/v1/engine/components/transform/`) | — | `tExtractXMLField` and `tXMLMap` operate on rows of a flow, not on standalone files; canonical "transform" placement. |
| Threshold-switched DOM vs iterparse | Engine Component Layer (per-component) | Shared util (new module) | Each component decides DOM-vs-streaming based on its own config + file size; a small shared helper (`_xml_io.py`) hosts the secure-parser factory + threshold check. |
| Incremental XML serialization | Engine Component Layer (per-output-component) | Base Component lifecycle (`base_component.py`'s streaming hook) | Output components own the `etree.xmlfile` context; the per-chunk `_process()` re-entry from `BaseComponent` (commit `bb5b97f`) drives chunked writes. Same shape as `FileOutputDelimited`. |
| Talend `.item` → engine config | Converter Layer (`src/converters/talend_to_v1/components/{file,transform}/`) | — | Converters already exist for 5 of 6 components; only `tFileOutputXML` (simple) needs a new converter. `tAdvancedFileOutputXML` converter exists and is gold-standard per its prior audit. |
| Java/Groovy expression evaluation | Java Bridge (Py4J + Arrow) | NOT TOUCHED IN PHASE 12 | xml_map.py currently does NOT call into the Java bridge. The "expression_filter" param is extracted by the converter but never consumed by the engine — that's the pre-existing `engine_gap`. Per D-E1, Phase 12 does NOT add expression_filter execution. |
| Secure XML parsing (XXE / billion-laughs) | Engine Component Layer | Shared helper (`_xml_io.py`) | Single factory function returns a configured `etree.XMLParser`; every component uses it. Replaces the deprecated `defusedxml.lxml` per the D-C4 caveat. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **lxml** | `>=4.9,<7` (project pin); installed=6.0.3, latest=6.1.0 [VERIFIED: `pip index versions lxml` 2026-05-08; project pin in `pyproject.toml:19`] | XML parsing (`etree.parse`, `etree.iterparse`), XPath 1.0, XML serialization (`etree.tostring`, `etree.xmlfile`), namespace handling | C-backed (libxml2/libxslt), the de-facto Python XML library, fastest in benchmarks, used by 3 of 4 in-scope input components today (extract_xml_fields, file_input_msxml, xml_map) [VERIFIED: grep across `src/v1/engine/components/`] |
| **pandas** | `>=2.0,<4` (project pin); 3.0.1 installed | DataFrame I/O for engine components | Already the engine's universal data carrier per `BaseComponent` |
| **defusedxml** | NOT installed; pinned nowhere; **CONTEXT.md D-C4 references defusedxml.lxml** [VERIFIED: `pip show` returned ModuleNotFoundError; `defusedxml.lxml` flagged DEPRECATED in upstream README on Context7 — see Pitfall P-1] | XXE / billion-laughs protections at the parser boundary | **Caveat: `defusedxml.lxml` is deprecated and the upstream guidance is to use a secure-configured `lxml.etree.XMLParser`. Recommendation: substitute the secure-XMLParser pattern from `extract_xml_fields.py` for D-C4 wherever it says "defusedxml.lxml wrappers". Surface in plan-check or discuss-phase amendment.** |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest** | `>=8.0,<10` | Test runner, fixtures, markers | Per-parameter pos+neg tests, E2E .item integration tests |
| **pytest-cov** | 7.0.0 installed [VERIFIED: `pip show pytest-cov`] | Per-module line coverage (>=95% gate per D-D2 / Phase 14 prep) | Coverage gate per plan 7. Standard invocation: `pytest --cov=src/v1/engine/components/file/file_input_xml --cov=src/v1/engine/components/file/file_input_msxml --cov=src/v1/engine/components/transform/extract_xml_fields --cov=src/v1/engine/components/transform/xml_map --cov-report=term-missing --cov-fail-under=95`. The 2 new output modules are added to the `--cov` list when they exist. |
| (test fixtures only) `tests/talend_xml_samples/Job_*.item` | repo-tracked | Hand-authored Talend job XML for E2E | Existing for tFileInputXML / tExtractXMLField / tXMLMap. Hand-author NEW fixtures for tFileOutputXML (simple + with-attributes + with-namespace) and tAdvancedFileOutputXML (hierarchical with ROOT/GROUP/LOOP). Existing fixture dir holds 1 each — pattern is well established. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `lxml.etree.iterparse` | `xml.sax` (stdlib) | SAX is event-only, no DOM/XPath; iterparse is the documented streaming-with-tree-context API for lxml. iterparse wins. [VERIFIED: lxml 6.0 docs via Context7] |
| `etree.xmlfile` (incremental) | Build full `etree.Element` tree, then `etree.tostring` | Buffers all rows in memory — defeats output streaming. xmlfile is the documented incremental API and the only correct choice for D-C3. [VERIFIED: lxml 6.0 docs via Context7] |
| Bare `etree.XMLParser()` | `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` | Default parser allows XXE / billion-laughs in some configurations. Secure flags are the project standard (already used by `extract_xml_fields.py:153-159`). [CITED: defusedxml README on Context7; existing repo pattern] |
| Migrate `file_input_xml.py` incrementally (keep stdlib + add lxml path under threshold flag) | Full migration to lxml in one plan | Two parsers in one component is harder to test and breaks D-C5 (no fallback to stdlib). Full migration is the rewrite-over-patch approach the project memory recommends. |

**Installation:**
```bash
# lxml is already installed via the project's `xml` extra:
pip install -e .[xml]
# pytest-cov already installed; no new test-runner work needed.
# defusedxml: per D-C4 caveat, NOT recommended to add; use lxml's XMLParser flags instead.
# If the planner / user insist on defusedxml after the caveat is reviewed:
#   pip install defusedxml  # version 0.7.1 (latest)
```

**Version verification:**
- `lxml`: latest = 6.1.0 (PyPI as of 2026-05-08); installed = 6.0.3; pinned `>=4.9,<7` → both 5.x and 6.x satisfy the contract. CONTEXT.md D-C1 says "lxml 5.x" — installed is 6.0.3, which is HIGHER. Recommendation: leave the pin alone (already correct), document `lxml 5.x or 6.x` in the plan, prefer to NOT bump lxml as part of Phase 12 scope (avoids dragging an lxml-bump into a feature-parity phase). [VERIFIED: `pip index versions lxml` 2026-05-08; pip show; pyproject.toml:19]
- `defusedxml`: latest = 0.7.1 (single-maintainer, last release 2021); upstream is in maintenance-mode and deprecating `.lxml` submodule per README. [VERIFIED: `pip index versions defusedxml`; defusedxml README via Context7]

## Architecture Patterns

### System Architecture Diagram

```
                            Talend .item XML
                                    |
                                    v
                  +-------------------------------------+
                  |  Converter Layer                    |
                  |  (talend_to_v1)                     |
                  |                                     |
                  |  - file/file_input_xml.py           |
                  |  - file/file_input_msxml.py         |
                  |  - file/file_output_xml.py          |
                  |     (currently `tAdvancedFileOutput |
                  |      XML` only -- ADD `tFileOutput  |
                  |      XML` registration in Phase 12) |
                  |  - transform/extract_xml_fields.py  |
                  |  - transform/xml_map.py             |
                  +-------------------------------------+
                                    |
                                    v   (JSON config dict per component)
                  +-------------------------------------+
                  |  ETLEngine.run_job()                |
                  |  - DAG topo sort                    |
                  |  - per-component instantiation      |
                  |    via @REGISTRY.register decorators|
                  |  - data flow routing                |
                  +-------------------------------------+
                                    |
                                    v   (DataFrame per flow)
+-----------------------------------+-----------------------------------+
|                                                                       |
v                                                                       v
+--- INPUT components ---------+              +--- OUTPUT components --------+
|                              |              |                              |
|  FileInputXML  -+            |              |  FileOutputXML  --+          |
|  FileInputMSXML +-+          |              |   (NEW, Phase 12) |          |
|                  |           |              |                   |          |
|                  v           |              |                   v          |
|         _process() -- BaseComp lifecycle:   |   _process(chunk) -- streaming
|         1. file size > threshold?           |   xmlfile context: open once,
|         2. DOM     OR  iterparse path       |   write per chunk, flush.
|         3. namespace strip / qualify        |   (mirror of FileOutputDelimited
|         4. row dict per loop_query node     |    `_streaming_write_started`)
|         5. dataframe assembly               |                              |
|         6. REJECT for parse fails           |   AdvancedFileOutputXML --+  |
|                                             |   (NEW, Phase 12)         |  |
|         secure parser:                      |                           v  |
|         etree.XMLParser(resolve_entities=   |   _process() -- ROOT/GROUP/  |
|           False, no_network=True,           |   LOOP TABLE -> hierarchical |
|           load_dtd=False)                   |   xmlfile emission;          |
|                                             |   nested xf.element() ctx-mgr|
+------------------------------+              +------------------------------+

                   +--- TRANSFORM components ----+
                   |                             |
                   |  ExtractXMLField            |
                   |   (per-row XPath over an    |
                   |    XML column)              |
                   |                             |
                   |  XMLMap                     |
                   |   (per-input-row XML tree   |
                   |    -> output rows;          |
                   |    audit-flagged data-loss  |
                   |    bug iloc[0,0] -> fix)    |
                   +-----------------------------+

  Java Bridge (Py4J + Arrow):  NOT TOUCHED in Phase 12 (D-E2). xml_map.py
  has no live bridge calls today; "expression_filter" param is extracted by
  the converter but un-consumed by the engine (existing engine_gap).
```

**Reader trace for the primary input use case (read XML file → DataFrame):**

1. ETLEngine instantiates `FileInputXML` based on JSON config → registry lookup.
2. `BaseComponent.execute()` runs lifecycle (validate_config → resolve context → _process).
3. `_process()` checks `os.stat(filename).st_size`; if `< xml_streaming_threshold_mb * 1024 * 1024` → DOM path (`etree.parse(filename, parser=secure_parser)`); else → streaming path (`etree.iterparse(filename, events=('end',), tag=loop_tag)` + `element.clear(keep_tail=True)` after each yielded element).
4. For each loop_query match → evaluate per-column XPath, build row dict.
5. Reject parse / nodecheck failures → REJECT flow with errorCode/errorMessage.
6. Return `{"main": df, "reject": reject_df, "stats": {...}}` to BaseComponent which writes globalMap.

**Reader trace for the primary output use case (DataFrame → XML file):**

1. ETLEngine routes input flow to `FileOutputXML._process(chunk)` (per-chunk if streaming mode active).
2. On the first chunk, `_process()` opens an `etree.xmlfile(path, encoding=...)` context manager; on subsequent chunks, it reuses the still-open context (state held on `self`, mirror of `_streaming_write_started`).
3. Inside `xf.element(root_tag)` → for each row → emit `xf.element(row_tag)` with sub-elements per column (or attributes when MAPPING.AS_ATTRIBUTE=true).
4. After last chunk, the context manager closes the file.
5. `_update_stats()` writes `{id}_NB_LINE`.

### Recommended Project Structure

```
src/v1/engine/components/
├── file/
│   ├── file_input_xml.py            # MIGRATE stdlib -> lxml (Plan 3 / 555 LOC)
│   ├── file_input_msxml.py          # AUDIT-AND-LIGHT-FIX (Plan 4 / 172 LOC, has tests)
│   ├── file_output_xml.py           # NEW (Plan 6) — register `FileOutputXML`, `tFileOutputXML`
│   ├── file_output_advanced_xml.py  # NEW (Plan 6) — register `AdvancedFileOutputXML`, `tAdvancedFileOutputXML`
│   └── _xml_io.py                   # NEW (Plan 2) — shared helpers: secure_xml_parser(), file_size_above_threshold(), iterparse_with_clearing()
└── transform/
    ├── extract_xml_fields.py        # AUDIT-AND-FIX (Plan 4 / 260 LOC, has tests)
    └── xml_map.py                   # AUDIT-AND-FIX (Plan 5 / 738 LOC, NO engine tests, iloc[0,0] data-loss bug)

src/converters/talend_to_v1/components/file/
├── file_input_xml.py                # exists; minor adjustments only (per audit findings, all params already extracted)
├── file_input_msxml.py              # exists; minor adjustments only
├── file_output_xml.py               # exists but ONLY registers `tAdvancedFileOutputXML` — ADD second class for `tFileOutputXML` (Plan 6)
├── extract_xml_fields.py            # exists; minor adjustments only
└── transform/xml_map.py             # exists; minor adjustments only

tests/v1/engine/components/file/
├── test_file_input_xml.py           # NEW (Plan 3) — 30-40 tests target
├── test_file_input_msxml.py         # exists, 13 tests, EXTEND to per-param pos+neg (Plan 4)
├── test_file_output_xml.py          # NEW (Plan 6) — 25-35 tests target
└── test_file_output_advanced_xml.py # NEW (Plan 6) — 35-45 tests target

tests/v1/engine/components/transform/
├── test_extract_xml_fields.py       # exists, 24 tests, EXTEND to per-param pos+neg (Plan 4)
└── test_xml_map.py                  # NEW (Plan 5) — 35-50 tests target

tests/talend_xml_samples/
├── Job_tFileInputXML_0.1.item       # exists
├── Job_tFileInputMSXML_0.1.item     # MISSING — hand-author (Plan 4)
├── Job_tExtractXMLFields_0.1.item   # exists
├── Job_tXMLMap_0.1.item             # exists
├── Job_tFileOutputXML_0.1.item      # MISSING — hand-author (Plan 6)
└── Job_tAdvancedFileOutputXML_0.1.item  # MISSING — hand-author (Plan 6)
```

### Pattern 1: Threshold-Switched Parsing (DOM vs streaming)

**What:** Inside `_process()`, branch on file size. Below threshold → `etree.parse()` returns full tree → XPath evaluation as today. Above threshold → `etree.iterparse(events=('end',), tag=loop_tag)` + `element.clear(keep_tail=True)` after consuming each match.

**When to use:** All 4 input components when given a file path. `tExtractXMLField` and `tXMLMap` parse XML strings from a column — no file size; always treat as small (DOM).

**Example** (skeleton; concrete code lives in `_xml_io.py` after Plan 2):
```python
# Source: lxml 6.0 docs (Context7) -- https://lxml.de/6.0/tutorial.html
# Source: existing repo pattern in src/v1/engine/components/transform/extract_xml_fields.py:153-159
from lxml import etree
import os

def secure_xml_parser() -> etree.XMLParser:
    """XXE / billion-laughs hardened parser. Replaces defusedxml.lxml per D-C4 caveat."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,  # fail loud per fix-source rule
    )

def parse_or_iterparse(filename: str, threshold_mb: int, loop_tag: str):
    """Yield elements matching loop_tag.

    Below threshold: load DOM, iterate xpath matches.
    Above threshold: stream via iterparse, clear after each match.
    """
    size_mb = os.stat(filename).st_size / (1024 * 1024)
    parser = secure_xml_parser()
    if size_mb < threshold_mb:
        tree = etree.parse(filename, parser=parser)
        # caller does the xpath against tree.getroot()
        return ("dom", tree)
    else:
        # iterparse honours XMLParser flags via `parser=` since lxml 4.x
        # tag filter limits which 'end' events fire
        ctx = etree.iterparse(filename, events=("end",), tag=loop_tag, **_secure_iterparse_kwargs())
        return ("stream", ctx)

def consume_streaming(ctx):
    for _event, element in ctx:
        yield element
        # CRITICAL: clear after consume to free memory
        element.clear(keep_tail=True)
        # also clear preceding siblings to release ancestors
        while element.getprevious() is not None:
            del element.getparent()[0]
```

### Pattern 2: Incremental XML Output via `etree.xmlfile`

**What:** Open `etree.xmlfile(path, encoding=...)` once on the first chunk; nest `xf.element(root_tag)` and per-row `xf.element(row_tag)`; flush after each chunk; close at end.

**When to use:** `tFileOutputXML` and `tAdvancedFileOutputXML`, both in single-DataFrame and streaming-mode invocations.

**Example** (verified pattern from lxml 6.0 docs):
```python
# Source: lxml 6.0 API docs (Context7) -- https://lxml.de/6.0/api.html
from io import BytesIO
from lxml import etree

f = BytesIO()  # in production, an open binary file handle
with etree.xmlfile(f, encoding="ISO-8859-15") as xf:
    xf.write_declaration()
    with xf.element("root"):
        for value in "123":
            el = etree.Element("xyz", attr=value)
            xf.write(el)
            xf.flush()
            el = None  # discard reference; helps GC
```

**Streaming-output state** (mirror of `FileOutputDelimited._streaming_write_started`):

```python
# Repo-internal mirror of bb5b97f streaming pattern. State held on self.
# First _process(chunk) call opens xmlfile context; subsequent calls write into the open context.
# A single component-instance attribute holds the context manager.

class FileOutputXML(BaseComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._streaming_xmlfile_ctx = None
        self._streaming_xmlfile_root_ctx = None

    def reset(self):
        super().reset()
        # close any leftover context cleanly during iterate re-execution
        if self._streaming_xmlfile_root_ctx is not None: ...
        # set both to None
```

### Pattern 3: Audit-First Plan Decomposition (Phase 11 mirror)

**What:** Plan 1 is a re-audit of the 5 existing audit docs against current `HEAD`, producing a per-component issue list with status (FIXED-by-Phase-7.1 / STILL-OPEN / NEW). Subsequent plans tackle one component (or a tight group) per plan, in waves that respect dependency.

**When to use:** Phase 12 contractually adopts D-B1. Plan 1's output is consumed by all later plans.

### Anti-Patterns to Avoid

- **Buffer-and-write XML output:** building an in-memory `etree.ElementTree` then `tostring(...)` defeats D-C3 streaming. Use `etree.xmlfile` instead.
- **Holding root references in iterparse:** keeps the entire prefix tree alive. Use `element.clear(keep_tail=True)` AND walk back removing prior siblings (see Pattern 1 example).
- **Falling back to stdlib `xml.etree`:** D-C5 forbids it. If lxml import fails, raise `ConfigurationError("lxml is required for XML components; install with `pip install -e .[xml]`")`.
- **`recover=True` on the secure parser:** swallows malformed XML silently. Set `recover=False`. Reject malformed input via REJECT flow at the row level, not via parser-level recovery.
- **`lstrip()` on XPath strings:** strips per-character, not by prefix. Use `removeprefix()` (Python 3.9+) — already a documented project rule (D-76). The existing `xml_map.py:281` still has a `lstrip("/")` per the audit; refactor during Plan 5.
- **Mocking lxml.etree:** D-D4 forbids it. Use real XML strings/files in fixtures.
- **Coverage-gaming via `# pragma: no cover`:** Phase 14 will gate this; Plan 7 must spot-check that no new pragmas were added under the 6 in-scope modules.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Streaming XML parse | Manual SAX-style state machine | `lxml.etree.iterparse(events=('end',), tag=...)` + `element.clear(keep_tail=True)` | Documented, C-fast, handles namespaces correctly. [VERIFIED: lxml 6.0 docs Context7] |
| Incremental XML write | Open file, manage indentation, escape entities, declaration handling | `lxml.etree.xmlfile()` context manager | Handles encoding, declaration, escaping, async support. Discards written elements as you go. [VERIFIED: lxml 6.0 docs Context7] |
| XXE / billion-laughs protection | DIY entity expansion limits | `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` | libxml2 has built-in expansion limits and the flags disable risky paths. defusedxml.lxml is deprecated in 2026 (the project's CONTEXT.md predates this finding). [CITED: defusedxml README on Context7] |
| Namespace prefix qualification | Walking the tree, building a custom prefix map | lxml's `etree.QName()` + `nsmap=` parameters and `xpath(..., namespaces={'p': 'uri'})` | Built-in. Currently file_input_xml's `normalize_nsmaps()` handles only the root element — the audit flags this as P1. lxml's nsmap API is the right migration target. |
| XPath 1.0 evaluation | Custom XPath impl | `element.xpath(expr, namespaces=...)` | lxml supports full XPath 1.0; tExtractXMLField + xml_map already use it. |
| `.item` XML parsing for tests | Custom XML reader for fixtures | Project's existing `XmlParser` in `src/converters/talend_to_v1/xml_parser.py` + the converter pipeline | Drives E2E: `convert_job(.item) -> JSON config -> ETLEngine.run_job()`. Used by all existing engine integration tests; keep using it. |
| File size threshold check | `os.path.getsize()` plus arithmetic | `os.stat(path).st_size / (1024*1024) >= threshold_mb` (single line in `_xml_io.py`) | Trivial, but centralize so the threshold flag is honored consistently across 6 components. |

**Key insight:** **No custom XML primitives. Every part of the parsing/serialization stack is already in lxml.** The work in Phase 12 is engine-component logic — namespace policy, REJECT routing, streaming-mode coordination, per-component param semantics — *not* re-inventing XML parsing.

## Component-by-Component Audit Baseline

This section gives the planner the per-component starting hypothesis from existing audit docs (dated 2026-04-03..04, predating Phase 7.1 cross-cutting fixes). Plan 1 verifies each claim against current `HEAD`.

### tFileInputXML (`src/v1/engine/components/file/file_input_xml.py`, 555 LOC, stdlib)

**Talaxie javajet parameters** [VERIFIED via WebFetch on `tFileInputXML_java.xml` 2026-05-08]:

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| FILENAME | FILE | `__COMP_DEFAULT_FILE_DIR__/in.xml` | Required |
| LOOP_QUERY | TEXT | `/bills/bill/line` | XPath for repeating elements |
| MAPPING | TABLE | -- | Items: QUERY (XPath), NODECHECK (CHECK, default false) |
| LIMIT | TEXT | empty | empty = unlimited |
| DIE_ON_ERROR | CHECK | false | |
| ENCODING | ENCODING_TYPE | ISO-8859-15 | NOT UTF-8 |
| GENERATION_MODE | CLOSED_LIST | DOM4J | DOM4J or SAX |
| IGNORE_NS | CHECK | false | shown when GENERATION_MODE='DOM4J' |
| IGNORE_DTD | CHECK | false | |
| ADVANCED_SEPARATOR | CHECK | false | |
| THOUSANDS_SEPARATOR | TEXT | `,` | shown when ADVANCED_SEPARATOR='true' |
| DECIMAL_SEPARATOR | TEXT | `.` | shown when ADVANCED_SEPARATOR='true' |
| CHECK_DATE | CHECK | false | |
| USE_SEPARATOR | CHECK | false | |
| FIELD_SEPARATOR | TEXT | `,` | shown when USE_SEPARATOR='true' |
| TMP_FILENAME | FILE | empty | hidden/design-time per existing converter |
| SCHEMA_OPT_NUM | TEXT | 100 | hidden |
| SCHEMA_REJECT | SCHEMA_TYPE | -- | errorCode + errorMessage columns |

**Starting-hypothesis open issues** [CITED: `docs/v1/audit/components/file/tFileInputXML.md` 2026-04-03]:

| ID | Status (claim) | Action |
|----|---------------|--------|
| BUG-FIX-001 | P0 cross-cutting `_update_global_map` crash | RE-CHECK: likely RESOLVED by Phase 7.1 (`base_component.py:304` was rewritten in 07.1-01-PLAN). Plan 1 verifies. |
| ENG-FIX-002 | P1 No REJECT flow | OPEN — re-verify in Plan 1, fix in Plan 3 |
| ENG-FIX-003 | P1 No SAX streaming | OPEN — supersedes by D-C2 threshold-switched iterparse |
| ENG-FIX-004 | P1 Namespace detection only finds root | OPEN — fix during lxml migration in Plan 3; lxml's `iter().nsmap` exposes child namespaces |
| ENG-FIX-005 | P1 `zip()` drops columns silently | OPEN — fix in Plan 3 |
| ENG-FIX-006 | P2 Encoding only in passthrough mode | OPEN — fix in Plan 3 |
| ENG-FIX-007 | P2 LIMIT not enforced in tabular mode | OPEN — fix in Plan 3 |
| ENG-FIX-008 | P2 Bare `@attr` XPath fails silently | OPEN — fix in Plan 3 |
| STD-FIX-001 | P2 RuntimeError instead of ConfigurationError | OPEN — fix in Plan 3 |
| TEST-FIX-001 | P1 Zero engine unit tests | NEW: 30-40 per-param tests in Plan 3 |

**Migration scope:** Full rewrite of `_parse_xml`, `extract_value`, `normalize_nsmaps`, `find_element_by_manual_navigation` against `lxml.etree`. Estimated 555 LOC → ~400-500 LOC.

### tFileInputMSXML (`src/v1/engine/components/file/file_input_msxml.py`, 172 LOC, lxml today)

**Talaxie javajet parameters** [VERIFIED via WebFetch on `tFileInputMSXML_java.xml` 2026-05-08]:

| Param | Type | Default |
|-------|------|---------|
| FILENAME | FILE | `__COMP_DEFAULT_FILE_DIR__/in.xml` |
| ROOT_LOOP_QUERY | TEXT | `/mailbox/emails/email` |
| IGNORE_ORDER | CHECK | false |
| SCHEMAS | TABLE (NB_LINES=6) | items: SCHEMA, LOOP_PATH, MAPPING (SCHEMA_XPATH_QUERYS), CREATE_EMPTY_ROW |
| DIE_ON_ERROR | CHECK | false |
| TRIMALL | CHECK | true (note: NOT false) |
| CHECK_DATE | CHECK | false |
| IGNORE_DTD | CHECK | false |
| GENERATION_MODE | CLOSED_LIST | Dom4j (DOM4J or SAX) |
| ENCODING | ENCODING_TYPE | ISO-8859-15 |

**Starting-hypothesis status** [CITED: `docs/v1/audit/components/file/tFileInputMSXML.md` 2026-04-05]:

- Engine: GREEN (engine implementation exists, secure parser in place at line 107-113)
- 13 engine tests already; per-parameter pos+neg pattern requires extending to ~30 tests in Plan 4
- Open: P2 multi-schema TABLE sub-schema extraction (rare); P2 SAX/streaming (subsumed by D-C2)
- No `Job_tFileInputMSXML_0.1.item` fixture today — hand-author one in Plan 4

### tExtractXMLField (`src/v1/engine/components/transform/extract_xml_fields.py`, 260 LOC, lxml today)

**Talaxie javajet parameters** [VERIFIED via WebFetch on `tExtractXMLField_java.xml` 2026-05-08]:

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| XMLFIELD | PREV_COLUMN_LIST | -- | column containing XML |
| LOOP_QUERY | TEXT | `/bills/bill/line` | |
| MAPPING | TABLE | -- | QUERY (XPath), NODECHECK (CHECK, false) — BASED_ON_SCHEMA |
| LIMIT | TEXT | empty | empty = unlimited; **0 = read nothing** |
| DIE_ON_ERROR | CHECK | false | |
| IGNORE_NS | CHECK | false | |
| (hidden) USE_ITEMS, LOOP_QUERY_BASE, USE_XML_FIELD, XML_TEXT, XML_PREFIX, SCHEMA_OPT_NUM | various | various | hidden — converter already excludes |

**Status** [CITED: `docs/v1/audit/components/transform/tExtractXMLField.md` updated 2026-05-06]:

- GREEN — recently hardened (limit=0 fix, XMLParser security flags, 23 engine tests added in Phase 7.x)
- Plan 4 work is light: extend tests from 24 to ~30-35 per per-param pos+neg rule, ensure 95% coverage
- E2E `Job_tExtractXMLFields_0.1.item` exists

### tXMLMap (`src/v1/engine/components/transform/xml_map.py`, 738 LOC, lxml today, NO engine tests)

**Talaxie javajet parameters** [VERIFIED via WebFetch on `tXMLMap_java.xml` 2026-05-08]:

| Param | Type | Default |
|-------|------|---------|
| MAP | EXTERNAL | empty (visual editor reference) |
| DIE_ON_ERROR | CHECK | true (note: `true`, unlike most components) |
| KEEP_ORDER_FOR_DOCUMENT | CHECK | false |

Plus **nodeData** (parsed by converter): `inputTrees`, `outputTrees`, `connections`, `varTables`, derived `looping_element`, derived `expressions`, `expression_filter` (Java).

**Starting-hypothesis open issues** [CITED: `docs/v1/audit/components/transform/tXMLMap.md` 2026-04-04]:

| ID | Severity | Action |
|----|----------|--------|
| BUG-XMP-003 | P0 — `iloc[0,0]` data-loss for multi-row Document input | Plan 5 — iterate input rows, not just first |
| BUG-XMP-012/013 | P0 cross-cutting | RE-CHECK: likely RESOLVED by Phase 7.1 |
| BUG-XMP-004 | P1 — `self.id` overwritten mid-execute | Plan 5 |
| BUG-XMP-006 | P1 — Ancestor fallback returns wrong nodes | Plan 5 |
| BUG-XMP-014 | P1 — `split_steps()` destroys XPath predicates | Plan 5 |
| ENG-XMP-001 | P0 — No lookup/join — silent data loss when LOOKUP connections exist | Plan 5: implement OR convert to conditional `needs_review` (D-E1) for "lookup/join not supported" |
| ENG-XMP-003 | P1 — No reject flow | Plan 5 |
| ENG-XMP-004 | P1 — No expression filter (Java) | **Convert to conditional `needs_review` (D-E1) — D-E1 explicitly defers Java-bridge changes to Phase 13. Per current code, `xml_map.py` does NOT call into the Java bridge today (verified by grep). Phase 12 does not add an expression_filter execution path; document and emit needs_review when a job has activateExpressionFilter='true'.** |
| ENG-XMP-005 | P1 — No Document output mode (allInOne) | Convert to conditional `needs_review` (D-E1) |
| ENG-XMP-006 | P1 — Die on error ignored | Plan 5 — small fix |
| STD-XMP-001 | P1 — 46 print() statements | Plan 5 — replace with logger |
| SEC-XMP-001 | P2 — No XML bomb protection | Plan 5 — switch to `secure_xml_parser()` from `_xml_io.py` |

**Bridge surface (D-E1):** `xml_map.py` has ZERO calls into `JavaBridgeManager` today [VERIFIED: `grep -n "JavaBridge\|java_bridge\|execute_one_time_expression" src/v1/engine/components/transform/xml_map.py` returned no matches]. The "Java-bridge-coupled tests that may need xfail" risk is therefore **theoretical for Phase 12**: there is no live bridge path to xfail. If the planner DOES add expression_filter execution within Phase 12 (against contract D-E1), the bridge methods that would be touched are `JavaBridgeManager.execute_one_time_expression()` and `RowWrapper`-based row evaluation — both currently being changed by manager. Recommendation: Plan 5 must explicitly state "no expression_filter execution; emit needs_review via D-E1 pattern" and add zero new bridge tests; D-E2's `xfail` clause becomes a nullity in this phase.

**Engine test gap:** Plan 5 must add ~35-50 engine tests. No E2E fixture-based test today. `Job_tXMLMap_0.1.item` exists; the engine test file (`test_xml_map.py`) does not.

### tFileOutputXML (simple, NEW — no engine, no converter today)

**Talaxie javajet parameters** [VERIFIED via WebFetch on `tFileOutputXML_java.xml` 2026-05-08]:

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| FILENAME | FILE | `__COMP_DEFAULT_FILE_DIR__/out.xml` | |
| INPUT_IS_DOCUMENT | CHECK | false | If true, input column already holds full XML doc |
| DOCUMENT_COL | COLUMN_LIST | -- | shown if INPUT_IS_DOCUMENT='true' |
| ROW_TAG | TEXT | `row` | shown if INPUT_IS_DOCUMENT='false' |
| ROOT_TAGS | TABLE | -- | custom root XML tags (when INPUT_IS_DOCUMENT='false') |
| MAPPING | TABLE | -- | items: AS_ATTRIBUTE (CHECK), SCHEMA_COLUMN_NAME (column→element/attr) |
| USE_DYNAMIC_GROUPING | CHECK | false | |
| GROUP_BY | TABLE | -- | items: COLUMN, LABEL |
| FLUSHONROW | CHECK | false | |
| FLUSHONROW_NUM | TEXT | 1 | shown if FLUSHONROW='true' |
| ENCODING | ENCODING_TYPE | ISO-8859-15 | NOT UTF-8 |
| SPLIT | CHECK | false | |
| SPLIT_EVERY | TEXT | 1000 | shown if SPLIT='true' |
| CREATE | CHECK | true | |
| TRIM | CHECK | false | shown if INPUT_IS_DOCUMENT='true' |
| ADVANCED_SEPARATOR | CHECK | false | |
| THOUSANDS_SEPARATOR | TEXT | `,` | |
| DECIMAL_SEPARATOR | TEXT | `.` | |
| DELETE_EMPTYFILE | CHECK | false | |

**Build scope (Plan 6):**
- New converter class `FileOutputXMLConverter` in `src/converters/talend_to_v1/components/file/file_output_xml.py` (currently only registers `tAdvancedFileOutputXML` — add a second `@REGISTRY.register("tFileOutputXML")` class)
- New engine class `FileOutputXML` in `src/v1/engine/components/file/file_output_xml.py`
- New tests: converter (~25 tests), engine (~25-35 tests)
- Hand-authored fixture `Job_tFileOutputXML_0.1.item`

**Implementation key:** map columns→sub-elements, columns→attributes (per MAPPING.AS_ATTRIBUTE), incremental write via `etree.xmlfile`, honor `ROOT_TAGS` TABLE for `<wrapper><row>...</row></wrapper>` style. SPLIT support mirrors `FileOutputDelimited` SPLIT_EVERY (Phase 4).

### tAdvancedFileOutputXML (hierarchical, NEW engine — converter exists)

**Talaxie javajet parameters** [CITED: `docs/v1/audit/components/file/tAdvancedFileOutputXML.md` — converter already extracts all 33 unique params + 2 framework]:

ROOT/GROUP/LOOP TABLE stride-5 (PATH, COLUMN, VALUE, ATTRIBUTE, ORDER) drives nested element emission. USESTREAM/STREAMNAME for output-stream mode (vs file). MERGE for append-to-existing-file (DOM4J only). FILE_VALID + DTD_VALID/XSL_VALID radio for output validation. SPLIT/SPLIT_EVERY. CREATE_EMPTY_ELEMENT, ADD_EMPTY_ATTRIBUTE, ADD_UNMAPPED_ATTRIBUTE, ADD_DOCUMENT_AS_NODE, OUTPUT_AS_XSD. ADVANCED_SEPARATOR + thousands/decimal. GENERATION_MODE (DOM4J/Null), ENCODING (ISO-8859-15), DELETE_EMPTYFILE.

**Build scope (Plan 6):**
- New engine class `AdvancedFileOutputXML` in `src/v1/engine/components/file/file_output_advanced_xml.py`
- New tests (~35-45 engine tests)
- Hand-authored fixture `Job_tAdvancedFileOutputXML_0.1.item`
- Converter is already gold-standard per the prior audit; no rewrite

**Implementation challenge — hierarchical streaming output:** ROOT/GROUP/LOOP define a 3-deep skeleton. ROOT once at top, GROUP wraps batches, LOOP per-row inside each group. With `etree.xmlfile`, nest the `xf.element()` context managers and re-enter LOOP per row. **Critical: do NOT buffer the whole tree** (Pitfall P-2). Easy to write code that builds `<root>...</root>` in memory under the guise of "streaming"; the test must catch this (Pitfall P-2 has the test recipe).

**Sub-features deferred via D-E1 conditional `needs_review`:**
- DTD_VALID / XSL_VALID validation (write-then-validate is a separate concern; FILE_VALID=true emits needs_review)
- OUTPUT_AS_XSD generation (auto-generate XSD alongside XML — niche)
- ADD_DOCUMENT_AS_NODE (requires Document column type which the engine doesn't fully support yet)
- ADD_UNMAPPED_ATTRIBUTE (rare; emits needs_review if true)
- MERGE (append to existing XML — requires parsing the existing file then appending; doable in DOM4J mode but adds significant complexity. Recommend deferring with conditional needs_review for the first cut.)

## Plan / Wave Decomposition Recommendation

7 plans in 6 waves, mirroring Phase 11 Oracle. Each plan owns a tight scope.

| Plan | Wave | Scope | Depends On | Risk |
|------|------|-------|------------|------|
| **12-01** | W1 | **Re-audit & baseline.** Read 5 existing audit docs vs current `HEAD`, mark P0/P1/P2 as RESOLVED / OPEN / NEW. Produce `12-01-AUDIT.md` covering all 6 components (incl. tFileOutputXML which has no prior audit). Decide conditional `needs_review` list per D-E1. NO CODE CHANGES. | -- | Low |
| **12-02** | W2 | **Shared infrastructure: `_xml_io.py`** with `secure_xml_parser()`, `parse_or_iterparse()` threshold helper, `consume_streaming()` clearing helper. Plus 15-20 unit tests for the helpers (synthetic XML, threshold simulation). Also: documentation amendment in `pyproject.toml` if `xml` extra needs adjustment (it doesn't per current state). NO component changes yet. | 12-01 | Low |
| **12-03** | W3 | **`tFileInputXML` lxml migration + audit fixes.** Largest single plan: 555 LOC stdlib → lxml, 30-40 new engine tests, fix the 7-9 OPEN audit items (REJECT, namespace, encoding, LIMIT, `@attr` XPath, ConfigurationError, `zip()` mismatch). Use `_xml_io.py` helpers from 12-02. | 12-02 | **HIGH** — full rewrite |
| **12-04** | W3 (parallel to 12-03) | **`tFileInputMSXML` + `tExtractXMLField` per-param test extension + minor audit fixes.** Both already lxml; both already have engine tests. Light-touch component fixes plus expanding tests to per-parameter pos+neg per D-D1 (~13→~30 for MSXML; ~24→~30-35 for ExtractXMLField). Add `Job_tFileInputMSXML_0.1.item` fixture. | 12-02 | Low |
| **12-05** | W4 | **`tXMLMap` audit fixes + engine tests.** `iloc[0,0]` data-loss bug; print()→logger; 35-50 new engine tests; `Job_tXMLMap_0.1.item` E2E. Convert lookup/join, expression_filter, allInOne to D-E1 conditional `needs_review`. NO Java-bridge work. | 12-02 | **HIGH** — 738 LOC component, no test net, multiple intertwined bugs |
| **12-06** | W5 | **`tFileOutputXML` (simple) + `tAdvancedFileOutputXML` (hierarchical) NEW engine components.** Both incremental via `etree.xmlfile`. New `tFileOutputXML` converter class. Hand-author 2 `.item` fixtures. ~60-80 new tests across both. | 12-02, 12-04 (output components depend on input/extract patterns being stable) | **MEDIUM-HIGH** — net-new code, hierarchical streaming is non-trivial |
| **12-07** | W6 | **E2E + coverage gate.** Run all 6 component E2E tests via real `convert_job() + run_job()` pipeline. Run `pytest --cov=...` for the 6 modules; assert ≥95% per module. Produce `12-VERIFICATION.md` and `12-PHASE-SUMMARY.md`. Include manual checkpoint per Phase 11 pattern (line up Citi production .item samples if/when the user can supply them). | 12-03, 12-04, 12-05, 12-06 | Low |

**Wave timing:**
- W1: 12-01 alone
- W2: 12-02 alone
- W3: 12-03 + 12-04 in parallel (different files)
- W4: 12-05 alone (xml_map is the heaviest fix)
- W5: 12-06 alone (new components)
- W6: 12-07 alone (gate)

**Dependency justification for serializing W4 vs W3:** `tXMLMap` shares helpers (`_xml_io.py`) with the input components but doesn't depend on their fixes. We could parallelize 12-03/04/05, but 12-05 is heavier and the project memory (`feedback_extensive_questions_complex_phases`) recommends giving the trickiest plan its own wave for review headroom. Keep 12-05 in its own wave.

## Common Pitfalls

### Pitfall P-1: defusedxml.lxml is deprecated

**What goes wrong:** Plan adds `defusedxml.lxml` per CONTEXT D-C4 → years from now, `from defusedxml.lxml import parse` raises `ImportError` and the engine breaks. Worse, the false sense of security if maintainers see "defusedxml" and assume current best practice.

**Why it happens:** CONTEXT.md predates the upstream deprecation announcement. `defusedxml`'s author marked the `.lxml` submodule as deprecated in the README; the package's last release was 0.7.1 in 2021 and `defusedxml.lxml` is slated for removal.

**How to avoid:** Substitute `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` everywhere — this is the documented replacement and the project's existing pattern (see `extract_xml_fields.py:153-159`, `file_input_msxml.py:107-113`). Centralize in `_xml_io.py:secure_xml_parser()`. lxml's libxml2 backend has built-in expansion limits, addressing billion-laughs.

**Warning signs:** Any line of code containing `from defusedxml.lxml`. Reject in code review.

[CITED: `https://github.com/tiran/defusedxml/blob/main/README.md` via Context7 — "The `defusedxml.lxml` module is deprecated and will be removed in a future release"]

### Pitfall P-2: "Streaming" output that buffers the full tree

**What goes wrong:** Developer writes:
```python
root = etree.Element("root")
for _, row in df.iterrows():
    el = etree.SubElement(root, "row")
    for col, val in row.items():
        sub = etree.SubElement(el, col)
        sub.text = str(val)
with open(filepath, "wb") as f:
    f.write(etree.tostring(root))
```
Looks like incremental construction; actually buffers the entire tree before any byte hits disk. For a 1M-row output, this is gigabytes of in-memory `Element` objects.

**Why it happens:** It's the natural `etree.SubElement` API; the streaming `xmlfile` API is less obvious.

**How to avoid:** Use `etree.xmlfile()` context manager. Inside the context, `xf.write(el)` writes to disk and you discard `el = None`. The test recipe for catching this regression: write 100k rows, check `psutil.Process().memory_info().rss` stays bounded (e.g., < 2× peak before write started); OR check that the output file size grows during the loop (byte-poll the file on a sentinel row).

**Warning signs:** No `etree.xmlfile` import in a tFileOutput*XML* module. `etree.SubElement` calls inside the per-row loop. `etree.tostring(root)` at the end of `_process()`.

[VERIFIED: lxml 6.0 docs (Context7) — `https://lxml.de/6.0/api.html`]

### Pitfall P-3: iterparse element-clearing bugs

**What goes wrong:** Three sub-flavors:

(a) **Forgetting `element.clear()`:** memory grows linearly with file size; defeats the streaming branch entirely.

(b) **Holding root references:** even with `element.clear()`, the prior siblings remain attached to the parent. After 1M rows you have 1M empty `<row/>` children of root. Fix: `while element.getprevious() is not None: del element.getparent()[0]`.

(c) **Accessing `element.text`/`element.tail` AFTER `element.clear()`:** values are cleared. Either capture them before `clear()` or pass `keep_tail=True` if you need the tail text downstream.

**Why it happens:** iterparse has an idiosyncratic memory-management contract. Default `clear()` drops the tail too, surprising many users.

**How to avoid:** centralize in `_xml_io.py:consume_streaming()` (Pattern 1 above). Test: build a 50 MB synthetic XML fixture (programmatic, in `conftest.py`), run input component, verify `tracemalloc` peak under 100 MB.

**Warning signs:** any iterparse loop without `element.clear()`. Any iterparse loop without sibling cleanup. Any post-clear access to `.text` or `.tail`.

[VERIFIED: lxml 6.0 tutorial (Context7) — `https://lxml.de/6.0/tutorial.html`]

### Pitfall P-4: Threshold "advisory not enforced"

**What goes wrong:** Threshold-check code computes file size but the streaming path is never taken because of a config-key typo, missing default, or the file-size code only runs when a flag is `true`. Result: files just below the threshold OOM, files just above silently fall back to DOM.

**Why it happens:** It's easy to forget to wire up the config key end-to-end (converter → JSON → engine `_process()`). Phase 1's ENG-13 history (config key alignment) is exactly this class of bug.

**How to avoid:** test `xml_streaming_threshold_mb=0` (always streaming) and `xml_streaming_threshold_mb=1000000` (never streaming) end-to-end with a real fixture. Spy on which code path executed (use a counter in `_xml_io.py` set during the parse-strategy decision, OR test by construction with a mock-friendly factory). Surface the chosen strategy in the engine log: `[{id}] XML strategy=DOM size=12.3MB threshold=50MB` ASCII-only. The log is testable.

**Warning signs:** Threshold default appearing in two places (drift bait). Streaming path with no test that proves it ran.

### Pitfall P-5: Namespace handling — only the root namespace seen

**What goes wrong:** `file_input_xml.py:normalize_nsmaps()` (current code) reads ONLY the root element's tag for `{ns}` and produces a single-prefix nsmap. Multi-namespace XML (SOAP envelopes, mixed XHTML) silently misroutes XPath. Existing audit P1: ENG-FIX-004.

**Why it happens:** Talend's `IGNORE_NS=true` pre-strips all namespaces — so it "works" when set. With `IGNORE_NS=false`, Talend's Java/Dom4j collects nsmaps from all elements; the Python port shortcut (root-only) is the bug.

**How to avoid:** lxml exposes per-element `element.nsmap` and tree-wide collection via iterating the tree. Build a complete prefix map. Or punt: support `IGNORE_NS=false` only for single-namespace docs, emit conditional `needs_review` when the document has multiple namespaces and IGNORE_NS=false.

**Warning signs:** any nsmap construction that reads only `tree.getroot().tag` or `tree.getroot().nsmap`. Tests that only use single-namespace fixtures.

### Pitfall P-6: tXMLMap `iloc[0, 0]` data-loss bug

**What goes wrong:** `xml_map.py` line ~506 reads `input_data.iloc[0, 0]` — exactly the first row, exactly the first column. If a tXMLMap input has 100 rows with XML Documents, 99 are dropped silently. This is the audit's P0 BUG-XMP-003.

**Why it happens:** Original implementer treated tXMLMap as a single-document transformer; Talend's tXMLMap iterates over all input rows.

**How to avoid:** Plan 5 must rewrite the input-row loop. Test: a 5-row Document input produces a per-row output (5 → N output rows where N is the looping_element count per Document × 5).

**Warning signs:** `iloc[0` anywhere in xml_map.py.

### Pitfall P-7: lstrip vs removeprefix on XPath strings

**What goes wrong:** `xml_map.py:281` (per audit) calls `tail.lstrip("/")`. `str.lstrip(chars)` strips ANY characters in `chars`, not the prefix string. `"/employees".lstrip("/")` happens to be correct; `"/employees".lstrip("/e")` returns `"mployees"`. A future code change to lstrip's argument will silently corrupt XPath.

**How to avoid:** `str.removeprefix("/")` is the project standard (D-76 from prior phase). Already enforced in the converter; the engine `xml_map.py` line 281 still has the bug. Plan 5 fixes.

**Warning signs:** any `.lstrip(` with a string argument longer than 1 char in any XML-touching code.

### Pitfall P-8: tFileInputXML stdlib→lxml semantic drift

**What goes wrong:** lxml's XPath evaluation differs subtly from stdlib's `findall(..., namespaces=...)`. Cases:
- lxml supports XPath 1.0 axes (e.g., `descendant::`, `ancestor::`); stdlib doesn't. After migration, expressions that PREVIOUSLY failed silently may now match — surprise behavior change.
- lxml returns `_Element` objects with full XPath context; stdlib returns `Element` with limited context. Code that relied on the stdlib type signature breaks.
- lxml's `parse()` raises `lxml.etree.XMLSyntaxError`; stdlib raises `xml.etree.ElementTree.ParseError`. Exception-handling code keyed on stdlib's ParseError must update.

**How to avoid:** the migration plan (12-03) must include a regression catalog: take all existing converter-generated JSON for tFileInputXML jobs (via batch-convert), run through the OLD engine and capture outputs, then run through the NEW engine and diff. Any diffs are either a fix-validation (audit fixes) or an unintended drift (revert).

**Warning signs:** any test that asserts on the EXACT exception class from XML parsing. Any test that uses `findall` (stdlib idiom) instead of `xpath` (lxml idiom).

## Code Examples

### Example 1: Secure parser factory (`_xml_io.py`)
```python
# Source: existing repo pattern in src/v1/engine/components/transform/extract_xml_fields.py:153-159
# Source: defusedxml README (Context7) -- recommended replacement for defusedxml.lxml
from lxml import etree

def secure_xml_parser(*, recover: bool = False) -> etree.XMLParser:
    """Build a hardened XMLParser.

    Disables external entity expansion (XXE), DTD loading (billion-laughs vector),
    and network access. recover=False fails loud on malformed XML so the caller
    can route to REJECT instead of silently passing through partial trees.
    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=recover,
    )
```

### Example 2: Threshold-switched read
```python
# Source: lxml 6.0 docs (Context7) -- iterparse + element.clear(keep_tail=True)
import os
from typing import Iterator
from lxml import etree

def parse_xml_strategy(filename: str, threshold_mb: int) -> tuple[str, object]:
    size_mb = os.stat(filename).st_size / (1024 * 1024)
    parser = secure_xml_parser()
    if size_mb < threshold_mb:
        return ("dom", etree.parse(filename, parser=parser))
    return ("stream", filename)  # caller calls iterparse_loop_query

def iterparse_loop_query(filename: str, loop_tag: str) -> Iterator[etree._Element]:
    """Yield each `loop_tag` element, then clear it and prior siblings to free memory."""
    # NOTE: iterparse takes its own *_kwargs* in lxml; can't pass an XMLParser directly.
    # The flags we want must be set via iterparse keyword args.
    ctx = etree.iterparse(
        filename,
        events=("end",),
        tag=loop_tag,
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
    )
    for _event, element in ctx:
        yield element
        # 1. clear children of the matched element (free its subtree)
        element.clear(keep_tail=True)
        # 2. drop preceding siblings to release prefix memory
        while element.getprevious() is not None:
            del element.getparent()[0]
    del ctx
```

### Example 3: Incremental XML write (FileOutputXML simple)
```python
# Source: lxml 6.0 docs (Context7) -- https://lxml.de/6.0/api.html
from lxml import etree

def write_chunk_simple(
    xf,                    # active xmlfile context (held on self)
    chunk_df,
    row_tag: str,
    column_to_attr: set,   # MAPPING.AS_ATTRIBUTE columns
    encoding: str = "ISO-8859-15",
):
    for _, row in chunk_df.iterrows():
        # build attributes dict for AS_ATTRIBUTE=true columns
        attrs = {col: str(row[col]) for col in column_to_attr if col in row.index}
        with xf.element(row_tag, **attrs):
            for col in row.index:
                if col in column_to_attr:
                    continue
                with xf.element(col):
                    xf.write(str(row[col]) if row[col] is not None else "")
        xf.flush()  # promptly persist; helps for tail of file scenarios
```

### Example 4: Incremental hierarchical write (AdvancedFileOutputXML)
```python
# Build the nested skeleton once, re-enter LOOP per row.
# Reference: existing pattern of nested xf.element() context managers in lxml docs.
def write_advanced(filepath, df, root_table, group_table, loop_table, encoding="ISO-8859-15"):
    with open(filepath, "wb") as f, etree.xmlfile(f, encoding=encoding) as xf:
        xf.write_declaration()
        # root_table[0] = topmost element name; could include attrs
        with xf.element(root_table[0]["path"]):
            # group_table elements wrap groups; each group can be re-entered per group_by partition
            for group_key, group_df in df.groupby(_groupby_columns(group_table), dropna=False):
                with xf.element(group_table[0]["path"]):
                    # emit static / mapped group-level columns/attrs
                    _emit_static(xf, group_table[1:])
                    # per-row LOOP element
                    for _, row in group_df.iterrows():
                        with xf.element(loop_table[0]["path"]):
                            _emit_row_columns(xf, row, loop_table[1:])
                        xf.flush()
```

(skeleton; exact ATTRIBUTE/PATH semantics implemented in Plan 6 against the converter's TABLE output.)

### Example 5: Per-parameter pos+neg test pattern (D-D1)

```python
# Source: existing pattern in tests/v1/engine/components/transform/test_extract_xml_fields.py
# (24 tests already present; extend to cover all 6 javajet params per per-param pos+neg rule)

class TestParamLimit:
    """Per D-D1: positive + negative test for the LIMIT parameter."""

    def test_limit_unlimited_when_empty_string(self):
        # positive: empty string => no limit, all 5 rows extracted
        ...

    def test_limit_zero_reads_nothing(self):
        # negative: limit='0' yields 0 rows (Talend semantic: 0 != unlimited)
        ...

    def test_limit_exceeds_available(self):
        # negative: limit='100' on 5-row XML still yields 5 rows (no error)
        ...

class TestParamLoopQuery:
    """Per D-D1: positive + negative for LOOP_QUERY."""

    def test_loop_query_matches(self):
        ...

    def test_loop_query_no_match_yields_empty(self):
        ...

    def test_loop_query_invalid_xpath_routes_reject_or_dies(self):
        ...
```

## Runtime State Inventory

> Phase 12 is a feature-add + audit-fix phase. There is no rename/refactor of identifiers used by external runtime systems. This section is documented to be explicit:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — XML components do not write to a database, cache, or vector store. They produce DataFrames or files only. | None |
| Live service config | None — no external service configuration ties to "tFileInputXML" / "tXMLMap" by name. | None |
| OS-registered state | None — no scheduled task or systemd unit named after these components. | None |
| Secrets/env vars | None — XML components do not read env vars. (`xml_streaming_threshold_mb` is a JSON config key, not an env var.) | None |
| Build artifacts | The `xml` extra in `pyproject.toml` already pins `lxml>=4.9,<7`; if the planner decides to add `defusedxml` as an optional dep (NOT recommended per P-1), update the extra. Otherwise no artifact change. | Likely none. Verify in Plan 7 that `pip install -e .[xml]` still resolves cleanly post-changes. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All engine code | ✓ | 3.12.12 | Project requires 3.10+; CI must verify |
| lxml | All 6 in-scope components | ✓ | 6.0.3 (latest 6.1.0; project pins ≥4.9,<7) | None — D-C5 forbids fallback. ConfigurationError if missing. |
| pytest | Tests | ✓ | per project | — |
| pytest-cov | Coverage gate (Plan 7) | ✓ | 7.0.0 | — |
| defusedxml | NONE (per P-1, not recommended) | ✗ | n/a | — (use `etree.XMLParser` flags) |
| Java bridge JAR | NOT TOUCHED in Phase 12 (D-E2) | n/a | n/a | n/a |
| Talend Open Studio | Not required — `.item` fixtures hand-authored per D-D5 | n/a | n/a | Hand-author |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (per pyproject.toml `dev` extra `pytest>=8.0,<10`) [VERIFIED: pyproject.toml:23] |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `pytest tests/v1/engine/components/file/test_file_input_xml.py -x` (per-component, after Plan 3) |
| Full suite command | `pytest tests/v1/engine tests/converters` |
| Coverage command (Plan 7 gate) | `pytest --cov=src.v1.engine.components.file.file_input_xml --cov=src.v1.engine.components.file.file_input_msxml --cov=src.v1.engine.components.file.file_output_xml --cov=src.v1.engine.components.file.file_output_advanced_xml --cov=src.v1.engine.components.transform.extract_xml_fields --cov=src.v1.engine.components.transform.xml_map --cov=src.v1.engine.components.file._xml_io --cov-report=term-missing --cov-fail-under=95 tests/v1/engine/components/file tests/v1/engine/components/transform` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| XML-01 | tFileInputXML matches javajet behavior | unit + integration | `pytest tests/v1/engine/components/file/test_file_input_xml.py` | ❌ Wave 0 / Plan 3 creates |
| XML-01 | tFileInputMSXML matches javajet behavior | unit + integration | `pytest tests/v1/engine/components/file/test_file_input_msxml.py` | ✅ extends in Plan 4 |
| XML-01 | tExtractXMLField matches javajet behavior | unit + integration | `pytest tests/v1/engine/components/transform/test_extract_xml_fields.py` | ✅ extends in Plan 4 |
| XML-01 | tXMLMap matches javajet behavior | unit + integration | `pytest tests/v1/engine/components/transform/test_xml_map.py` | ❌ Wave 0 / Plan 5 creates |
| XML-02 | tFileOutputXML simple emission | unit + integration | `pytest tests/v1/engine/components/file/test_file_output_xml.py` | ❌ Plan 6 creates |
| XML-02 | tFileOutputXML converter | converter unit | `pytest tests/converters/talend_to_v1/components/file/test_file_output_xml.py` | ✅ exists for tAdvancedFileOutputXML — extends in Plan 6 |
| XML-03 | tAdvancedFileOutputXML hierarchical emission | unit + integration | `pytest tests/v1/engine/components/file/test_file_output_advanced_xml.py` | ❌ Plan 6 creates |
| XML-04 | All 6 components on lxml; threshold-switched | unit (helper) + per-component integration | `pytest tests/v1/engine/components/file/test__xml_io.py` AND each component's streaming-path test | ❌ Plan 2 creates `_xml_io.py` tests; per-component plans add streaming path tests |
| XML-04 | E2E `.item` fixture per component | integration (real `convert_job() + run_job()`) | `pytest tests/v1/engine/integration -k "xml" -v` (after Plan 7 organizes; alternatively scattered per component) | partial (Job_*.item exist for 3 of 6; Plan 4/5/6 hand-author the other 3) |
| XML-04 | Per-module 95% line coverage | coverage gate | (see "Coverage command" in Test Framework table) | n/a — gate, not file |

### Sampling Rate (Nyquist criterion)

The "rate" question reads as: *how many distinct fixture patterns gives statistical confidence that production XML jobs will work?* For each in-scope component:

- **Per-parameter pos+neg minimum** (D-D1) gives **2 × N_params** tests as a floor. For tFileInputXML: 18 params → 36 tests minimum (the audit recommends 30-40, our number 30-40 lines up).
- **E2E `.item` fixture coverage** (D-D3): 1 fixture per component minimum. Recommend **3 fixtures per output component** to capture variant shapes (simple-flat, with-attributes, with-namespace for tFileOutputXML; flat-skeleton, hierarchical-with-groups, with-attribute-mapping for tAdvancedFileOutputXML).
- **Streaming path coverage**: 1 fixture per component that EXCEEDS the threshold. Recommend a per-component `conftest.py`-built synthetic ~60 MB XML — generated programmatically at test-collection time so the repo stays small. Programmatic generation pattern (~30 lines) goes in Plan 2's `_xml_io.py` shared helpers.

**Per-component test budgets (target, planner can adjust):**

| Component | Existing tests | New tests target | Rationale |
|-----------|----------------|------------------|-----------|
| tFileInputXML | 0 (engine), 63 (converter) | 30-40 (engine) | 18 javajet params × 2 (pos+neg) = 36 floor |
| tFileInputMSXML | 13 (engine), 44 (converter) | extend to 30 (engine) | 10 javajet params × 2 = 20 floor + state-machine tests for SCHEMAS TABLE |
| tExtractXMLField | 24 (engine), 50 (converter) | extend to 30-35 (engine) | 6 visible params × 2 = 12 floor + already covers ignore_ns / die_on_error / limit |
| tXMLMap | 0 (engine), 24 (converter) | 35-50 (engine) | 3 flat params × 2 + nodeData structures (input_trees, output_trees, connections, looping_element, expressions) need their own pos+neg sets |
| tFileOutputXML | 0 (none — net-new) | 25-35 (engine) + 25 (converter) | 18 javajet params × 2 = 36 floor; converter tests for new class |
| tAdvancedFileOutputXML | 0 (none — net-new) | 35-45 (engine) | 33 unique params × 2 = 66 floor — pruned to 35-45 by combining the rare ones (DTD_VALID/XSL_VALID, OUTPUT_AS_XSD, etc.) which are emitting needs_review and only need a "raises needs_review" test |
| **Total** | ~37 engine + ~181 converter | ~190-235 engine + ~25 new converter | comparable to Phase 11's 213-test discipline |

### Wave 0 Gaps

- [ ] `tests/v1/engine/components/file/test__xml_io.py` — Plan 2; covers shared helpers
- [ ] `tests/v1/engine/components/file/test_file_input_xml.py` — Plan 3
- [ ] `tests/v1/engine/components/file/test_file_output_xml.py` — Plan 6
- [ ] `tests/v1/engine/components/file/test_file_output_advanced_xml.py` — Plan 6
- [ ] `tests/v1/engine/components/transform/test_xml_map.py` — Plan 5
- [ ] `tests/converters/talend_to_v1/components/file/test_file_output_xml.py::TestFileOutputXMLSimple` — Plan 6 extends existing file with a NEW class (file currently only tests AdvancedFileOutputXmlConverter)
- [ ] `tests/talend_xml_samples/Job_tFileInputMSXML_0.1.item` — Plan 4 hand-authors
- [ ] `tests/talend_xml_samples/Job_tFileOutputXML_0.1.item` — Plan 6 hand-authors
- [ ] `tests/talend_xml_samples/Job_tAdvancedFileOutputXML_0.1.item` — Plan 6 hand-authors
- [ ] (synthetic) ~60 MB XML fixture generator in `_xml_io.py` test helper or a dedicated `tests/v1/engine/components/file/conftest.py` — Plan 2

*(No framework install gap — pytest, pytest-cov, lxml all installed.)*

## Security Domain

> The CONTEXT.md doesn't reference `security_enforcement` config; treating as enabled per default.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | XML components don't authenticate |
| V3 Session Management | no | batch ETL — no sessions |
| V4 Access Control | partial | FILENAME parameter accepts arbitrary paths; rely on the engine process's filesystem permissions and on the existing `os.path.exists()` check pattern. Path traversal mitigation in scope only via OS-level perms. |
| V5 Input Validation | yes | Schema validation via `BaseComponent.validate_schema()` (existing); XML well-formedness via `etree.XMLParser` (recover=False routes parse fail to REJECT). MAPPING table type-coercion via existing `convert_type()`. |
| V6 Cryptography | no | no crypto in XML components |
| V8 Data Protection | partial | XML files may contain PII; encoding handled via `encoding=` param. No additional protection at component layer. |
| V14 Configuration | yes | `_xml_io.py:secure_xml_parser()` is the project standard; no parser hand-rolls. |

### Known Threat Patterns for XML / lxml

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XXE (External Entity) injection | Information disclosure | `etree.XMLParser(resolve_entities=False)` — entities not expanded; in libxml2 they're tokenized but never resolved. [VERIFIED: lxml docs / defusedxml README] |
| Billion laughs (entity bomb) | DoS | `load_dtd=False` + `resolve_entities=False`; libxml2 also has a built-in entity-expansion limit (`huge_tree=False` is default). [CITED: defusedxml README via Context7] |
| Quadratic blowup | DoS | libxml2 has built-in mitigation; lxml inherits. No additional code needed. |
| External DTD network fetch | Information disclosure / Tampering | `no_network=True` + `load_dtd=False` |
| XInclude attacks | Tampering / Info disclosure | XInclude is OFF by default in lxml; do NOT call `tree.xinclude()`; emit `needs_review` if a job specifies XInclude. |
| Path traversal via FILENAME | Tampering | OS-level: process must not run as root; engine should canonicalize `os.path.realpath()` and reject paths outside expected directories. Out of scope for Phase 12 per CONTEXT (existing `os.path.exists()` is the only check); document as residual risk. |
| XPath injection | Tampering | XPath comes from JSON config (Talend export, trusted source). Low risk — same as existing system. |
| Compression bombs (zip) | DoS | OUT OF SCOPE — Phase 12 doesn't implement compressed XML reading. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The 2026-04-03/04 audit docs' P0 cross-cutting items (BUG-FIX-001, BUG-XMP-012, BUG-XMP-013) were resolved by Phase 7.1 (`07.1-01-PLAN.md` rewrote BaseComponent and `02-01-PLAN.md` rewrote bridge). [ASSUMED — Plan 1 must verify by `git log -- src/v1/engine/base_component.py` and re-running the audited code paths.] | Component-by-Component Audit Baseline | If wrong, Plan 3 / 5 still works because the fix is one-line; just adds rework time, no architectural impact. |
| A2 | tXMLMap's "expression_filter" Java path is currently un-implemented in the engine [VERIFIED via grep — no JavaBridgeManager imports in xml_map.py]; Phase 12 keeps it that way and emits `needs_review` per D-E1. | Component-by-Component / tXMLMap | If user wants expression_filter execution, Phase 12 scope grows by ~1 plan (bridge call + tests). Surface during plan check. |
| A3 | `defusedxml.lxml` is the wrong dependency to add [VERIFIED via Context7 README excerpt]. CONTEXT.md D-C4's intent ("XXE protection at the input boundary") is satisfied by the `etree.XMLParser` flag pattern already in the repo. | Standard Stack / Pitfall P-1 | If user insists on defusedxml.lxml, the plan adds a tiny adapter; semantics equivalent. Surface during plan check. |
| A4 | 95% per-module coverage target is achievable on lxml-migrated `file_input_xml.py` and on the new `xml_map.py` test suite [ASSUMED — Phase 11 hit 95%+ on Oracle modules of similar complexity]. | Validation Architecture | If 95% is unreachable on a specific module (e.g., `xml_map.py` 738 LOC has too many error-path corners), Plan 7's gate fails; remediation = either drop coverage to component-specific floor (e.g., 90%) for that module OR add more tests. |
| A5 | Talaxie javajet param tables fetched 2026-05-08 are current [VERIFIED via WebFetch on `master` branch of `Talaxie/tdi-studio-se`]. | Component-by-Component Audit Baseline | Talaxie tracks Talend upstream; if a future Talend release adds params, Phase 12 docs miss them. Acceptable for this milestone. |
| A6 | Hand-authored `.item` fixtures will faithfully reflect production Talend export shapes [ASSUMED — existing fixtures (Job_tFileInputXML, etc.) are hand-shaped and have been working in the converter test suite]. | Validation Architecture | If real production .item shapes differ materially, Phase 12.1 gap-closure handles per Deferred Ideas. |

**The risk in this list signals that:**
- A1, A3 are easy to verify upfront (Plan 1 actually does A1; the planner should do a quick `pip show defusedxml` / Context7 confirmation for A3).
- A2 is the highest-risk because it touches contract D-E1; the planner should note in the discuss-phase amendment if A2 needs revisiting.

## Open Questions

1. **Should Phase 12 also wire `defusedxml` as an optional dep, or rely fully on `etree.XMLParser` flags?**
   - What we know: D-C4 prescribes `defusedxml.lxml`. defusedxml.lxml is upstream-deprecated. The repo already uses `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` as the secure pattern.
   - What's unclear: whether D-C4's intent is satisfied by the existing pattern OR whether the user/manager wanted the actual defusedxml package as a dependency.
   - Recommendation: Plan 1 surfaces this in the audit doc; Plan 2 (`_xml_io.py`) implements the etree.XMLParser flag pattern by default. If the planner / discuss-phase amendment requires defusedxml, it's a 5-line wrapper change.

2. **Threshold default — 50 MB the right number?**
   - What we know: D-C2 fixes 50 MB as the default; configurable via `xml_streaming_threshold_mb`.
   - What's unclear: file-size distribution of production XML at Citi.
   - Recommendation: leave 50 MB as default (per CONTEXT); test both `=0` (always streaming) and `=10000` (effectively never) to prove the toggle works.

3. **Hand-authored `.item` fixtures — what's the canonical schema for the new ones?**
   - What we know: existing `Job_*.item` fixtures (e.g., `Job_tFileInputXML_0.1.item`) are 100-300 line hand-authored files mimicking Talend's export.
   - What's unclear: whether test fixtures need full Talend `.item` shape (PROPERTY block, SUBJOB block, etc.) or whether minimal `<node componentName="...">` is enough for the converter.
   - Recommendation: Plan 6 starts from the existing tFileInputXML fixture as a template, prunes nonessentials, and validates with `convert_job(fixture) -> ETLEngine.run_job()` round-trip.

4. **`tFileOutputXML` simple — is the converter changes additive only or does it conflict with the existing `AdvancedFileOutputXmlConverter` registration?**
   - What we know: `src/converters/talend_to_v1/components/file/file_output_xml.py` registers ONLY `tAdvancedFileOutputXML`. There's no `tFileOutputXML` register call anywhere.
   - What's unclear: the planner needs to decide whether to add a second class in the same file (`FileOutputXMLConverter` registered as `tFileOutputXML`) or split into two files.
   - Recommendation: same file, two classes. Project pattern is per-Talend-component class; same file is fine for sibling components. Keep `_parse_xml_table` shared at module scope.

5. **`xml_streaming_threshold_mb` config — converter responsibility or engine-only?**
   - What we know: CONTEXT D-C2 says "config knob".
   - What's unclear: should the converter set a default in JSON output, or is it purely engine config (read from `job_config['settings']` or component-level)?
   - Recommendation: per-component config key (read in `_process()`), defaulting from `BaseComponent` shared default of 50. Aligns with how iterate's `chunk_size` is handled. Converter does not emit it (additive engine-only behavior).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `defusedxml.lxml` wrapping | `lxml.etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` | `defusedxml` deprecated `.lxml` submodule c. 2024 (per upstream README) | Phase 12 substitutes; CONTEXT D-C4 obsolete on this point |
| stdlib `xml.etree.ElementTree` for streaming | `lxml.etree.iterparse(events=('end',), tag=...)` + element.clear(keep_tail=True) | lxml has long been the recommended Python XML lib; stdlib is fine for tiny XML but not for streaming or XPath-heavy work | `file_input_xml.py` migration |
| Build full tree, `etree.tostring(root)` | `etree.xmlfile(path)` context manager + `xf.write(el)` | Always available in lxml; rarely used because the `Element` API is more familiar | New output components must use xmlfile per D-C3 |
| `lstrip("/")` for prefix removal | `removeprefix("/")` (Python 3.9+) | Project D-76 (prior phase) | tXMLMap engine line 281 still has the old idiom — fix in Plan 5 |
| Single-namespace nsmap from root tag | `element.nsmap` per-element + tree-wide nsmap collection | lxml has always exposed nsmap; the existing `normalize_nsmaps()` shortcut is a bug | Plan 3 file_input_xml fix |

**Deprecated/outdated:**
- `defusedxml.lxml` — see above
- `xml.etree.ElementTree.findall(..., namespaces=...)` for production XPath — works for trivial cases, falls over on axes (`descendant::`, `ancestor::`)
- Talend's "Dom4j vs SAX" `GENERATION_MODE` distinction — both subsumed by lxml's threshold-switched DOM/iterparse. The config key is preserved (converter still extracts it) but the engine treats both modes identically per D-C2; emit `needs_review` if a job sets `GENERATION_MODE=SAX` AND the file is below threshold (no-op informational message).

## Sources

### Primary (HIGH confidence)
- Context7: `/websites/lxml_de` — fetched topics: iterparse, element clearing, xmlfile, incremental write, encoding (2026-05-08)
- Context7: `/tiran/defusedxml` — fetched topics: lxml deprecation status, secure-XMLParser recommendation (2026-05-08)
- Talaxie GitHub `master` branch: `tdi-studio-se/main/plugins/.../components/<component>/<component>_java.xml` for all 6 components (WebFetch 2026-05-08)
- `pyproject.toml:19` — `xml = ["lxml>=4.9,<7"]` extra
- `pip show lxml` / `pip index versions lxml` — installed 6.0.3, latest 6.1.0 (2026-05-08)
- `pip show pytest-cov` — 7.0.0 (2026-05-08)
- Repo grep verification for: `JavaBridge` not imported in `xml_map.py`, secure-XMLParser pattern in `extract_xml_fields.py:153-159` and `file_input_msxml.py:107-113`
- Repo audit docs (5):
  - `docs/v1/audit/components/file/tFileInputXML.md` (2026-04-03)
  - `docs/v1/audit/components/file/tFileInputMSXML.md` (2026-04-05)
  - `docs/v1/audit/components/transform/tExtractXMLField.md` (last updated 2026-05-06)
  - `docs/v1/audit/components/transform/tXMLMap.md` (2026-04-04)
  - `docs/v1/audit/components/file/tAdvancedFileOutputXML.md` (2026-04-04)

### Secondary (MEDIUM confidence)
- Phase 11 plan structure (`.planning/phases/11-oracle-components/11-0[1-7]-PLAN.md`) — used as template for plan/wave decomposition
- Phase 7.1 BaseComponent rewrite (`07.1-01-PLAN.md`) — implied resolution of cross-cutting P0s in older audits

### Tertiary (LOW confidence)
- None — every claim made above is either Context7-verified or repo-grepped.

## Metadata

**Confidence breakdown:**
- Standard stack (lxml, threshold-switched, secure parser): HIGH — Context7 verified, current repo pattern, version pinned
- Architecture (audit-first, plan/wave decomposition mirroring Phase 11): HIGH — Phase 11 actuals confirm structure works
- Per-component starting hypothesis: MEDIUM — based on 2026-04-03/04 audits; some P0s likely already resolved by Phase 7.1 (Plan 1 verifies)
- tXMLMap Java-bridge intersection: HIGH for "no current bridge calls" (grep verified); MEDIUM for "no expression_filter execution in Phase 12" (depends on planner respecting D-E1)
- Pitfalls (especially P-1 defusedxml.lxml deprecation): HIGH — direct upstream README excerpt
- Output components' xmlfile streaming: HIGH — Context7 verified pattern; MEDIUM on the exact AdvancedFileOutputXML hierarchical emission shape (no prior implementation; Plan 6 figures out the ROOT/GROUP/LOOP→nested-xf.element mapping)

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (30 days; lxml 6.1.0 → 6.2.0+ unlikely to change semantics meaningfully; Talaxie javajet templates are stable across the master branch).

## RESEARCH COMPLETE
