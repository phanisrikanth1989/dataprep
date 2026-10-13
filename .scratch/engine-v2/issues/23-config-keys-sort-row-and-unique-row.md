# 23 - Config keys, key by key: sort row and unique row

Status: resolved
Type: grilling
Blocked by: 05, 07, 08

## Question

Walk every config key of v1's SortRow and UniqueRow and of v2's `sort_row` and
`uniq_row` as found, and give each one of the five verdicts: same in both;
v2's name kept with v1's spelling as an alias; v2 adopts v1's name; the loader
translates v1's form; refused or ignored. Two small components in one ticket.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Recover the purpose of each v2 rename before judging it. Apply
[The performance bar](05-performance-bar.md) and the defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).

Sort row:

- v1 (`agents/schemas/config-surfaces.md`): `criteria` (each with `column`,
  `sort_type` of `num`, `alpha` or `date`, `order` of `asc` or `desc`),
  `external`.
- v2 as found: `columns` (each with `name`, `order`, `nulls_last`),
  `nulls_last`, `maintain_order`.
- Also settle, against the answer key: where nulls sort, whether equal rows
  keep their input order, and what `sort_type` means when the column already
  has a type.

Unique row:

- v1: `key_columns` (a name, or `column` with `case_sensitive`), `keep`,
  `case_sensitive`, `output_duplicates`, `is_reject_duplicate`,
  `only_once_each_duplicated_key`.
- v2 as found: `key_columns`, `keep` (`first`, `last`, `none`, `any`),
  `maintain_order`, `duplicate_output`, `only_once`. Its outputs are named
  `unique` and `duplicate`, and nothing is emitted as `main` (finding 3).
- Also settle how v1's `unique` and `duplicate` flow types select the
  outputs.

## Answer

Resolved 2026-10-06 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn. The full key list, generated from the
code, is the component's page under `docs/v2/components/`
(`.venv/bin/python scripts/gen_v2_docs.py`).

- Sort row: `criteria[]` (`column`, `sort_type` alpha/num/date, `order`),
  stable, missing values last both ways, text by code point, as v1.
  Talend's sort-on-disk keys (`external`, `tempfile`, `createdir`,
  `external_sort_buffersize`) are ignored.
- Unique row: `key_columns` (names, or `{column, case_sensitive}`; every
  column when empty), `keep` (first, last, or false for no row of a repeated
  key), `case_sensitive`, `only_once_each_duplicated_key`,
  `output_duplicates`, `is_reject_duplicate`. Outputs `main` (flow, main,
  unique) and `reject` (duplicate, reject), both in input order. Talend's
  work-on-disk keys are ignored.
- Row counts are v1's; `<id>_NB_UNIQUES` and `<id>_NB_DUPLICATES` are
  counted when something in the job reads them.
