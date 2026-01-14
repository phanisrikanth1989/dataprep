# RecDataPrep - Talend ETL Architecture Analysis

## Executive Summary

You're building a **Python-based ETL engine inspired by Talend's architecture**. This is a sophisticated distributed data transformation platform with:
- **Component-based architecture** (like Talend components)
- **Trigger-based workflow control** (OnSubjobOk, OnComponentOk, OnSubjobError)
- **Hybrid execution** (Python + Java via Py4J bridge)
- **Advanced data transformations** (tMap with lookups, joins, and expressions)
- **Multi-execution modes** (Batch, Streaming, Hybrid)

---

## 1. Architecture Overview

### 1.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    ETL ENGINE (Main Orchestrator)              │
│  - Job configuration loading (JSON)                            │
│  - Component lifecycle management                              │
│  - Trigger-based execution flow                                │
│  - Data flow routing between components                        │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Global State Mgmt│  │ Context Manager  │  │ Trigger Manager  │
│ (globalMap)      │  │ (context vars)   │  │ (workflow flow)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │ Java Bridge Manager  │
                    │ (Py4J + Apache Arrow)│
                    └──────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ Python Execs │    │ Java VM      │
            │ - Pandas     │    │ - Expressions│
            │ - Native Ops │    │ - Routines   │
            └──────────────┘    └──────────────┘
```

### 1.2 Key Components

**Core Engine Files:**
- `engine.py` - Main orchestrator, job execution, component lifecycle
- `base_component.py` - Abstract base for all ETL components
- `components/transform/map.py` - tMap (most complex, ~1140 lines)

**State & Context Management:**
- `global_map.py` - Talend-like global state store
- `context_manager.py` - Job context variables with type conversion
- `trigger_manager.py` - Trigger execution and workflow control

**Java Integration:**
- `java_bridge_manager.py` - Lifecycle management for Java bridge
- `java_bridge/bridge.py` - Py4J wrapper for Python-Java communication
- Uses **Apache Arrow** for efficient DataFrame serialization

---

## 2. Execution Flow

### 2.1 Job Execution Lifecycle

```
1. Initialize Engine
   ├─ Load job configuration (JSON)
   ├─ Initialize Java bridge (if enabled)
   ├─ Initialize Python routines
   ├─ Create global map & context manager
   ├─ Initialize all components from config
   └─ Register triggers

2. Identify Execution Topology
   ├─ Auto-detect subjobs (groups of connected components)
   ├─ Identify initial components (no inputs)
   └─ Register source components per subjob

3. Main Execution Loop (with Triggers)
   ├─ For each unexecuted component:
   │  ├─ Check if inputs are ready
   │  ├─ Check if component's subjob is active
   │  └─ Execute component
   │
   ├─ After component succeeds/fails:
   │  ├─ Update trigger manager status
   │  ├─ Check for triggered components
   │  ├─ Activate triggered subjobs if needed
   │  └─ Add triggered components to queue
   │
   ├─ Handle iterate components:
   │  ├─ Execute loop N times
   │  ├─ Run subjob on each iteration
   │  └─ Collect aggregated stats
   │
   └─ Repeat until all components executed

4. Cleanup
   ├─ Stop Java bridge
   ├─ Return execution statistics
   └─ Clean up resources
```

### 2.2 Component Execution

```
Component.execute(input_data)
  │
  ├─ Resolve Java expressions ({{java}} markers)
  ├─ Resolve context variables (${context.var})
  │
  ├─ Determine execution mode (Batch/Streaming/Hybrid)
  │
  ├─ Execute component logic
  │  └─ _process(input_data)
  │
  ├─ Update statistics
  │  └─ Write to global map
  │
  └─ Return output(s)
     ├─ main: Primary output
     ├─ reject: Error/rejected rows
     └─ [other named outputs]
```

---

## 3. Core Systems

### 3.1 GlobalMap (Talend-Like State Store)

**Purpose:** Shared state across components and iterations

```python
globalMap = GlobalMap()

# Store component statistics
globalMap.put_component_stat("tMap_1", "NB_LINE", 1000)
globalMap.put_component_stat("tMap_1", "NB_LINE_OK", 950)

# Access in expressions (Java-side)
((Integer)globalMap.get("tMap_1_NB_LINE"))  > 0

