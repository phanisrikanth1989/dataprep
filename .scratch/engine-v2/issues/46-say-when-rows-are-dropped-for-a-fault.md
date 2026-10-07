# 46 - Say when rows are dropped for a fault

Status: resolved
Type: task
Blocked by: 40

## Question

A reader that is told not to stop on a row it cannot read
(`die_on_error` off) turns the row away. When no flow takes its reject
output the row is gone, the job ends in success, and the log at its normal
level says nothing: one output is a row short and nobody is told. v1 shows
it for its delimited and JSON readers, because every v1 component logs
`NB_LINE / OK / REJECT`; v2 moved those counts behind `--row-counts`
([Row counts on request](32-row-count-of-every-component-in-the-log.md)),
and the reject count went with them.

Have the log say it, always: which component dropped rows for a fault, how
many, and which was the first.

Found on 2026-10-07 while the dev read the logs of the payments scenario:
the same bad amount that fails the strict job is dropped by the lenient one
without a word.

## To build

- One WARNING line for each component that dropped rows for a fault, when
  the subjob has finished: the count, what was wrong with the first, and the
  first one's place and key, worded as a failure words them.
- For a fault only: a row a reader cannot read, a record a path cannot be
  followed on, a missing value in a column that may not hold one. Not for
  what the job itself turns away (a filter's, a unique's, a join's rejects).
- Nothing when a flow takes the component's reject output, and nothing in a
  subjob that fails: nothing was dropped there, and nothing was written.
- The job still succeeds and writes the same files.

Agreed with the dev before building: the warning is on stderr, so a run that
dropped rows no longer has an empty stderr; and it may cost about what
`die_on_error` costs today (0.2 s per million rows on the payments
scenario, measured as a proxy).

## Answer

Built on 2026-10-07 (38 tests in `tests/v2/test_dropped_rows.py`), then
reviewed by a second reader and reworked the same day.

- The line, at WARNING, when the subjob has finished:
  "[payments_in] 1 row was dropped (no flow takes this component's
  rejects): Column 'amount': could not convert string to Decimal:
  '9600x81.20'; the row is line 654322 of payments.csv (txn_id=654321)".
  For several rows: "3 rows were dropped (...); the first: ...". A
  component with no reject output leaves the words in brackets out. What
  was wrong is worded as the component's reject output words it; the place
  and the key as a failure has them.
- Who says it: the delimited and the positional reader for a row they
  cannot read, the JSON input for a record a path cannot be followed on
  (whatever `die_on_error` says, as the record is turned away either way),
  and the engine for a missing value in a column that may not hold one,
  after any component. A component that dropped rows for two kinds of
  fault has a line for each.
- Not said: when a flow takes the component's reject output; when the
  component stops the job instead (`die_on_error`); in a subjob that fails,
  wherever it fails; for the rows a filter, a unique row or a join turns
  away.
- How: a component hands the engine the frame that still holds the rows
  (`frame = self.tell_dropped(frame, turned_away, wrong)`). The engine
  notices such rows as they pass, in the subjob's own pass. Only a subjob
  that had some is read once more when it has finished, to count them and
  find the first.
- Cost, measured on the payments scenario at 1,000,000 rows (the middle of
  seven whole runs each, turn and turn about): 2.01 s before there was a
  warning, 2.05 s now, and 2.24 s for a run that does drop a row. The
  first build asked in every run and took 2.24 s whether or not a row was
  dropped.
- The job's files and its exit code are unchanged: the three versions
  write the same bytes at a million rows, and the whole suite that
  compares v2's files with v1's passes.

What the review found and what became of it:

- **The warning cost a second reading in every run** (0.22 s of 2.05 s by
  the reviewer's measure). Reworked as above.
- **A value could break the log line or fill it.** A line break in a value
  or in a key made two lines, the second of which could read as a line of
  the engine's own; a field of 5,000 characters, or a whole file read with
  the wrong separators, landed in the line. Now what was wrong is cut at
  200 characters and control characters are written as escapes. A
  failure's line had the same two faults and is kept to one line and cut
  as well.
- **The JSON reader's reason named neither column nor path** ("a path
  could not be followed on the record (0)"). It names both now. The reject
  output's `errorMessage` is still what the library said, as in v1.
- **The payments scenario's timed run printed no warning at all**: it cut
  the engine's logger off from the log. It prints what the engine warns of
  now.
- **Tests that could not fail.** Added: a filter's, a unique row's and a
  join's rejects are not told; two subjobs (told once; a failed subjob's
  row is not told by the next); the missing-value drop with the rejects
  taken; a run that drops nothing is handed to Polars once.
- **The docs said more than is so**: that v1 shows every such loss (it
  shows a delimited or JSON reader's; a row dropped for a missing value it
  counts as passed on), and "one line for every component".
- **Still silent, and ticketed for the dev**: an aggregate leaves out rows
  with no value in a group column
  ([Rows an aggregate leaves out for a missing group value](51-rows-an-aggregate-leaves-out-for-a-missing-group-value.md)).

Left out: the summary printed at the end has no entry for dropped rows; the
warning is in the log only. When a file cannot be put in place after
another of the same subjob already was, the subjob has failed and nothing
is told of the rows dropped on the way to the file that is there.
