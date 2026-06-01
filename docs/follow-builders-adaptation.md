# follow-builders Adaptation

This project borrows three high-leverage ideas from `zarazhangrui/follow-builders`
and turns them into local artifacts.

## 1. Centralized Feed

**Goal:** one machine runs the expensive scraper stack, then publishes static JSON
that other clients can read.

Current implementation:

- Runtime endpoint: `GET /api/feed/latest`
- Publish-preview endpoint: `GET /api/publish/latest`
- Region filters: `GET /api/feed/latest?region=cn` and `?region=intl`
- Export script: `scripts/export_public_feed.py`
- Publish bundle script: `scripts/export_publish_bundle.py`
- Launchd path: `scrape_daily.py` exports `feeds/latest.json` after successful runs
- Daily publish artifacts: `publish/YYYY-MM-DD/digest.md`, `.html`, `.txt`, `wechat-draft.json`
- Artifacts: `feeds/latest.json` plus dated `feeds/YYYY-MM-DD.json`

Publishing options:

- GitHub repo as CDN: commit `feeds/*.json`, consume via raw GitHub URLs.
- R2/S3: sync `feeds/` after `run_daily.sh`.
- Private LAN: keep FastAPI running and consume `/api/feed/latest`.

The feed deliberately does not run scrapers or LLM calls. It reads current
SQLite rows plus cached clusters/briefs, which keeps the client path cheap and
predictable.

The publish bundle is the bridge to WeChat/manual delivery: it turns the cached
Daily Brief into reviewable Markdown, HTML, text, and a draft-shaped JSON payload
without requiring WeChat credentials yet.

## 2. Prompt Files

**Goal:** summary and clustering style can be changed through plain markdown,
instead of editing Python f-strings.

Current implementation:

- `prompts/cluster-cn.md`
- `prompts/cluster-intl.md`
- `prompts/daily-brief.md`
- Runtime editor: front-end `Prompt` view backed by `GET/POST /api/prompts`

`summarizer.py` and `briefer.py` load these files at runtime and fall back to
their baked-in prompts if a file is missing. This keeps the app durable while
making prompt iteration auditable through `git diff`.

The prompt editor exposes only the known markdown files, validates required
placeholders before saving, and provides one-click refresh targets for CN
clustering, INTL clustering, and Daily Brief regeneration.

## 3. Agent Skill Wrapper

**Goal:** make setup and operation conversational.

Current implementation:

- Root `SKILL.md` describes onboarding, startup, region/view choice, schedule,
  DeepSeek key setup, prompt editing, public feed export, and daily brief access.

A user can hand this repository to an agent and ask it to set up or adjust the
tool without memorizing launchd, uvicorn, prompt-file, or export commands.

## What Remains Optional

- A separate hosted repo or bucket for public feed publication.
- Delivery adapters for Telegram/Discord/email.
- A WeChat Official Account adapter that turns `publish/latest-wechat-draft.json`
  into a real draft after media credentials and cover-image flow are configured.
