# RecDataPrep - Knowledge Base Summary

**Complete workspace understanding - Quick reference**  
**Last Updated:** January 17, 2026

---

## 📋 What You Need to Know

### The Project
RecDataPrep is a **web-based visual ETL (Extract-Transform-Load) designer** inspired by Talend. It allows users to:
- Design data transformation jobs visually (drag-drop canvas)
- Connect components with data flows
- Configure transformations
- Execute jobs and monitor progress in real-time

### The Stack
- **Frontend:** React 18 + TypeScript + React Flow + Ant Design
- **Backend:** FastAPI + Python + Pydantic
- **Engine:** Custom Python ETL engine with Talend-like features
- **Optional:** Java bridge (Py4J) + Python routines

### The Architecture Pattern
```
Visual Design (React) → REST/WebSocket API (FastAPI) → Execution Engine (Python)
     ↓                          ↓                              ↓
  Job Editor              Job Persistence            Component Execution
  Canvas                  Job Validation              Data Transformation
  Config Forms            Status Tracking            Statistics Collection
```

---

## 🗂️ File Organization Quick Map

### Documentation Files (Start Here)
```
START_HERE.md               ← Overview & quick start
README_INDEX.md             ← Navigation hub
ARCHITECTURE.md             ← Deep dive architecture
WORKSPACE_OVERVIEW.md       ← [NEW] Complete system overview
SYSTEM_DIAGRAMS.md          ← [NEW] Visual diagrams
CODE_REFERENCE.md           ← [NEW] Code patterns & reference
QUICK_REFERENCE.md          ← Command cheat sheet
SETUP_DEPLOYMENT.md         ← Installation guide
TESTING_GUIDE.md            ← Testing procedures
```

### Source Code Organization
```
Frontend (React + TypeScript)
  frontend/src/
  ├── App.tsx                    ← Main app shell & navigation
  ├── pages/JobDesigner.tsx      ← Job editor page
  ├── components/
  │   ├── Canvas.tsx            ← React Flow visual editor
  │   ├── ComponentPalette.tsx   ← Draggable toolbar
  │   ├── ConfigPanel.tsx       ← Dynamic forms generator
  │   ├── JobList.tsx           ← Job management UI
  │   └── ExecutionMonitor.tsx  ← Real-time progress
  ├── services/
  │   ├── api.ts                ← REST client
  │   └── websocket.ts          ← WebSocket client
  └── types/index.ts            ← TypeScript interfaces

Backend (FastAPI + Python)
  backend/
  ├── run.py                     ← Entry point
  ├── app/
  │   ├── main.py               ← FastAPI factory
  │   ├── models.py             ← Pydantic models
  │   ├── schemas.py            ← Component registry
  │   ├── routes/
  │   │   ├── jobs.py           ← Job CRUD API
  │   │   ├── components.py     ← Component metadata API
  │   │   └── execution.py      ← Execution & WebSocket API
  │   └── services/
  │       ├── job_service.py    ← Job persistence
  │       └── execution_service.py ← Job execution
  └── jobs/                      ← Job storage (JSON files)

Core ETL Engine (Python)
  src/v1/engine/
  ├── engine.py                 ← Main orchestrator (743 lines)
  ├── base_component.py         ← Component base class (378 lines)
  ├── global_map.py             ← State store (Talend-like)
  ├── context_manager.py        ← Variable management
  ├── trigger_manager.py        ← Workflow triggers
  ├── java_bridge_manager.py    ← Java integration
  ├── python_routine_manager.py ← Python routines
  ├── components/
  │   └── transform/
  │       └── map.py            ← tMap component (1141 lines)
  └── java_bridge/
      └── bridge.py             ← Py4J wrapper
```

---

## 🔑 Key Concepts

### 1. **Jobs**
- Definition: Reusable ETL workflow
- Storage: JSON files in `backend/jobs/`
- Composition: Nodes (components) + Edges (data flows)

### 2. **Components**
- Definition: Individual ETL operations (Map, Filter, FileInput, etc.)
- Base: All extend `BaseComponent`
- Execution: `execute()` → `_process()` → outputs

### 3. **Data Flow**
- Components are connected via edges
- Main output → downstream components
- Reject/error output → error handlers
- Multiple inputs supported (lookups, joins)

### 4. **Execution**
- Triggered from UI via `/api/execution/start`
- Asynchronous execution in backend
- Real-time updates via WebSocket
- Statistics collection during execution

### 5. **GlobalMap** (Talend concept)
- Shared state store across job
- Stores component statistics (NB_LINE, NB_LINE_OK, etc.)
- Accessible in Java expressions
- Enables trigger conditions based on stats

### 6. **Triggers**
- OnComponentOk: Fired when component succeeds
- OnSubjobError: Fired when subjob fails
- Control workflow activation
- Enable complex conditional execution

---

## 🚀 Essential Workflows

