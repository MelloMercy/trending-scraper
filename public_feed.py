"""Static public-feed exporter.

This is the follow-builders-inspired boundary: a machine that can run the full
scraper publishes JSON artifacts, while lightweight clients can consume the
already-normalized feed without Playwright, cookies, or local scraping.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import aggregator
import briefer
import db
import summarizer

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
        "brief": briefer.get_cached_brief(snap) if region is None else None,
    }


def write_public_feed(
    platforms: PlatformRegistry,
    labeler: PlatformLabeler,
    out_dir: str | Path = DEFAULT_FEED_DIR,
    snapshot_date: str | None = None,
    region: str | None = None,
) -> dict[str, str]:
    """Write dated and latest feed JSON files, returning their paths."""
    payload = build_public_feed(platforms, labeler, snapshot_date=snapshot_date, region=region)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    suffix = "" if region is None else f"-{region}"
    dated = out / f"{payload['snapshot_date']}{suffix}.json"
    latest = out / f"latest{suffix}.json"
    _write_json(dated, payload)
    _write_json(latest, payload)
    return {
        "snapshot_date": payload["snapshot_date"],
        "dated": str(dated),
        "latest": str(latest),
    }


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
