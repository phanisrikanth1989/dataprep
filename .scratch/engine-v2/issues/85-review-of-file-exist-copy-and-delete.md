# 85 - Review of file exist, file copy and file delete

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran file exist, file copy and file
delete (tickets 81 to 83, as at commit d2f909dc) against v1 in scratch
folders, and read them against Talend's templates. What did it find, and
what is done about each?

## What it found (2026-10-12)

Twenty-six findings, six of them ways to lose data, and seventeen ways
of breaking the three that no test noticed (38 tried).

1. A folder copied into a folder inside itself, with the source to be
   taken away, deleted everything and said it had worked.
2. A folder's copy followed v1 where Talend differs (the source taken
   away, where the copy lands, `replace_file`, `create_directory`),
   though the README said v2 follows Talend.
3. A folder copied deeper into itself nests copies until a path is too
   long.
4. A delete of a link to a folder, written with a slash at its end,
   deletes what the folder holds.
5. `.` or `dir/..` empties the folder the job runs in.
6. Switches written as text or null are taken, where v1 refuses them.
7-15. Differences nothing said: a file named as the destination, a file
   copied onto itself, the globalMap entries and their values, a blank
   new name, which key a delete reads, when `ERROR_MESSAGE` is set, a
   path written as a globalMap expression.
16-20. Python's own words in failures: a folder copied onto itself, a
   copy that fails half way, refusals that name no path, a move whose
   source cannot be removed, links.
21-26. Claims in the README and the two tickets.

## Answer

Done on 2026-10-12, each fix with a test seen failing first.

Fixed:
- 1, 2, 3: a folder is copied as Talend's source copies it, and never
  into itself or below itself.
- 4, 5: a link is taken away itself, however the path is written; the
  folder the job runs in, or one it lies in, is never deleted. Both go
  beyond v1 and Talend on purpose, and the README says so first.
- 7, 9, 10, 16 to 20: plain words with the path; Talend's entries with
  Talend's values, in every outcome; Talend's `NewName.temp`.
- Tests for the seventeen, and 31 ways of breaking the fixes: 30 caught,
  one found to change nothing (which of file and folder is asked first
  of a path that can only be one).

Said in the README and left: 8, 13, and of 12 what stays v1's.

Claims corrected: 21 to 26, in the README and tickets 82 and 83.

Not done:
- 6 is the loader's: a switch written `"true"` is on for every v2
  component. Here it decides whether something is deleted; it is the
  user's to say whether text should be refused for these.
- 15: a path cannot be read from a globalMap entry in v2 (a Java
  expression is refused; plain text is the file's name).
- 12: `PATH` in capitals is read where v1 reads only `path`; two
  spellings of one key refuse the job.
