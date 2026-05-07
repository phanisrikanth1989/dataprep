# Phase 11: Oracle Components - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver three Oracle engine components plus the connection-sharing infrastructure that the entire Oracle component family depends on:

1. **`OracleConnectionManager`** — new manager class on `ETLEngine` (analog to `JavaBridgeManager` / `PythonRoutineManager`); owns lifecycle of all live `oracledb.Connection` objects; idempotent `stop()` integrated into `ETLEngine._cleanup()` so connections cannot leak.
2. **`tOracleConnection`** engine component — opens connection per `CONNECTION_TYPE`, registers it in the manager keyed by component id; downstream Oracle components reference it via `USE_EXISTING_CONNECTION + CONNECTION`.
3. **`tOracleRow`** engine component — executes arbitrary SQL/DDL/DML, ad-hoc or shared connection, with full `USE_PREPAREDSTATEMENT` support and `USE_NB_LINE` opt-in stat counting.
4. **`tOracleOutput`** engine component — writes DataFrames using full Talend coverage (8 `TABLE_ACTION` × 5 `DATA_ACTION`), batched via `cursor.executemany(batcherrors=True)`, with `COMMIT_EVERY` cycle and `REJECT` flow capturing per-row errors.

Plus a small converter update so jobs configured with `ORACLE_WALLET` / `ORACLE_OCI` connection types emit a `needs_review` entry pointing at the new `oracle_config.thick_mode` job-level flag.

**Driver mode:** `oracledb` thin by default (pure Python, no Oracle Client install on RHEL). Per-job thick escape hatch via `job_config['oracle_config']['thick_mode']: true` calls `oracledb.init_oracle_client()` once when the manager starts.

**Connection types in scope:** `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC` — fully implemented and integration-tested. `ORACLE_OCI` and `ORACLE_WALLET` raise `NotImplementedError` with a clear message pointing at the deferred items list and the `thick_mode` flag.

**Deferred and explicitly out of scope (engine still missing them; converters Green):**
- tOracleInput, tOracleSP, tOracleBulkExec, tOracleCommit, tOracleRollback, tOracleClose engine components — later phase(s)
- `ORACLE_OCI` and `ORACLE_WALLET` runtime support (URL builders, wallet auth) — when a real production job needs it
- `tOracleRow.PROPAGATE_RECORD_SET` — Talend-specific live `ResultSet`-as-FLOW-column, doesn't translate cleanly to DataFrame semantics; ConfigurationError when set true
- `tOracleInput.IS_CONVERT_XMLTYPE` / `CONVERT_XMLTYPE` table — XMLType column-mapping, only relevant for tOracleInput
- `BaseDbConnection` / `BaseDbInput` / `BaseDbOutput` abstractions — refactor when the MSSql phase ships with 2+ vendor implementations
- Replacing the hybrid mock-default test strategy with default-CI Docker fixtures — when ops can run testcontainers in CI

</domain>

<decisions>
## Implementation Decisions

### A. Connection persistence & lifecycle

- **D-A1:** Live `oracledb.Connection` objects live in a new `OracleConnectionManager` instance attached to `ETLEngine`, keyed by the registering component's id (e.g., `tOracleConnection_1`). Exact analog to `JavaBridgeManager` / `PythonRoutineManager`. `globalMap` retains Talend-parity metadata strings only (`{cid}_NB_LINE_INSERTED` etc.) — never holds live Connection objects (the Java bridge globalMap-sync would fail for non-serializable Python objects). Components access via `engine.oracle_manager.get(connection_ref)`.

- **D-A2:** Driver mode = `oracledb` thin by default (pure Python, zero Oracle Client install on RHEL), with per-job thick escape hatch. When `job_config['oracle_config']['thick_mode']` is true, `OracleConnectionManager.start()` calls `oracledb.init_oracle_client()` exactly once before any connect call. Default false. Must be set per job. Charset note: thin handles AL32UTF8, WE8MSWIN1252, ISO-8859-15 and all common Oracle charsets natively; thin ignores client-side `NLS_LANG` env var (decodes per server NLS_CHARACTERSET) — strictly more correct than Talend's behavior, only deviates for jobs that intentionally relied on `NLS_LANG`-based re-encoding.

- **D-A3:** `CONNECTION_TYPE` scope: `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC` are fully implemented and integration-tested. `ORACLE_OCI` and `ORACLE_WALLET` raise `NotImplementedError` with the message: `"CONNECTION_TYPE %s requires oracledb thick mode + Oracle Instant Client. Set oracle_config.thick_mode=true in job config and install Instant Client on the host. Tracked in deferred items."` No silent fallback.

