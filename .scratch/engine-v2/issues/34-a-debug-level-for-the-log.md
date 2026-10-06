# 34 - A debug level for the log

Status: resolved
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

## Answer

Built on 2026-10-06. Tests in `tests/v2/unit/test_debug_log.py` and at the
end of `tests/v2/components/test_file_delimited.py`.

What `--log-level DEBUG` adds, line by line:

    [in] config: {"path": "in.csv", "delimiter": ";", ...}
    [in] Polars parses the numbers of id, amt itself; every other column is read as text
    [in] every column is read as text: <why>
    [in] output main: id Int64, name String
    [job] sources may let Polars parse numbers itself in this subjob: <why>
    [job] sources read every column as text in this subjob: <why>
    [out] writing to the temporary file /data/.out.csv.out.v2tmp123
    [job] plan of output out:            (the plan follows, on lines of its own)
    [job] plan of what <id> asked to know:
    [job] plan of the rows <id> is handed:
    [out] the written file is put in the encoding ISO-8859-15
    [job] what the fast reader said, in full:

- The config is the one the component runs with: context values put in,
  defaults filled in, v2's names for the keys.
- The plan is the one Polars is given, before Polars rearranges it. There is
  one for each output, each thing a component asked to know (a check, a
  count) and each set of rows a component is handed.
- The reader's reasons for reading text: v2 splits the rows itself; the
  engine asked for the tolerant reader; the reject output is wired; the
  file has a footer; no column is declared int or float.
- The line of a subjob that is read a second time was at INFO already, with
  Polars' message cut to one line. DEBUG adds the message in full.
- Every debug line is behind `logger.isEnabledFor(logging.DEBUG)`. A test
  holds that Polars is not asked for a plan at INFO.
- Every one of these lines is plain ASCII as a whole, ids and paths
  included: any other character is written as its escape (`ascii_only` in
  `src/v2/components/base.py`).
- A debug line cannot fail a job. The one call in them that is not the
  engine's own, Polars printing a plan, is caught: the log then says the
  plan could not be printed.

Only the delimited reader chooses between the two ways of reading numbers,
so only it has that line.
