#!/usr/bin/env python3
"""Validate exported public-feed JSON against the expected schema.

This is intentionally dependency-free (stdlib only) so it can run as a fast CI
gate without installing the scraper stack. It mirrors the payload produced by
``public_feed.build_public_feed`` — if that shape changes, update both.

Usage:
    python scripts/validate_feed.py                       # validate feeds/latest*.json
    python scripts/validate_feed.py feeds/2026-06-01.json # validate specific files
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEED_DIR = ROOT / "feeds"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_REGIONS = {"all", "cn", "intl"}

# Region implied by a feed filename, e.g. latest-cn.json -> "cn".
_REGION_SUFFIX_RE = re.compile(r"-(cn|intl)\.json$")


def region_hint_from_name(name: str) -> str | None:
    """Return the region a feed filename advertises, or None for an all-region feed."""
    match = _REGION_SUFFIX_RE.search(name)
    return match.group(1) if match else None


def validate_feed_payload(payload: Any, *, expect_region: str | None = None) -> list[str]:
    """Return a list of human-readable errors. Empty list means the payload is valid.

    ``expect_region`` (when provided) asserts the payload's ``region`` field, e.g.
    a file named ``latest-cn.json`` must carry ``region == "cn"``.
    """
    errors: list[str] = []

    if not isinstance(payload, dict):
        return [f"top level must be an object, got {type(payload).__name__}"]

    _check_type(payload, "schema_version", int, errors)
    if payload.get("schema_version") not in (None, 1):
        errors.append(f"schema_version: expected 1, got {payload.get('schema_version')!r}")

    _check_type(payload, "generated_at", str, errors)

    snap = payload.get("snapshot_date")
    if not isinstance(snap, str) or not DATE_RE.match(snap):
        errors.append(f"snapshot_date: expected YYYY-MM-DD string, got {snap!r}")

    region = payload.get("region")
    if region not in VALID_REGIONS:
        errors.append(f"region: expected one of {sorted(VALID_REGIONS)}, got {region!r}")
    if expect_region is not None:
        wanted = expect_region or "all"
        if region != wanted:
            errors.append(f"region: filename implies {wanted!r}, payload says {region!r}")

    _validate_summary(payload.get("summary"), errors)
    _validate_platforms(payload.get("platforms"), errors)
    _validate_regions(payload.get("regions"), errors)

    if "brief" not in payload:
        errors.append("brief: key missing (expected object or null)")
    elif payload["brief"] is not None and not isinstance(payload["brief"], dict):
        errors.append(f"brief: expected object or null, got {type(payload['brief']).__name__}")

    return errors


def _validate_summary(summary: Any, errors: list[str]) -> None:
    if not isinstance(summary, dict):
        errors.append(f"summary: expected object, got {type(summary).__name__}")
        return
    _check_type(summary, "platforms", int, errors, prefix="summary.")
    _check_type(summary, "items", int, errors, prefix="summary.")
    if not isinstance(summary.get("regions"), dict):
        errors.append("summary.regions: expected object")


def _validate_platforms(platforms: Any, errors: list[str]) -> None:
    if not isinstance(platforms, list):
        errors.append(f"platforms: expected array, got {type(platforms).__name__}")
        return
    for idx, plat in enumerate(platforms):
        where = f"platforms[{idx}]"
        if not isinstance(plat, dict):
            errors.append(f"{where}: expected object")
            continue
        for key in ("id", "name", "region", "snapshot_date", "count", "items"):
            if key not in plat:
                errors.append(f"{where}.{key}: missing")
        if not isinstance(plat.get("count", 0), int):
            errors.append(f"{where}.count: expected int")
        items = plat.get("items")
        if not isinstance(items, list):
            errors.append(f"{where}.items: expected array")
            continue
        if isinstance(plat.get("count"), int) and plat["count"] != len(items):
            errors.append(f"{where}.count ({plat['count']}) != len(items) ({len(items)})")
        for j, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{where}.items[{j}]: expected object")
                continue
            for key in ("rank", "title", "url"):
                if key not in item:
                    errors.append(f"{where}.items[{j}].{key}: missing")


def _validate_regions(regions: Any, errors: list[str]) -> None:
    if not isinstance(regions, dict):
        errors.append(f"regions: expected object, got {type(regions).__name__}")
        return
    for reg, body in regions.items():
        where = f"regions.{reg}"
        if not isinstance(body, dict):
            errors.append(f"{where}: expected object")
            continue
        if not isinstance(body.get("platforms"), list):
            errors.append(f"{where}.platforms: expected array")
        if not isinstance(body.get("total_items", 0), int):
            errors.append(f"{where}.total_items: expected int")


def _check_type(obj: dict, key: str, typ: type, errors: list[str], prefix: str = "") -> None:
    if key not in obj:
        errors.append(f"{prefix}{key}: missing")
    elif not isinstance(obj[key], typ):
        errors.append(f"{prefix}{key}: expected {typ.__name__}, got {type(obj[key]).__name__}")


def _default_targets() -> list[Path]:
    candidates = ["latest.json", "latest-cn.json", "latest-intl.json"]
    return [DEFAULT_FEED_DIR / name for name in candidates if (DEFAULT_FEED_DIR / name).exists()]


def validate_file(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"file not found: {path}"]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_feed_payload(payload, expect_region=region_hint_from_name(path.name))


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = _default_targets()
        if not targets:
            print("FAIL no feed files found; run scripts/export_public_feed.py first")
            return 1

    failed = False
    for path in targets:
        errs = validate_file(path)
        rel = path.relative_to(ROOT) if path.is_absolute() and ROOT in path.parents else path
        if errs:
            failed = True
            print(f"FAIL {rel}")
            for err in errs:
                print(f"  - {err}")
        else:
            print(f"OK   {rel}")
    if failed:
        print("feed validation failed")
        return 1
    print("feed validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
