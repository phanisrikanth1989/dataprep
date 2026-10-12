# 88 - File touch

Status: resolved
Type: task

## Question

Build file touch (`FileTouch`, `tFileTouch`) on v2, to ticket 87's rules.

## What is known

- The converter writes `filename` and `createdir`; v1's engine reads
  `create_directory` for the second.
- Talend makes the file when it is not there and sets its time to now
  when it is.
- Talend's own source (Talaxie `tdi-studio-se@639d5fd1f776`,
  `tFileTouch_main.javajet`): `createNewFile()`, which makes the file
  only if it is not there, in one step; else `setLastModified(now)`.
  `mkdirs()` of the parent under `CREATEDIR`. It allows a flow through
  it and an iterate link to it (`tFileTouch_java.xml`).

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_touch.py`, an `Action`;
21 tests in `tests/v2/components/test_file_touch.py`, v2 alone, seen
failing first).

- Made only if nothing is there, in one step (`open(path, "xb")`): no
  look-then-make, so a file made in the meantime keeps what it holds,
  and nothing is made through a link (a link to nowhere fails the job; a
  link to a file sets the file's time).
- A folder that is there has its time set; a name ending in `/` is a
  folder, made under `createdir`, and no file is made of it.
- The missing folder fails the job unless `createdir` (or v1's
  `create_directory`) is on.
- `<id>_FILENAME`, one row counted, and an INFO line saying whether the
  file was made or was there.
- A flow to it refuses the job (the engine's own rule for an action).
  An iterate link to it is for the loop components to bring.
- Mutation check: 18 ways of breaking it, 17 caught; the eighteenth
  showed a condition that could never matter, which was taken out.
