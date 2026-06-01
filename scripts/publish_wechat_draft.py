#!/usr/bin/env python3
"""Create a WeChat Official Account draft from a publish-bundle draft payload.

Dry-run by default: it loads the draft, shows the resolved plan, and reports what
is still required for a live submit (credentials, cover image). Pass ``--submit``
to actually call WeChat: fetch token -> upload the cover as a permanent material
-> ``draft/add``. It only ever creates a *draft*; a human publishes from the
WeChat editor.

Credentials resolve from (highest priority first):
  --appid flag  >  WECHAT_APPID env  >  config.json:wechat_appid
  WECHAT_APPSECRET env  >  config.json:wechat_appsecret      (no flag, by design)

Examples:
  python scripts/publish_wechat_draft.py                          # dry-run latest
  python scripts/publish_wechat_draft.py --date 2026-06-01        # dry-run a date
  python scripts/publish_wechat_draft.py --cover cover.jpg --submit
  python scripts/publish_wechat_draft.py --thumb-media-id <id> --submit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import wechat_adapter  # noqa: E402

DEFAULT_DRAFT = ROOT / "publish" / "latest-wechat-draft.json"
DEFAULT_TOKEN_CACHE = ROOT / "data" / "wechat_token.json"


def resolve_draft_path(args: argparse.Namespace) -> Path:
    if args.date:
        return ROOT / "publish" / args.date / "wechat-draft.json"
    if args.draft:
        return Path(args.draft)
    return DEFAULT_DRAFT


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    cfg = config.load()
    appid = args.appid or os.environ.get("WECHAT_APPID") or cfg.get("wechat_appid") or ""
    appsecret = os.environ.get("WECHAT_APPSECRET") or cfg.get("wechat_appsecret") or ""
    return str(appid), str(appsecret)


def print_plan(articles: list[dict], *, draft_path: Path, appid: str, appsecret: str,
               thumb_source: str) -> None:
    print(f"draft file: {draft_path}")
    print(f"credentials: appid={'set' if appid else 'MISSING'} "
          f"appsecret={'set' if appsecret else 'MISSING'}")
    print(f"cover/thumb: {thumb_source}")
    print(f"articles: {len(articles)}")
    for idx, art in enumerate(articles):
        title = art.get("title") or "(no title)"
        digest = (art.get("digest") or "").strip()
        content_len = len(art.get("content") or "")
        src = art.get("content_source_url") or "(none)"
        thumb = art.get("thumb_media_id") or "(none)"
        print(f"  [{idx}] {title}")
        print(f"      digest: {digest[:80]}")
        print(f"      content: {content_len} chars HTML | source_url: {src}")
        print(f"      thumb_media_id: {thumb}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create a WeChat OA draft from a draft payload.")
    parser.add_argument("--draft", help="Path to a wechat-draft.json (default: publish/latest-wechat-draft.json)")
    parser.add_argument("--date", help="Use publish/<date>/wechat-draft.json")
    parser.add_argument("--appid", help="Override WeChat AppID (secret resolves from env/config only)")
    parser.add_argument("--cover", help="Local cover image to upload as the article thumb")
    parser.add_argument("--thumb-media-id", help="Reuse an already-uploaded permanent image media_id")
    parser.add_argument("--token-cache", default=str(DEFAULT_TOKEN_CACHE), help="Access-token cache path")
    parser.add_argument("--submit", action="store_true", help="Actually create the draft (default: dry-run)")
    args = parser.parse_args(argv)

    draft_path = resolve_draft_path(args)
    if not draft_path.exists():
        print(f"✗ draft not found: {draft_path}")
        print("  run scripts/export_publish_bundle.py first (needs a cached Daily Brief).")
        return 1
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"✗ draft is not valid JSON: {exc}")
        return 1

    appid, appsecret = resolve_credentials(args)

    if args.thumb_media_id:
        thumb_source = f"reuse media_id {args.thumb_media_id}"
    elif args.cover:
        thumb_source = f"upload {args.cover}"
    else:
        thumb_source = "MISSING (need --cover or --thumb-media-id)"

    # Plan uses the static thumb id if reusing; cover uploads happen at submit time.
    preview_thumb = args.thumb_media_id or None
    articles = wechat_adapter.build_articles(draft, preview_thumb)

    print("=== WeChat draft plan ===")
    print_plan(articles, draft_path=draft_path, appid=appid, appsecret=appsecret,
               thumb_source=thumb_source)

    if not args.submit:
        print()
        blockers = []
        if not appid or not appsecret:
            blockers.append("set WECHAT_APPID / WECHAT_APPSECRET (env or config.json)")
        if not args.cover and not args.thumb_media_id:
            blockers.append("provide --cover <image> or --thumb-media-id <id>")
        if blockers:
            print("dry-run only. Before --submit:")
            for b in blockers:
                print(f"  - {b}")
        else:
            print("dry-run only. Re-run with --submit to create the draft.")
        return 0

    # ---- live submit ----
    if not appid or not appsecret:
        print("✗ WECHAT_APPID / WECHAT_APPSECRET are required for --submit.")
        return 1
    if not args.cover and not args.thumb_media_id:
        print("✗ a cover is required: pass --cover <image> or --thumb-media-id <id>.")
        return 1

    try:
        print("→ fetching access token...")
        token = wechat_adapter.get_access_token(appid, appsecret, cache_path=args.token_cache)

        thumb_media_id = args.thumb_media_id
        if not thumb_media_id:
            print(f"→ uploading cover {args.cover} as permanent material...")
            thumb_media_id = wechat_adapter.upload_permanent_thumb(token, args.cover)
            print(f"  thumb_media_id={thumb_media_id}")

        articles = wechat_adapter.build_articles(draft, thumb_media_id)
        print("→ creating draft...")
        media_id = wechat_adapter.add_draft(token, articles)
    except wechat_adapter.WeChatError as exc:
        print(f"✗ {exc}")
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(f"✗ {exc}")
        return 1

    print(f"✓ draft created: media_id={media_id}")
    print("  review and publish it from the WeChat Official Account editor (草稿箱).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
