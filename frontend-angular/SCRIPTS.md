#!/usr/bin/env node

/**
 * RecDataPrep Angular Frontend - NPM Scripts Documentation
 * 
 * This file documents all available npm scripts and their usage.
 * 
 * All scripts are defined in package.json under "scripts" section.
 */

const scripts = {
  "start": {
    "command": "npm start",
    "alias": "ng serve",
    "description": "Start development server on http://localhost:4200",
    "when": "During development",
    "output": "Angular dev server running with hot reload"
  },
  
  "build": {
    "command": "npm run build",
    "alias": "ng build",
    "description": "Build production bundle (minified and optimized)",
    "when": "Before deployment",
    "output": "Optimized bundle in dist/recdataprep-angular/"
  },
  
  "test": {
    "command": "npm test",
    "alias": "ng test",
    "description": "Run unit tests with Jasmine/Karma",
    "when": "For testing code",
    "output": "Test results with coverage report"
  },
  
  "lint": {
    "command": "npm run lint",
    "alias": "ng lint",
    "description": "Lint code for style issues",
    "when": "For code quality check",
    "output": "List of linting issues"
  }
};

/**
 * DETAILED USAGE GUIDE
 */

console.log(`
╔═══════════════════════════════════════════════════════════════════╗
║  RecDataPrep Angular Frontend - NPM Scripts                      ║
╚═══════════════════════════════════════════════════════════════════╝

📦 AVAILABLE SCRIPTS:

1️⃣  DEVELOPMENT
    ─────────────────────────────────────────────────────────────
    npm start
    └─ Start development server
       • Runs on http://localhost:4200
       • Hot reload enabled
       • Proxy routes to backend (http://localhost:8000)
       • Press Ctrl+C to stop

2️⃣  BUILDING
    ─────────────────────────────────────────────────────────────
    npm run build
    └─ Build production bundle
       • Minified and optimized
       • Output: dist/recdataprep-angular/
       • Ready for deployment
       • Use: ng build --prod

3️⃣  TESTING
    ─────────────────────────────────────────────────────────────
    npm test
    └─ Run unit tests
       • Uses Jasmine test framework
       • Uses Karma test runner
       • Watch mode enabled by default
       • Press Ctrl+C to stop

4️⃣  CODE QUALITY
    ─────────────────────────────────────────────────────────────
    npm run lint
    └─ Lint code
       • Check code style
       • Find potential errors
       • Use --fix to auto-fix issues

═══════════════════════════════════════════════════════════════════

📋 EXPANDED COMMANDS:

Development Commands:
─────────────────────────────────────────────────────────────
  npm start
    • Default: ng serve
    • Opens on: http://localhost:4200
    
  ng serve --open
    • Automatically opens browser
    
  ng serve --port 4201
    • Use different port if 4200 in use
    
  ng serve --poll 1000
    • Enable polling if file watch not working

Building Commands:
─────────────────────────────────────────────────────────────
  npm run build
    • Default: ng build (development mode)
    • Size: Larger with source maps
    
  npm run build --prod
    • Production mode
    • Minified and optimized
    • Smaller bundle size
    • Better performance

Testing Commands:
─────────────────────────────────────────────────────────────
  npm test
    • Default: ng test (watch mode)
    • Runs Jasmine tests
    
  ng test --watch=false
    • Run once, don't watch
    
  ng test --browsers=Chrome
    • Specify browser (Chrome/Firefox/PhantomJS)
    
  ng test --code-coverage
    • Generate coverage report

Linting Commands:
─────────────────────────────────────────────────────────────
  npm run lint
    • Check code style issues
    
  ng lint --fix
    • Automatically fix issues

═══════════════════════════════════════════════════════════════════

🔧 ADDITIONAL COMMANDS:

Code Generation:
─────────────────────────────────────────────────────────────
  ng generate component name
    • Create new component
    
  ng generate service name
    • Create new service
    
  ng generate module name
    • Create new module

Utilities:
─────────────────────────────────────────────────────────────
  ng version
    • Show Angular CLI version
    
  npm install
    • Install dependencies
    
  npm update
    • Update packages
    
  npm outdated
    • Show outdated packages

═══════════════════════════════════════════════════════════════════

🚀 COMMON WORKFLOWS:

1. Starting Fresh:
   ───────────────────────────────────────────────────────────
   npm install
   npm start
   └─ Then navigate to http://localhost:4200

2. Development Cycle:
   ───────────────────────────────────────────────────────────
   npm start              # Start server
   [Make code changes]
   [Browser auto-reloads] # Hot reload
   npm test              # Run tests
   npm run lint          # Check code quality

3. Deployment:
   ───────────────────────────────────────────────────────────
   npm run lint          # Check code quality
   npm test              # Run tests
   npm run build         # Build production
   [Deploy dist/recdataprep-angular/]

4. Debugging:
   ───────────────────────────────────────────────────────────
   npm start             # Start dev server
   [Open DevTools - F12]
   [Sources tab - Debug TypeScript]
   [Console tab - Check logs]

═══════════════════════════════════════════════════════════════════

📊 SCRIPT ALIASES:

npm run dev      = npm start
npm run build    = ng build
npm run test     = ng test
npm run lint     = ng lint

Note: All commands can use 'npm run' prefix or run directly:
  npm start       (via npm run)
  ng serve        (if @angular/cli installed globally)

═══════════════════════════════════════════════════════════════════

💡 TIPS:

• Use npm start for development (preferred)
• Use ng serve if Angular CLI installed globally
• Browser automatically reloads on code changes
• Press Ctrl+C to stop any running command
• Check console for errors and warnings
• Use DevTools (F12) for debugging

═══════════════════════════════════════════════════════════════════

🔗 RELATED DOCUMENTATION:

• ANGULAR_SETUP.md         - Setup instructions
• COMMANDS.md              - Quick command reference
• INTEGRATION_TESTING.md   - Testing guide
• FILE_INVENTORY.md        - File reference
• package.json             - Dependency list

═══════════════════════════════════════════════════════════════════

For more info:
  • Angular: https://angular.io/
  • npm: https://www.npmjs.com/
  • ng docs: https://angular.io/cli

═══════════════════════════════════════════════════════════════════
`);

module.exports = scripts;
