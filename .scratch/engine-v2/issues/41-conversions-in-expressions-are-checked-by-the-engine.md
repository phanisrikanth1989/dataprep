# 41 - Conversions in expressions are checked by the engine

Status: resolved
Type: task
Blocked by: 40

## Question

A conversion written in an expression (`int()`, `float()`, `strptime()`)
fails a job through a Polars error that names the value and no row. Have
the engine make the check, so that the row is in hand and can be named.

## What is known

- Tried on 2026-10-07: the conversion made without raising, a row flagged
  when its text was there and gave no value, and one small plan beside the
  job: 0.17 s against 0.17 s on a million rows, and the count, the first
  row, its value and its key in the pass that fails today
  (`research/probes/probe_row_number_and_checked_conversion.py`).
- What can fail on a row is a short list in
  `src/v2/expressions/functions.py`: `int()` and `float()` of text, and
  `strptime()`.
- Which rows count as failed is the heart of it: the ones Python would work
  the conversion out for. `a and int(x)` does not for a row where `a` is
  false. Today v2 fails such a row and v1 does not:
  [A conversion guarded by `and` or `or` fails on v2 and not on v1](39-a-conversion-guarded-by-and-or-or-fails-on-v2.md).
- The map translates expressions in five places, each over rows of its own:
  an input's filter, a lookup's keys, the variables, an output's filter, an
  output's columns. Filter rows translates its advanced condition.

## To build

- The translator makes these conversions without raising and notes, for
  each, the flag "this row failed", what was converted and under which
  conditions it is worked out at all (`and`, `or`, `if`/`else`).
- The component that asked for the translation checks the flags on the rows
  the expression runs on, and fails as today when any is set, with the
  expression, the value, how many rows, and the first row's place.
- A conversion in a map column nothing reads fails the job too, as in v1.
  The README's line on that changes.
- Tests against v1 for every guard, and ticket 39 is resolved with it.

## Answer

Built on 2026-10-07 (`Translator.fallible` in
`src/v2/expressions/translate.py`, `Component.check_conversions` in
`src/v2/components/base.py`; tests in `tests/v2/test_conversions.py`).

- Checked by the engine now: `int()` of text, `int()` of a float that is
  not a number or too large, `float()` of text, `strptime()`.
- A row fails only where Python works the conversion out: not after a false
  part of an `and`, a true part of an `or`, or in the branch of an `if` not
  taken; and in a map only on the rows the expression runs on (an output's
  columns on the rows that output takes, an output's filter on the rows it
  is offered).
- The message: "outputs[0].columns[1].expression: int() could not read
  'x320' (in: int(row1.code) + 1); 2 rows failed; the row is line 3 of
  row1.csv (id=2)". The value is the one the conversion was handed, cut at
  100 characters.
- A conversion in a map column nothing reads fails the job, as in v1.
- A component that translates a conversion and does not check it fails the
  job with "conversions were translated and never checked", so none turns
  into a missing value silently.
- Held against v1 on five guarded and three unguarded-in-a-branch cases
  that v2 failed or could have failed before, and on five that must fail.

Left as they were: `round()`, `math.floor()`, `math.ceil()` and
`math.trunc()` of something that is not a number still raise in Polars.
A missing value handed to a conversion stays missing, as before.
