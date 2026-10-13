# 38 - How v2 points at the input row that failed a job

Status: resolved
Type: grilling

## Question

When a job fails on a row, what does v2 tell production support about that
row, where does it say it, and which kinds of failure does the first build
cover?

Follows the research of
[How to point at the input row that failed a job](37-how-to-point-at-the-input-row-that-failed-a-job.md),
whose findings are in
`research/2026-10-06-pointing-at-the-failed-row.md`. The dev asked on
2026-10-06 to discuss the findings and then build.

## What is known

The dev, 2026-10-06: support's trouble is a mix of both kinds of failure, a
bad value in an input file and a failure further in (a map expression).

Tried on 2026-10-06, polars 1.44.2, Apple M4:

- **A row's number is its line.** Numbered at the scan, a row's number plus
  the header lines plus one is the line an editor shows. That holds on both
  ways v2 reads a text file (`scan_csv` and `scan_lines`) and with blank
  lines in the file, which the scan counts as rows. So the number has to be
  taken at the scan, before any row is dropped.
- **Not with a line break inside a quoted field.** The scan then counts
  records: the record after a field that holds one line break is one line
  further down than its number says.
- **A conversion a condition guards does not fail.** `int(x) if x.isdigit()
  else 0` runs clean on v2 as on v1; only a conversion that is really worked
  out on the row fails. A row the search finds is therefore a row that fails.
- **What can fail on a row in an expression** is a short list, all in
  `src/v2/expressions/functions.py`: `int()` and `float()` of text, a number
  turned into a whole number that is not one (not a number, too large), and
  `strptime()`.
- **Looking again finds the row fast.** One bad value planted in a column a
  map converts with `int()`; the job fails with Polars' message, which names
  the value and no row. Running the failed component's part of the plan
  again on a window of the reader's rows, halved each time, found the
  planted row: 23 runs and 2.1 s for 1,000,000 rows (0.47 GB), 26 runs and
  13.1 s for 5,000,000 rows (2.3 GB). The job's own failure took 4.6 s and
  25 s. Probe: `research/probes/probe_look_again_for_the_failed_row.py`.
- **It grows with the file.** Skipping to a far row costs about 0.06 s for
  0.47 GB with the file in memory's cache. A file of tens of GB on a cold
  disk wants a limit on how long the search may take.
- **Polars' message is not enough to search by.** It names the column the
  value came from and the value as the conversion saw it (`x320` for a cell
  holding `OPx320`), so a search for the printed value in that column finds
  nothing.

Not tried yet: a failure whose bad row sits in a lookup and not in the main
input; a component that needs rows in hand before the one that fails (the
search would run its Python again on every try); files with enclosures.

### The dev's idea, 2026-10-07

Let the user mark a column of a source as its key, and show that column's
value when a row fails, in either kind of failure. Where no key is marked,
give every row of the source a number from 1 as it is read, whatever kind
of source it is, and report that number. The dev's doubt: whether this can
be done at all in Polars, which works on columns and not on rows.

Tried the same day (probe:
`research/probes/probe_row_number_and_checked_conversion.py`):

- **It can be done.** A row's number is one more column, and Polars keeps a
  row's values together through a filter, a sort and a join. The schema
  already has a `key` flag on every column; no v2 component reads it yet.
- **Carrying it costs nothing that shows.** The payments job with one more
  whole-number column read from the file, passed through both maps and
  written to every output, which is more than a hidden column would cost:
  1.87 s without, 1.89 s with, 1.85 s without again (1,000,000 rows).
- **The number alone does not find a row Polars fails on.** Polars' message
  prints the value and nothing else of the row. The number is of use where
  the engine holds the failing row itself.
- **So the engine has to make the check, and can.** The conversion built
  without raising, a row flagged when its text was there and gave no
  number, and one small plan beside the job asking for the count, the
  lowest row number, that row's value and its key: 0.17 s against 0.17 s
  on a clean file, and on a file with two bad rows "2 rows, first 654321,
  value 'OPx320', key '654321'" in the pass that fails today with no row.
  No second look at the data is needed for these.
- **What it does not reach:** a row after an aggregate (many rows have
  become one), a row after user Python that builds a new table, and an
  error Polars raises that the engine does not check for itself. Looking
  again (above) stays the way for the last.

What the others do, from the research note: Snowflake, Spark, DuckDB and
Delta Lake give a row number or row id as a column asked for at the read;
Great Expectations and dbt name a failing row by the key columns the user
lists; Talend and Integration Services hand on the failing row with its
columns. None of the pages read speaks of carrying the number through a
join by itself: that part would be v2's own.

