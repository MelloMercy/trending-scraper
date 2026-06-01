"""DeepSeek-powered semantic clustering of daily trending items.

Sends all of today's titles to DeepSeek and asks it to group them into 5-10
thematic clusters ("threads"), each with a short title and a one-sentence
summary. Results are cached per (snapshot_date, region) in `summary_cache`.

Designed to degrade gracefully:
  - If `deepseek_api_key` isn't configured, `cluster_themes()` returns
    {"status": "disabled", ...} immediately, no network calls.
  - If the API call fails, returns {"status": "error", "error": "..."}
    and never throws.

DeepSeek's API is OpenAI-compatible. We default to `deepseek-v4-flash`
(V4 generation, cheaper than pro, plenty for our clustering task — input
$0.14 / 1M tokens, output $0.28 / 1M tokens, well under $0.001 per day).

The older `deepseek-chat` model name is being deprecated. Override via
the `DEEPSEEK_MODEL` env var if you want `deepseek-v4-pro` instead.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import httpx

import config
import db

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_TIMEOUT = 180  # V4 with reasoning can take 1-2 minutes on 100+ items
MAX_ITEMS_FOR_LLM = 100  # trim to top-N by aggregator rank to bound cost & latency


# ---------- Cache table ----------

def init_cache_table() -> None:
    with db.get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS summary_cache (
                snapshot_date TEXT NOT NULL,
                region        TEXT NOT NULL,
                model         TEXT NOT NULL,
                status        TEXT NOT NULL,
                payload       TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                error         TEXT,
                PRIMARY KEY (snapshot_date, region)
            );
            """
        )


def _cache_get(snapshot_date: str, region: str) -> dict | None:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT model, status, payload, created_at, error FROM summary_cache WHERE snapshot_date = ? AND region = ?",
            (snapshot_date, region),
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        try:
            out["payload"] = json.loads(out["payload"])
        except Exception:
            pass
        out["snapshot_date"] = snapshot_date
        out["region"] = region
        return out


def _cache_put(snapshot_date: str, region: str, model: str, status: str, payload: dict, error: str | None = None) -> None:
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO summary_cache
                (snapshot_date, region, model, status, payload, created_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_date,
                region,
                model,
                status,
                json.dumps(payload, ensure_ascii=False),
                datetime.now().isoformat(timespec="seconds"),
                error,
            ),
        )


# ---------- Prompts ----------

PROMPT_TEMPLATE_CN = """你是一个中文新闻聚合编辑。下面是今日来自多个中文平台（抖音、小红书、B站、知乎、36氪、虎嗅）的热点标题列表。

请把语义相关的标题聚成 5-10 个「话题」(thread)。

**关键：在生成最终聚类前，先做内部推理（你的 reasoning 过程会自动进行，不必输出）**：

第一步 · 初步聚类
按你最自然的语义判断对所有标题分组。

第二步 · 自我批评（CRITICAL — 这是质量的关键）
对每个 thread 内部逐条检查：
- 这条标题真的属于这个 thread 的**核心语义主题**吗？还是只是「字面词汇匹配」？
- 标题的「字面含义」≠ 「实际语境」。同样一个词在不同平台 / 不同语气下，意思可能完全不同。例如：
  - 含品牌名的标题，可能是消费者吐槽段子（lifestyle / 个人感受），也可能是商业新闻——**取决于语气而非词汇**
  - 「创始人」「公司」等词出现在口语化、反讽、玩梗的标题里，本质是文娱内容，不是商业新闻
  - 「外交部」「政府」「政策」类词汇通常是社会 / 政治议题，**不应**因为提及产业被归入商业
  - 像「嚯！」「就是你小子」「不要太...」「！！！」「~」「呜呜」「真的」这种语气词 / 表情，强烈指向个人分享 / 段子，不是新闻
- 如果你发现某条标题「字面像 thread A 但语境其实是 thread B」，**移到 B**。
- 如果某条标题难以归入任何核心 thread，可以创建一个更合适的 thread，或归到「其他」（但避免滥用「其他」）。

第三步 · 输出最终聚类
应用所有修正后，输出最终结果。

每个 thread 字段：
- name: 不超过 10 字的简短主题名
- summary: 1-2 句话总结
- representative_titles: 从该 thread 里挑 2-3 条最能反映 thread **主导内容**的标题，**逐字引用原始标题**（不要改写、不要翻译）。这是给下游用来判断 thread 真实性质的样本——thread 主要是新闻就挑新闻标题，主要是个人日常就挑日常标题，如实反映即可
- item_ids: 归入的标题 id 数组（**此字段只填 id 数字**，原始标题通过 representative_titles 展示）

输出严格的 JSON：
{{"threads": [
  {{"name": "话题名", "summary": "总结", "representative_titles": ["原始标题1", "原始标题2", "原始标题3"], "item_ids": [12, 47, 88]}},
  ...
]}}

不要输出 JSON 之外的解释。

今日标题列表（id: 平台 - 标题）：
{items_str}
"""

