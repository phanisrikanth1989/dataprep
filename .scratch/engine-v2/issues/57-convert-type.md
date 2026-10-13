# 57 - Convert type

Status: resolved
Type: task

## Question

Build v1's convert type (`ConvertType`, `tConvertType`) on v2: read the
values of columns as the type the output declares. Asked for on 2026-10-11
with the other 25.

## What is known

v1 is not an answer key for most of it. Run on 2026-10-11 with text
columns `10`, `x`, nothing, ` 7 ` declared `int` on the way out: v1 turns
away every row that holds a value, the good ones with "Invalid value '10'
for dtype 'str'" (its cast writes a number back into a text column, which
today's pandas refuses), and a job with `autocast` alone or `emptytonull`
alone stalls. Only a pair that names another output column works on v1.

## Answer

Built on 2026-10-11 (`src/v2/components/transform/convert_type.py`; 16
tests in `tests/v2/components/test_convert_type.py`, one against v1, the
rest on v2 alone for the reason above).

- `manualtable`: each column is read as the type the output schema declares
  for its output column, by the rules v2's readers have. A value that
  cannot be read turns its row away: to the reject output with
  `error_code` CONVERSION_ERROR and `error_message` (v1's two names), or it
  fails the job under `dieonerror`, naming the row. With no flow on the
  reject output the log says how many were dropped and the first.
- `emptytonull`: empty text becomes a missing value in every text column.
- `autocast`: accepted, and asks for nothing the engine does not do for
  every component.
- Differs from v1 as said under "Differences from v1" in the README.
- Not checked against Talend's own tConvertType: its source was not read.

## Corrected after review (ticket 62)

- A source column that is a date or true/false lost every row: it was
  turned into text the target's type could not be read from. A date is now
  written by the target's own pattern, true/false as 1 and 0 for a number.
  Held against v1 for eight pairs of types.
- A fraction is no whole number (`1.5`, `2.5`, a Decimal `1.50`): the row
  is turned away, as in v1. It used to be cut to 1.
- `die_on_error` is another key than `dieonerror`, as in v1, where the base
  class reads it for a value that may not be missing. `empty_to_null` is
  no key.
- The reject output's two columns are `errorCode` and `errorMessage`, as
  in every other reject output and in Talend, so that a row turned away
  for a missing value sits in the same columns. v1 alone has `error_code`.
- Rows turned away carry their row numbers (a test in
  `tests/v2/test_row_numbers.py`).
- Still different from v1, and in the README: what pandas reads that v2's
  readers do not (dates in any spelling, any text as true), and two pairs
  that read one column.
