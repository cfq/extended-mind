from datetime import date, datetime

from ninja import Schema

from apps.items import ids, steps
from apps.items.images import local_url
from apps.items.models import Item, ItemSource

THUMBNAILS = {
    Item.Type.IMAGE: (ItemSource.Kind.ORIGINAL,),
    Item.Type.PAGE: (ItemSource.Kind.OG_IMAGE, ItemSource.Kind.SCREENSHOT_HEAD),
}


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
    # page, image; "" until the fetch decides.
    type: str
    url: str
    url_submitted: str
    found_on: str | None
    # Derived from the item's steps.
    status: str
    error: str
    title: str
    description: str
    site_name: str
    published_at: date | None
    created_at: datetime
    fetched_at: datetime | None
    tags: list[ItemTagOut]
    # For lists: the image itself, or a page's sharing image, else its
    # head screenshot.
    thumbnail: str | None

    @staticmethod
    def resolve_id(obj):
        return ids.encode(obj.id)

    @staticmethod
    def resolve_status(obj):
        return steps.status(obj)[0]

    @staticmethod
    def resolve_error(obj):
        return steps.status(obj)[1]

    @staticmethod
    def resolve_tags(obj):
        return item_tags(obj)

    @staticmethod
    def resolve_thumbnail(obj):
        kinds = THUMBNAILS.get(obj.type, ())
        # In Python, so prefetched sources are used.
        by_kind = {s.kind: s for s in obj.sources.all() if s.kind in kinds}
        for kind in kinds:
            if kind in by_kind:
                return local_url(obj, by_kind[kind].filename)
        return None


def item_tags(item) -> list:
    # Sorted in Python so a prefetch_related cache is used.
    return sorted(item.item_tags.all(), key=lambda link: link.tag.name)


class ScreenshotsOut(Schema):
    full: str | None
    head: str | None


def source_url(item, kind) -> str | None:
    source = item.sources.filter(kind=kind).first()
    return local_url(item, source.filename) if source else None


class PageOut(Schema):
    author: str
    markdown: str
    # og:, twitter: and article: meta tags as the page declares them.
    meta: dict
    screenshots: ScreenshotsOut
    pdf: str | None
    og_image: str | None

    @staticmethod
    def resolve_screenshots(obj):
        return {
            "full": source_url(obj.item, ItemSource.Kind.SCREENSHOT_FULL),
            "head": source_url(obj.item, ItemSource.Kind.SCREENSHOT_HEAD),
        }

    @staticmethod
    def resolve_pdf(obj):
        return source_url(obj.item, ItemSource.Kind.PDF)

    @staticmethod
    def resolve_og_image(obj):
        return source_url(obj.item, ItemSource.Kind.OG_IMAGE)


class ImageOut(Schema):
    width: int | None
    height: int | None
    # The file: URL, mime type and size in bytes.
    original: str | None
    mime: str | None
    size: int | None

    @staticmethod
    def original_source(obj):
        return obj.item.sources.filter(kind=ItemSource.Kind.ORIGINAL).first()

    @staticmethod
    def resolve_original(obj):
        return source_url(obj.item, ItemSource.Kind.ORIGINAL)

    @staticmethod
    def resolve_mime(obj):
        source = ImageOut.original_source(obj)
        return source.mime if source else None

    @staticmethod
    def resolve_size(obj):
        source = ImageOut.original_source(obj)
        return source.size if source else None


class ItemOut(ItemSummaryOut):
    # One of these, by type; both null until the type is known.
    page: PageOut | None
    image: ImageOut | None

    @staticmethod
    def resolve_page(obj):
        return obj.page if obj.type == Item.Type.PAGE else None

    @staticmethod
    def resolve_image(obj):
        return obj.image if obj.type == Item.Type.IMAGE else None


class StepOut(Schema):
    name: str
    # pending, queued, running, ok, failed, skipped, blocked, no_content
    state: str
    # The latest run's.
    message: str
    finished_at: datetime | None

    @staticmethod
    def resolve_state(obj):
        return steps.state(obj)

    @staticmethod
    def resolve_message(obj):
        run = steps.latest(obj)
        return run.message if run else ""

    @staticmethod
    def resolve_finished_at(obj):
        run = steps.latest(obj)
        return run.finished_at if run else None


class ActivityOut(ItemSummaryOut):
    # In pipeline order.
    steps: list[StepOut]

    @staticmethod
    def resolve_steps(obj):
        return steps.ordered(list(obj.steps.all()))
