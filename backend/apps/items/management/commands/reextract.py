from django.core.management.base import BaseCommand

from apps.items import fetch
from apps.items.models import Item, ItemSource


class Command(BaseCommand):
    help = "Re-run extraction on items from their saved HTML. No network."

    def handle(self, *args, **options):
        done = failed = 0
        sources = ItemSource.objects.filter(kind=ItemSource.Kind.HTML).select_related(
            "item"
        )
        items_with_source = set()
        for source in sources:
            item = source.item
            items_with_source.add(item.pk)
            try:
                # Bytes: trafilatura detects the encoding itself.
                fetch.extract(item, source.path.read_bytes())
            except (OSError, fetch.FetchError) as e:
                failed += 1
                self.stderr.write(f"{item.pk}: {e}")
                continue
            item.save()
            done += 1
        skipped = Item.objects.exclude(pk__in=items_with_source).count()
        self.stdout.write(f"Re-extracted {done}, skipped {skipped}, failed {failed}.")
