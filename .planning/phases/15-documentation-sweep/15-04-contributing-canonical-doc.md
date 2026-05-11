---
phase: 15
plan: 4
slug: contributing-canonical-doc
type: execute
wave: 1
depends_on: [15-01]
files_modified:
  - docs/CONTRIBUTING.md     # NEW (~250-400 lines)
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "docs/CONTRIBUTING.md exists at docs/ root (D-A3)"
    - "Header *Last updated: 2026-05-11* on line 2 (D-C2)"
    - "ASCII-only per D-C1"
    - "Encodes the 10 load-bearing rules per D-C3"
    - "Rule 5 (registry+abstract dual invariant) is explicit and cites Phase 14 BUG-PDC/SWIFT/FIJ"
    - "Rule 6 (95% per-module coverage floor) references CLAUDE.md Coverage section, does not duplicate it (D-B4)"
    - "References CLAUDE.md by section name (e.g., 'CLAUDE.md Error Handling section'), never copies CLAUDE.md content"
    - "References tests/fixtures/jobs/README.md as the pipeline-fixture authoring guide"
    - "Length within target 250-400 lines"
  artifacts:
    - path: docs/CONTRIBUTING.md
      provides: human-contributor entry point encoding load-bearing project rules and workflow
      min_lines: 200
      contains: "# Contributing to DataPrep"
  key_links:
    - from: docs/CONTRIBUTING.md
      to: CLAUDE.md
      via: section-name references (Error Handling, Logging, Coverage, etc.); MUST NOT copy CLAUDE.md content per D-B4
      pattern: "CLAUDE\\.md"
    - from: docs/CONTRIBUTING.md
      to: docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md
      via: link to the 12+1-rule contributor authoring guide (post-rename location; landing in plan 15-09)
      pattern: "patterns/MANUAL_COMPONENT_AUTHORING"
    - from: docs/CONTRIBUTING.md
      to: tests/fixtures/jobs/README.md
      via: link to pipeline-fixture authoring guide; reinforces Rule 8 (pipeline tests for lifecycle modules)
      pattern: "tests/fixtures/jobs/README"
    - from: docs/CONTRIBUTING.md
      to: scripts/check_per_module_coverage.py
      via: cited as the 95% floor gate enforcement (Rule 6)
      pattern: "check_per_module_coverage"
---

<objective>
Author `docs/CONTRIBUTING.md` (~250-400 lines) encoding the 10 load-bearing rules a human contributor must follow when working in DataPrep. Per D-C3 the rules are codified; per D-B4 CONTRIBUTING.md REFERENCES CLAUDE.md by section name but does NOT duplicate it. The doc encodes the Phase 14 systemic lesson (Rule 5 -- registry+abstract dual invariant) and the 95% per-module floor (Rule 6). Workflow / Tests / Style / Git sections give a contributor everything they need to make a clean PR without needing a teammate.
</objective>

<scope>
- Create `docs/CONTRIBUTING.md` from scratch.
- 10 numbered rules covering: ASCII-only logs, custom exception hierarchy, fix-source-no-fallbacks, atomic commits, registry+abstract dual invariant (the LOAD-BEARING Phase 14 lesson), 95% coverage floor, D-C5 dead-code policy, pipeline tests for lifecycle modules, Talend feature parity, FROZEN converter JSON format.
- Workflow section: authoring a new component, fixing a bug, modifying conventions.
- Tests section: test inventory, running tests, coverage gate.
- Style section: brief; references CLAUDE.md Conventions for the full table.
- Git workflow: branch naming, commit message format, PR process (minimal -- manager-owned future formalization).
- See Also: cross-links to CLAUDE.md, ARCHITECTURE.md, COMPONENT_REFERENCE.md, DEPLOYMENT.md, docs/v1/patterns/.
- ASCII-only per D-C1; `*Last updated: 2026-05-11*` header per D-C2.
- Single commit: `docs(15-04): add docs/CONTRIBUTING.md`.
</scope>

