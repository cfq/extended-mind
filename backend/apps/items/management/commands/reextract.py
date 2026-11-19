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
        # Per item, plain HTML first, then rendered: the order fetch uses.
        order = [ItemSource.Kind.HTML, ItemSource.Kind.RENDERED]
        by_item: dict = {}
        sources = ItemSource.objects.filter(kind__in=order).select_related("item")
        for source in sorted(sources, key=lambda s: order.index(s.kind)):
            by_item.setdefault(source.item_id, []).append(source)
        items_with_source = set(by_item)
        for sources in by_item.values():
            item = sources[0].item
            tags, errors = None, []
            for source in sources:
                try:
                    # Bytes: trafilatura detects the encoding itself.
                    tags = fetch.extract(item, source.path.read_bytes())
                    break
                except (OSError, fetch.FetchError) as e:
                    errors.append(f"{source.kind}: {e}")
            if tags is None:
                failed += 1
                self.stderr.write(f"{item.pk}: {'; '.join(errors)}")
                continue
            item.save()
            tagging.add_tags(item, tags, ItemTag.Source.PAGE)
            # Markdown is back to original image URLs; this swaps them again.
            save_images.defer(item_id=str(item.pk))
            done += 1
        skipped = Item.objects.exclude(pk__in=items_with_source).count()
        self.stdout.write(f"Re-extracted {done}, skipped {skipped}, failed {failed}.")
