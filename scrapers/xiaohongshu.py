"""Scrape Xiaohongshu hot content.

Xiaohongshu protects its hot-search board (/board/hot) behind a login wall —
every entry point except /explore redirects to a QR-code login modal.

So we run a **two-mode** strategy:

  1. If data/xhs_cookies.json exists (a logged-in session), we hit
     /board/hot directly and return the *real* hot-search list with heat values.
  2. Otherwise we fall back to /explore and return what's visible there
     — popular notes, not the hot board. This is *not* a true ranking but
     gives the UI something to show out-of-the-box.

The label exposed in `mode` lets the API/UI annotate which one is shown.

To enable mode 1, export your cookies after logging in to xiaohongshu.com:
    data/xhs_cookies.json   # array of Playwright cookies
A template is in data/xhs_cookies.json.example.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .base import browser_context

EXPLORE_URL = "https://www.xiaohongshu.com/explore"
HOT_BOARD_URL = "https://www.xiaohongshu.com/board/hot"
COOKIES_PATH = Path(__file__).resolve().parent.parent / "data" / "xhs_cookies.json"


async def _load_cookies(ctx) -> bool:
    if not COOKIES_PATH.exists():
        return False
    try:
        cookies = json.loads(COOKIES_PATH.read_text())
        await ctx.add_cookies(cookies)
        return True
    except Exception as e:
        print(f"[xhs] Failed to load cookies: {e}")
        return False


async def _scrape_hot_board(page) -> list[dict]:
    """Authenticated path — scrape the real hot-search board."""
    await page.goto(HOT_BOARD_URL, wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(3)

    # If we got bounced to a login modal, abort
    is_locked = await page.evaluate(
        "() => !!document.querySelector('.login-container, [class*=\"login\"][class*=\"modal\"]')"
    )
    if is_locked:
        print("[xhs] Cookies appear expired — got login wall on /board/hot")
        return []

    items = await page.evaluate(
        """
        () => {
          const out = [];
          // The hot-board renders a list of rows; selectors evolve, so we use
          // structural heuristics: look for rank + title + heat number triples.
          const rows = document.querySelectorAll('[class*="hot-item"], [class*="hotItem"], li');
          rows.forEach((row, idx) => {
            const text = (row.innerText || '').trim();
            if (!text) return;
            // Pattern: "1\n标题\n123.4w"
            const lines = text.split(/\\n+/).map(s => s.trim()).filter(Boolean);
            if (lines.length < 2) return;
            const rankMatch = lines[0].match(/^\\d{1,2}$/);
            if (!rankMatch) return;
            const rank = parseInt(lines[0], 10);
            if (rank < 1 || rank > 50) return;
            const title = lines[1];
            const heat = lines[2] || '';
            const link = row.querySelector('a[href]');
            out.push({
              rank,
              title,
              url: link ? link.href : null,
              hot_value: heat,
            });
          });
          // Dedupe by rank, keep first
          const seen = new Set();
          return out.filter(x => {
            if (seen.has(x.rank)) return false;
            seen.add(x.rank);
            return true;
          }).sort((a, b) => a.rank - b.rank);
        }
        """
    )
    return items


async def _scrape_explore(page, limit: int = 40) -> list[dict]:
    """Anonymous path — scrape /explore and return popular notes."""
    await page.goto(EXPLORE_URL, wait_until="domcontentloaded", timeout=30_000)
    try:
        await page.wait_for_selector('a[href*="/explore/"]', timeout=15_000)
    except Exception:
        pass
    await asyncio.sleep(2)
    # Scroll once to load more cards
    await page.evaluate("window.scrollBy(0, 1500)")
    await asyncio.sleep(2)

    items = await page.evaluate(
        f"""
        (limit) => {{
          const out = [];
          const seen = new Set();
          const links = document.querySelectorAll('a[href*="/explore/"]');
          for (const a of links) {{
            const href = a.href;
            if (!/\\/explore\\/[a-z0-9]+/i.test(href)) continue;
            if (seen.has(href)) continue;
            const titleEl = a.querySelector('.title, .footer .title, span') || a;
            let title = (titleEl.innerText || titleEl.textContent || '').trim();
            title = title.split('\\n')[0].trim();
            if (!title || title.length < 2) continue;
            const img = a.querySelector('img');
            const cover = img ? (img.src || img.dataset.src || null) : null;
            const card = a.closest('section, .note-item, li, div') || a;
            const likeEl = card.querySelector('.count, .like-wrapper .count, .interaction span');
            const hot = likeEl ? (likeEl.innerText || '').trim() : '';
            seen.add(href);
            out.push({{
              rank: out.length + 1,
              title,
              url: href,
              hot_value: hot,
              cover,
            }});
            if (out.length >= limit) break;
          }}
          return out;
        }}
        """,
        limit,
    )
    return items


async def scrape_xiaohongshu(limit: int = 30) -> list[dict]:
    """Return a ranked list of XHS trending items.

    Uses /board/hot when logged in (cookies present), /explore otherwise.
    Each item: {rank, title, url, hot_value, cover?}.
    """
    async with browser_context(headless=True) as ctx:
        has_cookies = await _load_cookies(ctx)
        page = await ctx.new_page()
        try:
            if has_cookies:
                items = await _scrape_hot_board(page)
                if items:
                    return items
                print("[xhs] hot_board returned 0 — falling back to /explore")
            return await _scrape_explore(page, limit)
        finally:
            await page.close()


if __name__ == "__main__":
    items = asyncio.run(scrape_xiaohongshu())
    print(json.dumps(items[:10], ensure_ascii=False, indent=2))
    print(f"Total: {len(items)}")
