# Session Handoff

Last updated: 2026-06-01

## Current State

- Project root: `/Users/mercy/projects/auto scripts/trending-scraper`
- Public GitHub repo: `https://github.com/MelloMercy/trending-scraper`
- Current branch: `main`
- Initial public release commit: `830db06 Initial public release`
- Local service URL: `http://localhost:11001`
- Local server start command:

```bash
bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"
```

## What Landed

- FastAPI + React dashboard for daily trending aggregation across CN and INTL sources.
- High-signal view backed by `follow-builders` plus local RSS/podcast sources.
- Public feed layer:
  - `GET /api/feed/latest`
  - `feeds/latest.json`
  - `feeds/YYYY-MM-DD.json`
  - Default export now uses the latest snapshot with data, avoiding empty cross-day feeds.
- Prompt externalization and UI editor:
  - `prompts/cluster-cn.md`
  - `prompts/cluster-intl.md`
  - `prompts/daily-brief.md`
  - `GET/POST /api/prompts`
  - Frontend `Prompt` view with placeholder validation and rerun controls.
- Publish bundle for future WeChat Official Account workflow:
  - `publisher.py`
  - `scripts/export_publish_bundle.py`
  - `GET /api/publish/latest`
  - generated local-only files under `publish/latest.*` and `publish/YYYY-MM-DD/`.
- Public-release hardening:
  - `.gitignore` blocks secrets and local runtime files.
  - `scripts/audit_public_release.py` checks for common secret patterns without printing secret values.
  - `docs/public-release-checklist.md` documents the public GitHub checklist.

## Privacy Boundary

Do not commit or print:

- `config.json`
- `.env*`
- `data/`
- `data/trending.db`
- `data/xhs_cookies.json`
- `data/*.log`
- DeepSeek API keys
- WeChat AppSecret / access tokens
- local publish drafts under `publish/latest*` and `publish/YYYY-MM-DD/`

Expected audit output may include:

```text
NOTE local-only present: config.json
NOTE local-only present: data
OK public release audit passed
```

The notes are fine. They mean local-only files exist and are ignored.

## Verified Commands

```bash
cd "/Users/mercy/projects/auto scripts/trending-scraper"
.venv/bin/python scripts/audit_public_release.py
.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py scripts/audit_public_release.py
.venv/bin/python scripts/export_public_feed.py
.venv/bin/python scripts/export_publish_bundle.py
cd webui && npm run lint && npm run build
```

Browser QA already verified:

- `http://localhost:11001`
- `高信号` view renders with partial upstream warning handling.
- `Prompt` view loads prompt files, switches tabs, detects dirty state, and restores clean state.

## Current Local Runtime Files

These are intentionally ignored:

- `.venv/`
- `config.json`
- `data/`
- `static/`
- `webui/node_modules/`
- `publish/latest*`
- `publish/2026-05-31/`
- `__pycache__/`
- `*.tsbuildinfo`

## Recommended Next Work

1. Add GitHub Actions for scheduled public feed generation.
2. Decide whether GitHub raw is enough as the public feed host, or whether R2/S3 is preferred.
3. Add a WeChat draft adapter after AppID/AppSecret and cover image/media flow are decided.
4. Keep delivery separate from scraping: use `publish/latest-wechat-draft.json` as the future adapter input.

## New Session Opener

Copy this paragraph into a new session:

Continue `/Users/mercy/projects/auto scripts/trending-scraper`. First read `SESSION-HANDOFF.md`, `README.md`, `docs/public-release-checklist.md`, `docs/follow-builders-adaptation.md`, `SKILL.md`, and `prompts/README.md`. The project is public at `https://github.com/MelloMercy/trending-scraper` on `main`; preserve the privacy boundary: never commit or print `config.json`, `.env*`, `data/`, DeepSeek keys, Xiaohongshu cookies, WeChat secrets/tokens, or local `publish/latest*` drafts. Start locally with `bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"` and verify with `.venv/bin/python scripts/audit_public_release.py`, `.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py scripts/audit_public_release.py`, `.venv/bin/python scripts/export_public_feed.py`, `.venv/bin/python scripts/export_publish_bundle.py`, and `cd webui && npm run lint && npm run build`. Next priority: add GitHub Actions/R2/S3 publication for `feeds/latest.json` and then build the WeChat Official Account draft adapter from `publish/latest-wechat-draft.json`.
