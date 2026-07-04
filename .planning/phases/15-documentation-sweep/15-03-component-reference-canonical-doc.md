---
phase: 15
plan: 3
slug: component-reference-canonical-doc
type: execute
wave: 1
depends_on: [15-01]
files_modified:
  - docs/COMPONENT_REFERENCE.md   # NEW (~200-300 lines, inline registry-driven index)
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "docs/COMPONENT_REFERENCE.md exists at docs/ root (D-A3)"
    - "Header *Last updated: 2026-05-11* on line 2 (D-C2)"
    - "ASCII-only per D-C1"
    - "Inline registry-driven inventory: every component name that REGISTRY exposes appears in a category table (Aggregate / Context / Control / Database / File / Iterate / Transform)"
    - "Every row maps: V1 Name -> Talend Alias -> source path -> test path -> audit doc path (docs/v1/audit/components/*.md)"
    - "PythonDataFrameComponent, FileInputJSON, SwiftTransformer, SwiftBlockFormatter are explicitly noted as 'Registered (Phase 14 BUG-PDC/SWIFT/FIJ fix)' per D-C6"
    - "Every cited source path is grep-confirmed to exist"
    - "Doc DOES NOT duplicate per-component audit depth (D-B3); points at docs/v1/audit/components/ for that"
    - "Length within target 200-300 lines"
  artifacts:
    - path: docs/COMPONENT_REFERENCE.md
      provides: registry-driven index of every engine component; the per-component truth source until Phase 15.1 reconciles audit/
      min_lines: 150
      contains: "# Component Reference"
  key_links:
    - from: docs/COMPONENT_REFERENCE.md
      to: src/v1/engine/component_registry.py
      via: cited as the canonical registry; doc mirrors its current registered names
      pattern: "component_registry"
    - from: docs/COMPONENT_REFERENCE.md
      to: docs/v1/audit/components/*.md
      via: per-row pointer column; D-B3 explicit (this doc does NOT duplicate audit depth)
      pattern: "docs/v1/audit/components"
    - from: docs/COMPONENT_REFERENCE.md
      to: docs/ARCHITECTURE.md
      via: "See Also" reference back to system overview
      pattern: "ARCHITECTURE\\.md"
---

<objective>
Create `docs/COMPONENT_REFERENCE.md` (~200-300 lines): a registry-driven inline reference table mapping every engine component to its source file, test file, Talend alias, and per-component audit doc pointer. Per D-C6 the doc is registry-driven; per D-B3 it does NOT duplicate audit/ depth; per planner D.3 resolution this is an INLINE table (no `scripts/gen_component_reference.py` -- deferred). Per D-C6, the 4 components registered via Phase 14 BUG-PDC/SWIFT/FIJ source fixes are explicitly flagged so a reader sees they are now production-ready.
</objective>

<scope>
- Create `docs/COMPONENT_REFERENCE.md` from scratch.
- Source of truth for which components to list: enumerate the live `src/v1/engine/component_registry.py` REGISTRY at planning time by reading the `__init__.py` registration chain or walking the registered names. Cross-check against the actual component files under `src/v1/engine/components/{aggregate,context,control,database,file,iterate,transform}/`.
- Inline reference tables, one per category. Each row: V1 PascalCase name, Talend alias(es), source path, test path, audit doc path.
- Special-flag rows for the 4 Phase 14 fixes (PythonDataFrameComponent, FileInputJSON, SwiftTransformer, SwiftBlockFormatter) -- a NOTE column or trailing parenthetical noting "Registered Phase 14 (BUG-PDC/BUG-FIJ/BUG-SWIFT)".
- Special-flag rows for Phase 12 new outputs (FileOutputXML, AdvancedFileOutputXML).
- Out-of-scope components section: pull V2-deferred items from `.planning/REQUIREMENTS.md` (COMP-V2-* and similar).
- ASCII-only per D-C1; `*Last updated: 2026-05-11*` header per D-C2.
- Single commit: `docs(15-03): add docs/COMPONENT_REFERENCE.md (registry-driven inline index)`.
</scope>

<out_of_scope>
- `scripts/gen_component_reference.py` generation tooling -- DEFERRED per planner D.3 resolution and CONTEXT.md "Deferred Ideas". Inline table for Phase 15. Capture follow-on as a deferred-items note in plan SUMMARY.
- Per-component audit depth -- D-B3 explicit. Per-row pointer to `docs/v1/audit/components/*.md` ONLY; never copy content.
- Editing any file under `docs/v1/audit/` -- D-A4 OFF LIMITS.
- ARCHITECTURE.md (plan 15-02 -- this doc REFERENCES it).
- CLAUDE.md edits (D-B4).
- src/ changes (D-E3).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A3 (docs/ root), D-B3 (no audit depth duplication), D-C6 (registry-driven; planner picks inline vs script)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section B.2 (skeleton for COMPONENT_REFERENCE.md; researcher recommends Option A inline)
- `src/v1/engine/component_registry.py` (live REGISTRY)
- `src/v1/engine/engine.py:18, 140` (REGISTRY import + lookup -- canonical name surface)
- `src/v1/engine/components/` (per-category subdirs)
- `tests/v1/engine/components/` (test mirror)
- `docs/v1/audit/components/` (per-component audit pointer targets -- READ ONLY)
- `.planning/REQUIREMENTS.md` (V2 deferred component list, COMP-V2-*)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (BUG-PDC/SWIFT/FIJ commit refs)
- `.planning/phases/12-xml-components-audit-harden-output/12-PHASE-SUMMARY.md` if exists (FileOutputXML + AdvancedFileOutputXML new-component refs)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-03-001: Enumerate the live REGISTRY</name>
  <files>(read-only)</files>
  <action>
Walk the live engine REGISTRY to build the source-of-truth component list. Run from project root:

```bash
# 1. Find every component file (will produce the inventory):
find src/v1/engine/components -type f -name "*.py" -not -name "__init__.py" | sort

# 2. Find every @REGISTRY.register decoration (live registration sites):
grep -rn "@REGISTRY.register" src/v1/engine/components/ | sort

# 3. Cross-check the 4 Phase 14 registration fixes are present:
grep -n "@REGISTRY.register" src/v1/engine/components/transform/python_dataframe_component.py
grep -n "@REGISTRY.register" src/v1/engine/components/file/file_input_json.py
grep -n "@REGISTRY.register" src/v1/engine/components/transform/swift_transformer.py
grep -n "@REGISTRY.register" src/v1/engine/components/transform/swift_block_formatter.py

# 4. List existing audit doc files (pointer targets):
find docs/v1/audit/components -name "*.md" | sort > /tmp/15-03-audit-files.txt

# 5. Find every test mirror:
find tests/v1/engine/components -type f -name "test_*.py" | sort

# 6. REQUIREMENTS.md V2 deferred list:
grep -n "COMP-V2" .planning/REQUIREMENTS.md | head -30
```

Capture the output as the manifest the table will be built from. If item 3 returns ZERO matches for any of the 4 files, that's a problem -- Phase 14 BUG-* claims to have fixed them. If verification fails, STOP and reconcile with Phase 14 PHASE-SUMMARY before authoring the doc.
  </action>
  <verify>
    <automated>grep -q "@REGISTRY.register" src/v1/engine/components/transform/python_dataframe_component.py && grep -q "@REGISTRY.register" src/v1/engine/components/file/file_input_json.py && grep -q "@REGISTRY.register" src/v1/engine/components/transform/swift_transformer.py && grep -q "@REGISTRY.register" src/v1/engine/components/transform/swift_block_formatter.py && echo "OK: 4 Phase 14 fix registrations present"</automated>
  </verify>
  <done>Live REGISTRY enumerated; 4 Phase 14 registration fixes confirmed present; component manifest captured for table authoring.</done>
</task>

<task type="auto">
  <name>Task 15-03-002: Author docs/COMPONENT_REFERENCE.md</name>
  <files>docs/COMPONENT_REFERENCE.md</files>
  <action>
Create the file with the structure below. Length target: 200-300 lines. ASCII-only per D-C1.

Required H2 sections (in order):

1. `# Component Reference` (H1, line 1)
2. `*Last updated: 2026-05-11*` (line 2 exact)
3. `## Overview` -- 1 paragraph: this doc is a registry-driven index. For per-component depth, see `docs/v1/audit/components/`. Per D-B3 this doc does NOT duplicate audit content -- it points.
4. `## How To Read This Doc` -- explain the columns: V1 Name (PascalCase) | Talend Alias (tCamelCase) | Source | Tests | Audit | Notes.
5. `## Component Inventory` -- the bulk, one H3 subsection per category. Use the Task 15-03-001 manifest as the source. Required category subsections, in this order:
   - `### Aggregate` (e.g., AggregateRow / tAggregateRow; UniqueRow / tUniqRow)
   - `### Context` (e.g., ContextLoad / tContextLoad; SetGlobalVar / tSetGlobalVar)
   - `### Control` (e.g., Die / tDie; SendMail / tSendMail; LogRow / tLogRow if classified here -- verify category)
   - `### Database` (OracleConnection, OracleRow, OracleOutput, etc. -- enumerate from `src/v1/engine/components/database/`)
   - `### File` (FileInputDelimited, FileInputExcel, FileInputJSON [NOTE Phase 14 BUG-FIJ-001/002 registration fix], FileInputPositional, FileInputRaw, FileInputXML, FileInputMSXML, FileOutputDelimited, FileOutputExcel, FileOutputPositional, FileOutputXML [NOTE Phase 12 new], AdvancedFileOutputXML [NOTE Phase 12 new], FileList, FileExist, FileRowCount, FileArchive, etc. -- enumerate)
   - `### Iterate` (FlowToIterate, FileList if classified here, FileExist if classified here -- verify by file location; FileList lives at `src/v1/engine/components/file/file_list.py` per STATE.md Phase 14-08 references)
   - `### Transform` (Map, FilterRows, FilterColumns, SortRow, Join, Unite, Normalize, JavaComponent, JavaRowComponent, PythonComponent, PythonRowComponent, PythonDataFrameComponent [NOTE Phase 14 BUG-PDC-001/002 registration fix], SwiftTransformer [NOTE Phase 14 BUG-SWIFT-001..005 fixes], SwiftBlockFormatter [NOTE Phase 14 BUG-SWIFT-001..005 fixes], LogRow, ConvertType, XMLMap, ExtractXMLField, ExtractJSONFields, ExtractDelimitedFields, ExtractPositionalFields, ExtractRegexFields, Replace, etc.)
6. `## Out-of-Scope Components` -- bullet list of COMP-V2-* deferred components from REQUIREMENTS.md (tMSSql* family, V2-specific items). Cite REQUIREMENTS.md.
7. `## How To Regenerate This Reference` -- two paragraphs:
   - Option A (Phase 15): manual update at component-add-time. CONTRIBUTING.md Rule 5 (registry+abstract discipline) covers the contributor-side flow.
   - Option B (deferred): `scripts/gen_component_reference.py` that walks REGISTRY and emits this table. Captured as a deferred follow-on in CONTEXT.md "Deferred Ideas"; the script is implementable in ~50-100 lines stdlib but not required for Phase 15. Phase 15.1 or a later quick task may ship it.
8. `## See Also` -- bullets:
   - `docs/ARCHITECTURE.md` -- system overview
   - `docs/CONTRIBUTING.md` -- authoring conventions including registry+abstract discipline
   - `docs/v1/audit/components/` -- per-component audit depth (Phase 15.1 will reconcile against current code)
   - `docs/v1/patterns/` -- pattern docs for component authoring (post-rename location; landing in plan 15-09)

Table column convention (Markdown):

```
| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| AggregateRow | tAggregateRow | src/v1/engine/components/aggregate/aggregate_row.py | tests/v1/engine/components/aggregate/test_aggregate_row.py | docs/v1/audit/components/transform/tAggregateRow.md (TBD path verify) | -- |
```

For the Notes column: leave empty (`--`) for standard rows. For the 4 Phase 14 fixes and 2 Phase 12 new outputs, use the explicit note language per the section listings above. If an audit doc does NOT exist for a component (the audit dir is incomplete), the cell value is `not yet authored (Phase 15.1 backlog)`.

ASCII discipline: same as plan 15-02 -- `--`, no smart quotes, no emoji.

The executor MUST grep-verify every source path and test path before adding the row. Doc-only phase -- if a source file is missing, the row simply doesn't appear; the doc reflects reality, not aspiration.
  </action>
  <verify>
    <automated>test -f docs/COMPONENT_REFERENCE.md && head -2 docs/COMPONENT_REFERENCE.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/COMPONENT_REFERENCE.md)" && grep -qF "BUG-PDC" docs/COMPONENT_REFERENCE.md && grep -qF "BUG-FIJ" docs/COMPONENT_REFERENCE.md && grep -qF "BUG-SWIFT" docs/COMPONENT_REFERENCE.md && grep -qE "^### Aggregate" docs/COMPONENT_REFERENCE.md && grep -qE "^### Transform" docs/COMPONENT_REFERENCE.md && lines=$(wc -l < docs/COMPONENT_REFERENCE.md) && test "$lines" -ge 150 && test "$lines" -le 400 && echo "OK: structure + Phase-14 fix notes + length=$lines"</automated>
  </verify>
  <done>COMPONENT_REFERENCE.md created; 7+ category tables; 4 Phase 14 fix rows + 2 Phase 12 new outputs flagged; ASCII verified; header verified; length 150-400 lines.</done>
</task>

<task type="auto">
  <name>Task 15-03-003: Path-existence verification sweep</name>
  <files>(read-only -- verify every cited path in the new doc)</files>
  <action>
For every `src/` and `tests/` path cited in `docs/COMPONENT_REFERENCE.md`, confirm it exists. The doc is built from grep manifests so this is a defensive double-check.

```bash
# Extract every src/ path:
grep -oE "src/[a-zA-Z0-9_/]+\.py" docs/COMPONENT_REFERENCE.md | sort -u | while read p; do
  test -f "$p" || echo "MISSING SOURCE: $p"
done

# Extract every tests/ path:
grep -oE "tests/[a-zA-Z0-9_/]+\.py" docs/COMPONENT_REFERENCE.md | sort -u | while read p; do
  test -f "$p" || echo "MISSING TEST: $p"
done

# Extract every docs/v1/audit/ path:
grep -oE "docs/v1/audit/[a-zA-Z0-9_/]+\.md" docs/COMPONENT_REFERENCE.md | sort -u | while read p; do
  test -f "$p" || echo "MISSING AUDIT: $p (use 'not yet authored (Phase 15.1 backlog)' in cell)"
done
```

Any MISSING SOURCE or MISSING TEST line: fix the doc (correct path, or remove the row if the component doesn't exist). Any MISSING AUDIT line: replace the cell with the explicit placeholder.

Record the verification log for plan 15-10's `15-VERIFICATION.md`.
  </action>
  <verify>
    <automated>missing=$(grep -oE "src/[a-zA-Z0-9_/]+\.py" docs/COMPONENT_REFERENCE.md | sort -u | while read p; do test -f "$p" || echo X; done | wc -l | tr -d ' ') && test "$missing" = "0" && echo "OK: all source paths exist"</automated>
  </verify>
  <done>All cited src/ and tests/ paths verified; missing audit/ pointers replaced with placeholder; verification log captured.</done>
</task>

<task type="auto">
  <name>Task 15-03-004: Commit</name>
  <files>docs/COMPONENT_REFERENCE.md</files>
  <action>
Atomic commit per D-E1:

```bash
git add docs/COMPONENT_REFERENCE.md
git commit -m "docs(15-03): add docs/COMPONENT_REFERENCE.md (registry-driven inline index)

Inline registry-driven reference index per D-C6 (planner D.3 -> Option A:
inline table, no generation script in Phase 15). Per D-B3 the doc points
at docs/v1/audit/components/*.md for per-component audit depth -- never
duplicates audit content.

Flags 4 Phase 14 registration fixes (BUG-PDC-001/002, BUG-FIJ-001/002,
BUG-SWIFT-001..005 trio) and 2 Phase 12 new outputs (FileOutputXML,
AdvancedFileOutputXML) so readers see what's freshly available.

A scripts/gen_component_reference.py generator is captured as a
deferred follow-on per CONTEXT.md Deferred Ideas -- not in Phase 15
scope.

Refs: 15-CONTEXT.md D-A3, D-B3, D-C6; 15-RESEARCH.md B.2; D.3 resolution"
```
  </action>
  <verify>
    <automated>git log -1 --pretty=%s | grep -qF "docs(15-03): add docs/COMPONENT_REFERENCE.md" && test "$(git diff --stat HEAD~1..HEAD -- src/ | wc -l | tr -d ' ')" = "0" && echo "OK: committed; no src/ touch"</automated>
  </verify>
  <done>Single commit landed; no src/ touched; HEAD subject matches.</done>
</task>

</tasks>

<verification_gate>

Plan 15-03 is GREEN when:
1. `docs/COMPONENT_REFERENCE.md` exists at `docs/` root.
2. `*Last updated: 2026-05-11*` on line 2.
3. ASCII-only (zero non-ASCII bytes).
4. All 7 category tables present (Aggregate / Context / Control / Database / File / Iterate / Transform).
5. 4 Phase 14 registration-fix rows explicitly flag the BUG-PDC / BUG-FIJ / BUG-SWIFT references.
6. Every cited `src/` and `tests/` path exists.
7. Length 150-400 lines (target 200-300).
8. Single commit landed; no src/ touched.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-03): add docs/COMPONENT_REFERENCE.md (registry-driven inline index)` | `docs/COMPONENT_REFERENCE.md` |

(Total: 1 commit.)

</commit_map>
