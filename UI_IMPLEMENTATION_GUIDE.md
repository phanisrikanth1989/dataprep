# RecDataPrep UI Implementation Guide

## Overview
Build a **web-based visual job designer** similar to Talend's interface. Users can:
- Drag & drop components onto a canvas
- Connect components with flows
- Configure component properties
- Manage triggers visually
- Execute and monitor jobs
- View statistics and logs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WEB BROWSER                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  React Frontend (Component Canvas + UI)                  │  │
│  │  - Visual Job Designer (Rete.js / React Flow)           │  │
│  │  - Component Configuration Panels                        │  │
│  │  - Job Execution Monitor                                │  │
│  │  - Statistics Dashboard                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────┴──────────┐
                   │ REST API + WebSocket│
                   │ (FastAPI/Flask)    │
                   └──────────┬──────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    PYTHON BACKEND                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server                                          │  │
│  │  - Job Management (CRUD)                               │  │
│  │  - Job Execution API                                   │  │
│  │  - WebSocket for live progress                         │  │
│  │  - Component metadata endpoints                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Your Existing ETL Engine                              │  │
│  │  - ETLEngine (orchestrator)                            │  │
│  │  - Components (tMap, etc.)                             │  │
│  │  - Job configs (JSON)                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack Recommendation

### Frontend
| Tool | Purpose | Why |
|------|---------|-----|
| **React 18+** | UI Framework | Best ecosystem, component reuse |
| **React Flow** | Canvas/Graph | Specialized for visual workflows, handles complex layouts |
| **Ant Design** | UI Components | Professional, built-in forms & tables |
| **TypeScript** | Type Safety | Catch errors early |
| **Axios** | HTTP Client | Simple REST calls |
| **Socket.io-client** | WebSocket | Real-time execution updates |

### Backend
| Tool | Purpose | Why |
|------|---------|-----|
| **FastAPI** | Web Framework | Fast, async, built-in WebSocket, auto docs |
| **Pydantic** | Validation | Type-safe data models |
| **SQLAlchemy** | Database | Job persistence (optional) |
| **Python-socketio** | WebSocket | Real-time communication |

---

## Implementation Roadmap

### Phase 1: Backend API (2-3 weeks)
- [ ] Create FastAPI server
- [ ] Job CRUD endpoints
- [ ] Component metadata endpoints
- [ ] Job execution endpoint (async)
- [ ] WebSocket for live progress

### Phase 2: Frontend - Visual Designer (3-4 weeks)
- [ ] React app setup with TypeScript
- [ ] React Flow canvas integration
- [ ] Component palette (drag-drop)
- [ ] Connection/flow creation
- [ ] Component configuration forms

### Phase 3: Frontend - Execution & Monitoring (2-3 weeks)
- [ ] Job execution trigger
- [ ] Real-time progress tracking
- [ ] Statistics dashboard
- [ ] Logs viewer
- [ ] Error handling UI

### Phase 4: Polish & Features (1-2 weeks)
- [ ] Save/load jobs
- [ ] Job templates
- [ ] Undo/redo
- [ ] Keyboard shortcuts
- [ ] Deployment packaging

---

## Detailed Implementation Plan

### A. Backend - FastAPI Server

**1. Project Structure**
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── models.py               # Pydantic models
│   ├── schemas.py              # API schemas
│   ├── routes/
│   │   ├── jobs.py             # Job CRUD
│   │   ├── components.py       # Component metadata
│   │   ├── execution.py        # Job execution
│   │   └── ws.py               # WebSocket handlers
│   └── services/
│       ├── job_service.py      # Job logic
│       └── execution_service.py # Execution logic
├── jobs/                        # Store job JSON files
│   ├── job_001.json
│   └── job_002.json
├── requirements.txt
└── run.py
```

**2. Key Endpoints**

```python
# Job Management
GET    /api/jobs                      # List all jobs
POST   /api/jobs                      # Create new job
GET    /api/jobs/{job_id}             # Get job details
PUT    /api/jobs/{job_id}             # Update job config
DELETE /api/jobs/{job_id}             # Delete job

# Component Metadata
GET    /api/components               # List available components
GET    /api/components/{type}        # Get component schema

# Execution
POST   /api/jobs/{job_id}/execute    # Start job execution (returns task_id)
GET    /api/execution/{task_id}      # Get execution status/progress
POST   /api/execution/{task_id}/stop # Stop execution