# Access in Python
value = globalMap.get_component_stat("tMap_1", "NB_LINE_OK")
```

**Statistics Tracked Per Component:**
- `NB_LINE` - Total rows processed
- `NB_LINE_OK` - Successfully processed
- `NB_LINE_REJECT` - Rejected/error rows
- `NB_LINE_INSERT`, `NB_LINE_UPDATE`, `NB_LINE_DELETE` - For database operations

### 3.2 Context Manager (Job Variables)

**Purpose:** Manage typed context variables (like Talend's context)

```json
{
  "context": {
    "Default": {
      "input_dir": { "value": "/data/input", "type": "id_String" },
      "max_rows": { "value": "10000", "type": "id_Integer" },
      "run_date": { "value": "2024-01-14", "type": "id_Date" }
    }
  }
}
```

**Variable Resolution:**
- `${context.input_dir}` → `/data/input`
- `context.max_rows` → `10000` (auto-converted to int)
- Supports concatenation: `${context.dir} + "/file.csv"`

### 3.3 Trigger Manager (Workflow Control)

**Trigger Types:**
- `OnComponentOK` - Fire when specific component succeeds
- `OnComponentError` - Fire when specific component fails
- `OnSubjobOk` - Fire when entire subjob completes successfully
- `OnSubjobError` - Fire when any component in subjob fails
- `RunIf` - Fire based on condition evaluation

**Example Trigger Sequence:**
```
1. Component A executes → Success
2. Trigger: OnComponentOK (A → B)
3. Subjob containing B is activated
4. Component B executes
5. Trigger: OnSubjobOk (B's subjob → C's subjob)
6. C's subjob is activated
```

---

## 4. tMap Component (Star Feature)

### 4.1 What is tMap?

**tMap = Data Transformation + Lookup/Join Engine**

It's your most powerful component - capable of:
- **Data transformation** with complex expressions
- **Multiple inputs** (1 main + N lookups)
- **Multiple outputs** with filtering
- **Joins** with different matching modes
- **Variables** for intermediate calculations
- **Parallel expression evaluation** (Java backend)

### 4.2 tMap Execution Pipeline

```
Input Data (main + lookups)
  │
  ▼ PHASE 1: Filter Lookups
  Apply any filter expressions to lookup tables
  │
  ▼ PHASE 2: Filter Main Input & Prepare Keys
  Apply main input filter, evaluate join key expressions
  │
  ▼ PHASE 3: Lookup Joins
  └─ Cartesian Join: Context-only expressions → cross join
  └─ Normal Join: Row-based expressions → left outer/inner join
  │
  ▼ PHASE 4: Evaluate Variables & Route to Outputs
  └─ Pre-evaluate all output columns via Java
  └─ Route rows based on output filters
  └─ Handle reject outputs (unmatched rows)
  │
  ▼ Output Data
```

### 4.3 Key tMap Features

**Expression Evaluation Strategy (Optimized Hybrid):**
```
1. Identify SIMPLE expressions: table.column
   └─ Extract directly from pandas (no Java)

2. Batch COMPLEX expressions: table.col > 100 && context.flag
   └─ Send to Java in ONE batch call (not per-row)

3. Use PANDAS for fast joins
   └─ Matching modes: FIRST_MATCH, LAST_MATCH, ALL_MATCHES

4. Compile TMAP ONCE, execute in CHUNKS
   └─ Generates optimized Java script
   └─ Parallel execution per chunk
   └─ ~189k rows/sec throughput
