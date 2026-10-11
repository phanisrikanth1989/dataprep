# 84 - Review of properties input, file row count, die, warn, set global var and the action kind

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran the five components of tickets 75
to 80 and the engine's new kind of component (as at commit 65b7917e)
against v1, and the properties reader against Java itself. What did it
find, and what is done about each?

## What it found (2026-10-12)

Sixteen findings, and twenty ways of breaking the five that no test
noticed (82 tried).

1. A die did not stop the job. It was recorded as a failed subjob, and
   whatever came after it ran.
2. A RunIf leaving a component before a set global var was judged with
   that component's entries already there.
3. The properties reader against Java itself (4,047 files): a malformed
   `\u`, and a line that is only a backslash.
4. A typed value that cannot be read goes missing without a word.
5. v1's wide row is not v1's for an ini file. 6. A section named twice.
7. Smaller: die's counts, null config values, `die_on_error` refused on
   four components, a warn or set global var with a flow out and none in,
   the line a duplicate key is named by.
8. Java's surrogate pairs broke the reader.
9. The same-subjob check of set global var fired on any quoted word.
10. Raw Python errors: `variables: null`, a null key, a folder as the
    path.
11. A die's message lost its own characters in the failure's text.
12-16. Claims: "stops the job as in v1"; "row by row" in v1; "as Java
    reads one"; the reach of the same-subjob check; the guide's words on
    an action.

## Answer

Done on 2026-10-12, each fix with a test seen failing first.

Fixed: 1 (a component can say that its failure ends the job; the runner
stops there), 2 (a component says which free keys it put; a trigger
judged before it is done does not see them), 3, 6, 8, 9, 10, 11 (the
engine writes what is beyond ASCII in a failure's text as its escape,
for every component), and of 7: `die_on_error` is taken by the four, a
warn or a set global var that is to hand rows on with no flow to it
refuses the job, a duplicate key is named by the line of the value that
stays.

One test of the engine's held the old `?` for a character beyond ASCII
in a failure's text (`tests/v2/unit/test_edges.py`); what it guards is
that the text is ASCII, which still holds, and it holds the escape now.

Said in the README and left as they are: 4, 5.

Claims corrected: 12 to 16.

Tests: one for each of the twenty, and 39 ways of breaking the fixes and
the reviewer's own, each caught.

Not done: a die's own row counts (v1 counts one row; a job that died
says no counts); a null written for a number of die or warn takes the
default where v1 fails.
