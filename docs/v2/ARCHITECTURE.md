# V2 Engine Architecture Reference

This document describes how the V2 ETL engine (`PyETLEngine`) works internally.
It is a reference for engineers who need to extend, debug, or reason about
the execution model. For usage and component API docs, see [README.md](README.md)
and [COMPONENTS.md](COMPONENTS.md).

---

## Table of Contents

1. [Engine Execution Model](#1-engine-execution-model)
2. [Lazy Pipeline Fusion](#2-lazy-pipeline-fusion)
3. [Barrier System](#3-barrier-system)
4. [DAG and Topological Sort](#4-dag-and-topological-sort)
5. [Reference Counting Memory](#5-reference-counting-memory)
6. [Component Lifecycle](#6-component-lifecycle)
7. [Expression Compilation Pipeline](#7-expression-compilation-pipeline)
8. [Flow Routing](#8-flow-routing)
9. [Context Variables](#9-context-variables)

---

## 1. Engine Execution Model

Entry point: `PyETLEngine.execute()` in `src/v2/engine.py`.

The engine runs a job through four sequential phases:

```
  Config (dict/JSON/Path)
           |
           v
  +-----------------------+
  | 1. Config Validation  |  JobConfig(**config)  -- Pydantic validates
  +-----------------------+
           |
           v
  +-----------------------+
  | 2. DAG Construction   |  DAGBuilder.build(config)
  +-----------------------+
           |
           v
  +-----------------------+
  | 3. Component Creation |  REGISTRY.get(type) -> class -> instantiate -> validate()
  +-----------------------+
           |
           v
  +-----------------------+
  | 4. Execution Loop     |  for component_id in dag.get_execution_order():
  |    (topological)      |      _execute_component(component_id, context)
  +-----------------------+
           |
           v
       Result dict
```

### Phase 1: Config Validation

The constructor accepts a `dict`, a `JobConfig`, or a file path (str/Path).
Raw dicts and JSON files are parsed into a `JobConfig` (Pydantic model) which
validates structure, types, and context variables at construction time.
Invalid configs raise `ValidationError` before any execution begins.

```python
# src/v2/engine.py:36-47
def __init__(self, config, routines_dir=None):
    if isinstance(config, (str, Path)):
        with open(config) as f:
            config = json.load(f)
    if isinstance(config, dict):
        self.config = JobConfig(**config)
    else:
        self.config = config
```

### Phase 2: DAG Construction

`DAGBuilder.build(config)` creates a `DAG` from the config's `components` and
`flows` lists. Each component becomes a `DAGNode`; each flow becomes a directed
edge. The builder runs `dag.validate()` which checks for cycles and disconnected
graphs.

```python
# src/v2/engine.py:51
self.dag = DAGBuilder.build(self.config)
```

### Phase 3: Component Creation

`_create_components()` iterates over config components, looks up each type in
the global `REGISTRY`, instantiates the class, and calls `validate()`. Any
validation errors abort the job.

```python
# src/v2/engine.py:99-124
def _create_components(self, context):
    for comp_config in self.config.components:
        component_class = REGISTRY.get(comp_config.type.lower())
        component = component_class(
            component_id=comp_config.id,
            config=comp_config.config,
            context=context.context_vars,
        )
        errors = component.validate()
        if errors:
            raise ValueError(...)
        self._components[comp_config.id] = component
```

### Phase 4: Execution Loop

The engine iterates through components in topological order. For each component:

1. Gather inputs from upstream outputs (using flow definitions for port routing).
2. Call `component.apply(inputs)`.
3. If the component (or multi-output) is a barrier, materialize via `.collect()`.
4. Store outputs in `ExecutionContext`.
5. Decrement ref counts on upstream components (may free their outputs).

```python
# src/v2/engine.py:72-78
execution_order = self.dag.get_execution_order()
for component_id in execution_order:
    if component_id in self._iterate_managed:
        continue  # handled by iterate loop
    self._execute_component(component_id, context)
```

The result dict includes per-component stats (duration, row counts, barrier
status) and overall job status/duration.

---

## 2. Lazy Pipeline Fusion

The fundamental performance strategy of the V2 engine is lazy evaluation.
Components pass `pl.LazyFrame` objects between each other. No data is
materialized until a barrier is reached.

### Why This Matters

Polars builds a logical plan for lazy operations. When multiple transforms
chain together without a barrier, Polars fuses them into a single optimized
physical plan. This means:

- **Predicate pushdown**: Filters move earlier in the plan (closer to I/O).
- **Projection pushdown**: Only columns actually needed downstream are read.
- **Common subexpression elimination**: Repeated computations are computed once.
- **Zero intermediate DataFrames**: No temporary allocations between transforms.

### Example: Fused vs. Unfused

Consider a pipeline: `FileInput -> Filter -> Map -> Sort -> FileOutput`.

Without lazy fusion (V1 / naive approach):
```
FileInput   -> DataFrame (allocate)
Filter      -> DataFrame (allocate)
Map         -> DataFrame (allocate)
Sort        -> DataFrame (allocate)
FileOutput  -> write
              4 intermediate allocations
```

With lazy fusion (V2):
```
FileInput   -> LazyFrame (plan node)
Filter      -> LazyFrame (plan node appended)
Map         -> LazyFrame (plan node appended)
Sort        -> LazyFrame -- BARRIER: .collect()
                 Polars optimizes & executes the ENTIRE plan at once.
                 1 allocation (the final sorted DataFrame).
FileOutput  -> write from re-wrapped LazyFrame
```

### The Contract

Every component's `apply()` method has this signature:

```python
def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]
```

Inputs are lazy. Outputs must be lazy. Components that need to break this
contract (sinks, Python UDFs) are marked as barriers.

---

## 3. Barrier System

A barrier is a point in the pipeline where the lazy plan is forced to
materialize via `.collect()`. The engine determines barrier status at
execution time in `_execute_component()`:

```python
# src/v2/engine.py:165
is_barrier = component.is_barrier or len(result) > 1
```

### What Triggers a Barrier

| Trigger                      | Mechanism                         | Example Components                    |
|------------------------------|-----------------------------------|---------------------------------------|
| `component.is_barrier = True` | Class property returns `True`    | All `SinkComponent`, `PythonComponent` subclasses |
| `len(result) > 1`            | Multiple output ports             | Map with reject output, multi-output routing |

### Which Components Are Barriers

By class hierarchy:

- **SinkComponent** subclasses (always): `file_output`, `file_output_parquet`
- **PythonComponent** subclasses (always): `python_code`, `python_row`, `python_dataframe`, `flow_to_iterate`, `file_list`
- **UtilityComponent** subclasses (always): `context_load`
- **Any component** producing multiple outputs (at runtime): e.g., a Map that
  emits both `main` and `reject` outputs

**Not barriers** (by default): `SourceComponent`, `TransformComponent` subclasses
like `map`, `filter`, `select`, `sort`, `aggregate`, `unique`, `union`.

### What Happens at a Barrier

```python
# src/v2/engine.py:167-182
if is_barrier and result:
    materialized = {}
    for name, data in result.items():
        if isinstance(data, pl.LazyFrame):
            df = data.collect()                  # <-- materialize
            materialized[name] = df.lazy()       # <-- re-wrap for downstream
            rows_out[name] = len(df)
        elif isinstance(data, pl.DataFrame):
            materialized[name] = data.lazy()
            rows_out[name] = len(data)
        else:
            materialized[name] = data
            rows_out[name] = 0
    result = materialized
```

The sequence is:

1. `data.collect()` -- Polars executes the entire accumulated lazy plan up to
   this point, producing an in-memory `DataFrame`.
2. `df.lazy()` -- The materialized DataFrame is immediately re-wrapped as a
   `LazyFrame` so downstream components receive the expected type.
3. Row counts are captured for stats.

This means barriers are the only places where you can observe actual row counts
and where memory consumption spikes (the full DataFrame exists momentarily).

---

## 4. DAG and Topological Sort

Source: `src/v2/execution/dag.py`

### DAG Construction

`DAGBuilder.build(config)` creates the graph in two passes:

1. **Nodes**: Each `ComponentConfig` becomes a `DAGNode` with empty upstream/downstream sets.
2. **Edges**: Each `FlowConnection` adds the target to the source's `downstream`
   set and the source to the target's `upstream` set.

```python
# src/v2/execution/dag.py:232-263
@classmethod
def build(cls, config: JobConfig) -> DAG:
    dag = DAG()
    for component in config.components:
        dag.add_node(component.id, component.type, component.config)
    for flow in config.flows:
        dag.add_edge(flow.source, flow.target)
    errors = dag.validate()
    if errors:
        raise DAGValidationError(...)
    return dag
```

### DAGNode Structure

```python
@dataclass
class DAGNode:
    component_id: str
    component_type: str
    config: Dict
    upstream: Set[str]    # who feeds into me
    downstream: Set[str]  # who I feed into
```

### Kahn's Algorithm (Topological Sort)

The engine uses Kahn's algorithm to determine execution order. This is a
BFS-based approach that processes nodes with zero in-degree first:

```
Algorithm: get_execution_order()

1. Compute in-degree for each node (= number of upstream edges).
2. Initialize queue with all nodes where in_degree == 0 (sources).
3. While queue is non-empty:
   a. Sort queue (for deterministic ordering).
   b. Pop first node, append to result.
   c. For each downstream neighbor:
      - Decrement its in-degree.
      - If in-degree reaches 0, add to queue.
4. If result length != node count, the graph has cycles -- raise error.
```

```
Example DAG:

    input_1 ──> filter ──> map ──> output
    input_2 ──────────────/

In-degrees: input_1=0, input_2=0, filter=1, map=2, output=1

Step 1: queue=[input_1, input_2]     result=[]
Step 2: pop input_1, decr filter     result=[input_1]
Step 3: pop input_2, decr map        result=[input_1, input_2]
Step 4: pop filter (in_degree=0), decr map  result=[input_1, input_2, filter]
Step 5: pop map (in_degree=0), decr output  result=[input_1, input_2, filter, map]
Step 6: pop output                   result=[input_1, input_2, filter, map, output]
```

The result is cached in `_execution_order` and invalidated whenever nodes or
edges are added.

### Cycle Detection

If after the BFS completes, some nodes were never added to the result (their
in-degree never reached 0), those nodes are involved in a cycle. The engine
raises `DAGValidationError` with the set of remaining node IDs.

---

## 5. Reference Counting Memory

Source: `src/v2/execution/context.py`

The engine tracks how many downstream consumers each component's output has.
Once all consumers have executed, the output is freed.

### How It Works

```
Initialization (engine.py:64-67):
  ref_counts = dag.get_ref_counts()    # {comp_id: len(downstream)}
  for comp_id, count in ref_counts.items():
      context.set_ref_count(comp_id, count)

After each component executes (engine.py:197-198):
  for upstream_id in dag_node.upstream:
      context.decrement_ref(upstream_id)
```

Inside `ExecutionContext.decrement_ref()`:

```python
# src/v2/execution/context.py:46-53
def decrement_ref(self, component_id: str) -> None:
    if component_id not in self._ref_counts:
        return
    self._ref_counts[component_id] -= 1
    if self._ref_counts[component_id] <= 0:
        if component_id in self._outputs:
            del self._outputs[component_id]
```

### Example

```
    A ──> B ──> D
    A ──> C

ref_count(A) = 2   (B and C consume it)
ref_count(B) = 1   (D consumes it)
ref_count(C) = 0   (terminal)

Execution order: A, B, C, D

Execute A: store output. ref_count(A) = 2.
Execute B: read A's output. Decrement A -> ref_count(A) = 1. A's output kept.
Execute C: read A's output. Decrement A -> ref_count(A) = 0. A's output FREED.
Execute D: read B's output. Decrement B -> ref_count(B) = 0. B's output FREED.
```

For lazy (non-barrier) components, "output" is a `LazyFrame` -- a plan node,
not materialized data. Freeing it drops the plan reference. For barrier
components, the output is a re-wrapped `LazyFrame` backed by a just-collected
`DataFrame`. Freeing it releases the actual memory.

### Output Storage Model

Outputs are stored in a two-level dict: `component_id -> output_name -> LazyFrame`.
Each component can have multiple named outputs (e.g., `main`, `reject`).

```python
# src/v2/execution/context.py:28-32
def store_output(self, component_id, output_name, data):
    if component_id not in self._outputs:
        self._outputs[component_id] = {}
    self._outputs[component_id][output_name] = data
```

---

## 6. Component Lifecycle

### Registration

Components self-register using the `@REGISTRY.register()` decorator. This
happens at module import time. The engine's `__init__` imports all component
modules to trigger registration:

```python
# src/v2/engine.py:18-23
from .components import file as _file_components          # noqa: F401
from .components import transform as _transform_components # noqa: F401
from .components import aggregate as _aggregate_components # noqa: F401
from .components import python as _python_components       # noqa: F401
from .components import iterate as _iterate_components     # noqa: F401
from .components import utility as _utility_components     # noqa: F401
```

A component registers under one or more type names:

```python
# Example from src/v2/components/file/file_input_delimited.py:14
@REGISTRY.register("file_input", "file_input_delimited", "file_input_csv")
class FileInputDelimited(SourceComponent):
    ...
```

The registry maps each name (lowercased) to the class. Lookup is O(1):

```python
# src/v2/components/registry.py:45-47
def get(self, name: str) -> Optional[Type[Component]]:
    return self._registry.get(name.lower())
```

### Class Hierarchy

```
Component (ABC)
  |
  +-- SourceComponent         apply() delegates to produce()
  |                            is_barrier = False (default)
  |
  +-- TransformComponent      override apply() directly
  |                            is_barrier = False (default)
  |
  +-- SinkComponent            apply() delegates to consume(), returns {}
  |                            is_barrier = True  (always)
  |
  +-- PythonComponent          is_barrier = True  (always)
  |
  +-- UtilityComponent         override apply() directly
                               is_barrier = True  (always)
```

### Instantiation

The engine passes three arguments to the constructor:

| Argument       | Type              | Source                        |
|----------------|-------------------|-------------------------------|
| `component_id` | `str`             | `comp_config.id`              |
| `config`       | `Dict[str, Any]`  | `comp_config.config`          |
| `context`      | `Dict[str, Any]`  | `context.context_vars`        |

### Validation

`validate()` returns a list of error strings. Empty list means valid. The
base class returns `[]` by default; subclasses override for custom checks
(e.g., verifying required config keys, checking file paths).

### Execution Methods

| Base Class           | Method to Override   | Signature                                           |
|----------------------|----------------------|-----------------------------------------------------|
| `SourceComponent`    | `produce()`          | `() -> Dict[str, pl.LazyFrame]`                     |
| `TransformComponent` | `apply()`            | `(Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]` |
| `SinkComponent`      | `consume()`          | `(Dict[str, pl.LazyFrame]) -> None`                 |
| `PythonComponent`    | `apply()`            | `(Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]` |
| `UtilityComponent`   | `apply()`            | `(Dict[str, Any]) -> Dict[str, Any]`                |

All methods use the same port-name convention: the dict keys are output/input
port names (typically `"main"`).

---

## 7. Expression Compilation Pipeline

Source: `src/v2/expressions/`

The expression system converts human-readable strings into Polars expressions
(`pl.Expr`). The pipeline has four stages:

```
  "UPPER(name) + ' - ' + CONCAT(city, ', ', state)"
       |
       v
  +------------+
  | Tokenizer  |   String -> List[Token]
  +------------+
       |
       v
  +------------+
  | Parser     |   List[Token] -> AST (tree of dataclass nodes)
  +------------+
       |
       v
  +------------+
  | Compiler   |   AST -> pl.Expr
  +------------+
       |
       v
  pl.col("name").str.to_uppercase() + pl.lit(" - ") + ...
```

### Stage 1: Tokenizer

`src/v2/expressions/tokenizer.py`

The tokenizer scans the expression string character by character and produces a
list of `Token(type, value, position)` objects. It handles:

- **Literals**: numbers (`123`, `45.67`), strings (`"hello"`, `'world'`),
  booleans (`true`, `false`), null.
- **Column references**: `row.column_name` or `input.column_name` produce
  `COLUMN_REF` tokens. Bare identifiers like `column_name` produce `IDENTIFIER`.
- **Context references**: `context.var_name` produces `CONTEXT_REF`.
- **Routine calls**: PascalCase identifiers followed by `.function(` produce
  `ROUTINE_CALL` tokens (e.g., `DemoRoutine.greet`).
- **Function names**: Known function names (e.g., `UPPER`, `CONCAT`) followed
  by `(` produce `FUNCTION` tokens. The tokenizer maintains a hard-coded set
  of known function names.
- **Operators**: arithmetic (`+`, `-`, `*`, `/`, `%`), comparison (`==`, `!=`,
  `<`, `<=`, `>`, `>=`), logical (`&&`/`AND`, `||`/`OR`, `!`/`NOT`).
- **Punctuation**: `(`, `)`, `,`, `.`, `?`, `:`.

### Stage 2: Parser

`src/v2/expressions/parser.py`

A recursive descent parser that converts the token list into an AST. The AST
uses these node types:

| Node Type      | Represents                            | Example                     |
|----------------|---------------------------------------|-----------------------------|
| `Literal`      | Constant value                        | `42`, `"hello"`, `null`     |
| `ColumnRef`    | Column reference                      | `row.name`, `amount`        |
| `ContextRef`   | Context variable                      | `context.tax_rate`          |
| `FunctionCall` | Built-in function                     | `UPPER(name)`               |
| `RoutineCall`  | User routine function                 | `MyRoutine.calc(x)`         |
| `BinaryOp`     | Binary operation                      | `a + b`, `x == y`           |
| `UnaryOp`      | Unary operation                       | `!flag`, `-amount`          |
| `Conditional`  | Ternary conditional                   | `x > 0 ? x : 0`            |

Operator precedence (lowest to highest):

```
1. Ternary     ( ? : )
2. OR          ( || )
3. AND         ( && )
4. Equality    ( ==, != )
5. Comparison  ( <, <=, >, >= )
6. Additive    ( +, - )
7. Multiplicative  ( *, /, % )
8. Unary       ( !, - )
9. Primary     ( literals, identifiers, function calls, parenthesized exprs )
```

### Stage 3: Compiler

`src/v2/expressions/compiler.py`

The `ExpressionCompiler` walks the AST and produces `pl.Expr` values. Each
node type has a dedicated compile method:

| AST Node       | Compiled To                                               |
|----------------|-----------------------------------------------------------|
| `Literal`      | `pl.lit(value)`                                           |
| `ColumnRef`    | `pl.col(column_name)`                                     |
| `ContextRef`   | `pl.lit(context[variable])` (resolved at compile time)    |
| `FunctionCall` | Looked up in a function registry, e.g., `args[0].str.to_uppercase()` |
| `RoutineCall`  | Dispatched via `RoutineRegistry` (see below)              |
| `BinaryOp`     | Polars operator overloads: `left + right`, `left == right`, etc. |
| `UnaryOp`      | `~operand` (NOT), `-operand` (negation)                   |
| `Conditional`  | `pl.when(cond).then(then_expr).otherwise(else_expr)`      |

### Routine Call Compilation

Routine calls use a two-tier dispatch:

- **Tier 1 (Vectorized)**: If the routine function has `_vectorized = True`,
  the compiler uses `map_batches()`. The function receives `pl.Series` args
  and returns `pl.Series`. This runs at near-native speed.
- **Tier 2 (Scalar fallback)**: Otherwise, `map_elements()` is used for
  row-by-row execution. Slower but works for any Python function.

For multi-argument routines, arguments are packed into a Polars struct and
unpacked inside the wrapper function.

### Safe Mode

When `safe=True`, type cast functions (e.g., `to_integer`, `to_float`) use
`strict=False`, so invalid values produce `null` instead of raising errors.
This is used by the reject-row error handling flow.

### Built-in Functions

The compiler has a registry of ~50 built-in functions organized by category:

- **String**: `UPPER`, `LOWER`, `TRIM`, `CONCAT`, `SUBSTRING`, `REPLACE`, `LENGTH`, `LPAD`, `RPAD`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX_MATCH`, `REGEX_EXTRACT`, `SPLIT`
- **Numeric**: `ABS`, `ROUND`, `FLOOR`, `CEIL`, `SQRT`, `POW`, `MOD`, `LOG`, `EXP`, `SIGN`
- **Null handling**: `COALESCE`, `IFNULL`/`NVL`, `ISNULL`, `ISNOTNULL`, `NULLIF`
- **Type conversion**: `TO_STRING`, `TO_INTEGER`, `TO_FLOAT`, `TO_BOOLEAN`, `TO_DECIMAL`
- **Date/time**: `YEAR`, `MONTH`, `DAY`, `HOUR`, `MINUTE`, `SECOND`, `TO_DATE`, `PARSE_DATE`, `FORMAT_DATE`, `DATE_ADD`, `DATE_DIFF`, `NOW`
- **Aggregation**: `SUM`, `COUNT`, `AVG`, `MIN`, `MAX`, `FIRST`, `LAST`
- **Conditional**: `IF`

---

## 8. Flow Routing

Source: `src/v2/config/job_config.py` (FlowConnection model), `src/v2/engine.py` (_execute_component, _get_flow)

### FlowConnection Model

Each flow in the job config specifies a directed connection between two
components, with optional port names:

```python
# src/v2/config/job_config.py:53-58
class FlowConnection(BaseModel):
    source: str   # Source component ID
    output: str = "main"  # Output port name from source
    target: str   # Target component ID
    input: str = "main"   # Input port name on target
```

Both `output` and `input` default to `"main"`.

### Port Name Semantics

Port names map to dict keys in the `apply()` inputs/outputs:

```
Component A produces: {"main": LazyFrame, "reject": LazyFrame}
Component B expects:  {"main": LazyFrame}
Component C expects:  {"lookup": LazyFrame}

Flows:
  {source: "A", output: "main",   target: "B", input: "main"}
  {source: "A", output: "reject", target: "C", input: "lookup"}
```

### Input Gathering

When the engine executes a component, it gathers inputs from all upstream
components by consulting the flow definitions:

```python
# src/v2/engine.py:133-141
inputs = {}
for upstream_id in dag_node.upstream:
    flow = self._get_flow(upstream_id, component_id)
    source_output = flow.output if flow else "main"
    target_input = flow.input if flow else "main"
    output_data = context.get_output(upstream_id, source_output)
    if output_data is not None:
        inputs[target_input] = output_data
```

This allows components to receive data on named input ports from specific
output ports of upstream components.

### Multi-Input Example

```json
{
    "flows": [
        {"source": "customers",  "target": "join", "input": "main"},
        {"source": "orders",     "target": "join", "input": "lookup"}
    ]
}
```

The join component's `apply()` receives:

```python
inputs = {
    "main": <LazyFrame from customers>,
    "lookup": <LazyFrame from orders>
}
```

### Multi-Output Example

```json
{
    "flows": [
        {"source": "router", "output": "valid",   "target": "output_good"},
        {"source": "router", "output": "invalid", "target": "output_bad"}
    ]
}
```

The router's `apply()` returns:

```python
{"valid": <LazyFrame>, "invalid": <LazyFrame>}
```

Because `len(result) > 1`, this triggers a barrier (see
[Barrier System](#3-barrier-system)).

---

## 9. Context Variables

Context variables are job-level parameters available to all components.

### Definition in Config

```json
{
    "context": {
        "input_dir": {"value": "/data/input", "type": "str"},
        "tax_rate": {"value": 0.08, "type": "float"},
        "debug": {"value": true, "type": "bool"}
    }
}
```

Simple values are also accepted; the type is auto-inferred:

```json
{
    "context": {
        "input_dir": "/data/input",
        "tax_rate": 0.08
    }
}
```

The `JobConfig.normalize_context()` validator wraps simple values into
`ContextVariable` objects with auto-detected types.

### Supported Types

Defined in `ContextVariableType` enum (`src/v2/config/job_config.py:11-17`):

| Type       | Python Cast |
|------------|-------------|
| `str`      | `str()`     |
| `int`      | `int()`     |
| `float`    | `float()`   |
| `bool`     | `bool()`    |
| `date`     | (passthrough) |
| `datetime` | (passthrough) |

### How Context Flows to Components

```
JobConfig.get_context_values()
    -> Dict[str, Any]  (typed values)
        -> ExecutionContext(context_vars=...)
            -> Component.__init__(context=context.context_vars)
```

At construction time, each component receives the full context dict as
`self.context`.

### Resolution Mechanisms

There are two independent resolution paths:

**1. In component configs (string interpolation)**

Components call `self.resolve_context(value)` to replace `${context.varname}`
placeholders in string config values:

```python
# src/v2/components/base.py:58-73
def resolve_context(self, value):
    if not isinstance(value, str) or "${context." not in value:
        return value
    return re.sub(r'\$\{context\.(\w+)\}', _replace, value)
```

Example: A file path `"${context.input_dir}/data.csv"` resolves to
`"/data/input/data.csv"`.

**2. In expressions (compile-time literal substitution)**

The expression compiler resolves `context.var` references by looking up the
value and emitting `pl.lit(value)`:

```python
# src/v2/expressions/compiler.py:104-108
def _compile_context_ref(self, node: ContextRef) -> pl.Expr:
    if node.variable not in self.context:
        raise CompileError(f"Unknown context variable: {node.variable}")
    return pl.lit(self.context[node.variable])
```

Example: Expression `amount * context.tax_rate` compiles to
`pl.col("amount") * pl.lit(0.08)`.

**3. In ExecutionContext (runtime resolution)**

`ExecutionContext.resolve(value)` provides the same `${context.var}` string
interpolation for use outside of components:

```python
# src/v2/execution/context.py:59-70
def resolve(self, value):
    if not isinstance(value, str) or "${context." not in value:
        return value
    return re.sub(r'\$\{context\.(\w+)\}', _replace, value)
```

### Iteration Context

The iterate component (`flow_to_iterate`, `file_list`) injects additional
context variables per iteration by mutating `context.context_vars` directly:

```python
# src/v2/engine.py:214-215
for key, value in iter_ctx.items():
    context.context_vars[key] = value
```

This means downstream components in the iterate sub-pipeline see the
iteration-specific values through the normal context resolution mechanisms.

---

## Appendix: Key Source File Index

| File | Purpose |
|------|---------|
| `src/v2/engine.py` | Engine orchestrator (`PyETLEngine`) |
| `src/v2/execution/dag.py` | DAG builder and topological sort |
| `src/v2/execution/context.py` | Execution context with ref counting |
| `src/v2/components/base.py` | Component ABC hierarchy |
| `src/v2/components/registry.py` | Component auto-registration |
| `src/v2/config/job_config.py` | Pydantic config models |
| `src/v2/expressions/tokenizer.py` | Expression tokenizer |
| `src/v2/expressions/parser.py` | Recursive descent parser, AST nodes |
| `src/v2/expressions/compiler.py` | AST to `pl.Expr` compiler |
| `src/v2/routines/` | Python routine auto-discovery system |
