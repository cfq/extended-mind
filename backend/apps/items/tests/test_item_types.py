import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from PIL import Image

from apps.items import fetch, ids, image_items, images, steps
from apps.items.models import ImageItem, Item, ItemSource, ItemStepRun, PageItem
from apps.items.tasks import fetch_item, process_upload, save_images

ITEMS = "/api/v1/items"
Outcome = ItemStepRun.Outcome


def png(width=3, height=2, format="PNG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(out, format=format)
    return out.getvalue()


def upload(client, *files, **form):
    return client.post(f"{ITEMS}/images", {"file": list(files), **form})


def image_file(name="Holiday Photo.png", body=None):
    return SimpleUploadedFile(name, body or png(), content_type="image/png")


def get(item) -> Item:
    return Item.objects.prefetch_related("steps__runs").get(pk=item.pk)


# Migration


@pytest.mark.django_db(transaction=True)
def test_migration_turns_items_into_pages_keeping_status(django_user_model):
    executor = MigrationExecutor(connection)
    executor.migrate([("items", "0009_item_types")])
    old = executor.loader.project_state([("items", "0009_item_types")]).apps
    user = django_user_model.objects.create(username="m", email="m@x.test")
    OldItem = old.get_model("items", "Item")
    common = {"user_id": user.pk, "url": "https://x.test", "url_submitted": "x"}
    done = OldItem.objects.create(
        **common, status="done", author="A", text="T", markdown="M", meta={"k": 1}
    )
    failed = OldItem.objects.create(**common, status="failed", error="HTTP 404")
    pending = OldItem.objects.create(**common, status="pending")

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())

    page = PageItem.objects.get(pk=done.pk)
    assert (page.author, page.text, page.markdown, page.meta) == (
        "A",
        "T",
        "M",
        {"k": 1},
    )
    assert Item.objects.get(pk=done.pk).type == "page"
    assert steps.status(get(done)) == (Item.Status.DONE, "")
    assert steps.status(get(failed)) == (Item.Status.FAILED, "HTTP 404")
    assert steps.status(get(pending)) == (Item.Status.PENDING, "")


# Uploads


def test_upload_makes_image_items(user_client, user, item_sources_dir, app):
    response = upload(
        user_client,
        image_file(),
        image_file("b.jpg", png(format="JPEG")),
        found_on="https://site.test/gallery",
    )

    assert response.status_code == 201
    first, second = response.json()
    assert first["type"] == "image"
    assert first["title"] == "Holiday Photo"
    assert first["url"] == ""
    assert first["found_on"] == "https://site.test/gallery"
    assert first["status"] == "done"
    assert first["page"] is None
    assert first["image"]["mime"] == "image/png"
    assert first["image"]["original"] == first["thumbnail"]
    assert second["image"]["mime"] == "image/jpeg"
    item = Item.objects.get(id=ids.decode(first["id"]))
    original = item.sources.get(kind=ItemSource.Kind.ORIGINAL)
    assert original.path.read_bytes() == png()
    assert original.run.step.name == "save_original"
    assert user_client.get(first["image"]["original"])["Content-Type"] == "image/png"
    jobs = [j["task_name"] for j in app.connector.jobs.values()]
    assert jobs == ["apps.items.tasks.process_upload"] * 2


def test_upload_dimensions_in_the_background(user_client, item_sources_dir, app):
    body = upload(user_client, image_file(body=png(40, 30))).json()[0]
    assert body["image"]["width"] is None

    (job,) = app.connector.jobs.values()
    process_upload(**job["args"])

    detail = user_client.get(f"{ITEMS}/{body['id']}").json()
    assert (detail["image"]["width"], detail["image"]["height"]) == (40, 30)
    item = Item.objects.get(id=ids.decode(body["id"]))
    runs = ItemStepRun.objects.filter(step__item=item)
    assert {r.step.name: r.outcome for r in runs} == {
        "save_original": "ok",
        "dimensions": "ok",
    }
    assert len({r.run_id for r in runs}) == 1


@pytest.mark.parametrize(
    "files, form, message",
    [
        (
            [image_file(), image_file("a.txt", b"not an image")],
            {},
            "a.txt: Not an image.",
        ),
        ([image_file("a.bmp", png(format="BMP"))], {}, "a.bmp: Not a JPEG"),
        ([image_file()], {"found_on": "nope"}, "Found on"),
    ],
    ids=["not-an-image", "bmp", "found-on"],
)
def test_upload_rejected_saves_nothing(
    user_client, item_sources_dir, files, form, message
):
    count = Item.objects.count()

    response = upload(user_client, *files, **form)

    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert Item.objects.count() == count


def test_upload_size_limit(user_client, item_sources_dir, monkeypatch):
    monkeypatch.setattr(image_items, "MAX_BYTES", 10)

    response = upload(user_client, image_file())

    assert response.status_code == 400
    assert "larger than 50 MB" in response.json()["detail"]


def test_upload_with_token(client, user, item_sources_dir):
    from apps.users.models import ApiToken

    _, key = ApiToken.create(user, "shortcut")
    response = client.post(
        f"{ITEMS}/images",
        {"file": [image_file()]},
        HTTP_AUTHORIZATION=f"Bearer {key}",
    )

    assert response.status_code == 201


