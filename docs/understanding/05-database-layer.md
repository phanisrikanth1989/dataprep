# Database Layer (Oracle/MSSQL)

> Engine-side execution of Talend Oracle and SQL Server components against live
> databases. This is the **newest** code in the project (added in the ~28 commits
> after the docs were locked 2026-05-11) and, as this document repeatedly flags,
> the **least mature and most under-tested** subsystem. Several files currently
> contain hard runtime errors. Read the "Reliability and Known Breakage" section
> before relying on anything here.

---

## 1. Scope and shape

The database layer has two halves:

1. **Connection managers** (live driver objects, owned per job, never serialized)
   - `src/v1/engine/oracle_connection_manager.py` -- `OracleConnectionManager` (python-oracledb, thin mode)
   - `src/v1/engine/mssql_connection_manager.py` -- `MSSqlConnectionManager` (pyodbc)

2. **Engine components** (one `BaseComponent` subclass per Talend palette item)
   under `src/v1/engine/components/database/`.

| Talend type(s)                  | Engine class            | File                    | Role |
|---------------------------------|-------------------------|-------------------------|------|
| `tOracleConnection`, `tDBConnection` | `OracleConnection` | `oracle_connection.py`  | Open + register a connection (per CONNECTION_TYPE) |
| `tOracleInput`                  | `OracleInput`           | `oracle_input.py`       | SELECT -> DataFrame |
| `tOracleOutput`                 | `OracleOutput`          | `oracle_output.py`      | Sink: 8 TABLE_ACTION x 5 DATA_ACTION matrix |
| `tOracleRow`                    | `OracleRow`             | `oracle_row.py`         | Arbitrary SQL/DDL/DML, prepared binds |
| `tOracleSP`                     | `OracleSP`              | `oracle_sp.py`          | Stored procedure / function call per row |
| `tOracleBulkExec`               | `OracleBulkExec`        | `oracle_bulk_exec.py`   | SQL*Loader bulk load via `sqlldr` |
| `tOracleCommit`                 | `OracleCommit`          | `oracle_commit.py`      | Commit (+ optional close) a named connection |
| `tOracleRollback`               | `OracleRollback`        | `oracle_rollback.py`    | Rollback (+ optional close) |
| `tOracleClose`                  | `OracleClose`           | `oracle_close.py`       | Idempotent close, no commit/rollback |
| `tMSSqlConnection`              | `MSSqlConnection`       | `mssql_connection.py`   | Open + store a pyodbc connection |
| `tMSSqlInput`                   | `MSSqlInput`            | `mssql_input.py`        | SELECT -> DataFrame |

All 11 component classes are imported (and thus `@REGISTRY.register`-ed) by
`src/v1/engine/components/database/__init__.py`. SQL Server support is
**deliberately minimal**: only a connection + input pair exist. There is **no
SQL Server write path** (no output/row/commit/close) -- see section 8.

---

## 2. Connection lifecycle (the manager-owns-resource pattern)

The central design rule is that **live driver connection objects must never enter
`globalMap`**. `globalMap` is synchronized to the Java bridge and must stay
Arrow-serializable (the Phase 2 sync contract). A connection object cannot be
serialized, so it lives in the manager, keyed by component id. Only *metadata
strings* (`connectionType_`, `dbschema_`, `username_`) ever reach `globalMap`,
and **credentials never do** (T-11-02).

### 2.1 Wiring by ETLEngine

`ETLEngine.__init__` auto-detects Oracle/MSSql component types in the job config
(or an explicit `oracle_config`/`mssql_config` `enabled` block) and constructs
the matching manager, calling `start()`. `_initialize_components` then injects
`self.oracle_manager` / `self.mssql_manager` and `input_schema`/`output_schema`
onto each database component.

`start()` (see `oracle_connection_manager.py:55`) is **idempotent** and:
- sets `oracledb.defaults.fetch_lobs = False` (D-B1) so CLOB/BLOB read as
  `str`/`bytes` rather than LOB locators;
- optionally calls `oracledb.init_oracle_client()` once per process for thick
  mode, guarded by the class-level `_thick_initialized` flag (the
  `init_oracle_client()` call is process-global and raises if called twice).

