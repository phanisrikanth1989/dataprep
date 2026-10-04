# Component Reference

Complete reference for all built-in v2 engine components.

## Table of Contents

1. [Component Types Overview](#component-types-overview)
2. [Source Components](#source-components)
3. [Transform Components](#transform-components)
4. [Aggregate Components](#aggregate-components)
5. [Sink Components](#sink-components)
6. [Utility Components](#utility-components)

---

## Component Types Overview

| Category | Components | Description |
|----------|------------|-------------|
| **Source** | `file_input`, `file_input_excel`, `file_input_full_row` | Produce data, no inputs |
| **Transform** | `map`, `filter`, `select`, `sort` | Transform data |
| **Aggregate** | `aggregate`, `unique` | Group and deduplicate |
| **Sink** | `file_output`, `file_output_parquet` | Consume data, no outputs |
| **Utility** | `union`, `context_load` | Combine inputs, load context |
| **Python** | `python_code`, `python_row`, `python_dataframe` | Custom Python code |

---

## Source Components

### FileInput / FileInputDelimited

Read delimited files (CSV, TSV, etc.) with explicit schema.

**Type aliases:** `file_input`, `file_input_delimited`, `file_input_csv`

```json
{
    "type": "file_input",
    "config": {
        "path": "${context.input_dir}/orders.csv",
        "delimiter": ",",
        "quote_char": "\"",
        "has_header": true,
        "skip_rows": 0,
        "footer_rows": 0,
        "limit": null,
        "skip_empty_rows": false,
        "trim_all": false,
        "encoding": "utf8",
        "die_on_error": true,
        "schema": [
            {"name": "order_id", "type": "integer"},
            {"name": "customer_id", "type": "string"},
            {"name": "amount", "type": "float"},
            {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"}
        ]
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | required | File path (supports `${context.var}`) |
| `schema` | list | required | Column definitions (see below) |
| `delimiter` | string | `","` | Field delimiter |
| `quote_char` | string\|null | `"\""` | CSV quoting character. `null` disables quoting |
| `has_header` | bool | `true` | Whether file has a header row |
| `skip_rows` | int | `0` | Rows to skip at start of file |
| `footer_rows` | int | `0` | Rows to skip at end of file. When > 0, triggers eager read (performance note for large files) |
| `limit` | int\|null | `null` | Max rows to return. `null` = unlimited. `0` = zero rows (not unlimited) |
| `skip_empty_rows` | bool | `false` | Filter out rows where all fields are null or empty string. Note: whitespace-only fields are NOT considered empty — use `trim_all` first if needed |
| `trim_all` | bool | `false` | Strip leading/trailing whitespace from all string columns |
| `encoding` | string | `"utf8"` | File encoding |
| `die_on_error` | bool | `true` | When false, routes rows with schema cast failures to reject output instead of crashing |

**Notes:**
- Schema is required. Column names from schema override file header names positionally.
- When `footer_rows > 0`, the file is read eagerly (`pl.read_csv`) instead of lazily (`pl.scan_csv`).
- `limit: 0` means zero rows, not unlimited. `null` means unlimited.

**Schema Column Definition:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Column name |
| `type` | string | yes | Column type (see types below) |
| `date_pattern` | string | for date/datetime | Format pattern (e.g. `"%Y-%m-%d"`, `"%d/%m/%Y"`) |

**Schema Types:**

| Type | Aliases | Polars Type | Description |
|------|---------|-------------|-------------|
| `string` | `str`, `id_String` | `Utf8` | Text |
| `integer` | `int`, `long`, `id_Integer`, `id_Long` | `Int64` | Whole numbers |
| `float` | `double`, `id_Float`, `id_Double` | `Float64` | Decimal numbers |
| `boolean` | `bool`, `id_Boolean` | `Boolean` | True/false |
| `date` | `id_Date` | `Date` | Date (requires `date_pattern`) |
| `datetime` | - | `Datetime` | DateTime (requires `date_pattern`) |
| `decimal` | `id_BigDecimal` | `Utf8` | High-precision decimal (stored as string) |

---

### FileInputExcel

Read Excel files (.xlsx, .xls, .xlsb).

**Type alias:** `file_input_excel`

```json
{
    "type": "file_input_excel",
    "config": {
        "path": "${context.input_dir}/data.xlsx",
        "sheet": "Orders",
        "has_header": true,
        "skip_rows": 0,
        "footer_rows": 0,
        "limit": null,
        "first_column": null,
        "last_column": null,
        "skip_empty_rows": false,
        "trim_all": false,
        "die_on_error": true,
        "schema": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
            {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"}
        ]
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | required | Excel file path |
| `schema` | list | required | Column definitions (see Schema below) |
| `sheet` | string/int | first sheet | Single sheet by name or 0-based index |
| `all_sheets` | bool | `false` | Read all sheets, concatenated |
| `sheets` | list | - | Sheet selection list (see Sheet Selection below) |
| `has_header` | bool | `true` | Whether first row is a header |
| `skip_rows` | int | `0` | Rows to skip after header |
| `footer_rows` | int | `0` | Rows to skip at end of each sheet |
| `limit` | int\|null | `null` | Max rows per sheet. `null` = unlimited. `0` = zero rows |
| `first_column` | int\|null | `null` | First column to read (1-based). `null` = first column |
| `last_column` | int\|null | `null` | Last column to read (1-based, inclusive). `null` = all |
| `skip_empty_rows` | bool | `false` | Filter out rows where all fields are null or empty. Whitespace-only fields are treated as empty for Excel |
| `trim_all` | bool | `false` | Strip whitespace from all string columns |
| `die_on_error` | bool | `true` | When false, routes rows with schema cast failures to reject output instead of crashing |

**Notes:**
- Schema is required. Column names from schema override file header names positionally.
- Excel is always read eagerly (no lazy scanning). The result is wrapped as LazyFrame for downstream.
- `limit: 0` means zero rows, not unlimited. `null` means unlimited.
- When reading multiple sheets, `footer_rows`, `limit`, `skip_rows`, and column range are applied per-sheet before concatenation.

**Sheet Selection:**

Priority: `all_sheets` > `sheets` > `sheet` > default (first sheet).

```json
"sheets": [
    {"name": "Sales"},
    {"name": "Data_\\d+", "regex": true},
    {"index": 2}
]
```

Each entry has either `name` (exact or regex) or `index` (0-based). Set `"regex": true` to match sheet names by pattern.

---

### FileInputFullRow

Read a text file line by line. Each line becomes a single string record — no field parsing. Useful for files with mixed record types (header/detail/trailer) or preprocessing before field extraction.

**Type aliases:** `file_input_full_row`, `file_input_full`

```json
{
    "type": "file_input_full_row",
    "config": {
        "path": "${context.input_dir}/mixed_records.txt",
        "header_rows": 1,
        "footer_rows": 1,
        "skip_empty_rows": true,
        "encoding": "utf8",
        "schema": [
            {"name": "line", "type": "string"}
        ]
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | required | File path (supports `${context.var}`) |
| `schema` | list | required | Single column of type `string` |
| `header_rows` | int | `0` | Rows to skip at start |
| `footer_rows` | int | `0` | Rows to skip at end |
| `limit` | int | `null` | Max rows to read |
| `skip_empty_rows` | bool | `false` | Exclude blank lines |
| `encoding` | string | `"utf8"` | File encoding |
| `die_on_error` | bool | `true` | Standard error handling |

**Note:** Schema must have exactly 1 column of type `string`. The column name is user-defined (commonly `line`).

---

## Transform Components

### Map

Transform columns with expressions. Supports lookups, match modes, and multi-output routing.

**Type aliases:** `map`

```json
{
    "type": "map",
    "config": {
        "lookups": [
            {
                "name": "customers",
                "input": "lookup_customers",
                "keys": [{"main": "customer_id", "lookup": "id"}],
                "join_type": "left",
                "match_mode": "first"
            }
        ],
        "variables": [
            {"name": "subtotal", "expression": "quantity * unit_price"}
        ],
        "outputs": [
            {
                "name": "main",
                "filter": "amount > 0",
                "columns": [
                    {"name": "order_id", "expression": "order_id"},
                    {"name": "customer_name", "expression": "customers.name"},
                    {"name": "total", "expression": "var.subtotal * (1 + context.tax_rate)"}
                ]
            },
            {
                "name": "reject",
                "filter": "amount <= 0",
                "columns": [
                    {"name": "order_id", "expression": "order_id"},
                    {"name": "reason", "expression": "'Invalid amount'"}
                ]
            }
        ]
    }
}
```

**Lookup Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | required | Lookup name (for column refs) |
| `input` | string | `name` | Input name to join with |
| `keys` | list | required | Join keys `[{main, lookup}]` |
| `join_type` | string | `"left"` | `"left"`, `"inner"`, `"outer"`, `"right"`, `"cross"` |
| `match_mode` | string | `"all"` | `"first"`, `"last"`, `"unique"`, `"all"` |

**Match Modes:**

| Mode | Description |
|------|-------------|
| `first` | Keep first matching row from lookup |
| `last` | Keep last matching row from lookup |
| `all` | Keep all matches (may multiply rows) |
| `unique` | Keep last matching row (Talend's default match mode) |

**Cartesian (Cross) Join:**

```json
{
    "lookups": [{
        "name": "regions",
        "input": "all_regions",
        "keys": [],
        "join_type": "cross"
    }]
}
```

**Reject Routing:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `lookup_reject_output` | string | `null` | Output name for rows rejected by inner join lookups |
| `filter_reject_output` | string | `null` | Output name for rows matching no output filter |
| `error_reject_output` | string | `null` | Output name for expression error rows (requires `die_on_error: false`) |
| `die_on_error` | boolean | `true` | When `false`, expression errors route to `error_reject_output` instead of crashing |

- **Lookup rejects:** Captured via anti-join before each inner join. Only `join_type: "inner"` produces rejects.
- **Filter rejects:** Uses combined negation `NOT(filter_1 OR filter_2 OR ...)` to find rows matching no output filter.
- **Error rejects:** Rows where compiled expressions produce null (e.g., bad type casts). Includes auto-generated `_error_message` column with column-level detail.
- All reject outputs use their own `columns` definition to control the output schema.

---

### Filter

Filter rows based on condition expression.

**Type aliases:** `filter`, `filter_rows`

```json
{
    "type": "filter",
    "config": {
        "condition": "status == 'active' && amount > 100",
        "reject_output": true
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `condition` | string | required | Filter expression |
| `reject_output` | bool | `false` | Enable reject output |

**Outputs:**
- `main` - Rows matching condition
- `unmatched` - Rows not matching (if `reject_output: true`)

---

### Select

Select, rename, or exclude columns.

**Type aliases:** `select`, `filter_columns`

**Select specific columns:**
```json
{
    "type": "select",
    "config": {
        "columns": ["id", "name", "amount"]
    }
}
```

**Select with rename:**
```json
{
    "type": "select",
    "config": {
        "columns": [
            {"name": "customer_id", "source": "id"},
            {"name": "customer_name", "source": "name"}
        ]
    }
}
```

**Exclude columns:**
```json
{
    "type": "select",
    "config": {
        "exclude": ["temp_col", "internal_id"]
    }
}
```

---

### Sort

Sort rows by one or more columns with configurable null positioning and stable sort.

**Type aliases:** `sort`, `sort_row`

```json
{
    "type": "sort",
    "config": {
        "columns": [
            {"name": "category"},
            {"name": "amount", "order": "desc", "nulls_last": true}
        ],
        "nulls_last": false,
        "maintain_order": true
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `columns` | list | required | Sort columns (see below) |
| `nulls_last` | bool | `false` | Default null positioning for all columns. When `true`, null values appear after all non-null values |
| `maintain_order` | bool | `false` | Preserve original row order for equal-valued rows (stable sort). Slightly slower, disables streaming |

**Column Definition:**

Each element in `columns` can be a plain string (column name, ascending, nulls use component default) or a dict:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Column name |
| `order` | string | `"asc"` | `"asc"` or `"desc"` |
| `descending` | bool | `false` | Legacy alternative to `order` |
| `nulls_last` | bool | component default | Override null positioning for this column |

**Simple format:**
```json
{
    "config": {
        "columns": ["name", "date"]
    }
}
```

**Nulls last example:**
```json
{
    "config": {
        "columns": [
            {"name": "priority", "order": "asc"},
            {"name": "due_date", "order": "asc", "nulls_last": true}
        ]
    }
}
```

---

## Aggregate Components

### Aggregate

Group by columns and apply aggregation functions.

**Type aliases:** `aggregate`, `aggregate_rows`

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `group_by` | list | `[]` | Columns to group by. Each entry is a string or `{"input": "col", "output": "alias"}` |
| `aggregations` | list | required | Aggregation definitions (see below) |
| `maintain_order` | bool | `false` | Preserve input row order in grouped output |

**Aggregation Entry Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Output column name |
| `function` | string | required | Aggregation function (see table below) |
| `column` | string | `"*"` | Column to aggregate (required for non-count functions) |
| `ignore_nulls` | bool | `true` | Ignore null values in aggregation |
| `separator` | string | `","` | Delimiter for `list` function |

**Aggregation Functions:**

| Function | Description |
|----------|-------------|
| `sum` | Sum of values |
| `count` | Count of non-null values (or all rows with `"*"`) |
| `avg` / `mean` | Average (mean) |
| `min` | Minimum value |
| `max` | Maximum value |
| `first` | First value (skips nulls by default) |
| `last` | Last value (skips nulls by default) |
| `count_distinct` / `n_unique` | Count of unique values |
| `std` | Standard deviation (sample) |
| `var` | Variance (sample) |
| `median` | Median value |
| `list` | Concatenate values into delimited string |

**Example -- Basic aggregation:**

```json
{
    "type": "aggregate",
    "config": {
        "group_by": ["category", "region"],
        "aggregations": [
            {"name": "total_amount", "function": "sum", "column": "amount"},
            {"name": "order_count", "function": "count", "column": "*"},
            {"name": "avg_amount", "function": "avg", "column": "amount"}
        ]
    }
}
```

**Example -- List, renaming, and maintain_order:**

```json
{
    "type": "aggregate",
    "config": {
        "group_by": [
            "region",
            {"input": "customer_id", "output": "cust_id"}
        ],
        "aggregations": [
            {"name": "total", "function": "sum", "column": "amount"},
            {"name": "products", "function": "list", "column": "product_name", "separator": ";"},
            {"name": "first_name", "function": "first", "column": "name", "ignore_nulls": true}
        ],
        "maintain_order": true
    }
}
```

---

### Unique

Remove duplicate rows.

**Type aliases:** `unique`, `unique_row`

```json
{
    "type": "unique",
    "config": {
        "columns": ["customer_id", "order_date"],
        "keep": "first"
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `columns` | list | all | Columns to check for duplicates |
| `keep` | string | `"first"` | `"first"` or `"last"` |

---

## Sink Components

All sink components support opt-in output schema validation. If `schema` is defined in a sink's config, the sink validates column presence and types before writing. Mismatches raise a `ValueError` and abort the write. If no `schema` is defined, data is written as-is (backward compatible).

```json
{
    "type": "file_output",
    "config": {
        "path": "output.csv",
        "schema": [
            {"name": "id", "type": "integer"},
            {"name": "order_date", "type": "date"},
            {"name": "amount", "type": "float"}
        ]
    }
}
```

### FileOutput / FileOutputDelimited

Write data to delimited files (CSV, TSV).

**Type aliases:** `file_output`, `file_output_delimited`, `file_output_csv`

```json
{
    "type": "file_output",
    "config": {
        "path": "${context.output_dir}/results.csv",
        "delimiter": ",",
        "has_header": true,
        "line_terminator": "\n",
        "quote_char": "\"",
        "quote_style": "necessary",
        "null_value": "",
        "append": false,
        "delete_empty_file": false,
        "error_if_exists": false,
        "date_format": "%Y-%m-%d",
        "datetime_format": "%Y-%m-%d %H:%M:%S",
        "schema": [
            {"name": "id", "type": "integer"},
            {"name": "amount", "type": "float"}
        ]
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | required | Output file path (supports `${context.var}`) |
| `delimiter` | string | `","` | Field delimiter |
| `has_header` | bool | `true` | Write header row |
| `line_terminator` | string | `"\n"` | Row separator. Supports `"\r\n"`, `"\r"` |
| `quote_char` | string | `"\""` | Quote character (single char) |
| `quote_style` | string | `"necessary"` | `"necessary"`, `"always"`, `"never"`, `"non_numeric"` |
| `null_value` | string | `""` | String for null values |
| `append` | bool | `false` | Append to existing file. Header is suppressed when appending to an existing file |
| `delete_empty_file` | bool | `false` | Skip writing if 0 data rows |
| `error_if_exists` | bool | `false` | Raise error if output file exists. Cannot combine with `append` |
| `date_format` | string | `null` | Date format pattern |
| `datetime_format` | string | `null` | DateTime format pattern |
| `schema` | list | `null` | Column selection, ordering, and type validation. When defined, only schema columns are written in schema order |

---

### FileOutputParquet

Write data to Parquet files with compression.

**Type alias:** `file_output_parquet`

```json
{
    "type": "file_output_parquet",
    "config": {
        "path": "${context.output_dir}/archive.parquet",
        "compression": "zstd",
        "row_group_size": 100000
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | required | Output file path |
| `compression` | string | `"zstd"` | `"zstd"`, `"lz4"`, `"snappy"`, `"gzip"`, `"none"` |
| `row_group_size` | int | `null` | Rows per row group |
| `schema` | list | `null` | Output schema for type validation (optional) |

---

## Utility Components

### Union

Combine multiple inputs into one output.

**Type aliases:** `union`, `unite`

```json
{
    "type": "union",
    "config": {
        "mode": "all"
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | string | `"all"` | `"all"` or `"distinct"` |

**Modes:**

| Mode | Description |
|------|-------------|
| `all` | Keep all rows including duplicates |
| `distinct` | Remove duplicates after combining |

### ContextLoad

Read key/value configuration from external files and inject into the execution context at runtime. Downstream components see the updated context variables.

**Type:** `context_load`

```json
{
    "type": "context_load",
    "config": {
        "path": "${context.config_dir}/db.properties",
        "format": "delimited",
        "delimiter": "=",
        "encoding": "utf-8",
        "comment_char": "#",
        "print_operations": false,
        "die_on_error": true,
        "types": {
            "port": {"type": "int"},
            "start_date": {"type": "date", "format": "%Y-%m-%d"}
        }
    }
}
```

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | required | File path. Supports `${context.var}` placeholders |
| `format` | string | auto | `"delimited"`, `"json"`, or `"yaml"`. Auto-detected from extension |
| `delimiter` | string | `"="` | Key/value separator (delimited format only) |
| `encoding` | string | `"utf-8"` | File encoding |
| `comment_char` | string | `"#"` | Comment line prefix (delimited format only) |
| `print_operations` | bool | `false` | Log loaded variables (sensitive values masked) |
| `die_on_error` | bool | `true` | Fail on errors vs skip and continue |
| `types` | dict | `{}` | Type declarations for new variables |

**Type Casting Priority:**

1. Existing context variable — cast to match declared type
2. Explicit `types` config — cast per specification
3. JSON/YAML native types — preserved as-is
4. Smart auto-detection — int, float, bool, string

**Supported Formats:**

| Format | Extension | Description |
|--------|-----------|-------------|
| `delimited` | `.properties`, `.txt`, `.cfg` | `key=value` pairs, one per line |
| `json` | `.json` | Flat JSON object `{"key": "value"}` |
| `yaml` | `.yaml`, `.yml` | Flat YAML mapping `key: value` |

---

## Python Code Components

For maximum flexibility, use Python code components. See [PYTHON_COMPONENTS.md](PYTHON_COMPONENTS.md) for details.

| Component | Description |
|-----------|-------------|
| `python_code` | Execute arbitrary Python code |
| `python_row` | Per-row processing (scalar/vectorized). Supports `die_on_error: false` to route rows with processing errors to reject output instead of crashing |
| `python_dataframe` | Full DataFrame access with pandas mode |

---

## Related Documentation

- [EXPRESSIONS.md](EXPRESSIONS.md) - Expression DSL reference
- [PYTHON_COMPONENTS.md](PYTHON_COMPONENTS.md) - Python code components guide
- [ROUTINES.md](ROUTINES.md) - Python routines guide
- [DEVELOPMENT.md](DEVELOPMENT.md) - Creating new components
