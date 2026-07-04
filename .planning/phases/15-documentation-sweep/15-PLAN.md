---
phase: 15
slug: documentation-sweep
plan: phase-summary
type: execute
status: ready
created: 2026-05-11
requirements: [DOCS-01, DOCS-02]
---

# Phase 15 -- Documentation Sweep (Phase Plan)

*Last updated: 2026-05-11*

> Roll-up across all 10 plans. Each individual plan lives in `15-NN-*.md` files. Read `15-CONTEXT.md` and `15-RESEARCH.md` before executing any plan. Doc-only phase per D-E3 -- NO `src/` modifications anywhere in this phase. The 86-file `docs/v1/audit/` directory is OFF LIMITS (D-A4) and is owned by Phase 15.1.

## Phase Objective

Replace the rotted top-level `docs/` (22 stale files) with a fresh 4-doc canonical set at `docs/` root (`ARCHITECTURE.md`, `COMPONENT_REFERENCE.md`, `CONTRIBUTING.md`, `DEPLOYMENT.md`) plus a minimal repo-root `README.md`. Deep-review the 11 standards-zone files (`docs/v1/standards/` 8 + `docs/v1/STANDARDS.md` + `docs/v1/BaseComponent-Info.md` + `docs/v1/talend_to_v1_converter_guide.md`): drop 4 (STANDARDS, METHODOLOGY, AUDIT_REPORT_TEMPLATE, NEXT_MILESTONE_GUIDE), fix 7 (ENGINE_COMPONENT_PATTERN, ENGINE_TEST_PATTERN, CONVERTER_PATTERN, TEST_PATTERN, MANUAL_COMPONENT_AUTHORING, BaseComponent-Info, talend_to_v1_converter_guide), rename `docs/v1/standards/` -> `docs/v1/patterns/`, and move BaseComponent-Info.md into patterns/. Encode the Phase 14 systemic registry+abstract-method discipline in `docs/CONTRIBUTING.md` and `docs/ARCHITECTURE.md`. Every claim in every doc must be verified against current code (D-E2). Every commit atomic per D-E1.

## Goal-Backward Truths

1. `ls docs/*.md` returns exactly 5 entries: `ARCHITECTURE.md`, `COMPONENT_REFERENCE.md`, `CONTRIBUTING.md`, `DEPLOYMENT.md` (and any pre-existing root-level entries that survived -- expected: only these 4 plus nothing else after the nuke).
2. `ls docs/` (top-level files only) shows NO `.docx` files and NO stale `.md` (FINAL_SUMMARY, IMPLEMENTATION_COMPLETE, LAYOUT_UPDATE, UI_*, etc.) -- the 22-file nuke is total.
3. `ls /Users/aarun/Workspace/Projects/dataprep/README.md` exists at repo root with minimal content per D-D3.
4. `ls docs/v1/patterns/` exists and contains: `ENGINE_COMPONENT_PATTERN.md`, `ENGINE_TEST_PATTERN.md`, `CONVERTER_PATTERN.md`, `TEST_PATTERN.md`, `MANUAL_COMPONENT_AUTHORING.md`, `BaseComponent-Info.md` (6 files).
5. `ls docs/v1/standards/` does NOT exist (renamed away).
6. `ls docs/v1/`: `patterns/` directory + `audit/` directory + `talend_to_v1_converter_guide.md` (3 entries, no STANDARDS.md, no BaseComponent-Info.md at this level).
7. Every new or rewritten doc starts with the line `*Last updated: 2026-05-11*` (D-C2).
8. `grep -P "[^\x00-\x7F]" <each new/edited doc>` returns zero lines (ASCII-only per D-C1).
9. No file under `docs/v1/audit/` was modified during Phase 15 (D-A4); `git log --oneline -- docs/v1/audit/` shows no Phase 15 commit subjects.
10. `git diff --stat <merge-base>..HEAD -- src/` shows zero changed lines (D-E3; doc-only phase).
11. The Phase 14 coverage gate still exits 0: `python -m pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=json && python scripts/check_per_module_coverage.py coverage.json --floor 95` (regression guard).
12. `15-VERIFICATION.md` exists with per-doc claim-verification log; `15-PHASE-SUMMARY.md` exists with retrospective; broken-cross-reference inventory captured for Phase 15.1 handoff.
13. REQUIREMENTS.md lists `DOCS-01` and `DOCS-02` marked `[x]` Complete; ROADMAP.md Phase 15 marked Complete with plan list filled in.
14. STATE.md records Phase 15 closure.