<out_of_scope>
- CLAUDE.md edits (D-B4 -- HARD STOP).
- Duplicating CLAUDE.md content. The doc REFERENCES CLAUDE.md by section name; readers visit CLAUDE.md for full detail.
- src/ changes (D-E3).
- A PR template under `.github/PULL_REQUEST_TEMPLATE.md` -- out of Phase 15 scope (D-B1 no CI/tooling); the Git Workflow PR Process subsection stays minimal and notes "TBD by manager".
- Editing `docs/v1/audit/` (D-A4).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A3 (docs/ root), D-B4 (no CLAUDE.md edits or copying), D-C1 (ASCII), D-C2 (header), D-C3 (10 load-bearing rules MANDATORY content)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section B.3 (full skeleton for CONTRIBUTING.md with all 10 rule headings)
- `CLAUDE.md` (read once to verify section anchor names; cite by section name NOT line number)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (Lessons Learned -- registry+abstract pattern, pipeline tests, fix-source policy, pragma allowlist, atomic commits)
- `tests/conftest.py` (run_job_fixture, assert_ascii_logs -- referenced from Rule 8)
- `tests/fixtures/jobs/README.md` (pipeline-fixture authoring guide -- referenced from Rule 8)
- `scripts/check_per_module_coverage.py` (95% floor gate -- referenced from Rule 6)
- `pyproject.toml` (coverage exclude_also regex -- referenced from Rule 6 / Rule 7)
- User memory rules (cited in plan 15-PLAN.md): feedback_ascii_logging, feedback_fix_source_no_fallbacks, feedback_rewrite_over_patch
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-04-001: Verify CLAUDE.md section anchors</name>
  <files>(read-only)</files>
  <action>
The doc will cite CLAUDE.md by section name. Confirm the section names exist before citing them.

```bash
grep -E "^## |^### " CLAUDE.md | head -40
```

Expected (or similar -- header text may have evolved): `## Project`, `## Technology Stack`, `## Conventions`, `## Architecture`, `## Coverage`, headings for Naming Patterns, Code Style, Error Handling, Logging, Comments, Function Design, Module Design.

For Rule 6 (95% floor) the doc MUST cite the existing `## Coverage` section in CLAUDE.md (Phase 14 added it). Verify it exists:

```bash
grep -nE "^## Coverage" CLAUDE.md
grep -nF "check_per_module_coverage" CLAUDE.md
```

If `## Coverage` does NOT exist or `check_per_module_coverage` is not referenced from CLAUDE.md, STOP. The doc's Rule 6 cannot reference a nonexistent CLAUDE.md anchor; either flag the discrepancy in plan SUMMARY (likely the user updates CLAUDE.md separately) or downgrade the citation to be path-based (`see CLAUDE.md`) without naming the section.

Also confirm `scripts/check_per_module_coverage.py` exists and is the actual gate script:

```bash
test -f scripts/check_per_module_coverage.py && head -1 scripts/check_per_module_coverage.py
```
  </action>
  <verify>
    <automated>grep -qE "^## Coverage" CLAUDE.md && grep -qF "check_per_module_coverage" CLAUDE.md && test -f scripts/check_per_module_coverage.py && echo "OK: CLAUDE.md Coverage anchor + gate script verified"</automated>
  </verify>
  <done>CLAUDE.md section anchors verified; gate script confirmed present; any discrepancies recorded in plan SUMMARY.</done>
</task>

<task type="auto">
  <name>Task 15-04-002: Author docs/CONTRIBUTING.md</name>
  <files>docs/CONTRIBUTING.md</files>
  <action>
Create the file with the structure below. Length target: 250-400 lines. ASCII-only.

Required H2 sections (in order):

