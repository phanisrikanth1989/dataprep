# File jobs

The components that do something with a file as a whole.

Where v2 differs from v1, each on purpose. v1 is the answer key for
everything else these components do. ([The other pages](README.md).)

## File copy

Where v1 and Talend differ, v2 does what Talend's source does, but for
the two safeguards said last; where they agree, v1 is the answer key
(what is in the folder afterwards).

A file:

- A copy that fails lets the job go on, with why in `<id>_ERROR_MESSAGE`
  and a warning in the log, unless `failon` is on. v1 fails the job
  unless `die_on_error` is written and off, which the converter never
  writes.
- A file that is there and is not to be replaced (`replace_file` off) is
  left, and that is no fault; v1 fails. The source is then not taken
  away either, having no copy.
- The time the file was changed is kept only with
  `preserve_last_modified_time`; v1 always keeps it.
- `<id>_DESTINATION_FILEPATH`, `<id>_DESTINATION_FILENAME`,
  `<id>_SOURCE_DIRECTORY` and `<id>_DESTINATION_DIRECTORY` are left in
  globalMap, whatever becomes of the copy, as in Talend; v1 leaves
  nothing.
- A new name of nothing but blanks is `NewName.temp`, as in Talend.
- The source has to be a file, and the destination a folder: a file
  named as the destination fails the copy, where v1 writes over that
  file.
- A file copied onto itself is left as it is. v1 fails; Talend compares
  the two paths as they are written.

A folder (`enable_copy_directory`):

- It is copied into the destination under its own name (`src` into `out`
  is `out/src`), as in Talend. v1 puts what it holds straight into the
  destination. A job written for v1 has to name the folder above.
- What is there is written over and what is missing is made, whatever
  `replace_file` and `create_directory` say, as in Talend.
- The source folder is never taken away, whatever `remove_file` says, as
  in Talend. v1 deletes it.
- A folder is not copied into itself or into a folder inside it. v1 (and
  Talend's template, as far as it was read) copies it into itself over
  and over, and v1 with `remove_file` on then deletes all of it.
- When some files cannot be copied, the others are, and the message says
  how many could not and names the first.

Nothing named to copy, or nowhere to copy to, refuses the job before it
runs.

## File delete

Where v1 and Talend differ, v2 does what Talend's source does, but for
the two safeguards said first.

- A link is taken away itself and what it leads to is never touched,
  however the path is written. v1 deletes everything in the folder a
  link leads to when the path ends in a slash, and Talend's template
  empties it either way.
- The folder the job runs in, and any folder it lies in (`.`, `..`,
  `dir/..`), is never deleted: the delete fails. v1 and Talend empty it,
  and then say that nothing was deleted.
- Nothing there to delete fails the job, unless `failon` is off (it is on
  when the job does not say). v1 warns and goes on whatever `failon`
  says. A job that deletes a file "in case it is there" has to switch
  `failon` off, as in Talend.
- `<id>_CURRENT_STATUS` holds Talend's words (`File deleted.`, `Path
  deleted.`, `No file deleted.`, `No path deleted.`, `File does not exist
  or is invalid.`, `Path does not exist or is invalid.`, `File or path
  does not exist or is invalid.`). v1 has `deleted`, `not exist`,
  `error`.
- With `failon` off, why nothing was deleted is in `<id>_ERROR_MESSAGE`
  (always, and with the path as it is written; Talend sets it only when
  its own logging is on) and in a warning in the log. A folder that
  could be deleted only in part says so.
- Kept from v1: `recursive` (off, only an empty folder goes; Talend
  always takes a folder with what it holds), and `path` standing in for
  a `filename` or `directory` that is not given.
- Nothing named to delete refuses the job before it runs.

## File exist

- As v1: `<id>_EXISTS` and `<id>_FILENAME`, a folder counting as there,
  only a folder under `check_directory`. (Talend has no
  `check_directory`.)
- An empty path refuses the job before it runs.

## File row count

- As v1: the count in `<id>_COUNT`, every kind of line end ending a row
  when the separator is one, any other separator splitting the whole
  text, rows of blanks left out when asked.
- A file that is not there, or not written in its encoding, fails the job
  in plain words. A separator of nothing refuses it before it runs.
- With a separator that is no line end the file is held in memory while
  it is split, as in v1.
