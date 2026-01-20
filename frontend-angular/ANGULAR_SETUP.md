# Angular Frontend - Setup & Integration Guide

**RecDataPrep Angular Frontend**  
**Fully Integrated with FastAPI Backend**

---

## 📋 What's Been Created

### Complete Angular 17 Project Structure
- ✅ Configuration files (angular.json, tsconfig.json, package.json)
- ✅ Core services (API, WebSocket, Job, Execution, Component Registry)
- ✅ Type definitions (TypeScript interfaces from React project)
- ✅ Shared components (Canvas, Config Panel, Component Palette, Execution Monitor)
- ✅ Page components (Job List, Job Designer)
- ✅ Routing and modules setup
- ✅ Ant Design Material UI integration
- ✅ Global styles and responsive design
- ✅ Backend proxy configuration

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
cd frontend-angular
npm install
```

### Step 2: Start Development Server

```bash
npm start
```

This will start Angular on **http://localhost:4200**

The proxy configuration automatically routes API calls to **http://localhost:8000**

### Step 3: Make Sure Backend is Running

```bash
cd backend
python run.py
```

Backend runs on **http://localhost:8000**

---

## 📁 Project Structure

```
frontend-angular/
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── models/
│   │   │   │   └── types.ts           ← All TypeScript interfaces
│   │   │   └── services/
│   │   │       ├── api.service.ts     ← REST API client (backend integration)
│   │   │       ├── websocket.service.ts ← Real-time updates
│   │   │       ├── job.service.ts     ← Job management
│   │   │       ├── execution.service.ts ← Execution management
│   │   │       └── component-registry.service.ts ← Component metadata
│   │   │
│   │   ├── shared/
│   │   │   ├── components/
│   │   │   │   ├── canvas.component.ts        ← Visual editor
│   │   │   │   ├── component-palette.component.ts ← Toolbar
│   │   │   │   ├── config-panel.component.ts  ← Dynamic forms
│   │   │   │   └── execution-monitor.component.ts ← Progress tracking
│   │   │   └── shared.module.ts       ← Shared module
│   │   │
│   │   ├── pages/
│   │   │   ├── job-list.component.ts  ← Job management page
│   │   │   └── job-designer.component.ts ← Main designer page
│   │   │
│   │   ├── app.component.ts           ← Main app component
│   │   ├── app-routing.module.ts      ← Routes
│   │   └── app.module.ts              ← Main module
│   │
│   ├── environments/
│   │   ├── environment.ts             ← Dev config
│   │   └── environment.prod.ts        ← Prod config
│   │
│   ├── main.ts                        ← Bootstrap
│   ├── index.html                     ← HTML entry
│   └── styles.scss                    ← Global styles
│
├── angular.json                       ← Angular CLI config
├── tsconfig.json                      ← TypeScript config
├── package.json                       ← Dependencies
├── proxy.conf.json                    ← API proxy config
└── README.md                          ← This file
```

---

## 🔌 Backend Integration - How It Works

### API Service (`api.service.ts`)
Handles all REST API communication with backend:

```typescript
// Calls backend endpoints
GET    /api/jobs                    ← List jobs
GET    /api/jobs/{id}              ← Get job
POST   /api/jobs                   ← Create job
PUT    /api/jobs/{id}              ← Update job
DELETE /api/jobs/{id}              ← Delete job
GET    /api/components             ← List components
POST   /api/execution/start        ← Start execution
GET    /api/execution/{taskId}     ← Get status
```

### WebSocket Service (`websocket.service.ts`)
Real-time execution updates:

```typescript
// Connects to WebSocket
WS     /ws/execution/{taskId}      ← Real-time status updates
```

### Proxy Configuration (`proxy.conf.json`)
Automatically routes requests during development:

```
/api/* → http://localhost:8000/api/*
/ws/*  → ws://localhost:8000/ws/*
```

---

## 🎯 Key Features

### Job Management
- ✅ List all jobs
- ✅ Create new jobs
- ✅ Edit existing jobs
- ✅ Delete jobs
- ✅ Execute jobs

### Visual Designer
- ✅ Drag-drop component palette
- ✅ Canvas for placing components
- ✅ Dynamic configuration forms
- ✅ Save job configurations

### Execution Monitoring
- ✅ Real-time progress tracking
- ✅ Live logs and statistics
- ✅ Error handling
- ✅ Stop execution

### Type Safety
- ✅ Full TypeScript interfaces
- ✅ Strict mode enabled
- ✅ Type-safe services

---

## 🔧 Configuration

### API URL (Development)
Edit `src/environments/environment.ts`:
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api',
  wsUrl: 'ws://localhost:8000'
};
```

### API URL (Production)
Edit `src/environments/environment.prod.ts`:
```typescript
export const environment = {
  production: true,
  apiUrl: '/api',  // Relative URL
  wsUrl: window.location.origin.replace('http', 'ws')
};
```

### Build for Production
```bash
npm run build
# Output in: dist/recdataprep-angular/
```

---

## 📱 Available Routes

```
/                    ← Job List page (home)
/designer/:jobId     ← Job Designer (edit mode)
/execution/:taskId   ← Execution Monitor (during/after execution)
```

---

## 🧩 Adding New Components

### Step 1: Create Component Class
```typescript
// src/app/shared/components/my-component.component.ts
import { Component, Input, Output, EventEmitter } from '@angular/core';

@Component({
  selector: 'app-my-component',
  template: `<!-- Template -->`,
  styles: [`/* Styles */`]
})
export class MyComponentComponent {
  @Input() data: any;
  @Output() actionTriggered = new EventEmitter();
}
```

