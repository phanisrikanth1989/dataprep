# 123 - Oracle row

Status: resolved
Type: task

## Question

Build the Oracle row (`OracleRow`, `tOracleRow`): one statement, run
once, or once for each row of a flow. To
[Databases: the decisions](118-databases-the-decisions.md).

## What is known

- In Talend the statement is a Java expression worked out again for
  each row, so that `"... where id = " + row1.id` is another statement
  every time. v1 runs the statement once, whatever leads to it.
- The sample in the repo has a row with a flow from it and none to it,
  and a commit at the end of that flow.
- Tried against the real Oracle: a statement run for many rows with
  values out, a block of PL/SQL that defines storing what waited, and a
  statement that defines taking no bound value.

## Answer

Built on 2026-10-12: `src/v2/components/database/oracle_row.py`.

- **Once**, when a trigger sets it off; **for each row** when a flow
  leads to it, a batch of rows in one round trip.
- **The statement reader learned two things.** A column of the row
  named where the statement is joined (`row1.id`) is a value that each
  row brings, and is always bound. A prepared statement has a mark for
  each value it is given.
- **The engine learned one thing**: an action may hand on a row of its
  own, for a flow that leaves it. What follows that flow is checked
  when the job loads.
- Docs: "Oracle row" in `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **For each row means one statement and the rows as its values**, not
  a statement for each row. So a value of a row is bound wherever it
  stands, also outside quotes, where a context variable has to be a
  name or a number. Where it stands in place of a name, Oracle refuses
  the statement, and says so.
- **The rows are held in memory while the statement runs.** It needs
  them in hand to send them, and to hand them on. For millions of rows
  an output is the component.
- **A statement that defines is not run for each row**, and is refused
  on a session with work that waits, as the output's table actions are.
- **A block of PL/SQL that stores what waited is told afterwards.**
  What a block does cannot be seen before it runs. The session is asked
  after it whether anything still waits.
- **A value given for a mark is made the kind its place names**,
  whatever kind it was when it was looked up. A column of the row is
  bound as it is.
- **Java in a value for a mark refuses the job when it loads.**
- **With a flow from it and none to it, it hands on one row with
  nothing in it**, as Talend does.

### How it was tested

- 15 more tests of the statement reader: 11 seen failing first.
- 42 tests of the component on SQLite. 32 were seen failing first, with
  the component taken away; the others came with the coverage gate and
  the mutation check.
- 7 tests against a real Oracle: once and for each row, a prepared
  statement, a statement that defines with a value in it, a block that
  stores what waited, and **the converted sample run as it is but for
  its password**, twice.
- The stand-in database was made to store a statement that defines at
  once, as Oracle does. Before that it did not, and a test that passed
  on it would have told nothing.

### Mutation check

48 ways of breaking it. 42 were caught at first. The six others got a
stronger test: no warning where nothing was stored by itself, the first
refused row across round trips, parameters that are not read without
their switch, the kind of a value that was looked up, the columns named
in a failure, and the check of what follows the row it hands on. One of
them changed the code: a looked-up value kept its own kind whatever its
place said, and is now made that kind.

All were run again, and were caught.

**For the user's eye**

- **A converted job whose statement is Java beyond joining is refused.**
  `"... " + TalendDate.formatDate(...)` has to be rewritten: v2 runs no
  Java.
- A `Blob`, `Clob`, `Bytes` or `Time` for a mark is refused.
- No reject flow: with `die_on_error` off the refused rows are counted
  and told, and not handed on.
