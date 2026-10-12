# 129 - Oracle's own client (thick mode), tried

Status: resolved
Type: task

## Question

Every test and every figure of the Oracle components was taken without
Oracle's client software (the driver's "thin mode"). A database may
demand what only that client does: Native Network Encryption, Kerberos.
The docs said of a job that asks for the client: "This was not tried
here: no client was at hand." The dev asked for it to be tried on
2026-10-13.

## How it was tried

- A container of **Oracle Linux 8.10** (the family of RHEL 8, glibc
  2.28) with **Python 3.12**, Oracle Instant Client 23.26 from Oracle's
  own package source, and the packages of the dev's environment at the
  same versions (python-oracledb 26.0.1, polars 1.44.2).
- The repository was mounted read-only into it.
- Oracle 23 Free in a second container, on a network of their own.
- The real-Oracle tests got a switch: `V2_ORACLE_THICK=1` puts the whole
  run in thick mode.
- A session was ended from outside with the database's administrator.
- The database was then made to **demand Native Network Encryption**
  (AES256, SHA256 checksums) in its `sqlnet.ora`.

## What was found

**It works.** With the three faults below fixed, all 74 real-Oracle
tests pass with the client and without it, in that container.

Against the database that demands the encryption:

- Without the client no session opens (`DPY-3001`): only the one test
  that needs no session passes, as it must be.
- With the client all 74 tests pass, and the session shows the AES256
  and SHA256 adapters at work.

**Three faults, only with the client:**

1. **A query run for each row failed** with the two words "not
   supported". Oracle's client says `DPI-1013` of a query handed over
   for many rows where the thin driver says `DPY-2040`, and v2 knew
   only the second.
2. **A session the database closed brought the engine down at the end
   of the job.** Asked whether a transaction is open on such a session,
   the client fails (`DPY-1001`) where the thin driver still answers.
   The engine asks that of every session it closes. The job ended with
   the driver's own error, and not with the word that work was lost.
3. **A job that names its own `tnsnames.ora` opened no session**
   (`ORA-12154`). The client looks a name up in its own folder and
   passes over the file a connection names. No test had ever opened a
   session by such a name, in either mode.

**What is the same in both modes**, each tried:

- Rows as an Arrow table for an insert, with the rows that were refused
  and the counts. A block for many rows, and the row it failed for.
- A block that cannot be compiled. A procedure's values in and out.
- Every column type the input reads, a `CLOB` of 40,000 characters, a
  number of 20 digits.
- What a wrong password, a host no one knows and a port nothing listens
  on are told. None shows the password.
- `oracle_config.thick_mode` in a job by itself, with `lib_dir` and
  without; a `lib_dir` that is not there says so in one line.
- A text written `q'...'`: the statement reader and the client's own
  reading agree at 304,845 places.

**What differs and was left as it is:**

- The client knows at once that a session was ended. The thin driver
  learns it with the next statement.
- Of a query handed over for many rows the thin driver loses the
  session; the client does not.

## Answer

Fixed on 2026-10-13, in `src/v2/oracle.py`.

- A query for each row is run row by row whichever of the two the
  driver says. The client's "not supported" of a statement that is no
  query is that statement's own failure, and is raised as it is.
- A session that cannot say whether a transaction is open is taken to
  have one: what waited on it is told as lost, never dropped.
- With the client, a name of tnsnames is looked up in the file the job
  names with the driver's own reader of such files, and the session is
  opened with what the name stands for.
- A database that asks for what only the client does is told with how
  a job asks for the client: `"oracle_config": {"thick_mode": true}`.

### Slips

- **I wrote in three places that thick mode "was not tried", and built
  and reviewed nine components on it all the same.** A side note to the
  dev said so before I did.
- **The first run in the container failed for a reason of its own**: the
  scratch database took 200 processes, and tests that open sessions
  fast were refused by its listener. Raised to 1,500. It says nothing
  of v2.
- My comparison of the statement reader with the driver assumed the
  thin driver's ways. With the client it flagged 58 statements that
  Oracle takes in neither mode (a `q'` with a blank as its mark). They
  are left out in both modes now.

### How it was tested

11 tests more against the stand-in driver, which now answers as the
client was seen to where that differs, and 1 against the real database.

- 8 seen failing first: the query for each row, the two of the closed
  session, two of tnsnames, two of the refusal that names the client,
  and the real one of tnsnames (in thick mode; it passes in thin).
- 4 hold what must stay.
- Mutation: 14 ways of breaking the four fixes, all caught at first.

### Not done

- **Speed.** With the client the bulk read and the bulk insert took
  about twice as long in a first measurement, and a block of PL/SQL for
  each row over twenty times as long. That is its own ticket, with the
  research the dev asked for.
- Kerberos and a wallet: not built, not tried.
- RHEL itself, and the client on any other release.

**For the user's eye**

- **If Citi's databases demand Native Network Encryption, v2 can serve
  them**: Oracle's client installed on the server, and
  `"oracle_config": {"thick_mode": true}` in the job. Proven here
  against a database that demands it.
- **If they take only Kerberos or a wallet sign-in, v2 cannot sign in
  yet.** It opens a session with a user and a password. That is a
  feature to build, and needs a site that has them.
- **It is slower with the client.** How much, and what to do about it,
  is being measured and researched now.
- The tests also ran on Oracle Linux 8 with Python 3.12 for the first
  time: the Oracle components pass there.
