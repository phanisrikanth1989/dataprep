# Hand-Authoring a DataPrep Job JSON

*Last updated: 2026-05-11*

DataPrep's engine executes any JSON that matches the V1 schema -- it does
not require a Talend `.item` source. This guide is for the case where you
want to model an ETL pipeline that has no Talend equivalent: a new
internal feed, a one-off migration, a test fixture, or just a pipeline
written from scratch by an engineer who never owned a Talend license.

**Read this when:** you are sitting in front of a text editor about to
write `pipeline.json` for an ETL flow that does not exist in Talend.

**Do not read this when:** you have a Talend `.item` file -- run the
converter (see `docs/guides/QUICKSTART.md`) and inspect the output. The
converter handles ~80 components correctly; hand-writing for those is
wasted effort.

---

## How the engine reads JSON

The engine loads the JSON into a `dict`, builds the component dependency
graph from `flows[]`, evaluates `subjobs` activation through `triggers[]`,
then walks the topological order and instantiates each component from
`components[].type` via the decorator-driven registry in
`src/v1/engine/component_registry.py`.

The engine does NOT care whether the `type` value is the PascalCase form
(`FileInputDelimited`) or the Talend alias (`tFileInputDelimited`) -- both
resolve through the same registry. Use whichever reads better.

---

## Top-level structure

```json
{
  "job_name": "my_pipeline",
  "job_type": "Standard",
  "default_context": "Default",
  "context":   { "Default": { /* context vars */ } },
  "components": [ /* one entry per component */ ],
  "flows":     [ /* data-flow edges between components */ ],
  "triggers":  [ /* control-flow edges (OnSubjobOk, RunIf, etc.) */ ],
  "subjobs":   { "subjob_1": ["comp_id_1", "comp_id_2"] },
  "java_config": {
    "enabled":   false,
    "routines":  [],
    "libraries": []
  }
}
```

### `job_name` (string, required)
Human-readable job identifier. Surfaces in logs and the final stats dump.
No semantic effect on execution.

### `job_type` (string, required)
Always `"Standard"` unless you have a specific reason to deviate.
Reserved for future Talend job-type parity (e.g., `"Big Data"`); the
engine only honors `"Standard"` today.

### `default_context` (string, required)
The context group used unless a context override is passed at the CLI or
via `set_context_variable()`. Almost always `"Default"`.

### `context` (object, required)
Map of context-group name -> variable bindings. Most jobs use a single
`"Default"` group:

```json
"context": {
  "Default": {
    "input_dir":  {"value": "/data/in",  "type": "str"},
    "batch_date": {"value": "2026-05-11", "type": "date"},
    "die_hard":   {"value": false,        "type": "bool"}
  }
}
```

Each binding is `{"value": <literal>, "type": "<type_name>"}`. Supported
types: `str`, `int`, `float`, `bool`, `date`, `datetime`. Bare strings
without the wrapper are accepted (legacy form) but `{"value": ..., "type":
...}` is preferred -- the type carries through `${context.x}`
substitution.

Reference context variables from inside component config using `${context.varname}`:

```json
"config": { "filepath": "${context.input_dir}/orders.csv" }
```

The engine resolves these at component-start time. Bare `context.varname`
references (without the `${...}` wrapper) also work but are best avoided
-- they read as Python identifiers and can collide with legitimate code.

### `components` (array, required)
The heart of the JSON. See the next section.

### `flows` (array, required)
Data-flow edges between components. Each entry:

```json
{"name": "row1", "from": "tFileInputDelimited_1", "to": "tFilterRow_1", "type": "flow"}
```

| Field | What |
|-------|------|
| `name`  | The flow's name. Used by components to reference upstream data. The component on the `to` side reads from this named flow. Must be unique across the job. |
| `from`  | Source component `id`. |
| `to`    | Destination component `id`. |
| `type`  | `"flow"` for main data, `"reject"` for reject routing. Only these two values today. |

A flow's `name` also appears in the source component's `outputs` array
and the destination component's `inputs` array -- those are the
component-side declaration; `flows[]` is the job-level wiring. Both must
agree.

### `triggers` (array, required, may be empty)
Control-flow edges between subjobs. The Talend `OnSubjobOk`,
`OnComponentOk`, `OnSubjobError`, `RunIf`, `Iterate` semantics live here.
Empty `[]` means the job has only one subjob and no conditional control
flow.

```json
{
  "from": "tDie_1",
  "to":   "tWarn_1",
  "type": "OnSubjobOk"
}
```

Trigger types currently supported: `OnSubjobOk`, `OnSubjobError`,
`OnComponentOk`, `OnComponentError`, `RunIf`, `Iterate`. `RunIf` carries
an additional `condition` field (a Python-evaluable expression resolved
against `context` and `globalMap`).

