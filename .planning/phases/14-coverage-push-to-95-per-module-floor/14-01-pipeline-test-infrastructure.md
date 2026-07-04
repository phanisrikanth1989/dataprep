---
phase: 14
plan: 01
slug: pipeline-test-infrastructure
type: execute
wave: 0
depends_on: []
files_modified:
  - tests/conftest.py
  - tests/fixtures/jobs/README.md
  - tests/fixtures/jobs/.gitkeep
  - tests/fixtures/jobs/file/.gitkeep
  - tests/fixtures/jobs/transform/.gitkeep
  - tests/fixtures/jobs/core/.gitkeep
  - tests/fixtures/jobs/swift/.gitkeep
  - tests/fixtures/data/.gitkeep
  - pyproject.toml
  - scripts/check_per_module_coverage.py
autonomous: true
requirements: [TEST-11, TEST-12]
must_haves:
  truths:
    - "Root tests/conftest.py exposes run_job_fixture, assert_ascii_logs, and a fixtures-root resolver"
    - "tests/fixtures/jobs/{file,transform,core,swift} directories exist and are tracked in git"
    - "pyproject.toml has [tool.coverage.run] and [tool.coverage.report] blocks aligned with D-E4"
    - "pyproject.toml dev extra explicitly pins pytest-cov>=7.0,<8 and pytest-xdist>=3.8,<4"
    - "scripts/check_per_module_coverage.py reads coverage.json and exits non-zero if any in-scope module < threshold"
    - "rm -f .coverage* && python -m pytest tests/ -m 'not oracle' -n auto --cov=src/v1/engine --cov=src/converters --cov-report=json runs to completion"
    - "scripts/check_per_module_coverage.py is paste-runnable via the locked gate command"
  artifacts:
    - path: tests/conftest.py
      provides: run_job_fixture, assert_ascii_logs, FIXTURE_JOBS_ROOT
      contains: "PipelineResult"
    - path: tests/fixtures/jobs/README.md
      provides: documents fixture-jobs JSON shape and naming convention
    - path: scripts/check_per_module_coverage.py
      provides: per-module floor enforcement; reads coverage.json
    - path: pyproject.toml
      provides: "[tool.coverage.run] source/omit; pytest-xdist explicit pin"
  key_links:
    - from: tests/conftest.py
      to: src/v1/engine/engine.py
      via: ETLEngine.execute() invocation in run_job_fixture
    - from: scripts/check_per_module_coverage.py
      to: coverage.json (gate-produced)
      via: file path argument; reads files[].summary.percent_covered
---

<objective>
Build the shared test infrastructure that every other Phase 14 plan depends on: root `tests/conftest.py` with `run_job_fixture` + `assert_ascii_logs`, `tests/fixtures/jobs/` directory scaffolding under git, `pyproject.toml` `[tool.coverage]` blocks, explicit `pytest-xdist` + `pytest-cov` pins, and `scripts/check_per_module_coverage.py` (per-module 95% floor enforcement). Plus a one-time smoke validation that pytest-xdist `-n auto` produces matching coverage to a serial run on one test file.

Purpose: Plan 14-01 unblocks every other Phase 14 plan. No subsystem lift can start until `run_job_fixture` and the coverage scaffolding ship.

Output: All scaffolding listed in `must_haves.artifacts`; one git commit per logical change; verified via the gate command running cleanly even before any subsystem lift work has begun.
</objective>

<scope>
- NEW: `tests/conftest.py` (root) with `run_job_fixture`, `assert_ascii_logs`, `FIXTURE_JOBS_ROOT`, `PipelineResult` dataclass.
- NEW: `tests/fixtures/jobs/` directory with `README.md` documenting JSON-job format + naming convention `{subsystem}/{behavior}.json`.
- NEW: empty `.gitkeep` files for `tests/fixtures/jobs/{file,transform,core,swift}` and `tests/fixtures/data/` so subsystem plans can drop in fixtures.
- NEW: `scripts/check_per_module_coverage.py` per RESEARCH.md `scripts/check_coverage_floor.py` design, but renamed per the locked filename in CONTEXT.md `additional_context` (`scripts/check_per_module_coverage.py`).
- MODIFIED: `pyproject.toml` -- add `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.coverage.html]` blocks; pin `pytest-cov>=7.0,<8` and `pytest-xdist>=3.8,<4` in the `dev` extra.
- TASK: smoke run -- compare serial vs `-n auto` coverage on `tests/v1/engine/test_executor.py`, confirm equal per-line counts (RESEARCH §A4).
</scope>

