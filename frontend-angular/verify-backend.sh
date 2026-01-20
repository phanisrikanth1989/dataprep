#!/bin/bash

# RecDataPrep Angular Frontend - Backend Integration Verification
# This script checks if the backend is properly configured and running

echo "======================================"
echo "RecDataPrep - Backend Integration Check"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backend is running
echo "1️⃣  Checking if Backend is running on http://localhost:8000..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is RUNNING${NC}"
else
    echo -e "${RED}✗ Backend is NOT RUNNING${NC}"
    echo "   Start backend with: cd backend && python run.py"
    echo ""
fi

# Check API endpoints
echo ""
echo "2️⃣  Testing API Endpoints..."
echo ""

# Health check
echo -n "   Health: "
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# List jobs
echo -n "   List Jobs (/api/jobs): "
if curl -s http://localhost:8000/api/jobs > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# List components
echo -n "   List Components (/api/components): "
if curl -s http://localhost:8000/api/components > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "3️⃣  Checking Node.js and npm..."
if command -v node &> /dev/null; then
    echo -e "   ${GREEN}✓ Node.js installed:${NC} $(node --version)"
else
    echo -e "   ${RED}✗ Node.js NOT installed${NC}"
fi

if command -v npm &> /dev/null; then
    echo -e "   ${GREEN}✓ npm installed:${NC} $(npm --version)"
else
    echo -e "   ${RED}✗ npm NOT installed${NC}"
fi

echo ""
echo "4️⃣  Checking Angular CLI..."
if command -v ng &> /dev/null; then
    echo -e "   ${GREEN}✓ Angular CLI installed:${NC} $(ng version 2>/dev/null | head -1)"
else
    echo -e "   ${YELLOW}⚠ Angular CLI not installed globally${NC}"
    echo "   Run: npm install -g @angular/cli"
fi

echo ""
echo "5️⃣  Next Steps:"
echo "   1. cd frontend-angular"
echo "   2. npm install"
echo "   3. npm start"
echo "   4. Open http://localhost:4200"
echo ""
echo "======================================"
echo "Check complete!"
echo "======================================"
