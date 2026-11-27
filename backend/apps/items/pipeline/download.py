"""Pages and files over plain HTTP, and cleaning their URLs."""

from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import courlan
import httpx2

from apps.items.pipeline import originals

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
            if mime not in HTML_TYPES | originals.MIME_TYPES:
                return Download(final_url, mime, None, None, response.status_code)
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FetchError("Larger than 50 MB.")
            return Download(
                final_url, mime, response.encoding, bytes(body), response.status_code
            )
