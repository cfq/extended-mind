import hashlib
import uuid
from datetime import date

import pytest

from apps.items.models import Item, ItemSource, PageItem
from apps.items.pipeline import download, flow, steps
from apps.items.pipeline.download import FetchError

HANDLES = "01a1a417-604d-7679-9ecf-8b8932f3091c"
EDEN = "01a1a42b-07df-70aa-81c9-8eb4c9cc7688"


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

    filename = flow.source_filename(item, title, description)

    assert filename == f"{slug}-{item.short_id}.html"


def test_source_filename_capped():
    item = make_item()

    filename = flow.source_filename(item, "word " * 50, "")

    slug = filename.removesuffix(f"-{item.short_id}.html")
    assert len(slug) <= 60
    assert not slug.endswith("-")


# fetch: download patched, trafilatura for real on fixture HTML


def go(item):
    flow.fetch(item, steps.new_run_id())


@pytest.fixture
def downloads(monkeypatch):
    """Make download() return the given values: downloads(url, mime, body)."""

    def use(final_url, mime="text/html", body=None):
        monkeypatch.setattr(
            download,
            "download",
            lambda url: download.Download(final_url, mime, "utf-8", body, 200),
        )

    return use


def test_fetch_html(user, item_sources_dir, downloads, fixture_html):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    body = fixture_html(HANDLES)
    downloads(
        "https://floooh.github.io/2018/06/17/handles-vs-pointers.html?utm_source=x",
        body=body,
    )

    go(item)

    item = Item.objects.get(pk=item.pk)
    assert steps.status(item)[0] == Item.Status.DONE
    assert item.type == Item.Type.PAGE
    assert item.url == "https://floooh.github.io/2018/06/17/handles-vs-pointers.html"
    assert item.title == "Handles are the better pointers"
    assert item.description
    assert item.page.markdown
    assert item.page.text
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

    with pytest.raises(FetchError):
        go(item)

    item = Item.objects.get(pk=item.pk)
    assert steps.status(item)[0] == Item.Status.FAILED
    assert item.type == ""
    assert not PageItem.objects.filter(item=item).exists()
    assert not item.sources.exists()
    assert not item.sources_dir.exists()


def test_fetch_no_content(user, item_sources_dir, downloads):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    downloads("https://example.com/", body=b"<html><body></body></html>")

    with pytest.raises(FetchError):
        go(item)


def test_fetch_retry_replaces_source(item, item_sources_dir, downloads, fixture_html):
    (old,) = item.sources.all()
    old_path = old.path
    assert old_path.exists()
    downloads(item.url, body=fixture_html(HANDLES))

    go(item)

    (new,) = item.sources.all()
    assert new.pk != old.pk
    assert new.path.exists()
    assert list(item.sources_dir.iterdir()) == [new.path]


def test_fetch_metadata(user, item_sources_dir, downloads, fixture_html):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    downloads(
        "https://shkspr.mobi/blog/2026/11/ai-resistance/", body=fixture_html(EDEN)
    )

    go(item)

    item = Item.objects.get(pk=item.pk)
    assert item.page.author == "Terence Eden"
    assert item.site_name == "Terence Eden’s Blog"
    assert item.published_at == date(2026, 11, 3)
