# 97 - File archive

Status: resolved
Type: task

## Question

Build the file archive (`FileArchive`, `tFileArchive`) on v2, to ticket
87's rule and what
[File jobs: what current practice says](93-file-jobs-what-current-practice-says.md)
found.

## What is known

- The converter writes `source`, `source_file`, `sub_directroy`,
  `target`, `mkdir`, `archive_format`, `level` (as text), `all_files`,
  `mask` (a list), `encoding`, `overwrite`, the encryption keys (the
  password always empty), `zip64_mode` and `use_sync_flush`. v1's engine
  reads `include_subdirectories` and `compression_level` for two of them
  and one mask as text, and writes zip only.
- Talend's layout (`Zip.java`, ticket 93): files only, each by its path
  below the source folder; a mask has to fit the whole name of a file;
  no file taken, no archive, and the old one is already deleted.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_archive.py`, an
`Action`; 61 tests in `tests/v2/components/test_file_archive.py`, v2
alone, seen failing first).

- Talend's layout kept: files only, by their path below the folder. The
  order is fixed, by name (Talend's is whatever the file system gives).
- Kinds: Talend's three (`zip`, `gzip` for one file, `tgz`), and `tar`,
  `tar.zst` and `zst`. Zstandard is in Python from 3.14; on an older one
  a job that asks for it is refused when it loads, with the reason.
  Measured here on 76 MB of delimited text (Python 3.14.6, this Mac, not
  the RHEL servers): at level 4, gzip packs 102 MB a second to a ratio
  of 3.11, Zstandard 350 MB a second to 3.15; unpacking is about 1.1 to
  1.3 GB a second for both.
- A mask is a file-name pattern (`*`, `?`, `[abc]`), held against the
  name with capitals told apart. Talend's is a regular expression in
  which only `*` and `.` are changed; `*.csv` means the same in both.
- Written beside the target with the engine's own naming and put in
  place with `put_in_place`. A failure leaves the archive that was
  there.
- The same files give the same bytes: a fixed order; a tar entry with
  no owner and a time in whole seconds; no time in a `tgz`'s gzip
  header. Held by a test that archives the same files twice in two
  folders.
- A link or a special file among the files is left out and named in a
  warning. A folder that cannot be looked into fails the job: Python's
  walk passes such a folder over in silence unless told otherwise, and
  the first version did (found by rereading; test first).
- A source that is a pipe or a device is refused and never opened.
  Found when a mutant that let a pipe through made the tests wait for
  ever: the same would happen to a job. The raw file input, change file
  encoding and file properties got the same guard, in a commit of their
  own.
- No file taken: no archive, the old one taken away, a warning,
  `<id>_NB_FILE` 0. As in Talend, so that an old archive is never taken
  for this run's.
- Encryption is refused at load (Python writes no encrypted zip). The
  name encoding, ZIP64 mode and sync flush keys are taken and have no
  effect.
- Mutation check: 71 ways of breaking it, 67 caught at first; the other
  four each got a test (an archive written over keeps its permissions,
  what is wrong with the target said before any file is read and in
  plain words, no time in a `tgz`'s gzip header). The script that runs
  the mutants gives each a minute now: one of them made the tests wait
  on a pipe for ever.
