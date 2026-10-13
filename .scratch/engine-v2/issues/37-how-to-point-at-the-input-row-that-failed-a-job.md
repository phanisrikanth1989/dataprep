# 37 - How to point at the input row that failed a job

Status: resolved
Type: research

## Question

Production support's main trouble is finding the exact input row that made a
job fail. What is the best way for v2 to report it, in a way that still fits
when an input is not lines of text (JSON, XML, Excel) and when a row is very
wide?

Raised by the dev on 2026-10-06, during the review of the engine. The dev
wants the answer to be future proof, and research before anything is built.

## What is known

Tried on the payments scenario (`scenarios/payments`), v2 on Polars 1.44.2:

- Today a failure names the component, the column, the bad value and how
  many rows, never which row. A reader: `Schema/coercion failed for 1
  row(s); first error: Column 'amount': could not convert string to Decimal:
  '12x.50'`. A map: `conversion from str to i64 failed in column
  'operator_id' for 1 out of 1065 values: ["x320"]`.
- Numbering the rows while a file is read costs nothing that could be
  measured: 0.15 s with and without, for 1,000,000 rows of 45 columns.
- For a failure Polars raises in the middle of a pass, running the job again
  on half the file, then half of that, found the planted row (line 654,322 of
  1,000,000) in 20 runs. The try-out reran the whole job and wrote every
  output each time and took 50 s; a build that reruns only the failing part
  has not been measured.
- A broken expression in a map column nothing reads never runs in v2, so it
  does not fail the job. v1 computes every column.

Both ideas were worked out in one sitting. Nothing says they are the best
way.

## To find out

- How other engines report the record that failed, from their own
  documentation and code: what they show, and what it costs them.
- Whether a later Polars says where a failed parse or cast happened, or
  offers anything to build this on.
- Giving every row an identity that travels through the whole plan, against
  searching for the row after the failure: the cost of each, and what
  survives a join, an aggregate and user Python.
- What "where" means for each kind of input: a line of a text file; a sheet
  and a row of a workbook; a record number or a path in JSON or XML. One
  shape of answer that every reader can fill in its own way, including
  readers v2 does not have yet.
- What to show of a row of a hundred columns or more: the column that failed
  and its value, the columns that identify the row (a schema can mark key
  columns), and where the whole row goes, if anywhere.
- Where it is reported: the log, the summary, a file of errors, and globalMap
  entries an error trigger's subjob can read.

## Then

The findings go in `.scratch/engine-v2/research/`. A ticket to build it
follows them.

## Answer

Researched on 2026-10-06 from primary sources only. The findings are in
[`research/2026-10-06-pointing-at-the-failed-row.md`](../research/2026-10-06-pointing-at-the-failed-row.md):
twelve sentences under "In short", then a section for each point above, a
table comparing eighteen tools, four options, twelve try-outs and what could
not be verified. Nothing was run for it.

What it comes to:

- No tool read says where in the input a row came from when it fails in a
  later step. A position is known only where the row is read. Talend,
  Spark, DuckDB and Polars are all alike in this.
- Talend gives less than it seems to: " - Line: N" on a rejected row is a
  count of rows handled so far, from 0, not a line of the file, and with
  die on error there is no line at all. (Read from the code templates of a
  fork of Talend Open Studio, not from a running job.)
- Polars names no row in any release, 2.0.0 of 2026-10-06 included. A
  request for line numbers is open without an answer; an earlier one was
  closed because the parallel reader does not know the line.
- The loaders that do it best (DuckDB, Snowflake, Redshift) give the file, a
  record or line number, the column, the value and the raw record, and keep
  them in a store of rejects, not only in the message.
- Where v2 finds the bad row itself (a reader's rejects, a missing value
  where none is allowed, text a map cannot read as a number) it can name the
  row in the same pass at no measured cost. An error Polars raises in the
  middle of a pass needs a second look at the data, on any Polars version.
- "Line" is the wrong word for the general case. What every reader can give
  is a record number; the position is the reader's own (a line, a sheet and
  a row, a path in JSON or XML). Published shapes for this exist (SARIF, the
  W3C model for CSV).
- For a wide row the others show the failed column and its value, cut to a
  length, add identifying columns only where the user names them, and send
  the whole record to the store of rejects. v2 today writes the bad value
  into the log with no limit, sets nothing in globalMap for an error, and
  never reads the schema's key flag.

The four options (readers report with a record number; the number travels
with the row; look again only after a failure; a failing row is a flagged
row and not an exception) are not decided here. That is
[How v2 points at the input row that failed a job](38-how-v2-points-at-the-input-row-that-failed-a-job.md).
