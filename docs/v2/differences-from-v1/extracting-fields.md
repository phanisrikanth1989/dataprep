# Extracting fields

The components that cut one column of text into several.

Where v2 differs from v1, each on purpose. v1 is the answer key for
everything else these components do. ([The other pages](README.md).)

## Extract delimited fields

- A missing value in a Decimal source column is a missing source: the
  row is left out, or leaves by the reject output. v1 holds a missing
  Decimal as empty text and hands the row on with nothing in its pieces.
  (The same holds for the other three extract components below.)
- A date in an output column is read by the column's pattern. v1 reads
  one written another usual way when no date of the column is written by
  the pattern.
- Where a column that may not be missing is missing and the job is not to
  die, the row leaves by the reject output with the engine's
  `SCHEMA_VIOLATION`, and the reject output then has the extracted
  columns too; v1's has the output's columns.
- The separator is taken as it is written, as in v1 (and as normalize
  takes its own). Talend reads it as a pattern: a job that separates at
  `|` or `.` there has it written `\\|`, which is to be written `|` here.
- A piece is read as its column's declared type the way every transform's
  output is: what cannot be read goes missing, an empty piece too. v1
  writes text through in a Decimal column, takes any text for true (the
  word `false` as well) and an empty piece for false, and writes `7.0`
  for a whole number beside a missing one.
- A date in the source column is split as the text its pattern writes. v1
  splits Python's text for it (`2024-01-31 00:00:00`).
- A source column that is not there refuses the job. v1 fails when the
  rows arrive.
- `die_on_error` is off when the job does not say: v1's own default for
  the number of pieces. v1's engine takes it for on when it looks at the
  columns that may not be missing; the converter always writes the key.
- Where no row is turned away, the file behind the reject output has its
  header line. v1 leaves that file with nothing in it.
- A wrong number of pieces that fails the job names the row.
- Not acted on, as in v1: `advanced_separator` (v1 looks for Talend type
  names its schemas never hold), `check_date`.

## Extract positional fields

- A piece is read as its column's declared type the way every transform's
  output is, as for extract delimited fields above.
- A `field` that names no column refuses the job. v1 cuts the first
  column in its place, with a warning. (With no `field` at all, both cut
  the first column.)
- A `pattern` that is no list of widths refuses the job before it runs.
  v1 fails when the rows arrive, and takes a pattern of commas alone for
  no width at all.
- With no output columns declared, a column is made for every width,
  `field_1` and so on, as in v1.
- A date in the source column is cut as the text its pattern writes; v1
  cuts Python's text for it.
- `die_on_error` is off when the job does not say, and the reject file
  has its header line where no row is turned away: both as for extract
  delimited fields.
- A text that is too short and fails the job names the row.
- Not read, as in v1: `formats`, `advanced_option`, `advanced_separator`.

## Extract regex fields

- The pattern is Python's, as in v1, as far as Polars can look for it. A
  pattern Polars does not take refuses the job, with Polars' own words
  for why: lookaround, a backreference, `\Z`, `(?a)`, a `{` that opens no
  count, `{,2}`, `\N{...}`, an octal escape, `(?#...)`, `(?>...)`, a
  conditional group, and a counted `\w` of some 250 or more.
- What both take and read differently refuses the job as well: a `[`
  inside `[...]` (`[[:alpha:]]` among them), `&&`, `--` and `~~` inside
  `[...]`, and `\<` and `\>`.
- Not refused, and not the same: `\w` and `\b` follow Unicode's own word
  characters in Polars (a combining accent and `‿` are of a word, `²` and
  `½` are not), where Python has its own list; `(?i)` does not pair the
  Turkish `İ` and `ı` with `i`; a group repeated around something that
  can be empty (`((a*)*)`) holds what its last turn held. `$` is the end
  of the text; in v1 it is also the place before a line break the text
  ends on.
- A date in the source column is looked in as the text its pattern
  writes; v1 looks in Python's text for it.
- A pattern that is none, and a `field` that names no column, refuse the
  job before it runs. v1 fails when the rows arrive, and with
  `die_on_error` off looks in the first column for a `field` it does not
  find.
- What a group holds is read as its column's declared type the way every
  transform's output is, as for extract delimited fields above.
- A text the pattern is not found in is said the way Python shows a text
  (`'bob'`), as in v1; a character Python would write as an escape other
  than a line break, a tab or a backslash is written as it is.
- A failure names the row. The reject file has its header line where no
  row is turned away.

## Extract JSON fields

- Paths are JSONPath (`read_by` JSONPATH). `read_by` XPATH refuses the
  job: v1 tries an XPath as a JSONPath, which it is not, and writes rows
  with nothing in them. The converter's own sample is written that way.
- A path that cannot be read, a loop path too, refuses the job. v1 fills
  nothing for the first and reads the whole document for the second,
  with a warning each.
- A `jsonfield` that names no column refuses the job. v1 reads the first
  column in its place.
- A value is read as its column's declared type as for rows written in a
  job config: true and false from words and numbers; a date by its
  column's pattern or one of the usual ways (`2024-01-31`, with a time
  after a blank or a `T`, or `31/01/2024`), where v1 reads the usual ways
  only when no date of the column is written by the pattern; a moment
  with an offset (`...Z`) or, in a column with no pattern, a fraction of a
  second, goes missing. A number with a fraction in a whole-number column
  is cut, as everywhere; v1 writes `2.0` and `1.7` through there.
- Also not as v1: a whole number of 2^63 or more in a whole-number column
  and one beyond 38 digits in a Decimal column go missing (v1 writes
  them); `true` in a float or Decimal column goes missing (v1 `1.0`); a
  number in a date column goes missing (v1 a moment in 1970); `1` beside
  a missing value in a text column is `1` (v1 `1.0`).
- A column of the mapping that the output does not declare is not
  written (v1 writes it as one column more), and the output columns have
  to be declared (v1 writes the mapping's). A column the output declares
  not nullable and the mapping does not fill turns every row away
  (`SCHEMA_VIOLATION`); v1 writes it empty.
- An entry of the mapping with no column, an empty mapping and a key v2
  does not know in an entry refuse the job; v1 passes over them.
- A failure names the row the document came from, and so does the trace
  for every item of it.
- Where no row is turned away, the file behind the reject output has its
  header line. v1 leaves that file with nothing in it.
- A document is read out of every row in Python: the rows are held in
  memory, as in v1.
