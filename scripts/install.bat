@echo off
REM Double-clickable wrapper for install.ps1 -- PowerShell's default execution
REM policy blocks running .ps1 scripts directly on a fresh Windows install,
REM so this launches it with that restriction bypassed for this one process
REM only (does not change the system's execution policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
