# Databases: how current tools read and load Oracle and SQL Server, and what follows for v2 (ticket 92)

Researched: 2026-10-12, for the eleven database components (Oracle connection,
input, output, row, stored procedure, bulk exec, commit, rollback, close; MSSQL
connection, input). The rule they are built to is ticket 87: not Talend or v1
parity, built for long use, and a converted job config still loads unchanged.

Sources are primary only: the projects' own documentation, source, changelogs
and registries, read on 2026-10-12. No blogs, no Stack Overflow, no summaries.

Labels used throughout:

- **Source**: stated by a primary source; the citation follows.
- **Observed**: run on this machine with short scripts: Polars 1.44.2
  (`polars-runtime-32` 1.44.2), pyarrow 25.0.0, Python 3.14.6, macOS 26.6.2
  arm64, Apple M4, 10 cores, 16 GB. No database was contacted: `oracledb`,
  `pyodbc` and every other driver are not installed, and no container was
  started. Where a driver was needed, a 40-line stand-in module with the
  driver's name and method names was used; that shows what Polars asks of the
  driver and nothing about the driver. Every observation is provisional for the
  RHEL servers and for any other Polars version. The scripts lived in the
  session's scratch folder and are not committed; section 7 gives them in
  short form.
- **unconfirmed**: could not be settled from a primary source or a run here.
- **Inferred**: follows from sources given, by reasoning that is spelled out.

Citation shorthand:

- `ODOC file Ln` = python-oracledb documentation source at commit
  `c92c8420874157ce169b28b60b7f139a73f59ee2` (main, 2026-10-07; rendered at
  python-oracledb.readthedocs.io/en/latest):
  https://github.com/oracle/python-oracledb/blob/c92c8420874157ce169b28b60b7f139a73f59ee2/doc/src/FILE#Ln
- `OSRC file Ln` = python-oracledb source at the release tag `v26.0.1`:
  https://github.com/oracle/python-oracledb/blob/v26.0.1/src/oracledb/FILE#Ln
- `ORN Ln` = `ODOC release_notes.rst Ln`. `#NNN (oracledb)` = issue NNN of
  https://github.com/oracle/python-oracledb/issues.
- `PL44 path Ln` = https://github.com/pola-rs/polars/blob/py-1.44.2/py-polars/src/polars/PATH#Ln.
  The installed `io/database/_executor.py` was diffed against this tag: equal.
- `TX Component/file Ln` = Talaxie at commit
  `639d5fd1f77699a574d26b8546b73d69cd4546f7` (2024-10-20):
  https://github.com/Talaxie/tdi-studio-se/blob/639d5fd1f776/main/plugins/org.talend.designer.components.localprovider/components/COMPONENT/FILE#Ln
- `MSD path` = https://github.com/MicrosoftDocs/sql-docs/blob/live/docs/PATH
  (rendered on learn.microsoft.com); the `ms.date` of each page is given.
- `PyPI name` = https://pypi.org/pypi/NAME/json as read on 2026-10-12.
- Repo paths are relative to the repo root, with `:line`, as the files stand
  at commit `32383de1` of `feature/engine-v2` (2026-10-12 07:38; the two
  commits after it, up to `bb40cb2f`, touch none of the cited files). A script
  checked the cited lines of the converter, of v1 and of Talaxie's component
  definitions against the files, and every quoted passage of 30 characters or
  more against the texts that were fetched; the lines of Talaxie's templates
  and of `src/v2` were checked by hand.

---

## 1. The ten findings that matter most for the design

1. **A direct path load cannot be part of a transaction.** python-oracledb:
   "The records are always implicitly committed", and "Direct Path Loads are
   only supported in python-oracledb Thin mode" (ODOC
   user_guide/batch_statement.rst L654, L684). It cannot be the default route
   of an engine that commits when the subjob has succeeded.
2. **Closing a connection means opposite things in Talend and in Python.**
   Oracle JDBC: "If the auto-commit mode is disabled and you close the
   connection without explicitly committing or rolling back your last changes,
   then an implicit COMMIT operation is run" (JDBC Developer's Guide 21c,
   2.3.8); python-oracledb: "When a database connection is closed ... any
   uncommitted transaction will be rolled back" (ODOC
   user_guide/txn_management.rst L27-29). What tOracleClose and the end of a
   job do with open work has to be decided, it cannot be inherited.
3. **TRUNCATE and every other table action is DDL, and DDL commits.** "Oracle
   Database implicitly commits the current transaction before and after every
   DDL statement" and "You cannot roll back a TRUNCATE TABLE statement"
   (Oracle SQL Language Reference 19c). Talend says so on its own screen:
   "this component configuration will automatically generate a commit before
   data insert/update/delete" (TX tOracleOutput/tOracleOutput_java.xml
   L216-220). Truncate-then-insert cannot be all or nothing in Oracle.
4. **A batch callback can join the subjob's one pass, but only as a sink.**
   `LazyFrame.sink_batches(fn, chunk_size=N, lazy=True)` ran inside one
   `pl.collect_all` beside a file sink and a tap: batches of exactly N rows, in
   row order, one call at a time, an exception in the callback reaching the
   caller unchanged. `map_batches(streamable=True)` was called from 12 threads,
   10 calls at once, out of row order. (Observed; both are marked unstable in
   1.44.2 and in 2.0.0: PL44 lazyframe/frame.py L4253-4254.)
5. **A lazy Python reader runs the query again for every plan and every later
   collect.** A reader registered with `register_io_source` was called 4 times
   for 2 sinks and 2 taps off one frame (once with `is_pure=True`), and v2
   collects again to blame a component, to count dropped rows, for the second
   attempt and for `--only`. Each call is one more execution of the SQL.
   (Observed; `src/v2/engine/runner.py:420-430, 471-495, 643-711, 882-901`.)
6. **python-oracledb's default Arrow types lose data, and Polars 1.44.2 cannot
   correct them.** NUMBER with a scale, and NUMBER with no precision, arrive
   as DOUBLE unless decimals are asked for; TIMESTAMP WITH TIME ZONE loses its
   zone; a LOB over 1 GB cannot be fetched (ODOC user_guide/dataframes.rst
   L190-203, L257, L281). `pl.read_database(..., schema_overrides=...)` is
   silently ignored for this driver in 1.44.2 (Observed; PL44
   io/database/_executor.py L248-251; fixed in 2.0.0, pola-rs/polars #29273).
   The driver's own `requested_schema` is the place to state the types.
7. **The Arrow path of python-oracledb is young and has had wrong-data bugs
   three weeks ago.** Data frames left pre-release in 3.4.0 (October 2025, ORN
   L459). 26.0.0 produced "malformed Arrow decimal arrays across batch
   boundaries" (#605) and dropped DATE values asked for as date32 (#606), both
   fixed in 26.0.1 (ORN L55); direct path load corrupted data on single-byte
   database character sets until 4.0.0 (#567, ORN L267). The repo pins
   `oracledb>=2.5,<4` (`pyproject.toml:18`), which shuts all of these fixes
   out.
8. **Thin mode and thick mode each lack something a bank may need, and a
   process can only be one of them.** Thin has no Native Network Encryption,
   no Kerberos, no SEPS wallet, no sqlnet.ora; thick has no direct path load
   (ODOC user_guide/appendix_a.rst L89, L133, L145, L169, L253). "All
   connections in an application use the same mode" (ODOC
   user_guide/initialization.rst L25). Which one the target databases require
   is not known here.
9. **For SQL Server there is now a first-party driver that needs no system
   packages and hands out Arrow batches.** `mssql-python` 1.15.0 (Microsoft,
   GA since 1.0.0 on 2025-11-18) carries ODBC Driver 18 inside a companion
   wheel and has `cursor.arrow_reader()` since 1.5.0; it needs glibc 2.28
   (RHEL 8 or later) and pulls `azure-identity` (PyPI mssql-python; its
   release notes). The SQL Server container image is amd64 only and
   "Emulation or translation environments (for example, Rosetta 2, Prism, or
   QEMU) aren't tested or supported" (Microsoft Learn, quickstart-install-docker,
   ms.date 2026-05-07); Azure SQL Edge "is retired as of September 30, 2025".
10. **The converter in this repo cannot convert eight of the eleven components
    today, and the queries it would write carry Java.** Every converter that
    reads a password calls `self._extract_password(..., log_id=...)`, which no
    class defines with that signature; the component becomes an `_unsupported`
    placeholder with an empty config (Observed by running the converter in
    memory on the three Oracle samples; section 4.1). The committed sample
    configs are older and differ from what the converter source says
    (`table_schema`, `enc:` passwords). A Talend query that joins context
    variables with `+` reaches the job config as raw Java text with no
    `{{java}}` mark (section 4.4).

---

## 2. Findings by question

### Q1. python-oracledb as of today

#### 1.1 Version and Python support

| Fact | Value | Source |
|---|---|---|
| Current release | 26.0.1, uploaded 2026-09-22 | PyPI oracledb |
| Releases before it | 3.4.2 (2026-01-28), 4.0.0 (2026-05-04), 4.0.1 (2026-05-19), 4.0.2 (2026-07-14), 26.0.0 (2026-09-10) | PyPI oracledb |
| Version scheme | "Moved to a year-based version number system. The python-oracledb major version number will be the two-digit year in which that major version was first released." | ORN L117 |
| Python | `requires_python >=3.10`; "Use any version from Python 3.10 through 3.15"; 26.0.0 "Dropped support for Python 3.9 and added initial support for Python 3.15" | PyPI; ODOC user_guide/installation.rst L38; ORN L120 |
| Wheels | cp310 to cp315 for manylinux2014 x86_64 and aarch64 (glibc 2.17), musllinux, macOS universal2, Windows | PyPI oracledb |
| Hard dependencies | `cryptography>=3.2.1`, `typing_extensions>=4.14.0` | PyPI oracledb |
| Licence | `UPL-1.0 OR Apache-2.0` | PyPI oracledb |
| Pin in this repo | `oracle = ["oracledb>=2.5,<4"]`: resolves to 3.4.2 at most | `pyproject.toml:18` |

#### 1.2 Thin and thick mode

"By default, python-oracledb runs in a 'Thin' mode which connects directly to
Oracle Database. This mode does not need Oracle Client libraries." Thick mode
loads Oracle Client libraries with `oracledb.init_oracle_client()`, which
"must be called before any standalone connection or connection pool is
created"; "All connections in an application use the same mode"; "Once the
Thick mode is enabled, you cannot go back to the Thin mode" (ODOC
user_guide/initialization.rst L9-25, L102-120). The docs name the common
reasons for thick mode: database version 11 or older, "Native Network
Encryption (NNE) or checksumming", Application Continuity (same file, L17-23).

| Feature | Thin | Thick | Source (ODOC user_guide/appendix_a.rst) |
|---|---|---|---|
| Oracle Database version | 12.1 and later | 11.2 and later; Oracle Client 19 or later (older clients dropped in 4.0.0, ORN L294) | L37 |
| Native Network Encryption | "No - use TLS instead" | Yes | L133 |
| Kerberos and Radius authentication | No | Yes | L89 |
| External authentication | No in this table; the authentication guide says TLS client-certificate authentication "can be used in both python-oracledb Thin and Thick modes" (added to thin in 26.0.0, ORN L69). The two pages disagree; the guide and the release note are the newer text | Yes | L77; ODOC user_guide/authentication_methods.rst L145, L376 |
| Secure External Password Store wallet (mkstore) | No | Yes | L169 |
| `sqlnet.ora` | "No - many values can be set at connection time" | Yes | L145 |
| `tnsnames.ora`, Easy Connect | Yes | Yes | same table |
| One-way TLS and mutual TLS | Yes; for mTLS the wallet directory "must contain the PEM-encoded wallet file ewallet.pem" | Yes (`cwallet.sso`) | same table; OSRC connection.py, `connect()` docstring |
| Token authentication (OAuth 2.0, OCI IAM) | Yes | Yes | same table; ODOC user_guide/authentication_methods.rst L437 |
| Connection pool session tagging | No (`DPY-3001`, ORN L535) | Yes | L69 |
| Heterogeneous pools, client result cache, FAN, TAF, Application Continuity, SODA, startup/shutdown | No | Yes | same table |
| Direct Path Loads | Yes | No | L253 |
| asyncio, pipelining | Yes | No | same table |
| Call timeouts, statement break, scrollable cursors, Transaction Guard | Yes | Yes | L269 and same table |

Inferred: Talend's `ORACLE_OCI` connection type (a TNS alias, TX
tOracleConnection/tOracleConnection_begin.javajet L47-49) does not need thick
mode in python-oracledb, since thin reads `tnsnames.ora`. `ORACLE_WALLET`
(`DriverManager.getConnection(url)` with no user or password, same file
L111-113) is a password-store wallet, which is thick only. v1 refuses both
(`src/v1/engine/components/database/oracle_connection.py:173-180`).

#### 1.3 Fetching as Arrow

History (ORN): `Connection.fetch_df_all()` and `fetch_df_batches()` arrived in
3.0.0, March 2025, as objects "that expose an Apache Arrow PyCapsule interface"
(L902); CLOB, BLOB, RAW in 3.1.0; the ArrowArrayStream PyCapsule interface in
3.3.0; "Support for data frames is no longer considered a pre-release",
`requested_schema`, and large (64-bit offset) strings by default in 3.4.0
(L459-464); intervals and decimal256 in 26.0.0 (L143).

Signatures at v26.0.1 (OSRC connection.py L1581, L1626):

```python
Connection.fetch_df_all(statement=None, parameters=None, arraysize=None, *,
                        fetch_decimals=None, requested_schema=None, handle=None) -> DataFrame
Connection.fetch_df_batches(statement=None, parameters=None, size=None, *,
                            fetch_decimals=None, requested_schema=None, handle=None) -> Iterator[DataFrame]
```

- They are methods of the connection, not of a cursor. `parameters` are bind
  values. `size` "controls the number of records fetched in each batch";
  "the `fetch_df_batches()`'s `Cursor.arraysize` and `Cursor.prefetchrows`
  sizes are always set to the value of the explicit or default `size`"
  (docstring). `handle` is thick only. "Any LOB fetched must be less than
  1 GB."
- The result object "exposes an Apache Arrow ArrowArrayStream PyCapsule
  Interface. This enables zero-copy data interchanges" (ODOC
  user_guide/dataframes.rst L17-20); Polars takes it with
  `polars.from_arrow(odf)` (same file, "Creating Polars DataFrames").
- "Querying any other data types from Oracle Database will result in an
  exception. Output type handlers cannot be used to map data types" (L121-124).

Default type mapping (ODOC user_guide/dataframes.rst L126-300):

| Oracle type | Arrow type by default | Trap |
|---|---|---|
| NUMBER, no precision and scale, or such an expression | DOUBLE: "If the column has been created without a precision and scale ... then the Apache Arrow data type will be DOUBLE" (L190-193) | exact values become floats. What `fetch_decimals=True` gives here is not stated (a bug in that case was fixed in 3.1.0, ORN L780): unconfirmed |
| NUMBER(p,0), p <= 18 | INT64 (L200-201) | |
| any other NUMBER | DOUBLE ("In all other cases", L203), or DECIMAL128 when `fetch_decimals` is true (L195-198); DECIMAL256 only through `requested_schema` | money as floats by default |
| DATE | TIMESTAMP, unit seconds, no zone (L283-284) | a DATE carries a time: "For each DATE value, Oracle stores the following information: year, month, day, hour, minute, and second" (Oracle SQL Language Reference 19c, Data Types) |
| TIMESTAMP(n) | TIMESTAMP, unit s (n=0), ms (1-3), us (4-6), ns (7-9) | ns covers only 1677-2262 |
| TIMESTAMP WITH [LOCAL] TIME ZONE | TIMESTAMP: "Apache Arrow TIMESTAMPs will not have timezone data" (L281) | the zone is lost; which instant is kept is not stated (unconfirmed). Thick mode returned "the wrong instant" until 4.0.2 (#596) |
| CHAR, VARCHAR2, NCHAR, NVARCHAR2, LONG, CLOB, NCLOB | LARGE_STRING | "LOBs must be no more than 1 GB in length" (L257) |
| RAW, LONG RAW, BLOB | LARGE_BINARY | BLOB: the same 1 GB limit (L269) |
| BINARY_DOUBLE, BINARY_FLOAT | DOUBLE, FLOAT | |
| BOOLEAN | BOOLEAN | SQL BOOLEAN exists from 23ai only |
| INTERVAL DS / YM | INTERVAL_MONTH_DAY_NANO (26.0.0) | |
| VECTOR | a list or a struct (L184-185) | not needed for these components |
| ROWID, XMLTYPE, JSON, objects | not in the table: an exception by the sentence above | unconfirmed which error |

Explicit mapping: `requested_schema` "should be an object implementing the
Arrow PyCapsule schema interface"; "The schema should have an entry for each
queried column"; names are taken from it too; "An error will occur if the
database type or the data cannot be represented in the requested schema type"
(L338-343, L375, L396-399). Allowed targets (L401-459): NUMBER to
DECIMAL256/DECIMAL128(p,s), DOUBLE, FLOAT, INT8..INT64, UINT8..UINT64; DATE
and every TIMESTAMP to DATE32, DATE64, TIMESTAMP; character types and CLOB to
LARGE_STRING or STRING; RAW and BLOB to BINARY, FIXED SIZE BINARY,
LARGE_BINARY; BOOLEAN only from a database BOOLEAN, so a NUMBER(1) cannot be
asked for as a boolean. Observed: `pl.Schema` has `__arrow_c_schema__`, but a Polars
string is a string view, which is not among the allowed targets; whether a
Polars schema is accepted is unconfirmed, a `pyarrow.schema` is the documented
form.

The empty string: "Oracle Database currently treats a character value with a
length of zero as null. However, this may not continue to be true in future
releases, and Oracle recommends that you do not treat empty strings the same
as nulls" (Oracle SQL Language Reference 19c, Nulls). A `str` column that held
`''` comes back missing, and v2's rule that a `str` read from a file is never
missing (docs/v2/writing-a-component.md L257-259) cannot hold for a table.

#### 1.4 Loading data frames with executemany

```python
Cursor.executemany(statement, parameters, *, batcherrors=False, arraydmlrowcounts=False,
                   suspend_on_success=False, batch_size=2**32 - 1) -> None      # OSRC cursor.py L1083
```

- "The `parameters` parameter can also be a DataFrame, or a third-party data
  frame that supports the Apache Arrow PyCapsule Interface" (docstring). Added
  in 3.3.0: "Added support for binding data frames to `Cursor.executemany()`
  ... for fast data ingestion" (ORN L566). Example in the guide:
  `cursor.executemany("insert into t (col1, col2) values (:1, :2)", pdf)`
  (ODOC user_guide/dataframes.rst L842-866).
- Arrow input types by release (ORN): only int64 integers before 3.4.0; all
  fixed-width integers, date32/date64 and multi-chunk frames in 3.4.0
  (L465-473); null-only arrays in 3.4.2; "data frames containing binary views
  (format "vb") and string views (format "vu")" in 4.0.0 (L321, #573);
  decimal256 and INTERVAL DAY TO SECOND in 26.0.0. No table of accepted input
  types is in the guide.
- Observed: a Polars frame handed over through the PyCapsule stream exports
  `str` as `string_view` and `bytes` as `binary_view` (through `to_arrow()`:
  `large_string`, `large_binary`); Decimal as `decimal128(38, s)`, `datetime`
  as `timestamp[us]`, `date` as `date32`. So a Polars frame passed as it is
  needs python-oracledb 4.0.0 or later.
- `batch_size` (3.4.0, ORN L484): "This will send the data to the database in
  batches of 200,000 records ... If `Connection.autocommit` is `True`, then a
  commit will take place per batch of records processed" (ODOC
  user_guide/batch_statement.rst L202-206).
