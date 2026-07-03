# Recon Requirements Template

Author the requirements as a `.docx` with exactly these four Heading-1 blocks.
`extract_doc` parses them deterministically; keep them as real Word tables
(not screenshots).

## Inputs and Schema
One table. Header row: `Source | Column | Type | Nullable | Key`.
One row per column of each input source. Type is one of
`str, int, float, bool, date, datetime, decimal`.

## Transformation Rules
One table. Header row: `ID | Kind | Description`.
Kind is one of `match, tolerance, filter, aggregate, derive`.

## Sample Input
One Heading-2 per source (named exactly as in "Inputs and Schema").
Under each, one table whose header row is that source's column names, with a
handful of real rows (include a null, a break, and a tolerance edge).

## Expected Output
One Heading-2 per output (e.g. `matched`, `breaks`, `summary`).
Under each, one table whose header row is the output's columns; suffix each
composite-key column with `*` (e.g. `txn_id*`). Rows are the expected result
for the Sample Input above. These rows are the test oracle and stay local.
