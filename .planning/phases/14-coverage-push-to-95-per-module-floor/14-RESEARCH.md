# Phase 14: Coverage Push to 95% per-module floor — Research

**Researched:** 2026-05-10
**Domain:** Test-writing / coverage tooling / fixture infrastructure (not a feature phase)
**Confidence:** HIGH — locked decisions in 14-CONTEXT.md narrow research scope; ecosystem patterns are well-established

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Module scope universe (Area A):**
- **D-A1: SWIFT engine modules in scope, full 95% lift.** `swift_transformer.py` (7%) and `swift_block_formatter.py` (7%) — both registered in `engine/components/transform/__init__.py`. ~800 stmts combined of new test surface.
- **D-A2: `file_input_json` (9%), `file_input_raw` (15%), `python_dataframe_component` (20%) all in scope.** Engine registers them; UI registry references them. Full lift required.
- **D-A3: `java_bridge_manager.py` measured WITH `-m java` markers.** Gate command requires JVM 11+. Aligns with project memory rule "test real bridge, not mocks". Gate: `pytest tests/ -m "not oracle" --cov=src/v1/engine --cov=src/converters ...`
- **D-A4: `send_mail.py` uses smtplib boundary mocking.** Mock `smtplib.SMTP` / `smtplib.SMTP_SSL` only; component-internal logic tested with real code paths.
- **D-A5: SWIFT fixtures = synthetic per the SWIFT user-handbook spec.** Generate representative MT103 / MT202 / MT940. No production samples required. If a code branch can't be hit with a synthetic message, flag dead code (D-C5).
- **D-A6: Oracle modules use mocked `oracledb`.** `oracle_output.py` (94%) and `oracle_row.py` (90%) lift via mocked Connection/Cursor. Live integration stays in `-m oracle` opt-in suite (Phase 11 testcontainer is the real bar).

**Test strategy & pragma policy (Area C):**
- **D-C1: Multi-component pipeline tests where they're the natural fit.** Lifecycle / globalMap / trigger / routing semantics modules (file_input_*, file_output_*, iterate, tMap variants, executor.py, base_component.py, base_iterate_component.py, trigger_manager.py, engine.py) get 2–5 small JSON-job pipeline tests per subsystem. Pure-pandas transforms stay as direct `_process()` unit tests.
- **D-C2: Pipeline tests load fixture .json files from `tests/fixtures/jobs/{subsystem}/{behavior}.json`.** Format mirrors converter output. Test code reads via conftest helper and runs through `ETLEngine.execute()`. Pattern mirrors `tests/integration/test_iterate_e2e.py`.
- **D-C3: Pragma allowlist (narrow).** `# pragma: no cover` allowed only on: `if __name__ == "__main__":`, `@abstractmethod` raising `NotImplementedError`, `try: import optional_dep / except ImportError:` shims. Anything else disallowed.
- **D-C4: Pure-pandas transforms — real-shape tests + targeted edge cases.** Realistic dtype mixes (object, StringDtype, Int64, datetime64, Decimal, float64). Every error branch hits documented custom exception (ETLError subclasses); assert exception type AND message-shape, not generic `pytest.raises(Exception)`.
- **D-C5: Dead-code policy.** Prefer **delete the dead branch** over `# pragma: no cover` over invented test setup. Document each deletion in the relevant plan's SUMMARY.md.