`stop()` is **idempotent and leak-proof** (`oracle_connection_manager.py:79`):
it iterates a copy of the dict and closes each connection in its own
`try/except`, so one bad close cannot strand the rest. It is called from
`ETLEngine._cleanup()` on **every** path (success, exception, `__del__`), so
connection leaks are structurally impossible. `MSSqlConnectionManager` mirrors
this shape faithfully.

### 2.2 Shared vs ad-hoc connections

Every data component acquires a connection through the same idiom:

```python
use_existing = self.config.get("use_existing_connection", False)
if use_existing:
    conn = self.oracle_manager.get(connection_ref)   # owned by tOracleConnection
    owns_connection = False
else:
    conn = self.oracle_manager.open_ad_hoc(self.id, config)  # component-owned
    owns_connection = True
```

- **Shared / registered** connections are opened by `tOracleConnection`
  (`register(cid, conn)`), survive across components, and are torn down only by
  an explicit `tOracleCommit`/`tOracleRollback`/`tOracleClose` or by the
  `manager.stop()` safety net in `ETLEngine._cleanup`.
- **Ad-hoc** connections are opened by the component itself via `open_ad_hoc`
  and closed in the component's own `finally` block.

`register()` raises `ValueError` if the same cid is registered twice (a component
that executed twice). The three connection-type kwargs builders
(`SID`/`SERVICE_NAME`/`RAC`) live in `oracle_connection_manager.py`;
`MSSqlConnectionManager._build_connection_string` builds an ODBC DSN
(`DRIVER`/`SERVER host,port`/`DATABASE`, Azure AD vs SQL auth).

---

## 3. Data flow through a database component

`BaseComponent.execute()` runs the standard template (validate -> resolve
expressions -> `_process` -> output-schema enforcement -> stats). Database
components push almost all real validation into `_process` (Phase 7.1 Rule 12 /
D-F3): `_validate_config` does structural shape checks only, content checks are
deferred until **after** context resolution so unresolved `${context.X}`
references do not crash validation.

- **Input** (`OracleInput`/`MSSqlInput`): `cursor.execute` + `fetchall`, build a
  DataFrame (columns from `output_schema` first, else `cursor.description`),
  apply trim / `no_null_values`, optional server-side cursor `arraysize`, return
  `{"main": df, "reject": None}`.
- **Output** (`OracleOutput`): writes rows in `batch_size` chunks via
  `executemany(..., batcherrors=True)`, partitions batch errors into a reject
  DataFrame, commits every `commit_every` rows.

### 3.1 Stats and globalMap keys

Stats land in `globalMap` following Talend conventions:

```
{cid}_NB_LINE              -- input row count
{cid}_NB_LINE_INSERTED     -- per data_action
{cid}_NB_LINE_UPDATED
{cid}_NB_LINE_DELETED
{cid}_NB_LINE_REJECTED     -- sum across batches
{cid}_QUERY                -- resolved query string (D-C8)
```

`tOracleConnection` has no RETURN section, so it publishes no `_NB_LINE_*` keys
(only the three metadata strings).

---

## 4. SQL emission and identifier handling (the ORA-00942 story)

This is the highest-churn, highest-risk area. The intent is correct and
parity-improving; the **current implementation is broken** (section 7).

### 4.1 The ORA-00942 fix (intent)

Oracle stores **unquoted** identifiers in uppercase and resolves unquoted
lookups case-insensitively (auto-uppercase). Wrapping an identifier in double
quotes makes it a **case-sensitive literal** lookup. A job config carrying a
lowercase table name (`citi_bser_run_details`) against a table physically stored
uppercase (`CITI_BSER_RUN_DETAILS`) therefore caused spurious `ORA-00942`
("table or view does not exist") whenever identifiers were quoted.

Commit `bafc8e7` switched Oracle identifier emission from **quoted** to
**unquoted** to mirror Talend's runtime (Talend never quotes), fixing the case
mismatch. The `_quote_ident` docstring (`oracle_output.py:97`) is now a slight
misnomer -- it validates and returns the identifier **without** quotes.

### 4.2 Identifier safety (T-11-04)

SQL-injection protection survives the unquoting because every identifier is
validated against a closed pattern before interpolation:

```
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")   # oracle_output.py:71
```

This permits legacy Oracle columns like `EMP$DATA` / `COL#1` for parity but
rejects spaces, semicolons, dashes, embedded quotes, and other metachars,
raising `ConfigurationError` with the offending name. `oracle_bulk_exec.py` does
**not** apply this validation to its control-file table/`INFILE` interpolation --
an inconsistency (section 7).

