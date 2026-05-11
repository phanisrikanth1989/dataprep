# Phase 15: Documentation Sweep — Context

**Gathered:** 2026-05-11
**Status:** Ready for research/planning

<domain>
## Phase Boundary

Delete every stale top-level file under `docs/`, write a fresh canonical doc set, and deep-review the `docs/v1/standards/` + 3 sibling `docs/v1/` files (fix stale/wrong content, drop redundant files, possibly rename the standards folder). The 86-file audit directory (`docs/v1/audit/`) is **out of scope** — it moves to Phase 15.1 (Documentation Audit Reconciliation) so each per-component audit file can be reconciled deeply against current source.

**In scope:**
- Delete all 22 top-level `docs/` files (20 .md + 2 .docx) — full nuke, no salvage
- Write 4 fresh canonical docs at `docs/`: `ARCHITECTURE.md`, `COMPONENT_REFERENCE.md`, `CONTRIBUTING.md`, `DEPLOYMENT.md`
- Deep review of `docs/v1/standards/` (8 files: ENGINE_COMPONENT_PATTERN, ENGINE_TEST_PATTERN, CONVERTER_PATTERN, TEST_PATTERN, AUDIT_REPORT_TEMPLATE, MANUAL_COMPONENT_AUTHORING, METHODOLOGY, NEXT_MILESTONE_GUIDE)
- Same deep review for `docs/v1/STANDARDS.md` (1325 lines), `docs/v1/BaseComponent-Info.md`, `docs/v1/talend_to_v1_converter_guide.md`
- AUDIT_REPORT_TEMPLATE and METHODOLOGY are explicit candidates for deletion if redundant — research must evaluate
- Folder rename considered if `standards/` no longer fits post-review content
- Repo root `README.md` does not exist yet — Phase 15 should add a minimal one that points at the 4 canonical docs (lockable during planning)

**Out of scope (deferred or never-touched):**
- **`docs/v1/audit/`** (89 files: 3 cross-cutting + 86 per-component) — **Phase 15.1** owns deep reconciliation against current code
- `CLAUDE.md` (project instructions — load-bearing, not user-facing docs)
- `.planning/`, `.claude/`, `.gemini/` (planning + workflow tooling, not user-facing docs)
- `tests/fixtures/jobs/README.md` (Phase 14 tooling readme for pipeline-test fixtures, stays as-is)
- CI / pre-commit doc-freshness lint (not required this phase; deferred indefinitely)
- Documentation generation tooling (e.g., Sphinx, MkDocs) — Phase 15 ships plain Markdown only
</domain>

<canonical_refs>
## Canonical References (MUST READ before planning)

