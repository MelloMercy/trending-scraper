"""Lightweight runtime config layer.

Config is read from `config.json` next to this file. If the file is missing,
defaults below are used. Secrets are read-only at runtime — `GET /api/config`
hides values, `POST /api/config` writes them but never echoes them back.

Schema:
    deepseek_api_key        (str)  — optional. Used by DeepSeek-powered
                                     clustering and Daily Brief generation.
    xhs_cookies_path        (str)  — path to a Playwright-format cookies JSON for
                                     Xiaohongshu login session.
    schedule_hour           (int)  — hour (0-23) launchd runs the daily scrape.
    schedule_minute         (int)  — minute (0-59).
    enabled_platforms       (list) — subset of supported platforms.

Anything not in the schema is silently ignored on load.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).parent / "config.json"

ALL_PLATFORMS = [
    # cn
    "douyin", "xiaohongshu", "bilibili", "zhihu", "kr36", "huxiu",
    # intl
    "bbc_world", "hackernews", "theverge", "techcrunch", "nyt_world", "arstechnica",
    # intl (Tier-1 expansion)
    "reuters", "ap_news", "politico", "axios", "semafor",
]

DEFAULTS: dict[str, Any] = {
    "deepseek_api_key": "",
    "xhs_cookies_path": "data/xhs_cookies.json",
    "schedule_hour": 8,
    "schedule_minute": 0,
    "enabled_platforms": list(ALL_PLATFORMS),
}

# Field-level descriptions exposed via /api/config — keep in sync with DEFAULTS.
SCHEMA: dict[str, dict[str, Any]] = {
    "deepseek_api_key": {
        "type": "string",
        "secret": True,
        "description": "DeepSeek API key, used for LLM clustering and Daily Brief generation.",
    },
    "xhs_cookies_path": {
        "type": "string",
        "secret": False,
        "description": "Path to a Playwright-format cookies JSON to access Xiaohongshu hot board.",
    },
    "schedule_hour": {
        "type": "integer",
        "secret": False,
        "min": 0,
        "max": 23,
        "description": "Hour of day the daily scrape runs (launchd).",
    },
    "schedule_minute": {
        "type": "integer",
        "secret": False,
        "min": 0,
        "max": 59,
        "description": "Minute of hour the daily scrape runs.",
    },
    "enabled_platforms": {
        "type": "array",
        "secret": False,
        "items": ALL_PLATFORMS,
        "description": "Platforms enabled for scraping.",
    },
}


def load() -> dict[str, Any]:
    """Return the merged config: defaults + on-disk overrides."""
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text())
            if isinstance(on_disk, dict):
                for k, v in on_disk.items():
                    if k in DEFAULTS:
                        cfg[k] = v
        except Exception as e:
            print(f"[config] Failed to load {CONFIG_PATH}: {e}; using defaults.")
    return cfg


def save(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge updates into config.json. Returns the new full config."""
    cfg = load()
    for k, v in updates.items():
        if k in DEFAULTS:
            cfg[k] = v
    # Persist only non-default values to keep config.json small (optional)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return cfg


def public_view(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a sanitized view of the config — secrets are masked."""
    cfg = cfg or load()
    out: dict[str, Any] = {}
    for k, v in cfg.items():
        meta = SCHEMA.get(k, {})
        if meta.get("secret"):
            out[k] = "set" if v else ""
        else:
            out[k] = v
    return out
