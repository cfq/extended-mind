import pytest

from apps.items import autotag, fetch, steps
from apps.items.models import Item, PageItem
from apps.items.tasks import fetch_item, tag_item


@pytest.fixture
def pending(user):
    return Item.objects.create(user=user, url="https://x.test", url_submitted="x")


def become_page(item, run_id):
    item.type = Item.Type.PAGE
    item.save()
    PageItem.objects.create(item=item, text="Some text")
    with steps.run(item, "extract", run_id):
        pass


def test_fetch_item_runs_a_pass(pending, monkeypatch, app):
    passes = []

    def fake_fetch(item, run_id):
        passes.append(run_id)
        become_page(item, run_id)

    monkeypatch.setattr(fetch, "fetch", fake_fetch)

    fetch_item(item_id=str(pending.id))

    assert len(passes) == 1
    assert steps.status(Item.objects.get(pk=pending.pk))[0] == Item.Status.DONE


def test_fetch_item_failed(pending, monkeypatch):
    def fail(item, run_id):
        with steps.run(item, "fetch_http", run_id):
            raise fetch.FetchError("Nope.")

    monkeypatch.setattr(fetch, "fetch", fail)

    with pytest.raises(fetch.FetchError):
        fetch_item(item_id=str(pending.id))

    item = Item.objects.get(pk=pending.pk)
    assert steps.status(item) == (Item.Status.FAILED, "Nope.")


def test_fetch_item_queues_tagging_and_images_with_its_pass(pending, monkeypatch, app):
    monkeypatch.setattr(fetch, "fetch", become_page)

    fetch_item(item_id=str(pending.id))

    jobs = [
        (j["task_name"], j["queue_name"], j["args"]["run_id"])
        for j in app.connector.jobs.values()
    ]
    run_id = str(pending.steps.get().runs.get().run_id)
    assert jobs == [
        ("apps.items.tasks.tag_item", "tags", run_id),
        ("apps.items.tasks.save_images", "default", run_id),
    ]


def test_failed_fetch_queues_nothing(pending, monkeypatch, app):
    def fail(item, run_id):
        raise fetch.FetchError("nope")

    monkeypatch.setattr(fetch, "fetch", fail)

    with pytest.raises(fetch.FetchError):
        fetch_item(item_id=str(pending.id))

    assert not app.connector.jobs


def test_tag_item_only_done_pages(pending, monkeypatch, settings):
    settings.OLLAMA_URL = "http://ollama.test"
    calls = []
    monkeypatch.setattr(autotag, "autotag", lambda item: calls.append(item) or [])

    tag_item(item_id=str(pending.id))
    become_page(pending, steps.new_run_id())
    tag_item(item_id=str(pending.id))

    assert [item.pk for item in calls] == [pending.pk]
    assert steps.state(pending.steps.get(name="tag")) == "ok"


def test_tag_item_skipped_without_model(pending, settings):
    settings.OLLAMA_URL = ""
    become_page(pending, steps.new_run_id())

    tag_item(item_id=str(pending.id))

    run = pending.steps.get(name="tag").runs.get()
    assert (run.outcome, run.message) == ("skipped", "No model configured.")
