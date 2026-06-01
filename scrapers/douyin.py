"""Scrape Douyin hot search board.

Strategy:
1. Try the public hot-search API endpoint (fast, no JS).
2. Fall back to loading https://www.douyin.com/hot via Playwright and
   parsing the rendered DOM.
"""

from __future__ import annotations

import asyncio
import json
import re

import httpx

from .base import USER_AGENT, browser_context

API_URL = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"
HOT_PAGE_URL = "https://www.douyin.com/hot"


async def _try_api() -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.douyin.com/"}
    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    raw = data.get("word_list") or data.get("data", {}).get("word_list") or []
    items: list[dict] = []
    for i, w in enumerate(raw):
        title = w.get("word") or w.get("title")
        if not title:
            continue
        items.append(
            {
                "rank": i + 1,
                "title": title,
                "url": f"https://www.douyin.com/search/{title}",
                "hot_value": str(w.get("hot_value") or w.get("hotValue") or ""),
                "cover": (w.get("word_cover") or {}).get("url_list", [None])[0],
            }
        )
    return items


async def _try_browser() -> list[dict]:
    async with browser_context(headless=True) as ctx:
        page = await ctx.new_page()
        await page.goto(HOT_PAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        # Allow client-side render
        try:
            await page.wait_for_selector('a[href*="/hot/"]', timeout=15_000)
        except Exception:
            pass
        await asyncio.sleep(2)

        items = await page.evaluate(
            """
            () => {
              const out = [];
              const seen = new Set();
              // Hot list rows usually contain rank + title text
              const candidates = document.querySelectorAll('a, li, div');
              for (const el of candidates) {
                const text = (el.innerText || '').trim();
                if (!text) continue;
                // Match leading rank numbers like "1 标题 1234.5万"
                const m = text.match(/^(\\d{1,2})\\s+([^\\n]{2,80})(?:\\s+([\\d.]+万?))?$/);
                if (!m) continue;
                const rank = parseInt(m[1], 10);
                const title = m[2].trim();
                if (rank < 1 || rank > 50) continue;
                if (seen.has(rank)) continue;
                seen.add(rank);
                let url = null;
                if (el.tagName === 'A' && el.href) url = el.href;
                else {
                  const a = el.querySelector && el.querySelector('a[href]');
                  if (a) url = a.href;
                }
                out.push({ rank, title, url, hot_value: m[3] || '' });
                if (out.length >= 50) break;
              }
              return out.sort((a, b) => a.rank - b.rank);
            }
            """
        )
        await page.close()
        return items


async def scrape_douyin() -> list[dict]:
    """Return ranked Douyin hot search items.

    Each item: {rank, title, url, hot_value, cover?}
    """
    try:
        items = await _try_api()
        if items:
            return items
    except Exception as e:
        print(f"[douyin] API path failed: {e}")

    try:
        return await _try_browser()
    except Exception as e:
        print(f"[douyin] Browser path failed: {e}")
        return []


if __name__ == "__main__":
    items = asyncio.run(scrape_douyin())
    print(json.dumps(items[:10], ensure_ascii=False, indent=2))
    print(f"Total: {len(items)}")
