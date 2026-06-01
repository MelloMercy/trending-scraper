"""Daily Brief generator.

Synthesizes today's data into 5 sections:
  - consensus  : topics big in BOTH cn and intl
  - cn_only    : big in cn, absent intl
  - intl_only  : big in intl, absent cn
  - persistent : recurring across multiple days
  - emerging   : new today but multi-source coverage
plus a 1-paragraph narrative.

Input sources:
  - today's `summary_cache` rows for cn + intl (LLM-clustered threads)
  - past N days' `summary_cache` rows (for persistence detection)

Uses ONE DeepSeek call per day. Cached in `daily_brief` table.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

import config
import db
from similarity import sim

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_TIMEOUT = 240   # Brief synthesis is more complex than clustering
PERSISTENCE_WINDOW_DAYS = 6  # Look back N days for cross-day matching


# ---------- DB ----------

def init_brief_table() -> None:
    with db.get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_brief (
                snapshot_date TEXT NOT NULL PRIMARY KEY,
                model         TEXT NOT NULL,
                status        TEXT NOT NULL,
                payload       TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                error         TEXT
            );
            """
        )


def _cache_get(snapshot_date: str) -> dict | None:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT model, status, payload, created_at, error FROM daily_brief WHERE snapshot_date = ?",
            (snapshot_date,),
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        try:
            out["payload"] = json.loads(out["payload"])
        except Exception:
            pass
        out["snapshot_date"] = snapshot_date
        return out


def _cache_put(snapshot_date: str, model: str, status: str, payload: dict, error: str | None = None) -> None:
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_brief
                (snapshot_date, model, status, payload, created_at, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_date,
                model,
                status,
                json.dumps(payload, ensure_ascii=False),
                datetime.now().isoformat(timespec="seconds"),
                error,
            ),
        )


# ---------- Data gathering ----------

def _load_threads_for(snapshot_date: str, region: str) -> list[dict]:
    """Return the threads cached for (snapshot_date, region), or []."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT payload, status FROM summary_cache WHERE snapshot_date = ? AND region = ?",
            (snapshot_date, region),
        ).fetchone()
        if not row or row["status"] != "ok":
            return []
        try:
            data = json.loads(row["payload"])
            return data.get("threads", []) or []
        except Exception:
            return []


def _gather_history(snapshot_date: str, days_back: int) -> list[dict]:
    """Past N days' threads (both regions), shaped for the LLM prompt.

    Returns list of {date, region, threads}. Most recent first (excluding today).
    """
    end = datetime.fromisoformat(snapshot_date).date()
    out: list[dict] = []
    for d in range(1, days_back + 1):
        day = (end - timedelta(days=d)).isoformat()
        for region in ("cn", "intl"):
            threads = _load_threads_for(day, region)
            if threads:
                out.append({"date": day, "region": region, "threads": threads})
    return out


def _gather_items_with_urls(snapshot_date: str, region: str) -> dict[int, dict]:
    """Build {item_id -> {platform, title, url, rank}} for today's items in a
    region. item_id matches the IDs used in summary_cache.threads.item_ids."""
    # Lazy import to avoid circular dep
    from main import platforms_for_region
    import aggregator

    platforms = platforms_for_region(region)
    items = aggregator.build_llm_items(snapshot_date, platforms)
    # Also load full DB rows so we have url/cover
    full = {}
    for p in platforms:
        for row in db.get_by_date(p, snapshot_date):
            full[(p, row["title"])] = row
    out: dict[int, dict] = {}
    for it in items:
        full_row = full.get((it["platform"], it["title"]))
        out[it["id"]] = {
            "platform": it["platform"],
            "title": it["title"],
            "rank": (full_row or {}).get("rank", it.get("group_rank", 99)),
            "url": (full_row or {}).get("url"),
        }
    return out


# ---------- Prompt ----------

BRIEF_PROMPT = """You are an editorial analyst producing a Daily Brief from today's clustered news threads. You'll receive:
1. Today's Chinese-platform threads (from 6 sources: Douyin, Xiaohongshu, Bilibili, Zhihu, 36Kr, Huxiu)
2. Today's international threads (from 6 sources: BBC, Hacker News, The Verge, TechCrunch, NYT, Ars Technica)
3. The same data for the past few days (for persistence detection)

