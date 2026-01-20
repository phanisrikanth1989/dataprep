# Angular Frontend - Backend Integration Testing Guide

This guide helps verify that the Angular frontend is properly integrated with the FastAPI backend.

---

## 🎯 Pre-flight Checklist

### Step 1: Start Backend
```bash
cd backend
python run.py
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 2: Verify Backend is Running
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

### Step 3: Start Frontend
```bash
cd frontend-angular
npm install      # If not done yet
npm start
```

Expected output:
```
✓ Compiled successfully
Local:   http://localhost:4200/
```

---

## 🔍 Integration Test Scenarios

### Test 1: List Jobs
**Objective:** Verify API integration for job listing

**Steps:**
1. Open http://localhost:4200 in browser
2. Observe Job List page loading
3. Open Developer Tools (F12) → Network tab
4. Refresh page (Ctrl+R)
5. Look for API call: `GET http://localhost:4200/api/jobs`
6. Should proxy to `http://localhost:8000/api/jobs`

**Expected Result:**
- Job List page loads
- Jobs display (or "No jobs" message if empty)
- Network request shows 200 status

---

### Test 2: Create Job
**Objective:** Verify job creation API integration

**Steps:**
1. On Job List page, click "New Job" button
2. Fill in job name and click "Create"
3. In Network tab, look for `POST http://localhost:4200/api/jobs`
4. Response should contain new job ID

**Expected Result:**
- New job created successfully
- Redirects to job designer page
- No network errors

---

### Test 3: Load Components
**Objective:** Verify component registry integration

**Steps:**
1. On Job Designer page, observe Component Palette
2. In Network tab, look for `GET http://localhost:4200/api/components`
3. Should show list of available components by category

**Expected Result:**
- Components load from backend
- Palette shows organized categories (Transform, Data, etc.)
- No loading errors

---

### Test 4: Execute Job
**Objective:** Verify execution API and WebSocket integration

**Steps:**
1. On Job Designer page, click "Execute"
2. In Network tab, look for `POST http://localhost:4200/api/execution/start`
3. Should return taskId
4. Watch for WebSocket connection to `ws://localhost:8000/ws/execution/{taskId}`

**Expected Result:**
- Execution starts
- Real-time updates appear
- Progress bar updates
- Logs stream in real-time

---

### Test 5: Stop Execution
**Objective:** Verify execution stop API

**Steps:**
1. During execution, click "Stop Execution"
2. In Network tab, look for `POST http://localhost:4200/api/execution/{taskId}/stop`

**Expected Result:**
- Execution stops
- Status shows "STOPPED"
- No WebSocket errors

---

## 🧪 Browser DevTools Verification

### Console Tab
- [ ] No JavaScript errors (red icons)
- [ ] No CORS errors
- [ ] Check for service messages like "Connected to WebSocket"

### Network Tab
- [ ] All `/api/*` requests return 200-399 status
- [ ] API response times are < 500ms
- [ ] WebSocket connection shows "101 Switching Protocols"

### Application Tab
- [ ] LocalStorage: Check for any stored job data
- [ ] Cookies: Verify any session cookies

### Network WS (WebSocket)
- [ ] Connection shows "Connected"
- [ ] Messages flow in real-time
- [ ] No reconnection spam (> 1 per second)

---

## 🐛 Common Integration Issues & Fixes

### Issue: API Returns 404
**Cause:** Backend endpoint not found or proxy misconfigured

**Fix:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check proxy.conf.json has correct routes
3. Restart frontend: `npm start`

---

### Issue: CORS Errors
**Cause:** Browser blocking cross-origin requests

**Fix:**
1. Proxy is configured, so should not happen
2. Check Network tab → click failed request → Headers
3. Verify `Access-Control-Allow-Origin` header is present
4. Check backend CORS configuration

---

### Issue: WebSocket Connection Fails
**Cause:** WebSocket endpoint not available or wrong URL

**Fix:**
1. Check backend supports WebSocket (uses Socket.io)
2. Verify environment.ts has correct wsUrl: `ws://localhost:8000`
3. Check browser console for WebSocket errors
4. Verify port 8000 is accessible

---

### Issue: Job Data Not Loading
**Cause:** Backend database empty or API returns empty response

**Fix:**
1. Create a test job in backend: `curl -X POST http://localhost:8000/api/jobs -d '{"name":"test"}'`
2. Refresh frontend
3. Check Network tab for response
4. Verify job appears in UI

---

## 📊 API Endpoint Mapping

| Frontend | Backend | Method | Status |
|----------|---------|--------|--------|
| Job List | /api/jobs | GET | ✓ |
| Create Job | /api/jobs | POST | ✓ |
| Load Job | /api/jobs/{id} | GET | ✓ |
| Update Job | /api/jobs/{id} | PUT | ✓ |
| Delete Job | /api/jobs/{id} | DELETE | ✓ |
| List Components | /api/components | GET | ✓ |
| Get Component | /api/components/{type} | GET | ✓ |
| Start Execution | /api/execution/start | POST | ✓ |
| Get Status | /api/execution/{taskId} | GET | ✓ |
| Stop Execution | /api/execution/{taskId}/stop | POST | ✓ |
| Real-time Updates | /ws/execution/{taskId} | WS | ✓ |

---

## ✅ Full Integration Test Checklist

Use this checklist to verify complete integration:

**API Communication**
- [ ] Jobs load on home page
- [ ] Can create new job
- [ ] Can edit job
- [ ] Can delete job
- [ ] Components load in palette
- [ ] Can execute job
- [ ] Can stop execution

**WebSocket Streaming**
- [ ] Real-time updates during execution
- [ ] Progress bar updates in real-time
- [ ] Logs stream live
- [ ] Connection drops gracefully
- [ ] Auto-reconnect works

**Error Handling**
- [ ] Network errors show user message
- [ ] Backend errors propagate correctly
- [ ] Invalid input shows validation error
- [ ] Timeouts handled gracefully

**Performance**
- [ ] Page loads in < 2s
- [ ] API responses in < 500ms
- [ ] Real-time updates in < 100ms
- [ ] No console errors or warnings

---

## 🔐 Production Deployment

Before deploying, verify:

1. **Build production**
   ```bash
   npm run build
   ```

2. **Verify build succeeds**
   ```bash
   ls dist/recdataprep-angular/
   ```

3. **Test with production environment**
   ```typescript
   // src/environments/environment.prod.ts
   apiUrl: '/api'  // Relative URL
   wsUrl: window.location.origin.replace('http', 'ws')
   ```

4. **Deploy to web server**
   - Copy `dist/recdataprep-angular/*` to web root
   - Configure web server to serve `index.html` for routes
   - Ensure backend API is on same domain or CORS enabled

---

## 📞 Support

If integration issues persist:

1. Check browser console for errors
2. Check Network tab for failed requests
3. Verify backend is running and accessible
4. Check environment configuration
5. Review proxy.conf.json for correct routes
6. Restart both frontend and backend

---

## 🎯 Next Steps

After verifying integration:

1. Create custom ETL components
2. Build advanced canvas features
3. Add comprehensive unit tests
4. Deploy to production
5. Monitor real-world usage

---

**Last Updated:** Angular Migration Complete
**Status:** Production Ready ✅
