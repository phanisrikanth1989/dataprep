# 41 - Conversions in expressions are checked by the engine

Status: ready-for-agent
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
