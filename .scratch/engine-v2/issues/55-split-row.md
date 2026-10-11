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
