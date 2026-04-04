# Next Milestone: Standardization Playbook

Step-by-step guide for the v1.1 Standardization milestone.

---

## Pre-Milestone Setup (do this FIRST)

### Step 1: Clear context
```
/clear
```

### Step 2: Refresh codebase map
```
/gsd:map-codebase
```
This refreshes the 7 codebase docs with post-v1.0 state (13 enhanced converters, 383 tests).

### Step 3: Clear again
```
/clear
```

### Step 4: Start new milestone
```
/gsd:new-milestone
```

When asked "What do you want to build?", use this description (copy-paste this):

> Standardize all 54 v1 engine components across 4 dimensions:
>
> 1. **Audit reports** — rewrite all 54 to match the gold standard template in `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md`. Re-research every component against .item files and _java.xml.
> 2. **Converter code** — standardize all 49 applicable converters to match the pattern in `docs/v1/standards/CONVERTER_PATTERN.md`. Re-verify correctness against .item/.xml sources.
> 3. **Test cases** — standardize all converter tests to match `docs/v1/standards/TEST_PATTERN.md`. Ensure comprehensive coverage per the template.
> 4. **File organization** — verify consistent folder structure across `src/converters/talend_to_v1/components/`, `tests/converters/talend_to_v1/components/`, and `docs/v1/audit/components/`.
>
> The 5 Python/Swift components (PythonComponent, PythonRowComponent, PythonDataFrameComponent, SwiftTransformer, SwiftBlockFormatter) get audit report standardization only — converter is N/A.
>
> Gold standard templates are in `docs/v1/standards/`. These are the canonical reference for every agent.

### Step 5: During questioning
Key points to convey:
- Gold standard templates already exist in `docs/v1/standards/` — agents MUST reference them
- Methodology framework exists in `docs/v1/standards/METHODOLOGY.md` — agents should follow the two-pass review process and edge-case checklist
- .item file is source of truth over _java.xml
- Re-research EVERY component — don't trust prior work
- Framework params (TSTATCATCHER_STATS, LABEL) are universal
- Full D-11 sweep on audit reports — all sections mandatory
- needs_review entries for all engine gaps

### Step 6: Workflow preferences
- Mode: YOLO
- Granularity: Standard (the 54 components will naturally group into 7-8 phases)
- Parallel: Yes
- Git tracking: Yes
- Research: Yes (mandatory — re-verifying every component)
- Plan check: Yes
- Verifier: Yes
- AI Models: Quality (opus everywhere)

### Step 7: Research decision
- Always "Research first" — this milestone is ABOUT re-verification

### Step 8: Requirements
When defining requirements, suggest these categories:
- **Audit reports** (54 components): One requirement per phase batch
- **Converter code** (49 components): One requirement per phase batch
- **Tests** (49 components): One requirement per phase batch
- **File organization**: One cross-cutting requirement
- **Scorecard update**: One requirement for final scorecard refresh

### Step 9: Roadmap
Suggested phase structure:

| Phase | Components | Scope |
|-------|-----------|-------|
| 1 | Gold standard validation | Validate templates against 2-3 existing best reports, refine if needed |
| 2 | Simple converters (tSleep, tDie, tWarn, tSetGlobalVar, tFileTouch, tFileDelete, etc.) | ~10 components, simplest fixes |
| 3 | File I/O family (tFileInput*, tFileOutput*, tFileArchive, etc.) | ~15 components |
| 4 | Transform family (tFilterRow, tSortRow, tJoin, tNormalize, etc.) | ~10 components |
| 5 | Extract + Reshape family (tExtract*, tPivot*, tUnpivot*, etc.) | ~8 components |
| 6 | Complex components (tMap, tXMLMap, tAggregateRow, etc.) | ~6 most complex |
| 7 | Python/Swift + custom (5 components) | Audit reports only |
| 8 | Final sweep | Scorecard refresh, cross-cutting docs, file org verification |

---

## Per-Phase Workflow

For each phase after Phase 1:

```
/clear
/gsd:discuss-phase N          # usually "carry forward" after Phase 2
/gsd:plan-phase N              # research + plan + verify
/gsd:execute-phase N           # parallel execution
/gsd:verify-work N             # UAT
```

### What each agent does per component:

1. **Research agent** (Pass 1 — Initial Audit):
   - Fetch _java.xml + search for .item examples from Talaxie GitHub
   - Read engine source (every line) for feature parity analysis
   - Read converter source for audit
   - Run METHODOLOGY.md edge-case checklist

2. **Planner**: Create tasks that reference gold standard templates explicitly

3. **Executor**: 
   - Read gold standard templates FIRST (AUDIT_REPORT_TEMPLATE.md, CONVERTER_PATTERN.md, TEST_PATTERN.md)
   - Re-verify converter against research
   - Standardize converter code to match CONVERTER_PATTERN.md
   - Standardize tests to match TEST_PATTERN.md
   - Rewrite audit report to match AUDIT_REPORT_TEMPLATE.md (all 10 mandatory sections + appendices)
   - Resolved issues use strikethrough: `~~P1~~ **FIXED**`
   - Section 9 counts must match individual sections
   - Full D-11 sweep — all sections mandatory

4. **Code reviewer** (Pass 2 — Adversarial Review per METHODOLOGY.md):
   - Read report AND source code
   - Mindset: "Find at least 3-5 issues the report missed"
   - Focus on edge cases, cross-class interactions, behavioral subtleties
   - Findings incorporated back into report

5. **Verifier**: Check all 3 artifacts match their templates

---

## Key Prompts for Context

When the GSD questioning/discuss phases ask for context, reference:

```
Gold standard templates:
- docs/v1/standards/AUDIT_REPORT_TEMPLATE.md
- docs/v1/standards/CONVERTER_PATTERN.md
- docs/v1/standards/TEST_PATTERN.md

These are CANONICAL — every agent must read them before making changes.
```

---

## Tips from v1.0

1. **Verify after every phase** — don't skip `/gsd:verify-work`
2. **Research is worth the tokens** — it catches real issues every time
3. **Clear between major operations** — keeps agents sharp
4. **Challenge the research** when your domain knowledge says something's off
5. **Worktree summaries may get lost** during parallel execution — reconstruct immediately after merge
6. **Batch similar components** in the same phase for efficiency
