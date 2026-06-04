"""Daily scrape entry point — designed to be invoked by cron / launchd.

Usage:
    python scrape_daily.py                 # scrape all + run LLM clustering (cn + intl)
    python scrape_daily.py douyin          # scrape just one platform
    python scrape_daily.py --region intl   # scrape only intl platforms
    python scrape_daily.py --no-cluster    # skip LLM clustering even if key is set
    python scrape_daily.py --no-export     # skip static public-feed JSON export
    python scrape_daily.py --no-publish    # skip WeChat-ready digest export
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime

import aggregator
import briefer
import db
import health
import public_feed
import publisher
import summarizer
from main import PLATFORMS, platform_meta, platforms_for_region
from scrapers import contract


async def run_one(name: str) -> tuple[str, int, str | None]:
    meta = PLATFORMS[name]
    region = meta["region"]
    run_id = db.log_run_start(name)
    try:
        items = await meta["fn"]()
        issues = contract.validate_items(items)
        if issues:
            print(f"  ⚠ {name}: {len(issues)} output-contract issue(s); first: {issues[0]}")
        count = db.save_items(name, items, region=region)
        db.log_run_finish(run_id, "ok", item_count=count)
        return name, count, None
    except Exception as e:
        db.log_run_finish(run_id, "error", error=str(e))
        return name, 0, str(e)


async def run_clustering_for_region(region: str, target_platforms: list[str]) -> None:
    """After scraping, run LLM thread clustering for one region."""
    if not summarizer.is_enabled():
        print(f"  ⊘ [{region}] LLM clustering skipped — deepseek_api_key not configured")
        return
    region_platforms = [p for p in target_platforms if PLATFORMS[p]["region"] == region]
    if not region_platforms:
        return
    snap = date.today().isoformat()
    items = aggregator.build_llm_items(snap, region_platforms)
    if not items:
        print(f"  ⊘ [{region}] LLM clustering skipped — no items")
        return
    sent = min(len(items), summarizer.MAX_ITEMS_FOR_LLM)
    print(f"  → [{region}] running LLM clustering on top {sent} of {len(items)} items...")
    result = await summarizer.cluster_themes(snap, items, region=region, force=True)
    if result["status"] == "ok":
        n = len(result.get("threads", []))
        print(f"  ✓ [{region}] LLM clustering: {n} themes cached")
    else:
        print(f"  ✗ [{region}] LLM clustering failed: {result.get('error', 'unknown')}")


async def main(
    targets: list[str],
    do_cluster: bool = True,
    do_export: bool = True,
    do_publish: bool = True,
) -> int:
    db.init_db()
    summarizer.init_cache_table()
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Scraping: {', '.join(targets)}")
    results = await asyncio.gather(*(run_one(t) for t in targets))
    rc = 0
    successful_targets: list[str] = []
    for name, count, err in results:
        if err:
            print(f"  ✗ {name}: FAILED — {err}")
            rc = 1
        else:
            print(f"  ✓ {name}: {count} items")
            successful_targets.append(name)
    if do_cluster and successful_targets:
        # Cluster each region that has successful platforms
        regions = {PLATFORMS[p]["region"] for p in successful_targets}
        for region in sorted(regions):
            await run_clustering_for_region(region, successful_targets)

        # After all region clusters finish, generate the Daily Brief
        await run_brief()
    if do_export and successful_targets:
        run_public_feed_export()
    if do_publish and successful_targets:
        run_publish_export()
    print_health_summary()
    return rc


def print_health_summary() -> None:
    """One-line source-health summary for the cron log."""
    try:
        h = health.compute_health(PLATFORMS, platform_meta)
        s = h["summary"]
        problems = [src["id"] for src in h["sources"] if src["status"] != "ok"]
        line = (f"  health[{h['overall']}]: ok={s['ok']} stale={s['stale']} "
                f"empty={s['empty']} failing={s['failing']}")
        if problems:
            line += f" — attention: {', '.join(problems[:8])}"
        print(line)
    except Exception as e:
        print(f"  ⊘ health summary failed: {e}")


async def run_brief() -> None:
    """Synthesize the cross-region Daily Brief. Requires both regions clustered."""
    if not briefer.is_enabled():
        print("  ⊘ Daily Brief skipped — deepseek_api_key not configured")
        return
    print("  → generating Daily Brief (cross-region synthesis + persistence)...")
    try:
        result = await briefer.generate_brief(force=True)
    except Exception as e:
        print(f"  ✗ Daily Brief failed (uncaught): {e}")
        return
    if result.get("status") == "ok":
        n_total = sum(
            len(result.get(s, []) or [])
            for s in ("consensus", "cn_only", "intl_only", "persistent", "emerging")
        )
        print(f"  ✓ Daily Brief: {n_total} entries across 5 sections, cached")
    else:
        print(f"  ✗ Daily Brief: status={result.get('status')} error={result.get('error', '—')[:120]}")


def run_public_feed_export() -> None:
    """Export static feed artifacts after scraping/clustering."""
    try:
        result = public_feed.write_public_feed(PLATFORMS, platform_meta)
    except Exception as e:
        print(f"  ✗ Public feed export failed: {e}")
        return
    print(f"  ✓ Public feed exported: {result['latest']}")


def run_publish_export() -> None:
    """Export WeChat/manual-delivery daily digest artifacts."""
    try:
        result = publisher.write_daily_digest_bundle(PLATFORMS, platform_meta)
    except Exception as e:
        print(f"  ✗ Publish bundle export failed: {e}")
        return
    if result.get("status") == "ok":
        print(f"  ✓ Publish bundle exported: {result['latest_markdown']}")
    else:
        print(f"  ⊘ Publish bundle skipped: {result.get('error', 'unknown')}")


def parse_args(argv: list[str]) -> tuple[list[str], bool, bool, bool]:
    """Returns (targets, do_cluster, do_export, do_publish)."""
    do_cluster = True
    do_export = True
    do_publish = True
    region_filter: str | None = None
    targets: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--no-cluster":
            do_cluster = False
        elif a == "--no-export":
            do_export = False
        elif a == "--no-publish":
            do_publish = False
        elif a == "--region":
            i += 1
            if i >= len(argv):
                print("--region requires a value (cn / intl)")
                sys.exit(2)
            region_filter = argv[i]
        else:
            targets.append(a)
        i += 1
    if region_filter:
        if targets:
            print("Cannot mix --region and explicit platforms")
            sys.exit(2)
        targets = platforms_for_region(region_filter)
        if not targets:
            print(f"No platforms for region={region_filter}")
            sys.exit(2)
    elif not targets:
        targets = list(PLATFORMS.keys())
    unknown = [t for t in targets if t not in PLATFORMS]
    if unknown:
        print(f"Unknown platform(s): {unknown}. Valid: {list(PLATFORMS.keys())}")
        sys.exit(2)
    return targets, do_cluster, do_export, do_publish


if __name__ == "__main__":
    targets, do_cluster, do_export, do_publish = parse_args(sys.argv[1:])
    sys.exit(asyncio.run(main(targets, do_cluster=do_cluster, do_export=do_export, do_publish=do_publish)))
