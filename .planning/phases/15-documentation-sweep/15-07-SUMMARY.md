---
phase: 15
plan: 7
slug: standards-drop-set
type: summary
status: complete
completed: 2026-05-11
subsystem: documentation
tags: [documentation, cleanup, standards-zone, phase-15.1-handoff]
dependency_graph:
  requires: [15-01]
  provides: [docs/v1/standards/ trimmed to KEEP+FIX set only; broken-reference inventory for Phase 15.1]
  affects: [docs/v1/audit/** (informational only -- audit/ NOT modified per D-A4); Phase 15.1 reconciliation scope]
key_files:
  deleted:
    - docs/v1/STANDARDS.md (1325 lines)
    - docs/v1/standards/METHODOLOGY.md (207 lines)
    - docs/v1/standards/AUDIT_REPORT_TEMPLATE.md (496 lines)
    - docs/v1/standards/NEXT_MILESTONE_GUIDE.md (159 lines)
  created:
    - .planning/phases/15-documentation-sweep/15-07-SUMMARY.md
  modified: []
decisions:
  - "Researcher's '~84 audit/ references to STANDARDS.md' estimate was a significant overcount: actual count is 1 audit/ file (docs/v1/audit/METHODOLOGY.md) containing the 'STANDARDS.md compliance' / 'STANDARDS' string pattern."
  - "Inventory captured pre-deletion at /tmp/15-07-inventory/*.txt and embedded in this SUMMARY -- not persisted as a separate file. Phase 15.1 consumes the inventory from this SUMMARY."
  - "All 4 deletes used `git rm` then single-file commits per D-E1; git history preserves the files (resurrectable via `git show <hash>:<path>`)."
metrics:
  total_lines_removed: 2187
  delete_commits: 4
  summary_commit: 1
  audit_files_modified: 0
---

# Phase 15 Plan 7: Standards DROP Set Summary

Deleted 4 redundant/stale standards-zone docs (2,187 lines) as 4 atomic commits, with a broken-cross-reference inventory captured here as the Phase 15.1 (Documentation Audit Reconciliation) handoff per user `<open_questions_resolution>` D.2.

## Outcome

4 files deleted from the standards-zone in 4 atomic commits per D-E1, in increasing-risk order:

| # | File | Lines | Commit |
|---|------|------:|--------|
| 1 | docs/v1/standards/NEXT_MILESTONE_GUIDE.md | 159 | `6a8d7de docs(15-07): drop docs/v1/standards/NEXT_MILESTONE_GUIDE.md` |
| 2 | docs/v1/standards/AUDIT_REPORT_TEMPLATE.md | 496 | `df96251 docs(15-07): drop docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` |
| 3 | docs/v1/standards/METHODOLOGY.md | 207 | `b506dfb docs(15-07): drop docs/v1/standards/METHODOLOGY.md` |
| 4 | docs/v1/STANDARDS.md | 1325 | `261ac20 docs(15-07): drop docs/v1/STANDARDS.md (1325 lines; section 9 actively WRONG)` |

**Total lines removed: 2187.**

Surviving `docs/v1/standards/` files (KEEP+FIX set, owned by plan 15-08 / relocated by plan 15-09):
- `CONVERTER_PATTERN.md`
- `ENGINE_COMPONENT_PATTERN.md`
- `ENGINE_TEST_PATTERN.md`
- `MANUAL_COMPONENT_AUTHORING.md`
- `TEST_PATTERN.md`

CLAUDE.md sanity check confirmed zero references to any of the 4 dropped files; CLAUDE.md not modified (D-B4 honored).

## Broken-Cross-Reference Inventory (Phase 15.1 Handoff)

Files below referenced the now-deleted docs. Phase 15.1 (Documentation Audit Reconciliation) is responsible for fixing the **`docs/v1/audit/**`** references as part of audit-content reconciliation against current code; Phase 15 does NOT touch `audit/` per D-A4. `.planning/` matches are historical phase artifacts (research / plan / summary) describing past state -- they are NOT breakable references and are NOT in 15.1's scope.

### Files referencing docs/v1/STANDARDS.md (7 files)

**Notable finding:** researcher estimated "~84 audit/ entries via 'STANDARDS.md compliance' header pattern" -- actual audit/ count is **1 file**. The researcher's count appears to have miscounted (possibly conflated file count with grep-line count, or with a different pattern).

`.planning/` (6 -- historical, not actionable):
- .planning/phases/15-documentation-sweep/15-04-SUMMARY.md
- .planning/phases/15-documentation-sweep/15-07-standards-drop-set.md
- .planning/phases/15-documentation-sweep/15-10-closeout.md
- .planning/phases/15-documentation-sweep/15-CONTEXT.md
- .planning/phases/15-documentation-sweep/15-PLAN.md
- .planning/phases/15-documentation-sweep/15-RESEARCH.md

`docs/v1/audit/` (1 -- **Phase 15.1 fixes**):
- docs/v1/audit/METHODOLOGY.md

### Files referencing docs/v1/standards/METHODOLOGY.md (20 files)

`.planning/` (6 -- historical, not actionable):
- .planning/phases/07.1-manager-audit-and-basecomponent-fixes/07.1-CONTEXT.md
- .planning/phases/15-documentation-sweep/15-07-standards-drop-set.md
- .planning/phases/15-documentation-sweep/15-10-closeout.md
- .planning/phases/15-documentation-sweep/15-PLAN-CHECK.md
- .planning/phases/15-documentation-sweep/15-PLAN.md
- .planning/phases/15-documentation-sweep/15-RESEARCH.md

`docs/v1/audit/` (14 -- **Phase 15.1 fixes**):
- docs/v1/audit/components/context/tContextLoad.md
- docs/v1/audit/components/control/tParallelize.md
- docs/v1/audit/components/control/tPrejob.md
- docs/v1/audit/components/control/tRunJob.md
- docs/v1/audit/components/database/tOracleBulkExec.md
- docs/v1/audit/components/database/tOracleClose.md
- docs/v1/audit/components/database/tOracleCommit.md
- docs/v1/audit/components/database/tOracleRollback.md
- docs/v1/audit/components/file/tFileInputProperties.md
- docs/v1/audit/components/file/tFileList.md
- docs/v1/audit/components/iterate/tFlowToIterate.md
- docs/v1/audit/components/iterate/tForeach.md
- docs/v1/audit/components/transform/PythonComponent.md
- docs/v1/audit/components/transform/tChangeFileEncoding.md

### Files referencing docs/v1/standards/AUDIT_REPORT_TEMPLATE.md (33 files)

`.planning/` (11 -- historical, not actionable):
- .planning/phases/01-infrastructure-bug-fixes-project-setup/01-CONTEXT.md
- .planning/phases/01-infrastructure-bug-fixes-project-setup/01-RESEARCH.md
- .planning/phases/15-documentation-sweep/15-07-standards-drop-set.md
- .planning/phases/15-documentation-sweep/15-09-folder-rename-and-relocation.md
- .planning/phases/15-documentation-sweep/15-10-closeout.md
- .planning/phases/15-documentation-sweep/15-CONTEXT.md
- .planning/phases/15-documentation-sweep/15-DISCUSSION-LOG.md
- .planning/phases/15-documentation-sweep/15-PLAN-CHECK.md
- .planning/phases/15-documentation-sweep/15-PLAN.md
- .planning/phases/15-documentation-sweep/15-RESEARCH.md
- .planning/ROADMAP.md

`docs/v1/audit/` (22 -- **Phase 15.1 fixes**):
- docs/v1/audit/components/context/tContextLoad.md
- docs/v1/audit/components/control/tParallelize.md
- docs/v1/audit/components/control/tPostjob.md
- docs/v1/audit/components/control/tPrejob.md
- docs/v1/audit/components/control/tRunJob.md
- docs/v1/audit/components/database/tMSSqlInput.md
- docs/v1/audit/components/database/tOracleBulkExec.md
- docs/v1/audit/components/database/tOracleClose.md
- docs/v1/audit/components/database/tOracleCommit.md
- docs/v1/audit/components/database/tOracleOutput.md
- docs/v1/audit/components/database/tOracleRollback.md
- docs/v1/audit/components/file/tAdvancedFileOutputXML.md
- docs/v1/audit/components/file/tFileInputMSXML.md
- docs/v1/audit/components/file/tFileInputProperties.md
- docs/v1/audit/components/file/tFileList.md
- docs/v1/audit/components/iterate/tFlowToIterate.md
- docs/v1/audit/components/iterate/tForeach.md
- docs/v1/audit/components/transform/PythonComponent.md
- docs/v1/audit/components/transform/tExtractRegexFields.md
- docs/v1/audit/components/transform/tHashOutput.md
- docs/v1/audit/components/transform/tMemorizeRows.md
- docs/v1/audit/components/transform/tSampleRow.md

### Files referencing docs/v1/standards/NEXT_MILESTONE_GUIDE.md (7 files)

`.planning/` (7 -- historical, not actionable):
- .planning/phases/15-documentation-sweep/15-07-standards-drop-set.md
- .planning/phases/15-documentation-sweep/15-10-closeout.md
- .planning/phases/15-documentation-sweep/15-CONTEXT.md
- .planning/phases/15-documentation-sweep/15-DISCUSSION-LOG.md
- .planning/phases/15-documentation-sweep/15-PLAN-CHECK.md
- .planning/phases/15-documentation-sweep/15-PLAN.md
- .planning/phases/15-documentation-sweep/15-RESEARCH.md

`docs/v1/audit/` (0 -- nothing for Phase 15.1 to fix here):
- (none found)

### Audit-folder fix count summary

| Dropped doc | audit/ files to fix in 15.1 |
|---|---:|
| docs/v1/STANDARDS.md | 1 |
| docs/v1/standards/METHODOLOGY.md | 14 |
| docs/v1/standards/AUDIT_REPORT_TEMPLATE.md | 22 |
| docs/v1/standards/NEXT_MILESTONE_GUIDE.md | 0 |
| **Unique audit/ files affected (de-duplicated)** | ~25 |

(Many audit/ files reference more than one dropped doc, so the de-duplicated unique-file count is ~25, well below the researcher's ~84 estimate.)

## Phase 15.1 Reconciliation Guidance

For each `docs/v1/audit/**` file in the inventory:

1. Determine whether the reference is structural (e.g., 'follows STANDARDS.md compliance' table-row pattern) or content (e.g., 'see AUDIT_REPORT_TEMPLATE.md section X').
2. **Structural references** → replace with a reference to a surviving authority -- typically `docs/CONTRIBUTING.md` Rule N (plan 15-04) or `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` (post-rename in plan 15-09).
3. **Content references** → replace with the actual content guidance; one of the surviving docs (ENGINE_COMPONENT_PATTERN.md, CONVERTER_PATTERN.md, MANUAL_COMPONENT_AUTHORING.md, ENGINE_TEST_PATTERN.md, TEST_PATTERN.md, CLAUDE.md) covers it.
4. If neither applies (the audit doc cited Phase-1-era bug patterns or v1.1 playbook items that no longer apply) → mark the reference as `legacy -- removed in Phase 15` and revise the audit doc to stand alone or remove the stale claim.

### Git-resurrect (if 15.1 finds it needs a deleted doc verbatim)

```bash
# Find the deletion commit for each dropped file
git log --diff-filter=D --summary -- docs/v1/STANDARDS.md
git log --diff-filter=D --summary -- docs/v1/standards/METHODOLOGY.md
git log --diff-filter=D --summary -- docs/v1/standards/AUDIT_REPORT_TEMPLATE.md
git log --diff-filter=D --summary -- docs/v1/standards/NEXT_MILESTONE_GUIDE.md

# Recover contents (replace <hash> with deletion-commit's parent)
git show 6a8d7de^:docs/v1/standards/NEXT_MILESTONE_GUIDE.md > /tmp/next_milestone_guide.md.recovered
git show df96251^:docs/v1/standards/AUDIT_REPORT_TEMPLATE.md > /tmp/audit_report_template.md.recovered
git show b506dfb^:docs/v1/standards/METHODOLOGY.md > /tmp/methodology.md.recovered
git show 261ac20^:docs/v1/STANDARDS.md > /tmp/standards.md.recovered
```

## Deviations from Plan

**None for executable behavior** -- plan executed exactly as written (4 deletes + SUMMARY).

**Inventory finding (informational, not a deviation):** The researcher's "~84 audit/ files reference STANDARDS.md" estimate was an overcount; actual `docs/v1/audit/**` count is 1 file referencing STANDARDS.md, ~25 unique audit/ files de-duplicated across all 4 dropped docs. The corrected counts are above and feed Phase 15.1 scoping.

## Constraints Honored

- **D-A4** (no `docs/v1/audit/**` modification): 0 audit/ files modified by this plan.
- **D-A6** (METHODOLOGY + AUDIT_REPORT_TEMPLATE explicit deletion candidates; NEXT_MILESTONE_GUIDE likely-stale candidate): all 3 deleted; STANDARDS.md also deleted per D-A5 deep-review + D-A6 alignment.
- **D-B4** (no CLAUDE.md edits): pre-flight grep confirmed CLAUDE.md has zero references to the DROP set; not modified.
- **D-E1** (atomic commits): 4 delete commits + 1 SUMMARY commit = 5 commits, one logical change each.
- **D-E3** (doc-only, no `src/` changes): 0 `src/` files modified.

## Self-Check: PASSED

- `docs/v1/STANDARDS.md` -- GONE (verified via `test ! -f`)
- `docs/v1/standards/METHODOLOGY.md` -- GONE
- `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` -- GONE
- `docs/v1/standards/NEXT_MILESTONE_GUIDE.md` -- GONE
- `docs/v1/audit/METHODOLOGY.md` -- PRESERVED (D-A4)
- Commit `6a8d7de` -- FOUND in `git log`
- Commit `df96251` -- FOUND in `git log`
- Commit `b506dfb` -- FOUND in `git log`
- Commit `261ac20` -- FOUND in `git log`
- CLAUDE.md unchanged -- VERIFIED (zero references found pre-deletion; file not in git status)
- `src/` unchanged -- VERIFIED (no `src/` paths in any commit's `--name-only`)
