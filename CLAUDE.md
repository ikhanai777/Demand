# Demand Scanner

Python CLI (`python3 -m demand_scanner`) that finds and scores pain points in a niche.
Only runtime dependency: `requests`. `anthropic` and `google-play-scraper` are optional.

- Pipeline: `demand_scanner/scanner.py` (collect → filter → `pain.py` → `cluster.py` → `scoring.py` → `solutions.py` → optional `llm.py`) → `report.py`
- Sources live in `demand_scanner/sources/`, one class per platform, registered in `sources/__init__.py`. A source must never crash the scan; raise and `scanner.py` records the error.
- Tests: `pytest -q` (offline). Run them after changing scoring, clustering or pain patterns.
- Scan output goes to `reports/` (gitignored).
- Slash commands: `/scan-niche <niche>` and `/build-solution <report-folder> <rank>`. When building a solution, create it outside this repo.
