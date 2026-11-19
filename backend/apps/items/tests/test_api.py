import uuid

import pytest

from apps.items import ids, tagging
from apps.items.models import Item, ItemSource, ItemTag
from apps.users.models import ApiToken

ITEMS = "/api/v1/items"


def deferred(app):
    return [(job["task_name"], job["args"]) for job in app.connector.jobs.values()]


def url_for(item):
    return f"{ITEMS}/{ids.encode(item.id)}"


# Create


def test_create(user_client, user, app):
    submitted = "https://example.com/post?utm_source=x&id=1"

    response = user_client.post(
        ITEMS, {"url": submitted}, content_type="application/json"
    )

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
    assert {"author", "site_name", "published_at"} <= body.keys()


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


def test_delete_drops_tags_left_unused(user_client, user, item, item_sources_dir):
    other = user.items.exclude(pk=item.pk).first()
    tagging.add_tags(item, ["only-here", "shared"], ItemTag.Source.MANUAL)
    tagging.add_tags(other, ["shared"], ItemTag.Source.MANUAL)

    user_client.delete(url_for(item))

    assert list(user.tags.values_list("name", flat=True)) == ["shared"]


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
        ("post", f"{ITEMS}/{'0' * 22}/tags"),
        ("delete", f"{ITEMS}/{'0' * 22}/tags/x"),
        ("get", "/api/v1/tags"),
    ],
)
def test_requires_login(client, db, method, path):
    assert getattr(client, method)(path).status_code == 401


# Tags


def add_tag(client, item, name):
    return client.post(
        f"{url_for(item)}/tags", {"name": name}, content_type="application/json"
    )


def test_item_has_tags(user_client, item):
    tagging.add_tags(item, ["design", "art"], ItemTag.Source.PAGE)

    body = user_client.get(url_for(item)).json()

    assert body["tags"] == [
        {"name": "art", "slug": "art", "source": "page"},
        {"name": "design", "slug": "design", "source": "page"},
    ]
    listed = next(i for i in user_client.get(ITEMS).json() if i["id"] == body["id"])
    assert listed["tags"] == body["tags"]


def test_add_tag(user_client, item):
    response = add_tag(user_client, item, "  Open Source ")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "open-source", "slug": "open-source", "source": "manual"}
    ]


@pytest.mark.parametrize("name", ["", "   ", "!!!", "x" * 51])
def test_add_tag_invalid(user_client, item, name):
    assert add_tag(user_client, item, name).status_code == 400
    assert not item.item_tags.exists()


def test_remove_tag(user_client, item):
    tagging.add_tags(item, ["art", "design"], ItemTag.Source.MODEL)

    response = user_client.delete(f"{url_for(item)}/tags/art")

    assert response.status_code == 200
    assert [t["name"] for t in response.json()] == ["design"]
    assert item.tag_removals.filter(name="art").exists()


def test_remove_unknown_tag(user_client, item):
    assert user_client.delete(f"{url_for(item)}/tags/nope").status_code == 404


def test_tags_on_other_users_item(client, other_user, item):
    client.force_login(other_user)

    assert add_tag(client, item, "art").status_code == 404
    assert client.delete(f"{url_for(item)}/tags/art").status_code == 404


def test_list_tags_with_counts(user_client, user, other_user, item):
    other = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    tagging.add_tags(item, ["art", "design"], ItemTag.Source.MANUAL)
    tagging.add_tags(other, ["art"], ItemTag.Source.MANUAL)
    tagging.get_or_create_tag(user, "unused")
    tagging.get_or_create_tag(other_user, "theirs")

    response = user_client.get("/api/v1/tags")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "art", "slug": "art", "count": 2},
        {"name": "design", "slug": "design", "count": 1},
        {"name": "unused", "slug": "unused", "count": 0},
    ]


def test_filter_items_by_tag(user_client, item):
    tagging.add_tags(item, ["art"], ItemTag.Source.MANUAL)

    response = user_client.get(ITEMS, {"tag": "art"})

    assert [i["id"] for i in response.json()] == [ids.encode(item.id)]
    assert user_client.get(ITEMS, {"tag": "nope"}).json() == []


def test_tags_with_token(client, user, item):
    _, key = ApiToken.create(user, "test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {key}"}

    response = client.post(
        f"{url_for(item)}/tags",
        {"name": "art"},
        content_type="application/json",
        **auth,
    )

    assert response.status_code == 200
    assert client.get("/api/v1/tags", **auth).status_code == 200


# Saved images


def save_source(item, filename, mime, body, kind=ItemSource.Kind.IMAGE):
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    return ItemSource.objects.create(
        item=item,
        kind=kind,
        filename=filename,
        url="https://x.test/a",
        mime=mime,
        size=len(body),
        sha256="0" * 64,
    )


def test_get_image(user_client, item, item_sources_dir):
    save_source(item, "a-00000000.png", "image/png", b"png")

    response = user_client.get(f"{url_for(item)}/sources/a-00000000.png")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert b"".join(response.streaming_content) == b"png"
    assert "immutable" in response["Cache-Control"]
    assert "Content-Security-Policy" not in response


def test_svg_is_sandboxed(user_client, item, item_sources_dir):
    save_source(item, "a.svg", "image/svg+xml", b"<svg/>")

    response = user_client.get(f"{url_for(item)}/sources/a.svg")

    assert "sandbox" in response["Content-Security-Policy"]


def test_html_source_not_served(user_client, item, item_sources_dir):
    html = item.sources.get(kind=ItemSource.Kind.HTML)

    response = user_client.get(f"{url_for(item)}/sources/{html.filename}")

    assert response.status_code == 404


def test_image_needs_auth_and_own_item(client, other_user, item, item_sources_dir):
    save_source(item, "a.png", "image/png", b"png")
    path = f"{url_for(item)}/sources/a.png"

    assert client.get(path).status_code == 401
    client.force_login(other_user)
    assert client.get(path).status_code == 404


def test_missing_image_file_is_404(user_client, item, item_sources_dir):
    source = save_source(item, "a.png", "image/png", b"png")
    source.path.unlink()

    assert user_client.get(f"{url_for(item)}/sources/a.png").status_code == 404
