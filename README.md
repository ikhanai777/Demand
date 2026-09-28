# Demand Scanner

Find real pain points in any niche, score the demand, and turn the best ones into build briefs
for Claude Code (or a Hermes agent).

```bash
pip install -r requirements.txt
python3 -m demand_scanner scan "meal prep" --deep
```

```
meal prep: demand 68.5/100 (STRONG) - 115 pain points from 1546 signals

   1. [ 53.1] plan zepbound / sugar                     20 sig  -> marketplace_directory
   2. [ 49.3] ingredient                                 3 sig  -> web_saas
   3. [ 47.4] chicken breast / chicken recipes / ideas  14 sig  -> content
   ...
Report: reports/meal-prep-20260927-2010/report.html
```

## Run it from Claude (Claude Desktop / Claude Code)

The scanner ships an MCP server, so Claude can run scans for you: *"Scan the niche meal prep for
diabetics and give me the top 5 opportunities."* On Windows, double-click **`Install.bat`**, then
**`Connect-Claude.bat`**, and restart Claude Desktop. Full steps: **[CLAUDE_SETUP.md](CLAUDE_SETUP.md)**.

Tools: `scan_niche`, `compare_niches`, `list_scans`, `get_scan`, `get_build_brief`, `list_sources`,
plus a `find_opportunities` prompt. Elsewhere: `pip install -e ".[mcp]"` and
`claude mcp add demand-scanner -- <path-to-python> -m demand_scanner mcp`.

## Windows 10 + Hermes Agent

Double-click **`Install.bat`**, then **`Start-Dashboard.bat`**, or have Nous Hermes Agent do the whole
deployment for you by following **[HERMES_DEPLOY.md](HERMES_DEPLOY.md)** (install, keys, dashboard,
autostart, Hermes skill, weekly re-scans). The Windows scripts live in `scripts/windows/`.

## Demand dashboard

```bash
python3 -m demand_scanner dashboard --open      # http://127.0.0.1:8765/
```

