---
phase: 15
plan: 6
slug: root-readme
type: execute
wave: 1
depends_on: [15-01]
files_modified:
  - README.md     # NEW at repo root (~30-50 lines, minimal per D-D3)
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "README.md exists at repo root (NOT under docs/)"
    - "Header *Last updated: 2026-05-11* on line 2 (D-C2)"
    - "ASCII-only per D-C1"
    - "Links to docs/ARCHITECTURE.md as the primary entry point per D-D3"
    - "Links to CLAUDE.md for Claude-specific instructions per D-D3"
    - "Links to the other 3 canonical docs (COMPONENT_REFERENCE.md, CONTRIBUTING.md, DEPLOYMENT.md)"
    - "Minimal Quickstart section with 2 short CLI examples (converter + engine) per planner D.6 resolution"
    - "Length within target 30-80 lines (D-D3 minimal; planner D.6 -> Option B in spirit but tight)"
  artifacts:
    - path: README.md
      provides: repo-root entry point pointing at canonical docs
      min_lines: 25
      contains: "# DataPrep"
  key_links:
    - from: README.md
      to: docs/ARCHITECTURE.md
      via: primary entry-point link per D-D3
      pattern: "docs/ARCHITECTURE\\.md"
    - from: README.md
      to: CLAUDE.md
      via: Claude-specific instructions link per D-D3
      pattern: "CLAUDE\\.md"
---

<objective>
Add a minimal `README.md` at the repo root (D-D3) pointing at the 4 canonical docs and CLAUDE.md. Per planner D.6 resolution (researcher Option B in spirit but still tight), include 2 short CLI Quickstart examples so a new-comer can run something without one more click. ~30-80 lines, ASCII-only, header on line 2.
</objective>

<scope>
- Create `README.md` at REPO ROOT (NOT under `docs/`).
- Sections: H1 title + Last-updated header + one-paragraph project description + Quickstart (2 short CLI examples) + Documentation (links to 4 canonical docs + CLAUDE.md) + License (if applicable; otherwise omit).
- ASCII-only per D-C1; `*Last updated: 2026-05-11*` header per D-C2.
- Single commit: `docs(15-06): add root README.md (minimal per D-D3)`.
</scope>

<out_of_scope>
- Anything beyond the 4 canonical docs + CLAUDE.md links (D-D3 explicit: "No expansion beyond the 4 canonical docs").
- Build status badges (no CI per D-B1).
- Contributing-guide depth (CONTRIBUTING.md owns that; README only links).
- CLAUDE.md edits (D-B4).
- src/ changes (D-E3).
- Replicating `docs/ARCHITECTURE.md` content (the README links there).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-D3 (root README minimal)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section D.6 (planner-resolution Option B in spirit but tight)
- `.planning/PROJECT.md` (1-paragraph project description; pull-quote source)
- `docs/ARCHITECTURE.md` (plan 15-02 -- linked from README)
- `docs/COMPONENT_REFERENCE.md` (plan 15-03)
- `docs/CONTRIBUTING.md` (plan 15-04)
- `docs/DEPLOYMENT.md` (plan 15-05)
- `CLAUDE.md` (Claude-specific instructions link)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
@.planning/PROJECT.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-06-001: Confirm no pre-existing README.md at root</name>
  <files>(read-only)</files>
  <action>
Confirm there is no existing `README.md` at repo root (D-D3 says Phase 15 ADDs one; if pre-existing, this plan modifies that one instead).

```bash
test -f README.md && echo "EXISTS at root (modify-mode)" || echo "ABSENT (create-mode)"
ls -1 README* 2>/dev/null
```

Expected per CONTEXT.md `<code_context>`: "Repo has no `README.md` at root (D-D3 adds one)." So expected: ABSENT (create-mode).

If a README.md is found, STOP and surface in plan SUMMARY -- the doc-only phase should NOT overwrite an existing root README without explicit user direction.
  </action>
  <verify>
    <automated>test ! -f README.md && echo "OK: create-mode (no pre-existing root README)" || echo "WARN: README.md exists; check before overwriting"</automated>
  </verify>
  <done>Create-mode confirmed; or pre-existing README.md surfaced in plan SUMMARY.</done>
</task>

<task type="auto">
  <name>Task 15-06-002: Author README.md</name>
  <files>README.md</files>
  <action>
Create the file with the structure below. Length target: 30-80 lines. ASCII-only.

