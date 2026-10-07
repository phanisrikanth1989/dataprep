# 48 - Run a job with one command, handing it the JSON

Status: resolved
Type: grilling

## Question

A job can be run from the command line today. What is still missing for
"run it directly with a command, passing the JSON to the engine": who calls
the command, from where, and how is the JSON handed over?

## What the dev asked (2026-10-07)

"Run by command: ensure the job can be run directly with a command, passing
JSON to the engine."

Ticketed only. To be grilled with the dev before anything is built.

## What is there today

```
python -m src.v2 <job_config.json> [--context_param KEY=VALUE] [--check]
                 [--row-counts] [--summary FILE] [--log-level LEVEL] [--engine NAME]
```

- Exit code 0 finished, 1 ran and failed, 2 not run (the job was refused,
  or the command line was wrong).
- The log goes to standard output and standard error; a summary of the run
  is the last thing on standard output, as JSON, and `--summary FILE`
  writes it to a file as well.
- v1's command has the same shape:
  `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]`.

What it does not do, found by trying on 2026-10-07:

- **The JSON is taken as a file path only.** `python -m src.v2 -` with the
  JSON on standard input ends with "No such file or directory: '-'", and
  the JSON text given as the argument is taken for a path too.
- **It has to be started from the repository's root** with the Python that
  has the packages: the command is a module path (`src.v2`), and
  `pyproject.toml` declares no command to install. From another folder it
  runs only with the repository on `PYTHONPATH`.
- **A relative path inside the job is taken from the folder the command is
  started in**, not from the folder of the job file. The same job run from
  another folder fails with "File not found: 'in.csv'".
- Nothing else in this repository starts the engine: whoever calls the
  command (a scheduler, the studio, a person) is outside it.
- A tool can already get the summary alone: with `--log-level WARNING` a
  clean run prints nothing on standard output but the summary's JSON.

## To settle in the grilling

1. **Who calls it, and with what in hand.** A scheduler with a job file on
   disk, the studio with the JSON in memory, a person at a terminal. That
   decides the rest.
2. **How the JSON is handed over.** A file path (works today), the text on
   standard input, the text as an argument. Standard input suits a caller
   that holds the JSON in memory and wants no file; an argument has a
   length limit and shows the job in the process list.
3. **The command's name and where it runs from.** `python -m src.v2` from
   the repository's root as now, or an installed command that runs from
   anywhere (`dataprep-v2 job.json`), which needs the package installed on
   the server.
4. **Relative paths in a job.** From the folder the command is started in
   (today, and v1), or from the folder of the job file. With the JSON on
   standard input there is no job file's folder.
5. **What the caller reads back.** The exit code and the summary are there.
   Whether the caller needs more: the log as JSON lines, the summary alone
   on standard output and the log elsewhere.
6. **The same for v1?** `src/v1` is not changed to suit v2, so this is for
   v2's command only unless the dev says otherwise.

## Where I lean, to be argued with

- **Add standard input** (`python -m src.v2 -`) beside the file path. It is
  the usual way for a caller that holds the JSON in memory, and it costs
  little. Not the JSON as an argument: the job would show in the process
  list, and a long job passes the length an argument may have.
- **Keep `python -m src.v2` as the command** unless the servers install
  the package. An installed command needs a `pip install` on each server,
  and this repository's code is imported as `src.*`, which is an odd name
  to install.
- **Relative paths stay as they are** (from the folder the command starts
  in), as in v1, and the docs say so.
- **Nothing new for reading the result** until a caller says what it
  lacks: exit code, summary, `--summary FILE` and `--log-level WARNING`
  cover a scheduler and a tool.

Much of this may already be there. The first thing to learn in the
grilling is what the dev found missing when trying to run a job by command.

Related: [Run settings in the job's JSON](47-run-settings-in-the-jobs-json.md).

## Answer

Grilled with the dev on 2026-10-07, then built (6 tests in
`tests/v2/unit/test_started_from_anywhere.py`).

Decided:

- No new command name. The dev wants to give the engine's path in the
  command and have it work from any folder.
- Nothing is changed in `api/`. What the dev asked is that a request of the
  shape the API has (job config, context overrides, run settings) works on
  v2, with any change needed made inside v2.
- A full path to a job file and full paths inside a job worked already.
  Relative paths inside a job stay as they are: from the folder the command
  is started in, as in v1.
- Standard input was not asked for and is not built.

Built:

- `python /opt/dataprep/src/v2 /data/jobs/pay.json` runs from any folder.
  Started by its path, Python looked for modules in the engine's folder,
  where the relative imports failed and `types.py` would have been taken
  for the standard library's; the entry point has it look in the project's
  folder instead. `python -m src.v2` from the project's folder is as it
  was.
- The request shape, held by a test that runs it as `api/routes/jobs.py`
  runs v1 (the job config as a dict, context overrides as text, in a
  background thread): `run_job(job_config, context=context_overrides,
  run=run)`, and `result.summary()` goes back as JSON. A run setting that
  is not known is refused before anything runs.

For whoever changes the API: choosing v2 is the API's own switch; the call
above is all v2 needs.
