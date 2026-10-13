# 98 - File unarchive

Status: resolved
Type: task

## Question

Build the file unarchive (`FileUnarchive`, `tFileUnarchive`) on v2, to
ticket 87's rule and what
[File jobs: what current practice says](93-file-jobs-what-current-practice-says.md)
found.

## What is known

- The converter writes `zipfile`, `directory`, `rootname`, `integrity`,
  `extractpath`, `checkpassword`, `decrypt_method`, `password`,
  `die_on_error` (off unless ticked), `printout`, `use_encoding` and
  `encording`. v1's engine reads `extract_path` and `check_password`
  for two of them.
- Python's `zipfile.extractall` moves a name that climbs out of the
  folder into it and says nothing, and writes a link as a file holding
  the link's target; `tarfile` leaves half an archive behind when it
  fails; neither holds an archive against the space there is (tried,
  ticket 93).

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_unarchive.py`, an
`Action`; 77 tests in `tests/v2/components/test_file_unarchive.py`, v2
alone, seen failing first).

- The kind is told from the content. A tar is tried first: its header
  carries a check sum of itself, so nothing else is taken for one,
  where the end of a zip may stand in any file that holds a zip.
- All or none, as Python's documentation advises ("Extract to a new
  temporary directory"): unpacked into a folder beside the files'
  places (the engine's naming for such things), every place looked at,
  then the files moved in. The moves themselves are one after another;
  what can fail an archive (damage, a bad name, a full disk, a
  password) has failed before the first of them.
- Names are checked by the component, the same way for zip and tar; a
  tar member is then unpacked by Python's own `data` filter, named
  explicitly since it is the default only from 3.14.
- A zip's declared sizes are held against the free space first. An
  entry cannot write more than it declares: Python stops at the
  declared size and then fails the check sum.
- Passwords: the key is declared a secret (the engine's new flag), and
  the debug log is held to show none. `NotImplementedError`, which
  Python raises for a packing it does not know, is a kind of
  `RuntimeError`, which it raises for a wrong password: caught in that
  order (the first version had them the other way round; a test found
  it).
- A zip entry made by a tool that does not say what kind of thing it
  was (Python's own `writestr`, for one) is a file. The first version
  left such entries out as "special"; a test found it.
- Kept from Talend for a converted job: the name of the folder
  `rootname` makes, UTF-8 for names that do not say their encoding,
  `<id>_CURRENT_FILE` and `<id>_CURRENT_FILEPATH` (of the last file),
  and going on with a warning when `die_on_error` is off.

- Mutation check: 75 ways of breaking it, 63 caught at first. Ten of
  the others each got a test (a tar that holds a zip, a name written
  with `./`, an archive exactly as large as the space, an encoding that
  is given and not to be used, an entry named as the archive names it
  in a failure, and more). One showed a step that could not matter (a
  folder made twice) and it was taken out. One is no change at all: the
  default of `use_encoding`, since the encoding it would use is UTF-8,
  which is what is used without it. One was no valid mutant.

For the loop components: Talend runs what an iterate link from this
component leads to once for every file unpacked. The component has the
list of what it placed, in order; the engine has no iterate yet.
