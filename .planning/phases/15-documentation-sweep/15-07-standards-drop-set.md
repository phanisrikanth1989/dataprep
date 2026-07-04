---
phase: 15
plan: 7
slug: standards-drop-set
type: execute
wave: 2
depends_on: [15-01]
files_modified:
  - docs/v1/STANDARDS.md                         # DELETE (1325 lines; redundant master, section 9 actively WRONG re: complex_converter)
  - docs/v1/standards/METHODOLOGY.md             # DELETE (207 lines; audit framing; D-A6 explicit candidate; Oracle exclusion claim wrong)
  - docs/v1/standards/AUDIT_REPORT_TEMPLATE.md   # DELETE (496 lines; audit template; D-A6 explicit candidate; references resolved bugs)
  - docs/v1/standards/NEXT_MILESTONE_GUIDE.md    # DELETE (159 lines; never-executed v1.1 playbook; D-A6 likely-stale candidate)
autonomous: true
requirements: [DOCS-02]
must_haves:
  truths:
    - "All 4 DROP-set files deleted from working tree"
    - "Each deletion is its own atomic commit per D-E1 (4 commits total)"
    - "git log preserves the deleted content (recoverable via git show)"
    - "Broken-cross-reference inventory captured in plan SUMMARY for Phase 15.1 handoff -- audit/ files referencing the dropped docs are enumerated, NOT fixed in Phase 15"
    - "Plan does NOT touch any file under docs/v1/audit/ (D-A4)"
    - "Plan does NOT modify CLAUDE.md (D-B4)"
    - "Plan does NOT modify any file under src/ (D-E3)"
  artifacts:
    - path: docs/v1/STANDARDS.md
      provides: gone (deleted); historical retrieval via git
    - path: docs/v1/standards/METHODOLOGY.md
      provides: gone (deleted); Phase 15.1 can resurrect from git if audit reconciliation needs it
    - path: docs/v1/standards/AUDIT_REPORT_TEMPLATE.md
      provides: gone (deleted); same as above
    - path: docs/v1/standards/NEXT_MILESTONE_GUIDE.md
      provides: gone (deleted); never-executed v1.1 playbook
  key_links:
    - from: this plan's SUMMARY
      to: Phase 15.1 (Documentation Audit Reconciliation)
      via: broken-cross-reference inventory -- list of audit/ files that referenced the deleted docs; 15.1 fixes them as part of audit reconciliation
      pattern: "Phase 15.1 handoff"
---

<objective>
Delete 4 standards-zone files per researcher recommendation + user `<open_questions_resolution>` D.2 (`DELETE in 15; capture broken-reference inventory for 15.1`):
- `docs/v1/STANDARDS.md` (1325 lines; section 9 actively WRONG re: `complex_converter`; bulk duplicates content covered by surviving patterns + ENGINE_COMPONENT_PATTERN + MANUAL_COMPONENT_AUTHORING + CLAUDE.md)
- `docs/v1/standards/METHODOLOGY.md` (207 lines; D-A6 explicit deletion candidate; "Database excluded" claim wrong post-Phase-11)
- `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` (496 lines; D-A6 explicit deletion candidate; references resolved-pre-Phase-1 bug patterns)
- `docs/v1/standards/NEXT_MILESTONE_GUIDE.md` (159 lines; D-A6 likely-stale candidate; never-executed v1.1 playbook)

Each deletion is its own atomic commit per D-E1. The plan SUMMARY captures the broken-cross-reference inventory (`docs/v1/audit/` files referencing the dropped docs) as the Phase 15.1 handoff -- Phase 15 does NOT fix those audit/ references (D-A4).
</objective>

<scope>
- 4 `git rm` operations, each its own commit.
- BEFORE deletion: enumerate `docs/v1/audit/**` references to each dropped file. Capture inventory in the plan SUMMARY at `.planning/phases/15-documentation-sweep/15-07-SUMMARY.md` for Phase 15.1 reconciliation.
- NO modification of any `docs/v1/audit/**` file (D-A4 HARD STOP).
- NO modification of CLAUDE.md (D-B4 HARD STOP).
- NO modification of `src/` (D-E3 HARD STOP).
</scope>

