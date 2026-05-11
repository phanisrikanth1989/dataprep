---
phase: 15
plan: 8
slug: standards-keep-fix-set
type: execute
wave: 2
depends_on: [15-01, 15-07]
files_modified:
  - docs/v1/standards/ENGINE_COMPONENT_PATTERN.md      # FIX (line 3 TBD -> real ref; add header)
  - docs/v1/standards/ENGINE_TEST_PATTERN.md           # FIX (add Phase 14 pipeline-pattern section + 95% floor; add header)
  - docs/v1/standards/CONVERTER_PATTERN.md             # FIX (light; add header)
  - docs/v1/standards/TEST_PATTERN.md                  # FIX (light; add header)
  - docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md    # FIX (add Rule 13 registry+abstract; update header date)
  - docs/v1/BaseComponent-Info.md                       # FIX (strike fixed gaps; mark remaining OPEN; update header)
  - docs/v1/talend_to_v1_converter_guide.md             # FIX (header date; verify lines 120-528 against current code)
autonomous: true
requirements: [DOCS-02]
must_haves:
  truths:
    - "All 7 files patched in place; each patch is its own atomic commit per D-E1 (7 commits)"
    - "Each file has *Last updated: 2026-05-11* on line 2 (or near top per existing convention) per D-C2"
    - "Each file is ASCII-only after patches per D-C1"
    - "ENGINE_COMPONENT_PATTERN.md line 3 TBD placeholder replaced with real reference"
    - "ENGINE_TEST_PATTERN.md gains a Phase 14 section citing run_job_fixture + tests/fixtures/jobs/ + 95% floor"
    - "MANUAL_COMPONENT_AUTHORING.md gains Rule 13 (registry+abstract dual invariant) citing Phase 14 BUG-PDC/SWIFT/FIJ"
    - "BaseComponent-Info.md gaps section: G-01..G-05/G-10/G-12 marked FIXED with phase reference; G-06/07/08/09/11 marked OPEN explicitly"
    - "talend_to_v1_converter_guide.md lines 120-528 verified against current converter behavior"
    - "Files are NOT yet moved -- they stay under docs/v1/standards/ or docs/v1/ (plan 15-09 owns the rename + move)"
    - "Plan does NOT touch any file under docs/v1/audit/ (D-A4) or CLAUDE.md (D-B4) or src/ (D-E3)"
  artifacts:
    - path: docs/v1/standards/ENGINE_COMPONENT_PATTERN.md
      provides: gold-standard authoring guide (TBD placeholder fixed; header)
    - path: docs/v1/standards/ENGINE_TEST_PATTERN.md
      provides: gold-standard test-file pattern (Phase 14 pipeline section added)
    - path: docs/v1/standards/CONVERTER_PATTERN.md
      provides: gold-standard converter file structure (header refresh)
    - path: docs/v1/standards/TEST_PATTERN.md
      provides: gold-standard converter-test pattern (header refresh)
    - path: docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md
      provides: 12+1-rule manual authoring guide (Rule 13 added; Phase 14 evidence)
    - path: docs/v1/BaseComponent-Info.md
      provides: BaseComponent reference card (gaps section disambiguated)
    - path: docs/v1/talend_to_v1_converter_guide.md
      provides: external-consumer converter guide (header refresh + full-doc verification sweep)
  key_links:
    - from: docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md
      to: src/v1/engine/component_registry.py
      via: Rule 13 cites the decorator-based REGISTRY as the live invariant target
      pattern: "component_registry"
    - from: docs/v1/standards/ENGINE_TEST_PATTERN.md
      to: tests/conftest.py
      via: Phase 14 pipeline-pattern section cites run_job_fixture + assert_ascii_logs
      pattern: "run_job_fixture"
    - from: docs/v1/BaseComponent-Info.md
      to: src/v1/engine/base_component.py
      via: gaps section references base_component.py docstring + Phase 7.1 fix commits
      pattern: "base_component"
---

<objective>
Fix 7 surviving standards-zone files in place (NO move, NO rename in this plan -- plan 15-09 owns those). Each file gets:
1. A `*Last updated: 2026-05-11*` header on line 2 (or right under the H1 per existing convention).
2. Stale-claim patches verified against live source.
3. Phase 14 lessons folded in where applicable (Rule 13 in MANUAL_COMPONENT_AUTHORING; pipeline-pattern section in ENGINE_TEST_PATTERN; struck-through fixed gaps in BaseComponent-Info).

