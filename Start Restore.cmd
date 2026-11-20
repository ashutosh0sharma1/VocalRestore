@echo off
cd /d "%~dp0"
if exist "dist\desktop\VocalRestore.exe" (
  start "" "dist\desktop\VocalRestore.exe"
  exit /b 0
)
if defined RESTORE_PYTHON (
  "%RESTORE_PYTHON%" restore.py
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" restore.py
) else (
  python restore.py
)
if errorlevel 1 pause
