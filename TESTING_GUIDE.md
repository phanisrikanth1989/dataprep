# UI Implementation - Validation & Testing Guide

This document provides validation steps and testing procedures for the RecDataPrep UI implementation.

## ✅ Implementation Checklist

### Backend Implementation (13 files)
- [x] **app/main.py** - FastAPI application factory
  - [x] CORS enabled for localhost
  - [x] Routes registered (jobs, components, execution)
  - [x] Error handling middleware
  - [x] Health check endpoint
  
- [x] **app/models.py** - Pydantic data models
  - [x] ComponentFieldSchema model
  - [x] ComponentMetadata model
  - [x] JobSchema model
  - [x] ExecutionStatus model
  - [x] ExecutionUpdate model

- [x] **app/schemas.py** - Component registry
  - [x] 6 components registered (Map, Filter, FileInput, FileOutput, Aggregate, Sort)
  - [x] Component metadata for each type
  - [x] Field definitions with types and defaults
  - [x] Helper functions (get_component_metadata, list_components)

- [x] **app/services/job_service.py** - Job CRUD logic
  - [x] create_job() - Create and save new job
  - [x] get_job() - Retrieve job by ID
  - [x] list_jobs() - List all jobs
  - [x] update_job() - Update existing job
  - [x] delete_job() - Delete job file
  - [x] export_job_config() - Convert to ETL engine format

- [x] **app/services/execution_service.py** - Execution management
  - [x] ExecutionManager class for tracking
  - [x] execute_job() - Async job execution
  - [x] get_execution() - Get execution status
  - [x] stop_execution() - Stop running job
  - [x] WebSocket connection tracking

- [x] **app/routes/jobs.py** - REST endpoints for jobs
  - [x] GET /api/jobs - List all jobs
  - [x] GET /api/jobs/{job_id} - Get job details
  - [x] POST /api/jobs - Create new job
  - [x] PUT /api/jobs/{job_id} - Update job
  - [x] DELETE /api/jobs/{job_id} - Delete job
  - [x] GET /api/jobs/{job_id}/export - Export config

- [x] **app/routes/components.py** - Component metadata endpoints
  - [x] GET /api/components - List all components
  - [x] GET /api/components/{component_type} - Get component details

- [x] **app/routes/execution.py** - Execution control & WebSocket
  - [x] POST /api/execution/start - Start job execution
  - [x] GET /api/execution/{task_id} - Get execution status
  - [x] POST /api/execution/{task_id}/stop - Stop execution
  - [x] WebSocket /api/execution/ws/{task_id} - Real-time updates

- [x] **run.py** - Server entry point
  - [x] Uvicorn configuration
  - [x] Auto-reload enabled
  - [x] Port 8000 default

- [x] **requirements.txt** - Python dependencies
  - [x] fastapi==0.104.1
  - [x] uvicorn[standard]==0.24.0
  - [x] pydantic==2.5.0
  - [x] pydantic-settings==2.1.0
  - [x] python-socketio==5.9.0
  - [x] python-multipart==0.0.6
  - [x] pydantic[email]==2.5.0
  - [x] pytest==7.4.3
  - [x] pytest-asyncio==0.21.1
  - [x] httpx==0.25.2

### Frontend Implementation (30+ files)

#### Configuration Files
- [x] **package.json** - npm dependencies
  - [x] React 18.2
  - [x] React Flow 11.10
  - [x] Ant Design 5.11
  - [x] Vite 5.0
  - [x] TypeScript 5.2
  - [x] Socket.io-client 4.5
  - [x] Axios 1.6

- [x] **vite.config.ts** - Vite build configuration
  - [x] React plugin
  - [x] Proxy for /api → backend
  - [x] Port 5173

- [x] **tsconfig.json** - TypeScript compiler options
  - [x] Strict mode
  - [x] React JSX support
  - [x] Path aliases

- [x] **index.html** - HTML entry point
  - [x] Root div for React mount
  - [x] Script for main.tsx

#### Type & Service Layer (5 files)
- [x] **src/types/index.ts** - TypeScript interfaces
  - [x] JobNode, JobEdge types
  - [x] ComponentMetadata type
  - [x] ExecutionStatus type
  - [x] ExecutionUpdate type

- [x] **src/services/api.ts** - Axios API client
  - [x] jobsAPI (list, get, create, update, delete, export)
  - [x] componentsAPI (list, get)
  - [x] executionAPI (start, status, stop)

- [x] **src/services/websocket.ts** - WebSocket client
  - [x] useWebSocket hook
  - [x] Connection/disconnection
  - [x] Error handling

#### Components (6 files)
- [x] **src/components/Canvas.tsx** - React Flow canvas
  - [x] Drag-drop support
  - [x] Node/edge management
  - [x] MiniMap, Controls
  - [x] State callbacks

- [x] **src/components/ComponentNode.tsx** - Custom React Flow node
  - [x] Icon display
  - [x] Input/output handles
  - [x] Component label