```

**Matching Modes (for lookups):**
- `UNIQUE_MATCH` / `FIRST_MATCH` - Keep first occurrence
- `LAST_MATCH` - Keep last occurrence  
- `ALL_MATCHES` - Keep all matches (default)

**Join Modes:**
- `LEFT_OUTER_JOIN` - Keep unmatched main rows
- `INNER_JOIN` - Only matched rows (unmatched → reject output)

### 4.4 tMap Configuration Example

```json
{
  "type": "Map",
  "id": "tMap_1",
  "config": {
    "inputs": {
      "main": {
        "name": "orders",
        "filter": "{{java}}orders.status == 'ACTIVE'",
        "activate_filter": true
      },
      "lookups": [
        {
          "name": "customers",
          "filter": "{{java}}customers.country IN ('US', 'CA')",
          "join_keys": [
            {
              "expression": "orders.customer_id",
              "lookup_column": "id"
            }
          ],
          "matching_mode": "FIRST_MATCH",
          "join_mode": "LEFT_OUTER_JOIN"
        }
      ]
    },
    "variables": [
      {
        "name": "total_amount",
        "expression": "{{java}}orders.amount + (customers.discount != null ? customers.discount : 0)"
      }
    ],
    "outputs": [
      {
        "name": "output_matched",
        "filter": "{{java}}customers.id != null",
        "activate_filter": true,
        "columns": [
          { "name": "order_id", "expression": "orders.id" },
          { "name": "customer_name", "expression": "customers.name" },
          { "name": "total", "expression": "total_amount" }
        ]
      },
      {
        "name": "output_reject",
        "reject": true,
        "columns": [
          { "name": "order_id", "expression": "orders.id" },
          { "name": "reason", "expression": "'NO_CUSTOMER'" }
        ]
      }
    ]
  }
}
```

---

## 5. Java Bridge (Py4J + Apache Arrow)

### 5.1 Architecture

```
Python Process                    Java Process (JVM)
─────────────────────────────────────────────────────
    tMap Component
         │
    DataFrame (pandas)
         │
    Apache Arrow Serialization
         │ (Binary encoded)
         ├────────────────────────────→ Arrow Deserialization
                                              │
                                        Java Objects
                                              │
                                        Execute Expression
                                              │
                                        Java Result
                                              │
    Arrow Deserialization  ←────────────────┤
         │
    NumPy Arrays / DataFrames
```

### 5.2 Key Methods

**One-Time Expression Evaluation:**
```python
java_bridge.execute_one_time_expression(
    "context.year + 100"  # Evaluate once (not per-row)
)
```

**Batch Expression Evaluation (tMap Preprocessing):**
```python
java_bridge.execute_tmap_preprocessing(
    df=DataFrame,  # ~189k rows/sec
    expressions={
        "__filter__": "orders.status == 'COMPLETE'",
        "__join_key__": "orders.customer_id"
    },
    main_table_name="orders"
)
# Returns: {"__filter__": [T,F,T,...], "__join_key__": [123,456,...]}
```

**Compiled tMap Execution (Most Optimized):**
```python
# STEP 1: Compile once
java_bridge.compile_tmap_script(
    component_id="tMap_1",
    java_script=generated_script,
    output_schemas={"output": ["col1", "col2"]},
    ...
)

# STEP 2: Execute chunks many times
results = java_bridge.execute_compiled_tmap_chunked(
    component_id="tMap_1",
    df=big_dataframe,  # Can be millions of rows
    chunk_size=50000  # Chunk size
)
```

### 5.3 Data Flow Safety

**Why Apache Arrow?**
- Preserves exact data types (pandas dtypes → Arrow → Java types)
- Prevents automatic type inference corruption
- Example: `["1", "2", "3"]` (strings) stays as strings, not auto-converted to int64

```python
# CRITICAL: Explicit Arrow schema prevents type corruption
arrow_schema_fields = []
for col_name in df.columns:
    pandas_dtype = str(df[col_name].dtype)
    if pandas_dtype == 'object':
        arrow_type = pa.string()  # Keep as string
    elif pandas_dtype.startswith('int'):
        arrow_type = pa.int64()
    # ... etc

