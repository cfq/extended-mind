import re

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from apps.items.models import Item, ItemTag, ItemTagRemoval, Tag

MAX_NAME = 50
MAX_PAGE_TAGS = 5
# Page tags that say nothing.
IGNORED = {"uncategorized", "uncategorised", "general", "misc", "other", "blog"}

AUTO = {ItemTag.Source.PAGE, ItemTag.Source.MODEL}


def normalize(name: str) -> str:
    """Trimmed, single-spaced, lowercase; empty if unusable."""
    name = re.sub(r"\s+", " ", name or "").strip().lower()
    if len(name) > MAX_NAME or not re.search(r"\w", name):
        return ""
    return name


def page_tags(categories: list[str] | None, tags: list[str] | None) -> list[str]:
    """Tags a page declares (keywords, article:tag, article:section)."""
    names = []
    for value in [*(tags or []), *(categories or [])]:
        # Meta keywords arrive as one comma-separated string.
        for part in value.split(","):
            name = normalize(part)
            if name and name not in IGNORED and name not in names:
                names.append(name)
    return names[:MAX_PAGE_TAGS]


def get_or_create_tag(user, name: str) -> Tag:
    tag = Tag.objects.filter(user=user, name=name).first()
    if tag:
        return tag
    base = slugify(name)[:50] or "tag"
    slug, n = base, 1
    # "c++" and "c#" both slugify to "c".
    while Tag.objects.filter(user=user, slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    try:
        with transaction.atomic():
            return Tag.objects.create(user=user, name=name, slug=slug)
    except IntegrityError:
        # Created concurrently.
        return Tag.objects.get(user=user, name=name)


def add_tags(item: Item, names: list[str], source: str) -> list[ItemTag]:
    """Adds tags to an item. Automatic sources skip tags the user removed;
    a manual add takes over an automatic link and clears its removal."""
    added = []
    names = [n for n in dict.fromkeys(normalize(n) for n in names) if n]
    if source in AUTO:
        removed = set(item.tag_removals.values_list("name", flat=True))
        names = [n for n in names if n not in removed]
    for name in names:
        tag = get_or_create_tag(item.user, name)
        link, created = ItemTag.objects.get_or_create(
            item=item, tag=tag, defaults={"source": source}
        )
        if not created and source == ItemTag.Source.MANUAL and link.source in AUTO:
            link.source = source
            link.save(update_fields=["source"])
        if source == ItemTag.Source.MANUAL:
            item.tag_removals.filter(name=name).delete()
        if created:
            added.append(link)
    return added


def remove_tag(item: Item, tag: Tag):
    if item.item_tags.filter(tag=tag).delete()[0]:
        ItemTagRemoval.objects.get_or_create(item=item, name=tag.name)
