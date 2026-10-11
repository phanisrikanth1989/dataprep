# 73 - Extract regex fields

Status: resolved
Type: task

## Question

Build v1's extract regex fields (`ExtractRegexFields`,
`tExtractRegexFields`) on v2: a pattern is looked for in one column's
text and what its groups hold becomes columns. Asked for on 2026-10-11
with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/extract_regex_fields.py`, on
  Python's `re.search`: the first place the pattern is found anywhere in
  the text; the first group goes to the first column the output declares
  and the input does not bring, and so on. A group that took no part is
  missing; so is a column beyond the last group.
- Tried on v1 (2026-10-12, 22 small jobs): a text the pattern is not
  found in leaves by the reject output (`NO_MATCH`) or, under
  `die_on_error` (on by default), fails the job; a missing source always
  leaves by the reject output (`NULL_SOURCE`) and never fails the job;
  under `check_fields_num` a pattern whose groups are not as many as the
  columns turns every row away that it is found in
  (`FIELD_COUNT_MISMATCH`); `\\\\` in the pattern is read as `\\`; a
  `field` that is no column is taken for the first column when the job is
  not to die.
- v2 looks for patterns with Polars, which has no lookaround and no
  backreference; the expressions refuse such a pattern at load, and so
  will this.

## Answer

Built on 2026-10-12 (`src/v2/components/transform/extract_regex_fields.py`;
28 tests in `tests/v2/components/test_extract_regex_fields.py`, all
written and seen failing before any code; held against v1 byte for byte).

- On `ExtractFields`: this component says how the groups are found and
  when a row is turned away. One pass, no row walked.
- The pattern is checked twice at load: Python has to read it (it counts
  the groups and their names), and Polars has to be able to look for it.
- v1's messages, the text shown as Python shows it; v1's order of faults
  in a row (no source, not found, wrong number of groups).
- Differs from v1, each in the README: patterns Polars cannot look for;
  `$` before a final line break; refusals at load.
- Row counts are held against v1's.
- Mutation check: 15 ways of breaking it; 13 caught at first, one after a
  test, and one showed a cut of the groups that did nothing and is gone.
