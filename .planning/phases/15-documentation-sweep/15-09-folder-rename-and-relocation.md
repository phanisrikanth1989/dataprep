---
phase: 15
plan: 9
slug: folder-rename-and-relocation
type: execute
wave: 2
depends_on: [15-07, 15-08]
files_modified:
  - docs/v1/standards/                        # RENAMED -> docs/v1/patterns/ (entire directory)
  - docs/v1/patterns/                         # NEW (rename target)
  - docs/v1/BaseComponent-Info.md             # MOVED to docs/v1/patterns/BaseComponent-Info.md
  - docs/v1/patterns/BaseComponent-Info.md    # NEW (move target)
autonomous: true
requirements: [DOCS-02]
must_haves:
  truths:
    - "docs/v1/standards/ no longer exists (renamed)"
    - "docs/v1/patterns/ exists with the 4 surviving standards files (ENGINE_COMPONENT_PATTERN, ENGINE_TEST_PATTERN, CONVERTER_PATTERN, TEST_PATTERN, MANUAL_COMPONENT_AUTHORING -- total 5 files from the rename) plus BaseComponent-Info.md (moved separately from docs/v1/)"
    - "docs/v1/BaseComponent-Info.md no longer exists at docs/v1/ root (moved into patterns/)"
    - "docs/v1/talend_to_v1_converter_guide.md STAYS at docs/v1/ root per planner D.7 (NOT moved)"
    - "docs/v1/audit/ directory untouched (D-A4)"
    - "After this plan, docs/v1/ contains exactly: patterns/ + audit/ + talend_to_v1_converter_guide.md (3 entries)"
    - "git mv preserves file history -- git log --follow on each moved file still shows pre-rename commits"
    - "Two atomic commits per D-E1: one for the rename, one for the BaseComponent-Info.md move"
  artifacts:
    - path: docs/v1/patterns/
      provides: post-rename pattern directory containing 6 files (5 from standards/ rename + BaseComponent-Info.md moved in)
    - path: docs/v1/patterns/BaseComponent-Info.md
      provides: reference card colocated with ENGINE_COMPONENT_PATTERN.md
  key_links:
    - from: docs/CONTRIBUTING.md (already landed in plan 15-04)
      to: docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md
      via: Rule 5 cross-reference -- the link works AFTER this plan lands (CONTRIBUTING.md was authored anticipating the rename per D-D1)
      pattern: "patterns/MANUAL_COMPONENT_AUTHORING"
    - from: docs/COMPONENT_REFERENCE.md (already landed in plan 15-03)
      to: docs/v1/patterns/
      via: "See Also" cross-reference; valid after this plan
      pattern: "docs/v1/patterns/"
---

<objective>
Rename `docs/v1/standards/` to `docs/v1/patterns/` per planner D.4 resolution (researcher Option A: "patterns/" describes the surviving content better than "standards/" or "conventions/"). Move `docs/v1/BaseComponent-Info.md` from `docs/v1/` root into `docs/v1/patterns/BaseComponent-Info.md` per D-D2 + planner D.5/D.7 resolution. Use `git mv` so file history is preserved. The 7 KEEP+FIX patches from plan 15-08 are already in place; this plan only moves files, no content changes.
</objective>

<scope>
- `git mv docs/v1/standards docs/v1/patterns` (directory rename).
- `git mv docs/v1/BaseComponent-Info.md docs/v1/patterns/BaseComponent-Info.md` (single-file move).
- Each operation is its own atomic commit per D-E1.
- After: `docs/v1/` contains `patterns/`, `audit/`, and `talend_to_v1_converter_guide.md` only.
- Cross-reference re-check: scan for any in-repo doc that cites `docs/v1/standards/` path (e.g., CONTRIBUTING.md if it did NOT use the post-rename path). Fix any internal Phase-15-authored doc that did so. NOT-IN-SCOPE: `docs/v1/audit/` references (D-A4; captured by plan 15-07 SUMMARY).
- NO move of `docs/v1/talend_to_v1_converter_guide.md` (planner D.7 resolution: STAYS at `docs/v1/`).
- NO modification of `docs/v1/audit/` (D-A4).
- NO modification of CLAUDE.md (D-B4).
- NO modification of `src/` (D-E3).
</scope>

