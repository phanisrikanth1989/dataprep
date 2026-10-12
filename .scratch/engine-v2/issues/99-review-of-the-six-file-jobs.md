# 99 - Review of the six file jobs

Status: resolved
Type: task

## Question

An independent reader went through the six file jobs as they stood at
commit `a3655da2` (file touch, file properties, raw file input, change
file encoding, file archive, file unarchive), with the two pages they are
held to, and tried to break them. It read a clean copy of that commit,
wrote its own probes and ran them on Python 3.12, 3.13 and 3.14. What
did it find, and what was done about it?

## What it found

Fourteen things, the first five in the unarchive. Each was turned into a
test that failed before the code was changed, unless said otherwise.

1. A compressed tar with one bit changed, or cut short, was unpacked in
   part and the job said it had succeeded. Of 40 single bits changed in
   a `tar.gz`, all 40 ended that way.
2. A plain tar cut off between two entries, or inside a header, or with
   a header that is not whole: the same.
3. A tar could plant a link or a pipe in the folder, and change the
   permissions and the time of a file outside it: by a second name (a
   hard link) for a link the component had left out.
4. A file that could not be moved to its place left the files moved
   before it where they were, with the files they had written over gone,
   while the job said nothing was unpacked.
5. A file that starts with zero bytes was taken for an empty tar: no
   file, and success.
6. The raw file input held seven to eleven times the file, not the three
   the page said, and kept the text to the end of the run.
7. The line of a fault was counted in bytes, and so was wrong in UTF-16
   (line 7 where it was line 3).
8. With `die_on_error` off, only a fault the component had worded itself
   let the job go on. What the file system refused in other steps
   failed it.
9. A file name from a context variable that holds nothing gave
   `'NoneType' object has no attribute 'strip'`.
10. The page said the same files give the same bytes on any server. Not
    a zip: it holds local time.
11. A file was written through a link put where it is written first.
12. A secret value could be shown by a refusal for three reasons the
    tests did not reach.
13. The tests skip some cases as root and need pipes.
14. The raw file input looked at its file three times before opening it.

## What was done

**Unarchive (1 to 5).** Python's reader of tar now only finds the
entries. Every file is written by the component, from the bytes of an
entry that is a file. So nothing in an archive can make a link, a pipe
or a device.

- Where the reader stops is looked at: it has to be the end mark, a
  block of zero bytes. Anything else is damage. The archive is then read
  to its last byte, which is where a compressed one says whether its
  check sum fits.
- A second name for a file is a copy of the file. A second name for a
  link or a special file is left out with it.
- A file is made with the permissions its entry has, less what could do
  harm, and through the server's own setting for new files (the umask):
  an archive gives no file more than a new file gets.
- A file that is there is moved aside before the new one takes its
  place. When a move fails, every move before it is taken back. When
  that fails too, the job says so and keeps the files that were there
  where they wait.
- What an archive is: a valid first header says tar. A tar with no entry
  is zero bytes and nothing else; only then does the name decide.
- New, found on the way: what stands after the end mark of a tar is said
  in a warning (it may be archives joined); an archive compressed with
  Zstandard on a Python without it says so; a file without a name in an
  archive is damage.
- The reviewer's own probes were run again on the new code: 40 of 40
  changed bits now fail the job, every cut tar fails it, the file
  outside the folder is not touched, no pipe is planted, and the folder
  is as it was after a move that fails.
- Time on a 480 MB archive (tar, tar.gz, tar.zst): the same as before.
  Memory stays at about 100 MB whatever the archive's size.

**Raw file input (6, 7, 14).**

- The file is written as UTF-8 to a scratch file, a piece at a time, and
  the value is made of that file's bytes. Python never holds the text as
  a text of its own. A test measures it: Python held nine times the file
  before, under one and a half times now.
- The value goes straight into the plan. No table of one row is made of
  it in the component.
- What a source made is let go of when its subjob has finished (in the
  engine, for every source; a loop no longer needs its own rule for it).
- The rest is Polars. A table of one row holds its value a second time,
  beside the table, and copies it with the table. Timed here: every
  step on one value of 128 MB takes as long as copying it; the same
  bytes in a million values take no time. So the job as a whole still
  holds seven to nine times a 256 MB file at its most. The page now says
  that, and why. The component's own share went from five to seven times
  down to about twice.
- Because of that the default of `size_limit_mb` is 256, not 1024. A
  file that grows past the limit while it is read fails the job too.
- A column declared as anything but text refuses the job.
- The line of a fault is counted in the text (in `files.transcode`,
  which the raw input now reads through as well).

**`die_on_error` (8).** One helper, `Component.fail_or_go_on`, takes
what was caught: a fault of the config, of the file system, or of an
encoding. It fails the job in plain words or lets it go on. The six file
jobs and the file list use it. Two steps got words of their own: a
folder that cannot be made, and a file whose name is not UTF-8 in an
archive.

**A key with no value (9).** A key that has to be given and has none is
refused by its name, where config values are checked: also when the
value was to come from a context variable that holds nothing. Two older
refusals (`pattern` of extract positional fields, `join_key` of join)
now say `required config key has no value` for a value of nothing; for
an empty one they say what they said. A file name of nothing but blanks
refuses a file touch, as it did the others.

**Zip and time zones (10).** The page says what is true: a tar gives the
same bytes anywhere, a zip only where the time zone is the same.

**A planted link (11).** It was not only these components: every output
of the engine wrote through such a link. Fixed in one place: before a
file is written at its scratch name, whatever stands there is taken
away, a link as the link it is. When it cannot be taken away the job
fails. Someone who may write in the output folder can still swap the
name between that and the write; they can also swap the output itself.

**Secrets (12).** A refusal of a secret value does not show it whatever
refuses it: its kind, the key's own check, its choices, or a key inside
a secret list or object. A secret inside a list or an object is `***`
in the debug line too.

**Zstandard.** Found on the way: v2's own Zstandard archives had no
check sum, so damage in one could not be told. They have one now, as
the zstd command writes it.

**Left as they are (13, 14).** The cases that need a pipe or a file the
job may not read are still skipped for root; two of them got a twin that
needs neither. The raw input still looks at the file's name before it
opens it; the limit is now also held while the file is read.

## Mutation check

The new code was broken on purpose in 75 ways, one at a time.

- Unarchive, 31 ways: 29 caught at first. The other two each got a test:
  an entry's permissions where a new file gets everything (macOS drops
  the bits that run a file as its owner by itself, so the test passed
  there for the wrong reason), and a compressed file that holds a zip
  byte for byte (Python takes it for a zip; it is the one file).
- The rest, 44 ways: 40 caught at first. Two got a better test (the
  level of a Zstandard archive; a file that really grows while it is
  read). One was a branch that changed nothing, and was taken out. One
  stays: putting the raw input's value in a table of one row again
  changes how much memory the component holds, and nothing a test sees.

The full run after it: 6,636 tests pass, every module at 95% or more.

## Slips

- The code for the unarchive was written before its new tests were run.
  They were then run against the old code (38 failed, for the reasons
  expected) and against the new.
- Six tests were written after their code: a link that cannot be taken
  away (twice), a disk that fills up, a file that may not be read, the
  permissions of a second entry of one name, and a reader that stopped
  elsewhere. The mutation check stands in for seeing them fail.
