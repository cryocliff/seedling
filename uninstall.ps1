# Fully removes seedling: the managed folder AND the $PROFILE hook line.
$ErrorActionPreference = "Stop"

$SeedlingHome = if ($env:SEEDLING_HOME) { $env:SEEDLING_HOME } else { Join-Path $HOME "seedling" }
$seedPs1 = Join-Path $SeedlingHome "system\shell\seed.ps1"
$hookLine = ". `"$seedPs1`""

if (Test-Path $PROFILE) {
    $lines = Get-Content $PROFILE | Where-Object { $_ -ne $hookLine -and $_ -ne "# seedling" }
    Set-Content -Path $PROFILE -Value $lines
    Write-Host "Removed seedling hook from $PROFILE"
}

if (Test-Path $SeedlingHome) {
    Remove-Item -Recurse -Force $SeedlingHome
    Write-Host "Removed $SeedlingHome"
}

Write-Host "seedling fully uninstalled. Open a new terminal for it to take effect."
