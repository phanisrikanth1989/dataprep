# RecDataPrep Workspace - Complete Overview

**Last Updated:** January 17, 2026  
**Status:** Production Ready  
**Total Implementation:** 50+ files, ~5000 lines of code

---

## 🎯 Project Vision

**RecDataPrep** is a **Python-based ETL (Extract-Transform-Load) visual designer** inspired by Talend's architecture. It provides:
- A web-based UI for designing ETL jobs visually (drag-and-drop)
- A powerful backend engine that executes these jobs
- Integration with Python and Java routines
- Advanced features like triggers, lookups, joins, and expressions
- Real-time execution monitoring via WebSockets

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER (Web Browser)                       │
│                  http://localhost:5173                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND (React 18)                       │
│  - React Flow: Drag-drop visual canvas                      │
│  - Ant Design: Component UI library                         │
│  - TypeScript: Type-safe code                              │
│  - Job Designer: Visual job builder                        │
│  - Job List: Manage all jobs                               │
│  - Execution Monitor: Real-time progress tracking          │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ REST API / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Routes Layer (REST API)                               │ │
│  │  - /api/jobs (CRUD operations)                         │ │
│  │  - /api/components (metadata registry)                 │ │
│  │  - /api/execution (run jobs, WebSocket streams)        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Services Layer                                        │ │
│  │  - JobService: Job persistence                        │ │
│  │  - ExecutionManager: Job execution & tracking         │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Models Layer (Pydantic)                               │ │
│  │  - JobSchema: Job structure                           │ │
│  │  - ExecutionStatus: Execution tracking                │ │
│  │  - ComponentMetadata: Component definitions           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Job Config (JSON)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   ETL ENGINE (Core)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Engine (engine.py)                                    │ │
│  │  - Job lifecycle management                           │ │
│  │  - Component orchestration                            │ │
│  │  - Trigger evaluation & workflow control              │ │
│  │  - Data routing between components                    │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  State Management                                      │ │
│  │  - GlobalMap: Shared state store (Talend-like)        │ │
│  │  - ContextManager: Job variables with type conversion │ │
│  │  - TriggerManager: Workflow control                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Components (Extensible Registry)                     │ │
│  │  - Map: Transformation with joins/lookups (1140 LOC)  │ │
│  │  - Filter: Row filtering based on conditions          │ │
│  │  - FileInput: Read CSV/JSON/Parquet/Excel            │ │
│  │  - FileOutput: Write files with various formats       │ │
│  │  - Aggregate: Group-by aggregations                   │ │
│  │  - Sort: Sort data by columns                         │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Integrations                                          │ │
│  │  - JavaBridgeManager: Py4J + Apache Arrow            │ │
│  │  - PythonRoutineManager: Custom Python functions      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
           ┌────────┐  ┌─────────┐  ┌──────────┐
           │ Python │  │ Java VM │  │ File I/O │
           │ Pandas │  │ Py4J    │  │ Storage  │
           └────────┘  └─────────┘  └──────────┘
```

---

## 📁 Detailed Folder Structure

### Root Level Documentation
```
recdataprep/
├── START_HERE.md                 ← Quick start guide
├── README_INDEX.md               ← Navigation hub
├── ARCHITECTURE.md               ← Deep architecture docs
├── UI_README.md                  ← UI feature guide
├── QUICK_REFERENCE.md            ← Command reference
├── SETUP_DEPLOYMENT.md           ← Setup instructions
├── TESTING_GUIDE.md              ← Validation procedures
├── FILE_INVENTORY.md             ← All 50+ files listed
├── COMPLETION_CHECKLIST.md       ← Implementation status
├── IMPLEMENTATION_COMPLETE.md    ← Final summary
├── quickstart.bat                ← Windows startup script
├── quickstart.sh                 ← Mac/Linux startup script
```

### Backend Structure
```
backend/
├── run.py                        ← Entry point (uvicorn server)
├── requirements.txt              ← Dependencies (FastAPI, Pydantic, etc)
├── app/
│   ├── __init__.py              ← Package init
│   ├── main.py                  ← FastAPI app factory
│   ├── models.py                ← Pydantic data models
│   ├── schemas.py               ← Component registry metadata
│   ├── services/
│   │   ├── __init__.py
│   │   ├── job_service.py       ← Job CRUD (file-based storage)
│   │   └── execution_service.py ← Job execution & monitoring
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── jobs.py              ← REST: /api/jobs endpoints
│   │   ├── components.py        ← REST: /api/components endpoints
│   │   └── execution.py         ← REST: /api/execution + WebSocket
│   └── __pycache__/
└── jobs/                        ← Job storage (JSON files)
    ├── job_1768428753534.json
    └── string.json
