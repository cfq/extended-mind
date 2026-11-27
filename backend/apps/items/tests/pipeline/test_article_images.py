import functools
from urllib.parse import urljoin

import httpx2
import pytest

from apps.items import ids
from apps.items.models import ItemSource
from apps.items.pipeline import article_images, sources

PNG = b"\x89PNG\r\n\x1a\nfake"


@pytest.fixture
def transport(monkeypatch):
    """Route image downloads through a handler; returns the requests seen."""
    seen = []

    def use(handler):
        def record(request):
            seen.append(request)
            return handler(request)

        client = functools.partial(
            httpx2.Client, transport=httpx2.MockTransport(record)
        )
        monkeypatch.setattr(article_images.httpx2, "Client", client)
        return seen

    return use


def png(request):
    return httpx2.Response(200, headers={"content-type": "image/png"}, content=PNG)


# Markdown


def test_image_urls_unique_http_only():
    markdown = (
        '![a](https://x.test/a.png) text ![b](https://x.test/b.png "Title")\n'
        "![a again](https://x.test/a.png) ![inline](data:image/png;base64,xx) "
        "[link](https://x.test/page)"
    )

    assert article_images.image_urls(markdown) == [
        "https://x.test/a.png",
        "https://x.test/b.png",
    ]


def test_image_filename():
    assert sources.image_filename(
        "https://x.test/p/Photo_01.JPG?w=2", "image/jpeg", "ab" * 32
    ) == ("photo_01-abababab.jpg")
    assert (
        sources.image_filename("https://x.test/", "image/png", "cd" * 32)
        == "cdcdcdcd.png"
    )


# Download and swap


def test_save_images_downloads_and_swaps(item, item_sources_dir, transport):
    seen = transport(png)
    item.page.markdown = "![a](https://x.test/a.png)\n\n[![a](https://x.test/a.png)](https://x.test/a.png)"
    item.page.save()

    assert article_images.save_images(item) == (1, [])

    source = item.sources.get(kind=ItemSource.Kind.IMAGE)
    local = f"/api/v1/items/{ids.encode(item.id)}/sources/{source.filename}"
    item.page.refresh_from_db()
    assert item.page.markdown == f"![a]({local})\n\n[![a]({local})]({local})"
    assert source.path.read_bytes() == PNG
    assert (source.url, source.mime, source.size) == (
        "https://x.test/a.png",
        "image/png",
        len(PNG),
    )
    assert len(seen) == 1
    assert seen[0].headers["referer"] == item.url


def test_failed_images_keep_original_url(item, item_sources_dir, transport):
    def handler(request):
        if request.url.path == "/missing.png":
            return httpx2.Response(404)
        if request.url.path == "/page.png":
            return httpx2.Response(
                200, headers={"content-type": "text/html"}, content=b"<p>"
            )
        return png(request)

    transport(handler)
    item.page.markdown = "![](https://x.test/missing.png) ![](https://x.test/page.png) ![](https://x.test/ok.png)"
    item.page.save()

    missing, page = "https://x.test/missing.png", "https://x.test/page.png"
    assert article_images.save_images(item) == (1, [missing, page])

    item.page.refresh_from_db()
    assert "](https://x.test/missing.png)" in item.page.markdown
    assert "](https://x.test/page.png)" in item.page.markdown
    assert "](https://x.test/ok.png)" not in item.page.markdown


def test_size_limit(item, item_sources_dir, transport, monkeypatch):
    monkeypatch.setattr(article_images, "MAX_BYTES", 3)
    transport(png)
    item.page.markdown = "![](https://x.test/a.png)"
    item.page.save()

    assert article_images.save_images(item) == (0, ["https://x.test/a.png"])
    assert not item.sources.filter(kind=ItemSource.Kind.IMAGE).exists()


def test_after_reextract_swaps_without_downloading(item, item_sources_dir, transport):
    seen = transport(png)
    original = "![a](https://x.test/a.png)"
    item.page.markdown = original
    item.page.save()
    article_images.save_images(item)
    swapped = item.page.markdown

    # reextract puts the original URL back.
    item.page.markdown = original
    item.page.save()

    assert article_images.save_images(item) == (0, [])
    assert item.page.markdown == swapped
    assert len(seen) == 1