**Plan / wave structure & ordering (Area D):**
- **D-D1: ~13 plans total, sliced by subsystem.** (14-01 infra ... 14-13 closeout — see CONTEXT.md for full list).
- **D-D2: Plan order = Infra → Quick wins → Medium → Deep gaps → Closeout.** Plan 14-01 (infra) blocks every multi-component plan. Plan-checker enforces ordering via `Depends on:` annotations.
- **D-D3: Uniform 95% floor — no module drops below 95%.** All 198 in-scope modules end at >=95%. Phase 14 closeout fails if any current PASS regresses.
- **D-D4 (Claude's call): pytest-xdist `-n auto` + `@pytest.mark.slow` for tests >5s.** Gate command: `pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html`. Coverage > runtime — never trade real-production-path test coverage for runtime savings.

**Roadmap / requirements adjustments (Area E):**
- **D-E1: Roadmap SC#2 amended.** Replace "CI gate enforces..." with "Paste-runnable gate command documented in `14-COVERAGE.md` and CLAUDE.md; running the command verifies the 95% floor." Operational CI in a future phase.
- **D-E2: Two new requirement IDs.** Planner adds **TEST-11** (coverage push to 95% per-module floor) and **TEST-12** (paste-runnable gate command + COVERAGE.md). Both flip to `Complete` at phase closeout.
- **D-E3: COVERAGE.md replaces COVERAGE-BASELINE.md.** Final per-module table lives in `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md`. Phase 13's baseline file stays archived in its own phase dir.
- **D-E4: Coverage tool config in `pyproject.toml`.** Add `[tool.coverage.run]` (source = src/v1/engine, src/converters; omit = src/converters/complex_converter) and `[tool.coverage.report]` (per-module gate enforced via documented command + final table, NOT a global `fail_under`). Branch coverage stays off.

### Claude's Discretion

- Plan / wave decomposition fine-tuning (planner may merge 14-04 into 14-09, or split 14-08 into per-SWIFT-component plans, etc.)
- Specific fixture file names and JSON job shapes
- Exact TEST-11 / TEST-12 wording (subject to user review at planner gate)
- Pytest invocation flag set in the documented gate command (default markers, `-q`/`-v` toggles, etc.)
- STALE-test cleanup if encountered: apply Phase 13 D-D1 pattern (delete tests for engine-implemented features, log under STALE-NN in plan summaries)
- Whether `python_dataframe_component.py` (20%) needs synthetic DataFrame fixtures or if existing test patterns scale up cleanly

### Deferred Ideas (OUT OF SCOPE)

- **CI workflow file (GitHub Actions / Jenkinsfile / pre-commit)** — operational CI lands in a future phase
- **aiosmtpd-based local SMTP server** for send_mail integration tests
- **Hypothesis property-based testing** — deferred; standard tests sufficient for 95% floor
- **Real Oracle testcontainer in the gate command** — Phase 11 verification debt; stays human-run via `-m oracle` opt-in
- **Branch coverage** — off in Phase 14; future quality phase may layer on top
- **`complex_converter` removal** — legacy modules at 5–11%; explicit N/A
- **TEST-05, TEST-06 (Phase 15)** — real .item E2E + Talend output comparison
- **PERF-02, PERF-03, PERF-04 (Phase 15)** — performance work
- **Documentation sweep (Phase 16)**
- **Architectural fixes surfaced during the lift** — patch source per Phase 13 pattern when test surface reveals real bugs; major architectural changes defer to their own phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (planner to finalize wording) | Research Support |
|----|--------------------------------------------|------------------|
| TEST-11 | Coverage push to 95% per-module line floor: every module under `src/v1/engine/` and `src/converters/` (excl. `complex_converter`) reaches >=95% line coverage; new tests are real-behavior (no `# pragma: no cover` on logic branches per D-C3); pipeline-test infrastructure under `tests/fixtures/jobs/` exists; no module currently >=95% regresses. | Module-by-module gap analysis (§Module Triage), pipeline-test infra design (§Pipeline-Test Infrastructure), pragma allowlist enforcement (§Pragma Policy & Enforcement), uniform-floor enforcement script (§Coverage Tooling). |
| TEST-12 | Paste-runnable gate command + final `14-COVERAGE.md`: documented command in CLAUDE.md and `14-COVERAGE.md` reproduces the 95% floor verification; `[tool.coverage]` config lives in `pyproject.toml`; per-module final coverage table replaces `13-COVERAGE-BASELINE.md`; future-proof for the operational CI phase. | Gate-command spec (§Coverage Tooling — Gate Command), pyproject.toml config block (§Coverage Tooling — pyproject), per-module enforcement script (§Per-Module Floor Enforcement Script), COVERAGE.md template (§Closeout). |

**Note:** TEST-11 and TEST-12 are the new requirements. Phase 13 already added TEST-09 (zero failures) and TEST-10 (baseline measurement) — those are Complete and outside Phase 14 scope.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives are project-wide and bind every Phase 14 plan:

- **snake_case** for files, functions, variables; **PascalCase** for classes; **UPPER_SNAKE_CASE** for constants
- **ASCII-only logging** — no emojis or unicode in log messages (RHEL servers need clean ASCII). Test fixtures and harness output included.
- **Custom exception hierarchy** — `ETLError` → `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`. Tests must assert these specific types, never generic `Exception`.
- **No fallbacks for bad data** — fix at the source. Phase 14 still applies: when a test surfaces a bug, patch the source root cause (Phase 13 D-B1 through D-B4 precedent), don't add a defensive shim downstream.
- **No new components or features in Phase 14.** Test-only phase. CLAUDE.md "rewrite over patch" applies to dead-code removal (D-C5).
- **pyproject.toml is the canonical dependency manifest.** D-E4 adds `[tool.coverage]` sections; existing `[project.optional-dependencies]` and `[tool.pytest.ini_options]` sections are not rewritten.
- **No `print()` statements in source or tests** — use `logger`.
- **Engine component lifecycle is a contract.** Tests of `_process()` directly (unit-test path) must mirror `execute()` Step 1 — populate `self.config = dict(_original_config)` — or call through `execute()`. The existing pattern is in `tests/v1/engine/components/control/test_send_mail.py::_make_component`.

## Summary

Phase 14 is a pure test-writing phase. The work is mechanical at scale (~52–53 module lifts) but requires three pieces of new shared infrastructure: a **pipeline-test runner** (Plan 14-01), a **synthetic SWIFT message generator** (Plan 14-08), and a **per-module floor enforcement script** (closeout). The dominant pattern for execution is "extend an existing test file with edge-case + error-branch tests until coverage reaches 95% on a single module" — every below-95% engine module already has a test file under `tests/v1/engine/components/<subsystem>/`. SWIFT is the one exception: there are zero engine SWIFT tests today.

Tooling is straightforward: pytest 9.0.2 + pytest-cov 7.0.0 + pytest-xdist 3.8.0 are installed (xdist is **NOT** declared in pyproject's `dev` extra — Plan 14-01 must add it). Coverage data combines automatically when pytest-cov runs under `-n auto`. Per-module 95% gating is not built into pytest-cov (only a global `--cov-fail-under` exists), so closeout (Plan 14-13) ships a small Python script that parses `coverage json -o coverage.json` and exits non-zero if any in-scope module falls below 95%.

The biggest single risk is SWIFT (Plan 14-08, ~800 stmts at 7%): the module branches on YAML config shape, MT message block structure, and lookup-file presence; synthetic message generators must exercise every branch or the coverage gate fails. The deepest core-engine gap (`java_bridge_manager.py` 59%) is bounded by JVM-lifecycle paths covered only via `-m java` tests — the JAR is already in-tree (Phase 13 rebuild), so the lift is straightforward once `JavaBridgeError` retry/library/routine-load paths are tested.

**Primary recommendation:** Build Plan 14-01 first (pipeline-test infra), generate the SWIFT synthetic generator in Plan 14-08 (the only hard part), and run the existing module-test extension pattern across the remaining 50 lifts in subsystem batches. Closeout's enforcement script is a 30-line Python file that reads `coverage.json` — there is no need to invent a custom test framework.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pipeline-test fixture loader | Test infrastructure | — | Lives under `tests/conftest.py` (root) or `tests/fixtures/conftest.py`; reads JSON job files; spins up `ETLEngine.execute()`. Not engine code. |
| SWIFT synthetic message generator | Test infrastructure | — | Lives under `tests/fixtures/swift/` as a helper module; generates valid MT103/MT202/MT940 strings. Pure test helper. |
| Per-module 95% floor gate | Build / CI tooling | — | Small Python script under `scripts/` or `tests/_tools/`; reads `coverage.json` produced by pytest-cov. NOT a pytest plugin. |
| Coverage tool config | pyproject.toml | — | `[tool.coverage.run]` and `[tool.coverage.report]` sections. Standard coverage.py config layered on existing pyproject. |
| Boundary mocks (smtplib, oracledb) | Test infrastructure (per-subsystem conftest) | — | Existing send_mail and oracle_output tests already use this pattern — extend, don't centralize. |
| `-m java` real-bridge tests for `java_bridge_manager.py` | Engine test (existing `tests/v1/engine/`) | — | Real JVM via existing `java_bridge` fixture in `tests/v1/engine/conftest.py`. |
| Module-level test extensions (50 lifts) | Existing per-component test files | — | Every below-95 module already has a test file. Extend it; do not invent new layout. |

## Standard Stack

### Core (already installed and pinned)

| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| pytest | 9.0.2 [VERIFIED: pip show] | Test runner; project-pinned `>=8.0,<10` in pyproject `dev` extra | Already adopted; Phase 13 baseline. |
| pytest-cov | 7.0.0 [VERIFIED: pip show] | Coverage measurement under pytest | Already adopted; Phase 13 baseline. coverage.py 7.x supported. [CITED: github.com/pytest-dev/pytest-cov via Context7] |
| pytest-xdist | 3.8.0 [VERIFIED: pip show] | Parallel test execution (`-n auto`) | Installed but **NOT declared** in pyproject's `dev` extra. Plan 14-01 MUST add `pytest-xdist>=3.5,<4` to `[project.optional-dependencies].dev` so other contributors get it via `pip install -e .[dev]`. |
| coverage.py | bundled with pytest-cov [CITED: pytest-cov docs] | Underlying coverage engine; supplies `coverage.json` for the gate script | Configurable via `[tool.coverage.*]` in pyproject.toml. |
| pandas | 3.0.1 [VERIFIED: pip show] | Runtime data transport; tests must use realistic dtypes | CoW semantics in 3.0 — `inplace=True` no longer mutates original copy (project memory). |

### Supporting (already used elsewhere; reuse, don't introduce)

| Library | Where Used | Purpose | When to Use |
|---------|-----------|---------|-------------|
| `unittest.mock` (stdlib) | `test_send_mail.py`, `test_oracle_output.py` | Boundary mocking for smtplib, oracledb | D-A4 (smtplib), D-A6 (oracledb). Use `MagicMock` and `patch` exactly as existing tests do. |
| pytest fixtures (built-in `tmp_path`, `caplog`) | Throughout `tests/integration/test_iterate_e2e.py` | Filesystem fixtures, log assertions | Every pipeline test needs `tmp_path`; every ASCII-log assertion uses `caplog` + `caplog.records[i].getMessage().encode("ascii")`. |
| `@pytest.mark.java` (already declared in pyproject markers) | Engine tests requiring real JVM | Opt-in JVM-dependent suite | D-A3 — `java_bridge_manager.py` real-bridge lifecycle tests. Existing fixture: `java_bridge` in `tests/v1/engine/conftest.py`. |
| `@pytest.mark.oracle` (already declared) | `tests/v1/engine/components/database/integration/` | Opt-in real-DB suite (Phase 11 testcontainer) | Excluded from gate command via `-m "not oracle"`. |
| `@pytest.mark.slow` (already declared) | TBD | Tests >5s | D-D4 — annotate any new SWIFT/Excel/JSON pipeline tests that exceed 5s wall time. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff (and why we chose the locked decision) |
|------------|-----------|--------------------------------------------------|
| `pytest --cov-fail-under=95` (global) | Per-module gate script | Global threshold passes when 145 modules at 100% mask 53 modules at 70%. D-D3 mandates per-module; CONTEXT.md explicitly forbids global gate. |
| Hypothesis property-based tests for SWIFT | Hand-written synthetic MT samples | Hypothesis is faster to write but slower to run, and SWIFT MT format is structured enough that explicit fixtures cover branches deterministically. CONTEXT.md `## Deferred Ideas` excludes Hypothesis. |
| aiosmtpd in-process SMTP server for send_mail | smtplib boundary mocks | Real-server tests are slower and require port management; D-A4 already chose mocks because internal logic (config parsing, MIME building) is the high-value test surface. |
| Real `oracledb` testcontainer in the gate | Mocked Connection/Cursor | Phase 11 already shipped a testcontainer suite under `-m oracle`; running it in the gate would require Docker in every contributor environment. D-A6 keeps the gate env-independent for Oracle. |
| pytest-cov subprocess patching | Direct coverage in single process | Plan 14-11 may exercise `python_routine_manager.py` paths that fork; if so, `[tool.coverage.run] patch = ["subprocess"]` automatically enables parallel mode [CITED: coverage.py via Context7]. Default-off; only add if Plan 14-11 needs it. |

**Installation:** No new packages required. Only pyproject.toml changes:

```toml
# pyproject.toml — Plan 14-01 adds pytest-xdist to dev extra
[project.optional-dependencies]
dev = [
    "pytest>=8.0,<10",
    "pytest-cov>=7.0,<8",          # add: was implicit, declare explicitly
    "pytest-xdist>=3.5,<4",         # add: required by D-D4 -n auto
    "testcontainers>=4",
]
```

**Version verification (per [VERIFIED] tags above):** `pip show pytest pytest-cov pytest-xdist pandas` confirmed installed versions match claims as of 2026-05-10.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Phase 14 work                            │
│                                                                   │
│   Plan 14-01: Pipeline-test infrastructure                       │
│       ┌───────────────────────────────────────────┐              │
│       │  tests/conftest.py (NEW)                  │              │
│       │   - run_job_fixture(name)                 │              │
│       │   - ascii_log_capture                     │              │
│       │  tests/fixtures/jobs/{subsystem}/*.json   │              │
│       │  tests/fixtures/swift/synthetic.py (Plan 14-08)│         │
│       └───────────────────────────────────────────┘              │
│                       │                                           │
│                       ▼                                           │
│   Plans 14-02..14-12: Module test extensions (~50 modules)       │
│       ┌─────────────────────┐    ┌─────────────────────┐         │
│       │ Pure-pandas transform│    │ Lifecycle component │         │
│       │ test_<x>.py extends  │    │ pipeline test       │         │
│       │ direct _process()    │    │ via run_job_fixture │         │
│       │ unit tests           │    │ + JSON fixture      │         │
│       └─────────────────────┘    └─────────────────────┘         │
│                       │                          │                │
│                       └────────────┬─────────────┘                │
│                                    ▼                              │
│   Plan 14-13: Closeout                                            │
│       ┌────────────────────────────────────────────┐             │
│       │  pytest -n auto -m "not oracle" --cov ...  │             │
│       │     │                                       │             │
│       │     └─▶ coverage json -o coverage.json     │             │
│       │           │                                 │             │
│       │           └─▶ scripts/check_coverage_floor.py│           │
│       │                 │                           │             │
│       │                 ├─ exit 0 if all >= 95%   │              │
│       │                 └─ exit 1 + list failures │              │
│       │                                             │             │
│       │  14-COVERAGE.md (final per-module table)  │              │
│       │  CLAUDE.md (gate command updated)         │              │
│       └────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

Data flow:
1. A plan's tests (unit or pipeline) execute against engine source.
2. pytest-cov accumulates line-level coverage data (combined automatically across xdist workers).
3. `coverage json` emits per-file `percent_covered` in `coverage.json`.
4. `check_coverage_floor.py` reads JSON, applies `[tool.coverage.run] source` and `omit` to filter in-scope modules, and exits non-zero if any < 95%.

### Recommended Project Structure

```
tests/
├── conftest.py                          # NEW (root) — run_job_fixture, ascii_log_capture
├── fixtures/                            # NEW
│   ├── jobs/                            # JSON job configs for pipeline tests
│   │   ├── file/                        # tFileInputDelimited, tFileOutputDelimited, ...
│   │   │   ├── csv_with_header.json
│   │   │   ├── csv_with_reject.json
│   │   │   └── ...
│   │   ├── transform/                   # tMap, tFilterRow, ...
│   │   ├── iterate/                     # tFileList, tFlowToIterate (already covered by Phase 10)
│   │   ├── core/                        # multi-component pipelines for executor.py / engine.py
│   │   └── swift/                       # SWIFT-specific job configs
│   ├── swift/                           # NEW — Plan 14-08 work
│   │   ├── __init__.py
│   │   ├── synthetic.py                 # MT103/MT202/MT940 generators
│   │   └── layouts/                     # YAML layout files for swift_block_formatter
│   └── data/                            # raw input data (CSVs, .xlsx, .json) for tests
└── (existing test tree unchanged)

scripts/                                 # NEW
└── check_coverage_floor.py              # per-module 95% gate script

pyproject.toml                           # MODIFIED — add [tool.coverage.run] and [tool.coverage.report]
```

### Pattern 1: Pipeline-Test via run_job_fixture

**What:** A pytest fixture that loads a `tests/fixtures/jobs/<subsystem>/<behavior>.json` file, optionally applies path/config mutations, runs it through `ETLEngine.execute()`, and returns a typed result with stats, globalMap, and output paths.

**When to use:** Every module flagged D-C1 (lifecycle / globalMap / trigger / routing semantics matter): file_input_*, file_output_*, executor.py, base_component.py, base_iterate_component.py, trigger_manager.py, engine.py, java_bridge_manager.py, plus tMap variants.

**Example (proposed shape):**

```python
# Source: synthesized from tests/integration/test_iterate_e2e.py pattern
# Lives in tests/conftest.py (NEW)
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from src.v1.engine.engine import ETLEngine


@dataclass
class PipelineResult:
    """Typed return for pipeline tests.

    Attributes:
        stats: Engine.execute() return dict (status, error, components, ...).
        global_map: Snapshot of GlobalMap.get_all() after execute.
        engine: The ETLEngine instance (for follow-up assertions on flows).
        json_path: Path to the mutated/copied JSON config used for the run.
    """
    stats: Dict[str, Any]
    global_map: Dict[str, Any]
    engine: ETLEngine
    json_path: Path


_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "jobs"


@pytest.fixture
def run_job_fixture(tmp_path):
    """Run a fixture JSON job through ETLEngine.execute().

    Usage::

        def test_csv_with_reject(run_job_fixture, tmp_path):
            result = run_job_fixture(
                "file/csv_with_reject",
                mutations={
                    "tFileInputDelimited_1": {"filepath": str(tmp_path / "in.csv")},
                    "tFileOutputDelimited_1": {"filepath": str(tmp_path / "out.csv")},
                },
            )
            assert result.stats["status"] == "success"
            assert result.global_map["tFileInputDelimited_1_NB_LINE_REJECT"] == 2

    Args:
        name: Path under tests/fixtures/jobs/ without .json suffix
              (e.g. "file/csv_with_reject" -> tests/fixtures/jobs/file/csv_with_reject.json).
        mutations: Optional dict mapping component_id -> {config_key: value}.
                   Mirrors _mutate_json_paths in tests/integration/test_iterate_e2e.py.

    Returns:
        PipelineResult with stats + globalMap snapshot + engine reference.
    """
    def _runner(name: str, mutations: Optional[Dict[str, Dict[str, Any]]] = None) -> PipelineResult:
        src = _FIXTURES_ROOT / f"{name}.json"
        if not src.exists():
            raise FileNotFoundError(f"Pipeline fixture not found: {src}")
        # Copy into tmp_path so mutations don't dirty the fixture
        dst = tmp_path / f"{name.replace('/', '_')}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(src, "r", encoding="utf-8") as f:
            config = json.load(f)
        if mutations:
            for comp in config.get("components", []):
                cid = comp.get("id")
                if cid in mutations:
                    comp.setdefault("config", {}).update(mutations[cid])
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        engine = ETLEngine(str(dst))
        stats = engine.execute()
        return PipelineResult(
            stats=stats,
            global_map=dict(engine.global_map.get_all()),
            engine=engine,
            json_path=dst,
        )

    return _runner
```

### Pattern 2: ASCII-only log assertion fixture

**What:** A `caplog`-driven helper that asserts no test produces non-ASCII log output (project memory `feedback_ascii_logging` requirement).

**When to use:** Every pipeline test (Phase 10 already does this manually — fold it into a fixture).

**Example:**

```python
# tests/conftest.py
import pytest


@pytest.fixture
def assert_ascii_logs(caplog):
    """Yield caplog; on test exit, fail if any captured log message is non-ASCII.

    Usage::

        def test_something(run_job_fixture, assert_ascii_logs):
            result = run_job_fixture("file/csv_with_header")
            assert result.stats["status"] == "success"
            # assert_ascii_logs runs at teardown and raises if non-ASCII found
    """
    import logging as _logging
    with caplog.at_level(_logging.DEBUG):
        yield caplog
        bad = []
        for rec in caplog.records:
            try:
                rec.getMessage().encode("ascii")
            except UnicodeEncodeError:
                bad.append(rec.getMessage())
        if bad:
            pytest.fail(
                "Non-ASCII log messages captured (project rule: ASCII-only logs):\n"
                + "\n".join(repr(m) for m in bad[:5])
            )
```

### Pattern 3: Boundary mock for smtplib (D-A4)

**What:** Mock `smtplib.SMTP` and `smtplib.SMTP_SSL` at module scope in `send_mail.py`. The pattern already exists in `tests/v1/engine/components/control/test_send_mail.py:111`.

**Example:**

```python
# Source: extends tests/v1/engine/components/control/test_send_mail.py
from unittest.mock import MagicMock, patch


def test_send_mail_starttls(self):
    config = dict(_BASE_CONFIG)
    config.update({"smtp_port": 587, "starttls": True, "auth_username": "u", "auth_password": "p"})
    comp = _make_component(config)

    with patch("src.v1.engine.components.control.send_mail.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        comp._process()

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("u", "p")
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()
```

For SSL: patch `smtplib.SMTP_SSL` instead. For attachment failure paths: use `tmp_path / "missing.txt"` for `FileOperationError` tests. The 49 missed lines in `send_mail.py` are concentrated in: SSL branch (lines ~227–230), starttls branch (~232–234), attachment exception branches (~210–223), `die_on_error=False` warning paths (~250–253), and the catch-all `Exception` branch (~255–260). Each needs one targeted test.

### Pattern 4: Boundary mock for oracledb (D-A6)

**What:** `MagicMock` for both `Connection` and `Cursor`. Pattern is established in `tests/v1/engine/components/database/test_oracle_output.py:_make_mock_oracle_manager`.

**Example:**

```python
# Source: tests/v1/engine/components/database/test_oracle_output.py:64-77
def _make_mock_oracle_manager(autocommit=False, batch_errors=None):
    mgr = MagicMock()
    mock_conn = MagicMock(autocommit=autocommit)
    mock_cursor = MagicMock()
    mock_cursor.getbatcherrors.return_value = batch_errors or []
    mock_conn.cursor.return_value = mock_cursor
    mgr.get.return_value = mock_conn
    mgr.open_ad_hoc.return_value = mock_conn
    return mgr, mock_conn, mock_cursor
```

For `oracle_row.py` (90% → 95%, 13 missed lines): test the rare branches — execute-many error paths, PARAMETER_TYPE coercion edge cases for less-common Oracle types, USE_NB_LINE counter when 0 rows returned.

For `oracle_output.py` (94% → 95%, 26 missed lines): test the rarer DATA_ACTION × TABLE_ACTION matrix corners (e.g., `INSERT_OR_UPDATE` on empty input, `UPDATE` with no key columns), and the `ConfigurationError` branches for missing required config.

### Anti-Patterns to Avoid

- **`pytest.raises(Exception)` instead of the specific `ETLError` subclass** — D-C4 forbids. Always use `ConfigurationError`, `ComponentExecutionError`, `FileOperationError`, etc.
- **Coverage gaming via `# pragma: no cover` on logic branches** — D-C3. Reviewers reject pragmas outside the narrow allowlist.
- **Mocking `JavaBridge` in pipeline tests** — D-A3 + project memory `feedback_test_real_bridge`. Use the real `java_bridge` fixture under `@pytest.mark.java`.
- **Single-row pandas DataFrames as the "realistic" fixture** — D-C4. Multi-row, multi-column, mixed-dtype frames surface CoW + StringDtype edges that single rows miss.
- **Asserting only `stats["status"] == "success"`** — pipeline tests must additionally verify globalMap keys (`{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT`) and output flow content where applicable.
- **Inventing JSON job shapes that don't match converter output** — D-C2. Pipeline JSON fixtures must mirror what `convert_job()` actually emits. To avoid drift, generate the first round of fixtures by running the converter on existing `.item` samples and trimming.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-module coverage gating | A pytest plugin | A 30-line script that reads `coverage json` output | coverage.py already produces `percent_covered` per file; the script is trivial. A plugin would duplicate coverage.py's data model. |
| SWIFT MT message parsing in tests | A full ISO 15022 parser | Hand-written string templates with `.format()` placeholders for required fields | The engine code is what we're testing; the test fixtures only need to be syntactically valid MT, not standards-compliant. |
| Pipeline-test JSON job synthesis | A fluent DSL builder | Static JSON files generated once by running `convert_job()` on `.item` samples | Static JSON catches converter→engine contract drift. A DSL adds maintenance burden and hides drift. |
| ASCII-log policy enforcement | A pytest plugin | A reusable `caplog` fixture (Pattern 2 above) | One-shot fixture is sufficient and discoverable. |
| Subprocess coverage for Java bridge | Custom Coverage.py instrumentation of subprocesses | Real `-m java` tests + the existing `java_bridge` fixture | `java_bridge_manager.py` runs in the parent Python process; the JVM is a subprocess but its lifecycle paths (start, stop, retry, library-load, routine-load, error rewrap) ARE Python code paths that real-bridge tests reach naturally. |
| smtplib server simulation | aiosmtpd in-process server | `unittest.mock.patch("...smtplib.SMTP")` | D-A4 locked. The 49 missed lines in `send_mail.py` are component logic, not transport behavior; mocks suffice. |
| oracledb integration | Per-test testcontainer | `MagicMock` for Connection/Cursor + opt-in `-m oracle` suite | D-A6 locked. Phase 11 testcontainer covers real-DB integration. |

**Key insight:** Phase 14 is dominated by extension of existing test patterns. Inventing new abstractions (DSLs, plugins, custom frameworks) increases surface area for bugs and reviewer fatigue. The locked decisions in CONTEXT.md are deliberately conservative — every pattern Phase 14 needs already exists in the test tree, just not at the volume Phase 14 requires.

## Module Triage (53 lift targets)

> Cross-referenced against `13-COVERAGE-BASELINE.md` per-subsystem table. Effort sizing: **S** = 1–4 missed lines (single test extension); **M** = 5–30 missed lines (multi-test extension); **L** = 30+ missed lines (significant test surface, may need pipeline tests). Numbers in parentheses are missed-line counts from the Phase 13 baseline.

### engine.components.file (16 lifts)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `file_list.py` | 94% | 11 | pipeline + unit | S | Existing tests at `test_file_list.py`. Phase 13 BUG-FL-001 already added NB_FILE; remaining gap likely in glob/regex error branches and sort-order edge cases. |
| `file_unarchive.py` | 92% | 5 | unit | S | Add edge cases for unsupported archive type + permission errors. |
| `file_properties.py` | 91% | 4 | unit | S | Trivial — error branches on missing file / permission errors. |
| `file_copy.py` | 92% | 8 | unit | S | Add overwrite-collision, source-missing, permission branches. |
| `file_input_properties.py` | 88% | 10 | unit | M | Test invalid `.properties` syntax, encoding mismatches. |
| `fixed_flow_input.py` | 88% | 14 | unit | M | Existing tests at `test_fixed_flow_input.py`. Add multi-row + schema-validation edges. |
| `set_global_var.py` | 89% | 7 | unit + pipeline | S | Pipeline test verifies variables flow to downstream component. |
| `file_input_delimited.py` | 86% | 53 | pipeline + unit | M-L | Largest delimited-input module by stmts (374). Most existing tests are unit; pipeline tests add CSV-mode + RFC4180 edge cases. |
| `file_output_delimited.py` | 83% | 46 | pipeline + unit | M-L | Existing tests at `test_file_output_delimited.py`. Add file-split, FILE_EXIST_EXCEPTION, multi-char delimiter branches. |
| `file_output_positional.py` | 83% | 44 | unit | M-L | Symmetrical to file_input_positional; add column-width edge cases. |
| `file_input_positional.py` | 81% | 33 | unit | M | Add date_pattern + thousands/decimal-separator branches. |
| `file_touch.py` | 83% | 9 | unit | S | Add timestamp-clobber and create-vs-update branches. |
| `file_output_excel.py` | 69% | 91 | pipeline + unit | L | Phase 13 BUG-EXC-001 already fixed defensive read; 91 missed lines likely in advanced-format branches (cell styles, formulas, multi-sheet). Real .xlsx fixtures in `tests/fixtures/data/`. |
| `file_input_excel.py` | 29% | 419 | pipeline + unit | L | **Deep gap.** 588 stmts of Excel-format-branching code: .xls vs .xlsx, password-protected, regex sheet matching, advanced separators, date conversion, streaming vs batch. Real .xls + .xlsx fixtures required. |
| `file_input_json.py` | 9% | 156 | pipeline + unit | L | **Deep gap.** Existing test scaffolding minimal; needs JSONPath fixtures, URL-read paths (mock `urlopen`), date-parse + advanced-separator branches. |
| `file_input_raw.py` | 15% | 51 | unit | M | **Deep gap, but small file.** 60-line module reading file as single field. Tests need: as_string True/False, encoding variations, missing file with die_on_error True/False, Windows/Unix/Mac line-ending detection (debug_content). |

### engine.components.transform (17 lifts)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `replace.py` | 94% | 6 | unit | S | Quick win — existing test at `test_replace.py`. |
| `python_row_component.py` | 93% | 4 | unit | S | Existing test at `test_python_row_component.py`. Per-row error + REJECT edges. |
| `pivot_to_columns_delimited.py` | 91% | 10 | unit | S-M | Existing test at `test_pivot_to_columns_delimited.py`. |
| `parse_record_set.py` | 89% | 7 | unit | S | Existing test at `test_parse_record_set.py`. |
| `row_generator.py` | 84% | 15 | unit | M | Existing test at `test_row_generator.py`. Random/sequential modes, type generators. |
| `python_component.py` | 84% | 6 | unit | S | Existing test at `test_python_component.py`. D-11 secure namespace branches. |
| `extract_positional_fields.py` | 87% | 14 | unit | M | Existing test at `test_extract_positional_fields.py`. Padding + truncation edges. |
| `extract_regex_fields.py` | 86% | 14 | unit | M | Existing test at `test_extract_regex_fields.py`. Phase 13 already fixed regex storage convention. Edge: invalid regex → `ConfigurationError`. |
| `convert_type.py` | 86% | 15 | unit | M | Existing test at `test_convert_type.py`. Phase 13 BUG-CT-001 added MANUALTABLE numeric fallback; remaining gap in type-coercion error paths. |
| `extract_json_fields.py` | 86% | 18 | unit | M | Existing test at `test_extract_json_fields.py`. JSONPath syntax errors, missing keys. |
| `extract_delimited_fields.py` | 83% | 18 | unit | M | Existing test at `test_extract_delimited_fields.py`. Inconsistent column counts. |
| `filter_rows.py` | 80% | 32 | unit + pipeline | M | Existing test at `test_filter_rows.py`. AST parser branches (FROW-01) + 14 operators (FROW-02) — inventory which operators are covered, fill gaps. |
| `map.py` | 77% | 198 | pipeline + unit | L | **868-stmt module.** Existing tests at `test_map.py`, `test_map_integration.py`, `test_map_method_size.py`. Heavy lift but mature test infra. Gap in: `enable_auto_convert_type` per-key paths, RELOAD_AT_EACH_ROW edges (Phase 5.2 fixed 4 bugs but coverage may have gaps), inner-join reject schema. |
| `join.py` | 69% | 45 | pipeline + unit | L | Existing test at `test_join.py`. Case-insensitive join branch (JOIN-01), null-key handling (JOIN-08), reject schema (JOIN-03). |
| `python_dataframe_component.py` | 20% | 37 | unit | M | **Deep gap, small file.** 46-stmt module: `python_code` exec on full DataFrame. Tests need: `output_columns` filter, routines availability, error branches. CONTEXT.md flags as Claude's discretion whether synthetic fixtures or existing patterns scale up. **Recommendation: existing patterns scale up cleanly** — the module is a thin wrapper around `exec(python_code, namespace)`; unit tests with hand-rolled namespaces suffice. |
| `swift_transformer.py` | 7% | 409 | unit + pipeline | L | **Largest deep gap (441 stmts).** Plan 14-08 enabling work — see §SWIFT Synthetic Generator below. |
| `swift_block_formatter.py` | 7% | 382 | unit + pipeline | L | **Second-largest deep gap (410 stmts).** Plan 14-08 enabling work — see §SWIFT Synthetic Generator below. |

### engine.components.aggregate (1 lift)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `aggregate_row.py` | 79% | 43 | unit | M | Existing tests rich (Phase 6 + 7.1 + 13). 43 missed lines likely in: list_object/union/population_std_dev (AGGR-04 paths), Decimal handling (AGGR-06), column-collision in grouped mode (AGGR-08), financial-precision toggle (AGGR-07). |

### engine.components.control (1 lift)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `send_mail.py` | 60% | 49 | unit (boundary mock) | M | See §Boundary mock for smtplib (D-A4). 49 missed lines = SSL/STARTTLS branches + attachment exceptions + die_on_error=False paths + catch-all Exception. |

### engine.components.database (2 lifts)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `oracle_output.py` | 94% | 26 | unit (boundary mock) | M | See §Boundary mock for oracledb (D-A6). Likely gap in rare TABLE_ACTION × DATA_ACTION corners. |
| `oracle_row.py` | 90% | 13 | unit (boundary mock) | M | PARAMETER_TYPE coercion + USE_NB_LINE edge cases. |

### engine (core, 7 lifts)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `trigger_manager.py` | 91% | 13 | unit + pipeline | M | RunIf, OnComponentOk/Error, OnSubjobOk timing branches. |
| `executor.py` | 91% | 30 | pipeline | M | Phase 12 commit `55d8354` finalization order; iterate stall paths; reject-flow routing. |
| `base_iterate_component.py` | 88% | 11 | pipeline | M | Iteration finalization; should_stop variants. |
| `base_component.py` | 87% | 69 | unit + pipeline | L | Largest core gap (526 stmts). Schema validation + dtype coercion + reject-flow + die_on_error + per-chunk streaming paths. |
| `python_routine_manager.py` | 82% | 18 | unit | M | Routine discovery, load failures, namespace assembly. |
| `engine.py` | 81% | 33 | pipeline | M | Top-level orchestrator; error-handling and cleanup paths. |
| `java_bridge_manager.py` | 59% | 41 | unit + `-m java` | M | See §Java Bridge Gate Strategy below. |

### converters.talend_to_v1 (core, 2 lifts)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `converter.py` | 94% | 13 | unit | S | Existing tests at `tests/converters/talend_to_v1/test_converter.py`. Edge: malformed `.item`, missing components, validator error propagation. |
| `expression_converter.py` | 78% | 20 | unit | M | Java→Python translation edge cases; `detect_java_expression` patterns. |

### converters.talend_to_v1.components (6 lifts)

| Module | Cover | Miss | Test fit | Effort | Notes |
|--------|------:|-----:|---------|:------:|-------|
| `file/file_input_excel.py` | 94% | 7 | unit | S | Quick win. |
| `transform/replace.py` | 94% | 6 | unit | S | Quick win. |
| `transform/xml_map.py` | 93% | 15 | unit | M | Phase 12 added rich tests; remaining gap in conditional-needs_review edge cases. |
| `aggregate/aggregate_row.py` | 91% | 11 | unit | M | Phase 13 already updated NeedsReview count to >= 1; 11 missed lines likely in remaining corner cases. |
| `iterate/foreach.py` | 94% | 2 | unit | S | Trivial. |
| `database/mssql_input.py` | 81% | 12 | unit | M | MSSQL converter (Phase v2 territory) — basic conversion paths likely covered, error branches not. |

**Total module-edit effort distribution (rough):** ~25 quick wins (S, mostly 1–4 missed lines), ~20 medium gaps (M), ~8 deep gaps (L) including SWIFT × 2.

## Pipeline-Test Infrastructure (Plan 14-01 design)

### File layout

```
tests/
├── conftest.py                          # NEW (root)
└── fixtures/
    └── jobs/
        ├── file/
        │   ├── csv_with_header.json     # tFileInputDelimited basic
        │   ├── csv_with_reject.json     # CHECK_FIELDS_NUM reject flow
        │   ├── csv_split_output.json    # FOLD-04 file split
        │   ├── excel_simple.json
        │   ├── json_jsonpath.json
        │   └── raw_text.json
        ├── transform/
        │   ├── filter_then_map.json
        │   └── join_with_reject.json
        ├── core/
        │   ├── trigger_runif.json       # trigger_manager test
        │   ├── multi_subjob.json        # executor test
        │   └── reject_routing.json      # base_component reject flow
        └── swift/
            ├── mt103_basic.json
            ├── mt202_with_lookup.json
            └── mt940_block_formatter.json
```

### Loader fixture

See Pattern 1 above (`run_job_fixture`). Implementation lives in `tests/conftest.py` (NEW root). The fixture:

1. Resolves `name` → `tests/fixtures/jobs/{name}.json`.
2. Copies the JSON into `tmp_path` (so mutations don't dirty the fixture).
3. Applies `mutations` dict (component_id → config patches; mirrors `_mutate_json_paths` from `test_iterate_e2e.py`).
4. Instantiates `ETLEngine(str(dst))` and calls `execute()`.
5. Returns `PipelineResult(stats, global_map, engine, json_path)`.

### Integration with existing tests

- The new `tests/conftest.py` is at the test-tree root and complements (does not replace) the existing `tests/v1/engine/conftest.py` (which provides `StubComponent`, `IterateStubComponent`, `make_job_config`, `java_bridge`).
- Pipeline tests under `tests/v1/engine/components/file/` etc. import `run_job_fixture` from the root conftest by virtue of pytest's automatic conftest discovery up the directory tree.
- The existing `tests/integration/conftest.py` `java_bridge` fixture is session-scoped and complements (does not conflict with) the engine-level `java_bridge` in `tests/v1/engine/conftest.py`. Pipeline tests that need real JVM use `@pytest.mark.java` and request `java_bridge` as before.

### Pattern for "small JSON job" templates

A pipeline-test JSON should:
- Have **1–3 components** (input + transform + output is the canonical shape).
- Use **placeholder paths** like `"filepath": "TBD_via_mutations"` so the mutations dict drives every test instance.
- Mirror the structure of converter output (`{"job": {...}, "components": [...], "flows": [...], "triggers": [...], "subjobs": [...], "context": {...}}`).
- Be **generated initially** by running `convert_job()` against existing `tests/talend_xml_samples/Job_*.item` files and trimming to the minimum needed for the behavior under test.

### Asserting on globalMap, output flows, exception types after execute

```python
def test_csv_with_reject(run_job_fixture, tmp_path):
    # Set up input file
    input_csv = tmp_path / "in.csv"
    input_csv.write_text("id;name;salary\n1;Alice;100\nbad row\n3;Bob;NOT_A_NUMBER\n", encoding="iso-8859-15")

    result = run_job_fixture(
        "file/csv_with_reject",
        mutations={
            "tFileInputDelimited_1": {"filepath": str(input_csv)},
            "tFileOutputDelimited_1": {"filepath": str(tmp_path / "out.csv")},
            "tFileOutputDelimited_reject": {"filepath": str(tmp_path / "reject.csv")},
        },
    )

    # 1. Job-level success
    assert result.stats["status"] == "success"

    # 2. globalMap stat keys
    assert result.global_map["tFileInputDelimited_1_NB_LINE"] == 3
    assert result.global_map["tFileInputDelimited_1_NB_LINE_OK"] == 1
    assert result.global_map["tFileInputDelimited_1_NB_LINE_REJECT"] == 2

    # 3. Output flow content
    assert (tmp_path / "out.csv").exists()
    assert (tmp_path / "reject.csv").exists()
    reject_content = (tmp_path / "reject.csv").read_text(encoding="iso-8859-15")
    assert "bad row" in reject_content
    assert "NOT_A_NUMBER" in reject_content


def test_invalid_filepath_raises_FileOperationError(run_job_fixture, tmp_path):
    """Per D-C4: assert specific ETLError subclass, never generic Exception."""
    from src.v1.engine.exceptions import FileOperationError

    # die_on_error=True in fixture; missing file should raise
    with pytest.raises(FileOperationError, match=r"\[tFileInputDelimited_1\]"):
        run_job_fixture(
            "file/csv_with_header",
            mutations={"tFileInputDelimited_1": {"filepath": "/does/not/exist.csv"}},
        )
```

## SWIFT Synthetic Generator (Plan 14-08)

### Why this is the hardest plan

`swift_transformer.py` and `swift_block_formatter.py` total **851 stmts** at **7%** coverage — a single plan accounts for ~50% of total Phase 14 missed-line lift. The modules are not registered with comprehensive engine tests; the only existing SWIFT test is at `tests/converters/talend_to_v1/components/transform/test_swift_transformer.py` and only covers the converter (19 stmts at 100%).

### MT message structure (foundation for the generator) [CITED: SWIFT MT user handbook]

A SWIFT MT message has **5 blocks**:

| Block | Purpose | Required | Example |
|-------|---------|----------|---------|
| 1 | Basic header (Application ID, Service ID, LT Address, Session, Sequence) | Yes | `{1:F01BANKBEBBAXXX0000000000}` |
| 2 | Application header (Input/Output, Message Type, Receiver/Sender LT, Priority) | Yes | `{2:I103BANKDEFFXXXXN}` |
| 3 | User header (UETR, validation flag, etc.) | No (often present) | `{3:{108:MT103REF1}}` |
| 4 | Text block (the actual message body — field tags) | Yes | `{4:\n:20:REF123\n:32A:240501USD1000,00\n-}` |
| 5 | Trailer block (CHK, MAC, PDE) | Yes | `{5:{CHK:ABC123DEF456}}` |

**Block 4 field tags** (the high-value content for the formatter):
- `:20:` — Sender's reference (mandatory for most MTs)
- `:23B:` — Bank operation code (MT103)
- `:32A:` — Value date / currency / amount (e.g., `:32A:240501USD1000,00` → date 2024-05-01, USD, 1000.00)
- `:50A:`, `:50K:` — Ordering customer
- `:59:`, `:59A:` — Beneficiary customer
- `:70:` — Remittance information
- `:71A:` — Details of charges
- `:25:` — Account ID (MT940)
- `:60F:` / `:62F:` — Opening / closing balance (MT940)
- `:61:` — Statement line (MT940)
- `:86:` — Information to account owner (MT940)

### Generator design

```python
# tests/fixtures/swift/synthetic.py (NEW — Plan 14-08)
"""Synthetic SWIFT MT message generators for SwiftBlockFormatter / SwiftTransformer tests.

Every branch in swift_transformer.py and swift_block_formatter.py must be
reachable by combining a representative MT type (MT103/MT202/MT940) with
optional features (block 3 user header, multi-line :86:, missing optional
fields, malformed blocks for reject-path tests).

Per D-A5: if a branch can't be hit with a synthetic message, flag dead code
and apply D-C5 (delete vs cover vs pragma).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MTBlock4Field:
    tag: str         # e.g. "20", "32A"
    value: str       # raw value


def build_block_1(
    app_id: str = "F",
    service_id: str = "01",
    lt_address: str = "BANKBEBBAXXX",
    session: str = "0000",
    sequence: str = "000000",
) -> str:
    """Block 1 -- basic header. Always present."""
    return f"{{1:{app_id}{service_id}{lt_address}{session}{sequence}}}"


def build_block_2(
    direction: str = "I",        # "I" input or "O" output
    message_type: str = "103",
    receiver: str = "BANKDEFFXXXX",
    priority: str = "N",
) -> str:
    """Block 2 -- application header."""
    return f"{{2:{direction}{message_type}{receiver}{priority}}}"


def build_block_3(uetr: Optional[str] = None, validation_flag: Optional[str] = None) -> str:
    """Block 3 -- user header (optional). Used for STP, COV, REMIT validation flags."""
    parts = []
    if uetr:
        parts.append(f"{{121:{uetr}}}")
    if validation_flag:
        parts.append(f"{{119:{validation_flag}}}")
    if not parts:
        return ""
    return "{3:" + "".join(parts) + "}"


def build_block_4(fields: List[MTBlock4Field]) -> str:
    """Block 4 -- text block. The formatter's primary input."""
    body = "\n".join(f":{f.tag}:{f.value}" for f in fields)
    return f"{{4:\n{body}\n-}}"


def build_block_5(chk: str = "ABC123DEF456") -> str:
    """Block 5 -- trailer. Always present."""
    return f"{{5:{{CHK:{chk}}}}}"


def build_mt_message(
    block_1: str,
    block_2: str,
    block_4_fields: List[MTBlock4Field],
    block_3: str = "",
    block_5: Optional[str] = None,
) -> str:
    """Assemble a complete MT message string."""
    blocks = [block_1, block_2]
    if block_3:
        blocks.append(block_3)
    blocks.append(build_block_4(block_4_fields))
    blocks.append(block_5 or build_block_5())
    return "".join(blocks)


# Convenience: canonical MT103, MT202, MT940 templates ---------------------

def mt103_minimum() -> str:
    """MT103 -- single customer credit transfer, minimum required fields."""
    return build_mt_message(
        build_block_1(),
        build_block_2(message_type="103"),
        [
            MTBlock4Field("20", "REF123"),
            MTBlock4Field("23B", "CRED"),
            MTBlock4Field("32A", "240501USD1000,00"),
            MTBlock4Field("50K", "/123456\nALICE COMPANY\nNEW YORK"),
            MTBlock4Field("59", "/987654\nBOB CORP\nLONDON"),
            MTBlock4Field("71A", "OUR"),
        ],
    )


def mt202_cov() -> str:
    """MT202 COV -- general financial institution transfer with validation flag."""
    return build_mt_message(
        build_block_1(),
        build_block_2(message_type="202"),
        [
            MTBlock4Field("20", "REF202"),
            MTBlock4Field("21", "RELATED202"),
            MTBlock4Field("32A", "240501EUR2500,00"),
            MTBlock4Field("52A", "BANKBEBBAXXX"),
            MTBlock4Field("58A", "BANKDEFFXXXX"),
        ],
        block_3=build_block_3(validation_flag="COV"),
    )


def mt940_with_balance() -> str:
    """MT940 -- customer statement message with opening/closing balance + statement lines."""
    return build_mt_message(
        build_block_1(),
        build_block_2(message_type="940"),
        [
            MTBlock4Field("20", "STMT001"),
            MTBlock4Field("25", "/123456789"),
            MTBlock4Field("28C", "00001/00001"),
            MTBlock4Field("60F", "C240501USD10000,00"),
            MTBlock4Field("61", "240501C500,00NTRFREF1//BANKREF"),
            MTBlock4Field("86", "INFO LINE 1\nINFO LINE 2"),
            MTBlock4Field("62F", "C240501USD10500,00"),
        ],
    )


def malformed_missing_block_4() -> str:
    """Reject-path fixture: missing block 4 should raise ConfigurationError or DataValidationError."""
    return build_block_1() + build_block_2() + build_block_5()
```

### YAML config / layout shapes the engine reads

Both modules read YAML config files. The shape of those configs (deduced from `swift_transformer.py:43-77` and `swift_block_formatter.py:33-79`):

```yaml
# layout file for swift_block_formatter (config.layout_file or config.layout)
blocks:
  - name: block1
    pattern: '\{1:(.*?)\}'
    fields:
      - {name: app_id, slice: [0, 1]}
      - {name: service_id, slice: [1, 3]}
      - {name: lt_address, slice: [3, 15]}
  - name: block4
    pattern: '\{4:\n(.*?)\n-\}'
    field_tag_pattern: ':(\w+):(.+?)(?=:\w+:|$)'

pipe_fields:
  - messagetype          # simple string form
  - {name: block1bic, source: lt_address, default: ""}  # dict form

processing:
  strip_whitespace: true
```

```yaml
# transform_config file for swift_transformer
input_fields:
  - {name: messagetype, type: string}
  - {name: block4_20, type: string}

output_fields:
  - {name: SIDE, type: string, default: ""}
  - {name: OURREF, type: string}

output_layout:
  - SIDE
  - TERMID
  - OURREF

field_mappings:
  SIDE:
    rule: condition
    when:
      messagetype: "103"
    then: "DEBIT"
    else: "CREDIT"
  OURREF:
    source: block4_20
    transform: trim

transformations:
  trim:
    type: regex_replace
    pattern: '^\s+|\s+$'
    replacement: ""

lookups:
  - name: bic_lookup
    file: tests/fixtures/swift/lookups/bic_country.csv
    key: bic
    value: country
```

### Coverage strategy for SWIFT plans

1. **Synthesize a YAML layout per behavior under test** (block 4 only, all 5 blocks, with vs without block 3, with vs without lookups).
2. **Generate MT messages via `synthetic.py`** that exercise field-tag-handling branches in the formatter (multi-line :86:, optional :70:, missing :32A: → reject path).
3. **Mock or synthesize CSV lookup files** at `tests/fixtures/swift/lookups/` for `transform_config.lookups`.
4. **Pipeline tests** load a JSON job config that wires `tFileInputRaw` → `SwiftBlockFormatter` → `SwiftTransformer` → `tFileOutputDelimited`, exercising the full pipeline end-to-end.

### Existing SWIFT converter test fixtures — leverageable?

`tests/converters/talend_to_v1/components/transform/test_swift_transformer.py` covers the **converter** (only 19 stmts). The converter and engine modules are different code paths; converter tests cannot be directly reused. However, the converter test demonstrates the YAML config keys the converter emits — those keys are the same ones the engine consumes. Plan 14-08 should cross-check that synthesized engine YAML configs match converter-emitted shapes.

## Java Bridge Gate Strategy (D-A3)

### Current `-m java` test surface

Existing `@pytest.mark.java` tests live in:
- `tests/v1/engine/test_bridge_integration.py`
- `tests/v1/engine/test_java_component.py`
- `tests/v1/engine/test_code_components_engine_smoke.py`
- `tests/v1/engine/test_map_method_size.py`
- `tests/v1/engine/components/transform/test_map_integration.py`
- `tests/integration/test_iterate_e2e.py::TestJobTFileListExecution`, `TestJobTFlowToIterateExecution`
- `tests/integration/test_full_pipeline.py::TestTMapJavaExpressionPipeline`

These exercise expression evaluation paths via `JavaBridgeManager` indirectly. They DO NOT exhaustively cover `java_bridge_manager.py` lifecycle code paths.

### Existing JAR sufficiency

[VERIFIED: `ls src/v1/java_bridge/java/target/*.jar` shows both `java-bridge-with-dependencies.jar` and `java-bridge.jar` present from the Phase 13 rebuild]. The JAR is current; no new build required for Phase 14.

### Java version note [VERIFIED: `java -version`]

Local environment has **OpenJDK 21.0.10** (Homebrew). Project requires Java 11+. The JAR was built for Java 11 and runs fine on 21. The gate command MUST be paste-runnable with `JAVA_HOME` resolving to a 11+ JVM; this is documented in CLAUDE.md.

### `java_bridge_manager.py` 59% gap analysis

The 41 missed lines (from 101 stmts) cluster around:

| Section (line ranges from src) | What needs testing |
|--------------------------------|---------------------|
| Port retry loop (lines 49–82) | "Address already in use" path: simulate by pre-binding a socket on an allocated port, then attempting bridge start. Plan 14-11 task. |
| Library validation (lines 90–99) | `self.libraries = ["nonexistent.jar"]` config → `RuntimeError("Missing required libraries...")`. Test asserts on exception type + message. |
| Routine loading (lines 101–113) | Mix of valid + invalid routine class names; assert `JavaBridgeError("Failed to load routines: [...]")`. |
| Stop / cleanup (lines 119–130) | Test `stop()` is idempotent (call twice); test stop() during exception. |
| `is_available()` and `get_bridge()` (lines 132–138) | Trivial — call before start, after start, after stop. |
| `__enter__` / `__exit__` context manager (lines 153–162) | Assert it starts and stops correctly. |
| `__repr__` (lines 163–166) | One assertion call. |

**Effort:** Medium (M). Real-bridge tests via the existing `java_bridge` fixture cover most paths. ~10 new tests.

## Coverage Tooling Configuration

### `pyproject.toml` — proposed `[tool.coverage]` section (Plan 14-01 or Plan 14-13)

```toml
[tool.coverage.run]
# In-scope source paths (matches Phase 13 baseline command --cov= flags)
source = [
    "src/v1/engine",
    "src/converters",
]
# Exclude legacy converter (CONTEXT.md Out of Scope: complex_converter)
omit = [
    "src/converters/complex_converter/*",
    "*/__init__.py",                        # Optional: tiny init files clutter the per-module table
    "*/tests/*",
    "*/test_*.py",
]
# Branch coverage stays OFF (CONTEXT.md Deferred: branch coverage)
branch = false
# Subprocess patching only if Plan 14-11 needs it; default off
# patch = ["subprocess"]

[tool.coverage.report]
# Per-module 95% gate is enforced by scripts/check_coverage_floor.py, NOT by --fail-under here.
# Allow lines that are explicitly excluded via the narrow D-C3 pragma allowlist.
exclude_also = [
    # D-C3 allowlist:
    "if __name__ == .__main__.:",
    "@(abc\\.)?abstractmethod",
    # Optional shims for optional dependencies (lxml, oracledb, openpyxl):
    # These are caught implicitly by `# pragma: no cover` annotations on the import block.
]
# Show missing line numbers in terminal report (already in baseline command)
show_missing = true
# 0 decimals -- match Phase 13 baseline display
precision = 0

[tool.coverage.html]
directory = "htmlcov"
```

### Gate command (D-D4 + D-A3)

The paste-runnable command goes in CLAUDE.md and `14-COVERAGE.md`:

```bash
# From project root. Requires JVM 11+ on PATH for -m java tests (D-A3).
# pytest-xdist via -n auto provides parallel speedup; pytest-cov combines worker data automatically.
python -m pytest tests/ \
  -m "not oracle" \
  -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json:coverage.json \
  -q

# Gate: per-module 95% floor
python scripts/check_coverage_floor.py --threshold 95 --report coverage.json
```

Notes:
- `-m "not oracle"` excludes the Phase 11 testcontainer suite (D-A6 boundary mocks cover Oracle in the gate).
- `-n auto` is the D-D4 parallelization. pytest-cov 7 + pytest-xdist 3.x combine cleanly with no extra flags [CITED: pytest-cov docs via Context7].
- `--cov-report=json:coverage.json` is the new addition vs Phase 13 — it produces machine-readable per-file data for the gate script.
- The `scripts/check_coverage_floor.py` step is what enforces the 95% per-module floor (pytest-cov has only a global `--cov-fail-under`).

### Per-Module Floor Enforcement Script (`scripts/check_coverage_floor.py`)

```python
#!/usr/bin/env python3
"""Per-module coverage floor enforcement (Phase 14, TEST-12).

Reads coverage.json (produced by `coverage json` or `pytest --cov-report=json:`)
and exits non-zero if any in-scope module is below the threshold.

In-scope = files matched by [tool.coverage.run] source minus omit, as already
filtered by coverage.py before json emission.

Usage::

    python scripts/check_coverage_floor.py --threshold 95 --report coverage.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=95.0)
    parser.add_argument("--report", type=Path, default=Path("coverage.json"))
    args = parser.parse_args()

    if not args.report.exists():
        print(f"ERROR: coverage report not found at {args.report}", file=sys.stderr)
        return 2

    with open(args.report, "r", encoding="utf-8") as f:
        data = json.load(f)

    files = data.get("files", {})
    if not files:
        print(f"ERROR: no per-file data in {args.report}", file=sys.stderr)
        return 2

    failures = []
    for path, summary in sorted(files.items()):
        pct = summary.get("summary", {}).get("percent_covered", 0.0)
        if pct < args.threshold:
            failures.append((path, pct, summary.get("summary", {}).get("missing_lines", 0)))

    if failures:
        print(f"FAIL: {len(failures)} module(s) below {args.threshold}% line coverage:", file=sys.stderr)
        for path, pct, missing in failures:
            print(f"  {pct:6.2f}%  {path}  (missing {missing} lines)", file=sys.stderr)
        return 1

    n_modules = len(files)
    print(f"PASS: all {n_modules} in-scope modules at >= {args.threshold}% line coverage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The script is ~40 lines, has zero dependencies beyond stdlib, and uses the well-documented `coverage.json` `files[].summary.percent_covered` field [CITED: coverage.py FAQ via Context7].

## pytest-xdist + pytest-cov combine

[CITED: pytest-cov via Context7] pytest-cov 7 + pytest-xdist 3.x **combine coverage data automatically** when running `pytest -n auto --cov=...`. No extra flags are needed in the standard case.

Caveats:
- Each xdist worker writes its own `.coverage.<hostname>.<pid>.<rand>` data file in the working directory; pytest-cov combines them at session end.
- These data files are ephemeral but visible in `git status` if a run is interrupted. Plan 14-01 should either add them to `.gitignore` (likely already gitignored under `.coverage*`) or document a `coverage erase` before-each-run step. **Verified `.coverage` already in working tree at root** — confirms gitignore covers it.
- Subprocess coverage (relevant if `python_routine_manager.py` forks subprocesses) requires `[tool.coverage.run] patch = ["subprocess"]`. Default-off; only enable if Plan 14-11 surfaces an actual subprocess-coverage gap.

## Pragma Policy & Enforcement (D-C3)

### Existing pragma usage (audit)

Single occurrence:
- `src/v1/engine/components/file/file_output_delimited.py:364`: `except Exception:  # pragma: no cover - defensive`

This is **disallowed** under D-C3 (defensive guards on internal-only code are not on the allowlist). Plan 14-09 (file output deep gaps) should either:
1. Write a test that triggers this branch (preferred per "rewrite over patch"), or
2. Apply D-C5 (delete the dead branch — it's a catch-all `Exception` after a typed exception block above, likely unreachable), or
3. Document why it must remain (would require user override of D-C3).

### Enforcement during plan execution

There is no automated linter for the pragma allowlist. Plan-checker / code reviewers enforce manually by grep:

```bash
# CI step or pre-merge check
grep -rn "pragma: no cover" src/ --include="*.py" \
  | grep -vE "(if __name__|abstractmethod|except ImportError)" \
  || echo "All pragma usages on D-C3 allowlist"
```

## Common Pitfalls

### Pitfall 1: pandas 3.0 CoW vs `inplace=True`

**What goes wrong:** Tests that use `df.fillna(0, inplace=True)` no longer mutate the original DataFrame under pandas 3.0 + CoW.
**Why it happens:** Copy-on-Write semantics treat `inplace=True` as a copy-modify-rebind, so the test's reference to the "original" df doesn't see the change.
**How to avoid:** Always use `df = df.fillna(0)` (rebind, never `inplace=True`) in test fixtures. Phase 13 D-B2 (unique_row pandas 3.0 StringDtype) is the canonical patch precedent.
**Warning signs:** Test passes locally on pandas 2.x but fails when pandas is bumped to 3.x; assertion that "the original df now has zero in column X" fails because the original wasn't mutated.

### Pitfall 2: StringDtype vs object dtype detection

**What goes wrong:** A test seeds a DataFrame from `pd.read_csv(...)` and the resulting string columns are `StringDtype`, not `object`. Engine code that does `if df[col].dtype == object:` returns False.
**Why it happens:** pandas 3.0 + CoW + Arrow strings makes `StringDtype` the default for string columns under many constructors.
**How to avoid:** Use the canonical detection pattern (Phase 13 D-B2): `pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)`. When seeding test data, prefer `pd.DataFrame({"col": pd.array([...], dtype="string")})` to make the dtype explicit.
**Warning signs:** Test setup uses `pd.DataFrame([{"name": "Alice"}])` and the engine's `str.lower()` branch isn't reached.

### Pitfall 3: pytest-cov + xdist `.coverage` data file collision

**What goes wrong:** A previous interrupted run leaves stale `.coverage.<hostname>.*` worker files in the working directory; pytest-cov combines them with the new run, producing inflated or stale coverage numbers.
**Why it happens:** xdist workers write per-worker data files; combine happens at session end; an interrupted session leaves orphans.
**How to avoid:** Run `coverage erase` before the gate command (or add `--cov-append=false` is the default — just delete `.coverage*` files). Alternatively, the gate script can `unlink` `.coverage*` before invoking pytest.
**Warning signs:** Coverage numbers drift between runs without code changes; `coverage.json` lists files no longer in the source tree.

### Pitfall 4: pyproject.toml `[tool.coverage.run] source` vs `--cov=` precedence

**What goes wrong:** A future contributor adds `--cov=` flags that conflict with `[tool.coverage.run] source` in pyproject; pytest-cov uses the CLI flags and the pyproject `source` is silently ignored.
**Why it happens:** CLI args override config file; coverage.py issues no warning.
**How to avoid:** Pin the gate command to use the same paths as `[tool.coverage.run] source`. Document in CLAUDE.md that `[tool.coverage]` config in pyproject is the source of truth for "what's in scope"; the gate command must match.
**Warning signs:** `coverage.json` files entries don't match `source` in pyproject; gate script reports failures for files not in scope.

### Pitfall 5: JVM env requirement for `-m java` tests

**What goes wrong:** A contributor without Java 11+ on `PATH` runs the gate command. `-m java` tests skip silently (existing `java_bridge` fixture calls `pytest.skip()`); `java_bridge_manager.py` falls below 95% in their local run, but the CI environment passes.
**Why it happens:** `tests/v1/engine/conftest.py:java_bridge` skips if JAR not present, but does not check JVM version.
**How to avoid:** CLAUDE.md gate command documentation must explicitly state "Requires JVM 11+ on PATH". The gate script could optionally probe for `java -version` and fail-fast with a clear message. Plan 14-11 task: add a one-line probe at the top of `java_bridge_manager.py` real-bridge tests that assert JVM is reachable.
**Warning signs:** `tests collected, X skipped` mentioning java tests; coverage on `java_bridge_manager.py` shifts based on whether JVM is present.

### Pitfall 6: SWIFT MT format edge cases

**What goes wrong:** Synthetic generator omits an optional MT field that a real Talend job would provide; an engine branch handling that field is never exercised; coverage falls just short of 95%.
**Why it happens:** SWIFT MT messages are highly variable per message-type; the engine code may have field-presence branches that the synthesizer doesn't think to populate.
**How to avoid:** When a SWIFT branch is uncovered, **read the engine code** for the missed line, identify what field-presence triggers it, and add a synthetic message variant that includes the field. Apply D-C5 (delete dead branches) only after confirming the branch can never be reached by any realistic MT input.
**Warning signs:** SWIFT modules at 90–94% after a "complete" first pass; `coverage report --show-missing` lists single-line gaps in field-tag-dispatch logic.

### Pitfall 7: Pipeline test JSON drift from converter output

**What goes wrong:** A pipeline-test JSON fixture is hand-edited and falls out of sync with what the converter emits today; the test passes but doesn't actually exercise the engine on production-shaped configs.
**Why it happens:** Manual edits accumulate; nobody re-runs the converter periodically.
**How to avoid:** Plan 14-01 ships an optional helper script that regenerates a JSON fixture from a `.item` file: `python scripts/regen_pipeline_fixture.py path/to/job.item`. Document in CLAUDE.md.
**Warning signs:** Pipeline tests pass but Phase 15 integration tests fail on the same logical config; converter changes don't break engine tests when they should.

### Pitfall 8: `make_pipeline_fixture` JSON fixture path resolution in worktrees

**What goes wrong:** Phase 14 work happens on a feature branch worktree; `tests/fixtures/jobs/` exists in the main repo only, and the worktree gate run finds zero fixtures.
**Why it happens:** `tests/fixtures/jobs/` is in-tree (not gitignored) so this is unlikely — but the existing `tests/v1/engine/conftest.py:_find_java_bridge_jar` worktree fix is a reminder that JAR-style worktree handling sometimes leaks into expected places.
**How to avoid:** Verify `tests/fixtures/jobs/` is checked into git in Plan 14-01's first commit. Do not rely on dynamic generation.
**Warning signs:** Fixture-not-found errors in CI but tests pass locally.

## Code Examples

(All inline examples above are pulled from existing codebase; representative excerpts captured under each Pattern section. No additional snippets needed.)

## State of the Art

| Old Approach (Phase 13 baseline) | Current Approach (Phase 14) | When Changed | Impact |
|----------------------------------|------------------------------|--------------|--------|
| `pytest --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html -q` (no parallelization, no Oracle exclusion) | Add `-n auto -m "not oracle" --cov-report=json:coverage.json` + run `scripts/check_coverage_floor.py` | Phase 14 (D-D4 + D-A3 + TEST-12) | Faster gate runs; Oracle live tests stay opt-in; per-module gate enforced. |
| `tests/integration/test_iterate_e2e.py` defines its own `_mutate_json_paths` and pipeline-execution helpers | Pull into `tests/conftest.py` as a reusable `run_job_fixture` | Phase 14 (D-C2, Plan 14-01) | All subsystem plans share the helper; reduces duplication; pattern documented. |
| Single `# pragma: no cover - defensive` exists in `file_output_delimited.py` | D-C3 narrow allowlist enforced; existing pragma either covered by a real test or deleted (D-C5) | Phase 14 (D-C3) | Coverage gate not gameable; dead code surfaced. |
| Phase 13 `13-COVERAGE-BASELINE.md` is the floor reference | Phase 14 `14-COVERAGE.md` is the final per-module table; baseline file stays archived | Phase 14 closeout (D-E3) | Single source of truth for "is the floor met". |

## Assumptions Log

> Claims tagged `[ASSUMED]` in this research; planner / discuss-phase should confirm before locking.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact count of below-95% modules is **53** per CONTEXT.md, but a strict grep of the baseline table FAIL rows yields **52** (excluding the legacy `complex_converter` and the `mssql_input.py` converter row appears in the baseline). The off-by-one is likely a `__init__.py` boundary or a count drift between baseline measurement and CONTEXT.md write. | §Module Triage | Low — Plan 14-13's gate script enumerates files dynamically from `coverage.json`, so the exact baseline count doesn't constrain execution. |
| A2 | The proposed `tests/conftest.py` (root) is added new in Plan 14-01. **No existing root conftest** found per `find tests -name conftest.py`. | §Pipeline-Test Infrastructure | Low — verified by filesystem scan. |
| A3 | The SWIFT YAML config shapes documented above are deduced from `_init_transformer_config` and `_init_swift_parser` source-reads (lines 43–77 and 33–79 respectively). The full set of YAML keys may be larger; SWIFT plan execution may surface additional keys during synthesis. | §SWIFT Synthetic Generator | Medium — SWIFT plan effort estimate is approximate; real branches in YAML-key dispatch may need additional fixture variants. Plan-checker should expect Plan 14-08 to iterate on YAML shape during execution. |
| A4 | `-n auto` parallelization with pytest-xdist 3.8.0 + pytest-cov 7.0.0 produces correct combined coverage with no additional flags. **Verified via Context7** (multiple pytest-cov doc snippets confirm), but not yet measured against the dataprep test suite specifically. Plan 14-01 should run a quick smoke (`pytest -n auto --cov=src/v1/engine -q tests/v1/engine/test_executor.py`) and compare per-line numbers against a serial run as a one-time validation. | §pytest-xdist + pytest-cov combine | Medium — if the smoke shows discrepancy, Plan 14-01 falls back to serial gate runs and adjusts D-D4 (subject to user override). |
| A5 | The `[tool.coverage.run] source = ["src/v1/engine", "src/converters"]` in pyproject.toml takes precedence over Phase 13's CLI `--cov=src/v1/engine --cov=src/converters`. **Verified via coverage.py docs** (CLI overrides config when both present; both must match). The gate command keeps both flags as a redundancy/clarity measure. | §Coverage Tooling | Low — both forms produce the same in-scope set; redundancy is intentional. |
| A6 | `java_bridge_manager.py` retry-loop testing (port collision branch, lines 49–82) can be triggered by pre-binding a socket to a known port. The retry path catches `"Address already in use"` strings; tests need to seed that exact substring into a raised exception, which may require monkey-patching `JavaBridge.start` rather than real OS-level binding. | §Java Bridge Gate Strategy | Medium — Plan 14-11 may discover the retry branch is reachable only via mocking `JavaBridge.start` to raise; that's still a real-bridge-style test (the bridge module under test is `java_bridge_manager.py`, not `bridge.py`). |
| A7 | Phase 14's existing pragma at `src/v1/engine/components/file/file_output_delimited.py:364` is a candidate for D-C5 deletion (it's a catch-all `Exception` after typed exception handling; likely unreachable). The decision belongs to Plan 14-09 reviewer; this research flags the candidate but doesn't pre-decide. | §Pragma Policy & Enforcement | Low — execution-time decision, not a planning constraint. |

**Confirmation needed:** A1 (53 vs 52 count — clarify in plan summary), A3 (SWIFT YAML shape may need extension — plan-checker should accept iteration), A4 (xdist+cov smoke — Plan 14-01 task), A6 (port-retry branch test approach — Plan 14-11 task).

## Open Questions

1. **Should the `coverage.json` produced by the gate be committed to git per-phase as a reference, or is `14-COVERAGE.md` (markdown table) sufficient?**
   - What we know: Phase 13 chose markdown-only (`13-COVERAGE-BASELINE.md`) — `htmlcov/` is gitignored; `coverage.json` would be analogous.
   - What's unclear: Whether Phase 14 wants a machine-readable artifact for the operational CI phase.
   - Recommendation: **Markdown-only**, mirroring Phase 13. Operational CI phase can re-emit `coverage.json` from a fresh run.

2. **Does `python_dataframe_component.py` (20%, 37 missed) need synthetic DataFrame fixtures or do existing patterns scale up?**
   - What we know: 46-stmt module is a thin wrapper around `exec(python_code, namespace)`; existing test patterns in `test_python_component.py` use hand-rolled namespaces.
   - What's unclear: Whether the 37 missed lines cluster in user-code error branches that need realistic DataFrame inputs.
   - Recommendation: **Existing patterns scale up** — hand-rolled `pd.DataFrame` fixtures with mixed dtypes are sufficient. Plan 14-07 confirms during execution.

3. **Should Plan 14-04 (iterate / context — both at >=95% per baseline) be merged into 14-09 (file quick wins)?**
   - What we know: CONTEXT.md D-D1 already flags this as a "may be merged" plan.
   - What's unclear: Whether iterate/context modules need a no-regress sanity test or just ride the closeout gate.
   - Recommendation: **Merge into 14-13 closeout** as a no-regress assertion. Saves a plan slot.

4. **Is the existing `mssql_input.py` converter (81%) really in scope for Phase 14, or is it deferred with the broader v2 MSSQL work?**
   - What we know: Baseline lists it as FAIL; CONTEXT.md `## v2 Requirements` defers `MSSQL database components`.
   - What's unclear: Whether the **converter** (already partially in tree) is in scope while the **engine** is v2.
   - Recommendation: **Lift converter to 95% in Plan 14-12** since it's already in tree and the gate doesn't distinguish; engine MSSQL stays v2.

5. **Do we run `coverage erase` automatically before the gate, or rely on contributors to do it manually?**
   - What we know: Stale `.coverage.<hostname>.*` files cause Pitfall 3.
   - What's unclear: Is the gate command line-edit (add `coverage erase &&` prefix) preferred, or a script that wraps both?
   - Recommendation: **Add `rm -f .coverage .coverage.*` to the documented gate command** as a one-liner prefix. Cheaper than a wrapper script.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Engine + tests | ✓ [VERIFIED] | 3.12 (via pip-installed pytest 9.0.2) | — |
| pandas | Test fixtures + engine | ✓ [VERIFIED] | 3.0.1 (CoW) | — |
| pytest | Test runner | ✓ [VERIFIED] | 9.0.2 | — |
| pytest-cov | Coverage measurement | ✓ [VERIFIED] | 7.0.0 | — |
| pytest-xdist | Parallel execution (D-D4) | ✓ [VERIFIED, but NOT in pyproject dev extra] | 3.8.0 | Serial gate (no `-n auto`); coverage still works |
| Java JVM 11+ | `-m java` tests for `java_bridge_manager.py` (D-A3) | ✓ [VERIFIED] | OpenJDK 21.0.10 (Homebrew) | `-m "not java and not oracle"` reduces gate to non-JVM modules; `java_bridge_manager.py` would not reach 95% — gate fails per D-D3 |
| Java bridge JAR | `-m java` tests | ✓ [VERIFIED] | Phase 13 rebuild present at `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar` | Build with `cd src/v1/java_bridge/java && mvn package -q`; existing fixture skips with this hint |
| openpyxl | Excel input/output tests (Plan 14-10) | ✓ [VERIFIED] | 3.1.5 | — |
| oracledb | Oracle boundary mock tests (Plan 14-05) | ✓ [VERIFIED] | 3.4.2 | — |
| Maven 3.x | JAR rebuild (NOT NEEDED in Phase 14) | not probed | — | Phase 13 rebuild is current; Phase 14 doesn't need rebuild |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — all required tools verified present.

**Documentation requirement:** CLAUDE.md gate command must state "Requires Java 11+ on PATH" and "Requires `pip install -e .[dev]` (which now includes pytest-xdist)".

## Validation Architecture

> Required: workflow.nyquist_validation is enabled in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-cov 7.0.0 + pytest-xdist 3.8.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, plus new `[tool.coverage]` sections from Plan 14-01) |
| Quick run command | `pytest <subsystem-test-dir> -m "not oracle" -q` (per-plan during execution) |
| Full suite command | `pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html --cov-report=json:coverage.json -q && python scripts/check_coverage_floor.py --threshold 95 --report coverage.json` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| TEST-11 | Every in-scope module reaches >=95% line coverage | full-suite + gate script | `pytest tests/ ... && python scripts/check_coverage_floor.py --threshold 95` | ❌ Plan 14-01 (gate script); ❌ Plan 14-02..14-12 (per-subsystem test extensions); ❌ Plan 14-13 (closeout) |
| TEST-11 | New tests are real-behavior (no D-C3 violations) | grep audit | `grep -rn "pragma: no cover" src/ \| grep -vE "(if __name__\|abstractmethod\|except ImportError)"` returns empty | ❌ Plan 14-13 (closeout audit) |
| TEST-11 | Pipeline-test infrastructure under `tests/fixtures/jobs/` exists | smoke unit test | `pytest tests/conftest.py::test_run_job_fixture_loads_minimal_pipeline -q` | ❌ Plan 14-01 (the fixture itself + a smoke test for it) |
| TEST-11 | No PASS module regresses below 95% | full-suite + gate script | `python scripts/check_coverage_floor.py --threshold 95 --report coverage.json` flags any regression | ❌ Plan 14-13 (closeout) |
| TEST-12 | Paste-runnable gate command in CLAUDE.md | manual verification | Copy-paste command from CLAUDE.md to fresh shell; expect exit 0 | ❌ Plan 14-13 (CLAUDE.md update) |
| TEST-12 | `[tool.coverage]` config in pyproject.toml | static check | `python -c "import tomllib; print(tomllib.loads(open('pyproject.toml','rb').read().decode())['tool']['coverage']['run']['source'])"` | ❌ Plan 14-01 (initial config) |
| TEST-12 | `14-COVERAGE.md` exists with per-module final numbers | static check | `test -f .planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md` | ❌ Plan 14-13 (closeout) |
| TEST-12 | `13-COVERAGE-BASELINE.md` archived in Phase 13 dir (not deleted) | static check | `test -f .planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md` | ✅ Already in tree |

### Sampling Rate

- **Per task commit:** the relevant subsystem test directory only — e.g., `pytest tests/v1/engine/components/file/ -m "not oracle" -q` (~30s) for Plan 14-09 / 14-10 work.
- **Per wave merge:** subsystem-scoped coverage check — e.g., `pytest tests/v1/engine/components/file/ --cov=src/v1/engine/components/file --cov-report=term-missing -q` and confirm subsystem average >=95%.
- **Phase gate:** Full-suite command above. Run before `/gsd-verify-work` and at closeout.

### Wave 0 Gaps

- [ ] `tests/conftest.py` — root conftest with `run_job_fixture` and `assert_ascii_logs` fixtures (Plan 14-01)
- [ ] `tests/fixtures/jobs/` — directory + initial JSON fixtures generated from existing `.item` samples (Plan 14-01)
- [ ] `tests/fixtures/swift/synthetic.py` — MT103/MT202/MT940 generator (Plan 14-08)
- [ ] `tests/fixtures/swift/layouts/*.yml` — YAML layouts for `swift_block_formatter` (Plan 14-08)
- [ ] `tests/fixtures/swift/lookups/*.csv` — lookup CSVs for `swift_transformer` (Plan 14-08)
- [ ] `scripts/check_coverage_floor.py` — per-module floor enforcement script (Plan 14-01 or Plan 14-13)
- [ ] `pyproject.toml` `[project.optional-dependencies] dev` — add `pytest-xdist>=3.5,<4`, `pytest-cov>=7.0,<8` (Plan 14-01)
- [ ] `pyproject.toml` `[tool.coverage.run]` and `[tool.coverage.report]` — coverage tool config (Plan 14-01)
- [ ] `tests/fixtures/data/sample.xlsx`, `tests/fixtures/data/sample.xls`, `tests/fixtures/data/sample.json` — real Excel + JSON fixture files (Plan 14-10)

## Sources

### Primary (HIGH confidence)
- [VERIFIED via filesystem scan / pip show / java -version / repo grep] — pytest 9.0.2, pytest-cov 7.0.0, pytest-xdist 3.8.0, pandas 3.0.1, oracledb 3.4.2, openpyxl 3.1.5, OpenJDK 21.0.10, Phase 13 JAR present, single existing `# pragma: no cover` instance, no root `tests/conftest.py`, four subsystem-level conftests
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` — locked decisions D-A1..D-A6, D-C1..D-C5, D-D1..D-D4, D-E1..D-E4
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md` — per-module floor table; reproducible measurement command; lift target counts
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-CONTEXT.md` — STALE deletion pattern (D-D1), pyproject conventions, documented `pytest --cov=...` command pattern
- `.planning/REQUIREMENTS.md` — TEST-09/TEST-10 already complete; TEST-11/TEST-12 to be added
- `.planning/ROADMAP.md` §"Phase 14" — 4 success criteria (SC#2 amended in CONTEXT.md D-E1)
- `.planning/STATE.md` — current project state (Phase 13 complete, Phase 14 next)
- [Context7: /pytest-dev/pytest-cov] — pytest-cov 7 + xdist combine pattern; `--cov-append`, parallel data files; pyproject configuration
- [Context7: /coveragepy/coveragepy] — coverage.py 7.x pyproject TOML configuration; `[tool.coverage.run]`, `[tool.coverage.report]`, `coverage json` output format with `percent_covered` per file

### Secondary (MEDIUM confidence)
- `tests/integration/test_iterate_e2e.py` — pipeline-test pattern (`_mutate_json_paths`, `_setup_filelist_input_dir`, ASCII-log assertion) — pulled into Pattern 1 as the basis for `run_job_fixture`
- `tests/v1/engine/components/control/test_send_mail.py` — boundary mock for `smtplib.SMTP` (line 111); `_make_component` pattern that mirrors `execute()` Step 1
- `tests/v1/engine/components/database/test_oracle_output.py` — boundary mock for `oracledb` Connection/Cursor (`_make_mock_oracle_manager`)
- `tests/v1/engine/conftest.py` — session-scoped `java_bridge` fixture; worktree-aware JAR resolution
- SWIFT MT message format (block 1/2/3/4/5 structure; field tags) — derived from common SWIFT MT user-handbook references and engine source reads at `src/v1/engine/components/transform/swift_transformer.py:43-77` and `swift_block_formatter.py:33-79`. Specific field-tag inventory (e.g., :20:, :32A:, :60F:, :86:) is widely documented in SWIFT publications.

### Tertiary (LOW confidence)
- A1 (53 vs 52 module count discrepancy) — needs reconciliation at planner gate, but does not block execution
- A3 (full SWIFT YAML key inventory) — research deduced from source reads; full key set may emerge during Plan 14-08 execution
- A4 (xdist+cov combine on dataprep specifically) — verified by Context7 docs but not yet measured on this repo's test suite

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed; versions current; no library substitutions proposed
- Architecture: HIGH — extends existing patterns (test_iterate_e2e.py, test_send_mail.py, test_oracle_output.py) with one new shared fixture and one new gate script
- Pitfalls: MEDIUM — pandas 3.0 + StringDtype gotchas are well-known via Phase 13 D-B2 precedent; xdist+cov combine is documented but not yet smoke-tested on this repo
- SWIFT plan effort: MEDIUM — synthetic generator design is sound but YAML key inventory may extend during execution
- Per-module floor enforcement: HIGH — coverage.py JSON output format is stable and well-documented [CITED: Context7]

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (30 days — stable test ecosystem; pandas 3.0 / pytest 9 / pytest-cov 7 are current)

## RESEARCH COMPLETE

**Phase:** 14 - Coverage Push to 95% per-module floor
**Confidence:** HIGH

### Key Findings
- All locked decisions in 14-CONTEXT.md execute on top of existing infrastructure — no new libraries required (pytest-xdist 3.8.0 is installed but missing from `pyproject` dev extra; Plan 14-01 must declare it).
- Pipeline-test infrastructure (Plan 14-01) generalizes the existing `tests/integration/test_iterate_e2e.py` pattern into a shared `run_job_fixture` in a NEW root `tests/conftest.py`. No root conftest exists today.
- SWIFT (Plan 14-08, 851 stmts at 7%) is the single dominant lift; synthetic MT103/MT202/MT940 generators with YAML layout fixtures are the enabling work. Existing converter SWIFT tests (19 stmts) cannot be reused for engine coverage.
- Per-module 95% floor enforcement requires a small (~40 LOC) Python script that parses `coverage.json` (pytest-cov has only a global `--cov-fail-under`).
- Boundary-mock patterns for `smtplib` (D-A4) and `oracledb` (D-A6) already exist verbatim in `test_send_mail.py:111` and `test_oracle_output.py:64-77` — extend, don't reinvent.
- Java bridge JAR is current (Phase 13 rebuild); local env has OpenJDK 21 (project requires 11+). Single existing `# pragma: no cover` (`file_output_delimited.py:364`) is a D-C3 violation candidate for Plan 14-09.

### File Created
`.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All libraries pip-verified; no version drift risk |
| Architecture | HIGH | Pure extension of existing test patterns |
| Pitfalls | MEDIUM | pandas 3.0 + StringDtype well-known; xdist+cov combine not repo-smoked |
| SWIFT plan sizing | MEDIUM | YAML key inventory may iterate during execution |
| Coverage tooling | HIGH | coverage.json schema + pyproject TOML well-documented |

### Open Questions
1. Module count: 52 vs 53 — minor reconciliation at planner gate (does not block execution)
2. Whether to merge Plan 14-04 (iterate/context already at >=95%) into 14-13 closeout — recommendation: yes
3. Whether `mssql_input.py` converter (81%) is in scope for Phase 14 — recommendation: yes (converter only; engine MSSQL stays v2)
4. Whether to commit `coverage.json` per phase — recommendation: no, markdown-only per Phase 13 precedent
5. Whether to add `rm -f .coverage*` prefix to gate command — recommendation: yes, prevents stale-data bugs

### Ready for Planning
Research complete. Planner can now create Plans 14-01 through 14-13 with the slicing locked in CONTEXT.md D-D1, the infrastructure design in §Pipeline-Test Infrastructure, the SWIFT enabling work in §SWIFT Synthetic Generator, the boundary-mock patterns in §Architecture Patterns 3 & 4, the gate command in §Coverage Tooling, and the per-module floor enforcement script in §Per-Module Floor Enforcement Script.
