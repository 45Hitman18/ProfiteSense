@echo off
title ProfitSense Launcher
echo ========================================================
echo   Launching ProfitSense (FastAPI Backend + Vite Frontend)
echo ========================================================
echo.

:: Launch Backend in its own window
start "ProfitSense Backend [FastAPI:8000]" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: Launch Frontend in its own window
start "ProfitSense Frontend [Vite:5173]" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Backend and Frontend have been started!
echo.
echo - Backend:  http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)
echo - Frontend: http://localhost:5173
echo.
echo You can close this window now.
pause
