"""Curated high-signal AI/product/startup feed.

Self-use oriented: keep the high-signal source list in `curated_sources.json`,
consume centrally generated X data from follow-builders, and fetch local RSS
feeds for blogs/newsletters/podcasts.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

from scrapers.base import USER_AGENT
from scrapers.rss_helper import parse_feed

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "curated_sources.json"

FOLLOW_BUILDERS_BASE = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main"
FOLLOW_BUILDERS_FEEDS = {
    "x": f"{FOLLOW_BUILDERS_BASE}/feed-x.json",
    "podcasts": f"{FOLLOW_BUILDERS_BASE}/feed-podcasts.json",
    "blogs": f"{FOLLOW_BUILDERS_BASE}/feed-blogs.json",
}

TIMEOUT = 20
PREVIEW_CHARS = 360
CACHE_TTL_SECONDS = 10 * 60
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, application/json, */*",
}

_CACHE: dict[str, Any] | None = None
_CACHE_AT: datetime | None = None


async def latest(force: bool = False) -> dict[str, Any]:
    """Fetch and normalize the latest curated feeds."""
    global _CACHE, _CACHE_AT

    now = datetime.now(timezone.utc)
    if (
        not force
        and _CACHE is not None
        and _CACHE_AT is not None
        and (now - _CACHE_AT).total_seconds() < CACHE_TTL_SECONDS
    ):
        return _CACHE

    config = _load_sources_config()
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        follow_task = _fetch_follow_builders(client, config, errors)
        local_task = _fetch_local_sources(client, config, errors)
        follow, local = await asyncio.gather(follow_task, local_task)

    builders = follow["builders"]
    podcasts = _dedupe_content([*follow["podcasts"], *local["podcasts"]])[: _limit(config, "podcasts", 24)]
    blogs = _dedupe_content([*follow["blogs"], *local["blogs"]])[: _limit(config, "blogs", 48)]

    payload = {
        "status": "ok" if not errors else "partial",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "name": "follow-builders + local curated_sources",
            "url": "https://github.com/zarazhangrui/follow-builders",
            "config_path": str(SOURCES_PATH),
            "local_sources": len(_enabled_sources(config)),
            "x_generated_at": follow["meta"].get("x_generated_at"),
            "podcasts_generated_at": follow["meta"].get("podcasts_generated_at"),
            "blogs_generated_at": follow["meta"].get("blogs_generated_at"),
        },
        "stats": {
            "sources": len(_enabled_sources(config)),
            "builders": len(builders),
            "tweets": sum(len(row.get("tweets") or []) for row in builders),
            "podcasts": len(podcasts),
            "blogs": len(blogs),
        },
        "builders": builders,
        "podcasts": podcasts,
        "blogs": blogs,
        "errors": errors or None,
    }
    _CACHE = payload
    _CACHE_AT = now
    return payload


def _load_sources_config() -> dict[str, Any]:
    try:
        data = json.loads(SOURCES_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"sources": []}


def _enabled_sources(config: dict[str, Any]) -> list[dict[str, Any]]:
    sources = config.get("sources") or []
    return [s for s in sources if isinstance(s, dict) and s.get("enabled", True)]


def _limit(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return int((config.get("limits") or {}).get(key) or default)
    except (TypeError, ValueError):
        return default


async def _fetch_follow_builders(
    client: httpx.AsyncClient,
    config: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    settings = config.get("follow_builders") or {}
    if settings.get("enabled", True) is False:
        return {"meta": {}, "builders": [], "podcasts": [], "blogs": []}

    raw = await _fetch_json_feeds(client, errors)
    feed_x = raw.get("x") or {}
    feed_podcasts = raw.get("podcasts") or {}
    feed_blogs = raw.get("blogs") or {}
    return {
        "meta": {
            "x_generated_at": feed_x.get("generatedAt"),
            "podcasts_generated_at": feed_podcasts.get("generatedAt"),
            "blogs_generated_at": feed_blogs.get("generatedAt"),
        },
        "builders": _normalize_builders(feed_x) if settings.get("include_x", True) else [],
        "podcasts": _normalize_follow_podcasts(feed_podcasts) if settings.get("include_podcasts", True) else [],
        "blogs": _normalize_follow_blogs(feed_blogs) if settings.get("include_blogs", True) else [],
    }


async def _fetch_json_feeds(client: httpx.AsyncClient, errors: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, url in FOLLOW_BUILDERS_FEEDS.items():
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            out[key] = resp.json()
            feed_errors = out[key].get("errors") or []
            errors.extend(f"follow-builders/{key}: {err}" for err in feed_errors)
        except Exception as e:
            errors.append(f"follow-builders/{key}: {e}")
    return out


async def _fetch_local_sources(
    client: httpx.AsyncClient,
    config: dict[str, Any],
    errors: list[str],
) -> dict[str, list[dict[str, Any]]]:
    semaphore = asyncio.Semaphore(8)
    per_source = _limit(config, "per_source", 5)
    tasks = [
        _fetch_source(client, source, errors, semaphore, per_source)
        for source in _enabled_sources(config)
    ]
    rows = await asyncio.gather(*tasks) if tasks else []
    podcasts: list[dict[str, Any]] = []
    blogs: list[dict[str, Any]] = []
    for source, entries in rows:
        kind = source.get("kind", "blog")
        if kind == "podcast":
            podcasts.extend(_normalize_local_podcasts(source, entries))
        else:
            blogs.extend(_normalize_local_blogs(source, entries))
    return {
        "podcasts": _sort_content(podcasts),
        "blogs": _sort_content(blogs),
    }


async def _fetch_source(
    client: httpx.AsyncClient,
    source: dict[str, Any],
    errors: list[str],
    semaphore: asyncio.Semaphore,
    limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    async with semaphore:
        name = source.get("name") or source.get("id") or "source"
        url = source.get("feed_url") or source.get("url")
        if not url:
            errors.append(f"{name}: missing feed_url")
            return source, []
        try:
            resp = await client.get(str(url))
            resp.raise_for_status()
            return source, parse_feed(resp.text, limit=limit)
        except Exception as e:
            errors.append(f"{name}: {e}")
            return source, []


def _normalize_builders(feed: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for builder in feed.get("x") or []:
        tweets = []
        for tweet in builder.get("tweets") or []:
            text = _clean(tweet.get("text") or "")
            if not text:
                continue
            tweets.append(
                {
                    "id": str(tweet.get("id") or tweet.get("url") or text[:40]),
                    "text": text,
                    "url": tweet.get("url"),
                    "created_at": tweet.get("createdAt"),
                    "likes": tweet.get("likes") or 0,
                    "retweets": tweet.get("retweets") or 0,
                    "replies": tweet.get("replies") or 0,
                    "is_quote": bool(tweet.get("isQuote")),
                }
            )
        if tweets:
            rows.append(
                {
                    "name": builder.get("name") or builder.get("handle") or "Unknown",
                    "handle": builder.get("handle"),
                    "bio": builder.get("bio") or "",
                    "tweets": tweets,
                }
            )
    return rows


def _normalize_follow_podcasts(feed: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in feed.get("podcasts") or []:
        transcript = _clean(item.get("transcript") or "")
        rows.append(
            {
                "name": item.get("name") or "Podcast",
                "title": _clean(item.get("title") or "Untitled"),
                "url": item.get("url"),
                "published_at": item.get("publishedAt"),
                "transcript_preview": _preview(transcript),
                "transcript_length": len(transcript),
                "source_kind": "follow-builders-transcript",
                "category": "ai-podcast",
                "tags": ["ai", "podcast", "transcript"],
                "homepage": None,
            }
        )
    return _sort_content(rows)


def _normalize_follow_blogs(feed: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in feed.get("blogs") or []:
        content = _clean(item.get("content") or item.get("description") or "")
        rows.append(
            {
                "name": item.get("name") or "Blog",
                "title": _clean(item.get("title") or "Untitled"),
                "url": item.get("url"),
                "published_at": item.get("publishedAt"),
                "author": item.get("author") or "",
                "content_preview": _preview(content),
                "content_length": len(content),
                "source_kind": "follow-builders-article",
                "category": "ai-official",
                "tags": ["ai", "official", "article"],
                "homepage": None,
            }
        )
    return _sort_content(rows)


def _normalize_local_podcasts(source: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": source.get("name") or "Podcast",
            "title": _clean(entry.get("title") or "Untitled"),
            "url": entry.get("link"),
            "published_at": entry.get("published") or None,
            "transcript_preview": _preview(_clean(entry.get("summary") or "")),
            "transcript_length": len(_clean(entry.get("summary") or "")),
            "source_kind": "rss",
            "category": source.get("category") or "podcast",
            "tags": _coerce_str_list(source.get("tags")),
            "homepage": source.get("homepage"),
        }
        for entry in entries
        if entry.get("title")
    ]


def _normalize_local_blogs(source: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": source.get("name") or "Blog",
            "title": _clean(entry.get("title") or "Untitled"),
            "url": entry.get("link"),
            "published_at": entry.get("published") or None,
            "author": "",
            "content_preview": _preview(_clean(entry.get("summary") or "")),
            "content_length": len(_clean(entry.get("summary") or "")),
            "source_kind": "rss",
            "category": source.get("category") or "blog",
            "tags": _coerce_str_list(source.get("tags")),
            "homepage": source.get("homepage"),
        }
        for entry in entries
        if entry.get("title")
    ]


def _dedupe_content(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen: set[str] = set()
    for item in _sort_content(items):
        keys = {
            str(item.get("url") or "").strip().lower(),
            f"{item.get('name') or ''}::{item.get('title') or ''}".strip().lower(),
            str(item.get("title") or "").strip().lower(),
        }
        keys.discard("")
        if not keys or keys & seen:
            continue
        seen.update(keys)
        out.append(item)
    return out


def _sort_content(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: _published_ts(item.get("published_at")), reverse=True)


def _published_ts(value: object) -> float:
    if not value:
        return 0.0
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _preview(text: str) -> str:
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[:PREVIEW_CHARS].rstrip() + "..."


def _clean(text: str) -> str:
    return " ".join(str(text or "").replace("&apos;", "'").replace("&amp;", "&").split())


def _coerce_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
