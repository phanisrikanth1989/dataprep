# 23 - Config keys, key by key: sort row and unique row

Status: open
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
