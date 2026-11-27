import hashlib

from apps.items.models import Item, ItemSource, ItemStepRun


def save_source(
    item: Item,
    kind: str,
    filename: str,
    url: str,
    mime: str,
    body: bytes,
    run: ItemStepRun | None = None,
) -> ItemSource:
    """Writes the file and its row. A retry replaces the previous file of
    this kind."""
    for old in item.sources.filter(kind=kind):
        old.path.unlink(missing_ok=True)
        old.delete()
    item.sources_dir.mkdir(parents=True, exist_ok=True)
    (item.sources_dir / filename).write_bytes(body)
    return ItemSource.objects.create(
        item=item,
        kind=kind,
        filename=filename,
        url=url,
        mime=mime,
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        run=run,
    )
