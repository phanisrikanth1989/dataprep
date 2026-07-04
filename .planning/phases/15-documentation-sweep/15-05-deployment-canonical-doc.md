---
phase: 15
plan: 5
slug: deployment-canonical-doc
type: execute
wave: 1
depends_on: [15-01]
files_modified:
  - docs/DEPLOYMENT.md       # NEW (~150-250 lines)
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "docs/DEPLOYMENT.md exists at docs/ root (D-A3)"
    - "Header *Last updated: 2026-05-11* on line 2 (D-C2)"
    - "ASCII-only per D-C1"
    - "Captures Linux + JVM 11+ validated runtime per D-C5"
    - "Cites pyproject.toml as the source of truth for Python dependency pins"
    - "Cites src/v1/java_bridge/java/pom.xml for Java bridge build (mvn package; Java 11 minimum)"
    - "Cites src/v1/engine/java_bridge_manager.py for dynamic-port behavior"
    - "Documents oracledb thin/thick modes per Phase 11; flags ORACLE_OCI / ORACLE_WALLET DEFERRED"
    - "Paste-runnable coverage gate command present (or pointer to CLAUDE.md Coverage section)"
    - "Length within target 150-250 lines"
  artifacts:
    - path: docs/DEPLOYMENT.md
      provides: validated runtime requirements + build + run + test gate for DataPrep deployment
      min_lines: 100
      contains: "# DataPrep Deployment"
  key_links:
    - from: docs/DEPLOYMENT.md
      to: pyproject.toml
      via: cited as the Python dependency pin source of truth
      pattern: "pyproject\\.toml"
    - from: docs/DEPLOYMENT.md
      to: src/v1/java_bridge/java/pom.xml
      via: Java bridge build instructions
      pattern: "pom\\.xml"
    - from: docs/DEPLOYMENT.md
      to: src/v1/engine/java_bridge_manager.py
      via: dynamic-port + JVM lifecycle docs
      pattern: "java_bridge_manager"
    - from: docs/DEPLOYMENT.md
      to: CLAUDE.md
      via: Coverage gate paste-runnable command (referenced, not copied)
      pattern: "CLAUDE\\.md"
---

<objective>
Write `docs/DEPLOYMENT.md` (~150-250 lines): the validated runtime requirements + build + run + test invocation guide for DataPrep. Per D-C5 Linux + JVM 11+ is the validated runtime. Per Phase 14 D-A3 `java_bridge_manager.py` is measured WITH `-m java` markers (JVM 11+ on PATH required for the full test suite). pandas 3.0.1 with CoW is the validated runtime (user memory `project_pandas3_installed`). Oracle integration tests use testcontainers (Docker) and are opt-in via `-m oracle`.
</objective>

<scope>
- Create `docs/DEPLOYMENT.md` from scratch.
- Sections: Validated Runtime, Python Dependencies, Java Bridge, Oracle Components, Configuration, Running a Job, Logging, Test Suite Runtime, Coverage Gate, Known Non-Blocking Items, See Also.
- Source-of-truth pins: extract from live `pyproject.toml` and `pom.xml`. Do NOT invent versions.
- Oracle: mention thin vs thick mode, supported CONNECTION_TYPE (SID / SERVICE_NAME / RAC), DEFERRED (OCI / WALLET).
- Coverage gate: reference CLAUDE.md "Coverage" section (D-B4 -- do not copy) and include a 1-line summary command for convenience.
- Known Non-Blocking Items: carry forward STATE.md Blockers/Concerns (Linux/RHEL `mvn package` build verified only on Darwin; tNormalize combined-flags vs golden Talend job output).
- ASCII-only per D-C1; `*Last updated: 2026-05-11*` header per D-C2.
- Single commit: `docs(15-05): add docs/DEPLOYMENT.md`.
</scope>

<out_of_scope>
- Deploy-automation scripts (D-B1 forbids CI/tooling).
- Cloud / Kubernetes / Docker production deployment recipes -- the doc captures "what runs the engine"; ops choices live elsewhere (deferred indefinitely, captured in plan SUMMARY).
- Editing CLAUDE.md (D-B4).
- src/ changes (D-E3).
</out_of_scope>

