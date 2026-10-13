# 77 - Review of the four extract components

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran extract delimited, positional,
regex and JSON fields (tickets 70, 72, 73 and 74, as at commit 35bca5b7)
against v1 on inputs their tests did not cover. What did it find, and what
is done about each?

## What it found (2026-10-12)

Eighteen findings, and fifteen ways of breaking the four that no test
noticed (67 tried). Both engines were run on each.

1. JSON: a loop path that cannot be followed on a document (an index into
   an object) failed the whole job with the message `0`.
2. Delimited: a separator given as nothing reached Polars.
3. Positional: a width beyond 64 bits reached Polars.
4. A pattern, a regex or a mapping given as nothing was refused in
   Python's words under the key `config`.
5. JSON told of dropped rows also when the subjob failed.
6. Positional with no output columns declared: v1 makes `field_1` and so
   on, v2 extracted nothing.
7. A missing Decimal source: v1 holds it as empty text.
8. Regex: patterns both engines take and read differently.
9. Regex: patterns v2 refuses beyond the two kinds the README named, each
   with a reason that was wrong for it.
10. Dates not written by their column's pattern: v1 reads them when no
    date of the column fits the pattern. ISO moments with a `T` went
    missing from JSON.
11. The reject output's columns when a column may not be missing and the
    job is not to die.
12, 13. Smaller differences of values and refusals.
14-18. Claims: two in ticket 74, one in ticket 70, the README's on regex,
    and the JSON component against `tell_dropped`'s own word.

## Answer

Done on 2026-10-12, each fix with a test seen failing first.

Fixed: 1, 2, 3, 4, 5, 6. Of 8: the constructs the two read differently
inside `[...]` and `\<`, `\>` refuse the job now (Python itself warns of
the same ones). Of 9: the reason is Polars' own words and no guess. Of
10: a date in JSON may be written the usual ways, ISO with a `T` among
them, in a column with a pattern or without (the rows a job config
writes read the same). Of 12: not-a-number is missing.
A component that has its rows in hand tells of dropped rows the way the
others do (`Component.tell_rows_dropped`): once the subjob has finished.

Said in the README and left as they are: 7, the rest of 8 and 9 (word
characters, Turkish i, a group repeated around nothing), 10 for the
three components whose pieces the engine reads, 11, the rest of 12, 13.

Claims corrected: 14 to 18.

Tests: one for each of the fifteen, and 34 ways of breaking the fixes and
the reviewer's own, each caught (one after a test more).

Not done: 11 is the engine's (a row the schema check turns away joins
the component's own reject output, whose columns then differ from
v1's).
