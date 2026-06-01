# Public Release Checklist

Use this before creating or pushing a public GitHub repository.

## Local-only files

These must stay on the machine and must not be committed:

- `config.json` — may contain `deepseek_api_key`.
- `data/` — SQLite database, cookies, logs, browser/session state.
- `.env*` — local environment variables.
- `static/` build output — regenerated from `webui/`.
- `publish/latest*` and `publish/YYYY-MM-DD/` — editorial drafts for delivery.
- `.venv/`, `webui/node_modules/`, `__pycache__/`, `*.pyc`.

The source-safe examples are:

- `config.example.json`
- `README.md`
- `SKILL.md`
- `prompts/*.md`
- `curated_sources.json`
- `feeds/*.json` if this repo is also used as a public static-feed host.

## Preflight

Run:

```bash
cd "/Users/mercy/projects/auto scripts/trending-scraper"
.venv/bin/python scripts/audit_public_release.py
.venv/bin/python -m compileall -q main.py curated.py public_feed.py publisher.py summarizer.py briefer.py scrape_daily.py
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
