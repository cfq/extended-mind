from procrastinate.contrib.django import app

from apps.items import autotag, fetch, images
from apps.items.models import Item


@app.task
def fetch_item(item_id: str):
    item = Item.objects.get(id=item_id)
    item.status = Item.Status.FETCHING
    item.error = ""
    item.save(update_fields=["status", "error"])
    try:
        fetch.fetch(item)
    except Exception as e:
        item.status = Item.Status.FAILED
        item.error = str(e) or e.__class__.__name__
        item.save(update_fields=["status", "error"])
        # Re-raise so the job is recorded as failed too.
        raise
    # Its own job and queue: a slow or failed model never holds up fetches.
    tag_item.defer(item_id=item_id)
    save_images.defer(item_id=item_id)


@app.task
def save_images(item_id: str):
    item = Item.objects.filter(id=item_id).first()
    if item and item.status == Item.Status.DONE:
        images.save_images(item)


@app.task(queue="tags")
def tag_item(item_id: str):
    item = Item.objects.filter(id=item_id).first()
    if item and item.status == Item.Status.DONE:
        autotag.autotag(item)
