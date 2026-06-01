# Prompt Pack

These markdown files are loaded at runtime by `summarizer.py` and `briefer.py`.
You can change the clustering or brief style without redeploying code:

- `cluster-cn.md` controls Chinese thread clustering.
- `cluster-intl.md` controls international thread clustering.
- `daily-brief.md` controls the cross-region Daily Brief.

Keep placeholders intact:

- `cluster-*.md`: `{items_str}`
- `daily-brief.md`: `{today}`, `{days_back}`, `{today_cn_str}`, `{today_intl_str}`, `{history_str}`

When examples contain literal JSON braces, escape them as `{{` and `}}` because
the templates are rendered with Python `.format(...)`.
