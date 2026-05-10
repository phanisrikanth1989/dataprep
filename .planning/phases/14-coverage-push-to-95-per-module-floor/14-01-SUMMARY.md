---
phase: 14
plan: 01
slug: pipeline-test-infrastructure
subsystem: test-infrastructure
tags: [test-infra, coverage-tooling, pytest-xdist, fixture-scaffolding]
status: complete
completed: 2026-05-10
duration_minutes: ~25
tasks_total: 6
tasks_completed: 6
commits_total: 5
requires:
  - "13-COVERAGE-BASELINE.md (per-module floor reference)"
  - "tests/integration/test_iterate_e2e.py (pipeline-pattern seed)"
provides:
  - "tests/conftest.py: PipelineResult, run_job_fixture, assert_ascii_logs, FIXTURE_JOBS_ROOT"
  - "tests/fixtures/jobs/{file,transform,core,swift}/: subsystem fixture-scaffolding directories"
  - "tests/fixtures/data/: shared synthetic data dir"
  - "tests/fixtures/jobs/README.md: fixture-job format and naming spec"
  - "scripts/check_per_module_coverage.py: per-module 95% floor enforcement"
  - "pyproject.toml [tool.coverage.run|report|html|json]: coverage tooling config"
  - "pyproject.toml dev extras: pytest-cov>=7.0,<8 + pytest-xdist>=3.8,<4 explicit pins"
  - "14-PLAN-CHECK-NOTES.md: gate-command smoke result + pre-existing-issue dispositions"
affects:
  - ".gitignore: add .coverage / .coverage.* / htmlcov/ to Coverage artifacts section"
tech_stack_added: []
tech_stack_patterns:
  - "Pipeline-test fixture loader pattern: load JSON-job, mutate via tmp copy, run via ETLEngine, snapshot global_map"
  - "ASCII-only log enforcement via caplog teardown hook (encode('ascii') check)"
  - "Per-module coverage floor enforcement via stdlib JSON parsing of coverage.json"
key_files_created:
  - tests/conftest.py
  - tests/fixtures/jobs/README.md
  - tests/fixtures/jobs/.gitkeep
  - tests/fixtures/jobs/file/.gitkeep
  - tests/fixtures/jobs/transform/.gitkeep
  - tests/fixtures/jobs/core/.gitkeep
  - tests/fixtures/jobs/swift/.gitkeep
  - tests/fixtures/data/.gitkeep
  - scripts/check_per_module_coverage.py
  - .planning/phases/14-coverage-push-to-95-per-module-floor/14-PLAN-CHECK-NOTES.md
key_files_modified:
  - pyproject.toml
  - .gitignore
decisions:
  - "Pipeline tests run via ETLEngine(dict) (not subprocess) for in-process coverage tracking"
  - "PipelineResult.global_map is a snapshot (dict copy) so tests can mutate freely"
  - "assert_ascii_logs runs at DEBUG level (catches more than INFO) and yields caplog so tests can also do positive content assertions"
  - "Per-module floor script is stdlib-only (no third-party deps) and ASCII-only output"
  - "pyproject [tool.coverage.run] sets parallel=true defensively for pytest-xdist + pytest-cov combine; smoke run confirms no drift either way"
  - "Coverage HTML/JSON output paths set in pyproject ([tool.coverage.html] dir=htmlcov; [tool.coverage.json] output=coverage.json) so the gate command works without extra CLI flags"
metrics:
  duration_minutes: ~25
  modules_below_floor_baseline: 53 (from 13-COVERAGE-BASELINE.md)
  modules_below_floor_measured: 52 (current tree, 2026-05-10; off-by-one is __init__ omit pattern)
  total_in_scope_modules: 198
  smoke_serial_pct: 59.58
  smoke_parallel_pct: 59.58
  smoke_delta_pct: 0.00
---

# Phase 14 Plan 01: Pipeline-Test Infrastructure Summary

**One-liner:** Built the shared Phase 14 test infrastructure -- root `tests/conftest.py` with `run_job_fixture` + `assert_ascii_logs` + `PipelineResult`, fixture-jobs directory scaffolding under `tests/fixtures/jobs/{file,transform,core,swift}/`, `pyproject.toml` `[tool.coverage]` blocks with explicit `pytest-cov` / `pytest-xdist` pins, and a stdlib-only `scripts/check_per_module_coverage.py` per-module 95% floor gate -- verified by a smoke run (serial vs `-n auto` matched exactly at 59.58%) and an end-to-end gate-command run (52 modules below 95%, matching the Phase 13 baseline).

## What Was Built

