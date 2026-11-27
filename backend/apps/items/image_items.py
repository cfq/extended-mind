"""Image items: the original file, uploaded or downloaded, and what's
read from it."""

import hashlib
import io
import uuid
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

from apps.items import images, steps
from apps.items.models import ImageItem, Item, ItemSource
from apps.items.sources import save_source

MAX_BYTES = 50 * 1024 * 1024
# Pillow format → mime type. What browsers show; no HEIC yet.
FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}
MIME_TYPES = set(FORMATS.values())


class NotAnImage(Exception):
    pass


def check(body: bytes) -> str:
    """The image's mime type, read from its content. Raises NotAnImage."""
    if len(body) > MAX_BYTES:
        raise NotAnImage("Image is larger than 50 MB.")
    try:
        with Image.open(io.BytesIO(body)) as image:
            mime = FORMATS.get(image.format or "")
    except (UnidentifiedImageError, OSError) as e:
        raise NotAnImage("Not an image.") from e
    if mime is None:
        raise NotAnImage("Not a JPEG, PNG, GIF or WebP image.")
    return mime


def name_from_url(url: str) -> str:
    return PurePosixPath(unquote(urlsplit(url).path)).name


def title_from(name: str) -> str:
    return PurePosixPath(name).stem


def ensure_image(item: Item) -> ImageItem:
    try:
        return item.image
    except ImageItem.DoesNotExist:
        image = ImageItem(item=item)
        image.save()
        return image


def make_image(item: Item, name: str, url: str, body: bytes, run_id: uuid.UUID):
    """Turns the item into an image item and saves its file. name: the
    original file name, for the title and the saved file's name."""
    item.type = Item.Type.IMAGE
    if not item.title:
        item.title = title_from(name)
    item.save()
    ensure_image(item)
    steps.need(item, "save_original", "dimensions")
    save_original(item, name, url, body, run_id)


def save_original(item: Item, name: str, url: str, body: bytes, run_id: uuid.UUID):
    with steps.run(item, "save_original", run_id) as run:
        mime = check(body)
        sha256 = hashlib.sha256(body).hexdigest()
        filename = images.image_filename(name, mime, sha256)
        save_source(item, ItemSource.Kind.ORIGINAL, filename, url, mime, body, run.row)
        run.note(mime=mime, bytes=len(body))


def dimensions(item: Item, run_id: uuid.UUID):
    with steps.run(item, "dimensions", run_id) as run:
        source = item.sources.get(kind=ItemSource.Kind.ORIGINAL)
        with Image.open(source.path) as file:
            width, height = file.size
        image = ensure_image(item)
        image.width, image.height = width, height
        image.save(update_fields=["width", "height"])
        run.note(width=width, height=height)
