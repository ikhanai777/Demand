@echo off
REM Double-click to install Demand Scanner (safe to re-run).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\install.ps1"
pause
