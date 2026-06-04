"""The output contract every scraper must satisfy.

A scraper returns a list of dict items. Enforcing a shared shape means a platform
that changes its HTML/API and starts emitting garbage is caught early (at scrape
time we warn; in CI we unit-test the validator) instead of silently corrupting
the feed. Validation is deliberately lenient about optional fields and strict
about the essentials (a usable title; sane rank/url types).
"""

from __future__ import annotations

import re

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def validate_items(items: object) -> list[str]:
    """Return a list of contract violations. Empty list == valid."""
    if not isinstance(items, list):
        return [f"items must be a list, got {type(items).__name__}"]

    errors: list[str] = []
    if not items:
        errors.append("empty item list")

    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errors.append(f"[{i}] not a dict: {type(it).__name__}")
            continue
        title = it.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"[{i}] missing/empty title")
        rank = it.get("rank")
        if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool) or rank < 1):
            errors.append(f"[{i}] bad rank: {rank!r}")
        url = it.get("url")
        if url is not None and (not isinstance(url, str) or not _URL_RE.match(url)):
            errors.append(f"[{i}] bad url: {str(url)[:40]!r}")
        for key in ("hot_value", "cover"):
            val = it.get(key)
            if val is not None and not isinstance(val, str):
                errors.append(f"[{i}] {key} must be a string or None")
    return errors


def is_valid(items: object) -> bool:
    return not validate_items(items)
