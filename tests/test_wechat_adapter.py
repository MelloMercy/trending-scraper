"""Tests for wechat_adapter.py — token cache, draft shaping, API error handling.

All HTTP is faked with httpx.MockTransport; no network and no credentials.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wechat_adapter as wx  # noqa: E402


def client_returning(responses_by_path):
    """Build an httpx.Client whose responses are keyed by URL path."""
    def handler(request: httpx.Request) -> httpx.Response:
        body, status = responses_by_path[request.url.path]
        request.read()  # make request.content available to assertions
        return httpx.Response(status, json=body)
    return httpx.Client(transport=httpx.MockTransport(handler))


def exploding_client():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP call to {request.url}")
    return httpx.Client(transport=httpx.MockTransport(handler))


class AccessTokenTests(unittest.TestCase):
    def test_fetch_and_cache(self):
        with TemporaryDirectory() as d:
            cache = Path(d) / "tok.json"
            cli = client_returning({"/cgi-bin/token": ({"access_token": "TOK1", "expires_in": 7200}, 200)})
            token = wx.get_access_token("app", "sec", cache_path=cache, client=cli, now=1000.0)
            self.assertEqual(token, "TOK1")
            saved = json.loads(cache.read_text())
            self.assertEqual(saved["access_token"], "TOK1")
            self.assertEqual(saved["expires_at"], 1000.0 + 7200)
            self.assertEqual(saved["appid"], "app")

    def test_cache_hit_makes_no_call(self):
        with TemporaryDirectory() as d:
            cache = Path(d) / "tok.json"
            cache.write_text(json.dumps({"appid": "app", "access_token": "CACHED", "expires_at": 9999.0}))
            # exploding client would raise if a network call happened
            token = wx.get_access_token("app", "sec", cache_path=cache, client=exploding_client(), now=1000.0)
            self.assertEqual(token, "CACHED")

    def test_expired_cache_refetches(self):
        with TemporaryDirectory() as d:
            cache = Path(d) / "tok.json"
            cache.write_text(json.dumps({"appid": "app", "access_token": "OLD", "expires_at": 1100.0}))
            cli = client_returning({"/cgi-bin/token": ({"access_token": "NEW", "expires_in": 7200}, 200)})
            # now=1000, expires_at=1100 -> only 100s left (< 300 margin) -> refetch
            token = wx.get_access_token("app", "sec", cache_path=cache, client=cli, now=1000.0)
            self.assertEqual(token, "NEW")

    def test_appid_mismatch_ignores_cache(self):
        with TemporaryDirectory() as d:
            cache = Path(d) / "tok.json"
            cache.write_text(json.dumps({"appid": "other", "access_token": "CACHED", "expires_at": 9999.0}))
            cli = client_returning({"/cgi-bin/token": ({"access_token": "FRESH", "expires_in": 7200}, 200)})
            token = wx.get_access_token("app", "sec", cache_path=cache, client=cli, now=1000.0)
            self.assertEqual(token, "FRESH")

    def test_force_bypasses_cache(self):
        with TemporaryDirectory() as d:
            cache = Path(d) / "tok.json"
            cache.write_text(json.dumps({"appid": "app", "access_token": "CACHED", "expires_at": 9999.0}))
            cli = client_returning({"/cgi-bin/token": ({"access_token": "FORCED", "expires_in": 7200}, 200)})
            token = wx.get_access_token("app", "sec", cache_path=cache, client=cli, now=1000.0, force=True)
            self.assertEqual(token, "FORCED")

    def test_error_response_raises(self):
        cli = client_returning({"/cgi-bin/token": ({"errcode": 40013, "errmsg": "invalid appid"}, 200)})
        with self.assertRaises(wx.WeChatError) as ctx:
            wx.get_access_token("app", "sec", client=cli, now=1000.0)
        self.assertEqual(ctx.exception.errcode, 40013)

    def test_missing_credentials(self):
        with self.assertRaises(ValueError):
            wx.get_access_token("", "sec")


class BuildArticlesTests(unittest.TestCase):
    def test_single_dict_wrapped_and_defaulted(self):
        draft = {"title": "T", "content": "<p>x</p>", "extra": "ignored"}
        arts = wx.build_articles(draft, "THUMB")
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0]["title"], "T")
        self.assertEqual(arts[0]["thumb_media_id"], "THUMB")
        self.assertEqual(arts[0]["need_open_comment"], 0)
        self.assertNotIn("extra", arts[0])

    def test_list_input(self):
        arts = wx.build_articles([{"title": "a", "content": "c"}, {"title": "b", "content": "d"}], "TH")
        self.assertEqual(len(arts), 2)
        self.assertTrue(all(a["thumb_media_id"] == "TH" for a in arts))

    def test_articles_wrapper(self):
        arts = wx.build_articles({"articles": [{"title": "a", "content": "c"}]}, "TH")
        self.assertEqual(len(arts), 1)

    def test_none_values_fall_back_to_defaults(self):
        arts = wx.build_articles({"title": "t", "content": "c", "author": None}, "TH")
        self.assertEqual(arts[0]["author"], "")

    def test_unsupported_type_raises(self):
        with self.assertRaises(ValueError):
            wx.build_articles("nope", "TH")


class AddDraftTests(unittest.TestCase):
    def test_requires_thumb(self):
        with self.assertRaises(ValueError) as ctx:
            wx.add_draft("tok", [{"title": "t", "content": "c"}])
        self.assertIn("thumb_media_id", str(ctx.exception))

    def test_requires_title_and_content(self):
        with self.assertRaises(ValueError):
            wx.add_draft("tok", [{"title": "", "content": "c", "thumb_media_id": "x"}])
        with self.assertRaises(ValueError):
            wx.add_draft("tok", [{"title": "t", "content": "", "thumb_media_id": "x"}])

    def test_success_sends_utf8_body_and_returns_media_id(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            request.read()
            captured["body"] = request.content
            captured["ctype"] = request.headers.get("content-type")
            return httpx.Response(200, json={"media_id": "DRAFT_42"})

        cli = httpx.Client(transport=httpx.MockTransport(handler))
        articles = wx.build_articles({"title": "测试标题", "content": "<p>测试内容</p>"}, "THUMB")
        media_id = wx.add_draft("tok", articles, client=cli)

        self.assertEqual(media_id, "DRAFT_42")
        body = captured["body"]
        # ensure_ascii=False: raw UTF-8 Chinese present, no \uXXXX escapes.
        self.assertIn("测试标题".encode("utf-8"), body)
        self.assertNotIn(b"\\u6d4b", body)
        # Body is valid JSON round-trips back to the same article.
        parsed = json.loads(body.decode("utf-8"))
        self.assertEqual(parsed["articles"][0]["title"], "测试标题")
        self.assertIn("application/json", captured["ctype"])

    def test_error_response_raises(self):
        cli = client_returning({"/cgi-bin/draft/add": ({"errcode": 47001, "errmsg": "data format error"}, 200)})
        articles = wx.build_articles({"title": "t", "content": "c"}, "THUMB")
        with self.assertRaises(wx.WeChatError) as ctx:
            wx.add_draft("tok", articles, client=cli)
        self.assertEqual(ctx.exception.errcode, 47001)


class UploadThumbTests(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            wx.upload_permanent_thumb("tok", "/no/such/cover.jpg")

    def test_success_returns_media_id(self):
        with TemporaryDirectory() as d:
            img = Path(d) / "cover.jpg"
            img.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
            cli = client_returning({"/cgi-bin/material/add_material": ({"media_id": "THUMB_9", "url": "http://x"}, 200)})
            media_id = wx.upload_permanent_thumb("tok", img, client=cli)
            self.assertEqual(media_id, "THUMB_9")


if __name__ == "__main__":
    unittest.main()