PROMPT_TEMPLATE_INTL = """You are an English-language news aggregator editor. Below is a list of today's headlines from multiple international sources (BBC World, Hacker News, The Verge, TechCrunch, NYT World, Ars Technica, Reuters, AP News, Politico, Axios, Semafor).

Cluster semantically-related headlines into 5-10 "threads".

**Important: before producing final clusters, do internal reasoning (your reasoning chain runs automatically, no need to output it)**:

Step 1 · Initial clustering
Group headlines by your most natural semantic judgment.

Step 2 · Self-critique (CRITICAL — this drives quality)
For each thread, review every item:
- Does this item truly belong to this thread's **core semantic topic**, or is it just "surface keyword match"?
- "Surface words" ≠ "actual context". The same word can mean very different things across sources / tones. For example:
  - A headline mentioning a brand name might be consumer commentary / opinion piece (lifestyle / personal voice), or actual business news — **depends on tone, not vocabulary**
  - Words like "founder", "CEO", "company" appearing in colloquial / sarcastic / meme-style headlines are entertainment, not business news
  - Words like "foreign ministry", "government", "policy" usually mean political / social topics; **do not** move them to business just because industry is mentioned
  - Exclamation marks, question marks, emoji, casual phrasing, "you know?", "really?" indicate personal opinion / banter, not news
- If you find an item that "looks like thread A by words but actually fits thread B by context", **move it to B**.
- Items that don't fit any core thread should either form a new appropriate thread, or go in an "Other" bucket (but use sparingly).

Step 3 · Output final clusters
After applying all corrections, output the final result.

Each thread:
- name: short title, no more than 6 words
- summary: 1-2 sentences
- representative_titles: 2-3 headlines from this thread that best reflect its **dominant content**, quoted **verbatim** (no rewriting, no translation). Downstream consumers use these as samples to judge what the thread really contains — if it's mostly real news, pick news headlines; if mostly personal/opinion/lifestyle, pick those. Be honest about the mix.
- item_ids: array of headline ids belonging to this thread (**this field is ids only**; the actual headlines are shown via representative_titles)

Output strict JSON:
{{"threads": [
  {{"name": "Thread title", "summary": "1-2 sentence summary.", "representative_titles": ["headline 1", "headline 2", "headline 3"], "item_ids": [12, 47, 88]}},
  ...
]}}

Do not output any text outside the JSON.

Today's headlines (id: source - title):
{items_str}
"""


def _load_prompt_file(filename: str, fallback: str) -> str:
    """Read editable prompt files at runtime, falling back to baked-in prompts."""
    path = PROMPTS_DIR / filename
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback
    return text or fallback


def _pick_prompt(region: str) -> str:
    if region == "intl":
        return _load_prompt_file("cluster-intl.md", PROMPT_TEMPLATE_INTL)
    return _load_prompt_file("cluster-cn.md", PROMPT_TEMPLATE_CN)


