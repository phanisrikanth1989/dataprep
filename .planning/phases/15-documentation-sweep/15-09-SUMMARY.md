---
phase: 15-documentation-sweep
plan: 9
subsystem: docs
tags: [docs-restructure, git-mv, history-preservation, patterns, manual-authoring]

requires:
  - phase: 15-07-standards-drop-set
    provides: 5-file standards/ directory (DROP set already removed); audit/ broken-ref inventory deferred to Phase 15.1
  - phase: 15-08-standards-keep-fix-set
    provides: KEEP+FIX content patches landed in place (this plan only moves files)

provides:
  - docs/v1/patterns/ as the renamed location of docs/v1/standards/ (history-preserving git mv)
  - docs/v1/patterns/BaseComponent-Info.md colocated with ENGINE_COMPONENT_PATTERN.md
  - docs/v1/ root reduced to 3 entries: patterns/, audit/, talend_to_v1_converter_guide.md
  - Phase-15-authored intra-doc references rewritten to the post-rename path (patterns/)

affects: [15-10-closeout, 15.1-audit-reconciliation]

tech-stack:
  added: []
  patterns:
    - "Folder rename via `git mv` -- preserves --follow history for every renamed file"
    - "Atomic per-operation commits (D-E1) -- one commit per logical move so a single revert undoes one move only"

key-files:
  created:
    - docs/v1/patterns/CONVERTER_PATTERN.md (renamed from docs/v1/standards/)
    - docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md (renamed from docs/v1/standards/)
    - docs/v1/patterns/ENGINE_TEST_PATTERN.md (renamed from docs/v1/standards/)
    - docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md (renamed from docs/v1/standards/)
    - docs/v1/patterns/TEST_PATTERN.md (renamed from docs/v1/standards/)
    - docs/v1/patterns/BaseComponent-Info.md (moved from docs/v1/)
  modified:
    - docs/v1/patterns/ENGINE_TEST_PATTERN.md (1 stale `docs/v1/standards/` path rewritten)
    - docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md (5 stale `docs/v1/standards/` paths rewritten)

key-decisions:
  - "Renamed standards/ -> patterns/ via `git mv` (single directory operation preserves all 5 files' --follow history)"
  - "Committed cross-reference fix as a separate third commit (15-09-004) instead of squashing into the rename commit -- keeps the rename a pure history-preserving operation and the fix a content change with its own reviewable diff"
  - "docs/v1/audit/ refs to old paths intentionally NOT fixed -- captured for Phase 15.1 per D-A4"

patterns-established:
  - "Rename-then-fix-refs sequence: commit the git mv first so reviewers see a pure rename; commit cross-reference fixes second"
  - "Cross-reference scan limited to Phase-15-authored docs (wave-1 canonical docs + KEEP+FIX patterns/ files); audit/ explicitly excluded under D-A4"

requirements-completed: [DOCS-02]

duration: ~10min
completed: 2026-05-11
---

# Phase 15 Plan 9: Folder Rename & Relocation Summary

**Renamed docs/v1/standards/ to docs/v1/patterns/ via `git mv` (history preserved) and moved BaseComponent-Info.md into patterns/; fixed 6 stale intra-doc cross-references in two Phase-15-authored files.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-11T04:42:00Z (approx)
- **Completed:** 2026-05-11T04:52:32Z
- **Tasks:** 4 of 4
- **Files modified:** 6 renamed + 2 content-edited = 8 total file touches (across 3 commits)

## Accomplishments

- `docs/v1/standards/` renamed to `docs/v1/patterns/` with `git mv` -- `git log --follow docs/v1/patterns/<file>` shows every pre-rename commit.
- `docs/v1/BaseComponent-Info.md` moved into `docs/v1/patterns/BaseComponent-Info.md` (colocated with ENGINE_COMPONENT_PATTERN.md per planner D.5).
- `docs/v1/talend_to_v1_converter_guide.md` left at `docs/v1/` root per planner D.7 (user-facing usage guide, not a contributor pattern).
- `docs/v1/` is now exactly 3 entries: `patterns/`, `audit/`, `talend_to_v1_converter_guide.md`.
- 6 stale intra-doc `docs/v1/standards/...` references in two Phase-15-authored docs rewritten to `docs/v1/patterns/...`.
- Zero changes to `docs/v1/audit/`, `CLAUDE.md`, or `src/` per scope.

## Task Commits

