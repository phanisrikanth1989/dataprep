# 106 - Unarchive as the start of a loop

Status: resolved
Type: task

## Question

In Talend the file unarchive is also the start of a loop: an iterate
link may leave it, and what the link leads to runs once for each file
unpacked. [File unarchive](98-file-unarchive.md) left that for when the
engine could loop. It can now
([The iterate link](102-the-iterate-link.md)). Build it, to
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md).

## What is known

- Talend's component takes an iterate link out, and puts
  `<id>_CURRENT_FILE` and `<id>_CURRENT_FILEPATH` for each file while it
  unpacks (read in Talaxie's `tFileUnarchive_java.xml` and
  `tFileUnarchive_begin.javajet`, commit `639d5fd1f776`). It has no
  other entry for the loop.
- v2's unarchive is all or none: the files land together at the end.

## Answer

Built on 2026-10-12 (six tests in
`tests/v2/components/test_file_unarchive.py`, seen failing first: the
job was refused, "a FileUnarchive starts no loop").

- The component hands the engine one item for each file it unpacked, in
  the order of the archive: the file's name and its full path, under
  Talend's two names. The log names an item by its path below the
  folder.
- The loop starts when the whole archive is unpacked. In Talend a pass
  runs while the next file is still packed; here a pass never sees half
  an archive, and an archive that is damaged runs no pass at all.
- No file, or an archive that cannot be unpacked in a job that goes on:
  no pass.
- `max_items` holds as for every loop. More files than that fail the
  job before the first pass. The archive is unpacked by then: the cap
  is the loop's, not the unpacking's.
- `<id>_NB_FILE` is the number of files in every pass (the file list
  counts up there; Talend's unarchive has no such entry).
- Mutation check: seven ways of breaking it, all caught.
