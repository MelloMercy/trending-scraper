"""Minimal RSS / Atom feed fetcher and parser.

Uses only stdlib (xml.etree.ElementTree) — no feedparser dependency.
Handles both RSS 2.0 (<item>) and Atom (<entry>) variants.

For each feed entry returns:
    {title, link, published, summary, image?}

Caller is responsible for mapping to the standard scraper output shape.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

from .base import USER_AGENT

DEFAULT_TIMEOUT = 15
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"}

# Atom namespace; some feeds embed media: namespaces too
ATOM_NS = "{http://www.w3.org/2005/Atom}"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"


def _strip_html(text: str) -> str:
    """Best-effort strip HTML tags from a string."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _find_text(elem: ET.Element, *names: str) -> Optional[str]:
    """Try each tag name in order; return the first non-empty text."""
    for name in names:
        node = elem.find(name)
        if node is not None and (node.text or "").strip():
            return node.text.strip()
    return None


def _find_link(elem: ET.Element) -> Optional[str]:
    """RSS uses <link>text</link>; Atom uses <link href="..." rel="alternate"/>."""
    # RSS-style text link
    link_node = elem.find("link")
    if link_node is not None:
        if link_node.text and link_node.text.strip():
            return link_node.text.strip()
        # Atom-style attribute
        href = link_node.get("href")
        if href:
            return href
    # Multiple Atom links — prefer rel="alternate"
    for ln in elem.findall(f"{ATOM_NS}link"):
        rel = ln.get("rel", "alternate")
        href = ln.get("href")
        if rel == "alternate" and href:
            return href
    # Fallback: first link with href
    for ln in elem.findall(f"{ATOM_NS}link"):
        href = ln.get("href")
        if href:
            return href
    return None


def _find_image(elem: ET.Element) -> Optional[str]:
    """Look for an image URL in common feed shapes."""
    # <enclosure url="..." type="image/...">
    enc = elem.find("enclosure")
    if enc is not None and (enc.get("type", "").startswith("image") or enc.get("url", "").endswith((".jpg", ".png", ".webp"))):
        return enc.get("url")
    # <media:thumbnail url="..."/> or <media:content url="...">
    media = elem.find(f"{MEDIA_NS}thumbnail")
    if media is not None and media.get("url"):
        return media.get("url")
    media = elem.find(f"{MEDIA_NS}content")
    if media is not None and media.get("url"):
        return media.get("url")
    return None


def _sanitize_xml(xml_text: str) -> str:
    """Remove common feed breakage before strict ElementTree parsing."""
    xml_text = xml_text.lstrip("﻿ \r\n\t")
    # XML 1.0 rejects most control characters; a few feeds include them in
    # descriptions copied from web pages.
    xml_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
    return re.sub(r"&(?![a-zA-Z]+;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", xml_text)


def parse_feed(xml_text: str, limit: int = 30) -> list[dict]:
    """Parse RSS or Atom XML and return up to `limit` entries.

    Returned items: {title, link, published, summary, image?}
    """
    # ElementTree is strict about XML; sanitize common invalid feed output first.
    xml_text = _sanitize_xml(xml_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        root = ET.fromstring(_sanitize_xml(xml_text))

    # Detect feed type
    tag = root.tag.lower()
    items: list[dict] = []

    if tag.endswith("rss") or tag.endswith("channel"):
        channel = root.find("channel") if root.find("channel") is not None else root
        entries = channel.findall("item")
    elif tag.endswith("feed"):  # Atom
        entries = root.findall(f"{ATOM_NS}entry")
    else:
        # Unknown — try both
        entries = root.findall("item") or root.findall(f"{ATOM_NS}entry")

    for entry in entries[:limit]:
        title = _find_text(entry, "title", f"{ATOM_NS}title")
        if not title:
            continue
        link = _find_link(entry)
        published = (
            _find_text(entry, "pubDate", f"{ATOM_NS}published", f"{ATOM_NS}updated")
            or ""
        )
        summary_raw = (
            _find_text(entry, "description", f"{ATOM_NS}summary", f"{ATOM_NS}content")
            or ""
        )
        items.append(
            {
                "title": _strip_html(title),
                "link": link,
                "published": _strip_html(published),
                "summary": _strip_html(summary_raw)[:300],
                "image": _find_image(entry),
            }
        )
    return items


async def fetch_feed(url: str, limit: int = 30, headers: Optional[dict] = None) -> list[dict]:
    """Fetch a feed URL and return parsed entries."""
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=h, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return parse_feed(resp.text, limit=limit)


def to_trending_items(entries: list[dict]) -> list[dict]:
    """Convert RSS entries to the standard trending-item shape.

    Standard shape: {rank, title, url, hot_value, cover}
    `hot_value` = published date string (RSS feeds rarely expose engagement metrics)
    """
    out: list[dict] = []
    for i, e in enumerate(entries):
        if not e.get("title"):
            continue
        out.append(
            {
                "rank": i + 1,
                "title": e["title"],
                "url": e.get("link"),
                "hot_value": e.get("published", ""),
                "cover": e.get("image"),
            }
        )
    return out
