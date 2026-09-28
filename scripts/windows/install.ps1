<#
.SYNOPSIS
  One-shot installer for Demand Scanner on Windows 10/11 (safe to re-run).

.DESCRIPTION
  1. Finds Python 3.10+ (installs Python 3.12 with winget if missing)
  2. Creates .venv and installs the scanner (+ Google Play and Claude extras)
  3. Creates .env from .env.example
  4. Runs the offline tests and lists data sources
  5. Installs the Hermes Agent skill into %LOCALAPPDATA%\hermes\skills\research\demand-scanner
  6. Optionally registers the dashboard to start at logon (-Autostart)

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\install.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\install.ps1 -Autostart
#>
param(
    [string]$HermesHome = $(if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA "hermes" }),
    [switch]$SkipSkill,
    [switch]$SkipTests,
    [switch]$Autostart,
    [switch]$Minimal   # core only: skip google-play-scraper and anthropic extras
)
. "$PSScriptRoot\_common.ps1"
Set-Location $Root

function Find-Python {
    $candidates = @(@("py", "-3.12"), @("py", "-3.11"), @("py", "-3.10"), @("py", "-3"), @("python"), @("python3"))
    foreach ($c in $candidates) {
        $exe = $c[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $args2 = @($c | Select-Object -Skip 1) + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        try { $ver = (& $exe @args2 2>$null | Select-Object -Last 1) } catch { continue }
        if ($ver -match "^3\.(\d+)$" -and [int]$Matches[1] -ge 10) {
            return ,@($c)
        }
    }
    return $null
}

Write-Step "Demand Scanner install in $Root"

# 1. Python ------------------------------------------------------------------------
$py = Find-Python
if (-not $py) {
    Write-Warn2 "Python 3.10+ not found."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Installing Python 3.12 with winget (user scope)"
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements --silent
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
        $py = Find-Python
    }
    if (-not $py) {
        throw "Install Python 3.10+ from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), open a new terminal, and re-run this script."
    }
}
$pyExe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)
Write-Ok ("Python: " + (& $pyExe @pyArgs --version))

# 2. Virtual environment + package ---------------------------------------------------
if (-not (Test-Path $VenvPy)) {
    Write-Step "Creating virtual environment (.venv)"
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
}
Write-Step "Installing Python packages"
& $VenvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
$extras = if ($Minimal) { "dev" } else { "dev,play,llm,mcp" }
& $VenvPy -m pip install -e ".[$extras]" --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Ok "Packages installed ($extras)"

# 3. .env ------------------------------------------------------------------------------
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Root ".env.example") $envFile
    Write-Ok "Created .env from .env.example (add API keys there; all optional)"
} else {
    Write-Ok ".env already exists (left unchanged)"
}
New-Item -ItemType Directory -Force -Path $LogDir, (Join-Path $Root "reports") | Out-Null

# 4. Verify ------------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Step "Running offline tests"
    & $VenvPy -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed - see output above" }
    Write-Ok "Tests passed"
}
Write-Step "Data sources"
& $VenvPy -m demand_scanner sources

# 5. Hermes skill --------------------------------------------------------------------------
if (-not $SkipSkill) {
    $skillDir = Join-Path $HermesHome "skills\research\demand-scanner"
    New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
    $template = Get-Content (Join-Path $Root "skills\demand-scanner\SKILL.md") -Raw -Encoding UTF8
    $skill = $template.Replace("{{DEMAND_SCANNER_HOME}}", $Root)
    [IO.File]::WriteAllText((Join-Path $skillDir "SKILL.md"), $skill, (New-Object Text.UTF8Encoding($false)))
    Write-Ok "Hermes skill installed: $skillDir\SKILL.md  (use /demand-scanner in Hermes)"
}

# 6. Autostart -------------------------------------------------------------------------------
if ($Autostart) {
    & "$PSScriptRoot\autostart.ps1"
}

Write-Host ""
Write-Ok "Install complete."
Write-Host "  Start dashboard : powershell -NoProfile -ExecutionPolicy Bypass -File `"$Root\scripts\windows\start-dashboard.ps1`" -Background"
Write-Host "  Run a scan      : powershell -NoProfile -ExecutionPolicy Bypass -File `"$Root\scripts\windows\scan.ps1`" -Niche `"meal prep`""
Write-Host "  Dashboard URL   : http://127.0.0.1:$(Get-EnvValue 'DEMAND_DASHBOARD_PORT' '8765')/"
