# Sources and outputs

The components a flow starts from or ends in: the files read and written,
and the sources that make their rows themselves.

Where v2 differs from v1, each on purpose. v1 is the answer key for
everything else these components do. ([The other pages](README.md).)

## Delimited files

- A blank line is never a row and does not count toward `limit`, as in v1.
  The exception is a file read with `row_separator` `\r`: there a blank
  line is a row of empty fields, kept when `remove_empty_row` is off and
  counted toward `limit`.
- With `csv_option`, an enclosure character must open and close a field.
  v1 also reads a file where one does not (an inch mark inside a field that
  is not enclosed, a field that opens an enclosure and never closes it), the
  lenient way Python's csv reader does. v2 fails the reader and says why; it
  never goes on with part of the rows. Reading such files is not built yet.
- With `csv_option`, a separator of more than one byte (a broken bar or a
  section sign, say) is refused at load, on read and on write.
- A row with more fields than the schema has its extra fields dropped. v1
  does that only when the first row is the longest and fails the read
  otherwise.
- `check_fields_num` rejects exactly the rows whose field count is not the
  schema's. v1's check also rejects rows whose last field is empty and
  misses short rows in some setups.
- Rejected rows carry v1's `errorCode` and `errorMessage`. The message for
  a date that cannot be read always names the pattern; v1's wording varies
  with the Python version.
- A row separator other than `\n`, `\r\n` or `\r` on read, and `split` on
  write, are refused for now.
- A file name is one file. Polars would read `*`, `?` and `[` in it as a
  pattern; v2 does not let it.

## Positional input

- A value that cannot be read rejects its row (or fails the component with
  `die_on_error`), as in the delimited reader. In v1 one such value makes
  the whole file come back with no rows, and a date that cannot be read
  goes missing silently.
- Text is kept as it is. v1 blanks every character outside printable ASCII,
  accents included, and empties the texts `NA`, `N/A`, `null`, `NaN`,
  `None`.
- `bool` reads true/1/yes and false/0/no. v1 reads any text as true.
- `limit` counts rows after blank lines are dropped, and works together
  with `footer_rows`.
- `*` as the last width takes the rest of the line (v1 refuses it).
- Kept as v1 has it: blanks around a field are stripped and blank rows
  dropped whatever `trim_all` and `remove_empty_row` say.

## Full-row input

- `random` (lines picked at random) is refused: the rows would differ from
  one run to the next.
- A row separator other than `\n`, `\r\n` or `\r` is refused.
- Kept as v1 has it: what follows the last line end counts as one more,
  empty line, so `footer_rows: 1` on a file ending in a newline removes
  nothing real.

## Excel input

- Read with fastexcel (calamine), about four times as fast as v1 on a
  60,000-row workbook. `.xls` is covered only for numbers and text.
- A sheet or column range narrower than the schema gives missing columns
  (v1 reads nothing from the sheet). `first_column` 0, which the converter
  itself writes, is read as 1 (v1 refuses it).
- Dates are read cell by cell with the declared pattern; whole-number
  columns stay whole.
- With `all_sheets` and a `sheetlist`, sheets are read in workbook order
  (v1: an order that changes between runs).
- Kept as v1 has it: a `sheetname` that is not in the workbook reads the
  first sheet; in a text column a date cell is written `dd-mm-yyyy` and a
  boolean `1`/`0`; cells that cannot be read go missing and are never
  rejected.

## JSON input

- One rule per value. v1 lets pandas pick one type for a column, so a whole
  number beside a fraction or a missing value comes out as `1.0`, in a text
  column too. v2 writes `1`.
- A path that is not a JSONPath refuses the job. v1 runs, rejects every
  record with "Parse error" and writes no row.
- A record a path cannot be followed on (the first item asked of a number,
  say) is turned away as in v1: it is left out of the main output and goes
  to the reject output with `PARSE_ERROR` and what the library said,
  whatever `die_on_error` says. v2's reject output has every column, empty
  from the path that failed on; v1's has only the columns read before that
  path, so its columns change with the data.
