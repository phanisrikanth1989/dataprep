# 25 - Config keys, key by key: map

Status: open
Type: grilling
Blocked by: 05, 07, 08, 12, 16

## Question

Walk every config key of v1's Map and of v2's `map` as found, and give each
one of the five verdicts: same in both; v2's name kept with v1's spelling as
an alias; v2 adopts v1's name; the loader translates v1's form; refused or
ignored. The largest of the key-by-key tickets: split it if one session
cannot finish it.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Recover the purpose of each v2 rename before judging it. Apply
[The performance bar](05-performance-bar.md) and the defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).

v1 keys (`agents/schemas/config-surfaces.md`, section 5; v1's Map and PyMap
share this shape, Map with `{{java}}` expressions and PyMap with Python):

- `inputs.main`: `name`, `filter`, `activate_filter`, `matching_mode`,
  `lookup_mode`.
- `inputs.lookups[]`: `name`, `join_keys[]` (`lookup_column`, `expression`,
  `type`, `nullable`, `operator`), `join_mode` (`LEFT_OUTER_JOIN`,
  `INNER_JOIN`), `matching_mode` (`UNIQUE_MATCH`, `FIRST_MATCH`,
  `ALL_MATCHES`, and `LAST_MATCH` in PyMap), `lookup_mode` (`LOAD_ONCE`,
  `RELOAD_AT_EACH_ROW`), `filter`, `activate_filter`.
- `variables[]`: `name`, `expression`, `type`, `nullable`.
- `outputs[]`: `name`, `columns[]` (`name`, `expression`, `type`, `nullable`,
  `length`, `precision`, and the date format key, which v1 reads under one
  name and its converter writes under another), `is_reject`,
  `inner_join_reject`, `catch_output_reject`, `filter`, `activate_filter`.
- `die_on_error`, `enable_auto_convert_type`, `label`, and the keys v1
  carries but never uses (`rows_buffer_size`, `size_state`, `persistent`,
  and others listed in config-surfaces).

v2 keys as found: `lookups[]` (`name`, `input`, `keys[]` with `main` and
`lookup`, `join_type`, `match_mode`), `variables[]`, `outputs[]` (`name`,
`filter`, `columns[]`), `lookup_reject_output`, `filter_reject_output`,
`error_reject_output`, `die_on_error`.

Also settle:

- Which v1 type names v2's map answers to: `Map`, `tMap`, `PyMap`.
- Join keys that are expressions on the main side, where v2 as found takes
  column names only.
- Lookup modes and matching modes Polars cannot do at speed (reloading the
  lookup at each row).
- The three kinds of reject and how v1's per-output flags select them.
- The defects in the map as found (findings 15 and 22).

Expression syntax itself is settled in
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).
