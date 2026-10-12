# Running a job

```bash
python -m src.v2 job.json                                  # run
python -m src.v2 job.json --context_param in_dir=/data     # set context variables
python -m src.v2 job.json --check                          # load and check only; run nothing
python -m src.v2 job.json --summary run.json               # also write the summary to a file
python -m src.v2 job.json --row-counts                     # log the row counts of every component
python -m src.v2 job.json --only payments_in:txn_id=654321 # run for one row (see looking-into-a-job.md)
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
output, `counts`, `duration_s`, and `loops` when the job has any). `--summary FILE` writes it to a file as
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


## Run settings in the job config

A job config can say how it is run, in a `run` block at its top level:

```json
"run": {"log_level": "DEBUG", "row_counts": true, "summary_file": "/logs/pay.json"}
```

| Key | Same as |
|---|---|
| `log_level` | `--log-level` |
| `row_counts` | `--row-counts` |
| `summary_file` | `--summary FILE` |
| `only` | `--only` ([Looking into a job](looking-into-a-job.md#running-a-job-for-a-few-rows)) |
| `trace` | `--trace` ([Looking into a job](looking-into-a-job.md#what-every-component-did-with-them)) |

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


## From a service

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
column, as a group of their own; see
[Aggregate row](differences-from-v1/rows.md#aggregate-row).)

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
