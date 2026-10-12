# Loops and job control

The components that start a loop, and the ones that steer a job as a
whole.

Built to their own rule: what is written here is what they are held to,
not v1. ([What that means](README.md).) How a loop runs, whatever starts
it, is in [How a job runs](../how-a-job-runs.md#loops): one pass after
another, a pass that fails stops the loop, a cap on the items.

One more component starts a loop and is on another page:
[File unarchive](file-jobs.md#file-unarchive), over the files it
unpacked.

## File list

- Starts a loop over the files of the folder `directory`: what its
  iterate link leads to runs once for each. The list is made once,
  before the first pass; a file that is gone by its pass fails that
  pass.
- In a pass the file is in globalMap under Talend's names:

  | Entry | What it holds |
  |---|---|
  | `<id>_CURRENT_FILE` | its name |
  | `<id>_CURRENT_FILEPATH` | its path in full |
  | `<id>_CURRENT_FILEDIRECTORY` | the folder it is in, in full |
  | `<id>_CURRENT_FILEEXTENSION` | what follows the last dot of its name; nothing for a folder |
  | `<id>_NB_FILE` | the number of files so far; when the loop is over, how many there were |

- Which names: every name, or those that fit one of the masks in
  `files`. A mask has to fit the whole name, never the path. It is a
  pattern in Talend's own form: `*` any run of characters, `?` any one,
  `[abc]` one of a set, which `!` or `^` at its start turns round, and a
  backslash takes the character after it as itself. With
  `glob_expressions` off a mask is a regular expression, Python's: one
  that Python cannot read refuses the job when it loads (Talend's are
  Java's, which differ in a few rare forms).
- `case_sensitive` `NO` takes capitals and small letters for the same.
  `exclude_file` leaves out the names that fit one of the masks in
  `exclude_filemask`, a list with commas between, as in Talend (v1 takes
  the whole text as one mask).
- `list_mode` says what is listed: `FILES`, `DIRECTORIES` or `BOTH`.
  `include_subdirs` goes into the folders inside the folder, at every
  depth.
- The order is by path when no other is asked for, which is what
  Talend's "by default" comes to, and the only order that is the same
  twice (v1 has the order the file system gives). `order_by_filename`,
  `order_by_filesize` and `order_by_modifieddate` sort by name (folders
  first), by size and by the time of the last change, with the name and
  then the path where two are the same; `order_action_desc` turns that
  round, and leaves the order by path as it is. v1's `order_by` and
  `order_action` are taken too.
- Left out, always:
  - a name that starts with a dot, unless a mask that itself starts with
    a dot fits it. Files that are still being written often carry such
    names, and so do a file system's own (`.snapshot`). A shell does the
    same; Talend lists them.
  - a file v2 itself is still writing beside its place;
  - a link that leads out of the folder, and what is neither a file nor
    a folder (a pipe, a link to nothing). These are named in a warning.
    A link to a file in the folder is listed.
- A folder that starts with a dot, or that is reached through a link, is
  not gone into: a walk through links can leave the folder or go round
  for ever.
- A folder that is not there fails the job, and so does one that cannot
  be looked into; it is not taken for an empty one. (Talend runs no pass
  and says nothing.) With `die_on_error` off in the job config the job
  goes on with no pass and a warning.
- No file, no pass. With `error` on that fails the job, in Talend's
  words: `No file found in directory <directory>`.
- `min_age_seconds`, v2's own: a file changed less than that long ago is
  left out for a later run and counted in the log. It is for a folder
  that files are still arriving in. It waits for nothing; only whoever
  writes a file can say that it is finished, by writing it under
  another name and renaming it.
- `max_items` is the most files the loop may have (100,000 when not
  given): a wrong folder with `include_subdirs` on is stopped before
  the first pass.
- A file's size and time are asked of the file system only when the
  order or `min_age_seconds` needs them, which a folder of very many
  files feels.

## Flow to iterate

- Starts a loop over the rows that reach it: what its iterate link
  leads to runs once for each row, in the order the rows arrive.
- In a pass the row is in globalMap, each value with the type it has (a
  whole number is a number, a date a date) and a missing one as nothing.
  With `default_map` on, as in a converted job, every column is there as
  `<flow>.<column>`, `<flow>` being the name of the flow that leads to
  the component: `row1.filepath`. With it off, `map_entries` says which
  columns, and under which names (`key` the name, `value` the column).
- `<id>_CURRENT_ITERATION` is the number of the pass, and `<id>_NB_LINE`
  how many rows there were.
- The rows are not held in memory, however many there are. They go to a
  scratch file in the one pass of the subjob they come from. When that
  subjob has finished, with its own files in place, the passes are fed
  from the scratch file a piece at a time, and the file is removed when
  the loop is over, however it ended. (Talend runs the body while the
  rows are still being read; v1 takes every row into memory first.)
- `max_items` is the most rows the loop may have (100,000 when not
  given). A loop over every row of a large table is nearly always a
  join written as a loop, and a join is what the engine is fast at.
- A column `map_entries` names that the flow does not have refuses the
  job when it loads, where the columns are declared, and fails it when
  it runs otherwise.

## Foreach

- Starts a loop over `values`: what its iterate link leads to runs once
  for each value, in the order written.
- In a pass the value is in globalMap as `<id>_CURRENT_VALUE`, and the
  number of the pass as `<id>_CURRENT_ITERATION`. The value is text, as
  in Talend: `007` stays `007`, and a value written as a number is the
  text of it.
- A value may name a context variable (`${context.x}`). It is put in
  when the component runs, before the first pass.
- No value, no pass. `<id>_NB_LINE` is how many values there are (v1's
  entry; Talend has none).
- `max_items` is the most values the loop may have (100,000 when not
  given).
