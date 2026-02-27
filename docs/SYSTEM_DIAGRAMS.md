# RecDataPrep - Visual System Diagrams

## 1. Complete System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      WEB BROWSER (User)                              │
│                   http://localhost:5173                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │              FRONTEND (React 18 + TypeScript)                  │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │           App Shell (App.tsx)                            │ │  │
│  │  │   Navigation between List/Designer/Execution pages      │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  │           │               │                    │               │  │
│  │     ┌─────▼────┐    ┌─────▼─────┐      ┌──────▼──────┐        │  │
│  │     │ JobList  │    │JobDesigner│      │  Execution  │        │  │
│  │     │Component │    │   Page    │      │  Monitor    │        │  │
│  │     └─────┬────┘    └─────┬─────┘      └──────┬──────┘        │  │
│  │           │                │                  │               │  │
│  │           └────────────────┼──────────────────┘               │  │
│  │                            │                                   │  │
│  │  ┌────────────────────────┴─────────────────────────────────┐ │  │
│  │  │        Shared Components & Services                      │ │  │
│  │  │                                                          │ │  │
│  │  │  • Canvas (React Flow)  ← Visual editor               │ │  │
│  │  │  • ComponentPalette     ← Draggable toolbar            │ │  │
│  │  │  • ComponentNode        ← Node representation           │ │  │
│  │  │  • ConfigPanel          ← Dynamic forms                │ │  │
│  │  │  • ExecutionMonitor     ← Progress tracking            │ │  │
│  │  │                                                          │ │  │
│  │  │  Services:                                              │ │  │
│  │  │  • api.ts (REST/Axios)                                 │ │  │
│  │  │  • websocket.ts (Socket.io)                            │ │  │
│  │  │                                                          │ │  │
│  │  │  Types:                                                 │ │  │
│  │  │  • JobSchema, JobNode, JobEdge                         │ │  │
│  │  │  • ComponentMetadata, ExecutionStatus                  │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                    ▲                                  ▲
                    │ HTTP REST API                    │ WebSocket
                    │                                  │ Real-time
                    │                                  │ Streams
                    ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    BACKEND SERVER (FastAPI)                          │