<canonical_refs>
- `.planning/phases/15-documentation-sweep/15-CONTEXT.md` D-A3, D-C1, D-C2, D-C5
- `.planning/phases/15-documentation-sweep/15-RESEARCH.md` Section B.4 (full skeleton for DEPLOYMENT.md)
- `pyproject.toml` (Python dependency pins)
- `src/v1/java_bridge/java/pom.xml` (Java 11+, Apache Arrow 15.0.2, Groovy 3.0.21, Py4J 0.10.9.7)
- `src/v1/engine/java_bridge_manager.py` (dynamic port via `socket.bind('', 0)`)
- `src/v1/engine/oracle_connection_manager.py` (Phase 11 connection lifecycle)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md` (gate command)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` (`-m java` / `-m oracle` opt-in convention)
- `.planning/STATE.md` Blockers/Concerns (Known Non-Blocking Items)
- `CLAUDE.md` "Coverage" section (gate; reference don't copy)
- `tests/fixtures/jobs/README.md` (test runtime requirements)
</canonical_refs>

<context>
@.planning/phases/15-documentation-sweep/15-CONTEXT.md
@.planning/phases/15-documentation-sweep/15-RESEARCH.md
@.planning/phases/15-documentation-sweep/15-PLAN.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 15-05-001: Extract live version pins</name>
  <files>(read-only)</files>
  <action>
Pull exact version pins from live build files. The doc MUST cite real pins, not stale ones from the codebase maps.

```bash
# Python dependency pins:
grep -nE "pandas|pyarrow|py4j|openpyxl|xlrd|lxml|oracledb|jsonpath_ng|PyYAML|pytest|pytest-cov|pytest-xdist" pyproject.toml | head -30

# Java bridge pins:
grep -nE "<maven.compiler.source>|<groovy.version>|<arrow.version>|<py4j|<artifactId>" src/v1/java_bridge/java/pom.xml | head -20

# Java bridge dynamic port:
grep -n "socket.bind\|port" src/v1/engine/java_bridge_manager.py | head -5

# pandas runtime (project memory pandas 3.0.1):
python -c "import pandas; print(pandas.__version__)" 2>/dev/null || echo "pandas not importable in this shell"
```

Capture the pinned values. If `pyproject.toml` shows a pin different from RESEARCH.md B.4 (e.g., py4j 0.10.9.9 vs 0.10.9.7), use the LIVE pyproject pin in the doc -- the live file is authority.
  </action>
  <verify>
    <automated>test -f pyproject.toml && test -f src/v1/java_bridge/java/pom.xml && grep -q "maven.compiler.source" src/v1/java_bridge/java/pom.xml && echo "OK: live pins available"</automated>
  </verify>
  <done>Live pins extracted; doc will cite real values.</done>
</task>

<task type="auto">
  <name>Task 15-05-002: Author docs/DEPLOYMENT.md</name>
  <files>docs/DEPLOYMENT.md</files>
  <action>
Create the file with the structure below. Length target: 150-250 lines.

Required H2 sections (in order):

1. `# DataPrep Deployment Guide` (H1, line 1)
2. `*Last updated: 2026-05-11*` (line 2 exact)
3. `## Validated Runtime` -- bullet list:
   - Linux servers (RHEL family validated; other Linux distros work but unvalidated)
   - Python 3.10+
   - JVM 11+ on PATH (REQUIRED for `-m java` test suite; required for any job using Java expressions / tMap / tJava / tJavaRow)
   - Apache Maven 3.x (one-time, to build the Java bridge JAR)
   - Optional: Docker (for Oracle integration tests via testcontainers; opt-in via `-m oracle`)

4. `## Python Dependencies` -- intro paragraph + bullet list of key pins. Use the LIVE values from Task 15-05-001 (`pyproject.toml` pins). Mention:
   - pandas (cite live pin; note 3.0.x with CoW is validated per user memory `project_pandas3_installed`)
   - pyarrow (Arrow IPC for Java bridge data transfer)
   - py4j (cite live pin; gateway client)
   - pytest, pytest-cov (cite >=7.0,<8), pytest-xdist (cite >=3.8,<4)
   - openpyxl, xlrd (Excel)
   - lxml (XML, with secure-parser flags)
   - oracledb (Oracle thin-mode; thick optional)
   - jsonpath_ng (JSONPath)
   - PyYAML (SWIFT transformer config)
   - Install: `pip install -e ".[all]"` (or whatever extras are defined in pyproject.toml -- verify before committing).

5. `## Java Bridge` --
   - Source: `src/v1/java_bridge/java/` (Maven project)
   - Build: `cd src/v1/java_bridge/java && mvn package`
   - Artifact: `target/java-bridge-with-dependencies.jar`
   - Runtime requirement: JVM 11+ on PATH (verified in `pom.xml` `<maven.compiler.source>11</maven.compiler.source>`)
   - Port: dynamically allocated via `socket.bind(('', 0))` in `src/v1/engine/java_bridge_manager.py` (safe under parallel pytest-xdist workers; BUG-JVM-001 Phase 14 verified)
   - Compiled-in deps (cite live pom.xml pins): Apache Arrow, Groovy, Py4J versions

6. `## Oracle Components (Phase 11)` --
   - Driver: oracledb (replaces cx_Oracle)
   - Modes:
     - Thin mode (default): pure Python; no Oracle Client install needed
     - Thick mode: requires Oracle Instant Client on the host
   - Supported CONNECTION_TYPE: `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC`
   - DEFERRED: `ORACLE_OCI`, `ORACLE_WALLET` (raise `ConfigurationError` with deferred-feature message)
   - Credentials: expected in context variables, NEVER in code or logs (per Phase 11 D-A2 / T-11-02)

7. `## Configuration` --
   - No `.env` files. Context variables come from the job-config JSON (`context`, `default_context`).
   - Job-config schema: see `docs/v1/talend_to_v1_converter_guide.md` for the JSON format.

8. `## Running a Job` --
   - CLI: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]`
   - Programmatic: `from src.v1.engine import ETLEngine; ETLEngine(config_dict).execute()`
   - Convenience: `from src.v1.engine.engine import run_job; run_job("path/to/job.json", {"override_var": "value"})`

9. `## Logging` --
   - stdlib `logging`; ASCII-only output (project rule, see `docs/CONTRIBUTING.md` Rule 1).
   - Default level: INFO; set DEBUG for chunk-processing detail.
   - Engine emits structured `[component_id]`-prefixed messages.

