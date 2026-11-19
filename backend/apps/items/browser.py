"""Page visits in headless Chromium, through the Playwright server in the
browser container: rendered HTML and screenshots."""

import time
from dataclasses import dataclass

from django.conf import settings

VIEWPORT = {"width": 1280, "height": 1280}
MAX_HEIGHT = 20_000
CONNECT_TIMEOUT = 30_000
LOAD_TIMEOUT = 45_000
# After load, waits for the network to go quiet; many pages never do.
SETTLE_TIMEOUT = 10_000
CHALLENGE_TIMEOUT = 15
SCROLL_STEP = 1000
# The page as it ends up: a challenge that never cleared stays on one of
# these; one that cleared loads the real page.
BLOCKED_STATUSES = {401, 403, 429, 503}
SCROLL_PAUSE = 0.25

# Bot-check interstitials (Cloudflare, DDoS-Guard and similar), by title
# or page text. Matched lowercase.
CHALLENGE_TITLES = (
    "just a moment",
    "attention required",
    "please wait",
    "access denied",
    "ddos-guard",
    "security checkpoint",
)
CHALLENGE_TEXT = (
    "checking your browser",
    "verify you are human",
    "enable javascript and cookies to continue",
)

# Scrolls down in steps so lazy content loads, up to MAX_HEIGHT.
SCROLL_JS = """
async ([step, pause, max]) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let y = 0;
  while (y < Math.min(document.documentElement.scrollHeight, max)) {
    y += step;
    window.scrollTo(0, y);
    await sleep(pause);
  }
  window.scrollTo(0, 0);
  return document.documentElement.scrollHeight;
}
"""


class BrowserError(Exception):
    pass


class Blocked(BrowserError):
    def __init__(self, message: str, status: int | None):
        super().__init__(message)
        self.status = status


@dataclass
class Visit:
    url: str
    # Of the last page load: after a challenge clears, the real page's.
    status: int | None
    html: str
    head: bytes
    full: bytes


def is_challenge(title: str, html: str) -> bool:
    title, html = title.lower(), html.lower()
    return any(t in title for t in CHALLENGE_TITLES) or any(
        t in html for t in CHALLENGE_TEXT
    )


def visit(url: str) -> Visit:
    """Loads the page and returns its rendered HTML and screenshots.
    Raises Blocked for bot walls, BrowserError for anything else."""
    from playwright.sync_api import TimeoutError, sync_playwright

    from apps.items.fetch import USER_AGENT

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect(
                settings.BROWSER_URL, timeout=CONNECT_TIMEOUT
            )
            try:
                # A fresh context per visit: no cookies carried between saves.
                context = browser.new_context(
                    viewport=VIEWPORT, user_agent=USER_AGENT, locale="en-US"
                )
                page = context.new_page()
                # Main document loads, including reloads by challenge scripts.
                loads: list[int] = []
                page.on(
                    "response",
                    lambda r: (
                        r.request.is_navigation_request()
                        and r.frame == page.main_frame
                        and loads.append(r.status)
                    ),
                )
                page.goto(url, wait_until="load", timeout=LOAD_TIMEOUT)
                try:
                    page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT)
                except TimeoutError:
                    pass

                deadline = time.monotonic() + CHALLENGE_TIMEOUT
                while is_challenge(page.title(), page.content()):
                    if time.monotonic() > deadline:
                        status = loads[-1] if loads else None
                        raise Blocked("Challenge page didn't clear.", status)
                    page.wait_for_timeout(1000)
                status = loads[-1] if loads else None
                if status in BLOCKED_STATUSES:
                    raise Blocked(f"HTTP {status}", status)

                head = page.screenshot(type="png")
                height = page.evaluate(
                    SCROLL_JS, [SCROLL_STEP, int(SCROLL_PAUSE * 1000), MAX_HEIGHT]
                )
                try:
                    page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT)
                except TimeoutError:
                    pass
                clip = None
                if height > MAX_HEIGHT:
                    clip = {
                        "x": 0,
                        "y": 0,
                        "width": VIEWPORT["width"],
                        "height": MAX_HEIGHT,
                    }
                full = page.screenshot(type="png", full_page=True, clip=clip)
                return Visit(
                    url=page.url,
                    status=status,
                    html=page.content(),
                    head=head,
                    full=full,
                )
            finally:
                browser.close()
    except BrowserError:
        raise
    except Exception as e:
        # Playwright's Error, and plain Exceptions from its driver.
        message = str(e).splitlines()[0] if str(e) else type(e).__name__
        raise BrowserError(message) from e
