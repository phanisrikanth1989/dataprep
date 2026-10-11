# 64 - Pivot to columns delimited

Status: resolved
Type: task

## Question

Build v1's pivot to columns delimited (`PivotToColumnsDelimited`,
`tPivotToColumnsDelimited`) on v2: the values of one column become the
columns of a delimited file, one row for each group. Asked for on
2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/pivot_to_columns_delimited.py`,
  on pandas' `pivot_table`. It writes the file itself and also hands the
  pivoted rows on.
- The columns of the file depend on the data, so no plan can be built for
  them before the rows are read. The rows are grouped in the subjob's one
  pass, and the small table of groups is turned into columns when the pass
  is done, before the file is put in place.
- Tried on v1 (2026-10-11): columns come in the order their values first
  appear; a column of whole floats is written as whole numbers; a sum or a
  count of nothing but missing values is 0; an empty input writes no file;
  v1 fails with "Invalid value '' for dtype 'Int64'" where the value column
  is whole numbers and no cell is empty; it drops the rows that miss a
  group value.
- Talend builds a group's key from the text of its values, a missing one
  among them (`tPivotToColumnsDelimited_main.javajet` at Talaxie
  639d5fd1f776, lines 196 to 250), so it keeps such rows.

## Answer

Built on 2026-10-12 (`src/v2/components/file/pivot_to_columns_delimited.py`;
40 tests in `tests/v2/components/test_pivot_to_columns_delimited.py`; tests
written and seen failing first).

- An output (a sink): the rows are grouped by the group columns and the
  pivot value in the subjob's one pass, and written as a small table; when
  the pass is done that table is read, turned into columns and written in
  the job's encoding, and only then is the file put in place. A subjob
  that fails leaves no file.
- Held against v1 for the six functions, sparse cells, Decimals, text,
  separators, encoding, fields that need enclosing, an empty input,
  `create` off, missing folders, and dates, true/false and Decimals in
  every role v1 can run.
- Held to Talend where v1 fails or differs (each in the README): whole
  numbers in the cells, rows that miss a group value, a date as a column
  name, true/false to group by.
- `<id>_NB_LINE` is the rows read and `<id>_NB_LINE_OUT` the groups
  written, as in v1 and Talend. The engine's own line in the log ("wrote 6
  row(s)") counts the rows read, not the groups.
- Its columns are checked at load when its input declares its columns, and
  when the rows arrive otherwise.
- Not built: handing the pivoted rows on (v1's extra), `csv_option` and
  `advanced_separator` (Talend's, which v1 does not act on either).
