# FileInputDelimited

## Purpose

Read delimited text files (CSV, TSV, custom separators) as a Polars LazyFrame. Equivalent of Talend **tFileInputDelimited**. Supports schema-driven typing, NaN-to-null normalization, per-column trim, footer skip, and reject flow for bad data.

**Component type:** `file_input_delimited`
**Base class:** `SourceComponent`
**Category:** `file`
**Registry name:** `file_input_delimited`

## When to Use

Use FileInputDelimited when you need to:
- Read CSV, TSV, or custom-delimited text files into the v2 pipeline
- Apply schema-driven type enforcement at read time (not Polars inference)
- Normalize NaN strings to null for consistent downstream processing
- Route parse-level or schema-level bad data to a reject output
- Trim whitespace globally or per-column at read time

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | (required) | File path. Supports `${context.var}` placeholder substitution. |
| `delimiter` | string | `","` | Field separator. Must be a single byte. Use `"\\t"` for TSV. |
| `quote_char` | string\|null | `"\""` | CSV quoting character. Set to `null` to disable quoting entirely. |
| `has_header` | boolean | `true` | Whether the file has a header row. |
| `skip_rows` | integer | `0` | Number of rows to skip at start (after header). |
| `footer_rows` | integer | `0` | Number of rows to skip at end. **Forces eager read** (`read_csv` instead of `scan_csv`). See Performance Notes. |
| `limit` | integer\|null | `null` | Maximum rows to return. `0` = zero rows. `null` = all rows. |
| `skip_empty_rows` | boolean | `false` | Filter out rows where all fields are null or empty string. |
| `trim_all` | boolean | `false` | Strip leading/trailing whitespace from all string columns. |
| `trim_columns` | list\|null | `null` | Per-column trim. List of `{"column": "name", "trim": "both"\|"left"\|"right"}`. Only applied when `trim_all` is `false`. |
| `encoding` | string | `"utf8"` | File encoding. Must be `"utf8"` or `"utf8-lossy"`. Any other value fails validation. |
| `die_on_error` | boolean | `true` | `true` = crash on bad data. `false` = route bad rows to reject output. When `false`, also sets `ignore_errors=True` on the Polars CSV reader so parse-level errors produce nulls instead of crashing. |
| `nan_is_null` | boolean | `true` | Convert `NaN`/`nan`/`NAN` strings to null at read time. Set `false` to preserve IEEE 754 float NaN. |
| `eol_char` | string\|null | `null` | Custom end-of-line character. Default uses Polars auto-detection (`\n` with `\r\n` support). |
| `schema` | list | (required) | Column definitions: `[{"name": "col", "type": "string\|integer\|float\|boolean\|date\|datetime", "date_pattern": "..."}]`. `date_pattern` required for date/datetime columns. |
| `label` | string\|null | `null` | Display label for debugging. |

## Outputs

| Output | Description |
|--------|-------------|
| `main` | All rows (when `die_on_error=true`) or good rows (when `die_on_error=false`). |
| `reject` | Bad rows with `_error_message` column. Only emitted when `die_on_error=false` and schema validation failures occur. |

## Schema Enforcement

FileInputDelimited **always** builds `schema_overrides` from the config `schema` -- it never relies on Polars type inference. This is critical for ETL correctness: Polars inference can produce unexpected types (e.g., inferring Int64 for a column that should be String, or Float64 for an Integer column with missing values).

**When `die_on_error=true` (default):**
- Typed columns use their target Polars types in `schema_overrides` (e.g., `pl.Int64`, `pl.Float64`, `pl.Utf8`)
- Date/datetime columns are read as `pl.Utf8` first, then parsed lazily via `str.to_date()` / `str.to_datetime()` with the configured `date_pattern`
- Invalid data causes a Polars parse error (crash) -- expected behavior for strict mode

**When `die_on_error=false`:**
- **All** columns are read as `pl.Utf8` via `schema_overrides` (safe mode)
- `ignore_errors=True` is passed to the Polars CSV reader so parse-level errors (malformed rows, wrong field counts) produce null values instead of crashing
- `SourceComponent._validate_schema()` then casts each column with `strict=False`, routing rows that fail casting to the `reject` output with an `_error_message` column

This two-layer approach (parse-level `ignore_errors` + schema-level `_validate_schema()`) ensures that **both** malformed CSV rows and type-mismatch values are captured and routed to reject rather than crashing the pipeline.

## v2-Native Defaults vs Talend Defaults

| Parameter | v2 Default | Talend Default | Rationale |
|-----------|-----------|----------------|-----------|
| `delimiter` | `,` (comma) | `;` (semicolon) | Industry standard CSV |
| `encoding` | `utf8` | `ISO-8859-15` | Polars native UTF-8 only |
| `skip_empty_rows` | `false` | `true` | Explicit opt-in; v2 preserves all rows by default |
| `nan_is_null` | `true` | N/A | Talend reads NaN as null natively; Polars reads NaN as float NaN -- normalization matches Talend behavior |

