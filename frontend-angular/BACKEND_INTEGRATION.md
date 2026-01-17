# Backend Integration Reference - Angular Frontend

**Complete Mapping of Frontend Services to Backend API**

---

## 🔗 API Endpoint Mapping

### Job Management Endpoints

#### 1. List All Jobs
```typescript
// Service
this.apiService.listJobs()

// HTTP
GET /api/jobs

// Frontend Usage
this.jobService.loadJobs()

// TypeScript Response
JobListResponse {
  jobs: JobSchema[]
  total: number
  page: number
}

// Component Usage
ngOnInit() {
  this.jobService.getJobs().subscribe(jobs => {
    this.jobsList = jobs;
  });
}
```

#### 2. Get Specific Job
```typescript
// Service
this.apiService.getJob(jobId: string)

// HTTP
GET /api/jobs/{jobId}

// Frontend Usage
this.jobService.loadJob(jobId)

// TypeScript Response
JobSchema {
  id: string
  name: string
  description?: string
  nodes: JobNode[]
  edges: JobEdge[]
  components: Record<string, ComponentMetadata>
  metadata: Record<string, any>
}

// Component Usage
ngOnInit() {
  const jobId = this.route.params['jobId'];
  this.jobService.loadJob(jobId).subscribe(job => {
    this.currentJob = job;
  });
}
```

#### 3. Create New Job
```typescript
// Service
this.apiService.createJob(job: JobSchema)

// HTTP
POST /api/jobs
Content-Type: application/json

// Request Body
{
  "name": "Data Processing",
  "description": "Clean and transform raw data",
  "nodes": [],
  "edges": []
}

// Frontend Usage
this.jobService.createJob(jobConfig)

// TypeScript Response
JobSchema {
  id: string (auto-generated)
  name: string
  created_at: string
  updated_at: string
}

// Component Usage
createJob(name: string) {
  const newJob: JobSchema = {
    id: uuid(),
    name: name,
    nodes: [],
    edges: []
  };
  this.jobService.createJob(newJob).subscribe(
    (job) => {
      this.router.navigate(['/designer', job.id]);
    }
  );
}
```

#### 4. Update Job
```typescript
// Service
this.apiService.updateJob(jobId: string, job: JobSchema)

// HTTP
PUT /api/jobs/{jobId}
Content-Type: application/json

// Request Body
{
  "id": "job_123",
  "name": "Updated Name",
  "nodes": [...],
  "edges": [...]
}

// Frontend Usage
this.jobService.updateJob(jobId, updatedConfig)

// TypeScript Response
JobSchema (updated)

// Component Usage
saveJob() {
  this.jobService.updateJob(
    this.currentJob.id,
    this.currentJob
  ).subscribe();
}
```

#### 5. Delete Job
```typescript
// Service
this.apiService.deleteJob(jobId: string)

// HTTP
DELETE /api/jobs/{jobId}

// Frontend Usage
this.jobService.deleteJob(jobId)

// TypeScript Response
{ success: true }

// Component Usage
deleteJob(jobId: string) {
  this.jobService.deleteJob(jobId).subscribe(
    () => {
      this.loadJobs();
    }
  );
}
```

#### 6. Export Job
```typescript
// Service
this.apiService.exportJob(jobId: string)

// HTTP
GET /api/jobs/{jobId}/export

// Frontend Usage
this.jobService.exportJob(jobId)

// TypeScript Response
Blob (JSON file)

// Component Usage
exportJob(jobId: string) {
  this.jobService.exportJob(jobId).subscribe((blob) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'job.json';
    link.click();
  });
}
```

---

### Component Registry Endpoints

#### 1. List All Components
```typescript
// Service
this.apiService.listComponents()

// HTTP
GET /api/components

// Frontend Usage
this.componentRegistry.getComponents()

// TypeScript Response
ComponentsResponse {
  components: Record<string, ComponentMetadata>
  categories: string[]
}

// Component Usage
ngOnInit() {
  this.componentRegistry.getComponents().subscribe(
    (components) => {
      this.paletteItems = components;
    }
  );
}
```

#### 2. Get Specific Component
```typescript
// Service
this.apiService.getComponent(componentType: string)

// HTTP
GET /api/components/{componentType}

// Frontend Usage
this.componentRegistry.getComponent(type)

// TypeScript Response
ComponentMetadata {
  type: string
  label: string
  category: string
  icon: string
  description: string
  fields: ComponentField[]
  inputs: Record<string, any>
  outputs: Record<string, any>
}

// Component Usage
getComponentMetadata(type: string) {
  this.componentRegistry.getComponent(type).subscribe(
    (metadata) => {
      this.configPanel.loadMetadata(metadata);
    }
  );
}
```

---

### Execution Endpoints

