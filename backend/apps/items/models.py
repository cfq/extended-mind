import shutil
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class ItemManager(models.Manager):
    # Every Item query brings its typed row along: no query per item.
    def get_queryset(self):
        return super().get_queryset().select_related("page", "image")


class Item(models.Model):
    class Type(models.TextChoices):
        PAGE = "page"
        IMAGE = "image"

    # Derived from the item's steps (apps.items.steps.status), not stored.
    class Status(models.TextChoices):
        PENDING = "pending"
        FETCHING = "fetching"
        DONE = "done"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    # Blank until known: a saved URL's type comes from its fetch.
    type = models.CharField(max_length=16, choices=Type.choices, blank=True)
    # The item's own address (page, or image file): what gets fetched.
    # Cleaned; after a fetch, the final URL after redirects. Blank for uploads.
    url = models.URLField(max_length=2048, blank=True)
    url_submitted = models.TextField(blank=True)
    # Where it was seen, when that isn't url: the page an upload came from.
    found_on = models.URLField(max_length=2048, null=True, blank=True)
    site_name = models.TextField(blank=True)
    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    # The content's own date: published (page).
    published_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set when something was downloaded; null for uploads.
    fetched_at = models.DateTimeField(null=True, blank=True)

    objects = ItemManager()

    class Meta:
        ordering = ["-created_at"]

    @property
    def detail(self) -> PageItem | ImageItem | None:
        """The typed row: item.page or item.image, by type."""
        return getattr(self, self.type, None) if self.type else None

    @property
    def short_id(self) -> str:
        # The end of a UUIDv7 is random; the start is a timestamp.
        return self.id.hex[-8:]

    @property
    def sources_dir(self):
        return settings.ITEM_SOURCES_DIR / str(self.id)


class ItemSource(models.Model):
    class Kind(models.TextChoices):
        # The page as the plain HTTP fetch got it.
        HTML = "html"
        # The browser's DOM after JavaScript ran.
        RENDERED = "rendered"
        IMAGE = "image"
        SCREENSHOT_FULL = "screenshot_full"
        SCREENSHOT_HEAD = "screenshot_head"
        # The page printed to PDF, through its print stylesheet.
        PDF = "pdf"
        # The page's sharing image (og:image, twitter:image).
        OG_IMAGE = "og_image"
        # An image item's file, as uploaded or downloaded.
        ORIGINAL = "original"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="sources")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    filename = models.CharField(max_length=255)
    # Pages and screenshots: final URL after redirects. Images: the URL as
    # written in the article's markdown. Sharing image: its absolute URL.
    url = models.URLField(max_length=2048)
    mime = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    # The step run that produced it.
    run = models.ForeignKey(
        "ItemStepRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sources",
    )

    @property
    def path(self):
        return self.item.sources_dir / self.filename


class PageItem(models.Model):
    item = models.OneToOneField(
        Item, primary_key=True, on_delete=models.CASCADE, related_name="page"
    )
    author = models.TextField(blank=True)
    # og:, twitter: and article: meta tags as the page declares them.
    meta = models.JSONField(default=dict, blank=True)
    text = models.TextField(blank=True)
    markdown = models.TextField(blank=True)

    def search_text(self) -> str:
        return self.text


class ImageItem(models.Model):
    item = models.OneToOneField(
        Item, primary_key=True, on_delete=models.CASCADE, related_name="image"
    )
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    # OCR, later.
    text = models.TextField(blank=True)

    def search_text(self) -> str:
        return self.text


class ItemStep(models.Model):
    """A piece of work the pipeline found an item needs. Created pending
    the moment it's known; each attempt is an ItemStepRun."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="steps")
    name = models.CharField(max_length=32)
    # Pipeline order, for display.
    position = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["item", "name"], name="itemstep_item_name"),
        ]

    def __str__(self):
        return self.name


class ItemStepRun(models.Model):
    """One attempt at a step. Runs of one pass share a run_id."""

    class Outcome(models.TextChoices):
        # Retried, waiting for its job.
        QUEUED = "queued"
        RUNNING = "running"
        OK = "ok"
        FAILED = "failed"
        # Not needed this time, e.g. no sharing image.
        SKIPPED = "skipped"
        # 401, 403, 429, 503, or a challenge page that didn't clear.
        BLOCKED = "blocked"
        # Loaded, but nothing usable in it.
        NO_CONTENT = "no_content"

    step = models.ForeignKey(ItemStep, on_delete=models.CASCADE, related_name="runs")
    run_id = models.UUIDField()
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    # Step-specific details: HTTP status, final URL, counts, model...
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["started_at", "id"]
        indexes = [models.Index(fields=["step", "started_at"])]


class Tag(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tags"
    )
    # Normalised (tagging.normalize): lowercase kebab-case.
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="tag_user_name"),
            models.UniqueConstraint(fields=["user", "slug"], name="tag_user_slug"),
        ]

    def __str__(self):
        return self.name


class ItemTag(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual"
        PAGE = "page"
        MODEL = "model"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="item_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="item_tags")
    source = models.CharField(max_length=16, choices=Source.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "tag"], name="itemtag_item_tag"),
        ]


class ItemTagRemoval(models.Model):
    """A tag removed from an item, so automatic tagging doesn't re-add it."""

    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="tag_removals"
    )
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "name"], name="itemtagremoval_item_name"
            ),
        ]


@receiver(post_delete, sender=Item)
def delete_sources_dir(sender, instance, **kwargs):
    shutil.rmtree(instance.sources_dir, ignore_errors=True)
