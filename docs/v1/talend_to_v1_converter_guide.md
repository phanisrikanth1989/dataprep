# Talend-to-V1 Converter — Usage Guide

## Overview

The `talend_to_v1` converter transforms Talend `.item` XML files into V1 engine JSON configurations. It replaces the old `complex_converter` with a clean, registry-based architecture.

```
Talend .item XML  ──>  talend_to_v1 converter  ──>  V1 engine JSON config
```

---

## Quick Start

### Python API

```python
from src.converters.talend_to_v1 import convert_job

# Convert and get the config dict
config = convert_job("path/to/job.item")

# Convert and write JSON to file
config = convert_job("path/to/job.item", output_path="output/job.json")
```

### Class-based API

```python
from src.converters.talend_to_v1 import TalendToV1Converter

converter = TalendToV1Converter()
config = converter.convert_file("path/to/job.item")

# Inspect the result
print(f"Job: {config['job_name']}")
print(f"Components: {len(config['components'])}")
print(f"Flows: {len(config['flows'])}")
print(f"Triggers: {len(config['triggers'])}")
print(f"Java required: {config['java_config']['enabled']}")
```

### Command Line

```bash
cd src/converters/talend_to_v1
python converter.py path/to/job.item output.json
```

---

## Output Format

The converter produces a JSON dict with these top-level keys:

```json
{
  "job_name": "MyTalendJob",
  "job_type": "Standard",
  "default_context": "Default",
  "context": {
    "Default": {
      "input_dir": {"value": "/data/input", "type": "str"},
      "db_host": {"value": "localhost", "type": "str"}
    }
  },
  "components": [
    {
      "id": "tFileInputDelimited_1",
      "type": "FileInputDelimited",
      "original_type": "tFileInputDelimited",
      "position": {"x": 128, "y": 192},
      "config": {
        "filepath": "/data/orders.csv",
        "delimiter": ",",
        "header_rows": 1,
        "encoding": "UTF-8",
        "die_on_error": true
      },
      "schema": {
        "input": [],
        "output": [
          {"name": "id", "type": "int", "nullable": false, "key": true},
          {"name": "amount", "type": "float", "nullable": true}
        ]
      },
      "inputs": [],
      "outputs": ["row1"],
      "subjob_id": "subjob_1",
      "is_subjob_start": true
    }
  ],
  "flows": [
    {"name": "row1", "from": "tFileInputDelimited_1", "to": "tMap_1", "type": "flow"}
  ],
  "triggers": [
    {"type": "OnSubjobOk", "from": "tPrejob_1", "to": "tFileInputDelimited_1"}
  ],
  "subjobs": {
    "subjob_1": ["tFileInputDelimited_1", "tMap_1", "tFileOutputDelimited_1"]
  },
  "java_config": {
    "enabled": false,
    "routines": ["routines.system.StringHandling"],
    "libraries": []
  },
  "_validation": {
    "valid": true,
    "summary": "Validation passed with no issues",
    "issues": []
  }
}
```

---

## Validation

Every conversion automatically runs a 4-layer validator:

| Layer | What it checks |
|-------|---------------|
| Reference integrity | Flow/trigger sources and targets point to existing components |
| Component-specific | tMap join keys non-empty, lookups have matching flows |
| Expression quality | Detects leftover Java method calls in expressions |
| Conversion quality | Flags `_unsupported` components, missing schemas |

Check the validation result:

```python
config = convert_job("job.item")

validation = config["_validation"]
if not validation["valid"]:
    print(f"Validation failed: {validation['summary']}")
    for issue in validation["issues"]:
        print(f"  [{issue['severity']}] {issue['component_id']}: {issue['message']}")
```

---

## Supported Components

The converter supports **85+ Talend component types** across 7 categories:

### File I/O (25 components)

| Talend Type | V1 Engine Type |
|---|---|
| tFileInputDelimited | FileInputDelimited |
| tFileOutputDelimited | FileOutputDelimited |
| tFileInputExcel | FileInputExcel |
| tFileOutputExcel | FileOutputExcel |
| tFileInputXML | FileInputXML |
| tFileInputMSXML | FileInputMSXMLComponent |
| tAdvancedFileOutputXML | AdvancedFileOutputXMLComponent |
| tFileInputJSON | FileInputJSON |
| tFileInputPositional | FileInputPositional |
| tFileOutputPositional | FileOutputPositional |
| tFileInputFullRow | FileInputFullRowComponent |
| tFileInputRaw | TFileInputRaw |
| tFileCopy | FileCopy |
| tFileDelete | FileDelete |
| tFileTouch | FileTouch |
| tFileExist | FileExistComponent |
| tFileProperties | FileProperties |
| tFileRowCount | FileRowCount |
| tFileArchive | FileArchiveComponent |
| tFileUnarchive | FileUnarchiveComponent |
| tFileList | FileList |
| tFileOutputEBCDIC | FileOutputEBCDIC |
| tFileInputProperties | FileInputProperties |
| tFixedFlowInput | FixedFlowInputComponent |
| tSetGlobalVar | SetGlobalVar |

