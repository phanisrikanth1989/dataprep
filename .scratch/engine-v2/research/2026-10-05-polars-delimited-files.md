# Polars facts: reading and writing delimited files (ticket 02)

Answers `.scratch/engine-v2/issues/02-polars-facts-delimited-files.md` (its
eight numbered sub-questions are sections 1 to 8 below). Facts only; no
recommendations.

Researched: 2026-10-05. Facts are stamped against two release tags of
pola-rs/polars: **py-1.38.0** (released 2026-02-04, the lower bound of this
repo's pin `polars>=1.38,<2.0`) and **py-1.44.2** (released 2026-09-09, the
installed version and the newest 1.x release; `py-2.0.0-rc.2` of 2026-09-20 is
a pre-release outside the pin). Where behaviour changed between the two tags,
the release that changed it is named. Release dates are from
https://github.com/pola-rs/polars/releases.

Sources are primary only: the Polars Python and Rust source and test suite at
those two tags; the release notes of every release from py-1.38.0 to
py-1.44.2; the API reference and user guide on docs.pola.rs; statements by
Polars maintainers in the pola-rs/polars issue tracker (status questions
only); and, for the Python-side decoding that `read_csv` delegates to, the
Python library reference and RFC 3629. No blogs, no Stack Overflow, no AI
summaries.

Two kinds of statement appear below and are kept apart:

- **Sourced**: followed by a citation to a line-numbered file at a tag, a
  release note, a docs page or an issue. "Both tags" means the cited code or
  docstring is present at py-1.38.0 and at py-1.44.2 (the two tagged files
  were diffed); such a fact is taken to hold for the releases in between
  unless a release note says otherwise.
- **Observed on polars 1.44.2**: the result of running a short snippet against
  the installed build (polars 1.44.2, Python 3.14.6, macOS 26.6 arm64, 10
  cores, 16 GB). An observation confirms a source; where it is the only
  evidence, that is said. Observations are provisional for the target RHEL
  servers and for the other versions in the pin. The snippets were temporary
  files outside the repo; each observation states its input.

The installed package's Python files that are cited here were diffed against
the py-1.44.2 tag and are identical, so py-1.44.2 line numbers apply to the
installed build. Quotations are verbatim, except that a non-ASCII character
is written as `[U+XXXX]` to keep this file plain ASCII, and that a docstring
entry is written as "name -- description" on one line.

Shorthand (every link is to a release tag, so it does not move):

- `py44:` = https://github.com/pola-rs/polars/blob/py-1.44.2/py-polars/src/polars/
- `py38:` = https://github.com/pola-rs/polars/blob/py-1.38.0/py-polars/src/polars/
- `rs44:` = https://github.com/pola-rs/polars/blob/py-1.44.2/crates/
- `rs38:` = https://github.com/pola-rs/polars/blob/py-1.38.0/crates/
- `test44:` = https://github.com/pola-rs/polars/blob/py-1.44.2/py-polars/tests/unit/io/
- `rel:<tag>` = https://github.com/pola-rs/polars/releases/tag/<tag>
- `#N` = https://github.com/pola-rs/polars/issues/N (pull requests redirect
  from the same URL)
- A bare `#L10-L20` continues the file cited just before it; `rs38:...` or
  `py38:...` means the same file as the citation just before it, at the
  other tag.

The API reference (https://docs.pola.rs/api/python/stable/reference/api/polars.scan_csv.html
and its sibling pages for `read_csv`, `DataFrame.write_csv`,
`LazyFrame.sink_csv`) has one page set for all of 1.x: "stable", which served
py-1.44.2 on 2026-10-05, and none per minor version. Version-stamped
statements therefore cite the tagged source files whose docstrings generate
those pages; a docstring quoted from the py-1.44.2 tag is the text that the
reference page showed on that date.

---

## Summary

