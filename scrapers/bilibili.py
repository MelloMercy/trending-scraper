"""Scrape Bilibili popular videos.

Bilibili exposes a stable, unauthenticated JSON API for the "popular" feed:
    https://api.bilibili.com/x/web-interface/popular

This is the fastest and most reliable source we have — pure HTTP, no browser.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from .base import USER_AGENT

POPULAR_URL = "https://api.bilibili.com/x/web-interface/popular"
RANKING_URL = "https://api.bilibili.com/x/web-interface/ranking/v2"


async def _fetch_popular(client: httpx.AsyncClient, page_size: int = 30) -> list[dict]:
    """Currently popular videos — like the 'Popular' tab on the homepage."""
    resp = await client.get(POPULAR_URL, params={"ps": page_size, "pn": 1})
    resp.raise_for_status()
    payload = resp.json()
    items_raw = (payload.get("data") or {}).get("list") or []
    out: list[dict] = []
    for i, v in enumerate(items_raw):
        title = v.get("title")
        bvid = v.get("bvid")
        if not title or not bvid:
            continue
        stat = v.get("stat") or {}
        # Format view count like "123.4万"
        view = stat.get("view") or 0
        hot = _format_count(view) + " 播放"
        out.append(
            {
                "rank": i + 1,
                "title": title,
                "url": f"https://www.bilibili.com/video/{bvid}",
                "hot_value": hot,
                "cover": v.get("pic"),
            }
        )
    return out


def _format_count(n: int) -> str:
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


async def scrape_bilibili() -> list[dict]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
    }
    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
        return await _fetch_popular(client)


if __name__ == "__main__":
    items = asyncio.run(scrape_bilibili())
    print(json.dumps(items[:10], ensure_ascii=False, indent=2))
    print(f"Total: {len(items)}")
