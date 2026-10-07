# 46 - Say when rows are dropped for a fault

Status: resolved
Type: task
Blocked by: 40

## Question

A reader that is told not to stop on a row it cannot read
(`die_on_error` off) turns the row away. When no flow takes its reject
output the row is gone, the job ends in success, and the log at its normal
level says nothing: one output is a row short and nobody is told. v1 shows
it, because every v1 component logs `NB_LINE / OK / REJECT`; v2 moved those
counts behind `--row-counts`
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

Built on 2026-10-07 (21 tests in `tests/v2/test_dropped_rows.py`).

- The line, at WARNING, when the subjob has finished:
  "[payments_in] 1 row was dropped (no flow takes this component's
  rejects): Column 'amount': could not convert string to Decimal:
  '9600x81.20'; the row is line 654322 of payments.csv (txn_id=654321)".
  For several rows: "3 rows were dropped (...); the first: ...". A
  component with no reject output leaves the words in brackets out.
- Who says it: the delimited and the positional reader for a row they
  cannot read, the JSON input for a record a path cannot be followed on
  (whatever `die_on_error` says, as the record is turned away either way),
  and the engine for a missing value in a column that may not hold one,
  after any component. A component calls `self.tell_dropped(rows, wrong)`;
  the engine logs what was told once the subjob's files are in place.
- Not said: when a flow takes the component's reject output; when the
  component stops the job instead (`die_on_error`); in a subjob that fails,
  wherever it fails; for the rows a filter, a unique row or a join turns
  away.
- The job's files and its exit code are unchanged. The whole suite that
  compares v2's files with v1's passes.
- Cost, measured: the payments scenario at 1,000,000 rows takes 2.30 s with
  the warning and 2.13 s without (the middle of seven whole runs each, turn
  and turn about). The typed columns of the payments file are parsed once
  more to count the rows that failed. A job whose readers stop on a bad row
  (`die_on_error` on) already paid this and pays nothing more.

Left out: the summary printed at the end has no entry for dropped rows; the
warning is in the log only.
