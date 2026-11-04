@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Local-only safe launcher: do not use any inherited paid AI API key.
set "DEEPSEEK_API_KEY="
set "FAULTMATE_NO_BROWSER="
cd /d "%~dp0"
if not exist "%~dp0FaultMateAI.exe" (
  echo [ERROR] FaultMateAI.exe not found. Keep the whole portable folder together.
  pause
  exit /b 1
)
"%~dp0FaultMateAI.exe"
if errorlevel 1 (
  echo [ERROR] FaultMate did not start. No system changes were requested.
  pause
  exit /b 1
)
exit /b 0