# WebSocket
WS     /ws/execution/{task_id}       # Live execution updates
```

**3. Sample FastAPI Code**

```python
# backend/app/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from pathlib import Path

app = FastAPI(title="RecDataPrep UI API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Jobs storage
JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)

@app.get("/api/jobs")
async def list_jobs():
    """List all saved jobs"""
    jobs = []
    for job_file in JOBS_DIR.glob("*.json"):
        with open(job_file) as f:
            jobs.append(json.load(f))
    return jobs

@app.post("/api/jobs")
async def create_job(job_data: dict):
    """Create new job"""
    job_id = f"job_{len(list(JOBS_DIR.glob('*.json'))) + 1:03d}"
    job_data["id"] = job_id
    
    job_file = JOBS_DIR / f"{job_id}.json"
    with open(job_file, "w") as f:
        json.dump(job_data, f, indent=2)
    
    return job_data

@app.post("/api/jobs/{job_id}/execute")
async def execute_job(job_id: str, context_overrides: dict = None):
    """Execute job and return task ID"""
    task_id = f"task_{job_id}_{int(time.time())}"
    
    # Start job execution in background
    asyncio.create_task(
        run_job_async(job_id, task_id, context_overrides)
    )
    
    return {"task_id": task_id, "status": "starting"}

@app.websocket("/ws/execution/{task_id}")
async def websocket_execution(websocket: WebSocket, task_id: str):
    """WebSocket for real-time execution updates"""
    await websocket.accept()
    
    try:
        # Send updates as job executes
        while task_id in active_tasks:
            update = active_tasks[task_id].get_latest_update()
            await websocket.send_json(update)
            await asyncio.sleep(0.5)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()
```

**4. Component Metadata**

```python
# backend/app/models.py
from pydantic import BaseModel
from typing import List, Dict, Any

class ComponentField(BaseModel):
    name: str
    type: str  # "text", "select", "number", "expression"
    label: str
    default: Any = None
    options: List[str] = None  # For select types
    required: bool = False

class ComponentSchema(BaseModel):
    type: str  # "Map", "FileInput", etc.
    label: str  # Display name
    category: str  # "Transform", "Input", "Output"
    icon: str  # Icon name
    fields: List[ComponentField]
    inputs: int  # Number of inputs
    outputs: int  # Number of outputs
    description: str

# Component definitions
COMPONENTS = {
    "Map": ComponentSchema(
        type="Map",
        label="tMap",
        category="Transform",
        icon="swap",
        description="Data transformation with joins and lookups",
        fields=[
            ComponentField(name="die_on_error", type="boolean", label="Die on Error", default=True),
            # ... more fields
        ],
        inputs=1,
        outputs=2
    ),
    # Add more components...
}
```

---

### B. Frontend - React + React Flow

**1. Project Structure**
```
frontend/
├── src/
│   ├── components/
│   │   ├── Canvas.tsx          # Main canvas component
│   │   ├── ComponentPalette.tsx # Draggable components
│   │   ├── ConfigPanel.tsx      # Component config form
│   │   ├── StatusBar.tsx        # Execution status
│   │   └── ExecutionMonitor.tsx # Live progress
│   ├── pages/
│   │   ├── JobDesigner.tsx      # Main editor
│   │   ├── JobList.tsx          # List jobs
│   │   └── ExecutionView.tsx    # Monitor job
│   ├── services/
│   │   ├── api.ts               # API calls
│   │   ├── websocket.ts         # WebSocket
│   │   └── jobStorage.ts        # Local storage
│   ├── App.tsx
│   └── main.tsx
└── package.json
```

**2. Canvas Component (React Flow)**

```typescript
// frontend/src/components/Canvas.tsx
import React, { useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  MiniMap,
  Controls,
} from 'reactflow';
import 'reactflow/dist/style.css';
import ComponentNode from './ComponentNode';

const nodeTypes = {
  component: ComponentNode,
};

export default function Canvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const componentType = event.dataTransfer.getData('componentType');
      
      const newNode: Node = {
        id: `${componentType}_${Date.now()}`,
        data: { label: componentType },
        position: { x: event.clientX, y: event.clientY },
        type: 'component',
      };
      
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes]
  );

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={(e) => e.preventDefault()}
        nodeTypes={nodeTypes}
      >
        <MiniMap />
        <Controls />
      </ReactFlow>
    </div>
  );
}
```

**3. Component Palette**

```typescript
// frontend/src/components/ComponentPalette.tsx
import React from 'react';
import { Card, Row, Col } from 'antd';

