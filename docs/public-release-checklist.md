# Public Release Checklist

Use this before creating or pushing a public GitHub repository.

## Local-only files

These must stay on the machine and must not be committed:

- `config.json` — may contain `deepseek_api_key`, `wechat_appid`, `wechat_appsecret`.
- `data/` — SQLite database, cookies, logs, `wechat_token.json`, session state.
- `.env*` — local environment variables.
- `static/` build output — regenerated from `webui/`.
- `publish/latest*` and `publish/YYYY-MM-DD/` — editorial drafts for delivery.
- `_site/` — GitHub Pages staging dir (assembled in CI / local test).
- `.venv/`, `webui/node_modules/`, `__pycache__/`, `*.pyc`.

The source-safe examples are:

- `config.example.json`
- `README.md`, `SKILL.md`, `docs/*.md`
- `prompts/*.md`
- `curated_sources.json`
- `wechat_adapter.py`, `scripts/publish_feed.py`, `scripts/validate_feed.py`,
  `scripts/publish_wechat_draft.py` — no embedded secrets (credentials come from
  env/config at runtime).
- `tests/*.py`, `.github/workflows/*.yml`, `requirements-publish.txt`.
- `feeds/*.json` if this repo is also used as a public static-feed host.

WeChat AppSecret and S3/R2 secret keys must never appear in committed files.
The adapter reads them from `config.json` (gitignored) or environment variables;
GitHub Actions reads them from repo secrets.

## Preflight

Run:

```bash
cd "/Users/mercy/projects/auto scripts/trending-scraper"
.venv/bin/python scripts/audit_public_release.py
.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py wechat_adapter.py scripts/audit_public_release.py scripts/validate_feed.py scripts/publish_feed.py scripts/publish_wechat_draft.py
.venv/bin/python scripts/validate_feed.py
.venv/bin/python -m unittest discover -s tests
cd webui && npm run lint && npm run build
```

Expected audit result:

```text
OK public release audit passed
```

`NOTE local-only present: ...` is fine. It means the file exists locally but is
covered by ignore rules.

## GitHub setup

This directory is not currently a git repository. When ready:

```bash
git init
git status --short --ignored
.venv/bin/python scripts/audit_public_release.py
git add .
git status --short
```

Before the first commit, check that none of these appear under staged files:

- `config.json`
- `data/`
- `.env*`
- `.venv/`
- `webui/node_modules/`
- `static/assets/`
- `publish/latest*`
- `publish/YYYY-MM-DD/`

After pushing to GitHub, enable GitHub secret scanning / push protection for the
repository.

## If a secret is exposed

1. Revoke or rotate the secret immediately.
2. Remove it from the repository.
3. If it was committed, rewrite history before making the repo public.
4. Treat cookies and API keys as compromised even if the repo was briefly public.
