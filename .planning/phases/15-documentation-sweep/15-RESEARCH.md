# Phase 15: Documentation Sweep -- Research

*Last updated: 2026-05-11*

**Researched:** 2026-05-11
**Domain:** Document-vs-code reconciliation (no algorithm/library research)
**Confidence:** HIGH (all claims verified against current source via grep/file-read)

---

## Summary

Phase 15 is a documentation sweep, not a code phase. Research focused on (1) reconciling the 11 deep-review files against the current `src/v1/engine/` and `src/converters/` codebase as of Phase 14 closure and (2) skeletoning the 4 fresh canonical docs (`docs/ARCHITECTURE.md`, `docs/COMPONENT_REFERENCE.md`, `docs/CONTRIBUTING.md`, `docs/DEPLOYMENT.md`) so the planner can fill content from already-current `.planning/codebase/*.md` and Phase 14 summary artifacts.

Three findings drive the plan:

1. **The engine `COMPONENT_REGISTRY` static dict no longer exists.** It was replaced by a decorator-based `src/v1/engine/component_registry.py` `REGISTRY` (mirror of the converter side). Every doc that mentions `ETLEngine.COMPONENT_REGISTRY` as a class attribute is STALE -- this includes `docs/v1/STANDARDS.md`, `docs/v1/BaseComponent-Info.md`, the (being-deleted) `docs/ARCHITECTURE.md`, and even `.planning/codebase/ARCHITECTURE.md` / `CONVENTIONS.md`. Planner must source from `engine.py:18 (REGISTRY import)` + `component_registry.py`, NOT from the stale codebase maps.
2. **`docs/v1/STANDARDS.md` is the redundant master.** It duplicates content in ENGINE_COMPONENT_PATTERN, CONVERTER_PATTERN, MANUAL_COMPONENT_AUTHORING, and parts of BaseComponent-Info. Section 9 explicitly documents `src/converters/complex_converter/` as the converter -- that subsystem was superseded by `talend_to_v1` and its tests were deleted in Phase 14-11 (STALE-INT-001). STANDARDS.md is a DROP candidate alongside METHODOLOGY.md, AUDIT_REPORT_TEMPLATE.md, and NEXT_MILESTONE_GUIDE.md.
3. **Phase 14 introduced two systemic constraints that must enter CONTRIBUTING.md.** (a) Every `BaseComponent` subclass MUST be decorated with `@REGISTRY.register(...)` AND implement `_validate_config` -- the BUG-PDC/SWIFT/FIJ trio showed engine.py silently drops unregistered classes as "Unknown component type" with a warning at runtime. (b) The 95% per-module line-coverage floor and paste-runnable gate via `scripts/check_per_module_coverage.py` -- already documented in CLAUDE.md; CONTRIBUTING.md references CLAUDE.md, does not duplicate.

**Primary recommendation:** Drop 4 of the 11 standards files (STANDARDS, METHODOLOGY, AUDIT_REPORT_TEMPLATE, NEXT_MILESTONE_GUIDE) outright. KEEP+FIX the remaining 7 with stale-claim patches (Phase 4 references, COMPONENT_REGISTRY references, complex_converter references, BUG-FIX-* artifact markers). Rename `docs/v1/standards/` -> `docs/v1/patterns/` to match surviving content. Move `BaseComponent-Info.md` into `patterns/`. Keep `talend_to_v1_converter_guide.md` at `docs/v1/` as a user-facing guide (it complements CONVERTER_PATTERN.md which is contributor-facing). The 4 canonical docs at `docs/` consume `.planning/codebase/*.md` + Phase 14 summary verbatim, with the COMPONENT_REGISTRY correction applied.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scope decisions**
- **D-A1:** Top-level `docs/` nuke is total. All 22 files (20 .md + 2 .docx) deleted, no salvage or migration. Fresh canonical docs replace them.
- **D-A2:** 4 canonical docs locked at the names from ROADMAP. `ARCHITECTURE.md`, `COMPONENT_REFERENCE.md`, `CONTRIBUTING.md`, `DEPLOYMENT.md`. Researcher/planner decide internal structure; names are fixed.
- **D-A3:** Canonical docs live at `docs/` root (not `docs/v1/` or `docs/canonical/`). The 4 files are the only top-level entries.
- **D-A4:** `docs/v1/audit/` is out of Phase 15 scope. No file under `docs/v1/audit/` may be modified during Phase 15. The reconciliation work is Phase 15.1.
- **D-A5:** `docs/v1/standards/` + 3 sibling files get deep review treatment. 11 files total. Same protocol: cross-check against current code, fix stale content, drop redundant files, possibly rename the standards/ folder if its content no longer matches the name.
- **D-A6:** AUDIT_REPORT_TEMPLATE.md and METHODOLOGY.md are explicit deletion candidates. Research must evaluate whether they still have a consumer post-Phase-14. Same evaluation applies to NEXT_MILESTONE_GUIDE.md (likely stale).

**Anti-scope decisions**
- **D-B1:** No CI / pre-commit doc-freshness lint. Stale-doc detection becomes a manual review concern.
- **D-B2:** No documentation generation tooling. Plain Markdown only.
- **D-B3:** No mass migration of audit/ content into COMPONENT_REFERENCE.md. Phase 15's COMPONENT_REFERENCE.md is a high-level index that points at `docs/v1/audit/` for per-component depth.
- **D-B4:** CLAUDE.md is not edited by Phase 15. CONTRIBUTING.md may reference CLAUDE.md but does not duplicate its content.

**Content decisions**
- **D-C1:** All new docs ASCII-only. No emoji, no smart quotes, no en/em dashes (use `--`).
- **D-C2:** Every new or rewritten doc starts with `*Last updated: YYYY-MM-DD*` line.
- **D-C3:** CONTRIBUTING.md must encode the load-bearing project rules (ASCII-only logs, exception hierarchy, fix-source-no-fallbacks, atomic commits, pragma allowlist, 95% per-module floor, pipeline fixtures, BaseComponent abstract-method discipline, registry membership).
- **D-C4:** ARCHITECTURE.md must include a registry-discipline section.
- **D-C5:** DEPLOYMENT.md captures Linux + JVM 11+ as the validated runtime.
- **D-C6:** COMPONENT_REFERENCE.md is a registry-driven index.

**Folder structure decisions**
- **D-D1:** `docs/v1/standards/` folder may be renamed. Acceptable alternative names: `docs/v1/patterns/`, `docs/v1/conventions/`. Decision deferred to planner.
- **D-D2:** The 3 sibling `docs/v1/` files may be moved into the standards/ folder.
- **D-D3:** Repo root `README.md` added by Phase 15. Minimal: project title, one-paragraph description, link to `docs/ARCHITECTURE.md`, link to `CLAUDE.md` for Claude-specific instructions.

**Atomicity / process**
- **D-E1:** Atomic commits. One logical change per commit.
- **D-E2:** Per-file verification. Every doc rewritten or fixed gets a manual content check (claims grounded via grep/file-read).
- **D-E3:** No new defensive shims in code from doc work. Phase 15 is doc-only.

### Claude's Discretion

- Whether to rename `docs/v1/standards/` (D-D1) -- decided by planner from research recommendation (this doc recommends `patterns/`).
- Whether to move 3 sibling files into the renamed folder (D-D2) -- decided by planner per content overlap (this doc recommends BaseComponent-Info.md moves, talend_to_v1_converter_guide.md stays).
- Internal section structure of each canonical doc (D-A2 names are fixed; content shape is open). Section B of this research proposes skeletons.
- COMPONENT_REFERENCE.md generation strategy: inline table vs `scripts/gen_component_reference.py` (D-C6).
- Per-doc paragraph-level wording (no locked phrasing).

### Deferred Ideas (OUT OF SCOPE)

- **Documentation generation tooling** (Sphinx, MkDocs, Docusaurus). Defer indefinitely.
- **CI / pre-commit stale-doc lint.** Defer indefinitely (D-B1).
- **Auto-generated COMPONENT_REFERENCE.md.** A small `scripts/gen_component_reference.py` is implementable but not required.
- **Phase 14 systemic registry/abstract-method audit.** A repo-wide sweep confirming every component class is registered and implements every abstract. Captured in CONTRIBUTING.md as a rule but not actively audited in Phase 15.
- **API reference auto-generation** (docstring extraction).
- **Multi-language docs.**

---

## Phase Requirements

Phase 15 requirement IDs (planner adds to REQUIREMENTS.md):

| ID | Description | Research Support |
|----|-------------|------------------|
| DOCS-01 | Canonical doc set in place at `docs/` root (ARCHITECTURE.md, COMPONENT_REFERENCE.md, CONTRIBUTING.md, DEPLOYMENT.md); all 22 stale top-level docs/ files deleted; minimal root README.md added | Section B (skeletons) + Section C pitfall on source-of-truth files |
| DOCS-02 | Deep review of 11 standards-zone files complete: drop redundant, fix stale, rename folder if content no longer fits | Section A (per-file analysis + overlap matrix + KEEP/FIX/DROP recommendations) |

DOCS-03 (Phase 15.1 audit reconciliation) is OUT of Phase 15 scope per D-A4 and is not addressed in this research.

---

## Project Constraints (from CLAUDE.md)

Extracted directives that CONTRIBUTING.md must reference (NOT copy):

