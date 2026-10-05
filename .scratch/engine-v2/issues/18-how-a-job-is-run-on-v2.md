# 18 - How a job is run on v2

Status: open
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