## Plan Inventory (10 plans, ordered by execution wave)

| Plan | Title | Wave | Depends on | Files / scope | Est. commits |
|------|-------|-----:|------------|---------------|-------------:|
| 15-01 | Nuke top-level `docs/` (22 files) | 0 | -- | Delete all top-level `docs/*.md` + 2 `.docx` files (single batch commit per discussion's example) | 1 |
| 15-02 | Canonical doc -- `docs/ARCHITECTURE.md` | 1 | 15-01 | Fresh write from `.planning/codebase/ARCHITECTURE.md` + STRUCTURE + STACK + INTEGRATIONS + Phase 14 PHASE-SUMMARY; corrects stale `COMPONENT_REGISTRY` static-dict claim; registry-discipline section (D-C4) | 1 |
| 15-03 | Canonical doc -- `docs/COMPONENT_REFERENCE.md` | 1 | 15-01 | Registry-driven inline index sourced from `src/v1/engine/component_registry.py` REGISTRY + per-component file paths; explicit registration status column; pointer to `docs/v1/audit/components/*.md` (D-B3) | 1 |
| 15-04 | Canonical doc -- `docs/CONTRIBUTING.md` | 1 | 15-01 | Encodes 10 load-bearing rules from D-C3 + Phase 14 lessons (registry+abstract, pipeline tests, fix-source, atomic commits, pragma allowlist, 95% floor, ASCII-only); references CLAUDE.md by section name, does NOT duplicate (D-B4) | 1 |
| 15-05 | Canonical doc -- `docs/DEPLOYMENT.md` | 1 | 15-01 | Linux + JVM 11+ validated runtime (D-C5); Python deps + pyproject pins; Java bridge build (mvn package); Oracle modes; coverage gate paste-runnable | 1 |
| 15-06 | Root `README.md` | 1 | 15-01 | Minimal: title + 1-paragraph description + Quickstart (2 short CLI examples) + links to the 4 canonical docs + CLAUDE.md (D-D3; researcher Option B accepted -- still tight) | 1 |
| 15-07 | standards/ DROP set -- delete 4 redundant files | 2 | 15-01 | `git rm docs/v1/STANDARDS.md`, `docs/v1/standards/METHODOLOGY.md`, `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md`, `docs/v1/standards/NEXT_MILESTONE_GUIDE.md`. Capture broken-cross-reference inventory in plan SUMMARY for Phase 15.1 handoff (84 audit/ files reference `docs/v1/STANDARDS.md` per researcher grep; need 15.1 fixup) | 4 |
| 15-08 | standards/ KEEP+FIX set -- fix 6 surviving files in place | 2 | 15-01, 15-07 | Per-file fixes (still under `docs/v1/standards/` until 15-09 renames): ENGINE_COMPONENT_PATTERN.md (line 3 TBD -> real ref), ENGINE_TEST_PATTERN.md (add Phase 14 pipeline-pattern section + run_job_fixture + 95% floor), CONVERTER_PATTERN.md (header date), TEST_PATTERN.md (header date), MANUAL_COMPONENT_AUTHORING.md (add Rule 13 registry+abstract; update header date), BaseComponent-Info.md (mark G-01..G-05/G-10/G-12 FIXED; explicit OPEN markers on remaining gaps); plus `docs/v1/talend_to_v1_converter_guide.md` (header date + verify lines 120-528 against current code) | 7 |
| 15-09 | folder rename + relocations | 2 | 15-07, 15-08 | `git mv docs/v1/standards docs/v1/patterns`; `git mv docs/v1/BaseComponent-Info.md docs/v1/patterns/BaseComponent-Info.md`; verify no broken intra-repo references introduced by the rename (audit/ refs to `docs/v1/STANDARDS.md` already enumerated in 15-07 SUMMARY; `docs/v1/talend_to_v1_converter_guide.md` STAYS at `docs/v1/`) | 2 |
| 15-10 | closeout | 3 | all of 15-01..15-09 | REQUIREMENTS.md adds DOCS-01 + DOCS-02 (Complete); ROADMAP.md Phase 15 marked Complete + plan list filled; STATE.md records closure; `15-VERIFICATION.md` (per-doc claim-verification log, broken-reference inventory, Phase 14 gate regression-check evidence); `15-PHASE-SUMMARY.md` (retrospective); final manual checkpoint reviews the inventory and confirms no `src/` was touched | 5 |

**Total estimated commits:** ~24.

## Wave Structure (cross-plan)

- **Wave 0:** Plan 15-01 nukes the top-level `docs/` directory. All other plans depend on 15-01 (waiting for the slate to be clean prevents conflicts with any of the 22 stale top-level filenames).
- **Wave 1:** Plans 15-02, 15-03, 15-04, 15-05, 15-06 (the 4 canonical docs + root README) all land in parallel. Zero `files_modified` overlap among them. Each file is freshly authored from source-of-truth inputs.
- **Wave 2:** Plans 15-07 (DROPs), 15-08 (KEEP+FIX), 15-09 (rename + move). 15-09 depends on BOTH 15-07 (the dropped files are gone) AND 15-08 (the surviving files have their per-file fixes landed BEFORE the rename, so git history is clean). 15-07 and 15-08 can run in parallel because they touch disjoint files (the DROP set vs the KEEP+FIX set).
- **Wave 3:** Plan 15-10 closeout. Depends on every prior plan landing.

Implicit dependency check (same-wave file overlap): Wave 1 plans write disjoint paths (`docs/ARCHITECTURE.md`, `docs/COMPONENT_REFERENCE.md`, `docs/CONTRIBUTING.md`, `docs/DEPLOYMENT.md`, `README.md`). Wave 2 plans 15-07 (4 deletes) and 15-08 (7 edits in place) have zero file overlap; 15-09 (rename) needs both 15-07 and 15-08 done so all final-state moves happen on the post-fix tree.

## Cross-Cutting Constraints (apply to every plan)

1. **Doc-only phase (D-E3).** No `src/` changes. If a doc claim contradicts current code, FIX THE DOC, do NOT patch source. If a doc references a real production bug, file a `BUG-...` follow-up note in the plan SUMMARY; do NOT add defensive shims in this phase.
2. **ASCII-only (D-C1).** No emoji, no smart quotes, no en/em dashes; use `--`. Verify via `grep -nP "[^\x00-\x7F]" <new_file>` returning zero lines.
3. **Mandatory header (D-C2).** Every new or rewritten doc starts with `*Last updated: 2026-05-11*` on line 2 (after the H1 title line).
4. **Verify-before-claim (D-E2).** Every reference to a class / function / file / line in a doc MUST be verified to exist via grep/file-read BEFORE the commit lands. Record claim-verification evidence in `15-VERIFICATION.md` (plan 15-10).
5. **Atomic commits (D-E1).** One logical change per commit. Plan 15-01 is the only multi-file commit (the nuke batch) -- explicitly allowed per the planner-discussion guidance. Each canonical doc is its own commit. Each KEEP+FIX is its own commit. Each DROP is its own commit. Rename + move are separate commits.
6. **No CLAUDE.md edits (D-B4).** Out of scope. CONTRIBUTING.md references CLAUDE.md by section name; does not copy content.
7. **No `docs/v1/audit/` edits (D-A4).** Out of scope. Phase 15.1 owns reconciliation. If the planner discovers cross-references from `docs/v1/audit/**` to a Phase-15-dropped file (e.g., 84 audit/ files reference `docs/v1/STANDARDS.md`), the inventory is captured for 15.1 handoff in 15-07's plan SUMMARY -- NOT fixed in Phase 15.
8. **No CI / tooling (D-B1, D-B2).** No `scripts/check_doc_freshness.py`, no GitHub Actions, no Sphinx / MkDocs / Docusaurus. Plain Markdown only.
9. **REGISTRY truth source.** The engine REGISTRY lives in `src/v1/engine/component_registry.py` (decorator-based) and is imported into `src/v1/engine/engine.py` at line 18 (`from .component_registry import REGISTRY`). The old `ETLEngine.COMPONENT_REGISTRY` static-dict class attribute NO LONGER EXISTS. Every Phase 15 doc that mentions the registry MUST cite the live decorator pattern, not the stale static dict. `.planning/codebase/ARCHITECTURE.md` and `.planning/codebase/CONVENTIONS.md` still carry the stale static-dict claim -- DO NOT TRUST these maps in isolation (see RESEARCH.md C.5).
10. **Encode the Phase 14 systemic lesson.** Every `BaseComponent` subclass MUST be decorated with `@REGISTRY.register("PascalName", "tTalendName")` AND implement `_validate_config()`. Engine silently drops unregistered classes ("Unknown component type" warning at runtime); ABC refuses instantiation of classes missing `_validate_config`. Phase 14 closed 4 dual-bug instances (BUG-PDC-001/002, BUG-SWIFT-001/002, BUG-FIJ-001/002 + 3 more SWIFT bugs). This rule MUST appear in `docs/ARCHITECTURE.md` (registry-discipline section) and `docs/CONTRIBUTING.md` (Rule 5).
11. **Per-doc verification command.** Every plan that creates or modifies a doc gates on a grep-based verification step in `<verify>`: (a) `grep -nP "[^\x00-\x7F]" <file>` returns zero lines (ASCII check), (b) `grep -F "*Last updated: 2026-05-11*" <file>` returns the header line, (c) every cited class / file path / function name is grep-confirmed to exist in `src/` (per-file claims listed in each plan task).
12. **Phase 14 coverage gate regression check.** Closeout (15-10) runs the Phase 14 gate to confirm no Phase 15 commit touched `src/`: `python -m pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=json && python scripts/check_per_module_coverage.py coverage.json --floor 95` MUST exit 0. If it fails, a Phase 15 commit accidentally modified source -- revert.

## Open Issues for Plan-Checker

1. **Researcher Section D open-question resolution (planner discretion exercised):**
   - D.1 NEXT_MILESTONE_GUIDE.md: DELETE (per `<open_questions_resolution>` note; git history preserves it; no live consumer).
   - D.2 METHODOLOGY + AUDIT_REPORT_TEMPLATE: DELETE in Phase 15 (per `<open_questions_resolution>` note; broken `docs/v1/audit/` cross-references captured in 15-07 SUMMARY as Phase 15.1 handoff -- 15.1's job is to reconcile audit/ against current reality, including resurrecting methodology from git if needed).
   - D.3 COMPONENT_REFERENCE.md: INLINE TABLE (per `<open_questions_resolution>`; D-B2 forbids doc-gen tooling; an inline reference table is the minimal-footprint choice; an optional `scripts/gen_component_reference.py` is captured as a deferred follow-on -- NOT in Phase 15 scope).
   - D.4 folder rename target: `patterns/` (researcher recommendation; matches surviving content; mirrors existing converter "pattern" vocabulary).
   - D.5 BaseComponent-Info "Gaps" section: KEEP with strike-through + explicit OPEN markers (per `<open_questions_resolution>`; preserves historical record + tells contributors which gaps are still live).
   - D.6 root README.md: MINIMAL (D-D3 locks this; planner adopts researcher Option-B-spirit-of-minimal -- title + paragraph + 2 short Quickstart examples + 4 doc links + CLAUDE.md link, ~30-50 lines).
   - D.7 `talend_to_v1_converter_guide.md` location: STAYS at `docs/v1/` (per `<open_questions_resolution>`; different audience from `docs/v1/patterns/` which is contributor-facing; this guide is external-consumer-facing).

2. **Researcher Assumption A1 verified during planning:** Cross-references from `docs/v1/audit/**` to the 4 DROP-candidate files DO EXIST. Confirmed via `grep -rln "STANDARDS\.md\|/standards/" docs/v1/audit/` returning ~84 files. Researcher's downgrade trigger ("If A1 grep returns any references, downgrade DROP to DEFER-TO-15.1") is OVERRIDDEN by user `<open_questions_resolution>` D.2 explicit instruction: delete in Phase 15, capture the broken-reference inventory in 15-07 SUMMARY for Phase 15.1 reconciliation handoff. Phase 15.1's scope is exactly this kind of audit/ reconciliation work.

3. **Stale `.planning/codebase/*.md` maps:** The codebase maps were last regenerated 2026-04-14 and still carry the deprecated `ETLEngine.COMPONENT_REGISTRY` static-dict claim (RESEARCH.md C.5). Planner / executor MUST cross-check load-bearing claims against live source files: `src/v1/engine/engine.py` (lines 18, 140), `src/v1/engine/component_registry.py` (decorator-based REGISTRY), `src/v1/engine/base_component.py` (lifecycle docstring lines 1-50). Codebase maps are a *starting point*, not authority.

4. **DOCS-01 / DOCS-02 final wording:** Captured in 15-10 closeout task (REQUIREMENTS.md update). Final wording follows the user-provided phase_requirements language exactly; closeout flips both to `[x] Complete`.

5. **Pre-existing docs/v1/audit/ deep-rot:** Phase 15 does NOT touch audit/. The 86 component audit files and 3 cross-cutting summary files are heavily stale post-Phase-14 (~200-250 cross-cutting issues closed). Phase 15.1 owns reconciliation. Phase 15 only points at `docs/v1/audit/components/*.md` from `docs/COMPONENT_REFERENCE.md` as the per-component truth source pending 15.1 cleanup.

6. **Phase 14 gate regression guard:** Plan 15-10 runs the gate as the FINAL verification step before manual checkpoint. If gate fails, the failing Phase 15 commit accidentally touched source -- revert before closing. (Expected: gate passes cleanly because Phase 15 is doc-only by D-E3.)

## Final Verification Gate (closeout, Plan 15-10)

```bash
# Per-doc ASCII + header check (run from project root for each created/modified doc):
for f in docs/ARCHITECTURE.md docs/COMPONENT_REFERENCE.md docs/CONTRIBUTING.md docs/DEPLOYMENT.md README.md \
         docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md docs/v1/patterns/ENGINE_TEST_PATTERN.md \
         docs/v1/patterns/CONVERTER_PATTERN.md docs/v1/patterns/TEST_PATTERN.md \
         docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md docs/v1/patterns/BaseComponent-Info.md \
         docs/v1/talend_to_v1_converter_guide.md; do
  grep -nP "[^\x00-\x7F]" "$f" && echo "FAIL ASCII: $f" && exit 1
  grep -qF "*Last updated: 2026-05-11*" "$f" || { echo "FAIL HEADER: $f"; exit 1; }
done

# Inventory check:
test ! -e docs/v1/standards && echo "OK: standards/ renamed" || echo "FAIL: standards/ still present"
test -d docs/v1/patterns && echo "OK: patterns/ exists" || echo "FAIL: patterns/ missing"
test -f README.md && echo "OK: root README" || echo "FAIL: no root README"

# Phase 14 coverage gate (regression guard -- src/ untouched):
rm -f .coverage* coverage.json && python -m pytest tests/ \
  -m "not oracle" -n auto \
  --cov=src/v1/engine --cov=src/converters \
  --cov-report=term-missing --cov-report=json -q \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected: all checks PASS, exit 0, gate prints `PASS: all 181 in-scope modules at >= 95.0% line coverage`.

---
*Phase 15 plan summary -- gathered 2026-05-11 -- ready for execution post-approval*