| # | Directive | Source in CLAUDE.md |
|---|-----------|---------------------|
| C1 | Custom exception hierarchy (`ETLError` -> `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`) | "Error Handling" sections |
| C2 | Never raise generic `Exception`, `RuntimeError`, `ValueError` from component code | "Error Handling" + Phase 14 BUG-SWIFT-001..005 lessons |
| C3 | ASCII-only logs (no emoji, no unicode) | "Logging" + memory `feedback_ascii_logging` |
| C4 | Module-level loggers via `logging.getLogger(__name__)`; no `print()` | "Logging" patterns |
| C5 | Talend XML to JSON converter format is FROZEN (no breaking changes) | "Constraints" |
| C6 | Engine component pattern: ABC + REGISTRY (decorator) + per-component organization | "Constraints" -- aligned with converter pattern |
| C7 | Python 3.10+ runtime, Java 11+ for bridge | "Platform Requirements" |
| C8 | Coverage command + 95% per-module floor + paste-runnable gate; no `--cov-branch` | "Coverage" section (Phase 14 lock) |
| C9 | `snake_case.py` files; `PascalCase` classes; `_` prefix for private | "Naming Patterns" |
| C10 | `pyproject.toml` + `[tool.coverage.*]` blocks are source of truth for coverage config (no .coveragerc) | "Coverage" (Phase 14 D-E4) |

The planner must verify CONTRIBUTING.md sections cite these CLAUDE.md anchors rather than restate them.

---

## Section A -- Per-File Analysis of the 11 Deep-Review Files

### Overlap Matrix

Cells use shorthand: **H**=heavy overlap, **M**=moderate, **L**=light, **-**=none.

| | ENGINE_COMP | ENGINE_TEST | CONV_PAT | TEST_PAT | AUDIT_TPL | MANUAL_AUTH | METHOD | NEXT_MS | STANDARDS | BC_INFO | TT_V1_GUIDE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ENGINE_COMPONENT_PATTERN | - | M | - | - | - | **H** | L | L | **H** | M | - |
| ENGINE_TEST_PATTERN | M | - | - | M | - | M | L | L | M | - | - |
| CONVERTER_PATTERN | - | - | - | M | - | - | L | L | M | - | M |
| TEST_PATTERN | - | M | M | - | - | - | L | L | M | - | - |
| AUDIT_REPORT_TEMPLATE | - | - | - | - | - | - | **H** | L | - | - | - |
| MANUAL_COMPONENT_AUTHORING | **H** | M | - | - | - | - | - | - | **H** | L | - |
| METHODOLOGY | L | L | L | L | **H** | - | - | M | - | - | - |
| NEXT_MILESTONE_GUIDE | L | L | L | L | L | - | M | - | - | - | - |
| STANDARDS.md | **H** | M | M | M | - | **H** | - | - | - | L | - |
| BaseComponent-Info.md | M | - | - | - | - | L | - | - | L | - | - |
| talend_to_v1_converter_guide.md | - | - | M | - | - | - | - | - | - | - | - |

The triangle of heavy overlap is `STANDARDS <-> ENGINE_COMPONENT_PATTERN <-> MANUAL_COMPONENT_AUTHORING`, and a smaller `AUDIT_REPORT_TEMPLATE <-> METHODOLOGY` couple.

---

### A.1 -- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` (686 lines)

**File-level summary:** Gold-standard authoring guide for `BaseComponent` subclasses. 12 rules, file structure template, anti-patterns, Iterate component pattern, full BaseComponent API reference.

**Stale claims:**
- Line 3: `> Reference: [best example component -- TBD until Phase 4]` -- TBD placeholder from Phase 1; Phase 4 / 5 / 6 / 7 / 10 / 11 / 12 all closed since. Should point to a real reference like `file_input_delimited.py` or `aggregate_row.py`.
- Lines 26-28: Imports use `from ...component_registry import REGISTRY` and `@REGISTRY.register("{ComponentName}", "t{ComponentName}")` -- these are CURRENT and correct (Phase 14 lessons applied). Confirmed against `src/v1/engine/component_registry.py:29`.
- Lines 297-321: Rule 11 "Schema Validation" addendum (Phase 7.1) -- CURRENT and correct.
- The doc references `_original_config`, `treat_empty_as_null`, `die_on_error` -- all current (verified in `src/v1/engine/base_component.py:1-50`).

**Wrong claims:**
- None substantive. The 12 rules match the implementation in `base_component.py`.

**Redundancy:** Heavy overlap with `STANDARDS.md` Section 6 (Component Structure) and `MANUAL_COMPONENT_AUTHORING.md` 12-rule list (which explicitly imports from this doc). MANUAL_AUTHORING duplicates the 12 rules at full length; one of the two must be the authority.

**Recommendation:** **KEEP+FIX.** Patch the TBD placeholder (line 3). This is the most reliable load-bearing pattern doc in the repo.

**Folder rename signal:** Content is patterns/templates, not "standards." Move to `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md`.

---

### A.2 -- `docs/v1/standards/ENGINE_TEST_PATTERN.md` (640 lines)

**File-level summary:** Gold-standard test-file structure for engine component tests. 11 rules, per-concern test classes (TestValidation / TestDefaults / ... / TestIterateReexecution), anti-patterns.

**Stale claims:**
- Line 3: `> Reference: test_global_map.py (best example -- one-class-per-concern, fresh fixtures, comprehensive coverage)` -- CURRENT (`tests/v1/engine/test_global_map.py` exists; verified by Phase 14-10 references).
- Rule 5 example imports look correct against current source.
- Does NOT document the Phase 14 `run_job_fixture` / `assert_ascii_logs` pipeline pattern. The Phase 14 `tests/conftest.py` infrastructure is missing from this doc. New contributors reading ENGINE_TEST_PATTERN.md would write only unit tests; Phase 14's lesson "pipeline tests are essential for lifecycle modules" (PHASE-SUMMARY Lessons section) would be missed.
- Does NOT mention the 95% per-module coverage floor.

**Wrong claims:**
- None outright wrong, but incomplete relative to Phase 14 closure.

**Redundancy:** Moderate overlap with TEST_PATTERN.md (converter-side analog).

**Recommendation:** **KEEP+FIX.** Patch in: (1) reference to `tests/conftest.py` `run_job_fixture` for lifecycle-sensitive modules (executor, base_component, iterate, file I/O); (2) reference to `tests/fixtures/jobs/{subsystem}/{behavior}.json` pattern; (3) 95% per-module floor requirement; (4) ASCII-only log enforcement via `assert_ascii_logs`.

**Folder rename signal:** Belongs in `docs/v1/patterns/`.

---

### A.3 -- `docs/v1/standards/CONVERTER_PATTERN.md` (160 lines)

**File-level summary:** Gold-standard converter file structure. TABLE parsing, framework params, `@REGISTRY.register` decorator usage, `_get_str/_get_bool/_get_int` helpers, 12 rules.

**Stale claims:** None apparent on read-through. Refers to `tSchemaComplianceCheck` as reference (line 3); the converter file exists in `src/converters/talend_to_v1/components/`. Patterns match the post-Phase-11 converter codebase.

**Wrong claims:** None.

**Redundancy:** Moderate overlap with `STANDARDS.md` Section 9 (Converter Standards) and with `talend_to_v1_converter_guide.md` introduction.

**Recommendation:** **KEEP+FIX (light).** Add `*Last updated: YYYY-MM-DD*` header per D-C2. Verify reference example still has all 12 rules represented. Move to `docs/v1/patterns/`.

**Folder rename signal:** Belongs in `docs/v1/patterns/`.

---

### A.4 -- `docs/v1/standards/TEST_PATTERN.md` (225 lines)

**File-level summary:** Gold-standard test-case pattern for the CONVERTER side. Mirrors the converter pattern: TalendNode/TalendConnection fixtures, _make_table_data helper, TestRegistration / TestDefaults / TestParameterExtraction / TestTableParsing / TestFrameworkParams / TestSchema classes.

**Stale claims:**
- Reference `test_schema_compliance_check.py` (line 3) -- still exists in `tests/converters/talend_to_v1/components/`.
- Does not mention the converter `complex_converter` legacy removal lesson from Phase 14-11 STALE-INT-001.

**Wrong claims:** None.

**Redundancy:** Moderate overlap with `STANDARDS.md` Section 9 converter testing notes; mostly disjoint from the engine-side `ENGINE_TEST_PATTERN.md`.

**Recommendation:** **KEEP+FIX (light).** Add updated-date header. Move to `docs/v1/patterns/`.

**Folder rename signal:** Belongs in `docs/v1/patterns/`.

---

### A.5 -- `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` (496 lines)

**File-level summary:** Template for per-component audit reports under `docs/v1/audit/components/`. Defines section structure, issue convention (FIXED/OPEN/SUPERSEDED/DEFERRED), priority definitions (P0..P3), scoring (R/Y/G), two-pass review process, edge-case checklist.

**Stale claims:**
- Line 1-6: claims `tFileInputDelimited.md` and `tMap.md` are best existing examples. These files exist under `docs/v1/audit/components/` (out of Phase 15 scope per D-A4), but Phase 15.1 will reconcile them. The reference is no longer load-bearing in Phase 15.
- Lines 86-91: edge-case checklist references `_update_global_map()` crash (ENG-01 Phase 1, FIXED), `validate_schema` inverted nullable logic (ENG-19 Phase 1, FIXED), `_validate_config()` dead code (ENG-08 Phase 1, FIXED). The checklist is historical, not current; many checks describe pre-Phase-1 bug patterns that no longer exist.

**Wrong claims:**
- Implicit: lines 86-91 frame ENG-01/19/08 as live audit concerns. They are not.

**Redundancy:** Heavy overlap with METHODOLOGY.md (which it references at line 5 and lines 60-74).

**Recommendation:** **DROP.** Per D-A6 explicit candidate. Consumer is the audit/ directory (Phase 15.1 territory). When Phase 15.1 reconciles audit files, it will either re-author this template or fold it into the audit reconciliation methodology. Phase 15 has no need to keep it under `docs/v1/standards/`.

