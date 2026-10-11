# 63 - Schema compliance check

Status: resolved
Type: task

## Question

Build v1's schema compliance check (`SchemaComplianceCheck`,
`tSchemaComplianceCheck`) on v2: rows that do not fit a schema written in
the config leave by the reject output, with what is wrong with them.
Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/schema_compliance_check.py`. The
  schema to check against is in the config (`schema`), not the component's
  own. For each column: may it be missing (`nullable`; empty text counts as
  missing under `all_empty_are_null`, or column by column in
  `empty_null_table`), can its value be read as a number or true/false,
  does a date fit its pattern (`strict_date_check`), is its text within
  `length` (characters, or bytes under `check_string_by_byte_length`).
- A row with any fault leaves by the reject output with `errorCode` 8 and
  an `errorMessage` of all its faults, `column:what`, joined with `;`.
- `check_another` with `checkcols` checks only the columns listed, and
  takes `nullable` from the list. v1 reads nothing else of an entry.
- `customer`, `sub_string`, `fast_date_check` and `ignore_timezone` are
  accepted by v1 and do nothing but log a warning.

## Answer

Built on 2026-10-11 (`src/v2/components/transform/schema_compliance_check.py`;
19 tests in `tests/v2/components/test_schema_compliance_check.py`, against
v1; tests written and seen failing first).

- Every check of v1's, with v1's words for a fault (`id:cannot be null`,
  `amt:invalid type`, `day:invalid date format`, `name:exceed max length`)
  and its code 8. A row's faults are joined with `;` in the order of the
  schema's columns. Held against v1 row for row, on text columns and on
  typed ones.
- `check_another` with `checkcols`, `all_empty_are_null` and
  `empty_null_table` (read only while the first is off, as in v1),
  `strict_date_check`, `check_string_by_byte_length` with `charset`,
  `die_on_error`. The four switches v1 only warns about are accepted.
- With no flow on the reject output, the log says how many rows were
  dropped and the first (a test in `tests/v2/test_dropped_rows.py`). Row
  numbers pass; the counts are held against v1's.
- Differs from v1, both in the README: the reject file's header line where
  no row is turned away, and the character sets bytes are counted in.
- Not checked against Talend's own component: its source was not read.

## Corrected after review (ticket 67)

- `strict_date_check` took dates v1 turns away (`24-01-31`, a blank in
  front, a missing fraction) and turned away one v1 takes. The check is
  now written out as pandas reads a pattern and held to pandas over 29
  patterns and some 180 values.
- A number behind a no-break space is no number, as in v1. The key
  `pattern` is not read, as in v1 (it was taken for `date_pattern`).
- The length of a typed value is of the text it is written as. A date
  pattern is held to a column of any type but a date.
- "Differs from v1, both in the README" was short by several; they are in
  the README now. The doc of `die_on_error` said more than it does.
