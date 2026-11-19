import shutil
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Item(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        FETCHING = "fetching"
        DONE = "done"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    # Cleaned; after a fetch, the final URL after redirects.
    url = models.URLField(max_length=2048)
    url_submitted = models.TextField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    error = models.TextField(blank=True)
    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    author = models.TextField(blank=True)
    site_name = models.TextField(blank=True)
    published_at = models.DateField(null=True, blank=True)
    text = models.TextField(blank=True)
    markdown = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

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

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="sources")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    filename = models.CharField(max_length=255)
    # Pages and screenshots: final URL after redirects. Images: the URL as
    # written in the article's markdown.
    url = models.URLField(max_length=2048)
    mime = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def path(self):
        return self.item.sources_dir / self.filename


class FetchAttempt(models.Model):
    """One try at getting a page. Failure details live here, not on Item."""

    class Method(models.TextChoices):
        HTTP = "http"
        BROWSER = "browser"

    class Outcome(models.TextChoices):
        OK = "ok"
        # 401, 403, 429, 503, or a challenge page that didn't clear.
        BLOCKED = "blocked"
        # Loaded, but no article found in it.
        NO_CONTENT = "no_content"
        ERROR = "error"

    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="fetch_attempts"
    )
    method = models.CharField(max_length=16, choices=Method.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]


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
