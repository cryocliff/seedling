@echo off
rem Double-click this file, or run `.\install.cmd` -- no PowerShell flags to
rem remember. Batch files aren't subject to PowerShell's script execution
rem policy, so this launches install.ps1 with the bypass already applied,
rem scoped to just this one run (it does NOT change your system's policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 pause
