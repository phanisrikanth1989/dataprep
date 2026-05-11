---
phase: 15
plan: 1
slug: nuke-top-level-docs
type: execute
wave: 0
depends_on: []
files_modified:
  - docs/ARCHITECTURE.md                  # DELETE (stale, 812 lines)
  - docs/BaseComponent Info.docx          # DELETE (.docx; md version stays at docs/v1/)
  - docs/CODE_REFERENCE.md                # DELETE (1416 lines stale)
  - docs/COMPLETION_CHECKLIST.md          # DELETE
  - docs/Demo Talking Points.docx         # DELETE (.docx)
  - docs/FILE_INVENTORY.md                # DELETE
  - docs/FINAL_SUMMARY.md                 # DELETE (ROADMAP SC#1 exemplar)
  - docs/IMPLEMENTATION_COMPLETE.md       # DELETE (ROADMAP SC#1 exemplar)
  - docs/JOB_WORKFLOW_GUIDE.md            # DELETE
  - docs/KNOWLEDGE_BASE_SUMMARY.md        # DELETE
  - docs/LAYOUT_UPDATE.md                 # DELETE (ROADMAP SC#1 exemplar)
  - docs/QUICK_REFERENCE.md               # DELETE
  - docs/README_INDEX.md                  # DELETE
  - docs/SETUP_DEPLOYMENT.md              # DELETE (replaced by DEPLOYMENT.md in 15-05)
  - docs/START_HERE.md                    # DELETE
  - docs/SYSTEM_DIAGRAMS.md               # DELETE
  - docs/TESTING_GUIDE.md                 # DELETE
  - docs/UI_IMPLEMENTATION_GUIDE.md       # DELETE (ROADMAP SC#1 exemplar)
  - docs/UI_INDEX.md                      # DELETE (ROADMAP SC#1 exemplar)
  - docs/UI_README.md                     # DELETE (ROADMAP SC#1 exemplar)
  - docs/WORKSPACE_OVERVIEW.md            # DELETE
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "All 22 top-level docs/*.md and docs/*.docx files removed in a single batch commit"
    - "ls docs/ shows only the v1/ subdirectory and any wave-1 canonical docs not yet landed"
    - "Git history preserves the deleted files (recoverable via git log -- <path>)"
    - "No file under docs/v1/ was touched by this plan"
    - "No file under src/ was touched (doc-only phase per D-E3)"
  artifacts:
    - path: docs/
      provides: cleared top-level (only v1/ subdirectory remains until wave 1 lands the 4 canonical docs)
  key_links:
    - from: this plan's commit
      to: subsequent wave-1 plans (15-02..15-06)
      via: clean slate at docs/ root -- no filename collision risk with the 22 stale files
---

<objective>
Nuke all 22 stale top-level entries under `docs/` (20 `.md` + 2 `.docx`) per D-A1. Single batch commit ("remove top-level docs/ batch") explicitly allowed per CONTEXT.md D-E1 example. No salvage, no migration -- fresh canonical docs in wave 1 replace them.
</objective>

