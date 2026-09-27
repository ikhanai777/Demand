<#
.SYNOPSIS
  Re-scan a watchlist of niches and rebuild reports\leaderboard.md.
  Meant for Hermes cron jobs or Windows Task Scheduler. Prints the leaderboard (markdown) at the end.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\scheduled-scan.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\scheduled-scan.ps1 -File my-niches.txt -Deep
#>
param(
    [string]$File = "niches.txt",
    [switch]$Deep,
    [ValidateSet("none", "anthropic", "hermes", "openai")][string]$Llm = "none"
)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
Set-Location $Root

if (-not (Test-Path $File)) {
    if (Test-Path "niches.example.txt") { Copy-Item "niches.example.txt" $File; Write-Warn2 "Created $File from niches.example.txt - edit it with your niches." }
    else { throw "Watchlist $File not found (one niche per line)." }
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$cmpArgs = @("-m", "demand_scanner", "compare", "--file", $File, "--llm", $Llm)
if ($Deep) { $cmpArgs += "--deep" }
# Progress goes to stderr; with "Stop", Windows PowerShell 5.1 would treat that as an error.
$ErrorActionPreference = "Continue"
& $VenvPy @cmpArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath (Join-Path $LogDir "scheduled-$stamp.log")
exit $LASTEXITCODE