- **D-A4:** Lifecycle (Talend-parity, with deterministic safety-net cleanup):
  - **Ad-hoc connection** (`USE_EXISTING_CONNECTION=false` on tOracleRow / tOracleOutput): manager opens at component `_prepare()` (or first SQL exec), final commit of trailing batch in `finalize()`, close in `finalize()`. Identical to Talend `_begin.javajet` open + `_end.javajet` `commit() + close()`.
  - **Shared connection** (`tOracleConnection`): opens in `tOracleConnection._process()`, registered with manager. Persists across the job. Closed at: (a) explicit `tOracleClose` (out of Phase 11 scope but manager API supports `manager.close(cid)`), (b) `engine._cleanup()` safety net via `oracle_manager.stop()`.
  - **`AUTO_COMMIT` advanced param** on tOracleConnection (default false) honored — manager calls `conn.autocommit = bool(auto_commit_param)` after open. Downstream components see the connection's autocommit setting and behave accordingly.
  - **Uncommitted work at close**: `oracledb.Connection.close()` rolls back uncommitted (matches Talend Oracle JDBC behavior). No explicit pre-close commit unless component logic dictates.

- **D-A4b:** `OracleConnectionManager.stop()` iterates `self.connections.values()` and closes each in a try/except so one bad close doesn't block the rest; clears the dict. Idempotent. Called from `ETLEngine._cleanup()` (which already runs on success path `engine.py:192`, exception path `engine.py:198`, and `__del__` `engine.py:241`) right alongside `java_bridge_manager.stop()`. Connection leaks impossible even on job exception.

### B. Type mapping & transactions

- **D-B1:** Schema-driven type coercion (Talend-parity). On read (tOracleRow with FLOW out, future tOracleInput): cursor returns `oracledb`-default Python types; we coerce per the engine schema column type using existing `BaseComponent._coerce_column_type` (precedent `base_component.py:1067-1069`). NUMBER → `Decimal` (lossless) when schema is `Decimal`; → `int` for `int`/`long` schemas; → `float` for `float`/`double` schemas. DATE / TIMESTAMP → `datetime` via `pd.Timestamp`. TIMESTAMP WITH (LOCAL) TIMEZONE → tz-aware `datetime`. CLOB / BLOB → `str` / `bytes` (`oracledb.defaults.fetch_lobs = False` set globally in `OracleConnectionManager.__init__`). XMLTYPE → `str` for tOracleRow (XMLTYPE-table handling deferred to tOracleInput later phase).

  On write (tOracleOutput): bind via `cursor.setinputsizes()` per schema column — explicit `oracledb.NUMBER` / `.DB_TYPE_DATE` / `.DB_TYPE_TIMESTAMP_TZ` / `.CLOB` / `.BLOB`. Honor `USE_TIMESTAMP_FOR_DATE_TYPE` (default true): when true, DATE columns are bound with `DB_TYPE_TIMESTAMP` not `DB_TYPE_DATE` to preserve sub-second precision (matches Talend). `TRIM_CHAR` honored on read for CHAR-typed columns.

- **D-B2:** tOracleOutput batching strategy = `cursor.executemany(sql, rows, batcherrors=True)` unconditionally — single code path, no Talend-style "disable batching when REJECT is wired". Without REJECT: executemany runs, commit at COMMIT_EVERY threshold. With REJECT: same call but read `cursor.getbatcherrors()` after each batch — each `BatchError` carries `offset`, `code`, and `message`. Build the reject DataFrame from those. NB_LINE_REJECTED summed across batches. Same observable behavior as Talend (same rows succeed, same rows fail with same error info), 5–50× faster at protocol level, single test surface. Trailing partial batch handled in `finalize()`.

### C. tOracleRow & tOracleOutput component semantics

- **D-C1:** tOracleOutput supports the **full Talend coverage**: 8 `TABLE_ACTION` (`NONE`, `CREATE`, `CREATE_IF_NOT_EXISTS`, `DROP_CREATE`, `DROP_IF_EXISTS_AND_CREATE`, `CLEAR` = `DELETE FROM`, `TRUNCATE`, `TRUNCATE_REUSE_STORAGE` = `TRUNCATE TABLE x REUSE STORAGE`) × 5 `DATA_ACTION` (`INSERT`, `UPDATE`, `INSERT_OR_UPDATE`, `UPDATE_OR_INSERT`, `DELETE`). CREATE-family actions emit Oracle DDL from engine schema column types (`NUMBER(p,s)` from Decimal precision/scale, `VARCHAR2(n)` from string length, `DATE` / `TIMESTAMP` from datetime, `CLOB` / `BLOB` from string-large / bytes). Each TABLE_ACTION is an isolated SQL emitter; one per — easy to test in isolation.

