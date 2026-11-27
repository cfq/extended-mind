import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.items import browser, fetch, ids, steps
from apps.items.models import Item, ItemSource, ItemStep, ItemStepRun
from apps.items.tasks import process_upload, retry_plan, retry_step, tag_item

ITEMS = "/api/v1/items"
Outcome = ItemStepRun.Outcome


def runs(item):
    rows = ItemStepRun.objects.filter(step__item=item).order_by("started_at", "id")
    return [(r.step.name, r.outcome) for r in rows]


def jobs(app):
    return [(j["task_name"], j["args"]) for j in app.connector.jobs.values()]


def retry(client, item, name):
    return client.post(f"{ITEMS}/{ids.encode(item.id)}/steps/{name}/retry")


def run_jobs(app, task_name, task):
    for job in list(app.connector.jobs.values()):
        if job["task_name"] == task_name:
            task(**job["args"])


# The step definition


def test_steps_come_after_what_they_depend_on():
    seen = set()
    for name, step in steps.STEPS.items():
        assert set(step.depends_on) <= seen, name
        seen.add(name)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("fetch_browser", ["extract", "images", "og_image", "tag"]),
        ("extract", ["images", "og_image", "tag"]),
        ("tag", []),
        ("save_original", ["dimensions"]),
        (
            "fetch_http",
            [
                "fetch_browser",
                "extract",
                "images",
                "og_image",
                "tag",
                "save_original",
                "dimensions",
            ],
        ),
    ],
)
def test_dependents(name, expected):
    assert steps.dependents(name) == expected


def test_core_and_required_from_the_definition():
    assert steps.CORE == {"fetch_http", "fetch_browser", "extract", "save_original"}
    assert steps.REQUIRED == {"page": "extract", "image": "save_original"}


def test_ordered_by_pipeline_not_creation(item):
    # Migrated items got extract first.
    steps.need(item, "tag", "fetch_http")

    assert [s.name for s in steps.ordered(list(item.steps.all()))] == [
        "fetch_http",
        "extract",
        "tag",
    ]


def test_queued_run_becomes_the_run(item):
    run_id = steps.new_run_id()
    steps.queue(item, "tag", run_id)
    assert steps.state(item.steps.get(name="tag")) == Outcome.QUEUED

    with steps.run(item, "tag", run_id):
        pass

    assert runs(item)[-1] == ("tag", "ok")
    assert item.steps.get(name="tag").runs.count() == 1


def test_queued_core_step_means_fetching(item):
    steps.queue(item, "extract", steps.new_run_id())

    assert steps.status(Item.objects.get(pk=item.pk))[0] == Item.Status.FETCHING


# Activity


def test_activity_newest_first_with_steps(user_client, other_user, item):
    Item.objects.create(user=other_user, url="https://x.test", url_submitted="x")
    steps.need(item, "fetch_http")

    rows = user_client.get(f"{ITEMS}/activity?limit=2").json()

    assert len(rows) == 2
    assert rows[0]["title"] == "Why Don’t We Live in an Art Nouveau World?"
    (row,) = [
        r
        for r in user_client.get(f"{ITEMS}/activity").json()
        if r["id"] == ids.encode(item.id)
    ]
    assert [(s["name"], s["state"]) for s in row["steps"]] == [
        ("fetch_http", "pending"),
        ("extract", "ok"),
    ]
    assert {"thumbnail", "status", "url"} <= row.keys()


# Retry endpoint


def test_retry_queues_the_step(user_client, item, app):
    response = retry(user_client, item, "extract")

    assert response.status_code == 202
    (extract,) = [s for s in response.json()["steps"] if s["name"] == "extract"]
    assert extract["state"] == "queued"
    ((name, args),) = jobs(app)
    assert name == "apps.items.tasks.retry_step"
    assert args["name"] == "extract"
    run = item.steps.get(name="extract").runs.get(outcome=Outcome.QUEUED)
    assert args["run_id"] == str(run.run_id)


def test_retry_refused_while_in_progress(user_client, item, app):
    assert retry(user_client, item, "extract").status_code == 202

    response = retry(user_client, item, "extract")

    assert response.status_code == 409
    assert len(jobs(app)) == 1


def test_retry_refused_while_a_dependent_is_busy(user_client, item, app):
    steps.queue(item, "tag", steps.new_run_id())

    assert retry(user_client, item, "extract").status_code == 409
    assert retry(user_client, item, "tag").status_code == 409


@pytest.mark.parametrize("name", ["nope", "dimensions"])
def test_retry_unknown_or_absent_step(user_client, item, name):
    assert retry(user_client, item, name).status_code == 404