<out_of_scope>
- Editing audit/ files to rewire the broken references (Phase 15.1 owns this; the inventory generated here is the handoff).
- Moving the dropped docs to `.planning/archive/` (researcher D.1 / D.2 preference Option A: delete outright; git history preserves them).
- Modifying the 7 KEEP+FIX files (plan 15-08 owns those).
- The folder rename to `patterns/` (plan 15-09).
- `docs/v1/talend_to_v1_converter_guide.md` (KEEP+FIX in plan 15-08).
- `docs/v1/BaseComponent-Info.md` (KEEP+FIX in plan 15-08; moves in plan 15-09).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A4 (audit/ OFF LIMITS), D-A5 (standards/ deep review), D-A6 (METHODOLOGY + AUDIT_REPORT_TEMPLATE explicit deletion candidates), D-B4 (no CLAUDE.md edits), D-E1 (atomic commits), D-E3 (doc-only, no src/ changes)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section A.5 (AUDIT_REPORT_TEMPLATE DROP rationale), A.7 (METHODOLOGY DROP rationale), A.8 (NEXT_MILESTONE_GUIDE DROP rationale), A.9 (STANDARDS.md DROP rationale -- "1325 lines are pure liability; Section 9 actively WRONG"), C.6 (zero-consumer verification grep), D.2 (Option A: delete in Phase 15)
- `.planning/phases/15-documentation-sweep/15-PLAN.md` Open Issue #2 (user `<open_questions_resolution>` D.2 explicitly authorizes Phase-15 deletion with inventory handoff to 15.1)
- Phase 15.1 ROADMAP.md entry (DOCS-03 scope: audit reconciliation)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-07-001: Pre-deletion cross-reference inventory (audit/ + CLAUDE.md + .planning/)</name>
  <files>(read-only; inventory captured in plan SUMMARY)</files>
  <action>
Before deleting, enumerate every reference to each DROP-set file. The inventory is the Phase 15.1 handoff per `<open_questions_resolution>` D.2.

```bash
mkdir -p /tmp/15-07-inventory

# 1. STANDARDS.md references (most-cited; researcher identified ~84 audit/ files):
grep -rln "docs/v1/STANDARDS\.md\|docs/v1/STANDARDS$\|STANDARDS\.md compliance\|STANDARDS\.md compliance" \
  docs/v1/audit/ CLAUDE.md .planning/ 2>/dev/null | sort -u > /tmp/15-07-inventory/standards-refs.txt

# 2. METHODOLOGY.md references (note: docs/v1/audit/METHODOLOGY.md is a SEPARATE file under audit/ -- do not confuse):
grep -rln "docs/v1/standards/METHODOLOGY\|standards/METHODOLOGY" \
  docs/v1/audit/ CLAUDE.md .planning/ 2>/dev/null | sort -u > /tmp/15-07-inventory/methodology-refs.txt

# 3. AUDIT_REPORT_TEMPLATE.md references:
grep -rln "AUDIT_REPORT_TEMPLATE" \
  docs/v1/audit/ CLAUDE.md .planning/ 2>/dev/null | sort -u > /tmp/15-07-inventory/audit-tpl-refs.txt

# 4. NEXT_MILESTONE_GUIDE.md references:
grep -rln "NEXT_MILESTONE_GUIDE" \
  docs/v1/audit/ CLAUDE.md .planning/ 2>/dev/null | sort -u > /tmp/15-07-inventory/next-ms-refs.txt

# 5. Sanity: ZERO matches in CLAUDE.md is expected; any match means CLAUDE.md anchors a reference we'd break.
grep -nE "docs/v1/STANDARDS|METHODOLOGY\.md|AUDIT_REPORT_TEMPLATE|NEXT_MILESTONE_GUIDE" CLAUDE.md && echo "WARN: CLAUDE.md references a DROP target" || echo "OK: CLAUDE.md has no references to DROP set"

# 6. Print counts for plan SUMMARY:
wc -l /tmp/15-07-inventory/*.txt
```