### `subjobs` (object, required)
Map of subjob name -> list of component ids that belong to it. A job with
no explicit subjobs:

```json
"subjobs": { "subjob_1": ["tFileInputDelimited_1", "tFilterRow_1", "tFileOutputDelimited_1"] }
```

The engine activates subjobs in topological order (defined by triggers).
Components within an activated subjob are executed in flow order. A
component not assigned to any subjob is ignored at execution time.

### `java_config` (object, required, often empty-shaped)
Configures the Java bridge for jobs that use `{{java}}` markers or
`tMap` in live mode. Default for pure-Python jobs:

```json
"java_config": {"enabled": false, "routines": [], "libraries": []}
```

When `enabled: true`, the engine launches the Java bridge subprocess at
job start. `routines` and `libraries` declare extra Talend routine classes
or JARs to load on the Java side.

---

## A component entry

```json
{
  "id": "tFileInputDelimited_1",
  "type": "FileInputDelimited",
  "original_type": "tFileInputDelimited",
  "position": {"x": 128, "y": 192},
  "config": {
    "filepath": "${context.input_dir}/orders.csv",
    "field_separator": ",",
    "header_rows": 1,
    "encoding": "UTF-8",
    "die_on_error": true
  },
  "schema": {
    "input":  [],
    "output": [
      {"name": "order_id",   "type": "int",    "nullable": false, "key": true},
      {"name": "customer",   "type": "str",    "nullable": false},
      {"name": "amount",     "type": "float",  "nullable": true},
      {"name": "order_date", "type": "date",   "nullable": true}
    ]
  },
  "inputs":  [],
  "outputs": ["row1"]
}
```

### `id` (string, required)
Component instance id. Must be unique in the job. Used by `flows[]`,
`triggers[]`, `subjobs[]` to reference this component, and surfaces in
log messages as `[{id}]`.

By convention: `<talend_name>_<n>` (e.g., `tFileInputDelimited_1`,
`tFilterRow_2`). The number is per-type, starts at 1, increments for each
additional instance of the same type.

### `type` (string, required)
The component class to instantiate. Resolved via
`@REGISTRY.register("X", "Y")` decorators. Either `FileInputDelimited` or
`tFileInputDelimited` works -- both are registered aliases. See
`docs/COMPONENT_REFERENCE.md` for the full inventory of registered names.

### `original_type` (string, optional)
The Talend component name. Informational only -- the converter sets it
for traceability back to the source. Safe to omit when hand-authoring; if
you set it, mirror `type` with the `t` prefix.

### `position` (object, optional)
GUI coordinates. Ignored by the engine. Safe to omit.

### `config` (object, required)
Per-component configuration. The supported keys differ for each
component type. The authoritative list for any component is its
docstring (e.g., `src/v1/engine/components/aggregate/aggregate_row.py`
documents 8 config keys at the top). `docs/COMPONENT_REFERENCE.md` is
the cross-component index.

Universal config keys (honored by `BaseComponent` for every subclass):

| Key | Type | Default | What |
|-----|------|---------|------|
| `die_on_error`  | bool | varies per component | If true, a row that raises during processing aborts the job; if false, the row routes to the `reject` output (when the component has one) or is dropped. |
| `tstatcatcher_stats` | bool | false | Framework hook -- emits per-component stats to `globalMap`. |
| `label`         | str  | ""    | Framework hook -- not used at runtime. |

### `schema` (object, required)
The DataFrame schema this component expects and produces.

```json
"schema": {
  "input":  [ /* columns coming IN from upstream */ ],
  "output": [ /* columns going OUT to downstream */ ]
}
```

Each column entry:

```json
{"name": "order_id", "type": "int", "nullable": false, "key": true}
```

| Field | Required? | What |
|-------|-----------|------|
| `name`     | yes | Column name. Used to look up values in the DataFrame. |
| `type`     | yes | One of `str`, `int`, `long`, `float`, `double`, `decimal`, `bool`, `date`, `datetime`, `timestamp`, `bytes`. The engine maps these to pandas dtypes via `src/v1/engine/type_mapping.py`. |
| `nullable` | optional, defaults true | If false, a null value during processing raises `DataValidationError` (subject to `die_on_error`). |
| `key`      | optional, defaults false | Marks the column as a key for join / aggregate components. Informational for most components. |

Input components (file readers, generators) have an empty `input: []`.
Output components (file writers, sinks) have an empty `output: []`.

### `inputs` (array, required)
Names of `flows[]` entries this component consumes. Empty for input
components.

### `outputs` (array, required)
Names of `flows[]` entries this component produces. Empty for output
components. Components with reject routing typically have two outputs:
the main flow (e.g., `row1`) and a reject flow (e.g., `row1_reject`).

---

## Wiring example -- read CSV, transform with tMap, aggregate, write CSV

