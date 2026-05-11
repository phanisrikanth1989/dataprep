---
phase: 15
plan: 5
slug: deployment-canonical-doc
type: execute
status: complete
completed: 2026-05-11
requirements: [DOCS-01]
provides:
  - canonical docs/DEPLOYMENT.md (Linux + JVM 11+ validated runtime)
files_created:
  - docs/DEPLOYMENT.md
files_modified: []
key_links:
  - from: docs/DEPLOYMENT.md
    to: pyproject.toml
    via: Python dependency pin source of truth
  - from: docs/DEPLOYMENT.md
    to: src/v1/java_bridge/java/pom.xml
    via: Java bridge build (mvn package, Java 11+)
  - from: docs/DEPLOYMENT.md
    to: src/v1/engine/java_bridge_manager.py
    via: dynamic-port allocation
  - from: docs/DEPLOYMENT.md
    to: src/v1/engine/oracle_connection_manager.py
    via: Oracle CONNECTION_TYPE + deferred OCI/WALLET
  - from: docs/DEPLOYMENT.md
    to: CLAUDE.md
    via: Coverage gate (referenced, not duplicated)
decisions: []
metrics:
  duration_minutes: 8
  tasks_completed: 4
  files_count: 1
  commits_count: 1
---

# Phase 15 Plan 5: Deployment Canonical Doc Summary

Wrote `docs/DEPLOYMENT.md` as the canonical deployment guide for DataPrep
covering validated runtime (Linux + JVM 11+ per D-C5), Python dependency
pins sourced live from `pyproject.toml`, Java bridge build via
`src/v1/java_bridge/java/pom.xml` (`mvn package`), Oracle component
support (thin/thick modes; SID / SERVICE_NAME / RAC supported; OCI /
WALLET deferred), and the paste-runnable coverage gate referenced from
CLAUDE.md "Coverage" section.

## Truths Verified

- `docs/DEPLOYMENT.md` exists at `docs/` root (D-A3).
- Line 1: `# DataPrep Deployment Guide`. Line 2: `*Last updated: 2026-05-11*` (D-C2).
- ASCII-only: `grep -nP "[^\x00-\x7F]" docs/DEPLOYMENT.md` returns zero lines (D-C1).
- Captures Linux + JVM 11+ validated runtime (D-C5).
- Cites `pyproject.toml` as the source of truth for Python dependency pins.
- Cites `src/v1/java_bridge/java/pom.xml` for the Java bridge build
  (`mvn package`; Java 11 minimum confirmed via
  `<maven.compiler.source>11</maven.compiler.source>`).
- Cites `src/v1/engine/java_bridge_manager.py` for dynamic-port behavior
  (`socket.bind(('', 0))` in `_find_free_port()`).
- Documents `oracledb` thin / thick modes per Phase 11; flags
  `ORACLE_OCI` and `ORACLE_WALLET` as DEFERRED (refused with
  `ConfigurationError`).
- Paste-runnable coverage gate command present (and points at CLAUDE.md
  "Coverage" section as the source of truth).
- Length: 240 lines (within the 150-250 target).

## Live Version Pins (Task 15-05-001)

Pulled directly from `pyproject.toml` and `src/v1/java_bridge/java/pom.xml`:

| Component | Live pin | Source |
|-----------|----------|--------|
| pandas | `>=2.0,<4` | pyproject.toml |
| numpy | `>=1.24,<3` | pyproject.toml |
| pyarrow | `>=15.0,<24` | pyproject.toml |
| py4j | `>=0.10.9,<0.11` | pyproject.toml |
| oracledb | `>=2.5,<4` | pyproject.toml |
| lxml | `>=4.9,<7` | pyproject.toml |
| pytest | `>=8.0,<10` | pyproject.toml |
| pytest-cov | `>=7.0,<8` | pyproject.toml |
| pytest-xdist | `>=3.8,<4` | pyproject.toml |
| Apache Arrow (Java) | 15.0.2 | pom.xml |
| Groovy | 3.0.21 | pom.xml |
| Py4J (Java) | 0.10.9.9 | pom.xml |
| Java minimum | 11 | pom.xml `<maven.compiler.source>` |

Note: the live `pom.xml` carries `py4j.version=0.10.9.9` (one minor patch
ahead of the 0.10.9.7 figure in older codebase maps). The doc cites the
live pin per Task 15-05-001 instruction.

## Path Verification Sweep (Task 15-05-003)

All `src/` paths cited in the doc were grep-confirmed to exist in the
live tree:

- `src/v1/engine/engine.py` -- OK
- `src/v1/engine/java_bridge_manager.py` -- OK
- `src/v1/engine/oracle_connection_manager.py` -- OK
- `src/v1/java_bridge/java/pom.xml` -- OK

`docs/` sibling references (`docs/ARCHITECTURE.md`,
`docs/COMPONENT_REFERENCE.md`, `docs/CONTRIBUTING.md`,
`docs/v1/talend_to_v1_converter_guide.md`) are forward references to
Wave 1 sibling plans (15-02, 15-03, 15-04) and the already-existing
converter guide. The converter guide exists in the live tree; the three
Wave 1 docs land in parallel with this plan and will all exist after the
Wave 1 merge.

## Deviations from Plan

None. Plan executed exactly as written. The plan's optional
`pip install -e ".[all]"` was confirmed against `pyproject.toml`
(the `all` extra is defined as
`dataprep[java,excel,xml,yaml,json,api,oracle]`) and reflected verbatim
in the doc.

## Commits

1. `docs(15-05): add docs/DEPLOYMENT.md (Linux + JVM 11+ validated runtime)` -- `docs/DEPLOYMENT.md`

(Single atomic commit per D-E1.)

## Out-of-Scope Discoveries (Deferred)

None. No `src/` changes (D-E3 honored). No `docs/v1/audit/` modifications
(D-A4 honored). No CLAUDE.md edits (D-B4 honored).

## Self-Check: PASSED

- `docs/DEPLOYMENT.md` exists -- verified.
- Line 2 header `*Last updated: 2026-05-11*` -- verified.
- ASCII-only -- verified (`grep -nP "[^\x00-\x7F]"` returns zero lines).
- Required tokens (`JVM 11`, `mvn package`, `java_bridge_manager`,
  `pyproject.toml`, `ORACLE_WALLET`, `check_per_module_coverage`,
  `pom.xml`, `CLAUDE.md`) all present -- verified.
- Line count 240 (within 150-250 target) -- verified.
- All 4 cited `src/` paths exist -- verified.
- Single commit landed -- recorded below post-commit.