<out_of_scope>
- Any subsystem-level test additions (those are 14-02..14-11).
- The first-pass JSON job fixtures themselves (each subsystem plan creates its own under `tests/fixtures/jobs/{subsystem}/`).
- SWIFT synthetic generator (Plan 14-07).
- The `scripts/regen_pipeline_fixture.py` helper from RESEARCH §Pitfall 7 -- defer to a future phase if needed.
- CI workflow file (D-E1 -- explicitly out of scope for Phase 14).
- Branch coverage (D-E4).
- Updating CLAUDE.md gate command -- closeout (Plan 14-12) handles that, since the command lands once per gate run, not per plan.
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` (D-D1, D-D4, D-E4, D-A3, D-A6)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Pipeline-Test Infrastructure, §Coverage Tooling Configuration, §Per-Module Floor Enforcement Script, §pytest-xdist + pytest-cov combine
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-VALIDATION.md` §Wave 0 Requirements
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md` (reproducible command)
- `tests/integration/test_iterate_e2e.py` (pattern for `_mutate_json_paths` and ETLEngine-driven pipeline tests)
- `tests/v1/engine/conftest.py` (existing engine-level fixtures: `StubComponent`, `IterateStubComponent`, `make_job_config`, `java_bridge`)
- `pyproject.toml` (existing markers, optional-dependencies)
- `src/v1/engine/engine.py` (ETLEngine constructor + execute())
- `src/v1/engine/global_map.py` (`get_all()` for the pipeline-result snapshot)
</canonical_refs>

<waves>

## Wave 0 -- Scaffolding (atomic, sequential)

### Task 14-01-001 -- Add pyproject.toml `[tool.coverage]` blocks + dev extras pin

- **Type:** config
- **Description:** Add `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.coverage.html]` per RESEARCH §Coverage Tooling. Pin `pytest-cov>=7.0,<8` and `pytest-xdist>=3.8,<4` in `[project.optional-dependencies].dev`. Do NOT set a global `fail_under` (per-module gate via the script -- D-E4).
- **Files to create or modify:** `pyproject.toml`
- **Verification command:** `python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert 'coverage' in d.get('tool',{}); assert any('xdist' in p for p in d['project']['optional-dependencies']['dev']); print('ok')"`
- **Expected outcome:** Stdout: `ok`. `python -m pip install -e .[dev]` resolves with the new pins.
- **Notes:** `pyproject.toml` keep existing `[project.optional-dependencies]` other extras unchanged; only edit the `dev` line and append `[tool.coverage.*]` blocks. `omit = ["src/converters/complex_converter/*", "*/__init__.py", "*/tests/*", "*/test_*.py"]`. `exclude_also` includes the D-C3 allowlist regexes.

### Task 14-01-002 -- Create `tests/fixtures/jobs/` scaffolding + README

- **Type:** fixture
- **Description:** Create `tests/fixtures/jobs/{file,transform,core,swift}/.gitkeep`, `tests/fixtures/data/.gitkeep`, and `tests/fixtures/jobs/README.md` documenting:
    1. JSON shape mirrors converter output: `{"job":{...},"components":[...],"flows":[...],"triggers":[...],"subjobs":[...],"context":{...}}`
    2. Naming convention: `{subsystem}/{behavior}.json` (lowercase snake_case)
    3. Pipeline tests use the `run_job_fixture` and pass a `mutations` dict to inject paths/config per test invocation
    4. Fixtures should be 1-3 components and use placeholder paths like `"filepath": "TBD_via_mutations"`
    5. To regenerate from a real `.item`, run `python -m src.converters.talend_to_v1.converter <item> tests/fixtures/jobs/<subsystem>/<behavior>.json` and trim
- **Files to create or modify:**
    - `tests/fixtures/jobs/.gitkeep`
    - `tests/fixtures/jobs/file/.gitkeep`
    - `tests/fixtures/jobs/transform/.gitkeep`
    - `tests/fixtures/jobs/core/.gitkeep`
    - `tests/fixtures/jobs/swift/.gitkeep`
    - `tests/fixtures/data/.gitkeep`
    - `tests/fixtures/jobs/README.md`
- **Verification command:** `test -d tests/fixtures/jobs/file && test -d tests/fixtures/jobs/transform && test -d tests/fixtures/jobs/core && test -d tests/fixtures/jobs/swift && test -d tests/fixtures/data && test -f tests/fixtures/jobs/README.md && echo ok`
- **Expected outcome:** Stdout: `ok`. Directories tracked in git via `.gitkeep`.
- **Notes:** `.gitkeep` files are zero-byte by convention (empty files).

