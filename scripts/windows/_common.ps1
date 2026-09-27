# Shared helpers for the Windows scripts. Dot-source it: . "$PSScriptRoot\_common.ps1"
# Keep this file ASCII-only: Windows PowerShell 5.1 reads BOM-less scripts as ANSI.

$ErrorActionPreference = "Stop"
$Root    = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvPy  = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir  = Join-Path $Root "logs"
$PidFile = Join-Path $LogDir "dashboard.pid"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "[ok] $msg" -ForegroundColor Green }
function Write-Warn2([string]$msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }

function Assert-Venv {
    if (-not (Test-Path $VenvPy)) {
        throw "Virtual environment not found. Run scripts\windows\install.ps1 first."
    }
}

function Get-EnvValue([string]$name, [string]$default) {
    # Read a value from the process environment, then from .env, else the default.
    $v = [Environment]::GetEnvironmentVariable($name)
    if ($v) { return $v }
    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile -Encoding UTF8) {
            if ($line -match "^\s*$name\s*=\s*(.*)$") {
                $v = ($Matches[1] -replace "\s+#.*$", "").Trim().Trim('"').Trim("'")
                if ($v) { return $v }
            }
        }
    }
    return $default
}

function Test-Dashboard([int]$Port) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        return [bool]$r.ok
    } catch { return $false }
}
