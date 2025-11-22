@echo off
REM Script to run main.py with automatic dependency installation for Windows
REM This script will install missing libraries automatically if needed

setlocal enabledelayedexpansion

echo Starting Dainn Screen Translator...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo Error: Python is not installed or not in PATH
        exit /b 1
    )
    set PYTHON_CMD=python3
) else (
    set PYTHON_CMD=python
)

echo Using Python:
%PYTHON_CMD% --version

REM Check if pip is installed
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo Error: pip is not installed. Please install pip first.
    exit /b 1
)

REM Install requirements from requirements.txt if it exists
if exist "requirements.txt" (
    echo Installing dependencies from requirements.txt...
    %PYTHON_CMD% -m pip install -q --upgrade pip 2>nul
    %PYTHON_CMD% -m pip install -q -r requirements.txt 2>nul
    if errorlevel 1 (
        echo Warning: Some packages from requirements.txt failed to install
    )
    echo Dependencies check complete
    echo.
) else (
    echo Warning: requirements.txt not found, skipping initial dependency installation
)

REM Check if run_with_deps.py exists, if so use it
if exist "run_with_deps.py" (
    echo Running with dependency auto-installer...
    echo.
    %PYTHON_CMD% run_with_deps.py
    exit /b %errorlevel%
)

REM Fallback: Simple approach - just run main.py
echo Running main.py...
echo.
%PYTHON_CMD% main.py
exit /b %errorlevel%