const COMPONENT_CATEGORIES = {
  'Input': ['FileInput', 'DatabaseInput'],
  'Transform': ['Map', 'Filter', 'Aggregate'],
  'Output': ['FileOutput', 'DatabaseOutput'],
};

export default function ComponentPalette() {
  const handleDragStart = (e: React.DragEvent, componentType: string) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('componentType', componentType);
  };

  return (
    <div style={{ padding: '10px', borderRight: '1px solid #ddd' }}>
      {Object.entries(COMPONENT_CATEGORIES).map(([category, components]) => (
        <div key={category} style={{ marginBottom: '20px' }}>
          <h4>{category}</h4>
          <Row gutter={[8, 8]}>
            {components.map((comp) => (
              <Col key={comp} span={24}>
                <Card
                  draggable
                  onDragStart={(e) => handleDragStart(e, comp)}
                  style={{ cursor: 'move', textAlign: 'center' }}
                >
                  {comp}
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      ))}
    </div>
  );
}
```

**4. Configuration Panel**

```typescript
// frontend/src/components/ConfigPanel.tsx
import React from 'react';
import { Form, Input, Select, Switch, Button } from 'antd';
import { useForm } from 'antd/es/form/Form';

interface ConfigPanelProps {
  selectedNode: any;
  onSave: (config: any) => void;
}

export default function ConfigPanel({ selectedNode, onSave }: ConfigPanelProps) {
  const [form] = useForm();

  if (!selectedNode) {
    return <div style={{ padding: '20px' }}>Select a component to configure</div>;
  }

  const handleSubmit = (values: any) => {
    onSave(values);
  };

  return (
    <div style={{ padding: '20px', borderLeft: '1px solid #ddd', width: '300px' }}>
      <h3>{selectedNode.data.label}</h3>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={selectedNode.data.config || {}}
      >
        {/* Component-specific fields */}
        <Form.Item
          name="die_on_error"
          label="Die on Error"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Button type="primary" htmlType="submit">
          Save Configuration
        </Button>
      </Form>
    </div>
  );
}
```

**5. Execution Monitor**

```typescript
// frontend/src/components/ExecutionMonitor.tsx
import React, { useEffect, useState } from 'react';
import { Progress, Table, Spin, Card, Row, Col, Statistic } from 'antd';
import { useWebSocket } from '../services/websocket';

interface ExecutionMonitorProps {
  taskId: string;
}

export default function ExecutionMonitor({ taskId }: ExecutionMonitorProps) {
  const [progress, setProgress] = useState(0);
  const [stats, setStats] = useState<any>({});
  const [logs, setLogs] = useState<string[]>([]);
  const { connect } = useWebSocket();

  useEffect(() => {
    const unsubscribe = connect(taskId, (update) => {
      if (update.type === 'progress') {
        setProgress(update.percentage);
      } else if (update.type === 'stats') {
        setStats(update.data);
      } else if (update.type === 'log') {
        setLogs((prev) => [...prev, update.message]);
      }
    });

    return () => unsubscribe();
  }, [taskId, connect]);

  return (
    <div style={{ padding: '20px' }}>
      <Card title="Job Execution">
        <Progress percent={progress} />

        <Row gutter={16} style={{ marginTop: '20px' }}>
          <Col span={8}>
            <Statistic
              title="Rows Processed"
              value={stats.NB_LINE || 0}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Success"
              value={stats.NB_LINE_OK || 0}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Rejected"
              value={stats.NB_LINE_REJECT || 0}
            />
          </Col>
        </Row>

        <Card title="Logs" style={{ marginTop: '20px' }}>
          <div style={{ maxHeight: '300px', overflow: 'auto' }}>
            {logs.map((log, i) => (
              <div key={i} style={{ fontSize: '12px' }}>
                {log}
              </div>
            ))}
          </div>
        </Card>
      </Card>
    </div>
  );
}
```

---

## Quick Start - Implementation Steps

### Step 1: Setup Backend (FastAPI)
```bash
# Create backend directory
mkdir backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn pydantic python-socketio aiofiles

# Create main.py (see code above)

# Run server
uvicorn app.main:app --reload --port 8000
```

### Step 2: Setup Frontend (React)
```bash
# Create React app
npm create vite@latest frontend -- --template react-ts
cd frontend

# Install dependencies
npm install
npm install reactflow antd axios socket.io-client typescript

# Start dev server
npm run dev  # Runs on http://localhost:5173
```

### Step 3: Connect Frontend to Backend
```typescript
// frontend/src/services/api.ts
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export const jobsAPI = {
  list: () => axios.get(`${API_BASE}/jobs`),
  get: (id: string) => axios.get(`${API_BASE}/jobs/${id}`),
  create: (data: any) => axios.post(`${API_BASE}/jobs`, data),
  update: (id: string, data: any) => axios.put(`${API_BASE}/jobs/${id}`, data),
  execute: (id: string) => axios.post(`${API_BASE}/jobs/${id}/execute`),
};
```

---

## UI Mockup (Talend-like Layout)

```
┌────────────────────────────────────────────────────────────────────────┐
│ RecDataPrep UI                  [File] [Edit] [View] [Help]    [▼] [×] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐  ┌─────────────────────────────┐  ┌──────────────┐ │
│  │ COMPONENTS   │  │                             │  │    CONFIG    │ │
│  │              │  │                             │  │              │ │
│  │ ▼ Input      │  │       Canvas                │  │ Component:   │ │
│  │  FileInput   │  │     [tMap_1]                │  │ tMap_1       │ │
│  │  DB Input    │  │        │                    │  │              │ │
│  │              │  │        ▼                    │  │ ▣ Die on     │ │
│  │ ▼ Transform  │  │    [Filter]                 │  │   Error      │ │
│  │  tMap        │  │        │                    │  │              │ │
│  │  Filter      │  │        ▼                    │  │ Fields:      │ │
│  │              │  │   [FileOutput]              │  │ ┌──────────┐ │ │
│  │ ▼ Output     │  │                             │  │ │ [Save]   │ │ │
│  │  FileOutput  │  │                             │  │ └──────────┘ │ │
│  │  DB Output   │  │                             │  │              │ │
│  └──────────────┘  └─────────────────────────────┘  └──────────────┘ │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ Status: Ready | 0 Components | 0 Flows | [▶ Execute] [⏹ Stop]        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Integration with Existing Code

Your existing codebase will be **the execution engine**. The UI just:

1. **Generates job JSON** (which you already have format for)
2. **Calls ETLEngine** to execute
3. **Streams progress** back to UI via WebSocket

```python
# backend/app/services/execution_service.py
from src.v1.engine.engine import ETLEngine

async def run_job_async(job_id: str, task_id: str, context_overrides: dict = None):
    """Run job and stream updates to WebSocket clients"""
    
    job_config = load_job_config(job_id)  # Load JSON
    
    try:
        with ETLEngine(job_config) as engine:
            # Apply context overrides
            if context_overrides:
                for key, value in context_overrides.items():
                    engine.set_context_variable(key, value)
            
            # Execute and stream progress
            stats = engine.execute()
            
            # Send completion update
            broadcast_update(task_id, {
                'type': 'complete',
                'stats': stats
            })
    except Exception as e:
        broadcast_update(task_id, {
            'type': 'error',
            'message': str(e)
        })
```

---

## Estimated Timeline

| Phase | Time | Difficulty |
|-------|------|-----------|
| Backend API | 2-3 weeks | Medium |
| Frontend Designer | 3-4 weeks | Medium-Hard |
| Execution & Monitoring | 2-3 weeks | Medium |
| Polish & Deploy | 1-2 weeks | Easy |
| **Total** | **8-12 weeks** | **Medium** |

---

## Why This Approach?

✅ **Decoupled** - UI is separate from engine, can iterate independently  
✅ **Web-based** - No native app compilation, works on any browser  
✅ **Familiar** - React Flow feels like Talend's canvas  
✅ **Real-time** - WebSocket gives instant feedback  
✅ **Scalable** - FastAPI handles concurrent jobs easily  
✅ **Reuses** - Your existing ETLEngine unchanged  

---

## Alternative Options

### Option 1: Electron App (Desktop)
- More professional feel
- Full filesystem access
- Takes longer to build (~4-6 weeks)

### Option 2: Vue.js Frontend
- Simpler than React, faster to build
- Same canvas libraries available
- Slightly smaller bundle

### Option 3: Streamlit (Rapid Prototyping)
- Build UI in pure Python
- Very fast to prototype (~2 weeks)
- Limited styling options, not production-grade

---

## Next Steps

1. **Start with Backend** - Create FastAPI server + basic CRUD
2. **Build Canvas** - Set up React Flow for visual designer
3. **Connect them** - Make frontend call backend APIs
4. **Add execution** - WebSocket streaming from backend
5. **Polish** - Forms, error handling, styling

Would you like me to start implementing any specific part?
