import hashlib
import mimetypes
from urllib.parse import unquote, urlsplit

from django.utils.text import slugify

from apps.items import ids
from apps.items.models import Item, ItemSource, ItemStepRun


def save_source(
    item: Item,
    kind: str,
    filename: str,
    url: str,
    mime: str,
    body: bytes,
    run: ItemStepRun | None = None,
) -> ItemSource:
    """Writes the file and its row. A retry replaces the previous file of
    this kind."""
    for old in item.sources.filter(kind=kind):
        old.path.unlink(missing_ok=True)
        old.delete()
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    return ItemSource.objects.create(
        item=item,
        kind=kind,
        filename=filename,
        url=url,
        mime=mime,
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        run=run,
    )


EXTENSIONS = {"image/jpeg": ".jpg", "image/svg+xml": ".svg"}


def image_filename(url: str, mime: str, sha256: str) -> str:
    # Decoded first: CDNs like Substack's end the path with the original URL.
    stem = unquote(urlsplit(url).path).rsplit("/", 1)[-1].rsplit(".", 1)[0]
    slug = slugify(stem)[:40].strip("-")
    ext = EXTENSIONS.get(mime) or mimetypes.guess_extension(mime) or ""
    return f"{slug}-{sha256[:8]}{ext}" if slug else f"{sha256[:8]}{ext}"


def local_url(item: Item, filename: str) -> str:
    # Stored in the markdown: keep this path stable.
    return f"/api/v1/items/{ids.encode(item.id)}/sources/{filename}"
