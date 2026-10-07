# The v2 engine

v2 runs v1 job configs on Polars. It is pure Python: no Java, no bridge. A
job that runs on v2 writes the same files v1 writes, and what v2 cannot run
it refuses before anything starts, in one report.

- Words used here are defined in [`src/v2/CONTEXT.md`](../../src/v2/CONTEXT.md).
- One page per component, with every config key, is generated from the code:
  `.venv/bin/python scripts/gen_v2_docs.py` writes `docs/v2/components/`.
- To add or change a component, read [Writing a v2 component](writing-a-component.md).

## Running a job

```bash
python -m src.v2 job.json                                  # run
python -m src.v2 job.json --context_param in_dir=/data     # set context variables
python -m src.v2 job.json --check                          # load and check only; run nothing
python -m src.v2 job.json --summary run.json               # also write the summary to a file
python -m src.v2 job.json --row-counts                     # log the row counts of every component
python -m src.v2 job.json --only payments_in:txn_id=654321 # run for one row (see "Running a job for a few rows")
```

That is from the project's folder. From any other folder, start the engine
by its own path, or by a link to its folder. The engine itself needs no
installing for it; the packages it runs on (Polars and the others) do, as
for any run:

```bash
python /opt/dataprep/src/v2 /data/jobs/pay.json
```

A path inside a job config that is not a full path is taken from the folder
the command is started in, as in v1.

| Exit code | Meaning |
|---|---|
| 0 | the job finished |
| 1 | the job ran and a component failed |
| 2 | nothing ran: the job config was refused, or the command line was wrong |

Log lines at INFO and DEBUG go to standard output. Warnings and errors go
to standard error, and so do the refusal report and what is wrong with the
command line: an empty standard error means a clean run. A job that
finished but dropped rows for a fault has a warning there (see "What the
log says"). `--log-level`
names the lowest level that is written (`INFO` unless told otherwise). A
character a stream's encoding cannot write is written as an escape, on
either stream, so no line is lost on a server whose locale is not UTF-8.

A summary of the run is the last thing written to standard output, as JSON
(`status`, `error`, `failed_component`, `failures`, `rows` written by each
output, `counts`, `duration_s`). `--summary FILE` writes it to a file as
well, so that nothing has to pick it out of the log. The file is opened
before the job runs: when it cannot be opened, nothing runs (exit code 2).
It is empty while the job runs, so the summary of an earlier run is never
taken for this one's. If it cannot be written once the job has run (a disk
that filled up), that is said on standard error and the exit code stays
the job's. A job that was not run leaves the file as it was.

`--row-counts` is for looking into a job: it counts the rows of every
component and logs them, one line a component (see "What the log says").
The run takes about three times as long, because every count is one more
plan Polars works through. Without it a run is as fast as it can be and
counts only what the job itself reads.

From Python:

```python
from src.v2 import run_job, load_job, JobRefusedError

try:
    result = run_job("job.json", context={"in_dir": "/data"})
except JobRefusedError as refused:
    print(refused.report.format())      # every problem in the job config, in one pass
else:
    result.raise_for_status()           # raises JobFailedError when a component failed
```

Two environment variables: `V2_ENGINE` picks the Polars engine (`streaming`,
the default, `in-memory` or `auto`), and `V2_TEMP_DIR` says where scratch
files go (files in other encodings than UTF-8 are read through a UTF-8 copy
when they hold more than ASCII).

### Run settings in the job config

A job config can say how it is run, in a `run` block at its top level:

```json
"run": {"log_level": "DEBUG", "row_counts": true, "summary_file": "/logs/pay.json"}
```

| Key | Same as |
|---|---|
| `log_level` | `--log-level` |
| `row_counts` | `--row-counts` |
| `summary_file` | `--summary FILE` |
| `only` | `--only` (next section) |
| `trace` | `--trace` (next section) |

The command line wins over the block, and the block over the default:
`--log-level INFO` quietens a job whose block says `DEBUG`,
`--no-row-counts` and `--no-trace` turn off what the block turned on, and
`--summary ''` writes no summary file. The log level is in force from the
moment the job config is read, while the job loads as well. A run says at
its start which settings are in force and who asked for each:

```
[payments] run settings: log level INFO (command line), row counts (job config)
```

A key the block does not know refuses the job, and so does a context
variable in one of its values (`${context.name}`; what picks the rows under
`only` is data and is taken as written otherwise). v1 runs a job that has
the block and takes no notice of it. The settings that belong to a machine
and not to a job (`V2_ENGINE`, `V2_TEMP_DIR`) are not in the block.

### From a service

A service that holds a request (the job config, context values, run
settings) runs it with one call, in a thread of its own if it likes:

```python
from src.v2 import run_job

result = run_job(job_config, context=context_overrides, run={"row_counts": True})
reply = result.summary()        # plain values, ready to be sent as JSON
```

