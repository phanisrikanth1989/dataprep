# 34 - A debug level for the log

Status: ready-for-agent
Type: task

## Question

`python -m src.v2 job.json --log-level DEBUG` prints the same lines as INFO:
v2 has no debug lines at all. Give the debug level something to say.

Asked for by the dev on 2026-10-06, during the review of the engine.

## To build

What a person needs when a job does not do what they expected, without
reading the code:

- for each component as it is built: its config after context values are
  put in, and the columns it hands on with their types;
- for each delimited reader: whether Polars parses the numbers itself or
  every column is read as text, and why;
- for each subjob: the plan Polars is given;
- for each output: the temporary file it is written to and the encoding it
  is put in;
- when a subjob is read a second time: the message that made it so.

Nothing here may cost time when the level is INFO: a debug line is not put
together unless it will be written.