#### 1. Start Execution
```typescript
// Service
this.apiService.startExecution(jobId: string, overrides?: any)

// HTTP
POST /api/execution/start
Content-Type: application/json

// Request Body
{
  "jobId": "job_123",
  "parameters": {
    "inputFile": "/path/to/file.csv"
  }
}

// Frontend Usage
this.executionService.startExecution(jobId, params)

// TypeScript Response
ExecutionResponse {
  taskId: string
  jobId: string
  status: ExecutionStatus
  startedAt: string
}

// Component Usage
executeJob(jobId: string) {
  this.executionService.startExecution(jobId).subscribe(
    (response) => {
      this.taskId = response.taskId;
      this.router.navigate(['/execution', this.taskId]);
    }
  );
}
```

#### 2. Get Execution Status
```typescript
// Service
this.apiService.getExecutionStatus(taskId: string)

// HTTP
GET /api/execution/{taskId}

// Frontend Usage
this.executionService.pollExecutionStatus(taskId)

// TypeScript Response
ExecutionStatus {
  taskId: string
  jobId: string
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'STOPPED'
  progress: number (0-100)
  startedAt: string
  completedAt?: string
  error?: string
  logs: ExecutionLog[]
  statistics: Record<string, any>
}

// Component Usage
ngOnInit() {
  this.executionService
    .getExecutionStatus()
    .subscribe((status) => {
      this.progress = status.progress;
      this.status = status.status;
      this.logs = status.logs;
    });
}
```

#### 3. Stop Execution
```typescript
// Service
this.apiService.stopExecution(taskId: string)

// HTTP
POST /api/execution/{taskId}/stop

// Frontend Usage
this.executionService.stopExecution(taskId)

// TypeScript Response
{ success: true, message: "Execution stopped" }

// Component Usage
stopExecution() {
  this.executionService.stopExecution(this.taskId).subscribe(
    () => {
      this.status = 'STOPPED';
    }
  );
}
```

---

## 🔌 WebSocket Integration

### Real-Time Execution Updates

#### Connection Initialization
```typescript
// Service
this.websocketService.connect(taskId)

// WebSocket URL
ws://localhost:8000/ws/execution/{taskId}

// Frontend Usage
this.executionService.startExecution(jobId)
  .subscribe((response) => {
    this.websocketService.connect(response.taskId);
  });
```

#### Event Streaming

**Event: execution_started**
```typescript
Data: {
  "taskId": "task_123",
  "jobId": "job_123",
  "timestamp": "2024-01-15T10:30:00Z"
}

Frontend Handler:
this.websocketService.on('execution_started').subscribe((data) => {
  this.startTime = data.timestamp;
  this.status = 'RUNNING';
});
```

**Event: execution_progress**
```typescript
Data: {
  "taskId": "task_123",
  "progress": 45,
  "currentNode": "Transform_1",
  "recordsProcessed": 5000
}

Frontend Handler:
this.websocketService.on('execution_progress').subscribe((data) => {
  this.progress = data.progress;
  this.currentNode = data.currentNode;
});
```

**Event: execution_log**
```typescript
Data: {
  "taskId": "task_123",
  "timestamp": "2024-01-15T10:30:05Z",
  "level": "INFO",
  "message": "Processing record 1000",
  "source": "Transform_1"
}

Frontend Handler:
this.websocketService.on('execution_log').subscribe((log) => {
  this.logs.push(log);
  this.logViewer.scrollToBottom();
});
```

**Event: execution_completed**
```typescript
Data: {
  "taskId": "task_123",
  "status": "COMPLETED",
  "completedAt": "2024-01-15T10:30:30Z",
  "statistics": {
    "totalRecords": 10000,
    "processedRecords": 10000,
    "failedRecords": 0,
    "duration": 30
  }
}

Frontend Handler:
this.websocketService.on('execution_completed').subscribe((data) => {
  this.status = 'COMPLETED';
  this.statistics = data.statistics;
});
```

**Event: execution_error**
```typescript
Data: {
  "taskId": "task_123",
  "error": "Invalid column name: 'unknown_col'",
  "nodeId": "Transform_1",
  "timestamp": "2024-01-15T10:30:10Z"
}

Frontend Handler:
this.websocketService.on('execution_error').subscribe((error) => {
  this.status = 'FAILED';
  this.error = error.error;
  this.failedNode = error.nodeId;
});
```

---

## 📡 Request/Response Examples

### Create Job Example
```bash
# Request
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Clean Customer Data",
    "description": "Remove duplicates and standardize formats",
    "nodes": [
      {
        "id": "input_1",
        "type": "tFileInput",
        "position": {"x": 100, "y": 100},
        "config": {"filePath": "/data/customers.csv"}
      }
    ],
    "edges": []
  }'

# Response
{
  "id": "job_abc123",
  "name": "Clean Customer Data",
  "description": "Remove duplicates and standardize formats",
  "nodes": [...],
  "edges": [],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Start Execution Example
```bash
# Request
curl -X POST http://localhost:8000/api/execution/start \
  -H "Content-Type: application/json" \
  -d '{
    "jobId": "job_abc123",
    "parameters": {
      "inputFile": "/data/customers.csv"
    }
  }'

