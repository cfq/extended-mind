"""Open Graph, Twitter card and article meta tags, kept as the page
declares them."""

from urllib.parse import urljoin

from trafilatura.utils import load_html

PREFIXES = ("og:", "twitter:", "article:")
# The sharing image, in order of preference.
IMAGE_KEYS = (
    "og:image:secure_url",
    "og:image",
    "og:image:url",
    "twitter:image",
    "twitter:image:src",
)


def parse(html: str | bytes) -> dict[str, str | list[str]]:
    """Meta tags whose property or name starts with og:, twitter: or
    article:. Keys lowercased; a key that repeats maps to a list."""
    # trafilatura's loader: detects the encoding of bytes, as extraction does.
    tree = load_html(html)
    if tree is None:
        return {}
    meta: dict[str, str | list[str]] = {}
    for tag in tree.iter("meta"):
        key = (tag.get("property") or tag.get("name") or "").strip().lower()
        content = (tag.get("content") or "").strip()
        if not key.startswith(PREFIXES) or not content:
            continue
        if key not in meta:
            meta[key] = content
        elif isinstance(meta[key], list):
            meta[key].append(content)
        elif meta[key] != content:
            meta[key] = [meta[key], content]
    return meta


def image_url(meta: dict, page_url: str) -> str | None:
    """The sharing image's absolute URL, or None."""
    for key in IMAGE_KEYS:
        value = meta.get(key)
        if isinstance(value, list):
            value = value[0]
        if not value:
            continue
        url = urljoin(page_url, value)
        if url.startswith(("http://", "https://")):
            return url
    return None