Synthesize into 5 sections + 1 narrative. Output STRICT JSON, no markdown.

Output schema:
{{
  "narrative": "1 paragraph (3-5 sentences) summarizing today's overall picture across cn + intl. Write in CHINESE.",

  "consensus": [
    {{
      "title": "话题标题（中文，不超过 12 字）",
      "summary": "一两句话总结（中文）",
      "cn_thread_indexes": [0, 3],    // indexes into today_cn_threads
      "intl_thread_indexes": [1],     // indexes into today_intl_threads
      "cn_item_ids": [12, 47],        // exact Chinese source item IDs supporting this entry
      "intl_item_ids": [8, 19]        // exact international source item IDs supporting this entry
    }}
  ],

  "cn_only": [
    {{
      "title": "话题（中文）",
      "summary": "一句话总结（中文）",
      "cn_thread_indexes": [2],
      "cn_item_ids": [4, 18]
    }}
  ],

  "intl_only": [
    {{
      "title": "Topic name (English, ≤8 words)",
      "summary": "One-sentence summary (English)",
      "intl_thread_indexes": [4],
      "intl_item_ids": [3, 21]
    }}
  ],

  "persistent": [
    {{
      "title": "话题标题（中文或英文，与当前主导地区匹配）",
      "summary": "为什么持续在榜（1-2 句）",
      "days_running": 3,
      "first_seen": "2026-05-10",
      "cn_thread_indexes": [],
      "intl_thread_indexes": [],
      "cn_item_ids": [],
      "intl_item_ids": []
    }}
  ],

  "emerging": [
    {{
      "title": "话题标题",
      "summary": "为什么这是早期信号（1 句）：今日首次出现但已经在多个源",
      "cn_thread_indexes": [],
      "intl_thread_indexes": [],
      "cn_item_ids": [],
      "intl_item_ids": []
    }}
  ]
}}

Critical rules:
- "consensus" = the EXACT SAME news event/topic is meaningfully covered in BOTH regions today.
  ⚠️ STRICT: the cn thread and the intl thread you cite MUST be substantively about the same event. If a topic is significant on one side but no cn (or intl) thread genuinely covers it, do NOT claim consensus — put it in cn_only or intl_only instead. NEVER pad consensus by referencing an unrelated catch-all thread (e.g. citing 「社会民生」for a global-health story just because both touch "society").
  ⚠️ If you can't truthfully name BOTH a cn thread AND an intl thread that talk about the SAME story, that topic isn't consensus.

  CONCRETE ANTI-EXAMPLE (do NOT do this):
  ✗ "title": "Global Health Events",
    "cn_thread_indexes": [社会民生 index],   ← WRONG, that thread is about Chinese society generally, not about the global health event
    "intl_thread_indexes": [Hantavirus & Health index]
  ✓ Correct: Place "Hantavirus / Global Health" in intl_only with intl_thread_indexes only. Empty cn_thread_indexes. Don't claim consensus.
- "cn_only" / "intl_only" = topic is significant in one region AND essentially absent in the other (even checking the past few days).
- "persistent" = topic appears today AND in at least 1 prior day's threads. Estimate days_running and first_seen from history.
- "emerging" = topic appears ONLY today (not in history) but with cross-platform spread (multiple sources mentioned).
- A single thread can be referenced by AT MOST ONE section (prefer consensus > persistent > emerging > region_only).
- Each thread is shown with 2-3 sample headlines underneath ("· …"). Judge each thread by those samples, NOT by its name. A thread named "lifestyle" might actually contain real news; a thread named "Politics" might be mostly memes. Trust the samples.
- A thread is worth including only if its samples show coherent, news-worthy signal. If the samples are diluted miscellany or personal banter with no shared story, omit the thread from sections — even if it has many items.
- For every entry you include, choose the exact `*_item_ids` that directly support that specific entry. Do NOT cite a whole broad thread by taking unrelated items from it.
- If a thread contains multiple unrelated stories, only use the item IDs for the story named in your entry. If you cannot identify exact supporting item IDs, omit that entry.
- Source IDs are shown below as `[id] platform #rank — title`. Return item IDs only from those lists.
- Each section: aim for 2-5 entries. Quality > quantity. If section truly has nothing, return an empty list. Fewer high-quality entries beats forced filler.
- Use thread INDEXES (0-based) from the lists provided, never copy thread names into indexes.

