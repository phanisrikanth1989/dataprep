# 124 - Oracle stored procedure

Status: resolved
Type: task

## Question

Build the Oracle stored procedure (`OracleSP`, `tOracleSP`): a procedure
or a function called once, or once for each row of a flow. To
[Databases: the decisions](118-databases-the-decisions.md).

## What is known

Tried against the real Oracle before it was built:

- Many calls go in one round trip, and what each handed out is read by
  its place. A number asked for as a Decimal comes out with every
  digit (thirty were tried); left to itself the driver makes it a float.
- Text comes out up to 32,767 characters, a `CLOB` whole (40,000 were
  tried), a `DATE` and a `TIMESTAMP` as a moment.
- A call that fails in the middle says which one it was.
- **A savepoint alone counts as an open transaction**, to the driver
  and to the database itself.

## Answer

Built on 2026-10-12: `src/v2/components/database/oracle_sp.py`.

- Once when a trigger sets it off, for each row when a flow leads to
  it, 10,000 calls a round trip.
- `IN` takes the row's column, `OUT` puts what comes out into its
  column, `INOUT` does both; a function's value goes to
  `return_column`.
- What comes out is made the kind its column is declared, and rounded
  to its places.
- Docs: "Oracle stored procedure" in `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **A call counts as work that waits.** What a procedure changed cannot
  be seen from outside. On the session of a connection a commit has to
  follow, or the connection commits by itself.
- **A statement that changed no row takes its word back** (this is the
  Oracle row's, found here). The engine marks a place on a shared
  session before a component changes anything, and Oracle counts that
  place alone as an open transaction. So a query run by an Oracle row,
  with no commit after it, would have ended the job with "work that was
  never stored". A plain statement that says it changed no row now
  leaves nothing waiting. A block of PL/SQL and a procedure still do.
- **A cursor that a procedure hands out is refused.** Talend puts it in
  a column for another component to read, which v2 does not have.
- **A true/false goes in as 1 or 0.** PL/SQL has a true/false of its
  own, which is no number, and the driver would hand it over as that.
- The rows are held in memory while the calls are made.

### Found while testing, and fixed before it was committed

**A moment that came out went missing unless its pattern happened to
fit.** The values out were first made into columns by the helper the
fixed flow input uses, which reads a moment as text by the column's
pattern. The test against the real Oracle passed only because the
moment it used had a fraction of a second, and the pattern had one. A
test with other kinds of value showed it. The columns are made from the
values as they are now.

### How it was tested

- 17 tests of the component, with a stand-in for the calls (SQLite has
  no procedures): 15 seen failing first, with the component taken away.
- 3 tests of Oracle's part with a stand-in driver, written with their
  code.
- 5 tests against a real Oracle: values in and out for each row with a
  `CLOB` of 40,000 characters, a function, a call that fails and what
  the others changed taken back, a procedure that is not there, the
  session's language.
- For the Oracle row: 5 more tests of a statement that changed no row.

### Mutation check

43 ways of breaking it. 39 were caught at first. Of the four others,
one showed code that did nothing, and it went (a date with a time of
day is cut to its day by the column itself), and three got a stronger
test: no warning where the procedure stored nothing by itself, a
true/false going in as a number, and the component's own connection
block.

All were run again, and were caught.

**For the user's eye**

- **A function that only reads still needs a commit after it on a
  shared connection**, or `auto_commit` on the connection. The engine
  cannot tell it from one that writes.
- Not built: a cursor out, a STRUCT or an ARRAY, a `BLOB`, an `XMLTYPE`
  or a date with a time zone coming out.
