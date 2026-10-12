# 125 - Oracle bulk exec

Status: resolved
Type: task

## Question

Build the Oracle bulk exec (`OracleBulkExec`, `tOracleBulkExec`). To
[Databases: the decisions](118-databases-the-decisions.md): no
SQL*Loader, the engine's own reader and the output's own loading.

## What is known

- Talend's component runs `sqlldr` on a file and takes no flow. The
  converter writes it with an input schema; v1 gives it a flow.
- A direct path load commits by itself, whatever the subjob comes to.
- SQL*Loader lets fifty refused rows pass by default, and writes them
  to a file beside the load.

## Answer

Built on 2026-10-12: `src/v2/components/database/oracle_bulk_exec.py`.
It is the Oracle output with another set of keys and another place its
rows come from.

- **With no flow leading to it, it reads the file `data` itself**, by a
  delimited file input it sets with its own keys. Every rule of that
  reader holds: the declared types, the patterns, the line a failure
  names.
- **The engine learned that a sink may read its own rows**, when no
  flow leads to it.
- `data_action` has SQL*Loader's meanings: `INSERT` needs an empty
  table, `APPEND` adds, `REPLACE` deletes first in the transaction,
  `TRUNCATE` truncates first.
- Of the load options four are read: `ROWS`, `SKIP`, `LOAD`, `ERRORS`.
- Docs: "Oracle bulk exec" in `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **Without `ERRORS`, the first refused row fails the job.**
  SQL*Loader's fifty that pass without a word are no default to keep.
  With `ERRORS` the job says how many it allows.
- **`UPDATE` is refused.** A load updates no rows; the output does.
- **`DIRECT` and the other tuning options are read and change
  nothing.** They tune a loader that is not run. A direct path load
  would store by itself; the rows here are stored with the subjob.
- **A value is stored as the file holds it.** SQL*Loader cuts blanks
  off the end of a field unless told to preserve them.
- **Numbers with other separators, a control file, and record formats
  other than a line a record refuse the job.**
- What is wrong with how the file is to be read is told when the job
  loads, under `data`.

### How it was tested

- 26 tests on SQLite: seen failing first, with the component taken
  away.
- 4 tests against a real Oracle: a file loaded, what each action does
  to the rows the table holds, refused rows up to the number allowed,
  a line that cannot be read.

### Mutation check

33 ways of breaking it. All were caught at first.

**For the user's eye**

- **A job that leaned on SQL*Loader passing bad rows by now fails on
  the first.** Say `ERRORS` in its options, or `die_on_error` off.
- **Speed is that of batches of rows, not of a direct path load.** It
  was not measured at the dev's sizes. If it is not enough, a direct
  path load is the thing to build, with its commit said plainly.
- The file's fields are trimmed by nobody: a job that leaned on
  SQL*Loader's trimming gets the blanks.
