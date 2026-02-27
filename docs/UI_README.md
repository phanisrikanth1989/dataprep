# RecDataPrep UI - Visual Job Designer

A modern web-based visual job designer for the RecDataPrep ETL engine, inspired by Talend's job design interface. Build, configure, and execute ETL jobs using an intuitive drag-and-drop canvas.

## Features

### 🎨 Visual Job Designer
- **Drag-and-Drop Canvas** - Intuitive component palette with drag-to-canvas functionality
- **React Flow Integration** - Professional visual workflow editing with zoom, pan, and minimap
- **Component Configuration** - Dynamic forms based on component metadata
- **Real-time Validation** - Component compatibility checking and error highlighting

### 🚀 Job Management
- **CRUD Operations** - Create, read, update, delete ETL jobs
- **Job Templates** - Save and reuse job configurations
- **Export/Import** - Export jobs as JSON for version control or sharing
- **Persistent Storage** - File-based or database storage (configured)

### 📊 Execution & Monitoring
- **Real-time Progress** - WebSocket-based live job execution updates
- **Component Statistics** - Track lines processed, accepted, rejected per component
- **Live Logs** - Stream execution logs to the UI as they happen
- **Status Tracking** - Monitor pending, running, success, and error states

### 🔧 Component Library
Pre-built components ready to use:
- **Input**: tFileInput (CSV, JSON, Parquet)
- **Transform**: tMap, tFilter, tAggregate, tSort
- **Output**: tFileOutput (single or bulk write)
- **Extensible**: Add custom components via metadata registry

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Option 1: Automated Setup (Windows)
```bash
quickstart.bat
```

### Option 2: Automated Setup (Mac/Linux)
```bash
chmod +x quickstart.sh
./quickstart.sh
```

### Option 3: Manual Setup

**Backend Setup:**
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

**Frontend Setup:**
```bash
cd frontend
npm install
```

### Starting the Application

**Terminal 1 - Start Backend Server:**
```bash
cd backend
source venv/bin/activate  # Mac/Linux
# or venv\Scripts\activate.bat  # Windows
python run.py
```

**Terminal 2 - Start Frontend Dev Server:**
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Project Structure

```
recdataprep/
├── src/                          # Original ETL engine
│   └── v1/engine/               # Engine implementation
├── backend/                      # FastAPI server
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory
│   │   ├── models.py            # Pydantic models
│   │   ├── schemas.py           # Component metadata registry
│   │   ├── routes/
│   │   │   ├── jobs.py          # Job CRUD endpoints
│   │   │   ├── components.py    # Component metadata endpoints
│   │   │   └── execution.py     # Execution & WebSocket
│   │   └── services/
│   │       ├── job_service.py   # Job persistence logic
│   │       └── execution_service.py  # Job execution manager
│   ├── requirements.txt
│   ├── run.py                   # Server entry point
│   └── jobs/                    # Stored job definitions
├── frontend/                     # React + TypeScript application
│   ├── src/
│   │   ├── main.tsx             # React entry point
│   │   ├── App.tsx              # App shell & routing
│   │   ├── components/
│   │   │   ├── Canvas.tsx       # React Flow canvas
│   │   │   ├── ComponentNode.tsx # Custom node type
│   │   │   ├── ComponentPalette.tsx  # Component library
│   │   │   ├── ConfigPanel.tsx  # Dynamic config form
│   │   │   ├── ExecutionMonitor.tsx  # Execution dashboard
│   │   │   └── JobList.tsx      # Job management table
│   │   ├── pages/
│   │   │   ├── JobDesigner.tsx  # Main designer page
│   │   │   └── ExecutionView.tsx # Execution view
│   │   ├── services/
│   │   │   ├── api.ts           # Axios API client
│   │   │   └── websocket.ts     # WebSocket client
│   │   ├── types/
│   │   │   └── index.ts         # TypeScript interfaces
│   │   └── index.css            # Global styles
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── index.html
└── docs/                         # Documentation
```

## API Reference

### Job Management

