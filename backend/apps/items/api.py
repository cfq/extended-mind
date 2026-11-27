from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router, Status, UploadedFile
from ninja.errors import HttpError
from ninja.security import django_auth

from apps.items import ids, image_items, steps, tagging
from apps.items.fetch import clean_url
from apps.items.models import ImageItem, Item, ItemSource, ItemTag, Tag
from apps.items.schemas import (
    ItemIn,
    ItemOut,
    ItemSummaryOut,
    ItemTagOut,
    TagIn,
    TagOut,
    item_tags,
)
from apps.items.tasks import fetch_item, process_upload
from apps.users.auth import token_auth

# Bearer token for the iOS Shortcut and scripts, session for the SPA.
router = Router(auth=[token_auth, django_auth])
tags_router = Router(auth=[token_auth, django_auth])


def with_related(items):
    # Tags, steps and runs (status), sources (thumbnail): a query each.
    return items.prefetch_related("item_tags__tag", "steps__runs", "sources")


def get_item(request, item_id: str) -> Item:
    # Unknown, malformed and other users' IDs all look the same: 404.
    uuid = ids.decode(item_id)
    if uuid is None:
        raise Http404
    return get_object_or_404(with_related(Item.objects), id=uuid, user=request.user)


def valid_url(url: str, message: str) -> str:
    try:
        URLValidator(schemes=["http", "https"])(url)
    except ValidationError as e:
        raise HttpError(400, message) from e
    return url


@router.post("", response={201: ItemOut})
def create_item(request, data: ItemIn):
    submitted = valid_url(data.url.strip(), "Enter a valid http(s) URL.")
    item = Item.objects.create(
        user=request.user, url=clean_url(submitted), url_submitted=submitted
    )
    fetch_item.defer(item_id=str(item.id))
    return Status(201, item)


@router.post("/images", response={201: list[ItemOut]})
def upload_images(
    request,
    file: File[list[UploadedFile]],
    found_on: Form[str | None] = None,
):
    """One image item per file. All files are checked before any is saved."""
    if found_on := (found_on or "").strip() or None:
        valid_url(found_on, "Found on: enter a valid http(s) URL.")
    bodies = []
    for upload in file:
        if upload.size > image_items.MAX_BYTES:
            raise HttpError(400, f"{upload.name}: larger than 50 MB.")
        body = upload.read()
        try:
            image_items.check(body)
        except image_items.NotAnImage as e:
            raise HttpError(400, f"{upload.name}: {e}") from e
        bodies.append((upload.name or "image", body))
    created = []
    for name, body in bodies:
        run_id = steps.new_run_id()
        item = Item.objects.create(
            user=request.user,
            type=Item.Type.IMAGE,
            title=image_items.title_from(name),
            found_on=found_on,
        )
        ImageItem.objects.create(item=item)
        steps.need(item, "save_original", "dimensions")
        image_items.save_original(item, name, "", body, run_id)
        process_upload.defer(item_id=str(item.id), run_id=str(run_id))
        created.append(item.id)
    items = with_related(Item.objects).filter(id__in=created).order_by("created_at")
    return Status(201, list(items))


@router.get("", response=list[ItemSummaryOut])
def list_items(request, tag: str | None = None):
    items = with_related(Item.objects.filter(user=request.user))
    if tag:
        items = items.filter(item_tags__tag__slug=tag)
    return items


@router.get("/{item_id}", response=ItemOut)
def get_item_detail(request, item_id: str):
    return get_item(request, item_id)


# A new pass through the whole pipeline. Not in the UI yet.
@router.post("/{item_id}/retry", response=ItemOut)
def retry_item(request, item_id: str):
    item = get_item(request, item_id)
    fetch_item.defer(item_id=str(item.id))
    return item


@router.delete("/{item_id}", response={204: None})
def delete_item(request, item_id: str):
    get_item(request, item_id).delete()
    tagging.delete_unused(request.user)
    return Status(204, None)


SERVED_KINDS = [
    ItemSource.Kind.IMAGE,
    ItemSource.Kind.SCREENSHOT_FULL,
    ItemSource.Kind.SCREENSHOT_HEAD,
    ItemSource.Kind.PDF,
    ItemSource.Kind.OG_IMAGE,
    ItemSource.Kind.ORIGINAL,
]


# Saved images, screenshots and PDFs. Article image URLs are stored in item markdown
# (images.local_url): keep this path stable.
@router.get("/{item_id}/sources/{filename}")
def get_item_source(request, item_id: str, filename: str):
    item = get_item(request, item_id)
    # Images, screenshots and PDFs only: a saved HTML page served from here
    # could run scripts.
    # first(): the sharing image can be the same file as an article image.
    source = ItemSource.objects.filter(
        item=item, kind__in=SERVED_KINDS, filename=filename
    ).first()
    if source is None:
        raise Http404
    try:
        file = source.path.open("rb")
    except OSError as e:
        raise Http404 from e
    response = FileResponse(file, content_type=source.mime)
    # Filenames include the content hash, so a URL never changes content.
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    if source.mime == "image/svg+xml":
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
    return response


# Tags on an item. Both return the item's tags after the change.


@router.post("/{item_id}/tags", response=list[ItemTagOut])
def add_item_tag(request, item_id: str, data: TagIn):
    item = get_item(request, item_id)
    name = tagging.normalize(data.name)
    if not name:
        raise HttpError(400, f"Tag names are 1–{tagging.MAX_NAME} characters.")
    tagging.add_tags(item, [name], ItemTag.Source.MANUAL)
    return item_tags(get_item(request, item_id))


@router.delete("/{item_id}/tags/{slug}", response=list[ItemTagOut])
def remove_item_tag(request, item_id: str, slug: str):
    item = get_item(request, item_id)
    tag = get_object_or_404(Tag, user=request.user, slug=slug)
    tagging.remove_tag(item, tag)
    return item_tags(get_item(request, item_id))


@tags_router.get("", response=list[TagOut])
def list_tags(request):
    return Tag.objects.filter(user=request.user).annotate(count=Count("item_tags"))
