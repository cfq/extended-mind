"""Article images: kept through extraction, downloaded, and the
article's markdown pointed at the local copies. Also the page's sharing
image."""

import hashlib
import logging
import re
from typing import NamedTuple

import httpx2

from apps.items.models import Item, ItemSource, ItemStepRun
from apps.items.pipeline import extract
from apps.items.pipeline.sources import image_filename, local_url

log = logging.getLogger(__name__)

TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024
MAX_IMAGES = 100

# ![alt](url) or ![alt](url "title")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\((\S+?)(?:\s+\"[^\"]*\")?\)")


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
    from apps.items.pipeline.download import USER_AGENT

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


def save_image(
    item: Item,
    url: str,
    kind: str = ItemSource.Kind.IMAGE,
    run: ItemStepRun | None = None,
) -> ItemSource:
    mime, body = download(url, referer=item.url)
    sha256 = hashlib.sha256(body).hexdigest()
    filename = image_filename(url, mime, sha256)
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    # url is the image's address in the markdown, the key for the swap.
    return ItemSource.objects.create(
        item=item,
        kind=kind,
        filename=filename,
        url=url,
        mime=mime,
        size=len(body),
        sha256=sha256,
        run=run,
    )


class Saved(NamedTuple):
    new: int
    failed: list[str]


def save_images(item: Item, run: ItemStepRun | None = None) -> Saved:
    """Downloads the article's images and points its markdown at them.
    Already saved ones aren't downloaded again; failed ones keep their
    original URL. Returns how many were new, and the failed URLs."""
    page = item.page
    saved = {s.url: s for s in item.sources.filter(kind=ItemSource.Kind.IMAGE)}
    markdown = page.markdown
    new, failed = 0, []
    for url in image_urls(markdown):
        source = saved.get(url)
        if source is None or not source.path.exists():
            if source is not None:
                source.delete()
            try:
                source = save_image(item, url, run=run)
                new += 1
            except Exception as e:
                failed.append(url)
                log.warning("Image %s for item %s: %s", url, item.pk, e)
                continue
        markdown = markdown.replace(f"]({url}", f"]({local_url(item, source.filename)}")
    if markdown != page.markdown:
        page.markdown = markdown
        page.save(update_fields=["markdown"])
    return Saved(new, failed)


def save_og_image(item: Item, run: ItemStepRun | None = None) -> str:
    """Downloads the page's sharing image, unless the same URL is already
    saved. A new URL replaces the old file; a failed download raises and
    keeps it. Returns "none" (the page has none), "kept" or "saved"."""
    url = extract.sharing_image_url(item.page.meta, item.url)
    if not url:
        return "none"
    old = item.sources.filter(kind=ItemSource.Kind.OG_IMAGE).first()
    if old and old.url == url and old.path.exists():
        return "kept"
    save_image(item, url, ItemSource.Kind.OG_IMAGE, run)
    if old:
        # Another source may share the file: same content, same name.
        if not item.sources.filter(filename=old.filename).exclude(pk=old.pk).exists():
            old.path.unlink(missing_ok=True)
        old.delete()
    return "saved"