Input data:

== Today's CN threads ({today}) ==
{today_cn_str}

== Today's INTL threads ({today}) ==
{today_intl_str}

== Past {days_back} days threads (for persistence detection) ==
{history_str}
"""


def _load_prompt_file(filename: str, fallback: str) -> str:
    """Read editable prompt files at runtime, falling back to baked-in prompts."""
    path = PROMPTS_DIR / filename
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback
    return text or fallback


def _fmt_threads(
    threads: list[dict],
    items_by_id: dict[int, dict] | None = None,
    max_items_per_thread: int = 14,
) -> str:
    if not threads:
        return "(none)"
    out = []
    for i, t in enumerate(threads):
        name = t.get("name", "?")
        summary = (t.get("summary", "") or "").replace("\n", " ").strip()
        n_items = len(t.get("item_ids", []))
        reps = [str(r).strip() for r in (t.get("representative_titles") or []) if r]
        block = [f"  [{i}] {name} ({n_items} items) — {summary}"]
        for r in reps[:3]:
            block.append(f"      · {r}")
        if items_by_id:
            ids = [item_id for item_id in (t.get("item_ids") or []) if item_id in items_by_id]
            if ids:
                block.append("      Source item IDs:")
                for item_id in ids[:max_items_per_thread]:
                    item = items_by_id[item_id]
                    platform = item.get("platform", "?")
                    rank = item.get("rank", "?")
                    title = item.get("title", "").replace("\n", " ").strip()
                    block.append(f"      [{item_id}] {platform} #{rank} — {title}")
        out.append("\n".join(block))
    return "\n".join(out)


def _fmt_history(history: list[dict]) -> str:
    if not history:
        return "(no prior days)"
    out = []
    for entry in history:
        names = [t.get("name", "?") for t in entry["threads"]]
        out.append(f"  {entry['date']} [{entry['region']}]: " + " | ".join(names))
    return "\n".join(out)


async def _call_deepseek(api_key: str, model: str, prompt: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(API_URL, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"DeepSeek returned non-JSON content: {content[:200]}") from e


# ---------- Enrich (thread index → real items) ----------

def _enrich_section(
    entries: list[dict],
    today_cn_threads: list[dict],
    today_intl_threads: list[dict],
    cn_items_by_id: dict[int, dict],
    intl_items_by_id: dict[int, dict],
) -> list[dict]:
    """Replace thread indexes with rich source-reference data."""
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        cn_refs = _refs_for_entry(
            entry,
            item_key="cn_item_ids",
            thread_key="cn_thread_indexes",
            threads=today_cn_threads,
            items_by_id=cn_items_by_id,
        )
        intl_refs = _refs_for_entry(
            entry,
            item_key="intl_item_ids",
            thread_key="intl_thread_indexes",
            threads=today_intl_threads,
            items_by_id=intl_items_by_id,
        )
        out.append(
            {
                "title": entry.get("title", "—"),
                "summary": entry.get("summary", ""),
                "cn_sources": cn_refs,
                "intl_sources": intl_refs,
                "days_running": entry.get("days_running"),
                "first_seen": entry.get("first_seen"),
            }
        )
    return out


def _refs_for_entry(
    entry: dict,
    item_key: str,
    thread_key: str,
    threads: list[dict],
    items_by_id: dict[int, dict],
    limit: int = 3,
) -> list[dict]:
    """Return source refs that support one brief entry.

    New brief generations return exact item IDs. Older generations only return
    thread indexes, so we fall back to scoring items inside those threads by
    similarity to the entry's title/summary. This avoids the previous behavior
    of blindly taking the first three items from a broad mixed thread.
    """
    refs: list[dict] = []
    seen: set[int] = set()

    allowed_ids = _allowed_item_ids(entry, thread_key, threads)
    explicit_ids = _coerce_int_list(entry.get(item_key))
    for item_id in explicit_ids:
        if item_id in seen:
            continue
        if item_id not in items_by_id:
            continue
        if allowed_ids and item_id not in allowed_ids:
            continue
        refs.append(items_by_id[item_id])
        seen.add(item_id)
        if len(refs) >= limit:
            return refs

    if refs:
        return refs

    candidates = [
        items_by_id[item_id]
        for item_id in allowed_ids
        if item_id in items_by_id
    ]
    if not candidates:
        return []

    query = " ".join(
        str(entry.get(k) or "")
        for k in ("title", "summary")
    ).strip()
    scored = sorted(
        ((_source_score(query, item), item) for item in candidates),
        key=lambda pair: (pair[0], -int(pair[1].get("rank") or 999)),
        reverse=True,
    )
    if not scored:
        return []
    top_score = scored[0][0]
    if top_score < 0.05:
        return [scored[0][1]]
    threshold = max(0.05, top_score * 0.45)
    return [item for score, item in scored if score >= threshold][:limit]


def _allowed_item_ids(entry: dict, thread_key: str, threads: list[dict]) -> set[int]:
    allowed: set[int] = set()
    for idx in _coerce_int_list(entry.get(thread_key)):
        if 0 <= idx < len(threads):
            allowed.update(_coerce_int_list(threads[idx].get("item_ids")))
    return allowed


def _coerce_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _source_score(query: str, item: dict) -> float:
    title = str(item.get("title") or "")
    if not query or not title:
        return 0.0
    score = sim(query, title)
    # Preserve rank as a weak tie-breaker only; semantic match should dominate.
    rank = int(item.get("rank") or 99)
    return score + max(0, 50 - rank) / 10000


# ---------- Public API ----------

def is_enabled() -> bool:
    return bool(config.load().get("deepseek_api_key"))


def get_cached_brief(snapshot_date: str) -> dict | None:
    """Return a cached Daily Brief without making an LLM call."""
    init_brief_table()
    cached = _cache_get(snapshot_date)
    if not cached:
        return None
    payload = cached.get("payload") or {}
    return {
        "status": cached["status"],
        "snapshot_date": snapshot_date,
        "model": cached["model"],
        "created_at": cached["created_at"],
        "error": cached.get("error"),
        **payload,
    }


async def generate_brief(snapshot_date: str | None = None, force: bool = False) -> dict:
    """Generate or fetch cached Daily Brief.

    Returns {
      "status": "ok" | "cached" | "disabled" | "error",
      "snapshot_date": str,
      "model": str | None,
      "narrative": str,
      "consensus": [...], "cn_only": [...], "intl_only": [...],
      "persistent": [...], "emerging": [...],
      "error": str | None,
      "created_at": str
    }
    """
    init_brief_table()
    snapshot_date = snapshot_date or date.today().isoformat()

    # 1. Cache
    if not force:
        cached = _cache_get(snapshot_date)
        if cached:
            payload = cached.get("payload") or {}
            return {
                "status": "cached",
                "snapshot_date": snapshot_date,
                "model": cached["model"],
                "created_at": cached["created_at"],
                "error": cached.get("error"),
                **payload,
            }

    # 2. Config
    api_key = config.load().get("deepseek_api_key")
    if not api_key:
        return {
            "status": "disabled",
            "snapshot_date": snapshot_date,
            "error": "deepseek_api_key not configured.",
        }

    # 3. Gather today's data
    today_cn_threads = _load_threads_for(snapshot_date, "cn")
    today_intl_threads = _load_threads_for(snapshot_date, "intl")

    if not today_cn_threads and not today_intl_threads:
        return {
            "status": "error",
            "snapshot_date": snapshot_date,
            "error": "No threads cached yet for either region. Run scrape + clustering first.",
        }

    # Brief is cross-region by design. Single-region input makes the LLM
    # collapse output into one section (everything → persistent, consensus empty).
    # Don't cache — leave the row absent so a later full run can fill it.
    if not today_cn_threads or not today_intl_threads:
        missing = "cn" if not today_cn_threads else "intl"
        return {
            "status": "skipped",
            "snapshot_date": snapshot_date,
            "error": f"Brief requires both regions; '{missing}' has no threads today. Skipped.",
        }

    history = _gather_history(snapshot_date, PERSISTENCE_WINDOW_DAYS)
    cn_items_by_id = _gather_items_with_urls(snapshot_date, "cn")
    intl_items_by_id = _gather_items_with_urls(snapshot_date, "intl")

    # 4. Build prompt
    prompt = _load_prompt_file("daily-brief.md", BRIEF_PROMPT).format(
        today=snapshot_date,
        days_back=PERSISTENCE_WINDOW_DAYS,
        today_cn_str=_fmt_threads(today_cn_threads, cn_items_by_id),
        today_intl_str=_fmt_threads(today_intl_threads, intl_items_by_id),
        history_str=_fmt_history(history),
    )

    # 5. Call DeepSeek
    try:
        raw = await _call_deepseek(api_key, DEFAULT_MODEL, prompt)
    except Exception as e:
        err = (str(e) or repr(e) or type(e).__name__)[:300]
        existing = _cache_get(snapshot_date)
        if not existing or existing.get("status") != "ok":
            _cache_put(snapshot_date, DEFAULT_MODEL, "error", {}, error=err)
        return {
            "status": "error",
            "snapshot_date": snapshot_date,
            "model": DEFAULT_MODEL,
            "error": err,
        }

    # 6. Enrich indexes → real items
    payload = {
        "narrative": raw.get("narrative", ""),
        "consensus": _enrich_section(
            raw.get("consensus", []), today_cn_threads, today_intl_threads,
            cn_items_by_id, intl_items_by_id
        ),
        "cn_only": _enrich_section(
            raw.get("cn_only", []), today_cn_threads, today_intl_threads,
            cn_items_by_id, intl_items_by_id
        ),
        "intl_only": _enrich_section(
            raw.get("intl_only", []), today_cn_threads, today_intl_threads,
            cn_items_by_id, intl_items_by_id
        ),
        "persistent": _enrich_section(
            raw.get("persistent", []), today_cn_threads, today_intl_threads,
            cn_items_by_id, intl_items_by_id
        ),
        "emerging": _enrich_section(
            raw.get("emerging", []), today_cn_threads, today_intl_threads,
            cn_items_by_id, intl_items_by_id
        ),
    }

    _cache_put(snapshot_date, DEFAULT_MODEL, "ok", payload)
    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "model": DEFAULT_MODEL,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "error": None,
        **payload,
    }


if __name__ == "__main__":
    print(f"enabled: {is_enabled()}")
    result = asyncio.run(generate_brief(force=True))
    print(f"status: {result['status']}")
    if result.get("error"):
        print(f"error: {result['error']}")
    print(f"narrative: {result.get('narrative', '')[:200]}")
    for section in ("consensus", "cn_only", "intl_only", "persistent", "emerging"):
        entries = result.get(section, [])
        print(f"\n{section} ({len(entries)}):")
        for e in entries[:3]:
            print(f"  · {e['title']}: {e['summary'][:80]}")
            if e.get("days_running"):
                print(f"    days_running: {e['days_running']}, first_seen: {e.get('first_seen')}")
            print(f"    cn={len(e.get('cn_sources') or [])}, intl={len(e.get('intl_sources') or [])}")
