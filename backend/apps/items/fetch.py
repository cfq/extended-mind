import hashlib
import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import courlan
import httpx2
import trafilatura
from django.utils import timezone
from django.utils.text import slugify

from apps.items import images, tagging
from apps.items.models import Item, ItemSource, ItemTag

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"
)
TIMEOUT = 60
MAX_BYTES = 50 * 1024 * 1024
HTML_TYPES = {"text/html", "application/xhtml+xml"}

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


def download(url: str) -> tuple[str, str, str | None, bytes | None]:
    """Returns final URL, mime type, encoding and body. No body if not HTML."""
    with httpx2.Client(
        follow_redirects=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    ) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            final_url = str(response.url)
            content_type = response.headers.get("content-type", "")
            mime = content_type.split(";")[0].strip().lower()
            if mime not in HTML_TYPES:
                return final_url, mime, None, None
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FetchError("Page is larger than 50 MB.")
            return final_url, mime, response.encoding, bytes(body)


def source_filename(item: Item, title: str, description: str) -> str:
    # slugify drops URL punctuation; make it word breaks: example.com/a → example-com-a
    url = re.sub(r"[^\w-]+", " ", re.sub(r"^https?://", "", item.url))
    slug = slugify(title or description or url)[:60].strip("-")
    return f"{slug}-{item.short_id}.html" if slug else f"{item.short_id}.html"


def save_html_source(item: Item, url: str, mime: str, body: bytes, filename: str):
    # A retry replaces the previous download.
    for old in item.sources.filter(kind=ItemSource.Kind.HTML):
        old.path.unlink(missing_ok=True)
        old.delete()
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    ItemSource.objects.create(
        item=item,
        kind=ItemSource.Kind.HTML,
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
    item.markdown = markdown
    item.text = trafilatura.extract(html, url=item.url, output_format="txt") or ""
    if not metadata:
        return []
    return tagging.page_tags(metadata.categories, metadata.tags)


def fetch(item: Item):
    final_url, mime, encoding, body = download(item.url)
    item.url = clean_url(final_url)

    tags = []
    if body is not None:
        html = body.decode(encoding or "utf-8", errors="replace")
        tags = extract(item, html)
        filename = source_filename(item, item.title, item.description)
        save_html_source(item, final_url, mime, body, filename)

    item.status = Item.Status.DONE
    item.error = ""
    item.fetched_at = timezone.now()
    item.save()
    tagging.add_tags(item, tags, ItemTag.Source.PAGE)
