# ETL Requirements Template

Author the requirements as a `.docx` with Heading-1 blocks. `extract_doc` parses
them deterministically; keep them as real Word tables (not screenshots).

Two blocks are REQUIRED; three more are OPTIONAL and select the verification
tier the harness will run:

- REQUIRED: `Inputs and Schema`, `Transformation Rules`.
- OPTIONAL: `Sample Input`, `Expected Output`, `Notes / Special Handling`.

The tier is presence-driven, not a row count of the required blocks:

- `Sample Input` present AND `Expected Output` present with data rows -> `verified`
  (the harness runs the job and diffs the outputs against the expected rows).
- `Sample Input` present but no graded `Expected Output` -> `smoke` (the harness
  runs the job to confirm it executes end-to-end; nothing is diffed).
- no parseable `Sample Input` -> `build` (the job is built and surfaced, never
  executed).

Two rules the parser depends on:

- Keep each table cell to a single line (no in-cell line breaks). Cell text is
  read verbatim and multi-line cells corrupt the parsed values.
- Use the English "Heading 1" and "Heading 2" Word styles for the block and
  sub-block headings. The parser matches on the English style names, so a
  localized Word UI must still apply the English "Heading 1"/"Heading 2" styles.

## Inputs and Schema  (REQUIRED)
One table. Header row: `Source | Column | Type | Nullable | Key`.
One row per column of each input source. Type is one of
`str, int, float, bool, date, datetime, decimal`.

## Transformation Rules  (REQUIRED)
One table. Header row: `ID | Kind | Description`.
Kind is one of `join, schema_validate, filter, aggregate, sort, derive`.

## Sample Input  (OPTIONAL)
One Heading-2 per source (named exactly as in "Inputs and Schema").
Under each, one table whose header row is that source's column names, with a
handful of real rows (include a null, plus rows that both do and do not match a
lookup key, so matched and unmatched cases are both exercised).

## Expected Output  (OPTIONAL)
One Heading-2 per output (e.g. `result`, `rejected`, `summary`).
Under each, one table whose header row is the output's columns; suffix each
composite-key column with `*` (e.g. `txn_id*`). Rows are the expected result
for the Sample Input above. These rows are the test oracle and stay local. An
output with only a header row and no data rows is declared-empty (`graded:
false`): it is run but not diffed.

## Notes / Special Handling  (OPTIONAL)
Free prose. Everything under this Heading-1 is captured verbatim into `notes`
and folded into the rules by the doc-interpreter (edge cases, tie-breaks,
case-sensitivity, unit conventions, or anything the tables cannot express).
