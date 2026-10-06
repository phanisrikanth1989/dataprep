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
