# The engine and values

What holds for every job, whatever its components.

Where v2 differs from v1, each on purpose. v1 is the answer key for
everything else these components do. ([The other pages](README.md).)

## The engine

- Java is not run. A `{{java}}` string is refused at load.
- A job is checked before it runs. Config keys that do not go together, an
  expression naming a column that is not there, a context variable nothing
  defines: v1 finds these when the component runs, or not at all; v2 refuses
  the job.
- No stall. In v1 a wired flow that gets no rows (a reject flow with nothing
  rejected) ends the job in status `error`. v2 writes the empty output and
  finishes.
- A failed job exits with code 1. v1 exits 0 whatever happened.
- A subjob is all or nothing: when one of its components fails, none of its
  files is written. v1 leaves the files written before the failure.
- `OnComponentOk` fires when the component's subjob finished, and
  `OnComponentError` for the component that failed. In v1 `OnComponentOk`
  fires for every component that ran before the failure, and
  `OnComponentError` never fires unless `die_on_error` is false.
- A component's row counts are known when its subjob has finished, so a
  later subjob and its triggers can read them, a component of the same
  subjob cannot.
- A component's row counts are of the rows it hands on. Most of v1's
  components count their rows before v1 checks them against the declared
  schema, so a row that check drops, or moves to the reject output (a
  missing value in a column that may not hold one, with `die_on_error`
  off), is still in v1's count of rows passed on and never in its count of
  rejects. In v1 the positional and the Excel input therefore always report
  no rejects. Where no row is dropped that way, the counts are v1's.
- Subjobs are always worked out from the flows. v1's `subjob_id` on a
  component is ignored.
- A context variable named as `${context.x}` that does not exist is an
  error. v1 leaves the text in the value. A context value that does not fit
  its declared type refuses the job; v1 keeps the text and warns.
- A config value that is exactly one context reference keeps the variable's
  type. In v1 every substituted value is text.

## Values

- One rule per type. v1's answer for a value can depend on the other values
  in its column (one fractional value turns a whole `int` column into
  floats; one unparsable value changes how every other value is parsed). v2
  reads every value the same way: `1.50` in an `int` column is `1`.
- `bool` columns produced by a transform are parsed (`true`, `1`, `yes`).
  v1 turns every non-empty text, `false` included, into true.
- Text that is not a number in a `Decimal` column is an unreadable row. v1
  passes any text through a `Decimal` column unchanged.
- A `Decimal` column with no declared `precision` holds ten places. v1 keeps
  the digits as they were typed. Written through a file output that declares
  the column, the result is the same (trailing zeros are dropped); printed
  or handed to Python code, ten places show.
- A negative `precision`, which is how Talend writes that none is declared,
  means none. v1 takes -1 as it stands: a float column is rounded to tens
  (123.456 becomes 120.0) and a Decimal column to whole numbers.
- A negative Decimal that rounds to zero is written `0.00`. v1 writes
  `-0.00`.
- A float written by an output that declares the column `Decimal` with no
  `precision` is written as it prints (`1e-07`). v1 writes `0.0000001`.
- Where v1 writes the text `<NA>` or `<na>` for a missing value (a Decimal
  or bool column the engine added, a missing Decimal after some readers), v2
  writes an empty field.
- Control characters in a file are kept. v1 replaces them with spaces, which
  it needs for its Java bridge.