### tests/conftest.py (root)
- `PipelineResult` dataclass: `stats`, `global_map` (dict snapshot), `engine` (live ETLEngine), `json_path` (mutated copy in tmp).
- `FIXTURE_JOBS_ROOT` module constant: absolute Path to `tests/fixtures/jobs`.
- `run_job_fixture` fixture: callable `(name, mutations=None) -> PipelineResult`. Loads JSON from `FIXTURE_JOBS_ROOT / f"{name}.json"`, copies to `tmp_path`, applies per-component config mutations, persists the mutated JSON to disk (so `result.json_path` is faithful), then runs `ETLEngine(deepcopy(config)).execute()` and snapshots `global_map.get_all()`.
- `assert_ascii_logs` fixture: enables caplog at DEBUG, yields it for in-test positive assertions, and on teardown raises `AssertionError` if any captured log message contains a non-ASCII byte.

Pattern reference: generalizes `_mutate_json_paths` + `ETLEngine.execute()` from `tests/integration/test_iterate_e2e.py`. Complements (does NOT replace) `tests/v1/engine/conftest.py` -- pytest discovers both via parent-walk.

### tests/fixtures/jobs/ scaffolding
- `tests/fixtures/jobs/{file,transform,core,swift}/.gitkeep` -- subsystem directories tracked in git ahead of the per-subsystem lift plans.
- `tests/fixtures/data/.gitkeep` -- shared synthetic data directory.
- `tests/fixtures/jobs/README.md` -- documents:
  - JSON shape mirroring talend_to_v1 converter output (`job`, `components`, `flows`, `triggers`, `subjobs`, `context`).
  - Naming convention `<subsystem>/<behavior>.json` (lowercase snake_case).
  - `run_job_fixture` usage with `mutations` dict.
  - Authoring guidelines: 1-3 components, `"TBD_via_mutations"` placeholders, ASCII-only, realistic dtypes.
  - Regen-from-`.item` helper command.
  - Subsystem-to-plan mapping table.

### scripts/check_per_module_coverage.py
- 30-50 LOC stdlib-only Python script.
- CLI: `python scripts/check_per_module_coverage.py <report> [--floor N]` (default floor 95.0).
- Reads `coverage.json` `files[*].summary.percent_covered`; on fail, sorts by ascending pct and emits `FAIL: K module(s) below F% line coverage:` with `<pct>%  <path>  (missing K lines)` rows to stderr; exits 1. On pass, emits `PASS: all <N> in-scope modules at >= F% line coverage` to stdout; exits 0. On data error (missing file, invalid JSON, missing keys), emits `ERROR: ...` to stderr; exits 2.
- Made executable (`chmod +x`).

### pyproject.toml additions
- `[project.optional-dependencies].dev`: explicit `pytest-cov>=7.0,<8` and `pytest-xdist>=3.8,<4` pins.
- `[tool.coverage.run]`: `source = ["src/v1/engine", "src/converters"]`, `omit = ["src/converters/complex_converter/*", "*/__init__.py", "*/tests/*", "*/test_*.py"]`, `branch = false`, `parallel = true`.
- `[tool.coverage.report]`: NO global `fail_under` (per-module gate is enforced by the script, not by coverage.py); `show_missing = true`, `precision = 1`, D-C3 narrow `exclude_also` allowlist for `if __name__ == "__main__":` / `raise NotImplementedError` / `@abstractmethod`.
- `[tool.coverage.html]`: `directory = "htmlcov"`.
- `[tool.coverage.json]`: `output = "coverage.json"`, `pretty_print = false`.

### .gitignore additions
- `.coverage` (binary data file).
- `.coverage.*` (parallel-mode worker data files).
- `htmlcov/` (HTML report directory).
- `coverage.json` is already covered by the project-wide `*.json` rule.

## Tasks Completed

| Task | Status | Commit |
|------|--------|--------|
| 14-01-001 (pyproject coverage + dev pins) | done | `145663c` |
| 14-01-002 (fixture scaffolding + README) | done | `d15de38` |
| 14-01-003 (root conftest.py) | done | `456e6da` |
| 14-01-004 (per-module floor script) | done | `541a805` |
| 14-01-005 (smoke: serial vs xdist) | done | (no commit -- no drift; result recorded in 14-PLAN-CHECK-NOTES.md alongside 006) |
| 14-01-006 (gate-command end-to-end) | done | `4699a82` (combined with .gitignore + PLAN-CHECK-NOTES) |

Total commits: 5. Plan's commit_map estimated 5-6; landed at 5 because no drift surfaced and INFRA-005 + INFRA-006 were combined (drift case + gate result) into one notes file.

## xdist + cov Smoke Test Result (Open Issue #3 from PLAN.md)

**Outcome: PASS -- no drift between serial and `-n auto` coverage measurement.**

| Mode | percent_covered for src/v1/engine/executor.py |
|------|----------------------------------------------:|
| Serial (`pytest -q`) | 59.58% |
| `-n auto` (10 workers) | 59.58% |
| Delta | 0.00% |

The `[tool.coverage.run] parallel = true` setting in pyproject.toml combined with pytest-cov 7.0.0's combine step works correctly under pytest-xdist 3.8.0. Phase 14's gate command (`pytest -n auto --cov=...`) is safe for measurement.

## Verification Evidence

