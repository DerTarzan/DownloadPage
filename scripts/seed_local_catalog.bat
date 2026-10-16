@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0seed_local_catalog.ps1"
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)
