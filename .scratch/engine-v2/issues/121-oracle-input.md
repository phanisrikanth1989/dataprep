# 121 - Oracle input

Status: resolved
Type: task

## Question

Build the Oracle input (`OracleInput`, `tOracleInput`), and with it how
a statement of a job becomes what a database is given. To
[Databases: the decisions](118-databases-the-decisions.md).

## What is known

- The engine reads a source again by design: for a second attempt, to
  find the component at fault, for a run of a few rows.
- Left to itself the driver loses digits, and asked for a decimal too
  wide it hands on another number without a word (ticket 118).
- A query reaches a job config as text, with `${context.x}` in it or as
  Java joined it, and the converter takes the outermost quotes off.

## Answer

Built on 2026-10-12.

- `src/v2/statements.py`: a statement as a job writes it, taken apart
  into text and values. A value in quotes is bound; one outside quotes
  is written in and has to be a name, a number or a list; a statement
  that defines has its values written as text with the quotes doubled.
  It knows nothing of a database: the same statement is handed out by
  name (`:context_d`, Oracle) or by place (`?`, for SQL Server later).
- `src/v2/sessions.py`: what a session says of a query's columns before
  it runs, and the one rule for what a job may declare them as.
- `src/v2/oracle.py`: the query that has Oracle convert each column.
- `src/v2/components/database/reading.py`: what every database input
  shares. `oracle_input.py` adds the keys and the session.
- Docs: "What is written into a statement" and "Oracle input" in
  `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **The database converts within a kind, and text is read by the
  engine.** A number becomes any number or text, a date a date or text.
  Text that the job declares as anything else is handed on as text and
  read as a file's text is, with the same rejects. A number is no date.
- **A number as text has a nought before its point.** Oracle writes a
  half as `.5`.
- **A timestamp as text is rounded first**, as the same column is when
  it is declared a datetime. Written out directly, Oracle cuts it.
- **The scratch file is Parquet**, lightly compressed. The research
  found an Arrow file's scan not flat in memory on this Polars.
- **Java that is more than joining refuses the job when it loads.** So
  does a name in double quotes next to a `+`: what the converter leaves
  of Talend's joining looks the same, and run as it stands it would
  find no row without a word.
- **`die_on_error` and a reject output are v2's own here.** Talend's
  input has neither; text that is none of its declared type needed
  somewhere to go.

### Found in the engine, and fixed

**A Decimal of more than twenty digits before its point went missing
without a word** when a column that was a Decimal already was made to
match its schema: it was read through the wider places that text is
read at, where it did not fit. A `NUMBER(38)` from Oracle arrived
empty. It is rounded where it stands now. (From a file such a number
was and is turned away with a message: that is the reader's doing, and
is said.)

### How it was tested

- 80 tests of the statement reader. Seen failing first for want of the
  module.
- 31 tests of the input on SQLite. Seen failing first, with the
  component taken away.
- 18 tests of Oracle's part with a stand-in driver, and 8 of the rule
  for declared types. **Written with their code**, not before it.
- 13 tests against a real Oracle: every kind of column, 38 digits,
  Oracle's rounding, a number too large, values bound through Talend's
  joining, a value that would change the query, order kept through the
  query's own `WITH` and a `UNION`, the time zone refusal and its two
  ways out, 25,000 rows in batches.
- The engine fix: a test that failed first.

### Mutation check

70 ways of breaking it. 65 were caught at first. Of the five others:

- **One showed code that did nothing, and it went**: the input turned 0
  and 1 into false and true, which the engine does for any number in
  such a column.
- **Four got a stronger test**: a remark that ends with its line, a
  pair of quotes between two values, texts joined side by side, and a
  session of a connection that is still there after the reading.

All were run again, and were caught.

**For the user's eye**

- The order of the rows rests on how Oracle works out a query inside
  another today: it keeps the inner `ORDER BY`. It was seen to, and the
  docs say that much and no more.
- An `XMLTYPE`, a `RAW`, a `BLOB` and a `LONG` column refuse the job.
  The query has to turn them into text.
- Memory and speed at the dev's sizes were not measured: Oracle Free
  holds 12 GB at most.
