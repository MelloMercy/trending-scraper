#!/usr/bin/env python3
"""Publish the exported feed JSON to a public host.

Scraping stays local — this script never runs Playwright, touches cookies, or
calls the LLM. It takes the already-exported ``feeds/*.json`` artifacts and pushes
them to a public CDN so lightweight clients can read the feed without the scraper.

Targets:
  s3 / r2  Upload to an S3-compatible bucket (Cloudflare R2 is S3-compatible).
  git      Stage ``feeds/`` only, run the public-release audit, commit, and push.

Credentials are read from environment variables (CI/secret friendly) and are
never printed. The secret access key is accepted ONLY via env, never as a flag,
to keep it out of shell history and the process table.

Environment variables (s3 / r2):
  S3_ENDPOINT_URL / R2_ENDPOINT_URL   custom endpoint (required for R2)
  S3_BUCKET / R2_BUCKET               target bucket
  S3_ACCESS_KEY_ID / R2_ACCESS_KEY_ID / AWS_ACCESS_KEY_ID
  S3_SECRET_ACCESS_KEY / R2_SECRET_ACCESS_KEY / AWS_SECRET_ACCESS_KEY
  S3_REGION / AWS_DEFAULT_REGION      region (R2 uses "auto")
  S3_KEY_PREFIX                       key prefix, e.g. "feeds/" (default "")
  PUBLIC_FEED_BASE_URL                base URL used only to print result links

Examples:
  python scripts/publish_feed.py --target r2 --dry-run
  python scripts/publish_feed.py --target s3 --all
  python scripts/publish_feed.py --target git            # commit+push feeds/
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEED_DIR = ROOT / "feeds"

CONTENT_TYPE = "application/json; charset=utf-8"
CACHE_LATEST = "public, max-age=300, must-revalidate"
CACHE_DATED = "public, max-age=86400, immutable"

LATEST_FILES = ["latest.json", "latest-cn.json", "latest-intl.json"]


@dataclass
class S3Config:
    bucket: str
    endpoint_url: str | None
    region: str | None
    access_key_id: str | None
    secret_access_key: str | None
    key_prefix: str
    public_base_url: str | None

    def missing(self) -> list[str]:
        """Return names of required settings that are absent."""
        missing = []
        if not self.bucket:
            missing.append("bucket (S3_BUCKET)")
        if not self.access_key_id:
            missing.append("access key id (S3_ACCESS_KEY_ID)")
        if not self.secret_access_key:
            missing.append("secret access key (S3_SECRET_ACCESS_KEY)")
        return missing


# ---- file selection (pure, no network) ----

def _snapshot_date(feeds_dir: Path) -> str | None:
    latest = feeds_dir / "latest.json"
    if not latest.exists():
        return None
    try:
        return str(json.loads(latest.read_text(encoding="utf-8")).get("snapshot_date") or "") or None
    except (json.JSONDecodeError, OSError):
        return None


def select_files(feeds_dir: Path, *, all_files: bool = False) -> list[Path]:
    """Return the feed files to publish.

    Default: the three stable ``latest*.json`` consumer URLs plus the dated
    snapshot files for the date recorded in ``latest.json``. ``all_files`` returns
    every ``*.json`` in the directory (archival re-sync).
    """
    if all_files:
        return sorted(p for p in feeds_dir.glob("*.json") if p.is_file())

    chosen: list[Path] = []
    for name in LATEST_FILES:
        path = feeds_dir / name
        if path.exists():
            chosen.append(path)
    snap = _snapshot_date(feeds_dir)
    if snap:
        for name in (f"{snap}.json", f"{snap}-cn.json", f"{snap}-intl.json"):
            path = feeds_dir / name
            if path.exists():
                chosen.append(path)
    return chosen


def build_plan(files: list[Path], key_prefix: str, public_base_url: str | None) -> list[dict[str, Any]]:
    """Build an upload plan (one entry per file). Pure: safe to print/test."""
    prefix = key_prefix.strip("/")
    plan: list[dict[str, Any]] = []
    for path in files:
        key = f"{prefix}/{path.name}" if prefix else path.name
        is_latest = path.name.startswith("latest")
        url = None
        if public_base_url:
            url = public_base_url.rstrip("/") + "/" + key
        plan.append(
            {
                "local_path": str(path),
                "name": path.name,
                "size": path.stat().st_size if path.exists() else 0,
                "key": key,
                "url": url,
                "content_type": CONTENT_TYPE,
                "cache_control": CACHE_LATEST if is_latest else CACHE_DATED,
            }
        )
    return plan


# ---- config resolution ----

def _env(*names: str) -> str | None:
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return None


def resolve_s3_config(args: argparse.Namespace) -> S3Config:
    """Resolve S3/R2 settings from CLI flags then environment (flag wins)."""
    is_r2 = args.target == "r2"
    return S3Config(
        bucket=args.bucket or _env("S3_BUCKET", "R2_BUCKET") or "",
        endpoint_url=args.endpoint_url or _env("S3_ENDPOINT_URL", "R2_ENDPOINT_URL"),
        region=args.region or _env("S3_REGION", "AWS_DEFAULT_REGION") or ("auto" if is_r2 else None),
        access_key_id=args.access_key_id or _env("S3_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
        secret_access_key=_env("S3_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"),
        key_prefix=args.key_prefix if args.key_prefix is not None else (_env("S3_KEY_PREFIX") or ""),
        public_base_url=args.public_base_url or _env("PUBLIC_FEED_BASE_URL"),
    )


# ---- upload (lazy boto3 import) ----

def upload_s3(plan: list[dict[str, Any]], cfg: S3Config) -> None:
    try:
        import boto3  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise SystemExit(
            "boto3 is required for s3/r2 upload. Install it with:\n"
            "    pip install boto3"
        ) from exc

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=cfg.endpoint_url,
        region_name=cfg.region,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
    )
    for entry in plan:
        with open(entry["local_path"], "rb") as fh:
            client.put_object(
                Bucket=cfg.bucket,
                Key=entry["key"],
                Body=fh.read(),
                ContentType=entry["content_type"],
                CacheControl=entry["cache_control"],
            )
        print(f"  ↑ {entry['key']} ({entry['size']} bytes)")


# ---- git target ----

def _run_audit() -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_public_release.py")],
        cwd=str(ROOT),
    ).returncode


def git_publish(feeds_dir: Path, *, push: bool = True, dry_run: bool = False) -> int:
    """Stage feeds/ only, audit, commit, and push. Never stages anything else."""
    rel = feeds_dir.relative_to(ROOT) if ROOT in feeds_dir.parents or feeds_dir == ROOT else feeds_dir
    print(f"→ git publish of {rel}/ (push={push}, dry_run={dry_run})")

    print("  running public-release audit before staging...")
    if _run_audit() != 0:
        print("  ✗ audit failed — refusing to commit/push")
        return 1

    if dry_run:
        diff = subprocess.run(
            ["git", "status", "--short", "--", str(rel)],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        print("  would stage:")
        print("    " + (diff.stdout.strip().replace("\n", "\n    ") or "(no changes)"))
        return 0

    subprocess.run(["git", "add", "--", str(rel)], cwd=str(ROOT), check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", str(rel)], cwd=str(ROOT)
    ).returncode
    if staged == 0:
        print("  nothing to publish — feeds unchanged")
        return 0

    snap = _snapshot_date(feeds_dir) or "update"
    message = f"chore(feeds): publish snapshot {snap}"
    subprocess.run(["git", "commit", "-m", message], cwd=str(ROOT), check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True
    ).stdout.strip()
    print(f"  ✓ committed {sha}: {message}")

    if push:
        subprocess.run(["git", "push"], cwd=str(ROOT), check=True)
        print("  ✓ pushed to origin")
    else:
        print("  (skipped push; --no-push)")
    return 0


def _print_plan(plan: list[dict[str, Any]], cfg: S3Config | None) -> None:
    if not plan:
        print("  (no files selected — run scripts/export_public_feed.py first)")
        return
    for entry in plan:
        line = f"  {entry['name']:24s} -> {entry['key']:32s} {entry['size']:>9d} B  [{entry['cache_control']}]"
        print(line)
        if entry["url"]:
            print(f"      url: {entry['url']}")
    total = sum(e["size"] for e in plan)
    print(f"  total: {len(plan)} files, {total} bytes")
    if cfg is not None:
        endpoint = cfg.endpoint_url or "(AWS default)"
        print(f"  bucket={cfg.bucket or '(unset)'} endpoint={endpoint} region={cfg.region or '(default)'}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Publish feeds/*.json to a public host.")
    parser.add_argument("--target", choices=["s3", "r2", "git"], default="r2")
    parser.add_argument("--feeds-dir", default=str(DEFAULT_FEED_DIR))
    parser.add_argument("--all", action="store_true", help="Upload every *.json (archival re-sync).")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan; touch nothing.")
    # s3 / r2
    parser.add_argument("--bucket")
    parser.add_argument("--endpoint-url")
    parser.add_argument("--region")
    parser.add_argument("--key-prefix")
    parser.add_argument("--public-base-url")
    parser.add_argument("--access-key-id", help="Access key id (secret key is env-only).")
    # git
    parser.add_argument("--no-push", action="store_true", help="git target: commit but do not push.")
    args = parser.parse_args(argv)

    feeds_dir = Path(args.feeds_dir)

    if args.target == "git":
        return git_publish(feeds_dir, push=not args.no_push, dry_run=args.dry_run)

    files = select_files(feeds_dir, all_files=args.all)
    cfg = resolve_s3_config(args)
    plan = build_plan(files, cfg.key_prefix, cfg.public_base_url)

    print(f"→ {args.target} publish plan ({'dry-run' if args.dry_run else 'live'}):")
    _print_plan(plan, cfg)

    if args.dry_run:
        return 0
    if not plan:
        return 1
    missing = cfg.missing()
    if missing:
        print("✗ missing required settings: " + ", ".join(missing))
        print("  set them via environment variables (see --help) and retry.")
        return 1

    upload_s3(plan, cfg)
    print(f"✓ published {len(plan)} files to {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
