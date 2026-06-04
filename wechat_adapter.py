"""WeChat Official Account draft adapter.

Turns the publish-bundle ``wechat-draft.json`` payload into a real *draft* in a
WeChat Official Account (公众号) via the official API. It deliberately creates a
**draft**, never a published/mass-send article — a human reviews and publishes
from the WeChat editor.

Pipeline:
    access_token  ->  upload cover image as permanent material (thumb_media_id)
                  ->  draft/add  ->  draft media_id

This module is credential-agnostic: the caller passes ``appid``/``appsecret``
(resolved from config/env by ``scripts/publish_wechat_draft.py``). Every network
function accepts an optional ``client`` so tests can inject ``httpx.MockTransport``.

WeChat gotchas handled here:
  * Responses are HTTP 200 even on failure — errors live in ``errcode``/``errmsg``.
  * ``draft/add`` bodies must be UTF-8 with non-ASCII left intact; the default
    ``ensure_ascii=True`` JSON (\\uXXXX) trips "data format error" (47001) for some
    accounts, so we serialize with ``ensure_ascii=False`` and send raw bytes.
  * ``access_token`` is rate-limited and valid ~7200s, so we cache it on disk.
"""

from __future__ import annotations

import json
import struct
import time
import zlib
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.weixin.qq.com"
TOKEN_URL = f"{API_BASE}/cgi-bin/token"
ADD_MATERIAL_URL = f"{API_BASE}/cgi-bin/material/add_material"
DRAFT_ADD_URL = f"{API_BASE}/cgi-bin/draft/add"

DEFAULT_TIMEOUT = 30.0
TOKEN_SAFETY_MARGIN = 300  # refresh when fewer than 5 minutes remain

# Fields WeChat's draft/add accepts per article, with safe defaults.
_ARTICLE_FIELDS = {
    "title": "",
    "author": "",
    "digest": "",
    "content": "",
    "content_source_url": "",
    "thumb_media_id": "",
    "need_open_comment": 0,
    "only_fans_can_comment": 0,
}


# Common errcodes mapped to actionable hints (the live-submit failure modes).
ERRCODE_HINTS: dict[int, str] = {
    -1: "微信系统繁忙，稍后重试。",
    40013: "AppID 无效：检查 wechat_appid。",
    40125: "AppSecret 无效：检查 wechat_appsecret（勿带空格/换行）。",
    40164: "调用方 IP 不在白名单：公众平台 → 设置与开发 → 基本配置 → IP白名单，加入本机出口 IP。",
    41001: "缺少 access_token。",
    42001: "access_token 已过期（会自动刷新，重试即可）。",
    45009: "接口调用频率超限（含 token 拉取限额），稍后再试。",
    48001: "未授权此接口：草稿/素材接口通常需要【已认证的服务号】。",
    53401: "封面不合规：thumb_media_id 无效或图片不符合要求。",
}


def explain(errcode: int | None) -> str:
    """Actionable hint for a WeChat errcode, or '' if none known."""
    try:
        return ERRCODE_HINTS.get(int(errcode), "")  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""


class WeChatError(RuntimeError):
    """A WeChat API call returned a non-zero errcode."""

    def __init__(self, errcode: int, errmsg: str, *, context: str = "") -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        self.context = context
        self.hint = explain(errcode)
        where = f" during {context}" if context else ""
        msg = f"WeChat API error{where}: errcode={errcode} errmsg={errmsg!r}"
        if self.hint:
            msg += f"\n  → {self.hint}"
        super().__init__(msg)


def _check(data: dict[str, Any], *, context: str) -> dict[str, Any]:
    """Raise WeChatError if the response carries a non-zero errcode."""
    errcode = data.get("errcode")
    if errcode not in (None, 0):
        raise WeChatError(int(errcode), str(data.get("errmsg", "")), context=context)
    return data


def _client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    """Return (client, owns_it). Caller closes only when owns_it is True."""
    if client is not None:
        return client, False
    return httpx.Client(timeout=DEFAULT_TIMEOUT), True


# ---- access token (with on-disk cache) ----

def _read_token_cache(cache_path: Path, appid: str, now: float) -> str | None:
    if not cache_path.exists():
        return None
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if cached.get("appid") != appid:
        return None
    token = cached.get("access_token")
    expires_at = cached.get("expires_at", 0)
    if token and (expires_at - now) > TOKEN_SAFETY_MARGIN:
        return str(token)
    return None


def _write_token_cache(cache_path: Path, appid: str, token: str, expires_at: float) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"appid": appid, "access_token": token, "expires_at": expires_at}
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(cache_path)


def get_access_token(
    appid: str,
    appsecret: str,
    *,
    cache_path: Path | str | None = None,
    client: httpx.Client | None = None,
    now: float | None = None,
    force: bool = False,
) -> str:
    """Return a valid access token, using and refreshing the on-disk cache."""
    if not appid or not appsecret:
        raise ValueError("appid and appsecret are required to fetch an access token")
    now = time.time() if now is None else now
    cache = Path(cache_path) if cache_path else None

    if cache and not force:
        cached = _read_token_cache(cache, appid, now)
        if cached:
            return cached

    cli, owns = _client(client)
    try:
        resp = cli.get(
            TOKEN_URL,
            params={"grant_type": "client_credential", "appid": appid, "secret": appsecret},
        )
        data = _check(resp.json(), context="get_access_token")
    finally:
        if owns:
            cli.close()

    token = str(data["access_token"])
    expires_in = int(data.get("expires_in", 7200))
    if cache:
        _write_token_cache(cache, appid, token, now + expires_in)
    return token


