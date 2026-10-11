# 56 - Replace

Status: resolved
Type: task

## Question

Build v1's replace (`Replace`, `tReplace`) on v2: search and replace in
the values of columns. Asked for on 2026-10-11 with the other 25.

## Answer

Built on 2026-10-11 (`src/v2/components/transform/replace.py`; 29 tests in
`tests/v2/components/test_replace.py`, against v1).

- Simple mode: `substitutions` with `whole_word`, `case_sensitive` (off by
  default, as in v1), `use_glob`, and `strict_match` (on by default: only
  a value that is the searched text and nothing else is replaced). The
  searched text is taken as written, never as a pattern.
- Advanced mode (`simple_mode` off): `search_column` is a regular
  expression and `replace_column` its replacement, as v1 reads them in
  spite of their names.
- A replacement is read as Python's `re.sub` reads it (`\1`, `\g<1>`, a
  dollar is a dollar) and handed to Polars in its own spelling. One Python
  would not take refuses the job at load.
- A column that is not text is searched as its text and read back as its
  declared type. A rule for a column that is not there is passed over.
- Differs from v1: an advanced pattern that needs look-around or a
  back-reference is refused at load, because Polars' regular expressions
  have neither.
- The converter's sample fails on both engines in the same way: it writes
  a word over a whole-number column that may not be missing.
