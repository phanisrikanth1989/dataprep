---
phase: 15
plan: 2
slug: architecture-canonical-doc
type: execute
wave: 1
depends_on: [15-01]
files_modified:
  - docs/ARCHITECTURE.md       # NEW (fresh write; ~300-500 lines)
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "docs/ARCHITECTURE.md exists at docs/ root (NOT docs/v1/) per D-A3"
    - "File starts with '# DataPrep Architecture' on line 1 and '*Last updated: 2026-05-11*' on line 2 (D-C2)"
    - "File is ASCII-only -- grep -nP \"[^\\x00-\\x7F]\" returns zero lines (D-C1)"
    - "Registry section cites decorator-based REGISTRY from src/v1/engine/component_registry.py and explicitly states the static dict ETLEngine.COMPONENT_REGISTRY no longer exists"
    - "Registry-discipline subsection (D-C4) names BUG-PDC-001/002, BUG-SWIFT-001..005, BUG-FIJ-001/002 as evidence of the dual-invariant rule (registered + _validate_config)"
    - "Every cited file path is grep-confirmed to exist in src/"
    - "Every cited class/function name is grep-confirmed to exist in current source"
    - "Length within target 300-500 lines"
  artifacts:
    - path: docs/ARCHITECTURE.md
      provides: canonical system-level architecture doc; entry point for new contributors and managers
      min_lines: 300
      contains: "# DataPrep Architecture"
  key_links:
    - from: docs/ARCHITECTURE.md
      to: src/v1/engine/component_registry.py
      via: cited as the live decorator-based REGISTRY (replaces stale static-dict claim)
      pattern: "component_registry"
    - from: docs/ARCHITECTURE.md
      to: src/v1/engine/base_component.py
      via: cited for template-method lifecycle (lines 1-50 docstring)
      pattern: "base_component"
    - from: docs/ARCHITECTURE.md
      to: docs/COMPONENT_REFERENCE.md (plan 15-03)
      via: "See Also" reference -- COMPONENT_REFERENCE is the per-component inventory
      pattern: "COMPONENT_REFERENCE\\.md"
    - from: docs/ARCHITECTURE.md
      to: docs/CONTRIBUTING.md (plan 15-04)
      via: "See Also" reference -- CONTRIBUTING covers authoring conventions
      pattern: "CONTRIBUTING\\.md"
---

<objective>
Write a fresh `docs/ARCHITECTURE.md` (~300-500 lines) that explains DataPrep at the system level: layers, key abstractions, registry pattern, data flow, state management, error handling, cross-cutting concerns, and entry points. Sourced from `.planning/codebase/ARCHITECTURE.md` + STRUCTURE.md + STACK.md + INTEGRATIONS.md, with corrections against live source (notably: the stale `COMPONENT_REGISTRY` static-dict claim must be replaced with the live `component_registry.py` decorator-based REGISTRY). Includes the LOAD-BEARING registry-discipline section per D-C4 documenting the Phase 14 systemic constraint.
</objective>

<scope>
- Create `docs/ARCHITECTURE.md` from scratch.
- Consume `.planning/codebase/ARCHITECTURE.md` as the structural starting point.
- CORRECT (do NOT propagate) the stale `ETLEngine.COMPONENT_REGISTRY` static-dict claim that appears in the codebase maps -- the live engine uses `src/v1/engine/component_registry.py` decorator-based `REGISTRY` (verified: `src/v1/engine/engine.py:18 from .component_registry import REGISTRY`).
- Include the registry-discipline section (D-C4): every `BaseComponent` subclass MUST be `@REGISTRY.register("PascalName", "tTalendName")`-decorated AND implement `_validate_config()`. Cite Phase 14 BUG-PDC/SWIFT/FIJ as evidence.
- Encode the Phase 14 systemic lesson explicitly: engine silently drops unregistered classes ("Unknown component type" warning); ABC refuses instantiation of classes missing the abstract method.
- ASCII-only per D-C1; `*Last updated: 2026-05-11*` header per D-C2.
- Per-claim verification (D-E2): every cited class, function, file path must be grep-confirmed in current source.
- Single commit: `docs(15-02): add docs/ARCHITECTURE.md from .planning/codebase/`.
</scope>