### Design a Job
1. Open frontend (http://localhost:5173)
2. Click "New Job"
3. Name the job
4. Drag components from palette → canvas
5. Connect with edges
6. Double-click component → configure
7. Save job

### Execute a Job
1. Select job from list
2. Click "Execute"
3. WebSocket connects
4. Real-time monitoring:
   - Component progress
   - Row counts
   - Logs & errors
5. View results when complete

### Add a Component
1. Define metadata in `backend/app/schemas.py`
2. Create class in `src/v1/engine/components/`
3. Extend `BaseComponent`
4. Implement `_process()` method
5. Register in `engine.py` COMPONENT_REGISTRY
6. Frontend auto-discovers via API

---

## 📊 Built-in Components

| Component | Type | Input/Output | Key Features |
|-----------|------|--------------|--------------|
| **Map** | Transform | 1+/2+ | Joins, lookups, expressions, transformations |
| **Filter** | Transform | 1/2 | Row filtering with conditions |
| **FileInput** | Input | 0/1 | CSV, JSON, Parquet, Excel reader |
| **FileOutput** | Output | 1/0 | Write to multiple formats |
| **Aggregate** | Transform | 1/1 | Group-by, sum, count, avg |
| **Sort** | Transform | 1/1 | Sort by columns |

---

## 🔌 API Quick Reference

### List Jobs
```bash
GET /api/jobs
```

### Get Job Details
```bash
GET /api/jobs/{job_id}
```

### Create Job
```bash
POST /api/jobs
Content-Type: application/json

{
  "id": "my_job",
  "name": "My Job",
  "nodes": [...],
  "edges": [...],
  "context": {}
}
```

### Start Execution
```bash
POST /api/execution/start
Content-Type: application/json

{
  "job_id": "my_job"
}
```
Response: `{ "task_id": "task_xyz", "status": "started" }`

### WebSocket Connection
```
ws://localhost:8000/ws/execution/{task_id}
```
Receives real-time ExecutionStatus updates

### List Components
```bash
GET /api/components
```
Returns all ComponentMetadata objects

---

## 💡 Development Quick Start

### Backend Development
```bash
# Terminal 1: Start backend
cd backend
python run.py

# Backend runs on http://localhost:8000
# Auto-reloads on file changes
# API docs at http://localhost:8000/docs
```

### Frontend Development
```bash
# Terminal 2: Start frontend
cd frontend
npm install       # First time only
npm run dev

# Frontend runs on http://localhost:5173
# Auto-reloads on file changes
```

### Creating New Features
1. **Backend Route:** Add in `backend/app/routes/`
2. **Backend Service:** Add in `backend/app/services/`
3. **Frontend Service:** Add in `frontend/src/services/api.ts`
4. **Frontend Component:** Add in `frontend/src/components/`
5. **Testing:** Use browser console & API docs

---

## 🔍 Debugging Tips

### Backend Issues
```python
# Add logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Debug: {value}")

# Check API docs
http://localhost:8000/docs  # Swagger UI

# Check server logs
# Look at terminal output where python run.py is running
```

### Frontend Issues
```typescript
// Add logging
console.log("Debug:", variable)
console.error("Error:", error)

// Check Network tab
// Browser DevTools → Network → filter for API calls

// Check Console tab
// Browser DevTools → Console → look for errors
```

### Job Execution Issues
```bash
# Check job file exists
ls backend/jobs/

# Check job JSON structure
cat backend/jobs/job_id.json

# Check execution logs
# Look at backend terminal output during execution
```

---

## 📈 Performance Considerations

### Memory Efficient
- **Streaming mode** for large files
- **Batch mode** for small data
- **Hybrid mode** (auto-switch) default

### Fast Execution
- Pandas for joins (optimized in native code)
- Java bridge for complex expressions
- Pre-compiled lookups

### Scalability
- Async execution (non-blocking)
- File-based job storage (no DB needed)
- Optional SQLAlchemy support for future DB

---

## 🎯 Architecture Decisions

### Why REST + WebSocket?
- REST for CRUD operations (simple, stateless)
- WebSocket for real-time streaming (low-latency updates)
- Hybrid approach for best of both worlds

### Why Pydantic?
- Automatic data validation
- Type hints throughout
- Auto-generated OpenAPI docs
- JSON serialization support

### Why React Flow?
- Proven visual graph editor
- Good performance for large DAGs
- Active community & support
- Easy to customize

### Why File-based Storage?
- No database setup required
- Easy deployment
- Human-readable (JSON)
- Optional SQL support later

### Why Component Registry?
- Dynamic component discovery
- Easy extensibility
- Frontend auto-discovery
- Type safety

---

## 🏗️ Deployment Checklist

- [ ] Python 3.8+ installed
- [ ] Node.js 14+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`, `npm install`)
- [ ] Frontend built (`npm run build`)
- [ ] Backend configured (port 8000)
- [ ] Frontend configured (port 5173 or served from build)
- [ ] Job storage directory created (backend/jobs/)
- [ ] CORS properly configured
- [ ] Environment variables set (if any)
- [ ] Test job execution
- [ ] Monitor real-time updates

---

## 📚 Documentation Structure

```
Level 1: Getting Started
  └─ START_HERE.md, README_INDEX.md

Level 2: Understanding
  ├─ ARCHITECTURE.md (system design)
  ├─ WORKSPACE_OVERVIEW.md (complete overview)
  ├─ SYSTEM_DIAGRAMS.md (visual diagrams)
  └─ QUICK_REFERENCE.md (commands)

Level 3: Development
  ├─ SETUP_DEPLOYMENT.md (setup instructions)
  ├─ CODE_REFERENCE.md (code patterns)
  └─ UI_README.md (UI features)

Level 4: Validation
  └─ TESTING_GUIDE.md (testing procedures)
```

---

## ✅ Implementation Status

| Component | Status | LOC | File |
|-----------|--------|-----|------|
| **Engine** | ✅ Complete | 2400 | src/v1/engine/ |
| **tMap Component** | ✅ Complete | 1141 | src/v1/engine/components/transform/map.py |
| **Backend API** | ✅ Complete | 850 | backend/app/ |
| **Frontend UI** | ✅ Complete | 2200 | frontend/src/ |
| **Documentation** | ✅ Complete | 2000+ | *.md files |
| **Total** | ✅ Complete | 5000+ | Entire project |

---

## 🎓 Learning Path

### Beginner
1. Read START_HERE.md
2. Run quickstart script
3. Create & execute simple job
4. Use UI to explore

### Intermediate
1. Read ARCHITECTURE.md
2. Read WORKSPACE_OVERVIEW.md
3. Look at code in backend/app/
4. Modify component configuration

### Advanced
1. Read CODE_REFERENCE.md
2. Read system/engine code
3. Create custom component
4. Modify ETL engine

### Expert
1. Understand trigger system
2. Understand execution model
3. Optimize for performance
4. Deploy to production

---

## 🔗 Key Files to Know

### Most Important
1. `WORKSPACE_OVERVIEW.md` - [NEW] Start here
2. `SYSTEM_DIAGRAMS.md` - [NEW] Visual reference
3. `CODE_REFERENCE.md` - [NEW] Code patterns

### Backend Core
1. `backend/app/main.py` - FastAPI setup
2. `backend/app/schemas.py` - Component registry
3. `src/v1/engine/engine.py` - Main engine

### Frontend Core
1. `frontend/src/App.tsx` - App shell
2. `frontend/src/pages/JobDesigner.tsx` - Designer
3. `frontend/src/components/Canvas.tsx` - Canvas

### Configuration
1. `backend/requirements.txt` - Backend dependencies
2. `frontend/package.json` - Frontend dependencies
3. `backend/app/models.py` - Data models

---

## 🚀 Next Steps

### If You Want To...

**Understand the system**
→ Read WORKSPACE_OVERVIEW.md & SYSTEM_DIAGRAMS.md

**Set up locally**
→ Run quickstart.bat (Windows) or quickstart.sh (Mac/Linux)

**Modify backend**
→ Edit backend/app/ and restart server

**Modify frontend**
→ Edit frontend/src/ (auto-reloads)

**Add a component**
→ Follow CODE_REFERENCE.md component development section

**Deploy to production**
→ Follow SETUP_DEPLOYMENT.md

**Debug issues**
→ Check browser console (frontend) or terminal logs (backend)

---

## 📞 Quick Help

**Backend won't start?**
- Check Python 3.8+ installed
- Check port 8000 free
- Check dependencies installed

**Frontend won't load?**
- Check Node.js installed
- Check npm dependencies installed
- Check backend running first

**Component not showing?**
- Verify registered in COMPONENT_REGISTRY
- Verify metadata in schemas.py
- Clear browser cache & reload

**WebSocket not working?**
- Check backend running
- Check WebSocket URL correct
- Check browser Network tab for connection

**Job execution fails?**
- Check component configuration
- Check data types match expectations
- Look at backend terminal for error details

---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Total Files | 50+ |
| Total Lines of Code | ~5000 |
| Backend Files | 13 |
| Frontend Files | 30+ |
| Documentation Files | 7+ |
| Core Engine LOC | 2400 |
| Largest Component | tMap (1141 LOC) |
| Built-in Components | 6 |
| API Endpoints | 14+ |
| Status | Production Ready ✅ |

---

## 🎉 Summary

**RecDataPrep is a complete, production-ready ETL visual designer system.**

It combines:
- **Modern Frontend:** React + TypeScript + React Flow
- **Robust Backend:** FastAPI + Python + Pydantic
- **Powerful Engine:** Custom ETL orchestrator with Talend-like features
- **Extensible Architecture:** Easy to add components and features
- **Comprehensive Documentation:** Multiple guides for different audiences

The system is ready for:
- ✅ Local development
- ✅ Feature additions
- ✅ Production deployment
- ✅ Custom extensions

Start with WORKSPACE_OVERVIEW.md and explore from there!

---

*Last Updated: January 17, 2026*  
*Status: Fully Implemented and Documented*
