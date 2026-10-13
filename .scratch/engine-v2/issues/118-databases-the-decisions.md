# 118 - Databases: the decisions

Status: resolved
Type: decision

## Question

What are the eleven database components built to: Oracle connection,
input, output, row, stored procedure, bulk exec, commit, rollback and
close, and the MSSQL connection and input? The rule is
[Thirty more, future-ready](87-thirty-more-future-ready-the-decisions.md):
not Talend or v1 parity, built for long use, and a converted job config
still loads.

## What is known

From [How current tools read and load databases](92-how-current-tools-read-and-load-databases.md)
(`research/2026-10-12-databases.md`, every finding with its source). The
ones the design turns on:

- A direct path load always commits. It cannot be the way of an engine
  that stores rows only when the subjob has succeeded.
- Closing a connection with work pending commits it in Talend (JDBC)
  and rolls it back in python-oracledb. It has to be decided.
- A table action (truncate, create, drop) is DDL, and DDL commits.
  Truncate-then-insert cannot be all or nothing in Oracle.
- A reader that runs its query inside the plan runs it again for every
  later reading; this engine reads a source again by design (to find
  the component at fault, to count dropped rows, for a run of a few
  rows).
- python-oracledb's default types lose data (a NUMBER with places
  arrives as a float); the types have to be asked for.
- Its Arrow path is young: wrong decimals across batches and lost dates
  in 26.0.0, fixed in 26.0.1. The repo pins `oracledb>=2.5,<4`.
- Thin mode has no Native Network Encryption and no Kerberos; thick
  mode has no direct path load; a process is one of the two.
- The converter cannot convert eight of the eleven today (a method it
  calls does not exist), and a query built from context variables
  reaches a job config as Java text with no mark.
- The research ran nothing against a database: no driver was installed.
  That was done after it; what the database said is the next part.

## What the real database said

Tried on 2026-10-12 with python-oracledb 26.0.1 in thin mode against
Oracle 23.26.3 in a container (`gvenzl/oracle-free:23-slim-faststart`).
Each line is what was seen, not what a page says.

Reading:

- **Left to itself the driver loses data.** `NUMBER(20)` and
  `NUMBER(10,2)` arrive as floats, a `DATE` as whole seconds, and a
  `TIMESTAMP WITH TIME ZONE` as the clock of its own zone with the zone
  gone.
- **Asked for a decimal, it does not round and it can wrap.** A value
  with more places than asked for fails (DPY-4042). A value too wide
  for 128 bits at the places asked for comes back as another number,
  without a word: `1234.5` asked for as 36 places was not `1234.5`.
  Asked for as a whole number, `1234.50` came back as `1234`.
- **The database converts rightly.** The query wrapped as
  `with v2q (c1, c2) as (<the query>) select cast(c1 as number(38, 2)),
  ... from v2q` rounds as Oracle rounds, fails loudly on a value too
  wide (ORA-01438), and keeps the query's own `WITH`, binds, hints,
  `UNION ALL` and `ORDER BY`. A query with fewer or more columns than
  the job declares fails (ORA-32038). `FOR UPDATE` inside it fails.
- `cursor.parse` says what a query's columns are before it runs, and
  needs no value for its binds.
- An empty text is a missing value (`''` is NULL). A CLOB of 100,000
  characters arrives whole. A `CHAR` arrives padded.

Loading:

- `executemany` takes a Polars frame, an Arrow table or a record batch
  as it is. A `datetime` into a `DATE` loses its fraction of a second,
  cut and not rounded.
- With `batcherrors` every row the database refuses is named with its
  place in the batch and Oracle's own words, and the others are in.
  Without it the rows before the first refused one stay in the
  transaction: they have to be rolled back.
- `arraydmlrowcounts` says for each row of an update how many rows it
  changed (`[1, 0]`): that is how an update that found nothing is told
  from one that did.

Transactions:

- `SAVEPOINT` and `ROLLBACK TO SAVEPOINT` do what they say, and the
  transaction stays open.
