"""Interactive Xiaohongshu cookie capture helper.

Opens a real (non-headless) Chromium window pointed at xiaohongshu.com.
You log in via the QR code or password as usual. As soon as the page detects
you've reached an authenticated state, the script saves the cookies to
`data/xhs_cookies.json` and exits.

Usage:
    python xhs_login.py

If you close the browser manually after logging in, the script will also
save cookies on shutdown.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

COOKIES_PATH = Path(__file__).parent / "data" / "xhs_cookies.json"
LOGIN_URL = "https://www.xiaohongshu.com/explore"
# After login XHS sets web_session in cookies
AUTH_COOKIE_NAMES = {"web_session", "webId", "a1"}


async def main() -> int:
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("Opening Chromium…  log in via the QR code, then come back here.")
    print(f"Cookies will be saved to: {COOKIES_PATH}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/129.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await ctx.new_page()
        await page.goto(LOGIN_URL)

        print("\n⏳ Waiting for login. The script will detect it automatically.")
        print("   (Or close the browser window when done — cookies will still save.)\n")

        saved = False
        try:
            # Poll cookies until the authenticated set shows up
            for _ in range(600):  # up to ~10 minutes
                cookies = await ctx.cookies()
                names = {c["name"] for c in cookies}
                if AUTH_COOKIE_NAMES & names and any(c["name"] == "web_session" for c in cookies):
                    COOKIES_PATH.write_text(
                        json.dumps(cookies, ensure_ascii=False, indent=2)
                    )
                    print(f"✅ Detected login — saved {len(cookies)} cookies to {COOKIES_PATH}")
                    saved = True
                    break
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            if not saved:
                # Manual close path — try to grab whatever we have
                try:
                    cookies = await ctx.cookies()
                    if cookies:
                        COOKIES_PATH.write_text(
                            json.dumps(cookies, ensure_ascii=False, indent=2)
                        )
                        print(
                            f"⚠️  Login not auto-detected, but saved {len(cookies)} cookies anyway."
                        )
                        saved = True
                except Exception:
                    pass

            try:
                await ctx.close()
                await browser.close()
            except Exception:
                pass

    if not saved:
        print("❌ No cookies captured. Try again.")
        return 1
    print("\n🎉 Done. Now run a scrape to verify:")
    print("   curl -X POST http://localhost:11001/api/refresh/xiaohongshu")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
