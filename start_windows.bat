@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title FaultMate AI - P7.2 Final
if not exist ".venv\Scripts\python.exe" (
  echo [FaultMate] Preparing local Python environment...
  call "%~dp0setup_windows.bat" --auto
  if errorlevel 1 goto failed
)
"%~dp0.venv\Scripts\python.exe" -c "import fastapi,uvicorn" >nul 2>&1
if errorlevel 1 (
  echo [FaultMate] Python dependencies missing. Repairing environment...
  call "%~dp0setup_windows.bat" --auto
  if errorlevel 1 goto failed
)
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\start.py"
if errorlevel 1 goto failed
exit /b 0
:failed
echo [ERROR] FaultMate did not start. Review messages above.
pause
exit /b 1
