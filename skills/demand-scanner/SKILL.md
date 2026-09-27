---
name: demand-scanner
description: Find and score real user pain points in any niche (Reddit, Hacker News, Google Trends, Google/YouTube autocomplete, YouTube, TikTok, Stack Exchange, Bluesky, app store reviews, GitHub issues) and turn the best ones into build briefs. Use when asked to research demand, validate an idea, find app/SaaS/content opportunities, or discover what people in a niche complain about.
---

# Demand scanner

A CLI in this repository that collects public complaints, questions and search queries about a
niche, detects pain language, clusters it into pain points, and scores each 0–100 for demand.

## Run it

```bash
pip install -r requirements.txt           # once
python3 -m demand_scanner scan "<niche>"  # add --deep for more coverage (slower)
python3 -m demand_scanner compare "niche a" "niche b" "niche c"   # rank niches
python3 -m demand_scanner sources          # show which sources are configured
```

Each scan writes `reports/<niche>-<timestamp>/` containing:

- `report.json` — machine-readable: `summary`, `pain_points[]` (score, components, tags, sources,
  evidence quotes with URLs, heuristic `solutions`), `search_demand[]`, source status
- `report.md` / `report.html` — human-readable report and dashboard
- `briefs/NN-*.md` — self-contained build prompts for a coding agent

## How to use the output

1. Read `report.json`. Treat `score` as a heuristic ranking, not truth; check the evidence quotes.
2. Drop noise clusters, merge duplicates, and name each pain from the user's point of view.
3. Prefer pain points with willingness-to-pay (`components.wtp`), explicit tool-seeking
   (`components.gap`), several sources (`components.breadth`) and recent activity.
4. Hand the chosen `briefs/NN-*.md` to a coding agent to build the MVP.

Optional LLM synthesis inside the scanner: `--llm anthropic` (Claude, needs ANTHROPIC_API_KEY) or
`--llm hermes` (any OpenAI-compatible endpoint: set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL — e.g.
Nous Hermes via OpenRouter, Nous Portal, or a local Ollama server).
