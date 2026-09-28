<#
.SYNOPSIS
  Connect Demand Scanner to Claude: registers its MCP server with Claude Desktop and Claude Code.

.DESCRIPTION
  After this, ask Claude things like "scan the niche meal prep for diabetics" and it runs the
  scanner on this PC through the demand-scanner tools. Safe to re-run.
  - Installs the MCP extra into .venv
  - Adds "demand-scanner" to claude_desktop_config.json (backs up the old file first)
  - Registers it with Claude Code (user scope) if the `claude` CLI is installed

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\connect-claude.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\connect-claude.ps1 -Disable
#>
param([switch]$Disable, [string]$Name = "demand-scanner")
. "$PSScriptRoot\_common.ps1"
Assert-Venv
Set-Location $Root

function Get-DesktopConfigPaths {
    $paths = @()
    $std = Join-Path $env:APPDATA "Claude"
    if (Test-Path $std) { $paths += (Join-Path $std "claude_desktop_config.json") }
    # Microsoft Store (MSIX) installs keep their config in a virtualized folder.
    $pkgRoot = Join-Path $env:LOCALAPPDATA "Packages"
    if (Test-Path $pkgRoot) {
        Get-ChildItem $pkgRoot -Directory -Filter "Claude_*" -ErrorAction SilentlyContinue | ForEach-Object {
            $d = Join-Path $_.FullName "LocalCache\Roaming\Claude"
            if (Test-Path $d) { $paths += (Join-Path $d "claude_desktop_config.json") }
        }
    }
    if ($paths.Count -eq 0) { $paths += (Join-Path $std "claude_desktop_config.json") }
    return $paths
}

function Read-Config([string]$path) {
    if (-not (Test-Path $path)) { return [pscustomobject]@{} }
    $raw = [IO.File]::ReadAllText($path)
    if (-not $raw.Trim()) { return [pscustomobject]@{} }
    try { return $raw | ConvertFrom-Json }
    catch { throw "Could not parse $path as JSON. Fix or delete it, then re-run. ($_)" }
}

function Write-Config([string]$path, $cfg) {
    New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
    if (Test-Path $path) { Copy-Item $path "$path.bak" -Force }
    $json = $cfg | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($path, $json, (New-Object Text.UTF8Encoding($false)))
}

$reports = Join-Path $Root "reports"

if (-not $Disable) {
    Write-Step "Installing MCP support into .venv"
    & $VenvPy -m pip install -e ".[mcp]" --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    & $VenvPy -c "import demand_scanner.mcp_server"
    if ($LASTEXITCODE -ne 0) { throw "MCP server failed to import - see the error above" }
    Write-Ok "MCP server ready"
}

# Claude Desktop ---------------------------------------------------------------------------
foreach ($path in Get-DesktopConfigPaths) {
    $cfg = Read-Config $path
    if (-not ($cfg.PSObject.Properties.Name -contains "mcpServers")) {
        $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
    }
    if ($cfg.mcpServers.PSObject.Properties.Name -contains $Name) {
        $cfg.mcpServers.PSObject.Properties.Remove($Name)
    }
    if (-not $Disable) {
        $entry = [pscustomobject]@{
            command = $VenvPy
            args    = @("-m", "demand_scanner", "mcp")
            env     = [pscustomobject]@{ DEMAND_SCANNER_REPORTS = $reports; PYTHONUTF8 = "1" }
        }
        $cfg.mcpServers | Add-Member -NotePropertyName $Name -NotePropertyValue $entry
    }
    Write-Config $path $cfg
    if ($Disable) { Write-Ok "Removed from Claude Desktop: $path" } else { Write-Ok "Added to Claude Desktop: $path" }
}

# Claude Code --------------------------------------------------------------------------------
if (Get-Command claude -ErrorAction SilentlyContinue) {
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & claude mcp remove $Name --scope user 2>$null | Out-Null
    if (-not $Disable) {
        & claude mcp add $Name --scope user -e "DEMAND_SCANNER_REPORTS=$reports" -e "PYTHONUTF8=1" -- $VenvPy -m demand_scanner mcp
        if ($LASTEXITCODE -eq 0) { Write-Ok "Registered with Claude Code (user scope). Check with: claude mcp list" }
        else { Write-Warn2 "Claude Code registration failed; run manually: claude mcp add $Name --scope user -- `"$VenvPy`" -m demand_scanner mcp" }
    } else {
        Write-Ok "Removed from Claude Code"
    }
    $ErrorActionPreference = $prev
} else {
    Write-Host "    Claude Code CLI not found - skipped (Claude Desktop is enough)."
}

Write-Host ""
if ($Disable) {
    Write-Ok "Disconnected. Fully quit Claude Desktop (tray icon > Quit) and reopen it."
} else {
    Write-Ok "Connected."
    Write-Host "  1. Fully quit Claude Desktop (system tray icon > Quit) and open it again."
    Write-Host "  2. In a new chat, check the tools/connectors menu lists 'demand-scanner'."
    Write-Host "  3. Ask: Scan the niche `"meal prep for diabetics`" and give me the top 5 opportunities."
}
