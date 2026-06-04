# Publishing

Two independent delivery paths, both starting from artifacts the daily run
already produces. Scraping stays on one local machine (Playwright, cookies,
SQLite); publication only moves the *exported* files. Nothing here runs a
scraper or calls the LLM.

```
scrape_daily.py ─┬─ feeds/*.json ──────────► public feed (GitHub Pages / raw / R2 / S3)
                 └─ publish/latest-wechat-draft.json ──► WeChat Official Account draft
```

---

## 1. Public feed (`feeds/*.json` → CDN)

The exporter (`scripts/export_public_feed.py`, also run automatically by
`scrape_daily.py`) writes `feeds/latest.json`, `feeds/latest-cn.json`,
`feeds/latest-intl.json`, and dated snapshots. Pick one or more hosts.

### Option A — GitHub Pages (recommended GitHub-native CDN)

Clean URLs with correct content-type, CORS, and caching:
`https://<owner>.github.io/<repo>/latest.json`.

1. One-time: repo **Settings → Pages → Build and deployment → Source: GitHub
   Actions**.
2. Publish the feed from the local machine (audits, stages **only** `feeds/`,
   commits, pushes):
   ```bash
   .venv/bin/python scripts/publish_feed.py --target git
   ```
3. `.github/workflows/publish-pages.yml` then validates and deploys `feeds/` on
   every push that touches it.

Consumers:
```bash
curl -s https://<owner>.github.io/<repo>/latest.json
curl -s https://<owner>.github.io/<repo>/latest-intl.json
```

### Option B — GitHub raw

If you just commit `feeds/*.json` (the `--target git` step above) you can also
read them directly without Pages:
```bash
curl -s https://raw.githubusercontent.com/<owner>/<repo>/main/feeds/latest.json
```
Pages is preferred (raw has stricter caching and no proper content-type).

### Option C — R2 / S3 (object storage)

`scripts/publish_feed.py` uploads to any S3-compatible bucket (Cloudflare R2 is
S3-compatible). Credentials come from environment variables and are never
printed; the secret access key is env-only (never a flag).

```bash
pip install -r requirements-publish.txt   # boto3, optional

export S3_ENDPOINT_URL="https://<account>.r2.cloudflarestorage.com"  # R2; omit for AWS
export S3_BUCKET="my-feed-bucket"
export S3_ACCESS_KEY_ID="..."
export S3_SECRET_ACCESS_KEY="..."          # env only
export S3_REGION="auto"                     # R2: auto
export S3_KEY_PREFIX="feeds"                # optional
export PUBLIC_FEED_BASE_URL="https://cdn.example.com"  # optional, for printed URLs

# Always dry-run first — prints the plan, touches nothing, needs no creds:
.venv/bin/python scripts/publish_feed.py --target r2 --dry-run
# Then upload (latest*.json + the current dated snapshot; --all for everything):
.venv/bin/python scripts/publish_feed.py --target r2
```

| Variable | Purpose | R2 example |
|----------|---------|-----------|
| `S3_ENDPOINT_URL` | custom endpoint (required for R2) | `https://<acct>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | target bucket | `my-feed-bucket` |
| `S3_ACCESS_KEY_ID` | access key id | — |
| `S3_SECRET_ACCESS_KEY` | secret key (env only) | — |
| `S3_REGION` | region | `auto` |
| `S3_KEY_PREFIX` | key prefix | `feeds` |
| `PUBLIC_FEED_BASE_URL` | base URL for printed links | `https://cdn.example.com` |

Aliases `R2_*` and `AWS_*` are also accepted. CLI flags override env.

To let **GitHub Actions** do the upload instead (keeps bucket creds off the
local machine), set the same names as repo secrets and keep
`.github/workflows/sync-storage.yml`. It no-ops while `S3_BUCKET` is unset, so
it is safe to leave enabled before you have a bucket.

### CI gate — `.github/workflows/validate-feed.yml`

Runs on every push/PR, no secrets:

