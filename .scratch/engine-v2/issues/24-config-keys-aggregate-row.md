# 24 - Config keys, key by key: aggregate row

Status: open
Type: grilling
Blocked by: 05, 07, 13

## Question

Walk every config key of v1's AggregateRow and of v2's `aggregate` as found,
and give each one of the five verdicts: same in both; v2's name kept with
v1's spelling as an alias; v2 adopts v1's name; the loader translates v1's
form; refused or ignored.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Recover the purpose of each v2 rename before judging it. Apply
[The performance bar](05-performance-bar.md) and the defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).

v1 keys (`agents/schemas/config-surfaces.md`): `groupbys` (each with
`input_column`, `output_column`), `operations` (each with `function`,
`input_column`, `output_column`, `ignore_null`), `list_delimiter`,
`use_financial_precision`.

- Functions: `count`, `min`, `max`, `avg`, `sum`, `first`, `last`, `list`,
  `list_object`, `count_distinct`, `std`, `population_std_dev`, `median`,
  `variance`, `union`. A verdict for each.

v2 keys as found: `group_by`, `aggregations` (each with `name`, `function`,
`column`, `ignore_nulls`, `separator`), `maintain_order`. Functions: `sum`,
`count`, `avg` / `mean`, `min`, `max`, `first`, `last`, `count_distinct` /
`n_unique`, `std`, `var`, `median`, `list`.

Also settle, against the answer key: the order of groups in the output; the
order and types of output columns; what each function returns for a group of
nulls; and what `use_financial_precision` asks for, which depends on the
Decimal decision in
[Types, nulls and schemas](13-types-nulls-and-schemas.md).
