"""Static public-feed exporter.

This is the follow-builders-inspired boundary: a machine that can run the full
scraper publishes JSON artifacts, while lightweight clients can consume the
already-normalized feed without Playwright, cookies, or local scraping.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import aggregator
import briefer
import db
import health as health_mod
import summarizer
import trends as trends_mod

ROOT = Path(__file__).parent
DEFAULT_FEED_DIR = ROOT / "feeds"


PlatformRegistry = Mapping[str, Mapping[str, Any]]
PlatformLabeler = Callable[[str], Mapping[str, Any]]


def build_public_feed(
    platforms: PlatformRegistry,
    labeler: PlatformLabeler,
    snapshot_date: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Build one static feed payload from current SQLite/cache state.

    The function is intentionally read-only: it never runs scrapers and never
    calls the LLM. If clusters/briefs are absent, the payload says so by leaving
    those fields as null.
    """
    db.init_db()
    summarizer.init_cache_table()
    briefer.init_brief_table()

    targets = _targets_for_region(platforms, region)
    snap = snapshot_date or latest_snapshot_date(platforms, region) or date.today().isoformat()
    regions = sorted({str(platforms[pid]["region"]) for pid in targets})

    platform_payloads = [_platform_payload(pid, labeler, snap) for pid in targets]
    region_payloads = {
        reg: _region_payload(reg, platforms, snap)
        for reg in regions
    }

    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_date": snap,
        "region": region or "all",
        "summary": {
            "platforms": len(platform_payloads),
            "items": sum(row["count"] for row in platform_payloads),
            "regions": {
                reg: {
                    "platforms": len(region_payloads[reg]["platforms"]),
                    "items": region_payloads[reg]["total_items"],
                    "themes_cached": bool(region_payloads[reg].get("themes")),
                }
                for reg in regions
            },
            "brief_cached": region is None and bool(briefer.get_cached_brief(snap)),
        },
        "platforms": platform_payloads,
        "regions": region_payloads,
        "trends": trends_mod.compute_trends(list(targets), days_back=7, limit=12),
        "brief": briefer.get_cached_brief(snap) if region is None else None,
    }


def write_public_feed(
    platforms: PlatformRegistry,
    labeler: PlatformLabeler,
    out_dir: str | Path = DEFAULT_FEED_DIR,
    snapshot_date: str | None = None,
    region: str | None = None,
    base_url: str | None = None,
) -> dict[str, str]:
    """Write dated and latest feed JSON (+ RSS for the all-region feed)."""
    payload = build_public_feed(platforms, labeler, snapshot_date=snapshot_date, region=region)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    suffix = "" if region is None else f"-{region}"
    dated = out / f"{payload['snapshot_date']}{suffix}.json"
    latest = out / f"latest{suffix}.json"
    _write_json(dated, payload)
    _write_json(latest, payload)
    result = {
        "snapshot_date": payload["snapshot_date"],
        "dated": str(dated),
        "latest": str(latest),
    }
    # RSS + health only for the all-region feed (the main published artifacts).
    if region is None:
        rss = build_rss(payload, base_url=base_url)
        rss_dated = out / f"{payload['snapshot_date']}.xml"
        rss_latest = out / "latest.xml"
        _write_text(rss_dated, rss)
        _write_text(rss_latest, rss)
        result["rss_latest"] = str(rss_latest)
        result["rss_dated"] = str(rss_dated)

        h = health_mod.compute_health(platforms, labeler)
        _write_json(out / "health.json", health_mod.badge_payload(h["healthy"], h["total"], h["overall"]))
        _write_json(out / "health-full.json", h)
        result["health"] = str(out / "health.json")
    return result


def latest_snapshot_date(platforms: PlatformRegistry, region: str | None = None) -> str | None:
    """Return latest snapshot date with rows for the selected platform scope."""
    db.init_db()
    targets = _targets_for_region(platforms, region)
    dates = []
    for pid in targets:
        history = db.get_history_dates(pid, limit=1)
        if history:
            dates.append(history[0])
    return max(dates) if dates else None


def _targets_for_region(platforms: PlatformRegistry, region: str | None) -> list[str]:
    return [
        pid
        for pid, meta in platforms.items()
        if region is None or meta.get("region") == region
    ]


def _platform_payload(pid: str, labeler: PlatformLabeler, snapshot_date: str) -> dict[str, Any]:
    meta = dict(labeler(pid))
    rows = [dict(row) for row in db.get_by_date(pid, snapshot_date)]
    return {
        "id": pid,
        "name": meta.get("name") or meta.get("label") or pid,
        "region": meta.get("region"),
        "snapshot_date": snapshot_date,
        "fetched_at": rows[0].get("fetched_at") if rows else None,
        "count": len(rows),
        "items": [
            {
                "rank": row.get("rank"),
                "title": row.get("title"),
                "url": row.get("url"),
                "hot_value": row.get("hot_value"),
                "cover": row.get("cover"),
                "fetched_at": row.get("fetched_at"),
            }
            for row in rows
        ],
    }