Found on the way:
[A conversion guarded by `and` or `or` fails on v2 and not on v1](39-a-conversion-guarded-by-and-or-or-fails-on-v2.md).

### Two more questions from the dev, 2026-10-07

**Does listing twenty bad rows mean `die_on_error` is passed over?** No.
Tried: 200,000 rows, three of them bad and far apart, `die_on_error` on.
The job fails, no file is written, and the message already reads "failed
for 3 row(s); first error: ...". v2 does not go row by row: the check runs
over the whole file in the pass, and the job fails when the pass is done.
So every bad row is known by the time it stops; twenty is how many are
shown, not how many are let through. The other side of it: a job that is
going to fail reads its whole file first, where Talend stops at the first
bad row.

**Can the row still be followed past an aggregate, Python code, a
transpose?** A row's identity need not stay one number; each kind of step
can say what becomes of it. Tried on 1,000,000 rows:

- An aggregate that also keeps, for each group, the lowest source row
  number and how many rows went in: 0.08 s with and without. A failure
  after it can name the group by its key columns and say "built from 11,112
  rows, the first is row 8".
- Finding a source row again by the value of its key column, once the
  number is gone: one filtered read of the source, 0.09 s. That reaches
  past Python code whatever the code did, as long as its result still has
  the key column.
- pandas keeps a row's label through a filter, a sort, a new column, a
  row-wise apply, an explode and a transpose (there the labels become the
  column names); it loses it in a groupby, a merge, a `reset_index` and a
  melt. The number could ride on the labels, but v1 hands user code labels
  from 0, and changing them can change what the code sees.

What cannot be had by any means: "the" row behind a row that many rows
were combined into. Only the group and the rows that went into it.

## To decide

- Which failures come first: the ones a reader finds (a value that is not
  the declared type, a wrong field count, a missing value where none is
  allowed), the ones the engine finds further down, or the ones Polars
  raises in the middle of a pass (a failing expression in a map).
- What "where" is: a record number every reader can give, and beside it the
  reader's own position (a line of a text file, a sheet and a row).
- What is shown of a wide row: the failed column and its value, how long a
  value may be, the columns that identify the row, and the whole row.
- Where it is said: the log, the summary, a file of errors written by the
  engine (a subjob that fails writes none of its own files), globalMap.
- Whether values of the data may stand in a log at all.
- Whether reject files stay byte for byte what v1 writes.
- How many failing rows are reported: the first, or the first few and a
  count.

## Answer

Settled with the dev on 2026-10-07. The dev's own idea is the design.

- **Every source numbers its rows**, from 1, as it reads them, whatever kind
  of source it is. The number is a hidden column that travels with the row.
  It is never written to a file and never shown to user Python.
- **A key column is shown as well.** A column the source's schema marks as
  key (the `key` flag every schema column already has) has its value shown
  beside the number. The number is always there, key or no key: a key can
  repeat, and can be the bad cell itself. (The dev asked for the number only
  where no key is marked; shown both ways the dev did not object.)
- **A failure names the row**: where it is in its source (a line of a text
  file, a sheet and a row, a path in a JSON document), and its key.
- **Only the log.** The first failing row and how many failed in all, in the
  one line the failure has today. The bad value may stand in the log. No
  file of errors. (The dev, 2026-10-07: "only bad row is sufficient. error
  can present in the log.")
- **`die_on_error` is untouched.** The job fails and writes nothing, as now.
- **Conversions in expressions are checked by the engine**, not left to
  Polars to raise on, so that the failing row is in hand and can be named.
  That also corrects the fault of ticket 39.
- **What becomes of the number at each kind of step**: kept through a
  filter, a sort, a lookup, a map and a unique row; repeated when one row
  becomes several; the lowest of the group, with how many rows went in,
  after an aggregate; lost after user Python.
- **Left for later**: finding a row again by its key after user Python (one
  filtered read of the source, 0.09 s for a million rows), and looking again
  after a failure for what Polars still raises by itself (the probe finds
  the row in 2.1 s for a million rows). Both are in the map.

Built under:
[Every source numbers its rows](40-every-source-numbers-its-rows.md),
[Conversions in expressions are checked by the engine](41-conversions-in-expressions-are-checked-by-the-engine.md),
[JSON file input](42-json-file-input.md),
[Normalize](43-normalize.md), and written down for whoever adds a component
next in
[What a new component owes the row numbers](44-what-a-new-component-owes-the-row-numbers.md).