<out_of_scope>
- Content changes to the moved files (plan 15-08 owned all content fixes, already complete).
- Moving `talend_to_v1_converter_guide.md` -- planner D.7 keeps it at `docs/v1/` root.
- Fixing audit/ cross-references that now point at `docs/v1/standards/` (gone) -- Phase 15.1 owns this as part of the broken-reference inventory enumerated in plan 15-07 SUMMARY.
- Symlinks / shims at the old path -- no compatibility layer (per Phase 14 rewrite-over-patch philosophy / project memory `feedback_rewrite_over_patch`).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-D1 (rename consideration), D-D2 (sibling moves), D-E1 (atomic commits)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section D.4 (planner -> patterns/), D.5 + A.10 (BaseComponent-Info moves into patterns/), D.7 + A.11 (talend_to_v1_converter_guide STAYS at docs/v1/)
- `.planning/phases/15-documentation-sweep/15-PLAN.md` (acknowledges plan 15-04 CONTRIBUTING.md and 15-03 COMPONENT_REFERENCE.md already cite `docs/v1/patterns/` -- the rename in this plan makes those links valid)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-09-001: Pre-rename inventory snapshot</name>
  <files>(read-only)</files>
  <action>
Before the rename, snapshot the standards/ directory contents to confirm expected post-rename state. Per plan 15-07 the DROP set is gone; per plan 15-08 the KEEP+FIX set is patched in place. After plan 15-07 the standards/ directory should contain exactly 5 files: ENGINE_COMPONENT_PATTERN.md, ENGINE_TEST_PATTERN.md, CONVERTER_PATTERN.md, TEST_PATTERN.md, MANUAL_COMPONENT_AUTHORING.md.

```bash
ls -1 docs/v1/standards/
ls -1 docs/v1/
```

Expected output for `docs/v1/standards/`:
```
CONVERTER_PATTERN.md
ENGINE_COMPONENT_PATTERN.md
ENGINE_TEST_PATTERN.md
MANUAL_COMPONENT_AUTHORING.md
TEST_PATTERN.md
```

Expected output for `docs/v1/`:
```
BaseComponent-Info.md
audit
standards
talend_to_v1_converter_guide.md
```

If counts differ, STOP and reconcile -- plan 15-07 or 15-08 missed something.
  </action>
  <verify>
    <automated>test "$(ls -1 docs/v1/standards/ 2>/dev/null | wc -l | tr -d ' ')" = "5" && ls docs/v1/BaseComponent-Info.md docs/v1/talend_to_v1_converter_guide.md docs/v1/audit docs/v1/standards >/dev/null && echo "OK: pre-rename state verified"</automated>
  </verify>
  <done>Pre-rename state: standards/ has 5 files; docs/v1/ has 4 entries (BaseComponent-Info.md, audit/, standards/, talend_to_v1_converter_guide.md).</done>
</task>

<task type="auto">
  <name>Task 15-09-002: Rename docs/v1/standards/ -> docs/v1/patterns/</name>
  <files>docs/v1/standards/, docs/v1/patterns/</files>
  <action>
Directory rename with history preservation:

```bash
git mv docs/v1/standards docs/v1/patterns
git status   # confirm 5 R (renamed) entries
git commit -m "docs(15-09): rename docs/v1/standards/ -> docs/v1/patterns/ (D-D1)

Surviving content (5 files post-15-07 DROP set):
- ENGINE_COMPONENT_PATTERN.md
- ENGINE_TEST_PATTERN.md
- CONVERTER_PATTERN.md
- TEST_PATTERN.md
- MANUAL_COMPONENT_AUTHORING.md

These are authoring patterns / templates / contributor guides --
'patterns/' describes them more accurately than 'standards/'
(which implied a compliance regime / audit framework that
METHODOLOGY.md + AUDIT_REPORT_TEMPLATE.md + STANDARDS.md
collectively defined). With those 4 files dropped in plan 15-07,
'standards/' no longer fits.

git mv preserves history: 'git log --follow docs/v1/patterns/<file>'
shows pre-rename commits.

NOTE: docs/v1/audit/ files that referenced 'docs/v1/standards/' are
now broken. The inventory was captured in 15-07-SUMMARY.md for
Phase 15.1 reconciliation per D-A4 (Phase 15 does not touch audit/).

Refs: 15-CONTEXT.md D-D1; 15-RESEARCH.md D.4 -> Option A"
```

If any of the 5 files SHOULD be renamed-with-content-change instead of pure-rename, this is the wrong plan -- plan 15-08 owns content changes and is already complete. Pure rename only here.
  </action>
  <verify>
    <automated>test ! -d docs/v1/standards && test -d docs/v1/patterns && test "$(ls -1 docs/v1/patterns/ | wc -l | tr -d ' ')" = "5" && git log -1 --pretty=%s | grep -qF "docs(15-09): rename docs/v1/standards/ -> docs/v1/patterns/" && echo "OK"</automated>
  </verify>
  <done>standards/ -> patterns/ rename committed with history preserved; 5 files at new location.</done>
</task>

<task type="auto">
  <name>Task 15-09-003: Move docs/v1/BaseComponent-Info.md into docs/v1/patterns/</name>
  <files>docs/v1/BaseComponent-Info.md, docs/v1/patterns/BaseComponent-Info.md</files>
  <action>
