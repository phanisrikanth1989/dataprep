# 126 - SQL Server connection and input

Status: resolved
Type: task

## Question

Build the SQL Server connection (`MSSqlConnection`, `tMSSqlConnection`)
and the SQL Server input (`MSSqlInput`, `tMSSqlInput`), behind the seam
the Oracle components stand on. To
[Databases: the decisions](118-databases-the-decisions.md).

## What is known

Tried on 2026-10-12 against SQL Server 2022 (16.0.4295, CU27) in a
container on this Mac, with Microsoft's `mssql-python` 1.15.0. The
image is for Intel only and ran here under emulation; it came up in a
few seconds and held for every probe.

**The driver**

- It installs with no system package and hands a result out as Arrow
  batches (`cursor.arrow_batch`).
- Numbers come whole: a `decimal(38,10)` as a decimal of 38 digits,
  `money` as a decimal of four places, `tinyint` unsigned, `bit` as a
  true/false.
- A `datetime2(7)` is cut to the millionth of a second.
- A `datetimeoffset` comes as its moment in UTC. Its offset is gone.
- `sql_variant` stops the Arrow path (`RuntimeError`, no driver error).
  Binary kinds, `hierarchyid` and `geography` come as bytes.
- A text of plain ASCII is bound as `varchar`, any other as `nvarchar`.
  So a bound value compared with a `varchar` key still seeks its index.
- It pools sessions unless told not to: a session that was closed
  stays at the server, for ten minutes. With pooling off a close ends
  it; the server shows it a few milliseconds more while it takes it
  down.
- The program name a session shows is `MSSQL-Python`, and the driver
  takes no other.
- No failure it reports repeats the password. All are one line.
- **An error that comes while rows are fetched has lost its reason**:
  a division by nought in row 3 comes as `Unknown DDBC error`. So does
  a session the server ends.
- **Its row-by-row path ends such a result without a word**, as if the
  query had two rows. v2 does not use that path.
- An error after the rows of a procedure (`THROW`) is seen only when
  the rest of what the statement hands back is asked for.

**SQL Server**

- A query cannot be wrapped as Oracle's is: no `ORDER BY` and no `WITH`
  inside a derived table, and a procedure call cannot stand in one.
- Its own conversions, asked of the server: to a whole number it cuts
  (2.7 to 2, -2.7 to -2); to fewer places it rounds a half away from
  nought (2.675 to 2.68); a float goes by the number it exactly is
  (2.675 to 2.67, 0.125 to 0.13).
- `"abc"` is a name, `[abc]` is a name, remarks nest, `q'[...]'` is
  not known. A text without its `N` loses what its code page lacks:
  `? + '<two Japanese letters>'` came back as `p??`.

**Talend** (Talaxie at 639d5fd1f776)

- An empty port leaves the port out of the URL
  (tMSSqlInput_begin.javajet L72-74).
- `properties` is put after the URL behind a `;`, and the input's own
  default for it is `noDatetimeStringSync=true`
  (tMSSqlInput_java.xml L232-234), which is MySQL's.
- The connection leaves `dbschema_<id>` and `db_<id>` in globalMap
  (tMSSqlConnection_begin.javajet L75-77).

## To build

1. `src/v2/statements.py`: a statement is read as its database reads
   it. For SQL Server: `[names]`, remarks that nest, no `q'...'`, a
   name that may start with `_` or `#`. For both: a text written
   `N'...'` keeps its `N` where a value is bound into it.
2. `src/v2/mssql.py`: the connection block, what is wrong with one,
   what the driver is given, and a session that runs a query once and
   hands its rows on as the job declares them.
3. `src/v2/components/database/mssql_connection.py` and
   `mssql_input.py`.
4. The extra `v2-mssql`, the docs, the README rows.

## How it is tested

- What needs no database (the block, the words of a failure, each
  conversion) as what it is: text and Arrow tables shaped as the real
  driver's were seen to be.
- The session against a stand-in driver that answers as the real one
  was seen to answer.
- The two components on SQLite behind the seam, as the Oracle ones.
- Against a real SQL Server (marked `mssql`, not in the gate): every
  type, each conversion beside the server's own, and jobs.

## Answer

Built on 2026-10-12.

- `src/v2/statements.py`: a statement is read as its own database reads
  one. For SQL Server a bound value is a mark (`?`), texts are joined
  with `+`, a name may stand in square brackets, a remark inside a
  remark ends only itself, and a name may start with `_` or `#`.
- `src/v2/mssql.py`: the connection block, what is wrong with one, what
  the driver is given, and a session that runs a query once and hands
  its rows on as the job declares them.
- `src/v2/components/database/mssql_connection.py`, `mssql_input.py`.
  The input is the Oracle input's base with another session.
- `src/v2/sessions.py` now holds what Oracle and SQL Server share: the
  two keys that say whose session a component works on, and a few
  words of their messages.