### 4.3 DDL type mapping

`_column_to_oracle_type` maps engine schema columns to Oracle DDL types:

| Engine type     | Oracle DDL |
|-----------------|------------|
| `int`           | `NUMBER(10)` |
| `float`         | `BINARY_FLOAT` (IEEE 754 round-trip) |
| `double`        | `BINARY_DOUBLE` |
| `str` (<=4000)  | `VARCHAR2(n CHAR)` (CHAR semantics, counts chars not bytes) |
| `str` (>4000)   | `CLOB` |
| `datetime`      | `TIMESTAMP` / `DATE` (per `use_timestamp_for_date_type`) |
| `bytes`         | `RAW` / `BLOB` |

### 4.4 The TABLE_ACTION x DATA_ACTION matrix (tOracleOutput)

`tOracleOutput` implements the full Talend 8x5 matrix. The 8 `TABLE_ACTION`
values are dispatched via a method dict (`_emit_*`):

- `NONE`, `CREATE`, `DROP_CREATE`, `CLEAR`, `TRUNCATE`,
  `TRUNCATE_REUSE_STORAGE`
- `CREATE_IF_NOT_EXISTS` -- PL/SQL `EXECUTE IMMEDIATE` wrapped with an
  `ORA-00955` ("name already used") catch
- `DROP_IF_EXISTS_AND_CREATE` -- PL/SQL DROP guarded by an `ORA-00942` catch,
  then CREATE

The PL/SQL `EXECUTE IMMEDIATE` + `SQLCODE` catch is the Oracle-idiomatic
"if not exists" form for SQL prior to 23ai (`oracle_output.py:335-359`).

The 5 `DATA_ACTION` values split into:
- **Simple** (`INSERT`/`UPDATE`/`DELETE`): single-statement `executemany`.
- **Upsert** (`INSERT_OR_UPDATE`/`UPDATE_OR_INSERT`): D-C2 batched 2-statement
  strategy -- per chunk, `SELECT` existing PKs once, partition matched/unmatched
  in Python, then `executemany` UPDATE on matched + `executemany` INSERT on
  unmatched. Stats split correctly (`NB_LINE_UPDATED += matched_ok`,
  `NB_LINE_INSERTED += unmatched_ok`); the reject DataFrame consolidates errors
  from both calls.

### 4.5 Reject DataFrame schema (D-C7)

```
[errorCode, errorMessage, <input columns>]
  errorCode    = str(BatchError.code)
  errorMessage = BatchError.message + " - Line: " + offset
```

`batcherrors=True` lets `executemany` continue past per-row failures and report
them as `BatchError` objects, which are partitioned into the reject flow.

---

## 5. Prepared statements, stored procedures, bulk load

### 5.1 tOracleRow prepared binds

`oracle_row.py` carries a rigorously sourced `_PARAM_TYPE_COERCERS` table:
**19 entries** = 16 values cross-checked against the actual Talaxie
`tOracleRow_java.xml` enum + 3 defensive inferred aliases
(`Integer`/`BigInteger`/`Timestamp`). Each `PARAMETER_TYPE` name maps to a
coercer for positional prepared-statement binds. The closed-enum contract is
enforced in **both** `_validate_config` and `_coerce_prepared_param`; unknown
types are rejected. `_coerce_decimal` routes through `str` to avoid float
round-trip; Null binds emit explicit SQL NULL.

The converter side (`oracle_row.py` converter, `_parse_prepared_params`) defends
incomplete bind groups (WR-03 drops incomplete groups, WR-04 rejects
non-numeric / `< 1` parameter index) so a bad bind fails at conversion with a
human-readable warning rather than crashing the engine at `int('abc')` far from
the source.

`tOracleRow` **refuses** `PROPAGATE_RECORD_SET` (record-set propagation is not
supported); `USE_NB_LINE` publishes a configurable stat key.

### 5.2 tOracleSP stored procedures

`oracle_sp.py` does per-row `callproc`/`callfunc` with IN/OUT/INOUT bind vars.
`_normalize_direction` folds `IN`/`OUT`/`IN OUT`; `_oracle_var_type` maps DBTYPE
to oracledb var types; OUT/INOUT/return values are collected back into output
rows. It **refuses** custom STRUCT/ARRAY params and RECORDSET ref-cursor params.

