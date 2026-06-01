# Public Feed Artifacts

`scripts/export_public_feed.py` writes CDN-friendly JSON here:

- `latest.json` - latest all-region feed.
- `YYYY-MM-DD.json` - immutable daily snapshot.
- `latest-cn.json` / `latest-intl.json` - optional region-only exports.

These files are intentionally static. A publishing machine can run the full
scraper, commit or upload this directory, and lightweight clients can consume
the JSON without installing Playwright or carrying cookies.
