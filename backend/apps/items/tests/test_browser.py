import struct

import httpx2
import pytest
from django.core.management import call_command

from apps.items import browser, fetch, ids
from apps.items.models import FetchAttempt, Item, ItemSource

Kind = ItemSource.Kind
Outcome = FetchAttempt.Outcome
URL = "https://x.test/post"


def article(words: str) -> str:
    body = f"<p>{words} " * 40
    head = f"<head><title>{words}</title></head>"
    return f"<html>{head}<body><article>{body}</article></body></html>"


PLAIN = article("Plain fetch text about cities")
RENDERED = article("Rendered page text about rivers")
EMPTY = "<html><body></body></html>"
PNG_FULL, PNG_HEAD = b"\x89PNG full", b"\x89PNG head"


@pytest.fixture
def page(user):
    return Item.objects.create(user=user, url=URL, url_submitted=URL)


@pytest.fixture
def http(monkeypatch):
    """http(body) serves HTML; http(status=403) fails with that status."""

    def use(body: str | None = PLAIN, status: int = 200, mime: str = "text/html"):
        def download(url):
            if status >= 400:
                request = httpx2.Request("GET", url)
                response = httpx2.Response(status, request=request)
                raise httpx2.HTTPStatusError("x", request=request, response=response)
            return fetch.Download(
                URL, mime, "utf-8", body.encode() if body is not None else None, status
            )

        monkeypatch.setattr(fetch, "download", download)

    return use


@pytest.fixture
def chrome(settings, monkeypatch):
    """chrome(html) makes browser visits return html; chrome(error=...) raises."""
    settings.BROWSER_URL = "ws://browser.test/"
    visits = []

    def use(html: str = RENDERED, error: Exception | None = None):
        def visit(url):
            visits.append(url)
            if error:
                raise error
            return browser.Visit(
                url=url, status=200, html=html, head=PNG_HEAD, full=PNG_FULL
            )

        monkeypatch.setattr(browser, "visit", visit)
        return visits

    return use


def attempts(item):
    return [
        (a.method, a.outcome, a.http_status)
        for a in item.fetch_attempts.order_by("started_at", "id")
    ]


def sources(item):
    return {s.kind: s.filename for s in item.sources.all()}


def test_html_page_goes_through_browser(page, http, chrome, item_sources_dir):
    http()
    chrome()

    fetch.fetch(page)

    page.refresh_from_db()
    assert "rivers" in page.text
    assert attempts(page) == [("http", "ok", 200), ("browser", "ok", 200)]
    name = f"rendered-page-text-about-rivers-{page.short_id}"
    assert sources(page) == {
        Kind.HTML: f"{name}.html",
        Kind.RENDERED: f"{name}-rendered.html",
        Kind.SCREENSHOT_FULL: f"{name}-full.png",
        Kind.SCREENSHOT_HEAD: f"{name}-head.png",
    }
    assert (page.sources_dir / f"{name}-full.png").read_bytes() == PNG_FULL
    assert (page.sources_dir / f"{name}.html").read_text() == PLAIN


def test_browser_failure_falls_back_to_plain_html(page, http, chrome, item_sources_dir):
    http()
    chrome(error=browser.BrowserError("Target closed"))

    fetch.fetch(page)

    assert "cities" in page.text
    assert attempts(page) == [("http", "ok", 200), ("browser", "error", None)]
    assert page.fetch_attempts.get(method="browser").message == "Target closed"
    assert set(sources(page)) == {Kind.HTML}


def test_rendered_without_content_falls_back(page, http, chrome, item_sources_dir):
    http()
    chrome(EMPTY)

    fetch.fetch(page)

    assert "cities" in page.text
    assert attempts(page) == [("http", "ok", 200), ("browser", "no_content", 200)]


def test_blocked_plain_fetch_tries_browser(page, http, chrome, item_sources_dir):
    http(status=403)
    chrome()

    fetch.fetch(page)

    assert page.status == Item.Status.DONE
    assert attempts(page) == [("http", "blocked", 403), ("browser", "ok", 200)]
    assert Kind.HTML not in sources(page)
    assert Kind.RENDERED in sources(page)


