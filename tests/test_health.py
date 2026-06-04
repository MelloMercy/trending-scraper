"""Tests for health.py — pure source-assessment logic (no DB)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import health  # noqa: E402


def run(status="ok", items=30, error=None, date="2026-06-03"):
    return {"status": status, "item_count": items, "error": error,
            "finished_at": "2026-06-03T08:00:00", "snapshot_date": date}


class AssessTests(unittest.TestCase):
    def test_ok(self):
        a = health.assess([run()], "2026-06-03", "2026-06-04")
        self.assertEqual(a["status"], "ok")
        self.assertEqual(a["days_stale"], 1)

    def test_failing_on_error(self):
        a = health.assess([run(status="error", items=0, error="boom")], "2026-05-01", "2026-06-04")
        self.assertEqual(a["status"], "failing")
        self.assertEqual(a["last_error"], "boom")

    def test_empty_when_ok_but_zero_items(self):
        a = health.assess([run(status="ok", items=0)], "2026-06-03", "2026-06-04")
        self.assertEqual(a["status"], "empty")

    def test_stale_when_last_good_old(self):
        a = health.assess([run()], "2026-05-30", "2026-06-04")  # 5 days old > 2
        self.assertEqual(a["status"], "stale")
        self.assertEqual(a["days_stale"], 5)

    def test_unknown_when_no_data(self):
        self.assertEqual(health.assess([], None, "2026-06-04")["status"], "unknown")

    def test_success_rate(self):
        runs = [run(), run(status="error", items=0), run(), run(items=0)]  # 2/4 usable
        self.assertEqual(health.assess(runs, "2026-06-03", "2026-06-04")["success_rate"], 0.5)


class OverallTests(unittest.TestCase):
    def test_all_ok(self):
        self.assertEqual(health.overall_status({"ok": 17}, 17), "ok")

    def test_down_when_half_broken(self):
        self.assertEqual(health.overall_status({"ok": 8, "failing": 9}, 17), "down")

    def test_degraded_when_some_stale(self):
        self.assertEqual(health.overall_status({"ok": 14, "stale": 3}, 17), "degraded")

    def test_unknown_when_empty(self):
        self.assertEqual(health.overall_status({}, 0), "unknown")


class BadgeTests(unittest.TestCase):
    def test_badge(self):
        b = health.badge_payload(15, 17, "degraded")
        self.assertEqual(b["schemaVersion"], 1)
        self.assertEqual(b["label"], "sources")
        self.assertEqual(b["message"], "15/17 ok")
        self.assertEqual(b["color"], "yellow")

    def test_badge_colors(self):
        self.assertEqual(health.badge_payload(17, 17, "ok")["color"], "brightgreen")
        self.assertEqual(health.badge_payload(0, 17, "down")["color"], "red")


if __name__ == "__main__":
    unittest.main()
