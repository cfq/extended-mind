from procrastinate.contrib.django import app

from apps.items import fetch
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