│                    http://localhost:8000                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Routes Layer                               │ │
│  │  ┌───────────────┐  ┌──────────────┐  ┌────────────────────┐ │ │
│  │  │  /api/jobs    │  │ /api/components │  │ /api/execution   │ │ │
│  │  │               │  │                │  │                  │ │ │
│  │  │ • GET list    │  │ • GET list     │  │ • POST /start    │ │ │
│  │  │ • GET {id}    │  │ • GET {type}   │  │ • GET /{task_id} │ │ │
│  │  │ • POST create │  │                │  │ • WS stream      │ │ │
│  │  │ • PUT update  │  │                │  │ • POST /stop     │ │ │
│  │  │ • DELETE      │  │                │  │                  │ │ │
│  │  │ • GET export  │  │                │  │                  │ │ │
│  │  └───────────────┘  └──────────────┘  └────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐ │
│  │                   Services Layer                              │ │
│  │  ┌──────────────────┐         ┌──────────────────────────┐   │ │
│  │  │  JobService      │         │ ExecutionManager         │   │ │
│  │  │                  │         │                          │   │ │
│  │  │ • create_job     │         │ • create_execution       │   │ │
│  │  │ • get_job        │         │ • get_execution          │   │ │
│  │  │ • list_jobs      │         │ • update_execution       │   │ │
│  │  │ • update_job     │         │ • execute_job (async)    │   │ │
│  │  │ • delete_job     │         │ • subscribe/notify       │   │ │
│  │  │ • export_config  │         │                          │   │ │
│  │  └──────────────────┘         └──────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐ │
│  │              Pydantic Models & Schemas                         │ │
│  │  • JobSchema        • ComponentMetadata                        │ │
│  │  • JobNode          • ExecutionStatus                          │ │
│  │  • JobEdge          • ExecutionUpdate                          │ │
│  │  • ExecutionRequest • ComponentFieldSchema                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐ │
│  │              File Storage (jobs/*.json)                        │ │
│  │  Persistent job definitions and configurations                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                    │ Job Config (JSON)
                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│              PYTHON ETL ENGINE (Core Processing)                     │
│              src/v1/engine/*.py                                      │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                 Engine Orchestrator                            │ │
│  │                  (engine.py)                                   │ │
│  │                                                                │ │
│  │  1. Load job configuration (JSON)                             │ │
│  │  2. Initialize state managers                                 │ │
│  │  3. Instantiate components                                    │ │
│  │  4. Identify execution topology (DAG)                         │ │
│  │  5. Execute components in dependency order                    │ │
│  │  6. Evaluate triggers → activate subjobs                      │ │
│  │  7. Route data between components                             │ │
│  │  8. Collect statistics & return results                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            │                                         │
│        ┌───────────────────┼───────────────────┐                     │
│        ▼                   ▼                   ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ GlobalMap    │  │ Context      │  │ Trigger      │               │
│  │              │  │ Manager      │  │ Manager      │               │
│  │ • Store      │  │              │  │              │               │
│  │   component  │  │ • Resolve    │  │ • Evaluate   │               │
│  │   stats      │  │   variables  │  │   triggers   │               │
│  │ • Access     │  │ • Type       │  │ • Activate   │               │
│  │   shared     │  │   conversion │  │   subjobs    │               │
│  │   state      │  │ • Context    │  │              │               │
│  │              │  │   variables  │  │              │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                            │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐ │
│  │           Component Execution Layer                            │ │
│  │                                                                │ │
│  │  BaseComponent (Abstract)                                      │ │
│  │  ├─ execute()  → lifecycle management                         │ │
│  │  ├─ _process() → component-specific logic                     │ │
│  │  └─ stats      → tracking metrics                             │ │
│  │                                                                │ │
│  │  Built-in Components:                                          │ │
│  │  ├─ Map (tMap)      ← 1140 LOC: joins, lookups, transforms   │ │
│  │  ├─ Filter          ← Row filtering with conditions            │ │
│  │  ├─ FileInput       ← CSV/JSON/Parquet/Excel reader           │ │
│  │  ├─ FileOutput      ← File writer                              │ │
│  │  ├─ Aggregate       ← Group-by operations                      │ │
│  │  └─ Sort            ← Sorting by columns                       │ │
│  │                                                                │ │
│  │  Framework Features:                                           │ │
│  │  ├─ Execution Modes (Batch/Streaming/Hybrid)                  │ │
│  │  ├─ Expression Resolution (Java/Python)                       │ │
│  │  ├─ Statistics Tracking                                        │ │
│  │  └─ Error Handling                                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            │                                         │
│        ┌───────────────────┼───────────────────┐                     │
│        ▼                   ▼                   ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   Python     │  │    Java      │  │   Python     │               │
│  │ Processing   │  │   Bridge     │  │  Routines    │               │
│  │              │  │              │  │              │               │
│  │ • Pandas     │  │ • Py4J       │  │ • Custom     │               │
│  │ • DataFrames │  │ • Apache     │  │   functions  │               │
│  │ • Joins      │  │   Arrow      │  │ • Imports    │               │
│  │ • Grouping   │  │ • Java VM    │  │   modules    │               │
│  │              │  │              │  │              │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow Example: Simple Job

```
USER INTERACTION:
┌─────────────────────────────────────────┐
│ 1. User creates job with 3 components:  │
│    • FileInput (source)                 │
│    • Map (transform)                    │
│    • FileOutput (sink)                  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 2. User configures each component:      │
│    • File paths                         │
│    • Transformations                    │
│    • Output format                      │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 3. User saves job (Backend stores JSON) │
└─────────────────────────────────────────┘
         │
         ▼

EXECUTION:
┌─────────────────────────────────────────┐
│ 4. User clicks "Execute"                │
│    → POST /api/execution/start          │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 5. Backend:                             │
│    • Generates task_id                  │
│    • Exports job config                 │
│    • Starts ETLEngine async             │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 6. Frontend connects WebSocket:         │
│    ws://localhost:8000/ws/{task_id}     │
└─────────────────────────────────────────┘
         │
         ▼

ENGINE EXECUTION:
┌─────────────────────────────────────────┐
│ 7. ETLEngine.execute()                  │
│    • Initialize GlobalMap               │
│    • Create component instances         │
│    • Identify topology (DAG)            │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 8. Execute FileInput component:         │
│    • Read CSV file                      │
│    • Parse rows → DataFrame(1000 rows)  │
│    • Return {"main": DataFrame}         │
│    • Update stats: NB_LINE=1000          │
└─────────────────────────────────────────┘
         │ Emit update event
         ▼
    WebSocket → Frontend
    "Component FileInput_1 completed"
         │
         ▼
┌─────────────────────────────────────────┐
│ 9. Execute Map component:               │
│    • Receive input DataFrame(1000)      │
│    • Apply transformations              │
│    • Evaluate expressions               │
│    • Return:                            │
│      - main: 950 rows (success)         │
│      - reject: 50 rows (errors)         │
│    • Update stats                       │
└─────────────────────────────────────────┘
         │ Emit update event
         ▼
    WebSocket → Frontend
    "Component Map_1 completed"
    "Progress: 1000/1000 rows"
         │
         ▼
┌─────────────────────────────────────────┐
│ 10. Execute FileOutput (main flow):     │
│     • Receive 950 rows                  │
│     • Write to output CSV               │
│     • Update stats                      │
└─────────────────────────────────────────┘
         │ Emit update event
         ▼
    WebSocket → Frontend
    "Component FileOutput_1 completed"
         │
         ▼
┌─────────────────────────────────────────┐
│ 11. Job Complete                        │
│     • Collect all statistics            │
│     • Return execution results          │
│     • Update status → "success"         │
└─────────────────────────────────────────┘
         │ Final WebSocket update
         ▼
    Frontend displays:
    ✓ Execution successful
    • Total time: 2.34s
    • Rows processed: 1000
    • Output: 950 rows written
```

---

## 3. Complex Flow: Map with Lookups

```
INPUT SOURCES:
┌──────────────┐  ┌──────────────┐
│ Main Input   │  │ Lookup Table │
│              │  │              │
│ Product ID   │  │ Product ID   │
│ Quantity     │  │ Product Name │
│ Price        │  │ Category     │
│              │  │              │
│ 1000 rows    │  │ 500 rows     │
└──────────────┘  └──────────────┘
       │                │
       └────────┬───────┘
                │
                ▼
         ┌──────────────┐
         │   tMap       │
         │ Component    │
         └──────────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼

INTERNAL STEPS:

1. Load lookups into memory
   └─ Product lookup: 500 rows → indexed by product_id

2. Iterate main rows (1000 rows)
   ├─ Row 1: Product ID = 101
   │  ├─ Find in lookup (Product ID 101)
   │  ├─ Merge data (Product Name + Category)
   │  ├─ Apply transformations
   │  └─ Route to MAIN output (row matched)
   │
   ├─ Row 2: Product ID = 999 (not found)
   │  ├─ Apply transformations
   │  └─ Route to REJECT output (lookup failed)
   │
   └─ ... repeat for all 1000 rows

3. Generate outputs
   ├─ MAIN output: 950 rows (successful matches)
   └─ REJECT output: 50 rows (lookup misses/errors)

OUTPUTS:
┌────────────────────┐  ┌────────────────┐
│ Main Output        │  │ Reject Output  │
│                    │  │                │
│ Product ID         │  │ Product ID     │
│ Quantity           │  │ Quantity       │
│ Price              │  │ Price          │
│ Product Name (new) │  │ Error Message  │
│ Category (new)     │  │                │
│                    │  │                │
│ 950 rows           │  │ 50 rows        │
└────────────────────┘  └────────────────┘
```

---

## 4. Job Schema Structure

```json
{
  "id": "job_12345",
  "name": "Sales ETL",
  "description": "Process sales data with lookups",
  
  "nodes": [
    {
      "id": "FileInput_1",
      "type": "FileInput",
      "label": "Sales Data",
      "x": 50,
      "y": 100,
      "config": {
        "file_path": "/data/sales.csv",
        "file_format": "csv",
        "encoding": "utf-8"
      }
    },
    {
      "id": "FileInput_2",
      "type": "FileInput",
      "label": "Product Lookup",
      "x": 50,
      "y": 300,
      "config": {
        "file_path": "/data/products.csv",
        "file_format": "csv"
      }
    },
    {
      "id": "Map_1",
      "type": "Map",
      "label": "Transform & Join",
      "x": 300,
      "y": 200,
      "config": {
        "die_on_error": true,
        "execution_mode": "hybrid",
        "variables": [...],
        "lookups": [
          {
            "name": "products",
            "keys": ["product_id"],
            "matching_mode": "FIRST_MATCH"
          }
        ]
      }
    },
    {
      "id": "FileOutput_1",
      "type": "FileOutput",
      "label": "Output Success",
      "x": 550,
      "y": 150,
      "config": {
        "file_path": "/output/success.csv",
        "file_format": "csv"
      }
    },
    {
      "id": "FileOutput_2",
      "type": "FileOutput",
      "label": "Output Reject",
      "x": 550,
      "y": 250,
      "config": {
        "file_path": "/output/reject.csv",
        "file_format": "csv"
      }
    }
  ],
  
  "edges": [
    {
      "id": "edge_1",
      "source": "FileInput_1",
      "target": "Map_1",
      "edge_type": "main",
      "name": "sales_main"
    },
    {
      "id": "edge_2",
      "source": "FileInput_2",
      "target": "Map_1",
      "edge_type": "lookup",
      "name": "products"
    },
    {
      "id": "edge_3",
      "source": "Map_1",
      "target": "FileOutput_1",
      "edge_type": "main",
      "name": "main"
    },
    {
      "id": "edge_4",
      "source": "Map_1",
      "target": "FileOutput_2",
      "edge_type": "reject",
      "name": "reject"
    }
  ],
  
  "context": {
    "batch_size": 1000,
    "max_errors": 100
  },
  
  "java_config": {
    "enabled": false,
    "routines": [],
    "libraries": []
  },
  
  "python_config": {
    "enabled": false,
    "routines_dir": "src/python_routines"
  },
  
  "created_at": "2026-01-17T10:30:00Z",
  "updated_at": "2026-01-17T11:45:00Z"
}
```

---

## 5. Execution Status Flow

```
Initial State:
┌─────────────────────────────────────────────────────────────┐
│ {                                                           │
│   "task_id": "task_abc123",                                 │
│   "job_id": "job_12345",                                    │
│   "status": "pending",                                      │
│   "progress": 0,                                            │
│   "started_at": "2026-01-17T12:00:00Z",                     │
│   "logs": []                                                │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
    Running:
┌─────────────────────────────────────────────────────────────┐
│ {                                                           │
│   "status": "running",                                      │
│   "progress": 45,  ← 45% complete                           │
│   "logs": [                                                 │
│     "Component FileInput_1 started",                        │
│     "Component FileInput_1 completed: 1000 rows",           │
│     "Component Map_1 started",                              │
│     "Component Map_1: processed 450 rows..."                │
│   ]                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
    Completed (Success):
┌─────────────────────────────────────────────────────────────┐
│ {                                                           │
│   "status": "success",                                      │
│   "progress": 100,                                          │
│   "completed_at": "2026-01-17T12:00:15Z",                   │
│   "stats": {                                                │
│     "total_time": 15.23,                                    │
│     "components": {                                         │
│       "FileInput_1": {                                      │
│         "NB_LINE": 1000,                                    │
│         "NB_LINE_OK": 1000                                  │
│       },                                                    │
│       "Map_1": {                                            │
│         "NB_LINE": 1000,                                    │
│         "NB_LINE_OK": 950,                                  │
│         "NB_LINE_REJECT": 50                                │
│       },                                                    │
│       "FileOutput_1": {"NB_LINE": 950},                     │
│       "FileOutput_2": {"NB_LINE": 50}                       │
│     }                                                       │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Component Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                    Component Lifecycle                           │
└──────────────────────────────────────────────────────────────────┘

┌─ INSTANTIATION ──────────────────────────────────────────────┐
│  1. BaseComponent.__init__()                                  │
│     ├─ Initialize component_id                               │
│     ├─ Store config parameters                               │
│     ├─ Initialize stats dictionary                           │
│     ├─ Set execution mode (Batch/Streaming/Hybrid)           │
│     └─ Status = PENDING                                      │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─ EXECUTION ──────────────────────────────────────────────────┐
│  2. Component.execute(input_data)                             │
│     ├─ Status = RUNNING                                       │
│     ├─ Resolve Java expressions in config (if enabled)       │
│     ├─ Resolve context variables                             │
│     └─ Call _process(input_data)                             │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─ PROCESSING ─────────────────────────────────────────────────┐
│  3. Component._process(input_data) [Component-Specific]       │
│     ├─ Load component-specific logic                          │
│     ├─ Process input data                                     │
│     ├─ Apply transformations                                  │
│     ├─ Update internal statistics                             │
│     └─ Return output data (dict of outputs)                   │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─ STATS UPDATE ───────────────────────────────────────────────┐
│  4. Component._update_global_map()                            │
│     ├─ Store NB_LINE (total rows)                            │
│     ├─ Store NB_LINE_OK (successful rows)                    │
│     ├─ Store NB_LINE_REJECT (failed rows)                    │
│     ├─ Store EXECUTION_TIME                                   │
│     └─ Store error information (if any)                      │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─ FINALIZATION ───────────────────────────────────────────────┐
│  5. Component status finalized                                │
│     ├─ Status = SUCCESS (if no errors)                       │
│     ├─ Status = ERROR (if exceptions)                        │
│     └─ Return result: {"main": output, "reject": errors}     │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─ ROUTING ────────────────────────────────────────────────────┐
│  6. Engine routes outputs to downstream components            │
│     ├─ Main output → downstream main input                   │
│     ├─ Reject output → error handler (if configured)         │
│     └─ Trigger evaluation (if applicable)                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. API Request/Response Flows

```
FLOW 1: CREATE JOB
─────────────────

Frontend                          Backend
  │                                 │
  ├─ POST /api/jobs               │
  │  {                              │
  │    "id": "job_1",              │
  │    "name": "My Job",           │
  │    "nodes": [...],             │
  │    "edges": [...]              │
  │  }                              │
  ├────────────────────────────────>
  │                                 │ Validate schema
  │                                 │ Save to jobs/job_1.json
  │                                 │ Update created_at/updated_at
  │                                 │
  │                 {               │
  │                   "id": "job_1",│
  │                   "status": "ok"│
  │                 }               │
  │<────────────────────────────────┤
  │                                 │
  └─ Display job created           │


FLOW 2: EXECUTE JOB
───────────────────

Frontend                          Backend                   Engine
  │                                 │                         │
  ├─ POST /api/execution/start     │                         │
  │  {                              │                         │
  │    "job_id": "job_1"           │                         │
  │  }                              │                         │
  ├────────────────────────────────>                         │
  │                                 │ Load job config         │
  │                                 │ Generate task_id        │
  │                                 │ Start async execution   │
  │                                 ├────────────────────────>
  │                                 │                         │ Initialize
  │                 {               │                         │ Load components
  │                   "task_id":    │                         │ Create GlobalMap
  │                   "task_abc123" │                         │
  │                 }               │                         │
  │<────────────────────────────────┤                         │
  │                                 │                         │
  ├─ WS connect:                   │                         │
  │  ws://host/ws/task_abc123      │                         │
  ├────────────────────────────────>                         │
  │                                 │ Subscribe to updates    │
  │                                 │                         │
  │                                 │ Execute FileInput_1     │
  │                                 ├────────────────────────>
  │                                 │                         │ Read file
  │                                 │                         │ Return 1000 rows
  │                                 │<────────────────────────┤
  │                                 │                         │
  │  WS: {event: "component_end",  │                         │
  │        component: "FileInput_1",│                         │
  │        rows_out: 1000}          │                         │
  │<────────────────────────────────┤                         │
  │                                 │                         │
  │                                 │ Execute Map_1          │
  │                                 ├────────────────────────>
  │                                 │                         │ Join with lookup
  │                                 │                         │ Transform rows
  │                                 │                         │ Route to outputs
  │                                 │<────────────────────────┤
  │                                 │                         │
  │  WS: {event: "component_end",  │                         │
  │        component: "Map_1",      │                         │
  │        rows_ok: 950,            │                         │
  │        rows_reject: 50}         │                         │
  │<────────────────────────────────┤                         │
  │                                 │                         │
  │  ... more components ...        │                         │
  │                                 │                         │
  │  WS: {event: "execution_end",  │                         │
  │        status: "success",       │                         │
  │        total_time: 15.23,       │                         │
  │        stats: {...}}            │                         │
  │<────────────────────────────────┤                         │
  │                                 │                         │
  └─ Display execution results     │                         │
```

---

## 8. Component Discovery Flow

```
Frontend                          Backend
  │                                 │
  ├─ GET /api/components          │
  ├────────────────────────────────>
  │                                 │ Load COMPONENT_REGISTRY
  │                                 │ Return all metadata
  │  [                              │
  │    {                            │
  │      "type": "Map",            │
  │      "label": "tMap",          │
  │      "category": "Transform",  │
  │      "icon": "swap",           │
  │      "fields": [               │
  │        {                        │
  │          "name": "execution_mode",
  │          "type": "select",     │
  │          "options": [...],     │
  │          ...                   │
  │        }                        │
  │      ]                          │
  │    },                           │
  │    {...},                       │
  │    ...                          │
  │  ]                              │
  │<────────────────────────────────┤
  │                                 │
  └─ Populate component palette    │
     (Draggable toolbar)            │
```

---

## 9. Trigger Evaluation

```
After Component Execution:
──────────────────────────

Component completes
       │
       ▼
Update GlobalMap with stats
       │
       ▼
TriggerManager.evaluate_triggers()
       │
       ├─ Check trigger conditions
       │
       ├─ OnComponentOk(Map_1)?
       │  └─ Condition met? → Mark FileOutput as ready
       │
       ├─ OnSubjobError(subjob_2)?
       │  └─ Error occurred? → Activate error handler
       │
       └─ OnSubjobOk(subjob_1)?
          └─ Subjob complete? → Activate subjob_2
                               → Add to execution queue
                               → Proceed with next components

Route data & update component states
       │
       ▼
Engine resumes main loop
       │
       └─ Execute next ready component
```

---

## 10. File System Layout During Execution

```
recdataprep/
├── backend/
│   ├── app/
│   ├── run.py
│   └── jobs/
│       ├── job_1.json
│       ├── job_2.json
│       └── sales_etl.json
│
├── frontend/
│   ├── src/
│   └── dist/  ← Built files (after npm run build)
│       ├── index.html
│       ├── assets/
│       │   ├── index-xxx.js
│       │   └── index-xxx.css
│       └── ...
│
├── src/
│   └── v1/
│       └── engine/
│
└── output/
    ├── success_2026-01-17.csv
    ├── reject_2026-01-17.csv
    └── ... (job output files)
```

*This comprehensive workspace contains a production-ready ETL visual designer system.*
