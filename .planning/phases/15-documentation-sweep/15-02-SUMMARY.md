---
phase: 15
plan: 2
subsystem: docs
tags: [docs, architecture, registry-discipline, phase-14-followup]
requires: [15-01]
provides: [docs/ARCHITECTURE.md]
affects: [docs/]
tech-stack:
  added: []
  patterns: [decorator-based-registry, template-method, strategy, iterator]
key-files:
  created:
    - docs/ARCHITECTURE.md
  modified: []
decisions:
  - "Cite the live decorator-based REGISTRY (src/v1/engine/component_registry.py) and explicitly flag the previously-documented ETLEngine.COMPONENT_REGISTRY static dict as no longer existing -- the .planning/codebase/ maps and the current ./CLAUDE.md still carry the stale claim and must be trusted as derived, not source-of-truth, per RESEARCH C.5."
  - "Use entry-point line numbers from current source (engine __main__ at line 285, converter __main__ at line 516) rather than the stale numbers in CLAUDE.md (860, 460)."
  - "Document the dual invariant (registered + _validate_config) as a load-bearing section with four bug citations from Phase 14 (BUG-PDC, BUG-SWIFT x3, BUG-FIJ)."
  - "Omit the `complex_converter` reference present in codebase maps -- that path no longer exists in src/."
metrics:
  duration_minutes: 12
  completed_date: 2026-05-11
---

# Phase 15 Plan 02: Architecture Canonical Doc Summary

Fresh `docs/ARCHITECTURE.md` (497 lines) authored from `.planning/codebase/`
inputs with three categories of corrections applied against live source:
the stale `ETLEngine.COMPONENT_REGISTRY` static-dict claim replaced with the
live decorator-based REGISTRY in `src/v1/engine/component_registry.py`, the
entry-point line numbers updated, and the no-longer-existing
`complex_converter` reference dropped. Includes the load-bearing Registry
Discipline section per D-C4 with full Phase 14 BUG-PDC/SWIFT/FIJ citations.

## What Changed

- Created `docs/ARCHITECTURE.md` (497 lines, ASCII-only).
- Zero `src/` touches (verified post-commit).
- Zero edits to `docs/v1/audit/` (out-of-scope per D-A4).
- Zero edits to `./CLAUDE.md` (D-B4); CLAUDE.md's stale static-dict claim
  noted in deviations but NOT patched here (out of plan 15-02 scope).

## Source-of-Truth Verification (Task 15-02-001)

Eight grep checks run against live source before authoring:

| # | Check | Result |
| - | ----- | ------ |
| 1a | `from .component_registry import REGISTRY` at engine.py:18 | OK (line 18) |
| 1b | `def register` in component_registry.py | OK (line 29) |
| 1c | `COMPONENT_REGISTRY =` in engine.py | ZERO matches (confirms static dict gone) |
| 1d | `class ETLEngine.*COMPONENT_REGISTRY` | ZERO matches |
| 2 | `@abstractmethod` in base_component.py | OK (lines 280, 295) |
| 3 | ETLError hierarchy in exceptions.py | OK (9 classes including TriggerEvaluationError) |
| 4 | `__main__` blocks | engine.py:285, converter.py:516 |
| 5 | JavaBridgeManager port allocation | OK (uses socket + dynamic port) |
| 6 | Phase 14 BUG-PDC/SWIFT/FIJ in 14-PHASE-SUMMARY.md | OK (rows 43, 45, 47, plus systemic note at row 103) |
| 7 | `src/v1/engine/components/iterate/` | OK (`flow_to_iterate.py`) |
| 8 | `src/v1/engine/oracle_connection_manager.py` | EXISTS |

All passes -- no doc claim required revision.

## Cross-Reference Sweep (Task 15-02-003)

Mechanical extraction of every `src/...` path mention in
`docs/ARCHITECTURE.md` yielded 24 unique source paths plus 2 directory
references plus 1 build-artifact path. All 24 source files verified to
exist; both directories exist; the build artifact
(`src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`) is
correctly framed in the doc as a Maven build output rather than a tracked
source.

## Verification Gate

| Criterion | Status |
| --------- | ------ |
| File at `docs/` root, not `docs/v1/` | PASS |
| Header line 1 = `# DataPrep Architecture` | PASS |
| Header line 2 = `*Last updated: 2026-05-11*` | PASS |
| `grep -nP "[^\x00-\x7F]" docs/ARCHITECTURE.md` returns zero lines | PASS |
| Registry-discipline section cites `component_registry.py` | PASS |
| Section cites BUG-PDC, BUG-SWIFT, BUG-FIJ | PASS |
| Doc states static-dict no longer exists (disambiguation only) | PASS |
| Every cited `src/` path exists | PASS (24/24) |
| Length 250-600 lines (target 300-500) | PASS (497) |
| Single commit, no `src/` touched | (verified at commit time) |

## Deviations from Plan

- **[Rule 2 -- Verify-before-claim]** PLAN.md listed engine `__main__` at line 860
  and converter `__main__` at line 460. Verified at execution time the real
  positions are 285 and 516 respectively (CLAUDE.md is stale on these). Doc
  cites the real line numbers. This is the verify-before-claim discipline
  the plan itself mandates (D-E2).
- **[Rule 2 -- Verify-before-claim]** `.planning/codebase/STRUCTURE.md` (implicit
  via CLAUDE.md) references `src/converters/complex_converter/converter.py`.
  Confirmed via `ls` that this directory no longer exists. Doc omits the
  reference; the deletion is presumably from an earlier phase cleanup.
- **[Rule 2 -- Verify-before-claim]** `iterate/` package contains only
  `flow_to_iterate.py` (plus `__init__.py`), not the three components
  (`tFileList`, `tFlowToIterate`, `tForeach`) named in `.planning/codebase/`.
  Doc cites the three Talend names as conceptual examples (which they are at
  the converter side) but does not claim three engine modules exist. The
  `tFileList` and `tForeach` engine implementations live elsewhere or are not
  yet built; documenting this carefully avoids an aspirational claim.

## Known Stubs

None. The doc references plans 15-03/15-04/15-05 in "See Also"; those plans
will create the referenced files. This is forward-pointing scaffolding, not
broken stubs.

## Files Created

- `docs/ARCHITECTURE.md` (497 lines)

## Files Modified

None.

## Commit

- `docs(15-02): add docs/ARCHITECTURE.md from .planning/codebase/`

## Self-Check: PASSED

- File `docs/ARCHITECTURE.md`: FOUND
- Header line 2 matches: PASS
- ASCII-only grep: zero non-ASCII lines
- Length: 497 lines (within 250-600 gate)
- Registry-discipline section present, BUG-PDC/SWIFT/FIJ cited
- All 24 cited src/ paths exist
- Zero src/ files touched
