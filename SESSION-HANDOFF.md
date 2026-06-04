# Session Handoff

Last updated: 2026-06-04 (T1–T4 polish: live Pages demo + RSS + trends + source health + WeChat live closeout)

## Current State

- Project root: `/Users/mercy/projects/auto scripts/trending-scraper`
- Public GitHub repo: `https://github.com/MelloMercy/trending-scraper`
- Current branch: `main`
- Initial public release commit: `830db06 Initial public release`
- Local service URL: `http://localhost:11001`
- **Live public demo: `https://mellomercy.github.io/trending-scraper/`** (GitHub Pages,
  reads `feeds/latest.json`; RSS at `/latest.xml`; sources badge from `/health.json`).
- GitHub Pages enabled (`build_type: workflow`). Workflows live: `validate-feed`,
  `publish-pages`, `sync-storage`. Latest `validate-feed` on `main` is green.
- All T1–T4 work committed + pushed to `main`; feeds published through 2026-06-04.
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
  - `tests/` — unittest cases (schema validator, upload planner, token cache, draft shaping, API errors).
  - Operational guide: `docs/publishing.md`.
- T1–T4 polish (2026-06-04, all pushed + CI green + live):
  - **T1 live feed**: `LICENSE` (MIT); RSS `public_feed.build_rss` → `feeds/latest.xml`;
    `feeds/index.html` zero-dep static demo; `publish_feed.py --target git` publishes; Pages live.
  - **T2 trends**: `trends.py` cross-day + cross-platform persistence (`cluster_trends`, inverted
    bigram index + DF cap, <0.5s); `GET /api/trends`; `trends` in the feed; demo 趋势 section.
  - **T3 health/observability**: `health.py` per-source status + success rate; `GET /api/health` +
    `/api/health/badge`; `feeds/health.json` (+ `-full`); README live badge; `scrapers/contract.py`
    output contract enforced in `scrape_daily` + tested.
  - **T4 WeChat live closeout**: `--check` preflight (token fetch verifies creds + IP whitelist),
    errcode→hint map, pure-stdlib default cover. Live submit is still user-run (needs creds).
  - Tests now total **79** (`python -m unittest discover -s tests`).

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
.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py wechat_adapter.py trends.py health.py scrapers/contract.py scripts/audit_public_release.py scripts/validate_feed.py scripts/publish_feed.py scripts/publish_wechat_draft.py
.venv/bin/python scripts/validate_feed.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/export_public_feed.py
.venv/bin/python scripts/export_publish_bundle.py
cd webui && npm run lint && npm run build
```

All green as of 2026-06-04: audit passes, **79 unit tests** pass, feed schema valid,
webui lint + build succeed, and CI `validate-feed` is green on `main`. The live demo,
feed, RSS, and sources badge are verified serving from GitHub Pages. The live WeChat
`draft/add` is the only **unverified** path (user-run: needs real AppID/AppSecret + IP
whitelist — run `publish_wechat_draft.py --check` first; see `docs/publishing.md`).

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

1. Run the WeChat live submit (user-only): `publish_wechat_draft.py --check`
   (verifies creds + IP whitelist), fix what it flags, then `--submit` with a real
   `--cover`. This is the one path not yet verified end-to-end.
2. Keep `feeds/` fresh on Pages: run `publish_feed.py --target git` after a scrape
   (or wire it into `run_daily.sh`, gated + audited) for hands-off daily publishing.
3. Optional R2/S3: set `sync-storage.yml` repo secrets, or `publish_feed.py --target r2`.
4. Optional polish: React local-UI trends view / line chart; more platforms (微博/头条/雪球).
5. OpenAI Codex-for-OSS application was drafted in chat — submit if desired (note: repo
   is new with low traction; the program targets widely-adopted/critical OSS).

## New Session Opener

Copy this paragraph into a new session:

Continue `/Users/mercy/projects/auto scripts/trending-scraper`. First read `SESSION-HANDOFF.md`, `README.md`, `docs/publishing.md`, `docs/public-release-checklist.md`, `docs/follow-builders-adaptation.md`, `SKILL.md`, and `prompts/README.md`. The project is public at `https://github.com/MelloMercy/trending-scraper` on `main`, with a live GitHub Pages demo at `https://mellomercy.github.io/trending-scraper/`. Preserve the privacy boundary: never commit or print `config.json`, `.env*`, `data/` (incl. `wechat_token.json`, `wechat-cover-default.png`), DeepSeek keys, Xiaohongshu cookies, WeChat AppID/AppSecret/tokens, S3/R2 secret keys, or local `publish/latest*` drafts; before any commit, show the staged-file list + run `scripts/audit_public_release.py` + scan for secrets. Start locally with `bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"` and verify with the commands under “Verified Commands” above. T1–T4 are done, pushed, CI-green, and live: MIT license, RSS (`feeds/latest.xml`), zero-dep static demo (`feeds/index.html`), cross-day trends (`trends.py` + `/api/trends`), source health/observability (`health.py` + `/api/health` + README badge + `scrapers/contract.py`), and the WeChat live-submit closeout (`publish_wechat_draft.py --check` doctor + errcode hints + default cover). Next priority: the user runs the WeChat live `--submit` (needs their AppID/AppSecret + IP whitelist — `--check` first); optionally auto-publish `feeds/` and add a React trends view. To publish feed data, use `scripts/publish_feed.py --target git` (audits, stages only `feeds/`, commits, pushes → triggers `publish-pages`).
