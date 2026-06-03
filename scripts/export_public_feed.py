#!/usr/bin/env python3
"""Export the current database/cache state to static JSON feed files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import public_feed  # noqa: E402
from main import PLATFORMS, platform_meta  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public feed JSON artifacts.")
    parser.add_argument("--date", dest="snapshot_date", help="Snapshot date, e.g. 2026-05-31")
    parser.add_argument("--region", choices=["cn", "intl"], help="Export only one region")
    parser.add_argument("--out", default=str(public_feed.DEFAULT_FEED_DIR), help="Output directory")
    parser.add_argument("--base-url", help="Public base URL stamped into the RSS channel link")
    args = parser.parse_args()

    result = public_feed.write_public_feed(
        PLATFORMS,
        platform_meta,
        out_dir=args.out,
        snapshot_date=args.snapshot_date,
        region=args.region,
        base_url=args.base_url,
    )
    for key in ("snapshot_date", "dated", "latest", "rss_latest", "rss_dated"):
        if key in result:
            print(f"{key}={result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
