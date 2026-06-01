# Public Feed Artifacts

`scripts/export_public_feed.py` writes CDN-friendly JSON here:

- `latest.json` - latest all-region feed.
- `YYYY-MM-DD.json` - immutable daily snapshot.
- `latest-cn.json` / `latest-intl.json` - optional region-only exports.

These files are intentionally static. A publishing machine can run the full
scraper, commit or upload this directory, and lightweight clients can consume
the JSON without installing Playwright or carrying cookies.

Publish with `scripts/publish_feed.py` (`--target git` for GitHub Pages/raw,
`--target r2|s3` for object storage). `scripts/validate_feed.py` checks these
files against the public-feed schema (also enforced in CI). See
[../docs/publishing.md](../docs/publishing.md).
