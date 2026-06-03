"""Tests for public_feed.build_rss — the RSS 2.0 digest export."""

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import public_feed  # noqa: E402


def payload_with_brief():
    return {
        "snapshot_date": "2026-06-03",
        "summary": {"platforms": 2, "items": 5},
        "platforms": [],
        "brief": {
            "status": "ok",
            "narrative": "今日重点。",
            "consensus": [
                {
                    "title": "话题 X & Y <z>",
                    "summary": "摘要含特殊字符 <b> 和 ]]> 终止符",
                    "cn_sources": [{"platform": "知乎", "rank": 1, "title": "原标题", "url": "https://zhihu.com/1"}],
                    "intl_sources": [],
                }
            ],
            "cn_only": [], "intl_only": [], "persistent": [], "emerging": [],
        },
    }


def payload_fallback():
    return {
        "snapshot_date": "2026-06-03",
        "summary": {"platforms": 1, "items": 2},
        "platforms": [
            {
                "id": "douyin", "name": "抖音", "region": "cn", "count": 2,
                "items": [
                    {"rank": 1, "title": "标题一", "url": "https://x/1"},
                    {"rank": 2, "title": "标题二", "url": None},
                ],
            }
        ],
        "brief": None,
    }


class BuildRssTests(unittest.TestCase):
    def test_valid_xml_both_paths(self):
        for payload in (payload_with_brief(), payload_fallback()):
            ET.fromstring(public_feed.build_rss(payload))  # raises on malformed XML

    def test_brief_entries_and_link(self):
        rss = public_feed.build_rss(payload_with_brief(), base_url="https://e.com/")
        root = ET.fromstring(rss)
        ch = root.find("channel")
        self.assertEqual(ch.findtext("link"), "https://e.com")
        items = ch.findall("item")
        self.assertGreaterEqual(len(items), 1)
        # section label prefix + original (unescaped) title round-trips through XML
        self.assertEqual(items[0].findtext("title"), "[跨区共识] 话题 X & Y <z>")
        self.assertEqual(items[0].findtext("link"), "https://zhihu.com/1")
        # source link is embedded as HTML inside the CDATA description
        self.assertIn("<a href=", items[0].findtext("description"))

    def test_cdata_terminator_is_sanitized(self):
        rss = public_feed.build_rss(payload_with_brief())
        self.assertIn("]]&gt;", rss)               # the literal ]]> was escaped
        ET.fromstring(rss)                          # and the doc still parses

    def test_fallback_uses_platform_items(self):
        rss = public_feed.build_rss(payload_fallback())
        items = ET.fromstring(rss).find("channel").findall("item")
        titles = [it.findtext("title") for it in items]
        self.assertIn("标题一", titles)
        first = next(it for it in items if it.findtext("title") == "标题一")
        self.assertEqual(first.findtext("link"), "https://x/1")

    def test_empty_base_url(self):
        rss = public_feed.build_rss(payload_fallback(), base_url=None)
        self.assertEqual(ET.fromstring(rss).find("channel").findtext("link"), "")

    def test_max_items_cap(self):
        p = payload_with_brief()
        p["brief"]["consensus"] = [
            {"title": f"话题{i}", "summary": "", "cn_sources": [], "intl_sources": []}
            for i in range(60)
        ]
        items = ET.fromstring(public_feed.build_rss(p, max_items=10)).find("channel").findall("item")
        self.assertEqual(len(items), 10)


if __name__ == "__main__":
    unittest.main()
