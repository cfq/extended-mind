from django.core.management.base import BaseCommand

from apps.items import fetch, tagging
from apps.items.models import Item, ItemSource, ItemTag
from apps.items.tasks import save_images


class Command(BaseCommand):
    help = (
        "Re-run extraction and page tags from saved HTML, then queue image "
        "downloads. No page fetches; saved images aren't downloaded again."
    )

    def handle(self, *args, **options):
        done = failed = 0
        # The rendered page when there is one, as the fetch prefers it.
        best = {}
        sources = ItemSource.objects.filter(
            kind__in=[ItemSource.Kind.HTML, ItemSource.Kind.RENDERED]
        ).select_related("item")
        for source in sources:
            if source.item_id not in best or source.kind == ItemSource.Kind.RENDERED:
                best[source.item_id] = source
        items_with_source = set(best)
        for source in best.values():
            item = source.item
            try:
                # Bytes: trafilatura detects the encoding itself.
                tags = fetch.extract(item, source.path.read_bytes())
            except (OSError, fetch.FetchError) as e:
                failed += 1
                self.stderr.write(f"{item.pk}: {e}")
                continue
            item.save()
            tagging.add_tags(item, tags, ItemTag.Source.PAGE)
            # Markdown is back to original image URLs; this swaps them again.
            save_images.defer(item_id=str(item.pk))
            done += 1
        skipped = Item.objects.exclude(pk__in=items_with_source).count()
        self.stdout.write(f"Re-extracted {done}, skipped {skipped}, failed {failed}.")