`context` overrides the job config's context values, and `run` its `run`
block, key by key. `summary()` is what the command prints last. What is
wrong with the job config or with `run` raises `JobRefusedError` before
anything runs. `run.log_level` is put in force on the engine's own logger
(`src.v2`) while the job loads and runs. That logger is one for the
process: while two jobs run at once, its lines are written from the lower
of their two levels, and it is as it was before once both have ended.

## Running a job for a few rows

A failure names its row: `the row is line 654322 of /data/payments.csv
(txn_id=654321)`. The job can be run for that row alone:

```bash
python -m src.v2 job.json --only payments_in:txn_id=654321          # by what a column holds
python -m src.v2 job.json --only payments_in:txn_id=654321,654400   # a few rows
python -m src.v2 job.json --only payments_in:line=654322            # by the place the failure names
```

```json
"run": {"only": {"source": "payments_in", "where": {"txn_id": [654321]}}}
"run": {"only": {"source": "payments_in", "lines": [654322]}}
```

The whole job runs, every stage of it, and writes its files as in any run:
existing output files are replaced by what this run writes, so keep the
ones that matter. The one difference is the reader that is named: it hands
on the picked rows and no others. Every other reader is read whole, so a
lookup finds its match, and a later stage reads what this run wrote.

- **The reader** is named by its component id. Only a reader can be named.
- **By value**: any column of the reader's schema, key or not. (A reader
  that declares no columns is picked by the ones it hands on: `line` for a
  full-row file, the names its paths give for a JSON document.) The value
  is read as the column's type, the way the reader reads the column in its
  file: `007` finds 7, a date is read by the column's pattern, and where a
  positional file writes two thousand as `2.000,00`, so can the asking, as
  the failure shows it. A number written as a number in the block
  (`{"amt": 2000}`) is the number itself. With two columns in `where`, a
  row has to hold both.
- **By place**: the reader's own kind of place, as its failures name it.
  `lines` for a text file; `records` for a JSON document and for a
  delimited file read with `csv_option`; `rows` with `sheet` for a
  workbook (a workbook read from one sheet needs no `sheet`). On the
  command line `line=`, `record=` and `row=`; a sheet, two columns, or a
  value with a comma in it are said as the block itself:
  `--only '{"source": "book_in", "sheet": "Q1", "rows": [3]}'`.
- **At most 5 rows.** Every value and every place named has to pick a row:
  one that picks none stops the run with a message, and so do more than 5
  rows. What is wrong with the asking itself (no such reader, no such
  column, a value that is not the column's type, the wrong kind of place)
  refuses the job before anything runs. One case waits: where the reader's
  config needs a value the job sets as it runs (a context load), what only
  the built reader can tell, its kind of place for one, stops the run when
  the run gets to that reader.
- **A row that is wrong elsewhere in the file does not matter**: the reader
  keeps to the picked rows before it reads any value. A picked row that is
  wrong fails the job, or is turned away, exactly as in the full run. A
  file the reader cannot get through is another matter, and fails this run
  as it fails any: an enclosure that is never closed under `csv_option`, a
  byte that is not of the file's encoding in a full-row file.
- What depends on the other rows sees only the picked ones: a unique row
  finds no repeat, an aggregate makes a group of the picked rows, a row
  count and a `RunIf` on one count them.

The reader is read twice: once to find the rows, once to run them. On the
payments scenario at 1,000,000 rows a run for one row takes 1.4 to 1.6 s.
The summary says which rows were picked:

```json
"only": {"source": "payments_in", "rows": ["line 654322 of /data/payments.csv"]}
```

### What every component did with them

With `--trace` (or `"trace": true` under `run`; it needs `only`), the
summary also holds what every component did with the picked rows:

```json
"trace": [
  {"id": "payments_in", "type": "FileInputDelimited", "outputs": {
     "main": {"rows": 1,
              "columns": [{"name": "txn_id", "type": "int"}, {"name": "amount", "type": "Decimal"}],
              "data": [["654321", "960081.20"]],
              "from": ["line 654322 of /data/payments.csv"]},
     "reject": {"rows": 0, "columns": [], "data": [], "from": []}}},
  {"id": "branches_in", "type": "FileInputDelimited", "outputs": null,
   "why": "its rows do not come from the picked rows"},
  {"id": "enriched_out", "type": "FileOutputDelimited", "path": "/data/out/enriched.csv",
   "written": true, "rows": 1, "columns": [], "data": [], "from": []}
]
```

- Every component of every stage that ran is there, in the order it ran.
- A component whose rows come from the picked rows has each of its outputs:
  how many rows, the columns with their types, the rows, and for each row
  where it came from: the picked row's place, or, in a later stage, its
  place in the file that stage read. A file output has the same for the
  rows it was handed, its path, and `written`: false when its stage failed,
  so that the file was not written.
- Values are text. A file output's are what its file holds. Any other
  component's are written the same way, by the columns it declares (a date
  by its pattern, a Decimal to its places). A column of a kind only code
  can make (a list, a time span) is shown as Python prints it. A missing
  value is `null`.