Single-file move with history preservation:

```bash
git mv docs/v1/BaseComponent-Info.md docs/v1/patterns/BaseComponent-Info.md
git status   # confirm 1 R (renamed) entry
git commit -m "docs(15-09): move BaseComponent-Info.md into docs/v1/patterns/ (D-D2)

BaseComponent-Info.md is a reference card colocated with the
ENGINE_COMPONENT_PATTERN.md gold-standard authoring guide.
Same contributor audience. Per planner D.5 -> Option A the gaps
section was disambiguated (FIXED markers + OPEN markers) in
plan 15-08; this plan only moves the file.

git mv preserves history.

talend_to_v1_converter_guide.md STAYS at docs/v1/ per planner D.7 ->
Option A (different audience: user-facing usage guide vs
contributor-facing pattern).

Refs: 15-CONTEXT.md D-D2; 15-RESEARCH.md A.10 + D.5; planner D.7"
```
  </action>
  <verify>
    <automated>test ! -f docs/v1/BaseComponent-Info.md && test -f docs/v1/patterns/BaseComponent-Info.md && test -f docs/v1/talend_to_v1_converter_guide.md && git log -1 --pretty=%s | grep -qF "docs(15-09): move BaseComponent-Info.md into docs/v1/patterns/" && echo "OK"</automated>
  </verify>
  <done>BaseComponent-Info.md moved into patterns/; talend_to_v1_converter_guide.md preserved at docs/v1/; commit landed.</done>
</task>

<task type="auto">
  <name>Task 15-09-004: Cross-reference re-check on Phase-15-authored docs</name>
  <files>(read-only -- scan for broken internal references)</files>
  <action>
The 4 canonical docs + root README authored in wave 1 (plans 15-02..15-06) and the KEEP+FIX docs from plan 15-08 may cite paths that this plan changed. Specifically:
- Wave 1 docs were authored anticipating the rename -- they reference `docs/v1/patterns/` (post-rename path) by design. NOT broken.
- KEEP+FIX docs from plan 15-08 stayed in place during 15-08; intra-doc references to other patterns/ files would only be broken IF an intra-doc cross-link uses the OLD path.

Scan:

```bash
# 1. Find any Phase-15-authored doc still referencing the old docs/v1/standards/ path:
grep -rn "docs/v1/standards/" docs/ README.md 2>/dev/null

# 2. Find any reference to docs/v1/BaseComponent-Info.md at old path:
grep -rn "docs/v1/BaseComponent-Info\.md" docs/ README.md 2>/dev/null
```

Expected: ZERO matches from #1 (Phase 15 docs were planned with patterns/ from the start). ZERO matches from #2 (no Phase 15 doc cites BaseComponent-Info.md by old path).

If any match is found in a Phase-15-AUTHORED doc (i.e., NOT under `docs/v1/audit/` which is OFF LIMITS per D-A4), fix the doc in place + commit as `docs(15-09): fix stale cross-reference in <file> after rename`. If a match is found in `docs/v1/audit/`, do NOT touch it -- record in plan SUMMARY as additional Phase 15.1 reconciliation work.
  </action>
  <verify>
    <automated>phase15_standards_refs=$(grep -rln "docs/v1/standards/" docs/v1/patterns docs/*.md README.md 2>/dev/null | wc -l | tr -d ' ') && test "$phase15_standards_refs" = "0" && echo "OK: no broken refs in Phase 15 docs"</automated>
  </verify>
  <done>Cross-reference scan complete; any broken Phase 15 doc references fixed (typically zero); audit/ matches recorded for 15.1.</done>
</task>

</tasks>

<verification_gate>

Plan 15-09 is GREEN when:
1. `docs/v1/standards/` does NOT exist.
2. `docs/v1/patterns/` exists and contains 6 files (5 from rename + BaseComponent-Info.md moved in).
3. `docs/v1/BaseComponent-Info.md` does NOT exist at `docs/v1/` root.
4. `docs/v1/talend_to_v1_converter_guide.md` STILL EXISTS at `docs/v1/` root (per planner D.7).
5. `docs/v1/audit/` directory untouched.
6. 2 atomic commits landed (rename + move).
7. Phase 15-authored docs reference only the new `docs/v1/patterns/` path.
8. CLAUDE.md not modified; `src/` not modified.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-09): rename docs/v1/standards/ -> docs/v1/patterns/ (D-D1)` | 5 git-renames |
| 2 | `docs(15-09): move BaseComponent-Info.md into docs/v1/patterns/ (D-D2)` | 1 git-rename |

(Total: 2 commits. Add a third commit only if Task 15-09-004 found a Phase 15-authored stale reference to fix.)

</commit_map>
