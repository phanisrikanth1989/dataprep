# 02 - Polars facts: reading and writing delimited files

Status: resolved
Type: research

## Question

What can Polars read and write natively for delimited files, lazily
(`scan_csv`, `sink_csv`) and eagerly (`read_csv`, `write_csv`)? Primary
sources only, stamped against the range this repo pins (`polars>=1.38,<2.0`;
1.44.2 is installed), with the version noted wherever behaviour changed inside
that range.

Specifically:

1. Encodings: which are accepted lazily and which eagerly; what happens to
   non-UTF-8 bytes in each; the documented way to read ISO-8859-15 / Latin-1
   and what it costs (is the whole file decoded in Python, is it held in
   memory); the same for writing.
2. Separators and line endings: multi-character field separators, custom and
   multi-character row separators, CRLF.
3. Quoting and escaping: quote character, an escape character distinct from
   the quote character, quote styles on write, embedded newlines.
4. Nulls and empties: how an empty unquoted field, a quoted empty string and
   `null_values` are read for each dtype; `missing_utf8_is_empty_string`; how
   nulls and empty strings are written.
5. Row limits that stay lazy: header and skipped rows, `n_rows`, skipping
   footer rows, row index, counting rows.
6. Ragged lines: too many or too few fields; `truncate_ragged_lines`,
   `ignore_errors`.
7. Number and date text: decimal comma and thousands separators on read;
   float formatting on write (`float_precision`, `float_scientific`); date
   and datetime formats on read and write.
8. Compression: reading and writing gzip and zip.

For each: the API, whether it keeps the query lazy, and what it costs when it
does not.

Feeds [The performance bar](05-performance-bar.md),
[Types, nulls and schemas](13-types-nulls-and-schemas.md),
[Encoding: what to do about ISO-8859-15](14-encoding-iso-8859-15.md) and the
two delimited-file key tickets
([input](20-config-keys-delimited-file-input.md),
[output](21-config-keys-delimited-file-output.md)).

## Answer

Resolved 2026-10-05 by a research agent. The full note, every claim cited or
labelled as an observation:
[Polars facts: reading and writing delimited files](../research/2026-10-05-polars-delimited-files.md)
(also on the throwaway branch `research/polars-delimited-files`, commit
`d637620a`). Facts are read at both ends of the pin, tags `py-1.38.0` and
`py-1.44.2`. Only 1.44.2 was run, and the timings are from one Mac with a
warm cache: provisional for the target servers.

The gist, by sub-question:

1. Encodings. `scan_csv` takes `utf8` or `utf8-lossy` only, and the
   maintainers call non-UTF-8 CSV out of scope. `read_csv(encoding=...)`
   works eagerly, by decoding the whole file in Python: about 5 times the
   time and 1.1 GB more peak memory on a 378 MB file. That path also alters
   CR and CRLF inside quoted fields and returns garbage on gzip input. Under
   strict `utf8` one non-UTF-8 byte fails the whole read; `utf8-lossy`
   replaces it irreversibly. A pure-ASCII file reads the same either way,
   but Latin bytes that happen to form valid UTF-8 are not detected. Writing
   is UTF-8 only; re-encoding through a Python file object stays streaming
   at about 5 times the native sink time.
2. Separators and line endings. The field separator is one ASCII byte, on
   read and on write; multi-character separators are closed as not planned.
   The read row separator is one byte. CRLF is handled by default, and
   `eol_char="\r\n"` is accepted but mis-parses.
3. Quoting. RFC 4180 only: there is no escape character, and
   backslash-escaped quotes are mangled without error. One lone quote in an
   unquoted field raises `CSV malformed` and makes `select(pl.len())` return
   a wrong count. `quote_char=None` turns quoting off.
4. Nulls and empties. An unquoted empty field is null for every type; `""`
   is an empty string for String and null for everything else. Giving
   `null_values` as a dict turns `""` into null as a side effect. Blank lines
   arrive as all-null rows. This explains finding 19.
5. Row limits. Header rows, skipped rows and `n_rows` stay lazy. There is no
   footer parameter and no negative-length lazy slice. A counting pass plus
   `n_rows` stays lazy, but a footer that does not fit the schema still
   raises, because rows cut off by a slice are parsed when they share a read
   chunk. `select(pl.len())` on a CSV scan returned wrong counts for filtered
   scans on 1.39.0 to 1.39.3 (fixed in 1.40.0) and for sliced scans on at
   least 1.40.1 (fixed in 1.41.0).
6. Ragged lines. Too many fields raises, unless projection drops any column,
   in which case it never raises. Too few fields are silently padded with
   nulls and nothing makes that an error.
7. Number and date text. `decimal_comma` exists on read and write; thousands
   separators exist nowhere. Floats are written as shortest round-trip text
   (`30200.0`, `1e+20`) unless `float_precision` is set. The reader has no
   date format parameter: custom patterns need `str.to_date` on a String
   column, which stays lazy. The writer takes one date format and one
   datetime format per file.
8. Compression. gzip, zlib and zstd are read by content, streaming in
   `scan_csv`; gzip and zstd can be written (marked unstable). Zip, bzip2 and
   xz are unsupported in both directions.

Also in the note: append has no parameter but a file opened in `"ab"` works;
splitting output by row count exists through `PartitionBy` (marked
unstable); and finding 20, full-row input failing on a quoted line, is the
quoting rule in 3.

Re-checked independently on polars 1.44.2 before the note was accepted
(scripts not kept): the encoding behaviours in 1, including Latin bytes read
as UTF-8 without error; the lone-quote error with its wrong count, and the
backslash case, in 3; all of 4, including the renamed parameter; the ragged
cases in 6; float text and appending in 7. One nuance from the re-check: the
note says a zip or bzip2 file can come back as an empty frame with no error.
That reproduced for a 2-row file; files of 50 and 500 rows raised an error
instead. The silent case is real but limited to very small files.

Could not establish: anything by execution on versions other than 1.44.2, so
the first release with the sliced-count bug is unknown; whether write chunks
can split a UTF-8 character when re-encoding; performance on the target
servers; whether default float and date text is byte-identical across the
pin.

Surfaced for
[Which Polars versions v2 supports](28-which-polars-versions-v2-supports.md):
the wrong counts on 1.39 and 1.40, and the rename of
`missing_utf8_is_empty_string` to `empty_string_is_null`, with inverted
meaning, in 1.43.0. Surfaced for the two delimited-file key tickets: the
reader and writer behaviours above that give a wrong result without an error,
which v2 has to guard against, refuse or accept one by one.
