# 93 - File jobs: what current practice says

Status: resolved
Type: research

## Question

Before file properties, raw file input, change file encoding, file
archive and file unarchive are built: what do Talend's own definitions
fix for a converted job, how do current tools do the same jobs, and what
does Python's own documentation say is safe? Looked up by the agent on
2026-10-12 (the user asked for research first, ticket 87).

## What was read

Talend, for the names a converted job leans on (Talaxie
`tdi-studio-se@639d5fd1f776`, `components/<name>/`; and the helper
library the archive components call, which Talaxie does not carry:
`toscollection/tdi-studio-se-core@d9f1c04b`,
`.../libs_src/talendzip/src/main/java/com/talend/compress/zip/`):

- **tFileProperties**: a fixed schema, `abs_path`, `dirname`, `basename`,
  `mode_string`, `size`, `mtime`, `mtime_string`, and `md5` when MD5 is
  ticked. `mode_string` is two characters, whether the job may read and
  write the file; `mtime` is milliseconds; `mtime_string` is Java's
  `Date.toString()`. A file that is not there gives a row of nothing.
- **tFileInputRaw**: a fixed schema of one column, `content`; the file as
  text (`AS_STRING`, in `ENCODING`), as bytes or as a stream. It leaves
  `<id>_FILENAME_PATH`. With `DIE_ON_ERROR` off a file that cannot be
  read gives a row of nothing.
