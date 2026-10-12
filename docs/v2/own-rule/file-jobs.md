# File jobs

The components that do something with a file as a whole.

Built to their own rule: what is written here is what they are held to,
not v1. ([What that means](README.md).)

## File touch

- The file `filename` is made empty when it is not there; when it is,
  what it holds is kept and the time it was changed is set to now. A
  folder that is there has its time set as well.
- The file is made in one step that makes it only if nothing is there, so
  a file another job made in the meantime keeps what it holds, and
  nothing is made through a link: a link to nowhere fails the job.
- The folder the file is to stand in has to be there, unless `createdir`
  is on (v1's `create_directory` is taken too).
- The path is left in `<id>_FILENAME`, and the log says whether the file
  was made or was there.
- It is a subjob of its own: a flow to it refuses the job. (Talend lets
  rows flow through it, touching the file once for each.)
