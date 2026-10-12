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

## File properties

- One row that says what the file `filename` is. The columns the job
  declares say which properties are wanted, in any order; a column that
  is none of them refuses the job.

  | Column | What it holds |
  |---|---|
  | `abs_path` | the path in full |
  | `dirname` | the folder it is in, in full |
  | `basename` | its name |
  | `mode_string` | its permissions as `ls -l` shows them: `-rw-r--r--`, `drwxr-x---` |
  | `size` | bytes |
  | `mtime` | when it was last changed, in milliseconds since 1970 |
  | `mtime_string` | the same in local time: `2026-10-12 14:03:05` |
  | `md5`, `sha256` | check sums of what it holds, in hexadecimal |
  | `type` | `file` or `folder` |
  | `exists` | whether it is there |

- A job that declares no columns, as a converted job does, gets the seven
  Talend's component has (the first seven of the table), and `md5` as an
  eighth when `md5` is on. What follows the component is checked at load
  with those columns.
- A file that is not there fails the job. When `exists` is among the
  columns it does not: the row says false there and holds nothing but
  the names. (Azure Data Factory's Get Metadata does the same.)
- A link has the properties of what it leads to. A folder has no check
  sum.
- A check sum is worked out only when its column is asked for, in one
  reading of the file, piece by piece, and once in a run. `md5` is asked
  for as a check sum and not for security, so that a server that allows
  only approved algorithms still works it out.
- A failure later in the flow names the row as `the properties of
  <filename>`.
- Not as in Talend: `mode_string` there is two characters, whether the
  job may read and write the file; `mtime_string` is Java's own way of
  writing a date (`Mon Oct 12 14:03:05 IST 2026`); `dirname` is the
  folder as the job wrote it; and a file that is not there is a row of
  nothing. v1 has `mtime` in seconds and `mode_string` in octal, and its
  engine reads the keys in capitals (`FILENAME`, `MD5`), which are taken
  too.

## Raw file input

- One row whose one column holds the whole text of the file `filename`.
  The column has the name the job declares, and `content`, Talend's name
  for it, when the job declares none. More than one column refuses the
  job.
- The text is as the file has it: every line end is kept as it is. A
  byte order mark at the start of the file is no part of the text.
- It is read in `encoding` (ISO-8859-15 when none is given, as Talend's
  default is). A byte that is no character there fails the job and says
  where: `'in.xml' is not written in UTF-8: byte 12 of it, on line 3, is
  no character there`. (Talend puts a replacement character there and
  goes on.)
- The whole file is held in memory as one value, and about three times
  over while it is read. That is what the component is for, so it reads
  no file larger than `size_limit_mb` megabytes (1024 when not given):
  a larger one fails the job before a byte is read. A file to be gone
  through row by row belongs to a reader.
- A file that cannot be read fails the job. When the job config says
  `die_on_error` is off, the job goes on with no row and a warning, and
  why is in `<id>_ERROR_MESSAGE`. (Talend hands on a row of nothing
  then.)
- The path of a file that was read is left in `<id>_FILENAME_PATH`. The
  file is read once in a run. A failure later in the flow names the row
  as `the content of <filename>`.
- Only text: `as_bytearray` and `as_inputstream` refuse the job, since
  v2 has no column type that holds bytes or an open file. A column the
  job declares as `object`, as a converted job does, is held as text.

## Change file encoding

- The text of the file `infile_name` is written to `outfile_name` in
  `encoding` (ISO-8859-15 when none is given).
- The input is read in `inencoding` when `use_inencoding` is on, and as
  UTF-8 when it is off. (Talend then reads it in whatever encoding the
  machine it runs on has, which is not the same on two servers.)
- The text is written as it is: line ends are not touched. A byte order
  mark at the start of the input is not carried over, and the output
  starts with one where its encoding writes one (UTF-16, UTF-32).
- Nothing is put in a character's place. A byte that is no character in
  the input's encoding, and a character the output's encoding cannot
  write, fail the job and say on which line:

  ```
  'in.csv' is not written in UTF-8: byte 12 of it, on line 3, is no character there
  'in.csv' holds '\u20ac' on line 2, which ISO-8859-1 cannot write
  ```

  (Talend writes a replacement character or a question mark there and
  goes on.)
- The file is gone through piece by piece and never held in memory. It
  is written beside `outfile_name` and put there when it is whole: the
  two may be the same file, and a job that fails leaves the output as it
  was.
- The folder of the output is made when it is not there, unless `create`
  is off. An output that is there is written over and keeps its
  permissions.
- The output's path is left in `<id>_FILENAME`, and the log says what
  was written as what, and how many bytes.
- `buffersize` is taken and has no effect: v2 reads in pieces of its own
  size.
