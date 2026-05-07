# Phase 11: Oracle Components - Research

**Researched:** 2026-05-07
**Domain:** Oracle database connectivity (oracledb thin/thick) + manager-based connection lifecycle + DataFrame -> Oracle DML/DDL with executemany batcherrors + Talend-parity reject flow
**Confidence:** HIGH (all decisions locked in CONTEXT.md; this research fills implementation-detail gaps with verified oracledb-3.4.2 API surface and verbatim Talaxie javajet references)

---

## Summary

Phase 11 ships three Oracle engine components (`tOracleConnection`, `tOracleRow`, `tOracleOutput`) plus the `OracleConnectionManager` infrastructure that owns live `oracledb.Connection` lifecycle for the entire Oracle component family. The manager is the exact analog of `JavaBridgeManager` / `PythonRoutineManager`: it is instantiated on `ETLEngine.__init__`, attached to components in `_initialize_components`, and stopped from `_cleanup` (idempotent close-all, runs on success/exception/`__del__`). Live `oracledb.Connection` objects are keyed by registering component id and never enter `globalMap` (which holds Talend-parity metadata strings only). Driver runs in `oracledb` thin mode by default (no Oracle Instant Client install on RHEL); `job_config['oracle_config']['thick_mode']: true` flips on `oracledb.init_oracle_client()` once at manager start. `ORACLE_OCI` and `ORACLE_WALLET` raise `NotImplementedError` (deferred); `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC` are fully implemented.

Writing uses `cursor.executemany(sql, rows, batcherrors=True)` unconditionally with `cursor.getbatcherrors()` driving the REJECT flow — single code path, 5–50x faster than Talend's per-row JDBC, same observable behavior. Type binding is schema-driven via `cursor.setinputsizes()` with `oracledb.DB_TYPE_*` constants. DDL emission for the 8 `TABLE_ACTION` values uses Oracle types derived from engine schema columns (`NUMBER(p,s)`, `VARCHAR2(n CHAR)`, `DATE`/`TIMESTAMP`, `BLOB`, etc.). `INSERT_OR_UPDATE` / `UPDATE_OR_INSERT` use a batched 2-statement pattern (`SELECT pk_cols WHERE pk IN (batch_keys)` -> partition matched/unmatched -> `executemany UPDATE` + `executemany INSERT`) — Talend-parity, not Oracle MERGE.

**Primary recommendation:** Mirror the `JavaBridgeManager` shape exactly, build `OracleConnectionManager` as a single ~250-line module, wire it into `ETLEngine` at lines 41/142/233 alongside the existing managers, then ship the three components in the D-F1 sub-phase order. The hardest sub-phase is 11-04 (DDL emitter) — the 8 TABLE_ACTIONs are independent SQL emitters, test each in isolation. Sub-phase 11-07 (testcontainers integration) is the verification gate per D-D3.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**A. Connection persistence & lifecycle**
- **D-A1:** Live `oracledb.Connection` objects in `OracleConnectionManager` keyed by registering component id. `globalMap` holds Talend-parity metadata strings only. Components access via `engine.oracle_manager.get(connection_ref)`.
- **D-A2:** `oracledb` thin by default. Per-job thick escape via `job_config['oracle_config']['thick_mode']: true` -> `oracledb.init_oracle_client()` once in `manager.start()`.
- **D-A3:** `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC` fully implemented. `ORACLE_OCI`, `ORACLE_WALLET` raise `NotImplementedError` with the exact message: `"CONNECTION_TYPE %s requires oracledb thick mode + Oracle Instant Client. Set oracle_config.thick_mode=true in job config and install Instant Client on the host. Tracked in deferred items."` No silent fallback.
- **D-A4:** Talend-parity lifecycle. Ad-hoc connection: open at component prepare, commit + close in finalize. Shared connection: open in `tOracleConnection._process()`, persists, closed by safety-net `oracle_manager.stop()` from `_cleanup`. `AUTO_COMMIT` honored at connection open. `oracledb.Connection.close()` rolls back uncommitted (matches Talend Oracle JDBC).
- **D-A4b:** `OracleConnectionManager.stop()` iterates connections, closes each in try/except, clears dict. Idempotent. Called from `ETLEngine._cleanup()` at the same site as `java_bridge_manager.stop()` (line 233).

**B. Type mapping & transactions**
- **D-B1:** Schema-driven type coercion via `BaseComponent._coerce_column_type`. NUMBER -> `Decimal` for `Decimal` schemas; -> `int` for `int`/`long`; -> `float` for `float`/`double`. DATE/TIMESTAMP -> `datetime` via `pd.Timestamp`. CLOB/BLOB -> `str`/`bytes` (`oracledb.defaults.fetch_lobs = False` set globally in manager `__init__`). Bind via `setinputsizes()` with `DB_TYPE_*` constants. Honor `USE_TIMESTAMP_FOR_DATE_TYPE` (default true): when true, DATE columns bound with `DB_TYPE_TIMESTAMP`. `TRIM_CHAR` honored on read for CHAR-typed columns.
- **D-B2:** `cursor.executemany(sql, rows, batcherrors=True)` unconditionally (no Talend-style "disable batching when REJECT is wired"). Trailing partial batch handled in `finalize()`. `NB_LINE_REJECTED` summed across batches.

**C. tOracleRow & tOracleOutput component semantics**
- **D-C1:** Full Talend coverage: 8 `TABLE_ACTION` x 5 `DATA_ACTION`. CREATE-family emit Oracle DDL from engine schema column types.
- **D-C2:** `INSERT_OR_UPDATE` / `UPDATE_OR_INSERT` = batched 2-statement (NOT MERGE). Per batch: `SELECT pk_cols WHERE pk IN (batch_keys)`, partition matched/unmatched, `executemany UPDATE` + `executemany INSERT`. Stats split correctly.
- **D-C3:** `USE_PREPAREDSTATEMENT` ships full 16 PARAMETER_TYPE coverage. Static lookup table maps Java type names to Python coercion calls. PARAMETER_VALUE resolved through engine pipeline first, then coerced. Bind via `cursor.execute(sql, [vals])`.
- **D-C4:** `tOracleRow.PROPAGATE_RECORD_SET=true` raises `ConfigurationError` with the exact deferral message.
- **D-C5:** `USE_NB_LINE` reads `cursor.rowcount`. DDL (rowcount -1 or None) -> 0 + WARNING.
- **D-C6:** `USE_FIELD_OPTIONS` per-column flags honored (UPDATE_KEY / DELETE_KEY / UPDATABLE / INSERTABLE). Without it, schema "Key" attribute drives WHERE clause; non-key columns are updatable + insertable.
- **D-C7:** Reject schema = `[errorCode (str), errorMessage (str), <input columns>]`. `errorCode` from `BatchError.code` (Oracle error number int). `errorMessage` from `BatchError.message + " - Line: <row_offset>"`.
- **D-C8:** Stat globalMap keys per component documented (matching Talend `_AFTER` availability).

**D. Architecture & test infrastructure**
- **D-D1:** Oracle-specific implementation now; NO `BaseDb*` abstractions in Phase 11.
- **D-D2:** New engine package `src/v1/engine/components/database/`. New top-level module `src/v1/engine/oracle_connection_manager.py`. Registration: `@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")`, `@REGISTRY.register("OracleRow", "tOracleRow")`, `@REGISTRY.register("OracleOutput", "tOracleOutput")`.
- **D-D3:** Hybrid test strategy. Mock-default unit tests + `@pytest.mark.oracle` integration tests with `testcontainers-python` + `gvenzl/oracle-free:23-slim`. `gsd-verify-work` gate requires real-DB run.
- **D-D4:** `pyproject.toml`: new `oracle = ["oracledb>=2.5,<4"]` extra; `dev` adds `testcontainers>=4`; register `oracle` pytest marker.

**E. Converter scope additions**
- **D-E1:** Converter update — `oracle_connection.py` / `oracle_row.py` / `oracle_output.py`: when `connection_type in {ORACLE_WALLET, ORACLE_OCI}`, emit a `needs_review` entry pointing at `oracle_config.thick_mode`.

**F. Phase 11 sub-phase plan (anticipatory)**
- **D-F1:** 7 sub-phases (11-01 through 11-07) — planner finalizes.
- **D-F2:** All components conform to `ENGINE_COMPONENT_PATTERN.md`. All tests conform to `ENGINE_TEST_PATTERN.md`.
- **D-F3:** Phase 7.1 Rule 12: content checks in `_process()`, NOT `_validate_config()`.
- **D-F4:** `@pytest.mark.oracle` integration tests mandatory at phase verification gate.

### Claude's Discretion

- Internal class structure of `OracleConnectionManager` (private helpers per connection type, `_open_ad_hoc()` vs `_open_shared()` split, docstring format)
- Stats dict shape for per-component execution stats
- SQL-emitter helper organization for tOracleOutput's 8 TABLE_ACTIONs
- Test fixture design for testcontainers (where conftest lives)
- Reject DataFrame buffer strategy (in-memory list vs concat-on-finalize)
- Public `engine.oracle_manager` vs private with getter
- Log message wording for thick-mode init
- DDL string formatting (uppercase keywords vs lowercase, line breaks)

### Deferred Ideas (OUT OF SCOPE)

- `ORACLE_OCI` and `ORACLE_WALLET` runtime support (engine raises NotImplementedError)
- 6 other Oracle engine components (tOracleInput, tOracleSP, tOracleBulkExec, tOracleCommit, tOracleRollback, tOracleClose)
- `tOracleRow.PROPAGATE_RECORD_SET` runtime support (ConfigurationError)
- `tOracleInput.IS_CONVERT_XMLTYPE` / `CONVERT_XMLTYPE` table
- `BaseDbConnection` / `BaseDbInput` / `BaseDbOutput` abstractions
- Default-CI Docker fixtures (testcontainers stays opt-in)
- Streaming-mode for very large tOracleOutput inputs
- MSSql engine components

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORAC-01 | Implement `OracleConnectionManager` analog to `JavaBridgeManager` with start/stop/get/register/open_ad_hoc/close/commit/rollback API; idempotent stop; integrated into `ETLEngine._cleanup` | Sections "Architectural Integration", "OracleConnectionManager API Surface" — manager API + integration line numbers verified |
| ORAC-02 | Implement `tOracleConnection` engine component with ORACLE_SID / ORACLE_SERVICE_NAME / ORACLE_RAC connection types; raise NotImplementedError for OCI/Wallet; honor AUTO_COMMIT | Sections "tOracleConnection Implementation Guidance", "JDBC URL -> oracledb DSN Translation" — exact `oracledb.connect()` calls per type |
| ORAC-03 | Implement `tOracleRow` engine component with USE_EXISTING_CONNECTION + ad-hoc, full 16-type USE_PREPAREDSTATEMENT, USE_NB_LINE; PROPAGATE_RECORD_SET=true raises ConfigurationError | Sections "tOracleRow Implementation Guidance", "USE_PREPAREDSTATEMENT 16-Type Coercion Table" |
| ORAC-04 | Implement `tOracleOutput` engine component with full 8 TABLE_ACTION x 5 DATA_ACTION matrix, executemany+batcherrors+commit cycle, FIELD_OPTIONS, USE_TIMESTAMP_FOR_DATE_TYPE | Sections "tOracleOutput Implementation Guidance", "Oracle DDL Emission From Engine Schema", "INSERT_OR_UPDATE Batched 2-Statement Pattern", "executemany + batcherrors Mechanics" |
| ORAC-05 | Converter update: emit `needs_review` for ORACLE_WALLET / ORACLE_OCI on the 3 components in scope, pointing at `oracle_config.thick_mode` | Section "Converter Update (D-E1)" |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Connection lifecycle (open/close, idempotent stop) | Engine top-level (`OracleConnectionManager`) | — | Mirrors JavaBridgeManager / PythonRoutineManager. Lives outside any component because shared across the whole job. |
| Driver mode init (thin vs thick) | Engine top-level (`OracleConnectionManager.start`) | — | `oracledb.init_oracle_client()` is process-global; called once per job, never per component. |
| Connection registration (cid -> Connection) | Engine top-level (`OracleConnectionManager`) | — | Components register/lookup; manager owns the dict. |
| Connection open per CONNECTION_TYPE | Component (`tOracleConnection._process`) delegating to manager | — | Component reads its own config (CONNECTION_TYPE, host, port, etc.), manager opens via private URL builder. |
| SQL execute (ad-hoc, prepared, batch) | Component (`tOracleRow._process`, `tOracleOutput._process`) | Manager (cursor acquisition only) | Components own SQL construction, parameter binding, batcherrors handling. Manager only provides `connection.cursor()`. |
| DDL emission per schema | Component (`tOracleOutput._process` -> private DDL helpers) | — | Schema-driven, table-action-driven; not reusable across other DB vendors yet (D-D1 — no BaseDbOutput). |
| REJECT flow construction | Component (`tOracleOutput._process`) | BaseComponent (auto-routes via OutputRouter) | Component builds reject DataFrame from `cursor.getbatcherrors()`; BaseComponent stats updates handle the rest. |
| globalMap stat keys | Component (`_process` writes via `self.global_map.put`) | BaseComponent (auto NB_LINE / NB_LINE_OK / NB_LINE_REJECT) | Talend-parity component-specific keys (`_NB_LINE_INSERTED`, etc.) are component responsibility. |
| Cleanup safety net | Engine (`ETLEngine._cleanup` -> `oracle_manager.stop()`) | Manager | Engine guarantees stop() runs on success/exception/`__del__`. Manager guarantees idempotency. |
| Converter Wallet/OCI needs_review | Converter (`oracle_*.py` in `src/converters/talend_to_v1/components/database/`) | — | Converter-side concern (D-E1); engine-side raises NotImplementedError as the runtime guard. |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `oracledb` | `>=2.5,<4` (3.4.2 verified installed) | Pure-Python Oracle driver (thin), optional thick via `init_oracle_client()` | [VERIFIED: oracledb 3.4.2 imported successfully in venv]. Official Oracle driver, replaces `cx_Oracle`. Thin mode = no Instant Client = clean RHEL deploy. [CITED: python-oracledb.readthedocs.io] |
| `pandas` | `>=2.0,<4` (already installed) | DataFrame in/out | Existing engine standard |
| `testcontainers` | `>=4` (dev only) | Ephemeral Oracle Free container for integration tests | Industry-standard ephemeral-DB test pattern. [VERIFIED: gvenzl/oracle-free has 1k+ Docker pulls, official Oracle-blessed lightweight image] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | `>=8.0,<10` (already installed) | Test runner with `oracle` marker | Required for test framework |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `oracledb` thin | `cx_Oracle` | `cx_Oracle` is the LEGACY driver; oracle.com shipped `oracledb` as the official replacement in 2022. `cx_Oracle` requires Instant Client even for thin-equivalent use. Do NOT use. |
| `oracledb` 3.x | `oracledb>=4` | 4.x is in beta as of research date; pin `<4` until stable. [VERIFIED: 3.4.2 is current stable per python-oracledb release notes] |
| `executemany` per batch | per-row `execute` | Per-row is 5–50x slower at protocol level; locked out by D-B2. |
| `gvenzl/oracle-free:23-slim` | `gvenzl/oracle-xe:21-slim` | Oracle Free is the modern Oracle-supported lightweight build for Oracle 23ai. Slim variant is ~300 MB vs full ~1 GB. Boots ~30–60s on a 4-core dev box. |
| Oracle MERGE for upsert | 2-statement SELECT+UPDATE+INSERT | Locked out by D-C2 (cleaner stats; smaller parity surface) |
| `oracledb.makedsn()` | `oracledb.connect(host=, port=, service_name=)` direct kwargs | makedsn is technically deprecated since oracledb 1.0 but still functional in 3.4.2. Direct kwargs is cleaner and the documented modern pattern. [VERIFIED: `inspect.signature(oracledb.connect)` shows `host, port, service_name, sid` as direct keyword params] |