- The document is read whole and gone through in Python, record by record:
  a JSONPath can ask for any part of it, so Polars cannot scan it. It is the
  one reader that takes memory and time by the size of its file.
- Reading from a URL (`useurl`) is refused: v2 reads files.
- A `schema` inside the config, v1's older way of typing values, is
  refused; with it go `advanced_separator`, `check_date` and their keys,
  which v1 reads only then.
- As everywhere, a wired reject flow that gets no rows is written empty; v1
  stalls.

## Properties input

Here v2 follows Talend and not v1. Talend's component has a schema a job
cannot change, `key` and `value` (and `section` for an ini file read
whole), and hands on a row for every property. v1 hands on one row and
fills each column from the property of that name, which on the schema of
every converted job is a row of nothing.

- A job whose reader declares only `key`, `value` and `section` gets
  Talend's rows. One that declares other columns gets v1's one row, as a
  job written for v1 expects (and v1's one row for each section of an ini
  file read whole, with its name in `__section__`).
- A properties file is read as Java reads one: `\t`, `\n` and `\uXXXX`
  are the characters they mean, a key ends at `=`, `:` or a blank, a line
  that ends on a backslash goes on in the next, and the file is always
  ISO-8859-1; a `\u` that is no four hex digits fails the job, as it
  stops Java. (An independent run of 4,047 files through Java 17 and v2
  found two rules amiss, both mended since.) v1 reads no escape, ends a
  key at `=` or `:` only, and reads the file in `encoding`.
- A value is read as its column's declared type, and one that cannot be
  goes missing without a word, also where the column may not be missing:
  the rule for rows a job config writes.
- v1's one row is v1's for a properties file of plain lines. For an ini
  file it is filled by v2's plain rules, not by Python's `configparser`
  as v1 fills it: no values handed down from a `[DEFAULT]` section, no
  value that goes on in the next line, and no failure on a key given
  twice or before any section.
- A section named twice is one section.
- The rows come in the order of the file. Talend hands them on in the
  order of Java's hash table, which no job can count on.
- An ini file's names of sections alone can be read
  (`retrive_mode` RETRIVE_SECTIONS), which v1 does not know.
- An ini file is read by plain rules (sections in brackets, `key = value`
  or `key: value`, comments that start with `;` or `#`); Talend reads it
  with the ini4j library, whose finer points were not looked up.
- A file that is not there, or an ini file not written in its encoding,
  fails the job in plain words; v1 reads a wrong byte as a replacement
  character.
- A failure names a row by the line its property is on (for a key given
  twice, the line of the value that stays), and a run can be for a few
  properties, by line or by key.

## Fixed flow input

- The text `false` is false. v1 takes any text that is not empty for true
  in a true/false column here, `false` and `no` among it.
- A value that is not of its column's declared type goes missing (`abc`
  in a Decimal column), and `1.5` in a whole-number column is cut to 1, as
  everywhere a whole-number column is filled. v1 writes both through as
  they are here, `<NA>` for a missing Decimal, and `3.0` for a whole number
  beside a missing one. A date may be written by its column's pattern or
  one of the usual ways, as v1 reads it.
- A whole number too long for 64 bits goes missing in a column declared a
  whole number; in a text or Decimal column it is kept, as in v1.
- A date in the last field of a line that ends in `\r\n`, under the
  default row separator, is read. v1 loses it to the `\r` that stays.
- A context variable that does not exist refuses the job. v1 writes the
  reference through as text.
- `nb_rows` may be written as text or come from the context. v1 fails.
- A failure names the row: `line 3 of the inline content of <id>`, or
  `row 3 of <id>` for the other two ways of writing rows.

## Row generator

- An expression is Python with no name to call on but the `random`
  module, as in v1. That is no fence: Python code can reach anything from
  there, and a job config is trusted as code is. The Java expressions a
  converted job holds (`{{java}}...`) refuse the job, as everywhere.
- A row whose expression fails leaves by the reject output as in v1, and
  the log says how many such rows there were and what failed in the first
  (`id: division by zero`). With no flow on the reject output the log
  warns that they were dropped; v1 drops them and logs an error for each.