- `scripts/audit_public_release.py` — leaked-secret / ignore-rule scan.
- `compileall` of the Python sources.
- `scripts/validate_feed.py` — checks `feeds/latest*.json` against the
  public-feed schema (`schema_version`, types, `snapshot_date` format,
  per-platform `count == len(items)`, region matches filename).
- `python -m unittest discover -s tests` — adapter + uploader + validator tests.
- `cd webui && npm ci && npm run lint && npm run build`.

---

## 2. WeChat Official Account draft adapter

`scripts/publish_wechat_draft.py` turns `publish/latest-wechat-draft.json`
(produced by `scripts/export_publish_bundle.py`) into a **draft** in a WeChat
Official Account via the official API. It never publishes or mass-sends — a
human reviews and publishes from the WeChat editor (草稿箱).

Pipeline: `access_token` → upload cover as permanent material (`thumb_media_id`)
→ `draft/add` → draft `media_id`.

### Credentials

Set the AppID/AppSecret either through the config API (stored in the gitignored
`config.json`, AppSecret masked by `/api/config`) or via environment variables
(env wins):

```bash
# via config (local UI/API):
curl -X POST -H 'Content-Type: application/json' \
  -d '{"wechat_appid":"wx...","wechat_appsecret":"..."}' \
  http://localhost:11001/api/config

# or via environment:
export WECHAT_APPID="wx..."
export WECHAT_APPSECRET="..."
```

### Cover image

`draft/add` requires a `thumb_media_id` per article. Provide one of:

- `--cover path/to/cover.jpg` — uploaded as a permanent image material at submit
  time; its `media_id` becomes the thumb.
- `--thumb-media-id <id>` — reuse a permanent material you uploaded earlier.
- nothing — a simple placeholder cover is generated (pure-Python, ≈2.35:1) so the
  submit isn't blocked; supply a real `--cover` for actual publishing.

### Run — 3 steps to go live

```bash
# 1. Dry-run (default): load the draft, print the plan, list what's missing.
.venv/bin/python scripts/publish_wechat_draft.py

# 2. Preflight against the live API WITHOUT creating anything: it fetches an
#    access token (verifies AppID/AppSecret AND the IP whitelist — the #1 live
#    blocker) and validates the draft + cover.
.venv/bin/python scripts/publish_wechat_draft.py --check

# 3. Once --check reports READY, create the draft:
.venv/bin/python scripts/publish_wechat_draft.py --cover cover.jpg --submit
#    (omit --cover to use the placeholder; --date YYYY-MM-DD for a past bundle)
```

`--check` is the fast path to a first-try live submit: if it reports
`errcode=40164` your server IP isn't whitelisted, `40125` means a bad AppSecret,
etc. (table below). It creates nothing, so it's safe to run repeatedly.

### Common errcodes

The adapter maps these to actionable hints in its output:

| errcode | meaning / fix |
|---------|---------------|
| 40013 | AppID invalid — check `wechat_appid` |
| 40125 | AppSecret invalid — check `wechat_appsecret` (no stray spaces/newlines) |
| 40164 | caller IP not in whitelist — add your egress IP under 基本配置 → IP白名单 |
| 45009 | rate limited (token fetch has a quota too) — back off |
| 48001 | API unauthorized — draft/material APIs usually need a **verified service account** |
| 53401 | cover/thumb invalid |

### Operational caveats

- **IP whitelist.** WeChat only issues `access_token` to server IPs on the OA's
  whitelist (公众平台 → 设置与开发 → 基本配置 → IP白名单). A local machine with a
  dynamic IP must keep this updated, or run the adapter from a fixed-IP host.
- **Access-token cache.** Tokens are cached at `data/wechat_token.json`
  (gitignored under `data/` and `*token*.json`) and reused until ~5 min before
  expiry. Tokens are rate-limited, so don't fetch them in a tight loop.
- **External links.** WeChat articles restrict external `<a href>` links for
  unverified accounts; the draft is still reviewable/editable before publishing.
- **Draft only.** Mass-send / publish is intentionally out of scope.
