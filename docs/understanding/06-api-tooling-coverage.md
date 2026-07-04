# API, Tooling & Coverage Infrastructure

This document covers the three "edge" subsystems of DataPrep that sit outside the
converter and engine cores:

1. The **FastAPI HTTP layer** (`api/`) that wraps `ETLEngine` for upload/run/poll
   and CRUD of Java/Python routine source files.
2. The **Python routines** mechanism (`src/python_routines/` plus the engine's
   `PythonRoutineManager`) that mirrors Talend's Java-routine model.
3. The **build/tooling/config** surface (`pyproject.toml`, helper scripts) and,
   most importantly for anyone extending this codebase, the **95% per-module
   coverage gate** that governs how new code must be tested.

If you are here to raise coverage to the per-module floor, jump straight to
[Coverage Infrastructure](#coverage-infrastructure) and
[The Coverage Gate Command](#the-coverage-gate-command).

> ASCII-only is a hard project rule (logging, scripts, and docs). Both helper
> scripts in this subsystem state it explicitly.

---

## 1. The API Layer (`api/`)

### Purpose and shape

A thin FastAPI surface that lets a client upload a JSON job config, run it,
poll for status, and manage routine source files. It is the only HTTP entry
point into the engine. There is **no execution logic** here beyond marshalling:
all real work is delegated to `ETLEngine`.

The app is assembled in `api/app.py:12` as a module-level `FastAPI` instance
(the composition root). It mounts three routers plus a health route:

| Mount prefix            | Router file                      | Responsibility                                   |
| ----------------------- | -------------------------------- | ------------------------------------------------ |
| `/api/jobs`             | `api/routes/jobs.py`             | Upload, run, run-inline, poll, list, get, delete |
| `/api/routines/java`    | `api/routes/routines.py`         | Java routine file CRUD + Maven build over SSE    |
| `/api/routines/python`  | `api/routes/python_routines.py`  | Python routine file CRUD                          |
| `/api/health`           | `api/app.py`                     | Liveness probe (`{"status": "ok"}`)              |

`api/__init__.py` and `api/routes/__init__.py` are empty package markers. There
is **no `__main__` / uvicorn entrypoint** in `api/` and no `[project.scripts]`
entry, so the process is presumably launched with `uvicorn api.app:app` (this is
undocumented in the files reviewed — see [Open Questions](#open-questions)).

### Endpoint catalog

| Method & path                         | Body / input              | Returns                          |
| ------------------------------------- | ------------------------- | -------------------------------- |
| `GET /api/health`                     | -                         | `{"status": "ok"}`               |
| `POST /api/jobs/upload`               | multipart `.json` file    | `job_id` + job metadata          |
| `POST /api/jobs/{job_id}/run`         | `RunRequest`              | `run_id` (status `queued`)       |
| `POST /api/jobs/run-inline`           | `RunInlineRequest`        | `run_id` (no persistence)        |
| `GET /api/jobs/runs/{run_id}`         | -                         | run status/stats/error           |
| `GET /api/jobs/runs`                  | -                         | all runs, most-recent first      |
| `GET /api/jobs/`                      | -                         | all uploaded jobs                |
| `GET /api/jobs/{job_id}`              | -                         | full job config JSON             |
| `DELETE /api/jobs/{job_id}`           | -                         | `{"deleted": job_id}`            |
| `GET\|POST /api/routines/java`        | `RoutineCreateRequest`    | list / created metadata          |
| `GET\|PUT\|DELETE /api/routines/java/{filename}` | `RoutineUpdateRequest` | file content / status      |
| `POST /api/routines/java/build`       | -                         | SSE stream of `mvn package`      |
| `GET\|POST /api/routines/python`      | `RoutineCreateRequest`    | list / created metadata          |
| `GET\|PUT\|DELETE /api/routines/python/{filename}` | `RoutineUpdateRequest` | file content / status   |

Request bodies are Pydantic models (`api/routes/jobs.py:31-37`):
`RunRequest.context_overrides` (optional `Dict[str,str]`) and
`RunInlineRequest.job_config` (an **unvalidated** `Dict[str, Any]` executed
directly by the engine).

### Job run lifecycle (data flow)

1. **Upload** (`jobs.py:42`): a multipart `.json` is read into memory
   (`await file.read()`), `json.loads`'d, and written to
   `data/jobs/{uuid}.json`. Returns the generated `job_id`.
2. **Run** (`jobs.py:94`): loads the persisted JSON, mints a `run_id`,
   registers a `queued` entry in the in-memory `_runs` dict, and spawns a
   **daemon thread** running `_execute_in_background`.
3. **Background execution** (`jobs.py:68`): opens
   `with ETLEngine(job_config) as engine:` (context-manager form so
   `engine._cleanup()` runs even on failure), applies `context_overrides` via
   `engine.set_context_variable`, calls `engine.execute()`, then writes
   serialized stats/status back into `_runs` under `_runs_lock`.
4. **Poll** (`jobs.py:158`): `GET /runs/{run_id}` returns the tracked dict.
5. **run-inline** (`jobs.py:127`) skips persistence entirely and executes the
   posted `job_config` dict directly.

The run tracker `_runs` (`jobs.py:25`) is a **process-global in-memory dict**
guarded by a single `threading.Lock`. `_make_serializable` (`jobs.py:217`)
recursively converts sets to lists and `NaN` floats to `None` so the status
response is JSON-safe.

### Security posture (read this before deploying)

The API is built as a **trusted single-user developer tool**. Several findings
make it unsafe to expose on an untrusted network:

| Severity | File                          | Issue                                                                                                                                                                      |
| -------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| HIGH     | `api/app.py`                  | **No auth/authz on any endpoint**; CORS is `allow_origins=["*"]` with `allow_credentials=True`. `POST /run-inline` executes an arbitrary job config with no check.        |
| HIGH     | `api/routes/jobs.py:97,199,208` | **Path traversal on `job_id`/`run_id`**: `JOBS_DIR / f"{job_id}.json"` is built from the raw URL with no UUID validation, so `..`-style ids reach arbitrary `*.json`.   |
| HIGH     | `api/routes/python_routines.py` | **RCE-by-design**: POST/PUT write arbitrary `.py` into `src/python_routines/`, which `PythonRoutineManager` imports and `python_component` `exec()`s.                  |
| MEDIUM   | `api/routes/jobs.py`          | `_runs` grows unbounded (memory leak), is process-local (lost on restart, wrong worker under multi-worker uvicorn), and has no TTL/eviction.                              |
| MEDIUM   | `api/routes/jobs.py:48,117`   | No upload size limit (`await file.read()` loads the whole file), and no concurrency cap / queue / timeout / cancellation on the per-run daemon threads (DoS surface).     |

Because the engine loads arbitrary Java JARs and Python routine directories from
job config, combining the path-traversal and no-auth gaps makes `run_job` on an
attacker-reachable file **effectively remote code execution**.

The Java/Python routine routers do get **one thing right**: a strict filename
allowlist `^[A-Za-z][A-Za-z0-9_]*\.(java|py)$` (`routines.py:23`,
`python_routines.py`) rejects dots, slashes, and `..`, blocking path traversal
on the `{filename}` param consistently across list/get/create/update/delete.

### Notable patterns

- **APIRouter-per-resource** mounted with prefixes in `app.py`.
- **Async-upload + sync-run** with fire-and-forget daemon threads.
- **Context-manager `ETLEngine`** to guarantee `_cleanup()` of Java/DB resources
  even when `execute()` raises (a genuine `good` finding).
- **SSE streaming** for the long-running Maven build (`routines.py:132`), which
  shells out to `mvn package -q --no-transfer-progress` in `_BRIDGE_DIR` and
  yields stdout line-by-line as `text/event-stream`.

### Packaging gotcha

`fastapi`, `uvicorn[standard]`, and `python-multipart` are declared only under
`[project.optional-dependencies].api` (`pyproject.toml:22`). A plain install of
the package will `ImportError` when `api/app.py` imports FastAPI. Install with
the extra: `pip install dataprep[api]` (or `dataprep[all]`).

### Testing status

**The entire `api/` HTTP surface is untested** — no `TestClient` usage anywhere
in `tests/`. The threaded run tracker, path-traversal gaps, and auth posture are
all uncovered. Recommended first additions:

- FastAPI `TestClient` tests for upload -> run -> poll happy path.
- A path-traversal regression test for `job_id`/`run_id` (`..%2F...`).
- A test asserting routine-filename validation rejects traversal payloads.

---

## 2. Python Routines

There are **two distinct things** that share the phrase "python routines";
keep them separate:

### 2a. Engine-integrated routines (`PythonRoutineManager`)

`src/v1/engine/python_routine_manager.py` is the real engine integration point.
When a job config has `python_config.enabled`, the engine constructs a
`PythonRoutineManager(routines_dir, required_routines)` which:

- Scans `routines_dir` for `.py` files (top-level **and one subdir level**),
- `importlib`-loads each module,
- maps the snake_case filename to a CamelCase name
  (`demo_routine` -> `DemoRoutine`),
- exposes them via a `RoutineNamespace` (`__getattr__`-based) so converted
  Talend expressions can call `routines.DemoRoutine.method()`.

`python_component.py` then spreads the loaded routines into the `exec()` globals
**both flat and under a nested `"routines"` key**, deliberately for backward
compatibility with converted jobs that reference routines by bare name. This
mirrors Talend's Java-routine mechanism (the parity intent is explicit).

**Known smell (`python_routine_manager.py:164`)**: `_load_module` registers each
module in the **global `sys.modules`** under its bare filename stem. Two routine
files with the same stem in different subdirs — or a stem colliding with an
installed package — will clobber each other / shadow real imports
process-wide. A namespaced key (e.g. `dataprep_routine.<qualified>`) would make
discovery collision-safe.

### 2b. The standalone SWIFT CLI (NOT a routine, NOT the engine component)

`src/python_routines/swift_transformer.py` is a **standalone argparse CLI** that
converts SWIFT MT messages to pipe-delimited output. It is *not* imported by the
engine. Critically, it shares the class name `SwiftTransformer` with the engine
component at `src/v1/engine/components/transform/swift_transformer.py` — a
**different file**.

The hazard: it lives inside the directory `PythonRoutineManager` scans by
default, so if `python_config.routines_dir` ever points at `src/python_routines`,
the manager would load it as routine `SwiftTransformer`, colliding conceptually
with the engine component name. Its module-level `argparse`/`main` are gated
behind `__main__`, so import itself is safe, but the naming collision is a latent
trap. It also uses `print()` for warnings rather than `logging` (benign for a
CLI, but would bypass ASCII-only log capture if loaded as a routine).

---

## 3. Build, Tooling & Config (`pyproject.toml`)

`pyproject.toml` (setuptools backend, `requires-python >= 3.12`) is the source of
truth for packaging metadata, optional-dependency extras, pyright/pytest config,
and the coverage scope.

### Optional-dependency extras

The base install is intentionally minimal (`pandas`, `numpy` only). Everything
else is an opt-in extra so the package stays light:

| Extra     | Pulls in                                              | Used by                                |
| --------- | ----------------------------------------------------- | -------------------------------------- |
| `java`    | `pyarrow`, `py4j`                                     | Java/Groovy bridge                     |
| `excel`   | `openpyxl`, `xlrd`                                    | Excel input/output components          |
| `oracle`  | `oracledb`                                            | Oracle DB components (thin mode)       |
| `xml`     | `lxml`                                                | XML input/output/extract components    |
| `yaml`    | `PyYAML`                                              | SWIFT transformer config               |
| `json`    | `jsonpath-ng`                                         | JSON input / extract-JSON components   |
| `api`     | `fastapi`, `uvicorn[standard]`, `python-multipart`    | the API layer                          |
| `dev`     | `pytest`, `pytest-cov`, `pytest-xdist`, `testcontainers` | the test + coverage stack           |
| `all`     | `dataprep[java,excel,xml,yaml,json,api,oracle]`       | everything except `dev`                |

Because DB drivers are lazy-imported inside methods, jobs that don't touch
Oracle/MSSQL run without those extras installed.

### pytest configuration and markers

`[tool.pytest.ini_options]` (`pyproject.toml:50`) sets `testpaths = ["tests"]`
and `addopts = "-v --tb=short"`, and declares these markers:

| Marker        | Meaning                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `unit`        | Fast, no I/O.                                                            |
| `integration` | May require file I/O.                                                    |
| `java`        | Requires the Java bridge (live JVM).                                     |
| `oracle`      | Requires an Oracle DB testcontainer; **slow, opt-in**.                  |
| `slow`        | Takes > 5 seconds.                                                       |
| `coverage`    | Documents a coverage requirement; **always skipped, enforced by CI**.   |

The `oracle` and `java` markers are load-bearing for the coverage gate (below):
`-m java` tests **are** measured (so `java_bridge_manager.py` and tMap live-bridge
paths count), while `-m oracle` is **excluded** from the gate (the testcontainer
suite is the verification path instead).

### Helper scripts

Two stdlib-only, ASCII-only scripts live in `scripts/`:

- `scripts/check_per_module_coverage.py` — the coverage gate (detailed below).
- `scripts/add_connectors.py` — generates UI connector port metadata into
  `src/router/ui_registry.json`.

`add_connectors.py` builds a `CONNECTOR_MAP` (Talend component name -> port spec)
from reusable builders (`source()`/`sink()`/`passthrough()`/`with_reject()`/
`utility()`) plus inline specs for special cases (tMap, tUnique, tFileList), then
**rewrites `ui_registry.json` in place** (input file == output file), inserting a
`connectors` block right after `category` and preserving key order via
`OrderedDict`. Components absent from `CONNECTOR_MAP` are passed through untouched
and printed as a `WARNING` list.

The connector specs encode Talend **port semantics** (UI-rendering parity, not
execution parity): tMap/tXmlMap take main + optional multi-lookup with main+reject
outputs; tJoin requires exactly one lookup (`maxConnections=1`); tUniqueRow emits
Unique+Duplicate; tFileList/tForeach/tLoop/tFlowToIterate emit an `iterate`
output (not `row`); tPrejob/tPostjob expose only an outgoing OnComponentOk
trigger.

**Tooling drift to be aware of:**

- `add_connectors.py` is **out of sync with its own output**. `ui_registry.json`
  contains a bespoke `tPagination` dual-output connector spec (a `Summary` main +
  a `detail` output) that no builder produces, but `tPagination` is **not** in
  `CONNECTOR_MAP`. Re-running the script prints
  `WARNING: No connector definition for: ['tPagination']` and leaves it untouched
  — i.e. the registry was hand-edited after the script ran.
- A **second, divergent registry** `src/router/ui_registry_v2.json` (86
  components) coexists with `ui_registry.json` (85 components), using different
  component keys (`PyMap` vs `tPythonDataframe`, `tFilterRow` vs `tFilterRows`,
  `tXMLMap` vs `tXmlMap`) and lacking `tPagination`. Its relationship to the live
  registry is undocumented; it may be a stale leftover.
- The script uses relative paths and has no repo-root resolution, so it only
  works when invoked from the repo root.

---

## Coverage Infrastructure

This is the part to internalize before adding any code. DataPrep enforces a
**95% per-module LINE-coverage floor**, not a global average. The mechanism is
deliberately external to `coverage` itself.

### Why per-module, not global

A global `fail_under` would let a 100%-covered module mask a 60%-covered one. The
project therefore **omits `fail_under` entirely** (`pyproject.toml:86` says so
explicitly) and enforces the floor with a separate gate script that checks
*every* in-scope module independently. The script's own docstring justifies this.

### Coverage scope: what is in and out

`[tool.coverage.run]` (`pyproject.toml:71`) defines the measured universe:

```
[tool.coverage.run]
source  = ["src/v1/engine", "src/converters"]
omit    = ["src/converters/complex_converter/*", "*/__init__.py",
           "*/tests/*", "*/test_*.py"]
branch  = false
parallel = true
```

- **In scope**: everything under `src/v1/engine` and `src/converters`.
- **Out of scope**: `__init__.py` files, anything under `tests/`, `test_*.py`,
  and the legacy `complex_converter/` tree.
- **Branch coverage is intentionally OFF** — only line coverage is floored.
- `parallel = true` matches `pytest-xdist`'s sharded `.coverage.*` files.

> **Dead omit pattern**: `src/converters/complex_converter/*` no longer exists
> (`src/converters` has only `talend_to_v1`). Harmless but misleading; CLAUDE.md
> still cites it.

> **Scope note for the API/python-routines subsystem of this very doc**: `api/`
> and `src/python_routines/` are **outside** the coverage source roots. They are
> not gated and their untested state does not affect the gate result.

### The pragma allowlist

`[tool.coverage.report].exclude_also` (`pyproject.toml:90`) is a **narrow**
allowlist of lines excluded from the denominator, to prevent coverage-dodging via
broad `# pragma: no cover`:

```
exclude_also = [
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "@(abc\\.)?abstractmethod",
]
```

Only `__main__` blocks, `raise NotImplementedError`, and abstract-method
declarations may be excluded. Anything else must be tested. `show_missing` is on,
`precision = 1`, JSON output goes to `coverage.json`
(`[tool.coverage.json]`, pretty-print off), HTML to `htmlcov/`.

### The gate script (`scripts/check_per_module_coverage.py`)

A 147-line, stdlib-only, ASCII-only CLI. Flow:

1. `_load_coverage_json` reads `coverage.json` and **fails loud** (`SystemExit(2)`)
   on a missing file, invalid JSON, or a missing top-level `files` dict.
2. `_collect_failures` iterates `coverage.json["files"]`, reads
   `summary.percent_covered` per file, and collects every module below the floor
   (sorted ascending). If **any** record lacks `summary.percent_covered`, it
   raises `SystemExit(2)` rather than silently passing.
3. `main` prints either:
   - `PASS: all <N> in-scope modules at >= 95.0% line coverage` (exit 0), or
   - `FAIL: <K> module(s) below 95.0% line coverage:` followed by
     `  <pct>%  <path>  (missing <n> lines)` lines on stderr (exit 1).

Exit codes: **0** pass, **1** at least one module under floor, **2** malformed
report. Invocation:

```
python scripts/check_per_module_coverage.py coverage.json --floor 95
```

The `--floor` defaults to 95.0 (`main`/`_build_parser`).

> **Blind spot**: the gate only checks modules that **appear** in
> `coverage.json`. A module never *imported* during the test run simply doesn't
> appear in `files` and is **silently un-gated**. The file count is import-driven,
> not a filesystem enumeration. Adding an expected-module manifest check (or
> diffing against the `[tool.coverage.run].source` enumeration) would close this.

### The Coverage Gate Command

The canonical paste-runnable command lives in `CLAUDE.md` (Coverage Gate
section). In essence:

```
rm -f .coverage*
pytest -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Key details (all from `CLAUDE.md` and `pyproject.toml`):

- `rm -f .coverage*` **is required** — stale `.coverage.*` shards from interrupted
  `xdist` runs otherwise pollute the JSON report.
- `-n auto` runs `pytest-xdist` in parallel (matched by `parallel = true`).
- `-m "not oracle"` excludes the opt-in Oracle testcontainer suite from the gate.
- `-m java` tests **are** measured, so a JVM 11+ on PATH is required for full
  measurement (tMap live-bridge + `java_bridge_manager.py` coverage).
- `pyproject.toml`'s `[tool.coverage.run]` / `[tool.coverage.report]` are the
  source of truth for in-scope modules and the pragma allowlist.

### Locked baseline and the "181 modules" drift

Phase 14 locked the per-module table on **2026-05-11**. CLAUDE.md documents the
expected final line as `PASS: all 181 in-scope modules ...`, and the committed
acceptance artifact `.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json`
contains exactly **181** file records (un-gitignored on purpose as a locked
baseline).

> **This count is now stale.** The 28 post-lock commits added engine modules that
> are absent from the 181 baseline — `pagination.py`, `mssql_connection.py`,
> `mssql_input.py`, `mssql_connection_manager.py`, and several Oracle modules
> (`oracle_bulk_exec/close/commit/rollback/sp`). The current tree has roughly
> ~198 in-scope modules. New modules below 95% would (correctly) fail the gate,
> but the **documented expected-output line and the locked artifact no longer
> match reality**. Anyone re-running the gate should expect a different module
> count and should not trust the "181" figure.

### Gate testing status

There is **no dedicated unit test** for `check_per_module_coverage.py` or
`add_connectors.py` (`scripts/` has no `test_*.py`). The gate is exercised only
indirectly via the CLAUDE.md CI command. There is an always-skipped marker test
(`tests/integration/test_iterate_e2e.py:556`,
`test_phase_10_files_covered_above_90_percent`) that self-documents a coverage
requirement — the pattern the `coverage` pytest marker exists for. Recommended
additions: direct tests for the gate (fixture `coverage.json` at/below/above
floor, malformed-report exit-2 paths) and a round-trip test for `add_connectors`.

---

## How This Subsystem Connects to the Rest

- **API -> Engine**: `api/routes/jobs.py` imports and drives `ETLEngine`
  (`execute`, `set_context_variable`, `__enter__`/`__exit__`). Nothing else in
  the API touches engine internals.
- **Python routines -> Engine**: `PythonRoutineManager` is consumed by the
  Python transform components (`python_component`, `python_row_component`,
  `python_dataframe_component`) via `BaseComponent.get_python_routines()`. The
  API does **not** import the manager.
- **Tooling -> Source**: the coverage scope points at `src/v1/engine` and
  `src/converters`; `add_connectors.py` rewrites `src/router/ui_registry.json`.
- The post-lock **Pagination + Oracle/MSSQL** additions are why the locked
  coverage baseline drifted; they register through the engine's normal `REGISTRY`
  path but the API exposes no endpoints to manage DB connection config/secrets
  (credentials are expected inside the job-config JSON / context variables).

---

## Open Questions

1. **Is `api/` meant to ship, or is it a localhost dev prototype?** The security
   posture (no auth, open CORS, path traversal, RCE-by-design routine writes)
   only makes sense for a trusted single-user tool. If it ships, the HIGH-severity
   findings must be fixed first.
2. **How is the API process launched?** There is no `__main__`/uvicorn entrypoint
   and no `[project.scripts]`; `uvicorn api.app:app` is the presumed but
   undocumented command.
3. **Should `src/python_routines/swift_transformer.py` live there at all?** It is
   a standalone CLI, not an engine routine, yet it sits in the directory
   `PythonRoutineManager` scans and shares a class name with the engine
   `SwiftTransformer` component.
4. **Should the Phase 14 baseline (181 modules) be re-locked** to include the
   post-lock pagination/MSSQL/Oracle modules, or is "181" intentionally frozen as
   a historical artifact? Either way CLAUDE.md's expected-output line is stale.
5. **Is `ui_registry_v2.json` live or dead?** If dead it should be deleted; if
   live, which registry is canonical and why do the naming schemes diverge?
6. **Is `add_connectors.py` still the intended registry generator?** `tPagination`
   exists only in the generated registry, not in `CONNECTOR_MAP`; commit cae6127
   suggested registry generation moved to a build-time step that may supersede the
   script.
7. **Do the new Oracle/MSSQL engine modules have non-`oracle`-marked unit tests?**
   If their only tests are `@pytest.mark.oracle`, they escape the gate's
   measurement entirely when no Oracle container is present (the
   never-imported-means-un-gated blind spot).
