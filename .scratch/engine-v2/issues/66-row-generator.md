# 66 - Row generator

Status: resolved
Type: task

## Question

Build v1's row generator (`RowGenerator`, `tRowGenerator`) on v2: a source
that makes `nb_rows` rows, each column from an expression written in the
job config. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/row_generator.py`. For every row
  and every entry of `values` (`schema_column`, `array`) it evaluates the
  `array` text as Python with nothing in reach but the `random` module.
  Text that is not Python (`hello`, `2024-01-31`, `007`), or that names
  something not in reach (`len('abc')`), is the value itself, as text,
  without the quotes around it if it has them. Any other failure
  (`1/0`) sends the row to the reject output with that column empty.
- `StringHandling.SPACE(3)` is three blanks and `StringHandling.LEN("ab")`
  is 2, taken out of the text before it is evaluated.
- An expression that begins `{{java}}` goes to the Java bridge. The
  converter marks Talend's own expressions that way
  (`TalendString.getAsciiRandomString(6)`), so a converted job needs its
  expressions rewritten for v2, as everywhere else.
- `nb_rows` is text or a number, 100 when left out; it may come from the
  context. Less than 0, or not a number, fails the job.
- Probed on 2026-10-12 with 40 small jobs (v1 only): a column with no
  entry is empty; `None` is a missing value; a value keeps Python's own
  text in a text column (`True`, `[1, 2]`, `0.3333333333333333`, `1e+20`).
- It is a source: it numbers its rows and can be picked from (`run.only`).
  The rows of one run have to be the same however many times the engine
  reads the source, also when the expressions are random.

## Answer

Built on 2026-10-12 (`src/v2/components/transform/row_generator.py`; 39
tests in `tests/v2/components/test_row_generator.py`, against v1; tests
written and seen failing first, 35 of them before any code).

- Expressions are evaluated as v1 evaluates them: Python with only
  `random` in reach, row by row and column after column, so that from the
  same start of Python's random numbers both engines write the same file.
  That is how the random tests hold v2 against v1.
- Text that is not Python, or names something out of reach, is the value
  itself; `StringHandling.SPACE` and `.LEN` as in v1.
- A row whose expression fails leaves by the reject output with the column
  missing and no column added, as v1 writes it. The log says at INFO how
  many rows failed and what failed in the first; with no flow on the
  reject output the usual warning of dropped rows follows.
- The rows of a run are made once and kept for the run
  (`RunContext.made`): the engine reads a source more than once (to find
  the rows `run.only` names, or again with the tolerant reader), and a
  second drawing would give other rows.
- As a reader it numbers its rows (`row 3 of in`), hands on its key, and a
  run can be for a few of its rows by row or by value. Tests in
  `tests/v2/test_row_numbers.py`, `test_only.py`, `test_dropped_rows.py`
  and `test_row_counts_against_v1.py` (counts equal to v1's).
- Mutation check: 31 ways of breaking the component, each caught by a
  test (one needed a test added: quotes around text that is not Python).
- The building of a frame from rows held in Python moved out of the fixed
  flow input into `column_types.held_frame`, which both sources now use.

Decided here, each in the README:

- Java expressions are refused (v2 has no Java). The converted sample
  `Job_tRowGenerator_0.1.json` is refused for them and nothing else.
- An entry for no column of the schema, or two for one column, refuses the
  job; v1 writes a column more.
- `false`/`no` are false; a true/false column with no expression is false
  (v1 `<na>`); a date given as a number goes missing (v1 1970-01-01).
- Not done: an expression Python cannot compile for want of stack (some
  200,000 terms) fails the job with Python's own words; v1 rejects every
  row.
- Talend has no reject output on this component and stops the job when an
  expression throws (Talaxie `tdi-studio-se@639d5fd1f776`,
  `tRowGenerator_java.xml` lines 27-35: a FLOW connector and no REJECT;
  `tRowGenerator_begin.javajet` has no try or catch). v1's reject output
  is kept, being what a v1 job config may be wired to.

Found on the way: the README said of the fixed flow input that `1.5` in a
whole-number column goes missing. It is cut to 1, as everywhere in both
engines; the README now says so.

## Corrected after review (ticket 71)

- A true/false column that may not be missing was written empty for an
  empty expression, and failed the job with no expression at all. It is
  false in both, as in v1 (the fixed flow input had the same fault).
- A number in a true/false column, and true or false in a whole-number
  column, are read as v1 reads them.
- A date written `2024-01-31` or `31/01/2024` under another pattern went
  missing; it is read, as in v1 (also in the fixed flow input).
- "Nothing in reach but `random`" read like a fence. It is none, in
  either engine: the docstring and the README say so.
