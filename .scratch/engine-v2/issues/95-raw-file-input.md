# 95 - Raw file input

Status: resolved
Type: task

## Question

Build the raw file input (`FileInputRaw`, `tFileInputRaw`) on v2, to
ticket 87's rule and what
[File jobs: what current practice says](93-file-jobs-what-current-practice-says.md)
found.

## What is known

- The converter writes `filename`, `as_string`, `as_bytearray`,
  `as_inputstream`, `encoding`, `die_on_error`, and the schema Talend
  fixes: one column, `content`, of type `object`
  (`src/converters/talend_to_v1/components/file/file_input_raw.py`;
  `id_Object` converts to `object`, every other type v2 has no name for
  to `str`, `type_mapping.py`).
- v2's loader refused a column declared `object`: a converted job with a
  raw file input did not load at all.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_input_raw.py`, a
`Source`; 34 tests in `tests/v2/components/test_file_input_raw.py`, v2
alone).

- In the loader, a column declared `object` (or `id_Object`) is held as
  text, as the converter has it for every other Talend type v2 has no
  name for. A commit of its own, test first.
- The text as the file has it: line ends kept, a byte order mark left
  out. Read strictly; the fault names the byte and its line.
- One value in memory is the component's purpose, so the one thing
  bounding it is said in the config: `size_limit_mb`, 1024 when not
  given, held against the file's size before a byte is read.
- `die_on_error` off, which is what a converted job says unless the
  dev ticked the box in Talend: no row, a warning, and
  `<id>_ERROR_MESSAGE`. With no `die_on_error` in the job config a file
  that cannot be read fails the job.
- Bytes and streams are refused at load, with what to do in their place.
- One row, numbered 1, named `the content of <filename>`; read once in
  a run; the check at load goes on down the flow with `content`.
- Mutation check: 35 ways of breaking it, 31 caught at first; the other
  four each got a test (the check going on at load, the key shown
  beside the place, the refusal of picking by line, a file exactly as
  large as the limit).

The slips, said plainly:

- The tests were written before the code but were not run before it, so
  they were not seen failing first. The mutation check stands in for
  that: every test was seen to fail on some mutant.
- The tool that writes files turned `\u` escapes into the characters
  themselves, a byte order mark in the source among them. Found by the
  mutation check (a mutant did not apply), and put back as escapes.

Found on the way, not changed: in the fixed flow input (a component held
to v1), text that is no number in a whole-number column that may not be
missing becomes a missing value and the job succeeds, in v1 and in v2
alike.
