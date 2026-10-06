# 35 - Log to stdout, warnings and errors to stderr

Status: resolved
Type: task

## Question

Every log line goes to stderr today, and stdout holds only the JSON summary.
Send the log where an operator and a scheduler expect it.

Decided by the dev on 2026-10-06, during the review of the engine: split by
level.

## What was decided

- INFO and DEBUG lines go to stdout.
- WARNING and above go to stderr. An empty stderr then means a clean run.
- The JSON summary stays on stdout, as the last thing written.

Proposed with it, to be confirmed when it is built: `--summary FILE` writes
the summary to a file as well, so that nothing has to pick JSON out of a log.

## What is known

- v1 logs to stderr too, but not by decision: it sets logging up without
  naming a stream, and Python's default is stderr.
- The refusal report and a bad command line are errors and stay on stderr.
- `docs/v2/README.md` ("Running a job") and `CLAUDE.md` (entry points) say
  how the command line behaves and have to say this too.

## Answer

Built on 2026-10-06 (`src/v2/cli.py`, tests in `tests/v2/unit/test_cli.py`).

- INFO and DEBUG lines go to standard output, WARNING and above to standard
  error. A job that finishes without a warning leaves standard error empty.
- The JSON summary is the last thing on standard output, after the log.
  Whatever read all of standard output as JSON has to change: it now holds
  the log as well.
- `--summary FILE` was built with it. It was the dev's to confirm and the
  dev was not there to ask; it is one flag and can be taken out. The file is
  opened before the job runs, so a summary that has nowhere to go stops the
  command with exit code 2 and nothing runs. A job that ran is never
  reported as failed for its summary's sake, which could have a scheduler
  run it twice: if the file cannot be written once the job has run (a disk
  that filled up), that is said on standard error and the exit code stays
  the job's. The file is empty while the job runs, so a run that is stopped
  leaves no summary of an earlier run behind. A job that was not run leaves
  the file as it was.
- A character standard output cannot write (a server whose locale is not
  UTF-8) is written as an escape, as standard error does by itself. Without
  that the line was dropped and logging complained on standard error; when
  every line went to standard error this could not happen.
- The command puts its two log handlers on when it starts and takes them off
  when it ends. `run_job` called from Python sets up no logging, as before.