def verify_credentials(appid: str, appsecret: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Fetch a fresh token to verify AppID/AppSecret AND the IP whitelist.

    This is the cheapest live check: a token fetch exercises credentials and the
    OA's IP-whitelist in one call, so the #1 live-submit blocker surfaces here
    rather than at draft/add. Never caches; returns a result dict (no raise).
    """
    if not appid or not appsecret:
        return {"ok": False, "errmsg": "appid/appsecret missing"}
    try:
        token = get_access_token(appid, appsecret, cache_path=None, client=client, force=True)
        return {"ok": True, "token_prefix": token[:6] + "…"}
    except WeChatError as e:
        return {"ok": False, "errcode": e.errcode, "errmsg": e.errmsg, "hint": e.hint}
    except (httpx.HTTPError, KeyError) as e:
        return {"ok": False, "errmsg": f"{type(e).__name__}: {e}"}


# ---- permanent cover upload ----

def upload_permanent_thumb(
    access_token: str,
    image_path: Path | str,
    *,
    client: httpx.Client | None = None,
) -> str:
    """Upload a cover image as a permanent image material; return its media_id.

    The returned media_id is used as each article's required ``thumb_media_id``.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"cover image not found: {path}")

    cli, owns = _client(client)
    try:
        with open(path, "rb") as fh:
            resp = cli.post(
                ADD_MATERIAL_URL,
                params={"access_token": access_token, "type": "image"},
                files={"media": (path.name, fh, _image_mime(path))},
            )
        data = _check(resp.json(), context="upload_permanent_thumb")
    finally:
        if owns:
            cli.close()
    return str(data["media_id"])


def _image_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, "image/jpeg")


# ---- draft creation ----

def normalize_article(article: dict[str, Any], thumb_media_id: str | None = None) -> dict[str, Any]:
    """Project an arbitrary draft dict onto WeChat's article fields + defaults."""
    out = dict(_ARTICLE_FIELDS)
    for key in _ARTICLE_FIELDS:
        if key in article and article[key] is not None:
            out[key] = article[key]
    if thumb_media_id:
        out["thumb_media_id"] = thumb_media_id
    return out


def build_articles(draft: Any, thumb_media_id: str | None = None) -> list[dict[str, Any]]:
    """Build the ``articles`` list from a draft payload.

    Accepts: a single article object (the publish-bundle shape), a list of
    articles, or a ``{"articles": [...]}`` wrapper.
    """
    if isinstance(draft, dict) and isinstance(draft.get("articles"), list):
        raw = draft["articles"]
    elif isinstance(draft, list):
        raw = draft
    elif isinstance(draft, dict):
        raw = [draft]
    else:
        raise ValueError(f"unsupported draft payload type: {type(draft).__name__}")
    return [normalize_article(item, thumb_media_id) for item in raw]


def add_draft(
    access_token: str,
    articles: list[dict[str, Any]],
    *,
    client: httpx.Client | None = None,
) -> str:
    """Create a draft from the given articles; return the draft's media_id."""
    if not articles:
        raise ValueError("at least one article is required")
    for idx, art in enumerate(articles):
        if not art.get("title"):
            raise ValueError(f"articles[{idx}] is missing a title")
        if not art.get("content"):
            raise ValueError(f"articles[{idx}] is missing content")
        if not art.get("thumb_media_id"):
            raise ValueError(
                f"articles[{idx}] is missing thumb_media_id — upload a cover first "
                "(--cover) or pass --thumb-media-id"
            )

    # Serialize with ensure_ascii=False and send raw UTF-8 bytes (WeChat gotcha).
    body = json.dumps({"articles": articles}, ensure_ascii=False).encode("utf-8")

    cli, owns = _client(client)
    try:
        resp = cli.post(
            DRAFT_ADD_URL,
            params={"access_token": access_token},
            content=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        data = _check(resp.json(), context="add_draft")
    finally:
        if owns:
            cli.close()
    return str(data["media_id"])


# ---- default cover (so a missing cover isn't a live-submit blocker) ----

def _png_bytes(width: int, height: int, rows: list[bytes]) -> bytes:
    """Encode 8-bit RGB scanlines as a PNG. Pure stdlib (no Pillow)."""
    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, colour type 2 (RGB)
    raw = b"".join(b"\x00" + row for row in rows)                 # filter byte 0 per scanline
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_default_cover(path: Path | str, width: int = 900, height: int = 383) -> Path:
    """Write a simple branded gradient cover (≈2.35:1) for use as the article thumb.

    It's a plain placeholder so the live submit isn't blocked on a missing cover;
    supply a real image with --cover for actual publishing.
    """
    rows = []
    for y in range(height):
        t = y / (height - 1) if height > 1 else 0
        r = int(18 + t * 14)
        g = int(26 + t * 24)
        b = int(46 + t * 66)
        rows.append(bytes((r, g, b)) * width)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_png_bytes(width, height, rows))
    return out
