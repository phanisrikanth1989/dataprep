# SQL Server

The two components that read from a SQL Server database: a connection
and an input.

Built to their own rule: what is written here is what they are held to,
not v1 or Talend. ([What that means](README.md).) What they share with
the Oracle components is on [Databases](databases.md): above all
[what is written into a statement](databases.md#what-is-written-into-a-statement),
which says what becomes of a context variable in a query. Why each rule
is as it is, and what a real SQL Server said when it was tried, is in the
ticket (`.scratch/engine-v2/issues/126-sql-server-connection-and-input.md`).

## The driver, a session and the connection block

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

## SQL Server connection

- Opens a session and keeps it for the SQL Server inputs that name this
  one. The job closes it when it ends.
- Every statement on it is stored by itself; see
  [above](#the-driver-a-session-and-the-connection-block). `auto_commit` is read and
  changes nothing.
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

- `connection` on an input has to be the id of a SQL Server connection of
  the job. The refusal lists the ones it has.
- Signing in any other way than with a user and a password, and a JDBC
  parameter v2 has no reading for.
- What is wrong with a connection block: no host, no user, a password
  only Talend can read.
