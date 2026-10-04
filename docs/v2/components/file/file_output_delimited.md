# FileOutputDelimited (tFileOutputDelimited)

## Purpose

Write data to delimited text files (CSV, TSV, custom separators) by collecting a Polars LazyFrame and writing to disk. Equivalent of Talend **tFileOutputDelimited**. Supports append mode with header suppression, CSV quoting with four quote styles, delete-empty-file, error-if-exists, and schema-based column selection/ordering.

**Component type:** `file_output_delimited`
**Base class:** `SinkComponent`
**Category:** `file`
**Registry name:** `file_output_delimited`

## When to Use

Use FileOutputDelimited when you need to:
- Write pipeline output to CSV, TSV, or custom-delimited text files
- Append data to an existing file without duplicating the header row
- Control quoting behavior (RFC4180, always, never, or non-numeric)
- Skip writing empty result sets (`delete_empty_file`)
- Guard against accidental overwrites (`error_if_exists`)
- Select and reorder columns at write time via schema

Do **not** use for Parquet output (use FileOutputParquet) or binary formats.

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | (required) | Output file path. Supports `${context.var}` placeholder substitution. Parent directories are created automatically. |
| `delimiter` | string | `","` | Field delimiter. Must be a single character. Use `"\\t"` for TSV. |
| `line_terminator` | string | `"\n"` | Row separator. Supports `"\r\n"` and `"\r"`. |
| `has_header` | boolean | `true` | Write header row. **v2 default is `true`; Talend default is `false` (INCLUDEHEADER).** |
| `append` | boolean | `false` | Append to existing file. Header is suppressed when appending to an existing file. Cannot be combined with `error_if_exists`. |
| `null_value` | string | `""` | String written for null values. |
| `quote_char` | string | `"\""` | Quote character. Must be a single character. |
| `quote_style` | string | `"necessary"` | Quoting strategy. One of: `necessary`, `always`, `never`, `non_numeric`. See below. |
| `datetime_format` | string | (optional) | Format string for datetime columns (e.g., `"%Y-%m-%d %H:%M:%S"`). |
| `date_format` | string | (optional) | Format string for date columns (e.g., `"%Y-%m-%d"`). |
| `delete_empty_file` | boolean | `false` | Skip writing entirely if the collected DataFrame has 0 data rows. |
| `error_if_exists` | boolean | `false` | Raise `FileExistsError` if the output file already exists. **v2 default is `false`; Talend default is `true` (FILE_EXIST_EXCEPTION).** Cannot be combined with `append`. |
| `schema` | list | (optional) | Column selection and ordering. When defined, only schema columns are written in schema order. Format: `[{"name": "col_name"}]`. |
| `label` | string | (optional) | Display label for debugging and logging. |

### Quote Style Options

| Style | Behavior |
|-------|----------|
| `necessary` | Quote only values that contain the delimiter, quote character, or newlines (default, RFC4180-compliant). |
| `always` | Wrap every value in quote characters, regardless of content. |
| `never` | Never quote any value. Use only when data is guaranteed to contain no special characters. |
| `non_numeric` | Quote all non-numeric values (strings, dates, booleans) while leaving integers and floats unquoted. This is commonly needed by downstream systems that parse numeric fields without quotes, and is a strength of the Polars writer. The `non_numeric` option has no direct Talend equivalent -- it is a v2 enhancement. |

## Outputs

None. `FileOutputDelimited` is a `SinkComponent` -- it returns an empty dict from `apply()`. Data is written to disk as a side effect.

## v2-Native Defaults vs Talend Defaults

| Parameter | v2 Default | Talend Default | Note |
|-----------|-----------|----------------|------|
| `delimiter` | `,` (comma) | `;` (semicolon) | Industry-standard CSV |
| `has_header` | `true` | `false` (INCLUDEHEADER) | v2 includes header by default |
| `null_value` | `""` (empty string) | N/A | Empty string for nulls |
| `line_terminator` | `\n` | `\n` | Same |
| `error_if_exists` | `false` | `true` (FILE_EXIST_EXCEPTION) | v2 allows overwrite by default |