**Note:** The `talend_to_v2` converter always emits explicit values extracted from the Talend XML, so converted jobs get correct Talend behavior regardless of v2 defaults. Only hand-written v2-native jobs use the modern defaults.

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
| `FileInputDelimitedFeature.advanced_separator` | unsupported | Locale-aware numeric parsing (THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR) not available in Polars |
| `FileInputDelimitedFeature.check_date` | not_planned | Date validation handled by schema typing via date_pattern |
| `FileInputDelimitedFeature.check_fields_num` | not_planned | Polars truncate_ragged_lines has different semantics; not mapped |
| `FileInputDelimitedFeature.csv_option` | partial | quote_char supported; ESCAPE_CHAR separate from TEXT_ENCLOSURE not supported |
| `FileInputDelimitedFeature.die_on_error` | full | True=crash on bad data; False=route to reject via SourceComponent._validate_schema() |
| `FileInputDelimitedFeature.enable_decode` | not_planned | Hex/octal decoding has no Polars native support |
| `FileInputDelimitedFeature.encoding_non_utf8` | unsupported | Only utf8 and utf8-lossy supported; pre-convert non-UTF-8 files |
| `FileInputDelimitedFeature.fieldseparator` | full | Single-byte field delimiter passed to Polars separator parameter |
| `FileInputDelimitedFeature.filename` | full | File path with ${context.var} placeholder substitution |
| `FileInputDelimitedFeature.footer` | full | footer_rows triggers eager read path (must count total rows) |
| `FileInputDelimitedFeature.header` | full | has_header + skip_rows for multi-row headers |
| `FileInputDelimitedFeature.label` | full | Component label for display/debugging |
| `FileInputDelimitedFeature.limit` | full | n_rows parameter on scan_csv; limit=0 returns zero rows |
| `FileInputDelimitedFeature.multi_char_separator` | unsupported | Polars requires single-byte field separator |
| `FileInputDelimitedFeature.random` | not_planned | Use downstream sampling expressions instead |
| `FileInputDelimitedFeature.reject_flow` | full | die_on_error=False + SourceComponent._validate_schema() splits main/reject |
| `FileInputDelimitedFeature.remove_empty_row` | full | Filter rows where all fields are null or empty string |
| `FileInputDelimitedFeature.rowseparator` | full | Mapped to Polars eol_char parameter (single-byte only) |
| `FileInputDelimitedFeature.schema_opt_num` | not_planned | Talend Studio UI feature; not applicable to engine execution |
| `FileInputDelimitedFeature.schema_typing` | full | schema_overrides built from config schema; never Polars inference |
| `FileInputDelimitedFeature.splitrecord` | not_planned | Polars quote_char handles embedded newlines per RFC4180 |
| `FileInputDelimitedFeature.trimall` | full | Strip whitespace from all string/date columns via str.strip_chars() |
| `FileInputDelimitedFeature.trimselect` | full | Per-column trim via str.strip_chars()/strip_chars_start()/strip_chars_end() |
| `FileInputDelimitedFeature.tstatcatcher_stats` | not_planned | tStatCatcher is a v1/Talend concept; use Python logging instead |
| `FileInputDelimitedFeature.uncompress` | partial | gzip (.gz) auto-detected by Polars; ZIP archives unsupported |
| `FileInputDelimitedFeature.use_header_as_is` | not_planned | Polars reads headers natively; no Studio UI hook needed |
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `encoding_non_utf8` | UNSUPPORTED | Polars only supports UTF-8. Pre-convert non-UTF-8 files to UTF-8 before reading, or use a dedicated encoding component. The `talend_to_v2` converter warns when the source encoding is not UTF-8. |
| `advanced_separator` | UNSUPPORTED | Locale-aware numeric parsing (THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR) is not available in Polars. Use downstream expression transforms for locale-specific number parsing. |
| `multi_char_separator` | UNSUPPORTED | Polars requires a single-byte field separator. Multi-character and regex separators cannot be mapped. Pre-process the file or use a dedicated parser. |
| `csv_option` (partial) | PARTIAL | `quote_char` is fully supported. `ESCAPE_CHAR` as a separate character from `TEXT_ENCLOSURE` is not supported -- Polars treats the quote character as both enclosure and escape (RFC4180 doubling). |
| `uncompress` (partial) | PARTIAL | gzip (`.gz`) files are auto-detected by Polars. ZIP archives with multiple entries are not supported. |
| `random` | NOT_PLANNED | Use downstream `sample()` expressions instead. |
| `enable_decode` | NOT_PLANNED | Hex/octal decoding has no Polars native support. |
| `splitrecord` | NOT_PLANNED | Polars `quote_char` handles embedded newlines per RFC4180 natively. |
| `tstatcatcher_stats` | NOT_PLANNED | tStatCatcher is a v1/Talend concept. Use Python logging for observability in v2. |

## Talend Differences

