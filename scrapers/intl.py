"""International news scrapers — 11 sources, all RSS / public API.

| platform_id     | source        | mechanism                         |
| --------------- | ------------- | --------------------------------- |
| bbc_world       | BBC World     | RSS                               |
| hackernews      | Hacker News   | Algolia public API                |
| theverge        | The Verge     | RSS (Atom)                        |
| techcrunch      | TechCrunch    | RSS                               |
| nyt_world       | NYT World     | RSS                               |
| arstechnica     | Ars Technica  | RSS                               |
| reuters         | Reuters       | Google News RSS (official RIP'd)  |
| ap_news         | AP News       | Google News RSS                   |
| politico        | Politico      | RSS (politics-news.xml)           |
| axios           | Axios         | RSS                               |
| semafor         | Semafor       | Google News RSS                   |

All run via httpx (no Playwright). Each scraper returns the standard
trending-item shape: {rank, title, url, hot_value, cover?}.
"""

from __future__ import annotations

import asyncio
import json
import re

import httpx

from .base import USER_AGENT
from .rss_helper import fetch_feed, to_trending_items


# ---------------------- BBC World ----------------------

BBC_FEED_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"


async def scrape_bbc_world(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(BBC_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- Hacker News ----------------------

HN_API = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={n}"


async def scrape_hackernews(limit: int = 30) -> list[dict]:
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(HN_API.format(n=limit))
        resp.raise_for_status()
        data = resp.json()
    hits = data.get("hits", [])
    items: list[dict] = []
    for i, hit in enumerate(hits[:limit]):
        title = hit.get("title") or hit.get("story_title")
        if not title:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        points = hit.get("points") or 0
        comments = hit.get("num_comments") or 0
        items.append(
            {
                "rank": i + 1,
                "title": title,
                "url": url,
                "hot_value": f"{points} pts · {comments} comments",
                "cover": None,
            }
        )
    return items


# ---------------------- The Verge ----------------------

VERGE_FEED_URL = "https://www.theverge.com/rss/index.xml"


async def scrape_theverge(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(VERGE_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- TechCrunch ----------------------

TECHCRUNCH_FEED_URL = "https://techcrunch.com/feed/"


async def scrape_techcrunch(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(TECHCRUNCH_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- NYT World ----------------------

NYT_WORLD_FEED_URL = "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"


async def scrape_nyt_world(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(NYT_WORLD_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- Ars Technica ----------------------

ARS_FEED_URL = "https://feeds.arstechnica.com/arstechnica/index"


async def scrape_arstechnica(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(ARS_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- Politico ----------------------

POLITICO_FEED_URL = "https://rss.politico.com/politics-news.xml"


async def scrape_politico(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(POLITICO_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- Axios ----------------------

AXIOS_FEED_URL = "https://api.axios.com/feed/"


async def scrape_axios(limit: int = 30) -> list[dict]:
    entries = await fetch_feed(AXIOS_FEED_URL, limit=limit)
    return to_trending_items(entries)


# ---------------------- Google News RSS helpers (Reuters / AP / Semafor) ----------------------
#
# Reuters killed its official RSS in 2020. AP / Semafor lack stable feeds.
# Google News RSS gives us a workable proxy: `site:<domain>` query, returns
# ~100 most recent articles from that domain.
#
# Caveats:
#   - Titles arrive as "Real Title - Source Name" — we strip the trailing
#     " - <source>" suffix for consistency with other scrapers.
#   - Links are Google News redirects, not the original URLs. Browser will
#     follow them on click; that's fine for our purposes.

_GNEWS_BASE = "https://news.google.com/rss/search"


def _gnews_url(site: str) -> str:
    return f"{_GNEWS_BASE}?q=site:{site}&hl=en-US&gl=US&ceid=US:en"


def _strip_gnews_suffix(title: str, source_label: str) -> str:
    """Strip ' - Reuters' / ' - The Associated Press' etc. from Google News titles."""
    if not title:
        return title
    # Common: "Headline - Reuters" or "Headline - AP News" or "Headline - Semafor"
    pattern = rf"\s+-\s+{re.escape(source_label)}\s*$"
    return re.sub(pattern, "", title).strip()


async def _scrape_via_gnews(site: str, source_label: str, limit: int) -> list[dict]:
    entries = await fetch_feed(_gnews_url(site), limit=limit)
    items = to_trending_items(entries)
    for it in items:
        it["title"] = _strip_gnews_suffix(it["title"], source_label)
    # Filter out empty titles after stripping (rare edge case)
    return [it for it in items if it.get("title")]


# ---------------------- Reuters ----------------------

async def scrape_reuters(limit: int = 30) -> list[dict]:
    return await _scrape_via_gnews("reuters.com", "Reuters", limit)


# ---------------------- AP News ----------------------

async def scrape_ap_news(limit: int = 30) -> list[dict]:
    return await _scrape_via_gnews("apnews.com", "AP News", limit)


# ---------------------- Semafor ----------------------

async def scrape_semafor(limit: int = 30) -> list[dict]:
    return await _scrape_via_gnews("semafor.com", "Semafor", limit)


# ---------------------- Self-test ----------------------

if __name__ == "__main__":
    async def go():
        scrapers = [
            ("BBC World", scrape_bbc_world),
            ("Hacker News", scrape_hackernews),
            ("The Verge", scrape_theverge),
            ("TechCrunch", scrape_techcrunch),
            ("NYT World", scrape_nyt_world),
            ("Ars Technica", scrape_arstechnica),
            ("Reuters", scrape_reuters),
            ("AP News", scrape_ap_news),
            ("Politico", scrape_politico),
            ("Axios", scrape_axios),
            ("Semafor", scrape_semafor),
        ]
        for name, fn in scrapers:
            try:
                items = await fn(limit=5)
                print(f"\n=== {name} ({len(items)} items) ===")
                for it in items[:3]:
                    print(f"  {it['rank']:>2}. {it['title'][:70]}")
                    if it.get('hot_value'):
                        print(f"      🔥 {it['hot_value'][:50]}")
            except Exception as e:
                print(f"\n=== {name} FAILED: {e} ===")

    asyncio.run(go())
