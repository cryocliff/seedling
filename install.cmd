@echo off
rem Double-click this file, or run `.\install.cmd` -- no PowerShell flags to
rem remember. Batch files aren't subject to PowerShell's script execution
rem policy, so this launches install.ps1 with the bypass already applied,
rem scoped to just this one run (it does NOT change your system's policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
    pause
    exit /b 1
)

rem `seed` is a PowerShell function defined in your $PROFILE. This window is
rem plain cmd.exe (and install.ps1 itself just ran with -NoProfile besides),
rem so `seed` can never work here no matter how install.cmd was launched.
rem Open a fresh, ordinary PowerShell window instead -- its profile loads
rem automatically, so `seed` is ready immediately -- with a short welcome
rem banner, and leave it open (-NoExit) so there's an actual usable prompt
rem right after install finishes.
start "seedling" powershell -NoLogo -NoExit -Command "Write-Host ''; Write-Host 'seedling is installed and ready.' -ForegroundColor Green; Write-Host ''; Write-Host 'Try:'; Write-Host '  seed python 312          # install a base Python interpreter'; Write-Host '  seed venv myproject       # create a venv off it'; Write-Host '  seed activate myproject   # activate it in this shell'; Write-Host '  seed vscode               # install (once) + open a self-contained VS Code'; Write-Host '  seed summary              # see everything seedling has installed'; Write-Host ''; Write-Host 'Run seed -h for the full command list.' -ForegroundColor DarkGray; Write-Host ''"
