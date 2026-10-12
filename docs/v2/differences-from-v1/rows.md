# Rows

The components that take rows and hand rows on.

Where v2 differs from v1, each on purpose. v1 is the answer key for
everything else these components do. ([The other pages](README.md).)

## Filter rows

- The advanced condition is a Python expression (`condition`; v1's
  `advanced_cond` is an alias). v1 runs it as Java, row by row, and passes
  every row when its bridge is off.
- A missing value fails every test except `!=`, `NOT_CONTAINS` and
  `IS_NULL`. v1 does the same, except that a missing whole number under a
  number comparison lands in neither output there.
- `MATCHES` always tests the whole text.
- Refused at load, where v1 runs and gives an answer that is rarely meant:
  a condition on a column that does not exist (v1: false for every row), an
  unknown `function` (v1: tests the column as it is), a date column compared
  with a number, a pattern with lookaround or back-references, a text test
  (`CONTAINS`, `MATCHES`, a text `function`) on a Decimal column.

## Filter columns

- With no input rows the declared columns are kept, as with rows. v1 passes
  every input column then.
- A schema that shares no column with the input is refused.

## Sort row

- Sorting text as dates reads every value as `%Y-%m-%d %H:%M:%S`,
  `%Y-%m-%d` or `%d/%m/%Y` and puts what does not fit last. v1 lets pandas
  guess one format for the column from its first value.
- A criterion on a column that does not exist is refused (v1 drops it).

## Unique row

- A key column that does not exist is refused at load. v1 skips it and
  falls back to the whole row.
- `<id>_NB_UNIQUES` and `<id>_NB_DUPLICATES` are counted only when something
  in the job reads them.

## Aggregate row

