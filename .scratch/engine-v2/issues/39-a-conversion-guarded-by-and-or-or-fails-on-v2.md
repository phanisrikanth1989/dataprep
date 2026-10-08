# 39 - A conversion guarded by `and` or `or` fails on v2 and not on v1

Status: resolved
Type: task

## Question

A map expression that protects a conversion with `and` or `or` runs on v1
and fails on v2. Make v2 work it out the way Python does.

Found on 2026-10-07, in a try-out for
[How v2 points at the input row that failed a job](38-how-v2-points-at-the-input-row-that-failed-a-job.md).

## What is known

One input, three rows, `code` holding `10`, `x320` and `30`, on both
engines (v1's PyMap, v2's map):

| Expression | v1 | v2 |
|---|---|---|
| `row1.code.isdigit() and int(row1.code) > 5` | finishes: true, false, true | fails: conversion from `str` to `i64` failed in column 'code' |
| `not row1.code.isdigit() or int(row1.code) > 5` | finishes: true, true, true | fails the same way |
| `int(row1.code) if row1.code.isdigit() else -1` | finishes: 10, -1, 30 | finishes: 10, -1, 30 |

Why: Python stops at the first part of an `and` that is false, so `int()`
never sees `x320`. v2 turns `a and b` into Polars' `a & b`, which works out
both sides for every row, and the strict conversion on the right raises.
The `if` form is safe because Polars works out the branches of a
`when/then/otherwise` only for the rows that take them.

A guard of this kind is a common way to write a Talend expression in Python
(`x != "" and float(x) > 0`), so jobs that run on v1 can fail on v2.

## To build

- The parts of an `and` or `or` after the first are worked out only for the
  rows Python would work them out for.
- Tests against v1 for `and`, `or`, chains of three, and a conversion inside
  a comparison on the right.
- If ticket 38 ends in conversions the engine checks for itself, the same
  rule decides which rows count as failed, and this is built with it.

## Answer

Corrected on 2026-10-07 with
[Conversions in expressions are checked by the engine](41-conversions-in-expressions-are-checked-by-the-engine.md).
The three expressions of the table above, and chains of three parts, now
give v1's rows (`tests/v2/test_conversions.py`).
