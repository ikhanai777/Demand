---
description: Turn a demand-scanner opportunity into a working MVP
argument-hint: <report-folder> [rank=1] [target-dir]
---

Arguments: $ARGUMENTS  (report folder, optional opportunity rank — default 1, optional target directory)

1. Read the matching build brief `briefs/<NN>-*.md` in the report folder. If `OPPORTUNITIES.md`
   exists there, read it too — its product definition takes precedence over the heuristic brief.
2. Restate the pain, the user, and the MVP scope in 5 lines, then create the project in the target
   directory (default: `../<product-slug>`), NOT inside the demand-scanner repo.
3. Write `SPEC.md` first (user, job-to-be-done, MVP features, non-goals, success metric).
4. Choose the stack by solution type:
   - android_app → Kotlin + Jetpack Compose (or Expo/React Native if cross-platform is requested)
   - web_saas / marketplace_directory → Next.js (App Router) + SQLite/Postgres via Prisma, Stripe for billing
   - ai_tool → the above plus the Claude API (official `anthropic` / `@anthropic-ai/sdk` SDK)
   - automation → Python or Node CLI/service with clear config; add a cron/webhook entry point
   - browser_extension → Manifest V3 + TypeScript
   - content → an outline, scripts/posts, and a publishing calendar instead of code
   - marketing_service → offer page, outreach templates, and a lead-tracking sheet/app
5. Implement the MVP end to end, with tests for the core flow, and make sure it runs locally.
6. Write landing-page (or store listing) copy that uses the users' own words from the evidence quotes.
7. Finish with `README.md` (setup, run, deploy) and a short list of the next 3 features to validate.
