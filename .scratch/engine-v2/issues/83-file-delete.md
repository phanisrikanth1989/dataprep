# 83 - File delete

Status: resolved
Type: task

## Question

Build v1's file delete (`FileDelete`, `tFileDelete`) on v2: a file or a
folder is deleted. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/file/file_delete.py`. Three ways: a file
  (`filename`), a folder (`folder` on, `directory`), or whichever the
  path is (`folder_file` on, `path`). A folder goes with everything in it
  unless `recursive` is off. It leaves `<id>_DELETE_PATH` and
  `<id>_CURRENT_STATUS` (`deleted`, `not exist`, `error`).
- Where v1 and Talend differ (`tFileDelete_main.javajet` at Talaxie
  639d5fd1f776):

  | | Talend | v1 |
  |---|---|---|
  | nothing is there to delete, `failon` on | the job fails | a warning, the job goes on |
  | `<id>_CURRENT_STATUS` | `File deleted.`, `Path deleted.`, `No file deleted.`, `No path deleted.`, `File does not exist or is invalid.`, `Path does not exist or is invalid.`, `File or path does not exist or is invalid.` | `deleted`, `not exist`, `error` |

  `failon` is on unless the job says otherwise, in both.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_delete.py`; 24 tests in
`tests/v2/components/test_file_delete.py`, 23 of them written and seen
failing while the review of ticket 84 ran; what is in the folder
afterwards is held against v1's wherever something is deleted, and with
`failon` off where nothing is).

- An action. Decided from Talend's source, without asking: nothing there
  to delete fails the job under `failon`, and the status is in Talend's
  words. Read in the source, not run in Talend. This one changes whether
  a job fails, so it is worth a look by the user.
- Mutation check: 18 ways of breaking it, each caught.
