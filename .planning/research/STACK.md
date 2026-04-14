# Stack Research

**Domain:** Python ETL Engine with Java Interop (Talend Migration)
**Researched:** 2026-04-14
**Confidence:** HIGH (core stack verified via official docs and PyPI; patterns verified via multiple sources)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ (target 3.12) | Engine runtime, all ETL logic | Already in use. 3.12 is the sweet spot: mature, fast, fully supported by all dependencies. 3.10 is the floor due to `set[str]` syntax. Do NOT jump to 3.13/3.14 yet -- pyarrow and pandas still stabilizing on those. |
| pandas | 2.2.3 | DataFrame-based data transport between components | **Stay on 2.2.x for this milestone.** Pandas 3.0 (Jan 2026) changes string inference to Arrow-backed by default and enforces Copy-on-Write -- both break existing ETL code patterns. Upgrade path: get to 2.2.3, then 2.3.x (to see deprecation warnings), then plan 3.0 as a separate milestone. |
| pyarrow | 15.0.2 (Python) | Arrow IPC serialization for Java bridge data transfer | **Keep Python pyarrow pinned to 15.0.2 to match Java Arrow 15.0.2.** Arrow IPC format is backward-compatible across versions, but keeping versions aligned eliminates edge cases with decimal128 precision handling and timestamp formatting. Upgrade both sides together as a deliberate task. |
| Apache Arrow (Java) | 15.0.2 | Arrow IPC deserialization on Java side, vector operations | Already in pom.xml. Matches pyarrow. Newer Arrow versions (18+) add Decimal32/64 and transparent compression, but upgrading requires rebuilding the fat JAR and re-testing all type round-trips. Defer to a future milestone. |
| Py4J | 0.10.9.9 (Python) + 0.10.9.7 (Java) | Python-Java gateway communication over TCP sockets | **Upgrade Python side from 0.10.9.7 to 0.10.9.9.** Version 0.10.9.9 adds "Retry on empty response" which directly addresses the bridge reliability problems. The Java JAR side at 0.10.9.7 is compatible with Python 0.10.9.9 (Py4J is cross-version compatible within 0.10.9.x). Keep Java at 0.10.9.7 to avoid pom.xml churn. |
| Groovy | 3.0.21 | Dynamic expression evaluation (Java bridge) | **Stay on 3.0.x for this milestone.** Groovy 4.0+ changed the Maven groupId from `org.codehaus.groovy` to `org.apache.groovy` and requires all-InvokeDynamic bytecode. The upgrade is mechanical but touches every Java compilation path. Not worth the risk during engine hardening. |
| Java | 11+ | JVM runtime for Java bridge subprocess | Already specified in pom.xml. Java 11 is fine. Java 17 is supported by Py4J 0.10.9.7+ and gives better performance, but not required. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| oracledb | 3.4.2 | Oracle database connectivity (replaces cx_Oracle) | Oracle components (tOracleInput, tOracleOutput, etc.). cx_Oracle is obsolete. oracledb is the official successor with Thin mode (no Oracle Client needed) and Thick mode for advanced features. |
| numpy | 1.26.x | Numerical operations, array handling in bridge | Already used in bridge.py for Java result array conversion. Pin to 1.26.x for pandas 2.2 compatibility. numpy 2.0+ requires pandas 2.1+ but has breaking API changes -- test carefully if upgrading. |
| openpyxl | 3.1.x | Excel .xlsx read/write | Already used for tFileInputExcel/tFileOutputExcel. Stable, no changes needed. |
| xlrd | 2.0.1 | Legacy .xls read | Already used. Last release 2.0.1 (Dec 2020). Stable, no alternatives for .xls format. |
| lxml | 5.x | XML processing with XPath | Already used for tExtractXMLFields, tXMLMap. Keep current. |
| PyYAML | 6.x | YAML config parsing | Already used for SWIFT transformer. Keep current. |
| jsonpath-ng | 1.6.x | JSONPath expression evaluation | Already used for tExtractJSONFields. Keep current. |

### Development & Testing Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| pytest | 8.x | Test framework | **Must add** -- engine currently has zero tests. Use pytest 8.x for modern fixture and parametrize support. |
| pytest-cov | 5.x | Coverage reporting | Track coverage goals. Target 80%+ for engine core, 90%+ for base_component. |
| pandas.testing | (bundled) | DataFrame assertion/comparison | Use `assert_frame_equal()` for component output validation. Supports dtype checking, tolerance for floats, index comparison options. |
| structlog | 25.x | Structured logging (optional) | **Consider but do not require.** Standard `logging` module is already in use throughout. structlog adds JSON output, context binding, and structured fields -- valuable for production log aggregation. However, migrating from `logging` to `structlog` is a cross-cutting change that touches every file. Recommendation: add structlog as a dependency, use it for new code, wrap existing loggers incrementally. |