A local web app (Python standard library only, no extra installs): start scans and watch their live
log, compare niches on a leaderboard, open any scan to see demand KPIs, the 5-year Google Trends
curve, score history across re-scans, a filterable pain-point table with score breakdowns, real
quotes and solution ideas, and copy build briefs with one click. It also has a JSON API
(`/api/scans`, `/api/jobs`, ...) so agents can drive it; see [HERMES_DEPLOY.md](HERMES_DEPLOY.md#4-dashboard-http-api-for-hermes-and-scripts).

## How it works

```
collect ──► filter ──► detect pain ──► cluster ──► score ──► recommend ──► (LLM) ──► report + briefs
 11 sources  relevance   9 pain types    TF-IDF +    8 signals   solution     Claude /    HTML, MD, JSON,
 in parallel + dedupe    13 aspects      aspects     → 0-100     types        Hermes      build prompts
```

### Sources

| Source | What it gives you | Key needed? |
|---|---|---|
| **Reddit** | Posts + top comments, niche subreddits mined for pain phrases | Optional (`REDDIT_CLIENT_ID/SECRET`); public JSON and PullPush fallback otherwise |
| **Hacker News** | Stories, Ask HN, comments (Algolia API) | No |
| **Google Trends** | 5-year interest → momentum; rising & top related queries | No |
| **Google + YouTube autocomplete** | "Alphabet soup" of real searches: *X alternative*, *X not working*, *how to X without…* | No |
| **YouTube** | Videos people watch to solve the problem (views = content demand); comments with a key | Optional (`YOUTUBE_API_KEY`) |
| **TikTok** | Videos, plays, likes, comments via Apify | `APIFY_TOKEN` |
| **Stack Exchange** | Software Recs, Web Apps, Super User, Android, Money… (unanswered + high views = gap) | Optional |
| **Bluesky** | Public social posts | No |
| **Apple App Store** | 1–3★ reviews of competing apps (competitor weaknesses) | No |
| **Google Play** | 1–2★ reviews of competing Android apps | `pip install google-play-scraper` |
| **GitHub** | Feature-request issues ranked by 👍 reactions | Optional (`GITHUB_TOKEN`) |

Run `python3 -m demand_scanner sources` to see what's configured. Any source that fails
(blocked, rate-limited, not configured) is reported and skipped — the scan never dies because of one source.
Copy `.env.example` to `.env` to add keys. Responses are cached for 6 hours (`--no-cache` to bypass).

> Reddit and some app store endpoints block many cloud/datacenter IPs. From a home connection
> they usually work; anywhere else, create a free Reddit "script" app and set the two env vars.
> X/Twitter and Instagram have no free search APIs and aren't included.

### Pain detection

Every signal is checked for 9 pain types: `willingness_to_pay`, `tool_seeking`
("is there an app…"), `alternative` ("switching from…"), `feature_gap` ("I wish…", "doesn't support"),
`frustration`, `workaround` (spreadsheets, "manually"), `time_waste`, `price`, `how_to`.
Low-star reviews and unanswered, highly-viewed questions count as pain even without the phrasing.
It also tags 13 product aspects (pricing, reliability, usability, integrations, mobile, automation,
payments, support, learning, privacy, compliance, collaboration, discovery) so complaints that share
no words ("loading forever", "crashes on save") still group together.

### Demand score (0–100)

Each pain point is scored from interpretable components, all shown in the report:

| Component | Weight | Meaning |
|---|---|---|
| volume | 18% | independent mentions (unique authors, log-scaled) |
| wtp | 16% | willingness-to-pay and price complaints (search queries excluded) |
| engagement | 14% | upvotes, comments, views behind the mentions |
| intensity | 14% | how strong the pain language is |
| gap | 12% | explicit tool-seeking / alternative-seeking / missing features |
| breadth | 10% | number of different platforms |
| recency | 10% | share of mentions in the last 180 days |
| momentum | 6% | Google Trends direction for the niche |

Grades: **HOT** ≥75 · **STRONG** ≥60 · **PROMISING** ≥45 · **WEAK** ≥30 · **NOISE**.
The niche score blends the top pain points with overall pain volume, WTP and momentum.

### Solutions

Each pain point is matched to solution types — `android_app`, `web_saas`, `ai_tool`, `automation`,
`browser_extension`, `content`, `marketplace_directory`, `marketing_service` — from its language and
pain types. A build brief (`briefs/NN-*.md`) is written for each of the top pain points, with the
score breakdown, real quotes with links, and instructions for a coding agent.

## Using it with Claude Code

This repo ships two slash commands (in `.claude/commands/`):

```
/scan-niche meal prep for diabetics --deep
```
Runs the scan, then Claude Code itself acts as the analyst: drops noise, merges duplicates, names
each pain, re-ranks, proposes products and writes `OPPORTUNITIES.md`. No API key needed.

```
/build-solution reports/meal-prep-for-diabetics-20260927-2010 1
```
Builds the MVP for opportunity #1 in a new directory: spec, stack choice by solution type,
implementation, tests, landing copy.

Or pipe a brief directly:

```bash
claude "$(python3 -m demand_scanner brief reports/<scan-folder> 1)"
```

## Using it with Nous Hermes (or any LLM) inside the scanner

```bash
# Claude via the official SDK
pip install anthropic
export ANTHROPIC_API_KEY=...
python3 -m demand_scanner scan "pet grooming" --llm anthropic

# Hermes (or any OpenAI-compatible endpoint: OpenRouter, Nous Portal, Ollama, LM Studio)
export LLM_BASE_URL=https://openrouter.ai/api/v1 LLM_API_KEY=... LLM_MODEL=nousresearch/hermes-4-405b
python3 -m demand_scanner scan "pet grooming" --llm hermes
```

The LLM names each pain point, writes a problem statement and persona, rates severity (blended into
the score), flags noise, and proposes named products with MVP features and monetization.
Those go straight into the report and the build briefs.

For Hermes Agent (or any agent that reads `SKILL.md` skills), use `skills/demand-scanner/SKILL.md`.
On Windows, `scripts/windows/install.ps1` installs it into Hermes for you (`/demand-scanner`).

## Other commands

```bash
# Rank several niches against each other → reports/leaderboard.md
python3 -m demand_scanner compare "meal prep" "pet grooming" "freelance invoicing"
python3 -m demand_scanner compare --file niches.txt

# Local dashboard
python3 -m demand_scanner dashboard [--port 8765] [--open]

# MCP server for Claude (needs: pip install -e ".[mcp]")
python3 -m demand_scanner mcp

# Options
--deep            more queries, more comments/reviews, full autocomplete alphabet (slower)
--sources a,b     only these sources (e.g. reddit,hackernews,google_suggest)
--keywords a,b    words that make a post relevant (default: words in the niche)
--days 365        look-back window
--geo GB          country for Trends / app stores
--llm anthropic|hermes   LLM synthesis
--json            also print the report JSON
```

## Development

```bash
pip install -e ".[dev]"
pytest -q          # offline tests, no network
```

Adding a source: subclass `demand_scanner.sources.base.Source`, implement `collect(ctx) -> list[Signal]`,
and register it in `demand_scanner/sources/__init__.py`.