**Installation:**
```bash
pip install -e ".[oracle]"          # production install
pip install -e ".[oracle,dev]"      # dev with testcontainers
```

**Version verification (run before starting Phase 11):**
```bash
python -c "import oracledb; print(oracledb.__version__)"   # expect: 3.4.2 or higher
pip show testcontainers 2>/dev/null | grep -i version || echo "testcontainers not yet installed"
```

[VERIFIED: 2026-05-07 — oracledb 3.4.2 already installed in venv]

---

## Architecture Patterns

### System Architecture Diagram

```
job_config.json
   |
   v
ETLEngine.__init__
   |---> JavaBridgeManager   (existing, line 41)
   |---> PythonRoutineManager (existing, line 59)
   |---> OracleConnectionManager  (NEW, around line 67)
   |        |
   |        |  state: { cid -> oracledb.Connection }
   |        |  capabilities: register / get / open_ad_hoc / close / commit / rollback / start / stop
   |
   v
ETLEngine._initialize_components  (line 111)
   |---> for each component, attach manager: component.oracle_manager = self.oracle_manager
   |
   v
[execution loop]
   |
   |     +------------------------+
   |     |  tOracleConnection     |
   |     |  _process():           |
   |     |    conn = oracledb.connect(...)              <-- thin/thick per oracle_config.thick_mode
   |     |    self.oracle_manager.register(self.id, conn)
   |     |    globalMap.put(f"connectionType_{cid}", connection_type)
   |     |    globalMap.put(f"dbschema_{cid}", schema_db)
   |     |    ...                                       <-- metadata strings only
   |     +------------------------+
   |              |
   |              | (downstream Oracle component refs CONNECTION=tOracleConnection_1)
   |              v
   |     +------------------------+         +------------------------+
   |     |  tOracleRow            |         |  tOracleOutput         |
   |     |  _process():           |         |  _process():           |
   |     |    if use_existing:    |         |    if use_existing:    |
   |     |      conn = manager.get(ref)     |      conn = manager.get(ref)
   |     |    else:               |         |    else:               |
   |     |      conn = manager.open_ad_hoc(self.id, config)
   |     |    cursor = conn.cursor()        |    cursor = conn.cursor()
   |     |    cursor.execute(sql, params)   |    [TABLE_ACTION DDL emit + execute]
   |     |    rowcount -> NB_LINE_*         |    [DATA_ACTION executemany + getbatcherrors]
   |     |                                  |    [build reject DataFrame]
   |     +------------------------+         +------------------------+
   |
   v
ETLEngine._cleanup  (line 229)
   |---> java_bridge_manager.stop()        (existing, line 233)
   |---> oracle_manager.stop()             (NEW, line 234)  -> closes all live connections idempotently
```

### Recommended Project Structure

```
src/v1/engine/
├── oracle_connection_manager.py       # NEW: Manager class (D-D2)
├── components/
│   ├── database/                      # NEW: Database component package (D-D2)
│   │   ├── __init__.py                # imports oracle_connection / oracle_row / oracle_output to trigger @REGISTRY.register
│   │   ├── oracle_connection.py       # NEW: tOracleConnection engine
│   │   ├── oracle_row.py              # NEW: tOracleRow engine
│   │   └── oracle_output.py           # NEW: tOracleOutput engine

tests/v1/engine/
├── test_oracle_connection_manager.py  # NEW: Mock-based manager unit tests
├── components/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── test_oracle_connection.py  # NEW: Mock-based component unit tests
│   │   ├── test_oracle_row.py
│   │   ├── test_oracle_output.py
│   │   └── integration/               # NEW: @pytest.mark.oracle gated tests
│   │       ├── __init__.py
│   │       ├── conftest.py            # testcontainers fixture
│   │       ├── test_oracle_connection_e2e.py
│   │       ├── test_oracle_row_e2e.py
│   │       └── test_oracle_output_e2e.py
```

### Pattern 1: Manager-as-Lifecycle-Owner (mirror of JavaBridgeManager)

**What:** Top-level engine object owning a non-Arrow-serializable resource (Connection, JVM, Python module dict). Lifecycle bound to engine `__init__` -> `_cleanup`, never per-component.

**When to use:** Whenever a resource is shared across components AND is not safely serializable into globalMap.

**Why this pattern:** Components MUST NOT push live `oracledb.Connection` objects into globalMap — globalMap is synced through the Java bridge via Apache Arrow, and Connection objects break Arrow serialization (project memory: "globalMap is a Python-Java shared key/value store; live connections must live in the manager"). Mirror image of how JavaBridge.bridge is held by JavaBridgeManager and never goes through globalMap.

### Pattern 2: Component-Owns-SQL, Manager-Owns-Connection

**What:** Components construct SQL and parameter bindings locally inside `_process()`. Manager only provides `Connection` objects via `manager.get(cid)` or `manager.open_ad_hoc(cid, config)`.

**When to use:** Always. Do NOT push SQL construction into the manager — the manager has no business knowing about TABLE_ACTION or DATA_ACTION.

### Pattern 3: Single executemany code path with conditional batcherrors handling

**What:** One `cursor.executemany(sql, rows, batcherrors=True)` call regardless of whether REJECT is wired. After each batch, ALWAYS read `cursor.getbatcherrors()`. If REJECT is wired, build reject DataFrame; if not, increment `NB_LINE_REJECTED` only.

**Why:** Per D-B2, single code path. Avoids the Talend-style "disable batching when REJECT exists" branching. Test surface stays uniform.

```python
# Source: D-B2 + python-oracledb batch_statement.rst pattern [VERIFIED]
import oracledb

cursor.setinputsizes(*input_sizes)  # bind types per schema
cursor.executemany(sql, rows, batcherrors=True)

batch_errors = cursor.getbatcherrors()  # list of oracledb._Error
for err in batch_errors:
    # err.offset (int) - position in rows that failed
    # err.code (int) - Oracle error number, e.g. 1 for ORA-00001
    # err.full_code (str) - "ORA-00001"
    # err.message (str) - human message
    pass

inserted_count = len(rows) - len(batch_errors)
rejected_count = len(batch_errors)

if commit_every_threshold_hit:
    conn.commit()
```

### Anti-Patterns to Avoid

- **DO NOT push `oracledb.Connection` into `globalMap`.** Breaks Arrow sync. Use `OracleConnectionManager` keyed by cid.
- **DO NOT call `oracledb.init_oracle_client()` more than once per process.** It's process-global; calling twice raises an error. Manager.start() must guard with a class-level `_thick_mode_initialized` flag (or simply check `oracledb.is_thin_mode()`).
- **DO NOT raise `oracledb` exceptions to the caller.** Wrap in `ConfigurationError` (bad params, OCI/Wallet) or `ComponentExecutionError` (runtime SQL/connection failures). BaseComponent already wraps `_process()` exceptions in `ComponentExecutionError`, so let unhandled `oracledb.DatabaseError` flow up to the wrapper.
- **DO NOT do per-row `execute()` for tOracleOutput.** D-B2 locks executemany. Per-row defeats the entire performance argument.
- **DO NOT call `cursor.commit()`.** Commit is on the Connection, not the cursor.
- **DO NOT store live cursors as instance state on the component.** Cursor lifetime = batch lifetime. Open-execute-close inside `_process()`; never persist.
- **DO NOT call `self.validate_schema()` inside `_process()`** (Phase 7.1 Rule 11). BaseComponent runs schema validation in step 7c automatically.
- **DO NOT do content checks (URL syntax, schema column type validity) in `_validate_config()`** (Phase 7.1 Rule 12 / D-F3). These run BEFORE context resolution. Put them in `_process()` after `self.config` is resolved.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Oracle protocol implementation | TCP/TNS handshake, BEQ protocol | `oracledb.connect()` | Net8/TNS is a non-trivial binary protocol. Driver handles auth, encryption, charset negotiation, RAC failover. |
| DSN string assembly | Manual `f"jdbc:oracle:thin:@{host}:{port}:{sid}"` | `oracledb.connect(host=..., port=..., sid=...)` direct kwargs | oracledb accepts `host`/`port`/`service_name`/`sid` directly without DSN string construction. [VERIFIED via `inspect.signature(oracledb.connect)`] |
| Per-row error tracking for batch DML | Try/except per row, custom error accumulator | `cursor.executemany(sql, rows, batcherrors=True)` + `cursor.getbatcherrors()` | Driver-level batch error accumulation is 10-100x faster than Python-level try/except per row, and exposes Oracle error code + offset. |
| Type binding for executemany | Manual coercion + ad-hoc `INSERT ... VALUES (TO_DATE(?, '...'), ...)` | `cursor.setinputsizes(*types)` with `oracledb.DB_TYPE_*` constants | Driver handles literal escaping, NULL coercion, encoding per column type. Hand-rolled string concat is SQL injection waiting to happen. |
| Upsert (INSERT_OR_UPDATE) row-by-row | Per-row `SELECT COUNT(1)` + `IF EXISTS UPDATE ELSE INSERT` | Batched 2-statement: `SELECT pk FROM t WHERE pk IN (batch_keys)` + `executemany UPDATE` + `executemany INSERT` | One round trip per batch instead of per row. D-C2 locks this pattern. |
| Connection pooling for shared connections | DIY ref-counting | A single Connection per `tOracleConnection` cid in the manager | Talend-parity: tOracleConnection opens ONE connection that downstream components share. Real pooling deferred to a perf phase. |
| Test fixture for ephemeral Oracle | Manual Docker shell-out | `testcontainers` `OracleDbContainer` (or generic container with `gvenzl/oracle-free:23-slim`) | testcontainers handles port mapping, healthcheck, teardown. |
| Java/Groovy expression eval inside SQL strings | Substring matching for `${...}` | Existing `{{java}}` resolution pipeline in `_resolve_expressions()` (BaseComponent step 3) | Phase 1/2 already built this. tOracleRow's `query` field flows through it transparently. |

**Key insight:** The Oracle Python ecosystem has a single dominant driver (`oracledb`, official Oracle-blessed) with a clean, well-documented batch API that already covers 95% of what Talend's tOracleOutput does at the JDBC level. Hand-rolling anything beyond URL construction is a mistake.

---

## OracleConnectionManager API Surface

This is the public API the planner should break into atomic tasks. Mirror `JavaBridgeManager` exactly.