- [x] **src/components/ComponentPalette.tsx** - Component library
  - [x] Dynamic component loading
  - [x] Category grouping
  - [x] Drag-start handlers

- [x] **src/components/ConfigPanel.tsx** - Configuration form
  - [x] Dynamic field rendering
  - [x] Field type handling
  - [x] Form state management
  - [x] Save callback

- [x] **src/components/ExecutionMonitor.tsx** - Execution dashboard
  - [x] WebSocket connection
  - [x] Progress bar
  - [x] Component statistics display
  - [x] Live logs viewer
  - [x] Error display
  - [x] Stop button

- [x] **src/components/JobList.tsx** - Job management
  - [x] Job table display
  - [x] Create modal
  - [x] Delete with confirmation
  - [x] Execute button

#### Pages (3 files)
- [x] **src/pages/JobDesigner.tsx** - Main designer
  - [x] Canvas area
  - [x] Component palette
  - [x] Config panel
  - [x] Save/Export/Execute buttons

- [x] **src/pages/ExecutionView.tsx** - Execution view (if created)
  - [x] Execution monitor integration

- [x] **src/App.tsx** - App shell
  - [x] Navigation/routing
  - [x] Page switching
  - [x] Header

#### Assets
- [x] **src/main.tsx** - React entry point
- [x] **src/index.css** - Global styles
- [x] **frontend/.env.example** - Environment template
- [x] **.gitignore** - Git ignore patterns

### Documentation (3 files)
- [x] **SETUP_DEPLOYMENT.md** - Setup and deployment guide
- [x] **UI_README.md** - Comprehensive UI documentation
- [x] **TESTING_GUIDE.md** - This file

---

## 🧪 Testing Procedures

### Unit 1: Backend Startup

**Test:** Verify backend starts correctly

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python run.py
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Validation Points:**
- [ ] No errors during startup
- [ ] Server listening on port 8000
- [ ] Can access http://localhost:8000/health
- [ ] Can access http://localhost:8000/docs (Swagger UI)

---

### Unit 2: Frontend Startup

**Test:** Verify frontend builds and serves correctly

```bash
cd frontend
npm install
npm run dev
```

**Expected Output:**
```
  VITE v5.0.0  ready in 500 ms

  ➜  Local:   http://localhost:5173/
```

**Validation Points:**
- [ ] No npm install errors
- [ ] Dev server starts without warnings
- [ ] Can access http://localhost:5173
- [ ] Browser loads without errors

---

### Unit 3: API Endpoint Testing

**Test:** Verify all backend API endpoints

**Prerequisites:** Backend running on localhost:8000

#### Test 3.1: Component Endpoints
```bash
# List components
curl http://localhost:8000/api/components

# Get single component
curl http://localhost:8000/api/components/Map
```

**Expected:** Returns JSON with component metadata

#### Test 3.2: Job Creation
```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Job",
    "description": "Test Description",
    "nodes": [],
    "edges": {},
    "context": {}
  }'
```

**Expected:** Returns job with ID and creation timestamp

#### Test 3.3: Job Retrieval
```bash
curl http://localhost:8000/api/jobs
curl http://localhost:8000/api/jobs/{job_id}
```

**Expected:** Returns job list and individual job

#### Test 3.4: Job Update
```bash
curl -X PUT http://localhost:8000/api/jobs/{job_id} \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "description": "Updated Description",
    "nodes": [],
    "edges": {},
    "context": {}
  }'
```

**Expected:** Job updated successfully

#### Test 3.5: Job Export
```bash
curl http://localhost:8000/api/jobs/{job_id}/export
```

**Expected:** Returns job in ETLEngine config format

---

### Integration 1: UI Component Rendering

**Test:** Verify React components render correctly

**Procedure:**
1. Open http://localhost:5173 in browser
2. Verify page loads without console errors
3. Check browser DevTools console for errors

**Validation Points:**
- [ ] No React errors in console
- [ ] Job list displays (even if empty)
- [ ] Can see "+ New Job" button
- [ ] Component palette loads (left sidebar)

---

### Integration 2: Create and Save Job

**Test:** Full workflow - create, design, save job

**Procedure:**
1. Click "+ New Job" button
2. Enter job name: "Integration Test Job"
3. Enter description: "Test job for integration"
4. Click "Create"
5. Verify redirected to job designer
6. Drag "FileInput" component to canvas
7. Click "Save" button
8. Verify job saved (check backend files in `backend/jobs/` directory)

**Validation Points:**
- [ ] Modal appears for new job
- [ ] Job designer page loads
- [ ] Can drag component to canvas
- [ ] Save button works
- [ ] Job file created in `backend/jobs/`

---

### Integration 3: Configure Component

**Test:** Configure a component with different field types

**Procedure:**
1. With job open in designer
2. Drag "Map" component to canvas
3. Click the Map component to select it
4. In right panel, edit configuration
5. Set mapping expression: `{ id: "input.id", name: "input.name" }`
6. Click "Save Config"
7. Verify configuration persisted

