# Databases

The components that open a session with a database, work in it, and end
what was done: nine for Oracle, and two that read from SQL Server.

Built to their own rule: what is written here is what they are held to,
not v1 or Talend. ([What that means](README.md).) Why each rule is as it
is, and what a real Oracle said when it was tried, is in the decisions
ticket (`.scratch/engine-v2/issues/118-databases-the-decisions.md`).

## Sessions and transactions

- **A component does its work and never ends a transaction. The engine
  does.** Nothing is stored for a subjob that fails.
- **A session a connection component opens is shared.** Components that
  name it in `connection` work on it, and what they do waits until a
  commit component stores it. A subjob that fails on it loses what it
  did there; what earlier subjobs did still waits.
- **A component that opens a session for itself** has its work stored
  when its subjob has succeeded, and rolled back when it has not. It
  needs no commit component.
- **A commit comes before any file of the subjob is put in place.** A
  commit can fail, and no file is in place yet when one does. A file
  that cannot be put in place after a commit fails the subjob and says
  what is stored: a commit is not taken back.
- **A job that ends with work nothing stored has failed.** The work is
  rolled back and the failure says whose it was. Rows that were loaded
  and never stored are no success.
- **A statement that stores by itself** (in Oracle: `CREATE`, `ALTER`,
  `DROP`, `TRUNCATE` and the like) stores what waited on the session
  before it. The engine sees that, and does not say afterwards that the
  work waits.
- A job run by another job has sessions of its own. None is shared
  between them.

### Oracle

- The driver is python-oracledb, 26.0.1 or later
  (`pip install 'dataprep[v2-oracle]'`); an older one refuses to open a
  session, since earlier ones hand on wrong numbers. It needs no client
  of Oracle's. A job says otherwise at its top:

  ```json
  "oracle_config": {"thick_mode": true, "lib_dir": "/opt/oracle/instantclient"}
  ```

  Oracle's own client is then loaded (it is needed where a database asks
  for Native Network Encryption or Kerberos). A process uses one or the
  other: the first job that opens a session decides. This was not tried
  here: no client was at hand.
- A session says in the database who it is: its module is `dataprep-v2`
  and its action the job's name (`v$session`).
- **The connection block** is the same on every component that can open
  a session:

  | `connection_type` | Opens a session with |
  |---|---|
  | `ORACLE_SID` | `host`, `port`, and a SID in `dbname` |
  | `ORACLE_SERVICE_NAME` | `host`, `port`, and a service name in `dbname` |
  | `ORACLE_RAC` | the connect string in `rac_url`: Oracle's own form, or a JDBC URL, whose `jdbc:oracle:thin:@` is taken off |
  | `ORACLE_OCI` | the name `local_service_name` has in tnsnames.ora; with `use_tns_file`, the file `tns_file` names |
  | `ORACLE_WALLET` | refused: the wallet holds the user and the password, and only Oracle's own client reads it |

- `user` and `password` are given by themselves. A `rac_url` that
  carries them refuses the job. The password is shown in no log and is
  put nowhere, globalMap included.
- A password Talend encrypted (`enc:system.encryption.key.v1:...`)
  refuses the job: only Talend can read it. Give the password from a
  context variable.
- Refused, with what to do instead: `use_ssl` (Java key stores are not
  read; a `rac_url` that says `tcps` opens a session over TLS),
  `use_shared_connection`, and any JDBC parameter in `properties`.
- What the database refuses is said in its own words on one line
  (`ORA-00942: ...`), without the link to its help.
- For whoever builds on the driver: python-oracledb 26.0.1 brings the
  interpreter down (a segmentation fault) when `call_timeout` is set on
  a session the database has closed. A time limit is set once, when a
  session is opened, and never after. Asking a dead session whether it
  lives, rolling it back and closing it are safe.

### SQL Server

- The driver is Microsoft's mssql-python, 1.15.0 or later
  (`pip install 'dataprep[v2-mssql]'`). It needs no ODBC driver of the
  system's. v2 was tried with no earlier one, and refuses to open a
  session with one.
- **v2 reads from SQL Server and stores nothing there.** There is a
  connection and an input. Every statement on a session is stored by
  itself: nothing waits for a commit, and what a procedure that a query
  calls has changed is stored at once.
- **The connection block** is the same on both: `host`, `port`,
  `dbname`, `user`, `password`. An instance of its own is named in the
  host (`server\instance`); with `port` left empty the driver finds the
  port that instance has. With no `dbname` the database is the one the
  user has by default.
