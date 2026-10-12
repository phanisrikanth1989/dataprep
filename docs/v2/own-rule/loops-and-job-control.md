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

## Sleep

- The job waits `pause_duration` seconds and then goes on. A part of a
  second may be given (`0.5`); one second when nothing is given, as in
  Talend.
- It stands alone: a trigger or an iterate link leads to it, where it
  waits once for each pass. A flow to it refuses the job. (Talend lets
  rows flow through it and waits once for each row.)
- The value may come from the context. What is no number of zero or
  more refuses the job when it loads, or fails it when its turn comes
  if the value is known only then. (v1 warns and does not wait, which
  lets a mistyped value pass for a pause.)
- The log says how long it waits, before and after. Whoever stops the
  job ends the wait at once.
- It waits a length of time, not for anything. For a file that is still
  being written, a file list's `min_age_seconds` leaves the file out
  until it has been still that long.

## Prejob

- Marks where a job's set-up starts: what its trigger leads to runs
  before everything else in the job, wherever it is written. It does
  nothing itself and has no key of its own.
- When the set-up fails, the job itself is not run, and the log says so.
  What a postjob sets off still runs. (Talend runs the job all the same,
  and so does v1: a job run on a set-up that failed fails later and less
  clearly. Airflow does as v2 does.)
- Nothing leads to it: a trigger or an iterate link to it refuses the
  job, and so does a flow. A job may have more than one; they run in the
  order they are written.
- How the three parts of a job run is in
  [How a job runs](../how-a-job-runs.md#set-up-and-clean-up).

## Postjob

- Marks where a job's clean-up starts: what its trigger leads to runs
  after everything else in the job. It does nothing itself and has no
  key of its own.
- The clean-up runs whatever became of the job: after a failure, and
  after a die. So it does in Talend, and in every other tool that was
  read. v1 runs it only after a job that succeeded, by choice; a
  clean-up that runs only then is not one. A step meant for success
  only stands behind the job's own subjob, on its OnSubjobOk trigger.
- A clean-up that fails fails the job, and does not hide why the job
  had failed before it.
- Nothing leads to it, as for a prejob.

## Run job

- Runs the job `process` names as one step of this job, and goes on
  when it has ended. `process` is the job's name, without `.json` and
  without a version.
- The child's job config is looked for beside the parent's:
  `<process>.json`, else the `<process>_<version>.json` of the highest
  version (`child_0.10.json` before `child_0.2.json`), which is how a
  converted job config is named. A parent that was not read from a file
  says where in `engine_config.jobs_dir`.
- The child is found, loaded and checked when the parent is. What is
  wrong with it refuses the parent, and the report says it under the
  step that runs it. A job that would run itself, at whatever remove,
  is refused. (v1 looks for the child when its turn comes, and stops at
  a depth of two.) So the name cannot come from the context, and
  `use_dynamic_job` and `use_dynamic_context` refuse the job.
- The child is given context values and nothing else.
  - Each entry of `context_params` sets the child's context variable
    `param_name` to `param_value`. The child has to declare the
    variable: a name it does not have refuses the parent when it loads,
    with the names it has. The value may be an item of globalMap, as in
    a loop (`((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`).
  - `transmit_whole_context` gives the child every variable of the
    parent that the child declares as well. A value given by name wins.
  - A value arrives with the type the child declares for it. One that
    is none of that type fails the job at the step.
  - `context_name` is the context group the child reads. `Default`,
    which a converted job has when the job named none, stands for the
    child's own group when it has none of that name.
- The child runs in the parent's process, as a run of its own: its
  context, its globalMap and its scratch files are its own, and nothing
  of them reaches the parent. It is run whole and as its parent is: on
  the same Polars engine, with its rows counted when the parent's are;
  what its own `run` block says is not looked at.
- What comes back is how it ended: `<id>_CHILD_RETURN_CODE` is 0, or
  the exit code of the die that ended the child, or 1; when it failed,
  `<id>_CHILD_EXCEPTION_STACKTRACE` is why, in one line (v2 shows no
  stack). The summary of the child's last run is in the parent's
  summary under `children`, with how many times the step ran it.
- A child that fails fails the parent at this step, with the child's
  reason. With `die_on_child_error` off the parent goes on, with a
  warning, and why is in `<id>_ERROR_MESSAGE` too. (v1 ends the whole
  parent whatever the switch says.)
- `propagate_child_result` refuses the job: v2 hands no rows from one
  job to another in memory. The child writes a file and the parent
  reads it.
- A flow to it refuses the job: to run a child for each row, put a flow
  to iterate before it. The keys that tune a JVM
  (`use_independent_process`, `jvm_arguments` and the like) are taken
  and have no effect, and so is `print_parameter`: the values given are
  shown in no log.
