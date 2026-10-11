# 62 - Review of the first five new components

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran replicate, sample row, split row,
replace and convert type (tickets 53 to 57, commits bf2f68b6..4bc4918c)
against v1 on inputs their tests did not cover. What did it find, and
what is done about each?

## What it found (2026-10-11)

Faults, most serious first:

1. Replace blanks every value of a date column that has a pattern, also
   where no rule matches: the date is searched as `2024-01-31 00:00:00`,
   which the engine cannot read back by the pattern. v1 searches
   `2024-01-31`.
2. Convert type turns away every row whose source column is a date or
   true/false, for the same reason.
3. Convert type to a whole number cuts a fraction off (`1.5` gives 1) where
   v1 turns the row away. Other values differ too (`nan`, `inf`, dates in
   several spellings, true/false from `10` or `x`).
4. Convert type took `die_on_error` for another spelling of `dieonerror`.
   In v1 they are two keys: its base class reads `die_on_error` for a
   missing value that is not allowed. `empty_to_null` is no v1 spelling.
5. Split row turns a column made of values of several kinds into one
   Polars type (a date becomes a number, true becomes `true` or 1) where
   v1 writes each value as it stands.
6. Replace refuses `${context.x}` in an advanced pattern: it is compiled
   before the context value is put in.
7. `die_on_error` is not declared on replicate, sample row, split row and
   replace, so a job that gives it is refused. v1's base class reads it on
   every component.
8. A pattern that can match nothing (`x*`) is replaced once more by v1
   than by v2 after a match.
9. Other differences in advanced patterns between Python and Polars
   (`[a[b]c]`, `[a&&b]`, `\<`), and in replacements (`\0`, `\101`).
10. The README names look-around and back-references only; more valid
    Python patterns are refused (`\Z`, `a{,2}`, `(?#c)a`, ...).
11. `\g<a>` in a replacement raises an IndexError out of `load_job`; a
    replacement of null fails with `config: 'replacement'`.
12. Two pairs of convert type that read one column: v1 fills the last
    output column only, v2 both.
13. Sample row refuses ranges v1 runs (`+3`, `1_0`, `,`), and two bad
    values give raw errors. Under `run.only` its places are counted among
    the picked rows, which the README does not say.
14. Small: replicate's `output_count` out of v1's range runs on v2; split
    row with no groups counts its input rows where v1 counts none; none of
    the five is in `tests/v2/test_row_counts_against_v1.py`.

Tests that could not fail: replace's default for `case_sensitive`;
convert type's reject rows carrying row numbers, its fallback to the
source column's declared type, its reading of a missing value, and its
guards for an input that already has `error_code`.

Found sound: replicate; sample row on 28 range forms; split row's literal
forms and order; 550 of 560 combinations of replace's simple mode; convert
type's whole numbers and floats from text; every converter key declared;
no row-by-row code.

## Answer

Each fault was reproduced as a failing test before it was fixed
(2026-10-11). What was done is in each component's ticket, under
"Corrected after review": [Replicate](53-replicate.md),
[Sample row](54-sample-row.md), [Split row](55-split-row.md),
[Replace](56-replace.md), [Convert type](57-convert-type.md).

- Fixed: 1, 2, 3 (the fraction; the other values are said in the README),
  4, 5, 6, 7, 11, 13 and 14.
- Said in the README and not changed: 8, 9, 10 (Polars' regular
  expressions are not Python's) and 12.
- The tests that could not fail can now: undoing each fix in a scratch
  copy makes a test fail.
- Seen on the way, and v1's doing too, so left: text that cannot be read
  as a column's declared type goes missing without a word, also in a
  column that may not be missing (the check for a missing value comes
  before the value is read as its type, in v1 and in v2).

What this taught, for the components still to build: test every component
on every column type, dates and true/false above all; declare
`die_on_error`; hold the row counts against v1; and have the review before
the next component is started, not after five.