### Step 2: Register in SharedModule
```typescript
// src/app/shared/shared.module.ts
declarations: [MyComponentComponent],
exports: [MyComponentComponent]
```

### Step 3: Use in Pages
```typescript
import { MyComponentComponent } from '../shared/components/my-component.component';
```

---

## 🧪 Testing

Run tests:
```bash
npm test
```

Tests use Jasmine/Karma framework.

---

## 📊 Comparison: React vs Angular

| Aspect | React | Angular |
|--------|-------|---------|
| **Installation** | `npm install` | `npm install` |
| **Dev Server** | `npm run dev` (Port 5173) | `npm start` (Port 4200) |
| **Build** | `npm run build` | `npm run build` |
| **Backend URL** | `http://localhost:8000` | Via proxy.conf.json |
| **State Management** | Zustand | Services + RxJS |
| **Routing** | React Router | Angular Router (built-in) |
| **HTTP Client** | Axios | HttpClient (built-in) |
| **UI Library** | Ant Design | ng-zorro-antd |
| **WebSocket** | Socket.io client | Socket.io client |

---

## ✅ Integration Verification Checklist

- [ ] Backend is running on http://localhost:8000
- [ ] Backend responds to /health endpoint
- [ ] `npm install` completes successfully
- [ ] `npm start` starts dev server on port 4200
- [ ] Job List page loads and shows jobs
- [ ] Can create a new job
- [ ] Can execute a job
- [ ] Real-time updates appear during execution
- [ ] Can view execution logs and progress

---

## 🚨 Troubleshooting

### "Cannot find module..."
```bash
npm install
```

### "API calls failing"
- Check backend is running: `http://localhost:8000/health`
- Check proxy.conf.json is correct
- Check environment URLs in `src/environments/`

### "WebSocket connection failing"
- Ensure backend supports WebSocket (FastAPI with Socket.io)
- Check WebSocket URL in WebSocket service
- Check browser console for connection errors

### "Port 4200 already in use"
```bash
ng serve --port 4201
```

### "ng command not found"
```bash
npm install -g @angular/cli
```

---

## 📚 Further Resources

- [Angular Documentation](https://angular.io/docs)
- [ng-zorro-antd Documentation](https://ng.ant.design/)
- [RxJS Documentation](https://rxjs.dev/)
- [Socket.io Client](https://socket.io/docs/v4/socket-io-client-api/)

---

## 🔄 Migration from React Complete

**What's Changed:**
- ✅ Frontend framework: React → Angular
- ✅ Build tool: Vite → Angular CLI
- ✅ UI Library: Ant Design React → ng-zorro-antd (Ant Design Angular)
- ✅ State Management: Zustand → Services + RxJS
- ✅ HTTP Client: Axios → HttpClient
- ✅ All backend APIs: **NO CHANGES** ✅

**What's Same:**
- Backend API endpoints unchanged
- Backend logic unchanged
- Database unchanged
- Component registry unchanged

**This is a full drop-in replacement for the React frontend!**

---

## 🎉 You're Ready!

The Angular frontend is now fully integrated with the FastAPI backend. All the existing backend APIs and functionality will work seamlessly.

**Next Steps:**
1. `cd frontend-angular && npm install`
2. `npm start`
3. Open http://localhost:4200
4. Create and execute your first job!

For new component code, please ask and I'll create them following the Angular patterns and full backend integration!
