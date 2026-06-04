"""Tests for scrapers.contract — the scraper output contract + a real-shape fixture."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Import the contract module directly, NOT via the `scrapers` package — its
# __init__ pulls in Playwright-based scrapers that aren't installed in the lean
# CI tests job. contract.py itself is dependency-free.
sys.path.insert(0, str(ROOT / "scrapers"))

import contract  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_items.json"


class ValidateItemsTests(unittest.TestCase):
    def test_good_list(self):
        items = [{"rank": 1, "title": "ok", "url": "https://x/1", "hot_value": "9", "cover": None}]
        self.assertEqual(contract.validate_items(items), [])
        self.assertTrue(contract.is_valid(items))

    def test_not_a_list(self):
        self.assertTrue(contract.validate_items({"title": "x"}))

    def test_empty_list(self):
        self.assertIn("empty item list", contract.validate_items([]))

    def test_missing_title(self):
        self.assertTrue(any("title" in e for e in contract.validate_items([{"rank": 1}])))
        self.assertTrue(any("title" in e for e in contract.validate_items([{"title": "   "}])))

    def test_bad_rank(self):
        for bad in (0, -1, "1", 1.5, True):
            self.assertTrue(any("rank" in e for e in contract.validate_items([{"title": "t", "rank": bad}])),
                            f"rank={bad!r} should fail")

    def test_rank_optional(self):
        self.assertEqual(contract.validate_items([{"title": "t"}]), [])

    def test_bad_url(self):
        for bad in ("ftp://x", "not a url", 123):
            self.assertTrue(any("url" in e for e in contract.validate_items([{"title": "t", "url": bad}])),
                            f"url={bad!r} should fail")
        self.assertEqual(contract.validate_items([{"title": "t", "url": None}]), [])

    def test_bad_optional_types(self):
        self.assertTrue(any("hot_value" in e for e in contract.validate_items([{"title": "t", "hot_value": 9}])))
        self.assertTrue(any("cover" in e for e in contract.validate_items([{"title": "t", "cover": 1}])))


class FixtureContractTests(unittest.TestCase):
    def test_sample_outputs_satisfy_contract(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for platform, items in data.items():
            if platform.startswith("_"):
                continue
            errs = contract.validate_items(items)
            self.assertEqual(errs, [], f"{platform} sample violates contract: {errs}")
            ranks = [it["rank"] for it in items]
            self.assertEqual(ranks, sorted(ranks), f"{platform} ranks not ascending")
            self.assertEqual(ranks[0], 1, f"{platform} ranks should start at 1")


if __name__ == "__main__":
    unittest.main()
