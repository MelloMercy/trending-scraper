#!/usr/bin/env python3
"""Export publish-ready digest files for WeChat/manual delivery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import publisher  # noqa: E402
from main import PLATFORMS, platform_meta  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export WeChat-ready daily digest artifacts.")
    parser.add_argument("--date", dest="snapshot_date", help="Snapshot date, e.g. 2026-05-31")
    parser.add_argument("--out", default=str(publisher.DEFAULT_PUBLISH_DIR), help="Output directory")
    parser.add_argument(
        "--feed-url",
        help="Optional public feed URL to include in digest metadata/content.",
    )
    args = parser.parse_args()

    result = publisher.write_daily_digest_bundle(
        PLATFORMS,
        platform_meta,
        out_dir=args.out,
        snapshot_date=args.snapshot_date,
        feed_url=args.feed_url,
    )
    for key, value in result.items():
        print(f"{key}={value}")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
