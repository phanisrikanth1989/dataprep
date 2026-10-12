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
  finds no repeat, an aggregate makes a group of the picked rows, a sample
  row counts its places among them, a row count and a `RunIf` on one count
  them.

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
3. Replace or remove components v2 does not have. v2 has these:
   - files: delimited input and output; positional, full-row, Excel and
     JSON input; fixed flow input (rows written in the job config); row
     generator (rows made from expressions); properties input (a
     properties or an ini file); Excel output; positional output; pivot
     to columns delimited (an output);
   - rows: filter rows, filter columns, sort row, unique row, aggregate
     row, aggregate sorted row, join, unite, map, normalize, replicate, sample row, split row,
     replace, convert type, unpivot row, denormalize, schema compliance
     check, extract delimited fields, extract positional fields, extract
     regex fields, extract JSON fields;
   - the rest: Python dataframe, log row, context load, file row count,
     die, warn, set global var, file exist, file copy, file delete,
     file touch.
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
writes nothing, so it dropped nothing). One more kind of row goes missing
without a word, as it does in v1 and in Talend: a context load skips a row
with no key. (An aggregate row keeps the rows that have no value in a group
column, as a group of their own; see "Differences from v1".)

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

For the components under "Components built to their own rule", at the
end, v1 is no answer key at all.

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

- Rows that miss a group value are a group of their own, whose key is
  written as nothing, as in Talend: the key its tAggregateRow generates
  holds a missing value like any other. v1 leaves such rows out without a
  word (pandas' `groupby` drops them), so v2 writes a row there that v1
  does not: of `1;1`, `;2`, `1;3`, `;40`, `2;5` summed by the first column,
  v1 writes `1;4` and `2;5`, and v2 writes `;42` as well.
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

**Aggregate sorted row**

- A group is a run of rows, one after another, that agree in the group
  columns, as in Talend, whose component compares each row with the one
  before it. On rows sorted by the group columns, which is what the
  component is for, that is what v1 writes. On rows that are not sorted,
  v1 groups the whole input and writes a group value once, where v2 and
  Talend write it once for each run: of `a;1`, `b;2`, `a;3` summed by the
  first column, v1 writes `a;4`, `b;2` and v2 writes `a;1`, `b;2`, `a;3`.
- Everything said of the aggregate row holds here too, the rows that miss
  a group value among it.

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

**Replace**

- Patterns run on Polars' regular expressions, not Python's. An advanced
  rule whose pattern Polars cannot read is refused at load: look-around, a
  back-reference inside the pattern, `\Z`, `a{,2}`, `(?#...)` and a few more
  spellings Python takes. A few patterns both read mean something else:
  a character class inside another (`[a[b]c]`), `&&` inside a class, `\<`.
- A pattern that can match nothing (`x*`) is replaced once less than in v1
  right after a match: of `x` under `x*` to `-`, v1 writes `--` and v2 `-`.
- A group of the match is put back in the replacement as in v1 (`\1`,
  `\g<1>`), and a replacement Python would not take refuses the job at
  load, where v1 fails when the component runs.
- A date is searched as the text its column's pattern gives, and as its
  day alone when it has no pattern and no time of day. v1 searches the
  second form whenever every value of the column is at midnight.

**Convert type**

- v1 on today's pandas turns away every row a pair converts in place (its
  own cast fails on a text column), so v1 is the answer key only for a pair
  that names another output column. There v2 keeps and turns away the same
  rows for whole numbers and floats, text or not, and for dates and
  true/false read from typed columns.
- Text is read by the rules v2's readers have for the declared type. v1
  reads through pandas, which takes more: a date in any spelling whatever
  the column's pattern, any text but `true` as false. v2 turns such a row
  away.
