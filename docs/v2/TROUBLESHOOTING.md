# V2 Engine Troubleshooting Guide

This guide covers the most common errors you will encounter when building and
running ETL pipelines with the V2 (Polars-based) engine.  Each section follows
the pattern **Problem / Cause / Solution** and includes the actual error
messages the engine produces so you can search for them directly.

---

## Table of Contents

1. [Configuration Errors](#1-configuration-errors)
2. [Expression Errors](#2-expression-errors)
3. [File I/O Errors](#3-file-io-errors)
4. [DAG Errors](#4-dag-errors)
5. [Python Component Errors](#5-python-component-errors)
6. [Runtime and Performance Issues](#6-runtime-and-performance-issues)
7. [Common Mistakes](#7-common-mistakes)

---

## 1. Configuration Errors

### 1.1 Unknown Component Type

**Error message:**

```
ValueError: Unknown component type: my_transform. Registered: ['aggregate', 'file_input', 'file_input_csv', ...]
```

**Cause:** The `type` field in a component definition does not match any
registered component name.  Type names are case-insensitive, but they must
match a name that a component class registered with `@REGISTRY.register()`.

**Solution:** Use one of the types listed in the error message.  Common type
names and their aliases:

| Canonical Name          | Aliases                                       |
|-------------------------|-----------------------------------------------|
| `file_input`            | `file_input_delimited`, `file_input_csv`       |
| `file_input_excel`      | --                                             |
| `file_output`           | `file_output_delimited`, `file_output_csv`     |
| `map`                   | --                                             |
| `filter`                | `filter_rows`                                  |
| `select`                | `filter_columns`                               |
| `sort`                  | `sort_row`                                     |
| `aggregate`             | `aggregate_rows`                               |
| `union`                 | `union_all`                                    |
| `python_code`           | --                                             |
| `python_dataframe`      | --                                             |
| `python_row`            | --                                             |

If you are writing a custom component, make sure the module that defines it is
imported in `src/v2/components/<category>/__init__.py` so the `@REGISTRY.register()`
decorator runs before the engine attempts to look it up.

---

### 1.2 Missing Required Fields (Pydantic Validation)

**Error message (examples):**

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for JobConfig
name
  Field required [type=missing, ...]
```

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ComponentConfig
id
  Field required [type=missing, ...]
```

**Cause:** The job configuration is validated by Pydantic models at load time.
`JobConfig` requires `name`.  Each `ComponentConfig` requires `id` and `type`.
Each `FlowConnection` requires `source` and `target`.

**Solution:** Ensure your configuration includes all mandatory fields.
Minimal valid skeleton:

```json
{
  "name": "my_job",
  "components": [
    {"id": "src_1", "type": "file_input", "config": {"path": "data.csv"}}
  ],
  "flows": []
}
```

---

### 1.3 Component-Level Validation Failures

**Error message:**

```
ValueError: Component my_map validation errors: ["Map requires at least one output definition"]
```

**Cause:** After the component is instantiated, the engine calls
`component.validate()`.  Each component checks for its own required config
keys.  Here are the required fields for each component type:

| Component          | Required `config` Keys                                       |
|--------------------|--------------------------------------------------------------|
| `file_input`       | `path`                                                       |
| `file_input_excel` | `path`                                                       |
| `file_output`      | `path`                                                       |
| `map`              | `outputs` (list with at least one entry; each needs `name` and `columns`) |
| `filter`           | `condition`                                                  |
| `select`           | `columns`                                                    |
| `sort`             | `columns`                                                    |
| `aggregate`        | `aggregations`                                               |
| `python_code`      | `code` (non-empty string)                                    |
| `python_dataframe` | `code` (non-empty string)                                    |
| `python_row`       | `code`, `output_columns` (list of `{name, type}` dicts)     |

**Solution:** Add the missing keys to the component's `config` object.

Example -- fixing a map component that is missing `outputs`:

```json
{
  "id": "transform_1",
  "type": "map",
  "config": {
    "outputs": [
      {
        "name": "main",
        "columns": [
          {"name": "id", "expression": "id"},
          {"name": "full_name", "expression": "CONCAT(first, ' ', last)"}
        ]
      }
    ]
  }
}
```

---

### 1.4 Invalid Flow References

**Error message:**

```
DAGValidationError: Source node not found: nonexistent_component
```

```
DAGValidationError: Target node not found: nonexistent_component
```

**Cause:** A flow's `source` or `target` field names a component ID that does
not appear in the `components` list.  This is caught during DAG construction
when `DAGBuilder.build()` calls `dag.add_edge()`.

**Solution:** Double-check that the `source` and `target` in every flow entry
match an `id` in the `components` array.  Watch for typos and copy-paste
errors.

```json
"flows": [
  {"source": "src_1", "target": "map_1"},
  {"source": "map_1", "target": "out_1"}
]
```

---

### 1.5 Invalid Context Variable Type

**Error message:**

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ContextVariable
type
  Input should be 'str', 'int', 'float', 'bool', 'date' or 'datetime' [type=enum, ...]
```

**Cause:** The `type` field in a context variable is not one of the supported
`ContextVariableType` enum values.

**Solution:** Use one of: `str`, `int`, `float`, `bool`, `date`, `datetime`.

```json
"context": {
  "tax_rate": {"value": 0.08, "type": "float"},
  "region":   {"value": "US",  "type": "str"}
}
```

You can also pass simple values without the `{value, type}` wrapper -- the
engine auto-detects the type:

```json
"context": {
  "tax_rate": 0.08,
  "region": "US"
}
```

---

### 1.6 Invalid Schema Type in File Components

**Error message (at runtime, not validation):**

Polars may raise a `SchemaError` or the column may silently read as `Utf8` if
the type string is not recognized by the `TYPE_MAPPING`.

**Cause:** The `type` field in a schema column definition does not match any
key in the `TYPE_MAPPING` dictionary.

**Solution:** Use one of these recognized type names:

- Strings: `string`, `str`
- Integers: `integer`, `int`, `long`
- Floats: `float`, `double`
- Booleans: `boolean`, `bool`
- Dates: `date`, `datetime`
- Decimal: `decimal`
- Talend ID types: `id_String`, `id_Integer`, `id_Long`, `id_Float`,
  `id_Double`, `id_Boolean`, `id_Date`, `id_BigDecimal`

Note that `date` and `datetime` are read as `Utf8` (string) initially and must
be parsed with `TO_DATE()` or `PARSE_DATE()` in a downstream expression if you
need actual date operations.

---

## 2. Expression Errors

The V2 expression engine has three phases: tokenization, parsing, and
compilation.  Errors from each phase have distinct exception types.

### 2.1 Unterminated String Literal

**Error message:**

```
TokenizerError: Unterminated string literal at position 14
```

**Cause:** A quoted string is opened with `"` or `'` but never closed.

**Solution:** Make sure every string literal has matching quotes.

```
WRONG:  CONCAT(name, " - )
RIGHT:  CONCAT(name, " - ")
```

---

### 2.2 Unexpected Character

**Error message:**

```
TokenizerError: Unexpected character: & at position 8
```

**Cause:** The tokenizer encountered a character it does not recognize.  A
common case is using a single `&` instead of `&&` for logical AND, or a single
`|` instead of `||` for logical OR.

**Solution:**

```
WRONG:  status == 'active' & amount > 0
RIGHT:  status == 'active' && amount > 0
```

---

### 2.3 Unexpected Token (Parse Error)

**Error message:**

```
ParseError: Expected RPAREN, got EOF
```

```
ParseError: Unexpected token: Token(COMMA, ',')
```

**Cause:** The expression is syntactically invalid.  Common causes:
- Mismatched parentheses
- Missing argument separators (commas)
- Incomplete ternary expressions (`condition ?` without `: else`)

**Solution:** Verify parentheses balance and argument counts.

```
WRONG:  UPPER(CONCAT(first, last)
RIGHT:  UPPER(CONCAT(first, last))
```

```
WRONG:  amount > 0 ? "positive"
RIGHT:  amount > 0 ? "positive" : "non-positive"
```

---

### 2.4 Unknown Function Name

**Error message:**

```
CompileError: Unknown function: STRLEN
```

**Cause:** The function name is not in the compiler's built-in function
registry.  The tokenizer recognizes it as a function (because it is followed
by `(`), but the compiler has no implementation for it.

**Solution:** Use the correct function name.  Common corrections:

| Wrong Name   | Correct Name   |
|-------------|----------------|
| `STRLEN`    | `LENGTH`       |
| `TOUPPER`   | `UPPER`        |
| `TOLOWER`   | `LOWER`        |
| `ISNULL`    | `ISNULL` (correct) or `NVL` / `IFNULL` |
| `SIZE`      | `LENGTH`       |

The full list of supported functions is in
`src/v2/expressions/tokenizer.py::Tokenizer.FUNCTIONS` and
`src/v2/expressions/compiler.py::ExpressionCompiler._build_function_registry`.

---

### 2.5 Wrong Argument Count

**Error message (examples):**

```
CompileError: CONCAT requires at least 2 arguments
```

```
CompileError: SUBSTRING requires at least 2 arguments
```

```
CompileError: PARSE_DATE requires format argument
```

```
CompileError: DATE_DIFF requires 2 arguments
```

**Cause:** A built-in function was called with too few (or too many)
arguments.

**Solution:** Check the required signature:

| Function          | Signature                                             |
|-------------------|-------------------------------------------------------|
| `CONCAT`          | `CONCAT(str1, str2, ...)`  (2+ args)                 |
| `SUBSTRING`       | `SUBSTRING(str, start)` or `SUBSTRING(str, start, length)` |
| `LPAD` / `RPAD`   | `LPAD(str, length)` or `LPAD(str, length, fill_char)` |
| `PARSE_DATE`      | `PARSE_DATE(str, format)`                             |
| `FORMAT_DATE`     | `FORMAT_DATE(date_col, format)`                       |
| `DATE_ADD`        | `DATE_ADD(date_col, days)`                            |
| `DATE_DIFF`       | `DATE_DIFF(date1, date2)`                             |
| `REGEX_EXTRACT`   | `REGEX_EXTRACT(str, pattern)` or `REGEX_EXTRACT(str, pattern, group)` |
| `ROUND`           | `ROUND(num)` or `ROUND(num, decimals)`                |
| `IF`              | `IF(condition, then_value, else_value)`               |

---

### 2.6 Unknown Context Variable

**Error message:**

```
CompileError: Unknown context variable: tax_rat
```

**Cause:** An expression references `context.tax_rat` but the job config does
not define a context variable named `tax_rat`.

**Solution:** Check that the variable name matches exactly (case-sensitive)
what is defined in the `context` section of the job config.

```json
"context": {
  "tax_rate": {"value": 0.08, "type": "float"}
}
```

```
WRONG:   amount * context.tax_rat
RIGHT:   amount * context.tax_rate
```

---

### 2.7 Unknown Routine Function

**Error message:**

```
CompileError: Cannot call routine MyRoutine.transform: no routine registry configured
```

```
CompileError: Unknown routine function: MyRoutine.transform
```

**Cause:**

- First message: The expression compiler was not given a `routine_registry`.
  This is a known engine issue -- the routine registry is not always passed to
  Map/Filter expression compilation.
- Second message: The routine or function name does not exist in the registry.

**Solution:** For the first case, ensure you are passing a `routines_dir` to
the `PyETLEngine` constructor.  For the second case, verify that:

1. The routine file exists in the routines directory.
2. The class name is PascalCase (e.g., `MyRoutine`) -- the tokenizer only
   recognizes PascalCase identifiers followed by `.function()` as routine calls.
3. The function name exists in the routine class.

---

### 2.8 Column Not Found at Runtime

**Error message (from Polars, not the expression engine):**

```
polars.exceptions.ColumnNotFoundError: column "customr_name" not found
```

**Cause:** The expression compiled successfully (the compiler does not
validate column names), but at execution time Polars cannot find the
referenced column in the DataFrame.

**Solution:** Check for typos in column names.  Use the schema defined by
upstream components to verify what columns are available.

For lookup columns, remember that the Map component prefixes them:

```
WRONG:  name                     (raw lookup column)
RIGHT:  customers.name           (prefixed with lookup name)
```

---

### 2.9 Unknown Operator

**Error message:**

```
CompileError: Unknown operator: ^
```

**Cause:** The expression uses an operator the compiler does not support.

**Solution:** Supported operators are:

- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=` (also `=` as alias for `==`)
- Logical: `&&` / `and`, `||` / `or`, `!` / `not`
- Ternary: `condition ? then : else`

For exponentiation, use `POW(base, exponent)` instead of `^`.

---

## 3. File I/O Errors

### 3.1 File Not Found

**Error message (from Polars):**

```
polars.exceptions.ComputeError: Error: path does not exist: /data/input/orders.csv
```

**Cause:** The file path in the `file_input` config does not point to an
existing file.  This is often because:
- The path is relative but the working directory is different from what you expect.
- A `${context.var}` placeholder was not resolved (the variable is missing or
  misspelled).

**Solution:**

1. Use absolute paths or verify your working directory.
2. Check that context variable resolution works:

```json
{
  "id": "source",
  "type": "file_input",
  "config": {
    "path": "${context.input_dir}/orders.csv"
  }
}
```

If `input_dir` is not defined in the `context` section, the literal string
`${context.input_dir}/orders.csv` is passed to Polars and will fail.  The
engine resolves `${context.varname}` placeholders only for variable names that
exist in the context -- undefined names are left as-is with no warning.

---

### 3.2 Wrong Delimiter

**Error message (from Polars):**

```
polars.exceptions.ComputeError: found more fields than defined in 'Schema'
```

Or the data loads successfully but every row has a single column containing
the entire line.

**Cause:** The `delimiter` in the config does not match the actual file's
delimiter.

**Solution:** Set the correct delimiter.  For tab-delimited files use `"\\t"`:

```json
"config": {
  "path": "data.tsv",
  "delimiter": "\\t"
}
```

The engine translates the escaped `\\t` string to an actual tab character.

---

### 3.3 Schema Does Not Match CSV Columns

**Error message (from Polars):**

```
polars.exceptions.SchemaError: ...
```

**Cause:** The schema overrides in the config specify column names or types
that conflict with what is actually in the file.  For example, specifying a
column as `integer` when it contains non-numeric values.

**Solution:**

- If using `has_header: true` (the default), schema column names must exactly
  match the header names in the file.
- If using `has_header: false`, the schema is used for renaming, and the
  column count must match the number of fields in the file.
- For type mismatches, consider reading the column as `string` and converting
  it later with `TO_INTEGER()` or `TO_FLOAT()` in a Map expression.

---

### 3.4 Excel: Missing Package

**Error message:**

```
ImportError: fastexcel is not installed
```

Or:

```
ModuleNotFoundError: No module named 'openpyxl'
```

**Cause:** Polars `read_excel()` requires the `fastexcel` package (default
engine) or `openpyxl` as a fallback.

**Solution:**

```bash
pip install fastexcel
# or
pip install openpyxl
```

---

### 3.5 Excel: Invalid Sheet Name

**Error message (from Polars/fastexcel):**

```
polars.exceptions.ComputeError: ... sheet not found ...
```

**Cause:** The `sheet` config option names a sheet that does not exist in the
workbook.

**Solution:** Verify the sheet name (case-sensitive) or use a sheet index
(0-based integer) instead:

```json
"config": {
  "path": "data.xlsx",
  "sheet": "Orders"
}
```

---

### 3.6 File Output: Permission Denied

**Error message:**

```
PermissionError: [Errno 13] Permission denied: '/read_only_dir/output.csv'
```

**Cause:** The process does not have write permission to the target directory.
Note that the engine automatically creates parent directories
(`path.parent.mkdir(parents=True, exist_ok=True)`), so the error is about
permissions, not missing directories.

**Solution:** Verify that the output path is writable by the user running the
pipeline.

---

## 4. DAG Errors

### 4.1 Circular Dependencies

**Error message:**

```
DAGValidationError: Graph contains cycles involving: {'comp_a', 'comp_b', 'comp_c'}
```

**Cause:** The flows create a cycle -- component A feeds B, B feeds C, and C
feeds back to A.  The engine uses Kahn's algorithm for topological sort and
detects this when not all nodes can be visited.

**Solution:** Review the flow connections listed in the error and remove the
back-edge.  You can visualize the graph by listing each flow's `source ->
target` to find the loop.

---

### 4.2 No Source Components

**Error message:**

```
DAGValidationError: DAG validation failed: ['No source components found (all components have upstream)']
```

**Cause:** Every component in the job has at least one incoming flow.  The
engine expects at least one source node (a component with no upstream edges)
to start execution.

**Solution:** Ensure that source components (like `file_input`) do not have
any flows targeting them.  If you accidentally added a flow that targets a
source, remove it.

---

### 4.3 Empty DAG

**Error message:**

```
DAGValidationError: DAG validation failed: ['DAG is empty - no components defined']
```

**Cause:** The `components` list in the job configuration is empty.

**Solution:** Add at least one component to the job.

---

### 4.4 Disconnected Components (No Input and Not a Source)

The DAG validator does not explicitly error on disconnected non-source
components.  However, a component that is not a source type but has no
incoming flows will execute with an empty `inputs` dict.  Most components
return `{}` in this case, which means they silently produce no output and
downstream components receive nothing.

**Symptom:** A component runs but produces zero rows, and there is no error
in the result.

**Solution:** Verify that every non-source component is the target of at
least one flow.

---

## 5. Python Component Errors

### 5.1 Code Does Not Set `output_df`

**Error message:**

```
RuntimeError: Code must set 'output_df' variable
```

**Cause:** The Python code executed by `python_code` or `python_dataframe`
finished without assigning to the `output_df` variable.

**Solution:** Make sure your code assigns a Polars (or pandas, if
`use_pandas: true`) DataFrame to `output_df`.

For `python_code`:

```python
# 'input_df' is a Polars DataFrame, 'pl' is the polars module
output_df = input_df.filter(pl.col("amount") > 100)
```

For `python_dataframe`:

```python
# 'df' is a Polars DataFrame (or pandas if use_pandas: true)
output_df = df.filter(pl.col("status") == "active")
```

---

### 5.2 `output_df` Is the Wrong Type

**Error message:**

```
RuntimeError: 'output_df' must be a Polars DataFrame, got <class 'list'>
```

```
RuntimeError: 'output_df' must be a DataFrame, got <class 'dict'>
```

**Cause:** The code set `output_df` to something other than a Polars
DataFrame, Polars LazyFrame, or (for `python_dataframe` with `use_pandas`)
a pandas DataFrame.

**Solution:** Ensure `output_df` is the correct type.  If you built a list
of dicts, convert it:

```python
output_df = pl.DataFrame(my_list_of_dicts)
```

---

### 5.3 Syntax Error in User Code

**Error message:**

```
ValueError: Syntax error in code: invalid syntax (<my_component>, line 3)
```

**Cause:** The Python code string has a syntax error.  The engine compiles
the code with `compile()` and surfaces the `SyntaxError`.

**Solution:** Fix the Python syntax.  The error message includes the line
number relative to the code string.  Be careful with indentation, especially
in JSON strings where leading whitespace may be stripped.

---

### 5.4 Runtime Exception in User Code

**Error message:**

```
RuntimeError: PythonCode execution failed: name 'pandas' is not defined
```

```
RuntimeError: PythonDataFrame execution failed: 'DataFrame' object has no attribute 'collect'
```

**Cause:** The code raised an exception during `exec()`.  Common reasons:
- Referencing a module that was not imported.
- Calling methods that do not exist on the object.
- Index/key errors in the data.

**Solution:** Check the inner error message.  For missing imports, add the
module name to the `imports` list:

```json
"config": {
  "code": "import pandas as pd\noutput_df = pl.from_pandas(pd.DataFrame({'a': [1]}))",
  "imports": ["pandas"]
}
```

Or use the `imports` list to make modules available by name in the execution
namespace:

```json
"config": {
  "code": "output_df = pl.from_pandas(pandas.DataFrame({'a': [1]}))",
  "imports": ["pandas"]
}
```

Note: `imports` makes the module available under its own name (e.g., `pandas`,
not `pd`).  For aliases, use an `import ... as ...` statement inside the
code itself.

---

### 5.5 PythonRow: Missing or Invalid `output_columns`

**Error message:**

```
ValueError: Component my_row validation errors:
  ["Missing required configuration: 'output_columns'"]
```

```
ValueError: Component my_row validation errors:
  ["output_columns[0] missing 'type'", "output_columns[1] unknown type: varchar"]
```

**Cause:** The `python_row` component requires `output_columns` with both
`name` and `type` for every entry.

**Solution:** Define output columns with recognized types:

```json
"config": {
  "code": "return {'full_name': row['first'] + ' ' + row['last']}",
  "output_columns": [
    {"name": "full_name", "type": "string"}
  ]
}
```

Recognized types: `string`, `str`, `utf8`, `integer`, `int`, `int64`,
`float`, `float64`, `double`, `boolean`, `bool`, `date`, `datetime`.

---

## 6. Runtime and Performance Issues

### 6.1 Out of Memory

**Symptom:** The process is killed by the OS, or you see:

```
polars.exceptions.ComputeError: OOM
```

**Cause:** The pipeline materializes too much data in memory.  The V2 engine
uses lazy evaluation (Polars `LazyFrame`) and only collects at barrier points.
However, every barrier forces a full materialization.  Common causes of
excessive memory use:

- Too many barrier components in sequence (each one collects the full dataset).
- A `python_code` or `python_dataframe` component (always a barrier) placed in
  the middle of a large pipeline.
- A lookup join with `match_mode: all` that multiplies rows significantly.

**Solution:**

- Minimize the number of barriers.  Consolidate multiple Map components into
  one where possible, so Polars can fuse the entire plan before collecting.
- Move Python components to the end of the pipeline where the data is already
  filtered/aggregated.
- Add filters early to reduce data volume before barriers.
- For large lookup joins, use `match_mode: first` or `match_mode: last`
  instead of `all` when you only need one match per row.

---

### 6.2 Slow Execution (Barriers Breaking Lazy Fusion)

**Symptom:** The pipeline takes much longer than expected, even though
individual operations are simple.

**Cause:** Every barrier point forces Polars to collect the LazyFrame,
breaking the query optimizer's ability to fuse operations.  Components that
are barriers:

- All sink components (`file_output`, etc.) -- by design.
- All Python components (`python_code`, `python_dataframe`, `python_row`).
- Any component that produces multiple outputs (e.g., `filter` with
  `reject_output: true`, `map` with multiple output definitions).
- Fan-out points (one component feeding two or more downstream components).

**Solution:**

- Combine sequential Map components into a single Map with all the column
  expressions in one output.
- Avoid using `reject_output: true` on Filter unless you actually consume the
  reject stream.
- If you need a Python UDF for a single column transformation, consider
  writing a routine instead (routines compile into Polars expressions and do
  not force collection).

To see where barriers occur, check the `barrier` field in the execution result
stats:

```python
result = engine.execute()
for comp_id, stats in result.get("components", {}).items():
    if stats.get("barrier"):
        print(f"BARRIER: {comp_id} ({stats['type']})")
```

---

### 6.3 Lookup Join Exploding Row Count

**Symptom:** The output has far more rows than the input.  Memory usage
spikes during a Map component.

**Cause:** A lookup join with `match_mode: all` (the default) keeps every
matching row from the lookup table.  If the join keys are not unique in the
lookup, a single input row can be duplicated for each match.

**Solution:**

1. Set `match_mode` to `first` or `last` if you only need one match per key:

```json
"lookups": [
  {
    "name": "customers",
    "input": "lookup_customers",
    "keys": [{"main": "customer_id", "lookup": "id"}],
    "join_type": "left",
    "match_mode": "first"
  }
]
```

2. Deduplicate the lookup data upstream before it reaches the Map component.

3. For intentional many-to-many joins, add a filter or aggregate downstream
   to reduce the result set.

---

### 6.4 Cross Join Producing Cartesian Product

**Symptom:** A Map component with a lookup configured with `join_type: cross`
or with an empty `keys` list produces rows = (input rows) x (lookup rows).

**Cause:** This is the intended behavior of a cross join.  A cross join
between 10,000 input rows and 1,000 lookup rows produces 10,000,000 output
rows.

**Solution:** Avoid cross joins on large datasets.  If you need to combine
data from two sources, ensure you have join keys:

```json
"keys": [{"main": "id", "lookup": "id"}]
```

If you intentionally need a cross join, filter aggressively afterward.

---

## 7. Common Mistakes

### 7.1 Forgetting to Connect a Component in Flows

**Symptom:** A component runs but produces zero rows.  No error is raised.

**Cause:** The component is defined in `components` but has no incoming flow
in `flows`.  If it is not a source component, its `inputs` dict will be
empty, and most components return `{}` for empty inputs.

**Solution:** Add a flow that connects the upstream component to this one:

```json
"flows": [
  {"source": "source_1", "target": "map_1"},
  {"source": "map_1",    "target": "output_1"}
]
```

---

### 7.2 Wrong Lookup Column Prefix

**Symptom:**

```
polars.exceptions.ColumnNotFoundError: column "name" not found
```

in a Map expression that references a lookup column.

**Cause:** The Map component prefixes all lookup columns with
`{lookup_name}.{column}`.  If your lookup is named `customers` and it has a
column `name`, you must reference it as `customers.name`, not just `name`.

**Solution:**

```json
"columns": [
  {"name": "customer_name", "expression": "customers.name"}
]
```

This applies to all lookup columns.  The join key columns from the lookup are
**not** prefixed (they match the main input's key columns), but all other
lookup columns are.

---

### 7.3 Using `reject` Output Without Wiring It

**Symptom:** The Map component with `die_on_error: false` or a Filter with
`reject_output: true` produces a `reject` output, but no downstream component
consumes it.  The rejected rows are silently lost.

**Cause:** The engine does not warn when an output port has no downstream
consumer.  The data is simply stored in the execution context and then
garbage collected.

**Solution:** If you want to capture rejected rows, wire the reject output to
a sink:

```json
"flows": [
  {"source": "map_1", "output": "main",   "target": "output_main"},
  {"source": "map_1", "output": "reject", "target": "output_rejects"}
]
```

If you do not need the reject rows, this is harmless -- just be aware they
are dropped.

---

### 7.4 Python Code Using LazyFrame Methods on a Collected DataFrame

**Symptom:**

```
RuntimeError: PythonCode execution failed: 'DataFrame' object has no attribute 'filter'
```

Wait -- `filter` does exist on DataFrame.  But some LazyFrame-only methods
like `collect()`, `explain()`, or `pipe()` with LazyFrame-specific arguments
will fail.

**Cause:** Python components are barriers.  The engine collects the LazyFrame
to a DataFrame before passing it to your code as `input_df` or `df`.  If you
call `.collect()` on a DataFrame, you get an `AttributeError`.

**Solution:** Remember that inside `python_code`, `input_df` is always a
`pl.DataFrame`.  Inside `python_dataframe`, `df` is a `pl.DataFrame` (or
pandas DataFrame if `use_pandas: true`).  Do not call `.collect()` on it:

```python
# WRONG: input_df is already collected
output_df = input_df.collect()

# RIGHT: work directly with the DataFrame
output_df = input_df.filter(pl.col("amount") > 0)
```

---

### 7.5 Context Variable Not Resolving in Expressions

**Symptom:** An expression like `amount * context.tax_rate` fails with
`CompileError: Unknown context variable: tax_rate` even though the context is
defined.

**Cause:** There are two different context resolution mechanisms, and they are
easy to confuse:

1. **Config-level `${context.var}` placeholders** -- resolved by
   `Component.resolve_context()` for string config values like file paths.
2. **Expression-level `context.var` references** -- resolved by the expression
   compiler.  The compiler receives the context dict at compile time.

If you put `${context.tax_rate}` inside an expression string, it will be
resolved to the literal value before the expression compiler ever sees it.  If
you put `context.tax_rate` (without `${}`), the expression compiler resolves it.

Both work, but they behave differently:

```json
"expression": "amount * context.tax_rate"
```

This is resolved by the expression compiler and produces `amount * pl.lit(0.08)`.

```json
"expression": "amount * ${context.tax_rate}"
```

This is resolved by `resolve_context()` first, producing the string
`"amount * 0.08"`, which is then parsed as an expression.  Both produce the
same result.

If neither works, check that the context variable is defined in the
job-level `context` section.

---

### 7.6 Aggregate Function Silently Ignored

**Symptom:** An aggregation produces a result but one of the expected output
columns is missing.

**Cause:** The Aggregate component logs a warning for unknown function names
but does not raise an error -- it returns `None` and the expression is
skipped:

```
WARNING: Unknown aggregation function: average
```

**Solution:** Use the correct function name.  Supported aggregate functions:
`sum`, `count`, `avg`, `mean`, `min`, `max`, `first`, `last`,
`count_distinct`, `std`, `var`, `median`.

Note: the function name is `avg` (not `average`), and `mean` is an alias for
`avg`.

---

### 7.7 Union Component Schema Mismatch

**Symptom:**

```
polars.exceptions.ShapeError: unable to vstack, column names don't match
```

**Cause:** The Union component uses `pl.concat(..., how="vertical_relaxed")`
which is lenient with types, but if `align_schemas` is set to `false` and the
input frames have different column names, Polars will raise this error.

**Solution:** Keep `align_schemas: true` (the default).  This automatically
adds missing columns as null to align all input frames before concatenation.

If you set `align_schemas: false`, ensure all input frames have exactly the
same column names and compatible types.

---

### 7.8 Sort Order Not Applied

**Symptom:** The output is not sorted as expected.

**Cause:** A barrier downstream of the Sort component may reorder the data.
For example, a `group_by` in an Aggregate component does not preserve sort
order.  Also, Polars lazy execution may reorder operations for optimization
unless sort is the final operation before collection.

**Solution:** Place the Sort component as close as possible to the final
output sink.  If an Aggregate follows the Sort, the sort is wasted -- apply
the Sort after the Aggregate instead.

---

## Appendix: Reading the Execution Result

When a job fails, the engine returns a result dict with error information:

```python
result = engine.execute()
if result["status"] == "error":
    print(f"Error type: {result['error_type']}")
    print(f"Error message: {result['error']}")
    print(f"Duration: {result['duration_ms']}ms")
    # Per-component stats up to the failure point:
    for comp_id, stats in result.get("components", {}).items():
        print(f"  {comp_id}: {stats}")
```

The `error_type` field gives you the Python exception class name (e.g.,
`ValueError`, `DAGValidationError`, `CompileError`, `RuntimeError`), which
tells you which section of this guide to consult.

| `error_type`           | Guide Section                      |
|------------------------|------------------------------------|
| `ValidationError`      | 1.2, 1.5 (Pydantic)               |
| `ValueError`           | 1.1, 1.3 (component validation)    |
| `DAGValidationError`   | 4.x (DAG structure)                |
| `TokenizerError`       | 2.1, 2.2 (expression tokenization) |
| `ParseError`           | 2.3 (expression parsing)           |
| `CompileError`         | 2.4--2.9 (expression compilation)  |
| `RuntimeError`         | 5.x (Python component execution)   |
| `ComputeError`         | 3.x (Polars I/O or query)          |
| `ColumnNotFoundError`  | 2.8, 7.2 (column name mismatch)    |
| `SchemaError`          | 1.6, 3.3, 7.7 (schema mismatch)   |