def test_retry_upload_reads_dimensions_again(user_client, item_sources_dir, app):
    body = upload(user_client, image_file(body=png(5, 4))).json()[0]

    fetch_item(item_id=str(ids.decode(body["id"])))

    item = Item.objects.get(id=ids.decode(body["id"]))
    assert (item.image.width, item.image.height) == (5, 4)


# Image URLs


def test_image_url_becomes_image_item(user, item_sources_dir, monkeypatch):
    item = Item.objects.create(user=user, url="https://x.test/p", url_submitted="x")
    url = "https://cdn.test/photos/Big%20Cat.webp"
    monkeypatch.setattr(
        fetch,
        "download",
        lambda u: fetch.Download(url, "image/webp", None, png(7, 9, "WEBP"), 200),
    )

    fetch.fetch(item, steps.new_run_id())

    item = get(item)
    assert item.type == Item.Type.IMAGE
    assert item.title == "Big Cat"
    assert item.url == url
    assert item.fetched_at
    assert (item.image.width, item.image.height) == (7, 9)
    assert item.sources.get(kind=ItemSource.Kind.ORIGINAL).url == url
    assert steps.status(item) == (Item.Status.DONE, "")
    assert [s.name for s in item.steps.all()] == [
        "fetch_http",
        "save_original",
        "dimensions",
    ]


def test_image_url_that_isnt_an_image_fails(user, item_sources_dir, monkeypatch):
    item = Item.objects.create(user=user, url="https://x.test/p", url_submitted="x")
    monkeypatch.setattr(
        fetch,
        "download",
        lambda u: fetch.Download(u, "image/png", None, b"<html>", 200),
    )

    with pytest.raises(image_items.NotAnImage):
        fetch.fetch(item, steps.new_run_id())

    assert steps.status(get(item)) == (Item.Status.FAILED, "Not an image.")


# Status


def test_status_pending_fetching_done_failed(user):
    item = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    assert steps.status(get(item)) == (Item.Status.PENDING, "")

    steps.need(item, "fetch_http")
    assert steps.status(get(item))[0] == Item.Status.FETCHING

    run_id = steps.new_run_id()
    with steps.run(item, "fetch_http", run_id):
        assert steps.status(get(item))[0] == Item.Status.FETCHING
    item.type = Item.Type.PAGE
    item.save()
    PageItem.objects.create(item=item)
    with steps.run(item, "extract", run_id):
        pass
    assert steps.status(get(item)) == (Item.Status.DONE, "")


def test_optional_step_failing_leaves_item_done(item):
    with pytest.raises(RuntimeError):
        with steps.run(item, "tag", steps.new_run_id()):
            raise RuntimeError("Model timed out.")

    assert steps.status(get(item)) == (Item.Status.DONE, "")
    assert steps.state(item.steps.get(name="tag")) == Outcome.FAILED


def test_later_success_replaces_failure(item):
    with steps.run(item, "extract", steps.new_run_id()) as run:
        run.finish(Outcome.NO_CONTENT, "No article content found.")
    assert steps.status(get(item)) == (
        Item.Status.FAILED,
        "No article content found.",
    )

    with steps.run(item, "extract", steps.new_run_id()):
        pass
    assert steps.status(get(item)) == (Item.Status.DONE, "")


def test_list_status_without_query_per_item(user_client, django_assert_max_num_queries):
    with django_assert_max_num_queries(8):
        items = user_client.get(ITEMS).json()

    assert {i["status"] for i in items} == {"done"}


# List images


def test_list_thumbnail_sharing_image_else_head_screenshot(
    user_client, item, item_sources_dir
):
    def thumbnail():
        (row,) = [i for i in user_client.get(ITEMS).json() if i["title"] == item.title]
        return row["thumbnail"]

    assert thumbnail() is None
    head = ItemSource.objects.create(
        item=item,
        kind="screenshot_head",
        filename="h.png",
        url=item.url,
        mime="image/png",
        size=1,
        sha256="x",
    )
    assert thumbnail() == images.local_url(item, head.filename)
    og = ItemSource.objects.create(
        item=item,
        kind="og_image",
        filename="o.png",
        url=item.url,
        mime="image/png",
        size=1,
        sha256="y",
    )
    assert thumbnail() == images.local_url(item, og.filename)


# Image steps for pages


def test_save_images_records_its_steps(item, item_sources_dir):
    run_id = steps.new_run_id()

    save_images(item_id=str(item.id), run_id=str(run_id))

    runs = {r.step.name: r for r in ItemStepRun.objects.filter(step__item=item)}
    assert runs["images"].outcome == Outcome.OK
    assert runs["images"].run_id == run_id
    assert (runs["og_image"].outcome, runs["og_image"].message) == (
        Outcome.SKIPPED,
        "No sharing image.",
    )


def test_image_item_has_no_page(user, item_sources_dir, monkeypatch):
    item = Item.objects.create(user=user, type=Item.Type.IMAGE, title="x")
    ImageItem.objects.create(item=item)

    item = Item.objects.get(pk=item.pk)
    assert item.detail == item.image
    assert not PageItem.objects.filter(item=item).exists()
