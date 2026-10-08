# 18 - How a job is run on v2

Status: resolved
Type: grilling

## Question

How does a person or a scheduler run a job on v2? There is no command line
for v2 in this repo, and the v1/v2 router stayed behind in ETL-AIAgent.

To settle:

- The command and its arguments. v1's is
  `python src/v1/engine/engine.py <job_config.json> --context_param KEY=VALUE`.
- How v1 or v2 is chosen for a job: a separate command, a key in the job
  config, or a router in front of both.
- A check-only mode that prints the refusal report without running the job.
- What the process exits with, for success, a refused job config and a failed
  run.
- What is logged (ASCII only) and what the result contains.
- The Python entry point that tests and the
  [Answer-key harness](19-answer-key-harness.md) call.

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- `python -m src.v2 job.json [--context_param KEY=VALUE]... [--check]
  [--engine ...] [--log-level ...]`.
- v1 or v2 is chosen by the command that is run; there is no router.
- `--check` loads and checks only. Exit codes: 0 finished, 1 ran and failed,
  2 not run (refused, or a bad command line). v1 exits 0 for a failed job;
  v2 does not copy that.
- Standard output carries a JSON summary of the run; logs (ASCII) and the
  refusal report go to standard error.
- Python entry points: `src.v2.run_job`, `load_job`, `check_job`.