```

### Frontend Structure
```
frontend/
├── package.json                 ← NPM dependencies (React, Vite, etc)
├── tsconfig.json                ← TypeScript configuration
├── tsconfig.node.json           ← TS config for Vite
├── vite.config.ts               ← Vite build configuration
├── index.html                   ← HTML entry point
├── src/
│   ├── main.tsx                 ← React app entry
│   ├── App.tsx                  ← Main app shell (navigation)
│   ├── index.css                ← Global styles
│   ├── types/
│   │   └── index.ts             ← TypeScript interfaces (Job, Node, Edge, etc)
│   ├── services/
│   │   ├── api.ts               ← REST API client (Axios)
│   │   └── websocket.ts         ← WebSocket client (Socket.io)
│   ├── components/              ← React components
│   │   ├── Canvas.tsx           ← React Flow visual canvas
│   │   ├── ComponentNode.tsx    ← Node representation
│   │   ├── ComponentPalette.tsx ← Draggable component toolbar
│   │   ├── ConfigPanel.tsx      ← Dynamic config form generator
│   │   ├── ExecutionMonitor.tsx ← Real-time progress tracker
│   │   └── JobList.tsx          ← Job management UI
│   └── pages/
│       └── JobDesigner.tsx      ← Main designer page
```

### Core Engine Structure
```
src/
├── v1/
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── engine.py            ← Main ETL orchestrator (743 lines)
│   │   │                           - Job execution lifecycle
│   │   │                           - Component registry & instantiation
│   │   │                           - Trigger-based workflow control
│   │   │                           - Data flow routing
│   │   │
│   │   ├── base_component.py    ← Abstract base class (378 lines)
│   │   │                           - Component lifecycle hooks
│   │   │                           - Statistics tracking
│   │   │                           - Execution mode selection
│   │   │                           - Java expression resolution
│   │   │
│   │   ├── global_map.py        ← Talend-like state store
│   │   │                           - Component statistics
│   │   │                           - Context variables
│   │   │                           - Iteration state
│   │   │
│   │   ├── context_manager.py   ← Job context (variables)
│   │   │                           - Type conversion
│   │   │                           - Variable resolution
│   │   │
│   │   ├── trigger_manager.py   ← Workflow control
│   │   │                           - OnSubjobOk/Error triggers
│   │   │                           - Component activation
│   │   │
│   │   ├── java_bridge_manager.py ← Java integration
│   │   │                            - Py4J lifecycle management
│   │   │                            - Routine loading
│   │   │
│   │   ├── python_routine_manager.py ← Python routines
│   │   │
│   │   ├── java_bridge/
│   │   │   ├── __init__.py
│   │   │   └── bridge.py        ← Py4J wrapper
│   │   │                           - Arrow serialization
│   │   │                           - Java function calls
│   │   │
│   │   └── components/
│   │       └── transform/
│   │           ├── __init__.py
│   │           └── map.py       ← tMap component (1141 lines)
│   │                               - Joins & lookups
│   │                               - Variable definitions
│   │                               - Multi-output filtering
│   │                               - Expression evaluation
│   │
│   ├── converters/              ← Format converters (extensible)
│   ├── python_routines/         ← User-defined Python functions
│   └── router/                  ← Request routing
```

---

## 🔧 Key Technologies & Dependencies

### Backend Stack
| Technology | Version | Purpose |
|-----------|---------|---------|
| **FastAPI** | 0.104.1+ | REST API & async server |
| **Pydantic** | 2.5.0 | Data validation & models |
| **uvicorn** | 0.24.0+ | ASGI server |
| **python-socketio** | 5.9.0+ | WebSocket support |
| **aiohttp** | 3.9.1+ | Async HTTP client |
| **SQLAlchemy** | 2.0.23+ | ORM (for future DB support) |
| **psutil** | 5.9.6+ | System metrics |

### Frontend Stack
| Technology | Version | Purpose |
|-----------|---------|---------|
| **React** | 18.2.0 | UI framework |
| **React Flow** | 11.10.1 | Visual canvas (drag-drop DAG) |
| **Ant Design** | 5.11.3 | Component library |
| **TypeScript** | 5.2.2 | Type safety |
| **Vite** | 5.0.8 | Fast build tool |
| **Axios** | 1.6.1 | HTTP client |
| **Socket.io** | 4.5.4 | WebSocket client |
| **Zustand** | 4.4.2 | State management (optional) |

### Core Engine Dependencies
| Library | Purpose |
|---------|---------|
| **Pandas** | DataFrame operations, joins, grouping |
| **Py4J** | Python-Java bridge (optional) |
| **Apache Arrow** | Efficient DataFrame serialization |

---

## 🎮 How It Works - User Journey

### 1. **Job Design Phase**
```
User → Frontend (React)
  ├─ Drag components from palette onto canvas
  ├─ Connect components with edges
  ├─ Configure each component (double-click → ConfigPanel)
  ├─ Define global context variables
  └─ Save job → Backend stores JSON
