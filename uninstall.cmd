@echo off
rem Double-click this file, or run `.\uninstall.cmd` -- no PowerShell flags
rem to remember.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
if errorlevel 1 pause
