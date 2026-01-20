@echo off
REM RecDataPrep Angular Frontend - Backend Integration Verification (Windows)
REM This batch file checks if the backend is properly configured and running

setlocal enabledelayedexpansion

echo ======================================
echo RecDataPrep - Backend Integration Check
echo ======================================
echo.

REM Check if backend is running
echo 1. Checking if Backend is running on http://localhost:8000...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2; Write-Host '[OK] Backend is RUNNING' -ForegroundColor Green } catch { Write-Host '[ERROR] Backend is NOT RUNNING' -ForegroundColor Red; Write-Host 'Start backend with: cd backend && python run.py' }"

echo.
echo 2. Testing API Endpoints...
echo.

REM Health check
echo -n "   Health: "
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2; Write-Host '[OK]' -ForegroundColor Green -NoNewline } catch { Write-Host '[ERROR]' -ForegroundColor Red -NoNewline }"
echo.

REM List jobs
echo -n "   List Jobs (/api/jobs): "
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/jobs' -UseBasicParsing -TimeoutSec 2; Write-Host '[OK]' -ForegroundColor Green -NoNewline } catch { Write-Host '[ERROR]' -ForegroundColor Red -NoNewline }"
echo.

REM List components
echo -n "   List Components (/api/components): "
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/components' -UseBasicParsing -TimeoutSec 2; Write-Host '[OK]' -ForegroundColor Green -NoNewline } catch { Write-Host '[ERROR]' -ForegroundColor Red -NoNewline }"
echo.

echo.
echo 3. Checking Node.js and npm...

REM Check Node.js
where /q node
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js: %%i
) else (
    echo [ERROR] Node.js NOT installed
)

REM Check npm
where /q npm
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('npm --version') do echo [OK] npm: %%i
) else (
    echo [ERROR] npm NOT installed
)

echo.
echo 4. Checking Angular CLI...
where /q ng
if %ERRORLEVEL% EQU 0 (
    echo [OK] Angular CLI installed
) else (
    echo [WARNING] Angular CLI not installed globally
    echo Run: npm install -g @angular/cli
)

echo.
echo 5. Next Steps:
echo    1. cd frontend-angular
echo    2. npm install
echo    3. npm start
echo    4. Open http://localhost:4200
echo.
echo ======================================
echo Check complete!
echo ======================================
pause