- An output lists its first 50 rows and says how many it has.
- A component whose rows do not come from the picked rows is not listed row
  by row: a lookup, or a stage that reads another file. It runs as ever. A
  later stage that reads a file this run wrote from picked rows is listed,
  unless rows that were not picked went to that file in this run as well.
  (A file an output appends to is taken to hold what this run wrote, so
  start such a run from a file that is not there.)
- A row the job fails on: the trace goes as far as the failing component,
  which has `"error"` in place of its outputs.
- After user Python a row no longer says where it came from (`null`).

The log has a short version: for each component the rows of each output,
and for each picked row what was added and what was changed (a dozen
columns at most; the summary has them all).

```
[branch_join] trace: main 1 row, reject 0 rows; added region=EMEA-N, cost_centre=CC0260
[prepare] trace: prepared 1 row; added amount_usd=960081.2000, purpose_code=GJQO; changed narrative: SALARY   TRANSFER -> SALARY TRANSFER
[enriched_out] trace: 1 row for /data/out/enriched.csv
```

A traced run takes each such flow's rows in hand between two components,
and reads every file with the tolerant reader from the start. On the
payments scenario at 1,000,000 rows one traced row takes 0.9 s; its summary
holds the 19 components of the stages that ran, in 33 KB of JSON (71 KB as
the command prints it, indented). A printed row holds what
the row holds, account numbers and names among it: that is in the log and
in the summary of a run that asked for it, and of no other.

## Taking a v1 job config to v2

1. Run `python -m src.v2 job.json --check`. The refusal report lists
   everything that stops the job, component by component. A component with
   a fault does not hide the faults of what it feeds: the check goes on
   down the flow with the columns the component declares, and a fault found
   that way says so. Three things are still left for a second look: what
   follows a faulty component that declares no columns (a map, for one, or
   a reader with no schema), what follows a component whose config values
   cannot be read at all, and what follows a component that waits for a
   value the job sets while it runs (a context variable a context load
   sets, a row count).
2. Rewrite every Java expression (`{{java}}...`) in Python. See
   "Expressions" below.
3. Replace or remove components v2 does not have. v2 has eighteen:
   delimited file input and output, positional, full-row, Excel and JSON
   input, filter rows, filter columns, sort row, unique row, aggregate row,
   join, unite, map, normalize, Python dataframe, log row and context load.
4. Deal with refused config keys: each refusal says why.

Everything else stays as it is. The job config keeps v1's shape and v1's
key spellings. Where v2 documents a clearer name (`path` for `filepath`),
v1's spelling is an alias and keeps working; a job config that gives both
spellings of one key is refused. Keys that only made sense to Talend or to
v1's engine (`subjobs`, `java_config`, `position`, tuning knobs) are
accepted and ignored.

## Expressions

Expressions are Python. Each one is translated once, when the job loads,
into a Polars expression that runs on whole columns. Nothing runs row by
row, and Python that has no Polars form is refused at load with the reason.

```python
row1.name[:10].strip().upper()
row1.amount * (1 + context.vat) if row1.country == "FR" else row1.amount
re.sub(r"\s+", "_", row1.label)
Var.total > globalMap.get("limit", 0)
```

- A column is `row1.price` or `row1['price']`; where a component has one
  input the column may also be written bare (`price`). Map variables are
  `Var.name`, context values `context.name`, globalMap entries
  `globalMap.get("name")`.
- Operators, `a if c else b`, `and` / `or` / `not`, `in`, `is None`,
  slicing, the usual string methods, `len`, `str`, `int`, `float`, `round`,
  `abs`, `min`, `max`, and parts of `re`, `math`, `datetime` and `Decimal`.
  The full list is in `src/v2/expressions/functions.py`.
- A missing value does not raise: arithmetic, text operations and ordering
  comparisons on a missing value give a missing value. `==` and `!=` treat a
  missing value as a value (`x == None` is true for a missing `x`), and
  conditions follow Python's truthiness.
- RunIf trigger conditions are read exactly as v1 reads them (Python, with
  `&&`, `||`, `!`, `null`, `true`, `false` and
  `((Integer)globalMap.get("key"))` casts rewritten first), so the
  conditions v1 job configs carry keep working.

### Routines

A job config's `python_config` (`enabled`, `routines_dir`, `routines`) names
a folder of Python files, loaded and named as v1 does: `fee_rules.py` is
`FeeRules`, called as `routines.FeeRules.net(row1.amount)` or
`FeeRules.net(row1.amount)`. In v2 a routine takes Polars expressions and
returns one, so it works on whole columns:

```python
import polars as pl

def net(amount, rate=0.2):
    return amount * (1 - rate)

def initials(name):
    return name.str.slice(0, 1).str.to_uppercase()
```

