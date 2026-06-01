"""FastAPI backend for the trending scraper.

Run locally:
    uvicorn main:app --reload --port 11001
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import aggregator
import briefer
import config
import curated
import db
import public_feed
import publisher
import summarizer
from scrapers import (
    scrape_ap_news,
    scrape_arstechnica,
    scrape_axios,
    scrape_bbc_world,
    scrape_bilibili,
    scrape_douyin,
    scrape_hackernews,
    scrape_huxiu,
    scrape_kr36,
    scrape_nyt_world,
    scrape_politico,
    scrape_reuters,
    scrape_semafor,
    scrape_techcrunch,
    scrape_theverge,
    scrape_xiaohongshu,
    scrape_zhihu,
)
from scrapers.xiaohongshu import COOKIES_PATH as XHS_COOKIES_PATH

# Each platform: {fn, region, label}.
PLATFORMS: dict[str, dict] = {
    # China
    "douyin":       {"fn": scrape_douyin,       "region": "cn", "label": "抖音热搜"},
    "xiaohongshu":  {"fn": scrape_xiaohongshu,  "region": "cn", "label": "小红书"},  # auto-relabeled if cookies present
    "bilibili":     {"fn": scrape_bilibili,     "region": "cn", "label": "B 站热门"},
    "zhihu":        {"fn": scrape_zhihu,        "region": "cn", "label": "知乎热榜"},
    "kr36":         {"fn": scrape_kr36,         "region": "cn", "label": "36 氪热榜"},
    "huxiu":        {"fn": scrape_huxiu,        "region": "cn", "label": "虎嗅推荐"},
    # International (English-original names per user preference)
    "bbc_world":    {"fn": scrape_bbc_world,    "region": "intl", "label": "BBC World"},
    "hackernews":   {"fn": scrape_hackernews,   "region": "intl", "label": "Hacker News"},
    "theverge":     {"fn": scrape_theverge,     "region": "intl", "label": "The Verge"},
    "techcrunch":   {"fn": scrape_techcrunch,   "region": "intl", "label": "TechCrunch"},
    "nyt_world":    {"fn": scrape_nyt_world,    "region": "intl", "label": "NYT World"},
    "arstechnica":  {"fn": scrape_arstechnica,  "region": "intl", "label": "Ars Technica"},
    # International (Tier-1 expansion: wire + politics)
    "reuters":      {"fn": scrape_reuters,      "region": "intl", "label": "Reuters"},
    "ap_news":      {"fn": scrape_ap_news,      "region": "intl", "label": "AP News"},
    "politico":     {"fn": scrape_politico,     "region": "intl", "label": "Politico"},
    "axios":        {"fn": scrape_axios,        "region": "intl", "label": "Axios"},
    "semafor":      {"fn": scrape_semafor,      "region": "intl", "label": "Semafor"},
}


def platform_meta(pid: str) -> dict:
    meta = dict(PLATFORMS[pid])
    # Special-case label for Xiaohongshu (depends on whether cookies are set)
    if pid == "xiaohongshu":
        meta["label"] = "小红书热搜榜" if XHS_COOKIES_PATH.exists() else "小红书热门笔记"
    # Don't leak the function reference over JSON
    meta.pop("fn", None)
    return meta


def platforms_for_region(region: str) -> list[str]:
    return [pid for pid, m in PLATFORMS.items() if m["region"] == region]


def platform_region(pid: str) -> str:
    return PLATFORMS[pid]["region"]


app = FastAPI(title="每日热点聚合 · 国内 + 国际", version="0.2.0")

STATIC_DIR = Path(__file__).parent / "static"
PROMPTS_DIR = Path(__file__).parent / "prompts"

PROMPT_FILES: dict[str, dict] = {
    "cluster-cn": {
        "filename": "cluster-cn.md",
        "title": "中文话题聚类",
        "description": "控制国内平台标题如何被聚成 5-10 个话题。",
        "placeholders": ["items_str"],
        "refresh_hint": "/api/aggregate/today?region=cn&force_llm=true",
    },
    "cluster-intl": {
        "filename": "cluster-intl.md",
        "title": "International clustering",
        "description": "Controls semantic thread clustering for international sources.",
        "placeholders": ["items_str"],
        "refresh_hint": "/api/aggregate/today?region=intl&force_llm=true",
    },
    "daily-brief": {
        "filename": "daily-brief.md",
        "title": "Daily Brief",
        "description": "控制跨地区 Daily Brief 的叙事、分区和引用规则。",
        "placeholders": ["today", "days_back", "today_cn_str", "today_intl_str", "history_str"],
        "refresh_hint": "/api/brief/today?force=true",
    },
}


def _prompt_spec(prompt_id: str) -> dict:
    spec = PROMPT_FILES.get(prompt_id)
    if not spec:
        raise HTTPException(404, f"Unknown prompt: {prompt_id}")
    return spec


def _prompt_path(prompt_id: str) -> Path:
    spec = _prompt_spec(prompt_id)
    return PROMPTS_DIR / spec["filename"]


def _validate_prompt_content(prompt_id: str, content: str) -> dict:
    spec = _prompt_spec(prompt_id)
    placeholders: list[str] = spec["placeholders"]
    missing = [name for name in placeholders if f"{{{name}}}" not in content]
    format_error = None
    try:
        content.format(**{name: f"<{name}>" for name in placeholders})
    except (KeyError, IndexError, ValueError) as e:
        format_error = str(e)
    return {
        "ok": not missing and format_error is None,
        "missing": missing,
        "format_error": format_error,
    }


def _prompt_payload(prompt_id: str) -> dict:
    spec = _prompt_spec(prompt_id)
    path = _prompt_path(prompt_id)
    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    return {
        "id": prompt_id,
        "filename": spec["filename"],
        "title": spec["title"],
        "description": spec["description"],
        "placeholders": spec["placeholders"],
        "refresh_hint": spec["refresh_hint"],
        "content": content,
        "size": stat.st_size,
        "line_count": len(content.splitlines()),
        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "validation": _validate_prompt_content(prompt_id, content),
    }


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ---- platform list ----

@app.get("/api/platforms")
def list_platforms(region: str | None = None) -> dict:
    out = []
    for pid in PLATFORMS:
        meta = platform_meta(pid)
        if region and meta["region"] != region:
            continue
        out.append({"id": pid, "name": meta["label"], "region": meta["region"]})
    return {"platforms": out}


# ---- per-platform data ----

@app.get("/api/trending/{platform}")
def trending_latest(platform: str) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(404, f"Unknown platform: {platform}")
    items = db.get_latest(platform)
    snapshot_date = items[0]["snapshot_date"] if items else None
    fetched_at = items[0]["fetched_at"] if items else None
    return {
        "platform": platform,
        "region": platform_region(platform),
        "snapshot_date": snapshot_date,
        "fetched_at": fetched_at,
        "count": len(items),
        "items": items,
    }


@app.get("/api/trending/{platform}/history")
def trending_history(platform: str, limit: int = 30) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(404, f"Unknown platform: {platform}")
    return {"platform": platform, "dates": db.get_history_dates(platform, limit)}


@app.get("/api/trending/{platform}/{snapshot_date}")
def trending_by_date(platform: str, snapshot_date: str) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(404, f"Unknown platform: {platform}")
    items = db.get_by_date(platform, snapshot_date)
    return {
        "platform": platform,
        "region": platform_region(platform),
        "snapshot_date": snapshot_date,
        "count": len(items),
        "items": items,
    }


# ---- manual refresh ----

@app.post("/api/refresh/{platform}")
async def refresh(platform: str) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(404, f"Unknown platform: {platform}")
    region = platform_region(platform)
    run_id = db.log_run_start(platform)
    try:
        items = await PLATFORMS[platform]["fn"]()
        count = db.save_items(platform, items, region=region)
        db.log_run_finish(run_id, "ok", item_count=count)
        return {"platform": platform, "region": region, "count": count, "status": "ok"}
    except Exception as e:
        db.log_run_finish(run_id, "error", error=str(e))
        raise HTTPException(500, f"Scrape failed: {e}")


@app.post("/api/refresh")
async def refresh_all(region: str | None = None, cluster: bool = True) -> dict:
    """Refresh all platforms, then regenerate downstream caches.

    Why regenerate: summary_cache.threads[*].item_ids are positional indexes
    into a flat aggregator output. Re-scraping items changes that ordering,
    so old caches map IDs to wrong items (e.g. lifestyle thread showing
    foreign-affairs item). Either invalidate, or regen — regen gives the
    user a consistent view immediately after refresh completes.

    `cluster=false` skips the LLM regen (useful for fast partial-refresh
    flows; caller takes responsibility for staleness).
    """
    targets = platforms_for_region(region) if region else list(PLATFORMS.keys())
    if not targets:
        raise HTTPException(400, f"No platforms for region={region}")
    results = await asyncio.gather(
        *[refresh(p) for p in targets],
        return_exceptions=True,
    )

    # Identify which regions actually got fresh data so we only regen those.
    fresh_regions: set[str] = set()
    for r in results:
        if isinstance(r, dict) and r.get("status") == "ok":
            fresh_regions.add(r["region"])

    cluster_status: dict[str, str] = {}
    if cluster and fresh_regions and summarizer.is_enabled():
        from datetime import date as _date
        snap = _date.today().isoformat()
        for reg in sorted(fresh_regions):
            try:
                items_for_llm = aggregator.build_llm_items(snap, platforms_for_region(reg))
                themes = await summarizer.cluster_themes(snap, items_for_llm, region=reg, force=True)
                cluster_status[reg] = themes.get("status", "unknown")
            except Exception as e:
                cluster_status[reg] = f"error: {e}"

        # Regen brief only if BOTH regions have fresh data this run
        # (brief is cross-region; partial refresh would give incoherent results)
        if {"cn", "intl"}.issubset(fresh_regions):
            try:
                brief = await briefer.generate_brief(force=True)
                cluster_status["brief"] = brief.get("status", "unknown")
            except Exception as e:
                cluster_status["brief"] = f"error: {e}"

    return {
        "region": region or "all",
        "results": [
            r if not isinstance(r, Exception) else {"status": "error", "error": str(r)}
            for r in results
        ],
        "cluster": cluster_status,
    }


# ---- aggregate / themes ----

_GENERIC_THREAD_NAMES = {
    "misc", "miscellany", "其他", "tech miscellany", "tech misc", "杂项", "other",
    "various", "general", "综合", "miscellaneous",
}


def _big_story_from_themes(items_for_llm: list[dict], themes: dict) -> dict | None:
    """Fallback when rule-based aggregator finds no cross-platform consensus.

    Heuristic: pick the LLM thread with highest (unique sources × 10 + item count),
    skipping catch-all "Misc" threads. This naturally favors threads where multiple
    sources covered the same theme — exactly the "Big Story" semantic.

    Returns a synthetic big_story dict in the same shape as aggregator output,
    plus extra fields `source="llm"`, `thread_name`, `thread_summary`.
    """
    threads = (themes or {}).get("threads") or []
    if not threads or not items_for_llm:
        return None

    by_id = {it["id"]: it for it in items_for_llm}

    best = None
    for idx, t in enumerate(threads):
        name_lc = (t.get("name") or "").strip().lower()
        if name_lc in _GENERIC_THREAD_NAMES:
            continue
        item_ids = t.get("item_ids") or []
        items = [by_id[i] for i in item_ids if i in by_id]
        if not items:
            continue
        platforms = sorted({it["platform"] for it in items})
        score = len(platforms) * 10 + len(items)
        if best is None or score > best[0]:
            best = (score, idx, t, items, platforms)

    if not best:
        return None
    _, idx, thread, items, platforms = best
    # Pull full item rows (with url, hot_value) from the DB-backed aggregator items
    # by looking them up via title+platform; items_for_llm has been built from the
    # same agg, so we re-fetch by walking the original groups in aggregator output.
    representative = min(items, key=lambda x: x.get("rank", 99))
    return {
        "rank": 1,
        "n_platforms": len(platforms),
        "platforms": platforms,
        "representative": representative,
        "items": items,
        "source": "llm",
        "thread_idx": idx,
        "thread_name": thread.get("name"),
        "thread_summary": thread.get("summary"),
    }


@app.get("/api/aggregate/today")
async def aggregate_today(date: str | None = None, region: str = "cn", force_llm: bool = False) -> dict:
    """Return cross-platform consensus + LLM threads for a region+date.

    If rule-based aggregator finds no cross-platform consensus (common in intl
    region where English sources don't textually overlap), fall back to picking
    the most-diverse LLM thread as the Big Story.
    """
    from datetime import date as _date
    snap = date or _date.today().isoformat()
    platforms = platforms_for_region(region)
    if not platforms:
        raise HTTPException(400, f"No platforms for region={region}")
    agg = aggregator.aggregate(snap, platforms=platforms)
    items_for_llm = aggregator.build_llm_items(snap, platforms)
    themes = await summarizer.cluster_themes(snap, items_for_llm, region=region, force=force_llm)

    # Big-story fallback when rule-based aggregator found nothing
    if not agg.get("big_story"):
        llm_big_story = _big_story_from_themes(items_for_llm, themes)
        if llm_big_story:
            # Need richer item info than just {id, platform, title} —
            # look up url/hot_value from the aggregator's group items.
            full_by_key = {
                (g_item["platform"], g_item["title"]): g_item
                for g in agg.get("groups", [])
                for g_item in g["items"]
            }
            enriched_items = []
            for it in llm_big_story["items"]:
                full = full_by_key.get((it["platform"], it["title"]))
                enriched_items.append(full if full else it)
            llm_big_story["items"] = enriched_items
            llm_big_story["representative"] = min(
                enriched_items, key=lambda x: x.get("rank", 99)
            )
            agg["big_story"] = llm_big_story

    return {
        "snapshot_date": snap,
        "region": region,
        "aggregate": agg,
        "themes": themes,
        "deepseek_enabled": summarizer.is_enabled(),
    }


# ---- daily brief ----

@app.get("/api/brief/today")
async def brief_today(force: bool = False) -> dict:
    """Generate or fetch cached Daily Brief for today."""
    return await briefer.generate_brief(force=force)


@app.get("/api/brief/{snapshot_date}")
async def brief_for_date(snapshot_date: str, force: bool = False) -> dict:
    """Generate or fetch Daily Brief for a specific date."""
    return await briefer.generate_brief(snapshot_date=snapshot_date, force=force)


# ---- curated high-signal feed ----

@app.get("/api/curated/latest")
async def curated_latest(force: bool = False) -> dict:
    """Return curated AI/product/startup sources for self-use."""
    return await curated.latest(force=force)


@app.get("/api/feed/latest")
def feed_latest(date: str | None = None, region: str | None = None) -> dict:
    """Return the static-feed payload without running scrapers or LLM calls."""
    if region is not None and region not in {"cn", "intl"}:
        raise HTTPException(400, "region must be cn or intl")
    return public_feed.build_public_feed(PLATFORMS, platform_meta, snapshot_date=date, region=region)


@app.get("/api/publish/latest")
def publish_latest(date: str | None = None, feed_url: str | None = None) -> dict:
    """Return WeChat/manual-delivery digest content without writing files."""
    return publisher.build_daily_digest(PLATFORMS, platform_meta, snapshot_date=date, feed_url=feed_url)


# ---- prompt files ----

@app.get("/api/prompts")
def list_prompts() -> dict:
    """Return editable LLM prompt files.

    Only known files are exposed. This keeps the local editor useful without
    turning it into a general filesystem API.
    """
    return {"prompts": [_prompt_payload(prompt_id) for prompt_id in PROMPT_FILES]}


@app.get("/api/prompts/{prompt_id}")
def get_prompt(prompt_id: str) -> dict:
    return {"prompt": _prompt_payload(prompt_id)}


@app.post("/api/prompts/{prompt_id}")
def update_prompt(prompt_id: str, payload: dict = Body(...)) -> dict:
    _prompt_spec(prompt_id)
    content = payload.get("content")
    if not isinstance(content, str):
        raise HTTPException(400, "content must be a string")

    normalized = content.rstrip() + "\n"
    validation = _validate_prompt_content(prompt_id, normalized)
    if not validation["ok"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Prompt validation failed. Keep required placeholders and escape literal JSON braces as {{ and }}.",
                "validation": validation,
            },
        )

    path = _prompt_path(prompt_id)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(normalized, encoding="utf-8")
    tmp_path.replace(path)
    return {"prompt": _prompt_payload(prompt_id), "updated": True}


# ---- runs / config ----

@app.get("/api/runs")
def recent_runs(limit: int = 20) -> dict:
    return {"runs": db.get_recent_runs(limit)}


@app.get("/api/config")
def get_config() -> dict:
    return {
        "config": config.public_view(),
        "schema": config.SCHEMA,
    }


@app.post("/api/config")
def update_config(updates: dict = Body(...)) -> dict:
    cleaned = {k: v for k, v in updates.items() if k in config.SCHEMA}
    if not cleaned:
        raise HTTPException(400, "No valid config fields supplied.")
    config.save(cleaned)
    return {"config": config.public_view(), "updated": list(cleaned.keys())}


# ---- static frontend ----

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