# Response
{
  "taskId": "task_def456",
  "jobId": "job_abc123",
  "status": "RUNNING",
  "startedAt": "2024-01-15T10:35:00Z"
}
```

### WebSocket Connection Example
```javascript
// Connect
const socket = io('ws://localhost:8000');

socket.on('execution_progress', (data) => {
  console.log(`Progress: ${data.progress}%`);
  console.log(`Processing: ${data.currentNode}`);
});

socket.on('execution_log', (log) => {
  console.log(`[${log.level}] ${log.message}`);
});

socket.on('execution_completed', (data) => {
  console.log('Execution finished!');
  console.log(`Total time: ${data.statistics.duration}s`);
});
```

---

## 🔒 Error Handling

### API Error Response
```typescript
// Service catches errors automatically
this.apiService.listJobs().subscribe(
  (jobs) => {
    // Success
    console.log('Jobs loaded');
  },
  (error) => {
    // Error handling
    console.error('Failed to load jobs:', error);
    console.error('Status:', error.status);
    console.error('Message:', error.error.detail);
  }
);
```

### Error Response Format
```json
{
  "detail": "Job not found",
  "status": 404,
  "error_type": "NotFoundError"
}
```

### Common HTTP Status Codes
| Code | Meaning | Solution |
|------|---------|----------|
| 200 | OK | Success |
| 201 | Created | Resource created |
| 400 | Bad Request | Check request format |
| 404 | Not Found | Check resource ID |
| 500 | Server Error | Backend issue |
| 503 | Service Unavailable | Backend down |

---

## 🔄 Authentication & CORS

### Development (with Proxy)
```
Frontend Request: http://localhost:4200/api/jobs
↓ Proxy Routes To
Backend Server: http://localhost:8000/api/jobs
```

### Production
```
Frontend Request: https://app.example.com/api/jobs
↓ Configured to
Backend Server: https://api.example.com/api/jobs
```

### CORS Headers (Set by Backend)
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type
```

---

## 🧪 Testing Backend Integration

### 1. Check Backend Health
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

### 2. List Jobs
```bash
curl http://localhost:8000/api/jobs
# Expected: {"jobs": [...], "total": 0}
```

### 3. List Components
```bash
curl http://localhost:8000/api/components
# Expected: {"components": {...}, "categories": [...]}
```

### 4. WebSocket Connection
```javascript
const socket = io('http://localhost:8000');
socket.on('connect', () => {
  console.log('Connected to backend');
});
```

---

## 🔐 Frontend Service Usage Pattern

### ApiService (REST Client)
```typescript
constructor(private http: HttpClient, private env: environment) {}

// All methods return Observable<T>
listJobs(): Observable<JobListResponse> {
  return this.http.get<JobListResponse>(
    `${this.env.apiUrl}/jobs`
  );
}
```

### WebSocketService (Real-time)
```typescript
connect(taskId: string): void {
  this.socket = io(this.env.wsUrl);
  this.socket.emit('subscribe', { taskId });
}

on(event: string): Observable<any> {
  return new Observable(observer => {
    this.socket.on(event, (data) => {
      observer.next(data);
    });
  });
}
```

### JobService (Business Logic)
```typescript
loadJobs(): void {
  this.api.listJobs().subscribe(
    (response) => {
      this.jobs$.next(response.jobs);
    },
    (error) => {
      console.error('Load failed', error);
    }
  );
}
```

### ExecutionService (Orchestration)
```typescript
startExecution(jobId: string): Observable<ExecutionResponse> {
  return this.api.startExecution(jobId).pipe(
    tap((response) => {
      this.taskId$.next(response.taskId);
      this.ws.connect(response.taskId);
    })
  );
}
```

---

## ✅ Integration Verification Steps

1. **Start Backend**
   ```bash
   cd backend && python run.py
   ```

2. **Check Health**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Install Frontend**
   ```bash
   cd frontend-angular && npm install
   ```

4. **Start Frontend**
   ```bash
   npm start
   ```

5. **Test Job Load**
   - Open http://localhost:4200
   - Check Network tab for `/api/jobs` call
   - Should see jobs list or empty state

6. **Test Execution**
   - Create test job
   - Click Execute
   - Watch WebSocket messages in browser DevTools

---

## 📚 Reference Documentation

- **Backend API:** Check backend/main.py
- **OpenAPI Docs:** http://localhost:8000/docs
- **WebSocket Events:** Check backend socket handlers
- **Component Registry:** Check backend COMPONENT_REGISTRY

---

**Backend Integration: COMPLETE ✅**

All frontend services properly integrated with backend APIs and ready for production use!