A routine that calls Python row by row (`map_elements`) is refused. A v1
routine written with plain operators often works unchanged; one that uses
Python string methods or `if` on its arguments has to be rewritten with
Polars expressions.

## How a job runs

- Components joined by flows form a subjob. A subjob is built as one lazy
  Polars plan and run in a single pass: a file is read once however many
  outputs hang off it, and rows are streamed, not held.
- No file of a subjob is put in place unless the whole subjob succeeded.
  Each file is written beside its target. At the end every file is first
  put in its encoding, which is the last thing the rows can fail, and only
  then are the files moved in. A run that is stopped leaves no temporary
  file behind.
- Subjobs run in v1's order: those nothing triggers in job-config order,
  and what a subjob triggers right after it. `OnSubjobOk`, `OnSubjobError`,
  `OnComponentOk`, `OnComponentError` and `RunIf` are supported. Of the
  subjobs one subjob sets off, those of a component's own triggers
  (`OnComponentOk`, `RunIf`) come first, component by component, and those
  of `OnSubjobOk` with the last component; what fires together goes by
  `output_id`. After a failed subjob its error triggers fire and the other
  subjobs still run; the job's status is then `failed`.
- A `RunIf` is judged twice, as in v1: when its own component is done, on
  what globalMap holds by then (the count of a later component of the same
  subjob is not there yet), and once more when the subjob is done.
- Context values in config strings (`${context.x}` and v1's bare
  `context.x`) are resolved when each component is built, so a value loaded
  by a context load in an earlier subjob is seen.
- Row counts: every file output sets `<id>_NB_LINE` in the globalMap. The
  counts of other components (`_NB_LINE`, `_NB_LINE_OK`, `_NB_LINE_REJECT`)
  are taken only when something in the job reads them, or when the run asks
  for the counts of every component (`--row-counts`, or
  `run_job(..., row_counts=True)`). They follow v1's rules: rows read, rows
  passed on, rows rejected; a map counts the rows of its outputs, a join the
  rows of its main input, a full-row input every line of its file.
- After each component the engine makes its output match the declared
  schema, as v1 does: column order, columns nobody produced, types, decimal
  places, and columns that may not hold a missing value.

## What the log says

At INFO:

- when the job starts and how it ended; when each subjob starts, with the
  components it holds, and when it finishes;
- for every file output, the rows it wrote and where;
- for every trigger that fires, its type, the component it leaves and the
  subjob it sets off. A `RunIf` is logged each time it is judged, with its
  condition and what it came to, also when that is false:

  ```
  [job] trigger OnSubjobOk from settings_in to payments_in fired: the subjob of payments_in is set off
  [job] trigger RunIf from rejects_out to rejects_in, judged when rejects_out was done: ((Integer)globalMap.get("rejects_out_NB_LINE")) > 0 is true: the subjob of rejects_in is set off
  ```

With `--row-counts`, one more line for every component when its subjob has
finished, in v1's words. The same numbers are in the summary, under
`counts`, and in the globalMap:

```
[format_check] NB_LINE:4000 OK:3920 REJECT:80
```

At WARNING, and so on standard error: a line for a component that dropped
rows because something was wrong with them, when its subjob has finished.
That is a row a reader could not read or a missing value in a column that
may not hold one, where the component is told to go on (`die_on_error`
off); and a JSON record a path could not be followed on, which is turned
away whatever `die_on_error` says. It is said when no flow takes the
component's reject output. The line has the count, what was wrong with the
first row in the words its reject output would have, and that row's place
and key as a failure has them. A component that dropped rows for two kinds
of fault has a line for each:

```
[payments_in] 1 row was dropped (no flow takes this component's rejects): Column 'amount': could not convert string to Decimal: '9600x81.20'; the row is line 654322 of /data/payments.csv (txn_id=654321)
[orders_in] 3 rows were dropped (no flow takes this component's rejects); the first: Column 'qty': could not convert string to float: 'x'; the row is line 12 of /data/orders.csv
[by_date] 1 row was dropped: Column 'amount': non-nullable column has null; the row is line 7 of /data/orders.csv
```

