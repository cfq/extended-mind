import re
import zlib

import numpy as np
import pytest

from apps.items import autotag, tagging
from apps.items.models import Item, ItemTag, Tag

DIMS = 256


def bag_of_words(texts):
    """Stand-in for the model: hashed word counts."""
    vectors = np.zeros((len(texts), DIMS))
    for row, text in enumerate(texts):
        for word in re.findall(r"\w+", text.lower()):
            vectors[row, zlib.crc32(word.encode()) % DIMS] += 1
    return vectors


@pytest.fixture
def low_thresholds(monkeypatch):
    monkeypatch.setattr(autotag, "TAG_THRESHOLD", 0.2)
    monkeypatch.setattr(autotag, "PHRASE_THRESHOLD", 0.1)


@pytest.fixture
def article(user):
    return Item.objects.create(
        user=user,
        url="https://x.test",
        url_submitted="x",
        status=Item.Status.DONE,
        title="Postgres indexes",
        text="Postgres indexes make queries fast. A postgres index is a tree. "
        "Vacuum keeps postgres tables healthy.",
    )


def test_candidates():
    phrases = autotag.candidates(
        "The database index and the database index are fast. Apple's Família once."
    )

    assert phrases[0] in {"database", "index"}
    assert "database index" in phrases
    assert {"apple", "família"} <= set(phrases)
    # Stopwords, and pairs seen only once.
    assert not {"the", "and", "are", "the database", "index fast"} & set(phrases)


def test_shares_word():
    assert autotag.shares_word("recent-emfcamp", ["emfcamp"])
    assert not autotag.shares_word("art-nouveau", ["sagrada"])


def test_in_text():
    words = {"british", "supermarket", "online"}

    assert autotag.in_text("british-online", words)
    assert not autotag.in_text("superintelligence", words)


def test_mmr_prefers_variety():
    doc = np.array([1.0, 0, 0])
    phrases = autotag.unit(
        np.array([[0.9, 0.1, 0], [0.9, 0.1, 0], [0.7, 0, 0.7], [-1, 0, 0]])
    )

    assert autotag.mmr(doc, phrases, 2, threshold=0.5) == [0, 2]


def test_suggest_reuses_existing_tags(article, low_thresholds):
    tagging.get_or_create_tag(article.user, "postgres-indexes")
    tagging.get_or_create_tag(article.user, "gardening")

    names = autotag.suggest(article, bag_of_words)

    assert names[0] == "postgres-indexes"
    assert "gardening" not in names
    assert len(names) <= autotag.MAX_TAGS


def test_suggest_reuses_only_tags_in_the_text(article, monkeypatch):
    # Close in meaning isn't enough: the tag's words must be in the article.
    monkeypatch.setattr(autotag, "TAG_THRESHOLD", -1)
    monkeypatch.setattr(autotag, "PHRASE_THRESHOLD", 2)
    tagging.get_or_create_tag(article.user, "databases")
    tagging.get_or_create_tag(article.user, "postgres")

    assert autotag.suggest(article, bag_of_words) == ["postgres"]


def test_suggest_skips_taken_and_removed(article, low_thresholds):
    tagging.add_tags(article, ["postgres"], ItemTag.Source.PAGE)
    tagging.add_tags(article, ["indexes"], ItemTag.Source.PAGE)
    tagging.remove_tag(article, Tag.objects.get(name="indexes"))

    names = autotag.suggest(article, bag_of_words)

    assert names
    # Nor phrases sharing their words ("postgres index").
    assert not any({"postgres", "indexes"} & autotag.words_of(n) for n in names)


def test_suggest_empty_article(user):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")

    assert autotag.suggest(item, bag_of_words) == []


def test_autotag_twice_adds_no_more(article, low_thresholds):
    first = autotag.autotag(article, bag_of_words)

    assert len(first) == autotag.MAX_TAGS
    assert autotag.autotag(article, bag_of_words) == []


def test_autotag_marks_source(article, low_thresholds):
    links = autotag.autotag(article, bag_of_words)

    assert links
    assert {link.source for link in links} == {ItemTag.Source.MODEL}


def test_real_model(item):
    """The baked-in model loads offline and tags a fixture article."""
    names = autotag.suggest(item)

    assert 0 < len(names) <= autotag.MAX_TAGS