**Folder rename signal:** N/A (deleted).

---

### A.6 -- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` (457 lines)

**File-level summary:** Manual authoring guide for contributors writing components OUTSIDE the GSD workflow. Restates the 12 rules from ENGINE_COMPONENT_PATTERN.md with Phase 7.1 lessons. Header "Last updated: 2026-04-25 (Phase 7.1 lessons)".

**Stale claims:**
- Header "Last updated: 2026-04-25" -- pre-dates Phase 14's BUG-PDC/SWIFT/FIJ unregistered-class systemic finding. Should mention registry-membership discipline as a hard rule with examples from Phase 14.
- Line 23-25: "Read CLAUDE.md (project root) -- naming conventions, error handling, logging rules, import style" -- CLAUDE.md anchors are CURRENT post-Phase-14 updates.
- Lines 96-110: Rule 11 (don't call `self.validate_schema` in `_process()`) is CURRENT.

**Wrong claims:** None.

**Redundancy:** Heavy overlap with `ENGINE_COMPONENT_PATTERN.md` -- explicitly imports the 12 rules. Currently both files are authoritative on the same content; one should be the source and the other should reference.

**Recommendation:** **KEEP+FIX.** Patch the updated-date. Add a new "Rule 13: Registry Membership AND Abstract Methods" section citing the Phase 14 BUG-PDC-001/002, BUG-SWIFT-001/002, BUG-FIJ-001/002 pattern. Rewrite as the "human contributor entry point" that summarizes + references ENGINE_COMPONENT_PATTERN.md and ENGINE_TEST_PATTERN.md rather than re-stating their rules at full length. Move to `docs/v1/patterns/`.

**Folder rename signal:** Belongs in `docs/v1/patterns/`.

---

### A.7 -- `docs/v1/standards/METHODOLOGY.md` (207 lines)

**File-level summary:** Audit methodology -- scoring framework, audit dimensions (Talend baseline, converter coverage, engine parity, code quality, performance, testing). Used to author the audit/ reports.

**Stale claims:**
- Line 16: "All ~50 implemented v1 engine components" -- inaccurate post-Phase-14 (engine has more registered components now; the registry decorator-based listing shows the canonical count).
- Line 17: "Database components (Oracle, MSSQL) are excluded" -- Oracle components are now IN scope (Phase 11 shipped them). MSSQL deferred per V2 requirements (REQUIREMENTS.md COMP-V2-02).
- Line 19: "V1 only -- reports must contain zero references to v2, V2, PyETL, v1-to-v2 converters" -- v2 framing is historical context; current repo has no v2.

**Wrong claims:**
- Line 17 Oracle exclusion claim is wrong.

**Redundancy:** Heavy with AUDIT_REPORT_TEMPLATE.md (same audit framing, shared edge-case checklist).

**Recommendation:** **DROP.** Per D-A6 explicit candidate. The audit/ subsystem is Phase 15.1's responsibility; if 15.1 needs methodology, it can either rewrite or fold methodology into a 15.1 doc. Phase 15 has no Phase-15-scope consumer.

**Folder rename signal:** N/A (deleted).

---

### A.8 -- `docs/v1/standards/NEXT_MILESTONE_GUIDE.md` (159 lines)

**File-level summary:** A playbook for the "v1.1 Standardization milestone" -- a forward-looking guide that walked through a 7-phase plan to standardize "54 components" against AUDIT_REPORT_TEMPLATE / CONVERTER_PATTERN / TEST_PATTERN.

**Stale claims:**
- Entire premise: "v1.1 Standardization milestone" never happened as described. The actual milestone became Phases 1-14 of the v1.0 engine restructure plus Phase 15 (this) and 15.1 (audit reconciliation).
- Line 38: "Standardize all 54 v1 engine components" -- registry shows a different count now.
- Line 47: "Mode: YOLO" -- not the actual workflow used; GSD-driven phases were used instead.
- Line 81-90: 8-phase table -- does not match the 16-phase ROADMAP.md.

**Wrong claims:**
- The entire document describes a milestone that never executed in the form described. It is a historical artifact.

**Redundancy:** Low. The content is unique but obsolete.

**Recommendation:** **DROP.** Per D-A6 likely-stale candidate. Confirmed: no Phase 15 / 15.1 / 16 work consumes this document. The ROADMAP.md serves the planning function it was meant to serve.

**Folder rename signal:** N/A (deleted).

---

### A.9 -- `docs/v1/STANDARDS.md` (1325 lines)

**File-level summary:** The "master standards" doc. 9 sections covering overview, file/module organization, naming conventions, logging, error handling, component structure, documentation standards, new-component checklist, and converter standards.

**Stale claims:**
- Line 801: "Standards for the Talend XML to JSON converter (`src/converters/complex_converter/`)" -- WRONG. Section 9 documents the LEGACY `complex_converter`, which Phase 14-11 STALE-INT-001 verified is no longer imported and whose tests were deleted. The CURRENT converter is `src/converters/talend_to_v1/`.
- Line 806: `src/converters/complex_converter/` -- LEGACY path; the directory still exists but is dead code (REQUIREMENTS.md TEST-11 explicitly excludes it from the 95% floor).
- Section 1 directory tree (lines 36-91): shows accurate `src/v1/engine/` layout BUT misses Oracle components (Phase 11), iterate components (`src/v1/engine/components/iterate/flow_to_iterate.py`), and SWIFT components (`src/python_routines/swift_transformer.py`, plus engine `transform/swift_*`).
- Implicit throughout: the doc still frames engine `COMPONENT_REGISTRY` as a static dict in engine.py. Wrong post-component-registry-decorator refactor; the registry now lives in `src/v1/engine/component_registry.py` and is populated via decorator.
- Naming Conventions table (line ~104): correct for current code.

**Wrong claims:**
- Multiple. Section 9 entire converter standards document the wrong subsystem (`complex_converter`). Engine layout in Section 1 is partial.

**Redundancy:** Heavy overlap with ENGINE_COMPONENT_PATTERN.md (Section 6), CONVERTER_PATTERN.md (Section 9), MANUAL_COMPONENT_AUTHORING.md (Sections 5/6/8), CLAUDE.md (logging, error handling, naming conventions). Three docs already cover what STANDARDS.md tries to cover.

**Recommendation:** **DROP.** Section 9 is actively WRONG and would mislead a new contributor. Sections 1-8 duplicate ENGINE_COMPONENT_PATTERN.md + MANUAL_COMPONENT_AUTHORING.md + CLAUDE.md without adding value. The 1325 lines are pure liability. Replace with: (a) the new `docs/ARCHITECTURE.md` (system overview), (b) `docs/CONTRIBUTING.md` (load-bearing rules), and (c) the surviving pattern docs in `docs/v1/patterns/`.

**Folder rename signal:** N/A (deleted).

---

### A.10 -- `docs/v1/BaseComponent-Info.md` (86 lines)

**File-level summary:** Tabular summary of what BaseComponent handles (template method lifecycle, config immutability, execution modes, Java resolution, schema validation, column ordering, stats) PLUS a "Gaps" table (G-01..G-12) listing missing features.

**Stale claims:**
- Lines 73-87 (gaps table): G-01..G-05, G-10, G-12 are Phase 7.1 "G-*" line items that were FIXED in Phase 7.1 plans 07.1-01..07.1-08. STATE.md and `base_component.py:1-50` docstring confirm: CR-01, CR-02, WR-01/02/03, G-01..G-05, G-10, G-12 all marked FIXED. The gaps table is historical wishlist, not a current snapshot.
- G-06, G-07, G-08, G-09, G-11 may still be open (not addressed in any Phase 1-14 closure that I can verify from STATE.md), but the doc gives no indication of which are fixed vs. open.

**Wrong claims:**
- G-01..G-05, G-10, G-12 framed as live gaps -- wrong post-Phase-7.1.

**Redundancy:** Light. The lifecycle table (Section 1) is a useful at-a-glance reference. The gaps table is the problem section.

**Recommendation:** **KEEP+FIX.** Delete or strike-through the FIXED gaps (G-01..G-05, G-10, G-12); leave the lifecycle table; mark remaining open gaps explicitly. Move into `docs/v1/patterns/BaseComponent-Info.md` (per D-D2) since it complements ENGINE_COMPONENT_PATTERN.md as a reference card.

**Folder rename signal:** Move to `docs/v1/patterns/` alongside ENGINE_COMPONENT_PATTERN.md.

---

### A.11 -- `docs/v1/talend_to_v1_converter_guide.md` (528 lines)

**File-level summary:** USER-facing guide for the talend_to_v1 converter -- quick start (Python API, CLI), output format example, validation behavior, how to convert a .item file.

**Stale claims:** Reviewed lines 1-120: output-format JSON example looks correct against current converter behavior. References `src/converters/talend_to_v1/`; no `complex_converter` references. The JSON example shows `"type": "FileInputDelimited"` and `"original_type": "tFileInputDelimited"` -- matches current converter output (verified by `src/v1/engine/engine.py:140` `comp_type = comp_config['type']` lookup behavior).

**Wrong claims:** None found in the sampled portion.

**Redundancy:** Moderate -- some overlap with CONVERTER_PATTERN.md, but this is USER-FACING (how to invoke the converter), not CONTRIBUTOR-FACING (how to author one). Distinct audience.

**Recommendation:** **KEEP+FIX (light).** Add updated-date header. Verify remaining sections (120-528) against current code in Phase 15 plan task. KEEP at `docs/v1/talend_to_v1_converter_guide.md` (not moved into patterns/ -- it serves a different audience than the pattern docs).

**Folder rename signal:** Stays at `docs/v1/` root.

---

### Summary Table -- A.1 to A.11

| # | File | Lines | Recommendation | New Location |
|---|------|-----:|----------------|--------------|
| 1 | ENGINE_COMPONENT_PATTERN.md | 686 | KEEP+FIX | `docs/v1/patterns/` |
| 2 | ENGINE_TEST_PATTERN.md | 640 | KEEP+FIX (add Phase 14 pipeline pattern) | `docs/v1/patterns/` |
| 3 | CONVERTER_PATTERN.md | 160 | KEEP+FIX (light) | `docs/v1/patterns/` |
| 4 | TEST_PATTERN.md | 225 | KEEP+FIX (light) | `docs/v1/patterns/` |
| 5 | AUDIT_REPORT_TEMPLATE.md | 496 | **DROP** | -- |
| 6 | MANUAL_COMPONENT_AUTHORING.md | 457 | KEEP+FIX (add Rule 13 registry+abstract) | `docs/v1/patterns/` |
| 7 | METHODOLOGY.md | 207 | **DROP** | -- |
| 8 | NEXT_MILESTONE_GUIDE.md | 159 | **DROP** | -- |
| 9 | STANDARDS.md | 1325 | **DROP** | -- |
| 10 | BaseComponent-Info.md | 86 | KEEP+FIX (strike fixed gaps) | `docs/v1/patterns/` |
| 11 | talend_to_v1_converter_guide.md | 528 | KEEP+FIX (light) | `docs/v1/` (stays) |

**Net delta:** 11 reviewed -> 4 dropped + 7 kept-with-fixes. Surviving footprint: ~2,800 lines (down from ~4,969).

**Folder rename:** `docs/v1/standards/` -> `docs/v1/patterns/` per D-D1.

---

## Section B -- Canonical Doc Skeletons

Per D-A2, the 4 doc names are LOCKED. Internal structure below is recommended; planner has discretion (D-A2). All 4 docs MUST be ASCII-only (D-C1) and start with `*Last updated: YYYY-MM-DD*` (D-C2).

---

### B.1 -- `docs/ARCHITECTURE.md` (target ~300-500 lines)

**Purpose:** Explain how DataPrep works at a system level. Entry point for new contributors / managers.

**Source-of-truth files (planner reads, doc consumes):**
- `.planning/codebase/ARCHITECTURE.md` (system overview, layers, data flow, key abstractions)
- `.planning/codebase/STRUCTURE.md` (directory layout)
- `.planning/codebase/STACK.md` (technology stack -- Python 3.10+, JVM 11+, Py4J, Arrow)
- `.planning/PROJECT.md` (Core Value)
- `src/v1/engine/engine.py` lines 18 + 140 (REGISTRY usage -- CORRECTION over codebase maps)
- `src/v1/engine/component_registry.py` (decorator-based engine REGISTRY)
- `src/v1/engine/base_component.py` lines 1-50 (template method lifecycle docstring)
- Phase 14 `14-PHASE-SUMMARY.md` "Lessons Learned" sections

**Critical Phase 14 lessons to encode:**
- The engine `COMPONENT_REGISTRY` static-dict pattern is GONE. Engine uses decorator-based `REGISTRY` in `src/v1/engine/component_registry.py`, same shape as the converter side. Both register via `@REGISTRY.register("PascalCase", "tCamelCase")`.
- The "registry membership AND abstract method" systemic constraint (BUG-PDC/SWIFT/FIJ): any `BaseComponent` subclass missing either invariant fails silently at runtime ("Unknown component type") or refuses ABC instantiation. ARCHITECTURE.md MUST devote a subsection to this constraint per D-C4.

**Recommended outline:**

```
# DataPrep Architecture
*Last updated: 2026-MM-DD*

## Overview
- 2-3 paragraphs: what DataPrep is, core value, two-subsystem split (converter + engine)
- Pull from .planning/PROJECT.md "What This Is" + "Core Value"

## System Diagram (ASCII)
- Conceptual data flow: Talend .item -> converter -> JSON config -> engine -> ETL results
- Show the converter pipeline (XmlParser -> ComponentConverters -> validator) and the engine pipeline (ETLEngine -> ExecutionPlan -> Executor -> components)
- Pull from .planning/codebase/ARCHITECTURE.md "Data Flow" sections

## Layers
- XML Parsing Layer
- Component Converter Layer
- Converter Orchestrator
- Engine Core (ETLEngine + ExecutionPlan + Executor + OutputRouter)
- Engine Component Layer
- Infrastructure Layer (GlobalMap, ContextManager, TriggerManager, JavaBridgeManager, PythonRoutineManager, OracleConnectionManager)
- Java Bridge Layer (Py4J + Arrow)
- Pull from .planning/codebase/ARCHITECTURE.md "Layers" but CORRECT engine.py mention (removed COMPONENT_REGISTRY static dict; now component_registry.py decorator)

## Key Abstractions
- BaseComponent (template method lifecycle in execute() -- 8 steps from base_component.py docstring)
- BaseIterateComponent (iterator pattern)
- ComponentConverter (strategy pattern, converter side)
- REGISTRY (decorator-based, both sides)
- Pull from .planning/codebase/ARCHITECTURE.md "Key Abstractions" + base_component.py:1-50

## Registry Discipline (D-C4) -- LOAD-BEARING
- The systemic constraint surfaced in Phase 14: every BaseComponent subclass MUST
  - be decorated with @REGISTRY.register("ClassName", "tTalendName")
  - implement _validate_config()
- If either is missing: engine silently drops the class as "Unknown component type" OR ABC raises on instantiation
- Reference Phase 14 BUG-PDC-001/002, BUG-SWIFT-001/002/003, BUG-FIJ-001/002 as evidence
- Mention scripts/check_per_module_coverage.py is the test-side guard
- This section is the most novel content vs prior docs/ARCHITECTURE.md

## Data Flow
- Conversion pipeline (12 steps from .planning/codebase/ARCHITECTURE.md)
- Engine execution pipeline (10 steps; verify against engine.py + executor.py)

## State Management
- GlobalMap, ContextManager, data_flows dict
- Java bridge sync semantics

## Error Handling Strategy
- ETLError hierarchy
- die_on_error contract
- REJECT flow routing
- Component-level exception containment + Die component exit code

## Cross-Cutting Concerns
- Logging (ASCII-only, structured)
- Validation (4-layer converter post-conversion + engine schema validation)
- Expression resolution (3-phase: {{java}} -> ${context.var} -> bare context.var)
- Security: batch ETL, no auth layer; DB credentials via context vars

## Entry Points
- Converter CLI: python -m src.converters.talend_to_v1.converter
- Engine CLI: python src/v1/engine/engine.py
- Programmatic: convert_job(), run_job()

## References
- docs/COMPONENT_REFERENCE.md for the component inventory
- docs/CONTRIBUTING.md for authoring conventions
- docs/DEPLOYMENT.md for runtime requirements
- docs/v1/patterns/ for detailed component / test / converter patterns
```

**Length target:** 300-500 lines. The diagram + Layers + Registry Discipline sections push toward 400+; everything else is tight.

---

### B.2 -- `docs/COMPONENT_REFERENCE.md` (target ~200-300 lines)

**Purpose:** Registry-driven index. For each known component name, point a reader at source, tests, audit doc, and (where applicable) Talend source component.

**Source-of-truth files:**
- `src/v1/engine/component_registry.py` (the live REGISTRY -- canonical names)
- All `src/v1/engine/components/*/[name].py` and `tests/v1/engine/components/*/test_[name].py` paths
- `docs/v1/audit/components/*.md` (per-component audit -- Phase 15.1 reconciles, Phase 15 just points)
- `docs/v1/audit/SUMMARY_SCORECARD.md` (per-component scorecard)
- REQUIREMENTS.md (which Talend components are in v1 scope vs V2 -- COMP-V2-* deferred)

**Critical Phase 14 lessons to encode:**
- The 4 components registered late in Phase 14 (`PythonDataFrameComponent`, `FileInputJSON`, `SwiftTransformer`, `SwiftBlockFormatter`) MUST appear in the registry list as registered now -- they were the BUG-PDC/SWIFT/FIJ-001 fixes.
- Each component row should call out registration status explicitly per D-C6 ("registered" column).

**Recommended outline:**

```
# Component Reference
*Last updated: 2026-MM-DD*

## Overview
- 1 paragraph: this doc is a registry-driven index. For deeper per-component audit content, see docs/v1/audit/components/.
- Note D-B3: this index intentionally does NOT duplicate per-component audit depth; Phase 15.1 reconciles audit/ separately.

## How To Read This Doc
- Component name (V1 PascalCase + tTalend alias)
- Source path
- Test path
- Audit doc path (under docs/v1/audit/components/)
- Status (Registered + has _validate_config = Production-ready per Phase 14 contract)

## Component Inventory (registry-driven)

### Aggregate
| V1 Name | Talend Alias | Source | Tests | Audit |
|---------|-------------|--------|-------|-------|
| AggregateRow | tAggregateRow | src/v1/engine/components/aggregate/aggregate_row.py | tests/.../test_aggregate_row.py | docs/v1/audit/components/tAggregateRow.md |
| UniqueRow | tUniqRow | ... | ... | ... |

### Context
| ... |

### Control
| ... |

### Database
| OracleConnection | tOracleConnection / tDBConnection | ... |
| OracleRow | tOracleRow | ... |
| OracleOutput | tOracleOutput | ... |

### File (input + output)
| FileInputDelimited | tFileInputDelimited | ... |
| FileInputJSON | tFileInputJSON | ... | NOTE Phase 14 BUG-FIJ-001/002 registration fix |
| FileInputXML | tFileInputXML | ... |
| FileInputMSXML | tFileInputMSXML | ... |
| FileInputExcel | tFileInputExcel | ... |
| FileInputPositional | tFileInputPositional | ... |
| FileInputRaw | tFileInputRaw | ... |
| FileOutputDelimited | tFileOutputDelimited | ... |
| FileOutputExcel | tFileOutputExcel | ... |
| FileOutputXML | tFileOutputXML | ... | NOTE Phase 12 new component |
| FileOutputPositional | tFileOutputPositional | ... |
| AdvancedFileOutputXML | tAdvancedFileOutputXML | ... | NOTE Phase 12 new component |
... (full file/ family)

### Iterate
| FlowToIterate | tFlowToIterate | src/v1/engine/components/iterate/flow_to_iterate.py | ... |
| FileList | tFileList | src/v1/engine/components/file/file_list.py | ... |
| FileExist | tFileExist | ... | ... |

### Transform
| Map | tMap | ... |
| FilterRows | tFilterRow / tFilterRows | ... |
| FilterColumns | tFilterColumns | ... |
| SortRow | tSortRow | ... |
| Join | tJoin | ... |
| Unite | tUnite | ... |
| Normalize | tNormalize | ... | NOTE Phase 7.1 vectorized rewrite |
| JavaComponent | tJava | ... |
| JavaRowComponent | tJavaRow | ... |
| PythonComponent | tPythonComponent | ... |
| PythonRowComponent | tPythonRowComponent | ... |
| PythonDataFrameComponent | tPythonDataFrame | ... | NOTE Phase 14 BUG-PDC-001/002 registration fix |
| SwiftTransformer | tSwiftTransformer | ... | NOTE Phase 14 BUG-SWIFT-001..005 fixes |
| SwiftBlockFormatter | tSwiftBlockFormatter | ... | NOTE Phase 14 BUG-SWIFT-001..005 fixes |
| LogRow | tLogRow | ... |
| ConvertType | tConvertType | ... |
| XMLMap | tXMLMap | ... |
| ExtractXMLField | tExtractXMLField | ... |
| ExtractJSONFields | tExtractJSONFields | ... |
... (full transform/ family)

## Out-of-Scope Components
- List the V2 deferred items from REQUIREMENTS.md (COMP-V2-*)
- tMSSql* family, distributed/parallel components, UI designer

## How To Regenerate This Reference
- Option A: manual update at component-add time
- Option B (deferred -- D-deferred): scripts/gen_component_reference.py reading REGISTRY
- Phase 15 ships Option A; Option B is documented as a future improvement
```

**Length target:** 200-300 lines. The registry inventory is the bulk; everything else is tight.

---

### B.3 -- `docs/CONTRIBUTING.md` (target ~250-400 lines)

**Purpose:** Human-contributor entry point. Encodes the load-bearing project rules per D-C3. **References CLAUDE.md, does not duplicate it.**

**Source-of-truth files:**
- `CLAUDE.md` (read once to verify anchors; cite by section name not by line number, since CLAUDE.md drifts)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (Lessons Learned -- registry+abstract pattern, pipeline tests, pragma allowlist)
- `tests/conftest.py` (run_job_fixture, assert_ascii_logs)
- `tests/fixtures/jobs/README.md` (pipeline-test fixture authoring)
- `scripts/check_per_module_coverage.py` (95% floor gate)
- `pyproject.toml` `[tool.coverage.*]` blocks
- User memory rules: feedback_ascii_logging, feedback_fix_source_no_fallbacks, feedback_rewrite_over_patch, feedback_verify_audit_claims, feedback_scope_boundaries

**Critical Phase 14 lessons to encode:**
- **"Pipeline tests are essential for lifecycle modules"** -- the BUG-PDC/SWIFT/FIJ trio was caught precisely BECAUSE pipeline tests via `run_job_fixture` were added. Mock-only tests passed even when the class wasn't registered.
- **"Fix source, no fallbacks"** -- 11 BUG-* root-cause patches in Phase 14 were preferred over defensive shims.
- **"D-C5 dead-code policy"** -- prefer DELETE unreachable branches over `# pragma: no cover`. Phase 14 deleted 12+ dead branches across plans 14-02, 14-05, 14-06, 14-07, 14-08.
- **"D-C3 pragma allowlist via pyproject"** -- the `[tool.coverage.report] exclude_also` regex pattern (currently in pyproject.toml) is the enforcement mechanism. Inline `# pragma: no cover` is forbidden in scope.
- **Registry+abstract systemic discipline** -- a hard rule, not a guideline.

**Recommended outline:**

```
# Contributing to DataPrep
*Last updated: 2026-MM-DD*

## Audience
- Human contributors writing or modifying engine code, converter code, or tests.
- Claude-driven contributors should first read CLAUDE.md, then this file for any human-facing process bits CLAUDE.md does not cover.

## Project Rules (Load-Bearing)

### Rule 1: ASCII-only logs and docs
- No emoji, no smart quotes, no en/em dashes; use `--` for ranges.
- Project memory `feedback_ascii_logging`. RHEL servers consume logs.
- Test enforcement: `tests/conftest.py:assert_ascii_logs` for tests that exercise log-emitting paths.

### Rule 2: Custom exception hierarchy (never raise generic Exception/RuntimeError/ValueError from component code)
- Hierarchy lives at `src/v1/engine/exceptions.py`. See CLAUDE.md "Error Handling" sections.
- Always include component_id (`f"[{self.id}] ..."`) in error messages.

### Rule 3: Fix source, no fallbacks
- Phase 14 closed 11 BUG-* root-cause patches via this rule. See `feedback_fix_source_no_fallbacks` memory.
- Do not paper over bad inputs with defensive shims downstream. Fix the source.

### Rule 4: Atomic commits per file
- One logical change per commit.
- Reference: Phase 14 D-F2 / constraint #7. Phase 14 shipped ~110 commits across 12 plans, each tightly scoped.

### Rule 5: BaseComponent abstract methods AND registry membership are MANDATORY
- Every BaseComponent subclass MUST:
  - Be decorated with @REGISTRY.register("PascalCaseName", "tTalendName")
  - Implement _validate_config() that raises ConfigurationError for any required missing key
- The Phase 14 BUG-PDC-001/002, BUG-SWIFT-001..005, BUG-FIJ-001/002 trio (all production bugs) were variations of THIS rule being violated. Engine silently drops unregistered classes as "Unknown component type".
- See `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` for the full 12-rule (Phase 7.2 promoted to 13 with this) contract.

### Rule 6: 95% per-module line coverage floor
- Every module under `src/v1/engine/` and `src/converters/` (excluding `complex_converter/`) must clear 95.0% line coverage.
- Paste-runnable gate: `python -m pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=json` then `python scripts/check_per_module_coverage.py coverage.json`.
- Reference: CLAUDE.md "Coverage" section. Source of truth for the regex allowlist is `pyproject.toml [tool.coverage.report] exclude_also`.
- Inline `# pragma: no cover` is FORBIDDEN in scope (D-C3 enforcement via `exclude_also` regex, not inline pragmas).

### Rule 7: D-C5 dead-code policy
- Prefer DELETE unreachable branches over `# pragma: no cover` annotations.
- Phase 14 deleted 12+ dead branches; the deletion is reversible via git but the live code is cleaner.

### Rule 8: Pipeline tests for lifecycle-sensitive modules
- For executor / base_component / iterate / file I/O / trigger flow, write tests using `tests/conftest.py:run_job_fixture` + `tests/fixtures/jobs/{subsystem}/{behavior}.json`.
- Mock-only tests pass even when the class is unregistered. Phase 14 BUG-PDC/SWIFT/FIJ are the cautionary tale.
- Reference: `tests/fixtures/jobs/README.md` for fixture-job authoring.

### Rule 9: Talend feature parity is non-negotiable
- Any Talend job using the target components must produce identical results when run through the Python engine.
- New features MUST be backed by .item / _java.xml reference (cite the Talend source).

### Rule 10: Converter JSON format is FROZEN
- Engine changes cannot require re-conversion of existing JSONs.
- Adding new config keys is fine; renaming or removing existing keys is breaking.

## Workflow

### Authoring a New Component
- Step 1: Read `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` (engine side) or `docs/v1/patterns/CONVERTER_PATTERN.md` (converter side).
- Step 2: Author the class in the correct category directory under `src/v1/engine/components/` or `src/converters/talend_to_v1/components/`.
- Step 3: Decorator-register via `@REGISTRY.register("PascalName", "tTalendName")`.
- Step 4: Implement `_validate_config()` raising ConfigurationError.
- Step 5: Write tests per `docs/v1/patterns/ENGINE_TEST_PATTERN.md` (engine) or `TEST_PATTERN.md` (converter). Include a `TestRegistration` class.
- Step 6: Run the coverage gate locally. Floor: 95% per-module.
- Step 7: Commit atomically per Rule 4.

### Fixing a Bug
- Step 1: Reproduce with a failing test (project memory `feedback_fix_source_no_fallbacks`).
- Step 2: Patch the root cause in source (not a downstream defensive shim).
- Step 3: Verify the test now passes; verify no other tests regress.
- Step 4: Commit the source fix + test as a single atomic commit per file (or two: src then test).

### Modifying Conventions
- Project conventions live in CLAUDE.md.
- This file (CONTRIBUTING.md) summarizes load-bearing rules and references CLAUDE.md.
- DO NOT update CLAUDE.md as part of a feature PR. CLAUDE.md edits are a separate concern.

## Tests

### Test Inventory
- `tests/v1/engine/` -- engine-side unit + pipeline tests
- `tests/converters/talend_to_v1/` -- converter-side unit + integration tests
- `tests/integration/` -- E2E integration tests (Phase 16 will grow this)
- `tests/fixtures/jobs/` -- pipeline-test JSON fixtures
- `tests/fixtures/data/` -- test data files (binary + text + JSON via D-RULE3 .gitignore negations)
- `tests/fixtures/swift/` -- SWIFT MT synthetic generator

### Running Tests
- All: `python -m pytest tests/`
- Engine subsystem: `python -m pytest tests/v1/engine/components/<subsystem>/`
- With Java bridge (requires JVM 11+): `python -m pytest tests/ -m java`
- With Oracle (requires Docker for testcontainers): `python -m pytest tests/ -m oracle`
- Parallel: `python -m pytest tests/ -n auto`

### Coverage
- See CLAUDE.md "Coverage" section.
- Gate: `scripts/check_per_module_coverage.py coverage.json`
- Output file: `coverage.json` is gitignored at the project root; per-phase JSON artifacts are committed under `.planning/phases/*/`.

## Style

- See CLAUDE.md "Conventions" for full detail.
- Highlights:
  - `snake_case.py` files, `PascalCase` classes, `_` prefix for private
  - 4-space indent
  - Double quotes for strings (Python)
  - Type hints on public signatures
  - `logger = logging.getLogger(__name__)` at module level

## Git Workflow

### Branch Naming
- `feature/<short-name>` for new work
- `fix/<short-name>` for bug fixes
- `docs/<short-name>` for doc-only changes

### Commit Messages
- Format: `type(scope): short description`
- Examples: `feat(swift): add SWIFT block formatter`, `fix(map): null join semantics`, `docs(15): write CONTRIBUTING.md`
- See ROADMAP.md / phase plan files for precedent style.

### PR Process
- TBD by manager; this section can stay minimal until the team formalizes a PR template.

## See Also
- CLAUDE.md (Claude-specific instructions)
- docs/ARCHITECTURE.md (system overview)
- docs/COMPONENT_REFERENCE.md (registry inventory)
- docs/DEPLOYMENT.md (runtime requirements)
- docs/v1/patterns/ (detailed authoring guides)
```

**Length target:** 250-400 lines. The 10 rules + workflow + tests are the bulk.

---

### B.4 -- `docs/DEPLOYMENT.md` (target ~150-250 lines)

**Purpose:** What's needed to run DataPrep in production. Per D-C5: Linux + JVM 11+ is the validated runtime.

**Source-of-truth files:**
- `pyproject.toml` (Python dependency pins, including `pytest-cov>=7.0,<8`, `pytest-xdist>=3.8,<4`)
- `src/v1/java_bridge/java/pom.xml` (Java 11 minimum, Apache Arrow 15.0.2, Groovy 3.0.21, Py4J 0.10.9.7)
- `src/v1/engine/java_bridge_manager.py` (dynamic port allocation, JVM 11+ requirement)
- `src/v1/engine/oracle_connection_manager.py` (oracledb thin/thick mode; Phase 11 decisions)
- `.planning/phases/11-oracle-components/11-PHASE-SUMMARY.md` (if exists -- Oracle deployment decisions)
- Phase 14 D-A3 (java_bridge_manager.py measured WITH `-m java` markers)
- `tests/fixtures/jobs/README.md` (test runtime requirements)

**Critical Phase 14 lessons to encode:**
- JVM 11+ is REQUIRED on PATH (D-A3) -- not optional. The full test suite (`-m java`) requires it.
- Oracle integration tests use testcontainers (Docker required) but are opt-in (`-m oracle`).
- pandas 3.0.1 is the validated pandas runtime (project memory `project_pandas3_installed`); CoW behavior matters for `pd.isna()` etc.
- No CI gate currently; the paste-runnable command is the verification mechanism (D-E1 of Phase 14).

**Recommended outline:**

```
# DataPrep Deployment Guide
*Last updated: 2026-MM-DD*

## Validated Runtime
- Linux servers (RHEL family validated; other Linux distros work but unvalidated)
- Python 3.10+
- JVM 11+ on PATH
- Apache Maven 3.x (for building the Java bridge JAR -- one-time)
- Optional: Docker (for Oracle integration tests via testcontainers)

## Python Dependencies
- Pinned in `pyproject.toml`. Key pins:
  - pandas 3.0.x (validated 3.0.1; CoW behavior is load-bearing)
  - pyarrow (Arrow IPC for Java bridge data transfer)
  - py4j 0.10.9.7+ (gateway client; 0.10.9.9 upgrade pending per BRDG-05)
  - pytest >=7, pytest-cov >=7.0 <8, pytest-xdist >=3.8 <4
  - openpyxl, xlrd (Excel)
  - lxml >=4.9 (XML, with secure-parser flags)
  - oracledb (Oracle thin-mode; thick-mode optional)
  - jsonpath_ng (JSONPath in extract_json_fields)
  - PyYAML (SWIFT transformer config)
- Install: `pip install -e ".[all]"` (or equivalent extras)

## Java Bridge
- Source: `src/v1/java_bridge/java/` (Maven project)
- Build: `cd src/v1/java_bridge/java && mvn package`
- Artifact: `target/java-bridge-with-dependencies.jar`
- Runtime requirement: JVM 11+ on PATH
- Port: dynamically allocated via socket.bind('', 0) (no hardcoded port; safe under parallel test workers)
- Dependencies (compiled into JAR): Apache Arrow 15.0.2, Groovy 3.0.21, Py4J 0.10.9.7

## Oracle Components (Phase 11)
- Driver: oracledb (replaces cx_Oracle)
- Modes:
  - Thin mode (default): pure Python; no Oracle Client install needed
  - Thick mode: requires Oracle Instant Client on the host
- Supported CONNECTION_TYPE: ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_RAC
- DEFERRED: ORACLE_OCI, ORACLE_WALLET (raise ConfigurationError with deferred-feature message)
- Credentials: expected in context variables, NEVER in code or logs

## Configuration
- No `.env` files used. Context variables come from the job config JSON (`context`, `default_context`).
- Job config schema: see `docs/v1/talend_to_v1_converter_guide.md` for the JSON format.

## Running a Job
- CLI: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]`
- Programmatic: `from src.v1.engine import ETLEngine; ETLEngine(config_dict).execute()`
- Convenience: `from src.v1.engine.engine import run_job; run_job("path/to/job.json", {"override_var": "value"})`

## Logging
- stdlib `logging`; ASCII-only output (project rule).
- Default level: INFO; set DEBUG for chunk processing detail.
- Engine emits structured `[component_id]`-prefixed messages.

## Test Suite Runtime
- Full suite: `python -m pytest tests/ -n auto` (parallel via pytest-xdist)
- Engine-only: `python -m pytest tests/v1/engine/ -n auto`
- With Java bridge: `python -m pytest tests/ -m java` (requires JVM 11+ on PATH)
- With Oracle: `python -m pytest tests/ -m oracle` (requires Docker)

## Coverage Gate
- Paste-runnable, per CLAUDE.md "Coverage" section.
- Floor: 95% line coverage per in-scope module (181 modules as of Phase 14 closeout).
- Reproducible: `python -m pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=json && python scripts/check_per_module_coverage.py coverage.json`

## Known Non-Blocking Items
- (carry forward from STATE.md "Blockers/Concerns")
- Linux/RHEL `mvn package` build verified only on Darwin so far; full Linux build verification pending.
- tNormalize combined-flags vs golden Talend job output -- non-blocking, pending Phase 16 integration testing.

## See Also
- docs/ARCHITECTURE.md
- docs/CONTRIBUTING.md
- CLAUDE.md "Technology Stack"
```