- Types are fixed from the first non-null value unless `setinputsizes` is
  called: "if the type is not explicitly specified, the value None is assumed
  to be a string of length 1" (docstring). How this meets Arrow input is not
  stated.

#### 1.5 Direct Path Load

```python
Connection.direct_path_load(schema_name, table_name, column_names, data, *,
                            batch_size=2**32 - 1) -> None                      # OSRC connection.py L1557
```

- Added in 3.4.0 (October 2025), thin mode only (ORN L429; guide L654). `data`
  "can be a list of sequences, a DataFrame object, or a third-party DataFrame
  instance that supports the Apache Arrow PyCapsule Interface".
- "Direct Path Loads allow data being inserted into Oracle Database to bypass
  code layers such as the database buffer cache. Also, there are no INSERT
  statements used ... because Direct Path Loads generate minimal redo, they
  reduce pressure on redo logs" (ODOC user_guide/batch_statement.rst
  L636-641). "The end-to-end insertion time when using Direct Path Loads for
  smaller data sets may not be faster than using `Cursor.executemany()`"
  (L648-650).
- "The records are always implicitly committed" (L684); notes: "Data is
  implicitly committed", LOB values "must be strings or bytes", object types
  are not supported, "Review Oracle Database documentation for database
  requirements and restrictions" (L728-735).
- The interface it speaks has "the following limitations that are the same as
  SQL*Loader": "Triggers are not supported", "Referential integrity
  constraints are not supported", "Clustered tables are not supported",
  "LONGs must be specified last" (Oracle Call Interface guide 21c, Direct Path
  Load Interface). Whether python-oracledb then raises or the database skips
  them is unconfirmed.
- From the driver's own tests at v26.0.1
  (`tests/connection/test_2000_direct_path_load.py`): the wrong number of
  columns raises `DPY-4009`, a string longer than the column `DPY-8000`, a
  null or an empty string for a NOT NULL column `DPY-8001`; test 2020 is "test
  data is committed on success". What a duplicate key does is not tested
  there. For SQL*Loader's direct path Oracle says: "Even though UNIQUE
  constraints remain enabled during direct path loads, any rows that violate
  those constraints are loaded anyway", leaving the index unusable (Oracle
  Utilities 19c, Conventional and Direct Path Loads). Whether the same holds
  for this API is unconfirmed.

#### 1.6 batcherrors and arraydmlrowcounts

- "If the parameter `batchErrors` is set to the value `True` when calling
  `executemany()`, however, processing will continue even if there are data
  errors in some rows, and the rows containing errors can be examined
  afterwards ... Note that if any errors are detected, a transaction will be
  started but not committed, even if `Connection.autocommit` is set to `True`"
  (ODOC user_guide/batch_statement.rst L344-354). Each error has `.message`
  and `.offset`, "the index into the array of the data that could not be
  inserted" (L378-380).
- "If you want to know the total number of rows affected by each row of data
  that is bound you must set the parameter `arraydmlrowcounts` to `True`"
  (L392-394); `cursor.getarraydmlrowcounts()`.
- "Both the `batcherrors` parameter and the `arraydmlrowcounts` parameter can
  only be True when executing an insert, update, delete, or merge statement"
  (OSRC cursor.py, `executemany` docstring); "the `batcherrors` parameter ...
  cannot be used with PL/SQL block execution" (guide L234-235).
- Not found in the docs or the tests: `batcherrors=True` together with a data
  frame and with `batch_size` (what an offset is relative to). unconfirmed.

#### 1.7 arraysize, prefetchrows, timeouts, pooling

- `Cursor.arraysize` default 100, `prefetchrows` default 2 (ODOC
  user_guide/tuning.rst L140, L147, L189-190; OSRC defaults.py). For a large result:
  "increase the `arraysize` value from its default of 100 until you are
  satisfied with performance, memory, and round-trip usage" (L138-142). For
  data frames the `arraysize`/`size` argument rules and prefetch is set to the
  same value (L357-364).
- `Connection.call_timeout`: "the amount of time (in milliseconds) that a
  single round-trip to the database may take before a timeout will occur. A
  value of 0 means that no timeout will take place ... If a timeout occurs,
  the error DPI-1067 will be returned if the connection is still usable.
  Alternatively the error DPI-1080 will be returned if the connection has
  become invalid" (OSRC connection.py, property docstring). It bounds one
  round trip, so one fetch batch or one `executemany` batch, not a whole
  statement. `Connection.cancel()`: "Breaks a long-running statement."
- Connect: `retry_count` default 0, `retry_delay` default 1 s,
  `tcp_connect_timeout` default 20.0 s, `expire_time` (keepalive, minutes)
  default 0 (OSRC connection.py, `connect()` docstring).
- Pooling: "The main use case is for applications that hold connections for
  relatively short durations while doing database work ... Using a driver pool
  is recommended for applications that need to support multiple users" (ODOC
  user_guide/connection_handling.rst L3470-3478). A batch job that holds one
  session for its whole run is the other case.
- Threads: `threadsafety = 2`, "threads may share the module and connections,
  but not cursors" (OSRC __init__.py L194-200); "Each connection to Oracle
  Database can only execute one statement at a time" (ODOC
  user_guide/sql_execution.rst L961). What two threads calling one connection
  at once get (wait or error) is unconfirmed.

#### 1.8 TLS, wallets, Kerberos, tokens

See the table in 1.2. In addition: "Both python-oracledb Thin and Thick modes
support TLS" (ODOC user_guide/connection_handling.rst L4961); "The
python-oracledb Thick mode can additionally use Oracle Database's native
network encryption" (L4971); token authentication "allows users to connect to
a database by using an encrypted authentication token without having to enter
a database username and password" (ODOC user_guide/authentication_methods.rst
L437). JDBC connection strings do not work as they are:
`jdbc:oracle:thin:@host:port/service` is `host:port/service`, and
`jdbc:oracle:thin:@host:port:sid` needs the `sid` parameter (ODOC
user_guide/connection_handling.rst L568-600).

#### 1.9 PL/SQL

- `Cursor.callproc(name, parameters=None, keyword_parameters=None) -> list`,
  `Cursor.callfunc(name, return_type, parameters=None, keyword_parameters=None)`
  (OSRC cursor.py L938, L967). "Calling `Cursor.callproc()` internally
  generates an anonymous PL/SQL block and executes it. This is equivalent to
  ... `cursor.execute("begin myproc(:1,:2); end;", [123, out_val])`" (ODOC
  user_guide/plsql_execution.rst L57-63).
- OUT and IN OUT: `out_val = cursor.var(int)`, then `out_val.getvalue()`
  (L53-55). "Oracle Database requires a type, even for null values. When you
  pass the value None, then python-oracledb assumes its type is a string"
  (same file, "Passing NULL values to PL/SQL").
- REF CURSOR: "A newly opened cursor can be bound to the REF CURSOR parameter
  ... the cursor can then be fetched just like any other cursor"; a function
  returning one uses `oracledb.DB_TYPE_CURSOR` as return type (ODOC
  user_guide/bind.rst L432-461). Set `arraysize` on that cursor; prefetch is
  ignored (ODOC user_guide/tuning.rst L319-352). 26.0.1 fixed a "hang with
  NUMBER input and SYS_REFCURSOR output bind variables" (#600).
- Implicit results: `cursor.getimplicitresults()` after
  `dbms_sql.return_result`; "It needs Oracle Database 12.1 (or later)" (ODOC
  user_guide/plsql_execution.rst L412-440).
- A procedure for many rows in one round trip: `executemany("begin myproc(:1,
  :2); end;", data)` with `cursor.var(type, arraysize=len(data))` given to
  `setinputsizes` for the OUT bind; "in python-oracledb Thick mode ... it will
  have the same performance characteristics as repeated calls to `execute()`"
  (ODOC user_guide/batch_statement.rst L238-290).
- A stored object created with errors does not raise: look at
  `cursor.warning` (`DPY-7000`) (ODOC user_guide/plsql_execution.rst,
  "PL/SQL Compilation Warnings").

#### 1.10 Saying who runs a statement

"The connection attributes `Connection.client_identifier`,
`Connection.clientinfo`, `Connection.dbop`, `Connection.module`, and
`Connection.action` set metadata for end-to-end tracing ... After attributes
are set, the values are sent to the database when the next round-trip to the
database occurs" (ODOC user_guide/tracing.rst L52-78): no extra round trip.
`module`: "The maximum length for this string is 48 and if you exceed this
length you will get ORA-24960" (OSRC connection.py). `connect()` also takes
`program`, `machine`, `osuser`, `terminal`, `driver_name` (since 2.5.0), and
thin mode exposes `Connection.session_id` and `serial_num`.
`Connection.transaction_in_progress` says "whether a transaction is currently
in progress". Bind values can show in server traces and audit trails ("Values
may appear in logs and audit trails", tracing.rst L57).

#### 1.11 Errors

Every exception derives from `oracledb.Error`; the error object has `code`,
`full_code`, `message`, `offset`, `isrecoverable` (ODOC
user_guide/exception_handling.rst; OSRC errors.py). In thin mode a database
error message gets a second line, `Help: https://docs.oracle.com/error-help/db/ora-NNNNN/`
(OSRC errors.py, `_make_adjustments`): a log line has to be made one line.
Thin network errors are `DPY-` messages, not `ORA-12xxx`.

### Q2. Polars 1.44.2 and databases

#### 2.1 pl.read_database

Signature (installed, `inspect.signature`):

```python
pl.read_database(query, connection, *, iter_batches=False, batch_size=None, schema_overrides=None,
                 infer_schema_length=100, execute_options=None) -> DataFrame | Iterator[DataFrame]
```

- `connection`: any object with `cursor()` or `execute()`, a SQLAlchemy
  object, an ADBC connection, or an ODBC connection string, "in which case the
  `arrow-odbc` package will be used" (docstring; PL44
  io/database/functions.py L82-86). A URI string is refused here: "string URI
  is invalid here; call `read_database_uri` instead" (L245-260).
- Arrow fast path: only for the drivers in `ARROW_DRIVER_REGISTRY`: adbc,
  arrow-odbc (through the string), databricks, duckdb, oracledb (minimum
  3.0.0), snowflake, turbodbc (PL44 io/database/_arrow_registry.py). pyodbc,
  pymssql and mssql-python are not in it: they go the row-wise way
  (`fetchall` / `fetchmany` into Python tuples, `_from_rows`).
- For a python-oracledb connection (Observed with the stand-in):
  `read_database` calls `connection.fetch_df_all(query, **execute_options)`,
  and with `iter_batches=True, batch_size=N`
  `connection.fetch_df_batches(query, size=N, **execute_options)`.
  `execute_options` reach the driver as keyword arguments, so
  `{"parameters": [...]}` binds. `iter_batches=True` without `batch_size`
  raises `ValueError`. With oracledb 2.5.1 it raises
  `ModuleUpgradeRequiredError`.
- `schema_overrides` does nothing on this path in 1.44.2: the frame is built
  with `DataFrame(batch)` and the overrides are applied only when the batch
  already is a Polars frame (PL44 io/database/_executor.py L248-251).
  Observed: `{"AMOUNT": pl.Decimal(38, 2), "ID": pl.Int32}` left Float64 and
  Int64. 2.0.0 lists "Apply "schema_overrides" in `read_database` for
  Arrow-based drivers (#29273)" among its bug fixes and asks for oracledb
  3.4.0.
- The "read queries only" guard is a first-word test against an upper-case
  list (ALTER, CREATE, DELETE, DROP, INSERT, UPDATE and others; PL44
  _executor.py L46-60, L541-545). Observed: `MERGE`, `TRUNCATE`,
  `BEGIN ... END;` and a lower-case `update` pass. It is no safety device.
- With an ODBC string, each call opens its own connection through
  `arrow_odbc.read_arrow_batches_from_odbc` (PL44
  io/database/_cursor_proxies.py L51-64): it cannot share a session.

#### 2.2 pl.read_database_uri and DataFrame.write_database

```python
pl.read_database_uri(query, uri, *, partition_on=None, partition_range=None, partition_num=None,
                     protocol=None, engine=None, schema_overrides=None, execute_options=None,
                     pre_execution_query=None) -> DataFrame
DataFrame.write_database(table_name, connection, *, if_table_exists="fail", engine=None,
                         engine_options=None) -> int
```

- `read_database_uri` returns one whole DataFrame. `engine="connectorx"` (the
  default) calls `cx.read_sql(conn=uri, query=..., return_type="arrow", ...)`;
  "the 'connectorx' engine does not support use of `execute_options`", so no
  bind values; the password is in the URI (Polars rewrites it out of error
  texts). `engine="adbc"` imports `adbc_driver_<scheme>` and "ADBC currently
  only supports positional 'qmark' style parameterization" (docstring; PL44
  io/database/_utils.py L35-123).
- `write_database` is an eager DataFrame method with two engines:
  "sqlalchemy" "currently inserts using Pandas' `to_sql` method", and "adbc"
  uses `adbc_ingest` and then calls `conn.commit()` itself (PL44
  dataframe/frame.py L4392, L4681, L4728). Modes: `fail`, `replace`,
  `append`. No merge, no rejected rows, and the commit is not the caller's.

Neither function fits an engine that streams, binds, and commits per subjob.

#### 2.3 Handing a lazy result to Python in batches

Signatures in 1.44.2 (installed; the same in 2.0.0, where `sink_batches`,
`collect_batches` and `register_io_source` are still marked unstable):

```python
LazyFrame.sink_batches(function: Callable[[DataFrame], bool | None], *, chunk_size=None,
                       maintain_order=True, lazy=False, engine="auto", optimizations=...) -> LazyFrame | None
LazyFrame.collect_batches(*, chunk_size=None, maintain_order=True, lazy=False, engine="auto",
                          optimizations=...) -> Iterator[DataFrame]
LazyFrame.sink_ipc(path, *, compression="uncompressed", compat_level=None, record_batch_size=None,
                   maintain_order=True, ..., lazy=False, engine="auto", ...) -> LazyFrame | None
LazyFrame.sink_parquet(path, *, compression="zstd", ..., row_group_size=None, ..., lazy=False, ...)
pl.scan_ipc(source, *, n_rows=None, row_index_name=None, row_index_offset=0, memory_map=True, ...)
polars.io.plugins.register_io_source(io_source, *, schema, validate_schema=False, is_pure=False) -> LazyFrame
```

Docstrings: `sink_batches`: "Evaluate the query and call a user-defined
function for every ready batch ... This functionality is considered
**unstable** ... This method is much slower than native sinks. Only use it if
you cannot implement your logic otherwise"; `chunk_size`: "The number of rows
that are buffered before the callback is called"; returning `True` "signals
that no more results are needed". `register_io_source`: `is_pure`: "Repeated
occurrences of same IO source in a LazyFrame plan can be de-duplicated during
optimization if they are pure."

Observed on 1.44.2, streaming engine:

| Route | What was seen |
|---|---|
| `sink_batches(fn, chunk_size=50_000, lazy=True)` in `pl.collect_all` with a `sink_csv(lazy=True)` and a tap | ran in the one pass; 20 batches of exactly 50,000 rows of 1,000,000; in row order and contiguous; all calls on one thread, which was not the main thread; never two calls at once; with `maintain_order=False` the same here; without `chunk_size` 44 batches of 3,351 to 25,101 rows |
| exception raised in the callback | reaches the `collect_all` caller with its own type and message |
| callback returns `True` | the pass stops after that batch |
| reader pace | with a Python reader behind it, 3 reader batches were pulled before the first callback and then 2 per callback: the sink holds the reader back |
| `collect_batches(chunk_size=50_000)` | an iterator run on the caller's thread; exact chunks in order; the producer ran about 3 chunks ahead of a slow reader; `lazy=True` starts on the first `next()`; no `stop()` method exists on the object though the docstring names one; it is a run of its own and cannot share a pass with other sinks |
| `map_batches(fn, streamable=True, schema=...)` | one call per morsel (44 calls, 3,351 to 25,101 rows); from 12 threads, 10 calls at once, not in row order; may return fewer rows and other columns; two readers of the mapped frame ran the function once here, by the optimizer's choice |
| `register_io_source`, `is_pure=False`, one frame feeding 2 file sinks and 2 taps | the reader function was called 4 times; a sink and a count: 2 times; a self-join: 2 times |
| the same with `is_pure=True` | called once in each case |
| what the reader is handed | `with_columns` (projection), a `pl.Expr` predicate, `n_rows`, `batch_size=100000`; `collect_schema()` does not call it |
| a plan that needs no column (the engine's own row count, `with_row_index` then `max`) | the reader is handed `with_columns=[]`; a reader that selects exactly those returns frames of height 0 and the count comes out `None`. A reader that ignores `with_columns` is right: Polars projects itself |
| early stop (`head(5)` behind a filter) | `collect` returned after 2 reader batches; one more was pulled afterwards; the generator was not closed one second and a `gc.collect()` later |
| the reader raises | the caller gets `polars.exceptions.ComputeError: caught exception during execution of a Python source, exception: RuntimeError: ORA-...`; the generator's `finally` ran |
| a failure downstream of the reader | the generator was closed (its `finally` ran) |
| a batch whose dtype differs from the declared schema | `SchemaError`, with and without `validate_schema` |

Spool files (Observed; 40,000,000 rows of an int, a Decimal(38,2) and a short
string; 2,195 MB as uncompressed Arrow IPC):

| Step | Peak RSS | Time |
|---|---|---|
| read the IPC file one record batch at a time with pyarrow, no memory map (`pa.OSFile`) | 91 MB | 1.0 s |
| `pq.ParquetFile.iter_batches(50_000)` | 192 MB | 1.9 s |
| `pl.scan_parquet` (zstd, row groups of 100,000) into `sink_batches` | 560 MB | 0.4 s |
| `pl.scan_parquet` (lz4) into `sink_batches` | 960 MB | 0.3 s |
| `pl.scan_ipc(memory_map=True)` into `sink_batches` | 2,460 MB (mapped file pages are counted) | 0.8 s |
| `pl.scan_ipc(memory_map=False)` into `sink_batches` | 3,020 MB: more than the file | 0.2 s |
| writing 100,000-row batches as they arrive: `pyarrow.ipc.new_file` | 148 MB | 1.7 s |
| the same with `pq.ParquetWriter(compression="lz4")` | 257 MB | 11.1 s |

Also Observed: `sink_ipc` wrote record batches of 100,000 rows here with and
without `record_batch_size`; a file written by pyarrow batch by batch scans
with `row_index_name`; an IPC stream (no footer) does not scan
(`InvalidFooter`); lz4 made the IPC file 666 MB.

Inferred: for a file Polars has to scan lazily with flat memory on 1.44.2,
Parquet is the safe format and uncompressed IPC is not. For a file a Python
loader reads back batch by batch, IPC read with pyarrow is flat and fastest.

### Q3. SQL Server from Python, compared

| Driver | Status (own sources) | On RHEL | On an Apple Silicon Mac | Read path | Bulk-load path | Type fidelity |
|---|---|---|---|---|---|---|
| **pyodbc** + Microsoft ODBC Driver 18 | 5.3.0 of 2025-10-17, community (mkleehammer); commits to 2026-10-03 ("support Python 3.15") | wheel (manylinux2014) plus `unixODBC` ("Linux wheels ... do not include their own copies of the unixODBC library files") plus `msodbcsql18` from Microsoft's repository (`ACCEPT_EULA=Y yum install -y msodbcsql18`; driver 18.7 supports RHEL 8, 9, 10) | `brew install unixodbc`; `brew tap microsoft/mssql-release`, `HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18`; arm64 wheels since 5.1.0; ODBC driver arm64 since 17.8 | rows as Python objects; no Arrow | `fast_executemany` (4.0.19): "all the parameters are sent to the database server in one bundle"; "only recommended for applications that use Microsoft's ODBC Driver for SQL Server"; no bulk copy API | decimal to `decimal.Decimal`, bit to bool; mature |
| **mssql-python** (Microsoft) | 1.15.0 of 2026-09-11; "Generally Available (GA) and ready for production use" since 1.0.0 (2025-11-18); a release about every two weeks; 74 open issues | wheel (manylinux_2_28: glibc 2.28, RHEL 8 or later); `dnf install -y libtool-ltdl krb5-libs`; pulls `mssql-python-odbc==18.6.2.1` (the ODBC Driver 18 binaries, "Other/Proprietary License") and `azure-identity>=1.12.0`; pyarrow for Arrow | `brew install openssl`; wheel `macosx_15_0_universal2` | DB-API rows, or Arrow: `cursor.arrow()`, `arrow_batch()`, `arrow_reader(batch_size=8192)` since 1.5.0 (2026-04-10); "pyarrow must be installed" | `cursor.bulkcopy()` (1.4.0) and `bulkcopy_arrow(table_name, source)` (1.13.0), through a Rust TDS core; "`cursor.bulkcopy()` opens a separate connection" (1.12.0 notes), so it is outside the cursor's transaction | by its own tests at v1.15.0: decimal(p,s) to decimal128(p,s); datetime2(0..7) all to timestamp[us] (the seventh digit is lost); datetimeoffset to timestamp with tz `+00:00` (the offset is lost, the instant kept); uniqueidentifier to upper-case text; tinyint to uint8; time to time64[ns] |
| **arrow-odbc** + ODBC Driver 18 | 10.6.0 of 2026-10-07; one maintainer (pacman82), 2 open issues, frequent releases | wheel (`manylinux_2_28`, any CPython; built with "target-cpu=x86-64-v3" since 9.3.7) plus `unixODBC` ("The provided wheels dynamically link against the driver manager") plus `msodbcsql18` | wheel `macosx_11_0_arm64` plus `brew install unixodbc` plus `msodbcsql18` | Arrow record batches with bounded buffers (`batch_size`, `max_bytes_per_batch`, `max_text_size`), `query_timeout_sec`, a fetching thread (`fetch_concurrently`); "Currently all parameters are passed as VARCHAR strings" | `insert_into_table(reader, chunk_size, table)`: ODBC array inserts; manual commit mode since 10.1.0 | README table: Numeric/Decimal(p<=38) to Decimal128; Timestamp(p>=7) to nanoseconds (out of range before 1677 and after 2262); Bit to Boolean; "All others" to Utf8 (so datetimeoffset and uniqueidentifier as text); an explicit `schema` can override |
| **ADBC driver for SQL Server** | 1.6.2 of 2026-09-10; in Apache's driver table as maintained by "Foundry", not by the ASF; "The source code for this project is private"; "Permissive Binary License" | `adbc-driver-manager` wheel plus the driver binary from Columnar's registry (`dbc install mssql`); linux amd64 and arm64; the registry and `dbc` "are provided by Columnar, and are maintained independently of the Apache Arrow project" | macOS arm64 binary, same way | Arrow | `adbc_ingest` (create, append, replace) | per its page: DECIMAL and MONEY to decimal128; DATETIME, DATETIME2 to timestamp[us]; UNIQUEIDENTIFIER to `arrow.uuid`; DATETIMEOFFSET not in the table |
| **connectorx** | 0.4.6 of 2026-09-17; community ("Special thanks to @oystersuki for actively maintaining the repo"); 228 open issues | wheel only (manylinux_2_28, about 60 MB); no ODBC | wheel (`macosx_11_0_arm64`) | Arrow table for the whole result, or `return_type="arrow_stream"` with `batch_size`; partitioned parallel reads; own connections from a URI; no bind values | none (read only) | its table gives NUMERIC as float64 and DECIMAL as float64 with the note "cannot support precision larger than 28"; 0.4.6 "use Decimal128 for MSSQL/MySQL DECIMAL types in Arrow destinations"; DATETIMEOFFSET to datetime64[ns] |
| **pymssql** | 2.4.4 of 2026-10-10, maintained; FreeTDS 1.5.19 inside the wheels; LGPL 2.1 | wheel only (manylinux_2_27/2_28) | wheel (`macosx_14_0_arm64`) | rows as Python objects; no Arrow | BCP operations (changelog 2.4.0 mentions "datetime conversion for BCP operations") | row-wise; not compared here |
| **turbodbc** | 5.3.0 of 2026-07-01; PyPI has the source only, no wheels | compile it (unixODBC headers, C++ compiler, the Arrow C++ of the installed pyarrow) or use conda-forge | the same | Arrow (`fetchallarrow`, `fetcharrowbatches`) | Arrow inserts | arrow-odbc's README: "build against the C++ implementation of Arrow, which implies it is only compatible with matching version of pyarrow" |
| **bcp** utility | `mssql-tools18` 18.7.1.1, September 2026 | `yum install mssql-tools18` (with `msodbcsql18`) | `brew install mssql-tools18` | exports a table or a query to a file | native bulk load of a file | character mode has no types; not a library |

Sources: PyPI JSON of each package; pyodbc wiki (Install; Cursor;
Features-beyond-the-DB-API); MSD connect/odbc/linux-mac/system-requirements.md
(ms.date 2026-09-07), installing-the-microsoft-odbc-driver-for-sql-server.md
(2026-10-07), install-microsoft-odbc-driver-sql-server-macos.md (2026-09-19),
release-notes-tools.md; microsoft/mssql-python README, releases and wiki
(Cursor, Calling-Stored-Procedures, Known-Issues) and
`tests/test_004_cursor_arrow.py` at v1.15.0; pacman82/arrow-odbc-py README,
releases and `python/arrow_odbc/read_arrow_batches_from_odbc.py` at v10.6.0;
apache/arrow-adbc `docs/source/driver/index.rst` (main), adbc-drivers/mssql
README, adbc-drivers.org/drivers/mssql; sfu-db/connector-x docs at v0.4.6
(api.md, databases/mssql.md) and releases; pymssql ChangeLog.rst;
blue-yonder/turbodbc README.

Further facts that weigh on the choice:

- No source gives comparable read speeds. connectorx claims "3x less memory
  and 14x less time compared with Pandas" for SQL Server and mssql-python's
  notes claim gains for its own paths; none was measured here.
- ODBC Driver 18 changed a default: for `Encrypt`, "The default value is `yes`
  in version 18.0 and later versions, and `no` in earlier versions" (MSD
  connect/odbc/dsn-connection-string-attribute.md, ms.date 2026-09-27). v1
  asks for "ODBC Driver 17 for SQL Server"
  (`src/v1/engine/mssql_connection_manager.py:26`), and Driver 17 is "in
  maintenance mode and receive only critical security updates".
- mssql-python: `callproc()` "raises NotSupportedError"; procedures are called
  with `{CALL ...}` and OUT values through a T-SQL batch (wiki,
  Calling-Stored-Procedures). `Connection.timeout` is the query timeout in
  seconds, default 0. Its licence is MIT except the driver binaries, "licensed
  under MICROSOFT SOFTWARE LICENSE TERMS".
- ADBC: Apache's table lists no ASF-maintained driver for SQL Server and no
  driver for Oracle at all.

### Q4. Loading patterns, and what makes a load repeatable

#### 4.1 The patterns

| Pattern | What runs | All or nothing | Same input twice gives the same table | Cost |
|---|---|---|---|---|
| append | INSERT | yes, in one transaction | no: "`append` doesn't check for duplicates ... it will be inserted again" (dbt) | least |
| truncate, then insert | TRUNCATE; INSERT | Oracle: no (finding 3). SQL Server: yes, "A TRUNCATE TABLE operation can be rolled back within a transaction" (MSD t-sql/statements/truncate-table-transact-sql.md) | yes | the table is empty while the load runs (Oracle) |
| delete all, then insert | DELETE; INSERT; COMMIT | yes | yes | undo and redo for every old and new row |
| delete by key or partition, then insert | DELETE WHERE key in new; INSERT | yes | yes for the keys loaded | needs a key |
| merge / upsert | MERGE, or update then insert | yes | yes when keyed | needs a key; "can be expensive for large tables because it scans the entire destination table" (dbt) |
| staging, then switch | load a staging table; one transaction or an exchange applies it | yes at the switch | yes | DDL rights; space twice. dlt: "will load all new data into staging tables away from your final destination tables and will then truncate and insert the new data in one transaction" |

