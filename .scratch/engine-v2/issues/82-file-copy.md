# 82 - File copy

Status: resolved
Type: task

## Question

Build v1's file copy (`FileCopy`, `tFileCopy`) on v2: a file or a folder
is copied, or moved. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/file/file_copy.py`. `filename` (or
  `source`) is copied into the folder `destination`, under its own name or
  `destination_rename` when `rename` is on; with `enable_copy_directory`
  the folder `source_derectory` (Talend's spelling) is copied to
  `destination`. `create_directory` makes what is missing, `remove_file`
  takes the source away afterwards, `replace_file` says whether a file
  that is there is written over.
- Where v1 and Talend differ (`tFileCopy_main.javajet` at Talaxie
  639d5fd1f776):

  | | Talend (lines) | v1 |
  |---|---|---|
  | a copy that fails | fails the job only with `failon` (163, 239) | fails it unless `die_on_error` is written and off |
  | the file is there, not to be replaced | no copy, no fault (188) | a fault |
  | the time the file was changed | kept only when asked (206) | always kept |
  | globalMap after a copy | `<id>_DESTINATION_FILEPATH`, `_DESTINATION_FILENAME`, `_SOURCE_DIRECTORY`, `_DESTINATION_DIRECTORY` (146, 266) | nothing |

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_copy.py`; 20 tests in
`tests/v2/components/test_file_copy.py`, written and seen failing while
the review of ticket 84 ran; seven of them hold what is in the folder
afterwards against v1's).

- An action. Decided from Talend's source, without asking, for the four
  rows of the table above; each is in the README. Read in the source, not
  run in Talend.
- One thing is neither v1's nor Talend's: when the file is there and not
  to be replaced, the source is left even with `remove_file` on. Talend's
  template removes the source in a step after the copy step (lines 226
  to 250); whether it does so when nothing was copied was not traced to
  the end, and v2 does not.
- Mutation check: 23 ways of breaking it, each caught.

Not done: `force_copy_delete`, Talend's other way of moving a file.

## Corrected after review (ticket 85)

- The table above is of a file's copy only. A folder's copy followed v1
  where Talend differs, and could lose data: copied into itself with the
  source to be taken away, everything was deleted. A folder is now
  copied as Talend copies it (under its own name, over what is there,
  the source never taken away), and never into itself.
- Wrong above: a source left when nothing was copied is Talend's rule
  too (the removal is part of the copy, line 206; lines 231 to 262 only
  look whether the source is still there).
- The globalMap entries are left whatever becomes of the copy, with
  Talend's values; a file named as the destination, a copy the system
  refuses and a source that cannot be taken away are each said in plain
  words with the path.