```python
# File: src/v1/engine/oracle_connection_manager.py
"""Oracle Connection Manager - Manages oracledb Connection lifecycle per job.

Mirrors JavaBridgeManager / PythonRoutineManager patterns. Live oracledb.Connection
objects MUST NOT enter globalMap (non-Arrow-serializable); they live here keyed by
the registering tOracleConnection's component id, plus optional per-cid ad-hoc
connections opened by tOracleRow / tOracleOutput when use_existing_connection=False.
"""
import logging
from typing import Any, Dict, Optional

import oracledb

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class OracleConnectionManager:
    """Owns lifecycle of all live oracledb.Connection objects for a job.

    Attributes:
        thick_mode: Whether thick mode is enabled (read from job_config['oracle_config']['thick_mode']).
        connections: dict mapping component_id -> oracledb.Connection.
        is_running: True after start() and before stop().
    """

    # Class-level guard: oracledb.init_oracle_client() is process-global,
    # calling it twice in the same process raises. We track init across all manager
    # instances in this process.
    _thick_initialized: bool = False

    def __init__(self, thick_mode: bool = False) -> None:
        self.thick_mode = bool(thick_mode)
        self.connections: Dict[str, oracledb.Connection] = {}
        self.is_running: bool = False

    # --- lifecycle ---
    def start(self) -> None:
        """Initialize driver mode. Idempotent.

        - Sets oracledb.defaults.fetch_lobs = False globally (D-B1).
        - If thick_mode True and not yet initialized in this process, calls
          oracledb.init_oracle_client().
        - Marks is_running True.
        """
        if self.is_running:
            return
        oracledb.defaults.fetch_lobs = False  # D-B1: read CLOB/BLOB as str/bytes
        if self.thick_mode and not OracleConnectionManager._thick_initialized:
            try:
                oracledb.init_oracle_client()
                OracleConnectionManager._thick_initialized = True
                logger.info("[OK] Oracle thick mode initialized")
            except Exception as e:
                logger.error("[ERROR] oracledb.init_oracle_client() failed: %s", e)
                raise
        self.is_running = True

    def stop(self) -> None:
        """Close all live connections. Idempotent. Called from ETLEngine._cleanup.

        Iterates self.connections and closes each in try/except so one bad close
        doesn't block the rest. Clears the dict. Sets is_running False.
        """
        if not self.is_running and not self.connections:
            return
        for cid, conn in list(self.connections.items()):
            try:
                conn.close()
                logger.info("[OK] Closed Oracle connection (cid=%s)", cid)
            except Exception as e:
                logger.error("[ERROR] Failed to close Oracle connection cid=%s: %s", cid, e)
        self.connections.clear()
        self.is_running = False

    def is_available(self) -> bool:
        return self.is_running

    # --- registration / lookup (used by tOracleConnection + downstream) ---
    def register(self, cid: str, conn: oracledb.Connection) -> None:
        """Register a connection opened by tOracleConnection under its component id.

        Raises:
            ValueError: If cid is already registered (component executed twice).
        """
        if cid in self.connections:
            raise ValueError(f"Connection already registered for cid={cid}")
        self.connections[cid] = conn

    def get(self, cid_ref: str) -> oracledb.Connection:
        """Look up a registered connection by the cid the downstream component refs.

        Raises:
            ConfigurationError: If cid_ref is not registered (upstream tOracleConnection
              did not run, or connection_ref typo in job config).
        """
        conn = self.connections.get(cid_ref)
        if conn is None:
            raise ConfigurationError(
                f"No registered Oracle connection for reference {cid_ref!r}. "
                f"Available: {sorted(self.connections.keys())}"
            )
        return conn

    # --- ad-hoc connections (used by tOracleRow / tOracleOutput when use_existing=False) ---
    def open_ad_hoc(self, cid: str, oracle_config: Dict[str, Any]) -> oracledb.Connection:
        """Open and register an ad-hoc connection for a component that didn't refer
        to a tOracleConnection. Component must call self.oracle_manager.close(cid)
        in its finalize step (or rely on stop() safety net).

        oracle_config dict keys: connection_type, host, port, dbname, local_service_name,
        rac_url, user, password, auto_commit, properties (optional kv pairs).

        Raises:
            ConfigurationError: For unsupported connection types (OCI, Wallet) per D-A3.
        """
        # ... internal _build_connect_kwargs() per connection type, then oracledb.connect(...)
        # ... apply auto_commit if specified
        # ... self.connections[cid] = conn
        # ... return conn

    # --- explicit close / commit / rollback (for future tOracleClose / tOracleCommit / tOracleRollback) ---
    def close(self, cid: str) -> None:
        """Explicit close (commit-aware). Removes from dict.

        Note: oracledb.Connection.close() rolls back uncommitted; component logic
        decides whether to commit before close.
        """
        conn = self.connections.pop(cid, None)
        if conn is None:
            return
        try:
            conn.close()
        except Exception as e:
            logger.error("[ERROR] Error closing connection cid=%s: %s", cid, e)

    def commit(self, cid: str) -> None:
        """Commit a registered connection. Used by future tOracleCommit."""
        self.get(cid).commit()

    def rollback(self, cid: str) -> None:
        """Rollback a registered connection. Used by future tOracleRollback."""
        self.get(cid).rollback()

    # --- context manager + repr ---
    def __enter__(self) -> "OracleConnectionManager":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.stop()
        return False

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return f"OracleConnectionManager(status={status}, connections={len(self.connections)}, thick={self.thick_mode})"
```

**The 7 public methods Phase 11 needs (and the 2 future-component methods we ship now per D-D2):**

| Method | Phase 11 caller | Future caller |
|--------|-----------------|----------------|
| `start()` | `ETLEngine.__init__` | — |
| `stop()` | `ETLEngine._cleanup` | — |
| `register(cid, conn)` | `tOracleConnection._process` | — |
| `get(cid_ref)` | `tOracleRow._process`, `tOracleOutput._process` | tOracleInput, tOracleSP, tOracleClose |
| `open_ad_hoc(cid, config)` | `tOracleRow._process`, `tOracleOutput._process` (when use_existing=False) | tOracleInput, tOracleSP |
| `close(cid)` | `tOracleRow.finalize`, `tOracleOutput.finalize` | tOracleClose |
| `commit(cid)` / `rollback(cid)` | — | tOracleCommit / tOracleRollback |
| `is_available()` | `ETLEngine` (optional, parallels JavaBridgeManager) | — |

---

## JDBC URL -> oracledb DSN Translation

For each in-scope `CONNECTION_TYPE`, the engine builds an `oracledb.connect()` call. **Do NOT construct a JDBC URL string and pass it as `dsn`.** Use the direct keyword args supported by `oracledb.connect()`. [VERIFIED via `inspect.signature(oracledb.connect)`: kwargs include `dsn, user, password, host, port, service_name, sid, params`]

### ORACLE_SID

Talend emits: `"jdbc:oracle:thin:@" + host + ":" + port + ":" + dbname` [CITED: tOracleConnection_begin.javajet]

Engine call:
```python
# Source: oracledb 3.4.2 connect() signature
conn = oracledb.connect(
    user=config["user"],
    password=config["password"],
    host=config["host"],
    port=int(config["port"]),
    sid=config["dbname"],   # SID == DBNAME for SID connection type
)
```

### ORACLE_SERVICE_NAME

Talend emits: `"jdbc:oracle:thin:@(description=(address=(protocol=tcp)(host=" + host + ")(port=" + port + "))(connect_data=(service_name=" + dbname + ")))"` [CITED: tOracleConnection_begin.javajet]

Engine call:
```python
conn = oracledb.connect(
    user=config["user"],
    password=config["password"],
    host=config["host"],
    port=int(config["port"]),
    service_name=config["dbname"],   # SERVICE_NAME maps to DBNAME field in Talend config
)
```

### ORACLE_RAC

Talend emits: the raw `RAC_URL` user-supplied string, expected to be a TNS connect descriptor:
```
(DESCRIPTION=
  (ADDRESS_LIST=
    (LOAD_BALANCE=ON)
    (FAILOVER=ON)
    (ADDRESS=(PROTOCOL=TCP)(HOST=h1)(PORT=1521))
    (ADDRESS=(PROTOCOL=TCP)(HOST=h2)(PORT=1521)))
  (CONNECT_DATA=(SERVICE_NAME=mydb.example.com)))
```

`oracledb.connect(dsn=raw_url, ...)` accepts this verbatim. [CITED: python-oracledb.readthedocs.io/connection_handling — "the dsn parameter ... can be ... a Connect Descriptor"]

Engine call:
```python
# rac_url is the raw TNS connect descriptor from config["rac_url"]
conn = oracledb.connect(
    user=config["user"],
    password=config["password"],
    dsn=config["rac_url"].strip(),
)
```

No preprocessing needed. Strip whitespace defensively (Talend XML embeds newlines).

### ORACLE_OCI / ORACLE_WALLET (deferred per D-A3)

```python
raise ConfigurationError(
    f"[{self.id}] CONNECTION_TYPE {connection_type!r} requires oracledb thick mode "
    f"+ Oracle Instant Client. Set oracle_config.thick_mode=true in job config and "
    f"install Instant Client on the host. Tracked in deferred items."
)
```