1. `# Contributing to DataPrep` (H1, line 1)
2. `*Last updated: 2026-05-11*` (line 2 exact)
3. `## Audience` -- 1 paragraph: human contributors writing/modifying engine, converter, or tests. Note that Claude-driven contributors read CLAUDE.md first, then this file for human-facing process bits CLAUDE.md doesn't cover.
4. `## Project Rules (Load-Bearing)` -- 10 H3 subsections, in this order. The exact rule wording below is required (planner-specified per D-C3):

   - `### Rule 1: ASCII-only logs and docs`
     - No emoji, no smart quotes, no en/em dashes; use `--` for ranges.
     - User memory: `feedback_ascii_logging`. RHEL servers consume logs.
     - Test enforcement: `tests/conftest.py:assert_ascii_logs` for tests that exercise log-emitting paths.

   - `### Rule 2: Custom exception hierarchy`
     - Never raise generic `Exception` / `RuntimeError` / `ValueError` from component code.
     - Hierarchy lives at `src/v1/engine/exceptions.py`. See CLAUDE.md "Error Handling" section.
     - Always include `[{self.id}]` prefix in error messages.

   - `### Rule 3: Fix source, no fallbacks`
     - User memory: `feedback_fix_source_no_fallbacks`. Phase 14 closed 11+ BUG-* root-cause patches with this rule.
     - Do not paper over bad inputs with defensive shims downstream. Fix the source.

   - `### Rule 4: Atomic commits per file`
     - One logical change per commit.
     - Phase 14 shipped ~88 commits across 12 plans, each tightly scoped.

   - `### Rule 5: BaseComponent abstract methods AND registry membership are MANDATORY`
     - Every `BaseComponent` subclass MUST be decorated with `@REGISTRY.register("PascalCaseName", "tTalendName")` AND implement `_validate_config()` raising `ConfigurationError` on missing required keys.
     - **Why this rule is LOAD-BEARING**: Phase 14 BUG-PDC-001/002, BUG-SWIFT-001..005, BUG-FIJ-001/002 were all variations of this rule being violated. Engine silently drops unregistered classes with "Unknown component type" at runtime. ABC refuses instantiation of classes missing `_validate_config`.
     - See `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` for the full rule contract (post-rename location landing in plan 15-09).

   - `### Rule 6: 95% per-module line coverage floor`
     - Every module under `src/v1/engine/` and `src/converters/` (excluding `complex_converter/`) must clear 95.0% line coverage.
     - Paste-runnable gate: see CLAUDE.md "Coverage" section. Run `python scripts/check_per_module_coverage.py coverage.json --floor 95` after `pytest --cov` to enforce.
     - Source of truth for the regex allowlist: `pyproject.toml` `[tool.coverage.report]` `exclude_also`.
     - Inline `# pragma: no cover` is FORBIDDEN in scope -- enforce via `exclude_also` regex only.

   - `### Rule 7: D-C5 dead-code policy`
     - Prefer DELETE unreachable branches over `# pragma: no cover` annotations.
     - Phase 14 deleted 12+ dead branches; the deletion is reversible via git, and the live source is cleaner.

   - `### Rule 8: Pipeline tests for lifecycle-sensitive modules`
     - For executor / base_component / iterate / file I/O / trigger flow, write tests using `tests/conftest.py:run_job_fixture` + `tests/fixtures/jobs/{subsystem}/{behavior}.json`.
     - Mock-only tests pass even when the class is unregistered. Phase 14 BUG-PDC/SWIFT/FIJ are the cautionary tale.
     - See `tests/fixtures/jobs/README.md` for the JSON-job authoring format.

   - `### Rule 9: Talend feature parity is non-negotiable`
     - Any Talend job using the target components MUST produce identical results when run through the Python engine.
     - New features MUST be backed by .item / _java.xml reference (cite the Talend source).

   - `### Rule 10: Converter JSON format is FROZEN`
     - Engine changes cannot require re-conversion of existing JSONs.
     - Adding new config keys is fine; renaming or removing existing keys is breaking.