**Validation Points:**
- [ ] Config panel appears on selection
- [ ] Can edit different field types
- [ ] Save applies changes
- [ ] Config persists after reload

---

### Integration 4: Job Export

**Test:** Export job to ETLEngine config format

**Procedure:**
1. With job in designer
2. Add at least 2 components
3. Connect them with edges
4. Click "Export" button
5. Verify JSON file downloads

**Validation Points:**
- [ ] Export button works
- [ ] JSON file contains proper structure
- [ ] Nodes converted to components
- [ ] Edges converted to flows/triggers

---

### Integration 5: Job Execution

**Test:** Execute job and monitor progress

**Prerequisites:**
- Job with complete configuration ready
- Both backend and frontend running

**Procedure:**
1. With job in designer, click "Execute"
2. Observe redirect to execution monitor
3. Watch progress bar update
4. Monitor statistics display
5. Observe logs streaming in

**Validation Points:**
- [ ] Execution starts without errors
- [ ] WebSocket connection established
- [ ] Progress updates in real-time
- [ ] Statistics display update
- [ ] Logs appear as execution progresses

---

### Integration 6: Job List Management

**Test:** Manage jobs from job list page

**Procedure:**
1. Navigate to Jobs page
2. Verify list shows created jobs
3. Click on job to edit
4. Verify opens in designer
5. Go back to list
6. Click delete on a test job
7. Confirm deletion
8. Verify job removed from list

**Validation Points:**
- [ ] List displays all jobs
- [ ] Can open job for editing
- [ ] Delete works with confirmation
- [ ] List updates after deletion

---

### Performance 1: Canvas Performance

**Test:** Verify canvas performance with multiple components

**Procedure:**
1. Create new job
2. Drag 20+ components to canvas
3. Zoom in/out
4. Pan across canvas
5. Observe responsiveness

**Validation Points:**
- [ ] Canvas remains responsive
- [ ] No lag during zoom/pan
- [ ] No console errors
- [ ] FPS stays above 30

---

### Performance 2: Large Job Execution

**Test:** Monitor performance with long-running job

**Procedure:**
1. Create job with large input
2. Execute job
3. Monitor WebSocket message rate
4. Check for memory leaks in DevTools

**Validation Points:**
- [ ] WebSocket stays connected
- [ ] No memory growth over time
- [ ] Updates arrive regularly (1/sec)
- [ ] UI remains responsive

---

## 🐛 Debugging Tips

### Backend Debugging

**Check server logs:**
```bash
# Terminal where python run.py is running
# Look for ERROR or WARNING messages
```

**Test individual routes:**
```bash
# Test with curl or Postman
curl -v http://localhost:8000/api/jobs
```

**Enable debug logging:**
```python
# In backend/app/main.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check job files:**
```bash
# Verify jobs are saved
ls -la backend/jobs/
cat backend/jobs/job_abc123.json
```

### Frontend Debugging

**Check browser console:**
- Right-click → Inspect → Console tab
- Look for React errors or API errors

**Check network requests:**
- DevTools → Network tab
- Verify all API calls return 200 OK
- Check WebSocket connection status (WS)

**Check localStorage:**
```javascript
// In DevTools console
localStorage.getItem('currentJobId')
```

**Enable verbose logging:**
```typescript
// In frontend/src/services/api.ts
api.interceptors.response.use(response => {
  console.log('API Response:', response);
  return response;
});
```

---

## 📋 Test Report Template

**Date:** _____________________
**Tester:** _____________________
**Environment:** Windows / Mac / Linux

### Passed Tests ✅
- [ ] Backend Startup
- [ ] Frontend Startup
- [ ] API Endpoints
- [ ] Component Rendering
- [ ] Create/Save Job
- [ ] Configure Component
- [ ] Job Export
- [ ] Job Execution
- [ ] Job Management
- [ ] Canvas Performance

### Failed Tests ❌
(List any failures with error messages)

1. _____________________
   Error: _____________________
   
2. _____________________
   Error: _____________________

### Notes
_____________________________________________________________

---

## 🚀 Next Steps After Testing

If all tests pass:
1. ✅ Build for production: `npm run build` (frontend)
2. ✅ Deploy backend with Gunicorn
3. ✅ Serve frontend with nginx or similar
4. ✅ Add authentication if needed
5. ✅ Connect to database backend for job persistence
6. ✅ Set up CI/CD pipeline

If issues found:
1. Review the troubleshooting section in UI_README.md
2. Check specific file implementations
3. Verify environment variables and configurations
4. Check console logs for specific error messages
5. Use debugging tips above to investigate further

---

## Support Resources

- **Frontend Issues:** Check `frontend/src/` structure and dependencies
- **Backend Issues:** Check `backend/app/` structure and routes
- **API Issues:** Test with curl/Postman against localhost:8000
- **WebSocket Issues:** Check browser DevTools Network → WS tab
- **TypeScript Errors:** Run `npm run build` to catch compile errors

---