### Task 14-01-003 -- Create root `tests/conftest.py` with `run_job_fixture`, `assert_ascii_logs`, `PipelineResult`

- **Type:** infra
- **Description:** Create `tests/conftest.py` (root level -- complements existing `tests/v1/engine/conftest.py`). Implement:
    1. `PipelineResult` dataclass: `stats: Dict[str, Any]`, `global_map: Dict[str, Any]`, `engine: ETLEngine`, `json_path: Path`.
    2. `_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "jobs"`.
    3. `@pytest.fixture run_job_fixture(tmp_path)`: returns a callable `(name: str, mutations: Optional[Dict[str, Dict[str, Any]]] = None) -> PipelineResult`. Behavior per RESEARCH §Pattern 1: load JSON from `_FIXTURES_ROOT / f"{name}.json"`, copy into `tmp_path` (so mutations don't dirty the fixture), apply `mutations` (component_id -> {config_key: value}), invoke `ETLEngine(str(dst))` and `.execute()`, return `PipelineResult` with `dict(engine.global_map.get_all())`.
    4. `@pytest.fixture assert_ascii_logs(caplog)`: yields caplog at DEBUG; on teardown, fail if any captured log message contains a non-ASCII byte (project rule `feedback_ascii_logging`).
    5. ASCII-only docstrings in this file. Use `logger = logging.getLogger(__name__)` if logging needed (probably none).
- **Files to create or modify:** `tests/conftest.py`
- **Verification command:** `python -m pytest tests/conftest.py -q --collect-only && python -c "import tests.conftest as c; from inspect import signature; assert hasattr(c,'PipelineResult'); assert hasattr(c,'run_job_fixture'); assert hasattr(c,'assert_ascii_logs'); print('ok')"`
- **Expected outcome:** Stdout: `ok`; conftest collected without errors.
- **Notes:** Must NOT shadow or replace `tests/v1/engine/conftest.py` -- pytest discovers both via parent-walk. The root conftest provides cross-tree helpers; the engine conftest provides engine-specific fixtures (`StubComponent`, `java_bridge`).

### Task 14-01-004 -- Create `scripts/check_per_module_coverage.py` per-module floor enforcement

- **Type:** infra
- **Description:** Create `scripts/check_per_module_coverage.py` per RESEARCH §Per-Module Floor Enforcement Script (renamed). CLI: `python scripts/check_per_module_coverage.py <report> [--floor N]` (default floor 95.0). Reads coverage.json `files[].summary.percent_covered`, sorts failures, prints `FAIL: N module(s) below F% line coverage:` with `<pct>%  <path>  (missing K lines)` per failure, exits 1. On success, prints `PASS: all <N> in-scope modules at >= F% line coverage`, exits 0. Argparse signature: positional `report` (path), `--floor` (float, default 95.0). 30-50 LOC, stdlib-only.
- **Files to create or modify:** `scripts/check_per_module_coverage.py`
- **Verification command:** Synthesize a tiny coverage.json and assert behavior:
    ```bash
    python -c "
    import json, subprocess, tempfile, sys
    data = {'files': {'a.py': {'summary': {'percent_covered': 99.0, 'missing_lines': 1}}, 'b.py': {'summary': {'percent_covered': 80.0, 'missing_lines': 10}}}}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(data, f); p = f.name
    r = subprocess.run([sys.executable, 'scripts/check_per_module_coverage.py', p, '--floor', '95'], capture_output=True, text=True)
    assert r.returncode == 1, r.returncode
    assert 'b.py' in r.stderr
    print('ok-fail-case')
    data['files']['b.py']['summary']['percent_covered'] = 96.0
    with open(p, 'w') as f: json.dump(data, f)
    r = subprocess.run([sys.executable, 'scripts/check_per_module_coverage.py', p, '--floor', '95'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    print('ok-pass-case')
    "
    ```
- **Expected outcome:** Both `ok-fail-case` and `ok-pass-case` printed.
- **Notes:** Make script executable (`chmod +x`). Print failures to stderr (per RESEARCH design); print pass message to stdout.

### Task 14-01-005 -- Smoke validation: serial vs `-n auto` coverage equivalence (RESEARCH §A4)

- **Type:** infra (smoke)
- **Description:** Run `python -m pytest tests/v1/engine/test_executor.py --cov=src/v1/engine/executor --cov-report=json:cov_serial.json -q` and `python -m pytest tests/v1/engine/test_executor.py -n auto --cov=src/v1/engine/executor --cov-report=json:cov_parallel.json -q`. Compare `files["src/v1/engine/executor.py"].summary.percent_covered` between the two JSON files; assert equal (or within 0.5% for floating-point noise). If discrepancy, log issue to `14-PLAN-CHECK-NOTES.md` and surface for user review (do NOT block this plan -- subject to user override per CONTEXT.md A4).
- **Files to create or modify:** none persisted (smoke output to stderr; cleanup `cov_serial.json` `cov_parallel.json` after).
- **Verification command:** the smoke script itself; reports equivalent coverage or surfaces a discrepancy.
- **Expected outcome:** Console: `SMOKE OK -- serial=<N>%, parallel=<N>%`. Else `SMOKE DRIFT -- serial=<N>%, parallel=<M>% delta=<D>%` and a written entry in `14-PLAN-CHECK-NOTES.md`.
- **Notes:** Discrepancy possibilities: stale `.coverage*` files in working tree (run `rm -f .coverage*` first; this is also why the gate command starts with that step per locked Q5). One-shot validation; not committed.

### Task 14-01-006 -- Run end-to-end gate command on current tree (no subsystem lifts yet)

- **Type:** infra (smoke)
- **Description:** Validate the locked gate command runs to completion on the current tree (will FAIL the floor check since no lifts have happened yet -- expected). Confirms: (a) `pytest-xdist -n auto` works on the full suite without collisions, (b) `--cov-report=json` lands `coverage.json` at project root, (c) `scripts/check_per_module_coverage.py` parses the resulting JSON and reports the expected 53 modules below floor.
    Command:
    ```bash
    rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
      --cov=src/v1/engine --cov=src/converters \
      --cov-report=term-missing --cov-report=html --cov-report=json -q
    python scripts/check_per_module_coverage.py coverage.json --floor 95
    ```
- **Files to create or modify:** none committed (`coverage.json` is generated; not committed at this stage -- closeout commits the final one).
- **Verification command:** the gate command itself.
- **Expected outcome:** pytest exits 0 (tests green); `check_per_module_coverage.py` exits 1 with ~53 failures listed (the Phase 13 baseline). This baseline-mirroring failure list confirms the script + `coverage.json` shape are correct.
- **Notes:** Capture the failure list to compare against `13-COVERAGE-BASELINE.md` -- if it matches the FAIL rows there, infrastructure is ready. Add `coverage.json` to `.gitignore` if not already covered (verify via `git status` after the run).

</waves>

<verification_gate>

Plan 14-01 is GREEN when ALL of:

1. Task 14-01-001..004 verification commands pass.
2. `tests/conftest.py` collected by pytest without errors (`pytest tests/conftest.py --collect-only`).
3. `pyproject.toml` valid TOML; `pip install -e .[dev]` resolves the new pins.
4. `scripts/check_per_module_coverage.py --help` prints usage; pass+fail synthetic JSON cases work as specified.
5. End-to-end gate command (Task 14-01-006) lands `coverage.json` at project root with 53 modules below 95% (matching `13-COVERAGE-BASELINE.md`).
6. Smoke (Task 14-01-005) shows serial vs parallel coverage equivalent or surfaces drift to `14-PLAN-CHECK-NOTES.md`.
7. No new pragmas added.
8. All commits ASCII-only.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-01): INFRA-001 add pyproject coverage config + xdist/cov pins` | `pyproject.toml` |
| 2 | `chore(14-01): INFRA-002 scaffold tests/fixtures/jobs/{file,transform,core,swift} + README` | `tests/fixtures/jobs/.gitkeep`, `tests/fixtures/jobs/file/.gitkeep`, `tests/fixtures/jobs/transform/.gitkeep`, `tests/fixtures/jobs/core/.gitkeep`, `tests/fixtures/jobs/swift/.gitkeep`, `tests/fixtures/data/.gitkeep`, `tests/fixtures/jobs/README.md` |
| 3 | `chore(14-01): INFRA-003 add root tests/conftest.py with run_job_fixture and assert_ascii_logs` | `tests/conftest.py` |
| 4 | `chore(14-01): INFRA-004 add scripts/check_per_module_coverage.py per-module floor gate` | `scripts/check_per_module_coverage.py` |
| 5 | `chore(14-01): INFRA-005 record xdist+cov smoke validation result` | `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PLAN-CHECK-NOTES.md` (only if drift; else skip this commit) |
| 6 | `chore(14-01): INFRA-006 verify end-to-end gate command parses coverage.json` | (no file changes; document in plan summary) |

(Total: 5 to 6 commits depending on whether smoke surfaces drift.)

</commit_map>
