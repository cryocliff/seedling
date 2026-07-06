# seedling installer (PowerShell) -- mirrors how `uv` installs itself.
# Requires nothing pre-installed; works on a stock Windows PowerShell / pwsh.
#
# Usage (from a local checkout of this repo):
#   .\install.ps1
#
# Usage (remote):
#   irm https://raw.githubusercontent.com/cryocliff/seedling/main/install.ps1 | iex
#   $env:SEEDLING_REPO = "https://github.com/someone/fork.git"; irm .../install.ps1 | iex

$ErrorActionPreference = "Stop"

# Built-in defaults. seedling.conf ships with these same values written
# out, so a conf that still matches them changes nothing -- only edited
# values have any effect. The baked-in copies exist for the piped
# one-liner install, where no local seedling.conf exists yet to consult.
$DefaultSeedlingRepo = "https://github.com/cryocliff/seedling.git"
$DefaultVenvPackages = "ipython,ruff"

function Info($msg)  { Write-Host "==> $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "!! $msg" -ForegroundColor Yellow }
function Die($msg)   { Write-Host "error: $msg" -ForegroundColor Red; exit 1 }

# seedling.conf is the deployment config: organizations distributing
# seedling from their own git host or a network drive set the source (and
# any install-time settings) there ONCE, and their users install with no
# flags or env vars. Standard internet installs ship a conf whose values
# match the baked-in defaults, so nothing changes for them.
function Read-SeedlingConf($path) {
    $conf = @{}
    if ($path -and (Test-Path $path)) {
        foreach ($line in Get-Content $path) {
            if ($line -match '^\s*([A-Z_]+)\s*=\s*"([^"]*)"\s*$') {
                $conf[$Matches[1]] = $Matches[2]
            }
        }
    }
    return $conf
}

# ---------------------------------------------------------------------------
# 1. Locate the seedling source (local checkout next to this script, or clone)
# ---------------------------------------------------------------------------
# $MyInvocation.MyCommand.Path is $null when this script is run via
# `irm ... | iex` (there's no backing file for a piped-in script), so guard
# against that instead of calling Split-Path on a null value.
$ScriptPath = $MyInvocation.MyCommand.Path
$ScriptDir = if ($ScriptPath) { Split-Path -Parent $ScriptPath } else { $null }

$HasLocalCheckout = $false
if ($ScriptDir) {
    if (Test-Path (Join-Path $ScriptDir "pyproject.toml")) {
        $HasLocalCheckout = $true
    }
}

$Conf = if ($ScriptDir) { Read-SeedlingConf (Join-Path $ScriptDir "seedling.conf") } else { @{} }

# Source resolution: SEEDLING_REPO env var (one-run override) beats
# seedling.conf, which beats the baked-in default.
$SeedlingRepo = if ($env:SEEDLING_REPO) {
    $env:SEEDLING_REPO
} elseif ($Conf["SEEDLING_REPO_URL"]) {
    $Conf["SEEDLING_REPO_URL"]
} else {
    $DefaultSeedlingRepo
}

# Home resolution follows the same order. A leading "~" in the conf value
# means the installing user's home directory.
$SeedlingHome = if ($env:SEEDLING_HOME) {
    $env:SEEDLING_HOME
} elseif ($Conf["SEEDLING_HOME_DIR"]) {
    $dir = $Conf["SEEDLING_HOME_DIR"]
    if ($dir -eq "~") { $HOME }
    elseif ($dir.StartsWith("~/") -or $dir.StartsWith("~\")) { Join-Path $HOME $dir.Substring(2) }
    else { $dir }
} else {
    Join-Path $HOME "seedling"
}

$InstalledFromDir = $null
if ($HasLocalCheckout) {
    $OriginalSrc = $ScriptDir
    $CleanupOriginalSrc = $false
} elseif ((Test-Path $SeedlingRepo -PathType Container) -and (Test-Path (Join-Path $SeedlingRepo "pyproject.toml"))) {
    # SEEDLING_REPO can be a plain directory instead of a git URL -- e.g. a
    # network drive holding a copy of this repo, on machines/networks with
    # no GitHub access at all.
    Info "Installing from directory $SeedlingRepo ..."
    $OriginalSrc = $SeedlingRepo
    $CleanupOriginalSrc = $false
    $InstalledFromDir = $SeedlingRepo
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git is required to clone $SeedlingRepo." }
    $OriginalSrc = Join-Path ([System.IO.Path]::GetTempPath()) ("seedling-src-" + [System.Guid]::NewGuid())
    $CleanupOriginalSrc = $true
    Info "Cloning $SeedlingRepo ..."
    git clone --depth 1 $SeedlingRepo $OriginalSrc
}

# ---------------------------------------------------------------------------
# 2. Lay out the folder structure
# ---------------------------------------------------------------------------
Info "Setting up $SeedlingHome"
$null = New-Item -ItemType Directory -Force -Path `
    "$SeedlingHome\system\bin", `
    "$SeedlingHome\system\config", `
    "$SeedlingHome\system\shell", `
    "$SeedlingHome\python\base", `
    "$SeedlingHome\python\venvs", `
    "$SeedlingHome\extensions", `
    "$SeedlingHome\repo"

# ---------------------------------------------------------------------------
# 2b. Copy the source INTO seedling itself. This is what makes updates
#     explicit: seed-cli gets installed from $SeedlingHome\src, a copy that
#     nothing outside of `seed update-commands` ever touches again. Deleting,
#     moving, or `git pull`-ing wherever you originally downloaded this from
#     has zero effect on the installed commands after this point.
# ---------------------------------------------------------------------------
Info "Copying source into $SeedlingHome\system\src ..."
$SrcDir = Join-Path $SeedlingHome "system\src"
if (Test-Path $SrcDir) { Remove-Item -Recurse -Force $SrcDir }
Copy-Item -Recurse -Force $OriginalSrc $SrcDir

if ($CleanupOriginalSrc) {
    Remove-Item -Recurse -Force $OriginalSrc -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 2c. Seed seedling's settings from seedling.conf (first install only --
#     an existing settings.json is never touched, so reinstalls don't
#     clobber choices made later with `seed config set`).
# ---------------------------------------------------------------------------
# Piped installs have no local conf, but the clone we just copied does.
if ($Conf.Count -eq 0) {
    $Conf = Read-SeedlingConf (Join-Path $SrcDir "seedling.conf")
}

# `seed update-commands` should keep pulling from wherever this install
# actually came from: a directory source, or any URL that isn't the public
# default (self-hosted git). Public-default installs leave this unset and
# update via the clone's own git remote, as always.
$UpdateSourceSeed = $null
if ($InstalledFromDir) {
    $UpdateSourceSeed = $InstalledFromDir
} elseif ($SeedlingRepo -ne $DefaultSeedlingRepo) {
    $UpdateSourceSeed = $SeedlingRepo
}

$SettingsFile = Join-Path $SeedlingHome "system\config\settings.json"
if (-not (Test-Path $SettingsFile)) {
    $seed = @{}
    if ($UpdateSourceSeed) { $seed["update_source"] = "$UpdateSourceSeed" }
    # Only seed the package list when it was actually changed -- the conf
    # ships with the built-in default written out for discoverability.
    if ($Conf["SEEDLING_VENV_DEFAULT_PACKAGES"]) {
        $pkgs = @($Conf["SEEDLING_VENV_DEFAULT_PACKAGES"].Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if ($pkgs.Count -gt 0 -and (($pkgs -join ",") -ne $DefaultVenvPackages)) {
            $seed["venv_default_packages"] = $pkgs
        }
    }
    if ($seed.Count -gt 0) {
        $seed | ConvertTo-Json | Set-Content -Path $SettingsFile -Encoding UTF8
        Info "Seeded seedling settings from seedling.conf"
    }
}


# ---------------------------------------------------------------------------
# 3. Install uv itself into seedling\bin
# ---------------------------------------------------------------------------
$UvExe = Join-Path $SeedlingHome "system\bin\uv.exe"
if (-not (Test-Path $UvExe)) {
    Info "Installing uv into $SeedlingHome\system\bin ..."
    $env:UV_INSTALL_DIR = "$SeedlingHome\system\bin"
    $env:UV_NO_MODIFY_PATH = "1"
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
} else {
    Info "uv already present, skipping."
}

if (-not (Test-Path $UvExe)) { Die "uv install appears to have failed (not found at $UvExe)." }

# ---------------------------------------------------------------------------
# 4. Install the seedling CLI itself as an isolated uv tool
# ---------------------------------------------------------------------------
Info "Installing the seedling CLI ..."
$env:UV_TOOL_DIR = "$SeedlingHome\system\tool"
$env:UV_TOOL_BIN_DIR = "$SeedlingHome\system\bin"
$env:UV_CACHE_DIR = "$SeedlingHome\system\cache\uv"
& $UvExe tool install --force --reinstall $SrcDir

$SeedCli = Join-Path $SeedlingHome "system\bin\seed-cli.exe"
if (-not (Test-Path $SeedCli)) { Die "seed-cli was not installed correctly." }

# ---------------------------------------------------------------------------
# 5. Write the `seed` PowerShell function and hook it into $PROFILE
# ---------------------------------------------------------------------------
Info "Writing shell integration ..."
$templatePath = Join-Path $SrcDir "src\seedling\shell\seed.ps1.template"
$content = Get-Content $templatePath -Raw
$content = $content -replace [regex]::Escape("__SEEDLING_HOME_PLACEHOLDER__"), $SeedlingHome
$seedPs1 = Join-Path $SeedlingHome "system\shell\seed.ps1"
Set-Content -Path $seedPs1 -Value $content -Encoding UTF8

$hookLine = ". `"$seedPs1`""
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Force -Path $PROFILE | Out-Null
}
# Drop hook lines left by older seedling layouts (e.g. ~\seedling\shell\
# before it moved under system\) before adding the current one, so a
# reinstall never leaves a stale line erroring in every new shell.
$lines = @(Get-Content $PROFILE -ErrorAction SilentlyContinue)
$cleaned = @($lines | Where-Object {
    -not ($_.Contains($SeedlingHome) -and ($_ -match "seed\.(ps1|sh)") -and $_ -ne $hookLine)
})
if ($cleaned.Count -ne $lines.Count) {
    Set-Content -Path $PROFILE -Value $cleaned
    Info "Removed stale seedling hook line(s) from $PROFILE"
}
if (-not ($cleaned -contains $hookLine)) {
    Add-Content -Path $PROFILE -Value "`n# seedling`n$hookLine"
    Info "Added seedling to $PROFILE"
}

Info "seedling is installed."
Write-Host ""
Write-Host "Open a new terminal (or run: . `"$seedPs1`") and try:"
Write-Host "  seed python 312"
Write-Host "  seed venv myproject"
Write-Host "  seed activate myproject"
Write-Host "  seed vscode"
Write-Host ""
Write-Host "Note: seed-cli was installed from a private copy at $SrcDir."
Write-Host "Nothing updates it automatically -- run 'seed update-commands' whenever"
Write-Host "you want to pull in changes."