CRITICAL: per `<open_questions_resolution>` D.2 the planner OVERRIDES researcher Assumption A1 (which said "if any audit/ ref exists, downgrade DROP to DEFER"). User explicit instruction: delete in Phase 15, capture the inventory for 15.1. So the audit/ matches expected from item 1 (~84 files referencing STANDARDS.md per researcher) are NOT a blocker -- they are the HANDOFF artifact.

CLAUDE.md sanity (item 5) IS a blocker: if CLAUDE.md links to a DROP-target file, that's a load-bearing reference. The expected outcome is ZERO matches in CLAUDE.md (per CONTEXT.md `<code_context>` "CLAUDE.md is comprehensive and authoritative for Claude" and D-B4 "CONTRIBUTING.md references CLAUDE.md but does not duplicate"). If CLAUDE.md DOES reference a DROP target, STOP and reconcile with the user before deleting.

`.planning/` matches: any reference under `.planning/` means a phase artifact (research / plan / summary) cited the doc historically. These are not breakable references (they describe past state); record in inventory but do not action.
  </action>
  <verify>
    <automated>test -f /tmp/15-07-inventory/standards-refs.txt && test -f /tmp/15-07-inventory/methodology-refs.txt && test -f /tmp/15-07-inventory/audit-tpl-refs.txt && test -f /tmp/15-07-inventory/next-ms-refs.txt && claude_refs=$(grep -cE "docs/v1/STANDARDS|METHODOLOGY\.md|AUDIT_REPORT_TEMPLATE|NEXT_MILESTONE_GUIDE" CLAUDE.md 2>/dev/null || echo 0) && test "$claude_refs" = "0" && echo "OK: inventory captured; CLAUDE.md clean"</automated>
  </verify>
  <done>Inventory captured at /tmp/15-07-inventory/; CLAUDE.md sanity-check passed (zero references); inventory will be folded into plan SUMMARY at 15-07-SUMMARY.md.</done>
</task>

<task type="auto">
  <name>Task 15-07-002: Delete docs/v1/standards/NEXT_MILESTONE_GUIDE.md</name>
  <files>docs/v1/standards/NEXT_MILESTONE_GUIDE.md</files>
  <action>
Lowest-risk delete first (entirely historical artifact; never-executed playbook).

```bash
test -f docs/v1/standards/NEXT_MILESTONE_GUIDE.md || { echo "ABSENT -- already gone"; exit 0; }
git rm docs/v1/standards/NEXT_MILESTONE_GUIDE.md
git commit -m "docs(15-07): drop docs/v1/standards/NEXT_MILESTONE_GUIDE.md

Never-executed v1.1 standardization playbook (159 lines). The
'8-phase' table does not match the actual 16-phase ROADMAP.md;
'Mode: YOLO' is not the actual GSD-driven workflow used.
Documented as DROP candidate per D-A6 likely-stale and RESEARCH.md A.8.

Git history preserves the file; resurrect via git show if needed
(no live consumer found in pre-deletion inventory).

Refs: 15-CONTEXT.md D-A6; 15-RESEARCH.md A.8; planner D.1 -> Option A"
```
  </action>
  <verify>
    <automated>test ! -f docs/v1/standards/NEXT_MILESTONE_GUIDE.md && git log -1 --pretty=%s | grep -qF "docs(15-07): drop docs/v1/standards/NEXT_MILESTONE_GUIDE.md" && echo "OK"</automated>
  </verify>
  <done>NEXT_MILESTONE_GUIDE.md deleted; single atomic commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-07-003: Delete docs/v1/standards/AUDIT_REPORT_TEMPLATE.md</name>
  <files>docs/v1/standards/AUDIT_REPORT_TEMPLATE.md</files>
  <action>
