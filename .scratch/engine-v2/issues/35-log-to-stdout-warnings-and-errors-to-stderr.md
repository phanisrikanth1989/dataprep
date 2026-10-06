# 35 - Log to stdout, warnings and errors to stderr

Status: ready-for-agent
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