**Length target:** 150-250 lines. Sections are tight, evidentiary.

---

## Section C -- Pitfalls and Constraints

### C.1 -- Out-of-scope guardrails (HARD STOPS)

1. **`docs/v1/audit/` is OFF LIMITS in Phase 15.** Per D-A4. 89 files (3 cross-cutting + 86 per-component). Phase 15.1 owns reconciliation. Researcher / planner must not propose any task that touches `docs/v1/audit/**`.
2. **CLAUDE.md is OFF LIMITS in Phase 15.** Per D-B4. CONTRIBUTING.md references CLAUDE.md (by section name) but does not copy or edit it.
3. **`.planning/`, `.claude/`, `.gemini/` are OFF LIMITS.** Per CONTEXT.md "Out of scope". These are planning + workflow tooling, not user-facing docs.
4. **`tests/fixtures/jobs/README.md` STAYS.** Per CONTEXT.md "Out of scope". CONTRIBUTING.md references it; no edit.
5. **NO CI / pre-commit / GitHub Actions / freshness lint.** Per D-B1. Stale-doc detection is a manual review concern.
6. **NO Sphinx / MkDocs / Docusaurus / doc-gen tooling.** Per D-B2. Plain Markdown only.

### C.2 -- The "stale" check protocol (mechanical per-doc verification)

