# 02 - Polars facts: reading and writing delimited files

Status: open
Type: research

## Question

What can Polars read and write natively for delimited files, lazily
(`scan_csv`, `sink_csv`) and eagerly (`read_csv`, `write_csv`)? Primary
sources only, stamped against the range this repo pins (`polars>=1.38,<2.0`;
1.44.2 is installed), with the version noted wherever behaviour changed inside
that range.

Specifically:

1. Encodings: which are accepted lazily and which eagerly; what happens to
   non-UTF-8 bytes in each; the documented way to read ISO-8859-15 / Latin-1
   and what it costs (is the whole file decoded in Python, is it held in
   memory); the same for writing.
2. Separators and line endings: multi-character field separators, custom and
   multi-character row separators, CRLF.
3. Quoting and escaping: quote character, an escape character distinct from
   the quote character, quote styles on write, embedded newlines.
4. Nulls and empties: how an empty unquoted field, a quoted empty string and
   `null_values` are read for each dtype; `missing_utf8_is_empty_string`; how
   nulls and empty strings are written.
5. Row limits that stay lazy: header and skipped rows, `n_rows`, skipping
   footer rows, row index, counting rows.
6. Ragged lines: too many or too few fields; `truncate_ragged_lines`,
   `ignore_errors`.
7. Number and date text: decimal comma and thousands separators on read;
   float formatting on write (`float_precision`, `float_scientific`); date
   and datetime formats on read and write.
8. Compression: reading and writing gzip and zip.

For each: the API, whether it keeps the query lazy, and what it costs when it
does not.

Feeds [The performance bar](05-performance-bar.md),
[Types, nulls and schemas](13-types-nulls-and-schemas.md),
[Encoding: what to do about ISO-8859-15](14-encoding-iso-8859-15.md) and the
two delimited-file key tickets
([input](20-config-keys-delimited-file-input.md),
[output](21-config-keys-delimited-file-output.md)).
