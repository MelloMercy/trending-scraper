---
name: trending-scraper
description: Operate the local daily trending content scraper, high-signal feed, Daily Brief, prompt files, public-feed export, and launchd schedule.
---

# Trending Scraper Skill

Use this skill when the user wants to set up, run, tune, publish, or receive
briefs from `/Users/mercy/projects/auto scripts/trending-scraper`.

## First Check

1. Work from the project root:
   `cd "/Users/mercy/projects/auto scripts/trending-scraper"`
2. Check whether the web service is reachable:
   `curl -fsS http://localhost:11001/api/platforms`
3. If it is not running, start it with one of:
   - `trending123`
   - `bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"`
   - `RELOAD=1 bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"`

## Onboarding Flow

Ask only for choices that cannot be inferred:

1. Region focus: `cn`, `intl`, or both.
2. Main view: `简报`, `高信号`, `Prompt`, `杂志`, or `时间流`.
3. Schedule time if they want daily automation. The local default is 08:00.
4. Whether they want DeepSeek-powered clustering/briefing.
5. Whether public feed publication should be local-only, GitHub raw, or R2/S3.
6. Whether the daily digest should be used manually, published to WeChat later,
   or pushed to another channel.

## Core Commands

Start web:

```bash
bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"
```

Start with reload:

```bash
RELOAD=1 bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"
```

Run daily scrape, clustering, brief, public-feed export, and publish bundle:

```bash
"/Users/mercy/projects/auto scripts/trending-scraper/.venv/bin/python" \
  "/Users/mercy/projects/auto scripts/trending-scraper/scrape_daily.py"
```

Export static public feed only:

```bash
"/Users/mercy/projects/auto scripts/trending-scraper/.venv/bin/python" \
  "/Users/mercy/projects/auto scripts/trending-scraper/scripts/export_public_feed.py"
```

Export WeChat/manual-delivery digest only:

```bash
"/Users/mercy/projects/auto scripts/trending-scraper/.venv/bin/python" \
  "/Users/mercy/projects/auto scripts/trending-scraper/scripts/export_publish_bundle.py"
```

Check launchd:

```bash
launchctl print "gui/$(id -u)/com.local.trending-scraper"
```

## Data Surfaces

- Web UI: `http://localhost:11001`
- International UI: `http://localhost:11001?region=intl`
- Daily Brief: `GET /api/brief/today`
- High-signal curated feed: `GET /api/curated/latest`
- Static-feed payload: `GET /api/feed/latest`
- Publish digest preview: `GET /api/publish/latest`
- Prompt editor: `GET /api/prompts`, `POST /api/prompts/{prompt_id}`
- Public feed files: `feeds/latest.json` and `feeds/YYYY-MM-DD.json`
- Publish bundle files: `publish/latest.md`, `publish/latest.html`,
  `publish/latest-wechat-draft.json`

## Prompt Tuning

Prompt files are loaded at runtime:

- `prompts/cluster-cn.md`
- `prompts/cluster-intl.md`
- `prompts/daily-brief.md`

When the user asks for a style change, edit the relevant prompt file, then
refresh with `force=true` where appropriate:

- `GET /api/aggregate/today?force_llm=true`
- `GET /api/brief/today?force=true`

The web UI has a `Prompt` view for editing `prompts/*.md`. It validates required
placeholders before saving and can trigger CN clustering, INTL clustering, or
Daily Brief regeneration. Keep required placeholders intact. See
`prompts/README.md`.

## Public Feed Publishing

The follow-builders-style publishing path is:

```text
scrape_daily.py -> SQLite/cache -> scripts/export_public_feed.py -> feeds/*.json
```

For GitHub raw publication, commit the generated `feeds/*.json` files from a
publishing machine. For object storage, sync the `feeds/` directory after
`run_daily.sh`.

## WeChat / Digest Publishing

The safe first step toward WeChat Official Account publishing is:

```text
cached Daily Brief -> scripts/export_publish_bundle.py -> publish/latest.*
```

Use `publish/latest.md` for manual review, `publish/latest.html` for rich-text
copy/paste workflows, and `publish/latest-wechat-draft.json` as the future input
to a WeChat draft adapter. Do not add WeChat app secrets to docs or commits.

## Guardrails

- Do not print or commit `config.json`, DeepSeek keys, or Xiaohongshu cookies.
- Before public GitHub publication, run
  `.venv/bin/python scripts/audit_public_release.py` and read
  `docs/public-release-checklist.md`.
- Do not regenerate the Daily Brief unless both `cn` and `intl` clusters are
  available for the same snapshot date.
- Treat `partial` high-signal status as degraded upstream data, not total
  failure.
