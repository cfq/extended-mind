from datetime import date, datetime

from ninja import Schema

from apps.items import ids


class ItemIn(Schema):
    url: str


class TagIn(Schema):
    name: str


class TagOut(Schema):
    name: str
    slug: str
    count: int


class ItemTagOut(Schema):
    name: str
    slug: str
    source: str

    @staticmethod
    def resolve_name(obj):
        return obj.tag.name

    @staticmethod
    def resolve_slug(obj):
        return obj.tag.slug


class ItemSummaryOut(Schema):
    id: str
    url: str
    url_submitted: str
    status: str
    error: str
    title: str
    description: str
    author: str
    site_name: str
    published_at: date | None
    created_at: datetime
    fetched_at: datetime | None
    tags: list[ItemTagOut]

    @staticmethod
    def resolve_id(obj):
        return ids.encode(obj.id)

    @staticmethod
    def resolve_tags(obj):
        return item_tags(obj)


def item_tags(item) -> list:
    # Sorted in Python so a prefetch_related cache is used.
    return sorted(item.item_tags.all(), key=lambda link: link.tag.name)


class ScreenshotsOut(Schema):
    full: str | None
    head: str | None


class ItemOut(ItemSummaryOut):
    markdown: str
    screenshots: ScreenshotsOut
    pdf: str | None
    # og:, twitter: and article: meta tags as the page declares them.
    meta: dict
    og_image: str | None

    @staticmethod
    def resolve_screenshots(obj):
        from apps.items.images import local_url
        from apps.items.models import ItemSource

        kinds = {
            ItemSource.Kind.SCREENSHOT_FULL: "full",
            ItemSource.Kind.SCREENSHOT_HEAD: "head",
        }
        urls = {"full": None, "head": None}
        for source in obj.sources.filter(kind__in=kinds):
            urls[kinds[source.kind]] = local_url(obj, source.filename)
        return urls

    @staticmethod
    def resolve_pdf(obj):
        from apps.items.images import local_url
        from apps.items.models import ItemSource

        source = obj.sources.filter(kind=ItemSource.Kind.PDF).first()
        return local_url(obj, source.filename) if source else None

    @staticmethod
    def resolve_og_image(obj):
        from apps.items.images import local_url
        from apps.items.models import ItemSource

        source = obj.sources.filter(kind=ItemSource.Kind.OG_IMAGE).first()
        return local_url(obj, source.filename) if source else None
