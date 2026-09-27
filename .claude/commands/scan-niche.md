---
description: Scan a niche for pain points, score demand, and pick the best opportunities to build
argument-hint: <niche> [--deep]
allowed-tools: Bash(python3 -m demand_scanner:*), Bash(pip install:*), Read, Write, Glob
---

You are running the demand scanner for the niche: **$ARGUMENTS**

1. Run the scan (install deps first if `requests` is missing: `pip install -r requirements.txt`):

   ```bash
   python3 -m demand_scanner scan $ARGUMENTS
   ```

   It prints the report folder. Read `report.json` from that folder. Note which sources failed
   or were skipped (e.g. Reddit blocked, TikTok not configured) — mention them, since missing
   sources lower confidence.

2. Act as the synthesis layer (no API key needed — you are the LLM). For the top ~12 pain points in
   `report.json`, using ONLY the evidence quotes provided:
   - Give each a clear name stated as the user's pain (e.g. "Freelancers waste hours chasing late payments").
   - Flag clusters that are noise / off-topic / not a real pain and drop them.
   - Merge clusters that describe the same underlying pain.
   - Write a 1–2 sentence problem statement and who has it.
   - Re-rank by your judgement of demand: the heuristic `score`, plus willingness-to-pay quotes,
     explicit "is there a tool" requests, and cross-platform breadth.

3. For the top 5 pain points, propose concrete solutions. For each: solution type (android_app, web_saas,
   ai_tool, automation, browser_extension, content, marketplace_directory, marketing_service), product
   name, one-liner, 3–6 MVP features, monetization, build effort (weekend / 1–2 weeks / 1 month+), and
   existing competitors mentioned in the evidence.

4. Write `OPPORTUNITIES.md` into the same report folder with:
   - Niche demand score and grade, trend momentum, source coverage
   - A ranked table of the validated pain points
   - The top 5 opportunities with the details above and 2–3 verbatim evidence quotes with links each
   - A "Build next" recommendation: the single best opportunity and why

5. Finish by telling the user the top 3 opportunities in a few lines and how to build one:
   `/build-solution <path-to-report-folder> <rank>`