- The reject output has `errorCode` and `errorMessage`, as every reject
  output of v2 and of Talend. v1's convert type alone calls them
  `error_code` and `error_message`. The message is v2's own (`Column 'n' ->
  'n' (int): cannot read 'x'`); v1's is pandas' text.
- Two pairs that read one column fill both output columns. v1 fills the
  last one only.
- `autocast` asks for nothing more: the engine reads every value as the
  type its output column declares, as after any component.

**Split row**

- A whole number is written whole (`100`). v1 writes `100.0` for every
  value of a whole-number column that has a missing value anywhere.

**Sample row**

- A range that cannot be read refuses the job at load. v1 fails when the
  component runs.

**Denormalize**

- A whole number is put together whole (`3`). v1 writes `3.0` for every
  value of a whole-number column that has a missing value anywhere.
- A Decimal whose column declares no places is put together without
  padding (`1.5`). v1 writes it as it stood in the file (`1.50`).
- A named column that is not there, and a config that names every column,
  refuse the job at load. v1 fails when the component runs. A column named
  twice refuses the job too; v1 writes the column twice.

**Unpivot row**

- A whole number is written whole (`3`). v1 writes `3.0` for every whole
  number when any of the unpivoted columns holds a float or a missing
  value, because pandas makes one column of them all.
- A Decimal whose column declares no places is written without padding
  (`1.5`). v1 writes it as it stood in the file (`1.50`).
- Keys that cannot be used (none named, one that is no column, one named
  twice) and names that clash refuse the job at load. v1 fails when the
  component runs. With `die_on_error` off both hand on no rows for a key
  that is no column.

**Schema compliance check**

- Where no row is turned away, the file behind the reject output has its
  header line. v1 leaves that file with nothing in it.
- Bytes are counted in UTF-8 and in one-byte character sets
  (`check_string_by_byte_length`). Any other `charset` is refused at load;
  v1 counts in whatever Python knows. A character a one-byte set cannot
  write counts as one; v1 fails the job on it.
- Under `strict_date_check` a date fits its pattern where v1 says it does
  (v1 asks pandas; v2 is held to pandas' answer over 29 patterns and some
  180 values, odd ones among them: `2024-1-5` fits `%Y-%m-%d`, `24-01-31`
  does not). Not the same: digits of another script are no date in v2; a
  pattern with a part other than year, month, day, hour, minute, second,
  fraction, AM/PM and time zone (a month by name, say) is read by Polars;
  and a pattern that is no pattern (`%Q`) refuses the job at load, where
  v1 fails when the rows arrive.
- A missing Decimal is a missing value. With `all_empty_are_null` off, v1
  holds it as empty text and turns its row away as `invalid type`.
- The length of a value that arrives typed is that of the text it is
  written as (`2024-01-31` for a day with no time, `1.5` for a Decimal
  with no declared places). v1 has the digits of such a Decimal as they
  were typed, and fails on a whole-number column that has a missing value.
- `length` written as text (`"2"`) is the number. v1 passes over it.
- An entry of `empty_null_table` without `empty_is_null`, and a key v2
  does not know in a column of `schema`, refuse the job. v1 passes over
  both.

**Extract delimited fields**

- A missing value in a Decimal source column is a missing source: the
  row is left out, or leaves by the reject output. v1 holds a missing
  Decimal as empty text and hands the row on with nothing in its pieces.
  (The same holds for the other three extract components below.)
- A date in an output column is read by the column's pattern. v1 reads
  one written another usual way when no date of the column is written by
  the pattern.
- Where a column that may not be missing is missing and the job is not to
  die, the row leaves by the reject output with the engine's
  `SCHEMA_VIOLATION`, and the reject output then has the extracted
  columns too; v1's has the output's columns.
- The separator is taken as it is written, as in v1 (and as normalize
  takes its own). Talend reads it as a pattern: a job that separates at
  `|` or `.` there has it written `\\|`, which is to be written `|` here.
- A piece is read as its column's declared type the way every transform's
  output is: what cannot be read goes missing, an empty piece too. v1
  writes text through in a Decimal column, takes any text for true (the
  word `false` as well) and an empty piece for false, and writes `7.0`
  for a whole number beside a missing one.
- A date in the source column is split as the text its pattern writes. v1
  splits Python's text for it (`2024-01-31 00:00:00`).
- A source column that is not there refuses the job. v1 fails when the
  rows arrive.
- `die_on_error` is off when the job does not say: v1's own default for
  the number of pieces. v1's engine takes it for on when it looks at the
  columns that may not be missing; the converter always writes the key.
- Where no row is turned away, the file behind the reject output has its
  header line. v1 leaves that file with nothing in it.
- A wrong number of pieces that fails the job names the row.
- Not acted on, as in v1: `advanced_separator` (v1 looks for Talend type
  names its schemas never hold), `check_date`.

**Extract positional fields**

- A piece is read as its column's declared type the way every transform's
  output is, as for extract delimited fields above.
- A `field` that names no column refuses the job. v1 cuts the first
  column in its place, with a warning. (With no `field` at all, both cut
  the first column.)
- A `pattern` that is no list of widths refuses the job before it runs.
  v1 fails when the rows arrive, and takes a pattern of commas alone for
  no width at all.
- With no output columns declared, a column is made for every width,
  `field_1` and so on, as in v1.
- A date in the source column is cut as the text its pattern writes; v1
  cuts Python's text for it.
- `die_on_error` is off when the job does not say, and the reject file
  has its header line where no row is turned away: both as for extract
  delimited fields.
- A text that is too short and fails the job names the row.
- Not read, as in v1: `formats`, `advanced_option`, `advanced_separator`.

**Extract regex fields**

- The pattern is Python's, as in v1, as far as Polars can look for it. A
  pattern Polars does not take refuses the job, with Polars' own words
  for why: lookaround, a backreference, `\Z`, `(?a)`, a `{` that opens no
  count, `{,2}`, `\N{...}`, an octal escape, `(?#...)`, `(?>...)`, a
  conditional group, and a counted `\w` of some 250 or more.
- What both take and read differently refuses the job as well: a `[`
  inside `[...]` (`[[:alpha:]]` among them), `&&`, `--` and `~~` inside
  `[...]`, and `\<` and `\>`.
- Not refused, and not the same: `\w` and `\b` follow Unicode's own word
  characters in Polars (a combining accent and `‿` are of a word, `²` and
  `½` are not), where Python has its own list; `(?i)` does not pair the
  Turkish `İ` and `ı` with `i`; a group repeated around something that
  can be empty (`((a*)*)`) holds what its last turn held. `$` is the end
  of the text; in v1 it is also the place before a line break the text
  ends on.
- A date in the source column is looked in as the text its pattern
  writes; v1 looks in Python's text for it.
- A pattern that is none, and a `field` that names no column, refuse the
  job before it runs. v1 fails when the rows arrive, and with
  `die_on_error` off looks in the first column for a `field` it does not
  find.
- What a group holds is read as its column's declared type the way every
  transform's output is, as for extract delimited fields above.
- A text the pattern is not found in is said the way Python shows a text
  (`'bob'`), as in v1; a character Python would write as an escape other
  than a line break, a tab or a backslash is written as it is.
- A failure names the row. The reject file has its header line where no
  row is turned away.

**Extract JSON fields**

- Paths are JSONPath (`read_by` JSONPATH). `read_by` XPATH refuses the
  job: v1 tries an XPath as a JSONPath, which it is not, and writes rows
  with nothing in them. The converter's own sample is written that way.
- A path that cannot be read, a loop path too, refuses the job. v1 fills
  nothing for the first and reads the whole document for the second,
  with a warning each.
- A `jsonfield` that names no column refuses the job. v1 reads the first
  column in its place.
- A value is read as its column's declared type as for rows written in a
  job config: true and false from words and numbers; a date by its
  column's pattern or one of the usual ways (`2024-01-31`, with a time
  after a blank or a `T`, or `31/01/2024`), where v1 reads the usual ways
  only when no date of the column is written by the pattern; a moment
  with an offset (`...Z`) or, in a column with no pattern, a fraction of a
  second, goes missing. A number with a fraction in a whole-number column
  is cut, as everywhere; v1 writes `2.0` and `1.7` through there.
- Also not as v1: a whole number of 2^63 or more in a whole-number column
  and one beyond 38 digits in a Decimal column go missing (v1 writes
  them); `true` in a float or Decimal column goes missing (v1 `1.0`); a
  number in a date column goes missing (v1 a moment in 1970); `1` beside
  a missing value in a text column is `1` (v1 `1.0`).
- A column of the mapping that the output does not declare is not
  written (v1 writes it as one column more), and the output columns have
  to be declared (v1 writes the mapping's). A column the output declares
  not nullable and the mapping does not fill turns every row away
  (`SCHEMA_VIOLATION`); v1 writes it empty.
- An entry of the mapping with no column, an empty mapping and a key v2
  does not know in an entry refuse the job; v1 passes over them.
- A failure names the row the document came from, and so does the trace
  for every item of it.
- Where no row is turned away, the file behind the reject output has its
  header line. v1 leaves that file with nothing in it.
- A document is read out of every row in Python: the rows are held in
  memory, as in v1.

**Pivot to columns delimited**

- It is an output and hands no rows on. v1 also hands the pivoted rows to
  a flow that leaves it; v2 refuses a job with such a flow.
- Whole numbers in the cells are written where v1 fails ("Invalid value ''
  for dtype 'Int64'", whenever the value column holds whole numbers and a
  cell is empty).
- A sum of floats is exact, as in the aggregate and as Talend adds: 0.1
  ten times is 1.0, whatever order the rows come in. v1 adds with a
  running correction and comes to the same on ordinary data; it can lose
  a small number beside very large ones.
- Rows that miss a group value are a group of their own, as in Talend. v1
  leaves them out.
- A group whose values are all missing is still a row, as in Talend. v1
  leaves it out for min, max, first and last.
- A missing Decimal is a missing value, as a missing float is in both: a
  sum over none is 0.00, a count 0, and a column with no value at all is
  left out. v1 holds a missing Decimal as something: it writes nothing for
  the sum, counts it, and keeps the column.
- A Decimal with no declared places is written without padding (`4.5`).
  v1 has its digits as they were typed (`4.50`).
- sum needs a column of numbers, and a job that sums anything else is
  refused. v1 puts text together (`x007`) and counts the trues.
- A column to group by that is named twice, or that is the pivot column,
  refuses the job. A pivot value that is the name of a group column fails
  it, in plain words (v1 fails there too).
- `create` written as the text `false` is off. v1 takes any text for on.
- A date that becomes a column name, or that is grouped by, is written by
  its column's pattern, and true/false to group by as `true`, both as in
  Talend. v1 writes the date with its time of day and the word as `True`.
- The table of groups is held in memory while it is turned into columns:
  one row for each group and pivot value, not the rows that came in.
- Not acted on, as in v1: `csv_option`, `advanced_separator`. (Talend acts
  on both.)

**Excel output**

- Written with openpyxl, as v1 writes it, and held against v1 by what is
  in the workbook (sheets, cells, their kinds and number formats, column
  widths): a workbook's bytes hold the time it was written.
- Every row is written, one with nothing in it as an empty row, as in
  Talend. v1 leaves such a row out and counts it as rejected.
- With `delete_empty_file`, a workbook that nothing was added to
  (`append_file`) is kept, as in Talend. v1 deletes it.
- A number that is none (not a number, or without end) is no cell. v1
  writes a cell with no value in it.
- Text in a column declared a date with a pattern is written as it is. v1
  writes nothing for text the pattern does not read.
- The widths of `is_all_auto_szie` follow v1's rule (the longest value's
  length and two more), not what Excel would measure as Talend has it.
  They are not always v1's numbers: v1 counts the digits a Decimal with
  no declared places was typed with, `7.0` for a whole number beside a
  missing one, and `nan`. v1 fails to size a sheet that has missing values
  in columns of several types; v2 sizes it.
- A sheet name that is nothing but a quote, or two, is openpyxl's `Sheet`,
  as in v1.
- Refused at load: a sheet name Excel does not take (longer than 31
  characters, which v1 writes with a warning, or holding one of
  `\ / * ? : [ ]`, where v1 fails when it comes to it); a first cell
  before A1 or beyond the last column or row a sheet has; `protect_file`,
  which v1 passes over, leaving the workbook unprotected; `usestream`.
- Columns are taken from the component's input schema. v1 also reads them
  from an output schema written on the component, which the converter
  never writes.
- A character no workbook can hold fails the job with the column and the
  row. v1 fails with openpyxl's words.
- A workbook that cannot be written always fails the job. With
  `die_on_error` off, v1 logs it and goes on with no file.
- A date whose column declares a pattern is text, as in v1. (Talend
  writes a date cell with that format.)
- Two outputs of one subjob may fill two sheets of one workbook, or add
  to one sheet, the second with `append_file`, as in v1.
- A workbook that is added to (`append_file`) and cannot be read, or
  whose sheet has no room for the rows, fails the job when its turn comes
  to be put in place; files the subjob wrote before it are in place by
  then.
- The rows are held in memory while the workbook is made, as in v1.

**Positional output**

v1's positional output and Talend's do not agree on much, so here v2 is
held to Talend's own component (read in its source, Talaxie
`tFileOutputPositional_begin.javajet`), and to v1 where v1 does the same:
text and whole numbers, padding and cutting, left and right, the row
separator, the encoding.

