# DataPrep Deployment Guide
*Last updated: 2026-05-11*

This guide captures the validated runtime requirements, build steps, and
test-invocation conventions for deploying the DataPrep Talend ETL Migration
Engine. Every version pin and file reference here is sourced from the live
repository -- `pyproject.toml` and `src/v1/java_bridge/java/pom.xml` are the
sources of truth for dependency versions.

## Validated Runtime

- Linux servers (RHEL family validated; other Linux distributions are
  expected to work but are not formally verified).
- Python 3.10+ (CPython). Required by `pyproject.toml`
  (`requires-python = ">=3.10"`).
- JVM 11+ on PATH. REQUIRED for any job using Java expressions, tMap,
  tJava, or tJavaRow, and REQUIRED for the `-m java` test suite (Phase 14
  D-A3 measures `src/v1/engine/java_bridge_manager.py` with `-m java`
  markers).
- Apache Maven 3.x. One-time requirement to build the Java bridge JAR.
- Optional: Docker. Required only for Oracle integration tests via
  testcontainers (opt-in via `-m oracle`).

## Python Dependencies

The single source of truth for Python dependency pins is `pyproject.toml`
at the repository root. The pins below mirror that file -- if the file
disagrees, the file wins.

Core (always installed):

- `pandas>=2.0,<4` -- DataFrame transport across the engine. The runtime
  has been validated against pandas 3.0.x with Copy-on-Write enabled.
- `numpy>=1.24,<3` -- numerical operations and Java bridge buffers.

Optional extras (declared in `pyproject.toml` under `[project.optional-dependencies]`):

- `java` -- `pyarrow>=15.0,<24`, `py4j>=0.10.9,<0.11`. Required for the
  Java bridge (Arrow IPC for DataFrame transfer, Py4J for the JVM gateway).
- `excel` -- `openpyxl>=3.1,<4`, `xlrd>=2.0,<3`. Required for `.xlsx`
  and legacy `.xls` Excel components.
- `oracle` -- `oracledb>=2.5,<4`. Required for Oracle components
  (`OracleConnection`, `OracleRow`, `OracleOutput`).
- `xml` -- `lxml>=4.9,<7`. Required for XML components.
- `yaml` -- `PyYAML>=6.0,<7`. Required for the SWIFT transformer config.
- `json` -- `jsonpath-ng>=1.5,<2`. Required for `tExtractJSONFields`.
- `api` -- `fastapi`, `uvicorn[standard]`, `python-multipart`. Required
  only when serving the optional HTTP API.
- `dev` -- `pytest>=8.0,<10`, `pytest-cov>=7.0,<8`, `pytest-xdist>=3.8,<4`,
  `testcontainers>=4`. Required to run the test suite and the coverage
  gate.

Install everything in one shot:

```
pip install -e ".[all]"
```

The `all` extra is defined as
`dataprep[java,excel,xml,yaml,json,api,oracle]` in `pyproject.toml`. Add
the `dev` extra explicitly when running tests: `pip install -e ".[all,dev]"`.

## Java Bridge

The Java bridge is a Py4J + Apache Arrow subprocess that executes Talend
Java / Groovy expressions and tMap row-level transformations.

- Source: `src/v1/java_bridge/java/` (Maven project).
- Build: `cd src/v1/java_bridge/java && mvn package`.
- Artifact: `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`.
- Runtime requirement: JVM 11+ on PATH. The minimum is enforced in the
  POM via `<maven.compiler.source>11</maven.compiler.source>` and
  `<maven.compiler.target>11</maven.compiler.target>` in
  `src/v1/java_bridge/java/pom.xml`.
- Port allocation: dynamic. `src/v1/engine/java_bridge_manager.py`
  acquires a free port via `socket.bind(('', 0))` in `_find_free_port()`
  and retries up to 3 times on TOCTOU race. This is safe under parallel
  `pytest-xdist` workers (Phase 14 BUG-JVM-001 verified).

Compiled-in dependency pins (from `src/v1/java_bridge/java/pom.xml`
`<properties>`):

- Apache Arrow 15.0.2 (`<arrow.version>15.0.2</arrow.version>`).
- Groovy 3.0.21 (`<groovy.version>3.0.21</groovy.version>`).
- Py4J 0.10.9.9 (`<py4j.version>0.10.9.9</py4j.version>`).

The bridge JAR is shaded via `maven-shade-plugin` so all runtime
dependencies ship in the single
`target/java-bridge-with-dependencies.jar` artifact -- no external Java
classpath needed.

## Oracle Components (Phase 11)

DataPrep uses the `oracledb` driver (the modern successor to `cx_Oracle`).

- Thin mode (default): pure Python; no Oracle Client install required.
  Recommended for most deployments.
- Thick mode: requires Oracle Instant Client installed on the host.
  Opt in by setting the appropriate `oracledb.init_oracle_client()` call
  before engine startup (see `oracledb` docs).