- `TRUNCATE` stores whatever was pending on the session
  (`transaction_in_progress` is false after it). So does a PL/SQL block
  that creates a table, as the sample job's does.
- A session closed with work pending loses it. Talend's keeps it.
- Two threads on one session wait for each other. A lock is kept all
  the same.

Statements:

- **A statement that defines takes no bound value.** `CREATE TABLE ...
  AS SELECT ... WHERE v = :v` fails before it is sent (DPY-4008), and
  so does `ALTER SESSION`. The same value written as text with its
  quotes doubled works.
- One bind name may stand twice. A bound value joins text with `||`.
  A name (of a table) cannot be bound.
- A bound value inside the text a block hands to `EXECUTE IMMEDIATE`
  works.
- A trailing `;` is taken. Two statements in one text are not.
- A procedure's values out come back for one call and for many calls
  in one round trip; a cursor out is read as rows. A function's
  `NUMBER` comes back as a float unless asked for otherwise.

Faults of the driver, for whoever builds on it:

- **A session the database has closed brings the interpreter down when
  its `call_timeout` is set** (a segmentation fault; tried one question
  per process). Asking whether it is healthy, rolling back, and closing
  are safe. So a time limit is set once, when the session opens, and
  never again.
- A call that runs out of time ends with the session alive when the
  database could be interrupted (a query), and dead when it could not
  (a block that sleeps).
- A failed connect does not repeat the password.

## The decisions

### How rows cross between the plan and a database

- **Every row rests once in a scratch file.** A source runs its query
  once, writes the result to scratch a batch at a time, closes the
  cursor, and hands the plan a scan of the file. An output lets the
  plan write its rows to scratch in the subjob's pass, and loads them
  when the whole pass has succeeded.
- So a query runs exactly once whatever the engine reads again, the
  result is one point in time, the cursor is closed before any slow
  step, and nothing touches a table until the rows are known to be
  whole. The cost is scratch space of about the size of the rows.

### Transactions

- **One commit, when the subjob has succeeded.** `commit_every` is
  taken and has no effect. A component with a session of its own
  commits when its subjob's files are put in place; database commits
  come before the file moves, since a commit can fail and a move
  almost never does.
- **A shared session** (a connection component, `use_existing_connection`)
  is committed by a commit component, as in Talend. A subjob that fails
  on it is rolled back to where it started; what earlier subjobs did
  stays pending.
- **The engine ends a subjob's transactions, not the components.** A
  component does its work on a session and never commits. When the
  subjob has succeeded the engine commits every session a component
  opened for itself; when it has not, it rolls them back.
- **A commit or a rollback that stands in a flow** acts when its subjob
  has succeeded and a row reached it, once. (Talend acts at the first
  row, while rows are still on their way.)
- **Closing with work pending fails the job and rolls back**, unless
  the close says otherwise (`uncommitted`: `fail`, `commit` or
  `rollback`). Talend's close commits: a close in a postjob then stores
  the half of a job that failed.
- **A job that ends with work pending has failed**, and says so: rows
  that were loaded and not stored are a failure.
- A table action that is DDL (`TRUNCATE`, `CREATE`, `DROP`) runs at the
  last moment, is refused when the session has work pending, and is
  said not to be all or nothing. `CLEAR` is a `DELETE` in the
  transaction, and is.

### What is written into a statement

A query is text the job wrote, and it may name context variables and
globalMap entries, also as Talend joins them (`"... where d = '" +
context.d + "'"`).

- **A value that stands in quotes is bound**, never pasted:
  `'${context.d}'` becomes a bind variable, and inside a longer text
  (`'%${context.s}%'`) it is joined to the rest by the database.
- **A value that stands outside quotes is written into the statement,
  and has to be a name, a number, or a list of those with commas.**
  That is what a table, a schema, a column to sort by or a list for
  `IN` are, and none of them can be bound. Anything else there fails
  the component. So no value can change what a statement does, and the
  statements Talend jobs carry keep their meaning.