- The text `false` or `no` is false in a true/false column. v1 takes any
  text that is not empty for true here.
- A value that is not of its column's declared type goes missing (`abc`
  in a whole-number column, as in v1; the number 20240131 in a date
  column, where v1 writes 1970-01-01), and `1.7` in a whole-number column
  is cut to 1, as everywhere, where v1 writes 1.7 through here. v1 writes
  `<NA>` for a missing Decimal.
- A true/false column with no expression is false. v1 writes `<na>`
  where the column may be missing. Text that is neither true nor false
  (`'Y'`, `'abc'`), and a list, go missing there; v1 takes them by whether
  they are empty. In a row whose expression failed, the column is false
  in the reject output, where v1 has it missing.
- A whole number too long for 64 bits goes missing in a whole-number
  column, and one beyond 38 digits in a Decimal column; v1 writes them.
  `-0.0` in a Decimal column is `0.00` (v1 `-0.00`). In a float column v1
  writes a whole number as it is given (`1` for `'1'`, `True` for `True`);
  v2 writes `1.0`, and nothing for `True`.
- A date may be written by its column's pattern or one of the usual ways
  (`2024-01-31`, with or without a time, or `31/01/2024`), as v1 reads it;
  any other text goes missing.
- An entry of `values` for a column the schema does not have, or a second
  entry for one column, refuses the job. v1 writes a column more.
- A number of rows below 0 or that is no number refuses the job before it
  runs. v1 fails when it comes to the component.
- A context variable that does not exist refuses the job. v1 writes the
  reference through as text.
- The rows of a run are made once: `run.only` and a second reading see the
  rows the first reading made, also where they are drawn at random.
- A failure names the row: `row 3 of <id>`.

## Excel output

- Written with openpyxl, as v1 writes it, and held against v1 by what is
  in the workbook (sheets, cells, their kinds and number formats, column
  widths): a workbook's bytes hold the time it was written.
- Every row is written, one with nothing in it as an empty row, as in
  Talend. v1 leaves such a row out and counts it as rejected.
- With `delete_empty_file`, a workbook that nothing was added to
  (`append_file`) is kept, as in Talend. v1 deletes it.
- A number that is none (not a number, or without end) is no cell. v1
  writes a cell with no value in it.
- Text in a column declared a date with a pattern is written as it is. v1
  writes nothing for text the pattern does not read.
- The widths of `is_all_auto_szie` follow v1's rule (the longest value's
  length and two more), not what Excel would measure as Talend has it.
  They are not always v1's numbers: v1 counts the digits a Decimal with
  no declared places was typed with, `7.0` for a whole number beside a
  missing one, and `nan`. v1 fails to size a sheet that has missing values
  in columns of several types; v2 sizes it.
- A sheet name that is nothing but a quote, or two, is openpyxl's `Sheet`,
  as in v1.
- Refused at load: a sheet name Excel does not take (longer than 31
  characters, which v1 writes with a warning, or holding one of
  `\ / * ? : [ ]`, where v1 fails when it comes to it); a first cell
  before A1 or beyond the last column or row a sheet has; `protect_file`,
  which v1 passes over, leaving the workbook unprotected; `usestream`.
- Columns are taken from the component's input schema. v1 also reads them
  from an output schema written on the component, which the converter
  never writes.
- A character no workbook can hold fails the job with the column and the
  row. v1 fails with openpyxl's words.
- A workbook that cannot be written always fails the job. With
  `die_on_error` off, v1 logs it and goes on with no file.
- A date whose column declares a pattern is text, as in v1. (Talend
  writes a date cell with that format.)
- Two outputs of one subjob may fill two sheets of one workbook, or add
  to one sheet, the second with `append_file`, as in v1.
- A workbook that is added to (`append_file`) and cannot be read, or
  whose sheet has no room for the rows, fails the job when its turn comes
  to be put in place; files the subjob wrote before it are in place by
  then.
- The rows are held in memory while the workbook is made, as in v1.

## Positional output