- A value is written as the delimited output writes it: a float as it
  prints (`1.5`), a Decimal to its declared places, `true` and `false`, a
  date by its column's pattern. v1 writes a float and a Decimal to eight
  places unless the column declares some (`1.50000000`), `True`, and a
  date without its pattern; and it fails on a job whose typed columns
  have missing values.
- Centred (`align` C), where the padding does not divide evenly the one
  more is on the right: `ab` in five is `*ab**`. v1 has `**ab*` when the
  size is odd.
- A column name longer than its size is kept as a value would be (whole
  under `keep` A). v1 cuts it to the size.
- When adding to a file (`append`), the header goes only into a new or
  empty file. v1 writes it again.
- No rows leave an empty file (or its header). v1 touches no file then,
  and one from an earlier run stays as it was.
- `compress` puts the file into a zip beside its name (`out.txt` into
  `out.zip`), and not when appending. v1 writes gzip under the file's own
  name. Two things Talend's template does with the plain file's name
  while it writes the zip are not followed: it leaves the header out of
  the zip when a plain file of that name is there and not empty, and
  with `delete_empty_file` and no rows it deletes that plain file and
  leaves the zip. v2 writes the header, and leaves no zip.
- A float is written as the engine holds it, which for a column that
  declares places is rounded to them (`2.005` in two places is `2.0`);
  Talend prints the float it was given, and v1 `2.00`.
