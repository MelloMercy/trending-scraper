"""Source health / observability.

Scrapers rot when platforms change their HTML/API — that's the real long-term
cost. This turns the scrape_runs log + stored snapshots into a per-source health
view (status, last good date, recent success rate) so a broken or stale source
is *visible*, plus a shields.io-style badge for the README. No network, no LLM.

The assessment helpers (`assess`, `overall_status`, `badge_payload`) are pure and
unit-tested; `compute_health` is the DB-backed wrapper used by the API/export.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import db

STALE_DAYS = 2
STATUSES = ("ok", "stale", "empty", "failing", "unknown")


def _days_between(d1: str, d2: str) -> int | None:
    try:
        a = date.fromisoformat(d1)
        b = date.fromisoformat(d2)
    except (ValueError, TypeError):
        return None
    return (b - a).days


def assess(runs: list[dict], last_good: str | None, today: str, stale_days: int = STALE_DAYS) -> dict[str, Any]:
    """Assess one source from its recent runs + last good snapshot date. Pure."""
    last_run = runs[0] if runs else None
    ok_runs = [r for r in runs if r.get("status") == "ok" and (r.get("item_count") or 0) > 0]
    success_rate = round(len(ok_runs) / len(runs), 2) if runs else None
    days_stale = _days_between(last_good, today) if last_good else None

    if last_run is None and last_good is None:
        status = "unknown"
    elif last_run and last_run.get("status") == "error":
        status = "failing"
    elif last_run and last_run.get("status") == "ok" and (last_run.get("item_count") or 0) == 0:
        status = "empty"
    elif days_stale is not None and days_stale > stale_days:
        status = "stale"
    elif last_good is None:
        status = "unknown"
    else:
        status = "ok"

    err = last_run.get("error") if last_run else None
    return {
        "status": status,
        "last_good_date": last_good,
        "days_stale": days_stale,
        "success_rate": success_rate,
        "last_item_count": last_run.get("item_count") if last_run else None,
        "last_run_status": last_run.get("status") if last_run else None,
        "last_finished_at": last_run.get("finished_at") if last_run else None,
        "last_error": (str(err)[:160] if err else None),
    }


def overall_status(counts: dict[str, int], total: int) -> str:
    if not total:
        return "unknown"
    if counts.get("ok", 0) == total:
        return "ok"
    if counts.get("failing", 0) + counts.get("empty", 0) >= max(1, total // 2):
        return "down"
    return "degraded"


def badge_payload(healthy: int, total: int, overall: str) -> dict[str, Any]:
    """shields.io endpoint format — embed via img.shields.io/endpoint?url=..."""
    color = {"ok": "brightgreen", "degraded": "yellow", "down": "red", "unknown": "lightgrey"}.get(
        overall, "lightgrey"
    )
    return {"schemaVersion": 1, "label": "sources", "message": f"{healthy}/{total} ok", "color": color}


def compute_health(platforms, labeler, *, recent: int = 10, today: str | None = None,
                   stale_days: int = STALE_DAYS) -> dict[str, Any]:
    """DB-backed per-source health for every platform in the registry."""
    db.init_db()
    today = today or date.today().isoformat()
    counts = {s: 0 for s in STATUSES}
    sources = []
    for pid, meta in platforms.items():
        runs = db.get_runs_by_platform(pid, recent)
        hist = db.get_history_dates(pid, 1)
        a = assess(runs, hist[0] if hist else None, today, stale_days)
        counts[a["status"]] = counts.get(a["status"], 0) + 1
        label = labeler(pid) if callable(labeler) else {}
        sources.append({
            "id": pid,
            "name": (label or {}).get("name") or (label or {}).get("label") or pid,
            "region": (meta or {}).get("region"),
            **a,
        })
    total = len(sources)
    healthy = counts.get("ok", 0)
    overall = overall_status(counts, total)
    # Sort worst-first so problems surface at the top.
    order = {"failing": 0, "empty": 1, "stale": 2, "unknown": 3, "ok": 4}
    sources.sort(key=lambda s: (order.get(s["status"], 9), s.get("region") or "", s["id"]))
    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "today": today,
        "summary": counts,
        "healthy": healthy,
        "total": total,
        "overall": overall,
        "sources": sources,
    }
