# RecDataPrep Angular Frontend
# Quick Command Reference

## 📦 Installation
npm install                    # Install all dependencies

## 🚀 Development
npm start                      # Start dev server (port 4200)
ng serve                       # Alternative: start dev server
ng serve --open               # Start dev server and open browser
ng serve --port 4201          # Use different port

## 🏗️ Build
npm run build                 # Build for production
ng build                      # Alternative: build for production
ng build --prod               # Production build with optimizations

## 🧪 Testing
npm test                      # Run unit tests
ng test                       # Alternative: run unit tests
ng test --watch=false         # Run tests once
ng test --browsers=Chrome     # Run tests in Chrome

## 📊 Development Tools
ng lint                       # Lint code
ng generate component name    # Generate component
ng generate service name      # Generate service
ng generate module name       # Generate module

## 📱 Preview
npm start                     # Start server, then navigate to http://localhost:4200

## 🐛 Debugging
# In browser:
# 1. Open DevTools (F12)
# 2. Check Console tab for logs
# 3. Check Network tab for API calls
# 4. Check Sources tab to debug TypeScript

# Check backend connection:
curl http://localhost:8000/health

# Check API endpoints:
curl http://localhost:8000/api/jobs
curl http://localhost:8000/api/components

## 🔄 Reset & Clean
rm -r node_modules            # Remove dependencies
npm cache clean --force       # Clean cache
npm install                   # Reinstall

## 📝 Common Tasks

### Stop Development Server
Press Ctrl+C in terminal

### Update Dependencies
npm update

### Install Specific Package
npm install package-name

### Remove Package
npm uninstall package-name

## 🌍 Environment Variables

Edit these files for configuration:
- src/environments/environment.ts      (Development)
- src/environments/environment.prod.ts (Production)

Current settings:
- API: http://localhost:8000/api
- WebSocket: ws://localhost:8000
- Dev Port: 4200
- Proxy: Enabled for /api and /ws routes
