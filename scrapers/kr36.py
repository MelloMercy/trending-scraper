"""Scrape 36Kr (36氪) hot article list.

36Kr serves its home page through an obfuscated bot-detection script, so
plain HTTP returns no usable HTML. We load https://36kr.com/hot-list/catalog
via Playwright and harvest the rendered article cards.

The page renders multiple categories — we collect the first ~30 visible
article titles in order, which approximates the "24h hot list" view.
"""

from __future__ import annotations

import asyncio
import json

from .base import browser_context

HOT_LIST_URL = "https://36kr.com/hot-list/catalog"


async def scrape_kr36(limit: int = 30) -> list[dict]:
    async with browser_context(headless=True) as ctx:
        page = await ctx.new_page()
        await page.goto(HOT_LIST_URL, wait_until="domcontentloaded", timeout=30_000)
        # 36kr's JS guard takes a moment to resolve and inject content
        try:
            await page.wait_for_selector('a[href*="/p/"]', timeout=20_000)
        except Exception:
            pass
        await asyncio.sleep(2)

        items = await page.evaluate(
            f"""
            (limit) => {{
              const out = [];
              const seen = new Set();
              const anchors = document.querySelectorAll('a[href*="/p/"]');
              for (const a of anchors) {{
                const href = a.href;
                // 36kr article pages: /p/<articleId>
                if (!/\\/p\\/[0-9]+/.test(href)) continue;
                if (seen.has(href)) continue;
                // Find the title node
                const titleEl =
                  a.querySelector('.article-item-title, .title, h3, .kr-flow-article-title') || a;
                let title = (titleEl.innerText || titleEl.textContent || '').trim();
                title = title.split('\\n')[0].trim();
                if (!title || title.length < 8) continue;
                // Reject common nav/footer artefacts
                if (/^(核心服务|关于我们|联系我们|首页|登录|注册|分类|热门)$/.test(title)) continue;
                // Find a view count if visible nearby
                const card = a.closest('.article-item-pic-pc, .hotlist-item-toplist, .hotlist-item, li, div') || a;
                const viewEl = card.querySelector('.kr-flow-bar-views, .views, .item-other-info');
                const views = viewEl ? (viewEl.innerText || '').trim().split('\\n')[0] : '';
                seen.add(href);
                out.push({{
                  rank: out.length + 1,
                  title,
                  url: href,
                  hot_value: views,
                }});
                if (out.length >= limit) break;
              }}
              return out;
            }}
            """,
            limit,
        )
        await page.close()
        return items


if __name__ == "__main__":
    items = asyncio.run(scrape_kr36())
    print(json.dumps(items[:10], ensure_ascii=False, indent=2))
    print(f"Total: {len(items)}")
