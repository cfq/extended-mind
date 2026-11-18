import importlib

from django.apps import apps

from apps.items.models import Item, ItemTag, ItemTagRemoval, Tag

kebab = importlib.import_module("apps.items.migrations.0004_kebab_tag_names").kebab


def test_kebab_renames_and_merges(user, item):
    other = Item.objects.create(user=user, url="https://x.test", url_submitted="x")
    spaced = Tag.objects.create(user=user, name="open source", slug="open-source")
    kebabed = Tag.objects.create(user=user, name="open-source", slug="open-source-2")
    renamed = Tag.objects.create(user=user, name="art nouveau", slug="art-nouveau")
    folded = Tag.objects.create(user=user, name="família", slug="familia")
    junk = Tag.objects.create(user=user, name="---", slug="tag")
    ItemTag.objects.create(item=item, tag=spaced, source="manual")
    ItemTag.objects.create(item=item, tag=kebabed, source="page")
    ItemTag.objects.create(item=other, tag=spaced, source="model")
    ItemTag.objects.create(item=item, tag=junk, source="page")
    ItemTagRemoval.objects.create(item=item, name="art nouveau")

    kebab(apps, None)

    assert set(Tag.objects.values_list("name", flat=True)) == {
        "open-source",
        "art-nouveau",
        "familia",
    }
    assert Tag.objects.get(pk=folded.pk).name == "familia"
    assert Tag.objects.get(pk=renamed.pk).name == "art-nouveau"
    assert {link.item_id for link in kebabed.item_tags.all()} == {item.pk, other.pk}
    assert list(item.tag_removals.values_list("name", flat=True)) == ["art-nouveau"]


def test_delete_unused_tags(user, item):
    delete_unused = importlib.import_module(
        "apps.items.migrations.0005_delete_unused_tags"
    ).delete_unused
    used = Tag.objects.create(user=user, name="used", slug="used")
    Tag.objects.create(user=user, name="unused", slug="unused")
    ItemTag.objects.create(item=item, tag=used, source="manual")

    delete_unused(apps, None)

    assert list(Tag.objects.values_list("name", flat=True)) == ["used"]