10. `## Test Suite Runtime` -- bullet list:
    - Full suite: `python -m pytest tests/ -n auto` (parallel via pytest-xdist)
    - Engine-only: `python -m pytest tests/v1/engine/ -n auto`
    - With Java bridge (requires JVM 11+ on PATH): `python -m pytest tests/ -m java`
    - With Oracle (requires Docker for testcontainers): `python -m pytest tests/ -m oracle`

11. `## Coverage Gate` --
    - Paste-runnable command, per CLAUDE.md "Coverage" section (REFERENCED, not duplicated):
      ```
      rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
        --cov=src/v1/engine --cov=src/converters --cov-report=json \
        && python scripts/check_per_module_coverage.py coverage.json --floor 95
      ```
    - Floor: 95% line coverage per in-scope module (181 modules as of Phase 14 closeout).
    - See `docs/CONTRIBUTING.md` Rule 6 for the contributor-facing rule.

12. `## Known Non-Blocking Items` -- bullet list, sourced from `.planning/STATE.md`:
    - Linux/RHEL `mvn package` build verified only on Darwin so far; full Linux build verification pending.
    - tNormalize combined-flags vs golden Talend job output -- non-blocking, pending Phase 16 integration testing.
    - FileOutputDelimited datetime default format vs Talend reference -- non-blocking.

13. `## See Also` --
    - `docs/ARCHITECTURE.md` (system overview)
    - `docs/CONTRIBUTING.md` (contributor rules)
    - `docs/COMPONENT_REFERENCE.md` (registry inventory)
    - CLAUDE.md (Technology Stack section, Coverage section)