explicit_schema = pa.schema(arrow_schema_fields)
arrow_table = pa.Table.from_pandas(df, schema=explicit_schema)
```

---

## 6. Execution Modes

### 6.1 Batch Mode
- Entire DataFrame loaded into memory
- Execute component once on full dataset
- **Use case:** Small to medium datasets

### 6.2 Streaming Mode
- DataFrame chunked into smaller pieces
- Each chunk processed independently
- Results concatenated
- **Use case:** Large datasets (>3GB memory threshold)

### 6.3 Hybrid Mode (Auto-Select)
- Automatically switch based on input size
- Memory usage > 3072 MB → Switch to Streaming
- Default for optimal performance

---

## 7. Job Configuration (JSON)

### 7.1 High-Level Structure

```json
{
  "job_name": "ETL_Sales_Pipeline",
  "default_context": "Default",
  
  "context": {
    "Default": {
      "input_dir": { "value": "/data/input", "type": "id_String" },
      "output_dir": { "value": "/data/output", "type": "id_String" }
    }
  },
  
  "java_config": {
    "enabled": true,
    "routines": ["routines.StringUtils"],
    "libraries": ["commons-lang3-3.14.0.jar"]
  },
  
  "python_config": {
    "enabled": true,
    "routines_dir": "src/python_routines"
  },
  
  "components": [
    { "id": "tFileInput_1", "type": "FileInput", ... },
    { "id": "tMap_1", "type": "Map", "subjob_id": "subjob_1", ... },
    { "id": "tFileOutput_1", "type": "FileOutput", "subjob_id": "subjob_1", ... }
  ],
  
  "flows": [
    { "from": "tFileInput_1", "to": "tMap_1", "type": "flow", "name": "flow1" },
    { "from": "tMap_1", "to": "tFileOutput_1", "type": "flow", "name": "flow2" }
  ],
  
  "triggers": [
    {
      "type": "OnSubjobOk",
      "from_component": "tFileInput_1",
      "to_component": "tCleanup_1",
      "condition": null
    }
  ]
}
```

### 7.2 Component Definition

```json
{
  "id": "tMap_1",
  "type": "Map",
  "subjob_id": "subjob_1",
  "is_subjob_start": false,
  "inputs": ["flow1"],
  "outputs": ["output", "reject"],
  
  "schema": {
    "input": [
      { "name": "order_id", "type": "id_Integer" },
      { "name": "amount", "type": "id_Float" }
    ],
    "output": [
      { "name": "order_id", "type": "id_Integer" },
      { "name": "total", "type": "id_Float" }
    ]
  },
  
  "config": {
    "inputs": { ... },
    "variables": [ ... ],
    "outputs": [ ... ]
  }
}
```

---

## 8. Subjobs & Iterate Components

### 8.1 Subjobs
- **Logical grouping** of related components
- **Execute in sequence** or triggered by previous subjob
- **Can share state** via globalMap

```
Subjob_1 (initial, no trigger)
  ├─ Component A
  ├─ Component B
  └─ Component C

[OnSubjobOk trigger]

Subjob_2 (triggered after Subjob_1)
  ├─ Component D
  ├─ Component E
  └─ Component F
```

### 8.2 Iterate Components
- Loop N times
- Each iteration executes downstream subjob
- Example: `tFileInput` with `iterate` flow

```
tFileInput_1 (reads file, splits into N chunks)
      │
      └─[iterate]→ Subjob_2 (processes each chunk)
                     ├─ tMap_1
                     ├─ tFileOutput_1
                     └─ [Loop back for next chunk]
      
Result: N iterations of Subjob_2
```

---

## 9. Current Codebase Status

### 9.1 What's Implemented ✅

- ✅ Core engine with component lifecycle
- ✅ Trigger-based workflow execution
- ✅ Global map state management
- ✅ Context variable management with type conversion
- ✅ Java bridge lifecycle management (Py4J)
- ✅ Apache Arrow data serialization
- ✅ tMap component with complex joins & transformations
- ✅ Batch, Streaming, Hybrid execution modes
- ✅ Multi-phase tMap processing (filter, join, output)
- ✅ Compiled tMap execution for performance

### 9.2 What's Not Implemented ❌

- ❌ Other component types (tFileInput, tFileOutput, tDatabase, etc.)
- ❌ Iterate component support (infrastructure exists, not components)
- ❌ Error handling for missing columns
- ❌ Component schema validation
- ❌ Configuration UI/visual job builder
- ❌ Job scheduling
- ❌ Monitoring & metrics dashboard
- ❌ Rollback/recovery mechanisms
- ❌ Parallel component execution (currently sequential within subjob)

### 9.3 Known Issues 🐛

1. **GlobalMap.py has bugs:**
   - References `self._map` instead of `self._storage`
   - `get()` method missing `default` parameter

2. **ContextManager.py has indentation issues:**
   - `load_context()` and `load_from_file()` methods defined inside `__init__`

3. **Python Routine Manager:**
   - File exists but is empty - needs implementation

4. **Type conversion:**
   - Limited type support, missing BigDecimal, custom types

5. **Error handling:**
   - die_on_error config mostly stubbed, not fully tested
   - Limited error context in exceptions

---

## 10. Performance Characteristics

### 10.1 tMap Throughput

| Scenario | Rows/Sec | Notes |
|----------|----------|-------|
| Simple column mapping | 500k+ | Direct pandas ops |
| Filter + Single join | 200k | Batch expression eval + merge |
| Multiple joins | 100k | Cartesian products scale poorly |
| Complex expressions | 189k | Compiled Java script (optimal) |

### 10.2 Memory Usage

**3GB Threshold (Hybrid Mode):**
- Below 3GB → Batch processing
- Above 3GB → Streaming chunks (50k rows default)

**Example:**
```
10M rows × 10 columns (numeric) ≈ 800MB
→ Batch mode