| Aspect | Talend tFileInputDelimited | v2 FileInputDelimited |
|--------|---------------------------|----------------------|
| **Encoding** | Default `ISO-8859-15`; supports Latin-1, Shift-JIS, etc. | UTF-8 only (`utf8` or `utf8-lossy`). Pre-convert non-UTF-8 files. |
| **NaN vs Null** | Reads `"NaN"` string as null natively in most contexts | Polars reads `"NaN"` as float NaN. v2 normalizes to null by default (`nan_is_null=true`). Set `nan_is_null=false` for IEEE 754 NaN preservation. |
| **Separator default** | `;` (semicolon, European convention) | `,` (comma, industry standard). Converter always emits explicit value from XML. |
| **Separator types** | Single char, multi-char, and regex separators | Single-byte only. Multi-char and regex UNSUPPORTED. |
| **Footer** | Streams with row counter | `footer_rows > 0` forces eager `read_csv` (entire file loaded into memory). `SourceComponent.produce()` wraps the resulting DataFrame in `.lazy()` before returning to the pipeline, so downstream components always receive LazyFrame. |
| **CSV quoting** | Separate TEXT_ENCLOSURE and ESCAPE_CHAR | Polars `quote_char` handles RFC4180 quoting natively. No separate escape character. |
| **REJECT flow** | Direct per-row reject during read | Two-layer: `ignore_errors=True` catches parse-level errors as nulls; `_validate_schema()` catches type-mismatch errors. Both route to reject output. Dynamic barrier: `die_on_error=false` forces `.collect()` for schema validation. |
| **Row separator** | `ROWSEPARATOR` with any character | `eol_char` supports custom single-byte EOL. Polars is optimized for `\n` and `\r\n`; non-standard separators may cause slower parsing. |
| **skip_empty_rows default** | `true` | `false`. Explicit opt-in in v2. |
| **Schema enforcement** | Type coercion per-column via Java | `schema_overrides` always built from config (never Polars inference). Dates read as Utf8 then parsed lazily. |
| **tStatCatcher** | Supported via Talend framework | Not planned. Use Python logging. |

## Performance Notes

- **Lazy path (default):** Uses `pl.scan_csv()` for full Polars query optimization and predicate pushdown. Zero overhead from `nan_is_null` -- Polars applies `null_values` at parse time natively.
- **Eager path (`footer_rows > 0`):** Uses `pl.read_csv()`, loading the entire file into memory. `SourceComponent.produce()` wraps the result in `.lazy()` for pipeline compatibility. Benchmark separately for footer-heavy workloads.
- **Reject path (`die_on_error=false`):** Forces materialization for schema validation via `_validate_schema()`. Sets `ignore_errors=True` on the CSV reader. Multi-output barrier cost applies (two outputs trigger engine barrier materialization).
- **Schema enforcement:** `schema_overrides` always set from config (never Polars inference). Zero overhead -- Polars applies overrides at parse time. Date/datetime columns read as Utf8 then parsed lazily in the query plan.
- **Trim:** Both `trim_all` and `trim_columns` use vectorized Polars `str.strip_chars()` expressions. Zero Python callback overhead.

## Examples

### Basic CSV Read with Schema

```json
{
    "name": "read_customers",
    "components": [
        {
            "id": "reader",
            "type": "file_input_delimited",
            "config": {
                "path": "data/customers.csv",
                "delimiter": ",",
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "email", "type": "string"},
                    {"name": "balance", "type": "float"}
                ]
            }
        }
    ],
    "flows": []
}
```

### CSV with NaN Handling and Reject Output

```json
{
    "name": "read_with_reject",
    "components": [
        {
            "id": "reader",
            "type": "file_input_delimited",
            "config": {
                "path": "${context.input_file}",
                "delimiter": ",",
                "die_on_error": false,
                "nan_is_null": true,
                "schema": [
                    {"name": "sensor_id", "type": "integer"},
                    {"name": "reading", "type": "float"},
                    {"name": "timestamp", "type": "datetime", "date_pattern": "%Y-%m-%d %H:%M:%S"}
                ]
            }
        },
        {
            "id": "good_data",
            "type": "filter_rows",
            "config": {
                "condition": "reading > 0"
            }
        }
    ],
    "flows": [
        {"from": "reader", "to": "good_data", "from_connector": "main", "to_connector": "main"}
    ]
}
```

### TSV with Per-Column Trim and Footer Skip

```json
{
    "name": "read_tsv_trimmed",
    "components": [
        {
            "id": "reader",
            "type": "file_input_delimited",
            "config": {
                "path": "data/report.tsv",
                "delimiter": "\\t",
                "footer_rows": 3,
                "trim_columns": [
                    {"column": "name", "trim": "both"},
                    {"column": "city", "trim": "right"}
                ],
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "city", "type": "string"},
                    {"name": "score", "type": "float"}
                ]
            }
        }
    ],
    "flows": []
}
```

## Benchmark Results

<!-- GENERATED: benchmarks -->
_No benchmark baseline committed yet._
<!-- /GENERATED: benchmarks -->

FileInputDelimited's primary overhead vs raw `pl.scan_csv()` comes from:
1. Schema override construction (one-time dict build per read)
2. Column renaming (positional mapping to schema names)
3. NaN-to-null normalization (zero-cost: applied at Polars parse time via `null_values`)
4. Trim expressions (vectorized Polars operations, composable in lazy plan)

The eager path (`footer_rows > 0`) adds full-file materialization cost. The reject path (`die_on_error=false`) adds schema validation materialization cost. Both are benchmarked separately.
