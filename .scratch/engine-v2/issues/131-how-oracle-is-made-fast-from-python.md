# 131 - How Oracle is made fast from Python: what its makers say

Status: resolved
Type: research

## Question

With Oracle's own client (thick mode) the Oracle components were about
twice as slow and held more memory
([Oracle's own client (thick mode), tried](129-oracles-own-client-tried.md)).
The dev asked on 2026-10-13: research it, and see how the Oracle
components can be made faster with Python, what is recommended and what
is tested.

One research agent read the primary sources (python-oracledb's docs,
source and release notes at v26.0.1, ODPI-C's source, Oracle's own
guides, each other tool's own docs) and ran nothing. Its note is below
as it wrote it. What was tried on a real database is in
[Faster with Oracle's own client, and a fraction of a second that was lost](130-faster-with-oracles-own-client.md).

## Answer

**What the makers say, and what the trial said of it:**

| The sources say | Tried here | What v2 does now |
|---|---|---|
| The thin driver is the faster by construction; with the client every value is copied once more | yes: reading 12.8 s against 22 s as v2 first asked | reads 2,000 rows a round trip with the client: 13.9 s |
| An Arrow `large_string`, which Polars hands over, is bound as a LONG: with the client 64 KiB for every value, and for PL/SQL a temporary LOB for every value | yes, and it is the cause: 2.2 GB and 27.8 s with it, 0.57 GB and 0.87 s with Arrow's plain string | hands rows to the client as tuples, which was faster still (2.5 s a million rows against 3.6 s) |
| With the client a fetch keeps room for rows a round trip times each column's declared width | yes: 1.5 GB at 50,000 rows, 0.9 GB at 2,000 | as above |
| A larger session data unit for bulk transfer; the driver's own is 8 KB | yes: ten million rows read in 5.3 s, and in 4.6 s with 64 KB; no gain with the client | every session asks for the most; a connect string that names its own keeps it |
| With the client a procedure with a value coming out is one round trip a call | yes: 25,000 calls a second against 170,000 | nothing: the way round is one block that takes arrays, not built |
| `direct_path_load()`: only without the client, and it always commits | yes: 0.9 s a million rows; another session sees them at once; a key twice goes in and leaves the index unusable | not built: the output stores nothing unless the whole subjob succeeded |
| Native Network Encryption will never be in the thin driver; the ways out are TLS or the client | half: without the client the session is refused, with it everything passes. TLS was not tried: the scratch image has no tool to make a certificate | the refusal says how a job asks for the client |
| `APPEND_VALUES`: a direct path insert that can be rolled back, one statement a transaction | no | nothing |
| Reading in parallel over several sessions: possible, and one moment across them "can be difficult" | no | nothing: a query's rows are one moment's rows |
| No other library does without Oracle's client where the client is needed | no | nothing |

**What follows for the sites:**

- **Ask the DBAs what the databases demand.**
  - Nothing, or TLS with a password: no Oracle client is needed, and v2
    runs at its fastest.
  - Native Network Encryption: Oracle's client on the server, and
    `"oracle_config": {"thick_mode": true}`. Proven here.
  - Kerberos, a wallet that holds the password: only with the client,
    and v2 cannot sign in that way yet.
- **Where a database demands the encryption, ask whether it has a TLS
  listener too.** Oracle documents a setting for that
  (`IGNORE_ANO_ENCRYPTION_FOR_TCPS`). Then no client is needed.
- **Against Oracle 19 the session data unit has to be raised on the
  database's side too** (its own default there is 8 KB; on 23 it is 64
  KB). The two sides settle on the smaller.

**Not tried, and worth trying where it can be:** TLS without the
client, against a real listener; the session data unit over a real
network; `APPEND_VALUES`.

## The note: what the owners of the software say

Reading only; nothing was run against a database. Sources read on 2026-10-13.

How to read the citations:

- PYO = https://github.com/oracle/python-oracledb/blob/v26.0.1 (tag v26.0.1, commit cf7d2aa8, released 2026-09-22). `doc/src/...` there is the source of python-oracledb.readthedocs.io. `#Ln` is a line number at that tag.
- ODPI = https://github.com/oracle/odpi/blob/11ff9c50c2debb0684f7612ef537b54b042699d8 (the ODPI-C commit that tag builds thick mode on).
- ORA26 = https://docs.oracle.com/en/database/oracle/oracle-database/26 (the current "26ai" documentation set; 26ai is the name release 23.26 carries). ORA19 = the same with /19/.
- GH#n = https://github.com/oracle/python-oracledb/issues/n and GHD#n = https://github.com/oracle/python-oracledb/discussions/n.
- Tuininga = anthony-tuininga, shown by GitHub as MEMBER of the repository, who writes the fixes in the threads cited. Jones = cjbj, Christopher Jones of Oracle, who writes the driver's release announcements and answers for the team.
- Tags: [doc] documentation; [src] source code as I read it (what the code does, not something its owners promise); [maint] a maintainer's statement; [blog] first-party blog; [3p] third party.
- Quotes are verbatim, with reST markup dropped and typographic quotes written in ASCII.

### What the sources say, in short

1. Thin is the faster mode by construction, and the owners say why: "the thin driver has direct access to the network buffers, thereby eliminating a copy and conversion step that the thick driver has to take" [maint, GHD#5]. No Oracle benchmark of the two modes for data frames was found; their advice is "do your own benchmarking".
2. Arrow in thick mode is not a separate fast path. Rows are fetched into client-library buffers of `size` x declared column width, then copied into Arrow one value at a time; binds go Arrow -> ODPI-C -> OCI one value at a time [src]. Unchanged since 3.0 (fetch) and 3.3 (bind).
3. Strongest lead for your insert and PL/SQL numbers: an Arrow `large_string` column, which is what Polars' `to_arrow()` hands over, is bound as Oracle LONG, not VARCHAR2 [src]. In thick mode that costs a 64 KiB buffer for every value in DML, and a temporary LOB for every value in PL/SQL [src]. 10,000 rows x 3 text columns x 64 KiB = 1.97 GB. Not in the docs; one test with `pyarrow.string()` settles it.
4. `Connection.direct_path_load()` exists since 3.4.0 (October 2025), thin mode only, with "no plans to add it to Thick mode" [blog]. "The records are always implicitly committed" [doc], and there is no bad-row handling. It cannot be used where NNE forces thick, and by itself it breaks "nothing is stored unless the subjob succeeded".
5. NNE will not come to thin: "Thin mode won't support NNE via upper management decision" [maint, 2025-06-05]; no release through 26.0.1 has it. The ways out are TLS (thin does one-way TLS, mutual TLS with a PEM wallet, and since 26.0.0 certificate authentication) or thick. Kerberos is thick only.
6. PL/SQL for many rows: thick "internally performs the execute once for each iteration" [maint]; thin sends all iterations at once after the first. Pipelining is thin + asyncio only, and real only against 23.26/26ai.
7. Network: SDU up to 2 MB; "For bulk data transfer scenarios, increase to 64k" [Oracle Net best-practice deck]. The value used is the lower of the two sides. Thin takes an `sdu` parameter; thick reads sqlnet.ora or the connect string.
8. Parallel reads: one operation per connection; the driver docs ask for "careful benchmarking"; thin holds the GIL except during I/O, so processes rather than threads. Oracle documents partition, value-range and ROWID-range splits, and warns that one consistent view across them "can be difficult".
9. No alternative gets rid of Oracle's client: ConnectorX, the one Oracle ADBC driver (Columnar, commercial) and ODBC all sit on Oracle's client libraries. python-oracledb thin is the only route found without it.

### 1. Thin against thick, and Arrow in thick mode

What is said:

- [maint, GHD#5, 2022-06-01, Tuininga] "One of the significant benefits of the thin driver is the reduced memory and CPU usage -- mostly due to the fact that the thin driver has direct access to the network buffers, thereby eliminating a copy and conversion step that the thick driver has to take. This frequently translates to a noticeable difference in performance."
- [maint, same thread, Tuininga] "The thick driver makes use of ODPI-C, which allows for more processing to occur while the GIL is not held. The thin driver only releases the GIL when performing I/O. This means that depending on your workload you may see different performance characteristics between thick and thin."
- [maint, same thread, Jones] "You should do your own benchmarking (and let us know what you find). The numbers we see for the Thin mode are great - see the release announcement for some data." The announcement is on Medium, which answered HTTP 403; I did not read it.
- [doc] The user guide has no general "one mode is faster" statement. A search of appendix_a.rst and appendix_b.rst (the mode comparison pages) for faster, slower, performance, overhead found nothing.
- [doc] Costs stated for thick only: prefetch (section 2), a 2 GB bind buffer limit (section 3), PL/SQL with OUT binds (section 5).

How Arrow is done in each mode [src]:

- Thick fetch: `dpiStmt_fetchRows` fills ODPI-C variables, then `_populate_arrow_arrays` runs `for var_impl in self.fetch_var_impls: for i in range(self._buffer_rowcount): var_impl._transform_element_to_arrow(i)` (PYO/src/oracledb/impl/thick/cursor.pyx#L232-L241 and #L366-L388). Each value is copied out of ODPI-C's `dpiData` and appended to the Arrow array (PYO/src/oracledb/impl/thick/var.pyx#L430-L499).
- In that path a NUMBER comes from the client library as text and is parsed again (var.pyx#L451-L460); ODPI-C keeps a 173-byte text buffer for each NUMBER element (ODPI/src/dpiVar.c#L935-L948, ODPI/src/dpiImpl.h#L104). A timestamp has an OCI descriptor for each element (dpiVar.c#L984-L995).
- Thin fetch: each value is decoded from the network packet and appended to Arrow in the same pass (PYO/src/oracledb/impl/thin/messages/base.pyx#L1209-L1219). Both modes end in the same `convert_oracle_data_to_arrow`; thick has the extra buffers and copies before it.
- Binding a data frame: both modes read the Arrow array one value at a time through `convert_arrow_to_oracle_data` (PYO/src/oracledb/impl/base/converters.pyx#L32-L165). There an integer is printed as decimal text into a Python bytes object, a timestamp becomes a Python datetime, a decimal becomes bytes.
- Thin then writes the value straight into the network buffer (thin/messages/base.pyx#L1540-L1558).
- Thick copies it into an ODPI-C variable with `dpiVar_setFromBytes` (thick/var.pyx#L203-L215, #L360-L428). ODPI-C walks every element of every variable again before the execute ("transfer data from dpiData structure to Oracle buffer structures"), and for PL/SQL or RETURNING once more after it ("OCI doesn't provide a way of knowing if a variable is an out variable so do this for all of them") (ODPI/src/dpiStmt.c#L569-L585, #L671-L685). OCI then encodes for the wire.
- So yes: element by element through ODPI-C. There is no columnar hand-over to the client library in the code.

Versions (PYO/doc/src/release_notes.rst):

- 3.0.0 (March 2025), "Common Changes": `fetch_df_all()` and `fetch_df_batches()` added, both modes.
- 3.1.0 (April 2025): CLOB, BLOB, RAW; "More efficient processing when a significant amount of data is duplicated from one row to the next"; "Avoid memory allocation/free cycles for decimal data".
- 3.3.0 (July 2025): "Added support for binding data frames to Cursor.executemany() and AsyncCursor.executemany() for fast data ingestion."
- 3.4.0 (October 2025): "Support for data frames is no longer considered a pre-release"; `requested_schema`; LARGE_STRING and LARGE_BINARY by default; `batch_size` on `executemany()`; Direct Path Load (thin).
- 4.0.0 (May 2026), thick: `fetch_df_*` accept an external OCI statement handle; client libraries before 19c dropped.
- 26.0.0 (September 2026): decimal256, intervals, year-based version numbers. 26.0.1: "Fixed bugs with handling duplicate data when fetching Arrow data frames".
- The thick element loops read the same at v3.0.0 (fetch), v3.3.0 (bind) and v26.0.1. No release note speaks of a change to the speed of the thick Arrow path, and the unreleased 26.1.0 section on main (commit c92c842, 2026-10-07) has nothing on it.

### 2. Tuning a bulk fetch

- [doc, PYO/doc/src/user_guide/tuning.rst#L86-L93] Bigger buffers mean fewer round trips: "The performance benefit of larger buffer sizes can be significant when fetching lots of rows, or when using a slow network."
- [doc, tuning.rst#L135-L155] "The best arraysize and prefetchrows values can be found by benchmarking your application under production load." For large results: "increase the arraysize value from its default of 100 until you are satisfied with performance, memory, and round-trip usage"; the example sets 1000; "Do not make the sizes unnecessarily large."
- [doc, tuning.rst#L354-L364] Data frames: "tuning of data transfer across the network is controlled by the respective methods arraysize or size parameters. Any oracledb.defaults.prefetchrows value is ignored since these methods always set the internal prefetch size to the relevant arraysize or size value." The docstring agrees (PYO/src/oracledb/connection.py#L1647-L1652). The docs' own examples use 100, 1000, and `BATCH_SIZE = 10000` for writing Parquet (PYO/doc/src/user_guide/dataframes.rst#L602-L607). No number is recommended.
- The one stated mode difference [doc, tuning.rst#L115-L119]: "An overhead of row prefetching in python-oracledb Thick mode is the use of a separate buffer from the array fetch buffer, increasing the memory requirements. Also, an additional data copy from Oracle Client's prefetch buffer is performed. These costs may outweigh the benefits of using prefetching in some cases."
- [src] ODPI-C sets the prefetch for the execute round trip and then turns it off, "in order to avoid the overhead of copying from prefetch buffers to our own buffers" (ODPI/src/dpiStmt.c#L587-L596, #L661-L669). With `size=50_000` the first 50,000 rows therefore take the prefetch path, the rest do not.
- Thick memory [ODPI doc, ODPI/doc/src/functions/dpiStmt.rst#L867-L874]: "All variables defined for fetching must have this many (or more) elements allocated for them. The higher this value is the less network round trips are required to fetch rows from the database but more memory is also required."
- [src] The allocation is `maxArraySize * sizeInBytes` for each column (ODPI/src/dpiVar.c#L893-L903). For text, sizeInBytes is the declared characters times the client character set's maximum bytes for a character (dpiVar.c#L87-L96), and thick mode fixes the client character set to UTF-8 (PYO/src/oracledb/impl/thick/utils.pyx#L531). Over 32,767 bytes the variable becomes "dynamic" (dpiVar.c#L108-L112).
- So thick fetch memory grows with `size` and with the declared width of each column, not with the data. Arithmetic of mine: a VARCHAR2(4000 CHAR) column at 4 bytes a character and 50,000 rows a round trip is 800 MB for that one column. The width is what the query describes, so a `to_char(...)` or a cast in the query sets it.
- Thin: no such statement in the docs and no define buffers in the code; values go from the packet into Arrow builders.
- [3p, Columnar's ADBC driver, built on the same Oracle client libraries; https://docs.columnar.tech/drivers/oracle/ v0.6.3, 2026-09-08] "If there is little or no latency between your client and the database, then a low value (in the tens to hundreds of rows) is best. If there is high latency, then a higher value (in the thousands of rows) is best." and "Memory usage, however, is directly proportional to fetch_array_size ... (The Oracle SDK pre-allocates memory to hold fetch_array_size rows, hence increasing fetch size also increases allocation size.)" Not Oracle's words, but the only source found that names a range for a client-library fetch.
- `oracledb.defaults` [doc]: arraysize 100, prefetchrows 2 (tuning.rst#L139-L141, #L188-L190). Application-wide defaults "should not be the first tuning choice" (#L274-L276). Thick can also be tuned from `oraaccess.xml` without code (#L270-L272).
- LOBs [doc, PYO/doc/src/user_guide/lob_data.rst#L75-L77]: "CLOBs and BLOBs smaller than 1 GB can queried from the database directly as strings and bytes. This can be much faster than streaming a LOB Object." Data frame fetches always take LOBs as values: "Any LOB fetched must be less than 1 GB." (connection.py#L1669).
- Numbers [doc, dataframes.rst#L187-L203]: no precision and scale -> DOUBLE; scale 0 and precision up to 18 -> INT64; with `fetch_decimals` -> DECIMAL128; DECIMAL256 through `requested_schema` (26.0.0).
- `requested_schema` [doc, dataframes.rst#L332-L336]: "This can reduce memory consumption and improve processing speed." STRING in place of LARGE_STRING "will save 4 bytes per record" (#L209-L213). "Output type handlers cannot be used to map data types." (#L122-L124).

### 3. Tuning bulk DML

- [doc, PYO/doc/src/user_guide/batch_statement.rst#L76-L78] One `executemany()` is one round trip for the array.
- Batch size [doc, batch_statement.rst#L174-L176]: "Upper limits on memory or network buffers may affect the maximum number of rows that can be passed to executemany(). Also, in some environments, it may be more efficient to process smaller batches of records." The examples use `BATCH_SIZE = 10000` for CSV with "Adjust the number of rows to be inserted in each iteration to meet your memory and performance requirements" (#L492-L494) and `batch_size=200_000` (#L200). No number is recommended.
- Thick limit [doc, PYO/src/oracledb/cursor.py#L1114-L1117]: "In python-oracledb Thick mode, if the size of the buffers allocated for any of the parameters exceeds 2 GB, you will receive the error DPI-1015: array size of <n> is too large." It is the same rows x size rule as for fetches (ODPI/src/dpiVar.c#L893-L903).
- `setinputsizes` [doc, batch_statement.rst#L115-L125, #L143-L151]: without it "memory has to be reallocated and data copied"; "Since python-oracledb allocates memory for each row based on the supplied values, do not oversize them." And "For maximum efficiency, it is best to use the setinputsizes() method to specify the bind value types and sizes." (cursor.py#L1144-L1145).
- [src, not in the docs] With a data frame, the bind variables are built anew from the Arrow schema alone (PYO/src/oracledb/impl/base/batch_load_manager.pyx#L235-L252). As far as that code shows, sizes given with `setinputsizes` do not reach them.
- [src] The type follows the Arrow type (PYO/src/oracledb/impl/base/metadata.pyx#L317-L373): `string` and `string_view` -> DB_TYPE_VARCHAR, whose default size is 4000 (PYO/src/oracledb/impl/base/types.pyx#L416-L426); `large_string` -> DB_TYPE_LONG; `large_binary` -> DB_TYPE_LONG_RAW; integers and decimals -> NUMBER; `timestamp` -> TIMESTAMP; `date32`/`date64` -> DATE. The same lines stand at v3.3.0 and on main.
- [src] What LONG means in thick mode: ODPI-C gives the LONG type a buffer size of `DPI_MAX_BASIC_BUFFER_SIZE + 1` (ODPI/src/dpiOracleType.c#L267-L276), so the variable is "dynamic" (dpiVar.c#L108-L112). Each value then gets "exactly one allocated chunk of the specified size or greater", rounded up to a multiple of 65,536 bytes (dpiVar.c#L165-L196, dpiImpl.h#L113), and reaches OCI through a callback for each row (dpiVar.c#L841-L872).
- [src] A `string` column in thick mode instead gets one block of rows x 4000 characters x bytes for a character. Arithmetic of mine at 4 bytes: 10,000 rows is 160 MB for a column, a quarter of the LONG figure, and not adjustable from a data frame.
- [src] Thin sends LONG binds after the other columns ("non-LONG values are written first followed by any LONG values", thin/messages/base.pyx#L1640-L1676). Whether the database takes a LONG bind into a VARCHAR2 column more slowly than a VARCHAR2 bind is stated nowhere I found.
- Polars [doc]: the `DataFrame.to_arrow()` example prints `bar: large_string` (https://github.com/pola-rs/polars/blob/py-1.44.2/py-polars/src/polars/dataframe/frame.py#L1749-L1783). The driver team's own data frame examples pass `pyarrow.string()` [blog, 2025-10-07, below].
- Type mismatch [blog, Jones, 2025-09-19, https://medium.com/oracledevs/application-and-database-type-mismatches-slow-down-data-loads-eda6ced82702]: binding date strings into a DATE column took "29,576 ms" for 500,000 rows, and "7,568 ms" with datetime objects: "The number of round-trips was the same, but the bind type mismatch has been solved."
- `batcherrors` and `arraydmlrowcounts` [doc, batch_statement.rst#L342-L354, #L388-L394; cursor.py#L1119-L1131]: DML only; with batch errors "a transaction will be started but not committed, even if Connection.autocommit is set to True". Nothing is said of what either costs.
- APPEND_VALUES [Oracle, ORA26/sqlrf/Comments.html]: "The APPEND_VALUES hint can be used to greatly enhance performance. Some examples of its uses are: In an Oracle Call Interface (OCI) program, when using large array binds or array binds with row callbacks".
- The rules of that hint [Oracle, ORA26/admin/managing-tables.html]: "Direct-path INSERT with the VALUES clause is best used when there are hundreds of thousands or millions of rows to load. The typical usage scenario is for array inserts using OCI."; "You cannot query or modify data inserted using direct-path INSERT immediately after the insert is complete. If you attempt to do so, an ORA-12838 error is generated. You must first issue a COMMIT statement"; "the database obtains exclusive locks on the table"; "referential integrity constraints are ignored"; "If the database or tablespace is in FORCE LOGGING mode, then direct-path INSERT always logs".
- It is plain SQL, so it runs in either mode, and it can be rolled back ("Direct-path INSERT operations ensure atomicity of the transaction"). The python-oracledb docs never mention the hint. What I draw from ORA-12838, to be confirmed on the bed: a second batch into the same table in the same transaction would be refused, so one transaction is one `executemany()`.
- [doc, batch_statement.rst#L522-L524] "database changes such as temporarily disabling redo logging on the table, or disabling indexes may also be beneficial."

### 4. Direct Path Load

- Name [src]: `Connection.direct_path_load(schema_name, table_name, column_names, data, *, batch_size=2**32 - 1)`, and the same on `AsyncConnection` (PYO/src/oracledb/connection.py#L1557-L1578).
- Version [release notes, 3.4.0, October 2025, under "Thin Mode Changes"]: "Added support for Oracle Database's Direct Path Load functionality which is very efficient for loading large datasets into a database. Data may be a list of sequences or a DataFrame object."
- Modes [doc, batch_statement.rst#L652-L654]: "Direct Path Loads are only supported in python-oracledb Thin mode." Appendix A lists Thin Yes, Thick No (PYO/doc/src/user_guide/appendix_a.rst#L253-L256). [blog, Jones, 2025-10-07, https://medium.com/oracledevs/direct-path-loads-fast-data-ingestion-with-python-and-oracle-database-c681fb60384f] "The method is supported only in python-oracledb Thin mode - there are no plans to add it to Thick mode."
- Input [doc, #L686-L688]: "a list of sequences, a DataFrame object, or a third-party DataFrame instance that supports the Apache Arrow PyCapsule Interface". [maint, GH#551, Tuininga] "The performance of direct_path_load() using a dataframe will very likely exceed the same call with a list of tuples, probably by a very noticeable amount".
- Types [doc, #L726-L735]: "Data being inserted into CLOB or BLOB columns must be strings or bytes, not python-oracledb LOB Objects"; "Insertion of python-oracledb DbObjectType Objects is not supported"; VECTOR is shown. No full list of column types is given. Fixed since: single-byte database character sets (4.0.0, GH#567), string views (4.0.0, GH#573), booleans (4.0.2, GH#593).
- Columns left out [maint, GH#577, Tuininga]: "If you don't supply a column, then all values in that column are set to null. The direct path API requires that behavior." [Oracle, ORA26/sutil/oracle-sql-loader-conventional-and-direct-loads.html 12.4.3] "Default column specifications defined in the database are not available when you use direct path loading."
- Nothing is checked or converted by the database [src comment, PYO/src/oracledb/impl/thin/messages/direct_path_prepare.pyx#L60-L68]: "Unlike the regular code path, direct path loading writes directly to disk and the server does not perform any validation or conversion." [maint, GH#567, Tuininga] "The direct path API does not perform character set conversion, unfortunately. Since Python is incapable of handling all of the character sets provided by Oracle Database, there will be limitations."
- Commit [doc, #L684, #L728]: "The records are always implicitly committed." [blog] "There is no explicit commit() call here, since direct_path_load() will commit the data." [Oracle, ORA26/lnoci/direct-path-loading-functions.html] OCIDirPathFinish: "Finish and commit the loaded data". [Oracle, sutil 12.7.5.3] "Rows cannot be rolled back after a data save."
- A failure inside one call [src]: the driver sends a prepare, then one load message for each batch, then one last operation, which is FINISH when all went well and ABORT when anything raised (PYO/src/oracledb/impl/thin/connection.pyx#L879-L924; only those two operations exist, PYO/src/oracledb/impl/thin/constants.pxi#L710-L711). Oracle says of an abort: "the data loaded before the terminate operation is not visible to any queries. However, the data may still consume space in the segments that are being loaded." So one call reads as all or nothing across its batches. That is my reading of code plus the OCI text; the driver's docs promise nothing of the kind.
- An open transaction [Oracle, sutil 12.4.7]: "Segments that you want to load cannot have any active transactions pending." What the implicit commit does to other work waiting on the same session is not stated.
- Bad rows [blog]: "Unlike executemany(), there is currently no way to filter noisy data, so make sure your data is clean before trying to load it." [maint, GH#551, Jones] "There is nothing similar to batcherrors, though it would be useful."
- The database's rules; the driver docs only say "Review Oracle Database documentation for database requirements and restrictions":
  - [ORA26/lnoci/direct-path-load-interface.html] "Triggers are not supported. Referential integrity constraints are not supported. Clustered tables are not supported. Loading of remote objects is not supported. LONGs must be specified last." and "All partitioning columns must come before any LOBs."
  - Lock [same page]: "For a table load, if the OCI_ATTR_DIRPATH_PARALLEL option is set to: FALSE, then the table DML X-Lock is acquired"; "queries are lock-free and are allowed while the object is being loaded".
  - Constraints [sutil 12.4.4, 12.11]: NOT NULL, UNIQUE and PRIMARY KEY stay enabled; CHECK and FOREIGN KEY "are automatically disabled by default"; "Even though UNIQUE constraints remain enabled during direct path loads, any rows that violate those constraints are loaded anyway ... if a violation is detected, then the index will be left in an Index Unusable state."
  - Triggers [sutil 12.11.2]: "insert triggers do not fire for any rows loaded on the direct path".
  - Also refused [sutil 12.4.7]: clustered tables, tables with a VPD policy on INSERT, BFILE columns.
  - How python-oracledb behaves for each of these (whether it re-enables constraints, what a duplicate key leaves behind) is not documented.
- Partitions [maint, GHD#562, Tuininga, 2026-01-12]: loading into a named partition "is currently not supported by the driver".
- Batches [doc, #L737-L766]: `batch_size` "will send the data to the database in batches". [src] One batch may hold at most 1,073,728,895 bytes (constants.pxi#L702).
- Redo, where two sources differ. Driver docs: "because Direct Path Loads generate minimal redo, they reduce pressure on redo logs" (#L639-L640). Oracle: "By default, a direct path load is RECOVERABLE", and full-image redo is avoided only with NOARCHIVELOG, UNRECOVERABLE or NOLOGGING (sutil 12.8.5). The driver's prepare message sets no such option (direct_path_prepare.pyx#L141-L145).
- Speed claims: [doc, #L636-L650] "very efficient for ingestion of huge amounts of data"; "for smaller data sets may not be faster than using Cursor.executemany()". [blog; an emulated x86 database on an arm64 Mac] "For my 2,000,000 row file, Direct Path Loading was 4 times faster than using Pandas, and 3 times faster than solution #2, our old recommendation." (#2 is the csv module plus `executemany()` of a list.) No figure against `executemany()` with a data frame is in the text; the chart could not be read. [a user in GHD#562, not a maintainer] "up to 30-40% reduced load times, though that fluctuates quite a bit".
- Database versions: none are stated. Issue reports show it in use against 19c (GH#551, GH#567, GH#577).

### 5. PL/SQL with executemany

- [doc, batch_statement.rst#L213-L214] "Using executemany() can improve performance when PL/SQL functions, procedures, or anonymous blocks need to be called multiple times."
- [doc, #L285-L287] "Note that in python-oracledb Thick mode, when executemany() is used for PL/SQL code that returns OUT binds, it will have the same performance characteristics as repeated calls to execute()."
- [maint, GH#599, Tuininga, 2026-07-24] "Thick mode (in the Oracle Client libraries) internally performs the execute once for each iteration, so the results are seen after each iteration and those results passed in to the next iteration. In thin mode, however, the first iteration is done independently in order to determine the direction of all bind variables. Once that is complete, however, all subsequent iterations are sent at once -- which is a significant performance boost."
- Since 26.0.0 thin also sends one iteration at a time when a bind is IN/OUT (release notes 26.0.0; PYO/src/oracledb/impl/thin/statement.pyx#L439-L453).
- The docs' sentence is about OUT binds; the maintainer's is general. Neither says what thick does for a block with IN binds only. [src] ODPI-C hands the whole count to one OCI call (ODPI/src/dpiStmt.c#L1338-L1341), so whatever happens for each iteration is inside Oracle's client library, which cannot be read.
- [src] Text in thick PL/SQL: "for PL/SQL where the maxSize is greater than 32K, adjust the variable so that LOBs are used internally" (dpiStmt.c#L154-L161). A LONG variable is always "dynamic", so this is done for every Arrow `large_string` column bound to a block or a call, however short its values.
- [src] ODPI-C then creates a temporary LOB for each element (dpiVar.c#L455-L465) and writes each value with a trim and a write (ODPI/src/dpiLob.c#L191-L202; dpiVar.c#L261-L301, #L1232-L1237). [Oracle, ORA26/lnoci/oci-function-server-round-trips.html] OCILobCreateTemporary() 1 round trip, OCILobTrim2() 1, OCILobWrite2() 0 or 1. That is 2 to 3 round trips for each text value.
- [doc, #L234-L235] `batcherrors` "cannot be used with PL/SQL block execution". [src] ODPI-C refuses a query in `executeMany` ("queries are not supported", dpiStmt.c#L1309-L1313): the DPI-1013 the engine already handles.
- What the docs offer in place of many executions: "Make good use of PL/SQL to avoid executing many individual statements from python-oracledb." (tuning.rst#L44-L45); and "PL/SQL Collections like Associative Arrays can be bound as IN, OUT, and IN/OUT variables. When binding IN values, an array can be passed directly", with `Cursor.arrayvar()` for values coming out (PYO/doc/src/user_guide/bind.rst#L466-L518).
- FORALL appears only in Oracle's text on APPEND_VALUES. No page says "bind arrays to one block in place of executemany in thick mode"; it is what the documented pieces allow. Limits on the size of an array bind were not checked.
- Pipelining [doc, PYO/doc/src/user_guide/asyncio.rst#L436-L465]: "Pipelining is only supported in python-oracledb Thin mode with asyncio." "True pipelining only occurs when you are connected to Oracle AI Database 26ai, or later. When you connect to an older database, operations are sequentially executed by python-oracledb ... There is no reduction in round-trips and no performance benefit." "Pipelined operations are executed sequentially by the database."

### 6. Native Network Encryption and the ways around it

- Releases: through 26.0.1, and in the unreleased 26.1.0 section on main, the only mention of NNE is the 3.0.0 error text: "DPY-3001: Native Network Encryption and Data Integrity is only supported in python-oracledb thick mode". [src] Thin answers the negotiation with "no encryption" and "no data integrity" (PYO/src/oracledb/impl/thin/messages/network_services.pyx#L198-L245). Appendix A: NNE, Thin "No - use TLS instead", Thick "Yes" (appendix_a.rst#L133-L136).
- [maint, GH#94, Tuininga, 2022-11-04] "I have a proof of concept implementation internally ... my proof of concept has demonstrated that native network encryption (NNE) imposes a significant overhead on the network traffic. I see it taking up to 3 times longer to perform the same work with NNE as without."
- [maint, GH#94, Jones, 2023-05-26] "We won't be supporting NNE in Thin mode. The solutions are to use TLS or Thick mode."
- [maint, GHD#503, Jones, 2025-06-05] "Thin mode won't support NNE via upper management decision - sorry about that. Using industry standard encryption is recommended."
- [doc, PYO/doc/src/user_guide/troubleshooting.rst#L328-L334] For DPY-3001: "Changing the architecture to use Transport Layer Security (TLS), which is supported in python-oracledb Thin and Thick modes" or "enabling python-oracledb Thick mode".
- Oracle on the choice [ORA26/dbseg/oracle-database-native-network-encryption-and-data-integrity.html]: "There are advantages and disadvantages to both methods." NNE: "In most cases, no client configuration changes are required. No certificates are required.", against "It uses a non-standard, Oracle proprietary implementation. It provides no non-repudiation of the server connection". TLS: "It is an industry standard for encrypting data in motion", "It can be used for database user authentication", against "It requires client and server changes. Certificates are required for server". That page does not tell the reader to prefer TLS; the push comes from the driver team.
- Thin supports [doc]: one-way TLS ("Both python-oracledb Thin and Thick modes support one-way TLS.", PYO/doc/src/user_guide/connection_handling.rst#L5102); mutual TLS with `ewallet.pem`, `wallet_location` and `wallet_password` (#L5216-L5251; thick uses `cwallet.sso`); authentication by TLS client certificate since 26.0.0 (release notes; PYO/doc/src/user_guide/authentication_methods.rst#L365-L376, "can be used in both python-oracledb Thin and Thick modes"); tokens (appendix_a.rst#L81-L88).
- Thin does not support: Kerberos and RADIUS (appendix_a.rst#L89-L92; GH#82 open since 2022, Jones on 2022-12-04: "no status change. Please continue to use Thick mode."); wallet (SEPS) and operating-system external authentication (authentication_methods.rst#L143-L146; appendix_a.rst#L169-L172); sqlnet.ora (appendix_a.rst#L145-L148).
- The docs contradict themselves on external authentication: "only supported in python-oracledb Thick mode" (authentication_methods.rst#L143-L146) and "No" for thin in Appendix A (#L77-L80), against the TLS section and the 26.0.0 release note. The TLS text is the newer.
- So thick can be left out when all of these hold:
  - The database does not REQUIRE NNE or checksumming. [ORA26/dbseg/configuration-data-encryption-and-integrity.html] "The default value for each of the parameters is ACCEPTED."; "The REQUESTED value enables the security service if the other side permits this service."; "The REQUIRED value enables the security service or preclude the connection." A thin session to an ACCEPTED or REQUESTED server is then in clear text unless it uses TLS.
  - Or the database offers a TCPS listener. Where SQLNET.ENCRYPTION_SERVER has to stay `required` for other clients, Oracle's text is: "you can set the IGNORE_ANO_ENCRYPTION_FOR_TCPS parameter in both SQLNET.ENCRYPTION_CLIENT and SQLNET.ENCRYPTION_SERVER to TRUE" (same page).
  - And the user is authenticated by password, token or TLS certificate, not by Kerberos.
- The cost of NNE by algorithm: no figures in Oracle's Security Guide. It says of AES in outer CBC mode "with no material performance penalty", but against inner CBC, not against no encryption. "Oracle recommends SHA-2, but maintains SHA-1 (deprecated) for backward compatibility." (ORA26/dbseg/data-integrity-algorithms-support.html). The server "picks the first algorithm in its own list that also appears in the client list". The driver docs say only "review the available algorithms for security and performance" (connection_handling.rst#L5012-L5014). The one number anywhere is Tuininga's "up to 3 times longer", for his unreleased thin implementation.

### 7. Network tuning for large transfers

- SDU [Oracle, ORA26/netag/configuring-session-data-unit.html]: "When large amounts of data are being transmitted, increasing the SDU size can improve performance and network throughput."; "The SDU size can range from 512 bytes to 2 MB. ... A high SDU size value requires more memory."; "The actual SDU size used is negotiated between the client and the server at connect time and is the smaller of the client and server values."; "If sufficient memory is available, then using the maximum value for the SDU minimizes the number of system calls and overhead for Oracle Net Services."
- Defaults differ by release. 26ai: "The default SDU size for the client is 8192 bytes and the server is 65536 bytes." 19c (ORA19/netag/optimizing-performance.html): "The default SDU size for the client and a dedicated server is 8192 bytes. The default SDU size for a shared server is 65535 bytes." So against 19c both sides have to be raised; against 23.26 raising the client alone may do.
- [Oracle, "Oracle Net Services: Best Practices for Database Performance and High Availability", Kant C Patel, Oracle OpenWorld 2019, slides 14-15; the deck the driver's tuning page links to, https://static.rainfocus.com/oracle/oow19/sess/1553616880266001WLIh/PF/OOW19_Net_CON4641_1569022126580001esUl.pdf] "Max: 2MB (12c), 64K (11.2)"; "Larger SDU gives: Better Network throughput; Fewer system calls to send and receive data; Less CPU usage"; "For bulk data transfer scenarios, increase to 64k: Large array fetch, LOB transfers, XML DB"; "Increase SDU on both client and server"; "Do not set to MTU value".
- In the driver [doc, tuning.rst#L64-L70]: "In python-oracledb Thick mode, the SDU size is configured in the Optional Oracle Net Configuration Files. In python-oracledb Thin mode, the SDU size can be passed as a connection or pool creation parameter. In both modes it may optionally be set in the connection Easy Connect string or connect descriptor."
- The `sdu` parameter came in 2.0.0 (December 2023, thin); default 8192; "Bigger values can increase throughput for large queries or bulk data loads, but at the cost of higher memory use." (PYO/src/oracledb/connect_params.py#L322-L328). [src] It is held between 512 and 2,097,152 (PYO/src/oracledb/impl/base/connect_params.pyx#L1090).
- Socket buffers [Oracle, ORA26/netag/configuring-i-o-buffer-space.html]: "For optimal network performance, these buffers should be set to at least the bandwidth-delay product." Linux defaults: SEND_BUF_SIZE 131,072 bytes, RECV_BUF_SIZE 174,700 bytes. "Because the database server writes data to clients, setting the SEND_BUF_SIZE parameter on the server-side is typically adequate." Deck, slide 13: "Set this size to accommodate the BDP (2x)"; "Set on both the server and the client"; it helps "In WAN deployments".
- Those are sqlnet.ora, tnsnames.ora and listener.ora parameters: thick mode and the server. Thin has no documented equivalent; [src] it sets TCP_NODELAY and keepalive and no buffer size (PYO/src/oracledb/impl/thin/transport.pyx#L325-L333).
- Compression [Oracle, ORA26/netrf/parameters-for-the-sqlnet.ora.html]: "If both the server and client have this parameter set to ON, then compression is used for the connection."; levels "low to use low CPU usage and low compression ratio" and "high to use high CPU usage and high compression ratio". "Advanced Network Compression" is listed under the Advanced Compression option (ORA19/dblic/Licensing-Information.html). The client side is sqlnet.ora, so thick only; nothing is documented for thin.

### 8. Parallelism

- Thread safety [doc, PYO/src/oracledb/__init__.py#L194-L200]: `threadsafety = 2`, "threads may share the module and connections, but not cursors". The same constant serves both modes. A process has one mode: "all connections must be the same mode" (PYO/doc/src/user_guide/initialization.rst#L362-L363).
- [doc, tuning.rst#L379-L383] "A single python-oracledb connection can only do one database operation at a time, so you need to use a different connection for each executed SQL statement, for example, using connections from a pool. This will cause extra database load that needs to be assessed."
- The GIL: [maint, GHD#5] thick "allows for more processing to occur while the GIL is not held. The thin driver only releases the GIL when performing I/O." [doc, tuning.rst#L78-L79] "If Python's Global Interpreter Lock (GIL) is limiting concurrent program performance, then explore using parallel Python processes."
- The driver's own advice on splitting one table [doc, tuning.rst#L366-L409]: "you should do careful benchmarking"; "A naive solution using the OFFSET FETCH syntax to fetch sections of a table in individual queries will still cause table blocks to be scanned even though not all data is returned."; "Is the table partitioned?"; "Is it better to execute a single query in Python but use a PARALLEL query hint? Or will this overload the database."
- Oracle on splitting an extract [ORA26/dwhsg/extraction-data-warehouses.html, chapter 17]: by partition, "SELECT * FROM orders PARTITION (orders_jan1998);"; "The logical method is based on logical ranges of column values"; "The physical method is based on a range of values ... you could then derive a set of rowid-range queries ... SELECT * FROM orders WHERE rowid BETWEEN value1 and value2;".
- Its two warnings [same page]: "the coordination of independent processes to guarantee a globally consistent view can be difficult" and "all parallel techniques can use considerably more CPU and I/O resources on the source system, and the impact on the source system should be evaluated". The first bears on the engine's rule that a query's rows are one moment's rows.
- DBMS_PARALLEL_EXECUTE [ORA26/arpls/DBMS_PARALLEL_EXECUTE.html]: "enables incremental update of table data in parallel"; it chunks by ROWID, by a NUMBER column ("takes the MIN and MAX value of the column, and then divides the range evenly according to chunk_size"), or by a SELECT. It is documented for updates; no Oracle page offers its chunks for extraction. ORA_HASH as a way to split an extract was not found in Oracle's docs.
- ConnectorX [its README at https://github.com/sfu-db/connector-x/blob/d0d8e151b7d83d0675decf6c025f176d5de9e61f/README.md#L30-L32 and #L79-L87, and docs/freq_questions.md]: "The function will partition the query by evenly splitting the specified column to the amount of partitions. ConnectorX will assign one thread for each partition to load and write data in parallel. Currently, we support partitioning on numerical columns (cannot contain NULL) for SPJA queries." It first asks "SELECT MIN($partition_on), MAX($partition_on)" and a COUNT for each partition. "It is recommended to set the partition_num to the number of available logical cores." Each partition is a query of its own; nothing is said of one snapshot across them.
- Spark [Spark 4.2.0, https://spark.apache.org/docs/latest/sql-data-sources-jdbc.html]: "partitionColumn must be a numeric, date, or timestamp column from the table in question. Notice that lowerBound and upperBound are just used to decide the partition stride, not for filtering the rows in table."; numPartitions "also determines the maximum number of concurrent JDBC connections"; fetchsize "can help performance on JDBC drivers which default to low fetch size (e.g. Oracle with 10 rows)"; batchsize defaults to 1000.

### 9. Other Arrow-native routes from Python

- ConnectorX 0.4.6 (2026-09-18). Reads only. Its Oracle source is built on the Rust `oracle` crate (connectorx/Cargo.toml#L43), "an Oracle database driver for Rust based on ODPI-C" whose run-time requirement is "Oracle client 11.2 or later" (https://github.com/kubo/rust-oracle/blob/master/README.md#L7-L19). So it needs Oracle's client libraries, as thick mode does.
  - Its own docs (docs/databases/oracle.md): "With Instant Client 23.4 some FALSE values come back as True, depending on the fetch array size, and no error is raised."
  - Types: a NUMBER with a scale becomes `rust_decimal::Decimal`, "limited to ~28-29 significant digits and a max scale of 28", narrower than NUMBER's 38. LOB and RAW are not in its type table.
  - Speed claim: "ConnectorX uses 3x less memory and 3x less time compared with Pandas" (its own benchmark, on RDS). It publishes no comparison with python-oracledb's data frames.
- ADBC. Apache's driver list (ADBC 24 documentation, https://arrow.apache.org/adbc/current/driver/index.html) names no Oracle driver; its JDBC adapter needs a JVM.
  - A third-party one exists, Columnar's "Driver for Oracle Database" (v0.6.3, 2026-09-08, https://docs.columnar.tech/drivers/oracle/): "This project is not affiliated with Oracle."; "This driver is available from Columnar's private driver registry. Before installing it, create an account at cloud.columnar.tech and click to activate a 14-day free trial."; "Install the Oracle Instant Client libraries."; tested on "godror ... +ODPI-6.0.0". Commercial, a shared library and no wheel, and again on Oracle's client.
- arrow-odbc 10.6.0 (2026-10-07, https://github.com/pacman82/arrow-odbc-py): "Makes efficient use of ODBC bulk reads and writes"; wheels exist, but "The provided wheels dynamically link against the driver manager, which must be provided by the system" (unixODBC). Oracle is not mentioned. Oracle's ODBC driver is an Instant Client add-on ("ODBC Package ... Additional libraries for enabling ODBC applications", https://www.oracle.com/database/technologies/instant-client/linux-x86-64-downloads.html): the same client libraries once more.
- turbodbc 5.3.0 (2026-07-01, https://github.com/blue-yonder/turbodbc, docs/pages): `pip install turbodbc` "will trigger a source build that requires compiling C++ code"; it is tested with PostgreSQL, MySQL, MSSQL and Exasol, and Oracle is not on the list. It needs unixODBC and an ODBC driver.
- Against "pure Python wheels, no JVM, no Oracle client", none of the four qualifies.

### 10. What else the sources recommend

- [doc, batch_statement.rst#L613-L627] "Avoiding Copying Data Over the Network": "it may be preferable to use INSERT INTO SELECT or CREATE AS SELECT"; across databases "consider creating a database link".
- [doc, #L533-L538] "You should also review whether Oracle's specialized data loading tools and features suit your environment. These can be faster than using Python. See SQL*Loader and External Tables."
- [doc, tuning.rst#L72-L73] "Do not commit or rollback unnecessarily. Use Connection.autocommit on the last of a sequence of DML statements." It saves the commit's round trip.
- [doc, #L526-L527] "The PyArrow package's CSV methods may be more efficient than the default CSV module." The blog of 2025-10-07 found a data frame through `executemany()` "another step better" than a list.
- Bind as the column's own type (the blog of 2025-09-19, section 3).
- [doc, tuning.rst#L41-L42] "It may be faster to work with simple scalar relational values than to use Oracle Database object types." Statement cache: 20 statements by default (#L514-L516).
- Thick only: `oraaccess.xml` tunes prefetch and the statement cache without code (tuning.rst#L270-L272, #L525-L527).
- [doc, batch_statement.rst#L768-L777] Memoptimized Rowstore, "particularly for frequent single row inserts": not a bulk tool.
- Databases that are not UTF-8, in thick mode: the client character set is always UTF-8 [src, utils.pyx#L531]. A user asked on 2026-09-30 for it to be configurable (GH#614, open); Jones: "I suspect (b) may not be feasible but I'll let Anthony comment."

### What my measurements above agree or disagree with

- Reads, thin 13-15 s against thick 16.5-31 s: agrees with the maintainers ("eliminating a copy and conversion step", "reduced memory and CPU usage") and with the code (define buffers, NUMBER through text, a copy for each value).
- Thick faster and smaller with fewer rows a round trip (24-31 s and 1.5 GB at 50,000; 19.8 s at 5,000; 16.5 s and 0.8 GB at 1,000): agrees with ODPI-C's rows x declared width allocation, with the docs' "separate buffer" and "additional data copy" for prefetch (which `fetch_df_batches` sets equal to `size`), with "Do not make the sizes unnecessarily large", and with Columnar's advice of tens to hundreds of rows on a link without latency. No Oracle text predicts the size of the effect.
- It disagrees with the line in docs/v2/own-rule/databases.md that a thousand rows "took about 40% longer than 50,000". That was a thin measurement; in thick the order is reversed. The sources support a default for `size` chosen by mode.
- Inserts, thick 47-50 s and 2.4 GB at 10,000 rows a batch: the memory agrees closely with the LONG finding. 10,000 rows x 3 text columns x 65,536 bytes is 1.97 GB of chunks, on top of the process's base. At 2,000 rows a batch the same sum is 0.39 GB. Whether the time is the same cause is not shown by any source; a run with `pyarrow.string()` columns, and one with lists plus `setinputsizes`, would tell.
- A block for each of 100k rows from an Arrow table, thin 1.2 s against thick 28-31 s: the docs do not predict this (their warning is about OUT binds). The code does: three `large_string` columns bound to PL/SQL in thick mode are 300,000 temporary LOBs at 2 to 3 round trips each, 600,000 to 900,000 round trips. At the 38 microseconds a round trip that your stored procedure figure implies (3.8 s for 100k), that is 23 to 34 s. The same block with `pyarrow.string()` columns, or with tuples, should fall to about the stored procedure's time if this is right.
- A procedure with one OUT bind, thin 0.66 s against thick 3.8 s: agrees with the docs' note for thick ("the same performance characteristics as repeated calls to execute()"), with GH#599, and with thin's code (first iteration alone, the rest at once).
- A plain INSERT for each of 100k rows, the same in both: agrees with the docs (one round trip for an array in both modes). It also says a LONG bind in thick DML costs no round trip for each row, so the LONG finding explains thick's memory in DML more surely than its time.
- DPY-3001 from thin against NNE: exactly as documented, and by decision permanent.
- One caution: if the thick timings were taken against the database that demands NNE, they hold the cost of encryption as well as of the driver path. The only figure for that cost is the maintainer's "up to 3 times longer", and it is for another implementation. A thick run against a database without NNE separates the two.

### Not established

- Any Oracle-published comparison of thin and thick for `fetch_df_batches` or for `executemany()` with a data frame. The launch announcement the maintainers point to for numbers could not be read (Medium, HTTP 403).
- A recommended `size` for data frame fetches, in either mode, from Oracle. The docs' examples (100, 1000, 10000) carry no reasoning.
- What `batcherrors` and `arraydmlrowcounts` cost. Nothing found.
- Whether a LONG bind (from `large_string`) is slower than a VARCHAR2 bind in thin mode or inside the database. Nothing found.
- Whether `setinputsizes` is meant to be ignored for data frame input. The code does so; the docs are silent.
- For `direct_path_load()`: the list of supported column types; what its commit does to other pending work on the session; that an error in a later batch leaves no rows (read from code, not promised, not tried); what a duplicate key leaves behind; whether redo is in fact reduced on an archive-logging or FORCE LOGGING database.
- What thick does for a PL/SQL block with IN binds only, for each iteration. The docs speak of OUT binds, the maintainer generally, and the behaviour is inside Oracle's client library.
- An Oracle text recommending "one block with array binds" over `executemany()` for PL/SQL, and the size limits of such binds.
- NNE's cost for each cipher and checksum (AES128/192/256, SHA1/SHA256/SHA512). No figures in Oracle's docs.
- Whether thin can connect over TCPS to a server with SQLNET.ENCRYPTION_SERVER=required when IGNORE_ANO_ENCRYPTION_FOR_TCPS is not set. Oracle's text suggests the parameter is needed; the driver's docs do not say.
- Any plan for Kerberos in thin. GH#82 is open, with no word since 2022.
- Socket buffer sizes and compression in thin mode. Not documented, and not in the code.
- An Oracle recommendation to split an extract by ORA_HASH or by DBMS_PARALLEL_EXECUTE chunks, and a documented way to hold one snapshot across parallel sessions. I did not look into flashback queries (AS OF SCN).
- How ConnectorX compares with python-oracledb's data frames. It compares itself with Pandas only.
- Two first-party posts whose titles came up in search and which I could not open (Medium, HTTP 403): "Going 10x faster with python-oracledb Data Frames" and "Selecting from an Oracle Database table in parallel using Python". Nothing here rests on them.
