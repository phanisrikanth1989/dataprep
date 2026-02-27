# RecDataPrep - Code Reference & Development Guide

**For Developers & Architects**  
**Updated:** January 17, 2026

---

## 📚 Table of Contents

1. [Backend Code Structure](#backend-code-structure)
2. [Frontend Code Structure](#frontend-code-structure)
3. [Core Engine Reference](#core-engine-reference)
4. [API Endpoints Reference](#api-endpoints-reference)
5. [Key Type Definitions](#key-type-definitions)
6. [Component Development](#component-development)
7. [Common Patterns](#common-patterns)

---

## Backend Code Structure

### Entry Point: `backend/run.py`

```python
"""
Starts the FastAPI server with uvicorn
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",          # Import path to FastAPI app
        host="0.0.0.0",
        port=8000,
        reload=True,             # Auto-reload on file change
        log_level="info"
    )
```

**Starting the backend:**
```bash
cd backend
python run.py
```

---

### FastAPI App Factory: `backend/app/main.py`

```python
def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="RecDataPrep UI API",
        description="API for RecDataPrep ETL visual designer",
        version="0.1.0",
    )
    
    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            ...
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include route modules
    app.include_router(jobs.router)
    app.include_router(components.router)
    app.include_router(execution.router)
    
    return app
```

**Key Concepts:**
- CORS enabled for frontend (localhost:5173)
- Routes organized into separate modules
- Health check endpoint for monitoring
- Global exception handler for error consistency

---

### Data Models: `backend/app/models.py`

```python
# Pydantic models for type safety and validation

class ComponentFieldType(str, Enum):
    """Field types for component configuration"""
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    EXPRESSION = "expression"
    ARRAY = "array"

class ComponentFieldSchema(BaseModel):
    """Schema for a single configuration field"""
    name: str
    type: ComponentFieldType
    label: str
    description: Optional[str] = None
    default: Optional[Any] = None
    required: bool = False
    options: Optional[List[str]] = None
    placeholder: Optional[str] = None

class ComponentMetadata(BaseModel):
    """Metadata describing a component type"""
    type: str
    label: str
    category: str  # "Input", "Transform", "Output"
    icon: str
    description: str
    fields: List[ComponentFieldSchema]
    input_count: int
    output_count: int
    allow_multiple_inputs: bool = False

class JobNode(BaseModel):
    """Node representing a component on the canvas"""
    id: str
    type: str  # Component type (e.g., "Map", "Filter")
    label: str
    x: int      # Canvas X position
    y: int      # Canvas Y position
    config: Dict[str, Any]  # Component-specific configuration

class JobEdge(BaseModel):
    """Edge representing data flow between components"""
    id: str
    source: str  # Source component ID
    target: str  # Target component ID
    edge_type: str  # "main", "reject", "error", "trigger"
    name: Optional[str] = None  # Data flow name

class JobSchema(BaseModel):
    """Complete job definition"""
    id: str
    name: str
    description: Optional[str] = None
    nodes: List[JobNode]
    edges: List[JobEdge]
    context: Dict[str, Any] = {}  # Global context variables
    java_config: Dict[str, Any] = {}
    python_config: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ExecutionStatus(BaseModel):
    """Track execution progress"""
    task_id: str
    job_id: str
    status: str  # "pending", "running", "success", "error"
    progress: int = 0  # 0-100
    started_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[str] = []
    stats: Optional[Dict[str, Any]] = None
```

---

### Component Registry: `backend/app/schemas.py`

```python
COMPONENT_REGISTRY: dict = {
    "Map": ComponentMetadata(
        type="Map",
        label="tMap",
        category="Transform",
        icon="swap",
        description="Data transformation with joins/lookups",
        fields=[
            ComponentFieldSchema(
                name="die_on_error",
                type=ComponentFieldType.BOOLEAN,
                label="Die on Error",
                description="Stop job if error occurs",
                default=True,
            ),
            ComponentFieldSchema(
                name="execution_mode",
                type=ComponentFieldType.SELECT,
                label="Execution Mode",
                options=["batch", "streaming", "hybrid"],
                default="hybrid",
            ),
        ],
        input_count=1,
        output_count=2,
        allow_multiple_inputs=True,
    ),
    
    "Filter": ComponentMetadata(
        # ... filter configuration
    ),
    
    # ... more components
}

# Access in routes
@router.get("/{component_type}")
async def get_component_metadata(component_type: str):
    if component_type not in COMPONENT_REGISTRY:
        raise HTTPException(status_code=404)
    return COMPONENT_REGISTRY[component_type]
```

**How to Add a New Component:**
1. Define ComponentMetadata in COMPONENT_REGISTRY
2. Create corresponding component class in `src/v1/engine/components/`
3. Register in engine's COMPONENT_REGISTRY
4. Frontend auto-discovers via `/api/components`

---

### Job Service: `backend/app/services/job_service.py`

```python
class JobService:
    """Service for job persistence and management"""
    
    def __init__(self, jobs_dir: str = "jobs"):
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(exist_ok=True)
    
    def create_job(self, job: JobSchema) -> JobSchema:
        """Persist new job to file"""
        job.created_at = datetime.utcnow().isoformat()
        job.updated_at = job.created_at
        
        job_path = self._get_job_path(job.id)
        with open(job_path, "w") as f:
            f.write(job.model_dump_json(indent=2))
        
        logger.info(f"Created job: {job.id}")
        return job
    
    def get_job(self, job_id: str) -> Optional[JobSchema]:
        """Load job from file"""
        job_path = self._get_job_path(job_id)
        if not job_path.exists():
            return None
        
        with open(job_path) as f:
            data = json.load(f)
        return JobSchema(**data)
    
    def export_job_config(self, job_id: str) -> dict:
        """
        Convert JobSchema to engine-compatible config
        Transform visual job → execution config
        """
        job = self.get_job(job_id)
        if not job:
            return None
        
        return {
            "job_name": job.name,
            "job_id": job.id,
            "nodes": [node.model_dump() for node in job.nodes],
            "edges": [edge.model_dump() for edge in job.edges],
            "context": job.context,
            "java_config": job.java_config,
            "python_config": job.python_config,
        }
```

**Key Methods:**
- `create_job()` - Persist new job
- `get_job()` - Load job by ID
- `list_jobs()` - Get all jobs
- `update_job()` - Update existing job
- `delete_job()` - Remove job
- `export_job_config()` - Convert to engine config

---

### Execution Service: `backend/app/services/execution_service.py`

```python
class ExecutionManager:
    """Manages active job executions"""
    
    def __init__(self):
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.callbacks: Dict[str, list] = {}
    
    def create_execution(self, job_id: str, task_id: str) -> ExecutionStatus:
        """Create new execution tracking"""
        execution = ExecutionStatus(
            task_id=task_id,
            job_id=job_id,
            status="pending",
            started_at=datetime.utcnow().isoformat(),
        )
        self.executions[task_id] = execution.model_dump()
        self.callbacks[task_id] = []
        return execution
    
    async def execute_job(
        self,
        task_id: str,
        job_config: dict,
        context_overrides: Optional[dict] = None,
    ) -> ExecutionStatus:
        """Execute job asynchronously"""
        try:
            self.update_execution(task_id, status="running")
            
            # Import and create engine
            from v1.engine.engine import ETLEngine
            engine = ETLEngine(job_config)
            
            # Execute
            results = engine.execute(
                context_overrides=context_overrides
            )
            
            # Update status
            self.update_execution(
                task_id,
                status="success",
                stats=results.get("stats"),
                completed_at=datetime.utcnow().isoformat(),
            )
            
        except Exception as e:
            self.update_execution(
                task_id,
                status="error",
                error_message=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )
    
    def subscribe(self, task_id: str, callback: Callable):
        """Subscribe to execution updates"""
        if task_id not in self.callbacks:
            self.callbacks[task_id] = []
        self.callbacks[task_id].append(callback)
    
    def update_execution(self, task_id: str, **kwargs) -> Optional[ExecutionStatus]:
        """Update execution and notify subscribers"""
        if task_id not in self.executions:
            return None
        
        self.executions[task_id].update(kwargs)
        execution = ExecutionStatus(**self.executions[task_id])
        
        # Notify all subscribers
        for callback in self.callbacks[task_id]:
            try:
                callback(execution)
            except Exception as e:
                logger.error(f"Error in execution callback: {e}")
        
        return execution

# Global instance (singleton)
execution_manager = ExecutionManager()
```

**Execution Flow:**
1. Frontend calls `/api/execution/start`
2. `ExecutionManager.create_execution()` creates task
3. `ETLEngine.execute()` runs asynchronously
4. Updates propagate to subscribers
5. Frontend receives updates via WebSocket

---

### Routes: Job Management (`backend/app/routes/jobs.py`)

```python
router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.get("")
async def list_jobs():
    """GET /api/jobs - List all jobs"""
    jobs = job_service.list_jobs()
    return [{
        "id": job.id,
        "name": job.name,
        "description": job.description,
        "node_count": len(job.nodes),
        "edge_count": len(job.edges),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    } for job in jobs]

@router.get("/{job_id}")
async def get_job(job_id: str):
    """GET /api/jobs/{job_id} - Get full job definition"""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("")
async def create_job(job_data: JobSchema):
    """POST /api/jobs - Create new job"""
    created_job = job_service.create_job(job_data)
    return created_job

@router.put("/{job_id}")
async def update_job(job_id: str, job_data: JobSchema):
    """PUT /api/jobs/{job_id} - Update job"""
    updated_job = job_service.update_job(job_id, job_data)
    if not updated_job:
        raise HTTPException(status_code=404, detail="Job not found")
    return updated_job

@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """DELETE /api/jobs/{job_id} - Delete job"""
    success = job_service.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully"}

@router.get("/{job_id}/export")
async def export_job_config(job_id: str):
    """GET /api/jobs/{job_id}/export - Export job config for engine"""
    config = job_service.export_job_config(job_id)
    if not config:
        raise HTTPException(status_code=404, detail="Job not found")
    return config
```

---

### Routes: Execution (`backend/app/routes/execution.py`)

```python
@router.post("/start")
async def start_execution(request: ExecutionRequest):
    """POST /api/execution/start - Start job execution"""
    job = job_service.get_job(request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    execution_manager.create_execution(request.job_id, task_id)
    
    job_config = job_service.export_job_config(request.job_id)
    
    # Start async execution
    asyncio.create_task(
        execution_manager.execute_job(
            task_id, job_config, request.context_overrides
        )
    )
    
    return {
        "task_id": task_id,
        "job_id": request.job_id,
        "status": "started",
    }

@router.get("/{task_id}")
async def get_execution_status(task_id: str):
    """GET /api/execution/{task_id} - Get execution status"""
    execution = execution_manager.get_execution(task_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket /ws/{task_id} - Real-time execution updates"""
    await websocket.accept()
    
    async def send_update(execution: ExecutionStatus):
        try:
            await websocket.send_json(execution.model_dump())
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
    
    # Subscribe to updates
    execution_manager.subscribe(task_id, send_update)
    
    # Send current status
    execution = execution_manager.get_execution(task_id)
    if execution:
        await websocket.send_json(execution.model_dump())
    
    # Keep connection alive
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {task_id}")
```

---

## Frontend Code Structure

### Entry Point: `frontend/src/main.tsx`

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

---

### App Shell: `frontend/src/App.tsx`

```typescript
const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<'list' | 'designer' | 'execution'>('list')
  const [selectedJobId, setSelectedJobId] = useState<string | undefined>()
  const [executionTaskId, setExecutionTaskId] = useState<string | undefined>()

  const handleJobSelect = (jobId: string) => {
    setSelectedJobId(jobId)
    setCurrentPage('designer')
  }

  const handleJobExecute = async (jobId: string) => {
    try {
      const { executionAPI } = await import('./services/api')
      const response = await executionAPI.start(jobId)
      setExecutionTaskId(response.data.task_id)
      setCurrentPage('execution')
    } catch (error) {
      message.error('Error starting job execution')
    }
  }

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Layout.Header>
        <div>RecDataPrep - ETL Visual Designer</div>
        {currentPage !== 'list' && (
          <Button onClick={() => setCurrentPage('list')}>
            Back to Jobs
          </Button>
        )}
      </Layout.Header>

      <Layout.Content>
        {currentPage === 'list' && (
          <JobList
            onJobSelect={handleJobSelect}
            onJobExecute={handleJobExecute}
          />
        )}

        {currentPage === 'designer' && selectedJobId && (
          <JobDesigner jobId={selectedJobId} />
        )}

        {currentPage === 'execution' && executionTaskId && (
          <ExecutionMonitor taskId={executionTaskId} />
        )}
      </Layout.Content>
    </Layout>
  )
}
```

---

### Type Definitions: `frontend/src/types/index.ts`

```typescript
export interface JobNode {
  id: string
  type: string              // Component type
  label: string
  x: number                 // Canvas position
  y: number
  config: Record<string, any>
  subjob_id?: string
  is_subjob_start?: boolean
}

export interface JobEdge {
  id: string
  source: string            // Source node ID
  target: string            // Target node ID
  edge_type: string         // "main", "reject", "trigger"
  name?: string
  trigger_type?: string
  condition?: string
}

export interface JobSchema {
  id: string
  name: string
  description?: string
  nodes: JobNode[]
  edges: JobEdge[]
  context: Record<string, any>
  java_config: Record<string, any>
  python_config: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface ComponentMetadata {
  type: string
  label: string
  category: string
  icon: string
  description: string
  fields: ComponentField[]
  input_count: number
  output_count: number
  allow_multiple_inputs?: boolean
}

export interface ExecutionStatus {
  task_id: string
  job_id: string
  status: 'pending' | 'running' | 'success' | 'error'
  progress: number
  started_at: string
  completed_at?: string
  error_message?: string
  logs: string[]
  stats?: Record<string, any>
}
```

---

### API Service: `frontend/src/services/api.ts`

```typescript
import axios, { AxiosInstance } from 'axios'
import { JobSchema, ExecutionStatus } from '../types'

const API_BASE = 'http://localhost:8000/api'

const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const jobsAPI = {
  list: () => axiosInstance.get<JobSchema[]>('/jobs'),
  get: (jobId: string) => axiosInstance.get<JobSchema>(`/jobs/${jobId}`),
  create: (job: JobSchema) => axiosInstance.post<JobSchema>('/jobs', job),
  update: (jobId: string, job: JobSchema) => 
    axiosInstance.put<JobSchema>(`/jobs/${jobId}`, job),
  delete: (jobId: string) => axiosInstance.delete(`/jobs/${jobId}`),
  export: (jobId: string) => axiosInstance.get(`/jobs/${jobId}/export`),
}

export const componentsAPI = {
  list: () => axiosInstance.get('/components'),
  get: (type: string) => axiosInstance.get(`/components/${type}`),
}

export const executionAPI = {
  start: (jobId: string, overrides?: Record<string, any>) =>
    axiosInstance.post('/execution/start', {
      job_id: jobId,
      context_overrides: overrides,
    }),
  getStatus: (taskId: string) =>
    axiosInstance.get<ExecutionStatus>(`/execution/${taskId}`),
  stop: (taskId: string) =>
    axiosInstance.post(`/execution/${taskId}/stop`),
}
```

---

### WebSocket Service: `frontend/src/services/websocket.ts`

```typescript
import io, { Socket } from 'socket.io-client'
import { ExecutionStatus } from '../types'

export class ExecutionWebSocket {
  private socket: Socket | null = null
  private taskId: string = ''

  connect(taskId: string, onUpdate: (status: ExecutionStatus) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.taskId = taskId
        this.socket = io('http://localhost:8000', {
          path: `/ws/execution/${taskId}`,
          transports: ['websocket', 'polling'],
        })

        this.socket.on('connect', () => {
          console.log('WebSocket connected')
          resolve()
        })

        this.socket.on('update', (data: ExecutionStatus) => {
          onUpdate(data)
        })

        this.socket.on('error', (error) => {
          reject(error)
        })
      } catch (error) {
        reject(error)
      }
    })
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
  }
}
```

---

### Job Designer Page: `frontend/src/pages/JobDesigner.tsx`

```typescript
const JobDesigner: React.FC<JobDesignerProps> = ({ jobId, onExecute }) => {
  const [job, setJob] = useState<JobSchema | null>(null)
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  useEffect(() => {
    if (jobId) {
      loadJob(jobId)
    }
  }, [jobId])

  const loadJob = async (id: string) => {
    try {
      const response = await jobsAPI.get(id)
      const loadedJob = response.data

      // Convert JobSchema → React Flow nodes/edges
      const flowNodes = loadedJob.nodes.map((node) => ({
        id: node.id,
        data: { label: node.type },
        position: { x: node.x, y: node.y },
        type: 'component',
      }))

      const flowEdges = loadedJob.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.name,
      }))

      setJob(loadedJob)
      setNodes(flowNodes)
      setEdges(flowEdges)
    } catch (error) {
      message.error('Error loading job')
    }
  }

  const saveJob = async () => {
    // Convert React Flow → JobSchema
    const jobData: JobSchema = {
      id: job!.id,
      name: job!.name,
      nodes: nodes.map((node) => ({
        id: node.id,
        type: node.data.label,
        label: node.data.label,
        x: node.position.x,
        y: node.position.y,
        config: job!.nodes.find((n) => n.id === node.id)?.config || {},
      })),
      edges: edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        edge_type: 'main',
        name: edge.label,
      })),
      context: job!.context,
      java_config: job!.java_config,
      python_config: job!.python_config,
    }

    try {
      await jobsAPI.update(job!.id, jobData)
      message.success('Job saved')
    } catch (error) {
      message.error('Error saving job')
    }
  }

  return (
    <Layout>
      <Layout.Sider width={250}>
        <ComponentPalette />
      </Layout.Sider>

      <Layout.Content>
        <Canvas
          nodes={nodes}
          edges={edges}
          onNodesChange={setNodes}
          onEdgesChange={setEdges}
          onNodeSelect={setSelectedNode}
        />
      </Layout.Content>

      <Layout.Sider width={300}>
        {selectedNode && <ConfigPanel node={selectedNode} />}
      </Layout.Sider>
    </Layout>
  )
}
```

---

### Canvas Component: `frontend/src/components/Canvas.tsx`

```typescript
import { ReactFlow, MiniMap, Controls, Background } from 'reactflow'
import 'reactflow/dist/style.css'

const Canvas: React.FC<CanvasProps> = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeSelect,
}) => {
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={(event, node) => onNodeSelect(node)}
      onPaneClick={() => onNodeSelect(null)}
    >
      <Background color="#aaa" gap={16} />
      <Controls />
      <MiniMap />
    </ReactFlow>
  )
}
```

---

### Execution Monitor: `frontend/src/components/ExecutionMonitor.tsx`

```typescript
const ExecutionMonitor: React.FC<{ taskId: string }> = ({ taskId }) => {
  const [status, setStatus] = useState<ExecutionStatus | null>(null)
  const wsRef = useRef<ExecutionWebSocket | null>(null)

  useEffect(() => {
    wsRef.current = new ExecutionWebSocket()
    wsRef.current.connect(taskId, (update) => {
      setStatus(update)
    })

    return () => {
      wsRef.current?.disconnect()
    }
  }, [taskId])

  if (!status) return <Spin />

  return (
    <div>
      <Progress percent={status.progress} />
      <Timeline>
        {status.logs.map((log, i) => (
          <Timeline.Item key={i}>{log}</Timeline.Item>
        ))}
      </Timeline>
      {status.status === 'success' && (
        <Result
          status="success"
          title="Execution Complete"
          subTitle={`Total time: ${status.stats?.total_time}s`}
        />
      )}
    </div>
  )
}
```

---

## Core Engine Reference

### Engine Orchestrator: `src/v1/engine/engine.py`

**Key Methods:**

```python
class ETLEngine:
    def __init__(self, job_config: Dict[str, Any]):
        """Initialize with job configuration"""
        # Load config
        # Initialize bridges (Java, Python)
        # Create managers (GlobalMap, ContextManager, TriggerManager)
    
    def execute(self, context_overrides: Optional[Dict] = None) -> Dict[str, Any]:
        """Main execution orchestrator"""
        # 1. Initialize engine
        # 2. Identify topology (DAG)
        # 3. Execute components in order
        # 4. Evaluate triggers
        # 5. Collect statistics
        # 6. Return results
    
    def _initialize_engine(self):
        """Setup engine state"""
        # Load components from config
        # Initialize GlobalMap
        # Initialize ContextManager
        # Initialize TriggerManager
    
    def _identify_topology(self):
        """Detect DAG structure"""
        # Identify subjobs (connected components)
        # Identify source components (no inputs)
        # Detect cycles (validate DAG)
    
    def _execute_component(self, component_id: str, input_data: Any) -> Dict[str, Any]:
        """Execute single component"""
        # Get component instance
        # Call component.execute(input_data)
        # Update stats
        # Emit execution event
        # Return output
```

---

### Base Component: `src/v1/engine/base_component.py`

```python
class BaseComponent(ABC):
    """Abstract base for all ETL components"""
    
    def execute(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Public interface for component execution
        
        Returns:
            {
                "main": output_dataframe,
                "reject": error_dataframe,
                "stats": {
                    "NB_LINE": 1000,
                    "NB_LINE_OK": 950,
                    "NB_LINE_REJECT": 50,
                    "EXECUTION_TIME": 0.23
                }
            }
        """
        self.status = ComponentStatus.RUNNING
        start_time = time.time()
        
        try:
            # Resolve expressions
            self.config = self._resolve_expressions(self.config)
            
            # Process
            result = self._process(input_data)
            
            # Update stats
            self.stats["EXECUTION_TIME"] = time.time() - start_time
            self._update_global_map()
            
            self.status = ComponentStatus.SUCCESS
            result["stats"] = self.stats
            return result
            
        except Exception as e:
            self.status = ComponentStatus.ERROR
            self.error_message = str(e)
            raise
    
    @abstractmethod
    def _process(self, input_data: Any) -> Dict[str, pd.DataFrame]:
        """
        Component-specific implementation
        Must be implemented by subclasses
        """
        pass
    
    def _update_global_map(self):
        """Update global statistics"""
        if self.global_map:
            self.global_map.put_component_stat(
                self.id, "NB_LINE", self.stats.get("NB_LINE", 0)
            )
            self.global_map.put_component_stat(
                self.id, "NB_LINE_OK", self.stats.get("NB_LINE_OK", 0)
            )
```

---

### GlobalMap: `src/v1/engine/global_map.py`

```python
class GlobalMap:
    """Talend-like global state store"""
    
    def put(self, key: str, value: Any):
        """Store value in global map"""
        self.store[key] = value
    
    def get(self, key: str) -> Any:
        """Retrieve value from global map"""
        return self.store.get(key)
    
    def put_component_stat(self, component_id: str, stat_name: str, value: Any):
        """Store component statistic"""
        key = f"{component_id}_{stat_name}"
        self.put(key, value)
    
    def get_component_stat(self, component_id: str, stat_name: str) -> Any:
        """Retrieve component statistic"""
        key = f"{component_id}_{stat_name}"
        return self.get(key)
```

**Common Statistics:**
- `NB_LINE`: Total rows processed
- `NB_LINE_OK`: Successful rows
- `NB_LINE_REJECT`: Rejected/failed rows
- `EXECUTION_TIME`: Component execution time

---

### Context Manager: `src/v1/engine/context_manager.py`

```python
class ContextManager:
    """Manage job context variables"""
    
    def set_variable(self, name: str, value: Any, var_type: str = "String"):
        """Set context variable"""
        self.variables[name] = {
            "value": value,
            "type": var_type
        }
    
    def resolve_string(self, template: str) -> str:
        """Replace ${context.var} with actual values"""
        # Find all ${context.*} patterns
        # Replace with values from context
        return resolved_string
    
    def resolve_dict(self, config: Dict) -> Dict:
        """Recursively resolve all context variables in dict"""
        # Iterate through dict values
        # Replace any ${context.var} strings
        return resolved_dict
```

---

### Trigger Manager: `src/v1/engine/trigger_manager.py`

```python
class TriggerManager:
    """Manage workflow triggers"""
    
    def register_trigger(
        self,
        source_component: str,
        trigger_type: str,    # "OnComponentOk", "OnSubjobError"
        target: str,
        condition: Optional[str] = None
    ):
        """Register trigger relationship"""
        # Store trigger mapping
    
    def evaluate_triggers(self, component_id: str, status: ComponentStatus):
        """Evaluate applicable triggers after component execution"""
        # Find all triggers for this component
        # Check conditions
        # Return list of activated components
```

---

## API Endpoints Reference

### Jobs Endpoints

| Method | Endpoint | Request | Response | Purpose |
|--------|----------|---------|----------|---------|
| GET | `/api/jobs` | - | `JobSchema[]` | List all jobs |
| GET | `/api/jobs/{id}` | - | `JobSchema` | Get job details |
| POST | `/api/jobs` | `JobSchema` | `JobSchema` | Create job |
| PUT | `/api/jobs/{id}` | `JobSchema` | `JobSchema` | Update job |
| DELETE | `/api/jobs/{id}` | - | `{message}` | Delete job |
| GET | `/api/jobs/{id}/export` | - | `dict` | Export for engine |

### Components Endpoints

| Method | Endpoint | Response | Purpose |
|--------|----------|----------|---------|
| GET | `/api/components` | `ComponentMetadata[]` | List all components |
| GET | `/api/components/{type}` | `ComponentMetadata` | Get component metadata |

### Execution Endpoints

| Method | Endpoint | Request | Response | Purpose |
|--------|----------|---------|----------|---------|
| POST | `/api/execution/start` | `{job_id}` | `{task_id}` | Start execution |
| GET | `/api/execution/{task_id}` | - | `ExecutionStatus` | Get status |
| POST | `/api/execution/{task_id}/stop` | - | `{message}` | Stop execution |
| WS | `/ws/{task_id}` | - | Stream | Real-time updates |

---

## Key Type Definitions

### Request/Response Models

```typescript
// Backend expects
interface ExecutionRequest {
  job_id: string
  context_overrides?: Record<string, any>
}

// Backend returns
interface ExecutionResponse {
  task_id: string
  job_id: string
  status: string
}

// WebSocket streaming
interface ExecutionUpdate {
  task_id: string
  status: string
  progress: number
  logs: string[]
  stats?: Record<string, any>
  error_message?: string
}
```

---

## Component Development

### Creating a New Component

**Step 1: Define in Backend Registry**

```python
# backend/app/schemas.py

"MyComponent": ComponentMetadata(
    type="MyComponent",
    label="My Custom Component",
    category="Transform",
    icon="my-icon",
    description="Does something useful",
    fields=[
        ComponentFieldSchema(
            name="param1",
            type=ComponentFieldType.TEXT,
            label="Parameter 1",
            required=True,
        ),
    ],
    input_count=1,
    output_count=2,
),
```

**Step 2: Create Component Class**

```python
# src/v1/engine/components/transform/my_component.py

from ..base_component import BaseComponent, ComponentStatus
import pandas as pd

class MyComponent(BaseComponent):
    """My custom transformation component"""
    
    def _process(self, input_data: pd.DataFrame) -> dict:
        """
        Process input data
        
        Args:
            input_data: DataFrame or dict of DataFrames
        
        Returns:
            {
                "main": processed_df,
                "reject": error_df,
            }
        """
        try:
            output = input_data.copy()
            
            # Apply your logic here
            param1 = self.config.get("param1", "default")
            # ... transformation logic ...
            
            # Update statistics
            self.stats["NB_LINE"] = len(input_data)
            self.stats["NB_LINE_OK"] = len(output)
            self.stats["NB_LINE_REJECT"] = len(input_data) - len(output)
            
            return {
                "main": output,
                "reject": error_rows,
            }
            
        except Exception as e:
            logger.exception(f"Error in {self.id}: {e}")
            raise
```

**Step 3: Register in Engine**

```python
# src/v1/engine/engine.py

COMPONENT_REGISTRY = {
    # ... existing components ...
    'MyComponent': MyComponent,
}
```

**Step 4: Frontend Auto-Discovery**

The frontend will automatically discover your component via `/api/components` endpoint. Create a node by dragging the component from the palette.

---

## Common Patterns

### Pattern 1: Input Data Handling

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    """Handle various input data formats"""
    
    # Single DataFrame
    if isinstance(input_data, pd.DataFrame):
        main_df = input_data
    
    # Dict of DataFrames (multiple inputs)
    elif isinstance(input_data, dict):
        main_df = input_data.get("main")
        lookup_df = input_data.get("lookup")
    
    # No input (source component)
    elif input_data is None:
        main_df = pd.DataFrame()
    
    # Process...
    return {"main": output}
```

### Pattern 2: Error Handling

```python
def _process(self, input_data: pd.DataFrame) -> dict:
    """Separate valid and error rows"""
    
    success_rows = []
    error_rows = []
    
    for idx, row in input_data.iterrows():
        try:
            # Process row
            processed = self._process_row(row)
            success_rows.append(processed)
        except Exception as e:
            # Capture error row
            row['ERROR'] = str(e)
            error_rows.append(row)
    
    success_df = pd.DataFrame(success_rows) if success_rows else pd.DataFrame()
    error_df = pd.DataFrame(error_rows) if error_rows else pd.DataFrame()
    
    self.stats["NB_LINE"] = len(input_data)
    self.stats["NB_LINE_OK"] = len(success_df)
    self.stats["NB_LINE_REJECT"] = len(error_df)
    
    return {
        "main": success_df,
        "reject": error_df,
    }
```

### Pattern 3: Expression Resolution

```python
def _resolve_expressions(self, config: dict) -> dict:
    """Resolve Java/Python expressions in config"""
    
    for key, value in config.items():
        if isinstance(value, str):
            # Resolve {{java}} expressions
            if value.startswith("{{java}}"):
                resolved = self.java_bridge.evaluate(value[8:-2])
                config[key] = resolved
            
            # Resolve ${context.var} variables
            elif value.startswith("${context"):
                resolved = self.context_manager.resolve_string(value)
                config[key] = resolved
    
    return config
```

### Pattern 4: Pandas Joins

```python
def _process(self, input_data: dict) -> dict:
    """Join main input with lookup"""
    
    main_df = input_data.get("main")
    lookup_df = input_data.get("lookup")
    
    # Join configuration
    join_keys = self.config.get("join_keys", ["id"])
    join_type = self.config.get("join_type", "left")
    
    # Perform join
    result = main_df.merge(
        lookup_df,
        on=join_keys,
        how=join_type,
        suffixes=("", "_lookup")
    )
    
    return {"main": result}
```

---

## Development Workflow

### Local Development

```bash
# Backend
cd backend
python run.py  # Auto-reloads on file change

# Frontend (new terminal)
cd frontend
npm run dev    # Auto-reloads on file change

# Open browser
http://localhost:5173
```

### Adding a Feature

1. **Backend API:** Add endpoint in `backend/app/routes/`
2. **Frontend Service:** Add API call in `frontend/src/services/api.ts`
3. **Frontend Component:** Create component in `frontend/src/components/`
4. **Testing:** Use browser DevTools & API documentation

### Debugging

**Backend:**
```python
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Debug info: {variable}")
```

**Frontend:**
```typescript
console.log("Debug info:", variable)
console.error("Error:", error)
```

---

*This is a comprehensive code reference for the RecDataPrep system. Use this guide when developing new features or components.*
