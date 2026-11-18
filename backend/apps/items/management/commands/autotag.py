from django.core.management.base import BaseCommand

from apps.items import autotag
from apps.items.models import Item


class Command(BaseCommand):
    help = "Add model tags to fetched items. Tags you removed stay removed."

    def handle(self, *args, **options):
        tagged = added = 0
        for item in Item.objects.filter(status=Item.Status.DONE):
            links = autotag.autotag(item)
            tagged += bool(links)
            added += len(links)
        self.stdout.write(f"Added {added} tags to {tagged} items.")
