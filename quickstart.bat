@echo off
echo ========================================
echo RecDataPrep UI - Quick Start (Windows)
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Node.js is not installed or not in PATH
    pause
    exit /b 1
)

echo Python and Node.js found!
echo.

REM Setup Backend
echo [1/4] Setting up backend...
cd backend
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo Backend setup complete!

REM Setup Frontend
echo.
echo [2/4] Setting up frontend...
cd ..\frontend
call npm install --silent
echo Frontend setup complete!

echo.
echo [3/4] Creating .env files...
if not exist backend\.env (
    echo > backend\.env
)
if not exist frontend\.env.local (
    echo VITE_API_URL=http://localhost:8000/api > frontend\.env.local
    echo VITE_WS_URL=ws://localhost:8000 >> frontend\.env.local
)
echo Configuration files created!

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To start the servers:
echo.
echo Terminal 1 (Backend):
echo   cd backend
echo   venv\Scripts\activate
echo   python run.py
echo.
echo Terminal 2 (Frontend):
echo   cd frontend
echo   npm run dev
echo.
echo Then open: http://localhost:5173
echo.
pause
