# 20 - Config keys, key by key: delimited file input

Status: open
Type: grilling
Blocked by: 02, 05, 07, 13, 14

## Question

Walk every config key of v1's FileInputDelimited and of v2's
`file_input_delimited` as found, and give each one of the five verdicts: same
in both; v2's name kept with v1's spelling as an alias; v2 adopts v1's name;
the loader translates v1's form; refused or ignored.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Recover the purpose of each v2 rename before judging it. Apply
[The performance bar](05-performance-bar.md) to anything that might be
refused and the defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).
Also settle v1 behaviours that have no key but that the answer key still
demands.

v1 keys (`agents/schemas/config-surfaces.md` is the code-verified list, with
defaults): `filepath`, `fieldseparator`, `row_separator`, `encoding`,
`header_rows`, `footer_rows`, `limit`, `remove_empty_row`, `csv_option`,
`csv_row_separator`, `escape_char`, `text_enclosure`, `trim_all`,
`trim_select`, `check_fields_num`, `check_date`, `die_on_error`. Present in
job configs but deferred or never read by v1: `uncompress`, `split_record`,
`random`, `nb_random`, `advanced_separator`, `thousands_separator`,
`decimal_separator`, `enable_decode`, `decode_cols`, `tstatcatcher_stats`,
`label`.

v2 keys as found: `path`, `delimiter`, `quote_char`, `has_header`,
`skip_rows`, `footer_rows`, `limit`, `skip_empty_rows`, `trim_all`,
`trim_columns`, `encoding`, `die_on_error`, `nan_is_null`, `eol_char`,
`schema`.

The verdict for `encoding` comes from
[Encoding: what to do about ISO-8859-15](14-encoding-iso-8859-15.md). Facts
come from
[Polars facts: reading and writing delimited files](02-polars-facts-delimited-files.md).
