---
phase: 15
plan: 4
slug: contributing-canonical-doc
subsystem: docs
tags: [docs, contributing, phase-15]
requires: [15-01]
provides: [DOCS-01-CONTRIBUTING]
affects: [docs/CONTRIBUTING.md]
tech_stack_added: []
patterns: [canonical-doc, rules-encoded, references-not-copies]
key_files_created:
  - docs/CONTRIBUTING.md
key_files_modified: []
decisions:
  - "Cited Phase 14 BUG-PDC/SWIFT/FIJ in Rule 5 to anchor the registry+abstract invariant in real Phase 14 evidence."
  - "Rule 6 references CLAUDE.md Coverage section by name and cites scripts/check_per_module_coverage.py without duplicating the paste-runnable command."
  - "Rule 8 cites tests/conftest.py::run_job_fixture and tests/fixtures/jobs/README.md; mock-only tests called out as the cautionary tale."
  - "docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md referenced as the post-rename landing for the authoring contract (plan 15-09); docs/v1/STANDARDS.md cited as the predecessor."
  - "PR Process section kept minimal (TBD by manager) per plan 15-04 out_of_scope guidance."
metrics:
  duration_minutes: 8
  tasks_completed: 4
  files_changed: 1
  lines_added: 287
  commits: 1
completed_date: 2026-05-11
---

# Phase 15 Plan 04: docs/CONTRIBUTING.md Summary

One-liner: Authored `docs/CONTRIBUTING.md` (287 lines) encoding the 10 load-bearing project rules per D-C3, citing Phase 14 BUG-PDC/SWIFT/FIJ as Rule 5 evidence and referencing CLAUDE.md by section name per D-B4 (no content duplication).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 15-04-001 | Verify CLAUDE.md section anchors | (read-only verification) | -- |
| 15-04-002 | Author docs/CONTRIBUTING.md | b83e375 | docs/CONTRIBUTING.md |
| 15-04-003 | CLAUDE.md non-duplication audit | (read-only audit) | -- |
| 15-04-004 | Commit | b83e375 (same commit) | docs/CONTRIBUTING.md |

Single atomic commit per the plan's commit_map (D-E1).

## Verification Gate

All ten gates from plan 15-04 verification_gate pass:

1. `docs/CONTRIBUTING.md` exists at `docs/` root -- VERIFIED.
2. `*Last updated: 2026-05-11*` on line 2 -- VERIFIED via `sed -n '1,2p'`.
3. ASCII-only -- VERIFIED via `grep -P '[^\x00-\x7F]'` returning empty.
4. All 10 numbered rules present (Rule 1 through Rule 10 as `### Rule N:` H3 headings) -- VERIFIED.
5. Rule 5 cites Phase 14 BUG-PDC, BUG-SWIFT, BUG-FIJ explicitly -- VERIFIED at line 75-76 (BUG-PDC-001/002, BUG-SWIFT-001..005, BUG-FIJ-001/002).
6. Rule 6 references CLAUDE.md "Coverage" section (does not duplicate) and cites `scripts/check_per_module_coverage.py` -- VERIFIED at lines 88-89.
7. Rule 8 cites `tests/conftest.py::run_job_fixture` and `tests/fixtures/jobs/README.md` -- VERIFIED at lines 114 and 121.
8. No verbatim multi-paragraph copy from CLAUDE.md -- VERIFIED via Python 3-line consecutive substring audit (Task 15-04-003).
9. Length 287 lines -- within target 250-400, within outer bound 200-500.
10. Single commit landed (`b83e375`); no src/ or CLAUDE.md touched -- VERIFIED via `git diff --stat HEAD~1..HEAD -- src/ CLAUDE.md` returning empty.

## CLAUDE.md Anchor Verification (Task 15-04-001)

CLAUDE.md was inspected before authoring; the following section anchors used in CONTRIBUTING.md are confirmed present in CLAUDE.md:

- `## Error Handling` (cited from Rule 2)
- `## Logging` (cited from Style section)
- `## Coverage` (line 160 of CLAUDE.md; cited from Rule 6 and Tests > Coverage)
- `## Conventions` and child anchors (Naming Patterns, Code Style, Import Organization, Comments, Function Design, Module Design) -- cited from Style section
- `## Architecture` and `## Key Abstractions` (cited from Workflow > Authoring a new component)
- `## Project` / Core Value (cited from Rule 9 Talend parity)

`scripts/check_per_module_coverage.py` confirmed present and is the actual gate referenced from CLAUDE.md "Coverage" (CLAUDE.md line 171). Zero discrepancies; no anchor downgrades required.

`tests/fixtures/jobs/README.md` confirmed present. `tests/conftest.py` confirmed exports `run_job_fixture` (line 109) and `assert_ascii_logs` (line 188).

## D-B4 Non-Duplication Audit (Task 15-04-003)

Result: **PASS -- no verbatim copy from CLAUDE.md detected.**

Method: Python 3-line consecutive substring audit -- for every 3-line window of CONTRIBUTING.md (filtered to non-trivial lines >= 30 chars, total window >= 120 chars), checked whether all three lines appeared verbatim in CLAUDE.md. Zero hits.

CONTRIBUTING.md cites CLAUDE.md 17 times by section name. The citation pattern is "see CLAUDE.md `<section>`" or "per CLAUDE.md `<section>`" -- never inlined content.

Single-line phrases of well-known rules (e.g., "ASCII-only logs" as a section heading) overlap conceptually with CLAUDE.md but are reworded; they do not constitute D-B4 duplication.

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None. docs/CONTRIBUTING.md is a complete canonical doc; the forward-pointers to docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md, docs/ARCHITECTURE.md, docs/COMPONENT_REFERENCE.md, and docs/DEPLOYMENT.md are intentional placeholders for sibling Phase 15 plans (15-05, 15-06, 15-09, etc.) -- they are documented as "landing later in Phase 15" / "landing in plan 15-09", which the plan explicitly authorizes.

## Threat Flags

None. Doc-only change; zero security surface introduced.

## Self-Check

- File exists: `docs/CONTRIBUTING.md` (287 lines) -- FOUND.
- Commit exists: `b83e375` -- FOUND in `git log`.
- No src/ touch: VERIFIED (`git diff --stat HEAD~1..HEAD -- src/ CLAUDE.md` empty).
- All 10 Rule headings present: VERIFIED.
- All required citations present (BUG-PDC, BUG-SWIFT, BUG-FIJ, check_per_module_coverage, run_job_fixture, tests/fixtures/jobs/README.md, patterns/MANUAL_COMPONENT_AUTHORING): VERIFIED.

## Self-Check: PASSED
