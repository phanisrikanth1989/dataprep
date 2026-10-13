# 122 - Oracle output

Status: resolved
Type: task

## Question

Build the Oracle output (`OracleOutput`, `tOracleOutput`), and with it
what the engine needs for a write that is no file. To
[Databases: the decisions](118-databases-the-decisions.md).

## What is known

- A direct path load always commits, and a table action that defines
  commits what waits. Nothing may be stored for a subjob that fails.
- The engine runs a subjob in one pass and puts its files in place only
  when the whole pass has succeeded.
- Tried against the real Oracle before anything was built: a batch is
  taken straight from a Parquet scratch file with every type intact, a
  text of 100,000 characters goes into a CLOB, a refused row is named
  with its place in the batch, and an update says for each row how many
  rows it changed.

## Answer

Built on 2026-10-12.

- **The engine**: a `Write` may name a scratch file of the run and no
  file to end up as. Its rows are written there in the pass, `ready`
  stores them from it and says how many it stored, nothing is moved.
  Files are made ready before tables are loaded. The summary, `NB_LINE_OK`
  and `NB_LINE_REJECT` have what was kept and what was turned away.
- **The session**: a statement run once for each row of a batch in one
  round trip, with the rows the database refused and how many rows each
  changed.
- **The component**: `src/v2/components/database/oracle_output.py`.
- Docs: "Oracle output" in `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **Update or insert in two or three round trips for a batch**, and to
  the same end as a row at a time. Every row updates; those that
  changed nothing are new; of several new ones with one key the first
  is inserted and the others update it, in their order. A single
  `MERGE` would not say how many were inserted and how many updated,
  and would insert a key that comes twice two times.
- **A key the table holds as a `DATE` is compared as a date.** Tried:
  handed a value with a fraction of a second, Oracle turns the column
  into such values row by row and reads the whole table; with the cast
  it uses the index. The table is asked what the column is. Talend's
  switch for this (`use_timestamp_for_date_type`) is read and changes
  nothing.
- **A value is bound as the kind it arrives as**, and is not made to
  match the output's declared columns first. Made to match, a text that
  is no number becomes a missing value without a word; bound as it is,
  the database refuses the row and says why.
- **A refused row is named by its place among the rows the output was
  handed, and by its key.** The engine takes the row's own number off
  before a sink sees the rows; giving it back is left for later.
- **With `die_on_error` off, a fault of the whole component takes back
  its own work and no other's**: it marks the session where it starts.
- **A table that is made gets its types from the declared columns**,
  since a job config carries no database types. The mapping is in the
  docs.
- **Field options and hints refuse the job when switched on.** The
  schema's `key` says which columns are keys.
- **No reject flow yet.** The rows the database refused would have to
  come back into the plan, which needs a stage of its own.

### How it was tested

- 7 tests of the engine's part, on SQLite: seen failing first.
- 63 tests of the component on SQLite. 58 were seen failing first, with
  the component taken away; five came with the mutation check.
- 3 tests of Oracle's part with a stand-in driver, written with their
  code.
- 10 tests against a real Oracle: every kind of value with 38 digits
  and a text of 100,000 characters, each action, a key that comes
  twice, refused rows with and without `die_on_error`, `CLEAR` taken
  back and `TRUNCATE` not, a table made and made again, a key that is a
  date, the session of a connection, 30,000 rows in batches.

### Mutation check

60 ways of breaking it. 49 were caught at first. Of the eleven others:

- **Two showed code that did nothing, and it went**: the engine took a
  scratch file away that the subjob's clean-up takes away, and the
  output asked whether a session is shared before taking its schema,
  which is its own block's either way.
- **One is no fault**: the rows are written to the scratch file with
  the declared columns only. Without that they are stored the same,
  from a larger file.
- **Eight got a stronger test**: the scratch file is the one asked for
  and nothing is moved; work taken back when the job goes on; the batch
  size without its switch; a refused row's number past the first batch;
  a fault the action does not allow for; a date key, cast and not
  looked up for an insert.

All were run again, and were caught.

**For the user's eye**

- **A load that fails after a `TRUNCATE` leaves the table empty.**
  Oracle does not take a truncate back. `CLEAR` is taken back.
- **Two outputs with a session each are two commits.** When the second
  commit fails the first stands, and the failure says so. One
  connection component and one commit is all or nothing.
- Speed and memory at the dev's sizes were not measured. (Measured
  since, up to thirty million rows: see
  [A database input's memory grew with its rows](128-a-database-inputs-memory-grew-with-its-rows.md).)
- Not built: a direct path load (it commits by itself), a check of the
  rows against the table's columns before they are sent, the reject
  flow.
