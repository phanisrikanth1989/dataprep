# DataPrep -- Local Development Setup

*Last updated: 2026-05-11*

This guide walks a new contributor from `git clone` to "I can run the test suite,
build the Java bridge, and convert a Talend `.item` file to JSON" in roughly
20 minutes.

If you only need to deploy the engine on a server (no test suite, no source), see
`docs/DEPLOYMENT.md` instead. If you already have the environment and just want
to run a job, see `docs/guides/QUICKSTART.md`.

---

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.10+ | The engine uses `set[str]` PEP-585 syntax without `from __future__ import annotations`. 3.9 will not parse `src/v1/engine/components/transform/swift_transformer.py`. |
| Java JDK | 11+ | The Java bridge subprocess executes Talend Java/Groovy expressions. Pinned in `src/v1/java_bridge/java/pom.xml`. |
| Maven | 3.x | Builds the Java bridge JAR. The `mvn package` step shades all runtime deps into one fat JAR. |
| Git | any modern version | -- |

Confirm with:

```bash
python3 --version    # >= 3.10
java -version        # >= 11
mvn -version
git --version
```

If Java reports a JRE rather than a JDK, install the JDK -- Maven needs `javac`,
not just `java`.

---

## 1. Clone and create a virtualenv

```bash
git clone <repo-url> dataprep
cd dataprep

python3 -m venv .venv
source .venv/bin/activate
```

The repo expects an activated venv for all subsequent commands. If you use
`pyenv`, `conda`, or a system Python, the steps still work -- just keep
the interpreter consistent across `pip install` and `pytest` invocations.

---

## 2. Install Python dependencies

DataPrep uses `pyproject.toml` (PEP 621) with optional extras grouped by
subsystem.

```bash
# Install the project with ALL runtime extras and the dev tools
pip install --upgrade pip
pip install -e ".[all,dev]"
```

The `[all]` extra resolves to
`[java,excel,xml,yaml,json,api,oracle]` and pulls in `pyarrow`, `py4j`,
`openpyxl`, `xlrd`, `lxml`, `PyYAML`, `jsonpath-ng`, `fastapi`, and
`oracledb`. The `[dev]` extra adds `pytest`, `pytest-cov`, `pytest-xdist`,
and `testcontainers`.

If you only intend to work on the converter (no engine execution), you can
omit the runtime extras:

```bash
pip install -e ".[dev]"
```

---

## 3. Build the Java bridge JAR

The Java bridge is a Py4J + Apache Arrow subprocess. Engine components that
evaluate `{{java}}`-tagged expressions (and tMap in live mode) require it.

```bash
cd src/v1/java_bridge/java
mvn package
cd -
```

Expected artifact:

```
src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar
```

The first build pulls Arrow 15.0.2, Groovy 3.0.21, and Py4J 0.10.9.9 from
Maven Central -- expect ~2 min the first time, ~10 s on rebuilds. The
shaded JAR includes every runtime dep, so no classpath setup is needed at
engine startup.

**You can skip this step** if you only plan to run jobs that do not use
`{{java}}` markers or `tMap` in live mode. The engine starts the bridge
lazily -- jobs without Java expressions never touch the JAR.

---

## 4. Smoke test -- run the unit suite

```bash
python -m pytest tests/ -m "not oracle and not java" -n auto
```

Expected: roughly 7900 tests pass in ~50 s. `-n auto` runs xdist in
parallel across cores. The `not oracle and not java` filter skips two
opt-in test classes:

- `oracle` tests spin up a real Oracle DB via testcontainers (slow,
  requires Docker).
- `java` tests require the bridge JAR from step 3 to be present.

To include the Java-bridge tests once the JAR is built:

```bash
python -m pytest tests/ -m "not oracle" -n auto
```

---

## 5. Coverage gate -- the 95% per-module floor

CONTRIBUTING.md Rule 6 requires every in-scope module to clear 95% line
coverage. To run the gate locally before pushing:

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected final line:

```
PASS: all 181 in-scope modules at >= 95.0% line coverage
```

The `rm -f .coverage*` prefix is required (Phase 14 locked Q5) -- stale
`.coverage.*` shards from interrupted xdist runs pollute the JSON
otherwise. The full command is also documented in `CLAUDE.md` under
"Coverage".

`htmlcov/` and `coverage.json` are gitignored at the project root; per-phase
acceptance artifacts (for example `14-coverage.json`) live under
`.planning/phases/{N}-{name}/` for historical reference.

---

## 6. First conversion -- end-to-end smoke

Convert a sample Talend `.item` file to V1 JSON:

```bash
python -m src.converters.talend_to_v1.converter \
    tests/fixtures/talend/<some_job>.item \
    /tmp/test_job.json
```

(Replace `<some_job>.item` with an actual fixture path; `ls
tests/fixtures/talend/` shows what is available.)

Then execute the JSON:

```bash
python src/v1/engine/engine.py /tmp/test_job.json
```

See `docs/guides/QUICKSTART.md` for the full conversion-and-execution
walkthrough with worked examples.

---

## 7. Editor / IDE setup (optional)

- **VS Code / Cursor**: select the `.venv/bin/python` interpreter so
  Pylance picks up the installed extras. Recommended extensions: Python,
  Pylance, Even Better TOML.
- **PyCharm**: mark `src/` as a Sources Root, point the Python interpreter
  at `.venv/bin/python`.
- **No automated formatter** is wired up. Stay consistent with neighboring
  code -- 4-space indent, double quotes, `snake_case.py` modules,
  `PascalCase` classes. See `CLAUDE.md` "Conventions" for the full inventory.

---

## Troubleshooting

**`pip install -e ".[all]"` errors on `oracledb` build.**
The Oracle extra needs system libs on some platforms (Linux Instant
Client, macOS thin-mode handles itself). Drop the `oracle` extra if you do
not need it: `pip install -e ".[java,excel,xml,yaml,json,dev]"`.

**`mvn package` fails with "no compiler is provided in this environment".**
You have a JRE, not a JDK. Install the JDK -- on macOS:
`brew install --cask temurin@11`.

**`java` tests fail with "JavaBridge connect timeout".**
Confirm the JAR exists at
`src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`. If the
JAR is present, check JAVA_HOME and ensure `java -version` reports 11+.

**Coverage gate fails with module below 95%.**
Run with `--cov-report=term-missing` and inspect the listed line numbers.
The fix is usually a missing test path -- not a `# pragma: no cover`
(Rule 7 forbids new pragmas).

**xdist hangs on the engine pipeline tests.**
You may have a stale `.coverage.*` shard. `rm -f .coverage*` and re-run.

---

## See Also

- `docs/guides/QUICKSTART.md` -- convert a `.item` file and run the JSON in 5 min
- `docs/guides/AUTHORING_JOB_JSON.md` -- write a job JSON by hand without a Talend source
- `docs/CONTRIBUTING.md` -- the 10 load-bearing project rules + git workflow
- `docs/DEPLOYMENT.md` -- production runtime requirements
- `docs/ARCHITECTURE.md` -- system layers and key abstractions
- `CLAUDE.md` -- codebase conventions, coverage command, Java bridge details
