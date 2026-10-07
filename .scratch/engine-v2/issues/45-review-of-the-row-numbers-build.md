# 45 - Review of the row numbers build

Status: resolved
Type: task
Blocked by: 40, 41, 42, 43

## Question

Tickets 40 to 43 were built in one go. Before they are pushed: does an
independent read of the build find faults, and are they real?

## Answer

Reviewed on 2026-10-07 by a second reader that had only the code. Each
finding was first reproduced as a failing test, on v1 too wherever parity
was the claim, and then fixed. Nothing was fixed that had no failing test.

Faults that were real, and are fixed:

- **JSON input.** A record a path cannot be followed on (`$.tags[0]` where
  `tags` is a number or an object) failed the whole job. v1 turns that
  record away with `PARSE_ERROR` and what the library said; so does v2 now,
  whatever `die_on_error` says. v2's reject output has every column, v1's
  only the columns read before the path that failed.
- **Map, a job failed that v1 finishes.** A conversion in a variable, or in
  the key of a later lookup, was checked on rows an inner join had already
  turned away. v1 (PyMap and the Java map) never works those out for such a
  row. When an `inner_join_reject` output reads a variable, which v1 does
  not allow, v2 works the variables out for every row.
- **Map, wrong row named.** With unreadable text in two columns of one
  output, the message could show one row's value and name another row.
- **Join.** The reject output lost the row's number when a reject schema
  was declared.
- **Expressions.** A chain of comparisons (`a < b < int(c)`) checked the
  conversion on rows where Python stops early. `np.where(c, int(x), 0)` did
  not check the value it does not pick; Python works out both.
  `.strip()` with no characters did not strip the four separators from
  `\x1c` to `\x1f`, which Python does.
- **Normalize.** Trim used Polars' blanks and not Python's. With a
  separator of several characters and `discard_trailing_empty_str`, `a---`
  cut by `--` gave `a-` (v1: `a` and `-`). A true-or-false or a very small
  float was split as `true` and `1e-7` (v1: `True` and `1e-07`).
- **Messages.** "N rows failed" counted the rows any conversion failed on
  while naming one; it now counts the rows that conversion failed on. A
  field-count failure showed v1's own row count ("- Line: 2") beside the
  file's line ("line 5"); the first is left out of the failure's message
  and stays in a reject file, as v1 writes it. A machine without the
  JSONPath library was told so once for every path, as if each path were
  at fault.
- **A job column named like a hidden one** (`__v2_...`) was dropped
  silently. The check at load refuses it now.

Findings that were not faults:

- An aggregate after a unite, with a group that holds no row of one input:
  no failure, and the message names the inputs that are in the group
  (tested).
- Row numbers under `footer_rows`, a `limit`, `\r` and `\r\n`, kept empty
  rows, a byte order mark, and an Excel sheet with nothing in it: all right
  (ten cases and one added as tests).

A guess of mine that a test caught: I made `int()` and `float()` skip the
same blanks as `strip()`. Python's do not; measured over every code point,
they skip exactly what Polars' `strip_chars()` strips. Put back.

Said in the docs now and not changed: a key column that Polars parses
itself is shown as the number (`7` for `007`), a positional key without its
padding; the plans printed at DEBUG name the hidden columns; the JSON
reader goes through its document in Python.

Verified: 4,515 tests in `tests/v2`, and the per-module coverage gate (40
modules at 95% or more).
