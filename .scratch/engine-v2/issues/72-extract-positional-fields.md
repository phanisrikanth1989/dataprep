# 72 - Extract positional fields

Status: resolved
Type: task

## Question

Build v1's extract positional fields (`ExtractPositionalFields`,
`tExtractPositionalFields`) on v2: one column's text is cut at fixed
widths and the pieces become columns. Asked for on 2026-10-11 with the
other 25.

## What is known

- v1: `src/v1/engine/components/transform/extract_positional_fields.py`.
  `pattern` is the widths, separated by commas (`"3,4,3"`); the columns
  the output declares and the input does not bring take the pieces.
- Tried on v1 (2026-10-12, 20 small jobs): a piece beyond the end of the
  text is empty text, not missing; a column beyond the last width is
  missing; widths beyond the last column are not read; a byte order mark
  at the start of the text is no part of it; `check_fields_num` turns a
  row away when its text is shorter than the widths together
  (`EXTRACTION_ERROR`), or fails the job under `die_on_error`; with no
  `field`, or one that is not a column, v1 cuts the first column.
- `formats`, `advanced_separator` and `advanced_option` are never read.

## Answer

Built on 2026-10-12 (`src/v2/components/transform/extract_positional_fields.py`;
25 tests in `tests/v2/components/test_extract_positional_fields.py`, all
written and seen failing before any code; held against v1 byte for byte).

- On the base extract delimited fields brought (`ExtractFields`): this
  component says only how a text is cut and when it is too short. The
  base learned one thing for it: the first column is the source when none
  is named, for the components v1 has it so.
- One pass, no row walked: each piece is a slice of the text.
- Differs from v1, each in the README: a `field` that names no column and
  a `pattern` that is none refuse the job.
- Row counts are held against v1's; the row is named in a failure and in
  the log of dropped rows.
- Mutation check: 15 ways of breaking it, 14 caught at first and the last
  (of the base) after a test.
