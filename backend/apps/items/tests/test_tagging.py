import pytest

from apps.items import fetch, tagging
from apps.items.models import Item, ItemTag, ItemTagRemoval, Tag

PAGE = ItemTag.Source.PAGE
MODEL = ItemTag.Source.MODEL
MANUAL = ItemTag.Source.MANUAL

TAGGED_HTML = (
    "<html><head><title>Indexes</title>"
    '<meta name="keywords" content="Postgres, Databases ,SQL">'
    '<meta property="article:tag" content="Open  Source">'
    '<meta property="article:section" content="Uncategorized">'
    "</head><body><article><h1>Indexes</h1><p>"
    + "B-tree indexes make lookups fast. " * 40
    + "</p></article></body></html>"
)


def tags_of(item):
    return {link.tag.name: link.source for link in item.item_tags.all()}


@pytest.mark.parametrize(
    "raw, name",
    [
        ("  Open   Source ", "open source"),
        ("C++", "c++"),
        ("---", ""),
        ("", ""),
        ("x" * 51, ""),
    ],
)
def test_normalize(raw, name):
    assert tagging.normalize(raw) == name


def test_page_tags_split_dedupe_ignore_cap():
    assert tagging.page_tags(["Tech", "general"], ["Postgres, SQL ,postgres"]) == [
        "postgres",
        "sql",
        "tech",
    ]
    assert len(tagging.page_tags([], [",".join("abcdefgh")])) == 5
    assert tagging.page_tags(None, None) == []


def test_slug_collisions(user):
    first = tagging.get_or_create_tag(user, "c++")
    second = tagging.get_or_create_tag(user, "c#")

    assert (first.slug, second.slug) == ("c", "c-2")
    assert tagging.get_or_create_tag(user, "c++") == first


def test_tags_are_per_user(user, other_user):
    mine = tagging.get_or_create_tag(user, "art")
    theirs = tagging.get_or_create_tag(other_user, "art")

    assert mine != theirs
    assert mine.slug == theirs.slug == "art"


def test_add_and_remove(item):
    tagging.add_tags(item, ["Art", "art ", "design"], PAGE)
    assert tags_of(item) == {"art": PAGE, "design": PAGE}

    tagging.remove_tag(item, Tag.objects.get(user=item.user, name="art"))

    assert tags_of(item) == {"design": PAGE}
    assert ItemTagRemoval.objects.filter(item=item, name="art").exists()


def test_auto_sources_skip_removed(item):
    tagging.add_tags(item, ["art"], PAGE)
    tagging.remove_tag(item, Tag.objects.get(name="art"))

    assert tagging.add_tags(item, ["art"], PAGE) == []
    assert tagging.add_tags(item, ["art"], MODEL) == []
    assert tags_of(item) == {}


def test_manual_takes_over_and_clears_removal(item):
    tagging.add_tags(item, ["art"], MODEL)
    tagging.add_tags(item, ["art"], MANUAL)
    assert tags_of(item) == {"art": MANUAL}

    tagging.remove_tag(item, Tag.objects.get(name="art"))
    tagging.add_tags(item, ["art"], MANUAL)

    assert tags_of(item) == {"art": MANUAL}
    assert not item.tag_removals.exists()


def test_auto_source_keeps_manual(item):
    tagging.add_tags(item, ["art"], MANUAL)
    tagging.add_tags(item, ["art"], PAGE)

    assert tags_of(item) == {"art": MANUAL}


def test_extract_returns_page_tags():
    item = Item(url="https://example.com/indexes")

    assert fetch.extract(item, TAGGED_HTML) == [
        "postgres",
        "databases",
        "sql",
        "open source",
    ]


def test_fetch_adds_page_tags(user, item_sources_dir, monkeypatch):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    monkeypatch.setattr(
        fetch,
        "download",
        lambda url: (url, "text/html", "utf-8", TAGGED_HTML.encode()),
    )

    fetch.fetch(item)

    assert tags_of(item) == {
        "postgres": PAGE,
        "databases": PAGE,
        "sql": PAGE,
        "open source": PAGE,
    }
