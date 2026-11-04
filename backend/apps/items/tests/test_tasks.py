import pytest

from apps.items import fetch
from apps.items.models import Item
from apps.items.tasks import fetch_item


@pytest.fixture
def pending(user):
    return Item.objects.create(user=user, url="https://x.test", url_submitted="x")


def test_fetch_item_done(pending, monkeypatch):
    statuses = []

    def fake_fetch(item):
        statuses.append(Item.objects.get(pk=item.pk).status)
        item.status = Item.Status.DONE
        item.save()

    monkeypatch.setattr(fetch, "fetch", fake_fetch)

    fetch_item(item_id=str(pending.id))

    assert statuses == [Item.Status.FETCHING]
    pending.refresh_from_db()
    assert pending.status == Item.Status.DONE


def test_fetch_item_failed(pending, monkeypatch):
    def fail(item):
        raise fetch.FetchError("No article content found.")

    monkeypatch.setattr(fetch, "fetch", fail)

    with pytest.raises(fetch.FetchError):
        fetch_item(item_id=str(pending.id))

    pending.refresh_from_db()
    assert pending.status == Item.Status.FAILED
    assert pending.error == "No article content found."
