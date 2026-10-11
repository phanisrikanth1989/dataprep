# 59 - Denormalize

Status: resolved
Type: task

## Question

Build v1's denormalize (`Denormalize`, `tDenormalize`) on v2: the rows
that agree in every other column become one row, with the values of the
named columns put together. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/denormalize.py`. Keys:
  `denormalize_columns` (each `input_column`, `delimiter` `;` by default,
  `merge`) and `null_as_empty`, which v1 added on its own.
- Every column that is not named is a key. v1 keeps the rows that miss a
  key value as a group (`dropna=False`), which is what Talend does (ticket
  51).

## Answer

Built on 2026-10-11 (`src/v2/components/transform/denormalize.py`; 16 tests
in `tests/v2/components/test_denormalize.py`, against v1; tests written
and seen failing first).

- Keys: `denormalize_columns` (`input_column`, `delimiter`, `merge`) and
  `null_as_empty`, with v1's defaults. Without any column named, every row
  is handed on.
- The rows of one key become one row where its first row arrives. Values
  are put together as v1 writes them (`True`, `1.50`), in the order they
  came; `merge` keeps the first of each.
- Rows that miss a key value are a group of their own, as in v1 and in
  Talend.
- A row made of several carries the lowest row number among them, and a
  failure says "the first of 2 rows that were combined" (a test in
  `tests/v2/test_row_numbers.py`). For that, `combined` moved from the
  aggregate into `src/v2/rows.py`, where the next components that make one
  row of several find it.
- Differs from v1: a whole number stays whole beside a missing one (v1:
  `3.0`); columns that cannot be used refuse the job at load.