5. `## Workflow` -- 3 H3 subsections:
   - `### Authoring a New Component` -- 7-step bullet list: read pattern doc -> author class -> register -> validate_config -> tests -> coverage gate -> atomic commit.
   - `### Fixing a Bug` -- 4-step bullet list: reproduce with failing test -> patch root cause -> verify no regressions -> atomic commit.
   - `### Modifying Conventions` -- 1 paragraph: conventions live in CLAUDE.md; this file references them; do NOT update CLAUDE.md as part of a feature PR (CLAUDE.md edits are a separate concern).

6. `## Tests` -- 3 H3 subsections:
   - `### Test Inventory` -- bullet list of `tests/v1/engine/`, `tests/converters/talend_to_v1/`, `tests/integration/`, `tests/fixtures/jobs/`, `tests/fixtures/data/`, `tests/fixtures/swift/`.
   - `### Running Tests` -- bullet list of commands: full suite, engine-only, with `-m java`, with `-m oracle`, parallel `-n auto`.
   - `### Coverage` -- 2-3 sentences: see CLAUDE.md "Coverage" for the gate. `coverage.json` is gitignored at project root; per-phase JSON artifacts committed under `.planning/phases/*/`.

7. `## Style` -- 1 short subsection: see CLAUDE.md "Conventions" for the full table. Highlights bullet list: `snake_case.py` files, `PascalCase` classes, `_` prefix for private, 4-space indent, double quotes for strings, type hints on public signatures, `logger = logging.getLogger(__name__)` at module level.

8. `## Git Workflow` -- 3 H3 subsections:
   - `### Branch Naming` -- bullets: `feature/<name>`, `fix/<name>`, `docs/<name>`.
   - `### Commit Messages` -- format `type(scope): short description`; examples drawn from real Phase 14 commits.
   - `### PR Process` -- 1 paragraph: TBD by manager; this section stays minimal until the team formalizes a PR template.

9. `## See Also` -- bullets:
   - CLAUDE.md (Claude-specific instructions; section anchors referenced throughout this doc)
   - docs/ARCHITECTURE.md (system overview)
   - docs/COMPONENT_REFERENCE.md (registry inventory)
   - docs/DEPLOYMENT.md (runtime requirements)
   - docs/v1/patterns/ (detailed authoring guides; landing post-rename in plan 15-09)
   - tests/fixtures/jobs/README.md (pipeline fixture authoring)

ASCII discipline as before. Every cited path must exist; the executor grep-confirms.

CRITICAL: do NOT inline-quote multi-paragraph chunks of CLAUDE.md. The reference pattern is "see CLAUDE.md X section" or "per CLAUDE.md X". One-line phrasings of well-known rules (e.g., "ASCII-only logs") are fine as section headings + the user-memory citation; multi-paragraph copies are forbidden by D-B4.
  </action>
  <verify>
    <automated>test -f docs/CONTRIBUTING.md && head -2 docs/CONTRIBUTING.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/CONTRIBUTING.md)" && grep -qE "^### Rule 1:" docs/CONTRIBUTING.md && grep -qE "^### Rule 10:" docs/CONTRIBUTING.md && grep -qF "BUG-PDC" docs/CONTRIBUTING.md && grep -qF "check_per_module_coverage" docs/CONTRIBUTING.md && grep -qF "run_job_fixture" docs/CONTRIBUTING.md && grep -qF "tests/fixtures/jobs/README.md" docs/CONTRIBUTING.md && lines=$(wc -l < docs/CONTRIBUTING.md) && test "$lines" -ge 200 && test "$lines" -le 500 && echo "OK: 10 rules + Phase-14 evidence + length=$lines"</automated>
  </verify>
  <done>CONTRIBUTING.md created with all 10 rules; Phase 14 BUG citations present; CLAUDE.md referenced by section name; ASCII verified; length 200-500.</done>
</task>

<task type="auto">
  <name>Task 15-04-003: CLAUDE.md non-duplication audit</name>
  <files>(read-only -- compare CONTRIBUTING.md against CLAUDE.md)</files>
  <action>
