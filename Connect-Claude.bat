@echo off
REM Double-click to connect Demand Scanner to Claude Desktop and Claude Code.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\connect-claude.ps1"
pause
