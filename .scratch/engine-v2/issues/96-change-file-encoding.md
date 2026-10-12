# 96 - Change file encoding

Status: resolved
Type: task

## Question

Build change file encoding (`ChangeFileEncoding`, `tChangeFileEncoding`)
on v2, to ticket 87's rule and what
[File jobs: what current practice says](93-file-jobs-what-current-practice-says.md)
found.

## What is known

- The converter writes `use_inencoding`, `inencoding`, `infile_name`,
  `outfile_name`, `encoding`, `buffersize` (as text) and `create`. There
  is a converted sample job
  (`tests/talend_xml_samples/converted_jsons/Job_tChangeFileEncoding_0.1.json`);
  it has a tJava beside the component, so the job as a whole does not
  load on v2.
- Talend's readers and writers replace what they cannot read or write
  and say nothing.

## Answer

Built on 2026-10-12 (`src/v2/components/file/change_file_encoding.py`,
an `Action`; the work is `transcode` in `src/v2/files.py`; 46 tests in
`tests/v2/components/test_change_file_encoding.py`, v2 alone, seen
failing first).

- Strict both ways, in pieces of 16 MB, with incremental decoders and
  encoders, so a character cut by the end of a piece is whole again in
  the next. The place of a fault is counted across the pieces: the byte
  and the line for a byte that is no character, the line for a
  character that cannot be written. The tests run with pieces of 1 to 8
  bytes to cut through every character.
- The encoder is told when the text has ended: an encoding that switches
  character sets as it goes (ISO-2022-JP, HZ) has to end switched back.
- UTF-8 when no input encoding is to be used. Talend takes the
  machine's, which a job should not depend on; and text in an 8-bit
  encoding that is read as UTF-8 fails at once and says so, where the
  other way round it would be written wrong without a word.
- A byte order mark at the start of the input is not carried over, and
  one in the middle of a file is left alone.
- Written beside the output (the engine's own naming of such files,
  moved from the runner to `files.temp_beside` for it) and put in place
  with `put_in_place`, as every file output is: the output may be the
  input, an output that is there keeps its permissions, and a failure
  leaves it as it was, with no file left beside it.
- The component of the converted sample loads as the converter wrote it
  (`tests/v2/test_converter_samples.py` checks its keys as well).
- Mutation check: 38 ways of breaking it, 34 caught at first; the four
  others each got a test (a mark in the middle of a file, the message
  plain ASCII from the function itself, the size in the log, an encoding
  that has to be told the text has ended).

Seen on the way: Python's incremental UTF-7 encoder writes other bytes,
of the same text, depending on where the pieces end. UTF-7 output is
right but is not the same bytes as a one-step conversion; no test holds
it to that.