Confirm D-B4 is honored: CONTRIBUTING.md REFERENCES CLAUDE.md but does NOT copy content. Spot-check by extracting any multi-line block in CONTRIBUTING.md that looks like it might be a CLAUDE.md paste.

```bash
# Extract longer multi-line blocks (>= 5 lines of plain text):
awk '/^```/{f=!f; next} !f && /^[^#-]/ {print NR": "$0}' docs/CONTRIBUTING.md | head -40

# Run a heuristic comparison: any 3-line consecutive sequence that appears verbatim in CLAUDE.md is a likely paste.
# (Quick check, not exhaustive; reviewer reads the diff for confidence.)
```

If a multi-line block from CONTRIBUTING.md appears verbatim in CLAUDE.md, REWORD it as a reference: e.g., `See CLAUDE.md "Error Handling" for the full hierarchy.` rather than pasting the hierarchy.

Capture the audit outcome in plan SUMMARY ("D-B4 audit: no verbatim copy from CLAUDE.md detected").
  </action>
  <verify>
    <automated>echo "manual reviewer audit -- captured in SUMMARY" && test -f docs/CONTRIBUTING.md && echo "OK"</automated>
  </verify>
  <done>CONTRIBUTING.md vs CLAUDE.md audited; no verbatim copy; references-by-section-name confirmed; result captured.</done>
</task>

<task type="auto">
  <name>Task 15-04-004: Commit</name>
  <files>docs/CONTRIBUTING.md</files>
  <action>
Atomic commit per D-E1:

```bash
git add docs/CONTRIBUTING.md
git commit -m "docs(15-04): add docs/CONTRIBUTING.md (10 load-bearing rules)

Encodes the 10 load-bearing project rules per D-C3:
1 ASCII-only / 2 ETLError hierarchy / 3 fix-source-no-fallbacks /
4 atomic commits / 5 registry+abstract dual invariant (Phase 14
BUG-PDC/SWIFT/FIJ evidence) / 6 95% coverage floor / 7 D-C5
dead-code policy / 8 pipeline tests for lifecycle modules /
9 Talend parity non-negotiable / 10 converter JSON FROZEN.

References CLAUDE.md by section name per D-B4. Does NOT
duplicate CLAUDE.md content. References tests/fixtures/jobs/README.md
for pipeline-fixture authoring.

Refs: 15-CONTEXT.md D-A3, D-B4, D-C1, D-C2, D-C3; 15-RESEARCH.md B.3"
```
  </action>
  <verify>
    <automated>git log -1 --pretty=%s | grep -qF "docs(15-04): add docs/CONTRIBUTING.md" && test "$(git diff --stat HEAD~1..HEAD -- src/ CLAUDE.md | wc -l | tr -d ' ')" = "0" && echo "OK: committed; no src/ or CLAUDE.md touch"</automated>
  </verify>
  <done>Single commit landed; no src/ or CLAUDE.md touched; HEAD subject matches.</done>
</task>

</tasks>

<verification_gate>

Plan 15-04 is GREEN when:
1. `docs/CONTRIBUTING.md` exists at `docs/` root.
2. `*Last updated: 2026-05-11*` on line 2.
3. ASCII-only.
4. All 10 numbered rules present (Rule 1 through Rule 10 H3 headings).
5. Rule 5 cites Phase 14 BUG-PDC/SWIFT/FIJ explicitly.
6. Rule 6 references CLAUDE.md Coverage section (does not duplicate) and cites `scripts/check_per_module_coverage.py`.
7. Rule 8 cites `tests/conftest.py:run_job_fixture` and `tests/fixtures/jobs/README.md`.
8. No verbatim multi-paragraph copy from CLAUDE.md.
9. Length 200-500 lines (target 250-400).
10. Single commit landed; no src/ or CLAUDE.md touched.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-04): add docs/CONTRIBUTING.md (10 load-bearing rules)` | `docs/CONTRIBUTING.md` |

(Total: 1 commit.)

</commit_map>