- A list outside quotes may hold text in single quotes too
  (`'A','B'` for an `IN`): each item is checked to be one text.
- **A statement that is nothing but one reference is that value**, as
  it is: the job says "run what this holds". References inside it are
  not read.
- **A statement that defines** (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`
  and the like) takes no bound value. There a value in quotes is
  written as text with its quotes doubled, which Oracle reads as that
  text and nothing else.
- The same rule holds for a context variable and for a globalMap entry.
- The statement shown in a log or in `<id>_QUERY` has the names of its
  binds, never their values.

### The driver

- **python-oracledb 26.0.1 or later**, thin mode. `oracle_config.thick_mode`
  at job level asks for thick mode, for a database that needs what thin
  lacks; it is the process's choice, so the first job that asks decides.
- **The database converts each column to the type the job declares**,
  and the driver is then asked for exactly that type: a query is run
  as `with v2q (...) as (<the query>) select cast(...) ... from v2q`.
  The driver's own conversions are not used: they lose data, and one of
  them changes a number without a word.
- A column with a time zone into a `datetime` refuses, with the two
  ways to say which clock is meant: `sys_extract_utc(...)` for UTC, or
  `cast(... as timestamp)` for the value's own zone.
- **SQL Server through a seam of two functions** (open a session; run a
  statement and hand back batches), with Microsoft's own `mssql-python`
  behind it first. The seam is the Oracle one too.

### Secrets

- `password` is a secret on every component that has one. A URL key
  that carries `user/password@` refuses the job, without quoting it.
- Neither the password nor the connection object goes into globalMap,
  which a result hands back. Talend's other entries do
  (`connectionType_<id>`, `dbschema_<id>`, `username_<id>`, `host_<id>`,
  `port_<id>`, `dbname_<id>`).
- Talend's encrypted text (`enc:system.encryption.key.v1:...`) is no
  password v2 can use, and refuses the job with that reason.

### `die_on_error`

Only the output, the row and the bulk exec have it. Off means: a row
the database refuses is left out, counted, and the first is named in
one warning; the rest are stored. What the whole component cannot do
(no session, no table) rolls its work back, warns, and the job goes on.
The other eight have no such key: what they cannot do fails the job.

### Tests

- v1 is not the answer key. A test runs a job on v2 against a real
  Oracle in a container (`gvenzl/oracle-free`, the image v1's own tests
  use) and reads the table back with the plain driver. These are
  marked `oracle` and are not in the coverage gate, as v1's are not.
- What needs no database (keys, refusals, how a statement is read, the
  order of commits) is tested without one, and is what the gate
  measures.
- SQL Server's image runs on Intel only; on this Mac it is emulation
  Microsoft does not support. Tried, and said how it went.

## What the engine has to learn

1. Sessions the run holds: the shared ones by the id of their
   connection component, and the ones a component opened for its
   subjob. The engine tells them when a subjob has succeeded or failed
   and when the job ends; it knows nothing of a driver.
2. A write that is no file: its rows rest in a scratch file of the run,
   nothing is moved, and it may say how many rows were kept. Files are
   made ready before tables are loaded, commits come before file moves.
3. An action that hands on a row of its own (an Oracle row with a flow
   from it and none to it, as Talend has it).
4. A key for statement text, which the loader leaves as written.
5. A folder `src/v2/components/database/`, and an extra for the driver.

## In what order

The seams with the connection, commit, rollback and close; then the
input; the output; the row; the stored procedure; the bulk exec; the
two for SQL Server. A ticket each.

## For the user's eye

- **Which mode the databases need is not known here**: thin (no client
  to install) or thick (Native Network Encryption, Kerberos, wallets).
  Thin is the default; a job says otherwise.
- **The converter cannot convert eight of these eleven today.** The
  keys they are built to are what its source says it writes, and what
  the three committed samples hold. A real converted job may differ.
- Installing the driver and pulling the test database's image were done
  on this machine for this work: `oracledb` 26.0.1 into the project's
  virtual environment, and `gvenzl/oracle-free:23-slim-faststart` into
  Docker.