<scope>
- Delete all 22 top-level entries under `docs/` enumerated in `files_modified` frontmatter.
- Single atomic commit covering all 22 deletions (the only multi-file commit in Phase 15; the planner-discussion example explicitly authorizes this batch).
- No touches to `docs/v1/` (handled by waves 2-3) or to `src/` (doc-only phase per D-E3).
- No new README at root in this plan -- root README is plan 15-06 in wave 1. The repo briefly has no top-level docs/*.md (only the v1/ subdir) between this commit and wave-1 landing; acceptable per the discussion order-of-operations note (RESEARCH.md C.7 acknowledges a brief gap window).
</scope>

<out_of_scope>
- `docs/v1/` (any file under it; standards/ + audit/ + sibling files are all handled by later plans).
- Root `README.md` (plan 15-06).
- The 4 canonical docs at `docs/` root (plans 15-02..15-05).
- Any `src/` change (D-E3 forbids).
- Any `.planning/`, `.claude/`, `.gemini/` change (CONTEXT.md out-of-scope).
- `tests/fixtures/jobs/README.md` (CONTEXT.md out-of-scope -- stays as-is).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A1 (total nuke), D-E1 (atomic commits; batch-delete example explicitly authorized)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section C.7 (order-of-operations -- delete is step 2)
- `.planning/ROADMAP.md` Phase 15 SC#1 (22 stale files deleted, 4 canonical docs replace)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-01-001: Pre-flight inventory check</name>
  <files>(read-only)</files>
  <action>
Confirm the 22 expected entries exist before deletion, so the plan's `files_modified` list matches reality on disk. Run from project root:

```bash
ls -1 docs/*.md docs/*.docx 2>/dev/null | sort
```

Expected output (22 entries, exact match):
```
docs/ARCHITECTURE.md
docs/BaseComponent Info.docx
docs/CODE_REFERENCE.md
docs/COMPLETION_CHECKLIST.md
docs/Demo Talking Points.docx
docs/FILE_INVENTORY.md
docs/FINAL_SUMMARY.md
docs/IMPLEMENTATION_COMPLETE.md
docs/JOB_WORKFLOW_GUIDE.md
docs/KNOWLEDGE_BASE_SUMMARY.md
docs/LAYOUT_UPDATE.md
docs/QUICK_REFERENCE.md
docs/README_INDEX.md
docs/SETUP_DEPLOYMENT.md
docs/START_HERE.md
docs/SYSTEM_DIAGRAMS.md
docs/TESTING_GUIDE.md
docs/UI_IMPLEMENTATION_GUIDE.md
docs/UI_INDEX.md
docs/UI_README.md
docs/WORKSPACE_OVERVIEW.md
```

If the count is not 22 or any name differs, STOP and update this plan's `files_modified` list to match before proceeding. Document the discrepancy in the plan SUMMARY.
  </action>
  <verify>
    <automated>test "$(ls -1 docs/*.md docs/*.docx 2>/dev/null | wc -l | tr -d ' ')" = "22" && echo "OK: 22 entries confirmed"</automated>
  </verify>
  <done>22 entries confirmed; any drift recorded in plan SUMMARY.</done>
</task>

<task type="auto">
  <name>Task 15-01-002: Batch-delete all 22 top-level docs/ files</name>
  <files>docs/ARCHITECTURE.md, docs/BaseComponent Info.docx, docs/CODE_REFERENCE.md, docs/COMPLETION_CHECKLIST.md, docs/Demo Talking Points.docx, docs/FILE_INVENTORY.md, docs/FINAL_SUMMARY.md, docs/IMPLEMENTATION_COMPLETE.md, docs/JOB_WORKFLOW_GUIDE.md, docs/KNOWLEDGE_BASE_SUMMARY.md, docs/LAYOUT_UPDATE.md, docs/QUICK_REFERENCE.md, docs/README_INDEX.md, docs/SETUP_DEPLOYMENT.md, docs/START_HERE.md, docs/SYSTEM_DIAGRAMS.md, docs/TESTING_GUIDE.md, docs/UI_IMPLEMENTATION_GUIDE.md, docs/UI_INDEX.md, docs/UI_README.md, docs/WORKSPACE_OVERVIEW.md, docs/Demo Talking Points.docx</files>
  <action>
Run from project root:

```bash
git rm "docs/ARCHITECTURE.md" \
       "docs/BaseComponent Info.docx" \
       "docs/CODE_REFERENCE.md" \
       "docs/COMPLETION_CHECKLIST.md" \
       "docs/Demo Talking Points.docx" \
       "docs/FILE_INVENTORY.md" \
       "docs/FINAL_SUMMARY.md" \
       "docs/IMPLEMENTATION_COMPLETE.md" \
       "docs/JOB_WORKFLOW_GUIDE.md" \
       "docs/KNOWLEDGE_BASE_SUMMARY.md" \
       "docs/LAYOUT_UPDATE.md" \
       "docs/QUICK_REFERENCE.md" \
       "docs/README_INDEX.md" \
       "docs/SETUP_DEPLOYMENT.md" \
       "docs/START_HERE.md" \
       "docs/SYSTEM_DIAGRAMS.md" \
       "docs/TESTING_GUIDE.md" \
       "docs/UI_IMPLEMENTATION_GUIDE.md" \
       "docs/UI_INDEX.md" \
       "docs/UI_README.md" \
       "docs/WORKSPACE_OVERVIEW.md"
```

Note the quoting around the two `.docx` filenames (they contain spaces).

Commit with the single batch message:

```
chore(15-01): nuke 22 top-level docs/ files (D-A1)

20 .md files + 2 .docx files removed wholesale per Phase 15 D-A1.
Fresh canonical docs land in plans 15-02..15-06. Git history
preserves the removed files (git log -- docs/<path>).

Refs: .planning/phases/15-documentation-sweep/15-CONTEXT.md D-A1, D-E1
```

Atomicity rationale: a single batch is explicitly allowed for this delete per CONTEXT.md D-E1 ("remove top-level docs/ batch" example). The 22 files are all deletions with no content interdependency; splitting into 22 commits adds no value and 21 lines of git log noise.
  </action>
  <verify>
    <automated>test "$(ls -1 docs/*.md docs/*.docx 2>/dev/null | wc -l | tr -d ' ')" = "0" && test -d docs/v1 && echo "OK: top-level cleared, v1/ preserved"</automated>
  </verify>
  <done>All 22 entries removed; `docs/v1/` directory still present; single commit landed with the chore(15-01) subject.</done>
</task>

<task type="auto">
  <name>Task 15-01-003: Doc-only regression check</name>
  <files>(read-only)</files>
  <action>
Confirm no `src/` file was touched in this plan (D-E3 doc-only). Run:

```bash
git diff --stat HEAD~1..HEAD -- src/ | wc -l
```

Expected: `0` (zero lines of diff in src/).

Also confirm `docs/v1/` is untouched:

```bash
git diff --stat HEAD~1..HEAD -- docs/v1/ | wc -l
```

Expected: `0`.

If either is nonzero, ROLL BACK the commit before wave 1 starts -- this plan accidentally exceeded its scope.
  </action>
  <verify>
    <automated>test "$(git diff --stat HEAD~1..HEAD -- src/ docs/v1/ 2>/dev/null | wc -l | tr -d ' ')" = "0" && echo "OK: scope honored"</automated>
  </verify>
  <done>Zero src/ or docs/v1/ changes in the commit; scope honored.</done>
</task>

</tasks>

<verification_gate>

Plan 15-01 is GREEN when:
1. `ls docs/*.md docs/*.docx 2>/dev/null` returns nothing (top-level cleared).
2. `docs/v1/` directory still exists with all its prior contents intact.
3. `README.md` does NOT yet exist at repo root (plan 15-06 adds it).
4. Single commit with subject `chore(15-01): nuke 22 top-level docs/ files (D-A1)` landed.
5. `git diff --stat HEAD~1..HEAD -- src/` shows zero lines.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(15-01): nuke 22 top-level docs/ files (D-A1)` | 22 deletions (see `files_modified`) |

(Total: 1 commit. Single batch by explicit CONTEXT.md D-E1 authorization.)

</commit_map>
