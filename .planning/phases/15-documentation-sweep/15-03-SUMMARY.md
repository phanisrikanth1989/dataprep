---
phase: 15
plan: 3
slug: component-reference-canonical-doc
subsystem: docs
tags: [docs, component-reference, registry, phase-14-fixes]
requires:
  - 15-01 (top-level docs/ nuke completed)
provides:
  - docs/COMPONENT_REFERENCE.md (registry-driven inline index)
affects:
  - docs/COMPONENT_REFERENCE.md (created)
tech_stack:
  added: []
  patterns:
    - "Inline registry-driven reference table (D-C6 + planner D.3 -> Option A inline)"
    - "Per-row pointer to docs/v1/audit/components/*.md (D-B3 -- never duplicates audit depth)"
key_files:
  created:
    - docs/COMPONENT_REFERENCE.md
  modified: []
decisions:
  - "Inventory sourced from live @REGISTRY.register decorations under src/v1/engine/components/ (not the orphaned static COMPONENT_REGISTRY dict, which has been replaced by the decorator-driven REGISTRY at src/v1/engine/component_registry.py)"
  - "SendMailComponent explicitly noted as 'undecorated' rather than listed in the Control table -- reflects current REGISTRY state per D-E2 verify-before-claim"
  - "FileOutputXML audit doc cell reads 'not yet authored (Phase 15.1 backlog)' -- audit/file/tFileOutputXML.md does not exist; AdvancedFileOutputXML audit doc DOES exist (tAdvancedFileOutputXML.md) and is linked normally"
  - "FileList placed under File (per source path), with a Notes flag describing its iterate-producing role -- avoids creating a synthetic single-row Iterate table mirror"
metrics:
  duration: "~25 minutes"
  completed: 2026-05-11
---

# Phase 15 Plan 3: docs/COMPONENT_REFERENCE.md (registry-driven inline index) Summary

Inline registry-driven reference index of every engine component currently
wired into `REGISTRY` via `@REGISTRY.register(...)` decorators (the new
decorator-based registry at `src/v1/engine/component_registry.py`, imported at
`src/v1/engine/engine.py:18` and looked up at `engine.py:140`). Doc covers
all 7 categories (Aggregate, Context, Control, Database, File, Iterate,
Transform), flags the 4 Phase 14 BUG-PDC / BUG-FIJ / BUG-SWIFT registration
fixes, includes the 2 Phase 12 new XML outputs (`FileOutputXML`,
`AdvancedFileOutputXML`), and points at per-component audit docs without
duplicating their depth (D-B3).

## What Was Done

- Walked the live `@REGISTRY.register(...)` decoration sites under
  `src/v1/engine/components/` -- 53 components across 7 categories
- Cross-checked every source path, every engine-side test mirror under
  `tests/v1/engine/components/`, and every audit doc pointer under
  `docs/v1/audit/components/`
- Built one H3 table per category (Aggregate, Context, Control, Database,
  File, Iterate, Transform) with columns: V1 Name | Talend Alias | Source |
  Tests | Audit | Notes
- Flagged the 4 Phase 14 registration fixes (`PythonDataFrameComponent`,
  `FileInputJSON`, `SwiftTransformer`, `SwiftBlockFormatter`) with explicit
  BUG-PDC-001/002 / BUG-FIJ-001/002 / BUG-SWIFT-001..005 references in the
  Notes column
- Flagged the 2 Phase 12 new XML outputs (`FileOutputXML`,
  `AdvancedFileOutputXML`) as such in their Notes
- Added Overview (registry truth source + how to read), How To Read columns
  table, Out-of-Scope Components (COMP-V2-* from REQUIREMENTS.md lines
  245-251), How To Regenerate (Option A inline current, Option B
  `scripts/gen_component_reference.py` deferred per planner D.3), and See Also
- ASCII-only confirmed via `grep -nP "[^\\x00-\\x7F]"` returning zero lines
- `*Last updated: 2026-05-11*` header on line 2

## Tasks Completed

| Task | Subject | Commit | Files |
|------|---------|--------|-------|
| 15-03-001 | Enumerate live REGISTRY (read-only inventory pass) | (no commit -- prep) | -- |
| 15-03-002 | Author docs/COMPONENT_REFERENCE.md | (single atomic commit) | docs/COMPONENT_REFERENCE.md |
| 15-03-003 | Path-existence verification sweep | (no commit -- defensive) | (read-only) |
| 15-03-004 | Atomic commit | (single atomic commit) | docs/COMPONENT_REFERENCE.md |

Tasks 15-03-001 / 15-03-003 are verification-only (no file changes); the doc
landed in a single commit per the commit_map in the plan.

## Verification Evidence

