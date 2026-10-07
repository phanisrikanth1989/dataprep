# 40 - Every source numbers its rows

Status: resolved
Type: task

## Question

Build the row numbers of
[How v2 points at the input row that failed a job](38-how-v2-points-at-the-input-row-that-failed-a-job.md):
every source numbers its rows, the number travels hidden with the row, and
a failure the engine finds names the row.

## To build

Names. Hidden columns start with `__v2_`: `__v2_row:<source id>` holds the
number, `__v2_key:<source id>:<column>` a copy of each key column, and after
an aggregate `__v2_rows:<source id>` how many rows went into the group.

Sources:

- Each of the four readers numbers its records from 1 where it reads them,
  before any row is dropped, so that for a text file the number plus the
  header lines is the line an editor shows.
- A source can say where a number is (`locate`): "line 7 of in.csv"; "record
  7 of in.csv" for a file with enclosures, where a record can span lines;
  "row 7 of sheet 'Q1' of book.xlsx".
- Key columns come from the schema's `key` flag.

The engine:

- Drops the hidden columns before a file output writes and before user
  Python or a context load is handed rows.
- Leaves them out of what a debug line and an error message list as columns.

Components that pick their columns keep the hidden ones: filter columns, the
map's outputs, the Python dataframe's lazy way (dropped), the aggregate
(lowest number of the group and the count). A join drops the lookup's. Log
row does not print them. Unique row does not count them as key.

Failures that name the row, in the line the failure has today:

- a reader with `die_on_error` (text that is not the declared type, a wrong
  field count, a missing value where none is allowed);
- a missing value in a column that may not hold one, after any component;
- text a map output cannot read as its declared type.

The words: "...; the row is line 654322 of /data/payments.csv
(txn_id=654321)". A value is cut at 100 characters.

Held by: tests of each message; the answer-key suite, which fails if a
hidden column reaches a file; a test that the numbers cost nothing a
million-row run can show.

Not here: reject files keep the bytes v1 writes, so a rejected row's own
message gains nothing.

## Answer

Built on 2026-10-07 (`src/v2/rows.py`; tests in `tests/v2/test_row_numbers.py`).

- The four readers that were there number their rows where they read them,
  and each says where a number is: `line 7 of in.csv` (delimited,
  positional, full row), `record 7 of in.csv` for a delimited file read with
  `csv_option`, `row 3 of sheet 'Q1' of book.xlsx`.
- The number and the copies of the key columns travel hidden. The engine
  drops them before a file output is handed its frame and before the Python
  dataframe or the context load is handed rows, and leaves them out of
  expression scopes and debug lines.
- Filter columns and the map's outputs hand them on; a join and a map leave
  a lookup's behind; an aggregate keeps the lowest number of each group,
  that row's key and the count; log row does not print them and unique row
  does not take them for key columns.
- Three failures name their row: a reader with `die_on_error`, a missing
  value where none is allowed after any component, and text a map output
  cannot read as its type. The words:
  "...; the row is line 4 of in.csv (id=3)", and after an aggregate
  "...line 3 of in.csv, the first of 2 rows that were combined (id=2)".
- Thirteen existing tests pinned the old message and now expect the place.
  Each named line was checked against the test's data by hand.
- Cost: the payments scenario at 1,000,000 rows runs in 1.89 s with the
  numbers carried, against 1.85 to 1.87 s before.
- No file changes: the whole suite that compares v2's files with v1's
  passes, and it fails wherever a hidden column reaches a component that
  treats every column alike (it caught log row, unique row, the Python
  dataframe and the context load while this was built).

Not done here: a rejected row's own message in a reject file is as v1
writes it. After the Python dataframe a row has no number.
