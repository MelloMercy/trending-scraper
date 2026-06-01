"""Scrape Huxiu (虎嗅) recommended article feed.

Huxiu's web client calls a public JSON endpoint that doesn't require any
signature or login:

    POST https://api-article.huxiu.com/web/article/articleList
    form: platform=www&page=1&pagesize=30

The endpoint returns the curated recommendation feed (most recently
published popular articles). Various sort_type / type / recommend_type
params have no effect — they all return the same feed, so we just take the
first N results from page 1.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from .base import USER_AGENT

API_URL = "https://api-article.huxiu.com/web/article/articleList"


async def scrape_huxiu(limit: int = 30) -> list[dict]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.huxiu.com",
        "Origin": "https://www.huxiu.com",
    }
    data = {"platform": "www", "page": 1, "pagesize": max(limit, 22)}

    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        resp = await client.post(API_URL, data=data)
        resp.raise_for_status()
        payload = resp.json()

    if not payload.get("success"):
        raise RuntimeError(f"Huxiu API error: {payload.get('error') or payload.get('message')}")

    raw_list = payload.get("data", {}).get("dataList", []) or []
    items: list[dict] = []
    for i, row in enumerate(raw_list[:limit]):
        title = row.get("title")
        if not title:
            continue
        aid = row.get("aid")
        url = row.get("share_url") or (f"https://www.huxiu.com/article/{aid}.html" if aid else None)
        items.append(
            {
                "rank": i + 1,
                "title": title,
                "url": url,
                # Use the relative date (e.g. "2 分钟前") as hot_value since
                # there's no public view count in this response
                "hot_value": row.get("formatDate") or "",
                "cover": row.get("pic_path"),
            }
        )
    return items


if __name__ == "__main__":
    items = asyncio.run(scrape_huxiu())
    print(json.dumps(items[:10], ensure_ascii=False, indent=2))
    print(f"Total: {len(items)}")
