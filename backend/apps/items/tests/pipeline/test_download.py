import functools
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from apps.items.pipeline import download

# clean_url


def test_clean_url_strips_tracking():
    url = download.clean_url(
        "https://example.com/post?utm_source=x&id=1&fbclid=y&gclid=z&si=q"
    )

    assert parse_qs(urlsplit(url).query) == {"id": ["1"]}


def test_clean_url_keeps_plain_url():
    assert download.clean_url("https://example.com/post") == "https://example.com/post"


# download: no network, httpx2's mock transport


@pytest.fixture
def transport(monkeypatch):
    """Route download() through a handler: transport(handler)."""

    def use(handler):
        client = functools.partial(
            httpx2.Client, transport=httpx2.MockTransport(handler)
        )
        monkeypatch.setattr(download.httpx2, "Client", client)

    return use


def html_response(body=b"<html></html>", status=200):
    return httpx2.Response(
        status, headers={"content-type": "text/html; charset=utf-8"}, content=body
    )


def test_download_follows_redirects(transport):
    def handler(request):
        if request.url.path == "/old":
            return httpx2.Response(301, headers={"location": "https://example.com/new"})
        return html_response(b"<p>hi</p>")

    transport(handler)

    final_url, mime, encoding, body, status = download.download(
        "https://example.com/old"
    )

    assert final_url == "https://example.com/new"
    assert status == 200
    assert mime == "text/html"
    assert encoding == "utf-8"
    assert body == b"<p>hi</p>"


def test_download_non_html_has_no_body(transport):
    transport(
        lambda request: httpx2.Response(
            200, headers={"content-type": "application/pdf"}, content=b"%PDF"
        )
    )

    final_url, mime, encoding, body, status = download.download(
        "https://example.com/a.pdf"
    )

    assert mime == "application/pdf"
    assert body is None


def test_download_size_limit(transport, monkeypatch):
    monkeypatch.setattr(download, "MAX_BYTES", 10)
    transport(lambda request: html_response(b"x" * 11))

    with pytest.raises(download.FetchError):
        download.download("https://example.com/")


def test_download_http_error(transport):
    transport(lambda request: html_response(status=404))

    with pytest.raises(httpx2.HTTPStatusError):
        download.download("https://example.com/")