- The row separator reads `\n`, `\r` and `\t` as the characters they
  mean, like the delimited output. v1 reads every escape Python knows
  (`\u2028`, `\x00`).
- A whole-number column with a missing value is written. v1 fails on it.
- Not the same as Talend, where v2 keeps to its own way of writing a
  value: a float of very many or very few digits (`1.0E10` in Java) and a
  date with no pattern (Java's `Wed Jan 31 ...`), which v2 writes as its
  delimited output does.
- Refused: `use_byte` (widths in bytes), `usestream`, a dynamic schema, a
  `padding_char` of more than one character (v1 fails on it when it
  runs).
- Not acted on, as in v1: `advanced_separator`.

**Fixed flow input**

- The text `false` is false. v1 takes any text that is not empty for true
  in a true/false column here, `false` and `no` among it.
- A value that is not of its column's declared type goes missing (`abc`
  in a Decimal column), and `1.5` in a whole-number column is cut to 1, as
  everywhere a whole-number column is filled. v1 writes both through as
  they are here, `<NA>` for a missing Decimal, and `3.0` for a whole number
  beside a missing one. A date may be written by its column's pattern or
  one of the usual ways, as v1 reads it.
- A whole number too long for 64 bits goes missing in a column declared a
  whole number; in a text or Decimal column it is kept, as in v1.
