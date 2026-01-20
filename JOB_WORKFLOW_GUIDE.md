# Job Workflow Guide

## Creating a New Job

### Step 1: Click "Create New Job"
- On the **Job List page**, click the **"+ Create New Job"** button in the left sidebar
- A modal dialog will appear with the following fields:
  - **Job Name** (Required): Name your job (e.g., "Customer Data Pipeline")
  - **Description** (Optional): Brief description of what the job does
  - **Version** (Optional): Version number (defaults to 1.0.0)

### Step 2: Configure Job Details
```
Example:
- Job Name: Customer Data Pipeline
- Description: Reads customer data, performs validation and enrichment
- Version: 1.0.0
```

### Step 3: Submit and Redirect
- Click **"Create"** button
- The new job is created and saved
- **Automatic redirect to Job Designer** window opens with your new job
- You can now start adding components and designing your ETL pipeline

## Job Designer Window

Once redirected to the Job Designer, you'll see:

### Left Sidebar (Repository)
- Job name
- Component count
- Connection count

### Center Canvas
- **Drag & drop components** from the right palette
- **Connect components** by drawing lines between them
- **Click on components** to configure them
- **Save Job** button to persist changes

### Right Sidebar (2 Tabs)
- **📦 Components Tab**: Browse available components by category
  - FILE: FileTouch, FileInputDelimited, FileOutputDelimited
  - Transform: FilterRows, Map, FilterColumns, etc.
- **🗂️ Metadata Browser Tab**: Browse database connections and schemas

### Bottom Config Panel
- **Configuration Tab**: Set component properties
- **Output Schema Tab**: Define output columns (for input components)

## Complete Workflow

```
1. Job List Page
   ↓
2. Click "+ Create New Job"
   ↓
3. Enter Job Details Modal
   ↓
4. Click "Create"
   ↓
5. Redirected to Job Designer
   ↓
6. Design Your Job:
   - Add components from palette
   - Configure each component
   - Connect components
   - Define schemas
   ↓
7. Click "Save Job"
   ↓
8. Job saved to jobs/{job_id}.json
   ↓
9. Click "Execute" to run the job (optional)
   ↓
10. Monitor execution in Execution Monitor
```

## Example: Create a Simple Data Pipeline

### Create Job
1. Click "+ Create New Job"
2. Enter:
   - Name: "Daily Customer Export"
   - Description: "Export customer data to CSV file"
   - Version: 1.0.0
3. Click "Create"

### Design Job (in Job Designer)

#### Step 1: Add FileInputDelimited Component
- Drag "file_input_delimited" from Components palette
- Click on it to configure:
  - File Path: `/data/customers.csv`
  - Delimiter: `,`
  - Encoding: UTF-8
- Click "Output Schema" tab:
  - Add columns: customer_id (Integer), name (String), email (String)

#### Step 2: Add FilterRows Component
- Drag "filter_rows" component
- Configure:
  - Condition: email is not empty
  - Connect output from FileInputDelimited

#### Step 3: Add FileOutputDelimited Component
- Drag "file_output_delimited" component
- Configure:
  - File Path: `/data/customers_export.csv`
  - Delimiter: `,`
  - Include Header: Yes
- Connect from FilterRows

#### Step 4: Connect Components
- Click on FileInputDelimited → drag to FilterRows (main output)
- Click on FilterRows → drag to FileOutputDelimited (main output)

#### Step 5: Save and Execute
- Click "Save Job" button
- Click "Execute" to run the pipeline
- Monitor execution in the execution panel

## Key Features

### Auto-Save
- Job configuration is automatically saved when you modify components
- JSON file updated in `jobs/job_{id}.json`

### Version Control
- Jobs are saved as JSON files
- Commit to Git for version history:
  ```bash
  git add jobs/
  git commit -m "Add customer export pipeline"
  ```

### Execution Tracking
- Click "Execute" to run the job
- Monitor real-time logs and statistics
- Track component execution time
- View success/failure status

### Schema Definition
- Define input/output schemas for each component
- Pass schema information between connected components
- Talend-like schema tab interface

## Troubleshooting

### "Create New Job" button not working?
- Ensure you're logged in (check top-right user menu)
- Check browser console for errors (F12)
- Verify backend is running on port 8000

### Job Designer not loading?
- Check if job ID is valid in URL: `/designer/{jobId}`
- Verify backend can load the job
- Check network tab for API errors

### Components not appearing?
- Ensure components are registered in backend
- Check if metadata browser shows connections (good sign backend is running)
- Refresh the page

### Job not saving?
- Click "Save Job" button explicitly
- Check console for errors
- Verify write permissions to jobs directory

## Navigation

```
Home (Job List)
  ├─ [Edit Job] → Job Designer
  ├─ [Execute Job] → Execution Monitor
  └─ [Create New Job] → Modal → Job Designer (auto)
```

## Environment Variables

Set these if needed:

```bash
# Backend
BACKEND_URL=http://localhost:8000

# Frontend  
API_BASE_URL=http://localhost:8000
```

## Next Steps After Creating Job

1. **Design**: Add components and configure pipeline
2. **Save**: Click "Save Job" to persist
3. **Test**: Click "Execute" to test run
4. **Commit**: `git add jobs/ && git commit -m "..."`
5. **Deploy**: Push to staging (UAT) for testing
6. **Release**: Tag and deploy to production

## Related Documentation

- [GIT_INTEGRATION_GUIDE.md](./GIT_INTEGRATION_GUIDE.md) - Version control & deployment
- [Component Documentation](./docs/) - Available components
- [API Reference](./backend/API.md) - Backend endpoints