- The extra `v2-mssql`, the test marker `mssql`.
- Docs: "SQL Server", "SQL Server connection" and "SQL Server input"
  in `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **The query is run as it is written, and nothing is wrapped round
  it.** So a query with an `ORDER BY`, a `WITH` or a procedure call
  works. The price: its columns are known only once it has run. A
  query whose columns do not go with the declared ones has been run
  when the job fails on that.
- **v2 converts on its side, the way SQL Server's own `CAST` does.**
  Each conversion was held beside the server's own in one query, row
  by row (15 pairs, 16 values each).
- **Of what a statement hands back, the first thing with columns is
  read.** What comes before is passed over. What comes after is drawn
  to its end, so that a failure there fails the job; more rows there
  are said in the log and not read. Talend reads the first and never
  looks further.
- **A statement with no rows to read fails, and has been run by then.**
- **Every statement is stored by itself.** v2 has nothing that commits
  on SQL Server. `auto_commit` is read and changes nothing.
- **`datetimeoffset`, binary kinds and `sql_variant` refuse**, each
  with what to write in the query instead. The three ways the failure
  names were run against the server and work.
- **A `time` is read as text.** A job declares no time of day.
- **Encrypted, and the certificate checked, when nothing says
  otherwise.** That is Microsoft's own default since 2022. Talend jobs
  on the older jTDS driver had neither.
- **Six of Talend's JDBC parameters are read**, six are passed over,
  any other refuses the job by its name. A value is never shown.
- **v2 signs in with a user and a password.** Microsoft Entra and
  Kerberos refuse the job: neither could be tried here.
- **The driver's pooling is turned off**, unless the process set it.
- **Tests start a container only when `V2_MSSQL_ACCEPT_EULA=Y` is
  set.** The image needs Microsoft's licence accepted, and that is for
  whoever runs the tests to do.
- Not built: a key for the isolation (a query can say its own), and
  anything at job level (`mssql_config` is still read and passed over).

### Slips from the decisions

- **The decisions said a session names the job to the database. It
  cannot.** The driver sets the program name and takes no other.
- The decisions named a seam of two functions. It is the Oracle one,
  of four (`bound`, `fields`, `typed`, `batches`).

### Found on the way

- **A text written `N'...'` with a value in it was read wrongly, for
  Oracle too.** `N'${context.x}'` failed (ORA-00923), and after a value
  the rest of the text lost its `N`. This was in what tickets 121 to
  125 built, none of it pushed. Fixed; the test was seen failing
  against the real Oracle first.
- **Arrow's own cast of a decimal to a float is a step off for about
  one value in nine** (21,926 of 192,093 tried). v2 goes through the
  digits, which was right for all, as SQL Server's own cast was for
  400 of 400.
- **Arrow's cast of a float to a decimal sends an exact half to the
  even digit; SQL Server sends it away from nought.** v2 finds the
  exact halves and rounds them again.
- **My first reading of the pooling was wrong**: I took a closed
  session for kept until Python let go of it. It is gone in about 15
  milliseconds; I had looked too soon. Measured with the collector off.

### How it was tested

- 23 tests of the statement reader. 22 were seen failing first; one
  came after I saw a hole in my own change, and was seen failing.
- 173 tests of the module, against a stand-in driver. They were
  written before the module and failed as a whole for want of it. **Not
  seen failing one by one**: 165 passed on the first run with the
  module. Eight came later, with the mutation check and the reread,
  and some lines in earlier ones; two of these were seen failing.
- 41 tests of the two components, on SQLite: 40 seen failing first.
- 60 tests against the real server, written after the code. 59 passed
  at first; the one that did not was the test's own fault.
- The fixture was run both ways: against a server that was there, and
  starting a container of its own (24 seconds for three tests).

### Mutation check

141 ways of breaking it. 137 were caught at first. Of the four others:

- **Two got a stronger test**: an exact half at 31 places, and the
  seconds a query is given when none are said.
- **Two showed code that did nothing, and it went**: a short cut for a
  column that needs no converting, and a widening of short floats.

All were run again, less the two for the code that went and with
three more for what the reread changed: 142, all caught.

### Speed and memory

On this Mac, the server under emulation:

- 10 million rows of six columns read into the scratch file in 13
  seconds, with 158 MB at the most. At 2 million it was 157 MB.
- As a whole job (query to CSV file) the same rows took 14 seconds and
  858 MB. That growth is the engine's pass, as for any reader, and was
  told before. (**That was wrong**, as
  [A database input's memory grew with its rows](128-a-database-inputs-memory-grew-with-its-rows.md)
  found: it was the layout of the scratch file, now changed.)

**For the user's eye**

- **Microsoft's driver has two faults** (mssql-python 1.15.0), worth
  telling Microsoft:
  1. An error that comes while rows are fetched has lost its reason on
     the Arrow path. v2 then says how many rows were read and that the
     driver gave no reason.
  2. Its row-by-row path (`fetchmany`) ends such a result without a
     word, as if the query had fewer rows. v2 does not use that path.
- **A SQL Server with a certificate of its own making will refuse
  every job** until the job says `trust_server_certificate: true` (or
  `encrypt: no`). The failure says so.
- **If the SQL Servers take only Windows or Kerberos sign-in, v2
  cannot sign in.** It is one more key, and has to be tried where
  there is a ticket.
- A named instance (`server\instance` with no port) is passed to the
  driver as Microsoft documents it. Not tried: none was at hand.
- Not tried on RHEL. The driver needs glibc 2.28 and the packages
  `libtool-ltdl` and `krb5-libs` there.
- The server here was SQL Server 2022 under emulation, which Microsoft
  does not support. It held for every run.
- I accepted Microsoft's licence for the SQL Server image and for the
  driver on this machine, to try them.