def test_missing_file_is_downloaded_again(item, item_sources_dir, transport):
    seen = transport(png)
    item.page.markdown = "![a](https://x.test/a.png)"
    item.page.save()
    article_images.save_images(item)
    item.sources.get(kind=ItemSource.Kind.IMAGE).path.unlink()
    item.page.markdown = "![a](https://x.test/a.png)"

    assert article_images.save_images(item) == (1, [])
    assert item.sources.filter(kind=ItemSource.Kind.IMAGE).count() == 1
    assert len(seen) == 2


# Sharing image


def test_og_image_saved(item, item_sources_dir, transport):
    seen = transport(png)
    item.page.markdown = ""
    item.page.meta = {"og:image": "/share.png"}
    item.page.save()

    assert article_images.save_og_image(item) == "saved"

    source = item.sources.get(kind=ItemSource.Kind.OG_IMAGE)
    assert source.url == urljoin(item.url, "/share.png")
    assert source.path.read_bytes() == PNG
    assert seen[0].headers["referer"] == item.url


def test_og_image_not_downloaded_twice(item, item_sources_dir, transport):
    seen = transport(png)
    item.page.markdown = ""
    item.page.meta = {"og:image": "https://x.test/share.png"}
    item.page.save()
    article_images.save_og_image(item)

    assert article_images.save_og_image(item) == "kept"
    assert len(seen) == 1


def test_og_image_new_url_replaces_old(item, item_sources_dir, transport):
    def handler(request):
        content = request.url.path.encode()
        return httpx2.Response(
            200, headers={"content-type": "image/png"}, content=content
        )

    transport(handler)
    item.page.markdown = ""
    item.page.meta = {"og:image": "https://x.test/one.png"}
    item.page.save()
    article_images.save_og_image(item)
    old = item.sources.get(kind=ItemSource.Kind.OG_IMAGE)

    item.page.meta = {"og:image": "https://x.test/two.png"}
    assert article_images.save_og_image(item) == "saved"

    new = item.sources.get(kind=ItemSource.Kind.OG_IMAGE)
    assert new.url == "https://x.test/two.png"
    assert not old.path.exists()


def test_og_image_failure_keeps_old(item, item_sources_dir, transport):
    transport(png)
    item.page.markdown = ""
    item.page.meta = {"og:image": "https://x.test/one.png"}
    item.page.save()
    article_images.save_og_image(item)

    transport(lambda request: httpx2.Response(404))
    item.page.meta = {"og:image": "https://x.test/two.png"}

    with pytest.raises(httpx2.HTTPStatusError):
        article_images.save_og_image(item)
    assert (
        item.sources.get(kind=ItemSource.Kind.OG_IMAGE).url == "https://x.test/one.png"
    )


def test_og_image_same_file_as_article_image(
    item, item_sources_dir, transport, user_client
):
    transport(png)
    item.page.markdown = "![a](https://x.test/a.png)"
    item.page.meta = {"og:image": "https://x.test/a.png"}
    item.page.save()

    assert article_images.save_images(item) == (1, [])
    assert article_images.save_og_image(item) == "saved"

    og = item.sources.get(kind=ItemSource.Kind.OG_IMAGE)
    article = item.sources.get(kind=ItemSource.Kind.IMAGE)
    assert og.filename == article.filename
    response = user_client.get(sources.local_url(item, og.filename))
    assert response.status_code == 200


def test_api_meta_and_og_image(item, item_sources_dir, transport, user_client):
    transport(png)
    item.page.markdown = ""
    item.page.meta = {"og:image": "https://x.test/share.png", "og:type": "article"}
    item.page.save()
    url = f"/api/v1/items/{ids.encode(item.id)}"
    assert user_client.get(url).json()["page"]["og_image"] is None

    article_images.save_og_image(item)

    data = user_client.get(url).json()["page"]
    assert data["meta"] == item.page.meta
    source = item.sources.get(kind=ItemSource.Kind.OG_IMAGE)
    assert data["og_image"] == sources.local_url(item, source.filename)
    response = user_client.get(data["og_image"])
    assert response["Content-Type"] == "image/png"