### Infrastructure Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Maven 3.x | Build Java bridge JAR | Already in use. No changes needed. |
| pyproject.toml | **Must add** -- Python project configuration | Project currently has NO requirements.txt, setup.py, or pyproject.toml. This is a critical gap. All dependencies are implicit. Create a pyproject.toml with pinned versions. |

## Installation

```bash
# Create pyproject.toml first, then:

# Core runtime
pip install pandas==2.2.3 pyarrow==15.0.2 py4j==0.10.9.9 numpy==1.26.4

# Database
pip install oracledb==3.4.2

# File format support
pip install openpyxl==3.1.5 xlrd==2.0.1 lxml==5.3.1 PyYAML==6.0.2 jsonpath-ng==1.6.1

# Development
pip install pytest==8.3.4 pytest-cov==5.0.0

# Optional: structured logging
pip install structlog==25.1.0

# Java bridge (Maven)
cd src/v1/java_bridge/java && mvn clean package -DskipTests
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| pandas 2.2.x | pandas 3.0.x | After this milestone is complete and engine is stable. Pandas 3.0 Copy-on-Write default and Arrow-backed strings will improve performance but require careful testing of every component's DataFrame mutation patterns. |
| pandas 2.2.x | Polars | Never for this project. Polars has a fundamentally different API (lazy evaluation, no index). Would require rewriting every component. The Talend parity requirement means we need pandas' mutable DataFrame semantics. |
| pyarrow 15.0.2 | pyarrow 18+ or 23.x | When you're ready to upgrade Arrow Java simultaneously. Arrow 18+ adds Decimal32/64 and transparent IPC compression. Arrow 23.x is latest but requires matching Java side rebuild. |
| Py4J 0.10.9.9 | JPype | Only if you need in-process JVM (no subprocess). JPype embeds the JVM in the Python process, enabling zero-copy Arrow exchange via pyarrow.jvm module. But: it requires a complete rewrite of the Java bridge, risks JVM crashes taking down the Python process, and the Py4J approach (separate JVM subprocess) provides better isolation. Stick with Py4J. |
| Py4J 0.10.9.9 | gRPC / Protocol Buffers | Only if Py4J's TCP socket protocol becomes a bottleneck (unlikely at ETL data volumes). gRPC adds complexity, requires .proto definitions, and provides no benefit when you're already using Arrow IPC for bulk data transfer. |
| oracledb 3.4.2 | cx_Oracle 8.x | Never. cx_Oracle is obsolete and no longer maintained. oracledb is the official successor from Oracle, with drop-in API compatibility. |
| Groovy 3.0.21 | Groovy 4.0+ / 5.0 | After engine stabilization. Groovy 4/5 require Maven groupId change, all-InvokeDynamic bytecode. Worth doing for performance but not during hardening. |
| Standard logging | structlog | When setting up production log aggregation. structlog wraps standard logging so migration is incremental, not big-bang. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| cx_Oracle | Obsolete, no longer maintained by Oracle. Will not receive security patches. | oracledb 3.4.2 (official successor, API-compatible) |
| pandas 3.0 (this milestone) | Copy-on-Write default breaks chained assignment (`df[col][row] = value`), Arrow-backed strings change dtype inference. Both patterns are used throughout engine components. | pandas 2.2.3, then plan upgrade for next milestone |
| Polars | Different API paradigm (lazy, no index, no in-place mutation). Would require rewriting all 50+ engine components. | pandas 2.2.x |
| Dask | Adds distributed computing overhead. Project constraint: "single-threaded is fine for now." Dask's lazy evaluation model doesn't match the eager execution model of the Talend component pipeline. | pandas chunked processing (already implemented in BaseComponent) |
| JPype | Embeds JVM in Python process. JVM crash = Python process crash. No isolation. | Py4J (separate JVM subprocess, crash isolation) |
| asyncio-based engine | Tempting for iterate/parallel execution, but: (1) Python GIL means no true parallelism for CPU-bound work, (2) all components are synchronous, (3) adds complexity with no benefit for single-threaded ETL. | Sequential BFS execution loop with `graphlib.TopologicalSorter` |
| subprocess.run() for Java | Loses the persistent JVM connection. Each call would restart the JVM (2+ seconds startup). | Py4J persistent gateway (start once, call many times) |
| print() for debugging | Already flagged in PROJECT.md. print() bypasses log levels, can't be filtered, doesn't include timestamps/component IDs. | `logging.getLogger(__name__)` with `[component_id]` prefix (already in BaseComponent) |

## Stack Patterns by Variant

**If processing datasets < 1GB (most Talend jobs):**
- Use batch mode (ExecutionMode.BATCH) -- load full DataFrame, process in one pass
- Because: simpler code paths, no chunk reassembly overhead, pandas optimized for in-memory operations

**If processing datasets 1-10GB:**
- Use hybrid mode (ExecutionMode.HYBRID) with automatic switching at 3GB threshold
- Because: the existing `MEMORY_THRESHOLD_MB = 3072` auto-switches to streaming. The chunked processing in `_execute_streaming()` handles this correctly for most components.

**If processing datasets > 10GB:**
- Use streaming mode (ExecutionMode.STREAMING) with explicit chunk_size tuning
- Because: prevents OOM. But note: the current streaming implementation drops reject data from non-first chunks (known bug in PROJECT.md). Fix this before relying on streaming for production.

**If Arrow type conversion fails (decimal/timestamp):**
- Use explicit `_build_arrow_schema()` (already implemented in bridge.py)
- Because: the existing implementation correctly handles Decimal inference. For timestamps, ensure `datetime64[ns]` pandas dtype before Arrow conversion -- Arrow defaults to `timestamp('ns')` which is correct for Talend date patterns.

**If iterate components need to re-execute downstream subjobs:**
- Use the existing `_execute_iterate_component()` pattern with proper state cleanup
- Because: the iterate loop already handles clearing `data_flows`, resetting `executed_components`, and clearing `triggered_components` between iterations. Key fix needed: ensure globalMap sync with Java bridge happens per-iteration.

## Version Compatibility Matrix

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pandas 2.2.3 | pyarrow 15.0.2, numpy 1.26.x | Verified compatible. pandas 2.2 explicitly supports pyarrow 14-17. |
| pyarrow 15.0.2 (Python) | Arrow Java 15.0.2 | Same release version. IPC format is backward-compatible but matching versions eliminates decimal128 precision edge cases. |
| py4j 0.10.9.9 (Python) | py4j 0.10.9.7 (Java JAR) | Cross-compatible within 0.10.9.x line. Python side gets retry-on-empty-response fix without changing Java JAR. |
| Groovy 3.0.21 | Java 11, Java 17 | Groovy 3.0.x works with Java 11-17. Groovy 4.0+ needed for Java 21. |
| oracledb 3.4.2 | Oracle DB 12c, 18c, 19c, 21c, 23ai | Thin mode (no Oracle Client) works with 12c+. Thick mode extends range. |
| numpy 1.26.4 | pandas 2.2.x, pyarrow 15.x | Last numpy 1.x release. numpy 2.0+ has breaking C API changes that affect some pyarrow operations. |
| pytest 8.3.4 | Python 3.10-3.13 | Fully compatible. No special configuration needed. |

## Critical Gap: Missing pyproject.toml

The project has **no dependency management file**. All Python dependencies are implicit. This is a production risk.

**Recommended pyproject.toml structure:**

```toml
[project]
name = "dataprep"
version = "1.0.0"
requires-python = ">=3.10"

