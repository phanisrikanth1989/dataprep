# 58 - Unpivot row

Status: resolved
Type: task

## Question

Build v1's unpivot row (`UnpivotRow`, `tUnpivotRow`) on v2: the columns
that are not keys become rows of a name and a value. Asked for on
2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/unpivot_row.py`, on pandas'
  `melt`. Keys: `row_keys`, `pivot_key`, `pivot_value`,
  `include_empty_values`, `die_on_error`. The converter writes the first
  four.
- v1's rows come out column by column (every row's first value column,
  then every row's second), not row by row as its docstring says.

## Answer

Built on 2026-10-11 (`src/v2/components/transform/unpivot_row.py`; 14 tests
in `tests/v2/components/test_unpivot_row.py`, against v1; tests written
and seen failing first).

- Keys: `row_keys` (needed), `pivot_key`, `pivot_value`,
  `include_empty_values`, `die_on_error`, with v1's defaults.
- Rows come out column by column, as v1's do. The value is the text of
  what the column holds, written as v1 writes it (`True`, `1.50`,
  `2024-01-31 00:00:00`). Empty text is a value; a missing value is one
  only while `include_empty_values` is on.
- Each row carries the row number of the row it was made from (a test in
  `tests/v2/test_row_numbers.py`).
- Differs from v1: a whole number stays whole beside a missing one (v1:
  `3.0`); keys that cannot be used refuse the job at load.
- A name for one of the two new columns that an input column already has
  fails on both engines.
- Not checked against Talend: tUnpivotRow is a community component, and
  v1's own notes say its source was not found.

## Corrected after review (ticket 65)

- A Decimal whose column declares no places was written padded to ten
  (`1.5000000000`). It is written `1.5`; v1 writes it as it stood in the
  file (`1.50`), which v2 no longer knows.
- The names column may be called like a column that is unpivoted, as v1
  allows ("fails on both engines" was wrong for that case). A key named
  twice, a names column called like a key, and a values column called like
  an input column refuse the job in words.
- The README said v1 writes `3.0` beside a missing value; it does so also
  beside any float among the unpivoted columns.
