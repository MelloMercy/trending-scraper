# Session Handoff

Last updated: 2026-06-01 (feed publication + WeChat draft adapter)

## Current State

- Project root: `/Users/mercy/projects/auto scripts/trending-scraper`
- Public GitHub repo: `https://github.com/MelloMercy/trending-scraper`
- Current branch: `main`
- Initial public release commit: `830db06 Initial public release`
- Local service URL: `http://localhost:11001`
- Feed publication + WeChat draft adapter built and verified locally; **not yet
  committed/pushed** (working tree has the new files + today's feed snapshot).
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
- Feed publication (this session):
  - `scripts/validate_feed.py` — stdlib public-feed schema validator (CI gate + Pages preflight).
  - `scripts/publish_feed.py` — `--target git` (audit + stage only `feeds/` + commit + push)
    and `--target r2|s3` (S3-compatible upload; creds via env; `--dry-run` default-safe).
  - `.github/workflows/`: `validate-feed.yml` (audit + compile + feed schema + unittest + webui build),
    `publish-pages.yml` (deploy `feeds/` to GitHub Pages), `sync-storage.yml` (opt-in R2/S3 via secrets).
  - `requirements-publish.txt` — optional `boto3` for object-storage upload.
- WeChat Official Account draft adapter (this session):
  - `wechat_adapter.py` — `get_access_token` (on-disk cache), `upload_permanent_thumb`
    (cover → `thumb_media_id`), `add_draft` (UTF-8 `ensure_ascii=False` body), typed `WeChatError`.
  - `scripts/publish_wechat_draft.py` — CLI, **dry-run by default**, `--submit` for live,
    `--cover` / `--thumb-media-id`. Creates a draft only; human publishes.
  - `publisher.py` now emits the required `thumb_media_id` field (empty placeholder).
  - `config.py` / `config.example.json` add `wechat_appid` + `wechat_appsecret` (secret masked).
  - `tests/` — 37 unittest cases (schema validator, upload planner, token cache, draft shaping, API errors).
  - Operational guide: `docs/publishing.md`.

## Privacy Boundary

Do not commit or print:

- `config.json`
- `.env*`
- `data/`
- `data/trending.db`
- `data/xhs_cookies.json`
- `data/*.log`
- `data/wechat_token.json` (access-token cache)
- DeepSeek API keys
- WeChat AppID/AppSecret (`config.json` `wechat_*`), access tokens
- S3/R2 secret keys (env / repo secrets only)
- local publish drafts under `publish/latest*` and `publish/YYYY-MM-DD/`
- `_site/` (GitHub Pages staging dir)

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
.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py wechat_adapter.py scripts/audit_public_release.py scripts/validate_feed.py scripts/publish_feed.py scripts/publish_wechat_draft.py
.venv/bin/python scripts/validate_feed.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/export_public_feed.py
.venv/bin/python scripts/export_publish_bundle.py
cd webui && npm run lint && npm run build
```

All green as of 2026-06-01: audit passes, 37 unit tests pass, feed schema valid,
webui lint + build succeed. `publish_feed.py` (git/r2/s3) and
`publish_wechat_draft.py` dry-runs verified; live WeChat submit is **unverified**
(needs real AppID/AppSecret + IP whitelist + a cover image — see `docs/publishing.md`).

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

1. Decide whether to commit/push this session's work (new files + today's feed
   snapshot). Pushing is outward-facing; the audit is the safety gate.
2. Enable GitHub Pages (Settings → Pages → Source: GitHub Actions), then publish
   with `scripts/publish_feed.py --target git` so `publish-pages.yml` deploys it.
3. Pick the object-storage host if desired (R2/S3): set repo secrets for
   `sync-storage.yml`, or run `publish_feed.py --target r2` locally.
4. Do a real WeChat draft submit once AppID/AppSecret + IP whitelist + a cover
   image are available; verify the live `draft/add` path end-to-end.
5. Optional: auto-push `feeds/` from `run_daily.sh` after the launchd run (gated,
   audited) so publication is fully hands-off.
6. Still open from before: historical trend chart; more platforms (微博/头条/雪球).

## New Session Opener

Copy this paragraph into a new session:

Continue `/Users/mercy/projects/auto scripts/trending-scraper`. First read `SESSION-HANDOFF.md`, `README.md`, `docs/publishing.md`, `docs/public-release-checklist.md`, `docs/follow-builders-adaptation.md`, `SKILL.md`, and `prompts/README.md`. The project is public at `https://github.com/MelloMercy/trending-scraper` on `main`; preserve the privacy boundary: never commit or print `config.json`, `.env*`, `data/` (incl. `wechat_token.json`), DeepSeek keys, Xiaohongshu cookies, WeChat AppID/AppSecret/tokens, S3/R2 secret keys, or local `publish/latest*` drafts. Start locally with `bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"` and verify with `.venv/bin/python scripts/audit_public_release.py`, `.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py wechat_adapter.py scripts/audit_public_release.py scripts/validate_feed.py scripts/publish_feed.py scripts/publish_wechat_draft.py`, `.venv/bin/python scripts/validate_feed.py`, `.venv/bin/python -m unittest discover -s tests`, `.venv/bin/python scripts/export_public_feed.py`, `.venv/bin/python scripts/export_publish_bundle.py`, and `cd webui && npm run lint && npm run build`. Feed publication (`scripts/publish_feed.py` + GitHub Actions) and the WeChat draft adapter (`wechat_adapter.py` + `scripts/publish_wechat_draft.py`) are built and locally verified. Next priority: decide whether to commit/push this work, enable GitHub Pages and publish `feeds/`, wire R2/S3 secrets if wanted, and do a real WeChat `draft/add` submit (needs AppID/AppSecret + IP whitelist + cover image).
