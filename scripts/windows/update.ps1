<#
.SYNOPSIS
  Pull the latest code, reinstall packages and the Hermes skill, restart the dashboard if it was running.
#>
param([string]$Branch = "")
. "$PSScriptRoot\_common.ps1"
Set-Location $Root
$port = [int](Get-EnvValue "DEMAND_DASHBOARD_PORT" "8765")
$wasRunning = Test-Dashboard $port

if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Step "Pulling latest code"
    if ($Branch) { git pull origin $Branch } else { git pull }
    if ($LASTEXITCODE -ne 0) { throw "git pull failed (local changes?)" }
} else {
    Write-Warn2 "git not found - skipping pull"
}
if ($wasRunning) { & "$PSScriptRoot\stop-dashboard.ps1" }
& "$PSScriptRoot\install.ps1" -SkipTests
if ($wasRunning) { & "$PSScriptRoot\start-dashboard.ps1" -Background }
