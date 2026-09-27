@echo off
REM Double-click to start the Demand Dashboard and open it in your browser.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\start-dashboard.ps1" -Background -Open
if errorlevel 1 pause