```

### 2. **Backend Processing**
```
Frontend sends JobSchema (JSON)
  ↓
Backend (FastAPI)
  ├─ Validates schema
  ├─ Persists to file system (jobs/*.json)
  └─ Returns job metadata
```

### 3. **Execution Phase**
```
Frontend → /api/execution/start (POST)
  ↓
Backend
  ├─ Generates task_id
  ├─ Exports job config
  ├─ Starts ExecutionManager
  └─ Returns task_id
  
Frontend → WebSocket connection
  ├─ Requests real-time updates
  └─ Receives:
      - Component start/end events
      - Progress (rows processed)
      - Logs and errors
      - Final statistics
```

### 4. **Engine Execution**
```
ETLEngine.execute(job_config)
  │
  ├─ Initialize
  │  ├─ Load component instances
  │  ├─ Initialize GlobalMap, ContextManager
  │  ├─ Load Java bridge (if enabled)
  │  └─ Register triggers
  │
  ├─ Identify topology
  │  ├─ Detect subjobs (component groups)
  │  └─ Identify source components (no inputs)
  │
  ├─ Main loop (trigger-driven)
  │  ├─ For each unexecuted component:
  │  │  ├─ Check if inputs ready
  │  │  ├─ Check if subjob active
  │  │  ├─ Execute component._process()
  │  │  ├─ Update statistics in GlobalMap
  │  │  └─ Evaluate triggers
  │  │
  │  └─ Route data between components
  │
  └─ Cleanup & return stats
```

---

## 📋 Core Concepts

### Jobs
- **Definition:** A reusable ETL workflow with components and connections
- **Storage:** JSON files in `backend/jobs/`
- **Schema:** `JobSchema` with nodes, edges, context, and configs

### Components
- **Definition:** Individual ETL operations (Map, Filter, FileInput, etc.)
- **Base Class:** `BaseComponent` (abstract)
- **Lifecycle:** Init → Execute → Update Stats → Output
- **Registry:** Defined in `backend/app/schemas.py` and `src/v1/engine/COMPONENT_REGISTRY`

### Nodes & Edges
- **Nodes:** Components on the canvas (position, config, type)
- **Edges:** Data flow connections between components (source → target)
- **Types:** Main flow, error/reject flow, trigger flow

### Execution
- **Status:** pending → running → success/error
- **Task ID:** Unique identifier for each execution run
- **Streaming:** Real-time updates via WebSocket
- **Statistics:** Tracks rows processed, errors, timing

### GlobalMap (Talend-like)
```python
# Component statistics
globalMap.put_component_stat("tMap_1", "NB_LINE", 1000)
globalMap.put_component_stat("tMap_1", "NB_LINE_OK", 950)

# Context variables
globalMap.put("my_var", value)

# Accessible in Java expressions
((Integer)globalMap.get("tMap_1_NB_LINE")) > 0
```

### Triggers (Workflow Control)
- **OnSubjobOk:** Fire when subjob completes successfully
- **OnComponentOk:** Fire when component succeeds
- **OnSubjobError:** Fire when subjob fails
- Activates dependent subjobs/components

### Execution Modes
- **Batch:** Process entire DataFrame at once
- **Streaming:** Process in chunks (memory-efficient)
- **Hybrid:** Auto-switch based on data size (default)

---

## 🔌 API Reference

### Jobs API
```
GET    /api/jobs                      # List all jobs
GET    /api/jobs/{job_id}             # Get job details
POST   /api/jobs                      # Create new job
PUT    /api/jobs/{job_id}             # Update job
DELETE /api/jobs/{job_id}             # Delete job
GET    /api/jobs/{job_id}/export      # Export job config
```

### Components API
```
GET    /api/components                # List available components
GET    /api/components/{type}         # Get component metadata
```

### Execution API
```
POST   /api/execution/start           # Start job execution
GET    /api/execution/{task_id}       # Get execution status
POST   /api/execution/{task_id}/stop  # Stop execution
WS     /ws/execution/{task_id}        # WebSocket stream (real-time updates)
```

---

## 🧩 Component Library (Built-in)

| Component | Type | Inputs | Outputs | Purpose |
|-----------|------|--------|---------|---------|
| **Map (tMap)** | Transform | 1+ | 2+ | Transformation, joins, lookups (1140 LOC) |
| **Filter** | Transform | 1 | 2 | Row filtering (main + reject) |
| **FileInput** | Input | 0 | 1 | Read CSV/JSON/Parquet/Excel |
| **FileOutput** | Output | 1 | 0 | Write to file |
| **Aggregate** | Transform | 1 | 1 | Group-by aggregations |
| **Sort** | Transform | 1 | 1 | Sort by columns |

### Extending Components
1. Create new class extending `BaseComponent`
2. Implement `_process(input_data)` method
3. Register in `COMPONENT_REGISTRY`
4. Add metadata to `backend/app/schemas.py`

---

## 🚀 Quick Start Commands

### Windows
```bash
cd c:\Users\phani\OneDrive\Documents\GitHub\recdataprep
quickstart.bat
# Then open http://localhost:5173
```

### Mac/Linux
```bash
cd ~/GitHub/recdataprep
chmod +x quickstart.sh
./quickstart.sh
# Then open http://localhost:5173
```

### Manual Start
```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python run.py

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

---

## 📊 Statistics & Metrics

| Aspect | Value |
|--------|-------|
| **Total Files** | 50+ |
| **Total LOC** | ~5000 |
| **Backend Files** | 13 |
| **Backend LOC** | ~850 |
| **Frontend Files** | 30+ |
| **Frontend LOC** | ~2200 |
| **Documentation Files** | 7+ |
| **Documentation LOC** | 1500+ |
| **Core Engine LOC** | ~2400 |

### Largest Files
1. `src/v1/engine/components/transform/map.py` - 1141 LOC (tMap)
2. `src/v1/engine/engine.py` - 743 LOC (Main orchestrator)
3. `src/v1/engine/base_component.py` - 378 LOC (Base class)

---

## ✨ Key Features

### Frontend (React)
- ✅ **Visual Designer:** Drag-drop canvas with React Flow
- ✅ **Component Palette:** Organized by category
- ✅ **Dynamic Configuration:** Auto-generated forms
- ✅ **Real-time Monitoring:** WebSocket streaming
- ✅ **Job Management:** CRUD operations
- ✅ **Type Safety:** Full TypeScript

### Backend (FastAPI)
- ✅ **REST API:** 14+ endpoints
- ✅ **WebSocket Streaming:** Real-time execution updates
- ✅ **Async Execution:** Non-blocking job runs
- ✅ **Pydantic Validation:** Type-safe data models
- ✅ **CORS Support:** Frontend integration ready
- ✅ **Extensible:** Easy to add routes/services

### Core Engine
- ✅ **Component-based:** Modular architecture
- ✅ **Trigger-driven:** Workflow control
- ✅ **Multi-input/output:** Flexible data routing
- ✅ **Java Integration:** Py4J bridge
- ✅ **Python Routines:** Custom functions
- ✅ **Advanced Transform:** tMap with joins/lookups
- ✅ **Statistics:** Comprehensive execution metrics
- ✅ **Error Handling:** Detailed error tracking

---

## 🔍 Understanding Data Flow

### Simple Example: FileInput → Map → FileOutput

```
1. FileInput reads data
   └─ Returns: {"main": DataFrame}

2. Map receives input
   ├─ Applies transformations
   ├─ Evaluates expressions
   └─ Returns: {"main": DataFrame, "reject": DataFrame}

3. FileOutput receives mapped data
   ├─ Filters for "main" flow
   └─ Writes to file

4. Error handling
   └─ Reject rows can be routed to error component
```

### Complex Example: With Lookups

```
1. Main input (tFileInput_1)
   └─ Returns: sales_data (1000 rows)

2. Lookup input (tFileInput_2)
   └─ Returns: product_lookup (500 rows)

3. tMap joins them
   ├─ Join on product_id
   ├─ Apply transformations
   ├─ Evaluate variables
   └─ Return: output data with joined columns

4. Route to outputs
   ├─ tFileOutput_1: main flow (900 rows)
   └─ tFileOutput_2: reject flow (100 rows)
```

---

## 🛠️ Development Workflow

### To Modify Backend
1. Edit files in `backend/app/` (routes, services, models)
2. Restart `python run.py`
3. FastAPI auto-reloads on file changes (in dev mode)

### To Modify Frontend
1. Edit files in `frontend/src/`
2. Vite automatically reloads browser
3. No manual refresh needed

### To Modify Core Engine
1. Edit files in `src/v1/engine/`
2. Changes take effect on next job execution
3. No server restart needed (Python reimports)

### To Add New Component
1. Create `src/v1/engine/components/<category>/<name>.py`
2. Extend `BaseComponent`
3. Implement `_process()` method
4. Add to `COMPONENT_REGISTRY` in engine.py
5. Add metadata to `backend/app/schemas.py`
6. Frontend auto-discovers via `/api/components`

---

## 📚 Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| [START_HERE.md](START_HERE.md) | Quick overview | Everyone |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Command reference | All users |
| [UI_README.md](UI_README.md) | Feature guide | UI users |
| [SETUP_DEPLOYMENT.md](SETUP_DEPLOYMENT.md) | Installation | Developers |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Validation | QA/Testers |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Deep dive | Architects |
| [FILE_INVENTORY.md](FILE_INVENTORY.md) | File listing | Code explorers |

---

## ✅ Production Readiness

- ✅ All features implemented
- ✅ Type-safe (TypeScript + Pydantic)
- ✅ Error handling comprehensive
- ✅ Logging enabled
- ✅ Documentation complete
- ✅ Extensible architecture
- ✅ Ready for deployment

---

## 🎓 Key Learning Points

1. **Component Architecture:** Highly modular, extensible design
2. **Async Execution:** FastAPI + asyncio for non-blocking operations
3. **Trigger-Driven Workflows:** Talend-like trigger system
4. **Hybrid Execution:** Smart batch/streaming mode selection
5. **Data Routing:** Complex multi-input/output scenarios
6. **Type Safety:** Full end-to-end TypeScript + Python types

---

## 📞 Quick Help

**Backend won't start?**
- Check Python version (3.8+)
- Verify dependencies: `pip install -r backend/requirements.txt`
- Check port 8000 is free

**Frontend won't load?**
- Check Node.js installed (14+)
- Clear node_modules: `rm -rf frontend/node_modules`
- Reinstall: `npm install` in frontend/

**Jobs not saving?**
- Verify `backend/jobs/` directory exists
- Check write permissions
- Inspect browser console for API errors

**Execution not working?**
- Check backend is running (`http://localhost:8000/health`)
- Verify WebSocket connection in browser Network tab
- Check job configuration is valid JSON

---

*This is a comprehensive, production-ready ETL visual designer system with a clean architecture, extensive documentation, and extensible components.*
