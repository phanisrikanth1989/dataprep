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

## Corrected after review (ticket 62)

- A date column lost every value, also where no rule matched: the date was
  searched as `2024-01-31 00:00:00`, which could not be read back by the
  column's pattern. A date is now searched as the text its pattern gives,
  or as its day alone when it has neither a pattern nor a time of day.
- A context value in an advanced pattern or replacement is put in before
  the pattern is read.
- `die_on_error` is declared, as on every component of v1.
- Octal escapes in a replacement (`\0`, `\101`) are read as Python reads
  them. `\g<a>` for a group that is not there, and a replacement that is
  no text, refuse the job in words of their own.
- The README now says what really differs: patterns run on Polars' regular
  expressions (more than look-around is refused, and a few spellings mean
  something else), and a pattern that can match nothing is replaced once
  less after a match.