Each surviving / new doc in Phase 15 needs a per-file verification step (D-E2). Mechanical checks the planner should bake into per-doc tasks:

| Check | What to run | Catches |
|-------|-------------|---------|
| Class/function name still exists in src/ | `grep -rn "ClassName" src/ \|\| echo MISSING` | Doc references classes that were renamed or deleted |
| Line-number citations | Spot-check each `file.py:NN` reference; never cite line numbers that may drift | Doc cites a line that shifted after refactor |
| Component-status claim | Read REQUIREMENTS.md status flag + STATE.md latest closure | Doc claims something is "WIP" when it shipped |
| Phase reference | Cross-reference against ROADMAP.md phase status | Doc cites a forward phase that already closed or never happened |
| Path references | `ls <path>` for any directory path mentioned | Doc references `complex_converter` or other dead paths |
| Talend component "in scope" framing | Cross-reference REQUIREMENTS.md (v1 list vs V2 list) | Doc claims component is in milestone when it is V2 deferred |

The planner should make these checks explicit in per-doc tasks (e.g., "Task 15-04: Patch ENGINE_TEST_PATTERN.md -- add Phase 14 pipeline-pattern section. Verification: grep `run_job_fixture` in `tests/conftest.py` AND in the new doc text").

### C.3 -- ASCII-only enforcement (D-C1)

