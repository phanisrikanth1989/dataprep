# 114 - Review of loops and job control

Status: resolved
Type: task

## Question

What does someone who did not build them find in the seven loop and
job-control components, in the item in a config string
([An item in a config string](101-an-item-in-a-config-string.md)) and
in the fixes of the six file jobs
([Review of the six file jobs](99-review-of-the-six-file-jobs.md))?

## How it was done

One reviewer, read-only, on a copy of the tree at `d620c631`. It wrote
forty probes that run the engine and say what they found. Each finding
was run again here on the tree as it is now before anything was
changed, and each fix has a test that was seen failing first.

## Findings, worst first

All eight were real.

1. **What was looked up was read as text of the job config.** Since
   ticket 101 the engine looks a value up (`globalMap.get("KEY")`)
   before the component sees it. Two components read the text of a
   value their own way, and read what was looked up that way too:
   - The fixed flow input reads text that is a plain number as that
     number. An account `00123` of a row, written down in a loop's
     body, became `123`.
   - The row generator works its text out as Python. A file named
     `1+1` was written as `2`. The reviewer rated this a wrong result.
     It was worse: `random` is the one name an expression has, and
     `random._os` is Python's `os`. A file named
     `random._os.system('...')` had its command run. Tried here with a
     command that makes an empty file in the test's own folder: it was
     made.

   This was ticket 101's doing, and mine. Nothing of it was pushed.

   Fixed: what is looked up is handed to such a key as `Looked`, and
   the component takes its value as it is. A key says
   `takes_looked=True`; every other key is handed the value itself, as
   before. The fixed flow input's three value keys and the row
   generator's expression say so.

   What v1 does, run here with its Java bridge: the fixed flow input
   keeps `00123` for a value that is not marked and writes `123` for
   one that is; the row generator keeps `1+1` under the mark. v2 now
   keeps both, marked or not.

2. **The archive of an earlier run was deleted for nothing.** A mask
   in the list a converted job has (`["${context.m}"]`) was never
   looked up: the loader reads a name in a text and in the items of a
   list key, and `mask` is declared as either. The mask fitted no
   file, and "no file taken" takes the old archive away. Fixed: the
   archive looks its masks up when it runs.
3. **Two second scratch names were written through a planted link.**
   A file in another encoding is written through `<scratch>.enc`, and
   a compressed positional output through `<scratch>.zip`. Ticket 99
   cleared the first name and missed these. The first is the default
   case: any output with a character beyond ASCII. Fixed: both are
   cleared before they are written.
4. **An archive named `...tar.gz` was unpacked one folder too high.**
   With `rootname`, its name less `.tar.gz` is `..`. Fixed: such a name
   is named as any other archive, up to its last dot (`...tar`).
5. **One file name could hold a file list for minutes.** Each `*` of a
   mask was `.*`, and Python tried every way of sharing a name out
   among them: 4.8 s for a name of 120 characters against five stars
   here, 93 s against seven for the reviewer. Fixed: what stands
   between two stars is looked for where it comes first and that place
   is kept, which is right for a pattern of this form. Twenty stars
   now take no time. `*` and `?` now fit a line end in a name too.
6. **A value given to a child job was in the log.** The docs said "in
   no log"; the config line at DEBUG had it. A password goes to a
   child this way. Fixed: the key is a secret, and a value that does
   not fit its type is no longer quoted in the message.
7. **Three faults went raw**, and ignored `die_on_error` off: a tar
   entry whose time is no number, a zip that needs a later zip than
   Python reads, and `hex`, `zlib` and their like given as an
   encoding. Fixed: the first is unpacked with the time it was
   unpacked at; the second fails as an archive Python cannot read; the
   third refuses the job when it loads, wherever a component takes an
   encoding. And whatever else Python raises while it reads an archive
   is now a fault of the archive, with what was raised in the message.
8. **A loop whose items could not be read on ended the run raw**, and
   the clean-up never ran. Fixed twice over: such items fail the
   component that starts the loop, as a pass that failed does; and the
   clean-up now also runs after a fault no component answers for,
   which then ends the run as it would have.

## What else was looked at and found sound

Loops and their bodies, nested loops, the cap on items; flow to iterate
on six million rows (memory flat at about 200 MB); run job (the child
found, checked, typed, kept apart, cycles refused through links and
versions); the three parts of a job; forty rounds of cut and changed
archives of every kind; references in every written form; sleep;
secrets of the unarchive; eight runs at once in threads; the orders of
the file list. Two things that cannot be found are in the docs already:
a byte changed inside a file of a plain tar, and one bit changed in a
zip's list of entries.

## For the user's eye

- Finding 1 let a file's name run a command. It was on this machine
  only: ticket 101 was never pushed.
- `number + number` under the mark is joined as text (`40 + 2` is
  `402`), as the docs say of joined terms. Talend adds them. Left as
  it is: said here so that it is not found by a job.
- A regular expression a job writes itself as a mask (`glob_expressions`
  off) can still be made slow by a name. It is the job's to keep.
- Not tried on the servers, nor on a Python before 3.14.

## Mutation check

Thirty-three ways of breaking the eight fixes. All were caught.

## How it was built

Each fix: the reviewer's probe run again here, a test written and seen
failing, the fix, the probe run once more. Two tests of run job's
message were changed with the message (the value is no longer quoted).
One test of the unarchive was first written to the wrong answer (the
whole name as the folder) and changed to Talend's rule before the fix
was kept.

The component guide outgrew the six hundred lines a page may have when
the key for looked-up values was written into it. Its part on row
numbers is a page of its own now (`docs/v2/row-numbers.md`).
