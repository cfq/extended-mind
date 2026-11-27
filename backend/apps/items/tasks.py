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


@app.task
def save_images(item_id: str, run_id: str | None = None):
    item = usable_page(item_id)
    if item is None:
        return
    rid = pass_id(run_id)
    with steps.run(item, "images", rid) as run:
        saved = images.save_images(item, run.row)
        message = f"{len(saved.failed)} failed." if saved.failed else ""
        run.finish(Outcome.OK, message, saved=saved.new, failed=saved.failed)
    with steps.run(item, "og_image", rid) as run:
        result = images.save_og_image(item, run.row)
        if result == "none":
            run.finish(Outcome.SKIPPED, "No sharing image.")
        else:
            run.note(result=result)


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