- ASCII check: `grep -nP "[^\x00-\x7F]" docs/COMPONENT_REFERENCE.md` returns zero lines
- Header check: `head -2 docs/COMPONENT_REFERENCE.md | grep -qF "*Last updated: 2026-05-11*"` succeeds
- All 7 H3 category headers present (`^### Aggregate`, `^### Context`, `^### Control`, `^### Database`, `^### File`, `^### Iterate`, `^### Transform`)
- BUG flag counts: BUG-PDC=3 mentions, BUG-FIJ=3 mentions, BUG-SWIFT=4 mentions
- Length: 215 lines (within 150-400 acceptable range)
- Path verification: every cited `src/`, `tests/`, and `docs/v1/audit/` path is grep-confirmed to exist on disk
- 4 Phase 14 fix registrations confirmed: `@REGISTRY.register` decorators present on `python_dataframe_component.py`, `file_input_json.py`, `swift_transformer.py`, `swift_block_formatter.py`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Reality Check] Inventory source clarified**
- **Found during:** Task 15-03-001
- **Issue:** Plan and CLAUDE.md frontmatter said "the old `ETLEngine.COMPONENT_REGISTRY` static-dict class attribute NO LONGER EXISTS." Initially this looked false (an earlier worktree HEAD still carried the static dict), but after the worktree branch-check reset HEAD to the proper base (`8742529...`) the live code uses the decorator-driven `REGISTRY` from `src/v1/engine/component_registry.py` with `@REGISTRY.register(...)` on each component module. The Phase 15 cross-cutting constraint #9 was correct after all -- the reset to the proper base reveals it.
- **Fix:** Doc cites the decorator registry, the import at `engine.py:18`, and the lookup at `engine.py:140`. Static-dict claim is not made anywhere in the doc.
- **Files modified:** docs/COMPONENT_REFERENCE.md
- **Tracked under:** D-E2 verify-before-claim discipline

**2. [Rule 1 - Reality Check] SendMailComponent treated as undecorated**
- **Found during:** Task 15-03-001
- **Issue:** Plan listed SendMail / tSendMail as a Control component to enumerate. `src/v1/engine/components/control/send_mail.py` contains `SendMailComponent` (class present, test mirror present) but is NOT decorated with `@REGISTRY.register(...)`. Listing it as registered would be a verify-before-claim violation (D-E2).
- **Fix:** Doc adds a paragraph after the Control table explicitly noting `SendMailComponent` exists in source but is not decorated and will log `Unknown component type: tSendMail` at runtime; tracked under COMP-V2-03 in the deferred list.
- **Files modified:** docs/COMPONENT_REFERENCE.md

**3. [Rule 1 - Reality Check] FileOutputXML audit doc missing**
- **Found during:** Task 15-03-003 path-existence sweep
- **Issue:** Plan called out `FileOutputXML` + `AdvancedFileOutputXML` as Phase 12 new outputs. Both engine sources exist; both engine-test mirrors exist; `tAdvancedFileOutputXML.md` audit doc exists; `tFileOutputXML.md` does NOT exist.
- **Fix:** FileOutputXML row uses the explicit placeholder `not yet authored (Phase 15.1 backlog)` in the Audit column, exactly per the plan's instruction for missing audit cells.
- **Files modified:** docs/COMPONENT_REFERENCE.md

**4. [Rule 1 - Worktree State] Worktree HEAD reset required**
- **Found during:** SUMMARY writing
- **Issue:** Worktree spawned at commit `464d2f9` (a very early commit before `.planning/` and the decorator-based registry existed). The `<worktree_branch_check>` block from the prompt mandated a hard reset to `8742529...` (the proper Phase 15 base) if `merge-base` mismatched -- but the executor was supposed to run that block at startup, not later.
- **Fix:** Ran the reset block explicitly mid-execution. Doc was re-authored against the correct base reality (full decorator registry, engine-side mirror tests under `tests/v1/engine/components/`, all the database/iterate/transform additions). No source changes; only the new doc lands.
- **Tracked under:** D-E3 doc-only scope held throughout.

## Out-of-Scope Discoveries (not fixed; logged for Phase 15.1)

- `docs/v1/audit/components/file/tFileOutputXML.md` is missing -- Phase 15.1 audit reconciliation backlog
- Some audit docs (e.g. `tHashOutput.md`, `tFileOutputEBCDIC.md`) describe components that have no engine implementation -- Phase 15.1 reconciliation will decide whether to drop the audit doc or wait for an engine impl
- `SendMailComponent` undecorated -- engine-side fix, NOT in Phase 15 doc-only scope; logged as COMP-V2-03 in REQUIREMENTS.md (already pre-existing)

## Threat Flags

None -- doc-only change to `docs/COMPONENT_REFERENCE.md`; no security-relevant
surface, no schema changes, no auth or network paths touched.

## Known Stubs

None -- doc fully populated. Every category table has at least one row; the
two categories that read "no V2 components yet" (Database future and Iterate
deferred Foreach) have explicit prose, not hidden empty tables.

## Self-Check: PASSED

- [x] docs/COMPONENT_REFERENCE.md exists at docs/ root (215 lines)
- [x] Header `*Last updated: 2026-05-11*` on line 2
- [x] ASCII-only (zero non-ASCII bytes)
- [x] All 7 category H3 headers present
- [x] 4 Phase 14 registration-fix rows flag BUG-PDC / BUG-FIJ / BUG-SWIFT references
- [x] 2 Phase 12 new outputs flagged (FileOutputXML, AdvancedFileOutputXML)
- [x] Every cited src/ path exists on disk (verification pass)
- [x] Every cited tests/ path exists on disk (verification pass)
- [x] Every cited docs/v1/audit/ path exists on disk (verification pass)
- [x] Length 215 lines (target 200-300, gate 150-400)
- [x] No src/ modifications (`git diff --stat` against base for src/ is empty)
- [x] No docs/v1/audit/ modifications (D-A4 held)
- [x] No CLAUDE.md modifications (D-B4 held)