- **D-C2:** `INSERT_OR_UPDATE` / `UPDATE_OR_INSERT` strategy = batched 2-statement (Talend semantic parity, faster than per-row). Per batch of N rows: (1) `SELECT pk_cols FROM table WHERE pk IN (batch_keys)` — one round trip identifies matched keys; (2) partition input rows into matched / unmatched; (3) `executemany UPDATE` for matched, `executemany INSERT` for unmatched. Stats split correctly: `NB_LINE_UPDATED += matched_count`, `NB_LINE_INSERTED += unmatched_count`. Not Oracle MERGE (avoids cursor.rowcount aggregate-only stats and small parity edge cases). Approx 3× slower than MERGE, ~10× faster than per-row Talend.

- **D-C3:** tOracleRow `USE_PREPAREDSTATEMENT` ships with full coverage of the 16 Talaxie `PARAMETER_TYPE` values. Static lookup table maps each Java-type name to a Python coercion call:
  ```
  String     → str          Int / Long / Short / Byte / BigInteger → int
  BigDecimal → Decimal      Boolean    → bool
  Float / Double → float    Date       → datetime.date
  Timestamp  → datetime.datetime       Time → datetime.time
  Bytes      → bytes        Object     → pass-through (oracledb infers)
  ```
  `PARAMETER_VALUE` is resolved through the existing engine resolution pipeline first ({{java}} expressions, ContextManager, GlobalMap), then coerced. Bind via `cursor.execute(sql, [vals])`. Configuration validation in `_process` (Phase 7.1 Rule 12).

- **D-C4:** tOracleRow `PROPAGATE_RECORD_SET` deferred. When `propagate_record_set=true`, raise `ConfigurationError`: `"tOracleRow PROPAGATE_RECORD_SET emits a live ResultSet to a downstream FLOW column; this Talend pattern doesn't translate cleanly to DataFrame semantics. Tracked in deferred items — rewrite as tOracleInput → downstream component when this is needed."` Most production jobs do not use it.

- **D-C5:** tOracleRow `USE_NB_LINE` = trivial. After `cursor.execute()` (or `executemany()` for the prepared-statement path), if `config['use_nb_line']` is one of `NB_LINE_INSERTED` / `NB_LINE_UPDATED` / `NB_LINE_DELETED`: set `globalMap[f'{cid}_<chosen>'] = cursor.rowcount`. `NONE` → don't set anything. DDL (`cursor.rowcount` is `-1` or `None`) → set `0` and log a WARNING that DDL stats aren't meaningful.

- **D-C6:** `USE_FIELD_OPTIONS` per-column flags on tOracleOutput honored: when `use_field_options=true`, the FIELD_OPTIONS table provides per-column `UPDATE_KEY` / `DELETE_KEY` / `UPDATABLE` / `INSERTABLE`. Without it, the schema's "Key" attribute drives the WHERE clause and all non-key columns are updatable + insertable (Talend default).

- **D-C7:** Reject schema for tOracleRow / tOracleOutput = `[errorCode (str), errorMessage (str), <input columns>]`. `errorCode` from `BatchError.code` (Oracle error number, e.g. `1` for ORA-00001). `errorMessage` from `BatchError.message + " - Line: <row_offset>"` (Talend-parity formatting).

- **D-C8:** Stat globalMap keys (matching Talend `_AFTER` availability):
  - tOracleConnection: none (Talend has no RETURN section).
  - tOracleRow: `{cid}_NB_LINE_INSERTED` / `{cid}_NB_LINE_UPDATED` / `{cid}_NB_LINE_DELETED` per `USE_NB_LINE` selection. `{cid}_QUERY` (the resolved SQL string, available during FLOW per Talend RETURN spec).
  - tOracleOutput: `{cid}_NB_LINE`, `{cid}_NB_LINE_INSERTED`, `{cid}_NB_LINE_UPDATED`, `{cid}_NB_LINE_DELETED`, `{cid}_NB_LINE_REJECTED`.

### D. Architecture & test infrastructure

- **D-D1:** Oracle-specific implementation now; no `BaseDbConnection` / `BaseDbInput` / `BaseDbOutput` abstractions in Phase 11. The 2 existing MSSql converters (`mssql_connection.py`, `mssql_input.py`) stay engine-unimplemented; a future MSSql phase extracts shared base classes informed by 2+ concrete vendor implementations. Aligns with project memories *"Phase scope boundaries — don't do global sweeps"* and *"don't design for hypothetical future requirements"*.