Batch size and commit frequency: a commit every N rows (Talend's `Commit
every`, Hop's `Commit size`, Spark's one transaction per partition) keeps undo
small and leaves a part of the load behind when the run fails. Spark says it
of itself: "these save modes do not utilize any locking and are not atomic"
(apache/spark docs/sql-data-sources-load-save-functions.md). One transaction
for the load costs undo for the whole of it. Batch size (rows per round trip)
and commit frequency are separate settings.

#### 4.2 Bulk routes and what they skip

| Route | What it skips or changes | Source |
|---|---|---|
| Oracle direct-path INSERT (`/*+ APPEND */`) | "Data is written directly into data files, bypassing the buffer cache. Free space in the existing data is not reused." Restrictions: "The target table cannot have any triggers or referential integrity constraints defined on it"; if a restriction is violated "Oracle Database executes conventional INSERT serially without returning any message"; "You cannot query or modify direct-path inserted data immediately after the insert is complete ... ORA-12838 ... You must first issue a COMMIT" | Oracle SQL Language Reference 19c, INSERT |
| SQL*Loader direct path | "formatting Oracle data blocks, and then writing the data blocks directly to the database files"; NOT NULL, UNIQUE and PRIMARY KEY stay enabled, CHECK and FOREIGN KEY are disabled; "Table insert triggers are also disabled when a direct path load begins ... insert triggers do not fire for any rows loaded on the direct path"; a data save: "Rows cannot be rolled back after a data save"; indexes can be left "Index Unusable" | Oracle Utilities 19c, Conventional and Direct Path Loads |
| OCI direct path API (what python-oracledb speaks) | section 1.5 | |
| Oracle external tables | the server reads the file: the file has to be on the database host | Oracle Utilities (not studied further) |
| SQL Server BULK INSERT | "Without the `CHECK_CONSTRAINTS` option, any `CHECK` and `FOREIGN KEY` constraints are ignored, and after the operation, the constraint on the table is marked as not-trusted. `UNIQUE` and `PRIMARY KEY` constraints are always enforced"; "If `FIRE_TRIGGERS` isn't specified, no insert triggers execute"; `BATCHSIZE`: "Each batch is copied to the server as one transaction" | MSD t-sql/statements/bulk-insert-transact-sql.md (ms.date 2026-03-20) |
| SQL Server minimal logging | needs `TABLOCK`, a table that is not replicated, and the simple or bulk-logged recovery model; "For a database under the full recovery model, all row-insert operations that are performed by bulk import are fully logged" | MSD relational-databases/import-export/prerequisites-for-minimal-logging-in-bulk-import.md |

#### 4.3 Rows the database turns away

| Mechanism | How it reports | Limits |
|---|---|---|
| python-oracledb `batcherrors` | per row: message and offset in the batch; the good rows of the batch are applied; the transaction stays open | DML only, not PL/SQL (1.6) |
| Oracle `LOG ERRORS INTO t REJECT LIMIT n` | bad rows go to an error table on the server; "The default rejection limit is zero" | not logged: "Violated deferred constraints", "Any direct-path INSERT or MERGE operation that raises a unique constraint or index violation", "Any update operation UPDATE or MERGE that raises a unique constraint or index violation"; no LONG, LOB or object columns (Oracle SQL Language Reference 19c, INSERT) |
| SQL*Loader | bad file; `ERRORS` default 50; exit codes on Linux `EX_SUCC 0`, `EX_FAIL 1`, `EX_WARN 2` ("All or some rows rejected"), `EX_FTL 3` | Oracle Utilities 19c, SQL*Loader Command-Line Reference. v1 reads the codes the other way: "0 OK, 1 OK with warnings, 2 fatal/discontinued, 3 error", and fails only at 2 or more (`src/v1/engine/components/database/oracle_bulk_exec.py:406-411`) |
| SQL Server BULK INSERT | `MAXERRORS` (default 10), `ERRORFILE` for rows "that have formatting errors" | format errors only |
| Apache Hop Table output | "Ignore insert errors ... A maximum of 20 warnings will be logged however. This option is not available for batch inserts"; before the load: "To find which rows, columns and values the database would reject before writing, put Database value validation in front of this transform" | apache/hop docs, pipeline/transforms/tableoutput.adoc |
| Talend tOracleOutput | a REJECT flow with `errorCode` and `errorMessage`, not offered when a batch size is used: `NOT_SHOW_IF="(DIE_ON_ERROR == 'true') OR (isShow[BATCH_SIZE])"`; in batch mode, with "Die on error" off, a failed batch is printed to standard error and the job goes on | TX tOracleOutput/tOracleOutput_java.xml L30-31; tOracleOutput_main.javajet L1273-1298, L1339-1364 |

#### 4.4 How tools name the choices

| Tool | Setting | Values |
|---|---|---|
| dbt | `incremental_strategy` | `append`, `merge`, `delete+insert`, `insert_overwrite`, `microbatch`; with `unique_key`, `merge_update_columns`, `merge_exclude_columns`. All of them apply a temporary relation to the target |
| dlt | `write_disposition` | `append`, `replace`, `merge`. `replace_strategy`: `truncate-and-insert` (default: "truncated at the beginning of the load, and the new data will be inserted consecutively but not within the same transaction ... You may end up with new data in some tables and no data in other tables if the load fails"), `insert-from-staging`, `staging-optimized`. Merge strategies: `delete-insert` (default; "All of this occurs within a single atomic transaction"), `scd2`, `upsert`, `insert-only`, `cdc` |
| Airbyte | destination half of the sync mode | Overwrite, Append, Append Deduped, Overwrite Deduped |
| Spark JDBC writer | `SaveMode` | `ErrorIfExists` (default), `Append`, `Overwrite`, `Ignore`; options `truncate` ("due to the different behavior of TRUNCATE TABLE among DBMSes, it's not always safe to use this"), `batchsize` (1000), `isolationLevel` (READ_UNCOMMITTED), `queryTimeout`, `numPartitions` |
| Sling | `mode` | `full-refresh` (default: "The target table will be dropped and recreated"), `incremental`, `truncate`, `snapshot`, `backfill`, `definition-only`, `change-capture`; "All modes load into a new temporary table prior to final load"; for Oracle it uses `sqlldr` "if present in PATH" |
| Apache Hop Table output | options | Commit size, Truncate table, Truncate on first row, Ignore insert errors, Use batch update for inserts, Automatically update table structure, Always drop and recreate table. "Table Output is equivalent to the DML operator INSERT" |
| Talend tOracleOutput | Action on table (`TABLE_ACTION`) | `NONE` "Default", `DROP_CREATE` "Drop and create table", `CREATE` "Create table", `CREATE_IF_NOT_EXISTS` "Create table if does not exist", `DROP_IF_EXISTS_AND_CREATE` "Drop table if exists and create", `CLEAR` "Clear table", `TRUNCATE` "Truncate table", `TRUNCATE_REUSE_STORAGE` "Truncate table with reuse storage" (TX tOracleOutput/tOracleOutput_java.xml L197-214; tOracleOutput_messages.properties) |
| Talend tOracleOutput | Action on data (`DATA_ACTION`) | `INSERT` "Insert", `UPDATE` "Update", `INSERT_OR_UPDATE` "Insert or update", `UPDATE_OR_INSERT` "Update or insert", `DELETE` "Delete" (same file L222-234) |
| Talend tOracleBulkExec | Action on data | `INSERT`, `UPDATE`, `APPEND`, `REPLACE`, `TRUNCATE`: SQL*Loader's load methods (TX tOracleBulkExec/tOracleBulkExec_java.xml L218-232) |

Sources for the first six rows: dbt-labs/docs.getdbt.com
website/docs/docs/build/incremental-strategy.md; dlt-hub/dlt
docs/website/docs/general-usage/incremental-loading.md, full-loading.md,
merge-loading.md; airbytehq/airbyte
docs/platform/using-airbyte/core-concepts/sync-modes/README.md; apache/spark
docs/sql-data-sources-jdbc.md and sql-data-sources-load-save-functions.md;
docs.slingdata.io/concepts/replication/modes and
/connections/database-connections/oracle; apache/hop tableoutput.adoc.

How Talend's two upserts run (TX tOracleOutput/tOracleOutput_main.javajet):
`INSERT_OR_UPDATE` asks `SELECT COUNT(1) FROM table WHERE key` for every row
and then updates or inserts (L687-902); `UPDATE_OR_INSERT` updates and inserts
when nothing was updated (L944-1100). Both are one row and two or three round
trips at a time. With its own connection the component commits every
`COMMIT_EVERY` rows and at the end (L1325-1397; tOracleOutput_end.javajet
L273-292); with an existing connection it never commits.

Two things current loaders do that Talend does not: dlt "Fully extracts the
data from your source to your hard drive" into a load package before anything
is loaded, and "If the connection to the destination fails, it is safe to
rerun the pipeline" (reference/explainers/how-dlt-works.md); and "Table
truncation/drop happens when the load step starts, so a failed extract or
normalization does not affect destination data" (incremental-loading.md).

### Q5. Reading patterns

- **Work in the SQL.** Spark pushes filters, aggregates and limits by default
  (`pushDownPredicate`, `pushDownAggregate`, `pushDownLimit`), wraps a query
  as `SELECT <columns> FROM (<user_specified_query>) spark_gen_alias`, and
  lets types be stated: `customSchema`, "For example, "id DECIMAL(38, 0), name
  STRING"" (docs/sql-data-sources-jdbc.md). python-oracledb's guide: "avoiding
  selecting columns not used in the application" (ODOC user_guide/tuning.rst
  L38-39).
- **Partitioned parallel reads.** connectorx: "The function will partition the
  query by evenly splitting the specified column ... ConnectorX will assign
  one thread for each partition ... Currently, we support partitioning on
  numerical columns (cannot contain NULL) for SPJA queries"; it first runs a
  schema query, a `MIN`/`MAX` query and a `COUNT` per partition (docs/intro.md
  at v0.4.6). Spark: `partitionColumn`, `lowerBound`, `upperBound`,
  `numPartitions`; the bounds "are just used to decide the partition stride,
  not for filtering the rows". Each partition is a statement of its own on a
  connection of its own. Inferred: the partitions are not read at one point in
  time, since Oracle's consistency is per statement (next point).
  python-oracledb is cautious: "Partitioning the table and reading one
  partition per connection is usually the most efficient database-side
  solution. However, even if a parallel solution appears to be faster, it
  could be inefficient", and asks "Is it better to execute a single query in
  Python but use a PARALLEL query hint?" (ODOC user_guide/sql_execution.rst
  "Fetching Data in Parallel"; user_guide/tuning.rst L366-409).
- **One point in time.** Oracle: "Oracle Database always enforces
  statement-level read consistency, which guarantees that data returned by a
  single query is committed and consistent for a single point in time ... the
  time at which the statement was opened" (Oracle Concepts 19c, Data
  Concurrency and Consistency). For several queries: `SET TRANSACTION READ
  ONLY`, "All subsequent queries in that transaction see only changes that
  were committed before the transaction began", with only queries allowed and
  as "the first statement in your transaction" (SQL Language Reference 19c);
  or `AS OF SCN`, which needs "FLASHBACK and either READ or SELECT privileges
  on those objects" and undo that still exists (Database Development Guide
  19c, Flashback). Long reads: "run the risk that undo data required for read
  consistency may have been reused by a different transaction, raising a
  snapshot too old error". SQL Server: under READ COMMITTED with
  `READ_COMMITTED_SNAPSHOT` off, "Row locks are released before the next row
  is processed", so one long SELECT is not a snapshot; with it on, each
  statement sees "a transactionally consistent snapshot of the data as it
  existed at the start of the statement"; `SNAPSHOT` isolation needs
  `ALLOW_SNAPSHOT_ISOLATION` set to ON (MSD
  t-sql/statements/set-transaction-isolation-level-transact-sql.md, ms.date
  2025-09-26).
- **Fetch size.** Spark: `fetchsize` "can help performance on JDBC drivers
  which default to low fetch size (e.g. Oracle with 10 rows)". python-oracledb:
  1.7. Talend: "Use fetch size" calls `stmt.setFetchSize(n)`, default 1000 (TX
  tOracleInput/tOracleInput_begin.javajet L190-197).
- **Type traps.**

| Database | Trap | Source |
|---|---|---|
| Oracle | NUMBER without precision: "The absence of precision and scale designators specifies the maximum range and precision"; precision 1 to 38, scale -84 to 127 | SQL Language Reference 19c, Data Types |
| Oracle | DATE holds a time; no fractional seconds, no zone | same |
| Oracle | `''` is NULL | 1.3 |
| Oracle | CHAR is blank-padded (Talend's "Trim all the String/Char columns" exists for it) | TX tOracleInput/tOracleInput_messages.properties; padding itself unconfirmed here |
| SQL Server | `datetime`: "Rounded to increments of .000, .003, or .007 seconds" | MSD t-sql/data-types/datetime-transact-sql.md (ms.date 2026-06-29) |
| SQL Server | `datetimeoffset`: accuracy 100 ns, offset kept; drivers above return UTC or text | MSD t-sql/data-types/datetimeoffset-transact-sql.md; Q3 |
| SQL Server | `datetime2(7)`: 100 ns; mssql-python gives microseconds, arrow-odbc nanoseconds | Q3 |
| SQL Server | `uniqueidentifier`: "ordering is not implemented by comparing the bit patterns"; text case differs by driver | MSD t-sql/data-types/uniqueidentifier-transact-sql.md; Q3 |
| SQL Server | `money`: "accurate to a ten-thousandth"; "You can experience rounding errors through truncation ... Instead, use the decimal data type" | MSD t-sql/data-types/money-and-smallmoney-transact-sql.md |
| SQL Server | `bit` is a boolean with nulls; `tinyint` is unsigned | Q3 |

### Q6. Connections and transactions in pipelines

- **The connection is a named, shared thing.** Airflow: "A Connection is
  essentially set of parameters - such as username, password and hostname -
  along with the type of system that it connects to, and a unique name, called
  the conn_id"; hooks "integrate with Connections to gather credentials"
  (apache/airflow airflow-core/docs/authoring-and-scheduling/connections.rst).
  Dagster: resources "provide access to external systems, databases, or
  services"; "Resources are configurable and shared, so configuration can be
  supplied in one place instead of individually"
  (docs/guides/build/external-resources/index.md). Prefect: "Prefect blocks
  store typed configuration that can be used across workflows ... The most
  common use case for blocks is storing credentials"
  (docs/v3/concepts/blocks.mdx). dbt: one profile per target. Talend's
  tOracleConnection is the same idea inside one job, kept in globalMap as
  `conn_<id>` (TX tOracleConnection/tOracleConnection_begin.javajet L98).
- **Secrets stay out of configs and logs.** dbt: `env_var` in `profiles.yml`
  "(to avoid putting credentials on a server)". Dagster: "Using `EnvVar` not
  only tells Dagster to retrieve the value at runtime, but also not to display
  the value in the UI". Prefect: `SecretStr` fields "stored with additional
  encryption and not displayed by default". Airflow masks by value: "It does
  this by looking for the specific *value* appearing anywhere in your output",
  for connection passwords and for fields whose names hold `password`,
  `secret`, `token`, `api_key`, `private_key` and others
  (airflow-core/docs/security/secrets/mask-sensitive-values.rst). Talend does
  the opposite: it puts `password_<id>` into globalMap (TX
  tOracleConnection/tOracleConnection_begin.javajet L200) and runs `sqlldr
  'user/password@service'` as a command line (TX
  tOracleBulkExec/tOracleBulkExec_begin.javajet L599), of which Oracle says
  "For security reasons, Oracle recommends that you specify only the user name
  on the command line" (Oracle Utilities 19c). v1 copies the command line
  (`src/v1/engine/components/database/oracle_bulk_exec.py:316-337`).
- **Retry.** python-oracledb retries the connect only (`retry_count`,
  `retry_delay`). After an outage a commit's fate is unknown: Transaction
  Guard "enables Python application to verify the success or failure of the
  last transaction in the event of an unplanned outage" (ODOC
  user_guide/ha.rst L166-175). Inferred: connecting may be retried; a
  statement that may have run, and above all a commit, may not be retried
  blindly; a read may be started again only while none of its rows has been
  handed on.
- **What one transaction spans.** python-oracledb: "Transactions are handled
  at the connection level, meaning changes performed by all cursors obtained
  from a connection will be committed or rolled back together" (ODOC
  user_guide/txn_management.rst L23-25). SQL Server: "When SET XACT_ABORT is
  OFF, in some cases only the Transact-SQL statement that raised the error is
  rolled back and the transaction continues processing"; OFF is the default
  (MSD t-sql/statements/set-xact-abort-transact-sql.md).
- **Session tags.** 1.10. dbt-oracle has `session_info` (`action`,
  `client_identifier`, `client_info`, `module`): "This helps to track dbt
  sessions in the Database view V$SESSION"
  (website/docs/reference/resource-configs/oracle-configs.md). Talend's MSSQL
  connection adds `appName=<project name>` to the URL (TX
  tMSSqlConnection/tMSSqlConnection_begin.javajet L55); its Oracle components
  set nothing.
- **Statement text.** python-oracledb: "Never concatenate or interpolate user
  data into SQL statements ... This is a security risk and can impact
  performance and scalability"; "Bind variables can be used to substitute
  data, but cannot be used to substitute the text of the statement. You
  cannot, for example, use a bind variable placeholder where a column name or
  a table name is required. Bind variable placeholders also cannot be used in
  Data Definition Language (DDL) statements" (ODOC user_guide/bind.rst
  L33-55). For names there are, since 4.0.0, `enquote_name()`,
  `enquote_literal()`, `is_qualified_sql_name()`, `is_simple_sql_name()` "to
  assist developers in avoiding SQL injection" (ORN L301); on Python 3.14 a
  template string given to `execute()` turns each interpolation into a bind
  variable, with `{name:i}` for a name (ODOC user_guide/sql_execution.rst
  L1165-1260). Talend builds the statement as a Java string and evaluates it
  for every row (`query_<cid> = <dbquery>;`, TX
  tOracleRow/tOracleRow_main.javajet L58).

### Q7. Stored procedures and arbitrary SQL

- IN, OUT, IN OUT, functions, REF CURSOR, implicit results: 1.9.
- **Several statements in one text.** `execute()` takes one statement.
  Nothing in the python-oracledb docs offers a script; several statements go
  in one PL/SQL block (`begin ...; ...; end;`). What a trailing `;` on plain
  SQL gives is not stated (unconfirmed; `ORA-00933` is expected). SQL Server
  takes a batch of statements in one text and returns several result sets
  (`nextset()`).
- **DDL.** "When Data Definition Language (DDL) statements such as CREATE are
  executed, Oracle Database will always perform a commit" (ODOC
  user_guide/txn_management.rst L31-33), before and after (finding 3). DDL
  inside PL/SQL (`EXECUTE IMMEDIATE`, as in the committed sample
  `tests/talend_xml_samples/converted_jsons/Job_tOracleRow_0.1.json`) cannot
  be seen in the text; `Connection.transaction_in_progress` before and after
  shows that a commit happened (Inferred; to be tried).
- **Timeouts and stopping.** `call_timeout` and `cancel()` (1.7); Spark's
  `queryTimeout`; Talend has a query timeout only on tMSSqlInput (`Set Query
  Timeout`, default 30 s). mssql-python: `Connection.timeout`; arrow-odbc:
  `query_timeout_sec`.
- **What Talend's components do.** tOracleRow "Executes an SQL query at each
  of Talend flow's iterations": once per incoming row, or once with no input;
  prepared-statement parameters are `(index, type, Java expression)` with 16
  types (TX tOracleRow/tOracleRow_java.xml L325-354); the row is handed on;
  with `PROPAGATE_RECORD_SET` a live `ResultSet` object is put into a column.
  tOracleSP prepares `{? = call name(?,?)}` once and executes it per row; a
  `RECORDSET` argument is registered as `OracleTypes.CURSOR` and the row gets
  the `ResultSet` object (TX tOracleSP/tOracleSP_main.javajet L292-341);
  `NLS_LANGUAGE` and `NLS_TERRITORY` are pasted into `ALTER SESSION`.
  tOracleBulkExec has no flow at all (`FLOW MAX_INPUT="0" MAX_OUTPUT="0"`):
  it "Loads efficiently data from a file" by running `sqlldr`.

### Q8. Testing against real databases

| Image | Tags | Architectures | Compressed size | Source |
|---|---|---|---|---|
| `gvenzl/oracle-free` | `slim`, `latest` (regular), `full`, each also `-faststart`; `23.26.3*` "Supported", `23.26.2*` "Deprecated", older "Unsupported"; `23-slim-faststart` (v1's choice) exists and follows 23.26.3; updated 2026-08-30 | amd64 and arm64 for every current tag: "Starting with Oracle Database 23.5 Free, Oracle provides ARM ports ... Multi-platform (multi-arch) images are provided starting with 23.5" | slim 848 MB (amd64) / 714 MB (arm64); slim-faststart 1,319 / 1,205; regular 1,186 / 1,002; regular-faststart 1,661 / 1,493; full 2,252 / 2,009; full-faststart 2,783 / 2,539 | gvenzl/oci-oracle-free README; hub.docker.com/v2/repositories/gvenzl/oracle-free/tags |
| `container-registry.oracle.com/database/free` (Oracle's own) | `latest`, `latest-lite`, `23.26.3.0`, `23.26.3.0-lite` and older | amd64 and arm64 since 23.5.0.0 | `latest` 3,709 MB / 3,528 MB; `latest-lite` 896 MB / 859 MB | the registry's v2 API (tags list and manifests) |
| `mcr.microsoft.com/mssql/server` | `2022-latest` (16.0.4295.3, Ubuntu 22.04), `2025-latest` and `latest` (17.0.5005.3, Ubuntu 24.04) | amd64 only: single-architecture manifests | about 626 MB and 634 MB | mcr.microsoft.com/v2/mssql/server manifests and config blobs |
| `mcr.microsoft.com/azure-sql-edge` | `latest` still lists arm64 and amd64 | | | "Azure SQL Edge is retired as of September 30, 2025"; "Azure SQL Edge no longer supports the ARM64 platform" (Microsoft Learn, archived overview, updated 2025-10-01) |

- Faststart: "The same image flavor as above but with an already expanded and
  ready-to-go database inside the image. This image trades image size on disk
  for a faster database startup time ... Best for (automated) test scenarios"
  (gvenzl README). No source gives a start-up time; v1's conftest says "~15-30s
  cold start" (`tests/v1/engine/components/database/integration/conftest.py:43`),
  not measured here.
- Oracle Free is small: "The maximum amount of user data in Oracle AI Database
  Free cannot exceed 12 GB ... ORA-12954"; RAM 2 GB; "limits itself
  automatically to two cores" (Oracle AI Database Free, Licensing
  Restrictions). A 30 to 100 GB load cannot be tried against it.
- SQL Server containers: "supported only on Linux hosts running on Intel and
  AMD x86-64 CPUs. Emulation or translation environments (for example, Rosetta
  2, Prism, or QEMU) aren't tested or supported"; at least 2 GB of disk and
  2 GB of RAM; `SA_PASSWORD` "is deprecated. Use `MSSQL_SA_PASSWORD` instead"
  (Microsoft Learn, linux/install-upgrade/quickstart-install-docker, ms.date
  2026-05-07). Whether it runs under emulation on this Mac is unconfirmed.
- testcontainers-python 4.15.0 (installed; read in site-packages):
  `testcontainers.community.oracle.OracleDbContainer(image="gvenzl/oracle-free:slim", ...)`
  waits for the log line "DATABASE IS READY TO USE!" and uses `FREEPDB1`;
  `testcontainers.oracle`, which v1's conftest imports, now warns
  "testcontainers.oracle is deprecated, use testcontainers.community.oracle
  instead". `testcontainers.community.mssql.SqlServerContainer` defaults to
  `mcr.microsoft.com/mssql/server:2019-latest`, sets the deprecated
  `SA_PASSWORD`, and waits by running `sqlcmd` inside the container. The core
  package has no container reuse (no file in `testcontainers/core` holds the
  word); the Ryuk reaper removes containers when the session ends.
- One container for a session: a `scope="session"` fixture, as v1 has. Under
  pytest-xdist every worker runs session fixtures itself: "pytest-xdist is
  designed so that each worker process will perform its own collection";
  "While pytest-xdist does not have a builtin support for ensuring a
  session-scoped fixture is executed exactly once", the documented way is a
  `FileLock` around a file under `tmp_path_factory.getbasetemp().parent`
  (pytest-xdist how-to). The repo's gate runs `-n auto`.

---

## 3. What follows for v2 (question 9)

### 3.1 What the engine gives, and what it lacks for a database

Read in `src/v2/engine/runner.py`, `src/v2/engine/context.py`,
`src/v2/components/base.py` and `src/v2/job/keys.py`, at commit `32383de1`
(2026-10-12 07:38, the head of `feature/engine-v2` when this file was
finished; the branch moved while the research ran, and every line number of
`src/v2` and `docs/v2` in this file was checked again at that commit):

- A subjob is built (`_build`, L507-599), run in one `pl.collect_all`
  (`_collect`, L790-838), and then every write is made `ready` and after that
  every write is put in `place` (`_place`, L839-881). "``ready`` is the last
  place the rows can fail the subjob" (base.py L607-608). That is a
  prepare-then-commit shape already.
- A subjob may be run twice: when the fast reader fails it is built and run
  again with the tolerant one (`_run_subjob`, L420-430). After a failure the
  engine collects each component's output again to find the one at fault
  (`_blame`, L882-901), collects again to count dropped rows (`_say_dropped`,
  L471-495), and for `--only` reads the source once more (`_picked_rows`,
  L643-711). All of it assumes that a source can be read again and gives the
  same rows.
- When a subjob fails, `_discard` removes temporary files and nothing else
  (L1031-1034). A `Write` has no way to undo (base.py L600-645), and it is a
  file: a path, a temporary path beside it, a move.
- A source may spool: the engine reads files in other encodings through a
  UTF-8 copy in a scratch folder (`utf8_copies`, context.py L44), and
  `RunContext.temp_path` hands out scratch files in `V2_TEMP_DIR` that are
  removed when the subjob ends (L135-155). The contract allows a source "whose
  format Polars cannot scan" to read in Python (docs/v2/writing-a-component.md
  L13-19).
- Context references in `str` values are pasted in before a component sees
  them (`RunContext.resolve`, context.py L103-120); `CODE` values are left
  alone (`src/v2/job/keys.py:19-23`).
- A config key can be declared a secret since commit `32383de1`, which landed
  while this file was written: `Key(..., secret=True)` (keys.py L62-64, L82).
  At DEBUG the engine logs each component's config through `without_secrets`
  (keys.py L90-93; runner.py L513-515), which shows such a key as `***`, and a
  refusal of its value does not quote it (keys.py L180, L214, L229). The mask
  goes by the key's name at the top level of the config. It does not reach a
  password that stands inside another key's value (a `rac_url` or `jdbc_url`
  of the form `user/password@...`, `properties`), nor a message a driver
  writes. The result object hands globalMap back (`JobResult.global_map`,
  runner.py L212); the printed summary does not hold it (L84-106).
- `oracle_config` and `mssql_config` are already accepted at job level, as
  ignored keys (`src/v2/job/loader.py:127-128`).
- The hidden row-number columns are dropped before a sink is handed its frame
  (docs/v2/writing-a-component.md L338-339), so a sink cannot say which input
  row the database turned away.

### 3.2 The shape recommended, in one paragraph

Every row that crosses between the plan and a database rests once in a local
spool file. A database source runs its query once, binds its values, writes
the result batch by batch to a scratch file, closes the cursor, and hands
Polars a scan of that file. A database output lets Polars write its rows to a
scratch file in the subjob's pass; when the whole pass has succeeded it loads
that file into the database in array batches inside a transaction (`ready`),
and commits when every file of the subjob is being put in place (`place`). A
connection is an object the run holds by the connection component's id; a
component without one opens its own for the subjob. Nothing is committed by
row count. Values are bound; names are checked and quoted; passwords are
masked wherever a config can be printed.

### 3.3 The decisions, each with its options

#### D1. Oracle driver, mode and version

| Option | For | Against |
|---|---|---|
| python-oracledb, thin by default, thick as a job-level switch (`oracle_config.thick_mode`, which v1 has) | no client install; Arrow in and out; maintained by Oracle; thick covers NNE, Kerberos, wallets | the Arrow path is young (finding 7); one mode per process (finding 8) |
| connectorx or ADBC | | no Oracle ADBC driver exists; connectorx has no binds, no shared session, no writes, decimals of 28 digits (Q3, Q5) |
| a JDBC bridge | Talend's exact driver | the engine has no Java, by decision |

Recommendation: python-oracledb, **`oracledb>=26.0.1`** (string views 4.0.0;
direct path fixes 4.0.0 and 4.0.2; decimal and date fixes 26.0.1). The
`<4` pin in `pyproject.toml:18` has to be raised for v2; whether v1 runs on
26.x is a separate check. Thin is the default; `oracle_config.thick_mode:
true` calls `init_oracle_client()` before the first connection. Keep a
row-wise reading route (`cursor.fetchmany`) behind a run setting, so that a
driver bug in the Arrow path can be stepped around without a release, and
compare the row count the database reports with the rows received.

#### D2. The connection as something the run holds

- The connection component is an `Action`: it opens the session, registers it
  in the run under its id, and puts `connectionType_<id>`, `dbschema_<id>`,
  `username_<id>`, `host_<id>`, `port_<id>`, `dbname_<id>` in globalMap as
  Talend does (4.5), and neither `conn_<id>` (an object; globalMap goes into
  the result) nor `password_<id>`.
- A component with `use_existing_connection: true` takes the session of
  `connection`; it is refused at load when that id is no connection component
  of the job. Otherwise it opens its own session for the subjob and closes it
  when the subjob ends.
- One lock per connection around every driver call: a reader and a loader of
  one subjob may be called from different Polars threads (2.3), and "Each
  connection ... can only execute one statement at a time".
- Session tags on every connection: `module` = `dataprep-v2`, `action` = the
  job and component, `client_identifier` and `program` from run settings;
  logged at INFO with the session id and serial number (thin).
- Connection types: `ORACLE_SID` (`sid=dbname`), `ORACLE_SERVICE_NAME`
  (`service_name=dbname`), `ORACLE_RAC` ("Oracle Custom": `rac_url` is a full
  JDBC URL in Talend; strip `jdbc:oracle:thin:@` and pass the rest as `dsn`),
  `ORACLE_OCI` (`local_service_name` as a TNS alias with `tnsnames.ora`; thin
  can), `ORACLE_WALLET` (thick only; say so).
- `properties` (JDBC parameters, `a=b&&c=d`): translate the few that mean
  something to python-oracledb, refuse the rest by name. `encoding`,
  `db_version`, `support_nls`, `datasource_alias` are ignored keys (the driver
  speaks UTF-8; data sources belong to Talend's runtime); `db_version:
  ORACLE_11` needs thick mode and is said.
- `auto_commit: true` on a connection: commit at the end of each subjob that
  succeeded on it, not after each statement. Departure, see 3.4.

#### D3. Oracle input: how rows reach the plan

| Option | Memory | Query runs | Verdict |
|---|---|---|---|
| A. `fetch_df_all` or `pl.read_database`, then `.lazy()` | the whole table | once | no: breaks the memory rule |
| B. a reader registered with `register_io_source(is_pure=True)` that yields `fetch_df_batches` | flat | once per pass, again for blame, dropped-row counts, the second attempt and `--only` (finding 5); on an early stop the generator is left open (2.3); the cursor stays open for the whole pass, on Polars threads; an unstable API | not as the base |
| C. spool: run the query once in `read()`, write batches to a scratch file, close the cursor, return a scan | flat (2.3) | exactly once; every later read is of the file | **recommended** |

Why C fits this engine rather than engines in general: v2 reads sources again
by design, and a failure has to name its row. One execution also gives one
point in time for the result (Q5), frees the cursor before the transformation
(no "snapshot too old" from slow steps downstream, no fetch across a commit on
a shared session), keeps the session off Polars' threads, and makes a read
that broke on the network restartable, since no row has left the component.
dlt does the same ("Fully extracts the data ... to your hard drive"). Cost:
scratch disk about the size of the result, and the transformation starts
after the download.

Details:

- Spool format: Parquet, row groups of the fetch size, read with
  `pl.scan_parquet(..., row_index_name=self.row_number, row_index_offset=1)`.
  On 1.44.2 an IPC scan was not flat in memory (2.3). Keep the spool path in
  `run_context.made[self.id]` so that the second attempt and the `--only`
  probe do not query again.
- Types: build a `pyarrow.schema` from the declared columns and pass it as
  `requested_schema`: `Decimal` to `decimal128(38, places)`, `int` to int64,
  `float` to float64, `str` to large_string, `datetime` to timestamp[us],
  `date` to date32; `bool` is asked for as int8 and compared with zero in
  Polars, since the driver gives a boolean only for a database BOOLEAN (1.3).
  The schema is the job's statement of types; no guessing from the cursor.
  Columns map to the declared ones by position, as in Talend and v1; a
  different column count fails the component.
- Binds: `parameters=` from the statement's context references (D5).
- Fetch size: `cursor_size` when `use_cursor` is on, else a v2 default well
  above 100 (to be measured).
- `trim_all_column` / `trim_column`: in Polars, on `str` columns.
  `no_null_values`: supported with a stated meaning (missing `str` becomes
  empty text), since Oracle cannot return `''`.
- Order: the result's order is the query's. A job whose query has no ORDER BY
  gets the database's order; the documentation says so, and the row numbers in
  messages are then positions in this run's result ("row 7 of the result of
  <id>", with the key columns). Sorting for the user is not done silently.
- A new optional key on the connection, `read_only: true`, runs `SET
  TRANSACTION READ ONLY` so that every input on that connection sees one point
  in time.
- Not done first: partitioned parallel reads (not one point in time; extra
  load; the driver's own doubts in Q5).

#### D4. Oracle output: how rows reach the table

| Option | All or nothing | Second attempt safe | Table actions | Rejects as a flow | Scratch disk |
|---|---|---|---|---|---|
| A. `sink_batches` callback runs `executemany` during the pass | yes with a rollback hook; the transaction is open for the whole pass | only with that hook | must run before the pass: a failed pass has already truncated | no: a sink has no output | none |
| B. spool with native `sink_ipc`, load in `ready`, commit in `place` | yes: the database is not touched until the pass has succeeded | yes: nothing was done | run at the last moment, after the rows are known to be whole | yes, as a second stage | the rows once |
| C. as B, then direct path into a staging table and one `INSERT ... SELECT` or `MERGE` | yes | yes | yes | harder | twice, plus DDL rights; a direct path load commits (finding 1) |

Recommendation: **B** as the one route. C is an option to add later behind an
explicit key for loads that need it (it needs DDL rights and a second
connection, because both the staging DDL and the direct path load commit).
A is not worth a second code path.

- `write()` returns a `Write` whose `sink` is `frame.sink_ipc(temp,
  lazy=True)` over the declared columns. `ready` opens a savepoint, runs the
  table action, reads the spool one record batch at a time with pyarrow
  (`pa.OSFile`: 91 MB for 2.2 GB in 2.3) and calls `executemany` per batch.
  `place` commits a connection the component owns and does nothing on a shared
  one. A new `abandon` rolls back to the savepoint, or rolls back and closes.
- A subjob that writes files and tables ends in two kinds of step that cannot
  be undone: a commit and a move. Inferred: a commit can fail (a lost
  connection, a constraint checked at commit), and the move of a ready file
  beside its place almost never does. So every database write of the subjob is
  committed first and the files are put in place after, whatever the order of
  the components. Today the engine makes every write ready (runner.py
  L849-859) and then places them in component order (L861-881), and a
  `place` is one that "only the file system may fail" (base.py L620-622): the
  order of the last step is a change to the engine, not to a component. Two
  cases stay open and are said at ERROR with what was and was not done, never
  retried: a move that fails after a commit, and a commit whose answer is lost
  with the connection (Q6, Transaction Guard).
- Before loading, read the table's columns from the dictionary (with binds)
  and check the spool in Polars for what the database would refuse for every
  such row: a missing value for a NOT NULL column, text longer than the
  column, more digits than the column. These failures name the input row and
  cost no round trip. (Hop puts a "Database value validation" in front for the
  same reason.) The dictionary types also say where a `datetime` bind has to
  be cast to DATE in a key comparison, which is what Talend's "Use Timestamp
  for Date type" is about.
- Data actions: `INSERT`: one array insert per batch. `UPDATE` and `DELETE`:
  array DML keyed by the schema's `key` columns, with `arraydmlrowcounts` for
  the counts. `UPDATE_OR_INSERT` and `INSERT_OR_UPDATE`: array UPDATE with row
  counts, then array INSERT of the rows that updated nothing, then UPDATE of
  the rows that insert refused as duplicates: two or three round trips per
  batch instead of two or three per row, and counts of inserted and updated
  rows as Talend reports them. (One `MERGE` per batch is simpler and does not
  split the two counts.) What rows of one batch see of each other is to be
  tried (section 5).
- Table actions: `CLEAR` is `DELETE` inside the transaction: an atomic
  replace. `TRUNCATE`, `TRUNCATE_REUSE_STORAGE`, `CREATE*`, `DROP*` are DDL:
  run as the first thing of `ready`, refused when the connection has work
  pending from earlier subjobs (`transaction_in_progress`), and documented as
  not atomic. `CREATE` types come from the declared schema, because the job
  config does not carry Talend's database type column (4.4).
- Names: `table` and `schema_db` are checked with `is_simple_sql_name` /
  `is_qualified_sql_name` and written unquoted (Talend never quotes;
  `convert_column_table_to_uppercase` is then a no-op for unquoted names).
- Rows the database refuses: with `die_on_error` true the first refusal fails
  the component, the transaction is rolled back, and the message names the
  row. With it false the batch is loaded with `batcherrors=True`, refused rows
  are counted and the first is told in the log, as v2 does for dropped rows
  (D12 has the whole of `die_on_error`). A wired reject flow needs a second
  stage (3.5, seam 5).
- `commit_every`: accepted and ignored; there is one commit. `batch_size` /
  `use_batch_size`: the rows per round trip.
- globalMap: `<id>_NB_LINE`, `_NB_LINE_INSERTED`, `_NB_LINE_UPDATED`,
  `_NB_LINE_DELETED`, `_NB_LINE_REJECTED` (Talend's names; the engine's own
  `_NB_LINE_REJECT` is a different key).
- Refused, with the reason: `use_field_options: true` without `field_options`
  (the converter does not write the table that says which columns are keys),
  `use_hint_options: true` (the hints are not in the config either).

#### D5. Oracle row: one statement, bound

- With no input flow it is an action: the statement runs once. With an input
  flow it runs once per row, as in Talend, but as array DML over the spooled
  rows in `ready`; the rows are handed on unchanged (the main output is the
  input frame, which does not wait for the database).
- The `query` key is declared as text the loader does not touch (`CODE`), and
  the component binds what it finds:
  - `${context.x}` or `context.x` outside quotes becomes a bind variable; a
    whole quoted literal `'${context.x}'` becomes a bind variable; inside a
    longer literal it becomes `'...' || :x || '...'`. A lexer that knows
    quotes and comments is enough; no SQL parser.
  - Where a name is needed (after FROM, JOIN, INTO, UPDATE, TABLE, or before a
    dot), the value is checked as a simple SQL name and written in; anything
    else there fails the component.
  - Java joining (`" + context.x + "`, `(String)globalMap.get("k")`) as the
    converter leaves it (4.4) is read as the same references; any other Java
    refuses the job at load, as Java does elsewhere in v2.
  - `use_preparedstatement` with `set_preparedstatement_parameters`: `?`
    becomes `:1..:n`; a value `rowN.col` binds the column, `context.x` the
    context value, anything else a literal of the stated type.
- One statement per component. DDL: refused when the connection has pending
  work; a PL/SQL block that commits is noticed afterwards through
  `transaction_in_progress` and said at WARNING.
- `use_nb_line`: the affected-row count into `<id>_NB_LINE_INSERTED` /
  `_UPDATED` / `_DELETED`; `<id>_QUERY`: the statement text with bind names,
  never the values.
- `propagate_record_set`: refused. A Java result set in a column has no
  meaning here; a query whose rows are wanted is an input.
- New optional key `statement_timeout` (seconds, to `call_timeout`).

#### D6. Oracle stored procedure

- `sp_name` is checked as a qualified name; the call is a PL/SQL block with
  named binds (`begin :ret := name(:a, :b); end;`).
- With no input flow: one call; OUT values and the return value become one
  output row.
- With an input flow: the block runs through `executemany` per batch, IN
  values from columns, OUT and IN OUT values in `cursor.var(type,
  arraysize=len(batch))`. The output rows hold values only the database knows,
  so the component is a stage of its own: input spooled, calls made, output
  spooled, scan handed on (seam 5).
- `RECORDSET`: with no input flow, the REF CURSOR's rows are the component's
  output rows, fetched in batches. With an input flow it is refused first.
  This departs from Talend, which hands on a result-set object.
- `is_custom` (STRUCT, ARRAY): refused first; thin mode can do objects later.
- `nls_language`, `nls_territory`: values from Talend's closed list, set with
  `ALTER SESSION` on a connection the component owns.

#### D7. Oracle bulk exec

Talend's component loads a file with `sqlldr`. Options: (a) run `sqlldr`: an
Oracle client install on every server, a password on a command line or in a
parameter file, log parsing; (b) read the file with v2's own delimited reader
and load it by D4's route. Recommendation: **(b)**. It is an action when no
flow leads to it (Talend's shape) and a sink when one does (v1's and the
converter's shape).

- `data_action`: `INSERT` (SQL*Loader's meaning: the table has to be empty;
  check and fail otherwise), `APPEND`, `REPLACE` (delete all, in the
  transaction), `TRUNCATE`, `UPDATE`.
- `options` (KEY, VALUE pairs, 4.3): `ROWS` to the batch size, `ERRORS` to the
  number of refused rows allowed, `SKIP`, `LOAD`; `DIRECT=true` asks for
  `direct_path_load`, an explicit opt-in whose loss of the transaction is said
  in the log. Others are refused by name.
- `use_existing_clt_file`, `input_into_table_clause`, `record_format` other
  than `DEFAULT`: refused; a hand-written control file cannot be read here.
- globalMap as Talend: `<id>_NB_LINE_DATA`, `_NB_LINE_BAD`,
  `_NB_LINE_INSERTED`, `_RETURN_CODE`.

#### D8. Commit, rollback, close, and the end of the job

| Situation | Talend (Oracle JDBC) | python-oracledb as it is | Recommended |
|---|---|---|---|
| commit component | commits if the connection is open, else does nothing (TX tOracleCommit/tOracleCommit_main.javajet L21-33); `close` default true | | commits; fails when the connection named is not open, since a commit that does nothing is a job that stores nothing |
| commit standing in a flow (as in `Job_tOracleRow_0.1.json`) | runs for each row: the first row commits and closes | | acts once, when the subjob has succeeded; hands the rows on |
| rollback component | rolls back, closes | | the same |
| close with work pending | the JDBC close commits it (finding 2) | rolls it back | fails the job and rolls back, with a message that names the fix; a key on the close component (`uncommitted: fail`, `commit` or `rollback`, default `fail`) lets a job say which it wants |
| job ends, connection never closed, work pending | the process ends, the database rolls back | the same | rolls back, says so at ERROR, and the job is `failed`: rows a job loaded and did not store are a failure |
| subjob fails on a shared connection | earlier batches stay pending; a later commit stores a part | | this subjob's work is rolled back to its savepoint; earlier subjobs' work stays pending |

Why not Talend's close: a tOracleClose under tPostjob runs after a job that
failed half way, and the JDBC close then commits the half.

#### D9. Secrets and logs

- `password` is declared `secret=True` on all eight components that have it;
  the engine then masks it in the DEBUG config line and in refusals (3.1).
  That is the whole of what the engine shows of a config today.
- A password can also stand inside another key: Talend's `rac_url` and
  `jdbc_url` are whole JDBC URLs, and the converter's own default for
  `jdbc_url` is `jdbc:oracle:thin:USER/MDP@server` (`oracle_connection.py:74`).
  A URL that carries `user/password@` is refused at load, with a reason that
  does not quote it; the credentials belong in `user` and `password`.
- The password is handed to the driver as an argument of its own
  (`oracledb.connect(user=..., password=..., dsn=...)`), never built into a
  text. `mssql-python` and ODBC take a connection string: whether their error
  messages can repeat it is to be tried (section 5, 18). Only if one does is a
  logging filter worth adding that replaces every secret value the run holds,
  wherever it appears (Airflow's way; it costs a pass over every log line).
- Neither `password_<id>` nor the connection object goes into globalMap,
  which the result hands back.
- A password is taken from the context (`${context.x}`), which comes from the
  command line or the caller. A value starting with
  `enc:system.encryption.key.v1:` is Talend's encrypted text and cannot be
  used: refuse it at load with that reason.
- Bind values are never logged; a rejected row's values are shown under the
  existing rule for values from the data (cut, one line).
- Driver messages are made one line (the thin driver adds a "Help:" line).

#### D10. SQL Server connection and input

Recommendation: one small seam with two functions (open a session from a
config; run a statement with its binds and hand back Arrow batches), and
behind it:

1. **`mssql-python` first.** First-party, GA, no system packages, Arrow
   batches, DB-API transactions and bulk copy for the day an MSSQL output is
   wanted. To check before relying on it: glibc 2.28 on the servers, the
   `azure-identity` dependency, the proprietary licence of the driver wheel,
   Kerberos if used, and the type table in section 5.
2. **`arrow-odbc` over the system's ODBC Driver 18 as the other
   implementation**, for sites that standardise on the system driver. Its
   binds are text only; its wheels need an x86-64-v3 CPU.
3. Not pyodbc for v2: rows as Python objects at 30 to 100 GB. Not connectorx:
   no binds, no shared session. Not the ADBC driver: closed source from one
   company's registry.

The input is D3 again: query once, spool, scan; `set_query_timeout` /
`query_timeout_in_seconds` to the driver's query timeout; trims in Polars.
Keys new to v2: `encrypt` (default yes, as Driver 18) and
`trust_server_certificate` (default no), and Talend's JDBC `properties`
translated where they have an ODBC meaning (`encrypt`,
`trustServerCertificate`, `applicationIntent`, `loginTimeout`) and refused by
name otherwise. `driver` (`MSSQL_PROP` or `JTDS`) is a JDBC choice and is
ignored. `active_dir_auth` maps to `Authentication=ActiveDirectoryPassword`.
The application name is set, as Talend sets `appName`. An optional
`isolation: snapshot` for a consistent read where the database allows it.

#### D11. Tests

- v1 is not the answer key (ticket 87). A test runs a job on v2 against a
  container and reads the table back with the plain driver.
- Oracle: `gvenzl/oracle-free:23.26.3-slim-faststart`, native on the Mac's
  arm64, one container per session; a schema or table names of its own per
  test. Under `-n auto` either the file-lock fixture or a run of its own
  without xdist behind a marker (v1 has `-m oracle`).
- SQL Server: `mcr.microsoft.com/mssql/server:2022-latest`, amd64. On the Mac
  it is emulation Microsoft does not support; make the suite opt-in there and
  let an x86-64 host be where it counts.
- Every type in both directions against the real database, with the values
  that hurt: 38 digits, a negative scale, `''`, a DATE with a time, a
  TIMESTAMP WITH TIME ZONE, a CLOB over 32,767 characters, a batch boundary
  inside repeated decimals (#605).
- Flat memory is shown at 5 to 10 GB (Oracle Free stops at 12 GB of data); 30
  to 100 GB needs a real database.

#### D12. `die_on_error`

Facts. In Talend only tOracleOutput and tOracleRow have "Die on error", and
its default is off (TX tOracleOutput/tOracleOutput_java.xml L287-291,
tOracleRow/tOracleRow_java.xml L275-279). The converter writes the key for
those two, false unless the job says otherwise (`oracle_output.py:94`,
`oracle_row.py:183`); v1's bulk exec reads it as well
(`src/v1/engine/components/database/oracle_bulk_exec.py:412`). The engine has
the seam: a component declares the shared key `DIE_ON_ERROR` (default true)
and asks `goes_on_after(fault, with_what)`, which leaves the fault in
`<id>_ERROR_MESSAGE`, warns, and lets the job go on
(`src/v2/components/base.py` L46-50, L403-418); the rule is "Where the job
config itself carries `die_on_error` and it is off, the job goes on with a
warning" (docs/v2/own-rule/README.md, under "What they share").

Recommended meaning of off, component by component:

| Component | The whole component cannot do its work (no session, no table, a statement the database refuses) | A row the database refuses |
|---|---|---|
| Oracle output | its work in this subjob is rolled back; `<id>_ERROR_MESSAGE`; one warning; the job goes on with nothing loaded | the row is left out and the others are loaded; counted in `<id>_NB_LINE_REJECTED` (Talend's name) and in the engine's `<id>_NB_LINE_REJECT`, with `<id>_NB_LINE_OK` lowered to match; the warning and `<id>_ERROR_MESSAGE` name the first one and say how many |
| Oracle row | rolled back; `<id>_ERROR_MESSAGE`; one warning; the job goes on | with an input flow: as the output, row by row |
| Oracle bulk exec | as the output. The converter does not write the key, so it is on unless a job config says otherwise | as the output, up to the `ERRORS` option |
| the other eight | they have no `die_on_error` in Talend, in the converter or in v1: what they cannot do fails the job | |

What follows and should be said on the components' pages: Talend's default is
off and the converter writes it, so nearly every converted output and row
arrives saying "do not die". In Talend such a job prints each refused row's
message to standard error, or hands the row to a reject flow, and loads the
rest (TX tOracleOutput/tOracleOutput_main.javajet L503-532). Here the same job
loads the rest too, and says so where an operator looks: one warning on stderr
with the count and the first row's place, and the counts in globalMap and in
the summary. The engine writes a sink's counts from the rows it handed over,
with no rejects (`src/v2/engine/runner.py` L870-875); a database output
corrects them in `Write.finish`, which runs right after (L876-877). "All or
nothing" still holds for what is loaded: nothing is committed unless the
subjob succeeded, and the rows left out are the job's own stated choice.

### 3.4 Where this departs from Talend, and why it is better for long use

| Talend | Recommended | Why |
|---|---|---|
| commits every 10,000 rows with its own connection | one commit, when the subjob has succeeded | a failed run leaves nothing half loaded; a rerun needs no clean-up |
| closing a connection commits | closing with pending work fails and rolls back, unless the job says otherwise | no accidental commit of a failed job's half |
| values pasted into the SQL text | bind variables; names checked | no injection through context values; one cursor in the shared pool; types kept |
| rows fetched and loaded one by one | Arrow batches | speed and memory at 30 to 100 GB |
| upsert by a query per row | array update, then array insert | the same end state and counts in two or three round trips per batch |
| table action first, then the rows | rows made whole on disk first, table action at the last moment | a failed transformation never empties a table |
| `sqlldr` with the password on the command line | the engine's reader and loader | no client install, no password in the process list, one behaviour for types and rejects |
| `password_<id>` and the connection object in globalMap | neither | globalMap is printed and returned |
| the result set as a Java object in a column | refused; a REF CURSOR's rows as rows | a value that means something outside a JVM |
| a statement per row, re-evaluated as Java | one statement, bound per row | the same rows touched, parsed once |
| no session tag for Oracle | module, action, client identifier | a DBA can see which job runs a statement |

### 3.5 What the engine has to learn (seams)

1. **Connections in the run**: a registry on `RunContext` (open, get, commit,
   rollback, close, a lock each, a savepoint per subjob), closed when the job
   ends and not in the per-subjob `cleanup()`.
2. **Undo for a write**: `Write.abandon`, called by `_discard`; a `Write`
   whose target is not a file path; and, in `_place`, the commits of a subjob
   ahead of its file moves (D4).
3. **Secrets**: the mark on a key exists since `32383de1` (3.1). Left to do:
   refuse credentials inside a URL key, and decide on a value-masking log
   filter once the drivers' messages have been looked at (D9).
4. **Statement text**: a key type that is not context-resolved, and one helper
   that turns references into binds.
5. **A stage boundary on disk**: what `needs_rows()` does in memory, done
   through a spool: the engine runs the pass up to the component into a file,
   the component works, and hands back scans. Needed for an output whose
   rejects feed a flow and for a procedure that returns values.
6. **Row numbers into a sink** that asks for them, to name the row the
   database refused.
7. `oracle_config` / `mssql_config` become supported job keys
   (`thick_mode`, the SQL Server driver choice).
8. A new folder `src/v2/components/database/`, an `oracle` and an `mssql`
   extra, and the README's exception for sources read in Python extended to
   database sources.

### 3.6 The eleven components at a glance

| Component | Kind | Does | First version refuses |
|---|---|---|---|
| Oracle connection | Action | opens and registers a session; tags it | `ORACLE_WALLET` without thick mode; unknown `properties` |
| Oracle input | Source | query once with binds, spool, scan | types outside the mapping; Java other than context joining |
| Oracle output | Sink | spool, check against the dictionary, array DML in `ready`, commit in `place` | a wired reject flow until seam 5; `use_field_options` without `field_options`; `use_hint_options` |
| Oracle row | Action, or a pass-through with an input | one bound statement, once or per row | `propagate_record_set`; DDL on pending work |
| Oracle stored procedure | Action, or a stage with an input | bound call; OUT values as columns | custom types; `RECORDSET` with an input flow |
| Oracle bulk exec | Action, or Sink with an input | file or flow into a table by the output's route | hand-written control files; `sqlldr` options with no meaning here |
| Oracle commit | Action, also in a flow | commit, close by default | a connection that is not open |
| Oracle rollback | Action, also in a flow | rollback, close by default | the same |
| Oracle close | Action | close; pending work fails by default | |
| MSSQL connection | Action | opens and registers a session; application name | unknown `properties`; `use_shared_connection` across jobs |
| MSSQL input | Source | as the Oracle input, through the driver seam | types outside the mapping |

### 3.7 Could not establish

- Which authentication and encryption the target Oracle and SQL Server
  databases require (NNE, TCPS, Kerberos, wallets), which decides thin or
  thick; their versions; the servers' RHEL release (glibc) and CPUs.
- Whether the loading accounts may create tables (staging) and how much undo a
  100 GB single transaction is allowed.
- What production job configs look like for passwords and for queries built
  from context variables: the converter in this repo cannot produce them
  (4.1), so they come from a converter that is not here.
- Everything in section 5.

---

## 4. Compatibility facts

### 4.1 The state of the converter (Observed)

Run in memory on 2026-10-12 (`TalendToV1Converter().convert_file(...)`, nothing
written), the converter turns `tOracleConnection`, `tOracleInput`,
`tOracleOutput` and `tOracleRow` of the three sample `.item` files into
`_unsupported` placeholders:

```
AttributeError: 'OracleConnectionConverter' object has no attribute '_extract_password'
```

- Six Oracle converters and `mssql_input.py` call
  `self._extract_password(self._get_str(node, "PASS", ""), log_id=node.component_id)`
  (`oracle_connection.py:73`, `oracle_input.py:136`, `oracle_output.py:81`,
  `oracle_row.py:171`, `oracle_sp.py:128`, `oracle_bulk_exec.py:112`,
  `mssql_input.py:59`). `ComponentConverter` has no such method
  (`src/converters/talend_to_v1/components/base.py`, 254 lines).
  `mssql_connection.py:54` calls the same with `log_id=` while its own static
  method takes one argument (`:105`) and names `_ENCRYPTED_PREFIX`, which the
  commit "db components converter sync" (`66e90fc7`, 2026-06-23) removed.
  `main` and `origin/main` are the same.
- The placeholder (`converter.py:202-214`) keeps `id` and `type`, has
  `"config": {}`, `"schema": {}` and `"_unsupported": true`. v2's component
  keys do not know `_unsupported` (`src/v2/job/loader.py:134-146`): once the
  type exists in v2 such a job is refused for that key, which is right, and
  the reason should say that the converter failed.
- Only `tOracleCommit`, `tOracleRollback`, `tOracleClose` convert today.
- So the keys below are what the converter source says it writes, and the
  committed samples (`tests/talend_xml_samples/converted_jsons/`, committed
  2026-05-11) are what an older converter wrote. Both shapes exist; v2 has to
  load both.

### 4.2 Keys shared by the components (the connection block)

Lines are of the converter module of each component, under
`src/converters/talend_to_v1/components/database/`. C = `oracle_connection.py`,
I = `oracle_input.py`, O = `oracle_output.py`, R = `oracle_row.py`, S =
`oracle_sp.py`, B = `oracle_bulk_exec.py`, MC = `mssql_connection.py`, MI =
`mssql_input.py`. Talaxie lines are of `tOracleConnection_java.xml` unless
said. Every converter also writes `tstatcatcher_stats` and `label` last
(Talend Studio adds them to every component; they are not in the component's
definition); v2 already accepts both on every component.

| Key (default the converter writes) | Written at | Talend parameter, label, meaning |
|---|---|---|
| `use_existing_connection` (false) | I:121 O:64 R:160 S:118 B:98 MI:51 | `USE_EXISTING_CONNECTION` "Use an existing connection": take the session of a connection component instead of opening one |
| `connection` ("") | I:122 O:65 R:161 S:119 B:99 MI:52, and commit:35 rollback:38 close:34 | `CONNECTION` "Component List": the id of the connection component (`tDBConnection_1` in the samples) |
| `connection_type` ("ORACLE_SID") | C:60 I:125 O:66 R:162 S:120 B:102 | `CONNECTION_TYPE` (L48): `ORACLE_SID` "Oracle SID", `ORACLE_SERVICE_NAME` "Oracle Service Name", `ORACLE_OCI` "Oracle OCI", `ORACLE_RAC` "ORACLE Custom" (the input and the output spell it "Oracle Custom"), `ORACLE_WALLET` "WALLET". Decides how the JDBC URL is built (tOracleConnection_begin.javajet L34-56) |
| `db_version` ("ORACLE_18") | C:61 I:126 O:67 R:163 S:121 B:103 | `DB_VERSION` (L61): `ORACLE_18`, `ORACLE_12`, `ORACLE_11`: which JDBC jar Talend loads |
| `rac_url` ("") | C:62 I:127 R:164 | `RAC_URL` "URL" (L70), shown for `ORACLE_RAC`: a whole JDBC URL, used as it is |
| `use_tns_file` (false), `tns_file` ("") | C:63, C:64 | `USE_TNS_FILE` "Use tns file", `TNS_FILE` "TNS File" (L79, L87) |
| `host` ("") | C:67 I:130 O:68 R:165 S:122 B:106 MC:49 MI:54 | `HOST` "Host" |
| `port` ("1521"; "1433" for MSSQL), a string | C:68 I:131 O:69 R:166 S:123 B:107 MC:50 MI:55 | `PORT` "Port" |
| `dbname` ("") | C:69 I:132 O:70 R:167 S:124 B:108 MC:52 MI:57 | `DBNAME` "Database": the SID for `ORACLE_SID`, the service name for `ORACLE_SERVICE_NAME`; the database for MSSQL |
| `local_service_name` ("") | C:70 I:133 R:168 S:125 B:109 | `LOCAL_SERVICE_NAME` "Local Service Name" (L146), shown for `ORACLE_OCI`: a TNS alias |
| `schema_db` ("") | C:71 I:134 R:169 S:126 B:110 from `SCHEMA_DB`; O:76 from `TABLESCHEMA`; MC:51 from `SCHEMA_DB`; MI:56 from `DB_SCHEMA` | "Schema" / "Oracle schema": the schema that qualifies the table; put in globalMap as `dbschema_<id>` |
| `user` ("") | C:72 I:135 O:78 R:170 S:127 B:111 MC:53 MI:58 | `USER` "Username" |
| `password` ("") | C:73 I:136 O:81 R:171 S:128 B:112 MC:54 MI:59 | `PASS` "Password". In the `.item` it is `enc:system.encryption.key.v1:...`; what the missing `_extract_password` returns is not known (4.1) |
| `jdbc_url` ("jdbc:oracle:thin:USER/MDP@server" in C; "" in I) | C:74 I:137 | `JDBC_URL` "URL" (L342), shown for `ORACLE_WALLET`: the URL a wallet connection uses |
| `encoding` ("ISO-8859-15"; "UTF8" in B) | C:77 I:151 R:194 S:145 B:150 MC:55 MI:69 | `ENCODING` "Encoding"; hidden in most components; in B the character set of the SQL*Loader control file (`UTF8`, `WE8ISO8859P15`, ...) |
| `properties` (""; "noDatetimeStringSync=true" in MI) | C:78 I:148 R:186 S:144 B:121 MC:56 MI:67 | `PROPERTIES` "Additional JDBC Parameters": `name=value&&name=value` for Oracle, `;name=value` appended to the URL for MSSQL |
| `use_shared_connection` (false), `shared_connection_name` ("") | C:81-82 MC:59-60 | "Use or register a shared DB Connection", "Shared DB Connection Name" (L293, L303): one JDBC connection shared between a parent job and its child jobs by name |
| `specify_datasource_alias` (false), `datasource_alias` ("") | C:85-86 I:144-145 R:179-180 S:140-141 MC:63-64 MI:63-64 | "Specify a data source alias", "Data source alias": "This option only applies when deploying and running in the Talaxie Runtime" (the note at L319) |
| `use_ssl`, `ssl_trustserver_truststore`, `need_client_auth`, `ssl_keystore`, `disable_cbc_protection` (false, "", false, "", true) | C:89-93 | "Use SSL", "TrustStore file", "Need Client authentication", "KeyStore file", "Disable CBC protection" (L188-261): TLS for `ORACLE_RAC` URLs with Java key stores. The two store passwords exist in Talend and are not written by the converter |
| `auto_commit` (false) | C:96 MC:68 | `AUTO_COMMIT` "Auto Commit" (L353): `conn.setAutoCommit(...)` |
| `support_nls` (false) | C:97 I:157 O:103 R:196 S:148 B:155 | `SUPPORT_NLS` "Support NLS": load `orai18n.jar` |

v1's engine reads of these: `connection_type`, `host`, `port`, `dbname`,
`local_service_name` (connection only), `rac_url`, `user`, `password`,
`schema_db`, `auto_commit`, `encoding` (to log that it is not honoured), and
warns on `use_tns_file`, `support_nls`, `use_ssl`
(`src/v1/engine/components/database/oracle_connection.py:112-266`,
`src/v1/engine/oracle_connection_manager.py:165-237`).

### 4.3 Keys of each component

**Oracle input** (`oracle_input.py`; Talaxie `tOracleInput_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads |
|---|---|---|---|
| `table` ("") | 140 | `TABLE` "Table Name" (L106): only for Talend's query builder | no |
| `query` ("select id, name from employee") | 141 | `QUERY` "Query" (L116): the statement, a Java string expression | `oracle_input.py:102` |
| `is_convert_xmltype` (false) | 149 | `IS_CONVERT_XMLTYPE` "Convert XMLType To Java Type." (L174) | warns, :85 |
| `convert_xmltype` ([]) | 150 | `CONVERT_XMLTYPE` (L177): rows of `REFCOL`, `CONVETTYPE`. The converter looks for `SCHEMA_COLUMN` and `XML_COLUMN` (:47), which Talend does not write, so it is always `[]` | no |
| `use_cursor` (false), `cursor_size` (1000) | 152, 153 | `USE_CURSOR` "Use fetch size", `CURSOR_SIZE` "Fetch size" (L193, L196): `stmt.setFetchSize(n)` | :105, :108 |
| `trim_all_column` (false) | 154 | "Trim all the String/Char columns" (L200) | :174 |
| `trim_column` ([]) | 155 | `TRIM_COLUMN` "Trim column" (L203): per column a `TRIM` check. Shape written: a flat list with one object per cell, `[{"schema_column": "ID"}, {"trim": "false"}, ...]` (`Job_tOracleConnection_0.1.json:87-105`). v1 trims every column named, whatever `trim` says (`oracle_input.py:190-200`) | :192 |
| `no_null_values` (false) | 156 | `NO_NULL_VALUES` "No null values" (L209); Talend's own source asks "any difference when the value of the parameter is true and false?" (tOracleInput_begin.javajet L278) | :204 |

Schema: `{"input": [], "output": [columns]}` (:178). Talend maps result
columns to schema columns by position. globalMap in Talend: `<id>_NB_LINE`,
`<id>_QUERY`.

**Oracle output** (`oracle_output.py`; Talaxie `tOracleOutput_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads (`oracle_output.py`) |
|---|---|---|---|
| `table` ("") | 84 | `TABLE` "Table" (L189) | :231, :278 |
| `table_action` ("NONE") | 85 | `TABLE_ACTION` "Action on table" (L198): the eight values of Q4.4 | :235, :1005 |
| `data_action` ("INSERT") | 86 | `DATA_ACTION` "Action on data" (L223): the five values of Q4.4 | :241, :977 |
| `commit_every` (10000) | 89 | `COMMIT_EVERY` "Commit every" (L362), shown without an existing connection | :993 |
| `use_batch_size` (true), `batch_size` (10000) | 90, 91 | "Use Batch Size", "Batch Size" (L477, L498): JDBC batches; offered for insert, update, delete without an existing connection. With one, Talend has `USE_BATCH_AND_USE_CONN` (L487, default false), which the converter does not write | :996, :997 |
| `use_field_options` (false) | 92 | "Use field options" (L394). The table itself, `FIELD_OPTIONS` (L402: `UPDATE_KEY`, `DELETE_KEY`, `UPDATABLE`, `INSERTABLE` per column), is not written | :470-496 read `field_options` |
| `use_hint_options` (false) | 93 | "Use Hint Options" (L419); `HINT_OPTIONS` (L427) is not written | no |
| `die_on_error` (false) | 94 | "Die on error" (L287) | :1139 |
| `enable_debug_mode` (false) | 95 | "Debug query mode" (L469): puts the statement with its values in `<id>_QUERY` | no |
| `convert_column_table_to_uppercase` (false) | 96 | "Convert columns and table to uppercase" (L453) | no |
| `use_timestamp_for_date_type` (true) | 99 | "Use Timestamp for Date type" (L515): bind dates as `Timestamp` | :305, :868 |
| `trim_char` (true) | 102 | "Trim when the updating or deleting key is of char DB type" (L522) | no |

- The committed sample has `table_schema`, not `schema_db`
  (`Job_tOracleOutput_0.1.json:246`), and no `rac_url`,
  `local_service_name`, `properties`. v1 reads `schema_db` or `dbschema`
  (`oracle_output.py:279`), never `table_schema`, and ignores the schema with
  an existing connection (:277-279). Three spellings to accept: `schema_db`,
  `table_schema`, `dbschema`.
- Not written at all though Talend has them: `ADD_COLS`,
  `USE_ALTERNATE_SCHEMA` / `ALTERNATE_SCHEMA`, `SUPPORT_NULL_WHERE`,
  `CONTAIN_BLOB_FROM_OTHER_DB`.
- Schema: `{"input": [columns], "output": []}` (:129); the column names are
  the table's column names; `key: true` marks the update and delete key. The
  database type of a column is not in the job config (`SchemaColumn`,
  `base.py:13-21`).
- globalMap in Talend (L548-554): `NB_LINE`, `NB_LINE_UPDATED`,
  `NB_LINE_INSERTED`, `NB_LINE_DELETED`, `NB_LINE_REJECTED`, and `QUERY` in
  debug mode. Reject columns: `errorCode` (the SQLState) and `errorMessage`.

**Oracle row** (`oracle_row.py`; Talaxie `tOracleRow_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads (`oracle_row.py`) |
|---|---|---|---|
| `table` ("") | 174 | "Table Name" (L202): for the query builder | no |
| `query` ("select id, name from employee") | 175 | `QUERY` (L219): a Java string expression, evaluated for each row | :371 |
| `use_nb_line` ("NONE") | 176 | `USE_NB_LINE` "Use NB_LINE_" (L227): `NONE`, `NB_LINE_INSERTED`, `NB_LINE_UPDATED`, `NB_LINE_DELETED`: which counter takes the update count; "Only used if the query is an insert, an update or a delete" (the note at L242) | :301, :372 |
| `die_on_error` (false) | 183 | "Die on error" (L275); off: the row goes to REJECT with `errorCode`, `errorMessage` | base class |
| `propagate_record_set` (false), `record_set_column` ("") | 187, 188 | "Propagate QUERY's recordset", "use column" (L302, L310): put the `ResultSet` object into that column | :352 refuses |
| `use_preparedstatement` (false) | 189 | "Use PreparedStatement" (L317) | :308, :373 |
| `set_preparedstatement_parameters` ([]) | 190 | L325: rows of `PARAMETER_INDEX`, `PARAMETER_TYPE`, `PARAMETER_VALUE`; written as `[{"parameter_index": "1", "parameter_type": "String", "parameter_value": "..."}]`; types `BigDecimal`, `Blob`, `Boolean`, `Byte`, `Bytes`, `Clob`, `Date`, `Double`, `Float`, `Int`, `Long`, `Object`, `Short`, `String`, `Time`, `Null`; the value is a Java expression in Talend. Rows with a bad index are dropped by the converter with a warning (:111-141) | :309, :378; also takes `Integer`, `BigInteger`, `Timestamp` |
| `commit_every` (10000) | 195 | "Commit every" (L369), without an existing connection | no; v1 commits after the statement (:414) |

Schema: input and output are both the node's schema (:222). A flow may lead
to and from it (`FLOW MAX_INPUT="1" MAX_OUTPUT="1"`). globalMap in Talend:
`<id>_QUERY`, `NB_LINE_UPDATED`, `NB_LINE_INSERTED`, `NB_LINE_DELETED`,
`<id>_ERROR_MESSAGE`. v1 runs the statement once, not per row.

**Oracle stored procedure** (`oracle_sp.py`; Talaxie `tOracleSP_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads (`oracle_sp.py`) |
|---|---|---|---|
| `sp_name` ("myfunction") | 131 | `SP_NAME` "SP Name" (L188) | :116 |
| `is_function` (false) | 132 | "Is function" (L197) | :195 |
| `return_column` ("") | 133 | `RETURN` "Return result in" (L205): the column that takes the function's value | :268 |
| `return_bdtype` ("AUTOMAPPING") | 134 | `RETURN_BDTYPE` "DBType" (L214): `AUTOMAPPING`, `CLOB`, `BLOB`, `DECIMAL`, `NUMERIC`, `XMLTYPE`, `DATE`, `TIMESTAMP`, `TIMESTAMP_WITH_TIMEZONE` | :257 |
| `sp_args` ([]) | 137 | `SP_ARGS` "Parameters" (L233); written as `[{"column", "type", "dbtype", "is_custom", "custom_type", "custom_name"}]` from `COLUMN`, `TYPE` (`IN`, `OUT`, `INOUT`, `RECORDSET`), `DBTYPE` (as above), `ISCUSTOME`, `CUSTOME_TYPE` (`STRUCT`, `ARRAY`), `CUSTOMENAME`. In order of the procedure's arguments | :120, :150; refuses custom types and `RECORDSET` |
| `nls_language` ("NONE"), `nls_territory` ("NONE") | 146, 147 | L333, L399: closed lists; `ALTER SESSION SET NLS_LANGUAGE=...` | no |

No `rac_url` and no `die_on_error` (the converter's own note, :34-37). Schema:
input and output are the node's schema (:169). v1 calls once per row and
commits after all calls (`oracle_sp.py:175`).

**Oracle bulk exec** (`oracle_bulk_exec.py`; Talaxie `tOracleBulkExec_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads (`oracle_bulk_exec.py`) |
|---|---|---|---|
| `table` ("") | 115 | "Table" (L176) | :84 |
| `table_action` ("NONE") | 116 | L185: seven values, no `TRUNCATE_REUSE_STORAGE` | :140; refuses all but `NONE`, `TRUNCATE` |
| `data` ("") | 117 | `DATA` "Data file name" (L209): the file to load | :162 |
| `data_action` ("INSERT") | 118 | L219: `INSERT`, `UPDATE`, `APPEND`, `REPLACE`, `TRUNCATE` | :88; no `UPDATE` |
| `advanced_separator` (false), `thousands_separator` (","), `decimal_separator` (".") | 122-124 | "Advanced separator (for numbers)" and its two characters (L268-278) | no |
| `use_existing_clt_file` (false), `clt_file` ("") | 127, 128 | "Use existing control file", ".ctl file name" (L285, L293) | :211, :212 |
| `record_format` ("DEFAULT") | 131 | "Record format" (L302): `DEFAULT`, `STREAM`, `FIXED`, `VARIABLE` | no |
| `input_into_table_clause` (false) | 132 | "Specify .ctl file's INTO TABLE clause manually" (L344); the clause itself is not written | no |
| `fields_terminator` ("OTHER"), `terminator_value` (";") | 133, 134 | "Field terminated by" (L365): `NONE`, `WHITESPACE`, `EOF`, `OTHER`; "Field terminator" (L379) | :195, :197; v1 expects `TAB`, `COMMA` and others that Talend does not have |
| `use_fields_enclosure` (false) | 135 | "Use fields enclosure" (L389); the two enclosure characters (L398, L407, default `"`) are not written | :176 |
| `use_date_pattern` (false) | 136 | "Use schema's Date Pattern to load Date field" (L416) | :262 |
| `preserve_blanks` (false), `trailing_nullcols` (false) | 137, 138 | "Preserve blanks", "Trailing null columns" (L443, L452) | :249, :251 |
| `options` ([]) | 141 | `OPTIONS` "Load options" (L461): rows of `KEY` and `VALUE`; keys `BINDSIZE`, `COLUMNARRAYROWS`, `DIRECT`, `ERRORS`, `LOAD`, `MULTITHREADING`, `PARALLEL`, `READSIZE`, `RESUMABLE`, `RESUMABLE_NAME`, `RESUMABLE_TIMEOUT`, `ROWS`, `SILENT`, `SKIP`, `SKIP_INDEX_MAINTENANCE`, `SKIP_UNUSABLE_INDEXES`, `STREAMSIZE`. Written as one flat list of strings, key then value (:61-77) | :325 |
| `nls_language`, `nls_date_language`, `nls_territory` ("DEFAULT"), `set_nls_territory` (true) | 144-147 | L495-638: the environment `sqlldr` runs in | :356, :357 |
| `output` ("OUTPUT_TO_CONSOLE") | 151 | "Output" (L762): `OUTPUT_TO_CONSOLE` "to console", `RETRIEVE_OUTPUT` "to global variable" (`<id>_OUTPUT`) | :323 |
| `convert_column_table_to_uppercase` (false) | 152 | L770 | :263 |

The converter writes it as an output with an input schema (:177); Talend's
component takes no flow. globalMap in Talend (L792-795): `NB_LINE_DATA`,
`NB_LINE_BAD`, `NB_LINE_INSERTED`, `RETURN_CODE`.

**Oracle commit, rollback, close** (`oracle_commit.py`, `oracle_rollback.py`,
`oracle_close.py`)

| Key (default) | Line | Talend parameter and meaning | v1 reads |
|---|---|---|---|
| `connection` ("") | commit:35 rollback:38 close:34 | `CONNECTION` (xml L38; close L37) | `oracle_commit.py:55`, `oracle_rollback.py:54`, `oracle_close.py:51` |
| `close` (true) | commit:36 rollback:39 | `CLOSE` "Close Connection" (L45) | `oracle_commit.py:79`, `oracle_rollback.py:78` |

Commit and rollback may stand in a flow (`FLOW MAX_INPUT="1"
MAX_OUTPUT="1"`); the committed sample has one (`Job_tOracleRow_0.1.json`:
flow `row1` from `tDBRow_1` to `tDBCommit_1`, and `"inputs": {"row1": []}`
under the commit's schema, line 118). Close takes no flow. Talend does nothing
when the connection is missing or closed.

**MSSQL connection** (`mssql_connection.py`; Talaxie `tMSSqlConnection_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads |
|---|---|---|---|
| `driver` ("MSSQL_PROP") | 48 | `DRIVER` "JDBC Provider" (L48): `JTDS` "Open source JTDS", `MSSQL_PROP` "Microsoft" | no |
| `active_dir_auth` (false) | 67 | "Authenticate using Azure Active Directory" (L192): adds `encrypt=true;trustServerCertificate=false;hostNameInCertificate=*.database.windows.net;Authentication=ActiveDirectoryPassword` | manager :153 |
| `share_identity_setting` (false) | 69 | "Share identity insert in multi table" (L198) | no |

and the shared keys of 4.2. v1 also reads `odbc_driver`
(`src/v1/engine/mssql_connection_manager.py:143`), which the converter does
not write. globalMap in Talend: `conn_<id>`, `dbschema_<id>`, `db_<id>`,
`shareIdentitySetting_<id>`.

**MSSQL input** (`mssql_input.py`; Talaxie `tMSSqlInput_java.xml`)

| Key (default) | Line | Talend parameter and meaning | v1 reads (`mssql_input.py`) |
|---|---|---|---|
| `driver` ("MSSQL_PROP") | 53 | as above (L75) | no |
| `query` ("select id, name from employee") | 60 | `QUERY` (L181) | :91 |
| `active_dir_auth` (false) | 68 | L236 | manager |
| `trim_all_column` (false), `trim_column` ([]) | 70, 71 | L250, L254; the same flat shape as the Oracle input's | :154, :167 |
| `set_query_timeout` (false), `query_timeout_in_seconds` (30) | 72, 73 | "Set Query Timeout", "Timeout (seconds)" (L261, L269) | :87, :89 |

Talend reads `datetimeoffset` as text (tMSSqlInput_begin.javajet L117).

### 4.4 Values and shapes that matter

- **Component types.** The converter writes `tOracleConnection`,
  `tOracleInput`, `tOracleOutput`, `tOracleRow`, `tOracleSP`,
  `tOracleBulkExec`, `tOracleCommit`, `tOracleRollback`, `tOracleClose`,
  `tMSSqlConnection`, `tMSSqlInput`; `tDBConnection` converts to
  `tOracleConnection` (`oracle_connection.py:45`). v1 also registers
  `OracleConnection` ... `MSSqlInput`, and `tDBConnection`
  (`src/v1/engine/components/database/*.py`).
- **Ids.** Talend 8 names the instances `tDBConnection_1`, `tDBInput_1`,
  `tDBOutput_1`, `tDBRow_1`, `tDBCommit_1`; `connection` holds such an id.
- **The query is Java text.** `QUERY` is a Java string expression. The parser
  strips one pair of outer quotes (`xml_parser.py:352-360`) and nothing else:
  `"select * from " + context.t` stays as it is with its quotes, and
  `"... where d = '" + context.d + "'"` becomes
  `... where d = '" + context.d + "'`. No `{{java}}` mark is added, so v2's
  loader does not refuse it, and `RunContext.resolve` would paste the value
  into the middle of that text. No test in the repo has a context variable in
  SQL. How real job configs carry such queries is unconfirmed (3.7).
- **The schema has no database types.** A column has `name`, `type` (`str`,
  `int`, `float`, `bool`, `datetime`, `date`, `Decimal`), `nullable`, `key`,
  `length`, `precision`, `date_pattern` (`base.py:172-196`). In the samples
  `ID` is `Decimal`, length 20, precision 0.
- **Job-level keys.** v1 reads `oracle_config.enabled`,
  `oracle_config.thick_mode` and `mssql_config.enabled`
  (`src/v1/engine/engine.py:84-119`).
- **Triggers in the samples.** `OnSubjobOk` from the connection to the first
  component of the next subjob, `OnComponentOk` from the output to the commit
  (`Job_tOracleOutput_0.1.json:344`).
- **What v1 does that a job may lean on.** It reads a whole result with
  `fetchall()` (`oracle_input.py:111`, `mssql_input.py:95`); commits right
  after a table action and every `commit_every` rows
  (`oracle_output.py:1008, 1096, 1102`); passes `rac_url` to the driver
  unchanged (`oracle_connection.py:206-215`); closes every connection when
  the job ends without committing (`engine.py:310-320`).

### 4.5 globalMap entries of Talend's connection component

`conn_<id>` (the JDBC connection), `connectionType_<id>`, `driverClass_<id>`,
`dbschema_<id>`, `username_<id>`, `password_<id>`, and `host_<id>`,
`port_<id>`, `dbname_<id>` or `localServiceName_<id>` or `rac_url_<id>` (TX
tOracleConnection/tOracleConnection_begin.javajet L57, L98, L164-174,
L191-200; templates/DB/AbstractDBConnection.javajet L38, L66). v1 writes
`connectionType_`, `dbschema_`, `username_` only.

---

## 5. To verify by experiment

Nothing below could be run here: no driver is installed and no container was
started. Each line is a question a short script answers.

**python-oracledb 26.0.1, thin, against `gvenzl/oracle-free:23.26.3-slim-faststart`**

1. `fetch_df_batches` with a `pyarrow.schema` as `requested_schema`, for
   NUMBER(20), NUMBER(10,2), NUMBER without precision, NUMBER(1) asked as
   boolean, FLOAT, BINARY_DOUBLE, DATE with a time asked as timestamp and as
   date32, TIMESTAMP(6) and (9), TIMESTAMP WITH TIME ZONE (which instant comes
   back), CHAR (padding), VARCHAR2 holding `''`, CLOB over 32,767 characters,
   RAW, ROWID, a value of more than 38 digits. Is a `pl.Schema` accepted?
2. The same query through `cursor.fetchmany`: equal values? (the fallback of
   D1)
3. A batch boundary inside repeated decimals (#605) and DATE as date32 (#606)
   on 26.0.1.
4. `executemany` with a Polars frame and with `frame.to_arrow()`:
   `batcherrors=True` with `batch_size` (what an offset counts from),
   `arraydmlrowcounts`, and how `setinputsizes` meets Arrow input.
5. Arrow binds: timestamp[us] into a DATE column (is the fraction dropped or
   rounded), a TIMESTAMP bind against an indexed DATE key (is the index
   used), decimal128 too wide for NUMBER(p,s) (the error), a long string into
   VARCHAR2 and into CLOB, boolean into NUMBER(1), `''` into NOT NULL.
6. Array UPDATE, INSERT and MERGE: does a row of a batch see the rows before
   it in the same batch (a new key twice in one batch)?
7. `direct_path_load`: does it commit DML pending on the same connection;
   duplicate keys under a primary key; a table with a foreign key, a trigger,
   a check constraint; what stays when a later batch fails; rows per second
   against `executemany` at 10 million rows.
8. `SAVEPOINT` and `ROLLBACK TO` around array DML with `batcherrors`;
   `transaction_in_progress` before and after DDL, and after the sample's
   `EXECUTE IMMEDIATE 'CREATE TABLE ...'` block.
9. Two threads on one connection at once: wait, or error?
10. `call_timeout` on a long fetch and a long DML: the error, and whether the
    connection lives; `cancel()` from another thread.
11. `close()` with DML pending: rolled back.
12. Plain SQL ending in `;`; two statements in one text.
13. REF CURSOR from a procedure fetched in batches; `executemany` of a PL/SQL
    block with OUT binds; implicit results.
14. Rows per second and peak memory of `fetch_df_batches` into a Parquet
    spool for 10 million rows of 20 columns, for sizes 1,000 to 100,000.
15. Thin mode against a listener that requires Native Network Encryption (the
    error text), and over TCPS.

**Polars**

16. Peak anonymous memory of `scan_parquet` and of `scan_ipc(memory_map=True)`
    over a 30 GB spool on RHEL; `sink_ipc` and `sink_parquet` throughput
    there.
17. Every observation of 2.3 again on Polars 2.0.0 (released 2026-10-06; the
    repo pins `<2.0`), above all the zero-column projection ("Update behavior
    of DataFrame/LazyFrame functions on 0-width input", #29099) and
    `sink_batches`.

**SQL Server**

18. `mssql-python` 1.15.0 on the servers' RHEL and on the Mac: install, connect
    with SQL and Kerberos authentication, `arrow_reader` for `datetime`
    (3 ms steps), `datetime2(7)`, `datetimeoffset`, `money`,
    `uniqueidentifier`, `bit`, `decimal(38,10)`, `varchar(max)`, `time`;
    query timeout; memory for a 10 million row read. Does the message of a
    failed connect (wrong password, wrong host, bad certificate) or of a
    failed statement repeat the connection string or the password?
19. The same reads, and the same question about messages, with `arrow-odbc`
    over ODBC Driver 18; are the values equal?
20. `mcr.microsoft.com/mssql/server:2022-latest` under emulation on the Mac:
    does it start, how long, is it stable for a test session? `Encrypt`
    defaults against the container's self-signed certificate.

**Containers and the repo**

21. Start-up time of the `-faststart` and plain Oracle images on the Mac; a
    session fixture under `-n auto` with the file lock.
22. v1's tests on oracledb 26.x, if the pin is raised for the whole repo.
23. What `_extract_password(raw, log_id=...)` is meant to return, and one real
    converted production job with a password and a query built from context
    variables.

---

## 6. Sources

python-oracledb (docs at commit c92c8420, 2026-10-07; code at v26.0.1)

- Release notes: https://github.com/oracle/python-oracledb/blob/c92c8420874157ce169b28b60b7f139a73f59ee2/doc/src/release_notes.rst
- User guide (same commit, `doc/src/user_guide/`): dataframes.rst,
  batch_statement.rst, bind.rst, plsql_execution.rst, txn_management.rst,
  tuning.rst, sql_execution.rst, tracing.rst, initialization.rst,
  installation.rst, appendix_a.rst, authentication_methods.rst,
  connection_handling.rst, exception_handling.rst, ha.rst, lob_data.rst
- Source: https://github.com/oracle/python-oracledb/tree/v26.0.1/src/oracledb
  (connection.py, cursor.py, defaults.py, errors.py, __init__.py)
- Tests: https://github.com/oracle/python-oracledb/blob/v26.0.1/tests/connection/test_2000_direct_path_load.py
  and tests/dataframe/test_1200_ingestion.py
- Issues 567, 573, 596, 597, 600, 605, 606: https://github.com/oracle/python-oracledb/issues
- https://pypi.org/pypi/oracledb/json

Oracle Database documentation

- JDBC Developer's Guide 21c, 2.3.8 About Committing Changes: https://docs.oracle.com/en/database/oracle/oracle-database/21/jjdbc/JDBC-getting-started.html
- SQL Language Reference 19c: TRUNCATE TABLE https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/TRUNCATE-TABLE.html ;
  INSERT https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/INSERT.html ;
  Nulls https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Nulls.html ;
  SET TRANSACTION https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SET-TRANSACTION.html ;
  Types of SQL Statements https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Types-of-SQL-Statements.html ;
  Data Types https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Data-Types.html
- Concepts 19c, Data Concurrency and Consistency: https://docs.oracle.com/en/database/oracle/oracle-database/19/cncpt/data-concurrency-and-consistency.html
- Database Development Guide 19c, Flashback: https://docs.oracle.com/en/database/oracle/oracle-database/19/adfns/flashback.html
- Utilities 19c: Conventional and Direct Path Loads https://docs.oracle.com/en/database/oracle/oracle-database/19/sutil/oracle-sql-loader-conventional-and-direct-loads.html ;
  SQL*Loader Command-Line Reference https://docs.oracle.com/en/database/oracle/oracle-database/19/sutil/oracle-sql-loader-commands.html
- Oracle Call Interface 21c, Direct Path Load Interface: https://docs.oracle.com/en/database/oracle/oracle-database/21/lnoci/direct-path-load-interface.html
- Oracle AI Database Free, Licensing Restrictions: https://docs.oracle.com/en/database/oracle/oracle-database/23/xeinl/licensing-restrictions.html

Polars

- Installed 1.44.2 (docstrings and source in site-packages) and the same files
  at https://github.com/pola-rs/polars/tree/py-1.44.2/py-polars/src/polars
  (lazyframe/frame.py, io/plugins.py, io/database/functions.py, _executor.py,
  _arrow_registry.py, _cursor_proxies.py, _utils.py, dataframe/frame.py)
- 2.0.0 release notes: https://github.com/pola-rs/polars/releases/tag/py-2.0.0 ;
  the same files at tag py-2.0.0
- https://pypi.org/pypi/polars/json

SQL Server drivers and Microsoft

- mssql-python: https://github.com/microsoft/mssql-python (README, CHANGELOG.md,
  ROADMAP.md, LICENSE, releases, tests/test_004_cursor_arrow.py at v1.15.0);
  wiki pages Cursor, Connection, Calling-Stored-Procedures,
  Database-Transaction-Management, Data-Type-Conversion,
  Known-Issues-and-Unsupported-Features;
  https://pypi.org/pypi/mssql-python/json , /mssql-python-odbc/json ,
  /mssql-python-rs/json
- pyodbc: https://github.com/mkleehammer/pyodbc (releases; wiki Install, Cursor,
  Features-beyond-the-DB-API, Data-Types); https://pypi.org/pypi/pyodbc/json
- arrow-odbc: https://github.com/pacman82/arrow-odbc-py (README, releases,
  python/arrow_odbc at v10.6.0); https://pypi.org/pypi/arrow-odbc/json
- ADBC: https://github.com/apache/arrow-adbc/blob/main/docs/source/driver/index.rst ;
  https://github.com/adbc-drivers/mssql ; https://adbc-drivers.org/drivers/mssql/
- connectorx: https://github.com/sfu-db/connector-x/tree/v0.4.6/docs (api.md,
  intro.md, freq_questions.md, databases/mssql.md, databases/oracle.md);
  releases
- pymssql: https://github.com/pymssql/pymssql/blob/master/ChangeLog.rst ;
  turbodbc: https://github.com/blue-yonder/turbodbc
- Microsoft docs (MicrosoftDocs/sql-docs, branch live):
  connect/odbc/linux-mac/system-requirements.md,
  installing-the-microsoft-odbc-driver-for-sql-server.md,
  install-microsoft-odbc-driver-sql-server-macos.md,
  release-notes-odbc-sql-server-linux-mac.md, release-notes-tools.md;
  connect/odbc/dsn-connection-string-attribute.md;
  t-sql/statements/bulk-insert-transact-sql.md, truncate-table-transact-sql.md,
  set-transaction-isolation-level-transact-sql.md, set-xact-abort-transact-sql.md;
  t-sql/data-types/datetime-transact-sql.md, datetimeoffset-transact-sql.md,
  money-and-smallmoney-transact-sql.md, uniqueidentifier-transact-sql.md;
  relational-databases/import-export/prerequisites-for-minimal-logging-in-bulk-import.md
- https://learn.microsoft.com/en-us/sql/linux/quickstart-install-connect-docker
  (redirects to linux/install-upgrade/quickstart-install-docker)
- https://learn.microsoft.com/en-us/azure/azure-sql-edge/overview (archived)

Other tools

- dbt: https://github.com/dbt-labs/docs.getdbt.com/blob/current/website/docs/docs/build/incremental-strategy.md ;
  website/docs/reference/dbt-jinja-functions/env_var.md and
  website/snippets/_env-var-secrets.md ;
  website/docs/reference/resource-configs/oracle-configs.md
- dlt: https://github.com/dlt-hub/dlt/tree/devel/docs/website/docs
  (general-usage/incremental-loading.md, full-loading.md, merge-loading.md,
  reference/explainers/how-dlt-works.md)
- Airbyte: https://github.com/airbytehq/airbyte/blob/master/docs/platform/using-airbyte/core-concepts/sync-modes/README.md
- Spark: https://github.com/apache/spark/blob/master/docs/sql-data-sources-jdbc.md
  and sql-data-sources-load-save-functions.md
- Sling: https://docs.slingdata.io/concepts/replication/modes ;
  https://docs.slingdata.io/connections/database-connections/oracle
- Apache Hop: https://github.com/apache/hop/blob/main/docs/hop-user-manual/modules/ROOT/pages/pipeline/transforms/tableoutput.adoc
- Airflow: https://github.com/apache/airflow/tree/main/airflow-core/docs
  (authoring-and-scheduling/connections.rst,
  security/secrets/mask-sensitive-values.rst)
- Dagster: https://github.com/dagster-io/dagster/tree/master/docs/docs/guides/build/external-resources
  (index.md, configuring-resources.md)
- Prefect: https://github.com/PrefectHQ/prefect/blob/main/docs/v3/concepts/blocks.mdx

Talend (Talaxie at 639d5fd1f776)

- https://github.com/Talaxie/tdi-studio-se/tree/639d5fd1f77699a574d26b8546b73d69cd4546f7/main/plugins/org.talend.designer.components.localprovider/components :
  tOracleConnection, tOracleInput, tOracleOutput, tOracleRow, tOracleSP,
  tOracleBulkExec, tOracleCommit, tOracleRollback, tOracleClose,
  tMSSqlConnection, tMSSqlInput (`*_java.xml`, `*_messages.properties`,
  `*.javajet`), and templates/DB/AbstractDBConnection.javajet

Containers and tests

- https://github.com/gvenzl/oci-oracle-free (README) ;
  https://hub.docker.com/v2/repositories/gvenzl/oracle-free/tags
- container-registry.oracle.com/v2/database/free (tags list and manifests)
- mcr.microsoft.com/v2/mssql/server and /v2/azure-sql-edge (tags, manifests,
  config blobs)
- testcontainers 4.15.0 as installed (`testcontainers/community/oracle`,
  `community/mssql`, `core`)
- https://pytest-xdist.readthedocs.io/en/stable/how-to.html

This repo

- `src/v2/engine/runner.py`, `src/v2/engine/context.py`,
  `src/v2/components/base.py`, `src/v2/job/keys.py`, `src/v2/job/loader.py`,
  `docs/v2/writing-a-component.md`, `pyproject.toml`
- `src/converters/talend_to_v1/components/database/*.py`,
  `src/converters/talend_to_v1/components/base.py`,
  `src/converters/talend_to_v1/xml_parser.py`,
  `src/converters/talend_to_v1/converter.py`
- `src/v1/engine/components/database/*.py`,
  `src/v1/engine/oracle_connection_manager.py`,
  `src/v1/engine/mssql_connection_manager.py`, `src/v1/engine/engine.py`
- `tests/talend_xml_samples/converted_jsons/Job_tOracle{Connection,Output,Row}_0.1.json`,
  `tests/v1/engine/components/database/integration/conftest.py`

---

## 7. The observations, in short form

Each was a script of its own, run with `.venv/bin/python -B`; these are the
parts that matter, enough to write them again. `ENGINE = "streaming"`.

```python
# A. a batch callback in the subjob's pass (2.3, finding 4)
seen = []
def load(batch):                                   # stands for cursor.executemany(...)
    seen.append((batch["n"][0], batch.height, threading.get_ident()))
frame = pl.scan_csv(src)                           # 1,000,000 rows
pl.collect_all([frame.sink_csv(out, lazy=True),
                frame.sink_batches(load, chunk_size=50_000, lazy=True),
                frame.select(pl.col("v").sum())], engine=ENGINE)

# B. a loader inside the plan is called from many threads (2.3)
rejects = frame.map_batches(load_and_return_refused, streamable=True, schema=REJECT_SCHEMA)
pl.collect_all([rejects.sink_csv(out, lazy=True)], engine=ENGINE)

# C. how often a Python reader runs (2.3, finding 5)
def reader(with_columns, predicate, n_rows, batch_size):
    log.append("called")                           # stands for executing the query
    for i in range(8):
        yield pl.DataFrame({"id": pl.int_range(i * 10_000, (i + 1) * 10_000, eager=True), "name": ["x"] * 10_000})
lazy = register_io_source(reader, schema={"id": pl.Int64, "name": pl.String}, is_pure=False)   # then True
numbered = lazy.with_row_index("__row", offset=1)
pl.collect_all([numbered.sink_csv(a, lazy=True), numbered.filter(pl.col("id") % 2 == 0).sink_csv(b, lazy=True),
                numbered.select(pl.col("__row").max()), numbered.select(pl.len())], engine=ENGINE)

# D. what Polars asks of a python-oracledb connection (2.1, finding 6)
# a module named `oracledb` on sys.path with __version__ = "3.4.2" and a class Connection that has
# fetch_df_all(statement, **kw) and fetch_df_batches(statement, size=None, **kw), each returning objects
# that only implement __arrow_c_stream__ over a pyarrow table; cursor() raises.
pl.read_database("select * from t where id > :1", conn, execute_options={"parameters": [5]},
                 schema_overrides={"AMOUNT": pl.Decimal(38, 2), "ID": pl.Int32})        # dtypes unchanged
next(pl.read_database("select * from t", conn, iter_batches=True, batch_size=1000))

# E. what a Polars frame exports through the PyCapsule stream (1.4)
pa.table(frame).schema                             # str -> string_view, bytes -> binary_view
frame.to_arrow().schema                            # str -> large_string

# F. spool memory, one scenario per process, resource.getrusage(RUSAGE_SELF).ru_maxrss (2.3)
with pa.OSFile(spool, "rb") as source:             # 91 MB for a 2,195 MB file
    reader = pa.ipc.open_file(source)
    for i in range(reader.num_record_batches):
        pl.from_arrow(reader.get_batch(i))
pl.collect_all([pl.scan_ipc(spool, memory_map=False).sink_batches(load, chunk_size=50_000, lazy=True)],
               engine=ENGINE)                      # 3,020 MB
pl.collect_all([pl.scan_parquet(spool_parquet).sink_batches(load, chunk_size=50_000, lazy=True)],
               engine=ENGINE)                      # 560 MB (zstd), 960 MB (lz4)

# G. the converter today (4.1)
TalendToV1Converter().convert_file("tests/talend_xml_samples/Job_tOracleOutput_0.1.item")
```
