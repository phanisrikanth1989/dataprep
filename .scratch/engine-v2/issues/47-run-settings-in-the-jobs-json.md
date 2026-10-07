# 47 - Run settings in the job's JSON

Status: claimed
Type: grilling

## Question

How a job is run (how much it logs, whether rows are counted, and the like)
is said on the command line today. Which of these settings should a job's
own JSON be able to hold, where in the JSON, and who wins when the JSON and
the command line disagree?

## What the dev asked (2026-10-07)

"Config in JSON: the ability to configure logging, enabling row count, and
all such aspects directly in the config JSON."

Ticketed only. To be grilled with the dev before anything is built.

## What is there today

Every setting of a run, and where it is set now:

| Setting | Set by |
|---|---|
| Lowest log level written | `--log-level` (INFO when not given) |
| Row counts of every component | `--row-counts`; `run_job(..., row_counts=True)` |
| A copy of the summary in a file | `--summary FILE` |
| Check the job and run nothing | `--check` |
| Context values | `--context_param KEY=VALUE`; the JSON's `context` |
| Polars engine | `--engine`; the environment variable `V2_ENGINE` |
| Tolerant reader from the start | the environment variable `V2_SAFE_READ` |
| Folder for scratch files | the environment variable `V2_TEMP_DIR` |
| Key column of a source | already in the JSON: `"key": true` on a schema column |

Where the log goes is not a setting: INFO and DEBUG to standard output,
warnings and errors to standard error, in one fixed layout
(`src/v2/cli.py`). A caller of `run_job` sets up logging itself.

Facts found on 2026-10-07 by running both engines on a job with a block
neither knows (`"run": {...}` at the top level):

- v2 refuses the job at load: "run: unknown config key". Every key v2 reads
  is declared (`JOB_KEYS` in `src/v2/job/loader.py`), so a settings block
  needs a declared key.
- v1 runs the job and takes no notice of the block. A block added for v2
  does not stop a job from running on v1.
- v1 has a block of its own for engine settings, `engine_config`, which v2
  is told to ignore.
- The converter writes none of this: these settings have no Talend
  counterpart that it carries over.

## A first shape, to react to

```json
{
  "job_name": "payments_end_of_day",
  "run": {
    "log_level": "INFO",
    "row_counts": true,
    "summary_file": "/logs/payments_summary.json"
  },
  "components": []
}
```

## To settle in the grilling

1. **Which settings.** Only the log level and the row counts, as named, or
   every row of the table above? "All such aspects" could also mean things
   that are not settings yet: a file for the log, another layout for it
   (JSON lines for a machine), settings for one component only.
2. **Where in the JSON, and its name.** A block of its own at the top level
   (`run`, `v2`, `run_config`), or inside v1's `engine_config`.
3. **Who wins.** The usual order is command line over JSON over the
   default, so that one job file can be run louder for a day without being
   edited. The other way round makes the JSON the one place to look.
4. **Does "logging" include where the log goes.** Today a scheduler
   redirects the two streams. A log file named in the JSON would be new
   behaviour (who rotates it, what happens when it cannot be opened).
5. **`run_job` from Python.** Whether the block is read there too, with the
   function's own arguments winning.
6. **A setting v2 does not know** inside the block: refused at load, as
   every unknown key is.
7. **Tickets 49 and 50.** If a run can be for one record, with every
   component's output printed, those settings would live in the same place.

## Where I lean, to be argued with

- **Start with the three that are about the job**: log level, row counts,
  summary file. The Polars engine, the tolerant reader and the scratch
  folder are about the machine a job runs on; a job file that moves from
  one server to another should not carry them.
- **A block of its own at the top level**, not inside `engine_config`,
  which is v1's and which v2 ignores whole.
- **Command line over JSON over default.** It is the order this engine
  already has for context values (`--context_param` over the JSON's
  `context`), and it lets support run one job louder for a day without
  touching its file.
- **The level only, not where the log goes**, until someone needs a log
  file: a file brings rotation, rights and "what if it cannot be opened".
- **Say at the start of the run what the JSON turned on.** A run that
  counts rows takes three times as long, and whoever reads the log should
  not have to open the job file to learn why.

Related: [Run a job with one command](48-run-a-job-with-one-command.md)
(what the command takes and what the JSON holds are two halves of one
answer).