- **D-D2:** New engine package `src/v1/engine/components/database/` with `oracle_connection.py`, `oracle_row.py`, `oracle_output.py`, `__init__.py`. New top-level engine module `src/v1/engine/oracle_connection_manager.py`. Registration via existing decorator pattern: `@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")` (mirror converter dual-registration), `@REGISTRY.register("OracleRow", "tOracleRow")`, `@REGISTRY.register("OracleOutput", "tOracleOutput")`.

- **D-D3:** Hybrid test strategy. Unit tests use `unittest.mock` for `oracledb.Cursor` / `Connection` — fast, run by default in `pytest`. Integration tests under `tests/v1/engine/components/database/integration/` marked `@pytest.mark.oracle`, using `testcontainers-python` + `gvenzl/oracle-free:23-slim` (~300 MB, boots ~30–60 s). Skipped by default; runnable opt-in via `pytest -m oracle`.

  **Phase-end verification gate** (mitigation for Phase 5.1 "mocks lie" risk): `gsd-verify-work` for Phase 11 must require running `pytest -m oracle` against a `gvenzl/oracle-free` testcontainer at least once before the phase is marked verified. Mocks alone cannot demonstrate Talend parity — this captures the lesson without forcing CI-side Docker. Document this explicitly in `11-VERIFICATION.md`.

