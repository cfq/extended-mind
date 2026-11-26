import uuid

from django.db import migrations


def to_pages(apps, schema_editor):
    """Every existing item is a page. Its old status becomes an extract
    step with one run, so the derived status stays what it was."""
    Item = apps.get_model("items", "Item")
    PageItem = apps.get_model("items", "PageItem")
    ItemStep = apps.get_model("items", "ItemStep")
    ItemStepRun = apps.get_model("items", "ItemStepRun")
    outcomes = {"done": "ok", "failed": "failed"}
    for item in Item.objects.all():
        PageItem.objects.create(
            item=item,
            author=item.author,
            meta=item.meta,
            text=item.text,
            markdown=item.markdown,
        )
        item.type = "page"
        item.save(update_fields=["type"])
        outcome = outcomes.get(item.status)
        if outcome is None:
            continue
        step = ItemStep.objects.create(item=item, name="extract", position=0)
        when = item.fetched_at or item.created_at
        ItemStepRun.objects.create(
            step=step,
            run_id=uuid.uuid7(),
            outcome=outcome,
            started_at=when,
            finished_at=when,
            message=item.error,
            meta={"migrated": True},
        )


class Migration(migrations.Migration):
    dependencies = [("items", "0009_item_types")]

    operations = [migrations.RunPython(to_pages, migrations.RunPython.noop)]
