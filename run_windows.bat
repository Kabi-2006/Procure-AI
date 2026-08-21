@echo off
title ProcureAI Launcher
echo Starting ProcureAI backend...
start "ProcureAI Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
echo Starting ProcureAI frontend...
start "ProcureAI Frontend" cmd /k "cd /d %~dp0 && npm run dev"
echo.
echo Open http://localhost:5173 after both windows are ready.
pause