### Transform (35 components)

| Talend Type | V1 Engine Type |
|---|---|
| tMap | Map |
| tXMLMap | XMLMap |
| tFilterRow / tFilterRows | FilterRows |
| tFilterColumns | FilterColumns |
| tSortRow | SortRow |
| tAggregateSortedRow | TAggregateSortedRow |
| tUnite | Unite |
| tJoin | Join |
| tNormalize | Normalize |
| tDenormalize | Denormalize |
| tUnpivotRow | UnpivotRow |
| tReplicate | Replicate |
| tReplace | Replace |
| tSplitRow | SplitRow |
| tSampleRow | SampleRow |
| tConvertType | ConvertType |
| tMemorizeRows | MemorizeRows |
| tSchemaComplianceCheck | SchemaComplianceCheck |
| tPivotToColumnsDelimited | PivotToColumnsDelimited |
| tRowGenerator | RowGenerator |
| tHashOutput | HashOutput |
| tChangeFileEncoding | ChangeFileEncoding |
| tParseRecordSet | ParseRecordSet |
| tExtractDelimitedFields | ExtractDelimitedFields |
| tExtractRegexFields | ExtractRegexFields |
| tExtractJSONFields | ExtractJSONFields |
| tExtractPositionalFields | ExtractPositionalFields |
| tExtractXMLField | ExtractXMLField |
| tLogRow | LogRow |
| tSwiftDataTransformer | SwiftTransformer |
| tJava | JavaComponent |
| tJavaRow | JavaRowComponent |
| tPython | PythonComponent |
| tPythonRow | PythonRowComponent |
| tPythonDataFrame | PythonDataFrameComponent |

### Aggregate (2 components)

| Talend Type | V1 Engine Type |
|---|---|
| tAggregateRow | AggregateRow |
| tUniqueRow / tUniqRow / tUnqRow | UniqueRow |

### Database (11 components)

| Talend Type | V1 Engine Type |
|---|---|
| tOracleConnection / tDBConnection | OracleConnection |
| tOracleInput | OracleInput |
| tOracleOutput | OracleOutput |
| tOracleRow | OracleRow |
| tOracleSP | OracleSP |
| tOracleBulkExec | OracleBulkExec |
| tOracleCommit | OracleCommit |
| tOracleClose | OracleClose |
| tOracleRollback | OracleRollback |
| tMSSqlConnection | MSSqlConnection |
| tMSSqlInput | MSSqlInput |

### Control (9 components)

| Talend Type | V1 Engine Type |
|---|---|
| tDie | Die |
| tWarn | Warn |
| tSleep | SleepComponent |
| tSendMail | SendMailComponent |
| tPrejob | PrejobComponent |
| tPostjob | PostjobComponent |
| tRunJob | RunJobComponent |
| tParallelize | Parallelize |
| tLoop | Loop |

### Context (1 component)

| Talend Type | V1 Engine Type |
|---|---|
| tContextLoad | ContextLoad |

### Iterate (2 components)

| Talend Type | V1 Engine Type |
|---|---|
| tFlowToIterate | FlowToIterate |
| tForeach | Foreach |

---

## Handling Unsupported Components

If a Talend component type is not registered, the converter creates a placeholder:

```json
{
  "id": "tUnknown_1",
  "type": "tUnknown",
  "_unsupported": true,
  "original_type": "tUnknown"
}
```

A warning is added to the output. To check for unsupported components:

```python
config = convert_job("job.item")
unsupported = [c for c in config["components"] if c.get("_unsupported")]
if unsupported:
    print(f"Warning: {len(unsupported)} unsupported components:")
    for c in unsupported:
        print(f"  - {c['id']} ({c['original_type']})")
```

---

## Adding a New Component Converter

To support a new Talend component type:

### 1. Create the converter file

```python
# src/converters/talend_to_v1/components/<category>/my_component.py

import logging
from ..base import ComponentConverter, ComponentResult, TalendNode, TalendConnection
from ..registry import REGISTRY
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@REGISTRY.register("tMyComponent")
class MyComponentConverter(ComponentConverter):
    def convert(self, node, connections, context):
        warnings = []

        config = {
            "param1": self._get_str(node, "PARAM1"),
            "param2": self._get_bool(node, "PARAM2"),
            "param3": self._get_int(node, "PARAM3", 0),
        }

        component = self._build_component_dict(
            node=node,
            type_name="MyComponent",  # must match v1 engine registry
            config=config,
            schema={"input": self._parse_schema(node), "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
```

### 2. Register the import

Add the import to the category's `__init__.py`:

```python
# src/converters/talend_to_v1/components/<category>/__init__.py
from . import my_component  # noqa: F401
```

### 3. Write tests

```python
# tests/converters/talend_to_v1/components/test_my_component.py

from src.converters.talend_to_v1.components.base import TalendNode
from src.converters.talend_to_v1.components.<category>.my_component import MyComponentConverter


def _make_node(params=None):
    return TalendNode(
        component_id="tMyComponent_1",
        component_type="tMyComponent",
        params=params or {},
        schema={},
        position={"x": 0, "y": 0},
    )


def test_basic_conversion():
    node = _make_node(params={"PARAM1": '"value1"', "PARAM2": "true", "PARAM3": "42"})
    result = MyComponentConverter().convert(node, [], {})
    assert result.component["type"] == "MyComponent"
    assert result.component["config"]["param1"] == "value1"
    assert result.component["config"]["param2"] is True
    assert result.component["config"]["param3"] == 42
```

