"""Article images: kept through extraction, downloaded, and the
article's markdown pointed at the local copies."""

import hashlib
import logging
import mimetypes
import re
from urllib.parse import unquote, urlsplit

import httpx2
import trafilatura
from django.utils.text import slugify
from lxml import html as lxml_html

from apps.items import cleanup, ids
from apps.items.models import Item, ItemSource

log = logging.getLogger(__name__)

TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024
MAX_IMAGES = 100
# srcset: the candidate closest to this width, preferring wider.
TARGET_WIDTH = 1600
# A 1x candidate with no width, roughly.
X_WIDTH = 800
LAZY_SRC = ("data-src", "data-lazy-src", "data-original")
LAZY_SRCSET = ("data-srcset", "data-lazy-srcset")

# ![alt](url) or ![alt](url "title")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\((\S+?)(?:\s+\"[^\"]*\")?\)")

EXTENSIONS = {"image/jpeg": ".jpg", "image/svg+xml": ".svg"}


# HTML tidying, before extraction.


def parse_srcset(srcset: str) -> list[tuple[str, float]]:
    """[(url, width)]. URLs can contain commas (Substack's do), so
    candidates are split on a comma followed by whitespace."""
    candidates = []
    for part in re.split(r",\s+", srcset.strip()):
        bits = part.strip().rstrip(",").split()
        if not bits:
            continue
        width = float(X_WIDTH)
        if len(bits) > 1:
            descriptor = bits[-1]
            try:
                if descriptor.endswith("w"):
                    width = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    width = float(descriptor[:-1]) * X_WIDTH
            except ValueError:
                pass
        candidates.append((bits[0], width))
    return candidates


def best_source(candidates: list[tuple[str, float]]) -> str | None:
    if not candidates:
        return None
    wide = [c for c in candidates if c[1] >= TARGET_WIDTH]
    if wide:
        return min(wide, key=lambda c: c[1])[0]
    return max(candidates, key=lambda c: c[1])[0]


def is_placeholder(src: str | None) -> bool:
    return not src or src.startswith("data:")


def tidy_html(html: str | bytes, url: str) -> str | bytes:
    """Rewrites image markup trafilatura would drop or misread:
    <picture> to one <img>, srcset to the best src, lazy-load attributes
    to src, relative URLs to absolute."""
    tree = trafilatura.load_html(html)
    if tree is None:
        return html

    for img in tree.iter("img"):
        for attr in LAZY_SRCSET:
            if img.get(attr):
                img.set("srcset", img.get(attr))
        for attr in LAZY_SRC:
            if img.get(attr) and is_placeholder(img.get("src")):
                img.set("src", img.get(attr))

    for picture in list(tree.iter("picture")):
        img = next(picture.iter("img"), None)
        if img is None:
            continue
        candidates = []
        for source in picture.iter("source"):
            candidates += parse_srcset(source.get("srcset") or "")
        candidates += parse_srcset(img.get("srcset") or "")
        best = best_source(candidates)
        if best:
            img.set("src", best)
        img.attrib.pop("srcset", None)
        img.tail = picture.tail
        picture.getparent().replace(picture, img)

    for img in tree.iter("img"):
        best = best_source(parse_srcset(img.get("srcset") or ""))
        if best:
            img.set("src", best)
        img.attrib.pop("srcset", None)
        img.attrib.pop("sizes", None)

    cleanup.mark_anchors(tree)
    tree.make_links_absolute(url, resolve_base_href=True, handle_failures="ignore")
    return lxml_html.tostring(tree, encoding="unicode")


# Download.


def image_urls(markdown: str) -> list[str]:
    """http(s) image URLs in the markdown, first appearance order, unique."""
    seen: dict[str, None] = {}
    for url in MARKDOWN_IMAGE.findall(markdown):
        if url.startswith(("http://", "https://")):
            seen.setdefault(url)
    return list(seen)[:MAX_IMAGES]


def download(url: str, referer: str) -> tuple[str, bytes]:
    """Mime type and body. Raises on HTTP errors, non-images, too large."""
    from apps.items.fetch import USER_AGENT

    headers = {"User-Agent": USER_AGENT, "Referer": referer}
    with httpx2.Client(follow_redirects=True, timeout=TIMEOUT, headers=headers) as c:
        with c.stream("GET", url) as response:
            response.raise_for_status()
            mime = response.headers.get("content-type", "").split(";")[0].strip()
            mime = mime.lower()
            if not mime.startswith("image/"):
                raise ValueError(f"Not an image: {mime or 'no content type'}")
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise ValueError("Image is larger than 20 MB.")
            return mime, bytes(body)


def image_filename(url: str, mime: str, sha256: str) -> str:
    # Decoded first: CDNs like Substack's end the path with the original URL.
    stem = unquote(urlsplit(url).path).rsplit("/", 1)[-1].rsplit(".", 1)[0]
    slug = slugify(stem)[:40].strip("-")
    ext = EXTENSIONS.get(mime) or mimetypes.guess_extension(mime) or ""
    return f"{slug}-{sha256[:8]}{ext}" if slug else f"{sha256[:8]}{ext}"


def local_url(item: Item, filename: str) -> str:
    # Stored in the markdown: keep this path stable.
    return f"/api/v1/items/{ids.encode(item.id)}/sources/{filename}"


def save_image(item: Item, url: str) -> ItemSource:
    mime, body = download(url, referer=item.url)
    sha256 = hashlib.sha256(body).hexdigest()
    filename = image_filename(url, mime, sha256)
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    # url is the image's address in the markdown, the key for the swap.
    return ItemSource.objects.create(
        item=item,
        kind=ItemSource.Kind.IMAGE,
        filename=filename,
        url=url,
        mime=mime,
        size=len(body),
        sha256=sha256,
    )


def save_images(item: Item) -> tuple[int, int]:
    """Downloads the article's images and points its markdown at them.
    Already saved ones aren't downloaded again; failed ones keep their
    original URL. Returns (saved, failed)."""
    saved = {s.url: s for s in item.sources.filter(kind=ItemSource.Kind.IMAGE)}
    markdown = item.markdown
    new = failed = 0
    for url in image_urls(markdown):
        source = saved.get(url)
        if source is None or not source.path.exists():
            if source is not None:
                source.delete()
            try:
                source = save_image(item, url)
                new += 1
            except Exception as e:
                failed += 1
                log.warning("Image %s for item %s: %s", url, item.pk, e)
                continue
        markdown = markdown.replace(f"]({url}", f"]({local_url(item, source.filename)}")
    if markdown != item.markdown:
        item.markdown = markdown
        item.save(update_fields=["markdown"])
    return new, failed