**Note:** The `talend_to_v2` converter always emits explicit values extracted from the Talend XML (delimiter, has_header, line_terminator, error_if_exists, etc.), so converted jobs get correct Talend behavior regardless of v2 defaults. Only hand-written v2-native jobs use the modern defaults (per D-04).

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
| `FileOutputDelimitedFeature.filename` | full | File path with ${context.var} placeholder substitution |
| `FileOutputDelimitedFeature.fieldseparator` | full | Single-byte field delimiter passed to Polars separator parameter |
| `FileOutputDelimitedFeature.rowseparator` | full | Line terminator passed to Polars line_terminator parameter |
| `FileOutputDelimitedFeature.append` | full | Append mode with header suppression when appending to existing file |
| `FileOutputDelimitedFeature.includeheader` | full | Polars include_header parameter on write_csv |
| `FileOutputDelimitedFeature.create_dir` | full | Auto-create parent directories via Path.mkdir(parents=True) |
| `FileOutputDelimitedFeature.csv_option` | full | quote_char + quote_style mapped from TEXT_ENCLOSURE and CSV_OPTION |
| `FileOutputDelimitedFeature.delete_emptyfile` | full | Skip writing when 0 data rows |
| `FileOutputDelimitedFeature.file_exist_exception` | full | Raise FileExistsError when output file exists and append=False |
| `FileOutputDelimitedFeature.csvrowseparator` | full | CLOSED_LIST row separator mapped to line_terminator when CSV_OPTION=true |
| `FileOutputDelimitedFeature.label` | full | Component label for display/debugging |
| `FileOutputDelimitedFeature.schema_selection` | full | Schema-based column selection and ordering on write |
| `FileOutputDelimitedFeature.null_value` | full | Polars null_value parameter on write_csv |
| `FileOutputDelimitedFeature.datetime_format` | full | Polars datetime_format parameter on write_csv |
| `FileOutputDelimitedFeature.date_format` | full | Polars date_format parameter on write_csv |
| `FileOutputDelimitedFeature.escape_char` | partial | Polars uses RFC4180 quote doubling; custom escape characters not supported |
| `FileOutputDelimitedFeature.compress` | unsupported | Polars cannot write ZIP-compressed CSV; use gzip post-processing |
| `FileOutputDelimitedFeature.split_every` | unsupported | Polars has no native file splitting; split post-processing |
| `FileOutputDelimitedFeature.advanced_separator` | unsupported | Locale-aware numeric formatting (THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR) not available in Polars |
| `FileOutputDelimitedFeature.encoding_non_utf8` | unsupported | Polars writes UTF-8 only; pre-convert or transcode downstream |
| `FileOutputDelimitedFeature.usestream` | not_planned | Java OutputStream sink has no Python equivalent |
| `FileOutputDelimitedFeature.flushonrow` | not_planned | Polars manages write buffering internally |
| `FileOutputDelimitedFeature.row_mode` | not_planned | Polars manages write buffering internally |
| `FileOutputDelimitedFeature.os_line_separator` | not_planned | v2 uses explicit line_terminator config |
| `FileOutputDelimitedFeature.tstatcatcher_stats` | not_planned | tStatCatcher is a v1/Talend concept; use Python logging instead |
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `compress` (COMPRESS) | UNSUPPORTED | Polars cannot write ZIP-compressed CSV. Use gzip post-processing or downstream compression tooling. |
| `split_every` (SPLIT/SPLIT_EVERY) | UNSUPPORTED | Polars has no native file splitting. Split files via post-processing or downstream tooling. |
| `advanced_separator` (ADVANCED_SEPARATOR) | UNSUPPORTED | Locale-aware numeric formatting (THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR) is not available in Polars. Use downstream expression transforms for locale-specific number formatting. |
| `encoding_non_utf8` (ENCODING) | UNSUPPORTED | Polars always writes UTF-8. Talend default `ISO-8859-15` is not supported. If downstream systems require a different encoding, use post-write transcoding (e.g., `iconv`). |
| `usestream` (USESTREAM) | NOT_PLANNED | Java `OutputStream` concept has no Python equivalent. |
| `flushonrow` (FLUSHONROW) | NOT_PLANNED | Polars manages write buffering internally. No meaningful equivalent. |
| `row_mode` (ROW_MODE) | NOT_PLANNED | Atomic per-row flush is a Java I/O concept. Same rationale as FLUSHONROW. |
| `os_line_separator` (OS_LINE_SEPARATOR) | NOT_PLANNED | v2 uses explicit `line_terminator` config. The converter ignores this Talend flag and uses ROWSEPARATOR/CSVROWSEPARATOR directly. |
| `tstatcatcher_stats` (TSTATCATCHER_STATS) | NOT_PLANNED | tStatCatcher is a v1/Talend concept. Use Python logging for observability in v2. |

## Talend Differences

