import hashlib
import re
from datetime import date
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import courlan
import httpx2
import trafilatura
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from apps.items import browser, cleanup, images, tagging
from apps.items.models import FetchAttempt, Item, ItemSource, ItemTag

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"
)
TIMEOUT = 60
MAX_BYTES = 50 * 1024 * 1024
HTML_TYPES = {"text/html", "application/xhtml+xml"}
# Bot walls answer with these; the browser may still get through.
BLOCKED_STATUSES = {401, 403, 429, 503}

# On top of what courlan strips (utm_* etc.).
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "igsh",
    "si",
    "mc_cid",
    "mc_eid",
}


class FetchError(Exception):
    pass


def clean_url(url: str) -> str:
    try:
        url = courlan.normalize_url(url, strict=True)
    except Exception:
        pass
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


class Download(NamedTuple):
    url: str
    mime: str
    encoding: str | None
    # None if not HTML.
    body: bytes | None
    status: int


def download(url: str) -> Download:
    """Final URL after redirects, mime type, encoding, body and status.
    No body if not HTML."""
    with httpx2.Client(
        follow_redirects=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    ) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            final_url = str(response.url)
            content_type = response.headers.get("content-type", "")
            mime = content_type.split(";")[0].strip().lower()
            if mime not in HTML_TYPES:
                return Download(final_url, mime, None, None, response.status_code)
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FetchError("Page is larger than 50 MB.")
            return Download(
                final_url, mime, response.encoding, bytes(body), response.status_code
            )


def source_filename(item: Item, title: str, description: str) -> str:
    # slugify drops URL punctuation; make it word breaks: example.com/a → example-com-a
    url = re.sub(r"[^\w-]+", " ", re.sub(r"^https?://", "", item.url))
    slug = slugify(title or description or url)[:60].strip("-")
    return f"{slug}-{item.short_id}.html" if slug else f"{item.short_id}.html"


def save_source(item: Item, kind: str, filename: str, url: str, mime: str, body):
    # A retry replaces the previous file of this kind.
    for old in item.sources.filter(kind=kind):
        old.path.unlink(missing_ok=True)
        old.delete()
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    ItemSource.objects.create(
        item=item,
        kind=kind,
        filename=filename,
        url=url,
        mime=mime,
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )


def parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def extract(item: Item, html: str | bytes) -> list[str]:
    """Fills the item's content and metadata from a page's HTML.
    Returns the tags the page declares."""
    html = images.tidy_html(html, item.url)
    markdown = trafilatura.extract(
        html,
        url=item.url,
        output_format="markdown",
        include_links=True,
        include_formatting=True,
        include_images=True,
    )
    if not markdown:
        raise FetchError("No article content found.")
    metadata = trafilatura.extract_metadata(html, default_url=item.url)
    item.title = (metadata and metadata.title) or ""
    item.description = (metadata and metadata.description) or ""
    item.author = (metadata and metadata.author) or ""
    item.site_name = (metadata and metadata.sitename) or ""
    item.published_at = parse_date(metadata and metadata.date)
    item.markdown = cleanup.clean_markdown(markdown, item.url)
    text = trafilatura.extract(html, url=item.url, output_format="txt") or ""
    item.text = cleanup.clean_text(text)
    if not metadata:
        return []
    return tagging.page_tags(metadata.categories, metadata.tags)


class Attempt:
    """A FetchAttempt row being filled in; saved at the end of the fetch."""

    def __init__(self, item: Item, method: str):
        self.row = FetchAttempt(item=item, method=method, started_at=timezone.now())

    def finish(self, outcome: str, status: int | None = None, message: str = ""):
        self.row.finished_at = timezone.now()
        self.row.outcome = outcome
        self.row.http_status = status
        self.row.message = message


