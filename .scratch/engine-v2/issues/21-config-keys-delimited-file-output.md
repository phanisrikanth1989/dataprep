# 21 - Config keys, key by key: delimited file output

Status: resolved
Type: grilling
Blocked by: 02, 05, 07, 13, 14

## Question

Walk every config key of v1's FileOutputDelimited and of v2's
`file_output_delimited` as found, and give each one of the five verdicts: same
in both; v2's name kept with v1's spelling as an alias; v2 adopts v1's name;
the loader translates v1's form; refused or ignored.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Recover the purpose of each v2 rename before judging it. Apply
[The performance bar](05-performance-bar.md) to anything that might be
refused and the defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).
Also settle v1 behaviours that have no key but that the answer key still
demands: how numbers, dates, nulls and empty strings are written. What the
Polars writer can and cannot do is in the answer to
[Polars facts: reading and writing delimited files](02-polars-facts-delimited-files.md):
shortest round-trip float text, one date format per file, no thousands
separator, UTF-8 only, no append parameter, and splitting only through an
option Polars marks unstable.

v1 keys (`agents/schemas/config-surfaces.md` is the code-verified list, with
defaults): `filepath`, `csv_option`, `include_header`, `append`,
`create_directory`, `split`, `split_every`, `delete_empty_file`,
`file_exist_exception`, `os_line_separator`, `streamname`, `fieldseparator`,
`row_separator`, `encoding`, `escape_char`, `text_enclosure`,
`csvrowseparator`. Present in job configs but deferred or never read by v1:
`compress`, `usestream`, `row_mode`, `flushonrow`, `flush_row_count`,
`advanced_separator`, `thousands_separator`, `decimal_separator`,
`tstatcatcher_stats`, `label`.

v2 keys as found: `path`, `delimiter`, `line_terminator`, `has_header`,
`append`, `null_value`, `quote_char`, `quote_style`, `datetime_format`,
`date_format`, `delete_empty_file`, `error_if_exists`, `schema`, `label`.

The verdict for `encoding` comes from
[Encoding: what to do about ISO-8859-15](14-encoding-iso-8859-15.md). Facts
come from
[Polars facts: reading and writing delimited files](02-polars-facts-delimited-files.md).

## Answer

Resolved 2026-10-06 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn. The full key list, generated from the
code, is the component's page under `docs/v2/components/`
(`.venv/bin/python scripts/gen_v2_docs.py`).

- Supported with v1's defaults: `path` (v1 `filepath`), `delimiter` (v1
  `fieldseparator`), `row_separator`, `csv_row_separator` (v1
  `csvrowseparator`), `os_line_separator` (default true, which overrides
  both separators, as in v1), `encoding`, `include_header`, `append`,
  `create_directory`, `csv_option`, `text_enclosure`, `escape_char`,
  `file_exist_exception`, `delete_empty_file`.
- Ignored, because v1 ignores them too: `compress`, `usestream`,
  `streamname`, `advanced_separator`, `thousands_separator`,
  `decimal_separator`, `flushonrow`, `flush_row_count`, `row_mode`; and
  `die_on_error` (a file that cannot be written always fails the job).
- Refused: `split` (one flow into several files) is not built yet.
- Values are written as v1 writes them, decided by the writer's own declared
  columns: dates by `date_pattern`, Decimals to `precision` (or without
  trailing zeros), booleans in lower case, floats as Python prints them.
  Columns go out in the order they arrive.
- The file is written beside its target and put in place when the whole
  subjob has succeeded; v1's rules for an existing file, for appending and
  for no rows are kept.
