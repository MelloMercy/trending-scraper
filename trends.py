"""Cross-day persistence trends — the time dimension of the archive.

Most aggregators only show "today". This module exploits the daily snapshots:
it clusters items across a multi-day window (same char-bigram Jaccard similarity
as the same-day aggregator) to surface topics that *persist* across days and
platforms, with a per-day timeline and a rising/steady/falling trajectory.

No LLM involved — deterministic and fast. The clustering core
(`cluster_trends`) is pure and DB-free so it can be unit-tested directly;
`compute_trends` is the DB-backed wrapper used by the API and the feed export.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import db
from aggregator import UnionFind
from similarity import char_bigrams, jaccard

PERSIST_THRESHOLD = 0.42       # a touch stricter than same-day (0.40): cross-day rewording
DEFAULT_DAYS_BACK = 7
PER_PLATFORM_DAY_CAP = 30      # bound the pool so pairwise clustering stays fast


def cluster_trends(
    items: list[dict[str, Any]],
    dates: list[str],
    *,
    min_days: int = 2,
    min_platforms: int = 2,
    threshold: float = PERSIST_THRESHOLD,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Cluster items across the window and return persistent topics, sorted.

    Each item needs: title, snapshot_date, platform, rank (optional url). A topic
    qualifies when it spans at least ``min_days`` distinct days AND ``min_platforms``
    distinct platforms — the latter filters out single-source "sticky" pages
    (e.g. a column that sits on one site for a week) in favor of genuine
    cross-platform persistence. Pure function: no DB, no network.
    """
    items = [it for it in items if (it.get("title") or "").strip()]
    n = len(items)
    if not items:
        return []

    bigrams = [char_bigrams(it["title"]) for it in items]
    # Inverted index over bigrams: only compare items that share at least one
    # bigram. This is exact (a pair with zero shared bigrams can't reach the
    # threshold) and skips the huge cross-language / cross-topic majority.
    inverted: dict[str, list[int]] = defaultdict(list)
    for i, bg in enumerate(bigrams):
        for g in bg:
            inverted[g].append(i)
    # Skip ultra-common bigrams when generating candidates: they aren't
    # discriminative, and any pair similar enough to merge (>=threshold) shares
    # rarer bigrams too. This bounds candidate-set size and keeps clustering fast.
    df_cap = max(50, n // 40)
    uf = UnionFind(n)
    for i in range(n):
        candidates: set[int] = set()
        for g in bigrams[i]:
            bucket = inverted[g]
            if len(bucket) > df_cap:
                continue
            for j in bucket:
                if j > i:
                    candidates.add(j)
        for j in candidates:
            if jaccard(bigrams[i], bigrams[j]) >= threshold:
                uf.union(i, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[uf.find(i)].append(i)

    dates_asc = sorted(dates)
    trends: list[dict[str, Any]] = []
    for idx_list in clusters.values():
        members = [items[i] for i in idx_list]
        by_date: dict[str, list[dict]] = defaultdict(list)
        for it in members:
            by_date[str(it.get("snapshot_date"))].append(it)
        if len(by_date) < min_days:
            continue
        if len({m["platform"] for m in members}) < min_platforms:
            continue
        trends.append(_summarize_cluster(members, by_date, dates_asc))

    trends.sort(key=lambda t: t["score"], reverse=True)
    return trends[:limit]


def _summarize_cluster(members, by_date, dates_asc) -> dict[str, Any]:
    timeline = []
    for d in sorted(by_date):
        day_items = by_date[d]
        plats = sorted({x["platform"] for x in day_items})
        best = min((x.get("rank") or 99) for x in day_items)
        timeline.append({"date": d, "platforms": plats, "best_rank": best, "count": len(day_items)})

    present = {t["date"] for t in timeline}
    streak = run = 0
    for d in dates_asc:
        run = run + 1 if d in present else 0
        streak = max(streak, run)

    platforms = sorted({x["platform"] for x in members})
    rep = min(members, key=lambda x: (x.get("rank") or 99))
    rank_bonus = sum(max(0, 50 - t["best_rank"]) for t in timeline)
    # Cross-platform breadth weighs most, then how many days, then streak.
    score = len(platforms) * 100 + len(timeline) * 60 + streak * 20 + rank_bonus

    return {
        "title": rep.get("title"),
        "url": rep.get("url"),
        "platforms": platforms,
        "platform_count": len(platforms),
        "days": [t["date"] for t in timeline],
        "day_count": len(timeline),
        "streak": streak,
        "first_seen": timeline[0]["date"],
        "last_seen": timeline[-1]["date"],
        "peak_rank": min(t["best_rank"] for t in timeline),
        "trajectory": _trajectory(timeline),
        "score": score,
        "timeline": timeline,
    }


def _trajectory(timeline: list[dict]) -> str:
    """rising / falling / steady, from first vs last active-day presence."""
    if len(timeline) < 2:
        return "new"
    def presence(t: dict) -> float:
        return len(t["platforms"]) * 10 + max(0, 50 - t["best_rank"])
    first, last = presence(timeline[0]), presence(timeline[-1])
    if last > first * 1.15:
        return "rising"
    if last < first * 0.85:
        return "falling"
    return "steady"


def _gather(dates: list[str], platforms: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for d in dates:
        for p in platforms:
            rows = db.get_by_date(p, d)[:PER_PLATFORM_DAY_CAP]
            for row in rows:
                items.append({**row, "platform": p, "snapshot_date": d})
    return items


def compute_trends(
    platforms: list[str] | None = None,
    *,
    days_back: int = DEFAULT_DAYS_BACK,
    min_days: int = 2,
    min_platforms: int = 2,
    threshold: float = PERSIST_THRESHOLD,
    limit: int = 20,
) -> dict[str, Any]:
    """DB-backed: cluster the last ``days_back`` snapshots into persistent topics."""
    db.init_db()
    if platforms is None:
        from main import PLATFORMS as _P
        platforms = list(_P.keys())

    dates = db.all_snapshot_dates(limit=days_back)
    items = _gather(dates, platforms)
    trends = cluster_trends(
        items, dates, min_days=min_days, min_platforms=min_platforms,
        threshold=threshold, limit=limit,
    )
    return {
        "schema_version": 1,
        "window": sorted(dates),
        "days_back": days_back,
        "min_days": min_days,
        "min_platforms": min_platforms,
        "pool_size": len(items),
        "count": len(trends),
        "trends": trends,
    }


if __name__ == "__main__":
    import json
    out = compute_trends()
    print(f"window={out['window']} pool={out['pool_size']} trends={out['count']}")
    for t in out["trends"][:12]:
        arrow = {"rising": "↑", "falling": "↓", "steady": "→", "new": "•"}.get(t["trajectory"], "")
        print(f"  [{t['day_count']}d streak{t['streak']} {t['platform_count']}p {arrow}] {(t['title'] or '')[:48]}")
