# 127 - Review of the database group

Status: resolved
Type: task

## Question

Have the eleven database components read by someone who did not write
them, before they are pushed: as the file jobs, the loops and the XML
group were.

## What was done

- One reviewer read a snapshot of the tree at `55ed6581`. It could run
  things from the snapshot and against the two scratch databases (Oracle
  23, SQL Server 2022), and could change nothing.
- Each finding was looked for on the live tree before anything was
  changed, and each fix has a test that was seen failing first.
- Looking for them turned up seven more faults of the same kinds, which
  the reviewer had not listed. They are fixed here too.

## What the reviewer found

1. **A value in a remark could end the remark and change the statement.**
   A value outside quotes may be a text in quotes; inside a remark quotes
   mean nothing, and its `*/` or its line break ended the remark. Shown
   on both real databases:
   - Oracle input: `select ... /* run for ${context.who} */ where n = 1`
     read the rows of a table the query never named.
   - Oracle row: `delete from t where n = 2 -- asked by ${context.why}`
     deleted every row.
   - SQL Server input: a query with `-- ${context.note}` dropped a table.
   - A statement that defines made a table with a column nobody wrote.
2. **A statement the database refused, with `die_on_error` off, made the
   job fail when it ended**, on the session of a connection: the row had
   said its work waits before it ran the statement, and never took that
   back.
3. The tests could not see either: the remark tests used values the
   grammar refused anyway, and the `die_on_error` tests all had a commit
   after them.
4. A host no one knows left the Oracle session as the system's own
   error, without the words every other failed session has.
5. The row sent a statement with nothing of the row in it once for each
   row, a round trip each.
6. The docs said a log never shows a value. It shows what was written
   into the statement.

## What looking into them found besides

- **A list over two lines did the same as finding 1 with no quotes at
  all**: `select a -- ${context.note}` with `x`, a line break and
  `, secret_col` selected one column more.
- **A number below nought after a minus of the statement's own made a
  remark of the rest of the line**: `where a = b -${context.n} and
  kept = 1` with -1 lost its second condition. No remark was written
  anywhere.
- **A carriage return by itself ends a `--` remark in SQL Server, and
  not in Oracle.** Asked of both servers; the reader had one rule.
- **The Oracle row, run for each row, had only ever worked for an
  insert, an update, a delete or a merge.** A block of PL/SQL or a query
  with a value of the row failed (the driver's DPY-2040). The SQLite
  stand-in takes anything, and the real tests had only inserts.
- **An insert that reads the table it writes gave every row of a batch
  the same value**, without a word: `values ((select max(n) + 1 from
  t), ...)` for three rows stored 2, 2, 2. Sent for many rows at once,
  Oracle works out every row's query from the table as it was before
  the first.
- **The stored procedure named a row that was not at fault**: for a
  call that cannot be compiled it said "line 7", the column of the
  fault in the call's own text.
- Finding 2 had kin: a statement run for each row that changed no row
  or was a query, and an output that took its own work back.

## Answer

Fixed on 2026-10-12.

- `src/v2/statements.py`: **a value that is written into a statement is
  held to one rule wherever it stands**, in the statement or in a
  remark: a name, a number or a list, on one line, with no control
  character and no `/*` or `*/`. A number below nought after a minus is
  kept apart from it by a blank. A `--` remark ends where its own
  database ends it.
- `src/v2/components/database/oracle_row.py`, `oracle_output.py`: a
  component that was refused, that took its own work back, or that
  changed no row takes back the word that its work waits.
- `src/v2/oracle.py`: how a statement is run for each row.
  - An insert, an update, a delete, a merge: for all the rows at once,
    as before.
  - A block or a call: for all at once, and again from the row after
    each one that fails.
  - A query: row by row. Sent for many rows, the driver loses the
    session.
  - An insert of values with a query among them: one row at a time.
  - A statement that takes no value: sent once, with how many times it
    is to run.
  - What cannot be compiled is the statement's fault and names no row.
- A host that cannot be found is said as any other session that was not
  opened.
- Docs: `docs/v2/own-rule/databases.md` says all of it. The page had
  outgrown its 600 lines, so the SQL Server part is now
  `docs/v2/own-rule/sql-server.md`.

### What was decided on the way

- **One rule for every written value, and not one for remarks and one
  for the rest.** Where a remark ends is each database's own to say. A
  value that can end none and start none is safe wherever the reader
  and the database might not agree.
- **A list has to be on one line now.** A list over several lines was
  taken before; it fails with that reason.
- **A blank between two minuses, and no refusal.** `d - -1` is what the
  job means.
- **An insert that reads as it writes costs a round trip a row.** The
  other way is a wrong value without a word. It is told by the words
  `insert`, `values` and `select` in that order; a statement that only
  looks so loses speed and nothing else.
- Finding 5 is fixed and not only said: a statement with no value goes
  as the others do.

### Slips

- **My first fix for the wrong row asked the driver to compile the call
  first.** On the real driver that says nothing of a block. It now goes
  by Oracle's own numbers for what cannot be compiled.
- **A real test of mine passed by accident**: two rows, and a fault at
  "column 7" names no row there is. It has forty rows now.
- **My first real test of finding 1 carried a value the old reader
  refused anyway.** Corrected, and then seen to break the old reader.

### How it was tested

87 tests more.

- 47 of the statement reader: 35 seen failing first; 12 hold what must
  still be taken.
- 14 of the Oracle session, against the stand-in driver. Seven were
  seen failing first, six of them twice: before the first fix, and
  before the one that works.
- 15 of the row and the output on SQLite: 9 seen failing first; the
  others hold what must still wait, and came with the mutation list.
- 11 against the real databases. With the code as it was committed,
  ten of them fail: the three attacks of finding 1 did their damage,
  the minus made its remark, and six of the others failed. With the
  fixes all 67 pass on Oracle and 62 on SQL Server.

### Mutation check

41 ways of breaking the fixes: all caught at first. The 139 of
[SQL Server connection and input](126-sql-server-connection-and-input.md)
were run again on the tree as it is: all caught.

**For the user's eye**

- **The hole of finding 1 was never pushed.** It was in the statement
  reader of tickets 121 to 126.
- **A job whose context value is a list over several lines fails now**,
  and says so. Put the list on one line.
- A query run for each row costs a round trip a row. So does an insert
  that reads the table it writes.
- **What is written into a statement shows in the log**, with the
  statement: a table's name, a number, a list. Only bound values never
  do. A password written into a statement outside quotes would show.
- A second pass over the fixes, by the same reviewer, was asked for.
  What it finds is under "The second pass".