### Available base class helpers

| Helper | Purpose |
|--------|---------|
| `_get_str(node, name, default="")` | Extract string param, strips quotes |
| `_get_bool(node, name, default=False)` | Extract boolean (handles "true"/"false"/"1"/"0") |
| `_get_int(node, name, default=0)` | Extract integer safely |
| `_get_param(node, name, default=None)` | Extract raw param (for lists, dicts, code) |
| `_parse_schema(node, connector="FLOW")` | Parse schema columns with type conversion |
| `_convert_date_pattern(pattern)` | Java SimpleDateFormat to Python strftime |
| `_build_component_dict(node, type_name, config, schema)` | Assemble standard component dict |
| `_incoming(node, connections)` | Get connections targeting this node |
| `_outgoing(node, connections)` | Get connections from this node |

### Schema patterns

```python
# Source component (produces data): input empty, output from FLOW
schema={"input": [], "output": self._parse_schema(node)}

# Sink/output component (consumes data): input from FLOW, output empty
schema={"input": self._parse_schema(node), "output": []}

# Transform component (passes through): both from FLOW
schema_cols = self._parse_schema(node)
schema={"input": schema_cols, "output": schema_cols}

# Utility component (no data flow): both empty
schema={"input": [], "output": []}
```

### TABLE parameter parsing

XmlParser stores TABLE params as flat lists of `{elementRef, value}` dicts:

```python
# Example: parse a TABLE with pairs of KEY/VALUE entries
raw = self._get_param(node, "MY_TABLE", [])
entries = []
current_key = None
for entry in raw:
    if not isinstance(entry, dict):
        continue
    ref = entry.get("elementRef", "")
    val = entry.get("value", "").strip('"')
    if ref == "KEY":
        current_key = val
    elif ref == "VALUE" and current_key:
        entries.append({"key": current_key, "value": val})
        current_key = None
```

---

## Architecture

```
src/converters/talend_to_v1/
├── __init__.py              # Public API: TalendToV1Converter, convert_job
├── converter.py             # 12-step pipeline orchestrator
├── xml_parser.py            # Talend XML → TalendNode data classes
├── expression_converter.py  # Java expression detection/marking
├── type_mapping.py          # Talend type → Python type (single source of truth)
├── trigger_mapper.py        # Trigger parsing with PascalCase v1 naming
├── validator.py             # 4-layer post-conversion validation
└── components/
    ├── base.py              # ComponentConverter ABC + shared helpers
    ├── registry.py          # Decorator-based ConverterRegistry
    ├── aggregate/           # tAggregateRow, tUniqueRow
    ├── context/             # tContextLoad
    ├── control/             # tDie, tWarn, tSleep, tSendMail, etc.
    ├── file/                # 25 file I/O components
    ├── transform/           # 35 transform components (including tMap, tXMLMap)
    ├── database/            # 11 Oracle + MSSQL components
    └── iterate/             # tFlowToIterate, tForeach
```

### Conversion Pipeline

```
1. XmlParser.parse(filepath)     → TalendJob (nodes, connections, context)
2. Convert context variables     → type mapping applied
3. For each node:
   ├─ REGISTRY.get(type)         → find converter class
   ├─ converter.convert(node)    → ComponentResult (or _unsupported placeholder)
   └─ collect warnings
4. Parse flows from connections  → centrally, not per-component
5. Update component inputs/outputs from flows
6. Parse triggers               → PascalCase naming (OnSubjobOk, etc.)
7. Detect subjobs               → DFS on flow connectivity
8. Detect Java requirement       → scan for Java component types + {{java}} markers
9. Validate                     → 4-layer validation
10. Return assembled config dict
```

---

## Differences from `complex_converter`

| Aspect | Old (`complex_converter`) | New (`talend_to_v1`) |
|--------|--------------------------|---------------------|
| Dispatch | 150-line `elif` chain | Registry-based decorator lookup |
| Component files | 1 file (2,985 lines) | 85 files (one per component) |
| Null safety | `node.find().get()` crashes | Base class `_get_*` helpers |
| Tests | None | 1,388 tests |
| Validation | None | 4-layer post-conversion validator |
| Type mapping | Duplicated in 2 places | Single `type_mapping.py` |
| Debug output | 30+ `print()` statements | `logging.getLogger(__name__)` |
| Error handling | Crashes on unknown components | `_unsupported` placeholder + warning |

---

## Running Tests

```bash
# All converter tests (1,388 tests)
pytest tests/converters/talend_to_v1/ -v

# Just integration tests
pytest tests/converters/talend_to_v1/test_integration.py -v

# Just a specific component
pytest tests/converters/talend_to_v1/components/test_file_input_delimited.py -v
```
