---
phase: 15
plan: 6
slug: root-readme
subsystem: documentation
tags: [docs, readme, navigation]
status: complete
completed: 2026-05-11
requires: [15-01]
provides: [repo-root-entry-point]
affects: [README.md]
tech_stack_added: []
tech_stack_patterns: []
key_files_created:
  - README.md
key_files_modified: []
decisions:
  - "Header placed on line 2 directly under H1 with no blank line between (per D-C2 strict verify)"
  - "License section kept as one-line placeholder per planner allowance"
  - "Quickstart paths cite real CLI entry points: converter.py:516 __main__, engine.py:285 __main__"
metrics:
  duration_minutes: ~5
  task_count: 3
  files_changed: 1
  commits: 1
---

# Phase 15 Plan 6: Root README.md Summary

*Last updated: 2026-05-11*

Minimal repo-root `README.md` added pointing at the 4 canonical docs (ARCHITECTURE, COMPONENT_REFERENCE, CONTRIBUTING, DEPLOYMENT) plus CLAUDE.md, with 2 short Quickstart CLI examples (converter + engine).

## What Changed

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Confirm no pre-existing README.md at root | done | (read-only) | -- |
| 2 | Author README.md | done | (squashed into task 3) | README.md |
| 3 | Atomic commit | done | `7fb50f7` | README.md |

Tasks 2 and 3 were authored separately but landed as a single atomic commit per the plan's `<commit_map>` (1 commit total). The plan explicitly required a single commit covering the create-and-author together.

## Verification

All `<verification_gate>` checks pass:

1. `README.md` exists at REPO ROOT (not under `docs/`).
2. `*Last updated: 2026-05-11*` on line 2 (directly under `# DataPrep` on line 1, no blank line between -- required to satisfy `head -2 README.md | grep -qF`).
3. ASCII-only: `grep -nP '[^\x00-\x7F]' README.md` returns zero lines.
4. All 5 required links present:
   - `docs/ARCHITECTURE.md`
   - `docs/COMPONENT_REFERENCE.md`
   - `docs/CONTRIBUTING.md`
   - `docs/DEPLOYMENT.md`
   - `CLAUDE.md`
5. 2 Quickstart fenced bash blocks present (converter + engine).
6. Length: 43 lines (within the 20-100 plan bound and the 30-50 target).
7. Single commit landed; `git diff --stat HEAD~1..HEAD -- src/ CLAUDE.md` returns zero lines.
8. Zero deletions in the commit.

## CLI Quickstart Grounding (D-E2)

Quickstart examples grep-confirmed against current source:

- **Converter** at `src/converters/talend_to_v1/converter.py:516` -- `if __name__ == "__main__":` block with usage string `python -m src.converters.talend_to_v1.converter <input.item> [output.json]` (line 522).
- **Engine** at `src/v1/engine/engine.py:285` -- `if __name__ == '__main__':` block using argparse with `job_config` positional + optional `--context_param KEY=VALUE` (lines 291-298).

Both CLI invocations in the README are paste-runnable from project root.

## Decisions Made

1. **Header on line 2 with no blank line.** The plan's example showed a blank line between `# DataPrep` and `*Last updated: 2026-05-11*` (which would put the header on line 3), but the plan's verify gate (`head -2 README.md | grep -qF`) and the critical_constraints (`*Last updated: 2026-05-11*` on line 2) require the header within the first 2 lines. Resolved in favor of the explicit constraint: no blank line between H1 and the header.
2. **License section.** Kept as a single placeholder line ("License details TBD -- internal.") per the plan's allowance to either reduce or omit the License section. Single-line keeps the README's footer structurally complete.
3. **Java bridge note placement.** The JVM 11+ note lives inside `## Quickstart` (not as a separate caveat heading) to keep the navigational README tight; full deployment detail lives in `docs/DEPLOYMENT.md` per D-D3 (no expansion beyond the 4 canonical docs).

## Deviations from Plan

None. Plan executed exactly as written. The one nuance (header on line 2 with no blank line) is a literal reading of the verify gate, not a deviation.

## Known Stubs

None.

## Threat Flags

None. Doc-only change with zero `src/` impact.

## Self-Check: PASSED

- `README.md` exists: FOUND
- Commit `7fb50f7` exists: FOUND in `git log --oneline -1` (subject `docs(15-06): add root README.md (minimal per D-D3)`)
- All link patterns present in the file (verified by grep)
- ASCII check passes (zero non-ASCII bytes)
- Length 43 lines, within 20-100 plan bound and 30-50 target
- No src/ or CLAUDE.md touched

---
*Plan 15-06 closed 2026-05-11*
