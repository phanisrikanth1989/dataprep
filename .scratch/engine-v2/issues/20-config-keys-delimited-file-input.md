# 20 - Config keys, key by key: delimited file input

Status: resolved
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

[The performance bar](05-performance-bar.md) settled that there is no blanket
test: each key here is judged on need against cost, and footer rows stays.
Bring its measurements for `footer_rows`, `encoding` and `die_on_error`, and
the three defects it found in the component as found: reject messages built
in a Python loop, a Boolean column failing when `die_on_error` is false, and
a trailer line that does not fit the schema failing when `die_on_error` is
true.

And settle, one by one, what v2 does about the Polars reader behaviours that
give a wrong result without an error: guard against it, refuse the input, or
accept it. They are listed in the answer to
[Polars facts: reading and writing delimited files](02-polars-facts-delimited-files.md):
a line with too few fields padded with nulls; too many fields not raising
once any column is projected away; blank lines read as all-null rows;
backslash-escaped quotes mangled; Latin bytes that form valid UTF-8 read as
if they were UTF-8; a wrong row count after a lone quote; a very small zip or
bzip2 file read as empty.

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

## Answer

Resolved 2026-10-06 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn. The full key list, generated from the
code, is the component's page under `docs/v2/components/`
(`.venv/bin/python scripts/gen_v2_docs.py`).

- Every key the converter emits is declared. Supported with v1's defaults:
  `path` (v1 `filepath`), `delimiter` (v1 `fieldseparator`), `row_separator`,
  `csv_row_separator`, `header_rows`, `footer_rows`, `limit`, `encoding`
  (default ISO-8859-15), `csv_option`, `text_enclosure`, `escape_char`,
  `remove_empty_row`, `trim_all`, `trim_select`, `check_fields_num`,
  `die_on_error` (default false, as v1's reader).
- Ignored, because v1 ignores them too: `uncompress`, `split_record`,
  `random`, `nb_random`, `advanced_separator`, `thousands_separator`,
  `decimal_separator`, `enable_decode`, `decode_cols`; and `check_date`
  (dates are always checked against their pattern).
- Refused values: a row separator other than `\n`, `\r\n`, `\r`; an
  `escape_char` other than the enclosure; `check_fields_num` with
  `csv_option`; a reader with no schema.
- How it is built: every field is read as text by Polars' lazy reader and
  turned into its declared type by expressions, so an unreadable field is a
  rejected row (`errorCode`, `errorMessage` in v1's words), never a failed
  read. A delimiter of several characters and the field-count check go
  through a slower line-splitting path. A footer costs one fast line count.
- Tests: `tests/v2/components/test_file_delimited.py`; most of them run the
  same job on v1 and on v2 and compare the bytes written.
