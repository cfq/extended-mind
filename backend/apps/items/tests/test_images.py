import functools

import httpx2
import pytest
from lxml import html as lxml_html

from apps.items import ids, images
from apps.items.models import ItemSource

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
        monkeypatch.setattr(images.httpx2, "Client", client)
        return seen

    return use


def png(request):
    return httpx2.Response(200, headers={"content-type": "image/png"}, content=PNG)


def imgs(html):
    tree = lxml_html.fromstring(html)
    return [dict(img.attrib) for img in tree.iter("img")]


# HTML tidying


def test_parse_srcset_with_commas_in_urls():
    srcset = (
        "https://cdn.test/fetch/w_424,c_limit/a.png 424w, "
        "https://cdn.test/fetch/w_1456,c_limit/a.png 1456w"
    )
    assert images.parse_srcset(srcset) == [
        ("https://cdn.test/fetch/w_424,c_limit/a.png", 424),
        ("https://cdn.test/fetch/w_1456,c_limit/a.png", 1456),
    ]
    assert images.parse_srcset("a.jpg 1x, b.jpg 2x") == [
        ("a.jpg", 800),
        ("b.jpg", 1600),
    ]


def test_best_source_closest_to_1600_preferring_wider():
    assert (
        images.best_source([("s", 600), ("m", 1200), ("l", 1920), ("xl", 3000)]) == "l"
    )
    assert images.best_source([("s", 600), ("m", 1200)]) == "m"
    assert images.best_source([]) is None


def test_tidy_picture_becomes_one_img():
    html = (
        "<html><body><p>Before</p><figure><picture>"
        '<source srcset="/a-600.avif 600w, /a-1920.avif 1920w" type="image/avif">'
        '<img src="/a-300.jpg" alt="A">'
        "</picture><figcaption>Cap</figcaption></figure></body></html>"
    )

    tidied = images.tidy_html(html, "https://site.test/post")

    assert "<picture" not in tidied
    assert imgs(tidied) == [{"src": "https://site.test/a-1920.avif", "alt": "A"}]
    assert "Cap" in tidied


def test_tidy_lazy_srcset_and_relative():
    html = (
        "<html><body>"
        '<img src="data:image/gif;base64,R0l" data-src="lazy.jpg">'
        '<img src="small.jpg" srcset="small.jpg 400w, big.jpg 1600w" sizes="50vw">'
        '<img data-lazy-srcset="x1.jpg 1x, x2.jpg 2x">'
        "</body></html>"
    )

    tidied = images.tidy_html(html, "https://site.test/blog/post")

    assert [img.get("src") for img in imgs(tidied)] == [
        "https://site.test/blog/lazy.jpg",
        "https://site.test/blog/big.jpg",
        "https://site.test/blog/x2.jpg",
    ]
    assert not any("srcset" in img or "sizes" in img for img in imgs(tidied))


def test_tidy_respects_base_href():
    html = (
        '<html><head><base href="https://cdn.test/"></head>'
        '<body><img src="a.png"></body></html>'
    )

    assert (
        imgs(images.tidy_html(html, "https://site.test/"))[0]["src"]
        == "https://cdn.test/a.png"
    )


# Markdown


def test_image_urls_unique_http_only():
    markdown = (
        '![a](https://x.test/a.png) text ![b](https://x.test/b.png "Title")\n'
        "![a again](https://x.test/a.png) ![inline](data:image/png;base64,xx) "
        "[link](https://x.test/page)"
    )

    assert images.image_urls(markdown) == [
        "https://x.test/a.png",
        "https://x.test/b.png",
    ]


def test_image_filename():
    assert images.image_filename(
        "https://x.test/p/Photo_01.JPG?w=2", "image/jpeg", "ab" * 32
    ) == ("photo_01-abababab.jpg")
    assert (
        images.image_filename("https://x.test/", "image/png", "cd" * 32)
        == "cdcdcdcd.png"
    )


# Download and swap


def test_save_images_downloads_and_swaps(item, item_sources_dir, transport):
    seen = transport(png)
    item.markdown = "![a](https://x.test/a.png)\n\n[![a](https://x.test/a.png)](https://x.test/a.png)"
    item.save()

    assert images.save_images(item) == (1, 0)

    source = item.sources.get(kind=ItemSource.Kind.IMAGE)
    local = f"/api/v1/items/{ids.encode(item.id)}/sources/{source.filename}"
    item.refresh_from_db()
    assert item.markdown == f"![a]({local})\n\n[![a]({local})]({local})"
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
    item.markdown = "![](https://x.test/missing.png) ![](https://x.test/page.png) ![](https://x.test/ok.png)"
    item.save()

    assert images.save_images(item) == (1, 2)

    item.refresh_from_db()
    assert "](https://x.test/missing.png)" in item.markdown
    assert "](https://x.test/page.png)" in item.markdown
    assert "](https://x.test/ok.png)" not in item.markdown


def test_size_limit(item, item_sources_dir, transport, monkeypatch):
    monkeypatch.setattr(images, "MAX_BYTES", 3)
    transport(png)
    item.markdown = "![](https://x.test/a.png)"
    item.save()

    assert images.save_images(item) == (0, 1)
    assert not item.sources.filter(kind=ItemSource.Kind.IMAGE).exists()


def test_after_reextract_swaps_without_downloading(item, item_sources_dir, transport):
    seen = transport(png)
    original = "![a](https://x.test/a.png)"
    item.markdown = original
    item.save()
    images.save_images(item)
    swapped = item.markdown

    # reextract puts the original URL back.
    item.markdown = original
    item.save()

    assert images.save_images(item) == (0, 0)
    assert item.markdown == swapped
    assert len(seen) == 1


def test_missing_file_is_downloaded_again(item, item_sources_dir, transport):
    seen = transport(png)
    item.markdown = "![a](https://x.test/a.png)"
    item.save()
    images.save_images(item)
    item.sources.get(kind=ItemSource.Kind.IMAGE).path.unlink()
    item.markdown = "![a](https://x.test/a.png)"

    assert images.save_images(item) == (1, 0)
    assert item.sources.filter(kind=ItemSource.Kind.IMAGE).count() == 1
    assert len(seen) == 2
