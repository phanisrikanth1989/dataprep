# 61 - Fixed flow input

Status: resolved
Type: task

## Question

Build v1's fixed flow input (`FixedFlowInputComponent`, `tFixedFlowInput`)
on v2: rows written in the job config itself. Asked for on 2026-10-11 with
the other 25.

## What is known

- v1: `src/v1/engine/components/file/fixed_flow_input.py`. Three ways to
  write the rows: one row of values repeated `nb_rows` times
  (`use_singlemode`, `values_config`), a table (`use_intable`, `intable`),
  or text with separators (`use_inlinecontent`, `inline_content`,
  `row_separator`, `field_separator`).
- A value that is a plain number as text becomes that number before the
  column's type is looked at (`007` is 7, also in a text column). A value
  that is `globalMap.get("KEY")` is that entry of globalMap.
- It is the first source added since the row numbers: it numbers its rows,
  says where a row is, and can be picked from (`run.only`).

## Answer

Built on 2026-10-11 (`src/v2/components/file/fixed_flow_input.py`; 27 tests
in `tests/v2/components/test_fixed_flow_input.py`, against v1; tests
written and seen failing first).

- The three ways of writing rows, in v1's order of precedence: inline
  content, the table, the single row repeated `nb_rows` times. Separators
  of the content take v1's escapes.
- A plain number written as text is the number, in a text column too, and
  `globalMap.get("KEY")` is that entry: both as in v1, held by tests.
- As a reader it numbers its rows, a failure names
  `line 3 of the inline content of in` or `row 2 of in` with the key, and
  a run can be for a few of its rows (`lines` for content, `rows` for the
  other two). Tests in `tests/v2/test_row_numbers.py` and
  `tests/v2/test_only.py`.
- Differs from v1, each in the README: the text `false` is false; a value
  not of its column's type goes missing where v1 writes it through.
- The rows are held in memory, being as many as the config writes.

## Corrected after review (ticket 65)

- A date written in digits (`20240131` under `%Y%m%d`) failed the job, and
  a whole number beyond 64 bits gave Polars' own error in any column. Only
  a column declared a number is now held as numbers; every other column
  holds each value as its text and the engine reads it as its declared
  type.
- A text column is picked from (`run.only`) by the number it holds: `007`,
  `7` and 7 all find it, through `as_read`, which the engine now asks for
  text columns too.
- Not done: `values_config` written as a mapping, which v1 reads and the
  converter never writes.
- More differences from v1 are in the README.