- **tChangeFileEncoding**: characters are read and written in pieces;
  with `USE_INENCODING` off the input is read in the machine's own
  encoding; in and out the same file goes through `<name>_tmp`. A byte
  that is no character and a character the target cannot hold are
  replaced without a word (Java's readers and writers do that). Its
  declared returns (`EXISTS`, `FILENAME`) are never set; `<id>_ISEND` is.
- **tFileArchive** (`Zip.java`): `zip`, `gzip` (one file, `SOURCE_FILE`)
  and `tgz`. Entries are the files of the source folder by their path
  below it, files only, no entry for a folder. A mask is a pattern with
  `*` (each `.` is taken as a dot) and has to match the whole name of a
  file. When no file is taken nothing is written, and the archive that
  was there is already deleted. A target that is there with `OVERWRITE`
  off fails ("File already exist!"). `LEVEL` is 0 (stored), 4 or 9.
  It leaves `<id>_ARCHIVE_FILEPATH` and `<id>_ARCHIVE_FILENAME`.
- **tFileUnarchive** (`Util.java`, `Unzip.java`): the kind of archive is
  told from the name (`.tar.gz`/`.tgz`, `.tar`, `.gz`, anything else a
  zip). `ROOTNAME` unpacks under a folder named after the archive.
  `EXTRACTPATH` off drops every entry's folders. A name that would land
  outside the folder fails. Times are those of the entries. It is the
  start of a loop: for every entry unpacked it sets `<id>_CURRENT_FILE`
  and `<id>_CURRENT_FILEPATH` and runs what an iterate link leads to.
  `JAVA_DECRYPT` is a cipher of Talend's own around the whole file.
- In Talend every one of the five may be the target of an iterate link.

Current tools, for how the same jobs are cut:

- Azure Data Factory, Get Metadata activity
  (<https://learn.microsoft.com/en-us/azure/data-factory/control-flow-get-metadata-activity>,
  page dated 2025-02-13): the caller lists the fields wanted (`itemName`,
  `itemType` File/Folder, `size`, `created`, `lastModified`,
  `contentMD5`, `exists`, ...). "If `exists` is specified in the Get
  Metadata field list, the activity doesn't fail even if the file,
  folder, or table doesn't exist. Instead, `exists: false` is returned."
  Times are ISO 8601 in UTC.
- Apache Hop (<https://hop.apache.org/manual/latest/>): "Get filenames"
  hands on `filename`, `short_filename`, `path`, `type`, `exists`,
  `ishidden`, `isreadable`, `iswriteable`, `lastmodifiedtime`, `size`,
  `extension`, `uri`, `rooturi`
  (`pipeline/transforms/getfilenames.html`). "Zip file" has include and
  exclude patterns, sub-folders, a level, and what to do when the
  archive is there (`workflow/actions/zipfile.html`). "Unzip file" has
  "use zipfile name as root directory", include and exclude patterns of
  entries, and what to do when a file is there
  (`workflow/actions/unzip.html`). "Load file content in memory" and
  "Change file encoding" say nothing of memory or of characters that
  cannot be written.

Python's documentation, for what is safe (read 2026-10-12; the venv runs
3.14.6, production is 3.12 or later):

- `tarfile` (<https://docs.python.org/3/library/tarfile.html>): the
  `data` filter refuses names that land outside the destination, links
  to absolute paths or out of it, and device files, and clears setuid
  and the like. It is the default only from 3.14 ("Previously, the
  filter strategy was equivalent to `fully_trusted`"), so it has to be
  named. "Note that when an exception is raised, the archive may be
  partially extracted. It is the user's responsibility to clean up."
  Under "Hints for further verification": "Extract to a new temporary
  directory", "Disallow symbolic links if you do not need the
  functionality", and limit what is unpacked; "the pre-defined filters
  do not prevent denial-of-service attacks".
- `zipfile` (<https://docs.python.org/3/library/zipfile.html>):
  `extract` drops a leading slash and every `..` from a name without a
  word; "decompression bombs (aka ZIP bomb) apply to zipfile library
  that can cause disk volume exhaustion"; "It supports decryption of
  encrypted files in ZIP archives, but it cannot create an encrypted
  file. Decryption is extremely slow as it is implemented in native
  Python"; "It is not possible to write member names in any encoding
  other than ASCII or UTF-8"; `metadata_encoding` (3.11) reads names in
  another encoding; ZIP64 is on by default.
- Zstandard is in the standard library from 3.14 only
  (`compression.zstd`, `tarfile` mode `zst`).

Tried here (Python 3.14.6, `scratchpad/arch/probe1.py`, `probe2.py`):

- `zipfile.extractall` puts `../evil.txt` and `/abs.txt` inside the
  folder under other names, and writes a link stored in the archive as a
  file holding the link's target.
- `tarfile` with the `data` filter fails on `../evil` and on a link out
  of the folder, drops the slash of `/abs`, refuses a fifo, and makes a
  link that stays inside.
- A `.tar.gz` cut in half fails with `EOFError` and leaves half a file
  behind in the folder it was unpacked to.
- A zip made with a password reads with it (`RuntimeError: Bad
  password` without); an entry in a method `zipfile` does not know
  (99, AES) is `NotImplementedError`; a flipped byte is `BadZipFile: Bad
  CRC-32`; a gzip cut short is `EOFError`, one with a wrong check sum
  `BadGzipFile`.
- `open(path, "xb")` on a link to nowhere fails and makes nothing.

## Answer: what the five are built to

Common to them, beside ticket 87's rule:

- **Kept for a converted job**: Talend's column names, its globalMap
  entries and the layout of an archive (entries by their path below the
  source folder, files only). These are what another part of a job, or
  whoever receives the archive, leans on.
- **Not kept**: Talend's silent losses. A byte that is no character, a
  character the target cannot write, a name that climbs out of the
  folder, an archive cut short: each fails the job and says where.
- **All or nothing**: an archive is written beside its place and put
  there when it is whole; an archive is unpacked into a folder of its
  own beside the files' places, and the files are moved in when every
  one of them is whole. A run that fails leaves the folder as it was.
- **Never held in memory**: files are gone through in pieces. The one
  exception is the raw file input, whose whole purpose is one value
  holding a file; it is bounded by a limit the job can raise.
- **Links**: nothing is read through a link and no link is written. A
  link among the files to archive, or in an archive, is left out and
  named in a warning. (Python's own hint, and v2's archive writes none.)
- **The kind of an archive is told from what it holds**, not from its
  name: a name is the sender's to choose.
- **What each did** is in the log and in globalMap (`<id>_NB_FILE`, the
  count of files, by the name Talend's file list uses).

Per component (each has its own ticket for the detail):

- File properties: the schema says which properties are wanted, as in
  Data Factory. Talend's eight names are kept. Beside them `exists`
  (asking for it makes a missing file a row and not a failure, as in
  Data Factory), `type` (`file`, `folder`) and `sha256`. `mode_string`
  is the ten characters `ls -l` shows; `mtime` milliseconds;
  `mtime_string` local time, `YYYY-MM-DD HH:MM:SS`.
- Raw file input: text only (bytes and streams have no column type in
  v2 and are refused); read strictly; a limit on the size.
- Change file encoding: strict both ways, the place of the fault named
  by its line; UTF-8 when no input encoding is given (Talend takes the
  machine's, which is not the same on two servers).
- File archive: Talend's three kinds, and tar without compression and
  with Zstandard where the Python has it; no encryption (refused);
  entries in a fixed order; the same files give the same bytes.
- File unarchive: every kind the standard library reads, told from the
  content; names checked before anything is written; a zip's declared
  sizes held against the free space first; passwords for the old zip
  encryption only.

Left for the loop components: each of the five as the target of an
iterate link, and the unarchive as the start of one (it keeps the list
of what it unpacked for that).
