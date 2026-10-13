# 68 - File output Excel

Status: resolved
Type: task

## Question

Build v1's Excel output (`FileOutputExcel`, `tFileOutputExcel`) on v2: the
rows of a flow written to a sheet of a workbook. Asked for on 2026-10-11
with the other 25.

## What is known

- v1: `src/v1/engine/components/file/file_output_excel.py`, on openpyxl.
  It reads `filename`, `sheetname` (quotes around it taken off),
  `includeheader`, `append_file`, `append_sheet`, `create`, `first_cell_x`
  and `first_cell_y`, `is_all_auto_szie`, `auto_szie_setting`,
  `recalculate_formula`, `delete_empty_file`, `die_on_error`. The other
  keys the converter writes (fonts, protection, streaming, separators) it
  never reads.
- A workbook's bytes differ from run to run (it is a zip with times in
  it), so v2 is held against v1 by what is in the workbook: sheets, cells,
  their types and number formats, column widths.
- v1 leaves out every row whose values are all missing or blank and counts
  it as rejected. Talend writes every row
  (`tFileOutputExcel_main.javajet` at Talaxie 639d5fd1f776, lines 118 to
  141: `addRow()` for each row, a null cell for a missing value).
- Talend deletes an empty file only when the component made it
  (`tFileOutputExcel_end.javajet` line 157: `isFileGenerated && nb_line ==
  0`). v1 deletes the workbook it appended nothing to.
- A date with a pattern is text in v1 and a date cell with that format in
  Talend (`putValue2007.javajet`).

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_output_excel.py`; 48
tests in `tests/v2/components/test_file_output_excel.py`, 36 of them
written and seen failing before any code; held against v1 by what is in
the workbook each engine writes).

- An output (a sink). The rows are written to a working file in the
  subjob's one pass; what they can fail on (a character no workbook can
  hold, more rows than a sheet has) is found when the pass is done, before
  any file is put in place; the workbook is made with openpyxl, as v1
  makes it, when its turn comes to be put in place. That late, because a
  second output of the same subjob may add to the workbook the first has
  just written (two sheets of one file, the common Talend job): held
  against v1 by two tests.
- As v1: sheet name and its quotes, header only into an empty sheet, first
  cell, append, the declared order of columns, a declared column that does
  not arrive, number formats from declared places, a date with a pattern
  as text and one without as a date cell, widths, the folder, the
  recalculation switch, and the keys v1 never reads.
- As Talend where v1 differs (each in the README): every row is written;
  a workbook nothing was added to is kept.
- openpyxl joins the `v2` extra in `pyproject.toml` (v1's `excel` extra
  has it already).
- Mutation check: 48 ways of breaking it; 46 caught at first, and the
  other two after a test each. Three pieces of code turned out to do
  nothing and were removed (`append_sheet` read, an empty text for a
  missing date, a cleanup the engine does itself).
- It walks its rows one by one, which the rules of `tests/v2/test_rules.py`
  forbid a component: a workbook is made cell by cell, with openpyxl. It
  is named there among the components that may (the Excel reader is
  another), and it walks them after the subjob's pass, not in it.
- Row counts are held against v1's (`tests/v2/test_row_counts_against_v1.py`).
  No row-number or dropped-row tests: an output names no source row and
  drops none.

Not done:
- A date as a date cell with its pattern as Excel format, which is what
  Talend writes: v1 writes text, and so does v2.
- `protect_file`, `usestream`, fonts and the other keys v1 never reads.
- A workbook that is there and cannot be read fails when the file is put
  in place, after earlier files of the subjob are in place.

## Corrected after review (ticket 71)

- A declared column that does not arrive made the rows count as none (and
  `delete_empty_file` then left no workbook). Every row is counted now.
- A day of a `date` column is text, as v1 holds it (it was a date cell).
- A first cell beyond a sheet's last column or row refuses the job; more
  columns than fit, and a sheet with no room for the rows, fail in plain
  words.
- A lone quote as a sheet name is `Sheet`, as in v1. A Decimal declared to
  no places is sized as it is shown.
- The trace shows a row as its cells hold it (`Write.as_text`).
- Wrong above: more than an unreadable workbook can fail when the file is
  put in place, and v1 fails to size only a sheet with missing values in
  columns of several types. Both are said rightly in the README and the
  docstring now.