<out_of_scope>
- COMPONENT_REFERENCE.md (plan 15-03 -- this doc REFERENCES it in "See Also").
- CONTRIBUTING.md (plan 15-04).
- DEPLOYMENT.md (plan 15-05).
- README.md (plan 15-06).
- Per-component depth (live at `docs/v1/audit/components/*.md` -- out of Phase 15 scope per D-A4; this doc points at COMPONENT_REFERENCE.md which in turn points at audit/).
- CLAUDE.md edits (D-B4).
- Any src/ change (D-E3).
- Generation tooling (D-B2 forbids).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A3 (canonical docs at docs/ root), D-C1 (ASCII), D-C2 (header), D-C4 (registry-discipline section MANDATORY), D-E2 (verify-before-claim)
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section B.1 (full skeleton for ARCHITECTURE.md), Section C.5 (codebase maps still carry stale static-dict claim -- do NOT propagate)
- `.planning/codebase/ARCHITECTURE.md` (structural starting point)
- `.planning/codebase/STRUCTURE.md` (directory layout)
- `.planning/codebase/STACK.md` (Python 3.10+, JVM 11+, Py4J, Arrow, etc.)
- `.planning/codebase/INTEGRATIONS.md` (Java bridge details)
- `.planning/PROJECT.md` (Core Value paragraph)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (Phase 14 Lessons Learned -- registry+abstract systemic pattern)
- `src/v1/engine/engine.py` lines 18 + 140 (REGISTRY import + lookup; verify ETLEngine.COMPONENT_REGISTRY class attr does NOT exist)
- `src/v1/engine/component_registry.py` (the live decorator-based REGISTRY; verify register() at line 29)
- `src/v1/engine/base_component.py` lines 1-50 (template-method lifecycle docstring)
- `src/v1/engine/exceptions.py` (ETLError hierarchy)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
@.planning/codebase/ARCHITECTURE.md
@.planning/codebase/STRUCTURE.md
@.planning/codebase/STACK.md
@.planning/codebase/INTEGRATIONS.md
@.planning/PROJECT.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-02-001: Verify source-of-truth claims against live code</name>
  <files>(read-only)</files>
  <action>
Before writing the doc, run these grep checks against live source to confirm the load-bearing facts the doc will assert. Record evidence in a scratch note for plan-SUMMARY use. Any check that fails means the doc's planned claim must be revised against reality.

```bash
# 1. REGISTRY pattern -- decorator-based, lives in component_registry.py:
grep -n "from .component_registry import REGISTRY" src/v1/engine/engine.py
grep -n "def register" src/v1/engine/component_registry.py
grep -n "COMPONENT_REGISTRY\s*=" src/v1/engine/engine.py    # expected: zero lines (static dict gone)
grep -nE "class ETLEngine.*COMPONENT_REGISTRY" src/v1/engine/engine.py    # expected: zero lines

# 2. BaseComponent abstract methods:
grep -n "@abstractmethod" src/v1/engine/base_component.py

# 3. ETLError hierarchy:
grep -n "^class " src/v1/engine/exceptions.py

# 4. Engine entry points:
grep -n "if __name__" src/v1/engine/engine.py
grep -n "if __name__" src/converters/talend_to_v1/converter.py

# 5. JavaBridgeManager dynamic port:
grep -n "socket.bind\|port" src/v1/engine/java_bridge_manager.py | head -5

# 6. Phase 14 BUG-* references in PHASE-SUMMARY for evidence citation:
grep -n "BUG-PDC\|BUG-SWIFT\|BUG-FIJ" .planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md | head -10

# 7. Iterate components:
ls src/v1/engine/components/iterate/

# 8. Oracle manager:
ls src/v1/engine/oracle_connection_manager.py 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

Expected outcomes:
- Item 1: import line at engine.py:18; register() in component_registry.py; ZERO matches for the static-dict pattern.
- Items 2-8: each returns a non-empty result confirming the doc can cite that artifact.

If any item fails, adjust the doc claim before writing. Do not fabricate citations.
  </action>
  <verify>
    <automated>grep -q "from .component_registry import REGISTRY" src/v1/engine/engine.py && test -z "$(grep -E 'class ETLEngine.*COMPONENT_REGISTRY' src/v1/engine/engine.py 2>/dev/null)" && echo "OK: registry truth confirmed"</automated>
  </verify>
  <done>All 8 grep checks complete; evidence captured for plan SUMMARY; no surprises.</done>
</task>

<task type="auto">
  <name>Task 15-02-002: Author docs/ARCHITECTURE.md</name>
  <files>docs/ARCHITECTURE.md</files>
  <action>
Create the file with the structure below. Length target: 300-500 lines. ASCII-only per D-C1. Header line 2 mandatory per D-C2.

Required H2 sections (in order):

1. `# DataPrep Architecture` (H1, line 1)
2. `*Last updated: 2026-05-11*` (line 2, exact)
3. `## Overview` -- 2-3 paragraphs: what DataPrep is, Core Value (paste-quote from `.planning/PROJECT.md`), the converter-engine split.
4. `## System Diagram (ASCII)` -- conceptual data flow: Talend .item -> XmlParser -> ComponentConverters -> JSON config -> ETLEngine -> ExecutionPlan -> Executor -> components -> output. Pure ASCII, no Unicode box-drawing.
5. `## Layers` -- one subsection per layer (XML Parsing, Component Converter, Converter Orchestrator, Engine Core, Engine Component Layer, Infrastructure Layer, Java Bridge Layer). For each layer: purpose, location, key classes (verified-to-exist via Task 15-02-001).
6. `## Key Abstractions` -- BaseComponent (template method, 8-step lifecycle from base_component.py docstring), BaseIterateComponent (iterator pattern), ComponentConverter (Strategy), REGISTRY (decorator-based, BOTH sides).
7. `## Registry Discipline` -- THE LOAD-BEARING NEW SECTION (D-C4). Required content:
   - "The engine REGISTRY lives in `src/v1/engine/component_registry.py` (decorator-based, mirroring the converter side). It is imported into `src/v1/engine/engine.py` at line 18 (`from .component_registry import REGISTRY`). The previously documented `ETLEngine.COMPONENT_REGISTRY` static-dict class attribute no longer exists."
   - "Every BaseComponent subclass MUST:
     1. Be decorated with `@REGISTRY.register("PascalCaseName", "tTalendName")` -- one decorator listing one or more aliases.
     2. Implement `_validate_config()` raising `ConfigurationError` on missing required keys."
   - "If decoration is missing: the engine logs 'Unknown component type' at runtime and silently drops the component from job execution. There is no startup-time check."
   - "If `_validate_config` is missing: the class is uninstantiable (Python ABC raises `TypeError: Can't instantiate abstract class ...` on `__init__`)."
   - Phase 14 evidence: list the 4 dual-bug instances explicitly (BUG-PDC-001/002 for PythonDataFrameComponent; BUG-SWIFT-001/002 for SwiftTransformer + SwiftBlockFormatter; BUG-FIJ-001/002 for FileInputJSON), citing the Phase 14 PHASE-SUMMARY commit ranges where each was fixed.
   - Note that Phase 14 chose NOT to add a startup-time membership audit (deferred per CONTEXT.md "Deferred Ideas"); manual review + `docs/CONTRIBUTING.md` Rule 5 enforce the invariant.