```bash
test -f docs/v1/standards/AUDIT_REPORT_TEMPLATE.md || { echo "ABSENT"; exit 0; }
git rm docs/v1/standards/AUDIT_REPORT_TEMPLATE.md
git commit -m "docs(15-07): drop docs/v1/standards/AUDIT_REPORT_TEMPLATE.md

D-A6 explicit deletion candidate. Template for audit reports under
docs/v1/audit/; its edge-case checklist references ENG-01 / ENG-19 /
ENG-08 (Phase 1 bugs FIXED) as live audit concerns. Heavy overlap
with METHODOLOGY.md (also being dropped this plan).

Phase 15.1 owns audit/ reconciliation; if 15.1 needs a fresh
audit-template, it can author one or resurrect this one from git.

audit/ files referencing this template: see 15-07-SUMMARY.md
inventory; Phase 15.1 reconciles those references as part of its
audit-reconciliation scope (D-A4 -- Phase 15 does not touch audit/).

Refs: 15-CONTEXT.md D-A6; 15-RESEARCH.md A.5; planner D.2 -> Option A"
```
  </action>
  <verify>
    <automated>test ! -f docs/v1/standards/AUDIT_REPORT_TEMPLATE.md && git log -1 --pretty=%s | grep -qF "docs(15-07): drop docs/v1/standards/AUDIT_REPORT_TEMPLATE.md" && echo "OK"</automated>
  </verify>
  <done>AUDIT_REPORT_TEMPLATE.md deleted; single atomic commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-07-004: Delete docs/v1/standards/METHODOLOGY.md</name>
  <files>docs/v1/standards/METHODOLOGY.md</files>
  <action>
```bash
test -f docs/v1/standards/METHODOLOGY.md || { echo "ABSENT"; exit 0; }
git rm docs/v1/standards/METHODOLOGY.md
git commit -m "docs(15-07): drop docs/v1/standards/METHODOLOGY.md

D-A6 explicit deletion candidate. Audit-methodology framework
(scoring, dimensions, edge-case checklist). Multiple stale claims:
'Database components excluded' (wrong post-Phase-11); 'V1 only'
v2 disclaimer (historical context, no v2 in repo); '~50 implemented
v1 engine components' (inaccurate post-Phase-14).

Heavy overlap with AUDIT_REPORT_TEMPLATE.md (just dropped).
docs/v1/audit/METHODOLOGY.md (a SEPARATE file under audit/) is OUT
OF SCOPE per D-A4 and is NOT touched by Phase 15.

audit/ files referencing this standards/METHODOLOGY.md: see
15-07-SUMMARY.md inventory; Phase 15.1 reconciles.

Refs: 15-CONTEXT.md D-A6; 15-RESEARCH.md A.7; planner D.2 -> Option A"
```

Note (important disambiguation): there are TWO files named `METHODOLOGY.md` in the repo:
- `docs/v1/standards/METHODOLOGY.md` (THIS file -- DELETED by this task)
- `docs/v1/audit/METHODOLOGY.md` (under audit/ -- OUT OF SCOPE per D-A4; Phase 15 does NOT touch it)

Confirm the delete targets the right path:

```bash
ls docs/v1/audit/METHODOLOGY.md 2>/dev/null && echo "OK: audit/METHODOLOGY.md still exists (correct -- D-A4)"
```
  </action>
  <verify>
    <automated>test ! -f docs/v1/standards/METHODOLOGY.md && test -f docs/v1/audit/METHODOLOGY.md && git log -1 --pretty=%s | grep -qF "docs(15-07): drop docs/v1/standards/METHODOLOGY.md" && echo "OK: standards/METHODOLOGY.md gone, audit/METHODOLOGY.md preserved"</automated>
  </verify>
  <done>docs/v1/standards/METHODOLOGY.md deleted; audit/METHODOLOGY.md preserved; single atomic commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-07-005: Delete docs/v1/STANDARDS.md</name>
  <files>docs/v1/STANDARDS.md</files>
  <action>
Highest-risk delete last (1325 lines; researcher-identified ~84 audit/ references). The user `<open_questions_resolution>` D.2 explicitly authorizes this -- Phase 15.1 owns the audit/ reconciliation.