```
# DataPrep

*Last updated: 2026-05-11*

DataPrep is a Python-based ETL execution engine that replaces Talend Open
Studio for 1200+ production jobs. The system has two layers: a converter
that transforms Talend `.item` XML job definitions into JSON configurations,
and an engine that executes those JSON configs. Talend feature parity is
non-negotiable -- any Talend job using the target components must produce
identical results when run through the Python engine.

## Quickstart

Convert a Talend `.item` file to a JSON job config:

```bash
python -m src.converters.talend_to_v1.converter path/to/job.item path/to/job.json
```

Execute a JSON job config:

```bash
python src/v1/engine/engine.py path/to/job.json
```

(Jobs using Java expressions / tMap / tJava / tJavaRow require JVM 11+ on
PATH and the Java bridge JAR built via `mvn package` under
`src/v1/java_bridge/java/`. See `docs/DEPLOYMENT.md` for details.)

## Documentation

- `docs/ARCHITECTURE.md` -- system overview, layers, data flow, registry discipline
- `docs/COMPONENT_REFERENCE.md` -- registry-driven inventory of every engine component
- `docs/CONTRIBUTING.md` -- contributor rules (registry+abstract discipline, 95% floor, ASCII-only, atomic commits, etc.)
- `docs/DEPLOYMENT.md` -- validated runtime (Linux + JVM 11+), build, run, test gate
- `CLAUDE.md` -- Claude-specific instructions (this file is project-Claude-instructions territory and takes precedence for Claude-driven work)

Detailed authoring patterns live under `docs/v1/patterns/` (engine component
pattern, converter pattern, test patterns, manual component authoring,
BaseComponent reference card).

## License

(Add license details when finalized; presently the repo is internal.)
```

Notes:
- The triple-backticks above are literal Markdown code-fence syntax (the doc itself includes the same code fences for the two Quickstart examples).
- The paragraph wording above is drawn from `.planning/PROJECT.md` -- the executor may rephrase for cleanliness but MUST keep ASCII-only and preserve the "Talend feature parity is non-negotiable" assertion (load-bearing per CONTRIBUTING.md Rule 9).
- If license details are not known, the License section can be reduced to a single line ("License details TBD -- internal") or omitted entirely.
- Length 30-80 lines including the code blocks.

ASCII discipline as before. Every cited path must exist; the executor confirms.
  </action>
  <verify>
    <automated>test -f README.md && head -2 README.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' README.md)" && grep -qF "docs/ARCHITECTURE.md" README.md && grep -qF "CLAUDE.md" README.md && grep -qF "docs/CONTRIBUTING.md" README.md && grep -qF "docs/DEPLOYMENT.md" README.md && grep -qF "docs/COMPONENT_REFERENCE.md" README.md && lines=$(wc -l < README.md) && test "$lines" -ge 20 && test "$lines" -le 100 && echo "OK: root README + all 5 links + length=$lines"</automated>
  </verify>
  <done>README.md created at repo root with all 5 required links + 2 Quickstart examples; ASCII verified; header verified; length 20-100.</done>
</task>

<task type="auto">
  <name>Task 15-06-003: Commit</name>
  <files>README.md</files>
  <action>
Atomic commit per D-E1:

```bash
git add README.md
git commit -m "docs(15-06): add root README.md (minimal per D-D3)

Repo-root entry point pointing at the 4 canonical docs at docs/
(ARCHITECTURE.md, COMPONENT_REFERENCE.md, CONTRIBUTING.md,
DEPLOYMENT.md) plus CLAUDE.md for Claude-specific instructions.
Includes 2 short Quickstart CLI examples (converter + engine)
per planner D.6 resolution (Option B in spirit; still tight).

Refs: 15-CONTEXT.md D-D3; 15-RESEARCH.md D.6 resolution"
```
  </action>
  <verify>
    <automated>git log -1 --pretty=%s | grep -qF "docs(15-06): add root README.md" && test "$(git diff --stat HEAD~1..HEAD -- src/ CLAUDE.md | wc -l | tr -d ' ')" = "0" && echo "OK: committed; no src/ or CLAUDE.md touch"</automated>
  </verify>
  <done>Single commit landed; no src/ or CLAUDE.md touched; HEAD subject matches.</done>
</task>

</tasks>

<verification_gate>

Plan 15-06 is GREEN when:
1. `README.md` exists at REPO ROOT.
2. `*Last updated: 2026-05-11*` on line 2.
3. ASCII-only.
4. Links to all 5 documents present (4 canonical docs + CLAUDE.md).
5. 2 Quickstart code blocks (converter + engine) present.
6. Length 20-100 lines.
7. Single commit landed; no src/ or CLAUDE.md touched.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-06): add root README.md (minimal per D-D3)` | `README.md` |

(Total: 1 commit.)

</commit_map>
