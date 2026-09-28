# Running Demand Scanner from Claude (Windows 10/11)

Connect the scanner to Claude once, then just ask Claude: *"Scan the niche meal prep for diabetics
and give me the top 5 opportunities."* Claude runs the scanner on your PC through its
**demand-scanner** tools, reads the evidence, and turns it into ranked product ideas. The scans
also appear in the dashboard at http://127.0.0.1:8765/.

This uses MCP (Model Context Protocol), which **Claude Desktop** and **Claude Code** support.
The claude.ai website in a browser can't start programs on your PC, so use the desktop app.

## 1. Install the scanner (skip if already done)

Double-click **`Install.bat`** in the project folder, or run:

```
powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\Demand\scripts\windows\install.ps1"
```

## 2. Connect it to Claude

1. Install **Claude Desktop** for Windows from https://claude.ai/download and sign in.
2. Double-click **`Connect-Claude.bat`** in the project folder, or run:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\Demand\scripts\windows\connect-claude.ps1"
   ```
   This adds `demand-scanner` to Claude Desktop's config file (backing up the old one as `.bak`)
   and, if the Claude Code CLI is installed, registers it there too.
3. **Fully quit Claude Desktop** (right-click the tray icon → Quit; closing the window is not
   enough) and open it again.
4. In a new chat, open the tools/connectors menu (the sliders icon under the message box).
   **demand-scanner** should be listed and switched on.

## 3. Use it

Ask in plain language:

- "Scan the niche *freelance invoicing* and give me the top 5 opportunities."
- "Do a deep scan of *dog training* and focus on ideas for an Android app."
- "Compare *pet grooming*, *dog training* and *cat litter*. Which has the most demand?"
- "Show my previous scans." / "Open the latest *meal prep* scan again."
- "Get the build brief for opportunity #2 from that scan."
- "Which data sources are switched off, and what do I need to turn them on?"

Or use the built-in prompt: in the **+** / attachments menu choose
**demand-scanner → find_opportunities**, type a niche, and send.

The first time Claude uses a tool it asks for permission. Choose **Allow always** for
demand-scanner so scans run without prompts.

A normal scan takes 15–60 seconds, a deep scan 1–3 minutes.

### Tools Claude gets

| Tool | What it does |
|---|---|
| `scan_niche` | Runs a scan (niche, optional deep / sources / country) and returns the demand score, top pain points with score breakdowns, evidence quotes with links, solution fits and source status |
| `compare_niches` | Scans several niches and returns a ranked leaderboard |
| `list_scans` | Lists saved scans (filter by niche) |
| `get_scan` | Reopens a saved scan |
| `get_build_brief` | Returns the ready-to-build spec for pain point #1–10 |
| `list_sources` | Shows which data sources are on and which need a key |

## 4. Build what you find

- **Claude Desktop:** "Write me a spec and landing page copy for opportunity #1."
- **Claude Code:** open a new empty folder in a terminal, run `claude`, then:
  *"Use demand-scanner get_build_brief for scan `<scan_id>` rank 1 and build the MVP here."*
  Inside the Demand project folder you can also use `/scan-niche <niche>` and
  `/build-solution <report-folder> <rank>`.

## Troubleshooting

| Problem | Fix |
|---|---|
| demand-scanner doesn't appear in Claude Desktop | Quit Claude fully from the tray and reopen it. Re-run `Connect-Claude.bat`. Check `%APPDATA%\Claude\claude_desktop_config.json` contains `"demand-scanner"` |
| "Server disconnected" / tool errors on start | Open Claude Desktop → Settings → Developer → demand-scanner → **Open logs**. Re-run `install.ps1` and then `connect-claude.ps1` |
| `Could not parse ... as JSON` when connecting | Your Claude config file has a typo. Fix it (or restore the `.bak`), then re-run |
| Scan takes long or times out | Try without deep, or limit sources: "scan X using only hackernews, google_suggest and youtube" |
| Reddit / TikTok missing | Add keys to the project's `.env` (see `.env.example`), then quit and reopen Claude Desktop |
| Moved the project folder | Re-run `connect-claude.ps1` so Claude gets the new path |
| Remove the connection | `connect-claude.ps1 -Disable`, then quit and reopen Claude Desktop |

## Other systems (macOS / Linux)

```bash
pip install -e ".[mcp]"
claude mcp add demand-scanner --scope user -- "$(pwd)/.venv/bin/python" -m demand_scanner mcp   # Claude Code
```
For Claude Desktop on macOS, add the same command to
`~/Library/Application Support/Claude/claude_desktop_config.json` under `mcpServers`.