- A date in the last field of a line that ends in `\r\n`, under the
  default row separator, is read. v1 loses it to the `\r` that stays.
- A context variable that does not exist refuses the job. v1 writes the
  reference through as text.
- `nb_rows` may be written as text or come from the context. v1 fails.
- A failure names the row: `line 3 of the inline content of <id>`, or
  `row 3 of <id>` for the other two ways of writing rows.

**Row generator**

- An expression is Python with no name to call on but the `random`
  module, as in v1. That is no fence: Python code can reach anything from
  there, and a job config is trusted as code is. The Java expressions a
  converted job holds (`{{java}}...`) refuse the job, as everywhere.
- A row whose expression fails leaves by the reject output as in v1, and
  the log says how many such rows there were and what failed in the first
  (`id: division by zero`). With no flow on the reject output the log
  warns that they were dropped; v1 drops them and logs an error for each.
- The text `false` or `no` is false in a true/false column. v1 takes any
  text that is not empty for true here.
- A value that is not of its column's declared type goes missing (`abc`
  in a whole-number column, as in v1; the number 20240131 in a date
  column, where v1 writes 1970-01-01), and `1.7` in a whole-number column
  is cut to 1, as everywhere, where v1 writes 1.7 through here. v1 writes
  `<NA>` for a missing Decimal.
