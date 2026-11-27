from django.core.management.base import BaseCommand

from apps.items.models import Item, ItemSource
from apps.items.pipeline import flow, steps
from apps.items.pipeline.download import FetchError
from apps.items.tasks import save_images


class Command(BaseCommand):
    help = (
        "Re-run extraction and page tags from saved HTML, then queue image "
        "downloads. No page fetches; saved images aren't downloaded again. "
        "Each item gets a new pass with its extract runs."
    )

    def handle(self, *args, **options):
        done = failed = 0
        kinds = [ItemSource.Kind.HTML, ItemSource.Kind.RENDERED]
        items = Item.objects.filter(sources__kind__in=kinds).distinct()
        for item in items:
            run_id = steps.new_run_id()
            try:
                flow.extract_saved(item, run_id)
            except FetchError as e:
                failed += 1
                self.stderr.write(f"{item.pk}: {e}")
                continue
            # Markdown is back to original image URLs; this swaps them again.
            save_images.defer(item_id=str(item.pk), run_id=str(run_id))
            done += 1
        skipped = Item.objects.exclude(sources__kind__in=kinds).count()
        self.stdout.write(f"Re-extracted {done}, skipped {skipped}, failed {failed}.")
