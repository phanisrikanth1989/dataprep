# RecDataPrep - Angular Frontend

**Complete Angular 17 Migration with Full Backend Integration**

[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()
[![Angular](https://img.shields.io/badge/Angular-17-red)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2-blue)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

---

## 📊 Project Overview

RecDataPrep is a visual ETL (Extract, Transform, Load) data preparation tool with a **new Angular-based frontend** fully integrated with the existing **FastAPI backend**.

### What's New?
✅ **React → Angular 17 Migration**  
✅ **Full Backend Integration Ready**  
✅ **Type-Safe Architecture**  
✅ **Real-Time Execution Monitoring**  
✅ **Production Ready**

---

## 🚀 Quick Start

### Prerequisites
- Node.js 14+ 
- npm 6+
- Backend running on http://localhost:8000

### Installation (3 Steps)

```bash
# 1. Install dependencies
npm install

# 2. Start development server
npm start

# 3. Open browser
# Navigate to http://localhost:4200
```

Done! 🎉

---

## 📁 Project Structure

```
frontend-angular/
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── models/types.ts        (TypeScript interfaces)
│   │   │   └── services/              (5 core services)
│   │   ├── pages/                     (Job List, Job Designer)
│   │   ├── shared/components/         (Reusable components)
│   │   └── app.*.ts                   (App setup)
│   ├── environments/                  (Dev/Prod config)
│   └── styles.scss                    (Global styles)
├── angular.json                       (Build config)
├── package.json                       (Dependencies)
├── proxy.conf.json                    (API proxy)
├── ANGULAR_SETUP.md                   📖 Read this first!
├── COMMANDS.md                        (Quick commands)
├── INTEGRATION_TESTING.md             (Testing guide)
└── FILE_INVENTORY.md                  (Complete file list)
```

---

## 🔌 Backend Integration

### All API Endpoints Mapped

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/jobs` | List all jobs |
| POST | `/api/jobs` | Create new job |
| GET | `/api/jobs/{id}` | Get job details |
| PUT | `/api/jobs/{id}` | Update job |
| DELETE | `/api/jobs/{id}` | Delete job |
| GET | `/api/components` | List components |
| POST | `/api/execution/start` | Start execution |
| GET | `/api/execution/{taskId}` | Get status |
| POST | `/api/execution/{taskId}/stop` | Stop execution |
| WS | `/ws/execution/{taskId}` | Real-time updates |

### Proxy Configuration
Automatically routes requests to backend:
```
/api/  → http://localhost:8000/api/
/ws/   → ws://localhost:8000/ws/
```

---

## 🎯 Key Features

### ✨ Job Management
- List, create, edit, delete jobs
- Export job configurations
- Full CRUD operations

### 🎨 Visual Designer
- Drag-drop component palette
- SVG-based canvas editor
- Node/edge visualization
- Real-time configuration

### 🔄 Execution Engine
- Start job execution
- Real-time progress monitoring
- Live logs and statistics
- Error handling and reporting

### 🧩 Component Registry
- Auto-discover components from backend
- Dynamic categorization
- Type-safe configuration forms

### 🔒 Type Safety
- Full TypeScript strict mode
- 100% typed services
- Type-safe API responses

---

## 📚 Documentation

Start with these files in order:

1. **[ANGULAR_SETUP.md](ANGULAR_SETUP.md)** ← Start here
   - Complete setup guide
   - Configuration instructions
   - Quick reference

2. **[COMMANDS.md](COMMANDS.md)**
   - All npm commands
   - Development workflow
   - Quick reference

3. **[INTEGRATION_TESTING.md](INTEGRATION_TESTING.md)**
   - API endpoint testing
   - WebSocket verification
   - Troubleshooting guide

4. **[FILE_INVENTORY.md](FILE_INVENTORY.md)**
   - Complete file reference
   - Code statistics
   - Architecture overview

---

## 💻 Development

### Start Development Server
```bash
npm start
# Opens http://localhost:4200 with hot reload
```

### Build for Production
```bash
npm run build
# Output: dist/recdataprep-angular/
```

### Run Tests
```bash
npm test
# Runs unit tests with Jasmine/Karma
```

### Lint Code
```bash
npm run lint
# Check code style and quality
```

---

## 🏗️ Architecture

### Services (Backend Integration)
- **ApiService** - REST client for all API calls
- **WebSocketService** - Real-time updates
- **JobService** - Job management logic
- **ExecutionService** - Execution orchestration
- **ComponentRegistryService** - Component discovery

### Components (UI)
- **Canvas** - Visual editor
- **ConfigPanel** - Dynamic forms
- **ComponentPalette** - Draggable toolbar
- **ExecutionMonitor** - Progress tracking
- **JobList** - Job management page
- **JobDesigner** - Main editor page

### Pages/Routes
- `/` - Job List
- `/designer/:jobId` - Job Designer
- `/execution/:taskId` - Execution Monitor

---

## 🔄 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Framework** | Angular | 17.0 |
| **Language** | TypeScript | 5.2 |
| **UI Components** | ng-zorro-antd | Latest |
| **HTTP** | HttpClientModule | Built-in |
| **Async** | RxJS | 7.8 |
| **WebSocket** | Socket.io | 4.5 |
| **Routing** | Angular Router | Built-in |
| **Build** | Angular CLI | 17.0 |

---

## ✅ Quality Assurance

### Code Quality
- TypeScript strict mode enabled
- All services fully typed
- Error handling implemented
- Production patterns followed

### Testing
- All API endpoints mapped
- WebSocket streaming verified
- Proxy configuration validated
- Error scenarios covered

### Documentation
- Complete setup guide
- API endpoint reference
- Integration testing guide
- File inventory

---

## 🐛 Troubleshooting

### "Cannot find module..."
```bash
npm install
```

### "Port 4200 already in use"
```bash
ng serve --port 4201
```

### "API calls failing"
- Check backend: `curl http://localhost:8000/health`
- Check proxy: `proxy.conf.json`
- Check environment: `src/environments/environment.ts`

### "WebSocket not connecting"
- Verify backend supports WebSocket
- Check WebSocket URL in services
- Review browser console for errors

---

## 📋 Backend Compatibility

✅ **Fully Compatible** with existing FastAPI backend

No backend changes required!

- API endpoints: Identical
- Database: Unchanged
- Component registry: Unchanged
- WebSocket protocol: Unchanged

This is a **drop-in replacement** for the React frontend.

---

## 🚀 Deployment

### Production Build
```bash
npm run build
```

### Deployment Steps
1. Run production build
2. Copy `dist/recdataprep-angular/` to web server
3. Configure web server for SPA routing
4. Set API URL in environment config
5. Deploy backend API

### Environment Configuration
Edit `src/environments/environment.prod.ts`:
```typescript
export const environment = {
  production: true,
  apiUrl: '/api',
  wsUrl: window.location.origin.replace('http', 'ws')
};
```

---

## 📞 Support

### Checking Backend Connection
```bash
# Windows
verify-backend.bat

# macOS/Linux
bash verify-backend.sh
```

### View Live Requests
1. Open DevTools (F12)
2. Go to Network tab
3. Perform an action
4. Check API calls

### Debug in Browser
1. Open DevTools (F12)
2. Go to Sources tab
3. Set breakpoints in TypeScript
4. Step through code

---

## 📦 Dependencies

**38 npm packages** including:
- @angular/core (17.0)
- @angular/common (17.0)
- @angular/platform-browser (17.0)
- @angular/router (17.0)
- ng-zorro-antd (latest)
- rxjs (7.8)
- socket.io-client (4.5)
- typescript (5.2)

See [package.json](package.json) for complete list.

---

## 🔗 Quick Links

- **[Angular Documentation](https://angular.io/)**
- **[ng-zorro-antd](https://ng.ant.design/)**
- **[RxJS Documentation](https://rxjs.dev/)**
- **[Socket.io Client](https://socket.io/)**
- **[TypeScript Handbook](https://www.typescriptlang.org/docs/)**

---

## 📝 Notes

### Frontend Migration
- ✅ React 18 → Angular 17
- ✅ Vite → Angular CLI
- ✅ Zustand → Services + RxJS
- ✅ Axios → HttpClientModule

### Backend Status
- ✅ No changes required
- ✅ All APIs compatible
- ✅ Database unchanged
- ✅ Component registry unchanged

---

## 🎉 Summary

The Angular frontend is **100% ready for development and production**.

**Next Steps:**
1. Read [ANGULAR_SETUP.md](ANGULAR_SETUP.md)
2. Run `npm install && npm start`
3. Navigate to http://localhost:4200
4. Start building custom components!

---

## 📄 License

MIT License - See LICENSE file for details

---

## 👥 Contributors

Created for RecDataPrep Angular Migration

**Status:** ✅ Production Ready  
**Version:** 1.0  
**Last Updated:** Angular 17 Migration Complete

---

**Need help?** Check the documentation files in order:
1. [ANGULAR_SETUP.md](ANGULAR_SETUP.md) - Setup guide
2. [COMMANDS.md](COMMANDS.md) - Command reference
3. [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md) - Testing guide
4. [FILE_INVENTORY.md](FILE_INVENTORY.md) - File reference

**Ready to start?** Run:
```bash
npm install && npm start
```

Then open http://localhost:4200 in your browser! 🚀
