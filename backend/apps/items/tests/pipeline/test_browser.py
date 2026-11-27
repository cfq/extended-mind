import struct

import httpx2
import pytest
from django.core.management import call_command

from apps.items import ids
from apps.items.models import Item, ItemSource, ItemStepRun, PageItem
from apps.items.pipeline import browser, download, flow, steps
from apps.items.pipeline.download import FetchError

Kind = ItemSource.Kind
Outcome = ItemStepRun.Outcome
URL = "https://x.test/post"


def article(words: str) -> str:
    body = f"<p>{words} " * 40
    head = f"<head><title>{words}</title></head>"
    return f"<html>{head}<body><article>{body}</article></body></html>"


PLAIN = article("Plain fetch text about cities")
RENDERED = article("Rendered page text about rivers")
EMPTY = "<html><body></body></html>"
PNG_FULL, PNG_HEAD = b"\x89PNG full", b"\x89PNG head"
PDF = b"%PDF-1.4 page"


@pytest.fixture
def page(user):
    return Item.objects.create(user=user, url=URL, url_submitted=URL)


@pytest.fixture
def http(monkeypatch):
    """http(body) serves HTML; http(status=403) fails with that status."""

    def use(body: str | None = PLAIN, status: int = 200, mime: str = "text/html"):
        def fake_download(url):
            if status >= 400:
                request = httpx2.Request("GET", url)
                response = httpx2.Response(status, request=request)
                raise httpx2.HTTPStatusError("x", request=request, response=response)
            return download.Download(
                URL, mime, "utf-8", body.encode() if body is not None else None, status
            )

        monkeypatch.setattr(download, "download", fake_download)

    return use


@pytest.fixture
def chrome(settings, monkeypatch):
    """chrome(html) makes browser visits return html; chrome(error=...) raises."""
    settings.BROWSER_URL = "ws://browser.test/"
    visits = []

    def use(
        html: str = RENDERED, error: Exception | None = None, pdf: bytes | None = PDF
    ):
        def visit(url):
            visits.append(url)
            if error:
                raise error
            return browser.Visit(
                url=url, status=200, html=html, head=PNG_HEAD, full=PNG_FULL, pdf=pdf
            )

        monkeypatch.setattr(browser, "visit", visit)
        return visits

    return use


def go(item):
    """A pass through the pipeline, as fetch_item runs it."""
    flow.fetch(item, steps.new_run_id())
    item.refresh_from_db()


def attempts(item):
    """(step, outcome, HTTP status) of every run, in order."""
    runs = ItemStepRun.objects.filter(step__item=item).order_by("started_at", "id")
    return [(r.step.name, r.outcome, r.meta.get("http_status")) for r in runs]


def text(item):
    return PageItem.objects.get(item=item).text


def status(item):
    return steps.status(Item.objects.get(pk=item.pk))


def sources(item):
    return {s.kind: s.filename for s in item.sources.all()}


def test_html_page_goes_through_browser(page, http, chrome, item_sources_dir):
    http()
    chrome()

    go(page)

    page.refresh_from_db()
    assert "cities" in text(page)
    assert attempts(page) == [
        ("fetch_http", "ok", 200),
        ("fetch_browser", "ok", 200),
        ("extract", "ok", None),
    ]
    name = f"plain-fetch-text-about-cities-{page.short_id}"
    assert sources(page) == {
        Kind.HTML: f"{name}.html",
        Kind.RENDERED: f"{name}-rendered.html",
        Kind.SCREENSHOT_FULL: f"{name}-full.png",
        Kind.SCREENSHOT_HEAD: f"{name}-head.png",
        Kind.PDF: f"{name}.pdf",
    }
    assert (page.sources_dir / f"{name}-full.png").read_bytes() == PNG_FULL
    assert (page.sources_dir / f"{name}.pdf").read_bytes() == PDF
    assert (page.sources_dir / f"{name}.html").read_text() == PLAIN


def test_browser_failure_falls_back_to_plain_html(page, http, chrome, item_sources_dir):
    http()
    chrome(error=browser.BrowserError("Target closed"))

    go(page)

    assert "cities" in text(page)
    assert attempts(page) == [
        ("fetch_http", "ok", 200),
        ("fetch_browser", "failed", None),
        ("extract", "ok", None),
    ]
    run = ItemStepRun.objects.get(step__item=page, step__name="fetch_browser")
    assert run.message == "Target closed"
    assert set(sources(page)) == {Kind.HTML}


def test_plain_without_content_falls_back_to_rendered(
    page, http, chrome, item_sources_dir
):
    http(EMPTY)
    chrome()

    go(page)

    assert "rivers" in text(page)
    assert attempts(page) == [
        ("fetch_http", "ok", 200),
        ("fetch_browser", "ok", 200),
        ("extract", "no_content", None),
        ("extract", "ok", None),
    ]


def test_neither_has_content(page, http, chrome, item_sources_dir):
    http(EMPTY)
    chrome(EMPTY)

    with pytest.raises(FetchError):
        go(page)

    assert attempts(page) == [
        ("fetch_http", "ok", 200),
        ("fetch_browser", "ok", 200),
        ("extract", "no_content", None),
        ("extract", "no_content", None),
    ]
    assert status(page) == (Item.Status.FAILED, "No article content found.")