**List all jobs**
```bash
GET /api/jobs
```

**Get job details**
```bash
GET /api/jobs/{job_id}
```

**Create new job**
```bash
POST /api/jobs
Content-Type: application/json

{
  "name": "My ETL Job",
  "description": "Sample job",
  "nodes": [],
  "edges": [],
  "context": {}
}
```

**Update job**
```bash
PUT /api/jobs/{job_id}
Content-Type: application/json

{
  "name": "Updated Job",
  "description": "New description",
  "nodes": [...],
  "edges": [...]
}
```

**Delete job**
```bash
DELETE /api/jobs/{job_id}
```

**Export job config**
```bash
GET /api/jobs/{job_id}/export
```
Returns the job in ETLEngine config format (JSON).

### Components

**List all components**
```bash
GET /api/components
```

**Get component metadata**
```bash
GET /api/components/{component_type}
```

Returns component schema with field definitions.

### Execution

**Start job execution**
```bash
POST /api/execution/start
Content-Type: application/json

{
  "job_id": "job123",
  "context": {}
}
```

Response:
```json
{
  "task_id": "exec_abc123",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Get execution status**
```bash
GET /api/execution/{task_id}
```

**Stop execution**
```bash
POST /api/execution/{task_id}/stop
```

**WebSocket Updates** (Real-time)
```
WS ws://localhost:8000/api/execution/ws/{task_id}
```

Receives JSON updates every second:
```json
{
  "type": "update",
  "data": {
    "task_id": "exec_abc123",
    "status": "running",
    "progress": 45,
    "stats": {
      "NB_LINE": 1000,
      "NB_LINE_OK": 900,
      "NB_LINE_REJECT": 100
    },
    "logs": ["Line 1", "Line 2"],
    "error": null
  }
}
```

## Usage Guide

### 1. Creating a New Job

1. Click **"+ New Job"** on the Jobs page
2. Enter job name and description
3. Click **"Create"**
4. You'll be taken to the Job Designer

### 2. Designing a Job

1. **Add Components**: Drag components from the palette on the left to the canvas
2. **Configure Components**: 
   - Click a component to select it
   - Adjust settings in the right panel
   - Click **"Save Config"** to apply changes
3. **Connect Components**: Click the output handle of one component and drag to the input handle of another
4. **Save Job**: Click **"Save"** at the top to persist your changes

### 3. Running a Job

1. Click **"Execute"** button at the top of the designer
2. You'll be taken to the Execution Monitor
3. Watch real-time progress, logs, and statistics
4. Click **"Stop"** if you need to halt execution

### 4. Managing Jobs

- **Edit**: Click a job in the list to open it in the designer
- **Delete**: Click the trash icon (with confirmation)
- **Export**: Click the download icon to export job config as JSON
- **Re-run**: Click the play icon to quickly execute an existing job

## Component Reference

### tFileInput
Read data from files (CSV, JSON, Parquet)

**Fields:**
- `file_path` (text): Path to input file
- `file_format` (select): CSV, JSON, Parquet
- `delimiter` (text): For CSV files, default `,`

**Outputs:**
- Default output with full schema

### tMap
Transform data with expressions and mappings

**Fields:**
- `mappings` (expression): JavaScript object with output mappings
- `filter_condition` (expression): Optional row filter

**Outputs:**
- Main output with transformed schema
- Reject output for failed rows

**Example Mapping:**
```javascript
{
  "id": "input.id",
  "name": "input.name.toUpperCase()",
  "amount": "parseFloat(input.amount)"
}
```

### tFilter
Filter rows based on conditions

**Fields:**
- `condition` (expression): JavaScript boolean expression
- `reject_on_false` (boolean): Route non-matching rows to reject

**Outputs:**
- Main (matching rows)
- Reject (non-matching rows if enabled)

### tAggregate
Group and aggregate data

**Fields:**
- `group_by` (text): Comma-separated grouping columns
- `aggregations` (expression): Aggregation functions

**Outputs:**
- Aggregated data

### tSort
Sort data by one or more columns

**Fields:**
- `sort_keys` (text): Comma-separated column names
- `reverse` (boolean): Descending order

**Outputs:**
- Sorted data

### tFileOutput
Write data to files

**Fields:**
- `file_path` (text): Output file path
- `file_format` (select): CSV, JSON, Parquet
- `append_mode` (boolean): Append to existing file

**Outputs:**
- None (terminal component)

## Adding Custom Components

To add a new component:

1. **Define metadata** in `backend/app/schemas.py`:
```python
{
    "type": "myComponent",
    "category": "Transform",
    "label": "My Component",
    "icon": "code",
    "inputs": 1,
    "outputs": 1,
    "fields": [
        {
            "name": "param1",
            "type": "text",
            "required": True,
            "default": ""
        }
    ]
}
```

2. **Implement component class** in `src/v1/engine/components/`:
```python
class MyComponent(BaseComponent):
    def __init__(self, config):
        super().__init__(config)
        self.param1 = config.get("param1")
    
    def process(self, input_data):
        # Your logic here
        return transformed_data