- A true/false column with no expression is false. v1 writes `<na>`
  where the column may be missing. Text that is neither true nor false
  (`'Y'`, `'abc'`), and a list, go missing there; v1 takes them by whether
  they are empty. In a row whose expression failed, the column is false
  in the reject output, where v1 has it missing.
- A whole number too long for 64 bits goes missing in a whole-number
  column, and one beyond 38 digits in a Decimal column; v1 writes them.
  `-0.0` in a Decimal column is `0.00` (v1 `-0.00`). In a float column v1
  writes a whole number as it is given (`1` for `'1'`, `True` for `True`);
  v2 writes `1.0`, and nothing for `True`.
- A date may be written by its column's pattern or one of the usual ways
  (`2024-01-31`, with or without a time, or `31/01/2024`), as v1 reads it;
  any other text goes missing.
- An entry of `values` for a column the schema does not have, or a second
  entry for one column, refuses the job. v1 writes a column more.
- A number of rows below 0 or that is no number refuses the job before it
  runs. v1 fails when it comes to the component.
- A context variable that does not exist refuses the job. v1 writes the
  reference through as text.
- The rows of a run are made once: `run.only` and a second reading see the
  rows the first reading made, also where they are drawn at random.
- A failure names the row: `row 3 of <id>`.

**Properties input**

Here v2 follows Talend and not v1. Talend's component has a schema a job
cannot change, `key` and `value` (and `section` for an ini file read
whole), and hands on a row for every property. v1 hands on one row and
fills each column from the property of that name, which on the schema of
every converted job is a row of nothing.

- A job whose reader declares only `key`, `value` and `section` gets
  Talend's rows. One that declares other columns gets v1's one row, as a
  job written for v1 expects (and v1's one row for each section of an ini
  file read whole, with its name in `__section__`).
- A properties file is read as Java reads one: `\t`, `\n` and `\uXXXX`
  are the characters they mean, a key ends at `=`, `:` or a blank, a line
  that ends on a backslash goes on in the next, and the file is always
  ISO-8859-1; a `\u` that is no four hex digits fails the job, as it
  stops Java. (An independent run of 4,047 files through Java 17 and v2
  found two rules amiss, both mended since.) v1 reads no escape, ends a
  key at `=` or `:` only, and reads the file in `encoding`.
- A value is read as its column's declared type, and one that cannot be
  goes missing without a word, also where the column may not be missing:
  the rule for rows a job config writes.
- v1's one row is v1's for a properties file of plain lines. For an ini
  file it is filled by v2's plain rules, not by Python's `configparser`
  as v1 fills it: no values handed down from a `[DEFAULT]` section, no
  value that goes on in the next line, and no failure on a key given
  twice or before any section.
- A section named twice is one section.
- The rows come in the order of the file. Talend hands them on in the
  order of Java's hash table, which no job can count on.
- An ini file's names of sections alone can be read
  (`retrive_mode` RETRIVE_SECTIONS), which v1 does not know.
- An ini file is read by plain rules (sections in brackets, `key = value`
  or `key: value`, comments that start with `;` or `#`); Talend reads it
  with the ini4j library, whose finer points were not looked up.