The job still finishes and writes the same files. A value a message shows
is cut (at 100 characters; a reader's whole reason at 200), and a line
break or any other control character in it is written as an escape (`\n`),
in this line and in the line of a failure.

Nothing is said when a flow takes the rejects (the rows are then in the
job's hands), nothing for the rows a filter, a unique row or a join turns
away (that is the job's own doing), and nothing in a subjob that fails (it
writes nothing, so it dropped nothing). Two more kinds of row go missing
without a word, as they do in v1: an aggregate row leaves out the rows that
have no value in a group column, and a context load skips a row with no
key.

v1 shows a reader's loss as the REJECT count it logs for every component,
for its delimited and JSON readers. A row dropped for a missing value it
counts as passed on, so its log does not show that loss.

The rows are noticed as they pass, which costs little: the payments
scenario at 1,000,000 rows took 0.04 s and 0.08 s longer than before there
was a warning, in two measurements (2.01 s to 2.05 s, and 2.14 s to 2.22 s
on a busier machine). Only a subjob that did drop rows is read once more,
to count them and find the first: 2.24 s with one bad amount in the file.

`--log-level DEBUG` adds what a person needs when a job does not do what
they expected:

- for each component, its config with context values put in and defaults
  filled in, and the columns of each of its outputs with their Polars types;
- for each delimited file input, whether Polars parses the numbers itself or
  every column is read as text, and why;
- for each subjob, whether it may be read a second time, and the plan Polars
  is given: one for every output, for everything a component asked to know
  about the data, and for the rows a component is handed;
- for each file output, the temporary file it is being written to (it can be
  watched growing during a long run) and the encoding it is put in;
- when a subjob is read a second time, what Polars said in full.

None of this is put together unless the level is DEBUG: a run at INFO pays
nothing for it. A plan takes many lines; the payments scenario's job logs
about six hundred lines at DEBUG. A plan Polars cannot print is said to be
so in the log; it does not fail the job.

## Finding the row that failed

When a job fails on a row, the failure's message ends with where that row
is in its source, and the same message is in the log and in the summary:

```
failed at payments_in: Schema/coercion failed for 1 row(s); first error: Column 'amount': could not convert string to Decimal: '12x.50'; the row is line 654322 of /data/payments.csv (txn_id=654321)
failed at prepare: outputs[0].columns[16].expression: int() could not read 'x320' (in: int(joined.operator_id[2:])); 2 rows failed; the row is line 654322 of /data/payments.csv (txn_id=654321)
```

- **The place** is the source's own: a line of a text file, as an editor
  numbers it; `row 3 of sheet 'Q1'` of a workbook; `record 2 ($.orders[1])`
  of a JSON document. A delimited file read with `csv_option` gives the
  record's number and no line: a field may hold a line break there.
- **The key.** Mark a column of the source's schema as key (`"key": true`,
  which is what Talend's key flag converts to) and its value is shown beside
  the place. Several key columns are all shown. The value is shown as the
  reader read it, before any trimming or typing of text, and cut at 100
  characters. Two readers have it changed by then: a number column of a
  delimited file that Polars parses itself shows as the number (`7` for
  `007`), and a positional field shows without the blanks that pad it. The
  place is always given, key or no key.
- **The first row and how many.** `die_on_error` is unchanged: the job
  fails and writes nothing. v2 does not go row by row, so by the time it
  fails it has seen every row: the message names the first row that failed
  and says how many failed the same way (a reader: every row it could not
  read; a conversion: the rows that one conversion failed on).

How it works: every source numbers its rows as it reads them, and the
number travels with the row as a column the job never sees. It is never
written to a file and never handed to user Python. It costs nothing a run
can show (the payments scenario at 1,000,000 rows: 1.9 s with and without).
These columns have names starting with `__v2_`. A job with a column of its
own named that way is refused at load, and the plans Polars prints at
`--log-level DEBUG` show them by name.

What becomes of the number on the way:

| Step | The row that goes on |
|---|---|
| filter rows, filter columns, sort row, unique row, log row, map, unite | keeps its number |
| join | keeps the main input's number; a lookup's is left behind |
| normalize | every row made carries the number of the row it came from |
| aggregate row | carries the lowest number of its group, and the message says "the first of 11,112 rows that were combined" (rows as they reached the aggregate: after a normalize, several of them come from one row of the source) |
| Python dataframe | has none: what the code hands back is a table of its own making |
| context load | hands no rows on |

Which failures name their row: a reader that cannot read a row, a missing
value in a column that may not hold one (after any component), text a map
cannot read as its output column's type, and a conversion in an expression
(`int()`, `float()`, `strptime()`). A failure Polars raises by itself still
names the value and no row. Few are left to it: user Python, and a whole
number asked of something that is not a number in `round()` or
`math.floor()`.

## Types and missing values

Declared types are `str`, `int`, `float`, `bool`, `datetime`, `date` and
`Decimal`; `date_pattern` is a Python `strftime` pattern (a Java-style
pattern such as `yyyy-MM-dd` is understood too). A `Decimal` column holds
its declared `precision` places, or ten when none is declared.

Text read from a file is never missing: an empty field is empty text. For
every other type an empty or blank field is a missing value, except `bool`,
where it is `false` as in v1. Missing values are written as empty fields.

## Differences from v1

v1 is the answer key, with these exceptions. Each is deliberate.

**The engine**

- Java is not run. A `{{java}}` string is refused at load.
- A job is checked before it runs. Config keys that do not go together, an
  expression naming a column that is not there, a context variable nothing
  defines: v1 finds these when the component runs, or not at all; v2 refuses
  the job.
- No stall. In v1 a wired flow that gets no rows (a reject flow with nothing
  rejected) ends the job in status `error`. v2 writes the empty output and
  finishes.
- A failed job exits with code 1. v1 exits 0 whatever happened.
- A subjob is all or nothing: when one of its components fails, none of its
  files is written. v1 leaves the files written before the failure.
- `OnComponentOk` fires when the component's subjob finished, and
  `OnComponentError` for the component that failed. In v1 `OnComponentOk`
  fires for every component that ran before the failure, and
  `OnComponentError` never fires unless `die_on_error` is false.
- A component's row counts are known when its subjob has finished, so a
  later subjob and its triggers can read them, a component of the same
  subjob cannot.
- A component's row counts are of the rows it hands on. Most of v1's
  components count their rows before v1 checks them against the declared
  schema, so a row that check drops, or moves to the reject output (a
  missing value in a column that may not hold one, with `die_on_error`
  off), is still in v1's count of rows passed on and never in its count of
  rejects. In v1 the positional and the Excel input therefore always report
  no rejects. Where no row is dropped that way, the counts are v1's.
- Subjobs are always worked out from the flows. v1's `subjob_id` on a
  component is ignored.
- A context variable named as `${context.x}` that does not exist is an
  error. v1 leaves the text in the value. A context value that does not fit
  its declared type refuses the job; v1 keeps the text and warns.
- A config value that is exactly one context reference keeps the variable's
  type. In v1 every substituted value is text.

**Values**

- One rule per type. v1's answer for a value can depend on the other values
  in its column (one fractional value turns a whole `int` column into
  floats; one unparsable value changes how every other value is parsed). v2
  reads every value the same way: `1.50` in an `int` column is `1`.
- `bool` columns produced by a transform are parsed (`true`, `1`, `yes`).
  v1 turns every non-empty text, `false` included, into true.
- Text that is not a number in a `Decimal` column is an unreadable row. v1
  passes any text through a `Decimal` column unchanged.
- A `Decimal` column with no declared `precision` holds ten places. v1 keeps
  the digits as they were typed. Written through a file output that declares
  the column, the result is the same (trailing zeros are dropped); printed
  or handed to Python code, ten places show.
- A negative `precision`, which is how Talend writes that none is declared,
  means none. v1 takes -1 as it stands: a float column is rounded to tens
  (123.456 becomes 120.0) and a Decimal column to whole numbers.
- A negative Decimal that rounds to zero is written `0.00`. v1 writes
  `-0.00`.
- A float written by an output that declares the column `Decimal` with no
  `precision` is written as it prints (`1e-07`). v1 writes `0.0000001`.
- Where v1 writes the text `<NA>` or `<na>` for a missing value (a Decimal
  or bool column the engine added, a missing Decimal after some readers), v2
  writes an empty field.
- Control characters in a file are kept. v1 replaces them with spaces, which
  it needs for its Java bridge.

**Filter rows**

- The advanced condition is a Python expression (`condition`; v1's
  `advanced_cond` is an alias). v1 runs it as Java, row by row, and passes
  every row when its bridge is off.
- A missing value fails every test except `!=`, `NOT_CONTAINS` and
  `IS_NULL`. v1 does the same, except that a missing whole number under a
  number comparison lands in neither output there.
- `MATCHES` always tests the whole text.
- Refused at load, where v1 runs and gives an answer that is rarely meant:
  a condition on a column that does not exist (v1: false for every row), an
  unknown `function` (v1: tests the column as it is), a date column compared
  with a number, a pattern with lookaround or back-references, a text test
  (`CONTAINS`, `MATCHES`, a text `function`) on a Decimal column.

**Sort row**

- Sorting text as dates reads every value as `%Y-%m-%d %H:%M:%S`,
  `%Y-%m-%d` or `%d/%m/%Y` and puts what does not fit last. v1 lets pandas
  guess one format for the column from its first value.
- A criterion on a column that does not exist is refused (v1 drops it).

**Filter columns**

- With no input rows the declared columns are kept, as with rows. v1 passes
  every input column then.
- A schema that shares no column with the input is refused.

**Unique row**

- A key column that does not exist is refused at load. v1 skips it and
  falls back to the whole row.
- `<id>_NB_UNIQUES` and `<id>_NB_DUPLICATES` are counted only when something
  in the job reads them.

**Aggregate row**

- Sums and averages of floats are exact and do not depend on the order of
  the rows: 0.1 + 0.2 + 0.3 is 0.6. That is v1 with
  `use_financial_precision` (the converter's default); with it off, v1 has
  float noise (0.6000000000000001) that v2 does not reproduce.
- Standard deviation and variance are exact where every distance from the
  mean has at most nine decimal places, and to about fifteen significant
  digits otherwise; the last digits of an unrounded result can then differ
  from v1's.
- A missing Decimal is a missing value. v1 holds an empty Decimal field as
  empty text and counts and lists it.
- The smallest and the largest of a text or date column are written. v1
  writes nothing for them under `use_financial_precision`, its default.
- An average kept in a Decimal column with no declared `precision` has 18
  decimal places. v1 keeps 28 significant digits.
- In a column declared `str`, or not declared, numbers print as held (`2.2`);
  v1 prints its Decimals (`2.20`).
- v2 runs what v1 fails on: first/last without group columns, group columns
  without operations (each group once), lists over missing whole numbers.
- Refused at load: a sum, average, median, deviation or variance of a column
  that is not a number (v1 gives 0 or nothing), a config with neither group
  columns nor operations.

**Join**

- A missing key matches nothing, for every type. v1 fails on whole-number
  keys when any is missing, and where it does run it hands a left-joined row
  the lookup columns of the lookup's own missing-key row.
- `case_sensitive: false` only compares without case. v1 also writes the key
  columns in lower case and multiplies rows when lookup keys differ only in
  case.
- Key columns that cannot be compared (text against a number or a date) are
  refused at load. v1 fails at run, or runs and matches nothing.
- Refused at load: a fetched column whose output name the output already
  has (v1 writes two columns of one name), a third input (v1 ignores it), an
  empty `join_key`, a key column that does not exist.
- Three things v1 does with `lookup_cols` are kept, each with a warning in
  the log, because they are what v1 writes: a lookup column whose name the
  main input also has is not fetched (it is reachable as `<name>_lookup`), a
  lookup column is fetched once, and an entry naming no lookup column adds
  nothing.
- `<id>_ERROR_MESSAGE` is not set in the globalMap.

**Unite**

- A unite with one input passes it through. v1 drops every row.
- The columns of the output never depend on which inputs happen to be
  empty. v1 forgets the columns of an empty input.

**Map**

- Main rows keep their order. v1 moves the rows whose join key is missing
  behind all the others, lookup by lookup.
- A whole-number column stays whole. v1 writes `30.0` wherever pandas turned
  the column into floats (a lookup column beside an unmatched row, a column
  holding a missing value).
- Reject outputs work as in Talend and in v1's tMap, not as in v1's PyMap:
  an `is_reject` output takes the rows no ordinary output took, with its own
  columns, and an `inner_join_reject` output computes its own expressions.
- An inner join on a lookup with no rows rejects every main row (PyMap keeps
  them all).
- An expression that fails on a row fails the component, whatever
  `die_on_error` says: `int(row1.code)` on text that is not a number, for
  instance. As in Python, it fails only on a row the conversion is worked
  out for: not behind an `and` that is already false, an `or` that is
  already true, in the branch of an `if` that is not taken, or further along
  a chain of comparisons (`a < b < c`) than the first that does not hold.
  `np.where` is a function and is handed both its values worked out, so a
  conversion in either fails. An operation on a missing value never fails;
  it gives a missing value. Rows are not sent to a catch output.
- A row an inner join turned away has left the map, as in v1: no variable
  and no key of a later lookup is worked out for it, so a conversion in one
  cannot fail on it. v1 gives an `inner_join_reject` output no variables to
  read. v2 does, and when such an output reads one, the variables are worked
  out for every row.
- An output column nothing in the job reads is never worked out. A
  conversion in it that fails on a row still fails the job, as in v1, which
  works out every column of every output.
- In an expression a missing value is `None`. v1 hands expressions pandas'
  `nan` or `<NA>`, so `x is None`, `str(x)` and `x or default` can answer
  differently there.
- Refused at load: `lookup_mode` other than LOAD_ONCE (reloading a lookup
  for each row needs a loop over the rows), a join key `operator` other
  than `=`, a lookup filter that reads the main row, a text key against a
  number key without `enable_auto_convert_type`, `ALL_ROWS` on a lookup
  that has join keys.
- Kept as v1 has them: an `is_reject` output's own filter is not read, and
  an output column's `nullable` and `precision` are not applied.
- A row count of a component in the same subjob is not known while the plan
  is built: `globalMap.get("in_NB_LINE")` reads it in a later subjob only.

**Python dataframe**

- `dataframe: polars` is new: the code gets a Polars lazy frame and the
  component stays lazy. The default, `pandas`, is v1's behaviour.
- A missing Decimal reaches the code as `None`. v1's file input leaves an
  empty text in the column.
- Code that leaves two columns of one name fails the component.
- Decimals the code makes with different numbers of places (by a division,
  say) are carried as text, each as Python prints it, so a file output
  writes what v1 writes. Declare the column `Decimal` in the component's
  schema to keep it a number for the components that follow.
- The code runs with Python's ordinary built-ins; v1 withholds a few
  (`open`, `eval`, `exec`).

**Log row**

- A whole number prints whole. v1 prints `1.0` when every column of the row
  is a number and one of them is a float.
- A table is always aligned. v1's table fails on a missing whole number or
  an all-missing date column.

**Context load**

- The flow's `key` and `value` columns are checked even when it has no
  rows. v1 checks once a row arrives.
- A policy other than ERROR, WARNING, INFO or NO_WARNING is refused at load.

**JSON input**

- One rule per value. v1 lets pandas pick one type for a column, so a whole
  number beside a fraction or a missing value comes out as `1.0`, in a text
  column too. v2 writes `1`.
- A path that is not a JSONPath refuses the job. v1 runs, rejects every
  record with "Parse error" and writes no row.
- A record a path cannot be followed on (the first item asked of a number,
  say) is turned away as in v1: it is left out of the main output and goes
  to the reject output with `PARSE_ERROR` and what the library said,
  whatever `die_on_error` says. v2's reject output has every column, empty
  from the path that failed on; v1's has only the columns read before that
  path, so its columns change with the data.
- The document is read whole and gone through in Python, record by record:
  a JSONPath can ask for any part of it, so Polars cannot scan it. It is the
  one reader that takes memory and time by the size of its file.
- Reading from a URL (`useurl`) is refused: v2 reads files.
- A `schema` inside the config, v1's older way of typing values, is
  refused; with it go `advanced_separator`, `check_date` and their keys,
  which v1 reads only then.
- As everywhere, a wired reject flow that gets no rows is written empty; v1
  stalls.

**Normalize**

- A column of dates is refused. A number or a true-or-false value is split
  as the text Python writes for it (`1e-07`, `True`), as in v1.
- `csv_option` and its two keys are accepted and change nothing, as in v1.

**Positional input**

- A value that cannot be read rejects its row (or fails the component with
  `die_on_error`), as in the delimited reader. In v1 one such value makes
  the whole file come back with no rows, and a date that cannot be read
  goes missing silently.
- Text is kept as it is. v1 blanks every character outside printable ASCII,
  accents included, and empties the texts `NA`, `N/A`, `null`, `NaN`,
  `None`.
- `bool` reads true/1/yes and false/0/no. v1 reads any text as true.
- `limit` counts rows after blank lines are dropped, and works together
  with `footer_rows`.
- `*` as the last width takes the rest of the line (v1 refuses it).
- Kept as v1 has it: blanks around a field are stripped and blank rows
  dropped whatever `trim_all` and `remove_empty_row` say.

**Full-row input**

- `random` (lines picked at random) is refused: the rows would differ from
  one run to the next.
- A row separator other than `\n`, `\r\n` or `\r` is refused.
- Kept as v1 has it: what follows the last line end counts as one more,
  empty line, so `footer_rows: 1` on a file ending in a newline removes
  nothing real.

**Excel input**

- Read with fastexcel (calamine), about four times as fast as v1 on a
  60,000-row workbook. `.xls` is covered only for numbers and text.
- A sheet or column range narrower than the schema gives missing columns
  (v1 reads nothing from the sheet). `first_column` 0, which the converter
  itself writes, is read as 1 (v1 refuses it).
- Dates are read cell by cell with the declared pattern; whole-number
  columns stay whole.
- With `all_sheets` and a `sheetlist`, sheets are read in workbook order
  (v1: an order that changes between runs).
- Kept as v1 has it: a `sheetname` that is not in the workbook reads the
  first sheet; in a text column a date cell is written `dd-mm-yyyy` and a
  boolean `1`/`0`; cells that cannot be read go missing and are never
  rejected.

**Delimited files**

- A blank line is never a row and does not count toward `limit`, as in v1.
  The exception is a file read with `row_separator` `\r`: there a blank
  line is a row of empty fields, kept when `remove_empty_row` is off and
  counted toward `limit`.
- With `csv_option`, an enclosure character must open and close a field.
  v1 also reads a file where one does not (an inch mark inside a field that
  is not enclosed, a field that opens an enclosure and never closes it), the
  lenient way Python's csv reader does. v2 fails the reader and says why; it
  never goes on with part of the rows. Reading such files is not built yet.
- With `csv_option`, a separator of more than one byte (a broken bar or a
  section sign, say) is refused at load, on read and on write.
- A row with more fields than the schema has its extra fields dropped. v1
  does that only when the first row is the longest and fails the read
  otherwise.
- `check_fields_num` rejects exactly the rows whose field count is not the
  schema's. v1's check also rejects rows whose last field is empty and
  misses short rows in some setups.
- Rejected rows carry v1's `errorCode` and `errorMessage`. The message for
  a date that cannot be read always names the pattern; v1's wording varies
  with the Python version.
- A row separator other than `\n`, `\r\n` or `\r` on read, and `split` on
  write, are refused for now.
- A file name is one file. Polars would read `*`, `?` and `[` in it as a
  pattern; v2 does not let it.
