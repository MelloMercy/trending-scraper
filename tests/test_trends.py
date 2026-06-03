"""Tests for trends.cluster_trends — cross-day persistence clustering (pure, no DB)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import trends  # noqa: E402

DATES = ["2026-06-01", "2026-06-02", "2026-06-03"]


def item(date, platform, title, rank=1):
    return {"snapshot_date": date, "platform": platform, "title": title, "rank": rank, "url": f"https://x/{rank}"}


class ClusterTrendsTests(unittest.TestCase):
    def test_cross_platform_persistent_topic(self):
        items = [
            # Topic A: 3 days, 2 platforms (identical title -> clusters)
            item("2026-06-01", "douyin", "英伟达发布新一代AI芯片", 1),
            item("2026-06-02", "zhihu", "英伟达发布新一代AI芯片", 2),
            item("2026-06-03", "douyin", "英伟达发布新一代AI芯片", 3),
            # Topic B: single day, 2 platforms -> excluded (min_days)
            item("2026-06-02", "douyin", "某地突发地震消息", 5),
            item("2026-06-02", "zhihu", "某地突发地震消息", 6),
            # Topic C: single platform, 3 days -> excluded (min_platforms)
            item("2026-06-01", "bilibili", "某综艺节目最新预告", 7),
            item("2026-06-02", "bilibili", "某综艺节目最新预告", 7),
            item("2026-06-03", "bilibili", "某综艺节目最新预告", 7),
        ]
        res = trends.cluster_trends(items, DATES, min_days=2, min_platforms=2)
        self.assertEqual(len(res), 1)
        t = res[0]
        self.assertEqual(t["day_count"], 3)
        self.assertEqual(t["platform_count"], 2)
        self.assertEqual(t["streak"], 3)
        self.assertEqual(t["first_seen"], "2026-06-01")
        self.assertEqual(t["last_seen"], "2026-06-03")
        self.assertEqual(t["peak_rank"], 1)
        self.assertEqual(len(t["timeline"]), 3)

    def test_min_platforms_relaxed_includes_single_source(self):
        items = [
            item("2026-06-01", "bilibili", "某综艺节目最新预告"),
            item("2026-06-02", "bilibili", "某综艺节目最新预告"),
        ]
        self.assertEqual(trends.cluster_trends(items, DATES, min_platforms=2), [])
        self.assertEqual(len(trends.cluster_trends(items, DATES, min_platforms=1)), 1)

    def test_single_day_excluded(self):
        items = [
            item("2026-06-02", "douyin", "只出现一天的话题"),
            item("2026-06-02", "zhihu", "只出现一天的话题"),
        ]
        self.assertEqual(trends.cluster_trends(items, DATES, min_days=2), [])

    def test_trajectory_rising(self):
        items = [
            item("2026-06-01", "a", "持续升温的大事件", 40),
            item("2026-06-02", "a", "持续升温的大事件", 10),
            item("2026-06-02", "b", "持续升温的大事件", 10),
            item("2026-06-03", "a", "持续升温的大事件", 1),
            item("2026-06-03", "b", "持续升温的大事件", 1),
            item("2026-06-03", "c", "持续升温的大事件", 1),
        ]
        t = trends.cluster_trends(items, DATES, min_platforms=2)[0]
        self.assertEqual(t["trajectory"], "rising")

    def test_trajectory_falling(self):
        items = [
            item("2026-06-01", "a", "逐渐降温的事件", 1),
            item("2026-06-01", "b", "逐渐降温的事件", 1),
            item("2026-06-01", "c", "逐渐降温的事件", 1),
            item("2026-06-03", "a", "逐渐降温的事件", 45),
        ]
        t = trends.cluster_trends(items, DATES, min_platforms=2)[0]
        self.assertEqual(t["trajectory"], "falling")

    def test_streak_with_gap(self):
        items = [
            item("2026-06-01", "a", "中间断了一天的话题"),
            item("2026-06-01", "b", "中间断了一天的话题"),
            item("2026-06-03", "a", "中间断了一天的话题"),
            item("2026-06-03", "b", "中间断了一天的话题"),
        ]
        t = trends.cluster_trends(items, DATES, min_days=2, min_platforms=2)[0]
        self.assertEqual(t["day_count"], 2)
        self.assertEqual(t["streak"], 1)  # 06-01 and 06-03 are not consecutive

    def test_sort_and_limit(self):
        items = [
            # broad topic (3 platforms, 3 days)
            *[item(d, p, "覆盖很广的头条") for d in DATES for p in ("a", "b", "c")],
            # narrower topic (2 platforms, 2 days)
            item("2026-06-01", "a", "范围较小的话题"),
            item("2026-06-02", "b", "范围较小的话题"),
        ]
        res = trends.cluster_trends(items, DATES, min_platforms=2)
        self.assertEqual(res[0]["title"], "覆盖很广的头条")  # higher score first
        self.assertEqual(len(trends.cluster_trends(items, DATES, min_platforms=2, limit=1)), 1)

    def test_empty(self):
        self.assertEqual(trends.cluster_trends([], DATES), [])
        self.assertEqual(trends.cluster_trends([{"title": "", "snapshot_date": "2026-06-01", "platform": "a"}], DATES), [])


if __name__ == "__main__":
    unittest.main()
