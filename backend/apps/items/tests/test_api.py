import uuid

import pytest

from apps.items import ids
from apps.items.models import Item

ITEMS = "/api/v1/items"


def deferred(app):
    return [(job["task_name"], job["args"]) for job in app.connector.jobs.values()]


def url_for(item):
    return f"{ITEMS}/{ids.encode(item.id)}"


# Create


def test_create(user_client, user, app):
    submitted = "https://example.com/post?utm_source=x&id=1"

    response = user_client.post(ITEMS, {"url": submitted}, content_type="application/json")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["url_submitted"] == submitted
    assert "utm_source" not in body["url"]
    item = Item.objects.get(id=ids.decode(body["id"]))
    assert item.user == user
    assert deferred(app) == [("apps.items.tasks.fetch_item", {"item_id": str(item.id)})]


@pytest.mark.parametrize("url", ["not a url", "ftp://example.com/file", ""])
def test_create_invalid_url(user_client, app, url):
    response = user_client.post(ITEMS, {"url": url}, content_type="application/json")

    assert response.status_code == 400
    assert not app.connector.jobs


# List


def test_list_own_items_newest_first(user_client, other_user):
    Item.objects.create(user=other_user, url="https://x.test", url_submitted="x")

    response = user_client.get(ITEMS)

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == [
        "Why Don’t We Live in an Art Nouveau World?",
        "AI is destroying my CS degree",
        "Just a little AI resistance, as a treat",
        "I Dumped Apple's Fucking Word List - Helge Sverre",
        "Handles are the better pointers",
    ]
    assert "markdown" not in response.json()[0]


# Detail


def test_detail(user_client, item):
    response = user_client.get(url_for(item))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == ids.encode(item.id)
    assert body["title"] == "Handles are the better pointers"
    assert body["markdown"]


@pytest.mark.parametrize(
    "item_id",
    [ids.encode(uuid.uuid7()), "not-an-id", "z" * 22],
    ids=["unknown", "malformed", "overflow"],
)
def test_detail_not_found(user_client, item_id):
    assert user_client.get(f"{ITEMS}/{item_id}").status_code == 404


def test_detail_other_users_item(client, other_user, item):
    client.force_login(other_user)

    assert client.get(url_for(item)).status_code == 404


# Retry


def test_retry(user_client, item, app):
    item.status = Item.Status.FAILED
    item.error = "boom"
    item.save()

    response = user_client.post(f"{url_for(item)}/retry")

    assert response.status_code == 200
    item.refresh_from_db()
    assert item.status == Item.Status.PENDING
    assert item.error == ""
    assert deferred(app) == [("apps.items.tasks.fetch_item", {"item_id": str(item.id)})]


# Delete


def test_delete(user_client, item, item_sources_dir):
    folder = item.sources_dir
    assert folder.exists()

    response = user_client.delete(url_for(item))

    assert response.status_code == 204
    assert not Item.objects.filter(pk=item.pk).exists()
    assert not folder.exists()


def test_delete_other_users_item(client, other_user, item):
    client.force_login(other_user)

    assert client.delete(url_for(item)).status_code == 404
    assert Item.objects.filter(pk=item.pk).exists()


# Auth


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", ITEMS),
        ("post", ITEMS),
        ("get", f"{ITEMS}/{'0' * 22}"),
        ("post", f"{ITEMS}/{'0' * 22}/retry"),
        ("delete", f"{ITEMS}/{'0' * 22}"),
    ],
)
def test_requires_login(client, db, method, path):
    assert getattr(client, method)(path).status_code == 401