# ---------- LLM call ----------

async def _call_deepseek(api_key: str, model: str, items: list[dict], region: str) -> dict:
    items_str = "\n".join(f"{it['id']}: {it['platform']} - {it['title']}" for it in items)
    prompt = _pick_prompt(region).format(items_str=items_str)

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


# ---------- Public API ----------

def is_enabled() -> bool:
    cfg = config.load()
    return bool(cfg.get("deepseek_api_key"))


def get_cached_themes(snapshot_date: str, region: str) -> dict | None:
    """Return cached thread clusters without making an LLM call."""
    init_cache_table()
    cached = _cache_get(snapshot_date, region)
    if not cached:
        return None
    return {
        "status": cached["status"],
        "model": cached["model"],
        "region": region,
        "threads": (cached["payload"] or {}).get("threads", []),
        "created_at": cached["created_at"],
        "error": cached.get("error"),
    }


async def cluster_themes(snapshot_date: str, items: list[dict], region: str = "cn", force: bool = False) -> dict:
    """Cluster items into themes using DeepSeek.

    Cached per (snapshot_date, region). Returns:
        {
          "status": "ok" | "disabled" | "error" | "cached",
          "model": str | None,
          "region": str,
          "threads": [{"name", "summary", "item_ids": [...]}],
          "error": str | None,
        }
    """
    init_cache_table()

    # 1. Cache check
    if not force:
        cached = _cache_get(snapshot_date, region)
        if cached:
            return {
                "status": "cached",
                "model": cached["model"],
                "region": region,
                "threads": (cached["payload"] or {}).get("threads", []),
                "created_at": cached["created_at"],
                "error": cached.get("error"),
            }

    # 2. Config check
    cfg = config.load()
    api_key = cfg.get("deepseek_api_key")
    if not api_key:
        return {
            "status": "disabled",
            "model": None,
            "region": region,
            "threads": [],
            "error": "deepseek_api_key not configured. POST it to /api/config to enable.",
        }

    # 3. Trim items so we don't blow timeouts on huge inputs
    if len(items) > MAX_ITEMS_FOR_LLM:
        items = items[:MAX_ITEMS_FOR_LLM]

    # 4. Call DeepSeek
    try:
        result = await _call_deepseek(api_key, DEFAULT_MODEL, items, region)
        threads = result.get("threads", []) if isinstance(result, dict) else []
        _cache_put(snapshot_date, region, DEFAULT_MODEL, "ok", {"threads": threads})
        return {
            "status": "ok",
            "model": DEFAULT_MODEL,
            "region": region,
            "threads": threads,
            "error": None,
        }
    except Exception as e:
        # Some exceptions (httpx.ReadTimeout) have empty str(); use type+repr.
        err = (str(e) or repr(e) or type(e).__name__)[:300]
        _cache_put(snapshot_date, region, DEFAULT_MODEL, "error", {"threads": []}, error=err)
        return {
            "status": "error",
            "model": DEFAULT_MODEL,
            "region": region,
            "threads": [],
            "error": err,
        }


if __name__ == "__main__":
    from datetime import date
    snap = date.today().isoformat()
    for region, platforms in [
        ("cn", ["douyin", "xiaohongshu", "bilibili", "zhihu", "kr36", "huxiu"]),
        ("intl", ["bbc_world", "hackernews", "theverge", "techcrunch", "nyt_world", "arstechnica"]),
    ]:
        items = []
        for p in platforms:
            for row in db.get_by_date(p, snap):
                items.append({"id": len(items), "platform": p, "title": row["title"]})
        print(f"\n=== region={region}, items={len(items)}, enabled={is_enabled()} ===")
        result = asyncio.run(cluster_themes(snap, items, region=region))
        print(f"status: {result['status']}")
        if result.get("error"):
            print(f"error: {result['error']}")
        for t in result.get("threads", []):
            print(f"  · {t['name']}: {t['summary'][:70]}  ({len(t['item_ids'])} items)")
