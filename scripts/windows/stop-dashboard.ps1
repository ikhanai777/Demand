<#
.SYNOPSIS
  Stop a dashboard started with start-dashboard.ps1 (by PID file, then by port).
#>
param([int]$Port = 0)
. "$PSScriptRoot\_common.ps1"
if ($Port -eq 0) { $Port = [int](Get-EnvValue "DEMAND_DASHBOARD_PORT" "8765") }

$stopped = $false
if (Test-Path $PidFile) {
    $procId = [int](Get-Content $PidFile -Raw)
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p) { Stop-Process -Id $procId -Force; $stopped = $true }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}
if (-not $stopped) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($p -and $p.ProcessName -like "python*") { Stop-Process -Id $p.Id -Force; $stopped = $true }
    }
}
if ($stopped) { Write-Ok "Dashboard stopped" } else { Write-Warn2 "No running dashboard found on port $Port" }
