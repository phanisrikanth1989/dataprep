# 94 - File properties

Status: resolved
Type: task

## Question

Build file properties (`FileProperties`, `tFileProperties`) on v2, to
ticket 87's rule and what
[File jobs: what current practice says](93-file-jobs-what-current-practice-says.md)
found.

## What is known

- The converter writes `filename` and `md5`, and no schema at all
  (`src/converters/talend_to_v1/components/file/file_properties.py`): a
  converted job declares no columns. v1's engine reads `FILENAME` and
  `MD5`, in capitals.
- Talend's schema is fixed and cannot be edited: seven columns, and
  `md5` when MD5 is ticked.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_properties.py`, a
`Source`; 34 tests in `tests/v2/components/test_file_properties.py`, v2
alone, seen failing first).

- The schema says which properties are wanted (Data Factory's field
  list): Talend's eight names, and `sha256`, `type` and `exists`. No
  schema: Talend's seven, `md5` an eighth when the key is on, and the
  check at load goes on down the flow with them.
- `exists` among the columns makes a missing file a row, not a failure
  (Data Factory's rule). Without it the job fails: `File not found`.
- `mode_string` is `ls -l`'s ten characters (Python's `stat.filemode`),
  which fits the length Talend declares for the column; `mtime`
  milliseconds as in Talend; `mtime_string` local time as v1 writes it;
  `dirname` in full.
- A check sum is read for only when asked, both from one reading, and
  once in a run (`RunContext.made`), with `usedforsecurity=False` so
  that a server in FIPS mode does not refuse `md5`.
- One row, numbered 1, named `the properties of <filename>`; a key
  column is shown beside it; a run can be for it (`rows: [1]`, or by
  what a column holds) and traced.
- Mutation check: 32 ways of breaking it, 27 caught at first. The five
  that were not each got a test (the file read only when asked, read
  once in a run, the columns' own types, a link followed), but for one:
  the call that keeps a source to its picked rows could not matter with
  one row, and was taken out with a note.

For the loop components to remember: what a source makes once in a run
(`RunContext.made`) is kept by the component's id. A subjob that runs
once for each item has to start each time with that emptied.
