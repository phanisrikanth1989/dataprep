# 65 - Review of four more new components

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran unpivot row, denormalize, aggregate
sorted row and fixed flow input (tickets 58 to 61, as at commit 09e15403)
against v1 on inputs their tests did not cover. What did it find, and what
is done about each?

## What it found (2026-10-12)

1. Denormalize blanks every date of a column that has a pattern: the date
   is put together as `2024-01-31 00:00:00`, which the engine cannot read
   back by the pattern. (The fault ticket 62 found in replace, not carried
   over.)
2. Fixed flow input fails the job on a date written in digits only
   (`20240131` under `%Y%m%d`): the column becomes whole numbers, which
   cannot be turned into a date.
3. Fixed flow input gives a raw Polars error on a whole number beyond 64
   bits (a 20-digit account number), in a column of any type.
4. `run.only` by value gives a raw Polars error on a text column of the
   fixed flow input that holds numbers (`007`).
5. `die_on_error` is not declared on the aggregate sorted row (nor on the
   aggregate row it is built on).
6. Unpivot row: v1 writes `3.0` for a whole-number column also when another
   unpivoted column is a float; the README names a missing value only.
7. Unpivot row and denormalize write a Decimal with no declared places
   padded to ten (`1.5000000000`); v1 writes `1.50`.
8. Unpivot row refuses, in Polars' words, a `pivot_key` that an input
   column is named like, which v1 runs; ticket 58 said both fail.
9. Denormalize with one column named twice loses a column without a word.
10. A column named `__sorted_run` gives a raw Polars error in the
    aggregate sorted row.
11. Fixed flow input refuses `values_config` written as a mapping, which
    v1 reads (the converter never writes it).
12. Differences of the fixed flow input from v1 that the README does not
    list (a date before `\r`, a column mixing dates with and without a
    time, a context variable that does not exist, `nb_rows` as text).
13. The row-count tests for denormalize and the aggregate sorted row
    cannot tell rows read from rows handed on.

Found sound: 43 mutations each made a test fail; every converter key is
declared; row counts on 17 jobs; `rows.combined` after a unite; picking
rows and tracing through all four (fault 4 aside).

## Answer

Each fault was reproduced as a failing test before it was fixed
(2026-10-12). What was done is in each component's ticket, under
"Corrected after review (ticket 65)": [Unpivot row](58-unpivot-row.md),
[Denormalize](59-denormalize.md),
[Aggregate sorted row](60-aggregate-sorted-row.md),
[Fixed flow input](61-fixed-flow-input.md).

- Fixed: 1, 2, 3, 4, 5, 7, 8, 9, 10 and 13.
- Said in the README and not changed: 6 and 12.
- Not done: 11 (a form of config the converter never writes).

One thing a component can ask of the engine came out of it:
`Component.declared(name)`, the column as the component's input declares
it, for what a value's own type does not say (a date's pattern, a
Decimal's places); and two ways to make text of a value inside a job
(`column_types.value_text` and `plain_text`), so that the next component
does not write a date or a Decimal its own way.

What this taught: fault 1 was known from ticket 62 and still got into a
component built at the same time. From here on every component that makes
text of values goes through those two functions, and is tried on a date
with a pattern before anything else.