ASCII discipline. Every cited file path must exist; the executor grep-confirms.
  </action>
  <verify>
    <automated>test -f docs/DEPLOYMENT.md && head -2 docs/DEPLOYMENT.md | grep -qF "*Last updated: 2026-05-11*" && test -z "$(grep -nP '[^\x00-\x7F]' docs/DEPLOYMENT.md)" && grep -qF "JVM 11" docs/DEPLOYMENT.md && grep -qF "mvn package" docs/DEPLOYMENT.md && grep -qF "java_bridge_manager" docs/DEPLOYMENT.md && grep -qF "pyproject.toml" docs/DEPLOYMENT.md && grep -qF "ORACLE_WALLET" docs/DEPLOYMENT.md && grep -qF "check_per_module_coverage" docs/DEPLOYMENT.md && lines=$(wc -l < docs/DEPLOYMENT.md) && test "$lines" -ge 100 && test "$lines" -le 350 && echo "OK: deployment doc + length=$lines"</automated>
  </verify>
  <done>DEPLOYMENT.md created with all 13 H2 sections; ASCII verified; live pins cited; length 100-350.</done>
</task>

<task type="auto">
  <name>Task 15-05-003: Path + pin verification sweep</name>
  <files>(read-only)</files>
  <action>
Verify every cited path and version pin exists in the live repo.

```bash
# Paths:
grep -oE "src/[a-zA-Z0-9_/]+\.py" docs/DEPLOYMENT.md | sort -u | while read p; do test -f "$p" || echo "MISSING $p"; done
grep -oE "src/[a-zA-Z0-9_/]+\.xml" docs/DEPLOYMENT.md | sort -u | while read p; do test -f "$p" || echo "MISSING $p"; done

# Pins -- spot-check 3 most-cited:
for pin in $(grep -oE "[a-zA-Z_-]+ ?[><=]+ ?[0-9]+\.[0-9]+" docs/DEPLOYMENT.md | head -5); do
  echo "Cited pin: $pin"
done
# Each should be visually confirmable against pyproject.toml or pom.xml. The executor reads both to confirm.
```

Any MISSING line: fix the doc. Any pin disagreement with `pyproject.toml`: update the doc to match the live pin.
  </action>
  <verify>
    <automated>missing=$(grep -oE "src/[a-zA-Z0-9_/]+\.(py|xml)" docs/DEPLOYMENT.md | sort -u | while read p; do test -f "$p" || echo X; done | wc -l | tr -d ' ') && test "$missing" = "0" && echo "OK: all cited paths exist"</automated>
  </verify>
  <done>All cited paths exist; all cited pins match live pyproject.toml / pom.xml; verification log captured.</done>
</task>

<task type="auto">
  <name>Task 15-05-004: Commit</name>
  <files>docs/DEPLOYMENT.md</files>
  <action>
Atomic commit per D-E1:

```bash
git add docs/DEPLOYMENT.md
git commit -m "docs(15-05): add docs/DEPLOYMENT.md (Linux + JVM 11+ validated runtime)

Validated runtime per D-C5 (Linux + JVM 11+). Captures Python
dependency pins from pyproject.toml live, Java bridge build via
src/v1/java_bridge/java/pom.xml (mvn package), Oracle component
support (Phase 11 thin/thick modes; SID/SERVICE_NAME/RAC supported;
OCI/WALLET deferred), and the paste-runnable coverage gate
referenced from CLAUDE.md 'Coverage' section.

Known Non-Blocking Items carried forward from STATE.md.

Refs: 15-CONTEXT.md D-A3, D-C2, D-C5; 15-RESEARCH.md B.4"
```
  </action>
  <verify>
    <automated>git log -1 --pretty=%s | grep -qF "docs(15-05): add docs/DEPLOYMENT.md" && test "$(git diff --stat HEAD~1..HEAD -- src/ | wc -l | tr -d ' ')" = "0" && echo "OK: committed; no src/ touch"</automated>
  </verify>
  <done>Single commit landed; no src/ touched; HEAD subject matches.</done>
</task>

</tasks>

<verification_gate>

Plan 15-05 is GREEN when:
1. `docs/DEPLOYMENT.md` exists at `docs/` root.
2. `*Last updated: 2026-05-11*` on line 2.
3. ASCII-only.
4. JVM 11+, mvn package, java_bridge_manager, pyproject.toml, ORACLE_WALLET, check_per_module_coverage all cited.
5. All cited `src/` paths exist.
6. Length 100-350 lines (target 150-250).
7. Single commit landed; no src/ touched.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `docs(15-05): add docs/DEPLOYMENT.md (Linux + JVM 11+ validated runtime)` | `docs/DEPLOYMENT.md` |

(Total: 1 commit.)

</commit_map>
