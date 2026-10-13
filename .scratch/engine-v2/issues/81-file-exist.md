# 81 - File exist

Status: resolved
Type: task

## Question

Build v1's file exist (`FileExistComponent`, `tFileExist`) on v2: whether
a file is there is left in globalMap as `<id>_EXISTS`. Asked for on
2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/file/file_exist.py`. The path is
  `file_name` (also `file_path`, `FILE_NAME`); a folder counts as there;
  with `check_directory` only a folder does. It leaves `<id>_EXISTS` (true
  or false) and `<id>_FILENAME`, and counts one row.
- Talend's does the same but for `check_directory`, which it does not
  have (`tFileExist_main.javajet` at Talaxie 639d5fd1f776, lines 24-36).

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_exist.py`; 16 tests in
`tests/v2/components/test_file_exist.py`, written and seen failing while
the review of ticket 84 ran; what it leaves in globalMap is held against
v1's for every case, and a trigger that reads it against v1's files).

- An action: it looks when its turn comes.
- Mutation check: 8 ways of breaking it, each caught.
