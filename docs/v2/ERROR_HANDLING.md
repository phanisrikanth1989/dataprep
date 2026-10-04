# V2 Engine Error Handling and Reject Flows

This document covers how the V2 engine handles errors at every level -- from
configuration validation through runtime failures to row-level reject routing.

---

## Table of Contents

1. [Error Levels Overview](#error-levels-overview)
2. [Config Validation Errors](#config-validation-errors)
3. [Runtime Error Handling](#runtime-error-handling)
4. [Row-Level Reject Flows](#row-level-reject-flows)
5. [Source Component die_on_error](#source-component-die_on_error)
6. [PythonRow die_on_error](#pythonrow-die_on_error)
7. [Filter Unmatched Output](#filter-unmatched-output)
8. [Output Port Naming Convention](#output-port-naming-convention)
9. [Flow Configuration for Rejects](#flow-configuration-for-rejects)
10. [Complete Examples](#complete-examples)
11. [Best Practices](#best-practices)

---

## Error Levels Overview

The V2 engine has three distinct error levels, each caught at a different stage
of execution:

| Level | When | Behavior | Recoverable? |
|---|---|---|---|
| **Config validation** | Before execution starts | Pydantic rejects invalid config; component `validate()` methods catch semantic errors | No -- job never runs |
| **Runtime error** | During component execution | Engine catches the exception and returns an error result dict | No -- job stops |
| **Row-level error** | During data reading, expression evaluation, or row processing | Bad rows are routed to a `"reject"` output with an `_error_message` column | Yes -- good rows continue |

These levels form a hierarchy. Config validation fires first, runtime errors
fire second, and row-level errors are only possible when you explicitly opt in
via `die_on_error: false`.

---

## Config Validation Errors

### Pydantic Validation (JobConfig)

When the engine receives a configuration dict, it is parsed into a `JobConfig`
Pydantic model (defined in `src/v2/config/job_config.py`). Pydantic enforces
structural rules automatically:

- `name` is required (must be a string).
- `components` must be a list of objects, each with `id` and `type`.
- `flows` must be a list of objects, each with `source` and `target`.
- Context variables are normalized -- plain values are auto-wrapped with an
  inferred type.

If the config fails Pydantic validation, a `ValidationError` is raised before
any component is created. The engine never calls `execute()`.

```python
from v2 import PyETLEngine

# Missing required "name" field -- Pydantic raises ValidationError
try:
    engine = PyETLEngine({"components": [], "flows": []})
except Exception as e:
    print(type(e).__name__)  # ValidationError
```

### Component validate() Method

Every component class inherits a `validate()` method from the `Component` base
class (`src/v2/components/base.py`). The default implementation returns an
empty list (no errors). Components override it to check semantic requirements.

The engine calls `validate()` on each component during `_create_components()`,
**before any data flows**. If any component returns a non-empty error list, the
engine raises a `ValueError` and stops:

```python
# Inside PyETLEngine._create_components():
errors = component.validate()
if errors:
    raise ValueError(
        f"Component {comp_config.id} validation errors: {errors}"
    )
```

Examples of component-level validation:

| Component | What `validate()` checks |
|---|---|
| **Map** | At least one output defined; each output has `name` and `columns` |
| **Filter** | `condition` key exists in config |
| **Select** | `columns` key exists in config |

A validation error looks like this in the result dict:

```python
result = engine.execute()
# {
#   "status": "error",
#   "error": "Component transform validation errors: [\"Map requires at least one output definition\"]",
#   "error_type": "ValueError",
#   ...
# }
```

### Unknown Component Type

If a component config references a type that is not in the component registry,
the engine raises a `ValueError` during `_create_components()`:

```python
# Config with typo in type
{"id": "t", "type": "mapp", "config": {}}
# -> ValueError: Unknown component type: mapp. Registered: [...]
```

---

## Runtime Error Handling

When any component throws an unhandled exception during `execute()`, the engine
catches it at the top level and returns an error result dict. This is the
catch-all safety net.

### The Error Result Dict

From `src/v2/engine.py`, the `execute()` method wraps the entire execution loop
in a try/except:

```python
try:
    # ... build DAG, create components, execute in order ...
    return {
        "status": "success",
        "job_name": self.job_name,
        "duration_ms": ...,
        # per-component stats
    }
except Exception as e:
    return {
        "status": "error",
        "job_name": self.job_name,
        "error": str(e),
        "error_type": type(e).__name__,
        "duration_ms": ...,
        "components": dict(context._component_stats),
    }
```

Key fields in the error result:

| Field | Type | Description |
|---|---|---|
| `status` | `str` | Always `"error"` |
| `job_name` | `str` | Name of the job |
| `error` | `str` | The exception message |
| `error_type` | `str` | The exception class name (e.g., `"ValueError"`, `"ComputeError"`) |
| `duration_ms` | `float` | How long the job ran before failing |
| `components` | `dict` | Stats for components that completed before the failure |

### Common Runtime Errors

| Scenario | Exception Type | Example |
|---|---|---|
| Expression compilation failure | `CompileError` | Unknown function name in expression |
| Type cast failure (strict mode) | `polars.ComputeError` | `TO_INTEGER("abc")` with `die_on_error: true` |
| Missing input file | `FileNotFoundError` | File path does not exist |
| Unknown context variable | `CompileError` | `context.missing_var` in expression |
| Column not found | `polars.SchemaError` | Expression references column not in data |

### Checking for Errors Programmatically

```python
engine = PyETLEngine(config)
result = engine.execute()

if result["status"] == "error":
    print(f"Job failed: {result['error']}")
    print(f"Error type: {result['error_type']}")
    print(f"Ran for: {result['duration_ms']}ms")
    # Inspect partial stats
    for comp_id, stats in result.get("components", {}).items():
        print(f"  {comp_id}: {stats}")
else:
    print(f"Job succeeded in {result['duration_ms']}ms")
```

---

## Row-Level Reject Flows

Row-level error handling is the most important pattern for production ETL
pipelines. Instead of failing the entire job when a single row has bad data,
you route the bad rows to a reject output and let the good rows continue.

This is controlled by the `die_on_error` flag, which is supported on three
component types:

- **Source components** (`file_input`, `file_input_excel`) -- routes rows with
  schema cast failures to the `"reject"` output.
- **Map component** -- routes rows where expression evaluation produced `null`
  to the `"reject"` output.
- **PythonRow component** -- routes rows where per-row processing raised an
  exception to the `"reject"` output.

### How It Works (Map)

The mechanism for Map involves three layers working together:

1. **Map component** reads `die_on_error` from its config (default: `true`).
2. **Expression compiler** receives `safe=True` when `die_on_error` is `false`,
   which makes type-cast functions use `strict=False`.
3. **Map output generation** detects rows where computed expressions produced
   `null` and routes them to a `"reject"` output.

#### Step 1: The die_on_error Flag

In the Map component's `_generate_outputs()` method:

```python
die_on_error = self.config.get("die_on_error", True)
safe = not die_on_error
```

When `die_on_error` is `false`, the `safe` flag is set to `True`, which
propagates to the expression compiler.

#### Step 2: Safe Expression Compilation

The expression compiler (`src/v2/expressions/compiler.py`) accepts a `safe`
parameter. When `safe=True`, all type-cast functions use `strict=False` in
their Polars cast calls:

```python
cast_strict = not self.safe

# These casts become lenient when safe=True:
'to_integer': lambda args: args[0].cast(pl.Int64, strict=cast_strict),
'to_float':   lambda args: args[0].cast(pl.Float64, strict=cast_strict),
'to_boolean': lambda args: args[0].cast(pl.Boolean, strict=cast_strict),
'to_decimal': lambda args: args[0].cast(pl.Float64, strict=cast_strict),
```

With `strict=False`, Polars returns `null` for values that cannot be cast
instead of raising a `ComputeError`. For example, `TO_INTEGER("abc")` returns
`null` instead of crashing.

#### Step 3: Null Detection and Reject Routing

After computing all output columns, the Map component checks which rows have
`null` values in columns that were computed via expressions (not direct column
references). This distinction is important -- a column that is simply passed
through (like `"expression": "id"`) is not checked, so pre-existing null values
in passthrough columns do not trigger rejection.

```python
if safe and computed_col_names and output_name == "main":
    # Build null check across all computed columns
    null_checks = [pl.col(c).is_null() for c in computed_col_names]
    has_error = null_checks[0]
    for nc in null_checks[1:]:
        has_error = has_error | nc

    # Reject rows: rows where any computed column is null
    reject = result.filter(has_error).with_columns([
        pl.lit("Expression produced null").alias("_error_message"),
    ])
    outputs["reject"] = reject

    # Main output: only good rows
    outputs[output_name] = result.filter(~has_error)
```

The reject output includes all the same columns as the main output, plus an
`_error_message` column containing the string `"Expression produced null"`.

### Important Details

- **Only the `"main"` output** generates a reject split. Named outputs other
  than `"main"` do not produce reject rows.
- **Direct column references are excluded** from null checking. If your
  expression is just a column name (e.g., `"expression": "id"`), nulls in that
  column will not cause rejection. Only columns computed via complex expressions
  (like `TO_INTEGER(raw_amount)`) are tracked.
- **The reject output always exists** when `die_on_error: false` and there are
  computed columns, even if zero rows are rejected. In that case the reject
  LazyFrame is simply empty.

---

## Source Component die_on_error

Source components (`file_input`, `file_input_excel`) support `die_on_error` to
handle rows that fail schema type casting during file reading.

When `die_on_error` is `true` (the default), a schema cast failure crashes the
entire job. When `die_on_error` is `false`, the source component catches cast
failures on a per-row basis and routes those rows to a `"reject"` output with
an `_error_message` column describing the failure.

### Source Reject Config

```json
{
    "id": "read",
    "type": "file_input",
    "config": {
        "path": "/data/raw_orders.csv",
        "die_on_error": false,
        "schema": [
            {"name": "id", "type": "integer"},
            {"name": "amount", "type": "float"}
        ]
    }
}
```

### Source Reject Outputs

- `"main"` -- rows that were successfully cast to the declared schema types.
- `"reject"` -- rows where one or more columns failed to cast. These rows
  include an `_error_message` column describing which cast failed.

To wire the reject output to a sink, add a flow with `"output": "reject"`:

```json
{"source": "read", "target": "write_reject", "output": "reject"}
```

---

## PythonRow die_on_error

The PythonRow component (`python_row`) supports `die_on_error` to handle rows
where the user-defined per-row function raises an exception.

When `die_on_error` is `true` (the default), any exception in the row function
crashes the entire job. When `die_on_error` is `false`, the component catches
per-row exceptions and routes the failing rows to a `"reject"` output with an
`_error_message` column containing the exception message.

### PythonRow Reject Config

```json
{
    "id": "enrich",
    "type": "python_row",
    "config": {
        "die_on_error": false,
        "code": "output['parsed_date'] = parse_date(input['raw_date'])"
    }
}
```

### PythonRow Reject Outputs

- `"main"` -- rows processed successfully.
- `"reject"` -- rows where the row function raised an exception. These rows
  include an `_error_message` column with the exception text.

---

## Filter Unmatched Output

The Filter component (`src/v2/components/transform/filter_component.py`)
supports a simpler form of output splitting via the `reject_output` flag.

When `reject_output` is `true`, the filter produces two outputs:

- `"main"` -- rows that match the condition
- `"unmatched"` -- rows that do not match the condition

```python
if self.config.get("reject_output", False):
    return {
        "main": data.filter(expr),
        "unmatched": data.filter(~expr),
    }
```

This is a barrier point because the component now has multiple outputs, which
forces the engine to materialize the LazyFrame.

### Filter Config

```json
{
    "id": "quality_check",
    "type": "filter",
    "config": {
        "condition": "amount > 0 && status != 'cancelled'",
        "reject_output": true
    }
}
```

Unlike the Map/Source/PythonRow reject flow, the Filter unmatched output does
**not** add an `_error_message` column. It simply splits rows based on the
boolean condition. This is a business-logic split, not an error split.

---

## Output Port Naming Convention

The V2 engine uses two distinct output port names for non-main outputs:

| Port Name | Meaning | Has `_error_message`? | Used By |
|---|---|---|---|
| `"reject"` | Rows that failed due to a data error | Yes | Map, Source, PythonRow |
| `"unmatched"` | Rows that did not match a business-logic condition | No | Filter |

This distinction is important:

- **`"reject"`** means something went wrong with the data -- a type cast
  failed, an expression produced null, or a row function raised an exception.
  These rows always carry an `_error_message` column so you can diagnose the
  failure.
- **`"unmatched"`** means the data was valid but did not satisfy a filter
  condition. There is nothing wrong with these rows; they simply belong to a
  different logical category.

---

## Flow Configuration for Rejects

To route reject output to a separate sink, you use the `output` field in a flow
definition. The `FlowConnection` model (from `src/v2/config/job_config.py`)
supports these fields:

```json
{
    "source": "component_id",
    "output": "main",
    "target": "downstream_id",
    "input": "main"
}
```

- `output` (default: `"main"`) -- which output port of the source to read from.
- `input` (default: `"main"`) -- which input port of the target to write to.

To wire a reject output from a Map/Source/PythonRow, set `"output": "reject"`:

```json
{"source": "transform", "target": "write_reject", "output": "reject"}
```

To wire an unmatched output from a Filter, set `"output": "unmatched"`:

```json
{"source": "quality_filter", "target": "write_unmatched", "output": "unmatched"}
```

### Flow Routing Diagram

```
                     output="main" (default)
                    +--------------------> [write_main]
                    |
[read] --> [transform]   (Map with die_on_error: false)
                    |
                    +--------------------> [write_reject]
                     output="reject"

                     output="main" (default)
                    +--------------------> [write_matched]
                    |
       [filter]     (Filter with reject_output: true)
                    |
                    +--------------------> [write_unmatched]
                     output="unmatched"
```

The engine resolves this in `_execute_component()` by looking up the flow
definition for each upstream-downstream pair:

```python
flow = self._get_flow(upstream_id, component_id)
source_output = flow.output if flow else "main"
```

If no explicit flow exists between two components, the engine defaults to the
`"main"` output.

---

## Complete Examples

### Example 1: Map Reject Flow with File Output

This is the most common pattern. A Map component with `die_on_error: false`
routes bad rows to a reject CSV file while good rows go to the main output.

```json
{
    "name": "orders_with_reject",
    "version": "2.0",
    "components": [
        {
            "id": "read",
            "type": "file_input",
            "config": {
                "path": "/data/raw_orders.csv",
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "raw_amount", "type": "string"}
                ]
            }
        },
        {
            "id": "transform",
            "type": "map",
            "config": {
                "die_on_error": false,
                "outputs": [
                    {
                        "name": "main",
                        "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "TO_INTEGER(raw_amount)"}
                        ]
                    }
                ]
            }
        },
        {
            "id": "write_main",
            "type": "file_output",
            "config": {"path": "/data/clean_orders.csv"}
        },
        {
            "id": "write_reject",
            "type": "file_output",
            "config": {"path": "/data/rejected_orders.csv"}
        }
    ],
    "flows": [
        {"source": "read", "target": "transform"},
        {"source": "transform", "target": "write_main"},
        {"source": "transform", "target": "write_reject", "output": "reject"}
    ]
}
```

**Input** (`raw_orders.csv`):
```
id,raw_amount
1,100
2,bad
3,300
```

**Main output** (`clean_orders.csv`):
```
id,amount
1,100
3,300
```

**Reject output** (`rejected_orders.csv`):
```
id,amount,_error_message
2,,Expression produced null
```

Row 2 failed because `TO_INTEGER("bad")` returned `null` in safe mode. The
reject file contains the row with its `_error_message` metadata.

### Example 2: Filter Unmatched Flow

Split rows based on a business rule, sending non-matching rows to a separate
file for review.

```json
{
    "name": "order_quality_check",
    "version": "2.0",
    "components": [
        {
            "id": "read",
            "type": "file_input",
            "config": {
                "path": "/data/orders.csv",
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "status", "type": "string"},
                    {"name": "amount", "type": "integer"}
                ]
            }
        },
        {
            "id": "quality_filter",
            "type": "filter",
            "config": {
                "condition": "status == 'active' && amount > 0",
                "reject_output": true
            }
        },
        {
            "id": "write_valid",
            "type": "file_output",
            "config": {"path": "/data/valid_orders.csv"}
        },
        {
            "id": "write_invalid",
            "type": "file_output",
            "config": {"path": "/data/invalid_orders.csv"}
        }
    ],
    "flows": [
        {"source": "read", "target": "quality_filter"},
        {"source": "quality_filter", "target": "write_valid"},
        {"source": "quality_filter", "target": "write_invalid", "output": "unmatched"}
    ]
}
```

### Example 3: Combined Map and Filter Reject Flows

A pipeline that first does safe type casting (catching data-quality errors),
then applies a business-rule filter (catching logical rejects).

```json
{
    "name": "full_validation_pipeline",
    "version": "2.0",
    "components": [
        {
            "id": "read",
            "type": "file_input",
            "config": {
                "path": "/data/raw_transactions.csv",
                "schema": [
                    {"name": "txn_id", "type": "string"},
                    {"name": "raw_amount", "type": "string"},
                    {"name": "raw_date", "type": "string"}
                ]
            }
        },
        {
            "id": "parse",
            "type": "map",
            "config": {
                "die_on_error": false,
                "outputs": [
                    {
                        "name": "main",
                        "columns": [
                            {"name": "txn_id", "expression": "txn_id"},
                            {"name": "amount", "expression": "TO_FLOAT(raw_amount)"},
                            {"name": "date", "expression": "raw_date"}
                        ]
                    }
                ]
            }
        },
        {
            "id": "business_rules",
            "type": "filter",
            "config": {
                "condition": "amount > 0",
                "reject_output": true
            }
        },
        {
            "id": "write_good",
            "type": "file_output",
            "config": {"path": "/data/good_transactions.csv"}
        },
        {
            "id": "write_parse_errors",
            "type": "file_output",
            "config": {"path": "/data/parse_errors.csv"}
        },
        {
            "id": "write_rule_rejects",
            "type": "file_output",
            "config": {"path": "/data/rule_rejects.csv"}
        }
    ],
    "flows": [
        {"source": "read", "target": "parse"},
        {"source": "parse", "target": "business_rules"},
        {"source": "parse", "target": "write_parse_errors", "output": "reject"},
        {"source": "business_rules", "target": "write_good"},
        {"source": "business_rules", "target": "write_rule_rejects", "output": "unmatched"}
    ]
}
```

This produces three output files:

- `good_transactions.csv` -- parsed successfully AND passed business rules
- `parse_errors.csv` -- rows where `TO_FLOAT(raw_amount)` failed (e.g.,
  non-numeric strings)
- `rule_rejects.csv` -- rows that parsed fine but had `amount <= 0`

### Example 4: Checking Results in Code

```python
from v2 import PyETLEngine

engine = PyETLEngine("job.json")
result = engine.execute()

if result["status"] == "success":
    print(f"Job completed in {result['duration_ms']}ms")

    # Check per-component stats
    for comp_id, stats in result["components"].items():
        print(f"  {comp_id}: type={stats['type']}, "
              f"duration={stats['duration_ms']}ms, "
              f"barrier={stats.get('barrier', False)}")
        if "rows_out" in stats:
            for output_name, count in stats["rows_out"].items():
                print(f"    output '{output_name}': {count} rows")

elif result["status"] == "error":
    print(f"FAILED: [{result['error_type']}] {result['error']}")
```

---

## Best Practices

### When to Use die_on_error: false

Use `die_on_error: false` when:

- You are ingesting data from external sources with unreliable data quality
  (CSV uploads, API responses, third-party feeds).
- The pipeline should not fail because of a few bad rows.
- You want to audit which rows failed and why.
- You are doing type conversions (`TO_INTEGER`, `TO_FLOAT`, `TO_DECIMAL`,
  `TO_BOOLEAN`) on user-supplied string data.

Do **not** use `die_on_error: false` when:

- You need strict data contracts and a single bad row means the whole batch is
  suspect.
- The expressions do not involve type casts (safe mode only affects cast
  functions).
- You are in development and want to catch problems early.

### When to Use Filter reject_output

Use `reject_output: true` on Filter when:

- You have business rules that split data into "matched" and "unmatched"
  categories.
- You need to route non-matching rows somewhere (audit table, manual review
  queue) rather than discard them.

Note: The Filter output port is named `"unmatched"` (not `"reject"`) because
it represents a business-logic split, not a data error.

### Reject / Unmatched Flow Wiring Checklist

1. Set `die_on_error: false` on the Source, Map, or PythonRow component config
   (or `reject_output: true` on Filter).
2. Add a sink component for the secondary output (e.g., a `file_output`).
3. Add a flow with the correct output port:
   - `"output": "reject"` for Source, Map, and PythonRow components.
   - `"output": "unmatched"` for Filter components.
4. If you forget step 3, the secondary output is computed but never consumed --
   it will be silently discarded.

### Error Monitoring

- Always check `result["status"]` after `engine.execute()`.
- For reject flows, monitor the row counts in reject outputs. If the reject
  file grows unexpectedly, your upstream data quality may have degraded.
- The `result["components"]` dict contains per-component stats including
  `duration_ms` and `rows_out` (when the component is a barrier). Use these to
  track pipeline health over time.
- Log the `error_type` field when jobs fail to help categorize failures
  (e.g., `CompileError` vs `ComputeError` vs `FileNotFoundError`).

### Safe Mode Limitations

The `safe` flag only affects **type cast functions** (`TO_INTEGER`, `TO_FLOAT`,
`TO_BOOLEAN`, `TO_DECIMAL`). Other expression errors (unknown function names,
missing columns, invalid syntax) still raise immediately regardless of the
`die_on_error` setting. Safe mode is not a blanket error suppressor -- it is
specifically designed for data-quality issues in type conversions.

### The _error_message Column

The reject output from Map always includes an `_error_message` column with the
value `"Expression produced null"`. This is a metadata column, not a column
from your data. If you need to distinguish which expression failed, you can
inspect which computed columns are `null` in the reject output rows.