Each file is its own atomic commit per D-E1 -- 7 commits total. Files stay at their current location (`docs/v1/standards/*` for 5 of them, `docs/v1/{BaseComponent-Info,talend_to_v1_converter_guide}.md` for 2 of them) until plan 15-09 renames + moves.
</objective>

<scope>
- 7 in-place edits, each its own atomic commit.
- The 4 DROP-set files from plan 15-07 are gone before this plan starts (depends_on includes 15-07).
- ASCII discipline (D-C1) and `*Last updated:*` header (D-C2) applied to every file.
- Per-file verification (D-E2): every cited class/function/file path grep-confirmed against live source.
- NO move / rename (plan 15-09 owns).
- NO modification of docs/v1/audit/** (D-A4).
- NO modification of CLAUDE.md (D-B4).
- NO modification of src/** (D-E3).
</scope>

<out_of_scope>
- Folder rename `docs/v1/standards/` -> `docs/v1/patterns/` (plan 15-09).
- Moving `docs/v1/BaseComponent-Info.md` into `patterns/` (plan 15-09).
- Moving `docs/v1/talend_to_v1_converter_guide.md` -- per planner D.7 resolution it STAYS at `docs/v1/` (different audience from patterns/).
- DROP-set deletions (plan 15-07, already complete).
- The 4 canonical docs at `docs/` (plans 15-02..15-05, already complete via wave 1).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A5 (deep review protocol), D-C1, D-C2, D-E1 (atomic commits), D-E2 (verify-before-claim), D-E3 (no src/ patching)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section A.1 (ENGINE_COMPONENT_PATTERN -- KEEP+FIX, line 3 TBD), A.2 (ENGINE_TEST_PATTERN -- KEEP+FIX, add Phase 14 pipeline pattern), A.3 (CONVERTER_PATTERN -- KEEP+FIX light), A.4 (TEST_PATTERN -- KEEP+FIX light), A.6 (MANUAL_COMPONENT_AUTHORING -- add Rule 13 registry+abstract), A.10 (BaseComponent-Info -- strike fixed gaps), A.11 (talend_to_v1_converter_guide -- KEEP+FIX light)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (Phase 14 BUG-PDC/SWIFT/FIJ evidence, pipeline-pattern lessons)
- `src/v1/engine/component_registry.py` (decorator-based REGISTRY; cite from Rule 13)
- `src/v1/engine/base_component.py` lines 1-50 (BaseComponent docstring; cite from BaseComponent-Info)
- `tests/conftest.py` (run_job_fixture, assert_ascii_logs; cite from ENGINE_TEST_PATTERN Phase 14 section)
- `tests/fixtures/jobs/README.md` (pipeline-fixture format; cite from ENGINE_TEST_PATTERN)
- `scripts/check_per_module_coverage.py` (95% floor gate; cite from ENGINE_TEST_PATTERN)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-08-001: Fix docs/v1/standards/ENGINE_COMPONENT_PATTERN.md</name>
  <files>docs/v1/standards/ENGINE_COMPONENT_PATTERN.md</files>
  <action>
1. Insert `*Last updated: 2026-05-11*` on line 2 (right after the H1 title; if a date header already exists, replace it).
2. Find the line-3 TBD placeholder (RESEARCH A.1: `> Reference: [best example component -- TBD until Phase 4]`). Replace with a real reference. Suggested replacement based on Phase 14 maturity: `> Reference: src/v1/engine/components/file/file_input_delimited.py (post-Phase-7.1 mature; comprehensive pattern coverage)`. Confirm path exists:
   ```bash
   test -f src/v1/engine/components/file/file_input_delimited.py && echo "OK"
   ```
   If alternate reference component is preferred (e.g., `aggregate_row.py` post-Phase-14-02 lift), the executor may choose; any chosen reference MUST be grep-verified to exist.
3. Verify the rest of the doc against current source (RESEARCH A.1 found imports + Rule 11 schema-validation addendum + `_original_config` / `treat_empty_as_null` / `die_on_error` all CURRENT). Spot-check by `grep -n "@REGISTRY.register" src/v1/engine/components/file/file_input_delimited.py` (or chosen reference); should match the pattern shown in the doc.
4. ASCII-only sweep: `grep -nP "[^\x00-\x7F]" docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -> zero lines. If non-ASCII found, replace with ASCII equivalents (smart quotes -> straight; en/em dash -> `--`).
5. Commit:
   ```bash
   git add docs/v1/standards/ENGINE_COMPONENT_PATTERN.md
   git commit -m "docs(15-08): fix ENGINE_COMPONENT_PATTERN.md (TBD placeholder + header date)
   
   Phase 4/5/6/7/10/11/12 all closed since the line-3 TBD placeholder
   was written. Replaced with reference to the chosen post-Phase-7.1
   mature example. Added Last-updated header per D-C2. ASCII swept.
   12-rule body confirmed CURRENT against base_component.py and
   component_registry.py.
   
   Refs: 15-CONTEXT.md D-C2, D-E2; 15-RESEARCH.md A.1"
   ```
  </action>
  <verify>
    <automated>head -5 docs/v1/standards/ENGINE_COMPONENT_PATTERN.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/standards/ENGINE_COMPONENT_PATTERN.md)" && ! grep -qF "TBD until Phase 4" docs/v1/standards/ENGINE_COMPONENT_PATTERN.md && echo "OK"</automated>
  </verify>
  <done>TBD removed; header set; ASCII clean; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-08-002: Fix docs/v1/standards/ENGINE_TEST_PATTERN.md</name>
  <files>docs/v1/standards/ENGINE_TEST_PATTERN.md</files>
  <action>
1. Insert `*Last updated: 2026-05-11*` on line 2.
2. Add a new H2 section `## Phase 14 Pipeline-Test Pattern (lifecycle-sensitive modules)` (place near the end, before any See-Also or final-notes section). Required content:
   - For lifecycle-sensitive modules (executor, base_component, iterate, file I/O, trigger flow), augment unit tests with pipeline tests via `tests/conftest.py:run_job_fixture` + `tests/fixtures/jobs/{subsystem}/{behavior}.json` (mirror converter JSON output format).
   - `assert_ascii_logs` fixture asserts no Unicode in caplog output (ASCII enforcement per Rule 1).
   - Mock-only tests PASS even when the class is unregistered with `@REGISTRY.register` -- the 4 Phase 14 BUG instances (BUG-PDC-001, BUG-FIJ-001, BUG-SWIFT-001/002) were caught precisely BECAUSE pipeline tests exercised the full engine lookup path. Cite these BUG IDs.
   - Coverage gate: every test surface contributes to the 95% per-module floor enforced by `scripts/check_per_module_coverage.py`. See `docs/CONTRIBUTING.md` Rule 6.
   - Fixture authoring format: see `tests/fixtures/jobs/README.md`.
3. Verify all the citations: `grep -n "run_job_fixture\|assert_ascii_logs" tests/conftest.py` returns lines; `test -f scripts/check_per_module_coverage.py`; `test -f tests/fixtures/jobs/README.md`.
4. ASCII sweep.
5. Commit:
   ```bash
   git add docs/v1/standards/ENGINE_TEST_PATTERN.md
   git commit -m "docs(15-08): fix ENGINE_TEST_PATTERN.md (add Phase 14 pipeline-test pattern section)
   
   Added a 'Phase 14 Pipeline-Test Pattern' section citing
   run_job_fixture / assert_ascii_logs (tests/conftest.py),
   tests/fixtures/jobs/ JSON format, and the 95% per-module floor
   via scripts/check_per_module_coverage.py. Documents that mock-only
   tests passed even when @REGISTRY.register was missing -- BUG-PDC-001,
   BUG-FIJ-001, BUG-SWIFT-001/002 were caught by pipeline tests.
   Added Last-updated header per D-C2.
   
   Refs: 15-CONTEXT.md D-C2; 15-RESEARCH.md A.2;
   14-PHASE-SUMMARY.md Lessons Learned"
   ```
  </action>
  <verify>
    <automated>head -5 docs/v1/standards/ENGINE_TEST_PATTERN.md | grep -qF "*Last updated: 2026-05-11*" && grep -qF "run_job_fixture" docs/v1/standards/ENGINE_TEST_PATTERN.md && grep -qF "BUG-PDC" docs/v1/standards/ENGINE_TEST_PATTERN.md && grep -qF "check_per_module_coverage" docs/v1/standards/ENGINE_TEST_PATTERN.md && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/standards/ENGINE_TEST_PATTERN.md)" && echo "OK"</automated>
  </verify>
  <done>Phase 14 section added; pipeline-pattern citations present; ASCII clean; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-08-003: Fix docs/v1/standards/CONVERTER_PATTERN.md (light)</name>
  <files>docs/v1/standards/CONVERTER_PATTERN.md</files>
  <action>
1. Insert `*Last updated: 2026-05-11*` on line 2.
2. Verify the doc against current converter source (RESEARCH A.3 found content CURRENT, no substantive stale claims). Spot-check:
   - `tSchemaComplianceCheck` reference still valid (Section 3 of doc): `ls src/converters/talend_to_v1/components/file/schema_compliance_check.py 2>/dev/null || find src/converters/talend_to_v1 -name "*schema*"`
   - 12 rules still align with converter coding standards (skim).
3. ASCII sweep.
4. Commit:
   ```bash
   git add docs/v1/standards/CONVERTER_PATTERN.md
   git commit -m "docs(15-08): refresh CONVERTER_PATTERN.md header
   
   Added Last-updated header per D-C2. Content reviewed and confirmed
   CURRENT against post-Phase-11 converter codebase. ASCII swept.
   
   Refs: 15-CONTEXT.md D-C2; 15-RESEARCH.md A.3"
   ```
  </action>
  <verify>
    <automated>head -5 docs/v1/standards/CONVERTER_PATTERN.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/standards/CONVERTER_PATTERN.md)" && echo "OK"</automated>
  </verify>
  <done>Header set; ASCII clean; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-08-004: Fix docs/v1/standards/TEST_PATTERN.md (light)</name>
  <files>docs/v1/standards/TEST_PATTERN.md</files>
  <action>
1. Insert `*Last updated: 2026-05-11*` on line 2.
2. Verify the doc against current converter-test source (RESEARCH A.4 found CURRENT). Spot-check:
   - `test_schema_compliance_check.py` reference still exists: `ls tests/converters/talend_to_v1/components/file/test_schema_compliance_check.py 2>/dev/null || find tests/converters -name "test_schema*"`.
3. Optionally add a line noting Phase 14-11 STALE-INT-001 (legacy `complex_converter` test removal) if relevant -- researcher A.4 flagged this. If added, keep to 1-2 sentences; don't bloat the doc.
4. ASCII sweep.
5. Commit:
   ```bash
   git add docs/v1/standards/TEST_PATTERN.md
   git commit -m "docs(15-08): refresh TEST_PATTERN.md header
   
   Added Last-updated header per D-C2. Content confirmed CURRENT
   against post-Phase-11 converter tests. ASCII swept.
   
   Refs: 15-CONTEXT.md D-C2; 15-RESEARCH.md A.4"
   ```
  </action>
  <verify>
    <automated>head -5 docs/v1/standards/TEST_PATTERN.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/standards/TEST_PATTERN.md)" && echo "OK"</automated>
  </verify>
  <done>Header set; ASCII clean; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-08-005: Fix docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md (add Rule 13)</name>
  <files>docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md</files>
  <action>
1. Update the existing `Last updated:` header (RESEARCH A.6 noted it currently reads "2026-04-25 (Phase 7.1 lessons)"). Replace with `*Last updated: 2026-05-11 (Phase 14 lessons folded in)*` on line 2 (or wherever the existing header line lives -- conform to the existing convention rather than forcing a structural reshape).
2. Add a new H2 section `## Rule 13: Registry Membership AND Abstract Methods` (place after Rule 12; if the doc currently caps at Rule 11 or Rule 12, append). Required content:
   - Every `BaseComponent` subclass MUST:
     - Be decorated with `@REGISTRY.register("PascalCaseName", "tTalendName")` -- import `from src.v1.engine.component_registry import REGISTRY`.
     - Implement `_validate_config()` raising `ConfigurationError` on missing required keys. The abstract is declared on `BaseComponent` -- ABC will refuse instantiation otherwise.
   - **Why this is a hard rule, not a guideline**: Phase 14 closed 4 dual-bug instances of THIS rule being violated in already-shipped code:
     - BUG-PDC-001/002 (`PythonDataFrameComponent` -- transform/python_dataframe_component.py)
     - BUG-SWIFT-001/002 (`SwiftTransformer`, `SwiftBlockFormatter` -- transform/swift_transformer.py, transform/swift_block_formatter.py)
     - BUG-FIJ-001/002 (`FileInputJSON` -- file/file_input_json.py)
     Engine silently drops unregistered classes with `WARNING [engine] Unknown component type: <type>` at runtime; jobs that should have run that component just skip it.
   - Test enforcement (covers most of the rule): pipeline tests via `tests/conftest.py:run_job_fixture` exercise the full engine REGISTRY lookup path. Mock-only tests do NOT catch unregistered classes.
3. ASCII sweep.
4. Commit:
   ```bash
   git add docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md
   git commit -m "docs(15-08): add Rule 13 to MANUAL_COMPONENT_AUTHORING.md (registry+abstract)
   
   Added Rule 13 codifying the dual invariant every BaseComponent
   subclass must honor: @REGISTRY.register decoration AND
   _validate_config() implementation. Cites Phase 14 BUG-PDC-001/002,
   BUG-SWIFT-001/002, BUG-FIJ-001/002 (4 dual-bug instances found
   in shipped code). Documents the silent-drop failure mode at
   runtime and the pipeline-test enforcement pattern.
   
   Header date updated from 2026-04-25 (Phase 7.1) to 2026-05-11
   (Phase 14 lessons folded in).
   
   Refs: 15-CONTEXT.md D-C2; 15-RESEARCH.md A.6;
   14-PHASE-SUMMARY.md Lessons Learned"
   ```
  </action>
  <verify>
    <automated>grep -qF "*Last updated: 2026-05-11" docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md && grep -qE "^## Rule 13:" docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md && grep -qF "BUG-PDC" docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md && grep -qF "BUG-FIJ" docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md)" && echo "OK"</automated>
  </verify>
  <done>Rule 13 added; Phase 14 evidence cited; header refreshed; ASCII clean; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-08-006: Fix docs/v1/BaseComponent-Info.md (strike fixed gaps; mark OPEN)</name>
  <files>docs/v1/BaseComponent-Info.md</files>
  <action>
1. Insert `*Last updated: 2026-05-11*` on line 2.
2. Per planner D.5 resolution (Option A: strike-through fixed gaps; mark remaining OPEN with explicit phase reference) and RESEARCH A.10:
   - G-01..G-05, G-10, G-12: mark as `FIXED in Phase 7.1` -- in the gaps table, edit each row's description to strike-through the original gap description (use Markdown strikethrough via `~~text~~`) and append `(FIXED Phase 7.1 -- see 07.1-PHASE-SUMMARY.md)`.
   - G-06, G-07, G-08, G-09, G-11: mark as `OPEN` -- prepend `**OPEN**:` to each row's description. If executor reading the doc finds any of these is actually fixed by a later phase (verify against ROADMAP.md / STATE.md), flip to FIXED with the phase reference instead.
3. Verify the lifecycle reference card (Section 1) is still accurate against `src/v1/engine/base_component.py` lines 1-50 docstring. If the docstring evolved, update the table to match.
4. ASCII sweep.
5. Commit:
   ```bash
   git add docs/v1/BaseComponent-Info.md
   git commit -m "docs(15-08): fix BaseComponent-Info.md gaps section (strike FIXED; mark OPEN)
   
   Per RESEARCH A.10 + planner D.5 -> Option A:
   - G-01..G-05, G-10, G-12 marked FIXED (Phase 7.1) with strikethrough +
     phase reference
   - G-06, G-07, G-08, G-09, G-11 marked OPEN explicitly (or FIXED with
     phase reference if executor verified post-7.1 closure)
   - Lifecycle reference card (Section 1) verified against current
     base_component.py docstring
   - Last-updated header added per D-C2
   - ASCII swept
   
   This doc stays at docs/v1/ for now; plan 15-09 moves it into
   docs/v1/patterns/ alongside ENGINE_COMPONENT_PATTERN.md per D-D2.
   
   Refs: 15-CONTEXT.md D-C2, D-D2; 15-RESEARCH.md A.10; planner D.5 -> Option A"
   ```
  </action>
  <verify>
    <automated>head -5 docs/v1/BaseComponent-Info.md | grep -qF "*Last updated: 2026-05-11*" && grep -qE "FIXED.*Phase 7\.1|~~G-0" docs/v1/BaseComponent-Info.md && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/BaseComponent-Info.md)" && echo "OK"</automated>
  </verify>
  <done>Gaps disambiguated (FIXED vs OPEN); header set; ASCII clean; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-08-007: Fix docs/v1/talend_to_v1_converter_guide.md (header + lines-120-528 verification)</name>
  <files>docs/v1/talend_to_v1_converter_guide.md</files>
  <action>
1. Insert `*Last updated: 2026-05-11*` on line 2.
2. Per RESEARCH A.11: lines 1-120 already verified accurate (output-format JSON example matches current converter behavior). Lines 120-528 require sweep against current converter code in this task.
   - Read the file in chunks (e.g., 100 lines at a time after line 120).
   - For every cited class / function / parameter / JSON-key claim, spot-check via grep against `src/converters/talend_to_v1/`.
   - Any stale claim found: patch the doc in place. Document each patch in the commit message.
   - Common drift suspects: parameter names that may have changed since converter v1 stabilized (Phase 12 added XML output components; Phase 11 added Oracle).
3. ASCII sweep.
4. Commit:
   ```bash
   git add docs/v1/talend_to_v1_converter_guide.md
   git commit -m "docs(15-08): refresh talend_to_v1_converter_guide.md (header + line 120+ sweep)
   
   Last-updated header added per D-C2.
   Lines 120-528 swept against current converter implementation; any
   stale claims patched (see diff). Lines 1-120 already validated by
   RESEARCH A.11.
   
   This doc STAYS at docs/v1/ per planner D.7 -> Option A (different
   audience from docs/v1/patterns/ -- user-facing converter usage guide
   vs contributor-facing pattern docs).
   
   Refs: 15-CONTEXT.md D-C2; 15-RESEARCH.md A.11; planner D.7 -> Option A"
   ```
  </action>
  <verify>
    <automated>head -5 docs/v1/talend_to_v1_converter_guide.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/v1/talend_to_v1_converter_guide.md)" && echo "OK"</automated>
  </verify>
  <done>Header set; lines 120-528 swept; ASCII clean; commit landed.</done>
</task>

</tasks>

<verification_gate>

Plan 15-08 is GREEN when:
1. All 7 files exist at their PRE-rename locations (5 in `docs/v1/standards/`; 2 in `docs/v1/`).
2. Each file has `*Last updated: 2026-05-11*` (or `*Last updated: 2026-05-11 ...*` with parenthetical) near the top.
3. Each file is ASCII-only.
4. ENGINE_COMPONENT_PATTERN.md no longer contains the `TBD until Phase 4` placeholder.
5. ENGINE_TEST_PATTERN.md contains `run_job_fixture` + `BUG-PDC` + `check_per_module_coverage` citations.
6. MANUAL_COMPONENT_AUTHORING.md contains a `## Rule 13:` heading and cites BUG-PDC / BUG-FIJ / BUG-SWIFT.
7. BaseComponent-Info.md gaps section uses strikethrough or "FIXED Phase 7.1" markers + explicit OPEN markers.
8. talend_to_v1_converter_guide.md has the new header.
9. 7 atomic commits landed (one per file).
10. CLAUDE.md not modified; no `src/` modified; no `docs/v1/audit/` modified.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-08): fix ENGINE_COMPONENT_PATTERN.md (TBD placeholder + header date)` | `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` |
| 2 | `docs(15-08): fix ENGINE_TEST_PATTERN.md (add Phase 14 pipeline-test pattern section)` | `docs/v1/standards/ENGINE_TEST_PATTERN.md` |
| 3 | `docs(15-08): refresh CONVERTER_PATTERN.md header` | `docs/v1/standards/CONVERTER_PATTERN.md` |
| 4 | `docs(15-08): refresh TEST_PATTERN.md header` | `docs/v1/standards/TEST_PATTERN.md` |
| 5 | `docs(15-08): add Rule 13 to MANUAL_COMPONENT_AUTHORING.md (registry+abstract)` | `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` |
| 6 | `docs(15-08): fix BaseComponent-Info.md gaps section (strike FIXED; mark OPEN)` | `docs/v1/BaseComponent-Info.md` |
| 7 | `docs(15-08): refresh talend_to_v1_converter_guide.md (header + line 120+ sweep)` | `docs/v1/talend_to_v1_converter_guide.md` |

(Total: 7 commits.)

</commit_map>