- A file that is not there, or an ini file not written in its encoding,
  fails the job in plain words; v1 reads a wrong byte as a replacement
  character.
- A failure names a row by the line its property is on (for a key given
  twice, the line of the value that stays), and a run can be for a few
  properties, by line or by key.

**Die**

- It stops the whole job, as in v1 and Talend: no trigger fires after it
  and no subjob follows, also not one nothing triggers. Any other failure
  fails its own subjob and lets the job go on.
- Set off by a trigger, it stops the job with v1's words.
- With a flow leading to it, it stops the job when a row arrives and not
  otherwise, as in Talend, and names the first such row. v1 stops the job
  whether a row arrives or not, so a die behind a filter's rejects stops
  every run.
- Talend's names are left in globalMap beside v1's (`<id>_DIE_MESSAGE`,
  `_DIE_MESSAGES`, `_DIE_CODE`, `_DIE_PRIORITY`).
- The exit code is said in the message and left in globalMap; the command
  line ends with 1 for any job that failed, as for every failure. (v1
  does not end with it either.)
- `exit_jvm` refuses the job: there is no JVM to exit.

**Warn**

- One that is to hand rows on with no flow leading to it refuses the job.
  v1 hands on no rows.
- Set off by a trigger, it logs its message as in v1. A message of
  priority 4 or more goes to stderr, like every warning: a job that warns
  is no clean run by that measure, which is what a warning is for.
- With a flow leading to it, it hands the rows on and speaks once when a
  row arrives, and not at all when none does. v1 speaks once either way;
  Talend speaks for every row.
- Talend's names are left in globalMap beside v1's (`<id>_WARN_MESSAGES`,
  `_WARN_CODE`, `_WARN_PRIORITY`).

**Set global var**

- With a flow leading to it, the entries are put when the subjob is done:
  v2 runs a subjob in one pass. A later subjob and a trigger's condition
  read them, as in v1; a trigger that leaves a component before it is
  judged without them, as in v1. A component of the same subjob that
  reads one of them (`globalMap.get("key")` or `globalMap["key"]` in its
  config) fails the job before anything is written: v1 runs the
  components of a subjob one after the other, so what follows this one
  there reads the last row's value, and Talend's reads each row's. Such a
  job has to be cut in two subjobs. A key put together in code is not
  seen by that check.
- One that is to hand rows on with no flow leading to it refuses the job.
  v1 hands on no rows.
- Nothing is put when no row arrives, as in Talend. v1 puts the values as
  they are written, the text `row1.name` among them.
- A value is a column of the row when it is written `<flow>.<column>`
  with the name of the flow that leads to the component. v1 takes any
  word before the dot.
- An entry with no key refuses the job. v1 fails when it comes to it, or
  passes over it with `die_on_error` off.
- A value that is a Java expression refuses the job, as everywhere.

**File copy**

Where v1 and Talend differ, v2 does what Talend's source does, but for
the two safeguards said last; where they agree, v1 is the answer key
(what is in the folder afterwards).

A file:

- A copy that fails lets the job go on, with why in `<id>_ERROR_MESSAGE`
  and a warning in the log, unless `failon` is on. v1 fails the job
  unless `die_on_error` is written and off, which the converter never
  writes.
- A file that is there and is not to be replaced (`replace_file` off) is
  left, and that is no fault; v1 fails. The source is then not taken
  away either, having no copy.
- The time the file was changed is kept only with
  `preserve_last_modified_time`; v1 always keeps it.
- `<id>_DESTINATION_FILEPATH`, `<id>_DESTINATION_FILENAME`,
  `<id>_SOURCE_DIRECTORY` and `<id>_DESTINATION_DIRECTORY` are left in
  globalMap, whatever becomes of the copy, as in Talend; v1 leaves
  nothing.
- A new name of nothing but blanks is `NewName.temp`, as in Talend.
- The source has to be a file, and the destination a folder: a file
  named as the destination fails the copy, where v1 writes over that
  file.
- A file copied onto itself is left as it is. v1 fails; Talend compares
  the two paths as they are written.

