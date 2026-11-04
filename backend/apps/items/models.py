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
        HTML = "html"
        IMAGE = "image"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="sources")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    filename = models.CharField(max_length=255)
    # Final URL after redirects.
    url = models.URLField(max_length=2048)
    mime = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def path(self):
        return self.item.sources_dir / self.filename


@receiver(post_delete, sender=Item)
def delete_sources_dir(sender, instance, **kwargs):
    shutil.rmtree(instance.sources_dir, ignore_errors=True)