```bash
test -f docs/v1/STANDARDS.md || { echo "ABSENT"; exit 0; }
git rm docs/v1/STANDARDS.md
git commit -m "docs(15-07): drop docs/v1/STANDARDS.md (1325 lines; section 9 actively WRONG)

1325-line 'master standards' doc. Section 9 documents the LEGACY
src/converters/complex_converter/ subsystem as 'the' converter;
Phase 14 STALE-INT-001 verified complex_converter is no longer
imported and its tests were deleted. Reading this doc would
mislead a new contributor.

Sections 1-8 duplicate content already in ENGINE_COMPONENT_PATTERN.md,
CONVERTER_PATTERN.md, MANUAL_COMPONENT_AUTHORING.md, and CLAUDE.md.
With STANDARDS.md gone, the surviving sources are the load-bearing
authorities. The new docs/ARCHITECTURE.md (plan 15-02) and
docs/CONTRIBUTING.md (plan 15-04) cover the system-overview /
contributor-rules content STANDARDS.md tried to cover.

audit/ files referencing this STANDARDS.md (researcher identified
~84 entries via 'STANDARDS.md compliance' header pattern): see
15-07-SUMMARY.md inventory. Phase 15.1 reconciles these audit/
'STANDARDS.md compliance: Follows docs/v1/STANDARDS.md' lines as
part of its audit-reconciliation scope per D-A4.

Refs: 15-CONTEXT.md D-A5, D-A6; 15-RESEARCH.md A.9; planner D.2 -> Option A;
15-PLAN.md Open Issue #2"
```
  </action>
  <verify>
    <automated>test ! -f docs/v1/STANDARDS.md && git log -1 --pretty=%s | grep -qF "docs(15-07): drop docs/v1/STANDARDS.md" && echo "OK"</automated>
  </verify>
  <done>docs/v1/STANDARDS.md deleted; single atomic commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-07-006: Write plan SUMMARY with broken-reference inventory</name>
  <files>.planning/phases/15-documentation-sweep/15-07-SUMMARY.md</files>
  <action>
Create the plan SUMMARY capturing the broken-reference inventory for Phase 15.1 handoff. The file is committed as part of standard GSD plan closure.

