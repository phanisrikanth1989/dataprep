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
  | `type` | `file`, `folder`, or `other` for a pipe or a device |
  | `exists` | whether it is there |

- A job that declares no columns, as a converted job does, gets the seven
  Talend's component has (the first seven of the table), and `md5` as an
  eighth when `md5` is on. What follows the component is checked at load
  with those columns.
- A file that is not there fails the job. When `exists` is among the
  columns it does not: the row says false there and holds nothing but
  the names. (Azure Data Factory's Get Metadata does the same.)
- A link has the properties of what it leads to. Only a file has a
  check sum: a folder holds no bytes, and a pipe or a device is never
  opened.
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
  job, and so does a column declared as anything but text.
- The text is as the file has it: every line end is kept as it is. A
  byte order mark at the start of the file is no part of the text.
- It is read in `encoding` (ISO-8859-15 when none is given, as Talend's
  default is). A byte that is no character there fails the job and says
  where: `'in.xml' is not written in UTF-8: byte 12 of it, on line 3, is
  no character there`. (Talend puts a replacement character there and
  goes on.)
- A pipe or a device fails the job and is never opened: it is no file
  to read from start to end.
- The whole file is held in memory as one value: that is what the
  component is for. A file to be gone through row by row belongs to a
  reader.
  - While the file is read it is in memory about twice: as the bytes
    read and as the value. Python never holds it as a text of its own,
    which can be four times the size of the file.
  - Every step the value then passes through holds it once more for as
    long as the step runs. That is Polars: the one value of a table of
    one row is kept beside the table and copied with it. A job that read
    a file of 256 MB and wrote it out again held seven to nine times
    the file's size at its most. (Measured on a Mac, where a figure of
    this kind is rough; not yet on the servers.)
  - So it reads no file larger than `size_limit_mb` megabytes (256 when
    not given). A larger one fails the job before a byte is read, and a
    file that grows past the limit while it is read fails it too.
  - The value is let go of when its subjob has finished.
- A file that cannot be read fails the job. When the job config says
  `die_on_error` is off, the job goes on with no row and a warning, and
  why is in `<id>_ERROR_MESSAGE`. (Talend hands on a row of nothing
  then.)
- The path of a file that was read is left in `<id>_FILENAME_PATH`. The
  file is read once in its subjob. A failure later in the flow names the
  row as `the content of <filename>`.
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
  goes on.) The line is a line of the text, whatever the encoding: in
  UTF-16 the byte of a line end is also half of other characters, and is
  not counted for one.
- An input that is a pipe or a device fails the job and is never opened.
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

## File archive

- The files of the folder `source` are packed into the archive `target`.
  An entry is a file by its path below the folder (`sub/c.csv`), and the
  entries come in the order of their names. Only files are entries: a
  folder is in the archive through the files in it, and an empty folder
  is not in it. This is how Talend lays an archive out. `source` may
  also be one file, which is then the one entry, under its name.
