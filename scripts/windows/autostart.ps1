<#
.SYNOPSIS
  Start the dashboard automatically when you log on to Windows (Task Scheduler, no admin needed).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\autostart.ps1            # enable
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\autostart.ps1 -Disable   # disable
#>
param([switch]$Disable, [string]$TaskName = "DemandDashboard")
. "$PSScriptRoot\_common.ps1"

if ($Disable) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Ok "Autostart disabled ($TaskName)"
    exit 0
}
Assert-Venv
$script = Join-Path $PSScriptRoot "start-dashboard.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Background" `
    -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Starts the Demand Scanner dashboard at logon" -Force | Out-Null
Write-Ok "Autostart enabled: task '$TaskName' starts the dashboard at logon"
