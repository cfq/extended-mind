from django.core.management.base import BaseCommand

from apps.items import fetch, steps, tagging
from apps.items.models import Item, ItemSource, ItemStepRun, ItemTag
from apps.items.tasks import save_images

Outcome = ItemStepRun.Outcome


class Command(BaseCommand):
    help = (
        "Re-run extraction and page tags from saved HTML, then queue image "
        "downloads. No page fetches; saved images aren't downloaded again. "
        "Each item gets a new pass with its extract runs."
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
            run_id = steps.new_run_id()
            item.type = Item.Type.PAGE
            fetch.ensure_page(item)
            tags, errors = None, []
            for source in sources:
                with steps.run(item, "extract", run_id) as run:
                    try:
                        # Bytes: trafilatura detects the encoding itself.
                        tags = fetch.extract(item, source.path.read_bytes())
                    except OSError as e:
                        run.finish(Outcome.FAILED, str(e), source=source.kind)
                    except fetch.FetchError as e:
                        run.finish(Outcome.NO_CONTENT, str(e), source=source.kind)
                    else:
                        run.note(source=source.kind)
                        break
                    errors.append(f"{source.kind}: {run.row.message}")
            if tags is None:
                failed += 1
                self.stderr.write(f"{item.pk}: {'; '.join(errors)}")
                continue
            item.save()
            item.page.save()
            tagging.add_tags(item, tags, ItemTag.Source.PAGE)
            # Markdown is back to original image URLs; this swaps them again.
            save_images.defer(item_id=str(item.pk), run_id=str(run_id))
            done += 1
        skipped = Item.objects.exclude(pk__in=items_with_source).count()
        self.stdout.write(f"Re-extracted {done}, skipped {skipped}, failed {failed}.")
