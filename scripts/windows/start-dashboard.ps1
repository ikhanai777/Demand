<#
.SYNOPSIS
  Start the Demand Dashboard (http://127.0.0.1:8765 by default).

.PARAMETER Background
  Start detached (hidden window), wait until it is healthy, then return.
  Use this from agents such as Hermes so the terminal call does not block.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\start-dashboard.ps1 -Background
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\start-dashboard.ps1 -Open
#>
param(
    [int]$Port = 0,
    [string]$BindHost = "",
    [switch]$Background,
    [switch]$Open
)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
Set-Location $Root
if ($Port -eq 0) { $Port = [int](Get-EnvValue "DEMAND_DASHBOARD_PORT" "8765") }
if (-not $BindHost) { $BindHost = Get-EnvValue "DEMAND_DASHBOARD_HOST" "127.0.0.1" }
$url = "http://127.0.0.1:$Port/"

if (Test-Dashboard $Port) {
    Write-Ok "Dashboard already running at $url"
    if ($Open) { Start-Process $url }
    exit 0
}

$dashArgs = @("-m", "demand_scanner", "dashboard", "--port", "$Port", "--host", $BindHost)

if ($Background) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $proc = Start-Process -FilePath $VenvPy -ArgumentList $dashArgs -WorkingDirectory $Root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "dashboard.log") `
        -RedirectStandardError (Join-Path $LogDir "dashboard.err.log") -PassThru
    Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Dashboard $Port) {
            Write-Ok "Dashboard running at $url (PID $($proc.Id)). Logs: $LogDir"
            if ($Open) { Start-Process $url }
            exit 0
        }
        if ($proc.HasExited) { break }
    }
    Write-Warn2 "Dashboard did not become healthy. Last errors:"
    Get-Content (Join-Path $LogDir "dashboard.err.log") -Tail 20 -ErrorAction SilentlyContinue
    exit 1
}

if ($Open) { $dashArgs += "--open" }
Write-Step "Starting dashboard at $url (Ctrl+C to stop)"
& $VenvPy @dashArgs
