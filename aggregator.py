"""Cross-platform consensus aggregator.

For a given snapshot date, this module:
  1. Pulls all trending items from every platform for that date.
  2. Clusters semantically-similar titles into "topic groups" using
     Union-Find over a character-bigram Jaccard similarity graph.
  3. Scores each group by (#platforms × 100 + Σ(50 - rank)), so a
     story appearing in 3 platforms always beats a single-platform #1.
  4. Returns sorted groups, plus a "big story" pick (the top one).

No LLM is involved here — this is purely deterministic and fast (<50 ms
for 200 items). Thread/theme labeling lives in summarizer.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import db
from similarity import char_bigrams, jaccard

SIMILARITY_THRESHOLD = 0.40  # tune: too low merges unrelated, too high splits same story


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _gather_items(snapshot_date: str, platforms: list[str]) -> list[dict]:
    """Pull all items from all platforms for `snapshot_date` into one flat list."""
    items: list[dict] = []
    for p in platforms:
        for row in db.get_by_date(p, snapshot_date):
            items.append({**row, "platform": p})
    return items


def _cluster(items: list[dict], threshold: float) -> list[list[int]]:
    """Cluster item indices by title similarity. Returns a list of clusters (each a list of indices)."""
    n = len(items)
    bigrams = [char_bigrams(it["title"]) for it in items]
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(bigrams[i], bigrams[j]) >= threshold:
                uf.union(i, j)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    return list(groups.values())


def _score(group_items: list[dict], n_platforms: int) -> int:
    """Score a topic group. Higher = more important."""
    rank_bonus = sum(max(0, 50 - it.get("rank", 99)) for it in group_items)
    return n_platforms * 100 + rank_bonus


def _pick_representative(group_items: list[dict]) -> dict:
    """Pick the single best item to represent a group (lowest rank)."""
    return min(group_items, key=lambda x: x.get("rank", 99))


def aggregate(
    snapshot_date: str | None = None,
    platforms: list[str] | None = None,
    threshold: float = SIMILARITY_THRESHOLD,
) -> dict:
    """Aggregate cross-platform consensus for a snapshot date.

    Returns:
        {
          "snapshot_date": "YYYY-MM-DD",
          "total_items": int,
          "total_groups": int,
          "consensus_count": int,           # groups with >= 2 platforms
          "big_story": {...} | None,        # top-ranked consensus group
          "groups": [                       # sorted by score, desc
            {
              "rank": 1,
              "score": int,
              "platforms": ["douyin","huxiu",...],
              "n_platforms": int,
              "representative": {title, url, platform, rank, ...},
              "items": [...],
            },
            ...
          ],
        }
    """
    snapshot_date = snapshot_date or date.today().isoformat()
    if platforms is None:
        # Lazy import to avoid circular dep with main.py
        from main import PLATFORMS as _P
        platforms = list(_P.keys())

    items = _gather_items(snapshot_date, platforms)
    if not items:
        return {
            "snapshot_date": snapshot_date,
            "total_items": 0,
            "total_groups": 0,
            "consensus_count": 0,
            "big_story": None,
            "groups": [],
        }

    clusters = _cluster(items, threshold)
    groups_out: list[dict] = []
    for cluster_indices in clusters:
        group_items = [items[i] for i in cluster_indices]
        platforms_in_group = sorted({it["platform"] for it in group_items})
        n_p = len(platforms_in_group)
        groups_out.append(
            {
                "score": _score(group_items, n_p),
                "platforms": platforms_in_group,
                "n_platforms": n_p,
                "representative": _pick_representative(group_items),
                "items": group_items,
            }
        )

    groups_out.sort(key=lambda g: g["score"], reverse=True)
    # Assign a rank after sorting
    for i, g in enumerate(groups_out, 1):
        g["rank"] = i

    consensus_groups = [g for g in groups_out if g["n_platforms"] >= 2]
    big_story = consensus_groups[0] if consensus_groups else None

    return {
        "snapshot_date": snapshot_date,
        "total_items": len(items),
        "total_groups": len(groups_out),
        "consensus_count": len(consensus_groups),
        "big_story": big_story,
        "groups": groups_out,
    }


def build_llm_items(snapshot_date: str, platforms: list[str]) -> list[dict]:
    """Build a flat numbered list of items suitable for sending to the LLM.

    Shared between the FastAPI endpoint and the daily scrape script so they
    feed the summarizer identical inputs (and therefore share the cache).
    """
    agg = aggregate(snapshot_date, platforms=platforms)
    items: list[dict] = []
    for group in agg["groups"]:
        for it in group["items"]:
            items.append(
                {
                    "id": len(items),
                    "platform": it["platform"],
                    "title": it["title"],
                    "group_rank": group["rank"],
                }
            )
    return items


if __name__ == "__main__":
    # Quick smoke test
    import json
    result = aggregate()
    print(f"snapshot={result['snapshot_date']}")
    print(f"  total items: {result['total_items']}")
    print(f"  total groups: {result['total_groups']}")
    print(f"  cross-platform consensus groups: {result['consensus_count']}")
    if result["big_story"]:
        bs = result["big_story"]
        print(f"  BIG STORY: {bs['representative']['title']}")
        print(f"    platforms: {bs['platforms']}")
    print("\nTop 10 groups:")
    for g in result["groups"][:10]:
        plats = "+".join(g["platforms"])
        print(f"  [{g['n_platforms']}p, score={g['score']:>4}] {g['representative']['title'][:50]}  ({plats})")