def _region_payload(region: str, platforms: PlatformRegistry, snapshot_date: str) -> dict[str, Any]:
    pids = [pid for pid, meta in platforms.items() if meta.get("region") == region]
    agg = aggregator.aggregate(snapshot_date, platforms=pids)
    themes = summarizer.get_cached_themes(snapshot_date, region)
    return {
        "platforms": pids,
        "total_items": int(agg.get("total_items") or 0),
        "aggregate": agg,
        "themes": themes,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ---- RSS 2.0 export ----

RSS_SECTIONS = [
    ("consensus", "跨区共识"),
    ("cn_only", "国内重点"),
    ("intl_only", "国际重点"),
    ("persistent", "持续追踪"),
    ("emerging", "早期信号"),
]


def build_rss(payload: dict[str, Any], base_url: str | None = None, max_items: int = 40) -> str:
    """Render a public feed payload as an RSS 2.0 document (string).

    Entries come from the cached Daily Brief sections when present, otherwise
    fall back to the top items across platforms — so the feed is useful even
    without DeepSeek configured.
    """
    snap = str(payload.get("snapshot_date") or date.today().isoformat())
    pub = _rfc822(snap)
    summary = payload.get("summary") or {}
    link = base_url.rstrip("/") if base_url else ""
    title = f"每日热点聚合 · {snap}"
    desc = f"{summary.get('platforms', 0)} 个平台 · {summary.get('items', 0)} 条热点的跨平台聚合与每日简报。"

    items = [_rss_item(entry, pub) for entry in _rss_entries(payload)[:max_items]]
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0">',
            "<channel>",
            f"<title>{escape(title)}</title>",
            f"<link>{escape(link)}</link>",
            f"<description>{escape(desc)}</description>",
            "<language>zh-cn</language>",
            f"<lastBuildDate>{pub}</lastBuildDate>",
            *items,
            "</channel>",
            "</rss>",
            "",
        ]
    )


def _rss_entries(payload: dict[str, Any]) -> list[dict[str, str]]:
    snap = str(payload.get("snapshot_date") or "")
    entries: list[dict[str, str]] = []
    brief = payload.get("brief")
    if isinstance(brief, dict):
        for key, label in RSS_SECTIONS:
            for idx, topic in enumerate(brief.get(key) or []):
                title = str(topic.get("title") or "").strip()
                if not title:
                    continue
                sources = (topic.get("cn_sources") or []) + (topic.get("intl_sources") or [])
                link = next((s["url"] for s in sources if s.get("url")), "")
                summary = str(topic.get("summary") or "").strip()
                desc = (f"<p>{html.escape(summary)}</p>" if summary else "") + _sources_html(sources)
                entries.append(
                    {
                        "title": f"[{label}] {title}",
                        "description": desc,
                        "link": link,
                        "guid": f"{snap}-{key}-{idx}",
                    }
                )
    if entries:
        return entries

    # Fallback: top few items per platform, deduped by title.
    seen: set[str] = set()
    for plat in payload.get("platforms", []):
        name = str(plat.get("name") or plat.get("id") or "")
        for item in (plat.get("items") or [])[:3]:
            title = str(item.get("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            url = str(item.get("url") or "")
            label = f"{name} · #{item.get('rank')}" if item.get("rank") else name
            entries.append(
                {
                    "title": title,
                    "description": f"<p>{html.escape(label)}</p>",
                    "link": url,
                    "guid": url or f"{snap}-{title}",
                }
            )
    return entries


def _rss_item(entry: dict[str, str], pub: str) -> str:
    link = entry.get("link") or ""
    guid = entry.get("guid") or link or entry["title"]
    is_perma = "true" if link and guid == link else "false"
    desc = (entry.get("description") or "").replace("]]>", "]]&gt;")
    parts = ["<item>", f"<title>{escape(entry['title'])}</title>"]
    if link:
        parts.append(f"<link>{escape(link)}</link>")
    parts.append(f'<guid isPermaLink="{is_perma}">{escape(str(guid))}</guid>')
    parts.append(f"<pubDate>{pub}</pubDate>")
    parts.append(f"<description><![CDATA[{desc}]]></description>")
    parts.append("</item>")
    return "\n".join(parts)


def _sources_html(sources: list[dict[str, Any]]) -> str:
    lis = []
    for s in (sources or [])[:4]:
        platform = s.get("platform") or "source"
        label = f"{platform} #{s.get('rank')}" if s.get("rank") else str(platform)
        title = str(s.get("title") or "")
        url = s.get("url")
        if url:
            lis.append(
                f'<li>{html.escape(label)}: '
                f'<a href="{html.escape(str(url), quote=True)}">{html.escape(title)}</a></li>'
            )
        else:
            lis.append(f"<li>{html.escape(label)}: {html.escape(title)}</li>")
    return ("<ul>" + "".join(lis) + "</ul>") if lis else ""


def _rfc822(snap: str) -> str:
    try:
        dt = datetime.strptime(snap, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    return format_datetime(dt)