A folder (`enable_copy_directory`):

- It is copied into the destination under its own name (`src` into `out`
  is `out/src`), as in Talend. v1 puts what it holds straight into the
  destination. A job written for v1 has to name the folder above.
- What is there is written over and what is missing is made, whatever
  `replace_file` and `create_directory` say, as in Talend.
- The source folder is never taken away, whatever `remove_file` says, as
  in Talend. v1 deletes it.
- A folder is not copied into itself or into a folder inside it. v1 (and
  Talend's template, as far as it was read) copies it into itself over
  and over, and v1 with `remove_file` on then deletes all of it.
- When some files cannot be copied, the others are, and the message says
  how many could not and names the first.

Nothing named to copy, or nowhere to copy to, refuses the job before it
runs.

**File delete**

Where v1 and Talend differ, v2 does what Talend's source does, but for
the two safeguards said first.

- A link is taken away itself and what it leads to is never touched,
  however the path is written. v1 deletes everything in the folder a
  link leads to when the path ends in a slash, and Talend's template
  empties it either way.
- The folder the job runs in, and any folder it lies in (`.`, `..`,
  `dir/..`), is never deleted: the delete fails. v1 and Talend empty it,
  and then say that nothing was deleted.
- Nothing there to delete fails the job, unless `failon` is off (it is on
  when the job does not say). v1 warns and goes on whatever `failon`
  says. A job that deletes a file "in case it is there" has to switch
  `failon` off, as in Talend.
- `<id>_CURRENT_STATUS` holds Talend's words (`File deleted.`, `Path
  deleted.`, `No file deleted.`, `No path deleted.`, `File does not exist
  or is invalid.`, `Path does not exist or is invalid.`, `File or path
  does not exist or is invalid.`). v1 has `deleted`, `not exist`,
  `error`.
- With `failon` off, why nothing was deleted is in `<id>_ERROR_MESSAGE`
  (always, and with the path as it is written; Talend sets it only when
  its own logging is on) and in a warning in the log. A folder that
  could be deleted only in part says so.
- Kept from v1: `recursive` (off, only an empty folder goes; Talend
  always takes a folder with what it holds), and `path` standing in for
  a `filename` or `directory` that is not given.
- Nothing named to delete refuses the job before it runs.

**File exist**

- As v1: `<id>_EXISTS` and `<id>_FILENAME`, a folder counting as there,
  only a folder under `check_directory`. (Talend has no
  `check_directory`.)
- An empty path refuses the job before it runs.

**File row count**

- As v1: the count in `<id>_COUNT`, every kind of line end ending a row
  when the separator is one, any other separator splitting the whole
  text, rows of blanks left out when asked.
- A file that is not there, or not written in its encoding, fails the job
  in plain words. A separator of nothing refuses it before it runs.
- With a separator that is no line end the file is held in memory while
  it is split, as in v1.

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

## Components built to their own rule

These are built for long use and not to v1 or Talend: v1 is not their
answer key, and their tests hold them to what is written here. A converted
job config still loads as it is: the keys the converter writes are the
keys read, and where v1's engine reads another name, that name is taken
too.

What they share:

- What cannot be done fails the job and says why. Where the job config
  itself carries `die_on_error` and it is off, the job goes on with a
  warning, and why is in `<id>_ERROR_MESSAGE`.
- A file is written beside its place and put there when it is whole.
- Each counts one row (`<id>_NB_LINE`, `_OK`, `_REJECT`) unless it says
  otherwise.

**File touch**

- The file `filename` is made empty when it is not there; when it is,
  what it holds is kept and the time it was changed is set to now. A
  folder that is there has its time set as well.
- The file is made in one step that makes it only if nothing is there, so
  a file another job made in the meantime keeps what it holds, and
  nothing is made through a link: a link to nowhere fails the job.
- The folder the file is to stand in has to be there, unless `createdir`
  is on (v1's `create_directory` is taken too).
- The path is left in `<id>_FILENAME`, and the log says whether the file
  was made or was there.
- It is a subjob of its own: a flow to it refuses the job. (Talend lets
  rows flow through it, touching the file once for each.)
