# Components built to their own rule

These are built for long use and not to v1 or Talend: v1 is not their
answer key, and their tests hold them to what is written here. A converted
job config still loads as it is: the keys the converter writes are the
keys read, and where v1's engine reads another name, that name is taken
too.

What they share:

- What cannot be done fails the job and says why, in plain words: also
  what the file system refuses (no room, no permission), whatever the
  step it happens in. Where the job config itself carries `die_on_error`
  and it is off, the job goes on with a warning, and why is in
  `<id>_ERROR_MESSAGE`.
- A key that has to be given and has no value refuses the job by its
  name: also when the value was to come from a context variable that
  holds nothing.
- A file is written beside its place and put there when it is whole.
  Nothing is written through a link that someone put where the file is
  written first: the link is taken away, and when it cannot be, the job
  fails.
- Each counts one row (`<id>_NB_LINE`, `_OK`, `_REJECT`) unless it says
  otherwise.

| Page | What is on it |
|---|---|
| [File jobs](file-jobs.md) | File touch, File properties, Raw file input, Change file encoding, File archive, File unarchive |
| [Loops and job control](loops-and-job-control.md) | File list, Flow to iterate, Foreach, Sleep, Prejob, Postjob, Run job |
| [XML](xml.md) | XML file input, XML file output, Advanced XML output, Extract XML field, Multi-schema XML input, XML map |
| [Databases](databases.md) | Oracle connection, Oracle commit, Oracle rollback, Oracle close, Oracle input, Oracle output, Oracle row, Oracle stored procedure |
