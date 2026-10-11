# 76 - File row count

Status: resolved
Type: task

## Question

Build v1's file row count (`FileRowCount`, `tFileRowCount`) on v2: the
rows of a file are counted and the count is left in globalMap as
`<id>_COUNT`, for a trigger's condition or a later component to read.
Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/file/file_row_count.py`. No flow in or
  out. With a row separator that is a line end (`\n`, `\r\n`, `\r`) every
  kind of line end ends a row, a last row needs none, and an empty file
  has no row. Any other separator splits the whole text, and what follows
  the last separator counts only if it is not empty. With
  `ignore_empty_row` a row of nothing but blanks is not counted. It sets
  `<id>_COUNT` (the rows counted) and the three line counts (rows found,
  counted, not counted). A file that is not there or cannot be read in its
  encoding fails the job. (Tried on 2026-10-12, 17 small jobs.)
- It is the first v2 component that hands no rows on and takes none: it
  acts. The engine needs a kind for that; the six components still to
  come after it (die, warn, set global var, file exist, file copy, file
  delete) are of the same kind.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_row_count.py`; 35 tests
in `tests/v2/components/test_file_row_count.py`, 31 of them written and
seen failing before any code; the four numbers it leaves in globalMap are
held against v1's for every file tried).

- The engine has a fifth kind of component, `Action`
  (`src/v2/components/base.py`): it takes and hands on no rows, and does
  what it does when its subjob's turn comes. The runner runs it, leaves
  its own counts alone and gives it counts of none when it says none; the
  check at load passes it by. A test of the engine's holds that with a
  component made for the test.
- Counted line by line where the separator is a line end, so the file is
  not held; split whole otherwise, as v1.
- A trigger's condition and a later subjob read the count: both held
  against v1 by a job each.
- Mutation check: 20 ways of breaking it and the engine's new lines. A
  first run of it was worth nothing (a test of mine was red, so every way
  "was caught"); the tool now stops on a red start. On the second run two
  ways got through, and each got a test.

Not looked up: whether Talend ends a row at every kind of line end when
the separator is `\n`; v1 does, and so does v2.
