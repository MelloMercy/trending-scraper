from .bilibili import scrape_bilibili
from .douyin import scrape_douyin
from .huxiu import scrape_huxiu
from .intl import (
    scrape_ap_news,
    scrape_arstechnica,
    scrape_axios,
    scrape_bbc_world,
    scrape_hackernews,
    scrape_nyt_world,
    scrape_politico,
    scrape_reuters,
    scrape_semafor,
    scrape_techcrunch,
    scrape_theverge,
)
from .kr36 import scrape_kr36
from .xiaohongshu import scrape_xiaohongshu
from .zhihu import scrape_zhihu

__all__ = [
    # cn
    "scrape_douyin",
    "scrape_xiaohongshu",
    "scrape_bilibili",
    "scrape_zhihu",
    "scrape_kr36",
    "scrape_huxiu",
    # intl (original 6)
    "scrape_bbc_world",
    "scrape_hackernews",
    "scrape_theverge",
    "scrape_techcrunch",
    "scrape_nyt_world",
    "scrape_arstechnica",
    # intl (Tier-1 expansion: wire services + politics)
    "scrape_reuters",
    "scrape_ap_news",
    "scrape_politico",
    "scrape_axios",
    "scrape_semafor",
]