dependencies = [
    "pandas>=2.2.0,<3.0.0",
    "pyarrow==15.0.2",
    "py4j>=0.10.9.9,<0.11",
    "numpy>=1.26.0,<2.0.0",
    "oracledb>=3.4.0,<4.0.0",
    "openpyxl>=3.1.0,<4.0.0",
    "xlrd>=2.0.1,<3.0.0",
    "lxml>=5.0.0,<6.0.0",
    "PyYAML>=6.0,<7.0",
    "jsonpath-ng>=1.6.0,<2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-cov>=5.0,<6.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

## Key Decisions for This Milestone

### 1. Pin pandas to 2.2.x (HIGH confidence)

**Decision:** Do NOT upgrade to pandas 3.0 during this milestone.

**Rationale:** Pandas 3.0 changes two fundamental behaviors:
- **Copy-on-Write default:** Every indexing operation returns a copy. Code like `df['col'][mask] = value` silently fails. The engine uses chained assignment in multiple components.
- **Arrow-backed string inference:** String columns get `ArrowDtype(string)` instead of `object` dtype. This breaks type comparisons, `isinstance()` checks, and the `validate_schema()` type mapping in base_component.py.

**Migration plan:** After this milestone, upgrade to pandas 2.3.x first (to get deprecation warnings), fix all warnings, then move to 3.0.

### 2. Upgrade Py4J Python to 0.10.9.9, keep Java at 0.10.9.7 (HIGH confidence)

**Decision:** Asymmetric version upgrade.

**Rationale:** Py4J 0.10.9.9 adds retry-on-empty-response handling which directly addresses the bridge reliability issues. The Python and Java sides of Py4J are protocol-compatible within the 0.10.9.x line. Upgrading only the Python pip package requires zero changes to the Java pom.xml or JAR rebuild.

### 3. Keep Arrow versions aligned at 15.0.2 (HIGH confidence)

**Decision:** Do not upgrade Arrow independently on either side.

**Rationale:** Arrow IPC format is backward-compatible, but decimal128 precision handling and timestamp formatting have had subtle cross-version issues (GitHub issues #61464, #37545). Matching versions eliminates this entire class of bugs. Upgrade both sides together in a future milestone when Decimal32/64 or IPC compression is needed.

### 4. Use oracledb instead of cx_Oracle (HIGH confidence)

**Decision:** Use `oracledb` 3.4.2 for all Oracle components.

**Rationale:** cx_Oracle is officially obsolete. oracledb is the official Oracle-maintained successor with API compatibility. Thin mode (default) eliminates the Oracle Client dependency for development/testing. Thick mode available for production if Oracle Client libraries are present.

### 5. Use graphlib.TopologicalSorter for engine execution ordering (MEDIUM confidence)

**Decision:** Replace the current BFS queue execution loop with `graphlib.TopologicalSorter`.

**Rationale:** The current execution loop in engine.py (lines 394-536) uses a BFS queue with manual `can_execute()` checks and re-scanning all components after each execution. This is O(n^2) and error-prone. Python's stdlib `graphlib.TopologicalSorter` (available since 3.9) provides `prepare()` / `get_ready()` / `done()` / `is_active()` which is purpose-built for this pattern. It handles cycle detection, ready-node tracking, and supports the iterate re-execution pattern by creating a new sorter per iteration.

**Risk:** The iterate component pattern (re-executing downstream subjobs) requires creating a fresh TopologicalSorter for each iteration's subgraph, which needs careful implementation.

### 6. Create pyproject.toml (HIGH confidence)

**Decision:** Add dependency management immediately.

**Rationale:** Zero dependency management in a production system is a deployment hazard. Any `pip install` could pull incompatible versions. This is the first task of the milestone.

## Sources

- [pyarrow on PyPI](https://pypi.org/project/pyarrow/) -- verified latest version 23.0.1 (Feb 2026); project uses 15.0.2
- [pandas release notes](https://pandas.pydata.org/docs/whatsnew/index.html) -- verified 3.0.2 latest (Mar 2026); recommended 2.2.3
- [pandas 3.0 what's new](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) -- verified Copy-on-Write and string dtype changes
- [pandas migration guide for strings](https://pandas.pydata.org/pandas-docs/stable/user_guide/migration-3-strings.html) -- Arrow-backed string migration details
- [py4j changelog](https://www.py4j.org/changelog.html) -- verified 0.10.9.9 adds retry-on-empty-response (Jan 2025)
- [py4j on PyPI](https://pypi.org/project/py4j/) -- verified 0.10.9.9 latest
- [py4j advanced topics](https://www.py4j.org/advanced_topics.html) -- timeout and callback configuration
- [python-oracledb](https://oracle.github.io/python-oracledb/) -- verified 3.4.2 latest, cx_Oracle obsolete
- [oracledb on PyPI](https://pypi.org/project/oracledb/) -- version history and compatibility
- [Apache Arrow format versioning](https://arrow.apache.org/docs/format/Versioning.html) -- IPC backward compatibility guarantees
- [Arrow IPC Python docs](https://arrow.apache.org/docs/python/ipc.html) -- streaming format, RecordBatchStreamWriter
- [Arrow Python-Java integration](https://arrow.apache.org/docs/python/integration/python_java.html) -- C Data Interface, JPype approach
- [pandas decimal/float issues #61464](https://github.com/pandas-dev/pandas/issues/61464) -- pyarrow >=18.0.0 decimal roundtrip issues
- [Arrow date_as_object #37545](https://github.com/apache/arrow/issues/37545) -- timestamp precision changes across versions
- [Groovy 4.0 release notes](https://groovy-lang.org/releasenotes/groovy-4.0.html) -- groupId change confirmed
- [Python graphlib docs](https://docs.python.org/3/library/graphlib.html) -- TopologicalSorter API for DAG execution
- [pandas scaling guide](https://pandas.pydata.org/docs/user_guide/scale.html) -- chunked processing patterns
- [structlog](https://www.structlog.org/) -- structured logging for production ETL

---
*Stack research for: Python ETL Engine with Java Interop (Talend Migration)*
*Researched: 2026-04-14*