### 5.3 tOracleBulkExec (SQL*Loader)

`oracle_bulk_exec.py` materializes the input FLOW to a data file, generates a
SQL*Loader `.ctl` control file from `input_schema`, builds the `sqlldr` argv +
NLS env, shells out via `subprocess.run`, parses the log via regex for stats,
and maps exit codes to errors. It depends on the external Oracle Instant Client
`sqlldr` binary being on the host.

---

## 6. Transaction semantics and parity notes

### 6.1 Commit/Rollback/Close

`tOracleCommit` and `tOracleRollback` both default `close=True` (matching
Talend). `tOracleClose` is idempotent and never commits/rolls back.

### 6.2 die_on_error preserves Talend commit-up-to-failure (WR-01)

`die_on_error` intentionally preserves Talend's commit-up-to-failure-point
semantics: already-committed chunks are **not** rolled back. This is documented
behavior, not a bug.

### 6.3 Refused / deferred features (declared parity gaps)

- `ORACLE_OCI` and `ORACLE_WALLET` connection types are **refused** (require
  thick mode + Instant Client).
- `tOracleRow` `PROPAGATE_RECORD_SET`, `tOracleSP` `RECORDSET` / custom
  STRUCT-ARRAY -- refused.
- `CHECK_TYPE_OVERFLOW` / `CHECK_ULP` -- unimplemented.
- Encoding / SSL / TNS / NLS flags -- warned-and-skipped (read by the converter,
  not actively used by the engine).

### 6.4 Cleanup must not mask the original error (WR-02)

`cursor.close()` and `manager.close()` are wrapped in `try/except` inside
`finally` blocks (e.g. `oracle_row.py:420-437`), so a close-time error never
replaces a meaningful SQL error like `ORA-00942`.

---

## 7. Reliability and Known Breakage

**This section is load-bearing.** Several findings below are hard runtime errors
verified by direct code inspection. Do not assume any of these components run
until the listed fixes land.

### 7.1 BLOCKER: package-wide import is broken (engine.py SyntaxError)

`src/v1/engine/engine.py:225` is missing a comma in the `add_trigger(...)` call:

```python
self.trigger_manager.add_trigger(
    trigger['type'],
    comp_id,
    trigger.get('target_component') or trigger.get('to'),
    trigger.get('condition')          # <-- missing comma here
    output_id=int(trigger.get('output_id', 0) or 0),
)
```

This is a hard `SyntaxError` ("Perhaps you forgot a comma?") that prevents the
entire `src.v1.engine` package from importing. Because `conftest` imports
`ETLEngine`, this **blocks pytest collection for the whole DB-layer test suite**,
masking the breakage below in any CI run that only checks collection. Introduced
in the same `0ad1ee0` (output_id) commit that broke `TriggerManager`. **Fix
first** -- nothing in this layer can be exercised until it imports.

### 7.2 BLOCKER: tOracleOutput cannot execute any DDL/DML path

`oracle_output.py` has three independent runtime errors on every write path:

1. **`NameError` -- undefined `IDENTIFIER_RE`.** The constant is `_IDENTIFIER_RE`
   (line 71) but `_quote_ident` references `IDENTIFIER_RE.match(name)` at line
   132. `_quote_ident` is called by every CREATE/INSERT/UPDATE/DELETE/SELECT
   builder, so any execution raises `NameError: name 'IDENTIFIER_RE' is not
   defined`. Introduced by `bafc8e7`.
2. **`AttributeError` -- method/call-site name mismatch.** The method is defined
   as `def qualified_table` (line 252) but **13 call sites** invoke
   `self._qualified_table()` (lines 321, 358, 367, 384, 388, 396, 476, 506, 525,
   556, 569, 1081). The unit tests also call `comp._qualified_table()`.
3. **`NameError` + wrong config key inside `qualified_table()`.** Lines 283/285/286
   reference an undefined local `schema` (only `table` is assigned, line 278);
   line 278 calls `self._quote_ident(...)` but `_quote_ident` is a module-level
   function, not a method; and line 279 reads
   `self.config.get('table') or self.config.get('dbschema')`, but the converter
   emits `schema_db` for the schema and `table` for the table -- so schema
   qualification is dropped and the wrong fallback key is consulted.

