"""Publish-ready daily digest artifacts.

This layer turns cached scraper/LLM output into stable files that can be copied
into WeChat Official Account drafts now, and adapted to GitHub/R2/S3 or official
delivery APIs later. It is deliberately read-only: no scraping and no LLM calls.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import briefer
import db
import public_feed

ROOT = Path(__file__).parent
DEFAULT_PUBLISH_DIR = ROOT / "publish"

SECTIONS = [
    ("consensus", "跨区共识"),
    ("cn_only", "国内重点"),
    ("intl_only", "国际重点"),
    ("persistent", "持续追踪"),
    ("emerging", "早期信号"),
]


def latest_publishable_date() -> str | None:
    """Return the latest snapshot date that has a cached usable Daily Brief."""
    briefer.init_brief_table()
    if not db.DB_PATH.exists():
        return None
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT snapshot_date
            FROM daily_brief
            WHERE status IN ('ok', 'cached')
            ORDER BY snapshot_date DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["snapshot_date"]) if row else None


def build_daily_digest(
    platforms: public_feed.PlatformRegistry,
    labeler: public_feed.PlatformLabeler,
    snapshot_date: str | None = None,
    feed_url: str | None = None,
) -> dict[str, Any]:
    """Build one publish-ready digest from cached brief + public feed summary."""
    db.init_db()
    snapshot_date = snapshot_date or latest_publishable_date()
    if not snapshot_date:
        return {
            "status": "skipped",
            "error": "No cached Daily Brief found. Run scrape_daily.py with DeepSeek enabled first.",
        }

    brief = briefer.get_cached_brief(snapshot_date)
    if not brief or brief.get("status") not in {"ok", "cached"}:
        return {
            "status": "skipped",
            "snapshot_date": snapshot_date,
            "error": "No usable cached Daily Brief for this snapshot date.",
        }

    feed = public_feed.build_public_feed(platforms, labeler, snapshot_date=snapshot_date)
    title = f"每日热点精华｜{snapshot_date}"
    digest = _digest_text(brief)
    markdown = _render_markdown(title, brief, feed_url)
    html_content = _render_html(title, brief, feed_url)
    text = _render_text(title, brief, feed_url)

    return {
        "status": "ok",
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_date": snapshot_date,
        "title": title,
        "digest": digest,
        "summary": feed.get("summary"),
        "feed_url": feed_url,
        "formats": {
            "markdown": markdown,
            "html": html_content,
            "text": text,
        },
        "wechat_draft": {
            "title": title,
            "author": "",
            "digest": digest[:120],
            "content": html_content,
            "content_source_url": feed_url or "",
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        },
    }


def write_daily_digest_bundle(
    platforms: public_feed.PlatformRegistry,
    labeler: public_feed.PlatformLabeler,
    out_dir: str | Path = DEFAULT_PUBLISH_DIR,
    snapshot_date: str | None = None,
    feed_url: str | None = None,
) -> dict[str, Any]:
    """Write dated and latest publish artifacts, returning paths + status."""
    payload = build_daily_digest(platforms, labeler, snapshot_date=snapshot_date, feed_url=feed_url)
    if payload.get("status") != "ok":
        return payload

    root = Path(out_dir)
    dated_dir = root / str(payload["snapshot_date"])
    dated_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = dated_dir / "manifest.json"
    markdown_path = dated_dir / "digest.md"
    html_path = dated_dir / "digest.html"
    text_path = dated_dir / "digest.txt"
    wechat_path = dated_dir / "wechat-draft.json"

    _write_json(manifest_path, {k: v for k, v in payload.items() if k != "formats"})
    markdown_path.write_text(payload["formats"]["markdown"], encoding="utf-8")
    html_path.write_text(payload["formats"]["html"], encoding="utf-8")
    text_path.write_text(payload["formats"]["text"], encoding="utf-8")
    _write_json(wechat_path, payload["wechat_draft"])

    latest_paths = {
        "latest_manifest": root / "latest-manifest.json",
        "latest_markdown": root / "latest.md",
        "latest_html": root / "latest.html",
        "latest_text": root / "latest.txt",
        "latest_wechat": root / "latest-wechat-draft.json",
    }
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, latest_paths["latest_manifest"])
    shutil.copyfile(markdown_path, latest_paths["latest_markdown"])
    shutil.copyfile(html_path, latest_paths["latest_html"])
    shutil.copyfile(text_path, latest_paths["latest_text"])
    shutil.copyfile(wechat_path, latest_paths["latest_wechat"])

    return {
        "status": "ok",
        "snapshot_date": payload["snapshot_date"],
        "dated_dir": str(dated_dir),
        "manifest": str(manifest_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
        "text": str(text_path),
        "wechat_draft": str(wechat_path),
        **{k: str(v) for k, v in latest_paths.items()},
    }


def _digest_text(brief: dict[str, Any]) -> str:
    narrative = _compact(brief.get("narrative") or "")
    if narrative:
        return narrative[:160]
    titles = []
    for key, _ in SECTIONS:
        titles.extend(str(item.get("title") or "") for item in brief.get(key) or [])
    return "；".join(t for t in titles if t)[:160]


def _render_markdown(title: str, brief: dict[str, Any], feed_url: str | None) -> str:
    lines = [
        f"# {title}",
        "",
        _compact(brief.get("narrative") or ""),
        "",
    ]
    for key, label in SECTIONS:
        items = brief.get(key) or []
        if not items:
            continue
        lines.extend([f"## {label}", ""])
        for idx, item in enumerate(items, 1):
            lines.extend(_markdown_item(idx, item))
            lines.append("")
    if feed_url:
        lines.extend(["---", "", f"完整 public feed: {feed_url}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_html(title: str, brief: dict[str, Any], feed_url: str | None) -> str:
    parts = [
        "<article>",
        f"<h1>{html.escape(title)}</h1>",
    ]
    narrative = _compact(brief.get("narrative") or "")
    if narrative:
        parts.append(f"<p>{html.escape(narrative)}</p>")
    for key, label in SECTIONS:
        items = brief.get(key) or []
        if not items:
            continue
        parts.append(f"<h2>{html.escape(label)}</h2>")
        for item in items:
            parts.append("<section>")
            parts.append(f"<h3>{html.escape(str(item.get('title') or '未命名话题'))}</h3>")
            summary = _compact(item.get("summary") or "")
            if summary:
                parts.append(f"<p>{html.escape(summary)}</p>")
            source_html = _render_html_sources(item)
            if source_html:
                parts.append(source_html)
            parts.append("</section>")
    if feed_url:
        safe_url = html.escape(feed_url, quote=True)
        parts.append(f'<p><a href="{safe_url}">完整 public feed</a></p>')
    parts.append("</article>")
    return "\n".join(parts) + "\n"


def _render_text(title: str, brief: dict[str, Any], feed_url: str | None) -> str:
    markdown = _render_markdown(title, brief, feed_url)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "")
    return text


def _markdown_item(idx: int, item: dict[str, Any]) -> list[str]:
    title = str(item.get("title") or "未命名话题")
    summary = _compact(item.get("summary") or "")
    lines = [f"{idx}. **{title}**"]
    if summary:
        lines.append(f"   {summary}")
    sources = _source_lines(item)
    if sources:
        lines.extend(f"   - {row}" for row in sources)
    return lines


def _source_lines(item: dict[str, Any]) -> list[str]:
    lines = []
    for label, key in (("CN", "cn_sources"), ("INTL", "intl_sources")):
        refs = item.get(key) or []
        for ref in refs[:3]:
            platform = ref.get("platform") or "source"
            rank = ref.get("rank")
            title = str(ref.get("title") or "")
            url = ref.get("url")
            prefix = f"{label} · {platform}"
            if rank:
                prefix += f" #{rank}"
            if url:
                lines.append(f"{prefix}: [{title}]({url})")
            else:
                lines.append(f"{prefix}: {title}")
    return lines


def _render_html_sources(item: dict[str, Any]) -> str:
    rows = _source_lines(item)
    if not rows:
        return ""
    lis = []
    for row in rows:
        match = re.match(r"(.+): \[([^\]]+)\]\(([^)]+)\)$", row)
        if match:
            prefix, text, url = match.groups()
            lis.append(
                f"<li>{html.escape(prefix)}: "
                f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a></li>'
            )
        else:
            lis.append(f"<li>{html.escape(row)}</li>")
    return "<ul>\n" + "\n".join(lis) + "\n</ul>"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
