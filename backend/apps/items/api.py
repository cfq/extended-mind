from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja.errors import HttpError
from ninja.security import django_auth

from apps.items import ids, tagging
from apps.items.fetch import clean_url
from apps.items.models import Item, ItemTag, Tag
from apps.items.schemas import (
    ItemIn,
    ItemOut,
    ItemSummaryOut,
    ItemTagOut,
    TagIn,
    TagOut,
    item_tags,
)
from apps.items.tasks import fetch_item
from apps.users.auth import token_auth

# Bearer token for the iOS Shortcut and scripts, session for the SPA.
router = Router(auth=[token_auth, django_auth])
tags_router = Router(auth=[token_auth, django_auth])


def get_item(request, item_id: str) -> Item:
    # Unknown, malformed and other users' IDs all look the same: 404.
    uuid = ids.decode(item_id)
    if uuid is None:
        raise Http404
    return get_object_or_404(
        Item.objects.prefetch_related("item_tags__tag"), id=uuid, user=request.user
    )


@router.post("", response={201: ItemOut})
def create_item(request, data: ItemIn):
    submitted = data.url.strip()
    try:
        URLValidator(schemes=["http", "https"])(submitted)
    except ValidationError as e:
        raise HttpError(400, "Enter a valid http(s) URL.") from e
    item = Item.objects.create(
        user=request.user, url=clean_url(submitted), url_submitted=submitted
    )
    fetch_item.defer(item_id=str(item.id))
    return Status(201, item)


@router.get("", response=list[ItemSummaryOut])
def list_items(request, tag: str | None = None):
    items = Item.objects.filter(user=request.user).prefetch_related("item_tags__tag")
    if tag:
        items = items.filter(item_tags__tag__slug=tag)
    return items


@router.get("/{item_id}", response=ItemOut)
def get_item_detail(request, item_id: str):
    return get_item(request, item_id)


@router.post("/{item_id}/retry", response=ItemOut)
def retry_item(request, item_id: str):
    item = get_item(request, item_id)
    item.status = Item.Status.PENDING
    item.error = ""
    item.save(update_fields=["status", "error"])
    fetch_item.defer(item_id=str(item.id))
    return item


@router.delete("/{item_id}", response={204: None})
def delete_item(request, item_id: str):
    get_item(request, item_id).delete()
    tagging.delete_unused(request.user)
    return Status(204, None)


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
