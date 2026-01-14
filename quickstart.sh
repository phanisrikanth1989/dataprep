#!/bin/bash

echo "========================================"
echo "RecDataPrep UI - Quick Start (Unix/Mac)"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed or not in PATH"
    exit 1
fi

echo "Python and Node.js found!"
echo ""

# Setup Backend
echo "[1/4] Setting up backend..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo "Backend setup complete!"

# Setup Frontend
echo ""
echo "[2/4] Setting up frontend..."
cd ../frontend
npm install --silent
echo "Frontend setup complete!"

echo ""
echo "[3/4] Creating .env files..."
if [ ! -f "backend/.env" ]; then
    touch backend/.env
fi
if [ ! -f "frontend/.env.local" ]; then
    echo "VITE_API_URL=http://localhost:8000/api" > frontend/.env.local
    echo "VITE_WS_URL=ws://localhost:8000" >> frontend/.env.local
fi
echo "Configuration files created!"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To start the servers:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  python run.py"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:5173"
echo ""
