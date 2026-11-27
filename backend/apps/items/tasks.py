import uuid

from django.conf import settings
from procrastinate.contrib.django import app

from apps.items import autotag, fetch, image_items, images, steps
from apps.items.models import Item, ItemStepRun

Outcome = ItemStepRun.Outcome


def pass_id(run_id: str | None) -> uuid.UUID:
    return uuid.UUID(run_id) if run_id else steps.new_run_id()


def usable_page(item_id: str) -> Item | None:
    item = Item.objects.filter(id=item_id).first()
    if (
        item
        and item.type == Item.Type.PAGE
        and steps.status(item)[0] == Item.Status.DONE
    ):
        return item
    return None


@app.task
def fetch_item(item_id: str, run_id: str | None = None):
    """A pass through the pipeline: a save or a retry. Failures are on the
    item's steps; re-raised so the job is recorded as failed too."""
    item = Item.objects.get(id=item_id)
    rid = pass_id(run_id)
    if item.type == Item.Type.IMAGE and not item.url:
        # An upload: nothing to fetch, its file is already saved.
        image_items.dimensions(item, rid)
        return
    fetch.fetch(item, rid)
    if item.type == Item.Type.PAGE:
        # Own jobs: a slow or failed model never holds up fetches.
        tag_item.defer(item_id=item_id, run_id=str(rid))
        save_images.defer(item_id=item_id, run_id=str(rid))


@app.task
def process_upload(item_id: str, run_id: str):
    item = Item.objects.filter(id=item_id).first()
    if item:
        image_items.dimensions(item, pass_id(run_id))


def run_images(item: Item, run_id: uuid.UUID):
    with steps.run(item, "images", run_id) as run:
        saved = images.save_images(item, run.row)
        message = f"{len(saved.failed)} failed." if saved.failed else ""
        run.finish(Outcome.OK, message, saved=saved.new, failed=saved.failed)


def run_og_image(item: Item, run_id: uuid.UUID):
    with steps.run(item, "og_image", run_id) as run:
        result = images.save_og_image(item, run.row)
        if result == "none":
            run.finish(Outcome.SKIPPED, "No sharing image.")
        else:
            run.note(result=result)


@app.task
def save_images(item_id: str, run_id: str | None = None):
    item = usable_page(item_id)
    if item is None:
        return
    rid = pass_id(run_id)
    run_images(item, rid)
    run_og_image(item, rid)


@app.task(queue="tags")
def tag_item(item_id: str, run_id: str | None = None):
    item = usable_page(item_id)
    if item is None:
        return
    with steps.run(item, "tag", pass_id(run_id)) as run:
        if not settings.OLLAMA_URL:
            run.finish(Outcome.SKIPPED, "No model configured.")
            return
        links = autotag.autotag(item)
        run.note(model=settings.OLLAMA_MODEL, tags=[link.tag.name for link in links])


# Retries: a step and everything that depends on it (steps.STEPS).


def in_its_queue(name: str):
    """A step whose job runs on another queue: deferred there."""
    tasks = {"tag": tag_item}

    def defer(item: Item, run_id: uuid.UUID):
        tasks[name].defer(item_id=str(item.id), run_id=str(run_id))

    return defer


def when_usable(run_step):
    """Page extras run only once the page is usable."""

    def run_if_usable(item: Item, run_id: uuid.UUID):
        if usable_page(str(item.id)):
            run_step(item, run_id)

    return run_if_usable


# Each step on its own, for a retry.
RETRY = {
    "fetch_browser": fetch.browse,
    "extract": fetch.extract_saved,
    "images": when_usable(run_images),
    "og_image": when_usable(run_og_image),
    "tag": in_its_queue("tag"),
    "save_original": image_items.recheck,
    "dimensions": image_items.dimensions,
}
assert set(RETRY) | {"fetch_http"} == set(steps.STEPS)


def retries_whole_pass(item: Item, name: str) -> bool:
    """Retrying the fetch, or the original of an image saved from a URL,
    means fetching again: the whole pipeline."""
    return name == "fetch_http" or (name == "save_original" and bool(item.url))


def retry_plan(item: Item, name: str) -> list[str]:
    """The steps a retry of this step runs, in order."""
    if retries_whole_pass(item, name):
        return list(steps.STEPS)
    return [name, *steps.dependents(name)]


@app.task
def retry_step(item_id: str, name: str, run_id: str):
    """One pass: the step, then everything that depends on it. Stops at
    the first step that raises; its run records why."""
    item = Item.objects.filter(id=item_id).first()
    if item is None:
        return
    if retries_whole_pass(item, name):
        fetch_item(item_id=item_id, run_id=run_id)
        return
    rid = uuid.UUID(run_id)
    for step in retry_plan(item, name):
        RETRY[step](item, rid)