1. `scan_csv` takes only `utf8` / `utf8-lossy` at both tags, and maintainers call non-UTF-8 CSV "out-of-scope for Polars" (#26244, Jan 2026); `read_csv(encoding="iso-8859-15")` works only eagerly, by decoding the whole file in Python (observed: about 5x the time and +1.1 GB peak for a 378 MB file).
2. That eager codec path also changes data: for a `str` path it turns CR and CRLF inside quoted fields into LF and breaks `eol_char="\r"` (#27408, open); on a gzip file it returns garbage with no error; text handles opened with a Latin codec are refused for reading and writing.
3. Under strict `utf8` one non-UTF-8 byte fails the read with `invalid utf-8 sequence` (even in an unselected column, even with `ignore_errors`); `utf8-lossy` turns each bad byte into U+FFFD for good; pure-ASCII files read the same either way, but Latin bytes that happen to form valid UTF-8 are not detected.
4. Writing is UTF-8 only (`write_csv` and `sink_csv` have no `encoding`); another encoding means Python re-encodes, either per chunk through an object with `write(bytes)` (stays streaming; observed about 5x the native sink time, flat memory) or the whole text through `write_csv(None)` (observed about +1.5 GB peak).
5. Field separator and quote character are one ASCII byte each, on read and write; multi-character and non-ASCII separators are rejected and closed as not planned (#2728, #23626); the read row separator is one byte too, and `scan_csv(eol_char="\r\n")` is not rejected but silently mis-parses.
6. Quoting is RFC 4180 only: no escape character on read or write (#3074, "I don't want to support this"); backslash-escaped quotes are mangled without error; one lone quote in an unquoted field raises `CSV malformed` and makes `select(pl.len())` miscount; `quote_char=None` switches quoting off.
7. An unquoted empty field is null for every dtype; `""` is an empty string for String and null for every other dtype; `empty_string_is_null=False` changes String only; `null_values` given as a dict (or as `""`) turns `""` into null as a side effect; blank lines arrive as all-null rows.
8. `missing_utf8_is_empty_string` was renamed `empty_string_is_null`, with inverted meaning, in 1.43.0: the old name warns from 1.43.0 on and the new name does not exist before it, so no one spelling is clean across the pin.
9. There is no footer-skip parameter and a LazyFrame slice cannot have a negative length; the lazy route is a counting pass plus `n_rows` (observed: 392 MB counted in 0.01 s), but rows cut off by a slice are still parsed when they share a read chunk, so a footer that does not fit the schema still raises, lazily and eagerly alike.
10. `select(pl.len())` on a CSV scan is a dedicated fast count; it returned wrong counts for filtered scans on 1.39.0-1.39.3 (#27168) and for sliced scans at least on 1.40.1 (#27534); fixed in 1.40.0 and 1.41.0.
11. A line with too many fields raises unless `truncate_ragged_lines=True`, except that it never raises once projection pushdown drops any column; a line with too few fields is silently padded with nulls and nothing can make it an error; `ignore_errors=True` nulls a bad value and keeps the row.
12. Numbers: `decimal_comma` exists on read and write, thousands separators nowhere (#18797, open); floats are written as shortest round-trip text (`30200.0`, `1e+20`) unless `float_precision` / `float_scientific` are set; `pl.Config(trim_decimal_zeros=True)` silently changes Decimal text in written files.
13. Dates: the reader has no format parameter and infers one layout per column from its first value; custom patterns need `str.to_date` / `str.to_datetime` on a String column (stays lazy); the writer takes one `date_format` / `datetime_format` per file, and default datetime text always carries fractional seconds.
14. gzip, zlib and zstd are read transparently by content, streaming in `scan_csv` (observed 199 MB peak against 1,094 MB for `read_csv`); gzip and zstd can be written since 1.38.0 (unstable); zip is supported in neither direction (#19447), and a zip or bzip2 file can come back as an empty frame with no error.
15. `read_csv` and `scan_csv` are two different readers that share field parsing; `write_csv` is `sink_csv` on the in-memory engine; append has no parameter (a file opened in `"ab"` works natively); splitting by row count is `sink_csv(pl.PartitionBy(dir, max_rows_per_file=N))` (unstable).

---

## What changed inside the pinned range (py-1.38.0 to py-1.44.2)

Only changes that touch delimited files. Each row is from the release notes
of that release unless another source is given.

| Release | Change | Source |
|---|---|---|
| 1.38.0 (2026-02-04) | `compression`, `compression_level`, `check_extension` added to `write_csv` / `sink_csv` (unstable). `pl.scan_lines` / `pl.read_lines` added (unstable). Both are therefore present across the whole pin. | `rel:py-1.38.0` (#26111, #26112) |
| 1.38.1 | Fix for schema inference reading some lines twice and others not at all when the inferred region crosses a read chunk. Within the pin this affects 1.38.0 only, and only when Polars infers a schema. | `rel:py-1.38.1`, #26452 |
| 1.39.0 | `missing_columns` added to `scan_csv` (unstable). `cache` and `file_cache_ttl` of `scan_csv` deprecated. Regression: a filter on a CSV scan followed by `select(pl.len())` returns the unfiltered count. | `rel:py-1.39.0` (#26787, #26688); #27168; `py44:io/csv/functions.py#L1243-L1247` |
| 1.40.0 | Fix for that regression: no fast count when a predicate is pushed into the scan. | `rel:py-1.40.0` (#27190) |
| 1.41.0 | Fix: no fast count when the scan carries a slice (`n_rows`, `head`, `slice`); the bug was reported against 1.40.1. `read_csv` docstring gains "Compressed files are supported when reading from a path". | `rel:py-1.41.0` (#27536, #27434); #27534 |
| 1.42.0 | Casting String to Date / Datetime / Time with `cast` is deprecated ("will be removed in Polars 2.0. Use `str.to_date()` instead" is the 1.44.2 warning text). | `rel:py-1.42.0` (#28056); observed on polars 1.44.2 |
| 1.43.0 | `missing_utf8_is_empty_string` renamed `empty_string_is_null` with inverted meaning; the old name still works and warns. `scan_csv` accepts `schema_overrides` as a list of dtypes without `new_columns` (before: `TypeError`). | `rel:py-1.43.0` (#28173, #28226); `py44:io/csv/functions.py#L1122-L1127`; `py38:io/csv/functions.py#L1347-L1349` |
| 1.43.2 | `infer_schema_files` added to `scan_csv` (unstable). | `rel:py-1.43.2` (#28440) |
| 1.44.0 | `rechunk` deprecated on read and scan functions. Date inference in the CSV reader keeps its state across values. | `rel:py-1.44.0` (#28063, #28663) |
| unstable APIs | `scan_lines` / `read_lines` default column name is `lines` at 1.38.0 and `line` at 1.44.2. | `py38:io/lines.py#L40`, `py44:io/lines.py#L40` |

Unchanged between the two tags, checked by diffing the tagged files: the CSV
writer's serializer and options (`polars-io/src/csv/write/write_impl/serializer.rs`
and `csv/write/options.rs`, zero changed lines); the field splitter and the
quote-unescape code (`csv/read/splitfields.rs`, `csv/read/utils.rs`, zero
changed lines); the body of `parse_lines`, which holds the null, ragged-line
and carriage-return rules (only an error-message line added); the Python
encoding path `prepare_file_arg` (only an unrelated helper added); and
`DataFrame.write_csv`, whose text is identical.

---

## 0. How the four functions execute

Every "lazy or eager" answer below rests on these four facts.

- **`scan_csv` is the lazy reader.** It builds a plan node; in both engines
  the scan is executed by the streaming engine's CSV source, because the
  in-memory planner hands every file scan to the streaming executor
  (`rs44:polars-mem-engine/src/planner/lp.rs#L499-L521`,
  `rs38:polars-mem-engine/src/planner/lp.rs#L376-L396`). Projection, filter
  and slice pushdown happen "at the scan level"
  (https://docs.pola.rs/user-guide/lazy/optimizations/).
- **`read_csv` is a different, eager reader.** For a local path it calls
  `PyDataFrame.read_csv`, which runs `CoreReader` over the whole file
  (`py44:io/csv/functions.py#L584-L622` and `#L743-L774`,
  `rs44:polars-python/src/dataframe/io.rs#L29-L125`,
  `rs44:polars-io/src/csv/read/read_impl.rs#L134-L277`; the source carries the
  note "TODO use `scan_csv` to implement `read_csv`" at `#L189`, both tags).
  It goes through `scan_csv` only for glob patterns, `hf://` paths, or when
  `POLARS_FORCE_STREAMING`, `POLARS_AUTO_STREAMING` or `POLARS_FORCE_ASYNC`
  is set (`py44:io/csv/functions.py#L510-L582`, `#L693-L739`). The two readers
  share the per-field code (`parse_lines` and the dtype builders), so field
  semantics are the same; chunking, decompression and slicing differ.
  The docstring warns: "Calling `read_csv().lazy()` is an antipattern as this
  forces Polars to materialize a full csv file and therefore cannot push any
  optimizations into the reader" (`py44:io/csv/functions.py#L264-L268`).
- **`sink_csv` is the lazy writer.** "Evaluate the query in streaming mode and
  write to a CSV file. This allows streaming results that are larger than RAM
  to be written to disk." Its `engine` defaults to `"auto"`, which falls back
  to `"streaming"` (`py44:lazyframe/frame.py#L3777-L3779`, `#L3920-L3940`;
  1.38.0 says the same at `py38:lazyframe/frame.py#L3562-L3564`).
- **`write_csv` is `sink_csv` on a materialized frame.** It calls
  `self.lazy().sink_csv(..., engine="in-memory")`, and file sinks are run by
  the streaming executor even then (`py44:dataframe/frame.py#L3238-L3266`,
  `py38:dataframe/frame.py#L3218-L3246`,
  `rs44:polars-mem-engine/src/planner/lp.rs#L415-L417`). The CSV options of
  the two are the same list; `sink_csv` adds `maintain_order`, `sync_on_close`,
  `mkdir`, `lazy`, `engine`, `optimizations`, and `write_csv` alone can return
  a `str` when `file=None` (`py44:dataframe/frame.py#L3067-L3093`,
  `py44:lazyframe/frame.py#L3743-L3775`).

---

## 1. Encodings

| Ref | Capability | Lazy (`scan_csv`, `sink_csv`) | Eager (`read_csv`, `write_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 1a | Read UTF-8 | yes, `encoding="utf8"` (default) | yes | - | both tags |
| 1b | Read UTF-8 and replace bad bytes | yes, `encoding="utf8-lossy"` | yes | none, but lossy | both tags |
| 1c | Read ISO-8859-15, Latin-1 or any other codec | no: `ValueError` | yes: `encoding=<Python codec name>` | whole file decoded by Python and held in memory | both tags |
| 1d | Read from a Python text handle opened with a Latin codec | no: `InvalidOperationError` | no: same error | - | both tags |
| 1e | Read bytes or a file-like object already decoded by Python | accepted, but the object is read fully into memory when `scan_csv` is called | yes | whole file in memory; the plan after it stays lazy | both tags |
| 1f | Write UTF-8, optional BOM | yes, `include_bom` | yes | - | both tags |
| 1g | Write any other encoding | no parameter | no parameter | Python re-encodes: per chunk through a `write()` object, or the whole text via `write_csv(None)` | both tags |

### Details and sources

**1a / 1b / 1c. What each reader accepts.**
`scan_csv`: "encoding : {'utf8', 'utf8-lossy'} -- Lossy means that invalid utf8
values are replaced with [U+FFFD] characters. Defaults to "utf8"."
(`py44:io/csv/functions.py#L1271-L1273`, `py38:io/csv/functions.py#L1203-L1205`).
The Rust reader has exactly two encodings, `Utf8` and `LossyUtf8`
(`rs44:polars-io/src/csv/read/options.rs#L362-L368`, `rs38:...#L336`), and any
other string is rejected when the argument is converted
(`rs44:polars-python/src/conversion/mod.rs#L979-L989`).
`read_csv`: "encoding : {'utf8', 'utf8-lossy', 'windows-1252',
'windows-1252-lossy', ...} ... When using other encodings than `utf8` or
`utf8-lossy`, the input is first decoded in memory with python."
(`py44:io/csv/functions.py#L204-L208`, `py38:io/csv/functions.py#L195-L199`).
A name ending in `-lossy` means Python's `errors="replace"`
(`py44:io/_utils.py#L182-L187`). After the Python decode the Rust reader is
called with `utf8` (`py44:io/csv/functions.py#L611`).
`scan_lines` / `read_lines` have no encoding parameter at all
(`py44:io/lines.py#L129-L150`).

Observed on polars 1.44.2: `scan_csv(encoding=x)` for x in `utf-8`, `latin1`,
`iso-8859-15`, `windows-1252`, `ascii` raises `ValueError` ("csv `encoding`
must be one of {'utf8', 'utf8-lossy'}, got ...") at the call, before any
collect. `read_csv` accepts all of those plus `windows-1252-lossy`; an unknown
name raises Python's `LookupError: unknown encoding`. With
`encoding="iso-8859-15"`, `read_csv` returns e-acute (U+00E9) for the byte
0xE9 and the euro sign (U+20AC) for 0xA4; with `encoding="latin1"` the byte
0xA4 becomes U+00A4 instead. Python's `iso8859_15` and `latin_1` are separate
codecs
(https://docs.python.org/3/library/codecs.html#standard-encodings) and differ
at eight bytes: 0xA4, 0xA6, 0xA8, 0xB4, 0xB8, 0xBC, 0xBD, 0xBE (observed on
Python 3.14.6). `scan_lines` on Latin bytes raises `ComputeError: invalid utf8`.

**1d. Text handles.** Polars unwraps a `TextIOWrapper` and refuses it unless
its encoding is UTF-8, with the error "file encoding is not UTF-8"
(`rs44:polars-python/src/file.rs#L375-L397`, `rs38:...#L384`). The same
function serves readers and writers. Upstream test:
`test44:test_csv.py#L2484` (`test_write_csv_raise_on_non_utf8_17328`).
Observed on polars 1.44.2: a handle from `open(p, encoding="iso-8859-15")`
passed to `scan_csv` or `read_csv`, and a handle from
`open(p, "w", encoding="iso-8859-15")` passed to `write_csv` or `sink_csv`,
all raise `InvalidOperationError: file encoding is not UTF-8`.

**1e. Bytes and other file-like objects.** A `bytes` object or a `BytesIO`
becomes an in-memory buffer; any other object with `read()` is drained by one
`read()` call into a buffer, and a returned `str` is taken as UTF-8
(`rs44:polars-python/src/file.rs#L70-L100`, `#L290-L295`, `#L407-L439`).
Observed on polars 1.44.2: a custom object whose `read()` decodes ISO-8859-15
is read with exactly one `read()` call, made inside `scan_csv()` before any
collect; `scan_csv(io.StringIO(text))` and `scan_csv(decoded_bytes)` both
work and return correct text. So Python can decode and hand the result to the
lazy reader, at the price of the whole decoded file living in memory for the
life of the LazyFrame.

**1f / 1g. Writing.** `write_csv` and `sink_csv` have no `encoding` parameter;
the only encoding control is `include_bom`: "Whether to include UTF-8 BOM in
the CSV output" (`py44:dataframe/frame.py#L3067-L3103`,
`py44:lazyframe/frame.py#L3743-L3788`; identical signature at 1.38.0,
`py38:dataframe/frame.py#L3047-L3073`). Open requests #11476 (2023) and #28803
(2026-08-13) have no maintainer reply. A 2023 pull request adding `encoding`
to `write_csv` (#10326) was closed unmerged; maintainers there:

> "But we don't support encodings in the reader. This means we could only
> write, but not round trip." (ritchie46)

> "We store everything as UTF-8 internally, so encoding to anything else is
> going to incur a re-encoding step regardless. Since this is the case there
> isn't really a performance argument as to why this should happen inside
> Polars instead of it being done by the caller ... I think we *really* don't
> want to get into the minefield of input encodings." (orlp)

> "In Python you pass an object with a `write(b)` method (as well as dummy
> `read` and `seek` methods) as the first argument to `write_csv` that does
> the re-encoding on the fly as well. In both cases you need to be careful
> around UTF-8 codepoint boundaries, the buffer with which `write` gets called
> might end in the middle of a codepoint." (orlp)

Writing to a Python object is supported and tested: Polars calls `write()`
with `bytes`, or with `str` when the object is a `TextIOBase`, and uses the
returned count (`rs44:polars-python/src/file.rs#L188-L245`,
`rs44:polars-python/src/lazyframe/sink.rs#L14-L34`, `test44:test_csv.py#L2138`
`test_custom_writable_object`). On Unix an exact `FileIO`, `BufferedWriter`,
`BufferedReader` (and a UTF-8 `TextIOWrapper`) is not called back at all: its
file descriptor is duplicated and written natively
(`rs44:polars-python/src/file.rs#L323-L373`).

Observed on polars 1.44.2:
- `write_csv(encoding=...)` and `sink_csv(encoding=...)` raise `TypeError:
  ... got an unexpected keyword argument 'encoding'`. Output bytes for
  e-acute are `c3 a9`. `include_bom=True` prefixes `ef bb bf`. A UTF-8 BOM at
  the start of an input file is dropped by both readers (also
  `test44:test_csv.py#L3218`).
- A custom object receives `bytes`: 9 calls for a 2.49 MB output, 751 calls
  for a 392 MB output (chunks up to about 0.5 MB). A `FileIO` subclass is
  called back; an exact `BufferedWriter` is not.
- `codecs.EncodedFile(raw, "utf-8", "iso-8859-15")` cannot be passed: its
  `write()` returns `None` and Polars raises `OSError: 'NoneType' object
  cannot be interpreted as an integer`. A wrapper has to return the byte count.
- `df.write_csv(None).encode("iso-8859-15")` yields the Latin-9 bytes; a
  character outside the charset (U+4E2D, U+2019) raises Python's
  `UnicodeEncodeError` unless an `errors=` policy is chosen in Python.

### What happens to non-UTF-8 bytes

| Case | Result | Source |
|---|---|---|
| `encoding="utf8"`, schema has at least one String column | `ComputeError: invalid utf-8 sequence`. The whole read chunk is validated, not single fields, so the error carries no column or row. | lazy: `rs44:polars-stream/src/nodes/io_sources/csv/chunk_reader.rs#L46-L47`, `#L69-L71` (`rs38:polars-stream/src/nodes/io_sources/csv.rs#L494-L495`, `#L517-L519`); eager: `rs44:polars-io/src/csv/read/read_impl.rs#L398-L399`, `#L443-L449` |
| same, bad byte in a column that is not selected | same error (validation is per chunk) | same lines; observed on polars 1.44.2 with `.select("id")` |
| same, with `ignore_errors=True` | same error; the chunk check does not look at `ignore_errors` | same lines; observed on polars 1.44.2 for `scan_csv` and `read_csv` |
| `encoding="utf8"`, schema has no String column | no chunk check; the bad byte fails in its own field: `could not parse ... as dtype i64 at column 'a' (column number 1)` | same lines (the check is made only when the schema has a String column); observed on polars 1.44.2 |
| `encoding="utf8-lossy"` | every invalid sequence in a String field becomes U+FFFD, through `String::from_utf8_lossy`; not reversible | `rs44:polars-io/src/csv/read/builder.rs#L235-L250` (same lines at 1.38.0); observed on polars 1.44.2: `caf\xe9` reads as `caf` + U+FFFD |
| Latin bytes that happen to be valid UTF-8 (for example `c3 a9`) | read as UTF-8 with no error (one character, U+00E9, where ISO-8859-15 means two) | observed on polars 1.44.2; the only evidence, but it follows from the definition of UTF-8 |
| UTF-8 file read with `encoding="iso-8859-15"` | no error, wrong text: every byte is a valid ISO-8859-15 character | observed on polars 1.44.2 and Python 3.14.6 (all 256 bytes decode) |

Bytes 0x00-0x7F mean the same characters in UTF-8, ISO-8859-1 and
ISO-8859-15 (observed on Python 3.14.6 for all 128 values; for UTF-8, RFC 3629
section 1: "US-ASCII characters are encoded in one octet having the normal
US-ASCII value, and any octet with such a value can only stand for a US-ASCII
character", https://www.rfc-editor.org/rfc/rfc3629). A pure-ASCII file is
therefore read identically by `scan_csv` whatever Latin encoding its config
names. Strict UTF-8 validation is not a test for "this file is ASCII": it
passes any valid multi-byte sequence. Observed on polars 1.44.2:
`pl.col(c).str.len_bytes() != pl.col(c).str.len_chars()` is true exactly for
values containing non-ASCII characters, and is an ordinary lazy expression.

### The documented way to read ISO-8859-15, and what it costs

The documented way is `read_csv(..., encoding="iso-8859-15")` (1c). Its
mechanism, from `prepare_file_arg` (`py44:io/_utils.py#L135-L297`, same logic
at `py38:io/_utils.py#L118-L280`): "When `encoding` is not `utf8` or
`utf8-lossy`, the whole file is first read in Python and decoded using the
specified encoding and returned as a `BytesIO`" (`py44:io/_utils.py#L153-L157`).

- **Is the whole file decoded in Python?** Yes: one `f.read()` then
  `.encode("utf8")` (`py44:io/_utils.py#L287-L295`).
- **Is it held in memory?** Yes. The decoded Python `str` and its UTF-8 copy
  exist together during the re-encode, and the UTF-8 copy stays alive while
  the Rust reader parses it (`py44:io/csv/functions.py#L671-L672`). A Python
  `str` costs one byte per character only while every character is below
  U+0100; one euro sign (0xA4 in ISO-8859-15) makes the whole string two bytes
  per character (observed on Python 3.14.6: 1.01 against 2.01 bytes per
  character).
- **Line endings change for `str` paths.** A `str` path is opened in Python
  text mode with the default `newline=None`, a `Path` object is read as bytes
  (`py44:io/_utils.py#L229-L239` against `#L259-L266` and `#L287-L295`). In
  text mode "Lines in the input can end in '\n', '\r', or '\r\n', and these
  are translated into '\n' before being returned to the caller"
  (https://docs.python.org/3/library/functions.html#open). Observed on polars
  1.44.2 with `encoding="iso-8859-15"`: for a `str` path the quoted fields
  `"x\ry"` and `"p\r\nq"` come back as `x\ny` and `p\nq`, while a `Path` or
  native UTF-8 read returns them unchanged; and a CR-terminated file read with
  `eol_char="\r"` returns zero rows and a garbled header. Open bug #27408
  (2026-04-25); its fix #27413 was still open on 2026-10-05, with a maintainer
  asking whether it would break CRLF handling.
- **Compressed input is not handled.** The compressed bytes are decoded as
  text before Polars sees them. Observed on polars 1.44.2:
  `read_csv("f.csv.gz", encoding="iso-8859-15")` returns a one-column frame of
  garbage with no error; `encoding="utf8-lossy"` on the same file is correct.
- **`use_pyarrow=True` is not a way around it.** That branch passes the codec
  to pyarrow's reader, but is taken only when `schema_overrides`, `n_rows`,
  `n_threads`, `low_memory` and `null_values` are all unset
  (`py44:io/csv/functions.py#L338-L345`), so it cannot carry explicit dtypes.
  Observed on polars 1.44.2: with `schema_overrides` given, the call falls back
  to the Python-decode path.

Cost, observed on polars 1.44.2 (see "Cost observations" for the set-up; 4
million rows, 378 MB as ISO-8859-15, 392 MB as UTF-8):

| Read | Median s | Peak RSS MB |
|---|---|---|
| `read_csv(utf8 file)` | 0.10 | 1,085 |
| `scan_csv(utf8 file).collect()` | 0.17 | 1,246 |
| `read_csv(latin file, encoding="iso-8859-15")` | 0.56 | 2,181 |
| `read_csv(latin file, encoding="utf8-lossy")` | 0.17 | 1,076 |
| Python only: whole-file `read().decode().encode()` | 0.36 | 1,581 |
| whole-file decode in Python, then `scan_csv(bytes).collect()` | 0.48 | 2,382 |
| Python only: streaming transcode to UTF-8 in 1 MiB chunks (`codecs` incremental decoder), output discarded | 0.27 | 61 |

The last row is not a Polars feature; it is included because it is the
measured price of the one route that leaves a UTF-8 file `scan_csv` can then
read lazily (it also needs a temporary file as large as the input).

Maintainer position on encodings in the reader:

> "Non-UTF-8 encoded CSVs are out-of-scope for Polars." (orlp, #26244, closed
> as not planned 2026-01-23)

> "Our reader only supports `utf8`, so there is something on the python side
> that decodes the buffer and gives us a utf8 buffer ... this is not something
> we can do in the `scan` operations." (ritchie46, #16881, 2024-06-11)

Requests #25423 (`windows-1252` in `scan_csv`, 2025-11) and #28705 (cp949,
2026-08) are open with no maintainer reply. Neither `Cargo.lock` contains a
character-set transcoding crate such as `encoding_rs`
(https://github.com/pola-rs/polars/blob/py-1.44.2/Cargo.lock, same at
py-1.38.0).

### Cost of writing another encoding

Observed on polars 1.44.2 (same set-up, output discarded to the null device):

| Write | Median s | Peak RSS MB |
|---|---|---|
| `scan_csv(utf8).sink_csv(path)` (native UTF-8) | 0.19 | 783 |
| `scan_csv(utf8).sink_csv(obj)`, `obj.write` copies the bytes unchanged | 0.18 | 799 |
| `scan_csv(utf8).sink_csv(obj)`, `obj.write` re-encodes to ISO-8859-15 with an incremental UTF-8 decoder | 0.97 | 776 |
| `read_csv(utf8)`, `write_csv(None)`, `str.encode("utf-8")` | 0.55 | 2,269 |
| `read_csv(utf8)`, `write_csv(None)`, `str.encode("iso-8859-15")` | 1.20 | 2,255 |
| Python only: streaming transcode UTF-8 to ISO-8859-15, 1 MiB chunks | 0.94 | 62 |

The Python callback itself costs nothing measurable at this chunk size (751
calls). The cost is the conversion from UTF-8 to ISO-8859-15 in CPython,
which took about 3.5 times as long as the opposite direction (0.94 s against
0.27 s for the same data).

---

## 2. Separators and line endings

| Ref | Capability | Lazy (`scan_csv`, `sink_csv`) | Eager (`read_csv`, `write_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 2a | Field separator: one ASCII byte (including tab and control bytes) | yes, `separator` | yes | - | both tags |
| 2b | Field separator: several characters | no: `ValueError` | no: `ValueError` | the file must be rewritten before Polars reads it; not planned | both tags |
| 2c | Field separator: one non-ASCII character | no: `ValueError` (it is 2+ bytes in UTF-8) | no | same | both tags |
| 2d | Read CRLF files | yes, with the default `eol_char="\n"` | yes | - | both tags |
| 2e | Read with another single-byte row separator (CR, or any byte) | yes, `eol_char` | yes | - | both tags |
| 2f | Read with a multi-character row separator | no; **not rejected**: the first byte is used silently | no: `ValueError` | - | both tags |
| 2g | Write any row separator, including several characters | yes, `line_terminator` | yes | - | both tags |

### Details and sources

**2a / 2b / 2c.** Read docstring: "separator -- Single byte character to use
as separator in the file" (`py44:io/csv/functions.py#L136-L137`,
`#L1202-L1203`; `py38:...#L128-L129`, `#L1145-L1146`). The check is on the
UTF-8 byte length, `len(arg.encode("utf-8"))` must be 1
(`py44:io/csv/_utils.py#L11-L28`), applied in `read_csv`, `scan_csv`,
`write_csv` and `sink_csv` (`py44:io/csv/functions.py#L306`, `#L1444`,
`py44:dataframe/frame.py#L3223`, `py44:lazyframe/engine.py#L720`;
`py38:io/csv/functions.py#L290`, `#L1364`, `py38:lazyframe/frame.py#L3748`).
The parser stores the separator as one `u8`
(`rs44:polars-io/src/csv/read/options.rs#L60-L71`), and so does the writer
(`rs44:polars-io/src/csv/write/options.rs#L57-L60`).

Status, from maintainers:

> "Polars (for efficiency reasons) does not support multi-byte CSV
> separators." (orlp, #23626, closed as not planned 2025-07-17)

> "This would lead to a very large regression in the csv parsers performance,
> which I don't want for Polars." ... "I will close this as this will not be
> done in polars" ... "Only thing I can foresee supporting is rewriting in
> memory from multichar delimited to single byte delimited and then parse with
> our single byte reader." (ritchie46, #2728, 2022-2023)

> "We don't want to support this." (ritchie46, #18320, 2024-08-24, on mapping
> a too-long separator, quote or eol character to a valid byte)

Observed on polars 1.44.2: `separator="||"` raises `ValueError` ("should be a
single byte character, but is 2 bytes long") in all four functions;
`separator=""` raises (0 bytes); the section sign U+00A7 raises (2 bytes),
although it is one byte, 0xA7, in an ISO-8859-15 file; `separator="\x01"` and
`"\t"` work. A separator in the range 0x80-0xFF cannot be expressed, because
the argument is a `str` measured in UTF-8.

**2d.** "eol_char -- Single byte end of line character (default: `\n`). When
encountering a file with windows line endings (`\r\n`), one can go with the
default `\n`. The extra `\r` will be removed when processed."
(`py44:io/csv/functions.py#L242-L245`, `#L1292-L1295`). In the parser the rule
is wider than line ends: a trailing `\r` is removed from **every unquoted
field** (`rs44:polars-io/src/csv/read/parser.rs#L1134-L1141`,
`rs38:...#L1083-L1090`). Observed on polars 1.44.2: in an LF file the line
`x\r;y\r` reads as `x`, `y`; CR and CRLF inside a quoted field are kept; LF
and CRLF lines may be mixed in one file.

**2e.** `eol_char` is one `u8` in the parser
(`rs44:polars-io/src/csv/read/options.rs#L63`); upstream test with `;` as row
separator: `test44:test_csv.py#L1395`. Observed on polars 1.44.2: a CR-only
file needs `eol_char="\r"`; with the default it is read as a header and zero
rows, with no error.

**2f.** `read_csv` checks the length (`py44:io/csv/functions.py#L308`);
`scan_csv` does not check `eol_char` (`#L1444-L1445` check separator and quote
only), and the binding takes `eol_char.as_bytes().first()`
(`rs44:polars-python/src/lazyframe/general.rs#L207-L212`,
`rs38:...#L198-L203`). Observed on polars 1.44.2:
`read_csv(eol_char="\r\n")` raises `ValueError`; `scan_csv(eol_char="\r\n")`
on a CRLF file returns wrong data with no error (every value of the first
column starts with a line feed, and one extra row appears); a file using `##`
as row separator read with `eol_char="#"` gets an all-null row between
records.

**2g.** "line_terminator -- String used to end each row"
(`py44:dataframe/frame.py#L3131-L3132`); it is a string, not a byte, in the
writer (`rs44:polars-io/src/csv/write/options.rs#L63-L64`, identical file at
1.38.0). Observed on polars 1.44.2: `"\r\n"`, `"\r"`, `"||\n"` and `""` are
all accepted and also end the header line. The writer quotes a string field
only when it contains the separator, LF, CR or the quote character
(`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L516-L538`), so with
`line_terminator="|"` the value `has|pipe` is written unquoted.

---

## 3. Quoting and escaping

| Ref | Capability | Lazy (`scan_csv`, `sink_csv`) | Eager (`read_csv`, `write_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 3a | Quote character: one byte of choice | yes, `quote_char` | yes | - | both tags |
| 3b | No quote handling | read: `quote_char=None`; write: `quote_style="never"` | same | - | both tags |
| 3c | A quote inside a quoted field written as two quotes (RFC 4180) | yes, read and write | yes | - | both tags |
| 3d | An escape character distinct from the quote character, on read | no parameter | no parameter | file must be sanitized first; not planned | both tags |
| 3e | An escape character on write | no parameter | no parameter | pre-escape with string expressions and `quote_style="never"` (stays lazy) | both tags |
| 3f | Quote styles on write: `necessary`, `always`, `non_numeric`, `never` | yes, `quote_style` | yes | - | both tags |
| 3g | Newlines inside quoted fields, read and write | yes | yes | - | both tags |

### Details and sources

**3a / 3b.** "quote_char -- Single byte character used for csv quoting,
default = `"`. Set to None to turn off special handling and escaping of
quotes." (`py44:io/csv/functions.py#L141-L143`, `#L1207-L1209`). Writer:
"quote_char -- Byte to use as quoting character"
(`py44:dataframe/frame.py#L3133-L3134`). Observed on polars 1.44.2:
`quote_char="'"` works; `None` and `""` both disable quoting on read; a
two-character value raises `ValueError`; on write `quote_char=""` raises
`ValueError` (the sink requires exactly one byte,
`py44:lazyframe/engine.py#L721`).

**3c.** A field is treated as quoted only when its **first byte** is the
quote character; inside it each quote toggles the "in quotes" state, so a
doubled quote stays inside the field, and separators and row separators
inside quotes do not end it (`rs44:polars-io/src/csv/read/splitfields.rs#L64-L110`,
identical file at 1.38.0). Unescaping strips the outer quotes and "replace[s]
double quotes by single ones" (`rs44:polars-io/src/csv/read/utils.rs#L115-L146`).
A quoted String field must also end with the quote character, else "Field
... is not properly escaped" (`rs44:polars-io/src/csv/read/builder.rs#L217-L221`).
For Int, Float, Decimal, Boolean and date columns the surrounding quotes are
simply removed before parsing
(`rs44:polars-io/src/csv/read/builder.rs#L140-L142`, `#L348-L352`,
`#L407-L409`, `#L554-L556`). `read_csv` states the scope: "Polars expects CSV
data to strictly conform to RFC 4180, unless documented otherwise. Malformed
data, though common, may lead to undefined behavior."
(`py44:io/csv/functions.py#L107-L108`).

**3d.** There is no escape field in the parse options
(`rs44:polars-io/src/csv/read/options.rs#L60-L71`) and no such parameter in any
of the four signatures. Status:

> "I don't want to support this. Polars aims to support RFC 4180 as csv
> standard. csv files that deviate from this standard need to be sanitized
> first." (ritchie46, #3074, closed 2022-07-08)

Observed on polars 1.44.2: `escape_char=` raises `TypeError` in `scan_csv`,
`read_csv` and `write_csv`. The backslash-escaped field `"say \"hi\""` reads
as `say \hi\` (quotes dropped, backslashes kept) with no error, also with
`ignore_errors=True`; with `quote_char=None` it reads as the raw text
including all quotes and backslashes.

**Odd quotes** (the upstream test notes "the malformed detection logic is
very basic, and fails to detect many types at this point",
`test44:test_csv.py#L2789-L2792`). Observed on polars 1.44.2, default
`quote_char`:
- two quotes inside one unquoted field (`he said "hi"`), or one each in two
  fields of the same row: read literally, no error;
- **one lone quote in an unquoted field** (`1;5" nail;x`): `ComputeError`
  ("CSV malformed: expected 0 rows, actual 2 rows, in chunk starting at
  row_offset 0") from `scan_csv`, and a similar error from `read_csv`; with
  `ignore_errors=True` a warning and the literal text; `select(pl.len())` on
  that file returns 0 with no error; with `quote_char=None` it reads
  correctly;
- text after a closing quote (`"start" and more`): `ComputeError` ("could not
  parse ... as dtype str"; the "not properly escaped" check above);
- an opening quote that never closes swallows the following lines into one
  field and then fails the same way.

**3e.** No parameter (#11393, open since 2023; collaborators there suggest
`str.replace_all` before writing). The writer escapes by doubling only
(`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L454-L484`).

**3f.** `quote_style : {'necessary', 'always', 'non_numeric', 'never'}`
(`py44:dataframe/frame.py#L3163-L3178`; enum at
`rs44:polars-io/src/csv/write/options.rs#L87-L109`; upstream test
`test44:test_csv.py#L2015`). Observed on polars 1.44.2, separator `;` (`\n`
stands for a line feed character):

| Value | `necessary` (default) | `always` | `non_numeric` | `never` |
|---|---|---|---|---|
| `plain` | `plain` | `"plain"` | `"plain"` | `plain` |
| `a;b` | `"a;b"` | `"a;b"` | `"a;b"` | `a;b` |
| `q"q` | `"q""q"` | `"q""q"` | `"q""q"` | `q"q` |
| `nl\nx` | `"nl\nx"` | `"nl\nx"` | `"nl\nx"` | `nl\nx` |
| empty string | `""` | `""` | `""` | (nothing) |
| null string | (nothing) | `""` | (nothing) | (nothing) |
| `pad` with a space on each side | unquoted, spaces kept | quoted, spaces kept | quoted, spaces kept | unquoted, spaces kept |
| Int `1`, Float `1.5` | `1`, `1.5` | `"1"`, `"1.5"` | `1`, `1.5` | `1`, `1.5` |
| Boolean, Date | `true`, `2024-01-15` | quoted | quoted | unquoted |
| header names | quoted when needed | all quoted | all quoted | never |

So null and empty string are distinguishable only under `necessary` and
`non_numeric`.

**3g.** Observed on polars 1.44.2: a quoted field containing LF is one value
in `scan_csv` and `read_csv`, and `select(pl.len())` counts the record once.
`skip_rows` honours the quoted newline, `skip_lines` does not (docstrings at
`py44:io/csv/functions.py#L1210-L1217`; tests `test44:test_csv.py#L1430`,
`#L2549`, `#L2664`). With `quote_char=None` the same file splits into two
rows. On write a value containing LF or CR is quoted
(`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L529`,
`test44:test_csv.py#L1421`).

---

## 4. Nulls and empties

### Reading

Rules, from the field builders (`rs44:polars-io/src/csv/read/builder.rs`; the
file differs between the tags only in the integer-parser call and the date
slow path):

- String: an empty field is null when `missing_is_null` is true, else an
  empty string; a non-empty quoted field is unescaped, so `""` yields a
  zero-length string (`#L199-L233`).
- Every other dtype: quotes are stripped first, then an empty field is null.
  "for types other than string `_missing_is_null` is irrelevant; we always
  append null" (`#L558-L562`; numeric `#L140-L151`, Boolean `#L348-L358`,
  Decimal `#L407-L418`).
- `missing_is_null` defaults to true (`rs44:polars-io/src/csv/read/options.rs#L116`,
  `rs38:...#L104`); Python default `empty_string_is_null=True`: "By default a
  missing string value is considered to be null. If `empty_string_is_null` is
  set to False, missing string values are considered to decoded as empty
  strings." (`py44:io/csv/functions.py#L167-L170`, `#L1235-L1238`).

Observed on polars 1.44.2 (columns: an unquoted empty field, a quoted empty
`""`, a field of two spaces). The first two columns were run through
`scan_csv` and `read_csv` and agree; the third through `scan_csv` only:

| dtype in schema | empty | `""` | two spaces | `empty_string_is_null=False` changes |
|---|---|---|---|---|
| String | null | empty string | two spaces kept | empty -> empty string |
| Categorical | null | empty string | - | nothing |
| Int64 | null | null | null | nothing |
| Float64 | null | null | null | nothing |
| Decimal(10,2) | null | null | null | nothing |
| Boolean | null | null | error | nothing |
| Date | null | null | error | nothing |
| Datetime | null | null | error | nothing |

**The parameter name changed in 1.43.0.** At 1.38.0 the parameter is
`missing_utf8_is_empty_string: bool = False` ("By default a missing value is
considered to be null; if you would prefer missing utf8 values to be treated
as the empty string you can set this param True",
`py38:io/csv/functions.py#L159-L161`, `#L1178-L1180`). At 1.44.2 it is
`empty_string_is_null: bool = True`, and the old name is mapped with `not x`
and a deprecation warning (`py44:io/csv/functions.py#L59-L64`, `#L1122-L1127`;
`rel:py-1.43.0`, #28173; `test44:test_csv.py#L3339`). Observed on polars
1.44.2: `missing_utf8_is_empty_string=True` still works and emits a
`DeprecationWarning` ("the argument `missing_utf8_is_empty_string` for
`scan_csv` is deprecated. It was renamed to `empty_string_is_null` in version
1.43.0."). The 1.38.0 signature has no `empty_string_is_null`
(`py38:io/csv/functions.py#L58-L96`), so by source that keyword is a
`TypeError` on 1.38.0-1.42.x. Default behaviour is the same on both sides of
the rename.

**`null_values`.** "`str`: All values equal to this string will be null.
`List[str]`: All values equal to any string in this list will be null.
`Dict[str, str]`: A dictionary that maps column name to a null value string."
(`py44:io/csv/functions.py#L1227-L1233`). It applies to every dtype, and the
comparison is made **after removing the quotes** of a quoted field
(`rs44:polars-io/src/csv/read/parser.rs#L1148-L1165`, `rs38:...#L1097-L1114`;
upstream test `test44:test_csv.py#L1075` `test_escaped_null_values`). In the
dict form, columns that are not named get the empty string as their null
value (`rs44:polars-io/src/csv/read/options.rs#L427-L434`).

Observed on polars 1.44.2, String column, field texts `(empty)`, `""`, `NaN`,
`"NaN"`, `nan`, `NULL`, two spaces:

| `null_values` | `(empty)` | `""` | `NaN` | `"NaN"` | `nan` | `NULL` |
|---|---|---|---|---|---|---|
| not given | null | empty string | `NaN` | `NaN` | `nan` | `NULL` |
| `"NaN"` | null | empty string | null | null | `nan` | `NULL` |
| `["NaN", "nan", "NAN"]` | null | empty string | null | null | null | `NULL` |
| `""` | null | **null** | `NaN` | `NaN` | `nan` | `NULL` |
| `{"v": "NULL"}` (this column) | null | empty string | `NaN` | `NaN` | `nan` | null |
| `{"k": "zzz"}` (another column) | null | **null** | `NaN` | `NaN` | `nan` | `NULL` |
| `['"NaN"']` (quotes included) | null | empty string | `NaN` | `NaN` | `nan` | `NULL` |

Two spaces stay two spaces in every row. With `empty_string_is_null=False`
plus `null_values=[""]` or a dict naming another column, the pair flips:
the unquoted empty field becomes an empty string and `""` becomes null.

Typed columns, observed on polars 1.44.2: in a Float64 column the texts `NaN`
and `nan` read as float NaN and `inf`, `-inf`, `Infinity` as infinities, not
as null; the text `NULL` is an error unless listed in `null_values` (or
`ignore_errors=True`, which gives null). With the three-NaN list above, `NaN`
and `nan` become null in Float columns as well.

**Whitespace**, observed on polars 1.44.2: String values keep leading and
trailing spaces (also `test44:test_csv.py#L738`).
Int, Float and Decimal accept leading spaces and reject trailing ones (`"7 "`
is `could not parse`); Boolean rejects both; Date accepts leading, Datetime
neither. The numeric rule is in source: leading whitespace is skipped, then
the rest must parse (`rs44:polars-io/src/csv/read/builder.rs#L144-L162`).

**Blank lines** are rows. Upstream tests: `b"a,b\n\nc,d\n"` yields a row of
nulls (`test44:test_csv.py#L714-L735`). Observed on polars 1.44.2: blank lines
after the header, between rows and at the end of the file each produce an
all-null row in both readers and are counted by `select(pl.len())`; a line
holding only separators gives the same row; the filter
`~pl.all_horizontal(pl.all().is_null())` removes them and appears inside the
scan node as `SELECTION` in `explain()`.

### Writing

"null_value -- A string representing null values (defaulting to the empty
string)." (`py44:dataframe/frame.py#L3161-L3162`). For strings under the
default style: "An empty string conflicts with null, so it is necessary to
quote" (`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L516-L527`,
identical file at 1.38.0).

Observed on polars 1.44.2, separator `;`:

| Value | default | `null_value="NULL"` | `quote_style="never"` | `quote_style="always"` |
|---|---|---|---|---|
| null (any dtype) | (nothing) | `NULL` | (nothing) | `""` |
| empty string | `""` | `""` | (nothing) | `""` |
| the string `NULL` | `NULL` | `NULL` (same text as a null) | - | - |
| float NaN, inf, -inf | `NaN`, `inf`, `-inf` | same | same | quoted |
| Boolean | `true` / `false` | same | same | quoted |

Round trip with defaults, observed on polars 1.44.2: `["x", "", None]` writes
as `x`, `""`, (nothing) and reads back as the same three values (also
`test44:test_csv.py#L1045` `test_empty_string_missing_round_trip`); written
with `quote_style="never"` it reads back as `["x", None, None]`. A
single-column null is written as an empty line.

---

## 5. Row limits that stay lazy

| Ref | Capability | Lazy (`scan_csv`) | Eager (`read_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 5a | Header row or none; names supplied by position | yes: `has_header`, `new_columns`, `schema` | yes | - | both tags |
| 5b | Skip leading rows | yes: `skip_rows` (quote-aware), `skip_lines` (raw lines), `skip_rows_after_header`, `comment_prefix` | yes | - | both tags |
| 5c | First n rows | yes: `n_rows`, `.head(n)`, `.slice(o, n)`, pushed into the scan | yes: `n_rows` | - | both tags |
| 5d | Skip footer rows | no parameter. Lazy: count, then `n_rows=count-k` (two passes). One plan: filter a row index against `pl.len()` (holds all rows). | `df.head(-k)` after a full read | eager and one-plan routes hold the whole file in memory | both tags |
| 5e | Last n rows | yes: `.tail(n)`, negative-offset `.slice`; costs a counting pass | `df.tail(n)` | - | both tags |
| 5f | Row index | yes: `row_index_name`, `row_index_offset`, `.with_row_index()` | yes | - | both tags |
| 5g | Count rows | yes: `select(pl.len())`, a dedicated count without field parsing | no fast count | - | wrong results on 1.39.0-1.39.3 and at least 1.40.1 for some plans |

### Details and sources

**5a.** "has_header -- ... If set to False, column names will be autogenerated
in the following format: `column_x`". "schema -- Provide the schema. This
means that polars doesn't do schema inference ... the order of the columns in
the provided `schema` must match the order of the columns in the CSV being
read." "new_columns -- Provide an explicit list of string column names to use"
(`py44:io/csv/functions.py#L1198-L1201`, `#L1218-L1222`, `#L1296-L1299`).
Observed on polars 1.44.2: with a header row present, a `schema` whose keys
are `k` and `v`, and `new_columns=["k", "v"]`, both replace the file's names
by position; a `schema_overrides` key that names no column in the file is
ignored without error (the column keeps its inferred dtype);
`infer_schema=False` makes every column String. At 1.38.0
`scan_csv(new_columns=...)` is implemented by a Python callback over the
column names, and a list-form `schema_overrides` requires it
(`py38:io/csv/functions.py#L1347-L1363`); at 1.44.2 both are handled natively
(`py44:io/csv/functions.py#L1561-L1572`, `#L1587-L1623`; list-form overrides
since `rel:py-1.43.0`, #28226).

**5b.** "skip_rows -- Start reading after `skip_rows` rows. The header will be
parsed at this offset. Note that we respect CSV escaping/comments when
skipping rows. If you want to skip by newline char only, use `skip_lines`."
"skip_lines -- ... Note that CSV escaping will not be respected when skipping
lines." "skip_rows_after_header -- Skip this number of rows when the header is
parsed." (`py44:io/csv/functions.py#L1210-L1217`, `#L1281-L1282`). Observed on
polars 1.44.2: skipped rows are not parsed (a banner line with extra fields is
fine); a banner containing one unbalanced quote makes `skip_rows=1` swallow
the file (`NoDataError: empty CSV`) while `skip_lines=1` works.

**5c.** "n_rows -- Stop reading from CSV file after reading `n_rows`."
(`py44:io/csv/functions.py#L1269-L1270`). The CSV reader accepts a positive
slice from the planner, except when `comment_prefix` is set
(`rs44:polars-stream/src/nodes/io_sources/csv/builder.rs#L42-L50`,
`rs38:polars-stream/src/nodes/io_sources/csv.rs#L53-L61`). Observed on polars
1.44.2: `explain()` shows `SLICE: Positive { offset: 0, len: 3 }` inside the
`Csv SCAN` node for `n_rows=3`, for `.head(3)` and (with offset 2) for
`.slice(2, 3)`; a `filter` between the scan and `head` keeps the slice above
the scan. For `read_csv`: "During multi-threaded parsing, an upper bound of
`n_rows` rows cannot be guaranteed" (`py44:io/csv/functions.py#L200-L203`);
the result is cut to `n_rows` afterwards
(`rs44:polars-io/src/csv/read/read_impl.rs#L536-L545`).

**Rows outside the slice can still be parsed.** The lazy reader skips whole
read chunks that lie before the slice and stops after it, but a chunk that
overlaps the slice is parsed in full and sliced afterwards
(`rs44:polars-stream/src/nodes/io_sources/csv/line_batch_source.rs#L205-L227`,
`rs44:polars-stream/src/nodes/io_sources/csv/chunk_reader.rs#L77-L114`;
`rs38:polars-stream/src/nodes/io_sources/csv.rs#L418-L422`, `#L558-L562`).
Read chunks start at 32 KiB and grow to 512 KiB
(`rs44:polars-io/src/utils/compression.rs#L116-L131`). Observed on polars
1.44.2, schema `{"id": Int64, "name": String}`, last line `TRAILER;10`:
- small file (10 data rows and the trailer): `n_rows=3`, `n_rows=count-1`,
  `.head(count-1)`, `read_csv(n_rows=count-1)` and `read_csv(...).head(-1)`
  all raise `ComputeError` ("could not parse `TRAILER` as dtype `i64` at
  column 'id'");
- 200,000 data rows and the trailer (9.5 MB): `n_rows=100` succeeds;
  `n_rows=total-1`, `n_rows=total-5000` and `.slice(-5, 3)` raise the same
  error. The "current offset in the file" in that message was 379,440 bytes
  for a failure on the last line of the 9.5 MB file, so in `scan_csv` the
  offset is relative to the read chunk;
- reading every column as String and casting after the slice works;
  `ignore_errors=True` works (and nulls any other bad value);
- a footer with more fields than the schema raises "found more fields than
  defined in 'Schema'" under `n_rows`, and passes with
  `truncate_ragged_lines=True`.

**5d.** No footer parameter exists in either signature. Maintainer, on a
request to add one:

> "I doubt we'll do this. This would be very expensive as you'd need a
> lookahead on every line that can determine if that line is a footer (which
> may be invalid)." (ritchie46, #16160, 2024-05-10)

`LazyFrame.slice` rejects a negative length: "negative slice lengths ... are
invalid for LazyFrame" (`py44:lazyframe/frame.py#L7256-L7258`,
`py38:lazyframe/frame.py#L6870`), and `head(n)` is `slice(0, n)`
(`py44:lazyframe/frame.py#L7351`). Observed on polars 1.44.2: `lf.head(-2)`
and `lf.slice(0, -2)` raise `ValueError`; `skip_footer=` and `skip_rows_end=`
are `TypeError`; eager `DataFrame.head(-2)` drops the last two rows. Three
routes work; cost observed on polars 1.44.2 (392 MB, 4 million rows, output
discarded):

| Route | Median s | Peak RSS MB |
|---|---|---|
| no footer handling: `scan_csv(...).sink_csv(...)` | 0.19 | 783 |
| eager: `read_csv`, `head(height-3)`, `write_csv` | 0.17 | 1,094 |
| two passes: `select(pl.len())` (0.011 s), then `scan_csv(n_rows=count-3).sink_csv(...)` | 0.18 | 799 |
| one plan: `with_row_index("i").filter(pl.col("i") < pl.len() - 3).drop("i").sink_csv(...)` | 0.22 | 1,260 |

All three give the same rows. The two-pass route depends on the count (5g)
and on the footer being parseable or excluded (5c).

**5e.** A negative slice is not read natively by the CSV source; the scan
layer first asks the reader for the file's row count and rewrites the slice
as a positive one (`rs44:polars-stream/src/nodes/io_sources/csv/mod.rs#L187-L188`,
`rs44:polars-stream/src/nodes/io_sources/multi_scan/functions/resolve_slice.rs#L43-L57`
and `#L147-L150`; the same function at
`rs38:polars-stream/src/nodes/io_sources/multi_scan/functions/resolve_slice.rs#L41-L55`).
Observed on polars 1.44.2: `.tail(2)` shows `SLICE: Negative {
offset_from_end: 2, len: 2 }` in the scan node and returns the last two rows;
`tail(5)` on the 392 MB file took 0.12 s.

**5f.** "row_index_name -- If not None, this will insert a row index column
with the given name ... row_index_offset -- Offset to start the row index
column" (`py44:io/csv/functions.py#L1283-L1287`). Observed on polars 1.44.2:
both the parameter and `.with_row_index()` directly after the scan appear as
`ROW_INDEX` inside the `Csv SCAN` node; the index counts data rows after
`skip_rows` and the header, from the offset; with `.tail(2)` the index values
are the true positions (10 and 11 of 12).

**5g.** A `select(pl.len())` directly over a CSV scan is replaced by a
`FastCount` that counts rows without building columns, honouring quote
character, comment prefix, row separator, header and the skip parameters
(`rs44:polars-plan/src/plans/optimizer/projection_pushdown/mod.rs#L1630-L1686`,
`rs44:polars-plan/src/plans/functions/count.rs#L28-L83`;
`rs38:polars-plan/src/plans/optimizer/count_star.rs#L151-L172`). At 1.44.2 it
is used only when the scan has no slice and no remaining predicate, and
`POLARS_NO_FAST_FILE_COUNT=1` turns it off
(`rs44:polars-plan/src/plans/optimizer/projection_pushdown/mod.rs#L1634-L1651`).
Version-dependent defects inside the pin:
- 1.39.0-1.39.3: `scan_csv(...).filter(p).select(pl.len())` returns the
  unfiltered count (#27168, labelled regression and P-high, bisected by a
  collaborator to #26688, which is in `rel:py-1.39.0`; fixed by #27190 in
  `rel:py-1.40.0`).
- at least 1.40.1: `scan_csv(...).slice(0, 2).select(pl.len())` returns the
  full count (#27534, reported 2026-05-07; fixed by #27536 in
  `rel:py-1.41.0`). The 1.38.0-1.40.1 rule does not look at the slice at all
  (`rs38:polars-plan/src/plans/optimizer/count_star.rs#L151-L172`), so
  earlier releases may be affected too; see "Could not establish".

Observed on polars 1.44.2: `explain()` shows `FAST COUNT (Csv)` for
`select(pl.len())` on both engines, and an ordinary scan (no fast count) when
a filter, `head` or `n_rows` is present; `scan_csv(n_rows=5).select(pl.len())`
returns 5; the count of the 392 MB file took 0.01 s and of its 59 MB gzip
0.22 s; the count is quote-aware, so one stray quote character changes it
(section 3). `LazyFrame.count()` is a different thing: non-null counts per
column.

---

## 6. Ragged lines

| Ref | Capability | Lazy (`scan_csv`) | Eager (`read_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 6a | Line with more fields than the schema | error by default; `truncate_ragged_lines=True` drops the extra fields | same | - | both tags |
| 6b | Line with fewer fields than the schema | missing fields become null; no parameter raises | same | - | both tags |
| 6c | Value that does not parse as its dtype | error by default; `ignore_errors=True` makes it null and keeps the row | same | - | both tags |

### Details and sources

**6a.** "truncate_ragged_lines -- Truncate lines that are longer than the
schema." (`py44:io/csv/functions.py#L1303-L1304`). The check runs only after
the last projected column of a line, and is switched off whenever fewer
columns are projected than the schema holds: "During projection pushdown we
are not checking other csv fields. This would be very expensive and we don't
care as we only want the projected columns."
(`rs44:polars-io/src/csv/read/parser.rs#L1077-L1083`, `#L1194-L1215`;
`rs38:...#L1026-L1032`, `#L1143-L1164`). Upstream test:
`test44:test_csv.py#L2102`. Observed on polars 1.44.2, file `a;b` / `1;x` /
`2;y;EXTRA` / `3;z` with a two-column schema:
- `scan_csv` and `read_csv`: `ComputeError` ("found more fields than defined
  in 'Schema' ... Consider setting 'truncate_ragged_lines=True'.");
- `truncate_ragged_lines=True`: three rows, `EXTRA` dropped;
- `ignore_errors=True` alone: still raises;
- the same default scan followed by `.select("a")`, `.select("b")` or
  `.select(pl.len())`, and `read_csv(columns=["a"])`: no error.

So in a lazy plan this error depends on which columns the rest of the plan
uses. Related, observed on polars 1.44.2: when `schema=` has fewer columns
than the header row, the read fails with `SchemaError` ("provided schema does
not match number of columns in file (2 != 3 in file)") unless
`truncate_ragged_lines=True`; a trailing separator on every line counts as
one more column.

**6b.** "there can be lines that miss fields (also the comma values) ... We
traverse them to read them as null values"
(`rs44:polars-io/src/csv/read/parser.rs#L1222-L1233`, `rs38:...#L1170-L1181`).
Observed on polars 1.44.2: `2;y` and `3` in a three-column file read as
`(2, "y", null)` and `(3, null, null)` in both readers, with no error or
warning; with `empty_string_is_null=False` the missing String fields are
empty strings. A missing trailing field cannot be told from an empty one
after the read. When `schema=` names more columns than the header, the extra
columns are filled the same way (`test44:test_lazy_csv.py#L409`).

**6c.** "ignore_errors -- Try to keep reading lines if some lines yield
errors." (`py44:io/csv/functions.py#L1239-L1242`). In the builders a failed
parse appends null when `ignore_errors` is set, else raises
(`rs44:polars-io/src/csv/read/builder.rs#L153-L162`). The default error names
the value, dtype, column name and number: "could not parse `{}` as dtype `{}`
at column '{}' (column number {})"
(`rs44:polars-io/src/csv/read/parser.rs#L1166-L1190`). Observed on polars
1.44.2: `oops` in an Int64 column raises by default; with
`ignore_errors=True` the result is `[1, null, 3]`, all rows kept, in both
readers. `ignore_errors` does not cover too-many-fields (6a) or invalid UTF-8
(section 1), and turns a `CSV malformed` error into a warning (section 3).

---

## 7. Number and date text

| Ref | Capability | Lazy (`scan_csv`, `sink_csv`) | Eager (`read_csv`, `write_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 7a | Read numbers with a decimal comma | yes, `decimal_comma=True` | yes | - | both tags |
| 7b | Read numbers with thousands separators | no parameter | no parameter | read as String, strip with string expressions, cast: all lazy | both tags |
| 7c | Write floats with fixed decimals or forced / forbidden exponent | yes: `float_precision`, `float_scientific` | yes | - | both tags |
| 7d | Write numbers with a decimal comma | yes, `decimal_comma=True` | yes | - | both tags |
| 7e | Write numbers with thousands separators | no parameter | no parameter | format to String with expressions first | both tags |
| 7f | Read dates in a layout the reader infers | yes: `Date` / `Datetime` dtype in the schema | yes | - | both tags; inference detail changed in 1.44.0 |
| 7g | Read dates in a stated format | no reader parameter; `str.to_date(fmt)`, `str.to_datetime(fmt)`, `str.strptime` on a String column | same | none: these are lazy expressions | both tags |
| 7h | Write dates in a stated format | yes: `date_format`, `datetime_format`, `time_format`, one each per file | yes | per-column formats: `dt.strftime` before the sink (lazy) | both tags |

### Details and sources

**7a.** "decimal_comma -- Parse floats using a comma as the decimal separator
instead of a period." (`py44:io/csv/functions.py#L251-L252`, `#L1305-L1306`;
`py38:...#L239-L240`, `#L1234-L1235`). For Float columns every comma in the
field is replaced by a period before parsing
(`rs44:polars-io/src/csv/read/builder.rs#L1131-L1144`); Decimal columns get
the flag directly (`#L420`). Tests: `test44:test_csv.py#L2387`, `#L2394`.
Observed on polars 1.44.2 with `decimal_comma=True`:

| Text | Float64 | Decimal(12,2) | Int64 |
|---|---|---|---|
| `1,5` | 1.5 | 1.50 | error |
| `1.5` | 1.5 | error | error |
| `1234,56` | 1234.56 | 1234.56 | error |
| `1.234,56` | error | error | error |
| `1 234,56` | error | error | error |
| `"1,5"` (quoted) | 1.5 | 1.50 | error |

When the field separator is itself `,`, such numbers must be quoted in the
file (observed: works).

**7b.** Parse options contain `decimal_comma` and nothing for grouping
(`rs44:polars-io/src/csv/read/options.rs#L60-L71`). Request #18797 (2024-09)
is open with no maintainer reply. Observed on polars 1.44.2:
`thousands_separator=` and `decimal_separator=` are `TypeError` in
`scan_csv` and `read_csv`; `1,234.56`, `1,234`, `1'234.56`, `1_000` and `1
000` are errors in Float64 and Int64 columns. Reading the column as String
and applying `str.replace_all(".", "", literal=True)`, `str.replace(",", ".",
literal=True)` and `cast(pl.Float64)` gives 1234.56 for `1.234,56` inside the
lazy plan.

**Other number spellings**, observed on polars 1.44.2. Int64: `7`, `+7`,
`007`, `-7` parse; `7.0`, `1e3`, `0x10` and out-of-range values are errors.
Float64: `7`, `.5`, `5.`, `1e3`, `1E3`, `NaN`, `inf` parse; `0x10`, `$5`, `5%`
are errors. Decimal(10,2): `1.5` gives 1.50, `1` gives 1.00, `1e2` gives
100.00, extra digits are rounded (`1.505` gives 1.50, `1.555` gives 1.56), and
a value too large for the precision is an error. Boolean: only `true` /
`false` in any letter case
(`rs44:polars-io/src/csv/read/builder.rs#L353-L364`); `1`, `0`, `yes`, `t`,
`Y` are errors. Dtypes the CSV reader cannot produce raise "unsupported data
type when reading CSV" (`rs44:polars-io/src/csv/read/builder.rs#L694-L696`;
observed for Binary, Duration, List, Null).

**7c / 7d.** "float_scientific -- Whether to use scientific form always
(true), never (false), or automatically (None) for floating-point datatypes.
float_precision -- Number of decimal places to write, applied to both
floating-point data types. decimal_comma -- Use a comma as the decimal
separator instead of a point in standard notation. Floats will be encapsulated
in quotes if necessary; set the field separator to override."
(`py44:dataframe/frame.py#L3151-L3160`). Implementation: the default uses the
`zmij` shortest round-trip formatter; `float_scientific=True` uses Rust's
`{:e}`; `False` uses Rust's plain `{}` on the value as f64; a precision uses
`{:.N}` / `{:.Ne}`; integers go through `itoa`; Decimal keeps its scale
(`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L98-L310`,
`#L331-L345`, identical file at 1.38.0). Tests: `test44:test_csv.py#L1579`,
`#L1589`, `#L2856`. Observed on polars 1.44.2 (Float64 unless noted):

| Value | default | `float_precision=2` | `float_scientific=False` | `float_scientific=True` | `decimal_comma=True`, sep `;` |
|---|---|---|---|---|---|
| 30200.0 | `30200.0` | `30200.00` | `30200` | `3.02e4` | `30200,0` |
| 0.1 + 0.2 | `0.30000000000000004` | `0.30` | `0.30000000000000004` | `3.0000000000000004e-1` | `0,30000000000000004` |
| 1e20 | `1e+20` | `100000000000000000000.00` | `100000000000000000000` | `1e20` | `1e+20` |
| 1e-7 | `1e-7` | `0.00` | `0.0000001` | `1e-7` | `1e-7` |
| 123456789012345680.0 | `1.2345678901234568e+17` | `123456789012345680.00` | `123456789012345680` | `1.2345678901234568e17` | `1,2345678901234568e+17` |
| 1.0 | `1.0` | `1.00` | `1` | `1e0` | `1,0` |

With `float_precision=2`, 0.125, 0.135, 2.675 and 1.005 are written `0.12`,
`0.14`, `2.67`, `1.00` (rounding of the exact binary value). With
`decimal_comma=True` and separator `,`, floats are quoted (`"30200,0"`).
Float32 values 0.1, 30200.0, 1.5 are written `0.1`, `30200.0`, `1.5`. An
Int64 column is written as plain digits (`30200`); the float options do not
reach the integer writer
(`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L98-L108`). A
Decimal(10,2) column keeps its scale (`30200.00`, `1.50`), ignores
`float_precision` (1.55 with `float_precision=1` is still `1.55`) and follows
`decimal_comma` (`1,50`).

**A display setting reaches the file.** Decimal columns are written with
`trim_zeros = get_trim_decimal_zeros()`, the global behind
`pl.Config.set_trim_decimal_zeros`
(`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L332-L340`,
`py44:config.py#L1472-L1511`). Observed on polars 1.44.2: inside
`pl.Config(trim_decimal_zeros=True)` the Decimal values 1.50 and 2.00 are
written `1.5` and `2`; `Config` settings `thousands_separator`,
`decimal_separator` and `float_precision` do not change `write_csv` output.

**7e.** Observed on polars 1.44.2: `write_csv(thousands_separator=...)` is a
`TypeError`.

**7f.** The reader has no date format parameter (observed: `date_format=` is a
`TypeError` in `scan_csv`). For a `Date` or `Datetime` column it infers a
pattern from the first value and then expects it for the column
(`rs44:polars-io/src/csv/read/builder.rs#L453-L537`, `#L546-L579`; 1.44.0
changed how the inferred state is kept, `rel:py-1.44.0` #28663). Observed on
polars 1.44.2, one value per file:

| Text | `pl.Date` | | Text | `pl.Datetime` |
|---|---|---|---|---|
| `2024-01-15` | ok | | `2024-01-15 10:30:00` | ok |
| `15/01/2024` | ok (day first) | | `2024-01-15T10:30:00` | ok |
| `01/15/2024` | error | | `2024-01-15 10:30:00.123` | ok |
| `15-01-2024`, `15.01.2024` | ok | | `...T10:30:00.123456789` | ok, cut to microseconds |
| `2024/01/15`, `2024-1-5` | ok | | `...T10:30:00+02:00` | 08:30:00 (shifted to UTC, no zone kept) |
| `20240115` | error | | `15/01/2024 10:30:00` | ok |
| `15 Jan 2024` | error | | `2024-01-15` | midnight |
| `2024-02-30` | error | | `20240115103000` | error |

A column mixing `15/01/2024` and `2024-01-16` fails at the second layout.
`try_parse_dates=True` applies the same inference when the schema is not given
(`py44:io/csv/functions.py#L1288-L1291`).

**7g.** Observed on polars 1.44.2: on a String column
`pl.col(c).str.to_date("%d/%m/%Y")` and
`pl.col(c).str.to_datetime("%d/%m/%Y %H:%M:%S")` parse inside the lazy plan;
a strict failure raises `InvalidOperationError` ("conversion from `str` to
`date` failed in column 'v' for 1 out of 3 values: ["bad"]"); `strict=False`
gives null. `cast(pl.Date)` from String works for ISO text and warns:
"Casting from String to Date is deprecated and will be removed in Polars 2.0.
Use `str.to_date()` instead" (deprecated in `rel:py-1.42.0`, #28056).

**7h.** "datetime_format / date_format / time_format -- A format string, with
the specifiers defined by the chrono Rust crate"
(`py44:dataframe/frame.py#L3137-L3150`; chrono reference
https://docs.rs/chrono/latest/chrono/format/strftime/index.html). Defaults in
source: Date as ISO; Datetime `%FT%H:%M:%S.%3f`, `.%6f` or `.%9f` according to
each column's time unit, with `%z` added for zone-aware columns; Time
`%T%.9f` (`rs44:polars-io/src/csv/write/write_impl.rs#L63-L130`,
`rs44:polars-io/src/csv/write/write_impl/serializer.rs#L780-L799`; same lines
at 1.38.0). Tests: `test44:test_csv.py#L1472`, `#L1559`. Observed on polars
1.44.2: defaults are `2024-01-15`, `2024-01-15T10:30:00.000000`
(microseconds), `2024-01-15T10:30:00.000` (milliseconds), `...000000+0100`
(zone-aware), `10:30:00.000000000` (Time); `date_format="%d/%m/%Y"` and
`datetime_format="%d/%m/%Y %H:%M:%S"` give `15/01/2024` and
`15/01/2024 10:30:00` for every Date and every Datetime column of the frame;
an invalid format raises `ComputeError` ("cannot format NaiveDate with format
'%Q'");
formatting single columns with `dt.strftime` / `dt.to_string` before the sink
stays lazy. The chrono crate moved from 0.4.41 to 0.4.45 between the tags
(`Cargo.lock` at each tag).

---

## 8. Compression

| Ref | Capability | Lazy (`scan_csv`, `sink_csv`) | Eager (`read_csv`, `write_csv`) | Cost outside the lazy plan | Versions |
|---|---|---|---|---|---|
| 8a | Read gzip, zlib, zstd | yes, detected from the first bytes, decompressed as a stream | yes, decompressed whole into memory | - | both tags |
| 8b | Read zip | no | no | Python `zipfile`, then pass bytes or the member handle: the member is fully in memory | both tags |
| 8c | Read bzip2, xz | no | no | decompress outside Polars | both tags |
| 8d | Write gzip, zstd | yes, `compression=` (unstable) | yes | - | both tags (added in 1.38.0) |
| 8e | Write zip | no | no | compress outside Polars | both tags |

### Details and sources

**8a.** Supported families are GZIP, ZLIB and ZSTD, recognised from the first
four bytes, not from the file name (`rs44:polars-io/src/utils/compression.rs#L10-L38`,
`rs38:...#L13-L35`; feature `decompress = ["flate2/zlib-rs", "zstd"]` in
`rs44:polars-io/Cargo.toml#L96`). The lazy CSV source checks those bytes and
wraps the input in a streaming decompressor
(`rs44:polars-stream/src/nodes/io_sources/csv/mod.rs#L115-L125`, `#L202-L207`,
`#L298`; streaming CSV decompression arrived in `rel:py-1.37.0`, #25842). The
eager reader decompresses the whole input into a buffer first, or only as far
as `n_rows` needs (`rs44:polars-io/src/csv/read/read_impl.rs#L171-L184`,
`rs44:polars-io/src/csv/read/utils.rs#L11-L113`). Upstream tests:
`test44:test_csv.py#L611` (eager), `test44:test_lazy_count_star.py#L235`
(`scan_csv` of a `.gz` file and its fast count; present at 1.38.0 too). The
`read_csv` docstring says "Compressed files are supported when reading from a
path" from 1.41.0 (`py44:io/csv/functions.py#L122`, `rel:py-1.41.0`); the
`scan_csv` docstring does not mention compression at 1.44.2 (documented in
the 2.0 line, `rel:py-2.0.0-rc.2` #29387).

Observed on polars 1.44.2: gzip (with or without a `.gz` name), multi-member
gzip, zlib and zstd files read correctly through both readers, as do gzip
`bytes`; `n_rows`, `tail` and `select(pl.len())` work on a gzip scan. Cost on
the 59 MB gzip of the 392 MB file:

| Read of the gzip file | Median s | Peak RSS MB |
|---|---|---|
| `scan_csv(gz).sink_csv(...)` | 0.25 | 199 |
| `scan_csv(gz).collect()` | 0.25 | 852 |
| `read_csv(gz)` | 0.38 | 1,094 |
| `scan_csv(gz).head(1000).collect()` | 0.00 | 132 |
| `scan_csv(gz).select(pl.len())` | 0.22 | 140 |

**8b / 8c.** No zip, bzip2 or xz crate is in `Cargo.lock` at either tag.
Maintainer on zip (#19447, open):

> "the supported compression formats (gz, zstd, etc) are 1:1 with files, and
> aren't archives like zip's are." ... "It would be cool if Polars could read
> from .zip files directly as if it's part of a path, but it very quickly
> becomes rather hairy ... I'm not sure we're quite ready to support this."
> (orlp, 2026-04-29)

Observed on polars 1.44.2, small files with an explicit schema: a deflated
zip and a bzip2 file each return an **empty frame with no error** from both
readers; a stored (uncompressed) zip and an xz file raise `invalid utf-8
sequence`. `zipfile.ZipFile(p).read(name)` passed as bytes, and
`ZipFile(p).open(name)` or `gzip.open(p)` passed as handles, read correctly
(the handle is drained into memory at the `scan_csv` call, see 1e).

**8d / 8e.** `compression: Literal["uncompressed", "gzip", "zstd"]`,
`compression_level`, `check_extension`, each marked "This functionality is
considered **unstable**" (`py44:dataframe/frame.py#L3072-L3074`,
`#L3104-L3126`; `py38:dataframe/frame.py#L3052-L3054`; added by #26111,
`rel:py-1.38.0`). The enum has no other member and maps to the suffixes `.gz`
and `.zst` (`rs44:polars-io/src/options.rs#L65-L96`, `rs38:...#L65-L96`).
Observed on polars 1.44.2:
- `compression="gzip"` and `"zstd"` work in `write_csv` and `sink_csv`; the
  gzip output is readable by Python's `gzip`; `"zip"` and `"bz2"` raise
  `InvalidOperationError: Invalid compression format`;
- `check_extension` (default true) raises when gzip is written to a path not
  ending `.gz`, **and when an uncompressed file is written to a path ending
  `.gz`, `.zst` or `.zstd`**; `check_extension=False` allows both;
- `write_csv(None, compression="gzip")` raises `UnicodeDecodeError` (the
  string return path decodes the output as UTF-8);
- cost, 392 MB of CSV to the null device: uncompressed 0.19 s, zstd 0.46 s,
  gzip 1.73 s.

---

## 9. Adjacent facts the config keys need

Not among the eight sub-questions, but named by the v1 keys (`append`,
`split`, `remove_empty_row`, `create_directory`) and by finding 20.

| Ref | Capability | Lazy (`scan_csv`, `sink_csv`) | Eager (`read_csv`, `write_csv`) | Versions |
|---|---|---|---|---|
| 9a | Append to an existing file | no parameter; pass a binary file object opened in append mode, with `include_header=False` | same | both tags |
| 9b | Split output every N rows | `sink_csv(pl.PartitionBy(base, max_rows_per_file=N))` (unstable) | `write_csv` accepted the same object (observed) | both tags |
| 9c | Create missing parent directories | `sink_csv(mkdir=True)` (unstable) | no parameter | both tags |
| 9d | Drop blank lines | no parameter; a filter, which is pushed into the scan | same filter after the read | both tags |
| 9e | Read whole lines as one column | `pl.scan_lines` (unstable) | `pl.read_lines` (unstable) | 1.38.0 on |
| 9f | Empty input | `raise_if_empty` | same | both tags |

**9a.** Neither signature has an append or mode parameter. Upstream test
writing through an already-open handle: `test44:test_csv.py#L2497`. On Unix an
exact `BufferedWriter` is written through its duplicated file descriptor,
whose position and flags are shared (`rs44:polars-python/src/file.rs#L323-L373`).
Observed on polars 1.44.2: `mode=` and `append=` are `TypeError`;
`df.write_csv(open(p, "ab"), include_header=False)` and the same call on
`lf.sink_csv` append the rows; writing to a path replaces the file.

**9b.** `PartitionBy(base_path, *, file_path_provider, key, include_key,
max_rows_per_file, approximate_bytes_per_file)`: "max_rows_per_file -- Maximum
number of rows to write for each file. Note that files may have less than this
amount of rows." Marked unstable (`py44:io/partition.py#L31-L134`; same public
parameters at `py38:io/partition.py#L27-L130`; user guide
https://docs.pola.rs/user-guide/lazy/sources_sinks/). Observed on polars
1.44.2: 10 rows with `max_rows_per_file=4` produce `00000000.csv` (4 rows),
`00000001.csv` (4), `00000002.csv` (2) under the base path, each with a
header (none with `include_header=False`), in row order; the base directory,
nested or not, is created without `mkdir=True`; zero rows produce one
header-only file; a second sink of fewer rows into the same directory
overwrites `00000000.csv` and leaves the older `00000001.csv` and
`00000002.csv` in place; a `file_path_provider` callable is called once per
file with `index_in_partition` 0, 1, 2 and decides the file name;
constructing `PartitionBy` emits `UnstableWarning` only when unstable
warnings are switched on.

**9c.** "mkdir -- Recursively create all the directories in the path."
(unstable, `py44:lazyframe/frame.py#L3908-L3913`). Observed on polars 1.44.2:
`sink_csv` and `write_csv` to a file path in a missing directory raise
`FileNotFoundError`; `sink_csv(mkdir=True)` creates it. (A partitioned sink
creates its base directory by itself, see 9b.)

**9d.** See "Blank lines" in section 4.

**9e.** `scan_lines(source, *, name, n_rows, row_index_name, row_index_offset,
...)`: "Construct a LazyFrame which scans lines into a string column from a
file", unstable, no encoding or separator parameters
(`py44:io/lines.py#L128-L239`; added in `rel:py-1.38.0`, #26112). Observed on
polars 1.44.2: every line is returned verbatim, an empty line as an empty
string, CRLF endings removed, `row_index_name` and `.tail` work.

**9f.** "raise_if_empty -- When there is no data in the source, `NoDataError`
is raised. If this parameter is set to False, an empty LazyFrame (with no
columns) is returned instead." (`py44:io/csv/functions.py#L1300-L1302`).
Observed on polars 1.44.2: a zero-byte file raises `NoDataError: empty CSV`;
with `raise_if_empty=False` and a `schema` the result has zero rows and the
schema's columns; a header-only file gives zero rows. A missing file is
reported at `collect()`, not at `scan_csv()`. On write, zero rows produce the
header line only, or an empty file with `include_header=False`. Object, List,
Struct and Binary columns cannot be written (`ComputeError`, observed).

---

## Findings 19 and 20 of the as-found report, explained

The findings are from `.scratch/engine-v2/research/2026-10-05-v2-as-found.md`;
the v2 line numbers below are at commit `33a13269` on `feature/engine-v2`.

**Finding 19** ("an empty field becomes null while `""` becomes an empty
string; the text `NaN` or `nan` in a string column becomes null").
- Empty field -> null: the String builder pushes null for a zero-length field
  when `missing_is_null` is true, the default
  (`rs44:polars-io/src/csv/read/builder.rs#L207-L214`,
  `rs44:polars-io/src/csv/read/options.rs#L116`).
- `""` -> empty string: the field is two bytes long, so it is not "missing";
  it is unescaped to a zero-length value
  (`rs44:polars-io/src/csv/read/builder.rs#L217-L233`,
  `rs44:polars-io/src/csv/read/utils.rs#L125-L146`).
- `NaN` -> null: v2 passes `null_values=["NaN", "nan", "NAN"]`
  (`src/v2/components/file/file_input_delimited.py` lines 341-344), and a
  list of null values applies to every column including String
  (`py44:io/csv/functions.py#L1227-L1233`,
  `rs44:polars-io/src/csv/read/parser.rs#L1148-L1165`). Without that argument
  the text stays `NaN` (section 4 table).
- Stable across the pin: these code paths are the same at both tags.

**Finding 20** ("`file_input_full_row` fails on a line that starts with a
quoted segment"). The component calls
`scan_csv(separator="\x00", has_header=False, ...)` and leaves `quote_char`
at its default `"` (`src/v2/components/file/file_input_full_row.py` lines
74-81). A field whose first byte is the quote character is treated as quoted
(`rs44:polars-io/src/csv/read/splitfields.rs#L70-L71`), and a quoted String
field must end with the quote character or the read fails with "Field ... is
not properly escaped" (`rs44:polars-io/src/csv/read/builder.rs#L217-L221`).
The line `"quoted start" and more` starts with a quote and ends with `e`.
Observed on polars 1.44.2: the same call raises `ComputeError` ("could not
parse `"quoted start" and more` as dtype `str` at column 'column_1'"); with
`quote_char=None` all lines are returned (an empty line as null);
`pl.scan_lines` returns all lines (an empty line as an empty string).

---

## Cost observations: set-up and full table

Observed on polars 1.44.2 only, on one machine, and provisional: Apple
arm64, 10 cores (4 performance, 6 efficiency), 16 GB, macOS 26.6, Python
3.14.6. Data: 4,000,000 rows x 8 columns (three Int64, one Float64, four
String; two String columns carry accented letters in most rows and one a
euro sign in every row), 391.9 MB as UTF-8, 377.5 MB as ISO-8859-15, 59.3 MB
as gzip. Explicit schema in every read. Each case ran five times in a fresh
process;
the table gives the median wall time and the largest peak RSS (`ru_maxrss`).
Inputs were warm in the page cache. Outputs went to the null device, because
writing the same 392 MB file to this machine's disk took between 0.25 s and
3 s from run to run. Peak RSS includes the pages of the memory-mapped input
for uncompressed local files, so "streaming" rows still show about the file
size; the gzip rows show the working memory without that effect. All times
are below two seconds: read the ratios, not the absolute values.

| Case | Median s | Peak RSS MB |
|---|---|---|
| Python start and `import polars` | 0.00 | 56 |
| `scan_csv(utf8).collect()` | 0.17 | 1,246 |
| `read_csv(utf8)` | 0.10 | 1,085 |
| `read_csv(latin, encoding="iso-8859-15")` | 0.56 | 2,181 |
| `read_csv(latin, encoding="utf8-lossy")` | 0.17 | 1,076 |
| `scan_csv(latin, encoding="utf8-lossy").collect()` | 0.23 | 1,235 |
| `scan_csv(utf8).sink_csv(null)` | 0.19 | 783 |
| `scan_csv(latin, encoding="utf8-lossy").sink_csv(null)` | 0.26 | 780 |
| `read_csv(latin, encoding="iso-8859-15")` then `write_csv(null)` | 0.55 | 2,252 |
| `sink_csv` to a Python object that copies bytes | 0.18 | 799 |
| `sink_csv` to a Python object that re-encodes to ISO-8859-15 | 0.97 | 776 |
| `read_csv`, `write_csv(None)`, `str.encode("utf-8")` | 0.55 | 2,269 |
| `read_csv`, `write_csv(None)`, `str.encode("iso-8859-15")` | 1.20 | 2,255 |
| Python only: stream transcode ISO-8859-15 to UTF-8 | 0.27 | 61 |
| Python only: stream transcode UTF-8 to ISO-8859-15 | 0.94 | 62 |
| Python only: whole-file decode and re-encode | 0.36 | 1,581 |
| whole-file decode in Python, `scan_csv(bytes).collect()` | 0.48 | 2,382 |
| `select(pl.len())` | 0.01 | 459 |
| `tail(5).collect()` | 0.12 | 473 |
| footer, eager (`read_csv`, `head`, `write_csv`) | 0.17 | 1,094 |
| footer, two passes (count, `n_rows`, `sink_csv`) | 0.18 | 799 |
| footer, one plan (row index filter against `pl.len()`) | 0.22 | 1,260 |
| `scan_csv(gz).collect()` | 0.25 | 852 |
| `read_csv(gz)` | 0.38 | 1,094 |
| `scan_csv(gz).sink_csv(null)` | 0.25 | 199 |
| `scan_csv(gz).head(1000).collect()` | 0.00 | 132 |
| `scan_csv(gz).select(pl.len())` | 0.22 | 140 |
| Python only: `gzip.open(gz).read()` | 0.20 | 881 |
| `sink_csv(null, compression="gzip")` | 1.73 | 753 |
| `sink_csv(null, compression="zstd")` | 0.46 | 705 |

A second run of nine of these cases reproduced the ordering; individual
medians moved by up to 0.11 s (for example `read_csv` with the codec 0.45 s,
native sink 0.15 s).

---

## Docs versus code

Places where a primary source says one thing and the code at the same tag
does another. Code and tests are taken as the fact; both are cited above.

1. A comment in `read_csv` says "`scan_csv` does not support compressed
   files" (`py44:io/csv/functions.py#L526-L527`, also at 1.38.0). The lazy
   source decompresses, and upstream tests scan a `.gz` file at both tags.
2. The Rust doc comment on `with_null_values` says null values "are matched
   before quote-parsing, so if the null values are quoted then those quotes
   also need to be included" (`rs44:polars-io/src/csv/read/options.rs#L316-L317`).
   The parser strips the quotes before comparing, and a test relies on it.
3. The `scan_csv` docstring calls `eol_char` a "Single byte end of line
   character", but only `read_csv` enforces it (section 2, 2f).
4. The `datetime_format` docstring says the default precision "is inferred
   from the maximum timeunit found in the frame's Datetime cols"
   (`py44:dataframe/frame.py#L3137-L3142`). The writer picks the default per
   column from that column's own unit (section 7, 7h).
5. The `truncate_ragged_lines` docstring does not say that the check is off
   whenever a projection drops a column (section 6, 6a).
6. The `rechunk` deprecation is dated 1.43.2 in docstrings and listed under
   1.44.0 in the release notes.

---

## Could not establish

- **Behaviour on the releases between the two tags, and on 1.38.0 itself, was
  read from source and release notes, not run.** Nothing here was executed on
  any version but 1.44.2.
- **Which releases return a wrong `select(pl.len())` for a sliced CSV scan.**
  The report (#27534) is against 1.40.1 and the fix is in 1.41.0. The rule in
  1.38.0-1.40.1 ignores the slice in source, which suggests 1.38.0-1.40.1 are
  all affected for `n_rows`, `head` and `slice`, but no source states the
  first affected release and it was not run.
- **Whether a write chunk handed to a Python `write()` can end inside a
  multi-byte UTF-8 character on 1.44.2.** A maintainer says it "might"
  (#10326, 2023). The probe used an incremental decoder and did not test for
  split characters.
- **Performance and memory on the target RHEL servers.** All timings are from
  one Mac with a warm page cache and output discarded; no measurement was
  made with a cold cache, a network file system, or more data than memory.
- **Any future support for other encodings.** Maintainers have called it out
  of scope (2024, 2026); the open requests (#25423, #28705, #11476, #28803)
  have no maintainer reply, and nothing was found about plans for 2.x.
- **Whether default float and date text is byte-identical across the pin.**
  The writer source is identical at both tags, but the formatting crates
  moved (`zmij` 1.0.12 to 1.0.23, `chrono` 0.4.41 to 0.4.45, per `Cargo.lock`);
  no changelog of those crates was read and no other version was run.
- **Whether the eager and lazy readers differ on any field-level result.**
  They share the parsing code and agreed on every probe run here, but they
  were not compared exhaustively. Known differences are outside the fields:
  the `encoding` values accepted, `eol_char` validation, and decompression.
  Whether the byte offset in `read_csv` parse errors is file-relative was not
  checked.
- **Semantics of the unstable `missing_columns` parameter.** In one probe
  (`schema` with one column more than the header) `missing_columns="raise"`
  did not raise; not investigated.
- **Reading the `Time` dtype.** `10:30:00` in a `pl.Time` column failed with
  "could not find an appropriate format to parse times"; not investigated,
  since neither v1 nor v2 lists a time type.
- **Decimal parsing rules** beyond the few values in section 7 (rounding
  mode, limits). That belongs to ticket 03.
- **Linux and Windows specifics.** Observations are from macOS; the native
  file-descriptor path for Python file objects is Unix-only in source.
