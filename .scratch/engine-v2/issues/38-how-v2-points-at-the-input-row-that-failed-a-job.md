# 38 - How v2 points at the input row that failed a job

Status: claimed
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
