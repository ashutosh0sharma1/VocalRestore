@echo off
cd /d "%~dp0"
if defined RESTORE_PYTHON (
  "%RESTORE_PYTHON%" restore.py
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" restore.py
) else (
  python restore.py
)
if errorlevel 1 pause
