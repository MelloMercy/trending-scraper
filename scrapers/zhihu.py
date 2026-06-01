"""Scrape Zhihu hot list (知乎热榜).

Zhihu exposes a JSON API for the hot list. It usually works without login but
some endpoints rate-limit; we add a polite User-Agent and Referer.

Strategy:
1. Try the public hot-list API.
2. Fall back to Playwright loading https://www.zhihu.com/hot if needed.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from .base import USER_AGENT, browser_context

# The web hot-list API now requires login. The mobile API is still open and
# returns the same data set.
API_URL = "https://api.zhihu.com/topstory/hot-lists/total"
HOT_PAGE_URL = "https://www.zhihu.com/hot"


async def _try_api() -> list[dict]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.zhihu.com/",
        "Accept": "application/json",
    }
    params = {"limit": 50, "reverse_order": 0}
    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
        resp = await client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    raw = data.get("data") or []
    items: list[dict] = []
    for i, w in enumerate(raw):
        target = w.get("target") or {}
        title = target.get("title") or (w.get("card_label") or {}).get("text")
        if not title:
            continue
        qid = target.get("id")
        url = f"https://www.zhihu.com/question/{qid}" if qid else None
        children = w.get("children") or []
        cover = children[0].get("thumbnail") if children else None
        items.append(
            {
                "rank": i + 1,
                "title": title,
                "url": url,
                "hot_value": (w.get("detail_text") or "").strip(),
                "cover": cover,
            }
        )
    return items


async def _try_browser() -> list[dict]:
    async with browser_context(headless=True) as ctx:
        page = await ctx.new_page()
        await page.goto(HOT_PAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_selector(".HotItem", timeout=15_000)
        except Exception:
            pass
        await asyncio.sleep(1)
        items = await page.evaluate(
            """
            () => {
              const out = [];
              const cards = document.querySelectorAll('.HotItem');
              cards.forEach((card, i) => {
                const titleEl = card.querySelector('.HotItem-title');
                const linkEl = card.querySelector('a');
                const metricEl = card.querySelector('.HotItem-metrics');
                if (!titleEl) return;
                out.push({
                  rank: i + 1,
                  title: titleEl.innerText.trim(),
                  url: linkEl ? linkEl.href : null,
                  hot_value: metricEl ? metricEl.innerText.replace(/\\s+/g, ' ').trim() : '',
                });
              });
              return out;
            }
            """
        )
        await page.close()
        return items


async def scrape_zhihu() -> list[dict]:
    try:
        items = await _try_api()
        if items:
            return items
    except Exception as e:
        print(f"[zhihu] API path failed: {e}")

    try:
        return await _try_browser()
    except Exception as e:
        print(f"[zhihu] Browser path failed: {e}")
        return []


if __name__ == "__main__":
    items = asyncio.run(scrape_zhihu())
    print(json.dumps(items[:10], ensure_ascii=False, indent=2))
    print(f"Total: {len(items)}")
