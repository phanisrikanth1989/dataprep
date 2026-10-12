# 104 - File list

Status: resolved
Type: task

## Question

Build the file list (`FileList`, `tFileList`) on v2, to
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md)
and the research's table for it
([Loops and job control](../research/2026-10-12-loops-and-job-control.md),
3.5).

## What is known

- The converter writes sixteen keys; v1's engine reads Talend's own
  names in capitals as well, and two keys of its own for the order.
- Talend (Talaxie `639d5fd1f776`, `tFileList_begin.javajet`): the list
  is built whole and then looped over; a mask is turned into a regular
  expression by Jakarta ORO and has to fit the whole name; the exclude
  field is split on commas; "by default" is `Collections.sort` over the
  files, which is by path; the entries of a pass are five.
- There is a converted sample job
  (`tests/talend_xml_samples/converted_jsons/Job_tFileList_0.1.json`):
  file list, a reader of the file the loop is at, a map, and one output
  that every pass adds to.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_list.py`, an `Action`
that starts a loop; 71 tests in `tests/v2/components/test_file_list.py`,
seen failing first).

- Talend's five entries for a pass, under its names; the path in full.
- Masks in Talend's own pattern form, by a translator of a few lines
  (`pattern_of`), held to ORO's rules by a table of cases. Python's
  `fnmatch` reads `[^a]` and a backslash another way, so a converted
  mask would have changed its meaning.
- By path when no other order is asked for; by name, size or date with
  the name and then the path where two are the same, so that the same
  folder gives the same list twice.
- Left out: dot names (unless a mask that starts with a dot fits), files
  v2 itself is still writing, links out of the folder and what is no
  file; dot folders and linked folders are not gone into.
- The folder that is not there, or cannot be looked into, fails the job.
- `min_age_seconds`, v2's own, for a folder files are still arriving in.
- The converted sample job runs as the converter wrote it, once the four
  Java expressions of its map are written in Python: two files found,
  two passes, three rows in the one output. Its reader's path,
  `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`, is read as
  it stands.
- A file's size and time are asked for only when the order or the age
  needs them.

Not built, and said on the page: nothing waits for a file to be
finished; a loop goes on after no failed pass.

Mutation check: 57 ways of breaking it, 54 caught at first; the three
others each got a test (the log's name for a pass, a folder with a dot
in its name, folders before files by name).