100M rows × 10 columns ≈ 8GB
→ Streaming mode (chunk size = 50k)
→ ~2000 chunks
```

---

## 11. Design Patterns Used

### 11.1 Component Registry
```python
COMPONENT_REGISTRY = {
    'Map': Map,
    'tMap': Map,
    # Add more components here
}

comp_class = COMPONENT_REGISTRY.get(comp_type)
component = comp_class(comp_id, config)
```

### 11.2 Context Manager Pattern
- Singleton-like behavior per job
- Lazy initialization of Java bridge
- Graceful fallback if Java unavailable

### 11.3 Hybrid Execution Strategy
- Auto-detect based on data size
- Fallback options (e.g., Java disabled → Python-only)
- Chunk processing for memory management

### 11.4 Batch Expression Evaluation
- Collect all expressions
- Execute in ONE Java call (not N calls)
- Return results as maps/arrays
- Reduces Py4J overhead

---

## 12. How to Extend

### 12.1 Add New Component

```python
# 1. Create component file: src/v1/engine/components/io/file_input.py
from base_component import BaseComponent

class FileInput(BaseComponent):
    def _process(self, input_data=None):
        # Your implementation
        return {'main': pandas_dataframe}

# 2. Register in engine.py
from .components.io.file_input import FileInput
COMPONENT_REGISTRY['tFileInput'] = FileInput

# 3. Use in JSON config
{
    "type": "tFileInput",
    "config": {
        "file_path": "/data/input.csv"
    }
}
```

### 12.2 Add New Expression Type

```python
# In tMap or component that evaluates expressions:

# Current: {{java}} expressions handled via Java bridge
if expr.startswith('{{java}}'):
    result = java_bridge.execute(expr)

# New: Add Python expressions
elif expr.startswith('{{python}}'):
    python_code = expr[10:]  # Remove marker
    result = eval(python_code, {"vars": locals()})
```

### 12.3 Add Java Routines

```python
# 1. Create Java file: src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/routines/StringUtils.java
public class StringUtils {
    public static String toUpperCase(String input) {
        return input.toUpperCase();
    }
}

# 2. Configure in JSON
{
    "java_config": {
        "routines": ["routines.StringUtils"],
        "libraries": ["commons-lang3-3.14.0.jar"]
    }
}

# 3. Use in expressions
"{{java}}routines.StringUtils.toUpperCase(orders.name)"
```

---

## 13. Deployment Considerations

### 13.1 Requirements
- Python 3.8+
- Pandas >= 1.2.0
- Py4J >= 0.10.0
- Apache Arrow
- Java 11+ (for Java bridge)

### 13.2 Configuration
- JSON job files should be versioned with the pipeline
- Context values can be overridden at runtime via CLI
- Java classpath must include all required libraries

### 13.3 Scaling
- **Single machine:** Process up to 100M rows in streaming mode
- **Distributed:** No built-in clustering (would require RDD/Spark integration)
- **Parallelization:** Opportunities in compiled tMap execution

---

## 14. Recommendations

### High Priority
1. **Fix GlobalMap bugs** - Data corruption risk
2. **Fix ContextManager indentation** - Won't work as-is
3. **Implement Python Routine Manager** - Required for Python expressions
4. **Add component types** - tFileInput, tFileOutput minimum

### Medium Priority
5. **Improve error handling** - Better error context and recovery
6. **Add schema validation** - Prevent type mismatches
7. **Unit tests** - Currently appears to have none
8. **Documentation** - Add docstrings and examples

### Future Enhancements
9. **Parallel component execution** - Within subjobs where possible
10. **Distributed execution** - Spark backend
11. **Real-time monitoring** - Web dashboard
12. **More component types** - Database, API, message queue connectors

---

## 15. Key Takeaways

1. **Well-architected** - Clear separation of concerns, component model scales
2. **Performance-focused** - Compiled script execution, Arrow serialization
3. **Production-ready basics** - Context, triggers, state management done right
4. **Incomplete implementation** - Core engine exists, but components/utilities missing
5. **Talend-compatible design** - Familiar mental model for Talend users
6. **Python-Java hybrid strength** - Leverages both ecosystems effectively

