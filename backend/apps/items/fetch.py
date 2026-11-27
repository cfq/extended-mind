import re
import uuid
from datetime import date
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import courlan
import httpx2
import trafilatura
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from apps.items import browser, cleanup, image_items, images, meta, steps, tagging
from apps.items.models import Item, ItemSource, ItemStepRun, ItemTag, PageItem
from apps.items.sources import save_source

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
    A body for HTML pages and images only."""
    with httpx2.Client(
        follow_redirects=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    ) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            final_url = str(response.url)
            content_type = response.headers.get("content-type", "")
            mime = content_type.split(";")[0].strip().lower()
            if mime not in HTML_TYPES | image_items.MIME_TYPES:
                return Download(final_url, mime, None, None, response.status_code)
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FetchError("Larger than 50 MB.")
            return Download(
                final_url, mime, response.encoding, bytes(body), response.status_code
            )


def source_filename(item: Item, title: str, description: str) -> str:
    # slugify drops URL punctuation; make it word breaks: example.com/a → example-com-a
    url = re.sub(r"[^\w-]+", " ", re.sub(r"^https?://", "", item.url))
    slug = slugify(title or description or url)[:60].strip("-")
    return f"{slug}-{item.short_id}.html" if slug else f"{item.short_id}.html"


def parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def ensure_page(item: Item) -> PageItem:
    try:
        return item.page
    except PageItem.DoesNotExist:
        page = PageItem(item=item)
        page.save()
        return page


def extract(item: Item, html: str | bytes) -> list[str]:
    """Fills the item's content and metadata from a page's HTML, on the
    item and its page (unsaved). Returns the tags the page declares."""
    page = item.page
    page.meta = meta.parse(html)
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
    item.site_name = (metadata and metadata.sitename) or ""
    item.published_at = parse_date(metadata and metadata.date)
    page.author = (metadata and metadata.author) or ""
    page.markdown = cleanup.clean_markdown(markdown, item.url)
    text = trafilatura.extract(html, url=item.url, output_format="txt") or ""
    page.text = cleanup.clean_text(text)
    if not metadata:
        return []
    return tagging.page_tags(metadata.categories, metadata.tags)


Outcome = ItemStepRun.Outcome


def fetch_http(item: Item, run_id: uuid.UUID) -> tuple[Download, steps.Run] | None:
    """None if blocked (the browser may get through). Raises on other
    failures, and for content that's neither a page nor an image."""
    with steps.run(item, "fetch_http", run_id) as run:
        try:
            result = download(item.url)
        except httpx2.HTTPStatusError as e:
            status = e.response.status_code
            outcome = Outcome.BLOCKED if status in BLOCKED_STATUSES else Outcome.FAILED
            run.finish(outcome, f"HTTP {status}", http_status=status)
            if outcome == Outcome.BLOCKED:
                return None
            raise
        run.note(http_status=result.status, final_url=result.url, mime=result.mime)
        if result.body is None:
            message = f"Not a page or an image: {result.mime or 'no type'}."
            run.finish(Outcome.NO_CONTENT, message)
            raise FetchError(message)
        return result, run


def fetch_browser(
    item: Item, url: str, run_id: uuid.UUID
) -> tuple[browser.Visit, steps.Run] | None:
    """None if the browser is off, blocked or failed."""
    if not settings.BROWSER_URL:
        return None
    with steps.run(item, "fetch_browser", run_id) as run:
        try:
            visit = browser.visit(url)
        except browser.Blocked as e:
            run.finish(Outcome.BLOCKED, str(e), http_status=e.status)
            return None
        except browser.BrowserError as e:
            run.finish(Outcome.FAILED, str(e))
            return None
        message = "" if visit.consent == "none" else f"Cookie banner {visit.consent}."
        run.finish(
            Outcome.OK,
            message,
            http_status=visit.status,
            final_url=visit.url,
            consent=visit.consent,
            pdf=visit.pdf is not None,
        )
        return visit, run