Supported `connection_type` values
(`src/v1/engine/oracle_connection_manager.py`):

- `ORACLE_SID` -- legacy SID-based connect string.
- `ORACLE_SERVICE_NAME` -- modern service-name connect string.
- `ORACLE_RAC` -- RAC URL connect string.

DEFERRED (refused with `ConfigurationError`):

- `ORACLE_OCI` -- requires thick mode + Instant Client; tracked in
  deferred items.
- `ORACLE_WALLET` -- requires thick mode + wallet provisioning; tracked
  in deferred items.

Credentials policy: Oracle credentials MUST be supplied via context
variables in the job-config JSON. They MUST NOT appear in source code,
in logs, or in committed config files (Phase 11 D-A2 / T-11-02).

Oracle integration tests use `testcontainers` (Docker) and are opt-in via
the `-m oracle` pytest marker. They are excluded from the default
coverage gate.

## Configuration

DataPrep does not use `.env` files. All deployment-specific variables are
supplied as context variables in the job-config JSON
(`context` / `default_context` blocks).

Override context variables at the engine CLI:

```
python src/v1/engine/engine.py path/to/job.json --context_param DB_HOST=prod-db
```

For the JSON schema and the full list of supported component types, see
`docs/v1/talend_to_v1_converter_guide.md`.

## Running a Job

Three invocation styles are supported.

CLI:

```
python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]
```

Programmatic, engine-level:

```
from src.v1.engine import ETLEngine
ETLEngine(config_dict).execute()
```

Programmatic, convenience helper:

```
from src.v1.engine.engine import run_job
run_job("path/to/job.json", {"override_var": "value"})
```

## Logging

- Stdlib `logging` is used throughout. No third-party logging framework.
- Output is ASCII-only by project convention (RHEL deployment targets;
  see CLAUDE.md "Conventions" section, "ASCII-only logs" rule).
- Default level is `INFO`. Set `DEBUG` for chunk-level processing
  detail.
- The engine emits messages prefixed with the component id, e.g.
  `[tFileInputDelimited_1] Read 1247 rows from input.csv`.

## Test Suite Runtime

All commands assume `pip install -e ".[all,dev]"` has been run.

- Full suite (parallel, excludes Oracle):
  `python -m pytest tests/ -m "not oracle" -n auto`
- Engine subsuite:
  `python -m pytest tests/v1/engine/ -n auto`
- Java bridge tests (REQUIRES JVM 11+ on PATH):
  `python -m pytest tests/ -m java`
- Oracle integration tests (REQUIRES Docker for testcontainers):
  `python -m pytest tests/ -m oracle`

The `-m java` and `-m oracle` markers are declared in `pyproject.toml`
under `[tool.pytest.ini_options]`.

## Coverage Gate

The Phase 14 coverage gate enforces a 95% line-coverage floor per
in-scope module. The full paste-runnable command lives in CLAUDE.md
"Coverage" section -- treat that as the source of truth. The convenience
form below is functionally identical:

```
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine --cov=src/converters --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected outcome: exit 0 with final stdout line
`PASS: all 181 in-scope modules at >= 95.0% line coverage`.

Notes:

- The `rm -f .coverage*` prefix is required (Phase 14 locked Q5) to
  prevent stale shards from polluting the JSON report.
- The gate excludes Oracle live tests by default (`-m "not oracle"`).
  Phase 11's testcontainer suite is the verification path for Oracle
  code paths.
- The `[tool.coverage.run]` and `[tool.coverage.report]` blocks in
  `pyproject.toml` are the source of truth for in-scope modules and the
  pragma allowlist (`__main__`, `@abstractmethod`,
  `raise NotImplementedError`).
- Branch coverage is intentionally disabled (Phase 13 D-E2 / Phase 14
  D-E4 reasoning).

## Known Non-Blocking Items

Carried forward from `.planning/STATE.md` Blockers/Concerns; none of
these block production deployment but each warrants tracking:

- Linux / RHEL `mvn package` build path: verified only on Darwin so far.
  Full Linux build verification is pending integration testing.
- `tNormalize` combined-flags handling: not fully verified against
  golden Talend job output. Tracked for Phase 16 integration testing.
- `FileOutputDelimited` datetime default format: minor divergence vs the
  Talend reference. Non-blocking.

## See Also

- `docs/ARCHITECTURE.md` -- system overview, layers, registry discipline.
- `docs/CONTRIBUTING.md` -- contributor rules (ASCII-only, atomic commits,
  registry + abstract-method discipline, 95% coverage floor).
- `docs/COMPONENT_REFERENCE.md` -- registry-driven component inventory.
- `docs/v1/talend_to_v1_converter_guide.md` -- job-config JSON schema and
  external-consumer guide.
- `CLAUDE.md` -- Technology Stack section and Coverage section (the
  authoritative paste-runnable coverage gate command).