```

3. **Register in engine** in `src/v1/engine/engine.py`

4. **Frontend auto-loads** from metadata API

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (need 3.8+)
- Check dependencies: `pip list | grep -E "fastapi|pydantic|uvicorn"`
- Check port: Ensure port 8000 is free
- Check firewall: Allow localhost:8000

### Frontend won't load
- Check Node version: `node --version` (need 16+)
- Check npm packages: `npm list` in frontend folder
- Clear cache: `rm -rf node_modules && npm install`
- Check environment: Verify `.env.local` has correct API URL

### WebSocket connection fails
- Verify backend is running on 8000
- Check browser console for connection errors
- Ensure CORS is enabled (should be in main.py)
- Try different port if 8000 is blocked

### Job execution errors
- Check job export format with `/api/jobs/{job_id}/export`
- Verify component configurations are complete
- Check backend logs for detailed error messages
- Enable debug logging in `execution_service.py`

## Development

### Hot Reload
- Backend: Auto-reloads with Uvicorn (changes to run.py)
- Frontend: Vite provides instant HMR for all changes

### Building for Production

**Backend:**
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
```

**Frontend:**
```bash
cd frontend
npm run build
npm run preview  # Test production build locally
```

### Environment Variables

**Frontend** (`frontend/.env.local`):
```
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000
```

**Backend** (`backend/.env`):
```
DEBUG=True
JOBS_DIR=./jobs
LOG_LEVEL=INFO
```

## Contributing

To extend the UI:

1. **Add backend endpoint** in `backend/app/routes/`
2. **Add frontend component** in `frontend/src/components/`
3. **Update types** in `frontend/src/types/index.ts`
4. **Add API client method** in `frontend/src/services/api.ts`

## Performance Tips

- **Large jobs**: Use React Flow's `enableNonLinearFlow` for better performance
- **Many components**: Implement virtual scrolling in ComponentPalette
- **Heavy transformations**: Consider backend-side tMap compilation
- **Real-time updates**: Adjust WebSocket update frequency in `execution.py`

## Known Limitations

1. **Component logic** - Currently uses metadata-driven forms; complex logic needs backend work
2. **Distributed execution** - Not yet implemented; single-machine only
3. **Job scheduling** - Requires external scheduler integration
4. **Authentication** - No user authentication in current version
5. **Job versioning** - Overwrite on save; no version history

## Roadmap

- [ ] Job versioning and history
- [ ] User authentication and RBAC
- [ ] Advanced trigger editor UI
- [ ] Context variables UI
- [ ] Job statistics and metrics
- [ ] Distributed job execution
- [ ] Component testing framework
- [ ] Workflow templates library

## Support

For issues, questions, or suggestions:
1. Check the troubleshooting section above
2. Review API documentation
3. Check backend logs: `backend/run.py` output
4. Check frontend logs: Browser DevTools console

## License

This project extends the original RecDataPrep ETL engine with a web-based UI layer.