def test_retry_other_users_item(client, other_user, item):
    client.force_login(other_user)

    assert retry(client, item, "extract").status_code == 404


def test_retry_requires_login(client, item):
    assert retry(client, item, "extract").status_code == 401


# Retry job


def test_retry_extract_runs_it_and_its_dependents(
    user_client, item, item_sources_dir, app, settings
):
    settings.OLLAMA_URL = "http://ollama.test"
    retry(user_client, item, "extract")
    (args,) = [a for n, a in jobs(app) if n.endswith("retry_step")]

    retry_step(**args)

    new = ItemStepRun.objects.filter(run_id=args["run_id"])
    assert sorted(r.step.name for r in new) == ["extract", "images", "og_image"]
    assert item.steps.get(name="extract").runs.filter(outcome="queued").count() == 0
    assert all(r.outcome in ("ok", "skipped") for r in new)
    tagging = [a for n, a in jobs(app) if n.endswith("tag_item")]
    assert tagging == [{"item_id": str(item.id), "run_id": args["run_id"]}]


def test_retry_tag_queues_it_on_its_own_queue(
    user_client, item, app, monkeypatch, settings
):
    settings.OLLAMA_URL = "http://ollama.test"
    monkeypatch.setattr("apps.items.autotag.autotag", lambda item: [])
    steps.need(item, "tag")
    retry(user_client, item, "tag")
    run_jobs(app, "apps.items.tasks.retry_step", retry_step)

    run_jobs(app, "apps.items.tasks.tag_item", tag_item)

    tag = item.steps.get(name="tag")
    assert [r.outcome for r in tag.runs.all()] == ["ok"]


def test_retry_extract_failure_stops_there(user_client, item, item_sources_dir, app):
    for path in item.sources_dir.glob("*.html"):
        path.unlink()
    retry(user_client, item, "extract")

    with pytest.raises(fetch.FetchError):
        run_jobs(app, "apps.items.tasks.retry_step", retry_step)

    assert runs(item)[-1] == ("extract", "failed")
    assert not ItemStep.objects.filter(item=item, name="images").exists()
    status = steps.status(Item.objects.get(pk=item.pk))
    assert status[0] == Item.Status.FAILED


def test_retry_browser_visits_again_then_extracts(
    user_client, item, item_sources_dir, app, settings, monkeypatch
):
    settings.BROWSER_URL = "ws://browser.test/"
    steps.need(item, "fetch_browser")
    html = (item.sources_dir / item.sources.get(kind="html").filename).read_text()
    monkeypatch.setattr(
        browser,
        "visit",
        lambda url: browser.Visit(
            url=url, status=200, html=html, head=b"head", full=b"full", pdf=None
        ),
    )
    retry(user_client, item, "fetch_browser")

    run_jobs(app, "apps.items.tasks.retry_step", retry_step)

    names = [n for n, o in runs(item) if o != "running"]
    assert names[-4:] == ["fetch_browser", "extract", "images", "og_image"]
    kinds = set(item.sources.values_list("kind", flat=True))
    assert {"rendered", "screenshot_full", "screenshot_head"} <= kinds


def test_retry_fetch_is_the_whole_pass(user_client, item, app, monkeypatch):
    passes = []
    monkeypatch.setattr(fetch, "fetch", lambda item, run_id: passes.append(run_id))
    steps.need(item, "fetch_http")
    retry(user_client, item, "fetch_http")

    run_jobs(app, "apps.items.tasks.retry_step", retry_step)

    assert len(passes) == 1
    assert retry_plan(item, "fetch_http") == list(steps.STEPS)


def test_retry_upload_original_rechecks_then_dimensions(
    user_client, item_sources_dir, app
):
    out = io.BytesIO()
    Image.new("RGB", (12, 8)).save(out, "PNG")
    file = SimpleUploadedFile("a.png", out.getvalue(), content_type="image/png")
    body = user_client.post(f"{ITEMS}/images", {"file": [file]}).json()[0]
    item = Item.objects.get(id=ids.decode(body["id"]))
    run_jobs(app, "apps.items.tasks.process_upload", process_upload)

    assert retry(user_client, item, "save_original").status_code == 202
    run_jobs(app, "apps.items.tasks.retry_step", retry_step)

    last_pass = ItemStepRun.objects.order_by("-started_at").first().run_id
    names = ItemStepRun.objects.filter(run_id=last_pass).values_list(
        "step__name", flat=True
    )
    assert sorted(names) == ["dimensions", "save_original"]
    assert item.sources.filter(kind=ItemSource.Kind.ORIGINAL).count() == 1