def fetch_http(item: Item, attempts: list[Attempt]) -> Download | None:
    """None if blocked (the browser may get through). Raises on other failures."""
    attempt = Attempt(item, FetchAttempt.Method.HTTP)
    attempts.append(attempt)
    try:
        result = download(item.url)
    except httpx2.HTTPStatusError as e:
        status = e.response.status_code
        if status in BLOCKED_STATUSES:
            attempt.finish(FetchAttempt.Outcome.BLOCKED, status, f"HTTP {status}")
            return None
        attempt.finish(FetchAttempt.Outcome.ERROR, status, f"HTTP {status}")
        raise
    except Exception as e:
        attempt.finish(FetchAttempt.Outcome.ERROR, message=str(e) or type(e).__name__)
        raise
    attempt.finish(FetchAttempt.Outcome.OK, result.status)
    return result


def fetch_browser(item: Item, url: str, attempts: list[Attempt]):
    """None if the browser is off, blocked or failed."""
    if not settings.BROWSER_URL:
        return None
    attempt = Attempt(item, FetchAttempt.Method.BROWSER)
    attempts.append(attempt)
    try:
        visit = browser.visit(url)
    except browser.Blocked as e:
        attempt.finish(FetchAttempt.Outcome.BLOCKED, e.status, str(e))
        return None
    except browser.BrowserError as e:
        attempt.finish(FetchAttempt.Outcome.ERROR, message=str(e))
        return None
    message = "" if visit.consent == "none" else f"Cookie banner {visit.consent}."
    attempt.finish(FetchAttempt.Outcome.OK, visit.status, message)
    return visit, attempt


def fetch(item: Item):
    """Plain HTTP first; HTML pages (or blocked ones) then through the
    browser for the rendered page and screenshots. Extracts from the
    plain HTML, falling back to the rendered one. Every try is logged."""
    attempts: list[Attempt] = []
    try:
        fetch_into(item, attempts)
    finally:
        FetchAttempt.objects.bulk_create(a.row for a in attempts)


def fetch_into(item: Item, attempts: list[Attempt]):
    http = fetch_http(item, attempts)
    if http is not None and http.body is None:
        # Not a page (PDF, image): nothing to render or extract yet.
        item.url = clean_url(http.url)
        finish(item, [])
        return

    browsed = fetch_browser(item, http.url if http else item.url, attempts)
    visit, browser_attempt = browsed if browsed else (None, None)

    # Plain first: sites often send the full article, then scripts add
    # consent dialogs and cut it at the paywall. The rendered page is for
    # pages built by JavaScript, where the plain one has no article.
    candidates = []
    if http:
        html = http.body.decode(http.encoding or "utf-8", errors="replace")
        candidates.append((html, attempts[0]))
    if visit:
        candidates.append((visit.html, browser_attempt))
    if not candidates:
        raise FetchError(attempts[-1].row.message or "Couldn't get the page.")

    item.url = clean_url(http.url if http else visit.url)
    tags = None
    for html, attempt in candidates:
        try:
            tags = extract(item, html)
            break
        except FetchError as e:
            attempt.row.outcome = FetchAttempt.Outcome.NO_CONTENT
            attempt.row.message = str(e)
    if tags is None:
        raise FetchError("No article content found.")

    name = source_filename(item, item.title, item.description).removesuffix(".html")
    if http:
        save_source(
            item, ItemSource.Kind.HTML, f"{name}.html", http.url, http.mime, http.body
        )
    if visit:
        kinds = ItemSource.Kind
        save_source(
            item,
            kinds.RENDERED,
            f"{name}-rendered.html",
            visit.url,
            "text/html",
            visit.html.encode(),
        )
        save_source(
            item,
            kinds.SCREENSHOT_FULL,
            f"{name}-full.png",
            visit.url,
            "image/png",
            visit.full,
        )
        save_source(
            item,
            kinds.SCREENSHOT_HEAD,
            f"{name}-head.png",
            visit.url,
            "image/png",
            visit.head,
        )
    finish(item, tags)


def finish(item: Item, tags: list[str]):
    item.status = Item.Status.DONE
    item.error = ""
    item.fetched_at = timezone.now()
    item.save()
    tagging.add_tags(item, tags, ItemTag.Source.PAGE)