Net: `tOracleOutput` is completely non-functional in its current state.

### 7.3 Tests assert the OLD (quoted) behavior -- the component ships effectively red

`tests/v1/engine/components/database/test_oracle_output.py` still asserts quoted
identifiers (`_quote_ident('emp_id') == '"emp_id"'`,
`comp._qualified_table() == '"HR"."EMP"'`) and calls `_qualified_table`. The
refactor intends **unquoted** emission and renamed the method, so the tests
**cannot pass against current source** even if the NameError/AttributeError were
fixed. Combined with the collection-blocking SyntaxError in 7.1, no
`oracle_output` test currently passes. This is the canonical example of "newest
code, least tested."

### 7.4 MSSqlInput leaks query timeout onto a shared connection

`mssql_input.py:87-89` sets `conn.timeout` when reusing a shared
(`use_existing_connection=True`) connection and **never restores it**. pyodbc's
timeout is connection-scoped, so a later `tMSSqlInput` on the same connection
inherits the prior component's timeout (and `0` means *no* timeout). Fix:
save/restore around the cursor, or apply the timeout per-cursor.

### 7.5 Unconditional commit on shared connections defeats transaction control

`tOracleRow` unconditionally calls `conn.commit()` whenever
`conn.autocommit` is False (`oracle_row.py:413-414`), **including** shared
`use_existing_connection` connections. `tOracleOutput` and `tOracleSP` share the
same pattern. Talend's `tOracleConnection`-managed transaction is meant to be
committed/rolled-back only by an explicit `tOracleCommit`/`tOracleRollback`, so
auto-committing here means a downstream `tOracleRollback` cannot undo the
statement -- a real parity break for multi-statement transactional jobs.

### 7.6 tDBConnection is silently forced to Oracle semantics

`tDBConnection` shares `OracleConnectionConverter`/`OracleConnection`
(`oracle_connection.py` register block) and is unconditionally given
Oracle-specific defaults (`connection_type ORACLE_SID`, port 1521,
`db_version ORACLE_18`, `jdbc:oracle:thin` URL). A job that uses
`tDBConnection` as a generic / non-Oracle connection would be silently converted
with Oracle semantics and **no `needs_review` entry** flagging the assumption.

### 7.7 Upsert PK SELECT can hit ORA-01795

The single-PK upsert path builds `WHERE pk IN (:1..:N)` with one bind per row but
does **not** chunk to Oracle's 1000-expression `IN`-list limit. With `batch_size`
default ~10000, a batch of >1000 keys raises `ORA-01795`. (The composite-PK
OR-chain avoids the limit but generates very large SQL.) Fix: sub-chunk the PK
SELECT to <= 1000 keys.

### 7.8 bulk_exec interpolates table/INFILE without identifier validation

`oracle_bulk_exec.py:240-242` writes `INTO TABLE {table}` and `INFILE
'{data_file}'` directly from config with no `_quote_ident` gate, unlike
`oracle_output`. Lower risk (internal job authors, not SQL-injection per se) but
inconsistent with the T-11-04 mitigation applied elsewhere.

### 7.9 Lower-severity smells

- `_parse_trim_column` is duplicated: a module function in `oracle_input.py`
  (converter side) and a staticmethod in `mssql_input.py` (converter side); the
  same KEY/VALUE stride-2 parse is re-implemented in several converters. A shared
  `base._parse_table` helper would remove ~6 near-identical parsers.
- Encrypted-password handling differs between the two MSSQL converters
  (strip-then-check-`enc:` vs check-then-strip ordering) -- works for unquoted
  values but is an avoidable divergence.