- Which files: `sub_directroy` off leaves out the files of subfolders
  (the spelling is Talend's; `include_subdirectories` is taken too).
  With `all_files` off only the files whose name fits one of the
  patterns in `mask` are taken. A pattern is held against the name of a
  file, not its path, with capitals and small letters told apart: `*`
  is any run of characters, `?` any one, `[abc]` one of a set. (Talend
  reads a mask as a regular expression in which `*` and `.` mean what
  they mean here; `*.csv` is the same in both.)
- The kind of archive, `archive_format`:

  | Kind | What it is |
  |---|---|
  | `zip` | a zip archive (also when none is given) |
  | `tgz` | a tar archive compressed with gzip (`tar.gz`, Talend's `TAR_GZIP`) |
  | `tar` | a tar archive, not compressed |
  | `tar.zst` | a tar archive compressed with Zstandard |
  | `gzip` | one file, `source_file`, compressed with gzip; no names |
  | `zst` | one file, `source_file`, compressed with Zstandard; no names |

  Zstandard packs to about the size gzip does and about three times as
  fast (tried on 76 MB of delimited text at level 4: gzip 102 MB a
  second, Zstandard 350, both to a third of the size; unpacking is as
  fast for both). Python has it from 3.14: on an older one a job that
  asks for it is refused when it loads. It is written with a check sum
  of what it holds, as the zstd command writes one, so that damage is
  found when it is unpacked.
- `level` is how hard the archive is compressed: 0, not at all, to 9
  (1 to 22 for Zstandard); 4 when none is given, as in Talend.
- Each file is read piece by piece and never held in memory. The archive
  is written beside `target` and put there when it is whole: a job that
  fails leaves the archive that was there, and nothing beside it.
- The same files give the same bytes whenever they are archived: the
  entries are in a fixed order, a tar entry says nothing of who owns the
  file and has its time in whole seconds, and the gzip header of a `tgz`
  has no time in it. For `tar`, `tgz` and `tar.zst` that holds on
  whichever server. A `zip` holds the time of each entry as a clock on
  the wall showed it where it was packed, without saying where that was:
  its bytes are the same on two servers only when both keep the same
  time zone. (A `gzip` of one file has the file's own name and time in
  its header, as the gzip command writes them.)
- A file whose name is not written in UTF-8 fails the job: an archive
  names its entries in UTF-8, and such a name is no text.
- A link, or anything else that is no file, among the files is left out
  and named in a warning: nothing is read through a link, and an
  archive holds files. A folder that cannot be looked into fails the
  job; it is not passed over.
- The archive never holds itself, also when `target` is in `source`.
- A `source` that is neither a file nor a folder (a pipe, a device)
  fails the job and is never opened.
- When no file is taken, no archive is written, one that was there is
  taken away, and a warning says so. `<id>_NB_FILE` is then 0.
- The folder of the archive has to be there unless `mkdir` is on. An
  archive that is there is written over, unless `overwrite` is off:
  then the job fails.
- It leaves `<id>_ARCHIVE_FILEPATH` and `<id>_ARCHIVE_FILENAME`, as in
  Talend, and `<id>_NB_FILE`, the number of files in the archive.
- Not done: encryption. `encrypt_files` on refuses the job, since Python
  cannot write an encrypted zip. Names in a zip are written in UTF-8
  and marked so, whatever `encoding` says; `zip64_mode` and
  `use_sync_flush` are taken and have no effect (a zip is written with
  ZIP64 where it needs it).
- Not as in v1: v1 writes zip only, and reads `include_subdirectories`
  and `compression_level` where the converter writes `sub_directroy`
  and `level`.

## File unarchive

- The archive `zipfile` is unpacked into the folder `directory`, which
  is made, with the folders above it, when it is not there.
- The archive is a zip, a tar (plain, or compressed with gzip, bzip2, xz
  or, where Python has it, Zstandard), or one file compressed by itself
  in one of those ways. Which it is is told from what it holds, not from
  its name: a zip named `in.dat` is unpacked as a zip. (Talend goes by
  the name, and takes whatever is not named `.tar`, `.tar.gz`, `.tgz` or
  `.gz` for a zip.) One case only is decided by the name: a tar with no
  entry is zero bytes to its end, and so is a file of zero bytes. It is
  taken for an empty archive when its name says tar (`.tar`, `.tar.gz`,
  `.tgz` and the like) and unpacks to nothing; under any other name it
  is no archive, or the one compressed file it is. An archive compressed
  with Zstandard on a Python that does not read it fails the job and
  says so.
- The files land by the paths the archive gives them, with the times it
  gives them, and a folder the archive names is made also when it holds
  nothing. A file that is there is written over. With `extractpath` off
  every file lands in the folder itself, without the folders of its
  path; two files that would then have one name fail the job.
- `rootname` unpacks into a folder of the archive's name inside
  `directory`: `data` for `data.zip` and for `data.tar.gz`.
- One file compressed by itself loses the ending of its name (`a.csv`
  from `a.csv.gz`) and has the time of the archive, as gunzip has it. A
  name without that ending fails the job: there is no name to unpack it
  under.
- All of it or none. The archive is unpacked into a folder of its own
  inside `directory`, and the files are moved to their places when
  every one of them is whole. An archive that is cut short, or damaged,
  or locked, fails the job and leaves `directory` as it was; a folder
  that was made for it is taken away again. (Python, like most tools,
  leaves half an archive behind.) A zip says how large its entries are:
  one that would not fit where `directory` is fails before a byte is
  written.
  - What counts as damaged in a tar: one that ends anywhere but at its
    end mark (Python's own reader takes a tar that is cut off between
    two entries, or whose next header is not whole, for a shorter
    archive and says nothing), and a compressed one whose check sum does
    not fit, which is looked at by reading it to its last byte. A tar
    that is not compressed holds no check of the bytes of its files:
    a byte changed inside a file cannot be told. Nor can it in one
    packed with Zstandard without a check sum (the zstd command and
    v2's own archive write one).
  - What stands after the end mark of a tar is not unpacked, as with
    the tar command, and a warning says so: it may be more than one
    archive joined.
  - A file that is there is moved aside before the new one takes its
    place. When a file cannot be moved to its place, every move before
    it is taken back, and the files that were there are there again.
    Should that not work either, the job says so, and says where the
    files that were there are kept.
- What an archive may not do:
  - A name that climbs out of the folder (`../x`) fails the job.
    Python's own zip reader puts such a file in the folder under another
    name and says nothing.
  - A name that starts at the root (`/etc/x`) lands in the folder, as
    tar and unzip have it. A zip made on Windows may name its entries
    with backslashes; they are taken as the separators they are.
  - A link, a pipe or a device in the archive is left out and named in
    a warning. A second name for a file of a tar archive (a hard link)
    is unpacked as a file of its own, a copy, so that what is later
    written to the one is not written to the other. A second name for
    a link or a special file is left out with it.
  - No file is made by Python's own unpacking of a tar: it only reads
    the entries, and the component writes the bytes of each file. So
    nothing an archive holds can make a link, a pipe or a device, or
    reach a file outside `directory`.
  - Nothing is written through a link that is already in `directory`
    and leads out of it: that fails the job before anything is moved.
  - A tar entry's owner is not carried over, nor a permission that
    would let a file run as its owner or be written by others. Of the
    permissions that are left, a file gets no more than a new file gets
    on the server (its umask), as with the tar command.
- A zip locked with a password is opened with `password` when
  `checkpassword` is on. The password is shown in no log. Python opens
  the old zip locking only, and slowly; an entry locked with AES fails
  the job and says so. Talend's `JAVA_DECRYPT`, a cipher of its own
  around the whole file, refuses the job when it loads.
- The names in a zip that does not say how they are written are read as
  UTF-8, as in Talend, and in `encording` when `use_encoding` is on
  (the spelling is Talend's). Names that are not UTF-8 fail the job and
  say which keys to give.
- It leaves `<id>_NB_FILE`, the number of files unpacked, and the name
  and the full path of the last of them in `<id>_CURRENT_FILE` and
  `<id>_CURRENT_FILEPATH`. `printout` says every file in the log.
- `die_on_error` is off in a converted job unless the box was ticked in
  Talend: such a job goes on after an archive that cannot be unpacked,
  with a warning, as it does in Talend. `integrity` is taken and has no
  effect: nothing lands unless the whole archive unpacks.
- It may be the start of a loop, as in Talend: what its iterate link
  leads to runs once for each file it unpacked, in the order of the
  archive, with that file's name in `<id>_CURRENT_FILE` and its full
  path in `<id>_CURRENT_FILEPATH`
  ([how a loop runs](../how-a-job-runs.md#loops)). The loop starts when
  the whole archive is unpacked, not file by file as in Talend: a pass
  never sees half an archive. `max_items` is the most files such a loop
  may have (100,000 when not given); more fail the job before the first
  pass, with the archive unpacked.
