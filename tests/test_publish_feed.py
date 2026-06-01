"""Tests for scripts/publish_feed.py — file selection, plan building, config."""

import argparse
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_feed  # noqa: E402


def _make_feeds(dirpath: Path, snapshot: str = "2026-06-01") -> None:
    payload = {"snapshot_date": snapshot}
    for name in ("latest.json", "latest-cn.json", "latest-intl.json",
                 f"{snapshot}.json", f"{snapshot}-cn.json", f"{snapshot}-intl.json",
                 "2026-05-31.json"):
        (dirpath / name).write_text(json.dumps(payload), encoding="utf-8")


class SelectFilesTests(unittest.TestCase):
    def test_default_selects_latest_plus_snapshot(self):
        with TemporaryDirectory() as d:
            feeds = Path(d)
            _make_feeds(feeds)
            names = {p.name for p in publish_feed.select_files(feeds)}
            self.assertEqual(
                names,
                {"latest.json", "latest-cn.json", "latest-intl.json",
                 "2026-06-01.json", "2026-06-01-cn.json", "2026-06-01-intl.json"},
            )
            # The older dated snapshot is NOT pulled in by default.
            self.assertNotIn("2026-05-31.json", names)

    def test_all_selects_everything(self):
        with TemporaryDirectory() as d:
            feeds = Path(d)
            _make_feeds(feeds)
            names = {p.name for p in publish_feed.select_files(feeds, all_files=True)}
            self.assertIn("2026-05-31.json", names)
            self.assertEqual(len(names), 7)

    def test_empty_dir(self):
        with TemporaryDirectory() as d:
            self.assertEqual(publish_feed.select_files(Path(d)), [])


class BuildPlanTests(unittest.TestCase):
    def test_keys_cache_and_url(self):
        with TemporaryDirectory() as d:
            feeds = Path(d)
            _make_feeds(feeds)
            files = publish_feed.select_files(feeds)
            plan = publish_feed.build_plan(files, "feeds", "https://cdn.example.com/")
            by_name = {e["name"]: e for e in plan}

            latest = by_name["latest.json"]
            self.assertEqual(latest["key"], "feeds/latest.json")
            self.assertEqual(latest["url"], "https://cdn.example.com/feeds/latest.json")
            self.assertEqual(latest["content_type"], "application/json; charset=utf-8")
            self.assertEqual(latest["cache_control"], publish_feed.CACHE_LATEST)

            dated = by_name["2026-06-01.json"]
            self.assertEqual(dated["cache_control"], publish_feed.CACHE_DATED)

            # No secret-bearing fields ever leak into the (printable) plan.
            for entry in plan:
                self.assertEqual(
                    set(entry),
                    {"local_path", "name", "size", "key", "url", "content_type", "cache_control"},
                )

    def test_no_prefix_and_no_base_url(self):
        with TemporaryDirectory() as d:
            feeds = Path(d)
            _make_feeds(feeds)
            files = publish_feed.select_files(feeds)
            plan = publish_feed.build_plan(files, "", None)
            entry = next(e for e in plan if e["name"] == "latest.json")
            self.assertEqual(entry["key"], "latest.json")
            self.assertIsNone(entry["url"])


class ResolveConfigTests(unittest.TestCase):
    def _args(self, **over) -> argparse.Namespace:
        base = dict(target="s3", bucket=None, endpoint_url=None, region=None,
                    key_prefix=None, public_base_url=None, access_key_id=None)
        base.update(over)
        return argparse.Namespace(**base)

    def test_env_resolution(self):
        env = {
            "S3_BUCKET": "mybucket",
            "S3_ACCESS_KEY_ID": "AKIA_TEST",
            "S3_SECRET_ACCESS_KEY": "shhh",
            "S3_ENDPOINT_URL": "https://endpoint",
            "S3_KEY_PREFIX": "feeds",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            cfg = publish_feed.resolve_s3_config(self._args())
        self.assertEqual(cfg.bucket, "mybucket")
        self.assertEqual(cfg.endpoint_url, "https://endpoint")
        self.assertEqual(cfg.key_prefix, "feeds")
        self.assertEqual(cfg.missing(), [])

    def test_flag_overrides_env(self):
        with mock.patch.dict("os.environ", {"S3_BUCKET": "envbucket"}, clear=True):
            cfg = publish_feed.resolve_s3_config(self._args(bucket="flagbucket"))
        self.assertEqual(cfg.bucket, "flagbucket")

    def test_r2_default_region_auto(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            cfg = publish_feed.resolve_s3_config(self._args(target="r2"))
        self.assertEqual(cfg.region, "auto")

    def test_missing_reports_required(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            cfg = publish_feed.resolve_s3_config(self._args())
        missing = cfg.missing()
        self.assertTrue(any("bucket" in m for m in missing))
        self.assertTrue(any("secret access key" in m for m in missing))


if __name__ == "__main__":
    unittest.main()
