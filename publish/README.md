# Publish Artifacts

`scripts/export_publish_bundle.py` writes WeChat/manual-delivery ready files here.

Generated files:

- `YYYY-MM-DD/digest.md` — Markdown article, easiest to review/edit.
- `YYYY-MM-DD/digest.html` — HTML article body for rich-text workflows.
- `YYYY-MM-DD/digest.txt` — plain text fallback.
- `YYYY-MM-DD/wechat-draft.json` — draft payload for the WeChat draft adapter.
- `YYYY-MM-DD/manifest.json` — metadata, title, digest, summary, and draft payload.
- `latest.*` — copies of the newest generated digest files.

The exporter is read-only. It uses cached Daily Brief and public-feed data, and
does not run scrapers or call the LLM.

`scripts/publish_wechat_draft.py` turns `latest-wechat-draft.json` into a WeChat
Official Account **draft** (dry-run by default; `--submit` to create it; a human
publishes from the editor). See [../docs/publishing.md](../docs/publishing.md).