1. **Task 15-09-001: Pre-rename inventory snapshot** — read-only verification; no commit.
2. **Task 15-09-002: Rename docs/v1/standards/ -> docs/v1/patterns/** — `e27199b` (docs)
3. **Task 15-09-003: Move BaseComponent-Info.md into docs/v1/patterns/** — `753ed9a` (docs)
4. **Task 15-09-004: Cross-reference re-check + fix stale Phase-15 refs** — `403049d` (docs)

Three commits total. The plan's commit map projected 2 commits; the third commit is the optional cross-reference fix authorized by Task 15-09-004 ("Add a third commit only if Task 15-09-004 found a Phase 15-authored stale reference to fix.").

## Files Created/Modified

**Renamed (history-preserving):**
- `docs/v1/standards/CONVERTER_PATTERN.md` -> `docs/v1/patterns/CONVERTER_PATTERN.md`
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -> `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md`
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` -> `docs/v1/patterns/ENGINE_TEST_PATTERN.md`
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` -> `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md`
- `docs/v1/standards/TEST_PATTERN.md` -> `docs/v1/patterns/TEST_PATTERN.md`
- `docs/v1/BaseComponent-Info.md` -> `docs/v1/patterns/BaseComponent-Info.md`

**Content-edited (stale path rewrites):**
- `docs/v1/patterns/ENGINE_TEST_PATTERN.md` -- line 689: `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` -> `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md`
- `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` -- 5 occurrences on lines 25, 26, 29, 304, 317: `docs/v1/standards/` -> `docs/v1/patterns/`

## Decisions Made

- **Two `git mv` operations, two separate commits (per D-E1):** A single combined commit would have made revert at directory-rename granularity impossible. Each commit is reversible without affecting the other.
- **Third commit for cross-reference fix:** Authorized by Task 15-09-004; isolates a pure rename (commit 2) from a content change (commit 3) for cleaner review and revert.
- **`docs/v1/audit/` intentionally untouched** per D-A4 -- the 23 audit files referencing `docs/v1/standards/` are now broken-by-construction. Inventory deferred to Phase 15.1 (already enumerated in `15-07-SUMMARY.md`).

## Deviations from Plan

None - plan executed exactly as written. Task 15-09-004 found stale references and the plan explicitly authorized a third commit to fix them. The third commit was anticipated, not a deviation.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None -- all three commits map directly to plan-authorized actions (D-E1 atomic rename + D-E1 atomic move + D-A4-compliant Phase-15-only ref fix).

## Issues Encountered

- **Worktree initial state was not at the plan-expected base.** The parallel worktree spawned at HEAD `464d2f9` (pre-15-07 state) but the plan assumes `32aad55` (post-15-08 state, where DROP and KEEP+FIX are already landed). The `<worktree_branch_check>` reset to base `32aad55` per its merge-base divergence rule, after which the pre-rename inventory in Task 15-09-001 verified clean (5 files in `standards/`, 4 entries in `docs/v1/`).
- No other issues.

## Audit/ Broken References (Phase 15.1 Inventory Update)

Post-rename, `docs/v1/audit/` contains **23 files** still referencing the old `docs/v1/standards/` path (verified via `grep -rln "docs/v1/standards/" docs/v1/audit/`). Zero audit/ files reference `docs/v1/BaseComponent-Info.md` by its old path. These 23 audit-file references join the inventory captured in `15-07-SUMMARY.md` for Phase 15.1 reconciliation per D-A4. Do NOT fix them in Phase 15.

A sample of impacted audit files (from `grep` output):
- `docs/v1/audit/components/database/tOracleRollback.md`
- `docs/v1/audit/components/database/tOracleClose.md`
- `docs/v1/audit/components/database/tOracleCommit.md`
- `docs/v1/audit/components/database/tOracleOutput.md`
- `docs/v1/audit/components/database/tOracleBulkExec.md`
- `docs/v1/audit/components/iterate/tFlowToIterate.md`
- `docs/v1/audit/components/database/tMSSqlInput.md`
- `docs/v1/audit/components/iterate/tForeach.md`
- ... (15 more)

Full list available via `grep -rln "docs/v1/standards/" docs/v1/audit/`.

## User Setup Required

None - no external service configuration required.

## Verification Gate (per plan)

1. PASS - `docs/v1/standards/` does NOT exist.
2. PASS - `docs/v1/patterns/` exists with 6 files (5 renamed + BaseComponent-Info.md).
3. PASS - `docs/v1/BaseComponent-Info.md` does NOT exist at `docs/v1/` root.
4. PASS - `docs/v1/talend_to_v1_converter_guide.md` STILL EXISTS at `docs/v1/` root.
5. PASS - `docs/v1/audit/` untouched (zero commits modify any path under `docs/v1/audit/`).
6. PASS - 2 atomic git-mv commits landed (rename + move); 1 additional plan-authorized commit for stale-ref fix.
7. PASS - Phase-15-authored docs reference only `docs/v1/patterns/` (zero matches in `docs/v1/patterns/`, `docs/*.md`, `README.md`).
8. PASS - `CLAUDE.md` not modified; `src/` not modified (`git log 32aad55..HEAD --name-only | grep -E "^(CLAUDE\.md|src/)"` returns nothing).

## Next Phase Readiness

- Plan 15-10 closeout can verify the post-Phase-15 `docs/v1/` shape: `patterns/` + `audit/` + `talend_to_v1_converter_guide.md`.
- Phase 15.1 inherits the 23 audit/ files with stale `docs/v1/standards/` references plus any others already captured in `15-07-SUMMARY.md`.
- No blockers for downstream work.

## Self-Check: PASSED

Verified:
- `docs/v1/patterns/` exists -- FOUND (6 files)
- `docs/v1/standards/` does not exist -- CONFIRMED
- `docs/v1/BaseComponent-Info.md` does not exist -- CONFIRMED
- `docs/v1/patterns/BaseComponent-Info.md` exists -- FOUND
- `docs/v1/talend_to_v1_converter_guide.md` exists -- FOUND
- Commit `e27199b` (rename) -- FOUND in `git log`
- Commit `753ed9a` (BaseComponent-Info move) -- FOUND in `git log`
- Commit `403049d` (cross-ref fix) -- FOUND in `git log`
- No matches for `docs/v1/standards/` outside `docs/v1/audit/` -- CONFIRMED

---
*Phase: 15-documentation-sweep*
*Completed: 2026-05-11*
