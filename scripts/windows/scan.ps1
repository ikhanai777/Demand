<#
.SYNOPSIS
  Scan one niche from the command line. Results appear in the dashboard automatically.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\scan.ps1 -Niche "meal prep for diabetics" -Deep
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\scan.ps1 -Niche "pet grooming" -Llm hermes -Json
#>
param(
    [Parameter(Mandatory = $true)][string]$Niche,
    [switch]$Deep,
    [ValidateSet("none", "anthropic", "hermes", "openai")][string]$Llm = "none",
    [string]$Sources = "",
    [string]$Geo = "US",
    [switch]$Json
)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
Set-Location $Root

$scanArgs = @("-m", "demand_scanner", "scan", $Niche, "--llm", $Llm, "--geo", $Geo)
if ($Deep) { $scanArgs += "--deep" }
if ($Sources) { $scanArgs += @("--sources", $Sources) }
if ($Json) { $scanArgs += "--json" }
& $VenvPy @scanArgs
exit $LASTEXITCODE
