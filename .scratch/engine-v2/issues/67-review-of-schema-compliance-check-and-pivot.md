# 67 - Review of schema compliance check and pivot to columns delimited

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran the schema compliance check and the
pivot to columns delimited (tickets 63 and 64, as at commit d37d5297)
against v1 on inputs their tests did not cover. What did it find, and what
is done about each?

## What it found (2026-10-12)

Twenty-nine findings; the reviewer ran both engines on each. In short:

Pivot to columns delimited
1. Sums of floats carried noise v1 does not have (`0.6000000000000001`).
2. A whole float of 2^63 or more, and `inf`, were written as empty cells.
3. A group whose values are all missing is a row in v2 and none in v1
   (min, max, first, last).
4. A Decimal column with missing values: sum, count and the header differ.
5. A Decimal with no declared places was padded to ten places.
6. Row order when a group's first row has no pivot value.
7. `NB_LINE_OK` was the rows read; v1 has the groups written.
8. sum of text or true/false is refused; v1 runs it.
9. A date cell with no pattern lost its time of day row by row.
10. Smaller: a row separator of nothing; `create` as text; grouping by the
    pivot column; `"` as the field separator.
16-18. Raw errors: group column named twice, pivot column among the
    groups, a pivot value named as a group column; an encoding failure in
    the codec's words; a `filename` that is a folder.
19-21, 24. Claims: "v1 fails when no cell is empty" is backwards, and the
    test that said so ran a case v1 passes; the docstring's "as in v1"
    for sums over nothing; the trace of a pivot lists the rows read.
26-28. Tests that could not fail, and no entry for the pivot among the
    row-count and `run.only` tests.

Schema compliance check
11. `strict_date_check` took values v1 turns away, and once the reverse.
12. An empty Decimal with `all_empty_are_null` off.
13. The key `pattern` was read as `date_pattern`; v1 never reads it.
14. Smaller: a number behind a no-break space; `length` as text; a
    charset that cannot hold a character; the length of typed values; a
    date pattern on a column of whole numbers; two refusals v1 passes.
15. Seen through it, the engine's own: a 20-digit number or `inf` into a
    whole-number column goes missing.
22-23. Claims: "differs from v1, both in the README"; what `die_on_error`
    does.
25, 29. Eight ways of breaking the check that no test noticed, and a
    helper that took any one-line reject file.

## Answer

Done on 2026-10-12, each fix with a test seen failing first.

Fixed:
- 1: floats are added exactly, with the aggregate's own sum; Talend adds
  BigDecimals (`tPivotToColumnsDelimited_main.javajet`, Talaxie
  639d5fd1f776), so that is Talend's answer too. v1's sum has a running
  correction and agrees on ordinary data.
- 2, 5, 6, 7, 9, the row separator of 10: as v1 has them.
- 16: refused at load, or failed in plain words.
- 17: the engine now words it for every file output: `'日本'
  cannot be written in the file's encoding`.
- 11: the date check is written out as pandas reads a pattern (its own
  reader for ISO 8601 patterns, Python's for the others) and held to
  pandas itself over 29 patterns and some 180 values. Two things are not
  the same and are in the README: digits of another script, and patterns
  with parts not written out. One value could not be explained and is
  left out of the test: `000012` under `%Y%m%d`, year 0.
- 13, the no-break space, the typed lengths and the date pattern on a
  column of numbers of 14.
- 19-23: README, tickets 63 and 64, docstrings and the test corrected.
- 25-29: tests added. Of 43 ways of breaking the two components and the
  fixes, 39 are each caught by a test now. Two are the same thing kept
  twice (the order of the pivot's groups is kept and then sorted again;
  losing both at once is caught) and two were code that could do nothing,
  now removed.
- 27: the pivot's counts are held against v1's; both components have a
  `run.only` test.

Said in the README and left as they are:
- 3, 4, 8, `create` as text of 10, 12, and of 14 `length` as text, the
  charset that cannot hold a character and the two refusals.

Not done:
- 15 is the engine's and known (a number too long for 64 bits goes
  missing in a whole-number column).
- 18: a `filename` that is a folder fails with the operating system's
  words and the name of the engine's working file in them. Every file
  output has that.
- 24: the trace lists the rows a pivot was handed; nothing says they are
  the lines of the file.
- A `"` as the field separator: v1 fails, v2 writes.
- NaN in the value column of a pivot (v1 `0.0`, v2 `0`).