def test_blocked_plain_fetch_tries_browser(page, http, chrome, item_sources_dir):
    http(status=403)
    chrome()

    go(page)

    assert status(page)[0] == Item.Status.DONE
    assert attempts(page) == [
        ("fetch_http", "blocked", 403),
        ("fetch_browser", "ok", 200),
        ("extract", "ok", None),
    ]
    assert Kind.HTML not in sources(page)
    assert Kind.RENDERED in sources(page)


def test_blocked_everywhere_fails_and_logs(page, http, chrome, item_sources_dir):
    http(status=403)
    chrome(error=browser.Blocked("Challenge page didn't clear.", 403))

    with pytest.raises(FetchError):
        go(page)

    assert attempts(page) == [
        ("fetch_http", "blocked", 403),
        ("fetch_browser", "blocked", 403),
    ]
    assert status(page) == (Item.Status.FAILED, "Challenge page didn't clear.")


def test_not_found_fails_without_browser(page, http, chrome, item_sources_dir):
    http(status=404)
    visits = chrome()

    with pytest.raises(httpx2.HTTPStatusError):
        go(page)

    assert attempts(page) == [("fetch_http", "failed", 404)]
    assert visits == []
    assert status(page) == (Item.Status.FAILED, "HTTP 404")


def test_not_html_or_image_fails_without_browser(page, http, chrome, item_sources_dir):
    http(body=None, mime="application/pdf")
    visits = chrome()

    with pytest.raises(FetchError):
        go(page)

    assert visits == []
    assert attempts(page) == [("fetch_http", "no_content", 200)]
    message = "Not a page or an image: application/pdf."
    assert status(page) == (Item.Status.FAILED, message)


def test_no_browser_configured(page, http, item_sources_dir):
    http()

    go(page)

    assert attempts(page) == [("fetch_http", "ok", 200), ("extract", "ok", None)]
    assert set(sources(page)) == {Kind.HTML}


def test_retry_replaces_files_and_adds_attempts(page, http, chrome, item_sources_dir):
    http()
    chrome()
    go(page)
    go(page)

    assert page.sources.count() == 5
    assert len(list(page.sources_dir.iterdir())) == 5
    assert len(attempts(page)) == 6
    assert len({r.run_id for r in ItemStepRun.objects.filter(step__item=page)}) == 2


def test_api_links_and_serves_screenshots(
    user_client, page, http, chrome, item_sources_dir
):
    http()
    chrome()
    go(page)
    base = f"/api/v1/items/{ids.encode(page.id)}"

    screenshots = user_client.get(base).json()["page"]["screenshots"]

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

    assert response.json()["page"]["screenshots"] == {"full": None, "head": None}
    assert response.json()["page"]["pdf"] is None


def test_api_serves_pdf(user_client, page, http, chrome, item_sources_dir):
    http()
    chrome()
    go(page)
    base = f"/api/v1/items/{ids.encode(page.id)}"

    pdf = user_client.get(base).json()["page"]["pdf"]

    assert pdf == f"{base}/sources/{sources(page)[Kind.PDF]}"
    response = user_client.get(pdf)
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content) == PDF


def test_no_pdf_when_printing_failed(page, http, chrome, item_sources_dir):
    http()
    chrome(pdf=None)

    go(page)

    page.refresh_from_db()
    assert status(page)[0] == Item.Status.DONE
    assert Kind.PDF not in sources(page)
    assert Kind.SCREENSHOT_FULL in sources(page)


def test_reextract_plain_first_then_rendered(page, http, chrome, item_sources_dir, app):
    http()
    chrome()
    go(page)
    page.page.text = ""
    page.page.save()

    call_command("reextract")
    page.refresh_from_db()
    assert "cities" in text(page)

    page.sources.get(kind=Kind.HTML).path.write_text(EMPTY)
    call_command("reextract")
    page.refresh_from_db()
    assert "rivers" in text(page)


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

    assert png_size(visit.head) == (2560, 2560)
    assert png_size(visit.full) == (2560, 40000)
    assert visit.pdf.startswith(b"%PDF")
    assert "tall" in visit.html


def test_live_dismisses_cookie_banner(live_browser):
    # A OneTrust banner, one of the consent managers autoconsent knows.
    banner = (
        "data:text/html,<body><p>Article</p>"
        "<div id='onetrust-consent-sdk'><div id='onetrust-banner-sdk' "
        "style='position:fixed;bottom:0;width:100%;height:200px;background:red'>"
        "<button id='onetrust-accept-btn-handler'>Accept</button>"
        "<button id='onetrust-reject-all-handler' onclick="
        "\"document.getElementById('onetrust-consent-sdk').remove()\">Reject"
        "</button></div></div></body>"
    )

    visit = browser.visit(banner)

    assert visit.consent == "dismissed"
    assert "onetrust-banner-sdk" not in visit.html


def test_live_no_banner(live_browser):
    assert browser.visit("data:text/html,<p>Article</p>").consent == "none"
