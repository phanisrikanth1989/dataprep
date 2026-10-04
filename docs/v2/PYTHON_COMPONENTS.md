# Python Code Components Reference

The v2 engine includes three components for executing custom Python code, providing maximum flexibility for complex transformations that can't be expressed with the standard expression DSL.

## Table of Contents

1. [Overview](#overview)
2. [PythonCode](#pythoncode)
3. [PythonRow](#pythonrow)
4. [PythonDataFrame](#pythondataframe)
5. [Choosing the Right Component](#choosing-the-right-component)
6. [Performance Considerations](#performance-considerations)

---

## Overview

| Component | Use Case | Performance |
|-----------|----------|-------------|
| `PythonCode` | Simple transformations with `input_df` → `output_df` | Fast |
| `PythonRow` | Per-row processing (scalar or vectorized) | Medium |
| `PythonDataFrame` | Full DataFrame access, pandas mode, routines | Flexible |

All Python code components:
- Have access to **Polars** (`pl`) for DataFrame operations
- Can use **context variables** via `context` dict
- Support **code caching** for repeated executions
- Must set `output_df` to the result DataFrame

---

## PythonCode

Execute arbitrary Python code with full DataFrame access.

### Config Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `code` | string | Yes | - | Python code to execute |
| `imports` | list | No | `[]` | Additional modules to import |

### Available Variables

| Variable | Type | Description |
|----------|------|-------------|
| `input_df` | `pl.DataFrame` | The input DataFrame |
| `context` | `dict` | Context variables |
| `pl` | module | Polars module |

### Required Output

Your code **must** set `output_df` to a Polars DataFrame.

### Examples

**Simple Filter:**
```json
{
    "type": "python_code",
    "config": {
        "code": "output_df = input_df.filter(pl.col('amount') > 100)"
    }
}
```

**Add Computed Column:**
```json
{
    "type": "python_code",
    "config": {
        "code": "output_df = input_df.with_columns([(pl.col('price') * pl.col('quantity')).alias('total')])"
    }
}
```

**Using Context Variables:**
```json
{
    "type": "python_code",
    "config": {
        "code": "threshold = context['min_amount']\noutput_df = input_df.filter(pl.col('amount') >= threshold)"
    }
}
```

**Multi-line with Imports:**
```json
{
    "type": "python_code",
    "config": {
        "code": "import json\ndata = json.loads('{\"multiplier\": 2}')\noutput_df = input_df.with_columns([(pl.col('value') * data['multiplier']).alias('doubled')])",
        "imports": ["json"]
    }
}
```

**Complex Multi-step Transformation:**
```json
{
    "type": "python_code",
    "config": {
        "code": "# Filter active records\nactive = input_df.filter(pl.col('status') == 'active')\n\n# Add calculated fields\nwith_total = active.with_columns([\n    (pl.col('price') * pl.col('qty')).alias('subtotal'),\n    pl.lit(context['tax_rate']).alias('tax_rate')\n])\n\n# Calculate final total\noutput_df = with_total.with_columns([\n    (pl.col('subtotal') * (1 + pl.col('tax_rate'))).alias('total')\n])"
    }
}
```

---

## PythonRow

Process each row individually with scalar or vectorized mode.

### Config Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `code` | string | Yes | - | Python code (must return dict or list of dicts) |
| `mode` | string | No | `"scalar"` | `"scalar"` or `"vectorized"` |
| `output_columns` | list | Yes | - | Output column definitions |
| `pass_through` | bool | No | `True` | Include original columns in output |
| `batch_size` | int | No | `1000` | Rows per batch (vectorized mode) |
| `die_on_error` | bool | No | `true` | When false, routes rows with processing errors to reject output instead of crashing |

### Output Column Types

| Type | Polars Type |
|------|-------------|
| `String` | `pl.Utf8` |
| `Integer` | `pl.Int64` |
| `Float` | `pl.Float64` |
| `Boolean` | `pl.Boolean` |
| `Date` | `pl.Date` |
| `Datetime` | `pl.Datetime` |

### Scalar Mode

Process one row at a time. Available variables:
- `row` - Dictionary of column values for current row
- `context` - Context variables

```json
{
    "type": "python_row",
    "config": {
        "code": "return {'full_name': row['first'] + ' ' + row['last']}",
        "mode": "scalar",
        "output_columns": [
            {"name": "full_name", "type": "String"}
        ],
        "pass_through": true
    }
}
```

**With Context:**
```json
{
    "type": "python_row",
    "config": {
        "code": "discount = context.get('discount_rate', 0.1)\nreturn {'final_price': row['price'] * (1 - discount)}",
        "mode": "scalar",
        "output_columns": [
            {"name": "final_price", "type": "Float"}
        ]
    }
}
```

### Vectorized Mode

Process batches of rows for better performance. Available variables:
- `rows` - List of row dictionaries
- `context` - Context variables

```json
{
    "type": "python_row",
    "config": {
        "code": "return [{'total': r['price'] * r['qty']} for r in rows]",
        "mode": "vectorized",
        "batch_size": 5000,
        "output_columns": [
            {"name": "total", "type": "Float"}
        ],
        "pass_through": false
    }
}
```

**Complex Vectorized Processing:**
```json
{
    "type": "python_row",
    "config": {
        "code": "results = []\nfor r in rows:\n    category = 'high' if r['amount'] > 1000 else 'medium' if r['amount'] > 100 else 'low'\n    results.append({'category': category, 'flag': r['amount'] > 500})\nreturn results",
        "mode": "vectorized",
        "batch_size": 10000,
        "output_columns": [
            {"name": "category", "type": "String"},
            {"name": "flag", "type": "Boolean"}
        ]
    }
}
```

---

## PythonDataFrame

Full DataFrame access with optional pandas mode and routine support.

### Config Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `code` | string | Yes | - | Python code to execute |
| `use_pandas` | bool | No | `false` | Use pandas DataFrame instead of Polars |
| `imports` | list | No | `[]` | Additional modules to import |

### Available Variables

| Variable | Type | Description |
|----------|------|-------------|
| `df` | DataFrame | Input (Polars or pandas based on `use_pandas`) |
| `context` | dict | Context variables |
| `pl` | module | Polars module |
| `routines` | RoutineManager | Access to routine functions (if available) |

### Polars Mode (default)

```json
{
    "type": "python_dataframe",
    "config": {
        "code": "output_df = df.group_by('category').agg([pl.col('value').sum().alias('total')])"
    }
}
```

### Pandas Mode

Enable when you need pandas-specific functionality:

```json
{
    "type": "python_dataframe",
    "config": {
        "code": "df['new_col'] = df.apply(lambda r: complex_calculation(r), axis=1)\noutput_df = df",
        "use_pandas": true
    }
}
```

### Using Routines

Access routine functions for complex transformations:

```json
{
    "type": "python_dataframe",
    "config": {
        "code": "def apply_greet(name):\n    return routines.DemoRoutine.greet(name)\n\noutput_df = df.with_columns([pl.col('name').map_elements(apply_greet, return_dtype=pl.Utf8).alias('greeting')])"
    }
}
```

### Complex Aggregation Example

```json
{
    "type": "python_dataframe",
    "config": {
        "code": "# Multi-step aggregation\ngrouped = df.group_by(['region', 'category']).agg([\n    pl.col('amount').sum().alias('total_amount'),\n    pl.col('amount').mean().alias('avg_amount'),\n    pl.col('order_id').count().alias('order_count')\n])\n\n# Add ranking\nranked = grouped.with_columns([\n    pl.col('total_amount').rank(descending=True).over('region').alias('rank_in_region')\n])\n\noutput_df = ranked.sort(['region', 'rank_in_region'])"
    }
}
```

---

## Choosing the Right Component

| Scenario | Recommended Component |
|----------|----------------------|
| Simple filter/transform | `PythonCode` |
| Add computed column | `PythonCode` |
| Row-by-row logic with conditionals | `PythonRow` (scalar) |
| Batch processing with external API | `PythonRow` (vectorized) |
| Complex aggregation | `PythonDataFrame` |
| Need pandas-specific functions | `PythonDataFrame` (pandas mode) |
| Call routine functions in loop | `PythonDataFrame` |

### Decision Tree

```
Need per-row processing?
├── Yes
│   ├── Simple logic? → PythonRow (scalar)
│   └── Complex/batch? → PythonRow (vectorized)
└── No
    ├── Simple transform? → PythonCode
    └── Complex/aggregation/pandas? → PythonDataFrame
```

---

## Performance Considerations

### Code Caching

All Python code components cache compiled code:

```python
# First execution: code is compiled
# Subsequent executions: use cached bytecode
```

### PythonRow Performance

| Mode | Overhead | Best For |
|------|----------|----------|
| Scalar | Higher (per-row call) | Complex per-row logic |
| Vectorized | Lower (batch calls) | Large datasets |

**Recommendation:** Use vectorized mode with `batch_size: 5000-10000` for large datasets.

### Avoid in Hot Paths

```python
# Slow - imports in code
"code": "import heavy_lib\noutput_df = heavy_lib.process(input_df)"

# Better - use imports config
"imports": ["heavy_lib"],
"code": "output_df = heavy_lib.process(input_df)"
```

### Use Polars Over Pandas

Polars is 10-100x faster than pandas for most operations:

```json
// Faster
{
    "type": "python_dataframe",
    "config": {
        "code": "output_df = df.filter(pl.col('x') > 0)",
        "use_pandas": false
    }
}

// Slower
{
    "type": "python_dataframe",
    "config": {
        "code": "output_df = df[df['x'] > 0]",
        "use_pandas": true
    }
}
```

### When to Use Expression DSL Instead

If your transformation can be expressed with the built-in expression DSL, prefer that:

```json
// Better - use expression DSL
{
    "type": "map",
    "config": {
        "outputs": [{
            "name": "main",
            "columns": [
                {"name": "total", "expression": "quantity * price"}
            ]
        }]
    }
}

// Unnecessary - Python for simple math
{
    "type": "python_code",
    "config": {
        "code": "output_df = input_df.with_columns([(pl.col('quantity') * pl.col('price')).alias('total')])"
    }
}
```

---

## Error Handling

### Validation Errors

Components validate config before execution:

```python
# Missing required 'code'
errors = component.validate_config()
# ["PythonCode requires 'code' in config"]

# Empty code
# ["PythonCode 'code' cannot be empty"]
```

### Runtime Errors

Errors in your code are raised with context:

```python
# Your code raises an exception
"code": "output_df = input_df.filter(pl.col('nonexistent') > 0)"

# Error includes component ID and original exception
# "PythonCode test_1: column 'nonexistent' not found"
```

### Debugging Tips

1. **Start simple** - Test with small DataFrames first
2. **Print debugging** - Use `print()` to inspect intermediate values
3. **Check types** - Verify `output_df` is a DataFrame, not LazyFrame
4. **Validate output** - Ensure output has expected columns