- `.planning/ROADMAP.md` (Phase 15 success criteria, locked 2026-05-11)
- `.planning/PROJECT.md` (project description, core value, constraints, evolution rules)
- `.planning/REQUIREMENTS.md` (TEST-11/12 closure pattern from Phase 14 — DOCS-01/02 will mirror)
- `CLAUDE.md` (project conventions Phase 15 must encode into CONTRIBUTING.md: ASCII-only logs, fix-source-no-fallbacks, custom exception hierarchy, atomic commits, etc.)
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/STACK.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/CONCERNS.md` (project intel maintained by gsd-map-codebase — direct input to ARCHITECTURE.md and CONTRIBUTING.md)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (test pattern reference: ASCII-only assertions, ETLError subclasses, run_job_fixture)
- `tests/conftest.py` (run_job_fixture, assert_ascii_logs — referenced by ENGINE_TEST_PATTERN if kept)
- `tests/fixtures/jobs/README.md` (pipeline-test fixture authoring guide — referenced by CONTRIBUTING.md, stays as-is)
- `docs/v1/audit/SUMMARY_SCORECARD.md` (deferred to 15.1, but Phase 15's COMPONENT_REFERENCE.md should point at it as the per-component truth source until 15.1 reconciles)
</canonical_refs>

<decisions>
## Decisions

### Scope decisions

- **D-A1: Top-level `docs/` nuke is total.** All 22 files (20 .md + 2 .docx) deleted, no salvage or migration. Fresh canonical docs replace them.
- **D-A2: 4 canonical docs locked at the names from ROADMAP.** `ARCHITECTURE.md`, `COMPONENT_REFERENCE.md`, `CONTRIBUTING.md`, `DEPLOYMENT.md`. Researcher/planner decide internal structure; names are fixed.
- **D-A3: Canonical docs live at `docs/` root** (not `docs/v1/` or `docs/canonical/`). The 4 files are the only top-level entries.
- **D-A4: `docs/v1/audit/` is out of Phase 15 scope.** No file under `docs/v1/audit/` may be modified during Phase 15. The reconciliation work is Phase 15.1.
- **D-A5: `docs/v1/standards/` + 3 sibling files get deep review treatment.** 11 files total: 8 in `docs/v1/standards/` + `docs/v1/STANDARDS.md` + `docs/v1/BaseComponent-Info.md` + `docs/v1/talend_to_v1_converter_guide.md`. Same protocol: cross-check against current code, fix stale content, drop redundant files, possibly rename the standards/ folder if its content no longer matches the name.
- **D-A6: AUDIT_REPORT_TEMPLATE.md and METHODOLOGY.md are explicit deletion candidates.** Research must evaluate whether they still have a consumer post-Phase-14. If no consumer, delete. Same evaluation applies to NEXT_MILESTONE_GUIDE.md (likely stale).

### Anti-scope decisions

- **D-B1: No CI / pre-commit doc-freshness lint.** ROADMAP SC#3 originally required `CI lints stale docs against codebase symbols` — explicitly dropped. Stale-doc detection becomes a manual review concern.
- **D-B2: No documentation generation tooling.** Plain Markdown only. No Sphinx, MkDocs, Docusaurus, or similar. Keeps Phase 15 reversible and avoids tooling lock-in.
- **D-B3: No mass migration of audit/ content into COMPONENT_REFERENCE.md.** Phase 15's COMPONENT_REFERENCE.md is a high-level index that points at `docs/v1/audit/` for per-component depth. Phase 15.1 will reconcile audit content; if needed, COMPONENT_REFERENCE.md can deepen in a future phase.
- **D-B4: CLAUDE.md is not edited by Phase 15.** Phase 14 already established the §Coverage pattern; CLAUDE.md is project-Claude-instructions territory, not user-facing docs. CONTRIBUTING.md may reference CLAUDE.md but does not duplicate its content.

### Content decisions

- **D-C1: All new docs ASCII-only.** No emoji, no smart quotes, no en/em dashes (use `--`). Mirrors the project memory `feedback_ascii_logging` and matches CLAUDE.md / engine code conventions.
- **D-C2: Every new or rewritten doc starts with `*Last updated: YYYY-MM-DD*` line.** No automated freshness check, but the header is mandatory so manual review can spot rot.
- **D-C3: CONTRIBUTING.md must encode the load-bearing project rules.** Including (non-exhaustive): ASCII-only logs and source; custom exception hierarchy (`ETLError` subclasses, never `pytest.raises(Exception)`); fix-source-no-fallbacks (project memory `feedback_fix_source_no_fallbacks`); atomic commits per file (Phase 14 D-F2 / constraint #7); pragma allowlist (D-C3 from Phase 14: `__main__` / `@abstractmethod` / `ImportError` shims only); 95% per-module coverage floor (Phase 14 gate); pipeline fixtures pattern (`run_job_fixture`, `assert_ascii_logs`); BaseComponent abstract methods MUST be implemented (Phase 14 BUG-PDC-002 / BUG-FIJ-002 / BUG-SWIFT-002); registry membership MUST be wired (Phase 14 BUG-PDC-001 / BUG-FIJ-001 / BUG-SWIFT-001).
- **D-C4: ARCHITECTURE.md must include a registry-discipline section.** The systemic disease Phase 14 surfaced (4 components unregistered in `COMPONENT_REGISTRY`, multiple missing `_validate_config`) is a load-bearing constraint of the engine pattern. Document explicitly.
- **D-C5: DEPLOYMENT.md captures Linux + JVM 11+ as the validated runtime.** Cite Phase 14 D-A3 (java_bridge_manager.py measured WITH `-m java` markers, JVM 11+ required on PATH).
- **D-C6: COMPONENT_REFERENCE.md is a registry-driven index.** Generated/maintained from `ETLEngine.COMPONENT_REGISTRY` keys, mapping each component name to: source file path, test file path, Talend-source-component (where applicable), registered status, and a pointer to the corresponding `docs/v1/audit/components/*.md` file (for now — Phase 15.1 reconciles audit content). Generation can be a small script in `scripts/` (committed) or an inline reference table (decided by planner).

### Folder structure decisions

- **D-D1: `docs/v1/standards/` folder may be renamed.** Research must evaluate. Acceptable alternative names if rename happens: `docs/v1/patterns/`, `docs/v1/conventions/`. Decision deferred to planner based on what survives the deep review.
- **D-D2: The 3 sibling `docs/v1/` files (`STANDARDS.md`, `BaseComponent-Info.md`, `talend_to_v1_converter_guide.md`) may be moved into the standards/ folder.** Researcher/planner decides based on content overlap.
- **D-D3: Repo root `README.md` added by Phase 15.** Minimal: project title, one-paragraph description, link to `docs/ARCHITECTURE.md` as the entry point, link to `CLAUDE.md` for Claude-specific instructions. No expansion beyond the 4 canonical docs.

### Atomicity / process decisions (mirror Phase 14)

- **D-E1: Atomic commits.** One logical change per commit. Examples: "remove top-level docs/ batch", "add docs/ARCHITECTURE.md", "update docs/v1/standards/ENGINE_COMPONENT_PATTERN.md fix stale fixture path", etc. No bundled "rewrite all docs" commits.
- **D-E2: Per-file verification.** Every doc rewritten or fixed gets a manual content check (claims grounded in current code via grep/file-read). If a doc cites a function/class/file, that reference is verified to exist before the commit lands. Mirrors project memory `feedback_verify_audit_claims`.
- **D-E3: No new defensive shims in code from doc work.** Phase 15 is doc-only. If a doc references a missing or buggy feature, fix the doc to match reality (or, for true production bugs, file a follow-up BUG entry; do NOT patch source in a doc-sweep phase). Mirrors project memory `feedback_fix_source_no_fallbacks` interpretation: scope discipline.

### Phase 15.1 setup

- **D-F1: Phase 15.1 added to ROADMAP.md** with 4 success criteria scoping audit reconciliation. Created 2026-05-11 alongside Phase 15 swap.
- **D-F2: 15.1 ownership.** Same Claude-driven model as Phase 15 (not manager-led). Audit reconciliation requires reading code + audit doc and updating doc to match — pure Claude work.
</decisions>

<specifics>
## Specifics

- 124 user-facing doc files in repo (excluding `.planning/`, `.claude/`, `.gemini/` tooling). Phase 15 surface area is ~33 files (22 top-level deletes + 11 deep-review). Phase 15.1 owns the remaining 89.
- Top-level `docs/` rot files explicitly named in ROADMAP SC#1: `FINAL_SUMMARY.md`, `IMPLEMENTATION_COMPLETE.md`, `LAYOUT_UPDATE.md`, all `UI_*` files. These are exemplars, not the only deletes — D-A1 nukes all 22.
- Two `.docx` files: `docs/Demo Talking Points.docx`, `docs/BaseComponent Info.docx`. Both deleted (D-A1). Markdown version of BaseComponent info already exists at `docs/v1/BaseComponent-Info.md` — that one stays for deep review (D-A5).
- Heaviest existing user docs (line counts for context, NOT a quality signal): `docs/v1/audit/CROSS_CUTTING_ISSUES.md` (2154), `docs/CODE_REFERENCE.md` (1416 — DELETE per D-A1), `docs/v1/STANDARDS.md` (1325 — deep review per D-A5), `docs/ARCHITECTURE.md` (812 — DELETE per D-A1, rewrite fresh).
- The 86-component audit dir breakdown: aggregate (2), context (1), control (9), database (11), file (25), iterate (2), transform (36). Phase 15.1 scope.
- Phase 14 closed ~200-250 cross-cutting issues out of 928 originally surveyed. SUMMARY_SCORECARD and CROSS_CUTTING_ISSUES are heavily stale post-Phase-14 — 15.1 target.
- New requirement IDs for Phase 15 / 15.1: DOCS-01 (Phase 15 canonical doc set in place), DOCS-02 (Phase 15 standards/ deep review complete), DOCS-03 (Phase 15.1 audit reconciliation complete). Final wording set by planner.
</specifics>

<deferred>
## Deferred Ideas

- **Documentation generation tooling** (Sphinx, MkDocs, Docusaurus). Defer indefinitely — plain Markdown is enough for now.
- **CI / pre-commit stale-doc lint** (`scripts/check_doc_freshness.py` greping doc files for src/v1/engine symbols). Defer indefinitely — D-B1.
- **Auto-generated COMPONENT_REFERENCE.md.** A small `scripts/gen_component_reference.py` that walks `COMPONENT_REGISTRY` and emits Markdown is implementable but not required for Phase 15 — planner decides between inline reference vs generated.
- **Phase 14 systemic registry/abstract-method audit.** A repo-wide sweep confirming every component class is in `COMPONENT_REGISTRY` and implements every BaseComponent abstract. Phase 14 patched 4 known instances (PDC, both SWIFT, FIJ). Defer to a separate Phase 15.2 or fold into manager-led Phase 16 startup tasks — captured in CONTRIBUTING.md as a rule but not actively audited in Phase 15.
- **API reference auto-generation** (docstring extraction). Plain Markdown only this phase.
- **Multi-language docs** (e.g., translated CONTRIBUTING). Out of scope.
</deferred>

<code_context>
## Code Context (scout findings)

- `docs/` directory layout: 22 top-level files (rot layer), 89 in `docs/v1/audit/` (deferred to 15.1), 11 in `docs/v1/standards/` + sibling (deep review), 2 `.docx` (deleted).
- `.planning/codebase/` exists with 7 maps maintained by gsd-map-codebase. These should be the ground truth input for ARCHITECTURE.md — Phase 15 doesn't regenerate them, it consumes them.
- `tests/fixtures/jobs/README.md` is the only doc inside `tests/` — Phase 14 artifact, load-bearing for pipeline tests, stays as-is and is referenced by CONTRIBUTING.md.
- Repo has no `README.md` at root (D-D3 adds one).
- `CLAUDE.md` is comprehensive and authoritative for Claude — CONTRIBUTING.md should NOT duplicate it; instead CONTRIBUTING.md references CLAUDE.md and adds human-facing conventions (commit format, PR process, test-first protocol).
- Phase 14 added `scripts/check_per_module_coverage.py` — example of the "wired and reproducible" tooling pattern. CONTRIBUTING.md should mention it.
- Pre-existing `docs/ARCHITECTURE.md` (812 lines) is stale — will be deleted; planner reads `.planning/codebase/ARCHITECTURE.md` as the rewrite source.
</code_context>

---
*Phase 15 context — gathered 2026-05-11 — ready for research/planning*
