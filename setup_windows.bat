@echo off
title ProcureAI Setup

echo Creating Python environment...
cd /d "%~dp0backend"

python -m venv .venv
if errorlevel 1 (
    echo ERROR: Could not create the Python environment.
    pause
    exit /b 1
)

call .venv\Scripts\activate
if errorlevel 1 (
    echo ERROR: Could not activate the Python environment.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Could not upgrade pip.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Python package installation failed.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Installing frontend packages...
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed.
    echo Confirm that Node.js is installed by running: node --version
    pause
    exit /b 1
)

echo Generating sample quotation PDFs...
backend\.venv\Scripts\python.exe scripts\generate_samples.py
if errorlevel 1 (
    echo ERROR: Sample quotation generation failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo ProcureAI setup completed successfully!
echo ========================================
echo.
echo Now double-click run_windows.bat
pause