def test_blocked_everywhere_fails_and_logs(page, http, chrome, item_sources_dir):
    http(status=403)
    chrome(error=browser.Blocked("Challenge page didn't clear.", 403))

    with pytest.raises(fetch.FetchError, match="Challenge page"):
        fetch.fetch(page)

    assert attempts(page) == [("http", "blocked", 403), ("browser", "blocked", 403)]


def test_not_found_fails_without_browser(page, http, chrome, item_sources_dir):
    http(status=404)
    visits = chrome()

    with pytest.raises(httpx2.HTTPStatusError):
        fetch.fetch(page)

    assert attempts(page) == [("http", "error", 404)]
    assert visits == []


def test_not_html_skips_browser(page, http, chrome, item_sources_dir):
    http(body=None, mime="application/pdf")
    visits = chrome()

    fetch.fetch(page)

    assert visits == []
    assert attempts(page) == [("http", "ok", 200)]


def test_no_browser_configured(page, http, item_sources_dir):
    http()

    fetch.fetch(page)

    assert attempts(page) == [("http", "ok", 200)]
    assert set(sources(page)) == {Kind.HTML}


def test_retry_replaces_files_and_adds_attempts(page, http, chrome, item_sources_dir):
    http()
    chrome()
    fetch.fetch(page)
    fetch.fetch(page)

    assert page.sources.count() == 4
    assert len(list(page.sources_dir.iterdir())) == 4
    assert len(attempts(page)) == 4


def test_api_links_and_serves_screenshots(
    user_client, page, http, chrome, item_sources_dir
):
    http()
    chrome()
    fetch.fetch(page)
    base = f"/api/v1/items/{ids.encode(page.id)}"

    screenshots = user_client.get(base).json()["screenshots"]

    assert screenshots == {
        "full": f"{base}/sources/{sources(page)[Kind.SCREENSHOT_FULL]}",
        "head": f"{base}/sources/{sources(page)[Kind.SCREENSHOT_HEAD]}",
    }
    response = user_client.get(screenshots["full"])
    assert response["Content-Type"] == "image/png"
    assert b"".join(response.streaming_content) == PNG_FULL
    rendered = sources(page)[Kind.RENDERED]
    assert user_client.get(f"{base}/sources/{rendered}").status_code == 404


def test_api_screenshots_null_without_them(user_client, item):
    response = user_client.get(f"/api/v1/items/{ids.encode(item.id)}")

    assert response.json()["screenshots"] == {"full": None, "head": None}


def test_reextract_prefers_rendered(page, http, chrome, item_sources_dir, app):
    http()
    chrome()
    fetch.fetch(page)
    page.text = ""
    page.save()

    call_command("reextract")

    page.refresh_from_db()
    assert "rivers" in page.text


@pytest.mark.parametrize(
    "title, html, challenge",
    [
        ("Just a moment...", "<html></html>", True),
        ("Vercel Security Checkpoint", "<html></html>", True),
        ("News", "<p>Checking your browser before accessing</p>", True),
        ("News", '<script src="/cdn-cgi/challenge-platform/x.js"></script>', False),
        ("News", "<p>An article</p>", False),
    ],
)
def test_is_challenge(title, html, challenge):
    assert browser.is_challenge(title, html) is challenge


# Against the real browser container; skipped when it isn't reachable.


def png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])


@pytest.fixture
def live_browser(settings):
    settings.BROWSER_URL = "ws://browser:3000/"
    try:
        browser.visit("data:text/html,<p>ping</p>")
    except browser.BrowserError as e:
        pytest.skip(f"browser not reachable: {e}")


def test_live_blocked_status(live_browser, monkeypatch):
    monkeypatch.setattr(browser, "CHALLENGE_TITLES", ())
    monkeypatch.setattr(browser, "CHALLENGE_TEXT", ())

    # An outside site; skipped if it can't be reached.
    try:
        browser.visit("https://httpbin.org/status/403")
    except browser.Blocked as blocked:
        assert blocked.status == 403
    except browser.BrowserError as e:
        pytest.skip(f"httpbin.org not reachable: {e}")
    else:
        pytest.fail("not blocked")


def test_live_screenshots_sizes(live_browser):
    tall = (
        "data:text/html,<body style='margin:0'><div style='height:30000px'>tall</div>"
    )

    visit = browser.visit(tall)

    assert png_size(visit.head) == (1280, 1280)
    assert png_size(visit.full) == (1280, 20000)
    assert "tall" in visit.html
