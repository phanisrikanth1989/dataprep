# RecDataPrep UI - Setup & Deployment Guide

## Overview

Complete setup instructions for the RecDataPrep ETL Visual Designer UI with backend and frontend.

**Architecture:**
- **Backend:** FastAPI server (Python) on port 8000
- **Frontend:** React + Vite app on port 5173
- **Communication:** REST API + WebSocket

---

## Prerequisites

- **Python 3.8+**
- **Node.js 16+** and npm
- **Git**

---

## Backend Setup (FastAPI)

### Step 1: Create Python Environment

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Verify ETL Engine

The backend expects your ETL engine at `src/v1/engine/`. Verify the path structure:

```
recdataprep/
├── backend/
│   ├── app/
│   ├── jobs/
│   └── run.py
├── src/
│   └── v1/
│       └── engine/
│           ├── engine.py
│           ├── base_component.py
│           └── ...
```

### Step 4: Run Backend Server

```bash
python run.py
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Verify the server:**
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## Frontend Setup (React)

### Step 1: Install Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install packages
npm install
```

### Step 2: Configure Environment

Create `.env.local` file:

```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000
```

### Step 3: Run Development Server

```bash
npm run dev
```

**Expected output:**
```
VITE v5.0.8  ready in 500 ms

➜  Local:   http://localhost:5173/
➜  Press h to show help
```

### Step 4: Open in Browser

Navigate to: **http://localhost:5173**

---

## Usage Guide

### 1. Create a Job

1. Click **"New Job"** button
2. Enter job name and description
3. Click **"Create"**
4. You'll be taken to the job designer

### 2. Design the Job

**Drag and Drop Components:**
- Left panel: Component palette
- Drag components onto the canvas
- Connect components with flows (click output → click input)

**Configure Components:**
- Click on a component to select it
- Right panel: Configure properties
- Click **"Save Configuration"**

**Supported Components:**
- **Input:** FileInput
- **Transform:** Map, Filter, Aggregate, Sort
- **Output:** FileOutput

### 3. Save the Job

- Click **"Save"** button (top right)
- Job is saved as JSON

### 4. Export Job Config

- Click **"Export"** button
- Downloads job as JSON (compatible with your ETL engine)

### 5. Execute Job

- Click **"Run"** button (top right)
- Opens execution monitor
- Watch real-time progress, logs, and statistics

---

## API Endpoints

### Jobs

```
GET    /api/jobs              - List all jobs
POST   /api/jobs              - Create new job
GET    /api/jobs/{job_id}     - Get job details
PUT    /api/jobs/{job_id}     - Update job
DELETE /api/jobs/{job_id}     - Delete job
GET    /api/jobs/{job_id}/export  - Export as config
```

### Components

```
GET    /api/components        - List all components
GET    /api/components/{type} - Get component metadata
```

### Execution

```
POST   /api/execution/start   - Start job execution
GET    /api/execution/{task_id} - Get execution status
POST   /api/execution/{task_id}/stop - Stop execution
WS     /api/execution/ws/{task_id} - WebSocket updates
```

---

## Project Structure

### Backend

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory
│   ├── models.py            # Pydantic models
│   ├── schemas.py           # Component metadata
│   ├── routes/
│   │   ├── jobs.py         # Job CRUD
│   │   ├── components.py   # Component metadata
│   │   └── execution.py    # Job execution
│   └── services/
│       ├── job_service.py  # Job logic
│       └── execution_service.py # Execution logic
├── jobs/                    # Job storage (auto-created)
├── run.py                   # Server entry point
└── requirements.txt         # Python dependencies
```

### Frontend

```
frontend/
├── src/
│   ├── components/
│   │   ├── Canvas.tsx           # React Flow canvas
│   │   ├── ComponentNode.tsx    # Component node design
│   │   ├── ComponentPalette.tsx # Drag-drop palette
│   │   ├── ConfigPanel.tsx      # Configuration form
│   │   ├── ExecutionMonitor.tsx # Job execution monitor
│   │   └── JobList.tsx          # Job list/management
│   ├── pages/
│   │   ├── JobDesigner.tsx      # Main designer page
│   │   └── ExecutionView.tsx    # Execution monitoring page
│   ├── services/
│   │   ├── api.ts               # API calls (axios)
│   │   └── websocket.ts         # WebSocket client
│   ├── types/
│   │   └── index.ts             # TypeScript types
│   ├── App.tsx                  # Main app
│   ├── main.tsx                 # Entry point
│   └── index.css                # Styles
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── .env.example
```

---

## Running Both Servers

### Terminal 1: Backend

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python run.py
```

### Terminal 2: Frontend

```bash
cd frontend
npm run dev
```

Now open **http://localhost:5173** in your browser!

---

## Production Deployment

### Build Frontend

```bash
cd frontend
npm run build
```

Creates `dist/` folder with optimized static files.

### Deploy Backend

```bash
# Using Gunicorn + Uvicorn
pip install gunicorn

gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Docker Deployment

**Backend Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .

CMD ["python", "run.py"]
```

**Frontend Dockerfile:**
```dockerfile
FROM node:18 as build
WORKDIR /app
COPY frontend/package*.json .
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
CMD ["nginx", "-g", "daemon off;"]
```

---

## Troubleshooting

### CORS Errors

**Solution:** Ensure both servers are running and CORS is configured:
- Backend: `vite:5173` is in allowed origins
- Frontend: API URL points to correct backend

### WebSocket Connection Fails

**Check:**
- Backend running on port 8000
- WebSocket proxy configured in `vite.config.ts`
- Browser console for error details

### Job Execution Fails

**Check:**
- ETL engine path in `execution_service.py` is correct
- Job has valid configuration
- Required components are implemented

### "Job not found" Error

**Solution:**
- Save job first before running
- Verify job file exists in `backend/jobs/` folder

---

## Next Steps

1. **Add More Components:**
   - Edit `backend/app/schemas.py` to add component definitions
   - Implement component classes in `src/v1/engine/components/`

2. **Enhance Job Monitoring:**
   - Stream real-time logs from ETL engine
   - Add component-level statistics tracking
   - Build advanced job analytics dashboard

3. **Add Features:**
   - Job templates & clone
   - Parameter overrides at runtime
   - Job scheduling/cron
   - Audit logs & history

4. **Security:**
   - Add authentication (JWT)
   - Add authorization (RBAC)
   - Encrypt sensitive data

---

## Support

For issues or questions:
1. Check backend logs: `http://localhost:8000/docs`
2. Check browser console (F12)
3. Review API responses in Network tab
4. Check `jobs/` folder for saved configurations

---

## License

Proprietary - RecDataPrep ETL Engine UI
