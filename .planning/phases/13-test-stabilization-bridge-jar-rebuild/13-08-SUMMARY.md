---
phase: "13"
plan: "08"
subsystem: testing
tags: [coverage, baseline, docs]
dependency_graph:
  requires: [13-01, 13-02, 13-03, 13-04, 13-05, 13-06, 13-07]
  provides: [coverage-baseline]
  affects: [CLAUDE.md, Phase 14 enforcement floor]
tech_stack:
  added: []
  patterns: [pytest-cov, term-missing report]
key_files:
  created:
    - .planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md
  modified:
    - CLAUDE.md
decisions:
  - "Baseline measures line coverage only (no --cov-branch) to match Phase 14s 95% line-coverage floor expectation"
  - "complex_converter marked N/A for Phase 14 gate -- superseded legacy code"
  - "Coverage command placed in CLAUDE.md between Conventions and Architecture sections"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 13 Plan 08: Coverage Baseline Summary

Measured and recorded per-module line coverage across `src/v1/engine/` and `src/converters/` against the green 6832-test suite. Locked the baseline in `13-COVERAGE-BASELINE.md` and added a reproducible coverage command to `CLAUDE.md`.

## What Was Done

### Task 1 -- Confirm test suite green

Ran `python -m pytest tests/ -q --tb=short` to verify the D-A3 hard-zero precondition before measuring coverage. Result: **6832 passed, 26 skipped, 1 xfailed, 0 failed**.

### Task 2 -- Measure coverage and write 13-COVERAGE-BASELINE.md

Ran:
```bash
python -m pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=term-missing -q
```

Wrote `13-COVERAGE-BASELINE.md` with:
- Full per-module table grouped by subsystem (engine.components.file, engine.components.transform, engine.components.aggregate, engine.components.control, engine.components.context, engine.components.iterate, engine.components.database, engine core, converters.talend_to_v1 all sub-groups, converters.complex_converter)
- Phase 14 floor annotation (PASS / FAIL) per module
- Reproducible command block
- Notable low-coverage modules flagged
- Summary lift-target count table

Updated `CLAUDE.md` with a Coverage section (placed between Conventions and Architecture) containing the reproducible `pytest --cov` command and a pointer to the baseline file.

Committed both as `7e42224`.

## Coverage Measurement Results

**Overall:** 19429 statements, 4881 missed, **75% total** (across all measured modules)

**Module counts (excluding complex_converter legacy):**
- Total modules measured: 198
- At or above 95% (Phase 14 PASS): **145**
- Below 95% (Phase 14 FAIL / lift targets): **53**

### Notable Low-Coverage Modules (below 50%)

| Module | Cover | Reason |
|--------|------:|--------|
| `src/v1/engine/components/transform/swift_transformer.py` | 7% | No unit tests for SWIFT processing |
| `src/v1/engine/components/transform/swift_block_formatter.py` | 7% | No unit tests for SWIFT block formatting |
| `src/v1/engine/components/file/file_input_json.py` | 9% | Minimal test coverage for JSON input |
| `src/v1/engine/components/file/file_input_raw.py` | 15% | Mostly untested raw file paths |
| `src/v1/engine/components/transform/python_dataframe_component.py` | 20% | Integration-only paths untested |
| `src/v1/engine/components/file/file_input_excel.py` | 29% | Complex format-branching paths untested |
| `src/converters/complex_converter/converter.py` | 6% | Legacy (not a Phase 14 target) |
| `src/converters/complex_converter/component_parser.py` | 5% | Legacy (not a Phase 14 target) |

### Per-Subsystem Highlights

| Subsystem | At/Above 95% | Below 95% |
|-----------|-------------:|----------:|
| converters.talend_to_v1.components.control | 10/10 | 0 |
| converters.talend_to_v1.components.context | 2/2 | 0 |
| engine.components.context | 2/2 | 0 |
| engine.components.iterate | 2/2 | 0 |
| converters.talend_to_v1.components.file | 25/26 | 1 |
| converters.talend_to_v1.components.transform | 34/36 | 2 |
| engine.components.file | 10/26 | 16 (biggest lift area) |
| engine.components.transform | 20/37 | 17 (biggest lift area) |

## Commits

| Hash | Message |
|------|---------|
| `7e42224` | docs(13-08): COV-BASE-001 measure and record per-module coverage baseline; COV-DOC-001 reference coverage command in CLAUDE.md |

## Deviations from Plan

None -- plan executed exactly as written. Both tasks completed, both artifacts produced, single commit as specified.

## Self-Check

- [x] `13-COVERAGE-BASELINE.md` exists with 243 coverage percentages and a TOTAL row
- [x] `CLAUDE.md` contains "coverage" (2 hits confirmed)
- [x] Commit `7e42224` exists
- [x] 0 file deletions in the commit
- [x] `grep -c "%" 13-COVERAGE-BASELINE.md` returns > 5 (returns 243)
