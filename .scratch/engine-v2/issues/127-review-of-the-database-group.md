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
- The second pass, below, found more. **Three things in it change what
  a job does**; they are under its own "For the user's eye".

## The second pass

The same reviewer read the tree with the fixes above, and was asked to
break them. While it did, I read the fixed code again myself.

### What the reviewer found

- **The four fixes hold.** It could not make a value change a statement
  on either database, could not get real work forgotten, and found the
  new way a statement is run for each row right, on the real Oracle.
- One note on speed: an insert of values with a query among them goes
  one row at a time also when the query reads another table, or when
  the word `select` only stands in a text. Kept as it is; why is under
  "What was decided".
- One note it did not count: a block that commits and then fails stored
  what waited, and no warning said so. Fixed.
- It could not try a session the database closes: it was not to touch
  the containers. I tried that with the scratch Oracle's own
  administrator. Two of the faults below came from it.

### What my own reading found

1. **A text written `q'!'...'!'` could be ended by a value.** Such a
   text starts with a quote. The reader took the mark and that quote
   for the end of the text, and wrote the value in as if no quotes
   stood round it. Shown on the real Oracle: a query read a column it
   never named. In the reader since ticket 121; never pushed.
2. **A text written `q'[...]'` at the start of a line, after a line that
   ends in a word, was taken for a plain text.** The check for "a word
   stands before the q" also took a line break for the end. Found by
   holding the reader beside the driver's own reader, place by place.
3. **Work that waited on a session the database closed was lost without
   a word.** A statement with `die_on_error` off failed on the closed
   session, the job went on, and a close after it had "nothing to fail
   on". The job ended as one that had succeeded; the rows of the
   components before were never stored.
4. **A session closed under a block, a query or a call run for each row
   was blamed on rows.** Every row after it was said to be refused; a
   call named the first row of its batch.
5. **A block run for each row that commits, refused for one row, told
   the job only `ORA-01086`**: that the place marked before it was
   gone. Not why, not which row, not that the other rows stay stored.
6. Run for each row, a statement that stored what waited said nothing
   of it. Run once, it did.
7. A name that was never used stood in the stored procedure. Gone.

### Answer

Fixed on 2026-10-12.

- `src/v2/statements.py`: the mark that opens a `q'...'` text is read
  with its quote, and never ends the text. A word before the q counts
  only when it stands right against it.
- `src/v2/sessions.py`: work that waited on a session the database
  closed is kept as lost. A close of that session fails and says whose
  it was, unless it was to roll back anyway; so does the end of a job.
- `src/v2/oracle.py`: a failure that leaves the session closed is the
  statement's own, for a block, a query and a call. No row is named,
  and no row after it is tried.
- `src/v2/components/database/oracle_row.py`: the warning that a
  statement stored what waited is said for each row too, and also when
  the statement failed after it. What could not be taken back is said
  beside the reason and the row.
- `tests/v2/database.py`: the stand-in fails a commit and a rollback on
  a closed session, as the real driver was seen to.
- `tests/v2/oracle/test_reader_beside_the_driver.py`: the comparison
  that found fault 2, kept as a test against the real Oracle. About
  100,000 small statements, each place of each.
- Docs: `docs/v2/own-rule/databases.md`.

### What was decided

- **A close over work that was lost fails.** Ticket 119 had it the
  other way ("a close has nothing to fail on"). Rows that were said to
  be stored and are not must never end as a success.
- **A close that was to roll back says nothing of lost work.** The job
  asked for that work to go.
- **The insert that reads as it writes stays one row at a time, lookups
  of other tables too.** v2 cannot know what a view or a function
  reads. A wrong value without a word is worse than a slow run, and a
  round trip a row is what Talend's own component costs for every
  statement. Not built: sending such an insert inside a block, which
  would be one round trip a batch. Values behave differently inside
  PL/SQL (a text over 32,767 characters, a true/false), so it needs
  trying of its own.

### What was learned of the driver

- After the database closes a session, python-oracledb 26.0.1 still
  says a transaction is open on it. A statement on it fails with
  `DPY-4011`, and everything after that with `DPY-1001`, a commit and
  a rollback too. Closing it is safe.
- Its own reader takes any `q'` for the start of such a text, also
  after a word (`xq'...'`). Oracle takes the word, as v2's reader does.
  No statement Oracle accepts has a word against a quote, so nothing
  follows from it.
- Oracle takes a colon after a bound value for the start of another:
  `json_object('${context.k}' : 1)` fails (`ORA-01745`, or the driver's
  `DPY-4010`). The word `value` in the colon's place works. Found while
  the two readers were held side by side; it is in the docs now.

### Slips

- **My first comparison "on the tree before the fix" ran on the tree
  with the fix.** Python looked for the code beside the script first.
  It proved nothing of the old tree. The tests were seen failing
  against the old code instead, and the mutation check holds the
  comparison.
- **My first test of fault 3 made the stand-in end its transaction when
  the session died.** The real driver does not, so the fix looked as if
  it did nothing. The stand-in now answers as the driver was seen to.
- Not every test was seen failing one by one: 21 of the 40 were. The
  others hold what must stay as it is, or were written after the code;
  the mutation check holds those.
- A session of Oracle's own client (thick mode) is now asked whether a
  transaction is open after the database closed it. Not tried: no
  client was at hand.

### How it was tested

40 tests, one of them in place of the test that held the old decision:
39 more.

- 9 of the statement reader, 6 seen failing first.
- 7 of the sessions, 4 seen failing first.
- 4 of the Oracle session against the stand-in driver, 3 seen failing
  first.
- 14 of the row on SQLite, 7 seen failing first.
- 6 against the real Oracle. The first was seen failing; four were
  written after probes had shown each fault on the real database; one
  holds what the docs say of JSON's colon.
- Gate: 8,396 passed, 105 modules at 95% or more. Real Oracle: 73
  passed. Real SQL Server: 62 passed.

### Mutation check

36 ways of breaking these fixes. 35 were caught at first. The one that
was not: the comparison beside the driver did not hold the line-start
case, which only the unit test did. Its statements were widened, and it
is caught there now.

**For the user's eye**

- **A job that lost its session with work waiting on it fails now**,
  at the close or at its end, and says whose work was lost. Before, it
  could end as a success.
- **A statement that commits by itself cannot be taken back by v2.** A
  block run for each row, refused for one row: the others stay stored.
  The failure now says so.
- A `q'...'` text takes no value, as before. Two shapes of it that
  were misread are read right now.