- `MSSqlConnection` uses `open_ad_hoc(self.id)` for what is semantically a
  *registered* shared connection (vs Oracle's `register()` path). It works
  (downstream `get(self.id)` finds it, `owns_connection=False` keeps it alive)
  but is a confusing semantic mismatch with `open_ad_hoc`'s documented intent.

---

## 8. SQL Server: deliberately partial

Only `tMSSqlConnection` + `tMSSqlInput` exist. There is **no MSSQL output / row /
commit / close** -- i.e. **no SQL Server write path** today. Whether this is an
accepted phase scope or a gap to close is an open question (section 10). Any work
extending SQL Server should follow the Oracle structure but learn from its bugs
(unquoted-identifier handling, shared-connection commit suppression,
timeout-restore).

---

## 9. Test coverage map and risk

> **Coverage health: poor and partly un-runnable.** The 95% per-module floor
> cannot currently be measured for this layer because pytest collection is
> blocked by the `engine.py` SyntaxError (7.1).

### 9.1 Existing tests

| Area | Test location |
|------|---------------|
| Engine unit (MagicMock manager + cursor, no live DB) | `tests/v1/engine/components/database/test_oracle_{output,input,row,sp,bulk_exec}.py`, `test_mssql_input.py` |
| Engine integration (`@pytest.mark.oracle`) | `tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py`, `test_oracle_row_e2e.py`, `test_oracle_output_e2e.py`, `test_oracle_connection_e2e.py` |
| Converter side | `tests/converters/talend_to_v1/components/database/test_oracle_{sp,bulk_exec,input,output}.py`, `test_mssql_input.py` |

### 9.2 Coverage gaps to close (priority order)

1. **Fix the import + tOracleOutput errors (7.1-7.3) so tests can even run**, then
   reconcile `test_oracle_output.py` to the unquoted-identifier contract.
2. **No unit tests at all** for `OracleConnectionManager` /
   `MSSqlConnectionManager` themselves (start/stop idempotency, `register`
   duplicate guard, thick-init guard, leak-proof `stop`).
3. **No dedicated tests** for the `oracle_connection`, `oracle_commit`,
   `oracle_rollback`, `oracle_close`, or `mssql_connection` engine components.
4. **`tDBConnection`-as-non-Oracle scenario** (7.6) is untested -- add a case that
   asserts either a dedicated converter or a `needs_review` flag.
5. **Shared-connection commit suppression** (7.5) -- add a test that a
   `tOracleRow` on a shared connection followed by `tOracleRollback` actually
   rolls back.
6. **Upsert batch > 1000 keys** (7.7) -- assert sub-chunking once implemented.
7. **MSSqlInput timeout restore** (7.4) -- assert a second input on the same
   connection does not inherit the timeout.
8. The unquoted-vs-quoted **identifier emission** behavior needs an explicit test
   that pins the chosen convention so it cannot silently regress again.

The unit tests build `TalendNode`/config fixtures directly with raw param dicts
rather than going through `XmlParser`, so converter-side pre-stripping of scalar
params is **not** exercised at this layer -- the redundant-strip and the MSSQL
encrypted-password ordering divergence would not be caught here.

---

## 10. Open questions for extenders

1. Is identifier emission intended to be **unquoted** (the `bafc8e7` refactor
   intent, fixing ORA-00942 case mismatch) or **quoted** (what the tests still
   assert)? Production code and tests currently disagree; both cannot be right.
2. Should `tOracleRow`/`tOracleOutput`/`tOracleSP` suppress their unconditional
   `conn.commit()` on shared (`use_existing_connection`) connections so explicit
   `tOracleCommit`/`tOracleRollback` retain transaction control, matching Talend?
3. Does any real Talend job use `tDBConnection` as a generic non-Oracle
   connection? If so, forcing Oracle defaults is a silent parity break needing a
   dedicated converter or a `needs_review`.
4. Does any Phase 11 sample exercise single-PK upsert with a batch > 1000 rows?
   That path hits `ORA-01795` and needs sub-chunking.
5. Is the absence of MSSQL output/row/commit/close an accepted phase scope or a
   parity gap to be closed?

---

## Quick reference: file map

```
src/v1/engine/
  oracle_connection_manager.py       # OracleConnectionManager (oracledb thin)
  mssql_connection_manager.py        # MSSqlConnectionManager (pyodbc)
  components/database/
    __init__.py                      # imports all 11 -> @REGISTRY.register fires
    oracle_connection.py             # tOracleConnection, tDBConnection
    oracle_input.py                  # tOracleInput
    oracle_output.py                 # tOracleOutput  (BROKEN: see 7.2)
    oracle_row.py                    # tOracleRow
    oracle_sp.py                     # tOracleSP
    oracle_bulk_exec.py              # tOracleBulkExec (sqlldr)
    oracle_commit.py / oracle_rollback.py / oracle_close.py
    mssql_connection.py              # tMSSqlConnection
    mssql_input.py                   # tMSSqlInput   (timeout leak: see 7.4)
```
