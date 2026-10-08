# 05 - The performance bar

Status: resolved
Type: grilling

## Question

When is a config key too slow to support? The rule is "refused if Polars
cannot do it natively, or only with a large slowdown". It needs a test that
anyone can apply to a v1 capability and reach the same verdict, because every
key-by-key ticket applies it dozens of times.

To settle:

- What "native" means. No Python callback is clear. May a supported key force
  an eager read or an extra collect? v2 as found reads the whole file eagerly
  when `footer_rows` is set, and collects at the source when `die_on_error`
  is false.
- What "large slowdown" means, and against what. The existing gate compares a
  component with hand-written Polars doing the same thing (within 10%), which
  any native implementation passes by construction. Is the baseline the same
  job without the key? A fixed budget per key? Memory as well as time?
- Who pays: a cost only when the key is used, versus a cost on every job
  because the key exists at all.
- How a verdict is measured and recorded so it can be reproduced: data size,
  machine, harness, and whether the measurement is stored with the declared
  key.
- Worked verdicts for a few known hard cases, to calibrate the bar: footer
  rows; a non-UTF-8 encoding; `die_on_error: false` at a source;
  case-insensitive unique keys; Map lookups that keep all matches.

Use the two Polars facts tickets
([delimited files](02-polars-facts-delimited-files.md),
[collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md))
where they are resolved; this ticket does not wait for them.

## Answer

Resolved 2026-10-05 in conversation with the driving dev. The question asked
for a test anyone could apply. The answer is that there is no such test.

1. No blanket test. A config key is not dropped because it makes a job
   slower. A product without the keys people need is not used.
2. Performance decides how a key is built, not whether it exists. v2 does it
   the fastest way Polars allows, and only jobs that use the key pay.
   `file_input_delimited` as found already works this way: it reads the file
   fully only when `footer_rows` is above 0 or `die_on_error` is false, and
   stays lazy otherwise.
3. Whether a key stays is decided key by key in each component's ticket,
   weighing what users need against what it costs. A refusal is made there,
   with a reason.
4. Footer rows is needed and stays.

The dev's words: "just because things will become slow doesn't mean you
completely drop some of the configurations", and "let's go to the real
component-level configurations and then try to focus there on individual
cases".

### What was tried and dropped

The session first drafted a blanket test: a key is supported only when Polars
does it inside the job's one lazy plan, it costs nothing to jobs that do not
use it, and it does not make a job hold the whole file in memory. Applied to
this ticket's own hard cases, that test refused footer rows, which users
need. The draft is withdrawn in full. The answers given to its questions were
given in the abstract and are not decisions; anything in them worth keeping
is decided again on a real key.

### Evidence for the component tickets

The hard cases were measured before the draft was dropped, and the figures
below stay as input. The scripts that produce them, and the fuller tables
behind them, are in `../research/probes/` (`probe_performance_bar*.py`); no
output is kept in the repo.

How they were taken: one Mac (Apple M4, 10 cores, 16 GB), polars 1.44.2,
files already in the OS cache, so all of it is provisional for the target
servers. The file is 2,000,000 rows of 10 columns, 231 MB, with a
10,000,000-row copy of 1.16 GB. Times are the median of 5 runs on the
in-memory engine, against the same job without the key; each pair of figures
is a job that uses every column and a job that keeps a tenth of the rows and
three columns. Memory is one run, file to file, read as macOS "peak memory
footprint".

- Scale. v1 reads the 231 MB test file in 12.4 s (38 s with 0.2% bad rows);
  v2's plain lazy read takes 0.08 s. Every v2 route measured, the slow ones
  included, was at least 40 times faster than v1.
- Footer rows. The eager read as found is no slower than a lazy scan (0.76x
  to 0.97x) but holds the file in memory. Counting the rows first and then
  scanning with a row limit costs 1.07x to 1.15x and memory stays flat. A
  position filter inside the plan costs 1.02x to 1.08x and holds the file.
  Two other routes inside the plan held 1 to 3.8 times the file. Counting
  first was the only route tried that kept memory flat.
- ISO-8859-15. Polars' only route decodes in Python: 3.1x to 4.4x the time
  and 7 to 8 times the file in memory. Checking the bytes are ASCII first and
  then scanning lazily costs 1.3x to 1.5x.
- `die_on_error: false` at a source. As found: 1.4x to 2.3x on a clean file
  and 12x to 19x with 0.2% bad rows. The same split built from lazy
  expressions: 1.2x to 2.1x, with flat memory.
- Case-insensitive unique keys: 0.93x to 1.08x. All matches in a lookup:
  3.4x a one-match join, for 28% more rows. Keeping v1's row order through
  unique, aggregate and join: 1.10x to 1.34x in memory and nothing
  measurable when streaming.
- Memory, file to file. A job that streams peaked at 0.5 to 1 GB at both
  sizes measured (231 MB and 1.16 GB). A job that holds the file needs about
  2 times the file, a sort about 3 times.

Could not establish: anything on the target servers or on another Polars
version; anything above 1.16 GB (figures quoted for 30 to 100 GB files are
straight-line extensions); what a second read of the input costs on a cold
or network disk.

### Surfaced for other tickets

- [Config keys, key by key: delimited file input](20-config-keys-delimited-file-input.md).
  Footer rows stays. The dev expects the component as found to need very
  little change, because it was designed around these cases. Three defects in
  it: with
  `die_on_error: false`, reject messages are built in a Python loop (the 12x
  to 19x above); with `die_on_error: false`, a Boolean column stops the read
  (`casting from Utf8View to Boolean not supported`); a trailer line that
  does not fit the schema stops the read when `die_on_error` is true and
  works when it is false. v1's default for `die_on_error` at a file input is
  false (27 of the 31 fixture inputs), so an unedited v1 job config takes the
  read-fully path.
- [Encoding: what to do about ISO-8859-15](14-encoding-iso-8859-15.md): the
  costs above.
- [Barriers, collection and row counts](09-barriers-collection-and-row-counts.md):
  the memory figures, and the dev's file sizes and server memory, now in the
  map's Notes. Also for that ticket: a file input that reads the file fully
  for `footer_rows` or `die_on_error: false` sits against the map's rule
  that components never collect, so it has to say what such a source is.
- [Types, nulls and schemas](13-types-nulls-and-schemas.md): Polars has no
  String-to-Boolean cast (1.44.2). v1's FileInputDelimited takes
  `date_pattern` as a strftime pattern: given `yyyy-MM-dd` it sent every row
  to reject, and it parsed with `%Y-%m-%d`.
- [Config keys, key by key: sort row and unique row](23-config-keys-sort-row-and-unique-row.md):
  when streaming, `unique(keep="any")` with no order held 3.4 times the file,
  where `keep="first"` with order kept stayed flat.
- The build's benchmark ("within 10% of hand-written Polars"): on this Mac an
  eager `read_csv` beat `scan_csv().collect()` (58 ms against 77 ms). The
  hand-written side has to read the same way the component does, or a lazy
  source fails the check.
