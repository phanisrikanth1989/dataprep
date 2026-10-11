# 69 - File output positional

Status: resolved
Type: task

## Question

Build v1's positional output (`FileOutputPositional`,
`tFileOutputPositional`) on v2: every column written to a fixed width,
padded or cut. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/file/file_output_positional.py`. Each entry
  of `formats` names a column with its `size`, `padding_char`, `align`
  (L, R, C) and `keep` (A all, L left, M middle, R right: what stays of a
  value longer than the size).
- Talend's own component (Talaxie `tdi-studio-se@639d5fd1f776`,
  `tFileOutputPositional_begin.javajet`) and v1 do not agree on much:

  | | Talend (lines) | v1 |
  |---|---|---|
  | a float | as it prints, `1.5` (473-495) | to 8 places, or the declared ones: `1.50000000` |
  | a Decimal | to its declared places, else plain (493) | through a float, to 8 places when none are declared |
  | true/false | `true` (495) | `True` |
  | a date with a pattern | by the pattern (479) | the pattern is not read |
  | centred, one more pad than fits evenly | on the right (562-571) | on the left when the size is odd |
  | a column name longer than its size, keep A | whole (242-244) | cut to the size |
  | header when adding to a file | only into an empty file (689) | always |
  | no rows | the file is made, empty (660) | no file is touched |
  | `compress` | a zip beside the file, `<name>.zip`, and not when appending (625-656) | gzip under the file's own name |

  v1 also fails outright on a job whose columns are of several types with
  missing values (tried on 2026-10-12).
- Where the two agree, v1 is the answer key: text and whole numbers, pad
  and cut, left and right, the row separator, the encoding, a column of
  `formats` that does not arrive.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_output_positional.py`;
54 tests in `tests/v2/components/test_file_output_positional.py`, 49 of
them written and seen failing before any code).

- Decided here, without asking: where v1 and Talend differ (the table
  above), v2 does what Talend's source does. The project's first rule is
  the same file as Talend, and v1's positional writer is far from it in
  what every file holds (floats to eight places, `True`, dates without
  their pattern). This was read in the source and not run in Talend: it is
  the one decision of this component worth a look by the user, the zip of
  `compress` most of all.
- Held against v1 byte for byte where the two agree: 23 of the 54 tests.
  The others say in a comment what v1 does there and where Talend's rule
  is in its source.
- A value is made text the way the delimited output makes it (one
  function for both), then fitted to its width in the subjob's one pass:
  no row is walked. The header is fitted by the same rule in plain Python,
  and tests hold the two to each other.
- The file is put in its encoding and in place when the whole subjob has
  succeeded, like the delimited output's; a subjob that fails leaves the
  file as it was.
- Mutation check: 48 ways of breaking it; 45 caught at first, and the
  other three (all of the header) after a test each.
- Row counts are held against v1's. No row-number or dropped-row tests: an
  output names no source row and drops none.

Not done: `use_byte`, `usestream`, a dynamic schema (each refused);
`advanced_separator` (not acted on, as in v1); Java's own way of printing
a very large float or a date with no pattern.

## Corrected after review (ticket 71)

- When no entry of `formats` named a column that arrives, one line was
  written for however many rows there were. Every row is written now.
- `align`, `keep` and `padding_char` given as nothing are the defaults (a
  null `align` centred; a null pad gave Polars' own error).
- The trace shows a row as the file holds it (`Write.as_text`).
- Two of Talend's ways with `compress` are not followed, and a float that
  declares places is rounded before it is written: both in the README now.