8. `## Data Flow` -- conversion pipeline (12 steps from converter), engine execution pipeline (10 steps from engine.py + executor.py).
9. `## State Management` -- GlobalMap, ContextManager, data_flows dict, Java bridge sync semantics.
10. `## Error Handling Strategy` -- ETLError hierarchy (paste class names from `src/v1/engine/exceptions.py`), `die_on_error` contract, REJECT flow routing, Die-component exit-code path.
11. `## Cross-Cutting Concerns` -- structured ASCII-only logging, 4-layer converter validation + engine schema validation, 3-phase expression resolution ({{java}} -> ${context.var} -> bare context.var), batch ETL (no auth layer; DB creds via context vars per RESEARCH.md skeleton).
12. `## Entry Points` -- converter CLI, engine CLI, programmatic `convert_job()` / `run_job()`. Cite the exact `__main__` line numbers verified in Task 15-02-001.
13. `## See Also` -- bullet links to `docs/COMPONENT_REFERENCE.md` (per-component inventory), `docs/CONTRIBUTING.md` (authoring conventions), `docs/DEPLOYMENT.md` (runtime), `docs/v1/patterns/` (post-rename location; reference here points at the wave-2 landing site).

ASCII discipline reminders:
- Use `--` not en/em dashes.
- No emoji, no smart quotes.
- Use straight `"` not curly quotes.

Verification: this plan provides skeleton content, NOT prose. The executor fills in prose by consuming the `<context>` files. The executor MUST grep-verify any class/function/path before citing it (D-E2). If a codebase-map claim contradicts live source, trust the live source (RESEARCH.md C.5 explicit on this).

Length sanity: 300-500 lines is the target; Layers + Registry Discipline + Data Flow are the heaviest sections. If exceeding 500 lines, trim Cross-Cutting Concerns first.
  </action>
  <verify>
    <automated>test -f docs/ARCHITECTURE.md && head -2 docs/ARCHITECTURE.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/ARCHITECTURE.md)" && grep -qF "component_registry" docs/ARCHITECTURE.md && grep -qF "BUG-PDC" docs/ARCHITECTURE.md && grep -qF "Registry Discipline" docs/ARCHITECTURE.md && lines=$(wc -l < docs/ARCHITECTURE.md) && test "$lines" -ge 250 && test "$lines" -le 600 && echo "OK: structure + ASCII + registry discipline + length=$lines"</automated>
  </verify>
  <done>docs/ARCHITECTURE.md created with all 13 H2 sections; ASCII verified; header verified; registry-discipline section explicit; Phase 14 BUG citations present; length 250-600 lines.</done>