- **What is sent is encrypted, and the server's certificate is
  checked**, as Microsoft's drivers do since 2022. A server with a
  certificate of its own making fails to open a session, and the
  failure says what can be done: have the certificate signed, or turn
  `trust_server_certificate` on. `encrypt` takes `yes`, `no` or
  `strict`.
- v2 signs in with a user and a password of the database's own. Signing
  in through Microsoft Entra (`active_dir_auth`) and through Kerberos
  were not at hand to be tried, are not built, and refuse the job.
- **Talend's JDBC parameters** (`properties`, as `name=value;name=value`)
  are read where they mean something here: `encrypt`,
  `trustServerCertificate`, `hostNameInCertificate`,
  `applicationIntent`, `multiSubnetFailover` and `loginTimeout`. A key
  of v2's own goes before them. The ones that say how a JDBC driver
  works are passed over, `noDatetimeStringSync` among them, which
  Talend's own input carries when nothing was said. Any other refuses
  the job by its name.
- `user` and `password` are given by themselves, and the password is
  shown in no log and put nowhere. A password Talend encrypted refuses
  the job.
- A closed session is closed. Left to itself the driver keeps one for
  whoever opens the next; v2 turns that off, unless the process has
  said itself how sessions are kept.
- **A session cannot say which job it is.** The program name it shows
  in the database is `MSSQL-Python`: the driver sets it and takes no
  other.
- What the database refuses is said in its own words on one line. **An
  error that comes while rows are being read has no words**: the driver
  loses them (mssql-python 1.15.0). The failure then says how many rows
  were read, and to run the query in another client to see the reason.

## What is written into a statement

A query or a statement is text the job wrote. It may name context
variables and entries of globalMap, as text with `${context.name}` in
it, or as Talend joins it (`"... where d = '" + context.d + "'"`). What
such a reference holds is a value, and **no value can change what a
statement does**:

| Where the value stands | What becomes of it |
|---|---|
| in quotes: `where d = '${context.d}'` | it is bound: the database is handed the statement with a name in its place (`:context_d`), and the value beside it |
| in quotes, inside a longer text: `like '%${context.s}%'` | bound, and joined to the rest by the database: `'%' \|\| :context_s \|\| '%'` |
| outside quotes: `from ${context.table}`, `in (${context.ids})` | written into the statement, and it has to be a name, a number, or a list of names, numbers and texts in quotes. Anything else fails the component |
| between the quotes of a name: `"${context.t}"` | written in; it has to be a name |

- A value in quotes is bound as text, whatever it holds: a quote in it
  is a quote.
- **A statement that is nothing but one reference** (`context.sql`) is
  what that holds, as it is: the job says "run what this holds".
  References inside it are not read.
