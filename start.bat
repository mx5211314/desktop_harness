@echo off
cd /d %~dp0
where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install Python 3.9+ with "Add Python to PATH" checked.
    pause
    exit /b 1
)
start "" pythonw "%~dp0desktop_pet.py"
