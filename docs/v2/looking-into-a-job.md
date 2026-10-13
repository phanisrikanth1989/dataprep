# Looking into a job

A failure says which row of which source it failed on. The job can then
be run for that row alone, and the run can list what every component did
with it.

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
| filter rows, filter columns, sort row, unique row, log row, map, unite, replicate, sample row, replace, convert type, schema compliance check, extract delimited fields, extract positional fields, extract regex fields, warn, set global var | keeps its number |
| join | keeps the main input's number; a lookup's is left behind |
| normalize, split row, unpivot row, extract JSON fields | every row made carries the number of the row it came from |
| aggregate row, aggregate sorted row, denormalize | carries the lowest number of its group, and the message says "the first of 11,112 rows that were combined" (rows as they reached the component: after a normalize, several of them come from one row of the source) |
| Python dataframe | has none: what the code hands back is a table of its own making |
| context load, die | hand no rows on (a die's message names the row that reached it) |

Which failures name their row: a reader that cannot read a row, a missing
value in a column that may not hold one (after any component), text a map
cannot read as its output column's type, and a conversion in an expression
(`int()`, `float()`, `strptime()`). A failure Polars raises by itself still
names the value and no row. Few are left to it: user Python, and a whole
number asked of something that is not a number in `round()` or
`math.floor()`.

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

## What every component did with them

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
