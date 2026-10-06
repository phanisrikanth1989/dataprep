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
```

| Exit code | Meaning |
|---|---|
| 0 | the job finished |
| 1 | the job ran and a component failed |
| 2 | nothing ran: the job config was refused, or the command line was wrong |

Log lines at INFO and DEBUG go to standard output. Warnings and errors go
to standard error, and so do the refusal report and what is wrong with the
command line: an empty standard error means a clean run. `--log-level`
names the lowest level that is written (`INFO` unless told otherwise).

A summary of the run is the last thing written to standard output, as JSON
(`status`, `error`, `failed_component`, `failures`, `rows` written by each
output, `duration_s`). `--summary FILE` writes it to a file as well, so
that nothing has to pick it out of the log. The file is opened before the
job runs: when it cannot be written, nothing runs (exit code 2). A job that
was not run leaves the file as it was.

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

## Taking a v1 job config to v2

1. Run `python -m src.v2 job.json --check`. The refusal report lists
   everything that stops the job, component by component.
2. Rewrite every Java expression (`{{java}}...`) in Python. See
   "Expressions" below.
3. Replace or remove components v2 does not have. v2 has sixteen: delimited
   file input and output, positional, full-row and Excel input, filter rows,
   filter columns, sort row, unique row, aggregate row, join, unite, map,
   Python dataframe, log row and context load.
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
  are taken only when something in the job reads them.
- After each component the engine makes its output match the declared
  schema, as v1 does: column order, columns nobody produced, types, decimal
  places, and columns that may not hold a missing value.

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
  instance. An operation on a missing value never fails; it gives a missing
  value. Rows are not sent to a catch output.
- An output column nothing in the job reads is never worked out, so an
  expression there that would fail on a row does not fail the job. v1 works
  out every column of every output.
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
