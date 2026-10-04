# Job Configuration Reference

Complete reference for v2 engine job configuration.

## Table of Contents

1. [Configuration Structure](#configuration-structure)
2. [Job-Level Settings](#job-level-settings)
3. [Context Variables](#context-variables)
4. [Components](#components)
5. [Flows](#flows)
6. [Memory Configuration](#memory-configuration)
7. [Complete Examples](#complete-examples)

---

## Configuration Structure

Jobs can be defined as JSON files or Python dictionaries:

```json
{
    "name": "job_name",
    "version": "2.0",
    "engine": "python",
    "description": "Optional description",
    "context": { ... },
    "components": [ ... ],
    "flows": [ ... ],
    "memory": { ... }
}
```

---

## Job-Level Settings

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique job identifier |
| `version` | string | No | `"2.0"` | Configuration version |
| `engine` | string | No | `"python"` | Engine type (`"python"` for v2) |
| `description` | string | No | - | Human-readable description |

```json
{
    "name": "daily_orders_etl",
    "version": "2.0",
    "engine": "python",
    "description": "Process daily order files and generate summary reports"
}
```

---

## Context Variables

Context variables are shared values accessible by all components using `context.variable_name` syntax.

### Definition

```json
{
    "context": {
        "input_dir": {"value": "/data/input", "type": "str"},
        "output_dir": {"value": "/data/output", "type": "str"},
        "tax_rate": {"value": 0.08, "type": "float"},
        "batch_size": {"value": 1000, "type": "int"},
        "debug_mode": {"value": false, "type": "bool"},
        "processing_date": {"value": "2024-01-15", "type": "str"}
    }
}
```

### Variable Types

| Type | Description | Example |
|------|-------------|---------|
| `str` | String | `"hello"` |
| `int` | Integer | `42` |
| `float` | Floating point | `0.08` |
| `bool` | Boolean | `true` or `false` |
| `date` | Date string | `"2024-01-15"` |
| `datetime` | DateTime string | `"2024-01-15T10:30:00"` |

### Usage in Components

**In file paths:**
```json
{
    "config": {
        "path": "${context.input_dir}/orders.csv"
    }
}
```

**In expressions:**
```json
{
    "expression": "amount * context.tax_rate"
}
```

---

## Components

Components define the data processing steps.

### Component Structure

```json
{
    "id": "unique_component_id",
    "type": "component_type",
    "config": {
        // Component-specific configuration
    }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (used in flows) |
| `type` | string | Yes | Component type name |
| `config` | object | Yes | Component-specific settings |

### Available Component Types

#### File Input

```json
{
    "id": "orders_input",
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
            {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
            {"name": "status", "type": "string"}
        ]
    }
}
```

**Schema is REQUIRED** - column names and types are never auto-inferred. Column names from schema override file header names positionally.

Schema types:
- `string`, `str`, `id_String`
- `integer`, `int`, `long`, `id_Integer`, `id_Long`
- `float`, `double`, `id_Float`, `id_Double`
- `boolean`, `bool`, `id_Boolean`
- `date`, `id_Date` (use with `date_pattern`)
- `datetime` (use with `date_pattern`)
- `decimal`, `id_BigDecimal`

#### File Input Full Row

```json
{
    "id": "raw_reader",
    "type": "file_input_full_row",
    "config": {
        "path": "${context.input_dir}/mixed_format.txt",
        "header_rows": 1,
        "schema": [
            {"name": "line", "type": "string"}
        ]
    }
}
```

Reads each line as a raw string. Schema must have exactly one column of type `string`. Useful for files with mixed record formats where downstream components handle field extraction.

#### File Output

```json
{
    "id": "results_output",
    "type": "file_output",
    "config": {
        "path": "${context.output_dir}/results.csv",
        "delimiter": ",",
        "include_header": true,
        "encoding": "utf8"
    }
}
```

#### File Output Parquet

```json
{
    "id": "archive_output",
    "type": "file_output_parquet",
    "config": {
        "path": "${context.output_dir}/archive.parquet",
        "compression": "zstd"
    }
}
```

#### Map

```json
{
    "id": "transform",
    "type": "map",
    "config": {
        "outputs": [
            {
                "name": "main",
                "filter": "amount > 0",
                "columns": [
                    {"name": "order_id", "expression": "order_id"},
                    {"name": "customer", "expression": "UPPER(customer_id)"},
                    {"name": "total", "expression": "quantity * unit_price"},
                    {"name": "with_tax", "expression": "total * (1 + context.tax_rate)"}
                ]
            },
            {
                "name": "errors",
                "filter": "amount <= 0",
                "columns": [
                    {"name": "order_id", "expression": "order_id"},
                    {"name": "error", "expression": "'Invalid amount'"}
                ]
            }
        ]
    }
}
```

#### Filter

```json
{
    "id": "active_only",
    "type": "filter",
    "config": {
        "condition": "status == 'active' && amount > 100",
        "reject_output": true
    }
}
```

#### Select

Select specific columns:
```json
{
    "id": "select_cols",
    "type": "select",
    "config": {
        "columns": ["id", "name", "amount"]
    }
}
```

Select with rename:
```json
{
    "id": "rename_cols",
    "type": "select",
    "config": {
        "columns": [
            {"name": "customer_id", "source": "id"},
            {"name": "customer_name", "source": "name"}
        ]
    }
}
```

Exclude columns:
```json
{
    "id": "drop_cols",
    "type": "select",
    "config": {
        "exclude": ["temp_col", "internal_id", "debug_info"]
    }
}
```

#### Sort

```json
{
    "id": "sort_results",
    "type": "sort",
    "config": {
        "columns": [
            {"name": "category"},
            {"name": "amount", "descending": true},
            {"name": "name"}
        ]
    }
}
```

#### Aggregate

```json
{
    "id": "summarize",
    "type": "aggregate",
    "config": {
        "group_by": ["category", "region"],
        "aggregations": [
            {"name": "total_amount", "function": "sum", "column": "amount"},
            {"name": "order_count", "function": "count", "column": "order_id"},
            {"name": "avg_amount", "function": "avg", "column": "amount"},
            {"name": "min_amount", "function": "min", "column": "amount"},
            {"name": "max_amount", "function": "max", "column": "amount"},
            {"name": "first_order", "function": "first", "column": "order_date"},
            {"name": "last_order", "function": "last", "column": "order_date"}
        ]
    }
}
```

Aggregation functions: `sum`, `count`, `avg`, `min`, `max`, `first`, `last`

#### Unique

```json
{
    "id": "dedup",
    "type": "unique",
    "config": {
        "columns": ["customer_id", "order_date"],
        "keep": "first"
    }
}
```

Options:
- `columns`: Columns to check (all if omitted)
- `keep`: `"first"` or `"last"`

#### Union

```json
{
    "id": "combine",
    "type": "union",
    "config": {
        "mode": "all"
    }
}
```

Modes:
- `all`: Keep all rows including duplicates
- `distinct`: Remove duplicates after combining

---

## Flows

Flows define data movement between components.

### Basic Flow

```json
{
    "flows": [
        {"source": "input", "target": "transform"},
        {"source": "transform", "target": "output"}
    ]
}
```

### Multi-Output Flows

When a component has multiple outputs:

```json
{
    "flows": [
        {"source": "filter", "source_output": "main", "target": "process"},
        {"source": "filter", "source_output": "unmatched", "target": "error_log"}
    ]
}
```

### Multi-Input Flows

For components accepting multiple inputs (like Union):

```json
{
    "flows": [
        {"source": "stream_a", "target": "combine", "target_input": "input_1"},
        {"source": "stream_b", "target": "combine", "target_input": "input_2"}
    ]
}
```

### Flow Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | - | Source component ID |
| `source_output` | string | `"main"` | Output name from source |
| `target` | string | - | Target component ID |
| `target_input` | string | `"main"` | Input name on target |

---

## Complete Examples

### Simple Pipeline

```json
{
    "name": "simple_etl",
    "engine": "python",
    "components": [
        {
            "id": "input",
            "type": "file_input",
            "config": {
                "path": "data/orders.csv",
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "customer", "type": "string"},
                    {"name": "amount", "type": "float"}
                ]
            }
        },
        {
            "id": "filter",
            "type": "filter",
            "config": {
                "condition": "amount > 100"
            }
        },
        {
            "id": "output",
            "type": "file_output",
            "config": {
                "path": "data/large_orders.csv"
            }
        }
    ],
    "flows": [
        {"source": "input", "target": "filter"},
        {"source": "filter", "target": "output"}
    ]
}
```

### Advanced CSV Input

```json
{
    "name": "advanced_csv_etl",
    "engine": "python",
    "components": [
        {
            "id": "input",
            "type": "file_input",
            "config": {
                "path": "data/orders.csv",
                "quote_char": "\"",
                "footer_rows": 1,
                "limit": 5000,
                "skip_empty_rows": true,
                "trim_all": true,
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "customer", "type": "string"},
                    {"name": "address", "type": "string"},
                    {"name": "amount", "type": "float"},
                    {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"}
                ]
            }
        },
        {
            "id": "output",
            "type": "file_output",
            "config": {
                "path": "data/cleaned_orders.csv"
            }
        }
    ],
    "flows": [
        {"source": "input", "target": "output"}
    ]
}
```

This example demonstrates:
- `quote_char`: handles CSV fields containing commas inside quotes
- `footer_rows: 1`: skips the last row (e.g., a summary/total row)
- `limit: 5000`: reads at most 5000 data rows
- `skip_empty_rows`: filters out blank lines
- `trim_all`: strips whitespace from all string columns before downstream processing

### Excel Multi-Sheet Pipeline

```json
{
    "name": "excel_multi_sheet",
    "engine": "python",
    "components": [
        {
            "id": "read_excel",
            "type": "file_input_excel",
            "config": {
                "path": "data/sales.xlsx",
                "sheets": [
                    {"name": "Sales_.*", "regex": true}
                ],
                "footer_rows": 1,
                "first_column": 2,
                "last_column": 5,
                "trim_all": true,
                "schema": [
                    {"name": "order_id", "type": "integer"},
                    {"name": "customer", "type": "string"},
                    {"name": "amount", "type": "float"},
                    {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"}
                ]
            }
        },
        {
            "id": "filter_large",
            "type": "filter",
            "config": {
                "condition": "amount > 100"
            }
        },
        {
            "id": "write_output",
            "type": "file_output",
            "config": {
                "path": "data/large_orders.csv"
            }
        }
    ],
    "flows": [
        {"source": "read_excel", "target": "filter_large"},
        {"source": "filter_large", "target": "write_output"}
    ]
}
```

This example demonstrates:
- `sheets` with regex: reads all sheets matching `Sales_.*` (e.g., Sales_2025, Sales_2026)
- `footer_rows: 1`: skips the last row of each sheet (e.g., a totals row)
- `first_column: 2, last_column: 5`: reads only columns B through E (1-based)
- `trim_all`: strips whitespace from all string columns
- Per-sheet operations (footer, column range) apply independently to each matched sheet before concatenation

### Complex Pipeline with Context

```json
{
    "name": "order_processing",
    "version": "2.0",
    "engine": "python",
    "description": "Process orders, apply tax, and generate summaries",
    "context": {
        "input_dir": {"value": "/data/input", "type": "str"},
        "output_dir": {"value": "/data/output", "type": "str"},
        "tax_rate": {"value": 0.08, "type": "float"},
        "min_order_amount": {"value": 50, "type": "float"}
    },
    "components": [
        {
            "id": "orders",
            "type": "file_input",
            "config": {
                "path": "${context.input_dir}/orders.csv",
                "schema": [
                    {"name": "order_id", "type": "integer"},
                    {"name": "customer_id", "type": "string"},
                    {"name": "product", "type": "string"},
                    {"name": "quantity", "type": "integer"},
                    {"name": "unit_price", "type": "float"},
                    {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"}
                ]
            }
        },
        {
            "id": "calculate",
            "type": "map",
            "config": {
                "outputs": [{
                    "name": "main",
                    "columns": [
                        {"name": "order_id", "expression": "order_id"},
                        {"name": "customer_id", "expression": "customer_id"},
                        {"name": "product", "expression": "product"},
                        {"name": "subtotal", "expression": "quantity * unit_price"},
                        {"name": "tax", "expression": "subtotal * context.tax_rate"},
                        {"name": "total", "expression": "subtotal + tax"},
                        {"name": "order_date", "expression": "order_date"},
                        {"name": "order_year", "expression": "YEAR(order_date)"}
                    ]
                }]
            }
        },
        {
            "id": "filter_valid",
            "type": "filter",
            "config": {
                "condition": "total >= context.min_order_amount",
                "reject_output": true
            }
        },
        {
            "id": "summarize",
            "type": "aggregate",
            "config": {
                "group_by": ["customer_id", "order_year"],
                "aggregations": [
                    {"name": "total_orders", "function": "count", "column": "order_id"},
                    {"name": "total_amount", "function": "sum", "column": "total"},
                    {"name": "avg_order", "function": "avg", "column": "total"}
                ]
            }
        },
        {
            "id": "sort_summary",
            "type": "sort",
            "config": {
                "columns": [
                    {"name": "total_amount", "descending": true}
                ]
            }
        },
        {
            "id": "valid_orders",
            "type": "file_output",
            "config": {
                "path": "${context.output_dir}/valid_orders.csv"
            }
        },
        {
            "id": "rejected_orders",
            "type": "file_output",
            "config": {
                "path": "${context.output_dir}/rejected_orders.csv"
            }
        },
        {
            "id": "customer_summary",
            "type": "file_output",
            "config": {
                "path": "${context.output_dir}/customer_summary.csv"
            }
        }
    ],
    "flows": [
        {"source": "orders", "target": "calculate"},
        {"source": "calculate", "target": "filter_valid"},
        {"source": "filter_valid", "source_output": "main", "target": "valid_orders"},
        {"source": "filter_valid", "source_output": "main", "target": "summarize"},
        {"source": "filter_valid", "source_output": "unmatched", "target": "rejected_orders"},
        {"source": "summarize", "target": "sort_summary"},
        {"source": "sort_summary", "target": "customer_summary"}
    ]
}
```

---

## Validation

The engine validates configurations before execution:

1. **Required fields**: `name`, component `id` and `type`
2. **Component config**: Each component validates its own config
3. **Flow references**: All source/target IDs must exist
4. **Context references**: Variables used in expressions must be defined
5. **Schema requirements**: FileInput requires explicit schema

Validation errors are raised before any data processing begins.
