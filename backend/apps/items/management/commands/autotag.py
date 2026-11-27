from django.core.management.base import BaseCommand

from apps.items.models import Item
from apps.items.pipeline import steps
from apps.items.tagging import model as autotag


class Command(BaseCommand):
    help = "Add model tags to fetched items. Tags you removed stay removed."

    def handle(self, *args, **options):
        tagged = added = 0
        items = Item.objects.prefetch_related("steps__runs")
        for item in items:
            if steps.status(item)[0] != Item.Status.DONE:
                continue
            links = autotag.autotag(item)
            tagged += bool(links)
            added += len(links)
        self.stdout.write(f"Added {added} tags to {tagged} items.")