v1's positional output and Talend's do not agree on much, so here v2 is
held to Talend's own component (read in its source, Talaxie
`tFileOutputPositional_begin.javajet`), and to v1 where v1 does the same:
text and whole numbers, padding and cutting, left and right, the row
separator, the encoding.

- A value is written as the delimited output writes it: a float as it
  prints (`1.5`), a Decimal to its declared places, `true` and `false`, a
  date by its column's pattern. v1 writes a float and a Decimal to eight
  places unless the column declares some (`1.50000000`), `True`, and a
  date without its pattern; and it fails on a job whose typed columns
  have missing values.
- Centred (`align` C), where the padding does not divide evenly the one
  more is on the right: `ab` in five is `*ab**`. v1 has `**ab*` when the
  size is odd.
- A column name longer than its size is kept as a value would be (whole
  under `keep` A). v1 cuts it to the size.
- When adding to a file (`append`), the header goes only into a new or
  empty file. v1 writes it again.
- No rows leave an empty file (or its header). v1 touches no file then,
  and one from an earlier run stays as it was.
- `compress` puts the file into a zip beside its name (`out.txt` into
  `out.zip`), and not when appending. v1 writes gzip under the file's own
  name. Two things Talend's template does with the plain file's name
  while it writes the zip are not followed: it leaves the header out of
  the zip when a plain file of that name is there and not empty, and
  with `delete_empty_file` and no rows it deletes that plain file and
  leaves the zip. v2 writes the header, and leaves no zip.
- A float is written as the engine holds it, which for a column that
  declares places is rounded to them (`2.005` in two places is `2.0`);
  Talend prints the float it was given, and v1 `2.00`.
- The row separator reads `\n`, `\r` and `\t` as the characters they
  mean, like the delimited output. v1 reads every escape Python knows
  (`\u2028`, `\x00`).
- A whole-number column with a missing value is written. v1 fails on it.
- Not the same as Talend, where v2 keeps to its own way of writing a
  value: a float of very many or very few digits (`1.0E10` in Java) and a
  date with no pattern (Java's `Wed Jan 31 ...`), which v2 writes as its
  delimited output does.
- Refused: `use_byte` (widths in bytes), `usestream`, a dynamic schema, a
  `padding_char` of more than one character (v1 fails on it when it
  runs).
- Not acted on, as in v1: `advanced_separator`.

## Pivot to columns delimited

- It is an output and hands no rows on. v1 also hands the pivoted rows to
  a flow that leaves it; v2 refuses a job with such a flow.
- Whole numbers in the cells are written where v1 fails ("Invalid value ''
  for dtype 'Int64'", whenever the value column holds whole numbers and a
  cell is empty).
- A sum of floats is exact, as in the aggregate and as Talend adds: 0.1
  ten times is 1.0, whatever order the rows come in. v1 adds with a
  running correction and comes to the same on ordinary data; it can lose
  a small number beside very large ones.
- Rows that miss a group value are a group of their own, as in Talend. v1
  leaves them out.
- A group whose values are all missing is still a row, as in Talend. v1
  leaves it out for min, max, first and last.
- A missing Decimal is a missing value, as a missing float is in both: a
  sum over none is 0.00, a count 0, and a column with no value at all is
  left out. v1 holds a missing Decimal as something: it writes nothing for
  the sum, counts it, and keeps the column.
- A Decimal with no declared places is written without padding (`4.5`).
  v1 has its digits as they were typed (`4.50`).
- sum needs a column of numbers, and a job that sums anything else is
  refused. v1 puts text together (`x007`) and counts the trues.
- A column to group by that is named twice, or that is the pivot column,
  refuses the job. A pivot value that is the name of a group column fails
  it, in plain words (v1 fails there too).
- `create` written as the text `false` is off. v1 takes any text for on.
- A date that becomes a column name, or that is grouped by, is written by
  its column's pattern, and true/false to group by as `true`, both as in
  Talend. v1 writes the date with its time of day and the word as `True`.
- The table of groups is held in memory while it is turned into columns:
  one row for each group and pivot value, not the rows that came in.
- Not acted on, as in v1: `csv_option`, `advanced_separator`. (Talend acts
  on both.)