**Recommendation: human discipline, not tooling.** Per D-B1 / D-B2 (no CI lint, no doc tooling) the project rejects automated freshness/style checks for Phase 15. The planner can spot-check with a simple grep at commit time:

```
grep -nP "[^\x00-\x7F]" docs/ARCHITECTURE.md
```

(returns lines with any non-ASCII byte). Per-doc plan tasks can include this grep as a verification step. No new tooling required.

### C.4 -- The deleted `docs/ARCHITECTURE.md` is NOT updated

The existing `docs/ARCHITECTURE.md` (812 lines, 14-Apr) is DELETED per D-A1, not edited. The replacement at `docs/ARCHITECTURE.md` is fresh-written from `.planning/codebase/ARCHITECTURE.md` (with corrections per Section B.1 above -- notably removing the `COMPONENT_REGISTRY` static-dict claim that even the codebase map repeats). Do not propose tasks to "update" the existing file; the workflow is `git rm` -> commit -> new file -> commit.

### C.5 -- The `.planning/codebase/*.md` maps are themselves slightly stale

The codebase maps were last regenerated 2026-04-14 (header dates confirm). They predate Phase 7.1, Phase 8, Phase 11, Phase 12, Phase 14. Specific staleness:
- ARCHITECTURE.md / STRUCTURE.md / CONVENTIONS.md / STANDARDS.md (the codebase one in `.planning/codebase/`) all still reference `ETLEngine.COMPONENT_REGISTRY` as a static dict. WRONG -- the engine now uses `src/v1/engine/component_registry.py` decorator-based `REGISTRY`.
- STRUCTURE.md missing: `oracle_*.py` files under `src/v1/engine/components/database/`, `flow_to_iterate.py` under `iterate/`, several Phase 8 / 11 / 12 component files.
- TESTING.md (not read in this research but flagged): may miss Phase 14's `tests/conftest.py` infrastructure.

