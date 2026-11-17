import functools
import hashlib
import uuid
from datetime import date
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from apps.items import fetch
from apps.items.models import Item, ItemSource

HANDLES = "01a1a417-604d-7679-9ecf-8b8932f3091c"
EDEN = "01a1a42b-07df-70aa-81c9-8eb4c9cc7688"


# clean_url


def test_clean_url_strips_tracking():
    url = fetch.clean_url(
        "https://example.com/post?utm_source=x&id=1&fbclid=y&gclid=z&si=q"
    )

    assert parse_qs(urlsplit(url).query) == {"id": ["1"]}


def test_clean_url_keeps_plain_url():
    assert fetch.clean_url("https://example.com/post") == "https://example.com/post"


# source_filename


def make_item(url="https://example.com/some/post"):
    return Item(id=uuid.uuid7(), url=url)


@pytest.mark.parametrize(
    "title, description, slug",
    [
        ("A Title", "A description", "a-title"),
        ("", "A description", "a-description"),
        ("", "", "example-com-some-post"),
    ],
    ids=["title", "description", "url"],
)
def test_source_filename_fallbacks(title, description, slug):
    item = make_item()

    filename = fetch.source_filename(item, title, description)

    assert filename == f"{slug}-{item.short_id}.html"


def test_source_filename_capped():
    item = make_item()

    filename = fetch.source_filename(item, "word " * 50, "")

    slug = filename.removesuffix(f"-{item.short_id}.html")
    assert len(slug) <= 60
    assert not slug.endswith("-")


# download: no network, httpx2's mock transport


@pytest.fixture
def transport(monkeypatch):
    """Route download() through a handler: transport(handler)."""

    def use(handler):
        client = functools.partial(
            httpx2.Client, transport=httpx2.MockTransport(handler)
        )
        monkeypatch.setattr(fetch.httpx2, "Client", client)

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

    final_url, mime, encoding, body = fetch.download("https://example.com/old")

    assert final_url == "https://example.com/new"
    assert mime == "text/html"
    assert encoding == "utf-8"
    assert body == b"<p>hi</p>"


def test_download_non_html_has_no_body(transport):
    transport(
        lambda request: httpx2.Response(
            200, headers={"content-type": "application/pdf"}, content=b"%PDF"
        )
    )

    final_url, mime, encoding, body = fetch.download("https://example.com/a.pdf")

    assert mime == "application/pdf"
    assert body is None


def test_download_size_limit(transport, monkeypatch):
    monkeypatch.setattr(fetch, "MAX_BYTES", 10)
    transport(lambda request: html_response(b"x" * 11))

    with pytest.raises(fetch.FetchError):
        fetch.download("https://example.com/")


def test_download_http_error(transport):
    transport(lambda request: html_response(status=404))

    with pytest.raises(httpx2.HTTPStatusError):
        fetch.download("https://example.com/")


# fetch: download patched, trafilatura for real on fixture HTML


@pytest.fixture
def downloads(monkeypatch):
    """Make download() return the given values: downloads(url, mime, body)."""

    def use(final_url, mime="text/html", body=None):
        monkeypatch.setattr(
            fetch, "download", lambda url: (final_url, mime, "utf-8", body)
        )

    return use


def test_fetch_html(user, item_sources_dir, downloads, fixture_html):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    body = fixture_html(HANDLES)
    downloads(
        "https://floooh.github.io/2018/06/17/handles-vs-pointers.html?utm_source=x",
        body=body,
    )

    fetch.fetch(item)

    item.refresh_from_db()
    assert item.status == Item.Status.DONE
    assert item.url == "https://floooh.github.io/2018/06/17/handles-vs-pointers.html"
    assert item.title == "Handles are the better pointers"
    assert item.description
    assert item.markdown
    assert item.text
    assert item.fetched_at

    (source,) = item.sources.all()
    assert source.kind == ItemSource.Kind.HTML
    assert source.filename == f"handles-are-the-better-pointers-{item.short_id}.html"
    assert source.size == len(body)
    assert source.sha256 == hashlib.sha256(body).hexdigest()
    assert source.path.read_bytes() == body


def test_fetch_non_html(user, item_sources_dir, downloads):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    downloads("https://example.com/a.pdf", mime="application/pdf")

    fetch.fetch(item)

    item.refresh_from_db()
    assert item.status == Item.Status.DONE
    assert item.url == "https://example.com/a.pdf"
    assert not item.markdown
    assert not item.sources.exists()
    assert not item.sources_dir.exists()


def test_fetch_no_content(user, item_sources_dir, downloads):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    downloads("https://example.com/", body=b"<html><body></body></html>")

    with pytest.raises(fetch.FetchError):
        fetch.fetch(item)


def test_fetch_retry_replaces_source(item, item_sources_dir, downloads, fixture_html):
    (old,) = item.sources.all()
    old_path = old.path
    assert old_path.exists()
    downloads(item.url, body=fixture_html(HANDLES))

    fetch.fetch(item)

    (new,) = item.sources.all()
    assert new.pk != old.pk
    assert new.path.exists()
    assert list(item.sources_dir.iterdir()) == [new.path]


def test_fetch_metadata(user, item_sources_dir, downloads, fixture_html):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    downloads(
        "https://shkspr.mobi/blog/2026/11/ai-resistance/", body=fixture_html(EDEN)
    )

    fetch.fetch(item)

    item.refresh_from_db()
    assert item.author == "Terence Eden"
    assert item.site_name == "Terence Eden’s Blog"
    assert item.published_at == date(2026, 11, 3)


@pytest.mark.parametrize(
    "value, expected",
    [("2026-11-03", date(2026, 11, 3)), ("", None), (None, None), ("not a date", None)],
)
def test_parse_date(value, expected):
    assert fetch.parse_date(value) == expected