- **D-D4:** `pyproject.toml` updates:
  - New extra: `oracle = ["oracledb>=2.5,<4"]`
  - `dev` extras add: `testcontainers>=4` (import-guarded so it's optional even within dev installs)
  - New pytest marker: `oracle: Tests requiring an Oracle DB testcontainer (slow, opt-in)` — register in the `[tool.pytest.ini_options].markers` list.

### E. Converter scope additions (small, inline)

- **D-E1:** Converter update — `oracle_connection.py`, `oracle_row.py`, `oracle_output.py`: when `connection_type in {ORACLE_WALLET, ORACLE_OCI}`, emit a `needs_review` entry: `"Connection type %s requires oracle_config.thick_mode=true in job config, plus Oracle Instant Client on the host. Phase 11 raises NotImplementedError until thick_mode is set."` Keep existing engine-gap entries removed once the engine ships (replace with thick-mode-only review for those types). Ship in a dedicated sub-phase plan with converter unit tests.

### F. Phase 11 sub-phase plan (anticipatory — planner finalizes)

- **D-F1:** Recommended sub-phase split (planner may adjust):
  - **11-01**: `OracleConnectionManager` + `ETLEngine` integration + `_cleanup` wiring + `pyproject.toml` extras (`oracle`, `testcontainers`, `oracle` marker) + manager unit tests
  - **11-02**: tOracleConnection engine component (5 connection-type URL builders with NotImplementedError for OCI/Wallet, thin/thick init, `AUTO_COMMIT`, register-to-manager, ASCII logging) + unit tests
  - **11-03**: tOracleRow engine component (USE_EXISTING_CONNECTION + ad-hoc, USE_PREPAREDSTATEMENT 16-type table, USE_NB_LINE counter, DIE_ON_ERROR + reject, PROPAGATE_RECORD_SET ConfigurationError) + unit tests
  - **11-04**: tOracleOutput engine component, part 1 — schema-driven DDL emitter for 8 TABLE_ACTIONs, INSERT/UPDATE/DELETE prepared statements, executemany+batcherrors+commit cycle, FIELD_OPTIONS, USE_TIMESTAMP_FOR_DATE_TYPE — + unit tests
  - **11-05**: tOracleOutput INSERT_OR_UPDATE / UPDATE_OR_INSERT batched 2-statement logic + unit tests
  - **11-06**: Converter update (Wallet/OCI `needs_review` for the 3 components in scope) + converter unit tests
  - **11-07**: Hybrid integration tests — testcontainers fixture + `@pytest.mark.oracle` E2E for the 3 `.item` samples (`Job_tOracleConnection_0.1.item`, `Job_tOracleRow_0.1.item`, `Job_tOracleOutput_0.1.item`) + verification gate doc

- **D-F2:** All new engine components conform to `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` gold standard (Phase 1 D-16 carryover). All new tests conform to `docs/v1/standards/ENGINE_TEST_PATTERN.md`.

- **D-F3:** Phase 7.1 Rule 12 carryover: content checks (e.g., URL syntactic validity, schema column type validity for DDL emission) belong in `_process()`, NOT `_validate_config()`. `_validate_config` only validates structural correctness (required keys present, enum values in allowed set), never resolved values.

- **D-F4:** Phase 5.1 lesson carryover: `@pytest.mark.oracle` integration tests are mandatory at the phase verification gate (D-D3). Mocks of `oracledb.Cursor` / `Connection` give false confidence — at least one real-DB test per shipped component before Phase 11 is verified.

### Claude's Discretion

- Internal class structure of `OracleConnectionManager` (private helpers for URL building per connection type, `_open_ad_hoc()` vs `_open_shared()` split, exact docstring format)
- Exact stats dataclass / dict shape for per-component execution stats
- Internal SQL-emitter helper organization for tOracleOutput's 8 TABLE_ACTIONs (one method each vs dispatch table — pick whichever reads cleaner)
- Test fixture design for testcontainers: where the docker-compose-equivalent lives (`tests/conftest.py` vs a new `tests/oracle_fixture.py`)
- Reject DataFrame buffer strategy (in-memory list of small DataFrames vs concat-on-finalize — choose based on memory profile)
- Whether to expose a public `engine.oracle_manager` attribute or keep it private with a getter
- Exact log message wording for D-A2 thick-mode init success/failure (the spec is "ASCII-only, prefix with `[<cid>]` where applicable"; precise text is discretion)
- DDL string formatting (uppercase keywords vs lowercase, line breaks, indentation) — pick one style and stay consistent

### Folded Todos

None for this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Talaxie source of truth (Talend feature baseline)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleConnection/tOracleConnection_java.xml` — tOracleConnection params: 5 CONNECTION_TYPEs (SID/SERVICE_NAME/OCI/RAC/WALLET), AUTO_COMMIT advanced (default false), SUPPORT_NLS, USE_TNS_FILE, SSL params (RAC + 12/18 only)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleConnection/tOracleConnection_begin.javajet` — JDBC URL formats per CONNECTION_TYPE; `globalMap.put("conn_<cid>", conn)` + 4 metadata keys (`connectionType_<cid>`, `dbschema_<cid>`, `username_<cid>`, `password_<cid>`); SharedDBConnection.getDBConnection for shared-pool semantics
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleRow/tOracleRow_java.xml` — params (USE_EXISTING_CONNECTION, USE_NB_LINE enum, USE_PREPAREDSTATEMENT, SET_PREPAREDSTATEMENT_PARAMETERS table, PROPAGATE_RECORD_SET, COMMIT_EVERY default 10000); RETURN: NB_LINE_UPDATED / NB_LINE_INSERTED / NB_LINE_DELETED (AFTER), QUERY (FLOW)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleRow/tOracleRow_begin.javajet` — confirms USE_NB_LINE counter init pattern; URL construction per connection type when ad-hoc
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleRow/tOracleRow_end.javajet` — globalMap key push pattern (`"<cid>_NB_LINE_INSERTED"` etc.); inherits AbstractDBRowEnd for cleanup
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleOutput/tOracleOutput_java.xml` — full param list incl. 8 TABLE_ACTION values, 5 DATA_ACTION values, FIELD_OPTIONS table semantics (UPDATE_KEY / DELETE_KEY / UPDATABLE / INSERTABLE), USE_BATCH_SIZE/BATCH_SIZE/COMMIT_EVERY (all default 10000), USE_TIMESTAMP_FOR_DATE_TYPE (default true), TRIM_CHAR (default true), reject schema (errorCode + errorMessage), RETURN (NB_LINE / NB_LINE_INSERTED / NB_LINE_UPDATED / NB_LINE_DELETED / NB_LINE_REJECTED, all AFTER)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleOutput/tOracleOutput_begin.javajet` — connection acquisition (existing vs new), prepared statement construction per DATA_ACTION incl. INSERT_OR_UPDATE 2-statement pattern (`SELECT COUNT(1) FROM ... WHERE pk` then UPDATE-or-INSERT, NOT MERGE); auto-commit/COMMIT_EVERY wiring
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleOutput/tOracleOutput_main.javajet` — per-row binding (type-specific setX calls), null handling (`setBooleanForNullableKeyStmt` when SUPPORT_NULL_WHERE), batch flush at COMMIT_EVERY/BATCH_SIZE thresholds, reject row construction on `SQLException` (errorCode = `SQLState`, errorMessage = `e.getMessage() + " - Line: " + count`)

### Sample Talend jobs (integration test fixtures)
- `tests/talend_xml_samples/Job_tOracleConnection_0.1.item` — connection-only iterate flow
- `tests/talend_xml_samples/Job_tOracleRow_0.1.item` — tOracleConnection → tOracleRow (likely DDL/DML flow with connection sharing)
- `tests/talend_xml_samples/Job_tOracleOutput_0.1.item` — tOracleConnection → … → tOracleOutput (write flow)

### Internal audit reports (production readiness state, dated 2026-04-03)
- `docs/v1/audit/components/database/tOracleConnection.md` — converter G (Green, 28 of 28 params), engine R (no implementation), 5 connection types documented with full param matrix
- `docs/v1/audit/components/database/tOracleRow.md` — converter G, engine R; documents PROPAGATE_RECORD_SET / USE_PREPAREDSTATEMENT / USE_NB_LINE
- `docs/v1/audit/components/database/tOracleOutput.md` — converter G (26 of 26 params), engine R; documents 8 TABLE_ACTION × 5 DATA_ACTION matrix and FIELD_OPTIONS semantics
- `docs/v1/audit/components/database/tOracleInput.md`, `tOracleSP.md`, `tOracleBulkExec.md`, `tOracleCommit.md`, `tOracleRollback.md`, `tOracleClose.md` — out of Phase 11 scope but inform the OracleConnectionManager API (must support `manager.commit(cid)` / `rollback(cid)` / `close(cid)` for future commit/rollback/close components)

### Project standards
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` — gold-standard structure for new engine components (D-F2)
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` — engine test structure (D-F2)
- `docs/v1/standards/CONVERTER_PATTERN.md` — converter structure rules (D-E1 update)
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` — Phase 7.1 Rule 12 (content checks in `_process`, not `_validate_config`) (D-F3)

### Engine infrastructure to extend
- `src/v1/engine/engine.py` — `ETLEngine.__init__` (lines 31–109), `_initialize_components` (line 111), `_cleanup` (line 229) — add `oracle_manager` instantiation alongside `java_bridge_manager` (line 41) and `python_routine_manager` (line 59); call `oracle_manager.stop()` in `_cleanup` (line 233)
- `src/v1/engine/java_bridge_manager.py` — exact reference template for `OracleConnectionManager`: `start()` / `stop()` / `is_available()` / context-manager / repr pattern
- `src/v1/engine/python_routine_manager.py` — second reference for the manager pattern
- `src/v1/engine/base_component.py` — `_coerce_column_type` (existing precedent for schema-driven type coercion), `_apply_decimal_precision` (line 1067) for Decimal handling, `reset()` (line 1336) for between-iteration cleanup if reused
- `src/v1/engine/component_registry.py` — iterate components register via `@REGISTRY.register` decorator pattern (Phase 3 D-04)
- `src/v1/engine/exceptions.py` — `ConfigurationError`, `ComponentExecutionError`, `DataValidationError`, `FileOperationError` already defined; add a small NotImplementedError pattern when raising for Wallet/OCI

### Engine components to create
- `src/v1/engine/oracle_connection_manager.py` — TO BE CREATED per D-A1, D-A4, D-A4b
- `src/v1/engine/components/database/__init__.py` — TO BE CREATED to register the database package
- `src/v1/engine/components/database/oracle_connection.py` — TO BE CREATED per D-A1..A4
- `src/v1/engine/components/database/oracle_row.py` — TO BE CREATED per D-C3, D-C4, D-C5, D-C7, D-C8
- `src/v1/engine/components/database/oracle_output.py` — TO BE CREATED per D-B1, D-B2, D-C1, D-C2, D-C6, D-C7, D-C8

### Converter source (existing — small Phase 11 update)
- `src/converters/talend_to_v1/components/database/oracle_connection.py` — Green; D-E1 adds `needs_review` for ORACLE_WALLET / ORACLE_OCI
- `src/converters/talend_to_v1/components/database/oracle_row.py` — Green; D-E1 same update
- `src/converters/talend_to_v1/components/database/oracle_output.py` — Green; D-E1 same update
- Other 6 Oracle converters (`oracle_input.py`, `oracle_sp.py`, `oracle_bulk_exec.py`, `oracle_commit.py`, `oracle_rollback.py`, `oracle_close.py`) — Green, no Phase 11 changes (engine implementations deferred)

### Build / packaging
- `pyproject.toml` — add `oracle = ["oracledb>=2.5,<4"]` extra, add `testcontainers>=4` to `dev`, add `oracle` to `[tool.pytest.ini_options].markers` (D-D4)
- `oracledb` already installed in the venv (v3.4.2 verified); the extra makes it explicit and pins the supported range

### Prior phase carryovers
- Phase 1 D-16 — All engine components conform to ENGINE_COMPONENT_PATTERN.md (D-F2)
- Phase 1 — `BaseComponent` `_original_config` deepcopy and `reset()` infrastructure available if iterate-driven Oracle components emerge later
- Phase 2 — JavaBridgeManager pattern is the exact template for `OracleConnectionManager` (D-A1, D-A4b)
- Phase 3 D-04 — `@REGISTRY.register` decorator pattern with PascalCase + Talend aliases (D-D2)
- Phase 5.1 — Always include `@pytest.mark.<integration>` integration tests; mocks lie — Phase 11 analog is `@pytest.mark.oracle` (D-D3, D-F4)
- Phase 7.1 Rule 12 — Content checks belong in `_process`, not `_validate_config` (D-F3)
- Phase 8 D-11 — Secure Python execution namespace for python_component / python_row_component is precedent for clean component-side integration with shared infrastructure managers (PythonRoutineManager pattern)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`JavaBridgeManager`** (`src/v1/engine/java_bridge_manager.py`) — exact reference for the `start()` / `stop()` / `is_available()` / context-manager / `__repr__` pattern. Phase 11 manager mirrors this structure.
- **`ETLEngine.__init__` lines 41–67** — pattern for conditionally instantiating a manager based on `job_config.<feature>_config.enabled` and starting it. Phase 11 adds `oracle_config` reading for `thick_mode` (and optionally `enabled` once a job has any Oracle component).
- **`ETLEngine._initialize_components`** (line 111) — wires manager instances onto components (`component.java_bridge = self.java_bridge_manager.bridge`). Phase 11 adds `component.oracle_manager = self.oracle_manager`.
- **`ETLEngine._cleanup` (line 229)** — already handles `java_bridge_manager.stop()`; Phase 11 adds `oracle_manager.stop()` at the same site. Already called from success path (line 192), exception path (line 198), and `__del__` (line 241).
- **`BaseComponent._coerce_column_type` and `_apply_decimal_precision`** (`base_component.py:1067-1069`, around line 950) — established precedent for schema-driven coercion and Decimal precision rounding. Phase 11 reuses for tOracleRow / tOracleOutput on read paths.
- **`@REGISTRY.register` decorator pattern** (engine `component_registry.py`) — `OracleConnection`, `OracleRow`, `OracleOutput` register identically with PascalCase + tXxx aliases.
- **`ConfigurationError` / `ComponentExecutionError`** (`exceptions.py`) — used for Wallet/OCI NotImplementedError paths and PROPAGATE_RECORD_SET path.
- **Existing converter classes** (`src/converters/talend_to_v1/components/database/oracle_*.py`) — already extract 100% of Talaxie params; engine just consumes the JSON. The 9 converter unit-test files in `tests/converters/talend_to_v1/components/database/` give us pre-existing ground truth.

### Established patterns (constraints)
- **`ENGINE_COMPONENT_PATTERN.md` gold standard**: every new engine component follows the structure (module docstring with full Config Mapping, `@REGISTRY.register` with multiple aliases, `_validate_config` raises ConfigurationError, `_process` returns `{main, reject, stats}` dict).
- **Phase 7.1 Rule 12**: Content checks (URL syntax, schema column type validity for DDL emission, query SQL correctness) belong in `_process`, NOT `_validate_config`. `_validate_config` runs BEFORE context resolution, so it cannot trust resolved values.
- **ASCII-only logging** (project memory): no emojis, no unicode arrows, no box-drawing. Format `[<cid>] <message>`. RHEL servers consume logs that must stay ASCII.
- **`@pytest.mark.<integration>` integration tests** (Phase 5.1 lesson): mocks of `oracledb.Cursor` / `Connection` give false confidence. Phase 11 analog: `@pytest.mark.oracle` against testcontainers. At least one real-DB test per shipped component before phase verification.
- **`globalMap` is a Python-Java shared key/value store**, synced via `bridge._sync_from_java()` in Phase 2's per-call sync. Live `oracledb.Connection` objects MUST NOT be pushed into globalMap (non-Arrow-serializable). Live connections live in the manager; metadata strings live in globalMap.

### Integration points
- **`ETLEngine.__init__`**: instantiate `OracleConnectionManager` after `python_routine_manager` (around line 67); call `manager.start()` if any Oracle component is present in `job_config['components']` OR if `oracle_config.enabled` is true. (Implementation choice — auto-detect from component types is simpler than requiring users to set the flag.)
- **`ETLEngine._initialize_components`**: when a component class has an `oracle_manager` attribute set requirement (BaseComponent subclasses can declare this), wire it: `component.oracle_manager = self.oracle_manager`.
- **`ETLEngine._cleanup`**: add `if self.oracle_manager: self.oracle_manager.stop()` immediately after the existing `java_bridge_manager.stop()` call (line 233).
- **Component `_process`**: read `self.oracle_manager.get(self.config['connection'])` when `use_existing_connection=True`; otherwise call `self.oracle_manager.open_ad_hoc(self.id, self.config)` to acquire and `self.oracle_manager.close(self.id)` (or `register_close_at_finalize`) at end.
- **Reject flow**: existing `OutputRouter` handles REJECT routing without changes — Phase 11 components produce `{main: ..., reject: ..., stats: ...}` from `_process`, OutputRouter does the rest.
- **Java bridge**: not used by Oracle components directly. Java expressions in tOracleRow's `QUERY` (e.g., `context.var` interpolation) go through the existing `{{java}}` resolution pipeline before the SQL is sent to oracledb — no Oracle-specific java-bridge work needed.

</code_context>

<specifics>
## Specific Ideas

- **User direction:** "We are going to majorly work with three of them — tOracleConnection, tOracleRow, tOracleOutput." Phase 11 scope is locked to those three. The remaining 6 Oracle components (Input, SP, BulkExec, Commit, Rollback, Close) stay engine-unimplemented but the `OracleConnectionManager` API is designed to support them when later phases ship — `manager.commit(cid)`, `manager.rollback(cid)`, `manager.close(cid)` are part of the public surface from Phase 11 day 1.
- **User direction:** "How to have oracle connection info persisted for other components from tOracleConnection component?" — Talend uses `globalMap.put("conn_<cid>", conn)`. Our engine cannot put live Python Connection objects into the Python-Java synchronized GlobalMap. Decision: dedicated `OracleConnectionManager` keyed by component id + Talend-parity metadata strings in globalMap (so any downstream Java expression can still see `connectionType_<cid>` etc., even if it can't see the live Connection).
- **User direction:** "Ensure the base will work solid with all of the Oracle components, not just the 3 we're shipping." — Decision-level: manager API supports `commit/rollback/close` for future components; thick-mode flag covers Wallet/OCI when those phases come; type-mapping policy is shared across the family (tOracleInput will reuse `_coerce_column_type` exactly like tOracleRow does for FLOW out).
- **User direction (concern):** "I don't want the existing DB to get affected." — Driver thin mode is read-only on the client side; cannot alter DB charset, NLS, or any DB-side state. Documented in D-A2.
- **User direction:** "Ensure to close connections or clean up connections in engine using the corresponding connection manager, similar to how Java bridge closes." — D-A4b explicitly mirrors `JavaBridgeManager.stop()` integration with `ETLEngine._cleanup()` call sites (success / exception / `__del__`). Idempotent per-connection close, no leaks.
- The 3 sample `.item` files in `tests/talend_xml_samples/` (`Job_tOracleConnection_0.1.item`, `Job_tOracleRow_0.1.item`, `Job_tOracleOutput_0.1.item`) ARE the integration-test fixtures for sub-phase 11-07. The conversion already produces clean JSON; integration testing converts + executes end-to-end against a `gvenzl/oracle-free` testcontainer.

</specifics>

<deferred>
## Deferred Ideas

- **`ORACLE_OCI` and `ORACLE_WALLET` connection types** — wired at the converter level (D-E1 emits needs_review), engine raises `NotImplementedError`. Lift in a future phase when a real Citi production job needs them, alongside thick-mode support. Both require Oracle Instant Client on the host.
- **Other 6 Oracle engine components** — tOracleInput, tOracleSP, tOracleBulkExec, tOracleCommit, tOracleRollback, tOracleClose. The `OracleConnectionManager` already exposes `commit / rollback / close / cursor` per cid, so these become focused component-only phases. tOracleBulkExec specifically requires shelling out to `sqlldr` (Oracle Instant Client) — should land alongside thick-mode support.
- **`tOracleRow.PROPAGATE_RECORD_SET`** — Talend pattern emits a live `ResultSet` object as a downstream FLOW column; doesn't translate cleanly to DataFrame semantics. Defer; rewrite affected jobs as `tOracleInput → downstream`. ConfigurationError when `propagate_record_set=true` in the meantime.
- **`tOracleInput.IS_CONVERT_XMLTYPE` / `CONVERT_XMLTYPE` table** — XMLType column-mapping per converter table; only relevant when tOracleInput ships. Captured via the converter already; engine handling deferred.
- **`BaseDbConnection` / `BaseDbInput` / `BaseDbOutput` abstractions** — refactor when the MSSql phase ships with 2+ vendor implementations. Project memory: don't speculate on shape from one example.
- **Replacing hybrid mock-default test strategy with default-CI Docker fixtures** — when ops can host Docker in CI. The phase-end verification gate (D-D3) keeps the discipline in the meantime.
- **Streaming-mode for very large tOracleOutput inputs** — `executemany` materializes the batch in memory; for extreme datasets a chunked-DataFrame iteration optimization could help. Defer to a later perf phase.
- **MSSql engine components** — converters exist (`mssql_connection.py`, `mssql_input.py`); engine implementations follow in their own phase, informed by the OracleConnectionManager learnings.

### Reviewed Todos (not folded)
None reviewed.

</deferred>

---

*Phase: 11-oracle-components*
*Context gathered: 2026-05-07*