| Aspect | Talend tFileOutputDelimited | v2 FileOutputDelimited |
|--------|----------------------------|------------------------|
| **Encoding** | Default `ISO-8859-15`; supports Latin-1, Windows-1252, etc. | UTF-8 only. Polars always writes UTF-8. Downstream transcoding required for non-UTF-8 consumers. |
| **INCLUDEHEADER default** | `false` -- Talend omits headers by default | `has_header=true` -- v2 includes headers by default. The converter always emits the explicit Talend value. |
| **FILE_EXIST_EXCEPTION default** | `true` -- Talend raises an error if the output file exists | `error_if_exists=false` -- v2 allows overwrite by default. The converter always emits the explicit Talend value. |
| **ESCAPE_CHAR** | Separate ESCAPE_CHAR parameter independent of TEXT_ENCLOSURE | Polars uses RFC4180 quote doubling (the quote character is doubled to escape itself). Custom escape characters different from the quote character are not supported. If Talend `ESCAPE_CHAR != TEXT_ENCLOSURE`, the converter warns. |
| **Append mode header** | Header suppressed when appending to existing file | Same behavior: v2 suppresses header when appending to an existing file. |
| **CSVROWSEPARATOR** | CLOSED_LIST values: `LF`, `CR`, `CRLF` | Mapped from Talend CLOSED_LIST to actual `line_terminator` characters (`"\n"`, `"\r"`, `"\r\n"`). Applied when CSV_OPTION is enabled. |
| **Separator default** | `;` (semicolon, European convention) | `,` (comma, industry standard). Converter always emits explicit value from Talend XML. |
| **Write approach** | Java `BufferedWriter` with per-row flush options | Uses `DataFrame.write_csv()` (collect then write). Not `LazyFrame.sink_csv()`, because append mode, delete_empty_file, error_if_exists, and schema selection all require the collected DataFrame. |
| **Quote styles** | CSV_OPTION toggles quoting on/off (binary choice) | v2 supports four `quote_style` options: `necessary` (RFC4180), `always`, `never`, and `non_numeric`. The `non_numeric` option is a v2 enhancement with no direct Talend equivalent -- it quotes all non-numeric values while leaving integers and floats unquoted. |
| **tStatCatcher** | Supported via Talend framework | Not planned. Use Python logging. |

## Performance Notes

- **SinkComponent barrier:** FileOutputDelimited always collects the LazyFrame (`is_barrier=True`). Write throughput is dominated by the Polars `write_csv()` C++ implementation.
- **Append mode overhead:** When appending, data is written to bytes via `write_csv(None)` then binary-appended to the file. This adds a small overhead for the in-memory buffer and file I/O.
- **Schema column selection:** When a schema is defined, `DataFrame.select()` filters and reorders columns before write. This is a lightweight Polars operation.
- **Quoting overhead:** The `always` and `non_numeric` quote styles add marginal overhead for wrapping values. The `necessary` style (default) incurs quoting cost only for values containing special characters.
- **Directory creation:** `Path.mkdir(parents=True, exist_ok=True)` runs once per write. Negligible cost.

## Examples

### Basic Write (Minimal Config)

```json
{
    "name": "write_output",
    "components": [
        {
            "id": "writer",
            "type": "file_output_delimited",
            "config": {
                "path": "output/results.csv"
            }
        }
    ],
    "flows": []
}
```

With default settings, this writes all columns with a header row, comma delimiter, and RFC4180 quoting (quote only when necessary).

### Append Mode with Header Suppression

```json
{
    "name": "append_daily_data",
    "components": [
        {
            "id": "writer",
            "type": "file_output_delimited",
            "config": {
                "path": "${context.output_file}",
                "append": true,
                "has_header": true,
                "delimiter": ","
            }
        }
    ],
    "flows": []
}
```

When the output file already exists, append mode writes data without a duplicate header row. When the file does not exist, it creates it with a header.

### CSV Quoting with non_numeric Quote Style

```json
{
    "name": "write_quoted_output",
    "components": [
        {
            "id": "writer",
            "type": "file_output_delimited",
            "config": {
                "path": "output/quoted_results.csv",
                "quote_char": "\"",
                "quote_style": "non_numeric",
                "null_value": "N/A"
            }
        }
    ],
    "flows": []
}
```

The `non_numeric` quote style wraps all string, date, and boolean values in double quotes while leaving integer and float values unquoted. This produces output like:

```
"name","city",amount,id
"Alice","New York",150.75,1
"Bob","Los Angeles",200.00,2
```

This is commonly needed by downstream systems that parse numeric fields without quotes.

## Benchmark Results

<!-- GENERATED: benchmarks -->
_No benchmark baseline committed yet._
<!-- /GENERATED: benchmarks -->

FileOutputDelimited's primary overhead vs raw `DataFrame.write_csv()` comes from:
1. Path resolution and context variable substitution
2. Parent directory creation check (`mkdir`)
3. Error-if-exists file existence check
4. Schema column selection (`DataFrame.select()`)
5. Append mode header suppression and binary file append

For simple writes (no append, no schema, no error_if_exists), overhead is minimal -- dominated by the Polars C++ write implementation.
