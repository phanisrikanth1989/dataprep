# Databases

The components that open a session with a database, work in it, and end
what was done.

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
- What a log shows of a statement, and what is left in `<id>_QUERY`,
  has the names of its values and never a value. A failure says which
  reference it is about, and not what it holds.
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

## What refuses the job

- `connection` on a commit, a rollback or a close has to be the id of an
  Oracle connection of the job. The refusal lists the ones it has.
- What is wrong with a connection block: no host, no user, a password
  only Talend can read.