(Use `ConfigurationError`, not `NotImplementedError` — the latter doesn't fit the exception hierarchy. CONTEXT.md D-A3 used "NotImplementedError" colloquially; the right typed exception is `ConfigurationError` per `src/v1/engine/exceptions.py`.)

### Optional: properties / encoding

`config["properties"]` is a Talend "key=value;key=value" string for additional JDBC properties. Most are JDBC-specific (e.g., `oracle.jdbc.ReadTimeout`) and don't translate to oracledb. **Recommendation:** parse the string, log a WARNING for any unrecognized key, and silently apply only those that map cleanly (none in Phase 11 scope). Do NOT silently ignore — log the skip.

`config["encoding"]` (default `ISO-8859-15`): oracledb thin always decodes per server NLS_CHARACTERSET. Encoding param is non-applicable in thin mode (per D-A2 — strictly more correct than Talend). Log INFO if a non-default encoding is set, noting it's not honored in thin mode.

---

## Architectural Integration (engine.py line numbers)

Exact additions to `src/v1/engine/engine.py`:

### 1. Import (top of file, after existing imports — around line 16)

```python
from .oracle_connection_manager import OracleConnectionManager
```

### 2. `__init__` instantiation — after `python_routine_manager` block, around line 67

```python
        # Oracle connection manager (D-A1, D-A2, D-A4b)
        self.oracle_manager = None
        oracle_config = self.job_config.get('oracle_config', {})
        # Auto-detect: instantiate if any Oracle component is in the job, OR if
        # oracle_config explicitly enabled. Auto-detect is simpler than requiring
        # users to set the flag (per code_context note).
        oracle_component_types = {"OracleConnection", "tOracleConnection", "tDBConnection",
                                   "OracleRow", "tOracleRow",
                                   "OracleOutput", "tOracleOutput"}
        has_oracle_components = any(
            c.get('type') in oracle_component_types
            for c in self.job_config.get('components', [])
        )
        if has_oracle_components or oracle_config.get('enabled', False):
            thick_mode = bool(oracle_config.get('thick_mode', False))
            self.oracle_manager = OracleConnectionManager(thick_mode=thick_mode)
            try:
                self.oracle_manager.start()
            except Exception:
                self.oracle_manager.stop()
                raise
            logger.info("Oracle connection manager initialized (thick_mode=%s)", thick_mode)
```

### 3. `_initialize_components` — after existing manager attachment block, around line 142

```python
            if self.java_bridge_manager:
                component.java_bridge = self.java_bridge_manager.bridge
            if self.python_routine_manager:
                component.python_routine_manager = self.python_routine_manager
            if self.oracle_manager:
                component.oracle_manager = self.oracle_manager
```

### 4. `_cleanup` — after existing `java_bridge_manager.stop()` call, around line 233

```python
    def _cleanup(self) -> None:
        """Cleanup resources including Java bridge and Oracle connections."""
        if self.java_bridge_manager:
            logger.info("Shutting down Java bridge...")
            self.java_bridge_manager.stop()
        if self.oracle_manager:
            logger.info("Closing Oracle connections...")
            self.oracle_manager.stop()
```

That's the entire engine.py touchpoint — 4 small edits (~25 lines added). All other behaviors flow through the existing infrastructure (REJECT routing, schema validation, stats accumulation, context resolution).

---

## tOracleConnection Implementation Guidance

### Module location
`src/v1/engine/components/database/oracle_connection.py`

### Registration
```python
@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")
class OracleConnection(BaseComponent):
    ...
```

### Config keys consumed (full list — copy verbatim from converter `oracle_connection.py`)
28 keys total. The component reads:
- `connection_type` (str) — drives URL builder
- `host`, `port`, `dbname`, `local_service_name`, `rac_url` — connection params
- `user`, `password` — credentials
- `auto_commit` (bool, default False) — applied via `conn.autocommit = bool(...)`
- `schema_db` — for globalMap metadata only (oracledb thin doesn't have ALTER SESSION SET CURRENT_SCHEMA scope; Phase 11 stores the metadata, deferred to component logic)
- `properties` — best-effort parse, log warnings on unrecognized keys
- `encoding` — log INFO; non-applicable in thin mode
- All others (use_tns_file, use_ssl, etc.) — extracted but not honored in Phase 11 (deferred — log WARNING when set true and skipped)

### `_validate_config()` (structural-only per Rule 12)

```python
def _validate_config(self) -> None:
    # Required: connection_type must be one of the 5 known values
    valid_types = {"ORACLE_SID", "ORACLE_SERVICE_NAME", "ORACLE_OCI", "ORACLE_RAC", "ORACLE_WALLET"}
    ct = self.config.get("connection_type", "ORACLE_SID")
    if ct not in valid_types:
        raise ConfigurationError(
            f"[{self.id}] Invalid connection_type {ct!r}. Must be one of: {valid_types}"
        )
    # Required: user / password keys present (values may be context-resolved)
    for key in ("user", "password"):
        if key not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key {key!r}"
            )
```

### `_process()` (content checks per Rule 12)

```python
def _process(self, input_data=None) -> dict:
    # tOracleConnection produces no data flow; it's a manager-side action
    ct = self.config["connection_type"]
    if ct in ("ORACLE_OCI", "ORACLE_WALLET"):
        raise ConfigurationError(
            f"[{self.id}] CONNECTION_TYPE {ct!r} requires oracledb thick mode "
            f"+ Oracle Instant Client. Set oracle_config.thick_mode=true in job "
            f"config and install Instant Client on the host. Tracked in deferred items."
        )

    # Build connect kwargs per CT (see "JDBC URL -> oracledb DSN Translation" section)
    if ct == "ORACLE_SID":
        conn = oracledb.connect(
            user=self.config["user"],
            password=self.config["password"],
            host=self.config["host"],
            port=int(self.config.get("port", 1521)),
            sid=self.config["dbname"],
        )
    elif ct == "ORACLE_SERVICE_NAME":
        conn = oracledb.connect(
            user=self.config["user"],
            password=self.config["password"],
            host=self.config["host"],
            port=int(self.config.get("port", 1521)),
            service_name=self.config["dbname"],
        )
    elif ct == "ORACLE_RAC":
        rac_url = self.config.get("rac_url", "").strip()
        if not rac_url:
            raise ConfigurationError(f"[{self.id}] ORACLE_RAC requires rac_url to be set")
        conn = oracledb.connect(
            user=self.config["user"],
            password=self.config["password"],
            dsn=rac_url,
        )

    # Honor AUTO_COMMIT advanced param (D-A4)
    if self.config.get("auto_commit", False):
        conn.autocommit = True

    # Register with manager — keyed by THIS component's id
    self.oracle_manager.register(self.id, conn)

    # Talend-parity globalMap metadata strings (NOT live Connection)
    if self.global_map:
        self.global_map.put(f"connectionType_{self.id}", ct)
        self.global_map.put(f"dbschema_{self.id}", self.config.get("schema_db", ""))
        self.global_map.put(f"username_{self.id}", self.config.get("user", ""))
        # password intentionally NOT pushed to globalMap (security; D-30 carryover)

    logger.info("[%s] Oracle connection registered (type=%s)", self.id, ct)
    return {"main": None, "reject": None}
```

### Stat globalMap keys
Per D-C8: tOracleConnection writes NO `_NB_LINE_*` keys (no data flow, matches Talend's missing RETURN section). Only the metadata keys above.

### Reject schema
Not applicable — tOracleConnection has no data flow.

### Integration tests must verify
- All 3 in-scope CT values open a real connection against `gvenzl/oracle-free`
- OCI / WALLET raise ConfigurationError with the expected message text
- `manager.get(self.id)` returns the same Connection downstream
- Connection survives across multiple downstream component calls (per D-A4 shared-connection lifetime)

---

## tOracleRow Implementation Guidance

### Module location
`src/v1/engine/components/database/oracle_row.py`

### Registration
```python
@REGISTRY.register("OracleRow", "tOracleRow")
class OracleRow(BaseComponent):
    ...
```

### Config keys consumed
28 keys (mirror converter). Critical ones for Phase 11:
- `use_existing_connection` (bool), `connection` (str cid ref) — connection acquisition
- `connection_type`, `host`, `port`, `dbname`, `user`, `password` — for ad-hoc when use_existing=False
- `query` (str) — the SQL to execute
- `use_nb_line` (str enum: `"NONE"`, `"NB_LINE_INSERTED"`, `"NB_LINE_UPDATED"`, `"NB_LINE_DELETED"`)
- `propagate_record_set` (bool) — must raise ConfigurationError when true (D-C4)
- `use_preparedstatement` (bool)
- `set_preparedstatement_parameters` (list[dict] with parameter_index, parameter_type, parameter_value)
- `commit_every` (int, default 10000) — only meaningful for prepared-statement loop (rare; usually tOracleRow runs one statement)
- `die_on_error` (bool, default False) — handled by BaseComponent via REJECT routing

### `_validate_config()`

```python
def _validate_config(self) -> None:
    if "query" not in self.config:
        raise ConfigurationError(f"[{self.id}] Missing required config key 'query'")
    use_nb_line = self.config.get("use_nb_line", "NONE")
    valid_nb = {"NONE", "NB_LINE_INSERTED", "NB_LINE_UPDATED", "NB_LINE_DELETED"}
    if use_nb_line not in valid_nb:
        raise ConfigurationError(
            f"[{self.id}] Invalid use_nb_line {use_nb_line!r}. Must be one of: {valid_nb}"
        )
    # Structural check on prepared-statement table shape (not value content)
    if self.config.get("use_preparedstatement", False):
        params = self.config.get("set_preparedstatement_parameters", [])
        if not isinstance(params, list):
            raise ConfigurationError(
                f"[{self.id}] set_preparedstatement_parameters must be a list"
            )
```

### `_process()`

```python
def _process(self, input_data=None) -> dict:
    # D-C4: PROPAGATE_RECORD_SET deferred
    if self.config.get("propagate_record_set", False):
        raise ConfigurationError(
            f"[{self.id}] tOracleRow PROPAGATE_RECORD_SET emits a live ResultSet "
            f"to a downstream FLOW column; this Talend pattern doesn't translate "
            f"cleanly to DataFrame semantics. Tracked in deferred items - rewrite "
            f"as tOracleInput -> downstream component when this is needed."
        )

    # Acquire connection
    use_existing = self.config.get("use_existing_connection", False)
    if use_existing:
        connection_ref = self.config.get("connection", "")
        conn = self.oracle_manager.get(connection_ref)
        owns_connection = False
    else:
        conn = self.oracle_manager.open_ad_hoc(self.id, self.config)
        owns_connection = True

    query = self.config["query"]
    use_nb_line = self.config.get("use_nb_line", "NONE")

    cursor = conn.cursor()
    try:
        if self.config.get("use_preparedstatement", False):
            # Coerce params via the 16-type lookup table (see "USE_PREPAREDSTATEMENT 16-Type Coercion Table")
            params = self.config.get("set_preparedstatement_parameters", [])
            bound_values = [_coerce_prepared_param(p) for p in sorted(params, key=lambda r: int(r["parameter_index"]))]
            cursor.execute(query, bound_values)
        else:
            cursor.execute(query)

        # USE_NB_LINE counter (D-C5)
        rowcount = cursor.rowcount
        if rowcount is None or rowcount < 0:
            # DDL or unknown
            if use_nb_line != "NONE":
                logger.warning(
                    "[%s] use_nb_line=%s set but cursor.rowcount=%s (DDL or unknown); writing 0",
                    self.id, use_nb_line, rowcount
                )
                rowcount = 0
        if use_nb_line != "NONE" and self.global_map:
            self.global_map.put(f"{self.id}_{use_nb_line}", int(rowcount or 0))

        # D-C8: also expose resolved query
        if self.global_map:
            self.global_map.put(f"{self.id}_QUERY", query)

        # If not using shared connection's auto_commit, commit explicitly
        # (Talend tOracleRow does conn.commit() at end of execution unless auto_commit set)
        if not conn.autocommit:
            conn.commit()
    finally:
        cursor.close()
        if owns_connection:
            self.oracle_manager.close(self.id)

    # tOracleRow can pass through input data on FLOW out (Talend behavior — passthrough)
    return {"main": input_data, "reject": None}
```

### Stat globalMap keys (D-C8)
- `{cid}_NB_LINE_INSERTED` / `{cid}_NB_LINE_UPDATED` / `{cid}_NB_LINE_DELETED` (per `use_nb_line` selection)
- `{cid}_QUERY` (resolved SQL, available during FLOW)

### Reject schema
Not applicable — tOracleRow doesn't have the executemany batch path. Errors raised as `ComponentExecutionError` (BaseComponent wraps `_process()` exceptions), routed by `die_on_error` semantics.

### Integration tests must verify
- DDL query (`CREATE TABLE`) succeeds, rowcount handled correctly (logs WARNING when use_nb_line set)
- DML query INSERT increments `NB_LINE_INSERTED`
- DML query UPDATE increments `NB_LINE_UPDATED`
- DML query DELETE increments `NB_LINE_DELETED`
- Prepared statement with all 16 PARAMETER_TYPE values round-trips correctly (mock-only tests cannot prove this — D-D3)
- PROPAGATE_RECORD_SET=true raises ConfigurationError with the expected message
- USE_EXISTING_CONNECTION=true reuses the tOracleConnection's Connection
- USE_EXISTING_CONNECTION=false opens ad-hoc and closes after

---

## tOracleOutput Implementation Guidance

### Module location
`src/v1/engine/components/database/oracle_output.py`

### Registration
```python
@REGISTRY.register("OracleOutput", "tOracleOutput")
class OracleOutput(BaseComponent):
    ...
```

### Config keys consumed
26 keys + 2 framework. Critical ones:
- `use_existing_connection`, `connection`, `connection_type`, `host`, `port`, `dbname`, `user`, `password`
- `table_schema` (Talend `TABLESCHEMA`), `table` — for SQL construction
- `table_action` (str enum, 8 values)
- `data_action` (str enum, 5 values)
- `commit_every` (int, default 10000)
- `use_batch_size`, `batch_size` (default True / 10000)
- `use_field_options`, `field_options` (TABLE — populated only if use_field_options=True; per-column UPDATE_KEY / DELETE_KEY / UPDATABLE / INSERTABLE)
- `use_timestamp_for_date_type` (bool, default True) — DATE columns bind as `DB_TYPE_TIMESTAMP` when true
- `trim_char` (bool, default True) — affects read path (deferred for tOracleOutput; relevant for tOracleInput)
- `convert_column_table_to_uppercase` (bool, default False)
- `die_on_error` (bool, default False) — handled by BaseComponent

### `_validate_config()`

```python
def _validate_config(self) -> None:
    if "table" not in self.config or not self.config["table"]:
        raise ConfigurationError(f"[{self.id}] Missing required config key 'table'")
    valid_table_actions = {"NONE", "CREATE", "CREATE_IF_NOT_EXISTS", "DROP_CREATE",
                            "DROP_IF_EXISTS_AND_CREATE", "CLEAR", "TRUNCATE",
                            "TRUNCATE_REUSE_STORAGE"}
    ta = self.config.get("table_action", "NONE")
    if ta not in valid_table_actions:
        raise ConfigurationError(
            f"[{self.id}] Invalid table_action {ta!r}. Must be one of: {valid_table_actions}"
        )
    valid_data_actions = {"INSERT", "UPDATE", "INSERT_OR_UPDATE", "UPDATE_OR_INSERT", "DELETE"}
    da = self.config.get("data_action", "INSERT")
    if da not in valid_data_actions:
        raise ConfigurationError(
            f"[{self.id}] Invalid data_action {da!r}. Must be one of: {valid_data_actions}"
        )
```

### `_process()` skeleton

```python
def _process(self, input_data=None) -> dict:
    if input_data is None:
        return {"main": None, "reject": None}

    # 1. Acquire connection (existing or ad-hoc)
    use_existing = self.config.get("use_existing_connection", False)
    if use_existing:
        conn = self.oracle_manager.get(self.config.get("connection", ""))
        owns_connection = False
    else:
        conn = self.oracle_manager.open_ad_hoc(self.id, self.config)
        owns_connection = True

    table_action = self.config.get("table_action", "NONE")
    data_action = self.config.get("data_action", "INSERT")
    table = self._qualified_table_name()  # combines table_schema + table

    cursor = conn.cursor()
    try:
        # 2. TABLE_ACTION: emit DDL (no DML if NONE)
        if table_action != "NONE":
            self._execute_table_action(cursor, table_action, table)
            if not conn.autocommit:
                conn.commit()  # DDL commits implicitly in Oracle, but explicit for clarity

        # 3. DATA_ACTION: build SQL + parameter binds + executemany
        rows = self._dataframe_to_param_list(input_data)
        input_sizes = self._build_input_sizes()

        inserted = updated = deleted = rejected = 0
        all_reject_dfs = []  # accumulator
        commit_every = int(self.config.get("commit_every", 10000))
        batch_size = int(self.config.get("batch_size", 10000)) if self.config.get("use_batch_size", True) else len(rows)

        # Chunk rows by batch_size
        since_commit = 0
        for chunk_start in range(0, len(rows), batch_size):
            chunk = rows[chunk_start:chunk_start + batch_size]

            if data_action in ("INSERT_OR_UPDATE", "UPDATE_OR_INSERT"):
                ins_count, upd_count, rej_chunk = self._execute_upsert_batch(
                    cursor, table, chunk, input_data.iloc[chunk_start:chunk_start + len(chunk)],
                    prefer_update=(data_action == "UPDATE_OR_INSERT"),
                )
                inserted += ins_count
                updated += upd_count
            else:
                # INSERT / UPDATE / DELETE: single executemany
                sql = self._build_dml_sql(data_action)
                cursor.setinputsizes(*input_sizes)
                cursor.executemany(sql, chunk, batcherrors=True)
                batch_errors = cursor.getbatcherrors()

                # Build reject DataFrame from BatchError.offset
                if batch_errors:
                    rej_chunk = self._build_reject_chunk(
                        input_data.iloc[chunk_start:chunk_start + len(chunk)],
                        batch_errors,
                    )
                else:
                    rej_chunk = None

                rejected += len(batch_errors)
                ok_count = len(chunk) - len(batch_errors)
                if data_action == "INSERT":
                    inserted += ok_count
                elif data_action == "UPDATE":
                    updated += ok_count
                elif data_action == "DELETE":
                    deleted += ok_count

            if rej_chunk is not None and not rej_chunk.empty:
                all_reject_dfs.append(rej_chunk)

            since_commit += len(chunk)
            if since_commit >= commit_every and not conn.autocommit:
                conn.commit()
                since_commit = 0

        # 4. Final commit of trailing batch
        if since_commit > 0 and not conn.autocommit:
            conn.commit()

        # 5. globalMap stats (D-C8)
        if self.global_map:
            self.global_map.put(f"{self.id}_NB_LINE", len(input_data))
            self.global_map.put(f"{self.id}_NB_LINE_INSERTED", inserted)
            self.global_map.put(f"{self.id}_NB_LINE_UPDATED", updated)
            self.global_map.put(f"{self.id}_NB_LINE_DELETED", deleted)
            self.global_map.put(f"{self.id}_NB_LINE_REJECTED", rejected)

        reject_df = pd.concat(all_reject_dfs, ignore_index=True) if all_reject_dfs else None
    finally:
        cursor.close()
        if owns_connection:
            self.oracle_manager.close(self.id)

    return {"main": input_data, "reject": reject_df}
```

### Stat globalMap keys (D-C8)
- `{cid}_NB_LINE` — total input rows
- `{cid}_NB_LINE_INSERTED`, `{cid}_NB_LINE_UPDATED`, `{cid}_NB_LINE_DELETED` — per data_action
- `{cid}_NB_LINE_REJECTED` — sum across batches

### Reject schema (D-C7)
```python
# [errorCode (str), errorMessage (str), <input_columns>]
# errorCode = str(BatchError.code)         # e.g. "1" for ORA-00001
# errorMessage = f"{BatchError.message} - Line: {batch_errors[i].offset}"
```

### Integration tests must verify (D-D3, D-F4)
- All 8 TABLE_ACTIONs emit working DDL against real Oracle (VERIFIED only by integration tests; mock cannot prove this)
- All 5 DATA_ACTIONs round-trip (INSERT, UPDATE, INSERT_OR_UPDATE, UPDATE_OR_INSERT, DELETE)
- batcherrors REJECT routing: insert duplicate PKs, verify REJECT DataFrame contains them with correct errorCode and offset
- Type binding: each engine schema type round-trips through Oracle (NUMBER, VARCHAR2, DATE, TIMESTAMP, CLOB, BLOB)
- USE_TIMESTAMP_FOR_DATE_TYPE preserves sub-second precision when true; loses it when false
- INSERT_OR_UPDATE batched 2-statement: matched updates + unmatched inserts, stats split correctly

---

## Oracle DDL Emission From Engine Schema

For TABLE_ACTION ∈ {CREATE, CREATE_IF_NOT_EXISTS, DROP_CREATE, DROP_IF_EXISTS_AND_CREATE}, emit DDL from the engine `output_schema` (which is the input schema for an output component).

The Talaxie reference template `_tableActionForOutput.javajet` could not be fetched (404 — file is in a non-Oracle-specific location and not at the expected URL). We fall back to Oracle's standard SQL grammar [CITED: docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/CREATE-TABLE.html] and the column-type mapping convention used by the JDBC driver path.

### Column type mapping (engine schema -> Oracle DDL type)

| Engine schema `type` | Oracle DDL type | Notes |
|----------------------|-----------------|-------|
| `int` | `NUMBER(10)` | Java int range fits NUMBER(10). Use `NUMBER` (no precision) only if `length` not set. |
| `long` | `NUMBER(19)` | Java long range. |
| `short` | `NUMBER(5)` | |
| `byte` (numeric) | `NUMBER(3)` | |
| `BigInteger` | `NUMBER(38)` | Oracle NUMBER max precision. |
| `float` | `BINARY_FLOAT` | Oracle native single-precision. (Talaxie may emit `NUMBER` for parity with old JDBC; prefer `BINARY_FLOAT` for round-trip correctness. **Open question: see Open Questions section.**) |
| `double` | `BINARY_DOUBLE` | Oracle native double-precision. (Same caveat.) |
| `Decimal` (precision + scale set) | `NUMBER(p,s)` | e.g. `NUMBER(10,2)` from `length=10, precision=2`. |
| `Decimal` (no precision) | `NUMBER` | Unbounded Oracle NUMBER. |
| `str` (length set) | `VARCHAR2(n CHAR)` | `CHAR` semantics so `n` counts characters not bytes. Talend default uses `CHAR`. |
| `str` (no length, "large") | `CLOB` | Trigger when length > 4000 (Oracle VARCHAR2 limit) or when explicit `is_clob=true` flag (rare in Talend schemas). |
| `bool` | `NUMBER(1)` | Oracle has no native BOOLEAN before 23c. Talend convention: NUMBER(1) with 0/1. |
| `datetime` (when `use_timestamp_for_date_type=False`) | `DATE` | Second precision. |
| `datetime` (when `use_timestamp_for_date_type=True`, default) | `TIMESTAMP` | Sub-second precision. Talend default. |
| `bytes` | `BLOB` | Or `RAW(n)` if `length` set ≤2000. |
| `Object` (passthrough) | `VARCHAR2(4000)` | Conservative fallback. Log WARNING — schema should declare a concrete type. |

### Standard DDL templates

```sql
-- CREATE
CREATE TABLE {qualified_table} (
  {col1} {type1} {NULL/NOT NULL},
  {col2} {type2} {NULL/NOT NULL},
  ...
  CONSTRAINT {pk_name} PRIMARY KEY ({key_cols})
);
```

`pk_name` convention: `PK_{table_unqualified}`. `key_cols` from schema columns where `key=True`. If no keys declared, omit the CONSTRAINT clause.

```sql
-- CREATE_IF_NOT_EXISTS (Oracle has no IF NOT EXISTS; emulate via PL/SQL)
BEGIN
  EXECUTE IMMEDIATE 'CREATE TABLE {qualified_table} (...)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN  -- ORA-00955: name is already used by an existing object
      RAISE;
    END IF;
END;
```

`-955` is the documented Oracle code for "name already in use". [CITED: docs.oracle.com error reference]

```sql
-- DROP_CREATE  (drop unconditionally, then create — fails if table doesn't exist)
DROP TABLE {qualified_table} PURGE;
CREATE TABLE {qualified_table} (...);
```

```sql
-- DROP_IF_EXISTS_AND_CREATE  (PL/SQL guard for ORA-00942: table or view does not exist)
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE {qualified_table} PURGE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -942 THEN
      RAISE;
    END IF;
END;
-- followed by CREATE TABLE ...
```

`-942` is documented Oracle code for "table or view does not exist".

```sql
-- CLEAR
DELETE FROM {qualified_table};

-- TRUNCATE
TRUNCATE TABLE {qualified_table};

-- TRUNCATE_REUSE_STORAGE
TRUNCATE TABLE {qualified_table} REUSE STORAGE;
```

### Implementation note for the planner

These emit-and-execute helpers are private static methods on `OracleOutput`. Each TABLE_ACTION is one method (~10–30 lines). Test in isolation with mocks — actual DDL execution is verified by `@pytest.mark.oracle` integration tests. The Decimal precision parser (`length`/`precision` -> `NUMBER(p,s)`) is the trickiest piece; reuse `BaseComponent._apply_decimal_precision` insights.

---

## INSERT_OR_UPDATE Batched 2-Statement Pattern (D-C2)

Per batch of N input rows:

1. **Identify primary key columns** from schema `key=True` columns (or `field_options` UPDATE_KEY when `use_field_options=True`).
2. **Build the SELECT-existing query.** For a single PK column:
   ```sql
   SELECT {pk_col} FROM {table} WHERE {pk_col} IN (:1, :2, ..., :N)
   ```
   For composite PK, Oracle does not support `(a,b) IN ((:1,:2),(:3,:4))` natively — use a tuple OR-chain or a temporary table. **Recommended:** OR-chain with bind groups:
   ```sql
   SELECT pk1, pk2 FROM {table}
    WHERE (pk1 = :1 AND pk2 = :2)
       OR (pk1 = :3 AND pk2 = :4)
       OR ...
   ```
   For very large batches (>100 keys) this becomes ugly — fall back to a temporary in-memory `WITH` CTE or split the batch.
3. **Fetch matched keys** into a Python set.
4. **Partition input rows** in Python:
   ```python
   matched_rows = [r for r in chunk if (r["pk1"], r["pk2"]) in matched_keys]
   unmatched_rows = [r for r in chunk if (r["pk1"], r["pk2"]) not in matched_keys]
   ```
5. **Execute `executemany UPDATE`** on matched_rows:
   ```sql
   UPDATE {table} SET {non_key_col} = :1, ... WHERE {pk1} = :N AND {pk2} = :M
   ```
6. **Execute `executemany INSERT`** on unmatched_rows (with batcherrors on this one — INSERT collisions due to race conditions still possible, route to REJECT).
7. **Stats:**
   - `INSERT_OR_UPDATE`: `inserted += len(unmatched_rows) - insert_errors`; `updated += len(matched_rows) - update_errors`
   - `UPDATE_OR_INSERT`: same logic but matched_rows go to UPDATE first (by partition); unmatched_rows go to INSERT. Behavioral difference is in the order of the SELECT: in `UPDATE_OR_INSERT` Talend tries UPDATE first per row, falling back to INSERT only on row-not-found. In our batched 2-statement, the partition logic is the same; only stat ordering differs.

### NULL-as-key edge case

Oracle treats `NULL = NULL` as UNKNOWN (not TRUE). If a PK column allows NULL (rare but possible in Talend schemas), input rows with NULL PK will:
- Never match the SELECT (`= NULL` never returns rows)
- Be partitioned as "unmatched" -> attempted INSERT
- INSERT may fail if there's a UNIQUE constraint that treats NULLs as distinct

**Recommendation:** Log WARNING when `key=True` columns have any NULL values in the input batch, and treat all NULL-key rows as "unmatched" (force INSERT).

### Code skeleton

```python
def _execute_upsert_batch(self, cursor, table, chunk_rows, chunk_df,
                          prefer_update: bool):
    """Batched 2-statement upsert. Returns (inserted, updated, reject_df).
    
    Args:
        cursor: oracledb cursor.
        table: qualified table name.
        chunk_rows: list of param tuples (DataFrame rows as bind values).
        chunk_df: original DataFrame slice for REJECT reconstruction.
        prefer_update: True for UPDATE_OR_INSERT (try update first), False for
            INSERT_OR_UPDATE (try insert first via the standard logic). Note: in
            the batched 2-statement form, prefer_update only affects which stats
            counter the matched/unmatched rows are attributed to.
    
    Returns:
        (inserted_count, updated_count, reject_df_or_None).
    """
    pk_cols = self._get_primary_key_cols()  # from schema or field_options
    if not pk_cols:
        raise ConfigurationError(
            f"[{self.id}] {data_action} requires at least one primary key column "
            f"(schema 'key' attribute or field_options UPDATE_KEY)"
        )

    # Build SELECT existing
    select_sql = self._build_pk_select_sql(table, pk_cols, len(chunk_rows))
    select_binds = self._flatten_pk_binds(chunk_rows, pk_cols)
    cursor.execute(select_sql, select_binds)
    matched_keys = set(tuple(row) for row in cursor.fetchall())

    # Partition
    matched_chunk = []
    unmatched_chunk = []
    for r in chunk_rows:
        key = tuple(r[col] for col in pk_cols)
        if key in matched_keys and not any(v is None for v in key):
            matched_chunk.append(r)
        else:
            unmatched_chunk.append(r)

    # executemany UPDATE
    update_sql = self._build_update_sql(table, pk_cols)
    if matched_chunk:
        cursor.setinputsizes(*self._build_update_input_sizes())
        cursor.executemany(update_sql, matched_chunk, batcherrors=True)
        update_errors = cursor.getbatcherrors()
    else:
        update_errors = []

    # executemany INSERT
    insert_sql = self._build_insert_sql(table)
    if unmatched_chunk:
        cursor.setinputsizes(*self._build_insert_input_sizes())
        cursor.executemany(insert_sql, unmatched_chunk, batcherrors=True)
        insert_errors = cursor.getbatcherrors()
    else:
        insert_errors = []

    # Build combined reject DataFrame (from both error lists)
    # ... maps offset back to chunk_df rows ...

    inserted_count = len(unmatched_chunk) - len(insert_errors)
    updated_count = len(matched_chunk) - len(update_errors)
    return (inserted_count, updated_count, reject_df_or_None)
```

---

## USE_PREPAREDSTATEMENT 16-Type Coercion Table

Per D-C3, all 16 PARAMETER_TYPE values from Talaxie's tOracleRow map to a Python coercion call. Use a static lookup dict at module level:

```python
# Source: D-C3 + Talaxie tOracleRow_java.xml PARAMETER_TYPE enum
import datetime
from decimal import Decimal

def _coerce_string(v):  return str(v) if v is not None else None
def _coerce_int(v):     return int(v) if v is not None else None
def _coerce_decimal(v): return Decimal(str(v)) if v is not None else None
def _coerce_bool(v):    return bool(v) if v is not None else None
def _coerce_float(v):   return float(v) if v is not None else None

def _coerce_date(v):
    if v is None: return None
    if isinstance(v, datetime.date) and not isinstance(v, datetime.datetime):
        return v
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, str):
        return datetime.date.fromisoformat(v)
    raise ValueError(f"Cannot coerce {v!r} to date")

def _coerce_timestamp(v):
    if v is None: return None
    if isinstance(v, datetime.datetime):
        return v
    if isinstance(v, str):
        return datetime.datetime.fromisoformat(v)
    raise ValueError(f"Cannot coerce {v!r} to timestamp")

def _coerce_time(v):
    if v is None: return None
    if isinstance(v, datetime.time):
        return v
    if isinstance(v, str):
        return datetime.time.fromisoformat(v)
    raise ValueError(f"Cannot coerce {v!r} to time")

def _coerce_bytes(v):
    if v is None: return None
    if isinstance(v, bytes):
        return v
    if isinstance(v, str):
        return v.encode("utf-8")
    raise ValueError(f"Cannot coerce {v!r} to bytes")

def _passthrough(v): return v


_PARAM_TYPE_COERCERS = {
    "String":     _coerce_string,
    "Int":        _coerce_int,
    "Integer":    _coerce_int,    # Talaxie alias
    "Long":       _coerce_int,    # Python int handles long range
    "Short":      _coerce_int,
    "Byte":       _coerce_int,
    "BigInteger": _coerce_int,    # Python int is unbounded
    "BigDecimal": _coerce_decimal,
    "Boolean":    _coerce_bool,
    "Float":      _coerce_float,
    "Double":     _coerce_float,
    "Date":       _coerce_date,
    "Timestamp":  _coerce_timestamp,
    "Time":       _coerce_time,
    "Bytes":      _coerce_bytes,
    "Object":     _passthrough,   # let oracledb infer
}


def _coerce_prepared_param(param: dict) -> Any:
    """Apply the right coercer for a single SET_PREPAREDSTATEMENT_PARAMETERS row.
    
    Args:
        param: dict with keys parameter_index, parameter_type, parameter_value.
    
    Returns:
        Coerced bind value.
    
    Raises:
        ConfigurationError: If parameter_type is not in the 16-type table.
    """
    p_type = param.get("parameter_type", "Object")
    p_value = param.get("parameter_value", None)
    coercer = _PARAM_TYPE_COERCERS.get(p_type)
    if coercer is None:
        raise ConfigurationError(
            f"Unknown PARAMETER_TYPE {p_type!r}. Supported: {sorted(_PARAM_TYPE_COERCERS.keys())}"
        )
    return coercer(p_value)
```

[ASSUMED: The 16th type — Talaxie's tOracleRow PARAMETER_TYPE enum may include `null` or `NULL` as a sentinel; verified Talaxie source listed via web research is incomplete on this point. Plan should grep tOracleRow_java.xml to confirm the full enum list before locking the table.]

---

## Type Binding for cursor.setinputsizes() (Schema -> oracledb DB_TYPE_*)

For tOracleOutput's executemany, build the `setinputsizes` argument list per output column. [VERIFIED via `python -c "import oracledb"`: all listed constants exist in oracledb 3.4.2]

| Engine schema `type` | oracledb constant | Notes |
|----------------------|-------------------|-------|
| `int` / `long` / `short` / `byte` / `BigInteger` | `oracledb.NUMBER` (or `oracledb.DB_TYPE_NUMBER`) | Both are equivalent for binding. |
| `Decimal` | `oracledb.NUMBER` | Driver handles `Decimal` -> NUMBER round-trip. |
| `float` / `double` | `oracledb.NUMBER` | (Or `DB_TYPE_BINARY_FLOAT` / `DB_TYPE_BINARY_DOUBLE` if BINARY_FLOAT/DOUBLE columns are used per the DDL section.) |
| `str` (with length) | `length` (int) | Per setinputsizes() convention, an int means "VARCHAR2 of size N". |
| `str` (CLOB) | `oracledb.DB_TYPE_CLOB` | When length > 4000 or column is CLOB. |
| `datetime` (USE_TIMESTAMP_FOR_DATE_TYPE=True) | `oracledb.DB_TYPE_TIMESTAMP` | D-B1: default true, preserves sub-second precision. |
| `datetime` (USE_TIMESTAMP_FOR_DATE_TYPE=False) | `oracledb.DB_TYPE_DATE` | Second precision. |
| `datetime` (TIMESTAMP WITH TIMEZONE) | `oracledb.DB_TYPE_TIMESTAMP_TZ` | Only when schema explicitly says timezone-aware (rare in Talend; deferred). |
| `bool` | `oracledb.NUMBER` | Bound as 0/1 since Oracle has no native BOOLEAN before 23c. |
| `bytes` (BLOB) | `oracledb.DB_TYPE_BLOB` | |
| `bytes` (RAW, length set) | `oracledb.DB_TYPE_RAW` | When schema length > 0 and ≤ 2000. |

```python
def _build_input_sizes(self) -> list:
    """Build setinputsizes args list, one entry per output_schema column in order."""
    sizes = []
    use_ts = self.config.get("use_timestamp_for_date_type", True)
    for col in self.output_schema:
        ctype = col.get("type", "str")
        clength = col.get("length")
        if ctype in ("int", "long", "short", "byte", "BigInteger", "Decimal", "float", "double", "bool"):
            sizes.append(oracledb.NUMBER)
        elif ctype == "str":
            if clength and int(clength) <= 4000:
                sizes.append(int(clength))
            else:
                sizes.append(oracledb.DB_TYPE_CLOB)
        elif ctype == "datetime":
            sizes.append(oracledb.DB_TYPE_TIMESTAMP if use_ts else oracledb.DB_TYPE_DATE)
        elif ctype == "bytes":
            if clength and int(clength) <= 2000:
                sizes.append(oracledb.DB_TYPE_RAW)
            else:
                sizes.append(oracledb.DB_TYPE_BLOB)
        else:
            sizes.append(None)  # let driver infer
    return sizes
```

---

## executemany + batcherrors Mechanics

[CITED: python-oracledb.readthedocs.io/en/v2.4.0/user_guide/batch_statement.html]

### Signature and behavior

```python
cursor.executemany(sql, data, batcherrors=True)
```

- `sql`: parameterized SQL string with `:1, :2, ...` (positional) or `:name` (named) bind variables.
- `data`: list of tuples (positional) or list of dicts (named).
- `batcherrors=True`: continues processing on per-row errors instead of raising on the first failure.

### `cursor.getbatcherrors()` return

Returns a `list[oracledb._Error]`. Each Error has the following public attributes [CITED: python-oracledb exception_handling docs + verified pattern in batch_statement docs]:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `code` | `int` | Oracle error number | `1` (for ORA-00001) |
| `full_code` | `str` | Full Oracle code with `ORA-` prefix | `"ORA-00001"` |
| `message` | `str` | Human-readable error message | `"unique constraint (HR.PK_EMP) violated"` |
| `offset` | `int` | Index into the `data` list of the row that failed | `2` (third row in the batch) |

### Autocommit interaction

[VERIFIED: oracledb 2.4 batch_statement docs] When `batcherrors=True` is passed AND errors occur, "a transaction will be started but not committed, even if Connection.autocommit is set to True." This means with batcherrors enabled, the engine MUST explicitly call `conn.commit()` after a successful batch (or `conn.rollback()` if all errors). Don't rely on connection autocommit when batcherrors is in play.

### Reset between batches at COMMIT_EVERY threshold

Cursor state resets per `executemany` call. The pattern for COMMIT_EVERY = 5000 with BATCH_SIZE = 1000:

```python
since_commit = 0
for chunk_start in range(0, len(rows), batch_size):
    chunk = rows[chunk_start:chunk_start + batch_size]
    cursor.executemany(sql, chunk, batcherrors=True)
    errors = cursor.getbatcherrors()
    # ... accumulate into reject_df, increment counters ...
    since_commit += len(chunk)
    if since_commit >= commit_every:
        conn.commit()
        since_commit = 0

if since_commit > 0:
    conn.commit()  # trailing partial commit
```

---

## Reject Schema Parity (D-C7)

Talaxie's tOracleOutput sets:
- `errorCode` = `SQLException.getSQLState()` (ANSI SQL state, like `"23000"` for integrity violation) [CITED: tOracleOutput_main.javajet]
- `errorMessage` = `e.getMessage() + " - Line: " + count`

Our oracledb path uses:
- `errorCode` from `BatchError.code` (Oracle error number int, like `1` for ORA-00001)
- `errorMessage` from `BatchError.message + " - Line: <BatchError.offset>"`

**Decision (per D-C7):** `errorCode = str(BatchError.code)` (Oracle number), NOT SQLState. Rationale:
1. oracledb does not expose ANSI SQLState directly (it would require mapping the Oracle code -> SQLState which is itself a JDBC convention).
2. Talaxie's SQLState comes from JDBC's `OracleSQLException.getSQLState()`, which itself wraps the Oracle code. The mapping is lossy (multiple Oracle codes can map to the same SQLState).
3. The Oracle code is more diagnostically useful for downstream consumers ("ORA-00001" is unambiguous; "23000" is "any integrity violation").

Document this divergence in the component docstring as a deliberate D-C7 decision.

```python
# Build reject row from BatchError
def _build_reject_row(self, original_row_df: pd.DataFrame, error: oracledb._Error) -> dict:
    """Convert one BatchError + its source DataFrame row into a reject row dict."""
    return {
        "errorCode": str(error.code),  # e.g. "1" for ORA-00001
        "errorMessage": f"{error.message} - Line: {error.offset}",
        # ...plus all input column values from original_row_df.iloc[error.offset]...
    }
```

---

## AUTO_COMMIT Param Semantics

When `tOracleConnection.AUTO_COMMIT=true`:
1. After `oracledb.connect(...)`, manager sets `conn.autocommit = True`.
2. Downstream tOracleRow / tOracleOutput honor it: skip explicit `conn.commit()` calls.
3. **executemany + batcherrors gotcha:** per [CITED: oracledb batch_statement] when batcherrors=True is set AND errors occur, Oracle starts a transaction even with autocommit=True. The engine must still commit successfully-executed-rows explicitly. Document this.

**Should we refuse `auto_commit=true + commit_every>0`?** No — Talend itself allows the combo (commit_every becomes a no-op). Honor it as Talend does. Log INFO when both are set: `"[%s] auto_commit=True; commit_every=%d ignored (autocommit commits per batch)"`.

---

## Test Infrastructure: testcontainers + gvenzl/oracle-free

### Recommended image: `gvenzl/oracle-free:23-slim-faststart`

| Image | Size | Boot time | Notes |
|-------|------|-----------|-------|
| `gvenzl/oracle-free:23-slim-faststart` | ~300 MB | ~15–30s | Pre-warmed PDB; recommended for tests |
| `gvenzl/oracle-free:23-slim` | ~300 MB | ~30–60s | Cold start; full PDB init |
| `gvenzl/oracle-free:23` | ~1 GB | ~60–120s | Full image with sample schemas |

[VERIFIED: gvenzl/oracle-free Docker Hub README; faststart variant is the documented test-recommended build]

CONTEXT.md D-D3 mentions `:23-slim`. Recommend `:23-slim-faststart` for ~2x faster CI runs. This is a Claude's-discretion call per CONTEXT.md (test fixture design).

### conftest.py fixture pattern

```python
# tests/v1/engine/components/database/integration/conftest.py
import os
import pytest
import oracledb

# Skip the entire module if testcontainers not installed
testcontainers = pytest.importorskip("testcontainers")
from testcontainers.oracle import OracleDbContainer  # type: ignore


@pytest.fixture(scope="session")
def oracle_container():
    """Session-scoped Oracle Free container. Boots once for the whole pytest -m oracle run."""
    if os.environ.get("SKIP_ORACLE_CONTAINER"):
        pytest.skip("Oracle container disabled via SKIP_ORACLE_CONTAINER")
    container = OracleDbContainer("gvenzl/oracle-free:23-slim-faststart")
    container.start()
    try:
        # Health probe: SELECT 1 from sys.dual until it succeeds (handles slow boot)
        import time
        for _ in range(60):
            try:
                conn = oracledb.connect(
                    user=container.username,
                    password=container.password,
                    host=container.get_container_host_ip(),
                    port=int(container.get_exposed_port(1521)),
                    service_name="FREEPDB1",  # gvenzl/oracle-free default PDB name
                )
                conn.close()
                break
            except Exception:
                time.sleep(1)
        yield container
    finally:
        container.stop()


@pytest.fixture
def oracle_dsn(oracle_container):
    """Per-test DSN dict for opening connections."""
    return {
        "user": oracle_container.username,
        "password": oracle_container.password,
        "host": oracle_container.get_container_host_ip(),
        "port": int(oracle_container.get_exposed_port(1521)),
        "service_name": "FREEPDB1",
    }


@pytest.fixture
def oracle_connection(oracle_dsn):
    """Per-test Oracle Connection. Auto-closed via fixture teardown."""
    conn = oracledb.connect(**oracle_dsn)
    yield conn
    conn.close()
```

### Test isolation strategy

**Recommended:** unique table names per test (e.g., `test_<func_name>_<random_suffix>`) with explicit DROP at test teardown. Avoid full container restart per test — that would push integration test wall time from minutes to hours.

```python
@pytest.fixture
def temp_table(oracle_connection):
    """Create a unique-named test table; drop on teardown."""
    import secrets
    name = f"PYTEST_T_{secrets.token_hex(4).upper()}"
    yield name
    cursor = oracle_connection.cursor()
    try:
        cursor.execute(f"DROP TABLE {name} PURGE")
    except Exception:
        pass
    finally:
        cursor.close()
```

### Marker registration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Unit tests (fast, no I/O)",
    "integration: Integration tests (may require file I/O)",
    "java: Tests requiring Java bridge",
    "oracle: Tests requiring an Oracle DB testcontainer (slow, opt-in)",
    "slow: Tests that take >5 seconds",
    "coverage: Documents coverage gate requirements (always skipped; enforced by CI command)",
]
```

### Boot time and overhead

- First `pytest -m oracle` run: ~30s container boot + ~2s per test (typical).
- Subsequent runs in same `pytest` invocation: ~2s per test (container reused via session scope).
- For 30 integration tests: ~90s total wall clock on dev hardware.

---

## Sample .item File Conversion (verify before writing integration tests)

The 3 sample files in `tests/talend_xml_samples/`:
- `Job_tOracleConnection_0.1.item`
- `Job_tOracleRow_0.1.item`
- `Job_tOracleOutput_0.1.item`

Sub-phase 11-07 must run:
```bash
python -m src.converters.talend_to_v1.converter tests/talend_xml_samples/Job_tOracleConnection_0.1.item /tmp/conn.json
python -m src.converters.talend_to_v1.converter tests/talend_xml_samples/Job_tOracleRow_0.1.item /tmp/row.json
python -m src.converters.talend_to_v1.converter tests/talend_xml_samples/Job_tOracleOutput_0.1.item /tmp/out.json
```

…and inspect the JSON output. Fixtures for `tests/v1/engine/components/database/integration/test_*_e2e.py` should reuse these exact JSONs (copy into the integration test fixture folder).

The plan should include a sub-task in 11-07 to inspect the output and document what context variables / connection params each sample uses (likely: `${context.host}`, `${context.user}`, `${context.password}`, hard-coded `dbname`, etc.). The integration test then injects values that point at the testcontainer.

---

## Converter Update (D-E1)

`src/converters/talend_to_v1/components/database/oracle_connection.py`, `oracle_row.py`, `oracle_output.py`: add a check after extracting `connection_type`:

```python
# After config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
if config["connection_type"] in ("ORACLE_OCI", "ORACLE_WALLET"):
    needs_review.append({
        "issue": (
            f"Connection type {config['connection_type']} requires "
            f"oracle_config.thick_mode=true in job config, plus Oracle Instant "
            f"Client on the host. Phase 11 raises ConfigurationError until "
            f"thick_mode is set."
        ),
        "component": node.component_id,
        "severity": "needs_attention",
    })
```

Replace the existing consolidated `engine_gap` review for OCI/Wallet jobs only — keep the existing engine-gap review for non-OCI/Wallet types (since those engines still don't exist for the OTHER 6 Oracle components — only these 3 ship in Phase 11).

[ASSUMED: After Phase 11, the existing "No concrete engine implementation" needs_review entry should be REMOVED for the 3 in-scope components, since the engine WILL exist. Plan should explicitly call this out — converter test files for these 3 components will need updating to reflect the new needs_review structure.]

---

## Validation Architecture

> Required per D-D3, D-F4. Validation is the verification gate of Phase 11.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/v1/engine/components/database/ -x --ignore=tests/v1/engine/components/database/integration` |
| Full unit suite | `pytest tests/v1/engine/components/database/ -x` (without `-m oracle` filter; integration tests skipped automatically since they require the marker AND testcontainers) |
| Integration suite | `pytest -m oracle tests/v1/engine/components/database/integration/` |
| Phase gate command | `pytest -m oracle` (full integration run, MUST pass before phase verified per D-D3/D-F4) |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ORAC-01 | Manager idempotent stop, register / get / open_ad_hoc / close / commit / rollback API | unit (mock-based) | `pytest tests/v1/engine/test_oracle_connection_manager.py -x` | Wave 0 (new file) |
| ORAC-01 | Manager wired into ETLEngine __init__ / _initialize_components / _cleanup | unit | `pytest tests/v1/engine/test_engine.py::test_oracle_manager_wiring -x` | Wave 0 (new test in existing file) |
| ORAC-02 | tOracleConnection opens for ORACLE_SID | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py::test_sid -x` | Wave 0 |
| ORAC-02 | tOracleConnection opens for ORACLE_SERVICE_NAME | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py::test_service_name -x` | Wave 0 |
| ORAC-02 | tOracleConnection opens for ORACLE_RAC (raw TNS DSN) | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py::test_rac -x` | Wave 0 |
| ORAC-02 | tOracleConnection raises ConfigurationError for OCI / Wallet | unit | `pytest tests/v1/engine/components/database/test_oracle_connection.py::test_unsupported_types_raise -x` | Wave 0 |
| ORAC-03 | tOracleRow USE_PREPAREDSTATEMENT all 16 PARAMETER_TYPE values round-trip | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_row_e2e.py::test_prepared_all_types -x` | Wave 0 |
| ORAC-03 | tOracleRow PROPAGATE_RECORD_SET=true raises ConfigurationError | unit | `pytest tests/v1/engine/components/database/test_oracle_row.py::test_propagate_record_set_raises -x` | Wave 0 |
| ORAC-03 | tOracleRow USE_NB_LINE writes correct globalMap key | unit + integration | `pytest tests/v1/engine/components/database/test_oracle_row.py::test_use_nb_line_*` | Wave 0 |
| ORAC-04 | tOracleOutput all 8 TABLE_ACTIONs emit valid Oracle DDL | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_output_e2e.py::test_table_actions` | Wave 0 |
| ORAC-04 | tOracleOutput all 5 DATA_ACTIONs round-trip | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_output_e2e.py::test_data_actions` | Wave 0 |
| ORAC-04 | tOracleOutput batcherrors REJECT routing (duplicate PK) | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_output_e2e.py::test_reject_on_unique_violation` | Wave 0 |
| ORAC-04 | tOracleOutput INSERT_OR_UPDATE batched 2-statement | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_output_e2e.py::test_upsert` | Wave 0 |
| ORAC-04 | tOracleOutput USE_TIMESTAMP_FOR_DATE_TYPE preserves sub-second precision | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_output_e2e.py::test_timestamp_precision` | Wave 0 |
| ORAC-05 | Converter emits needs_review for OCI/Wallet on the 3 components | unit | `pytest tests/converters/talend_to_v1/components/test_oracle_connection.py::test_oci_wallet_needs_review` | existing file, new test |

### Sampling Rate

- **Per task commit:** `pytest tests/v1/engine/components/database/ -x --ignore=tests/v1/engine/components/database/integration`
- **Per wave merge:** Same as per-task plus `pytest tests/v1/engine/test_oracle_connection_manager.py -x`
- **Phase gate:** `pytest -m oracle tests/v1/engine/components/database/integration/ -x` MUST pass with a real `gvenzl/oracle-free` testcontainer running (per D-D3/D-F4)

### Wave 0 Gaps

- [ ] `tests/v1/engine/test_oracle_connection_manager.py` — manager unit tests (Wave 0 of plan 11-01)
- [ ] `tests/v1/engine/components/database/__init__.py` — package marker
- [ ] `tests/v1/engine/components/database/integration/__init__.py` — package marker
- [ ] `tests/v1/engine/components/database/integration/conftest.py` — testcontainers fixture (Wave 0 of plan 11-07)
- [ ] `tests/v1/engine/components/database/test_oracle_connection.py` — component unit tests (Wave 0 of plan 11-02)
- [ ] `tests/v1/engine/components/database/test_oracle_row.py` — component unit tests (Wave 0 of plan 11-03)
- [ ] `tests/v1/engine/components/database/test_oracle_output.py` — component unit tests (Wave 0 of plans 11-04, 11-05)
- [ ] `tests/v1/engine/components/database/integration/test_oracle_*_e2e.py` — integration tests (plan 11-07)
- [ ] Add `oracle = ["oracledb>=2.5,<4"]` extra and `oracle` marker in `pyproject.toml` (plan 11-01)

---

## Common Pitfalls

### Pitfall 1: oracledb.init_oracle_client() called twice in a process

**What goes wrong:** The second call raises with "init_oracle_client already called". This breaks pytest sessions that run multiple jobs.

**Why it happens:** Each ETLEngine instance creates a new OracleConnectionManager. If thick_mode is set across jobs, the manager naively calls init each time.

**How to avoid:** Use a class-level `_thick_initialized` guard on `OracleConnectionManager` (see API surface section). Alternative: check `oracledb.is_thin_mode()` before calling init.

**Warning signs:** Tests run individually pass but the full pytest suite fails on the second thick-mode test.

### Pitfall 2: Live Connection in globalMap

**What goes wrong:** Connection object is non-Arrow-serializable; the next `bridge._sync_from_java()` call (Phase 2 mandatory sync) throws.

**Why it happens:** Developer "helpfully" pushes the conn into globalMap to mirror Talend's `globalMap.put("conn_<cid>", conn)`.

**How to avoid:** Strict rule — only metadata strings in globalMap. Live Connections in OracleConnectionManager only. Code review checks for any `global_map.put(.*, conn)`.

**Warning signs:** Java-bridge sync errors that mention "object is not Arrow-compatible" right after an Oracle component runs.

### Pitfall 3: Mock cursor "passes" but real Oracle behaves differently

**What goes wrong:** Mock-based unit tests for tOracleOutput pass with a contrived `mock_cursor.executemany.return_value = None`. Real Oracle protocol does NULL/type coercion, encoding, and reject offset assignment differently than the mock.

**Why it happens:** Developer mocks `oracledb.Cursor.executemany` and `getbatcherrors()` with hardcoded values. The mock can't reproduce: NULL-coerce-to-default-vs-raise behavior, datetime sub-second preservation, BatchError offset accuracy, error code mapping.

**How to avoid:** Mandatory `@pytest.mark.oracle` integration tests (D-D3, D-F4). Phase 5.1 lesson: "mocks lie." For Oracle specifically, mocks cannot prove: (1) wire-protocol correctness, (2) type round-trip, (3) NULL handling, (4) BatchError offset/code accuracy, (5) DDL syntactic validity. ALL of these must be in integration tests.

**Warning signs:** Mock-only tests "100% pass" but the first real-DB run fails on edge cases.

### Pitfall 4: cursor.rowcount is -1 or None for DDL

**What goes wrong:** `tOracleRow.use_nb_line=NB_LINE_INSERTED` writes -1 or None to globalMap when query is `CREATE TABLE ...`.

**Why it happens:** oracledb's cursor.rowcount is implementation-defined for DDL — Oracle JDBC returns -1, oracledb may return -1 or None.

**How to avoid:** D-C5 — `if rowcount is None or rowcount < 0: rowcount = 0; logger.warning(...)`.

**Warning signs:** globalMap contains negative or None NB_LINE_INSERTED values.

### Pitfall 5: ad-hoc connection leaks on exception

**What goes wrong:** `tOracleRow` opens an ad-hoc connection in `_process()`, then raises (e.g., bad SQL). Connection never closes; manager has it dangling until `engine._cleanup()` (which runs eventually but not immediately).

**Why it happens:** No try/finally around the SQL execution path.

**How to avoid:** Wrap connection-using logic in try/finally with `oracle_manager.close(self.id)` in the finally block. The manager's `stop()` is a SAFETY NET, not the primary close path.

**Warning signs:** During iterate execution, observe ever-growing `manager.connections` dict size between iterations.

### Pitfall 6: NULL primary key partition error in INSERT_OR_UPDATE

**What goes wrong:** Input row has NULL PK column. SELECT-existing query never matches (NULL = NULL is UNKNOWN). Row partitioned as "unmatched" -> INSERT attempt -> may collide with existing NULL-PK row depending on table constraints.

**Why it happens:** Oracle three-valued logic for NULL comparison.

**How to avoid:** Log WARNING when input batch contains NULL key columns. Force NULL-key rows into INSERT path, document that Talend behavior may differ for these edge cases.

**Warning signs:** Some rows reported as "inserted" but the table's existing-row count doesn't match expectations.

### Pitfall 7: Partial commit when batcherrors and autocommit interact

**What goes wrong:** With `autocommit=True` and `batcherrors=True`, Oracle starts a transaction (does NOT autocommit per row even though autocommit=True). If the engine doesn't explicitly commit after the batch, all successfully-executed rows in the batch roll back when the connection closes.

**Why it happens:** Per the verified python-oracledb docs: "If errors occur, a transaction will be started but not committed, even if Connection.autocommit is set to True."

**How to avoid:** Always call `conn.commit()` explicitly after each batch when batcherrors=True is in play, regardless of autocommit setting.

**Warning signs:** After exception, no rows in the table even though batch reported "5 inserted, 3 errors".

---

## Code Examples

### Connection open per type (Source: oracledb 3.4.2 verified signature)

```python
# ORACLE_SID
conn = oracledb.connect(user=u, password=p, host=h, port=int(pt), sid=db)

# ORACLE_SERVICE_NAME
conn = oracledb.connect(user=u, password=p, host=h, port=int(pt), service_name=db)

# ORACLE_RAC (raw TNS descriptor)
conn = oracledb.connect(user=u, password=p, dsn=raw_rac_url.strip())
```

### executemany with batcherrors (Source: python-oracledb v2.4.0 batch_statement.rst, [CITED])

```python
import oracledb

cursor = conn.cursor()
cursor.setinputsizes(oracledb.NUMBER, 50, oracledb.DB_TYPE_TIMESTAMP)
cursor.executemany(
    "INSERT INTO emp (id, name, hired_at) VALUES (:1, :2, :3)",
    rows,
    batcherrors=True,
)
for err in cursor.getbatcherrors():
    print(f"Row {err.offset}: ORA-{err.code:05d} {err.message}")
conn.commit()
cursor.close()
```

### Init thick mode once per process

```python
import oracledb

if not OracleConnectionManager._thick_initialized:
    oracledb.init_oracle_client()  # call ONCE per process; second call raises
    OracleConnectionManager._thick_initialized = True
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `cx_Oracle` driver | `oracledb` thin/thick | 2022 (oracledb 1.0 release) | No Oracle Instant Client needed for thin mode; pure Python; same API |
| `oracledb.makedsn(host, port, sid=...)` | `oracledb.connect(host=..., port=..., sid=...)` direct kwargs | oracledb 1.0 deprecated `makedsn` (still functional) | Cleaner API; one fewer string assembly step |
| `cursor.executemany(sql, rows)` (no batcherrors) | `cursor.executemany(sql, rows, batcherrors=True)` | Long-standing oracledb feature | Per-row errors no longer fail the whole batch |

**Deprecated/outdated:**
- `cx_Oracle` — replaced by `oracledb`; same author (Oracle), oracledb is the spiritual successor with thin mode added.
- `oracledb.makedsn()` — deprecated since oracledb 1.0 but still functional. Prefer direct kwargs.

---

## Project Constraints (from CLAUDE.md)

- Tech stack locked to Python 3.10+ engine + Java 11+ bridge — no framework changes. **Phase 11 adds oracledb as a Python dependency only; no Java side changes.**
- **Compatibility constraint:** Must produce identical output to Talend for the same input data and job configuration. Phase 11 honored via D-B1 (schema-driven coercion), D-B2 (executemany behavior matches Talend's per-row + reject-set pattern), D-C1/C2 (full TABLE_ACTION × DATA_ACTION coverage).
- **No breaking changes:** Converter JSON format must remain compatible. Phase 11 adds optional `oracle_config` to the top-level job config (greenfield key, no existing job has it). Converter changes (D-E1) only ADD `needs_review` entries; do not modify config keys.
- **snake_case** for all Python modules, functions, methods, variables. Constants `UPPER_SNAKE_CASE`. Classes `PascalCase`. — All examples in this RESEARCH.md follow these rules.
- **ASCII-only logging** — no emojis, unicode arrows, box-drawing. Format `[<cid>] <message>`. Per project memory ("ASCII-only logging — RHEL servers need clean ASCII").
- **No `print()` in components** — `logger = logging.getLogger(__name__)` per module.
- **Custom exception hierarchy** — use `ConfigurationError`, `ComponentExecutionError`, `DataValidationError`, `FileOperationError`. Never raise generic `Exception`/`RuntimeError`/`ValueError`.
- **Type hints throughout.**
- **GSD workflow enforcement** — Phase 11 work must go through `/gsd-execute-phase`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The "16th" PARAMETER_TYPE in Talaxie's tOracleRow may include a `null`/`NULL` sentinel; web research source did not list the full enum verbatim | "USE_PREPAREDSTATEMENT 16-Type Coercion Table" | Low — plan should grep `tOracleRow_java.xml` directly to confirm full enum before locking the table; if a 17th value exists, just add another row to the dict |
| A2 | After Phase 11 ships, the existing engine_gap `needs_review` entry should be REMOVED for the 3 in-scope converters (oracle_connection / oracle_row / oracle_output); the converter unit tests currently assert on the gap entry being present | "Converter Update (D-E1)" | Medium — updating those test assertions is a planned task in plan 11-06; if missed, converter tests will fail |
| A3 | `gvenzl/oracle-free:23-slim-faststart` is the recommended image variant (faster than `:23-slim`); CONTEXT.md mentioned `:23-slim` | "Test Infrastructure: testcontainers + gvenzl/oracle-free" | Low — Claude's discretion per CONTEXT.md (test fixture design); easy to change if user prefers `:23-slim` |
| A4 | Talend tOracleOutput's `_tableActionForOutput.javajet` template path could not be fetched (404 on the URL guess); falling back to standard Oracle DDL grammar with conventional Talend type mappings | "Oracle DDL Emission From Engine Schema" | Medium — at integration test time, real DDL execution will validate the syntax; if Talend uses unusual non-standard DDL in any TABLE_ACTION, the integration test will surface it. Plan should locate the actual javajet path via a Talaxie repo grep before plan 11-04 starts. |
| A5 | `BINARY_FLOAT` / `BINARY_DOUBLE` are the right Oracle types for engine schema `float` / `double` columns; Talaxie may emit `NUMBER` for legacy parity | "Oracle DDL Emission From Engine Schema" | Low–Medium — `BINARY_FLOAT` is more correct (preserves IEEE 754) but `NUMBER` is what Talaxie likely emits. Resolve via Talaxie javajet inspection in plan 11-04 (open question below). |
| A6 | `errorCode = str(BatchError.code)` (Oracle error number) instead of Talaxie's SQLState; deliberate D-C7 divergence | "Reject Schema Parity (D-C7)" | Low — D-C7 explicitly endorses Oracle code over SQLState; documented as intentional |
| A7 | Auto-detect Oracle component types in ETLEngine __init__ instead of requiring `oracle_config.enabled=true` flag in job config | "Architectural Integration" | Low — code_context note recommends auto-detect; if user prefers explicit flag, trivial to flip |
| A8 | CONTEXT.md said `NotImplementedError` for OCI/Wallet; correct typed exception is `ConfigurationError` per the engine exception hierarchy | "JDBC URL → oracledb DSN Translation" | Very low — typed exceptions are the documented engine pattern; CONTEXT.md was using "NotImplementedError" colloquially |

---

## Open Questions (RESOLVED)

> All five questions are resolved — three at plan-execution time (the executor fetches Talaxie source as part of the plan task) and two in-research with documented decisions. None gate plan-checker approval.

1. **Talaxie tOracleOutput's exact `_tableActionForOutput.javajet` path and content** — **RESOLVED-AT-EXECUTION (plan 11-04 Task 1).**
   - Plan 11-04 Task 1 fetches the Talaxie template (cloning the repo if direct raw URL still 404s) before any DDL emitter code is written. Verify step asserts the executor documented the resolved Talaxie DDL conventions inline in `oracle_output.py`'s module docstring (`grep -E "Talaxie _tableActionForOutput.javajet"`). If the Talaxie source cannot be located, the executor falls back to standard Oracle SQL grammar (`NUMBER` for numeric, `VARCHAR2(n)` for string, `DATE` / `TIMESTAMP` for datetime, `BLOB` for bytes) and notes the deviation. Integration tests in 11-07 validate observable behavior regardless.

2. **Full PARAMETER_TYPE enum from `tOracleRow_java.xml`** — **RESOLVED-AT-EXECUTION (plan 11-03 Task 1).**
   - Plan 11-03 Task 1 fetches `tOracleRow_java.xml` from Talaxie at execution time and verifies the PARAMETER_TYPE enum verbatim. The 16-entry working list (String, Int, Integer, Long, Short, Byte, BigInteger, BigDecimal, Boolean, Float, Double, Date, Timestamp, Time, Bytes, Object) is the assumption — if Talaxie inspection finds exactly these 16, no change is needed; if a 17th value emerges, the executor extends the `_PARAM_TYPE_COERCERS` dict. The plan's `grep -c "def test_"` check enforces test-coverage parity with the resolved enum size.

3. **Does Talaxie tOracleOutput TABLE_ACTION use the PL/SQL guard pattern for CREATE_IF_NOT_EXISTS?** — **RESOLVED-AT-EXECUTION (plan 11-04 Task 1).**
   - Plan 11-04 Task 1 inspects the Talaxie javajet alongside the DDL fetch (Open Q 1) and locks the CREATE_IF_NOT_EXISTS pattern to whatever Talaxie emits. Default working pattern: PL/SQL anonymous block with `EXECUTE IMMEDIATE 'CREATE TABLE ...'` wrapped in `EXCEPTION WHEN OTHERS THEN IF SQLCODE = -955 THEN NULL; ELSE RAISE; END IF;` (industry-standard Oracle pre-23c idiom). Integration tests in 11-07 validate observable behavior — table exists post-execution, no error on second invocation.

4. **Composite primary key in INSERT_OR_UPDATE — OR-chain vs temp-table threshold?** — **RESOLVED.**
   - Phase 11 uses OR-chain for ALL batch sizes. Talend's `BATCH_SIZE` default is 10000; at typical 2–4 PK columns and ~30 chars per identifier, max SQL string size for the SELECT-existing query stays under 50 KB — well within Oracle's parser limits via JDBC/oracledb thin. Temp-table optimization deferred to a future perf phase if production measurements show parser overhead. Recorded in 11-CONTEXT.md deferred-items.

5. **Should `oracle_config` be schema-validated by the engine?** — **RESOLVED.**
   - Light validation only — `OracleConnectionManager.__init__` casts `thick_mode` and any other booleans to `bool` defensively, and logs a `WARNING` on unrecognized `oracle_config` keys. No formal JSON schema in Phase 11. Trust the converter / job author for the rest. Implemented in plan 11-01 Task 2.

---

## Sources

### Primary (HIGH confidence)
- python-oracledb 2.4.0 user_guide/batch_statement.rst — `cursor.executemany(sql, rows, batcherrors=True)` signature and `getbatcherrors()` return
- python-oracledb 3.4.2 connect() signature — verified via `inspect.signature(oracledb.connect)` in venv
- python-oracledb DB_TYPE_* constants — verified via direct import in venv (oracledb 3.4.2)
- `src/v1/engine/java_bridge_manager.py` — direct file read, the exact reference template
- `src/v1/engine/python_routine_manager.py` — direct file read
- `src/v1/engine/engine.py` lines 1–260 — direct file read for integration line numbers
- `src/v1/engine/base_component.py` lines 1–120, 900–1100, 1300–1370 — direct file read for `_coerce_column_type`, `_apply_decimal_precision`, lifecycle, reset
- `src/converters/talend_to_v1/components/database/oracle_*.py` — direct file reads for JSON shape
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` — direct file read for the 12 rules and gold standard
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` — direct file read for Rule 11/12 carryover
- `docs/v1/audit/components/database/tOracleConnection.md` — direct file read for parameter matrix and behavioral notes
- `Talaxie tOracleConnection_begin.javajet` (raw.githubusercontent.com) — verbatim URL formats per CONNECTION_TYPE
- `pyproject.toml` — direct file read for dependency strategy

### Secondary (MEDIUM confidence)
- `python-oracledb` exception_handling docs — `Error.code`/`full_code`/`message` attributes confirmed via web search; example usage shown in user guide
- `gvenzl/oracle-free` Docker Hub README — image variant recommendations
- python-oracledb deprecations — `makedsn()` deprecated since 1.0 but functional in 3.4.2

### Tertiary (LOW confidence — flagged in Open Questions)
- Exact path and content of Talaxie's `_tableActionForOutput.javajet` (URL 404'd; DDL templates inferred from standard Oracle SQL grammar) — Open Question 1
- 16th PARAMETER_TYPE in tOracleRow enum (CONTEXT.md says 16; only 15 confirmed) — Open Question 2

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — oracledb verified installed (3.4.2), Talaxie URL formats verified, all DB_TYPE_* constants verified at import time
- OracleConnectionManager API: HIGH — direct mirror of JavaBridgeManager (read in full)
- Architectural integration: HIGH — exact line numbers (41/67/142/229/233) verified in engine.py
- Type binding: HIGH — DB_TYPE_* constants verified
- DDL emission templates: MEDIUM — Oracle standard SQL grammar is well-documented; Talaxie's exact templates not located (Open Q 1)
- INSERT_OR_UPDATE pattern: HIGH — D-C2 locks it, math is straightforward
- 16-type coercion table: MEDIUM — 15/16 confirmed; 16th is Open Q 2
- Test infrastructure: HIGH — testcontainers pattern is industry standard
- Pitfalls: HIGH — drawn from project memory (Phase 5.1 mocks-lie lesson) plus oracledb-specific verified gotchas

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (30 days for stable; oracledb 4.0 may release in this window — re-verify version pin if so)
