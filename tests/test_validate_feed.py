"""Tests for scripts/validate_feed.py — the public-feed schema gate."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_feed  # noqa: E402


def good_payload(region: str = "all") -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-01T08:00:00",
        "snapshot_date": "2026-06-01",
        "region": region,
        "summary": {"platforms": 1, "items": 2, "regions": {}},
        "platforms": [
            {
                "id": "douyin",
                "name": "抖音",
                "region": "cn",
                "snapshot_date": "2026-06-01",
                "count": 2,
                "items": [
                    {"rank": 1, "title": "a", "url": "https://x/1"},
                    {"rank": 2, "title": "b", "url": None},
                ],
            }
        ],
        "regions": {"cn": {"platforms": ["douyin"], "total_items": 2}},
        "brief": None,
    }


class ValidateFeedTests(unittest.TestCase):
    def test_good_payload_passes(self):
        self.assertEqual(validate_feed.validate_feed_payload(good_payload()), [])

    def test_region_payload_passes_with_expectation(self):
        payload = good_payload(region="cn")
        self.assertEqual(validate_feed.validate_feed_payload(payload, expect_region="cn"), [])

    def test_region_mismatch_flagged(self):
        payload = good_payload(region="all")
        errs = validate_feed.validate_feed_payload(payload, expect_region="cn")
        self.assertTrue(any("filename implies" in e for e in errs), errs)

    def test_missing_schema_version(self):
        payload = good_payload()
        del payload["schema_version"]
        errs = validate_feed.validate_feed_payload(payload)
        self.assertTrue(any("schema_version" in e for e in errs), errs)

    def test_wrong_schema_version(self):
        payload = good_payload()
        payload["schema_version"] = 2
        errs = validate_feed.validate_feed_payload(payload)
        self.assertTrue(any("expected 1" in e for e in errs), errs)

    def test_bad_snapshot_date(self):
        payload = good_payload()
        payload["snapshot_date"] = "06/01/2026"
        errs = validate_feed.validate_feed_payload(payload)
        self.assertTrue(any("snapshot_date" in e for e in errs), errs)

    def test_count_mismatch(self):
        payload = good_payload()
        payload["platforms"][0]["count"] = 99
        errs = validate_feed.validate_feed_payload(payload)
        self.assertTrue(any("!= len(items)" in e for e in errs), errs)

    def test_missing_item_keys(self):
        payload = good_payload()
        payload["platforms"][0]["items"][0] = {"rank": 1}  # no title/url
        errs = validate_feed.validate_feed_payload(payload)
        self.assertTrue(any("items[0].title" in e for e in errs), errs)

    def test_non_dict_payload(self):
        self.assertTrue(validate_feed.validate_feed_payload([1, 2, 3]))

    def test_region_hint_from_name(self):
        self.assertEqual(validate_feed.region_hint_from_name("latest-cn.json"), "cn")
        self.assertEqual(validate_feed.region_hint_from_name("2026-06-01-intl.json"), "intl")
        self.assertIsNone(validate_feed.region_hint_from_name("latest.json"))


if __name__ == "__main__":
    unittest.main()
