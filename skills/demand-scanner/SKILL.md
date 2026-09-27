---
name: demand-scanner
description: Find and score real user pain points in any niche (Reddit, Hacker News, Google Trends, Google/YouTube autocomplete, YouTube, TikTok, Stack Exchange, Bluesky, App Store and Google Play reviews, GitHub issues), show them on a local demand dashboard, and turn the best ones into build briefs. Use when asked to research demand, validate an idea, find app/SaaS/content opportunities, compare niches, or discover what people in a niche complain about.
version: 1.1.0
platforms: [windows, linux, macos]
metadata:
  hermes:
    category: research
    tags: [market-research, demand, pain-points, product-ideas, dashboard]
---

# Demand Scanner

Project folder: `{{DEMAND_SCANNER_HOME}}`
(The Windows installer replaces this placeholder with the real path. If you still see the
placeholder, the project is wherever this repository was cloned, e.g. `%USERPROFILE%\Demand`.)

All commands below are for Windows and work from PowerShell, cmd or Git Bash because they
call `powershell -File`. Always quote the path. On Linux/macOS use
`.venv/bin/python -m demand_scanner ...` from the project folder instead.

Shorthand used below: `PS = powershell -NoProfile -ExecutionPolicy Bypass -File`
and `DS = {{DEMAND_SCANNER_HOME}}`.

## 1. Make sure it is installed and the dashboard is up

```
PS "DS\scripts\windows\status.ps1"
```
- exit code 1 / "Not installed" -> run `PS "DS\scripts\windows\install.ps1"`
- "Dashboard not running" -> run `PS "DS\scripts\windows\start-dashboard.ps1" -Background`
  (returns immediately; never start the dashboard without `-Background`, it would block your terminal)

Dashboard: http://127.0.0.1:8765/ (tell the user this URL after starting it).

## 2. Scan a niche

Preferred: the CLI (blocks until done, typically 15-60 s, `-Deep` 1-3 min):
```
PS "DS\scripts\windows\scan.ps1" -Niche "meal prep for diabetics"
PS "DS\scripts\windows\scan.ps1" -Niche "pet grooming" -Deep
```
It prints the demand score, the top 10 pain points and the report folder
(`DS\reports\<niche>-<timestamp>\`). The scan appears in the dashboard automatically.

Alternative when the dashboard is running (non-blocking, good for chat gateways):
```
curl -s -X POST http://127.0.0.1:8765/api/scans -H "Content-Type: application/json" -d "{\"niche\": \"pet grooming\", \"deep\": false}"
curl -s http://127.0.0.1:8765/api/jobs            # poll until status is "done"; scan_id = report folder
```

Compare several niches (writes `DS\reports\leaderboard.md`):
```
PS "DS\scripts\windows\scheduled-scan.ps1" -File "DS\niches.txt"
```

## 3. Read the results

Open `DS\reports\<scan>\report.json` (or `GET http://127.0.0.1:8765/api/scans/<scan>`):
- `summary.score` / `summary.grade`: niche demand 0-100 (HOT >= 75, STRONG >= 60, PROMISING >= 45, WEAK >= 30)
- `pain_points[]`: `label`, `score`, `components` (volume, engagement, intensity, wtp, breadth,
  recency, gap, momentum - each 0..1), `tags` (pain types), `sources`, `evidence[]` (real quotes
  with URLs), `solutions[]` (heuristic best-fit solution types)
- `search_demand[]`: real Google/YouTube autocomplete and Google Trends queries
- `sources[]`: which sources worked; mention failed/skipped ones, they lower confidence

Scores are heuristic. Before recommending anything:
1. Read the evidence quotes. Drop clusters that are noise or off-topic; merge duplicates.
2. Name each pain from the user's point of view ("Freelancers waste hours chasing late payments").
3. Prefer pain points with willingness to pay (`components.wtp`), explicit tool-seeking
   (`components.gap`), several sources (`components.breadth`) and recent activity (`components.recency`).
4. Give the user the top 3-5 opportunities: pain, who has it, evidence links, solution type,
   product idea, MVP features, monetization, build effort.

## 4. Build a solution

Each scan writes `briefs\01-*.md` ... `briefs\10-*.md`: self-contained prompts with the pain,
score breakdown, quotes and build instructions. Read one and build the MVP in a NEW folder
outside the project (e.g. `%USERPROFILE%\projects\<product>`), or hand it to Claude Code:
`claude "<contents of the brief>"`. The dashboard's "Copy build brief" button copies the same text.

## 5. Recurring scans (Hermes cron)

Put the user's niches in `DS\niches.txt` (one per line), then schedule, e.g.
"Every Monday at 08:00 run `PS "DS\scripts\windows\scheduled-scan.ps1"` and send me the
leaderboard table it prints plus the top pain point of the #1 niche."
Re-scans of the same niche build a score history in the dashboard.

## Troubleshooting
- Reddit/App Store "403/429": blocked or rate-limited; the scan continues without them. A free
  Reddit API key in `DS\.env` (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET) fixes Reddit.
- TikTok skipped: needs APIFY_TOKEN in `DS\.env`.
- After editing `.env`, restart the dashboard: `stop-dashboard.ps1` then `start-dashboard.ps1 -Background`.
- Port busy: add `DEMAND_DASHBOARD_PORT=8766` to `.env`.
- Logs: `DS\logs\dashboard.log`, `DS\logs\dashboard.err.log`.
