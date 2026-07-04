# DataPrep -- Quickstart

*Last updated: 2026-05-11*

Convert a Talend `.item` file to V1 JSON, execute the JSON, and observe the
output. Five minutes if your dev environment is already set up.

If you do not have a working environment yet, run through
`docs/guides/DEV_SETUP.md` first.

---

## The two-step flow

```
┌──────────────┐    converter    ┌──────────────┐     engine    ┌──────────────┐
│  job.item    │  ──────────▶    │  job.json    │  ──────────▶  │   data out   │
│  (Talend)    │                 │  (V1)        │               │  (CSV, etc.) │
└──────────────┘                 └──────────────┘               └──────────────┘
```

The converter (`src/converters/talend_to_v1/`) parses Talend `.item` XML
and emits the V1 JSON format. The engine (`src/v1/engine/`) executes that
JSON. The two layers are independent: you can run the engine against any
JSON that matches the V1 schema, whether the converter produced it or you
hand-wrote it.

---

## Step 1 -- Convert a `.item` file to JSON

### CLI

```bash
python -m src.converters.talend_to_v1.converter \
    tests/talend_xml_samples/Job_tFileOutputDelimited_0.1.item \
    /tmp/job_tFileOutputDelimited.json
```

The second argument (output path) is optional. If omitted, JSON is written
next to the input with a `.json` suffix.

Expected stdout:

```
INFO Parsed job 'Job_tFileOutputDelimited' with 2 nodes
INFO Converted 2 components, 0 warnings, 0 review items
INFO Wrote /tmp/job_tFileOutputDelimited.json
```

### Python API

```python
from src.converters.talend_to_v1.converter import convert_job

# Convert and write JSON to file
result = convert_job(
    input_path="tests/talend_xml_samples/Job_tFileOutputDelimited_0.1.item",
    output_path="/tmp/job_tFileOutputDelimited.json",
)

print(f"Components: {len(result['components'])}")
print(f"Warnings:   {len(result.get('warnings', []))}")
print(f"Review:     {len(result.get('needs_review', []))}")
```

`convert_job` returns the same dict that was serialized to JSON.

### Inspecting conversion warnings

If a component lacks a converter or has ambiguous config, the converter
emits an `_unsupported` placeholder plus an entry in `warnings` or
`needs_review`. The JSON still produces -- inspect the warnings before
executing.

```python
result = convert_job("tests/talend_xml_samples/<file>.item")
for w in result.get("warnings", []):
    print("WARNING:", w)
for r in result.get("needs_review", []):
    print("REVIEW:", r)
```

The converter's full output schema is documented in
`docs/guides/AUTHORING_JOB_JSON.md`.

---

## Step 2 -- Execute the JSON

### CLI

```bash
python src/v1/engine/engine.py /tmp/job_tFileOutputDelimited.json
```

Override context variables on the command line (use `--context_param`
once per variable):

```bash
python src/v1/engine/engine.py /tmp/job.json \
    --context_param DB_HOST=prod-db \
    --context_param input_dir=/data/today
```

Expected: the engine logs each component's lifecycle (`Starting`,
`Completed`, `NB_LINE_OK=...`) and prints a JSON statistics dump at the
end.

### Python API -- one-shot helper

```python
from src.v1.engine.engine import run_job

stats = run_job(
    "/tmp/job_tFileOutputDelimited.json",
    {"input_dir": "/data/today"},   # context overrides (optional)
)

print(stats)
```

### Python API -- engine instance

For programmatic use where you want to inspect or modify state between
load and execute:

```python
from src.v1.engine import ETLEngine

with ETLEngine("/tmp/job.json") as engine:
    engine.set_context_variable("input_dir", "/data/today")
    stats = engine.execute()

print(stats["components"]["tFileInputDelimited_1"]["status"])  # "success"
```

The context-manager form ensures the Java bridge subprocess is shut down
cleanly if the job raises.

---

## A complete example -- read CSV, filter, write CSV

If you do not have a `.item` file handy, you can skip the converter and
execute a hand-written JSON directly. Drop this into
`/tmp/hello_dataprep.json`:

```json
{
  "job_name": "hello_dataprep",
  "job_type": "Standard",
  "default_context": "Default",
  "context": {
    "Default": {
      "input_path":  {"value": "/tmp/input.csv",  "type": "str"},
      "output_path": {"value": "/tmp/output.csv", "type": "str"}
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
        "die_on_error": false
      },
      "schema": {
        "input": [],
        "output": [
          {"name": "id",     "type": "int",   "nullable": false},
          {"name": "name",   "type": "str",   "nullable": false},
          {"name": "salary", "type": "float", "nullable": true}
        ]
      },
      "inputs": [],
      "outputs": ["row1"]
    },
    {
      "id": "tFilterRow_1",
      "type": "FilterRow",
      "config": {
        "logical_op": "AND",
        "conditions": [
          {"column": "salary", "function": "GREATER", "value": 50000}
        ]
      },
      "schema": {
        "input":  [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}, {"name": "salary", "type": "float"}],
        "output": [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}, {"name": "salary", "type": "float"}]
      },
      "inputs":  ["row1"],
      "outputs": ["row2"]
    },
    {
      "id": "tFileOutputDelimited_1",
      "type": "FileOutputDelimited",
      "config": {
        "filepath": "${context.output_path}",
        "field_separator": ",",
        "include_header": true,
        "encoding": "UTF-8"
      },
      "schema": {
        "input":  [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}, {"name": "salary", "type": "float"}],
        "output": []
      },
      "inputs":  ["row2"],
      "outputs": []
    }
  ],
  "flows": [
    {"name": "row1", "from": "tFileInputDelimited_1", "to": "tFilterRow_1",          "type": "flow"},
    {"name": "row2", "from": "tFilterRow_1",          "to": "tFileOutputDelimited_1", "type": "flow"}
  ],
  "triggers": [],
  "subjobs": {
    "subjob_1": ["tFileInputDelimited_1", "tFilterRow_1", "tFileOutputDelimited_1"]
  },
  "java_config": {"enabled": false, "routines": [], "libraries": []}
}
```

Make a tiny input CSV:

```bash
cat > /tmp/input.csv <<'CSV'
id,name,salary
1,Alice,75000
2,Bob,40000
3,Carol,90000
CSV
```

Run it:

```bash
python src/v1/engine/engine.py /tmp/hello_dataprep.json
cat /tmp/output.csv
```

Expected `/tmp/output.csv`:

```
id,name,salary
1,Alice,75000.0
3,Carol,90000.0
```

For the full JSON schema reference (every top-level key, every config
key) see `docs/guides/AUTHORING_JOB_JSON.md`.

---

## What if it fails?

If the engine raises, do NOT immediately edit component code. Hand the
error to `docs/ai-prompts/DEBUG_JOB_FAILURE.md` first -- that prompt
forces the assistant to reproduce, classify, and diagnose before
proposing any fix. Component edits without a clear reproduction step are
how Talend parity gets quietly broken.

---

## See Also

- `docs/guides/DEV_SETUP.md` -- environment setup if you have not run the smoke tests yet
- `docs/guides/AUTHORING_JOB_JSON.md` -- the full V1 JSON schema, written for hand-authoring
- `docs/COMPONENT_REFERENCE.md` -- inventory of supported components and their config keys
- `docs/ai-prompts/DEBUG_JOB_FAILURE.md` -- AI prompt for safely diagnosing a job failure
- `docs/ARCHITECTURE.md` -- conversion pipeline (12 steps) and engine execution pipeline
- `CLAUDE.md` -- entry points and CLI reference