A representative mid-complexity pipeline. Reads `orders.csv`, normalizes
`amount` to USD via tMap, aggregates total revenue per customer with
tAggregateRow, writes `revenue_by_customer.csv`.

```json
{
  "job_name": "revenue_by_customer",
  "job_type": "Standard",
  "default_context": "Default",
  "context": {
    "Default": {
      "input_path":  {"value": "/data/orders.csv",                "type": "str"},
      "output_path": {"value": "/data/revenue_by_customer.csv",   "type": "str"},
      "fx_rate_eur": {"value": 1.07,                              "type": "float"}
    }
  },
  "components": [
    {
      "id": "tFileInputDelimited_1",
      "type": "FileInputDelimited",
      "config": {
        "filepath": "${context.input_path}",
        "field_separator": ",",
        "header_rows": 1,
        "encoding": "UTF-8",
        "die_on_error": true
      },
      "schema": {
        "input": [],
        "output": [
          {"name": "order_id", "type": "int",    "nullable": false},
          {"name": "customer", "type": "str",    "nullable": false},
          {"name": "amount",   "type": "float",  "nullable": false},
          {"name": "currency", "type": "str",    "nullable": false}
        ]
      },
      "inputs": [],
      "outputs": ["row1"]
    },
    {
      "id": "tMap_1",
      "type": "Map",
      "config": {
        "outputs": [
          {
            "name": "row2",
            "columns": [
              {"name": "customer",   "expression": "row1.customer"},
              {"name": "amount_usd", "expression": "row1.amount if row1.currency == 'USD' else row1.amount * ${context.fx_rate_eur}"}
            ]
          }
        ]
      },
      "schema": {
        "input":  [
          {"name": "order_id", "type": "int"},
          {"name": "customer", "type": "str"},
          {"name": "amount",   "type": "float"},
          {"name": "currency", "type": "str"}
        ],
        "output": [
          {"name": "customer",   "type": "str"},
          {"name": "amount_usd", "type": "float"}
        ]
      },
      "inputs":  ["row1"],
      "outputs": ["row2"]
    },
    {
      "id": "tAggregateRow_1",
      "type": "AggregateRow",
      "config": {
        "groupbys":   [{"output_column": "customer",  "input_column": "customer"}],
        "operations": [{"output_column": "revenue",   "function": "sum", "input_column": "amount_usd", "ignore_null": false}],
        "use_financial_precision": true
      },
      "schema": {
        "input":  [{"name": "customer", "type": "str"}, {"name": "amount_usd", "type": "float"}],
        "output": [{"name": "customer", "type": "str"}, {"name": "revenue",    "type": "float"}]
      },
      "inputs":  ["row2"],
      "outputs": ["row3"]
    },
    {
      "id": "tFileOutputDelimited_1",
      "type": "FileOutputDelimited",
      "config": {
        "filepath": "${context.output_path}",
        "field_separator": ",",
        "include_header": true,
        "encoding": "UTF-8",
        "create_directory": true
      },
      "schema": {
        "input":  [{"name": "customer", "type": "str"}, {"name": "revenue", "type": "float"}],
        "output": []
      },
      "inputs":  ["row3"],
      "outputs": []
    }
  ],
  "flows": [
    {"name": "row1", "from": "tFileInputDelimited_1", "to": "tMap_1",                "type": "flow"},
    {"name": "row2", "from": "tMap_1",                "to": "tAggregateRow_1",       "type": "flow"},
    {"name": "row3", "from": "tAggregateRow_1",       "to": "tFileOutputDelimited_1","type": "flow"}
  ],
  "triggers": [],
  "subjobs": {
    "subjob_1": ["tFileInputDelimited_1", "tMap_1", "tAggregateRow_1", "tFileOutputDelimited_1"]
  },
  "java_config": {"enabled": false, "routines": [], "libraries": []}
}
```

Things worth noticing in this example:

- **Context vars carry types** -- `fx_rate_eur` is `float`, so `${context.fx_rate_eur}` resolves to `1.07` (number), not `"1.07"` (string).
- **The tMap expression** uses Python syntax. tMap evaluates expressions natively in Python when no `{{java}}` marker is present.
- **Schema propagation is explicit** -- the output schema of tMap exactly matches the input schema of tAggregateRow. If they drift, the aggregate will fail at execution.
- **Single subjob** -- the four components form one linear pipeline; one subjob containing all four is enough, and `triggers: []` is correct.

---

## Multi-subjob example -- trigger between two pipelines

Reads a config file, then conditionally runs the main pipeline. Two
subjobs wired by `OnSubjobOk`:

```json
{
  "components": [
    {"id": "tFileInputDelimited_1", "type": "FileInputDelimited", "config": { /* read config.csv */ }, "schema": { /* ... */ }, "inputs": [], "outputs": ["cfg"]},
    {"id": "tContextLoad_1",        "type": "ContextLoad",        "config": { /* load context from cfg */ }, "schema": { /* ... */ }, "inputs": ["cfg"], "outputs": []},
    {"id": "tFileInputDelimited_2", "type": "FileInputDelimited", "config": { /* read orders.csv */ }, "schema": { /* ... */ }, "inputs": [], "outputs": ["row1"]},
    {"id": "tFileOutputDelimited_1","type": "FileOutputDelimited","config": { /* write filtered.csv */ }, "schema": { /* ... */ }, "inputs": ["row1"], "outputs": []}
  ],
  "flows": [
    {"name": "cfg",  "from": "tFileInputDelimited_1", "to": "tContextLoad_1",         "type": "flow"},
    {"name": "row1", "from": "tFileInputDelimited_2", "to": "tFileOutputDelimited_1", "type": "flow"}
  ],
  "triggers": [
    {"from": "tContextLoad_1", "to": "tFileInputDelimited_2", "type": "OnSubjobOk"}
  ],
  "subjobs": {
    "subjob_load_config": ["tFileInputDelimited_1", "tContextLoad_1"],
    "subjob_main":        ["tFileInputDelimited_2", "tFileOutputDelimited_1"]
  }
}
```

The engine executes `subjob_load_config` first. If it completes without
error, the `OnSubjobOk` trigger activates `subjob_main`. If
`tContextLoad_1` raises, `subjob_main` never runs.

---

## Reject routing

Components that support reject (most file readers, tFilterRow, tMap, etc.)
emit two flows -- the main flow and a reject flow. Declare both:

```json
"outputs": ["row1", "row1_reject"]
```

And wire both in `flows[]`:

```json
{"name": "row1",        "from": "tFileInputDelimited_1", "to": "tMap_1",                  "type": "flow"},
{"name": "row1_reject", "from": "tFileInputDelimited_1", "to": "tLogRow_reject",          "type": "reject"}
```

The `type: "reject"` distinguishes the reject edge from the main flow.
The component receiving the reject (e.g., a `tLogRow` for logging or a
`tFileOutputDelimited` writing a reject file) sees it via its `inputs`
just like any other flow.

If `die_on_error: true` and the component has no reject wired, a bad
row aborts the job (per CONTRIBUTING.md Rule 3 -- fail loudly, no
silent drops).

---

## Validation -- catch JSON errors before runtime

The converter ships with a validator (`src/converters/talend_to_v1/validator.py`)
that checks reference integrity, tMap rules, expression quality, and
conversion quality markers. You can run it standalone on hand-written
JSON:

```python
import json
from src.converters.talend_to_v1.validator import validate_config

with open("/tmp/my_pipeline.json") as f:
    config = json.load(f)

report = validate_config(config)
print(report.summary)
for issue in report.issues:
    print(f"{issue.severity.upper()}: {issue.message}")
```

The validator emits three severities -- `error`, `warning`, `info`.
Errors mean the engine will likely fail at runtime; fix them first.

---

## Common pitfalls

**Mismatched flow names between `flows[]` and `inputs`/`outputs`.**
The component declarations and the job-level wiring must agree. The
engine surfaces this at startup as "no flow named X feeding component
Y" -- but only if you go looking.

**Schema drift across a flow boundary.**
The output schema of the source component must match the input schema of
the destination. The engine does not auto-coerce types across a flow;
mismatches surface as `SchemaError` at execution time.

**Forgetting `subjobs[]`.**
A component not assigned to any subjob is silently skipped. If your job
runs but produces no output, this is the most likely cause.

**Context-var type mismatch.**
`{"value": "false", "type": "bool"}` evaluates to `True` (non-empty
string). Use `{"value": false, "type": "bool"}` -- JSON literal `false`,
not the string.

**Bare `context.x` references inside Python expressions in tMap.**
Inside a tMap expression, `context.x` works but is fragile -- it can
collide with attribute access. Prefer `${context.x}` which is resolved
before the expression evaluates.

**`die_on_error` defaults differ per component.**
Some readers default to `true` (fail fast), some to `false` (continue
with rejects). Always set it explicitly when correctness matters.

---

## See Also

- `docs/guides/QUICKSTART.md` -- five-minute walkthrough using a real `.item` and JSON
- `docs/COMPONENT_REFERENCE.md` -- registered component inventory + config keys per component
- `docs/ARCHITECTURE.md` -- the engine's execution pipeline and registry discipline
- `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` -- internal pattern reference (for understanding what your config does once it reaches the component class)
- `src/converters/talend_to_v1/validator.py` -- validation rules cited above
- `tests/fixtures/jobs/` -- 50+ hand-authored fixture JSONs across `file/`, `transform/`, `core/`, `swift/` -- excellent reference shapes