```bash
cat > .planning/phases/15-documentation-sweep/15-07-SUMMARY.md <<'SUMMARY'
---
phase: 15
plan: 7
slug: standards-drop-set
type: summary
status: complete
completed: 2026-05-11
---

# Plan 15-07 Summary -- Standards DROP set (4 files deleted)

*Last updated: 2026-05-11*

## Outcome

4 files deleted from the standards-zone in 4 atomic commits per D-E1:

| # | File | Lines | Commit |
|---|------|------:|--------|
| 1 | docs/v1/standards/NEXT_MILESTONE_GUIDE.md | 159 | docs(15-07): drop docs/v1/standards/NEXT_MILESTONE_GUIDE.md |
| 2 | docs/v1/standards/AUDIT_REPORT_TEMPLATE.md | 496 | docs(15-07): drop docs/v1/standards/AUDIT_REPORT_TEMPLATE.md |
| 3 | docs/v1/standards/METHODOLOGY.md | 207 | docs(15-07): drop docs/v1/standards/METHODOLOGY.md |
| 4 | docs/v1/STANDARDS.md | 1325 | docs(15-07): drop docs/v1/STANDARDS.md |

**Total lines removed: 2187.**

All deletions per user `<open_questions_resolution>` D.2 (DELETE in Phase 15; broken audit/ references captured here as Phase 15.1 handoff).

## Broken-Cross-Reference Inventory (Phase 15.1 Handoff)

The following audit/ files referenced the now-deleted docs. Phase 15.1 (Documentation Audit Reconciliation) is responsible for fixing these references as part of audit-content reconciliation against current code.

### Files referencing docs/v1/STANDARDS.md

(Paste the full list from `/tmp/15-07-inventory/standards-refs.txt` here. Each line is an audit/ file path -- typically referenced via a 'STANDARDS.md compliance' header pattern -- e.g., `| **STANDARDS.md compliance** | Follows docs/v1/STANDARDS.md |`.)

### Files referencing docs/v1/standards/METHODOLOGY.md

(Paste the full list from `/tmp/15-07-inventory/methodology-refs.txt` here.)

### Files referencing docs/v1/standards/AUDIT_REPORT_TEMPLATE.md

(Paste the full list from `/tmp/15-07-inventory/audit-tpl-refs.txt` here.)

### Files referencing docs/v1/standards/NEXT_MILESTONE_GUIDE.md

(Paste the full list from `/tmp/15-07-inventory/next-ms-refs.txt` here. Expected: zero or near-zero matches.)

## Phase 15.1 Reconciliation Guidance

For each audit/ file in the inventory:
1. Determine whether the reference is structural (e.g., 'follows STANDARDS.md compliance') or content (e.g., 'see AUDIT_REPORT_TEMPLATE.md section X').
2. Structural references: replace with reference to surviving authority -- typically `docs/CONTRIBUTING.md` Rule N or `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` (post-rename).
3. Content references: replace with the actual content guidance (one of the surviving docs covers it).
4. If neither: mark the reference as `legacy -- removed in Phase 15` and revise the audit doc to stand alone.

Git resurrect (if any deleted doc IS needed):
```bash
git log --diff-filter=D --summary -- docs/v1/STANDARDS.md
git show <commit-hash>:docs/v1/STANDARDS.md > /tmp/standards.md.recovered
```

## Constraints Honored

- D-A4: no `docs/v1/audit/**` file modified by Phase 15-07. The inventory is enumerated only; reconciliation is Phase 15.1.
- D-B4: CLAUDE.md not modified (sanity check returned zero references to the DROP set; preserved).
- D-E1: 4 atomic commits, one logical change each.
- D-E3: no `src/` modification.

SUMMARY

git add .planning/phases/15-documentation-sweep/15-07-SUMMARY.md
git commit -m "docs(15-07): SUMMARY with broken-reference inventory for 15.1 handoff

Captures the 4-file DROP outcome + the audit/ broken-reference
inventory enumerated pre-deletion. Phase 15.1 (Documentation Audit
Reconciliation) uses this inventory to fix audit/ references as
part of audit-content reconciliation against current code.

Refs: 15-CONTEXT.md D-A4; 15-PLAN.md Open Issue #2"
```

The executor must paste the actual contents of the four `/tmp/15-07-inventory/*.txt` files into the corresponding sections of the SUMMARY before commit. Empty files are valid (e.g., NEXT_MILESTONE_GUIDE references may be zero); the section reads `(none found)` in that case.
  </action>
  <verify>
    <automated>test -f .planning/phases/15-documentation-sweep/15-07-SUMMARY.md && grep -qF "Broken-Cross-Reference Inventory" .planning/phases/15-documentation-sweep/15-07-SUMMARY.md && grep -qF "Phase 15.1 Reconciliation Guidance" .planning/phases/15-documentation-sweep/15-07-SUMMARY.md && echo "OK"</automated>
  </verify>
  <done>15-07-SUMMARY.md committed with full inventory; Phase 15.1 handoff captured.</done>
</task>

</tasks>

<verification_gate>

Plan 15-07 is GREEN when:
1. All 4 DROP-set files absent from working tree (`test ! -f` returns true for each).
2. `docs/v1/audit/METHODOLOGY.md` STILL EXISTS (D-A4 preserved; different file).
3. 4 atomic delete commits landed, plus 1 SUMMARY commit (5 commits total).
4. `15-07-SUMMARY.md` exists with cross-reference inventory + Phase 15.1 reconciliation guidance.
5. CLAUDE.md not modified.
6. No `src/` file modified.
7. No file under `docs/v1/audit/` modified.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-07): drop docs/v1/standards/NEXT_MILESTONE_GUIDE.md` | 1 delete |
| 2 | `docs(15-07): drop docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | 1 delete |
| 3 | `docs(15-07): drop docs/v1/standards/METHODOLOGY.md` | 1 delete |
| 4 | `docs(15-07): drop docs/v1/STANDARDS.md` | 1 delete |
| 5 | `docs(15-07): SUMMARY with broken-reference inventory for 15.1 handoff` | `.planning/phases/15-documentation-sweep/15-07-SUMMARY.md` |

(Total: 5 commits; 4 deletes + 1 SUMMARY.)

</commit_map>
