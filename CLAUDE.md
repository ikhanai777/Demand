# Demand Scanner

Python CLI (`python3 -m demand_scanner`) that finds and scores pain points in a niche.
Only runtime dependency: `requests`. `anthropic` and `google-play-scraper` are optional.

- Pipeline: `demand_scanner/scanner.py` (collect → filter → `pain.py` → `cluster.py` → `scoring.py` → `solutions.py` → optional `llm.py`) → `report.py`
- Sources live in `demand_scanner/sources/`, one class per platform, registered in `sources/__init__.py`. A source must never crash the scan; raise and `scanner.py` records the error.
- Dashboard: `demand_scanner/dashboard/` (stdlib `http.server` + one static `index.html`, no build step). Keep it dependency-free; escape all evidence text in the UI (it is untrusted public content).
- Windows deployment: `scripts/windows/*.ps1` must stay ASCII-only (PowerShell 5.1 reads BOM-less files as ANSI) and CRLF (see `.gitattributes`). `HERMES_DEPLOY.md` documents them; keep both in sync.
- Tests: `pytest -q` (offline). Run them after changing scoring, clustering or pain patterns.
- Scan output goes to `reports/` (gitignored).
- Slash commands: `/scan-niche <niche>` and `/build-solution <report-folder> <rank>`. When building a solution, create it outside this repo.
