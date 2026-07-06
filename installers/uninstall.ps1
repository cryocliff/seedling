# Fully removes seedling: the managed folder AND the $PROFILE hook line.
$ErrorActionPreference = "Stop"

$SeedlingHome = if ($env:SEEDLING_HOME) { $env:SEEDLING_HOME } else { Join-Path $HOME "seedling" }

if (Test-Path $PROFILE) {
    # Match any line sourcing a seed shell script from under the seedling
    # home -- not just the exact current hook text -- so hooks written by
    # older seedling layouts (e.g. ~\seedling\shell\ before it moved under
    # system\) are cleaned up too instead of erroring in every new shell.
    $lines = Get-Content $PROFILE | Where-Object {
        -not ($_.Contains($SeedlingHome) -and ($_ -match "seed\.(ps1|sh)")) -and $_.Trim() -ne "# seedling"
    }
    Set-Content -Path $PROFILE -Value $lines
    Write-Host "Removed seedling hook from $PROFILE"
}

if (Test-Path $SeedlingHome) {
    Remove-Item -Recurse -Force $SeedlingHome
    Write-Host "Removed $SeedlingHome"
}

Write-Host "seedling fully uninstalled. Open a new terminal for it to take effect."
