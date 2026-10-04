# PyETL Engine v2

Python-native ETL engine built on Polars for high-performance data transformations.

## Overview

The v2 engine is a pure Python implementation that offers:

- **High Performance**: Uses Polars for 10-100x faster processing than pandas
- **Lazy Evaluation**: Deferred computation with smart materialization
- **Memory Management**: Automatic disk spill for large datasets (process 50GB with 16GB RAM)
- **Expression DSL**: Rich expression language for transformations
- **Type Safety**: Explicit schema definition (no automatic type inference)

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from src.v2 import PyETLEngine

# Define job configuration
config = {
    "name": "my_job",
    "engine": "python",
    "components": [
        {
            "id": "input",
            "type": "file_input",
            "config": {
                "path": "data/input.csv",
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "amount", "type": "float"}
                ]
            }
        },
        {
            "id": "transform",
            "type": "map",
            "config": {
                "outputs": [{
                    "name": "main",
                    "columns": [
                        {"name": "id", "expression": "id"},
                        {"name": "upper_name", "expression": "UPPER(name)"},
                        {"name": "doubled", "expression": "amount * 2"}
                    ]
                }]
            }
        },
        {
            "id": "output",
            "type": "file_output",
            "config": {"path": "data/output.csv"}
        }
    ],
    "flows": [
        {"source": "input", "target": "transform"},
        {"source": "transform", "target": "output"}
    ]
}

# Execute
engine = PyETLEngine(config)
result = engine.execute()

print(f"Status: {result['status']}")
print(f"Rows processed: {result['components_executed']}")
```

### From JSON File

```python
engine = PyETLEngine("jobs/my_job.json")
result = engine.execute()
```

## Architecture

```
                ┌──────────────────────────────────────────────────┐
                │                  PyETLEngine                      │
                ├──────────────────────────────────────────────────┤
                │  1. Load & validate config (JSON/dict/Pydantic)  │
                │  2. Build execution DAG (topological sort)       │
                │  3. Execute components (lazy LazyFrame passing)  │
                │  4. Materialize at barriers (sort/aggregate)     │
                └──────────────────────────────────────────────────┘
                       │              │              │
            ┌──────────┘              │              └──────────┐
            ▼                         ▼                         ▼
    ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
    │  18 Components │         │  Expressions  │         │    Memory     │
    ├───────────────┤         ├───────────────┤         ├───────────────┤
    │ Source (3)    │         │ • Tokenizer   │         │ • Ref counting│
    │ Transform (4) │         │ • Parser      │         │ • Barriers    │
    │ Aggregate (2) │         │ • Compiler    │         │ • Disk spill  │
    │ Sink (2)     │         │ • 50+ funcs   │         │   (Parquet)   │
    │ Utility (2)  │         │ • Routines    │         └───────────────┘
    │ Iterate (2)  │         └───────────────┘
    │ Python (3)   │
    └───────────────┘
```

## Components

### Source Components

| Type | Aliases | Description |
|------|---------|-------------|
| `file_input_delimited` | `file_input`, `file_input_csv` | Read CSV/TSV files with explicit schema |
| `file_input_excel` | | Read Excel files (single/multi-sheet, regex matching) |
| `file_input_full_row` | `file_input_full` | Read each line as a single string column |

### Transform Components

| Type | Aliases | Description |
|------|---------|-------------|
| `map` | | Column expressions, lookups, multi-output routing |
| `filter` | `filter_rows` | Row filtering with expressions |
| `select` | `filter_columns` | Column selection and renaming |
| `sort` | `sort_row` | Row sorting with nulls_last/maintain_order |

### Aggregate Components

| Type | Aliases | Description |
|------|---------|-------------|
| `aggregate` | `aggregate_rows` | Group by with 13 aggregation functions |
| `unique` | `deduplicate` | Remove duplicate rows |

### Sink Components

| Type | Aliases | Description |
|------|---------|-------------|
| `file_output` | `file_output_delimited`, `file_output_csv` | Write CSV/TSV files |
| `file_output_parquet` | | Write Parquet files |

### Utility Components

| Type | Aliases | Description |
|------|---------|-------------|
| `union` | `union_all` | Combine multiple inputs |
| `context_load` | | Load context variables from properties/CSV files |

### Iterate Components

| Type | Aliases | Description |
|------|---------|-------------|
| `flow_to_iterate` | | Convert flow data into iteration context |
| `file_list` | `iterate_file_list` | Iterate over files matching a glob pattern |

### Python Code Components

| Type | Description |
|------|-------------|
| `python_code` | Execute arbitrary Python code with DataFrame access |
| `python_row` | Per-row processing (scalar or vectorized) |
| `python_dataframe` | Full DataFrame access with optional pandas mode |

## Key Concepts

### Explicit Schema

The v2 engine **never infers column names or types**. You must always provide an explicit schema:

```json
{
    "type": "file_input",
    "config": {
        "path": "data.csv",
        "schema": [
            {"name": "id", "type": "integer"},
            {"name": "created_at", "type": "date", "date_pattern": "%Y-%m-%d"},
            {"name": "amount", "type": "float"}
        ]
    }
}
```

### Lazy Evaluation

Data flows as Polars `LazyFrame` objects. Computation is deferred until:
- A component requires full input (sort, aggregate)
- Data is written to output
- Memory limits are reached

### Expression DSL

Rich expression language for transformations:

```
// Column reference
amount

// Arithmetic
amount * 2 + 10

// Functions
UPPER(TRIM(name))

// Conditionals
status == 'active' ? amount : 0

// Context variables
amount * context.tax_rate

// String concatenation
CONCAT(first_name, ' ', last_name)

// Null handling
COALESCE(middle_name, '')
```

See [EXPRESSIONS.md](EXPRESSIONS.md) for full reference.

## Documentation

### Reference
- [COMPONENTS.md](COMPONENTS.md) — All 18 components: config options, examples, notes
- [EXPRESSIONS.md](EXPRESSIONS.md) — Expression DSL: operators, functions, routines, conditionals
- [CONFIGURATION.md](CONFIGURATION.md) — Job JSON structure: context vars, components, flows

### Guides
- [PYTHON_COMPONENTS.md](PYTHON_COMPONENTS.md) — PythonCode, PythonRow, PythonDataFrame deep dive
- [ROUTINES.md](ROUTINES.md) — Creating and using Python routines in expressions
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) — Converting Talend tJavaRow to V2 equivalents
- [DEVELOPMENT.md](DEVELOPMENT.md) — How to create a new V2 component

### Deep Dives
- [ARCHITECTURE.md](ARCHITECTURE.md) — Engine internals: DAG, barriers, lazy fusion, memory, expression compiler
- [ERROR_HANDLING.md](ERROR_HANDLING.md) — Error levels, die_on_error, reject flows
- [MEMORY_MANAGEMENT.md](MEMORY_MANAGEMENT.md) — Reference counting, benchmarks, performance tuning
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — 42 scenarios: problem → cause → solution

## Testing

```bash
# Run all v2 tests
pytest tests/v2 -v

# Run with coverage
pytest tests/v2 --cov=src/v2 --cov-report=html
```

## Engine Selection (Router)

The router automatically selects the engine based on configuration:

```python
from router import run_job

# Runs v2 engine (engine: "python")
result = run_job({
    "engine": "python",
    ...
})

# Runs v1 engine (engine: "talend" or omitted)
result = run_job({
    "engine": "talend",
    ...
})
```
