#!/usr/bin/env python3
"""Create a WeChat Official Account draft from a publish-bundle draft payload.

Three modes:
  (default)   dry-run: load the draft, show the plan, list what's still needed.
  --check     preflight against the live API WITHOUT creating anything: fetch an
              access token (verifies AppID/AppSecret AND the OA IP whitelist —
              the #1 live blocker), validate the draft, and check the cover.
  --submit    live: token -> upload cover as permanent material -> draft/add.
              Only ever creates a *draft*; a human publishes from the editor.

If no cover is given, a simple placeholder cover is generated so the submit
isn't blocked (supply --cover <image> for real publishing).

Credentials resolve from (highest first):
  --appid flag  >  WECHAT_APPID env  >  config.json:wechat_appid
  WECHAT_APPSECRET env  >  config.json:wechat_appsecret      (no flag, by design)

Examples:
  python scripts/publish_wechat_draft.py                 # dry-run latest
  python scripts/publish_wechat_draft.py --check         # live preflight
  python scripts/publish_wechat_draft.py --cover c.jpg --submit
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
DEFAULT_COVER = ROOT / "data" / "wechat-cover-default.png"


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


def cover_plan(args: argparse.Namespace) -> str:
    if args.thumb_media_id:
        return f"reuse media_id {args.thumb_media_id}"
    if args.cover:
        return f"upload {args.cover}"
    return f"generate placeholder cover ({DEFAULT_COVER.name}) — supply --cover for real publishing"


def print_plan(articles: list[dict], *, draft_path: Path, appid: str, appsecret: str, cover: str) -> None:
    print(f"draft file:  {draft_path}")
    print(f"credentials: appid={'set' if appid else 'MISSING'} appsecret={'set' if appsecret else 'MISSING'}")
    print(f"cover/thumb: {cover}")
    print(f"articles:    {len(articles)}")
    for idx, art in enumerate(articles):
        print(f"  [{idx}] {art.get('title') or '(no title)'}")
        print(f"      digest: {(art.get('digest') or '').strip()[:80]}")
        print(f"      content: {len(art.get('content') or '')} chars HTML | source_url: {art.get('content_source_url') or '(none)'}")


def resolve_thumb_media_id(args: argparse.Namespace, token: str) -> str:
    if args.thumb_media_id:
        return args.thumb_media_id
    cover = args.cover
    if not cover:
        print(f"→ no --cover; generating placeholder cover at {DEFAULT_COVER}")
        wechat_adapter.make_default_cover(DEFAULT_COVER)
        cover = str(DEFAULT_COVER)
    print(f"→ uploading cover {cover} as permanent material...")
    media_id = wechat_adapter.upload_permanent_thumb(token, cover)
    print(f"  thumb_media_id={media_id}")
    return media_id


def run_check(draft, appid: str, appsecret: str, args: argparse.Namespace) -> int:
    """Live preflight: verify connectivity + readiness without creating a draft."""
    print("\n=== preflight (--check) ===")
    ok = True

    if appid and appsecret:
        print("✓ credentials present")
        print("→ verifying via token fetch (checks AppID/Secret + IP whitelist)...")
        res = wechat_adapter.verify_credentials(appid, appsecret)
        if res.get("ok"):
            print(f"✓ token fetched ({res['token_prefix']}) — credentials + IP whitelist OK")
        else:
            ok = False
            detail = res.get("errmsg", "")
            code = res.get("errcode")
            print(f"✗ token fetch failed: errcode={code} {detail}")
            if res.get("hint"):
                print(f"  → {res['hint']}")
    else:
        ok = False
        print("✗ credentials missing — set WECHAT_APPID / WECHAT_APPSECRET (env or config.json)")

    # cover
    if args.thumb_media_id:
        print(f"✓ cover: reuse media_id {args.thumb_media_id}")
    elif args.cover:
        if Path(args.cover).exists():
            print(f"✓ cover: {args.cover}")
        else:
            ok = False
            print(f"✗ cover not found: {args.cover}")
    else:
        print("✓ cover: will generate a placeholder (supply --cover for real publishing)")

    # draft validity (fill a dummy thumb so we only check title/content here)
    try:
        arts = wechat_adapter.build_articles(draft, "preflight-thumb")
        for i, a in enumerate(arts):
            if not a.get("title"):
                ok = False; print(f"✗ articles[{i}] missing title")
            if not a.get("content"):
                ok = False; print(f"✗ articles[{i}] missing content")
        print(f"✓ draft payload valid ({len(arts)} article(s))")
    except ValueError as e:
        ok = False
        print(f"✗ draft payload invalid: {e}")

    print("\nresult:", "READY — re-run with --submit to create the draft" if ok else "NOT READY (see ✗ above)")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create a WeChat OA draft from a draft payload.")
    parser.add_argument("--draft", help="Path to a wechat-draft.json (default: publish/latest-wechat-draft.json)")
    parser.add_argument("--date", help="Use publish/<date>/wechat-draft.json")
    parser.add_argument("--appid", help="Override WeChat AppID (secret resolves from env/config only)")
    parser.add_argument("--cover", help="Local cover image to upload as the article thumb")
    parser.add_argument("--thumb-media-id", help="Reuse an already-uploaded permanent image media_id")
    parser.add_argument("--token-cache", default=str(DEFAULT_TOKEN_CACHE), help="Access-token cache path")
    parser.add_argument("--check", action="store_true", help="Live preflight; create nothing")
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
    articles = wechat_adapter.build_articles(draft, args.thumb_media_id or None)

    print("=== WeChat draft plan ===")
    print_plan(articles, draft_path=draft_path, appid=appid, appsecret=appsecret, cover=cover_plan(args))

    if args.check:
        return run_check(draft, appid, appsecret, args)

    if not args.submit:
        print()
        blockers = []
        if not appid or not appsecret:
            blockers.append("set WECHAT_APPID / WECHAT_APPSECRET (env or config.json)")
        if blockers:
            print("dry-run only. Before --submit:")
            for b in blockers:
                print(f"  - {b}")
            print("  tip: run --check to verify credentials + IP whitelist against the live API.")
        else:
            print("dry-run only. Run --check to verify live readiness, then --submit to create the draft.")
        return 0

    # ---- live submit ----
    if not appid or not appsecret:
        print("✗ WECHAT_APPID / WECHAT_APPSECRET are required for --submit.")
        return 1
    try:
        print("→ fetching access token...")
        token = wechat_adapter.get_access_token(appid, appsecret, cache_path=args.token_cache)
        thumb_media_id = resolve_thumb_media_id(args, token)
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
