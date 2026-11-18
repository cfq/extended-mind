import pytest

from apps.items import autotag, fetch
from apps.items.models import Item
from apps.items.tasks import fetch_item, tag_item


@pytest.fixture
def pending(user):
    return Item.objects.create(user=user, url="https://x.test", url_submitted="x")


def test_fetch_item_done(pending, monkeypatch, app):
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


def test_fetch_item_queues_tagging(pending, monkeypatch, app):
    monkeypatch.setattr(fetch, "fetch", lambda item: None)

    fetch_item(item_id=str(pending.id))

    jobs = [(j["task_name"], j["args"]) for j in app.connector.jobs.values()]
    assert jobs == [("apps.items.tasks.tag_item", {"item_id": str(pending.id)})]


def test_failed_fetch_queues_no_tagging(pending, monkeypatch, app):
    def fail(item):
        raise fetch.FetchError("nope")

    monkeypatch.setattr(fetch, "fetch", fail)

    with pytest.raises(fetch.FetchError):
        fetch_item(item_id=str(pending.id))

    assert not app.connector.jobs


def test_tag_item_only_done(pending, monkeypatch):
    calls = []
    monkeypatch.setattr(autotag, "autotag", calls.append)

    tag_item(item_id=str(pending.id))
    pending.status = Item.Status.DONE
    pending.save()
    tag_item(item_id=str(pending.id))

    assert [item.pk for item in calls] == [pending.pk]
