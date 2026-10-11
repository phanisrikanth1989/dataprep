# 55 - Split row

Status: resolved
Type: task

## Question

Build v1's split row (`SplitRow`, `tSplitRow`) on v2: one row becomes one
row for each group of `col_mapping`. Asked for on 2026-10-11 with the
other 25.

## Answer

Built on 2026-10-11 (`src/v2/components/transform/split_row.py`; 13 tests
in `tests/v2/components/test_split_row.py`, against v1).

- A group says what each of its columns holds, read as v1 reads it: a
  column of the input after any flow name (`row1.amount`), text in quotes,
  a number (`1.50` is 1.5), and anything else as the text it is written as.
- The rows made of one input row stay together, in the order of the groups.
  A column a group leaves out is missing in its rows. No groups, no rows.
- Each row made carries the row number of the row it came from (a test in
  `tests/v2/test_row_numbers.py`).
- No difference from v1 found.

## Corrected after review (ticket 62)

- "No difference from v1 found" was wrong. Where the groups gave one
  column values of several kinds, the column was turned into one Polars
  type: a date became a number, true became 1. It now holds each value as
  the text it is written as, which is what v1 writes, and the engine reads
  it as the type the output declares. Held against v1 for a date, true or
  false and a Decimal beside text and numbers.
- One difference stays, and is in the README: a whole number beside a
  missing one is written `100`, where v1 writes `100.0`.
- `die_on_error` is declared. With no groups it counts no rows, as v1.
- Not done: a column of the input named like one of its two working
  columns (`__split_place`) fails with Polars' own words.