- `python -c "import tomllib; ..."` confirms pyproject parses and contains the new sections / pins -- output `ok`.
- `python -m pytest tests/conftest.py --collect-only` -- no errors.
- `python -c "import tests.conftest as c; assert hasattr(c, 'PipelineResult'); ..."` -- output `ok`.
- `python scripts/check_per_module_coverage.py --help` -- prints usage.
- Synthetic JSON pass+fail cases for the per-module script -- both `ok-fail-case` and `ok-pass-case` printed.
- End-to-end gate command runs to completion; produces `coverage.json` (831 KB); per-module script reports 52 modules below 95% (matches Phase 13 baseline expectations).
- 6826 tests pass under `-n auto` (3 skipped, 1 xfailed). 4 pre-existing failures + 1 collection-time ImportError surfaced under FULL-suite parallelism but NOT introduced by this plan -- documented in `14-PLAN-CHECK-NOTES.md` with disposition for Plans 14-11 and 14-12.

## Deviations from Plan

**[Rule 2 -- Auto-add missing critical functionality] Add coverage artifacts to .gitignore.**

- **Found during:** Task 14-01-006 verification.
- **Issue:** Plan acknowledged "verify via `git status` after the run" but did not pre-stage `.gitignore` updates. The gate command produces `.coverage` (untracked, NOT covered by `*.json`) and `htmlcov/` (NOT covered by `*.json`). Without ignoring these, every gate run leaves untracked artifacts that polluted `git status` and could be accidentally committed by future contributors using `git add -A`.
- **Fix:** Added a "Coverage artifacts" section to `.gitignore` covering `.coverage`, `.coverage.*`, and `htmlcov/`. Verified via `git status --ignored` post-run.
- **Files modified:** `.gitignore`.
- **Commit:** `4699a82`.

No other deviations. All other tasks executed exactly as the plan specified.

## Pre-Existing Issues Surfaced (Out of Scope for 14-01)

The end-to-end gate command (Task 14-01-006) made two pre-existing infrastructure issues visible. Both predate Phase 14 and are NOT regressions introduced by this plan; both are deferred to later Phase 14 plans where they naturally fit:

1. **`tests/v1/engine/test_bridge_integration.py::TestTMapCompiledExpressions`** -- 4 tests fail under FULL-suite `-n auto` (10 workers) due to per-worker JVM contention; pass in isolation. Deferred to **Plan 14-11** (engine core, includes `java_bridge_manager.py`).
2. **`tests/converters/talend_to_v1/test_integration.py`** -- collection-time `ModuleNotFoundError: src.converters.complex_converter` (legacy / not shipped). Pre-existing since commit `90d56be`. Deferred to **Plan 14-12** (converter-core lift).

Full disposition: `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PLAN-CHECK-NOTES.md`.

## Self-Check: PASSED

**Files verified to exist:**
- `tests/conftest.py` -- FOUND
- `tests/fixtures/jobs/README.md` -- FOUND
- `tests/fixtures/jobs/.gitkeep`, `file/.gitkeep`, `transform/.gitkeep`, `core/.gitkeep`, `swift/.gitkeep` -- ALL FOUND
- `tests/fixtures/data/.gitkeep` -- FOUND
- `scripts/check_per_module_coverage.py` -- FOUND (executable)
- `pyproject.toml` -- contains `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.coverage.html]`, `[tool.coverage.json]`, `pytest-cov>=7.0,<8` and `pytest-xdist>=3.8,<4` in dev extras
- `.gitignore` -- contains `.coverage`, `.coverage.*`, `htmlcov/`
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PLAN-CHECK-NOTES.md` -- FOUND

**Commits verified to exist (5 commits, range d922579..HEAD):**
- `145663c` chore(14-01): INFRA-001 add pyproject coverage config + xdist/cov pins -- FOUND
- `d15de38` chore(14-01): INFRA-002 scaffold tests/fixtures/jobs/... + README -- FOUND
- `456e6da` chore(14-01): INFRA-003 add root tests/conftest.py ... -- FOUND
- `541a805` chore(14-01): INFRA-004 add scripts/check_per_module_coverage.py ... -- FOUND
- `4699a82` chore(14-01): INFRA-005/006 record gate-command smoke result + ignore coverage artifacts -- FOUND

**Verification gate (from PLAN.md):**
1. Tasks 14-01-001..004 verification commands -- ALL PASS
2. `tests/conftest.py` collected by pytest without errors -- VERIFIED
3. `pyproject.toml` valid TOML; new pins resolve -- VERIFIED
4. `scripts/check_per_module_coverage.py --help` works; pass+fail synthetic cases work -- VERIFIED
5. End-to-end gate command lands `coverage.json`; 52 modules below 95% (Phase 13 baseline expected ~53) -- VERIFIED
6. Smoke (Task 14-01-005) serial vs parallel equivalent (delta 0.00%) -- VERIFIED
7. No new pragmas added -- VERIFIED
8. All commits ASCII-only -- VERIFIED

All eight verification-gate criteria GREEN. Plan 14-01 complete.