- Rows that miss a group value are a group of their own, whose key is
  written as nothing, as in Talend: the key its tAggregateRow generates
  holds a missing value like any other. v1 leaves such rows out without a
  word (pandas' `groupby` drops them), so v2 writes a row there that v1
  does not: of `1;1`, `;2`, `1;3`, `;40`, `2;5` summed by the first column,
  v1 writes `1;4` and `2;5`, and v2 writes `;42` as well.
- Sums and averages of floats are exact and do not depend on the order of
  the rows: 0.1 + 0.2 + 0.3 is 0.6. That is v1 with
  `use_financial_precision` (the converter's default); with it off, v1 has
  float noise (0.6000000000000001) that v2 does not reproduce.
- Standard deviation and variance are exact where every distance from the
  mean has at most nine decimal places, and to about fifteen significant
  digits otherwise; the last digits of an unrounded result can then differ
  from v1's.
- A missing Decimal is a missing value. v1 holds an empty Decimal field as
  empty text and counts and lists it.
- The smallest and the largest of a text or date column are written. v1
  writes nothing for them under `use_financial_precision`, its default.
- An average kept in a Decimal column with no declared `precision` has 18
  decimal places. v1 keeps 28 significant digits.
- In a column declared `str`, or not declared, numbers print as held (`2.2`);
  v1 prints its Decimals (`2.20`).
- v2 runs what v1 fails on: first/last without group columns, group columns
  without operations (each group once), lists over missing whole numbers.
- Refused at load: a sum, average, median, deviation or variance of a column
  that is not a number (v1 gives 0 or nothing), a config with neither group
  columns nor operations.

## Aggregate sorted row

- A group is a run of rows, one after another, that agree in the group
  columns, as in Talend, whose component compares each row with the one
  before it. On rows sorted by the group columns, which is what the
  component is for, that is what v1 writes. On rows that are not sorted,
  v1 groups the whole input and writes a group value once, where v2 and
  Talend write it once for each run: of `a;1`, `b;2`, `a;3` summed by the
  first column, v1 writes `a;4`, `b;2` and v2 writes `a;1`, `b;2`, `a;3`.
- Everything said of the aggregate row holds here too, the rows that miss
  a group value among it.

## Join

- A missing key matches nothing, for every type. v1 fails on whole-number
  keys when any is missing, and where it does run it hands a left-joined row
  the lookup columns of the lookup's own missing-key row.
- `case_sensitive: false` only compares without case. v1 also writes the key
  columns in lower case and multiplies rows when lookup keys differ only in
  case.
- Key columns that cannot be compared (text against a number or a date) are
  refused at load. v1 fails at run, or runs and matches nothing.
- Refused at load: a fetched column whose output name the output already
  has (v1 writes two columns of one name), a third input (v1 ignores it), an
  empty `join_key`, a key column that does not exist.
- Three things v1 does with `lookup_cols` are kept, each with a warning in
  the log, because they are what v1 writes: a lookup column whose name the
  main input also has is not fetched (it is reachable as `<name>_lookup`), a
  lookup column is fetched once, and an entry naming no lookup column adds
  nothing.
- `<id>_ERROR_MESSAGE` is not set in the globalMap.

## Unite

- A unite with one input passes it through. v1 drops every row.
- The columns of the output never depend on which inputs happen to be
  empty. v1 forgets the columns of an empty input.

## Map

- Main rows keep their order. v1 moves the rows whose join key is missing
  behind all the others, lookup by lookup.
- A whole-number column stays whole. v1 writes `30.0` wherever pandas turned
  the column into floats (a lookup column beside an unmatched row, a column
  holding a missing value).
- Reject outputs work as in Talend and in v1's tMap, not as in v1's PyMap:
  an `is_reject` output takes the rows no ordinary output took, with its own
  columns, and an `inner_join_reject` output computes its own expressions.
- An inner join on a lookup with no rows rejects every main row (PyMap keeps
  them all).
- An expression that fails on a row fails the component, whatever
  `die_on_error` says: `int(row1.code)` on text that is not a number, for
  instance. As in Python, it fails only on a row the conversion is worked
  out for: not behind an `and` that is already false, an `or` that is
  already true, in the branch of an `if` that is not taken, or further along
  a chain of comparisons (`a < b < c`) than the first that does not hold.
  `np.where` is a function and is handed both its values worked out, so a
  conversion in either fails. An operation on a missing value never fails;
  it gives a missing value. Rows are not sent to a catch output.
- A row an inner join turned away has left the map, as in v1: no variable
  and no key of a later lookup is worked out for it, so a conversion in one
  cannot fail on it. v1 gives an `inner_join_reject` output no variables to
  read. v2 does, and when such an output reads one, the variables are worked
  out for every row.
- An output column nothing in the job reads is never worked out. A
  conversion in it that fails on a row still fails the job, as in v1, which
  works out every column of every output.
- In an expression a missing value is `None`. v1 hands expressions pandas'
  `nan` or `<NA>`, so `x is None`, `str(x)` and `x or default` can answer
  differently there.
- Refused at load: `lookup_mode` other than LOAD_ONCE (reloading a lookup
  for each row needs a loop over the rows), a join key `operator` other
  than `=`, a lookup filter that reads the main row, a text key against a
  number key without `enable_auto_convert_type`, `ALL_ROWS` on a lookup
  that has join keys.
- Kept as v1 has them: an `is_reject` output's own filter is not read, and
  an output column's `nullable` and `precision` are not applied.
- A row count of a component in the same subjob is not known while the plan
  is built: `globalMap.get("in_NB_LINE")` reads it in a later subjob only.

## Normalize

- A column of dates is refused. A number or a true-or-false value is split
  as the text Python writes for it (`1e-07`, `True`), as in v1.
- `csv_option` and its two keys are accepted and change nothing, as in v1.

## Denormalize

- A whole number is put together whole (`3`). v1 writes `3.0` for every
  value of a whole-number column that has a missing value anywhere.
- A Decimal whose column declares no places is put together without
  padding (`1.5`). v1 writes it as it stood in the file (`1.50`).
- A named column that is not there, and a config that names every column,
  refuse the job at load. v1 fails when the component runs. A column named
  twice refuses the job too; v1 writes the column twice.

## Replicate

- No difference from v1 is known. `output_count` is checked as v1 checks
  it (a whole number from 1 to 10) and changes nothing: the flows that
  leave the component decide how many copies there are.

## Sample row

- A range that cannot be read refuses the job at load. v1 fails when the
  component runs.

## Split row

- A whole number is written whole (`100`). v1 writes `100.0` for every
  value of a whole-number column that has a missing value anywhere.

## Replace

- Patterns run on Polars' regular expressions, not Python's. An advanced
  rule whose pattern Polars cannot read is refused at load: look-around, a
  back-reference inside the pattern, `\Z`, `a{,2}`, `(?#...)` and a few more
  spellings Python takes. A few patterns both read mean something else:
  a character class inside another (`[a[b]c]`), `&&` inside a class, `\<`.
- A pattern that can match nothing (`x*`) is replaced once less than in v1
  right after a match: of `x` under `x*` to `-`, v1 writes `--` and v2 `-`.
- A group of the match is put back in the replacement as in v1 (`\1`,
  `\g<1>`), and a replacement Python would not take refuses the job at
  load, where v1 fails when the component runs.
- A date is searched as the text its column's pattern gives, and as its
  day alone when it has no pattern and no time of day. v1 searches the
  second form whenever every value of the column is at midnight.

## Convert type

- v1 on today's pandas turns away every row a pair converts in place (its
  own cast fails on a text column), so v1 is the answer key only for a pair
  that names another output column. There v2 keeps and turns away the same
  rows for whole numbers and floats, text or not, and for dates and
  true/false read from typed columns.
- Text is read by the rules v2's readers have for the declared type. v1
  reads through pandas, which takes more: a date in any spelling whatever
  the column's pattern, any text but `true` as false. v2 turns such a row
  away.
- The reject output has `errorCode` and `errorMessage`, as every reject
  output of v2 and of Talend. v1's convert type alone calls them
  `error_code` and `error_message`. The message is v2's own (`Column 'n' ->
  'n' (int): cannot read 'x'`); v1's is pandas' text.
- Two pairs that read one column fill both output columns. v1 fills the
  last one only.
- `autocast` asks for nothing more: the engine reads every value as the
  type its output column declares, as after any component.

## Unpivot row

- A whole number is written whole (`3`). v1 writes `3.0` for every whole
  number when any of the unpivoted columns holds a float or a missing
  value, because pandas makes one column of them all.
- A Decimal whose column declares no places is written without padding
  (`1.5`). v1 writes it as it stood in the file (`1.50`).
- Keys that cannot be used (none named, one that is no column, one named
  twice) and names that clash refuse the job at load. v1 fails when the
  component runs. With `die_on_error` off both hand on no rows for a key
  that is no column.

## Schema compliance check

- Where no row is turned away, the file behind the reject output has its
  header line. v1 leaves that file with nothing in it.
- Bytes are counted in UTF-8 and in one-byte character sets
  (`check_string_by_byte_length`). Any other `charset` is refused at load;
  v1 counts in whatever Python knows. A character a one-byte set cannot
  write counts as one; v1 fails the job on it.
- Under `strict_date_check` a date fits its pattern where v1 says it does
  (v1 asks pandas; v2 is held to pandas' answer over 29 patterns and some
  180 values, odd ones among them: `2024-1-5` fits `%Y-%m-%d`, `24-01-31`
  does not). Not the same: digits of another script are no date in v2; a
  pattern with a part other than year, month, day, hour, minute, second,
  fraction, AM/PM and time zone (a month by name, say) is read by Polars;
  and a pattern that is no pattern (`%Q`) refuses the job at load, where
  v1 fails when the rows arrive.
- A missing Decimal is a missing value. With `all_empty_are_null` off, v1
  holds it as empty text and turns its row away as `invalid type`.
- The length of a value that arrives typed is that of the text it is
  written as (`2024-01-31` for a day with no time, `1.5` for a Decimal
  with no declared places). v1 has the digits of such a Decimal as they
  were typed, and fails on a whole-number column that has a missing value.
- `length` written as text (`"2"`) is the number. v1 passes over it.
- An entry of `empty_null_table` without `empty_is_null`, and a key v2
  does not know in a column of `schema`, refuse the job. v1 passes over
  both.

## Python dataframe

- `dataframe: polars` is new: the code gets a Polars lazy frame and the
  component stays lazy. The default, `pandas`, is v1's behaviour.
- A missing Decimal reaches the code as `None`. v1's file input leaves an
  empty text in the column.
- Code that leaves two columns of one name fails the component.
- Decimals the code makes with different numbers of places (by a division,
  say) are carried as text, each as Python prints it, so a file output
  writes what v1 writes. Declare the column `Decimal` in the component's
  schema to keep it a number for the components that follow.
- The code runs with Python's ordinary built-ins; v1 withholds a few
  (`open`, `eval`, `exec`).

## Log row

- A whole number prints whole. v1 prints `1.0` when every column of the row
  is a number and one of them is a float.
- A table is always aligned. v1's table fails on a missing whole number or
  an all-missing date column.