</task>

<task type="auto">
  <name>Task 15-02-003: Cross-reference verification sweep</name>
  <files>(read-only -- read docs/ARCHITECTURE.md and grep its claims against src/)</files>
  <action>
For every src-path or class-name claim in `docs/ARCHITECTURE.md`, verify it exists in current code. Build a verification log (will be folded into 15-VERIFICATION.md by plan 15-10).

Suggested mechanical sweep:

```bash
# Extract every "src/v1/engine/..." or "src/converters/..." path mention:
grep -oE "src/[a-zA-Z0-9_/]+\.py" docs/ARCHITECTURE.md | sort -u > /tmp/15-02-paths.txt
while read p; do
  test -f "$p" && echo "OK: $p" || echo "MISSING: $p"
done < /tmp/15-02-paths.txt

# Extract code-quoted class/function names (heuristic: words with PascalCase or snake_case_with_parens):
grep -oE '`[A-Za-z_]+(\(\))?`' docs/ARCHITECTURE.md | sort -u | head -50
# Spot-check each via `grep -rn <name> src/`
```

If MISSING lines appear, FIX THE DOC before commit. Doc-only phase per D-E3: never patch source to match an aspirational doc claim.
  </action>
  <verify>
    <automated>grep -oE "src/[a-zA-Z0-9_/]+\.py" docs/ARCHITECTURE.md | sort -u | while read p; do test -f "$p" || { echo "MISSING $p"; exit 1; }; done && echo "OK: all paths exist"</automated>
  </verify>
  <done>Every cited src/ path exists; every spot-checked class/function name is grep-confirmed in source; verification log captured for plan SUMMARY.</done>
</task>

<task type="auto">
  <name>Task 15-02-004: Commit</name>
  <files>docs/ARCHITECTURE.md</files>
  <action>
Atomic commit per D-E1:

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs(15-02): add docs/ARCHITECTURE.md from .planning/codebase/

Fresh canonical architecture doc replacing the deleted top-level
ARCHITECTURE.md from plan 15-01. Sourced from .planning/codebase/
maps with the COMPONENT_REGISTRY static-dict claim corrected to
the live decorator-based REGISTRY in src/v1/engine/component_registry.py.

Includes the LOAD-BEARING registry-discipline section per D-C4
documenting the dual invariant (every BaseComponent subclass must
be @REGISTRY.register-decorated AND implement _validate_config).
Cites Phase 14 BUG-PDC-001/002, BUG-SWIFT-001..005, BUG-FIJ-001/002
as evidence of the rule.

Refs: 15-CONTEXT.md D-A3, D-C2, D-C4; 15-RESEARCH.md B.1, C.5"
```

Verify no src/ change snuck in: `git diff --stat HEAD~1..HEAD -- src/` returns empty.
  </action>
  <verify>
    <automated>git log -1 --pretty=%s | grep -qF "docs(15-02): add docs/ARCHITECTURE.md" && test "$(git diff --stat HEAD~1..HEAD -- src/ | wc -l | tr -d ' ')" = "0" && echo "OK: committed; no src/ touch"</automated>
  </verify>
  <done>Single commit landed; no src/ touched; HEAD subject matches.</done>
</task>

</tasks>

<verification_gate>

Plan 15-02 is GREEN when:
1. `docs/ARCHITECTURE.md` exists at `docs/` root (NOT `docs/v1/`).
2. Header `*Last updated: 2026-05-11*` is on line 2.
3. ASCII-only: `grep -nP "[^\x00-\x7F]" docs/ARCHITECTURE.md` returns zero lines.
4. Registry-discipline section present; cites `component_registry.py`; cites Phase 14 BUG-PDC/SWIFT/FIJ.
5. ZERO mentions of `ETLEngine.COMPONENT_REGISTRY` as a static-dict class attribute (the stale pattern); the doc may MENTION the old pattern only to disambiguate (e.g., "previously documented `COMPONENT_REGISTRY` static dict no longer exists").
6. Every cited `src/` path exists in the repo.
7. Length: 250-600 lines (target 300-500; tight upper/lower bounds allowed).
8. Single commit landed; no `src/` touched.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-02): add docs/ARCHITECTURE.md from .planning/codebase/` | `docs/ARCHITECTURE.md` |

(Total: 1 commit.)

</commit_map>
