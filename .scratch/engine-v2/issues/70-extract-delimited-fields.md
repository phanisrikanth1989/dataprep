# 70 - Extract delimited fields

Status: resolved
Type: task

## Question

Build v1's extract delimited fields (`ExtractDelimitedFields`,
`tExtractDelimitedFields`) on v2: one column's text is split at a
separator and its pieces become columns. Asked for on 2026-10-11 with the
other 25.

## What is known

- v1: `src/v1/engine/components/transform/extract_delimited_fields.py`.
  The columns of the output schema that do not arrive are the extracted
  ones: the first takes the first piece, and so on. A piece that is not
  there is missing; pieces beyond the last column are dropped. The other
  output columns are handed on; an input column the output does not
  declare is dropped.
- A row whose source is missing is left out without a word
  (`ignore_source_null`, on by default), or leaves by the reject output
  with `NULL_SOURCE`. With `check_fields_num` a row whose pieces are not as
  many as the extracted columns leaves with `FIELD_COUNT_MISMATCH`, or
  fails the job under `die_on_error`.
- The separator is taken as it is written (quotes around it taken off;
  nothing given is `;`). Talend reads it as a pattern
  (`tExtractDelimitedFields_main.javajet` at Talaxie 639d5fd1f776, line
  93: `field.split(separator, -1)`), as it does for normalize, where v2
  keeps v1's reading too.
- `advanced_separator` looks for Talend type names (`id_Integer`) that a
  v1 schema never has, so it never acts. `check_date` is a stub.
- Tried on v1 (2026-10-12, 24 small jobs): an empty text is one empty
  piece, not a missing source; a source that is a number or a date is
  split as the text Python writes for it (`2024-01-31 00:00:00`).

## Answer

Built on 2026-10-12 (`src/v2/components/transform/extract_delimited_fields.py`;
30 tests in `tests/v2/components/test_extract_delimited_fields.py`, 29 of
them written and seen failing before any code, while the review of ticket
71 ran; held against v1 byte for byte but for four that say why not).

- One pass, no row walked: the text is split into a list, the list's
  pieces become the columns, and a row is turned away where it is.
- The part every such component shares is a class of its own
  (`ExtractFields`): which columns are filled, the missing source, the
  reject output with `errorCode` and `errorMessage`, failing the job with
  the row named, telling of dropped rows. Extract positional fields and
  extract regex fields are to be built on it.
- Kept from v1 where Talend differs: the separator as written (Talend: a
  pattern), a missing source as `NULL_SOURCE` (Talend hands the row on
  with empty text), v1's codes and messages in the reject output.
- A failure names the row (`line 3 of in.csv`), the log tells of rows
  dropped with no flow to take them, a run can be for a few rows, and the
  counts are v1's: the rows left out for a missing source are among the
  rows read and in neither of the other two. Tests for each.
- Mutation check: 29 ways of breaking it, 28 caught at first and the last
  after a test.