def fetch(item: Item, run_id: uuid.UUID):
    """Plain HTTP first. Images become image items. HTML pages (or
    blocked ones) then go through the browser for the rendered page and
    screenshots. Extracts from the plain HTML, falling back to the
    rendered one. Every step and try is recorded."""
    fetched = fetch_http(item, run_id)
    http, http_run = fetched if fetched else (None, None)
    if http and http.mime in image_items.MIME_TYPES:
        item.url = clean_url(http.url)
        item.fetched_at = timezone.now()
        name = image_items.name_from_url(http.url)
        image_items.make_image(item, name, http.url, http.body, run_id)
        image_items.dimensions(item, run_id)
        return

    if settings.BROWSER_URL:
        steps.need(item, "fetch_browser")
    if http:
        steps.need(item, "extract")
    browsed = fetch_browser(item, http.url if http else item.url, run_id)
    visit, browser_run = browsed if browsed else (None, None)
    if not http and not visit:
        raise FetchError("Couldn't get the page.")

    item.type = Item.Type.PAGE
    item.url = clean_url(http.url if http else visit.url)
    ensure_page(item)

    # Plain first: sites often send the full article, then scripts add
    # consent dialogs and cut it at the paywall. The rendered page is for
    # pages built by JavaScript, where the plain one has no article.
    candidates = []
    if http:
        html = http.body.decode(http.encoding or "utf-8", errors="replace")
        candidates.append((html, "html"))
    if visit:
        candidates.append((visit.html, "rendered"))
    tags = None
    for html, source in candidates:
        with steps.run(item, "extract", run_id) as run:
            try:
                tags = extract(item, html)
            except FetchError as e:
                run.finish(Outcome.NO_CONTENT, str(e), source=source)
                continue
            run.note(source=source, words=len(item.page.text.split()))
            break
    if tags is None:
        item.save()
        raise FetchError("No article content found.")

    if http:
        name = file_stem(item)
        save_source(
            item,
            ItemSource.Kind.HTML,
            f"{name}.html",
            http.url,
            http.mime,
            http.body,
            http_run.row,
        )
    if visit:
        save_visit(item, visit, browser_run)
    item.fetched_at = timezone.now()
    item.save()
    item.page.save()
    extracted(item, tags)


def extracted(item: Item, tags: list[str]):
    tagging.add_tags(item, tags, ItemTag.Source.PAGE)
    # Known now: the article's images, its sharing image, model tags.
    steps.need(item, "images", "og_image", "tag")


def file_stem(item: Item) -> str:
    return source_filename(item, item.title, item.description).removesuffix(".html")


def save_visit(item: Item, visit: browser.Visit, run: steps.Run):
    """The browser's rendered page, screenshots and PDF."""
    name, kinds, row = file_stem(item), ItemSource.Kind, run.row
    save_source(
        item,
        kinds.RENDERED,
        f"{name}-rendered.html",
        visit.url,
        "text/html",
        visit.html.encode(),
        row,
    )
    save_source(
        item,
        kinds.SCREENSHOT_FULL,
        f"{name}-full.png",
        visit.url,
        "image/png",
        visit.full,
        row,
    )
    save_source(
        item,
        kinds.SCREENSHOT_HEAD,
        f"{name}-head.png",
        visit.url,
        "image/png",
        visit.head,
        row,
    )
    if visit.pdf:
        save_source(
            item,
            kinds.PDF,
            f"{name}.pdf",
            visit.url,
            "application/pdf",
            visit.pdf,
            row,
        )


# Single steps again, for retries and reextract.


def browse(item: Item, run_id: uuid.UUID):
    """A new browser visit: rendered page, screenshots, PDF."""
    browsed = fetch_browser(item, item.url, run_id)
    if browsed:
        save_visit(item, *browsed)


def extract_saved(item: Item, run_id: uuid.UUID) -> list[str]:
    """Extraction again from the saved HTML, plain first, then rendered.
    Saves the item and its page tags. Raises FetchError with each saved
    page's problem."""
    order = [ItemSource.Kind.HTML, ItemSource.Kind.RENDERED]
    sources = sorted(
        item.sources.filter(kind__in=order), key=lambda s: order.index(s.kind)
    )
    item.type = Item.Type.PAGE
    ensure_page(item)
    if not sources:
        with steps.run(item, "extract", run_id):
            raise FetchError("No saved page.")
    errors = []
    for source in sources:
        with steps.run(item, "extract", run_id) as run:
            try:
                # Bytes: trafilatura detects the encoding itself.
                tags = extract(item, source.path.read_bytes())
            except OSError as e:
                run.finish(Outcome.FAILED, str(e), source=source.kind)
            except FetchError as e:
                run.finish(Outcome.NO_CONTENT, str(e), source=source.kind)
            else:
                run.note(source=source.kind)
                item.save()
                item.page.save()
                extracted(item, tags)
                return tags
        errors.append(f"{source.kind}: {run.row.message}")
    raise FetchError("; ".join(errors))
