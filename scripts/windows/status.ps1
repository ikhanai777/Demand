<#
.SYNOPSIS
  Health check: install state, dashboard state, data sources, latest scans. Exit code 0 = healthy.
#>
param([int]$Port = 0)
. "$PSScriptRoot\_common.ps1"
if ($Port -eq 0) { $Port = [int](Get-EnvValue "DEMAND_DASHBOARD_PORT" "8765") }
$healthy = $true

if (Test-Path $VenvPy) { Write-Ok ("Installed: " + (& $VenvPy --version)) } else { Write-Warn2 "Not installed (run install.ps1)"; exit 1 }

$skill = Join-Path $(if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA "hermes" }) "skills\research\demand-scanner\SKILL.md"
if (Test-Path $skill) { Write-Ok "Hermes skill: $skill" } else { Write-Warn2 "Hermes skill not installed (install.ps1 installs it)" }

if (Test-Dashboard $Port) {
    Write-Ok "Dashboard: http://127.0.0.1:$Port/"
    try {
        $scans = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/scans" -TimeoutSec 5
        Write-Host ("    scans: {0}" -f @($scans).Count)
        @($scans) | Select-Object -First 5 | ForEach-Object {
            Write-Host ("    {0,5}  {1,-10} {2}  ({3})" -f $_.score, $_.grade, $_.niche, $_.generated_at)
        }
    } catch { Write-Warn2 "Could not list scans: $_" }
} else {
    Write-Warn2 "Dashboard not running (start-dashboard.ps1 -Background)"
    $healthy = $false
}

Set-Location $Root
& $VenvPy -m demand_scanner sources
if ($healthy) { exit 0 } else { exit 2 }