- **A statement that defines** (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`
  and the like) takes no bound value in Oracle. There a value in quotes
  is written as text with its quotes doubled, which Oracle reads as
  that text and nothing else.
- **A statement is read as its own database reads one.** For SQL Server
  a bound value is a mark (`?`) and texts are joined with `+`; a name
  may stand between square brackets (`[it's]`), and a remark inside a
  remark ends only itself. A value outside quotes may be a name that
  starts with `_` or `#`. No statement of SQL Server's takes its values
  as text: every one binds.
- **A text written `N'...'` keeps its `N`** on both sides of a value
  that is bound into it. (Without it SQL Server keeps of the rest only
  what its own set of characters has.)
- What a log shows of a statement, and what is left in `<id>_QUERY`,
  has the names of its values (for SQL Server their marks) and never a
  value. A failure says which reference it is about, and not what it
  holds.
- Java that is more than joining (`TalendDate.formatDate(...)`) refuses
  the job when it loads. So does a name in double quotes next to a
  `+`, which looks the same: write it another way round.
- A reference written `${context.name}` has to be there. Written bare
  in plain text (`context.name`) and not there, it is left as it is:
  it may be a column of a table called `context`.

## Oracle connection

- Opens a session and keeps it for the components that name this one.
  The job closes it when it ends, if nothing else did.
- Leaves in globalMap what Talend leaves there, save the password and
  the session itself: `connectionType_<id>`, `dbschema_<id>`,
  `username_<id>`, and by `connection_type` either `host_<id>`,
  `port_<id>` and `dbname_<id>`, or `localServiceName_<id>`, or
  `rac_url_<id>`.
- `auto_commit` stores what a subjob did on the session when that
  subjob has succeeded, with no commit component. (Talend stores after
  each statement. Here a subjob that fails stores nothing, also with
  this on.)
- Run again while its earlier session is still open, it closes that one
  and opens another; with work still waiting on the earlier one it
  fails, and the work stays where it was.
- `tDBConnection` is this component.

## Oracle commit

- Stores what was done on the session of the connection it names, and
  closes the session unless `close` is off.
- Set off by a trigger, it commits when its turn comes.
- With a flow leading to it, it commits once, when its subjob has
  succeeded and a row reached it. The rows go on as they came. (Talend
  commits at the first row, while the others are still on their way.)
- A session that is not open fails it: a commit that stores nothing is
  a job that stored nothing.

## Oracle rollback

- Takes back what was done on the session and not stored, and closes the
  session unless `close` is off.
- Set off by a trigger or standing in a flow, as the commit.
- A session that is not open has nothing to take back, and is no fault.

## Oracle close

- Closes the session of the connection it names.
- **Work that waits on the session fails the job and is rolled back.** A
  close is no commit. Talend's close stores such work, so a close in a
  job's clean-up stores the half of a job that failed.
- `uncommitted` says otherwise: `commit` stores the work, `rollback`
  takes it back and goes on, `fail` is what happens without it.
- A session that is not open is no fault.

## Oracle input

- Reads the rows of `query`. **The query is run once.** Its rows are
  written to a scratch file a batch at a time, and the engine reads the
  file: however often it reads a source again (a second attempt, the
  search for a row at fault, a run for a few rows), the database is
  asked once, and what it handed back is one moment's rows.
- It reads on the session of the connection `connection` names when
  `use_existing_connection` is on. Without it, it opens a session with
  its own connection block and closes it when the rows are in.
- **Columns are taken by their place**, as in Talend: the first column
  of the query is the first declared column, whatever either is called.
  A query that hands back more or fewer columns than are declared fails
  before it is run.
- **The database converts each column to its declared type**, and the
  driver is asked for exactly that. (Left to itself the driver hands on
  a `NUMBER(20)` as a float.)

  | The query hands back | Declared as | What arrives |
  |---|---|---|
  | a number | `Decimal` | every digit, rounded to the declared places as Oracle rounds (2.345 is 2.35); one too wide fails the query |
  | a number | `int` | cut to a whole number; one too large for 64 bits fails the query |
  | a number | `float`, `bool` | the float; false for 0 and true for any other |
  | a number | `str` | its digits, with a point: `0.5`, `-0.25` |
  | a date | `datetime`, `date` | to the millionth of a second; the day |
  | a date | `str` | `2024-01-31 13:14:15`, with six places more for a `TIMESTAMP` |
  | text | `str` | as it is; a `CHAR` comes padded, and a `CLOB` whole |
  | text | anything else | read as the text of a file is, by the column's pattern; a value that is none of its type fails the job and names the row, or leaves by the reject output with `die_on_error` off |
  | a date with a time zone | `str` | `2024-01-31 13:14:15.500000 +05:30` |
  | a date with a time zone | `datetime`, `date` | refused: a `datetime` has no zone. The failure gives the two ways to say which clock is meant: `sys_extract_utc(...)`, or `cast(... as timestamp)` |
  | a number as a date, a date as a number | | refused |
  | `RAW`, `BLOB`, `LONG`, `XMLTYPE` and others | | refused: turn it into text, a number or a date in the query |

- An empty text is a missing value: Oracle has it so. `no_null_values`
  makes a missing text column empty text.
- `trim_all_column` strips every text column of surrounding blanks, and
  `trim_column` the columns it names.
- `use_cursor` with `cursor_size` says how many rows a round trip
  brings; without it, 50,000.
- The rows come in the order the database hands them: with an `ORDER BY`
  in the query, in that order, as Oracle works such a query out today.
  (The query is given to Oracle inside another that converts its
  columns, with its own `WITH`, hints and `ORDER BY` as they are.)
- The query is left in `<id>_QUERY` as it was sent. A failure names a
  row as `row 3 of the result of <id>`.
- Scratch space is needed for about the size of the rows (they are kept
  compressed), in the folder `V2_TEMP_DIR` names.

## Oracle output

- Stores the rows it is handed in `table`. **The rows rest in a scratch
  file while the subjob runs**, and are sent to the table when the
  whole subjob has succeeded: for a subjob that fails, no statement is
  sent at all. They go in batches, one round trip for `batch_size` rows
  (10,000 without `use_batch_size`), inside a transaction.
- On the session of a connection (`use_existing_connection`) the rows
  then wait for a commit component. With a session of its own the
  output opens it at that last moment, and the engine stores the rows
  in one commit when the subjob is done. `commit_every` is read and
  changes nothing: there is no commit in the middle of a load.
- The columns stored are the declared ones, by their names, which are
  the table's column names. The table is `table`, in `schema_db` when
  the component names one (`table_schema` and `dbschema` are taken for
  the same key), else in the schema of its connection. Names are
  written without quotes, as Talend writes them, and have to be names
  Oracle takes that way.
- **`data_action`**:

  | Value | What a row does |
  |---|---|
  | `INSERT` | is inserted |
  | `UPDATE` | updates the row with its key; a key that is not there changes nothing |
  | `DELETE` | deletes the row with its key |
  | `UPDATE_OR_INSERT`, `INSERT_OR_UPDATE` | updates the row with its key, and is inserted when there is none |

  The key is the columns the schema marks as `key`. The two last come
  to what a job that handled its rows one by one would come to, also
  where one key comes twice in the rows: the first is inserted and the
  others update it, in their order. It takes two or three round trips
  for a batch, and not one for a row.
- A key the table holds as a `DATE` is compared as a date. Handed a
  value with a fraction of a second, Oracle would turn the column into
  such values row by row and use no index on it.
- **`table_action`**:

  | Value | What is done first |
  |---|---|
  | `NONE` | nothing |
  | `CLEAR` | every row is deleted, in the same transaction: taken back with the rows when the subjob fails |
  | `TRUNCATE`, `TRUNCATE_REUSE_STORAGE` | the table is truncated |
  | `CREATE`, `CREATE_IF_NOT_EXISTS` | the table is made from the declared columns |
  | `DROP_CREATE`, `DROP_IF_EXISTS_AND_CREATE` | the table is dropped and made again |

  All but the first two are statements that define. They are run at the
  last moment, when the rows are known to be whole, so a subjob that
  fails before that has touched nothing. **Oracle does not take them
  back**: a load that fails after a `TRUNCATE` leaves the table empty.
  They are refused on a session with work that waits, which Oracle
  would store with them: put a commit before the output, or use `CLEAR`.
- A table that is made gets its types from the declared columns, which
  say no more of them than this:

  | Declared | In the table |
  |---|---|
  | `str` | `VARCHAR2(n CHAR)` for a length up to 4000, 4000 with none; `CLOB` beyond |
  | `int` | `NUMBER(19)`, or `NUMBER(n)` with a length |
  | `Decimal` | `NUMBER(length, places)`; `NUMBER(38, places)` with places only; `NUMBER` with neither |
  | `float`, `bool` | `BINARY_DOUBLE`, `NUMBER(1)` |
  | `datetime`, `date` | `TIMESTAMP(6)`, `DATE` |

  A column that may not be missing is `not null`, and the key columns
  are the primary key.
- A value is bound as the kind it arrives as: a number as a number, a
  date as a date, text as text. The database turns it into the column's
  own kind, or refuses the row. An empty text is a missing value in
  Oracle. A date into a `DATE` loses its fraction of a second.
- **A row the database refuses fails the job**, names the row by its
  place among the rows the output was handed and by its key, and says
  what Oracle said: `the database refused row 2 of the rows it was
  handed (ID=1): ORA-00001: ...`. Nothing is stored.
- **With `die_on_error` off** such a row is left out and the others are
  stored. One warning says how many were refused and what was wrong
  with the first, and the same is in `<id>_ERROR_MESSAGE`. When the
  output cannot do its work at all (no session, no table), what it did
  is taken back, the job goes on, and nothing is stored by it. A
  converted job nearly always says off: it is Talend's default.
- It leaves in globalMap: `<id>_NB_LINE` (the rows it was handed),
  `<id>_NB_LINE_INSERTED`, `_NB_LINE_UPDATED`, `_NB_LINE_DELETED`,
  `_NB_LINE_REJECTED`, and the engine's `_NB_LINE_OK` and
  `_NB_LINE_REJECT` when something reads them.
- No flow leaves it: the rows that were refused cannot be handed on yet.
- Refused when on: `use_field_options` (the schema's `key` says which
  columns are keys) and `use_hint_options`.
- Scratch space is needed for about the size of the rows, compressed.

## Oracle row

- Runs the one statement `query` holds. What it is and what its values
  are is under [What is written into a statement](#what-is-written-into-a-statement).
- **Set off by a trigger, it runs the statement once.** What it changed
  waits on the session of its connection for a commit component; with a
  session of its own it is stored when the component is done.
- **With a flow leading to it, it runs the statement once for each
  row**, a batch of rows in one round trip, and hands the rows on as
  they came. The rows are held in memory while it runs: it is for
  thousands of rows, and an output is for millions.
  - Where the statement is joined, it may name a column of the row:
    `"delete from t where id = " + row1.id`. A value of a row is always
    bound, in quotes or out of them: the statement is one, and the rows
    are its values.
  - A prepared statement (`use_preparedstatement`) has a mark (`?`) for
    each entry of `set_preparedstatement_parameters`, in their order.
    An entry's value is text or a number, a context variable, an entry
    of globalMap, or a column of the row (`row1.id`); `parameter_type`
    says what a written value is made into (`String`, `Int`, `Long`,
    `Double`, `Float`, `BigDecimal`, `Boolean`, `Date`, `Timestamp`,
    `Null`). A column of the row is bound as it is.
  - A row the database refuses fails the job and names the row
    (`line 3 of in.csv`); with `die_on_error` off the others are done,
    and one warning says how many were refused.
- **A statement that defines** (`CREATE`, `ALTER`, `TRUNCATE`...) is
  stored by Oracle at once, with whatever waited on the session. It is
  refused on a session with work that waits, and is not run for each
  row of a flow.
- A block of PL/SQL that commits, or defines, also stores what waited.
  That cannot be seen before it runs. When it has happened, a warning
  says whose work was stored that way.
- **With a flow from it and none to it, it hands on one row with
  nothing in it**, as Talend does: what the flow leads to runs once. A
  commit that follows by a flow stores what the statement did.
- With `die_on_error` off a statement the database refuses is said in a
  warning and in `<id>_ERROR_MESSAGE`, and the job goes on.
- A query, or a statement that found no row to change, leaves nothing
  waiting for a commit. What a block of PL/SQL changed cannot be seen,
  and counts as work that waits.
- It leaves the statement in `<id>_QUERY` as it was sent, with the
  names of its values and no value. `use_nb_line` names the entry that
  takes the number of rows it changed: `<id>_NB_LINE_INSERTED`,
  `_NB_LINE_UPDATED` or `_NB_LINE_DELETED`.
- Refused when on: `propagate_record_set` (a query's rows are read with
  an input). A `Blob`, `Clob`, `Bytes` or `Time` for a mark is refused.

## Oracle stored procedure

- Calls the procedure or function `sp_name`: a name, with its package or
  schema before a dot.
- **Set off by a trigger, it calls it once**, with nothing handed in.
  **With a flow leading to it, it calls it once for each row**, 10,000
  calls in one round trip. The rows are held in memory meanwhile.
- `sp_args` names the arguments in the procedure's own order:

  | `type` | What happens |
  |---|---|
  | `IN` | the value of the row's column `column` is handed in |
  | `OUT` | what comes out goes into the column `column` |
  | `INOUT` | both |

  With `is_function`, what the function returns goes into
  `return_column`.
- The rows go on with what came out in their columns. With no flow to
  it and one from it, it hands on one row.
- **A number comes out with every digit it has** and is rounded to its
  column's places; a date into a `date` column is its day. `dbtype`
  says what a value that comes out is when the column's own type does
  not: `DECIMAL`, `NUMERIC`, `DATE`, `TIMESTAMP`, `CLOB`. A true/false
  is handed in as 1 or 0: PL/SQL's own true/false is no number.
- **A call counts as work that waits.** What a procedure changed cannot
  be seen from outside, so on the session of a connection a commit
  component has to follow, or the connection has `auto_commit`; with a
  session of its own the engine stores when the subjob is done. A
  procedure that commits by itself stores what waited on the session
  too, and a warning then says whose work that was.
- A call that fails fails the job, with Oracle's words and the row
  (`line 2 of in.csv`). The calls before it in the same subjob are
  rolled back with it.
- `nls_language` and `nls_territory` set the session's before the first
  call, when they are not `NONE`.
- Refused when the job loads: a `RECORDSET` argument (a cursor that a
  procedure hands out is not read; read its rows with an input), a
  STRUCT or an ARRAY (`is_custom`), and a `BLOB`, an `XMLTYPE` or a
  `TIMESTAMP_WITH_TIMEZONE` that comes out.

## Oracle bulk exec

- Stores the rows of a file in `table`. **With no flow leading to it**,
  as in Talend, it reads the file `data` itself: delimited text, a line
  a row, `terminator_value` between the fields, read as every delimited
  file is, by the declared columns and their patterns. **With a flow
  leading to it** it stores that flow's rows and reads no file.
- **Nothing of Oracle's is run.** Talend's component runs SQL*Loader,
  which needs Oracle's client on the machine and the password on a
  command line. Here the rows are stored as the
  [Oracle output](#oracle-output) stores them: in batches, inside a
  transaction, when the whole subjob has succeeded; on a connection's
  session they wait for a commit.
- A line that cannot be read as its declared types fails the job, names
  the line, and nothing is sent to the database.
- **`data_action`** has SQL*Loader's meanings:

  | Value | What becomes of the rows the table holds |
  |---|---|
  | `INSERT` | there may be none: a table that holds rows fails the job |
  | `APPEND` | they stay, and the file's rows are added |
  | `REPLACE` | they are deleted first, in the same transaction: taken back with the rows when the subjob fails |
  | `TRUNCATE` | the table is truncated first, which Oracle does not take back |
  | `UPDATE` | refused: a load updates no rows; an Oracle output does |

  `table_action` is the Oracle output's, and comes first.
- `use_fields_enclosure` lets a field stand in double quotes, so that it
  can hold the terminator or a line end. `encoding` is the file's, by
  Oracle's name (`UTF8`, `WE8ISO8859P15`, `WE8MSWIN1252`) or Python's.
- Of the load options (`options`, a name and then its value):

  | Option | What it is here |
  |---|---|
  | `ROWS` | the rows a round trip takes; 10,000 without it |
  | `SKIP` | lines left out at the start of the file |
  | `LOAD` | the most rows read |
  | `ERRORS` | how many rows the database may refuse before the job fails |
  | any other (`DIRECT`, `BINDSIZE`, `PARALLEL`...) | read and without effect: it tunes a loader that is not run |

- **Without `ERRORS`, the first row the database refuses fails the
  job.** (SQL*Loader lets fifty pass and writes them to a file nobody
  reads.) With it, that many are left out and told in one warning; one
  more fails the job. `die_on_error` off leaves out any number.
- It leaves in globalMap: `<id>_NB_LINE_DATA` (the rows it was handed),
  `<id>_NB_LINE_BAD` (those the database refused), `<id>_NB_LINE_INSERTED`,
  and `<id>_RETURN_CODE`: 0, or 2 when rows were refused.
- A value is stored as the file holds it: blanks at its ends are kept.
- Refused when on: `advanced_separator` (numbers with other separators),
  `use_existing_clt_file` and `input_into_table_clause` (a control file
  of SQL*Loader's), a `record_format` other than `DEFAULT`, and a
  `fields_terminator` other than `OTHER`.

## SQL Server connection

- Opens a session and keeps it for the SQL Server inputs that name this
  one. The job closes it when it ends.
- Every statement on it is stored by itself; see
  [SQL Server](#sql-server). `auto_commit` is read and changes nothing.
- Leaves in globalMap what Talend leaves there, save the session
  itself: `dbschema_<id>` and `db_<id>`.
- A component of Oracle's cannot work on its session, nor a SQL Server
  input on an Oracle connection's: the job is refused.

## SQL Server input

- Reads the rows of `query`. **The query is run once, as it is
  written**: with its `ORDER BY`, its `WITH`, or as the call of a
  procedure (`exec dbo.orders_of '${context.day}'`). Its rows are
  written to a scratch file a batch at a time, and the engine reads the
  file: however often it reads a source again, the database is asked
  once.
- It reads on the session of the connection `connection` names when
  `use_existing_connection` is on. Without it, it opens a session with
  its own connection block and closes it when the rows are in.
- **Of what a statement hands back, the first thing that has columns
  is read.** What comes before it is passed over (the count of rows a
  procedure changed, a `PRINT`). What comes after it is passed over too,
  and said in the log when it has columns; a failure after the rows
  fails the job. A statement that hands back nothing with columns
  fails: it was run, and an input reads.
- **Columns are taken by their place.** A query that hands back more or
  fewer columns than are declared fails. It has been run by then: SQL
  Server says what a query hands back only when it runs it.
- **Each column is made what the job declares, the way SQL Server's own
  `CAST` would.** Nothing is written round the query to do it (SQL
  Server takes no `ORDER BY`, no `WITH` and no procedure call inside
  another query), so v2 converts what the driver hands out.

  | The query hands back | Declared as | What arrives |
  |---|---|---|
  | a number | `int` | cut off at its point: 2.7 is 2, -2.7 is -2 |
  | a number | `Decimal` | every digit, rounded to the declared places, a half going away from nought (2.675 is 2.68) |
  | a `float` or `real` | `Decimal` | by the number the float exactly is: 2.675 is 2.67, 0.125 is 0.13 |
  | a number | `float`, `bool` | the nearest float; false for 0 and true for any other |
  | a number | `str` | as the database holds it: `1.50` for a `decimal(9,2)`, `1` or `0` for a `bit`; a float as v2 writes one (`1.5`, `1e+22`) |
  | a number too large for what is declared | | fails the job and names the row: `row 3 of the result: column 2 holds ...` |
  | `date` | `date`, `datetime`, `str` | the day; midnight of it; `2024-01-31` |
  | `datetime`, `datetime2`, `smalldatetime` | `datetime`, `date` | to the millionth of a second; the day |
  | the same | `str` | `2024-01-31 13:14:15`, with the digits after the second that the type has: three for a `datetime`, none for a `smalldatetime`, up to six for a `datetime2` |
  | text, `uniqueidentifier`, `xml` | `str` | as it is; a `char` comes padded, a `varchar(max)` whole, a `uniqueidentifier` in capitals |
  | `time` | `str` | `13:14:15.1234567`, with the digits its type has |
  | text or a `time` | anything else | read as the text of a file is, by the column's pattern; a value that is none of its type fails the job and names the row, or leaves by the reject output with `die_on_error` off |
  | `datetimeoffset` | | refused: the driver hands it on without its zone. The failure gives what to write in the query: `convert(varchar(34), c, 121)` for its text, `cast(c at time zone 'UTC' as datetime2)` for its clock in UTC |
  | `binary`, `varbinary`, `image`, `rowversion`, `sql_variant`, `hierarchyid`, `geography` | | refused: turn it into text in the query (`convert(varchar(max), c, 2)` writes binary data as hexadecimal digits) |
  | a number as a date, a date as a number | | refused |

- **A `datetime2` is cut to the millionth of a second**, not rounded:
  the driver hands on no more. (`cast(c as datetime2(6))` in the query
  rounds.)
- **A value bound from plain ASCII text reaches SQL Server as
  `varchar`, any other as `nvarchar`.** Compared with a `varchar` key
  column, the first seeks the index as a text in quotes does. The
  second reads all of it, as an `N'...'` text does.
- An empty text is empty text, and a missing one is missing: SQL Server
  tells them apart. `no_null_values` makes a missing text column empty
  text.
- `trim_all_column` strips every text column of surrounding blanks, and
  `trim_column` the columns it names.
- `set_query_timeout` with `query_timeout_in_seconds` says how long the
  query may take before its first rows come; one that takes longer
  fails the job.
- `use_cursor` with `cursor_size` says how many rows a round trip
  brings; without it, 50,000.
- **Rows may be of more than one moment.** SQL Server reads a table
  that is being changed row by row, unless the database is set to read
  committed snapshot, or the query says its own isolation first
  (`set transaction isolation level snapshot; select ...`, where the
  database allows it). What a query sets holds for the session: on a
  connection's, for the inputs that read after it too.
- The rows come in the order the database hands them: with an `ORDER BY`
  in the query, in that order.
- The query is left in `<id>_QUERY` as it was sent, with a `?` where
  each bound value goes. A failure names a row as
  `row 3 of the result of <id>`.
- Scratch space is needed for about the size of the rows (they are kept
  compressed), in the folder `V2_TEMP_DIR` names.

## What refuses the job

- `connection` on a commit, a rollback or a close has to be the id of an
  Oracle connection of the job. The refusal lists the ones it has.
- `connection` on a SQL Server input has to be the id of a SQL Server
  connection of the job.
- For SQL Server: signing in any other way than with a user and a
  password, and a JDBC parameter v2 has no reading for.
- What is wrong with a connection block: no host, no user, a password
  only Talend can read.
