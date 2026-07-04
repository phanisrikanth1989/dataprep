# Job Configuration Schema Reference

**Last Updated:** 2026-06-13

Complete reference for DataPrep JSON job configuration format.

---

## Table of Contents

1. [Overview](#overview)
2. [Top-Level Structure](#top-level-structure)
3. [Components](#components)
4. [Flows & Triggers](#flows--triggers)
5. [Schema Definition](#schema-definition)
6. [Configuration Options](#configuration-options)
7. [Context & Variables](#context--variables)
8. [Java Bridge Configuration](#java-bridge-configuration)
9. [Complete Examples](#complete-examples)

---

## Overview

A job configuration is a JSON file that defines:
- **Components** — processing steps (file I/O, transformations, etc.)
- **Flows** — connections between components
- **Triggers** — when flows execute (conditional execution)
- **Schema** — data structure definitions
- **Context** — variables and parameters
- **Java Configuration** — JVM settings for Java expressions

---

## Top-Level Structure

```json
{
  "name": "string",                   // Job name (required)
  "description": "string",            // Optional description
  "version": "string",                // Job version
  "java_config": {                    // Java bridge settings (optional)
    "enabled": boolean,
    "jvm_options": ["string"]
  },
  "context": {                        // Variable definitions (optional)
    "key": "value"
  },
  "components": [                     // Component array (required)
    { /* component definition */ }
  ],
  "flows": [                          // Flow connections (required)
    { /* flow definition */ }
  ],
  "triggers": [                       // Trigger conditions (optional)
    { /* trigger definition */ }
  ]
}
```

### Top-Level Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Unique job identifier |
| `description` | string | No | Human-readable description |
| `version` | string | No | Semantic version (e.g., "1.0.0") |
| `java_config` | object | No | JVM configuration |
| `context` | object | No | Global variables |
| `components` | array | Yes | Processing steps |
| `flows` | array | Yes | Component connections |
| `triggers` | array | No | Conditional execution |

---

## Components

### Component Structure

```json
{
  "id": "string",                     // Unique ID (required)
  "type": "string",                   // Component type (required)
  "config": {                         // Type-specific config (required)
    "param1": "value1",
    "param2": 100
  },
  "schema": [                         // Output schema (optional)
    {
      "name": "column_name",
      "type": "string",
      "length": 100,
      "nullable": true
    }
  ],
  "execution_mode": "string",         // BATCH, STREAMING, HYBRID
  "metadata": {                       // Optional metadata
    "description": "Component description",
    "owner": "team_name",
    "tags": ["tag1", "tag2"]
  }
}
```

### Component Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | Yes | Unique within job |
| `type` | string | Yes | Component class name (e.g., "tFileInputDelimited") |
| `config` | object | Yes | Component-specific parameters |
| `schema` | array | No | Output column definitions |
| `execution_mode` | string | No | Batch/Streaming/Hybrid |
| `metadata` | object | No | Tags, description, ownership |

### Common Component Types

**File I/O:**
- `tFileInputDelimited` — Read CSV/TSV
- `tFileOutputDelimited` — Write CSV/TSV
- `tFileInputExcel` — Read Excel
- `tFileOutputExcel` — Write Excel
- `tFileInputXML` — Read XML
- `tFileInputJSON` — Read JSON

**Transformation:**
- `tMap` — Field mapping and expressions
- `tFilter` — Conditional row filtering
- `tSort` — Sort rows
- `tUnique` — Remove duplicates
- `tJavaRow` — Row-level Java processing

**Aggregation:**
- `tAggregateRow` — Group and aggregate
- `tUnique` — Distinct values

**Control Flow:**
- `tSubjob` — Execute another subjob
- `tDie` — Terminate with error
- `tWaitForFile` — Wait for file existence

**Iteration:**
- `tFileList` — Iterate over files
- `tForeach` — Foreach loop
- `tFlowToIterate` — Iterate over flow data

**Context:**
- `tContextLoad` — Load context from file
- `tContextDump` — Export context

### Execution Modes

```json
{
  "execution_mode": "BATCH"   // Process entire DataFrame at once
}
```

```json
{
  "execution_mode": "STREAMING",      // Row-by-row processing
  "streaming_batch_size": 10000       // Batch size for efficiency
}
```

```json
{
  "execution_mode": "HYBRID"          // Batch with iterator support
}
```

---

## Flows & Triggers

### Flow Structure

```json
{
  "source": "string",                 // Source component ID (required)
  "target": "string",                 // Target component ID (required)
  "name": "string",                   // Flow name: "main" or "reject" (required)
  "condition": "string",              // Optional filter condition
  "metadata": {                       // Optional metadata
    "description": "Flow description"
  }
}
```

### Flow Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `source` | string | Yes | Source component ID |
| `target` | string | Yes | Target component ID |
| `name` | string | Yes | "main" or "reject" or custom |
| `condition` | string | No | Optional filter (Python expression) |
| `metadata` | object | No | Documentation |

### Flow Types

**Main Flow:**
```json
{
  "source": "input",
  "target": "transform",
  "name": "main"
}
```

**Reject Flow** (error/filtered rows):
```json
{
  "source": "filter_component",
  "target": "error_handler",
  "name": "reject"
}
```

**Conditional Flow** (if supported):
```json
{
  "source": "component_a",
  "target": "component_b",
  "name": "main",
  "condition": "value > 100"
}
```

### Trigger Structure

```json
{
  "source": "string",                 // Source component/subjob (required)
  "event": "string",                  // Event type (required)
  "target": "string",                 // Target subjob (required)
  "condition": "string"               // Optional condition
}
```

### Trigger Events

| Event | Meaning | Example |
|-------|---------|---------|
| `OnComponentOk` | Component succeeded | Fire if previous component succeeds |
| `OnComponentError` | Component failed | Fire if previous component fails |
| `OnSubjobOk` | Subjob completed successfully | Chain subjobs |
| `OnSubjobError` | Subjob failed | Error handling |
| `RunIf` | Conditional execution | `"${context.skip_flag}" != "true"` |

**Example Trigger:**
```json
{
  "source": "data_load",
  "event": "OnComponentOk",
  "target": "subjob_2"
}
```

---

## Schema Definition

### Schema Column Structure

```json
{
  "name": "string",                   // Column name (required)
  "type": "string",                   // Data type (required)
  "length": integer,                  // String length (optional)
  "precision": integer,               // Total digits (for numeric)
  "scale": integer,                   // Decimal places (for numeric)
  "nullable": boolean,                // Allow NULL values (default: true)
  "default": "value"                  // Default value (optional)
}
```

### Data Types

**String Types:**
```json
{"name": "email", "type": "string", "length": 100}
{"name": "name", "type": "string"}  // No length limit
```

**Numeric Types:**
```json
{"name": "count", "type": "integer"}
{"name": "amount", "type": "double", "precision": 10, "scale": 2}
{"name": "price", "type": "decimal", "precision": 19, "scale": 4}
```

**Temporal Types:**
```json
{"name": "created_date", "type": "date"}
{"name": "updated_time", "type": "timestamp"}
{"name": "birth_date", "type": "date"}
```

**Other Types:**
```json
{"name": "is_active", "type": "boolean"}
{"name": "metadata", "type": "object"}
```

### Complete Schema Example

```json
{
  "schema": [
    {"name": "id", "type": "integer", "precision": 10, "nullable": false},
    {"name": "name", "type": "string", "length": 100, "nullable": false},
    {"name": "email", "type": "string", "length": 255},
    {"name": "created_date", "type": "date"},
    {"name": "amount", "type": "decimal", "precision": 10, "scale": 2},
    {"name": "is_active", "type": "boolean", "default": true}
  ]
}
```

---

## Configuration Options

### File Input Components

**tFileInputDelimited:**
```json
{
  "id": "file_input",
  "type": "tFileInputDelimited",
  "config": {
    "file_path": "/path/to/file.csv",
    "delimiter": ",",
    "encoding": "UTF-8",
    "header": true,
    "skip_rows": 0,
    "quote_char": "\"",
    "escape_char": "\\",
    "null_value": "NULL"
  },
  "schema": [ /* column definitions */ ]
}
```

**tFileInputExcel:**
```json
{
  "id": "excel_input",
  "type": "tFileInputExcel",
  "config": {
    "file_path": "/path/to/file.xlsx",
    "sheet_name": "Sheet1",
    "sheet_index": 0,
    "header_row": 1,
    "read_headers": true
  }
}
```

### File Output Components

**tFileOutputDelimited:**
```json
{
  "id": "file_output",
  "type": "tFileOutputDelimited",
  "config": {
    "file_path": "/path/to/output.csv",
    "delimiter": ",",
    "encoding": "UTF-8",
    "include_header": true,
    "quote_char": "\"",
    "append": false,
    "create_directory": true
  }
}
```

### Transformation Components

**tMap:**
```json
{
  "id": "mapper",
  "type": "tMap",
  "config": {
    "mapping": {
      "output_col1": "input.col1.toUpperCase()",
      "output_col2": "input.col2 * 2",
      "output_col3": "'constant_value'"
    }
  }
}
```

**tFilter:**
```json
{
  "id": "filter",
  "type": "tFilter",
  "config": {
    "condition": "amount > 100 AND status == 'ACTIVE'"
  }
}
```

**tSort:**
```json
{
  "id": "sorter",
  "type": "tSort",
  "config": {
    "sort_keys": [
      {"column": "department", "order": "ASC"},
      {"column": "salary", "order": "DESC"}
    ]
  }
}
```

### Aggregation Components

**tAggregateRow:**
```json
{
  "id": "aggregator",
  "type": "tAggregateRow",
  "config": {
    "group_by": ["department", "year"],
    "aggregations": [
      {"column": "salary", "function": "SUM"},
      {"column": "employee_id", "function": "COUNT"},
      {"column": "bonus", "function": "AVG"}
    ]
  }
}
```

### Control Components

**tDie:**
```json
{
  "id": "error_handler",
  "type": "tDie",
  "config": {
    "message": "Processing failed: invalid input",
    "exit_code": 1
  }
}
```

---

## Context & Variables

### Context Definition

```json
{
  "context": {
    "input_dir": "/data/input",
    "output_dir": "/data/output",
    "max_rows": 1000,
    "skip_errors": false
  }
}
```

### Using Context Variables

In component config (string replacement):
```json
{
  "file_path": "${context.input_dir}/data.csv"
}
```

In Java expressions ({{java}} marker):
```json
{
  "mapping": {
    "output": "input_value + context.suffix"
  }
}
```

### Context Variable Types

**String variables:**
```json
{"input_file": "data.csv"}
```

**Numeric variables:**
```json
{"batch_size": 1000}
```

**Boolean variables:**
```json
{"debug_mode": true}
```

**Complex variables (from file):**
```json
{
  "context_file": "context.json",
  "context_file_type": "json"
}
```

---

## Java Bridge Configuration

### Basic Java Config

```json
{
  "java_config": {
    "enabled": true
  }
}
```

### Advanced Java Config

```json
{
  "java_config": {
    "enabled": true,
    "jvm_heap_size": "2g",              // Xmx memory
    "jvm_options": [
      "-XX:+UseG1GC",
      "-Dfile.encoding=UTF-8"
    ],
    "bridge_port": 25333,
    "bridge_timeout": 30,
    "debug": false,
    "max_batch_size": 10000
  }
}
```

### Java Config Properties

| Property | Type | Description |
|----------|------|-------------|
| `enabled` | boolean | Enable Java bridge |
| `jvm_heap_size` | string | JVM max memory (e.g., "2g", "1024m") |
| `jvm_options` | array | Additional JVM flags |
| `bridge_port` | integer | Py4J server port (25333 default) |
| `bridge_timeout` | integer | Expression timeout in seconds |
| `debug` | boolean | Enable Java debug logging |
| `max_batch_size` | integer | Expressions per RPC call |

---

## Complete Examples

### Example 1: Simple CSV Read/Write

```json
{
  "name": "simple_etl_job",
  "description": "Read CSV, apply filter, write output",
  "components": [
    {
      "id": "input",
      "type": "tFileInputDelimited",
      "config": {
        "file_path": "input_data.csv",
        "delimiter": ","
      },
      "schema": [
        {"name": "id", "type": "integer"},
        {"name": "name", "type": "string"},
        {"name": "salary", "type": "decimal", "precision": 10, "scale": 2}
      ]
    },
    {
      "id": "filter",
      "type": "tFilter",
      "config": {
        "condition": "salary > 50000"
      }
    },
    {
      "id": "output",
      "type": "tFileOutputDelimited",
      "config": {
        "file_path": "output_data.csv",
        "delimiter": ",",
        "include_header": true
      }
    }
  ],
  "flows": [
    {"source": "input", "target": "filter", "name": "main"},
    {"source": "filter", "target": "output", "name": "main"}
  ]
}
```

### Example 2: Complex Mapping with Java

```json
{
  "name": "complex_mapping_job",
  "java_config": {
    "enabled": true
  },
  "context": {
    "country_code": "US"
  },
  "components": [
    {
      "id": "input",
      "type": "tFileInputDelimited",
      "config": {
        "file_path": "${context.input_dir}/raw_data.csv"
      }
    },
    {
      "id": "mapper",
      "type": "tMap",
      "config": {
        "mapping": {
          "full_name": "first_name + ' ' + last_name",
          "email_upper": "email.toUpperCase()",
          "age_group": "age < 30 ? 'Young' : age < 60 ? 'Middle' : 'Senior'",
          "country": "'${context.country_code}'"
        }
      }
    },
    {
      "id": "filter",
      "type": "tFilter",
      "config": {
        "condition": "age_group != 'Senior'"
      }
    },
    {
      "id": "output",
      "type": "tFileOutputDelimited",
      "config": {
        "file_path": "${context.output_dir}/processed_data.csv"
      }
    }
  ],
  "flows": [
    {"source": "input", "target": "mapper", "name": "main"},
    {"source": "mapper", "target": "filter", "name": "main"},
    {"source": "filter", "target": "output", "name": "main"}
  ]
}
```

### Example 3: Multi-Component with Error Handling

```json
{
  "name": "robust_pipeline",
  "components": [
    {
      "id": "input",
      "type": "tFileInputDelimited",
      "config": {
        "file_path": "input.csv"
      }
    },
    {
      "id": "validate",
      "type": "tFilter",
      "config": {
        "condition": "id IS NOT NULL AND amount > 0"
      }
    },
    {
      "id": "process_valid",
      "type": "tMap",
      "config": {
        "mapping": {
          "processed_amount": "amount * 1.1"
        }
      }
    },
    {
      "id": "output_valid",
      "type": "tFileOutputDelimited",
      "config": {
        "file_path": "output_valid.csv"
      }
    },
    {
      "id": "output_invalid",
      "type": "tFileOutputDelimited",
      "config": {
        "file_path": "output_invalid.csv"
      }
    }
  ],
  "flows": [
    {"source": "input", "target": "validate", "name": "main"},
    {"source": "validate", "target": "process_valid", "name": "main"},
    {"source": "process_valid", "target": "output_valid", "name": "main"},
    {"source": "validate", "target": "output_invalid", "name": "reject"}
  ]
}
```

### Example 4: Aggregation Pipeline

```json
{
  "name": "aggregation_job",
  "components": [
    {
      "id": "input",
      "type": "tFileInputDelimited",
      "config": {
        "file_path": "sales_data.csv"
      },
      "schema": [
        {"name": "department", "type": "string"},
        {"name": "year", "type": "integer"},
        {"name": "amount", "type": "decimal", "precision": 10, "scale": 2}
      ]
    },
    {
      "id": "aggregate",
      "type": "tAggregateRow",
      "config": {
        "group_by": ["department"],
        "aggregations": [
          {"column": "amount", "function": "SUM"},
          {"column": "year", "function": "COUNT"}
        ]
      }
    },
    {
      "id": "sort",
      "type": "tSort",
      "config": {
        "sort_keys": [
          {"column": "amount", "order": "DESC"}
        ]
      }
    },
    {
      "id": "output",
      "type": "tFileOutputDelimited",
      "config": {
        "file_path": "aggregated_results.csv"
      }
    }
  ],
  "flows": [
    {"source": "input", "target": "aggregate", "name": "main"},
    {"source": "aggregate", "target": "sort", "name": "main"},
    {"source": "sort", "target": "output", "name": "main"}
  ]
}
```

---

## Validation Rules

### Component IDs
- Must be unique within job
- Alphanumeric + underscore only
- Cannot contain spaces
- Max 100 characters

### Component Types
- Must match registered component name exactly
- Case-sensitive (e.g., `tFileInputDelimited` not `tfileinputdelimited`)
- Must be supported by engine

### Flow Connections
- Source and target must exist
- Cannot create circular flows
- Can have multiple flows from one component

### Schema Names
- Must be unique within component schema
- Alphanumeric + underscore only
- Match actual data column names

### Data Types
- Must be valid SQL type
- Type-specific properties (precision, scale) must be valid
- String length must be > 0

---

## Tips & Best Practices

1. **Use context variables for portability:**
   ```json
   "file_path": "${context.data_dir}/file.csv"
   ```

2. **Define schema explicitly** for validation:
   ```json
   "schema": [{"name": "id", "type": "integer", "nullable": false}]
   ```

3. **Use meaningful component IDs:**
   ```json
   "id": "validate_customer_data"  // Clear purpose
   ```

4. **Group related flows:**
   ```json
   "flows": [
     {"source": "input", "target": "validate", "name": "main"},
     {"source": "validate", "target": "output_valid", "name": "main"},
     {"source": "validate", "target": "output_invalid", "name": "reject"}
   ]
   ```

5. **Add metadata for documentation:**
   ```json
   "metadata": {
     "owner": "data_team",
     "created": "2026-06-13",
     "version": "1.0.0"
   }
   ```

---

## JSON Schema Validation

For programmatic validation, use this schema structure:

```python
from jsonschema import validate, ValidationError
import json

config = json.load(open('job.json'))

# Validate against DataPrep schema
try:
    validate(instance=config, schema=dataprep_schema)
    print("Config valid")
except ValidationError as e:
    print(f"Config invalid: {e.message}")
```

---

## Troubleshooting Config Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Component type not found | Misspelled or unsupported | Check component name spelling |
| Flow target missing | Target component doesn't exist | Verify target component ID |
| Schema mismatch | Column names don't match | Update schema or component config |
| Invalid expression | Groovy/Java syntax error | Check expression for syntax errors |

For more help, see TROUBLESHOOTING.md