**Implication:** Planner must NOT treat `.planning/codebase/*.md` as ground truth in isolation. For load-bearing claims (engine registry, runtime requirements, component inventory), cross-check against the live `src/v1/engine/engine.py` + `component_registry.py` + REQUIREMENTS.md + Phase 14 PHASE-SUMMARY. The codebase maps are a starting point, not the authority. This research has already done that cross-check for the canonical-doc skeletons in Section B.

### C.6 -- "Drop" recommendations require zero-consumer verification

Before deleting AUDIT_REPORT_TEMPLATE.md, METHODOLOGY.md, NEXT_MILESTONE_GUIDE.md, STANDARDS.md, the planner should verify none of:
- `docs/v1/audit/**` files reference them (Phase 15.1 may want to keep methodology; if so, MOVE rather than DELETE)
- `.planning/` planning artifacts reference them by path (likely safe; .planning/ is the GSD pipeline, not the source-of-truth content)
- `CLAUDE.md` references them (CLAUDE.md is off limits but if it references a doc being dropped, the rule "references CLAUDE.md don't break" means we should LEAVE the doc; if CLAUDE.md only references CLAUDE.md itself + .planning/, we're fine)

Quick verification command (planner runs during planning):
```
grep -rn "AUDIT_REPORT_TEMPLATE\|METHODOLOGY\.md\|NEXT_MILESTONE_GUIDE\|STANDARDS\.md" \
  docs/v1/audit/ CLAUDE.md .planning/ 2>/dev/null
```

If any matches surface in `docs/v1/audit/`, the planner can:
- Option A: defer deletion to Phase 15.1 (since 15.1 owns audit/ anyway)
- Option B: delete and update the audit/ reference as part of Phase 15.1 (cleaner)
- Option C: keep the doc but move under `docs/v1/patterns/` if it has a legitimate ongoing consumer

This research recommends Option A for safety -- if 15.1 wants methodology back, it can resurrect from git.

### C.7 -- Order-of-operations matters for the 22 top-level deletes

Per D-A1 the 22 top-level files are deleted. Per D-D3 a minimal new `README.md` is added. Order:
1. Add new `README.md` at root FIRST (so the repo isn't temporarily README-less if reviewing mid-commit)
2. Delete the 22 top-level docs/ files (split into atomic commits per D-E1, but practically one bulk-delete commit is acceptable per discussion's "remove top-level docs/ batch" example)
3. Add the 4 new canonical docs/ files (each in its own commit)
4. Standards folder rename + sibling moves (in their own commits)
5. Per-file fixes to surviving standards/patterns docs (each in its own commit)

This sequencing prevents a window where the repo has no README + no docs/ARCHITECTURE.md simultaneously.

---

## Section D -- Open Questions for the Planner-Checker

### D.1 -- Should NEXT_MILESTONE_GUIDE.md be moved to `.planning/archive/` instead of deleted?

**Context:** NEXT_MILESTONE_GUIDE.md (159 lines) is a planning-style artifact (the "v1.1 standardization milestone" playbook) that never executed. Deleting it loses the historical "what was originally planned" record.

**Options:**
- **Option A:** Delete outright (this research's recommendation in A.8).
- **Option B:** Move to `.planning/archive/historical_plans/NEXT_MILESTONE_GUIDE.md` -- preserves history without polluting `docs/v1/standards/`.
- **Option C:** Keep in `docs/v1/standards/` (or wherever the folder rename lands) with a `*ARCHIVED -- historical only, never executed*` banner.

**Researcher's preference:** Option A. Git keeps the deletion reversible; if someone needs the historical playbook, `git log -- docs/v1/standards/NEXT_MILESTONE_GUIDE.md` retrieves it. The doc has no live consumer; preserving it under `.planning/` violates "scope boundaries" by leaking docs concerns into planning concerns.

**Decision required from:** planner / discuss-phase if they want to override.

### D.2 -- Should METHODOLOGY.md and AUDIT_REPORT_TEMPLATE.md be deferred to Phase 15.1 rather than deleted in Phase 15?

**Context:** Phase 15.1 (Documentation Audit Reconciliation) will reconcile `docs/v1/audit/` files against current code. Those files were authored using METHODOLOGY.md's scoring framework and AUDIT_REPORT_TEMPLATE.md's section structure. Phase 15.1 may want to update the methodology rather than delete it.

**Options:**
- **Option A:** Delete in Phase 15 per D-A6 (this research's recommendation in A.5 / A.7).
- **Option B:** Defer the deletion decision to Phase 15.1; Phase 15 leaves them untouched.
- **Option C:** Keep both, fix their stale claims (e.g., the "Database components excluded" claim in METHODOLOGY.md), and move to `docs/v1/patterns/` as live methodology references.

**Researcher's preference:** Option A. Per Section C.6, the planner should run the quick grep `grep -rn "METHODOLOGY\|AUDIT_REPORT_TEMPLATE" docs/v1/audit/ CLAUDE.md`. If zero hits, Option A is clean. If audit/ files reference them, fall back to Option B (defer). Phase 15.1 can resurrect from git as needed.

**Decision required from:** planner / discuss-phase, contingent on grep result.

### D.3 -- COMPONENT_REFERENCE.md generation strategy (inline table vs script)

**Context:** D-C6 says "registry-driven index" but defers to planner whether to author an inline Markdown table or wire `scripts/gen_component_reference.py` that walks `REGISTRY` and emits the table.

**Options:**
- **Option A:** Inline Markdown table, manually maintained, ~80 rows.
- **Option B:** Add `scripts/gen_component_reference.py` (~50-100 lines stdlib) that imports the REGISTRY and emits the table; commit the script and the generated `docs/COMPONENT_REFERENCE.md`; document the regeneration step.
- **Option C:** Hybrid -- inline table for now, script later (defer to Phase 16 / future).

**Researcher's preference:** Option A for Phase 15, with Option B as a deferred follow-on. Reasoning: D-B2 forbids doc-gen TOOLING (Sphinx etc.), but a simple stdlib script is a different category and is even explicitly allowed by CONTEXT.md "Deferred Ideas". However: adding the script consumes Phase 15 budget on tooling rather than docs. Ship Option A (manual table) for Phase 15, capture Option B in a future quick task or fold into Phase 15.1.

**Decision required from:** planner.

### D.4 -- Folder rename: `patterns/` vs `conventions/` vs other?

**Context:** D-D1 says `docs/v1/standards/` may be renamed; acceptable alternatives are `docs/v1/patterns/` or `docs/v1/conventions/`.

**Options:**
- **Option A:** `docs/v1/patterns/` (this research's recommendation throughout Section A).
- **Option B:** `docs/v1/conventions/`.
- **Option C:** Keep `docs/v1/standards/` (no rename).

**Researcher's preference:** Option A. Reasoning:
- The surviving content is gold-standard authoring patterns + manual authoring guide + BaseComponent reference card. "Patterns" describes this better than "standards" (which implies a compliance regime) or "conventions" (which implies style choices).
- "Standards" was the old broad name when the folder included methodology, audit templates, etc. Post-DROP, the content is narrower.
- `docs/v1/patterns/` reads cleanly: "Read the patterns/ folder to learn how to author a new component".

**Decision required from:** planner.

### D.5 -- Should `BaseComponent-Info.md` keep its "Gaps" section?

**Context:** A.10 found G-01..G-05, G-10, G-12 are FIXED post-Phase-7.1, but G-06, G-07, G-08, G-09, G-11 may still be open. The doc currently lists them all as live gaps.

**Options:**
- **Option A:** Strike-through fixed gaps; leave open gaps with explicit "OPEN" markers; cite which Phase/plan fixed each fixed gap.
- **Option B:** Delete the Gaps section entirely -- BaseComponent-Info.md becomes just the lifecycle / abstractions reference card.
- **Option C:** Move the Gaps section to a separate `.planning/` doc (open issues track) and keep BaseComponent-Info.md as a pure reference card.

**Researcher's preference:** Option A. The "Gaps" framing has value as a known-limitations record for a contributor reading the reference card. Marking fixed items as such (with phase reference) preserves the historical record; marking unfixed items explicitly tells the contributor "this is a known gap, don't waste time discovering it". Option B loses information; Option C scatters it.

**Decision required from:** planner.

### D.6 -- Root `README.md` content -- minimal or richer?

**Context:** D-D3 says minimal: project title, one-paragraph description, link to `docs/ARCHITECTURE.md`, link to `CLAUDE.md`.

**Options:**
- **Option A:** Strict D-D3 minimum (~20-30 lines).
- **Option B:** Slightly richer: add Quickstart (engine CLI invocation, converter CLI invocation), Development setup (pip install + mvn package), and link to docs/ files. ~80-100 lines.

**Researcher's preference:** Option B for usability. D-D3 says "Minimal" but allows the 4 canonical doc links plus CLAUDE.md. Adding two quickstart code blocks (5 lines each) is still minimal in spirit and saves the new-comer one click to docs/ARCHITECTURE.md. The locked decision is "no expansion beyond the 4 canonical docs", which Option B respects.

**Decision required from:** planner.

### D.7 -- Should the surviving `talend_to_v1_converter_guide.md` move into `docs/v1/patterns/`?

**Context:** A.11 recommends KEEP at `docs/v1/`. But D-D2 says any of the 3 sibling files MAY be moved into the standards/ folder.

**Options:**
- **Option A:** Keep at `docs/v1/talend_to_v1_converter_guide.md` (this research's recommendation in A.11). Rationale: user-facing usage guide vs contributor-facing pattern.
- **Option B:** Move to `docs/v1/patterns/talend_to_v1_converter_guide.md` alongside CONVERTER_PATTERN.md.

**Researcher's preference:** Option A. The two docs serve different audiences:
- CONVERTER_PATTERN.md: "I am writing a new converter class; what shape must it take?"
- talend_to_v1_converter_guide.md: "I am calling the converter from my code or CLI; how do I invoke it and read the output?"

Keeping them in separate directories reflects the audience split. The `docs/COMPONENT_REFERENCE.md` and `docs/ARCHITECTURE.md` can link to the appropriate one.

**Decision required from:** planner.

---

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/engine.py` (current engine implementation; lines 18, 140, 207 verified)
- `src/v1/engine/component_registry.py` (current decorator-based REGISTRY; 72 lines, register method at line 29)
- `src/v1/engine/base_component.py` (current BaseComponent; lines 1-100 read, exceptions and lifecycle verified)
- `tests/conftest.py` (current pipeline-test infra; run_job_fixture + assert_ascii_logs)
- `scripts/check_per_module_coverage.py` (current per-module floor gate; 60 lines read)
- `.planning/REQUIREMENTS.md` (current v1 / v2 / out-of-scope component split)
- `.planning/STATE.md` (current phase status; Phase 14 closed 2026-05-11)
- `.planning/ROADMAP.md` (Phase 15 + 15.1 + 16 scope; Phase 15 SC #1-#4)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (Phase 14 lessons -- registry+abstract systemic pattern)
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` (locked decisions; D-A1 through D-F2)
- `CLAUDE.md` (current Phase 14 §Coverage anchors; Project / Constraints / Conventions sections)
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` (686 lines read; current and correct except line-3 TBD)
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` (120 lines read; Phase 7.1 dated, needs Phase 14 update)
- `docs/v1/STANDARDS.md` (line 801 `complex_converter` reference verified WRONG)
- `docs/v1/BaseComponent-Info.md` (G-01..G-12 gap framing verified historical post-Phase-7.1)

### Secondary (MEDIUM confidence -- verified via grep cross-check)
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` (read; needs Phase 14 pipeline-pattern addition)
- `docs/v1/standards/CONVERTER_PATTERN.md` (read; current and correct)
- `docs/v1/standards/TEST_PATTERN.md` (read; current and correct)
- `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` (read; edge-case checklist references resolved bugs)
- `docs/v1/standards/METHODOLOGY.md` (read; "Database excluded" claim wrong post-Phase-11)
- `docs/v1/standards/NEXT_MILESTONE_GUIDE.md` (read; never-executed playbook)
- `docs/v1/talend_to_v1_converter_guide.md` (sample read; output-format JSON example accurate)
- `.planning/codebase/ARCHITECTURE.md` / `STRUCTURE.md` / `CONVENTIONS.md` (read; carry the stale `COMPONENT_REGISTRY` static-dict claim -- DO NOT TRUST in isolation)

### Tertiary (LOW confidence -- pending planner verification)
- The grep cross-check for `AUDIT_REPORT_TEMPLATE.md`, `METHODOLOGY.md`, `STANDARDS.md`, `NEXT_MILESTONE_GUIDE.md` references in `docs/v1/audit/**` -- this research did NOT run that grep (audit/ is OFF LIMITS per D-A4); planner should run it during planning to confirm zero-consumer status before authorizing deletes.
- Coverage of remaining 408 unread lines of MANUAL_COMPONENT_AUTHORING.md, 525 unread lines of STANDARDS.md, 408 unread lines of talend_to_v1_converter_guide.md -- this research read the first 120 lines of each; planner / per-file tasks should sweep the remainder during per-file verification (D-E2).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No file under `docs/v1/audit/**` references AUDIT_REPORT_TEMPLATE.md, METHODOLOGY.md, NEXT_MILESTONE_GUIDE.md, or STANDARDS.md by path | A.5, A.7, A.8, A.9, D.2 | DROP recommendation may need adjustment to MOVE; planner runs the grep in C.6 to verify |
| A2 | Phase 15.1 will not need METHODOLOGY.md's audit framing intact -- it can rewrite if needed | A.7 | If 15.1 needs the methodology, deletion forces a `git show` retrieval; minor cost |
| A3 | `tests/fixtures/jobs/README.md` is the canonical pipeline-fixture authoring guide that CONTRIBUTING.md references; its content covers what new contributors need | B.3 | If the README is thin, CONTRIBUTING.md may need to inline more pipeline-test guidance |
| A4 | Root `README.md` should be ~50-100 lines (Option B in D.6) | B.3 / D.6 | Locked decision; planner can override to strict-minimal Option A |
| A5 | The deferred Phase 15.1 grep-audit (registry+abstract membership) is not in Phase 15 scope; CONTRIBUTING.md only documents the rule | Section C / B.3 | If the manager wants an audit script in Phase 15, scope expands |

**If A1 grep returns any references, downgrade the DROP recommendations to DEFER-TO-15.1.**

---

## Open Questions for the Planner-Checker

See Section D.

---

## Validation Architecture

Phase 15 is a doc-only phase per D-E3. No new tests are required for Phase 15.

The existing pytest infrastructure (181 modules, 95% per-module floor) MUST continue to pass after Phase 15 lands. Specifically:
- Phase 14's `scripts/check_per_module_coverage.py coverage.json` gate still exits 0
- No files under `src/` are modified by Phase 15

| Property | Value |
|----------|-------|
| Framework | pytest (current; >=7) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` + `[tool.coverage.*]` |
| Quick run command | `python -m pytest tests/ -n auto -m "unit"` |
| Full suite command | `python -m pytest tests/ -n auto` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | Canonical doc set in place at `docs/` root | manual-only | n/a (doc verification per D-E2) | n/a |
| DOCS-02 | 11 standards-zone files deep-reviewed | manual-only | n/a (doc verification per D-E2) | n/a |

Both requirements are doc-only; per-file manual verification is the test pattern (D-E2 "verify each claim grounded in current code via grep/file-read"). No automated tests are added.

### Sampling rate
- **Per task commit:** No automated check; reviewer reads the doc diff.
- **Per wave merge:** `python -m pytest tests/ -n auto` still passes (regression guard that no Phase 15 commit accidentally touches src/).
- **Phase gate:** Full test suite still passes; per-module floor still at >=95% (carried from Phase 14).

### Wave 0 Gaps
None -- existing test infrastructure carries through Phase 15 unchanged.

---

## Metadata

**Confidence breakdown:**
- Section A per-file claims: HIGH (each claim verified via file read + cross-grep against current src/)
- Section B canonical-doc skeletons: HIGH for structure; section content depends on planner consuming the source-of-truth files cited (which are HIGH-confidence themselves)
- Section C pitfalls: HIGH (every guardrail traceable to CONTEXT.md decision IDs or REQUIREMENTS.md flags)
- Section D open questions: deliberately uncertain -- they ARE the discretion items

**Research date:** 2026-05-11
**Valid until:** 2026-06-10 (30 days for stable; the underlying src/ + .planning/ artifacts are post-Phase-14 stable until Phase 15 commits land)

---

## RESEARCH COMPLETE
